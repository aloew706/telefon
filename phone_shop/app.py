import glob
import io
import os
import re
from datetime import date

from flask import Flask, abort, flash, redirect, render_template, request, send_file, session, url_for
from werkzeug.exceptions import HTTPException

import config
import db

app = Flask(__name__, static_folder="static")
app.secret_key = config.SECRET_KEY
app.json.sort_keys = False
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024

DELIVERY_METHODS = ["Курьер", "Почта", "Самовывоз"]
PAYMENT_METHODS = ["Карта", "Наличные", "Рассрочка"]
MAX_QTY = 10

# Фото телефонов лежат в папке templates/photos (файлы phone_<код>.png и т. п.)
PHOTO_DIR = os.path.join(app.root_path, "templates", "photos")

COLORS = {
    "черный": ("#3a3a3c", "#111"), "белый": ("#fafafa", "#d8d8dc"), "синий": ("#5b8def", "#1f4fb5"),
    "серый": ("#a1a1a6", "#636366"), "зеленый": ("#7bd88f", "#2f8f4e"), "зелёный": ("#7bd88f", "#2f8f4e"),
    "фиолетовый": ("#b18cf0", "#6b3fc4"), "красный": ("#ff6b6b", "#b3202a"), "золотой": ("#f1d9a8", "#c29a4d"),
    "розовый": ("#f9a8c9", "#d6568a"), "голубой": ("#8fd3f4", "#3b9ed6"),
}


# ---------------------------------------------------------------- фото
PHOTO_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif")
MIME_EXT = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp", "image/gif": "gif"}


def _norm(s):
    return re.sub(r"[^0-9a-zа-яё]", "", (s or "").lower())


def photo_index():
    """Все картинки из папки templates/photos: по коду (phone_5.png) и по названию (Galaxy S24.png)."""
    by_id, by_name = {}, {}
    if os.path.isdir(PHOTO_DIR):
        for fn in os.listdir(PHOTO_DIR):
            base, ext = os.path.splitext(fn)
            if ext.lower() not in PHOTO_EXT:
                continue
            m = re.fullmatch(r"phone_(\d+)", base, re.I)
            if m:
                by_id[int(m.group(1))] = fn
            else:
                by_name[_norm(base)] = (fn, re.findall(r"[0-9a-zа-яё]+", base.lower()))
    return by_id, by_name


def photo_file(phone_id, model=None, brand=None):
    """Путь к фото телефона.
    1) phone_<код>.png; 2) файл с названием модели («Galaxy S24.png») или «марка модель»;
    3) файл, все слова которого есть в «марка модель» («google.png», «xiaomi.png», «apple 16.png»):
       побеждает файл с большим числом слов."""
    by_id, by_name = photo_index()
    fn = by_id.get(int(phone_id))
    if not fn and by_name:
        if model is None:
            p = phones_by_id(with_photo=False).get(int(phone_id))
            model, brand = (p["model"], p["brand"]) if p else (None, None)
        for key in (_norm(model), _norm(f"{brand or ''}{model or ''}")):
            if key and key in by_name:
                fn = by_name[key][0]
                break
        if not fn:
            words = set(re.findall(r"[0-9a-zа-яё]+", f"{brand or ''} {model or ''}".lower()))
            best = max(((len(t), name) for name, (f, t) in by_name.items() if t and set(t) <= words), default=None)
            if best:
                fn = by_name[best[1]][0]
    return os.path.join(PHOTO_DIR, fn) if fn else None


def photo_version(phone_id, model=None, brand=None):
    f = photo_file(phone_id, model, brand)
    return int(os.path.getmtime(f)) if f else None


def prepare_photo(data):
    """Проверяет загруженную картинку и по возможности превращает её в настоящий PNG.
    Возвращает (байты, расширение). Любой реальный снимок (PNG, JPEG, WEBP, GIF) принимается,
    даже если у файла «не то» расширение: часто PNG с сайтов на самом деле WEBP или JPEG."""
    if len(data) > db.MAX_PHOTO:
        raise ValueError("Фото слишком большое (максимум 10 МБ)")
    mime = db.sniff_image(data)
    if mime == "image/png":
        return data, "png"
    try:  # если установлена библиотека pillow, переводим в PNG
        from PIL import Image
    except ImportError:
        Image = None
    if Image is not None:
        try:
            im = Image.open(io.BytesIO(data))
            im.load()
            im.thumbnail((1600, 1600))
            has_alpha = im.mode in ("RGBA", "LA", "P") and (im.mode != "P" or "transparency" in im.info)
            im = im.convert("RGBA" if has_alpha else "RGB")
            out = io.BytesIO()
            im.save(out, "PNG", optimize=True)
            return out.getvalue(), "png"
        except Exception:
            raise ValueError("Не удалось прочитать картинку: выберите другой файл (PNG, JPG или WEBP)")
    if mime in MIME_EXT:  # без pillow сохраняем как есть, с правильным расширением
        return data, MIME_EXT[mime]
    raise ValueError("Это не картинка или формат не поддерживается: выберите PNG, JPG или WEBP")


def save_photo(phone_id, data, ext="png"):
    os.makedirs(PHOTO_DIR, exist_ok=True)
    for old in glob.glob(os.path.join(PHOTO_DIR, f"phone_{int(phone_id)}.*")):
        os.remove(old)
    with open(os.path.join(PHOTO_DIR, f"phone_{int(phone_id)}.{ext}"), "wb") as fh:
        fh.write(data)


# ---------------------------------------------------------------- фильтры
@app.template_filter("gradient")
def gradient(color):
    a, b = COLORS.get((color or "").strip().lower(), ("#c7c7cc", "#8e8e93"))
    return f"linear-gradient(160deg, {a}, {b})"


@app.template_filter("money")
def money(v):
    return "" if v is None else f"{float(v):,.0f}".replace(",", " ") + " ₽"


@app.template_filter("badge")
def badge(status):
    s = (status or "").lower()
    if "отмен" in s:
        return "bad"
    if "доставлен" in s:
        return "ok"
    return "warn" if s else ""


def digits(s):
    return re.sub(r"\D", "", s or "")[-10:]


def cart_dict():
    out = {}
    for k, v in session.get("cart", {}).items():
        try:
            out[int(k)] = int(v)
        except (TypeError, ValueError):
            pass
    return out


def save_cart(c):
    session["cart"] = {str(k): v for k, v in c.items() if v > 0}


@app.context_processor
def inject():
    return {"role": session.get("role"), "uname": session.get("name"), "path": request.path,
            "cart_count": sum(cart_dict().values())}


def need(*roles):
    if session.get("role") not in roles:
        flash("Войдите в систему", "error")
        abort(redirect(url_for("login")))


def login_as(**data):
    """Входим, но не теряем корзину, собранную до входа."""
    cart = session.get("cart")
    session.clear()
    session.update(data)
    if cart:
        session["cart"] = cart


def safe_next():
    nxt = request.form.get("next", "")
    if nxt.startswith("/") and not nxt.startswith("//"):
        return nxt
    return url_for("catalog")


@app.errorhandler(Exception)
def on_error(e):
    if isinstance(e, HTTPException):
        return e
    print("Ошибка:", e)
    if session.get("role") in ("admin", "seller"):
        msg = str(e)
    else:
        msg = "Не удалось выполнить действие. Попробуйте ещё раз чуть позже."
    return render_template("error.html", message=msg), 500


# ---------------------------------------------------------------- данные
def build_form(table, **kv):
    """Подставляет настоящие названия столбцов таблицы."""
    return {(db.col(table, k) or k): v for k, v in kv.items()}


def brand_map():
    bs = db.get_schema()["марки"]
    name_c, country_c = db.col("марки", "название_марки", "название"), db.col("марки", "страна")
    return {r[bs["pk"]]: {"название_марки": r.get(name_c), "страна": r.get(country_c)} for r in db.rows("марки")}


def stock_col():
    """Настоящее имя столбца с остатком на складе в таблице «телефоны»."""
    c = db.col("телефоны", "КоличествоНаСкладе", "Количество_на_складе", "количество", "остаток")
    if c:
        return c
    for f in db.get_schema()["телефоны"]["fields"]:
        if f["name"].lower().startswith(("количество", "остаток")):
            return f["name"]
    return None


def phone_view(p, brands, with_photo=True):
    def g(*aliases):
        c = db.col("телефоны", *aliases)
        return p.get(c) if c else None

    b = brands.get(g("код_марки"), {})
    pid = p[db.get_schema()["телефоны"]["pk"]]
    return {
        "id": pid,
        "brand": b.get("название_марки", ""), "country": b.get("страна", ""),
        "model": g("модель"), "storage": g("памятьГБ", "память"), "ram": g("ОЗУГБ", "ОЗУ"),
        "color": g("цвет"), "description": g("описание"), "price": g("цена"),
        "stock": p.get(stock_col()) if stock_col() else None,
        "photo": photo_version(pid, g("модель"), b.get("название_марки")) if with_photo else None,
    }


def phones_by_id(with_photo=True):
    brands = brand_map()
    out = {}
    for p in db.rows("телефоны"):
        v = phone_view(p, brands, with_photo)
        out[v["id"]] = v
    return out


def lookup_name(table, pk_value, field="ФИО", default=None):
    pk = db.get_schema()[table]["pk"]
    c = db.col(table, field)
    for r in db.rows(table):
        if r.get(pk) == pk_value:
            return (r.get(c) if c else None) or default
    return default


def stock_limit(p):
    try:
        if p["stock"] is not None and p["stock"] != "":
            return max(0, min(MAX_QTY, int(float(p["stock"]))))
    except (TypeError, ValueError):
        pass
    return MAX_QTY


def build_cart():
    phones = phones_by_id()
    items, total = [], 0.0
    for pid, qty in cart_dict().items():
        p = phones.get(pid)
        if not p or not p["price"]:
            continue
        s = round(float(p["price"]) * qty, 2)
        total += s
        items.append({**p, "qty": qty, "sum": s, "limit": stock_limit(p)})
    return items, round(total, 2)


def default_seller():
    sch = db.get_schema()["продавцы"]
    rows = db.rows("продавцы")
    pos = db.col("продавцы", "Должность")
    for r in rows:
        if pos and "консультант" in (r.get(pos) or "").lower():
            return r[sch["pk"]]
    return rows[0][sch["pk"]] if rows else None


def buyer_orders(buyer_id):
    """Заказы ТОЛЬКО указанного покупателя."""
    phones = phones_by_id()
    delivery = {d.get("Код_заказа"): d for d in db.rows("доставка")}
    out = []
    for o in db.rows("заказы"):
        if o.get("Код_покупателя") != buyer_id:
            continue
        d = delivery.get(o["Код_заказа"], {})
        out.append({
            "id": o["Код_заказа"], "phone_id": o.get("Код_телефона"),
            "model": phones.get(o.get("Код_телефона"), {}).get("model"),
            "photo": phones.get(o.get("Код_телефона"), {}).get("photo"),
            "date": o.get("Дата_заказа"), "qty": o.get("Количество"), "sum": o.get("Сумма"),
            "pay": o.get("Способ_оплаты"), "delivery": d.get("Способ_доставки"), "status": d.get("Статус"),
            "address": d.get("Адрес_доставки"), "sent": d.get("Дата_отправки"), "received": d.get("Дата_получения"),
            "has_delivery": bool(d),
        })
    out.sort(key=lambda x: x["id"], reverse=True)
    return out


def track_step(o):
    """1 — оформлен, 2 — в пути, 3 — доставлен, -1 — отменён."""
    s = (o.get("status") or "").lower()
    if "отмен" in s:
        return -1
    if o.get("received") or "доставлен" in s:
        return 3
    if o.get("sent") or "в пути" in s or "отправ" in s:
        return 2
    return 1


# ---------------------------------------------------------------- каталог
@app.get("/")
def catalog():
    q = request.args.get("q", "").strip()
    brand = request.args.get("brand", "").strip()
    items = list(phones_by_id().values())
    all_brands = sorted({i["brand"] for i in items if i["brand"]})
    shown = [i for i in items if (not brand or i["brand"] == brand) and (not q or q.lower() in (i["model"] or "").lower())]
    # два баннера справа: самая новая модель и самая выгодная цена (только то, что есть в наличии)
    avail = [i for i in items if i["price"] and not (i["stock"] not in (None, "") and float(i["stock"]) <= 0)]
    promo_new = max(avail, key=lambda i: i["id"], default=None)
    rest = [i for i in avail if not promo_new or i["id"] != promo_new["id"]]
    promo_cheap = min(rest, key=lambda i: float(i["price"]), default=None)
    return render_template("catalog.html", items=shown, brands=all_brands, q=q, brand=brand,
                           promo_new=promo_new, promo_cheap=promo_cheap)


@app.get("/phone/<int:id>")
def phone(id):
    p = phones_by_id().get(id)
    if not p:
        abort(404)
    return render_template("phone.html", p=p)


@app.get("/photo/<int:id>")
def photo(id):
    f = photo_file(id)
    if not f:
        abort(404)
    with open(f, "rb") as fh:
        mime = db.sniff_image(fh.read(16))
    if not mime:
        abort(404)  # в папке лежит не картинка
    return send_file(f, mimetype=mime, max_age=300)


# ---------------------------------------------------------------- вход, регистрация
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        lg = request.form.get("login", "").strip()
        pw = request.form.get("password", "").strip()
        if lg == config.ADMIN_LOGIN and pw == config.ADMIN_PASSWORD:
            login_as(role="admin", name="Администратор")
            return redirect(url_for("admin"))
        if db.table_exists("логины"):
            for r in db.rows("логины"):
                if (r.get("Логин") or "").strip().lower() == lg.lower() and (r.get("Пароль") or "") == pw and pw:
                    role = (r.get("Роль") or "").strip()
                    if role == "Администратор":
                        login_as(role="admin", name=lookup_name("продавцы", r.get("Код_сотрудника"), default="Администратор"))
                        return redirect(url_for("admin"))
                    if role == "Продавец":
                        login_as(role="seller", name=lookup_name("продавцы", r.get("Код_сотрудника"), default=lg))
                        return redirect(url_for("admin"))
                    login_as(role="user", name=lookup_name("покупатели", r.get("Код_покупателя"), default=lg),
                             buyer_id=r.get("Код_покупателя"))
                    return redirect(url_for("cart") if session.get("cart") else url_for("catalog"))
        else:  # таблицы «логины» нет — старый вход: email + номер телефона
            if lg and digits(pw):
                for b in db.rows("покупатели"):
                    if (b.get("email") or "").strip().lower() == lg.lower() and digits(b.get("номер_телефона")) == digits(pw):
                        login_as(role="user", name=b.get("ФИО") or lg, buyer_id=b["Код_Покупателя"])
                        return redirect(url_for("catalog"))
        return render_template("login.html", error="Неверный логин или пароль", login=lg)
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("role"):
        return redirect(url_for("catalog"))
    if request.method == "GET":
        return render_template("register.html", f={})
    f = {k: request.form.get(k, "").strip() for k in ("fio", "phone", "email", "address", "login", "password", "password2")}
    err = None
    if len(f["fio"]) < 3:
        err = "Введите ФИО"
    elif len(digits(f["phone"])) < 10:
        err = "Введите номер телефона полностью"
    elif not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", f["email"]):
        err = "Введите корректный email"
    elif not f["address"]:
        err = "Введите адрес"
    elif len(f["login"]) < 3 or " " in f["login"]:
        err = "Логин: не меньше 3 символов, без пробелов"
    elif len(f["password"]) < 4:
        err = "Пароль: не меньше 4 символов"
    elif f["password"] != f["password2"]:
        err = "Пароли не совпадают"
    if not err:
        try:
            if not db.table_exists("логины"):
                db.ensure_logins()
            taken = {(r.get("Логин") or "").strip().lower() for r in db.rows("логины")} | {config.ADMIN_LOGIN.lower()}
            emails = {(r.get("email") or "").strip().lower() for r in db.rows("покупатели")}
            if f["login"].lower() in taken:
                err = "Такой логин уже занят"
            elif f["email"].lower() in emails:
                err = "Покупатель с таким email уже зарегистрирован"
            else:
                bid = db.insert("покупатели", build_form("покупатели", ФИО=f["fio"], номер_телефона=f["phone"],
                                                         email=f["email"], Адрес=f["address"]))
                try:
                    db.insert("логины", build_form("логины", Логин=f["login"], Пароль=f["password"],
                                                   Роль="Покупатель", Код_покупателя=str(bid)))
                except Exception:
                    db.delete_row("покупатели", bid)
                    raise
                login_as(role="user", name=f["fio"], buyer_id=bid)
                flash("Добро пожаловать! Аккаунт создан", "ok")
                return redirect(url_for("catalog"))
        except Exception as e:
            print("Ошибка регистрации:", e)
            err = "Не удалось создать аккаунт. Попробуйте ещё раз чуть позже."
    return render_template("register.html", f=f, error=err)


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("catalog"))


# ---------------------------------------------------------------- корзина и заказы покупателя
@app.get("/cart")
def cart():
    if session.get("role") in ("admin", "seller"):
        return redirect(url_for("admin"))
    items, total = build_cart()
    address = ""
    if session.get("role") == "user":
        address = lookup_name("покупатели", session.get("buyer_id"), field="Адрес", default="") or ""
    return render_template("cart.html", items=items, total=total, address=address,
                           delivery_methods=DELIVERY_METHODS, payment_methods=PAYMENT_METHODS)


@app.post("/cart/add/<int:pid>")
def cart_add(pid):
    if session.get("role") in ("admin", "seller"):
        flash("Корзина доступна только покупателям", "error")
        return redirect(safe_next())
    p = phones_by_id().get(pid)
    if not p or not p["price"]:
        flash("Этот телефон пока нельзя заказать", "error")
        return redirect(safe_next())
    limit = stock_limit(p)
    if limit <= 0:
        flash("Этого телефона сейчас нет в наличии", "error")
        return redirect(safe_next())
    c = cart_dict()
    c[pid] = min(c.get(pid, 0) + 1, limit)
    save_cart(c)
    flash(f"«{p['model']}» добавлен в корзину", "ok")
    return redirect(safe_next())


@app.post("/cart/update/<int:pid>")
def cart_update(pid):
    p = phones_by_id().get(pid)
    try:
        qty = int(request.form.get("qty", "1"))
    except ValueError:
        qty = 1
    c = cart_dict()
    if p and pid in c:
        c[pid] = max(0, min(qty, stock_limit(p)))
        save_cart(c)
    return redirect(url_for("cart"))


@app.post("/cart/remove/<int:pid>")
def cart_remove(pid):
    c = cart_dict()
    c.pop(pid, None)
    save_cart(c)
    return redirect(url_for("cart"))


class OutOfStock(Exception):
    pass


@app.post("/checkout")
def checkout():
    need("user")
    items, _ = build_cart()
    if not items:
        flash("Корзина пуста", "error")
        return redirect(url_for("cart"))
    method = request.form.get("delivery", "")
    pay = request.form.get("payment", "")
    address = request.form.get("address", "").strip()
    if method not in DELIVERY_METHODS or pay not in PAYMENT_METHODS:
        flash("Выберите способ доставки и оплаты", "error")
        return redirect(url_for("cart"))
    if method == "Самовывоз":
        address = "Самовывоз из магазина"
    elif not address:
        flash("Укажите адрес доставки", "error")
        return redirect(url_for("cart"))
    # 1) хватает ли товара на складе: если нет — подправляем корзину
    col = stock_col()
    c = cart_dict()
    short = []
    for it in items:
        if col and it["stock"] not in (None, ""):
            try:
                have = max(0, int(float(it["stock"])))
            except (TypeError, ValueError):
                continue
            if it["qty"] > have:
                short.append((it, have))
    if short:
        for it, have in short:
            c[it["id"]] = have
        save_cart(c)
        flash("Не хватает товара на складе: " + "; ".join(
            f"«{it['model']}» — осталось {have} шт." if have else f"«{it['model']}» закончился" for it, have in short)
            + ". Корзина обновлена", "error")
        return redirect(url_for("cart"))
    # 2) оформляем: списываем со склада и записываем заказ и доставку
    try:
        seller = default_seller()
        if seller is None:
            raise RuntimeError("нет продавцов")
        for it in items:
            taken = False
            if col:
                if not db.take_stock(it["id"], col, it["qty"]):
                    raise OutOfStock(it["model"])
                taken = True
            try:
                oid = db.insert("заказы", build_form(
                    "заказы", Код_покупателя=str(session["buyer_id"]), Код_телефона=str(it["id"]), Код_сотрудника=str(seller),
                    Дата_заказа=date.today().isoformat(), Количество=str(it["qty"]), Сумма=str(it["sum"]), Способ_оплаты=pay))
                try:
                    db.insert("доставка", build_form("доставка", Код_заказа=str(oid), Способ_доставки=method,
                                                     Адрес_доставки=address, Статус="Оформлен"))
                except Exception:
                    db.delete_row("заказы", oid)
                    raise
            except Exception:
                if taken:
                    db.return_stock(it["id"], col, it["qty"])  # заказ не записался — товар возвращаем
                raise
    except OutOfStock as e:
        flash(f"«{e}» только что закончился. Проверьте корзину", "error")
        return redirect(url_for("cart"))
    except Exception as e:
        print("Ошибка оформления заказа:", e)
        flash("Не удалось оформить заказ. Попробуйте ещё раз чуть позже.", "error")
        return redirect(url_for("cart"))
    save_cart({})
    flash("Заказ оформлен! Следите за ним на этой странице", "ok")
    return redirect(url_for("orders"))


@app.get("/orders")
def orders():
    need("user")
    return render_template("orders.html", orders=buyer_orders(session["buyer_id"]), step=track_step)


@app.get("/orders/<int:id>")
def order_track(id):
    need("user")
    for o in buyer_orders(session["buyer_id"]):  # чужие заказы сюда не попадают
        if o["id"] == id:
            return render_template("track.html", o=o, step=track_step(o))
    abort(404)


# ---------------------------------------------------------------- управление (админ и продавец)
def brand_options():
    bs = db.get_schema()["марки"]
    name_c = db.col("марки", "название_марки", "название")
    return {r[bs["pk"]]: r.get(name_c) for r in db.rows("марки")}


def all_orders():
    """Все заказы всех покупателей (только для админа и продавца)."""
    phones = phones_by_id(with_photo=False)
    buyers = {r.get("Код_Покупателя"): r for r in db.rows("покупатели")}
    delivery = {d.get("Код_заказа"): d for d in db.rows("доставка")}
    out = []
    for o in db.rows("заказы"):
        b = buyers.get(o.get("Код_покупателя"), {})
        d = delivery.get(o["Код_заказа"], {})
        out.append({
            "id": o["Код_заказа"], "date": o.get("Дата_заказа"),
            "buyer": b.get("ФИО"), "phone": b.get("номер_телефона"), "email": b.get("email"),
            "model": phones.get(o.get("Код_телефона"), {}).get("model"),
            "qty": o.get("Количество"), "sum": o.get("Сумма"), "pay": o.get("Способ_оплаты"),
            "delivery": d.get("Способ_доставки"), "address": d.get("Адрес_доставки"), "status": d.get("Статус"),
        })
    out.sort(key=lambda x: x["id"], reverse=True)
    return out


def resolve_brand(form):
    """Если выбрана не марка из списка, а вписана новая — создаём её (или берём уже существующую)."""
    brand_col = db.col("телефоны", "код_марки")
    new_brand = form.pop("new_brand", "").strip()
    if brand_col and not form.get(brand_col) and new_brand:
        existing = {(v or "").strip().lower(): k for k, v in brand_options().items()}
        if new_brand.lower() in existing:
            form[brand_col] = str(existing[new_brand.lower()])
        else:
            form[brand_col] = str(db.insert("марки", build_form("марки", название_марки=new_brand)))
    return form


@app.get("/admin")
def admin():
    need("admin", "seller")
    t = request.args.get("t", "add")
    if t == "orders":
        orders_list = all_orders()
        total = sum(float(o["sum"] or 0) for o in orders_list)
        return render_template("admin.html", t="orders", orders=orders_list, total=total)
    meta = db.get_schema()["телефоны"]
    brand_col = db.col("телефоны", "код_марки")
    fk_options = {brand_col: brand_options()} if brand_col else {}
    if t == "edit":
        q = request.args.get("q", "").strip().lower()
        brands = brand_map()
        items = []
        for r in db.rows("телефоны"):
            v = phone_view(r, brands)
            if q and q not in f"{v['brand']} {v['model']}".lower():
                continue
            items.append({"v": v, "raw": r})
        return render_template("admin.html", t="edit", meta=meta, fk_options=fk_options, brand_col=brand_col, items=items,
                               q=request.args.get("q", ""), open_id=request.args.get("open", type=int))
    return render_template("admin.html", t="add", meta=meta, fk_options=fk_options, brand_col=brand_col)


@app.post("/admin/add")
def admin_add():
    need("admin", "seller")
    try:
        form = resolve_brand(request.form.to_dict())
        f = request.files.get("photo")
        data = f.read() if f is not None and f.filename else b""
        ext = "png"
        if data:
            data, ext = prepare_photo(data)  # проверяем до записи в базу
        new_id = db.insert("телефоны", form)
        if data:
            save_photo(new_id, data, ext)
        flash(f"Телефон «{form.get(db.col('телефоны', 'модель'))}» добавлен в каталог (код {new_id})", "ok")
    except ValueError as e:
        flash(str(e), "error")
    except Exception as e:
        print("Ошибка добавления телефона:", e)
        flash(f"Не удалось добавить телефон: {e}", "error")
    return redirect(url_for("admin", t="add"))


@app.post("/admin/phone/<int:id>")
def admin_phone_edit(id):
    need("admin", "seller")
    pk = db.get_schema()["телефоны"]["pk"]
    if id not in {r[pk] for r in db.rows("телефоны")}:
        abort(404)
    try:
        form = resolve_brand(request.form.to_dict())
        f = request.files.get("photo")
        data = f.read() if f is not None and f.filename else b""
        ext = "png"
        if data:
            data, ext = prepare_photo(data)  # проверяем до записи в базу
        db.update("телефоны", id, form)
        if data:
            save_photo(id, data, ext)
        flash(f"Изменения сохранены (код {id})" + (", фото обновлено" if data else ""), "ok")
    except ValueError as e:
        flash(str(e), "error")
    except Exception as e:
        print("Ошибка сохранения телефона:", e)
        flash(f"Не удалось сохранить: {e}", "error")
    return redirect(url_for("admin", t="edit", open=id, _anchor=f"p{id}"))


if __name__ == "__main__":
    try:
        added = db.ensure_schema()
        if added:
            print("В таблицу «телефоны» добавлены столбцы:", ", ".join(added))
    except Exception as e:
        print("Не удалось проверить таблицу «телефоны»:", e)
    try:
        if db.ensure_logins():
            print("Таблица «логины» создана в базе Access.")
    except Exception as e:
        print("Не удалось проверить/создать таблицу «логины»:", e)
    print("Сайт: http://127.0.0.1:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)

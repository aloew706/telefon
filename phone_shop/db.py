"""Работа с базой Access через ODBC (pyodbc)."""
import datetime
import decimal

import pyodbc

import config

# Описание таблиц: имена как в вашем файле Access.
# kind: text / int / money / date ; fk — ссылка на другую таблицу ; req — обязательное поле
SCHEMA = {
    "марки": {
        "title": "Марки", "pk": "Код_марки",
        "fields": [
            {"name": "название_марки", "label": "Название марки", "kind": "text", "req": True},
            {"name": "страна", "label": "Страна", "kind": "text", "req": False},
        ],
    },
    "цвет": {
        "title": "Цвета", "pk": "Код_Цвета",
        "fields": [{"name": "Цвет", "label": "Цвет", "kind": "text", "req": True}],
    },
    "память": {
        "title": "Память", "pk": "Код_памяти",
        "fields": [{"name": "память", "label": "Объем памяти, ГБ", "kind": "int", "req": True}],
    },
    "телефоны": {
        "title": "Телефоны", "pk": "Код_телефона",
        "fields": [
            {"name": "код_марки", "label": "Марка", "kind": "int", "fk": "марки", "req": True},
            {"name": "модель", "label": "Модель", "kind": "text", "req": True},
            {"name": "памятьГБ", "label": "Память, ГБ", "kind": "int", "req": True},
            {"name": "ОЗУГБ", "label": "ОЗУ, ГБ", "kind": "int", "req": True},
            {"name": "цвет", "label": "Цвет", "kind": "text", "req": False},
            {"name": "описание", "label": "Описание", "kind": "text", "req": False},
        ],
    },
    "покупатели": {
        "title": "Покупатели", "pk": "Код_Покупателя",
        "fields": [
            {"name": "ФИО", "label": "ФИО", "kind": "text", "req": True},
            {"name": "номер_телефона", "label": "Номер телефона", "kind": "text", "req": True},
            {"name": "email", "label": "Email", "kind": "text", "req": True},
            {"name": "Адрес", "label": "Адрес", "kind": "text", "req": False},
        ],
    },
    "продавцы": {
        "title": "Продавцы", "pk": "Код_Сотрудника",
        "fields": [
            {"name": "ФИО", "label": "ФИО", "kind": "text", "req": True},
            {"name": "Должность", "label": "Должность", "kind": "text", "req": False},
        ],
    },
    "заказы": {
        "title": "Заказы", "pk": "Код_заказа",
        "fields": [
            {"name": "Код_покупателя", "label": "Покупатель", "kind": "int", "fk": "покупатели", "req": True},
            {"name": "Код_телефона", "label": "Телефон", "kind": "int", "fk": "телефоны", "req": True},
            {"name": "Код_сотрудника", "label": "Продавец", "kind": "int", "fk": "продавцы", "req": True},
            {"name": "Дата_заказа", "label": "Дата заказа", "kind": "date", "req": True},
            {"name": "Количество", "label": "Количество", "kind": "int", "req": True},
            {"name": "Сумма", "label": "Сумма, ₽", "kind": "money", "req": True},
            {"name": "Способ_оплаты", "label": "Способ оплаты", "kind": "text", "req": False},
        ],
    },
    "доставка": {
        "title": "Доставка", "pk": "Код_доставки",
        "fields": [
            {"name": "Код_заказа", "label": "Заказ", "kind": "int", "fk": "заказы", "req": True},
            {"name": "Способ_доставки", "label": "Способ доставки", "kind": "text", "req": True},
            {"name": "Адрес_доставки", "label": "Адрес доставки", "kind": "text", "req": False},
            {"name": "Дата_отправки", "label": "Дата отправки", "kind": "date", "req": False},
            {"name": "Дата_получения", "label": "Дата получения", "kind": "date", "req": False},
            {"name": "Статус", "label": "Статус", "kind": "text", "req": False},
        ],
    },
}

ROLES = ["Администратор", "Продавец", "Покупатель"]

SCHEMA["логины"] = {
    "title": "Логины", "pk": "Код_логина", "admin_only": True,
    "fields": [
        {"name": "Логин", "label": "Логин", "kind": "text", "req": True},
        {"name": "Пароль", "label": "Пароль", "kind": "text", "req": True},
        {"name": "Роль", "label": "Роль", "kind": "text", "req": True, "choices": ROLES},
        {"name": "Код_покупателя", "label": "Покупатель (для роли «Покупатель»)", "kind": "int", "fk": "покупатели", "req": False},
        {"name": "Код_сотрудника", "label": "Сотрудник (для ролей «Продавец» и «Администратор»)", "kind": "int", "fk": "продавцы", "req": False},
    ],
}

BINARY_TYPES = {"LONGBINARY", "VARBINARY", "BINARY", "OLEOBJECT", "IMAGE"}
LONGTEXT_TYPES = {"LONGCHAR", "MEMO", "LONGTEXT", "LONGVARCHAR"}
MAX_PHOTO = 10 * 1024 * 1024
INT_TYPES = {"INTEGER", "LONG", "SHORT", "SMALLINT", "BYTE", "TINYINT", "COUNTER", "INT", "BIGINT"}
NUM_TYPES = {"CURRENCY", "DOUBLE", "SINGLE", "REAL", "FLOAT", "DECIMAL", "NUMERIC"}
DATE_TYPES = {"DATETIME", "DATE", "TIMESTAMP"}
BOOL_TYPES = {"BIT", "YESNO"}


def connect():
    conn_str = (
        r"DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};"
        f"DBQ={config.DB_PATH};"
    )
    try:
        return pyodbc.connect(conn_str, autocommit=False)
    except pyodbc.Error as e:
        import struct
        raise RuntimeError(
            f"Python {struct.calcsize('P') * 8}-бит. Не удалось открыть базу Access. Проверьте путь DB_PATH в config.py, "
            "что файл не открыт в режиме монопольного доступа, и что установлен "
            "драйвер Microsoft Access Database Engine (той же разрядности, что и Python). "
            f"Подробности: {e}"
        )


def _tables(conn):
    cur = conn.cursor()
    return {r.table_name.lower(): r.table_name for r in cur.tables(tableType="TABLE")}


def _columns(conn, table):
    cur = conn.cursor()
    return [(r.column_name, (r.type_name or "").upper()) for r in cur.columns(table=table)]


def _table_exists(conn, name):
    return name.lower() in _tables(conn)


def table_exists(name):
    conn = connect()
    try:
        return _table_exists(conn, name)
    finally:
        conn.close()


def _column_types(conn, table):
    return dict(_columns(conn, table))


def _last_id(cur):
    cur.execute("SELECT @@IDENTITY")
    return cur.fetchone()[0]


def _coerce(value, type_name, kind):
    """Приводим значение из формы к типу поля в Access."""
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return None
    t = (type_name or "").upper()
    if t in INT_TYPES or (not t and kind == "int"):
        return int(str(value).strip())
    if t in NUM_TYPES or (not t and kind == "money"):
        return decimal.Decimal(str(value).strip().replace(",", "."))
    if t in DATE_TYPES or (not t and kind == "date"):
        return datetime.datetime.strptime(str(value).strip(), "%Y-%m-%d")
    if t in BOOL_TYPES:
        return str(value).strip().lower() in ("1", "true", "да", "on")
    return str(value).strip()


def _jsonable(v):
    if isinstance(v, (datetime.datetime, datetime.date)):
        return v.strftime("%Y-%m-%d")
    if isinstance(v, decimal.Decimal):
        return float(v)
    return v


_cache = {}


def _hint(table, name, typ):
    """Подсказка для поля формы: подпись, вид, обязательность."""
    lname = name.lower()
    h = None
    for f in SCHEMA[table]["fields"]:
        if f["name"].lower() == lname:
            h = dict(f)
            break
    if h is None:
        if lname in ("память", "памятьгб"):
            h = {"label": "Память, ГБ", "kind": "int", "req": True}
        elif lname in ("озу", "озугб"):
            h = {"label": "ОЗУ, ГБ", "kind": "int", "req": True}
        elif lname == "цена":
            h = {"label": "Цена, ₽", "kind": "money", "req": True}
        elif lname.startswith("количество"):
            h = {"label": "Количество на складе" if "склад" in lname else "Количество", "kind": "int", "req": False}
        elif lname in ("фото", "photo"):
            h = {"label": "Фото телефона", "kind": "file", "req": False}
        else:
            h = {"label": name.replace("_", " ").capitalize(), "kind": "text", "req": False}
    h["name"] = name
    if typ in BINARY_TYPES:
        h["kind"] = "file"
        h["label"] = "Фото телефона" if table == "телефоны" else "Фото"
        h["req"] = False
    elif typ in LONGTEXT_TYPES or lname == "описание":
        h["kind"] = "longtext"
    elif typ in BOOL_TYPES:
        h["kind"] = "bool"
        h["req"] = False
    elif typ in DATE_TYPES and h["kind"] not in ("date",):
        h["kind"] = "date"
    return h


def get_schema(refresh=False):
    """Схема таблиц по ФАКТИЧЕСКИМ столбцам вашей базы Access."""
    if _cache.get("schema") and not refresh:
        return _cache["schema"]
    conn = connect()
    try:
        tables = _tables(conn)
        out = {}
        for t, meta in SCHEMA.items():
            if t.lower() not in tables:
                continue
            real = tables[t.lower()]
            cols = _columns(conn, real)
            if not cols:
                continue
            names = [c[0] for c in cols]
            pk = meta["pk"] if meta["pk"] in names else names[0]
            fields = [_hint(t, n, ty) for n, ty in cols if n != pk and ty not in BINARY_TYPES]
            out[t] = {"title": meta["title"], "pk": pk, "fields": fields, "real": real,
                      "admin_only": meta.get("admin_only", False), "types": dict(cols)}
    finally:
        conn.close()
    _cache["schema"] = out
    return out


def col(table, *aliases):
    """Настоящее имя столбца таблицы по списку возможных названий."""
    sch = get_schema().get(table)
    if not sch:
        return None
    names = {f["name"].lower(): f["name"] for f in sch["fields"]}
    for a in aliases:
        if a.lower() in names:
            return names[a.lower()]
    return None


def rows(table):
    """Все строки таблицы."""
    sch = get_schema()[table]
    pk = sch["pk"]
    names_sel = [pk] + [f["name"] for f in sch["fields"]]
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT {', '.join('[' + n + ']' for n in names_sel)} FROM [{sch['real']}]")
        names = [d[0] for d in cur.description]
        data = [{n: _jsonable(v) for n, v in zip(names, r)} for r in cur.fetchall()]
    finally:
        conn.close()
    data.sort(key=lambda r: (r.get(pk) is None, r.get(pk)))
    return data


def sniff_image(b):
    if b[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP":
        return "image/webp"
    if b[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    return None


SEED_STOCK = {"Galaxy S24": 15, "iPhone 15": 10, "Redmi Note 13": 30,
              "P60 Pro": 7, "Pixel 8": 9, "G42 5G": 20}
SEED_PRICES = {"Galaxy S24": 79990, "iPhone 15": 74990, "Redmi Note 13": 19990,
               "P60 Pro": 64990, "Pixel 8": 59990, "G42 5G": 14990}


def take_stock(phone_id, col, qty):
    """Списывает qty штук со склада. True — списано (или остаток не ведётся), False — не хватает."""
    sch = get_schema()["телефоны"]
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT [{col}] FROM [{sch['real']}] WHERE [{sch['pk']}] = ?", (int(phone_id),))
        row = cur.fetchone()
        if row is None:
            return False
        if row[0] is None:
            return True  # остаток не указан — учёт не ведётся
        cur.execute(f"UPDATE [{sch['real']}] SET [{col}] = [{col}] - ? WHERE [{sch['pk']}] = ? AND [{col}] >= ?",
                    (int(qty), int(phone_id), int(qty)))
        conn.commit()
        return cur.rowcount > 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def return_stock(phone_id, col, qty):
    """Возвращает qty штук на склад (если заказ не удалось оформить)."""
    sch = get_schema()["телефоны"]
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute(f"UPDATE [{sch['real']}] SET [{col}] = [{col}] + ? WHERE [{sch['pk']}] = ? AND [{col}] IS NOT NULL",
                    (int(qty), int(phone_id)))
        conn.commit()
    finally:
        conn.close()


def ensure_schema():
    """Добавляет в таблицу «телефоны» недостающие столбцы: память, ОЗУ, описание, цена."""
    conn = connect()
    try:
        tables = _tables(conn)
        if "телефоны" not in tables:
            return []
        real = tables["телефоны"]
        have = {n.lower() for n, _ in _columns(conn, real)}
        todo = []
        if not ({"памятьгб", "память"} & have):
            todo.append(("памятьГБ", "LONG"))
        if not ({"озугб", "озу"} & have):
            todo.append(("ОЗУГБ", "LONG"))
        if "описание" not in have:
            todo.append(("описание", "LONGTEXT"))
        if "цена" not in have:
            todo.append(("цена", "CURRENCY"))
        if not any(n.startswith("количество") or n.startswith("остаток") for n in have):
            todo.append(("КоличествоНаСкладе", "LONG"))
        cur = conn.cursor()
        for name, typ in todo:
            cur.execute(f"ALTER TABLE [{real}] ADD COLUMN [{name}] {typ}")
            conn.commit()
        if any(n == "цена" for n, _ in todo):  # проставляем цены известным моделям (как в заказах)
            for model, price in SEED_PRICES.items():
                try:
                    cur.execute(f"UPDATE [{real}] SET [цена] = ? WHERE [модель] = ?", (price, model))
                    conn.commit()
                except Exception:
                    conn.rollback()
        if any(n == "КоличествоНаСкладе" for n, _ in todo):  # стартовые остатки известным моделям
            for model, qty in SEED_STOCK.items():
                try:
                    cur.execute(f"UPDATE [{real}] SET [КоличествоНаСкладе] = ? WHERE [модель] = ?", (qty, model))
                    conn.commit()
                except Exception:
                    conn.rollback()
        _cache.clear()
        return [n for n, _ in todo]
    finally:
        conn.close()


def insert(table, form):
    """Добавляет строку в таблицу Access. Возвращает новый код."""
    sch = get_schema()[table]
    fields = sch["fields"]
    for f in fields:
        if f["req"] and str(form.get(f["name"], "")).strip() == "":
            raise ValueError(f"Заполните поле «{f['label']}»")
    conn = connect()
    try:
        types = sch["types"]
        cols, vals = [], []
        for f in fields:
            name = f["name"]
            if f["kind"] == "bool":
                cols.append(name)
                vals.append(name in form)
                continue
            if name not in form:
                continue
            try:
                v = _coerce(form[name], types.get(name, ""), f["kind"])
            except (ValueError, decimal.InvalidOperation):
                raise ValueError(f"Неверное значение в поле «{f['label']}»")
            if v is None and not f["req"]:
                continue
            cols.append(name)
            vals.append(v)
        if not cols:
            raise ValueError("Нет данных для добавления")
        sql = (
            f"INSERT INTO [{sch['real']}] ({', '.join('[' + c + ']' for c in cols)}) "
            f"VALUES ({', '.join('?' for _ in cols)})"
        )
        cur = conn.cursor()
        cur.execute(sql, vals)
        new_id = _last_id(cur)
        conn.commit()
        return int(new_id) if new_id is not None else None
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def update(table, row_id, form):
    """Сохраняет изменения строки в таблице Access (кроме файлов-фото)."""
    sch = get_schema()[table]
    sets, vals = [], []
    for f in sch["fields"]:
        name = f["name"]
        if name not in form:
            continue
        if table == "логины" and name == "Пароль" and str(form[name]).strip() == "":
            continue  # пустой пароль = не менять
        try:
            v = _coerce(form[name], sch["types"].get(name, ""), f["kind"])
        except (ValueError, decimal.InvalidOperation):
            raise ValueError(f"Неверное значение в поле «{f['label']}»")
        if v is None:
            if f["req"]:
                raise ValueError(f"Заполните поле «{f['label']}»")
            sets.append(f"[{name}] = NULL")
        else:
            sets.append(f"[{name}] = ?")
            vals.append(v)
    if not sets:
        raise ValueError("Нет данных для сохранения")
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute(f"UPDATE [{sch['real']}] SET {', '.join(sets)} WHERE [{sch['pk']}] = ?", vals + [int(row_id)])
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def delete_row(table, row_id):
    sch = get_schema()[table]
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute(f"DELETE FROM [{sch['real']}] WHERE [{sch['pk']}] = ?", (int(row_id),))
        conn.commit()
    finally:
        conn.close()


# ---------- таблица «логины»: создаётся автоматически при первом запуске ----------
LOGIN_DDL = [
    "CREATE TABLE [логины] ([Код_логина] COUNTER PRIMARY KEY, [Логин] VARCHAR(50) NOT NULL, "
    "[Пароль] VARCHAR(50) NOT NULL, [Роль] VARCHAR(20) NOT NULL, [Код_покупателя] LONG, [Код_сотрудника] LONG)",
    "CREATE UNIQUE INDEX [idx_логин] ON [логины] ([Логин])",
]
LOGIN_FK = [
    "ALTER TABLE [логины] ADD CONSTRAINT [покупателилогины] FOREIGN KEY ([Код_покупателя]) "
    "REFERENCES [покупатели] ([Код_Покупателя])",
    "ALTER TABLE [логины] ADD CONSTRAINT [продавцылогины] FOREIGN KEY ([Код_сотрудника]) "
    "REFERENCES [продавцы] ([Код_Сотрудника])",
]
LOGIN_ROWS = [
    ("admin", "admin123", "Администратор", None, 6),
    ("ivanov", "seller01", "Продавец", None, 1),
    ("smirnova", "seller02", "Продавец", None, 2),
    ("petrov", "pass1001", "Покупатель", 1, None),
    ("sidorova", "pass1002", "Покупатель", 2, None),
    ("kozlov", "pass1003", "Покупатель", 3, None),
    ("morozova", "pass1004", "Покупатель", 4, None),
    ("volkov", "pass1005", "Покупатель", 5, None),
    ("novikova", "pass1006", "Покупатель", 6, None),
]


def ensure_logins():
    """Создаёт таблицу «логины» в Access (с данными и связями), если её ещё нет."""
    conn = connect()
    try:
        if _table_exists(conn, "логины"):
            return False
        cur = conn.cursor()
        for sql in LOGIN_DDL:
            cur.execute(sql)
        conn.commit()
        for sql in LOGIN_FK:
            try:
                cur.execute(sql)
                conn.commit()
            except Exception as e:
                print("Связь для таблицы «логины» не создана автоматически, создайте её в Схеме данных:", e)
        for row in LOGIN_ROWS:
            try:
                cur.execute(
                    "INSERT INTO [логины] ([Логин], [Пароль], [Роль], [Код_покупателя], [Код_сотрудника]) VALUES (?,?,?,?,?)", row)
                conn.commit()
            except Exception as e:
                conn.rollback()
                print(f"Логин {row[0]} не добавлен:", e)
        _cache.clear()
        return True
    finally:
        conn.close()

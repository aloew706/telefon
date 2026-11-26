const $app = document.getElementById('app');
const $links = document.getElementById('links');
const $toast = document.getElementById('toast');
let me = { role: null };
let schema = null;

const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

async function api(path, opts = {}) {
  const r = await fetch(path, {
    method: opts.method || 'GET',
    headers: opts.body ? { 'Content-Type': 'application/json' } : undefined,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  let data = {};
  try { data = await r.json(); } catch (e) {}
  if (!r.ok) throw new Error(data.error || 'Ошибка запроса');
  return data;
}

function toast(msg, isErr = false) {
  $toast.textContent = msg;
  $toast.className = 'toast show' + (isErr ? ' error' : '');
  clearTimeout(toast.t);
  toast.t = setTimeout(() => ($toast.className = 'toast'), 3200);
}

const COLORS = {
  'черный': ['#3a3a3c', '#111'], 'белый': ['#fafafa', '#d8d8dc'], 'синий': ['#5b8def', '#1f4fb5'],
  'серый': ['#a1a1a6', '#636366'], 'зеленый': ['#7bd88f', '#2f8f4e'], 'зелёный': ['#7bd88f', '#2f8f4e'],
  'фиолетовый': ['#b18cf0', '#6b3fc4'], 'красный': ['#ff6b6b', '#b3202a'], 'золотой': ['#f1d9a8', '#c29a4d'],
  'розовый': ['#f9a8c9', '#d6568a'], 'голубой': ['#8fd3f4', '#3b9ed6'],
};
const phoneGradient = c => {
  const k = (c || '').trim().toLowerCase();
  const [a, b] = COLORS[k] || ['#c7c7cc', '#8e8e93'];
  return `linear-gradient(160deg, ${a}, ${b})`;
};

// ---------- навигация ----------
function renderNav() {
  const route = location.hash || '#/';
  const a = (h, t) => `<a href="${h}" class="${route === h ? 'active' : ''}">${t}</a>`;
  let h = a('#/', 'Каталог');
  if (me.role === 'user') h += a('#/orders', 'Мои заказы');
  if (me.role === 'admin') h += a('#/admin', 'Управление');
  if (me.role) h += `<span class="who">${esc(me.name)}</span><button id="out">Выйти</button>`;
  else h += a('#/login', 'Войти');
  $links.innerHTML = h;
  const out = document.getElementById('out');
  if (out) out.onclick = async () => { await api('/api/logout', { method: 'POST' }); me = { role: null }; schema = null; location.hash = '#/'; route_(); };
}

// ---------- каталог ----------
async function viewCatalog() {
  $app.innerHTML = `<section class="hero"><h1>Телефоны.</h1><p>Выберите свой.</p></section><div class="empty">Загрузка…</div>`;
  let items;
  try { items = await api('/api/catalog'); } catch (e) { $app.innerHTML = `<div class="empty">${esc(e.message)}</div>`; return; }
  const brands = [...new Set(items.map(i => i.brand).filter(Boolean))].sort();
  let q = '', brand = '';
  $app.innerHTML = `
    <section class="hero"><h1>Телефоны.</h1><p>Выберите свой.</p></section>
    <div class="search"><input id="q" placeholder="Поиск по модели" autocomplete="off"></div>
    <div class="chips" id="chips"></div>
    <div class="grid" id="grid"></div>`;
  const draw = () => {
    document.getElementById('chips').innerHTML =
      `<button class="chip ${brand === '' ? 'on' : ''}" data-b="">Все</button>` +
      brands.map(b => `<button class="chip ${brand === b ? 'on' : ''}" data-b="${esc(b)}">${esc(b)}</button>`).join('');
    document.querySelectorAll('.chip').forEach(c => c.onclick = () => { brand = c.dataset.b; draw(); });
    const list = items.filter(i => (!brand || i.brand === brand) && (!q || (i.model || '').toLowerCase().includes(q)));
    document.getElementById('grid').innerHTML = list.length ? list.map(i => `
      <article class="card">
        <div class="pic"><div class="phone" style="background:${phoneGradient(i.color)}"></div></div>
        <div class="brand">${esc(i.brand)}</div>
        <div class="model">${esc(i.model)}</div>
        <div class="specs">${[i.storage ? i.storage + ' ГБ' : '', i.ram ? i.ram + ' ГБ ОЗУ' : '', i.color].filter(Boolean).map(esc).join(' · ')}</div>
        ${i.description ? `<div class="desc">${esc(i.description)}</div>` : ''}
      </article>`).join('') : `<div class="empty" style="grid-column:1/-1">Ничего не найдено</div>`;
  };
  document.getElementById('q').oninput = e => { q = e.target.value.trim().toLowerCase(); draw(); };
  draw();
}

// ---------- вход ----------
function viewLogin() {
  $app.innerHTML = `
    <div class="panel">
      <h2>Вход</h2>
      <p class="sub">Войдите, чтобы увидеть свои заказы.</p>
      <form id="f">
        <input id="lg" placeholder="Логин или email" autocomplete="username" required>
        <input id="pw" type="password" placeholder="Пароль или номер телефона" autocomplete="current-password" required>
        <button class="btn" type="submit">Войти</button>
        <div class="err" id="err"></div>
      </form>
      <p class="hint">Покупатель входит по email из базы<br>и номеру телефона вместо пароля.</p>
    </div>`;
  document.getElementById('f').onsubmit = async e => {
    e.preventDefault();
    try {
      me = await api('/api/login', { method: 'POST', body: { login: lg.value, password: pw.value } });
      location.hash = me.role === 'admin' ? '#/admin' : '#/orders';
    } catch (err) { document.getElementById('err').textContent = err.message; }
  };
}

// ---------- заказы покупателя ----------
async function viewOrders() {
  if (me.role !== 'user') { location.hash = '#/login'; return; }
  $app.innerHTML = `<div class="page-head"><h1 class="page-title">Мои заказы</h1></div><div class="empty">Загрузка…</div>`;
  let list;
  try { list = await api('/api/my-orders'); } catch (e) { toast(e.message, true); return; }
  const cls = s => { s = (s || '').toLowerCase(); return s.includes('достав') && !s.includes('не') ? 'ok' : s.includes('отмен') ? 'bad' : s ? 'warn' : ''; };
  const money = v => v == null ? '' : Number(v).toLocaleString('ru-RU') + ' ₽';
  $app.innerHTML = `<div class="page-head"><h1 class="page-title">Мои заказы</h1></div>` +
    (list.length ? `<div class="orders">${list.map(o => `
      <div class="order">
        <div><h3>${esc(o.model || 'Телефон')}</h3>
          <div class="meta">Заказ №${o.id} · ${esc(o.date || '')} · ${o.qty} шт.${o.pay ? ' · ' + esc(o.pay) : ''}</div></div>
        <div class="right"><div style="font-size:20px;font-weight:600">${money(o.sum)}</div>
          ${o.status || o.delivery ? `<span class="badge ${cls(o.status)}">${esc([o.delivery, o.status].filter(Boolean).join(' · '))}</span>` : ''}</div>
      </div>`).join('')}</div>` : `<div class="empty">Заказов пока нет</div>`);
}

// ---------- управление ----------
let curTable = null;
const optCache = {};

async function viewAdmin() {
  if (me.role !== 'admin') { location.hash = '#/login'; return; }
  if (!schema) schema = await api('/api/schema');
  curTable = curTable || Object.keys(schema)[0];
  const t = schema[curTable];
  $app.innerHTML = `
    <div class="page-head"><h1 class="page-title">Управление</h1><button class="btn" id="add">+ Добавить</button></div>
    <div class="seg" id="seg">${Object.entries(schema).map(([k, v]) => `<button data-t="${k}" class="${k === curTable ? 'on' : ''}">${esc(v.title)}</button>`).join('')}</div>
    <div class="table-wrap" id="tw"><div class="empty">Загрузка…</div></div>`;
  document.querySelectorAll('#seg button').forEach(b => b.onclick = () => { curTable = b.dataset.t; viewAdmin(); });
  document.getElementById('add').onclick = () => openForm(curTable);
  try {
    const rows = await api('/api/table/' + curTable);
    const fkMaps = {};
    for (const f of t.fields) if (f.fk) fkMaps[f.name] = Object.fromEntries((await getOptions(f.fk, true)).map(o => [o.id, o.label]));
    const cols = [t.pk, ...t.fields.map(f => f.name)];
    document.getElementById('tw').innerHTML = rows.length ? `<table><thead><tr>${cols.map(c => `<th>${esc(c.replace(/_/g, ' '))}</th>`).join('')}</tr></thead><tbody>${
      rows.map(r => `<tr>${cols.map(c => `<td>${esc(fkMaps[c] ? (fkMaps[c][r[c]] ?? r[c]) : (r[c] ?? ''))}</td>`).join('')}</tr>`).join('')}</tbody></table>`
      : `<div class="empty">В таблице пока нет записей</div>`;
  } catch (e) { toast(e.message, true); }
}

async function getOptions(table, fresh) {
  if (fresh || !optCache[table]) optCache[table] = await api('/api/options/' + table);
  return optCache[table];
}

async function openForm(table) {
  const t = schema[table];
  const selects = {};
  for (const f of t.fields) if (f.fk) selects[f.name] = await getOptions(f.fk, true);
  const today = new Date().toISOString().slice(0, 10);
  const field = f => {
    const id = 'f_' + f.name;
    let input;
    if (f.fk) input = `<select id="${id}" ${f.req ? 'required' : ''}><option value="">Выберите…</option>${selects[f.name].map(o => `<option value="${o.id}">${esc(o.label)}</option>`).join('')}</select>`;
    else if (f.kind === 'int') input = `<input id="${id}" type="number" step="1" ${f.req ? 'required' : ''}>`;
    else if (f.kind === 'money') input = `<input id="${id}" type="number" step="0.01" min="0" ${f.req ? 'required' : ''}>`;
    else if (f.kind === 'date') input = `<input id="${id}" type="date" ${f.name === 'Дата_заказа' ? `value="${today}"` : ''} ${f.req ? 'required' : ''}>`;
    else input = `<input id="${id}" type="text" ${f.req ? 'required' : ''}>`;
    return `<label>${esc(f.label)}${f.req ? '' : ' (необязательно)'}${input}</label>`;
  };
  const ov = document.createElement('div');
  ov.className = 'overlay';
  ov.innerHTML = `<div class="modal"><h3>Добавить: ${esc(t.title)}</h3><form id="af">${t.fields.map(field).join('')}
    <div class="row"><button type="button" class="btn ghost small" id="cx">Отмена</button><button class="btn small" type="submit">Сохранить</button></div></form></div>`;
  document.body.appendChild(ov);
  const close = () => ov.remove();
  ov.onclick = e => { if (e.target === ov) close(); };
  ov.querySelector('#cx').onclick = close;
  ov.querySelector('#af').onsubmit = async e => {
    e.preventDefault();
    const body = {};
    t.fields.forEach(f => { body[f.name] = ov.querySelector('#f_' + CSS.escape(f.name)).value; });
    try {
      const r = await api('/api/table/' + table, { method: 'POST', body });
      close();
      toast(`Добавлено в Access (код ${r.id ?? '—'})`);
      viewAdmin();
    } catch (err) { toast(err.message, true); }
  };
}

// ---------- роутер ----------
async function route_() {
  renderNav();
  const r = location.hash || '#/';
  if (r === '#/login') return viewLogin();
  if (r === '#/orders') return viewOrders();
  if (r === '#/admin') return viewAdmin();
  return viewCatalog();
}
window.addEventListener('hashchange', route_);
(async () => {
  try { me = await api('/api/me'); } catch (e) {}
  route_();
})();

// Монтажёр — iPhone-friendly web app for the video agent. No build step, no dependencies.
'use strict';

const $ = (s, el = document) => el.querySelector(s);
const app = $('#app');
const CHUNK = 8 * 1024 * 1024; // Safari on iPhone drops long requests — small resumable chunks
const UP = {}; // pid → [{name, size, sent, note, done}]
const SEL = {}; // pid → {template, variants, brief} chosen on the collect screen, kept across re-renders
let pollTimer = null;
let meta = {templates: [], max_variants: 30};

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const mb = (b) => (b / 1048576).toFixed(b > 104857600 ? 0 : 1) + ' МБ';

function toast(msg, ms = 2600) {
  const t = $('#toast');
  t.textContent = msg;
  t.hidden = false;
  clearTimeout(toast.t);
  toast.t = setTimeout(() => (t.hidden = true), ms);
}

async function api(path, {method = 'GET', body} = {}) {
  const res = await fetch(path, {
    method,
    credentials: 'same-origin',
    headers: body ? {'Content-Type': 'application/json'} : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  if (res.status === 401) {
    location.hash = '#/login';
    throw new Error('Нужно войти');
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || data.error || `Ошибка ${res.status}`);
  return data;
}

function header(title, back) {
  $('#title').textContent = title;
  $('#back').hidden = !back;
  $('#back').onclick = () => (location.hash = back || '#/');
}

const STAGE = {
  collect: ['Загрузка видео', ''],
  analysing: ['Разбираю видео', 'work'],
  planning: ['Монтирую', 'work'],
  review: ['План готов', 'ok'],
  rendering: ['Рендер', 'work'],
  done: ['Готово', 'ok'],
  error: ['Ошибка', 'bad'],
};
const BUSY = ['analysing', 'planning', 'rendering'];
const uploading = () => Object.values(UP).some((l) => l.some((f) => !f.done));

window.addEventListener('beforeunload', (e) => {
  if (uploading()) {
    e.preventDefault();
    e.returnValue = '';
  }
});

// ---------------------------------------------------------------- router

async function route() {
  clearTimeout(pollTimer);
  const h = location.hash || '#/';
  try {
    if (h === '#/login') return viewLogin();
    const me = await api('/api/me');
    if (!me.authed) return viewLogin(me.configured);
    $('#logout').hidden = false;
    if (!meta.templates.length) meta = await api('/api/templates');
    const m = h.match(/^#\/p\/([\w-]+)/);
    if (m) return viewProject(m[1]);
    return viewList();
  } catch (e) {
    app.innerHTML = `<div class="card error">${esc(e.message)}</div><button class="btn secondary" onclick="route()">Обновить</button>`;
  }
}
window.addEventListener('hashchange', route);
$('#logout').onclick = async () => {
  await api('/api/logout', {method: 'POST'}).catch(() => {});
  location.hash = '#/login';
};

// ---------------------------------------------------------------- login

function viewLogin(configured = true) {
  header('Монтажёр');
  $('#logout').hidden = true;
  app.innerHTML = `
    <div class="card stack">
      <h2>Вход</h2>
      <p class="muted">Введите код доступа — его задают на сервере в файле .env (WEB_PASSWORD).</p>
      ${configured ? '' : '<p class="error">На сервере не задан WEB_PASSWORD — вход закрыт.</p>'}
      <form id="f" class="stack">
        <input type="password" id="code" autocomplete="current-password" placeholder="Код доступа" required>
        <button class="btn" type="submit">Войти</button>
      </form>
    </div>`;
  $('#f').onsubmit = async (e) => {
    e.preventDefault();
    const btn = $('button', e.target);
    btn.disabled = true;
    try {
      await api('/api/login', {method: 'POST', body: {code: $('#code').value}});
      location.hash = '#/';
      route();
    } catch (err) {
      toast(err.message);
      btn.disabled = false;
    }
  };
}

// ---------------------------------------------------------------- list

async function viewList() {
  header('Монтажёр');
  const {projects} = await api('/api/projects');
  const items = projects
    .map((p) => {
      const [label, cls] = STAGE[p.stage] || [p.stage, ''];
      const when = new Date(p.created * 1000).toLocaleString('ru-RU', {day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit'});
      const extra = p.stage === 'done' ? ` · ${p.results_count} роликов` : p.owner !== 'web' ? ' · из Telegram' : '';
      return `<a class="card proj" href="#/p/${p.id}">
        <div class="grow"><div class="name">${esc(p.title)}</div><div class="meta">${when}${extra}</div></div>
        <span class="pill ${cls}">${label}</span><span class="chev">›</span></a>`;
    })
    .join('');
  app.innerHTML = `
    <button class="btn" id="new">＋ Новый ролик</button>
    <div style="height:14px"></div>
    ${items || '<div class="empty">Пока нет проектов.<br>Нажмите «Новый ролик» и загрузите видео.</div>'}`;
  $('#new').onclick = async () => {
    const p = await api('/api/projects', {method: 'POST', body: {}});
    location.hash = `#/p/${p.id}`;
  };
  if (projects.some((p) => BUSY.includes(p.stage))) pollTimer = setTimeout(route, 5000);
}

// ---------------------------------------------------------------- project

async function viewProject(pid) {
  const p = await api(`/api/projects/${pid}`);
  header(p.title, '#/');
  if (BUSY.includes(p.stage)) return viewBusy(p);
  ({collect: viewCollect, review: viewReview, done: viewDone, error: viewError})[p.stage]?.(p);
  if ((UP[p.id] || []).some((f) => !f.done)) return;
  const del = document.createElement('button');
  del.className = 'link-btn';
  del.style.cssText = 'display:block;margin:18px auto 8px;color:var(--bad)';
  del.textContent = 'Удалить проект';
  del.onclick = async () => {
    if (!confirm('Удалить проект вместе с видео и готовыми роликами?')) return;
    try {
      await api(`/api/projects/${p.id}`, {method: 'DELETE'});
      location.hash = '#/';
    } catch (err) {
      toast(err.message);
    }
  };
  app.appendChild(del);
}

function viewCollect(p) {
  const sel = (SEL[p.id] ||= {template: p.template, variants: p.variants, brief: p.brief || ''});
  const ups = (UP[p.id] || []).filter((f) => !f.done);
  const files = p.inputs
    .map((n, i) => `<div class="file"><div class="row"><span class="fname">✅ ${esc(n)}</span><button class="x" data-del="${i}" aria-label="Убрать">✕</button></div></div>`)
    .join('');
  const pending = ups
    .map((f, i) => `<div class="file" id="up-${i}"><div class="row"><span class="fname">${esc(f.name)}</span><span class="muted" data-pct>${Math.floor((100 * f.sent) / f.size)}%</span></div>
      <div class="progress"><i style="width:${(100 * f.sent) / f.size}%"></i></div><div class="muted" data-note>${esc(f.note || mb(f.size))}</div></div>`)
    .join('');
  const tpls = meta.templates
    .map((t) => `<label class="tpl ${t.name === sel.template ? 'on' : ''}"><input type="radio" name="tpl" value="${t.name}" ${t.name === sel.template ? 'checked' : ''}><b>${esc(t.name)}</b><span>${esc(t.description)}</span></label>`)
    .join('');
  app.innerHTML = `
    <div class="card">
      <h2>1. Видео</h2>
      <label class="drop"><input type="file" id="pick" accept="video/*" multiple>
        <strong>＋ Выбрать видео</strong><span class="muted">Из «Фото» или «Файлов». Любой размер — загрузка продолжится, если пропадёт связь.</span></label>
      <div id="files">${files}${pending}</div>
      <details style="margin-top:12px"><summary class="muted">или ссылка на Google Drive</summary>
        <div class="row" style="margin-top:8px"><input type="url" id="link" placeholder="https://drive.google.com/…"><button class="btn small secondary" id="addlink">Добавить</button></div>
      </details>
    </div>
    <div class="card"><h2>2. Шаблон</h2>${tpls}</div>
    <div class="card stack">
      <h2>3. Задание <span class="muted" style="font-weight:400">— необязательно</span></h2>
      <p class="muted" style="margin:0">Как смонтировать — своими словами. Задание важнее шаблона, но смысл сказанного не меняется.</p>
      <textarea id="brief" placeholder="Например: «до 30 секунд, начни с цены, убери всё про доставку, жёлтые субтитры, в конце — вывод про качество»">${esc(sel.brief)}</textarea>
    </div>
    <div class="card">
      <h2>4. Сколько вариантов</h2>
      <div class="stepper"><button id="minus" aria-label="Меньше">−</button><output id="n">${p.variants}</output><button id="plus" aria-label="Больше">＋</button></div>
      <div class="chips">${[1, 3, 5, 10, 20].map((n) => `<button data-n="${n}">${n}</button>`).join('')}</div>
      <p class="muted" id="nhint"></p>
    </div>
    <button class="btn" id="go">▶ Монтировать</button>
    <p class="muted center" id="gohint"></p>`;

  let n = sel.variants;
  const setN = (v) => {
    n = sel.variants = Math.max(1, Math.min(meta.max_variants, v));
    $('#n').textContent = n;
    $('#nhint').textContent = `Основной монтаж + ${n} вар. Рендер ~3–5 мин на каждый ролик${n > 10 ? ' — это надолго' : ''}.`;
  };
  setN(n);
  $('#minus').onclick = () => setN(n - 1);
  $('#plus').onclick = () => setN(n + 1);
  app.querySelectorAll('[data-n]').forEach((b) => (b.onclick = () => setN(+b.dataset.n)));
  app.querySelectorAll('.tpl input').forEach((r) => (r.onchange = () => {
    sel.template = r.value;
    app.querySelectorAll('.tpl').forEach((l) => l.classList.toggle('on', $('input', l).checked));
  }));
  $('#brief').oninput = (e) => (sel.brief = e.target.value);
  app.querySelectorAll('[data-del]').forEach((b) => (b.onclick = async () => {
    await api(`/api/projects/${p.id}/inputs/${b.dataset.del}/delete`, {method: 'POST'});
    route();
  }));
  $('#pick').onchange = (e) => {
    const list = [...e.target.files];
    e.target.value = '';
    if (list.length) startUploads(p.id, list);
  };
  $('#addlink').onclick = async () => {
    try {
      await api(`/api/projects/${p.id}/links`, {method: 'POST', body: {url: $('#link').value.trim()}});
      route();
    } catch (err) {
      toast(err.message);
    }
  };
  const ready = p.inputs.length > 0 && !ups.length;
  $('#go').disabled = !ready;
  $('#gohint').textContent = ups.length ? 'Дождитесь окончания загрузки' : p.inputs.length ? '' : 'Сначала добавьте видео';
  $('#go').onclick = async () => {
    $('#go').disabled = true;
    try {
      if (sel.template === 'free' && !sel.brief.trim()) {
        toast('Для «free» напишите задание');
        $('#go').disabled = false;
        return;
      }
      await api(`/api/projects/${p.id}/start`, {method: 'POST', body: {template: sel.template, variants: n, brief: sel.brief}});
      route();
    } catch (err) {
      toast(err.message);
      $('#go').disabled = false;
    }
  };
}

async function startUploads(pid, files) {
  const list = (UP[pid] = (UP[pid] || []).filter((f) => !f.done));
  const items = files.map((f) => ({file: f, name: f.name, size: f.size, sent: 0, note: 'в очереди', done: false}));
  list.push(...items);
  route();
  if (startUploads.running?.[pid]) return;
  (startUploads.running ||= {})[pid] = true;
  try {
    for (const it of list) if (!it.done) await uploadOne(pid, it);
  } finally {
    startUploads.running[pid] = false;
  }
  if (location.hash === `#/p/${pid}`) route();
  toast('Видео загружено');
}

function paint(pid, it) {
  if (location.hash !== `#/p/${pid}`) return;
  const idx = UP[pid].filter((f) => !f.done).indexOf(it);
  const el = document.getElementById(`up-${idx}`);
  if (!el) return;
  const pct = Math.floor((100 * it.sent) / it.size);
  $('[data-pct]', el).textContent = pct + '%';
  $('i', el).style.width = pct + '%';
  $('[data-note]', el).textContent = it.note;
}

async function uploadOne(pid, it) {
  let fails = 0;
  it.note = 'загружаю…';
  paint(pid, it);
  for (;;) {
    try {
      if (!it.uid) it.uid = (await api(`/api/projects/${pid}/uploads`, {method: 'POST', body: {name: it.name, size: it.size}})).uid;
      const url = `/api/projects/${pid}/uploads/${it.uid}`;
      while (it.sent < it.size) {
        const t0 = performance.now();
        const res = await fetch(`${url}?offset=${it.sent}`, {method: 'PUT', body: it.file.slice(it.sent, it.sent + CHUNK), credentials: 'same-origin'});
        if (res.status === 401) throw new Error('Нужно войти заново');
        const j = await res.json().catch(() => ({}));
        if (res.status === 409) {
          it.sent = j.received;
          continue;
        }
        if (!res.ok) throw new Error(j.detail || `Ошибка ${res.status}`);
        const speed = (j.received - it.sent) / ((performance.now() - t0) / 1000);
        it.sent = j.received;
        const left = (it.size - it.sent) / Math.max(speed, 1);
        it.note = `${mb(it.sent)} из ${mb(it.size)} · ${left > 90 ? Math.round(left / 60) + ' мин' : Math.round(left) + ' с'}`;
        fails = 0;
        paint(pid, it);
        if (j.done) break;
      }
      it.done = true;
      return;
    } catch (err) {
      if (/войти/.test(err.message)) {
        it.note = err.message;
        paint(pid, it);
        throw err;
      }
      fails++;
      it.note = `Связь прервалась — продолжу через ${Math.min(30, 2 * fails)} с…`;
      paint(pid, it);
      await sleep(Math.min(30000, 2000 * fails));
      if (it.uid) {
        try {
          it.sent = (await api(`/api/projects/${pid}/uploads/${it.uid}`)).received;
        } catch (_) {}
      }
    }
  }
}

function viewBusy(p) {
  const title = {analysing: 'Разбираю видео', planning: 'Монтирую по шаблону', rendering: 'Рендерю ролики'}[p.stage];
  const sub = {
    analysing: 'Распознаю речь, лица и кадры. Обычно 5–15 минут — можно закрыть приложение, работа продолжится на сервере.',
    planning: 'Claude строит историю и варианты. Обычно 1–3 минуты.',
    rendering: `Основной монтаж + ${p.variants} вар. — примерно 3–5 минут на каждый ролик. Можно закрыть приложение.`,
  }[p.stage];
  const log = [...p.status].reverse().map((l) => `<li>${esc(l)}</li>`).join('');
  app.innerHTML = `
    <div class="card">
      <div class="row"><div class="spinner" aria-hidden="true"></div><div><h2 style="margin:0">${title}…</h2><div class="muted">${sub}</div></div></div>
      <ul class="log">${log}</ul>
    </div>`;
  pollTimer = setTimeout(route, 3000);
}

function planCards(md) {
  return md
    .split(/^## /m)
    .filter((s) => s.trim())
    .map((s) => {
      const [head, ...rest] = s.split('\n');
      return `<div class="card"><h3>${esc(head)}</h3><div class="plan">${esc(rest.join('\n').trim())}</div></div>`;
    })
    .join('');
}

function viewReview(p) {
  const checks = p.checks.length
    ? `<div class="card"><h2>Проверка смысла</h2>${p.checks
        .map((c) => `<div class="check">${c.ok ? '✅' : '⚠️'} <b>${esc(c.plan_id)}</b>${c.problems.map((x) => `<br>— ${esc(x)}`).join('')}</div>`)
        .join('')}</div>`
    : '';
  app.innerHTML = `
    <div class="card"><h2>План готов</h2><p class="muted">Проверьте хук, порядок и текст. Если всё хорошо — «Рендер». Если нет — напишите правки словами.</p>
      ${p.brief ? `<div class="caption" style="margin-bottom:12px"><b>Задание:</b> ${esc(p.brief)}</div>` : ''}
      <button class="btn" id="render">🎬 Рендер (${p.variants + 1} роликов)</button></div>
    ${checks}
    ${planCards(p.plans_md)}
    <div class="card stack" id="fb"><h2>Правки</h2>
      <textarea id="fbtext" placeholder="Например: «в v1 начни с фразы про ВБ», «убери кусок про возраст», «v2 короче, до 40 секунд»"></textarea>
      <button class="btn secondary" id="send">✏️ Переделать план</button></div>`;
  $('#render').onclick = () => act(p.id, 'render');
  $('#send').onclick = () => {
    const text = $('#fbtext').value.trim();
    if (!text) return toast('Напишите, что поменять');
    act(p.id, 'feedback', {text});
  };
}

async function act(pid, what, body) {
  app.querySelectorAll('button').forEach((b) => (b.disabled = true));
  try {
    await api(`/api/projects/${pid}/${what}`, {method: 'POST', body: body || {}});
  } catch (err) {
    toast(err.message);
  }
  route();
}

function viewDone(p) {
  const vids = p.results
    .map(
      (r) => `<div class="card">
      <h2>${esc(r.id)} — ${esc(r.angle)}</h2>
      <video class="video" src="${r.preview}" controls playsinline preload="metadata"></video>
      <div class="btn-row"><button class="btn" data-share="${r.preview}" data-name="${esc(r.id)}.mp4">Сохранить</button>
        <a class="btn secondary" href="${r.master}?download=1">Оригинал · ${r.mb} МБ</a></div>
      <div style="height:10px"></div>
      <div class="caption">${esc(r.caption)}</div>
      <button class="btn secondary small" style="margin-top:8px" data-copy="${encodeURIComponent(r.caption)}">Скопировать текст поста</button>
    </div>`,
    )
    .join('');
  app.innerHTML = `
    <div class="card"><h2>Готово: ${p.results.length} роликов</h2>
      <p class="muted">«Сохранить» — откроется меню iPhone, там «Сохранить видео» (в Фото). «Оригинал» — полное качество 1080×1920.</p></div>
    ${vids || '<div class="empty">Роликов не найдено</div>'}
    <div class="card stack"><h2>Ещё правки?</h2>
      <textarea id="fbtext" placeholder="Что поменять — план переделается, потом снова рендер"></textarea>
      <button class="btn secondary" id="send">✏️ Переделать план</button></div>`;
  app.querySelectorAll('[data-copy]').forEach((b) => (b.onclick = async () => {
    try {
      await navigator.clipboard.writeText(decodeURIComponent(b.dataset.copy));
      toast('Текст скопирован');
    } catch (_) {
      toast('Не удалось скопировать — выделите текст вручную');
    }
  }));
  app.querySelectorAll('[data-share]').forEach((b) => (b.onclick = () => saveVideo(b)));
  $('#send').onclick = () => {
    const text = $('#fbtext').value.trim();
    if (!text) return toast('Напишите, что поменять');
    act(p.id, 'feedback', {text});
  };
}

async function saveVideo(btn) {
  const url = btn.dataset.share;
  btn.disabled = true;
  const label = btn.textContent;
  btn.textContent = 'Готовлю…';
  try {
    const blob = await (await fetch(url, {credentials: 'same-origin'})).blob();
    const file = new File([blob], btn.dataset.name, {type: 'video/mp4'});
    if (navigator.canShare && navigator.canShare({files: [file]})) {
      await navigator.share({files: [file]});
    } else {
      const a = Object.assign(document.createElement('a'), {href: URL.createObjectURL(blob), download: file.name});
      a.click();
    }
  } catch (err) {
    if (err.name !== 'AbortError') toast('Не получилось — нажмите «Оригинал»');
  }
  btn.textContent = label;
  btn.disabled = false;
}

function viewError(p) {
  const log = [...p.status].reverse().slice(0, 6).map((l) => `<li>${esc(l)}</li>`).join('');
  app.innerHTML = `
    <div class="card stack"><h2>Что-то пошло не так</h2>
      <div class="error">${esc(p.error)}</div>
      <button class="btn" id="retry">↻ Повторить</button>
      <ul class="log">${log}</ul></div>`;
  $('#retry').onclick = () => act(p.id, 'retry');
}

route();

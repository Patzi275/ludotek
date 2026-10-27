// Interface of the library. Every user-facing string comes from the catalog (t / tn).
const TOKEN = document.querySelector('meta[name="biblio-token"]').content;
const $ = s => document.querySelector(s);

// ---- translations: catalog injected by server.py (see ludotek/i18n.py for the format)
const I18N = JSON.parse($("#i18n").textContent);
const LANG = I18N.lang;
function t(key, params = {}) {
  const msg = I18N.messages[key] ?? I18N.fallback[key] ?? key;
  return msg.replace(/\{(\w+)\}/g, (m, k) => (k in params ? params[k] : m));
}
function tn(key, n, params = {}) {
  const one = t("plural.zero_is_one") === "yes" ? n <= 1 : n === 1;
  return t(`${key}.${one ? "one" : "other"}`, {n, ...params});
}
function applyI18n() {
  document.querySelectorAll("[data-i18n]").forEach(el => { el.textContent = t(el.dataset.i18n); });
  for (const attr of ["placeholder", "title", "aria-label"])
    document.querySelectorAll(`[data-i18n-${attr}]`).forEach(el => el.setAttribute(attr, t(el.getAttribute(`data-i18n-${attr}`))));
}
applyI18n();

let state = {items: [], removed: [], enrich: {}}, wasFilling = false, lastJson = "", filter = "all", sortBy = "name", query = "", openId = null;

// Library layouts: same values as api.VIEWS (checked by tests). The saved one comes from <html data-view>.
const VIEWS = ["grid-s", "grid-m", "grid-l", "list"];
let view = VIEWS.includes(document.documentElement.dataset.view) ? document.documentElement.dataset.view : "grid-m";

const STATUS = {"": "", todo: t("status.todo"), playing: t("status.playing"), done: t("status.done"), dropped: t("status.dropped")};
const FILTERS = [
  ["all", t("filter.all"), () => true],
  ["ready", t("filter.ready"), i => i.kind === "dossier" && i.exe],
  ["archive", t("filter.archive"), i => i.kind === "archive"],
  ["executable", t("filter.executable"), i => i.kind === "executable"],
  ["fav", t("filter.fav"), i => i.favorite],
  ["new", t("filter.new"), i => i.is_new],
  ["dup", t("filter.dup"), i => i.dup],
];
const SORTS = {
  name: (a, b) => a.name.localeCompare(b.name, LANG, {sensitivity: "base"}),
  added: (a, b) => (b.added || 0) - (a.added || 0),
  size: (a, b) => (b.size || 0) - (a.size || 0),
  played: (a, b) => (b.last_launched || 0) - (a.last_launched || 0),
};

const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const SIZE_UNITS = t("size.units").split(" ");
function fmtSize(b) {
  if (b == null) return "…";
  let i = 0;
  while (b >= 1024 && i < SIZE_UNITS.length - 1) { b /= 1024; i++; }
  const digits = i >= 3 ? 1 : 0;
  return new Intl.NumberFormat(LANG, {minimumFractionDigits: digits, maximumFractionDigits: digits}).format(b) + " " + SIZE_UNITS[i];
}
const fmtDate = ts => ts ? new Date(ts * 1000).toLocaleDateString(LANG, {day: "numeric", month: "short", year: "numeric"}) : "";
function initials(name) {
  const small = new Set(["the", "of", "a", "an", "and", "de", "du", "la", "le", "les", "-"]);
  const w = name.split(/\s+/).filter(x => /[\p{L}\p{N}]/u.test(x) && !small.has(x.toLowerCase()));
  return ((w[0] || "?")[0] + ((w[1] || "")[0] || "")).toUpperCase();
}
function kindInfo(it) {
  if (it.kind === "dossier")
    return it.exe ? {label: t("kind.ready"), cls: "ready", act: t("action.play"), action: "launch"}
                  : {label: it.computing ? t("kind.analysing") : t("kind.folder"), cls: "folder", act: t("action.open"), action: "reveal"};
  if (it.kind === "archive") return {label: t("kind.archive"), cls: "archive", act: t("action.open_archive"), action: "launch"};
  if (it.kind === "executable") return {label: t("kind.executable"), cls: "exe", act: t("action.run"), action: "launch"};
  return {label: t("kind.file"), cls: "other", act: t("action.open"), action: "launch"};
}
function toast(msg) {
  const el = $("#toast"); el.textContent = msg; el.classList.add("show");
  clearTimeout(toast.timer); toast.timer = setTimeout(() => el.classList.remove("show"), 2200);
}
async function post(url, body) {
  const r = await fetch(url, {method: "POST", headers: {"Content-Type": "application/json", "X-Biblio-Token": TOKEN},
                              body: JSON.stringify(body || {})});
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || t("error.http", {status: r.status}));
  return data;
}
async function load(force) {
  try {
    const r = await fetch("/api/library", {cache: "no-store"});
    const txt = await r.text();
    $("#banner").classList.remove("show");
    if (!force && txt === lastJson) return;
    lastJson = txt; state = JSON.parse(txt);
    render(); if (openId) fillModal(false);
  } catch (e) { $("#banner").classList.add("show"); }
}
const byId = id => state.items.find(i => i.id === id);

function render() {
  const items = state.items;
  renderFill(state.enrich || {});
  $("#path").textContent = state.root;
  const total = items.reduce((s, i) => s + (i.size || 0), 0);
  const pending = items.filter(i => i.computing).length;
  const count = f => items.filter(FILTERS.find(x => x[0] === f)[2]).length;
  const ready = count("ready"), archives = count("archive"), executables = count("executable");
  $("#stats").innerHTML = [
    [items.length, tn("stats.items", items.length)],
    [fmtSize(total) + (pending ? "+" : ""), pending ? t("stats.used_pending", {n: pending}) : t("stats.used")],
    [ready, tn("stats.ready", ready)], [archives, tn("stats.archives", archives)], [executables, tn("stats.executables", executables)],
  ].map(([b, s]) => `<div class="stat"><b>${esc(b)}</b><span>${esc(s)}</span></div>`).join("");

  $("#chips").innerHTML = FILTERS.map(([k, label, fn]) => {
    const n = items.filter(fn).length;
    if (k !== "all" && !n && filter !== k) return "";
    return `<button class="chip ${filter === k ? "on" : ""}" data-filter="${k}" aria-pressed="${filter === k}">${esc(label)}<small>${n}</small></button>`;
  }).join("");

  const fn = FILTERS.find(x => x[0] === filter)[2];
  const q = query.trim().toLowerCase();
  const list = items.filter(i => fn(i) && (!q || (i.name + " " + i.file + " " + i.description).toLowerCase().includes(q))).sort(SORTS[sortBy]);
  $("#empty").hidden = list.length > 0;
  $("#grid").innerHTML = list.map(view === "list" ? rowHtml : cardHtml).join("");

  const rm = state.removed || [];
  $("#removedBox").hidden = !rm.length;
  $("#removed").innerHTML = rm.map(r => `<li>${esc(r.name)} <small>— ${esc(t("removed.item", {file: r.file, date: fmtDate(r.removed_at)}))}</small></li>`).join("");
}

// ---- item markup: a card (grid layouts) or a row (list). Both keep class "card" and
// data-id, so clicks, favorites and cover drag and drop work the same in every layout.
const hueOf = it => parseInt(it.id.slice(0, 4), 16) % 360;
const metaOf = it => [fmtSize(it.size), it.source, fmtDate(it.added)].filter(Boolean).join(" · ");
const coverInner = (it, lazy) => it.cover ? `<img src="${esc(it.cover)}" alt=""${lazy ? ' loading="lazy"' : ""}>`
                                          : `<span class="initials">${esc(initials(it.name))}</span>`;
const starHtml = it => `<button class="star ${it.favorite ? "on" : ""}" data-act="fav" title="${esc(t("card.favorite"))}" aria-label="${esc(t("card.favorite"))}" aria-pressed="${!!it.favorite}">★</button>`;
const badgesHtml = (it, k) => `<span class="b ${k.cls}">${esc(k.label)}</span>
  ${it.is_new ? `<span class="b new">${esc(t("card.new"))}</span>` : ""}
  ${it.dup ? `<span class="b dup" title="${esc(t("card.dup_title"))}">${esc(t("card.dup"))}</span>` : ""}`;
const statusHtml = it => it.status ? `<div class="status">${esc(STATUS[it.status] || "")}</div>` : "";
const actionsHtml = k => `<button class="btn ${k.cls === "ready" || k.cls === "exe" ? "primary" : ""}" data-act="${k.action}"><span>${esc(k.act)}</span></button>
  <button class="btn more" data-act="details" title="${esc(t("card.details"))}" aria-label="${esc(t("card.details"))}">⋯</button>`;

function cardHtml(it) {
  const k = kindInfo(it);
  return `<div class="card" data-id="${it.id}">
    <div class="cover ${it.cover ? "has-img" : ""}" style="--h:${hueOf(it)}">
      ${coverInner(it, true)}
      ${starHtml(it)}
      <div class="badges">${badgesHtml(it, k)}</div>
    </div>
    <div class="body">
      <div class="title" title="${esc(it.file)}">${esc(it.name)}</div>
      <div class="meta">${esc(metaOf(it))}</div>
      ${it.description ? `<div class="desc">${esc(it.description)}</div>` : ""}
      ${statusHtml(it)}
      <div class="actions">${actionsHtml(k)}</div>
    </div>
  </div>`;
}

function rowHtml(it) {
  const k = kindInfo(it);
  return `<div class="card row" data-id="${it.id}">
    <div class="thumb cover ${it.cover ? "has-img" : ""}" style="--h:${hueOf(it)}">${coverInner(it, true)}</div>
    <div class="row-main">
      <div class="title" title="${esc(it.file)}">${esc(it.name)}</div>
      <div class="meta">${esc(metaOf(it))}</div>
      <div class="row-badges">${badgesHtml(it, k)}</div>
    </div>
    ${statusHtml(it)}
    <div class="actions">${starHtml(it)}${actionsHtml(k)}</div>
  </div>`;
}

// ---- Steam fill: header button shows progress, a toast sums up when the job ends.
function renderFill(job) {
  const btn = $("#enrich");
  btn.textContent = job.running ? t("header.enrich_stop", {done: job.done, total: job.total}) : t("header.enrich");
  btn.classList.toggle("running", !!job.running);
  if (wasFilling && !job.running) toast(t("enrich.done", job));
  wasFilling = !!job.running;
}

function applyView() {
  $("#grid").className = view === "list" ? "grid list" : `grid size-${view.slice(-1)}`;
  document.querySelectorAll("#views [data-view]").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.view === view)));
}

async function act(id, action) {
  const it = byId(id); if (!it) return;
  try {
    if (action === "fav") { await post("/api/update/" + id, {favorite: !it.favorite}); }
    else if (action === "details") { openModal(id); return; }
    else { await post(`/api/${action}/` + id); toast(action === "launch" ? t("toast.launching", {name: it.name}) : t("toast.revealing")); }
    load(true);
  } catch (e) { toast(e.message); }
}

function openModal(id) { openId = id; $("#mCandidates").hidden = true; fillModal(true); $("#modalBg").classList.add("open"); }
function closeModal() { openId = null; $("#modalBg").classList.remove("open"); }
function fillModal(full) {
  const it = byId(openId); if (!it) return closeModal();
  const k = kindInfo(it);
  $("#mTitle").textContent = it.name;
  $("#mFile").textContent = it.file + (it.size != null ? " · " + fmtSize(it.size) : "");
  const mc = $("#mCover");
  mc.style.setProperty("--h", parseInt(it.id.slice(0, 4), 16) % 360);
  mc.classList.toggle("has-img", !!it.cover);
  mc.innerHTML = it.cover ? `<img src="${esc(it.cover)}" alt="">` : `<span class="initials">${esc(initials(it.name))}</span>`;
  $("#mUncover").hidden = !it.cover;
  if (full || document.activeElement !== $("#mDesc")) $("#mDesc").value = it.description || "";
  $("#mStatus").value = it.status || "";
  $("#mExeField").hidden = !it.exes.length;
  $("#mExe").innerHTML = it.exes.map(e => `<option ${e === it.exe ? "selected" : ""}>${esc(e)}</option>`).join("");
  if (full || document.activeElement !== $("#mNotes")) $("#mNotes").value = it.notes || "";
  $("#mLaunch").textContent = k.act;
  $("#mLaunch").dataset.action = k.action;
}

$("#grid").addEventListener("click", e => {
  const b = e.target.closest("[data-act]"); if (!b) return;
  act(b.closest(".card").dataset.id, b.dataset.act);
});
$("#chips").addEventListener("click", e => {
  const c = e.target.closest("[data-filter]"); if (!c) return;
  filter = c.dataset.filter; render();
});
$("#search").addEventListener("input", e => { query = e.target.value; render(); });
$("#sort").addEventListener("change", e => { sortBy = e.target.value; render(); });
$("#enrich").addEventListener("click", async () => {
  try {
    if (state.enrich && state.enrich.running) { await post("/api/enrich", {stop: true}); return load(true); }
    const n = state.items.filter(i => i.needs_info).length;
    if (!n) return toast(t("enrich.nothing"));
    if (!confirm(t("enrich.confirm", {n}))) return;
    await post("/api/enrich"); load(true);
  } catch (e) { toast(e.message); }
});
$("#views").addEventListener("click", e => {
  const b = e.target.closest("[data-view]"); if (!b || b.dataset.view === view) return;
  view = b.dataset.view; applyView(); render();
  post("/api/settings", {view}).then(d => { if (d.warning) toast(d.warning); }).catch(err => toast(err.message));
});
$("#rescan").addEventListener("click", async () => { await post("/api/rescan"); await load(true); toast(t("toast.rescanned")); });
$("#quit").addEventListener("click", async () => {
  if (!confirm(t("quit.confirm"))) return;
  await post("/api/quit").catch(() => {});
  document.body.innerHTML = `<p style="padding:40px;text-align:center;color:var(--dp-color-ink-secondary)">${esc(t("quit.stopped"))}</p>`;
});
$("#mStatus").addEventListener("change", e => post("/api/update/" + openId, {status: e.target.value}).then(() => load(true)));
$("#mExe").addEventListener("change", e => post("/api/update/" + openId, {exe: e.target.value}).then(() => load(true)));
let notesTimer;
$("#mNotes").addEventListener("input", e => {
  clearTimeout(notesTimer); const id = openId, v = e.target.value;
  notesTimer = setTimeout(() => post("/api/update/" + id, {notes: v}).then(() => load(true)), 500);
});
let descTimer;
$("#mDesc").addEventListener("input", e => {
  clearTimeout(descTimer); const id = openId, v = e.target.value;
  descTimer = setTimeout(() => post("/api/update/" + id, {description: v}).then(() => load(true)), 500);
});

// ---- covers: file, URL, drag and drop, paste
async function uploadCover(id, blob) {
  if (!blob || !/^image\//.test(blob.type)) return toast(t("toast.not_image"));
  if (blob.size > 15 * 1024 * 1024) return toast(t("error.image_too_big"));
  try {
    const r = await fetch("/api/cover/" + id, {method: "POST", body: blob,
      headers: {"Content-Type": blob.type, "X-Biblio-Token": TOKEN}});
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.error || t("error.http", {status: r.status}));
    toast(t("toast.image_added")); load(true);
  } catch (e) { toast(e.message); }
}
async function coverFromUrl(id, url) {
  toast(t("toast.image_downloading"));
  try { await post("/api/cover/" + id, {url}); toast(t("toast.image_added")); load(true); }
  catch (e) { toast(e.message); }
}
function handleDrop(id, dt) {
  const file = [...(dt.files || [])].find(f => /^image\//.test(f.type));
  if (file) return uploadCover(id, file);
  const url = (dt.getData("text/uri-list") || dt.getData("text/plain") || "").split("\n")[0].trim();
  if (/^https?:\/\//i.test(url)) return coverFromUrl(id, url);
  toast(t("toast.drop_hint"));
}
const hasDrag = e => [...e.dataTransfer.types].some(type => type === "Files" || type === "text/uri-list");

$("#grid").addEventListener("dragover", e => {
  const card = e.target.closest(".card"); if (!card || !hasDrag(e)) return;
  e.preventDefault(); card.classList.add("drop");
});
$("#grid").addEventListener("dragleave", e => {
  const card = e.target.closest(".card"); if (card && !card.contains(e.relatedTarget)) card.classList.remove("drop");
});
$("#grid").addEventListener("drop", e => {
  const card = e.target.closest(".card"); if (!card) return;
  e.preventDefault(); card.classList.remove("drop"); handleDrop(card.dataset.id, e.dataTransfer);
});
const mc = $("#mCover");
mc.addEventListener("dragover", e => { if (hasDrag(e)) { e.preventDefault(); mc.classList.add("drop"); } });
mc.addEventListener("dragleave", () => mc.classList.remove("drop"));
mc.addEventListener("drop", e => { e.preventDefault(); mc.classList.remove("drop"); handleDrop(openId, e.dataTransfer); });
document.addEventListener("paste", e => {
  if (!openId) return;
  const item = [...e.clipboardData.items].find(i => i.type.startsWith("image/"));
  if (item) { e.preventDefault(); uploadCover(openId, item.getAsFile()); return; }
  const text = e.clipboardData.getData("text").trim();
  const inField = ["TEXTAREA", "INPUT"].includes(document.activeElement.tagName);
  if (!inField && /^https?:\/\/\S+$/i.test(text)) { e.preventDefault(); coverFromUrl(openId, text); }
});
$("#mPick").addEventListener("click", () => $("#mFileInput").click());
$("#mFileInput").addEventListener("change", e => { const f = e.target.files[0]; e.target.value = ""; if (f) uploadCover(openId, f); });
$("#mUrl").addEventListener("click", () => {
  const url = prompt(t("details.cover_url_prompt"));
  if (url && url.trim()) coverFromUrl(openId, url.trim());
});
// Per-game Steam search: the user picks the right store page among the top results.
$("#mSteam").addEventListener("click", async () => {
  const id = openId, box = $("#mCandidates");
  box.hidden = false; box.innerHTML = `<p class="hint">${esc(t("details.steam_searching"))}</p>`;
  try {
    const {candidates} = await post("/api/steam_search/" + id);
    if (openId !== id) return;
    if (!candidates.length) { box.hidden = true; return toast(t("details.steam_none")); }
    box.innerHTML = `<p class="hint">${esc(t("details.steam_pick"))}</p><div class="cand-list">` + candidates.map(c =>
      `<button class="cand" data-appid="${c.appid}" title="${esc(c.name)}"><img src="${esc(c.image)}" data-fallback="${esc(c.fallback || "")}" alt=""><span>${esc(c.name)}</span></button>`
    ).join("") + "</div>";
    // Old games have no portrait cover: show Steam's small capsule instead, or nothing.
    box.querySelectorAll("img").forEach(img => img.addEventListener("error", () => {
      if (img.dataset.fallback && img.src !== img.dataset.fallback) img.src = img.dataset.fallback; else img.remove();
    }));
  } catch (e) { box.hidden = true; toast(e.message); }
});
$("#mCandidates").addEventListener("click", async e => {
  const b = e.target.closest("[data-appid]"); if (!b) return;
  try {
    await post("/api/steam_apply/" + openId, {appid: Number(b.dataset.appid)});
    $("#mCandidates").hidden = true; toast(t("toast.steam_applied")); await load(true); fillModal(true);
  } catch (err) { toast(err.message); }
});
$("#mUncover").addEventListener("click", () => post("/api/uncover/" + openId).then(() => { toast(t("toast.image_removed")); load(true); }));

$("#mLaunch").addEventListener("click", e => act(openId, e.target.dataset.action));
$("#mReveal").addEventListener("click", () => act(openId, "reveal"));
$("#mClose").addEventListener("click", closeModal);
$("#modalBg").addEventListener("click", e => { if (e.target.id === "modalBg") closeModal(); });
document.addEventListener("keydown", e => { if (e.key === "Escape") { closeModal(); closeSettings(); } });

// ---- settings: watched folder and language
$("#setLang").innerHTML = I18N.languages.map(l => `<option value="${esc(l.code)}">${esc(l.name)}</option>`).join("");
function openSettings() {
  $("#setRoot").value = state.root || ""; $("#setLang").value = LANG;
  $("#setBg").classList.add("open"); $("#setRoot").focus();
}
function closeSettings() { $("#setBg").classList.remove("open"); }
async function saveSettings() {
  // Only send what changed: a new folder means a rescan, a new language means a reload.
  const body = {}, root = $("#setRoot").value, language = $("#setLang").value;
  if (root.trim() !== (state.root || "")) body.root = root;
  if (language !== LANG) body.language = language;
  if (!Object.keys(body).length) return closeSettings();
  try {
    const d = await post("/api/settings", body);
    if (body.language) { if (d.warning) alert(d.warning); return location.reload(); }  // a toast would not survive the reload
    closeSettings(); closeModal(); await load(true);
    toast(d.warning || t("toast.folder_changed"));
  } catch (e) { toast(e.message); }
}
$("#settings").addEventListener("click", openSettings);
$("#setCancel").addEventListener("click", closeSettings);
$("#setSave").addEventListener("click", saveSettings);
$("#setRoot").addEventListener("keydown", e => { if (e.key === "Enter") saveSettings(); });
$("#setBg").addEventListener("click", e => { if (e.target.id === "setBg") closeSettings(); });
$("#setBrowse").addEventListener("click", async () => {
  try { const d = await post("/api/browse"); if (d.path) $("#setRoot").value = d.path; }
  catch (e) { toast(e.message); }
});

applyView();
load(true);
setInterval(load, 4000);

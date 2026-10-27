// Interface of the library. Every user-facing string stays in French.
const TOKEN = document.querySelector('meta[name="biblio-token"]').content;
const $ = s => document.querySelector(s);
let state = {items: [], removed: []}, lastJson = "", filter = "all", sortBy = "name", query = "", openId = null;

const STATUS = {"": "", todo: "Pas commencé", playing: "En cours", done: "Terminé", dropped: "Abandonné"};
const FILTERS = [
  ["all", "Tous", () => true],
  ["ready", "Prêts à jouer", i => i.kind === "dossier" && i.exe],
  ["archive", "Archives", i => i.kind === "archive"],
  ["executable", "Exécutables", i => i.kind === "executable"],
  ["fav", "Favoris", i => i.favorite],
  ["new", "Nouveaux", i => i.is_new],
  ["dup", "Doublons ?", i => i.dup],
];
const SORTS = {
  name: (a, b) => a.name.localeCompare(b.name, "fr", {sensitivity: "base"}),
  added: (a, b) => (b.added || 0) - (a.added || 0),
  size: (a, b) => (b.size || 0) - (a.size || 0),
  played: (a, b) => (b.last_launched || 0) - (a.last_launched || 0),
};

const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
function fmtSize(b) {
  if (b == null) return "…";
  const u = ["o", "Ko", "Mo", "Go", "To"]; let i = 0;
  while (b >= 1024 && i < u.length - 1) { b /= 1024; i++; }
  return (i >= 3 ? b.toFixed(1) : Math.round(b)).toString().replace(".", ",") + " " + u[i];
}
const fmtDate = t => t ? new Date(t * 1000).toLocaleDateString("fr-FR", {day: "numeric", month: "short", year: "numeric"}) : "";
function initials(name) {
  const small = new Set(["the", "of", "a", "an", "and", "de", "du", "la", "le", "les", "-"]);
  const w = name.split(/\s+/).filter(x => /[\p{L}\p{N}]/u.test(x) && !small.has(x.toLowerCase()));
  return ((w[0] || "?")[0] + ((w[1] || "")[0] || "")).toUpperCase();
}
function kindInfo(it) {
  if (it.kind === "dossier")
    return it.exe ? {label: "Prêt à jouer", cls: "ready", act: "▶ Jouer", action: "launch"}
                  : {label: it.computing ? "Analyse…" : "Dossier", cls: "folder", act: "Ouvrir", action: "reveal"};
  if (it.kind === "archive") return {label: "Archive · à extraire", cls: "archive", act: "Ouvrir l'archive", action: "launch"};
  if (it.kind === "executable") return {label: "Exécutable", cls: "exe", act: "▶ Lancer", action: "launch"};
  return {label: "Fichier", cls: "other", act: "Ouvrir", action: "launch"};
}
function toast(msg) {
  const t = $("#toast"); t.textContent = msg; t.classList.add("show");
  clearTimeout(toast.timer); toast.timer = setTimeout(() => t.classList.remove("show"), 2200);
}
async function post(url, body) {
  const r = await fetch(url, {method: "POST", headers: {"Content-Type": "application/json", "X-Biblio-Token": TOKEN},
                              body: JSON.stringify(body || {})});
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || "Erreur " + r.status);
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
  $("#path").textContent = state.root;
  const total = items.reduce((s, i) => s + (i.size || 0), 0);
  const pending = items.filter(i => i.computing).length;
  const count = f => items.filter(FILTERS.find(x => x[0] === f)[2]).length;
  $("#stats").innerHTML = [
    [items.length, "éléments"], [fmtSize(total) + (pending ? "+" : ""), pending ? `occupés · ${pending} en analyse` : "occupés"],
    [count("ready"), "prêts à jouer"], [count("archive"), "archives"], [count("executable"), "exécutables"],
  ].map(([b, s]) => `<div class="stat"><b>${esc(b)}</b><span>${esc(s)}</span></div>`).join("");

  $("#chips").innerHTML = FILTERS.map(([k, label, fn]) => {
    const n = items.filter(fn).length;
    if (k !== "all" && !n && filter !== k) return "";
    return `<button class="chip ${filter === k ? "on" : ""}" data-filter="${k}" aria-pressed="${filter === k}">${label}<small>${n}</small></button>`;
  }).join("");

  const fn = FILTERS.find(x => x[0] === filter)[2];
  const q = query.trim().toLowerCase();
  const list = items.filter(i => fn(i) && (!q || (i.name + " " + i.file + " " + i.description).toLowerCase().includes(q))).sort(SORTS[sortBy]);
  $("#empty").hidden = list.length > 0;
  $("#grid").innerHTML = list.map(it => {
    const k = kindInfo(it);
    const hue = parseInt(it.id.slice(0, 4), 16) % 360;
    const meta = [fmtSize(it.size), it.source, fmtDate(it.added)].filter(Boolean).join(" · ");
    return `<div class="card" data-id="${it.id}">
      <div class="cover ${it.cover ? "has-img" : ""}" style="--h:${hue}">
        ${it.cover ? `<img src="${esc(it.cover)}" alt="" loading="lazy">` : `<span class="initials">${esc(initials(it.name))}</span>`}
        <button class="star ${it.favorite ? "on" : ""}" data-act="fav" title="Favori" aria-label="Favori" aria-pressed="${!!it.favorite}">★</button>
        <div class="badges">
          <span class="b ${k.cls}">${k.label}</span>
          ${it.is_new ? '<span class="b new">Nouveau</span>' : ""}
          ${it.dup ? '<span class="b dup" title="Un autre élément semble être le même jeu">Doublon ?</span>' : ""}
        </div>
      </div>
      <div class="body">
        <div class="title" title="${esc(it.file)}">${esc(it.name)}</div>
        <div class="meta">${esc(meta)}</div>
        ${it.description ? `<div class="desc">${esc(it.description)}</div>` : ""}
        ${it.status ? `<div class="status">${esc(STATUS[it.status] || "")}</div>` : ""}
        <div class="actions">
          <button class="btn ${k.cls === "ready" || k.cls === "exe" ? "primary" : ""}" data-act="${k.action}">${k.act}</button>
          <button class="btn more" data-act="details" title="Détails">⋯</button>
        </div>
      </div>
    </div>`;
  }).join("");

  const rm = state.removed || [];
  $("#removedBox").hidden = !rm.length;
  $("#removed").innerHTML = rm.map(r => `<li>${esc(r.name)} <small>— ${esc(r.file)} · disparu le ${fmtDate(r.removed_at)}</small></li>`).join("");
}

async function act(id, action) {
  const it = byId(id); if (!it) return;
  try {
    if (action === "fav") { await post("/api/update/" + id, {favorite: !it.favorite}); }
    else if (action === "details") { openModal(id); return; }
    else { await post(`/api/${action}/` + id); toast(action === "launch" ? `Lancement : ${it.name}` : "Ouverture de l'emplacement"); }
    load(true);
  } catch (e) { toast(e.message); }
}

function openModal(id) { openId = id; fillModal(true); $("#modalBg").classList.add("open"); }
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
$("#rescan").addEventListener("click", async () => { await post("/api/rescan"); await load(true); toast("Dossier rescanné"); });
$("#quit").addEventListener("click", async () => {
  if (!confirm("Arrêter la bibliothèque ?")) return;
  await post("/api/quit").catch(() => {});
  document.body.innerHTML = '<p style="padding:40px;text-align:center;color:var(--dp-color-ink-secondary)">Ludex est arrêté. Tu peux fermer cet onglet.</p>';
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
  if (!blob || !/^image\//.test(blob.type)) return toast("Ce n'est pas une image.");
  if (blob.size > 15 * 1024 * 1024) return toast("Image trop lourde (15 Mo max).");
  try {
    const r = await fetch("/api/cover/" + id, {method: "POST", body: blob,
      headers: {"Content-Type": blob.type, "X-Biblio-Token": TOKEN}});
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.error || "Erreur " + r.status);
    toast("Image ajoutée"); load(true);
  } catch (e) { toast(e.message); }
}
async function coverFromUrl(id, url) {
  toast("Téléchargement de l'image…");
  try { await post("/api/cover/" + id, {url}); toast("Image ajoutée"); load(true); }
  catch (e) { toast(e.message); }
}
function handleDrop(id, dt) {
  const file = [...(dt.files || [])].find(f => /^image\//.test(f.type));
  if (file) return uploadCover(id, file);
  const url = (dt.getData("text/uri-list") || dt.getData("text/plain") || "").split("\n")[0].trim();
  if (/^https?:\/\//i.test(url)) return coverFromUrl(id, url);
  toast("Dépose un fichier image ou une image depuis un site.");
}
const hasDrag = e => [...e.dataTransfer.types].some(t => t === "Files" || t === "text/uri-list");

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
  const url = prompt("Adresse de l'image (clic droit sur une image → Copier l'adresse de l'image) :");
  if (url && url.trim()) coverFromUrl(openId, url.trim());
});
$("#mUncover").addEventListener("click", () => post("/api/uncover/" + openId).then(() => { toast("Image retirée"); load(true); }));

$("#mLaunch").addEventListener("click", e => act(openId, e.target.dataset.action));
$("#mReveal").addEventListener("click", () => act(openId, "reveal"));
$("#mClose").addEventListener("click", closeModal);
$("#modalBg").addEventListener("click", e => { if (e.target.id === "modalBg") closeModal(); });
document.addEventListener("keydown", e => { if (e.key === "Escape") { closeModal(); closeSettings(); } });

// ---- settings: watched folder
function openSettings() { $("#setRoot").value = state.root || ""; $("#setBg").classList.add("open"); $("#setRoot").focus(); }
function closeSettings() { $("#setBg").classList.remove("open"); }
async function saveSettings() {
  try {
    const d = await post("/api/settings", {root: $("#setRoot").value});
    closeSettings(); closeModal(); await load(true);
    toast(d.warning || "Dossier changé");
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

load(true);
setInterval(load, 4000);

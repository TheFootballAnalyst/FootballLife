"use strict";
// FootballLife — front-end of web/app/serveur.py.  Vanilla JS, one file.
// State lives on the server; this page only holds what it just fetched.

const QUOTA = {GK: 2, DEF: 5, MID: 5, FWD: 3};
const FAMS = ["GK", "DEF", "MID", "FWD"];
const NOM_FAM = {GK: "Gardien", DEF: "Défenseur", MID: "Milieu", FWD: "Attaquant"};
const PLURIEL = {GK: "gardiens", DEF: "défenseurs", MID: "milieux", FWD: "attaquants"};
const POSTE_COURT = {"Gardien":"Gardien","Defenseur central":"Défenseur central","Lateral":"Latéral","Milieu defensif":"Milieu défensif","Milieu relayeur":"Milieu relayeur","Milieu offensif":"Meneur","Ailier":"Ailier","Ailier droit":"Ailier droit","Ailier gauche":"Ailier gauche","Buteur":"Buteur"};
const ATTR_NOMS = {FIN:"Finition",CRE:"Création",PRO:"Progression",DEF:"Défense",DRI:"Dribble",CON:"Conservation",ARR:"Arrêts",EVI:"Buts évités",SOR:"Sorties",REL:"Relance",BUT:"Imbattabilité"};
const AXES = {champ:["FIN","CRE","PRO","DEF","DRI","CON"], gardien:["ARR","EVI","SOR","REL","BUT","PRO"]};
const f1 = x => (Math.round((+x || 0) * 10) / 10).toFixed(1);

// ---- état local (miroir de ce que le serveur a renvoyé) ----
const G = {moi: null, saison: null, cartes: [], idx: new Map(), equipe: null, compo: null, ecran: "connexion"};
let TAILLE = 15, FORMATIONS = {"4-3-3": [1,4,3,3]}, LIMITES = {GK: [1,1], DEF: [3,5], MID: [2,5], FWD: [1,3]};

// ---- utilitaires ----
const $ = s => document.querySelector(s);
const el = (tag, attrs = {}, ...kids) => { const e = document.createElement(tag); for (const [k, v] of Object.entries(attrs)) { if (v === null || v === false || v === undefined) continue; if (k === "class") e.className = v; else if (k.startsWith("on")) e.addEventListener(k.slice(2), v); else e.setAttribute(k, v); } for (const k of kids) if (k != null) e.append(k); return e; };
function toast(msg) { const t = $("#toast"); t.textContent = msg; t.classList.add("on"); clearTimeout(t._t); t._t = setTimeout(() => t.classList.remove("on"), 2200); }
async function api(chemin, corps, methode) {
  const r = await fetch("/api" + chemin, {method: methode || (corps ? "POST" : "GET"), headers: corps ? {"Content-Type": "application/json"} : {}, body: corps ? JSON.stringify(corps) : undefined, credentials: "same-origin"});
  let data = null; try { data = await r.json(); } catch (e) {}
  if (!r.ok) { const e = new Error((data && data.detail) ? (typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail)) : r.statusText); e.status = r.status; throw e; }
  return data;
}
const carte = id => G.idx.get(+id);
const ovr = id => carte(id)?.ovr ?? 0;
const prix = id => carte(id)?.prix ?? 0;
const idsEffectif = () => Object.keys(G.equipe?.effectif || {}).map(Number);
const patrimoine = () => (G.equipe?.budget || 0) + idsEffectif().reduce((a, i) => a + prix(i), 0);
const nbFam = fam => idsEffectif().filter(i => carte(i)?.fam === fam).length;
function vignette(id) {
  const c = carte(id); const v = el("div", {class: "vign"});
  const img = el("img", {src: `/images/joueurs/${id}.png`, alt: "", loading: "lazy"});
  img.addEventListener("error", () => { img.remove(); v.append(el("span", {class: "init"}, (c?.nom || "?").split(" ").slice(0, 2).map(w => w[0]).join(""))); });
  v.append(img); return v;
}
function barresForme(c) {
  const f = el("div", {class: "forme", title: "dernières notes"});
  for (const [n] of (c.notes || [])) { const b = el("i"); b.style.height = (4 + Math.max(0, n - 1) * 2.4) + "px"; b.style.background = n >= 7 ? "var(--vert)" : n < 5 ? "var(--rouge)" : "var(--sourd)"; f.append(b); }
  return f;
}
const formeMoy = c => { const r = (c.notes || []).slice(-5); const w = r.reduce((a, x) => a + x[1] / 90, 0); return w ? r.reduce((a, x) => a + x[0] * x[1] / 90, 0) / w : 0; };

// ---- chargement ----
async function rafraichir(tout) {
  G.saison = await api("/saison");
  if (tout || !G.cartes.length) { G.cartes = await api("/cartes"); G.idx = new Map(G.cartes.map(c => [c.id, c])); }
  G.equipe = await api("/equipe");
  G.compo = G.equipe.composition || compoVide();
  majStatut();
}
function majStatut() {
  const j = G.saison?.courante;
  $("#marque-sous").textContent = "saison " + (G.saison?.saison || "");
  $("#st-j").textContent = j ? "J" + j.numero + (j.verrouillee ? " 🔒" : "") : "Fin";
  $("#st-cash").textContent = f1(G.equipe?.budget);
  $("#st-val").textContent = f1(patrimoine());
  $("#st-pts").textContent = f1(G.equipe?.points);
  $("#st-rang").textContent = G.equipe ? `${G.equipe.rang}/${G.saison.equipes}` : "—";
}
async function montrer(ecran) {
  G.ecran = ecran;
  for (const s of document.querySelectorAll("main > section")) s.hidden = s.id !== "ecran-" + ecran;
  for (const b of document.querySelectorAll("nav button[data-ecran]")) b.setAttribute("aria-current", b.dataset.ecran === ecran ? "page" : "false");
  try { location.hash = ecran; } catch (e) {}
  if (ecran === "connexion") return;
  try {
    await rafraichir(ecran === "marche" || !G.cartes.length);
    await ({marche: rendreMarche, equipe: rendreEquipe, journee: rendreJournee, classement: rendreClassement, admin: rendreAdmin}[ecran] || (async () => {}))();
  } catch (e) { if (e.status === 401) { connecte(null); } else toast(e.message); }
}
function connecte(moi) {
  G.moi = moi;
  const on = !!(moi && moi.connecte);
  $("#statut").hidden = !on; $("#nav").hidden = !on; $("#nav-admin").hidden = !(on && moi.admin);
  if (!on) { for (const s of document.querySelectorAll("main > section")) s.hidden = s.id !== "ecran-connexion"; G.ecran = "connexion"; }
}

// ---- connexion ----
let modeAuth = "connexion";
for (const b of document.querySelectorAll(".onglets button")) b.addEventListener("click", () => {
  modeAuth = b.dataset.mode;
  for (const x of document.querySelectorAll(".onglets button")) x.setAttribute("aria-current", x === b ? "page" : "false");
  $("#champ-equipe").hidden = modeAuth !== "inscription";
  $("#auth-bouton").textContent = modeAuth === "inscription" ? "Créer mon compte" : "Se connecter";
});
$("#form-auth").addEventListener("submit", async e => {
  e.preventDefault(); $("#auth-erreur").textContent = "";
  const fd = new FormData(e.target);
  try {
    const r = await api("/" + modeAuth, {pseudo: fd.get("pseudo"), mot_de_passe: fd.get("mot_de_passe"), equipe: fd.get("equipe") || null});
    connecte({connecte: true, ...r});
    await montrer(idsEffectif().length ? "equipe" : "marche");
    if (modeAuth === "inscription") toast("Bienvenue ! Recrute tes 15 cartes.");
  } catch (err) { $("#auth-erreur").textContent = err.message; }
});
$("#btn-deconnexion").addEventListener("click", async () => { await api("/deconnexion", {}); connecte(null); });

// ---- marché ----
let marcheLimite = 60;
function peutAcheter(id) {
  const c = carte(id);
  if (G.equipe.effectif[id]) return "déjà dans l'effectif";
  if (!G.equipe.marche_ouvert) return "marché fermé";
  if (idsEffectif().length >= TAILLE) return `effectif complet (${TAILLE})`;
  if (nbFam(c.fam) >= QUOTA[c.fam]) return `déjà ${QUOTA[c.fam]} ${PLURIEL[c.fam]}`;
  if (c.prix > G.equipe.budget + 1e-9) return "pas assez de crédits";
  return null;
}
async function acheter(id) {
  const why = peutAcheter(id); if (why) { toast(why); return; }
  try { const r = await api("/equipe/acheter", {player_id: id}); toast(`${carte(id).nom} recruté pour ${f1(r.prix)}`); await rafraichir(false); rendreMarche(); }
  catch (e) { toast(e.message); }
}
async function vendre(id) {
  try { const r = await api("/equipe/vendre", {player_id: id}); toast(`${carte(id).nom} vendu ${f1(r.prix)}`); await rafraichir(false); rendreMarche(); if (G.ecran === "equipe") rendreEquipe(); }
  catch (e) { toast(e.message); }
}
function rendreMarche() {
  const mf = $("#marche-ferme"); mf.hidden = !!G.equipe.marche_ouvert;
  mf.textContent = !G.saison.courante
    ? "Aucune journée ouverte sur cette base : la saison est terminée, ou le serveur a été lancé sur la mauvaise base (utiliser  py web/app/lancer.py)."
    : "Marché fermé : la journée est verrouillée. Les transferts rouvrent une fois la journée calculée par l'administrateur.";
  const norm = s => (s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
  const q = norm($("#f-nom").value), fam = $("#f-fam").value, ligue = $("#f-ligue").value, tri = $("#f-tri").value;
  const abord = $("#f-abord").checked, miens = $("#f-miens").checked;
  let rows = G.cartes.filter(c => {
    if (fam && c.fam !== fam) return false; if (ligue && c.ligue !== ligue) return false;
    if (abord && c.prix > G.equipe.budget) return false; if (miens && !G.equipe.effectif[c.id]) return false;
    if (q && !norm(c.nom).includes(q) && !norm(c.club).includes(q)) return false; return true;
  });
  const cle = {ovr: c => -c.ovr, prix: c => -c.prix, forme: c => -formeMoy(c), part: c => -c.part, nom: c => 0}[tri];
  rows.sort((a, b) => cle(a) - cle(b) || a.nom.localeCompare(b.nom));
  $("#marche-compteur").textContent = `${rows.length} cartes`;
  $("#marche-effectif").textContent = `${idsEffectif().length} / ${TAILLE} · ${FAMS.map(f => nbFam(f) + "/" + QUOTA[f]).join(" · ")}`;
  const L = $("#marche-liste"); L.replaceChildren();
  for (const c of rows.slice(0, marcheLimite)) L.append(ligneCarte(c));
  $("#marche-plus").hidden = rows.length <= marcheLimite;
}
function ligneCarte(c) {
  const mien = !!G.equipe.effectif[c.id];
  const l = el("div", {class: "ligne", tabindex: "0", role: "button", onclick: () => ouvrirFiche(c.id), onkeydown: e => { if (e.key === "Enter") ouvrirFiche(c.id); }});
  l.style.setProperty("--clubc", c.couleur);
  const delta = mien ? c.prix - G.equipe.effectif[c.id] : 0;
  l.append(vignette(c.id),
    el("div", {class: "qui"}, el("div", {class: "nom"}, c.nom), el("div", {class: "sous"}, `${c.club} · ${POSTE_COURT[c.poste] || c.poste}${c.part > 0 ? " · " + Math.round(c.part * 100) + " % des équipes" : ""}`)),
    barresForme(c),
    el("div", {class: "ovr num" + (c.ovr >= 80 ? " haut" : "")}, String(c.ovr)),
    el("div", {class: "prix num"}, f1(c.prix), mien && Math.abs(delta) >= 0.05 ? el("div", {class: "delta " + (delta > 0 ? "plus" : "moins")}, (delta > 0 ? "+" : "") + f1(delta)) : null));
  const why = mien ? null : peutAcheter(c.id);
  const b = mien ? el("button", {disabled: !G.equipe.marche_ouvert, onclick: e => { e.stopPropagation(); vendre(c.id); }}, "Vendre")
                 : el("button", {class: why ? "" : "primaire", title: why || "", onclick: e => { e.stopPropagation(); acheter(c.id); }}, "Acheter");
  l.append(b);
  return l;
}

// ---- équipe ----
function compoVide() { return {formation: "4-3-3", titulaires: [], banc: [], capitaine: null}; }
function slotsFam(formation) { const [g, d, m, f] = FORMATIONS[formation]; return [...Array(g).fill("GK"), ...Array(d).fill("DEF"), ...Array(m).fill("MID"), ...Array(f).fill("FWD")]; }
function legal(fams) { if (fams.length !== 11 || fams.some(x => !x)) return false; return FAMS.every(f => { const n = fams.filter(x => x === f).length; return n >= LIMITES[f][0] && n <= LIMITES[f][1]; }); }
// composition locale : slots (11, null si vide), banc, capitaine
let C = {formation: "4-3-3", slots: Array(11).fill(null), banc: [], cap: null};
function compoVersSlots() {
  const cp = G.compo; const fams = slotsFam(cp.formation in FORMATIONS ? cp.formation : "4-3-3");
  const slots = Array(11).fill(null); const reste = cp.titulaires.filter(id => carte(id));
  for (let s = 0; s < 11; s++) { const k = reste.findIndex(id => carte(id).fam === fams[s]); if (k >= 0) { slots[s] = reste[k]; reste.splice(k, 1); } }
  const tous = new Set(idsEffectif());
  const banc = cp.banc.filter(id => tous.has(id) && !slots.includes(id));
  for (const id of tous) if (!slots.includes(id) && !banc.includes(id)) banc.push(id);
  C = {formation: fams.length ? (cp.formation in FORMATIONS ? cp.formation : "4-3-3") : "4-3-3", slots, banc, cap: slots.includes(cp.capitaine) ? cp.capitaine : null};
}
function auto(formation) {
  C.formation = formation; const fams = slotsFam(formation);
  const tri = idsEffectif().sort((a, b) => ovr(b) - ovr(a)); const pris = new Set(); const slots = [];
  for (const fam of fams) { const i = tri.find(x => carte(x).fam === fam && !pris.has(x)); slots.push(i ?? null); if (i !== undefined) pris.add(i); }
  C.slots = slots; C.banc = tri.filter(x => !pris.has(x));
  if (!slots.includes(C.cap)) C.cap = slots.find(x => x !== null) ?? null;
  rendreEquipe(false);
}
function rendreEquipe(recalc = true) {
  if (recalc) compoVersSlots();
  const sel = $("#formation"); if (!sel.options.length) for (const f of Object.keys(FORMATIONS)) sel.append(el("option", {value: f}, f));
  sel.value = C.formation;
  const fams = slotsFam(C.formation); const [g, d, m, f] = FORMATIONS[C.formation];
  const T = $("#terrain"); T.replaceChildren();
  let k = 0;
  for (const n of [f, m, d, g]) { const rang = el("div", {class: "rang"}); const debut = 11 - (k + n); k += n; for (let s = debut; s < debut + n; s++) rang.append(slotEl(s, fams[s])); T.append(rang); }
  const ok = legal(C.slots.map(i => i === null ? null : carte(i).fam));
  const A = $("#avert-compo"); A.replaceChildren();
  if (!ok) A.append(el("div", {class: "avert"}, "Le onze n'est pas complet ou pas légal : 1 gardien, 3 à 5 défenseurs, 2 à 5 milieux, 1 à 3 attaquants."));
  const j = G.saison.courante;
  const etat = $("#compo-etat"); etat.replaceChildren();
  if (!j) etat.append("Saison terminée.");
  else if (j.verrouillee) etat.append(el("b", {}, `Journée ${j.numero} verrouillée`), ` depuis le coup d'envoi. Composition envoyée : ${G.equipe.composition ? "oui" : "non, score nul"}.`);
  else etat.append(`Journée ${j.numero}, du ${j.du} au ${j.au}. Verrouillage au premier coup d'envoi : ${new Date(j.cloture).toLocaleString("fr-FR")}. `, G.equipe.composition ? el("b", {}, `Composition envoyée le ${new Date(G.equipe.composition.soumise_le).toLocaleString("fr-FR")}.`) : el("b", {class: "rouge"}, "Aucune composition envoyée."));
  $("#btn-envoyer").disabled = !ok || !j || j.verrouillee;
  const B = $("#banc"); B.replaceChildren();
  C.banc.forEach((i, r) => B.append(ligneBanc(i, r)));
  if (!C.banc.length) B.append(el("p", {class: "compteur"}, "Banc vide. 4 remplaçants conseillés : un gardien et trois joueurs de champ."));
}
function slotEl(s, fam) {
  const i = C.slots[s];
  if (i === null) return el("div", {class: "slot vide", tabindex: "0", onclick: () => { const cands = C.banc.filter(x => carte(x).fam === fam).sort((a, b) => ovr(b) - ovr(a)); if (!cands.length) { toast(`Aucun ${NOM_FAM[fam].toLowerCase()} sur le banc`); return; } C.banc = C.banc.filter(x => x !== cands[0]); C.slots[s] = cands[0]; rendreEquipe(false); }}, el("div", {class: "n"}, NOM_FAM[fam]), el("div", {class: "o"}, "+"));
  const c = carte(i); const d = el("div", {class: "slot", tabindex: "0", onclick: () => menuSlot(s)});
  d.append(vignette(i), el("div", {class: "n"}, c.nom.split(" ").slice(-1)[0]), el("div", {class: "o num"}, String(c.ovr)));
  if (C.cap === i) d.append(el("div", {class: "cap"}, "C"));
  return d;
}
function menuSlot(s) {
  const i = C.slots[s]; const fam = carte(i).fam; const dlg = $("#fiche"); dlg.replaceChildren();
  const box = el("div", {class: "fiche"}, el("h3", {class: "anton"}, carte(i).nom), el("p", {class: "compteur"}, `${NOM_FAM[fam]} · OVR ${ovr(i)}`));
  const acts = el("div", {class: "actions", style: "justify-content:flex-start"});
  acts.append(el("button", {class: "primaire", onclick: () => { C.cap = i; dlg.close(); rendreEquipe(false); }}, "Nommer capitaine"));
  for (const b of C.banc.filter(x => carte(x).fam === fam)) acts.append(el("button", {onclick: () => { C.banc = C.banc.map(x => x === b ? i : x); C.slots[s] = b; if (C.cap === i) C.cap = b; dlg.close(); rendreEquipe(false); }}, `Remplacer par ${carte(b).nom} (${ovr(b)})`));
  acts.append(el("button", {onclick: () => { C.slots[s] = null; C.banc.unshift(i); if (C.cap === i) C.cap = null; dlg.close(); rendreEquipe(false); }}, "Mettre sur le banc"));
  acts.append(el("button", {onclick: () => { dlg.close(); ouvrirFiche(i); }}, "Voir la fiche"), el("button", {class: "discret", onclick: () => dlg.close()}, "Fermer"));
  box.append(acts); dlg.append(box); dlg.showModal();
}
function ligneBanc(i, r) {
  const c = carte(i);
  const l = el("div", {class: "ligne", tabindex: "0", onclick: () => ouvrirFiche(i)}); l.style.setProperty("--clubc", c.couleur);
  const ord = el("div", {class: "ordre"},
    el("button", {title: "Monter", disabled: r === 0, onclick: e => { e.stopPropagation(); [C.banc[r - 1], C.banc[r]] = [C.banc[r], C.banc[r - 1]]; rendreEquipe(false); }}, "▲"),
    el("button", {title: "Descendre", disabled: r === C.banc.length - 1, onclick: e => { e.stopPropagation(); [C.banc[r + 1], C.banc[r]] = [C.banc[r], C.banc[r + 1]]; rendreEquipe(false); }}, "▼"));
  l.append(ord, vignette(i), el("div", {class: "qui"}, el("div", {class: "nom"}, c.nom), el("div", {class: "sous"}, c.club)), el("span", {class: "fam " + c.fam}, c.fam), el("div", {class: "ovr num"}, String(c.ovr)));
  return l;
}
async function envoyer() {
  try {
    const r = await api("/equipe/composition", {formation: C.formation, titulaires: C.slots, banc: C.banc, capitaine: C.cap});
    toast(`Composition envoyée pour la journée ${r.journee}`); await rafraichir(false); rendreEquipe();
  } catch (e) { toast(e.message); }
}

// ---- journée ----
async function rendreJournee() {
  const P = $("#journee-pan"); P.replaceChildren();
  const j = G.saison.courante, d = G.saison.derniere;
  const res = await api("/resultats");
  const dernier = d && res.find(r => r.journee === d.numero);
  if (d && dernier) {
    const det = await api("/resultats/" + d.numero);
    P.append(el("div", {class: "tete"}, el("h2", {class: "anton"}, `Journée ${d.numero}`), el("span", {class: "compteur"}, `${det.participants} équipes classées`)),
      el("div", {class: "gros num"}, f1(det.score)),
      el("div", {class: "recap"},
        el("div", {class: "tuile"}, el("div", {class: "etiq"}, "Rang de la journée"), el("b", {class: "num"}, `${det.rang}/${det.participants}`)),
        el("div", {class: "tuile"}, el("div", {class: "etiq"}, "Gain"), el("b", {class: "num"}, "+" + f1(det.gain))),
        el("div", {class: "tuile"}, el("div", {class: "etiq"}, "Entrés du banc"), el("b", {class: "num"}, String(det.onze.filter(p => !(G.equipe.composition?.titulaires || []).includes(p)).length)))));
    if (det.detail.refusee) P.append(el("div", {class: "avert"}, "Composition refusée : " + det.detail.refusee));
    const t = el("table"); t.append(el("thead", {}, el("tr", {}, el("th", {}, "Joueur"), el("th", {}, "Matchs (note · min)"), el("th", {class: "num"}, "Points"))));
    const tb = el("tbody");
    const lignes = det.onze.map(pid => ({pid, p: det.detail[String(pid)] ?? 0})).sort((a, b) => b.p - a.p);
    for (const {pid, p} of lignes) {
      const c = carte(pid); const pres = det.prestations[String(pid)] || [];
      tb.append(el("tr", {}, el("td", {}, el("b", {}, (c ? c.nom : "#" + pid))),
        el("td", {}, pres.length ? el("div", {class: "notes"}, ...pres.map(x => el("span", {class: "note " + (x.note >= 7 ? "b" : x.note < 5 ? "m" : ""), title: x.competition}, `${f1(x.note)} · ${Math.round(x.minutes)}'`))) : el("span", {class: "compteur"}, "n'a pas joué")),
        el("td", {class: "num"}, f1(p))));
    }
    t.append(tb); P.append(el("div", {class: "tableau"}, t), el("hr", {style: "border:0;border-top:1px solid var(--ligne);margin:14px 0"}));
  } else if (d) {
    P.append(el("p", {class: "info"}, `Journée ${d.numero} calculée ; tu n'avais pas d'équipe ou pas de composition.`));
  }
  if (j) {
    P.append(el("div", {class: "tete"}, el("h2", {class: "anton"}, `Journée ${j.numero}`), el("span", {class: "compteur"}, `du ${j.du} au ${j.au}`)));
    P.append(el("p", {class: "info"}, j.verrouillee
      ? el("span", {}, el("b", {}, "Verrouillée."), " Les matchs se jouent ; le score arrive quand l'administrateur clôture la journée.")
      : el("span", {}, "Verrouillage au premier coup d'envoi : ", el("b", {}, new Date(j.cloture).toLocaleString("fr-FR")), ". ", G.equipe.composition ? "Composition envoyée." : "Pas de composition envoyée : va sur Équipe.")));
  } else P.append(el("p", {class: "info"}, "Saison terminée."));
  const tb = $("#histo tbody"); tb.replaceChildren();
  for (const r of res) tb.append(el("tr", {}, el("td", {}, "J" + r.journee), el("td", {class: "num"}, f1(r.score)), el("td", {class: "num"}, "+" + f1(r.gain)), el("td", {class: "num"}, String(r.rang))));
}

// ---- classement et ligues ----
async function rendreClassement() {
  const cl = await api("/classement"); const tb = $("#classement tbody"); tb.replaceChildren();
  for (const r of cl) tb.append(el("tr", {class: r.equipe_id === G.equipe.equipe_id ? "moi" : ""}, el("td", {}, String(r.rang)), el("td", {}, r.equipe), el("td", {}, r.pseudo), el("td", {class: "num"}, f1(r.points)), el("td", {class: "num"}, r.derniere == null ? "—" : f1(r.derniere)), el("td", {class: "num"}, f1(r.patrimoine))));
  const L = $("#ligues"); L.replaceChildren();
  for (const l of await api("/ligues")) {
    const box = el("div", {class: "ligue"}, el("div", {class: "tete"}, el("h3", {class: "anton"}, l.nom), el("span", {class: "compteur"}, "code ", el("span", {class: "code"}, l.code))));
    const t = el("table"); const b = el("tbody");
    for (const r of l.classement) b.append(el("tr", {class: r.equipe_id === G.equipe.equipe_id ? "moi" : ""}, el("td", {}, String(r.rang)), el("td", {}, r.equipe), el("td", {class: "num"}, f1(r.points))));
    t.append(b); box.append(el("div", {class: "tableau"}, t)); L.append(box);
  }
}
$("#btn-creer-ligue").addEventListener("click", async () => { try { const r = await api("/ligues", {nom: $("#ligue-nom").value}); toast(`Ligue créée, code ${r.code}`); $("#ligue-nom").value = ""; rendreClassement(); } catch (e) { toast(e.message); } });
$("#btn-rejoindre-ligue").addEventListener("click", async () => { try { const r = await api("/ligues/rejoindre", {code: $("#ligue-code").value}); toast(`Tu as rejoint ${r.nom}`); $("#ligue-code").value = ""; rendreClassement(); } catch (e) { toast(e.message); } });

// ---- admin ----
async function rendreAdmin() {
  const A = $("#admin-etat"); A.replaceChildren();
  const e = await api("/admin/etat");
  const cour = G.saison.courante;
  A.append(el("p", {class: "info"}, `${e.cartes} cartes · ${e.equipes} équipes · échelle OVR ${e.echelle?.bas} → ${e.echelle?.haut}`));
  const js = el("div", {class: "journees"});
  for (const j of e.journees.filter(x => x.numero >= 1)) js.append(el("span", {class: j.calculee ? "ok" : (cour && cour.numero === j.numero ? "cour" : ""), title: `${j.du} → ${j.au}`}, "J" + j.numero));
  A.append(js);
  if (!cour) { A.append(el("p", {class: "info"}, "Toutes les journées sont calculées.")); return; }
  A.append(el("h3", {class: "anton", style: "margin-top:14px"}, `Journée ${cour.numero} · ${cour.verrouillee ? "verrouillée" : "ouverte"}`),
    el("p", {class: "compteur"}, `Fenêtre ${cour.du} → ${cour.au}. Clôture : ${new Date(cour.cloture).toLocaleString("fr-FR")}.`));
  const acts = el("div", {class: "admin-actions"});
  acts.append(el("button", {onclick: async () => { await api(`/admin/journee/${cour.numero}/verrouiller`, {}); toast("Journée verrouillée"); montrer("admin"); }}, "Verrouiller maintenant"));
  acts.append(el("button", {onclick: async () => { await api(`/admin/journee/${cour.numero}/ouvrir`, {}); toast("Journée rouverte 7 jours"); montrer("admin"); }}, "Rouvrir 7 jours"));
  const fichier = el("input", {type: "file", accept: ".json"});
  acts.append(el("label", {class: "case"}, "Prestations notées (JSON) : ", fichier),
    el("button", {onclick: async () => {
      if (!fichier.files[0]) { toast("Choisis le fichier exporté par jeu.exporter_journee"); return; }
      const fd = new FormData(); fd.append("fichier", fichier.files[0]);
      const r = await fetch(`/api/admin/journee/${cour.numero}/prestations`, {method: "POST", body: fd});
      const d = await r.json(); toast(r.ok ? `${d.prestations} prestations chargées` : (d.detail || "échec"));
    }}, "Charger les prestations"));
  acts.append(el("button", {class: "primaire", onclick: async () => {
      if (!confirm(`Clôturer la journée ${cour.numero} ? Les scores seront calculés et les cartes mises à jour.`)) return;
      try { const r = await api(`/admin/journee/${cour.numero}/calculer`, {}); toast(`Journée ${cour.numero} calculée : ${r.equipes} équipes, ${r.cartes_bougees} cartes bougées`); await montrer("admin"); }
      catch (err) { toast(err.message); }
    }}, `Clôturer la journée ${cour.numero}`));
  A.append(acts, el("p", {class: "compteur"}, "Ordre normal : la journée se verrouille au premier coup d'envoi ; après le dernier match, charger les prestations exportées localement (jeu.exporter_journee) puis clôturer. En démo, les prestations sont déjà en base : clôturer suffit."));
}

// ---- démarrage ----
for (const b of document.querySelectorAll("nav button[data-ecran]")) b.addEventListener("click", () => montrer(b.dataset.ecran));
for (const id of ["f-nom", "f-fam", "f-ligue", "f-tri", "f-abord", "f-miens"]) $("#" + id).addEventListener("input", () => { marcheLimite = 60; rendreMarche(); });
$("#marche-plus").addEventListener("click", () => { marcheLimite += 100; rendreMarche(); });
$("#formation").addEventListener("change", e => auto(e.target.value));
$("#btn-auto").addEventListener("click", () => auto(C.formation));
$("#btn-envoyer").addEventListener("click", envoyer);
$("#fiche").addEventListener("click", e => { if (e.target === e.currentTarget) e.currentTarget.close(); });

// ---- fiche ----
async function ouvrirFiche(id) {
  let d; try { d = await api("/cartes/" + id); } catch (e) { toast(e.message); return; }
  const dlg = $("#fiche"); dlg.replaceChildren();
  const box = el("div", {class: "fiche fiche-carte"});
  const img = el("img", {class: "carte-img", src: `/images/cartes/${id}.png?ovr=${d.ovr}`, alt: `Carte de ${d.nom}`});
  img.addEventListener("error", () => img.remove());
  const cote = el("div", {class: "fiche-cote"});
  cote.append(el("div", {class: "etiq"}, `${d.club} · ${d.ligue}`), el("h3", {class: "anton"}, d.nom),
    el("div", {class: "compteur"}, `${POSTE_COURT[d.poste] || d.poste} · ${d.matchs} matchs, ${d.minutes} min · ${Math.round(d.part * 100)} % des équipes`),
    el("div", {style: "display:flex;gap:14px;align-items:baseline;margin-top:6px"}, el("div", {class: "ovr num" + (d.ovr >= 80 ? " haut" : ""), style: "font-size:40px"}, String(d.ovr)), el("div", {class: "prix num", style: "font-size:22px"}, f1(d.prix) + " cr.")));
  box.append(el("div", {class: "fiche-haut"}, img, cote));
  const axes = d.fam === "GK" ? AXES.gardien : AXES.champ; const A = el("div", {class: "attrs"});
  for (const ax of axes) { const val = d.attributs[ax] ?? 40; A.append(el("div", {class: "attr"}, el("span", {}, ATTR_NOMS[ax]), el("div", {class: "jauge"}, el("i", {class: val >= 80 ? "haut" : "", style: `width:${(val - 40) / 59 * 100}%`})), el("b", {class: "num"}, String(val)))); }
  box.append(el("div", {class: "etiq"}, "Attributs de la saison"), A);
  box.append(el("div", {class: "etiq"}, "Dernières prestations"), el("div", {class: "notes"}, ...(d.prestations.length ? d.prestations.slice(0, 8).map(p => el("span", {class: "note " + (p.note >= 7 ? "b" : p.note < 5 ? "m" : ""), title: `J${p.numero} · ${p.competition}`}, `${f1(p.note)} · ${Math.round(p.minutes)}'`)) : [el("span", {class: "compteur"}, "aucun match noté cette saison")])));
  if (d.historique.length > 1) box.append(el("div", {class: "etiq", style: "margin-top:10px"}, "Prix par journée"), sparkline(d.historique.map(h => h.prix)));
  const acts = el("div", {class: "actions"});
  if (G.equipe.effectif[id]) { const dl = d.prix - G.equipe.effectif[id]; acts.append(el("span", {class: "compteur", style: "margin-right:auto"}, `acheté ${f1(G.equipe.effectif[id])} · ${dl >= 0 ? "+" : ""}${f1(dl)}`), el("button", {disabled: !G.equipe.marche_ouvert, onclick: () => { dlg.close(); vendre(id); }}, "Vendre " + f1(d.prix))); }
  else { const why = peutAcheter(id); acts.append(why ? el("span", {class: "compteur", style: "margin-right:auto"}, why) : null, el("button", {class: why ? "" : "primaire", disabled: !!why, onclick: () => { dlg.close(); acheter(id); }}, "Acheter " + f1(d.prix))); }
  acts.append(el("button", {class: "discret", onclick: () => dlg.close()}, "Fermer"));
  box.append(acts); dlg.append(box); dlg.showModal();
}
function sparkline(vals) {
  const W = 480, H = 60, lo = Math.min(...vals), hi = Math.max(...vals), pad = 6;
  const x = k => pad + k * (W - 2 * pad) / Math.max(1, vals.length - 1), y = v => hi === lo ? H / 2 : H - pad - (v - lo) * (H - 2 * pad) / (hi - lo);
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg"); svg.setAttribute("viewBox", `0 0 ${W} ${H}`); svg.setAttribute("class", "spark");
  svg.innerHTML = `<polyline points="${vals.map((v, k) => `${x(k).toFixed(1)},${y(v).toFixed(1)}`).join(" ")}" fill="none" stroke="var(--or)" stroke-width="2"/><circle cx="${x(vals.length - 1).toFixed(1)}" cy="${y(vals[vals.length - 1]).toFixed(1)}" r="3.5" fill="var(--or)"/><text x="${pad}" y="${H - 1}" font-size="10" fill="var(--sourd)" font-family="Barlow Condensed">${f1(vals[0])}</text><text x="${W - pad}" y="10" text-anchor="end" font-size="10" fill="var(--sourd)" font-family="Barlow Condensed">${f1(vals[vals.length - 1])}</text>`;
  return svg;
}

(async () => {
  try {
    const s = await api("/saison"); TAILLE = s.taille_effectif; FORMATIONS = s.formations; LIMITES = s.limites;
    const moi = await api("/moi"); connecte(moi);
    if (moi.connecte) { const h = location.hash.replace("#", ""); await montrer(["marche", "equipe", "journee", "classement", "admin"].includes(h) ? h : "equipe"); }
  } catch (e) { toast("Serveur injoignable : " + e.message); }
})();

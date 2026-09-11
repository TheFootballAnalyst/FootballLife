"use strict";
// FootballLife — front-end of web/app/serveur.py.  Vanilla JS, one file.
// State lives on the server; this page only holds what it just fetched.

const QUOTA = {GK: 2, DEF: 5, MID: 5, FWD: 3};
const FAMS = ["GK", "DEF", "MID", "FWD"];
const NOM_FAM = {GK: "Gardien", DEF: "Défenseur", MID: "Milieu", FWD: "Attaquant"};
const PLURIEL = {GK: "gardiens", DEF: "défenseurs", MID: "milieux", FWD: "attaquants"};
const POSTE_COURT = {"Gardien":"Gardien","Defenseur central":"Défenseur central","Lateral":"Latéral","Milieu defensif":"Milieu défensif","Milieu relayeur":"Milieu relayeur","Milieu offensif":"Meneur","Ailier":"Ailier","Ailier droit":"Ailier droit","Ailier gauche":"Ailier gauche","Buteur":"Buteur"};
const ATTR_NOMS = {FIN:"Finition",CRE:"Création",PRO:"Progression",DEF:"Défense",DRI:"Dribble",CON:"Conservation",ARR:"Arrêts",EVI:"Buts évités",SOR:"Sorties",REL:"Jeu long",BUT:"Imbattabilité"};
const ATTR_NOMS_GARDIEN = {PRO:"Jeu court"};   // a keeper's PRO axis is his short passing (jeu/bareme.py)
const AXES = {champ:["FIN","CRE","PRO","DEF","DRI","CON"], gardien:["ARR","EVI","SOR","REL","BUT","PRO"]};
const f1 = x => (Math.round((+x || 0) * 10) / 10).toFixed(1);
// money: every amount is in M€ (0.1 = 100 k€)
const fM = (x, signe = false) => { const v = +x || 0, a = Math.abs(v), s = v < 0 ? "−" : signe && v > 0 ? "+" : "";
  if (a < 1) return s + Math.round(a * 1000) + " k€";
  if (a < 10) return s + a.toFixed(2).replace(".", ",") + " M€";
  return s + (Math.round(a * 10) / 10).toFixed(1).replace(".", ",") + " M€"; };

// ISO-3 (FotMob) -> ISO-2, for the flag emoji on the card
const ISO2 = {FRA:"FR",ENG:"GB",SCO:"GB",WAL:"GB",NIR:"GB",IRL:"IE",ESP:"ES",ITA:"IT",GER:"DE",POR:"PT",NED:"NL",BEL:"BE",SUI:"CH",AUT:"AT",DEN:"DK",SWE:"SE",NOR:"NO",FIN:"FI",ISL:"IS",POL:"PL",CZE:"CZ",SVK:"SK",HUN:"HU",ROU:"RO",BUL:"BG",SRB:"RS",CRO:"HR",SVN:"SI",BIH:"BA",MNE:"ME",MKD:"MK",ALB:"AL",KOS:"XK",GRE:"GR",TUR:"TR",UKR:"UA",RUS:"RU",BLR:"BY",GEO:"GE",ARM:"AM",AZE:"AZ",KAZ:"KZ",ISR:"IL",CYP:"CY",MLT:"MT",LUX:"LU",LTU:"LT",LVA:"LV",EST:"EE",MDA:"MD",BRA:"BR",ARG:"AR",URU:"UY",PAR:"PY",CHI:"CL",COL:"CO",PER:"PE",ECU:"EC",VEN:"VE",BOL:"BO",MEX:"MX",USA:"US",CAN:"CA",JAM:"JM",CRC:"CR",HON:"HN",PAN:"PA",GUA:"GT",SLV:"SV",HAI:"HT",CUB:"CU",DOM:"DO",TRI:"TT",CUW:"CW",SUR:"SR",MAR:"MA",ALG:"DZ",TUN:"TN",EGY:"EG",SEN:"SN",CIV:"CI",CMR:"CM",NGA:"NG",GHA:"GH",MLI:"ML",GUI:"GN",BFA:"BF",COD:"CD",CGO:"CG",GAB:"GA",ANG:"AO",MOZ:"MZ",ZAM:"ZM",ZIM:"ZW",RSA:"ZA",KEN:"KE",UGA:"UG",TAN:"TZ",ETH:"ET",SUD:"SD",TOG:"TG",BEN:"BJ",NIG:"NE",GAM:"GM",SLE:"SL",LBR:"LR",CPV:"CV",GNB:"GW",EQG:"GQ",CTA:"CF",CHA:"TD",MTN:"MR",LBY:"LY",COM:"KM",MAD:"MG",BDI:"BI",RWA:"RW",JPN:"JP",KOR:"KR",CHN:"CN",AUS:"AU",NZL:"NZ",IRN:"IR",IRQ:"IQ",KSA:"SA",QAT:"QA",UAE:"AE",UZB:"UZ",IND:"IN",THA:"TH",VIE:"VN",PHI:"PH",IDN:"ID",MAS:"MY",SYR:"SY",JOR:"JO",LBN:"LB",PLE:"PS"};
const drapeau = code => { const c = ISO2[code] || (code && code.length === 2 ? code : null); if (!c) return ""; return String.fromCodePoint(...[...c.toUpperCase()].map(ch => 0x1F1E6 + ch.charCodeAt(0) - 65)); };
const ageTxt = c => c.age ? `${c.age} ans` : "";
const FAM_COURT = {GK: "GB", DEF: "DÉF", MID: "MIL", FWD: "ATT"};

// ---- état local (miroir de ce que le serveur a renvoyé) ----
const G = {moi: null, saison: null, cartes: [], idx: new Map(), equipe: null, compo: null, ecran: "connexion", ventes: [], club: [], packs: null};
const ventesDe = id => G.ventes.filter(v => v.player_id === id);
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
  try { G.ventes = (await api("/marche")).ventes; } catch (e) { G.ventes = []; }
  majStatut();
}
function majStatut() {
  const j = G.saison?.courante;
  $("#marque-sous").textContent = "saison " + (G.saison?.saison || "");
  $("#st-j").textContent = j ? "J" + j.numero + (j.verrouillee ? " 🔒" : "") : "Fin";
  $("#st-cash").textContent = fM(G.equipe?.budget);
  $("#st-val").textContent = fM(patrimoine());
  $("#st-pts").textContent = f1(G.equipe?.points);
  $("#st-rang").textContent = G.equipe ? `${G.equipe.rang}/${G.saison.equipes}` : "—";
  $("#st-elo").textContent = G.equipe?.elo ?? "—";
}
async function montrer(ecran) {
  G.ecran = ecran;
  for (const s of document.querySelectorAll("main > section")) s.hidden = s.id !== "ecran-" + ecran;
  for (const b of document.querySelectorAll("nav button[data-ecran]")) b.setAttribute("aria-current", b.dataset.ecran === ecran ? "page" : "false");
  try { location.hash = ecran; } catch (e) {}
  if (ecran === "connexion") return;
  try {
    await rafraichir(ecran === "marche" || !G.cartes.length);
    await ({packs: rendrePacks, encheres: rendreEncheres, marche: rendreMarche, equipe: rendreEquipe, match: rendreMatch, journee: rendreJournee, classement: rendreClassement, admin: rendreAdmin}[ecran] || (async () => {}))();
  } catch (e) { if (e.status === 401) { connecte(null); } else toast(e.message); }
}
async function vitrine() {
  const V = $("#vitrine"); if (!V || V.childElementCount) return;
  try { for (const c of await api("/vitrine")) V.append(carteMarche(c, {vitrine: true})); } catch (e) {}
}
function connecte(moi) {
  G.moi = moi;
  const on = !!(moi && moi.connecte);
  if (!on) vitrine();
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
    await montrer(idsEffectif().length ? "equipe" : "packs");
    if (modeAuth === "inscription") toast("Bienvenue ! Ouvre tes premiers packs.");
  } catch (err) { $("#auth-erreur").textContent = err.message; }
});
$("#btn-deconnexion").addEventListener("click", async () => { await api("/deconnexion", {}); connecte(null); });

// ---- marché ----
let marcheLimite = 60;
let marcheVue = "cartes";
try { marcheVue = localStorage.getItem("fl_vue") || "cartes"; } catch (e) {}
document.querySelectorAll(".vue button").forEach(b => b.addEventListener("click", () => { marcheVue = b.dataset.vue; try { localStorage.setItem("fl_vue", marcheVue); } catch (e) {} rendreMarche(); }));
document.querySelectorAll("#pills-fam button").forEach(b => b.addEventListener("click", () => { $("#f-fam").value = b.dataset.fam; document.querySelectorAll("#pills-fam button").forEach(x => x === b ? x.setAttribute("aria-current", "page") : x.removeAttribute("aria-current")); marcheLimite = 60; rendreMarche(); }));
// ---- the market: packs, club, auctions ----
const TIER_TXT = {bronze: "Bronze", argent: "Argent", or: "Or"};
const resteTxt = fin => { const ms = new Date(fin) - Date.now(); if (ms <= 0) return "terminée"; const h = Math.floor(ms / 3.6e6), m = Math.floor(ms % 3.6e6 / 6e4); return h ? `${h} h ${String(m).padStart(2, "0")}` : `${m} min`; };
async function rendrePacks() {
  G.packs = await api("/packs");
  const P = $("#packs-liste"); P.replaceChildren();
  $("#packs-info").textContent = `Une carte ne peut exister qu'en ${G.packs.plafond} exemplaires dans la ligue. Réserve : ${G.packs.reserve_max} cartes. La banque rachète à ${Math.round(G.packs.rachat * 100)} % de la cote.`;
  for (const p of G.packs.catalogue) {
    const k = el("div", {class: "pack " + p.type + (p.disponible ? "" : " epuise")},
      el("div", {class: "pack-tier etiq"}, TIER_TXT[p.type] + (p.fam ? " · " + (p.fam === "GK" ? "Gardiens" : p.fam === "DEF" ? "Défenseurs" : p.fam === "MID" ? "Milieux" : "Attaquants") : " · Mixte")),
      el("div", {class: "pack-visuel"}, el("div", {class: "pack-carte a"}), el("div", {class: "pack-carte b"}), el("div", {class: "pack-carte c"})),
      el("div", {class: "pack-desc"}, p.desc),
      el("div", {class: "pack-prix anton"}, fM(p.prix)),
      el("button", {class: "primaire", disabled: !p.disponible || p.prix > G.equipe.budget + 1e-9, onclick: () => ouvrirPack(p)}, p.disponible ? "Ouvrir" : "Épuisé"));
    P.append(k);
  }
}
async function ouvrirPack(p) {
  let r; try { r = await api("/packs/ouvrir", {type: p.type, fam: p.fam}); } catch (e) { toast(e.message); return; }
  await rafraichir(false);
  const dlg = $("#fiche"); dlg.replaceChildren();
  const box = el("div", {class: "fiche ouverture"}, el("h3", {class: "anton"}, `${p.nom}`), el("p", {class: "compteur"}, `${fM(p.prix)} · il te reste ${fM(r.budget)}`));
  const grille = el("div", {class: "cartes-grille ouverture-grille"});
  r.cartes.forEach((x, i) => { const c = x.carte; const k = carteMarche(c, {vitrine: true}); k.classList.add("revele"); k.style.animationDelay = (i * 0.25) + "s";
    k.append(el("div", {class: "cj-cote"}, `cote ${fM(x.cote)} · n° ${x.numero}`)); grille.append(k); });
  box.append(grille, el("div", {class: "actions"}, el("button", {onclick: () => { dlg.close(); montrer("equipe"); }}, "Gérer mon club"), el("button", {class: "primaire", onclick: () => { dlg.close(); rendrePacks(); }}, "Encore un pack")));
  dlg.append(box); dlg.showModal();
}
async function rendreEncheres(filtrePid = null) {
  const d = await api("/marche"); G.ventes = d.ventes;
  const norm = s => (s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
  const q = norm($("#e-nom").value), fam = $("#e-fam").value, miennes = $("#e-miennes").checked, tri = $("#e-tri").value;
  let rows = d.ventes.filter(v => v.carte && (!filtrePid || v.player_id === filtrePid) && (!fam || v.carte.fam === fam) && (!miennes || v.mienne || v.je_mene) && (!q || norm(v.carte.nom).includes(q) || norm(v.carte.club).includes(q)));
  const cle = {fin: v => new Date(v.fin) - 0, prix: v => -(v.meilleure_offre ?? v.prix_depart), ovr: v => -v.carte.ovr, cote: v => -(v.cote || 0)}[tri];
  rows.sort((a, b) => cle(a) - cle(b));
  $("#encheres-compteur").textContent = `${rows.length} vente${rows.length > 1 ? "s" : ""} en cours`;
  const L = $("#encheres-liste"); L.replaceChildren();
  if (!rows.length) L.append(el("p", {class: "info"}, "Aucune vente en cours. Les cartes se vendent depuis ton club (écran Équipe) : mise à prix, achat immédiat, durée."));
  for (const v of rows) L.append(ligneVente(v));
}
function ligneVente(v) {
  const c = v.carte; const cour = v.meilleure_offre ?? null;
  const l = el("div", {class: "vente" + (v.mienne ? " mienne" : "") + (v.je_mene ? " mene" : "")});
  l.style.setProperty("--clubc", c.couleur);
  const k = carteMarche(c, {vitrine: true}); k.classList.add("petite");
  const infos = el("div", {class: "vente-infos"},
    el("div", {class: "etiq"}, `Vendeur : ${v.vendeur} · exemplaire n° ${v.numero} · cote ${fM(v.cote)}`),
    el("div", {class: "vente-prix"}, el("div", {}, el("span", {class: "etiq"}, cour ? "Meilleure offre" : "Mise à prix"), el("b", {class: "anton"}, fM(cour ?? v.prix_depart))),
      v.prix_immediat ? el("div", {}, el("span", {class: "etiq"}, "Achat immédiat"), el("b", {class: "anton"}, fM(v.prix_immediat))) : null,
      el("div", {}, el("span", {class: "etiq"}, "Fin"), el("b", {class: "anton"}, resteTxt(v.fin)))),
    v.je_mene ? el("div", {class: "compteur", style: "color:var(--vert)"}, "Tu mènes l'enchère") : null);
  const acts = el("div", {class: "vente-actions"});
  if (v.mienne) {
    acts.append(el("span", {class: "compteur"}, cour ? "Une offre est faite, la vente ira à son terme." : "Ta vente."),
      el("button", {disabled: !!cour, onclick: async () => { try { await api("/marche/annuler", {enchere_id: v.enchere_id}); toast("Vente annulée"); rendreEncheres(); } catch (e) { toast(e.message); } }}, "Retirer"));
  } else {
    const mini = cour ? Math.round(cour * 1.05 * 100 + 0.5) / 100 : v.prix_depart;
    const inp = el("input", {type: "number", step: "0.1", min: String(mini), value: String(mini), style: "width:110px"});
    acts.append(inp, el("button", {class: "achat", onclick: async () => { try { const r = await api("/marche/encherir", {enchere_id: v.enchere_id, montant: +inp.value}); toast(`Offre de ${fM(r.montant)} placée`); await rafraichir(false); rendreEncheres(); } catch (e) { toast(e.message); } }}, "Enchérir"));
    if (v.prix_immediat) acts.append(el("button", {class: "achat primaire", onclick: async () => { try { const r = await api("/marche/acheter", {enchere_id: v.enchere_id}); toast(`${c.nom} acheté ${fM(r.prix)}`); await rafraichir(false); rendreEncheres(); } catch (e) { toast(e.message); } }}, "Acheter " + fM(v.prix_immediat)));
  }
  l.append(k, infos, acts);
  return l;
}
function dialogueVente(x) {
  const c = x.carte; const dlg = $("#fiche"); dlg.replaceChildren();
  const cote = x.cote || 1;
  const dep = el("input", {type: "number", step: "0.1", min: "0.1", value: String(Math.round(cote * 0.8 * 10) / 10)});
  const imm = el("input", {type: "number", step: "0.1", min: "0.1", value: String(Math.round(cote * 1.2 * 10) / 10)});
  const dur = el("select", {}, ...(G.packs?.durees || [6, 12, 24, 48]).map(h => el("option", {value: String(h), selected: h === 24 ? "selected" : null}, h + " heures")));
  const box = el("div", {class: "fiche"}, el("h3", {class: "anton"}, "Mettre en vente"), el("p", {class: "compteur"}, `${c.nom} · exemplaire n° ${x.numero} · cote ${fM(cote)} · acheté ${fM(x.prix_achat)}`),
    el("form", {class: "form-vente", onsubmit: async e => { e.preventDefault(); try { await api("/marche/vendre", {exemplaire_id: x.exemplaire_id, prix_depart: +dep.value, prix_immediat: imm.value ? +imm.value : null, duree_h: +dur.value}); toast("Carte mise en vente"); dlg.close(); await rafraichir(false); rendreEquipe(); } catch (err) { toast(err.message); } }},
      el("label", {}, "Mise à prix (M€)", dep), el("label", {}, "Achat immédiat (M€, facultatif)", imm), el("label", {}, "Durée", dur),
      el("p", {class: "compteur"}, `La banque prend ${Math.round((G.packs?.commission ?? 0.05) * 100)} % à la vente. Une carte en vente quitte l'effectif.`),
      el("div", {class: "actions"}, el("button", {type: "button", class: "discret", onclick: () => dlg.close()}, "Annuler"), el("button", {type: "submit", class: "primaire"}, "Mettre en vente"))));
  dlg.append(box); dlg.showModal();
}
async function actionClub(chemin, corps, msg) {
  try { await api(chemin, corps); if (msg) toast(msg); await rafraichir(false); if (G.ecran === "equipe") rendreEquipe(); if (G.ecran === "packs") rendrePacks(); } catch (e) { toast(e.message); }
}
function rendreMarche() {
  const mf = $("#marche-ferme"); mf.hidden = !!G.saison.courante;
  mf.textContent = "Aucune journée ouverte sur cette base : la saison est terminée, ou le serveur a été lancé sur la mauvaise base (utiliser  py web/app/lancer.py).";
  const norm = s => (s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
  const q = norm($("#f-nom").value), fam = $("#f-fam").value, ligue = $("#f-ligue").value, tri = $("#f-tri").value;
  const abord = $("#f-abord").checked, miens = $("#f-miens").checked;
  let rows = G.cartes.filter(c => {
    if (fam && c.fam !== fam) return false; if (ligue && c.ligue !== ligue) return false;
    if (abord && !ventesDe(c.id).length) return false; if (miens && !G.equipe.effectif[c.id]) return false;
    if (q && !norm(c.nom).includes(q) && !norm(c.club).includes(q)) return false; return true;
  });
  const cle = {ovr: c => -c.ovr, prix: c => -c.prix, rapport: c => -(c.ovr - 40) / Math.max(c.prix, 0.1), forme: c => -formeMoy(c), age: c => c.age || 99, part: c => -c.part, nom: c => 0}[tri];
  rows.sort((a, b) => cle(a) - cle(b) || a.nom.localeCompare(b.nom));
  $("#marche-compteur").textContent = `${rows.length} cartes`;
  const ME = $("#marche-effectif"); ME.replaceChildren(el("span", {class: "etiq"}, "Effectif"), el("b", {class: "num"}, `${idsEffectif().length} / ${TAILLE}`),
    ...FAMS.map(f => el("span", {class: "quota" + (nbFam(f) >= QUOTA[f] ? " plein" : "")}, `${FAM_COURT[f]} `, el("b", {}, `${nbFam(f)}/${QUOTA[f]}`))));
  document.querySelectorAll(".vue button").forEach(b => { if (b.dataset.vue === marcheVue) b.setAttribute("aria-current", "page"); else b.removeAttribute("aria-current"); });
  const L = $("#marche-liste"); L.replaceChildren(); L.className = marcheVue === "cartes" ? "cartes-grille" : "liste";
  for (const c of rows.slice(0, marcheLimite)) L.append(marcheVue === "cartes" ? carteMarche(c) : ligneCarte(c));
  $("#marche-plus").hidden = rows.length <= marcheLimite;
}
function boutonAchatVente(c, mien) {
  const n = ventesDe(c.id).length;
  return el("button", {class: "achat" + (n ? " primaire" : ""), disabled: !n, onclick: e => { e.stopPropagation(); if (n) allerAuxVentes(c.id); }}, n ? `${n} vente${n > 1 ? "s" : ""}` : "Aucune vente");
}
async function allerAuxVentes(pid) { $("#e-nom").value = carte(pid)?.nom || ""; await montrer("encheres"); }
// the card itself: an escutcheon (clip-path) in the club colour — OVR, position, age,
// flag, shirt number, portrait, then name, club, form, price and the button
function carteMarche(c, opts = {}) {
  const mien = !opts.vitrine && !!G.equipe?.effectif[c.id];
  const k = el("div", {class: "cartej" + (mien ? " mienne" : ""), tabindex: opts.vitrine ? null : "0", role: opts.vitrine ? null : "button",
    onclick: opts.vitrine ? null : () => ouvrirFiche(c.id), onkeydown: opts.vitrine ? null : e => { if (e.key === "Enter") ouvrirFiche(c.id); }});
  k.style.setProperty("--clubc", c.couleur);
  const delta = mien ? c.prix - G.equipe.effectif[c.id] : 0;
  const haut = el("div", {class: "cj-haut"},
    el("div", {class: "cj-ovr anton" + (c.ovr >= 80 ? " haut" : "")}, String(c.ovr)),
    el("div", {class: "cj-pos"}, el("span", {class: "fam " + c.fam}, FAM_COURT[c.fam])),
    c.age ? el("div", {class: "cj-age"}, ageTxt(c)) : null,
    el("img", {class: "cj-logo", src: `/images/logos/${c.team_id}.png`, alt: "", loading: "lazy", onerror: e => e.target.remove()}),
    c.pays ? el("div", {class: "cj-drapeau", title: c.pays}, drapeau(c.pays)) : null,
    c.numero ? el("div", {class: "cj-num"}, "#" + c.numero) : null,
    recrue(c) ? el("div", {class: "cj-recrue", title: `Entré dans le jeu à la journée ${c.arrivee}`}, "NOUVEAU") : null,
    vignetteDe(c));
  const corps = el("div", {class: "cj-corps"},
    el("div", {class: "nom", title: c.nom}, c.nom),
    el("div", {class: "sous"}, `${c.club} · ${POSTE_COURT[c.poste] || c.poste}`),
    el("div", {class: "cj-milieu"}, barresForme(c), c.part > 0 ? el("span", {class: "part"}, Math.round(c.part * 100) + " %") : null),
    el("div", {class: "cj-pied"}, el("span", {class: "prix num"}, fM(c.prix)),
      mien && Math.abs(delta) >= 0.005 ? el("span", {class: "delta " + (delta > 0 ? "plus" : "moins")}, fM(delta, true)) : null),
    opts.vitrine ? null : boutonAchatVente(c, mien));
  k.append(el("div", {class: "crest-bord"}, el("div", {class: "crest-corps"}, haut, corps)));
  return k;
}
// A card that entered the game during the season (mercato): shown for the
// three gameweeks after it opened, which is when nobody knows it yet.
function recrue(c) {
  const j = G.saison?.derniere?.numero ?? 0;
  return c.arrivee > 0 && j - c.arrivee < 3;
}
function vignetteDe(c) {
  const v = el("div", {class: "vign"});
  const img = el("img", {src: `/images/joueurs/${c.id}.png`, alt: "", loading: "lazy"});
  img.addEventListener("error", () => { img.remove(); v.append(el("span", {class: "init"}, (c.nom || "?").split(" ").slice(0, 2).map(w => w[0]).join(""))); });
  v.append(img); return v;
}
function ligneCarte(c) {
  const mien = !!G.equipe.effectif[c.id];
  const l = el("div", {class: "ligne", tabindex: "0", role: "button", onclick: () => ouvrirFiche(c.id), onkeydown: e => { if (e.key === "Enter") ouvrirFiche(c.id); }});
  l.style.setProperty("--clubc", c.couleur);
  const delta = mien ? c.prix - G.equipe.effectif[c.id] : 0;
  l.append(vignette(c.id),
    el("div", {class: "qui"}, el("div", {class: "nom"}, c.nom), el("div", {class: "sous"}, `${c.club} · ${POSTE_COURT[c.poste] || c.poste}${c.age ? " · " + c.age + " ans" : ""}${c.part > 0 ? " · " + Math.round(c.part * 100) + " % des équipes" : ""}`)),
    barresForme(c),
    el("div", {class: "ovr num" + (c.ovr >= 80 ? " haut" : "")}, String(c.ovr)),
    el("div", {class: "prix num"}, fM(c.prix), mien && Math.abs(delta) >= 0.005 ? el("div", {class: "delta " + (delta > 0 ? "plus" : "moins")}, fM(delta, true)) : null));
  l.append(boutonAchatVente(c, mien));
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
  rendreClub();
}
async function rendreClub() {
  const d = await api("/club"); G.club = d.cartes;
  const R = $("#club-liste"); R.replaceChildren();
  const eff = d.cartes.filter(x => x.dans_effectif), res = d.cartes.filter(x => !x.dans_effectif);
  $("#club-compteur").textContent = `${eff.length} / ${d.effectif_max} dans l'effectif · ${res.length} / ${d.reserve_max} en réserve`;
  const ligne = x => {
    const c = x.carte; const l = el("div", {class: "ligne club-ligne" + (x.enchere_id ? " en-vente" : "")}); l.style.setProperty("--clubc", c.couleur);
    const delta = (x.cote || 0) - x.prix_achat;
    l.append(vignette(c.id), el("div", {class: "qui", tabindex: "0", onclick: () => ouvrirFiche(c.id)}, el("div", {class: "nom"}, c.nom, el("span", {class: "compteur"}, ` n° ${x.numero}`)), el("div", {class: "sous"}, `${c.club} · acheté ${fM(x.prix_achat)} · cote ${fM(x.cote)} `, el("span", {class: "delta " + (delta >= 0 ? "plus" : "moins")}, fM(delta, true)))),
      el("span", {class: "fam " + c.fam}, FAM_COURT[c.fam]), el("div", {class: "ovr num" + (c.ovr >= 80 ? " haut" : "")}, String(c.ovr)));
    const acts = el("div", {class: "club-actions"});
    if (x.enchere_id) acts.append(el("span", {class: "compteur"}, "en vente"), el("button", {onclick: () => montrer("encheres")}, "Voir"));
    else {
      acts.append(x.dans_effectif
        ? el("button", {title: "Mettre en réserve", onclick: () => actionClub("/club/aligner", {exemplaire_id: x.exemplaire_id, dans_effectif: false}, `${c.nom} en réserve`)}, "Réserve")
        : el("button", {class: "primaire", title: "Aligner dans l'effectif", disabled: !G.equipe.marche_ouvert, onclick: () => actionClub("/club/aligner", {exemplaire_id: x.exemplaire_id, dans_effectif: true}, `${c.nom} dans l'effectif`)}, "Aligner"));
      acts.append(el("button", {class: "vente", onclick: () => dialogueVente(x)}, "Vendre"),
        el("button", {class: "discret", title: `Vendre à la banque : ${fM((G.packs?.rachat ?? 0.4) * (x.cote || 0))}`, onclick: () => { if (confirm(`Vendre ${c.nom} à la banque pour ${fM((G.packs?.rachat ?? 0.4) * (x.cote || 0))} ? La carte est détruite.`)) actionClub("/club/banque", {exemplaire_id: x.exemplaire_id}, "Vendu à la banque"); }}, "Banque"));
    }
    l.append(acts); return l;
  };
  R.append(el("div", {class: "etiq"}, "Effectif"), ...(eff.length ? eff.map(ligne) : [el("p", {class: "compteur"}, "Personne. Ouvre des packs, puis aligne tes cartes ici.")]));
  R.append(el("div", {class: "etiq", style: "margin-top:12px"}, "Réserve"), ...(res.length ? res.map(ligne) : [el("p", {class: "compteur"}, "Réserve vide.")]));
  if (!G.packs) { try { G.packs = await api("/packs"); } catch (e) {} }
}
function slotEl(s, fam) {
  const i = C.slots[s];
  if (i === null) return el("div", {class: "slot vide", tabindex: "0", onclick: () => { const cands = C.banc.filter(x => carte(x).fam === fam).sort((a, b) => ovr(b) - ovr(a)); if (!cands.length) { toast(`Aucun ${NOM_FAM[fam].toLowerCase()} sur le banc`); return; } C.banc = C.banc.filter(x => x !== cands[0]); C.slots[s] = cands[0]; rendreEquipe(false); }}, el("div", {class: "mini"}, el("div", {}, el("div", {class: "o"}, "+"), el("div", {class: "n"}, NOM_FAM[fam]))));
  const c = carte(i); const d = el("div", {class: "slot", tabindex: "0", onclick: () => menuSlot(s), onkeydown: e => { if (e.key === "Enter") menuSlot(s); }});
  d.style.setProperty("--clubc", c.couleur);
  d.append(el("div", {class: "mini"}, el("div", {},
    el("div", {class: "mh"}, el("div", {class: "o num" + (c.ovr >= 80 ? " haut" : "")}, String(c.ovr)), vignette(i)),
    el("div", {class: "n"}, c.nom.split(" ").slice(-1)[0]))));
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

// ---- match en face à face ----
const RES_TXT = {V: "Victoire", N: "Match nul", D: "Défaite"};
function scoreLigne(m) { return m.score ? `${m.score[0]} – ${m.score[1]}` : "—"; }
async function rendreMatch() {
  const d = await api("/match");
  const j = G.saison.courante;
  const P1 = $("#match-prochain"); P1.replaceChildren();
  if (d.a_venir) {
    const a = d.a_venir;
    P1.append(el("div", {class: "tete"}, el("h2", {class: "anton"}, `Journée ${a.journee}`), el("span", {class: "compteur"}, j && j.verrouillee ? "verrouillée, les matchs se jouent" : "à venir")),
      el("div", {class: "affiche"},
        el("div", {class: "equipe-aff moi"}, el("div", {class: "etiq"}, "Toi"), el("b", {}, G.equipe.nom), el("span", {class: "elo-chip"}, "Elo " + d.elo)),
        el("div", {class: "vs anton"}, "VS"),
        el("div", {class: "equipe-aff"}, el("div", {class: "etiq"}, a.adversaire.pseudo), el("b", {}, a.adversaire.equipe), el("span", {class: "elo-chip"}, "Elo " + a.adversaire.elo))),
      el("p", {class: "info"}, "Le match se joue sur les vraies actions de vos deux onze pendant la journée : chaque but réel est une occasion, trois tirs cadrés non convertis en font une de plus, et la défense adverse en annule une tous les 70 points défensifs. Les buts de ton capitaine ne s'annulent jamais."));
  } else {
    P1.append(el("div", {class: "tete"}, el("h2", {class: "anton"}, j ? `Journée ${j.numero}` : "Saison terminée")),
      el("p", {class: "info"}, d.equipes < 2 ? "Tu es seul dans la ligue pour l'instant : le premier autre manager inscrit sera ton adversaire." : "Pas d'adversaire cette journée (nombre impair d'équipes) : tu es exempt."));
  }
  const P2 = $("#match-dernier"); P2.replaceChildren();
  const dernier = d.joues[0];
  if (dernier) {
    const m = await api("/match/" + dernier.journee);
    const f = m.feuille;
    P2.append(el("div", {class: "tete"}, el("h2", {class: "anton"}, `Journée ${m.journee}`), el("span", {class: "badge-res " + m.resultat}, RES_TXT[m.resultat]),
        el("span", {class: "compteur"}, `Elo ${m.elo_avant} → ${m.elo_apres}`)),
      el("div", {class: "tableau-score"},
        el("div", {class: "eq"}, el("b", {}, G.equipe.nom)),
        el("div", {class: "score anton"}, `${m.score[0]} – ${m.score[1]}`),
        el("div", {class: "eq droite"}, el("b", {}, m.adversaire.equipe), el("div", {class: "compteur"}, m.adversaire.pseudo))));
    if (f) {
      P2.append(el("div", {class: "poss"}, el("span", {}, f.possession[0] + " %"), el("div", {class: "barre-poss"}, el("i", {style: `width:${f.possession[0]}%`})), el("span", {}, f.possession[1] + " %")), el("div", {class: "etiq", style: "text-align:center"}, "Possession"));
      const chances = (c, coteCls) => el("div", {class: "chances " + coteCls}, ...(c.length ? c.map(x => el("div", {class: "chance" + (x.annule ? " annulee" : "")},
        el("span", {class: "ico"}, x.annule ? "✖" : x.but ? "⚽" : "◎"), el("span", {}, `${x.nom} (${f1(x.note)})`, x.annule ? el("i", {}, ` annulé${x.par ? " par " + x.par : ""}`) : x.but ? null : el("i", {}, " occasion")))) : [el("span", {class: "compteur"}, "aucune occasion")]));
      P2.append(el("div", {class: "deux-cotes"}, chances(f.a.chances, "g"), chances(f.b.chances, "d")));
      const t = el("table", {class: "totaux"}); const tb = el("tbody");
      const LAB = Object.fromEntries([["buts","Buts réels"],["tirs","Tirs"],["cadres","Tirs cadrés"],["xg","xG"],["gom","Grosses occasions manquées"],["occ","Occasions créées"],["passes","Passes réussies"],["p3","Passes dernier tiers"],["surf","Ballons dans la surface"],["drib","Dribbles réussis"],["tacles","Tacles"],["int","Interceptions"],["deg","Dégagements"],["blocs","Tirs bloqués"],["arrets","Arrêts"],["evites","Buts évités (xGOT)"],["enc","Buts encaissés (réels)"]]);
      for (const k of Object.keys(LAB)) tb.append(el("tr", {}, el("td", {class: "num g"}, String(f.a.totaux[k] ?? 0)), el("td", {class: "lib"}, LAB[k]), el("td", {class: "num d"}, String(f.b.totaux[k] ?? 0))));
      tb.append(el("tr", {class: "def"}, el("td", {class: "num g"}, `${f.a.defense} pts · ${f.b.annulations} annulation${f.b.annulations > 1 ? "s" : ""} subie${f.b.annulations > 1 ? "s" : ""}`), el("td", {class: "lib"}, "Travail défensif"), el("td", {class: "num d"}, `${f.b.defense} pts · ${f.a.annulations} subie${f.a.annulations > 1 ? "s" : ""}`)));
      t.append(tb); P2.append(el("div", {class: "etiq", style: "margin-top:14px"}, "La feuille de match"), el("div", {class: "tableau"}, t));
      const onze = (jrs, cls) => el("div", {class: "onze-liste " + cls}, ...jrs.map(x => el("div", {class: "ligne-onze", tabindex: "0", onclick: () => ouvrirFiche(x.pid)},
        vignette(x.pid), el("div", {class: "qui"}, el("div", {class: "nom"}, x.nom + (x.capitaine ? " ©" : "")), el("div", {class: "sous"}, `${x.buts ? x.buts + " but" + (x.buts > 1 ? "s" : "") + " · " : ""}${x.pd ? x.pd + " passe" + (x.pd > 1 ? "s" : "") + " déc. · " : ""}xG ${f1(x.xg)} · déf. ${Math.round(x.defense)}`)),
        el("div", {class: "notes"}, ...x.notes.map(n => el("span", {class: "note " + (n >= 7 ? "b" : n < 5 ? "m" : "")}, f1(n)))))));
      P2.append(el("div", {class: "etiq", style: "margin-top:14px"}, "Les deux onze"), el("div", {class: "deux-cotes"}, onze(f.a.joueurs, "g"), onze(f.b.joueurs, "d")));
    }
  } else P2.append(el("p", {class: "info"}, "Aucun match joué pour l'instant. Le premier se jouera à la clôture de la journée."));
  const tb = $("#elo tbody"); tb.replaceChildren();
  for (const r of await api("/elo")) tb.append(el("tr", {class: r.equipe_id === G.equipe.equipe_id ? "moi" : ""}, el("td", {class: r.rang <= 3 ? "podium p" + r.rang : ""}, String(r.rang)), el("td", {}, r.equipe, el("div", {class: "compteur"}, r.pseudo)), el("td", {class: "num"}, String(r.elo)), el("td", {class: "num"}, `${r.v}·${r.n}·${r.d}`), el("td", {class: "num"}, `${r.bp}:${r.bc}`)));
  const tm = $("#mes-matchs tbody"); tm.replaceChildren();
  for (const m of d.joues) tm.append(el("tr", {}, el("td", {}, "J" + m.journee), el("td", {}, m.adversaire.equipe), el("td", {class: "num res-" + m.resultat}, scoreLigne(m)), el("td", {class: "num"}, `${m.elo_apres > m.elo_avant ? "+" : ""}${m.elo_apres - m.elo_avant}`)));
  if (!d.joues.length) tm.append(el("tr", {}, el("td", {colspan: "4", class: "compteur"}, "—")));
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
        el("div", {class: "tuile"}, el("div", {class: "etiq"}, "Gain"), el("b", {class: "num"}, fM(det.gain, true))),
        el("div", {class: "tuile"}, el("div", {class: "etiq"}, "Entrés du banc"), el("b", {class: "num"}, String(det.onze.filter(p => !(det.titulaires || []).includes(p)).length)))));
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
  for (const r of res) tb.append(el("tr", {}, el("td", {}, "J" + r.journee), el("td", {class: "num"}, f1(r.score)), el("td", {class: "num"}, fM(r.gain, true)), el("td", {class: "num"}, String(r.rang))));
}

// ---- classement et ligues ----
async function rendreClassement() {
  const cl = await api("/classement"); const tb = $("#classement tbody"); tb.replaceChildren();
  for (const r of cl) tb.append(el("tr", {class: r.equipe_id === G.equipe.equipe_id ? "moi" : ""}, el("td", {class: r.rang <= 3 ? "podium p" + r.rang : ""}, String(r.rang)), el("td", {}, r.equipe), el("td", {}, r.pseudo), el("td", {class: "num"}, f1(r.points)), el("td", {class: "num"}, r.derniere == null ? "—" : f1(r.derniere)), el("td", {class: "num"}, fM(r.patrimoine))));
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
  A.append(el("p", {class: "info"}, `${e.cartes} cartes · ${e.equipes} équipes · OVR sur le barème de saison : ${e.bareme?.reguliers ?? "?"} réguliers, cloche ${e.bareme?.mu ?? 65} ± ${e.bareme?.sigma ?? 10}, borne ±${e.bareme?.borne ?? 10}`));
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
for (const id of ["e-nom", "e-fam", "e-tri", "e-miennes"]) $("#" + id).addEventListener("input", () => rendreEncheres());
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
    el("div", {class: "fiche-ligne"}, el("span", {class: "fam " + d.fam}, FAM_COURT[d.fam]), el("span", {}, POSTE_COURT[d.poste] || d.poste), d.age ? el("span", {}, `· ${d.age} ans`) : null, d.pays ? el("span", {title: d.pays}, `· ${drapeau(d.pays)} ${d.pays}`) : null, d.numero ? el("span", {}, `· n° ${d.numero}`) : null),
    el("div", {class: "compteur"}, `${d.matchs} matchs, ${d.minutes} min cette saison · ${Math.round(d.part * 100)} % des équipes`),
    el("div", {style: "display:flex;gap:14px;align-items:baseline;margin-top:6px"}, el("div", {class: "ovr num" + (d.ovr >= 80 ? " haut" : ""), style: "font-size:40px"}, String(d.ovr)), el("div", {class: "prix num", style: "font-size:22px"}, fM(d.prix))));
  const dep = d.valeur_base != null ? `${fM(d.valeur_base)} à OVR ${d.ovr_base}` : "—";
  cote.append(el("div", {class: "compteur", style: "margin-top:6px"}, `Départ de saison : ${dep}`),
    el("div", {class: "compteur"}, d.valeur_marche != null ? `Valeur marchande réelle (FotMob) : ${fM(d.valeur_marche)}` : "Valeur marchande réelle inconnue : prix estimé d'après l'OVR"),
    el("div", {class: "compteur"}, `L'OVR est la qualité sur la saison, borné à ±10 du départ. Le prix double tous les +8 OVR, et monte avec la part des équipes qui possèdent la carte.`));
  box.append(el("div", {class: "fiche-haut"}, img, cote));
  const axes = d.fam === "GK" ? AXES.gardien : AXES.champ; const A = el("div", {class: "attrs"});
  for (const ax of axes) { const val = d.attributs[ax] ?? 40; A.append(el("div", {class: "attr"}, el("span", {}, (d.poste === "Gardien" && ATTR_NOMS_GARDIEN[ax]) || ATTR_NOMS[ax]), el("div", {class: "jauge"}, el("i", {class: val >= 80 ? "haut" : "", style: `width:${(val - 40) / 59 * 100}%`})), el("b", {class: "num"}, String(val)))); }
  box.append(el("div", {class: "etiq"}, "Attributs de la saison"), A);
  box.append(el("div", {class: "etiq"}, "Dernières prestations"), el("div", {class: "notes"}, ...(d.prestations.length ? d.prestations.slice(0, 8).map(p => el("span", {class: "note " + (p.note >= 7 ? "b" : p.note < 5 ? "m" : ""), title: `J${p.numero} · ${p.competition}`}, `${f1(p.note)} · ${Math.round(p.minutes)}'`)) : [el("span", {class: "compteur"}, "aucun match noté cette saison")])));
  if (d.historique.length > 1) box.append(el("div", {class: "etiq", style: "margin-top:10px"}, "Prix par journée"), sparkline(d.historique.map(h => h.prix), fM));
  const acts = el("div", {class: "actions"});
  const nv = ventesDe(id).length;
  if (G.equipe.effectif[id]) { const dl = d.prix - G.equipe.effectif[id]; acts.append(el("span", {class: "compteur", style: "margin-right:auto"}, `dans ton effectif · acheté ${fM(G.equipe.effectif[id])} · ${fM(dl, true)}`)); }
  acts.append(el("button", {class: "achat" + (nv ? " primaire" : ""), disabled: !nv, onclick: () => { dlg.close(); allerAuxVentes(id); }}, nv ? `${nv} vente${nv > 1 ? "s" : ""} en cours` : "Aucune vente en cours"));
  acts.append(el("button", {class: "discret", onclick: () => dlg.close()}, "Fermer"));
  box.append(acts); dlg.append(box); dlg.showModal();
}
function sparkline(vals, fmt = f1) {
  const W = 480, H = 60, lo = Math.min(...vals), hi = Math.max(...vals), pad = 6;
  const x = k => pad + k * (W - 2 * pad) / Math.max(1, vals.length - 1), y = v => hi === lo ? H / 2 : H - pad - (v - lo) * (H - 2 * pad) / (hi - lo);
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg"); svg.setAttribute("viewBox", `0 0 ${W} ${H}`); svg.setAttribute("class", "spark");
  svg.innerHTML = `<polyline points="${vals.map((v, k) => `${x(k).toFixed(1)},${y(v).toFixed(1)}`).join(" ")}" fill="none" stroke="var(--or)" stroke-width="2"/><circle cx="${x(vals.length - 1).toFixed(1)}" cy="${y(vals[vals.length - 1]).toFixed(1)}" r="3.5" fill="var(--or)"/><text x="${pad}" y="${H - 1}" font-size="10" fill="var(--sourd)" font-family="Barlow Condensed">${fmt(vals[0])}</text><text x="${W - pad}" y="10" text-anchor="end" font-size="10" fill="var(--sourd)" font-family="Barlow Condensed">${fmt(vals[vals.length - 1])}</text>`;
  return svg;
}

(async () => {
  try {
    const s = await api("/saison"); TAILLE = s.taille_effectif; FORMATIONS = s.formations; LIMITES = s.limites;
    const moi = await api("/moi"); connecte(moi);
    if (moi.connecte) { const h = location.hash.replace("#", ""); await montrer(["packs", "encheres", "marche", "equipe", "match", "journee", "classement", "admin"].includes(h) ? h : (idsEffectif().length ? "equipe" : "packs")); }
  } catch (e) { toast("Serveur injoignable : " + e.message); }
})();

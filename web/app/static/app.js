"use strict";
// FootballLife — front-end of web/app/serveur.py.  Vanilla JS, one file.
// State lives on the server; this page only holds what it just fetched.

const QUOTA = {GK: 2, DEF: 5, MID: 5, FWD: 3};
const FAMS = ["GK", "DEF", "MID", "FWD"];
const NOM_FAM = {GK: "Gardien", DEF: "Défenseur", MID: "Milieu", FWD: "Attaquant"};
const PLURIEL = {GK: "gardiens", DEF: "défenseurs", MID: "milieux", FWD: "attaquants"};
const POSTE_COURT = {"Gardien":"Gardien","Defenseur central":"Défenseur central","Lateral":"Latéral","Lateral gauche":"Latéral gauche","Lateral droit":"Latéral droit","Milieu defensif":"Milieu défensif","Milieu relayeur":"Milieu relayeur","Milieu offensif":"Meneur","Ailier":"Ailier","Ailier droit":"Ailier droit","Ailier gauche":"Ailier gauche","Buteur":"Buteur"};
// Un poste sans son côté : « Lateral gauche » → « Lateral ».
const posteBase = p => (p || "").replace(/ (gauche|droit)$/, "");
const ATTR_NOMS = {FIN:"Finition",CRE:"Création",PRO:"Progression",DEF:"Défense",DRI:"Dribble",CON:"Conservation",ARR:"Arrêts",EVI:"Buts évités",SOR:"Sorties",REL:"Jeu long",BUT:"Imbattabilité"};
const ATTR_NOMS_GARDIEN = {PRO:"Jeu court"};   // a keeper's PRO axis is his short passing (jeu/bareme.py)
const PIEDS = {gauche: "gaucher", droit: "droitier", deux: "ambidextre"};
const AXES = {champ:["FIN","CRE","PRO","DEF","DRI","CON"], gardien:["ARR","EVI","SOR","REL","BUT","PRO"]};
const f1 = x => (Math.round((+x || 0) * 10) / 10).toFixed(1);
// money: every amount is in M€ (0.1 = 100 k€)
// Les montants sont en M€.  Le palier du milliard sert au compte de
// démonstration, qui démarre à dix : « 10000,0 M€ » ne se lit pas.
const fM = (x, signe = false) => { const v = +x || 0, a = Math.abs(v), s = v < 0 ? "−" : signe && v > 0 ? "+" : "";
  if (a < 1) return s + Math.round(a * 1000) + " k€";
  if (a < 10) return s + a.toFixed(2).replace(".", ",") + " M€";
  if (a < 1000) return s + (Math.round(a * 10) / 10).toFixed(1).replace(".", ",") + " M€";
  return s + (a / 1000).toFixed(2).replace(".", ",") + " Md€"; };

// ISO-3 (FotMob) -> ISO-2, for the flag emoji on the card
const ISO2 = {FRA:"FR",ENG:"GB",SCO:"GB",WAL:"GB",NIR:"GB",IRL:"IE",ESP:"ES",ITA:"IT",GER:"DE",POR:"PT",NED:"NL",BEL:"BE",SUI:"CH",AUT:"AT",DEN:"DK",SWE:"SE",NOR:"NO",FIN:"FI",ISL:"IS",POL:"PL",CZE:"CZ",SVK:"SK",HUN:"HU",ROU:"RO",BUL:"BG",SRB:"RS",CRO:"HR",SVN:"SI",BIH:"BA",MNE:"ME",MKD:"MK",ALB:"AL",KOS:"XK",GRE:"GR",TUR:"TR",UKR:"UA",RUS:"RU",BLR:"BY",GEO:"GE",ARM:"AM",AZE:"AZ",KAZ:"KZ",ISR:"IL",CYP:"CY",MLT:"MT",LUX:"LU",LTU:"LT",LVA:"LV",EST:"EE",MDA:"MD",BRA:"BR",ARG:"AR",URU:"UY",PAR:"PY",CHI:"CL",COL:"CO",PER:"PE",ECU:"EC",VEN:"VE",BOL:"BO",MEX:"MX",USA:"US",CAN:"CA",JAM:"JM",CRC:"CR",HON:"HN",PAN:"PA",GUA:"GT",SLV:"SV",HAI:"HT",CUB:"CU",DOM:"DO",TRI:"TT",CUW:"CW",SUR:"SR",MAR:"MA",ALG:"DZ",TUN:"TN",EGY:"EG",SEN:"SN",CIV:"CI",CMR:"CM",NGA:"NG",GHA:"GH",MLI:"ML",GUI:"GN",BFA:"BF",COD:"CD",CGO:"CG",GAB:"GA",ANG:"AO",MOZ:"MZ",ZAM:"ZM",ZIM:"ZW",RSA:"ZA",KEN:"KE",UGA:"UG",TAN:"TZ",ETH:"ET",SUD:"SD",TOG:"TG",BEN:"BJ",NIG:"NE",GAM:"GM",SLE:"SL",LBR:"LR",CPV:"CV",GNB:"GW",EQG:"GQ",CTA:"CF",CHA:"TD",MTN:"MR",LBY:"LY",COM:"KM",MAD:"MG",BDI:"BI",RWA:"RW",JPN:"JP",KOR:"KR",CHN:"CN",AUS:"AU",NZL:"NZ",IRN:"IR",IRQ:"IQ",KSA:"SA",QAT:"QA",UAE:"AE",UZB:"UZ",IND:"IN",THA:"TH",VIE:"VN",PHI:"PH",IDN:"ID",MAS:"MY",SYR:"SY",JOR:"JO",LBN:"LB",PLE:"PS"};
const drapeau = code => { const c = ISO2[code] || (code && code.length === 2 ? code : null); if (!c) return ""; return String.fromCodePoint(...[...c.toUpperCase()].map(ch => 0x1F1E6 + ch.charCodeAt(0) - 65)); };
const ageTxt = c => c.age ? `${c.age} ans` : "";
// pour chercher : minuscules, sans accents
const norm = s => (s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
const FAM_COURT = {GK: "GB", DEF: "DÉF", MID: "MIL", FWD: "ATT"};

// ---- état local (miroir de ce que le serveur a renvoyé) ----
const G = {moi: null, saison: null, cartes: [], idx: new Map(), equipe: null, compo: null, ecran: "connexion", ventes: [], club: [], packs: null};
const ventesDe = id => G.ventes.filter(v => v.player_id === id);
let TAILLE = 18, BANC_MAX = 7, FORMATIONS = {"4-3-3": [1,4,3,3]}, LIMITES = {GK: [1,1], DEF: [3,5], MID: [2,5], FWD: [1,4]};
let RANGS = {"4-3-3": [["Gardien"], ["Lateral gauche","Defenseur central","Defenseur central","Lateral droit"],
  ["Milieu relayeur","Milieu defensif","Milieu relayeur"], ["Ailier gauche","Buteur","Ailier droit"]]};
let FAM_POSTE = {"Gardien":"GK","Defenseur central":"DEF","Lateral":"DEF","Lateral gauche":"DEF","Lateral droit":"DEF",
  "Milieu defensif":"MID","Milieu relayeur":"MID","Milieu offensif":"MID","Ailier":"FWD","Ailier droit":"FWD",
  "Ailier gauche":"FWD","Buteur":"FWD"};
// Ce qu'une carte perd à chaque poste (scoring.malus_poste), servi par le
// serveur : {poste de la case: {poste tenu: malus}}.  Et de combien un
// poste se dessine devant ou derrière sa ligne.
let MALUS_POSTES = {}, MALUS_GK = 30, PROF_POSTE = {"Milieu defensif": -0.045, "Milieu offensif": 0.045};

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
  // La tactique de départ du club est la tactique de TOUS ses matchs :
  // le lobby et le solo partent de là, comme ils partent de la compo.
  if (G.equipe.tactique) LOBBY.tac = {...LOBBY.tac, ...G.equipe.tactique};
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
  $("#st-elo").textContent = G.equipe?.elo_classe ?? "—";
}
async function montrer(ecran) {
  G.ecran = ecran;
  for (const s of document.querySelectorAll("main > section")) s.hidden = s.id !== "ecran-" + ecran;
  for (const b of document.querySelectorAll("nav button[data-ecran]")) b.setAttribute("aria-current", b.dataset.ecran === ecran ? "page" : "false");
  try { location.hash = ecran; } catch (e) {}
  if (ecran === "connexion") return;
  try {
    await rafraichir(ecran === "marche" || !G.cartes.length);
    await ({packs: rendrePacks, encheres: rendreEncheres, marche: rendreMarche, equipe: rendreEquipe, lobby: rendreLobby, solo: rendreSolo, journee: rendreJournee, classement: rendreClassement, admin: rendreAdmin}[ecran] || (async () => {}))();
  } catch (e) { if (e.status === 401) { connecte(null); } else toast(e.message); }
  finally { if (ecran !== "lobby") arreterLobby(); if (ecran !== "solo") arreterBoucleSolo();
    if (ecran !== "lobby" && ecran !== "solo") arreterTerrain(true); }
}
async function vitrine() {
  const V = $("#vitrine"); if (!V || V.childElementCount) return;
  try { for (const c of await api("/vitrine")) V.append(carteMarche(c, {vitrine: true, largeur: 240})); } catch (e) {}
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
  $("#packs-info").textContent = `Une carte ne peut exister qu'en ${G.packs.plafond} exemplaires dans la ligue. Réserve ${G.packs.reserve_max == null ? "illimitée" : G.packs.reserve_max + " cartes"}. La banque rachète à ${Math.round(G.packs.rachat * 100)} % de la cote.`;
  const offerts = Object.entries(G.packs.offerts || {}).filter(([, n]) => n > 0);
  if (offerts.length) {
    const b = el("div", {class: "panneau offerts"}, el("h3", {class: "anton"}, "Packs offerts"),
      el("p", {class: "compteur"}, "Gagnés en campagne solo. Ils s'ouvrent sans rien coûter."));
    const l = el("div", {class: "offerts-liste"});
    for (const [type, n] of offerts) {
      const p = G.packs.catalogue.find(x => x.type === type && !x.fam);
      l.append(el("div", {class: "offert " + type},
        el("b", {class: "anton"}, `${n} × ${TIER_TXT[type]}`),
        el("span", {class: "compteur"}, p ? p.desc : ""),
        el("button", {class: "primaire", disabled: !(p && p.disponible),
          onclick: () => ouvrirPack({...(p || {type, nom: "Pack " + TIER_TXT[type], prix: 0}), offert: true})},
          "Ouvrir gratuitement")));
    }
    b.append(l); P.append(b);
  }
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
  let r; try { r = await api("/packs/ouvrir", {type: p.type, fam: p.offert ? null : p.fam, offert: !!p.offert}); } catch (e) { toast(e.message); return; }
  await rafraichir(false);
  const dlg = $("#fiche"); dlg.replaceChildren();
  const box = el("div", {class: "fiche ouverture"}, el("h3", {class: "anton"}, `${p.nom}`), el("p", {class: "compteur"}, `${p.offert ? "offert" : fM(p.prix)} · il te reste ${fM(r.budget)}`));
  const grille = el("div", {class: "cartes-grille ouverture-grille"});
  r.cartes.forEach((x, i) => { const c = x.carte; const k = carteMarche(c, {vitrine: true, largeur: 240}); k.classList.add("revele"); k.style.animationDelay = (i * 0.25) + "s";
    k.append(el("div", {class: "cj-cote"}, `cote ${fM(x.cote)} · n° ${x.numero}`)); grille.append(k); });
  box.append(grille, el("div", {class: "actions"}, el("button", {onclick: () => { dlg.close(); montrer("equipe"); }}, "Gérer mon club"), el("button", {class: "primaire", onclick: () => { dlg.close(); rendrePacks(); }}, "Encore un pack")));
  dlg.append(box); dlg.showModal();
}
async function rendreEncheres(filtrePid = null) {
  const d = await api("/marche"); G.ventes = d.ventes;
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
    el("div", {class: "cj-milieu"}, barresForme(c), c.part > 0 ? el("span", {class: "part"}, Math.round(c.part * 100) + " %") : null));
  // The drawn card IS the card.  The CSS escutcheon stays underneath as the
  // fallback: it is what you see while the PNG loads, and what stays if the
  // render is missing.  Price and button live under the drawing, since the
  // drawing has no room for them.
  const crest = el("div", {class: "crest-bord"}, el("div", {class: "crest-corps"}, haut, corps));
  k.append(carteDessinee(c, opts.largeur || 170, crest),
    el("div", {class: "cj-bas"},
      el("div", {class: "cj-pied"}, el("span", {class: "prix num"}, fM(c.prix)),
        mien && Math.abs(delta) >= 0.005 ? el("span", {class: "delta " + (delta > 0 ? "plus" : "moins")}, fM(delta, true)) : null),
      opts.vitrine ? null : boutonAchatVente(c, mien)));
  return k;
}
// A card that entered the game during the season (mercato): shown for the
// three gameweeks after it opened, which is when nobody knows it yet.
function recrue(c) {
  const j = G.saison?.derniere?.numero ?? 0;
  return c.arrivee > 0 && j - c.arrivee < 3;
}
// The drawn card (moteur/carte_design), the one the game trades, with the
// light HTML box as a fallback while it loads or if the render is missing.
function carteDessinee(c, largeur = 170, secours = null) {
  const d = el("div", {class: "dessin"});
  secours = secours || el("div", {class: "mini"}, el("div", {},
    el("div", {class: "mh"}, el("div", {class: "o num" + (c.ovr >= 80 ? " haut" : "")}, String(c.ovr)), vignetteDe(c)),
    el("div", {class: "n"}, (c.nom || "").split(" ").slice(-1)[0])));
  const img = el("img", {src: `/images/cartes/${c.id ?? c.pid}.png?l=${largeur}&v=${c.ovr}`,
    alt: c.nom || "", loading: "lazy", draggable: "false"});
  img.addEventListener("load", () => secours.remove());
  img.addEventListener("error", () => img.remove());
  d.append(secours, img);
  return d;
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
  l.append(carteDessinee(c, 120),
    el("div", {class: "qui"}, el("div", {class: "nom"}, c.nom), el("div", {class: "sous"}, `${c.club} · ${POSTE_COURT[c.poste] || c.poste}${c.age ? " · " + c.age + " ans" : ""}${c.part > 0 ? " · " + Math.round(c.part * 100) + " % des équipes" : ""}`)),
    barresForme(c),
    el("div", {class: "ovr num" + (c.ovr >= 80 ? " haut" : "")}, String(c.ovr)),
    el("div", {class: "prix num"}, fM(c.prix), mien && Math.abs(delta) >= 0.005 ? el("div", {class: "delta " + (delta > 0 ? "plus" : "moins")}, fM(delta, true)) : null));
  l.append(boutonAchatVente(c, mien));
  return l;
}

// ---- équipe ----
function compoVide() { return {formation: "4-3-3", titulaires: [], banc: [], capitaine: null}; }
// A slot is a REAL POSITION, not a family.  A slot that only said
// "defender" is why Van Dijk came out at left back and Robertson in the
// middle, and why "best eleven" put three centre-backs in a back four.
function rangsDe(formation) { return RANGS[formation] || RANGS["4-3-3"]; }
function slotsPostes(formation) { return rangsDe(formation).flat(); }
function slotsFam(formation) { return slotsPostes(formation).map(p => FAM_POSTE[p] || "MID"); }
// N'importe qui n'importe où — et ça coûte selon la DISTANCE entre la
// case et le poste le plus proche que la carte a vraiment tenu
// (scoring.malus_poste) : un central au poste de latéral perd 4 sur
// chaque attribut, au poste de buteur 14, dans les buts 30.  L'OVR
// affiché sur la case est celui qu'il vaut là où il est.
function malusDe(id, poste) {
  const c = carte(id); if (!c || !poste) return 0;
  const ligne = MALUS_POSTES[poste];
  const tenus = (c.postes && c.postes.length) ? c.postes : [c.poste];
  if (!ligne) return tenus.includes(poste) ? 0 : 8;
  return Math.min(...tenus.map(p => ligne[p] ?? 8));
}
function ovrAu(id, poste) { return Math.max(40, ovr(id) - malusDe(id, poste)); }
function aLePoste(id, poste) { return malusDe(id, poste) === 0; }
function horsPoste(id, poste) { return malusDe(id, poste) > 0; }
// loin de chez lui : un attaquant central en défense, quelqu'un dans les buts
function loinDuPoste(id, poste) { return malusDe(id, poste) >= 14; }
const POSTE_ABBR = {"Gardien": "GB", "Defenseur central": "DC", "Lateral": "LAT",
  "Lateral gauche": "LG", "Lateral droit": "LD",
  "Milieu defensif": "MDF", "Milieu relayeur": "MC", "Milieu offensif": "MO",
  "Ailier": "AIL", "Ailier droit": "AD", "Ailier gauche": "AG", "Buteur": "BU"};
function legal(fams) { return fams.length === 11 && fams.every(x => !!x); }
// A card is eligible wherever the player really played, not only at the one
// label the barème shows: Valverde spent a third of his season at right
// back, a third on the wing and a quarter in midfield.
function famillesDe(c) { return (c && c.familles && c.familles.length) ? c.familles : [c ? c.fam : "MID"]; }
// Plus de ligne interdite : une carte peut occuper n'importe quelle case.
function peutJouer(id, fam) { return !!carte(id); }
function onzeLegal() { return C.slots.every(id => id !== null && carte(id)); }
// composition locale : slots (11, null si vide), banc, capitaine
let C = {formation: "4-3-3", slots: Array(11).fill(null), banc: [], cap: null};
function compoVersSlots() {
  const cp = G.compo; const fams = slotsFam(cp.formation in FORMATIONS ? cp.formation : "4-3-3");
  let slots = Array(11).fill(null);
  // The lineup is stored slot by slot, so the manager's own arrangement —
  // Valverde moved into midfield, the two centre-backs swapped — comes back
  // exactly as he left it.  Re-matching by position would undo it.
  const direct = cp.titulaires.length === 11 && cp.titulaires.every(id => id !== null && carte(id));
  if (direct) slots = cp.titulaires.slice();
  else {
    const reste = cp.titulaires.filter(id => carte(id));
    for (const exact of [true, false])
      for (let s = 0; s < 11; s++) {
        if (slots[s] !== null) continue;
        const k = reste.findIndex(id => exact ? carte(id).fam === fams[s] : peutJouer(id, fams[s]));
        if (k >= 0) { slots[s] = reste[k]; reste.splice(k, 1); }
      }
  }
  const tous = new Set(idsEffectif());
  const banc = cp.banc.filter(id => tous.has(id) && !slots.includes(id));
  for (const id of tous) if (!slots.includes(id) && !banc.includes(id)) banc.push(id);
  C = {formation: fams.length ? (cp.formation in FORMATIONS ? cp.formation : "4-3-3") : "4-3-3", slots, banc, cap: slots.includes(cp.capitaine) ? cp.capitaine : null};
  const brouillon = lireBrouillon();
  if (brouillon) C = brouillon;
}

// Le brouillon de composition.
//
// Tant qu'elle n'est pas ENVOYÉE, une composition ne vit que dans la
// page : recharger l'écran la reconstruisait depuis la dernière
// composition envoyée au serveur, et le travail du manager disparaissait
// — le "reset au chargement".  On la garde donc en local, et l'envoi
// reste ce qu'il était : la décision de la soumettre pour la journée.
function cleBrouillon() { return "fl.compo." + (G.equipe?.equipe_id ?? 0); }

function ecrireBrouillon() {
  try {
    localStorage.setItem(cleBrouillon(), JSON.stringify({t: Date.now(), c: C}));
  } catch (e) { /* navigation privée, quota : on s'en passe */ }
}

function lireBrouillon() {
  let b;
  try { b = JSON.parse(localStorage.getItem(cleBrouillon()) || "null"); } catch (e) { return null; }
  if (!b || !b.c || !Array.isArray(b.c.slots) || b.c.slots.length !== 11) return null;
  // il doit encore correspondre à l'effectif du jour : une carte vendue
  // ou achetée depuis rend le brouillon caduc
  const tous = new Set(idsEffectif());
  const dedans = [...b.c.slots.filter(x => x !== null), ...(b.c.banc || [])];
  if (!dedans.every(id => tous.has(id))) return null;
  if (!(b.c.formation in FORMATIONS)) return null;
  // une composition envoyée APRÈS le brouillon fait foi : c'est celle qui
  // compte pour la journée
  const envoyee = G.equipe?.composition?.soumise_le;
  if (envoyee && Date.parse(envoyee) > (b.t || 0)) return null;
  const banc = (b.c.banc || []).filter(id => tous.has(id) && !b.c.slots.includes(id));
  for (const id of tous) if (!b.c.slots.includes(id) && !banc.includes(id)) banc.push(id);
  return {formation: b.c.formation, slots: b.c.slots, banc, cap: b.c.cap ?? null};
}
// Best eleven, POSITION by position: for each slot, the card worth the
// most THERE — its OVR less what it loses away from what it held.  The
// scarcest slot is served first — filling in slot order left a back four
// of three centre-backs because the full-backs had already gone into the
// middle.
function auto(formation) {
  C.formation = formation;
  const postes = slotsPostes(formation);
  const tri = idsEffectif().sort((a, b) => ovr(b) - ovr(a));
  const pris = new Set(); const slots = postes.map(() => null);
  const ordre = postes.map((_, s) => s)
    .sort((x, y) => tri.filter(i => aLePoste(i, postes[x])).length - tri.filter(i => aLePoste(i, postes[y])).length);
  for (const s of ordre) {
    let meilleur = null, valeur = -1;
    for (const x of tri) {
      if (pris.has(x)) continue;
      const v = ovrAu(x, postes[s]) - malusDe(x, postes[s]) * 0.01;   // à valeur égale, celui de chez lui
      if (v > valeur) { valeur = v; meilleur = x; }
    }
    if (meilleur !== null) { slots[s] = meilleur; pris.add(meilleur); }
  }
  C.slots = slots;
  // the bench keeps a keeper first, then the best of what is left
  const reste = tri.filter(x => !pris.has(x));
  const gk = reste.find(x => peutJouer(x, "GK"));
  C.banc = gk === undefined ? reste : [gk, ...reste.filter(x => x !== gk)];
  if (!slots.includes(C.cap)) C.cap = slots.find(x => x !== null) ?? null;
  rendreEquipe(false);
}
// La recherche de l'écran Équipe : un nom tapé une fois filtre le banc,
// le club, et allume la carte sur le terrain.
function normEq() { const n = $("#eq-nom"); return n ? norm(n.value) : ""; }
function cherche(id, q) { const c = carte(id); return !!c && (norm(c.nom).includes(q) || norm(c.club || "").includes(q)); }

function rendreEquipe(recalc = true) {
  if (recalc) {
    compoVersSlots();
    // a squad with no lineup yet opens on its best eleven rather than on
    // eleven empty boxes and a bench of sixteen
    if (!G.compo?.titulaires?.length && idsEffectif().length >= 11) return auto(C.formation);
  }
  const sel = $("#formation"); if (!sel.options.length) for (const f of Object.keys(FORMATIONS)) sel.append(el("option", {value: f}, f));
  sel.value = C.formation;
  const postes = slotsPostes(C.formation);
  const T = $("#terrain"); T.replaceChildren();
  // the formation's own rows, drawn front to back
  const rangs = rangsDe(C.formation);
  let debut = 0; const bornes = rangs.map(r => { const b = [debut, debut + r.length]; debut += r.length; return b; });
  for (const [d0, d1] of [...bornes].reverse()) {
    const rang = el("div", {class: "rang"});
    for (let s = d0; s < d1; s++) rang.append(slotEl(s, postes[s]));
    T.append(rang);
  }
  const ok = onzeLegal();
  const A = $("#avert-compo"); A.replaceChildren();
  if (!ok) {
    const trous = C.slots.filter(i => i === null).length;
    A.append(el("div", {class: "avert"},
      `Il manque ${trous} joueur${trous > 1 ? "s" : ""} : glisse une carte du banc sur une case vide.`));
  }
  // Out of position is allowed, and it costs: say who, and how much the
  // eleven is worth where it stands.
  const postesC = slotsPostes(C.formation);
  const dehors = C.slots.map((id, s) => id === null ? 0 : malusDe(id, postesC[s]));
  const nDehors = dehors.filter(x => x > 0).length, perdu = dehors.reduce((a, b) => a + b, 0);
  if (nDehors) A.append(el("div", {class: "info"},
    `${nDehors} joueur${nDehors > 1 ? "s" : ""} hors de son poste : `
    + `${perdu} points d'OVR perdus en tout pendant le match, chacun selon la distance entre la case et ce qu'il a vraiment tenu `
    + `(orange : un cran, rouge : loin de chez lui). C'est permis, ça coûte.`));
  const moyenne = C.slots.every(x => x !== null)
    ? C.slots.reduce((a, id, s) => a + ovrAu(id, postesC[s]), 0) / 11 : null;
  if (moyenne !== null) A.append(el("div", {class: "compteur"}, `Onze au poste : ${moyenne.toFixed(1)} d'OVR en moyenne.`));
  const j = G.saison.courante;
  const etat = $("#compo-etat"); etat.replaceChildren();
  if (!j) etat.append("Saison terminée.");
  else if (j.verrouillee) etat.append(el("b", {}, `Journée ${j.numero} verrouillée`), ` depuis le coup d'envoi. Composition envoyée : ${G.equipe.composition ? "oui" : "non, score nul"}.`);
  else etat.append(`Journée ${j.numero}, du ${j.du} au ${j.au}. Verrouillage au premier coup d'envoi : ${new Date(j.cloture).toLocaleString("fr-FR")}. `, G.equipe.composition ? el("b", {}, `Composition envoyée le ${new Date(G.equipe.composition.soumise_le).toLocaleString("fr-FR")}.`) : el("b", {class: "rouge"}, "Aucune composition envoyée."));
  $("#btn-envoyer").disabled = !ok || !j || j.verrouillee;
  const B = $("#banc"); B.replaceChildren();
  zoneDepot(B, {type: "banc"});
  // la recherche filtre le banc et signale sur le terrain
  const q = normEq();
  C.banc.forEach((i, r) => { if (!q || cherche(i, q)) B.append(ligneBanc(i, r)); });
  if (q) T.querySelectorAll(".slot").forEach(n => n.classList.toggle("trouve", n._slot !== undefined && C.slots[n._slot] !== null && cherche(C.slots[n._slot], q)));
  if (q && !C.banc.some(i => cherche(i, q)) && !C.slots.some(i => i !== null && cherche(i, q)))
    B.append(el("p", {class: "compteur"}, `Personne ne s'appelle « ${$("#eq-nom").value.trim()} » dans ton effectif.`));
  if (!C.banc.length) B.append(el("p", {class: "compteur"}, `Banc vide. ${BANC_MAX} remplaçants : un gardien et six joueurs de champ, dans l’ordre où tu veux les faire entrer.`));
  // Un banc court n'est pas un bug de l'écran : c'est un effectif court.
  // Le dire, plutôt que de laisser croire à un banc de trois imposé.
  else if (C.banc.length < BANC_MAX) {
    const manque = 11 + BANC_MAX - idsEffectif().length;
    B.append(el("div", {class: "avert"},
      `Banc de ${C.banc.length} sur ${BANC_MAX} : tu n'as que ${idsEffectif().length} cartes dans l'effectif. `
      + `Il en faut ${11 + BANC_MAX} pour un onze et sept remplaçants`
      + (manque > 0 ? ` — il t'en manque ${manque}. Ouvre des packs, achète aux enchères, ou fais entrer des cartes de ta réserve dans l'effectif.` : ".")));
  }
  ecrireBrouillon();
  rendreTactiqueClub();
  rendreClub();
}
// La tactique de départ, réglée là où on règle la composition.  Elle est
// ENREGISTRÉE dès qu'on y touche : ce n'est pas une soumission de journée,
// elle n'est jamais verrouillée, et elle sert à tous les matchs.
let TAC_ENREG = null;

// Un seul endroit qui écrit la tactique du club, appelé depuis l'écran
// Équipe comme depuis le lobby.  Retardé d'un instant : cliquer trois
// réglages d'affilée ne fait pas trois écritures.
function enregistrerTactique(etat) {
  clearTimeout(TAC_ENREG);
  TAC_ENREG = setTimeout(async () => {
    try {
      const r = await api("/equipe/tactique", {tactique: LOBBY.tac});
      if (G.equipe) G.equipe.tactique = r.tactique;
      if (etat) etat.textContent = "enregistrée";
    } catch (e) { if (etat) etat.textContent = e.message; }
  }, 350);
}

function rendreTactiqueClub() {
  const boite = $("#tac-club");
  if (!boite) return;
  boite.replaceChildren();
  const etat = $("#tac-etat");
  const enregistrer = () => {
    rendreTactiqueClub();                       // les boutons se rallument tout de suite
    enregistrerTactique(etat);
  };
  boite.append(selecteurTactique(LOBBY.tac, enregistrer));
  boite.append(bilanAise());
  boite.append(depliant("equipe", "Consignes aux lignes",
    el("p", {class: "compteur"},
      "Ce que tu demandes à chaque ligne. Chacune est un échange, jamais un bonus : "
      + "le premier choix de chaque ligne ne touche à rien."),
    selecteurConsignes(LOBBY.tac, enregistrer)));
}

// Ce que ta tactique fait à TON onze : qui elle sert, qui elle dessert.
// C'est le retour dont le manager a besoin pour choisir — sans lui, le
// profil d'un joueur n'est qu'une ligne de plus sur une fiche.
function bilanAise() {
  const b = el("div", {class: "bilan-aise"});
  if (!Object.keys(AFFINITES).length) return b;
  const postes = slotsPostes(C.formation);
  const gens = [];
  C.slots.forEach((id, i) => {
    const c = id === null ? null : carte(id);
    if (!c || !c.profil) return;
    gens.push({nom: c.nom, poste: postes[i],
               a: aiseDe(c.profil, postes[i], LOBBY.tac)});
  });
  if (!gens.length) return b;
  const pct = x => AISE.max * Math.max(-1, Math.min(1, x / AISE.z)) * 100;
  const moyen = gens.reduce((s, g) => s + pct(g.a), 0) / gens.length;
  gens.sort((x, y) => y.a - x.a);
  const servis = gens.filter(g => pct(g.a) >= 1.5);
  const desservis = gens.filter(g => pct(g.a) <= -1.5).reverse();
  b.append(el("div", {class: "etiq"}, "Ce que ta tactique fait à ton onze"));
  b.append(el("div", {class: "bilan-chiffre " + (moyen > 0.5 ? "bon" : moyen < -0.5 ? "mauvais" : "")},
    (moyen > 0 ? "+" : "") + moyen.toFixed(1) + " %",
    el("span", {class: "compteur"}, " en moyenne sur tes onze titulaires")));
  const ligne = (titre, liste, classe) => {
    if (!liste.length) return null;
    return el("div", {class: "bilan-ligne " + classe},
      el("span", {class: "t"}, titre),
      el("span", {}, liste.slice(0, 4).map(g =>
        `${g.nom.split(" ").slice(-1)[0]} ${pct(g.a) > 0 ? "+" : ""}${pct(g.a).toFixed(0)} %`).join(" · ")
        + (liste.length > 4 ? ` (+${liste.length - 4})` : "")));
  };
  for (const l of [ligne("Elle les sert", servis, "bon"), ligne("Elle les dessert", desservis, "mauvais")])
    if (l) b.append(l);
  if (!servis.length && !desservis.length)
    b.append(el("p", {class: "compteur"}, "Ton onze est indifférent à ce réglage : personne n'y gagne ni n'y perd."));
  return b;
}

async function rendreClub() {
  const d = await api("/club"); G.club = d.cartes;
  const R = $("#club-liste"); R.replaceChildren();
  const q = normEq();
  const garde = x => !q || norm(x.carte.nom).includes(q) || norm(x.carte.club || "").includes(q);
  const eff = d.cartes.filter(x => x.dans_effectif && garde(x)), res = d.cartes.filter(x => !x.dans_effectif && garde(x));
  $("#club-compteur").textContent = `${eff.length} / ${d.effectif_max} dans l'effectif · ${res.length}${d.reserve_max == null ? "" : " / " + d.reserve_max} en réserve`;
  const ligne = x => {
    const c = x.carte; const l = el("div", {class: "ligne club-ligne" + (x.enchere_id ? " en-vente" : "")}); l.style.setProperty("--clubc", c.couleur);
    const delta = (x.cote || 0) - x.prix_achat;
    l.append(carteDessinee(c, 120), el("div", {class: "qui", tabindex: "0", onclick: () => ouvrirFiche(c.id)}, el("div", {class: "nom"}, c.nom, el("span", {class: "compteur"}, ` n° ${x.numero}`)), el("div", {class: "sous"}, `${c.club} · acheté ${fM(x.prix_achat)} · cote ${fM(x.cote)} `, el("span", {class: "delta " + (delta >= 0 ? "plus" : "moins")}, fM(delta, true)))),
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
// What is being moved: a pitch slot or a bench line.  The same state serves
// the drag (desktop) and the tap-tap (touch, and the keyboard).
let PRISE = null;
function prendre(src) { PRISE = (PRISE && PRISE.type === src.type && PRISE.i === src.i) ? null : src; marquerCibles(); }

// Repainting the pitch while a finger or a button is down detaches the very
// node the gesture started on, and Chromium then stops delivering pointer
// events: the drag froze on its first pixel.  During a gesture we only
// toggle classes on the nodes that are already there.
function marquerCibles() {
  const pris = PRISE ? carteDe(PRISE) : null;
  const vise = pris !== null && pris !== undefined;
  document.querySelectorAll("#terrain .slot").forEach(n => {
    n.classList.remove("cible", "interdit", "prise");
    if (PRISE && PRISE.type === "slot" && PRISE.i === n._slot) n.classList.add("prise");
    else if (vise) n.classList.add(aLePoste(pris, n._poste) ? "cible" : loinDuPoste(pris, n._poste) ? "cible-loin" : "cible-ligne");
  });
  document.querySelectorAll("#banc .ligne").forEach((n, r) =>
    n.classList.toggle("prise", !!PRISE && PRISE.type === "banc" && PRISE.i === r));
}
function carteDe(src) { return src.type === "slot" ? C.slots[src.i] : C.banc[src.i]; }

function deposer(src, cible) {
  // cible = {type:"slot", i} or {type:"banc"}.  A card may only land on a
  // slot of a family it really played; whoever it displaces goes to the
  // bench rather than into a position he has never held.
  const id = carteDe(src);
  if (id === null || id === undefined) return;
  if (cible.type === "banc") {
    if (src.type === "slot") { C.slots[src.i] = null; C.banc.unshift(id); if (C.cap === id) C.cap = null; }
    PRISE = null; rendreEquipe(false); return;
  }
  const occupant = C.slots[cible.i];
  if (src.type === "slot") {
    if (src.i === cible.i) { PRISE = null; rendreEquipe(false); return; }
    // deux titulaires échangent leurs postes, quels qu'ils soient
    C.slots[cible.i] = id;
    C.slots[src.i] = occupant;
  } else {
    C.banc.splice(src.i, 1);
    C.slots[cible.i] = id;
    if (occupant !== null) { C.banc.unshift(occupant); if (C.cap === occupant) C.cap = null; }
  }
  PRISE = null; rendreEquipe(false);
}

// Pointer events rather than HTML5 drag and drop: the latter does not
// exist on mobile browsers, and the pitch has to work under a thumb.  One
// gesture covers both ways of moving a card — drag it, or tap it and tap
// where it goes — because a drag under the threshold IS a tap.
const SEUIL_GLISSE = 7;          // pixels before a tap becomes a drag
let FANTOME = null;

function zoneDepot(d, cible) { d._cible = cible; }

function cibleSous(x, y) {
  for (let n = document.elementFromPoint(x, y); n; n = n.parentElement)
    if (n._cible) return {cible: n._cible, noeud: n};
  return null;
}

function zonePrise(d, src) {
  // The portraits are <img>: Chromium starts its own native image drag on
  // the first move and fires pointercancel, which killed the gesture on its
  // first pixel.  Refusing dragstart keeps the pointer stream ours.
  d.addEventListener("dragstart", e => e.preventDefault());
  d.addEventListener("pointerdown", e => {
    if (e.button !== 0 && e.pointerType === "mouse") return;
    if (e.target.closest(".slot-menu, .ordre")) return;       // the options and the arrows keep their click
    const depart = {x: e.clientX, y: e.clientY};
    let glisse = false, dernier = null;
    const bouge = ev => {
      if (!glisse && Math.hypot(ev.clientX - depart.x, ev.clientY - depart.y) < SEUIL_GLISSE) return;
      if (!glisse) {
        glisse = true;
        PRISE = src;
        FANTOME = d.cloneNode(true);
        FANTOME.className = (d.className || "") + " fantome";
        document.body.append(FANTOME);
        marquerCibles();
      }
      FANTOME.style.left = ev.clientX + "px";
      FANTOME.style.top = ev.clientY + "px";
      const sous = cibleSous(ev.clientX, ev.clientY);
      if (dernier && dernier !== sous?.noeud) dernier.classList.remove("survol");
      dernier = sous?.noeud || null;
      if (dernier) dernier.classList.add("survol");
    };
    const fini = ev => {
      window.removeEventListener("pointermove", bouge);
      window.removeEventListener("pointerup", fini);
      window.removeEventListener("pointercancel", fini);
      if (FANTOME) { FANTOME.remove(); FANTOME = null; }
      if (dernier) dernier.classList.remove("survol");
      if (!glisse) return;                                     // a tap: the click handler takes it
      const sous = cibleSous(ev.clientX, ev.clientY);
      if (sous) deposer(src, sous.cible);
      else { PRISE = null; rendreEquipe(false); }
      ev.preventDefault();
    };
    window.addEventListener("pointermove", bouge);
    window.addEventListener("pointerup", fini);
    window.addEventListener("pointercancel", fini);
  });
}

function slotEl(s, poste) {
  const fam = FAM_POSTE[poste] || "MID";
  const i = C.slots[s];
  const pris = PRISE ? carteDe(PRISE) : null;
  const vise = pris !== null && pris !== undefined;
  const classes = ["slot"];
  if (i === null) classes.push("vide");
  if (PRISE && PRISE.type === "slot" && PRISE.i === s) classes.push("prise");
  else if (vise) classes.push(aLePoste(pris, poste) ? "cible" : loinDuPoste(pris, poste) ? "cible-loin" : "cible-ligne");
  const malus = i === null ? 0 : malusDe(i, poste);
  if (malus >= 14) classes.push("faute");
  else if (malus > 0) classes.push("dephase");
  const nomPoste = POSTE_COURT[poste] || poste;
  const titre = i === null ? `Case ${nomPoste.toLowerCase()} vide`
    : malus > 0
      ? `${carte(i).nom} joue ${nomPoste.toLowerCase()}, loin de ce qu'il a tenu (${(carte(i).postes || [carte(i).poste]).map(x => (POSTE_COURT[x] || x).toLowerCase()).join(", ")}) : −${malus} sur chaque attribut, OVR ${ovrAu(i, poste)} à ce poste.`
      : `${carte(i).nom} — ${nomPoste}. Glisse-le ailleurs, ou touche-le puis touche sa destination.`;
  const d = el("div", {class: classes.join(" "), tabindex: "0", title: titre,
    style: PROF_POSTE[poste] ? `--prof:${PROF_POSTE[poste]}` : null,
    onclick: () => { if (PRISE) deposer(PRISE, {type: "slot", i: s}); else if (i !== null) prendre({type: "slot", i: s}); },
    onkeydown: e => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); if (PRISE) deposer(PRISE, {type: "slot", i: s}); else if (i !== null) prendre({type: "slot", i: s}); }
      if (e.key === "Escape") { PRISE = null; rendreEquipe(false); }
      if (e.key.toLowerCase() === "c" && i !== null) { C.cap = i; rendreEquipe(false); }
    }});
  d._slot = s; d._fam = fam; d._poste = poste;
  zoneDepot(d, {type: "slot", i: s});
  if (i === null) {
    d.append(el("div", {class: "mini"}, el("div", {}, el("div", {class: "o"}, "+"),
      el("div", {class: "n"}, POSTE_ABBR[poste] || NOM_FAM[fam]))));
    return d;
  }
  const c = carte(i);
  zonePrise(d, {type: "slot", i: s});
  d.style.setProperty("--clubc", c.couleur);
  d.append(carteDessinee(c, 170));
  d.append(el("div", {class: "slot-poste" + (malus >= 14 ? " loin" : malus > 0 ? " dephase" : "")},
    (POSTE_ABBR[poste] || fam) + (malus > 0 ? ` · ${ovrAu(i, poste)}` : "")));
  if (C.cap === i) d.append(el("div", {class: "cap"}, "C"));
  d.append(el("button", {class: "slot-menu", title: "Options", onclick: e => { e.stopPropagation(); PRISE = null; menuSlot(s); }}, "···"));
  return d;
}
function menuSlot(s) {
  const i = C.slots[s]; const poste = slotsPostes(C.formation)[s];
  const fam = FAM_POSTE[poste] || "MID"; const dlg = $("#fiche"); dlg.replaceChildren();
  const c = carte(i);
  const box = el("div", {class: "fiche"}, el("h3", {class: "anton"}, c.nom),
    el("p", {class: "compteur"}, `${POSTE_COURT[poste] || poste} · OVR ${ovr(i)}`
      + (horsPoste(i, poste) ? ` (${ovrAu(i, poste)} à ce poste)` : "") + ` · a tenu `
      + (c.postes || []).map(x => (POSTE_COURT[x] || x).toLowerCase()).join(", ")),
    horsPoste(i, poste) ? el("div", {class: "avert"},
      `Hors de son poste : −${malusDe(i, poste)} sur chacun de ses attributs pendant le match.`) : null);
  const acts = el("div", {class: "actions", style: "justify-content:flex-start"});
  acts.append(el("button", {class: "primaire", onclick: () => { C.cap = i; dlg.close(); rendreEquipe(false); }}, "Nommer capitaine"));
  // the bench, those who really hold the position first
  const remplacants = C.banc.slice().sort((x, y) => ovrAu(y, poste) - ovrAu(x, poste));
  for (const b of remplacants) acts.append(el("button", {onclick: () => { C.banc = C.banc.map(x => x === b ? i : x); C.slots[s] = b; if (C.cap === i) C.cap = b; dlg.close(); rendreEquipe(false); }},
    `Remplacer par ${carte(b).nom} (${ovrAu(b, poste)})${aLePoste(b, poste) ? "" : ` — hors poste, −${malusDe(b, poste)}`}`));
  acts.append(el("button", {onclick: () => { C.slots[s] = null; C.banc.unshift(i); if (C.cap === i) C.cap = null; dlg.close(); rendreEquipe(false); }}, "Mettre sur le banc"));
  acts.append(el("button", {onclick: () => { dlg.close(); ouvrirFiche(i); }}, "Voir la fiche"), el("button", {class: "discret", onclick: () => dlg.close()}, "Fermer"));
  box.append(acts); dlg.append(box); dlg.showModal();
}
function ligneBanc(i, r) {
  const c = carte(i);
  const choisi = PRISE && PRISE.type === "banc" && PRISE.i === r;
  const l = el("div", {class: "ligne" + (choisi ? " prise" : ""), tabindex: "0",
    title: `${c.nom} — ${famillesDe(c).map(f => NOM_FAM[f]).join(", ")}. Glisse-le sur le terrain.`,
    onclick: () => { if (PRISE && PRISE.type === "slot") deposer(PRISE, {type: "banc"}); else prendre({type: "banc", i: r}); },
    onkeydown: e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); if (PRISE && PRISE.type === "slot") deposer(PRISE, {type: "banc"}); else prendre({type: "banc", i: r}); } }});
  l.style.setProperty("--clubc", c.couleur);
  zonePrise(l, {type: "banc", i: r});
  const ord = el("div", {class: "ordre"},
    el("button", {title: "Monter", disabled: r === 0, onclick: e => { e.stopPropagation(); [C.banc[r - 1], C.banc[r]] = [C.banc[r], C.banc[r - 1]]; rendreEquipe(false); }}, "▲"),
    el("button", {title: "Descendre", disabled: r === C.banc.length - 1, onclick: e => { e.stopPropagation(); [C.banc[r + 1], C.banc[r]] = [C.banc[r], C.banc[r + 1]]; rendreEquipe(false); }}, "▼"));
  l.append(ord, carteDessinee(c, 120), el("div", {class: "qui"}, el("div", {class: "nom"}, c.nom), el("div", {class: "sous"}, c.club)),
    el("span", {class: "fams"}, ...famillesDe(c).map(f => el("span", {class: "fam " + f}, f))),
    el("div", {class: "ovr num"}, String(c.ovr)));
  return l;
}
async function envoyer() {
  try {
    const r = await api("/equipe/composition", {formation: C.formation, titulaires: C.slots, banc: C.banc, capitaine: C.cap});
    toast(`Composition envoyée pour la journée ${r.journee}`); await rafraichir(false); rendreEquipe();
  } catch (e) { toast(e.message); }
}

// ---- lobby classé : un match joué avec les cartes -------------------------
// The sheet is recomputed server-side from the seed and the tactical
// timeline on every poll, so what we draw is never a local accumulation:
// refreshing, or coming back after a while, shows the same match.
const TEMPO_TXT = {possession: "Garder le ballon", equilibre: "Équilibré", direct: "Jouer direct"};
const BLOC_TXT = {haut: "Bloc haut", median: "Bloc médian", bas: "Bloc bas"};
const RISQUE_TXT = {offensif: "Offensif", equilibre: "Équilibré", prudent: "Prudent"};
const AXE_TXT = {tempo: TEMPO_TXT, bloc: BLOC_TXT, risque: RISQUE_TXT};

// Les consignes individuelles : ce qu'on demande à une LIGNE, dans les
// mots d'un entraîneur.  Chacune est un échange, jamais un bonus, et le
// premier choix de chaque ligne est neutre (jeu/simulation.CONSIGNES).
const CONSIGNE_TXT = {
  lateraux: {titre: "Latéraux", opts: {
    couloir: ["Monte dans son couloir", "Le latéral accompagne l'attaque sur son aile. Le réglage neutre."],
    bas: ["Reste derrière", "Il ne dépasse pas le milieu : +défense, −percussion."],
    axe: ["Rentre dans l'axe", "Latéral axial : un homme de plus au milieu. +contrôle, −défense."]}},
  ailiers: {titre: "Ailiers", opts: {
    equilibre: ["Équilibré", "Il alterne appel extérieur et intérieur. Le réglage neutre."],
    ligne: ["Colle la ligne", "Il tient la largeur et étire le bloc adverse : +percussion, −création."],
    interieur: ["Repique dans l'axe", "Ailier inversé, il rentre pour frapper : +création, +finition, −percussion."]}},
  milieux: {titre: "Milieux", opts: {
    equilibre: ["Équilibré", "Il monte et redescend avec le jeu. Le réglage neutre."],
    projection: ["Rejoint l'attaque", "Il se projette dans la surface : +percussion, −défense (l'espace derrière)."],
    bas: ["Reste derrière", "Il protège la ligne : +défense, +contrôle, −percussion."],
    lateral: ["Organise sur les côtés", "Il décale le jeu vers les ailes : +création, −contrôle (l'axe se vide)."]}},
  attaquants: {titre: "Attaquants", opts: {
    equilibre: ["Équilibré", "Il joue entre les lignes et en profondeur. Le réglage neutre."],
    profondeur: ["Cherche la profondeur", "Appels dans le dos : plus de ballons joués, moins bien : +percussion, −création."],
    pivot: ["Joue en pivot", "Dos au but, il fixe et remise : +contrôle, +création, −percussion."]}},
  relance: {titre: "Relance", opts: {
    equilibre: ["Équilibrée", "On ressort comme on peut. Le réglage neutre."],
    courte: ["Courte, par le bas", "On sort proprement mais on se découvre : +contrôle, −défense."],
    longue: ["Jeu long", "On saute le milieu : +percussion, +défense, −contrôle."]}},
};

// Un dépliant dont l'état SURVIT au sondage : l'écran du lobby est
// redessiné toutes les deux secondes et demie, et un <details> reconstruit
// se referait sous le nez du manager au milieu d'un réglage.
const DEPLIES = {};
function depliant(cle, titre, ...enfants) {
  const d = el("details", {class: "consignes"}, el("summary", {}, titre), ...enfants);
  d.open = !!DEPLIES[cle];
  d.addEventListener("toggle", () => { DEPLIES[cle] = d.open; });
  return d;
}

// ---------------------------------------------------------------------------
// Le profil d'un joueur : où il est chez lui.
//
// Le serveur envoie six nombres par carte — sa FORME sur les six axes,
// lue contre sa ligne et débarrassée de son niveau (jeu/simulation.profil)
// — et la table de ce que chaque réglage demande.  Tout le reste se
// déduit ici : rien n'est étiqueté à la main, ni au serveur ni ici.
let AFFINITES = {}, AISE = {max: 0.10, z: 1.3, seuil: 0.35};

function affinite(profil, poste, axe, choix) {
  const d = AFFINITES[axe]?.[choix];
  if (!d || !profil) return null;
  if (d.postes && !d.postes.includes(posteBase(poste))) return null;
  const vals = d.axes.map(k => profil[k]).filter(v => v !== undefined);
  return vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : null;
}

// Son aise dans une tactique donnée : la moyenne des réglages non
// neutres qui le concernent, exactement comme le moteur la calcule.
function aiseDe(profil, poste, tac) {
  const v = [];
  for (const axe of Object.keys(AFFINITES)) {
    const a = affinite(profil, poste, axe, tac?.[axe]);
    if (a !== null) v.push(a);
  }
  return v.length ? v.reduce((a, b) => a + b, 0) / v.length : 0;
}

// Les réglages où il est le plus, et le moins, chez lui.
function lectureProfil(profil, poste, combien = 3) {
  const out = [];
  for (const [axe, opts] of Object.entries(AFFINITES))
    for (const choix of Object.keys(opts)) {
      const v = affinite(profil, poste, axe, choix);
      if (v !== null && v !== 0) out.push({texte: opts[choix].texte, score: v});
    }
  out.sort((a, b) => b.score - a.score);
  return {aise: out.filter(x => x.score >= AISE.seuil).slice(0, combien),
          gene: out.filter(x => x.score <= -AISE.seuil).slice(-combien).reverse()};
}

function selecteurConsignes(tac, onChange) {
  const d = el("div", {class: "tactiques consignes-jeu"});
  for (const [axe, def] of Object.entries(CONSIGNE_TXT)) {
    const g = el("div", {class: "tac-groupe"}, el("span", {class: "tac-titre"}, def.titre));
    for (const [v, [libelle, aide]] of Object.entries(def.opts))
      g.append(el("button", {class: "tac" + (tac[axe] === v ? " actif" : ""),
        "data-consigne": axe, "data-valeur": v, title: aide,
        onclick: () => { tac[axe] = v; onChange(); }}, libelle));
    d.append(g);
  }
  return d;
}
const EVT_ICONE = {but: "⚽", arret: "🧤", occasion: "✗", tactique: "⇄", corner: "⛳", faute: "⚠",
  jaune: "🟨", rouge: "🟥", horsjeu: "🚩", changement: "🔁", blessure: "🚑", permutation: "⇅",
  formation: "⇄", penalty_manque: "✗"};
let LOBBY = {timer: null, vus: 0,
  tac: {tempo: "equilibre", bloc: "median", risque: "equilibre",
        lateraux: "couloir", ailiers: "equilibre", milieux: "equilibre",
        attaquants: "equilibre", relance: "equilibre"}};

function arreterLobby() {
  if (G.ecran !== "solo") arreterTerrain(true); if (LOBBY.timer) { clearInterval(LOBBY.timer); LOBBY.timer = null; } }

async function rendreLobby(donnees) {
  const d = donnees || await api("/lobby");
  LOBBY.etat = d;
  $("#lobby-info").textContent = `Elo classé ${Math.round(d.elo)} · ${d.classees} match${d.classees > 1 ? "s" : ""} classé${d.classees > 1 ? "s" : ""}`;
  const B = $("#lobby-corps"); B.replaceChildren();
  if (d.etat === "libre") { arreterLobby(); B.append(panneauEntree(d)); B.append(panneauHistorique(d)); return; }
  if (d.etat === "attente") { B.append(panneauAttente(d)); lancerBoucle(); return; }
  B.append(panneauMatch(d));
  if (d.etat === "fini") { arreterLobby(); B.append(panneauHistorique(d)); } else lancerBoucle();
}
function lancerBoucle() { if (!LOBBY.timer) LOBBY.timer = setInterval(() => { if (G.ecran === "lobby") rendreLobby().catch(() => {}); }, 2500); }

function selecteurTactique(tac, onChange) {
  const d = el("div", {class: "tactiques"});
  for (const axe of ["tempo", "bloc", "risque"]) {
    const g = el("div", {class: "tac-groupe"}, el("span", {class: "tac-titre"}, {tempo: "Tempo", bloc: "Bloc", risque: "Risque"}[axe]));
    for (const v of Object.keys(AXE_TXT[axe])) {
      // l'axe et la valeur sont posés sur le bouton : le panneau du match
      // est réutilisé d'un sondage à l'autre et n'a plus qu'à remettre la
      // classe `actif` au bon endroit, sans reconstruire les boutons
      g.append(el("button", {class: "tac" + (tac[axe] === v ? " actif" : ""), "data-axe": axe, "data-valeur": v,
        onclick: () => { tac[axe] = v; onChange(); }}, AXE_TXT[axe][v]));
    }
    d.append(g);
  }
  return d;
}

function panneauEntree(d) {
  const p = el("div", {class: "panneau"}, el("h3", {class: "anton"}, "Lance un match"));
  p.append(el("p", {class: "compteur"},
    `Ton onze joue contre celui d'un autre manager, avec les attributs de tes cartes. ${Math.round(d.duree / 60)} minutes pour 90, tu ajustes en direct.`));
  const onze = C.slots.every(x => x !== null) ? C.slots.slice() : null;
  if (!onze) {
    p.append(el("div", {class: "avert"}, "Ton onze n'est pas complet : va dans Équipe le compléter, il sert aussi ici."));
    return p;
  }
  const strip = el("div", {class: "onze-strip"});
  for (const i of onze) {
    const c = carte(i);
    const t = el("div", {class: "onze-carte", title: c.nom, onclick: () => ouvrirFiche(i)});
    t.style.setProperty("--clubc", c.couleur);
    t.append(carteDessinee(c, 120), el("div", {class: "n"}, c.nom.split(" ").slice(-1)[0]));
    strip.append(t);
  }
  p.append(el("div", {class: "etiq"}, "Le onze que tu alignes"), strip);
  // Retoucher la tactique ici l'enregistre aussi : c'est la MÊME que
  // celle de l'écran Équipe, il n'y en a qu'une par club.
  const maj = () => { const n = panneauEntree(d); p.replaceWith(n); enregistrerTactique(); };
  p.append(el("div", {class: "etiq"}, "Ta tactique de départ"));
  p.append(selecteurTactique(LOBBY.tac, maj));
  p.append(depliant("entree", "Consignes aux lignes",
    el("p", {class: "compteur"},
      "Ce que tu demandes à chaque ligne, en plus des trois axes. Tu peux les changer en cours de match."),
    selecteurConsignes(LOBBY.tac, maj)));
  p.append(el("p", {class: "compteur"},
    "Réglée une fois, elle sert à tous tes matchs — tu la retrouves aussi sur l'écran Équipe."));
  const acts = el("div", {class: "actions", style: "justify-content:flex-start"});
  acts.append(el("button", {class: "primaire", onclick: () => entrerLobby(onze, false)}, "Chercher un adversaire"),
    el("button", {onclick: () => entrerLobby(onze, true)}, "Jouer un défi tout de suite"));
  p.append(acts);
  p.append(el("p", {class: "compteur"}, d.attente_file ? `${d.attente_file} manager(s) dans la file.` : "Personne dans la file : le défi te fait jouer contre un onze de ton niveau, hors classement."));
  return p;
}

async function entrerLobby(onze, defi) {
  try { await rendreLobby(await api("/lobby/rejoindre", {formation: C.formation, onze, banc: C.banc.slice(0, BANC_MAX), tactique: LOBBY.tac, defi})); }
  catch (e) { toast(e.message); }
}

function panneauAttente(d) {
  const p = el("div", {class: "panneau"}, el("h3", {class: "anton"}, "En attente d'un adversaire"));
  p.append(el("p", {class: "compteur"}, "Le match démarre dès qu'un manager de ton niveau entre dans la file."),
    el("div", {class: "actions", style: "justify-content:flex-start"},
      el("button", {onclick: async () => { try { await rendreLobby(await api("/lobby/quitter", {})); } catch (e) { toast(e.message); } }}, "Quitter la file")));
  return p;
}

// ---------------------------------------------------------------------------
// L'écran de match.
//
// Quand un match tourne, il PREND l'écran : le score et l'horloge en
// haut, le terrain au centre, les deux compositions de chaque côté avec
// la note et l'endurance de chacun, et en dessous des onglets — le
// direct, la tactique, les stats.  C'est la disposition d'un jeu de
// management : tout ce qu'on regarde pendant qu'on décide est visible en
// même temps, et ce qu'on ne regarde qu'entre deux décisions est derrière
// un onglet.
//
// L'onglet reste où le manager l'a laissé d'un sondage à l'autre.
// ---------------------------------------------------------------------------
const ONGLETS_MATCH = {direct: "Le direct", tactique: "Tactique", stats: "Statistiques"};
let ONGLET = "direct";
const MATCH_FINI_VU = new Set();     // pour n'ouvrir la feuille qu'une fois

function couleurNote(n) { return n >= 7.5 ? "haute" : n >= 6.5 ? "bonne" : n >= 5.5 ? "" : "basse"; }

// Une composition, joueur par joueur : sa note de match, ce qu'il a
// fait, ce qu'il lui reste dans les jambes.
function colonneCompo(m, cote, mien) {
  const tous = [...(m.onze?.[cote] || []), ...(m.banc?.[cote] || [])];
  const sur = (m.sur_le_terrain?.[cote] || []).map(pid => tous.find(j => j.pid === pid)).filter(Boolean);
  const endu = m.endurance?.[cote] || {};
  const fiches = m.joueurs || {};
  const c = el("div", {class: "compo-col " + (mien ? "mien" : "adverse")});
  c.append(el("div", {class: "compo-tete"},
    el("b", {class: "anton"}, m.noms[cote === "a" ? 0 : 1]),
    el("span", {class: "compo-forme"}, m.formation?.[cote] || "")));
  for (const j of sur) {
    const f = fiches[j.pid] || {};
    const faits = [];
    if (f.buts) faits.push("⚽".repeat(Math.min(3, f.buts)));
    if (f.passes_d) faits.push("🅰".repeat(Math.min(3, f.passes_d)));
    if (f.arrets) faits.push(`🧤${f.arrets}`);
    if (f.jaunes) faits.push("🟨");
    if (f.rouges) faits.push("🟥");
    const e = endu[j.pid];
    const l = el("div", {class: "compo-j", title: `${j.nom} · ${j.slot || j.poste} · OVR ${j.ovr}`
        + (f.touches ? ` · ${f.touches} ballons joués` : "")},
      el("span", {class: "po"}, POSTE_ABBR[j.slot] || ""),
      el("span", {class: "nm"}, (j.nom || "").split(" ").slice(-1)[0]),
      el("span", {class: "fa"}, faits.join(" ")),
      jaugeEndurance(e),
      el("b", {class: "note " + couleurNote(f.note ?? 6)}, f.note ? f.note.toFixed(1) : "—"));
    c.append(l);
  }
  const utilises = new Set(m.entres?.[cote] || []);
  const restants = (m.banc?.[cote] || []).filter(j => !utilises.has(j.pid));
  c.append(el("div", {class: "compo-banc"}, `Banc : ${restants.length} · `
    + `${m.changements?.[cote === "a" ? 0 : 1] ?? 0}/${SM_MAX_CHG} changements`));
  return c;
}

// Les stats avancées : les barres, la carte des tirs, la course au xG.
function ongletStats(d) {
  const m = d.match, moi = d.cote === "b" ? 1 : 0, lui = 1 - moi;
  const p = el("div", {class: "onglet-corps"});
  const stats = el("div", {class: "live-stats"});
  const pair = (lib, a, b) => [lib, a, b];
  for (const [lib, va, vb] of [
      pair("Possession", m.possession[moi] + " %", m.possession[lui] + " %"),
      pair("Tirs", m.tirs[moi], m.tirs[lui]),
      pair("xG", m.xg[moi].toFixed(2), m.xg[lui].toFixed(2)),
      pair("xG par tir", (m.tirs[moi] ? m.xg[moi] / m.tirs[moi] : 0).toFixed(2),
           (m.tirs[lui] ? m.xg[lui] / m.tirs[lui] : 0).toFixed(2)),
      pair("Corners", m.corners?.[moi] ?? 0, m.corners?.[lui] ?? 0),
      pair("Fautes", m.fautes?.[moi] ?? 0, m.fautes?.[lui] ?? 0),
      pair("Hors-jeu", m.horsjeu?.[moi] ?? 0, m.horsjeu?.[lui] ?? 0),
      pair("Cartons", cartons(m, moi), cartons(m, lui))])
    stats.append(el("div", {class: "sl"}, el("b", {}, String(va)), el("span", {}, lib), el("b", {}, String(vb))));
  p.append(stats);
  p.append(el("div", {class: "etiq"}, "La course au xG"), courseXg(m, moi));
  p.append(el("div", {class: "etiq"}, "Où ils ont tiré"), carteTirs(m, moi));
  // les meilleures notes des deux camps
  const fiches = Object.entries(m.joueurs || {}).map(([pid, f]) => ({pid: +pid, ...f}));
  if (fiches.length) {
    const nom = pid => {
      for (const c of ["a", "b"])
        for (const j of [...(m.onze?.[c] || []), ...(m.banc?.[c] || [])])
          if (j.pid === pid) return [j.nom, c];
      return ["?", "a"];
    };
    fiches.sort((x, y) => y.note - x.note);
    const h = el("div", {class: "hommes"});
    fiches.slice(0, m.fini ? 6 : 5).forEach((f, i) => {
      const [n, c] = nom(f.pid);
      const faits = [];
      if (f.buts) faits.push(`${f.buts} but${f.buts > 1 ? "s" : ""}`);
      if (f.passes_d) faits.push(`${f.passes_d} passe${f.passes_d > 1 ? "s" : ""} d.`);
      if (f.arrets) faits.push(`${f.arrets} arrêt${f.arrets > 1 ? "s" : ""}`);
      faits.push(`${f.touches} ballons`);
      h.append(el("div", {class: "homme" + (c === "ab"[moi] ? " mien" : "") + (i === 0 && m.fini ? " premier" : "")},
        el("b", {class: "note " + couleurNote(f.note)}, f.note.toFixed(1)),
        el("span", {}, n),
        i === 0 && m.fini ? el("span", {class: "medaille"}, "homme du match") : null,
        el("span", {class: "compteur"}, faits.join(" · "))));
    });
    p.append(el("div", {class: "etiq"}, m.fini ? "La feuille de match" : "Les hommes du match"), h);
  }
  return p;
}

// La course au xG : ce qui distingue une domination d'un cambriolage.
function courseXg(m, moi) {
  const cum = [[0], [0]];
  for (const l of m.fil || []) {
    const e = l.e !== null && l.e !== undefined ? m.evenements[l.e] : null;
    const x = e && e.xg ? e.xg : 0;
    const c = e ? (e.cote === "A" ? 0 : 1) : null;
    cum[0].push(cum[0][cum[0].length - 1] + (c === 0 ? x : 0));
    cum[1].push(cum[1][cum[1].length - 1] + (c === 1 ? x : 0));
  }
  const n = cum[0].length;
  const haut = Math.max(0.5, cum[0][n - 1], cum[1][n - 1]);
  const W = 100, H = 42;
  const trace = s => s.map((v, i) => `${(i / Math.max(1, n - 1) * W).toFixed(2)},${(H - v / haut * H).toFixed(2)}`).join(" ");
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.setAttribute("class", "xg-course");
  svg.setAttribute("preserveAspectRatio", "none");
  for (const [k, cls] of [[moi, "mien"], [1 - moi, "adverse"]]) {
    const l = document.createElementNS("http://www.w3.org/2000/svg", "polyline");
    l.setAttribute("points", trace(cum[k]));
    l.setAttribute("class", cls);
    svg.append(l);
  }
  const b = el("div", {class: "xg-boite"});
  b.append(svg, el("div", {class: "xg-legende"},
    el("span", {class: "lg mien"}, `toi ${cum[moi][n - 1].toFixed(2)}`),
    el("span", {class: "lg adverse"}, `eux ${cum[1 - moi][n - 1].toFixed(2)}`)));
  return b;
}

// La carte des tirs : chaque frappe à l'endroit d'où elle est partie,
// grosse comme son xG, pleine si elle est rentrée.
function carteTirs(m, moi) {
  const b = el("div", {class: "tirs-carte"});
  const fond = el("div", {class: "tirs-fond"}, el("div", {class: "tirs-surface"}), el("div", {class: "tirs-but"}));
  b.append(fond);
  let n = 0;
  for (const l of m.fil || []) {
    const e = l.e !== null && l.e !== undefined ? m.evenements[l.e] : null;
    if (!e || !["but", "arret", "occasion"].includes(e.type)) continue;
    const tir = (l.s || []).find(x => x.k === "tir");
    const mien = e.cote === "AB"[moi];
    const xg = e.xg || 0.05;
    const taille = 7 + Math.min(22, xg * 42);
    // d'où : plus le xG est grand, plus c'est près du but
    const prof = 0.06 + (1 - Math.min(1, xg / 0.5)) * 0.26;
    const trav = tir && tir.t !== undefined ? 0.5 + (tir.t - 0.5) * 0.62 : 0.5;
    const pt = el("span", {class: "tir " + e.type + (mien ? " mien" : " adverse"),
      title: `${e.minute}' ${e.texte} · xG ${xg.toFixed(2)}`,
      style: `right:${(prof * 100).toFixed(1)}%;top:${(trav * 100).toFixed(1)}%;`
             + `width:${taille}px;height:${taille}px;margin:${-taille / 2}px`});
    fond.append(pt); n++;
  }
  if (!n) b.append(el("p", {class: "compteur"}, "Pas encore de tir."));
  else b.append(el("p", {class: "compteur"},
    "Taille = xG. Plein = but, cerclé = arrêt ou occasion manquée. Tes tirs en bleu, les leurs en rouge."));
  return b;
}

function ligneEvt(e, moi) {
  const l = el("div", {class: "evt " + e.type + (e.cote === "AB"[moi] ? " mien" : "")},
    el("span", {class: "min"}, e.minute + "'"), el("span", {class: "ico"}, EVT_ICONE[e.type] || "•"),
    el("span", {class: "txt"}, e.texte));
  // d'où venait le but : une action à une passe ne raconte pas la même
  // chose qu'une action à six
  if (e.type === "but" && e.passes !== undefined)
    l.append(el("span", {class: "amont"},
      e.passes <= 1 ? "action directe" : `${e.passes} passes, parti de ${(e.depart || "").split(" ").slice(-1)[0]}`));
  return l;
}

// Le fil ne montre que ce que le terrain a DÉJÀ joué : le serveur a une
// minute d'avance, et lire le but avant de le voir, c'est le décalage
// que tout le monde remarque.
function ongletDirect(d) {
  const m = d.match, moi = d.cote === "b" ? 1 : 0;
  const p = el("div", {class: "onglet-corps"});
  const fil = el("div", {class: "fil"});
  const vus = m.evenements.map((e, i) => [e, i]).filter(([, i]) => evtVu(m, i));
  for (const [e] of vus.reverse()) fil.append(ligneEvt(e, moi));
  if (!vus.length) fil.append(el("p", {class: "compteur"}, "Le match vient de commencer."));
  p.append(fil);
  return p;
}

function panneauMatch(d, routeTac = "/lobby/tactique", routePause = "/lobby/pause", rendre = rendreLobby) {
  const m = d.match, moi = d.cote === "b" ? 1 : 0, lui = 1 - moi;
  const cote = d.cote === "b" ? "b" : "a", adv = cote === "a" ? "b" : "a";
  const bloc = el("div", {class: "ecran-match"});

  // ---- le bandeau : les deux équipes, le score, l'horloge
  const tete = el("div", {class: "panneau match-tete"});
  tete.append(el("div", {class: "mt-eq"}, el("div", {class: "nom anton"}, m.noms[moi]),
    el("div", {class: "style"}, m.style["ab"[moi]])));
  // Le score et la minute sont ceux que l'ANIMATION a montrés : le
  // serveur a une minute d'avance, et un score qui change avant que le
  // ballon n'entre gâche le but (majTete).
  const scoreEl = el("div", {class: "live-score anton"}, `${m.score[moi]} – ${m.score[lui]}`);
  const minEl = el("div", {class: "mt-min anton"}, "");
  tete.append(el("div", {class: "mt-centre"}, scoreEl, minEl));
  tete.append(el("div", {class: "mt-eq droite"}, el("div", {class: "nom anton"}, m.noms[lui]),
    // Pas ses réglages : ce qu'on en voit (simulation.lecture_adverse).
    el("div", {class: "style"}, (m.lecture?.[cote] || []).join(" · ")
      || (m.minute < 15 ? "trop tôt pour les lire" : "rien de net"))));
  const aiguille = el("i", {});
  tete.append(el("div", {class: "horloge" + (m.pause ? " suspendue" : "")}, aiguille));
  bloc.append(tete);

  // ---- le corps : compo · terrain · compo
  const corps = el("div", {class: "match-corps"});
  corps.append(colonneCompo(m, cote, true));
  corps.append(panneauTerrain(d, cote));
  corps.append(colonneCompo(m, adv, false));
  bloc.append(corps);
  T2D.tete = {m, score: scoreEl, min: minEl, horloge: aiguille, minutes: d.minutes};
  majTete();

  // ---- les onglets
  const p = el("div", {class: "panneau match-live"});
  const barre = el("div", {class: "onglets"});
  const corpsOnglet = el("div", {});
  const dessiner = () => {
    barre.querySelectorAll("button").forEach(b => b.classList.toggle("actif", b.dataset.onglet === ONGLET));
    corpsOnglet.replaceChildren(
      ONGLET === "stats" ? ongletStats(d)
      : ONGLET === "tactique" && !m.fini ? blocAjuster(d, routeTac, routePause, rendre)
      : ongletDirect(d));
  };
  for (const [cle, lib] of Object.entries(ONGLETS_MATCH)) {
    if (cle === "tactique" && m.fini) continue;
    barre.append(el("button", {"data-onglet": cle, onclick: () => { ONGLET = cle; dessiner(); }}, lib));
  }
  // Au coup de sifflet final, c'est la feuille de match qu'on veut voir,
  // pas le fil des actions qu'on vient de regarder passer.
  if (m.fini && (ONGLET === "tactique" || !MATCH_FINI_VU.has(m.rencontre_id))) {
    ONGLET = "stats";
    MATCH_FINI_VU.add(m.rencontre_id);
  }
  p.append(barre, corpsOnglet);
  dessiner();
  bloc.append(p);

  if (m.fini) {
    const r = m.resultat === "N" ? "Match nul" : ((m.resultat === "A") === (moi === 0) ? "Victoire" : "Défaite");
    const de = m.elo_apres && m.elo_apres[moi] !== null ? m.elo_apres[moi] - m.elo_avant[moi] : null;
    p.append(el("div", {class: "live-fin"}, el("b", {class: "anton"}, r),
      de === null ? el("span", {}, m.defi ? " · défi, hors classement" : "") : el("span", {}, ` · Elo ${de > 0 ? "+" : ""}${de.toFixed(1)}`),
      routeTac === "/lobby/tactique" ? el("button", {class: "primaire", onclick: () => rendreLobby()}, "Rejouer") : null));
  }
  return bloc;
}

// ---------------------------------------------------------------------------
// Le mode solo : tu prends la place d'un vrai club dans une vraie
// compétition et tu joues son calendrier contre les onze des autres, bâtis
// sur leurs cartes.  Les récompenses dépendent de la place ou du tour
// atteint (jeu/solo.py).
// ---------------------------------------------------------------------------
let SOLO = {cle: null, timer: null};

async function rendreSolo(donnees) {
  const d = donnees || await api("/solo");
  SOLO.d = d;
  const B = $("#solo-corps"); B.replaceChildren();
  const offerts = Object.values(d.packs_offerts || {}).reduce((a, b) => a + b, 0);
  $("#solo-info").textContent = offerts ? `${offerts} pack${offerts > 1 ? "s" : ""} offert${offerts > 1 ? "s" : ""} à ouvrir`
    : "Prends la place d'un club et joue sa saison";
  B.append(d.campagne ? panneauCampagne(d) : panneauChoixSolo(d));
  B.append(panneauPalmares(d));
  if (d.campagne?.match && !d.campagne.match.fini) lancerBoucleSolo();
}

function panneauChoixSolo(d) {
  const p = el("div", {class: "panneau"}, el("h3", {class: "anton"}, "Choisis ta compétition"),
    el("p", {class: "compteur"},
      "Tu remplaces un club de la compétition et tu joues son calendrier avec ton onze. "
      + "Les adversaires sont les vrais clubs, alignés avec les cartes de leurs joueurs : "
      + "quand un joueur baisse, son club baisse avec lui. Plus tu vas loin, plus tu gagnes."));
  const onglets = el("div", {class: "onglets"});
  for (const c of d.competitions)
    onglets.append(el("button", {class: SOLO.cle === c.cle ? "actif" : "",
      onclick: async () => { SOLO.cle = c.cle; await rendreSolo(SOLO.d); }},
      c.nom + (c.format === "coupe" ? " · coupe" : "")));
  p.append(onglets);
  if (!SOLO.cle) { p.append(el("p", {class: "info"}, "Choisis une compétition pour voir les clubs.")); return p; }
  const zone = el("div", {class: "clubs-solo"}, el("p", {class: "compteur"}, "Chargement…"));
  p.append(el("div", {class: "etiq"}, "Quel club remplaces-tu ?"), zone);
  api(`/solo/clubs/${SOLO.cle}`).then(r => {
    zone.replaceChildren();
    for (const c of r.clubs) {
      const k = el("div", {class: "club-solo", tabindex: "0", role: "button",
        onclick: () => demarrerSolo(r, c), onkeydown: e => { if (e.key === "Enter") demarrerSolo(r, c); }});
      k.style.setProperty("--clubc", c.couleur);
      k.append(el("img", {src: `/images/logos/${c.team_id}.png`, alt: "", loading: "lazy", onerror: e => e.target.remove()}),
        el("div", {class: "qui"}, el("div", {class: "nom"}, c.nom),
          el("div", {class: "sous"}, `effectif ${c.force}`)));
      zone.append(k);
    }
  }).catch(e => { zone.replaceChildren(el("p", {class: "avert"}, e.message)); });
  return p;
}

async function demarrerSolo(r, club) {
  if (!confirm(`Tu prends la place de ${club.nom} en ${r.nom}. C'est parti ?`)) return;
  try { await rendreSolo(await api("/solo/demarrer", {cle: r.cle, club: club.team_id})); }
  catch (e) { toast(e.message); }
}

function panneauCampagne(d) {
  const c = d.campagne;
  const p = el("div", {class: "panneau"});
  const pr = c.prochain;
  // A league round is a journée; a knockout round has a name of its own,
  // and which leg it is matters more than its number in the calendar.
  const ou = !pr ? "campagne terminée"
    : (pr.phase === "ligue" || pr.phase === "championnat")
      ? `journée ${pr.tour} sur ${c.format === "championnat" ? c.tours : 8}`
      : (PHASES_SOLO[pr.phase] || pr.libelle || "") + (pr.manche ? ` · match ${pr.manche === 1 ? "aller" : "retour"}` : "");
  p.append(el("div", {class: "tete-campagne"},
    el("div", {}, el("h3", {class: "anton"}, c.nom),
      el("div", {class: "compteur"}, `À la place de ${c.club_remplace} · ${ou}`)),
    el("button", {class: "discret", onclick: async () => {
      if (!confirm("Abandonner la campagne ? Elle ne rapportera rien.")) return;
      try { await rendreSolo(await api("/solo/abandonner", {})); } catch (e) { toast(e.message); }
    }}, "Abandonner")));
  if (c.match) { p.append(panneauMatchSolo(c)); return p; }
  const onze = C.slots.every(x => x !== null) ? C.slots.slice() : null;
  if (!onze) p.append(el("div", {class: "avert"}, "Ton onze n'est pas complet : va dans Équipe le compléter, c'est lui qui joue ici."));
  else if (c.prochain) {
    if (c.prochain.exempt) {
      p.append(el("p", {class: "info"}, "Tu es exempt cette journée : les autres jouent, toi tu regardes."));
      p.append(el("div", {class: "actions"}, el("button", {class: "primaire", onclick: () => jouerSolo(onze)}, "Passer la journée")));
    } else {
      const a = c.prochain.adversaire;
      const ligne = el("div", {class: "affiche"});
      ligne.style.setProperty("--clubc", a.couleur || "#14161E");
      ligne.append(el("img", {src: `/images/logos/${a.team_id}.png`, alt: "", onerror: e => e.target.remove()}),
        el("div", {}, el("div", {class: "etiq"}, c.prochain.domicile ? "À domicile contre" : "En déplacement à"),
          el("div", {class: "nom anton"}, a.nom),
          el("div", {class: "compteur"}, `effectif ${a.force}`
            + (c.prochain.aller ? ` · aller ${c.prochain.aller.moi} – ${c.prochain.aller.lui}` : ""))));
      p.append(ligne);
      p.append(selecteurTactique(LOBBY.tac, () => {}));
      p.append(el("div", {class: "actions"},
        el("button", {class: "primaire", onclick: () => jouerSolo(onze)},
          c.prochain.manche === 2 ? "Jouer le match retour" : "Jouer le match")));
    }
  }
  if (c.mes_matchs?.length) {
    p.append(el("div", {class: "etiq"}, "Tes derniers matchs"));
    for (const m of [...c.mes_matchs].reverse()) {
      const r = resSolo(m, c.place), chez_moi = m.a === c.place;
      p.append(el("div", {class: "ligne simple"},
        el("span", {class: "res " + r}, r),
        el("div", {class: "qui"}, el("div", {class: "nom"}, (chez_moi ? "" : "à ") + m.adversaire),
          el("div", {class: "sous"}, PHASES_SOLO[m.phase]
            ? PHASES_SOLO[m.phase] + (m.manche ? (m.manche === 1 ? " · aller" : " · retour") : "")
            : `journée ${m.tour + 1}`)),
        el("b", {class: "num"}, scoreSolo(m, c.place))));
    }
  }
  if (c.classement?.length)
    p.append(el("div", {class: "etiq"}, c.format === "championnat" ? "Classement" : "Phase de ligue"),
      tableauClassement(c.classement, c.qualification));
  if (c.tableau?.length) p.append(el("div", {class: "etiq"}, "Tableau final"), tableauCoupe(c.tableau));
  return p;
}

// A campaign match is played LIVE, on the same clock and the same pitch as
// a lobby match: you watch it, you adjust, you make your changes.
// Un match de campagne se joue sur LE MÊME écran qu'un match du lobby :
// il n'y a qu'une façon de regarder un match dans ce jeu.
function panneauMatchSolo(c) {
  const d = {match: c.match, cote: "a", duree: c.match.duree, minutes: c.match.minutes};
  const b = el("div", {});
  b.append(panneauMatch(d, "/solo/tactique", "/solo/pause", rendreSolo));
  if (c.match.fini) b.append(el("p", {class: "compteur"}, "Match terminé, la journée se clôture…"));
  return b;
}

// V / N / D and the score seen from your side: `a` and `b` are PLACES in
// the field, and `place` is the one the campaign holds for you.
function resSolo(m, place) {
  if (m.resultat === "N") return "N";
  return (m.resultat === "A") === (m.a === place) ? "V" : "D";
}
function scoreSolo(m, place) {
  const [x, y] = m.a === place ? m.score : [m.score[1], m.score[0]];
  return `${x} – ${y}`;
}

// The league-phase table doubles as the qualification board: the top eight
// go straight to the last sixteen, nine to twenty-four to the play-off,
// the rest are out.  Colouring the rows says it without a legend.
function tableauClassement(lignes, qual) {
  const t = el("div", {class: "table-solo"});
  t.append(el("div", {class: "tl tete"}, el("span", {}, "#"), el("span", {}, "Club"),
    el("b", {}, "J"), el("b", {}, "G"), el("b", {}, "N"), el("b", {}, "P"), el("b", {}, "Diff"), el("b", {}, "Pts")));
  for (const l of lignes) {
    const zone = qual ? (l.rang <= qual.directs ? " direct" : l.rang <= qual.barrages ? " barrage" : " dehors") : "";
    t.append(el("div", {class: "tl" + (l.toi ? " moi" : "") + zone}, el("span", {}, String(l.rang)),
      el("span", {class: "nom"}, l.nom), el("b", {}, String(l.j)), el("b", {}, String(l.g)),
      el("b", {}, String(l.n)), el("b", {}, String(l.p)),
      el("b", {}, (l.bp - l.bc > 0 ? "+" : "") + (l.bp - l.bc)), el("b", {class: "pts"}, String(l.pts))));
  }
  if (qual) t.append(el("p", {class: "compteur"},
    `Les ${qual.directs} premiers passent directement en huitièmes, du ${qual.directs + 1}ᵉ au ${qual.barrages}ᵉ par les barrages, les autres sont éliminés.`));
  return t;
}

const PHASES_SOLO = {barrage: "Barrages", "8": "Huitièmes de finale", "4": "Quarts de finale",
  "2": "Demi-finales", F: "Finale"};

// One column per phase, each tie with its AGGREGATE over the two legs —
// that is what decides it, so that is what the bracket shows.
function tableauCoupe(phases) {
  const t = el("div", {class: "bracket"});
  for (const ph of phases) {
    const col = el("div", {class: "bcol"}, el("div", {class: "etiq"}, ph.libelle));
    for (const d of ph.ties)
      col.append(el("div", {class: "btie" + (d.toi ? " moi" : "") + (d.vainqueur ? " fini" : "")},
        el("span", {class: d.vainqueur === d.a ? "gagne" : ""}, d.a),
        el("b", {}, d.cumul ? `${d.cumul[0]}–${d.cumul[1]}` : "—"),
        el("span", {class: d.vainqueur === d.b ? "gagne" : ""}, d.b)));
    t.append(col);
  }
  return t;
}

async function jouerSolo(onze) {
  // Read your place BEFORE playing: a campaign that ends on this round
  // leaves no campagne in the answer, and reading the place from it then
  // fell back to the home side — a defeat away from home was announced as
  // a victory.
  const place = SOLO.d?.campagne?.place;
  let r;
  try { r = await api("/solo/jouer", {formation: C.formation, onze, banc: C.banc.slice(0, BANC_MAX), tactique: LOBBY.tac}); }
  catch (e) { toast(e.message); return; }
  await rafraichir(false);
  await rendreSolo(r);
  // your match kicks off live; only an exempt round resolves at once
  if (!r.tour_joue) { lancerBoucleSolo(); return; }
  const mien = (r.tour_joue.feuilles || []).find(f => f.mien);
  if (mien) montrerFeuilleSolo(mien, r.tour_joue.fini ? r.tour_joue.bilan : null, place);
  else if (r.tour_joue.fini) montrerBilanSolo(r.tour_joue.bilan);
}

// The campaign screen polls like the lobby while a match is running: the
// clock belongs to the server, so the page asks it rather than counting.
function lancerBoucleSolo() {
  if (SOLO.timer) return;
  SOLO.timer = setInterval(async () => {
    if (G.ecran !== "solo") { arreterBoucleSolo(); return; }
    try {
      const avant = SOLO.d?.campagne?.tour;
      const d = await api("/solo");
      const fini = !d.campagne?.match;
      await rendreSolo(d);
      if (fini) {
        arreterBoucleSolo();
        await rafraichir(false);
        const c = d.campagne;
        const dernier = c?.mes_matchs?.[c.mes_matchs.length - 1];
        if (!c) {
          // the campaign is over: its summary is the newest line of the palmarès
          const fini = d.palmares?.[0];
          if (fini) montrerBilanSolo(fini);
        } else if (c.tour !== avant && dernier) {
          montrerFeuilleSolo(dernier, null, c.place);
        }
      }
    } catch (e) { arreterBoucleSolo(); }
  }, 2500);
}
function arreterBoucleSolo() { if (SOLO.timer) { clearInterval(SOLO.timer); SOLO.timer = null; } }

// `bilan` is the campaign's closing summary when this match ended it, and
// null otherwise.  It used to be dug out of the play response, which the
// live path does not have: the dialog threw and never opened at all.
function montrerFeuilleSolo(f, bilan, place) {
  const dlg = $("#fiche"); dlg.replaceChildren();
  const chez_moi = f.a === place;
  const box = el("div", {class: "fiche"}, el("h3", {class: "anton"}, scoreSolo(f, place)),
    el("p", {class: "compteur"},
      `${{V: "Victoire", N: "Match nul", D: "Défaite"}[resSolo(f, place)]}`
      + ` · possession ${chez_moi ? f.possession[0] : f.possession[1]} %`
      + ` · tirs ${chez_moi ? f.tirs[0] : f.tirs[1]} contre ${chez_moi ? f.tirs[1] : f.tirs[0]}`));
  const fil = el("div", {class: "fil"});
  for (const e of f.evenements)
    fil.append(el("div", {class: "evt " + e.type},
      el("span", {class: "min"}, e.minute + "'"), el("span", {class: "ico"}, EVT_ICONE[e.type] || "•"),
      el("span", {class: "txt"}, e.texte)));
  if (!f.evenements.length) fil.append(el("p", {class: "compteur"}, "Match sans fait marquant."));
  box.append(fil);
  const acts = el("div", {class: "actions"});
  if (bilan) acts.append(el("button", {class: "primaire", onclick: () => { dlg.close(); montrerBilanSolo(bilan); }}, "Voir le bilan"));
  else acts.append(el("button", {class: "primaire", onclick: () => dlg.close()}, "Journée suivante"));
  box.append(acts); dlg.append(box); dlg.showModal();
}

function montrerBilanSolo(b) {
  if (!b) return;
  const dlg = $("#fiche"); dlg.replaceChildren();
  const box = el("div", {class: "fiche bilan"}, el("h3", {class: "anton"}, b.libelle),
    el("p", {class: "compteur"}, b.rang ? `${b.rang}${b.rang === 1 ? "er" : "e"} sur ${b.sur} · ${b.victoires} victoires, ${b.nuls} nuls en ${b.matchs} matchs`
      : `${b.tour || ""} · ${b.victoires} victoires en ${b.matchs} matchs`));
  box.append(el("div", {class: "gains"},
    el("div", {class: "tuile"}, el("div", {class: "etiq"}, "Crédits"), el("b", {class: "anton"}, fM(b.credits))),
    ...Object.entries(b.packs || {}).map(([t, n]) =>
      el("div", {class: "tuile"}, el("div", {class: "etiq"}, "Packs " + TIER_TXT[t]), el("b", {class: "anton"}, "× " + n)))));
  box.append(el("div", {class: "actions"},
    el("button", {onclick: () => { dlg.close(); montrer("packs"); }}, "Ouvrir mes packs"),
    el("button", {class: "primaire", onclick: () => { dlg.close(); rendreSolo(); }}, "Nouvelle campagne")));
  dlg.append(box); dlg.showModal();
}

function panneauPalmares(d) {
  const p = el("div", {class: "panneau"}, el("h3", {class: "anton"}, "Palmarès"));
  if (!d.palmares?.length) { p.append(el("p", {class: "compteur"}, "Aucune campagne terminée.")); return p; }
  for (const c of d.palmares)
    p.append(el("div", {class: "ligne simple"},
      el("div", {class: "qui"}, el("div", {class: "nom"}, c.competition),
        el("div", {class: "sous"}, c.libelle + (c.rang ? ` · ${c.rang}${c.rang === 1 ? "er" : "e"} sur ${c.sur}` : c.tour ? ` · ${c.tour}` : ""))),
      el("b", {class: "num"}, fM(c.credits || 0)),
      el("span", {class: "compteur"}, Object.entries(c.packs || {}).map(([t, n]) => `${n} ${TIER_TXT[t]}`).join(", ") || "—")));
  return p;
}

// ---------------------------------------------------------------------------
// Le terrain 2D : les vingt-deux cartes jouent le match.
//
// Le moteur donne `fil`, une ligne par minute, et dans chaque ligne `s` :
// les PHASES de cette minute — la relance, les passes, la conduite, le
// tir, le sifflet, la perte de balle.  Le terrain ne devine donc rien du
// tout : il rejoue ces phases une à une, déplace le ballon sur celui qui
// l'a, fait partir le tir vers le but, arrête les joueurs au coup de
// sifflet et les relance après.  L'horloge est celle du serveur : on
// avance d'une minute toutes les `duree / 90` secondes, réparties entre
// les phases, et on se recale à chaque réponse.
// ---------------------------------------------------------------------------
const T2D = {timer: null, m: 0, fil: [], evts: [], cle: null, cible: 0, noeud: null,
             dernier: null, phases: [], i: 0, pas: 2700, arret: false,
             vus: new Set(), score: null, attente: null, rid: null, tete: null, delais: []};

// Le placement d'un onze sur le terrain, ligne par ligne, à partir de la
// formation réelle : x = profondeur (0 = sa propre ligne de but), y en
// largeur.  Le bloc coulisse en x selon la zone de jeu.
const PROFONDEUR = {GK: 0.05, DEF: 0.20, MID: 0.40, FWD: 0.62};
const GLISSE_2D = 0.13;        // de combien un bloc avance par zone

function placesDe(joueurs, formation) {
  // Les rangs de la formation donnent la vraie silhouette : un 3-4-2-1
  // ne se dessine pas comme un 4-4-2.  Faute de formation connue, on
  // retombe sur les familles.
  const rangs = formation && RANGS[formation] ? RANGS[formation] : null;
  if (rangs && rangs.flat().length === joueurs.length) {
    // La profondeur d'une ligne vient de son RANG, pas de la famille de
    // son premier poste : le milieu d'un 4-4-2 commence par un ailier,
    // donc il se posait à la profondeur des attaquants et les deux
    // lignes se superposaient.  Le gardien devant son but, les autres
    // lignes réparties jusqu'au dernier tiers.
    const n = rangs.length;
    const out = [];
    rangs.forEach((rang, r) => {
      const x = r === 0 ? PROFONDEUR.GK : 0.20 + (0.46 * (r - 1)) / Math.max(1, n - 2);
      // le pivot derrière ses relayeurs, le meneur devant : le triangle
      // du milieu se lit sur le terrain
      rang.forEach((poste, k) => out.push([x + (PROF_POSTE[poste] || 0), (k + 1) / (rang.length + 1)]));
    });
    return out;
  }
  const pris = {GK: 0, DEF: 0, MID: 0, FWD: 0};
  const total = {GK: 0, DEF: 0, MID: 0, FWD: 0};
  for (const j of joueurs) total[PROFONDEUR[j.fam] !== undefined ? j.fam : "MID"]++;
  return joueurs.map(j => {
    const fam = PROFONDEUR[j.fam] !== undefined ? j.fam : "MID";
    const k = pris[fam]++;
    return [PROFONDEUR[fam], (k + 1) / (total[fam] + 1)];
  });
}

function terrain2d() {
  const t = el("div", {class: "terrain2d"});
  t.append(el("div", {class: "t2d-fond"},
    el("div", {class: "t2d-ligne-mediane"}), el("div", {class: "t2d-rond"}),
    el("div", {class: "t2d-surface gauche"}), el("div", {class: "t2d-surface droite"}),
    el("div", {class: "t2d-but gauche"}), el("div", {class: "t2d-but droite"})));
  t.append(el("div", {class: "t2d-jeu"}), el("div", {class: "t2d-ballon"}),
    el("div", {class: "t2d-bandeau", hidden: true}), el("div", {class: "t2d-popup", hidden: true}));
  return t;
}

// On dessine les vingt-deux cartes UNE FOIS ; ensuite seuls leur position
// et leur barre d'endurance changent, donc une phase coûte deux écritures
// de style par joueur et rien n'est reconstruit.
function peuplerTerrain(t, m, moi) {
  const jeu = t.querySelector(".t2d-jeu");
  jeu.replaceChildren();
  T2D.pions = {};
  for (const cote of ["a", "b"]) {
    const tous = [...(m.onze?.[cote] || []), ...(m.banc?.[cote] || [])];
    const joueurs = (m.sur_le_terrain?.[cote] || []).map(pid => tous.find(j => j.pid === pid)).filter(Boolean);
    const places = placesDe(joueurs, m.formation?.[cote]);
    joueurs.forEach((j, i) => {
      const p = el("div", {class: "t2d-pion " + (cote === moi ? "mien" : "adverse"),
        title: `${j.nom} · ${j.ovr}${j.slot ? " · " + j.slot : ""}`});
      p.append(el("span", {class: "t2d-anneau"}), carteDessinee(j, 120),
        el("span", {class: "t2d-jauge"}, el("i", {})),
        el("span", {class: "t2d-nom"}, (j.nom || "").split(" ").slice(-1)[0]));
      p.dataset.pid = j.pid; p.dataset.cote = cote;
      p._base = places[i] || [0.4, 0.5];
      p._poste = j.slot || j.poste || "Milieu relayeur";
      jeu.append(p);
      T2D.pions[cote + ":" + j.pid] = p;
    });
  }
}

// Les barres d'endurance : ce que le manager regarde pour décider de
// sortir quelqu'un.  Le moteur donne l'endurance restante de chacun.
function jauges(m) {
  if (!T2D.pions) return;
  for (const cote of ["a", "b"]) {
    const e = m.endurance?.[cote] || {};
    for (const [pid, v] of Object.entries(e)) {
      const p = T2D.pions[cote + ":" + pid];
      const i = p && p.querySelector(".t2d-jauge i");
      if (!i) continue;
      i.style.width = Math.max(0, Math.min(100, v)) + "%";
      i.className = v < 35 ? "vide" : v < 60 ? "basse" : "";
    }
  }
}

// Où se trouve un point du terrain À L'ÉCRAN.  Tu attaques toujours vers
// la droite, quel que soit ton côté de la feuille, donc le camp adverse
// est dessiné en miroir.
function ecran(cote, x, y, moi) {
  // Les deux camps jouent la même forme en miroir : sans écart, leurs
  // milieux se posent exactement au même endroit et les noms se
  // chevauchent.  On les décale en largeur ET en profondeur, chacun d'un
  // côté, pour que les vingt-deux restent lisibles.
  const mien = cote === moi;
  const xx = Math.max(0.02, Math.min(0.98, x + (mien ? -0.018 : 0.018)));
  const gauche = mien ? xx : 1 - xx;
  const haut = (mien ? y : 1 - y) + (mien ? -0.055 : 0.055);
  return [gauche, Math.max(0.05, Math.min(0.95, haut))];
}

// Le but qu'attaque un camp, à l'écran.
function buts(cote, moi, t) {
  const gauche = cote === moi ? 0.975 : 0.025;
  return [gauche, 0.5 + ((t === undefined ? 0.5 : t) - 0.5) * 0.30];
}

// ---------------------------------------------------------------------------
// Les déplacements sans ballon.
//
// Faire coulisser deux blocs rigides ne ressemble pas à du football : un
// latéral qui monte dépasse son ailier, un ailier qui repique laisse le
// couloir, les centraux se resserrent quand ils défendent, les
// attaquants rentrent dans la surface sur une frappe.  Chaque poste a
// donc sa façon de bouger quand son camp a le ballon et quand il ne
// l'a pas, et les consignes du manager la modifient — ce qu'il demande
// à ses latéraux se VOIT.
//
// C'est du dessin, pas du moteur : rien ici ne touche au résultat.  Le
// résultat, lui, écoute les mêmes consignes par les traits d'équipe
// (simulation.CONSIGNES).
//
//   av  — de combien il avance quand son camp attaque (en fraction de
//         terrain, à pleine progression)
//   rec — de combien il recule quand son camp défend (négatif)
//   lar — positif : il s'écarte vers la touche ; négatif : il rentre
//         dans l'axe.  Nul pour un joueur déjà axial.
const JEU_POSTE = {
  "Gardien":           {av: 0.030, rec: 0.000, lar: 0.00, surface: 0.00},
  "Defenseur central": {av: 0.110, rec: -0.055, lar: -0.12, surface: 0.02},
  "Lateral":           {av: 0.300, rec: -0.045, lar: 0.10, surface: 0.10},
  "Milieu defensif":   {av: 0.120, rec: -0.120, lar: -0.18, surface: 0.05},
  "Milieu relayeur":   {av: 0.210, rec: -0.165, lar: -0.06, surface: 0.20},
  "Milieu offensif":   {av: 0.235, rec: -0.205, lar: -0.12, surface: 0.35},
  "Ailier":            {av: 0.200, rec: -0.225, lar: 0.26, surface: 0.40},
  "Ailier droit":      {av: 0.200, rec: -0.225, lar: 0.26, surface: 0.40},
  "Ailier gauche":     {av: 0.200, rec: -0.225, lar: 0.26, surface: 0.40},
  "Buteur":            {av: 0.160, rec: -0.265, lar: -0.16, surface: 0.55},
};
const JEU_DEFAUT = {av: 0.18, rec: -0.15, lar: 0.0, surface: 0.2};
// Ce que les consignes changent au DESSIN, poste par poste.
const CONSIGNE_JEU = {
  lateraux:   {poste: ["Lateral"],
               bas: {av: -0.20, lar: -0.02}, axe: {av: -0.07, lar: -0.26}},
  ailiers:    {poste: ["Ailier", "Ailier droit", "Ailier gauche"],
               ligne: {lar: 0.16}, interieur: {lar: -0.36, av: 0.05, surface: 0.12}},
  milieux:    {poste: ["Milieu defensif", "Milieu relayeur", "Milieu offensif"],
               projection: {av: 0.14, surface: 0.18}, bas: {av: -0.11, surface: -0.10},
               lateral: {lar: 0.24}},
  attaquants: {poste: ["Buteur"],
               profondeur: {av: 0.12}, pivot: {av: -0.07, surface: -0.08}},
  relance:    {poste: ["Gardien", "Defenseur central"],
               courte: {av: 0.05}, longue: {av: -0.03}},
};

function consigneDe(poste, tac) {
  const out = {av: 0, rec: 0, lar: 0, surface: 0};
  if (!tac) return out;
  for (const [axe, def] of Object.entries(CONSIGNE_JEU)) {
    if (!def.poste.includes(poste)) continue;
    const d = def[tac[axe]];
    if (d) for (const k of Object.keys(out)) out[k] += d[k] || 0;
  }
  return out;
}

// Où se place un joueur pour CETTE phase, dans son propre repère
// (x = profondeur vers le but adverse, y = largeur).
function placeJoueur(p, avecBallon, progression, ph, tac) {
  const [bx, by] = p._base;
  const r = JEU_POSTE[posteBase(p._poste)] || JEU_DEFAUT;
  const c = consigneDe(posteBase(p._poste), tac);
  const ecart = by - 0.5;
  const sens = ecart === 0 ? 0 : Math.sign(ecart);
  // Se resserrer, oui ; se marcher dessus, non.  Deux centraux qui
  // rentrent finissaient sur la même case : chacun garde au moins la
  // moitié de son écart de départ à l'axe.
  const garder = y => ecart >= 0 ? Math.max(0.5 + ecart * 0.55, y) : Math.min(0.5 + ecart * 0.55, y);
  let x = bx, y = by;
  if (avecBallon) {
    x += (r.av + c.av) * progression;
    y = garder(by + sens * (r.lar + c.lar) * progression * 0.42);
    // Sur une frappe, ceux qui attaquent rentrent dans la surface : ils
    // convergent vers le point de penalty au lieu de rester en ligne.
    if (SUR_LE_BUT.has(ph.k)) {
      const dans = Math.max(0, Math.min(1, r.surface + c.surface));
      x += (0.86 - x) * dans;
      y += (0.5 - y) * dans * 0.55;
    }
  } else {
    x += (r.rec + c.rec * 0.4) * progression;
    y = garder(by - sens * 0.22 * progression * 0.42);     // le bloc se resserre
    if (SUR_LE_BUT.has(ph.k)) {
      // on défend sa surface : la ligne et le gardien couvrent le but
      const dans = p._poste === "Gardien" ? 0 : Math.max(0, 0.55 - r.surface);
      x -= (x - 0.13) * dans;
      y += (0.5 - y) * dans * 0.45;
    }
  }
  return [Math.max(0.02, Math.min(0.96, x)), Math.max(0.04, Math.min(0.96, y))];
}
const SUR_LE_BUT = new Set(["tir", "but", "rate", "arret", "corner", "centre"]);

// ---------------------------------------------------------------------------
// Le ballon a une position, et tout le monde joue par rapport à lui.
//
// Avant, le ballon SAUTAIT sur le pion de celui qui l'avait et les deux
// blocs coulissaient d'un cran par zone : on ne voyait ni d'où venait une
// passe, ni un côté, ni un siège.  Le moteur donne maintenant à chaque
// phase une profondeur (z) et une largeur (y) dans le repère du porteur,
// et chaque minute repart d'où la précédente s'est arrêtée.  Ici :
//
//   - le ballon est dessiné À SA POSITION, et il y va en un temps qui
//     dépend de la distance (une ouverture prend plus de temps qu'une
//     remise) ;
//   - le porteur VIENT au ballon, il ne se le fait pas téléporter ;
//   - les deux blocs coulissent vers le ballon, celui qui défend plus
//     que celui qui attaque, ce qui fait la compacité d'un bloc et le
//     dessin d'un siège ;
//   - deux coéquipiers se proposent en soutien, l'adversaire le plus
//     proche vient au contact ;
//   - chacun respire un peu autour de sa place, personne n'est aligné
//     au laser.
//
// Tout ceci est du dessin : le résultat vient du moteur et rien ici ne
// le touche.
// ---------------------------------------------------------------------------
const ZONE_X = {0: 0.07, 1: 0.30, 2: 0.58, 3: 0.84};
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

// (x, y) du ballon dans le repère du camp de la phase
function ballonDe(ph) {
  return [ZONE_X[ph.z] ?? 0.4, ph.y === undefined ? 0.5 : ph.y];
}

// Un petit écart propre à chaque joueur et à chaque minute : il change
// lentement, ce qui donne du vivant sans donner de la nervosité.
function grain(pid, minute) {
  let h = (pid * 2654435761 + minute * 97) >>> 0;
  h ^= h >>> 13; h = Math.imul(h, 0x5bd1e995) >>> 0; h ^= h >>> 15;
  const a = ((h & 0xffff) / 0xffff - 0.5) * 0.05;
  const b = (((h >>> 16) & 0xffff) / 0xffff - 0.5) * 0.06;
  return [a, b];
}

function bougerTerrain(t, cote, zone, moi, ph) {
  if (!T2D.pions) return;
  const phase = ph || {k: "passe", z: zone, c: cote, y: 0.5, p: null};
  if (phase.c === undefined || phase.c === null) return;
  // la progression : 0 devant son propre but, 1 dans la surface adverse
  const progression = clamp(((phase.z === undefined ? 1 : phase.z) - 0.5) / 2.5, 0, 1);
  const [bx, by] = ballonDe(phase);
  const camp = "ab"[phase.c];
  const porteurCle = camp + ":" + phase.p;
  const places = {};
  for (const [cle, p] of Object.entries(T2D.pions)) {
    const c = cle.slice(0, 1);
    const sien = c === camp;
    // le ballon vu de CE camp
    const yb = sien ? by : 1 - by;
    let [x, y] = placeJoueur(p, sien, progression, phase, T2D.consignes?.[c]);
    // le bloc coulisse vers le ballon, celui qui défend davantage
    y += (yb - 0.5) * (sien ? 0.16 : 0.28);
    const g = grain(+p.dataset.pid, T2D.m);
    x += g[0]; y += g[1];
    places[cle] = {x, y, sien, gk: posteBase(p._poste) === "Gardien"};
  }
  const porteur = places[porteurCle];
  if (porteur) {
    // le porteur vient au ballon ; sur une frappe il est déjà là
    porteur.x = bx; porteur.y = by;
    if (!SUR_LE_BUT.has(phase.k) && !ARRETS_JEU.has(phase.k)) {
      const dist = v => Math.hypot(v.x - bx, v.y - by);
      // deux soutiens se proposent
      const soutiens = Object.entries(places)
        .filter(([cle, v]) => cle !== porteurCle && v.sien && !v.gk)
        .sort((a, b) => dist(a[1]) - dist(b[1])).slice(0, 2);
      for (const [, v] of soutiens) { v.x += (bx - v.x) * 0.22; v.y += (by - v.y) * 0.22; }
      // et l'adversaire le plus proche vient au contact — dans SON repère
      // le ballon est en miroir
      const bxa = 1 - bx, bya = 1 - by;
      const presseur = Object.entries(places)
        .filter(([, v]) => !v.sien && !v.gk)
        .sort((a, b) => Math.hypot(a[1].x - bxa, a[1].y - bya) - Math.hypot(b[1].x - bxa, b[1].y - bya))[0];
      if (presseur) { const v = presseur[1]; v.x += (bxa - v.x) * 0.45; v.y += (bya - v.y) * 0.45; }
    }
  }
  for (const [cle, p] of Object.entries(T2D.pions)) {
    const c = cle.slice(0, 1), v = places[cle];
    const [g, h] = ecran(c, clamp(v.x, 0.02, 0.96), clamp(v.y, 0.04, 0.96), moi);
    p.style.left = (g * 100) + "%";
    p.style.top = (h * 100) + "%";
    // le porteur arrive avec le ballon, les autres à leur rythme
    p.style.transitionDuration = cle === porteurCle && T2D.dureeBallon ? T2D.dureeBallon + "ms" : "";
  }
}

// Une phase : le ballon va où elle dit, le porteur s'allume, et pour un
// tir le ballon quitte vraiment le pied pour aller au but.
function jouerPhase(t, ph, moi) {
  const b = t.querySelector(".t2d-ballon");
  const jeu = t.querySelector(".t2d-jeu");
  if (!ph) { b.hidden = true; return; }
  const cote = "ab"[ph.c];
  bougerTerrain(t, ph.c, ph.z, moi, ph);
  for (const p of Object.values(T2D.pions || {}))
    p.classList.toggle("ballon", p.dataset.cote === cote && +p.dataset.pid === ph.p);
  b.classList.toggle("tir", ph.k === "tir" || ph.k === "rate");
  b.classList.toggle("dedans", ph.k === "but");
  T2D.arret = ARRETS_JEU.has(ph.k);
  jeu.classList.toggle("arret", T2D.arret);
  jeu.classList.toggle("celebre", ph.k === "but");
  b.style.transitionDuration = (T2D.dureeBallon || 400) + "ms";
  if (ph.k === "tir" || ph.k === "but" || ph.k === "rate") {
    // une frappe manquée ne revient pas dans les pieds du tireur : elle
    // file à côté du but
    const [g, h] = buts(cote, moi, ph.k === "rate" ? (T2D.dernierTir ?? 0.5) : ph.t);
    const dehors = ph.k === "rate" ? (h < 0.5 ? -0.10 : 0.10) : 0;
    if (ph.k === "tir") T2D.dernierTir = ph.t;
    if (ph.k !== "but") b.style.transitionDuration = "300ms";
    b.style.left = (g * 100) + "%";
    b.style.top = ((h + dehors) * 100) + "%";
    b.hidden = false;
  } else {
    const [bx, by] = ballonDe(ph);
    const [g, h] = ecran(cote, bx, by, moi);
    b.style.left = (g * 100) + "%";
    b.style.top = (h * 100) + "%";
    b.hidden = false;
  }
  // L'événement de la minute s'annonce QUAND sa phase se joue — le but
  // quand le ballon entre, la faute au coup de sifflet — jamais avant.
  if (T2D.attente && ph.k === T2D.attente.k) voir(T2D.attente.idx, T2D.attente.evt);
  // le libellé d'action vit dans la légende, au-dessus du terrain
  // Le commentaire vient du moteur (simulation.PHRASES) : il est tiré du
  // même générateur que la séquence, donc rejouer un match redonne mot
  // pour mot le même récit.  L'étiquette ne sert que de secours.
  const nom = T2D.noeud && T2D.noeud.querySelector(".t2d-action");
  if (nom) {
    const porteur = T2D.pions?.[cote + ":" + ph.p];
    const j = porteur ? porteur.getAttribute("title").split(" · ")[0] : "";
    nom.textContent = ph.d || (PHASE_TXT[ph.k] || "") + (j ? " — " + j : "");
    nom.className = "t2d-action " + ph.k;
  }
}

const ARRETS_JEU = new Set(["faute", "horsjeu", "but", "blessure", "carton", "penalty"]);
const PHASE_TXT = {
  relance: "Relance", passe: "Passe", conduite: "Il perce", tir: "Frappe !", but: "BUT",
  arret: "Arrêt du gardien", rate: "À côté", degagement: "Dégagement", perte: "Perte de balle",
  duel: "Duel", faute: "Faute — coup de sifflet", carton: "Carton", coupfranc: "Coup franc",
  corner: "Corner", centre: "Centre", horsjeu: "Hors-jeu", engagement: "Engagement",
  blessure: "Blessure — le jeu est arrêté", circulation: "Ça circule", ouverture: "Renversement",
  retrait: "En retrait", recuperation: "Récupération", penalty: "Penalty",
};

function annoncer(t, evt) {
  const bandeau = t.querySelector(".t2d-bandeau");
  if (!evt) { bandeau.hidden = true; return; }
  bandeau.replaceChildren(el("span", {class: "ico"}, EVT_ICONE[evt.type] || "•"),
    el("span", {class: "txt"}, evt.texte));
  bandeau.className = "t2d-bandeau " + evt.type;
  bandeau.hidden = false;
}

// Un but, un rouge, un penalty : ça se voit en plein terrain, pas dans
// un bandeau de bas de page.
const DUREE_POPUP = 3800;
function surgir(t, evt, moi) {
  const p = t.querySelector(".t2d-popup");
  if (!p) return;
  clearTimeout(T2D.popupTimer);
  moi = moi === "b" || moi === 1 ? 1 : 0;                 // T2D.moi est « a » ou « b »
  const mien = evt.cote === "AB"[moi];
  let titre, sous, classe = evt.type;
  if (evt.type === "but") {
    titre = evt.penalty ? "PENALTY TRANSFORMÉ" : "BUT !";
    sous = (evt.nom || "") + (evt.passeur && !evt.penalty ? ` · servi par ${(evt.passeur || "").split(" ").slice(-1)[0]}` : "");
  } else if (evt.type === "rouge") { titre = "CARTON ROUGE"; sous = evt.texte; }
  else if (evt.type === "penalty_manque") { titre = "PENALTY MANQUÉ"; sous = evt.texte; }
  else return;
  const score = evt.score ? (moi === 0 ? `${evt.score[0]} – ${evt.score[1]}` : `${evt.score[1]} – ${evt.score[0]}`) : "";
  p.replaceChildren(el("div", {class: "titre anton"}, titre),
    el("div", {class: "sous"}, sous),
    score ? el("div", {class: "score anton"}, score) : null);
  p.className = "t2d-popup on " + classe + (mien ? " mien" : " adverse");
  p.hidden = false;
  T2D.popupTimer = setTimeout(() => { p.classList.remove("on"); p.hidden = true; }, DUREE_POPUP);
}

// Un événement est VU quand sa phase s'est jouée : c'est là qu'il entre
// dans le score, dans le fil et dans le bandeau.
function voir(idx, evt) {
  T2D.attente = null;
  if (idx === null || idx === undefined || T2D.vus.has(idx)) return;
  T2D.vus.add(idx);
  T2D.dernier = {evt, quand: Date.now()};
  if (evt.type === "but" && evt.score) T2D.score = evt.score.slice();
  if (T2D.t) { annoncer(T2D.t, evt); surgir(T2D.t, evt, T2D.moi); }
  majTete();
  // le fil du direct, s'il est ouvert, reçoit la ligne tout de suite
  const fil = document.querySelector(".match-live .fil");
  if (fil) { fil.querySelector(".compteur")?.remove(); fil.prepend(ligneEvt(evt, T2D.moi === "b" ? 1 : 0)); }
}

// Le moteur d'animation : une phase à la fois, enchaînées par setTimeout
// plutôt que par un intervalle fixe — le nombre de phases change d'une
// minute à l'autre, et un arrêt de jeu dure plus longtemps qu'une passe.
const POIDS_PHASE = {faute: 1.8, horsjeu: 1.6, but: 2.4, blessure: 2.2, carton: 1.5,
                     tir: 1.2, arret: 1.4, coupfranc: 1.2, corner: 1.3, penalty: 1.8, engagement: 1.2};
// quelle phase porte l'événement de la minute
const EVT_PHASE = {but: "but", arret: "arret", occasion: "rate", corner: "corner", faute: "faute",
                   jaune: "carton", rouge: "carton", horsjeu: "horsjeu", blessure: "blessure",
                   penalty_manque: "arret"};

// Le temps de chaque phase de la minute : au poids de la phase, plus
// long quand le ballon voyage loin, le tout ramené à la durée d'une
// minute pour ne jamais prendre de retard sur l'horloge du serveur.
function delaisDe(phases) {
  if (!phases.length) return [];
  let prev = null;
  const brut = phases.map(ph => {
    const [x, y] = ballonDe(ph);
    const abs = ph.c === 0 ? [x, y] : [1 - x, 1 - y];
    const d = prev ? Math.hypot(abs[0] - prev[0], abs[1] - prev[1]) : 0.3;
    prev = abs;
    return (POIDS_PHASE[ph.k] || 0.9) * (0.65 + 1.2 * Math.min(1, d));
  });
  const total = brut.reduce((a, b) => a + b, 0);
  const budget = T2D.pas * 0.92;
  return brut.map(w => Math.max(220, budget * w / total));
}

function chargerMinute() {
  // une minute qui finit sans avoir montré son événement le montre
  // quand même : rien ne doit rester dans le score sans passer par le fil
  if (T2D.attente) voir(T2D.attente.idx, T2D.attente.evt);
  T2D.m += 1;
  const ligne = T2D.fil[T2D.m - 1];
  T2D.phases = (ligne && ligne.s) || [];
  T2D.delais = delaisDe(T2D.phases);
  T2D.i = 0;
  const idx = ligne && ligne.e !== null && ligne.e !== undefined ? ligne.e : null;
  const evt = idx !== null ? T2D.evts[idx] : null;
  if (evt) {
    const k = EVT_PHASE[evt.type];
    if (k && T2D.phases.some(ph => ph.k === k)) T2D.attente = {idx, evt, k};
    else voir(idx, evt);                     // un changement, une tactique : dès la minute
  }
  majTete();
  if (!T2D.phases.length && ligne) bougerTerrain(T2D.t, ligne.c, ligne.z, T2D.moi);
}

function battre() {
  const t = T2D.t, moi = T2D.moi;
  if (!t) return 400;
  if (T2D.i >= T2D.phases.length) {
    if (T2D.m >= T2D.cible) { reAnnoncer(t); return 400; }
    // en retard de plus de deux minutes (onglet en arrière-plan, réseau) :
    // on saute jusqu'à l'avant-dernière minute plutôt que de rejouer tout
    while (T2D.cible - T2D.m > 2) chargerMinute();
    chargerMinute();
    if (!T2D.phases.length) { reAnnoncer(t); return 300; }
  }
  const ph = T2D.phases[T2D.i];
  const delai = T2D.delais[T2D.i] || 400;
  T2D.i += 1;
  T2D.dureeBallon = Math.round(delai * 0.7);
  jouerPhase(t, ph, moi);
  reAnnoncer(t);
  return delai;
}

function programmer(d) {
  clearTimeout(T2D.timer);
  T2D.timer = setTimeout(() => { T2D.timer = null; programmer(battre()); }, Math.max(120, d));
}

function arreterTerrain(oublier) {
  if (T2D.timer) { clearTimeout(T2D.timer); T2D.timer = null; }
  if (oublier) {
    T2D.noeud = null; T2D.cle = null; T2D.m = 0; T2D.dernier = null; T2D.phases = []; T2D.i = 0;
    T2D.vus = new Set(); T2D.score = null; T2D.attente = null; T2D.rid = null; T2D.tete = null;
  }
}

// Ce que l'écran a DÉJÀ montré : le score et l'horloge suivent
// l'animation, pas le serveur, qui a une minute d'avance.  Les
// événements des minutes déjà passées quand on arrive sont considérés
// vus, sinon un spectateur en retard verrait tout le match défiler.
function vusInitiaux(m) {
  T2D.vus = new Set();
  // T2D.m est la minute déjà jouée : ses événements sont passés aussi
  (m.evenements || []).forEach((e, i) => { if (e.minute <= T2D.m) T2D.vus.add(i); });
  const s = [0, 0];
  (m.evenements || []).forEach((e, i) => { if (e.type === "but" && T2D.vus.has(i) && e.score) { s[0] = e.score[0]; s[1] = e.score[1]; } });
  T2D.score = s;
}

function scoreVu(m) {
  if (m.fini || !T2D.score || T2D.rid !== m.rencontre_id) return m.score;
  return T2D.score;
}
function minuteVue(m) {
  if (m.fini || T2D.rid !== m.rencontre_id) return m.minute;
  return Math.min(m.minute, Math.max(0, T2D.m));
}
function evtVu(m, i) {
  if (m.fini || T2D.rid !== m.rencontre_id) return true;
  return T2D.vus.has(i);
}

// Le bandeau du match (score, minute, horloge) écrit depuis l'animation.
function majTete() {
  const h = T2D.tete;
  if (!h || !h.m) return;
  const m = h.m, moi = T2D.moi === "b" ? 1 : 0, lui = 1 - moi;
  const s = scoreVu(m), min = minuteVue(m);
  h.score.textContent = `${s[moi]} – ${s[lui]}`;
  h.min.textContent = m.fini ? "Terminé"
    : m.pause ? `${min}' — ${{"mi-temps": "mi-temps", "blessure": "blessure"}[m.motif_pause] || "arrêté"}`
    : `${min}'`;
  h.horloge.style.width = Math.round(100 * min / (h.minutes || 90)) + "%";
}

// Le panneau est RÉUTILISÉ d'un sondage à l'autre, pas reconstruit :
// redessiner vingt-deux cartes toutes les deux secondes et demie
// relançait chaque transition CSS et effaçait le bandeau d'événement.
function panneauTerrain(d, moi) {
  const m = d.match;
  if (T2D.rid !== m.rencontre_id) {
    arreterTerrain(true);
    T2D.rid = m.rencontre_id;
  }
  const cle = JSON.stringify([m.rencontre_id, moi, m.sur_le_terrain?.a, m.sur_le_terrain?.b,
                              m.formation?.a, m.formation?.b]);
  let p = T2D.noeud;
  if (!p || T2D.cle !== cle) {
    arreterTerrain();                       // nouveau match, ou nouveau onze
    // Pas de score ni d'horloge ici : le bandeau du match les porte, et
    // deux horloges qui ne disent pas la même minute (l'animation a un
    // temps de retard sur le serveur) valent moins qu'une seule.
    p = el("div", {class: "panneau terrain-live"});
    p.append(el("div", {class: "t2d-legende"},
      el("span", {class: "lg mien"}, "Ton équipe"),
      el("span", {class: "lg adverse"}, "L'adversaire"),
      el("span", {class: "t2d-action"}, "")));
    const t = terrain2d();
    p.append(t);
    peuplerTerrain(t, m, moi);
    T2D.noeud = p; T2D.cle = cle;
    if (T2D.m > m.minute) T2D.m = Math.max(0, m.minute - 1);
  }
  const t = p.querySelector(".terrain2d");
  T2D.fil = m.fil || [];
  T2D.cible = m.minute;
  T2D.evts = m.evenements || [];
  T2D.t = t; T2D.moi = moi;
  T2D.consignes = m.tactique || {};
  T2D.pas = Math.max(900, (d.duree * 1000) / (d.minutes || 90));
  if (T2D.m === 0 || !T2D.score) { if (T2D.m === 0) T2D.m = Math.max(0, T2D.cible - 1); vusInitiaux(m); }
  if (T2D.m > T2D.cible) T2D.m = T2D.cible;
  jauges(m);
  reAnnoncer(t);
  t.classList.toggle("suspendu", !!m.pause);
  // L'horloge d'animation tourne PLUS LENTEMENT que le sondage : la
  // relancer à chaque réponse l'empêchait de se déclencher, et le terrain
  // ne bougeait jamais tout seul.
  if (!m.fini && !m.pause && !T2D.timer) programmer(200);
  if (m.pause) arreterTerrain();
  if (m.fini) {
    arreterTerrain();
    T2D.m = m.minute;
    const der = T2D.fil[T2D.fil.length - 1];
    if (der) bougerTerrain(t, der.c, der.z, moi);
  }
  return p;
}

// Une annonce reste affichée quelques secondes, d'un sondage à l'autre.
const DUREE_BANDEAU = 5000;
function reAnnoncer(t) {
  const e = T2D.dernier;
  if (e && Date.now() - e.quand < DUREE_BANDEAU) annoncer(t, e.evt);
  else annoncer(t, null);
}

// Five changes over three stoppages, like the laws.  The rules themselves
// live in the simulation — it is the only place that knows who is still on
// after a red card or an injury — so the screen only offers the players.
function cartons(m, c) {
  const j = m.jaunes?.[c] ?? 0, r = m.rouges?.[c] ?? 0;
  return r ? `${j} · ${r} 🟥` : String(j);
}

// La sélection d'un changement SURVIT au sondage.  Le panneau est
// reconstruit toutes les deux secondes et demie ; tant que le choix
// vivait dans une variable locale, il partait avec l'ancien panneau et
// personne n'avait le temps de cliquer deux joueurs d'affilée.
// Le panneau de match est REDESSINÉ à chaque sondage, toutes les deux
// secondes et demie.  Le panneau des changements, lui, ne doit pas
// l'être : un bouton reconstruit perd la sélection ET le clic en cours,
// si bien que « Faire le changement » ne restait allumé qu'une
// demi-seconde et qu'un changement était quasiment infaisable.
//
// Il est donc construit UNE FOIS par situation (le match, ton camp, qui
// est sur le terrain, qui reste sur le banc) et seulement rafraîchi
// ensuite : le compteur de changements restants, les barres d'endurance,
// la mise en évidence de la sélection.  Il n'est rebâti que lorsque la
// liste des joueurs change vraiment — un changement fait, un expulsé, un
// blessé sorti.
const CHG = {cle: null, noeud: null, sortant: null, entrant: null, maj: null, refresh: null, perm: []};

function jaugeEndurance(v) {
  const n = v === undefined || v === null ? 100 : v;
  const i = el("i", {});
  const j = el("span", {class: "endu"}, i);
  poserEndurance(j, n);
  return j;
}

function poserEndurance(noeud, v) {
  const n = v === undefined || v === null ? 100 : v;
  const i = noeud.querySelector("i");
  if (!i) return;
  i.style.width = Math.max(0, Math.min(100, n)) + "%";
  i.className = n < 35 ? "vide" : n < 60 ? "basse" : "";
  noeud.title = `Endurance ${Math.round(n)} %`;
}

function ligneJoueur(j, endu, role, onclick) {
  return el("button", {class: "chg-j", "data-pid": j.pid, "data-role": role, onclick},
    el("span", {class: "fam " + j.fam}, FAM_COURT[j.fam] || j.fam),
    el("div", {class: "qui"}, el("span", {class: "nom"}, j.nom),
      el("span", {class: "sous"}, POSTE_ABBR[j.slot] || j.slot || "")),
    jaugeEndurance(endu?.[j.pid]),
    el("b", {class: "num"}, String(j.ovr)));
}

// Qui est SUR LE TERRAIN, pas qui a commencé : un remplaçant peut
// ressortir, un expulsé non.  Le onze et le banc réunis sont le seul
// endroit où les cartes elles-mêmes sont décrites.
function gensDuBanc(m, cote) {
  const tous = [...(m.onze?.[cote] || []), ...(m.banc?.[cote] || [])];
  const utilises = new Set(m.entres?.[cote] || []);
  return {
    tous,
    surTerrain: (m.sur_le_terrain?.[cote] || []).map(pid => tous.find(j => j.pid === pid)).filter(Boolean),
    banc: (m.banc?.[cote] || []).filter(j => !utilises.has(j.pid)),
    blesses: (m.attente?.[cote] || []).map(pid => tous.find(j => j.pid === pid)).filter(Boolean),
    endu: m.endurance?.[cote] || {},
    restants: SM_MAX_CHG - (m.changements?.[cote === "a" ? 0 : 1] ?? 0),
  };
}

function blocChangements(d, route = "/lobby/changement", rendre = rendreLobby) {
  const m = d.match, cote = d.cote === "b" ? "b" : "a";
  const g = gensDuBanc(m, cote);
  // La signature ne retient que ce qui change la LISTE des boutons.  La
  // minute, le score et l'endurance n'en font pas partie : ils ne
  // justifient pas de reconstruire ce sur quoi on est en train de
  // cliquer.
  const cle = JSON.stringify([m.rencontre_id, cote, route,
                              g.surTerrain.map(j => j.pid), g.banc.map(j => j.pid),
                              g.blesses.map(j => j.pid), g.restants > 0]);
  if (CHG.noeud && CHG.cle === cle) { CHG.refresh(d); return CHG.noeud; }
  CHG.cle = cle;
  CHG.sortant = null;
  CHG.entrant = null;
  CHG.noeud = construireChangements(d, route, rendre);
  return CHG.noeud;
}

function construireChangements(d, route, rendre) {
  const m = d.match, cote = d.cote === "b" ? "b" : "a";
  const {surTerrain, banc, blesses, endu, restants} = gensDuBanc(m, cote);
  const b = el("div", {class: "changements"});

  // Une blessure arrête le match : tant que le manager n'a pas dit qui
  // entre, l'horloge ne repart pas.  C'est la seule décision qui bloque.
  const zoneBlessure = el("div", {});
  b.append(zoneBlessure);
  if (blesses.length) {
    const bl = el("div", {class: "blessure-stop"},
      el("div", {class: "titre anton"}, "🚑 " + blesses.map(j => j.nom).join(", ")
        + (blesses.length > 1 ? " sortent" : " sort") + " sur blessure"),
      el("p", {class: "etat"}, ""));
    if (!banc.length || restants <= 0) {
      bl.append(el("p", {class: "compteur"}, "Plus personne à faire entrer : il faut finir en infériorité."));
    } else {
      const liste = el("div", {class: "chg-liste"});
      for (const j of banc)
        liste.append(ligneJoueur(j, endu, "bless", async () => {
          try { await rendre(await api(route, {sortant: blesses[0].pid, entrant: j.pid})); toast(j.nom + " entre"); }
          catch (e) { toast(e.message); }
        }));
      bl.append(liste);
    }
    zoneBlessure.append(bl);
  }

  const compteur = el("div", {class: "etiq"}, "");
  b.append(compteur);
  const routePerm = route.replace("changement", "permutation");
  if (!banc.length) {
    b.append(el("p", {class: "compteur"}, "Personne sur le banc. Nomme des remplaçants sur l'écran Équipe avant de lancer un match."));
    b.append(blocPermutation(d, routePerm, rendre, surTerrain, endu));
    CHG.refresh = dd => majCompteur(dd, compteur, zoneBlessure, b);
    CHG.refresh(d);
    return b;
  }
  if (restants <= 0) {
    b.append(el("p", {class: "compteur"}, "Tu as fait tous tes changements."));
    b.append(blocPermutation(d, routePerm, rendre, surTerrain, endu));
    CHG.refresh = dd => majCompteur(dd, compteur, zoneBlessure, b);
    CHG.refresh(d);
    return b;
  }

  const choix = el("div", {class: "chg-choix"});
  const maj = () => {
    choix.querySelectorAll("[data-pid]").forEach(n => n.classList.toggle("choisi",
      (n.dataset.role === "out" && +n.dataset.pid === CHG.sortant)
      || (n.dataset.role === "in" && +n.dataset.pid === CHG.entrant)));
    valider.disabled = !(CHG.sortant && CHG.entrant);
  };
  const colonne = (titre, gens, role) => {
    const c = el("div", {}, el("div", {class: "etiq"}, titre));
    for (const j of gens)
      c.append(ligneJoueur(j, endu, role, () => {
        if (role === "out") CHG.sortant = j.pid; else CHG.entrant = j.pid;
        maj();
      }));
    return c;
  };
  const valider = el("button", {class: "primaire", disabled: true, onclick: async () => {
    const paire = {sortant: CHG.sortant, entrant: CHG.entrant};
    CHG.sortant = null; CHG.entrant = null;
    maj();
    try { await rendre(await api(route, paire)); toast("Changement enregistré"); }
    catch (e) { toast(e.message); }
  }}, "Faire le changement");
  // Le plus fatigué d'abord : c'est lui qu'on cherche quand on ouvre ce
  // panneau à la soixante-dixième minute.  L'ordre est fixé à la
  // construction, pas à chaque sondage : une liste qui se réordonne sous
  // le curseur est pire qu'une liste mal triée.
  const parFatigue = [...surTerrain].sort((x, y) => (endu[x.pid] ?? 100) - (endu[y.pid] ?? 100));
  choix.append(colonne("Il sort", parFatigue, "out"), colonne("Il entre", banc, "in"));
  b.append(choix, valider);
  b.append(blocPermutation(d, routePerm, rendre, surTerrain, endu));
  CHG.maj = maj;
  CHG.refresh = dd => { majCompteur(dd, compteur, zoneBlessure, b); maj(); };
  CHG.refresh(d);
  return b;
}

// Échanger les postes de deux joueurs sur le terrain : Valverde monte de
// latéral à milieu et Camavinga descend, ou les deux ailiers changent
// d'aile.  Personne ne sort, ça ne compte pas comme un changement, et
// chacun paie le poste où il se retrouve (scoring.malus_poste).
function blocPermutation(d, route, rendre, surTerrain, endu) {
  const b = el("div", {class: "permutation"});
  b.append(el("div", {class: "etiq"}, "Postes — échanger deux joueurs"),
    el("p", {class: "compteur"}, "Touche deux joueurs : ils échangent leurs postes à la minute suivante. Ça ne coûte pas de changement."));
  const liste = el("div", {class: "chg-choix"});
  const maj = () => {
    liste.querySelectorAll("[data-pid]").forEach(n => n.classList.toggle("choisi", CHG.perm.includes(+n.dataset.pid)));
    const [x, y] = CHG.perm;
    const nom = pid => (surTerrain.find(j => j.pid === pid)?.nom || "").split(" ").slice(-1)[0];
    valider.disabled = !(x && y);
    valider.textContent = x && y ? `Échanger ${nom(x)} et ${nom(y)}` : "Échanger leurs postes";
  };
  const colonneG = el("div", {}), colonneD = el("div", {});
  surTerrain.forEach((j, i) => (i % 2 ? colonneD : colonneG).append(ligneJoueur(j, endu, "perm", () => {
    if (CHG.perm.includes(j.pid)) CHG.perm = CHG.perm.filter(p => p !== j.pid);
    else CHG.perm = [...CHG.perm.slice(-1), j.pid];
    maj();
  })));
  liste.append(colonneG, colonneD);
  const valider = el("button", {disabled: true, onclick: async () => {
    const [un, deux] = CHG.perm;
    CHG.perm = [];
    maj();
    try { await rendre(await api(route, {un, deux})); toast("Échange de postes enregistré"); }
    catch (e) { toast(e.message); }
  }}, "Échanger leurs postes");
  CHG.perm = [];
  b.append(liste, valider);
  maj();
  return b;
}

// Ce qui bouge d'un sondage à l'autre, écrit DANS les nœuds existants.
function majCompteur(d, compteur, zoneBlessure, racine) {
  const m = d.match, cote = d.cote === "b" ? "b" : "a";
  const {endu, restants} = gensDuBanc(m, cote);
  compteur.textContent = `Remplacements — il t'en reste ${Math.max(0, restants)}`;
  const postes = m.postes?.[cote] || {};
  racine.querySelectorAll(".chg-j").forEach(n => {
    const j = n.querySelector(".endu");
    if (j) poserEndurance(j, endu[+n.dataset.pid]);
    // le poste qu'il tient MAINTENANT : un échange de postes le change
    const p = postes[+n.dataset.pid], sous = n.querySelector(".sous");
    if (p && sous) sous.textContent = (POSTE_ABBR[p.slot] || p.slot || "") + (p.malus ? ` · −${p.malus}` : "");
  });
  const etat = zoneBlessure.querySelector(".etat");
  if (etat) etat.textContent = m.pause
    ? "Le match est arrêté : choisis qui entre."
    : "Tu joues en infériorité tant que personne n'entre.";
}

// Le panneau tactique du match : les trois axes, la formation, la pause
// pour un match à un seul humain, et les changements.  Réutilisé lui
// aussi — un bouton de formation reconstruit sous le doigt perd le clic
// exactement comme celui des changements.
const AJU = {cle: null, noeud: null, tac: null};

function blocAjuster(d, routeTac, routePause, rendre) {
  const m = d.match, cote = d.cote === "b" ? "b" : "a";
  const cle = JSON.stringify([m.rencontre_id, cote, routeTac, m.solitaire]);
  if (!AJU.noeud || AJU.cle !== cle) {
    AJU.cle = cle;
    AJU.tac = {};
    AJU.attendu = null;
    AJU.noeud = construireAjuster(d, routeTac, routePause, rendre);
  }
  majAjuster(d, routePause, rendre);
  majCauserie(d, routeTac, rendre);
  majMarquage(d, routeTac, rendre);
  majTireurs(d);
  const chg = blocChangements(d, routeTac === "/solo/tactique" ? "/solo/changement" : "/lobby/changement", rendre);
  // et on ne le réinsère que s'il a VRAIMENT changé : détacher puis
  // rattacher le même nœud pour rien, c'est le clic du manager qu'on
  // risque de perdre
  if (AJU.corps.firstChild !== chg) AJU.corps.replaceChildren(chg);
  return AJU.noeud;
}

function construireAjuster(d, routeTac, routePause, rendre) {
  const p = el("div", {class: "panneau interne"}, el("h3", {class: "anton"}, "Ajuster"),
    el("p", {class: "compteur"}, "Un changement prend effet à la minute suivante : il ne touche jamais ce qui est déjà joué."));
  const tac = AJU.tac;
  const envoyer = async () => {
    // Un ajustement prend effet à la MINUTE SUIVANTE : d'ici là le
    // serveur rend encore l'ancienne tactique, et remettre bêtement ce
    // qu'il rend éteignait le bouton qu'on vient de choisir pendant
    // plusieurs secondes.  On garde donc ce qui est en attente affiché,
    // jusqu'à ce que le serveur le confirme.
    AJU.attendu = {...tac};
    try { await rendre(await api(routeTac, {tactique: {...tac}})); }
    catch (e) { AJU.attendu = null; toast(e.message); }
  };
  AJU.pause = el("div", {class: "actions", style: "justify-content:flex-start;margin-bottom:8px"});
  if (d.match.solitaire && routePause) {
    // L'état de pause est lu AU CLIC, jamais figé à la construction : le
    // panneau est réutilisé d'un sondage à l'autre, et un `d` capturé ici
    // envoyait « mettre en pause » à un match que l'arbitre avait déjà
    // arrêté pour la mi-temps — donc « Reprendre » ne faisait rien.
    AJU.boutonPause = el("button", {onclick: async () => {
      const enPause = !!(AJU.d?.match?.pause);
      try { await rendre(await api(routePause, {pause: !enPause})); } catch (e) { toast(e.message); }
    }}, "");
    AJU.pause.append(AJU.boutonPause);
    p.append(AJU.pause);
  }
  AJU.causerie = el("div", {});
  p.append(AJU.causerie);
  p.append(selecteurTactique(tac, envoyer));
  // La formation change EN COURS DE MATCH : les onze restent sur le
  // terrain, on les redistribue sur les postes de la nouvelle forme
  // comme le fait le meilleur onze, et ceux qui se retrouvent hors de
  // leur poste le paient.
  const g = el("div", {class: "tac-groupe"}, el("span", {class: "tac-titre"}, "Formation"));
  for (const f of Object.keys(RANGS))
    g.append(el("button", {class: "tac", "data-form": f,
      onclick: () => { tac.formation = f; envoyer(); }}, f));
  p.append(el("div", {class: "tactiques"}, g));
  p.append(depliant("match", "Consignes aux lignes",
    el("p", {class: "compteur"},
      "Ce que tu demandes à chaque ligne. Chacune est un échange, jamais un bonus, "
      + "et elle se voit sur le terrain : un latéral qui reste derrière ne monte plus, "
      + "un ailier qui repique quitte le couloir."),
    selecteurConsignes(tac, envoyer)));
  // Museler un joueur d'en face.  C'est la seule consigne qui regarde
  // l'autre équipe, et elle est légitime : son onze est sur le terrain,
  // on le voit jouer.
  AJU.marquage = el("div", {class: "marquage"});
  p.append(AJU.marquage);
  AJU.tireurs = el("div", {class: "compteur tireurs"});
  p.append(AJU.tireurs);
  AJU.corps = el("div", {});
  p.append(AJU.corps);
  return p;
}

// La causerie : seulement à la mi-temps, et seulement une fois.
const CAUSERIE_TXT = {
  secouer: ["Les secouer", "De l'urgence, moins de sang-froid. Ça porte surtout quand on est mené."],
  rassurer: ["Les rassurer", "Du sang-froid, moins d'élan. Ça tient un résultat, ça n'en renverse pas."],
  feliciter: ["Les féliciter", "Ça porte quand ça va bien. Quand ça va mal, c'est hors sujet et ça endort."],
};

function majCauserie(d, routeTac, rendre) {
  const m = d.match, cote = d.cote === "b" ? "b" : "a";
  const z = AJU.causerie;
  if (!z) return;
  const dite = m.causerie?.[cote];
  const cest = m.pause && m.motif_pause === "mi-temps";
  if (dite && dite !== "rien") {
    z.replaceChildren(el("div", {class: "causerie dite"},
      `À la pause, tu les as ${{"secouer": "secoués", "rassurer": "rassurés", "feliciter": "félicités"}[dite] || "laissés"}.`));
    return;
  }
  if (!cest) { z.replaceChildren(); return; }
  const route = routeTac.replace("tactique", "causerie");
  const b = el("div", {class: "causerie"},
    el("div", {class: "etiq"}, "🗣 Mi-temps — tu leur dis quoi ?"),
    el("p", {class: "compteur"},
      `Ce que tu dis ne vaut pas la même chose selon le score. L'effet dure ${G.saison?.duree_causerie ?? 20} minutes, `
      + "et tu ne parles qu'une fois."));
  const choix = el("div", {class: "tac-groupe"});
  for (const [cle, [lib, aide]] of Object.entries(CAUSERIE_TXT))
    choix.append(el("button", {class: "tac", title: aide, onclick: async () => {
      try { await rendre(await api(route, {causerie: cle})); } catch (e) { toast(e.message); }
    }}, lib));
  choix.append(el("button", {class: "tac discret", onclick: async () => {
    try { await rendre(await api(route, {causerie: "rien"})); } catch (e) { toast(e.message); }
  }}, "Ne rien dire"));
  b.append(choix);
  z.replaceChildren(b);
}

function majMarquage(d, routeTac, rendre) {
  const m = d.match, cote = d.cote === "b" ? "b" : "a", adv = cote === "a" ? "b" : "a";
  const z = AJU.marquage;
  if (!z || m.fini) { if (z) z.replaceChildren(); return; }
  const tous = [...(m.onze?.[adv] || []), ...(m.banc?.[adv] || [])];
  const sur = (m.sur_le_terrain?.[adv] || []).map(pid => tous.find(j => j.pid === pid)).filter(Boolean);
  const actuel = AJU.tac.marquage || 0;
  const paire = m.marquage?.[cote];
  const g = el("div", {class: "tac-groupe"}, el("span", {class: "tac-titre"}, "Marquage"));
  g.append(el("button", {class: "tac" + (!actuel ? " actif" : ""),
    onclick: () => { AJU.tac.marquage = 0; envoyerTac(d, routeTac, rendre); }}, "Personne"));
  for (const j of sur.filter(x => x.fam !== "GK").slice(0, 10))
    g.append(el("button", {class: "tac" + (actuel === j.pid ? " actif" : ""),
      title: `${j.nom} · ${j.slot || j.poste} · OVR ${j.ovr}`,
      onclick: () => { AJU.tac.marquage = j.pid; envoyerTac(d, routeTac, rendre); }},
      (j.nom || "").split(" ").slice(-1)[0]));
  z.replaceChildren(
    el("p", {class: "compteur"},
      "Coller un homme sur l'un des leurs. Il pèse moins — d'autant moins qu'il est fort — "
      + "mais celui qui le suit passe son match à le suivre. Ça ne se justifie que contre un vrai danger."),
    el("div", {class: "tactiques"}, g));
  if (paire) {
    const nom = pid => (tous.find(x => x.pid === pid)?.nom
      || [...(m.onze?.[cote] || []), ...(m.banc?.[cote] || [])].find(x => x.pid === pid)?.nom || "?");
    z.append(el("div", {class: "compteur"}, `${nom(paire.garde)} suit ${nom(paire.cible)}.`));
  }
}

// Qui tire les penaltys et les corners : lu dans le onze, pas choisi.
// Le meilleur finisseur prend les penaltys, le meilleur créateur les
// corners, et ça change tout seul quand il sort.
function majTireurs(d) {
  const m = d.match, cote = d.cote === "b" ? "b" : "a";
  if (!AJU.tireurs) return;
  const t = m.tireurs?.[cote];
  if (!t) { AJU.tireurs.replaceChildren(); return; }
  const tous = [...(m.onze?.[cote] || []), ...(m.banc?.[cote] || [])];
  const nom = pid => (tous.find(x => x.pid === pid)?.nom || "—").split(" ").slice(-1)[0];
  AJU.tireurs.textContent =
    `Penaltys : ${nom(t.penalty)} · corners : ${nom(t.corner)} — le meilleur finisseur et le meilleur créateur de ton onze.`;
}

function envoyerTac(d, routeTac, rendre) {
  AJU.attendu = {...AJU.tac};
  api(routeTac, {tactique: {...AJU.tac}}).then(rendre).catch(e => { AJU.attendu = null; toast(e.message); });
}

const AXES_TAC = ["tempo", "bloc", "risque", "formation", "marquage",
                  "lateraux", "ailiers", "milieux", "attaquants", "relance"];

function memeTactique(a, b) {
  return AXES_TAC.every(k => (a[k] || "") === (b[k] || ""));
}

function majAjuster(d, routePause, rendre) {
  AJU.d = d;                                  // l'état courant, pour les gestionnaires
  const m = d.match, cote = d.cote === "b" ? "b" : "a";
  const tac = AJU.tac;
  const serveur = {...(m.tactique[cote] || LOBBY.tac)};
  serveur.formation = m.formation?.[cote] || serveur.formation || "4-3-3";
  if (AJU.attendu && memeTactique(serveur, AJU.attendu)) AJU.attendu = null;
  Object.assign(tac, AJU.attendu || serveur);
  const enAttente = !!AJU.attendu;
  AJU.noeud.querySelectorAll(".tac[data-axe]").forEach(n => {
    const choisi = tac[n.dataset.axe] === n.dataset.valeur;
    n.classList.toggle("actif", choisi);
    n.classList.toggle("attente", choisi && enAttente && serveur[n.dataset.axe] !== n.dataset.valeur);
  });
  AJU.noeud.querySelectorAll(".tac[data-form]").forEach(n => {
    const choisi = tac.formation === n.dataset.form;
    n.classList.toggle("actif", choisi);
    n.classList.toggle("attente", choisi && enAttente && serveur.formation !== n.dataset.form);
  });
  AJU.noeud.querySelectorAll(".tac[data-consigne]").forEach(n => {
    const choisi = tac[n.dataset.consigne] === n.dataset.valeur;
    n.classList.toggle("actif", choisi);
    n.classList.toggle("attente", choisi && enAttente && serveur[n.dataset.consigne] !== n.dataset.valeur);
  });
  if (AJU.boutonPause) {
    AJU.boutonPause.textContent = m.pause ? "▶ Reprendre" : "⏸ Mettre en pause";
    AJU.boutonPause.className = m.pause ? "primaire" : "";
  }
}

const SM_MAX_CHG = 5;

function panneauHistorique(d) {
  const p = el("div", {class: "panneau"}, el("h3", {class: "anton"}, "Tes derniers matchs classés"));
  if (!d.historique?.length) { p.append(el("p", {class: "compteur"}, "Aucun match joué.")); return p; }
  for (const h of d.historique)
    p.append(el("div", {class: "ligne simple"},
      el("span", {class: "res " + h.resultat}, h.resultat),
      el("div", {class: "qui"}, el("div", {class: "nom"}, h.adversaire), el("div", {class: "sous"}, h.defi ? "défi" : "classé")),
      el("b", {class: "num"}, `${h.score[0]} – ${h.score[1]}`),
      el("span", {class: "compteur"}, h.elo === null ? "—" : (h.elo > 0 ? "+" : "") + h.elo)));
  return p;
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
// la recherche : un instant après la frappe, pas à chaque touche
let EQ_RECH = null;
$("#eq-nom").addEventListener("input", () => { clearTimeout(EQ_RECH); EQ_RECH = setTimeout(() => rendreEquipe(false), 160); });
$("#btn-envoyer").addEventListener("click", envoyer);
$("#fiche").addEventListener("click", e => { if (e.target === e.currentTarget) e.currentTarget.close(); });

// ---- fiche ----
// What the player actually did that week.  The raw actions were collected
// for the weekly head-to-head sheet; that match is gone and they belong
// here, next to the note they produced.
const FAIT_ICONE = {buts: "⚽", pd: "🅰", tirs: "↗", arrets: "🧤", enc: "↘"};
function faits(p) {
  const f = p.faits || {};
  const bouts = ["buts", "pd", "arrets"].filter(k => f[k]).map(k => ` ${FAIT_ICONE[k]}${f[k]}`);
  return bouts.join("");
}
// Ce que la fiche dit du profil : où il est chez lui, où il l'est moins,
// et — si le manager a déjà réglé sa tactique — ce que ça lui vaut dans
// SON équipe à lui.
function blocProfil(d) {
  const b = el("div", {class: "profil-bloc"});
  const lu = lectureProfil(d.profil, d.postes?.[0] || d.poste);
  if (!lu.aise.length && !lu.gene.length) {
    b.append(el("div", {class: "etiq"}, "Profil de jeu"),
      el("p", {class: "compteur"},
        "Aucune préférence marquée : il est également à l'aise partout, ce qui est "
        + "la marque d'un joueur complet — et ce qui veut dire qu'aucune tactique ne "
        + "le fera jouer au-dessus de lui-même."));
    return b;
  }
  b.append(el("div", {class: "etiq"}, "Profil de jeu"));
  b.append(el("p", {class: "compteur"},
    "Lu dans ses attributs, comparés à ceux de sa ligne : ce qu'il fait mieux que "
    + "les autres à son poste, pas son niveau. Une tactique qui lui va le fait jouer "
    + `jusqu'à ${Math.round(AISE.max * 100)} % au-dessus de lui-même ; une qui le dessert, autant en dessous.`));
  const l = el("div", {class: "profil-listes"});
  if (lu.aise.length) l.append(el("div", {class: "profil-col aise"},
    el("div", {class: "t"}, "À l'aise dans"),
    ...lu.aise.map(x => el("div", {class: "profil-item"}, el("span", {}, x.texte),
      el("b", {}, (x.score > 0 ? "+" : "") + x.score.toFixed(1))))));
  if (lu.gene.length) l.append(el("div", {class: "profil-col gene"},
    el("div", {class: "t"}, "Moins à l'aise dans"),
    ...lu.gene.map(x => el("div", {class: "profil-item"}, el("span", {}, x.texte),
      el("b", {}, x.score.toFixed(1))))));
  b.append(l);
  // et avec TA tactique de départ ?
  if (Object.keys(AFFINITES).length) {
    const a = aiseDe(d.profil, d.postes?.[0] || d.poste, LOBBY.tac);
    const pct = AISE.max * Math.max(-1, Math.min(1, a / AISE.z)) * 100;
    b.append(el("div", {class: "profil-tien " + (pct > 1 ? "bon" : pct < -1 ? "mauvais" : "")},
      Math.abs(pct) < 1
        ? "Avec ta tactique de départ, il joue à son niveau."
        : `Avec ta tactique de départ, il joue ${pct > 0 ? "au-dessus" : "en dessous"} de lui-même `
          + `(${pct > 0 ? "+" : ""}${pct.toFixed(0)} % sur ses attributs).`));
  }
  return b;
}

async function ouvrirFiche(id) {
  let d; try { d = await api("/cartes/" + id); } catch (e) { toast(e.message); return; }
  const dlg = $("#fiche"); dlg.replaceChildren();
  const box = el("div", {class: "fiche fiche-carte"});
  const img = el("img", {class: "carte-img", src: `/images/cartes/${id}.png?ovr=${d.ovr}`, alt: `Carte de ${d.nom}`});
  img.addEventListener("error", () => img.remove());
  const cote = el("div", {class: "fiche-cote"});
  cote.append(el("div", {class: "etiq"}, `${d.club} · ${d.ligue}`), el("h3", {class: "anton"}, d.nom),
    el("div", {class: "fiche-ligne"}, el("span", {class: "fam " + d.fam}, FAM_COURT[d.fam]), el("span", {}, POSTE_COURT[d.poste] || d.poste), d.age ? el("span", {}, `· ${d.age} ans`) : null, d.pays ? el("span", {title: d.pays}, `· ${drapeau(d.pays)} ${d.pays}`) : null, d.numero ? el("span", {}, `· n° ${d.numero}`) : null,
      el("span", {title: d.pied ? "Pied fort, d'après FotMob" : "Pied fort inconnu : la donnée n'a pas été récupérée (donnees/pieds.py)"},
        "· " + (PIEDS[d.pied] || "pied inconnu"))),
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
  box.append(blocProfil(d));
  box.append(el("div", {class: "etiq"}, "Dernières prestations"), el("div", {class: "notes"}, ...(d.prestations.length ? d.prestations.slice(0, 8).map(p => el("span", {class: "note " + (p.note >= 7 ? "b" : p.note < 5 ? "m" : ""), title: `J${p.numero} · ${p.competition}`}, `${f1(p.note)} · ${Math.round(p.minutes)}'${faits(p)}`)) : [el("span", {class: "compteur"}, "aucun match noté cette saison")])));
  if (d.historique.length > 1) box.append(el("div", {class: "etiq", style: "margin-top:10px"}, "Prix par journée"), sparkline(d.historique.map(h => h.prix), fM));
  const acts = el("div", {class: "actions"});
  const nv = ventesDe(id).length;
  if (G.equipe.effectif[id]) { const dl = d.prix - G.equipe.effectif[id]; acts.append(el("span", {class: "compteur", style: "margin-right:auto"}, `dans ton effectif · acheté ${fM(G.equipe.effectif[id])} · ${fM(dl, true)}`)); }
  acts.append(el("button", {class: "achat" + (nv ? " primaire" : ""), disabled: !nv, onclick: () => { dlg.close(); allerAuxVentes(id); }}, nv ? `${nv} vente${nv > 1 ? "s" : ""} en cours` : "Aucune vente en cours"));
  acts.append(el("button", {onclick: () => { dlg.close(); ouvrirDetail(id); }}, "Détail des stats"));
  acts.append(el("button", {class: "discret", onclick: () => dlg.close()}, "Fermer"));
  box.append(acts); dlg.append(box); dlg.showModal();
}

// ---------------------------------------------------------------------------
// Where the numbers come from.  Every line is a step the card really went
// through (jeu/bareme.py), with the figure it produced: the card's OVR and
// its six attributes are the last line of each chain, not a second opinion.
// ---------------------------------------------------------------------------
const pc = v => Math.round(v * 100) + " %";
const f2 = v => (Math.round(v * 100) / 100).toLocaleString("fr-FR", {minimumFractionDigits: 2, maximumFractionDigits: 2});
// "100 %" reads as if he were the only one; the place says it better.
function place(rang, n) {
  const k = Math.max(1, Math.round((1 - rang) * n));
  return `≈ ${k}${k === 1 ? "er" : "e"} sur ${n}`;
}
function etape(lib, val, note) {
  return el("div", {class: "etape"}, el("span", {class: "lib"}, lib),
    el("b", {class: "num"}, val), note ? el("span", {class: "note-etape"}, note) : null);
}
async function ouvrirDetail(id) {
  let d; try { d = await api(`/cartes/${id}/detail`); } catch (e) { toast(e.message); return; }
  const dlg = $("#fiche"); dlg.replaceChildren();
  const gk = d.poste === "Gardien";
  const box = el("div", {class: "fiche detail"});
  box.append(el("h3", {class: "anton"}, `${d.nom} — d'où viennent ses stats`),
    el("p", {class: "compteur"}, `Tout vient du barème « Ballon d'or » du moteur : chaque action de chaque match, pondérée par la compétition, le tour et l'adversaire, lue par 90 minutes. Rien n'est tiré au sort.`));

  // --- the OVR ---
  const dep = d.depart, sa = d.saison;
  const o = el("div", {class: "chaine"});
  o.append(el("div", {class: "etiq"}, `1. Le départ de saison${d.source ? " — barème " + d.source : ""}`));
  o.append(etape("Barème brut", `${f2(dep.terrain.points)} pts`, `sur ${Math.round(dep.terrain.minutes)} min`));
  o.append(etape("Par 90 minutes", f2(dep.terrain.par90)));
  o.append(etape("Ramené vers la médiane du poste", f2(dep.terrain.retreci),
    `médiane ${f2(dep.terrain.prior)} · ton échantillon pèse ${pc(dep.terrain.poids)} (${dep.terrain.k} min de référence)`));
  o.append(etape("Corrigé du rôle", f2(dep.terrain.s),
    `${Math.round(dep.terrain.titularisations)} titularisations sur ${Math.round(dep.terrain.feuilles)} feuilles → ${pc(dep.terrain.part_role)}, contre ${pc(dep.terrain.role_ref)} pour un titulaire type`));
  o.append(etape("Total Ballon d'or", f2(dep.t),
    `${pc(dep.part_terrain)} terrain (${f2(dep.t_terrain)}) + ${pc(1 - dep.part_terrain)} palmarès (${f2(dep.t_palmares)})`));
  o.append(etape("OVR de départ", String(dep.ovr), `${place(dep.rang, d.reguliers)} joueurs réguliers de la saison`));
  o.append(el("div", {class: "etiq"}, "2. Ce que la saison en cours en fait"));
  if (!sa.terrain.minutes || sa.fenetre.min === 0)
    o.append(el("p", {class: "compteur"}, "Aucune journée jouée depuis le départ : la carte est encore à son OVR de départ."));
  else
    o.append(etape("Barème de la saison", `${f2(sa.fenetre.pts)} pts`,
      `sur ${Math.round(sa.fenetre.min)} min, ${Math.round(sa.fenetre.tit)} titularisations · la saison passée compte encore pour ${pc(sa.poids_passe)}`));
  o.append(etape("Niveau lu aujourd'hui", f2(sa.lecture), `contre ${f2(sa.lecture_depart)} au départ`));
  o.append(etape("Mouvement", (sa.mouvement > 0 ? "+" : "") + f2(sa.mouvement),
    Math.abs(sa.mouvement_brut) > sa.borne ? `ramené dans la limite de ±${sa.borne} points` : `limite ±${sa.borne} points`));
  o.append(etape("OVR de la carte", String(sa.ovr), null));
  box.append(o);

  // --- the six attributes ---
  box.append(el("div", {class: "etiq", style: "margin-top:14px"}, "3. Les six attributs"),
    el("p", {class: "compteur"}, "Chaque axe est la somme des points que le barème donne à ses actions, par 90 minutes, classée parmi TOUS les joueurs de champ réguliers — le dribble d'un défenseur est comparé à celui d'un ailier, pas aux autres défenseurs."));
  for (const a of d.axes) {
    const nom = (gk && ATTR_NOMS_GARDIEN[a.axe]) || ATTR_NOMS[a.axe];
    const det = el("details", {class: "axe-detail"});
    det.append(el("summary", {},
      el("span", {class: "lib"}, nom),
      el("div", {class: "jauge"}, el("i", {class: a.valeur >= 80 ? "haut" : "", style: `width:${(a.valeur - 40) / 59 * 100}%`})),
      el("b", {class: "num"}, String(a.valeur))));
    const c = el("div", {class: "chaine interne"});
    c.append(etape("Points de l'axe", f2(a.points), `soit ${f2(a.par90)} par 90 min`));
    c.append(etape("Ramené vers la médiane du poste", f2(a.retreci),
      `médiane ${f2(a.prior)} · ton échantillon pèse ${pc(a.poids)}`));
    c.append(etape("Classement", place(a.rang, d.reguliers), `parmi les réguliers de la saison, tous postes confondus → ${a.valeur}`));
    if (a.actions.length) {
      c.append(el("div", {class: "etiq"}, "Les actions comptées cette saison"));
      const t = el("div", {class: "actions-axe"});
      for (const ac of a.actions)
        t.append(el("div", {}, el("span", {}, ac.nom),
          el("b", {class: "num"}, Number.isInteger(ac.total) ? String(ac.total) : f2(ac.total)),
          el("span", {class: "compteur"}, f2(ac.par90) + " / 90")));
      c.append(t);
    }
    c.append(el("p", {class: "compteur"}, "Lignes du barème : " + a.cles.join(", ")));
    det.append(c);
    box.append(det);
  }
  const acts = el("div", {class: "actions"});
  acts.append(el("button", {onclick: () => { dlg.close(); ouvrirFiche(id); }}, "Retour à la fiche"),
    el("button", {class: "discret", onclick: () => dlg.close()}, "Fermer"));
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
    const s = await api("/saison"); TAILLE = s.taille_effectif; BANC_MAX = s.taille_banc ?? BANC_MAX;
    FORMATIONS = s.formations; LIMITES = s.limites;
    if (s.formations_rangs) RANGS = s.formations_rangs;
    if (s.familles_poste) FAM_POSTE = s.familles_poste;
    if (s.malus_postes) MALUS_POSTES = s.malus_postes;
    if (s.malus_gardien) MALUS_GK = s.malus_gardien;
    if (s.profondeur_poste) PROF_POSTE = s.profondeur_poste;
    if (s.affinites) AFFINITES = s.affinites;
    if (s.aise) AISE = s.aise;
    const moi = await api("/moi"); connecte(moi);
    if (moi.connecte) { const h = location.hash.replace("#", ""); await montrer(["packs", "encheres", "marche", "equipe", "lobby", "solo", "journee", "classement", "admin"].includes(h) ? h : (idsEffectif().length ? "equipe" : "packs")); }
  } catch (e) { toast("Serveur injoignable : " + e.message); }
})();

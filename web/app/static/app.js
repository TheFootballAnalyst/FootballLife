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
const PIEDS = {gauche: "gaucher", droit: "droitier", deux: "ambidextre"};
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
let TAILLE = 18, BANC_MAX = 7, FORMATIONS = {"4-3-3": [1,4,3,3]}, LIMITES = {GK: [1,1], DEF: [3,5], MID: [2,5], FWD: [1,4]};
let RANGS = {"4-3-3": [["Gardien"], ["Lateral","Defenseur central","Defenseur central","Lateral"],
  ["Milieu defensif","Milieu relayeur","Milieu offensif"], ["Ailier","Buteur","Ailier"]]};
let FAM_POSTE = {"Gardien":"GK","Defenseur central":"DEF","Lateral":"DEF","Milieu defensif":"MID",
  "Milieu relayeur":"MID","Milieu offensif":"MID","Ailier":"FWD","Ailier droit":"FWD",
  "Ailier gauche":"FWD","Buteur":"FWD"};

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
// exactly his position, or merely his line — the second is allowed and costs
// MALUS_HORS_POSTE on every attribute in the match
function aLePoste(id, poste) { const c = carte(id); return !!c && (c.postes || []).includes(poste); }
function horsPoste(id, poste) { return !aLePoste(id, poste); }
const POSTE_ABBR = {"Gardien": "GB", "Defenseur central": "DC", "Lateral": "LAT",
  "Milieu defensif": "MDF", "Milieu relayeur": "MC", "Milieu offensif": "MO",
  "Ailier": "AIL", "Ailier droit": "AD", "Ailier gauche": "AG", "Buteur": "BU"};
function legal(fams) { if (fams.length !== 11 || fams.some(x => !x)) return false; return FAMS.every(f => { const n = fams.filter(x => x === f).length; return n >= LIMITES[f][0] && n <= LIMITES[f][1]; }); }
// A card is eligible wherever the player really played, not only at the one
// label the barème shows: Valverde spent a third of his season at right
// back, a third on the wing and a quarter in midfield.
function famillesDe(c) { return (c && c.familles && c.familles.length) ? c.familles : [c ? c.fam : "MID"]; }
function peutJouer(id, fam) { const c = carte(id); return !!c && famillesDe(c).includes(fam); }
function onzeLegal() { const fams = slotsFam(C.formation); return C.slots.every((id, s) => id !== null && peutJouer(id, fams[s])); }
// composition locale : slots (11, null si vide), banc, capitaine
let C = {formation: "4-3-3", slots: Array(11).fill(null), banc: [], cap: null};
function compoVersSlots() {
  const cp = G.compo; const fams = slotsFam(cp.formation in FORMATIONS ? cp.formation : "4-3-3");
  let slots = Array(11).fill(null);
  // The lineup is stored slot by slot, so the manager's own arrangement —
  // Valverde moved into midfield, the two centre-backs swapped — comes back
  // exactly as he left it.  Re-matching by position would undo it.
  const direct = cp.titulaires.length === 11 && cp.titulaires.every((id, s) => id !== null && carte(id) && peutJouer(id, fams[s]));
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
// Best eleven, POSITION by position: the best card that really held that
// position, then the best of the line, then whoever is left.  The scarcest
// slot is served first — filling in slot order left a back four of three
// centre-backs because the full-backs had already gone into the middle.
function auto(formation) {
  C.formation = formation;
  const postes = slotsPostes(formation), fams = slotsFam(formation);
  const tri = idsEffectif().sort((a, b) => ovr(b) - ovr(a));
  const pris = new Set(); const slots = postes.map(() => null);
  const ordre = postes.map((_, s) => s)
    .sort((x, y) => tri.filter(i => aLePoste(i, postes[x])).length - tri.filter(i => aLePoste(i, postes[y])).length);
  for (const tour of ["poste", "famille", "reste"])
    for (const s of ordre) {
      if (slots[s] !== null) continue;
      const i = tri.find(x => !pris.has(x) && (tour === "poste" ? aLePoste(x, postes[s])
        : tour === "famille" ? peutJouer(x, fams[s]) : true));
      if (i !== undefined) { slots[s] = i; pris.add(i); }
    }
  C.slots = slots;
  // the bench keeps a keeper first, then the best of what is left
  const reste = tri.filter(x => !pris.has(x));
  const gk = reste.find(x => peutJouer(x, "GK"));
  C.banc = gk === undefined ? reste : [gk, ...reste.filter(x => x !== gk)];
  if (!slots.includes(C.cap)) C.cap = slots.find(x => x !== null) ?? null;
  rendreEquipe(false);
}
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
    A.append(el("div", {class: "avert"}, trous
      ? `Il manque ${trous} joueur${trous > 1 ? "s" : ""} : glisse une carte du banc sur une case vide.`
      : "Un joueur occupe une ligne qu'il n'a jamais tenue. Les cases en rouge sont à corriger."));
  }
  // out of position is legal, and it costs: say how many and how much
  const postesC = slotsPostes(C.formation);
  const dephases = C.slots.filter((id, s) => id !== null && peutJouer(id, postesC[s]) === undefined ? false
    : id !== null && horsPoste(id, postesC[s]) && peutJouer(id, FAM_POSTE[postesC[s]])).length;
  if (dephases) A.append(el("div", {class: "info"},
    `${dephases} joueur${dephases > 1 ? "s" : ""} hors poste (case orange) : −${MALUS_HORS_POSTE} sur chacun de leurs attributs pendant le match. C'est permis, ça coûte.`));
  const j = G.saison.courante;
  const etat = $("#compo-etat"); etat.replaceChildren();
  if (!j) etat.append("Saison terminée.");
  else if (j.verrouillee) etat.append(el("b", {}, `Journée ${j.numero} verrouillée`), ` depuis le coup d'envoi. Composition envoyée : ${G.equipe.composition ? "oui" : "non, score nul"}.`);
  else etat.append(`Journée ${j.numero}, du ${j.du} au ${j.au}. Verrouillage au premier coup d'envoi : ${new Date(j.cloture).toLocaleString("fr-FR")}. `, G.equipe.composition ? el("b", {}, `Composition envoyée le ${new Date(G.equipe.composition.soumise_le).toLocaleString("fr-FR")}.`) : el("b", {class: "rouge"}, "Aucune composition envoyée."));
  $("#btn-envoyer").disabled = !ok || !j || j.verrouillee;
  const B = $("#banc"); B.replaceChildren();
  zoneDepot(B, {type: "banc"});
  C.banc.forEach((i, r) => B.append(ligneBanc(i, r)));
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
  rendreClub();
}
async function rendreClub() {
  const d = await api("/club"); G.club = d.cartes;
  const R = $("#club-liste"); R.replaceChildren();
  const eff = d.cartes.filter(x => x.dans_effectif), res = d.cartes.filter(x => !x.dans_effectif);
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
    else if (vise) n.classList.add(peutJouer(pris, n._fam) ? "cible" : "interdit");
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
  const fam = slotsFam(C.formation)[cible.i];
  if (!peutJouer(id, fam)) { toast(`${carte(id).nom} n'a jamais joué ${NOM_FAM[fam].toLowerCase()}`); PRISE = null; rendreEquipe(false); return; }
  const occupant = C.slots[cible.i];
  if (src.type === "slot") {
    if (src.i === cible.i) { PRISE = null; rendreEquipe(false); return; }
    const famOrigine = slotsFam(C.formation)[src.i];
    C.slots[cible.i] = id;
    if (occupant !== null && peutJouer(occupant, famOrigine)) C.slots[src.i] = occupant;
    else { C.slots[src.i] = null; if (occupant !== null) { C.banc.unshift(occupant); if (C.cap === occupant) C.cap = null; } }
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
  else if (vise) classes.push(peutJouer(pris, fam) ? (aLePoste(pris, poste) ? "cible" : "cible-ligne") : "interdit");
  if (i !== null && !peutJouer(i, fam)) classes.push("faute");
  else if (i !== null && horsPoste(i, poste)) classes.push("dephase");
  const nomPoste = POSTE_COURT[poste] || poste;
  const titre = i === null ? `Case ${nomPoste.toLowerCase()} vide`
    : horsPoste(i, poste)
      ? `${carte(i).nom} joue ${nomPoste.toLowerCase()}, un poste qu'il n'a pas tenu : −${MALUS_HORS_POSTE} sur chaque attribut.`
      : `${carte(i).nom} — ${nomPoste}. Glisse-le ailleurs, ou touche-le puis touche sa destination.`;
  const d = el("div", {class: classes.join(" "), tabindex: "0", title: titre,
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
  d.append(el("div", {class: "slot-poste" + (horsPoste(i, poste) ? " dephase" : "")}, POSTE_ABBR[poste] || fam));
  if (C.cap === i) d.append(el("div", {class: "cap"}, "C"));
  d.append(el("button", {class: "slot-menu", title: "Options", onclick: e => { e.stopPropagation(); PRISE = null; menuSlot(s); }}, "···"));
  return d;
}
function menuSlot(s) {
  const i = C.slots[s]; const poste = slotsPostes(C.formation)[s];
  const fam = FAM_POSTE[poste] || "MID"; const dlg = $("#fiche"); dlg.replaceChildren();
  const c = carte(i);
  const box = el("div", {class: "fiche"}, el("h3", {class: "anton"}, c.nom),
    el("p", {class: "compteur"}, `${POSTE_COURT[poste] || poste} · OVR ${ovr(i)} · a tenu `
      + (c.postes || []).map(x => (POSTE_COURT[x] || x).toLowerCase()).join(", ")),
    horsPoste(i, poste) ? el("div", {class: "avert"},
      `Hors poste : −${MALUS_HORS_POSTE} sur chacun de ses attributs pendant le match.`) : null);
  const acts = el("div", {class: "actions", style: "justify-content:flex-start"});
  acts.append(el("button", {class: "primaire", onclick: () => { C.cap = i; dlg.close(); rendreEquipe(false); }}, "Nommer capitaine"));
  // the bench, those who really hold the position first
  const remplacants = C.banc.filter(x => peutJouer(x, fam))
    .sort((x, y) => (aLePoste(y, poste) - aLePoste(x, poste)) || (ovr(y) - ovr(x)));
  for (const b of remplacants) acts.append(el("button", {onclick: () => { C.banc = C.banc.map(x => x === b ? i : x); C.slots[s] = b; if (C.cap === i) C.cap = b; dlg.close(); rendreEquipe(false); }},
    `Remplacer par ${carte(b).nom} (${ovr(b)})${aLePoste(b, poste) ? "" : " — hors poste"}`));
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
const EVT_ICONE = {but: "⚽", arret: "🧤", occasion: "✗", tactique: "⇄", corner: "⛳", faute: "⚠",
  jaune: "🟨", rouge: "🟥", horsjeu: "🚩", changement: "🔁", blessure: "🚑"};
let LOBBY = {timer: null, tac: {tempo: "equilibre", bloc: "median", risque: "equilibre"}, vus: 0};

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
      g.append(el("button", {class: "tac" + (tac[axe] === v ? " actif" : ""), onclick: () => { tac[axe] = v; onChange(); }}, AXE_TXT[axe][v]));
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
  const maj = () => { const n = panneauEntree(d); p.replaceWith(n); };
  p.append(selecteurTactique(LOBBY.tac, maj));
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

function panneauMatch(d) {
  const m = d.match, moi = d.cote === "b" ? 1 : 0, lui = 1 - moi;
  const bloc = el("div", {});
  bloc.append(panneauTerrain(d, d.cote === "b" ? "b" : "a"));
  const p = el("div", {class: "panneau match-live"});
  bloc.append(p);
  p.append(el("div", {class: "live-tete"},
    el("div", {class: "live-eq"}, el("div", {class: "nom anton"}, m.noms[0]), el("div", {class: "style"}, m.style.a)),
    el("div", {class: "live-score anton"}, `${m.score[0]} – ${m.score[1]}`),
    el("div", {class: "live-eq droite"}, el("div", {class: "nom anton"}, m.noms[1]), el("div", {class: "style"}, m.style.b))));
  const pct = Math.round(100 * m.minute / d.minutes);
  p.append(el("div", {class: "horloge" + (m.pause ? " suspendue" : "")}, el("i", {style: `width:${pct}%`}),
    el("b", {}, m.fini ? "Terminé" : m.pause ? `${m.minute}' — arrêté` : `${m.minute}'`)));
  const stats = el("div", {class: "live-stats"});
  for (const [lib, va, vb] of [["Possession", m.possession[0] + " %", m.possession[1] + " %"],
                               ["Tirs", m.tirs[0], m.tirs[1]], ["xG", m.xg[0].toFixed(2), m.xg[1].toFixed(2)],
                               ["Corners", m.corners?.[0] ?? 0, m.corners?.[1] ?? 0],
                               ["Fautes", m.fautes?.[0] ?? 0, m.fautes?.[1] ?? 0],
                               ["Cartons", cartons(m, 0), cartons(m, 1)]])
    stats.append(el("div", {class: "sl"}, el("b", {}, String(va)), el("span", {}, lib), el("b", {}, String(vb))));
  p.append(stats);
  const fil = el("div", {class: "fil"});
  for (const e of [...m.evenements].reverse())
    fil.append(el("div", {class: "evt " + e.type + (e.cote === "AB"[moi] ? " mien" : "")},
      el("span", {class: "min"}, e.minute + "'"), el("span", {class: "ico"}, EVT_ICONE[e.type] || "•"),
      el("span", {class: "txt"}, e.texte)));
  if (!m.evenements.length) fil.append(el("p", {class: "compteur"}, "Le match vient de commencer."));
  p.append(fil);
  if (!m.fini) {
    p.append(blocAjuster(d, "/lobby/tactique", "/lobby/pause", rendreLobby));
  } else {
    const r = m.resultat === "N" ? "Match nul" : ((m.resultat === "A") === (moi === 0) ? "Victoire" : "Défaite");
    const de = m.elo_apres && m.elo_apres[moi] !== null ? m.elo_apres[moi] - m.elo_avant[moi] : null;
    p.append(el("div", {class: "live-fin"}, el("b", {class: "anton"}, r),
      de === null ? el("span", {}, m.defi ? " · défi, hors classement" : "") : el("span", {}, ` · Elo ${de > 0 ? "+" : ""}${de.toFixed(1)}`),
      el("button", {class: "primaire", onclick: () => rendreLobby()}, "Rejouer")));
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
function panneauMatchSolo(c) {
  const d = {match: c.match, cote: "a", duree: c.match.duree, minutes: c.match.minutes};
  const b = el("div", {});
  b.append(panneauTerrain(d, "a"));
  const m = c.match;
  const p = el("div", {class: "panneau match-live"});
  const stats = el("div", {class: "live-stats"});
  for (const [lib, va, vb] of [["Possession", m.possession[0] + " %", m.possession[1] + " %"],
                               ["Tirs", m.tirs[0], m.tirs[1]], ["xG", m.xg[0].toFixed(2), m.xg[1].toFixed(2)],
                               ["Corners", m.corners?.[0] ?? 0, m.corners?.[1] ?? 0],
                               ["Fautes", m.fautes?.[0] ?? 0, m.fautes?.[1] ?? 0],
                               ["Cartons", cartons(m, 0), cartons(m, 1)]])
    stats.append(el("div", {class: "sl"}, el("b", {}, String(va)), el("span", {}, lib), el("b", {}, String(vb))));
  p.append(stats);
  const fil = el("div", {class: "fil"});
  for (const e of [...m.evenements].reverse())
    fil.append(el("div", {class: "evt " + e.type + (e.cote === "A" ? " mien" : "")},
      el("span", {class: "min"}, e.minute + "'"), el("span", {class: "ico"}, EVT_ICONE[e.type] || "•"),
      el("span", {class: "txt"}, e.texte)));
  if (!m.evenements.length) fil.append(el("p", {class: "compteur"}, "Le match vient de commencer."));
  p.append(fil);
  if (!m.fini) {
    p.append(blocAjuster(d, "/solo/tactique", "/solo/pause", rendreSolo));
  } else {
    p.append(el("p", {class: "compteur"}, "Match terminé, la journée se clôture…"));
  }
  b.append(p);
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
             dernier: null, phases: [], i: 0, pas: 2700, arret: false};

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
      rang.forEach((_, k) => out.push([x, (k + 1) / (rang.length + 1)]));
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
    el("div", {class: "t2d-bandeau", hidden: true}));
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

function bougerTerrain(t, cote, zone, moi) {
  if (!T2D.pions) return;
  const dec = {a: 0, b: 0};
  if (cote !== null && cote !== undefined) {
    const avance = ((zone === undefined ? 1 : zone) - 1) * GLISSE_2D;
    dec["ab"[cote]] = avance;
    dec["ab"[1 - cote]] = -avance * 0.55;
  }
  for (const [cle, p] of Object.entries(T2D.pions)) {
    const c = cle.slice(0, 1);
    const [x, y] = p._base;
    const [g, h] = ecran(c, x + dec[c], y, moi);
    p.style.left = (g * 100) + "%";
    p.style.top = (h * 100) + "%";
  }
}

// Une phase : le ballon va sur celui qui l'a, le porteur s'allume, et
// pour un tir le ballon quitte vraiment le pied pour aller au but.
function jouerPhase(t, ph, moi) {
  const b = t.querySelector(".t2d-ballon");
  const jeu = t.querySelector(".t2d-jeu");
  if (!ph) { b.hidden = true; return; }
  const cote = "ab"[ph.c];
  bougerTerrain(t, ph.c, ph.z, moi);
  for (const p of Object.values(T2D.pions || {}))
    p.classList.toggle("ballon", p.dataset.cote === cote && +p.dataset.pid === ph.p);
  const porteur = T2D.pions?.[cote + ":" + ph.p];
  b.classList.toggle("tir", ph.k === "tir" || ph.k === "rate");
  b.classList.toggle("dedans", ph.k === "but");
  T2D.arret = ARRETS_JEU.has(ph.k);
  jeu.classList.toggle("arret", T2D.arret);
  jeu.classList.toggle("celebre", ph.k === "but");
  if (ph.k === "tir" || ph.k === "but" || ph.k === "rate") {
    // une frappe manquée ne revient pas dans les pieds du tireur : elle
    // file à côté du but
    const [g, h] = buts(cote, moi, ph.k === "rate" ? (T2D.dernierTir ?? 0.5) : ph.t);
    const dehors = ph.k === "rate" ? (h < 0.5 ? -0.10 : 0.10) : 0;
    if (ph.k === "tir") T2D.dernierTir = ph.t;
    b.style.left = (g * 100) + "%";
    b.style.top = ((h + dehors) * 100) + "%";
    b.hidden = false;
  } else if (porteur) {
    b.style.left = porteur.style.left;
    b.style.top = porteur.style.top;
    b.hidden = false;
  } else {
    b.hidden = true;
  }
  // le libellé d'action vit dans la légende, au-dessus du terrain
  const nom = T2D.noeud && T2D.noeud.querySelector(".t2d-action");
  if (nom) {
    const j = porteur ? porteur.getAttribute("title").split(" · ")[0] : "";
    nom.textContent = (PHASE_TXT[ph.k] || "") + (j ? " — " + j : "");
    nom.className = "t2d-action " + ph.k;
  }
}

const ARRETS_JEU = new Set(["faute", "horsjeu", "but", "blessure", "carton"]);
const PHASE_TXT = {
  relance: "Relance", passe: "Passe", conduite: "Il perce", tir: "Frappe !", but: "BUT",
  arret: "Arrêt du gardien", rate: "À côté", degagement: "Dégagement", perte: "Perte de balle",
  duel: "Duel", faute: "Faute — coup de sifflet", carton: "Carton", coupfranc: "Coup franc",
  corner: "Corner", centre: "Centre", horsjeu: "Hors-jeu", engagement: "Engagement",
  blessure: "Blessure — le jeu est arrêté",
};

function annoncer(t, evt) {
  const bandeau = t.querySelector(".t2d-bandeau");
  if (!evt) { bandeau.hidden = true; return; }
  bandeau.replaceChildren(el("span", {class: "ico"}, EVT_ICONE[evt.type] || "•"),
    el("span", {class: "txt"}, evt.texte));
  bandeau.className = "t2d-bandeau " + evt.type;
  bandeau.hidden = false;
}

// Le moteur d'animation : une phase à la fois, enchaînées par setTimeout
// plutôt que par un intervalle fixe — le nombre de phases change d'une
// minute à l'autre, et un arrêt de jeu dure plus longtemps qu'une passe.
const POIDS_PHASE = {faute: 1.8, horsjeu: 1.6, but: 2.2, blessure: 2.2, carton: 1.5,
                     tir: 1.3, arret: 1.3, coupfranc: 1.2, corner: 1.3};

function delaiPhase(k, n) {
  const base = T2D.pas / Math.max(1, n);
  return Math.max(180, base * (POIDS_PHASE[k] || 0.9));
}

function chargerMinute() {
  T2D.m += 1;
  const ligne = T2D.fil[T2D.m - 1];
  T2D.phases = (ligne && ligne.s) || [];
  T2D.i = 0;
  const evt = ligne && ligne.e !== null && ligne.e !== undefined ? T2D.evts[ligne.e] : null;
  if (evt) T2D.dernier = {evt, quand: Date.now()};
  const h = T2D.noeud && T2D.noeud.querySelector(".t2d-minute");
  if (h) h.textContent = T2D.m + "'";
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
  const ph = T2D.phases[T2D.i++];
  jouerPhase(t, ph, moi);
  reAnnoncer(t);
  return delaiPhase(ph.k, T2D.phases.length);
}

function programmer(d) {
  clearTimeout(T2D.timer);
  T2D.timer = setTimeout(() => { T2D.timer = null; programmer(battre()); }, Math.max(120, d));
}

function arreterTerrain(oublier) {
  if (T2D.timer) { clearTimeout(T2D.timer); T2D.timer = null; }
  if (oublier) { T2D.noeud = null; T2D.cle = null; T2D.m = 0; T2D.dernier = null; T2D.phases = []; T2D.i = 0; }
}

// Le panneau est RÉUTILISÉ d'un sondage à l'autre, pas reconstruit :
// redessiner vingt-deux cartes toutes les deux secondes et demie
// relançait chaque transition CSS et effaçait le bandeau d'événement.
function panneauTerrain(d, moi) {
  const m = d.match;
  const cle = JSON.stringify([m.rencontre_id, moi, m.sur_le_terrain?.a, m.sur_le_terrain?.b,
                              m.formation?.a, m.formation?.b]);
  let p = T2D.noeud;
  if (!p || T2D.cle !== cle) {
    arreterTerrain();                       // nouveau match, ou nouveau onze
    p = el("div", {class: "panneau terrain-live"});
    p.append(el("div", {class: "t2d-tete"},
      el("div", {class: "eq"}, el("b", {class: "anton"}, m.noms[moi === "a" ? 0 : 1])),
      el("div", {class: "t2d-score anton"}, ""),
      el("div", {class: "eq droite"}, el("b", {class: "anton"}, m.noms[moi === "a" ? 1 : 0])),
      el("div", {class: "t2d-minute anton"}, "")));
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
  p.querySelector(".t2d-score").textContent =
    `${m.score[moi === "a" ? 0 : 1]} – ${m.score[moi === "a" ? 1 : 0]}`;
  T2D.fil = m.fil || [];
  T2D.cible = m.minute;
  T2D.evts = m.evenements || [];
  T2D.t = t; T2D.moi = moi;
  T2D.pas = Math.max(900, (d.duree * 1000) / (d.minutes || 90));
  if (T2D.m === 0) T2D.m = Math.max(0, T2D.cible - 1);
  if (T2D.m > T2D.cible) T2D.m = T2D.cible;
  p.querySelector(".t2d-minute").textContent = m.fini ? "Terminé" : T2D.m + "'";
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
const CHG = {cle: null, sortant: null, entrant: null};

function jaugeEndurance(v) {
  const n = v === undefined || v === null ? 100 : v;
  return el("span", {class: "endu", title: `Endurance ${Math.round(n)} %`},
    el("i", {class: n < 35 ? "vide" : n < 60 ? "basse" : "", style: `width:${Math.max(0, Math.min(100, n))}%`}));
}

function ligneJoueur(j, endu, role, onclick) {
  return el("button", {class: "chg-j", "data-pid": j.pid, "data-role": role, onclick},
    el("span", {class: "fam " + j.fam}, FAM_COURT[j.fam] || j.fam),
    el("div", {class: "qui"}, el("span", {class: "nom"}, j.nom),
      el("span", {class: "sous"}, POSTE_ABBR[j.slot] || j.slot || "")),
    jaugeEndurance(endu?.[j.pid]),
    el("b", {class: "num"}, String(j.ovr)));
}

function blocChangements(d, route = "/lobby/changement", rendre = rendreLobby) {
  const m = d.match, cote = d.cote === "b" ? "b" : "a";
  // Qui est SUR LE TERRAIN, pas qui a commencé : un remplaçant peut
  // ressortir, un expulsé non.  Le onze et le banc réunis sont le seul
  // endroit où les cartes elles-mêmes sont décrites.
  const tous = [...(m.onze?.[cote] || []), ...(m.banc?.[cote] || [])];
  const surTerrain = (m.sur_le_terrain?.[cote] || []).map(pid => tous.find(j => j.pid === pid)).filter(Boolean);
  const utilises = new Set(m.entres?.[cote] || []);
  const banc = (m.banc?.[cote] || []).filter(j => !utilises.has(j.pid));
  const endu = m.endurance?.[cote] || {};
  const blesses = (m.attente?.[cote] || []).map(pid => tous.find(j => j.pid === pid)).filter(Boolean);
  const b = el("div", {class: "changements"});
  const restants = SM_MAX_CHG - (m.changements?.[cote === "a" ? 0 : 1] ?? 0);

  // Une blessure arrête le match : tant que le manager n'a pas dit qui
  // entre, l'horloge ne repart pas.  C'est la seule décision qui bloque.
  if (blesses.length) {
    const bl = el("div", {class: "blessure-stop"},
      el("div", {class: "titre anton"}, "🚑 " + blesses.map(j => j.nom).join(", ") + (blesses.length > 1 ? " sortent" : " sort") + " sur blessure"),
      el("p", {}, m.pause ? "Le match est arrêté : choisis qui entre." : "Tu joues à " + (11 - blesses.length) + " tant que personne n'entre."));
    if (!banc.length || restants <= 0) {
      bl.append(el("p", {class: "compteur"}, "Plus personne à faire entrer : il faut finir en infériorité."));
    } else {
      const liste = el("div", {class: "chg-liste"});
      for (const j of banc)
        liste.append(ligneJoueur(j, endu, "in", async () => {
          try { await rendre(await api(route, {sortant: blesses[0].pid, entrant: j.pid})); toast(j.nom + " entre"); }
          catch (e) { toast(e.message); }
        }));
      bl.append(liste);
    }
    b.append(bl);
  }

  b.append(el("div", {class: "etiq"}, `Remplacements — il t'en reste ${Math.max(0, restants)}`));
  if (!banc.length) { b.append(el("p", {class: "compteur"}, "Personne sur le banc. Nomme des remplaçants sur l'écran Équipe avant de lancer un match.")); return b; }
  if (restants <= 0) { b.append(el("p", {class: "compteur"}, "Tu as fait tous tes changements.")); return b; }

  // La sélection est gardée entre deux sondages, à condition que le match
  // et les joueurs disponibles n'aient pas changé.
  const cle = JSON.stringify([m.rencontre_id, cote]);
  if (CHG.cle !== cle) { CHG.cle = cle; CHG.sortant = null; CHG.entrant = null; }
  if (!surTerrain.some(j => j.pid === CHG.sortant)) CHG.sortant = null;
  if (!banc.some(j => j.pid === CHG.entrant)) CHG.entrant = null;

  const choix = el("div", {class: "chg-choix"});
  const maj = () => {
    choix.querySelectorAll("[data-pid]").forEach(n => n.classList.toggle(
      "choisi", (n.dataset.role === "out" && +n.dataset.pid === CHG.sortant) || (n.dataset.role === "in" && +n.dataset.pid === CHG.entrant)));
    valider.disabled = !(CHG.sortant && CHG.entrant);
  };
  const colonne = (titre, ids, role) => {
    const c = el("div", {}, el("div", {class: "etiq"}, titre));
    for (const j of ids)
      c.append(ligneJoueur(j, endu, role, () => {
        if (role === "out") CHG.sortant = j.pid; else CHG.entrant = j.pid;
        maj();
      }));
    return c;
  };
  const valider = el("button", {class: "primaire", disabled: true, onclick: async () => {
    const paire = {sortant: CHG.sortant, entrant: CHG.entrant};
    CHG.sortant = null; CHG.entrant = null;
    try { await rendre(await api(route, paire)); toast("Changement enregistré"); }
    catch (e) { toast(e.message); }
  }}, "Faire le changement");
  // Le plus fatigué d'abord : c'est lui qu'on cherche quand on ouvre ce
  // panneau à la soixante-dixième minute.
  const parFatigue = [...surTerrain].sort((x, y) => (endu[x.pid] ?? 100) - (endu[y.pid] ?? 100));
  choix.append(colonne("Il sort", parFatigue, "out"), colonne("Il entre", banc, "in"));
  b.append(choix, valider);
  maj();
  return b;
}
const SM_MAX_CHG = 5;
const MALUS_HORS_POSTE = 10;

// Le panneau tactique du match : les trois axes, la formation, et — pour
// un match à un seul humain — la pause.
function blocAjuster(d, routeTac, routePause, rendre) {
  const m = d.match, cote = d.cote === "b" ? "b" : "a";
  const tac = {...(m.tactique[cote] || LOBBY.tac)};
  tac.formation = m.formation?.[cote] || tac.formation || "4-3-3";
  const p = el("div", {class: "panneau interne"}, el("h3", {class: "anton"}, "Ajuster"),
    el("p", {class: "compteur"}, "Un changement prend effet à la minute suivante : il ne touche jamais ce qui est déjà joué."));
  const envoyer = async () => {
    try { await rendre(await api(routeTac, {tactique: tac})); } catch (e) { toast(e.message); }
  };
  if (m.solitaire && routePause)
    p.append(el("div", {class: "actions", style: "justify-content:flex-start;margin-bottom:8px"},
      el("button", {class: m.pause ? "primaire" : "", onclick: async () => {
        try { await rendre(await api(routePause, {pause: !m.pause})); } catch (e) { toast(e.message); }
      }}, m.pause ? "▶ Reprendre" : "⏸ Mettre en pause")));
  p.append(selecteurTactique(tac, envoyer));
  // La formation change EN COURS DE MATCH : les onze restent sur le
  // terrain, on les redistribue sur les postes de la nouvelle forme comme
  // le fait le meilleur onze, et ceux qui se retrouvent hors de leur
  // poste le paient.
  const g = el("div", {class: "tac-groupe"}, el("span", {class: "tac-titre"}, "Formation"));
  for (const f of Object.keys(RANGS))
    g.append(el("button", {class: "tac" + (tac.formation === f ? " actif" : ""),
      onclick: () => { tac.formation = f; envoyer(); }}, f));
  p.append(el("div", {class: "tactiques"}, g));
  p.append(blocChangements(d, routeTac === "/solo/tactique" ? "/solo/changement" : "/lobby/changement", rendre));
  return p;
}

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
    const moi = await api("/moi"); connecte(moi);
    if (moi.connecte) { const h = location.hash.replace("#", ""); await montrer(["packs", "encheres", "marche", "equipe", "lobby", "solo", "journee", "classement", "admin"].includes(h) ? h : (idsEffectif().length ? "equipe" : "packs")); }
  } catch (e) { toast("Serveur injoignable : " + e.message); }
})();

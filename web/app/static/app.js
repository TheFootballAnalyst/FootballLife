"use strict";
// FootballLife — front-end of web/app/serveur.py.  Vanilla JS, one file.
// State lives on the server; this page only holds what it just fetched.

const QUOTA = {};
const FAMS = ["GK", "DEF", "MID", "FWD"];
// Les tables de libellés lisent le dictionnaire de la langue (static/lang) : une
// table est un préfixe de clés, et NOM_FAM.GK vaut t("fam.GK").
const tableT = prefixe => new Proxy({}, {get: (_, k) => typeof k === "string" && existeT(prefixe + k) ? t(prefixe + k) : undefined,
  has: (_, k) => typeof k === "string" && existeT(prefixe + k)});
const NOM_FAM = tableT("fam.");
const PLURIEL = tableT("fam_pl.");
const POSTE_COURT = tableT("poste.");
// Un poste sans son côté : « Lateral gauche » → « Lateral ».
const posteBase = p => (p === "Milieu gauche" || p === "Milieu droit") ? "Milieu de couloir" : (p || "").replace(/ (gauche|droit)$/, "");
const ATTR_NOMS = tableT("attr.");
const ATTR_NOMS_GARDIEN = tableT("attr_gk.");   // a keeper's PRO axis is his short passing (jeu/bareme.py)
const PIEDS = tableT("pied.");
// Les deux pieds, en jauges sur deux icônes de pied : le pied fort est
// plein, le mauvais pied se remplit selon sa qualité (1 à 5, d'après la
// fiche EA).  Un droitier dont le mauvais pied est à 5 est simplement
// ambidextre : deux pieds pleins.  Pas d'étoiles.
const PIED_TRACE = "M10 2.2c-3.1 0-5.6 3.4-5.6 8.6 0 3.2 1.2 5.6 1.2 9.2 0 3.6-2 5.4-2 7.8 0 2.4 2 3.6 4.2 3.6 2.1 0 3.6-1.2 4.6-3.2 1-2 1.2-4.4 1.2-7.4 0-3.2 2-5.8 2-9.8 0-5.4-2.5-8.8-5.6-8.8z";
const PIED_ORTEILS = "M5.2 3.3a2.2 2.2 0 1 0 0.1 0zM9 1.4a1.5 1.5 0 1 0 0.1 0zM12.2 1.6a1.3 1.3 0 1 0 0.1 0zM14.8 2.6a1.15 1.15 0 1 0 0.1 0zM16.9 4.2a1 1 0 1 0 0.1 0z";
function niveauxPieds(c) {
  if (!c || !c.pied) return null;
  const faible = c.pied === "deux" ? 5 : Math.max(0, Math.min(5, +c.pied_faible || 0));
  const g = c.pied === "gauche" || c.pied === "deux" ? 1 : faible / 5;
  const d = c.pied === "droit" || c.pied === "deux" ? 1 : faible / 5;
  return {gauche: g, droit: d, faible, connu: c.pied === "deux" || !!c.pied_faible};
}
function iconePied(cote, niveau, id) {
  const H = 32, y = H - H * niveau;
  const miroir = cote === "gauche" ? ' transform="scale(-1,1) translate(-20,0)"' : "";
  const w = el("span", {class: "pied " + cote + (niveau >= 0.99 ? " plein" : niveau <= 0 ? " vide" : "")});
  w.innerHTML = `<svg viewBox="0 0 20 32" aria-hidden="true"><defs><clipPath id="${id}"><rect x="0" y="${y.toFixed(1)}" width="20" height="${(H - y).toFixed(1)}"/></clipPath></defs>`
    + `<g class="fond"${miroir}><path d="${PIED_TRACE}"/><path d="${PIED_ORTEILS}"/></g>`
    + `<g class="jauge" clip-path="url(#${id})"${miroir}><path d="${PIED_TRACE}"/><path d="${PIED_ORTEILS}"/></g></svg>`;
  return w;
}
let _piedId = 0;
function piedsDe(c, compact = false) {
  const n = niveauxPieds(c);
  const w = el("span", {class: "pieds" + (compact ? " compact" : "") + (n ? "" : " inconnu")});
  if (!n) {
    w.title = t("pied.inconnu");
    w.append(iconePied("gauche", 0, "pg" + (++_piedId)), iconePied("droit", 0, "pd" + (++_piedId)));
    return w;
  }
  const txt = n.gauche >= 1 && n.droit >= 1 ? t("pied.ambidextre_titre")
    : t("pied.fort_titre", {fort: t("pied.cote_" + c.pied), faible: t("pied.cote_" + (c.pied === "droit" ? "gauche" : "droit")), n: n.faible}) + (n.connu ? "" : t("pied.qualite_inconnue"));
  w.title = txt;
  w.append(iconePied("gauche", n.gauche, "pg" + (++_piedId)), iconePied("droit", n.droit, "pd" + (++_piedId)));
  if (!compact) w.append(el("span", {class: "pieds-txt"}, n.gauche >= 1 && n.droit >= 1 ? t("pied.deux") : `${PIEDS[c.pied]} · ${n.faible ? n.faible + "/5" : "?"}`));
  return w;
}
// La fiche physique (EA) : les neuf jauges et les mesures.
const PHYSIQUE_CLES = ["acceleration", "vitesse_pointe", "agilite", "equilibre", "reactions", "endurance", "force", "detente", "agressivite"];
function blocPhysique(d) {
  const ph = d.physique;
  const b = el("div", {class: "physique-bloc"});
  // les trois globaux à côté de l'OVR : PHY (le profil physique), OFF et DEF (les attributs)
  const g = d.globaux;
  if (g && (g.phy != null || g.off != null)) {
    const ligne = el("div", {class: "globaux"});
    const dev = (g.source ? " (" + g.source + ")" : "") + (g.leviers ? " — " + g.leviers : "");
    for (const [k, v, titre] of [["PHY", g.phy, t("phys.phy_titre")], ["OFF", g.off, t("phys.off_titre") + dev], ["DEF", g.def, t("phys.def_titre") + dev]]) {
      if (v == null) continue;
      ligne.append(el("div", {class: "global", title: titre}, el("span", {}, k), el("b", {class: "num" + (v >= 80 || v === "Haut" ? " haut" : "")}, String(v))));
    }
    b.append(ligne);
  }
  b.append(el("div", {class: "etiq"}, t("phys.titre")));
  if (!ph) { b.append(el("p", {class: "compteur"}, t("phys.sans_fiche"))); return b; }
  const A = el("div", {class: "attrs physique"});
  for (const k of PHYSIQUE_CLES) {
    const v = ph[k]; if (v === undefined || v === null) continue;
    A.append(el("div", {class: "attr"}, el("span", {}, t("phys." + k)), el("div", {class: "jauge"}, el("i", {class: v >= 80 ? "haut" : "", style: `width:${Math.max(0, Math.min(100, v))}%`})), el("b", {class: "num"}, String(v))));
  }
  b.append(A);
  const mesures = [];
  if (ph.taille) mesures.push(`${Math.floor(ph.taille / 100)} m ${String(ph.taille % 100).padStart(2, "0")}`);
  if (ph.poids) mesures.push(`${ph.poids} kg`);
  if (ph.gestes) mesures.push(t("phys.gestes", {n: ph.gestes}));
  if (ph.note_physique) mesures.push(t("phys.note", {n: ph.note_physique}));
  if (ph.defaut) b.append(el("div", {class: "compteur"}, t("phys.defaut") + (mesures.length ? " (" + mesures.join(" · ") + ")" : "") + "."));
  else if (mesures.length) b.append(el("div", {class: "compteur"}, mesures.join(" · ") + " · " + t("phys.source_ea")));
  const m = d.mesures;
  if (m && m.n) {
    const km = v => (Math.round(v / 100) / 10).toLocaleString(LOCALE, {minimumFractionDigits: 1, maximumFractionDigits: 1});
    b.append(el("div", {class: "compteur mesure", title: t("phys.mesure_titre")},
      t("phys.mesure", {n: m.n, vmax: (Math.round(m.vmax * 10) / 10).toLocaleString(LOCALE), km: km(m.dist90), sprints: Math.round(m.nsprint90)})));
  }
  return b;
}
const dateFr = iso => { if (!iso) return ""; const [a, m, j] = iso.split("-"); try { return new Date(Date.UTC(+a, +m - 1, +j)).toLocaleDateString(LOCALE, {day: "numeric", month: "short", year: "numeric", timeZone: "UTC"}); } catch (e) { return `${+j}/${+m}/${a}`; } };
const AXES = {champ:["FIN","CRE","PRO","DEF","DRI","CON"], gardien:["ARR","EVI","SOR","REL","BUT","PRO"]};
const f1 = x => (Math.round((+x || 0) * 10) / 10).toFixed(1);
// money: every amount is in M€ (0.1 = 100 k€)
// Les montants sont en M€.  Le palier du milliard sert au compte de
// démonstration, qui démarre à dix : « 10000,0 M€ » ne se lit pas.
const virgule = x => (typeof LOCALE === "string" && !LOCALE.startsWith("fr")) ? x : x.replace(".", ",");
const fM = (x, signe = false) => { const v = +x || 0, a = Math.abs(v), s = v < 0 ? "−" : signe && v > 0 ? "+" : "";
  if (a < 1) return s + Math.round(a * 1000) + " k€";
  if (a < 10) return s + virgule(a.toFixed(2)) + " M€";
  if (a < 1000) return s + virgule((Math.round(a * 10) / 10).toFixed(1)) + " M€";
  return s + virgule((a / 1000).toFixed(2)) + " Md€"; };

// ISO-3 (FotMob) -> ISO-2, for the flag emoji on the card
const ISO2 = {FRA:"FR",ENG:"GB",SCO:"GB",WAL:"GB",NIR:"GB",IRL:"IE",ESP:"ES",ITA:"IT",GER:"DE",POR:"PT",NED:"NL",BEL:"BE",SUI:"CH",AUT:"AT",DEN:"DK",SWE:"SE",NOR:"NO",FIN:"FI",ISL:"IS",POL:"PL",CZE:"CZ",SVK:"SK",HUN:"HU",ROU:"RO",BUL:"BG",SRB:"RS",CRO:"HR",SVN:"SI",BIH:"BA",MNE:"ME",MKD:"MK",ALB:"AL",KOS:"XK",GRE:"GR",TUR:"TR",UKR:"UA",RUS:"RU",BLR:"BY",GEO:"GE",ARM:"AM",AZE:"AZ",KAZ:"KZ",ISR:"IL",CYP:"CY",MLT:"MT",LUX:"LU",LTU:"LT",LVA:"LV",EST:"EE",MDA:"MD",BRA:"BR",ARG:"AR",URU:"UY",PAR:"PY",CHI:"CL",COL:"CO",PER:"PE",ECU:"EC",VEN:"VE",BOL:"BO",MEX:"MX",USA:"US",CAN:"CA",JAM:"JM",CRC:"CR",HON:"HN",PAN:"PA",GUA:"GT",SLV:"SV",HAI:"HT",CUB:"CU",DOM:"DO",TRI:"TT",CUW:"CW",SUR:"SR",MAR:"MA",ALG:"DZ",TUN:"TN",EGY:"EG",SEN:"SN",CIV:"CI",CMR:"CM",NGA:"NG",GHA:"GH",MLI:"ML",GUI:"GN",BFA:"BF",COD:"CD",CGO:"CG",GAB:"GA",ANG:"AO",MOZ:"MZ",ZAM:"ZM",ZIM:"ZW",RSA:"ZA",KEN:"KE",UGA:"UG",TAN:"TZ",ETH:"ET",SUD:"SD",TOG:"TG",BEN:"BJ",NIG:"NE",GAM:"GM",SLE:"SL",LBR:"LR",CPV:"CV",GNB:"GW",EQG:"GQ",CTA:"CF",CHA:"TD",MTN:"MR",LBY:"LY",COM:"KM",MAD:"MG",BDI:"BI",RWA:"RW",JPN:"JP",KOR:"KR",CHN:"CN",AUS:"AU",NZL:"NZ",IRN:"IR",IRQ:"IQ",KSA:"SA",QAT:"QA",UAE:"AE",UZB:"UZ",IND:"IN",THA:"TH",VIE:"VN",PHI:"PH",IDN:"ID",MAS:"MY",SYR:"SY",JOR:"JO",LBN:"LB",PLE:"PS"};
const drapeau = code => { const c = ISO2[code] || (code && code.length === 2 ? code : null); if (!c) return ""; return String.fromCodePoint(...[...c.toUpperCase()].map(ch => 0x1F1E6 + ch.charCodeAt(0) - 65)); };
const ageTxt = c => c.age ? t("carte.ans", {n: c.age}) : "";
// pour chercher : minuscules, sans accents
const norm = s => (s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
const FAM_COURT = tableT("fam_court.");

// ---- état local (miroir de ce que le serveur a renvoyé) ----
const G = {moi: null, saison: null, cartes: [], idx: new Map(), equipe: null, compo: null, ecran: "connexion", ventes: [], club: [], packs: null};
const ventesDe = id => G.ventes.filter(v => v.player_id === id);
let TAILLE = 18, BANC_MAX = 7, FORMATIONS = {"4-3-3": [1,4,3,3]}, LIMITES = {GK: [1,1], DEF: [3,5], MID: [2,5], FWD: [1,4]};
let RANGS = {"4-3-3": [["Gardien"], ["Lateral gauche","Defenseur central","Defenseur central","Lateral droit"],
  ["Milieu relayeur","Milieu defensif","Milieu relayeur"], ["Ailier gauche","Buteur","Ailier droit"]]};
let FAM_POSTE = {"Gardien":"GK","Defenseur central":"DEF","Lateral":"DEF","Lateral gauche":"DEF","Lateral droit":"DEF",
  "Milieu defensif":"MID","Milieu relayeur":"MID","Milieu offensif":"MID","Milieu de couloir":"MID","Milieu gauche":"MID","Milieu droit":"MID","Ailier":"FWD","Ailier droit":"FWD",
  "Ailier gauche":"FWD","Buteur":"FWD"};
// Ce qu'une carte perd à chaque poste (scoring.malus_poste), servi par le
// serveur : {poste de la case: {poste tenu: malus}}.  Et de combien un
// poste se dessine devant ou derrière sa ligne.
let MALUS_POSTES = {}, MALUS_GK = 30, PROF_POSTE = {"Milieu defensif": -0.045, "Milieu offensif": 0.045};
// ... et ce que les attributs y changent (scoring.POIDS_POSTE) : hors de
// son poste, une carte paie la moitié de la distance moins ce que ses
// attributs disent du nouveau poste, jusqu'à un petit bonus.
let POIDS_POSTES = {}, BONUS_POSTE_MAX = 3, PART_DISTANCE = 0.5, PART_ECART = 0.6;
let LIBELLES_FORMATION = {"4-3-3": "4-3-3 (1)"};
const nomFormation = f => LIBELLES_FORMATION[f] || f;

// ---- utilitaires ----
const $ = s => document.querySelector(s);
const el = (tag, attrs = {}, ...kids) => { const e = document.createElement(tag); for (const [k, v] of Object.entries(attrs)) { if (v === null || v === false || v === undefined) continue; if (k === "class") e.className = v; else if (k.startsWith("on")) e.addEventListener(k.slice(2), v); else e.setAttribute(k, v); } for (const k of kids) if (k != null) e.append(k); return e; };

// ---- les langues (PLAN § 3) ----
// Un dictionnaire par langue (static/lang/<code>.json), le français comme
// langue source et secours.  t(clé, {nom}) met les paramètres ; une valeur
// {"1": ..., "n": ...} choisit sa forme sur le paramètre n.  La langue vient du
// profil (fl_langue), sinon du navigateur.  « xx » est la pseudo-traduction :
// le français allongé de 30 % avec des accents, pour voir ce qui déborde.
const LANGUES = {fr: "Français", en: "English"};
let LANGUE = "fr", LOCALE = "fr-FR", DICO = {}, DICO_FR = {};
const LOCALES = {fr: "fr-FR", en: "en-GB"};
function langueChoisie() {
  try { const l = localStorage.getItem("fl_langue"); if (l && (LANGUES[l] || l === "xx")) return l; } catch (e) {}
  const nav = (navigator.language || "fr").slice(0, 2).toLowerCase();
  return LANGUES[nav] ? nav : "fr";
}
function pseudoTraduire(d) {
  const acc = {a: "å", e: "ë", i: "ï", o: "ø", u: "ü", c: "ç", n: "ñ", A: "Å", E: "Ë", O: "Ø", U: "Ü"};
  // les {paramètres} restent intacts : ce sont des clés, pas du texte
  const f = s => { const x = s.replace(/\{\w+\}|[aeiouAEOUcn]/g, ch => ch.length > 1 ? ch : (acc[ch] || ch)); return x + " " + "~".repeat(Math.ceil(x.replace(/\{\w+\}/g, "").length * 0.3)); };
  const out = {};
  for (const [k, v] of Object.entries(d)) out[k] = typeof v === "object" ? Object.fromEntries(Object.entries(v).map(([a, b]) => [a, f(b)])) : f(v);
  return out;
}
async function chargerLangue(code) {
  const charge = async c => { try { const r = await fetch(`/static/lang/${c}.json?v=1`); return r.ok ? await r.json() : {}; } catch (e) { return {}; } };
  DICO_FR = await charge("fr");
  LANGUE = code;
  DICO = code === "fr" ? DICO_FR : code === "xx" ? pseudoTraduire(DICO_FR) : await charge(code);
  LOCALE = LOCALES[code] || "fr-FR";
}
const existeT = cle => DICO[cle] !== undefined || DICO_FR[cle] !== undefined;
function t(cle, p) {
  let s = DICO[cle]; if (s === undefined) s = DICO_FR[cle];
  if (s === undefined) return cle;
  if (typeof s === "object") s = (p && +p.n === 1) ? (s["1"] ?? s.n) : (s.n ?? s["1"]);
  return String(s).replace(/\{(\w+)\}/g, (_, k) => (p && p[k] !== undefined && p[k] !== null) ? p[k] : "");
}
function appliquerLangue() {
  document.documentElement.lang = LANGUE === "xx" ? "fr" : LANGUE;
  for (const e of document.querySelectorAll("[data-t]")) e.textContent = t(e.dataset.t);
  for (const e of document.querySelectorAll("[data-t-placeholder]")) e.placeholder = t(e.dataset.tPlaceholder);
  for (const e of document.querySelectorAll("[data-t-title]")) e.title = t(e.dataset.tTitle);
  const sel = $("#langue");
  if (sel) {
    sel.replaceChildren(...Object.entries(LANGUES).map(([c, nom]) => el("option", {value: c}, nom)));
    if (LANGUE === "xx") sel.append(el("option", {value: "xx"}, "Pseudo"));
    sel.value = LANGUE;
    sel.onchange = () => { try { localStorage.setItem("fl_langue", sel.value); } catch (e) {} location.reload(); };
  }
}
// Le commentaire d'un événement de match : par gabarit dans la langue de
// l'écran quand la feuille en donne un (moteur B), sinon le texte tel quel.
// L'ordinal d'un rang : 1er, 2e en français ; 1st, 2nd, 3rd en anglais.
function ordinal(n) {
  n = +n;
  if (LANGUE === "en") { const r = n % 100; return n + ((r >= 11 && r <= 13) ? "th" : ({1: "st", 2: "nd", 3: "rd"}[n % 10] || "th")); }
  return n + (n === 1 ? t("ordinal.premier") : t("ordinal.autres"));
}
const texteEvt = e => (e && e.gab && existeT("evt." + e.gab.k)) ? t("evt." + e.gab.k, e.gab) : (e ? e.texte : "");
function toast(msg) { const t = $("#toast"); t.textContent = msg; t.classList.add("on"); clearTimeout(t._t); t._t = setTimeout(() => t.classList.remove("on"), 2200); }
async function api(chemin, corps, methode) {
  const r = await fetch("/api" + chemin, {method: methode || (corps ? "POST" : "GET"), headers: corps ? {"Content-Type": "application/json"} : {}, body: corps ? JSON.stringify(corps) : undefined, credentials: "same-origin"});
  let data = null; try { data = await r.json(); } catch (e) {}
  if (!r.ok) {
    const d = data && data.detail;
    let msg = r.statusText;
    if (d && typeof d === "object" && d.code) msg = existeT("err." + d.code) ? t("err." + d.code, d.params) : (d.message || d.code);
    else if (typeof d === "string") msg = d;
    else if (d) msg = JSON.stringify(d);
    const e = new Error(msg); e.status = r.status; e.code = d && d.code; throw e;
  }
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
  const f = el("div", {class: "forme", title: t("carte.dernieres_notes")});
  for (const [n] of (c.notes || [])) { const b = el("i"); b.style.height = (4 + Math.max(0, n - 1) * 2.4) + "px"; b.style.background = n >= 7 ? "var(--vert)" : n < 5 ? "var(--rouge)" : "var(--sourd)"; f.append(b); }
  return f;
}
const formeMoy = c => { const r = (c.notes || []).slice(-5); const w = r.reduce((a, x) => a + x[1] / 90, 0); return w ? r.reduce((a, x) => a + x[0] * x[1] / 90, 0) / w : 0; };

// ---- chargement ----
async function rafraichir(tout) {
  G.saison = await api("/saison");
  majBadgeJournee(G.saison.derniere ? G.saison.derniere.numero : 0);
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
  $("#marque-sous").textContent = t("statut.saison", {saison: G.saison?.saison || ""});
  $("#st-j").textContent = j ? t("journee.j") + j.numero + (j.verrouillee ? " 🔒" : "") : t("statut.fin");
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
    await ({packs: rendrePacks, encheres: rendreEncheres, marche: rendreMarche, equipe: rendreEquipe, lobby: rendreLobby, solo: rendreSolo, journee: rendreJournee, classement: rendreClassement, compte: rendreCompte, admin: rendreAdmin}[ecran] || (async () => {}))();
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
  $("#champ-email").hidden = modeAuth !== "inscription";
  $("#champ-naissance").hidden = modeAuth !== "inscription";
  $("#btn-oublie").hidden = modeAuth === "inscription";
  $("#auth-bouton").textContent = modeAuth === "inscription" ? t("auth.creer") : t("auth.se_connecter");
});
// Le mot de passe oublié : un lien par courriel (ou dans le journal du serveur), puis
// un nouveau mot de passe choisi depuis ce lien (?mdp=<jeton>).
$("#btn-oublie").addEventListener("click", async () => {
  const qui = prompt(t("auth.oublie_qui"), $("#form-auth").pseudo.value || "");
  if (!qui) return;
  try { await api("/mdp/oublie", {qui}); toast(t("auth.oublie_envoye")); } catch (e) { toast(e.message); }
});
async function remiseDepuisLien() {
  const jeton = new URLSearchParams(location.search).get("mdp");
  if (!jeton) return;
  const mdp = prompt(t("auth.nouveau_mdp"));
  if (!mdp) return;
  try {
    const r = await api("/mdp/remettre", {jeton, mot_de_passe: mdp});
    history.replaceState(null, "", location.pathname);
    connecte({connecte: true, ...r}); toast(t("auth.mdp_change"));
    await montrer(idsEffectif().length ? "equipe" : "packs");
  } catch (e) { toast(e.message); }
}
$("#form-auth").addEventListener("submit", async e => {
  e.preventDefault(); $("#auth-erreur").textContent = "";
  const fd = new FormData(e.target);
  try {
    const r = await api("/" + modeAuth, {pseudo: fd.get("pseudo"), mot_de_passe: fd.get("mot_de_passe"), equipe: fd.get("equipe") || null,
                                           email: fd.get("email") || null, naissance: fd.get("naissance") || null});
    connecte({connecte: true, ...r});
    await montrer(idsEffectif().length ? "equipe" : "packs");
    if (modeAuth === "inscription") toast(t("auth.bienvenue"));
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
const TIER_TXT = tableT("tier.");
const tierTxt = k => TIER_TXT[k] || k;
const PALIER_TXT = tableT("palier.");
// les chances d'un pack, telles qu'elles sont : chaque tirage est uniforme parmi les cartes du palier
function chancesTxt(p) {
  if (!p.chances) return "";
  const parts = Object.entries(p.chances).map(([pal, n]) => t("packs.chance", {palier: PALIER_TXT[pal] || pal, n}));
  return parts.join(" · ");
}
const resteTxt = fin => { const ms = new Date(fin) - Date.now(); if (ms <= 0) return t("vente.terminee"); const h = Math.floor(ms / 3.6e6), m = Math.floor(ms % 3.6e6 / 6e4); return h ? `${h} h ${String(m).padStart(2, "0")}` : `${m} min`; };
async function rendrePacks() {
  G.packs = await api("/packs");
  const P = $("#packs-liste"); P.replaceChildren();
  $("#packs-info").textContent = (G.packs.plafond >= 1e6 ? t("packs.sans_plafond") : t("packs.plafond", {n: G.packs.plafond})) + " " + t("packs.reserve", {reserve: G.packs.reserve_max == null ? t("packs.illimitee") : t("packs.n_cartes", {n: G.packs.reserve_max}), rachat: Math.round(G.packs.rachat * 100)});
  const offerts = Object.entries(G.packs.offerts || {}).filter(([, n]) => n > 0);
  if (offerts.length) {
    const b = el("div", {class: "panneau offerts"}, el("h3", {class: "anton"}, t("packs.offerts")),
      el("p", {class: "compteur"}, t("packs.offerts_texte")));
    const l = el("div", {class: "offerts-liste"});
    for (const [type, n] of offerts) {
      const p = G.packs.catalogue.find(x => x.type === type && !x.fam);
      l.append(el("div", {class: "offert " + type},
        el("b", {class: "anton"}, `${n} × ${TIER_TXT[type]}`),
        el("span", {class: "compteur"}, p ? p.desc : ""),
        el("button", {class: "primaire", disabled: !(p && p.disponible),
          onclick: () => ouvrirPack({...(p || {type, nom: t("packs.pack") + " " + TIER_TXT[type], prix: 0}), offert: true})},
          t("packs.ouvrir_gratuit"))));
    }
    b.append(l); P.append(b);
  }
  for (const p of G.packs.catalogue) {
    const k = el("div", {class: "pack " + p.type + (p.disponible ? "" : " epuise")},
      el("div", {class: "pack-tier etiq"}, TIER_TXT[p.type] + " · " + (p.fam ? t("filtre." + {GK: "gardiens", DEF: "defenseurs", MID: "milieux", FWD: "attaquants"}[p.fam]) : t("packs.mixte"))),
      el("div", {class: "pack-visuel"}, el("div", {class: "pack-carte a"}), el("div", {class: "pack-carte b"}), el("div", {class: "pack-carte c"})),
      el("div", {class: "pack-desc"}, p.desc),
      el("div", {class: "pack-chances compteur", title: t("packs.doublon_titre")}, chancesTxt(p)),
      el("div", {class: "pack-prix anton"}, fM(p.prix)),
      el("button", {class: "primaire", disabled: !p.disponible || p.prix > G.equipe.budget + 1e-9, onclick: () => ouvrirPack(p), title: p.disponible ? "" : t("packs.epuise_titre")}, p.disponible ? t("packs.ouvrir") : t("packs.epuise")));
    P.append(k);
  }
}
async function ouvrirPack(p) {
  let r; try { r = await api("/packs/ouvrir", {type: p.type, fam: p.offert ? null : p.fam, offert: !!p.offert}); } catch (e) { toast(e.message); return; }
  await rafraichir(false);
  const dlg = $("#fiche"); dlg.replaceChildren();
  const box = el("div", {class: "fiche ouverture"}, el("h3", {class: "anton"}, `${p.nom}`), el("p", {class: "compteur"}, `${p.offert ? t("packs.offert") : fM(p.prix)} · ${t("packs.reste", {budget: fM(r.budget)})}`));
  const grille = el("div", {class: "cartes-grille ouverture-grille"});
  r.cartes.forEach((x, i) => { const c = x.carte; const k = carteMarche(c, {vitrine: true, largeur: 240}); k.classList.add("revele"); k.style.animationDelay = (i * 0.25) + "s";
    k.append(el("div", {class: "cj-cote"}, `${t("carte.cote")} ${fM(x.cote)} · n° ${x.numero}`));
    if (x.doublon) k.append(el("div", {class: "cj-doublon"}, t("packs.doublon_vendre", {banque: fM(x.banque)})));
    grille.append(k); });
  const nd = r.cartes.filter(x => x.doublon).length;
  if (nd) box.append(el("p", {class: "compteur"}, t("packs.doublons", {n: nd})));
  box.append(grille, el("div", {class: "actions"}, el("button", {onclick: () => { dlg.close(); montrer("equipe"); }}, t("packs.gerer_club")), el("button", {class: "primaire", onclick: () => { dlg.close(); rendrePacks(); }}, t("packs.encore"))));
  dlg.append(box); dlg.showModal();
}
async function rendreEncheres(filtrePid = null) {
  const d = await api("/marche"); G.ventes = d.ventes;
  const q = norm($("#e-nom").value), fam = $("#e-fam").value, miennes = $("#e-miennes").checked, tri = $("#e-tri").value;
  let rows = d.ventes.filter(v => v.carte && (!filtrePid || v.player_id === filtrePid) && (!fam || v.carte.fam === fam) && (!miennes || v.mienne || v.je_mene) && (!q || norm(v.carte.nom).includes(q) || norm(v.carte.club).includes(q)));
  const cle = {fin: v => new Date(v.fin) - 0, prix: v => -(v.meilleure_offre ?? v.prix_depart), ovr: v => -v.carte.ovr, cote: v => -(v.cote || 0)}[tri];
  rows.sort((a, b) => cle(a) - cle(b));
  $("#encheres-compteur").textContent = t("vente.en_cours_n", {n: rows.length});
  const L = $("#encheres-liste"); L.replaceChildren();
  if (!rows.length) L.append(el("p", {class: "info"}, t("vente.aucune_texte")));
  for (const v of rows) L.append(ligneVente(v));
}
function ligneVente(v) {
  const c = v.carte; const cour = v.meilleure_offre ?? null;
  const l = el("div", {class: "vente" + (v.mienne ? " mienne" : "") + (v.je_mene ? " mene" : "")});
  l.style.setProperty("--clubc", c.couleur);
  const k = carteMarche(c, {vitrine: true}); k.classList.add("petite");
  const infos = el("div", {class: "vente-infos"},
    el("div", {class: "etiq"}, `${t("vente.vendeur")} ${v.vendeur} · ${t("carte.exemplaire")} n° ${v.numero} · ${t("carte.cote")} ${fM(v.cote)}`),
    el("div", {class: "vente-prix"}, el("div", {}, el("span", {class: "etiq"}, cour ? t("vente.meilleure_offre") : t("vente.mise_a_prix")), el("b", {class: "anton"}, fM(cour ?? v.prix_depart))),
      v.prix_immediat ? el("div", {}, el("span", {class: "etiq"}, t("vente.achat_immediat")), el("b", {class: "anton"}, fM(v.prix_immediat))) : null,
      el("div", {}, el("span", {class: "etiq"}, t("vente.fin")), el("b", {class: "anton"}, resteTxt(v.fin)))),
    v.je_mene ? el("div", {class: "compteur", style: "color:var(--vert)"}, t("vente.tu_menes")) : null);
  const acts = el("div", {class: "vente-actions"});
  if (v.mienne) {
    acts.append(el("span", {class: "compteur"}, cour ? t("vente.offre_faite") : t("vente.ta_vente")),
      el("button", {disabled: !!cour, onclick: async () => { try { await api("/marche/annuler", {enchere_id: v.enchere_id}); toast(t("vente.annulee")); rendreEncheres(); } catch (e) { toast(e.message); } }}, t("vente.retirer")));
  } else {
    const mini = cour ? Math.round(cour * 1.05 * 100 + 0.5) / 100 : v.prix_depart;
    const inp = el("input", {type: "number", step: "0.1", min: String(mini), value: String(mini), style: "width:110px"});
    acts.append(inp, el("button", {class: "achat", onclick: async () => { try { const r = await api("/marche/encherir", {enchere_id: v.enchere_id, montant: +inp.value}); toast(t("vente.offre_placee", {montant: fM(r.montant)})); await rafraichir(false); rendreEncheres(); } catch (e) { toast(e.message); } }}, t("vente.encherir")));
    if (v.prix_immediat) acts.append(el("button", {class: "achat primaire", onclick: async () => { try { const r = await api("/marche/acheter", {enchere_id: v.enchere_id}); toast(t("vente.achete", {nom: c.nom, prix: fM(r.prix)})); await rafraichir(false); rendreEncheres(); } catch (e) { toast(e.message); } }}, t("vente.acheter") + " " + fM(v.prix_immediat)));
  }
  l.append(k, infos, acts);
  return l;
}
function dialogueVente(x) {
  const c = x.carte; const dlg = $("#fiche"); dlg.replaceChildren();
  const cote = x.cote || 1;
  const dep = el("input", {type: "number", step: "0.1", min: "0.1", value: String(Math.round(cote * 0.8 * 10) / 10)});
  const imm = el("input", {type: "number", step: "0.1", min: "0.1", value: String(Math.round(cote * 1.2 * 10) / 10)});
  const dur = el("select", {}, ...(G.packs?.durees || [6, 12, 24, 48]).map(h => el("option", {value: String(h), selected: h === 24 ? "selected" : null}, t("vente.heures", {n: h}))));
  const box = el("div", {class: "fiche"}, el("h3", {class: "anton"}, t("vente.mettre_en_vente")), el("p", {class: "compteur"}, `${c.nom} · ${t("carte.exemplaire")} n° ${x.numero} · ${t("carte.cote")} ${fM(cote)} · ${t("carte.achete")} ${fM(x.prix_achat)}`),
    el("form", {class: "form-vente", onsubmit: async e => { e.preventDefault(); try { await api("/marche/vendre", {exemplaire_id: x.exemplaire_id, prix_depart: +dep.value, prix_immediat: imm.value ? +imm.value : null, duree_h: +dur.value}); toast(t("vente.mise")); dlg.close(); await rafraichir(false); rendreEquipe(); } catch (err) { toast(err.message); } }},
      el("label", {}, t("vente.mise_a_prix_m"), dep), el("label", {}, t("vente.achat_immediat_m"), imm), el("label", {}, t("vente.duree"), dur),
      el("p", {class: "compteur"}, t("vente.commission", {pct: Math.round((G.packs?.commission ?? 0.05) * 100)})),
      el("div", {class: "actions"}, el("button", {type: "button", class: "discret", onclick: () => dlg.close()}, t("annuler")), el("button", {type: "submit", class: "primaire"}, t("vente.mettre_en_vente")))));
  dlg.append(box); dlg.showModal();
}
async function actionClub(chemin, corps, msg) {
  try { await api(chemin, corps); if (msg) toast(msg); await rafraichir(false); if (G.ecran === "equipe") rendreEquipe(); if (G.ecran === "packs") rendrePacks(); } catch (e) { toast(e.message); }
}
function rendreMarche() {
  // les ligues du filtre viennent des cartes elles-mêmes (le monde fictif les renomme)
  const sl = $("#f-ligue");
  if (sl && sl.options.length <= 1) {
    const ligues = [...new Set(G.cartes.map(c => c.ligue).filter(Boolean))].sort();
    for (const l of ligues) sl.append(el("option", {value: l}, l));
  }
  const mf = $("#marche-ferme"); mf.hidden = !!G.saison.courante;
  mf.textContent = t("marche.ferme");
  const q = norm($("#f-nom").value), fam = $("#f-fam").value, ligue = $("#f-ligue").value, tri = $("#f-tri").value;
  const abord = $("#f-abord").checked, miens = $("#f-miens").checked;
  let rows = G.cartes.filter(c => {
    if (fam && c.fam !== fam) return false; if (ligue && c.ligue !== ligue) return false;
    if (abord && !ventesDe(c.id).length) return false; if (miens && !G.equipe.effectif[c.id]) return false;
    if (q && !norm(c.nom).includes(q) && !norm(c.club).includes(q)) return false; return true;
  });
  const cle = {ovr: c => -c.ovr, prix: c => -c.prix, rapport: c => -(c.ovr - 40) / Math.max(c.prix, 0.1), forme: c => -formeMoy(c), age: c => c.age || 99, part: c => -c.part, nom: c => 0}[tri];
  rows.sort((a, b) => cle(a) - cle(b) || a.nom.localeCompare(b.nom));
  $("#marche-compteur").textContent = t("marche.n_cartes", {n: rows.length});
  // dix-huit cartes, réparties comme le manager veut : on compte, on ne plafonne plus
  const ME = $("#marche-effectif"); ME.replaceChildren(el("span", {class: "etiq"}, t("marche.effectif")), el("b", {class: "num"}, `${idsEffectif().length} / ${TAILLE}`),
    ...FAMS.map(f => el("span", {class: "quota"}, `${FAM_COURT[f]} `, el("b", {}, String(nbFam(f))))));
  document.querySelectorAll(".vue button").forEach(b => { if (b.dataset.vue === marcheVue) b.setAttribute("aria-current", "page"); else b.removeAttribute("aria-current"); });
  const L = $("#marche-liste"); L.replaceChildren(); L.className = marcheVue === "cartes" ? "cartes-grille" : "liste";
  for (const c of rows.slice(0, marcheLimite)) L.append(marcheVue === "cartes" ? carteMarche(c) : ligneCarte(c));
  $("#marche-plus").hidden = rows.length <= marcheLimite;
}
function boutonAchatVente(c, mien) {
  const n = ventesDe(c.id).length;
  return el("button", {class: "achat" + (n ? " primaire" : ""), disabled: !n, onclick: e => { e.stopPropagation(); if (n) allerAuxVentes(c.id); }}, n ? t("vente.n", {n}) : t("vente.aucune"));
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
    el("div", {class: "cj-pos"}, el("span", {class: "fam " + c.fam}, POSTE_ABBR[c.poste] || FAM_COURT[c.fam])),
    c.age ? el("div", {class: "cj-age"}, ageTxt(c)) : null,
    c.pied ? el("div", {class: "cj-pieds"}, piedsDe(c, true)) : null,
    el("img", {class: "cj-logo", src: `/images/logos/${c.team_id}.png`, alt: "", loading: "lazy", onerror: e => e.target.remove()}),
    c.pays ? el("div", {class: "cj-drapeau", title: c.pays}, drapeau(c.pays)) : null,
    c.numero ? el("div", {class: "cj-num"}, "#" + c.numero) : null,
    recrue(c) ? el("div", {class: "cj-recrue", title: t("carte.recrue_titre", {n: c.arrivee})}, t("carte.nouveau")) : null,
    vignetteDe(c));
  const corps = el("div", {class: "cj-corps"},
    el("div", {class: "nom", title: c.nom}, c.nom),
    el("div", {class: "sous"}, `${codesDe(c)} · ${c.club}`),
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
// D'où vient la carte et où elle en est : la note initiale de la saison
// (ovr_base, celle de l'amorce) et une flèche — verte si elle est montée
// depuis, rouge si elle a baissé, un trait bleu si elle n'a pas bougé.
// La forme : trois bons vrais matchs d'affilée, +1 temporaire (et +2 sur chaque attribut en match) ; trois mauvais, -1.
function formeBadge(c) {
  if (!c || !c.forme) return null;
  return el("span", {class: "forme " + (c.forme > 0 ? "bonne" : "mauvaise"),
    title: c.forme > 0 ? t("carte.forme_titre") : t("carte.meforme_titre")},
    c.forme > 0 ? t("carte.forme") : t("carte.meforme"));
}
// L'état d'une carte entre deux matchs : suspendue, blessée (en matchs), ou la fatigue reportée.
function etatBadge(x) {
  const e = x && x.etat; if (!e) return null;
  if (e.suspension > 0) return el("span", {class: "etat suspendu", title: t("carte.suspendu_titre")}, t("carte.suspendu", {n: e.suspension}));
  if (e.blessure > 0) return el("span", {class: "etat blesse", title: t("carte.blesse_titre")}, t("carte.blesse", {n: e.blessure}));
  if (e.fatigue > 0.04) return el("span", {class: "etat fatigue", title: t("carte.fatigue_titre")}, t("carte.jus", {pct: Math.round(100 - e.fatigue * 100)}));
  return null;
}
function tendance(c, compact = false) {
  if (c.ovr_base == null || c.ovr == null) return null;
  const d = c.ovr - c.ovr_base;
  const cls = d > 0 ? "plus" : d < 0 ? "moins" : "egal";
  const fleche = d > 0 ? "▲" : d < 0 ? "▼" : "—";
  return el("span", {class: "tend " + cls,
    title: t("carte.tendance_titre", {base: c.ovr_base, ovr: c.ovr}) + (d ? ` (${d > 0 ? "+" : ""}${d})` : t("carte.inchangee"))},
    fleche + (compact ? "" : " " + c.ovr_base));
}

// The drawn card (moteur/carte_design), the one the game trades, with the
// light HTML box as a fallback while it loads or if the render is missing.
function carteDessinee(c, largeur = 170, secours = null) {
  const d = el("div", {class: "dessin"});
  const t = tendance(c);                      // sous l'OVR : d'où elle vient
  if (t) d.append(t);
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
    el("div", {class: "qui"}, el("div", {class: "nom"}, c.nom), el("div", {class: "sous"}, `${codesDe(c)} · ${c.club}${c.age ? " · " + ageTxt(c) : ""}${c.part > 0 ? " · " + t("carte.part_equipes", {pct: Math.round(c.part * 100)}) : ""}`)),
    barresForme(c),
    el("div", {class: "ovr num" + (c.ovr >= 80 ? " haut" : "")}, String(c.ovr), tendance(c)),
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
function scorePoste(attributs, poste) {
  const poids = POIDS_POSTES[posteBase(poste)];
  if (!poids || !attributs) return null;
  return Object.entries(poids).reduce((s, [ax, w]) => s + w * (attributs[ax] ?? 40), 0);
}
function malusDe(id, poste) {
  const c = carte(id); if (!c || !poste) return 0;
  const ligne = MALUS_POSTES[poste];
  const tenus = (c.postes && c.postes.length) ? c.postes : [c.poste];
  const d = !ligne ? (tenus.includes(poste) ? 0 : 8) : Math.min(...tenus.map(p => ligne[p] ?? 8));
  if (d === 0 || d >= MALUS_GK || !c.attributs) return d;
  const a = scorePoste(c.attributs, poste), b = scorePoste(c.attributs, c.poste);
  const ecart = a === null || b === null ? 0 : a - b;
  return Math.max(-BONUS_POSTE_MAX, Math.min(MALUS_GK, Math.round(PART_DISTANCE * d - PART_ECART * ecart)));
}
function ovrAu(id, poste) { return Math.max(40, Math.min(99, ovr(id) - malusDe(id, poste))); }
function aLePoste(id, poste) { return malusDe(id, poste) === 0; }
function horsPoste(id, poste) { return malusDe(id, poste) > 0; }
// loin de chez lui : un attaquant central en défense, quelqu'un dans les buts
function loinDuPoste(id, poste) { return malusDe(id, poste) >= 14; }
// Les codes de poste, comme FIFA les écrit (scoring.CODE_POSTE, servi par
// le serveur) : GB, DC, DG, DD, MDC, MC, MOC, AG, AD, BU.
let POSTE_ABBR = {"Gardien": "GB", "Defenseur central": "DC", "Lateral": "DG/DD",
  "Lateral gauche": "DG", "Lateral droit": "DD",
  "Milieu defensif": "MDC", "Milieu relayeur": "MC", "Milieu offensif": "MOC",
  "Milieu de couloir": "MG/MD", "Milieu gauche": "MG", "Milieu droit": "MD",
  "Ailier": "AG/AD", "Ailier droit": "AD", "Ailier gauche": "AG", "Buteur": "BU"};
// les postes tenus d'une carte, en codes : « AD / BU »
const codesDe = c => ((c.postes && c.postes.length) ? c.postes : [c.poste]).map(p => POSTE_ABBR[p] || p).join(" / ");
// les postes qu'on peut filtrer, en codes
// (les codes sont ceux des cartes dessinées, le libellé vient du dictionnaire : code.<code>)
const FILTRES_POSTE = ["GB", "DC", "DG", "DD", "MDC", "MC", "MOC", "MG", "MD", "AG", "AD", "BU"];
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
  const sel = $("#formation"); if (!sel.options.length) for (const f of Object.keys(FORMATIONS)) sel.append(el("option", {value: f}, nomFormation(f)));
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
      t("compo.manque", {n: trous})));
  }
  // Out of position is allowed, and it costs: say who, and how much the
  // eleven is worth where it stands.
  const postesC = slotsPostes(C.formation);
  const dehors = C.slots.map((id, s) => id === null ? 0 : malusDe(id, postesC[s]));
  const nDehors = dehors.filter(x => x > 0).length, perdu = dehors.filter(x => x > 0).reduce((a, b) => a + b, 0);
  const nBonus = dehors.filter(x => x < 0).length;
  if (nDehors) A.append(el("div", {class: "info"}, t("compo.hors_poste", {n: nDehors, perdu})));
  if (nBonus) A.append(el("div", {class: "info"}, t("compo.bonus", {n: nBonus})));
  const moyenne = C.slots.every(x => x !== null)
    ? C.slots.reduce((a, id, s) => a + ovrAu(id, postesC[s]), 0) / 11 : null;
  if (moyenne !== null) A.append(el("div", {class: "compteur"}, t("compo.moyenne", {ovr: moyenne.toFixed(1)})));
  const j = G.saison.courante;
  const etat = $("#compo-etat"); etat.replaceChildren();
  if (!j) etat.append(t("compo.saison_terminee"));
  else if (j.verrouillee) etat.append(el("b", {}, t("compo.verrouillee", {n: j.numero})), " " + t("compo.verrouillee_suite", {envoyee: G.equipe.composition ? t("oui") : t("compo.non_score_nul")}));
  else etat.append(t("compo.ouverte", {n: j.numero, du: dateFr(j.du), au: dateFr(j.au), cloture: new Date(j.cloture).toLocaleString(LOCALE)}) + " ", G.equipe.composition ? el("b", {}, t("compo.envoyee_le", {date: new Date(G.equipe.composition.soumise_le).toLocaleString(LOCALE)})) : el("b", {class: "rouge"}, t("compo.aucune_envoyee")));
  $("#btn-envoyer").disabled = !ok || !j || j.verrouillee;
  const B = $("#banc"); B.replaceChildren();
  zoneDepot(B, {type: "banc"});
  // la recherche filtre le banc et signale sur le terrain
  const q = normEq();
  C.banc.forEach((i, r) => { if (!q || cherche(i, q)) B.append(ligneBanc(i, r)); });
  if (q) T.querySelectorAll(".slot").forEach(n => n.classList.toggle("trouve", n._slot !== undefined && C.slots[n._slot] !== null && cherche(C.slots[n._slot], q)));
  if (q && !C.banc.some(i => cherche(i, q)) && !C.slots.some(i => i !== null && cherche(i, q)))
    B.append(el("p", {class: "compteur"}, t("compo.personne", {nom: $("#eq-nom").value.trim()})));
  if (!C.banc.length) B.append(el("p", {class: "compteur"}, t("compo.banc_vide", {n: BANC_MAX})));
  // Un banc court n'est pas un bug de l'écran : c'est un effectif court.
  // Le dire, plutôt que de laisser croire à un banc de trois imposé.
  else if (C.banc.length < BANC_MAX) {
    const manque = 11 + BANC_MAX - idsEffectif().length;
    B.append(el("div", {class: "avert"},
      t("compo.banc_court", {banc: C.banc.length, max: BANC_MAX, effectif: idsEffectif().length, requis: 11 + BANC_MAX})
      + (manque > 0 ? " " + t("compo.banc_manque", {n: manque}) : ".")));
  }
  ecrireBrouillon();
  rendreTactiqueClub();
  rendreClub();
}
// La tactique de départ, réglée là où on règle la composition.  Elle est
// ENREGISTRÉE dès qu'on y touche : ce n'est pas une soumission de journée,
// elle n'est jamais verrouillée, et elle sert à tous les matchs.
let TAC_ENREG = null;

// Le maillot du club : un aperçu (une chemise en SVG au motif choisi) et
// trois réglages, enregistrés dès qu'on les touche.
const MOTIFS_MAILLOT = ["uni", "bande", "rayures", "cercle", "moitie", "echarpe"];
function chemiseSVG(m, taille = 96) {
  const id = "m" + Math.random().toString(36).slice(2, 8);
  const corps = "M20 14 L36 6 Q48 14 60 6 L76 14 L92 30 L78 40 L74 34 L74 90 L22 90 L22 34 L18 40 L4 30 Z";
  let motif = "";
  if (m.motif === "bande") motif = `<rect x="38" y="6" width="20" height="84" fill="${m.second}"/>`;
  else if (m.motif === "rayures") motif = [28, 44, 60].map(x => `<rect x="${x}" y="6" width="8" height="84" fill="${m.second}"/>`).join("");
  else if (m.motif === "cercle") motif = [30, 50, 70].map(y => `<rect x="4" y="${y}" width="88" height="8" fill="${m.second}"/>`).join("");
  else if (m.motif === "moitie") motif = `<rect x="48" y="6" width="44" height="84" fill="${m.second}"/>`;
  else if (m.motif === "echarpe") motif = `<polygon points="4,30 20,14 92,74 92,90 78,90" fill="${m.second}"/>`;
  return `<svg viewBox="0 0 96 96" width="${taille}" height="${taille}"><defs><clipPath id="${id}"><path d="${corps}"/></clipPath></defs>
    <path d="${corps}" fill="${m.base}"/><g clip-path="url(#${id})">${motif}</g>
    <path d="${corps}" fill="none" stroke="rgba(0,0,0,.45)" stroke-width="2"/><path d="M36 6 Q48 18 60 6" fill="none" stroke="rgba(0,0,0,.35)" stroke-width="2"/></svg>`;
}
let MAILLOT_ENREG = null;
function rendreMaillot() {
  const box = $("#maillot-club"); if (!box) return;
  const m = Object.assign({base: "#1f6fd1", second: "#ffffff", motif: "uni"}, G.equipe?.maillot || {});
  const apercu = el("div", {class: "apercu"}); apercu.innerHTML = chemiseSVG(m);
  const maj = () => {
    apercu.innerHTML = chemiseSVG(m);
    clearTimeout(MAILLOT_ENREG);
    MAILLOT_ENREG = setTimeout(async () => {
      try { const r = await api("/equipe/maillot", m); if (G.equipe) G.equipe.maillot = r.maillot; $("#maillot-etat").textContent = t("enregistre"); }
      catch (e) { $("#maillot-etat").textContent = e.message; }
    }, 400);
  };
  const cBase = el("input", {type: "color", value: m.base, oninput: e => { m.base = e.target.value; maj(); }});
  const cSecond = el("input", {type: "color", value: m.second, oninput: e => { m.second = e.target.value; maj(); }});
  const sel = el("select", {onchange: e => { m.motif = e.target.value; maj(); }});
  for (const k of MOTIFS_MAILLOT) sel.append(el("option", {value: k, selected: k === m.motif ? "selected" : null}, t("maillot." + k)));
  box.replaceChildren(apercu, el("div", {class: "reglages"},
    el("label", {}, t("maillot.couleur") + " ", cBase), el("label", {}, t("maillot.seconde") + " ", cSecond), el("label", {}, t("maillot.motif") + " ", sel)));
}

// Un seul endroit qui écrit la tactique du club, appelé depuis l'écran
// Équipe comme depuis le lobby.  Retardé d'un instant : cliquer trois
// réglages d'affilée ne fait pas trois écritures.
function enregistrerTactique(etat) {
  clearTimeout(TAC_ENREG);
  TAC_ENREG = setTimeout(async () => {
    try {
      const r = await api("/equipe/tactique", {tactique: LOBBY.tac});
      if (G.equipe) G.equipe.tactique = r.tactique;
      if (etat) etat.textContent = t("enregistree");
    } catch (e) { if (etat) etat.textContent = e.message; }
  }, 350);
}

function rendreTactiqueClub() {
  const boite = $("#tac-club");
  if (!boite) return;
  rendreMaillot();
  boite.replaceChildren();
  const etat = $("#tac-etat");
  const enregistrer = () => {
    rendreTactiqueClub();                       // les boutons se rallument tout de suite
    enregistrerTactique(etat);
  };
  boite.append(selecteurTactique(LOBBY.tac, enregistrer));
  boite.append(bilanAise());
  boite.append(depliant("equipe", t("consignes.titre"),
    el("p", {class: "compteur"}, t("consignes.texte_equipe")),
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
  b.append(el("div", {class: "etiq"}, t("aise.titre")));
  b.append(el("div", {class: "bilan-chiffre " + (moyen > 0.5 ? "bon" : moyen < -0.5 ? "mauvais" : "")},
    (moyen > 0 ? "+" : "") + moyen.toFixed(1) + " %",
    el("span", {class: "compteur"}, " " + t("aise.moyenne"))));
  const ligne = (titre, liste, classe) => {
    if (!liste.length) return null;
    return el("div", {class: "bilan-ligne " + classe},
      el("span", {class: "t"}, titre),
      el("span", {}, liste.slice(0, 4).map(g =>
        `${g.nom.split(" ").slice(-1)[0]} ${pct(g.a) > 0 ? "+" : ""}${pct(g.a).toFixed(0)} %`).join(" · ")
        + (liste.length > 4 ? ` (+${liste.length - 4})` : "")));
  };
  for (const l of [ligne(t("aise.sert"), servis, "bon"), ligne(t("aise.dessert"), desservis, "mauvais")])
    if (l) b.append(l);
  if (!servis.length && !desservis.length)
    b.append(el("p", {class: "compteur"}, t("aise.indifferent")));
  return b;
}

async function rendreClub() {
  const d = await api("/club"); G.club = d.cartes;
  const R = $("#club-liste"); R.replaceChildren();
  // les filtres : le nom (le champ au-dessus du banc), le poste tenu, le tri
  const q = normEq();
  const selPoste = $("#club-poste");
  if (selPoste && selPoste.options.length <= 1) {
    for (const code of FILTRES_POSTE) selPoste.append(el("option", {value: code}, code + " · " + t("code." + code)));
  }
  const codeVoulu = selPoste ? selPoste.value : "";
  const tri = $("#club-tri") ? $("#club-tri").value : "ovr";
  const tient = (c, code) => ((c.postes && c.postes.length) ? c.postes : [c.poste]).some(p => (POSTE_ABBR[p] || "").split("/").includes(code));
  const garde = x => (!q || norm(x.carte.nom).includes(q) || norm(x.carte.club || "").includes(q)) && (!codeVoulu || tient(x.carte, codeVoulu));
  const cle = {ovr: x => -x.carte.ovr, tendance: x => -(x.carte.ovr - (x.carte.ovr_base ?? x.carte.ovr)), cote: x => -(x.cote || 0),
               achat: x => -x.prix_achat, plus: x => -((x.cote || 0) - x.prix_achat), nom: x => 0}[tri] || (x => -x.carte.ovr);
  const ordre = (a, b) => cle(a) - cle(b) || a.carte.nom.localeCompare(b.carte.nom);
  const eff = d.cartes.filter(x => x.dans_effectif && garde(x)).sort(ordre), res = d.cartes.filter(x => !x.dans_effectif && garde(x)).sort(ordre);
  $("#club-compteur").textContent = `${eff.length} / ${d.effectif_max} ${t("club.dans_effectif")} · ${res.length}${d.reserve_max == null ? "" : " / " + d.reserve_max} ${t("club.en_reserve")}`;
  const ligne = x => {
    const c = x.carte; const l = el("div", {class: "ligne club-ligne" + (x.enchere_id ? " en-vente" : "")}); l.style.setProperty("--clubc", c.couleur);
    const delta = (x.cote || 0) - x.prix_achat;
    l.append(carteDessinee(c, 120), el("div", {class: "qui", tabindex: "0", onclick: () => ouvrirFiche(c.id)}, el("div", {class: "nom"}, c.nom, el("span", {class: "compteur"}, ` n° ${x.numero}`)), el("div", {class: "sous"}, el("b", {}, codesDe(c)), ` · ${c.club} · ${t("carte.achete")} ${fM(x.prix_achat)} · ${t("carte.cote")} ${fM(x.cote)} `, el("span", {class: "delta " + (delta >= 0 ? "plus" : "moins")}, fM(delta, true)))),
      el("span", {class: "fam " + c.fam}, POSTE_ABBR[c.poste] || FAM_COURT[c.fam]), el("div", {class: "ovr num" + (c.ovr >= 80 ? " haut" : "")}, String(c.ovr), tendance(c), formeBadge(c), etatBadge(x)));
    const acts = el("div", {class: "club-actions"});
    if (x.enchere_id) acts.append(el("span", {class: "compteur"}, t("marche.en_vente")), el("button", {onclick: () => montrer("encheres")}, t("club.voir")));
    else {
      if (x.doublon) acts.append(el("span", {class: "doublon", title: t("club.doublon_titre")}, t("club.doublon")));
      else acts.append(x.dans_effectif
        ? el("button", {title: t("club.mettre_reserve"), onclick: () => actionClub("/club/aligner", {exemplaire_id: x.exemplaire_id, dans_effectif: false}, t("club.en_reserve_toast", {nom: c.nom}))}, t("club.reserve"))
        : el("button", {class: "primaire", title: t("club.aligner_titre"), disabled: !G.equipe.marche_ouvert, onclick: () => actionClub("/club/aligner", {exemplaire_id: x.exemplaire_id, dans_effectif: true}, t("club.dans_effectif_toast", {nom: c.nom}))}, t("club.aligner")));
      const banque = fM((G.packs?.rachat ?? 0.25) * (x.cote || 0));
      acts.append(el("button", {class: "vente", onclick: () => dialogueVente(x)}, t("club.vendre")),
        el("button", {class: "discret", title: t("club.banque_titre", {montant: banque}), onclick: () => { if (confirm(t("club.banque_confirmer", {nom: c.nom, montant: banque}))) actionClub("/club/banque", {exemplaire_id: x.exemplaire_id}, t("club.vendu_banque")); }}, t("club.banque")));
    }
    l.append(acts); return l;
  };
  R.append(el("div", {class: "etiq"}, t("marche.effectif")), ...(eff.length ? eff.map(ligne) : [el("p", {class: "compteur"}, t("club.personne"))]));
  R.append(el("div", {class: "etiq", style: "margin-top:12px"}, t("club.reserve")), ...(res.length ? res.map(ligne) : [el("p", {class: "compteur"}, t("club.reserve_vide"))]));
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
  else if (malus < 0) classes.push("bonus");
  const nomPoste = POSTE_COURT[poste] || poste;
  const titre = i === null ? t("slot.vide", {poste: nomPoste.toLowerCase()})
    : malus > 0
      ? t("slot.loin", {nom: carte(i).nom, poste: nomPoste.toLowerCase(), tenus: codesDe(carte(i)), malus, ovr: ovrAu(i, poste)})
      : malus < 0
      ? t("slot.bonus", {nom: carte(i).nom, poste: nomPoste.toLowerCase(), bonus: -malus, ovr: ovrAu(i, poste)})
      : t("slot.ok", {nom: carte(i).nom, poste: nomPoste});
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
  d.append(el("div", {class: "slot-poste" + (malus >= 14 ? " loin" : malus > 0 ? " dephase" : malus < 0 ? " bonus" : "")},
    (POSTE_ABBR[poste] || fam) + (malus !== 0 ? ` · ${ovrAu(i, poste)}` : "")));
  if (C.cap === i) d.append(el("div", {class: "cap"}, "C"));
  d.append(el("button", {class: "slot-menu", title: t("slot.options"), onclick: e => { e.stopPropagation(); PRISE = null; menuSlot(s); }}, "···"));
  return d;
}
function menuSlot(s) {
  const i = C.slots[s]; const poste = slotsPostes(C.formation)[s];
  const fam = FAM_POSTE[poste] || "MID"; const dlg = $("#fiche"); dlg.replaceChildren();
  const c = carte(i);
  const box = el("div", {class: "fiche"}, el("h3", {class: "anton"}, c.nom),
    el("p", {class: "compteur"}, `${POSTE_COURT[poste] || poste} · OVR ${ovr(i)}`
      + (malusDe(i, poste) !== 0 ? ` (${t("slot.a_ce_poste", {ovr: ovrAu(i, poste)})})` : "") + ` · ${t("slot.a_tenu", {codes: codesDe(c)})}`),
    malusDe(i, poste) > 0 ? el("div", {class: "avert"}, t("slot.hors_poste", {malus: malusDe(i, poste)}))
    : malusDe(i, poste) < 0 ? el("div", {class: "info"}, t("slot.mieux_ici", {bonus: -malusDe(i, poste)})) : null);
  const acts = el("div", {class: "actions", style: "justify-content:flex-start"});
  acts.append(el("button", {class: "primaire", onclick: () => { C.cap = i; dlg.close(); rendreEquipe(false); }}, t("slot.capitaine")));
  // the bench, those who really hold the position first
  const remplacants = C.banc.slice().sort((x, y) => ovrAu(y, poste) - ovrAu(x, poste));
  for (const b of remplacants) acts.append(el("button", {onclick: () => { C.banc = C.banc.map(x => x === b ? i : x); C.slots[s] = b; if (C.cap === i) C.cap = b; dlg.close(); rendreEquipe(false); }},
    t("slot.remplacer_par", {nom: carte(b).nom, ovr: ovrAu(b, poste)}) + (malusDe(b, poste) > 0 ? ` — ${t("slot.hors_poste_court", {malus: malusDe(b, poste)})}` : malusDe(b, poste) < 0 ? ` — ${t("slot.bonus_court", {bonus: -malusDe(b, poste)})}` : "")));
  acts.append(el("button", {onclick: () => { C.slots[s] = null; C.banc.unshift(i); if (C.cap === i) C.cap = null; dlg.close(); rendreEquipe(false); }}, t("slot.sur_le_banc")));
  acts.append(el("button", {onclick: () => { dlg.close(); ouvrirFiche(i); }}, t("voir_fiche")), el("button", {class: "discret", onclick: () => dlg.close()}, t("fermer")));
  box.append(acts); dlg.append(box); dlg.showModal();
}
function ligneBanc(i, r) {
  const c = carte(i);
  const choisi = PRISE && PRISE.type === "banc" && PRISE.i === r;
  const l = el("div", {class: "ligne" + (choisi ? " prise" : ""), tabindex: "0",
    title: t("banc.glisse", {nom: c.nom, codes: codesDe(c)}),
    onclick: () => { if (PRISE && PRISE.type === "slot") deposer(PRISE, {type: "banc"}); else prendre({type: "banc", i: r}); },
    onkeydown: e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); if (PRISE && PRISE.type === "slot") deposer(PRISE, {type: "banc"}); else prendre({type: "banc", i: r}); } }});
  l.style.setProperty("--clubc", c.couleur);
  zonePrise(l, {type: "banc", i: r});
  const ord = el("div", {class: "ordre"},
    el("button", {title: t("banc.monter"), disabled: r === 0, onclick: e => { e.stopPropagation(); [C.banc[r - 1], C.banc[r]] = [C.banc[r], C.banc[r - 1]]; rendreEquipe(false); }}, "▲"),
    el("button", {title: t("banc.descendre"), disabled: r === C.banc.length - 1, onclick: e => { e.stopPropagation(); [C.banc[r + 1], C.banc[r]] = [C.banc[r], C.banc[r + 1]]; rendreEquipe(false); }}, "▼"));
  l.append(ord, carteDessinee(c, 120), el("div", {class: "qui"}, el("div", {class: "nom"}, c.nom), el("div", {class: "sous"}, `${codesDe(c)} · ${c.club}`)),
    el("span", {class: "fams"}, el("span", {class: "fam " + c.fam}, POSTE_ABBR[c.poste] || c.poste)),
    el("div", {class: "ovr num"}, String(c.ovr), tendance(c)));
  return l;
}
async function envoyer() {
  try {
    const r = await api("/equipe/composition", {formation: C.formation, titulaires: C.slots, banc: C.banc, capitaine: C.cap});
    toast(t("compo.envoyee_toast", {n: r.journee})); await rafraichir(false); rendreEquipe();
  } catch (e) { toast(e.message); }
}

// ---- lobby classé : un match joué avec les cartes -------------------------
// The sheet is recomputed server-side from the seed and the tactical
// timeline on every poll, so what we draw is never a local accumulation:
// refreshing, or coming back after a while, shows the same match.
const AXE_VALEURS = {tempo: ["possession", "equilibre", "direct"], bloc: ["haut", "median", "bas"], risque: ["offensif", "equilibre", "prudent"]};
const axeTxt = (axe, v) => t(`tac.${axe}.${v}`);

// Les consignes individuelles : ce qu'on demande à une LIGNE, dans les
// mots d'un entraîneur.  Chacune est un échange, jamais un bonus, et le
// premier choix de chaque ligne est neutre (jeu/simulation.CONSIGNES).
// (les libellés et les aides sont dans le dictionnaire : consigne.<ligne>.<valeur> et .aide)
const CONSIGNE_VALEURS = {lateraux: ["couloir", "bas", "axe"], ailiers: ["equilibre", "ligne", "interieur"],
  milieux: ["equilibre", "projection", "bas", "lateral"], attaquants: ["equilibre", "profondeur", "pivot"], relance: ["equilibre", "courte", "longue"]};

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
      if (v !== null && v !== 0) out.push({texte: existeT(`affinite.${axe}.${choix}`) ? t(`affinite.${axe}.${choix}`) : opts[choix].texte, score: v});
    }
  out.sort((a, b) => b.score - a.score);
  return {aise: out.filter(x => x.score >= AISE.seuil).slice(0, combien),
          gene: out.filter(x => x.score <= -AISE.seuil).slice(-combien).reverse()};
}

function selecteurConsignes(tac, onChange) {
  const d = el("div", {class: "tactiques consignes-jeu"});
  for (const [axe, valeurs] of Object.entries(CONSIGNE_VALEURS)) {
    const g = el("div", {class: "tac-groupe"}, el("span", {class: "tac-titre"}, t("consigne." + axe)));
    for (const v of valeurs)
      g.append(el("button", {class: "tac" + (tac[axe] === v ? " actif" : ""),
        "data-consigne": axe, "data-valeur": v, title: t(`consigne.${axe}.${v}.aide`),
        onclick: () => { tac[axe] = v; onChange(); }}, t(`consigne.${axe}.${v}`)));
    d.append(g);
  }
  return d;
}
const EVT_ICONE = {but: "⚽", arret: "🧤", occasion: "✗", tactique: "⇄", corner: "⛳", faute: "⚠",
  jaune: "🟨", rouge: "🟥", horsjeu: "🚩", changement: "🔁", blessure: "🚑", permutation: "⇅",
  formation: "⇄", penalty_manque: "✗", additionnel: "⏱"};
let LOBBY = {timer: null, vus: 0,
  tac: {tempo: "equilibre", bloc: "median", risque: "equilibre",
        lateraux: "couloir", ailiers: "equilibre", milieux: "equilibre",
        attaquants: "equilibre", relance: "equilibre"}};

function arreterLobby() {
  if (G.ecran !== "solo") arreterTerrain(true); if (LOBBY.timer) { clearInterval(LOBBY.timer); LOBBY.timer = null; } }

async function rendreLobby(donnees) {
  const d = donnees || await api(cheminSonde("/lobby"));
  LOBBY.etat = d;
  $("#lobby-info").textContent = `${t("statut.elo")} ${Math.round(d.elo)} · ${t("lobby.n_classes", {n: d.classees})}`;
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
    const g = el("div", {class: "tac-groupe"}, el("span", {class: "tac-titre"}, t("tac." + axe)));
    for (const v of AXE_VALEURS[axe]) {
      // l'axe et la valeur sont posés sur le bouton : le panneau du match
      // est réutilisé d'un sondage à l'autre et n'a plus qu'à remettre la
      // classe `actif` au bon endroit, sans reconstruire les boutons
      g.append(el("button", {class: "tac" + (tac[axe] === v ? " actif" : ""), "data-axe": axe, "data-valeur": v,
        onclick: () => { tac[axe] = v; onChange(); }}, axeTxt(axe, v)));
    }
    d.append(g);
  }
  return d;
}

// Le rythme d'un match contre la machine : six minutes pour quatre-vingt-dix
// est un résumé, douze ou dix-huit un match qu'on suit du banc.  Mémorisé.
let RYTHME = 720;
try { RYTHME = +localStorage.getItem("fl_rythme") || 720; } catch (e) {}
// Avec le moteur B, le rythme est une VITESSE du ballon vivant (les arrêts de jeu
// se sautent) : ×2, c'est le football à un rythme normal, une demi-heure réelle
// pour un match complet ; ×4 un quart d'heure ; ×8 un résumé de neuf minutes.
let VITESSE = 2;
try { VITESSE = +localStorage.getItem("fl_vitesse") || 2; } catch (e) {}
const DUREE_VITESSE = v => Math.round(29 * 2 / v);          // minutes réelles, mesurées : 52 min de ballon vivant, 77 arrêts
function moteurB() { return (G.saison?.moteur || "B") === "B"; }
function selecteurRythme(d) {
  if (moteurB()) return selecteurVitesse(d);
  const choix = (d.durees || G.saison?.durees_match || [360, 720, 1080]);
  if (!choix.includes(RYTHME)) RYTHME = choix[Math.min(1, choix.length - 1)];
  const g = el("div", {class: "tac-groupe"}, el("span", {class: "tac-titre"}, t("rythme.titre")));
  const maj = () => g.querySelectorAll("button").forEach(b => b.classList.toggle("actif", +b.dataset.d === RYTHME));
  for (const s of choix)
    g.append(el("button", {class: "tac", "data-d": String(s), title: t("rythme.minutes_reelles", {n: Math.round(s / 60)}),
      onclick: () => { RYTHME = s; try { localStorage.setItem("fl_rythme", String(s)); } catch (e) {} maj(); }},
      `${Math.round(s / 60)} min`));
  maj();
  return el("div", {class: "tactiques rythme"}, g,
    el("span", {class: "compteur"}, t("rythme.classe_six")));
}
function selecteurVitesse(d) {
  const choix = (d.vitesses || G.saison?.vitesses_match || [2, 4, 8]);
  if (!choix.includes(VITESSE)) VITESSE = choix[0];
  const g = el("div", {class: "tac-groupe"}, el("span", {class: "tac-titre"}, t("rythme.titre")));
  const maj = () => g.querySelectorAll("button").forEach(b => b.classList.toggle("actif", +b.dataset.v === VITESSE));
  for (const v of choix)
    g.append(el("button", {class: "tac", "data-v": String(v), title: t("rythme.vitesse_titre", {v, n: DUREE_VITESSE(v)}),
      onclick: () => { VITESSE = v; try { localStorage.setItem("fl_vitesse", String(v)); } catch (e) {} maj(); }},
      `×${v} · ${DUREE_VITESSE(v)} min`));
  maj();
  return el("div", {class: "tactiques rythme"}, g,
    el("span", {class: "compteur"}, t("rythme.vitesse_texte", {v: G.saison?.vitesse_match || 2})));
}

function panneauEntree(d) {
  const p = el("div", {class: "panneau"}, el("h3", {class: "anton"}, t("lobby.lance")));
  p.append(el("p", {class: "compteur"},
    moteurB() ? t("lobby.texte_b", {v: d.vitesse || 2}) : t("lobby.texte_a", {n: Math.round(d.duree / 60)})));
  const onze = C.slots.every(x => x !== null) ? C.slots.slice() : null;
  if (!onze) {
    p.append(el("div", {class: "avert"}, t("lobby.onze_incomplet")));
    return p;
  }
  const strip = el("div", {class: "onze-strip"});
  for (const i of onze) {
    const c = carte(i);
    const k = el("div", {class: "onze-carte", title: c.nom, onclick: () => ouvrirFiche(i)});
    k.style.setProperty("--clubc", c.couleur);
    k.append(carteDessinee(c, 120), el("div", {class: "n"}, c.nom.split(" ").slice(-1)[0]));
    strip.append(k);
  }
  p.append(el("div", {class: "etiq"}, t("lobby.ton_onze")), strip);
  // Retoucher la tactique ici l'enregistre aussi : c'est la MÊME que
  // celle de l'écran Équipe, il n'y en a qu'une par club.
  const maj = () => { const n = panneauEntree(d); p.replaceWith(n); enregistrerTactique(); };
  p.append(el("div", {class: "etiq"}, t("lobby.ta_tactique")));
  p.append(selecteurTactique(LOBBY.tac, maj));
  p.append(depliant("entree", t("consignes.titre"),
    el("p", {class: "compteur"}, t("consignes.texte_entree")),
    selecteurConsignes(LOBBY.tac, maj)));
  p.append(el("p", {class: "compteur"}, t("lobby.tactique_une_fois")));
  const acts = el("div", {class: "actions", style: "justify-content:flex-start"});
  p.append(selecteurRythme(d));
  acts.append(el("button", {class: "primaire", onclick: () => entrerLobby(onze, false)}, t("lobby.chercher")),
    el("button", {onclick: () => entrerLobby(onze, true)}, t("lobby.defi")));
  p.append(acts);
  p.append(el("p", {class: "compteur"}, d.attente_file ? t("lobby.file", {n: d.attente_file}) : t("lobby.file_vide")));
  return p;
}

async function entrerLobby(onze, defi) {
  try { await rendreLobby(await api("/lobby/rejoindre", {formation: C.formation, onze, banc: C.banc.slice(0, BANC_MAX), tactique: LOBBY.tac, defi, duree: defi ? RYTHME : null, vitesse: defi ? VITESSE : null})); }
  catch (e) { toast(e.message); }
}

function panneauAttente(d) {
  const p = el("div", {class: "panneau"}, el("h3", {class: "anton"}, t("lobby.attente")));
  p.append(el("p", {class: "compteur"}, t("lobby.attente_texte")),
    el("div", {class: "actions", style: "justify-content:flex-start"},
      el("button", {onclick: async () => { try { await rendreLobby(await api("/lobby/quitter", {})); } catch (e) { toast(e.message); } }}, t("lobby.quitter_file"))));
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
const ONGLETS_MATCH = ["direct", "tactique", "stats"];
let ONGLET = "direct";
const MATCH_FINI_VU = new Set();     // pour n'ouvrir la feuille qu'une fois

function couleurNote(n) { return n >= 7.5 ? "haute" : n >= 6.5 ? "bonne" : n >= 5.5 ? "" : "basse"; }

// Le style d'un onze et la lecture de l'adversaire : par codes dans la langue de
// l'écran quand la feuille les donne, sinon le français du serveur.
const styleTxt = (m, c) => m.style_codes ? ((m.style_codes[c] || []).map(x => t("style." + x)).join(", ") || t("style.equilibre")) : (m.style?.[c] || "");
const lectureTxt = (m, c) => m.lecture_codes ? (m.lecture_codes[c] || []).map(x => t("lecture." + x)).join(" · ") : (m.lecture?.[c] || []).join(" · ");
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
    el("span", {class: "compo-forme"}, nomFormation(m.formation?.[cote] || ""))));
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
        + (f.touches ? ` · ${t("match.ballons_joues", {n: f.touches})}` : "")},
      el("span", {class: "po"}, POSTE_ABBR[j.slot] || ""),
      el("span", {class: "nm"}, (j.nom || "").split(" ").slice(-1)[0]),
      el("span", {class: "fa"}, faits.join(" ")),
      jaugeEndurance(e),
      el("b", {class: "note " + couleurNote(f.note ?? 6)}, f.note ? f.note.toFixed(1) : "—"));
    c.append(l);
  }
  const utilises = new Set(m.entres?.[cote] || []);
  const restants = (m.banc?.[cote] || []).filter(j => !utilises.has(j.pid));
  c.append(el("div", {class: "compo-banc"}, `${t("match.banc")} ${restants.length} · `
    + `${m.changements?.[cote === "a" ? 0 : 1] ?? 0}/${SM_MAX_CHG} ${t("match.changements")}`));
  return c;
}

// Les stats avancées : les barres, la carte des tirs, la course au xG.
function ongletStats(d) {
  const m = d.match, moi = d.cote === "b" ? 1 : 0, lui = 1 - moi;
  const p = el("div", {class: "onglet-corps"});
  const stats = el("div", {class: "live-stats"});
  const pair = (lib, a, b) => [lib, a, b];
  for (const [lib, va, vb] of [
      pair(t("stats.possession"), m.possession[moi] + " %", m.possession[lui] + " %"),
      pair(t("stats.tirs"), m.tirs[moi], m.tirs[lui]),
      pair("xG", m.xg[moi].toFixed(2), m.xg[lui].toFixed(2)),
      pair(t("stats.xg_par_tir"), (m.tirs[moi] ? m.xg[moi] / m.tirs[moi] : 0).toFixed(2),
           (m.tirs[lui] ? m.xg[lui] / m.tirs[lui] : 0).toFixed(2)),
      pair(t("stats.corners"), m.corners?.[moi] ?? 0, m.corners?.[lui] ?? 0),
      pair(t("stats.fautes"), m.fautes?.[moi] ?? 0, m.fautes?.[lui] ?? 0),
      pair(t("stats.horsjeu"), m.horsjeu?.[moi] ?? 0, m.horsjeu?.[lui] ?? 0),
      pair(t("stats.cartons"), cartons(m, moi), cartons(m, lui))])
    stats.append(el("div", {class: "sl"}, el("b", {}, String(va)), el("span", {}, lib), el("b", {}, String(vb))));
  p.append(stats);
  p.append(el("div", {class: "etiq"}, t("stats.course_xg")), courseXg(m, moi));
  p.append(el("div", {class: "etiq"}, t("stats.ou_tire")), carteTirs(m, moi));
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
      if (f.buts) faits.push(t("stats.n_buts", {n: f.buts}));
      if (f.passes_d) faits.push(t("stats.n_passes_d", {n: f.passes_d}));
      if (f.arrets) faits.push(t("stats.n_arrets", {n: f.arrets}));
      faits.push(t("stats.n_ballons", {n: f.touches}));
      h.append(el("div", {class: "homme" + (c === "ab"[moi] ? " mien" : "") + (i === 0 && m.fini ? " premier" : "")},
        el("b", {class: "note " + couleurNote(f.note)}, f.note.toFixed(1)),
        el("span", {}, n),
        i === 0 && m.fini ? el("span", {class: "medaille"}, t("stats.homme_du_match")) : null,
        el("span", {class: "compteur"}, faits.join(" · "))));
    });
    p.append(el("div", {class: "etiq"}, m.fini ? t("stats.feuille") : t("stats.hommes")), h);
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
    el("span", {class: "lg mien"}, `${t("stats.toi")} ${cum[moi][n - 1].toFixed(2)}`),
    el("span", {class: "lg adverse"}, `${t("stats.eux")} ${cum[1 - moi][n - 1].toFixed(2)}`)));
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
      title: `${e.minute}' ${texteEvt(e)} · xG ${xg.toFixed(2)}`,
      style: `right:${(prof * 100).toFixed(1)}%;top:${(trav * 100).toFixed(1)}%;`
             + `width:${taille}px;height:${taille}px;margin:${-taille / 2}px`});
    fond.append(pt); n++;
  }
  if (!n) b.append(el("p", {class: "compteur"}, t("stats.pas_de_tir")));
  else b.append(el("p", {class: "compteur"}, t("stats.legende_tirs")));
  return b;
}

function ligneEvt(e, moi) {
  const l = el("div", {class: "evt " + e.type + (e.cote === "AB"[moi] ? " mien" : "")},
    el("span", {class: "min"}, (e.lib || e.minute) + "'"), el("span", {class: "ico"}, EVT_ICONE[e.type] || "•"),
    el("span", {class: "txt"}, texteEvt(e)));
  // d'où venait le but : une action à une passe ne raconte pas la même
  // chose qu'une action à six
  if (e.type === "but" && e.passes !== undefined)
    l.append(el("span", {class: "amont"},
      e.passes <= 1 ? t("match.action_directe") : t("match.passes_depuis", {n: e.passes, de: (e.depart || "").split(" ").slice(-1)[0]})));
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
  if (!vus.length) fil.append(el("p", {class: "compteur"}, t("match.vient_de_commencer")));
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
    el("div", {class: "style"}, styleTxt(m, "ab"[moi]))));
  // Le score et la minute sont ceux que l'ANIMATION a montrés : le
  // serveur a une minute d'avance, et un score qui change avant que le
  // ballon n'entre gâche le but (majTete).
  const scoreEl = el("div", {class: "live-score anton"}, `${m.score[moi]} – ${m.score[lui]}`);
  const minEl = el("div", {class: "mt-min anton"}, "");
  tete.append(el("div", {class: "mt-centre"}, scoreEl, minEl));
  tete.append(el("div", {class: "mt-eq droite"}, el("div", {class: "nom anton"}, m.noms[lui]),
    // Pas ses réglages : ce qu'on en voit (simulation.lecture_adverse).
    el("div", {class: "style"}, lectureTxt(m, cote)
      || (m.minute < 15 ? t("match.trop_tot") : t("match.rien_de_net")))));
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
  for (const cle of ONGLETS_MATCH) {
    if (cle === "tactique" && m.fini) continue;
    barre.append(el("button", {"data-onglet": cle, onclick: () => { ONGLET = cle; dessiner(); }}, t("onglet." + cle)));
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
    const r = m.resultat === "N" ? t("res.nul") : ((m.resultat === "A") === (moi === 0) ? t("res.victoire") : t("res.defaite"));
    const de = m.elo_apres && m.elo_apres[moi] !== null ? m.elo_apres[moi] - m.elo_avant[moi] : null;
    p.append(el("div", {class: "live-fin"}, el("b", {class: "anton"}, r),
      de === null ? el("span", {}, m.defi ? " · " + t("match.defi_hors_classement") : "") : el("span", {}, ` · Elo ${de > 0 ? "+" : ""}${de.toFixed(1)}`),
      routeTac === "/lobby/tactique" ? el("button", {class: "primaire", onclick: () => rendreLobby()}, t("match.rejouer")) : null));
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
  $("#solo-info").textContent = offerts ? t("solo.packs_offerts", {n: offerts}) : t("solo.accroche");
  B.append(d.campagne ? panneauCampagne(d) : panneauChoixSolo(d));
  B.append(panneauPalmares(d));
  if (d.campagne?.match && !d.campagne.match.fini) lancerBoucleSolo();
}

function panneauChoixSolo(d) {
  const p = el("div", {class: "panneau"}, el("h3", {class: "anton"}, t("solo.choisis_competition")),
    el("p", {class: "compteur"}, t("solo.choisis_texte")));
  const onglets = el("div", {class: "onglets"});
  for (const c of d.competitions)
    onglets.append(el("button", {class: SOLO.cle === c.cle ? "actif" : "",
      onclick: async () => { SOLO.cle = c.cle; await rendreSolo(SOLO.d); }},
      nomCompetition(c.cle, c.nom) + (c.format === "coupe" ? " · " + t("solo.coupe") : "")));
  p.append(onglets);
  if (!SOLO.cle) { p.append(el("p", {class: "info"}, t("solo.choisis_pour_voir"))); return p; }
  const zone = el("div", {class: "clubs-solo"}, el("p", {class: "compteur"}, t("chargement")));
  p.append(el("div", {class: "etiq"}, t("solo.quel_club")), zone);
  api(`/solo/clubs/${SOLO.cle}`).then(r => {
    zone.replaceChildren();
    for (const c of r.clubs) {
      const k = el("div", {class: "club-solo", tabindex: "0", role: "button",
        onclick: () => demarrerSolo(r, c), onkeydown: e => { if (e.key === "Enter") demarrerSolo(r, c); }});
      k.style.setProperty("--clubc", c.couleur);
      k.append(el("img", {src: `/images/logos/${c.team_id}.png`, alt: "", loading: "lazy", onerror: e => e.target.remove()}),
        el("div", {class: "qui"}, el("div", {class: "nom"}, c.nom),
          el("div", {class: "sous"}, t("solo.effectif_force", {n: c.force}))));
      zone.append(k);
    }
  }).catch(e => { zone.replaceChildren(el("p", {class: "avert"}, e.message)); });
  return p;
}

async function demarrerSolo(r, club) {
  if (!confirm(t("solo.confirmer", {club: club.nom, competition: nomCompetition(r.cle, r.nom)}))) return;
  try { await rendreSolo(await api("/solo/demarrer", {cle: r.cle, club: club.team_id})); }
  catch (e) { toast(e.message); }
}

function panneauCampagne(d) {
  const c = d.campagne;
  const p = el("div", {class: "panneau"});
  const pr = c.prochain;
  // A league round is a journée; a knockout round has a name of its own,
  // and which leg it is matters more than its number in the calendar.
  const ou = !pr ? t("solo.campagne_terminee")
    : (pr.phase === "ligue" || pr.phase === "championnat")
      ? t("solo.journee_sur", {n: pr.tour, total: c.format === "championnat" ? c.tours : 8})
      : (PHASES_SOLO[pr.phase] || pr.libelle || "") + (pr.manche ? ` · ${pr.manche === 1 ? t("solo.aller") : t("solo.retour")}` : "");
  p.append(el("div", {class: "tete-campagne"},
    el("div", {}, el("h3", {class: "anton"}, nomCompetition(c.cle, c.nom)),
      el("div", {class: "compteur"}, `${t("solo.a_la_place_de", {club: c.club_remplace})} · ${ou}`)),
    el("button", {class: "discret", onclick: async () => {
      if (!confirm(t("solo.abandonner_confirmer"))) return;
      try { await rendreSolo(await api("/solo/abandonner", {})); } catch (e) { toast(e.message); }
    }}, t("solo.abandonner"))));
  if (c.match) { p.append(panneauMatchSolo(c)); return p; }
  if (c.objectifs && c.objectifs.length) p.append(panneauObjectifs(c.objectifs));
  const onze = C.slots.every(x => x !== null) ? C.slots.slice() : null;
  if (!onze) p.append(el("div", {class: "avert"}, t("solo.onze_incomplet")));
  else if (c.prochain) {
    if (c.prochain.exempt) {
      p.append(el("p", {class: "info"}, t("solo.exempt")));
      p.append(el("div", {class: "actions"}, el("button", {class: "primaire", onclick: () => jouerSolo(onze)}, t("solo.passer_journee"))));
    } else {
      const a = c.prochain.adversaire;
      const ligne = el("div", {class: "affiche"});
      ligne.style.setProperty("--clubc", a.couleur || "#14161E");
      ligne.append(el("img", {src: `/images/logos/${a.team_id}.png`, alt: "", onerror: e => e.target.remove()}),
        el("div", {}, el("div", {class: "etiq"}, c.prochain.domicile ? t("solo.a_domicile") : t("solo.en_deplacement")),
          el("div", {class: "nom anton"}, a.nom),
          el("div", {class: "compteur"}, t("solo.effectif_force", {n: a.force})
            + (c.prochain.aller ? ` · ${t("solo.aller").toLowerCase()} ${c.prochain.aller.moi} – ${c.prochain.aller.lui}` : ""))));
      p.append(ligne);
      p.append(selecteurTactique(LOBBY.tac, () => {}));
      p.append(selecteurRythme({durees: G.saison?.durees_match, vitesses: G.saison?.vitesses_match}));
      p.append(el("div", {class: "actions"},
        el("button", {class: "primaire", onclick: () => jouerSolo(onze)},
          c.prochain.manche === 2 ? t("solo.jouer_retour") : t("solo.jouer"))));
    }
  }
  if (c.mes_matchs?.length) {
    p.append(el("div", {class: "etiq"}, t("solo.derniers_matchs")));
    for (const m of [...c.mes_matchs].reverse()) {
      const r = resSolo(m, c.place), chez_moi = m.a === c.place;
      p.append(el("div", {class: "ligne simple"},
        el("span", {class: "res " + r}, r),
        el("div", {class: "qui"}, el("div", {class: "nom"}, (chez_moi ? "" : t("solo.chez") + " ") + m.adversaire),
          el("div", {class: "sous"}, PHASES_SOLO[m.phase]
            ? PHASES_SOLO[m.phase] + (m.manche ? " · " + (m.manche === 1 ? t("solo.aller") : t("solo.retour")) : "")
            : t("solo.journee_n", {n: m.tour + 1}))),
        el("b", {class: "num"}, scoreSolo(m, c.place))));
    }
  }
  if (c.classement?.length)
    p.append(el("div", {class: "etiq"}, c.format === "championnat" ? t("solo.classement") : t("solo.phase_ligue")),
      tableauClassement(c.classement, c.qualification));
  if (c.tableau?.length) p.append(el("div", {class: "etiq"}, t("solo.tableau_final")), tableauCoupe(c.tableau));
  return p;
}

// A campaign match is played LIVE, on the same clock and the same pitch as
// a lobby match: you watch it, you adjust, you make your changes.
// Un match de campagne se joue sur LE MÊME écran qu'un match du lobby :
// il n'y a qu'une façon de regarder un match dans ce jeu.
function panneauMatchSolo(c) {
  const d = {match: c.match, cote: "a", duree: c.match.duree, vitesse: c.match.vitesse, minutes: c.match.minutes};
  const b = el("div", {});
  b.append(panneauMatch(d, "/solo/tactique", "/solo/pause", rendreSolo));
  if (c.match.fini) b.append(el("p", {class: "compteur"}, t("solo.cloture")));
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
  const tab = el("div", {class: "table-solo"});
  tab.append(el("div", {class: "tl tete"}, el("span", {}, "#"), el("span", {}, t("table.club")),
    el("b", {}, t("table.j")), el("b", {}, t("table.g")), el("b", {}, t("table.n")), el("b", {}, t("table.p")), el("b", {}, t("table.diff")), el("b", {}, t("table.pts"))));
  for (const l of lignes) {
    const zone = qual ? (l.rang <= qual.directs ? " direct" : l.rang <= qual.barrages ? " barrage" : " dehors") : "";
    tab.append(el("div", {class: "tl" + (l.toi ? " moi" : "") + zone}, el("span", {}, String(l.rang)),
      el("span", {class: "nom"}, l.nom), el("b", {}, String(l.j)), el("b", {}, String(l.g)),
      el("b", {}, String(l.n)), el("b", {}, String(l.p)),
      el("b", {}, (l.bp - l.bc > 0 ? "+" : "") + (l.bp - l.bc)), el("b", {class: "pts"}, String(l.pts))));
  }
  if (qual) tab.append(el("p", {class: "compteur"},
    t("solo.qualification", {directs: qual.directs, suivant: qual.directs + 1, barrages: qual.barrages})));
  return tab;
}

const PHASES_SOLO = tableT("phase.");

// One column per phase, each tie with its AGGREGATE over the two legs —
// that is what decides it, so that is what the bracket shows.
function tableauCoupe(phases) {
  const t = el("div", {class: "bracket"});
  for (const ph of phases) {
    const col = el("div", {class: "bcol"}, el("div", {class: "etiq"}, PHASES_SOLO[ph.phase] || ph.libelle));
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
  try { r = await api("/solo/jouer", {formation: C.formation, onze, banc: C.banc.slice(0, BANC_MAX), tactique: LOBBY.tac, duree: RYTHME, vitesse: VITESSE}); }
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
      const d = await api(cheminSonde("/solo"));
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
      `${{V: t("res.victoire"), N: t("res.nul"), D: t("res.defaite")}[resSolo(f, place)]}`
      + ` · ${t("stats.possession").toLowerCase()} ${chez_moi ? f.possession[0] : f.possession[1]} %`
      + ` · ${t("solo.tirs_contre", {a: chez_moi ? f.tirs[0] : f.tirs[1], b: chez_moi ? f.tirs[1] : f.tirs[0]})}`));
  const fil = el("div", {class: "fil"});
  for (const e of f.evenements)
    fil.append(el("div", {class: "evt " + e.type},
      el("span", {class: "min"}, (e.lib || e.minute) + "'"), el("span", {class: "ico"}, EVT_ICONE[e.type] || "•"),
      el("span", {class: "txt"}, texteEvt(e))));
  if (!f.evenements.length) fil.append(el("p", {class: "compteur"}, t("solo.sans_fait")));
  box.append(fil);
  const acts = el("div", {class: "actions"});
  if (bilan) acts.append(el("button", {class: "primaire", onclick: () => { dlg.close(); montrerBilanSolo(bilan); }}, t("solo.voir_bilan")));
  else acts.append(el("button", {class: "primaire", onclick: () => dlg.close()}, t("solo.journee_suivante")));
  box.append(acts); dlg.append(box); dlg.showModal();
}

// Le nom d'une compétition : dans le monde fictif (jeu/fictif), le pays dans la langue
// de l'écran ; dans le monde réel, le vrai nom, qui ne se traduit pas.
const nomCompetition = (cle, nom) => (G.saison?.monde === "fictif" && cle && existeT("competition." + cle)) ? t("competition." + cle) : (nom || cle || "");
// Ce qu'une campagne a payé : par code dans la langue de l'écran, sinon le français du serveur.
const recompenseTxt = b => (b.code && existeT("recompense." + b.code)) ? t("recompense." + b.code) : (b.libelle || b.tour || "");
// Les objectifs du club : trois par campagne, tirés selon ta force dans le champ.
// Chacun paie ; les trois remplis donnent un titre.
function panneauObjectifs(objs, fini) {
  const p = el("div", {class: "objectifs"}, el("div", {class: "etiq"}, fini ? t("objectifs.titre_fin") : t("objectifs.titre")));
  for (const o of objs) {
    const etat = o.reussi ? "ok" : (o.perdu || (fini && !o.reussi)) ? "rate" : "encours";
    const valeur = o.cle === "buts" ? `${o.valeur ?? 0} / ${o.cible}`
      : o.cle === "domicile" ? t("objectifs.defaites_chez_toi", {n: o.valeur ?? 0})
      : o.cle === "classement" ? (o.valeur ? `${ordinal(o.valeur)} (${t("objectifs.cible")} : ${ordinal(o.cible)})` : "—")
      : (o.valeur ? (PHASES_SOLO[o.valeur] || o.valeur) : "—");
    p.append(el("div", {class: "objectif " + etat},
      el("span", {class: "coche"}, etat === "ok" ? "✓" : etat === "rate" ? "✗" : "·"),
      el("div", {class: "qui"}, el("b", {}, o.code && existeT("obj." + o.code) ? t("obj." + o.code, o.params) : o.libelle), el("span", {class: "compteur"}, ` · ${valeur}`)),
      el("span", {class: "compteur"}, `${fM(o.credits)} + ${t("packs.pack").toLowerCase()} ${TIER_TXT[o.pack] || o.pack}`)));
  }
  return p;
}
function montrerBilanSolo(b) {
  if (!b) return;
  const dlg = $("#fiche"); dlg.replaceChildren();
  const box = el("div", {class: "fiche bilan"}, el("h3", {class: "anton"}, recompenseTxt(b)),
    el("p", {class: "compteur"}, b.rang ? `${t("solo.rang_sur", {rang: ordinal(b.rang), sur: b.sur})} · ${t("solo.bilan_ligue", {v: b.victoires, n: b.nuls, m: b.matchs})}`
      : `${b.tour ? recompenseTxt(b) : ""} · ${t("solo.bilan_coupe", {v: b.victoires, m: b.matchs})}`));
  if (b.objectifs && b.objectifs.length) box.append(panneauObjectifs(b.objectifs, true));
  if (b.titre) box.append(el("p", {class: "titre-gagne anton"}, `🏆 ${b.titre}`));
  box.append(el("div", {class: "gains"},
    el("div", {class: "tuile"}, el("div", {class: "etiq"}, t("solo.credits")), el("b", {class: "anton"}, fM(b.credits))),
    ...Object.entries(b.packs || {}).map(([tier, n]) =>
      el("div", {class: "tuile"}, el("div", {class: "etiq"}, t("packs.titre") + " " + TIER_TXT[tier]), el("b", {class: "anton"}, "× " + n)))));
  box.append(el("div", {class: "actions"},
    el("button", {onclick: () => { dlg.close(); montrer("packs"); }}, t("solo.ouvrir_packs")),
    el("button", {class: "primaire", onclick: () => { dlg.close(); rendreSolo(); }}, t("solo.nouvelle_campagne"))));
  dlg.append(box); dlg.showModal();
}

function panneauPalmares(d) {
  const p = el("div", {class: "panneau"}, el("h3", {class: "anton"}, t("solo.palmares")));
  if (d.titres?.length) p.append(el("div", {class: "titres"}, ...d.titres.map(x => el("span", {class: "titre-gagne"}, `🏆 ${x}`))));
  if (!d.palmares?.length) { p.append(el("p", {class: "compteur"}, t("solo.aucune_campagne"))); return p; }
  for (const c of d.palmares)
    p.append(el("div", {class: "ligne simple"},
      el("div", {class: "qui"}, el("div", {class: "nom"}, nomCompetition(c.cle, c.competition)),
        el("div", {class: "sous"}, recompenseTxt(c) + (c.rang ? ` · ${t("solo.rang_sur", {rang: ordinal(c.rang), sur: c.sur})}` : ""))),
      el("b", {class: "num"}, fM(c.credits || 0)),
      el("span", {class: "compteur"}, Object.entries(c.packs || {}).map(([tier, n]) => `${n} ${TIER_TXT[tier]}`).join(", ") || "—")));
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
    el("div", {class: "t2d-six gauche"}), el("div", {class: "t2d-six droite"})));
  // les cages, avec leurs filets : un but les fait onduler
  for (const c of ["gauche", "droite"]) {
    const cage = el("div", {class: "t2d-cage " + c});
    cage.innerHTML = `<svg viewBox="0 0 10 40" preserveAspectRatio="none"><defs><pattern id="filet-${c}" width="2.2" height="2.2" patternUnits="userSpaceOnUse"><path d="M0 0H2.2M0 0V2.2" stroke="rgba(255,255,255,.55)" stroke-width=".35" fill="none"/></pattern></defs><rect class="filet" x="0" y="0" width="10" height="40" fill="url(#filet-${c})"/><rect class="poteaux" x="${c === "gauche" ? 9 : 0}" y="0" width="1" height="40" fill="#fff"/></svg>`;
    t.append(cage);
  }
  const ballon = el("div", {class: "t2d-ballon"});
  ballon.innerHTML = '<svg viewBox="0 0 20 20"><circle cx="10" cy="10" r="9.2" fill="#fff" stroke="#1a1a1a" stroke-width="1"/><polygon points="10,5.2 13.6,7.8 12.2,12 7.8,12 6.4,7.8" fill="#1a1a1a"/><polygon points="2.4,7.6 4.9,5.4 6.4,7.8 5,10.6 1.9,10.4" fill="#1a1a1a"/><polygon points="17.6,7.6 15.1,5.4 13.6,7.8 15,10.6 18.1,10.4" fill="#1a1a1a"/><polygon points="6.2,18.4 7.8,12 10,13.6 9.6,18.9" fill="#1a1a1a"/><polygon points="13.8,18.4 12.2,12 10,13.6 10.4,18.9" fill="#1a1a1a"/><polygon points="8.4,1 10,3.6 11.6,1" fill="#1a1a1a"/></svg>';
  t.append(el("div", {class: "t2d-jeu"}), el("div", {class: "t2d-ombre"}), ballon,
    el("div", {class: "t2d-bandeau", hidden: true}), el("div", {class: "t2d-popup", hidden: true}));
  return t;
}

// Vingt-deux JETONS, pas vingt-deux cartes.  Une carte est faite pour
// être lue de près ; sur un terrain, ce qu'on lit, c'est une position,
// un côté, une distance — comme sur la tablette d'un entraîneur.  Le
// jeton porte le poste tenu, le nom dessous, l'endurance en dessous.
// Dessinés une fois ; ensuite seule leur position change.
function peuplerTerrain(t, m, moi) {
  const jeu = t.querySelector(".t2d-jeu");
  jeu.replaceChildren();
  T2D.pions = {};
  for (const cote of ["a", "b"]) {
    const tous = [...(m.onze?.[cote] || []), ...(m.banc?.[cote] || [])];
    const joueurs = (m.sur_le_terrain?.[cote] || []).map(pid => tous.find(j => j.pid === pid)).filter(Boolean);
    const places = placesDe(joueurs, m.formation?.[cote]);
    joueurs.forEach((j, i) => {
      const poste = j.slot || j.poste || "Milieu relayeur";
      const gk = posteBase(poste) === "Gardien";
      const p = el("div", {class: "t2d-pion " + (cote === moi ? "mien" : "adverse") + (gk ? " gk" : ""),
        title: `${j.nom} · ${j.ovr}${j.slot ? " · " + (POSTE_COURT[j.slot] || j.slot) : ""}`});
      p.append(el("span", {class: "t2d-jeton"}, POSTE_ABBR[poste] || (gk ? "GB" : "")),
        el("span", {class: "t2d-nom"}, (j.nom || "").split(" ").slice(-1)[0]),
        el("span", {class: "t2d-jauge"}, el("i", {})));
      p.dataset.pid = j.pid; p.dataset.cote = cote;
      p._base = places[i] || [0.4, 0.5];
      p._poste = poste;
      p._gk = gk;
      p._phys = j.physique || null;
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
function ecran(cote, x, y, moi, brut = false) {
  // Les deux camps jouent la même forme en miroir : sans écart, leurs
  // milieux se posent exactement au même endroit et les noms se
  // chevauchent.  On les décale un peu en largeur et en profondeur,
  // chacun d'un côté, pour que les vingt-deux restent lisibles.  Pas le
  // gardien ni le ballon (`brut`) : un gardien décalé n'est plus dans
  // l'axe de son but, et le ballon doit être exactement où il est.
  const mien = cote === moi;
  const dx = brut ? 0 : (mien ? -0.012 : 0.012), dy = brut ? 0 : (mien ? -0.035 : 0.035);
  const xx = Math.max(0.02, Math.min(0.98, x + dx));
  const gauche = mien ? xx : 1 - xx;
  const haut = (mien ? y : 1 - y) + dy;
  return [gauche, Math.max(0.05, Math.min(0.95, haut))];
}

// Le but qu'attaque un camp, à l'écran.  La cage fait 19 % de la hauteur
// du terrain : une frappe cadrée tombe ENTRE les poteaux — à 0,30 les
// frappes au ras du poteau sortaient de la cage et tout ressemblait à
// un poteau rentrant.
const LARGEUR_BUT = 0.16;
function buts(cote, moi, t) {
  const gauche = cote === moi ? 0.975 : 0.025;
  return [gauche, 0.5 + ((t === undefined ? 0.5 : t) - 0.5) * LARGEUR_BUT];
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
  "Milieu de couloir": {av: 0.240, rec: -0.200, lar: 0.24, surface: 0.28},
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
  ailiers:    {poste: ["Ailier", "Ailier droit", "Ailier gauche", "Milieu de couloir"],
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

// Un petit écart propre à chaque joueur, FIXE pour tout le match : les
// lignes ne sont pas au laser, et personne ne tremble entre deux phases.
function grain(pid) {
  let h = (pid * 2654435761) >>> 0;
  h ^= h >>> 13; h = Math.imul(h, 0x5bd1e995) >>> 0; h ^= h >>> 15;
  return [((h & 0xffff) / 0xffff - 0.5) * 0.022, (((h >>> 16) & 0xffff) / 0xffff - 0.5) * 0.03];
}

// Où va le gardien, dans SON repère.  Il ferme l'angle : sur la droite
// entre le ballon et le milieu de son but, un peu devant sa ligne, plus
// avancé quand le ballon est loin.  Sur une frappe il va au point
// visé ; sur un arrêt il y est, le ballon dans les gants ; sur un but
// il est parti du mauvais côté.
function placeGardien(sien, phase, xb, yb) {
  const contre = !sien && (phase.k === "tir" || phase.k === "but" || phase.k === "rate");
  if (contre) {
    const t = phase.t === undefined ? (T2D.dernierTir ?? 0.5) : phase.t;
    const yt = 0.5 + (t - 0.5) * LARGEUR_BUT;
    if (phase.k === "but") return [0.03, 0.5 + (yt - 0.5) * -0.7];         // battu, parti de l'autre côté
    return [0.03, 1 - yt];                                                    // le but visé, vu de sa ligne
  }
  if (sien && (phase.k === "arret" || phase.k === "relance" || phase.k === "degagement")) return null; // porteur : il est au ballon
  // Dans l'axe, sur sa ligne, la plupart du temps.  Il ne s'en écarte
  // qu'un peu, vers le côté du ballon quand celui-ci approche, et il
  // avance de quelques mètres quand le jeu est loin.
  const loin = Math.max(0, Math.min(1, xb));                                  // 0 : sur sa ligne, 1 : tout là-bas
  const x = 0.03 + 0.045 * loin;
  const y = 0.5 + (yb - 0.5) * (0.06 + 0.16 * (1 - loin));
  return [x, y];
}

function bougerTerrain(t, cote, zone, moi, ph, suivant) {
  if (!T2D.pions) return;
  const phase = ph || {k: "passe", z: zone, c: cote, y: 0.5, p: null};
  if (phase.c === undefined || phase.c === null) return;
  // Avec la simulation (sim2d.js), les jetons ne sont plus POSÉS : ils
  // reçoivent le contexte de la phase et y courent à chaque tic.
  if (window.SIM && SIM.actif) { SIM.phaseDe(phase, suivant); return; }
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
    const xb = sien ? bx : 1 - bx, yb = sien ? by : 1 - by;
    let x, y;
    if (p._gk) {
      const g = placeGardien(sien, phase, xb, yb);
      [x, y] = g || [0.035, 0.5];
    } else {
      [x, y] = placeJoueur(p, sien, progression, phase, T2D.consignes?.[c]);
      // le bloc coulisse vers le ballon, celui qui défend davantage
      y += (yb - 0.5) * (sien ? 0.12 : 0.22);
      const g = grain(+p.dataset.pid);
      x += g[0]; y += g[1];
    }
    places[cle] = {x, y, sien, gk: p._gk};
  }
  const porteur = places[porteurCle];
  if (porteur) {
    // le porteur vient au ballon ; sur une frappe il est déjà là ; sur un
    // arrêt, le gardien est sur sa ligne, au point visé
    if (phase._arret) { const [ax, ay] = ballonArret(phase); porteur.x = ax; porteur.y = ay; }
    else { porteur.x = bx; porteur.y = by; }
    if (!SUR_LE_BUT.has(phase.k) && !ARRETS_JEU.has(phase.k)) {
      const dist = v => Math.hypot(v.x - bx, v.y - by);
      // un soutien se propose
      const soutien = Object.entries(places)
        .filter(([cle, v]) => cle !== porteurCle && v.sien && !v.gk)
        .sort((a, b) => dist(a[1]) - dist(b[1]))[0];
      if (soutien) { const v = soutien[1]; v.x += (bx - v.x) * 0.18; v.y += (by - v.y) * 0.18; }
      // et l'adversaire le plus proche vient au contact — dans SON repère
      // le ballon est en miroir
      const bxa = 1 - bx, bya = 1 - by;
      const presseur = Object.entries(places)
        .filter(([, v]) => !v.sien && !v.gk)
        .sort((a, b) => Math.hypot(a[1].x - bxa, a[1].y - bya) - Math.hypot(b[1].x - bxa, b[1].y - bya))[0];
      if (presseur) { const v = presseur[1]; v.x += (bxa - v.x) * 0.35; v.y += (bya - v.y) * 0.35; }
    }
  }
  for (const [cle, p] of Object.entries(T2D.pions)) {
    const c = cle.slice(0, 1), v = places[cle];
    const [g, h] = ecran(c, clamp(v.x, 0.02, 0.97), clamp(v.y, 0.04, 0.96), moi, v.gk || cle === porteurCle);
    p.style.left = (g * 100) + "%";
    p.style.top = (h * 100) + "%";
    // le porteur arrive avec le ballon, les autres au rythme du match :
    // plus la minute est longue, plus les courses sont posées
    const lent = Math.round(Math.max(700, Math.min(1600, (T2D.dureeBallon || 500) * 1.3)));
    p.style.transitionDuration = (cle === porteurCle && T2D.dureeBallon ? T2D.dureeBallon : lent) + "ms";
  }
}

// Où est le ballon pour un arrêt du gardien : dans ses gants, sur sa
// ligne, à l'endroit visé par la frappe — pas au milieu de sa surface.
function ballonArret(ph) {
  const t = T2D.dernierTir ?? 0.5;
  return [0.03, 1 - (0.5 + (t - 0.5) * LARGEUR_BUT)];
}

// Une phase : le ballon va où elle dit, le porteur s'allume, et pour un
// tir le ballon quitte vraiment le pied pour aller au but.
function jouerPhase(t, ph, moi) {
  const b = t.querySelector(".t2d-ballon"), ombre = t.querySelector(".t2d-ombre");
  const jeu = t.querySelector(".t2d-jeu");
  if (!ph) { b.hidden = true; ombre.hidden = true; return; }
  const cote = "ab"[ph.c];
  if (ph.k === "arret") ph = {...ph, _arret: true};
  bougerTerrain(t, ph.c, ph.z, moi, ph, T2D.phases[T2D.i] || null);
  for (const p of Object.values(T2D.pions || {}))
    p.classList.toggle("ballon", p.dataset.cote === cote && +p.dataset.pid === ph.p);
  b.classList.toggle("tir", ph.k === "tir" || ph.k === "rate");
  b.classList.toggle("dedans", ph.k === "but");
  // Un arrêt de jeu ne se voit que quand il pèse : un but, un carton, une
  // blessure, un penalty.  Une faute est un coup de sifflet et un coup
  // franc joué dans la foulée — la montrer comme une pause cassait le
  // fil du match vingt-cinq fois par mi-temps.
  T2D.arret = ARRETS_LOURDS.has(ph.k);
  jeu.classList.toggle("arret", T2D.arret);
  jeu.classList.toggle("celebre", ph.k === "but");
  const duree = T2D.dureeBallon || 400;
  b.style.transitionDuration = duree + "ms";
  ombre.style.transitionDuration = duree + "ms";
  let g, h;
  if (ph.k === "tir" || ph.k === "but" || ph.k === "rate") {
    // une frappe manquée ne revient pas dans les pieds du tireur : elle
    // file à côté du but
    [g, h] = buts(cote, moi, ph.k === "rate" ? (T2D.dernierTir ?? 0.5) : ph.t);
    const dehors = ph.k === "rate" ? (h < 0.5 ? -0.10 : 0.10) : 0;
    if (ph.k === "tir") T2D.dernierTir = ph.t;
    if (ph.k !== "but") { b.style.transitionDuration = "280ms"; ombre.style.transitionDuration = "280ms"; }
    h += dehors;
    if (ph.k === "but") {
      // le filet ondule
      const cage = t.querySelector(".t2d-cage." + (g > 0.5 ? "droite" : "gauche"));
      if (cage) { cage.classList.remove("ondule"); void cage.offsetWidth; cage.classList.add("ondule"); }
    }
  } else if (ph.k === "arret") {
    [g, h] = ecran(cote, ...ballonArret(ph), moi, true);
  } else {
    const [bx, by] = ballonDe(ph);
    [g, h] = ecran(cote, bx, by, moi, true);
  }
  b.hidden = false; ombre.hidden = false;
  if (window.SIM && SIM.actif) SIM.envoyer(g, h, ph, duree);   // il y va à sa vitesse
  else {
    b.style.left = (g * 100) + "%"; b.style.top = (h * 100) + "%";
    ombre.style.left = (g * 100) + "%"; ombre.style.top = (h * 100) + "%";
    // il roule le temps du trajet
    b.classList.add("en-vol");
    clearTimeout(T2D.rouleTimer);
    T2D.rouleTimer = setTimeout(() => b.classList.remove("en-vol"), Math.max(200, duree));
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
    nom.textContent = (PHASE_ICONE[ph.k] ? PHASE_ICONE[ph.k] + " " : "") + (ph.d || (PHASE_TXT[ph.k] || "") + (j ? " — " + j : ""));
    nom.className = "t2d-action " + ph.k;
  }
}

const PHASE_ICONE = {faute: "🟡", carton: "🟨", horsjeu: "🚩", corner: "⛳", but: "⚽", blessure: "🚑", penalty: "⚠"};
const ARRETS_LOURDS = new Set(["but", "blessure", "carton", "penalty"]);
const ARRETS_JEU = new Set(["faute", "horsjeu", "but", "blessure", "carton", "penalty"]);
const PHASE_TXT = tableT("phase2d.");

function annoncer(t, evt) {
  const bandeau = t.querySelector(".t2d-bandeau");
  if (!evt) { bandeau.hidden = true; return; }
  bandeau.replaceChildren(el("span", {class: "ico"}, EVT_ICONE[evt.type] || "•"),
    el("span", {class: "txt"}, texteEvt(evt)));
  bandeau.className = "t2d-bandeau " + evt.type;
  bandeau.hidden = false;
}

// Un but, un rouge, un penalty : ça se voit en plein terrain, pas dans
// un bandeau de bas de page.
const DUREE_POPUP = 3800;
function surgir(terr, evt, moi) {
  const p = terr.querySelector(".t2d-popup");
  if (!p) return;
  moi = moi === "b" || moi === 1 ? 1 : 0;                 // T2D.moi est « a » ou « b »
  const mien = evt.cote === "AB"[moi];
  let titre, sous, classe = evt.type;
  if (evt.type === "but") {
    titre = evt.penalty ? t("popup.penalty_transforme") : t("popup.but");
    sous = (evt.nom || "") + (evt.passeur && !evt.penalty ? ` · ${t("popup.servi_par", {nom: (evt.passeur || "").split(" ").slice(-1)[0]})}` : "");
  } else if (evt.type === "rouge") { titre = t("popup.rouge"); sous = texteEvt(evt); }
  else if (evt.type === "penalty_manque") { titre = t("popup.penalty_manque"); sous = texteEvt(evt); }
  else return;
  // Le minuteur ne s'annule qu'ici, une fois sûr qu'une pop-up remplace
  // l'autre : l'annuler pour un événement sans pop-up (la faute qui suit
  // un penalty) laissait la précédente à l'écran jusqu'au but suivant.
  clearTimeout(T2D.popupTimer);
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
const POIDS_PHASE = {faute: 1.0, duel: 0.7, horsjeu: 1.1, but: 2.4, blessure: 2.0, carton: 1.4,
                     tir: 1.2, arret: 1.4, coupfranc: 0.9, corner: 1.2, penalty: 1.8, engagement: 1.1};
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
  if (oublier) arreterTerrainB(true);
  if (oublier) {
    if (window.SIM) SIM.stop();
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
// La minute telle qu'on l'affiche : 45+2, 90+4.  `min` est l'index de la
// minute dans le match ; le temps additionnel de la première période décale
// tout ce qui suit (simulation.libelle).
function libMin(min, m) {
  const a1 = m && m.additionnel ? m.additionnel[0] : null;
  if (min <= 45 || a1 === null || a1 === undefined) return String(min);
  if (min <= 45 + a1) return `45+${min - 45}`;
  const d = min - a1;
  return d <= 90 ? String(d) : `90+${d - 90}`;
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
  const lib = libMin(min, m);
  h.min.textContent = m.fini ? t("match.termine")
    : m.pause ? `${lib}' — ${{"mi-temps": t("pause.mi_temps"), "blessure": t("pause.blessure")}[m.motif_pause] || t("pause.arrete")}`
    : `${lib}'`;
  h.horloge.style.width = Math.round(100 * min / (m.total || (h.minutes || 90) + 7)) + "%";
}


// -- Le terrain du moteur B (terrain_b.js) dans l'écran de match --------------
// Le serveur avance le match vivant au rythme de l'horloge et renvoie, à
// chaque sondage, les images de positions après la dernière reçue
// (`depuis`).  Le terrain les joue derrière, à la vitesse de l'horloge
// (90 minutes en `duree` secondes), sans jamais dépasser ce qu'il a reçu ;
// le bandeau (score, minute) suit ce que le terrain montre, pas le serveur.
// L'horloge de l'écran est le TEMPS AFFICHÉ (jeu/direct.py) : le ballon vivant se joue
// en entier à la vitesse de la rencontre, chaque arrêt de jeu se saute jusqu'à ses deux
// dernières secondes, comme dans le bac.  `d` est le temps affiché consommé.
const TB = {rid: null, terrain: null, noeud: null, canvas: null, d: 0, derniere: 0, raf: null, vitesse: 2,
            m: null, moi: "a", fini: false, pause: false};
// Le retard que l'écran garde sur le serveur, en secondes de temps affiché : le
// temps d'un sondage et demi, quelle que soit la vitesse du match, pour avoir
// toujours des images d'avance et ne jamais attendre le prochain paquet.
function margeB() { return 3.5 * TB.vitesse; }
function depuisB() { return (TB.rid !== null && TB.terrain && TB.terrain.trace.length) ? TB.terrain.duree : null; }
function cheminSonde(base) { const d = depuisB(); return d === null ? base : `${base}?depuis=${d}`; }
function panneauTerrainB(d, moi) {
  const m = d.match;
  if (TB.rid !== m.rencontre_id || !TB.noeud) {
    arreterTerrainB(true);
    TB.rid = m.rencontre_id;
    const p = el("div", {class: "panneau terrain-live"});
    p.append(el("div", {class: "t2d-legende"},
      el("span", {class: "lg mien"}, t("terrain.ton_equipe")), el("span", {class: "lg adverse"}, t("terrain.adversaire")),
      el("span", {class: "t2d-action"}, "")));
    const boite = el("div", {class: "terrain2d terrain-b"});
    const canvas = el("canvas", {class: "terrain-b-canvas", width: 1050, height: 680});
    boite.append(canvas); p.append(boite);
    TB.noeud = p; TB.canvas = canvas;
    TB.terrain = new TerrainB(canvas, {miroir: moi === "b"});
    TB.terrain.charger({joueurs: m.cartes || [], trace: [], evenements: [], trace_pas: m.trace_pas || 0.4, phases: m.phases || null,
                        saut_arret: m.saut_arret}, m.maillots);
    TB.d = -1; TB.derniere = performance.now();
    T2D.rid = m.rencontre_id; T2D.vus = new Set(); T2D.score = [0, 0]; T2D.m = 0;
  }
  if (m.cartes) TB.terrain.remplacer(m.cartes);
  TB.terrain.ajouter(m.trace || [], m.gestes || []);
  TB.m = m; TB.moi = moi; TB.fini = !!m.fini; TB.pause = !!m.pause;
  T2D.moi = moi;                               // le bandeau lit le score de ton côté
  TB.vitesse = m.vitesse || d.vitesse || 2;
  // on arrive en cours de match : on regarde les dernières secondes reçues, pas le coup d'envoi
  if (TB.d < 0 && TB.terrain.trace.length) TB.d = Math.max(0, TB.terrain.affiche - margeB());
  TB.noeud.querySelector(".terrain2d").classList.toggle("suspendu", !!m.pause);
  if (!TB.raf) { TB.derniere = performance.now(); TB.raf = requestAnimationFrame(boucleB); }
  return TB.noeud;
}
function boucleB(now) {
  TB.raf = null;
  if (!TB.terrain || !TB.noeud || !TB.noeud.isConnected) return;
  const dt = Math.min(0.5, (now - TB.derniere) / 1000); TB.derniere = now;
  const tr = TB.terrain;
  if (!TB.pause && tr.trace.length && TB.d >= 0) {
    TB.d = Math.min(tr.affiche, TB.d + dt * TB.vitesse);
    if (tr.affiche - TB.d > 2.5 * margeB()) TB.d = tr.affiche - margeB();   // trop de retard (onglet endormi) : on rattrape
  }
  const r = tr.dessiner(tr.indexAffiche(Math.max(0, TB.d)));
  // le bandeau suit le terrain
  const m = TB.m;
  if (m) {
    T2D.rid = m.rencontre_id;
    T2D.m = Math.floor(r.t / 60);
    T2D.score = r.score;
    const vus = new Set();
    (m.evenements || []).forEach((e, i) => { if (e.t === undefined || e.t === null || e.t <= r.t) vus.add(i); });
    T2D.vus = vus;
    majTete();
  }
  TB.raf = requestAnimationFrame(boucleB);
}
function arreterTerrainB(oublier) {
  if (TB.raf) { cancelAnimationFrame(TB.raf); TB.raf = null; }
  if (oublier) { TB.rid = null; TB.terrain = null; TB.noeud = null; TB.canvas = null; TB.d = -1; TB.m = null; }
}

// Le panneau est RÉUTILISÉ d'un sondage à l'autre, pas reconstruit :
// redessiner vingt-deux cartes toutes les deux secondes et demie
// relançait chaque transition CSS et effaçait le bandeau d'événement.
function panneauTerrain(d, moi) {
  const m = d.match;
  if (m.moteur === "B") return panneauTerrainB(d, moi);
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
      el("span", {class: "lg mien"}, t("terrain.ton_equipe")),
      el("span", {class: "lg adverse"}, t("terrain.adversaire")),
      el("span", {class: "t2d-action"}, "")));
    const terr = terrain2d();
    p.append(terr);
    peuplerTerrain(terr, m, moi);
    T2D.noeud = p; T2D.cle = cle;
    if (T2D.m > m.minute) T2D.m = Math.max(0, m.minute - 1);
    if (window.SIM) SIM.init(terr, moi);
  }
  const terr = p.querySelector(".terrain2d");
  // le panneau revient à l'écran après un détour par un autre onglet :
  // la simulation, qui s'était endormie, repart
  if (window.SIM && SIM.t === terr && !SIM.timer) { SIM.actif = true; SIM.start(); }
  T2D.fil = m.fil || [];
  T2D.cible = m.minute;
  T2D.evts = m.evenements || [];
  T2D.t = terr; T2D.moi = moi;
  T2D.consignes = m.tactique || {};
  T2D.pas = Math.max(900, (d.duree * 1000) / (d.minutes || 90));
  if (T2D.m === 0 || !T2D.score) { if (T2D.m === 0) T2D.m = Math.max(0, T2D.cible - 1); vusInitiaux(m); }
  if (T2D.m > T2D.cible) T2D.m = T2D.cible;
  jauges(m);
  reAnnoncer(terr);
  terr.classList.toggle("suspendu", !!m.pause);
  // L'horloge d'animation tourne PLUS LENTEMENT que le sondage : la
  // relancer à chaque réponse l'empêchait de se déclencher, et le terrain
  // ne bougeait jamais tout seul.
  if (!m.fini && !m.pause && !T2D.timer) programmer(200);
  if (m.pause) arreterTerrain();
  if (m.fini) {
    arreterTerrain();
    T2D.m = m.minute;
    const der = T2D.fil[T2D.fil.length - 1];
    if (der) bougerTerrain(terr, der.c, der.z, moi);
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
const CHG = {cle: null, noeud: null, sel: [], maj: null, refresh: null};

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
    el("span", {class: "fam " + j.fam}, POSTE_ABBR[j.slot] || POSTE_ABBR[j.poste] || FAM_COURT[j.fam] || j.fam),
    el("div", {class: "qui"}, el("span", {class: "nom"}, j.nom),
      el("span", {class: "sous"}, POSTE_COURT[j.slot || j.poste] || j.slot || j.poste || "")),
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
  CHG.sel = [];
  CHG.noeud = construireChangements(d, route, rendre);
  return CHG.noeud;
}

function construireChangements(d, route, rendre) {
  const m = d.match, cote = d.cote === "b" ? "b" : "a";
  const {surTerrain, banc, blesses, endu, restants} = gensDuBanc(m, cote);
  const b = el("div", {class: "changements"});
  const routePerm = route.replace("changement", "permutation");

  // Une blessure arrête le match : tant que le manager n'a pas dit qui
  // entre, l'horloge ne repart pas.  C'est la seule décision qui bloque.
  const zoneBlessure = el("div", {});
  b.append(zoneBlessure);
  if (blesses.length) {
    const bl = el("div", {class: "blessure-stop"},
      el("div", {class: "titre anton"}, "🚑 " + t("chg.sort_blessure", {noms: blesses.map(j => j.nom).join(", "), n: blesses.length})),
      el("p", {class: "etat"}, ""));
    if (!banc.length || restants <= 0) {
      bl.append(el("p", {class: "compteur"}, t("chg.plus_personne")));
    } else {
      const liste = el("div", {class: "chg-liste"});
      for (const j of banc)
        liste.append(ligneJoueur(j, endu, "bless", async () => {
          try { await rendre(await api(route, {sortant: blesses[0].pid, entrant: j.pid})); toast(t("chg.entre", {nom: j.nom})); }
          catch (e) { toast(e.message); }
        }));
      bl.append(liste);
    }
    zoneBlessure.append(bl);
  }

  // UN SEUL geste pour les deux décisions.  Touche un joueur sur le
  // terrain et un sur le banc : c'est un changement.  Touche deux
  // joueurs sur le terrain : ils permutent leurs postes — ce n'est pas
  // un changement, ça n'en coûte pas un, et il n'y a pas de limite.
  const compteur = el("div", {class: "etiq"}, "");
  b.append(compteur, el("p", {class: "compteur"}, t("chg.aide")));
  const choix = el("div", {class: "chg-choix"});
  const maj = () => {
    const s = CHG.sel;
    choix.querySelectorAll("[data-pid]").forEach(n => n.classList.toggle("choisi",
      s.some(x => x.role === n.dataset.role && x.pid === +n.dataset.pid)));
    const dessus = s.filter(x => x.role === "out"), dedans = s.filter(x => x.role === "in");
    const nom = pid => (surTerrain.concat(banc).find(j => j.pid === pid)?.nom || "").split(" ").slice(-1)[0];
    if (dessus.length === 2) {
      valider.disabled = false;
      valider.textContent = t("chg.permuter", {un: nom(dessus[0].pid), deux: nom(dessus[1].pid)});
      valider.dataset.mode = "perm";
    } else if (dessus.length === 1 && dedans.length === 1) {
      valider.disabled = restants <= 0;
      valider.textContent = restants <= 0 ? t("chg.plus_possible") : t("chg.entre_pour", {entrant: nom(dedans[0].pid), sortant: nom(dessus[0].pid)});
      valider.dataset.mode = "chg";
    } else {
      valider.disabled = true;
      valider.textContent = dessus.length === 1 ? t("chg.choisis_entrant") : t("chg.choisis");
      valider.dataset.mode = "";
    }
  };
  const toucher = (j, role) => {
    const deja = CHG.sel.some(x => x.role === role && x.pid === j.pid);
    let s = CHG.sel.filter(x => !(x.role === role && x.pid === j.pid));
    if (!deja) {
      // on l'ajoute, en poussant le plus ancien du même rôle si la place
      // est prise (deux du terrain au plus, un du banc)
      const max = role === "out" ? 2 : 1;
      const memes = s.filter(x => x.role === role);
      if (memes.length >= max) s = s.filter(x => x !== memes[0]);
      // deux du terrain et un du banc ne vont pas ensemble
      if (role === "out" && s.some(x => x.role === "out")) s = s.filter(x => x.role !== "in");
      if (role === "in") { const out = s.filter(x => x.role === "out"); s = s.filter(x => x.role !== "out").concat(out.slice(-1)); }
      s.push({role, pid: j.pid});
    }
    CHG.sel = s;
    maj();
  };
  const colonne = (titre, gens, role) => {
    const c = el("div", {}, el("div", {class: "etiq"}, titre));
    for (const j of gens) c.append(ligneJoueur(j, endu, role, () => toucher(j, role)));
    if (!gens.length) c.append(el("p", {class: "compteur"}, role === "in" ? t("chg.personne_banc") : t("chg.personne")));
    return c;
  };
  const valider = el("button", {class: "primaire", disabled: true, onclick: async () => {
    const s = CHG.sel, mode = valider.dataset.mode;
    CHG.sel = [];
    maj();
    try {
      if (mode === "perm") {
        const [x, y] = s.filter(v => v.role === "out");
        await rendre(await api(routePerm, {un: x.pid, deux: y.pid})); toast(t("chg.permutation_ok"));
      } else if (mode === "chg") {
        await rendre(await api(route, {sortant: s.find(v => v.role === "out").pid, entrant: s.find(v => v.role === "in").pid}));
        toast(t("chg.changement_ok"));
      }
    } catch (e) { toast(e.message); }
  }}, t("chg.choisis"));
  // Dans l'ordre du terrain lu de l'attaque vers le but : attaquants,
  // milieux, défenseurs, gardien — et dans une ligne, de gauche à droite
  // comme sur la pelouse.  L'ordre est fixé à la construction, pas à
  // chaque sondage : une liste qui se réordonne sous le curseur est pire
  // qu'une liste mal triée.  La fatigue se lit sur la barre.
  const rangLigne = j => ({FWD: 0, MID: 1, DEF: 2, GK: 3}[FAM_POSTE[j.slot || j.poste] || j.fam] ?? 1);
  const parLigne = gens => gens.map((j, i) => [j, i]).sort((x, y) => rangLigne(x[0]) - rangLigne(y[0]) || x[1] - y[1]).map(x => x[0]);
  choix.append(colonne(t("chg.sur_le_terrain"), parLigne([...surTerrain].reverse()), "out"), colonne(t("chg.sur_le_banc"), parLigne(banc), "in"));
  b.append(choix, valider);
  CHG.sel = [];
  CHG.maj = maj;
  CHG.refresh = dd => { majCompteur(dd, compteur, zoneBlessure, b); maj(); };
  CHG.refresh(d);
  return b;
}

// Ce qui bouge d'un sondage à l'autre, écrit DANS les nœuds existants.
function majCompteur(d, compteur, zoneBlessure, racine) {
  const m = d.match, cote = d.cote === "b" ? "b" : "a";
  const {endu, restants} = gensDuBanc(m, cote);
  compteur.textContent = t("chg.titre", {n: Math.max(0, restants)});
  const postes = m.postes?.[cote] || {};
  racine.querySelectorAll(".chg-j").forEach(n => {
    const j = n.querySelector(".endu");
    if (j) poserEndurance(j, endu[+n.dataset.pid]);
    // le poste qu'il tient MAINTENANT : un échange de postes le change
    const p = postes[+n.dataset.pid], sous = n.querySelector(".sous");
    if (p && sous) sous.textContent = (POSTE_COURT[p.slot] || p.slot || "") + (p.malus > 0 ? ` · −${p.malus}` : p.malus < 0 ? ` · +${-p.malus}` : "");
    const badge = n.querySelector(".fam");
    if (p && badge) badge.textContent = POSTE_ABBR[p.slot] || badge.textContent;
  });
  const etat = zoneBlessure.querySelector(".etat");
  if (etat) etat.textContent = m.pause ? t("chg.arrete_choisis") : t("chg.inferiorite");
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
  const p = el("div", {class: "panneau interne"}, el("h3", {class: "anton"}, t("ajuster.titre")),
    el("p", {class: "compteur"}, t("ajuster.texte")));
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
  // La boîte de dialogue (PLAN § 2.5) : parler à son équipe en français, la
  // phrase est traduite en un levier qu'on a déjà, et le coach confirme.
  p.append(boiteDialogue(routeTac.replace("tactique", "dire"), tac, rendre));
  p.append(selecteurTactique(tac, envoyer));
  // La formation change EN COURS DE MATCH : les onze restent sur le
  // terrain, on les redistribue sur les postes de la nouvelle forme
  // comme le fait le meilleur onze, et ceux qui se retrouvent hors de
  // leur poste le paient.
  const g = el("div", {class: "tac-groupe"}, el("span", {class: "tac-titre"}, t("ajuster.formation")));
  for (const f of Object.keys(RANGS))
    g.append(el("button", {class: "tac", "data-form": f,
      onclick: () => { tac.formation = f; envoyer(); }}, nomFormation(f)));
  p.append(el("div", {class: "tactiques"}, g));
  p.append(depliant("match", t("consignes.titre"),
    el("p", {class: "compteur"}, t("consignes.texte_match")),
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

// La boîte de dialogue : ce que tu dis, ce que le coach en fait.
function boiteDialogue(route, tac, rendre) {
  const fil = el("div", {class: "dialogue-fil"});
  const champ = el("input", {type: "text", maxlength: "160", placeholder: t("dialogue.exemples")});
  const dire = async () => {
    const texte = champ.value.trim();
    if (!texte) return;
    champ.value = "";
    fil.append(el("div", {class: "dit toi"}, texte));
    try {
      const rep = await api(route, {texte, tactique: {...tac}, langue: LANGUE === "xx" ? "fr" : LANGUE});
      // une règle du match qui refuse : traduite ici, comme une erreur de l'API
      const reponse = rep.code && existeT("err." + rep.code) ? t("err." + rep.code, rep.params) : rep.reponse;
      fil.append(el("div", {class: "dit coach" + (rep.compris ? "" : " non")}, reponse));
      if (rep.compris && rep.tactique) { Object.assign(tac, rep.tactique); AJU.attendu = {...tac}; }
      if (rep.etat) await rendre(rep.etat);
    } catch (e) { fil.append(el("div", {class: "dit coach non"}, e.message)); }
    while (fil.childElementCount > 12) fil.removeChild(fil.firstChild);
    fil.scrollTop = fil.scrollHeight;
  };
  champ.addEventListener("keydown", ev => { if (ev.key === "Enter") { ev.preventDefault(); dire(); } });
  return el("div", {class: "dialogue"},
    el("div", {class: "etiq"}, "🗣 " + t("dialogue.titre")),
    fil,
    el("div", {class: "dialogue-saisie"}, champ, el("button", {onclick: dire}, t("dialogue.dire"))));
}

// La causerie : seulement à la mi-temps, et seulement une fois.
const CAUSERIES = ["secouer", "rassurer", "feliciter"];

function majCauserie(d, routeTac, rendre) {
  const m = d.match, cote = d.cote === "b" ? "b" : "a";
  const z = AJU.causerie;
  if (!z) return;
  const dite = m.causerie?.[cote];
  const cest = m.pause && m.motif_pause === "mi-temps";
  if (dite && dite !== "rien") {
    z.replaceChildren(el("div", {class: "causerie dite"}, t(CAUSERIES.includes(dite) ? "causerie.dite." + dite : "causerie.dite.rien")));
    return;
  }
  if (!cest) { z.replaceChildren(); return; }
  const route = routeTac.replace("tactique", "causerie");
  const b = el("div", {class: "causerie"},
    el("div", {class: "etiq"}, "🗣 " + t("causerie.titre")),
    el("p", {class: "compteur"}, t("causerie.texte", {n: G.saison?.duree_causerie ?? 20})));
  const choix = el("div", {class: "tac-groupe"});
  for (const cle of CAUSERIES)
    choix.append(el("button", {class: "tac", title: t("causerie." + cle + ".aide"), onclick: async () => {
      try { await rendre(await api(route, {causerie: cle})); } catch (e) { toast(e.message); }
    }}, t("causerie." + cle)));
  choix.append(el("button", {class: "tac discret", onclick: async () => {
    try { await rendre(await api(route, {causerie: "rien"})); } catch (e) { toast(e.message); }
  }}, t("causerie.rien")));
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
  const g = el("div", {class: "tac-groupe"}, el("span", {class: "tac-titre"}, t("marquage.titre")));
  g.append(el("button", {class: "tac" + (!actuel ? " actif" : ""),
    onclick: () => { AJU.tac.marquage = 0; envoyerTac(d, routeTac, rendre); }}, t("marquage.personne")));
  for (const j of sur.filter(x => x.fam !== "GK").slice(0, 10))
    g.append(el("button", {class: "tac" + (actuel === j.pid ? " actif" : ""),
      title: `${j.nom} · ${j.slot || j.poste} · OVR ${j.ovr}`,
      onclick: () => { AJU.tac.marquage = j.pid; envoyerTac(d, routeTac, rendre); }},
      (j.nom || "").split(" ").slice(-1)[0]));
  z.replaceChildren(
    el("p", {class: "compteur"}, t("marquage.texte")),
    el("div", {class: "tactiques"}, g));
  if (paire) {
    const nom = pid => (tous.find(x => x.pid === pid)?.nom
      || [...(m.onze?.[cote] || []), ...(m.banc?.[cote] || [])].find(x => x.pid === pid)?.nom || "?");
    z.append(el("div", {class: "compteur"}, t("marquage.suit", {garde: nom(paire.garde), cible: nom(paire.cible)})));
  }
}

// Qui tire les penaltys et les corners : lu dans le onze, pas choisi.
// Le meilleur finisseur prend les penaltys, le meilleur créateur les
// corners, et ça change tout seul quand il sort.
function majTireurs(d) {
  const m = d.match, cote = d.cote === "b" ? "b" : "a";
  if (!AJU.tireurs) return;
  const tir = m.tireurs?.[cote];
  if (!tir) { AJU.tireurs.replaceChildren(); return; }
  const tous = [...(m.onze?.[cote] || []), ...(m.banc?.[cote] || [])];
  const nom = pid => (tous.find(x => x.pid === pid)?.nom || "—").split(" ").slice(-1)[0];
  AJU.tireurs.textContent = t("tireurs.texte", {penalty: nom(tir.penalty), corner: nom(tir.corner)});
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
    AJU.boutonPause.textContent = m.pause ? "▶ " + t("pause.reprendre") : "⏸ " + t("pause.mettre");
    AJU.boutonPause.className = m.pause ? "primaire" : "";
  }
}

const SM_MAX_CHG = 5;

function panneauHistorique(d) {
  const p = el("div", {class: "panneau"}, el("h3", {class: "anton"}, t("historique.titre")));
  if (!d.historique?.length) { p.append(el("p", {class: "compteur"}, t("historique.aucun"))); return p; }
  for (const h of d.historique)
    p.append(el("div", {class: "ligne simple"},
      el("span", {class: "res " + h.resultat}, h.resultat),
      el("div", {class: "qui"}, el("div", {class: "nom"}, h.adversaire), el("div", {class: "sous"}, h.defi ? t("historique.defi") : t("historique.classe"))),
      el("b", {class: "num"}, `${h.score[0]} – ${h.score[1]}`),
      el("span", {class: "compteur"}, h.elo === null ? "—" : (h.elo > 0 ? "+" : "") + h.elo)));
  return p;
}

// ---- journée ----
// La saison vivante : tes cartes sont de vrais joueurs, elles bougent avec leurs vrais
// matchs chaque semaine.  Ce panneau montre ce qui a bougé dans ton club à la dernière
// journée calculée, et la révélation de la semaine.  Une journée pas encore vue met un
// point sur l'onglet (mémorisé dans le navigateur).
function panneauSaisonVivante(v) {
  if (!v || !v.journee) return el("div", {class: "panneau vivante"}, el("h2", {class: "anton"}, t("journee.titre")),
    el("p", {class: "compteur"}, t("journee.aucune")));
  const j = v.journee, c = v.club;
  const p = el("div", {class: "panneau vivante"});
  p.append(el("div", {class: "tete"}, el("h2", {class: "anton"}, t("journee.la_journee_n", {n: j.numero})), el("span", {class: "compteur"}, t("journee.vrais_matchs_du", {du: dateFr(j.du), au: dateFr(j.au)}))));
  const chip = d => d === null || d === undefined ? el("span", {class: "delta nul"}, "—") : el("span", {class: "delta " + (d > 0 ? "plus" : d < 0 ? "moins" : "nul")}, d > 0 ? `+${d}` : String(d));
  p.append(el("div", {class: "recap"},
    el("div", {class: "tuile"}, el("div", {class: "etiq"}, t("journee.ton_club")), el("b", {class: "num"}, (c.total > 0 ? "+" : "") + c.total + " OVR")),
    el("div", {class: "tuile"}, el("div", {class: "etiq"}, t("journee.en_hausse")), el("b", {class: "num"}, String(c.hausses))),
    el("div", {class: "tuile"}, el("div", {class: "etiq"}, t("journee.en_baisse")), el("b", {class: "num"}, String(c.baisses))),
    el("div", {class: "tuile"}, el("div", {class: "etiq"}, t("journee.vrais_matchs")), el("b", {class: "num"}, String(c.matchs)))));
  const bouge = c.cartes.filter(x => x.delta || x.matchs.length).sort((a, b) => (b.delta || 0) - (a.delta || 0));
  const l = el("div", {class: "vivante-liste"});
  for (const x of bouge) {
    l.append(el("div", {class: "vivante-ligne", onclick: () => ouvrirFiche(x.player_id)},
      chip(x.delta),
      el("div", {class: "qui"}, el("b", {}, x.nom), el("span", {class: "compteur"}, ` · ${x.club || ""} · ${x.ovr_avant ?? "?"} → ${x.ovr ?? "?"}`)),
      el("div", {class: "notes"}, ...x.matchs.map(m => el("span", {class: "note " + (m.note >= 7 ? "b" : m.note < 5 ? "m" : ""), title: `${m.competition || ""} · ${m.date || ""}`},
        `${m.note == null ? "—" : f1(m.note)} · ${m.minutes}'${m.entrant ? " (" + t("journee.entre") + ")" : ""}`)))));
  }
  p.append(l.children.length ? l : el("p", {class: "compteur"}, t("journee.personne_joue")));
  if (v.revelations.length) {
    p.append(el("div", {class: "etiq", style: "margin-top:12px"}, t("journee.revelation")));
    p.append(el("div", {class: "vivante-liste"}, ...v.revelations.map(x => el("div", {class: "vivante-ligne", onclick: () => ouvrirFiche(x.player_id)}, chip(x.delta),
      el("div", {class: "qui"}, el("b", {}, x.nom), el("span", {class: "compteur"}, ` · ${x.club || ""} · ${x.ovr_avant} → ${x.ovr}`))))));
  }
  if (v.chutes.length) {
    p.append(el("div", {class: "etiq", style: "margin-top:12px"}, t("journee.chutes")));
    p.append(el("div", {class: "vivante-liste"}, ...v.chutes.map(x => el("div", {class: "vivante-ligne", onclick: () => ouvrirFiche(x.player_id)}, chip(x.delta),
      el("div", {class: "qui"}, el("b", {}, x.nom), el("span", {class: "compteur"}, ` · ${x.club || ""} · ${x.ovr_avant} → ${x.ovr}`))))));
  }
  try { localStorage.setItem("fl_journee_vue", String(j.numero)); } catch (e) {}
  majBadgeJournee(j.numero);
  return p;
}
function majBadgeJournee(numero) {
  const b = document.querySelector('#nav button[data-ecran="journee"]'); if (!b) return;
  let vue = 0; try { vue = +localStorage.getItem("fl_journee_vue") || 0; } catch (e) {}
  b.classList.toggle("nouveau", !!numero && numero > vue);
}
async function rendreJournee() {
  const P = $("#journee-pan"); P.replaceChildren();
  const j = G.saison.courante, d = G.saison.derniere;
  try { P.append(panneauSaisonVivante(await api("/journee/club"))); } catch (e) {}
  const res = await api("/resultats");
  const dernier = d && res.find(r => r.journee === d.numero);
  if (d && dernier) {
    const det = await api("/resultats/" + d.numero);
    P.append(el("div", {class: "tete"}, el("h2", {class: "anton"}, t("journee.journee_n", {n: d.numero})), el("span", {class: "compteur"}, t("journee.equipes_classees", {n: det.participants}))),
      el("div", {class: "gros num"}, f1(det.score)),
      el("div", {class: "recap"},
        el("div", {class: "tuile"}, el("div", {class: "etiq"}, t("journee.rang_journee")), el("b", {class: "num"}, `${det.rang}/${det.participants}`)),
        el("div", {class: "tuile"}, el("div", {class: "etiq"}, t("journee.gain")), el("b", {class: "num"}, fM(det.gain, true))),
        el("div", {class: "tuile"}, el("div", {class: "etiq"}, t("journee.entres_banc")), el("b", {class: "num"}, String(det.onze.filter(p => !(det.titulaires || []).includes(p)).length)))));
    if (det.detail.refusee) P.append(el("div", {class: "avert"}, t("journee.compo_refusee") + " " + det.detail.refusee));
    const tb0 = el("table"); tb0.append(el("thead", {}, el("tr", {}, el("th", {}, t("journee.joueur")), el("th", {}, t("journee.matchs_note_min")), el("th", {class: "num"}, t("statut.points")))));
    const tb = el("tbody");
    const lignes = det.onze.map(pid => ({pid, p: det.detail[String(pid)] ?? 0})).sort((a, b) => b.p - a.p);
    for (const {pid, p} of lignes) {
      const c = carte(pid); const pres = det.prestations[String(pid)] || [];
      tb.append(el("tr", {}, el("td", {}, el("b", {}, (c ? c.nom : "#" + pid))),
        el("td", {}, pres.length ? el("div", {class: "notes"}, ...pres.map(x => el("span", {class: "note " + (x.note >= 7 ? "b" : x.note < 5 ? "m" : ""), title: x.competition}, `${f1(x.note)} · ${Math.round(x.minutes)}'`))) : el("span", {class: "compteur"}, t("journee.pas_joue"))),
        el("td", {class: "num"}, f1(p))));
    }
    tb0.append(tb); P.append(el("div", {class: "tableau"}, tb0), el("hr", {style: "border:0;border-top:1px solid var(--ligne);margin:14px 0"}));
  } else if (d) {
    P.append(el("p", {class: "info"}, t("journee.calculee_sans_equipe", {n: d.numero})));
  }
  if (j) {
    P.append(el("div", {class: "tete"}, el("h2", {class: "anton"}, t("journee.journee_n", {n: j.numero})), el("span", {class: "compteur"}, t("journee.du_au", {du: dateFr(j.du), au: dateFr(j.au)}))));
    P.append(el("p", {class: "info"}, j.verrouillee
      ? el("span", {}, el("b", {}, t("journee.verrouillee")), " " + t("journee.verrouillee_texte"))
      : el("span", {}, t("journee.verrouillage") + " ", el("b", {}, new Date(j.cloture).toLocaleString(LOCALE)), ". ", G.equipe.composition ? t("journee.compo_envoyee") : t("journee.pas_de_compo"))));
  } else P.append(el("p", {class: "info"}, t("compo.saison_terminee")));
  const tb = $("#histo tbody"); tb.replaceChildren();
  for (const r of res) tb.append(el("tr", {}, el("td", {}, t("journee.j") + r.journee), el("td", {class: "num"}, f1(r.score)), el("td", {class: "num"}, fM(r.gain, true)), el("td", {class: "num"}, String(r.rang))));
}

// ---- classement et ligues ----
async function rendreClassement() {
  const cl = await api("/classement"); const tb = $("#classement tbody"); tb.replaceChildren();
  for (const r of cl) tb.append(el("tr", {class: r.equipe_id === G.equipe.equipe_id ? "moi" : ""}, el("td", {class: r.rang <= 3 ? "podium p" + r.rang : ""}, String(r.rang)), el("td", {}, r.equipe), el("td", {}, r.pseudo), el("td", {class: "num"}, f1(r.points)), el("td", {class: "num"}, r.derniere == null ? "—" : f1(r.derniere)), el("td", {class: "num"}, fM(r.patrimoine))));
  const L = $("#ligues"); L.replaceChildren();
  for (const l of await api("/ligues")) {
    const box = el("div", {class: "ligue"}, el("div", {class: "tete"}, el("h3", {class: "anton"}, l.nom), el("span", {class: "compteur"}, t("ligues.code_court") + " ", el("span", {class: "code"}, l.code))));
    const tab = el("table"); const b = el("tbody");
    for (const r of l.classement) b.append(el("tr", {class: r.equipe_id === G.equipe.equipe_id ? "moi" : ""}, el("td", {}, String(r.rang)), el("td", {}, r.equipe), el("td", {class: "num"}, f1(r.points))));
    tab.append(b); box.append(el("div", {class: "tableau"}, tab)); L.append(box);
  }
}
$("#btn-creer-ligue").addEventListener("click", async () => { try { const r = await api("/ligues", {nom: $("#ligue-nom").value}); toast(t("ligues.creee", {code: r.code})); $("#ligue-nom").value = ""; rendreClassement(); } catch (e) { toast(e.message); } });
$("#btn-rejoindre-ligue").addEventListener("click", async () => { try { const r = await api("/ligues/rejoindre", {code: $("#ligue-code").value}); toast(t("ligues.rejointe", {nom: r.nom})); $("#ligue-code").value = ""; rendreClassement(); } catch (e) { toast(e.message); } });

// ---- le compte : le palier, ses limites, la boutique (PLAN § 5) ----
async function rendreCompte() {
  const P = $("#compte-pan"), B = $("#compte-boutique"); P.replaceChildren(); B.replaceChildren();
  const c = await api("/compte");
  const premium = c.palier === "premium";
  P.append(el("h2", {class: "anton"}, t("compte.titre")),
    el("div", {class: "recap"},
      el("div", {class: "tuile"}, el("div", {class: "etiq"}, t("compte.palier")), el("b", {class: "num"}, premium ? t("compte.premium") : t("compte.gratuit"))),
      el("div", {class: "tuile"}, el("div", {class: "etiq"}, t("compte.matchs_jour")), el("b", {class: "num"}, c.limites ? `${c.matchs_joues} / ${c.matchs_jour === null ? "∞" : c.matchs_jour}` : "∞")),
      el("div", {class: "tuile"}, el("div", {class: "etiq"}, t("compte.encheres")), el("b", {class: "num"}, c.limites ? `${c.encheres_en_cours} / ${c.encheres}` : "∞")),
      el("div", {class: "tuile"}, el("div", {class: "etiq"}, t("compte.packs_jour")), el("b", {class: "num"}, c.packs_jour.map(x => tierTxt(x)).join(" + ")))));
  if (premium && c.premium_jusqua) P.append(el("p", {class: "info"}, t("compte.premium_jusqua", {date: new Date(c.premium_jusqua).toLocaleDateString(LOCALE)})));
  P.append(el("p", {class: "compteur"}, c.limites ? t("compte.limites_texte") : t("compte.sans_limites")));
  P.append(el("p", {class: "compteur"}, t("compte.email_texte", {email: c.email || t("compte.aucun_email")})));
  if (c.mineur) P.append(el("p", {class: "avert"}, t("compte.mineur")));
  B.append(el("h2", {class: "anton"}, t("boutique.titre")),
    el("p", {class: "compteur"}, t("boutique.texte")));
  if (c.paiement === "manuel") B.append(el("p", {class: "info"}, t("boutique.fermee")));
  const L = el("div", {class: "offerts-liste"});
  for (const p of c.catalogue) {
    L.append(el("div", {class: "offert " + (p.type === "premium" ? "or" : "argent")},
      el("b", {class: "anton"}, p.type === "premium" ? t("produit." + p.produit) : t("produit." + p.produit)),
      el("span", {class: "compteur"}, p.prix.toLocaleString(LOCALE, {style: "currency", currency: "EUR"})),
      el("button", {class: "primaire", disabled: c.paiement === "manuel" || c.mineur, onclick: async () => {
        try { const r = await api("/paiement/session", {produit: p.produit}); if (r.url) location.href = r.url; } catch (e) { toast(e.message); }
      }}, t("boutique.acheter"))));
  }
  B.append(L);
  if (c.achats?.length) {
    B.append(el("div", {class: "etiq", style: "margin-top:12px"}, t("boutique.achats")));
    for (const a of c.achats) B.append(el("div", {class: "ligne simple"}, el("div", {class: "qui"}, el("div", {class: "nom"}, t("produit." + a.produit)), el("div", {class: "sous"}, new Date(a.le).toLocaleString(LOCALE))),
      el("b", {class: "num"}, a.montant.toLocaleString(LOCALE, {style: "currency", currency: "EUR"}))));
  }
  const q = new URLSearchParams(location.search).get("paiement");
  if (q) { toast(q === "ok" ? t("boutique.merci") : t("boutique.annule")); history.replaceState(null, "", location.pathname + location.hash); }
}

// ---- admin ----
async function rendreAdmin() {
  const A = $("#admin-etat"); A.replaceChildren();
  const e = await api("/admin/etat");
  const cour = G.saison.courante;
  A.append(el("p", {class: "info"}, t("admin.etat", {cartes: e.cartes, equipes: e.equipes, reguliers: e.bareme?.reguliers ?? "?", mu: e.bareme?.mu ?? 65, sigma: e.bareme?.sigma ?? 10, borne: e.bareme?.borne ?? 10})));
  const js = el("div", {class: "journees"});
  for (const j of e.journees.filter(x => x.numero >= 1)) js.append(el("span", {class: j.calculee ? "ok" : (cour && cour.numero === j.numero ? "cour" : ""), title: `${j.du} → ${j.au}`}, t("journee.j") + j.numero));
  A.append(js);
  if (!cour) { A.append(el("p", {class: "info"}, t("admin.toutes_calculees"))); return; }
  A.append(el("h3", {class: "anton", style: "margin-top:14px"}, `${t("journee.journee_n", {n: cour.numero})} · ${cour.verrouillee ? t("admin.verrouillee") : t("admin.ouverte")}`),
    el("p", {class: "compteur"}, t("admin.fenetre", {du: cour.du, au: cour.au, cloture: new Date(cour.cloture).toLocaleString(LOCALE)})));
  const acts = el("div", {class: "admin-actions"});
  acts.append(el("button", {onclick: async () => { await api(`/admin/journee/${cour.numero}/verrouiller`, {}); toast(t("admin.verrouillee_toast")); montrer("admin"); }}, t("admin.verrouiller")));
  acts.append(el("button", {onclick: async () => { await api(`/admin/journee/${cour.numero}/ouvrir`, {}); toast(t("admin.rouverte_toast")); montrer("admin"); }}, t("admin.rouvrir")));
  const fichier = el("input", {type: "file", accept: ".json"});
  acts.append(el("label", {class: "case"}, t("admin.prestations_json") + " ", fichier),
    el("button", {onclick: async () => {
      if (!fichier.files[0]) { toast(t("admin.choisis_fichier")); return; }
      const fd = new FormData(); fd.append("fichier", fichier.files[0]);
      const r = await fetch(`/api/admin/journee/${cour.numero}/prestations`, {method: "POST", body: fd});
      const d = await r.json(); toast(r.ok ? t("admin.prestations_chargees", {n: d.prestations}) : ((d.detail && d.detail.message) || d.detail || t("admin.echec")));
    }}, t("admin.charger")));
  acts.append(el("button", {class: "primaire", onclick: async () => {
      if (!confirm(t("admin.cloturer_confirmer", {n: cour.numero}))) return;
      try { const r = await api(`/admin/journee/${cour.numero}/calculer`, {}); toast(t("admin.calculee_toast", {n: cour.numero, equipes: r.equipes, cartes: r.cartes_bougees})); await montrer("admin"); }
      catch (err) { toast(err.message); }
    }}, t("admin.cloturer", {n: cour.numero})));
  A.append(acts, el("p", {class: "compteur"}, t("admin.ordre_normal")));
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
for (const id of ["club-poste", "club-tri"]) $("#" + id).addEventListener("change", () => rendreClub());
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
    b.append(el("div", {class: "etiq"}, t("profil.titre")),
      el("p", {class: "compteur"}, t("profil.aucune_preference")));
    return b;
  }
  b.append(el("div", {class: "etiq"}, t("profil.titre")));
  b.append(el("p", {class: "compteur"}, t("profil.texte", {pct: Math.round(AISE.max * 100)})));
  const l = el("div", {class: "profil-listes"});
  if (lu.aise.length) l.append(el("div", {class: "profil-col aise"},
    el("div", {class: "t"}, t("profil.a_laise")),
    ...lu.aise.map(x => el("div", {class: "profil-item"}, el("span", {}, x.texte),
      el("b", {}, (x.score > 0 ? "+" : "") + x.score.toFixed(1))))));
  if (lu.gene.length) l.append(el("div", {class: "profil-col gene"},
    el("div", {class: "t"}, t("profil.moins_a_laise")),
    ...lu.gene.map(x => el("div", {class: "profil-item"}, el("span", {}, x.texte),
      el("b", {}, x.score.toFixed(1))))));
  b.append(l);
  // et avec TA tactique de départ ?
  if (Object.keys(AFFINITES).length) {
    const a = aiseDe(d.profil, d.postes?.[0] || d.poste, LOBBY.tac);
    const pct = AISE.max * Math.max(-1, Math.min(1, a / AISE.z)) * 100;
    b.append(el("div", {class: "profil-tien " + (pct > 1 ? "bon" : pct < -1 ? "mauvais" : "")},
      Math.abs(pct) < 1 ? t("profil.a_son_niveau")
        : t(pct > 0 ? "profil.au_dessus" : "profil.en_dessous", {pct: (pct > 0 ? "+" : "") + pct.toFixed(0)})));
  }
  return b;
}

async function ouvrirFiche(id) {
  let d; try { d = await api("/cartes/" + id); } catch (e) { toast(e.message); return; }
  const dlg = $("#fiche"); dlg.replaceChildren();
  const box = el("div", {class: "fiche fiche-carte"});
  const img = el("img", {class: "carte-img", src: `/images/cartes/${id}.png?ovr=${d.ovr}`, alt: t("fiche.carte_de", {nom: d.nom})});
  img.addEventListener("error", () => img.remove());
  const cote = el("div", {class: "fiche-cote"});
  cote.append(el("div", {class: "etiq"}, `${d.club} · ${d.ligue}`), el("h3", {class: "anton"}, d.nom),
    el("div", {class: "fiche-ligne"}, el("span", {class: "fam " + d.fam}, POSTE_ABBR[d.poste] || FAM_COURT[d.fam]), el("span", {}, `${POSTE_COURT[d.poste] || d.poste} · ${t("slot.a_tenu", {codes: codesDe(d)})}`), d.age ? el("span", {title: d.naissance ? t("fiche.ne_le", {date: dateFr(d.naissance)}) : ""}, `· ${ageTxt(d)}${d.naissance ? " (" + dateFr(d.naissance) + ")" : ""}`) : null, d.pays ? el("span", {title: d.pays}, `· ${drapeau(d.pays)} ${d.pays}`) : null, d.numero ? el("span", {}, `· n° ${d.numero}`) : null,
      el("span", {}, "·"), piedsDe(d)),
    el("div", {class: "compteur"}, `${t("fiche.matchs_min", {matchs: d.matchs, minutes: d.minutes})} · ${t("carte.part_equipes", {pct: Math.round(d.part * 100)})}`),
    el("div", {style: "display:flex;gap:14px;align-items:baseline;margin-top:6px"}, el("div", {class: "ovr num" + (d.ovr >= 80 ? " haut" : ""), style: "font-size:40px"}, String(d.ovr), tendance(d)), el("div", {class: "prix num", style: "font-size:22px"}, fM(d.prix)),
      d.potentiel ? el("div", {class: "potentiel", title: t("fiche.potentiel_titre")}, el("span", {class: "etiq"}, t("fiche.potentiel")), el("b", {class: "num"}, String(d.potentiel))) : null));
  const dep = d.valeur_base != null ? t("fiche.a_ovr", {valeur: fM(d.valeur_base), ovr: d.ovr_base}) : "—";
  cote.append(el("div", {class: "compteur", style: "margin-top:6px"}, `${t("fiche.depart_saison")} ${dep}`),
    el("div", {class: "compteur"}, d.valeur_marche != null ? t("fiche.valeur_marche", {valeur: fM(d.valeur_marche)}) : t("fiche.valeur_inconnue")),
    el("div", {class: "compteur"}, t("fiche.ovr_texte")));
  box.append(el("div", {class: "fiche-haut"}, img, cote));
  const axes = d.fam === "GK" ? AXES.gardien : AXES.champ; const A = el("div", {class: "attrs"});
  for (const ax of axes) { const val = d.attributs[ax] ?? 40; A.append(el("div", {class: "attr"}, el("span", {}, (d.poste === "Gardien" && ATTR_NOMS_GARDIEN[ax]) || ATTR_NOMS[ax]), el("div", {class: "jauge"}, el("i", {class: val >= 80 ? "haut" : "", style: `width:${(val - 40) / 59 * 100}%`})), el("b", {class: "num"}, String(val)))); }
  box.append(el("div", {class: "etiq"}, t("fiche.attributs")), A);
  box.append(blocPhysique(d));
  box.append(blocProfil(d));
  box.append(el("div", {class: "etiq"}, t("fiche.prestations")), el("div", {class: "notes"}, ...(d.prestations.length ? d.prestations.slice(0, 8).map(p => el("span", {class: "note " + (p.note >= 7 ? "b" : p.note < 5 ? "m" : ""), title: `${t("journee.j")}${p.numero} · ${p.competition}`}, `${f1(p.note)} · ${Math.round(p.minutes)}'${faits(p)}`)) : [el("span", {class: "compteur"}, t("fiche.aucun_match"))])));
  if (d.historique.length > 1) box.append(el("div", {class: "etiq", style: "margin-top:10px"}, t("fiche.prix_journee")), sparkline(d.historique.map(h => h.prix), fM));
  const acts = el("div", {class: "actions"});
  const nv = ventesDe(id).length;
  if (G.equipe.effectif[id]) { const dl = d.prix - G.equipe.effectif[id]; acts.append(el("span", {class: "compteur", style: "margin-right:auto"}, `${t("fiche.dans_effectif")} · ${t("carte.achete")} ${fM(G.equipe.effectif[id])} · ${fM(dl, true)}`)); }
  acts.append(el("button", {class: "achat" + (nv ? " primaire" : ""), disabled: !nv, onclick: () => { dlg.close(); allerAuxVentes(id); }}, nv ? t("vente.en_cours_n", {n: nv}) : t("vente.aucune_en_cours")));
  acts.append(el("button", {onclick: () => { dlg.close(); ouvrirDetail(id); }}, t("fiche.detail_stats")));
  acts.append(el("button", {class: "discret", onclick: () => dlg.close()}, t("fermer")));
  box.append(acts); dlg.append(box); dlg.showModal();
}

// ---------------------------------------------------------------------------
// Where the numbers come from.  Every line is a step the card really went
// through (jeu/bareme.py), with the figure it produced: the card's OVR and
// its six attributes are the last line of each chain, not a second opinion.
// ---------------------------------------------------------------------------
const pc = v => Math.round(v * 100) + " %";
const f2 = v => (Math.round(v * 100) / 100).toLocaleString(LOCALE, {minimumFractionDigits: 2, maximumFractionDigits: 2});
// "100 %" reads as if he were the only one; the place says it better.
function place(rang, n) {
  const k = Math.max(1, Math.round((1 - rang) * n));
  return `≈ ${t("solo.rang_sur", {rang: ordinal(k), sur: n})}`;
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
  box.append(el("h3", {class: "anton"}, t("detail.titre", {nom: d.nom})),
    el("p", {class: "compteur"}, t("detail.texte")));

  // --- the OVR ---
  const dep = d.depart, sa = d.saison;
  const o = el("div", {class: "chaine"});
  o.append(el("div", {class: "etiq"}, t("detail.1_depart") + (d.source ? " — " + t("detail.bareme") + " " + d.source : "")));
  o.append(etape(t("detail.bareme_brut"), `${f2(dep.terrain.points)} pts`, t("detail.sur_min", {n: Math.round(dep.terrain.minutes)})));
  o.append(etape(t("detail.par_90"), f2(dep.terrain.par90)));
  o.append(etape(t("detail.mediane_poste"), f2(dep.terrain.retreci),
    t("detail.mediane_note", {mediane: f2(dep.terrain.prior), poids: pc(dep.terrain.poids), k: dep.terrain.k})));
  o.append(etape(t("detail.corrige_role"), f2(dep.terrain.s),
    t("detail.role_note", {tit: Math.round(dep.terrain.titularisations), feuilles: Math.round(dep.terrain.feuilles), part: pc(dep.terrain.part_role), ref: pc(dep.terrain.role_ref)})));
  o.append(etape(t("detail.total"), f2(dep.t),
    t("detail.total_note", {pt: pc(dep.part_terrain), t: f2(dep.t_terrain), pp: pc(1 - dep.part_terrain), p: f2(dep.t_palmares)})));
  o.append(etape(t("detail.ovr_depart"), String(dep.ovr), `${place(dep.rang, d.reguliers)} ${t("detail.reguliers")}`));
  o.append(el("div", {class: "etiq"}, t("detail.2_saison")));
  if (!sa.terrain.minutes || sa.fenetre.min === 0)
    o.append(el("p", {class: "compteur"}, t("detail.aucune_journee")));
  else
    o.append(etape(t("detail.bareme_saison"), `${f2(sa.fenetre.pts)} pts`,
      t("detail.saison_note", {min: Math.round(sa.fenetre.min), tit: Math.round(sa.fenetre.tit), poids: pc(sa.poids_passe)})));
  o.append(etape(t("detail.niveau_lu"), f2(sa.lecture), t("detail.contre_depart", {valeur: f2(sa.lecture_depart)})));
  o.append(etape(t("detail.mouvement"), (sa.mouvement > 0 ? "+" : "") + f2(sa.mouvement),
    Math.abs(sa.mouvement_brut) > sa.borne ? t("detail.ramene_limite", {n: sa.borne}) : t("detail.limite", {n: sa.borne})));
  o.append(etape(t("detail.ovr_carte"), String(sa.ovr), null));
  box.append(o);

  // --- the six attributes ---
  box.append(el("div", {class: "etiq", style: "margin-top:14px"}, t("detail.3_attributs")),
    el("p", {class: "compteur"}, t("detail.attributs_texte")));
  for (const a of d.axes) {
    const nom = (gk && ATTR_NOMS_GARDIEN[a.axe]) || ATTR_NOMS[a.axe];
    const det = el("details", {class: "axe-detail"});
    det.append(el("summary", {},
      el("span", {class: "lib"}, nom),
      el("div", {class: "jauge"}, el("i", {class: a.valeur >= 80 ? "haut" : "", style: `width:${(a.valeur - 40) / 59 * 100}%`})),
      el("b", {class: "num"}, String(a.valeur))));
    const c = el("div", {class: "chaine interne"});
    c.append(etape(t("detail.points_axe"), f2(a.points), t("detail.soit_par_90", {n: f2(a.par90)})));
    c.append(etape(t("detail.mediane_poste"), f2(a.retreci),
      t("detail.mediane_note_court", {mediane: f2(a.prior), poids: pc(a.poids)})));
    c.append(etape(t("detail.classement"), place(a.rang, d.reguliers), t("detail.parmi_reguliers", {valeur: a.valeur})));
    if (a.actions.length) {
      c.append(el("div", {class: "etiq"}, t("detail.actions_comptees")));
      const tab = el("div", {class: "actions-axe"});
      for (const ac of a.actions)
        tab.append(el("div", {}, el("span", {}, ac.nom),
          el("b", {class: "num"}, Number.isInteger(ac.total) ? String(ac.total) : f2(ac.total)),
          el("span", {class: "compteur"}, f2(ac.par90) + " / 90")));
      c.append(tab);
    }
    c.append(el("p", {class: "compteur"}, t("detail.lignes_bareme") + " " + a.cles.join(", ")));
    det.append(c);
    box.append(det);
  }
  const acts = el("div", {class: "actions"});
  acts.append(el("button", {onclick: () => { dlg.close(); ouvrirFiche(id); }}, t("detail.retour_fiche")),
    el("button", {class: "discret", onclick: () => dlg.close()}, t("fermer")));
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
  await chargerLangue(langueChoisie());
  appliquerLangue();
  try {
    const s = await api("/saison"); TAILLE = s.taille_effectif; BANC_MAX = s.taille_banc ?? BANC_MAX;
    FORMATIONS = s.formations; LIMITES = s.limites;
    if (s.formations_rangs) RANGS = s.formations_rangs;
    if (s.familles_poste) FAM_POSTE = s.familles_poste;
    if (s.malus_postes) MALUS_POSTES = s.malus_postes;
    if (s.malus_gardien) MALUS_GK = s.malus_gardien;
    if (s.profondeur_poste) PROF_POSTE = s.profondeur_poste;
    if (s.poids_postes) POIDS_POSTES = s.poids_postes;
    if (s.bonus_poste_max != null) BONUS_POSTE_MAX = s.bonus_poste_max;
    if (s.part_distance != null) PART_DISTANCE = s.part_distance;
    if (s.part_ecart != null) PART_ECART = s.part_ecart;
    if (s.codes_poste) POSTE_ABBR = s.codes_poste;
    if (s.libelles_formation) LIBELLES_FORMATION = s.libelles_formation;
    if (s.affinites) AFFINITES = s.affinites;
    if (s.aise) AISE = s.aise;
    const moi = await api("/moi"); connecte(moi);
    if (moi.cadeau) toast(moi.cadeau.bonus
      ? t("cadeau.serie", {tier: tierTxt(moi.cadeau.bonus), n: moi.cadeau.serie})
      : (moi.cadeau.packs || []).length > 1 ? t("cadeau.premium", {packs: moi.cadeau.packs.map(x => tierTxt(x)).join(" + ")})
      : t(moi.cadeau.serie > 1 ? "cadeau.jour_serie" : "cadeau.jour", {tier: tierTxt(moi.cadeau.pack), n: moi.cadeau.serie}));
    if (moi.connecte) { const h = location.hash.replace("#", ""); await montrer(["packs", "encheres", "marche", "equipe", "lobby", "solo", "journee", "classement", "compte", "admin"].includes(h) ? h : (idsEffectif().length ? "equipe" : "packs")); }
    else await remiseDepuisLien();
  } catch (e) { toast(t("serveur_injoignable", {detail: e.message})); }
})();

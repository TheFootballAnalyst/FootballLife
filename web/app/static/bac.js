// Le bac à sable du moteur B : on rejoue une trace de positions.
//
// Le serveur joue le match (jeu/emergent.py) et renvoie une image toutes
// les 0,4 s : le ballon (x, y, z) et les vingt-deux (x, y), en décimètres.
// Ici on interpole entre deux images et on dessine sur un canvas.  Rien
// n'est décidé côté page : elle regarde.
const $ = s => document.querySelector(s);
const LONG = 105, LARG = 68;
const BAC = {res: null, i: 0, joue: false, vitesse: 4, horloge: 0, derniere: 0, noms: {}};

async function clubs() {
  const r = await fetch("/api/bac/clubs"); const d = await r.json();
  for (const id of ["club-a", "club-b"]) {
    const sel = $("#" + id); sel.replaceChildren();
    for (const c of d.clubs) { const o = document.createElement("option"); o.value = c.team_id; o.textContent = `${c.nom} (${c.ovr})`; sel.append(o); }
  }
  if (d.clubs.length > 1) $("#club-b").selectedIndex = 1;
  for (const id of ["club-a", "club-b"]) $("#" + id).addEventListener("change", profils);
  await profils();
}

// La tactique par défaut de chaque club vient de sa possession réelle sur la
// saison (un club qui a le ballon joue en possession, bloc haut, relance
// courte) ; on peut toujours la changer à la main avant de jouer.
async function profils() {
  try {
    const r = await fetch(`/api/bac/profil?a=${$("#club-a").value}&b=${$("#club-b").value}`); const d = await r.json();
    for (const [c, p] of [["a", d.a], ["b", d.b]]) {
      for (const k of ["bloc", "tempo", "risque", "relance"]) $(`#${k}-${c}`).value = p[k];
      const e = $(`#profil-${c}`);
      if (e) e.textContent = p.possession != null ? `possession réelle ${Math.round(p.possession * 100)} %` : "pas de match joué";
    }
  } catch (e) { /* le bac joue avec les réglages affichés */ }
}

async function jouer() {
  const a = $("#club-a").value, b = $("#club-b").value;
  const q = new URLSearchParams({a, b, formation: $("#formation").value, minutes: $("#minutes").value, graine: $("#graine").value,
    bloc_a: $("#bloc-a").value, tempo_a: $("#tempo-a").value, risque_a: $("#risque-a").value, relance_a: $("#relance-a").value,
    bloc_b: $("#bloc-b").value, tempo_b: $("#tempo-b").value, risque_b: $("#risque-b").value, relance_b: $("#relance-b").value});
  if ($("#coll-a").value !== "") q.set("collectif_a", $("#coll-a").value);
  if ($("#coll-b").value !== "") q.set("collectif_b", $("#coll-b").value);
  $("#jouer").disabled = true; $("#etat").textContent = "Le match se joue… (six secondes pour 90 minutes)";
  try {
    const r = await fetch("/api/bac/match?" + q); if (!r.ok) throw new Error(await r.text());
    charger(await r.json());
    $("#etat").textContent = "";
  } catch (e) { $("#etat").textContent = "Raté : " + e.message; }
  $("#jouer").disabled = false;
}

function charger(res) {
  BAC.res = res; BAC.i = 0; BAC.horloge = 0; BAC.joue = true; BAC.derniere = performance.now();
  TERRAIN.charger(res, res.maillots); BAC.noms = TERRAIN.noms;
  $("#nom-a").textContent = res.noms[0]; $("#nom-b").textContent = res.noms[1];
  $("#curseur").max = res.trace.length - 1; $("#curseur").value = 0;
  $("#lecture").textContent = "⏸";
  // le fil
  const fil = $("#fil"); fil.replaceChildren();
  const LIB = {but: "BUT", tir: "Frappe", arret: "Arrêt", rate: "À côté", contre: "Contré", faute: "Faute", corner: "Corner",
    penalty: "Penalty", horsjeu: "Hors-jeu", mi_temps: "Mi-temps", fin: "Fin du match", additionnel: "Temps additionnel", carton: "Carton",
    percee: "Percée balle au pied", passe: "Passe en profondeur", provoque: "Provoque son vis-à-vis", crochet: "Crochet",
    seul: "Seul face au gardien", tacle: "Tacle"};
  for (const e of res.evenements) {
    if (!LIB[e.k]) continue;
    if (e.k === "faute" && !e.carton) continue;
    if (e.k === "passe" && !e.prof) continue;
    const d = document.createElement("div"); d.className = e.k;
    const qui = e.de != null ? BAC.noms[e.camp + ":" + e.de] || "" : "";
    let txt = LIB[e.k] + (qui ? " · " + qui : "");
    if (e.k === "but") txt += ` (${e.score[0]}–${e.score[1]})` + (e.xg != null ? ` · xG ${e.xg}` : "");
    if (e.k === "tir") txt += ` · ${e.d} m · xG ${e.xg}` + (e.tete ? " · de la tête" : e.pied ? ` · pied ${e.pied === "G" ? "gauche" : "droit"}` : "") + (e.penalty ? " · penalty" : "");
    if (e.k === "provoque") txt += e.rentre ? " · rentre sur son bon pied" : " · déborde";
    if (e.k === "faute" && e.carton) txt += " · carton " + e.carton;
    if (e.k === "passe") txt += " → " + (BAC.noms[e.camp + ":" + e.a] || "") + ` · ${e.d} m`;
    d.innerHTML = `<small>${e.lib || e.minute}'</small>` + txt;
    fil.append(d);
  }
  // les stats
  const st = res.stats, S = $("#stats"); S.replaceChildren();
  const tuile = (l, v) => { const d = document.createElement("div"); d.className = "stat"; d.innerHTML = `<b>${v}</b><span>${l}</span>`; S.append(d); };
  if (res.collectif) tuile("Collectif", `${Math.round(res.collectif[0] * 100)} – ${Math.round(res.collectif[1] * 100)} %`);
  if (res.affinite) tuile("Affinité au style", `${Math.round(res.affinite[0] * 100)} – ${Math.round(res.affinite[1] * 100)} %`);
  tuile("Possession", `${Math.round(res.possession[0] * 100)} – ${Math.round(res.possession[1] * 100)} %`);
  tuile("Tirs (cadrés)", `${st.tirs[0]} (${st.cadres[0]}) – ${st.tirs[1]} (${st.cadres[1]})`);
  tuile("xG", `${st.xg[0]} – ${st.xg[1]}`);
  tuile("Passes (réussies)", `${st.passes[0]} (${st.passes_ok[0]}) – ${st.passes[1]} (${st.passes_ok[1]})`);
  tuile("Corners", `${st.corners[0]} – ${st.corners[1]}`);
  tuile("Fautes", `${st.fautes[0]} – ${st.fautes[1]}`);
  tuile("Hors-jeu", `${st.horsjeu[0]} – ${st.horsjeu[1]}`);
  tuile("Tacles", `${st.tacles[0]} – ${st.tacles[1]}`);
  // les joueurs
  const J = $("#joueurs"); J.replaceChildren();
  const t = document.createElement("table");
  t.innerHTML = "<tr><th>Joueur</th><th>km</th><th>sprint</th><th>pointe</th><th>EA</th><th title='volume · pressing · récupération, rang dans son poste'>V·P·R</th><th>touches</th><th>passes</th><th>tirs</th></tr>";
  for (const j of res.joueurs) {
    const tr = document.createElement("tr"); tr.className = j.camp === 0 ? "a" : "b";
    tr.innerHTML = `<td>${j.nom.split(" ").slice(-1)[0]}${j.capitaine ? " <b style='color:#ffd86b'>C</b>" : ""} <small>${j.poste.split(" ")[0]}</small></td><td>${(j.distance / 1000).toFixed(1)}</td><td>${j.sprint}</td><td>${j.vmax_kmh}</td><td>${j.vmax_ea ?? "—"}</td><td>${j.travail ? j.travail.map(v => Math.round(v * 9)).join("") : "—"}</td><td>${j.touches}</td><td>${j.passes_ok}/${j.passes}</td><td>${j.buts ? j.buts + "⚽ " : ""}${j.cadres}/${j.tirs}</td>`;
    t.append(tr);
  }
  J.append(t);
  dessiner();
}

// -- le dessin : le terrain partagé (terrain_b.js)
const c = $("#c");
const TERRAIN = new TerrainB(c);
function fond() { TERRAIN.fond(); }
function dessiner() {
  if (!BAC.res) { TERRAIN.fond(); return; }
  const r = TERRAIN.dessiner(BAC.i);
  const t = r.t, m = Math.floor(t / 60);
  $("#min").textContent = `${m}'`;
  $("#score").textContent = `${r.score[0]} – ${r.score[1]}`;
  $("#curseur").value = Math.floor(BAC.i);
}
function boucle(now) {
  if (BAC.res && BAC.joue) {
    const dt = (now - BAC.derniere) / 1000;
    BAC.i += dt * BAC.vitesse / BAC.res.trace_pas;
    // les temps morts (touche, coup franc, célébration) se sautent : on
    // avance jusqu'aux deux dernières secondes de l'arrêt
    if ($("#sauter").checked) {
      const tr = BAC.res.trace; let k = Math.floor(BAC.i);
      if (tr[k] && tr[k][4] === 1) {
        let fin = k; while (fin < tr.length - 1 && tr[fin][4] === 1) fin++;
        if (fin - k > 5) BAC.i = fin - 5;
      }
    }
    if (BAC.i >= BAC.res.trace.length - 1) { BAC.i = BAC.res.trace.length - 1; BAC.joue = false; $("#lecture").textContent = "▶"; }
    dessiner();
  }
  BAC.derniere = now;
  requestAnimationFrame(boucle);
}
$("#lecture").addEventListener("click", () => { if (!BAC.res) return; if (!BAC.joue && BAC.i >= BAC.res.trace.length - 1) BAC.i = 0; BAC.joue = !BAC.joue; $("#lecture").textContent = BAC.joue ? "⏸" : "▶"; });
$("#vitesse").addEventListener("change", e => BAC.vitesse = +e.target.value);
$("#curseur").addEventListener("input", e => { BAC.i = +e.target.value; dessiner(); });
$("#jouer").addEventListener("click", jouer);
fond();
clubs();
requestAnimationFrame(boucle);

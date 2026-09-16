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
  BAC.noms = {}; for (const j of res.joueurs) BAC.noms[j.camp + ":" + j.pid] = j.nom.split(" ").slice(-1)[0];
  $("#nom-a").textContent = res.noms[0]; $("#nom-b").textContent = res.noms[1];
  $("#curseur").max = res.trace.length - 1; $("#curseur").value = 0;
  $("#lecture").textContent = "⏸";
  // le fil
  const fil = $("#fil"); fil.replaceChildren();
  const LIB = {but: "BUT", tir: "Frappe", arret: "Arrêt", rate: "À côté", contre: "Contré", faute: "Faute", corner: "Corner",
    penalty: "Penalty", horsjeu: "Hors-jeu", mi_temps: "Mi-temps", fin: "Fin du match", carton: "Carton",
    percee: "Percée balle au pied", passe: "Passe en profondeur"};
  for (const e of res.evenements) {
    if (!LIB[e.k]) continue;
    if (e.k === "faute" && !e.carton) continue;
    if (e.k === "passe" && !e.prof) continue;
    const d = document.createElement("div"); d.className = e.k;
    const qui = e.de != null ? BAC.noms[e.camp + ":" + e.de] || "" : "";
    let txt = LIB[e.k] + (qui ? " · " + qui : "");
    if (e.k === "but") txt += ` (${e.score[0]}–${e.score[1]})` + (e.xg != null ? ` · xG ${e.xg}` : "");
    if (e.k === "tir") txt += ` · ${e.d} m · xG ${e.xg}` + (e.tete ? " · de la tête" : "") + (e.penalty ? " · penalty" : "");
    if (e.k === "faute" && e.carton) txt += " · carton " + e.carton;
    if (e.k === "passe") txt += " → " + (BAC.noms[e.camp + ":" + e.a] || "") + ` · ${e.d} m`;
    d.innerHTML = `<small>${e.minute}'</small>` + txt;
    fil.append(d);
  }
  // les stats
  const st = res.stats, S = $("#stats"); S.replaceChildren();
  const tuile = (l, v) => { const d = document.createElement("div"); d.className = "stat"; d.innerHTML = `<b>${v}</b><span>${l}</span>`; S.append(d); };
  if (res.collectif) tuile("Collectif", `${Math.round(res.collectif[0] * 100)} – ${Math.round(res.collectif[1] * 100)} %`);
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
    tr.innerHTML = `<td>${j.nom.split(" ").slice(-1)[0]} <small>${j.poste.split(" ")[0]}</small></td><td>${(j.distance / 1000).toFixed(1)}</td><td>${j.sprint}</td><td>${j.vmax_kmh}</td><td>${j.vmax_ea ?? "—"}</td><td>${j.travail ? j.travail.map(v => Math.round(v * 9)).join("") : "—"}</td><td>${j.touches}</td><td>${j.passes_ok}/${j.passes}</td><td>${j.buts ? j.buts + "⚽ " : ""}${j.cadres}/${j.tirs}</td>`;
    t.append(tr);
  }
  J.append(t);
  dessiner();
}

// -- le dessin --------------------------------------------------------------
const c = $("#c"), ctx = c.getContext("2d");
const sx = x => x / LONG * c.width, sy = y => y / LARG * c.height;
function fond() {
  ctx.fillStyle = "#1f7a3a"; ctx.fillRect(0, 0, c.width, c.height);
  ctx.fillStyle = "rgba(255,255,255,.04)";
  for (let i = 0; i < 10; i += 2) ctx.fillRect(sx(i * 10.5), 0, sx(10.5), c.height);
  ctx.strokeStyle = "rgba(255,255,255,.75)"; ctx.lineWidth = 2;
  ctx.strokeRect(sx(0.5), sy(0.5), sx(104), sy(67));
  ctx.beginPath(); ctx.moveTo(sx(52.5), sy(0.5)); ctx.lineTo(sx(52.5), sy(67.5)); ctx.stroke();
  ctx.beginPath(); ctx.arc(sx(52.5), sy(34), sx(9.15), 0, Math.PI * 2); ctx.stroke();
  for (const [x0, dir] of [[0.5, 1], [104.5, -1]]) {
    ctx.strokeRect(Math.min(sx(x0), sx(x0 + dir * 16.5)), sy(34 - 20.16), sx(16.5), sy(40.32));
    ctx.strokeRect(Math.min(sx(x0), sx(x0 + dir * 5.5)), sy(34 - 9.16), sx(5.5), sy(18.32));
    ctx.beginPath(); ctx.arc(sx(x0 + dir * 11), sy(34), 3, 0, Math.PI * 2); ctx.fillStyle = "#fff"; ctx.fill();
    // la cage
    ctx.fillStyle = "rgba(255,255,255,.35)";
    ctx.fillRect(dir > 0 ? sx(0.5) - 8 : sx(104.5), sy(34 - 3.66), 8, sy(7.32));
  }
}
function image(k) {
  const tr = BAC.res.trace; k = Math.max(0, Math.min(tr.length - 1, k));
  const f0 = tr[Math.floor(k)], f1 = tr[Math.min(tr.length - 1, Math.floor(k) + 1)], u = k - Math.floor(k);
  return f0.map((v, i) => i === 0 ? v : v + (f1[i] - v) * u);
}
function dessiner() {
  fond();
  if (!BAC.res) return;
  const f = image(BAC.i);
  const t = f[0] / 10;
  // les joueurs
  for (let j = 0; j < 22; j++) {
    const x = f[7 + j * 2] / 10, y = f[8 + j * 2] / 10;
    const jo = BAC.res.joueurs[j];
    ctx.beginPath(); ctx.arc(sx(x), sy(y), 9, 0, Math.PI * 2);
    ctx.fillStyle = jo.camp === 0 ? "#1F6FD1" : "#C62E2E"; ctx.fill();
    ctx.lineWidth = 2; ctx.strokeStyle = jo.poste.startsWith("Gardien") ? "#ffd86b" : "rgba(255,255,255,.9)"; ctx.stroke();
    ctx.fillStyle = "#fff"; ctx.font = "11px Barlow Condensed, sans-serif"; ctx.textAlign = "center";
    ctx.fillText(BAC.noms[jo.camp + ":" + jo.pid] || "", sx(x), sy(y) + 22);
  }
  // le ballon, avec son ombre selon la hauteur
  const bx = f[1] / 10, by = f[2] / 10, bz = f[3] / 10;
  ctx.beginPath(); ctx.ellipse(sx(bx), sy(by), 5 + bz, 2.5 + bz * 0.5, 0, 0, Math.PI * 2); ctx.fillStyle = "rgba(0,0,0,.35)"; ctx.fill();
  ctx.beginPath(); ctx.arc(sx(bx), sy(by) - bz * 6, 5 + bz * 0.8, 0, Math.PI * 2); ctx.fillStyle = "#fff"; ctx.fill(); ctx.strokeStyle = "#222"; ctx.lineWidth = 1; ctx.stroke();
  // la phase de chaque camp, en haut du terrain
  if (BAC.res.phases) {
    const LIBP = {construction: "construction", progression: "progression", finition: "finition", contre: "contre-attaque",
      pressing: "pressing", bloc_median: "bloc médian", bloc_bas: "bloc bas", contre_pressing: "contre-pressing", relance: "relance"};
    const f0 = BAC.res.trace[Math.floor(BAC.i)];
    ctx.font = "bold 15px Barlow Condensed, sans-serif"; ctx.textAlign = "left"; ctx.fillStyle = "#7cb3ff";
    ctx.fillText(LIBP[BAC.res.phases[f0[5]]] || "", 12, 22);
    ctx.textAlign = "right"; ctx.fillStyle = "#ff8f8f";
    ctx.fillText(LIBP[BAC.res.phases[f0[6]]] || "", c.width - 12, 22);
  }
  // l'horloge et le score à cet instant
  const m = Math.floor(t / 60);
  $("#min").textContent = `${m}'`;
  let s = [0, 0];
  for (const e of BAC.res.evenements) if (e.k === "but" && e.t <= t) s = e.score;
  $("#score").textContent = `${s[0]} – ${s[1]}`;
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

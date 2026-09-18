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
  // les tenues : le maillot du club, le gardien dans une couleur à lui
  const T = res.maillots || {a: {base: "#1F6FD1", second: "#ffffff", motif: "uni"}, b: {base: "#C62E2E", second: "#ffffff", motif: "uni"}, gardiens: ["#f2d33a", "#3ec46d"]};
  BAC.tenues = res.joueurs.map(j => j.poste.startsWith("Gardien") ? {base: T.gardiens[j.camp], second: "#222", motif: "uni"} : (j.camp === 0 ? T.a : T.b));
  BAC.cap = res.joueurs.map((j, i) => j.camp === 0 ? 0 : Math.PI);   // l'orientation du corps, lissée
  BAC.pas = res.joueurs.map(() => 0);                                 // la foulée : les pieds alternent
  BAC.prec = null;
  // les gestes : pour chaque frappe, tête, arrêt et but, de quoi les dessiner
  BAC.idx = {}; res.joueurs.forEach((j, i) => BAC.idx[j.camp + ":" + j.pid] = i);
  BAC.gestes = [];
  const pas = res.trace_pas;
  for (const e of res.evenements) {
    if (!["tir", "arret", "but"].includes(e.k)) continue;
    const k = Math.max(0, Math.min(res.trace.length - 2, Math.round(e.t / pas) - 1));   // l'image k est à (k+1)·pas
    const g = {k: e.k, t: e.t, camp: e.camp, tete: !!e.tete, pied: e.pied || "", j: BAC.idx[e.camp + ":" + e.de]};
    if (e.k === "tir" || e.k === "arret") {
      const f0 = res.trace[k], f1 = res.trace[Math.min(res.trace.length - 1, k + (e.k === "tir" ? 1 : 0))];
      const fb = e.k === "tir" ? f1 : res.trace[Math.max(0, k - 1)];
      const jx = f0[7 + g.j * 2] / 10, jy = f0[8 + g.j * 2] / 10;
      g.dir = Math.atan2(fb[2] / 10 - jy, fb[1] / 10 - jx);
    }
    BAC.gestes.push(g);
  }
  $("#nom-a").textContent = res.noms[0]; $("#nom-b").textContent = res.noms[1];
  $("#curseur").max = res.trace.length - 1; $("#curseur").value = 0;
  $("#lecture").textContent = "⏸";
  // le fil
  const fil = $("#fil"); fil.replaceChildren();
  const LIB = {but: "BUT", tir: "Frappe", arret: "Arrêt", rate: "À côté", contre: "Contré", faute: "Faute", corner: "Corner",
    penalty: "Penalty", horsjeu: "Hors-jeu", mi_temps: "Mi-temps", fin: "Fin du match", carton: "Carton",
    percee: "Percée balle au pied", passe: "Passe en profondeur", provoque: "Provoque son vis-à-vis", crochet: "Crochet",
    seul: "Seul face au gardien"};
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
    tr.innerHTML = `<td>${j.nom.split(" ").slice(-1)[0]}${j.capitaine ? " <b style='color:#ffd86b'>C</b>" : ""} <small>${j.poste.split(" ")[0]}</small></td><td>${(j.distance / 1000).toFixed(1)}</td><td>${j.sprint}</td><td>${j.vmax_kmh}</td><td>${j.vmax_ea ?? "—"}</td><td>${j.travail ? j.travail.map(v => Math.round(v * 9)).join("") : "—"}</td><td>${j.touches}</td><td>${j.passes_ok}/${j.passes}</td><td>${j.buts ? j.buts + "⚽ " : ""}${j.cadres}/${j.tirs}</td>`;
    t.append(tr);
  }
  J.append(t);
  dessiner();
}

// -- le dessin --------------------------------------------------------------
const c = $("#c"), ctx = c.getContext("2d");
const MARGE = 14;                                    // les cages se dessinent dans la marge
const sx = x => MARGE + x / LONG * (c.width - 2 * MARGE), sy = y => MARGE * 0.4 + y / LARG * (c.height - MARGE * 0.8);
function fond() {
  ctx.fillStyle = "#1f7a3a"; ctx.fillRect(0, 0, c.width, c.height);
  ctx.fillStyle = "rgba(255,255,255,.04)";
  for (let i = 0; i < 10; i += 2) ctx.fillRect(sx(i * 10.5), 0, sx(10.5) - sx(0), c.height);
  ctx.strokeStyle = "rgba(255,255,255,.75)"; ctx.lineWidth = 2;
  ctx.strokeRect(sx(0.5), sy(0.5), sx(104.5) - sx(0.5), sy(67.5) - sy(0.5));
  ctx.beginPath(); ctx.moveTo(sx(52.5), sy(0.5)); ctx.lineTo(sx(52.5), sy(67.5)); ctx.stroke();
  ctx.beginPath(); ctx.arc(sx(52.5), sy(34), sx(9.15) - sx(0), 0, Math.PI * 2); ctx.stroke();
  for (const [x0, dir] of [[0.5, 1], [104.5, -1]]) {
    ctx.strokeRect(Math.min(sx(x0), sx(x0 + dir * 16.5)), sy(34 - 20.16), sx(16.5) - sx(0), sy(40.32) - sy(0));
    ctx.strokeRect(Math.min(sx(x0), sx(x0 + dir * 5.5)), sy(34 - 9.16), sx(5.5) - sx(0), sy(18.32) - sy(0));
    ctx.beginPath(); ctx.arc(sx(x0 + dir * 11), sy(34), 3, 0, Math.PI * 2); ctx.fillStyle = "#fff"; ctx.fill();
    // la cage
    ctx.fillStyle = "rgba(255,255,255,.35)";
    ctx.fillRect(dir > 0 ? sx(0.5) - 10 : sx(104.5), sy(34 - 3.66), 10, sy(7.32) - sy(0));
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
  // les gestes en cours à cet instant (frappe, tête, détente, filets)
  const gestes = (BAC.gestes || []).filter(g => t >= g.t - 0.45 && t <= g.t + (g.k === "but" ? 1.4 : 0.55));
  const enGeste = {}; for (const g of gestes) if (g.k !== "but") enGeste[g.j] = g;
  // l'orientation et la foulée de chacun : la vitesse entre deux images, ou le ballon quand on est à l'arrêt
  const fn = image(BAC.i + 1), dtp = BAC.res.trace_pas;
  const bx0 = f[1] / 10, by0 = f[2] / 10;
  for (let j = 0; j < 22; j++) {
    const x = f[7 + j * 2] / 10, y = f[8 + j * 2] / 10;
    const vx = (fn[7 + j * 2] / 10 - x) / dtp, vy = (fn[8 + j * 2] / 10 - y) / dtp;
    const v = Math.hypot(vx, vy);
    let vise = v > 0.8 ? Math.atan2(vy, vx) : Math.atan2(by0 - y, bx0 - x);
    let d = vise - BAC.cap[j]; while (d > Math.PI) d -= 2 * Math.PI; while (d < -Math.PI) d += 2 * Math.PI;
    BAC.cap[j] += d * (v > 0.8 ? 0.35 : 0.12);
    if (BAC.prec) BAC.pas[j] += Math.hypot(x - BAC.prec[j][0], y - BAC.prec[j][1]);
    BAC.vit = BAC.vit || []; BAC.vit[j] = v;
  }
  BAC.prec = Array.from({length: 22}, (_, j) => [f[7 + j * 2] / 10, f[8 + j * 2] / 10]);
  // les joueurs, du haut du terrain vers le bas pour que les ombres se recouvrent bien
  const ordre = Array.from({length: 22}, (_, j) => j).sort((a, b) => f[8 + a * 2] - f[8 + b * 2]);
  for (const j of ordre) {
    const x = f[7 + j * 2] / 10, y = f[8 + j * 2] / 10;
    const jo = BAC.res.joueurs[j];
    if (enGeste[j]) { geste(enGeste[j], x, y, t, jo, j); continue; }
    joueur(x, y, jo, j);
    ctx.fillStyle = "#fff"; ctx.font = "11px Barlow Condensed, sans-serif"; ctx.textAlign = "center";
    ctx.fillText(BAC.noms[jo.camp + ":" + jo.pid] || "", sx(x), sy(y) + 22);
  }
  // le ballon, avec son ombre selon la hauteur
  const bx = f[1] / 10, by = f[2] / 10, bz = f[3] / 10;
  ctx.beginPath(); ctx.ellipse(sx(bx), sy(by), 5 + bz, 2.5 + bz * 0.5, 0, 0, Math.PI * 2); ctx.fillStyle = "rgba(0,0,0,.35)"; ctx.fill();
  ctx.beginPath(); ctx.arc(sx(bx), sy(by) - bz * 6, 5 + bz * 0.8, 0, Math.PI * 2); ctx.fillStyle = "#fff"; ctx.fill(); ctx.strokeStyle = "#222"; ctx.lineWidth = 1; ctx.stroke();
  // les filets qui tremblent
  for (const g of gestes) if (g.k === "but") filets(g, t);
  // la phase de chaque camp, en haut du terrain
  if (BAC.res.phases) {
    const LIBP = {construction: "construction", progression: "progression", finition: "finition", contre: "contre-attaque",
      pressing: "pressing", bloc_median: "bloc médian", bloc_bas: "bloc bas", contre_pressing: "contre-pressing", relance: "relance"};
    const f0 = BAC.res.trace[Math.max(0, Math.min(BAC.res.trace.length - 1, Math.floor(BAC.i)))];
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
// -- les gestes : l'élan d'une frappe, la tête, la détente du gardien, les filets
// -- un footballeur vu de dessus : les pieds qui courent, les épaules au maillot du club, la tête
const PEAUX = ["#f1c9a5", "#e0ac7e", "#c68642", "#8d5524", "#5a3b25", "#f7d9c4"];
function joueur(x, y, jo, j, r = 10.5) {
  const cap = BAC.cap ? BAC.cap[j] : 0, v = BAC.vit ? BAC.vit[j] || 0 : 0;
  const ten = BAC.tenues ? BAC.tenues[j] : {base: jo.camp === 0 ? "#1F6FD1" : "#C62E2E", second: "#fff", motif: "uni"};
  const X = sx(x), Y = sy(y);
  ctx.save(); ctx.translate(X, Y);
  // l'ombre
  ctx.beginPath(); ctx.ellipse(2, 3, r + 1, r * 0.6, 0, 0, Math.PI * 2); ctx.fillStyle = "rgba(0,0,0,.28)"; ctx.fill();
  ctx.rotate(cap);
  // les pieds : ils alternent avec la foulée (1,4 m par pas en course, plus court au trot), immobiles à l'arrêt
  const foulee = v > 0.8 ? Math.sin((BAC.pas[j] / (0.7 + 0.25 * Math.min(v, 7))) * Math.PI * 2) : 0;
  const amp = v > 0.8 ? 5 + Math.min(v, 8) * 0.6 : 0;
  ctx.fillStyle = "#1c1c1c";
  ctx.beginPath(); ctx.ellipse(foulee * amp, -4.2, 3.6, 2.1, 0, 0, Math.PI * 2); ctx.fill();
  ctx.beginPath(); ctx.ellipse(-foulee * amp, 4.2, 3.6, 2.1, 0, 0, Math.PI * 2); ctx.fill();
  // les épaules, au maillot
  ctx.beginPath(); ctx.ellipse(0, 0, r * 0.8, r, 0, 0, Math.PI * 2);
  ctx.fillStyle = ten.base; ctx.fill();
  ctx.save(); ctx.clip();
  ctx.fillStyle = ten.second;
  if (ten.motif === "bande") ctx.fillRect(-r, -r * 0.34, 2 * r, r * 0.68);
  else if (ten.motif === "rayures") for (const o of [-0.66, 0, 0.66]) ctx.fillRect(-r, o * r - r * 0.16, 2 * r, r * 0.32);
  else if (ten.motif === "cercle") for (const o of [-0.5, 0.5]) ctx.fillRect(o * r - r * 0.18, -r, r * 0.36, 2 * r);
  else if (ten.motif === "moitie") ctx.fillRect(-r, 0, 2 * r, r);
  else if (ten.motif === "echarpe") { ctx.rotate(-0.7); ctx.fillRect(-2 * r, -r * 0.2, 4 * r, r * 0.4); }
  ctx.restore();
  ctx.lineWidth = 1.2; ctx.strokeStyle = "rgba(0,0,0,.45)"; ctx.stroke();
  // la tête, un peu vers l'avant
  ctx.beginPath(); ctx.arc(r * 0.18, 0, r * 0.42, 0, Math.PI * 2);
  ctx.fillStyle = PEAUX[(jo.pid || 0) % PEAUX.length]; ctx.fill(); ctx.lineWidth = 1; ctx.strokeStyle = "rgba(0,0,0,.35)"; ctx.stroke();
  ctx.restore();
  brassard(x, y, jo, r);
}
function jeton(x, y, jo, r = 10.5, j = null) {
  if (j === null) j = BAC.res.joueurs.indexOf(jo);
  joueur(x, y, jo, j, r);
}
function brassard(x, y, jo, r = 9) {
  // le capitaine : un brassard jaune, en haut à gauche du jeton
  if (!jo.capitaine) return;
  ctx.beginPath(); ctx.arc(sx(x) - r * 0.75, sy(y) - r * 0.75, 5, 0, Math.PI * 2); ctx.fillStyle = "#ffd86b"; ctx.fill();
  ctx.fillStyle = "#1a1405"; ctx.font = "bold 8px Barlow Condensed, sans-serif"; ctx.textAlign = "center";
  ctx.fillText("C", sx(x) - r * 0.75, sy(y) - r * 0.75 + 3);
}
function geste(g, x, y, t, jo, j) {
  const u = Math.max(0, Math.min(1, (t - (g.t - 0.45)) / 1.0));
  if (g.k === "tir" && g.tete) {
    // la tête : le jeton s'élève sur sa détente, son ombre reste au sol
    const h = Math.sin(Math.PI * u) * 14;
    ctx.beginPath(); ctx.ellipse(sx(x), sy(y) + 4, 9, 4, 0, 0, Math.PI * 2); ctx.fillStyle = "rgba(0,0,0,.35)"; ctx.fill();
    ctx.save(); ctx.translate(0, -h); jeton(x, y, jo, 9 + h * 0.15, j); ctx.restore();
    ctx.fillStyle = "#fff"; ctx.font = "11px Barlow Condensed, sans-serif"; ctx.textAlign = "center";
    ctx.fillText(BAC.noms[jo.camp + ":" + jo.pid] || "", sx(x), sy(y) + 22);
    return;
  }
  if (g.k === "tir") {
    // l'élan : la jambe part en arrière puis fouette vers le ballon ; le pied dit droit ou gauche
    jeton(x, y, jo, 9, j);
    const balancier = u < 0.45 ? -1.3 * (u / 0.45) : -1.3 + 2.0 * ((u - 0.45) / 0.55);
    const cote = g.pied === "G" ? 1 : -1;                 // le pied gauche part de l'autre côté du jeton
    const a = g.dir + balancier * cote;
    const px = sx(x) + Math.cos(a) * 15, py = sy(y) + Math.sin(a) * 15;
    ctx.beginPath(); ctx.moveTo(sx(x) + Math.cos(g.dir + Math.PI / 2 * cote) * 4, sy(y) + Math.sin(g.dir + Math.PI / 2 * cote) * 4); ctx.lineTo(px, py);
    ctx.lineWidth = 4; ctx.strokeStyle = "#fff"; ctx.lineCap = "round"; ctx.stroke();
    ctx.beginPath(); ctx.arc(px, py, 4, 0, Math.PI * 2); ctx.fillStyle = "#ffd86b"; ctx.fill();
    ctx.fillStyle = "#1a1405"; ctx.font = "bold 8px Barlow Condensed, sans-serif"; ctx.textAlign = "center"; ctx.fillText(g.pied, px, py + 3);
    ctx.fillStyle = "#fff"; ctx.font = "11px Barlow Condensed, sans-serif"; ctx.fillText(BAC.noms[jo.camp + ":" + jo.pid] || "", sx(x), sy(y) + 22);
    return;
  }
  if (g.k === "arret") {
    // la détente : le gardien s'allonge vers le ballon
    const s = Math.sin(Math.PI * Math.min(1, u * 1.2));
    ctx.save(); ctx.translate(sx(x), sy(y)); ctx.rotate(g.dir);
    ctx.beginPath(); ctx.ellipse(s * 12, 0, 9 + s * 15, 9 - s * 4, 0, 0, Math.PI * 2);
    ctx.fillStyle = (BAC.tenues && BAC.tenues[j]) ? BAC.tenues[j].base : "#ffd86b"; ctx.fill(); ctx.lineWidth = 1.5; ctx.strokeStyle = "rgba(0,0,0,.45)"; ctx.stroke();
    ctx.beginPath(); ctx.arc(s * 12 + 4, 0, 3.8, 0, Math.PI * 2); ctx.fillStyle = PEAUX[(jo.pid || 0) % PEAUX.length]; ctx.fill();
    ctx.restore();
    ctx.fillStyle = "#fff"; ctx.font = "11px Barlow Condensed, sans-serif"; ctx.textAlign = "center";
    ctx.fillText(BAC.noms[jo.camp + ":" + jo.pid] || "", sx(x), sy(y) + 22);
    return;
  }
  jeton(x, y, jo, 9, j);
}
function filets(g, t) {
  // le camp qui marque pousse le filet d'en face ; il tremble et s'apaise
  const u = (t - g.t) / 1.4, amp = Math.exp(-3 * u) * 5 * Math.sin(40 * (t - g.t));
  const droite = g.camp === 0;
  const x0 = droite ? sx(104.5) : sx(0.5) - 10, y0 = sy(34 - 3.66), h = sy(7.32) - sy(0), w = 10;
  ctx.strokeStyle = "rgba(255,255,255,.8)"; ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {
    const y = y0 + h * i / 4;
    ctx.beginPath(); ctx.moveTo(x0, y); ctx.lineTo(x0 + w + (droite ? amp : -amp), y + amp * 0.3); ctx.stroke();
  }
  for (let i = 1; i <= 2; i++) {
    const x = x0 + w * i / 2;
    ctx.beginPath(); ctx.moveTo(x + (droite ? amp : -amp) * i / 2, y0); ctx.lineTo(x + (droite ? amp : -amp) * i / 2, y0 + h); ctx.stroke();
  }
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

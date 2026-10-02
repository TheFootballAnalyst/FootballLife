// Le terrain du moteur B, partagé par le bac à sable et l'écran de match.
//
// Le serveur joue le match (jeu/emergent.py) et renvoie une image toutes
// les 0,4 s : le ballon (x, y, z) et les vingt-deux (x, y), en décimètres.
// Ici on interpole entre deux images et on dessine sur un canvas.  Rien
// n'est décidé côté page : elle regarde.  Le bac reçoit tout le match
// d'un coup ; l'écran de match reçoit les images au fil de l'horloge
// (`ajouter`) et le terrain les joue derrière, sans jamais dépasser ce
// qu'il a reçu.
const TB_LONG = 105, TB_LARG = 68;

class TerrainB {
  constructor(canvas, options = {}) {
    this.c = canvas; this.ctx = canvas.getContext("2d");
    this.miroir = !!options.miroir;            // ton équipe attaque vers la droite, quel que soit son camp
    this.MARGE = 14;
    this.trace = []; this.evenements = []; this.gestes = []; this.joueurs = []; this.noms = {}; this.idx = {};
    this.cap = []; this.pas = []; this.vit = []; this.peau = []; this.tenues = []; this.prec = null;
    this.trace_pas = 0.4; this.phases = null; this.i = 0;
    // le temps affiché : ce que coûte chaque image à l'écran quand on saute les arrêts
    // de jeu (cout[k] = secondes affichées cumulées jusqu'à l'image k ; une image de ballon
    // vivant coûte un pas, les deux dernières secondes d'un arrêt aussi, le reste de l'arrêt rien)
    this.saut = 2.0; this.cout = []; this.debutArret = -1;
  }
  sx(x) { return this.MARGE + x / TB_LONG * (this.c.width - 2 * this.MARGE); }
  sy(y) { return this.MARGE * 0.4 + y / TB_LARG * (this.c.height - this.MARGE * 0.8); }

  // -- ce qu'on reçoit ---------------------------------------------------------
  charger(res, maillots) {
    this.joueurs = res.joueurs; this.trace = []; this.evenements = []; this.gestes = []; this.i = 0; this.prec = null;
    this.cout = []; this.debutArret = -1;
    this.trace_pas = res.trace_pas; this.phases = res.phases || null;
    if (res.saut_arret !== undefined && res.saut_arret !== null) this.saut = res.saut_arret;
    this.noms = {}; this.idx = {};
    res.joueurs.forEach((j, i) => { this.noms[j.camp + ":" + j.pid] = j.nom.split(" ").slice(-1)[0]; this.idx[j.camp + ":" + j.pid] = i; });
    const T = maillots || res.maillots || {a: {base: "#1F6FD1", second: "#ffffff", motif: "uni"}, b: {base: "#C62E2E", second: "#ffffff", motif: "uni"}, gardiens: ["#f2d33a", "#3ec46d"]};
    this.tenues = res.joueurs.map(j => j.poste.startsWith("Gardien") ? {base: T.gardiens[j.camp], second: "#222", motif: "uni"} : (j.camp === 0 ? T.a : T.b));
    this.cap = res.joueurs.map(j => (j.camp === 0) !== this.miroir ? 0 : Math.PI);
    this.pas = res.joueurs.map(() => 0); this.vit = res.joueurs.map(() => 0);
    this.peau = res.joueurs.map(() => "#d9a77c");
    res.joueurs.forEach((j, i) => this._peau(j, i));
    this.ajouter(res.trace || [], res.evenements || []);
  }
  // un joueur qui entre en cours de match (remplacement) : sa fiche remplace celle du sortant au même rang
  remplacer(joueurs) {
    joueurs.forEach((j, i) => {
      if (this.joueurs[i] && this.joueurs[i].pid === j.pid) return;
      this.joueurs[i] = j;
      this.noms[j.camp + ":" + j.pid] = j.nom.split(" ").slice(-1)[0]; this.idx[j.camp + ":" + j.pid] = i;
      this.peau[i] = "#d9a77c"; this._peau(j, i);
    });
  }
  _peau(j, i) {
    // la peau : lue sur le portrait du joueur quand il est là (le front, au-dessus des yeux), sinon un ton moyen
    const im = new Image(); im.crossOrigin = "anonymous";
    im.onload = () => {
      try {
        const c2 = document.createElement("canvas"); c2.width = im.width; c2.height = im.height;
        const g = c2.getContext("2d"); g.drawImage(im, 0, 0);
        const x0 = Math.floor(im.width * 0.35), x1 = Math.floor(im.width * 0.65), y0 = Math.floor(im.height * 0.28), y1 = Math.floor(im.height * 0.55);
        const px = g.getImageData(x0, y0, x1 - x0, y1 - y0).data;
        let r = 0, gg = 0, b = 0, n = 0;
        for (let k = 0; k < px.length; k += 4) {
          const R = px[k], G = px[k + 1], B = px[k + 2], A = px[k + 3];
          if (A < 200) continue;
          if (R > G && G >= B * 0.85 && R - B > 12 && R + G + B > 90) { r += R; gg += G; b += B; n++; }
        }
        if (n > 40) this.peau[i] = `rgb(${Math.round(r / n)},${Math.round(gg / n)},${Math.round(b / n)})`;
      } catch (e) { /* portrait d'une autre origine : on garde le ton moyen */ }
    };
    im.src = `/images/joueurs/${j.pid}.png`;
  }
  // des images de plus (après la dernière reçue) et des événements de plus
  ajouter(trace, evenements) {
    const dernier = this.trace.length ? this.trace[this.trace.length - 1][0] : -1;
    const avant = this.trace.length;
    for (const f of trace) {
      if (f[0] <= dernier) continue;
      this.trace.push(this.miroir ? this._miroir(f) : f);
    }
    if (this.trace.length > avant) this._couter(avant);
    const vus = new Set(this.evenements.map(e => e.k + "@" + e.t + "@" + (e.de ?? "")));
    for (const e of evenements || []) {
      const cle = e.k + "@" + e.t + "@" + (e.de ?? "");
      if (vus.has(cle)) continue;
      vus.add(cle); this.evenements.push(e);
      if (["tir", "arret", "but", "tacle"].includes(e.k)) this._geste(e);
    }
  }
  _miroir(f) {
    const g = f.slice();
    g[1] = 1050 - f[1]; g[2] = 680 - f[2];
    for (let j = 0; j < 22; j++) { g[7 + j * 2] = 1050 - f[7 + j * 2]; g[8 + j * 2] = 680 - f[8 + j * 2]; }
    return g;
  }
  _geste(e) {
    const tr = this.trace, pas = this.trace_pas;
    if (!tr.length) return;
    const k = Math.max(0, Math.min(tr.length - 2, Math.round(e.t / pas) - 1 - (tr[0][0] / 10 / pas)));   // l'image k est à (k+1)·pas depuis la première reçue
    const g = {k: e.k, t: e.t, camp: e.camp, tete: !!e.tete, pied: e.pied || "", j: this.idx[e.camp + ":" + e.de]};
    if (g.j === undefined && e.k !== "but") return;
    if (e.k === "tacle") {
      const f0 = tr[k], jv = this.idx[(1 - e.camp) + ":" + e.sur];
      const jx = f0[7 + g.j * 2] / 10, jy = f0[8 + g.j * 2] / 10;
      g.dir = jv === undefined ? 0 : Math.atan2(f0[8 + jv * 2] / 10 - jy, f0[7 + jv * 2] / 10 - jx);
    }
    if (e.k === "tir" || e.k === "arret") {
      const f0 = tr[k], f1 = tr[Math.min(tr.length - 1, k + (e.k === "tir" ? 1 : 0))];
      const fb = e.k === "tir" ? f1 : tr[Math.max(0, k - 1)];
      const jx = f0[7 + g.j * 2] / 10, jy = f0[8 + g.j * 2] / 10;
      g.dir = Math.atan2(fb[2] / 10 - jy, fb[1] / 10 - jx);
    }
    if (this.miroir) g.camp = 1 - g.camp;    // les filets d'en face sont de l'autre côté
    this.gestes.push(g);
  }
  // le coût d'affichage des images à partir de `depuis` ; un arrêt encore ouvert à la fin
  // (sa fin pas reçue) ne coûte rien pour l'instant, on le refait quand elle arrive
  _couter(depuis) {
    const tr = this.trace, pas = this.trace_pas, n = tr.length;
    let k = Math.min(depuis, this.debutArret >= 0 ? this.debutArret : depuis);
    if (k > 0 && tr[k - 1][4] === 1) { while (k > 0 && tr[k - 1][4] === 1) k--; }     // reprendre au début de l'arrêt en cours
    this.cout.length = k;
    let c = k > 0 ? this.cout[k - 1] : 0;
    this.debutArret = -1;
    while (k < n) {
      if (tr[k][4] !== 1) { c += pas; this.cout.push(c); k++; continue; }
      let fin = k; while (fin < n && tr[fin][4] === 1) fin++;
      if (fin >= n) { this.debutArret = k; for (; k < n; k++) this.cout.push(c); break; }   // arrêt ouvert
      const montrees = Math.max(1, Math.round(this.saut / pas));
      for (; k < fin; k++) { if (k >= fin - montrees) c += pas; this.cout.push(c); }
    }
  }
  // le temps affiché total reçu, et l'image atteinte pour un temps affiché
  get affiche() { return this.cout.length ? this.cout[this.cout.length - 1] : 0; }
  indexAffiche(d) {
    const c = this.cout; if (!c.length) return 0;
    let lo = 0, hi = c.length - 1;
    while (lo < hi) { const mi = (lo + hi) >> 1; if (c[mi] < d) lo = mi + 1; else hi = mi; }
    // lo : la première image dont le coût cumulé atteint d ; on y ajoute la fraction du pas
    const prec = lo > 0 ? c[lo - 1] : 0, dc = c[lo] - prec;
    return dc > 0 ? Math.max(0, lo - 1 + (d - prec) / dc) : lo;
  }
  get duree() { return this.trace.length ? this.trace[this.trace.length - 1][0] / 10 : 0; }
  get debut() { return this.trace.length ? this.trace[0][0] / 10 : 0; }
  // l'index d'image pour un instant de jeu
  index(t) { return Math.max(0, Math.min(this.trace.length - 1, (t - this.debut) / this.trace_pas)); }
  image(k) {
    const tr = this.trace; k = Math.max(0, Math.min(tr.length - 1, k));
    const f0 = tr[Math.floor(k)], f1 = tr[Math.min(tr.length - 1, Math.floor(k) + 1)], u = k - Math.floor(k);
    return f0.map((v, i) => i === 0 ? v : v + (f1[i] - v) * u);
  }
  scoreA(t) { let s = [0, 0]; for (const e of this.evenements) if (e.k === "but" && e.t <= t && e.score) s = e.score; return s; }

  // -- le dessin -----------------------------------------------------------------
  fond() {
    const ctx = this.ctx, c = this.c, sx = x => this.sx(x), sy = y => this.sy(y);
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
      ctx.fillStyle = "rgba(255,255,255,.35)";
      ctx.fillRect(dir > 0 ? sx(0.5) - 10 : sx(104.5), sy(34 - 3.66), 10, sy(7.32) - sy(0));
    }
  }
  // dessine l'image k (fractionnaire) ; rend l'instant de jeu et le score à cet instant
  dessiner(k) {
    const ctx = this.ctx, c = this.c, sx = x => this.sx(x), sy = y => this.sy(y);
    this.fond();
    if (!this.trace.length) return {t: 0, score: [0, 0]};
    this.i = Math.max(0, Math.min(this.trace.length - 1, k));
    const f = this.image(this.i);
    const t = f[0] / 10;
    const gestes = this.gestes.filter(g => t >= g.t - (g.k === "tacle" ? 0.1 : 0.45) && t <= g.t + (g.k === "but" ? 1.4 : g.k === "tacle" ? 0.7 : 0.55));
    const enGeste = {}; for (const g of gestes) if (g.k !== "but") enGeste[g.j] = g;
    const fn = this.image(this.i + 1), dtp = this.trace_pas;
    const bx0 = f[1] / 10, by0 = f[2] / 10;
    for (let j = 0; j < 22; j++) {
      const x = f[7 + j * 2] / 10, y = f[8 + j * 2] / 10;
      const vx = (fn[7 + j * 2] / 10 - x) / dtp, vy = (fn[8 + j * 2] / 10 - y) / dtp;
      const v = Math.hypot(vx, vy);
      let vise = v > 0.8 ? Math.atan2(vy, vx) : Math.atan2(by0 - y, bx0 - x);
      let d = vise - this.cap[j]; while (d > Math.PI) d -= 2 * Math.PI; while (d < -Math.PI) d += 2 * Math.PI;
      this.cap[j] += d * (v > 0.8 ? 0.35 : 0.12);
      if (this.prec) this.pas[j] += Math.hypot(x - this.prec[j][0], y - this.prec[j][1]);
      this.vit[j] = v;
    }
    this.prec = Array.from({length: 22}, (_, j) => [f[7 + j * 2] / 10, f[8 + j * 2] / 10]);
    const ordre = Array.from({length: 22}, (_, j) => j).sort((a, b) => f[8 + a * 2] - f[8 + b * 2]);
    for (const j of ordre) {
      const x = f[7 + j * 2] / 10, y = f[8 + j * 2] / 10;
      const jo = this.joueurs[j];
      if (!jo) continue;
      if (enGeste[j]) { this.geste(enGeste[j], x, y, t, jo, j); continue; }
      if (y < -1.5 || y > 69.5) continue;
      this.joueur(x, y, jo, j);
      ctx.fillStyle = "#fff"; ctx.font = "11px Barlow Condensed, sans-serif"; ctx.textAlign = "center";
      ctx.fillText(this.noms[jo.camp + ":" + jo.pid] || "", sx(x), sy(y) + 22);
    }
    const bx = f[1] / 10, by = f[2] / 10, bz = f[3] / 10;
    ctx.beginPath(); ctx.ellipse(sx(bx), sy(by), 5 + bz, 2.5 + bz * 0.5, 0, 0, Math.PI * 2); ctx.fillStyle = "rgba(0,0,0,.35)"; ctx.fill();
    if (this.prec_ballon) this.rot_ballon = (this.rot_ballon || 0) + Math.hypot(bx - this.prec_ballon[0], by - this.prec_ballon[1]) * 0.9;
    this.prec_ballon = [bx, by];
    this.ballon(sx(bx), sy(by) - bz * 6, 6 + bz * 0.8, this.rot_ballon || 0);
    for (const g of gestes) if (g.k === "but") this.filets(g, t);
    if (this.phases) {
      // le nom de la phase dans la langue de l'écran (app.js, clés phaseb.*) ; le bac n'a pas t()
      const LIBP = {construction: "construction", progression: "progression", finition: "finition", contre: "contre-attaque",
        pressing: "pressing", bloc_median: "bloc médian", bloc_bas: "bloc bas", contre_pressing: "contre-pressing", relance: "relance"};
      const lib = k => (typeof t === "function" && typeof existeT === "function" && existeT("phaseb." + k)) ? t("phaseb." + k) : (LIBP[k] || "");
      const f0 = this.trace[Math.floor(this.i)];
      const g = this.miroir ? [f0[6], f0[5]] : [f0[5], f0[6]];
      ctx.font = "bold 15px Barlow Condensed, sans-serif"; ctx.textAlign = "left"; ctx.fillStyle = "#7cb3ff";
      ctx.fillText(lib(this.phases[g[0]]), 12, 22);
      ctx.textAlign = "right"; ctx.fillStyle = "#ff8f8f";
      ctx.fillText(lib(this.phases[g[1]]), c.width - 12, 22);
    }
    return {t, score: this.scoreA(t), arret: this.trace[Math.floor(this.i)][4] === 1};
  }
  ballon(x, y, r, rot) {
    const ctx = this.ctx;
    ctx.save(); ctx.translate(x, y); ctx.rotate(rot);
    ctx.beginPath(); ctx.arc(0, 0, r, 0, Math.PI * 2); ctx.fillStyle = "#fff"; ctx.fill();
    ctx.strokeStyle = "#111"; ctx.lineWidth = 1.2; ctx.stroke();
    ctx.beginPath(); ctx.arc(0, 0, r, 0, Math.PI * 2); ctx.clip();
    ctx.fillStyle = "#111";
    for (let k = 0; k < 3; k++) {
      const a = k * Math.PI * 2 / 3, cx = Math.cos(a) * r * 0.55, cy = Math.sin(a) * r * 0.55;
      ctx.beginPath();
      for (let i = 0; i < 5; i++) { const b = a + i * Math.PI * 2 / 5; ctx.lineTo(cx + Math.cos(b) * r * 0.34, cy + Math.sin(b) * r * 0.34); }
      ctx.closePath(); ctx.fill();
    }
    ctx.restore();
  }
  joueur(x, y, jo, j, r = 10.5) {
    const ctx = this.ctx, cap = this.cap[j] || 0, v = this.vit[j] || 0;
    const ten = this.tenues[j] || {base: jo.camp === 0 ? "#1F6FD1" : "#C62E2E", second: "#fff", motif: "uni"};
    const X = this.sx(x), Y = this.sy(y);
    ctx.save(); ctx.translate(X, Y);
    ctx.beginPath(); ctx.ellipse(2, 3, r + 1, r * 0.6, 0, 0, Math.PI * 2); ctx.fillStyle = "rgba(0,0,0,.28)"; ctx.fill();
    ctx.rotate(cap);
    const foulee = v > 0.8 ? Math.sin((this.pas[j] / (0.7 + 0.25 * Math.min(v, 7))) * Math.PI * 2) : 0;
    const amp = v > 0.8 ? 5 + Math.min(v, 8) * 0.6 : 0;
    ctx.fillStyle = "#1c1c1c";
    ctx.beginPath(); ctx.ellipse(foulee * amp, -4.2, 3.6, 2.1, 0, 0, Math.PI * 2); ctx.fill();
    ctx.beginPath(); ctx.ellipse(-foulee * amp, 4.2, 3.6, 2.1, 0, 0, Math.PI * 2); ctx.fill();
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
    ctx.beginPath(); ctx.arc(r * 0.18, 0, r * 0.42, 0, Math.PI * 2);
    ctx.fillStyle = this.peau[j] || "#d9a77c"; ctx.fill(); ctx.lineWidth = 1; ctx.strokeStyle = "rgba(0,0,0,.35)"; ctx.stroke();
    ctx.restore();
    this.brassard(x, y, jo, r);
  }
  brassard(x, y, jo, r = 9) {
    if (!jo.capitaine) return;
    const ctx = this.ctx;
    ctx.beginPath(); ctx.arc(this.sx(x) - r * 0.75, this.sy(y) - r * 0.75, 5, 0, Math.PI * 2); ctx.fillStyle = "#ffd86b"; ctx.fill();
    ctx.fillStyle = "#1a1405"; ctx.font = "bold 8px Barlow Condensed, sans-serif"; ctx.textAlign = "center";
    ctx.fillText("C", this.sx(x) - r * 0.75, this.sy(y) - r * 0.75 + 3);
  }
  _nom(jo, x, y) {
    const ctx = this.ctx;
    ctx.fillStyle = "#fff"; ctx.font = "11px Barlow Condensed, sans-serif"; ctx.textAlign = "center";
    ctx.fillText(this.noms[jo.camp + ":" + jo.pid] || "", this.sx(x), this.sy(y) + 22);
  }
  geste(g, x, y, t, jo, j) {
    const ctx = this.ctx, sx = v => this.sx(v), sy = v => this.sy(v);
    const u = Math.max(0, Math.min(1, (t - (g.t - 0.45)) / 1.0));
    if (g.k === "tir" && g.tete) {
      const h = Math.sin(Math.PI * u) * 14;
      ctx.beginPath(); ctx.ellipse(sx(x), sy(y) + 4, 9, 4, 0, 0, Math.PI * 2); ctx.fillStyle = "rgba(0,0,0,.35)"; ctx.fill();
      ctx.save(); ctx.translate(0, -h); this.joueur(x, y, jo, j, 9 + h * 0.15); ctx.restore();
      this._nom(jo, x, y); return;
    }
    if (g.k === "tir") {
      this.joueur(x, y, jo, j, 9);
      const balancier = u < 0.45 ? -1.3 * (u / 0.45) : -1.3 + 2.0 * ((u - 0.45) / 0.55);
      const cote = g.pied === "G" ? 1 : -1;
      const a = g.dir + balancier * cote;
      const px = sx(x) + Math.cos(a) * 15, py = sy(y) + Math.sin(a) * 15;
      ctx.beginPath(); ctx.moveTo(sx(x) + Math.cos(g.dir + Math.PI / 2 * cote) * 4, sy(y) + Math.sin(g.dir + Math.PI / 2 * cote) * 4); ctx.lineTo(px, py);
      ctx.lineWidth = 4; ctx.strokeStyle = "#fff"; ctx.lineCap = "round"; ctx.stroke();
      ctx.beginPath(); ctx.arc(px, py, 4, 0, Math.PI * 2); ctx.fillStyle = "#ffd86b"; ctx.fill();
      ctx.fillStyle = "#1a1405"; ctx.font = "bold 8px Barlow Condensed, sans-serif"; ctx.textAlign = "center"; ctx.fillText(g.pied, px, py + 3);
      this._nom(jo, x, y); return;
    }
    if (g.k === "tacle") {
      const s = Math.sin(Math.PI * Math.min(1, u));
      ctx.save(); ctx.translate(sx(x), sy(y)); ctx.rotate(g.dir);
      ctx.beginPath(); ctx.moveTo(-6, 0); ctx.lineTo(-6 - s * 22, 0); ctx.lineWidth = 6; ctx.strokeStyle = "rgba(255,255,255,.28)"; ctx.stroke();
      ctx.beginPath(); ctx.ellipse(s * 6, 0, 9 + s * 10, 8 - s * 2.5, 0, 0, Math.PI * 2);
      ctx.fillStyle = (this.tenues[j] || {}).base || "#ffd86b"; ctx.fill(); ctx.lineWidth = 1.5; ctx.strokeStyle = "rgba(0,0,0,.45)"; ctx.stroke();
      ctx.beginPath(); ctx.arc(-2, 0, 3.8, 0, Math.PI * 2); ctx.fillStyle = this.peau[j] || "#d9a77c"; ctx.fill();
      ctx.restore();
      this._nom(jo, x, y); return;
    }
    if (g.k === "arret") {
      const s = Math.sin(Math.PI * Math.min(1, u * 1.2));
      ctx.save(); ctx.translate(sx(x), sy(y)); ctx.rotate(g.dir);
      ctx.beginPath(); ctx.ellipse(s * 12, 0, 9 + s * 15, 9 - s * 4, 0, 0, Math.PI * 2);
      ctx.fillStyle = (this.tenues[j] || {}).base || "#ffd86b"; ctx.fill(); ctx.lineWidth = 1.5; ctx.strokeStyle = "rgba(0,0,0,.45)"; ctx.stroke();
      ctx.beginPath(); ctx.arc(s * 12 + 4, 0, 3.8, 0, Math.PI * 2); ctx.fillStyle = this.peau[j] || "#d9a77c"; ctx.fill();
      ctx.restore();
      this._nom(jo, x, y); return;
    }
    this.joueur(x, y, jo, j, 9);
  }
  filets(g, t) {
    const ctx = this.ctx, sx = v => this.sx(v), sy = v => this.sy(v);
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
}

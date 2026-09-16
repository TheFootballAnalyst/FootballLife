// ---------------------------------------------------------------------------
// Les jetons vivent ENTRE deux phases.
//
// Le moteur décide de tout ce qui compte : qui a le ballon, où, ce qu'il
// en fait, et ce que ça donne.  Le terrain, lui, ne recevait qu'une
// photo par phase : vingt-deux jetons posés d'un coup à leur place, un
// ballon qui glisse d'un point à l'autre.  Entre deux photos, rien —
// pas d'appel, pas de couverture, pas de course.
//
// Ici, chaque jeton est un AGENT : il a une position, une vitesse, une
// place dans la forme de son équipe, et à chaque tic (25 fois par
// seconde) il choisit où aller en fonction du ballon, du porteur, de ses
// coéquipiers et de l'adversaire — puis il y court à la vitesse d'un
// joueur, pas d'un curseur.  Ce qu'il fait :
//
//   - il tient sa place dans la forme (placeJoueur, avec les consignes),
//     forme qui coulisse vers le ballon et se resserre quand on défend ;
//   - il ne marche sur personne : deux jetons trop proches s'écartent ;
//   - le porteur VIENT au ballon et le conduit ; celui qui va recevoir la
//     passe suivante est déjà en route avant qu'elle parte ;
//   - deux coéquipiers se proposent en soutien, les attaquants font des
//     appels dans le dos de la ligne, en restant en jeu ;
//   - l'adversaire le plus proche presse, le second coupe la ligne de
//     passe vers le prochain receveur, le voisin du presseur couvre ;
//   - le ballon voyage à sa vitesse (une ouverture met plus longtemps
//     qu'une remise), une frappe file, une conduite colle au pied ;
//   - le gardien ferme l'angle, sort sur sa ligne, plonge où va la
//     frappe.
//
// Rien ici ne touche au résultat : le score est celui du moteur.  Ce
// fichier ne fait que rendre visible ce que le moteur raconte.
// ---------------------------------------------------------------------------
// `var` : app.js vérifie `window.SIM`, et une constante de script n'y est pas.
var SIM = {
  actif: false, t: null, moi: "a", joueurs: [], parCle: {},
  ballon: {x: 0.5, y: 0.5, de: null, a: null, t0: 0, t1: 0, vol: false, tir: false, attache: null, visible: false},
  phase: null, suivant: null, camp: null, porteur: null, receveur: null,
  timer: null, derniere: 0, horloge: 0, tempo: 1, gel: false,
  ASPECT: 1.9,           // le terrain est 1,9 fois plus large que haut
  RAYON: 0.046,          // en dessous, deux jetons se marchent dessus
  LONGUEUR: 0.40,        // un bloc en possession ne s'étire pas au-delà
};

// -- repères ---------------------------------------------------------------
// Tout se calcule dans le repère de l'ÉCRAN : x de gauche à droite, y de
// haut en bas, toi qui attaques vers la droite.  Un joueur du camp `c`
// attaque dans le sens `sens` (+1 vers la droite).  Son propre repère
// (celui du moteur : x = profondeur vers le but adverse, y = sa largeur)
// s'obtient en miroir quand il joue vers la gauche.
SIM.sensDe = function (cote) { return cote === SIM.moi ? 1 : -1; };
SIM.versPropre = function (cote, x, y) { return cote === SIM.moi ? [x, y] : [1 - x, 1 - y]; };
SIM.versEcran = function (cote, x, y) { return ecran(cote, x, y, SIM.moi, true); };
SIM.dist = function (ax, ay, bx, by) { return Math.hypot(ax - bx, (ay - by) / SIM.ASPECT); };

// La progression : 0 devant son propre but, 1 dans la surface adverse,
// lue sur la position du ballon dans le repère du camp qui l'a.
SIM.progression = function (cote) {
  const [xo] = SIM.versPropre(cote, SIM.ballon.x, SIM.ballon.y);
  return clamp(((xo - 0.07) / 0.257 - 0.5) / 2.5, 0, 1);
};

// Un décalage propre à chaque joueur, fixe pour tout le match : les
// appels ne partent pas tous en même temps.
SIM.hache = function (pid) {
  let h = (pid * 2246822519 + 374761393) >>> 0;
  h ^= h >>> 15; h = Math.imul(h, 0x85ebca6b) >>> 0; h ^= h >>> 13;
  return (h & 0xffffff) / 0xffffff;
};

// -- mise en place -----------------------------------------------------------
SIM.init = function (t, moi) {
  const anciens = SIM.parCle || {};
  SIM.t = t; SIM.moi = moi;
  SIM.joueurs = []; SIM.parCle = {};
  for (const [cle, p] of Object.entries(T2D.pions || {})) {
    const cote = cle.slice(0, 1), pid = +p.dataset.pid;
    const [bx, by] = SIM.versEcran(cote, p._base[0], p._base[1]);
    const vieux = anciens[cle];
    // la fiche physique (EA) : un joueur à 95 de vitesse court un quart
    // plus vite qu'un joueur à 65 ; sans fiche, la vitesse moyenne
    const vit = p._phys && p._phys.vit;
    const allure = vit === undefined || vit === null ? 1 : clamp(1 + (vit - 65) / 120, 0.78, 1.28);
    const j = {cle, cote, pid, p, gk: p._gk, poste: posteBase(p._poste), sens: SIM.sensDe(cote),
               x: vieux ? vieux.x : bx, y: vieux ? vieux.y : by, vx: 0, vy: 0, cx: bx, cy: by,
               vmax: 1, allure, grain: grain(pid), dec: SIM.hache(pid), role: "forme"};
    SIM.joueurs.push(j); SIM.parCle[cle] = j;
  }
  SIM.phase = null; SIM.suivant = null; SIM.camp = null; SIM.porteur = null; SIM.receveur = null;
  SIM.ballon.vol = false; SIM.ballon.attache = null;
  t.classList.add("sim");
  SIM.actif = true;
  SIM.poser();
  SIM.start();
};

SIM.start = function () {
  if (SIM.timer) return;
  SIM.derniere = performance.now();
  SIM.timer = setInterval(SIM.tic, 40);
};

SIM.stop = function () {
  if (SIM.timer) { clearInterval(SIM.timer); SIM.timer = null; }
  SIM.actif = false;
};

// -- une phase du moteur -----------------------------------------------------
// Ce que le moteur dit de cette phase : qui a le ballon (camp, porteur),
// ce qu'il en fait (k), et — grâce à la phase suivante — à qui il va le
// donner.  Les cibles de chacun en découlent à chaque tic ; ici on ne
// retient que le contexte.
SIM.phaseDe = function (ph, suivant) {
  SIM.phase = ph || null;
  SIM.suivant = suivant || null;
  SIM.camp = ph && ph.c !== undefined && ph.c !== null ? "ab"[ph.c] : null;
  SIM.porteur = SIM.camp && ph.p ? SIM.parCle[SIM.camp + ":" + ph.p] || null : null;
  SIM.receveur = null;
  if (suivant && suivant.c === ph.c && suivant.p && suivant.p !== ph.p && !SUR_LE_BUT.has(suivant.k) && !ARRETS_JEU.has(suivant.k))
    SIM.receveur = SIM.parCle[SIM.camp + ":" + suivant.p] || null;
  SIM.gel = !!ph && ARRETS_JEU.has(ph.k) && ph.k !== "but";
  SIM.tempo = clamp(Math.sqrt(8000 / Math.max(900, T2D.pas || 8000)), 0.6, 1.8);
  // une conduite : le ballon colle au pied du porteur
  SIM.ballon.attache = ph && ph.k === "conduite" && SIM.porteur ? SIM.porteur : null;
};

// Où va le ballon pour cette phase, à l'écran, et en combien de temps.
// `duree` est le budget de la phase : le ballon arrive avant la fin.
SIM.envoyer = function (g, h, ph, duree) {
  const b = SIM.ballon;
  const tir = ph.k === "tir" || ph.k === "but" || ph.k === "rate";
  const pose = ph.k === "engagement" || ph.k === "penalty" || ph.k === "coupfranc" || ph.k === "corner";
  const d = SIM.dist(b.x, b.y, g, h);
  if (pose || !b.visible) {
    // un coup de pied arrêté se PLACE : le ballon y est posé, pas envoyé
    b.x = g; b.y = h; b.vol = false; b.visible = true; b.tir = false;
    if (SIM.porteur) { SIM.porteur.x = g - 0.012 * SIM.porteur.sens; SIM.porteur.y = h; }
    return;
  }
  const vitesse = (tir ? 1.7 : 0.62) * SIM.tempo;
  const temps = clamp((d / vitesse) * 1000, 140, Math.max(160, duree * 0.85));
  b.de = [b.x, b.y]; b.a = [g, h];
  b.t0 = SIM.horloge; b.t1 = SIM.horloge + temps / 1000;
  b.vol = true; b.tir = tir; b.visible = true;
  if (SIM.ballon.attache) b.vol = false;   // la conduite : c'est le porteur qui l'amène
};

// Où ira le ballon à la phase suivante : ce que le receveur anticipe.
SIM.destination = function (ph) {
  if (!ph || ph.c === undefined || ph.c === null) return null;
  const cote = "ab"[ph.c];
  if (ph.k === "tir" || ph.k === "but" || ph.k === "rate") return buts(cote, SIM.moi, ph.t);
  if (ph.k === "arret") return ecran(cote, ...ballonArret(ph), SIM.moi, true);
  const [bx, by] = ballonDe(ph);
  return ecran(cote, bx, by, SIM.moi, true);
};

// -- le tic --------------------------------------------------------------------
SIM.tic = function () {
  if (!SIM.t || !document.contains(SIM.t)) { SIM.stop(); return; }
  const maintenant = performance.now();
  const dt = Math.min(0.12, (maintenant - SIM.derniere) / 1000);
  SIM.derniere = maintenant;
  SIM.horloge += dt;
  SIM.viser();
  SIM.avancer(dt);
  SIM.ecarter();
  SIM.bougerBallon();
  SIM.poser();
};

// La cible de chacun pour ce tic.
SIM.viser = function () {
  const ph = SIM.phase || {k: "passe", c: null, p: null};
  const camp = SIM.camp;
  const b = SIM.ballon;
  const engagement = ph.k === "engagement";
  const arrivee = b.vol ? b.a : [b.x, b.y];
  const progression = camp ? (engagement ? 0 : SIM.progression(camp)) : 0;

  // 1. la forme : chacun à sa place, selon que son camp a le ballon
  for (const j of SIM.joueurs) {
    const sien = camp === null ? false : j.cote === camp;
    j.vmax = 0.15; j.role = "forme";
    const [xo, yo] = SIM.versPropre(j.cote, b.x, b.y);
    if (j.gk) {
      const g = camp === null ? null : placeGardien(sien, ph, xo, yo);
      if (g === null && sien) { j.cx = arrivee[0]; j.cy = arrivee[1]; j.role = "porteur"; j.vmax = 0.3; }
      else { const [gx, gy] = g || [0.035, 0.5]; [j.cx, j.cy] = SIM.versEcran(j.cote, gx, gy); j.vmax = 0.32; }
      continue;
    }
    const [px, py] = placeJoueur(j.p, sien, progression, ph, T2D.consignes?.[j.cote]);
    let [x, y] = SIM.versEcran(j.cote, px, py);
    if (!engagement && camp !== null) {
      // le bloc coulisse vers le ballon en largeur, celui qui défend plus ;
      // et en profondeur : un bloc qui défend se tient près du ballon
      y += (b.y - 0.5) * (sien ? 0.12 : 0.22);
      if (!sien) x += (b.x - x) * 0.10;
      else {
        // une équipe fait quarante mètres de long : quand le ballon est
        // devant, la ligne arrière MONTE avec lui au lieu de rester devant
        // sa surface, et personne ne se retrouve seul à cinquante mètres
        const retard = (b.x - x) * j.sens;                 // > 0 : il est derrière le ballon
        if (retard > SIM.LONGUEUR) x += (retard - SIM.LONGUEUR) * j.sens;
      }
    }
    // le grain : personne n'est aligné au laser
    x += j.grain[0]; y += j.grain[1];
    j.cx = clamp(x, 0.02, 0.98); j.cy = clamp(y, 0.05, 0.95);
  }
  if (camp === null) return;

  const stop = ARRETS_JEU.has(ph.k);
  const porteur = SIM.porteur;

  // 2. le porteur vient au ballon (là où il arrive) ; à l'engagement, il
  //    reste au point central avec le ballon
  if (porteur) {
    porteur.cx = arrivee[0] - (b.attache ? 0 : 0.008 * porteur.sens); porteur.cy = arrivee[1];
    porteur.vmax = b.attache ? 0.34 : 0.36; porteur.role = "porteur";
  }

  if (ph.k === "but" && porteur) {
    // la joie : ses coéquipiers proches courent vers lui
    for (const j of SIM.joueurs)
      if (j.cote === camp && j !== porteur && !j.gk && SIM.dist(j.x, j.y, porteur.x, porteur.y) < 0.28) {
        j.cx = porteur.x + (j.x - porteur.x) * 0.25; j.cy = porteur.y + (j.y - porteur.y) * 0.25; j.vmax = 0.28; j.role = "fete";
      }
    return;
  }
  if (stop || engagement) return;

  // 3. le receveur est déjà en route vers là où la passe va tomber
  const receveur = SIM.receveur;
  if (receveur && receveur !== porteur) {
    const dest = SIM.destination(SIM.suivant);
    if (dest) {
      receveur.cx = receveur.cx + (dest[0] - receveur.cx) * 0.7;
      receveur.cy = receveur.cy + (dest[1] - receveur.cy) * 0.7;
      receveur.vmax = 0.28; receveur.role = "receveur";
    }
  }

  // 4. le soutien et les appels, côté ballon
  const siens = SIM.joueurs.filter(j => j.cote === camp && !j.gk && j !== porteur && j !== receveur);
  const distB = j => SIM.dist(j.cx, j.cy, arrivee[0], arrivee[1]);
  const soutiens = [...siens].sort((u, v) => distB(u) - distB(v)).slice(0, 2);
  for (const s of soutiens) {
    // se proposer, sans venir coller le porteur
    const d = distB(s);
    if (d > 0.09) { s.cx += (arrivee[0] - s.cx) * 0.22; s.cy += (arrivee[1] - s.cy) * 0.22; s.role = "soutien"; s.vmax = 0.2; }
  }
  const sens = porteur ? porteur.sens : SIM.sensDe(camp);
  // la ligne de hors-jeu : le dernier défenseur adverse (hors gardien)
  const adverses = SIM.joueurs.filter(j => j.cote !== camp && !j.gk);
  const ligne = adverses.length
    ? (sens > 0 ? Math.max(...adverses.map(j => j.x)) : Math.min(...adverses.map(j => j.x)))
    : (sens > 0 ? 0.9 : 0.1);
  if (progression > 0.3 && !SUR_LE_BUT.has(ph.k)) {
    for (const j of siens) {
      if (!SIM.APPEL.has(j.poste) || soutiens.includes(j)) continue;
      // chacun a sa fenêtre : un appel dure une seconde et demie, puis il
      // revient se replacer ; les fenêtres ne se recouvrent pas toutes
      const cycle = (SIM.horloge * 0.28 * SIM.tempo + j.dec) % 1;
      if (cycle > 0.42) continue;
      let ax = j.cx + 0.16 * sens, ay = j.cy + (0.5 - j.cy) * 0.35;
      // en jeu : on ne dépasse pas le dernier défenseur
      ax = sens > 0 ? Math.min(ax, ligne - 0.012) : Math.max(ax, ligne + 0.012);
      j.cx = clamp(ax, 0.03, 0.97); j.cy = clamp(ay, 0.06, 0.94); j.role = "appel"; j.vmax = 0.3;
    }
  }

  // 5. la défense : le plus proche presse, le second coupe la ligne de
  //    passe, le voisin du presseur couvre sa place
  if (adverses.length) {
    const distA = j => SIM.dist(j.x, j.y, b.x, b.y);
    const tri = [...adverses].sort((u, v) => distA(u) - distA(v));
    const presseur = tri[0];
    const dp = distA(presseur);
    const forme = [presseur.cx, presseur.cy];
    if (dp > 0.035) {
      presseur.cx = b.x + (presseur.x - b.x) * (0.03 / Math.max(dp, 0.03));
      presseur.cy = b.y + (presseur.y - b.y) * (0.03 / Math.max(dp, 0.03));
    } else { presseur.cx = b.x - 0.02 * sens; presseur.cy = b.y; }
    presseur.role = "presse"; presseur.vmax = 0.3;
    const second = tri[1];
    if (second) {
      if (receveur) {
        second.cx = (b.x + receveur.x) / 2; second.cy = (b.y + receveur.y) / 2;
      } else { second.cx += (b.x - second.cx) * 0.35; second.cy += (b.y - second.cy) * 0.35; }
      second.role = "coupe"; second.vmax = 0.24;
    }
    // la couverture : celui qui tenait la place la plus proche de celle
    // que le presseur a quittée vient la fermer
    const voisin = adverses.filter(j => j !== presseur && j !== second)
      .sort((u, v) => SIM.dist(u.cx, u.cy, forme[0], forme[1]) - SIM.dist(v.cx, v.cy, forme[0], forme[1]))[0];
    if (voisin) { voisin.cx += (forme[0] - voisin.cx) * 0.4; voisin.cy += (forme[1] - voisin.cy) * 0.4; voisin.role = "couvre"; voisin.vmax = 0.2; }
  }
};
SIM.APPEL = new Set(["Buteur", "Ailier", "Milieu offensif", "Milieu de couloir", "Milieu relayeur"]);

// Chacun court vers sa cible, à sa vitesse, sans à-coups : la vitesse
// suit la distance qui reste, plafonnée par ce qu'un joueur peut courir.
SIM.avancer = function (dt) {
  const frein = SIM.gel ? 0.25 : 1;
  for (const j of SIM.joueurs) {
    const dx = j.cx - j.x, dy = j.cy - j.y;
    const d = Math.hypot(dx, dy / SIM.ASPECT);
    const vmax = j.vmax * j.allure * SIM.tempo * frein;
    // vitesse voulue : proportionnelle à la distance, bornée
    const v = Math.min(vmax, d / 0.35);
    const ux = d > 1e-6 ? dx / d : 0, uy = d > 1e-6 ? dy / d : 0;
    const vx = ux * v, vy = uy * v * SIM.ASPECT;
    // l'inertie : une course ne repart pas dans l'autre sens d'un coup
    const k = Math.min(1, dt / 0.16);
    j.vx += (vx - j.vx) * k; j.vy += (vy - j.vy) * k;
    j.x += j.vx * dt; j.y += j.vy * dt;
    j.x = clamp(j.x, 0.015, 0.985); j.y = clamp(j.y, 0.04, 0.96);
  }
};

// Deux jetons ne se marchent pas dessus : trop proches, ils s'écartent
// (le porteur ne bouge pas, c'est l'autre qui se décale).
SIM.ecarter = function () {
  const J = SIM.joueurs, R = SIM.RAYON;
  for (let a = 0; a < J.length; a++) for (let c = a + 1; c < J.length; c++) {
    const u = J[a], v = J[c];
    const dx = v.x - u.x, dy = (v.y - u.y) / SIM.ASPECT;
    const d = Math.hypot(dx, dy);
    if (d >= R || d < 1e-6) continue;
    const pousse = (R - d) / 2;
    const nx = dx / d, ny = dy / d;
    const fu = u === SIM.porteur || u.gk ? 0 : 1, fv = v === SIM.porteur || v.gk ? 0 : 1;
    const tot = fu + fv || 1;
    u.x -= nx * pousse * 2 * fu / tot; u.y -= ny * pousse * 2 * fu / tot * SIM.ASPECT;
    v.x += nx * pousse * 2 * fv / tot; v.y += ny * pousse * 2 * fv / tot * SIM.ASPECT;
  }
};

SIM.bougerBallon = function () {
  const b = SIM.ballon;
  if (b.attache) {
    const p = b.attache;
    b.x = p.x + 0.012 * p.sens; b.y = p.y; b.vol = false;
    return;
  }
  if (!b.vol) return;
  const u = clamp((SIM.horloge - b.t0) / Math.max(1e-3, b.t1 - b.t0), 0, 1);
  const e = b.tir ? u : 1 - (1 - u) * (1 - u);          // une passe ralentit en arrivant
  b.x = b.de[0] + (b.a[0] - b.de[0]) * e;
  b.y = b.de[1] + (b.a[1] - b.de[1]) * e;
  if (u >= 1) b.vol = false;
};

SIM.poser = function () {
  for (const j of SIM.joueurs) {
    j.p.style.left = (j.x * 100).toFixed(2) + "%";
    j.p.style.top = (j.y * 100).toFixed(2) + "%";
  }
  const t = SIM.t;
  const bal = t && t.querySelector(".t2d-ballon"), ombre = t && t.querySelector(".t2d-ombre");
  if (!bal) return;
  const b = SIM.ballon;
  bal.style.left = (b.x * 100).toFixed(2) + "%"; bal.style.top = (b.y * 100).toFixed(2) + "%";
  ombre.style.left = bal.style.left; ombre.style.top = bal.style.top;
  bal.classList.toggle("en-vol", b.vol || !!b.attache);
};

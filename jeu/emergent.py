"""emergent.py — la voie B : un match qui se JOUE, sur un terrain.

Le moteur statistique (jeu/simulation.py) tire un dé par minute et
raconte ce qu'il a tiré.  Ici, rien n'est tiré d'avance : vingt-deux
joueurs ont une position, une vitesse, un profil physique (la fiche EA),
six attributs (la carte), et à chaque instant chacun décide — courir où,
passer à qui, frapper ou non — puis exécute avec une précision qui dépend
de ses attributs.  Le ballon a sa physique.  Un but est un ballon qui a
franchi la ligne parce qu'un appel a battu une ligne et qu'une frappe a
battu un gardien, pas parce qu'un dé l'a dit.

Ce fichier est un BAC À SABLE : il n'est branché sur aucun résultat du
jeu.  Il produit trois choses : les événements du match, une trace de
positions (pour regarder), et des statistiques agrégées (pour calibrer
contre la réalité — docs/MOTEUR_B.md).  Il ne deviendra le moteur du jeu
que quand son banc de calibration reproduira les distributions réelles.

Unités : mètres, secondes, mètres par seconde.  Le terrain fait 105 × 68,
le camp A attaque vers x = 105.  Tout est déterministe pour une graine.

    python3 -m jeu.emergent --jeu jeu/demo.sqlite --matchs 10      # le banc
    python3 -m jeu.emergent --jeu jeu/demo.sqlite --trace m.json   # une trace
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sqlite3
import sys
import pathlib
from dataclasses import dataclass, field

RACINE = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from jeu import scoring as S  # noqa: E402

# --------------------------------------------------------------------------
# Le terrain et le temps
# --------------------------------------------------------------------------
LONG, LARG = 105.0, 68.0
BUT_LARG = 7.32
BUT_HAUT = 2.44
SURFACE_X, SURFACE_Y = 16.5, 20.16          # la surface : 16,5 m de profondeur, 40,32 m de large
SIX_X, SIX_Y = 5.5, 9.16
PENALTY_X = 11.0
DT = 0.1                                    # le pas physique
DECISION = 2                                # une décision tous les DECISION pas (0,2 s)
TRACE_PAS = 4                               # une image de trace tous les TRACE_PAS pas (0,4 s)
MI_TEMPS = 45 * 60.0

# --------------------------------------------------------------------------
# Le physique : de la fiche EA aux mètres par seconde.
#
# La conversion est MESURÉE (donnees/physique/LISEZMOI.md) : dix points de
# vitesse EA valent 1,41 km/h de pointe réelle, la médiane des joueurs
# mesurés en Ligue des champions est 31,8 km/h pour une note médiane de 70.
# --------------------------------------------------------------------------
VITESSE_MEDIANE_KMH = 31.8
VITESSE_MEDIANE_EA = 70
KMH_PAR_POINT = 0.141


def vitesse_max(vit: float | None) -> float:
    v = VITESSE_MEDIANE_KMH + ((vit if vit is not None else VITESSE_MEDIANE_EA) - VITESSE_MEDIANE_EA) * KMH_PAR_POINT
    return max(6.5, min(10.5, v / 3.6))


def acceleration_max(acc: float | None) -> float:
    a = acc if acc is not None else 68
    return 2.6 + 0.045 * a                     # 40 → 4,4 m/s², 95 → 6,9 m/s²


BALLON_FROTTEMENT = 3.2                      # m/s², un ballon au sol qui roule
GRAVITE = 9.81
RAYON_CONTROLE = 1.1                         # à moins d'un mètre, on peut prendre le ballon
VITESSE_CONTROLE = 14.0                      # au-delà, il faut un contrôle (et il peut rater)
VITESSE_PASSE = (9.0, 22.0)                  # une passe courte, une longue
VITESSE_TIR = (20.0, 31.0)
SPRINT = 7.0                                 # m/s, au-delà c'est un sprint (les mesures FotMob)

FAMILLE_X = {"GK": 0.05, "DEF": 0.20, "MID": 0.40, "FWD": 0.62}


# --------------------------------------------------------------------------
# Les joueurs
# --------------------------------------------------------------------------
@dataclass
class Joueur:
    pid: int
    nom: str
    camp: int
    idx: int                                  # 0..21
    poste: str                                # poste tenu (avec côté)
    fam: str
    attributs: dict
    physique: dict
    x: float = 0.0
    y: float = 0.0
    vx: float = 0.0
    vy: float = 0.0
    home: tuple[float, float] = (0.0, 0.0)    # dans SON repère : x vers le but adverse
    vmax: float = 8.8
    amax: float = 5.5
    endurance_ea: float = 70.0
    fatigue: float = 0.0                      # 0 frais, 1 vidé
    cible: tuple[float, float] = (0.0, 0.0)
    role: str = "forme"
    horloge_appel: float = 0.0
    dernier_contact: float = -10.0
    travail_def: float = 0.5
    travail_att: float = 0.5
    appel_jusqua: float = -1.0                # une course lancée par la passe d'un coéquipier
    # stats
    distance: float = 0.0
    sprint: float = 0.0
    vmax_vue: float = 0.0
    touches: int = 0
    passes: int = 0
    passes_ok: int = 0
    tirs: int = 0
    tirs_cadres: int = 0
    buts: int = 0
    passes_d: int = 0
    tacles: int = 0
    interceptions: int = 0
    fautes: int = 0
    arrets: int = 0

    @property
    def gk(self) -> bool:
        return self.fam == "GK"

    def attr(self, k: str, defaut: float = 55.0) -> float:
        return float(self.attributs.get(k, defaut))

    def sens(self) -> int:
        return 1 if self.camp == 0 else -1

    # son repère : x = profondeur vers le but adverse, y = largeur, depuis sa gauche
    def propre(self, x: float, y: float) -> tuple[float, float]:
        return (x, y) if self.camp == 0 else (LONG - x, LARG - y)

    def absolu(self, xp: float, yp: float) -> tuple[float, float]:
        return (xp, yp) if self.camp == 0 else (LONG - xp, LARG - yp)


def _place(sur: list[dict], formation: str) -> list[tuple[float, float]]:
    """Les places de repos d'un onze (profondeur, largeur) en fractions,
    ligne par ligne — la silhouette de la formation (comme le terrain 2D)."""
    rangs = S.FORMATIONS_RANGS.get(formation)
    out = []
    if rangs and sum(len(r) for r in rangs) == len(sur):
        n = len(rangs)
        for r, rang in enumerate(rangs):
            x = FAMILLE_X["GK"] if r == 0 else 0.20 + (0.46 * (r - 1)) / max(1, n - 2)
            for k, poste in enumerate(rang):
                out.append((x + S.PROFONDEUR_POSTE.get(poste, 0.0), (k + 1) / (len(rang) + 1)))
        return out
    pris: dict[str, int] = {}
    total: dict[str, int] = {}
    for j in sur:
        total[j.get("fam", "MID")] = total.get(j.get("fam", "MID"), 0) + 1
    for j in sur:
        f = j.get("fam", "MID")
        k = pris.get(f, 0)
        pris[f] = k + 1
        out.append((FAMILLE_X.get(f, 0.4), (k + 1) / (total[f] + 1)))
    return out


def joueurs_de(sur: list[dict], camp: int, formation: str) -> list[Joueur]:
    places = _place(sur, formation)
    out = []
    for i, j in enumerate(sur):
        ph = j.get("physique") or {}
        vit = ph.get("vit") if "vit" in ph else (
            (ph.get("acceleration", 68) + ph.get("vitesse_pointe", 68)) / 2 if ph else None)
        acc = ph.get("acceleration", (vit if vit is not None else 68))
        px, py = places[i]
        jo = Joueur(pid=j["pid"], nom=j.get("nom", str(j["pid"])), camp=camp, idx=camp * 11 + i,
                    poste=j.get("slot") or j.get("poste", "Milieu relayeur"),
                    fam=j.get("fam") or S.FAMILLE_POSTE.get(j.get("slot") or j.get("poste", ""), "MID"),
                    attributs=dict(j.get("attributs") or {}), physique=ph,
                    home=(px * LONG, py * LARG), vmax=vitesse_max(vit), amax=acceleration_max(acc),
                    endurance_ea=float(ph.get("end", ph.get("endurance", 70)) or 70))
        jo.travail_def, jo.travail_att = travail_de(j, "def"), travail_de(j, "att")
        if jo.gk:
            jo.vmax = min(jo.vmax, 8.0)
        out.append(jo)
    return out


# --------------------------------------------------------------------------
# Le ballon
# --------------------------------------------------------------------------
@dataclass
class Ballon:
    x: float = LONG / 2
    y: float = LARG / 2
    z: float = 0.0
    vx: float = 0.0
    vy: float = 0.0
    vz: float = 0.0
    porteur: Joueur | None = None
    dernier: Joueur | None = None             # le dernier à l'avoir touché
    dernier_camp: int | None = None
    t_kick: float = -10.0
    passe_vers: Joueur | None = None          # la passe en cours : à qui
    hors_jeu_au_kick: set = field(default_factory=set)   # les pids hors jeu à l'instant de la passe

    def vitesse(self) -> float:
        return math.hypot(self.vx, self.vy)


# --------------------------------------------------------------------------
# Le match
# --------------------------------------------------------------------------
# Ce qu'un manager règle, lu par la forme et les rôles (les mêmes mots que
# simulation.Tactique) :
#   bloc     haut : la défense se tient six mètres derrière le ballon et
#            on presse en un pour un dans le camp adverse ; bas : seize
#            mètres derrière, jamais au-delà du milieu, on contient.
#   tempo    possession : on garde le ballon et on passe court ; direct :
#            on lâche vite et on joue long.
#   risque   offensif : plus d'appels et de projection ; prudent : moins.
TACTIQUE_DEFAUT = {"bloc": "median", "tempo": "equilibre", "risque": "equilibre",
                   "lateraux": "couloir", "ailiers": "equilibre", "milieux": "equilibre", "attaquants": "equilibre"}
# Le travail sans ballon (work rate) : "bas", "moyen", "haut".  Lu dans la
# fiche EA quand elle l'a ; sinon deviné sur les attributs (un attaquant
# qui défend bien revient, un latéral qui crée bien monte).
TRAVAIL = {"bas": 0.0, "moyen": 0.5, "haut": 1.0}


def travail_de(j: dict, sens: str) -> float:
    ph = j.get("physique") or {}
    v = ph.get("wr_def" if sens == "def" else "wr_att")
    if v in TRAVAIL:
        return TRAVAIL[v]
    a = j.get("attributs") or {}
    if sens == "def":
        return max(0.0, min(1.0, (float(a.get("DEF", 55)) - 40.0) / 45.0))
    return max(0.0, min(1.0, (float(a.get("CRE", 55)) * 0.5 + float(a.get("DRI", 55)) * 0.5 - 40.0) / 45.0))


COLLECTIF_MANUEL = RACINE / "jeu" / "collectif_manuel.json"


def cohesion(jeu, pids: list[int], team_id: int | None = None) -> float:
    """Le collectif d'un onze, lu dans la saison : la part des matchs du
    club que chaque paire a commencés ENSEMBLE, en moyenne sur les
    cinquante-cinq paires, étirée pour que l'onze le plus stable des huit
    championnats vaille 1 et un onze qui tourne à chaque match 0.  C'est
    une mesure d'habitude, pas de style : un club qui rode le même onze
    depuis août se connaît."""
    if len(pids) < 2:
        return 0.0
    marks = ",".join("?" * len(pids))
    par_match: dict[int, dict[int, float]] = {}
    for mid, pid, minutes in jeu.execute(f"SELECT match_id, player_id, minutes FROM prestation WHERE player_id IN ({marks})", pids):
        par_match.setdefault(mid, {})[pid] = float(minutes or 0)
    if team_id is not None:
        nm = jeu.execute("""SELECT COUNT(*) FROM prestation WHERE team_id=? AND entrant=0 AND minutes >= 60""",
                         (team_id,)).fetchone()[0] / 11.0
    else:
        nm = float(len(par_match))
    if nm < 3:
        return 0.5
    paires: dict[tuple[int, int], float] = {}
    for jeu_m in par_match.values():
        ps = sorted(jeu_m)
        for i in range(len(ps)):
            for k in range(i + 1, len(ps)):
                paires[(ps[i], ps[k])] = paires.get((ps[i], ps[k]), 0.0) + min(jeu_m[ps[i]], jeu_m[ps[k]])
    n = len(pids) * (len(pids) - 1) / 2
    part = sum(paires.values()) / n / (nm * 90.0)
    return round(max(0.0, min(1.0, (part - 0.25) / 0.35)), 3)


def collectif_de(jeu, team_id: int, pids: list[int]) -> float:
    """Le collectif d'un club : la valeur écrite à la main dans
    jeu/collectif_manuel.json quand il y en a une (le manager du jeu sait
    qu'un PSG combine et qu'un Real est une somme d'individualités, la
    saison ne le dit pas toujours), sinon la mesure sur la saison."""
    try:
        table = json.loads(COLLECTIF_MANUEL.read_text(encoding="utf-8")) if COLLECTIF_MANUEL.exists() else {}
    except (OSError, ValueError):
        table = {}
    nom = (jeu.execute("SELECT nom FROM club WHERE team_id=?", (team_id,)).fetchone() or [""])[0]
    for cle in (str(team_id), nom):
        v = table.get(cle)
        if isinstance(v, (int, float)):
            return max(0.0, min(1.0, float(v)))
    return cohesion(jeu, pids, team_id)


class Match:
    def __init__(self, sur_a: list[dict], sur_b: list[dict], formation_a: str = "4-3-3",
                 formation_b: str = "4-3-3", graine: int = 1, minutes: float = 90.0,
                 noms: tuple[str, str] = ("A", "B"), trace: bool = True,
                 tactiques: tuple[dict | None, dict | None] = (None, None),
                 collectif: tuple[float, float] = (0.6, 0.6)):
        self.rs = random.Random(graine)
        self.tac = [dict(TACTIQUE_DEFAUT) | (tactiques[0] or {}), dict(TACTIQUE_DEFAUT) | (tactiques[1] or {})]
        self.collectif = list(collectif)
        self.ligne_def = [FAMILLE_X["DEF"] * LONG, FAMILLE_X["DEF"] * LONG]   # la profondeur de chaque défense, dans son repère
        self.joueurs = joueurs_de(sur_a, 0, formation_a) + joueurs_de(sur_b, 1, formation_b)
        self.camp = [[j for j in self.joueurs if j.camp == 0], [j for j in self.joueurs if j.camp == 1]]
        self.noms = noms
        self.ballon = Ballon()
        self.t = 0.0
        self.duree = minutes * 60.0
        self.mi_temps = min(MI_TEMPS, self.duree / 2)
        self.periode = 1
        self.score = [0, 0]
        self.evenements: list[dict] = []
        self.trace: list[list[int]] = [] if trace else None
        self.pas = 0
        self.possession = [0.0, 0.0]
        self.arret: dict | None = None        # un arrêt de jeu en cours : {"k", "t", "camp", "x", "y"}
        self.camp_engagement = 0
        self.dist = [[0.0] * 22 for _ in range(22)]
        self.stats = {"passes": [0, 0], "passes_ok": [0, 0], "tirs": [0, 0], "cadres": [0, 0], "corners": [0, 0],
                      "fautes": [0, 0], "horsjeu": [0, 0], "touches_ligne": [0, 0], "xg": [0.0, 0.0],
                      "jaunes": [0, 0], "rouges": [0, 0], "tacles": [0, 0], "interceptions": [0, 0]}
        self.jaunes: dict[int, int] = {}
        self.exclus: set[int] = set()
        self._engagement(0)

    # -- outils ------------------------------------------------------------------
    def but_de(self, camp: int) -> tuple[float, float]:
        """Le but que le camp ATTAQUE."""
        return (LONG, LARG / 2) if camp == 0 else (0.0, LARG / 2)

    def actifs(self, camp: int) -> list[Joueur]:
        return [j for j in self.camp[camp] if j.pid not in self.exclus]

    def evt(self, k: str, **kw):
        e = {"k": k, "t": round(self.t, 1), "minute": int(self.t // 60) + 1} | kw
        self.evenements.append(e)
        return e

    def _distances(self):
        J = self.joueurs
        for a in range(22):
            ja = J[a]
            for b in range(a + 1, 22):
                jb = J[b]
                d = math.hypot(ja.x - jb.x, ja.y - jb.y)
                self.dist[a][b] = d
                self.dist[b][a] = d

    def d_ballon(self, j: Joueur) -> float:
        """La distance du joueur au ballon — au plus près du SEGMENT que le
        ballon vient de parcourir, pas seulement à son point d'arrivée :
        une frappe avance de deux mètres et demi par pas."""
        b = self.ballon
        x0, y0 = getattr(self, "ballon_avant", (b.x, b.y))
        dx, dy = b.x - x0, b.y - y0
        n2 = dx * dx + dy * dy
        if n2 < 1e-6:
            return math.hypot(j.x - b.x, j.y - b.y)
        t = max(0.0, min(1.0, ((j.x - x0) * dx + (j.y - y0) * dy) / n2))
        return math.hypot(j.x - (x0 + t * dx), j.y - (y0 + t * dy))

    def plus_proche(self, camp: int, x: float, y: float, sauf: Joueur | None = None,
                    gk: bool = True) -> tuple[Joueur | None, float]:
        best, bd = None, 1e9
        for j in self.actifs(camp):
            if j is sauf or (not gk and j.gk):
                continue
            d = math.hypot(j.x - x, j.y - y)
            if d < bd:
                best, bd = j, d
        return best, bd

    def ligne_horsjeu(self, camp_att: int) -> float:
        """La ligne de hors-jeu que le camp attaquant affronte : l'avant-
        dernier défenseur (en x absolu)."""
        xs = sorted((j.x for j in self.actifs(1 - camp_att)), reverse=(camp_att == 0))
        if len(xs) < 2:
            return LONG if camp_att == 0 else 0.0
        ligne = xs[1]
        # jamais dans son propre camp
        return max(ligne, LONG / 2) if camp_att == 0 else min(ligne, LONG / 2)

    def hors_jeu(self, j: Joueur, xb: float) -> bool:
        ligne = self.ligne_horsjeu(j.camp)
        if j.camp == 0:
            return j.x > ligne and j.x > xb and j.x > LONG / 2
        return j.x < ligne and j.x < xb and j.x < LONG / 2

    # -- coups d'envoi et arrêts -------------------------------------------------
    def _replacer(self, camp_en_possession: int | None = None, engagement: bool = False):
        for j in self.joueurs:
            xp, yp = j.home
            if engagement:
                xp = min(xp, LONG / 2 - 1.0)
            j.x, j.y = j.absolu(xp, yp)
            j.vx = j.vy = 0.0

    def _engagement(self, camp: int, immediat: bool = False):
        if immediat or self.t == 0.0:
            self._replacer(engagement=True)
        b = self.ballon
        b.x, b.y, b.z = LONG / 2, LARG / 2, 0.0
        b.vx = b.vy = b.vz = 0.0
        b.porteur = None
        b.passe_vers = None
        tireur = min((j for j in self.actifs(camp) if j.fam in ("FWD", "MID")),
                     key=lambda j: math.hypot(j.x - b.x, j.y - b.y), default=None)
        if tireur and (immediat or self.t == 0.0):
            tireur.x, tireur.y = LONG / 2 - 0.6 * tireur.sens(), LARG / 2
        self.arret = {"k": "engagement", "t": self.t, "camp": camp, "x": b.x, "y": b.y, "tireur": tireur,
                      "delai": 40.0 if self.evenements and self.evenements[-1]["k"] == "but" else 3.0}

    def _arret(self, k: str, camp: int, x: float, y: float, delai: float):
        """Un arrêt de jeu : le ballon est posé, le camp reprend après `delai`.
        Le tireur est choisi tout de suite et MARCHE au ballon ; personne
        n'est téléporté."""
        b = self.ballon
        b.x, b.y, b.z = x, y, 0.0
        b.vx = b.vy = b.vz = 0.0
        b.porteur = None
        b.passe_vers = None
        b.t_kick = self.t
        self.dernier_tir = None
        tireur = None
        if k == "penalty":
            tireur = max((j for j in self.actifs(camp) if not j.gk), key=lambda j: j.attr("FIN"), default=None)
        elif k == "corner":
            tireur = max((j for j in self.actifs(camp) if not j.gk), key=lambda j: j.attr("CRE"), default=None)
        elif k == "sortie_but":
            tireur = next((j for j in self.actifs(camp) if j.gk), None)
        elif k == "relance":
            tireur = next((j for j in self.actifs(camp) if j.gk), None)
        if tireur is None:
            tireur, _ = self.plus_proche(camp, x, y, gk=(k == "sortie_but"))
        self.arret = {"k": k, "t": self.t, "camp": camp, "x": x, "y": y, "delai": delai, "tireur": tireur}

    def _reprise(self):
        """Le coup de pied de reprise : qui tire, et quoi."""
        a = self.arret
        self.arret = None
        camp = a["camp"]
        b = self.ballon
        k = a["k"]
        if k == "engagement":
            j, _ = self.plus_proche(camp, b.x, b.y, gk=False)
            if j:
                # un retrait vers un milieu
                cible = min((x for x in self.actifs(camp) if x is not j and not x.gk),
                            key=lambda x: math.hypot(x.x - b.x, x.y - b.y), default=None)
                if cible:
                    self._passer(j, cible, courte=True)
            return
        tireur = a.get("tireur")
        if tireur is not None and tireur.pid in self.exclus:
            tireur = None
        if k == "penalty":
            tireur = tireur or max((x for x in self.actifs(camp) if not x.gk), key=lambda x: x.attr("FIN"))
            self._frapper(tireur, penalty=True)
            return
        if k == "corner":
            tireur = tireur or max((x for x in self.actifs(camp) if not x.gk), key=lambda x: x.attr("CRE"))
            self._centrer(tireur)
            return
        # coup franc, sortie de but, touche : le tireur joue court, ou long si pressé
        j = tireur or self.plus_proche(camp, b.x, b.y)[0]
        if j is None:
            return
        b.porteur = j
        j.dernier_contact = self.t
        # dans les 30 m : on peut frapper
        bx, by = self.but_de(camp)
        if k == "coup_franc" and math.hypot(bx - b.x, by - b.y) < 26 and self.rs.random() < 0.35:
            self._frapper(j, coup_franc=True)
            return
        self._decider_porteur(j, force=True)

    # -- le pas de temps -----------------------------------------------------------
    def jouer(self) -> dict:
        while self.t < self.duree:
            self.pas_de_temps()
        self.evt("fin", score=list(self.score))
        return self.resume()

    def pas_de_temps(self):
        self.pas += 1
        self.t += DT
        # la mi-temps
        if self.periode == 1 and self.t >= self.mi_temps:
            self.periode = 2
            self.evt("mi_temps", score=list(self.score))
            self._engagement(1 - self.camp_engagement, immediat=True)
        decision = self.pas % DECISION == 0
        if decision:
            self._distances()
        b = self.ballon
        if self.arret:
            a = self.arret
            tireur = a.get("tireur")
            if decision:
                # tout le monde prend la forme de la reprise, au pas ; le tireur va au ballon
                if a["k"] == "engagement":
                    for j in self.joueurs:
                        xp, yp = j.home
                        j.cible = j.absolu(min(xp, LONG / 2 - 1.0), yp)
                        j.role = "forme"
                else:
                    for camp in (0, 1):
                        self._forme(camp, a["camp"])
                    self._gardiens(a["camp"])
                    self._espacer()
                if tireur is not None and tireur.pid not in self.exclus:
                    tireur.cible = (b.x - 0.7 * tireur.sens(), b.y)
                    tireur.role = "porteur"
            pret = tireur is None or math.hypot(tireur.x - b.x, tireur.y - b.y) < 1.6
            if self.t - a["t"] >= a["delai"] and pret:
                self._reprise()
            self._bouger_joueurs(decision, gel=True)
        else:
            if decision:
                self._decisions()
            self._bouger_joueurs(decision)
            self._bouger_ballon()
            self._contacts()
            self._regles()
        if b.porteur is not None:
            self.possession[b.porteur.camp] += DT
        if self.trace is not None and self.pas % TRACE_PAS == 0:
            self.trace.append([int(round(self.t * 10)), int(round(b.x * 10)), int(round(b.y * 10)), int(round(b.z * 10)), 1 if self.arret else 0]
                              + [v for j in self.joueurs for v in (int(round(j.x * 10)), int(round(j.y * 10)))])

    # -- les décisions -------------------------------------------------------------
    def _decisions(self):
        b = self.ballon
        att = b.porteur.camp if b.porteur else (b.dernier_camp if b.dernier_camp is not None else 0)
        # le porteur
        if b.porteur is not None:
            self._decider_porteur(b.porteur)
        # les autres : la forme, puis les rôles
        for camp in (0, 1):
            self._forme(camp, att)
        self._roles_attaque(att)
        self._roles_defense(1 - att)
        self._ballon_libre()
        self._gardiens(att)
        self._espacer()

    def _forme(self, camp: int, att: int):
        b = self.ballon
        sien = camp == att
        bx, by = b.x, b.y
        # la profondeur de chaque ligne, vue du camp : la défense se tient
        # onze mètres derrière le ballon quand elle défend (jamais plus bas
        # que sa surface, jamais plus haut que le milieu), quinze mètres
        # derrière quand elle attaque ; le milieu et l'attaque s'étagent
        # devant elle, en un bloc de trente mètres
        bxp0 = bx if camp == 0 else LONG - bx
        tac = self.tac[camp]
        bloc = tac["bloc"]
        if sien:
            recul = {"haut": 11.0, "median": 15.0, "bas": 19.0}[bloc]
            ligne_def = max(18.0, min({"haut": 60.0, "median": 55.0, "bas": 45.0}[bloc], bxp0 - recul))
            saut = 14.0 if tac["milieux"] == "projection" else 16.0
            etage = {"DEF": ligne_def, "MID": ligne_def + saut, "FWD": ligne_def + 32.0}
        else:
            recul = {"haut": 6.0, "median": 11.0, "bas": 16.0}[bloc]
            plafond = {"haut": 52.0, "median": 45.0, "bas": 35.0}[bloc]
            ligne_def = max(8.0, min(plafond, bxp0 - recul))
            etage = {"DEF": ligne_def, "MID": min(ligne_def + 11.0, bxp0 + 3.0), "FWD": min(ligne_def + 24.0, bxp0 + 8.0)}
        self.ligne_def[camp] = ligne_def
        base = {"DEF": FAMILLE_X["DEF"] * LONG, "MID": FAMILLE_X["MID"] * LONG, "FWD": FAMILLE_X["FWD"] * LONG}
        for j in self.actifs(camp):
            if j.gk:
                continue
            xp, yp = j.home
            bxp, byp = j.propre(bx, by)
            # sa place dans sa ligne : l'écart qu'il a au repos avec la ligne de sa famille
            x = etage.get(j.fam, etage["MID"]) + (xp - base.get(j.fam, base["MID"])) * 0.6
            lateral = j.fam == "DEF" and abs(yp - LARG / 2) > 15.0
            if sien:
                # le travail offensif : un latéral qui monte, un milieu qui se projette
                if lateral and tac["lateraux"] != "bas":
                    x += 6.0 + 10.0 * j.travail_att
                elif lateral:
                    x -= 2.0
                if j.fam == "MID" and (tac["milieux"] == "projection" or j.travail_att > 0.7):
                    x += 5.0
            else:
                # le travail défensif : un attaquant qui revient, un milieu qui se replie
                if j.fam == "FWD":
                    x = etage["FWD"] - 10.0 * j.travail_def
                elif j.fam == "MID" and tac["milieux"] == "bas":
                    x -= 3.0
            # la largeur coulisse vers le ballon, plus quand on défend ; un
            # ailier « intérieur » rentre, un ailier « ligne » tient la touche
            y = yp + (byp - LARG / 2) * (0.25 if sien else 0.45)
            if sien and j.fam == "FWD" and abs(yp - LARG / 2) > 14.0:
                if tac["ailiers"] == "interieur":
                    y += (LARG / 2 - yp) * 0.4
                elif tac["ailiers"] == "ligne":
                    y = yp + (byp - LARG / 2) * 0.1
            # le collectif : un latéral qui a dépassé son ailier, l'ailier prend sa place (permutation)
            if sien and lateral and self.collectif[camp] > 0.6:
                ailier = next((o for o in self.actifs(camp) if o.fam == "FWD" and abs(o.home[1] - yp) < 12.0 and abs(o.home[1] - LARG / 2) > 14.0), None)
                if ailier is not None:
                    lx = j.propre(j.x, j.y)[0]
                    ax = ailier.propre(ailier.x, ailier.y)[0]
                    if lx > ax + 3.0:
                        ailier.cible = ailier.absolu(max(2.0, min(LONG - 2.0, x - 8.0)), max(2.0, min(LARG - 2.0, y)))
                        ailier.role = "forme"
                        ailier.appel_jusqua = -1.0
            nx, ny = j.absolu(max(2.0, min(LONG - 2.0, x)), max(2.0, min(LARG - 2.0, y)))
            # la forme se lit lissée : une cible qui saute à chaque tic fait des zigzags
            if j.role == "forme":
                nx, ny = j.cible[0] * 0.6 + nx * 0.4, j.cible[1] * 0.6 + ny * 0.4
            j.cible = (nx, ny)
            j.role = "forme"

    def _roles_attaque(self, att: int):
        b = self.ballon
        porteur = b.porteur
        siens = [j for j in self.actifs(att) if not j.gk and j is not porteur]
        if not siens:
            return
        bx, by = b.x, b.y
        gx, gy = self.but_de(att)
        # le receveur d'une passe en cours va au ballon
        if b.passe_vers is not None and b.passe_vers.pid not in self.exclus:
            r = b.passe_vers
            r.cible = self._point_de_reception(r)
            r.role = "receveur"
        # deux soutiens : les plus proches, à dix mètres, jamais derrière un adversaire
        soutiens = sorted(siens, key=lambda j: math.hypot(j.x - bx, j.y - by))[:2]
        for k, s in enumerate(soutiens):
            if s.role == "receveur":
                continue
            ang = (0.9 if k == 0 else -0.9) * (1 if s.y >= by else -1)
            dx, dy = gx - bx, gy - by
            n = math.hypot(dx, dy) or 1.0
            ux, uy = dx / n, dy / n
            ca, sa = math.cos(ang), math.sin(ang)
            ray = 14.0 - 3.0 * self.collectif[att]
            s.cible = (max(2.0, min(LONG - 2.0, bx + ray * (ux * ca - uy * sa))),
                       max(2.0, min(LARG - 2.0, by + ray * (ux * sa + uy * ca))))
            s.role = "soutien"
        # les appels : attaquants et ailiers, dans le dos, en restant en jeu ;
        # plus souvent quand on prend des risques, et le troisième homme part
        # sur la passe d'un coéquipier quand le collectif le permet
        sens = 1 if att == 0 else -1
        ligne = self.ligne_horsjeu(att)
        avance = (bx - LONG / 2) * sens
        risque = {"offensif": 1.4, "equilibre": 1.0, "prudent": 0.7}[self.tac[att]["risque"]]
        if self.tac[att]["attaquants"] == "profondeur":
            risque *= 1.3
        for j in siens:
            if j.role != "forme" or j.fam not in ("FWD", "MID"):
                continue
            if avance < -10:
                continue
            fenetre = (self.t * 0.11 + j.idx * 0.37) % 1.0
            lance = j.appel_jusqua > self.t
            if lance or (fenetre < 0.22 * risque and j.fam == "FWD") or (fenetre < 0.10 * risque and j.fam == "MID"):
                x = j.cible[0] + 14.0 * sens
                # en jeu : un pas derrière la ligne
                x = min(x, ligne - 1.6) if sens == 1 else max(x, ligne + 1.6)
                y = j.cible[1] + (gy - j.cible[1]) * 0.35
                j.cible = (max(2.0, min(LONG - 2.0, x)), y)
                j.role = "appel"

    ESPACE = 8.0                                 # deux coéquipiers ne visent jamais le même mètre carré

    def _espacer(self):
        """Deux coéquipiers dont les cibles sont à moins de ESPACE mètres
        s'écartent l'un de l'autre : un onze occupe le terrain, il ne
        s'entasse pas autour du ballon.  Ceux qui vont au ballon (porteur,
        receveur, presseur, chasseur) gardent leur cible."""
        fixes = {"porteur", "receveur", "presse", "chasse", "gardien"}
        for camp in (0, 1):
            js = [j for j in self.actifs(camp) if not j.gk]
            for _ in range(2):
                for a in range(len(js)):
                    ja = js[a]
                    for c in range(a + 1, len(js)):
                        jb = js[c]
                        dx, dy = jb.cible[0] - ja.cible[0], jb.cible[1] - ja.cible[1]
                        d = math.hypot(dx, dy)
                        if d >= self.ESPACE:
                            continue
                        if d < 0.1:
                            dx, dy, d = 1.0, 0.0, 1.0
                        pousse = (self.ESPACE - d) / 2
                        ux, uy = dx / d, dy / d
                        fa, fb = ja.role not in fixes, jb.role not in fixes
                        if not fa and not fb:
                            continue
                        ka = pousse * (2.0 if not fb else 1.0) if fa else 0.0
                        kb = pousse * (2.0 if not fa else 1.0) if fb else 0.0
                        ja.cible = (max(1.0, min(LONG - 1.0, ja.cible[0] - ux * ka)), max(1.0, min(LARG - 1.0, ja.cible[1] - uy * ka)))
                        jb.cible = (max(1.0, min(LONG - 1.0, jb.cible[0] + ux * kb)), max(1.0, min(LARG - 1.0, jb.cible[1] + uy * kb)))

    def _ballon_libre(self):
        """Un ballon que personne ne tient : le plus proche de chaque camp
        y court, là où il va s'arrêter."""
        b = self.ballon
        if b.porteur is not None:
            return
        v = b.vitesse()
        if v > 0.5:
            s_ = (v * v) / (2 * BALLON_FROTTEMENT)
            px, py = b.x + b.vx / v * s_, b.y + b.vy / v * s_
        else:
            px, py = b.x, b.y
        px, py = max(0.5, min(LONG - 0.5, px)), max(0.5, min(LARG - 0.5, py))
        for camp in (0, 1):
            if b.passe_vers is not None and b.passe_vers.camp == camp:
                continue                          # le receveur y va déjà
            j, d = self.plus_proche(camp, px, py, gk=False)
            if j is not None and j.fam == "DEF":
                pxp = px if camp == 0 else LONG - px
                if pxp - self.ligne_def[camp] > 22.0:
                    autre, da = min(((o, math.hypot(o.x - px, o.y - py)) for o in self.actifs(camp) if o.fam not in ("DEF", "GK")),
                                    key=lambda t: t[1], default=(None, 1e9))
                    if autre is not None and da < d + 12.0:
                        j = autre
            if j is not None:
                j.cible = (px, py)
                j.role = "chasse"

    def _roles_defense(self, df: int):
        b = self.ballon
        bx, by = b.x, b.y
        siens = [j for j in self.actifs(df) if not j.gk]
        if not siens:
            return
        tri = sorted(siens, key=lambda j: math.hypot(j.x - bx, j.y - by))
        tac = self.tac[df]
        bxp0 = bx if df == 0 else LONG - bx        # le ballon, vu de la défense
        # un central ne part pas presser à trente mètres de sa ligne : le
        # premier non-défenseur à moins de quinze mètres y va à sa place
        p = tri[0]
        if p.fam == "DEF" and bxp0 - self.ligne_def[df] > 22.0:
            autre = next((j for j in tri[1:] if j.fam != "DEF" and math.hypot(j.x - bx, j.y - by) < 18.0), None)
            if autre is not None:
                p = autre
        mx, my = self.but_de(df)                   # son propre but : il se met entre le ballon et lui
        dx, dy = mx - bx, my - by
        n = math.hypot(dx, dy) or 1.0
        # un bloc bas contient à trois mètres tant que le ballon est loin ;
        # un bloc haut va au contact partout
        contient = 0.0 if b.porteur is None else {"haut": 1.0, "median": 1.3, "bas": 3.0 if bxp0 > 45 else 1.5}[tac["bloc"]]
        p.cible = (bx + b.vx * 0.4 + dx / n * contient, by + b.vy * 0.4 + dy / n * contient)
        p.role = "presse"
        tri = [p] + [j for j in tri if j is not p]
        # le second coupe la ligne vers le soutien le plus dangereux
        att = 1 - df
        gx, gy = self.but_de(att)
        cand = [j for j in self.actifs(att) if not j.gk and j is not b.porteur]
        if len(tri) > 1 and cand:
            danger = min(cand, key=lambda j: math.hypot(j.x - gx, j.y - gy))
            tri[1].cible = ((bx + danger.x) / 2, (by + danger.y) / 2)
            tri[1].role = "coupe"
        # le pressing en un pour un : bloc haut et ballon dans le camp
        # adverse, les deux suivants prennent chacun un homme au contact
        pris: set[int] = set()
        if tac["bloc"] == "haut" and bxp0 > LONG / 2 - 5:
            for j in tri[2:4]:
                adv = min((o for o in self.actifs(att) if not o.gk and o is not b.porteur and o.pid not in pris),
                          key=lambda o: math.hypot(o.x - j.x, o.y - j.y), default=None)
                if adv is not None and math.hypot(adv.x - j.x, adv.y - j.y) < 20.0:
                    pris.add(adv.pid)
                    j.cible = (adv.x + (mx - adv.x) / (math.hypot(mx - adv.x, my - adv.y) or 1.0) * 1.5,
                               adv.y + (my - adv.y) / (math.hypot(mx - adv.x, my - adv.y) or 1.0) * 1.5)
                    j.role = "presse"
        # les autres : marquage de zone, UN défenseur par attaquant — chacun
        # glisse vers l'adversaire libre le plus proche de sa place
        for j in tri[2:]:
            if j.role == "presse":
                continue
            adv, d = None, 1e9
            for o in self.actifs(att):
                if o.gk or o is b.porteur or o.pid in pris:
                    continue
                dd = math.hypot(o.x - j.cible[0], o.y - j.cible[1])
                if dd < d:
                    adv, d = o, dd
            if adv is not None and d < 15.0:
                pris.add(adv.pid)
                # entre l'adversaire et son but : à un mètre et demi dans sa
                # surface, à quatre mètres au milieu du terrain (une zone, pas
                # un marquage individuel)
                mx, my = self.but_de(df)
                dm = math.hypot(mx - adv.x, my - adv.y) or 1.0
                recul = 1.5 if dm < 22 else 4.0
                cx, cy = adv.x + (mx - adv.x) / dm * recul, adv.y + (my - adv.y) / dm * recul
                # un défenseur ne descend jamais sous sa ligne pour suivre un
                # homme : il tient l'alignement (et le hors-jeu), sauf dans sa
                # surface où il colle
                if j.fam == "DEF" and dm > 22:
                    cxp, cyp = j.propre(cx, cy)
                    cxp = max(cxp, self.ligne_def[df] - 1.0)
                    cx, cy = j.absolu(cxp, cyp)
                j.cible = (cx, cy)
                j.role = "marque"

    def _gardiens(self, att: int):
        b = self.ballon
        for camp in (0, 1):
            gk = next((j for j in self.actifs(camp) if j.gk), None)
            if gk is None:
                continue
            mx, my = self.but_de(1 - camp)          # son propre but
            dx, dy = b.x - mx, b.y - my
            d = math.hypot(dx, dy) or 1.0
            # sur la bissectrice, un peu devant sa ligne, plus loin quand le ballon est loin
            sortie = min(5.0, 1.0 + d * 0.06)
            x = mx + dx / d * sortie
            y = my + dy / d * sortie * 0.6
            # il sort sur un ballon libre dans sa surface si personne n'est plus près
            libre = b.porteur is None and b.vitesse() < 8
            dans = abs(b.x - mx) < SURFACE_X and abs(b.y - my) < SURFACE_Y
            if libre and dans:
                _, dd = self.plus_proche(1 - camp, b.x, b.y, gk=False)
                if math.hypot(gk.x - b.x, gk.y - b.y) < dd + 1.5:
                    x, y = b.x, b.y
            tir = self._tir_en_cours()
            if tir and tir["camp"] != camp and abs(b.vx) > 1.0:
                # où la frappe croise sa ligne
                tt = (gk.x - b.x) / b.vx
                if tt > 0:
                    y = max(my - 5.0, min(my + 5.0, b.y + b.vy * tt))
                    x = gk.x
            gk.cible = (x, y)
            gk.role = "gardien"

    def _point_de_reception(self, r: Joueur) -> tuple[float, float]:
        """Où le ballon en vol sera à portée : on avance le long de sa
        trajectoire jusqu'à un point que le receveur peut atteindre."""
        b = self.ballon
        x, y, vx, vy = b.x, b.y, b.vx, b.vy
        v = math.hypot(vx, vy)
        if v < 0.5:
            return (x, y)
        t = 0.0
        while t < 4.0:
            t += 0.2
            vv = max(0.0, v - BALLON_FROTTEMENT * t)
            s = v * t - 0.5 * BALLON_FROTTEMENT * t * t if vv > 0 else (v * v) / (2 * BALLON_FROTTEMENT)
            px, py = x + vx / v * s, y + vy / v * s
            if math.hypot(px - r.x, py - r.y) <= r.vmax * (1 - 0.15 * r.fatigue) * t + 1.0:
                return (px, py)
            if vv <= 0:
                return (px, py)
        return (px, py)

    # -- le porteur ----------------------------------------------------------------
    def _pression(self, j: Joueur) -> float:
        _, d = self.plus_proche(1 - j.camp, j.x, j.y, gk=False)
        return max(0.0, min(1.0, (6.0 - d) / 6.0))

    def _decider_porteur(self, j: Joueur, force: bool = False):
        b = self.ballon
        camp = j.camp
        gx, gy = self.but_de(camp)
        dbut = math.hypot(gx - j.x, gy - j.y)
        pression = self._pression(j)
        tenu = self.t - j.dernier_contact
        tac = self.tac[camp]
        coh = self.collectif[camp]
        tempo = {"possession": 1.25, "equilibre": 1.0, "direct": 0.7}[tac["tempo"]]
        # un temps de contrôle, plus court sous pression, plus court dans les
        # trente derniers mètres, plus court quand on joue direct
        garde = (1.8 + 2.6 * (1 - pression)) * (1.0 - 0.3 * j.attr("CON") / 99) * tempo
        if dbut < 32:
            garde *= 0.7
        if not force and tenu < garde:
            if not (dbut < 24 and tenu > 0.3):        # dans la zone de frappe, on ne réfléchit pas trois secondes
                return
        options: list[tuple[float, str, object]] = []
        # le bruit de décision : moins avec le sang-froid, moins dans un
        # collectif rodé (chacun sait ce que l'autre va faire)
        bruit = 0.25 * (1.0 - 0.5 * j.attr("CON") / 99) * (1.25 - 0.5 * coh)
        # -- frapper : une occasion se prend, surtout si rien ne bouche l'axe
        if dbut < 32 and not j.gk:
            ang = self._angle_but(j.x, j.y, camp)
            xg = self._xg(dbut, ang, pression)
            axe = self._axe_libre(j)
            val = 0.3 + 6.0 * xg * (0.6 + 0.8 * j.attr("FIN") / 99) + (0.2 if dbut < 16 else 0.0) - 0.3 * pression + 0.35 * axe * (1.0 if dbut < 22 else 0.2)
            options.append((val + self.rs.gauss(0, bruit), "tir", None))
        # -- passer
        for c in self.actifs(camp):
            if c is j:
                continue
            d = math.hypot(c.x - j.x, c.y - j.y)
            if d < 3.0 or d > 55.0:
                continue
            if c.gk and dbut < 60:
                continue
            gain = ((c.x - j.x) * j.sens()) / 35.0                          # la progression
            danger = 1.0 - math.hypot(gx - c.x, gy - c.y) / 105.0            # proche du but adverse
            _, libre = self.plus_proche(1 - camp, c.x, c.y, gk=False)
            couloir = self._couloir_libre(j, c)
            hj = self.hors_jeu(c, b.x)
            # l'homme libre près du but vaut de l'or ; le tempo direct aime les longues
            val = (0.25 + 1.4 * gain + 0.6 * danger + 0.1 * min(libre, 8.0) + 0.6 * couloir - 0.012 * d
                   - 0.025 * max(0.0, d - 22.0) * tempo - (0.5 if libre < 3.0 else 0.0)
                   + 0.5 * danger * min(libre, 10.0) / 10.0 * (0.6 + 0.4 * coh))
            if hj:
                val -= 3.0
            if c.gk:
                val -= 0.6
            val += self.rs.gauss(0, bruit)
            options.append((val, "passe", c))
        # -- centrer, depuis le couloir dans les trente derniers mètres
        if abs(j.y - LARG / 2) > 18.0 and (gx - j.x) * j.sens() < 32 and not j.gk:
            dans = [c for c in self.actifs(camp) if c is not j and math.hypot(gx - c.x, gy - c.y) < 22]
            if dans:
                val = 0.8 + 0.25 * len(dans) + 0.4 * j.attr("CRE") / 99 - 0.4 * pression
                options.append((val + self.rs.gauss(0, bruit), "centre", None))
        # -- conduire
        _, dev = self._espace_devant(j)
        # une somme d'individualités conduit plus qu'elle ne combine
        val = 0.7 + 0.06 * min(dev, 12.0) + 0.3 * j.attr("DRI") / 99 - 0.9 * pression + 0.35 * (1.0 - coh)
        if dbut < 40:
            val += 0.25
        options.append((val + self.rs.gauss(0, bruit), "conduite", None))
        # -- dégager sous pression dans son camp
        if pression > 0.5 and (j.x - LONG / 2) * j.sens() < -20:
            options.append((0.9 + self.rs.gauss(0, bruit), "degagement", None))
        options.sort(key=lambda o: -o[0])
        _, quoi, cible = options[0]
        if quoi == "tir":
            self._frapper(j)
        elif quoi == "passe":
            self._passer(j, cible)
        elif quoi == "degagement":
            self._degager(j)
        elif quoi == "centre":
            self._centrer(j)
        else:
            self._conduire(j)

    def _axe_libre(self, j: Joueur) -> float:
        """1 si personne ne bouche l'axe de frappe (le cône vers le but,
        gardien exclu), 0 si un défenseur est dedans."""
        gx, gy = self.but_de(j.camp)
        dx, dy = gx - j.x, gy - j.y
        n = math.hypot(dx, dy) or 1.0
        pire = 1.0
        for o in self.actifs(1 - j.camp):
            if o.gk:
                continue
            px, py = o.x - j.x, o.y - j.y
            t = (px * dx + py * dy) / (n * n)
            if t <= 0.0 or t >= 1.0:
                continue
            ecart = abs(px * dy - py * dx) / n
            pire = min(pire, max(0.0, (ecart - 0.6) / 2.0))
        return pire

    def _angle_but(self, x: float, y: float, camp: int) -> float:
        gx = LONG if camp == 0 else 0.0
        a1 = math.atan2(LARG / 2 - BUT_LARG / 2 - y, gx - x)
        a2 = math.atan2(LARG / 2 + BUT_LARG / 2 - y, gx - x)
        return abs(a2 - a1)

    def _xg(self, d: float, ang: float, pression: float) -> float:
        """Une lecture d'expected goal grossière : la distance et l'angle
        d'ouverture du but, sous pression."""
        base = 0.95 * math.exp(-0.135 * d) * (0.35 + 0.65 * min(1.0, ang / 0.6))
        return max(0.01, min(0.9, base * (1.0 - 0.45 * pression)))

    def _couloir_libre(self, de: Joueur, a: Joueur) -> float:
        """1 si personne n'est sur la ligne de passe, 0 si un adversaire
        est dedans."""
        dx, dy = a.x - de.x, a.y - de.y
        n = math.hypot(dx, dy) or 1.0
        pire = 1.0
        for o in self.actifs(1 - de.camp):
            px, py = o.x - de.x, o.y - de.y
            t = (px * dx + py * dy) / (n * n)
            if t <= 0.05 or t >= 0.95:
                continue
            ecart = abs(px * dy - py * dx) / n
            pire = min(pire, max(0.0, (ecart - 0.8) / 3.0))
        return pire

    def _espace_devant(self, j: Joueur) -> tuple[tuple[float, float], float]:
        gx, gy = self.but_de(j.camp)
        dx, dy = gx - j.x, gy - j.y
        n = math.hypot(dx, dy) or 1.0
        ux, uy = dx / n, dy / n
        # l'adversaire le plus proche devant, à moins de 60° de la direction du but
        best = 25.0
        for o in self.actifs(1 - j.camp):
            px, py = o.x - j.x, o.y - j.y
            d = math.hypot(px, py)
            if d < 0.1:
                best = 0.0
                continue
            if (px * ux + py * uy) / d > 0.5:
                best = min(best, d)
        return (ux, uy), best

    # -- les actions ---------------------------------------------------------------
    def _lacher(self, j: Joueur, vx: float, vy: float, vz: float = 0.0):
        b = self.ballon
        b.porteur = None
        b.dernier = j
        b.dernier_camp = j.camp
        b.t_kick = self.t
        b.vx, b.vy, b.vz = vx, vy, vz
        b.z = max(b.z, 0.0)
        j.touches += 1

    def _passer(self, j: Joueur, c: Joueur, courte: bool = False):
        b = self.ballon
        dx, dy = c.x - j.x, c.y - j.y
        d = math.hypot(dx, dy) or 1.0
        # on vise un peu devant un receveur qui court
        vise_x, vise_y = c.x + c.vx * min(1.2, d / 15.0), c.y + c.vy * min(1.2, d / 15.0)
        dx, dy = vise_x - j.x, vise_y - j.y
        d = math.hypot(dx, dy) or 1.0
        # la vitesse : assez pour arriver, pas plus
        v = math.sqrt(max(0.0, 2 * BALLON_FROTTEMENT * d)) + 1.0
        v = max(VITESSE_PASSE[0], min(VITESSE_PASSE[1], v))
        # la précision : l'erreur d'angle dépend de CRE/PRO, de la pression et de la distance
        pression = self._pression(j)
        precision = (j.attr("PRO") * 0.6 + j.attr("CRE") * 0.4) / 99
        sigma = math.radians(1.0 + 4.0 * (1 - precision) + 3.0 * pression + 0.04 * d)
        ang = math.atan2(dy, dx) + self.rs.gauss(0, sigma)
        vz = 0.0
        haut = d > 30 or (self._couloir_libre(j, c) < 0.2 and d > 15)
        if haut:
            # par-dessus : la portée en l'air vaut la distance (v = d·g / 2vz)
            vz = 6.0 + d * 0.1
            v = max(10.0, min(28.0, d * GRAVITE / (2 * vz)))
        j.passes += 1
        self.stats["passes"][j.camp] += 1
        self._lacher(j, v * math.cos(ang), v * math.sin(ang), vz)
        b.passe_vers = c
        # le troisième homme : sur une passe vers l'avant, un coéquipier bien
        # rodé part dans l'espace que la passe ouvre
        if self.collectif[j.camp] > 0.45 and (c.x - j.x) * j.sens() > 4.0 and self.rs.random() < self.collectif[j.camp] * 0.7:
            gx, gy = self.but_de(j.camp)
            tiers = [o for o in self.actifs(j.camp) if o not in (j, c) and not o.gk and o.fam in ("FWD", "MID")
                     and (o.x - c.x) * j.sens() > -8.0 and math.hypot(o.x - c.x, o.y - c.y) < 25.0]
            if tiers:
                min(tiers, key=lambda o: math.hypot(gx - o.x, gy - o.y)).appel_jusqua = self.t + 2.2
        b.hors_jeu_au_kick = {x.pid for x in self.actifs(j.camp) if x is not j and self.hors_jeu(x, b.x)}
        self.evt("passe", de=j.pid, a=c.pid, camp=j.camp, x=round(j.x, 1), y=round(j.y, 1), d=round(d, 1), haut=vz > 0, role=c.role)

    def _centrer(self, j: Joueur):
        gx, gy = self.but_de(j.camp)
        cx = gx - 9.0 * j.sens()
        cy = gy + self.rs.uniform(-6.0, 6.0)
        dx, dy = cx - j.x, cy - j.y
        d = math.hypot(dx, dy) or 1.0
        sigma = math.radians(4.0 + 8.0 * (1 - j.attr("CRE") / 99))
        ang = math.atan2(dy, dx) + self.rs.gauss(0, sigma)
        v = min(24.0, math.sqrt(2 * BALLON_FROTTEMENT * d) + 6.0)
        j.passes += 1
        self.stats["passes"][j.camp] += 1
        self._lacher(j, v * math.cos(ang), v * math.sin(ang), 6.5)
        self.ballon.passe_vers = None
        self.evt("centre", de=j.pid, camp=j.camp)

    def _degager(self, j: Joueur):
        gx, gy = self.but_de(j.camp)
        ang = math.atan2(gy - j.y + self.rs.uniform(-20, 20), gx - j.x) + self.rs.gauss(0, 0.15)
        self._lacher(j, 24.0 * math.cos(ang), 24.0 * math.sin(ang), 8.0)
        self.ballon.passe_vers = None
        self.evt("degagement", de=j.pid, camp=j.camp)

    def _conduire(self, j: Joueur):
        (ux, uy), dev = self._espace_devant(j)
        # on s'écarte du défenseur le plus proche
        o, d = self.plus_proche(1 - j.camp, j.x, j.y, gk=False)
        if o is not None and d < 6.0:
            ox, oy = j.x - o.x, j.y - o.y
            n = math.hypot(ox, oy) or 1.0
            ux, uy = ux * 0.6 + ox / n * 0.4, uy * 0.6 + oy / n * 0.4
            n = math.hypot(ux, uy) or 1.0
            ux, uy = ux / n, uy / n
        portee = 8.0 + 8.0 * (1 - j.attr("DRI") / 99) if dev > 6 else 3.0
        j.cible = (max(1.0, min(LONG - 1.0, j.x + ux * portee)), max(1.0, min(LARG - 1.0, j.y + uy * portee)))
        j.role = "porteur"

    def _frapper(self, j: Joueur, penalty: bool = False, coup_franc: bool = False):
        b = self.ballon
        camp = j.camp
        gx, gy = self.but_de(camp)
        d = math.hypot(gx - j.x, gy - j.y)
        pression = 0.0 if penalty or coup_franc else self._pression(j)
        ang = self._angle_but(j.x, j.y, camp)
        xg = 0.76 if penalty else self._xg(d, ang, pression)
        fin = j.attr("FIN") / 99
        # où il vise : un poteau, avec une erreur qui dépend de la finition et de la pression
        cote = self.rs.choice([-1, 1])
        vise_y = gy + cote * (BUT_LARG / 2 - 0.5) * self.rs.uniform(0.3, 1.0)
        sigma = math.radians(13.0 + 9.0 * (1 - fin) + 6.0 * pression + 0.3 * d)
        theta = math.atan2(vise_y - j.y, gx - j.x) + self.rs.gauss(0, sigma)
        v = VITESSE_TIR[0] + (VITESSE_TIR[1] - VITESSE_TIR[0]) * (0.4 + 0.6 * fin) * (1.0 - 0.3 * pression)
        # la hauteur : un tir tendu, parfois enlevé
        vz = max(0.0, self.rs.gauss(2.0 + 0.08 * d, 2.4 + 2.5 * (1 - fin) + 1.5 * pression))
        j.tirs += 1
        self.stats["tirs"][camp] += 1
        self.stats["xg"][camp] += xg
        self._lacher(j, v * math.cos(theta), v * math.sin(theta), vz)
        b.passe_vers = None
        self.evt("tir", de=j.pid, camp=camp, xg=round(xg, 3), d=round(d, 1), penalty=penalty)
        self.dernier_tir = {"de": j, "xg": xg, "t": self.t, "camp": camp}

    # -- le mouvement ----------------------------------------------------------------
    def _bouger_joueurs(self, decision: bool, gel: bool = False):
        b = self.ballon
        for j in self.joueurs:
            if j.pid in self.exclus:
                continue
            if gel:
                # à l'arrêt, chacun rejoint sa place au pas
                tx, ty = j.cible
                v_lim = 3.2 if j.role != "porteur" else 4.0
            else:
                tx, ty = j.cible
                v_lim = j.vmax * (1.0 - 0.12 * j.fatigue)
                # on ne sprinte que quand ça compte : au ballon, sur un appel, pour recevoir
                plafond = {"forme": 3.4, "marque": 4.2, "gardien": 6.0, "coupe": 5.5, "soutien": 5.5, "receveur": 7.5}.get(j.role)
                if j.role in ("presse", "chasse") and self.d_ballon(j) > 7.0:
                    plafond = 6.8                # on ne sprinte que pour les derniers mètres
                if plafond is not None:
                    plafond *= j.vmax / 8.83     # un rapide trotte plus vite aussi
                if j.role == "porteur":
                    plafond = j.vmax * 0.88      # balle au pied, on va moins vite
                if plafond is not None:
                    v_lim = min(v_lim, plafond)
            dx, dy = tx - j.x, ty - j.y
            d = math.hypot(dx, dy)
            # une zone morte : personne ne fait deux pas pour un mètre
            tol = 0.3 if j.role in ("porteur", "presse", "receveur", "gardien", "chasse") else 1.5
            if d < tol:
                vx_v = vy_v = 0.0
            else:
                v_v = min(v_lim, math.sqrt(2 * j.amax * d) * 0.9)
                vx_v, vy_v = dx / d * v_v, dy / d * v_v
            # l'accélération borne le changement de vitesse
            ax, ay = vx_v - j.vx, vy_v - j.vy
            a = math.hypot(ax, ay)
            amax = j.amax * (1.0 - 0.12 * j.fatigue) * DT
            if a > amax:
                ax, ay = ax / a * amax, ay / a * amax
            j.vx += ax
            j.vy += ay
            v = math.hypot(j.vx, j.vy)
            if v > v_lim:
                j.vx, j.vy = j.vx / v * v_lim, j.vy / v * v_lim
                v = v_lim
            j.x = max(-2.0, min(LONG + 2.0, j.x + j.vx * DT))
            j.y = max(-2.0, min(LARG + 2.0, j.y + j.vy * DT))
            pas = v * DT
            j.distance += pas
            if v > SPRINT:
                j.sprint += pas
            j.vmax_vue = max(j.vmax_vue, v)
            # l'usure : courir vite coûte, plus à qui a peu d'endurance
            cout = (0.00006 + 0.0011 * (v / 9.0) ** 3) * (1.0 + (70.0 - j.endurance_ea) / 100.0)
            j.fatigue = min(1.0, j.fatigue + cout * DT)
            # le porteur emmène le ballon
            if b.porteur is j:
                b.x, b.y = j.x + (j.vx * 0.12 if v > 0.5 else 0.0), j.y + (j.vy * 0.12 if v > 0.5 else 0.0)
                b.vx, b.vy, b.z, b.vz = j.vx, j.vy, 0.0, 0.0

    def _bouger_ballon(self):
        b = self.ballon
        self.ballon_avant = (b.x, b.y)
        if b.porteur is not None:
            return
        if b.z > 0.0 or b.vz > 0.0:
            b.vz -= GRAVITE * DT
            b.z += b.vz * DT
            if b.z <= 0.0:
                b.z = 0.0
                b.vz = -b.vz * 0.35 if b.vz < -2.0 else 0.0
                b.vx *= 0.45                     # l'herbe mange l'élan d'un ballon qui retombe
                b.vy *= 0.45
        else:
            v = b.vitesse()
            if v > 0:
                nv = max(0.0, v - BALLON_FROTTEMENT * DT)
                b.vx, b.vy = b.vx / v * nv, b.vy / v * nv
        b.x += b.vx * DT
        b.y += b.vy * DT

    # -- les contacts -----------------------------------------------------------------
    def _contacts(self):
        b = self.ballon
        if b.porteur is None:
            # qui prend le ballon ? le plus proche à portée, sauf celui qui vient de le lâcher
            cand = []
            for j in self.joueurs:
                if j.pid in self.exclus:
                    continue
                if j is b.dernier and self.t - b.t_kick < 0.4:
                    continue
                d = self.d_ballon(j)
                tir = self._tir_en_cours()
                v_b = b.vitesse()
                # un ballon qui file se prend moins facilement qu'un ballon qui roule ;
                # celui à qui la passe est adressée sait où la prendre
                portee = RAYON_CONTROLE if v_b < 8.0 else (0.5 if j is not b.passe_vers else 1.5)
                if j.gk:
                    portee = RAYON_CONTROLE + ((1.3 + 1.2 * j.attr("ARR") / 99) if tir else 0.6)
                if b.dernier is not None and j.camp != b.dernier.camp and self.t - b.t_kick < 0.35 and not tir:
                    continue                          # au pied du passeur : la passe part
                if d < portee and b.z < (2.4 if j.gk else 1.9):
                    cand.append((d, j))
                # un défenseur sur la trajectoire d'une frappe la contre, une fois sur deux
                elif tir and not j.gk and j.camp != tir["camp"] and d < 1.3 and b.z < 1.7 and self.t - tir["t"] < 1.2 \
                        and self.t - j.dernier_contact > 0.5:
                    j.dernier_contact = self.t
                    if self.rs.random() < 0.5:
                        self._contrer(j)
                        return
            if not cand:
                return
            cand.sort(key=lambda c: c[0])
            _, j = cand[0]
            if b.z > 1.0 and not j.gk:
                self._tete(j)
                return
            # un ballon rapide se contrôle avec les attributs ; le gardien capte,
            # ou plonge sur une frappe — et peut la manquer
            v = b.vitesse()
            if j.gk and b.dernier is not None and b.dernier.camp != j.camp and v > 6.0:
                tir = self._tir_en_cours()
                if tir:
                    d = self.d_ballon(j)
                    p = (1.08 - 0.008 * max(0.0, v - 18.0) - 0.08 * d) * (0.72 + 0.28 * j.attr("ARR") / 99)
                    if self.rs.random() > max(0.15, min(0.95, p)):
                        j.dernier_contact = self.t
                        b.dernier = j
                        b.t_kick = self.t
                        return                     # battu
                self._arret_gardien(j)
                return
            p_controle = 1.0 if v < VITESSE_CONTROLE else max(0.35, 1.0 - (v - VITESSE_CONTROLE) / 18.0 * (1.0 - 0.5 * j.attr("CON") / 99))
            if self.rs.random() > p_controle:
                # contrôle raté : le ballon rebondit devant
                b.vx *= 0.35
                b.vy *= 0.35
                b.x += b.vx * DT * 3
                b.y += b.vy * DT * 3
                b.dernier = j
                b.t_kick = self.t
                return
            self._prendre(j)
        else:
            self._duels()

    def _prendre(self, j: Joueur):
        b = self.ballon
        prec = b.dernier
        passe_vers = b.passe_vers
        if prec is not None and prec.camp == j.camp and prec is not j and passe_vers is not None:
            prec.passes_ok += 1
            self.stats["passes_ok"][j.camp] += 1
        elif prec is not None and prec.camp != j.camp and passe_vers is not None:
            j.interceptions += 1
            self.stats["interceptions"][j.camp] += 1
            self.evt("interception", de=j.pid, camp=j.camp)
        # le hors-jeu : celui qui prend la passe était-il hors jeu au départ ?
        if prec is not None and prec.camp == j.camp and passe_vers is not None and j.pid in b.hors_jeu_au_kick:
            self.stats["horsjeu"][j.camp] += 1
            self.evt("horsjeu", de=j.pid, camp=j.camp)
            self._arret("coup_franc", 1 - j.camp, j.x, j.y, 14.0)
            return
        b.porteur = j
        b.passe_vers = None
        b.hors_jeu_au_kick = set()
        b.z = b.vz = 0.0
        b.vx, b.vy = j.vx, j.vy
        j.dernier_contact = self.t
        j.touches += 1
        j.role = "porteur"
        j.cible = (j.x, j.y)

    def _tete(self, j: Joueur):
        """Un ballon en l'air se dévie de la tête : un défenseur dégage loin
        de son but, un attaquant remise ou frappe vers le but."""
        b = self.ballon
        mx, my = self.but_de(1 - j.camp)               # son propre but
        gx, gy = self.but_de(j.camp)
        dbut = math.hypot(gx - j.x, gy - j.y)
        j.touches += 1
        if j.fam == "FWD" and dbut < 14 and self.rs.random() < 0.6:
            # une tête vers le but
            self.dernier_tir = {"de": j, "xg": self._xg(dbut, self._angle_but(j.x, j.y, j.camp), 0.4) * 0.6, "t": self.t, "camp": j.camp}
            j.tirs += 1
            self.stats["tirs"][j.camp] += 1
            self.stats["xg"][j.camp] += self.dernier_tir["xg"]
            ang = math.atan2(gy - j.y, gx - j.x) + self.rs.gauss(0, 0.22)
            self._lacher(j, 16.0 * math.cos(ang), 16.0 * math.sin(ang), 1.5)
            self.evt("tir", de=j.pid, camp=j.camp, xg=round(self.dernier_tir["xg"], 3), d=round(dbut, 1), tete=True)
            return
        ang = math.atan2(j.y - my, j.x - mx) + self.rs.gauss(0, 0.9 if j.fam == "DEF" else 1.2)
        v = 9.0 + 7.0 * j.attr("DEF") / 99
        self._lacher(j, v * math.cos(ang), v * math.sin(ang), 3.0)
        b.passe_vers = None
        self.dernier_tir = None

    def _tir_en_cours(self) -> dict | None:
        tir = getattr(self, "dernier_tir", None)
        return tir if tir and self.t - tir["t"] < 2.5 and self.ballon.porteur is None else None

    def _contrer(self, j: Joueur):
        """Une frappe contrée : le ballon repart dévié, souvent vers la
        ligne de fond — d'où les corners."""
        b = self.ballon
        tir = self._tir_en_cours()
        if tir:
            self.evt("contre", de=j.pid, camp=j.camp, tireur=tir["de"].pid)
        v = b.vitesse() * 0.45
        ang = math.atan2(b.vy, b.vx) + self.rs.gauss(0, 0.9)
        b.vx, b.vy = v * math.cos(ang), v * math.sin(ang)
        b.vz = abs(self.rs.gauss(2.0, 2.0))
        b.dernier = j
        b.dernier_camp = j.camp
        b.t_kick = self.t
        b.passe_vers = None
        j.touches += 1
        self.dernier_tir = None

    def _arret_gardien(self, gk: Joueur):
        b = self.ballon
        gk.arrets += 1
        tir = getattr(self, "dernier_tir", None)
        if tir and self.t - tir["t"] < 3.0:
            self.stats["cadres"][tir["camp"]] += 1
            tir["de"].tirs_cadres += 1
            self.evt("arret", de=gk.pid, camp=gk.camp, tireur=tir["de"].pid)
        # une frappe forte est repoussée plutôt que captée : le ballon repart
        # devant, ou vers la ligne de fond
        if tir and self.rs.random() < 0.15 + 0.5 * max(0.0, (b.vitesse() - 20.0) / 12.0):
            mx, my = self.but_de(1 - gk.camp)
            sens = 1 if gk.camp == 0 else -1
            cote = 1 if b.y >= my else -1
            ang = math.atan2(cote * 1.0, sens * -0.35) + self.rs.gauss(0, 0.5)   # vers la touche, légèrement en arrière
            v = 6.0 + self.rs.random() * 8.0
            b.porteur = None
            b.dernier = gk
            b.dernier_camp = gk.camp
            b.t_kick = self.t
            b.passe_vers = None
            b.vx, b.vy, b.vz = v * math.cos(ang), v * math.sin(ang), 2.0
            gk.dernier_contact = self.t
            gk.touches += 1
            self.dernier_tir = None
            return
        b.porteur = gk
        b.passe_vers = None
        b.z = b.vz = 0.0
        b.vx = b.vy = 0.0
        gk.dernier_contact = self.t - 0.5
        gk.touches += 1
        # il relance dans deux secondes : on marque un arrêt de jeu court
        self._arret("relance", gk.camp, b.x, b.y, 6.0)

    def _duels(self):
        """Un adversaire au contact du porteur tente de lui prendre le ballon."""
        b = self.ballon
        p = b.porteur
        for o in self.actifs(1 - p.camp):
            if o.gk:
                continue
            d = math.hypot(o.x - p.x, o.y - p.y)
            if d > 1.4:
                continue
            if self.t - o.dernier_contact < 2.0:
                continue
            o.dernier_contact = self.t
            # la chance de prendre le ballon : défense contre dribble, et la force
            force_o = (o.physique.get("for", 68) or 68) / 99
            force_p = (p.physique.get("for", 68) or 68) / 99
            p_gagne = 0.30 + 0.35 * (o.attr("DEF") - p.attr("DRI")) / 99 + 0.15 * (force_o - force_p)
            p_gagne = max(0.08, min(0.75, p_gagne)) * DT * 1.4   # par pas de temps : un duel se joue sur quelques secondes
            r = self.rs.random()
            if r >= p_gagne and self.rs.random() < 0.012:
                self._faute(o, p)
                return
            if r < p_gagne:
                o.tacles += 1
                self.stats["tacles"][o.camp] += 1
                # une faute une fois sur six
                if self.rs.random() < 0.35:
                    self._faute(o, p)
                    return
                self.evt("tacle", de=o.pid, sur=p.pid, camp=o.camp)
                # le ballon part libre, un peu devant le tacleur
                ang = self.rs.uniform(0, 2 * math.pi)
                b.porteur = None
                b.dernier = o
                b.dernier_camp = o.camp
                b.t_kick = self.t
                b.passe_vers = None
                b.vx, b.vy = 4.0 * math.cos(ang), 4.0 * math.sin(ang)
                return

    def _faute(self, o: Joueur, p: Joueur):
        o.fautes += 1
        self.stats["fautes"][o.camp] += 1
        carton = None
        if self.rs.random() < 0.24:
            n = self.jaunes.get(o.pid, 0) + 1
            self.jaunes[o.pid] = n
            if n >= 2:
                carton = "rouge"
                self.exclus.add(o.pid)
                self.stats["rouges"][o.camp] += 1
            else:
                carton = "jaune"
                self.stats["jaunes"][o.camp] += 1
        self.evt("faute", de=o.pid, sur=p.pid, camp=o.camp, carton=carton)
        # dans la surface : penalty
        mx, my = self.but_de(p.camp)
        if abs(p.x - mx) < SURFACE_X and abs(p.y - my) < SURFACE_Y:
            self.evt("penalty", camp=p.camp, sur=p.pid)
            self._arret("penalty", p.camp, mx - PENALTY_X * p.sens(), my, 40.0)
        else:
            self._arret("coup_franc", p.camp, p.x, p.y, 18.0)

    # -- les règles --------------------------------------------------------------------
    def _regles(self):
        b = self.ballon
        if b.porteur is not None:
            return
        # un but ?
        for camp in (0, 1):
            gx = LONG if camp == 0 else 0.0
            franchi = b.x >= gx if camp == 0 else b.x <= gx
            if franchi and abs(b.y - LARG / 2) < BUT_LARG / 2 and b.z < BUT_HAUT:
                self._but(camp)
                return
        # sorti sur le côté ?
        if b.y < 0.0 or b.y > LARG:
            camp = 1 - b.dernier_camp if b.dernier_camp is not None else 0
            self.stats["touches_ligne"][camp] += 1
            self.evt("touche", camp=camp)
            self._arret("touche", camp, max(0.5, min(LONG - 0.5, b.x)), 0.3 if b.y < 0 else LARG - 0.3, 9.0)
            return
        # sorti derrière la ligne ?
        if b.x < 0.0 or b.x > LONG:
            fond = 0 if b.x < 0.0 else 1                     # 0 : la ligne du but de A
            defenseur = 0 if fond == 0 else 1                # le camp dont c'est le but
            if b.dernier_camp == defenseur:
                att = 1 - defenseur
                self.stats["corners"][att] += 1
                self.evt("corner", camp=att)
                cx = 0.5 if fond == 0 else LONG - 0.5
                self._arret("corner", att, cx, 0.5 if b.y < LARG / 2 else LARG - 0.5, 22.0)
            else:
                tir = getattr(self, "dernier_tir", None)
                if tir and self.t - tir["t"] < 3.0 and tir["camp"] != defenseur:
                    self.evt("rate", de=tir["de"].pid, camp=tir["camp"])
                gx = SIX_X if fond == 0 else LONG - SIX_X
                self.evt("sortie_but", camp=defenseur)
                self._arret("sortie_but", defenseur, gx, LARG / 2 + self.rs.choice([-8.0, 8.0]), 14.0)
            return
        # le ballon mort loin de tout le monde : le plus proche y va (déjà par les rôles)

    def _but(self, camp: int):
        b = self.ballon
        self.score[camp] += 1
        tir = getattr(self, "dernier_tir", None)
        buteur = tir["de"] if tir and tir["camp"] == camp and self.t - tir["t"] < 3.0 else b.dernier
        if buteur is not None and buteur.camp == camp:
            buteur.buts += 1
            if tir:
                buteur.tirs_cadres += 1
                self.stats["cadres"][camp] += 1
        csc = buteur is not None and buteur.camp != camp
        self.evt("but", camp=camp, de=buteur.pid if buteur else None, csc=csc, score=list(self.score),
                 xg=round(tir["xg"], 3) if tir and tir["camp"] == camp else None)
        self.camp_engagement = 1 - camp
        self._engagement(1 - camp)

    # -- le résumé ---------------------------------------------------------------------
    def resume(self) -> dict:
        tot = sum(self.possession) or 1.0
        joueurs = []
        for j in self.joueurs:
            joueurs.append({"pid": j.pid, "nom": j.nom, "camp": j.camp, "poste": j.poste,
                            "distance": round(j.distance), "sprint": round(j.sprint), "vmax_kmh": round(j.vmax_vue * 3.6, 1),
                            "vmax_ea": j.physique.get("vit"), "touches": j.touches, "passes": j.passes, "passes_ok": j.passes_ok,
                            "tirs": j.tirs, "cadres": j.tirs_cadres, "buts": j.buts, "tacles": j.tacles,
                            "interceptions": j.interceptions, "fautes": j.fautes, "arrets": j.arrets,
                            "fatigue": round(j.fatigue, 2), "exclu": j.pid in self.exclus})
        return {"score": list(self.score), "noms": list(self.noms), "minutes": round(self.duree / 60),
                "collectif": list(self.collectif), "tactiques": [dict(t) for t in self.tac],
                "possession": [round(self.possession[0] / tot, 3), round(self.possession[1] / tot, 3)],
                "stats": {k: (v if not isinstance(v[0], float) else [round(v[0], 2), round(v[1], 2)]) for k, v in self.stats.items()},
                "joueurs": joueurs, "evenements": self.evenements, "trace": self.trace,
                "trace_pas": DT * TRACE_PAS}


# --------------------------------------------------------------------------
# Le banc de calibration
# --------------------------------------------------------------------------
# Les cibles : les ordres de grandeur d'un match des cinq grands championnats.
CIBLES = {"buts": 2.8, "tirs": 25.0, "cadres": 8.5, "passes": 900.0, "reussite": 0.83, "corners": 10.0,
          "fautes": 22.0, "horsjeu": 3.5, "distance_km": 10.5, "vmax_kmh": 31.8, "sprints_m": 190.0,
          "possession_max": 0.58, "tacles": 32.0, "jaunes": 4.0}


def banc(jeu: sqlite3.Connection, saison: str, matchs: int, graine: int, minutes: float = 90.0,
         formation: str = "4-3-3") -> dict:
    from jeu import solo as SO
    rs = random.Random(graine)
    clubs = [r[0] for r in jeu.execute("""SELECT j.team_id FROM joueur j JOIN carte c ON c.player_id = j.player_id
                                         WHERE c.saison=? GROUP BY j.team_id HAVING COUNT(*) >= 14""", (saison,))]
    cumul: dict[str, list[float]] = {k: [] for k in CIBLES}
    vit = []
    resultats = []
    if len(clubs) < 2:
        return {"matchs": 0, "moyennes": {k: None for k in CIBLES}, "cibles": CIBLES, "corr_vitesse": None, "resultats": []}
    for i in range(matchs):
        a, b = rs.sample(clubs, 2)
        sa = SO.onze_club(jeu, saison, a, formation)
        sb = SO.onze_club(jeu, saison, b, formation)
        if len(sa) < 11 or len(sb) < 11:
            continue
        na = jeu.execute("SELECT nom FROM club WHERE team_id=?", (a,)).fetchone()[0]
        nb = jeu.execute("SELECT nom FROM club WHERE team_id=?", (b,)).fetchone()[0]
        m = Match(sa, sb, formation, formation, graine=graine * 1000 + i, minutes=minutes, noms=(na, nb), trace=False,
                  collectif=(collectif_de(jeu, a, [j["pid"] for j in sa]), collectif_de(jeu, b, [j["pid"] for j in sb])))
        r = m.jouer()
        st = r["stats"]
        f = 90.0 / minutes
        cumul["buts"].append(sum(r["score"]) * f)
        cumul["tirs"].append(sum(st["tirs"]) * f)
        cumul["cadres"].append(sum(st["cadres"]) * f)
        cumul["passes"].append(sum(st["passes"]) * f)
        cumul["reussite"].append(sum(st["passes_ok"]) / max(1, sum(st["passes"])))
        cumul["corners"].append(sum(st["corners"]) * f)
        cumul["fautes"].append(sum(st["fautes"]) * f)
        cumul["horsjeu"].append(sum(st["horsjeu"]) * f)
        cumul["tacles"].append(sum(st["tacles"]) * f)
        cumul["jaunes"].append(sum(st["jaunes"]) * f)
        cumul["possession_max"].append(max(r["possession"]))
        champ = [j for j in r["joueurs"] if not j["poste"].startswith("Gardien")]
        cumul["distance_km"].append(sum(j["distance"] for j in champ) / len(champ) / 1000 * f)
        cumul["sprints_m"].append(sum(j["sprint"] for j in champ) / len(champ) * f)
        cumul["vmax_kmh"].append(sorted(j["vmax_kmh"] for j in champ)[len(champ) // 2])
        for j in champ:
            if j["vmax_ea"] is not None:
                vit.append((j["vmax_ea"], j["vmax_kmh"]))
        resultats.append({"a": na, "b": nb, "score": r["score"], "tirs": st["tirs"], "xg": st["xg"]})
    moy = {k: (sum(v) / len(v) if v else None) for k, v in cumul.items()}
    corr = None
    if len(vit) > 5:
        mx = sum(x for x, _ in vit) / len(vit)
        my = sum(y for _, y in vit) / len(vit)
        sxy = sum((x - mx) * (y - my) for x, y in vit)
        sxx = math.sqrt(sum((x - mx) ** 2 for x, _ in vit) * sum((y - my) ** 2 for _, y in vit)) or 1.0
        corr = sxy / sxx
    return {"matchs": len(resultats), "moyennes": moy, "cibles": CIBLES, "corr_vitesse": corr, "resultats": resultats}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jeu", default=str(RACINE / "jeu" / "demo.sqlite"))
    ap.add_argument("--saison", default="2025/26")
    ap.add_argument("--matchs", type=int, default=6)
    ap.add_argument("--graine", type=int, default=1)
    ap.add_argument("--minutes", type=float, default=90.0)
    ap.add_argument("--formation", default="4-3-3")
    ap.add_argument("--trace", default=None, help="jouer un match et écrire sa trace (JSON) dans ce fichier")
    ap.add_argument("--clubs", default=None, help="deux team_id séparés par une virgule, pour --trace")
    a = ap.parse_args()
    from jeu import importer as I
    from jeu import solo as SO
    jeu = I.ouvrir_jeu(pathlib.Path(a.jeu))
    if a.trace:
        if a.clubs:
            ta, tb = (int(x) for x in a.clubs.split(","))
        else:
            rs = random.Random(a.graine)
            clubs = [r[0] for r in jeu.execute("""SELECT j.team_id FROM joueur j JOIN carte c ON c.player_id = j.player_id
                                                 WHERE c.saison=? GROUP BY j.team_id HAVING COUNT(*) >= 14""", (a.saison,))]
            ta, tb = rs.sample(clubs, 2)
        noms = tuple(jeu.execute("SELECT nom FROM club WHERE team_id=?", (t,)).fetchone()[0] for t in (ta, tb))
        sa, sb = SO.onze_club(jeu, a.saison, ta, a.formation), SO.onze_club(jeu, a.saison, tb, a.formation)
        m = Match(sa, sb, a.formation, a.formation, graine=a.graine, minutes=a.minutes, noms=noms,
                  collectif=(collectif_de(jeu, ta, [j["pid"] for j in sa]), collectif_de(jeu, tb, [j["pid"] for j in sb])))
        r = m.jouer()
        pathlib.Path(a.trace).write_text(json.dumps(r), encoding="utf-8")
        print(f"{noms[0]} {r['score'][0]} - {r['score'][1]} {noms[1]} · tirs {r['stats']['tirs']} · xG {r['stats']['xg']} "
              f"· passes {r['stats']['passes']} · {len(r['trace'])} images -> {a.trace}")
        return
    import time
    t0 = time.time()
    r = banc(jeu, a.saison, a.matchs, a.graine, a.minutes, a.formation)
    print(f"{r['matchs']} matchs en {time.time() - t0:.0f} s")
    print(f"{'mesure':<16}{'simulé':>10}{'cible':>10}")
    for k, c in CIBLES.items():
        v = r["moyennes"][k]
        print(f"{k:<16}{(v if v is not None else float('nan')):>10.2f}{c:>10.2f}")
    print(f"corrélation vitesse EA / pointe simulée : {r['corr_vitesse']:.2f}" if r["corr_vitesse"] is not None else "")
    for x in r["resultats"]:
        print(f"  {x['a']} {x['score'][0]}-{x['score'][1]} {x['b']}  tirs {x['tirs']}  xG {x['xg']}")


if __name__ == "__main__":
    main()

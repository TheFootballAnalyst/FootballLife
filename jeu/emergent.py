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
SOUFFLE = 2.6                                # s : un sprint est une bouffée, pas une allure ; il se recharge au trot

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
    role_tac: str = "relayeur"
    volume: float = 0.5                       # la course par 90 (rang dans sa ligne)
    pressing: float = 0.5                     # les sprints vers le porteur (rang dans sa ligne)
    recup: float = 0.5                        # les ballons gagnés (rang dans sa ligne)
    appel_jusqua: float = -1.0                # une course lancée par la passe d'un coéquipier
    appel_vers: tuple[float, float] | None = None   # où va cet appel : derrière la ligne, dans la brèche
    appel_marge: float = 1.0                  # à combien de la ligne il attend la passe (négatif : un pas trop tôt)
    perce_jusqua: float = -1.0                # une percée balle au pied : il ne relâche pas avant
    souffle: float = 2.6                      # les secondes de sprint qu'il a dans les jambes (une bouffée)
    pied: str = "droit"
    pied_faible: int = 3                      # 1..5, 5 = ambidextre
    recu_de: int = -1                         # de qui il vient de recevoir (le une-deux)
    t_recu: float = -10.0
    homme: int = -1                           # l'homme qu'il marque, et depuis quand (le marquage colle)
    t_homme: float = -10.0
    provoque_jusqua: float = -1.0             # il provoque son vis-à-vis balle au pied
    battu_jusqua: float = -1.0                # il vient de se faire passer : un temps pour se retourner
    dernier_duel: float = -10.0               # le dernier duel subi balle au pied
    dernier_choc: float = -10.0               # la dernière arrivée lancée sur un porteur (la faute de pressing)
    capitaine: bool = False
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
        jo.pied = "gauche" if str(j.get("pied") or "").lower().startswith("g") else "droit"
        try:
            jo.pied_faible = max(1, min(5, int(j.get("pied_faible") or 3)))
        except (TypeError, ValueError):
            jo.pied_faible = 3
        # les trois leviers du travail sans ballon, quand la fiche les a
        jo.volume = float(ph.get("volume", 0.5) if ph.get("volume") is not None else 0.5)
        jo.pressing = float(ph.get("pressing", 0.5) if ph.get("pressing") is not None else 0.5)
        jo.recup = float(ph.get("recup", 0.5) if ph.get("recup") is not None else 0.5)
        if ph.get("pressing") is not None and (j.get("physique") or {}).get("wr_def") not in TRAVAIL:
            # revenir défendre, c'est presser et courir : la mesure remplace la devinette
            jo.travail_def = 0.6 * jo.pressing + 0.4 * jo.volume
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
#   relance  courte : le gardien joue ses six mètres au sol, le bloc se
#            resserre autour de lui pour offrir des lignes courtes ; longue :
#            il dégage sur l'attaquant et le bloc monte à la retombée du
#            ballon ; mixte : courte, longue si l'adversaire vient presser.
PHASES = ["construction", "progression", "finition", "contre", "pressing", "bloc_median", "bloc_bas", "contre_pressing", "relance"]
TACTIQUE_DEFAUT = {"bloc": "median", "tempo": "equilibre", "risque": "equilibre", "relance": "mixte",
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
                 collectif: tuple[float, float] = (0.6, 0.6),
                 capitaines: tuple[int | None, int | None] = (None, None)):
        self.rs = random.Random(graine)
        self.tac = [dict(TACTIQUE_DEFAUT) | (tactiques[0] or {}), dict(TACTIQUE_DEFAUT) | (tactiques[1] or {})]
        self.collectif = list(collectif)
        self.ligne_def = [FAMILLE_X["DEF"] * LONG, FAMILLE_X["DEF"] * LONG]   # la profondeur de chaque défense, dans son repère
        self.phase = ["construction", "bloc_median"]
        for t in self.tac:
            if t.get("relance", "mixte") == "mixte" and t["tempo"] in ("possession", "direct"):
                t["relance"] = "courte" if t["tempo"] == "possession" else "longue"
        self.relance_choix = ["courte", "courte"]    # ce que chaque camp fait de SA relance en cours
        self.cote_suite = [0, 0]                     # les passes d'affilée sur un même côté : un côté bouché se quitte
        self.t_bascule = 0.0
        self.x_bascule = 50.0
        self.joueurs = joueurs_de(sur_a, 0, formation_a) + joueurs_de(sur_b, 1, formation_b)
        self.camp = [[j for j in self.joueurs if j.camp == 0], [j for j in self.joueurs if j.camp == 1]]
        self.exclus = set()
        for j in self.joueurs:
            j.role_tac = self._role_tac(j)
        # le capitaine : celui de la compo, sinon le joueur de champ le mieux noté
        for camp, sur in ((0, sur_a), (1, sur_b)):
            pid = capitaines[camp]
            if pid is None or not any(j.pid == pid for j in self.camp[camp]):
                cand = [j for j in sur if S.FAMILLE_POSTE.get(j.get("slot") or j.get("poste", ""), "MID") != "GK"]
                pid = max(cand, key=lambda j: j.get("ovr", 0), default={"pid": -1})["pid"] if cand else -1
            for j in self.camp[camp]:
                j.capitaine = (j.pid == pid)
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

    def ligne_horsjeu(self, camp_att: int, retard: bool = False) -> float:
        """La ligne de hors-jeu que le camp attaquant affronte : l'avant-
        dernier défenseur (en x absolu).  Avec `retard`, la ligne telle
        que le passeur l'a vue quatre dixièmes plus tôt : c'est de là que
        viennent les vrais hors-jeu, d'un coureur parti sur la ligne d'il y
        a un instant."""
        xs = sorted((j.x for j in self.actifs(1 - camp_att)), reverse=(camp_att == 0))
        if len(xs) < 2:
            return LONG if camp_att == 0 else 0.0
        ligne = xs[1]
        # jamais dans son propre camp
        ligne = max(ligne, LONG / 2) if camp_att == 0 else min(ligne, LONG / 2)
        hist = getattr(self, "_lignes", None)
        if hist is None:
            hist = self._lignes = {0: [], 1: []}
        h = hist[camp_att]
        if not h or h[-1][0] < self.t:
            h.append((self.t, ligne))
            if len(h) > 8:
                del h[0]
        if retard:
            vue = next((l for t, l in h if t >= self.t - 0.45), ligne)
            return vue
        return ligne

    def hors_jeu(self, j: Joueur, xb: float, retard: bool = False) -> bool:
        ligne = self.ligne_horsjeu(j.camp, retard)
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
        apres_but = bool(self.evenements) and self.evenements[-1]["k"] == "but" and not immediat and self.t > 0.0
        if apres_but:
            b.x, b.y = max(-1.5, min(LONG + 1.5, b.x)), max(0.0, min(LARG, b.y))   # il reste au fond des filets
        else:
            b.x, b.y = LONG / 2, LARG / 2
        b.z = 0.0
        b.vx = b.vy = b.vz = 0.0
        b.porteur = None
        b.passe_vers = None
        tireur = min((j for j in self.actifs(camp) if j.fam in ("FWD", "MID")),
                     key=lambda j: math.hypot(j.x - LONG / 2, j.y - LARG / 2), default=None)
        if tireur and (immediat or self.t == 0.0):
            tireur.x, tireur.y = LONG / 2 - 0.6 * tireur.sens(), LARG / 2
        self.arret = {"k": "engagement", "t": self.t, "camp": camp, "x": LONG / 2, "y": LARG / 2, "tireur": tireur,
                      "delai": 40.0 if apres_but else 3.0, "au_centre": self.t + 4.0 if apres_but else self.t}

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
        elif k == "coup_franc":
            mx, my = self.but_de(1 - camp)
            if abs(x - mx) < SURFACE_X + 4.0 and abs(y - my) < SURFACE_Y:
                tireur = next((j for j in self.actifs(camp) if j.gk), None)   # dans sa surface : le gardien joue
        if tireur is None:
            tireur, _ = self.plus_proche(camp, x, y, gk=(k == "sortie_but"))
        self.arret = {"k": k, "t": self.t, "camp": camp, "x": x, "y": y, "delai": delai, "tireur": tireur}

    def _forme_arret(self, a: dict):
        """Les coups de pied arrêtés ont leur forme.  Corner : les grands
        montent prendre le ballon de la tête, une option courte, les
        latéraux et le pivot restent couvrir le contre ; en face, deux
        attaquants restent hauts, les autres défendent la surface.  Coup
        franc proche : le mur (jusqu'à cinq dans l'axe, deux excentré),
        la ligne, les attaquants au bord de la surface.  Penalty : tout
        le monde hors de la surface, prêt à bondir."""
        k, camp = a["k"], a["camp"]
        if k not in ("corner", "coup_franc", "penalty"):
            return
        df = 1 - camp
        b = self.ballon
        gx, gy = self.but_de(camp)                  # le but attaqué
        s = 1 if camp == 0 else -1
        tireur = a.get("tireur")
        att = [j for j in self.actifs(camp) if not j.gk and j is not tireur]
        defs = [j for j in self.actifs(df) if not j.gk]
        dbut = math.hypot(gx - b.x, gy - b.y)
        central = abs(b.y - gy) < 16.0

        def pose(j, x, y):
            j.cible = (max(1.0, min(LONG - 1.0, x)), max(1.0, min(LARG - 1.0, y)))
            j.role = "arret"

        if k == "penalty":
            # au bord de la surface, en alternance, prêts à bondir
            for i, j in enumerate(sorted(att, key=lambda j: -j.attr("FIN"))):
                pose(j, gx - 17.5 * s, gy + [-10, -5, 0, 5, 10, -16, 16, 22, -22, 28][i % 10] if i < 5 else gy + [-12, 12, -20, 20, 0][i - 5])
                if i >= 5:
                    pose(j, gx - (28.0 + 5.0 * (i - 5)) * s, j.cible[1])
            for i, j in enumerate(sorted(defs, key=lambda j: j.attr("DEF"), reverse=True)):
                if i < 6:
                    pose(j, gx - 17.5 * s, gy + [-12.5, -7.5, -2.5, 2.5, 7.5, 12.5][i])
                else:
                    pose(j, gx - (30.0 + 6.0 * (i - 6)) * s, gy + [-8, 8, 0, -16][(i - 6) % 4])
            return

        if k == "coup_franc" and dbut > 38.0:
            return                                  # loin : le jeu reprend dans la forme normale

        # --- corner et coup franc proche : la surface
        grands = sorted(att, key=lambda j: (j.role_tac in ("central", "buteur", "meneur", "ailier"), j.attr("FIN") + j.attr("DEF")), reverse=True)
        n_dans = 6 if k == "corner" else 5
        dans, reste = grands[:n_dans], grands[n_dans:]
        if k == "corner":
            spots = [(-8.0, -7.0), (-8.0, -2.0), (-8.0, 3.0), (-8.0, 8.0), (-12.0, -4.0), (-12.0, 5.0)]
        else:
            spots = [(-11.0, -8.0), (-11.0, -3.0), (-11.0, 2.0), (-11.0, 7.0), (-14.0, 0.0)]
        for j, (dx, dy) in zip(dans, spots):
            pose(j, gx + dx * s, gy + dy)
        # une option courte près du tireur, les autres en couverture
        if reste:
            court = min(reste, key=lambda j: math.hypot(j.x - b.x, j.y - b.y))
            pose(court, b.x - 7.0 * s, b.y + (6.0 if b.y < LARG / 2 else -6.0))
            reste = [j for j in reste if j is not court]
        for i, j in enumerate(reste):
            pose(j, gx - 36.0 * s - 4.0 * s * (i % 2), gy + [-10.0, 10.0, 0.0, -20.0, 20.0][i % 5])
        # --- la défense : deux restent hauts pour le contre, le mur, la surface
        hauts = sorted(defs, key=lambda j: (j.role_tac in ("buteur", "ailier"), -j.travail_def, j.attr("FIN")), reverse=True)[:2]
        for i, j in enumerate(hauts):
            pose(j, gx - 48.0 * s, gy + (-14.0 if i == 0 else 14.0))
        restants = [j for j in defs if j not in hauts]
        if k == "coup_franc":
            n_mur = (5 if dbut < 22 else 4 if dbut < 28 else 3) if central else (2 if dbut < 30 else 1)
            n_mur = min(n_mur, len(restants))
            ux, uy = (gx - b.x) / (dbut or 1.0), (gy - b.y) / (dbut or 1.0)
            mur = sorted(restants, key=lambda j: (j.fam == "DEF", -j.physique.get("for", 68) if j.physique else 0))[:n_mur]
            for i, j in enumerate(mur):
                off = (i - (n_mur - 1) / 2) * 0.9
                pose(j, b.x + ux * 9.3 - uy * off, b.y + uy * 9.3 + ux * off)
            restants = [j for j in restants if j not in mur]
        # la surface : les défenseurs en ligne au second poteau et devant le but, les milieux sur les attaquants
        ligne = [j for j in restants if j.fam == "DEF"]
        for i, j in enumerate(ligne):
            pose(j, gx - 6.0 * s, gy + [-6.0, 6.0, -1.5, 3.0, -10.0, 10.0][i % 6])
        marqueurs = [j for j in restants if j.fam != "DEF"]
        libres = [o for o in dans]
        for j in marqueurs:
            if not libres:
                pose(j, gx - 16.0 * s, gy + self.rs.uniform(-10, 10))
                continue
            o = min(libres, key=lambda o: math.hypot(o.cible[0] - j.x, o.cible[1] - j.y))
            libres.remove(o)
            ox, oy = o.cible
            n = math.hypot(gx - ox, gy - oy) or 1.0
            pose(j, ox + (gx - ox) / n * 1.2, oy + (gy - oy) / n * 1.2)

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
        if k == "coup_franc":
            d = math.hypot(bx - b.x, by - b.y)
            if d < 30 and abs(b.y - by) < 16 and self.rs.random() < 0.35 + 0.3 * j.attr("FIN") / 99:
                self._frapper(j, coup_franc=True)
                return
            if d < 38 and self.rs.random() < 0.7:
                self._centrer(j)                    # dans la surface, où les grands attendent
                return
        self._decider_porteur(j, force=True)
        if k == "sortie_but":
            b.hors_jeu_au_kick = set()               # pas de hors-jeu sur une sortie de but

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
                    self._phases(a["camp"])
                    for camp in (0, 1):
                        self._forme(camp, a["camp"])
                    self._gardiens(a["camp"])
                    self._espacer()
                    self._forme_arret(a)
                if a["k"] == "engagement" and self.t >= a.get("au_centre", 0.0) and (b.x, b.y) != (a["x"], a["y"]):
                    b.x, b.y, b.z = a["x"], a["y"], 0.0              # l'arbitre ramène le ballon au centre
                if tireur is not None and tireur.pid not in self.exclus:
                    tireur.cible = (a["x"] - 0.7 * tireur.sens(), a["y"])
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
            self.trace.append([int(round(self.t * 10)), int(round(b.x * 10)), int(round(b.y * 10)), int(round(b.z * 10)),
                               1 if self.arret else 0, PHASES.index(self.phase[0]), PHASES.index(self.phase[1])]
                              + [v for j in self.joueurs for v in (int(round(j.x * 10)), int(round(j.y * 10)))])

    # -- les décisions -------------------------------------------------------------
    # ------------------------------------------------------------------------
    # L'ÉQUIPE décide, chacun exécute.
    #
    # Avant, chaque joueur calculait sa place tout seul, avec ses propres
    # règles : vingt-deux partitions, pas un mouvement d'équipe.  Ici, à
    # chaque tic, chaque camp lit d'abord SA PHASE — ce que l'équipe fait
    # en ce moment — puis la forme de la phase donne à chaque rôle tactique
    # (centraux, latéraux, pivot, relayeurs, meneur, ailiers, buteur) une
    # place qui dépend du ballon, et les rôles individuels (porteur,
    # receveur, presseur, appel dans la brèche) se posent par-dessus.
    #
    #   avec le ballon   construction (dans son tiers), progression (au
    #                    milieu), finition (dans les trente derniers
    #                    mètres), contre (six secondes après une
    #                    récupération basse)
    #   sans le ballon   pressing (on va chercher haut, chacun son homme,
    #                    en couvrant une ligne de passe), bloc médian,
    #                    bloc bas (tassé sur trente mètres, personne
    #                    devant le ballon), contre-pressing (cinq secondes
    #                    après une perte)
    # ------------------------------------------------------------------------
    def _decisions(self):
        b = self.ballon
        att = b.porteur.camp if b.porteur else (b.dernier_camp if b.dernier_camp is not None else 0)
        self._phases(att)
        if b.porteur is not None:
            self._decider_porteur(b.porteur)
        for camp in (0, 1):
            self._forme(camp, att)
        self._roles_attaque(att)
        self._roles_defense(1 - att)
        self._ballon_libre()
        self._gardiens(att)
        self._espacer()

    def _phases(self, att: int):
        b = self.ballon
        df = 1 - att
        # le changement de possession : on note quand
        if getattr(self, "_att_prec", None) != att:
            self.t_bascule = self.t
            self._att_prec = att
        depuis = self.t - getattr(self, "t_bascule", -99.0)
        bxp = b.x if att == 0 else LONG - b.x             # le ballon, vu de l'attaque
        tac_a, tac_d = self.tac[att], self.tac[df]
        # --- l'attaque : d'abord la relance du gardien, qui a sa forme à elle
        en_relance = ((b.porteur is not None and b.porteur.gk and b.porteur.camp == att)
                      or (self.arret is not None and self.arret["k"] in ("sortie_but", "relance") and self.arret["camp"] == att))
        if en_relance:
            if self.phase[att] != "relance":
                self.relance_choix[att] = self._choix_relance(att)
            self.phase[att] = "relance"
        elif (depuis < 6.0 and getattr(self, "x_bascule", 60.0) < 45.0 and tac_a["tempo"] != "possession"
              and (depuis < 2.5 or bxp - self.x_bascule > 8.0 + 4.0 * (depuis - 2.5))):
            self.phase[att] = "contre"
        elif bxp < 35.0:
            self.phase[att] = "construction"
        elif bxp < 72.0:
            self.phase[att] = "progression"
        else:
            self.phase[att] = "finition"
        if depuis == 0.0:
            self.x_bascule = bxp
        # --- la défense
        bxd = LONG - bxp                                   # le ballon, vu de la défense
        envie = sum(j.pressing for j in self.actifs(df) if j.fam == "FWD") / max(1, sum(1 for j in self.actifs(df) if j.fam == "FWD"))
        if depuis < 5.0 and (tac_d["bloc"] == "haut" or self.collectif[df] > 0.7) and bxd > 45.0:
            self.phase[df] = "contre_pressing"
        elif tac_d["bloc"] == "haut" and bxd > 40.0:
            self.phase[df] = "pressing"
        elif tac_d["bloc"] == "median" and bxd > 68.0 and envie > 0.55:
            self.phase[df] = "pressing"                  # on va chercher une relance, si les attaquants aiment ça
        elif tac_d["bloc"] == "bas" or bxd < 32.0 or self._doit_reculer(df, bxd):
            self.phase[df] = "bloc_bas"
        else:
            self.phase[df] = "bloc_median"

    def _doit_reculer(self, df: int, bxd: float) -> bool:
        """Même une équipe haute dans ses principes recule quand il le faut :
        sur un contre adverse dans sa moitié, ou quand il y a autant
        d'attaquants que de défenseurs à moins de trente-cinq mètres de son
        but."""
        att = 1 - df
        if self.phase[att] == "contre" and bxd < 62.0:
            return True
        mx, my = self.but_de(1 - df)                          # son propre but
        n_att = sum(1 for o in self.actifs(att) if not o.gk and math.hypot(o.x - mx, o.y - my) < 35.0)
        n_def = sum(1 for j in self.actifs(df) if not j.gk and math.hypot(j.x - mx, j.y - my) < 35.0)
        return bxd < 55.0 and n_att >= 2 and n_att + 1 >= n_def

    def _choix_relance(self, att: int) -> str:
        """Courte ou longue, au départ de la relance : la consigne, et pour
        une consigne mixte, la présence adverse — on ne joue pas court dans
        les pieds d'un pressing."""
        consigne = self.tac[att].get("relance", "mixte")
        if consigne in ("courte", "longue"):
            return consigne
        # mixte : au sol, sauf face à un bloc haut qui vient chercher la relance
        # (et au moment de jouer, sans ligne courte, le gardien allonge de lui-même)
        return "longue" if self.tac[1 - att]["bloc"] == "haut" else "courte"

    def _role_tac(self, j: Joueur) -> str:
        base = S.poste_base(j.poste)
        if j.gk:
            return "gardien"
        if base == "Defenseur central":
            return "central"
        if base == "Lateral":
            return "lateral"
        if base == "Milieu defensif":
            return "pivot"
        if base == "Milieu offensif":
            return "meneur"
        if base in ("Ailier", "Milieu de couloir"):
            return "ailier"
        if base == "Buteur":
            return "buteur"
        if base == "Milieu relayeur":
            # sans pivot dans le onze, le relayeur le plus bas fait pivot
            mids = [o for o in self.actifs(j.camp) if S.poste_base(o.poste) in ("Milieu relayeur", "Milieu defensif")]
            if not any(S.poste_base(o.poste) == "Milieu defensif" for o in mids) and mids and min(mids, key=lambda o: o.home[0]) is j:
                return "pivot"
            return "relayeur"
        return "relayeur"

    def _forme(self, camp: int, att: int):
        """La place de chaque rôle dans la phase de son équipe, dans SON
        repère (x vers le but adverse, y depuis sa gauche), puis en
        absolu.  Le ballon est (bx, by) dans ce repère."""
        b = self.ballon
        sien = camp == att
        phase = self.phase[camp]
        tac = self.tac[camp]
        siens = [j for j in self.actifs(camp) if not j.gk]
        if not siens:
            return
        bx, by = siens[0].propre(b.x, b.y)
        if not sien:
            # un ballon qui vient vers notre but : le bloc se place là où il sera dans une seconde
            vers_nous = -(b.vx * siens[0].sens())
            bx = max(2.0, bx - max(0.0, min(8.0, vers_nous)) * 1.0)
            # le bloc ne suit pas le ballon à la trace : il recule vite (7 m/s),
            # remonte lentement (2,5 m/s) et glisse en largeur à 5 m/s — une
            # passe de quinze mètres ne déplace pas onze hommes de quinze mètres
            ref = getattr(self, "bloc_ref", {}).get(camp)
            if ref is None or self.t - ref[2] > 3.0:
                ref = (bx, by, self.t)
            if vers_nous < -3.0:
                bx = min(bx + 4.0, ref[0] + 1.3)          # le ballon repart en arrière : la ligne remonte d'un coup (le piège)
            else:
                bx = max(bx, ref[0] - 1.4) if bx < ref[0] else min(bx, ref[0] + 0.5)
            by = ref[1] + max(-1.0, min(1.0, by - ref[1]))
            if not hasattr(self, "bloc_ref"):
                self.bloc_ref = {}
            self.bloc_ref[camp] = (bx, by, self.t)
        cote = 1 if by >= LARG / 2 else -1               # le côté du ballon (+1 : sa droite)
        # la ligne de hors-jeu que l'attaque affronte, vue de l'attaque
        ligne_hj = None
        if sien:
            lh = self.ligne_horsjeu(camp)
            ligne_hj = lh if camp == 0 else LONG - lh
        # --- les profondeurs de ligne
        if phase == "bloc_bas":
            L = max(7.0, min(24.0, bx - 15.0))
            prof = {"central": L, "lateral": L + 1.0, "pivot": L + 7.0, "relayeur": L + 8.0, "meneur": L + 10.0,
                    "ailier": L + 9.0, "buteur": min(L + 20.0, 46.0)}
            larg = {"central": 6.0, "lateral": 16.0, "pivot": 0.0, "relayeur": 8.0, "meneur": 4.0, "ailier": 18.0, "buteur": 0.0}
            glisse = 0.35
        elif phase == "bloc_median":
            L = max(10.0, min(40.0, bx - 18.0))
            prof = {"central": L, "lateral": L + 2.0, "pivot": L + 8.0, "relayeur": L + 10.0, "meneur": L + 13.0,
                    "ailier": L + 12.0, "buteur": min(L + 22.0, bx + 6.0)}
            larg = {"central": 8.0, "lateral": 21.0, "pivot": 0.0, "relayeur": 11.0, "meneur": 5.0, "ailier": 22.0, "buteur": 0.0}
            glisse = 0.4
        elif phase in ("pressing", "contre_pressing"):
            L = max(20.0, min(60.0, bx - 8.0))
            prof = {"central": L, "lateral": L + 3.0, "pivot": L + 12.0, "relayeur": L + 15.0, "meneur": L + 22.0,
                    "ailier": L + 24.0, "buteur": L + 30.0}
            larg = {"central": 9.0, "lateral": 22.0, "pivot": 0.0, "relayeur": 12.0, "meneur": 5.0, "ailier": 22.0, "buteur": 0.0}
            glisse = 0.3
        elif phase == "relance" and self.relance_choix[camp] == "courte":
            # les six mètres au sol : les centraux ouverts au bord de la
            # surface, le pivot devant le gardien, tout le bloc sur quarante
            # mètres pour que chaque porteur ait deux lignes courtes
            prof = {"central": 9.0, "lateral": 24.0, "pivot": 18.0, "relayeur": 32.0, "meneur": 40.0, "ailier": 46.0, "buteur": 52.0}
            larg = {"central": 16.0, "lateral": 29.0, "pivot": 0.0, "relayeur": 10.0, "meneur": 0.0, "ailier": 24.0, "buteur": 0.0}
            glisse = 0.0
        elif phase == "relance":
            # le long ballon : tout le bloc monte à la retombée (soixante
            # mètres), serré autour de l'attaquant pour le second ballon
            prof = {"central": 30.0, "lateral": 38.0, "pivot": 42.0, "relayeur": 50.0, "meneur": 56.0, "ailier": 58.0, "buteur": 62.0}
            larg = {"central": 9.0, "lateral": 24.0, "pivot": 0.0, "relayeur": 10.0, "meneur": 4.0, "ailier": 16.0, "buteur": 0.0}
            glisse = 0.0
        elif phase == "construction":
            prof = {"central": 14.0, "lateral": 32.0, "pivot": 24.0, "relayeur": 40.0, "meneur": 52.0, "ailier": 60.0, "buteur": 68.0}
            larg = {"central": 11.0, "lateral": 28.0, "pivot": 0.0, "relayeur": 12.0, "meneur": 3.0, "ailier": 26.0, "buteur": 0.0}
            glisse = 0.15
        elif phase == "progression":
            L = max(25.0, min(52.0, bx - 15.0))
            prof = {"central": L, "lateral": L + 14.0, "pivot": L + 8.0, "relayeur": L + 18.0, "meneur": L + 28.0,
                    "ailier": max(bx + 8.0, L + 30.0), "buteur": L + 36.0}
            larg = {"central": 9.0, "lateral": 26.0, "pivot": 0.0, "relayeur": 12.0, "meneur": 4.0, "ailier": 26.0, "buteur": 0.0}
            glisse = 0.2
        elif phase == "contre":
            L = max(25.0, min(50.0, bx - 12.0))
            prof = {"central": L, "lateral": L + 10.0, "pivot": L + 8.0, "relayeur": bx + 15.0, "meneur": bx + 22.0,
                    "ailier": min(92.0, bx + 30.0), "buteur": min(92.0, bx + 32.0)}
            larg = {"central": 9.0, "lateral": 24.0, "pivot": 0.0, "relayeur": 10.0, "meneur": 4.0, "ailier": 22.0, "buteur": 0.0}
            glisse = 0.1
        else:  # finition : la surcharge côté ballon, le poteau opposé, la défense de repli
            prof = {"central": 52.0, "lateral": 60.0, "pivot": 63.0, "relayeur": 72.0, "meneur": 82.0, "ailier": 90.0, "buteur": 90.0}
            larg = {"central": 8.0, "lateral": 8.0, "pivot": 0.0, "relayeur": 10.0, "meneur": 4.0, "ailier": 22.0, "buteur": 0.0}
            glisse = 0.1
        self.ligne_def[camp] = prof["central"]
        # --- chaque rôle à sa place (le porteur garde la sienne : il conduit, il ne se replace pas)
        for j in siens:
            if j is b.porteur:
                continue
            r = j.role_tac
            gauche = j.home[1] < LARG / 2                 # son côté au repos
            signe = -1 if gauche else 1
            x = prof.get(r, prof["relayeur"])
            y = LARG / 2 + signe * larg.get(r, 8.0)
            # les rôles axiaux à deux (deux relayeurs, deux buteurs) : chacun garde son côté
            if r in ("pivot", "buteur") and sum(1 for o in siens if o.role_tac == r) > 1:
                y = LARG / 2 + signe * 7.0
            if r == "relayeur" and sum(1 for o in siens if o.role_tac == "relayeur") == 1:
                y = LARG / 2
            cote_ballon = (signe == cote)
            if sien:
                if phase == "finition":
                    if r == "ailier":
                        # côté ballon : la surcharge avec le latéral ; côté opposé : le second poteau
                        x, y = (min(96.0, bx + 4.0), LARG / 2 + signe * 22.0) if cote_ballon else (92.0, LARG / 2 + signe * 7.0)
                    elif r == "lateral":
                        x, y = (min(95.0, bx + 3.0), LARG / 2 + signe * 30.0) if cote_ballon else (58.0, LARG / 2 + signe * 8.0)
                    elif r == "relayeur":
                        x, y = (max(55.0, bx - 8.0), by - cote * 8.0) if cote_ballon else (70.0, LARG / 2 + signe * 10.0)
                    elif r == "buteur":
                        x, y = 90.0, LARG / 2 + (signe * 7.0 if sum(1 for o in siens if o.role_tac == "buteur") > 1 else 0.0)
                elif phase == "contre":
                    pass
                elif phase == "progression":
                    if r == "lateral" and tac["lateraux"] == "bas":
                        x = prof["central"] + 3.0
                    if r == "lateral" and (tac["lateraux"] == "axe" or j.travail_att > 0.75) and cote_ballon:
                        x += 6.0
                    if r == "ailier" and tac["ailiers"] == "interieur":
                        y = LARG / 2 + signe * 14.0
                    if r == "relayeur" and (tac["milieux"] == "projection" or j.travail_att > 0.75):
                        x += 6.0
                # personne ne se met hors jeu en se plaçant
                if ligne_hj is not None:
                    x = min(x, ligne_hj - 1.5)
                # la largeur coulisse un peu vers le ballon
                y += (by - LARG / 2) * glisse
            else:
                # sans ballon : tout le monde derrière le ballon (sauf en pressing), et le bloc glisse côté ballon
                if phase not in ("pressing", "contre_pressing"):
                    x = min(x, bx - 6.0) if r not in ("buteur", "ailier") else min(x, bx + 6.0 if r == "buteur" else bx - 1.0)
                    # un attaquant qui travaille revient dans le bloc
                    if r in ("ailier", "buteur") and j.travail_def > 0.6:
                        x = min(x, prof["relayeur"] + 6.0 + 8.0 * (1.0 - j.travail_def))
                y += (by - LARG / 2) * glisse
                if phase == "bloc_bas":
                    # tassé : le côté opposé rentre jusqu'à l'axe
                    if not cote_ballon and r in ("lateral", "ailier"):
                        y = LARG / 2 + signe * 10.0 + (by - LARG / 2) * 0.2
            nx, ny = j.absolu(max(2.0, min(LONG - 2.0, x)), max(2.0, min(LARG - 2.0, y)))
            # la forme se lit lissée : une cible qui saute à chaque tic fait des zigzags,
            # et sans ballon une place ne fuit jamais plus vite qu'un homme ne court (6,5 m/s)
            if j.role == "forme":
                nx, ny = j.cible[0] * 0.5 + nx * 0.5, j.cible[1] * 0.5 + ny * 0.5
                if not sien:
                    dx, dy = nx - j.cible[0], ny - j.cible[1]
                    dd = math.hypot(dx, dy)
                    if dd > 0.7:
                        nx, ny = j.cible[0] + dx / dd * 0.7, j.cible[1] + dy / dd * 0.7
            j.cible = (nx, ny)
            j.role = "forme"

    def _breche(self, att: int) -> tuple[float, float] | None:
        """La brèche dans la dernière ligne adverse : le plus grand trou
        entre deux défenseurs voisins (ou entre un défenseur et la touche),
        juste devant la ligne de hors-jeu.  C'est là qu'on fait l'appel."""
        defs = sorted((j for j in self.actifs(1 - att) if j.fam == "DEF"), key=lambda j: j.y)
        if len(defs) < 2:
            return None
        lh = self.ligne_horsjeu(att)
        bords = [(4.0, defs[0].y), (defs[-1].y, LARG - 4.0)] + [(defs[i].y, defs[i + 1].y) for i in range(len(defs) - 1)]
        y0, y1 = max(bords, key=lambda p: p[1] - p[0])
        if y1 - y0 < 9.0:
            return None
        x = lh - 1.5 if att == 0 else lh + 1.5
        return (max(2.0, min(LONG - 2.0, x)), (y0 + y1) / 2)

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
        # UN soutien : le relayeur ou le pivot le plus proche, en retrait, à
        # dix mètres, à quarante-cinq degrés du côté du ballon
        cand = [j for j in siens if j.role == "forme" and j.role_tac in ("relayeur", "pivot", "meneur")]
        if cand:
            s = min(cand, key=lambda j: math.hypot(j.x - bx, j.y - by))
            if math.hypot(s.x - bx, s.y - by) < 25.0:
                dx, dy = gx - bx, gy - by
                n = math.hypot(dx, dy) or 1.0
                ux, uy = dx / n, dy / n
                signe = 1 if (s.y - by) >= 0 else -1
                ray = 11.0 - 3.0 * self.collectif[att]
                bouche = self.cote_suite[att] >= 2 and self._zone(by) != "A"
                if bouche:
                    # le côté est bouché : on vient proposer en retrait, vers l'axe, pour réorienter
                    signe = 1 if by < LARG / 2 else -1
                    s.cible = (max(2.0, min(LONG - 2.0, bx - ux * 8.0)), max(2.0, min(LARG - 2.0, by + signe * 10.0)))
                else:
                    s.cible = (max(2.0, min(LONG - 2.0, bx - ux * ray * 0.7 - uy * signe * ray * 0.7)),
                               max(2.0, min(LARG - 2.0, by - uy * ray * 0.7 + ux * signe * ray * 0.7)))
                s.role = "soutien"
                if bouche:
                    # et un second homme dans l'axe, plus bas : le pivot ou l'autre relayeur
                    autre = next((j for j in cand if j is not s and j.role == "forme"), None)
                    if autre is not None and math.hypot(autre.x - bx, autre.y - by) < 30.0:
                        autre.cible = (max(2.0, min(LONG - 2.0, bx - ux * 13.0)), LARG / 2 + (2.0 if by < LARG / 2 else -2.0))
                        autre.role = "soutien"
        # l'appel dans la brèche : quand le porteur a le temps, un attaquant
        # attaque le plus grand trou de la dernière ligne, en restant en jeu
        phase = self.phase[att]
        if phase in ("progression", "finition", "contre") and porteur is not None:
            risque = {"offensif": 1.4, "equilibre": 1.0, "prudent": 0.7}[self.tac[att]["risque"]]
            if self.tac[att]["attaquants"] == "profondeur":
                risque *= 1.3
            lh = self.ligne_horsjeu(att)
            sens = 1 if att == 0 else -1
            derriere = (gx - lh) * sens                 # les mètres entre la ligne adverse et le but
            temps = self._pression(porteur) < 0.55      # le porteur a le temps de voir la course
            breche = self._breche(att)
            coureurs = sorted([j for j in siens if j.role == "forme" and (j.role_tac in ("ailier", "buteur", "meneur")
                                                                          or (j.role_tac == "lateral" and j.travail_att >= 0.6))],
                              key=lambda j: -j.travail_att)
            lances = 0
            for j in coureurs:
                lance = j.appel_jusqua > self.t
                if not lance:
                    # une course se lance quand le porteur a le temps, quand il y a
                    # de la profondeur à attaquer, et quand on est en jeu
                    if lances >= 2 or not temps or derriere < 14.0 or self.hors_jeu(j, bx):
                        continue
                    if math.hypot(j.x - bx, j.y - by) > 42.0 or (j.x - bx) * sens < -6.0:
                        continue
                    chance = 0.05 * risque * (0.7 + 0.6 * j.travail_att) * (1.8 if phase == "contre" else 1.0)
                    if self.rs.random() >= chance:
                        continue
                    j.appel_jusqua = self.t + 2.8
                    # la destination : DERRIÈRE la ligne, dans la brèche si elle
                    # est à portée, sinon droit devant en glissant vers l'axe
                    fond = min(14.0, max(6.0, derriere - 7.0))
                    if breche is not None and math.hypot(breche[0] - j.x, breche[1] - j.y) < 30.0:
                        cx, cy = breche[0] + fond * sens, breche[1]
                        breche = None                   # un seul dans la brèche
                    else:
                        cx, cy = lh + fond * sens, j.y + (gy - j.y) * 0.35
                    j.appel_vers = (max(3.0, min(LONG - 3.0, cx)), max(3.0, min(LARG - 3.0, cy)))
                    # le timing : un bon lecteur attend sur la ligne, un autre part un pas trop tôt
                    j.appel_marge = 1.0 + self.rs.gauss(0.0, 1.4) * (1.2 - 0.6 * j.attr("CON") / 99)
                    self.evt("appel", de=j.pid, camp=att)
                lances += 1
                if j.appel_vers is None:
                    j.appel_vers = (max(3.0, min(LONG - 3.0, lh + 8.0 * sens)), j.y)
                # tant que la passe n'est pas partie, il court à la ligne sans la franchir
                cx, cy = j.appel_vers
                x = min(cx, lh - j.appel_marge) if att == 0 else max(cx, lh + j.appel_marge)
                j.cible = (x, cy)
                j.role = "appel"
                if lances >= 2:
                    break                               # deux appels à la fois, pas une ruée

    ESPACE = 8.0                                 # deux coéquipiers ne visent jamais le même mètre carré

    def _espacer(self):
        """Deux coéquipiers dont les cibles sont à moins de ESPACE mètres
        s'écartent l'un de l'autre : un onze occupe le terrain, il ne
        s'entasse pas autour du ballon.  Ceux qui vont au ballon (porteur,
        receveur, presseur, chasseur) gardent leur cible.  Autour du
        ballon, les défenseurs (marqueurs, coupeur, doubleur) gardent
        quatre mètres entre eux et avec le presseur : un pressing, pas un amas."""
        fixes = {"porteur", "receveur", "presse", "chasse", "gardien", "appel", "marque", "double", "arret"}
        for camp in (0, 1):
            defs = [j for j in self.actifs(camp) if j.role in ("presse", "coupe", "marque", "double")]
            for a in range(len(defs)):
                for c in range(a + 1, len(defs)):
                    ja, jc = defs[a], defs[c]
                    dx, dy = jc.cible[0] - ja.cible[0], jc.cible[1] - ja.cible[1]
                    d = math.hypot(dx, dy)
                    if d >= 4.0:
                        continue
                    # celui qui n'est pas le presseur s'écarte (ou les deux, à parts égales)
                    if d < 0.1:
                        dx, dy, d = 1.0, 0.0, 1.0
                    pousse = (4.0 - d) / d
                    if ja.role == "presse":
                        jc.cible = (jc.cible[0] + dx * pousse, jc.cible[1] + dy * pousse)
                    elif jc.role == "presse":
                        ja.cible = (ja.cible[0] - dx * pousse, ja.cible[1] - dy * pousse)
                    else:
                        ja.cible = (ja.cible[0] - dx * pousse * 0.5, ja.cible[1] - dy * pousse * 0.5)
                        jc.cible = (jc.cible[0] + dx * pousse * 0.5, jc.cible[1] + dy * pousse * 0.5)
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
        att = 1 - df
        phase = self.phase[df]
        tac = self.tac[df]
        mx, my = self.but_de(1 - df)                         # son propre but (but_de donne le but qu'on ATTAQUE)
        bxd = bx if df == 0 else LONG - bx                   # le ballon, vu de la défense
        adverses = [o for o in self.actifs(att) if not o.gk]
        porteur = b.porteur
        # --- le pressing : chacun son homme, en couvrant une ligne de passe
        if phase in ("pressing", "contre_pressing"):
            devant = sorted([j for j in siens if j.role_tac in ("buteur", "ailier", "meneur", "relayeur")],
                            key=lambda j: -j.pressing)
            n_press = 3
            pris: set[int] = set()
            # d'abord le porteur (ou le ballon libre), par le plus envieux des plus proches
            cibles = [(o, math.hypot(o.x - bx, o.y - by)) for o in ([b.porteur] if b.porteur else [])]
            presseur = min(devant, key=lambda j: math.hypot(j.x - bx, j.y - by) / (0.6 + 0.8 * j.pressing), default=None)
            if presseur is not None:
                # l'ombre : il arrive sur le porteur en coupant la passe vers
                # l'option la plus proche du porteur (le défenseur voisin)
                options = [o for o in self.actifs(att) if o is not porteur and 4.0 < math.hypot(o.x - bx, o.y - by) < 25.0]
                if porteur is not None and options:
                    o = min(options, key=lambda o: math.hypot(o.x - bx, o.y - by))
                    dx, dy = o.x - bx, o.y - by
                    n = math.hypot(dx, dy) or 1.0
                    presseur.cible = (bx + dx / n * 1.8, by + dy / n * 1.8)
                else:
                    presseur.cible = (bx + b.vx * 0.4, by + b.vy * 0.4)
                presseur.role = "presse"
                devant = [j for j in devant if j is not presseur]
            # puis chacun un homme, au contact côté but — et on le garde :
            # un marquage qui change d'homme à chaque tic, c'est le fouillis
            for j in devant[:n_press - 1]:
                adv = self._son_homme(j, [o for o in adverses if o is not porteur and o.pid not in pris], 25.0)
                if adv is None:
                    continue
                pris.add(adv.pid)
                dm = math.hypot(mx - adv.x, my - adv.y) or 1.0
                j.cible = (adv.x + (mx - adv.x) / dm * 1.8, adv.y + (my - adv.y) / dm * 1.8)
                j.role = "presse"
            # les autres tiennent la forme haute (déjà posée) ; les centraux montent à la ligne
            return
        # --- les blocs : le plus proche va au contact ou contient, la ligne tient
        tri = sorted(siens, key=lambda j: math.hypot(j.x - bx, j.y - by) / (0.65 + 0.7 * j.pressing))
        p = tri[0]
        if p.fam == "DEF" and bxd - self.ligne_def[df] > 20.0:
            autre = next((j for j in tri[1:] if j.fam != "DEF" and math.hypot(j.x - bx, j.y - by) < 18.0), None)
            if autre is not None:
                p = autre
        dx, dy = mx - bx, my - by
        n = math.hypot(dx, dy) or 1.0
        # on contient à deux mètres et demi : on ferme, on ne saute pas dans les pieds
        # (un presseur vorace se rapproche, un prudent reste à trois)
        if phase == "bloc_bas":
            contient = 0.0 if porteur is None else (3.5 if bxd > 40 else 2.2)
        else:
            contient = 0.0 if porteur is None else 2.5
        contient *= 1.25 - 0.5 * p.pressing
        # un bloc bas ne sort pas chercher le ballon au-delà de sa moitié
        if not (phase == "bloc_bas" and bxd > 55.0 and porteur is not None):
            p.cible = (bx + b.vx * 0.4 + dx / n * contient, by + b.vy * 0.4 + dy / n * contient)
            p.role = "presse"
        # le second coupe la ligne vers l'option la plus dangereuse
        second = next((j for j in tri[1:] if j.role == "forme"), None)
        cand = [o for o in adverses if o is not porteur]
        if second is not None and cand:
            gx, gy = self.but_de(att)
            danger = min(cand, key=lambda o: math.hypot(o.x - mx, o.y - my))
            second.cible = ((bx + danger.x) / 2, (by + danger.y) / 2)
            second.role = "coupe"
        # le marquage dans le dernier tiers : un défenseur par attaquant, sans
        # jamais descendre sous la ligne (sauf dans la surface).  L'attribution
        # est STABLE : chacun garde d'abord son homme (le porteur compris),
        # puis les libres prennent le plus proche — un marquage qui change
        # d'homme à chaque passe n'est jamais au contact.
        if bxd < 40.0:
            pris: set[int] = set()
            marqueurs = [x for x in tri if x.role == "forme" and x.fam in ("DEF", "MID")]
            attribs: dict[int, Joueur] = {}
            for j in marqueurs:
                if j.homme >= 0 and self.t - j.t_homme < 8.0:
                    o = next((o for o in adverses if o.pid == j.homme and o.pid not in pris), None)
                    if o is not None and math.hypot(o.x - j.x, o.y - j.y) <= (26.0 if j.fam == "DEF" else 18.0):
                        attribs[j.pid] = o
                        pris.add(o.pid)
            # les attaquants déjà dans les vingt-cinq mètres se prennent d'abord, par les défenseurs libres
            proches = [o for o in adverses if o.pid not in pris and math.hypot(o.x - mx, o.y - my) < 25.0]
            for j in [x for x in marqueurs if x.pid not in attribs and x.fam == "DEF"]:
                adv = min((o for o in proches if o.pid not in pris), key=lambda o: math.hypot(o.x - j.x, o.y - j.y), default=None)
                if adv is None or math.hypot(adv.x - j.x, adv.y - j.y) > 22.0:
                    continue
                attribs[j.pid] = adv
                pris.add(adv.pid)
                j.homme, j.t_homme = adv.pid, self.t
            for j in [x for x in marqueurs if x.pid not in attribs]:
                adv = min((o for o in adverses if o.pid not in pris), key=lambda o: math.hypot(o.x - j.cible[0], o.y - j.cible[1]), default=None)
                if adv is None or math.hypot(adv.x - j.cible[0], adv.y - j.cible[1]) > 14.0:
                    continue
                attribs[j.pid] = adv
                pris.add(adv.pid)
                j.homme, j.t_homme = adv.pid, self.t
            for j in marqueurs:
                adv = attribs.get(j.pid)
                if adv is None:
                    continue
                dm = math.hypot(mx - adv.x, my - adv.y) or 1.0
                recul = 1.5 if dm < 22 else 4.0
                # côté but de son homme, et un peu devant sa course : on ne suit pas, on accompagne
                ax, ay = adv.x + adv.vx * 0.4, adv.y + adv.vy * 0.4
                cx, cy = ax + (mx - ax) / dm * recul, ay + (my - ay) / dm * recul
                if j.fam == "DEF" and dm > 22:
                    cxp, cyp = j.propre(cx, cy)
                    cxp = max(cxp, self.ligne_def[df] - 1.0)
                    cx, cy = j.absolu(cxp, cyp)
                j.cible = (cx, cy)
                j.role = "marque"
        self._doubler(df, siens, adverses)

    def _son_homme(self, j: Joueur, cand: list[Joueur], portee: float, depuis: tuple[float, float] | None = None):
        """L'homme que j marque : celui qu'il tenait déjà s'il est encore à
        portée (six secondes de fidélité), sinon le plus proche."""
        ox, oy = depuis or (j.x, j.y)
        if j.homme >= 0 and self.t - j.t_homme < 6.0:
            o = next((o for o in cand if o.pid == j.homme), None)
            if o is not None and math.hypot(o.x - ox, o.y - oy) <= portee + 4.0:
                return o
        adv = min(cand, key=lambda o: math.hypot(o.x - ox, o.y - oy), default=None)
        if adv is None or math.hypot(adv.x - ox, adv.y - oy) > portee:
            return None
        if adv.pid != j.homme:
            j.homme, j.t_homme = adv.pid, self.t
        return adv

    def _doubler(self, df: int, siens: list[Joueur], adverses: list[Joueur]):
        """Le repli des ailiers (et des attaquants qui travaillent) : côté
        ballon, l'ailier revient doubler son latéral sur l'ailier adverse
        qui attaque le couloir.  Le work rate décide qui le fait."""
        b = self.ballon
        mx, my = self.but_de(1 - df)                          # son propre but
        for j in siens:
            if j.role != "forme" or j.role_tac not in ("ailier", "buteur"):
                continue
            seuil = 0.45 if j.role_tac == "ailier" else 0.75
            if j.travail_def < seuil:
                continue
            gauche = j.home[1] < LARG / 2
            # l'adversaire qui attaque son couloir : un latéral ou un ailier de ce côté, près du ballon
            cand = [o for o in adverses if o.role_tac in ("lateral", "ailier")
                    and (o.propre(o.x, o.y)[1] >= LARG / 2) == gauche      # son côté à lui, vu de l'autre camp
                    and math.hypot(o.x - b.x, o.y - b.y) < 22.0 and math.hypot(o.x - j.x, o.y - j.y) < 32.0]
            if not cand:
                continue
            o = min(cand, key=lambda o: math.hypot(o.x - mx, o.y - my))
            # notre latéral de ce côté : on double s'il est seul, entre l'adversaire et lui
            lat = next((x for x in siens if x.role_tac == "lateral" and (x.home[1] < LARG / 2) == gauche), None)
            if lat is not None and math.hypot(lat.x - o.x, lat.y - o.y) < 3.0 and o is not b.porteur:
                continue
            if sum(1 for x in siens if x is not j and math.hypot(x.x - o.x, x.y - o.y) < 5.0) >= 2:
                continue                                # déjà deux des nôtres dessus : on ne s'entasse pas
            dm = math.hypot(mx - o.x, my - o.y) or 1.0
            j.cible = (o.x + (mx - o.x) / dm * 2.5, o.y + (my - o.y) / dm * 2.5)
            j.role = "double"

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
            libre = b.porteur is None and b.vitesse() < 8 and self.arret is None
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
        if j.gk:
            self._relancer(j, force)
            return
        gx, gy = self.but_de(camp)
        dbut = math.hypot(gx - j.x, gy - j.y)
        pression = self._pression(j)
        tenu = self.t - j.dernier_contact
        tac = self.tac[camp]
        coh = self.collectif[camp]
        phase = self.phase[camp]
        gk_adv = next((o for o in self.actifs(1 - camp) if o.gk), None)
        d_gk = math.hypot(gk_adv.x - j.x, gk_adv.y - j.y) if gk_adv else 99.0
        # seul au but : personne dans le couloir entre lui et le but (à part le gardien)
        seul = dbut < 40 and abs(j.y - LARG / 2) < 16.0 and not j.gk and self._seul_au_but(j, dbut)
        if seul and dbut > 17 and d_gk > 9.0 and not force:
            # il file au but : il ira au duel avec le gardien, pas de latérale
            if self.t > j.perce_jusqua + 1.0:
                self.evt("seul", de=j.pid, camp=camp, x=round(j.x, 1), y=round(j.y, 1), d=round(dbut, 1), gk=round(d_gk, 1))
            j.perce_jusqua = self.t + 0.6
            self._conduire(j, percee=True, au_but=True)
            return
        # une provocation en cours se tient une seconde
        if self.t < j.provoque_jusqua and not force and dbut > 12:
            self._conduire(j, provoque=True)
            return
        # une percée en cours se tient : on ne lâche pas le ballon au premier
        # tic, sauf quand un adversaire arrive ou quand la frappe est là
        if self.t < j.perce_jusqua and not force and pression < 0.7 and dbut > 22 and not seul:
            self._conduire(j, percee=True)
            return
        tempo = {"possession": 1.25, "equilibre": 1.0, "direct": 0.7}[tac["tempo"]]
        # un temps de contrôle, plus court sous pression, plus court dans les
        # trente derniers mètres, plus court quand on joue direct
        garde = (3.6 + 3.0 * (1 - pression)) * (1.0 - 0.3 * j.attr("CON") / 99) * tempo
        if dbut < 32:
            garde *= 0.7
        if pression > 0.6:
            garde *= 0.7                                  # un homme dans les pieds : on lâche
        (_, _), dev = self._espace_devant(j)
        if dev > 8.0:
            garde *= 1.0 - 0.4 * min(dev, 20.0) / 20.0   # du champ devant : on ne s'arrête pas pour réfléchir
        if not force and tenu < garde:
            if not (dbut < 24 and tenu > 0.3):        # dans la zone de frappe, on ne réfléchit pas trois secondes
                if dev > 7.0 and pression < 0.6:
                    self._conduire(j)                 # et on réfléchit en avançant
                elif pression < 0.7 and tenu > 0.5:
                    self._conduire(j, derive=True)    # fermé devant : on dérive vers le côté ouvert
                return
        options: list[tuple[float, str, object]] = []
        # le bruit de décision : moins avec le sang-froid, moins dans un
        # collectif rodé (chacun sait ce que l'autre va faire)
        bruit = 0.25 * (1.0 - 0.5 * j.attr("CON") / 99) * (1.25 - 0.5 * coh)
        # -- frapper : une occasion se prend, surtout si rien ne bouche l'axe ;
        # de loin, face à un bloc bas qui ne s'ouvre pas, on tente sa chance
        if dbut < 36 and not j.gk:
            ang = self._angle_but(j.x, j.y, camp)
            xg = self._xg(dbut, ang, pression)
            axe = self._axe_libre(j)
            val = 0.55 + 7.5 * xg * (0.6 + 0.8 * j.attr("FIN") / 99) + (0.4 if dbut < 18 else 0.0) - 0.15 * pression + 0.35 * axe * (1.0 if dbut < 22 else 0.2)
            if ang < 0.25 and dbut > 9:
                val -= 0.6                                # un angle fermé : on cherche mieux
            if xg < 0.05 and not seul:
                val -= 0.55                               # une frappe pour rien : on cherche mieux
            if 20 < dbut < 36 and self.phase[1 - camp] == "bloc_bas" and axe > 0.6 and pression < 0.5 and abs(j.y - gy) < 14:
                val += 0.45 + 0.5 * j.attr("FIN") / 99    # le bloc est bas et l'axe s'ouvre : la frappe de loin
            if seul and dbut < 20:
                val += 1.5                                # le duel avec le gardien se finit
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
            hj = self.hors_jeu(c, b.x, retard=True)      # la ligne telle qu'il l'a vue, pas telle qu'elle est
            if hj and self.rs.random() < 0.03:
                hj = False                              # il n'a pas vu la ligne du tout : le drapeau se lèvera
            # une équipe menée en fin de match, ou qui joue direct, accepte l'homme tenu
            audace = (0.4 if (self.score[camp] < self.score[1 - camp] and self.t > 55 * 60) else 0.0) + (0.3 if tac["tempo"] == "direct" else 0.0)
            # l'homme libre près du but vaut de l'or ; le tempo direct aime les longues
            val = (0.25 + 1.4 * gain + 0.6 * danger + 0.1 * min(libre, 8.0) + 1.0 * couloir - 0.012 * d
                   - 0.025 * max(0.0, d - 22.0) * tempo - ((0.5 - audace * 0.5) if libre < 3.0 else 0.0)
                   + 0.5 * danger * min(libre, 10.0) / 10.0 * (0.6 + 0.4 * coh))
            # dans les trente derniers mètres, on ne rend pas le ballon à un
            # central libre à trente mètres derrière — sauf sous pression
            if dbut < 35 and gain < -0.25 and pression < 0.6:
                val -= 0.7
            # dans la surface, on ne remet pas en retrait ou de côté : on frappe, sauf
            # pour un coéquipier encore mieux placé
            if dbut < 20 and gain < 0.1 and math.hypot(gx - c.x, gy - c.y) > dbut - 3.0:
                val -= 0.7
            # la balle qui navigue sur la ligne : une latérale vers un homme
            # tenu, dans le camp adverse, n'apporte rien
            if phase in ("progression", "finition") and abs(gain) < 0.1 and libre < 5.0:
                val -= 0.35
            # seul au but, on ne donne qu'à un coéquipier mieux placé et aussi seul
            if seul and not (libre > 6.0 and math.hypot(gx - c.x, gy - c.y) < dbut - 3.0):
                val -= 1.2
            # le une-deux : on ne remet pas au passeur pour rien — sauf dans sa course
            if c.pid == j.recu_de and self.t - j.t_recu < 2.5 and gain < 0.15:
                val -= 0.6
            # un côté bouché se quitte : après deux passes sur le même côté sans
            # progresser, on n'insiste pas — on repasse par l'axe, ou on renverse
            zj, zc = self._zone(j.y), self._zone(c.y)
            n_cote = self.cote_suite[camp]
            seuil_cote = 2 if phase in ("construction", "progression", "relance") else 3
            if zj != "A" and n_cote >= seuil_cote:
                k_cote = 1.0 if phase in ("construction", "progression", "relance") else 0.7
                if zc == zj and gain < 0.25:
                    val -= 0.3 * k_cote * min(n_cote - 1, 4)
                elif zc == "A":
                    val += (0.2 + 0.1 * min(n_cote, 4)) * k_cote
                elif couloir > 0.5:
                    val += (0.35 + 0.1 * min(n_cote, 4)) * k_cote + 0.025 * max(0.0, d - 22.0) * tempo   # la transversale
            # une passe dans la surface pour un coureur : la passe qui tue
            if c.role == "appel" and math.hypot(gx - c.x, gy - c.y) < 25:
                val += 0.6
            if hj:
                val -= 3.0
            if c.gk:
                val -= 0.6
            val += self.rs.gauss(0, bruit)
            options.append((val, "passe", c))
            # -- la passe en profondeur : dans l'espace derrière la ligne, pour
            # un coéquipier lancé qui y arrive avant le défenseur
            # (un coureur parti un pas trop tôt : le passeur l'a vu partir en jeu, il joue quand même)
            hj_course = hj and not (c.appel_marge < 0.6 and self.rs.random() < 0.5)
            if c.role == "appel" and c.appel_vers is not None and not hj_course and not c.gk:
                px, py = c.appel_vers
                dp = math.hypot(px - j.x, py - j.y)
                if 8.0 < dp < 52.0 and (px - j.x) * j.sens() > 4.0 and math.hypot(px - c.x, py - c.y) > 4.0:
                    _, libre_p = self.plus_proche(1 - camp, px, py, gk=False)
                    d_c = math.hypot(px - c.x, py - c.y)
                    gk_adv = next((o for o in self.actifs(1 - camp) if o.gk), None)
                    d_gk = math.hypot(gk_adv.x - px, gk_adv.y - py) if gk_adv else 99.0
                    couloir_p = self._couloir_vers(j, px, py)
                    vc = math.hypot(c.vx, c.vy)
                    avantage = max(-1.0, min(1.0, (libre_p - d_c * 0.6) / 8.0))     # lancé, il a un temps d'avance
                    danger_p = 1.0 - math.hypot(gx - px, gy - py) / 105.0
                    val = (0.35 + 1.2 * danger_p + 0.8 * couloir_p + 0.7 * avantage + 0.3 * min(vc, 8.0) / 8.0
                           - 0.02 * max(0.0, dp - 32.0) + 0.35 * (j.attr("CRE") / 99) - 0.2 * pression)
                    if avantage < 0.0:
                        val -= 0.8                      # le défenseur y sera avant : ce n'est pas une passe
                    if tac["risque"] == "offensif" or tac["tempo"] == "direct":
                        val += 0.2
                    if d_gk < 11.0:
                        val -= 0.8                      # le gardien sort dessus
                    if libre_p < 2.5:
                        val -= 0.6
                    options.append((val + self.rs.gauss(0, bruit), "profondeur", (c, px, py)))
        # -- centrer, depuis le couloir dans les trente derniers mètres
        if abs(j.y - LARG / 2) > 18.0 and (gx - j.x) * j.sens() < 32 and not j.gk:
            dans = [c for c in self.actifs(camp) if c is not j and math.hypot(gx - c.x, gy - c.y) < 22]
            if dans:
                val = 0.8 + 0.25 * len(dans) + 0.4 * j.attr("CRE") / 99 - 0.4 * pression
                options.append((val + self.rs.gauss(0, bruit), "centre", None))
        # -- conduire
        # une somme d'individualités conduit plus qu'elle ne combine
        val = 0.7 + 0.06 * min(dev, 12.0) + 0.3 * j.attr("DRI") / 99 - 0.9 * pression + 0.35 * (1.0 - coh)
        if dbut < 40:
            val += 0.25
        options.append((val + self.rs.gauss(0, bruit), "conduite", None))
        # -- provoquer : l'ailier face à son vis-à-vis dans le dernier tiers,
        # rentre sur son bon pied (ailier inversé) ou déborde
        _, d_vis = self.plus_proche(1 - camp, j.x, j.y, gk=False)
        if j.role_tac == "ailier" and dbut < 42 and abs(j.y - LARG / 2) > 11.0 and 2.0 < d_vis < 9.0 and not seul:
            val = 1.45 + 0.9 * j.attr("DRI") / 99 + (0.3 if self._rentre(j) else 0.0) - 0.5 * pression + 0.15 * (1.0 - coh)
            options.append((val + self.rs.gauss(0, bruit), "provoque", None))
        # -- percer : un boulevard devant, un dribbleur qui le prend à pleine vitesse
        # (un central qui a vingt mètres devant lui en construction ne perce pas : il relance)
        seuil_dev = 8.0 if dbut < 36 else 14.0        # dans le dernier tiers, huit mètres libres sont déjà un boulevard
        if (dev > seuil_dev and dbut > 14 and phase in ("progression", "finition", "contre")
                and (j.fam != "DEF" or j.attr("DRI") > 72)):
            val = (0.15 + 0.05 * min(dev, 24.0) + 0.7 * j.attr("DRI") / 99 - 0.9 * pression + 0.3 * (1.0 - coh)
                   + (0.4 if phase == "contre" else 0.0) + 0.15 * j.travail_att + (0.45 if dbut < 36 else 0.0))
            options.append((val + self.rs.gauss(0, bruit), "percee", None))
        # -- dégager sous pression dans son camp
        if pression > 0.5 and (j.x - LONG / 2) * j.sens() < -20:
            options.append((0.9 + self.rs.gauss(0, bruit), "degagement", None))
        options.sort(key=lambda o: -o[0])
        _, quoi, cible = options[0]
        if quoi == "tir":
            self._frapper(j)
        elif quoi == "passe":
            self._passer(j, cible)
        elif quoi == "profondeur":
            c, px, py = cible
            self._passer(j, c, point=(px, py))
        elif quoi == "percee":
            if self.t > j.perce_jusqua + 1.0:
                self.evt("percee", de=j.pid, camp=camp, x=round(j.x, 1), y=round(j.y, 1))
            j.perce_jusqua = self.t + 1.8
            self._conduire(j, percee=True)
        elif quoi == "provoque":
            if self.t > j.provoque_jusqua + 1.5:
                self.evt("provoque", de=j.pid, camp=camp, rentre=self._rentre(j))
            j.provoque_jusqua = self.t + 1.2
            self._conduire(j, provoque=True)
        elif quoi == "degagement":
            self._degager(j)
        elif quoi == "centre":
            self._centrer(j)
        else:
            self._conduire(j)

    def _seul_au_but(self, j: Joueur, dbut: float) -> bool:
        gx, gy = self.but_de(j.camp)
        ux, uy = (gx - j.x) / (dbut or 1.0), (gy - j.y) / (dbut or 1.0)
        for o in self.actifs(1 - j.camp):
            if o.gk:
                continue
            px, py = o.x - j.x, o.y - j.y
            if math.hypot(px, py) < 6.0:
                return False                          # dans son dos, il peut le rattraper
            t = px * ux + py * uy                      # sa position le long de la course
            if -4.0 < t < dbut and abs(px * uy - py * ux) < 12.0:
                return False                          # dans le couloir : il peut revenir
        return True

    def _rentre(self, j: Joueur) -> bool:
        """Un ailier rentre sur son bon pied quand il est inversé (droitier à
        gauche, gaucher à droite) ; un ambidextre rentre aussi."""
        yp = j.propre(j.x, j.y)[1]
        a_gauche = yp < LARG / 2
        return j.pied_faible >= 5 or (a_gauche and j.pied == "droit") or (not a_gauche and j.pied == "gauche")

    def _relancer(self, gk: Joueur, force: bool = False):
        """La relance du gardien : courte, dans les pieds d'un homme libre
        avec une ligne ; longue, en cloche sur l'attaquant, le bloc monte
        à la retombée.  Sous pression sans ligne courte, on joue long."""
        b = self.ballon
        camp = gk.camp
        pression = self._pression(gk)
        tenu = self.t - gk.dernier_contact
        if not force and tenu < 1.2 - 0.8 * pression:
            return                                    # il regarde avant de jouer
        choix = self.relance_choix[camp] if self.phase[camp] == "relance" else self._choix_relance(camp)
        siens = [c for c in self.actifs(camp) if c is not gk]
        if not siens:
            return
        if choix == "courte":
            best, bv = None, -9.0
            for c in siens:
                d = math.hypot(c.x - gk.x, c.y - gk.y)
                if d < 3.0 or d > 38.0:
                    continue
                _, libre = self.plus_proche(1 - camp, c.x, c.y, gk=False)
                couloir = self._couloir_libre(gk, c)
                val = (0.1 * min(libre, 10.0) + 0.8 * couloir - 0.015 * d + (0.3 if c.fam == "DEF" else 0.0)
                       + 0.2 * (c.x - gk.x) * gk.sens() / 35.0 + self.rs.gauss(0, 0.1))
                if libre < 4.0 or couloir < 0.3:
                    val -= 1.0                        # pas dans les pieds d'un homme tenu
                if val > bv:
                    best, bv = c, val
            if best is not None and (bv > 0.2 or pression < 0.25):
                self._passer(gk, best, courte=True)
                return
            # aucune ligne courte : on n'insiste pas, on joue long
        # long : sur l'attaquant le moins couvert, en cloche, loin dans le camp adverse
        cand = [c for c in siens if c.role_tac in ("buteur", "ailier", "meneur")] or [c for c in siens if c.fam != "DEF"] or siens
        def valeur(c):
            _, libre = self.plus_proche(1 - camp, c.x, c.y, gk=False)
            return (c.x - gk.x) * gk.sens() / 60.0 + 0.05 * min(libre, 10.0) + (0.3 if c.role_tac == "buteur" else 0.0) \
                - (0.6 if self.hors_jeu(c, b.x) else 0.0)
        c = max(cand, key=valeur)
        self._passer(gk, c, longue=True)

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
        return max(0.01, min(0.9, base * (1.0 - 0.3 * pression)))

    def _couloir_libre(self, de: Joueur, a: Joueur) -> float:
        """1 si personne n'est sur la ligne de passe, 0 si un adversaire
        est dedans."""
        return self._couloir_vers(de, a.x, a.y)

    def _couloir_vers(self, de: Joueur, ax: float, ay: float) -> float:
        dx, dy = ax - de.x, ay - de.y
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

    @staticmethod
    def _zone(y: float) -> str:
        return "G" if y < LARG / 2 - 10.0 else ("D" if y > LARG / 2 + 10.0 else "A")

    def _passer(self, j: Joueur, c: Joueur, courte: bool = False, point: tuple[float, float] | None = None,
                longue: bool = False):
        b = self.ballon
        zj, zc = self._zone(j.y), self._zone(c.y)
        self.cote_suite[j.camp] = self.cote_suite[j.camp] + 1 if (zj != "A" and zc == zj) else 0
        dx, dy = c.x - j.x, c.y - j.y
        d = math.hypot(dx, dy) or 1.0
        if point is not None:
            # dans l'espace : le ballon va où le coureur va, pas où il est
            vise_x, vise_y = point
        else:
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
        gx_, gy_ = self.but_de(j.camp)
        serre = 1.35 if math.hypot(gx_ - j.x, gy_ - j.y) < 35.0 else 1.0     # dans le dernier tiers, tout va plus vite
        sigma = math.radians((1.0 + 4.0 * (1 - precision) + 3.0 * pression + 0.045 * d) * serre)
        ang = math.atan2(dy, dx) + self.rs.gauss(0, sigma)
        # la passe ratée : sous pression, de loin, dans le dernier tiers, ou par
        # manque de technique, une passe sur dix part de travers ou mal dosée
        p_rate = (0.04 + 0.09 * pression + 0.07 * min(d, 40.0) / 40.0 + (0.05 if serre > 1.0 else 0.0)) * (1.4 - 0.8 * precision)
        if self.rs.random() < p_rate:
            ang += self.rs.gauss(0, sigma * 4.0 + math.radians(6.0))
            v *= self.rs.uniform(0.6, 1.3)
        vz = 0.0
        haut = longue or d > 30 or (self._couloir_vers(j, vise_x, vise_y) < 0.2 and d > 15)
        if point is not None and d < 30 and not longue:
            v += 1.5                                  # une passe en profondeur file, elle n'attend pas
            v = min(VITESSE_PASSE[1], v)
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
            tiers = [o for o in self.actifs(j.camp) if o not in (j, c) and not o.gk
                     and (o.fam in ("FWD", "MID") or (o.role_tac == "lateral" and o.travail_att >= 0.6))
                     and (o.x - c.x) * j.sens() > -8.0 and math.hypot(o.x - c.x, o.y - c.y) < 25.0]
            if tiers:
                min(tiers, key=lambda o: math.hypot(gx - o.x, gy - o.y)).appel_jusqua = self.t + 2.2
        b.hors_jeu_au_kick = {x.pid for x in self.actifs(j.camp) if x is not j and self.hors_jeu(x, b.x)}
        self.evt("passe", de=j.pid, a=c.pid, camp=j.camp, x=round(j.x, 1), y=round(j.y, 1), d=round(d, 1), haut=vz > 0, role=c.role,
                 prof=point is not None, longue=longue)

    def _centrer(self, j: Joueur):
        """Un centre : vers le coéquipier le mieux placé dans la surface (le
        plus libre, le plus près du but), un peu devant lui, et en l'air à
        hauteur de tête quand il arrive — c'est là que ça se dispute."""
        gx, gy = self.but_de(j.camp)
        dans = [c for c in self.actifs(j.camp) if c is not j and not c.gk
                and abs(c.x - gx) < 18.0 and abs(c.y - gy) < 18.0]
        c = None
        if dans:
            def valeur(c):
                _, libre = self.plus_proche(1 - j.camp, c.x, c.y, gk=False)
                return min(libre, 6.0) - 0.08 * math.hypot(gx - c.x, gy - c.y)
            c = max(dans, key=valeur)
            cx, cy = c.x + c.vx * 0.5 + self.rs.gauss(0, 1.5), c.y + c.vy * 0.5 + self.rs.gauss(0, 1.5)
        else:
            cx, cy = gx - 9.0 * j.sens(), gy + self.rs.uniform(-6.0, 6.0)
        dx, dy = cx - j.x, cy - j.y
        d = math.hypot(dx, dy) or 1.0
        sigma = math.radians(4.0 + 8.0 * (1 - j.attr("CRE") / 99))
        ang = math.atan2(dy, dx) + self.rs.gauss(0, sigma)
        v = max(12.0, min(22.0, 10.0 + 0.4 * d))
        T = d / v
        vz = (1.7 + 0.5 * GRAVITE * T * T) / T          # à hauteur de tête à l'arrivée
        j.passes += 1
        self.stats["passes"][j.camp] += 1
        self._lacher(j, v * math.cos(ang), v * math.sin(ang), vz)
        self.ballon.passe_vers = c
        self.ballon.hors_jeu_au_kick = {x.pid for x in self.actifs(j.camp) if x is not j and self.hors_jeu(x, self.ballon.x)}
        self.evt("centre", de=j.pid, camp=j.camp, a=c.pid if c else None)

    def _degager(self, j: Joueur):
        gx, gy = self.but_de(j.camp)
        ang = math.atan2(gy - j.y + self.rs.uniform(-20, 20), gx - j.x) + self.rs.gauss(0, 0.15)
        mx, my = self.but_de(1 - j.camp)
        if math.hypot(j.x - mx, j.y - my) < 20.0 and self._pression(j) > 0.5 and self.rs.random() < 0.45:
            # en catastrophe, dans sa surface : n'importe où, souvent en corner
            ang = math.atan2(1.0 if j.y >= my else -1.0, -0.6 * j.sens()) + self.rs.gauss(0, 0.35)
        self._lacher(j, 24.0 * math.cos(ang), 24.0 * math.sin(ang), 8.0)
        self.ballon.passe_vers = None
        self.evt("degagement", de=j.pid, camp=j.camp)

    def _conduire(self, j: Joueur, percee: bool = False, au_but: bool = False, provoque: bool = False, derive: bool = False):
        (ux, uy), dev = self._espace_devant(j)
        gx, gy = self.but_de(j.camp)
        if derive:
            # à 60° de chaque côté de l'axe du but, le côté le plus ouvert ; quatre mètres, au pas
            meilleur, best = None, -1.0
            for a in (-1.05, 1.05):
                ca, sa = math.cos(a), math.sin(a)
                vx, vy = ux * ca - uy * sa, ux * sa + uy * ca
                libre = min((math.hypot(o.x - j.x, o.y - j.y) for o in self.actifs(1 - j.camp)
                             if ((o.x - j.x) * vx + (o.y - j.y) * vy) / (math.hypot(o.x - j.x, o.y - j.y) or 1.0) > 0.5), default=25.0)
                if libre > best:
                    meilleur, best = (vx, vy), libre
            vx, vy = meilleur
            j.cible = (max(1.0, min(LONG - 1.0, j.x + vx * 4.0)), max(1.0, min(LARG - 1.0, j.y + vy * 4.0)))
            j.role = "porteur"
            return
        if au_but:
            # droit au but, pas vers l'espace : il va au duel
            n = math.hypot(gx - j.x, gy - j.y) or 1.0
            ux, uy = (gx - j.x) / n, (gy - j.y) / n
            j.cible = (max(1.0, min(LONG - 1.0, j.x + ux * 12.0)), max(1.0, min(LARG - 1.0, j.y + uy * 12.0)))
            j.role = "porteur"
            return
        if provoque:
            # rentrer sur le bon pied : vers l'axe en diagonale ; sinon déborder le long de la ligne
            if self._rentre(j):
                tx, ty = gx - 10.0 * j.sens(), gy
            else:
                tx, ty = gx - 3.0 * j.sens(), j.y + (4.0 if j.y > LARG / 2 else -4.0)
            n = math.hypot(tx - j.x, ty - j.y) or 1.0
            j.cible = (max(1.0, min(LONG - 1.0, j.x + (tx - j.x) / n * 9.0)), max(1.0, min(LARG - 1.0, j.y + (ty - j.y) / n * 9.0)))
            j.role = "porteur"
            return
        # on s'écarte un peu du défenseur le plus proche
        o, d = self.plus_proche(1 - j.camp, j.x, j.y, gk=False)
        if o is not None and d < 4.0:
            ox, oy = j.x - o.x, j.y - o.y
            n = math.hypot(ox, oy) or 1.0
            ux, uy = ux * 0.75 + ox / n * 0.25, uy * 0.75 + oy / n * 0.25
            n = math.hypot(ux, uy) or 1.0
            ux, uy = ux / n, uy / n
        if percee:
            portee = 20.0                               # le boulevard se prend en sprintant
        else:
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
        # de quel pied : le ballon à sa gauche se frappe du droit, à sa droite
        # du gauche, dans l'axe du bon pied ; le mauvais pied coûte
        yp = j.propre(j.x, j.y)[1]
        pied = ("droit" if yp < LARG / 2 - 3.0 else "gauche" if yp > LARG / 2 + 3.0 else j.pied) if not penalty else j.pied
        mauvais = (pied != j.pied and j.pied_faible < 5)
        malus = 0.12 * (5 - j.pied_faible) if mauvais else 0.0
        # où il vise : un poteau, avec une erreur qui dépend de la finition et de la pression
        cote = self.rs.choice([-1, 1])
        vise_y = gy + cote * (BUT_LARG / 2 - 0.5) * self.rs.uniform(0.3, 1.0)
        sigma = math.radians((14.0 + 10.0 * (1 - fin) + 7.0 * pression + 0.35 * d) * (1.0 + malus))
        theta = math.atan2(vise_y - j.y, gx - j.x) + self.rs.gauss(0, sigma)
        v = VITESSE_TIR[0] + (VITESSE_TIR[1] - VITESSE_TIR[0]) * (0.4 + 0.6 * fin) * (1.0 - 0.3 * pression) * (1.0 - 0.25 * malus)
        # la hauteur : un tir tendu, parfois enlevé
        vz = max(0.0, self.rs.gauss(2.0 + 0.08 * d, 2.4 + 2.5 * (1 - fin) + 1.5 * pression))
        j.tirs += 1
        self.stats["tirs"][camp] += 1
        self.stats["xg"][camp] += xg
        self._lacher(j, v * math.cos(theta), v * math.sin(theta), vz)
        b.passe_vers = None
        self.evt("tir", de=j.pid, camp=camp, xg=round(xg, 3), d=round(d, 1), penalty=penalty, pied=pied[0].upper())
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
                plafond = {"forme": 3.3, "marque": 4.8, "gardien": 6.0, "coupe": 5.5, "soutien": 5.5, "receveur": 7.5,
                           "chasse": 6.6, "double": 6.2}.get(j.role)
                if j.role in ("receveur", "chasse") and self.d_ballon(j) > 8.0:
                    plafond = 7.8                    # loin du ballon, on y va à fond : c'est là que la pointe se voit
                if j.role == "presse":
                    fuit = (b.porteur is not None and math.hypot(b.porteur.vx, b.porteur.vy) > 4.5) or (b.porteur is None and b.vitesse() > 6.0)
                    if not fuit:
                        plafond = 6.6            # on arrive vite ; on ne sprinte que sur un porteur qui s'échappe
                if plafond is not None:
                    plafond *= j.vmax / 8.83     # un rapide trotte plus vite aussi
                if j.role == "porteur":
                    # balle au pied on va bien moins vite qu'un défenseur qui court : une
                    # conduite se fait à 20 km/h, une percée à 27, un défenseur revient à 30
                    plafond = j.vmax * (0.85 if self.t < j.perce_jusqua else 0.58)
                    if self.t < j.provoque_jusqua:
                        plafond = j.vmax * 0.72      # on provoque à demi-vitesse, le crochet fait le reste
                    elif self.t >= j.perce_jusqua:
                        # un défenseur à trois mètres et demi devant : on ne rentre pas dedans,
                        # on ralentit, on protège, on donne — le duel, c'est quand on le cherche
                        _, dev = self._espace_devant(j)
                        if dev < 3.5:
                            plafond = 2.5
                if self.t < j.battu_jusqua:
                    plafond = 2.0                    # passé : le temps de se retourner
                elif j.role == "forme":
                    ph = self.phase[j.camp]
                    devant = (j.x - b.x) * j.sens() > 3.0
                    if ph == "contre" and j.role_tac in ("ailier", "buteur") and devant:
                        plafond = 7.3 * j.vmax / 8.83        # la transition offensive : les attaquants partent
                    elif ph == "contre" and j.role_tac in ("meneur", "relayeur"):
                        plafond = 5.5 * j.vmax / 8.83
                    elif ph in ("bloc_bas", "bloc_median", "contre_pressing") and j.fam != "DEF" and (j.x - b.x) * j.sens() > 14.0:
                        plafond = 5.0 * j.vmax / 8.83        # le repli : on rentre derrière le ballon en courant
                if j.role in ("forme", "marque", "coupe") and math.hypot(tx - j.x, ty - j.y) > 10.0:
                    # loin de sa place, on y court ; un bloc sans ballon qui doit se replacer court vite
                    plafond = max(plafond or 0.0, (5.2 if self.phase[j.camp] in ("bloc_bas", "bloc_median") else 4.8) * j.vmax / 8.83)
                if j.role == "marque" and j.homme >= 0:
                    h = next((o for o in self.actifs(1 - j.camp) if o.pid == j.homme), None)
                    if h is not None and math.hypot(h.vx, h.vy) > 4.5:
                        plafond = j.vmax * 0.9           # son homme part : il part avec lui
                    elif h is not None and math.hypot(tx - j.x, ty - j.y) > 4.0:
                        plafond = 5.5 * j.vmax / 8.83    # loin de lui : il revient en courant
                if j.fam == "DEF" and j.role in ("forme", "marque", "coupe") and -(b.vx * j.sens()) > 3.0 \
                        and (j.x - b.x) * j.sens() < 0.0:
                    plafond = max(plafond or 0.0, 6.5 * j.vmax / 8.83)   # le ballon vient : la ligne recule en courant
                if plafond is not None:
                    v_lim = min(v_lim, plafond)
                # à bout de souffle, on ne sprinte plus : on court
                if j.souffle <= 0.0:
                    v_lim = min(v_lim, SPRINT - 0.6)
            dx, dy = tx - j.x, ty - j.y
            d = math.hypot(dx, dy)
            # une zone morte : personne ne fait deux pas pour un mètre
            tol = 0.3 if j.role in ("porteur", "presse", "receveur", "gardien", "chasse") else (2.5 if j.role == "forme" else 1.5)
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
                j.souffle = max(0.0, j.souffle - DT)
            elif v < 4.5:
                j.souffle = min(SOUFFLE, j.souffle + DT * 0.08)
            j.vmax_vue = max(j.vmax_vue, v)
            # l'usure : courir vite coûte, plus à qui a peu d'endurance
            cout = (0.00006 + 0.0011 * (v / 9.0) ** 3) * (1.0 + (70.0 - j.endurance_ea) / 100.0) * (1.25 - 0.5 * j.volume)
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
                if (b.passe_vers is not None and j.camp != b.passe_vers.camp and not j.gk
                        and math.hypot(j.x - b.passe_vers.x, j.y - b.passe_vers.y) < 2.2 and b.z < 1.0):
                    portee = 0.9 + 0.6 * j.recup      # le marqueur d'un homme tenu anticipe : il souffle le ballon
                if b.z > 1.0:
                    portee = 1.4                      # en l'air, on saute dessus : la tête se dispute
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
                # le duel aérien : si les deux camps sont sous le ballon, ce n'est pas
                # le plus près qui l'emporte mais le plus costaud — et celui qui l'attendait
                autre = next((c for _, c in cand[1:] if c.camp != j.camp and not c.gk), None)
                if autre is not None:
                    f_j = (j.physique.get("for", 68) or 68) if j.physique else 68
                    f_a = (autre.physique.get("for", 68) or 68) if autre.physique else 68
                    p_j = 0.5 + 0.3 * (f_j - f_a) / 99 + (0.12 if b.passe_vers is j else 0.0) - (0.12 if b.passe_vers is autre else 0.0) \
                        + 0.1 * (j.attr("DEF") - autre.attr("DEF")) / 99
                    if self.rs.random() > p_j:
                        j = autre
                self._tete(j)
                return
            # un ballon rapide se contrôle avec les attributs ; le gardien capte,
            # ou plonge sur une frappe — et peut la manquer
            v = b.vitesse()
            if j.gk and b.dernier is not None and b.dernier.camp != j.camp and v > 6.0:
                tir = self._tir_en_cours()
                if tir:
                    d = self.d_ballon(j)
                    p = (1.0 - 0.012 * max(0.0, v - 18.0) - 0.10 * d) * (0.72 + 0.28 * j.attr("ARR") / 99)
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
        if prec is not None and prec.camp == j.camp and prec is not j and passe_vers is not None:
            j.recu_de, j.t_recu = prec.pid, self.t
        else:
            j.recu_de = -1
        b.porteur = j
        b.passe_vers = None
        b.hors_jeu_au_kick = set()
        b.z = b.vz = 0.0
        b.vx, b.vy = j.vx, j.vy
        j.dernier_contact = self.t
        j.touches += 1
        j.role = "porteur"
        j.cible = (j.x, j.y)
        if not j.gk:
            mx, my = self.but_de(1 - j.camp)
            _, gene = self.plus_proche(1 - j.camp, j.x, j.y, gk=False)
            if (j.fam == "DEF" and math.hypot(j.x - mx, j.y - my) < 22.0 and prec is not None and prec.camp != j.camp
                    and gene < 4.0):
                self._degager(j)                    # dans sa surface, un attaquant dans le dos : première intention
                return
            # le point d'appui : dos au but, un marqueur dans le dos, un coéquipier
            # qui arrive lancé — on remet en une touche, le troisième homme joue
            gx, gy = self.but_de(j.camp)
            dbut_r = math.hypot(gx - j.x, gy - j.y)
            (_, _), dev_r = self._espace_devant(j)
            en_position = dbut_r < 26.0 and (self._angle_but(j.x, j.y, j.camp) > 0.3 or dev_r > 6.0)
            if (prec is not None and prec.camp == j.camp and passe_vers is j and j.fam in ("FWD", "MID")
                    and (j.x - LONG / 2) * j.sens() > 0.0 and gene < 3.0 and not en_position
                    and self.rs.random() < 0.5 + 0.4 * self.collectif[j.camp]):
                cand = [o for o in self.actifs(j.camp) if o is not j and o is not prec and not o.gk
                        and (math.hypot(o.vx, o.vy) > 2.5 or o.role in ("appel", "soutien") or o.appel_jusqua > self.t)
                        and 4.0 < math.hypot(o.x - j.x, o.y - j.y) < 15.0
                        and self._couloir_libre(j, o) > 0.5]
                if cand:
                    o = min(cand, key=lambda o: math.hypot(gx - o.x, gy - o.y))
                    self.evt("remise", de=j.pid, a=o.pid, camp=j.camp)
                    self._passer(j, o, courte=True)
                    return
            _, dev = self._espace_devant(j)
            if dev > 7.0:
                self._conduire(j)                   # l'espace devant se prend dès le contrôle

    def _tete(self, j: Joueur):
        """Un ballon en l'air se dévie de la tête : un défenseur dégage loin
        de son but, un attaquant remise ou frappe vers le but."""
        b = self.ballon
        mx, my = self.but_de(1 - j.camp)               # son propre but
        gx, gy = self.but_de(j.camp)
        dbut = math.hypot(gx - j.x, gy - j.y)
        j.touches += 1
        prec = b.dernier
        if prec is not None and prec.camp == j.camp and prec is not j and b.passe_vers is not None:
            prec.passes_ok += 1                         # la passe (ou le centre) est arrivée à un coéquipier
            self.stats["passes_ok"][j.camp] += 1
        elif prec is not None and prec.camp != j.camp and b.passe_vers is not None:
            j.interceptions += 1
            self.stats["interceptions"][j.camp] += 1
        b.passe_vers = None
        if dbut < 13 and self.rs.random() < (0.45 if j.fam == "FWD" else 0.3):
            # une tête vers le but
            self.dernier_tir = {"de": j, "xg": self._xg(dbut, self._angle_but(j.x, j.y, j.camp), 0.4) * 0.6, "t": self.t, "camp": j.camp}
            j.tirs += 1
            self.stats["tirs"][j.camp] += 1
            self.stats["xg"][j.camp] += self.dernier_tir["xg"]
            ang = math.atan2(gy - j.y, gx - j.x) + self.rs.gauss(0, 0.34)
            self._lacher(j, 14.0 * math.cos(ang), 14.0 * math.sin(ang), 1.5)
            self.evt("tir", de=j.pid, camp=j.camp, xg=round(self.dernier_tir["xg"], 3), d=round(dbut, 1), tete=True)
            return
        ang = math.atan2(j.y - my, j.x - mx) + self.rs.gauss(0, 0.9 if j.fam == "DEF" else 1.2)
        _, gene = self.plus_proche(1 - j.camp, j.x, j.y, gk=False)
        if j.fam == "DEF" and math.hypot(j.x - mx, j.y - my) < 20.0 and self.rs.random() < (0.5 if gene < 2.5 else 0.3):
            # une tête en catastrophe, un attaquant dans le dos : vers la touche, en arrière — d'où les corners
            ang = math.atan2(1.0 if j.y >= my else -1.0, -1.1 * (1 if j.camp == 0 else -1)) + self.rs.gauss(0, 0.3)
        v = 9.0 + 7.0 * j.attr("DEF") / 99
        self.evt("tete", de=j.pid, camp=j.camp)
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
        if tir and self.rs.random() < 0.65:
            # dévié : le ballon file derrière le défenseur, vers la ligne de fond
            v = b.vitesse() * 0.7
            ang = math.atan2(b.vy, b.vx) + self.rs.choice([-1, 1]) * self.rs.uniform(0.5, 1.1)
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
        if tir and self.rs.random() < 0.25 + 0.5 * max(0.0, (b.vitesse() - 20.0) / 12.0):
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
            v_p = math.hypot(p.vx, p.vy)
            # la faute de pressing : un défenseur qui arrive lancé dans les pieds du
            # porteur le bouscule parfois — la plupart des fautes d'un match
            gxp, gyp = self.but_de(p.camp)
            prudence = 0.35 if (abs(p.x - gxp) < SURFACE_X + 2.0 and abs(p.y - gyp) < SURFACE_Y + 2.0) else 1.0
            if d < 1.4 and math.hypot(o.vx, o.vy) > 4.0 and self.t - o.dernier_choc > 2.0:
                o.dernier_choc = self.t
                if self.rs.random() < (0.04 + 0.03 * (1.0 - o.recup)) * prudence:
                    self._faute(o, p)                     # dans la surface, on défend les mains dans le dos
                    return
            gx, gy = self.but_de(p.camp)
            cote_but = (o.x - p.x) * (gx - p.x) + (o.y - p.y) * (gy - p.y) > 0.0
            portee = 1.1 if v_p < 3.0 else (2.2 if cote_but else 1.6)
            if d > portee:
                continue                              # un porteur lancé sur un défenseur côté but ne le contourne pas sans duel
            if self.t - o.dernier_contact < 2.5 or self.t - p.dernier_duel < 5.0:
                continue                              # un duel, pas une grêle : cinq secondes entre deux
            if v_p < 3.0 and self.t - p.dernier_contact < 2.0:
                continue                              # à l'arrêt, on ne pique que celui qui traîne
            # lancé, le duel n'a lieu que s'il va SUR le défenseur (il se rapproche)
            if v_p >= 3.0 and (p.vx * (o.x - p.x) + p.vy * (o.y - p.y)) / (d or 1.0) < 1.0:
                continue
            p.dernier_duel = self.t
            if self.t < p.provoque_jusqua:
                # le crochet : dribble contre défense, en un coup de rein
                o.dernier_contact = self.t
                p_passe = 0.52 + 0.5 * (p.attr("DRI") - o.attr("DEF")) / 99 + (0.08 if self._rentre(p) else 0.0)
                if self.rs.random() < max(0.15, min(0.85, p_passe)):
                    o.battu_jusqua = self.t + 0.8
                    o.vx *= 0.3
                    o.vy *= 0.3
                    self.evt("crochet", de=p.pid, sur=o.pid, camp=p.camp)
                    continue
                # raté : le défenseur prend le ballon, ou fait faute
                o.tacles += 1
                self.stats["tacles"][o.camp] += 1
                if self.rs.random() < 0.2:
                    self._faute(o, p)
                    return
                self.evt("tacle", de=o.pid, sur=p.pid, camp=o.camp)
                ang = self.rs.uniform(0, 2 * math.pi)
                b.porteur = None
                b.dernier = o
                b.dernier_camp = o.camp
                b.t_kick = self.t
                b.passe_vers = None
                b.vx, b.vy = 4.0 * math.cos(ang), 4.0 * math.sin(ang)
                return
            o.dernier_contact = self.t
            # la chance de prendre le ballon : défense contre dribble, et la force ;
            # un porteur lancé droit sur le défenseur se tacle plus facilement, un
            # porteur qui protège son ballon à l'arrêt, moins
            force_o = (o.physique.get("for", 68) or 68) / 99
            force_p = (p.physique.get("for", 68) or 68) / 99
            p_gagne = (0.45 + 0.4 * (o.attr("DEF") - p.attr("DRI")) / 99 + 0.15 * (force_o - force_p) + 0.16 * (o.recup - 0.5)
                       + 0.12 * min(v_p, 8.0) / 8.0 - 0.1)
            if v_p < 3.0:
                p_gagne *= 0.4                        # à l'arrêt, il protège son ballon : le défenseur pique, il ne tacle pas
            p_gagne = max(0.08, min(0.8, p_gagne))
            # le duel se tranche en un jet : passé, le défenseur met un demi-seconde à se retourner
            r = self.rs.random()
            if r >= p_gagne:
                o.battu_jusqua = self.t + 0.5
                if self.rs.random() < 0.03 * prudence:
                    self._faute(o, p)
                    return
                continue
            if r < p_gagne:
                o.tacles += 1
                self.stats["tacles"][o.camp] += 1
                # une faute une fois sur douze, moins dans la surface
                if self.rs.random() < 0.08 * prudence:
                    self._faute(o, p)
                    return
                self.evt("tacle", de=o.pid, sur=p.pid, camp=o.camp)
                p.battu_jusqua = self.t + 0.4           # dépossédé, il se retourne
                if self.rs.random() < 0.6:
                    # le tacleur ressort avec le ballon
                    b.porteur = o
                    b.passe_vers = None
                    b.dernier = o
                    b.dernier_camp = o.camp
                    b.hors_jeu_au_kick = set()
                    o.touches += 1
                    o.dernier_contact = self.t
                    o.role = "porteur"
                    o.cible = (o.x, o.y)
                    o.recu_de = -1
                    # dans sa surface, sous pression, on ne fait pas le beau : on dégage
                    mx, my = self.but_de(1 - o.camp)
                    if math.hypot(o.x - mx, o.y - my) < 28.0 and self._pression(o) > 0.25:
                        self._degager(o)
                    return
                # sinon le ballon part libre, un peu devant le tacleur
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
                            "fatigue": round(j.fatigue, 2), "exclu": j.pid in self.exclus, "capitaine": j.capitaine,
                            "travail": [round(j.volume, 2), round(j.pressing, 2), round(j.recup, 2)]})
        return {"score": list(self.score), "noms": list(self.noms), "minutes": round(self.duree / 60),
                "collectif": list(self.collectif), "tactiques": [dict(t) for t in self.tac],
                "possession": [round(self.possession[0] / tot, 3), round(self.possession[1] / tot, 3)],
                "stats": {k: (v if not isinstance(v[0], float) else [round(v[0], 2), round(v[1], 2)]) for k, v in self.stats.items()},
                "joueurs": joueurs, "evenements": self.evenements, "trace": self.trace,
                "trace_pas": DT * TRACE_PAS, "phases": PHASES}


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

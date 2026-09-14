"""scoring.py — what a manager's team scores on a gameweek.

Pure functions, no database.  Inputs are plain dicts so the same code runs
in the backtest (docs/ROADMAP.md, phase 1) and in the live game.

Rules (all constants below are game-design knobs, see docs/GAME_DESIGN.md):
  - a gameweek groups every match played in a date window (league round +
    the midweek European fixtures that follow it);
  - a player's points for the gameweek = sum of their notes over the
    matches of the window; a player who did not play scores 0.  No extra
    competition bonus: the engine already weights the competition, the
    round and the opponent inside the raw score (docs/REPONSES.md §3);
  - the team score = sum over the 11 starters, with a captain bonus, and an
    automatic substitution from the bench for any starter who did not play
    (bench order matters, formation must stay legal).
"""
from __future__ import annotations

from dataclasses import dataclass, field

BONUS_CAPITAINE = 1.5
TAILLE_ONZE = 11
TAILLE_BANC = 7          # a real matchday squad: eleven and seven

# A formation is ELEVEN REAL POSITIONS laid out in rows, keeper first, back
# to front, left to right inside a row.  A wide slot carries its side:
# the manager reads "latéral gauche" and "ailier droit" on the pitch, not
# two anonymous "latéral" boxes.  The flattened order is the slot index,
# so a lineup stored before this still reads correctly.
#
# The midfield of a 4-3-3 is a pivot and two eights, drawn as a triangle
# (PROFONDEUR_POSTE): the flat row "defensif, relayeur, offensif" put the
# holding player on the left touchline and nobody could tell who did what.
FORMATIONS_RANGS = {
    "4-3-3": [("Gardien",),
              ("Lateral gauche", "Defenseur central", "Defenseur central", "Lateral droit"),
              ("Milieu relayeur", "Milieu defensif", "Milieu relayeur"),
              ("Ailier gauche", "Buteur", "Ailier droit")],
    "4-4-2": [("Gardien",),
              ("Lateral gauche", "Defenseur central", "Defenseur central", "Lateral droit"),
              ("Ailier gauche", "Milieu relayeur", "Milieu defensif", "Ailier droit"),
              ("Buteur", "Buteur")],
    "4-2-3-1": [("Gardien",),
                ("Lateral gauche", "Defenseur central", "Defenseur central", "Lateral droit"),
                ("Milieu defensif", "Milieu defensif"),
                ("Ailier gauche", "Milieu offensif", "Ailier droit"),
                ("Buteur",)],
    "4-1-4-1": [("Gardien",),
                ("Lateral gauche", "Defenseur central", "Defenseur central", "Lateral droit"),
                ("Milieu defensif",),
                ("Ailier gauche", "Milieu relayeur", "Milieu relayeur", "Ailier droit"),
                ("Buteur",)],
    "4-5-1": [("Gardien",),
              ("Lateral gauche", "Defenseur central", "Defenseur central", "Lateral droit"),
              ("Ailier gauche", "Milieu relayeur", "Milieu defensif", "Milieu offensif", "Ailier droit"),
              ("Buteur",)],
    "3-5-2": [("Gardien",),
              ("Defenseur central", "Defenseur central", "Defenseur central"),
              ("Lateral gauche", "Milieu relayeur", "Milieu defensif", "Milieu relayeur", "Lateral droit"),
              ("Buteur", "Buteur")],
    "3-4-3": [("Gardien",),
              ("Defenseur central", "Defenseur central", "Defenseur central"),
              ("Lateral gauche", "Milieu relayeur", "Milieu defensif", "Lateral droit"),
              ("Ailier gauche", "Buteur", "Ailier droit")],
    "3-4-2-1": [("Gardien",),
                ("Defenseur central", "Defenseur central", "Defenseur central"),
                ("Lateral gauche", "Milieu defensif", "Milieu relayeur", "Lateral droit"),
                ("Milieu offensif", "Milieu offensif"),
                ("Buteur",)],
    "5-3-2": [("Gardien",),
              ("Lateral gauche", "Defenseur central", "Defenseur central", "Defenseur central", "Lateral droit"),
              ("Milieu relayeur", "Milieu defensif", "Milieu relayeur"),
              ("Buteur", "Buteur")],
    "5-4-1": [("Gardien",),
              ("Lateral gauche", "Defenseur central", "Defenseur central", "Defenseur central", "Lateral droit"),
              ("Ailier gauche", "Milieu relayeur", "Milieu defensif", "Ailier droit"),
              ("Buteur",)],
}
# How far in front of its row a position stands, in fractions of the
# pitch: the pivot sits behind the eights, the ten in front of them.
# Drawing only — the match reads positions, not depths.
PROFONDEUR_POSTE = {"Milieu defensif": -0.045, "Milieu offensif": 0.045}

FAMILLE_POSTE = {
    "Gardien": "GK",
    "Defenseur central": "DEF",
    "Lateral": "DEF", "Lateral gauche": "DEF", "Lateral droit": "DEF",
    "Milieu defensif": "MID",
    "Milieu relayeur": "MID",
    "Milieu offensif": "MID",
    "Ailier": "FWD", "Ailier droit": "FWD", "Ailier gauche": "FWD",
    "Buteur": "FWD",
}
# Kept for the display of a squad by line; the pitch itself no longer
# enforces it (see malus_poste).
LIMITES_FAMILLE = {"GK": (1, 1), "DEF": (3, 5), "MID": (2, 5), "FWD": (1, 4)}


LIBELLE_POSTE = {
    "Gardien": "gardien", "Defenseur central": "défenseur central",
    "Lateral": "latéral", "Lateral gauche": "latéral gauche", "Lateral droit": "latéral droit",
    "Milieu defensif": "milieu défensif", "Milieu relayeur": "milieu relayeur",
    "Milieu offensif": "meneur", "Ailier": "ailier", "Ailier gauche": "ailier gauche",
    "Ailier droit": "ailier droit", "Buteur": "buteur",
}


def libelle_poste(poste: str | None) -> str:
    return LIBELLE_POSTE.get(poste or "", (poste or "").lower())


def poste_base(poste: str) -> str:
    """A position without its side: "Lateral gauche" -> "Lateral"."""
    for suffixe in (" gauche", " droit"):
        if poste.endswith(suffixe):
            return poste[:-len(suffixe)]
    return poste


def cote_poste(poste: str) -> str | None:
    return "gauche" if poste.endswith(" gauche") else "droit" if poste.endswith(" droit") else None


def postes_formation(formation: str) -> list[str]:
    """The eleven positions of a formation, in slot order (keeper first,
    then back to front, left to right inside a row)."""
    return [p for rang in FORMATIONS_RANGS[formation] for p in rang]


def familles_formation(formation: str) -> list[str]:
    return [FAMILLE_POSTE[p] for p in postes_formation(formation)]


def _comptes(formation: str) -> tuple[int, int, int, int]:
    fams = familles_formation(formation)
    return tuple(fams.count(f) for f in ("GK", "DEF", "MID", "FWD"))


# The family counts, derived — what the simulation reads.
FORMATIONS = {nom: _comptes(nom) for nom in FORMATIONS_RANGS}

# A card is not one position.  Valverde played sixteen matches at right
# back, fifteen on the right wing and twelve in midfield: calling him a
# winger and refusing him a midfield slot is wrong twice over.  A card is
# eligible wherever the player really played, from this share of his
# minutes up; `joueur.poste` stays the main one, for display and for the
# barème's shrink.
PART_POSTE_ELIGIBLE = 0.20

# Anyone can play anywhere — and it costs by DISTANCE.  The pitch is a
# graph of positions; a card pays, on every attribute, the malus of the
# distance between the slot and the closest position it really held.  A
# centre-back at full-back is one step away and loses a little; the same
# man at centre-forward is three steps away and loses a lot.  A keeper in
# the field, or a field player in goal, is another sport.
VOISINS = {
    "Defenseur central": ("Lateral", "Milieu defensif"),
    "Lateral": ("Defenseur central", "Ailier", "Milieu relayeur"),
    "Milieu defensif": ("Defenseur central", "Milieu relayeur"),
    "Milieu relayeur": ("Milieu defensif", "Milieu offensif", "Lateral"),
    "Milieu offensif": ("Milieu relayeur", "Ailier", "Buteur"),
    "Ailier": ("Lateral", "Milieu offensif", "Buteur"),
    "Buteur": ("Milieu offensif", "Ailier"),
}
MALUS_DISTANCE = (0, 4, 8, 14, 20)    # by graph distance, the last for anything farther
MALUS_GARDIEN = 30                    # keeper <-> field, either way
MALUS_COTE = 2                        # the right side, the wrong foot: a winger switched over


def _distances() -> dict[tuple[str, str], int]:
    """Graph distance between every pair of base positions (BFS)."""
    out = {}
    for depart in VOISINS:
        vus = {depart: 0}
        file = [depart]
        while file:
            p = file.pop(0)
            for v in VOISINS[p]:
                if v not in vus:
                    vus[v] = vus[p] + 1
                    file.append(v)
        for arrivee, d in vus.items():
            out[(depart, arrivee)] = d
    return out


DISTANCES = _distances()


def malus_poste(postes_carte, poste_slot: str) -> int:
    """What a card loses on every attribute in that slot: zero at a
    position it held, more the farther the slot is from any of them."""
    if not poste_slot:
        return 0
    tenus = [p for p in (postes_carte or ()) if p]
    if not tenus:
        return MALUS_DISTANCE[2]
    slot_base, slot_cote = poste_base(poste_slot), cote_poste(poste_slot)
    meilleur = None
    for tenu in tenus:
        base, cote = poste_base(tenu), cote_poste(tenu)
        if (base == "Gardien") != (slot_base == "Gardien"):
            m = MALUS_GARDIEN
        elif base == "Gardien":
            m = 0
        else:
            d = DISTANCES.get((base, slot_base), len(MALUS_DISTANCE))
            m = MALUS_DISTANCE[min(d, len(MALUS_DISTANCE) - 1)]
            if slot_cote and cote and slot_cote != cote:
                m += MALUS_COTE
        meilleur = m if meilleur is None else min(meilleur, m)
    return meilleur


def a_le_poste(postes_carte, poste_slot: str) -> bool:
    """Whether the card really held THAT position (side included when the
    card's own position names one)."""
    return malus_poste(postes_carte, poste_slot) == 0


def hors_poste(postes_carte, poste_slot: str) -> bool:
    """Fielded away from every position he held: allowed, and it costs
    `malus_poste` on every attribute."""
    return malus_poste(postes_carte, poste_slot) > 0


def matrice_malus() -> dict[str, dict[str, int]]:
    """{slot: {position held: malus}} for every slot of every formation
    and every position a card can carry — what the screen reads to colour
    a box and to show the OVR a card is worth where it stands."""
    slots = sorted({p for rangs in FORMATIONS_RANGS.values() for rang in rangs for p in rang})
    tenus = sorted(FAMILLE_POSTE)
    return {s: {t: malus_poste([t], s) for t in tenus} for s in slots}


def _affectation(cout: list[list[float]]) -> list[int]:
    """The column of each row that minimises the total cost (Hungarian
    algorithm, rows <= columns).  Small: eleven rows, a squad of columns."""
    n, m = len(cout), len(cout[0]) if cout else 0
    if n == 0 or m < n:
        raise ValueError("plus de cases que de joueurs")
    INF = float("inf")
    u = [0.0] * (n + 1)
    v = [0.0] * (m + 1)
    p = [0] * (m + 1)          # p[j] = row assigned to column j (1-based), 0 if none
    way = [0] * (m + 1)
    for i in range(1, n + 1):
        p[0] = i
        j0 = 0
        minv = [INF] * (m + 1)
        used = [False] * (m + 1)
        while True:
            used[j0] = True
            i0 = p[j0]
            delta, j1 = INF, 0
            for j in range(1, m + 1):
                if used[j]:
                    continue
                cur = cout[i0 - 1][j - 1] - u[i0] - v[j]
                if cur < minv[j]:
                    minv[j], way[j] = cur, j0
                if minv[j] < delta:
                    delta, j1 = minv[j], j
            for j in range(m + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while j0:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
    out = [0] * n
    for j in range(1, m + 1):
        if p[j]:
            out[p[j] - 1] = j - 1
    return out


def repartir(postes_par_joueur: list, formation: str, valeurs: list[float] | None = None) -> list[int]:
    """Which player fills which slot of `formation`, best fit overall.

    `postes_par_joueur[k]` is the list of positions player k really held,
    best player first; `valeurs` (optional) what each is worth, an OVR.
    Returns one player index per slot, in slot order: the assignment
    that MAXIMISES the eleven's worth at its posts — the sum of value
    less out-of-position cost — so that a missing full-back is covered
    by the one man whose move costs the least, and never by a chain of
    three men each one step out.  Slot by slot, scarcest first, it did
    exactly that chain.  Without values, it is the cheapest assignment,
    ties to the better-ranked player.
    """
    postes = postes_formation(formation)
    n, m = len(postes), len(postes_par_joueur)
    if m < n:
        # fewer players than slots: fill what can be filled, in order
        return list(range(m))
    cout = [[malus_poste(postes_par_joueur[k], postes[i]) - (valeurs[k] if valeurs else 0.0) + k * 1e-6
             for k in range(m)] for i in range(n)]
    return _affectation(cout)


def familles_eligibles(postes) -> list[str]:
    """The family codes a card may be fielded in, main one first.
    `postes` is the ordered list stored on `joueur.postes`."""
    out = []
    for p in postes or []:
        f = FAMILLE_POSTE.get(p)
        if f and f not in out:
            out.append(f)
    return out


@dataclass
class Prestation:
    """One player's rated appearance in one match of the gameweek."""
    player_id: int
    match_id: int
    competition: str
    note: float
    minutes: float


@dataclass
class Composition:
    """A manager's lineup for a gameweek."""
    titulaires: list[int]                 # 11 player ids
    banc: list[int] = field(default_factory=list)   # ordered, first comes on first
    capitaine: int | None = None
    formation: str = "4-3-3"


def points_joueur(prestas: list[Prestation]) -> float:
    """Gameweek points of one player from all their rated appearances."""
    return round(sum(p.note for p in prestas), 2)


def a_joue(prestas: list[Prestation]) -> bool:
    return any(p.minutes > 0 for p in prestas)


def formation_legale(familles: list[str]) -> bool:
    """A set of 11 family codes is legal if every family is within bounds."""
    if len(familles) != TAILLE_ONZE:
        return False
    for fam, (lo, hi) in LIMITES_FAMILLE.items():
        n = familles.count(fam)
        if not lo <= n <= hi:
            return False
    return True


def onze_legal(eligibles: list[list[str]], formation: str | None = None) -> bool:
    """Can these eleven cards fill a legal formation at all?

    Each card carries the list of families it may play.  The question is
    whether one family can be picked per card so the counts land inside
    LIMITES_FAMILLE (and match `formation` when given).  Eleven cards and
    four families: solved by trying every legal count vector and matching
    greedily from the most constrained card.
    """
    if len(eligibles) != TAILLE_ONZE or any(not e for e in eligibles):
        return False
    cibles = [FORMATIONS[formation]] if formation in FORMATIONS else None
    if cibles is None:
        cibles = [(g, d, m, f) for g in range(*_borne("GK")) for d in range(*_borne("DEF"))
                  for m in range(*_borne("MID")) for f in range(*_borne("FWD")) if g + d + m + f == TAILLE_ONZE]
    for cible in cibles:
        besoin = dict(zip(("GK", "DEF", "MID", "FWD"), cible))
        if _affecte(sorted(eligibles, key=len), besoin):
            return True
    return False


def _borne(fam: str) -> tuple[int, int]:
    lo, hi = LIMITES_FAMILLE[fam]
    return lo, hi + 1


def _affecte(restants: list[list[str]], besoin: dict[str, int]) -> bool:
    if not restants:
        return all(n == 0 for n in besoin.values())
    tete, suite = restants[0], restants[1:]
    for fam in tete:
        if besoin.get(fam, 0) > 0:
            besoin[fam] -= 1
            if _affecte(suite, besoin):
                besoin[fam] += 1
                return True
            besoin[fam] += 1
    return False


def remplacements(compo: Composition, prestas: dict[int, list[Prestation]],
                  poste: dict[int, str]) -> list[int]:
    """The 11 ids that actually score, after automatic substitutions.

    Each starter who did not play is replaced by the first bench player who
    played and keeps the formation legal.  Goalkeepers only swap with
    goalkeepers.
    """
    onze = list(compo.titulaires)
    banc = [b for b in compo.banc if a_joue(prestas.get(b, []))]
    for i, pid in enumerate(onze):
        if a_joue(prestas.get(pid, [])):
            continue
        for cand in list(banc):
            essai = onze[:]
            essai[i] = cand
            fams = [FAMILLE_POSTE[poste[x]] for x in essai]
            if formation_legale(fams):
                onze = essai
                banc.remove(cand)
                break
    return onze


def score_equipe(compo: Composition, prestas: dict[int, list[Prestation]],
                 poste: dict[int, str]) -> dict:
    """Team score for a gameweek and the per-player breakdown.

    `prestas` maps player_id -> their appearances in the window; a player
    absent from the dict did not play.  `poste` maps player_id -> engine
    position (needed for legal substitutions).
    """
    if len(compo.titulaires) != TAILLE_ONZE:
        raise ValueError(f"{len(compo.titulaires)} titulaires, il en faut {TAILLE_ONZE}")
    fams = [FAMILLE_POSTE[poste[x]] for x in compo.titulaires]
    if not formation_legale(fams):
        raise ValueError(f"composition illegale : {fams}")

    onze = remplacements(compo, prestas, poste)
    detail = {}
    total = 0.0
    for pid in onze:
        pts = points_joueur(prestas.get(pid, []))
        if pid == compo.capitaine:
            pts = round(pts * BONUS_CAPITAINE, 2)
        detail[pid] = pts
        total += pts
    return {
        "score": round(total, 2),
        "onze": onze,
        "entres": [p for p in onze if p not in compo.titulaires],
        "detail": detail,
    }

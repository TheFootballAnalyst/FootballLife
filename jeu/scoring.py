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
# to front.  It used to be four counts (one keeper, four defenders, three
# midfielders, three forwards) and a slot only knew its family — which is
# why Van Dijk came out at left back and Robertson in the middle, and why
# "best eleven" put three centre-backs and one full-back in a back four.
# A row is what the pitch draws; the flattened order is the slot index, so
# a lineup stored before this still reads correctly.
FORMATIONS_RANGS = {
    "4-3-3": [("Gardien",),
              ("Lateral", "Defenseur central", "Defenseur central", "Lateral"),
              ("Milieu defensif", "Milieu relayeur", "Milieu offensif"),
              ("Ailier", "Buteur", "Ailier")],
    "4-4-2": [("Gardien",),
              ("Lateral", "Defenseur central", "Defenseur central", "Lateral"),
              ("Ailier", "Milieu relayeur", "Milieu defensif", "Ailier"),
              ("Buteur", "Buteur")],
    "4-2-3-1": [("Gardien",),
                ("Lateral", "Defenseur central", "Defenseur central", "Lateral"),
                ("Milieu defensif", "Milieu defensif"),
                ("Ailier", "Milieu offensif", "Ailier"),
                ("Buteur",)],
    "4-1-4-1": [("Gardien",),
                ("Lateral", "Defenseur central", "Defenseur central", "Lateral"),
                ("Milieu defensif",),
                ("Ailier", "Milieu relayeur", "Milieu relayeur", "Ailier"),
                ("Buteur",)],
    "4-5-1": [("Gardien",),
              ("Lateral", "Defenseur central", "Defenseur central", "Lateral"),
              ("Ailier", "Milieu offensif", "Milieu relayeur", "Milieu defensif", "Ailier"),
              ("Buteur",)],
    "3-5-2": [("Gardien",),
              ("Defenseur central", "Defenseur central", "Defenseur central"),
              ("Lateral", "Milieu defensif", "Milieu relayeur", "Milieu offensif", "Lateral"),
              ("Buteur", "Buteur")],
    "3-4-3": [("Gardien",),
              ("Defenseur central", "Defenseur central", "Defenseur central"),
              ("Lateral", "Milieu relayeur", "Milieu defensif", "Lateral"),
              ("Ailier", "Buteur", "Ailier")],
    "3-4-2-1": [("Gardien",),
                ("Defenseur central", "Defenseur central", "Defenseur central"),
                ("Lateral", "Milieu defensif", "Milieu relayeur", "Lateral"),
                ("Milieu offensif", "Milieu offensif"),
                ("Buteur",)],
    "5-3-2": [("Gardien",),
              ("Lateral", "Defenseur central", "Defenseur central", "Defenseur central", "Lateral"),
              ("Milieu defensif", "Milieu relayeur", "Milieu offensif"),
              ("Buteur", "Buteur")],
    "5-4-1": [("Gardien",),
              ("Lateral", "Defenseur central", "Defenseur central", "Defenseur central", "Lateral"),
              ("Ailier", "Milieu relayeur", "Milieu defensif", "Ailier"),
              ("Buteur",)],
}
FAMILLE_POSTE = {
    "Gardien": "GK",
    "Defenseur central": "DEF",
    "Lateral": "DEF",
    "Milieu defensif": "MID",
    "Milieu relayeur": "MID",
    "Milieu offensif": "MID",
    "Ailier": "FWD",
    "Ailier droit": "FWD",
    "Ailier gauche": "FWD",
    "Buteur": "FWD",
}
LIMITES_FAMILLE = {"GK": (1, 1), "DEF": (3, 5), "MID": (2, 5), "FWD": (1, 4)}


def postes_formation(formation: str) -> list[str]:
    """The eleven positions of a formation, in slot order (keeper first,
    then back to front, left to right inside a row)."""
    return [p for rang in FORMATIONS_RANGS[formation] for p in rang]


def familles_formation(formation: str) -> list[str]:
    return [FAMILLE_POSTE[p] for p in postes_formation(formation)]


def _comptes(formation: str) -> tuple[int, int, int, int]:
    fams = familles_formation(formation)
    return tuple(fams.count(f) for f in ("GK", "DEF", "MID", "FWD"))


# The family counts, derived — what the legality check and the simulation
# read.  Kept under the old name so nothing else has to change.
FORMATIONS = {nom: _comptes(nom) for nom in FORMATIONS_RANGS}

# A card is not one position.  Valverde played sixteen matches at right
# back, fifteen on the right wing and twelve in midfield: calling him a
# winger and refusing him a midfield slot is wrong twice over.  A card is
# eligible wherever the player really played, from this share of his
# minutes up; `joueur.poste` stays the main one, for display and for the
# barème's shrink.
PART_POSTE_ELIGIBLE = 0.20


def a_le_poste(postes_carte, poste_slot: str) -> bool:
    """Whether the card really held THAT position — not merely a position
    of the same family.  A centre-back and a full-back are both defenders
    and are not interchangeable."""
    return poste_slot in (postes_carte or ())


def hors_poste(postes_carte, poste_slot: str) -> bool:
    """Fielded in his line but not at his position: allowed, and it costs
    something (simulation.MALUS_HORS_POSTE)."""
    return not a_le_poste(postes_carte, poste_slot)


def repartir(postes_par_joueur: list, formation: str) -> list[int]:
    """Which player fills which slot of `formation`, best fit first.

    `postes_par_joueur[i]` is the list of positions player i really held.
    Returns one player index per slot, in slot order.  The scarcest slot
    is served first — a squad with one keeper and ten midfielders must not
    lose the keeper to a midfield slot — then each slot takes a player who
    held that very position, failing that one of the line, failing that
    whoever is left.  It is what the manager's "best eleven" button does,
    and what a formation changed at half-time has to do as well.
    """
    postes = postes_formation(formation)
    fams = familles_formation(formation)
    place: list[int | None] = [None] * len(postes)
    pris: set[int] = set()
    rareté = lambda i: len([t for t in postes_par_joueur if a_le_poste(t, postes[i])])
    ordre = sorted(range(len(postes)), key=rareté)
    for tour in ("poste", "famille", "reste"):
        for i in ordre:
            if place[i] is not None:
                continue
            for k, tenus in enumerate(postes_par_joueur):
                if k in pris:
                    continue
                if (tour == "poste" and a_le_poste(tenus, postes[i])) \
                        or (tour == "famille" and fams[i] in (familles_eligibles(tenus) or [])) \
                        or tour == "reste":
                    place[i] = k
                    pris.add(k)
                    break
    return [k for k in place if k is not None]


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

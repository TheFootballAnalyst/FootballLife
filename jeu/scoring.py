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
TAILLE_BANC = 4

# Formation = counts of (GK, DEF, MID, FWD).  Position families map onto
# the engine's positions; a card carries one family.
FORMATIONS = {
    "4-3-3": (1, 4, 3, 3),
    "4-4-2": (1, 4, 4, 2),
    "4-2-3-1": (1, 4, 5, 1),
    "3-5-2": (1, 3, 5, 2),
    "3-4-3": (1, 3, 4, 3),
    "5-3-2": (1, 5, 3, 2),
    "4-5-1": (1, 4, 5, 1),
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
LIMITES_FAMILLE = {"GK": (1, 1), "DEF": (3, 5), "MID": (2, 5), "FWD": (1, 3)}


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

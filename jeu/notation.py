"""notation.py — bridge between the rating engine and the game.

The engine (`moteur/topsflops.py`) produces, for every (match, player), a raw
score (`brut`) that already includes the competition and round coefficient,
and a set of scoring lines by label.  The game needs two derived things:

1. a **note out of 10**, comparable across positions and competitions, that
   is what a card "scores" on a matchday;
2. six **attributes on 40-99** (finishing, creation, progression, defence,
   dribbling, retention; goalkeepers have their own six) shown on the card.

Both are pure functions of the engine output plus three calibration files
shipped with the engine (`seuils_flops_postes_2526.json`,
`echelles_attributs.json`, `familles_lignes.json`).  Nothing here touches
the points table or the percentiles: they are calibrated on 42 000
performances and are read-only.

Spec, as reverse-checked against the visual pipeline's reference output
(40/40 exact on jeu/tests/donnees/valeurs_attendues.json):
  - input is the engine's `points` (raw score x position coefficient),
    compared to the position's thresholds as shipped;
  - anchors: p10 -> 4, p25 -> 5, median -> 6, p75 -> 7, p90 -> 8, linear
    in between;
  - beyond p90 the curve saturates:  note = 8 + 2u / (1 + u)  with
    u = (points - p90) / (p90 - median), so 10 is an asymptote;
  - below p10: note = max(1, 4 - 3 * min(ecart, 1)) with
    ecart = (p10 - points) / |median - p10|  (checked on 61 flops);
  - minutes damping: the note departs from 6 in proportion to the square
    root of minutes played, full at 60 minutes.
Attributes take the engine's `lignes` as they are (no coefficient removed):
240/240 exact on the same reference file.
"""
from __future__ import annotations

import bisect
import json
import math
import pathlib
from dataclasses import dataclass

MOTEUR = pathlib.Path(__file__).resolve().parent.parent / "moteur"
SEUILS_PATH = MOTEUR / "seuils_flops_postes_2526.json"
ECHELLES_PATH = MOTEUR / "echelles_attributs.json"
FAMILLES_PATH = MOTEUR / "familles_lignes.json"

NOTE_MIN, NOTE_MAX = 1.0, 10.0
NOTE_PIVOT = 6.0             # median performance
MINUTES_PLEINES = 60.0       # damping is 1.0 from here on

# Engine positions -> position family used by the percentile thresholds.
POSTE_SEUIL = {
    "Gardien": "Gardien",
    "Defenseur central": "Defenseur central",
    "Lateral": "Lateral",
    "Milieu defensif": "Milieu defensif",
    "Milieu relayeur": "Milieu relayeur",
    "Milieu offensif": "Milieu offensif",
    "Ailier": "Ailier",
    "Ailier droit": "Ailier",
    "Ailier gauche": "Ailier",
    "Buteur": "Buteur",
}

# Card attribute families.  Outfield players and goalkeepers each have six.
AXES_CHAMP = ("FIN", "CRE", "PRO", "DEF", "DRI", "CON")
AXES_GARDIEN = ("ARR", "EVI", "SOR", "REL", "BUT", "PRO")
ATTRIBUT_MIN, ATTRIBUT_MAX = 40, 99

# --------------------------------------------------------------------------
# Line label -> card families.  Loaded from moteur/familles_lignes.json, the
# exact table that produced echelles_attributs.json (docs/REPONSES.md §1):
# eleven families, 39 labels (duels left DRI, ground duels left DEF), strict string equality on the engine's
# accent-free labels.  A label may belong to two families ("Passe reussie"
# and "Long ballon reussi" count in PRO and in REL) — that is deliberate.
#
# Labels the engine can write but that are in no family (red card, own
# goal, penalties conceded/won/missed/saved, last-man tackle, goal-line
# clearance, diving save, clean sheet, errors leading to a goal) count in
# the note, not in any attribute.  Do not add them here: the percentiles
# were measured without them.
# --------------------------------------------------------------------------
_FAMILLES: dict[str, list[str]] | None = None


def charger_familles(chemin: pathlib.Path = FAMILLES_PATH) -> dict[str, list[str]]:
    """{famille: [libelles]} as shipped with the engine."""
    global _FAMILLES
    if _FAMILLES is None:
        _FAMILLES = json.loads(chemin.read_text(encoding="utf-8"))
    return _FAMILLES


def familles_du_libelle(familles: dict[str, list[str]] | None = None) -> dict[str, list[str]]:
    """Inverse table: {libelle: [familles]} — a label can map to several."""
    familles = familles or charger_familles()
    inv: dict[str, list[str]] = {}
    for fam, libs in familles.items():
        for lib in libs:
            inv.setdefault(lib, []).append(fam)
    return inv


@dataclass(frozen=True)
class Seuils:
    """Percentile thresholds of the neutral raw score for one position."""
    p10: float
    p25: float
    mediane: float
    p75: float
    p90: float

    def ancres(self) -> list[tuple[float, float]]:
        return [(self.p10, 4.0), (self.p25, 5.0), (self.mediane, 6.0),
                (self.p75, 7.0), (self.p90, 8.0)]


_SEUILS: dict[str, Seuils] | None = None
_ECHELLES: dict | None = None


def charger_seuils(chemin: pathlib.Path = SEUILS_PATH) -> dict[str, Seuils]:
    global _SEUILS
    if _SEUILS is None or chemin != SEUILS_PATH:
        doc = json.loads(chemin.read_text(encoding="utf-8"))
        table = {p: Seuils(s["p10"], s["p25"], s["mediane"], s["p75"], s["p90"])
                 for p, s in doc["postes"].items()}
        if chemin != SEUILS_PATH:
            return table
        _SEUILS = table
    return _SEUILS


def charger_echelles(chemin: pathlib.Path = ECHELLES_PATH) -> dict:
    global _ECHELLES
    if _ECHELLES is None:
        _ECHELLES = json.loads(chemin.read_text(encoding="utf-8"))
    return _ECHELLES


# --------------------------------------------------------------------------
# Note out of 10
# --------------------------------------------------------------------------

def note_brute(valeur: float, seuils: Seuils) -> float:
    """Map the engine's `points` to a note, no damping.

    Linear between the five anchors; saturating beyond p90 so that the note
    approaches 10 without reaching it (a monstrous night reads 9.5, not 12);
    below p10 a straight line down to the floor of 1.
    """
    if valeur >= seuils.p90:
        u = (valeur - seuils.p90) / (seuils.p90 - seuils.mediane)
        return 8.0 + 2.0 * u / (1.0 + u)
    if valeur <= seuils.p10:
        # Below p10: linear down to 1.0, reached one (median - p10) span
        # under p10, then flat (visual pipeline rule, checked on 61 flops).
        ecart = (seuils.p10 - valeur) / abs(seuils.mediane - seuils.p10)
        return max(NOTE_MIN, 4.0 - 3.0 * min(ecart, 1.0))
    ancres = seuils.ancres()
    xs = [x for x, _ in ancres]
    i = bisect.bisect_right(xs, valeur) - 1
    (x0, y0), (x1, y1) = ancres[i], ancres[i + 1]
    pente = (y1 - y0) / (x1 - x0) if x1 != x0 else 0.0
    return y0 + (valeur - x0) * pente


def amortissement(minutes: float) -> float:
    """0..1 — how far a note may depart from the pivot given time on pitch."""
    if minutes <= 0:
        return 0.0
    return min(1.0, math.sqrt(minutes / MINUTES_PLEINES))


def note_sur_10(points: float, poste: str, minutes: float,
                seuils: dict[str, Seuils] | None = None) -> float | None:
    """Note out of 10 for one performance, or None if the position is unknown.

    `points` is the engine's field of the same name (raw score x competition
    x position coefficient).  Rounded to one decimal, the precision shown on
    the card.
    """
    seuils = seuils or charger_seuils()
    s = seuils.get(POSTE_SEUIL.get(poste, poste))
    if s is None:
        return None
    n = note_brute(points, s)
    n = NOTE_PIVOT + (n - NOTE_PIVOT) * amortissement(minutes)
    return round(n, 1)


def note_prestation(p: dict, seuils: dict[str, Seuils] | None = None) -> float | None:
    """Convenience: note from one entry of topsflops.json `prestations`."""
    return note_sur_10(float(p["points"]), p["poste"],
                       float(p.get("minutes") or 0.0), seuils)


# --------------------------------------------------------------------------
# Attributes 40-99
# --------------------------------------------------------------------------

def sommes_par_famille(lignes: dict[str, float],
                       familles: dict[str, list[str]] | None = None) -> dict[str, float]:
    """Sum the engine's scoring lines per card family, as they are.

    The scales in echelles_attributs.json were measured on the lines exactly
    as topsflops writes them (competition and position coefficients
    included), so nothing is divided out.  Every family of the table is
    summed, outfield and goalkeeper alike; the caller picks the six axes it
    displays.  A label in two families is added to both.
    """
    inv = familles_du_libelle(familles)
    out: dict[str, float] = {}
    for lib, v in lignes.items():
        for fam in inv.get(lib, ()):
            out[fam] = out.get(fam, 0.0) + v
    return out


SEUIL_PLANCHER = 0.05        # a family is "mostly zero" past this share of 0s
EPSILON_ZERO = 0.001


def rang_percentile(valeur: float, echelle: list[float]) -> float:
    """Percentile rank 0..1 of a family sum on its 201-point scale, WITH the
    floor for families that are mostly zeros (docs/REPONSES.md §2).

    On a family where most performances are exactly 0 — finishing for a
    full-back — the plain rank of any positive value jumps straight past the
    zero plateau: one shot on target reads as 92.  The floor re-maps the
    scale so that the plateau ends at 0.50 and the positive values share
    the upper half; the zeros sit in 0.20-0.50 and the negatives below.
    One shot on target then reads as 70.
    """
    n = max(len(echelle) - 1, 1)
    rang = bisect.bisect_left(echelle, valeur) / n
    bas = bisect.bisect_left(echelle, -EPSILON_ZERO) / n        # where the exact zeros start
    haut = bisect.bisect_right(echelle, EPSILON_ZERO) / n       # where they end
    zeros = haut - bas
    # Only EXACT zeros form the plateau.  Negative sums (fouls, dribbled
    # past, a missed big chance) are real information and stay below it:
    # counting them as zeros made the floor fire on Défense (no zero at all,
    # 22 % of negative sums) and pushed any striker with three duel points
    # above 70.
    if zeros > SEUIL_PLANCHER and rang > haut:
        rang = 0.50 + 0.50 * (rang - haut) / max(1 - haut, 0.01)
    elif zeros > SEUIL_PLANCHER and rang >= bas:
        rang = 0.20 + 0.30 * (rang - bas) / max(zeros, 0.01)
    elif zeros > SEUIL_PLANCHER:
        rang = 0.20 * rang / max(bas, 0.01)
    return max(0.0, min(1.0, rang))


def attribut(valeur: float, echelle: list[float]) -> int:
    """Map a family sum to 40-99 via its percentile scale (floor included)."""
    return int(round(ATTRIBUT_MIN + (ATTRIBUT_MAX - ATTRIBUT_MIN)
                     * rang_percentile(valeur, echelle)))


def attributs(lignes: dict[str, float], poste: str,
              echelles: dict | None = None) -> dict[str, int]:
    """Six attributes on 40-99 for a performance (outfield or goalkeeper)."""
    echelles = echelles or charger_echelles()
    gardien = poste == "Gardien"
    # Two scales only, `champ` and `gardien`, never one per position: a
    # full-back's finishing is measured against every outfield player.
    table = echelles["gardien" if gardien else "champ"]
    axes = AXES_GARDIEN if gardien else AXES_CHAMP
    sommes = sommes_par_famille(lignes)
    return {ax: attribut(sommes.get(ax, 0.0), table[ax]) for ax in axes}


# --------------------------------------------------------------------------
# Season attributes: the card's six numbers
# --------------------------------------------------------------------------
# A season is ranked among SEASONS, not averaged from match ranks: averaging
# percentiles match by match pulled every regular towards 70.  The season
# scale (echelles_attributs.json["saison"], measured by
# importer.mesurer_echelles_saison on players with >= 450 minutes) ranks the
# family points per 90 minutes; a thin sample is shrunk towards a cautious
# prior (the PRIOR_SAISON quantile of the scale, under the median: an
# unknown player reads modest, like his OVR) with the weight of K_SAISON_90
# full matches.

K_SAISON_90 = 5.0
PRIOR_SAISON = 60          # index on the 201-point scale: the 30th percentile


def attributs_saison(sommes: dict[str, float], min90: float, poste: str,
                     echelles: dict | None = None) -> dict[str, int]:
    """Six attributes on 40-99 from the season's family points (`sommes`,
    engine points summed per family) over `min90` full-match equivalents."""
    echelles = echelles or charger_echelles()
    saison = echelles.get("saison")
    if not saison:
        raise KeyError("echelles_attributs.json has no 'saison' scales: run importer --echelles-saison")
    gardien = poste == "Gardien"
    table = saison["gardien" if gardien else "champ"]
    axes = AXES_GARDIEN if gardien else AXES_CHAMP
    out = {}
    for ax in axes:
        ech = table[ax]
        prior = ech[PRIOR_SAISON]
        v = ((sommes.get(ax, 0.0) + prior * K_SAISON_90) / (min90 + K_SAISON_90)) if min90 + K_SAISON_90 > 0 else prior
        out[ax] = attribut(v, ech)
    return out


def sommes_saison(prestations: list[tuple[float, dict]]) -> tuple[dict[str, float], float]:
    """(family points, full-match equivalents) of a list of (minutes, lignes)."""
    sommes: dict[str, float] = {}
    min90 = 0.0
    for m, lignes in prestations:
        min90 += (m or 0) / 90.0
        for f, v in sommes_par_famille(lignes or {}).items():
            sommes[f] = sommes.get(f, 0.0) + v
    return sommes, min90


def attributs_prestation(p: dict, echelles: dict | None = None) -> dict[str, int]:
    """Convenience: attributes from one entry of topsflops.json `prestations`."""
    return attributs(p.get("lignes") or {}, p["poste"], echelles)

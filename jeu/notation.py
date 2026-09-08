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

Spec (from docs/CONTEXTE.md, section 2 "La note sur 10"):
  - anchors per position on the *neutral* raw score (brut / coef):
        p10 -> 4, p25 -> 5, median -> 6, p75 -> 7, p90 -> 8
    linear interpolation between anchors, linear extrapolation beyond;
  - minutes damping: the note departs from 6 in proportion to the square
    root of minutes played, full at 60 minutes.
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
# eleven families, 41 labels, strict string equality on the engine's
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

def brut_neutre(brut: float, coef: float) -> float:
    """Raw score with the competition/round coefficient removed.

    The percentile thresholds were measured on brut / coef, so the note
    compares performances of the same quality across competitions.  The
    competition and opponent weighting still lives in the engine's points;
    the game does not add a second layer on top (docs/REPONSES.md §3).
    """
    return brut / coef if coef else brut


def note_brute(valeur: float, seuils: Seuils) -> float:
    """Piecewise-linear map of a neutral raw score to a note, no damping."""
    ancres = seuils.ancres()
    xs = [x for x, _ in ancres]
    # Beyond the anchors: extend the outer segment's slope.
    if valeur <= xs[0]:
        (x0, y0), (x1, y1) = ancres[0], ancres[1]
    elif valeur >= xs[-1]:
        (x0, y0), (x1, y1) = ancres[-2], ancres[-1]
    else:
        i = bisect.bisect_right(xs, valeur) - 1
        (x0, y0), (x1, y1) = ancres[i], ancres[i + 1]
    pente = (y1 - y0) / (x1 - x0) if x1 != x0 else 0.0
    note = y0 + (valeur - x0) * pente
    return max(NOTE_MIN, min(NOTE_MAX, note))


def amortissement(minutes: float) -> float:
    """0..1 — how far a note may depart from the pivot given time on pitch."""
    if minutes <= 0:
        return 0.0
    return min(1.0, math.sqrt(minutes / MINUTES_PLEINES))


def note_sur_10(brut: float, coef: float, poste: str, minutes: float,
                seuils: dict[str, Seuils] | None = None) -> float | None:
    """Note out of 10 for one performance, or None if the position is unknown.

    `brut` and `coef` are the engine's fields of the same name (brut already
    includes coef; it is divided out here).  Rounded to one decimal, which is
    the precision shown on the card.
    """
    seuils = seuils or charger_seuils()
    s = seuils.get(POSTE_SEUIL.get(poste, poste))
    if s is None:
        return None
    n = note_brute(brut_neutre(brut, coef), s)
    n = NOTE_PIVOT + (n - NOTE_PIVOT) * amortissement(minutes)
    return round(n, 1)


def note_prestation(p: dict, seuils: dict[str, Seuils] | None = None) -> float | None:
    """Convenience: note from one entry of topsflops.json `prestations`."""
    return note_sur_10(float(p["brut"]), float(p.get("coef") or 1.0),
                       p["poste"], float(p.get("minutes") or 0.0), seuils)


# --------------------------------------------------------------------------
# Attributes 40-99
# --------------------------------------------------------------------------

def sommes_par_famille(lignes: dict[str, float], coef: float,
                       familles: dict[str, list[str]] | None = None) -> dict[str, float]:
    """Sum the engine's scoring lines per card family, neutral of coef.

    Every family of the table is summed, outfield and goalkeeper alike; the
    caller picks the six axes it displays.  A label in two families is added
    to both.
    """
    inv = familles_du_libelle(familles)
    out: dict[str, float] = {}
    for lib, v in lignes.items():
        for fam in inv.get(lib, ()):
            out[fam] = out.get(fam, 0.0) + brut_neutre(v, coef)
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
    the upper half; zeros and negatives are squeezed into the lower 0.30.
    One shot on target then reads as 70.
    """
    n = max(len(echelle) - 1, 1)
    rang = bisect.bisect_left(echelle, valeur) / n
    seuil = bisect.bisect_right(echelle, EPSILON_ZERO) / n
    if seuil > SEUIL_PLANCHER and rang > seuil:
        rang = 0.50 + 0.50 * (rang - seuil) / max(1 - seuil, 0.01)
    elif seuil > SEUIL_PLANCHER:
        rang = 0.50 * rang / max(seuil, 0.01) * 0.6
    return max(0.0, min(1.0, rang))


def attribut(valeur: float, echelle: list[float]) -> int:
    """Map a family sum to 40-99 via its percentile scale (floor included)."""
    return int(round(ATTRIBUT_MIN + (ATTRIBUT_MAX - ATTRIBUT_MIN)
                     * rang_percentile(valeur, echelle)))


def attributs(lignes: dict[str, float], coef: float, poste: str,
              echelles: dict | None = None) -> dict[str, int]:
    """Six attributes on 40-99 for a performance (outfield or goalkeeper)."""
    echelles = echelles or charger_echelles()
    gardien = poste == "Gardien"
    # Two scales only, `champ` and `gardien`, never one per position: a
    # full-back's finishing is measured against every outfield player.
    table = echelles["gardien" if gardien else "champ"]
    axes = AXES_GARDIEN if gardien else AXES_CHAMP
    sommes = sommes_par_famille(lignes, coef)
    return {ax: attribut(sommes.get(ax, 0.0), table[ax]) for ax in axes}


def attributs_prestation(p: dict, echelles: dict | None = None) -> dict[str, int]:
    """Convenience: attributes from one entry of topsflops.json `prestations`."""
    return attributs(p.get("lignes") or {}, float(p.get("coef") or 1.0),
                     p["poste"], echelles)

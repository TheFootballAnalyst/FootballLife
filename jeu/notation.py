"""notation.py — bridge between the rating engine and the game.

The engine (`moteur/topsflops.py`) produces, for every (match, player), a raw
score (`brut`) that already includes the competition and round coefficient,
and a set of scoring lines by label.  The game needs two derived things:

1. a **note out of 10**, comparable across positions and competitions, that
   is what a card "scores" on a matchday;
2. six **attributes on 40-99** (finishing, creation, progression, defence,
   dribbling, retention; goalkeepers have their own six) shown on the card.

Both are pure functions of the engine output plus the two calibration files
shipped with the engine (`seuils_flops_postes_2526.json`,
`echelles_attributs.json`).  Nothing here touches the points table or the
percentiles: they are calibrated on 42 000 performances and are read-only.

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
# Line label -> card family.  The labels are the ones the engine writes in
# `prestation["lignes"]` (see bareme_stats.POINTS / FRACTIONS and the extra
# lines credited in topsflops.calculer).
#
# TO CONFIRM against the ranking pipeline that produced echelles_attributs.json:
# the percentiles were computed on family sums, so this grouping must match
# the one used there or the 40-99 scale drifts.  It is kept as data on
# purpose so it can be corrected without touching any logic.
# --------------------------------------------------------------------------
FAMILLE_LIGNE = {
    # FIN — finishing
    "But": "FIN",
    "xG hors penalty (par unite)": "FIN",
    "Tir cadre": "FIN",
    "Poteau ou barre": "FIN",
    "Tir non cadre": "FIN",
    "Tir contre par un defenseur": "FIN",
    "Grosse occasion manquee": "FIN",
    "Penalty manque": "FIN",
    "Surperformance de finition (G - xG)": "FIN",
    # CRE — creation
    "Passe decisive": "CRE",
    "xA (par unite)": "CRE",
    "Grosse occasion creee": "CRE",
    "Occasion creee": "CRE",
    "Centre reussi": "CRE",
    # PRO — progression
    "Passe dans le dernier tiers": "PRO",
    "Long ballon reussi": "PRO",
    # DEF — defence
    "Sauvetage sur la ligne": "DEF",
    "Tacle du dernier defenseur": "DEF",
    "Tir contre": "DEF",
    "Interception": "DEF",
    "Degagement": "DEF",
    "Degagement de la tete": "DEF",
    "Duel gagne": "DEF",
    "Duel perdu": "DEF",
    "Recuperation": "DEF",
    "Dribble par l'adversaire": "DEF",
    "Faute commise": "DEF",
    "Penalty concede": "DEF",
    "Erreur menant a un but": "DEF",
    "Duel aerien gagne": "DEF",
    "Duel au sol gagne": "DEF",
    "Duels defensifs (taux vs reference)": "DEF",
    "Clean sheet": "DEF",
    # DRI — dribbling
    "Dribble reussi": "DRI",
    "Penalty obtenu": "DRI",
    "Faute subie": "DRI",
    # CON — retention / ball security
    "Passe reussie": "CON",
    "Ballon touche": "CON",
    "Ballon perdu au contact": "CON",
    "But contre son camp": "CON",
    # Goalkeeper families
    "Arret": "ARR",
    "Arret plongeant": "ARR",
    "Arret dans la surface": "ARR",
    "Penalty arrete": "ARR",
    "But evite vs xGOT (par unite)": "EVI",
    "Sortie aerienne": "SOR",
    "Sortie dans le dos": "SOR",
    "Degagement du poing": "SOR",
    "But encaisse": "BUT",
}
# Lines that a goalkeeper's `lignes` may carry but that belong to REL/PRO on
# their card rather than the outfield family of the same label.
FAMILLE_LIGNE_GARDIEN = {
    "Passe reussie": "REL",
    "Long ballon reussi": "REL",
    "Passe dans le dernier tiers": "PRO",
    "Clean sheet": "BUT",
}
# Lines deliberately left out of every family (they are not a skill).
LIGNES_HORS_FAMILLE = {"Carton rouge"}


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

    The percentile thresholds were measured on brut / coef, so a goal in a
    Champions League final and the same goal in Ligue 1 land on the same
    note.  Rewarding the competition is a *game* decision (see scoring.py),
    not a rating one.
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
                       gardien: bool) -> dict[str, float]:
    """Group the engine's scoring lines into card families (neutral of coef)."""
    out: dict[str, float] = {}
    for lib, v in lignes.items():
        if any(lib.startswith(h) for h in LIGNES_HORS_FAMILLE):
            continue
        fam = None
        if gardien:
            fam = FAMILLE_LIGNE_GARDIEN.get(lib)
        if fam is None:
            fam = FAMILLE_LIGNE.get(lib)
        if fam is None:
            continue
        out[fam] = out.get(fam, 0.0) + brut_neutre(v, coef)
    return out


def attribut(valeur: float, echelle: list[float]) -> int:
    """Map a family sum to 40-99 via its 201-point percentile scale.

    Rank is the *lowest* index among ties (bisect_left): on a family where
    half the field sits at exactly 0 — a full-back who never shoots — the
    player stays low rather than being lifted to the middle of the plateau.
    """
    n = len(echelle) - 1
    i = bisect.bisect_left(echelle, valeur)
    pct = max(0, min(n, i)) / n
    return ATTRIBUT_MIN + round((ATTRIBUT_MAX - ATTRIBUT_MIN) * pct)


def attributs(lignes: dict[str, float], coef: float, poste: str,
              echelles: dict | None = None) -> dict[str, int]:
    """Six attributes on 40-99 for a performance (outfield or goalkeeper)."""
    echelles = echelles or charger_echelles()
    gardien = poste == "Gardien"
    table = echelles["gardien" if gardien else "champ"]
    axes = AXES_GARDIEN if gardien else AXES_CHAMP
    sommes = sommes_par_famille(lignes, coef, gardien)
    return {ax: attribut(sommes.get(ax, 0.0), table[ax]) for ax in axes}


def attributs_prestation(p: dict, echelles: dict | None = None) -> dict[str, int]:
    """Convenience: attributes from one entry of topsflops.json `prestations`."""
    return attributs(p.get("lignes") or {}, float(p.get("coef") or 1.0),
                     p["poste"], echelles)

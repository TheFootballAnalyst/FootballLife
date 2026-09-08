"""evolution.py — how a card and a manager's budget change over time.

This is the economic core of the game and the most structuring design
decision (docs/CONTEXTE.md section 3b).  Every number here is a proposal to
be tuned by the backtest, not a rule: the functions are pure so a full
season can be replayed offline with different constants.

Three quantities:

  OVR      the card's overall rating on 40-99, a slow-moving average of the
           player's notes.  It starts the season from last season's notes
           (shrunk towards a cautious prior when the sample is thin — an
           unknown player is *cheap*, which is what rewards scouting) and
           then follows each new note with an exponential moving average.
  PRIX     the card's price in credits, an exponential function of OVR so
           that stars cost many times a solid regular.  Recomputed after
           every gameweek: buying low before the OVR climbs is the skill.
  BUDGET   what a manager can spend.  It grows with results: a share of the
           points scored above a baseline is paid out every gameweek.
"""
from __future__ import annotations

import math

OVR_MIN, OVR_MAX = 40, 99
# Season-mean notes are compressed (regulars sit between ~4.8 and ~8.0 over
# the five leagues, ~4.7 to ~7.7 in Ligue 1 alone, because the engine's
# competition weighting lives inside the note).  The OVR scale is therefore
# calibrated per game league on its own perimeter: `calibrer_echelle` sets
# the two bounds from the distribution of the seeding season's means.
NOTE_OVR_BAS, NOTE_OVR_HAUT = 4.8, 7.8   # defaults ~ top-5 regulars
QUANTILE_BAS, QUANTILE_HAUT = 0.02, 0.995

# Season start: weighted mean of last season's notes shrunk to a prior.
PRIOR_NOTE = 5.5             # below median: an unproven player is cheap
K_RETRECISSEMENT = 10.0      # in full matches (90 min); the prior weighs
                             # as much as 10 full matches

# In season: exponential moving average of the notes.
ALPHA_EMA = 0.08             # a note moves the OVR-note by 8 % of the gap
MINUTES_POIDS_PLEIN = 60.0   # a short cameo moves the rating less

# Price
PRIX_PLANCHER = 0.5
PRIX_BASE_OVR = 60           # OVR 60 costs 1 credit
PRIX_DOUBLE_TOUS_LES = 8     # +8 OVR = price x2  (99 ~ 29.5 credits)

# Demand: a card's price is its OVR price x (1 + DEMANDE x share of the
# managers who own it).  Backtested at 1.0 (docs/BACKTEST.md): keeps the
# game global and the informed manager ahead.
DEMANDE = 1.0

# Budget
BUDGET_INITIAL = 60.0        # ~60 % of the global perimeter's best 15 (backtest)
TAILLE_EFFECTIF = 15         # 11 + 4 bench
SCORE_REFERENCE = 60.0       # a gameweek at 11 x 5.5 (or 66 at 11 x 6)
TAUX_GAIN = 0.05             # credits per point above the reference
GAIN_MAX_SEMAINE = 3.0


def calibrer_echelle(moyennes: list[float]) -> tuple[float, float]:
    """Set NOTE_OVR_BAS/HAUT so that the perimeter's regulars span 40-99.

    `moyennes` are minutes-weighted season means of players with a real
    sample (say >= 450 minutes).  Bounds are the 2nd and 99.5th percentiles
    so one freak season does not stretch the whole scale.
    """
    global NOTE_OVR_BAS, NOTE_OVR_HAUT
    if len(moyennes) < 20:
        return NOTE_OVR_BAS, NOTE_OVR_HAUT
    xs = sorted(moyennes)
    def q(p):
        i = min(len(xs) - 1, max(0, int(round(p * (len(xs) - 1)))))
        return xs[i]
    NOTE_OVR_BAS, NOTE_OVR_HAUT = round(q(QUANTILE_BAS), 2), round(q(QUANTILE_HAUT), 2)
    return NOTE_OVR_BAS, NOTE_OVR_HAUT


def ovr_depuis_note(note_moyenne: float) -> int:
    """Linear map of a mean note to 40-99, clamped."""
    k = (note_moyenne - NOTE_OVR_BAS) / (NOTE_OVR_HAUT - NOTE_OVR_BAS)
    return int(round(OVR_MIN + (OVR_MAX - OVR_MIN) * max(0.0, min(1.0, k))))


def note_depuis_ovr(ovr: float) -> float:
    return NOTE_OVR_BAS + (ovr - OVR_MIN) / (OVR_MAX - OVR_MIN) * (NOTE_OVR_HAUT - NOTE_OVR_BAS)


def note_initiale(notes_minutes: list[tuple[float, float]]) -> float:
    """Shrunk minutes-weighted mean of last season's (note, minutes).

    An empty list returns the prior: a newcomer is priced as a cautious
    unknown, not as a median player.
    """
    poids = sum(m / 90.0 for _, m in notes_minutes)
    somme = sum(n * m / 90.0 for n, m in notes_minutes)
    return (somme + PRIOR_NOTE * K_RETRECISSEMENT) / (poids + K_RETRECISSEMENT)


def ovr_initial(notes_minutes: list[tuple[float, float]]) -> int:
    return ovr_depuis_note(note_initiale(notes_minutes))


def note_ema(note_courante: float, note_match: float, minutes: float) -> float:
    """Update the rating-note with one new match note."""
    w = min(1.0, minutes / MINUTES_POIDS_PLEIN) if minutes > 0 else 0.0
    return note_courante + ALPHA_EMA * w * (note_match - note_courante)


def prix(ovr: float) -> float:
    """Price in credits, exponential in OVR, one decimal."""
    p = 2.0 ** ((ovr - PRIX_BASE_OVR) / PRIX_DOUBLE_TOUS_LES)
    return round(max(PRIX_PLANCHER, p), 1)


def prix_demande(ovr: float, part: float, k: float | None = None) -> float:
    """Price with the demand multiplier: `part` is the share (0..1) of
    managers owning the card, `k` the season's DEMANDE."""
    k = DEMANDE if k is None else k
    return round(prix(ovr) * (1.0 + k * max(0.0, part)), 1)


def gain_semaine(score: float) -> float:
    """Credits earned by a manager for one gameweek score."""
    g = max(0.0, score - SCORE_REFERENCE) * TAUX_GAIN
    return round(min(GAIN_MAX_SEMAINE, g), 2)


def valeur_effectif(ovrs: list[float]) -> float:
    return round(sum(prix(o) for o in ovrs), 1)


def plus_value(ovr_achat: float, ovr_actuel: float) -> float:
    """Credits gained (or lost) by holding a card whose OVR moved."""
    return round(prix(ovr_actuel) - prix(ovr_achat), 1)


def ovr_prix_table() -> list[tuple[int, float]]:
    """Reference table, handy for docs and for sanity-checking a budget."""
    return [(o, prix(o)) for o in range(OVR_MIN, OVR_MAX + 1)]


def budget_moyen_par_carte(budget: float = BUDGET_INITIAL,
                           taille: int = TAILLE_EFFECTIF) -> float:
    """OVR a manager can afford on average if they spread the budget evenly."""
    par_carte = budget / taille
    return PRIX_BASE_OVR + PRIX_DOUBLE_TOUS_LES * math.log2(max(par_carte, PRIX_PLANCHER))

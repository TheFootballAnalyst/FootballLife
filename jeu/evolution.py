"""evolution.py — how a card and a manager's budget change over time.

This is the economic core of the game and the most structuring design
decision (docs/CONTEXTE.md section 3b).  Every number here is a proposal to
be tuned by the backtest, not a rule: the functions are pure so a full
season can be replayed offline with different constants.

Three quantities:

  OVR      the card's overall rating on 40-99: the player's quality over
           a season, read from the SEASON BARÈME (jeu/bareme.py, the
           engine's Ballon d'or barème).  It starts as last season's
           hybrid total (60 % barème per 90, 40 % palmarès) placed on a
           bell by rank among the regulars (MU_OVR, SIGMA_OVR), then the
           terrain part follows this season's matches, last season keeping
           the weight POIDS_SAISON_PASSEE; the OVR is bounded to
           ±BORNE_OVR around the season start: a bad month cannot cost a
           star twenty points.  Recent form is shown on the card, not
           priced in — the gap between form and OVR is what an attentive
           manager exploits.  (The note-based running mean below —
           note_initiale, note_maj, ovr_borne — was the first mechanism;
           it is kept for jeu/backtest.py, which compares mechanisms.)
  PRIX     the card's price in millions of euros.  It starts the season at
           the player's real market value (FotMob's figure, Transfermarkt
           style, read from the match sheets) and then follows the OVR:
           +PRIX_DOUBLE_TOUS_LES OVR points doubles it, the same drop halves
           it.  A card everybody owns costs more (demand).  Buying a player
           before his OVR climbs is the skill.
  BUDGET   what a manager can spend, in millions of euros.  It grows with
           results: a share of the points scored above a baseline is paid
           out every gameweek.

Every amount of money in the game is in millions of euros (M€): 0.1 is
100 k€, 152.5 is Haaland.
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

# In season: running shrunk mean.  Last season's matches weigh
# POIDS_SAISON_PASSEE each (in full-match equivalents), this season's 1, the
# prior K.  A new match therefore weighs 1 / (K + weight so far): with a
# full season behind, about 1/25 at the start and 1/45 at the end.
POIDS_SAISON_PASSEE = 0.5
BORNE_OVR = 10               # displayed OVR stays within +-10 of the season start

# The barème OVR (jeu/bareme.py): a card's Ballon d'or total is placed on
# 40-99 by its rank among the season's regulars, on a bell centred on
# MU_OVR with SIGMA_OVR per standard deviation.  The median regular reads
# 65, one regular in six is 75 or more, one in forty 85 or more, the top of
# the ranking 98-99 — a FIFA-like spread, whatever the shape of the barème.
MU_OVR, SIGMA_OVR = 65.0, 10.0

# The same bell for the six attributes, on their own axis distribution.
# A plain 40 + 59 x rank put the MEDIAN outfield player at 70 on every
# axis, so half the pool read 70+ and a position's own specialty (rank
# 0.88 for a striker's finishing) read 92 whatever the player was worth.
# Centred lower and wider: the median reads 58, a position's specialty
# about 73, the genuine top of an axis 95-99, and 2 % of the cards carry
# a 90 anywhere.
MU_ATTR, SIGMA_ATTR = 58.0, 14.0

# Price (M€)
PRIX_PLANCHER = 0.1          # 100 k€: a card is never free
PRIX_DOUBLE_TOUS_LES = 8     # +8 OVR since the season start = price x2

# Demand multiplier on the cote: (1 + DEMANDE x share of the managers who
# hold the card).  It priced the first store (backtested at 1.0, see
# docs/BACKTEST.md); with the auction house the managers set the price
# themselves and the cote stays a pure reference, so it is off.
DEMANDE = 0.0

# Budget (M€)
BUDGET_INITIAL = 100.0       # a club's transfer budget for 15 cards
TAILLE_EFFECTIF = 15         # 11 + 4 bench
SCORE_REFERENCE = 60.0       # a gameweek at 11 x 5.5 (or 66 at 11 x 6)
TAUX_GAIN = 0.1              # M€ per point above the reference
GAIN_MAX_SEMAINE = 5.0       # 5 % of the initial budget at most per gameweek


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


def poids_initial(notes_minutes: list[tuple[float, float]]) -> float:
    """Weight last season's sample keeps in the running mean: its full-match
    equivalents x POIDS_SAISON_PASSEE.  The season-start note itself is the
    plain shrunk mean (best estimate); only its inertia is discounted, so
    this season's matches take over faster than they were accumulated."""
    return POIDS_SAISON_PASSEE * sum(m / 90.0 for _, m in notes_minutes)


def note_initiale_ponderee(notes_minutes: list[tuple[float, float]]) -> tuple[float, float]:
    """(note, poids) of a card at the season start."""
    return note_initiale(notes_minutes), poids_initial(notes_minutes)


def note_maj(note_courante: float, poids: float, note_match: float, minutes: float) -> tuple[float, float]:
    """Fold one match into the running mean: returns the new (note, poids).

    The state (note, poids) is the shrunk mean of everything seen so far
    with total weight `poids`; the prior K is part of the denominator.
    """
    w = max(0.0, minutes) / 90.0
    if w <= 0:
        return note_courante, poids
    d = poids + K_RETRECISSEMENT
    return (note_courante * d + note_match * w) / (d + w), poids + w


def ovr_borne(note: float, ovr_base: int) -> int:
    """Displayed OVR: the note mapped to 40-99, clamped to +-BORNE_OVR
    around the season-start OVR."""
    o = ovr_depuis_note(note)
    return max(OVR_MIN, min(OVR_MAX, max(ovr_base - BORNE_OVR, min(ovr_base + BORNE_OVR, o))))


def prix_carte(valeur_base: float, ovr_base: float, ovr: float) -> float:
    """Price in M€ of a card whose season started at `valeur_base` M€ with
    OVR `ovr_base`, now at `ovr`.  Two decimals (10 k€)."""
    p = valeur_base * 2.0 ** ((ovr - ovr_base) / PRIX_DOUBLE_TOUS_LES)
    return round(max(PRIX_PLANCHER, p), 2)


def prix_demande(valeur_base: float, ovr_base: float, ovr: float, part: float,
                 k: float | None = None) -> float:
    """Price with the demand multiplier: `part` is the share (0..1) of
    managers owning the card, `k` the season's DEMANDE."""
    k = DEMANDE if k is None else k
    return round(prix_carte(valeur_base, ovr_base, ovr) * (1.0 + k * max(0.0, part)), 2)


def ajuster_valeur(couples: list[tuple[float, float]]) -> tuple[float, float]:
    """Least-squares fit of log2(market value) on OVR over the seeded
    population: (a, b) such that value ~ 2 ** (a + b * ovr).  Used to price
    the few cards FotMob gives no market value for."""
    pts = [(o, math.log2(v)) for o, v in couples if v and v > 0]
    n = len(pts)
    if n < 20:
        return (math.log2(1.0) - 0.125 * 60, 0.125)      # 1 M€ at OVR 60, x2 per 8
    mx = sum(o for o, _ in pts) / n
    my = sum(y for _, y in pts) / n
    sxx = sum((o - mx) ** 2 for o, _ in pts)
    sxy = sum((o - mx) * (y - my) for o, y in pts)
    b = sxy / sxx if sxx else 0.0
    return (my - b * mx, b)


def valeur_estimee(ovr: float, ajust: tuple[float, float]) -> float:
    a, b = ajust
    return round(max(PRIX_PLANCHER, 2.0 ** (a + b * ovr)), 2)


def gain_semaine(score: float) -> float:
    """Credits earned by a manager for one gameweek score."""
    g = max(0.0, score - SCORE_REFERENCE) * TAUX_GAIN
    return round(min(GAIN_MAX_SEMAINE, g), 2)

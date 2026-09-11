"""bareme.py — the season barème as the source of a card's OVR and attributes.

The engine has two readings of a player.  topsflops.py rates one MATCH
(the note /10 the fantasy score is made of).  bareme_stats.py rates a
SEASON: every action of every match, weighted by the competition, the round
and the opponent, summed per player and read per 90 minutes — the "Ballon
d'or" barème, calibrated by hand over 2025/26 and reproduced here to the
decimal (docs/BACKTEST.md).  This module is the bridge between that
barème and the cards.

What a card takes from it:

  OVR at the season start   the hybrid Ballon d'or total of last season:
                            60 % the barème per 90 (S, "terrain"), 40 % the
                            palmarès (titles and distinctions of
                            palmares_zero.py), both on the same dispersion.
                            The total is placed on 40-99 by RANK among the
                            season's regulars, on a bell (MU_OVR +- SIGMA_OVR):
                            the median regular reads 65, 84 % are under 75,
                            2 % are 85 and above, the top of the ranking
                            reads 98-99.
  OVR in season             the terrain part moves, the palmarès is frozen.
                            The running barème blends last season (weighed
                            POIDS_SAISON_PASSEE) with this season's matches;
                            its reading on the same bell, minus the reading
                            of the seed, is the card's move — bounded so a
                            bad month never unmakes a star.  The bound is
                            +-BORNE_OVR for a card with a full season
                            behind it and widens to BORNE_NOUVEAU for one
                            seeded on nothing (`borne`): a signing from an
                            uncovered league has no past to protect.
  the six attributes        the points of the barème's ACTIONS per 90, per
                            axis (finishing, creation, progression,
                            dribbling, retention, defence; the keeper's
                            own six), ranked among ALL outfield regulars:
                            a defender's dribbling is compared to a
                            winger's.  Read on the same kind of bell as the
                            OVR (MU_ATTR +- SIGMA_ATTR), so the median of a
                            position on its own specialty reads about 73
                            and not 92.  Only absolute action points are
                            used here, never the engine's position-relative
                            corrections — those are what made a striker's
                            three interceptions read as elite defence.

Thin samples are shrunk exactly like the engine does (K_RETRECISSEMENT
minutes of the position's median regular), the goalkeepers are aligned on
the outfield median, and a substitute's per 90 is discounted by his share
of starts (facteur_role) — read from the match sheets, so it works in
season and needs no side file.

The engine is run once on a FotMob base (bareme_stats.charger, ~30 s) for
EVERY player; its per-key, per-date trace (`par_cle_date`) is folded into
gameweek windows, which the game base stores (table bareme_journee) and the
pipeline adds up.  Nothing here is drawn: the same base gives the same
cards.
"""
from __future__ import annotations

import bisect
import contextlib
import io
import json
import os
import pathlib
import statistics
import sys
from statistics import NormalDist

RACINE = pathlib.Path(__file__).resolve().parent.parent
MOTEUR = RACINE / "moteur"
sys.path.insert(0, str(RACINE))

from jeu import evolution as E  # noqa: E402
from jeu import notation as N  # noqa: E402

# --------------------------------------------------------------------------
# Constants (the engine's own where they exist)
# --------------------------------------------------------------------------

MINUTES_REFERENCE = 2300     # the engine's Ballon d'or panel: the hybrid dispersions are measured on it
MINUTES_REGULIER = 900       # a card with a real season behind it: the scales are measured on them
MINUTES_PRIOR = 2000         # the position's median is taken among these (engine: retrecir)
K_ROLE = 10                  # match sheets before a player's own share of starts outweighs the anchor
Q = 1000                     # resolution of the stored scales (quantiles at i/Q)
ATTR_MIN, ATTR_MAX = 40, 99
_ND = NormalDist()

# The six axes, as points of the barème's ACTIONS (bareme_stats.POINTS and
# FRACTIONS keys, plus the engine's own synthetic keys: g_moins_xg,
# penalty_marque, clean_sheet).  Position-relative lines (correction_*,
# taux_duels, the FBref excess lines) are deliberately left out.
AXES_CHAMP = {
    "FIN": ["goals", "expected_goals_non_penalty", "ShotsOnTarget", "shots_woodwork", "ShotsOffTarget",
            "blocked_shots", "big_chance_missed_title", "missed_penalty", "g_moins_xg", "penalty_marque"],
    "CRE": ["assists", "expected_assists", "big_chance_created_team_title", "chances_created", "accurate_crosses"],
    "PRO": ["passes_into_final_third", "long_balls_accurate", "accurate_passes"],
    "DEF": ["clearance_off_the_line", "last_man_tackle", "shot_blocks", "interceptions", "clearances",
            "headed_clearance", "duel_won", "duel_lost", "recoveries", "dribbled_past", "fouls",
            "conceded_penalties", "errors_led_to_goal", "owngoal", "aerials_won", "ground_duels_won", "clean_sheet"],
    "DRI": ["dribbles_succeeded", "was_fouled", "penalties_won"],
    "CON": ["touches", "dispossessed"],
}
AXES_GARDIEN = {
    "ARR": ["saves", "keeper_diving_save", "saves_inside_box", "saved_penalties"],
    "EVI": ["goals_prevented"],
    "SOR": ["keeper_high_claim", "keeper_sweeper", "punches"],
    "REL": ["long_balls_accurate"],
    "BUT": ["goals_conceded", "clean_sheet"],
    "PRO": ["accurate_passes"],
}
LIBELLES_GARDIEN = {"REL": "Jeu long", "PRO": "Jeu court"}

_bs = _pz = None


def moteur():
    """Import the engine with its side files pinned to moteur/ (they are
    read relative to the working directory)."""
    global _bs, _pz
    if _bs is None:
        avant = os.getcwd()
        os.chdir(MOTEUR)
        if str(MOTEUR) not in sys.path:
            sys.path.insert(0, str(MOTEUR))
        try:
            import bareme_stats as bs
            import palmares_zero as pz
        finally:
            os.chdir(avant)
        for nom in ("COEFS", "EVENTS", "FBREF_MATCHS", "TITULAIRE", "MANUEL_DISTINCTIONS", "MANUEL_POSTES",
                    "UNDERSTAT", "UNDERSTAT_ASSOC", "DB_PATH"):
            setattr(bs, nom, MOTEUR / getattr(bs, nom).name)
        pz.MANUEL, pz.DB = MOTEUR / "bareme_manuel.json", MOTEUR / "fotmob.db"
        bs.SEUIL_GARDIEN = 1          # the game loads every player; the panel is filtered here
        _bs, _pz = bs, pz
    return _bs, _pz


# --------------------------------------------------------------------------
# Running the engine: per-player, per-date windows
# --------------------------------------------------------------------------

def fenetre_vide() -> dict:
    return {"min": 0.0, "pts": 0.0, "tit": 0, "dispo": 0, "axes": {}}


def ajouter(a: dict, b: dict, poids: float = 1.0) -> dict:
    """a + poids x b, window-wise (minutes, points, starts, sheets, axes)."""
    out = {"min": a["min"] + poids * b["min"], "pts": a["pts"] + poids * b["pts"],
           "tit": a["tit"] + poids * b["tit"], "dispo": a["dispo"] + poids * b["dispo"],
           "axes": dict(a["axes"])}
    for k, v in b["axes"].items():
        out["axes"][k] = out["axes"].get(k, 0.0) + poids * v
    return out


def arrondir(f: dict) -> dict:
    return {"min": round(f["min"], 1), "pts": round(f["pts"], 3), "tit": round(f["tit"], 2), "dispo": round(f["dispo"], 2),
            "axes": {k: round(v, 3) for k, v in f["axes"].items()}}


def calculer(fot) -> dict[int, dict]:
    """Run the barème on a FotMob base for every player who played.

    Returns {player_id: {nom, poste, team_id, dates: {date: fenetre}}} where
    the window of a date holds the minutes, the barème points (no position
    coefficient — the engine does not apply one either), the starts and
    squad sheets of the day, and the points per attribute axis.
    """
    bs, _ = moteur()
    bs._ELIGIBLES = None
    with contextlib.redirect_stdout(io.StringIO()):
        joueurs = bs.reponderer(bs.charger(fot, 1, 0))
    feuilles: dict[int, dict[str, list]] = {}
    for pid, date, tit in fot.execute("""
            SELECT a.player_id, substr(m.date_utc, 1, 10), a.position_id IS NOT NULL
            FROM appearance a JOIN match m ON m.match_id = a.match_id AND m.usable = 1"""):
        d = feuilles.setdefault(pid, {}).setdefault(date, [0, 0])
        d[0] += 1
        d[1] += int(tit)
    out = {}
    for pid, j in joueurs.items():
        axes = AXES_GARDIEN if j["poste"] == "Gardien" else AXES_CHAMP
        cle_axe = {c: ax for ax, cs in axes.items() for c in cs}
        dates: dict[str, dict] = {}
        for cle, par_date in j["par_cle_date"].items():
            ax = cle_axe.get(cle)
            for date, v in par_date.items():
                f = dates.setdefault(date, fenetre_vide())
                f["pts"] += v
                if ax:
                    f["axes"][ax] = f["axes"].get(ax, 0.0) + v
        for date, m in j["minutes_par_date"].items():
            dates.setdefault(date, fenetre_vide())["min"] += m
        for date, (dispo, tit) in feuilles.get(pid, {}).items():
            f = dates.setdefault(date, fenetre_vide())
            f["dispo"] += dispo
            f["tit"] += tit
        out[pid] = {"nom": j["nom"], "poste": j["poste"], "team_id": j.get("team_id"), "dates": dates}
    return out


def fenetre(joueur: dict, du: str | None = None, au: str | None = None) -> dict:
    """The player's window over [du, au] (dates as YYYY-MM-DD, both
    inclusive, None = open)."""
    f = fenetre_vide()
    for date, d in joueur["dates"].items():
        if (du is None or date >= du) and (au is None or date <= au):
            f = ajouter(f, d)
    return f


def fenetres_journees(joueur: dict, journees: list[tuple[int, str, str]]) -> dict[int, dict]:
    """Fold the player's dates into gameweek windows.  `journees` =
    [(journee_id, du, au)] sorted by date; a date before the first window
    joins the first, after the last (a final played after the league's
    last round) the last, in a gap the previous one."""
    out: dict[int, dict] = {}
    if not journees:
        return out
    debuts = [du for _, du, _ in journees]
    for date, d in joueur["dates"].items():
        i = max(0, bisect.bisect_right(debuts, date) - 1)
        jid = journees[i][0]
        out[jid] = ajouter(out.get(jid, fenetre_vide()), d)
    return out


def eligibles(fot) -> set[int]:
    """The players the engine admits into its panel whatever their minutes:
    an MVP or a team-of-the-tournament pick of a major competition is a
    jury's verdict on a season and cannot be cut by a minutes threshold
    (bareme_stats.eligibles_distinction — that is how Messi, 1 990 club
    minutes and the World Cup's team of the tournament, stays in)."""
    bs, _ = moteur()
    bs._ELIGIBLES = None
    return set(bs.eligibles_distinction(fot))


def palmares(fot) -> dict[int, float]:
    """Palmarès points of every player (palmares_zero.calculer), from the
    base and moteur/bareme_manuel.json."""
    _, pz = moteur()
    with contextlib.redirect_stdout(io.StringIO()):
        _, total, _ = pz.calculer(fot)
    return {pid: v for pid, v in total.items() if v > 0}


# --------------------------------------------------------------------------
# From a window to a terrain score, an OVR, six attributes
# --------------------------------------------------------------------------

def _quantiles(valeurs: list[float]) -> list[float]:
    xs = sorted(valeurs)
    if not xs:
        return [0.0] * (Q + 1)
    n = len(xs) - 1
    out = []
    for i in range(Q + 1):
        pos = i / Q * n
        lo = int(pos)
        hi = min(lo + 1, n)
        out.append(round(xs[lo] + (xs[hi] - xs[lo]) * (pos - lo), 5))
    return out


def rang(valeur: float, echelle: list[float]) -> float:
    """Rank 0..1 of a value on a stored scale, clamped one step away from the
    ends so the bell stays finite."""
    n = max(len(echelle) - 1, 1)
    r = (bisect.bisect_left(echelle, valeur) + bisect.bisect_right(echelle, valeur)) / 2 / n
    return max(0.5 / n, min(1 - 0.5 / n, r))


def cloche(valeur: float, echelle: list[float]) -> float:
    """The bell reading (unrounded OVR) of a value on a scale."""
    return E.MU_OVR + E.SIGMA_OVR * _ND.inv_cdf(rang(valeur, echelle))


def par90(f: dict) -> float:
    return f["pts"] / f["min"] * 90.0 if f["min"] else 0.0


def part_role(f: dict, params: dict) -> float:
    """The window's share of starts, shrunk towards the unknown's anchor.

    The raw ratio is worthless on a small sample: one start out of one
    sheet reads 1.00, and a card seeded on nothing then jumped eighteen
    OVR points on its first match — the one thing the design forbids.
    K_ROLE sheets of the anchor are added to the count, so the first
    appearances nudge the card and a real season decides it.  The
    reference (`role_ref`) is measured the same way, so an established
    player's factor is unchanged.
    """
    ancre = params.get("role_inconnu", 1.0)
    return (f["tit"] + ancre * K_ROLE) / (f["dispo"] + K_ROLE)


def terrain(f: dict, poste: str, params: dict) -> float:
    """S, the barème per 90 of a window as the engine reads it: shrunk to the
    position's median over K_RETRECISSEMENT minutes, keepers aligned on the
    outfield median, discounted by the share of starts."""
    bs, _ = moteur()
    k = bs.K_RETRECISSEMENT
    prior = params["priors"].get(poste, params["priors"].get("*", 0.0))
    w = f["min"] / (f["min"] + k) if f["min"] > 0 else 0.0
    s = w * par90(f) + (1 - w) * prior
    if poste == "Gardien":
        s *= params["gk_k"]
    # A player with no window at all has no role either.  Leaving the factor
    # out read him as a guaranteed starter — better than the reference, since
    # role_ref is under 1 — so a card seeded on nothing came out ABOVE the
    # median card instead of below it.  An unknown is read as a rotation
    # player until he proves otherwise (`role_inconnu`, `part_role`).
    part = max(0.05, min(1.0, part_role(f, params)))
    s *= (part / params["role_ref"]) ** bs.EXP_ROLE
    return s


def hybride(s: float, p: float, params: dict) -> float:
    """The Ballon d'or total: 60 % terrain, 40 % palmarès, each centred on
    its 25th percentile and scaled by its dispersion (palmares_zero)."""
    h = params["hybride"]
    t = 200 * h["part_terrain"] * (s - h["p25s"]) / h["sds"]
    if h["sdp"]:
        t += 200 * (1 - h["part_terrain"]) * (max(p, 0.0) - h["p25p"]) / h["sdp"]
    return t


def ovr_base(t: float, params: dict) -> int:
    return int(round(max(E.OVR_MIN, min(E.OVR_MAX, cloche(t, params["echelles"]["T"])))))


def borne(carte_bareme: dict, params: dict) -> float:
    """How far a card may move from its season start, in OVR points.

    The bound exists because the seed is trustworthy: a full season behind
    a card means a bad month says little.  A card seeded on nothing — a
    signing from an uncovered league, a promoted club's squad, a teenager
    on debut — is seeded on its position's median, and there is nothing
    there to protect.  The bound therefore widens as the seed thins, from
    BORNE_OVR for a full season to BORNE_NOUVEAU for no history at all:
    a pépite can climb this season rather than next.
    """
    k = params.get("k_retrecissement", 1200.0)
    minutes = (carte_bareme.get("base") or {}).get("min", 0.0) * params.get("poids_passe", 1.0)
    w = minutes / (minutes + k) if minutes > 0 else 0.0
    return E.BORNE_OVR * w + E.BORNE_NOUVEAU * (1 - w)


def ovr_courant(ovr_base_: int, s0: float, s: float, params: dict, marge: float | None = None) -> int:
    """The card's OVR in season: the seed OVR plus the move of the terrain
    reading on the bell, bounded to +-`marge` (BORNE_OVR by default)."""
    ech = params["echelles"]["S"]
    marge = E.BORNE_OVR if marge is None else marge
    o = ovr_base_ + cloche(s, ech) - cloche(s0, ech)
    o = max(ovr_base_ - marge, min(ovr_base_ + marge, o))
    return int(round(max(E.OVR_MIN, min(E.OVR_MAX, o))))


def axes_par90(f: dict, poste: str, params: dict) -> dict[str, float]:
    """The six axes of a window per 90, each shrunk to the position's median
    like the terrain score."""
    bs, _ = moteur()
    k = bs.K_RETRECISSEMENT
    axes = AXES_GARDIEN if poste == "Gardien" else AXES_CHAMP
    priors = params["priors_axes"].get(poste) or params["priors_axes"].get("*", {})
    w = f["min"] / (f["min"] + k) if f["min"] > 0 else 0.0
    out = {}
    for ax in axes:
        v = f["axes"].get(ax, 0.0) / f["min"] * 90.0 if f["min"] else 0.0
        out[ax] = w * v + (1 - w) * priors.get(ax, 0.0)
    return out


def attribut(valeur: float, echelle: list[float], params: dict) -> int:
    """One attribute on 40-99: the rank of `valeur` on its axis scale, read
    on a bell (MU_ATTR +- SIGMA_ATTR).

    Not 40 + 59 x rank: that puts the MEDIAN player of the pool at 70 on
    every axis, so half the cards read 70+, and the median of a position on
    its own specialty — rank 0.88 for a striker's finishing, 0.90 for a
    centre-back's defending — reads 92 before the player has done anything.
    A card then described the position, not the player.  The bell keeps the
    order (so a winger still out-dribbles a centre-back, the rule that
    forbids per-position percentiles) and gives the scale its shape back.
    """
    mu = params.get("mu_attr", E.MU_ATTR)
    sigma = params.get("sigma_attr", E.SIGMA_ATTR)
    return int(round(max(ATTR_MIN, min(ATTR_MAX, mu + sigma * _ND.inv_cdf(rang(valeur, echelle))))))


def attributs(f: dict, poste: str, params: dict) -> dict[str, int]:
    """Six attributes on 40-99: the axes per 90 ranked on the season's
    scales (outfield players all together, keepers among keepers)."""
    table = params["echelles"]["gardien" if poste == "Gardien" else "champ"]
    return {ax: attribut(v, table[ax], params) for ax, v in axes_par90(f, poste, params).items()}


# --------------------------------------------------------------------------
# Season parameters, measured on the seed
# --------------------------------------------------------------------------

def parametres(bases: dict[int, tuple[str, dict]], pal: dict[int, float] | None = None,
               population: dict[int, tuple[str, dict]] | None = None,
               exemptes: set[int] | None = None) -> dict:
    """Measure everything a season needs from the seed windows
    {player_id: (poste, fenetre)} and the palmarès: the priors, the keeper
    alignment, the role reference and the hybrid dispersions on
    `population` (every player the engine rated — the engine's own panel;
    the cards themselves when not given), the OVR and attribute scales on
    the cards' regulars.  `exemptes` are the players the engine admits
    into its panel whatever their minutes (see `eligibles`).  Stored as
    parametre 'bareme'."""
    bs, pz = moteur()
    pal = pal or {}
    med = statistics.median
    cartes = bases
    bases = population or bases
    # priors: median per 90 of the position's players with a full season
    priors, priors_axes = {}, {}
    for poste in bs.ORDRE:
        gens = [(f, pid) for pid, (po, f) in bases.items() if po == poste and f["min"] >= MINUTES_PRIOR]
        if gens:
            priors[poste] = med([par90(f) for f, _ in gens])
            axes = AXES_GARDIEN if poste == "Gardien" else AXES_CHAMP
            priors_axes[poste] = {ax: med([f["axes"].get(ax, 0.0) / f["min"] * 90 for f, _ in gens]) for ax in axes}
    tous_pleins = [f for _, (po, f) in bases.items() if f["min"] >= MINUTES_PRIOR]
    priors["*"] = med([par90(f) for f in tous_pleins]) if tous_pleins else 0.0
    global_axes: dict[str, list[float]] = {}
    for po_axes in priors_axes.values():
        for ax, v in po_axes.items():
            global_axes.setdefault(ax, []).append(v)
    priors_axes["*"] = {ax: med(v) for ax, v in global_axes.items()}
    # keeper alignment and role reference, before the role factor
    params = {"priors": priors, "priors_axes": priors_axes, "gk_k": 1.0, "role_ref": 1.0,
              "mu": E.MU_OVR, "sigma": E.SIGMA_OVR, "mu_attr": E.MU_ATTR, "sigma_attr": E.SIGMA_ATTR,
              "borne": E.BORNE_OVR, "poids_passe": E.POIDS_SAISON_PASSEE,
              "k_retrecissement": bs.K_RETRECISSEMENT, "exp_role": bs.EXP_ROLE, "coef_poste": bool(bs.APPLIQUER_COEF_POSTE)}
    brut = {pid: terrain(f, po, params) for pid, (po, f) in bases.items()}
    gk = [brut[pid] for pid, (po, f) in bases.items() if po == "Gardien" and f["min"] >= MINUTES_PRIOR]
    champ = [brut[pid] for pid, (po, f) in bases.items() if po != "Gardien" and f["min"] >= MINUTES_PRIOR]
    if gk and champ and med(gk) > 0:
        params["gk_k"] = med(champ) / med(gk)
    # the median REGULAR starter is the neutral point (engine: facteur_role).
    # Measured on the whole pool it lands on 1.0 — a fringe player who started
    # the two matches he was on the sheet for reads as a full-time starter —
    # and nobody could ever earn the bonus, only the penalty.
    # What a player nobody has seen is read as: a rotation player.  The
    # AGGREGATE share of starts of the non-regulars, not the median of their
    # ratios — half of them appear on one or two sheets and started them, so
    # the median of the ratios reads 0.83 and says nothing.
    tit = sum(f["tit"] for _, (po, f) in bases.items() if 0 < f["min"] < MINUTES_REGULIER)
    dispo = sum(f["dispo"] for _, (po, f) in bases.items() if 0 < f["min"] < MINUTES_REGULIER)
    params["role_inconnu"] = round(tit / dispo, 4) if dispo else 1.0
    # the neutral point: the median REGULAR starter, on the same shrunk
    # quantity the players are measured with
    parts = [part_role(f, params) for _, (po, f) in bases.items()
             if f["dispo"] > 0 and f["min"] >= MINUTES_REGULIER]
    hauts = [p for p in parts if p >= 0.75 * (med(parts) if parts else 1.0)]
    params["role_ref"] = med(hauts) if hauts else 1.0
    S = {pid: terrain(f, po, params) for pid, (po, f) in bases.items()}
    # hybrid dispersions on the engine's panel (players with palmarès, else all of it)
    exemptes = exemptes or set()
    panel = [pid for pid, (po, f) in bases.items() if f["min"] >= MINUTES_REFERENCE or pid in exemptes]
    if len(panel) < 20:
        panel = list(bases)
    pop = [pid for pid in panel if pal.get(pid, 0.0) > 0] or panel
    vs = [S[pid] for pid in pop]
    vp = [pal.get(pid, 0.0) for pid in pop]

    def pct(v, q):
        v = sorted(v)
        i = q * (len(v) - 1)
        lo = int(i)
        return v[lo] + (v[min(lo + 1, len(v) - 1)] - v[lo]) * (i - lo)
    params["hybride"] = {"part_terrain": pz.PART_TERRAIN, "p25s": pct(vs, 0.25) if vs else 0.0,
                         "sds": (statistics.pstdev(vs) or 1.0) if len(vs) > 1 else 1.0,
                         "p25p": pct(vp, 0.25) if vp else 0.0,
                         "sdp": (statistics.pstdev(vp) if len(vp) > 1 and any(vp) else 0.0)}
    # scales on the cards' regulars: the hybrid total, the terrain score, the axes
    reguliers = [pid for pid, (po, f) in cartes.items() if f["min"] >= MINUTES_REGULIER] or list(cartes)
    Sc = {pid: terrain(f, po, params) for pid, (po, f) in cartes.items()}
    T = {pid: hybride(Sc[pid], pal.get(pid, 0.0), params) for pid in reguliers}
    ech = {"T": _quantiles([T[pid] for pid in reguliers]), "S": _quantiles([Sc[pid] for pid in reguliers]),
           "champ": {}, "gardien": {}}
    for cle, axes, gardien in (("champ", AXES_CHAMP, False), ("gardien", AXES_GARDIEN, True)):
        gens = [(po, f) for pid, (po, f) in cartes.items() if pid in set(reguliers) and (po == "Gardien") == gardien]
        for ax in axes:
            ech[cle][ax] = _quantiles([axes_par90(f, po, params)[ax] for po, f in gens])
    params["echelles"] = ech
    params["panel"], params["reguliers"], params["cartes"] = len(pop), len(reguliers), len(cartes)
    params["exemptes"] = sorted(pid for pid in exemptes if pid in bases)
    return params


def carte_initiale(poste: str, base: dict, pal: float, params: dict) -> dict:
    """What a card stores about its seed: the base window, its terrain score
    at full weight (the Ballon d'or reading) and at the in-season weight
    (the reference the moves are measured from), its palmarès, its total."""
    s25 = terrain(base, poste, params)
    s0 = terrain(ajouter(fenetre_vide(), base, params["poids_passe"]), poste, params)
    t = hybride(s25, pal, params)
    ci = {"base": arrondir(base), "s25": round(s25, 4), "s0": round(s0, 4), "pal": round(pal, 2), "t": round(t, 2),
          "ovr": ovr_base(t, params)}
    ci["borne"] = round(borne(ci, params), 1)
    return ci


def etat_courant(carte_bareme: dict, saison: dict, poste: str, params: dict) -> tuple[float, int, dict[str, int], float]:
    """(S, OVR, attributs, poids) of a card given its seed record and its
    season-to-date window."""
    f = ajouter(saison, carte_bareme["base"], params["poids_passe"])
    s = terrain(f, poste, params)
    ovr = ovr_courant(carte_bareme["ovr"], carte_bareme["s0"], s, params,
                      carte_bareme.get("borne", borne(carte_bareme, params)))
    w = f["min"] / (f["min"] + params["k_retrecissement"]) if f["min"] > 0 else 0.0
    return s, ovr, attributs(f, poste, params), w


# --------------------------------------------------------------------------

def main():
    import argparse
    import sqlite3
    ap = argparse.ArgumentParser(description="run the season barème on a FotMob base and print the top")
    ap.add_argument("--fotmob", default=str(MOTEUR / "fotmob.db"))
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--sans-palmares", action="store_true")
    a = ap.parse_args()
    fot = sqlite3.connect(a.fotmob)
    tous = calculer(fot)
    pal = {} if a.sans_palmares else palmares(fot)
    exempt = eligibles(fot)
    bases = {pid: (j["poste"], fenetre(j)) for pid, j in tous.items()}
    params = parametres(bases, pal, exemptes=exempt)
    cartes = {pid: carte_initiale(bases[pid][0], bases[pid][1], pal.get(pid, 0.0), params) for pid in bases}
    # the Ballon d'or ranking is read on the engine's own panel
    panel = [pid for pid in bases if bases[pid][1]["min"] >= MINUTES_REFERENCE or pid in exempt]
    print(f"{len(cartes)} joueurs, panel {len(panel)}, réguliers {params['reguliers']} ; "
          f"priors {json.dumps({k: round(v, 1) for k, v in params['priors'].items()})}")
    print(f"{'rang':>4} {'joueur':24s} {'poste':18s} {'min':>5} {'S':>6} {'P':>5} {'T':>6} OVR  attributs")
    for i, pid in enumerate(sorted(panel, key=lambda p: -cartes[p]["t"])[:a.top], 1):
        c, j = cartes[pid], tous[pid]
        attrs = attributs(ajouter(fenetre_vide(), bases[pid][1], params["poids_passe"]), j["poste"], params)
        print(f"{i:>4} {j['nom'][:24]:24s} {j['poste'][:18]:18s} {bases[pid][1]['min']:>5.0f} {c['s25']:>6.1f} "
              f"{c['pal']:>5.0f} {c['t']:>6.0f} {c['ovr']:>3}  {' '.join(f'{k} {v}' for k, v in attrs.items())}")


if __name__ == "__main__":
    main()

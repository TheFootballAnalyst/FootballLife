"""simulation.py — the ranked lobby match, played with the cards.

This is the game's only match.  It is played with the CARDS — their six
attributes — against an opponent's eleven, with tactics you set and
change while it runs (jeu/lobby.py).  A weekly head-to-head resolved from
the real actions of a gameweek used to sit beside it; it was retired once
the cards had a match of their own.

The repeatability rule of the project applies to the CARDS, not to this
match.  The real weekend fixes what a card is worth (jeu/bareme.py): an
injured Barcola stops accumulating and his card slides, an inconsistent
Adeyemi loses OVR.  The lobby then plays those cards.  A manager who
assembles Haaland, Dembélé and Olise up front wins a lot of matches
because the cards are good, and the cards are good because of what those
players really did.

Nothing here is drawn from an unseeded generator.  Every minute's dice
come from `Random((graine, minute))`: the match is reproducible from its
seed and its tactical timeline alone, so a result can always be audited
and a manager can never reroll a bad minute.  Changing a tactic changes
what happens to the SAME dice, which is what makes an adjustment a real
decision instead of a new draw.

How an eleven becomes a way of playing
--------------------------------------
Six team traits, read from the cards' attributes by line.  A midfield of
retention and progression keeps the ball; wingers who dribble break lines
and open the score up; a back line with defence smothers the other side.

  controle   CON and PRO of the defence and midfield   -> share of possession
  percussion PRO and DRI of the midfield and attack    -> possessions that reach a shot
  creation   CRE of the midfield and attack            -> quality of those shots
  finition   FIN of the attack                         -> converting them
  defense    DEF of the defence and midfield           -> smothering the other side
  gardien    ARR and EVI of the keeper                 -> saving what gets through

Tactics (`Tactique`) shift those weights: holding the ball, going direct,
pressing high, sitting deep, taking risks.  Each is a trade — possession
lowers the shot count and raises the quality of what is left, a high
press wins the ball higher but leaves better chances behind.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

MINUTES = 90

# --------------------------------------------------------------------------
# Calibration.  Targets: about 12 shots and 1.4 goals a side, 26 % of draws.
# --------------------------------------------------------------------------
TIRS_BASE = 0.285         # shots per minute of possession, at parity
XG_BASE = 0.116           # expected goals of a shot, at parity
EXP_POSSESSION = 1.3      # how sharply `controle` decides the ball
POSSESSION_MAX = 0.78     # no eleven ever holds more than this
EXP_TIR = 1.5             # how sharply percussion vs defence decides a shot
EXP_XG = 1.1              # ... the quality of that shot
EXP_FIN = 0.9             # ... and its conversion
XG_MAX = 0.62             # a chance is never a certainty
# A shot every two and a half minutes of possession, and no more.  Without
# a ceiling the two ways of dominating compound: `controle` already buys
# the minutes, then percussion against defence multiplies the shots taken
# in each of them.  Two real clubs never reach it (the shot duel tops out
# at 1.41 over the 96 elevens of the five leagues), but an end-game squad
# of the best cards in the game did — 34 shots in a match, which is not
# football any more.
TIR_PAR_MIN_MAX = 0.40
# Six settings multiply together — my tempo and block and risk, and the
# opponent's — and left free they compounded: two sides going direct,
# high and all-out produced four goals a side and twenty-four shots.
# Football does not, however open the match gets, so the tactical part of
# the shot rate and of the chance quality is held between these bounds.
TAC_TIR_MIN, TAC_TIR_MAX = 0.55, 1.60
TAC_XG_MIN, TAC_XG_MAX = 0.70, 1.45
XG_NOTABLE = 0.13         # below this a shot is a statistic, not an event

LIGNES = {"GK": ("GK",), "DEF": ("DEF",), "MID": ("MID",), "FWD": ("FWD",)}

# The family of each slot of a formation, in the order a lineup is stored:
# keeper, then the back line, the midfield and the attack.
from jeu import scoring as _S  # noqa: E402
FORMATIONS_COMPTES = _S.FORMATIONS


def familles_formation(formation: str) -> list[str]:
    g, d, m, f = _S.FORMATIONS[formation]
    return ["GK"] * g + ["DEF"] * d + ["MID"] * m + ["FWD"] * f


def _z(attr: int) -> float:
    """A card attribute (40-99) on 0-1."""
    return max(0.0, min(1.0, (attr - 40) / 59.0))


def _moyenne(joueurs: list[dict], familles: tuple[str, ...], axes: tuple[str, ...]) -> float:
    """Mean of `axes` over the players of those lines, 0-1.  An empty line
    reads as a weak one rather than as nothing."""
    vals = [_z(j["attributs"].get(ax, 40)) for j in joueurs if j["fam"] in familles for ax in axes]
    return sum(vals) / len(vals) if vals else 0.25


# --------------------------------------------------------------------------
# Tactics
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Tactique:
    """What a manager decides, before the match and during it.

    Each axis is a trade, never a free bonus:
      tempo   "possession" keeps the ball and makes fewer, better chances;
              "direct" gives the ball up and makes more, worse ones.
      bloc    "haut" wins the ball higher (more of your shots, fewer of
              theirs) but what they do get is a better chance;
              "bas" is the mirror.
      risque  "offensif" opens the match for BOTH sides, "prudent" closes it.
    """
    tempo: str = "equilibre"      # possession | equilibre | direct
    bloc: str = "median"          # haut | median | bas
    risque: str = "equilibre"     # offensif | equilibre | prudent

    def valide(self) -> "Tactique":
        t = self.tempo if self.tempo in TEMPO else "equilibre"
        b = self.bloc if self.bloc in BLOC else "median"
        r = self.risque if self.risque in RISQUE else "equilibre"
        return Tactique(t, b, r)


# Every setting is a TRADE, and the products below are balanced so that no
# single one is free: holding the ball wins minutes and loses the sharpness
# to use them, going direct is the mirror.  What separates them is the
# counters (CONTRE), not a bonus.
# (possession odds, own shot rate, own shot quality)
TEMPO = {"possession": (1.35, 0.70, 1.15), "equilibre": (1.0, 1.0, 1.0), "direct": (0.75, 1.45, 0.95)}
# (own shot rate, opponent shot rate, opponent shot quality)
BLOC = {"haut": (1.12, 0.88, 1.25), "median": (1.0, 1.0, 1.0), "bas": (0.90, 1.14, 0.80)}
# (own shot rate, opponent shot rate) — opens or closes the match for BOTH
RISQUE = {"offensif": (1.22, 1.22), "equilibre": (1.0, 1.0), "prudent": (0.85, 0.85)}

# The cycle, read the way football reads it: (my tempo, their block) ->
# (my shot rate, my shot quality).  Holding the ball against a high press
# loses it higher up; going direct against a high line finds the space
# behind, and finds nothing at all against a low one.
CONTRE = {("possession", "haut"): (0.84, 1.0), ("possession", "bas"): (1.12, 1.0),
          ("direct", "haut"): (1.0, 1.22), ("direct", "bas"): (1.0, 0.78)}


# --------------------------------------------------------------------------
# An eleven, read as a way of playing
# --------------------------------------------------------------------------

@dataclass
class Equipe:
    """`joueurs` = [{pid, nom, fam, poste, ovr, attributs}] — the eleven on
    the pitch, in the order the manager fielded them."""
    nom: str
    joueurs: list[dict]
    tactique: Tactique = field(default_factory=Tactique)

    def trait(self, cle: str) -> float:
        return traits(self.joueurs)[cle]


def traits(joueurs: list[dict]) -> dict[str, float]:
    """The six team traits of an eleven, each 0-1."""
    gardien = [j for j in joueurs if j["fam"] == "GK"]
    return {
        "controle": _moyenne(joueurs, ("DEF", "MID"), ("CON", "PRO")),
        "percussion": _moyenne(joueurs, ("MID", "FWD"), ("PRO", "DRI")),
        "creation": _moyenne(joueurs, ("MID", "FWD"), ("CRE",)),
        "finition": _moyenne(joueurs, ("FWD",), ("FIN",)) * 0.75 + _moyenne(joueurs, ("MID",), ("FIN",)) * 0.25,
        "defense": _moyenne(joueurs, ("DEF", "MID"), ("DEF",)),
        "gardien": (_z(gardien[0]["attributs"].get("ARR", 40)) * 0.6
                    + _z(gardien[0]["attributs"].get("EVI", 40)) * 0.4) if gardien else 0.25,
    }


def _duel(a: float, b: float, exposant: float) -> float:
    """Multiplier of a trait against an opposing one: 1.0 at parity."""
    if a + b <= 0:
        return 1.0
    return (2.0 * a / (a + b)) ** exposant


def possession(ta: dict, tb: dict, tac_a: Tactique, tac_b: Tactique) -> float:
    """Share of the minutes side A holds the ball, 0-1."""
    ca = max(1e-6, ta["controle"]) ** EXP_POSSESSION * TEMPO[tac_a.tempo][0]
    cb = max(1e-6, tb["controle"]) ** EXP_POSSESSION * TEMPO[tac_b.tempo][0]
    return max(1 - POSSESSION_MAX, min(POSSESSION_MAX, ca / (ca + cb)))


def _chance(ta: dict, tb: dict, tac_a: Tactique, tac_b: Tactique) -> tuple[float, float]:
    """(probability that a minute of possession becomes a shot, its xG) for
    side A attacking side B."""
    c_tir, c_xg = CONTRE.get((tac_a.tempo, tac_b.bloc), (1.0, 1.0))
    m_tir = (TEMPO[tac_a.tempo][1] * BLOC[tac_a.bloc][0] * RISQUE[tac_a.risque][0]
             * BLOC[tac_b.bloc][1] * RISQUE[tac_b.risque][1] * c_tir)
    m_xg = TEMPO[tac_a.tempo][2] * BLOC[tac_b.bloc][2] * c_xg
    m_tir = max(TAC_TIR_MIN, min(TAC_TIR_MAX, m_tir))
    m_xg = max(TAC_XG_MIN, min(TAC_XG_MAX, m_xg))
    tir = TIRS_BASE * _duel(ta["percussion"], tb["defense"], EXP_TIR) * m_tir
    xg = XG_BASE * _duel(ta["creation"], tb["defense"], EXP_XG) * m_xg
    return min(TIR_PAR_MIN_MAX, tir), min(XG_MAX, xg)


def _tireur(joueurs: list[dict], rng: random.Random, axe: str = "FIN") -> dict:
    """Who takes it: weighted by the axis, forwards first."""
    poids = []
    for j in joueurs:
        w = _z(j["attributs"].get(axe, 40)) + 0.05
        w *= {"FWD": 1.0, "MID": 0.55, "DEF": 0.14, "GK": 0.004}.get(j["fam"], 0.3)
        poids.append(w)
    total = sum(poids) or 1.0
    seuil = rng.random() * total
    acc = 0.0
    for j, w in zip(joueurs, poids):
        acc += w
        if acc >= seuil:
            return j
    return joueurs[-1]


# --------------------------------------------------------------------------
# The match
# --------------------------------------------------------------------------

def jouer(a: Equipe, b: Equipe, graine: int, tactiques: dict[int, tuple[Tactique | None, Tactique | None]] | None = None,
          jusqua: int = MINUTES) -> dict:
    """Play the match minute by minute and return its sheet.

    `tactiques` is the timeline of adjustments: {minute: (tactique A or
    None, tactique B or None)}, applied at the start of that minute.  A
    manager who changes nothing plays his kick-off tactic throughout.
    `jusqua` stops the match early, which is how the live view advances it.

    The dice of minute m are Random(graine * 1000 + m) and nothing else, so the
    sheet is a pure function of (elevens, seed, tactical timeline): the
    same match always replays identically, and an adjustment changes the
    outcome of the SAME dice rather than drawing new ones.
    """
    tactiques = tactiques or {}
    tac_a, tac_b = a.tactique.valide(), b.tactique.valide()
    ta, tb = traits(a.joueurs), traits(b.joueurs)
    score = [0, 0]
    tirs, xg_tot, minutes_ballon = [0, 0], [0.0, 0.0], [0, 0]
    evenements = []
    for m in range(1, min(jusqua, MINUTES) + 1):
        if m in tactiques:
            na, nb = tactiques[m]
            if na is not None:
                tac_a = na.valide()
                evenements.append({"minute": m, "cote": "A", "type": "tactique", "texte": _texte_tactique(a.nom, tac_a)})
            if nb is not None:
                tac_b = nb.valide()
                evenements.append({"minute": m, "cote": "B", "type": "tactique", "texte": _texte_tactique(b.nom, tac_b)})
        rng = random.Random(graine * 1000 + m)
        pa = possession(ta, tb, tac_a, tac_b)
        cote = 0 if rng.random() < pa else 1
        minutes_ballon[cote] += 1
        att, deff = (a, b) if cote == 0 else (b, a)
        t_att, t_def = (ta, tb) if cote == 0 else (tb, ta)
        tac_att, tac_def = (tac_a, tac_b) if cote == 0 else (tac_b, tac_a)
        p_tir, xg = _chance(t_att, t_def, tac_att, tac_def)
        if rng.random() >= p_tir:
            continue
        tirs[cote] += 1
        xg_tot[cote] += xg
        tireur = _tireur(att.joueurs, rng)
        conversion = min(XG_MAX, xg * _duel(_z(tireur["attributs"].get("FIN", 40)) + 0.15,
                                            t_def["gardien"] + 0.15, EXP_FIN))
        if rng.random() < conversion:
            score[cote] += 1
            passeur = _tireur([j for j in att.joueurs if j["pid"] != tireur["pid"]], rng, "CRE")
            evenements.append({"minute": m, "cote": "AB"[cote], "type": "but", "pid": tireur["pid"],
                               "nom": tireur["nom"], "passeur": passeur["nom"], "xg": round(xg, 2),
                               "score": list(score),
                               "texte": f"But de {tireur['nom']}, servi par {passeur['nom']}"})
        elif xg >= XG_NOTABLE:
            # a tame shot is a number on the sheet; only a real chance is a moment
            gk = next((j for j in deff.joueurs if j["fam"] == "GK"), None)
            arret = rng.random() < 0.42 + 0.3 * t_def["gardien"]
            evenements.append({"minute": m, "cote": "AB"[cote], "type": "arret" if arret and gk else "occasion",
                               "pid": tireur["pid"], "nom": tireur["nom"], "xg": round(xg, 2),
                               "texte": (f"Arrêt de {gk['nom']} devant {tireur['nom']}" if arret and gk
                                         else f"{tireur['nom']} manque l'occasion")})
    fini = jusqua >= MINUTES
    poss = [round(100 * minutes_ballon[0] / max(1, sum(minutes_ballon))),
            round(100 * minutes_ballon[1] / max(1, sum(minutes_ballon)))]
    return {
        "minute": min(jusqua, MINUTES), "fini": fini, "score": score,
        "resultat": ("A" if score[0] > score[1] else "B" if score[1] > score[0] else "N") if fini else None,
        "possession": poss, "tirs": tirs, "xg": [round(x, 2) for x in xg_tot],
        "evenements": evenements,
        "traits": {"a": {k: round(v, 3) for k, v in ta.items()}, "b": {k: round(v, 3) for k, v in tb.items()}},
        "tactique": {"a": vars(tac_a), "b": vars(tac_b)},
        "graine": graine,
    }


_MOTS = {"possession": "garde le ballon", "direct": "joue direct", "equilibre": "revient à l'équilibre",
         "haut": "monte son bloc", "median": "replace son bloc", "bas": "descend son bloc",
         "offensif": "prend des risques", "prudent": "ferme le jeu"}


def _texte_tactique(nom: str, t: Tactique) -> str:
    return f"{nom} : {_MOTS.get(t.tempo, t.tempo)}, {_MOTS.get(t.bloc, t.bloc)}, {_MOTS.get(t.risque, t.risque)}"


# The median of each trait over a real card pool (docs/BACKTEST.md), and
# how much of a gap counts as a trait worth naming.
REPERE = {"controle": 0.39, "percussion": 0.31, "creation": 0.40,
          "finition": 0.50, "defense": 0.40, "gardien": 0.30}
DITS = {
    "controle": ("garde le ballon", "subit la possession"),
    "percussion": ("casse les lignes", "bute sur le bloc"),
    "creation": ("crée beaucoup", "crée peu"),
    "finition": ("finit froidement", "gâche ses occasions"),
    "defense": ("verrouille derrière", "laisse des espaces"),
    "gardien": ("un gardien qui sauve", "un gardien fragile"),
}
ECART_STYLE = 0.06        # under this the trait is unremarkable
TRAITS_DITS = 3           # naming every trait names none of them


def style(joueurs: list[dict]) -> str:
    """A one-line reading of how an eleven will play, for the lobby screen.

    Only the traits that stand OUT, most distinctive first.  Listing every
    trait above a threshold made two elite elevens read identically —
    "garde le ballon, casse les lignes, crée beaucoup, finit froidement,
    verrouille derrière" — which tells a manager nothing about either.
    """
    t = traits(joueurs)
    ecarts = sorted(((v - REPERE[k], k) for k, v in t.items() if k in REPERE), key=lambda x: -x[0])
    forces = [DITS[k][0] for d, k in ecarts[:TRAITS_DITS - 1] if d >= ECART_STYLE]
    # always name the worst flaw too: an eleven that leaks is what an
    # opponent most needs to read, and it never wins a magnitude contest
    # against three strengths at once.
    faible = next((DITS[k][1] for d, k in reversed(ecarts) if d <= -ECART_STYLE), None)
    bouts = forces + ([faible] if faible else [])
    return ", ".join(bouts) or "équipe équilibrée, sans trait dominant"


# --------------------------------------------------------------------------

def onze_depuis_cartes(jeu, saison: str, pids: list[int], nom: str = "Équipe") -> Equipe:
    """Build an eleven from the game base's cards."""
    import json
    from jeu import scoring as S
    joueurs = []
    for pid in pids:
        row = jeu.execute("""SELECT j.nom, j.poste, c.ovr, c.attributs FROM carte c
                             JOIN joueur j ON j.player_id = c.player_id
                             WHERE c.player_id = ? AND c.saison = ?""", (pid, saison)).fetchone()
        if not row:
            continue
        nom_j, poste, ovr, attrs = row
        joueurs.append({"pid": pid, "nom": nom_j, "poste": poste,
                        "fam": S.FAMILLE_POSTE.get(poste, "MID"), "ovr": ovr,
                        "attributs": json.loads(attrs or "{}")})
    return Equipe(nom, joueurs)


def main():
    import argparse
    import json
    import sqlite3
    import pathlib
    import sys
    RACINE = pathlib.Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(RACINE))
    from jeu import scoring as S
    ap = argparse.ArgumentParser(description="play one ranked lobby match between two elevens of cards")
    ap.add_argument("--jeu", default=str(RACINE / "jeu" / "demo.sqlite"))
    ap.add_argument("--saison", default="2025/26")
    ap.add_argument("--graine", type=int, default=1)
    ap.add_argument("--budget", type=float, nargs=2, default=[200.0, 200.0])
    ap.add_argument("--tempo", nargs=2, default=["equilibre", "equilibre"])
    a = ap.parse_args()
    jeu = sqlite3.connect(a.jeu)
    rng = random.Random(a.graine)

    def onze(budget):
        """A 4-3-3 inside the budget: the best cards a manager could line up."""
        pris, reste = [], budget
        restants = {"GK": 1, "DEF": 4, "MID": 3, "FWD": 3}
        for fam, n in (("GK", 1), ("DEF", 4), ("MID", 3), ("FWD", 3)):
            postes = [p for p, f in S.FAMILLE_POSTE.items() if f == fam]
            marks = ",".join("?" * len(postes))
            for _ in range(n):
                restants[fam] -= 1
                a_venir = sum(restants.values())
                plafond = max(0.1, reste - a_venir * 0.3)
                pool = jeu.execute(f"""SELECT c.player_id, c.prix FROM carte c JOIN joueur j ON j.player_id=c.player_id
                    WHERE c.saison=? AND j.poste IN ({marks}) AND c.prix <= ?
                    ORDER BY c.ovr DESC LIMIT 25""", [a.saison] + postes + [plafond]).fetchall()
                pool = [(p, x) for p, x in pool if p not in pris]
                if not pool:
                    continue
                pid, prix = rng.choice(pool)
                pris.append(pid); reste -= prix
        return pris

    ea = onze_depuis_cartes(jeu, a.saison, onze(a.budget[0]), "Domicile")
    eb = onze_depuis_cartes(jeu, a.saison, onze(a.budget[1]), "Extérieur")
    ea.tactique = Tactique(tempo=a.tempo[0])
    eb.tactique = Tactique(tempo=a.tempo[1])
    for e in (ea, eb):
        print(f"{e.nom:12s} OVR {sum(j['ovr'] for j in e.joueurs) / len(e.joueurs):.0f} — {style(e.joueurs)}")
        print("   " + ", ".join(f"{j['nom'].split()[-1]}({j['ovr']})" for j in e.joueurs))
    f = jouer(ea, eb, a.graine)
    print(f"\n{ea.nom} {f['score'][0]} - {f['score'][1]} {eb.nom}   "
          f"possession {f['possession'][0]}/{f['possession'][1]} · tirs {f['tirs'][0]}/{f['tirs'][1]} · "
          f"xG {f['xg'][0]}/{f['xg'][1]}")
    for e in f["evenements"]:
        print(f"  {e['minute']:>2}'  {e['texte']}")


if __name__ == "__main__":
    main()

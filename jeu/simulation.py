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
# at 1.50 over the 150 elevens of the eight leagues), but an end-game
# squad of the best cards in the game did — 34 shots in a match, which is
# not football any more.
TIR_PAR_MIN_MAX = 0.40

# What a match has besides shots, per MINUTE OF POSSESSION, set so a whole
# match lands on what football really produces (both sides together):
# about 22 fouls, 10 corners, 4 yellow cards and one red every five
# matches, 4 offsides.  They are drawn from the same minute's dice as the
# rest, so the sheet stays a pure function of the seed.
P_FAUTE = 0.34            # the defending side commits one
P_CARTON = 0.24           # ... and it is a booking
P_ROUGE = 0.004           # ... or, far more rarely, a straight red
P_SECOND_JAUNE = 0.16     # a booked player who fouls again is rarely booked again:
                          # he pulls out of the tackle, or his manager takes him off.
                          # Without this the same well-drilled defender collected a
                          # second yellow in most matches and reds ran at 0.7 a game.
P_CORNER = 0.075          # won in open play
P_CORNER_TIR = 0.28       # after a save or a block
P_HORSJEU = 0.10          # the attacking side is caught
P_BLESSURE = 0.0022       # a player has to come off
MAX_CHANGEMENTS = 5       # substitutions a side may make
FENETRE_CHANGEMENT = 3    # ... in this many stoppages, as the laws have it

# Where the play is, for the pitch that draws it: own third, middle,
# final third, box.  A minute of possession advances by how much the
# attack beats the defence, so a side that is camped reads as camped.
ZONES = 4
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
    return _S.familles_formation(formation)


# What it costs to field a player out of his position — a centre-back at
# left back, a winger up front.  Ten points off every attribute: enough
# that the manager feels it, not so much that a squad with a hole in it
# becomes unplayable.  The eleven is still legal; it is simply worse.
MALUS_HORS_POSTE = 10


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
# A deep block smothers direct play twice over: fewer balls come back, and
# what does is worse.  Quality alone was not enough — the xG multiplier is
# already on its floor (TAC_XG_MIN) in that matchup, so lowering it further
# changed nothing at all and the leg of the cycle was down to +0.04 over
# eight hundred matches.  Taking the shot rate down as well doubles it.
CONTRE = {("possession", "haut"): (0.78, 0.94), ("possession", "bas"): (1.12, 1.0),
          ("direct", "haut"): (1.0, 1.22), ("direct", "bas"): (0.86, 0.78)}


# --------------------------------------------------------------------------
# An eleven, read as a way of playing
# --------------------------------------------------------------------------

@dataclass
class Equipe:
    """`joueurs` = [{pid, nom, fam, poste, ovr, attributs}] — the eleven on
    the pitch, in the order the manager fielded them; `banc` the seven who
    can come on for them."""
    nom: str
    joueurs: list[dict]
    tactique: Tactique = field(default_factory=Tactique)
    banc: list[dict] = field(default_factory=list)
    formation: str = "4-3-3"

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

def _sur_le_terrain(e: Equipe) -> list[dict]:
    return [j for j in e.joueurs]


def _remplacer(sur: list[dict], banc: list[dict], sortant: int, entrant: int) -> dict | None:
    """Swap one card for another, in place.  The player coming on keeps his
    OWN line: taking off a centre-back for a striker really does weaken the
    defence, which is the whole point of making the change."""
    i = next((k for k, j in enumerate(sur) if j["pid"] == sortant), None)
    e = next((j for j in banc if j["pid"] == entrant), None)
    if i is None or e is None:
        return None
    sur[i] = e
    banc.remove(e)
    return {"sortant": sur[i], "entrant": e}


def jouer(a: Equipe, b: Equipe, graine: int, tactiques: dict[int, tuple[Tactique | None, Tactique | None]] | None = None,
          jusqua: int = MINUTES, changements: dict[int, tuple[list, list]] | None = None) -> dict:
    """Play the match minute by minute and return its sheet.

    `tactiques` is the timeline of adjustments: {minute: (tactique A or
    None, tactique B or None)}, applied at the start of that minute.
    `changements` is the same for substitutions: {minute: ([(out, in), ...]
    for A, [...] for B)}, at most MAX_CHANGEMENTS each over
    FENETRE_CHANGEMENT stoppages.  A manager who changes nothing plays his
    kick-off eleven and tactic throughout.  `jusqua` stops the match early,
    which is how the live view advances it.

    The dice of minute m are Random(graine * 1000 + m) and nothing else, so
    the sheet is a pure function of (elevens, seed, tactical and
    substitution timelines): the same match always replays identically, and
    a change acts on the SAME dice rather than drawing new ones.

    Besides the score the sheet carries `fil`, one entry per minute — which
    side has the ball, how far up the pitch, who carries it, which event if
    any.  That is what the 2D pitch animates; it costs ninety small records
    and saves the front-end from inventing a match of its own.
    """
    tactiques = tactiques or {}
    changements = changements or {}
    tac = [a.tactique.valide(), b.tactique.valide()]
    eq = [a, b]
    sur = [_sur_le_terrain(a), _sur_le_terrain(b)]
    banc = [list(a.banc), list(b.banc)]
    t = [traits(sur[0]), traits(sur[1])]
    score = [0, 0]
    tirs, xg_tot, minutes_ballon = [0, 0], [0.0, 0.0], [0, 0]
    fautes, corners, jaunes_n, rouges_n, horsjeux = [0, 0], [0, 0], [0, 0], [0, 0], [0, 0]
    jaunes: list[dict[int, int]] = [{}, {}]
    faits_chg = [0, 0]
    fenetres_chg = [0, 0]
    entres: list[list[int]] = [[], []]      # who has already come on, so the bench knows
    evenements: list[dict] = []
    fil: list[dict] = []

    def ajoute(minute, cote, type_, texte, **extra):
        evenements.append({"minute": minute, "cote": "AB"[cote] if cote is not None else None,
                           "type": type_, "texte": texte} | extra)
        return len(evenements) - 1

    def carton(minute, cote, joueur, rouge=False):
        """A booking, and a second one is a sending off.  A side down to ten
        is read as ten: its traits are recomputed on who is left."""
        if rouge:
            rouges_n[cote] += 1
            sur[cote][:] = [j for j in sur[cote] if j["pid"] != joueur["pid"]]
            t[cote] = traits(sur[cote])
            return ajoute(minute, cote, "rouge", f"{joueur['nom']} est expulsé", pid=joueur["pid"])
        jaunes[cote][joueur["pid"]] = jaunes[cote].get(joueur["pid"], 0) + 1
        jaunes_n[cote] += 1
        return ajoute(minute, cote, "jaune", f"Carton jaune pour {joueur['nom']}", pid=joueur["pid"])

    for m in range(1, min(jusqua, MINUTES) + 1):
        if m in tactiques:
            for c, nouvelle in enumerate(tactiques[m]):
                if nouvelle is not None:
                    tac[c] = nouvelle.valide()
                    ajoute(m, c, "tactique", _texte_tactique(eq[c].nom, tac[c]))
        if m in changements:
            for c, liste in enumerate(changements[m]):
                if not liste or faits_chg[c] >= MAX_CHANGEMENTS or fenetres_chg[c] >= FENETRE_CHANGEMENT:
                    continue
                fait = False
                for sortant, entrant in liste:
                    if faits_chg[c] >= MAX_CHANGEMENTS:
                        break
                    i = next((k for k, j in enumerate(sur[c]) if j["pid"] == sortant), None)
                    e = next((j for j in banc[c] if j["pid"] == entrant), None)
                    if i is None or e is None:
                        continue
                    parti = sur[c][i]
                    sur[c][i] = e
                    banc[c].remove(e)
                    faits_chg[c] += 1
                    fait = True
                    entres[c].append(e["pid"])
                    ajoute(m, c, "changement", f"{e['nom']} remplace {parti['nom']}",
                           pid=e["pid"], sortant=parti["pid"])
                if fait:
                    fenetres_chg[c] += 1
                    t[c] = traits(sur[c])

        rng = random.Random(graine * 1000 + m)
        pa = possession(t[0], t[1], tac[0], tac[1])
        cote = 0 if rng.random() < pa else 1
        adv = 1 - cote
        minutes_ballon[cote] += 1
        r_zone = rng.random()
        p_tir, xg = _chance(t[cote], t[adv], tac[cote], tac[adv])
        r_tir = rng.random()
        porteur = _tireur(sur[cote], rng, "CON") if sur[cote] else None
        evt = None
        zone = 1 + (1 if r_zone < min(0.85, 0.5 * _duel(t[cote]["percussion"], t[adv]["defense"], 1.0)) else 0)

        if r_tir < p_tir:
            zone = 3
            tirs[cote] += 1
            xg_tot[cote] += xg
            tireur = _tireur(sur[cote], rng, "FIN") if sur[cote] else porteur
            porteur = tireur
            conversion = min(XG_MAX, xg * _duel(_z(tireur["attributs"].get("FIN", 40)) + 0.15,
                                                t[adv]["gardien"] + 0.15, EXP_FIN))
            if rng.random() < conversion:
                score[cote] += 1
                autres = [j for j in sur[cote] if j["pid"] != tireur["pid"]]
                passeur = _tireur(autres, rng, "CRE") if autres else tireur
                evt = ajoute(m, cote, "but", f"But de {tireur['nom']}, servi par {passeur['nom']}",
                             pid=tireur["pid"], nom=tireur["nom"], passeur=passeur["nom"],
                             xg=round(xg, 2), score=list(score))
            else:
                gk = next((j for j in sur[adv] if j["fam"] == "GK"), None)
                arret = rng.random() < 0.42 + 0.3 * t[adv]["gardien"]
                r_corner = rng.random()
                if arret and gk:
                    evt = ajoute(m, cote, "arret", f"Arrêt de {gk['nom']} devant {tireur['nom']}",
                                 pid=tireur["pid"], nom=tireur["nom"], gardien=gk["nom"], xg=round(xg, 2))
                elif xg >= XG_NOTABLE:
                    evt = ajoute(m, cote, "occasion", f"{tireur['nom']} manque l'occasion",
                                 pid=tireur["pid"], nom=tireur["nom"], xg=round(xg, 2))
                if r_corner < P_CORNER_TIR:
                    corners[cote] += 1
                    if evt is None:
                        evt = ajoute(m, cote, "corner", f"Corner pour {eq[cote].nom}")
        else:
            r_faute, r_carton, r_corner, r_hj = rng.random(), rng.random(), rng.random(), rng.random()
            if r_faute < P_FAUTE and sur[adv]:
                fautes[adv] += 1
                fauteur = _tireur(sur[adv], rng, "DEF")
                deja = jaunes[adv].get(fauteur["pid"], 0) >= 1
                r_second = rng.random()
                if r_carton < P_ROUGE:
                    evt = carton(m, adv, fauteur, rouge=True)
                elif r_carton < P_CARTON and deja and r_second < P_SECOND_JAUNE:
                    evt = carton(m, adv, fauteur, rouge=True)
                elif r_carton < P_CARTON and not deja:
                    evt = carton(m, adv, fauteur)
                else:
                    evt = ajoute(m, adv, "faute", f"Faute de {fauteur['nom']}", pid=fauteur["pid"])
            elif r_corner < P_CORNER:
                corners[cote] += 1
                zone = 3
                evt = ajoute(m, cote, "corner", f"Corner pour {eq[cote].nom}")
            elif r_hj < P_HORSJEU and porteur is not None:
                horsjeux[cote] += 1
                evt = ajoute(m, cote, "horsjeu", f"{porteur['nom']} est signalé hors-jeu", pid=porteur["pid"])

        if rng.random() < P_BLESSURE:
            c_bless = 0 if rng.random() < 0.5 else 1
            if sur[c_bless]:
                blesse = _tireur(sur[c_bless], rng, "DEF")
                remplacant = next((j for j in banc[c_bless] if j["fam"] == blesse["fam"]), None) \
                    or (banc[c_bless][0] if banc[c_bless] else None)
                if remplacant is not None and faits_chg[c_bless] < MAX_CHANGEMENTS:
                    i = sur[c_bless].index(blesse)
                    sur[c_bless][i] = remplacant
                    banc[c_bless].remove(remplacant)
                    faits_chg[c_bless] += 1
                    entres[c_bless].append(remplacant["pid"])
                    evt = ajoute(m, c_bless, "blessure",
                                 f"{blesse['nom']} sort sur blessure, {remplacant['nom']} entre",
                                 pid=blesse["pid"], entrant=remplacant["pid"])
                else:
                    sur[c_bless][:] = [j for j in sur[c_bless] if j["pid"] != blesse["pid"]]
                    evt = ajoute(m, c_bless, "blessure", f"{blesse['nom']} sort sur blessure",
                                 pid=blesse["pid"])
                t[c_bless] = traits(sur[c_bless])

        fil.append({"m": m, "c": cote, "z": zone,
                    "p": porteur["pid"] if porteur else None, "e": evt})

    fini = jusqua >= MINUTES
    poss = [round(100 * minutes_ballon[0] / max(1, sum(minutes_ballon))),
            round(100 * minutes_ballon[1] / max(1, sum(minutes_ballon)))]
    return {
        "minute": min(jusqua, MINUTES), "fini": fini, "score": score,
        "resultat": ("A" if score[0] > score[1] else "B" if score[1] > score[0] else "N") if fini else None,
        "possession": poss, "tirs": tirs, "xg": [round(x, 2) for x in xg_tot],
        "fautes": fautes, "corners": corners, "jaunes": jaunes_n, "rouges": rouges_n,
        "horsjeu": horsjeux, "changements": faits_chg,
        "entres": {"a": entres[0], "b": entres[1]},
        "evenements": evenements, "fil": fil,
        "onze": {"a": [j["pid"] for j in sur[0]], "b": [j["pid"] for j in sur[1]]},
        "traits": {"a": {k: round(v, 3) for k, v in t[0].items()}, "b": {k: round(v, 3) for k, v in t[1].items()}},
        "tactique": {"a": vars(tac[0]), "b": vars(tac[1])},
        "graine": graine,
    }


_MOTS = {"possession": "garde le ballon", "direct": "joue direct", "equilibre": "revient à l'équilibre",
         "haut": "monte son bloc", "median": "replace son bloc", "bas": "descend son bloc",
         "offensif": "prend des risques", "prudent": "ferme le jeu"}


def _texte_tactique(nom: str, t: Tactique) -> str:
    return f"{nom} : {_MOTS.get(t.tempo, t.tempo)}, {_MOTS.get(t.bloc, t.bloc)}, {_MOTS.get(t.risque, t.risque)}"


# The median of each trait over a real card pool — the 150 club elevens of
# the eight leagues — and how much of a gap counts as a trait worth naming.
REPERE = {"controle": 0.416, "percussion": 0.352, "creation": 0.429,
          "finition": 0.511, "defense": 0.406, "gardien": 0.319}
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

def onze_depuis_cartes(jeu, saison: str, pids: list[int], nom: str = "Équipe",
                       postes_slots: list[str] | None = None) -> Equipe:
    """Build an eleven from the game base's cards.

    `postes_slots` is the formation's position for each slot.  A card
    fielded away from a position it really held keeps its line but loses
    MALUS_HORS_POSTE on every attribute: a centre-back at left back is a
    worse left back, and the manager should see it in the match rather
    than only in a warning.
    """
    import json
    from jeu import scoring as S
    joueurs = []
    for i, pid in enumerate(pids):
        row = jeu.execute("""SELECT j.nom, j.poste, c.ovr, c.attributs, j.postes FROM carte c
                             JOIN joueur j ON j.player_id = c.player_id
                             WHERE c.player_id = ? AND c.saison = ?""", (pid, saison)).fetchone()
        if not row:
            continue
        nom_j, poste, ovr, attrs, postes = row
        tenus = json.loads(postes) if postes else [poste]
        attributs = json.loads(attrs or "{}")
        slot = postes_slots[i] if postes_slots and i < len(postes_slots) else None
        dehors = bool(slot) and S.hors_poste(tenus, slot)
        if dehors:
            attributs = {k: max(40, v - MALUS_HORS_POSTE) for k, v in attributs.items()}
        fam = S.FAMILLE_POSTE.get(slot or poste, S.FAMILLE_POSTE.get(poste, "MID"))
        joueurs.append({"pid": pid, "nom": nom_j, "poste": poste, "fam": fam, "ovr": ovr,
                        "attributs": attributs, "slot": slot, "hors_poste": dehors})
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

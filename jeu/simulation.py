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

# --------------------------------------------------------------------------
# Stamina
# --------------------------------------------------------------------------
# A card has no physical attribute — nothing in the real data says who can
# run for ninety minutes — so the wear is the same for everyone, modulated
# by the line he plays in and by how his manager makes him play: pressing
# high and going direct cost legs, keeping the ball and sitting deep save
# them.  A midfielder ends a normal match around 45, a keeper barely tired.
ENDURANCE_MAX = 100.0
USURE_BASE = 0.52             # stamina points lost per minute on the pitch
USURE_FAM = {"GK": 0.22, "DEF": 0.92, "MID": 1.12, "FWD": 1.02}
USURE_TEMPO = {"possession": 0.90, "equilibre": 1.0, "direct": 1.08}
USURE_BLOC = {"haut": 1.12, "median": 1.0, "bas": 0.90}
USURE_RISQUE = {"offensif": 1.06, "equilibre": 1.0, "prudent": 0.95}
# What being empty costs: at zero a player is worth 88 % of himself.
# Enough that the last half-hour is a real decision — take him off or live
# with it — and never enough to turn a good card into a bad one on the
# clock alone.  It applies to BOTH sides, so it does not move the match
# averages; it moves WHO is on the pitch at the eightieth minute.
COUT_FATIGUE = 0.12


# --------------------------------------------------------------------------
# Le profil d'un joueur, et son aise dans la tactique qu'on lui demande
# --------------------------------------------------------------------------
# Un joueur n'est pas également à l'aise partout.  Vitinha s'épanouit dans
# une équipe qui garde le ballon ; Nuno Mendes veut déborder, pas rester
# derrière.  Le jeu ne l'étiquette nulle part à la main : il le LIT dans
# la carte, qui elle-même vient de ce que le joueur a vraiment fait.
#
# Deux normalisations, et elles comptent toutes les deux :
#
#  1. contre SA LIGNE.  Un défenseur central défend mieux qu'un attaquant :
#     sans ça, tout défenseur passerait pour un amoureux du bloc bas.  Ce
#     qui nous intéresse, c'est un latéral qui progresse plus que LES
#     AUTRES LATÉRAUX.
#  2. contre LUI-MÊME.  Sinon un joueur élite, au-dessus de la médiane sur
#     tous les axes, serait à l'aise dans toutes les tactiques à la fois —
#     et l'aise deviendrait un bonus offert aux gros effectifs.  Le profil
#     mesure donc une FORME, pas un niveau : il fait zéro en moyenne sur
#     les six axes.  Un joueur complet n'a de profil nulle part, ce qui est
#     exactement ce qu'on veut dire de lui.
#
# Médianes et écarts-types mesurés sur les 3 541 cartes de champ des huit
# championnats (1 446 défenseurs, 894 milieux, 1 201 attaquants).
PROFIL_REPERE = {
    "DEF": {"CON": (68, 6.2), "CRE": (48, 9.4), "DEF": (71, 7.7), "DRI": (49, 7.8), "FIN": (49, 5.4), "PRO": (64, 6.3)},
    "MID": {"CON": (59, 6.1), "CRE": (60, 7.8), "DEF": (57, 5.6), "DRI": (61, 6.1), "FIN": (58, 5.9), "PRO": (66, 7.1)},
    "FWD": {"CON": (46, 4.3), "CRE": (72, 7.9), "DEF": (45, 4.1), "DRI": (71, 5.4), "FIN": (72, 6.1), "PRO": (46, 5.0)},
}
# Le gardien en est exclu : ses axes (ARR, EVI, SOR, REL) ne sont pas ceux
# du champ, et aucun réglage tactique ne lui demande autre chose que de
# garder son but.
AXES_PROFIL = ("CON", "CRE", "DEF", "DRI", "FIN", "PRO")


def profil(attributs: dict, fam: str) -> dict[str, float]:
    """La forme d'un joueur : sur quels axes il sort DE SA LIGNE, et de
    combien, une fois son niveau général retiré.  Somme nulle."""
    rep = PROFIL_REPERE.get(fam)
    if not rep:
        return {}
    z = {k: (attributs.get(k, 40) - rep[k][0]) / rep[k][1] for k in AXES_PROFIL if k in rep}
    if not z:
        return {}
    moyen = sum(z.values()) / len(z)
    return {k: v - moyen for k, v in z.items()}


# Ce qu'un réglage demande à un joueur.  Chaque pôle d'un axe appelle des
# qualités DIFFÉRENTES de l'autre, sinon le réglage ne distinguerait
# personne ; et le réglage neutre de chaque axe n'appelle rien du tout.
#
#   axe -> {choix: (axes de la carte appelés, postes concernés ou None
#                   pour tout le monde)}
AFFINITES = {
    "tempo": {"possession": (("CON", "CRE"), None), "direct": (("PRO", "FIN"), None)},
    # Presser haut, c'est défendre dans le camp d'en face, avec de
    # l'espace derrière : il faut progresser et gagner ses duels haut.
    # Défendre bas, c'est défendre sa surface et ne pas la redonner.
    "bloc": {"haut": (("PRO", "DRI"), None), "bas": (("DEF", "CON"), None)},
    # `prudent` n'appelle rien : fermer le match réduit le VOLUME des
    # occasions des deux côtés, ça ne demande pas d'autres qualités — et
    # écrit (DEF, CON), c'était mot pour mot le bloc bas, deux décisions
    # différentes qui se lisaient pareil.  Ouvrir le match, si : il faut
    # des joueurs qui vivent dans le désordre.
    "risque": {"offensif": (("DRI", "FIN"), None)},
    # Pas de "couloir" ici : c'est le réglage PAR DÉFAUT des latéraux,
    # donc le réglage neutre, et un défaut ne rend personne plus à l'aise.
    "lateraux": {"bas": (("DEF", "CON"), ("Lateral",)),
                 "axe": (("CON", "CRE"), ("Lateral",))},
    "ailiers": {"ligne": (("DRI", "PRO"), ("Ailier", "Ailier droit", "Ailier gauche")),
                "interieur": (("FIN", "CRE"), ("Ailier", "Ailier droit", "Ailier gauche"))},
    "milieux": {"bas": (("DEF", "CON"), ("Milieu defensif", "Milieu relayeur", "Milieu offensif")),
                "projection": (("PRO", "FIN"), ("Milieu defensif", "Milieu relayeur", "Milieu offensif")),
                "lateral": (("CRE", "PRO"), ("Milieu defensif", "Milieu relayeur", "Milieu offensif"))},
    "attaquants": {"profondeur": (("PRO", "DRI"), ("Buteur",)),
                   "pivot": (("CON", "CRE"), ("Buteur",))},
    "relance": {"courte": (("CON", "CRE"), ("Defenseur central",)),
                "longue": (("PRO", "FIN"), ("Defenseur central",))},
}
# Ce que vaut une aise parfaite : 10 % sur les attributs du joueur, soit
# environ trois points de carte sur un attribut à 70 — un tiers du malus
# de hors-poste.  Mesuré sur quatorze onzes de vrais clubs, le même
# réglage joué avec et sans l'aise : celui qui va à l'équipe rapporte
# +0,107 but par match, celui qui la dessert en coûte 0,071, soit 0,18
# but entre le bon choix et le mauvais — du même ordre qu'un axe
# tactique.  À 6 % l'écart tombait à 0,09 but, trop peu pour valoir une
# décision.
AISE_MAX = 0.10
AISE_Z = 1.3         # l'écart-type de profil à partir duquel c'est au maximum
# Ce qu'un ONZE entier peut gagner à être bien servi : 2 %, pas plus.
#
# C'est une GARANTIE, pas un correctif : mesuré sur 435 matchs entre
# vrais clubs, à tactiques identiques des deux côtés, l'aise déplace le
# football de 1,96 à 1,98 but par camp — deux centièmes, autant dire
# rien, et le plafond ne change pas ce chiffre.  Ce qu'il assure, c'est
# qu'aucun effectif, même taillé exprès, ne pourra transformer une bonne
# lecture tactique en avantage collectif : la lecture doit se payer en
# choix (le réglage qui flatte tes joueurs n'est pas forcément celui qui
# contre l'adversaire), jamais en niveau offert.
#
# Seul l'EXCÈS au-dessus du plafond est repris, et à tout le monde
# également : qui est flatté et qui est desservi DANS l'équipe ne change
# pas d'un iota, et c'est là que se joue la lecture d'un effectif.  Une
# tactique qui dessert son équipe, elle, garde son coût entier — bien
# lire rapporte peu, mal lire coûte cher.
AISE_EQUIPE_MAX = 0.02


# Comment se dit chaque réglage, pour la fiche d'un joueur.
LIBELLE_AFFINITE = {
    ("tempo", "possession"): "une équipe qui garde le ballon",
    ("tempo", "direct"): "une équipe qui joue direct",
    ("bloc", "haut"): "un bloc haut",
    ("bloc", "bas"): "un bloc bas",
    ("risque", "offensif"): "un match ouvert",
    ("lateraux", "bas"): "rester derrière",
    ("lateraux", "axe"): "rentrer dans l'axe",
    ("ailiers", "ligne"): "coller la ligne de touche",
    ("ailiers", "interieur"): "repiquer dans l'axe",
    ("milieux", "bas"): "rester bas",
    ("milieux", "projection"): "se projeter dans la surface",
    ("milieux", "lateral"): "décaler le jeu",
    ("attaquants", "profondeur"): "chercher la profondeur",
    ("attaquants", "pivot"): "jouer en pivot",
    ("relance", "courte"): "ressortir par le bas",
    ("relance", "longue"): "le jeu long",
}
ECART_AISE = 0.35    # en deçà, un joueur n'a pas de préférence à afficher


def lecture_profil(attributs: dict, fam: str, slot: str | None = None, combien: int = 2) -> dict:
    """Ce qu'on écrit sur la fiche : où ce joueur est chez lui, et où non.

    Rien n'est étiqueté à la main.  C'est la carte qui parle, et la carte
    vient de ce que le joueur a vraiment fait sur un terrain."""
    pr = profil(attributs, fam)
    if not pr:
        return {"axes": {}, "aise": [], "gene": []}
    faux = {"slot": slot, "poste": slot, "profil": pr}
    scores = []
    for axe, options in AFFINITES.items():
        for choix in options:
            v = affinite(faux, Tactique(**{axe: choix}).valide())
            if v:
                scores.append({"cle": f"{axe}:{choix}",
                               "texte": LIBELLE_AFFINITE.get((axe, choix), choix),
                               "score": round(v, 2)})
    scores.sort(key=lambda x: -x["score"])
    return {"axes": {k: round(v, 2) for k, v in pr.items()},
            "aise": [x for x in scores[:combien] if x["score"] >= ECART_AISE],
            "gene": [x for x in scores[-combien:] if x["score"] <= -ECART_AISE][::-1]}


def affinite(j: dict, tac: "Tactique") -> float:
    """De combien un joueur est chez lui dans ce qu'on lui demande, en
    écarts-types de profil.  La MOYENNE des réglages non neutres qui le
    concernent : des consignes cohérentes entre elles s'additionnent
    naturellement, des consignes qui se contredisent s'annulent."""
    pr = j.get("profil")
    if not pr:
        return 0.0
    slot = j.get("slot") or j.get("poste")
    scores = []
    for axe, choix in AFFINITES.items():
        appel = choix.get(getattr(tac, axe, None))
        if appel is None:
            continue                          # réglage neutre : il ne demande rien
        axes, postes = appel
        if postes is not None and slot not in postes:
            continue                          # cette consigne ne le concerne pas
        vals = [pr[k] for k in axes if k in pr]
        if vals:
            scores.append(sum(vals) / len(vals))
    return sum(scores) / len(scores) if scores else 0.0


def aise(j: dict, tac: "Tactique") -> float:
    """Le multiplicateur d'un joueur dans la tactique du moment."""
    return 1.0 + AISE_MAX * max(-1.0, min(1.0, affinite(j, tac) / AISE_Z))


def _forme(j: dict) -> float:
    """A player's fatigue multiplier, 1.0 when fresh."""
    e = j.get("endurance", ENDURANCE_MAX)
    return 1.0 - COUT_FATIGUE * (1.0 - max(0.0, min(1.0, e / ENDURANCE_MAX)))


def usure(j: dict, tac: "Tactique") -> float:
    """Stamina a player burns in one minute, given how his side plays."""
    return (USURE_BASE * USURE_FAM.get(j.get("fam"), 1.0) * USURE_TEMPO.get(tac.tempo, 1.0)
            * USURE_BLOC.get(tac.bloc, 1.0) * USURE_RISQUE.get(tac.risque, 1.0))


def _z(attr: int) -> float:
    """A card attribute (40-99) on 0-1."""
    return max(0.0, min(1.0, (attr - 40) / 59.0))


def _moyenne(joueurs: list[dict], familles: tuple[str, ...], axes: tuple[str, ...]) -> float:
    """Mean of `axes` over the players of those lines, 0-1.  An empty line
    reads as a weak one rather than as nothing."""
    vals = [_z(j["attributs"].get(ax, 40)) * _forme(j) * j.get("aise", 1.0)
            for j in joueurs if j["fam"] in familles for ax in axes]
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
    # The shape, changed like any other setting: an empty string means
    # "whatever the eleven kicked off in", so an old stored tactic and a
    # manager who never touches it both keep their formation.
    formation: str = ""
    # What each line is asked to do (CONSIGNES).  Every default is
    # neutral, so a stored tactic written before they existed reads as a
    # manager who has not touched them.
    lateraux: str = "couloir"
    ailiers: str = "equilibre"
    milieux: str = "equilibre"
    attaquants: str = "equilibre"
    relance: str = "equilibre"

    def valide(self) -> "Tactique":
        t = self.tempo if self.tempo in TEMPO else "equilibre"
        b = self.bloc if self.bloc in BLOC else "median"
        r = self.risque if self.risque in RISQUE else "equilibre"
        f = self.formation if self.formation in _S.FORMATIONS_RANGS else ""
        c = {axe: (getattr(self, axe) if getattr(self, axe, None) in opts else CONSIGNE_DEFAUT[axe])
             for axe, opts in CONSIGNES.items()}
        return Tactique(t, b, r, f, **c)


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

# --------------------------------------------------------------------------
# Player instructions — what you ask of a LINE, not of the team
# --------------------------------------------------------------------------
# The three axes above say how the team plays.  These say what each line
# is asked to do inside it, in the vocabulary a manager actually uses:
# a full-back who stays home or overlaps or tucks into midfield, a winger
# who hugs the touchline or cuts inside, midfielders who join the attack
# or sit, forwards who run in behind or hold it up, a back line that
# plays out or goes long.
#
# The same rule as everywhere else: NONE of them is a bonus.  Each one
# moves two or three team traits, one up and one down, and the default of
# every axis is neutral — a manager who touches nothing plays exactly the
# match the engine is calibrated on.  They are deliberately smaller than
# the three main axes: an instruction is a nuance, not a second tactic.
CONSIGNES: dict[str, dict[str, dict[str, float]]] = {
    # Les latéraux
    "lateraux": {
        "couloir": {},                                              # il monte dans son couloir
        "bas": {"defense": 1.07, "percussion": 0.93},               # il reste derrière
        "axe": {"controle": 1.07, "defense": 0.95},                 # il rentre dans l'axe
    },
    # Les ailiers
    "ailiers": {
        "equilibre": {},
        "ligne": {"percussion": 1.08, "creation": 0.94},            # il colle la ligne de touche
        "interieur": {"creation": 1.11, "finition": 1.07, "percussion": 0.94},   # il repique
    },
    # Les milieux
    "milieux": {
        "equilibre": {},
        "projection": {"percussion": 1.10, "defense": 0.945},       # il rejoint l'attaque
        "bas": {"defense": 1.06, "controle": 1.03, "percussion": 0.92},          # il reste derrière
        "lateral": {"creation": 1.11, "controle": 0.97},            # il organise sur les côtés
    },
    # Les attaquants
    "attaquants": {
        "equilibre": {},
        "profondeur": {"percussion": 1.09, "creation": 0.93},       # il cherche la profondeur
        "pivot": {"controle": 1.06, "creation": 1.04, "percussion": 0.92},       # il joue dos au but
    },
    # La relance de la défense
    "relance": {
        "equilibre": {},
        "courte": {"controle": 1.08, "defense": 0.94},              # on ressort par le bas
        "longue": {"percussion": 1.07, "defense": 1.03, "controle": 0.95},       # on joue long
    },
}
CONSIGNE_DEFAUT = {axe: next(iter(opts)) for axe, opts in CONSIGNES.items()}
# Cinq consignes qui vont toutes dans le même sens ne font pas une équipe
# deux fois meilleure sur un trait : le produit est borné.
CONSIGNE_MIN, CONSIGNE_MAX = 0.88, 1.12


def appliquer_consignes(t: dict[str, float], tac: "Tactique") -> dict[str, float]:
    """The six traits as the instructions leave them."""
    facteurs: dict[str, float] = {}
    for axe in CONSIGNES:
        choix = getattr(tac, axe, None)
        for cle, m in CONSIGNES[axe].get(choix, {}).items():
            facteurs[cle] = facteurs.get(cle, 1.0) * m
    if not facteurs:
        return t
    return {k: max(0.0, min(1.0, v * max(CONSIGNE_MIN, min(CONSIGNE_MAX, facteurs.get(k, 1.0)))))
            for k, v in t.items()}


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
        "gardien": ((_z(gardien[0]["attributs"].get("ARR", 40)) * 0.6
                     + _z(gardien[0]["attributs"].get("EVI", 40)) * 0.4)
                    * _forme(gardien[0])) if gardien else 0.25,
    }


def appliquer_formation(joueurs: list[dict], formation: str) -> None:
    """Re-assign an eleven's slots to another shape, in place.

    Nobody comes off: what changes is the position each player is asked to
    fill, so the out-of-position penalty is recomputed from the raw card.
    Going from 4-3-3 to 3-5-2 turns a full-back into a wing-back — which
    he may well have held — and a winger into a second striker, which he
    probably has not.  The eleven is REDISTRIBUTED over the new slots by
    the same rule as the "best eleven" button (scoring.repartir): filling
    the shape slot by slot in the kick-off order would have sent the
    second full-back of a 4-3-3 into midfield just because he stood
    fourth, when a real manager moves the men who fit.
    """
    postes = _S.postes_formation(formation)
    ordre = _S.repartir([j.get("tenus") or [j.get("poste")] for j in joueurs], formation)
    reste = [j for k, j in enumerate(joueurs) if k not in set(ordre)]
    joueurs[:] = [joueurs[k] for k in ordre] + reste
    for i, j in enumerate(joueurs):
        if i < len(postes):
            _poser(j, postes[i])


def _poser(j: dict, slot: str) -> None:
    """Put one player in one slot, penalty and line recomputed."""
    brut = j.get("attributs_bruts") or j.get("attributs") or {}
    j["attributs_bruts"] = dict(brut)
    tenus = j.get("tenus") or ([j["poste"]] if j.get("poste") else [])
    dehors = bool(slot) and _S.hors_poste(tenus, slot)
    j["slot"] = slot
    j["hors_poste"] = dehors
    j["attributs"] = ({k: max(40, v - MALUS_HORS_POSTE) for k, v in brut.items()}
                      if dehors else dict(brut))
    j["fam"] = _S.FAMILLE_POSTE.get(slot, j.get("fam", "MID"))
    j["profil"] = profil(j["attributs"], j["fam"])


def poser_aise(joueurs: list[dict], tac: "Tactique") -> None:
    """Écrire sur chaque joueur son aise, le gain d'équipe plafonné."""
    if not joueurs:
        return
    brut = [aise(j, tac) for j in joueurs]
    exces = max(0.0, sum(brut) / len(brut) - (1.0 + AISE_EQUIPE_MAX))
    for j, v in zip(joueurs, brut):
        j["aise"] = v - exces


def traits_diriges(joueurs: list[dict], tac: "Tactique") -> dict[str, float]:
    """An eleven's six traits, instructions included.

    The only reading the match uses: the cards say what the eleven is,
    the instructions say what it is being asked to do — and how much each
    player is at home in it."""
    poser_aise(joueurs, tac)
    return appliquer_consignes(traits(joueurs), tac)


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
    # A copy: the match writes stamina onto the players it plays, and an
    # Equipe must be replayable — the live sheet rebuilds the same match
    # from minute one on every poll.
    return [dict(j) for j in e.joueurs]


# --------------------------------------------------------------------------
# What a minute LOOKS like
# --------------------------------------------------------------------------
# The dice above decide what HAPPENS in a minute; nothing below changes
# it.  What this builds is how that outcome is reached — who plays the
# ball out, through whom it goes, where it is lost, where the whistle
# goes — so the pitch can show a build-up and a shot leaving a boot
# instead of a card sliding forward.
#
# It draws from its OWN generator, seeded apart from the match's, for one
# reason: adding a touch must never move a goal.  The sequence is still a
# pure function of the seed and the minute, so a match replays down to
# the pass that preceded the goal.
ARRETS_DE_JEU = ("faute", "horsjeu", "but", "blessure", "carton")


def _un(rs: random.Random, joueurs: list[dict], *familles: str) -> dict | None:
    """One player of those lines, or of the eleven if that line is empty."""
    cands = [j for j in joueurs if j["fam"] in familles] or joueurs
    return rs.choice(cands) if cands else None


def _pas(kind: str, j: dict | None, cote: int, zone: int, **extra) -> dict | None:
    if j is None:
        return None
    return {"k": kind, "p": j["pid"], "c": cote, "z": zone} | extra


def _construction(rs: random.Random, joueurs: list[dict], cote: int, jusqua: int) -> list[dict]:
    """The build-up: two to four touches, from the back towards `jusqua`."""
    out = []
    if joueurs and rs.random() < 0.30:
        out.append(_pas("relance", _un(rs, joueurs, "GK"), cote, 0))
    out = [x for x in out if x]
    out.append(_pas("passe" if out else "relance", _un(rs, joueurs, "DEF"), cote, 1))
    out.append(_pas("passe", _un(rs, joueurs, "MID"), cote, min(2, max(1, jusqua))))
    if jusqua >= 2 and rs.random() < 0.55:
        out.append(_pas("passe", _un(rs, joueurs, "MID", "FWD"), cote, 2))
    return [x for x in out if x]


def sequence(rs: random.Random, sur: list[list[dict]], cote: int, zone: int, issue: dict) -> list[dict]:
    """The phases of one minute, in the order they are played."""
    adv = 1 - cote
    q = issue.get("quoi", "rien")
    pas = _construction(rs, sur[cote], cote, zone)
    tireur, gk = issue.get("tireur"), issue.get("gardien")

    if q in ("but", "arret", "rate"):
        if tireur is not None:
            pas.append(_pas("conduite", tireur, cote, 3))
            # where he aims: the posts more often than the middle
            cible = round(rs.choice([0.12, 0.22, 0.5, 0.78, 0.88]) + rs.uniform(-0.05, 0.05), 3)
            pas.append(_pas("tir", tireur, cote, 3, t=max(0.05, min(0.95, cible))))
        if q == "but":
            pas.append(_pas("but", tireur, cote, 3, o=issue.get("passeur", {}).get("pid")
                            if isinstance(issue.get("passeur"), dict) else None))
            pas.append(_pas("engagement", _un(rs, sur[adv], "MID"), adv, 1))
        elif q == "arret":
            pas.append(_pas("arret", gk, adv, 0))
        else:
            pas.append(_pas("rate", tireur, cote, 3))
            pas.append(_pas("degagement", _un(rs, sur[adv], "GK"), adv, 0))
    elif q == "faute":
        fauteur = issue.get("fauteur")
        pas.append(_pas("duel", fauteur, adv, zone))
        pas.append(_pas("faute", fauteur, adv, zone))
        if issue.get("carton"):
            pas.append(_pas("carton", fauteur, adv, zone, r=bool(issue.get("rouge"))))
        pas.append(_pas("coupfranc", _un(rs, sur[cote], "MID", "DEF"), cote, zone))
    elif q == "horsjeu":
        pas.append(_pas("horsjeu", issue.get("porteur"), cote, 3))
        pas.append(_pas("degagement", _un(rs, sur[adv], "GK"), adv, 0))
    elif q == "corner":
        pass                                  # the corner block below adds it
    else:
        pas.append(_pas("perte", _un(rs, sur[adv], "DEF", "MID"), adv, zone))

    if issue.get("corner"):
        pas.append(_pas("corner", _un(rs, sur[cote], "MID", "FWD"), cote, 3))
        pas.append(_pas("centre", _un(rs, sur[cote], "DEF", "FWD"), cote, 3))
        pas.append(_pas("degagement", _un(rs, sur[adv], "DEF"), adv, 3))
    if issue.get("blesse") is not None:
        pas.append(_pas("blessure", issue["blesse"], issue.get("cote_blesse", cote), zone))
    return [x for x in pas if x]


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
          jusqua: int = MINUTES, changements: dict[int, tuple[list, list]] | None = None,
          auto_remplacement: tuple[bool, bool] = (True, True)) -> dict:
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
    any, and `s`, the PHASES of that minute: the touches of the build-up,
    the shot, the whistle, the turnover.  That is what the 2D pitch
    animates; it costs ninety small records and saves the front-end from
    inventing a match of its own.

    `auto_remplacement` says, side by side, whether the machine replaces an
    injured player on its own.  A side a human manages is left a man short
    and the sheet reports it (`attente`): the screen stops and asks him who
    comes on, which is what a manager would actually have to decide.
    """
    tactiques = tactiques or {}
    changements = changements or {}
    tac = [a.tactique.valide(), b.tactique.valide()]
    eq = [a, b]
    sur = [_sur_le_terrain(a), _sur_le_terrain(b)]
    banc = [[dict(j) for j in a.banc], [dict(j) for j in b.banc]]
    forme = [a.formation, b.formation]
    for c in (0, 1):
        for j in sur[c] + banc[c]:
            j.setdefault("endurance", ENDURANCE_MAX)
        if tac[c].formation and tac[c].formation != forme[c]:
            forme[c] = tac[c].formation
            appliquer_formation(sur[c], forme[c])
    t = [traits_diriges(sur[0], tac[0]), traits_diriges(sur[1], tac[1])]
    blesses: list[list[int]] = [[], []]    # off injured, nobody on for them yet
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
            t[cote] = traits_diriges(sur[cote], tac[cote])
            return ajoute(minute, cote, "rouge", f"{joueur['nom']} est expulsé", pid=joueur["pid"])
        jaunes[cote][joueur["pid"]] = jaunes[cote].get(joueur["pid"], 0) + 1
        jaunes_n[cote] += 1
        return ajoute(minute, cote, "jaune", f"Carton jaune pour {joueur['nom']}", pid=joueur["pid"])

    for m in range(1, min(jusqua, MINUTES) + 1):
        if m in tactiques:
            for c, nouvelle in enumerate(tactiques[m]):
                if nouvelle is not None:
                    tac[c] = nouvelle.valide()
                    if tac[c].formation and tac[c].formation != forme[c]:
                        forme[c] = tac[c].formation
                        appliquer_formation(sur[c], forme[c])
                        ajoute(m, c, "formation", f"{eq[c].nom} passe en {forme[c]}")
                    t[c] = traits_diriges(sur[c], tac[c])
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
                    if e is None:
                        continue
                    if i is None:
                        # the man he replaces is already off injured: the
                        # side goes back up to eleven rather than staying
                        # a man short for the rest of the match.
                        if sortant not in blesses[c]:
                            continue
                        blesses[c].remove(sortant)
                        parti = {"nom": "le blessé", "slot": None}
                        sur[c].append(e)
                    else:
                        parti = sur[c][i]
                        sur[c][i] = e
                    banc[c].remove(e)
                    if parti.get("slot"):
                        _poser(e, parti["slot"])
                    faits_chg[c] += 1
                    fait = True
                    entres[c].append(e["pid"])
                    ajoute(m, c, "changement", f"{e['nom']} remplace {parti['nom']}",
                           pid=e["pid"], sortant=parti.get("pid"))
                if fait:
                    fenetres_chg[c] += 1
                    t[c] = traits_diriges(sur[c], tac[c])

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
        issue: dict = {"quoi": "rien", "porteur": porteur}
        zone = 1 + (1 if r_zone < min(0.85, 0.5 * _duel(t[cote]["percussion"], t[adv]["defense"], 1.0)) else 0)

        if r_tir < p_tir:
            zone = 3
            tirs[cote] += 1
            xg_tot[cote] += xg
            tireur = _tireur(sur[cote], rng, "FIN") if sur[cote] else porteur
            porteur = tireur
            conversion = min(XG_MAX, xg * _duel(_z(tireur["attributs"].get("FIN", 40)) + 0.15,
                                                t[adv]["gardien"] + 0.15, EXP_FIN))
            issue.update({"quoi": "rate", "tireur": tireur})
            if rng.random() < conversion:
                score[cote] += 1
                autres = [j for j in sur[cote] if j["pid"] != tireur["pid"]]
                passeur = _tireur(autres, rng, "CRE") if autres else tireur
                issue.update({"quoi": "but", "passeur": passeur})
                evt = ajoute(m, cote, "but", f"But de {tireur['nom']}, servi par {passeur['nom']}",
                             pid=tireur["pid"], nom=tireur["nom"], passeur=passeur["nom"],
                             xg=round(xg, 2), score=list(score))
            else:
                gk = next((j for j in sur[adv] if j["fam"] == "GK"), None)
                arret = rng.random() < 0.42 + 0.3 * t[adv]["gardien"]
                r_corner = rng.random()
                if arret and gk:
                    issue.update({"quoi": "arret", "gardien": gk})
                    evt = ajoute(m, cote, "arret", f"Arrêt de {gk['nom']} devant {tireur['nom']}",
                                 pid=tireur["pid"], nom=tireur["nom"], gardien=gk["nom"], xg=round(xg, 2))
                elif xg >= XG_NOTABLE:
                    evt = ajoute(m, cote, "occasion", f"{tireur['nom']} manque l'occasion",
                                 pid=tireur["pid"], nom=tireur["nom"], xg=round(xg, 2))
                if r_corner < P_CORNER_TIR:
                    corners[cote] += 1
                    issue["corner"] = True
                    if evt is None:
                        evt = ajoute(m, cote, "corner", f"Corner pour {eq[cote].nom}")
        else:
            r_faute, r_carton, r_corner, r_hj = rng.random(), rng.random(), rng.random(), rng.random()
            if r_faute < P_FAUTE and sur[adv]:
                fautes[adv] += 1
                fauteur = _tireur(sur[adv], rng, "DEF")
                deja = jaunes[adv].get(fauteur["pid"], 0) >= 1
                r_second = rng.random()
                issue.update({"quoi": "faute", "fauteur": fauteur})
                if r_carton < P_ROUGE:
                    issue.update({"carton": True, "rouge": True})
                    evt = carton(m, adv, fauteur, rouge=True)
                elif r_carton < P_CARTON and deja and r_second < P_SECOND_JAUNE:
                    issue.update({"carton": True, "rouge": True})
                    evt = carton(m, adv, fauteur, rouge=True)
                elif r_carton < P_CARTON and not deja:
                    issue["carton"] = True
                    evt = carton(m, adv, fauteur)
                else:
                    evt = ajoute(m, adv, "faute", f"Faute de {fauteur['nom']}", pid=fauteur["pid"])
            elif r_corner < P_CORNER:
                corners[cote] += 1
                zone = 3
                issue.update({"quoi": "corner", "corner": True})
                evt = ajoute(m, cote, "corner", f"Corner pour {eq[cote].nom}")
            elif r_hj < P_HORSJEU and porteur is not None:
                horsjeux[cote] += 1
                issue["quoi"] = "horsjeu"
                evt = ajoute(m, cote, "horsjeu", f"{porteur['nom']} est signalé hors-jeu", pid=porteur["pid"])

        if rng.random() < P_BLESSURE:
            c_bless = 0 if rng.random() < 0.5 else 1
            if sur[c_bless]:
                blesse = _tireur(sur[c_bless], rng, "DEF")
                remplacant = next((j for j in banc[c_bless] if j["fam"] == blesse["fam"]), None) \
                    or (banc[c_bless][0] if banc[c_bless] else None)
                issue["blesse"] = blesse
                issue["cote_blesse"] = c_bless
                sortant_slot = blesse.get("slot")
                auto = auto_remplacement[c_bless] if c_bless < len(auto_remplacement) else True
                if auto and remplacant is not None and faits_chg[c_bless] < MAX_CHANGEMENTS:
                    i = sur[c_bless].index(blesse)
                    sur[c_bless][i] = remplacant
                    banc[c_bless].remove(remplacant)
                    if sortant_slot:
                        _poser(remplacant, sortant_slot)
                    faits_chg[c_bless] += 1
                    entres[c_bless].append(remplacant["pid"])
                    evt = ajoute(m, c_bless, "blessure",
                                 f"{blesse['nom']} sort sur blessure, {remplacant['nom']} entre",
                                 pid=blesse["pid"], entrant=remplacant["pid"])
                else:
                    # A side its manager runs himself is left a man short:
                    # the sheet says so, the screen stops the match and
                    # asks him who comes on.  Football does not substitute
                    # an injured player by itself either.
                    sur[c_bless][:] = [j for j in sur[c_bless] if j["pid"] != blesse["pid"]]
                    if banc[c_bless] and faits_chg[c_bless] < MAX_CHANGEMENTS:
                        blesses[c_bless].append(blesse["pid"])
                    evt = ajoute(m, c_bless, "blessure", f"{blesse['nom']} sort sur blessure",
                                 pid=blesse["pid"], slot=sortant_slot)
                t[c_bless] = traits_diriges(sur[c_bless], tac[c_bless])

        # The legs.  Everyone on the pitch loses a little of the minute,
        # each side at the cost of the way its manager makes it play, and
        # the traits are read again from tired players.
        for c in (0, 1):
            for j in sur[c]:
                j["endurance"] = max(0.0, j.get("endurance", ENDURANCE_MAX) - usure(j, tac[c]))
            t[c] = traits_diriges(sur[c], tac[c])

        rs = random.Random(graine * 1000 + m + 7_000_003)
        fil.append({"m": m, "c": cote, "z": zone,
                    "p": porteur["pid"] if porteur else None, "e": evt,
                    "s": sequence(rs, sur, cote, zone, issue)})

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
        "endurance": {"a": {j["pid"]: round(j.get("endurance", ENDURANCE_MAX)) for j in sur[0]},
                      "b": {j["pid"]: round(j.get("endurance", ENDURANCE_MAX)) for j in sur[1]}},
        "attente": {"a": list(blesses[0]), "b": list(blesses[1])},
        "formation": {"a": forme[0], "b": forme[1]},
        # the position each player is CURRENTLY filling, which a formation
        # changed at half-time and a substitution both move
        "postes": {"ab"[c]: {j["pid"]: {"slot": j.get("slot"), "hors_poste": bool(j.get("hors_poste"))}
                             for j in sur[c]} for c in (0, 1)},
        "evenements": evenements, "fil": fil,
        "onze": {"a": [j["pid"] for j in sur[0]], "b": [j["pid"] for j in sur[1]]},
        "traits": {"a": {k: round(v, 3) for k, v in t[0].items()}, "b": {k: round(v, 3) for k, v in t[1].items()}},
        "tactique": {"a": vars(tac[0]), "b": vars(tac[1])},
        "graine": graine,
    }


_MOTS = {"possession": "garde le ballon", "direct": "joue direct", "equilibre": "revient à l'équilibre",
         "haut": "monte son bloc", "median": "replace son bloc", "bas": "descend son bloc",
         "offensif": "prend des risques", "prudent": "ferme le jeu"}


# Ce qu'on dit d'une consigne dans le fil du match.
_MOTS_CONSIGNE = {
    ("lateraux", "bas"): "latéraux bas", ("lateraux", "axe"): "latéraux dans l'axe",
    ("ailiers", "ligne"): "ailiers sur la ligne", ("ailiers", "interieur"): "ailiers qui repiquent",
    ("milieux", "projection"): "milieux qui se projettent", ("milieux", "bas"): "milieux bas",
    ("milieux", "lateral"): "jeu décalé sur les côtés",
    ("attaquants", "profondeur"): "appels en profondeur", ("attaquants", "pivot"): "attaquant en pivot",
    ("relance", "courte"): "relance courte", ("relance", "longue"): "jeu long",
}


def _texte_tactique(nom: str, t: Tactique) -> str:
    bouts = [_MOTS.get(t.tempo, t.tempo), _MOTS.get(t.bloc, t.bloc), _MOTS.get(t.risque, t.risque)]
    # les consignes ne sont nommées que si elles ne sont pas neutres : les
    # citer toutes noierait ce que le manager vient vraiment de changer
    bouts += [m for (axe, choix), m in _MOTS_CONSIGNE.items() if getattr(t, axe, None) == choix]
    return f"{nom} : " + ", ".join(bouts)


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
        fam = S.FAMILLE_POSTE.get(slot or poste, S.FAMILLE_POSTE.get(poste, "MID"))
        joueurs.append({"pid": pid, "nom": nom_j, "poste": poste, "fam": fam, "ovr": ovr,
                        # the card as it is, kept apart from the card as it
                        # is being played: a formation change mid-match
                        # recomputes the penalty from the raw one.
                        "attributs_bruts": dict(attributs), "tenus": tenus,
                        "attributs": ({k: max(40, v - MALUS_HORS_POSTE) for k, v in attributs.items()}
                                      if dehors else attributs),
                        "slot": slot, "hors_poste": dehors,
                        "profil": profil(attributs, fam),
                        "endurance": ENDURANCE_MAX})
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

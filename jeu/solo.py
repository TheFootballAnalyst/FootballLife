"""solo.py — la campagne solo : ta place dans une vraie compétition.

Tu choisis une compétition, tu choisis le club dont tu prends la place, et
tu joues son calendrier contre les onze réels des autres clubs, construits
à partir des cartes du jeu.  Chaque adversaire vaut exactement ce que
valent ses joueurs cette saison : quand Hakimi baisse, le PSG que tu
affrontes baisse avec lui.

Deux formats, parce que les compétitions n'ont pas la même forme.

  championnat   aller-retour contre tous les autres clubs.  Les autres
                matchs de la journée sont joués eux aussi, donc le
                classement est un vrai classement et pas un décor.  La
                récompense dépend de la place finale.
  coupe         un tableau à seize, à élimination directe, tête de série
                par la valeur de l'effectif.  Un nul se décide aux tirs au
                but.  La récompense dépend du tour atteint : « en fonction
                de là où tu es éliminé ».

Tout est déterministe.  La graine de la campagne fixe la graine de chaque
match (`_graine`), donc rejouer la même campagne donne la même chose, et
un match déjà joué ne se rejoue pas en mieux : le résultat est écrit dès
qu'il est calculé.

Les récompenses sont des crédits (M€, le budget du club) et des packs
offerts (equipe.packs_offerts), qui s'ouvrent gratuitement depuis l'écran
Packs.  Elles ne créent pas de carte de nulle part : un pack offert tire
dans le même vivier que les autres.
"""
from __future__ import annotations

import json
import random
from datetime import datetime, timezone

from jeu import scoring as S
from jeu import simulation as SM

# The competitions you can take a place in.  `cid` is the competition_id of
# the game base; a cup keeps only its `taille` strongest clubs, so the
# bracket is the one everybody has in mind (a last sixteen) and not the
# league phase.
COMPETITIONS = {
    "ligue1":  {"nom": "Ligue 1", "cid": 53, "format": "championnat"},
    "premier": {"nom": "Premier League", "cid": 47, "format": "championnat"},
    "liga":    {"nom": "LaLiga", "cid": 87, "format": "championnat"},
    "seriea":  {"nom": "Serie A", "cid": 55, "format": "championnat"},
    "bundes":  {"nom": "Bundesliga", "cid": 54, "format": "championnat"},
    "ldc":     {"nom": "Ligue des champions", "cid": 42, "format": "coupe", "taille": 16},
}

TOURS_COUPE = {16: "Huitièmes", 8: "Quarts", 4: "Demi-finales", 2: "Finale"}

# What a campaign pays.  `credits` in M€, `packs` by type.  A league pays on
# the final position (as a share of the field), a cup on the round reached.
PRIME_VICTOIRE, PRIME_NUL = 1.5, 0.5     # per match, so every match is worth playing
RECOMPENSES_CHAMPIONNAT = {
    "champion": ("Champion", 60.0, {"or": 2}),
    "podium": ("Podium", 35.0, {"or": 1}),
    "europe": ("Qualifié pour l'Europe", 20.0, {"argent": 2}),
    "moitie": ("Première moitié de tableau", 10.0, {"argent": 1}),
    "maintenu": ("Maintenu", 5.0, {"bronze": 1}),
    "relegue": ("Relégué", 2.0, {"bronze": 1}),
}
RECOMPENSES_COUPE = {
    1: ("Vainqueur", 80.0, {"or": 2, "argent": 1}),
    2: ("Finaliste", 45.0, {"or": 1}),
    4: ("Demi-finaliste", 28.0, {"argent": 2}),
    8: ("Quart de finaliste", 16.0, {"argent": 1}),
    16: ("Éliminé en huitièmes", 8.0, {"bronze": 1}),
}


class ErreurSolo(Exception):
    pass


def maintenant() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------
# The real clubs and their elevens
# --------------------------------------------------------------------------

def clubs_competition(jeu, saison: str, cle: str) -> list[dict]:
    """The clubs of a competition, strongest squad first.

    Strength is the mean OVR of the club's eight best cards — enough to
    seed a bracket, and it moves with the season like everything else."""
    if cle not in COMPETITIONS:
        raise ErreurSolo("Compétition inconnue")
    comp = COMPETITIONS[cle]
    tids = [r[0] for r in jeu.execute(
        """SELECT DISTINCT home_team_id FROM match WHERE competition_id=?
           UNION SELECT DISTINCT away_team_id FROM match WHERE competition_id=?""",
        (comp["cid"], comp["cid"]))]
    out = []
    for tid in tids:
        ovrs = [r[0] for r in jeu.execute(
            """SELECT c.ovr FROM carte c JOIN joueur j ON j.player_id=c.player_id
               WHERE c.saison=? AND j.team_id=? ORDER BY c.ovr DESC LIMIT 8""", (saison, tid))]
        if len(ovrs) < 8:                 # a club the game has no squad for cannot be played
            continue
        nom, couleur = (jeu.execute("SELECT nom, couleur FROM club WHERE team_id=?", (tid,)).fetchone()
                        or ("Club " + str(tid), None))
        out.append({"team_id": tid, "nom": nom, "couleur": couleur or "#14161E",
                    "force": round(sum(ovrs) / len(ovrs), 1)})
    out.sort(key=lambda c: -c["force"])
    taille = comp.get("taille")
    return out[:taille] if taille else out


def onze_club(jeu, saison: str, team_id: int, formation: str = "4-3-3") -> list[dict]:
    """A real club's best eleven, as cards.

    The scarcest line is served first: filling greedily in slot order let a
    club with two keepers and nineteen midfielders end up without a
    defender.  A club short of a line is completed with its best remaining
    cards rather than refused — the eleven is still eleven real players."""
    cartes = [{"pid": r[0], "nom": r[1], "poste": r[2], "ovr": r[3],
               "attributs": json.loads(r[4] or "{}"),
               "familles": S.familles_eligibles(json.loads(r[5])) if r[5] else
                           [S.FAMILLE_POSTE.get(r[2], "MID")]}
              for r in jeu.execute(
                  """SELECT c.player_id, j.nom, j.poste, c.ovr, c.attributs, j.postes FROM carte c
                     JOIN joueur j ON j.player_id=c.player_id
                     WHERE c.saison=? AND j.team_id=? ORDER BY c.ovr DESC""", (saison, team_id))]
    for c in cartes:
        c["familles"] = c["familles"] or [S.FAMILLE_POSTE.get(c["poste"], "MID")]
    besoins = dict(zip(("GK", "DEF", "MID", "FWD"), S.FORMATIONS[formation]))
    pris: list[dict] = []
    utilises: set[int] = set()
    for fam in sorted(besoins, key=lambda f: len([c for c in cartes if f in c["familles"]])):
        for c in cartes:
            if len([x for x in pris if x["fam"] == fam]) >= besoins[fam]:
                break
            if c["pid"] not in utilises and fam in c["familles"]:
                utilises.add(c["pid"])
                pris.append(c | {"fam": fam})
    for c in cartes:                       # a line the club cannot fill
        if len(pris) >= S.TAILLE_ONZE:
            break
        if c["pid"] not in utilises:
            utilises.add(c["pid"])
            pris.append(c | {"fam": c["familles"][0]})
    return pris


# Tercile boundaries measured on the 96 club elevens of the five leagues.
# A club's way of playing has to be read against its PEERS: judged against
# absolute values, every club came out direct and offensive at once,
# because a club eleven finishes better than it controls almost by
# definition.  Against the terciles, the league divides in three.
SEUILS_TEMPO = (-0.139, -0.081)     # controle - finition
SEUILS_BLOC = (0.392, 0.436)        # defense
SEUILS_RISQUE = (0.071, 0.130)      # finition - defense


def _tercile(valeur: float, seuils: tuple[float, float], bas: str, milieu: str, haut: str) -> str:
    return bas if valeur < seuils[0] else haut if valeur > seuils[1] else milieu


def tactique_club(joueurs: list[dict]) -> SM.Tactique:
    """How a real club plays: read from its own eleven, never drawn.

    A side that controls far more than it finishes keeps the ball; one
    whose finishing is well ahead of its control goes direct; a weak
    defence sits deep, a strong one presses high."""
    t = SM.traits(joueurs)
    return SM.Tactique(
        tempo=_tercile(t["controle"] - t["finition"], SEUILS_TEMPO, "direct", "equilibre", "possession"),
        bloc=_tercile(t["defense"], SEUILS_BLOC, "bas", "median", "haut"),
        risque=_tercile(t["finition"] - t["defense"], SEUILS_RISQUE, "prudent", "equilibre", "offensif"),
    ).valide()


def equipe_club(jeu, saison: str, club: dict) -> SM.Equipe:
    j = onze_club(jeu, saison, club["team_id"])
    return SM.Equipe(club["nom"], j, tactique_club(j))


# --------------------------------------------------------------------------
# The calendar
# --------------------------------------------------------------------------

def calendrier_championnat(n: int) -> list[list[tuple[int, int]]]:
    """A double round robin over `n` places, by the circle method.

    Returns the rounds, each a list of (home, away) pairs; the second leg
    mirrors the first, so everybody plays everybody twice, once each way.
    The ends are swapped on odd rounds: the plain circle method gives a
    club its whole first leg at home and the second away (a nineteen-match
    run), which is not a calendar anybody recognises.  Alternating brings
    the longest run down to two, like a real fixture list.  An odd field
    rests one club a round (the ghost)."""
    places = list(range(n if n % 2 == 0 else n + 1))
    fantome = len(places) - 1 if n % 2 else None
    aller = []
    for tour in range(len(places) - 1):
        paires = [(places[i], places[len(places) - 1 - i]) for i in range(len(places) // 2)]
        if tour % 2:
            paires = [(b, a) for a, b in paires]
        aller.append([(a, b) for a, b in paires if fantome not in (a, b)])
        places = [places[0]] + [places[-1]] + places[1:-1]
    return aller + [[(b, a) for a, b in tour] for tour in aller]


def bracket_coupe(n: int) -> list[tuple[int, int]]:
    """The first round of a seeded bracket over `n` seeds: 1-16, 8-9, ...
    so the two strongest can only meet in the final."""
    ordre = [0]
    while len(ordre) < n:
        taille = len(ordre) * 2
        ordre = [x for i in ordre for x in (i, taille - 1 - i)]
    return [(ordre[i], ordre[i + 1]) for i in range(0, n, 2)]


def demarrer(jeu, saison: str, equipe_id: int, cle: str, club_remplace: int,
             graine: int | None = None) -> int:
    """Take a club's place in a competition.  Returns the campagne_id."""
    if en_cours(jeu, saison, equipe_id):
        raise ErreurSolo("Tu as déjà une campagne en cours")
    clubs = clubs_competition(jeu, saison, cle)
    if club_remplace not in {c["team_id"] for c in clubs}:
        raise ErreurSolo("Ce club ne joue pas cette compétition")
    comp = COMPETITIONS[cle]
    graine = graine if graine is not None else random.SystemRandom().randrange(1, 10 ** 9)
    # your place in the field is the one you took, seeding included
    place = next(i for i, c in enumerate(clubs) if c["team_id"] == club_remplace)
    autres = [c["team_id"] for c in clubs]
    if comp["format"] == "championnat":
        cal = calendrier_championnat(len(clubs))
    else:
        cal = [bracket_coupe(len(clubs))]
    cur = jeu.execute("""INSERT INTO campagne(saison, equipe_id, cle, club_remplace, place, graine,
                            clubs, calendrier, cree_le)
                         VALUES (?,?,?,?,?,?,?,?,?)""",
                      (saison, equipe_id, cle, club_remplace, place, graine,
                       json.dumps(autres), json.dumps(cal), maintenant()))
    jeu.commit()
    return cur.lastrowid


def en_cours(jeu, saison: str, equipe_id: int):
    return jeu.execute("""SELECT * FROM campagne WHERE saison=? AND equipe_id=? AND statut='en_cours'
                          ORDER BY campagne_id DESC LIMIT 1""", (saison, equipe_id)).fetchone()


def _graine(camp, tour: int, i: int = 0) -> int:
    return camp["graine"] * 10007 + tour * 101 + i


# --------------------------------------------------------------------------
# Playing a round
# --------------------------------------------------------------------------

def _clubs_du(jeu, saison, camp) -> list[dict]:
    """The field, in seeding order, with your place held by your team."""
    tids = json.loads(camp["clubs"])
    par_id = {c["team_id"]: c for c in clubs_competition(jeu, saison, camp["cle"])}
    nom_equipe = jeu.execute("SELECT nom FROM equipe WHERE equipe_id=?", (camp["equipe_id"],)).fetchone()[0]
    out = []
    for i, tid in enumerate(tids):
        c = dict(par_id.get(tid) or {"team_id": tid, "nom": f"Club {tid}", "couleur": "#14161E", "force": 60.0})
        if i == camp["place"]:
            c = c | {"nom": nom_equipe, "toi": True}
        out.append(c)
    return out


def jouer_tour(jeu, saison: str, equipe_id: int, onze: list[int], tactique: dict | None,
               formation: str = "4-3-3") -> dict:
    """Play your next match, and with it the rest of the round.

    Your opponents' matches are played too: a table nobody else fills is
    not a table.  Everything of the round is written at once, so a refresh
    never gives a second draw of the same fixtures."""
    from jeu import lobby as LB
    camp = en_cours(jeu, saison, equipe_id)
    if not camp:
        raise ErreurSolo("Aucune campagne en cours")
    onze = LB.verifier_onze(jeu, saison, equipe_id, onze, formation)
    cal = json.loads(camp["calendrier"])
    tour = camp["tour"]
    if tour >= len(cal):
        raise ErreurSolo("La campagne est terminée")
    clubs = _clubs_du(jeu, saison, camp)
    moi = camp["place"]
    equipes: dict[int, SM.Equipe] = {}

    def eq(place: int) -> SM.Equipe:
        if place not in equipes:
            equipes[place] = (SM.Equipe(clubs[moi]["nom"], SM.onze_depuis_cartes(jeu, saison, onze).joueurs,
                                        SM.Tactique(**(tactique or {})).valide())
                              if place == moi else equipe_club(jeu, saison, clubs[place]))
        return equipes[place]

    resultats = json.loads(camp["resultats"] or "[]")
    duels = cal[tour]
    feuilles = []
    for i, (a, b) in enumerate(duels):
        g = _graine(camp, tour, i)
        f = SM.jouer(eq(a), eq(b), g)
        tirs_au_but = None
        if COMPETITIONS[camp["cle"]]["format"] == "coupe" and f["resultat"] == "N":
            tirs_au_but = _penalties(eq(a), eq(b), g)
        feuilles.append({"tour": tour, "a": a, "b": b, "score": f["score"],
                         "resultat": tirs_au_but or f["resultat"],
                         "tab": tirs_au_but is not None,
                         "possession": f["possession"], "tirs": f["tirs"],
                         "evenements": f["evenements"] if moi in (a, b) else [],
                         "mien": moi in (a, b)})
    resultats += feuilles
    tour += 1
    fini, bilan = False, None
    if COMPETITIONS[camp["cle"]]["format"] == "coupe":
        vainqueurs = [d[0] if f["resultat"] == "A" else d[1] for d, f in zip(duels, feuilles)]
        if moi not in vainqueurs or len(vainqueurs) == 1:
            fini = True
        else:
            cal.append([(vainqueurs[i], vainqueurs[i + 1]) for i in range(0, len(vainqueurs), 2)])
    else:
        fini = tour >= len(cal)
    jeu.execute("UPDATE campagne SET tour=?, resultats=?, calendrier=? WHERE campagne_id=?",
                (tour, json.dumps(resultats), json.dumps(cal), camp["campagne_id"]))
    jeu.commit()
    if fini:
        bilan = cloturer(jeu, saison, camp["campagne_id"])
    return {"tour": tour - 1, "feuilles": feuilles, "fini": fini, "bilan": bilan}


def _penalties(a: SM.Equipe, b: SM.Equipe, graine: int) -> str:
    """A shootout: the better finishers have the edge, the seed decides."""
    ta, tb = SM.traits(a.joueurs), SM.traits(b.joueurs)
    pa = 0.5 + 0.5 * (ta["finition"] - tb["finition"]) + 0.3 * (tb["gardien"] - ta["gardien"])
    return "A" if random.Random(graine ^ 0xB0F).random() < max(0.15, min(0.85, pa)) else "B"


# --------------------------------------------------------------------------
# The table, the bracket, the rewards
# --------------------------------------------------------------------------

def classement(camp, clubs: list[dict]) -> list[dict]:
    """The league table as the played rounds leave it."""
    t = {i: {"place": i, "nom": c["nom"], "couleur": c.get("couleur"), "toi": bool(c.get("toi")),
             "j": 0, "g": 0, "n": 0, "p": 0, "bp": 0, "bc": 0, "pts": 0} for i, c in enumerate(clubs)}
    for f in json.loads(camp["resultats"] or "[]"):
        a, b = t[f["a"]], t[f["b"]]
        ba, bb = f["score"]
        for x, pour, contre in ((a, ba, bb), (b, bb, ba)):
            x["j"] += 1; x["bp"] += pour; x["bc"] += contre
        if f["resultat"] == "A":
            a["g"] += 1; a["pts"] += 3; b["p"] += 1
        elif f["resultat"] == "B":
            b["g"] += 1; b["pts"] += 3; a["p"] += 1
        else:
            a["n"] += 1; b["n"] += 1; a["pts"] += 1; b["pts"] += 1
    lignes = sorted(t.values(), key=lambda x: (-x["pts"], -(x["bp"] - x["bc"]), -x["bp"], x["nom"]))
    for k, l in enumerate(lignes, 1):
        l["rang"] = k
    return lignes


def recompense_championnat(rang: int, n: int) -> tuple[str, float, dict]:
    """What a final position pays.  The bands are the ones a league really
    has: the title, the podium, Europe, the top half, staying up, going
    down — scaled to the size of the field so an 18-club league and a
    20-club one read the same."""
    if rang == 1:
        cle = "champion"
    elif rang <= 3:
        cle = "podium"
    elif rang <= max(4, round(0.30 * n)):
        cle = "europe"
    elif rang <= n / 2:
        cle = "moitie"
    elif rang <= n - 3:
        cle = "maintenu"
    else:
        cle = "relegue"
    libelle, credits, packs = RECOMPENSES_CHAMPIONNAT[cle]
    return libelle, credits, dict(packs)


def cloturer(jeu, saison: str, campagne_id: int) -> dict:
    """Close a finished campaign and pay it.  Closing twice pays once."""
    camp = jeu.execute("SELECT * FROM campagne WHERE campagne_id=?", (campagne_id,)).fetchone()
    if camp is None:
        raise ErreurSolo("Campagne inconnue")
    if camp["statut"] == "fini":
        return json.loads(camp["recompenses"] or "{}")
    clubs = _clubs_du(jeu, saison, camp)
    moi = camp["place"]
    resultats = json.loads(camp["resultats"] or "[]")
    miens = [f for f in resultats if f["mien"]]
    victoires = sum(1 for f in miens if (f["resultat"] == "A") == (f["a"] == moi))
    nuls = sum(1 for f in miens if f["resultat"] == "N")
    if COMPETITIONS[camp["cle"]]["format"] == "championnat":
        table = classement(camp, clubs)
        rang = next(l["rang"] for l in table if l["place"] == moi)
        libelle, credits, packs = recompense_championnat(rang, len(clubs))
        detail = {"rang": rang, "sur": len(clubs)}
    else:
        # the round you went out in, counted by how many clubs were still
        # in when it was played: sixteen for the last sixteen, two for the
        # final, one if you won it
        restants = len(clubs)
        for t in range(camp["tour"]):
            mien = next((f for f in resultats if f["tour"] == t and f["mien"]), None)
            if mien is None:
                break
            engages = len([f for f in resultats if f["tour"] == t]) * 2
            if (mien["resultat"] == "A") != (mien["a"] == moi):
                restants = engages          # beaten with that many still in
                break
            restants = engages // 2 if engages > 2 else 1
        libelle, credits, packs = RECOMPENSES_COUPE[restants]
        detail = {"tour": TOURS_COUPE.get(restants, f"Tour à {restants}")}
    credits += PRIME_VICTOIRE * victoires + PRIME_NUL * nuls
    credits = round(credits, 1)
    bilan = {"libelle": libelle, "credits": credits, "packs": packs,
             "victoires": victoires, "nuls": nuls, "matchs": len(miens)} | detail
    jeu.execute("UPDATE campagne SET statut='fini', fini_le=?, recompenses=? WHERE campagne_id=?",
                (maintenant(), json.dumps(bilan), campagne_id))
    jeu.execute("UPDATE equipe SET budget = budget + ? WHERE equipe_id=?", (credits, camp["equipe_id"]))
    offerts = json.loads(jeu.execute("SELECT COALESCE(packs_offerts,'{}') FROM equipe WHERE equipe_id=?",
                                     (camp["equipe_id"],)).fetchone()[0])
    for k, v in packs.items():
        offerts[k] = offerts.get(k, 0) + v
    jeu.execute("UPDATE equipe SET packs_offerts=? WHERE equipe_id=?",
                (json.dumps(offerts), camp["equipe_id"]))
    jeu.commit()
    return bilan


def abandonner(jeu, saison: str, equipe_id: int) -> bool:
    """Give up a campaign.  It pays nothing: a campaign you walk out of is
    not a campaign you finished."""
    camp = en_cours(jeu, saison, equipe_id)
    if not camp:
        return False
    jeu.execute("UPDATE campagne SET statut='fini', fini_le=?, recompenses=? WHERE campagne_id=?",
                (maintenant(), json.dumps({"libelle": "Abandon", "credits": 0.0, "packs": {},
                                           "victoires": 0, "nuls": 0, "matchs": 0}),
                 camp["campagne_id"]))
    jeu.commit()
    return True


# --------------------------------------------------------------------------
# What the screen reads
# --------------------------------------------------------------------------

def etat(jeu, saison: str, equipe_id: int) -> dict:
    camp = en_cours(jeu, saison, equipe_id)
    offerts = json.loads(jeu.execute("SELECT COALESCE(packs_offerts,'{}') FROM equipe WHERE equipe_id=?",
                                     (equipe_id,)).fetchone()[0])
    base = {"packs_offerts": offerts, "palmares": palmares(jeu, saison, equipe_id)}
    if not camp:
        return base | {"campagne": None,
                       "competitions": [{"cle": k, "nom": v["nom"], "format": v["format"]}
                                        for k, v in COMPETITIONS.items()]}
    clubs = _clubs_du(jeu, saison, camp)
    cal = json.loads(camp["calendrier"])
    comp = COMPETITIONS[camp["cle"]]
    prochain = None
    if camp["tour"] < len(cal):
        # an odd field rests one club a round: there is a journée to play,
        # but not for you
        prochain = {"exempt": True, "tour": camp["tour"] + 1, "tours": len(cal)}
        for a, b in cal[camp["tour"]]:
            if camp["place"] in (a, b):
                adv = b if a == camp["place"] else a
                prochain = {"exempt": False, "adversaire": clubs[adv], "domicile": a == camp["place"],
                            "tour": camp["tour"] + 1, "tours": len(cal)}
    resultats = json.loads(camp["resultats"] or "[]")
    c = {"campagne_id": camp["campagne_id"], "cle": camp["cle"], "nom": comp["nom"], "format": comp["format"],
         "club_remplace": next((x["nom"] for i, x in enumerate(clubs_competition(jeu, saison, camp["cle"]))
                                if x["team_id"] == camp["club_remplace"]), ""),
         "place": camp["place"], "tour": camp["tour"], "tours": len(cal), "prochain": prochain,
         "mes_matchs": [f | {"adversaire": clubs[f["b"] if f["a"] == camp["place"] else f["a"]]["nom"]}
                        for f in resultats if f["mien"]][-8:]}
    if comp["format"] == "championnat":
        c["classement"] = classement(camp, clubs)
    else:
        c["tableau"] = [[{"a": clubs[a]["nom"], "b": clubs[b]["nom"],
                          "score": next((f["score"] for f in resultats if f["tour"] == t and f["a"] == a), None),
                          "resultat": next((f["resultat"] for f in resultats if f["tour"] == t and f["a"] == a), None),
                          "toi": camp["place"] in (a, b)}
                         for a, b in cal[t]] for t in range(len(cal))]
        c["reste"] = TOURS_COUPE.get(len(cal[camp["tour"]]) * 2 if camp["tour"] < len(cal) else 1, "")
    return base | {"campagne": c}


def palmares(jeu, saison: str, equipe_id: int) -> list[dict]:
    out = []
    for r in jeu.execute("""SELECT cle, recompenses, fini_le FROM campagne
                            WHERE saison=? AND equipe_id=? AND statut='fini'
                            ORDER BY campagne_id DESC LIMIT 12""", (saison, equipe_id)):
        try:
            bilan = json.loads(r[1] or "{}")
        except (TypeError, json.JSONDecodeError):
            continue
        if isinstance(bilan, dict):
            out.append({"competition": COMPETITIONS.get(r[0], {}).get("nom", r[0]),
                        "fini_le": r[2]} | bilan)
    return out

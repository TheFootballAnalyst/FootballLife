"""solo.py — la campagne solo : ta place dans une vraie compétition.

Tu choisis une compétition, tu choisis le club dont tu prends la place, et
tu joues SON calendrier — le vrai, celui de la base — contre les onze
réels des autres clubs, bâtis sur les cartes du jeu.  Chaque adversaire
vaut exactement ce que valent ses joueurs cette saison : quand Hakimi
baisse, le PSG que tu affrontes baisse avec lui.  Tout suit la saison de
la base : importe 2026/27 et la campagne se joue en 2026/27.

Deux formats, et ce sont les vrais.

  championnat        le calendrier réel de la compétition, journée par
                     journée.  Les autres matchs de la journée sont joués
                     eux aussi, donc le classement est un vrai classement
                     et pas un décor.  La récompense dépend de la place.
  ligue_puis_coupe   la Ligue des champions telle qu'elle est depuis 2024 :
                     une phase de ligue à 36 où chacun joue huit adversaires
                     différents (le vrai tirage, lu dans la base), un seul
                     classement, puis
                       1-8    qualifiés directement pour les huitièmes
                       9-24   barrages en aller-retour (9-16 reçoivent au
                              retour), les huit vainqueurs rejoignent les
                              huitièmes
                       25-36  éliminés
                     huitièmes, quarts et demies en aller-retour, finale
                     sur un match.  Une double confrontation se joue au
                     cumul des deux manches, et un cumul à égalité se
                     décide aux tirs au but — plus de but à l'extérieur,
                     comme l'UEFA depuis 2021.

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
# the game base, and everything else about the shape of the competition is
# read from the base's own fixture list.
COMPETITIONS = {
    "ligue1":  {"nom": "Ligue 1", "cid": 53, "format": "championnat"},
    "premier": {"nom": "Premier League", "cid": 47, "format": "championnat"},
    "liga":    {"nom": "LaLiga", "cid": 87, "format": "championnat"},
    "seriea":  {"nom": "Serie A", "cid": 55, "format": "championnat"},
    "bundes":  {"nom": "Bundesliga", "cid": 54, "format": "championnat"},
    "ldc":     {"nom": "Ligue des champions", "cid": 42, "format": "ligue_puis_coupe"},
}

# The knockout ladder of the European format, in order.  `aller_retour`
# says whether the tie is two legs; the final never is.
PHASES = {
    "ligue": "Phase de ligue",
    "barrage": "Barrages",
    "8": "Huitièmes de finale",
    "4": "Quarts de finale",
    "2": "Demi-finales",
    "F": "Finale",
}
SUITE = {"barrage": "8", "8": "4", "4": "2", "2": "F"}
ALLER_RETOUR = {"barrage": True, "8": True, "4": True, "2": True, "F": False}

# Who survives the league phase, as UEFA has it since 2024.
DIRECTS = 8           # ranks 1-8 go straight to the last sixteen
BARRAGISTES = 24      # ranks 9-24 play off for the other eight places
TAILLE_LIGUE = 36     # clubs in the league phase
MATCHS_LIGUE = 8      # ... each playing eight different opponents

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
# A European campaign pays by how far you went, and going out in the
# league phase still pays something: eight matches is a campaign.
RECOMPENSES_EUROPE = {
    "vainqueur": ("Vainqueur", 90.0, {"or": 3}),
    "F": ("Finaliste", 55.0, {"or": 2}),
    "2": ("Demi-finaliste", 36.0, {"or": 1}),
    "4": ("Quart de finaliste", 24.0, {"argent": 2}),
    "8": ("Huitième de finaliste", 15.0, {"argent": 1}),
    "barrage": ("Éliminé en barrages", 9.0, {"bronze": 1}),
    "ligue": ("Éliminé en phase de ligue", 5.0, {"bronze": 1}),
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
    if comp["format"] != "ligue_puis_coupe":
        return out
    # The European field is thirty-six.  A base that covers only the big
    # five has cards for maybe twenty of the clubs that really qualified —
    # the rest play in leagues it never imported — and a knockout built on
    # twenty is not the competition.  The field is therefore completed with
    # the strongest clubs the game DOES have cards for, so the format is
    # the real one and every club in it is a real club with real cards.
    if len(out) < TAILLE_LIGUE:
        deja = {c["team_id"] for c in out}
        for tid, nom, couleur in jeu.execute(
                "SELECT team_id, nom, couleur FROM club ORDER BY nom"):
            if tid in deja:
                continue
            ovrs = [r[0] for r in jeu.execute(
                """SELECT c.ovr FROM carte c JOIN joueur j ON j.player_id=c.player_id
                   WHERE c.saison=? AND j.team_id=? ORDER BY c.ovr DESC LIMIT 8""", (saison, tid))]
            if len(ovrs) == 8:
                out.append({"team_id": tid, "nom": nom, "couleur": couleur or "#14161E",
                            "force": round(sum(ovrs) / len(ovrs), 1), "invite": True})
        out.sort(key=lambda c: -c["force"])
    return out[:TAILLE_LIGUE]


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


def banc_club(jeu, saison: str, team_id: int, onze: list[dict]) -> list[dict]:
    """The seven best cards of the club that are not in its eleven, a
    keeper first: a real bench, so the machine can make changes too."""
    pris = {j["pid"] for j in onze}
    reste = [{"pid": r[0], "nom": r[1], "poste": r[2], "ovr": r[3],
              "attributs": json.loads(r[4] or "{}"),
              "fam": (S.familles_eligibles(json.loads(r[5])) if r[5] else
                      [S.FAMILLE_POSTE.get(r[2], "MID")])[0] or "MID"}
             for r in jeu.execute(
                 """SELECT c.player_id, j.nom, j.poste, c.ovr, c.attributs, j.postes FROM carte c
                    JOIN joueur j ON j.player_id=c.player_id
                    WHERE c.saison=? AND j.team_id=? ORDER BY c.ovr DESC""", (saison, team_id))
             if r[0] not in pris]
    banc, quotas = [], {"GK": 1, "DEF": 2, "MID": 2, "FWD": 2}
    for j in reste:
        if quotas.get(j["fam"], 0) > 0:
            quotas[j["fam"]] -= 1
            banc.append(j)
    for j in reste:                       # a club short of a line fills up anyway
        if len(banc) >= S.TAILLE_BANC:
            break
        if j not in banc:
            banc.append(j)
    return banc[:S.TAILLE_BANC]


# When a real club makes its changes.  Three stoppages, like the laws, at
# the hours a manager really uses them: just after the break, the usual
# double change, and one to see the match out.
MINUTES_CHANGEMENT = (58, 70, 80)


def changements_club(e: SM.Equipe, graine: int) -> dict[int, list]:
    """The changes a machine-run club makes: its tired outfield players for
    the best of its bench, in the same line.  Deterministic in the seed, so
    a campaign replays identically."""
    rng = random.Random(graine ^ 0xC4A6)
    banc = [j for j in e.banc if j["fam"] != "GK"]
    sur = [j for j in e.joueurs if j["fam"] != "GK"]
    plan: dict[int, list] = {}
    utilises: set[int] = set()
    for k, minute in enumerate(MINUTES_CHANGEMENT):
        n = 2 if k == 1 else 1
        paires = []
        for _ in range(n):
            entrant = next((j for j in banc if j["pid"] not in utilises), None)
            if entrant is None:
                break
            memes = [j for j in sur if j["fam"] == entrant["fam"] and j["pid"] not in utilises]
            sortant = min(memes or [j for j in sur if j["pid"] not in utilises],
                          key=lambda j: j["ovr"], default=None)
            if sortant is None:
                break
            utilises |= {entrant["pid"], sortant["pid"]}
            paires.append((sortant["pid"], entrant["pid"]))
        if paires:
            plan[minute + rng.randrange(-3, 4)] = paires
    return plan


def equipe_club(jeu, saison: str, club: dict) -> SM.Equipe:
    j = onze_club(jeu, saison, club["team_id"])
    return SM.Equipe(club["nom"], j, tactique_club(j), banc_club(jeu, saison, club["team_id"], j))


# --------------------------------------------------------------------------
# The calendar
# --------------------------------------------------------------------------

def calendrier_championnat(n: int) -> list[list[tuple[int, int]]]:
    """A double round robin over `n` places, by the circle method — the
    fallback when the base has no fixture list for the competition.

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


PHASE_REGULIERE = "Phase reguliere"


def calendrier_reel(jeu, saison: str, cle: str, clubs: list[int]) -> list[list[tuple[int, int]]]:
    """The competition's REAL fixture list, gameweek by gameweek.

    This is what makes a campaign the competition and not a generated
    imitation: the eight opponents a club really drew in the league phase,
    the real order of a league season.  Fixtures involving a club the game
    has no squad for are dropped — it cannot be played — and a base with
    no fixtures at all returns nothing, so the caller falls back on the
    circle method."""
    cid = COMPETITIONS[cle]["cid"]
    place = {tid: i for i, tid in enumerate(clubs)}
    tours: dict[int, list[tuple[int, int]]] = {}
    for numero, a, b in jeu.execute("""
            SELECT j.numero, m.home_team_id, m.away_team_id FROM match m
            JOIN journee j ON j.journee_id = m.journee_id
            WHERE m.competition_id = ? AND j.saison = ? AND COALESCE(m.phase, ?) = ?
            ORDER BY j.numero, m.date_utc""", (cid, saison, PHASE_REGULIERE, PHASE_REGULIERE)):
        if a in place and b in place and a != b:
            tours.setdefault(numero, []).append((place[a], place[b]))
    return [tours[k] for k in sorted(tours) if tours[k]]


def _complet(tours: list[list[tuple[int, int]]], n: int, attendus: int) -> bool:
    """Whether a fixture list really covers the field: every club playing
    the expected number of matches.  A base that covers only some of the
    competition's clubs gives a calendar full of holes — half a league
    phase, a club with two matches and another with nine — and a generated
    draw is then closer to the competition than the real fragments."""
    if not tours:
        return False
    joues = {i: 0 for i in range(n)}
    for tour in tours:
        for a, b in tour:
            joues[a] = joues.get(a, 0) + 1
            joues[b] = joues.get(b, 0) + 1
    return all(v == attendus for v in joues.values())


def _tour(phase: str, manche: int, duels: list[tuple[int, int]]) -> dict:
    return {"phase": phase, "libelle": PHASES.get(phase, phase), "manche": manche,
            "duels": [list(d) for d in duels]}


def demarrer(jeu, saison: str, equipe_id: int, cle: str, club_remplace: int,
             graine: int | None = None) -> int:
    """Take a club's place in a competition.  Returns the campagne_id."""
    if en_cours(jeu, saison, equipe_id):
        raise ErreurSolo("Tu as déjà une campagne en cours")
    clubs = clubs_competition(jeu, saison, cle)
    if club_remplace not in {c["team_id"] for c in clubs}:
        raise ErreurSolo("Ce club ne joue pas cette compétition")
    graine = graine if graine is not None else random.SystemRandom().randrange(1, 10 ** 9)
    place = next(i for i, c in enumerate(clubs) if c["team_id"] == club_remplace)
    tids = [c["team_id"] for c in clubs]
    europe = COMPETITIONS[cle]["format"] == "ligue_puis_coupe"
    reel = calendrier_reel(jeu, saison, cle, tids)
    attendus = MATCHS_LIGUE if europe else 2 * (len(tids) - 1)
    tours = reel if _complet(reel, len(tids), attendus) else (
        calendrier_championnat(len(tids))[:MATCHS_LIGUE] if europe else calendrier_championnat(len(tids)))
    phase = "ligue" if europe else "championnat"
    cal = [_tour(phase, 0, t) for t in tours]
    cur = jeu.execute("""INSERT INTO campagne(saison, equipe_id, cle, club_remplace, place, graine,
                            clubs, calendrier, cree_le)
                         VALUES (?,?,?,?,?,?,?,?,?)""",
                      (saison, equipe_id, cle, club_remplace, place, graine,
                       json.dumps(tids), json.dumps(cal), maintenant()))
    jeu.commit()
    return cur.lastrowid


def en_cours(jeu, saison: str, equipe_id: int):
    return jeu.execute("""SELECT * FROM campagne WHERE saison=? AND equipe_id=? AND statut='en_cours'
                          ORDER BY campagne_id DESC LIMIT 1""", (saison, equipe_id)).fetchone()


def _graine(camp, tour: int, i: int = 0) -> int:
    return camp["graine"] * 10007 + tour * 101 + i


# --------------------------------------------------------------------------
# The ladder: what the league phase leaves, and what each tie decides
# --------------------------------------------------------------------------

def _duels_de(cal: list[dict], tour: int) -> list[tuple[int, int]]:
    return [tuple(d) for d in cal[tour]["duels"]]


def _cumul(resultats: list[dict], phase: str) -> dict[frozenset, dict]:
    """Each tie of a phase, with its aggregate over the legs played."""
    ties: dict[frozenset, dict] = {}
    for f in resultats:
        if f.get("phase") != phase:
            continue
        cle = frozenset((f["a"], f["b"]))
        t = ties.setdefault(cle, {"buts": {}, "manches": 0, "duel": (f["a"], f["b"])})
        t["buts"][f["a"]] = t["buts"].get(f["a"], 0) + f["score"][0]
        t["buts"][f["b"]] = t["buts"].get(f["b"], 0) + f["score"][1]
        t["manches"] += 1
    return ties


def vainqueurs_phase(camp, resultats: list[dict], phase: str) -> list[int] | None:
    """The winners of a phase once every tie has been played out, or None
    while one is still open.

    The aggregate decides; level on aggregate goes to penalties — there is
    no away-goals rule any more, and there has not been since 2021."""
    cal = json.loads(camp["calendrier"])
    manches = sum(1 for t in cal if t["phase"] == phase)
    if not manches:
        return None
    ties = _cumul(resultats, phase)
    attendus = len(_duels_de(cal, next(i for i, t in enumerate(cal) if t["phase"] == phase)))
    if len(ties) != attendus or any(t["manches"] < manches for t in ties.values()):
        return None
    out = []
    for cle, t in ties.items():
        x, y = t["duel"]
        bx, by = t["buts"].get(x, 0), t["buts"].get(y, 0)
        if bx != by:
            out.append(x if bx > by else y)
        else:
            g = camp["graine"] * 7919 + min(x, y) * 131 + max(x, y)
            out.append(x if random.Random(g).random() < 0.5 else y)
    # keep the order of the bracket, so the next round is drawn from it
    ordre = {frozenset(d): i for i, d in enumerate(
        _duels_de(cal, next(i for i, t in enumerate(cal) if t["phase"] == phase)))}
    return [v for _, v in sorted(zip([ordre[frozenset((x, y))] for x, y in
                                      [(t["duel"]) for t in ties.values()]], out))]


def seuils_qualification(n: int) -> tuple[int, int]:
    """(how many go straight through, how many reach the play-off) for a
    league phase of `n` clubs.

    The real competition is 8 and 24 out of 36.  A base that has no squad
    for some clubs gives a smaller field, and the shape has to hold: the
    play-off must produce exactly as many winners as there are seeds, so
    the number going through is a power of two and the play-off is three
    times it."""
    if n >= 36:
        return DIRECTS, BARRAGISTES
    directs = 1
    while directs * 2 <= DIRECTS and directs * 6 <= n:
        directs *= 2
    return directs, min(n, directs * 3)


def tableau_apres_ligue(rangs: list[int]) -> tuple[list[tuple[int, int]], list[int], list[int]]:
    """What the league phase decides: (play-off ties, the seeded clubs that
    go straight to the last sixteen, the clubs knocked out).

    `rangs` are the places in finishing order.  UEFA seeds the play-off
    9-16 against 17-24 — ninth plays twenty-fourth — and the seeded side
    hosts the second leg."""
    n_directs, n_barrages = seuils_qualification(len(rangs))
    directs = rangs[:n_directs]
    barrages = rangs[n_directs:n_barrages]
    sortis = rangs[n_barrages:]
    n = len(barrages) // 2
    # (lower seed, higher seed): the first leg is at the lower seed's
    duels = [(barrages[n + i], barrages[n - 1 - i]) for i in range(n)]
    return duels, directs, sortis


def tableau_huitiemes(directs: list[int], qualifies: list[int]) -> list[tuple[int, int]]:
    """The last sixteen: the eight seeded clubs meet the eight play-off
    winners, best against weakest, and host the second leg."""
    return [(qualifies[len(qualifies) - 1 - i] if i < len(qualifies) else directs[i], directs[i])
            for i in range(len(directs))]


def _prochaine_phase(camp, resultats: list[dict]) -> tuple[str, list[tuple[int, int]]] | None:
    """The round to play after the one just finished, or None if the
    campaign is over for everybody."""
    cal = json.loads(camp["calendrier"])
    phase = cal[-1]["phase"]
    if phase == "championnat":
        return None
    if phase == "ligue":
        clubs = json.loads(camp["clubs"])
        table = _table(camp, resultats, "ligue", len(clubs))
        rangs = [l["place"] for l in table]
        duels, _directs, _sortis = tableau_apres_ligue(rangs)
        return ("barrage", duels) if duels else None
    gagnants = vainqueurs_phase(camp, resultats, phase)
    if gagnants is None:
        return None
    if phase == "barrage":
        clubs = json.loads(camp["clubs"])
        table = _table(camp, resultats, "ligue", len(clubs))
        rangs = [l["place"] for l in table]
        _duels, directs, _sortis = tableau_apres_ligue(rangs)
        return "8", tableau_huitiemes(directs, gagnants)
    if len(gagnants) <= 1:
        return None
    suite = SUITE.get(phase)
    if suite is None:
        return None
    return suite, [(gagnants[i], gagnants[i + 1]) for i in range(0, len(gagnants) - 1, 2)]


def _ajouter_phase(cal: list[dict], phase: str, duels: list[tuple[int, int]]) -> None:
    """Append a phase's rounds: one leg, or two with the ends swapped."""
    if ALLER_RETOUR.get(phase):
        cal.append(_tour(phase, 1, duels))
        cal.append(_tour(phase, 2, [(b, a) for a, b in duels]))
    else:
        cal.append(_tour(phase, 0, duels))


# --------------------------------------------------------------------------
# Playing a round
# --------------------------------------------------------------------------

def _clubs_du(jeu, saison, camp) -> list[dict]:
    """The field, in the order the campaign froze, with your place held by
    your team."""
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


def match_en_cours(jeu, camp):
    """The live match of the campaign's current round, if one is running."""
    if camp is None:
        return None
    return jeu.execute("""SELECT * FROM rencontre WHERE campagne_id=? AND tour=? AND resultat IS NULL
                          ORDER BY rencontre_id DESC LIMIT 1""",
                       (camp["campagne_id"], camp["tour"])).fetchone()


def lancer_tour(jeu, saison: str, equipe_id: int, onze: list[int], tactique: dict | None,
                formation: str = "4-3-3", banc: list[int] | None = None) -> int:
    """Kick YOUR match of the round off, live.

    It is an ordinary `rencontre` row tied to the campaign, so it uses the
    lobby's own machinery — the server's clock, the sheet replayed from the
    seed, tactical changes and substitutions stamped by that clock.  There
    is one live match in the game, not two.  The rest of the round is
    played when this one ends (`cloturer_tour`)."""
    from jeu import lobby as LB
    camp = en_cours(jeu, saison, equipe_id)
    if not camp:
        raise ErreurSolo("Aucune campagne en cours")
    if match_en_cours(jeu, camp):
        raise ErreurSolo("Ton match est déjà en cours")
    cal = json.loads(camp["calendrier"])
    tour = camp["tour"]
    if tour >= len(cal):
        raise ErreurSolo("La campagne est terminée")
    onze = LB.verifier_onze(jeu, saison, equipe_id, onze, formation)
    banc = LB.verifier_banc(jeu, saison, equipe_id, onze, banc)
    moi = camp["place"]
    duels = _duels_de(cal, tour)
    mien = next(((i, d) for i, d in enumerate(duels) if moi in d), None)
    if mien is None:
        return 0                            # exempt this round: nothing to kick off
    i, (a, b) = mien
    clubs = _clubs_du(jeu, saison, camp)
    adv = b if a == moi else a
    eq_adv = equipe_club(jeu, saison, clubs[adv])
    g = _graine(camp, tour, i)
    plan = changements_club(eq_adv, g)
    # You are always side A of the live match, whoever is at home in the
    # fixture: the sheet then reads from your side without anyone having to
    # flip it, and `domicile` keeps the fixture's own truth.
    rempl = {str(m): ([], [[s, e] for s, e in paires]) for m, paires in plan.items()}
    cur = jeu.execute("""INSERT INTO rencontre(saison, equipe_a, equipe_b, defi, onze_a, banc_a, tactique_a,
                            onze_b, banc_b, tactique_b, remplacements, graine, debut, campagne_id, tour,
                            nom_adverse, domicile, cree_le)
                         VALUES (?,?,?,1,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                      (saison, equipe_id, None,
                       json.dumps(onze), json.dumps(banc),
                       json.dumps(vars(SM.Tactique(**(tactique or {})).valide())),
                       json.dumps([j["pid"] for j in eq_adv.joueurs]),
                       json.dumps([j["pid"] for j in eq_adv.banc]),
                       json.dumps(vars(eq_adv.tactique)),
                       json.dumps(rempl), g, LB.maintenant(), camp["campagne_id"], tour,
                       clubs[adv]["nom"], int(a == moi), maintenant()))
    jeu.commit()
    return cur.lastrowid


def jouer_tour(jeu, saison: str, equipe_id: int, onze: list[int], tactique: dict | None,
               formation: str = "4-3-3", banc: list[int] | None = None) -> dict:
    """Play your next match, and with it the rest of the round.

    Your opponents' matches are played too: a table nobody else fills is
    not a table.  Everything of the round is written at once, so a refresh
    never gives a second draw of the same fixtures."""
    from jeu import lobby as LB
    camp = en_cours(jeu, saison, equipe_id)
    if not camp:
        raise ErreurSolo("Aucune campagne en cours")
    onze = LB.verifier_onze(jeu, saison, equipe_id, onze, formation)
    banc = LB.verifier_banc(jeu, saison, equipe_id, onze, banc)
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
                                        SM.Tactique(**(tactique or {})).valide(),
                                        SM.onze_depuis_cartes(jeu, saison, banc).joueurs)
                              if place == moi else equipe_club(jeu, saison, clubs[place]))
        return equipes[place]

    def plan(place: int, g: int) -> dict[int, list]:
        """A machine-run club makes its changes; yours are yours to make."""
        return {} if place == moi else changements_club(eq(place), g)

    resultats = json.loads(camp["resultats"] or "[]")
    phase = cal[tour]["phase"]
    duels = _duels_de(cal, tour)
    # your match may already have been PLAYED LIVE: its sheet is the one
    # that counts, or you would watch one match and be scored on another
    jouee = jeu.execute("""SELECT feuille FROM rencontre WHERE campagne_id=? AND tour=?
                           AND feuille IS NOT NULL ORDER BY rencontre_id DESC LIMIT 1""",
                        (camp["campagne_id"], tour)).fetchone()
    feuille_live = json.loads(jouee[0]) if jouee and jouee[0] else None
    feuilles = []
    for i, (a, b) in enumerate(duels):
        g = _graine(camp, tour, i)
        if feuille_live is not None and moi in (a, b):
            # the live sheet is written from YOUR side; the fixture records
            # home first, so it is flipped back when you played away
            f = feuille_live if a == moi else _retourner(feuille_live)
        else:
            chg: dict[int, tuple[list, list]] = {}
            for cote, place in ((0, a), (1, b)):
                for minute, paires in plan(place, g).items():
                    courant = chg.setdefault(minute, ([], []))
                    courant[cote].extend(paires)
            f = SM.jouer(eq(a), eq(b), g, changements=chg)
        feuilles.append({"tour": tour, "phase": phase, "manche": cal[tour]["manche"],
                         "a": a, "b": b, "score": f["score"], "resultat": f["resultat"],
                         "possession": f["possession"], "tirs": f["tirs"],
                         "corners": f["corners"], "fautes": f["fautes"],
                         "jaunes": f["jaunes"], "rouges": f["rouges"],
                         "evenements": f["evenements"] if moi in (a, b) else [],
                         "fil": f["fil"] if moi in (a, b) else [],
                         "mien": moi in (a, b)})
    resultats += feuilles
    tour += 1

    # the round that follows, once this phase has played itself out
    if tour >= len(cal) and cal[-1]["phase"] != "championnat":
        suite = _prochaine_phase(camp, resultats)
        if suite:
            _ajouter_phase(cal, suite[0], suite[1])

    fini = tour >= len(cal) or not _encore_en_lice(camp, resultats, cal, moi, tour)
    jeu.execute("UPDATE campagne SET tour=?, resultats=?, calendrier=? WHERE campagne_id=?",
                (tour, json.dumps(resultats), json.dumps(cal), camp["campagne_id"]))
    jeu.commit()
    bilan = cloturer(jeu, saison, camp["campagne_id"]) if fini else None
    return {"tour": tour - 1, "phase": phase, "feuilles": feuilles, "fini": fini, "bilan": bilan}


def _retourner(f: dict) -> dict:
    """The same sheet seen from the other side."""
    ech = ("score", "possession", "tirs", "xg", "corners", "fautes", "jaunes", "rouges", "horsjeu",
           "changements")
    out = dict(f)
    for cle in ech:
        if isinstance(f.get(cle), list) and len(f[cle]) == 2:
            out[cle] = [f[cle][1], f[cle][0]]
    out["resultat"] = {"A": "B", "B": "A"}.get(f.get("resultat"), f.get("resultat"))
    out["evenements"] = [e | {"cote": {"A": "B", "B": "A"}.get(e.get("cote"), e.get("cote"))}
                         for e in f.get("evenements", [])]
    out["fil"] = [x | {"c": 1 - x["c"]} for x in f.get("fil", [])]
    return out


def cloturer_tour(jeu, saison: str, equipe_id: int) -> dict | None:
    """Close the round once your live match's ninety minutes are up: freeze
    its sheet, play the rest of the round, advance the campaign."""
    from jeu import lobby as LB
    camp = en_cours(jeu, saison, equipe_id)
    if not camp:
        return None
    r = match_en_cours(jeu, camp)
    if r is None:
        return None
    if LB.minute_courante(r["debut"]) < SM.MINUTES:
        return None
    LB.cloturer(jeu, saison, r)
    onze, banc, tac = json.loads(r["onze_a"]), json.loads(r["banc_a"] or "[]"), json.loads(r["tactique_a"])
    return jouer_tour(jeu, saison, equipe_id, onze, tac, banc=banc)


def _encore_en_lice(camp, resultats: list[dict], cal: list[dict], moi: int, tour: int) -> bool:
    """Whether you still have a match to play: a league season always does,
    a knockout only while you are in the next round."""
    if tour >= len(cal):
        return False
    if cal[tour]["phase"] in ("championnat", "ligue"):
        return True
    return any(moi in d for d in _duels_de(cal, tour))


def _penalties(a: SM.Equipe, b: SM.Equipe, graine: int) -> str:
    """A shootout: the better finishers have the edge, the seed decides."""
    ta, tb = SM.traits(a.joueurs), SM.traits(b.joueurs)
    pa = 0.5 + 0.5 * (ta["finition"] - tb["finition"]) + 0.3 * (tb["gardien"] - ta["gardien"])
    return "A" if random.Random(graine ^ 0xB0F).random() < max(0.15, min(0.85, pa)) else "B"


# --------------------------------------------------------------------------
# The table, the bracket, the rewards
# --------------------------------------------------------------------------

def _table(camp, resultats: list[dict], phase: str, n: int) -> list[dict]:
    """The standing of one phase, places only — what the ranking rules need
    without any club name."""
    t = {i: {"place": i, "j": 0, "g": 0, "n": 0, "p": 0, "bp": 0, "bc": 0, "pts": 0} for i in range(n)}
    for f in resultats:
        if f.get("phase") not in (phase, None) or f["a"] not in t or f["b"] not in t:
            continue
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
    lignes = sorted(t.values(), key=lambda x: (-x["pts"], -(x["bp"] - x["bc"]), -x["bp"], x["place"]))
    for k, l in enumerate(lignes, 1):
        l["rang"] = k
    return lignes


def classement(camp, clubs: list[dict], phase: str | None = None) -> list[dict]:
    """The table as the played rounds leave it, with the clubs' names."""
    phase = phase or json.loads(camp["calendrier"])[0]["phase"]
    lignes = _table(camp, json.loads(camp["resultats"] or "[]"), phase, len(clubs))
    return [l | {"nom": clubs[l["place"]]["nom"], "couleur": clubs[l["place"]].get("couleur"),
                 "toi": bool(clubs[l["place"]].get("toi"))} for l in lignes]


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


def _sortie_europe(camp, resultats: list[dict], cal: list[dict], moi: int) -> str:
    """Where a European campaign ended for you: the key of RECOMPENSES_EUROPE."""
    phases = [t["phase"] for t in cal]
    if "barrage" not in phases:            # the league phase did not send you through
        return "ligue"
    derniere = None
    for phase in ("barrage", "8", "4", "2", "F"):
        if phase not in phases:
            break
        joues = [f for f in resultats if f.get("phase") == phase and moi in (f["a"], f["b"])]
        if not joues:
            return derniere or "ligue"
        gagnants = vainqueurs_phase(camp, resultats, phase)
        if gagnants is None:
            return phase                   # eliminated before the phase resolved
        if moi not in gagnants:
            return phase
        derniere = phase
    return "vainqueur" if derniere == "F" else (SUITE.get(derniere) or "vainqueur")


def cloturer(jeu, saison: str, campagne_id: int) -> dict:
    """Close a finished campaign and pay it.  Closing twice pays once."""
    camp = jeu.execute("SELECT * FROM campagne WHERE campagne_id=?", (campagne_id,)).fetchone()
    if camp is None:
        raise ErreurSolo("Campagne inconnue")
    if camp["statut"] == "fini":
        return json.loads(camp["recompenses"] or "{}")
    clubs = json.loads(camp["clubs"])
    cal = json.loads(camp["calendrier"])
    moi = camp["place"]
    resultats = json.loads(camp["resultats"] or "[]")
    miens = [f for f in resultats if f["mien"]]
    victoires = sum(1 for f in miens if (f["resultat"] == "A") == (f["a"] == moi))
    nuls = sum(1 for f in miens if f["resultat"] == "N")
    if COMPETITIONS[camp["cle"]]["format"] == "championnat":
        table = _table(camp, resultats, "championnat", len(clubs))
        rang = next(l["rang"] for l in table if l["place"] == moi)
        libelle, credits, packs = recompense_championnat(rang, len(clubs))
        detail = {"rang": rang, "sur": len(clubs)}
    else:
        cle = _sortie_europe(camp, resultats, cal, moi)
        libelle, credits, packs = RECOMPENSES_EUROPE[cle]
        table = _table(camp, resultats, "ligue", len(clubs))
        rang = next((l["rang"] for l in table if l["place"] == moi), None)
        detail = {"tour": libelle, "rang_ligue": rang, "sur": len(clubs)}
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
    # A live match whose ninety minutes are up closes the round HERE, before
    # anything else is read: otherwise the screen shows last round's fixture
    # for one more poll.
    from jeu import lobby as LB
    r = match_en_cours(jeu, camp)
    if r is not None and LB.minute_courante(r["debut"]) >= SM.MINUTES:
        cloturer_tour(jeu, saison, equipe_id)
        return etat(jeu, saison, equipe_id)
    live = (LB.feuille(jeu, saison, r) | {"duree": LB.DUREE_REELLE, "minutes": SM.MINUTES,
                                          "cote": "a", "domicile": bool(r["domicile"])}
            if r is not None else None)
    clubs = _clubs_du(jeu, saison, camp)
    cal = json.loads(camp["calendrier"])
    comp = COMPETITIONS[camp["cle"]]
    resultats = json.loads(camp["resultats"] or "[]")
    tour = camp["tour"]
    prochain = None
    if tour < len(cal):
        t = cal[tour]
        prochain = {"exempt": True, "tour": tour + 1, "tours": len(cal),
                    "phase": t["phase"], "libelle": t["libelle"], "manche": t["manche"]}
        for a, b in _duels_de(cal, tour):
            if camp["place"] in (a, b):
                adv = b if a == camp["place"] else a
                cumul = _cumul(resultats, t["phase"]).get(frozenset((a, b)))
                prochain |= {"exempt": False, "adversaire": clubs[adv],
                             "domicile": a == camp["place"],
                             "aller": (dict(zip(("moi", "lui"),
                                                (cumul["buts"].get(camp["place"], 0), cumul["buts"].get(adv, 0))))
                                       if cumul and t["manche"] == 2 else None)}
    c = {"campagne_id": camp["campagne_id"], "cle": camp["cle"], "nom": comp["nom"], "format": comp["format"],
         "match": live,
         "club_remplace": next((x["nom"] for x in clubs_competition(jeu, saison, camp["cle"])
                                if x["team_id"] == camp["club_remplace"]), ""),
         "place": camp["place"], "tour": tour, "tours": len(cal), "prochain": prochain,
         "phase": cal[min(tour, len(cal) - 1)]["phase"],
         "mes_matchs": [f | {"adversaire": clubs[f["b"] if f["a"] == camp["place"] else f["a"]]["nom"]}
                        for f in resultats if f["mien"]][-10:]}
    phase_table = "championnat" if comp["format"] == "championnat" else "ligue"
    c["classement"] = classement(camp, clubs, phase_table)
    if comp["format"] != "championnat":
        c["qualification"] = {"directs": DIRECTS, "barrages": BARRAGISTES}
        c["tableau"] = _tableau_ko(camp, clubs, cal, resultats)
    return base | {"campagne": c}


def _tableau_ko(camp, clubs: list[dict], cal: list[dict], resultats: list[dict]) -> list[dict]:
    """The knockout bracket as it stands: one entry per phase, each tie with
    its aggregate and, once both legs are in, its winner."""
    out = []
    for phase in ("barrage", "8", "4", "2", "F"):
        tours = [i for i, t in enumerate(cal) if t["phase"] == phase]
        if not tours:
            continue
        ties = _cumul(resultats, phase)
        gagnants = vainqueurs_phase(camp, resultats, phase)
        duels = _duels_de(cal, tours[0])
        lignes = []
        for i, (a, b) in enumerate(duels):
            t = ties.get(frozenset((a, b)))
            lignes.append({"a": clubs[a]["nom"], "b": clubs[b]["nom"],
                           "cumul": [t["buts"].get(a, 0), t["buts"].get(b, 0)] if t else None,
                           "manches": t["manches"] if t else 0,
                           "vainqueur": (clubs[gagnants[i]]["nom"] if gagnants and i < len(gagnants) else None),
                           "toi": camp["place"] in (a, b)})
        out.append({"phase": phase, "libelle": PHASES[phase], "ties": lignes})
    return out


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

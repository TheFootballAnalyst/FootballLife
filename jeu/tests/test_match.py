"""The head-to-head match: chances, cancellations, captain, Elo, pairing."""
from jeu import match as M


def joueur(pid, nom, poste, buts=0, cadres=0, note=6.0, lignes=None, passes=30):
    return {"pid": pid, "nom": nom, "poste": poste,
            "prestations": [{"note": note, "minutes": 90, "lignes": lignes or {},
                             "stats": {"buts": buts, "cadres": cadres, "passes": passes, "tirs": cadres + 2}}]}


def defense(pts):
    """A back line whose DEF lines are worth `pts` engine points."""
    return [joueur(90, "Gardien", "Gardien", lignes={"Arret": pts / 2}),
            joueur(91, "Stopper", "Defenseur central", lignes={"Interception": pts / 2})]


def test_real_goals_make_the_score_and_the_defence_cancels_the_weakest():
    A = [joueur(1, "Kane", "Buteur", buts=2, cadres=2, note=8.5), joueur(2, "Doue", "Ailier", buts=1, cadres=1, note=6.2)] + defense(0)
    B = [joueur(3, "Muriqi", "Buteur", buts=1, cadres=1, note=7.0)] + defense(M.SEUIL_ANNULATION * 1.0)
    f = M.feuille_de_match(A, B)
    assert f["score"] == [2, 1] and f["resultat"] == "A"
    annulee = [c for c in f["a"]["chances"] if c["annule"]]
    assert len(annulee) == 1 and annulee[0]["nom"] == "Doue" and annulee[0]["par"] in ("Gardien", "Stopper")
    assert f["a"]["totaux"]["buts"] == 3 and f["b"]["annulations"] == 0


def test_captain_goals_cannot_be_cancelled():
    A = [joueur(1, "Kane", "Buteur", buts=1, cadres=1, note=6.0)] + defense(0)
    B = defense(M.SEUIL_ANNULATION * 3)
    assert M.feuille_de_match(A, B)["score"] == [0, 0]
    assert M.feuille_de_match(A, B, capitaine_a=1)["score"] == [1, 0]


def test_unconverted_shots_on_target_add_chances():
    A = [joueur(1, "Haaland", "Buteur", buts=0, cadres=M.CADRES_PAR_CHANCE * 2, note=7.0)] + defense(0)
    B = defense(0)
    f = M.feuille_de_match(A, B)
    assert f["score"] == [2, 0]
    assert all(not c["but"] and c["nom"] == "Haaland" for c in f["a"]["chances"])
    # a missed chance is cancelled before a real goal
    A2 = [joueur(1, "Haaland", "Buteur", buts=1, cadres=1 + M.CADRES_PAR_CHANCE, note=7.0)] + defense(0)
    f2 = M.feuille_de_match(A2, defense(M.SEUIL_ANNULATION))
    assert f2["score"] == [1, 0] and [c["but"] for c in f2["a"]["chances"] if c["annule"]] == [False]


def test_sheet_is_deterministic_and_carries_possession():
    A = [joueur(1, "A", "Buteur", passes=60)] + defense(0)
    B = [joueur(2, "B", "Buteur", passes=40)] + defense(0)
    f1, f2 = M.feuille_de_match(A, B), M.feuille_de_match(A, B)
    assert f1 == f2 and f1["possession"] == [55, 45] and f1["resultat"] == "N"   # 120 passes vs 100


def test_elo_and_pairing():
    ra, rb = M.elo_maj(1000, 1000, "A")
    assert ra == 1016 and rb == 984
    ra2, rb2 = M.elo_maj(1200, 1000, "B")
    assert rb2 - 1000 > 16                       # an upset pays more
    assert M.elo_maj(1000, 1000, "N") == (1000, 1000)
    paires = M.apparier([(1, 1100), (2, 1000), (3, 1050), (4, 900), (5, 950)])
    assert paires == [(1, 3), (2, 5)]            # neighbours by Elo, 4 sits out
    assert M.apparier([(1, 1100), (2, 1000), (3, 1050)], {frozenset((1, 3))}) == [(1, 2)]

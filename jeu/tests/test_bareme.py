"""jeu/bareme.py on synthetic windows: the mapping from barème windows to
a terrain score, an OVR on the bell, six attributes, and a bounded move."""
import math

from jeu import bareme as B
from jeu import evolution as E

POSTES = ["Gardien", "Defenseur central", "Lateral", "Milieu defensif", "Milieu relayeur",
          "Milieu offensif", "Ailier", "Buteur"]


def fenetre(minutes, pts, tit=30, dispo=30, poste="Buteur", fin=None):
    axes = ({"ARR": pts * 0.6, "EVI": pts * 0.2, "SOR": pts * 0.1, "REL": 0.0, "BUT": pts * 0.1, "PRO": 0.0}
            if poste == "Gardien" else
            {"FIN": pts * 0.4 if fin is None else fin, "CRE": pts * 0.2, "PRO": pts * 0.1, "DEF": pts * 0.1,
             "DRI": pts * 0.1, "CON": pts * 0.1})
    return {"min": float(minutes), "pts": float(pts), "tit": tit, "dispo": dispo, "axes": axes}


def population(n=200):
    """n players: full seasons, barème points growing with the index, every
    position represented."""
    out = {}
    for i in range(n):
        poste = POSTES[i % len(POSTES)]
        out[i] = (poste, fenetre(2700, 100 + 4 * i, poste=poste))
    return out


def test_windows_add_and_fold_into_gameweeks():
    a = fenetre(90, 10)
    b = B.ajouter(a, fenetre(45, 5), 0.5)
    assert b["min"] == 112.5 and b["pts"] == 12.5 and b["axes"]["FIN"] == 4 + 1
    joueur = {"dates": {"2026-08-10": fenetre(90, 1), "2026-08-16": fenetre(90, 2),
                        "2026-08-30": fenetre(90, 4), "2027-06-05": fenetre(90, 8)}}
    js = [(1, "2026-08-14", "2026-08-20"), (2, "2026-08-21", "2026-08-27"), (3, "2026-08-28", "2026-09-03")]
    fs = B.fenetres_journees(joueur, js)
    # before the first gameweek -> the first; after the last -> the last; a gap -> the previous
    assert fs[1]["pts"] == 3 and 2 not in fs and fs[3]["pts"] == 12
    assert B.fenetre(joueur, "2026-08-16", "2026-08-30")["pts"] == 6


def test_parameters_and_ovr_follow_the_rank_on_a_bell():
    pop = population()
    params = B.parametres(pop)
    assert params["reguliers"] == 200 and set(params["priors"]) >= set(POSTES)
    ovrs = [B.carte_initiale(po, f, 0.0, params)["ovr"] for po, f in pop.values()]
    # monotonic in the points (the keepers are aligned, so within a position at least)
    for poste in POSTES:
        serie = [B.carte_initiale(po, f, 0.0, params)["ovr"] for po, f in pop.values() if po == poste]
        assert serie == sorted(serie)
    # a bell: the median regular reads MU, the top under 99, the bottom over 40
    assert abs(sorted(ovrs)[100] - E.MU_OVR) <= 2
    assert max(ovrs) <= E.OVR_MAX and min(ovrs) >= E.OVR_MIN and max(ovrs) >= 90 and min(ovrs) <= 45


def test_thin_samples_are_shrunk_to_the_position_and_subs_discounted():
    pop = population()
    params = B.parametres(pop)
    plein = B.terrain(fenetre(2700, 1000), "Buteur", params)
    mince = B.terrain(fenetre(90, 1000 / 30), "Buteur", params)       # same per 90, one match
    prior = params["priors"]["Buteur"]
    assert prior < mince < plein
    assert abs(mince - (90 / (90 + params["k_retrecissement"]) * (1000 / 2700 * 90)
                        + params["k_retrecissement"] / (90 + params["k_retrecissement"]) * prior)) < 1e-9
    remplacant = B.terrain(fenetre(2700, 1000, tit=3, dispo=30), "Buteur", params)
    assert remplacant < plein
    assert B.terrain(fenetre(0, 0, 0, 0), "Buteur", params) == prior


def test_palmares_enters_the_seed_only():
    pop = population()
    pal = {i: 100.0 * (i % 7) for i in pop}
    params = B.parametres(pop, pal)
    po, f = pop[150]
    avec = B.carte_initiale(po, f, 600.0, params)
    sans = B.carte_initiale(po, f, 0.0, params)
    assert avec["t"] > sans["t"] and avec["ovr"] >= sans["ovr"]
    # in season the move only depends on the terrain: same S move, same OVR move
    s_t = avec["s0"] + 3.0
    assert (B.ovr_courant(avec["ovr"], avec["s0"], s_t, params) - avec["ovr"]
            == B.ovr_courant(sans["ovr"], sans["s0"], s_t, params) - sans["ovr"])


def test_move_is_bounded_and_symmetric_around_the_seed():
    pop = population()
    params = B.parametres(pop)
    po, f = pop[100]
    ci = B.carte_initiale(po, f, 0.0, params)
    assert B.ovr_courant(ci["ovr"], ci["s0"], ci["s0"], params) == ci["ovr"]
    assert B.ovr_courant(ci["ovr"], ci["s0"], ci["s0"] * 10, params) == ci["ovr"] + E.BORNE_OVR
    assert B.ovr_courant(ci["ovr"], ci["s0"], -100.0, params) == ci["ovr"] - E.BORNE_OVR
    # a full extra season at the same level leaves the card where it started
    s, ovr, attrs, w = B.etat_courant(ci, f, po, params)
    assert abs(ovr - ci["ovr"]) <= 1 and 0 < w < 1


def test_attributes_rank_every_outfield_player_together():
    pop = population()
    params = B.parametres(pop)
    haut = B.attributs(fenetre(2700, 500, fin=2000.0), "Defenseur central", params)
    bas = B.attributs(fenetre(2700, 500, fin=0.0), "Buteur", params)
    assert haut["FIN"] > bas["FIN"] and set(haut) == set(B.AXES_CHAMP)
    gk = B.attributs(fenetre(2700, 500, poste="Gardien"), "Gardien", params)
    assert set(gk) == set(B.AXES_GARDIEN)
    for v in list(haut.values()) + list(gk.values()):
        assert 40 <= v <= 99


def test_rank_is_finite_at_both_ends():
    ech = [float(i) for i in range(11)]
    assert 0 < B.rang(-5.0, ech) < B.rang(5.0, ech) < B.rang(50.0, ech) < 1
    assert math.isfinite(B.cloche(-5.0, ech)) and math.isfinite(B.cloche(50.0, ech))

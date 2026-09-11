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


def population(n=200, frange=60):
    """n regulars with a full season, barème points growing with the index,
    every position represented, plus a tail of rotation players: a real
    pool has both, and the reference points are measured on each."""
    out = {}
    for i in range(n):
        poste = POSTES[i % len(POSTES)]
        out[i] = (poste, fenetre(2700, 100 + 4 * i, poste=poste))
    for i in range(frange):
        poste = POSTES[i % len(POSTES)]
        out[1000 + i] = (poste, fenetre(300, 10 + i, tit=2, dispo=12, poste=poste))
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
    assert 0 < params["role_inconnu"] < params["role_ref"] <= 1.0
    reg = [v for k, v in pop.items() if k < 1000]
    ovrs = [B.carte_initiale(po, f, 0.0, params)["ovr"] for po, f in reg]
    # monotonic in the points (the keepers are aligned, so within a position at least)
    for poste in POSTES:
        serie = [B.carte_initiale(po, f, 0.0, params)["ovr"] for po, f in reg if po == poste]
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
    # nobody at all: the position's median, read as a rotation player
    inconnu = B.terrain(fenetre(0, 0, 0, 0), "Buteur", params)
    assert inconnu == prior * min(1.0, params["role_inconnu"]) / params["role_ref"]
    assert inconnu < prior


def test_the_share_of_starts_is_shrunk_so_one_match_cannot_remake_a_card():
    """One start out of one sheet reads 1.00 raw, and a card seeded on
    nothing jumped eighteen OVR points on its first match."""
    pop = population()
    params = B.parametres(pop)
    ancre = params["role_inconnu"]
    assert B.part_role(B.fenetre_vide(), params) == ancre
    un_match = B.part_role(fenetre(90, 20, tit=1, dispo=1), params)
    assert ancre < un_match < ancre + 0.1              # a nudge, not a verdict
    saison = B.part_role(fenetre(2700, 600, tit=30, dispo=32), params)
    assert saison > 0.75                                # a real season decides it
    # and a rotation player still reads as one
    assert B.part_role(fenetre(900, 200, tit=3, dispo=30), params) < un_match


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
    # a full extra season at the same level leaves the card at that level
    s, ovr, attrs, w = B.etat_courant(ci, f, po, params)
    blend = B.ajouter(f, ci["base"], params["poids_passe"])
    assert abs(B.par90(blend) - B.par90(f)) < 1e-9        # same football
    # what little the OVR moves is role confidence, not performance: the
    # share of starts is shrunk (part_role) and a second season of starting
    # every week settles it.  On the 2025/26 replay the median move over
    # nine gameweeks is zero (docs/BACKTEST.md).
    assert abs(ovr - ci["ovr"]) < ci["borne"] and 0 < w < 1


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


def test_attribute_bell_puts_the_median_in_the_middle():
    """40 + 59 x rank put the median player at 70 on every axis, so a
    position's own specialty read 92 before the player had done anything."""
    pop = population()
    params = B.parametres(pop)
    ech = params["echelles"]["champ"]["FIN"]
    median = ech[len(ech) // 2]
    assert abs(B.attribut(median, ech, params) - E.MU_ATTR) <= 1
    # the 90th percentile of an axis — where a position's specialty sits —
    # reads in the seventies, not in the nineties
    assert 68 <= B.attribut(ech[int(0.90 * len(ech))], ech, params) <= 80
    assert B.attribut(ech[-1], ech, params) >= 90 and B.attribut(ech[0], ech, params) <= 45
    # still monotone, so the cross-position order is untouched
    serie = [B.attribut(v, ech, params) for v in ech]
    assert serie == sorted(serie)


def test_rank_is_finite_at_both_ends():
    ech = [float(i) for i in range(11)]
    assert 0 < B.rang(-5.0, ech) < B.rang(5.0, ech) < B.rang(50.0, ech) < 1
    assert math.isfinite(B.cloche(-5.0, ech)) and math.isfinite(B.cloche(50.0, ech))


def test_the_breakdown_lands_on_the_card_it_explains():
    """A detail panel that does not reproduce the card is worse than none:
    it would teach a wrong rule.  `detail` walks the same functions."""
    pop = population()
    pal = {i: 100.0 * (i % 7) for i in pop}
    params = B.parametres(pop, pal)
    for i in (0, 37, 150, 199, 1000, 1040):
        poste, f = pop[i]
        ci = B.carte_initiale(poste, f, pal[i], params)
        saison = fenetre(720, 180, tit=7, dispo=8, poste=poste)
        s, ovr, attrs, _w = B.etat_courant(ci, saison, poste, params)
        d = B.detail(ci, saison, poste, params)
        assert d["saison"]["ovr"] == ovr
        assert {a["axe"]: a["valeur"] for a in d["axes"]} == attrs
        assert d["depart"]["ovr"] == ci["ovr"]
        # the steps add up: the seed chain ends on the stored S25
        assert abs(d["depart"]["terrain"]["s"] - ci["s25"]) < 1e-3
        assert abs(d["depart"]["t_terrain"] + d["depart"]["t_palmares"] - ci["t"]) < 0.02
        # and the move is the bounded difference of the two bell readings
        sa = d["saison"]
        assert abs(sa["mouvement"] - max(-sa["borne"], min(sa["borne"], sa["mouvement_brut"]))) < 1e-6
        # every axis names the barème lines it is made of
        for a in d["axes"]:
            assert a["cles"] and 0 < a["rang"] < 1


def test_a_card_seeded_on_nothing_can_still_be_explained():
    pop = population()
    params = B.parametres(pop)
    ci = B.carte_initiale("Ailier", B.fenetre_vide(), 0.0, params)
    d = B.detail(ci, B.fenetre_vide(), "Ailier", params)
    assert d["saison"]["ovr"] == ci["ovr"] and d["depart"]["terrain"]["minutes"] == 0
    assert d["saison"]["borne"] == ci["borne"]        # the widened bound is the one shown

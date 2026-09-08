import json

from jeu import notation as N


def test_anchors_map_to_their_notes():
    seuils = N.charger_seuils()
    s = seuils["Buteur"]
    for valeur, attendu in s.ancres():
        assert N.note_brute(valeur, s) == attendu


def test_interpolation_is_monotonic_and_bounded():
    s = N.charger_seuils()["Ailier"]
    prev = None
    for v in range(-100, 200):
        n = N.note_brute(float(v), s)
        assert N.NOTE_MIN <= n <= N.NOTE_MAX
        if prev is not None:
            assert n >= prev
        prev = n


def test_short_cameo_cannot_reach_extremes():
    # A monster performance in 14 minutes: note pulled back towards 6.
    seuils = N.charger_seuils()
    s = seuils["Buteur"]
    brut = s.p90 * 3          # far beyond p90
    plein = N.note_sur_10(brut, 1.0, "Buteur", 90)
    court = N.note_sur_10(brut, 1.0, "Buteur", 14)
    assert plein > 8.5
    assert 6 < court < 8
    # And a disaster in 14 minutes cannot be a 3.
    assert N.note_sur_10(s.p10 * 3, 1.0, "Buteur", 14) > 4.0


def test_competition_coef_is_neutralised():
    # Same neutral performance in Ligue 1 (coef 0.634) and UCL (coef 2.0).
    s = N.charger_seuils()["Milieu relayeur"]
    neutre = s.p75
    n_l1 = N.note_sur_10(neutre * 0.634, 0.634, "Milieu relayeur", 90)
    n_ucl = N.note_sur_10(neutre * 2.0, 2.0, "Milieu relayeur", 90)
    assert n_l1 == n_ucl == 7.0


def test_winger_sides_share_thresholds():
    assert N.note_sur_10(10.0, 1.0, "Ailier droit", 90) == \
        N.note_sur_10(10.0, 1.0, "Ailier gauche", 90) == \
        N.note_sur_10(10.0, 1.0, "Ailier", 90)


def test_unknown_position_gives_none():
    assert N.note_sur_10(10.0, 1.0, "Libero", 90) is None


def test_attribute_scale_bounds():
    ech = N.charger_echelles()["champ"]["FIN"]
    assert N.attribut(-999, ech) == 40
    assert N.attribut(999, ech) == 99


def test_floor_on_mostly_zero_families():
    """One shot on target must not read as elite finishing (REPONSES.md §2)."""
    ech = N.charger_echelles()["champ"]["FIN"]
    un_tir_cadre = 1.3            # "Tir cadre" line, coef 1
    assert 65 <= N.attribut(un_tir_cadre, ech) <= 75
    # Zero stays in the lower band, well under the plateau's top.
    assert N.attribut(0.0, ech) < 60
    # Reference values from the delivered code: floor active on FIN.
    assert N.rang_percentile(0.0, ech) < 0.30


def test_families_table_matches_engine_labels():
    """Every label of familles_lignes.json must be one the engine can write,
    and the two shared labels must sit in both PRO and REL."""
    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "moteur"))
    import bareme_stats as B
    moteur = {lib for table in B.POINTS.values() for lib, _ in table.values()}
    moteur |= {v[0] for v in B.FRACTIONS.values()}
    moteur |= {"Surperformance de finition (G - xG)", "Clean sheet",
               "Duels defensifs (taux vs reference)"}
    fam = N.charger_familles()
    assert len(fam) == 11
    assert sum(len(v) for v in fam.values()) == 41
    inconnus = {l for libs in fam.values() for l in libs} - moteur
    assert not inconnus, inconnus
    inv = N.familles_du_libelle()
    assert sorted(inv["Passe reussie"]) == ["PRO", "REL"]
    assert sorted(inv["Long ballon reussi"]) == ["PRO", "REL"]


def test_attributes_have_six_axes_for_both_kinds():
    lignes = {"But": 6.34, "Passe reussie": 1.2, "Interception": 0.5}
    champ = N.attributs(lignes, 0.634, "Buteur")
    assert set(champ) == set(N.AXES_CHAMP)
    assert champ["FIN"] > champ["DEF"]
    gk = N.attributs({"Arret": 3.0, "Passe reussie": 1.0}, 1.0, "Gardien")
    assert set(gk) == set(N.AXES_GARDIEN)
    assert gk["REL"] > 40 and gk["PRO"] > 40   # shared label feeds both


def test_prestation_helpers_accept_topsflops_rows():
    p = {"nom": "X", "poste": "Lateral", "minutes": 90, "brut": 12.0,
         "coef": 0.634, "lignes": {"Passe reussie": 0.8, "Interception": 0.76}}
    assert N.note_prestation(p) is not None
    attrs = N.attributs_prestation(p)
    assert len(attrs) == 6
    json.dumps(attrs)  # serialisable

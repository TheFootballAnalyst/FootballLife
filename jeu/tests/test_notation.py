import json
import pathlib

from jeu import notation as N


def test_anchors_map_to_their_notes():
    seuils = N.charger_seuils()
    s = seuils["Buteur"]
    for valeur, attendu in s.ancres():
        assert abs(N.note_brute(valeur, s) - attendu) < 1e-9


def test_curve_is_monotonic_and_saturates():
    s = N.charger_seuils()["Ailier"]
    prev = None
    for v in range(-300, 600):
        n = N.note_brute(float(v), s)
        assert 1.0 <= n < 10.0
        if prev is not None:
            assert n >= prev
        prev = n
    # far beyond p90 the note approaches 10 without reaching it
    assert 9.7 < N.note_brute(s.p90 * 40, s) < 10.0


def test_short_cameo_cannot_reach_extremes():
    seuils = N.charger_seuils()
    s = seuils["Buteur"]
    pts = s.p90 * 3          # far beyond p90
    plein = N.note_sur_10(pts, "Buteur", 90)
    court = N.note_sur_10(pts, "Buteur", 14)
    assert plein > 8.5
    assert 6 < court < 8
    # And a disaster in 14 minutes cannot be a 3.
    assert N.note_sur_10(s.p10 * 3, "Buteur", 14) > 4.0


def test_winger_sides_share_thresholds():
    assert N.note_sur_10(10.0, "Ailier droit", 90) == \
        N.note_sur_10(10.0, "Ailier gauche", 90) == \
        N.note_sur_10(10.0, "Ailier", 90)


def test_unknown_position_gives_none():
    assert N.note_sur_10(10.0, "Libero", 90) is None


def test_reference_values_from_the_visual_pipeline():
    """Performances rated by the production pipeline (40 tops, 65 flops and
    edge cases): note and six attributes must match exactly."""
    fichiers = sorted((pathlib.Path(__file__).parent / "donnees").glob("controle_*.json"))
    assert len(fichiers) >= 2
    ecarts, n = [], 0
    for f in fichiers:
        for row in json.loads(f.read_text(encoding="utf-8"))["prestations"]:
            m, e = row["moteur"], row["attendu"]
            note = N.note_prestation(m)
            att = N.attributs_prestation(m)
            n += 1
            if abs(note - e["note_sur_10"]) > 0.051 or att != e["attributs"]:
                ecarts.append((f.name, e["nom"], note, e["note_sur_10"], att, e["attributs"]))
    assert n >= 100
    assert not ecarts, ecarts


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
    assert sum(len(v) for v in fam.values()) == 39    # "Duel gagne" left DRI, "Duel au sol gagne" left DEF
    inconnus = {l for libs in fam.values() for l in libs} - moteur
    assert not inconnus, inconnus
    inv = N.familles_du_libelle()
    assert sorted(inv["Passe reussie"]) == ["PRO", "REL"]
    assert sorted(inv["Long ballon reussi"]) == ["PRO", "REL"]


def test_attributes_have_six_axes_for_both_kinds():
    lignes = {"But": 6.34, "Passe reussie": 1.2, "Interception": 0.5}
    champ = N.attributs(lignes, "Buteur")
    assert set(champ) == set(N.AXES_CHAMP)
    assert champ["FIN"] > champ["DEF"]
    gk = N.attributs({"Arret": 3.0, "Passe reussie": 1.0}, "Gardien")
    assert set(gk) == set(N.AXES_GARDIEN)
    assert gk["REL"] > 40 and gk["PRO"] > 40   # shared label feeds both


def test_prestation_helpers_accept_topsflops_rows():
    p = {"nom": "X", "poste": "Lateral", "minutes": 90, "brut": 12.0,
         "coef": 0.634, "points": 25.7,
         "lignes": {"Passe reussie": 0.8, "Interception": 0.76}}
    assert N.note_prestation(p) is not None
    attrs = N.attributs_prestation(p)
    assert len(attrs) == 6
    json.dumps(attrs)  # serialisable


def test_season_attributes_rank_seasons_and_shrink_thin_samples():
    e = N.charger_echelles()["saison"]["champ"]
    # the season scale exists for the six outfield families and the six goalkeeper ones
    assert set(e) == set(N.AXES_CHAMP) and set(N.charger_echelles()["saison"]["gardien"]) == set(N.AXES_GARDIEN)
    # a striker's season: lots of finishing per 90, little defence
    a = N.attributs_saison({"FIN": 300.0, "DEF": 10.0}, 20.0, "Buteur")     # 15 finishing points per 90
    assert a["FIN"] >= 90 and a["DEF"] < 60
    # an empty season sits at the cautious prior, under the median
    vide = N.attributs_saison({}, 0.0, "Buteur")
    assert all(52 <= v <= 62 for v in vide.values())
    # one match is shrunk towards the median: the same per-90 rate reads lower than over 20 matches
    court = N.attributs_saison({"FIN": 15.0}, 1.0, "Buteur")["FIN"]
    long_ = N.attributs_saison({"FIN": 300.0}, 20.0, "Buteur")["FIN"]
    assert vide["FIN"] < court < long_

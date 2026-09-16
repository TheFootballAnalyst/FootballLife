"""The weekly pipeline on a tiny synthetic season: seed, one gameweek,
idempotence, payout, auto-sub, lock."""
import json
import pathlib
import sqlite3

import pytest

from jeu import evolution as E
from jeu import importer as I
from jeu import pipeline as P

SCHEMA = pathlib.Path(__file__).resolve().parents[1] / "schema.sql"
POSTES = ["Gardien", "Defenseur central", "Defenseur central", "Lateral", "Lateral",
          "Milieu defensif", "Milieu relayeur", "Milieu offensif", "Ailier", "Buteur", "Ailier",
          "Gardien", "Defenseur central", "Milieu relayeur", "Buteur"]


def base():
    jeu = sqlite3.connect(":memory:")
    jeu.executescript(SCHEMA.read_text(encoding="utf-8"))
    jeu.execute("INSERT INTO competition VALUES (53, 'Ligue 1', '2025/26')")
    jeu.execute("INSERT INTO club(team_id, nom) VALUES (1, 'A')")
    jeu.execute("INSERT INTO club(team_id, nom) VALUES (2, 'B')")
    for i, poste in enumerate(POSTES, 1):
        jeu.execute("INSERT INTO joueur(player_id, nom, nom_normalise, team_id, poste) VALUES (?, ?, ?, 1, ?)",
                    (i, f"J{i}", f"j{i}", poste))
    # market values: players 1-10 have one (i M€ on the seed date), 11-15 are estimated
    for i in range(1, 11):
        jeu.execute("INSERT INTO valeur_marche VALUES (?, '2025-01-01', ?)", (i, float(i)))
    jeu.execute("INSERT INTO valeur_marche VALUES (1, '2025-08-20', 99.0)")      # after the seed: ignored
    # source season with one gameweek of performances: everyone 6.0 x 90 min
    jeu.execute("INSERT INTO journee(saison, numero, du, au, cloture, calculee) VALUES ('2024/25', 1, '2025-01-01', '2025-01-07', '2025-01-01T20:00:00Z', 1)")
    js = jeu.execute("SELECT journee_id FROM journee WHERE saison='2024/25'").fetchone()[0]
    jeu.execute("INSERT INTO match VALUES (100, ?, 53, '2025-01-01T20:00:00Z', 'Phase reguliere', 1, 2, 1, 0)", (js,))
    for i in range(1, 16):
        jeu.execute("""INSERT INTO prestation(match_id, player_id, team_id, poste, minutes, entrant, brut, coef, points, note, statut, lignes, attributs)
                       VALUES (100, ?, 1, ?, 90, 0, 10, 1, 20, 6.0, 'ok', '{}', '{}')""", (i, POSTES[i - 1]))
        # the season barème of the source season: a full season each, player i
        # worth 100 + 20 i points, his axes spread so the attributes differ
        fenetre_bareme(jeu, js, i, 2700, 100 + 20 * i, tit=30, dispo=30)
    # live season: gameweek 0 (seed) and 1
    jeu.execute("INSERT INTO journee(saison, numero, du, au, cloture, calculee) VALUES ('2025/26', 0, '2025-08-01', '2025-08-01', '2025-08-01T00:00:00Z', 0)")
    jeu.execute("INSERT INTO journee(saison, numero, du, au, cloture, calculee) VALUES ('2025/26', 1, '2025-08-15', '2025-08-21', '2025-08-15T18:45:00Z', 0)")
    jeu.commit()
    return jeu


def fenetre_bareme(jeu, jid, pid, minutes, pts, tit=1, dispo=1, axes=None, poste=None):
    """One bareme_journee row (a player's window over a gameweek)."""
    poste = poste or POSTES[pid - 1]
    if axes is None:
        if poste == "Gardien":
            axes = {"ARR": pts * 0.5, "EVI": pts * 0.2, "SOR": pts * 0.1, "REL": 0.0, "BUT": -pts * 0.1, "PRO": 0.0}
        else:
            axes = {"FIN": 400 * pid / 15, "CRE": pts * 0.2, "PRO": pts * 0.2, "DEF": 400 * (16 - pid) / 15,
                    "DRI": pts * 0.1, "CON": pts * 0.1}
    jeu.execute("INSERT OR REPLACE INTO bareme_journee(journee_id, player_id, minutes, points, tit, dispo, axes) VALUES (?,?,?,?,?,?,?)",
                (jid, pid, minutes, pts, tit, dispo, json.dumps(axes)))


def equipe_et_compo(jeu, soumise="2025-08-15T10:00:00Z"):
    jeu.execute("INSERT INTO utilisateur(pseudo, cree_le) VALUES ('toi', 'x')")
    jeu.execute("INSERT INTO ligue_jeu(nom, saison, perimetre, cree_le) VALUES ('L', '2025/26', '[53]', 'x')")
    jeu.execute("INSERT INTO equipe(utilisateur_id, ligue_jeu_id, nom, budget) VALUES (1, 1, 'Mon équipe', 60)")
    j1 = P.journee_id(jeu, "2025/26", 1)
    jeu.execute("""INSERT INTO composition VALUES (1, ?, '4-3-3', ?, ?, 10, ?)""",
                (j1, json.dumps(list(range(1, 12))), json.dumps([12, 13, 14, 15]), soumise))
    jeu.commit()
    return j1


def prestations_j1(jeu, notes):
    j1 = P.journee_id(jeu, "2025/26", 1)
    jeu.execute("INSERT INTO match VALUES (200, ?, 53, '2025-08-15T18:45:00Z', 'Phase reguliere', 1, 2, 2, 2)", (j1,))
    for pid, (note, minutes) in notes.items():
        jeu.execute("""INSERT INTO prestation(match_id, player_id, team_id, poste, minutes, entrant, brut, coef, points, note, statut, lignes, attributs)
                       VALUES (200, ?, 1, ?, ?, 0, 10, 1, 20, ?, 'ok', '{}', '{}')""", (pid, POSTES[pid - 1], minutes, note))
    jeu.commit()


def test_seed_writes_cards_and_scale():
    jeu = base()
    n, params = P.amorcer(jeu, "2025/26", "2024/25", ligues=(53,))
    assert n == 15
    assert P.parametre(jeu, "2025/26", "bareme")["reguliers"] == params["reguliers"] == 15
    # the card keeps its seed record; its terrain score is the seed's s0
    note, bareme = jeu.execute("SELECT note_ovr, bareme FROM carte WHERE player_id=1").fetchone()
    ci = json.loads(bareme)
    assert abs(note - ci["s0"]) < 1e-3 and ci["base"]["min"] == 2700 and ci["pal"] == 0
    assert jeu.execute("SELECT COUNT(*) FROM carte_historique").fetchone()[0] == 15
    # more barème points per 90 = a higher OVR, on a bell centred on the median
    ovrs = dict(jeu.execute("SELECT player_id, ovr FROM carte"))
    assert ovrs[15] > ovrs[8] > ovrs[2]
    assert E.OVR_MIN <= min(ovrs.values()) and max(ovrs.values()) <= E.OVR_MAX


def test_gameweek_scores_pays_and_is_idempotent():
    jeu = base()
    P.amorcer(jeu, "2025/26", "2024/25", ligues=(53,))
    equipe_et_compo(jeu)
    # striker 10 (captain) did not play; bench 15 (striker) did; everyone else 7.0
    notes = {i: (7.0, 90) for i in range(1, 10)}
    notes[11] = (7.0, 90)
    notes[15] = (8.0, 90)
    prestations_j1(jeu, notes)
    fenetre_bareme(jeu, P.journee_id(jeu, "2025/26", 1), 1, 90, 60.0)
    jeu.commit()
    r = P.calculer(jeu, None, "2025/26", 1, importer=False)
    # 10 starters x 7 + sub 15 at 8 (captain absent, no bonus) = 78
    assert r["scores"] == [(1, 78.0)]
    budget, pts = jeu.execute("SELECT budget, points_total FROM equipe WHERE equipe_id=1").fetchone()
    assert pts == 78.0 and abs(budget - (60 + E.gain_semaine(78.0))) < 1e-9
    res = jeu.execute("SELECT score, gain, rang, onze FROM resultat").fetchone()
    assert res[0] == 78.0 and res[2] == 1 and 15 in json.loads(res[3]) and 10 not in json.loads(res[3])
    # cards: player 1 (a barème window this gameweek) moved, player 10 (none) did not
    n1 = jeu.execute("SELECT note_ovr FROM carte WHERE player_id=1").fetchone()[0]
    n10 = jeu.execute("SELECT note_ovr FROM carte WHERE player_id=10").fetchone()[0]
    s0 = {pid: json.loads(b)["s0"] for pid, b in jeu.execute("SELECT player_id, bareme FROM carte")}
    assert n1 > s0[1] + 1e-6 and abs(n10 - s0[10]) < 1e-3
    assert 0 < jeu.execute("SELECT poids FROM carte WHERE player_id=1").fetchone()[0] < 1
    assert jeu.execute("SELECT calculee FROM journee WHERE numero=1 AND saison='2025/26'").fetchone()[0] == 1
    # run again: nothing changes
    P.calculer(jeu, None, "2025/26", 1, importer=False)
    budget2, pts2 = jeu.execute("SELECT budget, points_total FROM equipe WHERE equipe_id=1").fetchone()
    assert (budget2, pts2) == (budget, pts)
    assert jeu.execute("SELECT COUNT(*) FROM carte_historique").fetchone()[0] == 30
    assert abs(jeu.execute("SELECT note_ovr FROM carte WHERE player_id=1").fetchone()[0] - n1) < 1e-9


def test_composition_after_lock_is_refused():
    jeu = base()
    P.amorcer(jeu, "2025/26", "2024/25", ligues=(53,))
    equipe_et_compo(jeu, soumise="2025-08-15T19:00:00Z")      # after the 18:45 kick-off
    prestations_j1(jeu, {i: (7.0, 90) for i in range(1, 12)})
    r = P.calculer(jeu, None, "2025/26", 1, importer=False)
    assert r["scores"] == [(1, 0.0)]
    detail = json.loads(jeu.execute("SELECT detail FROM resultat").fetchone()[0])
    assert "refusee" in detail


def test_dry_run_writes_nothing():
    jeu = base()
    P.amorcer(jeu, "2025/26", "2024/25", ligues=(53,))
    equipe_et_compo(jeu)
    prestations_j1(jeu, {i: (7.0, 90) for i in range(1, 12)})
    r = P.calculer(jeu, None, "2025/26", 1, dry_run=True, importer=False)
    assert r["scores"] == [(1, 77.0 + 7.0 * 0.5)]      # captain 10 played: 11 x 7 + 3.5
    assert jeu.execute("SELECT COUNT(*) FROM resultat").fetchone()[0] == 0
    assert jeu.execute("SELECT calculee FROM journee WHERE numero=1 AND saison='2025/26'").fetchone()[0] == 0


def test_demand_raises_the_price_of_owned_cards():
    jeu = base()
    P.amorcer(jeu, "2025/26", "2024/25", ligues=(53,))
    equipe_et_compo(jeu)
    # a second team owning player 1 too, a third owning nobody: share(1) = 2/3
    jeu.execute("INSERT INTO utilisateur(pseudo, cree_le) VALUES ('lui', 'x')")
    jeu.execute("INSERT INTO utilisateur(pseudo, cree_le) VALUES ('elle', 'x')")
    jeu.execute("INSERT INTO equipe(utilisateur_id, ligue_jeu_id, nom, budget) VALUES (2, 1, 'B', 60)")
    jeu.execute("INSERT INTO equipe(utilisateur_id, ligue_jeu_id, nom, budget) VALUES (3, 1, 'C', 60)")
    for eid in (1, 2):
        jeu.execute("INSERT INTO exemplaire(player_id, saison, numero, equipe_id, dans_effectif, origine, prix_achat, achete_le) VALUES (1, '2025/26', ?, ?, 1, 'pack', 1.0, 'x')", (eid, eid))
    jeu.execute("INSERT INTO exemplaire(player_id, saison, numero, equipe_id, dans_effectif, origine, prix_achat, achete_le) VALUES (2, '2025/26', 1, 1, 1, 'pack', 1.0, 'x')")
    prestations_j1(jeu, {i: (6.0, 90) for i in range(1, 12)})
    P.calculer(jeu, None, "2025/26", 1, importer=False)
    ovr1, prix1, part1, vb1, ob1 = jeu.execute("SELECT ovr, prix, part, valeur_base, ovr_base FROM carte WHERE player_id=1").fetchone()
    ovr3, prix3, part3, vb3, ob3 = jeu.execute("SELECT ovr, prix, part, valeur_base, ovr_base FROM carte WHERE player_id=3").fetchone()
    assert abs(part1 - 2 / 3) < 1e-9 and part3 == 0
    assert prix1 == E.prix_demande(vb1, ob1, ovr1, 2 / 3)
    assert prix1 == E.prix_carte(vb1, ob1, ovr1)            # DEMANDE is 0: the cote ignores popularity
    assert E.prix_demande(vb1, ob1, ovr1, 2 / 3, k=1.0) > prix1
    assert prix3 == E.prix_carte(vb3, ob3, ovr3)
    h = jeu.execute("SELECT prix, part FROM carte_historique ch JOIN journee j ON j.journee_id = ch.journee_id WHERE ch.player_id=1 AND j.numero=1").fetchone()
    assert h == (prix1, part1)


def test_gameweek_needs_previous_state():
    jeu = base()
    P.amorcer(jeu, "2025/26", "2024/25", ligues=(53,))
    jeu.execute("INSERT INTO journee(saison, numero, du, au, cloture, calculee) VALUES ('2025/26', 2, '2025-08-22', '2025-08-28', '2025-08-22T18:45:00Z', 0)")
    with pytest.raises(SystemExit):
        P.calculer(jeu, None, "2025/26", 2, importer=False)


def test_seed_prices_start_at_the_market_value_known_at_seed_time():
    jeu = base()
    I.ecrire_valeurs(jeu, [(1, "2025-01-02", 1.0, 27, "9", "FRA")])
    assert jeu.execute("SELECT age, numero, pays FROM joueur WHERE player_id=1").fetchone() == (27, "9", "FRA")
    P.amorcer(jeu, "2025/26", "2024/25", ligues=(53,))
    rows = {pid: (vb, ob, ovr, prix) for pid, vb, ob, ovr, prix in
            jeu.execute("SELECT player_id, valeur_base, ovr_base, ovr, prix FROM carte")}
    assert rows[5][0] == 5.0 and rows[5][3] == 5.0 and rows[5][1] == rows[5][2]
    # the seed only knows the value on or before its last day: a later one is ignored
    limite = jeu.execute("SELECT au FROM journee WHERE saison='2024/25' AND numero=1").fetchone()[0]
    assert limite == "2025-01-07"
    P.amorcer(jeu, "2025/26", "2024/25", journees_source=(1, 1), ligues=(53,))
    assert jeu.execute("SELECT valeur_base FROM carte WHERE player_id=1").fetchone()[0] == 1.0
    # players without a value are priced from the OVR fit, never below the floor
    vb11 = jeu.execute("SELECT valeur_base FROM carte WHERE player_id=11").fetchone()[0]
    assert vb11 >= E.PRIX_PLANCHER
    prm = P.parametre(jeu, "2025/26", "valeur_marche")
    assert prm["connues"] == 10 and prm["estimees"] == 5


def test_composition_carries_over_to_the_next_gameweek():
    jeu = base()
    jeu.execute("INSERT INTO journee(saison, numero, du, au, cloture, calculee) VALUES ('2025/26', 2, '2025-08-22', '2025-08-28', '2025-08-22T18:45:00Z', 0)")
    equipe_et_compo(jeu)
    P.amorcer(jeu, "2025/26", "2024/25", ligues=(53,))
    prestations_j1(jeu, {i: (7.0, 90) for i in range(1, 12)})
    P.calculer(jeu, None, "2025/26", 1, importer=False)
    j2 = P.journee_id(jeu, "2025/26", 2)
    row = jeu.execute("SELECT formation, titulaires, capitaine FROM composition WHERE equipe_id=1 AND journee_id=?", (j2,)).fetchone()
    assert row is not None and row[0] == "4-3-3" and json.loads(row[1]) == list(range(1, 12)) and row[2] == 10
    # closing again does not overwrite what the manager may have changed since
    jeu.execute("UPDATE composition SET capitaine=9 WHERE equipe_id=1 AND journee_id=?", (j2,))
    jeu.commit()
    P.calculer(jeu, None, "2025/26", 1, importer=False)
    assert jeu.execute("SELECT capitaine FROM composition WHERE equipe_id=1 AND journee_id=?", (j2,)).fetchone()[0] == 9


def test_ovr_is_bounded_around_the_season_start():
    jeu = base()
    equipe_et_compo(jeu)
    P.amorcer(jeu, "2025/26", "2024/25", ligues=(53,))
    ob = dict(jeu.execute("SELECT player_id, ovr_base FROM carte"))
    prestations_j1(jeu, {i: (6.0, 90) for i in range(1, 12)})
    # player 2 has a monstrous gameweek, player 3 a disastrous one (barème points over 90 min)
    j1 = P.journee_id(jeu, "2025/26", 1)
    fenetre_bareme(jeu, j1, 2, 90, 5000.0)
    fenetre_bareme(jeu, j1, 3, 90, -5000.0)
    jeu.commit()
    P.calculer(jeu, None, "2025/26", 1, importer=False)
    ovr = dict(jeu.execute("SELECT player_id, ovr FROM carte"))
    s = dict(jeu.execute("SELECT player_id, note_ovr FROM carte"))
    bar = {pid: json.loads(b) for pid, b in jeu.execute("SELECT player_id, bareme FROM carte")}
    s0 = {pid: b["s0"] for pid, b in bar.items()}
    assert s[2] > s0[2] and s[3] < s0[3]
    # the bound is the card's own: BORNE_OVR for a full season behind it,
    # wider for a thin seed (jeu.bareme.borne)
    m2, m3 = round(bar[2]["borne"]), round(bar[3]["borne"])
    assert E.BORNE_OVR <= m2 <= E.BORNE_NOUVEAU
    assert ovr[2] == ob[2] + m2 and ovr[3] == max(E.OVR_MIN, ob[3] - m3)
    assert ovr[4] == ob[4]                     # nothing played, nothing moved
    # the season-to-date window is kept on the card and in the history
    som, m90 = jeu.execute("SELECT sommes, min90 FROM carte WHERE player_id=2").fetchone()
    assert json.loads(som)["pts"] == 5000.0 and m90 == 1.0

def recrue(jeu, pid=16, poste="Buteur", club_avant=3, valeur=None):
    """A player who is not in the perimeter at seeding time: he plays for a
    club outside the five leagues (or nowhere at all)."""
    jeu.execute("INSERT OR IGNORE INTO club(team_id, nom) VALUES (?,?)", (club_avant, f"Hors périmètre {club_avant}"))
    jeu.execute("INSERT INTO joueur(player_id, nom, nom_normalise, team_id, poste) VALUES (?,?,?,?,?)",
                (pid, f"Recrue{pid}", f"recrue{pid}", club_avant, poste))
    if valeur is not None:
        jeu.execute("INSERT INTO valeur_marche VALUES (?, '2025-01-01', ?)", (pid, valeur))
    jeu.commit()
    return pid


def joue_la_journee(jeu, pid, poste="Buteur", minutes=90, pts=200.0, note=7.0, team=1):
    """The newcomer plays gameweek 1 for a club of the perimeter."""
    j1 = P.journee_id(jeu, "2025/26", 1)
    jeu.execute("""INSERT INTO prestation(match_id, player_id, team_id, poste, minutes, entrant, brut, coef, points, note, statut, lignes, attributs)
                   VALUES (200, ?, ?, ?, ?, 0, 10, 1, 20, ?, 'ok', '{}', '{}')""", (pid, team, poste, minutes, note))
    fenetre_bareme(jeu, j1, pid, minutes, pts, poste=poste)
    jeu.commit()


def test_mercato_opens_a_card_for_a_newcomer_to_the_perimeter():
    jeu = base()
    pid = recrue(jeu, valeur=30.0)
    P.amorcer(jeu, "2025/26", "2024/25", ligues=(53,))
    assert jeu.execute("SELECT COUNT(*) FROM carte WHERE player_id=?", (pid,)).fetchone()[0] == 0
    prestations_j1(jeu, {i: (6.0, 90) for i in range(1, 12)})
    joue_la_journee(jeu, pid)
    r = P.calculer(jeu, None, "2025/26", 1, importer=False)
    assert r["nouvelles_cartes"] == 1 and r["clubs_maj"] == 1
    ovr, prix, vb, arrivee, bar = jeu.execute(
        "SELECT ovr, prix, valeur_base, arrivee, bareme FROM carte WHERE player_id=?", (pid,)).fetchone()
    # priced on his real market value, entered on gameweek 1, seeded on nothing
    assert vb == 30.0 and arrivee == 1 and E.OVR_MIN <= ovr <= E.OVR_MAX
    assert json.loads(bar)["base"]["min"] == 0 and json.loads(bar)["pal"] == 0
    # and his gameweek counted: the card moved from its own seed
    assert jeu.execute("SELECT min90 FROM carte WHERE player_id=?", (pid,)).fetchone()[0] == 1.0
    # recomputing the gameweek does not open a second card
    P.calculer(jeu, None, "2025/26", 1, importer=False)
    assert jeu.execute("SELECT COUNT(*) FROM carte WHERE player_id=?", (pid,)).fetchone()[0] == 1


def test_mercato_keeps_the_source_season_of_a_signing_from_a_covered_league():
    jeu = base()
    connu, inconnu = recrue(jeu, 16), recrue(jeu, 17)
    # the engine covers eight leagues, not only the five of the game: a signing from
    # one of them arrives with his real barème, a modest season here
    js = jeu.execute("SELECT journee_id FROM journee WHERE saison='2024/25'").fetchone()[0]
    fenetre_bareme(jeu, js, connu, 2700, 100.0, tit=30, dispo=30, poste="Buteur")
    jeu.commit()
    P.amorcer(jeu, "2025/26", "2024/25", ligues=(53,))
    prestations_j1(jeu, {i: (6.0, 90) for i in range(1, 12)})
    joue_la_journee(jeu, connu)
    joue_la_journee(jeu, inconnu)
    P.calculer(jeu, None, "2025/26", 1, importer=False)
    o = dict(jeu.execute("SELECT player_id, ovr FROM carte WHERE arrivee=1"))
    b = {pid: json.loads(x) for pid, x in jeu.execute("SELECT player_id, bareme FROM carte WHERE arrivee=1")}
    assert b[connu]["base"]["min"] == 2700 and b[inconnu]["base"]["min"] == 0
    # his own season is what prices him, even when it is worse than his position's median
    assert b[connu]["s25"] < b[inconnu]["s25"] and o[connu] < o[inconnu]
    # the unknown keeps the wide bound, the one with a season behind him a tighter one
    assert b[inconnu]["borne"] == E.BORNE_NOUVEAU and b[connu]["borne"] < E.BORNE_NOUVEAU


def test_mercato_ignores_a_player_outside_the_perimeter():
    jeu = base()
    pid = recrue(jeu)
    P.amorcer(jeu, "2025/26", "2024/25", ligues=(53,))
    prestations_j1(jeu, {i: (6.0, 90) for i in range(1, 12)})
    joue_la_journee(jeu, pid, team=3)          # still a club of no league of the game
    r = P.calculer(jeu, None, "2025/26", 1, importer=False)
    assert r["nouvelles_cartes"] == 0
    assert jeu.execute("SELECT COUNT(*) FROM carte WHERE player_id=?", (pid,)).fetchone()[0] == 0


def test_cards_carry_season_attributes_from_the_seed_onwards():
    jeu = base()
    equipe_et_compo(jeu)
    P.amorcer(jeu, "2025/26", "2024/25", ligues=(53,))
    attrs = {pid: json.loads(a) for pid, a in jeu.execute("SELECT player_id, attributs FROM carte")}
    assert set(attrs[10]) == {"FIN", "CRE", "PRO", "DEF", "DRI", "CON"} and set(attrs[1]) == {"ARR", "EVI", "SOR", "REL", "BUT", "PRO"}
    # finishing points grow with the player number, defence points shrink: ranked among ALL outfield players
    assert attrs[15]["FIN"] > attrs[8]["FIN"] > attrs[2]["FIN"] and attrs[2]["DEF"] > attrs[8]["DEF"] > attrs[15]["DEF"]
    prestations_j1(jeu, {i: (6.0, 90) for i in range(1, 12)})
    j1 = P.journee_id(jeu, "2025/26", 1)
    fenetre_bareme(jeu, j1, 2, 90, 100.0, axes={"FIN": 100.0})      # a striker's night from a defender
    jeu.commit()
    P.calculer(jeu, None, "2025/26", 1, importer=False)
    apres = json.loads(jeu.execute("SELECT attributs FROM carte WHERE player_id=2").fetchone()[0])
    assert apres["FIN"] > attrs[2]["FIN"] and apres["DEF"] <= attrs[2]["DEF"]
    s, m = jeu.execute("SELECT sommes, min90 FROM carte WHERE player_id=2").fetchone()
    assert json.loads(s)["axes"]["FIN"] == 100.0 and m == 1.0


def test_the_preferred_foot_comes_from_the_file_or_stays_unknown(tmp_path):
    """A fact about a real person: it is read from the source or left
    blank.  Nothing infers it from the position or from the shots."""
    jeu = base()
    f = tmp_path / "pieds.json"
    f.write_text(json.dumps({"1": "gauche", "2": "droit", "3": "deux",
                             "4": "left",            # not normalised: refused
                             "999": "droit",         # unknown player: no row to update
                             "_sans_pied": [5, 6]}), encoding="utf-8")
    assert I.importer_pieds(jeu, f) == 3
    pieds = dict(jeu.execute("SELECT player_id, pied FROM joueur"))
    assert (pieds[1], pieds[2], pieds[3]) == ("gauche", "droit", "deux")
    assert pieds[4] is None and pieds[5] is None
    # no file at all is not an error: every card simply reads "inconnu"
    assert I.importer_pieds(jeu, tmp_path / "absent.json") == 0


def test_the_perimeter_is_the_eight_leagues_the_engine_rates():
    """The engine collects and calibrates eight championships
    (bareme_stats.LIGUES, and a coefficient each in
    coefs_championnats.json).  The game used to stop at five, which left
    a Champions League field two thirds full and no card at all for a PSV
    or a Sporting player."""
    assert set(P.LIGUES) == {47, 87, 55, 54, 53, 57, 61, 71}
    jeu = base()
    # a club that only plays the Eredivisie is inside the perimeter
    jeu.execute("INSERT INTO competition VALUES (57, 'Eredivisie', '2025/26')")
    jeu.execute("INSERT INTO club(team_id, nom) VALUES (77, 'PSV')")
    jeu.execute("INSERT INTO club(team_id, nom) VALUES (78, 'Ajax')")
    jid = jeu.execute("SELECT journee_id FROM journee WHERE saison='2025/26' AND numero=1").fetchone()[0]
    jeu.execute("""INSERT INTO match(match_id, journee_id, competition_id, date_utc,
                   home_team_id, away_team_id) VALUES (777, ?, 57, '2025-08-16T18:00:00Z', 77, 78)""", (jid,))
    jeu.commit()
    dedans = P.clubs_perimetre(jeu, "2025/26")
    assert 77 in dedans and 78 in dedans
    # and the five-league perimeter is what it used to be, if anyone asks
    assert 77 not in P.clubs_perimetre(jeu, "2025/26", ligues=(47, 87, 55, 54, 53))


def test_the_engine_s_manual_positions_come_first_in_the_game(tmp_path, monkeypatch):
    """moteur/postes_manuel.json is the engine's own list of hand-set
    positions; the game reads the same file, so a player the slot data
    reads wrong is fixed once for both."""
    from jeu import importer as I
    jeu = base()
    nom = jeu.execute("SELECT nom FROM joueur WHERE player_id=2").fetchone()[0]
    avant = jeu.execute("SELECT poste, postes FROM joueur WHERE player_id=2").fetchone()
    f = tmp_path / "postes_manuel.json"
    f.write_text(json.dumps({nom: "Milieu relayeur", "Personne Inconnue": "Buteur", nom + "x": "Poste bidon"}), encoding="utf-8")
    monkeypatch.setattr(I, "POSTES_MANUEL", f)
    I.majorite_postes_et_clubs(jeu)
    poste, postes = jeu.execute("SELECT poste, postes FROM joueur WHERE player_id=2").fetchone()
    assert poste == "Milieu relayeur" and json.loads(postes)[0] == "Milieu relayeur"
    # what he really held stays eligible behind it
    assert set(json.loads(avant[1] or "[]")) <= set(json.loads(postes)) | {"Milieu relayeur"}


def test_the_side_of_a_flat_midfield_four_is_read_as_a_wide_midfielder():
    """FotMob line 7, wide column: the engine says winger, the game says
    MG/MD.  Everything else keeps the engine's label."""
    from jeu import importer as I
    assert I.poste_raffine("Ailier", 72) == "Milieu droit"
    assert I.poste_raffine("Ailier", 78) == "Milieu gauche"
    assert I.poste_raffine("Ailier", 82) == "Ailier"          # the attacking line of a 4-2-3-1
    assert I.poste_raffine("Buteur", 72) == "Buteur" and I.poste_raffine("Ailier", None) == "Ailier"
    # on an existing base, from the FotMob slots
    jeu = base()
    fot = sqlite3.connect(":memory:")
    fot.execute("CREATE TABLE appearance(match_id, player_id, position_id)")
    fot.execute("INSERT INTO appearance VALUES (100, 9, 72)")        # player 9 is an Ailier in the fixture
    fot.execute("INSERT INTO appearance VALUES (100, 11, 104)")      # player 11 too, on the attacking line
    assert I.raffiner_postes(fot, jeu) == 1
    assert jeu.execute("SELECT poste FROM prestation WHERE player_id=9").fetchone()[0] == "Milieu droit"
    assert jeu.execute("SELECT poste FROM prestation WHERE player_id=11").fetchone()[0] == "Ailier"
    I.majorite_postes_et_clubs(jeu)
    assert jeu.execute("SELECT poste FROM joueur WHERE player_id=9").fetchone()[0] == "Milieu droit"
    # running it twice changes nothing more
    assert I.raffiner_postes(fot, jeu) == 0


# --------------------------------------------------------------------------
# The EA sheet: feet, birth dates, sides, physical profile
# --------------------------------------------------------------------------
FICHE_EA = """fotmob_id,nom_fotmob,ea_id,nom_ea,equipe_ea,championnat,naissance,age,poste,note,taille_cm,poids_kg,pied_fort,mauvais_pied,gestes,acceleration,vitesse_pointe,agilite,equilibre,reactions,endurance,force,detente,agressivite,note_physique
4,J4,1004,J4,A,Ligue 1,1998-11-04,27,RB,83,181,73,Left,4,4,89,95,81,78,90,95,72,84,77,79
9,J9,1009,J9,A,Ligue 1,2007-07-13,18,RW,89,180,72,Right,3,5,86,83,93,84,85,70,55,60,45,60
10,J10,1010,J10,A,Ligue 1,1997-05-15,29,ST,90,178,67,Right,5,5,93,89,94,81,91,76,69,84,58,69
99999,Inconnu,1,X,A,Ligue 1,2000-01-01,26,CB,60,180,80,Right,3,2,60,60,60,60,60,60,60,60,60,60
"""


def test_the_ea_sheet_gives_feet_birth_dates_sides_and_physique(tmp_path):
    jeu = base()
    jeu.execute("UPDATE joueur SET postes=? WHERE player_id=4", (json.dumps(["Lateral", "Ailier"]),))
    fichier = tmp_path / "physique_ea.csv"
    fichier.write_text(FICHE_EA, encoding="utf-8")
    from datetime import date
    n = I.importer_physique(jeu, fichier, quand=date(2026, 3, 12))
    assert n == 3                                   # the unknown fotmob_id is skipped
    j4 = jeu.execute("SELECT poste, postes, pied, pied_faible, naissance, age, cote, physique FROM joueur WHERE player_id=4").fetchone()
    assert j4[0] == "Lateral"                       # the base position stays for the barème
    assert json.loads(j4[1]) == ["Lateral droit", "Ailier droit"]   # every wide position takes the side
    # the sheet's foot column is mirrored (Left for Hakimi): read the other way round
    assert (j4[2], j4[3]) == ("droit", 4)
    assert (j4[4], j4[5], j4[6]) == ("1998-11-04", 27, "droit")
    ph = json.loads(j4[7])
    assert ph["vitesse_pointe"] == 95 and ph["endurance"] == 95 and ph["taille"] == 181 and ph["poste_ea"] == "RB"
    # a full weak foot is read as ambidextrous by the screen, kept as 5 here
    assert jeu.execute("SELECT pied, pied_faible FROM joueur WHERE player_id=10").fetchone() == ("gauche", 5)
    # the age is the age at the date the base stands at, not the sheet's
    assert jeu.execute("SELECT age FROM joueur WHERE player_id=9").fetchone()[0] == 18
    # a central player keeps its sideless list
    assert json.loads(jeu.execute("SELECT postes FROM joueur WHERE player_id=10").fetchone()[0] or "[]") in ([], ["Buteur"])
    # the majority pass rebuilds `postes` and keeps the side
    I.majorite_postes_et_clubs(jeu)
    assert json.loads(jeu.execute("SELECT postes FROM joueur WHERE player_id=4").fetchone()[0]) == ["Lateral droit"]
    assert jeu.execute("SELECT poste FROM joueur WHERE player_id=4").fetchone()[0] == "Lateral"


def test_lateraliser_puts_the_side_on_every_wide_position_only():
    assert I.lateraliser(["Lateral", "Milieu de couloir", "Ailier", "Buteur"], "gauche") == \
        ["Lateral gauche", "Milieu gauche", "Ailier gauche", "Buteur"]
    assert I.lateraliser(["Lateral droit", "Lateral"], "gauche") == ["Lateral gauche"]
    assert I.lateraliser(["Lateral", "Ailier"], None) == ["Lateral", "Ailier"]
    assert I._age_au("2007-07-13", __import__("datetime").date(2026, 7, 12)) == 18
    assert I._age_au("2007-07-13", __import__("datetime").date(2026, 7, 13)) == 19
    assert I._age_au("n'importe quoi", __import__("datetime").date(2026, 7, 13)) is None


def test_the_base_stands_at_its_last_calculated_match():
    from datetime import date
    jeu = base()
    assert I.date_de_la_base(jeu) == date(2025, 1, 1)          # the one calculated match
    jeu.execute("UPDATE journee SET calculee=0")
    assert I.date_de_la_base(jeu) == date.today()

"""The solo campaign: take a real club's place, play its calendar against
the other clubs' elevens, be paid for where you finished."""
import json
import sqlite3

import pytest

from jeu import marche as MA
from jeu import solo as SO
from jeu.tests import test_pipeline as TP

CLUBS = [(10 + i, f"Club {i}") for i in range(6)]      # six clubs for the fixture's competition


def base_solo(n_clubs=6):
    """The pipeline fixture, seeded, plus a manager with a squad and a real
    competition of `n_clubs` clubs, each with a full squad of cards.  The
    fixture's own club A already plays the competition, so only `n_clubs-1`
    are added and the field stays even, like a real league."""
    jeu = TP.base()
    jeu.row_factory = sqlite3.Row
    from jeu import pipeline as P
    P.amorcer(jeu, "2025/26", "2024/25", ligues=(53,))
    jeu.execute("INSERT INTO ligue_jeu(nom, saison, perimetre, cree_le) VALUES ('L', '2025/26', '[53]', 'x')")
    jeu.execute("INSERT INTO utilisateur(pseudo, cree_le) VALUES ('m1', 'x')")
    jeu.execute("INSERT INTO equipe(utilisateur_id, ligue_jeu_id, nom, budget) VALUES (1, 1, 'Mon FC', 100)")
    for k, pid in enumerate(range(1, 16), 1):
        jeu.execute("""INSERT INTO exemplaire(player_id, saison, numero, equipe_id, dans_effectif, origine,
                       prix_achat, achete_le) VALUES (?, '2025/26', ?, 1, 1, 'pack', 1.0, 'x')""", (pid, k))
    for pid, poste in jeu.execute("SELECT player_id, poste FROM joueur").fetchall():
        jeu.execute("UPDATE joueur SET postes=? WHERE player_id=?", (json.dumps([poste]), pid))
    # `n_clubs` real clubs, a fifteen-card squad each, and one match apiece
    # so the competition knows they play in it
    postes = TP.POSTES          # fifteen, every line covered
    pid = 1000
    for i in range(n_clubs - 1):
        tid = 10 + i
        jeu.execute("INSERT INTO club(team_id, nom, couleur) VALUES (?,?,?)", (tid, f"Club {i}", "#123456"))
        for k in range(15):
            pid += 1
            poste = postes[k % len(postes)]
            jeu.execute("""INSERT INTO joueur(player_id, nom, nom_normalise, team_id, poste, postes)
                           VALUES (?,?,?,?,?,?)""", (pid, f"P{pid}", f"p{pid}", tid, poste, json.dumps([poste])))
            jeu.execute("""INSERT INTO carte(player_id, saison, note_ovr, ovr, prix, attributs, matchs, minutes, maj)
                           VALUES (?, '2025/26', 6.5, ?, 5.0, ?, 10, 900, 'x')""",
                        (pid, 55 + i * 3 + (k % 4), json.dumps({"FIN": 55 + i, "CRE": 55, "PRO": 55,
                                                                "DEF": 55, "DRI": 55, "CON": 55,
                                                                "ARR": 55, "EVI": 55, "SOR": 55,
                                                                "REL": 55, "BUT": 55})))
    jeu.execute("""INSERT INTO journee(saison, numero, du, au, cloture, calculee)
                   VALUES ('2025/26', 90, '2026-01-01', '2026-01-07', '2026-01-01T00:00:00Z', 1)""")
    jid = jeu.execute("SELECT journee_id FROM journee WHERE numero=90").fetchone()[0]
    for i in range(n_clubs - 1):
        jeu.execute("""INSERT INTO match(match_id, journee_id, competition_id, date_utc, home_team_id, away_team_id)
                       VALUES (?,?,53,'2026-01-01T00:00:00Z',?,?)""",
                    (90000 + i, jid, 10 + i, 10 + (i + 1) % (n_clubs - 1)))
    jeu.commit()
    return jeu


ONZE = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]


def test_the_field_is_the_real_clubs_strongest_first():
    jeu = base_solo()
    clubs = SO.clubs_competition(jeu, "2025/26", "ligue1")
    assert len(clubs) == 6 and {f"Club {i}" for i in range(5)} <= {c["nom"] for c in clubs}
    assert [c["force"] for c in clubs] == sorted((c["force"] for c in clubs), reverse=True)
    vrais = [c for c in clubs if c["nom"].startswith("Club ")]
    assert vrais[0]["nom"] == "Club 4"          # the squads grow with the index
    with pytest.raises(SO.ErreurSolo):
        SO.clubs_competition(jeu, "2025/26", "inexistante")


def test_a_club_eleven_is_eleven_real_cards_of_that_club():
    jeu = base_solo()
    onze = SO.onze_club(jeu, "2025/26", 12)
    assert len(onze) == 11 and len({j["pid"] for j in onze}) == 11
    assert {j["fam"] for j in onze} == {"GK", "DEF", "MID", "FWD"}
    tids = {r[0] for r in jeu.execute("SELECT team_id FROM joueur WHERE player_id IN (%s)"
                                      % ",".join(str(j["pid"]) for j in onze))}
    assert tids == {12}


def test_a_league_campaign_plays_out_and_pays_the_final_position():
    jeu = base_solo()
    SO.demarrer(jeu, "2025/26", 1, "ligue1", 11, graine=7)
    with pytest.raises(SO.ErreurSolo):
        SO.demarrer(jeu, "2025/26", 1, "ligue1", 12)      # one campaign at a time
    n = len(SO.clubs_competition(jeu, "2025/26", "ligue1"))
    e = SO.etat(jeu, "2025/26", 1)
    tours = e["campagne"]["tours"]
    assert tours == 2 * (n - 1) and e["campagne"]["prochain"]["tour"] == 1
    budget0 = jeu.execute("SELECT budget FROM equipe WHERE equipe_id=1").fetchone()[0]
    r = None
    for _ in range(tours):
        r = SO.jouer_tour(jeu, "2025/26", 1, ONZE, {"tempo": "possession"})
    assert r["fini"] and r["bilan"]["credits"] > 0
    # the other clubs played too: every club has played every round
    table = SO.etat(jeu, "2025/26", 1)["palmares"]
    assert table and table[0]["libelle"] == r["bilan"]["libelle"]
    assert 1 <= r["bilan"]["rang"] <= n and r["bilan"]["matchs"] == tours
    budget = jeu.execute("SELECT budget FROM equipe WHERE equipe_id=1").fetchone()[0]
    assert abs(budget - budget0 - r["bilan"]["credits"]) < 1e-6
    assert MA.packs_offerts(jeu, 1) == {k: v for k, v in r["bilan"]["packs"].items()}
    # the campaign is closed: there is nothing left to play
    with pytest.raises(SO.ErreurSolo):
        SO.jouer_tour(jeu, "2025/26", 1, ONZE, None)


def test_the_table_counts_every_club_and_adds_up():
    jeu = base_solo()
    SO.demarrer(jeu, "2025/26", 1, "ligue1", 11, graine=3)
    for _ in range(4):
        SO.jouer_tour(jeu, "2025/26", 1, ONZE, None)
    t = SO.etat(jeu, "2025/26", 1)["campagne"]["classement"]
    assert len(t) == len(SO.clubs_competition(jeu, "2025/26", "ligue1"))
    assert all(l["j"] == 4 for l in t)
    assert sum(l["bp"] for l in t) == sum(l["bc"] for l in t)
    assert sum(l["g"] for l in t) == sum(l["p"] for l in t)
    assert sum(l["pts"] for l in t) == 3 * sum(l["g"] for l in t) + sum(l["n"] for l in t)
    assert sum(l["toi"] for l in t) == 1


def test_a_cup_ends_the_campaign_the_day_you_lose():
    jeu = base_solo(n_clubs=8)
    SO.COMPETITIONS["essai"] = {"nom": "Coupe d'essai", "cid": 53, "format": "coupe", "taille": 8}
    try:
        clubs = SO.clubs_competition(jeu, "2025/26", "essai")
        SO.demarrer(jeu, "2025/26", 1, "essai", clubs[3]["team_id"], graine=11)
        tours = 0
        while True:
            r = SO.jouer_tour(jeu, "2025/26", 1, ONZE, None)
            tours += 1
            if r["fini"]:
                break
        assert 1 <= tours <= 3
        b = r["bilan"]
        assert b["libelle"] in ("Vainqueur", "Finaliste", "Demi-finaliste", "Quart de finaliste")
        # no tie is ever left drawn: a cup has to produce a winner
        for f in json.loads(jeu.execute("SELECT resultats FROM campagne WHERE campagne_id=1").fetchone()[0]):
            assert f["resultat"] in ("A", "B")
    finally:
        SO.COMPETITIONS.pop("essai")


def test_a_campaign_replays_identically_from_its_seed():
    a, b = base_solo(), base_solo()
    for jeu in (a, b):
        SO.demarrer(jeu, "2025/26", 1, "ligue1", 11, graine=99)
        for _ in range(3):
            SO.jouer_tour(jeu, "2025/26", 1, ONZE, {"tempo": "direct"})
    ra, rb = (json.loads(j.execute("SELECT resultats FROM campagne WHERE campagne_id=1").fetchone()[0])
              for j in (a, b))
    assert ra == rb


def test_giving_up_pays_nothing_and_frees_the_slot():
    jeu = base_solo()
    SO.demarrer(jeu, "2025/26", 1, "ligue1", 11, graine=5)
    SO.jouer_tour(jeu, "2025/26", 1, ONZE, None)
    budget = jeu.execute("SELECT budget FROM equipe WHERE equipe_id=1").fetchone()[0]
    assert SO.abandonner(jeu, "2025/26", 1) is True
    assert jeu.execute("SELECT budget FROM equipe WHERE equipe_id=1").fetchone()[0] == budget
    assert MA.packs_offerts(jeu, 1) == {}
    assert SO.etat(jeu, "2025/26", 1)["campagne"] is None
    assert SO.abandonner(jeu, "2025/26", 1) is False
    SO.demarrer(jeu, "2025/26", 1, "ligue1", 12)          # the slot is free again


def test_a_free_pack_costs_nothing_and_is_spent_once():
    jeu = base_solo()
    jeu.execute("UPDATE equipe SET packs_offerts=? WHERE equipe_id=1", (json.dumps({"bronze": 1}),))
    jeu.commit()
    budget = jeu.execute("SELECT budget FROM equipe WHERE equipe_id=1").fetchone()[0]
    MA.ouvrir_pack(jeu, "2025/26", 1, "bronze", offert=True)
    assert jeu.execute("SELECT budget FROM equipe WHERE equipe_id=1").fetchone()[0] == budget
    assert MA.packs_offerts(jeu, 1) == {}
    with pytest.raises(MA.ErreurMarche):
        MA.ouvrir_pack(jeu, "2025/26", 1, "bronze", offert=True)
    with pytest.raises(MA.ErreurMarche):                  # a free pack has no chosen family
        MA.ouvrir_pack(jeu, "2025/26", 1, "bronze", fam="FWD", offert=True)


def test_the_bracket_keeps_the_two_strongest_apart_until_the_final():
    paires = SO.bracket_coupe(16)
    assert len(paires) == 8 and sorted(x for p in paires for x in p) == list(range(16))
    assert (0, 15) in paires and (1, 14) in paires
    # the top seed and the second seed are in opposite halves
    moities = [set(x for p in paires[:4] for x in p), set(x for p in paires[4:] for x in p)]
    assert (0 in moities[0]) != (1 in moities[0])


def test_an_odd_field_gives_everyone_a_bye_and_nobody_a_double():
    """Real leagues have an even number of clubs, but the calendar must not
    break on an odd one: the circle method rests one club a round."""
    cal = SO.calendrier_championnat(7)
    assert len(cal) == 14 and all(len(t) == 3 for t in cal)
    rencontres = [tuple(sorted(d)) for tour in cal for d in tour]
    assert len(rencontres) == 7 * 6                      # every pair twice
    from collections import Counter
    assert set(Counter(rencontres).values()) == {2}
    for tour in cal:                                     # nobody plays twice in a round
        joueurs = [x for d in tour for x in d]
        assert len(joueurs) == len(set(joueurs)) == 6


def test_a_club_plays_its_own_way_and_the_ways_are_not_all_the_same():
    """Judged against absolutes, every club came out direct and offensive
    at once: a club eleven finishes better than it controls almost by
    definition.  The thresholds are the league's own terciles, so the
    field divides instead of converging."""
    jeu = base_solo()
    tacs = [SO.tactique_club(SO.onze_club(jeu, "2025/26", c["team_id"]))
            for c in SO.clubs_competition(jeu, "2025/26", "ligue1")]
    assert len({(t.tempo, t.bloc, t.risque) for t in tacs}) > 1
    # and it is read, not drawn: the same eleven always plays the same way
    onze = SO.onze_club(jeu, "2025/26", 12)
    a, b = SO.tactique_club(onze), SO.tactique_club(onze)
    assert (a.tempo, a.bloc, a.risque) == (b.tempo, b.bloc, b.risque)


def test_the_calendar_alternates_home_and_away():
    """The plain circle method gave a club its whole first leg at home and
    the second away: a nineteen-match run, and a table nobody believes."""
    import itertools
    for n in (18, 20):
        cal = SO.calendrier_championnat(n)
        for p in range(n):
            cote = [a == p for tour in cal for (a, b) in tour if p in (a, b)]
            assert sum(cote) == n - 1 and len(cote) == 2 * (n - 1)
            assert max(len(list(g)) for _, g in itertools.groupby(cote)) <= 2


def test_a_machine_run_club_makes_its_changes():
    """A club that never touches its bench plays eleven tired men against
    a manager who uses his seven.  The plan is read from the seed, so a
    campaign still replays identically."""
    jeu = base_solo()
    clubs = SO.clubs_competition(jeu, "2025/26", "ligue1")
    e = SO.equipe_club(jeu, "2025/26", clubs[1])
    assert 1 <= len(e.banc) <= 7 and not {j["pid"] for j in e.banc} & {j["pid"] for j in e.joueurs}
    plan = SO.changements_club(e, 42)
    assert plan and sum(len(v) for v in plan.values()) <= SO.SM.MAX_CHANGEMENTS
    assert all(50 <= m <= 85 for m in plan)
    sortants = [s for v in plan.values() for s, _ in v]
    entrants = [x for v in plan.values() for _, x in v]
    assert len(set(sortants)) == len(sortants) and len(set(entrants)) == len(entrants)
    assert SO.changements_club(e, 42) == plan            # read, not drawn
    # a keeper is never taken off by the machine
    gk = {j["pid"] for j in e.joueurs if j["fam"] == "GK"}
    assert not gk & set(sortants)

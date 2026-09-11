"""The solo campaign: take a real club's place in a real competition, play
its real calendar, be paid for how far you went."""
import json
import sqlite3

import pytest

from jeu import marche as MA
from jeu import solo as SO
from jeu.tests import test_pipeline as TP

ONZE = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]


def base_solo(n_clubs=6, cid=53, tours=None):
    """The pipeline fixture, seeded, plus a manager with a squad and a real
    competition of `n_clubs` clubs, each with a fifteen-card squad and a
    real fixture list written into the base — which is where the campaign
    reads its calendar from.

    The fixture's own club A already plays competition 53, so for a league
    only `n_clubs - 1` are added and the field stays even.
    """
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

    jeu.execute("INSERT OR IGNORE INTO competition VALUES (?, ?, '2025/26')",
                (cid, {42: "Champions League"}.get(cid, "Ligue 1")))
    ajoutes = n_clubs - 1 if cid == 53 else n_clubs
    pid = 1000
    tids = ([1] if cid == 53 else []) + [10 + i for i in range(ajoutes)]
    for i in range(ajoutes):
        tid = 10 + i
        jeu.execute("INSERT INTO club(team_id, nom, couleur) VALUES (?,?,?)", (tid, f"Club {i}", "#123456"))
        for k in range(15):
            pid += 1
            poste = TP.POSTES[k % len(TP.POSTES)]
            jeu.execute("""INSERT INTO joueur(player_id, nom, nom_normalise, team_id, poste, postes)
                           VALUES (?,?,?,?,?,?)""", (pid, f"P{pid}", f"p{pid}", tid, poste, json.dumps([poste])))
            jeu.execute("""INSERT INTO carte(player_id, saison, note_ovr, ovr, prix, attributs, matchs, minutes, maj)
                           VALUES (?, '2025/26', 6.5, ?, 5.0, ?, 10, 900, 'x')""",
                        (pid, 55 + i * 2 + (k % 4), json.dumps({"FIN": 55 + i, "CRE": 55, "PRO": 55,
                                                                "DEF": 55, "DRI": 55, "CON": 55,
                                                                "ARR": 55, "EVI": 55, "SOR": 55,
                                                                "REL": 55, "BUT": 55})))
    # the real fixture list, written gameweek by gameweek like the importer
    calendrier = tours if tours is not None else SO.calendrier_championnat(len(tids))
    mid = 90000
    for numero, duels in enumerate(calendrier, start=90):
        jeu.execute("""INSERT INTO journee(saison, numero, du, au, cloture, calculee)
                       VALUES ('2025/26', ?, '2026-01-01', '2026-01-07', '2026-01-01T00:00:00Z', 1)""",
                    (numero,))
        jid = jeu.execute("SELECT journee_id FROM journee WHERE numero=?", (numero,)).fetchone()[0]
        for a, b in duels:
            mid += 1
            jeu.execute("""INSERT INTO match(match_id, journee_id, competition_id, date_utc, phase,
                           home_team_id, away_team_id) VALUES (?,?,?,'2026-01-01T00:00:00Z',?,?,?)""",
                        (mid, jid, cid, SO.PHASE_REGULIERE, tids[a], tids[b]))
    jeu.commit()
    return jeu


def base_europe(n_clubs=12, matchs_par_club=4):
    """A European field: `n_clubs` clubs, each drawn against
    `matchs_par_club` DIFFERENT opponents — a league phase, not a round
    robin, which is exactly what the format is."""
    # the first `matchs_par_club` rounds of a round robin: every club meets
    # that many DIFFERENT opponents, which is what a league phase is
    tours = SO.calendrier_championnat(n_clubs)[:matchs_par_club]
    return base_solo(n_clubs=n_clubs, cid=42, tours=tours)


# --------------------------------------------------------------------------
# The field and the elevens
# --------------------------------------------------------------------------

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


def test_a_machine_run_club_makes_its_changes():
    """A club that never touches its bench plays eleven tired men against a
    manager who uses his seven.  The plan is read from the seed."""
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
    assert SO.changements_club(e, 42) == plan
    gk = {j["pid"] for j in e.joueurs if j["fam"] == "GK"}
    assert not gk & set(sortants)


def test_a_club_plays_its_own_way_and_the_ways_are_not_all_the_same():
    jeu = base_solo()
    tacs = [SO.tactique_club(SO.onze_club(jeu, "2025/26", c["team_id"]))
            for c in SO.clubs_competition(jeu, "2025/26", "ligue1")]
    assert len({(t.tempo, t.bloc, t.risque) for t in tacs}) > 1
    onze = SO.onze_club(jeu, "2025/26", 12)
    a, b = SO.tactique_club(onze), SO.tactique_club(onze)
    assert (a.tempo, a.bloc, a.risque) == (b.tempo, b.bloc, b.risque)


# --------------------------------------------------------------------------
# The calendar
# --------------------------------------------------------------------------

def test_the_calendar_is_the_competition_s_own():
    """A generated round robin is an imitation; the base holds the real
    fixture list and that is what the campaign plays."""
    jeu = base_solo()
    clubs = [c["team_id"] for c in SO.clubs_competition(jeu, "2025/26", "ligue1")]
    cal = SO.calendrier_reel(jeu, "2025/26", "ligue1", clubs)
    assert len(cal) == 2 * (len(clubs) - 1)
    paires = [tuple(sorted(d)) for tour in cal for d in tour]
    from collections import Counter
    assert set(Counter(paires).values()) == {2}            # everybody twice
    for tour in cal:
        places = [x for d in tour for x in d]
        assert len(places) == len(set(places))             # nobody twice in a round
    # a competition the base knows nothing about gives nothing, and the
    # caller falls back on the circle method
    assert SO.calendrier_reel(jeu, "2025/26", "premier", clubs) == []


def test_the_generated_calendar_alternates_home_and_away():
    """The fallback, for a base with no fixture list.  The plain circle
    method gave a club its whole first leg at home: nineteen in a row."""
    import itertools
    for n in (18, 20):
        cal = SO.calendrier_championnat(n)
        for p in range(n):
            cote = [a == p for tour in cal for (a, b) in tour if p in (a, b)]
            assert sum(cote) == n - 1 and len(cote) == 2 * (n - 1)
            assert max(len(list(g)) for _, g in itertools.groupby(cote)) <= 2


# --------------------------------------------------------------------------
# A league season
# --------------------------------------------------------------------------

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
    assert 1 <= r["bilan"]["rang"] <= n and r["bilan"]["matchs"] == tours
    budget = jeu.execute("SELECT budget FROM equipe WHERE equipe_id=1").fetchone()[0]
    assert abs(budget - budget0 - r["bilan"]["credits"]) < 1e-6
    assert MA.packs_offerts(jeu, 1) == {k: v for k, v in r["bilan"]["packs"].items()}
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
    SO.demarrer(jeu, "2025/26", 1, "ligue1", 12)


# --------------------------------------------------------------------------
# The European format
# --------------------------------------------------------------------------

def test_the_league_phase_sends_the_right_clubs_to_the_right_places():
    """1-8 straight to the last sixteen, 9-24 to the play-off seeded
    9 v 24, 25-36 out.  On a smaller field the shape is kept: the play-off
    has to produce exactly as many winners as there are seeds."""
    assert SO.seuils_qualification(36) == (8, 24)
    assert SO.seuils_qualification(12) == (4, 12)
    rangs = list(range(36))
    duels, directs, sortis = SO.tableau_apres_ligue(rangs)
    assert directs == rangs[:8] and sortis == rangs[24:]
    assert len(duels) == 8 and len(directs) == len(duels)
    # ninth plays twenty-fourth, and the lower seed hosts the first leg
    assert (rangs[23], rangs[8]) in duels and (rangs[16], rangs[15]) in duels
    # the last sixteen: best seed against weakest qualifier, seed at home in the second leg
    huit = SO.tableau_huitiemes(directs, [rangs[8 + i] for i in range(8)])
    assert len(huit) == 8 and all(b in directs for _a, b in huit)
    assert huit[0] == (rangs[15], rangs[0])


def test_a_european_campaign_runs_league_phase_then_knockouts():
    jeu = base_europe(n_clubs=12, matchs_par_club=4)
    clubs = SO.clubs_competition(jeu, "2025/26", "ldc")
    # the field is completed to thirty-six with the strongest clubs the game
    # has cards for; this fixture only has thirteen, and that is the field
    assert 12 <= len(clubs) <= SO.TAILLE_LIGUE
    SO.demarrer(jeu, "2025/26", 1, "ldc", clubs[5]["team_id"], graine=4)
    e = SO.etat(jeu, "2025/26", 1)["campagne"]
    n_ligue = e["tours"]
    assert e["format"] == "ligue_puis_coupe" and e["phase"] == "ligue"
    assert 1 <= n_ligue <= SO.MATCHS_LIGUE
    vus = []
    for _ in range(60):
        r = SO.jouer_tour(jeu, "2025/26", 1, ONZE, None)
        vus.append(r["phase"])
        if r["fini"]:
            break
    assert vus[:n_ligue] == ["ligue"] * n_ligue
    # a league phase, not a round robin: nobody meets the same club twice
    camp = jeu.execute("SELECT * FROM campagne WHERE campagne_id=1").fetchone()
    resultats = json.loads(camp["resultats"])
    ligue = [f for f in resultats if f["phase"] == "ligue"]
    for place in range(len(clubs)):
        rencontres = [f["b"] if f["a"] == place else f["a"] for f in ligue if place in (f["a"], f["b"])]
        assert len(rencontres) == len(set(rencontres)) <= SO.MATCHS_LIGUE
    b = r["bilan"]
    assert b["libelle"] in [v[0] for v in SO.RECOMPENSES_EUROPE.values()]
    assert b["credits"] > 0


def test_a_two_legged_tie_is_decided_on_the_aggregate():
    jeu = base_europe(n_clubs=12, matchs_par_club=4)
    clubs = SO.clubs_competition(jeu, "2025/26", "ldc")
    SO.demarrer(jeu, "2025/26", 1, "ldc", clubs[0]["team_id"], graine=11)
    for _ in range(40):
        r = SO.jouer_tour(jeu, "2025/26", 1, ONZE, None)
        if r["fini"]:
            break
    camp = jeu.execute("SELECT * FROM campagne WHERE campagne_id=1").fetchone()
    cal = json.loads(camp["calendrier"])
    resultats = json.loads(camp["resultats"])
    phases = [t["phase"] for t in cal]
    assert "barrage" in phases or "8" in phases
    for phase in ("barrage", "8", "4", "2"):
        manches = [t for t in cal if t["phase"] == phase]
        if not manches:
            continue
        assert len(manches) == 2                     # home and away
        assert [t["manche"] for t in manches] == [1, 2]
        # the second leg is the first one reversed
        assert sorted(tuple(sorted(d)) for d in manches[0]["duels"]) == \
               sorted(tuple(sorted(d)) for d in manches[1]["duels"])
        assert [tuple(d) for d in manches[1]["duels"]] == [(b, a) for a, b in manches[0]["duels"]]
        gagnants = SO.vainqueurs_phase(camp, resultats, phase)
        if gagnants is None:
            continue
        ties = SO._cumul(resultats, phase)
        for cle, t in ties.items():
            x, y = t["duel"]
            bx, by = t["buts"].get(x, 0), t["buts"].get(y, 0)
            gagnant = next(g for g in gagnants if g in (x, y))
            if bx != by:
                assert gagnant == (x if bx > by else y)   # the aggregate, nothing else
    # the final is a single match
    if "F" in phases:
        assert len([t for t in cal if t["phase"] == "F"]) == 1


def test_a_european_campaign_replays_identically():
    a, b = base_europe(n_clubs=12, matchs_par_club=4), base_europe(n_clubs=12, matchs_par_club=4)
    for jeu in (a, b):
        clubs = SO.clubs_competition(jeu, "2025/26", "ldc")
        SO.demarrer(jeu, "2025/26", 1, "ldc", clubs[3]["team_id"], graine=77)
        for _ in range(40):
            if SO.jouer_tour(jeu, "2025/26", 1, ONZE, None)["fini"]:
                break
    ra, rb = (json.loads(j.execute("SELECT resultats FROM campagne WHERE campagne_id=1").fetchone()[0])
              for j in (a, b))
    assert ra == rb and len(ra) > 0


# --------------------------------------------------------------------------
# Rewards
# --------------------------------------------------------------------------

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
    with pytest.raises(MA.ErreurMarche):
        MA.ouvrir_pack(jeu, "2025/26", 1, "bronze", fam="FWD", offert=True)


# --------------------------------------------------------------------------
# A campaign match is played live
# --------------------------------------------------------------------------

def _reculer(jeu, secondes):
    from datetime import datetime, timedelta, timezone
    from jeu import lobby as LB
    quand = (datetime.now(timezone.utc) - timedelta(seconds=secondes)).strftime("%Y-%m-%dT%H:%M:%SZ")
    jeu.execute("UPDATE rencontre SET debut=? WHERE resultat IS NULL", (quand,))
    jeu.commit()


def test_a_campaign_match_is_played_live_and_closes_the_round():
    """It is an ordinary rencontre tied to the campaign, so it runs on the
    lobby's clock: you watch it, adjust it, make your changes, and the round
    resolves when its ninety minutes are up."""
    from jeu import lobby as LB
    jeu = base_solo()
    SO.demarrer(jeu, "2025/26", 1, "ligue1", 11, graine=21)
    rid = SO.lancer_tour(jeu, "2025/26", 1, ONZE, {"tempo": "direct"}, banc=[12, 13, 14, 15])
    assert rid
    camp = SO.en_cours(jeu, "2025/26", 1)
    r = SO.match_en_cours(jeu, camp)
    assert r is not None and r["campagne_id"] == camp["campagne_id"] and r["defi"] == 1
    assert r["nom_adverse"] and r["equipe_a"] == 1
    # the lobby must not see it: it is not a lobby match
    assert LB.en_cours(jeu, "2025/26", 1) is None
    with pytest.raises(SO.ErreurSolo):
        SO.lancer_tour(jeu, "2025/26", 1, ONZE, None)          # one at a time
    # it shows up live on the campaign screen, and the round has not moved
    e = SO.etat(jeu, "2025/26", 1)["campagne"]
    assert e["match"] and e["match"]["fini"] is False and e["tour"] == 0
    # adjust and substitute through the lobby's own machinery
    assert LB.ajuster(jeu, "2025/26", 1, {"tempo": "possession"}, r) >= 1
    assert LB.changer(jeu, "2025/26", 1, ONZE[10], 12, r) >= 1
    # ninety minutes later the round closes: your live sheet is the result
    _reculer(jeu, LB.DUREE_REELLE + 5)
    e = SO.etat(jeu, "2025/26", 1)["campagne"]
    assert e["match"] is None and e["tour"] == 1
    mien = [f for f in json.loads(SO.en_cours(jeu, "2025/26", 1)["resultats"]) if f["mien"]]
    assert len(mien) == 1
    feuille = json.loads(jeu.execute("SELECT feuille FROM rencontre WHERE rencontre_id=?", (rid,)).fetchone()[0])
    place = e["place"]
    attendu = feuille["score"] if mien[0]["a"] == place else feuille["score"][::-1]
    assert mien[0]["score"] == attendu
    assert any(x["type"] == "changement" for x in feuille["evenements"])
    # and the rest of the round was played too
    tour0 = [f for f in json.loads(SO.en_cours(jeu, "2025/26", 1)["resultats"]) if f["tour"] == 0]
    assert len(tour0) == 3                       # six clubs, three fixtures


def test_a_live_campaign_match_never_touches_the_ranked_ladder():
    from jeu import lobby as LB
    jeu = base_solo()
    SO.demarrer(jeu, "2025/26", 1, "ligue1", 11, graine=33)
    SO.lancer_tour(jeu, "2025/26", 1, ONZE, None)
    _reculer(jeu, LB.DUREE_REELLE + 5)
    SO.etat(jeu, "2025/26", 1)
    assert jeu.execute("SELECT elo_classe, classees FROM equipe WHERE equipe_id=1").fetchone()[0] == 1000
    assert LB.classement(jeu, "2025/26") == []


def test_an_exempt_round_has_nothing_to_kick_off():
    """An odd field rests one club a round.  There is a journée to play,
    but not for you, so the round resolves at once."""
    jeu = base_solo(n_clubs=7)
    n = len(SO.clubs_competition(jeu, "2025/26", "ligue1"))
    SO.demarrer(jeu, "2025/26", 1, "ligue1", 11, graine=8)
    camp = SO.en_cours(jeu, "2025/26", 1)
    cal = json.loads(camp["calendrier"])
    moi = camp["place"]
    exempts = [t for t, tour in enumerate(cal) if not any(moi in d for d in tour["duels"])]
    if not exempts:
        pytest.skip("ce champ ne laisse personne au repos")
    for _ in range(exempts[0]):
        SO.lancer_tour(jeu, "2025/26", 1, ONZE, None)
        from jeu import lobby as LB
        _reculer(jeu, LB.DUREE_REELLE + 5)
        SO.etat(jeu, "2025/26", 1)
    assert SO.lancer_tour(jeu, "2025/26", 1, ONZE, None) == 0

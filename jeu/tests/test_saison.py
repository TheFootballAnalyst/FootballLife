"""outils/saison.py — the season's replay on the tiny synthetic season of
test_pipeline: which gameweeks are over, the replay in order, the movers."""
from datetime import date

from jeu import pipeline as P
from jeu.tests.test_pipeline import base, fenetre_bareme, prestations_j1
from outils import saison as SA


def test_paths_follow_the_season():
    assert SA.saison_precedente("2026/27") == "2025/26"
    assert SA.saison_precedente("2030/31") == "2029/30"
    ch = SA.chemins("2026/27")
    assert ch["fotmob"].name == "fotmob_2627.db" and ch["jeu"].name == "jeu_2627.sqlite"
    assert ch["source"] == "2025/26" and ch["fotmob_source"].name == "fotmob_2526.db"
    assert SA.debut("2026/27") == date(2026, 8, 1)


def test_a_gameweek_is_over_the_morning_after_its_window():
    jeu = base()                                   # J1 = 2025-08-15 → 2025-08-21
    assert SA.journees_terminees(jeu, "2025/26", date(2025, 8, 21)) == []
    assert SA.journees_terminees(jeu, "2025/26", date(2025, 8, 22)) == [1]
    jeu.execute("UPDATE journee SET calculee=1 WHERE saison='2025/26' AND numero=1")
    assert SA.journees_terminees(jeu, "2025/26", date(2025, 9, 1)) == []


def test_replay_computes_the_finished_gameweeks_in_order_and_names_the_movers():
    jeu = base()
    P.amorcer(jeu, "2025/26", "2024/25", ligues=(53,))
    jeu.execute("INSERT INTO journee(saison, numero, du, au, cloture, calculee) VALUES ('2025/26', 2, '2025-08-22', '2025-08-28', '2025-08-22T18:45:00Z', 0)")
    notes = {i: (7.0, 90) for i in range(1, 12)}
    prestations_j1(jeu, notes)
    fenetre_bareme(jeu, P.journee_id(jeu, "2025/26", 1), 1, 90, 60.0)
    fenetre_bareme(jeu, P.journee_id(jeu, "2025/26", 1), 2, 90, 5.0)
    jeu.commit()
    lignes = []
    assert SA.rejouer(jeu, None, "2025/26", date(2025, 8, 22), lignes.append) and len(lignes) == 1
    assert [r[0] for r in jeu.execute("SELECT numero FROM journee WHERE saison='2025/26' AND calculee=1 ORDER BY numero")] == [1]
    assert lignes[0].startswith("  J 1")
    # J2 is still open: nothing more to do today, both when replayed again and a week later
    assert SA.rejouer(jeu, None, "2025/26", date(2025, 8, 22)) == []
    faits = SA.rejouer(jeu, None, "2025/26", date(2025, 9, 1), lambda s: None)
    assert [r["journee"] for r in faits] == [2]
    m = SA.mouvements(jeu, "2025/26")
    assert m["depuis"] == 0 and m["jusqua"] == 2 and m["cartes"] == 15
    noms = [r[0] for r in m["hausses"]]
    assert "J1" in noms                              # a strong window: up
    assert all(r[5] > 0 for r in m["hausses"]) and all(r[5] < 0 for r in m["baisses"])
    sortie = []
    SA.afficher_mouvements(m, sortie.append)
    assert sortie[0].startswith("  15 cartes") and any("J1 (A, Gardien)" in s for s in sortie)
    assert SA.mouvements(jeu, "2025/26", depuis=2)["cartes"] == 0


# --------------------------------------------------------------------------
# End to end, on a synthetic provider: two seasons of a six-club league,
# the base built from the previous one, the gameweeks replayed, a week later
# --------------------------------------------------------------------------

import json  # noqa: E402
import random  # noqa: E402
import sqlite3  # noqa: E402
from datetime import timedelta  # noqa: E402

from donnees import journee as J  # noqa: E402

CLES = ["ShotsOnTarget", "ShotsOffTarget", "assists", "chances_created", "clearances", "duel_won", "duel_lost", "dribbled_past",
        "expected_goals_non_penalty", "expected_assists", "fouls", "interceptions", "passes_into_final_third", "recoveries",
        "saves", "touches", "was_fouled", "keeper_diving_save", "goals_conceded", "accurate_passes"]
SLOTS = [(11, True), (33, False), (34, False), (36, False), (37, False), (63, False), (65, False), (67, False),
         (84, False), (86, False), (105, False), (None, False), (None, False), (None, False), (None, False)]
CLUBS = {100 + i: f"Club {chr(65 + i)}" for i in range(6)}


def effectifs(seconde: bool) -> dict:
    """club -> players; in the second season the keepers rotate one club on
    and a newcomer takes a starter's place at Club A."""
    eff = {tid: [tid * 100 + j for j in range(15)] for tid in CLUBS}
    if seconde:
        t = list(CLUBS)
        for a, b in zip(t, t[1:] + t[:1]):
            eff[a][0], eff[b][0] = eff[b][0], eff[a][0]
        eff[t[0]][5] = 999901
    return eff


def feuille_synthetique(rng, mid, jour, h, a, eff, rnd):
    stats, lineup, scores = {}, {"homeTeam": {"starters": [], "subs": []}, "awayTeam": {"starters": [], "subs": []}}, [0, 0]
    for cote, tid in (("homeTeam", h), ("awayTeam", a)):
        for k, pid in enumerate(eff[tid][:15]):
            pos, gk = SLOTS[k]
            minutes = 90 if pos else rng.choice([0, 15, 30])
            s = {"minutes_played": minutes}
            if minutes:
                for c in CLES:
                    s[c] = round(rng.random() * (1 if gk else 3) * (3 if c == "touches" else 1), 2) if rng.random() < 0.6 else 0
                s["goals"] = int(rng.random() < 0.12 and not gk)
                scores[0 if cote == "homeTeam" else 1] += s["goals"]
            stats[str(pid)] = {"id": pid, "name": f"Joueur {pid}", "teamId": tid, "teamName": CLUBS[tid], "positionId": pos,
                               "isGoalkeeper": gk, "stats": [{"stats": {c: {"key": c, "stat": {"value": v}} for c, v in s.items()}}]}
            lineup[cote]["starters" if pos else "subs"].append({"id": pid, "marketValue": 1e6 * (1 + k), "age": 24, "countryCode": "FRA"})
    return {"general": {"matchId": mid, "matchTimeUTCDate": f"{jour}T19:00:00Z", "leagueId": 53, "leagueName": "Ligue 1",
                        "parentLeagueId": 53, "matchRound": str(rnd), "finished": True,
                        "homeTeam": {"id": h, "name": CLUBS[h]}, "awayTeam": {"id": a, "name": CLUBS[a]},
                        "teamColors": {"lightMode": {"home": "#AA0000", "away": "#0000AA"}}},
            "header": {"teams": [{"score": scores[0]}, {"score": scores[1]}]},
            "content": {"playerStats": stats, "matchFacts": {"events": {"events": []}}, "lineup": lineup}}


def fournisseur(annee: int, tours: int, seconde: bool, reponses: dict):
    """`tours` Friday rounds of three matches from 14 August, as the
    provider would list and detail them."""
    rng, eff, t, mid = random.Random(annee), effectifs(seconde), list(CLUBS), annee * 1000
    for rnd in range(1, tours + 1):
        jour = date(annee, 8, 14) + timedelta(days=7 * (rnd - 1))
        ms = []
        for i in range(3):
            h, a = t[i], t[(i + rnd) % 6]
            if h == a:
                a = t[(i + rnd + 1) % 6]
            mid += 1
            reponses[J.URL_MATCH.format(id=mid)] = feuille_synthetique(rng, mid, jour.isoformat(), h, a, eff, rnd)
            ms.append({"id": mid, "status": {"finished": True, "started": True, "cancelled": False, "utcTime": f"{jour}T19:00:00Z"},
                       "home": {"id": h, "name": CLUBS[h]}, "away": {"id": a, "name": CLUBS[a]}})
        reponses[J.URL_JOUR.format(jour=jour.strftime("%Y%m%d"))] = {
            "leagues": [{"id": 53, "primaryId": 53, "name": "Ligue 1", "ccode": "FRA", "matches": ms}]}


def test_build_and_weekly_run_on_a_synthetic_provider(tmp_path, monkeypatch, capsys):
    reponses = {}
    fournisseur(2025, 12, False, reponses)          # the source season: twelve rounds
    fournisseur(2026, 6, True, reponses)            # the live one: six so far
    monkeypatch.setattr(J, "requete", lambda url, entetes=None, essais=4: reponses.get(url, {"leagues": []}))
    monkeypatch.setattr(J, "PAUSE", 0)
    ch = dict(fotmob=tmp_path / "fotmob_2627.db", jeu=tmp_path / "jeu_2627.sqlite", source="2025/26",
              fotmob_source=tmp_path / "fotmob_2526.db", cache=tmp_path / "cache", sortie=tmp_path / "out")
    monkeypatch.setattr(SA, "chemins", lambda s: ch)
    b = J.recuperer(date(2025, 8, 1), date(2025, 11, 15), ch["fotmob_source"], ch["cache"], journal=lambda s: None)
    assert b["ingeres"] == 36 and b["utilisables"] == 36
    assert sqlite3.connect(ch["fotmob_source"]).execute("SELECT DISTINCT competition FROM v_match").fetchall() == [("Ligue 1",)]

    # Saturday 12 September 2026: rounds 1-5 played, the window of J5 (11/9) still open
    monkeypatch.setattr(SA, "aujourdhui", lambda: date(2026, 9, 12))
    lignes = []
    r = SA.construire("2026/27", journal=lignes.append)
    assert r["journees"] == [1, 2, 3, 4] and r["cartes"] > 40
    jeu = sqlite3.connect(ch["jeu"])
    etat = {j["numero"]: j["calculee"] for j in P.etat(jeu, "2026/27")["journees"]}
    assert etat == {0: False, 1: True, 2: True, 3: True, 4: True, 5: False}
    assert jeu.execute("SELECT COUNT(*) FROM carte WHERE saison='2026/27'").fetchone()[0] == r["cartes"]
    assert jeu.execute("SELECT ovr FROM carte WHERE player_id=999901").fetchone() is not None     # the newcomer has a card
    assert jeu.execute("SELECT c.nom FROM joueur j JOIN club c ON c.team_id=j.team_id WHERE j.player_id=10100").fetchone()[0] == "Club F"   # the keeper who moved
    assert jeu.execute("SELECT COUNT(*) FROM valeur_marche").fetchone()[0] > 0
    assert r["mouvements"]["hausses"] and r["mouvements"]["baisses"]
    assert any("lancer 2627" in s for s in lignes)
    jeu.close()

    # the Saturday after round 6: J5 is over (its window ends the day before round 6), J6 open
    monkeypatch.setattr(SA, "aujourdhui", lambda: date(2026, 9, 26))
    r2 = SA.semaine("2026/27", journal=lambda s: None)
    assert r2["journees"] == [5]
    jeu = sqlite3.connect(ch["jeu"])
    etat = {j["numero"]: (j["calculee"], j["au"]) for j in P.etat(jeu, "2026/27")["journees"]}
    assert etat[5] == (True, "2026-09-17") and etat[6][0] is False
    assert jeu.execute("SELECT COUNT(*) FROM carte_historique h JOIN journee j ON j.journee_id=h.journee_id WHERE j.numero=5").fetchone()[0] > 40
    jeu.close()
    # again the same day: nothing to do; and for a site online, the gameweek goes out as a file instead
    assert SA.semaine("2026/27", journal=lambda s: None)["journees"] == []
    monkeypatch.setattr(SA, "aujourdhui", lambda: date(2026, 10, 3))
    jeu = sqlite3.connect(ch["jeu"])
    jeu.execute("UPDATE journee SET au='2026-09-30' WHERE saison='2026/27' AND numero=6"); jeu.commit(); jeu.close()
    r3 = SA.semaine("2026/27", exporter=True, telecharger=False, journal=lambda s: None)
    assert r3["journees"] == [6] and r3["fichiers"][0].name == "2026-27_J6.json"
    doc = json.loads(r3["fichiers"][0].read_text(encoding="utf-8"))
    assert doc["journee"] == 6 and doc["prestations"] and doc["bareme"]
    capsys.readouterr()

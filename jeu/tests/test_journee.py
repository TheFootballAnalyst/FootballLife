"""donnees/journee.py — the fetch of a window of matches, on canned FotMob
answers: the perimeter, the cache, the ingest, the finalised base."""
import json
import sqlite3
from datetime import date

import pytest

from donnees import journee as J


def feuille(mid, finished=True, league=(47, "Premier League", 47), joueurs=2, date_utc="2026-08-15T14:00:00Z"):
    lid, lname, parent = league
    stats = {}
    for i in range(joueurs):
        pid = mid * 100 + i
        stats[str(pid)] = {"id": pid, "name": f"J{pid}", "teamId": 10 + i % 2, "teamName": "A" if i % 2 == 0 else "B",
                           "positionId": 11, "isGoalkeeper": False,
                           "stats": [{"stats": {"Minutes": {"key": "minutes_played", "stat": {"value": 90, "type": "number"}},
                                                "Goals": {"key": "goals", "stat": {"value": i, "type": "number"}}}}]}
    return {"general": {"matchId": mid, "matchTimeUTCDate": date_utc, "leagueId": lid, "leagueName": lname,
                        "parentLeagueId": parent, "matchRound": "1", "finished": finished,
                        "homeTeam": {"id": 10, "name": "A"}, "awayTeam": {"id": 11, "name": "B"},
                        "teamColors": {"lightMode": {"home": "#FF0000", "away": "#0000FF"}}},
            "header": {"teams": [{"score": 2}, {"score": 1}]},
            "content": {"playerStats": stats, "matchFacts": {"events": {"events": []}},
                        "lineup": {"homeTeam": {"starters": [], "subs": []}, "awayTeam": {"starters": [], "subs": []}}}}


def liste(jour, matchs):
    """One day's listing: [(league dict, [(mid, finished)])]."""
    return {"date": jour, "leagues": [dict(l, matches=[{"id": mid, "status": {"finished": fin, "started": True, "cancelled": False,
                                                                                "utcTime": f"{jour[:4]}-{jour[4:6]}-{jour[6:]}T14:00:00Z"},
                                                        "home": {"id": 10, "name": "A"}, "away": {"id": 11, "name": "B"}}
                                                       for mid, fin in ms]) for l, ms in matchs]}


PL = {"id": 47, "primaryId": 47, "name": "Premier League", "ccode": "ENG"}
UCL_QUAL = {"id": 10611, "primaryId": 42, "name": "Champions League Qualification", "ccode": "INT"}
EGY = {"id": 9000, "primaryId": 9000, "name": "Premier League", "ccode": "EGY"}
CHAMP = {"id": 48, "primaryId": 48, "name": "Championship", "ccode": "ENG"}
WCQ = {"id": 10197, "primaryId": 10197, "name": "World Cup Qualification UEFA", "ccode": "INT"}
BEL = {"id": 40, "primaryId": 40, "name": "Pro League", "ccode": "BEL"}


@pytest.fixture
def fausse_api(monkeypatch):
    reponses = {}
    appels = []

    def faux(url, entetes=None, essais=4):
        appels.append(url)
        if url not in reponses:
            raise AssertionError(f"adresse imprévue : {url}")
        r = reponses[url]
        if isinstance(r, Exception):
            raise r
        return r

    monkeypatch.setattr(J, "requete", faux)
    monkeypatch.setattr(J, "PAUSE", 0)
    return reponses, appels


def jour_url(j):
    return J.URL_JOUR.format(jour=j)


def match_url(mid):
    return J.URL_MATCH.format(id=mid)


def test_perimeter_by_id_and_by_exact_name_in_a_followed_country():
    assert J.dans_perimetre(PL)
    assert J.dans_perimetre(UCL_QUAL)                       # by its mother competition's id
    assert J.dans_perimetre(BEL)                            # by id 40, whatever FotMob calls it
    assert not J.dans_perimetre(EGY)                        # a homonym elsewhere
    assert not J.dans_perimetre(CHAMP)
    assert not J.dans_perimetre(WCQ)                        # qualifiers never
    assert J.dans_perimetre({"id": 777, "name": "Coppa Italia", "ccode": "ITA"})
    assert not J.dans_perimetre({"id": 778, "name": "Coppa Italia Women", "ccode": "ITA"})
    assert J.dans_perimetre({"id": 5, "name": "x"}, competitions={5: "ajoutée"})


def test_competition_names_follow_the_reference_then_the_perimeter_then_the_alias():
    assert J.nom_competition("Champions League Qualification", 42) == "Champions League"
    assert J.nom_competition("FIFA Club World Cup", 78) == "Club World Cup"
    assert J.nom_competition("FIFA Club World Cup", None) == "Club World Cup"
    assert J.nom_competition("Süper Lig", None) == "Super Lig"
    assert J.nom_competition("Trophée des Champions", None) == "Trophee des champions"   # the palmarès spelling
    assert J.nom_competition("Taça de Portugal", None) == "Taca de Portugal"
    assert J.nom_competition("Premier League", 47, {47: "Premier League (ref)"}) == "Premier League (ref)"


def test_season_and_base_names():
    assert J.saison_du_jour(date(2026, 10, 23)) == "2026/27"
    assert J.saison_du_jour(date(2027, 5, 1)) == "2026/27"
    assert J.saison_du_jour(date(2026, 6, 30)) == "2025/26"
    assert J.base_de_saison("2026/27").name == "fotmob_2627.db"
    assert J.base_de_saison("2025/26").name == "fotmob_2526.db"


def test_headers_are_kept_for_next_time(tmp_path):
    f = tmp_path / "entetes.json"
    assert J.lire_entetes([], f) == {}
    assert J.lire_entetes(["x-mas: abc=="], f) == {"x-mas": "abc=="}
    assert J.lire_entetes([], f) == {"x-mas": "abc=="}
    assert J.lire_entetes(["Autre: 1", "sans valeur:"], f) == {"x-mas": "abc==", "Autre": "1"}


def test_fetch_window_caches_ingests_and_finalises(tmp_path, fausse_api):
    reponses, appels = fausse_api
    reponses[jour_url("20260815")] = liste("20260815", [(PL, [(1, True), (2, False)]), (CHAMP, [(3, True)]), (UCL_QUAL, [(4, True)])])
    reponses[jour_url("20260816")] = liste("20260816", [(EGY, [(5, True)])])
    reponses[match_url(1)] = feuille(1)
    reponses[match_url(4)] = feuille(4, league=(10611, "Champions League Qualification", 42), date_utc="2026-08-15T19:00:00Z")
    cache, db = tmp_path / "cache", tmp_path / "f.db"
    lignes = []
    bilan = J.recuperer(date(2026, 8, 15), date(2026, 8, 16), db, cache, {"x-mas": "t"}, noms={42: "Champions League"}, journal=lignes.append)
    assert bilan["jours"] == 2 and bilan["listes"] == 3 and bilan["termines"] == 2
    assert bilan["telecharges"] == 2 and bilan["en_cache"] == 0 and bilan["ingeres"] == 2 and bilan["utilisables"] == 2
    assert len(bilan["non_termines"]) == 1 and "(2)" in bilan["non_termines"][0]
    assert not bilan["erreurs"]
    assert (cache / "1.json").exists() and (cache / "4.json").exists() and not (cache / "3.json").exists()
    assert match_url(3) not in appels and match_url(5) not in appels and match_url(2) not in appels
    assert len(lignes) == 2
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM match").fetchone()[0] == 2
    assert conn.execute("SELECT usable FROM match WHERE match_id=1").fetchone()[0] == 1
    # the views the barème reads, with the competition named like the reference base
    assert dict(conn.execute("SELECT match_id, competition FROM v_match")) == {1: "Premier League", 4: "Champions League"}
    assert conn.execute("SELECT COUNT(*) FROM v_appearance").fetchone()[0] == 4
    assert conn.execute("SELECT SUM(value) FROM v_stat WHERE stat_key='goals'").fetchone()[0] == 2
    assert conn.execute("SELECT home_score, away_score FROM match WHERE match_id=1").fetchone() == (2, 1)

    # second pass: the sheets come from the cache, nothing is re-ingested
    appels.clear()
    bilan2 = J.recuperer(date(2026, 8, 15), date(2026, 8, 16), db, cache, journal=lambda s: None)
    assert bilan2["telecharges"] == 0 and bilan2["en_cache"] == 2 and bilan2["ingeres"] == 0 and bilan2["utilisables"] == 2
    assert appels == [jour_url("20260815"), jour_url("20260816")]

    # match 2 finishes: fetched now; a cached sheet that was not finished is asked again
    reponses[jour_url("20260815")] = liste("20260815", [(PL, [(1, True), (2, True)])])
    reponses[match_url(2)] = feuille(2)
    (cache / "1.json").write_text(json.dumps(feuille(1, finished=False)), encoding="utf-8")
    reponses[match_url(1)] = feuille(1)
    appels.clear()
    bilan3 = J.recuperer(date(2026, 8, 15), date(2026, 8, 15), db, cache, journal=lambda s: None)
    assert bilan3["telecharges"] == 2 and bilan3["ingeres"] == 1 and bilan3["utilisables"] == 3
    assert match_url(1) in appels and match_url(2) in appels
    assert json.loads((cache / "1.json").read_text(encoding="utf-8"))["general"]["finished"] is True


def test_a_refusal_stops_with_the_header_hint_and_keeps_what_was_fetched(tmp_path, fausse_api):
    reponses, _ = fausse_api
    reponses[jour_url("20260815")] = liste("20260815", [(PL, [(1, True), (2, True)])])
    reponses[match_url(1)] = feuille(1)
    reponses[match_url(2)] = J.Refus("403")
    db = tmp_path / "f.db"
    with pytest.raises(SystemExit) as e:
        J.recuperer(date(2026, 8, 15), date(2026, 8, 15), db, tmp_path / "cache", journal=lambda s: None)
    assert "x-mas" in str(e.value)
    assert sqlite3.connect(db).execute("SELECT COUNT(*) FROM match").fetchone()[0] == 1


def test_a_broken_sheet_is_an_error_not_a_stop(tmp_path, fausse_api):
    reponses, _ = fausse_api
    reponses[jour_url("20260815")] = liste("20260815", [(PL, [(1, True), (2, True)])])
    reponses[match_url(1)] = {"general": {}}        # no matchId
    reponses[match_url(2)] = feuille(2)
    bilan = J.recuperer(date(2026, 8, 15), date(2026, 8, 15), tmp_path / "f.db", tmp_path / "cache", journal=lambda s: None)
    assert bilan["ingeres"] == 1 and len(bilan["erreurs"]) == 1 and "illisible" in bilan["erreurs"][0]
    assert "en erreur" in J.resume(bilan)


def test_reference_names_come_from_the_previous_season_base(tmp_path):
    ref = tmp_path / "ref.db"
    conn = sqlite3.connect(ref)
    conn.executescript("""CREATE TABLE match (match_id INTEGER PRIMARY KEY, parent_league_id INTEGER, usable INTEGER);
                          CREATE VIEW v_match AS SELECT m.*, CASE parent_league_id WHEN 71 THEN 'Super Lig' ELSE 'Autre' END AS competition FROM match m;
                          INSERT INTO match VALUES (1, 71, 1), (2, 71, 1), (3, 99, 1);""")
    conn.commit(); conn.close()
    assert J.noms_de_reference(ref) == {71: "Super Lig", 99: "Autre"}
    assert J.noms_de_reference(tmp_path / "absente.db") == {}
    assert J.noms_de_reference(None) == {}


def test_listing_marks_the_perimeter(fausse_api):
    reponses, _ = fausse_api
    reponses[jour_url("20261017")] = liste("20261017", [(PL, [(1, True), (2, False)]), (CHAMP, [(3, True)])])
    lignes = J.lister(date(2026, 10, 17))
    assert lignes[0].startswith("●") and "Premier League" in lignes[0] and "2 matchs, 1 terminés" in lignes[0]
    assert lignes[1].startswith(" ") and "Championship" in lignes[1]

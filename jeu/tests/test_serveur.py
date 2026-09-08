"""The web API on a tiny synthetic season (same fixture as the pipeline
tests): accounts, market rules, composition rules, lock, standings,
private leagues, admin close."""
import json
import os
import pathlib
import sqlite3

import pytest

from jeu import evolution as E
from jeu import pipeline as P
from jeu.tests import test_pipeline as TP


@pytest.fixture
def client(tmp_path, monkeypatch):
    chemin = tmp_path / "jeu.sqlite"
    jeu = TP.base()
    disque = sqlite3.connect(chemin)
    jeu.backup(disque)
    disque.close()
    jeu.close()
    monkeypatch.setenv("FL_JEU", str(chemin))
    monkeypatch.setenv("FL_SAISON", "2025/26")
    from web.app import serveur as SV
    monkeypatch.setattr(SV, "CHEMIN_JEU", chemin)
    monkeypatch.setattr(SV, "SAISON", "2025/26")
    SV._CACHE["cle"] = None
    j = SV.ouvrir()
    P.amorcer(j, "2025/26", "2024/25", ligues=(53,))
    # open the market: lock far in the future
    j.execute("UPDATE journee SET cloture='2099-01-01T00:00:00Z' WHERE saison='2025/26' AND numero=1")
    j.commit(); j.close()
    from fastapi.testclient import TestClient
    return TestClient(SV.app)


def inscrire(client, pseudo="ana", mdp="secret1"):
    r = client.post("/api/inscription", json={"pseudo": pseudo, "mot_de_passe": mdp})
    assert r.status_code == 200, r.text
    return r.json()


def test_inscription_creates_team_and_first_user_is_admin(client):
    r = inscrire(client)
    assert r["admin"] is True
    moi = client.get("/api/moi").json()
    assert moi["connecte"] and moi["pseudo"] == "ana" and moi["equipe"] == "Équipe de ana"
    e = client.get("/api/equipe").json()
    assert e["budget"] == E.BUDGET_INITIAL and e["effectif"] == {} and e["marche_ouvert"]
    assert client.post("/api/inscription", json={"pseudo": "ANA", "mot_de_passe": "xxxxxx"}).status_code == 409
    assert client.post("/api/inscription", json={"pseudo": "b", "mot_de_passe": "xxxxxx"}).status_code == 400


def test_login_logout(client):
    inscrire(client, "bob", "motdepasse")
    client.post("/api/deconnexion")
    assert client.get("/api/moi").json()["connecte"] is False
    assert client.post("/api/connexion", json={"pseudo": "bob", "mot_de_passe": "faux"}).status_code == 401
    assert client.post("/api/connexion", json={"pseudo": "Bob", "mot_de_passe": "motdepasse"}).status_code == 200
    assert client.get("/api/moi").json()["pseudo"] == "bob"
    assert client.get("/api/equipe").status_code == 200


def test_market_rules(client):
    inscrire(client)
    cartes = client.get("/api/cartes").json()
    assert len(cartes) == 15 and {"id", "nom", "fam", "ovr", "prix", "part", "notes"} <= set(cartes[0])
    prix = {c["id"]: c["prix"] for c in cartes}
    assert client.post("/api/equipe/acheter", json={"player_id": 1}).status_code == 200
    assert client.post("/api/equipe/acheter", json={"player_id": 1}).status_code == 409      # already owned
    assert client.post("/api/equipe/acheter", json={"player_id": 999}).status_code == 404
    e = client.get("/api/equipe").json()
    assert abs(e["budget"] - (E.BUDGET_INITIAL - prix[1])) < 1e-6 and "1" in e["effectif"] or 1 in e["effectif"]
    # quotas: three goalkeepers is one too many (ids 1 and 12 are GK)
    assert client.post("/api/equipe/acheter", json={"player_id": 12}).status_code == 200
    # a third GK does not exist in the fixture; check a family cap with strikers (10, 15 + none) is fine
    assert client.post("/api/equipe/vendre", json={"player_id": 12}).status_code == 200
    assert client.post("/api/equipe/vendre", json={"player_id": 12}).status_code == 404
    e = client.get("/api/equipe").json()
    assert abs(e["budget"] - (E.BUDGET_INITIAL - prix[1])) < 1e-6


def test_composition_rules_and_lock(client):
    inscrire(client)
    for pid in range(1, 15):          # 15 would be a fourth striker: quota
        assert client.post("/api/equipe/acheter", json={"player_id": pid}).status_code == 200
    assert client.post("/api/equipe/acheter", json={"player_id": 15}).status_code == 409
    bonne = {"formation": "4-3-3", "titulaires": list(range(1, 12)), "banc": [12, 13, 14], "capitaine": 10}
    assert client.post("/api/equipe/composition", json=bonne).status_code == 200
    e = client.get("/api/equipe").json()
    assert e["composition"]["capitaine"] == 10 and e["composition"]["titulaires"] == list(range(1, 12))
    # two goalkeepers in the eleven: illegal
    mauvaise = dict(bonne, titulaires=[1, 12, 3, 4, 5, 6, 7, 8, 9, 10, 11], banc=[2, 13, 14])
    assert client.post("/api/equipe/composition", json=mauvaise).status_code == 400
    # captain must start
    assert client.post("/api/equipe/composition", json=dict(bonne, capitaine=14)).status_code == 400
    # a player not owned
    assert client.post("/api/equipe/composition", json=dict(bonne, banc=[12, 13, 99])).status_code == 400
    # selling a starter removes him from the composition
    assert client.post("/api/equipe/vendre", json={"player_id": 11}).status_code == 200
    assert 11 not in client.get("/api/equipe").json()["composition"]["titulaires"]
    # lock: admin locks now, then nothing moves
    assert client.post("/api/admin/journee/1/verrouiller").status_code == 200
    assert client.get("/api/saison").json()["courante"]["verrouillee"] is True
    assert client.post("/api/equipe/composition", json=bonne).status_code == 409
    assert client.post("/api/equipe/acheter", json={"player_id": 11}).status_code == 409
    assert client.post("/api/admin/journee/1/ouvrir").status_code == 200
    assert client.get("/api/saison").json()["courante"]["verrouillee"] is False


def test_admin_close_and_standings(client):
    inscrire(client, "admin1")
    for pid in range(1, 15):
        client.post("/api/equipe/acheter", json={"player_id": pid})
    client.post("/api/equipe/composition", json={"formation": "4-3-3", "titulaires": list(range(1, 12)), "banc": [12, 13, 14], "capitaine": 10})
    # a second manager, not admin, with no composition
    client.post("/api/deconnexion")
    r = inscrire(client, "zoe")
    assert r["admin"] is False
    assert client.get("/api/admin/etat").status_code == 403
    client.post("/api/deconnexion")
    client.post("/api/connexion", json={"pseudo": "admin1", "mot_de_passe": "secret1"})
    # rated performances arrive as a file (everyone 7.0)
    doc = {"saison": "2025/26", "journee": 1, "du": "2025-08-15", "au": "2025-08-21",
           "matchs": {"200": {"competition_id": 53, "competition": "Ligue 1", "date_utc": "2025-08-15T18:45:00Z",
                              "phase": "Phase reguliere", "home_team_id": 1, "away_team_id": 2, "home_score": 2, "away_score": 2}},
           "clubs": {"1": {"nom": "A", "couleur": "#112233"}}, "joueurs": {},
           "prestations": [dict(match_id=200, player_id=i, team_id=1, poste=TP.POSTES[i - 1], minutes=90, entrant=0,
                                brut=10, coef=1, points=20, note=7.0, statut="ok", lignes={}, attributs={"FIN": 60})
                           for i in range(1, 12)]}
    files = {"fichier": ("j1.json", json.dumps(doc), "application/json")}
    r = client.post("/api/admin/journee/1/prestations", files=files)
    assert r.status_code == 200 and r.json()["prestations"] == 11
    r = client.post("/api/admin/journee/1/calculer")
    assert r.status_code == 200 and r.json()["scores"][0][1] == 11 * 7.0 + 3.5
    cl = client.get("/api/classement").json()
    assert cl[0]["pseudo"] == "admin1" and cl[0]["points"] == 80.5 and cl[1]["points"] == 0
    res = client.get("/api/resultats/1").json()
    assert res["score"] == 80.5 and res["participants"] == 1 and len(res["prestations"][str(1)] if "1" in res["prestations"] else res["prestations"][1]) == 1
    assert client.get("/api/saison").json()["courante"] is None      # only one gameweek in the fixture
    # card detail after a computed gameweek
    d = client.get("/api/cartes/1").json()
    assert d["attributs"] == {"FIN": 60} and len(d["historique"]) == 2 and d["prestations"][0]["note"] == 7.0


def test_private_leagues(client):
    inscrire(client, "ana")
    r = client.post("/api/ligues", json={"nom": "Les potes"})
    assert r.status_code == 200
    code = r.json()["code"]
    client.post("/api/deconnexion")
    inscrire(client, "bob")
    assert client.post("/api/ligues/rejoindre", json={"code": "ZZZZZZ"}).status_code == 404
    assert client.post("/api/ligues/rejoindre", json={"code": code.lower()}).status_code == 200
    ligues = client.get("/api/ligues").json()
    assert len(ligues) == 1 and ligues[0]["nom"] == "Les potes"
    assert {m["pseudo"] for m in ligues[0]["classement"]} == {"ana", "bob"}

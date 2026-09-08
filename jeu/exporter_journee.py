"""exporter_journee.py — rate one gameweek locally and write it as JSON.

    python3 -m jeu.exporter_journee --saison 2026/27 --journee 3 \
            --fotmob moteur/fotmob.db --jeu jeu/jeu_2627.sqlite

Runs the engine on the gameweek's window (dates read from the game base,
so run `pipeline journees` first), rates every performance (note +
attributes) and writes out/journees/2026-27_J3.json.  The admin uploads
that file on the site (Admin → journée → prestations), then closes the
gameweek; the server never needs fotmob.db or the match cache.

The same document can be loaded locally with pipeline.charger_prestations.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sqlite3
import sys

RACINE = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from jeu import importer as I  # noqa: E402
from jeu import notation as N  # noqa: E402
from jeu import pipeline as P  # noqa: E402

T = I.T   # topsflops, with its side files pinned to moteur/


def exporter(fot, jeu, saison, numero):
    jid = P.journee_id(jeu, saison, numero)
    du, au = jeu.execute("SELECT du, au FROM journee WHERE journee_id=?", (jid,)).fetchone()
    prestas, matchs = T.calculer(fot, du, au, comps=T.COMPS_SERIE, seuil_min=1)
    statuts = T._charger_seuils()
    doc = {"saison": saison, "journee": numero, "du": du, "au": au, "matchs": {}, "clubs": {}, "joueurs": {}, "prestations": []}
    for mid, m in matchs.items():
        lid, plid, lname, dutc = fot.execute("SELECT league_id, parent_league_id, league_name, date_utc FROM match WHERE match_id=?", (mid,)).fetchone()
        doc["matchs"][str(mid)] = dict(competition_id=plid or lid, competition=lname, date_utc=dutc, phase=m["phase"],
                                       home_team_id=m["home"][0], away_team_id=m["away"][0],
                                       home_score=m["home"][2], away_score=m["away"][2])
        for tid, tnom, _ in (m["home"], m["away"]):
            doc["clubs"][str(tid)] = {"nom": tnom}
    for (mid, pid), p in prestas.items():
        tid = fot.execute("SELECT team_id FROM appearance WHERE match_id=? AND player_id=?", (mid, pid)).fetchone()
        doc["joueurs"].setdefault(str(pid), {"nom": p["nom"], "poste": p["poste"], "team_id": tid[0] if tid else None})
        doc["prestations"].append(dict(match_id=mid, player_id=pid, team_id=tid[0] if tid else None, poste=p["poste"],
                                       minutes=p["minutes"], entrant=int(bool(p.get("entrant"))), brut=p["brut"],
                                       coef=p["coef"], points=p["points"], note=N.note_prestation(p),
                                       statut=T._statut_final(p, statuts), lignes=p["lignes"],
                                       attributs=N.attributs_prestation(p)))
    return doc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--saison", required=True)
    ap.add_argument("--journee", type=int, required=True)
    ap.add_argument("--fotmob", default=str(RACINE / "moteur" / "fotmob.db"))
    ap.add_argument("--jeu", required=True, help="game base holding the season's gameweeks")
    ap.add_argument("--sortie", default=str(RACINE / "out" / "journees"))
    a = ap.parse_args()
    fot = sqlite3.connect(a.fotmob)
    jeu = I.ouvrir_jeu(pathlib.Path(a.jeu))
    doc = exporter(fot, jeu, a.saison, a.journee)
    out = pathlib.Path(a.sortie); out.mkdir(parents=True, exist_ok=True)
    f = out / f"{a.saison.replace('/', '-')}_J{a.journee}.json"
    f.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    print(f"{len(doc['prestations'])} prestations, {len(doc['matchs'])} matchs -> {f}")


if __name__ == "__main__":
    main()

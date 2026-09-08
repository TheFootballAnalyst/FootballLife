"""importer.py — turn a FotMob season base into game rows.

    python3 -m jeu.importer --fotmob moteur/fotmob.db --jeu jeu/jeu_2526.sqlite \
                            --saison 2025/26 --ligue 53

Cuts the season into gameweeks on the rounds of the reference league (a
gameweek runs from the first kick-off of round N to the day before the
first kick-off of round N+1, so the European midweek that follows a round
belongs to it), runs the engine (`topsflops.calculer`) on every window over
the whole series perimeter (top 5 + Champions League), rates each
performance (note + attributes), and writes `journee`, `match`, `club`,
`joueur`, `prestation` into the game database.

Idempotent: every row is INSERT OR REPLACE on its natural key.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sqlite3
import sys
import unicodedata
from datetime import date, timedelta

RACINE = pathlib.Path(__file__).resolve().parent.parent
MOTEUR = RACINE / "moteur"
sys.path.insert(0, str(MOTEUR))

import topsflops as T  # noqa: E402
import bareme_stats as B  # noqa: E402

from jeu import notation as N  # noqa: E402

# The engine resolves its side files relative to the working directory;
# pin them to moteur/ so the importer runs from anywhere.
T.COEFS = MOTEUR / "bareme_stats_coefs.json"
T.REFS_LOCALES = MOTEUR / "topsflops_refs.json"
T.SEUILS_FLOPS = MOTEUR / "seuils_flops_postes_2526.json"
T.CACHE_MATCHES = MOTEUR / "cache" / "matches"
T.CACHE_DIR = MOTEUR / "cache" / "matches"

SCHEMA = RACINE / "jeu" / "schema.sql"


def sans_accents(txt: str) -> str:
    n = unicodedata.normalize("NFKD", str(txt).lower())
    return "".join(c for c in n if not unicodedata.combining(c)).strip()


# --------------------------------------------------------------------------
# Gameweeks
# --------------------------------------------------------------------------

def journees_depuis_rounds(fot: sqlite3.Connection, ligue_id: int,
                           fin_saison: str | None = None) -> list[dict]:
    """One gameweek per numeric round of the reference league.

    Window = [first kick-off of round N, first kick-off of round N+1 - 1 day].
    The last round closes at `fin_saison` (default: 10 days after its first
    kick-off).
    """
    rows = fot.execute("""
        SELECT round, MIN(date_utc), MAX(date_utc)
        FROM match WHERE league_id = ? AND finished = 1
        GROUP BY round""", (ligue_id,)).fetchall()
    rounds = sorted(((int(r), d0, d1) for r, d0, d1 in rows if str(r).isdigit()),
                    key=lambda x: x[1])
    out = []
    for i, (num, d0, d1) in enumerate(rounds):
        du = d0[:10]
        if i + 1 < len(rounds):
            au = (date.fromisoformat(rounds[i + 1][1][:10]) - timedelta(days=1)).isoformat()
        else:
            au = fin_saison or (date.fromisoformat(du) + timedelta(days=10)).isoformat()
        # A round can spill past the next round's first kick-off (postponed
        # match): keep the window contiguous, the spilled match goes to the
        # later gameweek by date, which is what a manager would expect.
        out.append(dict(numero=num, du=du, au=max(au, du), cloture=d0))
    return out


# --------------------------------------------------------------------------
# Import
# --------------------------------------------------------------------------

def ouvrir_jeu(chemin: pathlib.Path) -> sqlite3.Connection:
    jeu = sqlite3.connect(chemin)
    jeu.executescript(SCHEMA.read_text(encoding="utf-8"))
    return jeu


def importer_journee(fot: sqlite3.Connection, jeu: sqlite3.Connection,
                     saison: str, j: dict, comps=None, adversaire=False) -> int:
    prestas, matchs = T.calculer(fot, j["du"], j["au"],
                                 comps=comps if comps is not None else T.COMPS_SERIE,
                                 seuil_min=1, adversaire=adversaire)
    jeu.execute("""INSERT OR REPLACE INTO journee(journee_id, saison, numero, du, au, cloture, calculee)
                   VALUES ((SELECT journee_id FROM journee WHERE saison=? AND numero=?),
                           ?, ?, ?, ?, ?, 1)""",
                (saison, j["numero"], saison, j["numero"], j["du"], j["au"], j["cloture"]))
    jid = jeu.execute("SELECT journee_id FROM journee WHERE saison=? AND numero=?",
                      (saison, j["numero"])).fetchone()[0]

    # competitions / clubs / matches
    comp_ids = {}
    for mid, m in matchs.items():
        row = fot.execute("""SELECT league_id, parent_league_id, league_name, date_utc
                             FROM match WHERE match_id=?""", (mid,)).fetchone()
        lid, plid, lname, dutc = row
        cid = plid or lid
        comp_ids[mid] = cid
        jeu.execute("INSERT OR IGNORE INTO competition(competition_id, nom, saison) VALUES (?,?,?)",
                    (cid, lname, saison))
        for tid, tnom, _ in (m["home"], m["away"]):
            jeu.execute("INSERT OR IGNORE INTO club(team_id, nom) VALUES (?,?)", (tid, tnom))
        jeu.execute("""INSERT OR REPLACE INTO match(match_id, journee_id, competition_id, date_utc,
                       phase, home_team_id, away_team_id, home_score, away_score)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (mid, jid, cid, dutc, m["phase"], m["home"][0], m["away"][0],
                     m["home"][2], m["away"][2]))

    # performances
    statuts = T._charger_seuils()
    n = 0
    for (mid, pid), p in prestas.items():
        jeu.execute("""INSERT OR IGNORE INTO joueur(player_id, nom, nom_normalise, team_id, poste)
                       VALUES (?,?,?,?,?)""",
                    (pid, p["nom"], sans_accents(p["nom"]), None, p["poste"]))
        note = N.note_prestation(p)
        attrs = N.attributs_prestation(p)
        tid = fot.execute("SELECT team_id FROM appearance WHERE match_id=? AND player_id=?",
                          (mid, pid)).fetchone()
        jeu.execute("""INSERT OR REPLACE INTO prestation(match_id, player_id, team_id, poste, minutes,
                       entrant, brut, coef, points, note, statut, lignes, attributs)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (mid, pid, tid[0] if tid else None, p["poste"], p["minutes"],
                     int(bool(p.get("entrant"))), p["brut"], p["coef"], p["points"], note,
                     T._statut_final(p, statuts), json.dumps(p["lignes"], ensure_ascii=False),
                     json.dumps(attrs)))
        n += 1
    jeu.commit()
    return n


def majorite_postes_et_clubs(jeu: sqlite3.Connection) -> None:
    """Set joueur.poste / team_id to the season's majority (by minutes)."""
    rows = jeu.execute("""
        SELECT player_id, poste, team_id, SUM(minutes) m
        FROM prestation GROUP BY player_id, poste, team_id""").fetchall()
    best: dict[int, tuple[float, str, int]] = {}
    for pid, poste, tid, m in rows:
        if pid not in best or m > best[pid][0]:
            best[pid] = (m, poste, tid)
    for pid, (_, poste, tid) in best.items():
        jeu.execute("UPDATE joueur SET poste=?, team_id=? WHERE player_id=?", (poste, tid, pid))
    jeu.commit()


def importer_couleurs(jeu: sqlite3.Connection, cache: pathlib.Path = MOTEUR / "cache" / "matches") -> int:
    """club.couleur from the kit colours in the cached match sheets.

    FotMob gives `general.teamColors.lightMode.{home,away}` per match.  A
    club's colour is its most frequent home-kit colour, unless that is plain
    white or black (the card darkens the colour, so a white kit would give a
    grey card): then the most frequent away colour.
    """
    from collections import Counter
    votes: dict[int, Counter] = {}
    for mid, h, a in jeu.execute("SELECT match_id, home_team_id, away_team_id FROM match"):
        f = cache / f"{mid}.json"
        if not f.exists():
            continue
        try:
            tc = json.loads(f.read_text(encoding="utf-8"))["general"]["teamColors"]["lightMode"]
        except (KeyError, TypeError, json.JSONDecodeError, OSError):
            continue
        for tid, cle in ((h, "home"), (a, "away")):
            c = (tc.get(cle) or "").upper()
            if c.startswith("#") and len(c) == 7:
                votes.setdefault(tid, Counter())[c] += 1
    n = 0
    for tid, cnt in votes.items():
        ordre = [c for c, _ in cnt.most_common()]
        choix = next((c for c in ordre if c not in ("#FFFFFF", "#000000")), ordre[0])
        jeu.execute("UPDATE club SET couleur=? WHERE team_id=?", (choix, tid))
        n += 1
    jeu.commit()
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fotmob", default=str(MOTEUR / "fotmob.db"))
    ap.add_argument("--jeu", default=str(RACINE / "jeu" / "jeu_2526.sqlite"))
    ap.add_argument("--saison", default="2025/26")
    ap.add_argument("--ligue", type=int, default=53, help="reference league for the gameweeks")
    ap.add_argument("--adversaire", action="store_true", help="engine opponent coefficient")
    ap.add_argument("--journees", default=None, help="e.g. 1-5 to import a subset")
    ap.add_argument("--couleurs-seulement", action="store_true",
                    help="only refresh club colours from the cache")
    a = ap.parse_args()
    if a.couleurs_seulement:
        jeu = ouvrir_jeu(pathlib.Path(a.jeu))
        print(f"{importer_couleurs(jeu)} couleurs de club -> {a.jeu}")
        return

    fot = sqlite3.connect(a.fotmob)
    jeu = ouvrir_jeu(pathlib.Path(a.jeu))
    js = journees_depuis_rounds(fot, a.ligue)
    if a.journees:
        lo, hi = (int(x) for x in a.journees.split("-"))
        js = [j for j in js if lo <= j["numero"] <= hi]
    total = 0
    for j in js:
        n = importer_journee(fot, jeu, a.saison, j, adversaire=a.adversaire)
        total += n
        print(f"J{j['numero']:>2}  {j['du']} -> {j['au']}  {n:>5} prestations")
    majorite_postes_et_clubs(jeu)
    nc = importer_couleurs(jeu)
    print(f"{total} prestations, {len(js)} journees, {nc} couleurs de club -> {a.jeu}")


if __name__ == "__main__":
    main()

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
from jeu import scoring as S  # noqa: E402

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

MIGRATIONS = {                       # columns added after the first bases were written
    "prestation": [("stats", "TEXT")],
    "equipe": [("elo_classe", "REAL NOT NULL DEFAULT 1000"), ("classees", "INTEGER NOT NULL DEFAULT 0"),
               ("packs_offerts", "TEXT")],
    "joueur": [("valeur_marche", "REAL"), ("age", "INTEGER"), ("numero", "TEXT"), ("pays", "TEXT"),
               ("postes", "TEXT"), ("pied", "TEXT")],
    "carte": [("part", "REAL NOT NULL DEFAULT 0"), ("valeur_base", "REAL NOT NULL DEFAULT 1"),
              ("ovr_base", "INTEGER NOT NULL DEFAULT 60"), ("poids", "REAL NOT NULL DEFAULT 0"),
              ("sommes", "TEXT"), ("min90", "REAL NOT NULL DEFAULT 0"), ("bareme", "TEXT"),
              ("arrivee", "INTEGER NOT NULL DEFAULT 0")],
    "carte_historique": [("part", "REAL NOT NULL DEFAULT 0"), ("poids", "REAL NOT NULL DEFAULT 0"),
                         ("sommes", "TEXT"), ("min90", "REAL NOT NULL DEFAULT 0")],
    "utilisateur": [("mdp_hash", "TEXT"), ("mdp_sel", "TEXT"), ("est_admin", "INTEGER NOT NULL DEFAULT 0")],
    "rencontre": [("banc_a", "TEXT"), ("banc_b", "TEXT"),
                  ("remplacements", "TEXT NOT NULL DEFAULT '{}'")],
}


# Tables of features the game no longer has.  Dropped only when EMPTY:
# a base that still holds rows keeps them, and says so, rather than having
# its history deleted by an upgrade.
RETIREES = {"match_h2h": "le face-à-face hebdomadaire sur actions réelles, remplacé par le lobby classé"}


def nettoyer_retirees(jeu: sqlite3.Connection) -> list[str]:
    restes = []
    for table, quoi in RETIREES.items():
        if not jeu.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone():
            continue
        if jeu.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]:
            restes.append(f"{table} ({quoi}) contient encore des lignes : table conservée, à supprimer à la main")
        else:
            jeu.execute(f"DROP TABLE {table}")
    return restes


def ouvrir_jeu(chemin: pathlib.Path) -> sqlite3.Connection:
    jeu = sqlite3.connect(chemin, check_same_thread=False)
    jeu.executescript(SCHEMA.read_text(encoding="utf-8"))
    for reste in nettoyer_retirees(jeu):
        print(reste)
    for table, cols in MIGRATIONS.items():
        existantes = {r[1] for r in jeu.execute(f"PRAGMA table_info({table})")}
        for nom, typ in cols:
            if nom not in existantes:
                jeu.execute(f"ALTER TABLE {table} ADD COLUMN {nom} {typ}")
    jeu.commit()
    return jeu


# Raw match actions kept on every performance: FotMob stat key -> short
# key, counts and not points.  They are what the card sheet shows next to
# the note — the goals, assists and saves the player really produced.
STATS = {
    "goals": "buts", "assists": "pd", "total_shots": "tirs", "ShotsOnTarget": "cadres",
    "expected_goals": "xg", "expected_assists": "xa", "chances_created": "occ",
    "big_chance_missed_title": "gom", "accurate_passes": "passes", "passes_into_final_third": "p3",
    "touches": "touches", "touches_opp_box": "surf", "dribbles_succeeded": "drib",
    "matchstats.headers.tackles": "tacles", "interceptions": "int", "clearances": "deg",
    "shot_blocks": "blocs", "recoveries": "rec", "duel_won": "dg", "duel_lost": "dp",
    "aerials_won": "aer", "dribbled_past": "dribble", "fouls": "fautes", "was_fouled": "subies",
    "saves": "arrets", "goals_conceded": "enc", "goals_prevented": "evites",
    "expected_goals_on_target_faced": "xgot", "owngoal": "csc", "errors_led_to_goal": "err",
}


def lire_stats(fot: sqlite3.Connection, match_ids) -> dict[tuple[int, int], dict]:
    """{(match_id, player_id): {short key: value}} from the FotMob stat table."""
    out: dict[tuple[int, int], dict] = {}
    marks = ",".join("?" * len(match_ids))
    if not match_ids:
        return out
    for mid, pid, cle, val in fot.execute(f"""SELECT match_id, player_id, stat_key, value FROM stat
                                              WHERE match_id IN ({marks})""", list(match_ids)):
        court = STATS.get(cle)
        if court is None or val is None:
            continue
        v = float(val)
        out.setdefault((mid, pid), {})[court] = int(v) if v == int(v) and court not in ("xg", "xa", "evites", "xgot") else round(v, 2)
    return out


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
    stats = lire_stats(fot, list(matchs))
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
                       entrant, brut, coef, points, note, statut, lignes, attributs, stats)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (mid, pid, tid[0] if tid else None, p["poste"], p["minutes"],
                     int(bool(p.get("entrant"))), p["brut"], p["coef"], p["points"], note,
                     T._statut_final(p, statuts), json.dumps(p["lignes"], ensure_ascii=False),
                     json.dumps(attrs), json.dumps(stats.get((mid, pid), {}))))
        n += 1
    jeu.commit()
    importer_valeurs(jeu, list(matchs))
    return n


def lire_valeurs(match_ids, cache: pathlib.Path | None = None) -> list[tuple]:
    """[(player_id, ISO date, M€, age, shirt number, country code)] from the
    cached sheets of `match_ids`.

    FotMob's lineup carries `marketValue` (euros) for every player on the
    sheet; it is Transfermarkt's figure, refreshed a few times a season.
    The sheet also gives the player's age, shirt number and nationality.
    """
    cache = pathlib.Path(cache or T.CACHE_MATCHES)
    out = []
    for mid in match_ids:
        f = cache / f"{mid}.json"
        if not f.exists():
            continue
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            date = (d["general"].get("matchTimeUTCDate") or "")[:10]
            lineup = d["content"]["lineup"]
        except (KeyError, TypeError, json.JSONDecodeError, OSError):
            continue
        if not date:
            continue
        for cote in ("homeTeam", "awayTeam"):
            eq = lineup.get(cote) or {}
            for grp in ("starters", "subs"):
                for pj in eq.get(grp) or []:
                    mv, pid = pj.get("marketValue"), pj.get("id")
                    if pid and mv:
                        out.append((int(pid), date, round(float(mv) / 1e6, 2), pj.get("age"),
                                    str(pj.get("shirtNumber") or "") or None, pj.get("countryCode")))
    return out


def ecrire_valeurs(jeu: sqlite3.Connection, valeurs) -> int:
    """valeur_marche rows (players known to the game only) + joueur.valeur_marche."""
    connus = {r[0] for r in jeu.execute("SELECT player_id FROM joueur")}
    n = 0
    derniers: dict[int, tuple] = {}
    for ligne in valeurs:
        pid, date, v = ligne[0], ligne[1], ligne[2]
        if pid in connus:
            jeu.execute("INSERT OR REPLACE INTO valeur_marche(player_id, date, valeur) VALUES (?,?,?)", (pid, date, v))
            n += 1
            if len(ligne) >= 6 and (pid not in derniers or date >= derniers[pid][0]):
                derniers[pid] = (date, ligne[3], ligne[4], ligne[5])
    for pid, (_, age, numero, pays) in derniers.items():
        jeu.execute("UPDATE joueur SET age=COALESCE(?, age), numero=COALESCE(?, numero), pays=COALESCE(?, pays) WHERE player_id=?",
                    (age, numero, pays, pid))
    jeu.execute("""UPDATE joueur SET valeur_marche = (SELECT valeur FROM valeur_marche v WHERE v.player_id = joueur.player_id
                                                   ORDER BY date DESC LIMIT 1)""")
    jeu.commit()
    return n


def importer_valeurs(jeu: sqlite3.Connection, match_ids, cache: pathlib.Path | None = None) -> int:
    """Market values of the cached sheets of `match_ids` into the game base."""
    return ecrire_valeurs(jeu, lire_valeurs(match_ids, cache))


def valeurs_a_date(jeu: sqlite3.Connection, limite: str | None = None) -> dict[int, float]:
    """{player_id: M€}: the latest market value known on or before `limite`
    (ISO date; None = the latest known at all)."""
    out: dict[int, float] = {}
    for pid, v in jeu.execute("""SELECT player_id, valeur FROM valeur_marche WHERE date <= ?
                                 ORDER BY date""", (limite or "9999-12-31",)):
        out[pid] = v
    return out


def importer_stats(fot: sqlite3.Connection, jeu: sqlite3.Connection) -> int:
    """Fill prestation.stats on a base written before the column existed."""
    mids = [r[0] for r in jeu.execute("SELECT match_id FROM match")]
    n = 0
    for i in range(0, len(mids), 500):
        stats = lire_stats(fot, mids[i:i + 500])
        for (mid, pid), st in stats.items():
            n += jeu.execute("UPDATE prestation SET stats=? WHERE match_id=? AND player_id=?",
                             (json.dumps(st), mid, pid)).rowcount
    jeu.commit()
    return n


def importer_bareme(fot: sqlite3.Connection, jeu: sqlite3.Connection, saison: str) -> int:
    """Run the season barème on the FotMob base (jeu/bareme.py, ~1 min) and
    write every player's window of every gameweek of `saison` into
    bareme_journee.  Matches before the first gameweek join it, matches
    after the last (a final) join the last."""
    from jeu import bareme as B
    journees = [(jid, du, au) for jid, du, au in jeu.execute(
        "SELECT journee_id, du, au FROM journee WHERE saison=? AND numero >= 1 ORDER BY du", (saison,))]
    if not journees:
        raise SystemExit(f"aucune journée pour {saison} : lancer `pipeline journees` d'abord")
    tous = B.calculer(fot)
    jeu.execute("DELETE FROM bareme_journee WHERE journee_id IN (%s)" % ",".join(str(j) for j, _, _ in journees))
    n = 0
    for pid, j in tous.items():
        for jid, f in B.fenetres_journees(j, journees).items():
            jeu.execute("""INSERT OR REPLACE INTO bareme_journee(journee_id, player_id, minutes, points, tit, dispo, axes)
                           VALUES (?,?,?,?,?,?,?)""",
                        (jid, pid, round(f["min"], 1), round(f["pts"], 4), int(f["tit"]), int(f["dispo"]),
                         json.dumps({k: round(v, 4) for k, v in f["axes"].items()})))
            n += 1
    jeu.commit()
    return n


def postes_joues(jeu: sqlite3.Connection, pid: int | None = None) -> dict[int, list[str]]:
    """{player_id: positions played, most minutes first, keeping those worth
    at least scoring.PART_POSTE_ELIGIBLE of the player's minutes}.

    A card is eligible wherever the player really played.  Valverde spent
    a third of his season at right back and a third on the wing: one label
    cannot hold him, and refusing him a midfield slot is wrong.
    """
    cond, args = ("WHERE player_id = ?", (pid,)) if pid else ("", ())
    par_joueur: dict[int, dict[str, float]] = {}
    for p, poste, m in jeu.execute(
            f"SELECT player_id, poste, SUM(minutes) FROM prestation {cond} GROUP BY player_id, poste", args):
        par_joueur.setdefault(p, {})[poste] = m or 0.0
    out = {}
    for p, minutes in par_joueur.items():
        total = sum(minutes.values()) or 1.0
        # The threshold is on the FAMILY, not on the label: Valverde's
        # midfield minutes are split between "Milieu defensif" and "Milieu
        # relayeur" and neither half clears it, while the midfield as a
        # whole is a quarter of his season.
        par_fam: dict[str, float] = {}
        for q, m in minutes.items():
            fam = S.FAMILLE_POSTE.get(q)
            if fam:
                par_fam[fam] = par_fam.get(fam, 0.0) + m
        familles = [f for f in sorted(par_fam, key=lambda f: -par_fam[f])
                    if par_fam[f] / total >= S.PART_POSTE_ELIGIBLE]
        gardes = []
        for f in familles or sorted(par_fam, key=lambda f: -par_fam[f])[:1]:
            dedans = [q for q in minutes if S.FAMILLE_POSTE.get(q) == f]
            if dedans:
                gardes.append(max(dedans, key=lambda q: minutes[q]))
        out[p] = gardes or sorted(minutes, key=lambda q: -minutes[q])[:1]
    return out


def majorite_postes_et_clubs(jeu: sqlite3.Connection) -> None:
    """Set joueur.poste / team_id to the season's majority (by minutes) and
    joueur.postes to every position the player really held."""
    rows = jeu.execute("""
        SELECT player_id, poste, team_id, SUM(minutes) m
        FROM prestation GROUP BY player_id, poste, team_id""").fetchall()
    best: dict[int, tuple[float, str, int]] = {}
    for pid, poste, tid, m in rows:
        if pid not in best or m > best[pid][0]:
            best[pid] = (m, poste, tid)
    eligibles = postes_joues(jeu)
    for pid, (_, poste, tid) in best.items():
        liste = eligibles.get(pid) or [poste]
        # the displayed position is the first of the list — the best position
        # of the family he spent most minutes in — so it never contradicts it
        jeu.execute("UPDATE joueur SET poste=?, team_id=?, postes=? WHERE player_id=?",
                    (liste[0], tid, json.dumps(liste), pid))
    jeu.commit()


def importer_pieds(jeu: sqlite3.Connection, fichier: pathlib.Path = MOTEUR / "pieds.json") -> int:
    """joueur.pied depuis moteur/pieds.json (donnees/pieds.py).

    Le pied fort est un fait sur une personne réelle : il vient de la source
    ou il reste inconnu.  Rien ici ne le déduit du poste ni des tirs — la
    part de tirs du pied droit dit « ambidextre » pour un tiers des joueurs,
    ce qui est faux (donnees/pieds.py explique la mesure).  Un joueur absent
    du fichier garde pied NULL, et la carte n'affiche rien."""
    if not fichier.exists():
        return 0
    try:
        table = json.loads(fichier.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return 0
    table.pop("_sans_pied", None)
    n = 0
    for pid, pied in table.items():
        if pied not in ("gauche", "droit", "deux"):
            continue
        n += jeu.execute("UPDATE joueur SET pied=? WHERE player_id=?", (pied, int(pid))).rowcount
    jeu.commit()
    return n


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


def main_import(fotmob: pathlib.Path, jeu_path: pathlib.Path, saison="2025/26", ligue=53) -> int:
    """Import a whole season (every gameweek) into the game base."""
    fot = sqlite3.connect(fotmob)
    jeu = ouvrir_jeu(pathlib.Path(jeu_path))
    total = 0
    for j in journees_depuis_rounds(fot, ligue):
        n = importer_journee(fot, jeu, saison, j)
        total += n
        print(f"J{j['numero']:>2}  {j['du']} -> {j['au']}  {n:>5} prestations")
    majorite_postes_et_clubs(jeu)
    importer_couleurs(jeu)
    importer_pieds(jeu)
    print(f"barème de saison : {importer_bareme(fot, jeu, saison)} fenêtres joueur x journée")
    return total


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
    ap.add_argument("--valeurs-seulement", action="store_true",
                    help="only (re)read the market values from the cached match sheets")
    ap.add_argument("--stats-seulement", action="store_true",
                    help="only fill the raw match actions (prestation.stats) from the FotMob base")
    ap.add_argument("--bareme-seulement", action="store_true",
                    help="only (re)compute the season barème windows (bareme_journee) from the FotMob base")
    a = ap.parse_args()
    if a.bareme_seulement:
        jeu = ouvrir_jeu(pathlib.Path(a.jeu))
        print(f"{importer_bareme(sqlite3.connect(a.fotmob), jeu, a.saison)} fenêtres joueur x journée -> {a.jeu}")
        return
    if a.stats_seulement:
        jeu = ouvrir_jeu(pathlib.Path(a.jeu))
        print(f"{importer_stats(sqlite3.connect(a.fotmob), jeu)} prestations, actions brutes -> {a.jeu}")
        return
    if a.couleurs_seulement:
        jeu = ouvrir_jeu(pathlib.Path(a.jeu))
        print(f"{importer_couleurs(jeu)} couleurs de club -> {a.jeu}")
        return
    if a.valeurs_seulement:
        jeu = ouvrir_jeu(pathlib.Path(a.jeu))
        mids = [r[0] for r in jeu.execute("SELECT match_id FROM match")]
        print(f"{importer_valeurs(jeu, mids)} valeurs marchandes -> {a.jeu}")
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
    npd = importer_pieds(jeu)
    nb = importer_bareme(fot, jeu, a.saison)
    print(f"{total} prestations, {len(js)} journees, {nc} couleurs de club, {npd} pieds forts, "
          f"{nb} fenêtres de barème -> {a.jeu}")


if __name__ == "__main__":
    main()

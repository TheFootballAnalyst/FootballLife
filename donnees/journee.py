#!/usr/bin/env python3
"""journee.py — les matchs d'une fenêtre, depuis FotMob, dans la base du moteur.

    py donnees/journee.py --du 2026-08-14 --au 2026-08-20           # vers moteur/fotmob_2627.db (la saison se déduit des dates)
    py donnees/journee.py --semaine                                  # les dix derniers jours
    py donnees/journee.py --du 2026-08-01 --au 2026-10-23 --fotmob moteur/fotmob_2627.db
    py donnees/journee.py --liste 2026-10-17                         # ce que FotMob liste ce jour-là, avec les identifiants
    py donnees/journee.py --semaine --entete "x-mas: ..."            # si FotMob répond 403 ; l'en-tête est gardé pour la prochaine fois

Pour chaque jour de la fenêtre : la liste des matchs du jour, réduite au
périmètre (les compétitions que le barème connaît, par identifiant ou par
nom), puis la feuille de chaque match terminé qui n'est pas déjà en cache,
écrite dans moteur/cache/matches/<id>.json et ingérée dans la base par
moteur/ingest.py. La base est ensuite finalisée : la colonne `usable` et
les vues v_match / v_appearance / v_stat que le barème lit.

Relancer ne coûte rien : une feuille en cache n'est pas redemandée, un
match déjà en base n'est pas réingéré. Seul un match listé « pas terminé »
la dernière fois est repris.

Deux adresses, les mêmes que le site : /api/matches?date=AAAAMMJJ pour la
liste d'un jour, /api/matchDetails?matchId= pour une feuille. FotMob exige
parfois un en-tête `x-mas` : il se copie depuis l'onglet Réseau du
navigateur et se passe avec --entete ; il est alors écrit dans
moteur/entetes.json et relu aux passages suivants. À lancer depuis une
machine qui atteint fotmob.com (la session distante de Claude Code ne le
peut pas).
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sqlite3
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from datetime import date, timedelta

RACINE = pathlib.Path(__file__).resolve().parent.parent
MOTEUR = RACINE / "moteur"
sys.path.insert(0, str(MOTEUR))

import ingest  # noqa: E402  (moteur/ingest.py : le schéma et l'ingestion d'une feuille)

CACHE = MOTEUR / "cache" / "matches"
ENTETES = MOTEUR / "entetes.json"
URL_JOUR = "https://www.fotmob.com/api/matches?date={jour}&timezone=UTC"
URL_MATCH = "https://www.fotmob.com/api/matchDetails?matchId={id}"
AGENT = "Mozilla/5.0"
PAUSE = 0.4            # entre deux requêtes : un rythme poli
ESSAIS = 4             # sur un 429 ou un 5xx, avec un recul doublé à chaque fois

# Le périmètre, par identifiant FotMob : les compétitions que le barème
# connaît (moteur/bareme_stats.py, COEF_COMPET_NOM) et que le jeu suit
# (jeu/pipeline.py, LIGUES). Le nom est celui que la base porte dans
# v_match.competition — sans accent, comme le palmarès les écrit.
COMPETITIONS = {
    42: "Champions League", 73: "Europa League", 10216: "Conference League",
    74: "UEFA Super Cup", 78: "Club World Cup",
    47: "Premier League", 132: "FA Cup", 133: "EFL Cup", 247: "Community Shield",
    87: "LaLiga", 138: "Copa del Rey", 139: "Supercopa de Espana",
    55: "Serie A", 141: "Coppa Italia", 222: "Supercoppa Italiana", 11015: "Supercoppa Italiana",
    54: "Bundesliga", 209: "DFB Pokal",
    53: "Ligue 1", 134: "Coupe de France", 207: "Trophee des champions",
    57: "Eredivisie", 61: "Liga Portugal", 71: "Super Lig", 40: "Jupiler Pro League",
    77: "World Cup", 50: "Euro", 44: "Copa America", 9806: "UEFA Nations League A",
}
# Les pays dont une compétition homonyme compte (« Premier League » existe
# ailleurs qu'en Angleterre) ; INT = les compétitions internationales.
PAYS = {"ENG", "ESP", "ITA", "GER", "FRA", "NED", "POR", "TUR", "BEL", "INT"}
# Ce que le barème ne doit pas voir : les qualifications (le coefficient de
# la Coupe du monde irait à ses éliminatoires), les amicaux, les jeunes, les
# réserves, le football féminin (une autre population, un autre barème).
EXCLUS = ("qualif", "friendl", "amical", "women", "femin", "u21", "u20", "u19", "u17", "youth", "reserve")
# Les noms FotMob qui ne sont pas ceux du barème.
ALIAS = {
    "fifa club world cup": "Club World Cup", "uefa champions league": "Champions League",
    "uefa europa league": "Europa League", "uefa europa conference league": "Conference League",
    "uefa conference league": "Conference League", "dfb-pokal": "DFB Pokal",
    "fa community shield": "Community Shield", "supercopa": "Supercopa de Espana",
    "super lig": "Super Lig", "euro": "Euro", "uefa euro": "Euro", "fifa world cup": "World Cup",
}


class Refus(Exception):
    """FotMob refuse la requête (401/403) : il faut l'en-tête x-mas."""


# --------------------------------------------------------------------------
# Les noms, les saisons, les en-têtes
# --------------------------------------------------------------------------

def normaliser(txt) -> str:
    n = unicodedata.normalize("NFKD", str(txt or "").lower())
    return "".join(ch for ch in n if not unicodedata.combining(ch)).strip()


NOMS = {normaliser(n) for n in COMPETITIONS.values()}


def sans_accents(txt) -> str:
    n = unicodedata.normalize("NFKD", str(txt or ""))
    return "".join(ch for ch in n if not unicodedata.combining(ch)).strip()


def nom_competition(nom_ligue, parent_id=None, noms: dict | None = None) -> str:
    """Le nom qu'une base porte pour une compétition : celui de la base de
    référence s'il est connu, sinon celui du périmètre pour cet identifiant,
    sinon l'alias du nom FotMob, sinon le nom FotMob sans accent."""
    if noms and parent_id in noms:
        return noms[parent_id]
    if parent_id in COMPETITIONS:
        return COMPETITIONS[parent_id]
    n = normaliser(nom_ligue)
    if n in ALIAS:
        return ALIAS[n]
    for cle, nom in ((normaliser(v), v) for v in COMPETITIONS.values()):
        if n == cle:
            return nom
    return sans_accents(nom_ligue)


def saison_du_jour(jour: date) -> str:
    """« 2026/27 » pour tout jour de juillet 2026 à juin 2027."""
    an = jour.year if jour.month >= 7 else jour.year - 1
    return f"{an}/{(an + 1) % 100:02d}"


def base_de_saison(saison: str) -> pathlib.Path:
    """moteur/fotmob_2627.db pour « 2026/27 »."""
    a, b = saison.split("/")
    return MOTEUR / f"fotmob_{a[-2:]}{b[-2:]}.db"


def lire_entetes(extra: list[str] | None = None, fichier: pathlib.Path = ENTETES) -> dict:
    """Les en-têtes HTTP à joindre : ceux gardés dans moteur/entetes.json,
    puis ceux de la ligne de commande (« Nom: valeur »), qui y sont écrits
    pour la prochaine fois."""
    entetes = {}
    if fichier.exists():
        try:
            entetes.update(json.loads(fichier.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            pass
    nouveaux = {}
    for e in extra or []:
        nom, _, val = e.partition(":")
        if nom.strip() and val.strip():
            nouveaux[nom.strip()] = val.strip()
    if nouveaux:
        entetes.update(nouveaux)
        fichier.parent.mkdir(parents=True, exist_ok=True)
        fichier.write_text(json.dumps(entetes, indent=1), encoding="utf-8")
    return entetes


# --------------------------------------------------------------------------
# Les requêtes
# --------------------------------------------------------------------------

def requete(url: str, entetes: dict | None = None, essais: int = ESSAIS):
    """Le JSON d'une adresse FotMob ; None sur un 404 ; Refus sur un 401/403
    (l'en-tête x-mas manque ou a expiré) ; un 429 ou un 5xx est repris."""
    req = urllib.request.Request(url, headers={"User-Agent": AGENT, "Accept": "application/json"} | (entetes or {}))
    for k in range(essais):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise Refus(f"FotMob répond {e.code} sur {url}") from None
            if e.code == 404:
                return None
            if e.code in (429, 500, 502, 503, 504) and k + 1 < essais:
                time.sleep(2 ** (k + 1))
                continue
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if k + 1 < essais:
                time.sleep(2 ** (k + 1))
                continue
            raise RuntimeError(f"{url} : {e}") from None


def dans_perimetre(ligue: dict, competitions: dict | None = None) -> bool:
    """Une compétition listée par FotMob est du périmètre par son identifiant
    (le sien, celui de sa compétition mère), ou par son nom exact dans un
    pays suivi — jamais une qualification, un amical, les jeunes."""
    competitions = COMPETITIONS if competitions is None else competitions
    ids = {ligue.get("id"), ligue.get("primaryId"), ligue.get("parentLeagueId")} - {None}
    if ids & set(competitions):
        return True
    nom = normaliser(ligue.get("name"))
    if any(x in nom for x in EXCLUS):
        return False
    return ligue.get("ccode") in PAYS and nom in NOMS


def matchs_du_jour(doc, competitions: dict | None = None) -> list[dict]:
    """Les matchs du périmètre dans la liste d'un jour : identifiant, nom de
    la compétition, terminé ou non, les deux équipes."""
    out = []
    for ligue in (doc or {}).get("leagues") or []:
        if not dans_perimetre(ligue, competitions):
            continue
        for m in ligue.get("matches") or []:
            st = m.get("status") or {}
            mid = m.get("id")
            if mid is None:
                continue
            out.append(dict(id=int(mid), ligue=ligue.get("name"), ligue_id=ligue.get("primaryId") or ligue.get("id"),
                            termine=bool(st.get("finished")), annule=bool(st.get("cancelled")),
                            home=(m.get("home") or {}).get("name"), away=(m.get("away") or {}).get("name"),
                            utc=st.get("utcTime")))
    return out


def lire_feuille(f: pathlib.Path):
    """La feuille en cache si elle est lisible et terminée, sinon None (elle
    sera redemandée)."""
    if not f.exists():
        return None
    try:
        doc = json.loads(f.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not (ingest.unwrap(doc).get("general") or {}).get("finished"):
        return None
    return doc


def en_base(conn: sqlite3.Connection, mid: int) -> bool:
    """Le match est ingéré : terminé, avec sa feuille."""
    r = conn.execute("SELECT finished FROM match WHERE match_id=?", (mid,)).fetchone()
    if not r or not r[0]:
        return False
    return conn.execute("SELECT 1 FROM appearance WHERE match_id=? LIMIT 1", (mid,)).fetchone() is not None


def jours(du: date, au: date):
    d = du
    while d <= au:
        yield d
        d += timedelta(days=1)


# --------------------------------------------------------------------------
# La finalisation : ce que le barème lit en plus des tables d'ingest.py
# --------------------------------------------------------------------------

VUES = {
    "v_match": """CREATE VIEW v_match AS
        SELECT m.*, COALESCE(c.nom, m.league_name) AS competition
        FROM match m LEFT JOIN competition c ON c.league_id = COALESCE(m.parent_league_id, m.league_id)
        WHERE m.usable = 1""",
    "v_appearance": """CREATE VIEW v_appearance AS
        SELECT a.* FROM appearance a JOIN match m ON m.match_id = a.match_id WHERE m.usable = 1""",
    "v_stat": """CREATE VIEW v_stat AS
        SELECT s.* FROM stat s JOIN match m ON m.match_id = s.match_id WHERE m.usable = 1""",
}


def finaliser(conn: sqlite3.Connection, noms: dict | None = None) -> int:
    """Rendre une base d'ingest.py lisible par le barème : `match.usable`
    (terminé, avec sa feuille), la table `competition` (le nom par
    compétition mère) et les vues v_match, v_appearance, v_stat. Retourne
    le nombre de matchs utilisables."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(match)")}
    if "usable" not in cols:
        conn.execute("ALTER TABLE match ADD COLUMN usable INTEGER")
    conn.execute("""UPDATE match SET usable = CASE WHEN finished = 1 AND EXISTS
                    (SELECT 1 FROM appearance a WHERE a.match_id = match.match_id) THEN 1 ELSE 0 END""")
    conn.execute("CREATE TABLE IF NOT EXISTS competition (league_id INTEGER PRIMARY KEY, nom TEXT NOT NULL)")
    for lid, nom in (noms or {}).items():
        conn.execute("INSERT OR REPLACE INTO competition VALUES (?, ?)", (int(lid), nom))
    for lid, lname in conn.execute("""SELECT COALESCE(parent_league_id, league_id), MIN(league_name)
                                      FROM match GROUP BY 1""").fetchall():
        if lid is None:
            continue
        if not conn.execute("SELECT 1 FROM competition WHERE league_id=?", (lid,)).fetchone():
            conn.execute("INSERT INTO competition VALUES (?, ?)", (lid, nom_competition(lname, lid, noms)))
    for nom, sql in VUES.items():
        conn.execute(f"DROP VIEW IF EXISTS {nom}")
        conn.execute(sql)
    conn.commit()
    return conn.execute("SELECT COUNT(*) FROM match WHERE usable = 1").fetchone()[0]


def noms_de_reference(base: pathlib.Path) -> dict[int, str]:
    """Le nom que la base d'une saison précédente donne à chaque compétition
    mère (v_match.competition) : la base neuve reprend la même convention,
    le barème et le palmarès lisent les compétitions par leur nom."""
    if not base or not pathlib.Path(base).exists():
        return {}
    conn = sqlite3.connect(f"file:{base}?mode=ro", uri=True)
    try:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='v_match'").fetchone():
            return {}
        votes: dict[int, dict[str, int]] = {}
        for lid, nom, n in conn.execute("""SELECT parent_league_id, competition, COUNT(*) FROM v_match
                                           WHERE parent_league_id IS NOT NULL AND competition IS NOT NULL
                                           GROUP BY 1, 2"""):
            votes.setdefault(int(lid), {})[nom] = n
        return {lid: max(v, key=v.get) for lid, v in votes.items()}
    except sqlite3.Error:
        return {}
    finally:
        conn.close()


# --------------------------------------------------------------------------
# La récupération d'une fenêtre
# --------------------------------------------------------------------------

def recuperer(du: date, au: date, fotmob: pathlib.Path, cache: pathlib.Path = CACHE, entetes: dict | None = None,
              competitions: dict | None = None, noms: dict | None = None, pause: float | None = None,
              journal=print) -> dict:
    """Les matchs terminés du périmètre entre `du` et `au` (inclus) : listés
    jour par jour, feuilles mises en cache puis ingérées dans `fotmob`, base
    finalisée. Retourne le bilan."""
    pause = PAUSE if pause is None else pause
    cache = pathlib.Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    pathlib.Path(fotmob).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(fotmob)
    conn.executescript(ingest.SCHEMA)
    ingest.migrate(conn)
    bilan = dict(du=du.isoformat(), au=au.isoformat(), jours=0, listes=0, termines=0, telecharges=0,
                 en_cache=0, ingeres=0, non_termines=[], erreurs=[])
    suite_erreurs = 0
    try:
        for jour in jours(du, au):
            bilan["jours"] += 1
            doc = requete(URL_JOUR.format(jour=jour.strftime("%Y%m%d")), entetes)
            time.sleep(pause)
            du_jour = matchs_du_jour(doc, competitions)
            for m in du_jour:
                bilan["listes"] += 1
                mid = m["id"]
                if not m["termine"]:
                    if not m["annule"]:
                        bilan["non_termines"].append(f"{jour} {m['ligue']} : {m['home']} - {m['away']} ({mid})")
                    continue
                bilan["termines"] += 1
                f = cache / f"{mid}.json"
                feuille = lire_feuille(f)
                if feuille is None:
                    try:
                        feuille = requete(URL_MATCH.format(id=mid), entetes)
                    except Refus:
                        raise
                    except Exception as e:  # noqa: BLE001
                        suite_erreurs += 1
                        bilan["erreurs"].append(f"{mid} : {e}")
                        if suite_erreurs >= 10:
                            raise RuntimeError("dix feuilles de suite en erreur : FotMob ne répond plus, on s'arrête") from None
                        continue
                    finally:
                        time.sleep(pause)
                    if feuille is None:
                        bilan["erreurs"].append(f"{mid} : feuille introuvable (404)")
                        continue
                    f.write_text(json.dumps(feuille), encoding="utf-8")
                    bilan["telecharges"] += 1
                else:
                    bilan["en_cache"] += 1
                suite_erreurs = 0
                if not en_base(conn, mid):
                    try:
                        ingest.ingest(conn, ingest.parse(ingest.unwrap(feuille)))
                        bilan["ingeres"] += 1
                    except Exception as e:  # noqa: BLE001
                        bilan["erreurs"].append(f"{mid} : feuille illisible ({type(e).__name__}: {e})")
            conn.commit()
            journal(f"  {jour}  {len(du_jour):>3} matchs du périmètre, "
                    f"{bilan['telecharges']} feuilles téléchargées, {bilan['ingeres']} ingérées jusqu'ici")
    except Refus as e:
        conn.commit()
        raise SystemExit(f"{e}\nFotMob refuse : copie l'en-tête x-mas depuis l'onglet Réseau de ton navigateur "
                         f"(une requête vers fotmob.com/api/…) et relance avec --entete \"x-mas: …\". "
                         f"Ce qui a été récupéré jusqu'ici est gardé.") from None
    bilan["utilisables"] = finaliser(conn, noms)
    conn.close()
    return bilan


def resume(bilan: dict) -> str:
    lignes = [f"{bilan['du']} → {bilan['au']} : {bilan['jours']} jours, {bilan['listes']} matchs listés dans le périmètre, "
              f"{bilan['termines']} terminés ; {bilan['telecharges']} feuilles téléchargées, {bilan['en_cache']} déjà en cache, "
              f"{bilan['ingeres']} ingérées ; {bilan.get('utilisables', 0)} matchs utilisables dans la base"]
    if bilan["non_termines"]:
        lignes.append(f"  pas encore terminés ({len(bilan['non_termines'])}) : " + " ; ".join(bilan["non_termines"][:6])
                      + (" …" if len(bilan["non_termines"]) > 6 else ""))
    if bilan["erreurs"]:
        lignes.append(f"  en erreur ({len(bilan['erreurs'])}) : " + " ; ".join(bilan["erreurs"][:6])
                      + (" …" if len(bilan["erreurs"]) > 6 else ""))
    return "\n".join(lignes)


def lister(jour: date, entetes: dict | None = None) -> list[str]:
    """Ce que FotMob liste ce jour-là, une ligne par compétition, avec les
    identifiants et si elle est du périmètre : pour vérifier et compléter
    COMPETITIONS quand un identifiant change."""
    doc = requete(URL_JOUR.format(jour=jour.strftime("%Y%m%d")), entetes) or {}
    out = []
    for ligue in doc.get("leagues") or []:
        n = len(ligue.get("matches") or [])
        t = sum(1 for m in ligue.get("matches") or [] if (m.get("status") or {}).get("finished"))
        out.append(f"{'●' if dans_perimetre(ligue) else ' '} {str(ligue.get('id')):>6} (mère {str(ligue.get('primaryId')):>6})  "
                   f"{ligue.get('ccode') or '':4} {ligue.get('name')}  — {n} matchs, {t} terminés")
    return out


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")      # une console Windows redirigée n'a pas toujours l'UTF-8
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--du", help="premier jour (AAAA-MM-JJ)")
    ap.add_argument("--au", help="dernier jour, inclus (défaut : aujourd'hui)")
    ap.add_argument("--semaine", action="store_true", help="les dix derniers jours")
    ap.add_argument("--fotmob", default=None, help="la base du moteur (défaut : moteur/fotmob_AABB.db de la saison des dates)")
    ap.add_argument("--cache", default=str(CACHE))
    ap.add_argument("--reference", default=None, help="base FotMob d'une saison précédente, pour reprendre ses noms de compétitions")
    ap.add_argument("--competition", type=int, action="append", default=[], help="identifiant FotMob à ajouter au périmètre (répétable)")
    ap.add_argument("--entete", action="append", default=[], help='en-tête HTTP « Nom: valeur », répétable, gardé dans moteur/entetes.json')
    ap.add_argument("--liste", default=None, help="afficher ce que FotMob liste ce jour-là (AAAA-MM-JJ) et s'arrêter")
    a = ap.parse_args()
    entetes = lire_entetes(a.entete)
    if a.liste:
        print("\n".join(lister(date.fromisoformat(a.liste), entetes)))
        return
    au = date.fromisoformat(a.au) if a.au else date.today()
    if a.semaine:
        du = au - timedelta(days=10)
    elif a.du:
        du = date.fromisoformat(a.du)
    else:
        sys.exit("--du AAAA-MM-JJ, ou --semaine")
    fotmob = pathlib.Path(a.fotmob) if a.fotmob else base_de_saison(saison_du_jour(au))
    competitions = dict(COMPETITIONS) | {c: f"competition {c}" for c in a.competition}
    noms = noms_de_reference(pathlib.Path(a.reference)) if a.reference else None
    print(f"{du} → {au}, vers {fotmob} (cache {a.cache})")
    bilan = recuperer(du, au, fotmob, pathlib.Path(a.cache), entetes, competitions, noms)
    print(resume(bilan))


if __name__ == "__main__":
    main()

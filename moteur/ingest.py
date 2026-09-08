#!/usr/bin/env python3
"""FotMob — parser et ingestion SQLite (v2)."""
import glob, json, pathlib, sqlite3, sys

DB_PATH = pathlib.Path("fotmob.db")
SCHEMA = """
CREATE TABLE IF NOT EXISTS match (
    match_id INTEGER PRIMARY KEY, date_utc TEXT NOT NULL, league_id INTEGER,
    league_name TEXT, parent_league_id INTEGER, round TEXT,
    home_team_id INTEGER, home_team TEXT, away_team_id INTEGER, away_team TEXT,
    home_score INTEGER, away_score INTEGER, finished INTEGER,
    coverage_level TEXT, gender TEXT);
CREATE TABLE IF NOT EXISTS player (player_id INTEGER PRIMARY KEY, name TEXT, opta_id TEXT);
CREATE TABLE IF NOT EXISTS appearance (
    match_id INTEGER NOT NULL, player_id INTEGER NOT NULL, team_id INTEGER,
    team_name TEXT, shirt_number TEXT, position_id INTEGER, is_goalkeeper INTEGER,
    PRIMARY KEY (match_id, player_id));
CREATE TABLE IF NOT EXISTS stat (
    match_id INTEGER NOT NULL, player_id INTEGER NOT NULL, stat_key TEXT NOT NULL,
    value REAL, total REAL, stat_type TEXT,
    PRIMARY KEY (match_id, player_id, stat_key));
CREATE TABLE IF NOT EXISTS event (
    match_id INTEGER NOT NULL, ordinal INTEGER NOT NULL, event_id TEXT,
    minute INTEGER, type TEXT, player_id INTEGER, assist_player_id INTEGER,
    own_goal INTEGER, is_home INTEGER, PRIMARY KEY (match_id, ordinal));
CREATE INDEX IF NOT EXISTS idx_stat_player ON stat(player_id, stat_key);
CREATE INDEX IF NOT EXISTS idx_stat_key ON stat(stat_key);
CREATE INDEX IF NOT EXISTS idx_match_date ON match(date_utc);
CREATE INDEX IF NOT EXISTS idx_app_player ON appearance(player_id);
CREATE INDEX IF NOT EXISTS idx_event_pl ON event(player_id, type);
"""
MIGRATIONS = {"match": [("coverage_level", "TEXT"), ("gender", "TEXT")]}


def migrate(conn):
    for table, columns in MIGRATIONS.items():
        existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        for name, sql_type in columns:
            if name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {sql_type}")
    cols = {row[1] for row in conn.execute("PRAGMA table_info(event)")}
    if cols and "ordinal" not in cols:
        conn.execute("DROP TABLE event"); conn.executescript(SCHEMA)
    conn.commit()


def unwrap(doc):
    if "props" in doc and "pageProps" in doc.get("props", {}):
        return doc["props"]["pageProps"]
    return doc


def player_id_from_url(url):
    if not url: return None
    parts = [p for p in url.split("/") if p.isdigit()]
    return int(parts[0]) if parts else None


def parse(pp):
    general = pp.get("general", {}); header = pp.get("header", {})
    content = pp.get("content", {}); teams = header.get("teams", [])
    home = teams[0] if len(teams) > 0 else {}
    away = teams[1] if len(teams) > 1 else {}
    match_id = general.get("matchId")
    if match_id is None: raise ValueError("matchId absent")
    match_row = (match_id, general.get("matchTimeUTCDate"), general.get("leagueId"),
        general.get("leagueName"), general.get("parentLeagueId"), general.get("matchRound"),
        (general.get("homeTeam") or {}).get("id"), (general.get("homeTeam") or {}).get("name"),
        (general.get("awayTeam") or {}).get("id"), (general.get("awayTeam") or {}).get("name"),
        home.get("score"), away.get("score"), 1 if general.get("finished") else 0,
        general.get("coverageLevel"), general.get("gender"))
    players, appearances, stats = [], [], []
    for pid_str, p in (content.get("playerStats") or {}).items():
        pid = p.get("id") or int(pid_str)
        players.append((pid, p.get("name"), p.get("optaId")))
        appearances.append((match_id, pid, p.get("teamId"), p.get("teamName"),
            p.get("shirtNumber"), p.get("positionId"), 1 if p.get("isGoalkeeper") else 0))
        vus = set()
        for block in p.get("stats") or []:
            for label, entry in (block.get("stats") or {}).items():
                key = entry.get("key")
                if not key or key in vus: continue
                vus.add(key)
                st = entry.get("stat") or {}
                stats.append((match_id, pid, key, st.get("value"), st.get("total"),
                              st.get("type")))
    events = []
    ev = (content.get("matchFacts") or {}).get("events") or {}
    for ordinal, e in enumerate(ev.get("events") or []):
        events.append((match_id, ordinal,
            str(e.get("eventId")) if e.get("eventId") is not None else None,
            e.get("time"), e.get("type"), (e.get("player") or {}).get("id"),
            player_id_from_url(e.get("assistProfileUrl")),
            1 if e.get("ownGoal") else 0, 1 if e.get("isHome") else 0))
    return {"match": match_row, "players": players, "appearances": appearances,
            "stats": stats, "events": events}


def ingest(conn, parsed):
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO match (match_id, date_utc, league_id, league_name,"
        " parent_league_id, round, home_team_id, home_team, away_team_id, away_team,"
        " home_score, away_score, finished, coverage_level, gender)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", parsed["match"])
    c.executemany("INSERT OR REPLACE INTO player VALUES (?,?,?)", parsed["players"])
    c.executemany("INSERT OR REPLACE INTO appearance VALUES (?,?,?,?,?,?,?)", parsed["appearances"])
    c.executemany("INSERT OR REPLACE INTO stat VALUES (?,?,?,?,?,?)", parsed["stats"])
    c.executemany("INSERT OR REPLACE INTO event VALUES (?,?,?,?,?,?,?,?,?)", parsed["events"])


def main():
    if len(sys.argv) < 2: sys.exit(__doc__)
    paths = []
    for arg in sys.argv[1:]:
        p = pathlib.Path(arg)
        if p.is_dir(): paths.extend(sorted(p.glob("*.json")))
        else: paths.extend(pathlib.Path(x) for x in glob.glob(arg))
    if not paths: sys.exit("Aucun fichier JSON trouve.")
    conn = sqlite3.connect(DB_PATH); conn.executescript(SCHEMA); migrate(conn)
    ok = failed = 0; problems = []
    for n, path in enumerate(paths, 1):
        try:
            ingest(conn, parse(unwrap(json.loads(path.read_text(encoding="utf-8")))))
            ok += 1
        except Exception as exc:
            failed += 1; problems.append(f"{path.name} : {type(exc).__name__}: {exc}")
        if n % 200 == 0 or n == len(paths): conn.commit()
    conn.commit()
    print(f"{ok} fichier(s) charge(s), {failed} echec(s).")
    for line in problems[:20]: print(" ", line)
    conn.close()


if __name__ == "__main__":
    main()

# Roadmap — from a rating engine to a playable game

You have never built a game; that is fine, because most of this one is
not game code. The engine is done. What remains is, in order of risk:
(1) an economy that stays balanced over a season, (2) a weekly pipeline
that turns real matches into scores without human intervention, (3) a
user interface, (4) accounts and hosting. Build in that order. The UI is
the most visible piece and the last one to start.

## Phase 0 — foundations (this commit)

- Engine under Git, untouched, as a library (`moteur/`).
- Game layer with pure functions and tests (`jeu/`): note out of 10,
  card attributes, gameweek scoring, card and budget evolution.
- Game database schema (`jeu/schema.sql`).
- Design decisions written down (`docs/GAME_DESIGN.md`).

## Phase 1 — backtest the economy on 2025/26 (2–3 weeks)

Goal: replay a whole season of the *game* offline, before writing a single
screen. You have every match of 2025/26 in `fotmob.db`; that is a full
season of ground truth for free.

1. `jeu/importer.py` — run `topsflops.calculer()` window by window over
   the season, compute note and attributes, write `prestation` rows.
2. `jeu/journees.py` — cut the season into gameweeks (league round +
   following midweek).
3. `jeu/backtest.py` — seed cards from 2024/25 notes, then for each
   gameweek: score a handful of scripted managers (naive, informed,
   random), update every card's OVR and price, pay out.
4. Read the four questions at the end of `GAME_DESIGN.md` off the
   output. Tune the constants in `evolution.py` and `scoring.py`. Repeat.

Deliverable: a CSV of card prices per gameweek and a table of manager
budgets per strategy. Also the first real card images, since `carte()`
can now be fed real notes and attributes.

Exit criterion: the informed strategy beats the naive one by a margin
you find fair, and no card sits on the floor or ceiling all season.

## Phase 2 — the weekly pipeline (2 weeks)

Goal: one command turns a finished gameweek into frozen results.

1. `jeu/cloture.py` — lock lineups at first kick-off.
2. `jeu/calcul.py` — after the last match: import performances, score
   every submitted lineup, apply auto-subs, update cards, write
   `resultat` and `carte_historique`.
3. Idempotent: running it twice on the same gameweek changes nothing.
4. A `--dry-run` that prints what would change.

Deliverable: the whole of 2025/26 replayed through the *live* code path,
results identical to the backtest.

## Phase 3 — the interface (4–6 weeks)

Goal: a manager can do everything the game needs from a browser.

Stack recommendation: **FastAPI** for the API (the engine and Pillow are
Python, keep one language server-side), **SQLite** until there are
enough managers that it hurts, then Postgres with the same schema.
Front-end: **React + Vite** (or Svelte); a lineup screen with drag and
drop and a price chart per card wants a real front-end, not templates.

Screens, in the order they unblock play:

1. Market — cards with OVR, price, position, club; filters; buy/sell.
2. Squad and lineup — formation picker, eleven, bench order, captain;
   validation from `scoring.formation_legale`; lock countdown.
3. Gameweek result — team score with per-card breakdown, auto-subs
   flagged.
4. Card page — the PNG from `carte_design.carte`, note history, price
   history, attributes.
5. Standings — game league table, weekly and season.

## Phase 4 — accounts and hosting (1–2 weeks)

- Auth: email + magic link is enough for a first season; no passwords
  to store.
- Hosting: one small VM or a PaaS (Fly.io, Railway). The weekly pipeline
  is a cron job on the same box. Card PNGs are generated once per
  gameweek and served as static files.
- Backups of the game database after every gameweek.

## Phase 5 — first live season

- One game league, Ligue 1 + UCL, invited managers.
- A "what changed" note per gameweek for the players (the engine's
  tops/flops output is already a good draft of it).
- Collect the data you will need to re-tune for season two.

## Not before season two

Manager traits, peer trading, ownership caps, the other four leagues as
separate game leagues, mobile app.

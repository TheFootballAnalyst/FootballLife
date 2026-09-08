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

## Phase 1 — backtest the economy on 2025/26 (done)

`jeu/importer.py` cuts the season into gameweeks and rates every
performance into the game base; `jeu/backtest.py` replays J18–J34 with
scripted managers after seeding cards on J1–J17; `jeu/cartes.py` renders
match and season cards. Results and settings in `docs/BACKTEST.md`: on
the global league, informed beats naive by 30 % in points and 44 % in
value, random is far behind, the oracle keeps a 9 % margin. Decided: the
perimeter is global and the Champions League weighting stays in the note.

Left open from this phase:
- `SCORE_REFERENCE` for payouts, to be reset once real managers' scores
  are observed;
- the top of the OVR scale: with a half-season seed, four cards hit 99 in
  spring; re-check with a full previous season;
- portraits: fetched by `donnees/portraits.py` on a machine that can
  reach images.fotmob.com (the remote session cannot).

## Phase 2 — the weekly pipeline (done)

`jeu/pipeline.py`: `journees` cuts the live season into gameweeks from
the FotMob base, `amorcer` seeds a season's cards from another season
(and freezes the OVR scale and the economy constants in `parametre`),
`calculer --journee N` imports the window's performances, moves every
card, scores every composition submitted before the lock, pays out and
closes the gameweek; `--dry-run` shows what would change. Idempotent:
a gameweek is always recomputed from the card state after the previous
one, so running it twice changes nothing. Five tests in
`jeu/tests/test_pipeline.py`.

Exit check passed: `jeu/rejouer.py` pushes 2025/26 J18–J34 through the
live path with a witness manager and gets exactly the backtest's naive
score, 1 391.5, with zero difference on any gameweek or card.

Not in this phase, by choice: the weekly *trigger* (a cron that runs
`calculer` after the last match of the window) belongs with hosting,
phase 4.

## Phase 2b — the market, second design (new)

From the prototype's feedback (`GAME_DESIGN.md`, "After playing the
prototype"): one owner per card per league, a draft at season start,
contracts, offers between managers, bids at contract end. Data model
changes (`effectif` with contract, `offre`, draft picks), then the
backtest re-run with several managers competing for the same cards to
re-tune prices under scarcity. This comes before the interface, because
the interface's main screens (draft, offers) depend on it.

## Phase 3 — the interface (4–6 weeks)

The browser prototype (`web/`, docs/PROTOTYPE.md) is the sketch of the
market, lineup and gameweek screens; the real interface adds accounts,
the draft, offers and the live calendar.

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

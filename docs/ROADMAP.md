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

## Phase 2b — demand pricing (decided, small)

From the prototype's feedback and the "global game" constraint
(`GAME_DESIGN.md`, "how the market gets scarce"): a card's price follows
the share of managers who own it. Backtested (`jeu/backtest.py
--demande`), decided. To do: the weekly pipeline computes each card's
ownership share from `effectif` and applies the multiplier when it
reprices; `parametre` gains `demande`. Private draft leagues (exclusivity
inside a league of ten) are an optional later format, not a prerequisite
for the interface.

## Phase 3 — the interface (done)

`web/app/`: FastAPI + SQLite + one HTML page. Accounts, the world market
(demand pricing recomputed at each close), lineup on a pitch, gameweek
results, world and private standings, an Admin screen that locks or
reopens a gameweek, loads the rated performances exported locally by
`jeu/exporter_journee.py` and closes the gameweek through
`jeu/pipeline.py`. Six API tests (34 in total). `web/app/demo.py` builds
a demo base on 2025/26 from J18 so several people can play before the
live season. See `docs/SITE.md`.

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

## Phase 4 — hosting (next)

- Accounts are pseudo + password (done in phase 3; magic links need an
  email provider, later).
- Hosting: the `Dockerfile` on a PaaS with a persistent volume (Fly.io,
  Railway, Render) or a small VPS. The weekly close is done by the admin
  from the site; the engine runs on the owner's machine, which exports
  one JSON per gameweek.
- Backups: copy `/data/jeu.sqlite` after every close.
- Card PNGs (`jeu/cartes.py`) as shareable images: later.

## Phase 5 — first live season

- One game league, Ligue 1 + UCL, invited managers.
- A "what changed" note per gameweek for the players (the engine's
  tops/flops output is already a good draft of it).
- Collect the data you will need to re-tune for season two.

## Phase 3b — the mercato (done)

The card pool no longer freezes on the seed: `pipeline.integrer_nouveaux`
opens a card at the close for anyone who entered the perimeter that
gameweek, seeded on his own last season when the engine covers his old
league and on his position's rotation-player median otherwise, priced on
his real market value, with the wide bound of `bareme.borne`. See
`GAME_DESIGN.md` and the replay in `BACKTEST.md`.

## Phase 3c — the ranked lobby (done)

`jeu/simulation.py` plays a match from the CARDS: six team traits read
from the attributes, three tactical axes that form a cycle, minute-by-
minute dice fixed by the seed so the match is reproducible and the live
view can advance without rewriting itself. Calibrated in `BACKTEST.md`.

`jeu/lobby.py` and the Lobby screen add the rest: pairing within 250
points of a ranked Elo of its own, a server clock that plays the ninety
minutes over four real ones, a live feed, tactical adjustments stamped at
the minute the clock says, a défi against a generated eleven when nobody
is waiting, and the ranked standing. Nine tests in
`jeu/tests/test_lobby.py`, plus an end-to-end run of two managers in
Chromium.

The weekly head-to-head resolved from real actions has been retired: the
cards have a match of their own, and two competitive matches split the
attention and the ladders for no gain. `jeu/match.py` is gone, its Elo
maths live on in `jeu/elo.py`, and the gameweek keeps what only it can
do — moving every card and ranking the week's scores.

## Not before season two

Manager traits, peer trading, ownership caps, the other four leagues as
separate game leagues, mobile app.

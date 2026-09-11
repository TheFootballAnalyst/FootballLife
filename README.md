# FootballLife

A squad-management card game where every point comes from **real
performances**. No match is simulated: after each real gameweek, every
player's performance is rated by a validated scoring engine, and the cards
a manager lined up score exactly that.

The engine finds the real Ballon d'Or winner five seasons out of five.
The game is a way to play with it.

## How it plays

1. Join a game league with a budget; buy 15 cards at their current price.
2. Before each gameweek, set a formation, an eleven, a bench order and a
   captain. Lineups lock at the first kick-off.
3. After the matches, each card gets its note out of 10 per match. Your
   team score is the sum over the eleven (auto-subs from the bench for
   anyone who did not play, ×1.5 for the captain; the Champions League
   already weighs more inside the note).
4. Every card's rating (OVR 40–99) moves with its notes, and its price
   follows: a card starts the season at the player's real market value
   (in euros) and doubles every +8 OVR. You have 100 M€. Buy low before a
   card climbs and you own something worth more than you paid. Weekly
   results pay out a few million on top.

Spotting under-priced players is the skill the game rewards.

## Layout

```
moteur/     the rating engine — a library, do not rewrite (see moteur/LISEZMOI.md)
jeu/        the game layer: pure functions + schema, all tested
  notation.py    engine output -> note out of 10 and six card attributes
                 (40/40 notes and 240/240 attributes exact vs the visual pipeline)
  scoring.py     lineup + performances -> team score for a gameweek
  evolution.py   card OVR, price, manager budget over time
  importer.py    fotmob.db -> game base (gameweeks, rated performances, club colours, barème windows)
  bareme.py      the season barème (moteur/bareme_stats.py + palmares_zero.py) -> OVR, attributes, evolution
  simulation.py  the ranked lobby match: the cards play it, tactics decide the scenario
  lobby.py       pairing, the server clock, live adjustments, the ranked ladder
  elo.py         the ladder maths
  pipeline.py    the live weekly path: gameweeks, seed, close a gameweek (idempotent)
  rejouer.py     phase 2 exit check: a season through the live path = the backtest
  backtest.py    replay a season with scripted managers
  cartes.py      render match and season cards from the game base
  schema.sql     the game database
  tests/         incl. the reference performances in tests/donnees/
donnees/    league logos; scripts to fetch the FotMob base and the portraits
web/app/    the site: FastAPI server, single-page front-end, demo base builder (docs/SITE.md)
web/        the earlier solo browser prototype (template + build scripts), see docs/PROTOTYPE.md
Dockerfile  the site in one container
docs/
  SITE.md        the site: screens, rules, running it, the weekly admin routine, hosting (French)
  PROTOTYPE.md   the prototype's URL, screens, how to rebuild it (French)
  GUIDE_DEBUTANT.md  step-by-step, from installing Python to the first cards (French)
  CONTEXTE.md    the original project brief (French)
  REPONSES.md    answers on families, attribute floor, UCL bonus (French)
  GAME_DESIGN.md decisions: perimeter, cadence, valuation, rules
  BACKTEST.md    the 2025/26 season replayed: settings, results, the PSG finding
  DATA_MODEL.md  the two databases and the weekly write path
  ROADMAP.md     phases, in order of risk: economy, pipeline, UI, hosting
```

## Running

```
pip install -r requirements.txt
python3 -m pytest jeu/tests
```

The engine itself needs a FotMob base (`fotmob.db`, one per season,
300–550 MB), the match cache and the player portraits, none of which are
in the repository (see `donnees/README.md`; fonts and club logos are).
The game layer's tests run without them.

## Replaying a season

```
python3 donnees/telecharger.py <release asset url>   # fotmob.db + cache into moteur/
python3 donnees/portraits.py                         # portraits into moteur/images/joueurs/
python3 donnees/pieds.py                             # preferred foot -> moteur/pieds.json
python3 -m jeu.importer                              # -> jeu/jeu_2526.sqlite
python3 -m jeu.backtest                              # -> out/ (global league)
python3 -m jeu.cartes --journee 34 --n 8             # -> out/cartes/*.png
```

## Where things stand

Phases 0, 1 and 2 of `docs/ROADMAP.md` are done: engine under Git, game
rules as code matching the production pipeline exactly (105 reference
performances), the 2025/26 season imported and replayed, the economy
tuned (`docs/BACKTEST.md`), cards rendered, a browser prototype to play
with (`docs/PROTOTYPE.md`), and the live weekly pipeline verified
against the backtest to the decimal. The perimeter is one global league.
Phase 3 is built: the site (`docs/SITE.md`) with accounts, a world
market with demand pricing, lineups, gameweeks closed by the admin from
rated performances exported locally, world and private standings.
Next: hosting (phase 4) and the first live season.

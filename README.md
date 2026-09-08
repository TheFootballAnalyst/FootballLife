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
   anyone who did not play, ×1.5 for the captain, ×1.25 in the Champions
   League).
4. Every card's rating (OVR 40–99) moves with its notes, and its price
   follows. Buy low before a card climbs and you own something worth more
   than you paid. Weekly results pay out a few credits on top.

Spotting under-priced players is the skill the game rewards.

## Layout

```
moteur/     the rating engine — a library, do not rewrite (see moteur/LISEZMOI.md)
jeu/        the game layer: pure functions + schema, all tested
  notation.py    engine output -> note out of 10 and six card attributes
  scoring.py     lineup + performances -> team score for a gameweek
  evolution.py   card OVR, price, manager budget over time
  schema.sql     the game database
  tests/
donnees/    league logos for the cards
docs/
  CONTEXTE.md    the original project brief (French)
  GAME_DESIGN.md decisions: perimeter, cadence, valuation, rules
  DATA_MODEL.md  the two databases and the weekly write path
  ROADMAP.md     phases, in order of risk: economy, pipeline, UI, hosting
```

## Running

```
pip install -r requirements.txt
python3 -m pytest jeu/tests
```

The engine itself needs a FotMob base (`fotmob.db`), the match cache and
the fonts/portraits, none of which are in the repository (see
`.gitignore`). The game layer's tests run without them.

## Where things stand

Phase 0 of `docs/ROADMAP.md` is done: engine under Git, game rules as
code, database designed, decisions written. Next is phase 1: replay the
2025/26 season through the game offline and tune the economy before any
screen is built.

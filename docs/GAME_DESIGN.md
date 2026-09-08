# Game design — decisions and proposals

Companion to `CONTEXTE.md`. That document lists three open questions
(section 4). This one answers them with a recommendation each, and writes
down the card economy that `jeu/evolution.py` and `jeu/scoring.py`
implement. Every number is a starting value to be tuned by the backtest
(see `ROADMAP.md`, phase 1), not a rule.

## The loop, in one paragraph

A manager joins a game league with a budget, buys 15 cards (11 + 4 bench)
at their current price, and before each gameweek submits a formation, a
starting eleven, a bench order and a captain. After the matches, every card
that played receives the engine's note out of 10 for each match; the team
score is the sum over the eleven. The score ranks the manager for the week
and pays out credits. Meanwhile every card's rating (OVR) moves with its
notes, and its price follows its OVR. A manager who bought a cheap card
before its OVR rose owns something worth more than they paid. That gap,
plus weekly payouts, is what a manager builds a better team with.

## The three open questions

### 1. Perimeter — start with Ligue 1 + Champions League, model for all five

Recommendation: the first live season runs on **Ligue 1 plus the
Champions League matches of Ligue 1 clubs**. The engine already rates the
five leagues, so the data model carries a `perimetre` per game league
(`ligue_jeu.perimetre`, a list of competition ids) from day one. Opening a
"Top 5 + UCL" league later is a configuration row, not a rewrite.

Why not everything at once: balancing the economy is hard enough on one
pool of ~500 players; the first season is the one where prices and payouts
get tuned in public, and mistakes are cheaper on a small pool.

### 2. Frequency — one gameweek per league round, midweek included

A **gameweek** is a date window (`journee.du` to `journee.au`) that groups
a league round and the European midweek that follows it. Lineups lock at
the first kick-off of the window. A card that plays twice in the window
scores twice.

This matches how the engine already works (`topsflops.py --du --au`) and
how the audience follows football. Slower cadences (fortnightly) lose the
Tuesday-night moments the UCL multiplier is meant to reward.

### 3. Valuation — from last season's notes, cautious on thin samples

This is the structuring decision. The proposal:

**Start of season.** A card's rating-note is the minutes-weighted mean of
its notes last season, **shrunk towards a prior of 5.5** with the weight of
ten full matches (`evolution.note_initiale`). Consequences:

- a player with a full season at 7.0 starts around OVR 71;
- a player with three matches at 8.0 starts around OVR 65;
- a newcomer with no data starts at OVR 58, price under 1 credit.

The prior sits *below* the median on purpose. The game is meant to reward
knowledge of low-cost players, so the unknowns must be cheap enough that
being right about them pays.

**In season.** After every match the rating-note moves by 12 % of the gap
to the new note, scaled by minutes (`evolution.note_ema`). Ten matches
at 7.5 lift a card from OVR 64 to 76; one good match barely moves it.
That is slow enough that a manager who spots a trend early has time to buy,
fast enough that the card visibly "evolves" over a month.

**Price.** `prix = 2 ^ ((OVR − 60) / 8)`, floor 0.5 credits:

| OVR | 52 | 60 | 68 | 76 | 84 | 92 | 99 |
|-----|----|----|----|----|----|----|----|
| credits | 0.5 | 1 | 2 | 4 | 8 | 16 | 29.5 |

Exponential so that the top of the market is scarce: with 100 credits for
15 cards, spreading evenly buys an OVR-82 squad; one OVR-95 card costs a
fifth of the budget on its own.

**Budget.** Starts at 100. Each gameweek pays `0.05 × (score − 60)`
credits, capped at 3 (`evolution.gain_semaine`): a strong week at 80
points earns 1 credit. Payouts are small on purpose; the main way to grow
is to hold cards that climb.

## Rules fixed in code (proposals)

| Rule | Value | Where |
|------|-------|-------|
| Squad size | 15 (11 + 4 bench) | `evolution.TAILLE_EFFECTIF` |
| Formations | 4-3-3, 4-4-2, 4-2-3-1, 3-5-2, 3-4-3, 5-3-2, 4-5-1 | `scoring.FORMATIONS` |
| Position families | GK 1, DEF 3–5, MID 2–5, FWD 1–3 | `scoring.LIMITES_FAMILLE` |
| Captain | points × 1.5 | `scoring.BONUS_CAPITAINE` |
| Champions League | note × 1.25 | `scoring.MULTIPLICATEUR_COMPETITION` |
| Did not play | 0 points, auto-sub from bench in order | `scoring.remplacements` |
| Note precision | one decimal | `notation.note_sur_10` |

**Note and competition.** The note out of 10 is neutral: the percentile
thresholds were measured on `brut / coef`, so a 7.0 in Ligue 1 and a 7.0 in
the Champions League describe the same quality of performance. The UCL
bonus is applied by the *game* (`scoring.multiplicateur`), not by the
rating. This keeps the card honest and the game tunable independently.

## Deliberately left out of v1

- **Manager selection and manager traits.** Mentioned as a maybe. Adds a
  second economy before the first is balanced. Revisit after one season.
- **Injuries and form as separate mechanics.** The notes already carry
  form; injuries show up as "did not play". Anything more is simulation,
  which `CONTEXTE.md` rules out.
- **Player-to-player trading.** Prices are set by OVR, managers buy from
  and sell to the market. Peer trading needs anti-collusion rules; later.
- **Ownership limits / scarcity.** In v1 every manager can own any card.
  If the backtest shows everyone converging on the same 15, add a
  per-league ownership cap.

## What the backtest must answer

1. Distribution of end-of-season budgets under a naive strategy (buy the
   15 highest-OVR cards you can afford) vs. an informed one (buy last
   season's under-priced risers). If naive wins, the prior or the EMA is
   too timid.
2. Whether any card reaches the price floor or ceiling and stays there.
3. Median team score per gameweek (target ~66 = eleven 6.0s) and its
   spread between top and bottom managers.
4. How often auto-subs trigger and whether bench order matters enough.

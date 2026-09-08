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

### 1. Perimeter — global league: the five leagues + Champions League

Decision (the project owner's, after the backtest): the game league is
**global**, the players of the five big leagues with their league and
Champions League matches, about 2 400 cards. The data model still carries
a `perimetre` per game league (`ligue_jeu.perimetre`, a list of
competition ids), so a Ligue 1-only league remains a configuration row.

The backtest showed why global is the safer first perimeter for this
engine: with the Champions League weighting inside the note, a Ligue
1-only league had a single club (PSG) behind every spring price rise;
across five leagues the rises spread over Arsenal, Bayern, Barcelona,
PSG, Atlético and Nottingham (`BACKTEST.md`).

### 2. Frequency — one gameweek per league round, midweek included

A **gameweek** is a date window (`journee.du` to `journee.au`) that groups
a league round and the European midweek that follows it. Lineups lock at
the first kick-off of the window. A card that plays twice in the window
scores twice.

This matches how the engine already works (`topsflops.py --du --au`) and
how the audience follows football. Slower cadences (fortnightly) lose the
Tuesday-night moments that the engine's competition weighting rewards.

### 3. Valuation — from last season's notes, cautious on thin samples

This is the structuring decision. The proposal:

**The OVR scale is calibrated on the perimeter.** Season means are
compressed (regulars sit between roughly 4.8 and 8.0 across the five
leagues, 4.7 to 7.7 in Ligue 1 alone, because the engine's competition
weighting lives inside the note). So `evolution.calibrer_echelle` maps the
2nd percentile of the seeding season's means to OVR 40 and the 99.5th to
99, per game league. For Ligue 1 2025/26 that is 4.84 → 40, 7.21 → 99.

**Start of season.** A card's rating-note is the minutes-weighted mean of
its notes last season, **shrunk towards a prior of 5.5** with the weight of
ten full matches (`evolution.note_initiale`). A newcomer with no data
starts at the prior, well under the median, price under 1 credit. The
prior sits *below* the median on purpose: the game is meant to reward
knowledge of low-cost players, so the unknowns must be cheap enough that
being right about them pays.

**In season.** After every match the rating-note moves by 8 % of the gap
to the new note, scaled by minutes (`evolution.note_ema`). At 12 % the
backtest showed prices jumping a full band on one match; at 8 % a run of
five good matches is needed to move a card visibly, which is the horizon
a manager can anticipate.

**Price.** `prix = 2 ^ ((OVR − 60) / 8)`, floor 0.5 credits:

| OVR | 52 | 60 | 68 | 76 | 84 | 92 | 99 |
|-----|----|----|----|----|----|----|----|
| credits | 0.5 | 1 | 2 | 4 | 8 | 16 | 29.5 |

Exponential so that the top of the market is scarce. A steeper slope
(doubling every 6) made risers too lucrative in the backtest (an informed
manager's value ×4 in half a season).

**Budget.** Starts at **60** for 15 cards, spread evenly that buys an
OVR-76 squad. The global perimeter's best fifteen cost 104: at 100
credits the naive manager nearly matches the informed one (+8 %), at 60
the informed one is 30 % ahead, so scarcity is what makes knowledge
count. Each gameweek pays `0.05 × (score − 60)`
credits, capped at 3 (`evolution.gain_semaine`). Payouts are small on
purpose; the main way to grow is to hold cards that climb. See
`BACKTEST.md` for the full run.

## Rules fixed in code (proposals)

| Rule | Value | Where |
|------|-------|-------|
| Squad size | 15 (11 + 4 bench) | `evolution.TAILLE_EFFECTIF` |
| Formations | 4-3-3, 4-4-2, 4-2-3-1, 3-5-2, 3-4-3, 5-3-2, 4-5-1 | `scoring.FORMATIONS` |
| Position families | GK 1, DEF 3–5, MID 2–5, FWD 1–3 | `scoring.LIMITES_FAMILLE` |
| Captain | points × 1.5 | `scoring.BONUS_CAPITAINE` |
| Champions League | no game-side bonus | see below |
| Did not play | 0 points, auto-sub from bench in order | `scoring.remplacements` |
| Note precision | one decimal | `notation.note_sur_10` |

**Note and competition.** The engine already weights every action by the
competition, the round and the opponent inside the raw score, so a Champions
League night is worth more *in the note itself*. A first draft added a 1.25
game-side multiplier on top; that counted the premium twice and was removed
(`REPONSES.md` §3). The percentile thresholds are measured on `brut / coef`
so the note stays comparable across competitions; the engine's weighting is
the only one.

**Price scale and the note's range.** The price doubles every 8 points
of **OVR**, not of note, and the OVR scale is calibrated on the
perimeter's real season means (see above), so the spread of prices
follows the spread that actually exists.

**Decided: the Champions League stays inside the note.** The engine's
competition and round coefficients are kept as they are (option a in
`BACKTEST.md`): the Champions League is the summit, and anticipating
European runs is part of the game. The global perimeter is what keeps
that from collapsing onto one club.

## After playing the prototype — the market must change

The owner's reactions to the browser prototype (docs/PROTOTYPE.md), and
what follows from them. These are the decisions for season one; the
backtest and the prototype will be updated to match before phase 3.

**1. The market is too easy.** In the prototype every manager can buy any
card: with 60 credits you own several of the very best from the first
day. The pricing is right (the backtest showed the informed manager
winning), but unlimited supply is the flaw. Decision: **each card has one
owner per game league**. Once Dembélé is signed in a league, nobody else
in that league can sign him until his contract ends or his owner sells.
That alone makes the market a game: the best cards are gone in the first
hour, and knowledge of the second tier is what the season is played on.

**2. Online only.** No solo mode. A game league is a group of managers on
one shared market; the prototype's solo replay stays as a training ground
but is not the product. Consequences: a season start is a **draft**
(managers pick in turn, snake order, until everyone has 15), so nobody
gets everything by clicking first; the shared clock is the gameweek.

**3. Contracts.** A signed card carries a **contract length in gameweeks**
(chosen at signing among a few options, longer costs more per gameweek,
to be tuned). During the contract the card cannot be taken; when it ends
the card returns to the market unless renewed before the last gameweek.

**4. Transfers between managers.** A manager can **make an offer** for a
card another manager owns: credits, or credits plus a card. The owner
accepts or declines before the next lock. The market price stays the
reference; the deal can sit anywhere above it.

**5. Negotiation at contract end.** A card whose contract is ending is
**open to offers from every manager** during the last gameweek; the
current owner has a right of first refusal at the best offer. "The most
convincing wins" is, in v1, the highest bid; a non-monetary pitch
(playing time promised, role) is a season-two idea.

What this changes in the code: `effectif` gains a contract (start, end,
weekly cost) and becomes unique per (game league, player); a `offre`
table for transfer offers and end-of-contract bids; the draft as a
sequence of picks stored per game league; and the backtest needs several
managers competing for the same cards to re-tune prices under scarcity.
Phase 2 (the weekly pipeline) is unaffected by any of this: it scores
whatever compositions exist.

## Deliberately left out of v1

- **Manager selection and manager traits.** Mentioned as a maybe. Adds a
  second economy before the first is balanced. Revisit after one season.
- **Injuries and form as separate mechanics.** The notes already carry
  form; injuries show up as "did not play". Anything more is simulation,
  which `CONTEXTE.md` rules out.
- **Free-text negotiation.** Offers are numbers in v1 (see above);
  pitches and promises come after a season of watching real offers.
- **Anti-collusion on transfers.** Two friends trading a star for 0.5
  credits is possible in v1; a floor at the market price is the obvious
  first rule if it happens.

## What the backtest must answer

Answered in `BACKTEST.md` for both perimeters; kept here as the
checklist for the next run (with a real previous season as the seed).

1. Distribution of end-of-season budgets under a naive strategy (buy the
   15 highest-OVR cards you can afford) vs. an informed one (buy last
   season's under-priced risers). If naive wins, the prior or the EMA is
   too timid.
2. Whether any card reaches the price floor or ceiling and stays there.
3. Median team score per gameweek (target ~66 = eleven 6.0s) and its
   spread between top and bottom managers.
4. How often auto-subs trigger and whether bench order matters enough.

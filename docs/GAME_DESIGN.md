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
and pays out a few million euros. Meanwhile every card's rating (OVR) moves with its
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
starts at the prior, well under the median. The
prior sits *below* the median on purpose: the game is meant to reward
knowledge of low-cost players, so the unknowns must be cheap enough that
being right about them pays.

**In season.** The rating-note is a running mean that folds every new
match in (`evolution.note_maj`): the season-start note keeps an inertia
of half of last season's full-match equivalents plus the prior's ten, so a
new match weighs about 1/25 at the start of the season and 1/45 at the
end. One night never remakes a card. On top of that the displayed OVR is
**bounded to ±10 around the season start** (`evolution.ovr_borne`): a
star's bad month cannot cost twenty points, a rookie's hot streak earns
at most ten, and a card's price moves at most ×2.4 or ÷2.4 in a season.

Why so calm: the replay showed that an evolving OVR predicts the next
eight gameweeks no better than a fixed one (rank correlation 0.26 against
0.24), and that manager points are identical whatever the mechanism. Card
evolution is not information, it is the economy. The earlier exponential
moving average (8 % of the gap per match) sent Dembélé from 64 to 95 and
98 M€ to 1 435 M€ in half a season, and cost Andrich 21 points: that was
the volatility of a form indicator, not of a card. Form is shown on the
card (the last notes) and left out of the price on purpose: buying a
player in form before his OVR, hence his price, catches up is the edge.

**Price — in euros, from the real market value.** Every amount in the
game is money: a card's price starts the season at the player's **real
market value** (FotMob prints Transfermarkt's figure on every match sheet;
`importer.lire_valeurs` reads it, `valeur_marche` keeps the history) and
then follows its OVR:

    prix = valeur_base × 2 ^ ((OVR − OVR_base) / 8) × (1 + demande)

+8 OVR since the season start doubles the price, −8 halves it, floor
100 k€. Haaland starts at 152 M€ and stays there unless he plays better
or worse than last season; a 54-OVR full-back at 400 k€ who strings five
good matches together doubles. Age, contract and hype are in the market
value, form is in the OVR, popularity is in `demande` (the share of teams
owning the card, see "how the market gets scarce"). The 3 % of cards
FotMob gives no value for are priced from a log-linear fit of value on OVR
over the seeded population (`evolution.ajuster_valeur`).

Two consequences that are the point of the game: a 34-year-old Van Dijk
at OVR 87 costs 10 M€ (his market value) — a bargain for one season that
demand then pushes up; a 19-year-old at 130 M€ with OVR 65 is a bad buy
for points. The market value is what the world thinks the player is worth
to a club; the OVR is what he does on the pitch this season. The gap is
where knowledge pays.

**Budget.** Starts at **100 M€** for 15 cards. The median card costs
6 M€, the 90th percentile 50 M€: one star or two, the rest to find cheap.
The backtest (`BACKTEST.md`) puts the informed manager 20 % ahead of the
naive one and the naive one 80 % ahead of random, at any budget from 60 to
250 M€ — the ordering does not depend on the figure, 100 is a round club
budget. Each gameweek pays `0.1 M€ × (score − 60)`, capped at 5 M€
(`evolution.gain_semaine`). Payouts are small on purpose; the main way to
grow is to hold cards that climb.

## The market — packs, copies, auction house

The card of a player (OVR, attributes, cote) is a model; what a manager
owns is a **copy** of it, and copies only come out of **packs**
(`jeu/marche.py`). Every copy shares the model's evolution, so the point
of the game is unchanged — find the player before his OVR climbs — but the
price at which copies change hands is set by the managers on the
**auction house**. The cote (market value × OVR move) stays an indicative
value.

- Packs, sold by the bank at a fixed price: Bronze 6 M€ (three cards under
  60), Argent 25 M€ (three cards 60–74), Or 50 M€ (one card 75+, two
  60–74); a pack of one family costs 20 % more. Contents are drawn
  uniformly among the players of the tier whose copies in circulation are
  under the cap: **max(3, 25 % of the teams)** copies of a player. A star
  is rare, and gets rarer as the ladder fills.
- The club: 15 cards at most in the squad (2 GK / 5 DEF / 5 MID / 3 FWD,
  one copy of a player), 30 in the reserve, held as investments.
- The auction house: a start price, an optional buy-now price, 6 to 48
  hours; bids lock the money, +5 % at least; the seller receives the price
  minus 5 %. A listed card leaves the squad.
- The bank buys back at 40 % of the cote and destroys the copy: opening
  packs to resell them to the bank loses money, which keeps the supply
  honest.

The first store (buy at the cote, demand multiplier) is gone; its backtest
stays in `BACKTEST.md` as the calibration of the cote.

## The match — head-to-head, resolved from real actions

Every gameweek pairs each team with an opponent of its level (Swiss
pairing on Elo, rematches avoided), and the two elevens play a virtual
match whose sheet is made of the **real actions** of their players over
the gameweek (`jeu/match.py`). Nothing is random: the same gameweek
always gives the same match.

1. Every real goal of one of your starters is a chance, carried by its
   scorer with the note he got that match. The shots on target your
   players did not convert add one more chance per three of them, carried
   by your best shooters, a notch weaker than a goal.
2. The opposing back line cancels chances with its defensive work of the
   gameweek, measured in the engine's own points (DEF lines of the
   outfield players, ARR/EVI/SOR lines of the keeper): one cancellation
   per 70 points. Cancellations hit the weakest chances first; the
   captain's goals cannot be cancelled.
3. What is left is the score. Win 3, draw 1, Elo K = 32.

The sheet shows possession (real completed passes), shots, xG, big
chances, passes into the final third, tackles, interceptions, saves,
goals prevented, and who scored, who missed, who cancelled what. The
calibration, on 340 simulated matches of 2025/26, is in `BACKTEST.md`.

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

## After playing the prototype — how the market gets scarce

The owner's reactions to the browser prototype (docs/PROTOTYPE.md): the
best cards are too easy to get, the game must be online, and ideas such
as one owner per card, contracts, buying a card from another manager and
bidding at contract end. Then a second thought that settles it: **the game
is global**, and one owner per card caps a global game at about 150
managers (2 371 cards, 15 each). So exclusivity is out as the core
mechanic, and the question becomes: what makes stars scarce when everyone
can own everyone? Three mechanisms were added to the backtest and
measured (`BACKTEST.md`, "Trois façons de créer de la rareté").

**Decision: prices follow demand.** A card's price is its OVR price
multiplied by `1 + k × (share of managers owning it)`. The crowd's
favourites get expensive; a producer nobody has noticed stays cheap.
Backtested at k = 1 on a crowd of 200: the informed manager still beats
the naive one (1 772 vs 1 331) and the oracle stays ahead; the naive
manager can no longer afford the top fifteen. This scales to any number
of managers and keeps one world market and one world ranking. `k` is
the knob; 1.0 is the starting value, to be re-read on the first real
crowd. Prices are recomputed once per gameweek with the OVR, so a card
is bought and sold at the same public price by everyone.

**Rejected: wages.** A weekly charge proportional to squad value does
not change who scores what; it only drains the manager who trades.

**Kept as an optional format, later: private draft leagues.** A group of
friends can play a league of ten with a snake draft and one owner per
card *inside that league* only; leagues are independent, so this scales
too. The backtest shows it flattens the informed manager's edge (draft
order and free-agent scarcity dominate), which is fine for a friends'
format and wrong for the main game. Contracts, offers between managers
and end-of-contract bids only make sense with exclusivity, so they live
in this format if it is built, not in the global game.

**Online only, still.** No solo mode in the product; the prototype's
solo replay stays a training ground. Private leagues on the global
market (a shared ranking among friends, no exclusivity) are the social
layer of season one.

What this changes in the code: `carte.prix` becomes `prix_ovr × (1 + k ×
part)`, with `part` computed by the weekly pipeline from `effectif`
across all teams; a `parametre` `demande` per season; the backtest's
`--demande` is the reference implementation. Nothing else in phase 2
moves.

## Deliberately left out of v1

- **Manager selection and manager traits.** Mentioned as a maybe. Adds a
  second economy before the first is balanced. Revisit after one season.
- **Injuries and form as separate mechanics.** The notes already carry
  form; injuries show up as "did not play". Anything more is simulation,
  which `CONTEXTE.md` rules out.
- **Player-to-player trading, contracts, negotiation.** They need
  exclusivity; see the private draft league format above.

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

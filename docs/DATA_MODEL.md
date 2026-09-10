# Data model

Two databases, one direction of flow.

```
fotmob.db (engine source, read-only)          game database (jeu/schema.sql)
  match, appearance, player, stat   --topsflops.calculer()-->   prestation
                                    --notation.py------------>  note, attributs
                                    --evolution.py----------->  carte, carte_historique
                                                                 equipe, composition, resultat
```

The engine's base is never written by the game, and the game never
recomputes stats. The bridge is `topsflops.calculer(conn, du, au, ...)`,
which returns one dict per `(match_id, player_id)` with `brut`, `coef`,
`points`, `minutes`, `poste`, `lignes`. `jeu/notation.py` turns that into
a note and six attributes (family table: `moteur/familles_lignes.json`);
both are frozen into `prestation` so a later recalibration of the engine
never rewrites history.

## Keys

All football entities use **FotMob ids** as primary keys: `player_id`,
`team_id`, `match_id`, and the primary `league_id` for competitions. This
is the single most important choice in the model: every trap in
`CONTEXTE.md` section 5 (homonyms, accents, label variants) comes from
matching on names. The game never does. `joueur.nom_normalise` exists for
search boxes only.

## Tables

### Football (mirrors of the engine, plus derived values)

| table | one row per | notes |
|-------|-------------|-------|
| `competition` | competition × season | |
| `club` | club | kit colour for the card, from the cached match sheets (`importer_couleurs`) |
| `joueur` | player | majority position for the season, latest market value (M€) |
| `valeur_marche` | player × sheet date | market value printed on the FotMob match sheet (Transfermarkt's figure), M€; the seed reads the value known at its date |
| `journee` | gameweek | date window + lock time; gameweek 0 holds the seed state |
| `parametre` | season × key | OVR scale and economy constants frozen at seed time |
| `match` | match | assigned to a gameweek |
| `prestation` | rated appearance | engine output + note + attributes + raw actions (`stats`, for the match sheet), frozen |

### Cards

| table | one row per | notes |
|-------|-------------|-------|
| `carte` | player × season | current `note_ovr` (the terrain score S of the season barème), `ovr`, `prix` (M€), `attributs`; `valeur_base`/`ovr_base` anchor the price at the seed; `bareme` keeps the seed record (last season's window, its scores, the palmarès), `sommes` the season-to-date window |
| `carte_historique` | player × gameweek | price chart, "card evolves" screen |
| `bareme_journee` | player × gameweek | the season barème of the gameweek's window (minutes, points, starts, sheets, points per axis), written by the importer or the exporter document; the pipeline adds them into `carte.sommes`, a replay seeds from them |
| `parametre` | season × key | `bareme` (priors, dispersions, the OVR and attribute scales measured on the seed), `economie`, `valeur_marche` |

### Managers

| table | one row per | notes |
|-------|-------------|-------|
| `exemplaire` | copy of a card | owner, squad or reserve, serial number, price paid; destroyed by a bank sale |
| `enchere` | listing | start, buy-now, end, best bid (money locked), status |
| `pack_ouvert` | pack opening | type, price, contents |
| `match_h2h` | fixture | one per team per gameweek, Elo before/after, the JSON match sheet |

| table | one row per | notes |
|-------|-------------|-------|
| `utilisateur` | account | |
| `ligue_jeu` | game league | perimeter, budget, squad size |
| `equipe` | manager × game league | free budget, season points |
| `effectif` | owned card | price paid, for the scouting reward |
| `transfert` | buy or sell | full ledger |
| `composition` | lineup × gameweek | immutable after lock |
| `resultat` | scored lineup × gameweek | frozen output of `score_equipe` |

`jeu/importer.py` is the offline version of the import step, run over a
whole season; `jeu/backtest.py` reads the result. `jeu/pipeline.py` is
the live path below.

## The weekly write path (`jeu/pipeline.py calculer`)

```
1. import       topsflops.calculer(du, au) -> prestation (+ match, joueur, club upserts)
2. evolve       carte_historique of gameweek N-1 + bareme_journee of N -> bareme.etat_courant
                (terrain score, OVR bounded around ovr_base, six attributes)
                -> carte_historique of gameweek N, copied into carte
3. score        for each composition submitted before journee.cloture:
                scoring.score_equipe -> resultat (rank included)
4. pay          resultat.gain -> equipe.budget, score -> equipe.points_total
5. close        journee.calculee = 1
```

Steps 2–5 are one transaction and idempotent: the card state is always
derived from the previous gameweek's history, and a resultat that
already exists has its previous payout taken back before being replaced.
A composition submitted after the lock is recorded with a zero score and
the reason. Recomputing an earlier gameweek makes the later ones stale:
run them again in order.

## What is JSON on purpose

`prestation.lignes`, `prestation.attributs`, `composition.titulaires`,
`composition.banc`, `resultat.detail`, `ligue_jeu.perimetre`. These are
read whole and never queried by field. If a query ever needs "every
performance with a red card", add a column then, not now.

## SQLite → Postgres

The schema uses only types both understand (`INTEGER`, `REAL`, `TEXT`).
`AUTOINCREMENT` becomes `GENERATED ALWAYS AS IDENTITY`; `PRAGMA
foreign_keys` disappears. Nothing else changes.

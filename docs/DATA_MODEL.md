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
| `club` | club | kit colour for the card |
| `joueur` | player | majority position for the season |
| `journee` | gameweek | date window + lock time |
| `match` | match | assigned to a gameweek |
| `prestation` | rated appearance | engine output + note + attributes, frozen |

### Cards

| table | one row per | notes |
|-------|-------------|-------|
| `carte` | player × season | current `note_ovr`, `ovr`, `prix` |
| `carte_historique` | player × gameweek | price chart, "card evolves" screen |

### Managers

| table | one row per | notes |
|-------|-------------|-------|
| `utilisateur` | account | |
| `ligue_jeu` | game league | perimeter, budget, squad size |
| `equipe` | manager × game league | free budget, season points |
| `effectif` | owned card | price paid, for the scouting reward |
| `transfert` | buy or sell | full ledger |
| `composition` | lineup × gameweek | immutable after lock |
| `resultat` | scored lineup × gameweek | frozen output of `score_equipe` |

## The weekly write path

```
1. cloture      composition rows become immutable (journee.cloture passed)
2. import       topsflops.calculer(du, au) -> prestation (+ match, joueur, club upserts)
3. score        for each composition: scoring.score_equipe -> resultat
4. evolve       for each card that played: evolution.note_ema -> carte, carte_historique
5. pay          resultat.gain -> equipe.budget ; journee.calculee = 1
```

Steps 2–5 are one transaction per gameweek and idempotent: re-running
replaces the same rows with the same values.

## What is JSON on purpose

`prestation.lignes`, `prestation.attributs`, `composition.titulaires`,
`composition.banc`, `resultat.detail`, `ligue_jeu.perimetre`. These are
read whole and never queried by field. If a query ever needs "every
performance with a red card", add a column then, not now.

## SQLite → Postgres

The schema uses only types both understand (`INTEGER`, `REAL`, `TEXT`).
`AUTOINCREMENT` becomes `GENERATED ALWAYS AS IDENTITY`; `PRAGMA
foreign_keys` disappears. Nothing else changes.

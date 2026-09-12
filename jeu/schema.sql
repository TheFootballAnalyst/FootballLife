-- schema.sql — the GAME database (SQLite first, Postgres-compatible types).
--
-- Deliberately separate from fotmob.db, which stays the engine's read-only
-- source.  The game only stores what the engine derives (one row per rated
-- performance) plus everything about managers.  Player, club and match ids
-- are the FotMob ids, so the two bases join without any name matching —
-- the homonym/accent traps of docs/CONTEXTE.md section 5 never apply here.

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------- football
CREATE TABLE IF NOT EXISTS competition (
    competition_id   INTEGER PRIMARY KEY,           -- FotMob primary league id
    nom              TEXT NOT NULL,                 -- "Ligue 1", "Champions League"
    saison           TEXT NOT NULL                  -- "2026/27"
);

CREATE TABLE IF NOT EXISTS club (
    team_id          INTEGER PRIMARY KEY,           -- FotMob team id
    nom              TEXT NOT NULL,
    couleur          TEXT NOT NULL DEFAULT '#14161E', -- kit colour for the card
    competition_id   INTEGER REFERENCES competition(competition_id)
);

CREATE TABLE IF NOT EXISTS joueur (
    player_id        INTEGER PRIMARY KEY,           -- FotMob player id
    nom              TEXT NOT NULL,
    nom_normalise    TEXT NOT NULL,                 -- accents stripped, lower
    team_id          INTEGER REFERENCES club(team_id),
    poste            TEXT NOT NULL,                 -- main position: the first of `postes`
    postes           TEXT,                          -- JSON, every position really held (importer.postes_joues)
    valeur_marche    REAL,                          -- M€, latest known (FotMob match sheets)
    age              INTEGER,                       -- from the latest match sheet
    numero           TEXT,                          -- shirt number
    pays             TEXT,                          -- ISO-3 country code
    pied             TEXT                           -- 'gauche' | 'droit' | 'deux'; NULL = inconnu (donnees/pieds.py)
);
CREATE INDEX IF NOT EXISTS ix_joueur_nom ON joueur(nom_normalise);

-- Market value history: FotMob prints a Transfermarkt-style value for every
-- player on every match sheet; one row per player per sheet date, in M€.
-- The seed reads the value known at the seed date (no look-ahead).
CREATE TABLE IF NOT EXISTS valeur_marche (
    player_id        INTEGER NOT NULL REFERENCES joueur(player_id),
    date             TEXT NOT NULL,                 -- ISO date of the match
    valeur           REAL NOT NULL,                 -- M€
    PRIMARY KEY (player_id, date)
);

-- A gameweek is the game's unit of time: a date window that groups a league
-- round and the European midweek that follows.  Lineups lock at `cloture`.
CREATE TABLE IF NOT EXISTS journee (
    journee_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    saison           TEXT NOT NULL,
    numero           INTEGER NOT NULL,
    du               TEXT NOT NULL,                 -- ISO date, inclusive
    au               TEXT NOT NULL,                 -- ISO date, inclusive
    cloture          TEXT NOT NULL,                 -- ISO datetime, first kick-off
    calculee         INTEGER NOT NULL DEFAULT 0,    -- 1 once scores are final
    UNIQUE (saison, numero)
);

CREATE TABLE IF NOT EXISTS match (
    match_id         INTEGER PRIMARY KEY,           -- FotMob match id
    journee_id       INTEGER REFERENCES journee(journee_id),
    competition_id   INTEGER REFERENCES competition(competition_id),
    date_utc         TEXT NOT NULL,
    phase            TEXT,                          -- engine classer_phase()
    home_team_id     INTEGER REFERENCES club(team_id),
    away_team_id     INTEGER REFERENCES club(team_id),
    home_score       INTEGER,
    away_score       INTEGER
);
CREATE INDEX IF NOT EXISTS ix_match_journee ON match(journee_id);

-- One rated appearance = what topsflops.calculer() returns, plus the two
-- derived values (note, attributes) frozen at computation time.  Keeping
-- them frozen means a later recalibration never rewrites history.
CREATE TABLE IF NOT EXISTS prestation (
    match_id         INTEGER NOT NULL REFERENCES match(match_id),
    player_id        INTEGER NOT NULL REFERENCES joueur(player_id),
    team_id          INTEGER REFERENCES club(team_id),
    poste            TEXT NOT NULL,                 -- position held THAT match
    minutes          REAL NOT NULL,
    entrant          INTEGER NOT NULL DEFAULT 0,
    brut             REAL NOT NULL,                 -- engine raw (with coef)
    coef             REAL NOT NULL,                 -- competition x round (x opponent)
    points           REAL NOT NULL,                 -- engine points (brut x coef_poste)
    note             REAL,                          -- notation.note_sur_10
    statut           TEXT,                          -- ok / sous_mediane / flop / flop_severe
    lignes           TEXT NOT NULL,                 -- JSON {label: points}
    attributs        TEXT,                          -- JSON {FIN: 71, ...}
    stats            TEXT,                          -- JSON raw actions of the match (importer.STATS)
    PRIMARY KEY (match_id, player_id)
);
CREATE INDEX IF NOT EXISTS ix_prestation_joueur ON prestation(player_id);

-- Per-season parameters frozen at seed time (OVR scale, economy constants),
-- so a later change of a constant never silently rewrites a running season.
CREATE TABLE IF NOT EXISTS parametre (
    saison           TEXT NOT NULL,
    cle              TEXT NOT NULL,
    valeur           TEXT NOT NULL,                 -- JSON
    PRIMARY KEY (saison, cle)
);

-- ------------------------------------------------------------------ cards
-- The card is the player's game-side state.  One row per player per season;
-- `note_ovr` is the card's terrain score S (the season barème per 90,
-- jeu/bareme.py: last season weighed POIDS_SAISON_PASSEE plus this season),
-- `ovr` derives from its move since the seed (bounded around `ovr_base`)
-- and `prix` (M€) from the OVR move: valeur_base x 2^((ovr-ovr_base)/8),
-- times the demand multiplier.  `bareme` keeps the seed record (last
-- season's window, its scores, the palmarès), `sommes` the season-to-date
-- window (minutes, barème points, starts, sheets, points per axis).
CREATE TABLE IF NOT EXISTS carte (
    player_id        INTEGER NOT NULL REFERENCES joueur(player_id),
    saison           TEXT NOT NULL,
    note_ovr         REAL NOT NULL,
    ovr              INTEGER NOT NULL,
    prix             REAL NOT NULL,                 -- M€, with the demand multiplier
    valeur_base      REAL NOT NULL DEFAULT 1,       -- M€ at the seed (market value)
    ovr_base         INTEGER NOT NULL DEFAULT 60,   -- OVR at the seed
    poids            REAL NOT NULL DEFAULT 0,       -- weight of the sample in the shrink (0..1)
    part             REAL NOT NULL DEFAULT 0,       -- share of managers owning the card
    sommes           TEXT,                          -- JSON window of this season (bareme.fenetre)
    min90            REAL NOT NULL DEFAULT 0,       -- full-match equivalents behind `sommes`
    attributs        TEXT,                          -- JSON, bareme.attributs on last season + this one
    bareme           TEXT,                          -- JSON, bareme.carte_initiale (the seed record)
    arrivee          INTEGER NOT NULL DEFAULT 0,    -- gameweek the card entered (0 = the seed; >0 = mercato)
    matchs           INTEGER NOT NULL DEFAULT 0,
    minutes          REAL NOT NULL DEFAULT 0,
    maj              TEXT NOT NULL,                 -- ISO datetime of last update
    PRIMARY KEY (player_id, saison)
);

-- The season barème of one gameweek, per player: what the engine's
-- per-date trace gives over the gameweek's window (jeu/bareme.py), written
-- by the importer / the exporter document.  The pipeline adds these up
-- into carte.sommes; the seed of a replay adds up a source season's rows.
CREATE TABLE IF NOT EXISTS bareme_journee (
    journee_id       INTEGER NOT NULL REFERENCES journee(journee_id),
    player_id        INTEGER NOT NULL,
    minutes          REAL NOT NULL DEFAULT 0,
    points           REAL NOT NULL DEFAULT 0,       -- barème points of the window (no position coefficient)
    tit              INTEGER NOT NULL DEFAULT 0,    -- starts
    dispo            INTEGER NOT NULL DEFAULT 0,    -- match sheets (bench included)
    axes             TEXT,                          -- JSON {axe: points}
    PRIMARY KEY (journee_id, player_id)
);

-- Full history of a card's value: this is what the "card evolves" screen
-- and the price charts read.
CREATE TABLE IF NOT EXISTS carte_historique (
    player_id        INTEGER NOT NULL REFERENCES joueur(player_id),
    journee_id       INTEGER NOT NULL REFERENCES journee(journee_id),
    note_ovr         REAL NOT NULL,
    ovr              INTEGER NOT NULL,
    prix             REAL NOT NULL,                 -- M€, with the demand multiplier
    part             REAL NOT NULL DEFAULT 0,
    poids            REAL NOT NULL DEFAULT 0,
    sommes           TEXT,
    min90            REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (player_id, journee_id)
);

-- --------------------------------------------------------------- managers
CREATE TABLE IF NOT EXISTS utilisateur (
    utilisateur_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    pseudo           TEXT NOT NULL UNIQUE,
    email            TEXT UNIQUE,
    cree_le          TEXT NOT NULL,
    mdp_hash         TEXT,                          -- PBKDF2, see web/app/serveur.py
    mdp_sel          TEXT,
    est_admin        INTEGER NOT NULL DEFAULT 0
);

-- Private leagues: a ranking among friends on the global market (no
-- exclusivity, same cards, same prices).  A team can be in many.
CREATE TABLE IF NOT EXISTS ligue_privee (
    ligue_privee_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    nom              TEXT NOT NULL,
    code             TEXT NOT NULL UNIQUE,          -- invitation code
    saison           TEXT NOT NULL,
    cree_par         INTEGER REFERENCES equipe(equipe_id),
    cree_le          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ligue_privee_membre (
    ligue_privee_id  INTEGER NOT NULL REFERENCES ligue_privee(ligue_privee_id),
    equipe_id        INTEGER NOT NULL REFERENCES equipe(equipe_id),
    rejoint_le       TEXT NOT NULL,
    PRIMARY KEY (ligue_privee_id, equipe_id)
);

-- A "league" in the game sense: a group of managers competing over one
-- season on one football perimeter (Ligue 1 only, or top 5 + UCL).
CREATE TABLE IF NOT EXISTS ligue_jeu (
    ligue_jeu_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    nom              TEXT NOT NULL,
    saison           TEXT NOT NULL,
    perimetre        TEXT NOT NULL,                 -- JSON list of competition ids
    budget_initial   REAL NOT NULL DEFAULT 100.0,
    taille_effectif  INTEGER NOT NULL DEFAULT 15,
    cree_le          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS equipe (
    equipe_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    utilisateur_id   INTEGER NOT NULL REFERENCES utilisateur(utilisateur_id),
    ligue_jeu_id     INTEGER NOT NULL REFERENCES ligue_jeu(ligue_jeu_id),
    nom              TEXT NOT NULL,
    budget           REAL NOT NULL,                 -- M€ not tied up in cards
    points_total     REAL NOT NULL DEFAULT 0,
    elo_classe       REAL NOT NULL DEFAULT 1000,   -- the ranked lobby's ladder, the game's only one
    classees         INTEGER NOT NULL DEFAULT 0,    -- ranked matches played in the lobby
    packs_offerts    TEXT,                          -- JSON {type: nombre}, gagnés en campagne solo
    UNIQUE (utilisateur_id, ligue_jeu_id)
);

-- Solo campaign: you take a real club's place in a real competition and
-- play its calendar against the other clubs' elevens, built from the game's
-- cards (jeu/solo.py).  The whole campaign is in this row: the field, the
-- calendar and every result, so nothing is redrawn on a refresh.
CREATE TABLE IF NOT EXISTS campagne (
    campagne_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    saison           TEXT NOT NULL,
    equipe_id        INTEGER NOT NULL REFERENCES equipe(equipe_id),
    cle              TEXT NOT NULL,                 -- solo.COMPETITIONS key
    club_remplace    INTEGER NOT NULL,              -- team_id whose place you took
    place            INTEGER NOT NULL,              -- your index in `clubs` (seeding)
    graine           INTEGER NOT NULL,              -- every match of the campaign derives from it
    clubs            TEXT NOT NULL,                 -- JSON [team_id], seeding order, frozen at the start
    calendrier       TEXT NOT NULL,                 -- JSON [[ [place, place], ... ], ...] per round
    resultats        TEXT NOT NULL DEFAULT '[]',    -- JSON, one entry per fixture played
    tour             INTEGER NOT NULL DEFAULT 0,    -- rounds played
    statut           TEXT NOT NULL DEFAULT 'en_cours',
    recompenses      TEXT,                          -- JSON, written once at the close
    cree_le          TEXT NOT NULL,
    fini_le          TEXT
);
CREATE INDEX IF NOT EXISTS ix_campagne_equipe ON campagne(equipe_id, saison, statut);

CREATE TABLE IF NOT EXISTS rencontre (
    rencontre_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    saison           TEXT NOT NULL,
    equipe_a         INTEGER NOT NULL REFERENCES equipe(equipe_id),
    equipe_b         INTEGER REFERENCES equipe(equipe_id),   -- NULL: waiting for an opponent
    defi             INTEGER NOT NULL DEFAULT 0,    -- 1 = against a generated eleven, unranked
    onze_a           TEXT NOT NULL,                 -- JSON [player_id x 11], slot order
    onze_b           TEXT,
    banc_a           TEXT,                          -- JSON [player_id], order of entry
    banc_b           TEXT,
    formation_a      TEXT,                          -- the shape each side lined up in
    formation_b      TEXT,
    tactique_a       TEXT NOT NULL,                 -- JSON {tempo, bloc, risque} at kick-off
    tactique_b       TEXT,
    ajustements      TEXT NOT NULL DEFAULT '{}',    -- JSON {minute: [tactique A | null, tactique B | null]}
    remplacements    TEXT NOT NULL DEFAULT '{}',    -- JSON {minute: [[[out, in], ...] A, [...] B]}
    graine           INTEGER NOT NULL,
    debut            TEXT,                          -- ISO kick-off; NULL while waiting
    elo_a_avant      REAL, elo_b_avant REAL, elo_a_apres REAL, elo_b_apres REAL,
    score_a          INTEGER, score_b INTEGER,
    resultat         TEXT,                          -- 'A' | 'B' | 'N', NULL while running
    feuille          TEXT,                          -- JSON of the final sheet
    campagne_id      INTEGER REFERENCES campagne(campagne_id),  -- NULL: a lobby match
    tour             INTEGER,                       -- ... else the campaign round it plays
    nom_adverse      TEXT,                          -- the club you face in a campaign
    domicile         INTEGER,                       -- 1 if you are at home in that fixture
    pause            TEXT,                          -- ISO instant the clock was stopped, NULL while running
    pause_cumul      INTEGER NOT NULL DEFAULT 0,    -- seconds already spent paused
    arrets_vus       TEXT,                          -- JSON [player_id] the referee already stopped play for
    cree_le          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_rencontre_attente ON rencontre(saison, equipe_b, debut);
CREATE INDEX IF NOT EXISTS ix_rencontre_a ON rencontre(equipe_a, cree_le);
CREATE INDEX IF NOT EXISTS ix_rencontre_b ON rencontre(equipe_b, cree_le);

CREATE TABLE IF NOT EXISTS exemplaire (
    exemplaire_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id        INTEGER NOT NULL REFERENCES joueur(player_id),
    saison           TEXT NOT NULL,
    numero           INTEGER NOT NULL,              -- serial number of the copy for this player
    equipe_id        INTEGER REFERENCES equipe(equipe_id),
    dans_effectif    INTEGER NOT NULL DEFAULT 0,
    origine          TEXT NOT NULL,                 -- 'pack' | 'marche'
    prix_achat       REAL NOT NULL,                 -- M€ paid by the current owner
    achete_le        TEXT NOT NULL,
    detruit          INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_exemplaire_equipe ON exemplaire(equipe_id);
CREATE INDEX IF NOT EXISTS ix_exemplaire_joueur ON exemplaire(player_id, saison);

-- The auction house: one listing per copy at a time.
CREATE TABLE IF NOT EXISTS enchere (
    enchere_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    exemplaire_id    INTEGER NOT NULL REFERENCES exemplaire(exemplaire_id),
    vendeur_id       INTEGER NOT NULL REFERENCES equipe(equipe_id),
    prix_depart      REAL NOT NULL,
    prix_immediat    REAL,
    fin              TEXT NOT NULL,                 -- ISO datetime
    meilleur_offrant INTEGER REFERENCES equipe(equipe_id),
    meilleure_offre  REAL,
    statut           TEXT NOT NULL DEFAULT 'ouverte', -- ouverte | vendue | expiree | annulee
    cree_le          TEXT NOT NULL,
    conclue_le       TEXT
);
CREATE INDEX IF NOT EXISTS ix_enchere_statut ON enchere(statut, fin);

CREATE TABLE IF NOT EXISTS pack_ouvert (
    pack_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    equipe_id        INTEGER NOT NULL REFERENCES equipe(equipe_id),
    type             TEXT NOT NULL,
    fam              TEXT,
    prix             REAL NOT NULL,
    contenu          TEXT NOT NULL,                 -- JSON list of player ids
    date             TEXT NOT NULL
);

-- Legacy of the first store (buy at the public price); kept for old bases.
CREATE TABLE IF NOT EXISTS effectif (
    equipe_id        INTEGER NOT NULL REFERENCES equipe(equipe_id),
    player_id        INTEGER NOT NULL REFERENCES joueur(player_id),
    prix_achat       REAL NOT NULL,
    achete_le        TEXT NOT NULL,
    PRIMARY KEY (equipe_id, player_id)
);

CREATE TABLE IF NOT EXISTS transfert (
    transfert_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    equipe_id        INTEGER NOT NULL REFERENCES equipe(equipe_id),
    player_id        INTEGER NOT NULL REFERENCES joueur(player_id),
    sens             TEXT NOT NULL CHECK (sens IN ('achat', 'vente')),
    prix             REAL NOT NULL,
    journee_id       INTEGER REFERENCES journee(journee_id),
    date             TEXT NOT NULL
);

-- The lineup submitted for a gameweek.  Immutable after `journee.cloture`.
CREATE TABLE IF NOT EXISTS composition (
    equipe_id        INTEGER NOT NULL REFERENCES equipe(equipe_id),
    journee_id       INTEGER NOT NULL REFERENCES journee(journee_id),
    formation        TEXT NOT NULL,
    titulaires       TEXT NOT NULL,                 -- JSON list of 11 player ids
    banc             TEXT NOT NULL,                 -- JSON ordered list
    capitaine        INTEGER REFERENCES joueur(player_id),
    soumise_le       TEXT NOT NULL,
    PRIMARY KEY (equipe_id, journee_id)
);

-- Result of scoring.score_equipe() for that lineup, frozen.
CREATE TABLE IF NOT EXISTS resultat (
    equipe_id        INTEGER NOT NULL REFERENCES equipe(equipe_id),
    journee_id       INTEGER NOT NULL REFERENCES journee(journee_id),
    score            REAL NOT NULL,
    onze             TEXT NOT NULL,                 -- JSON, after auto-subs
    detail           TEXT NOT NULL,                 -- JSON {player_id: points}
    gain             REAL NOT NULL,                 -- M€ earned (evolution.gain_semaine)
    rang             INTEGER,                       -- rank in the game league that week
    PRIMARY KEY (equipe_id, journee_id)
);

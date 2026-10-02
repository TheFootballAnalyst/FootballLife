# Le monde fictif et les mods

Le jeu existe en deux mondes (PLAN.md § 4, ECONOMIE.md § 5) :

- **réel** : les vrais noms de joueurs, de clubs et de compétitions, les
  portraits et les logos rechargés sur ta machine. C'est le jeu local, tant
  qu'on ne vend rien.
- **fictif** : chaque carte garde tout ce qui vient du réel (son barème, son
  poste, son âge, son pied, sa nationalité, son physique) et reçoit un nom
  généré, déterministe, tiré de listes par nationalité ; les clubs prennent
  le nom de leur ville (« Lyon », et l'année de fondation quand la ville en
  a deux : « Manchester 1878 », « Manchester 1880 ») ; les compétitions, le
  pays (« Championnat d'Angleterre », traduit par l'écran). Les portraits
  sont des avatars dessinés par le jeu, les écussons des blasons. C'est le
  monde de la version en ligne.

## Choisir le monde

```
py web/app/lancer.py --fictif      # bascule la base dans le monde fictif, puis lance le site
py web/app/lancer.py --reel        # revient aux vrais noms
py jeu/fictif.py --etat --jeu jeu/demo.sqlite
```

Le monde est écrit dans la base (`parametre.monde`). Les vrais noms sont
gardés dans `nom_reel` : la bascule est réversible, et une carte garde son
nom fictif d'une base à l'autre (même identifiant, même nom), sauf dans le
cas rare où l'autre base a un vrai joueur de ce nom-là : un nom fictif
n'est jamais un vrai nom de la base, et deux cartes n'ont jamais le même.

## Les mods

Un dossier `mods/` à la racine du jeu, chez le joueur. Le jeu le lit en
mode fictif, s'il existe, et n'en fournit aucun fichier : la communauté
fait les siens, comme pour les *option files* de PES.

| Fichier | Contenu |
| --- | --- |
| `mods/noms.csv` | `player_id,nom` — le nom affiché d'une carte |
| `mods/clubs.csv` | `team_id,nom[,couleur]` — le nom et, en option, la couleur (`#rrggbb`) d'un club |
| `mods/competitions.csv` | `competition_id,nom` |
| `mods/portraits/<player_id>.png` | le portrait d'une carte (fond transparent, le visage au tiers supérieur) |
| `mods/logos/<team_id>.png` | l'écusson d'un club (carré) |

Les identifiants sont ceux de la base (`player_id`, `team_id`,
`competition_id`), stables d'une saison à l'autre. Une première ligne
d'en-tête est acceptée ; une ligne qui commence par `#` est ignorée. Les
noms des CSV s'appliquent à la bascule (`--fictif`) ; les images sont
lues à la demande.

L'outil `donnees/portraits.py` (qui recharge les photos depuis FotMob)
est un outil de mod : il remplit `moteur/images/joueurs/`, que le monde
fictif n'utilise jamais.

## Ce qui n'est pas traduit

Les noms fictifs des clubs sont dans la langue de la base (le français
pour les villes : « Séville », « Munich »). Un mod les remplace ; une
version par langue viendrait avec le chantier 5.

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

## Le monde « proche » : reconnaissable, pas le vrai nom

```
py web/app/lancer.py --proche      # ou : py jeu/fictif.py --proche --jeu jeu/demo.sqlite
```

Le prénom reste, une voyelle du nom de famille change : Ousmane Dembéli,
Kylian Mbappi, Mohamed Saleh, Erling Haalend, Lionel Messa. Jamais un vrai
nom de la base, jamais deux cartes du même nom (la variante suivante
sinon). Les clubs et les compétitions sont ceux du monde fictif (la ville,
le pays), les portraits sont les avatars dessinés. La **recherche répond
au vrai nom** : taper « dembele » trouve Dembéli. Le vrai nom n'est ni
affiché ni envoyé à l'écran : la carte porte les empreintes (FNV-1a, six
hexas) des préfixes de quatre lettres et plus de chaque mot du vrai nom,
l'écran hache ce qu'on tape et compare (`jeu/fictif.py`,
`alias_recherche` ; `app.js`, `chercheCarte`).

**À savoir avant de le mettre en ligne.** C'est le procédé des jeux sans
licence (noms déformés, clubs par ville), et il marche parce que le joueur
reconnaît. C'est précisément là qu'est le risque : un nom proche, le
club, l'âge, le poste, les statistiques réelles identifient la personne,
et le droit (nom, image, personnalité ; marques des clubs et des ligues)
s'attache à l'identification, pas à l'orthographe. Ce mode n'est donc pas
plus sûr juridiquement que les vrais noms, il est seulement moins
frontal. Le mode **fictif** (noms sans ressemblance) est le seul des trois
qui ne désigne personne. Le choix se prend avec un avis juridique, pays
de la société en main.

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

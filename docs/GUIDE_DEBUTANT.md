# Guide pas à pas — rejouer la phase 1 sur ton ordinateur

Ce guide part de zéro : tu n'as jamais ouvert de terminal, ni installé
Python. Il est écrit pour Windows ; les différences pour Mac sont notées
à la fin. Compte une demi-heure la première fois, dont dix minutes de
téléchargements.

Un **terminal** est une fenêtre noire dans laquelle on tape des
commandes au lieu de cliquer. Chaque commande de ce guide se copie, se
colle dans cette fenêtre, et se lance avec la touche Entrée. Le terminal
répond par du texte ; ce guide dit à chaque fois ce que tu dois voir.

---

## Étape 1 — Installer Python (une seule fois)

1. Va sur https://www.python.org/downloads/ et clique sur le gros bouton
   **Download Python 3.x**.
2. Lance le fichier téléchargé. Sur le premier écran, **coche la case
   « Add python.exe to PATH »** tout en bas, puis clique **Install Now**.
   Sans cette case, les commandes `py` ne seront pas trouvées.
3. Ferme l'installeur.

## Étape 2 — Récupérer le projet

Pas besoin de Git. Sur GitHub, le projet se télécharge en zip :

1. Ouvre ce lien, il télécharge directement la bonne branche :
   https://github.com/TheFootballAnalyst/FootballLife/archive/refs/heads/claude/football-manager-card-game-kpmpno.zip
2. Le fichier s'appelle `FootballLife-claude-football-manager-card-game-kpmpno.zip`.
   Clic droit dessus → **Extraire tout**. Un dossier du même nom apparaît.
3. Renomme ce dossier en **`FootballLife`** et mets-le où tu veux, par
   exemple dans `Documents`. Dedans tu dois voir `docs`, `donnees`, `jeu`,
   `moteur`, `README.md`.

## Étape 3 — Ouvrir un terminal *dans* ce dossier

C'est le point qui bloque tout le monde la première fois. Le terminal
doit être ouvert **dans le dossier `FootballLife`**, sinon les commandes
ne trouvent pas les fichiers.

1. Dans l'Explorateur de fichiers, ouvre le dossier `FootballLife` (tu
   vois `docs`, `jeu`, `moteur`…).
2. Clique dans la **barre d'adresse** en haut (là où est écrit le chemin),
   efface tout, tape `cmd` et appuie sur Entrée.
3. Une fenêtre noire s'ouvre. La ligne se termine par
   `\FootballLife>` : tu es au bon endroit.

Sur Windows 11, un clic droit dans le vide du dossier propose aussi
**« Ouvrir dans le Terminal »**, ça revient au même.

Vérifie Python en tapant :

```
py --version
```

Attendu : `Python 3.12.x` (ou 3.11, 3.13). Si tu vois « py n'est pas
reconnu », Python n'est pas installé ou la case PATH n'a pas été cochée :
refais l'étape 1.

**Pour la suite, toutes les commandes se tapent dans cette fenêtre.**
Copie la ligne, colle-la (clic droit dans la fenêtre colle), Entrée.

## Étape 4 — Installer les trois bibliothèques

```
py -m pip install -r requirements.txt
```

Ça défile pendant une minute et finit par `Successfully installed …`.
Un avertissement jaune sur la version de pip est sans importance.

## Étape 5 — Vérifier que la notation est juste, sans aucune donnée

```
py -m pytest jeu/tests
```

Attendu, à la dernière ligne : **`22 passed`** en vert.

C'est la vérification la plus importante du projet : un de ces tests
rejoue tes 105 prestations de référence (40 tops, 65 flops) et exige
la note et les six attributs exacts. S'il est vert, le jeu note comme ta
chaîne de visuels.

## Étape 6 — Récupérer les données de la release

Trois commandes, une par fichier. Chacune télécharge, décompresse et
range au bon endroit. Les deux premières prennent une à deux minutes
chacune, la troisième un peu plus.

```
py donnees/telecharger.py https://github.com/TheFootballAnalyst/FootballLife/releases/download/data-2025-26/fotmob_2526.7z
```
```
py donnees/telecharger.py https://github.com/TheFootballAnalyst/FootballLife/releases/download/data-2025-26/cache.7z
```
```
py donnees/telecharger.py https://github.com/TheFootballAnalyst/FootballLife/releases/download/data-2025-26/portraits-joueurs.zip --vers moteur/images
```

Vérification dans l'Explorateur : le dossier `moteur` contient maintenant
`fotmob_2526.db` (452 Mo), un dossier `cache\matches` plein de fichiers
`.json`, et `images\joueurs` plein de `.png`.

*Si tu préfères le faire à la main :* télécharge les trois fichiers
depuis https://github.com/TheFootballAnalyst/FootballLife/releases/tag/data-2025-26,
extrais `fotmob_2526.7z` et `cache.7z` dans `moteur`, et
`portraits-joueurs.zip` dans `moteur\images`. Le résultat doit être le
même que ci-dessus.

## Étape 7 — Importer la saison dans la base du jeu

```
py -m jeu.importer --fotmob moteur/fotmob_2526.db
```

Une ligne par journée s'affiche, `J 1`, `J 2`… jusqu'à `J34`, puis :

```
42810 prestations, 34 journees, 110 couleurs de club -> ...\jeu\jeu_2526.sqlite
```

Ça prend environ 1 min 30. Le moteur a noté chaque prestation de la
saison et tout est rangé dans `jeu\jeu_2526.sqlite`.

## Étape 8 — Rejouer la saison

```
py -m jeu.backtest
```

Instantané. Un bloc de texte s'affiche ; dedans, cherche `"managers"` :

```
"naif":   { "points": 1391.5, ... "valeur": 143.2 }
"forme":  { "points": 1809.8, ... "valeur": 205.7 }
"oracle": { "points": 1979.5, ... "valeur": 236.6 }
"hasard0" ... autour de 700
```

C'est le résultat de `docs/BACKTEST.md` : l'informé (forme) bat le naïf,
le hasard est loin derrière.

Trois fichiers sont écrits dans un nouveau dossier `out` :

| fichier | ce qu'il contient | comment l'ouvrir |
|---|---|---|
| `resume.json` | réglages et résultats | Bloc-notes |
| `cartes.csv` | OVR et prix de chaque carte, journée par journée | Excel |
| `managers.csv` | score, gains, patrimoine de chaque manager par journée | Excel |

Dans `cartes.csv`, filtre sur un joueur pour voir sa courbe de prix.

## Étape 9 — Produire des cartes

```
py -m jeu.cartes --journee 34 --n 8
```

Huit images arrivent dans `out\cartes` : les huit meilleures prestations
de la dernière journée, avec portrait, écusson, couleur du club, note et
attributs. Et une carte de saison, celle du jeu :

```
py -m jeu.cartes --joueur 737066
```

C'est Haaland, OVR 82. Le numéro est l'identifiant FotMob du joueur ; tu
le trouves dans `cartes.csv`, colonne `player_id`.

---

## Jouer avec les réglages

Toute l'économie tient dans les premières lignes de `jeu\evolution.py`.
Ouvre-le avec le Bloc-notes (clic droit → Ouvrir avec) :

| ligne | rôle |
|---|---|
| `BUDGET_INITIAL = 100.0` | budget de départ, en millions d'euros |
| `PRIX_DOUBLE_TOUS_LES = 8` | le prix (parti de la valeur marchande réelle) double tous les 8 OVR gagnés |
| `GAIN_MAX_SEMAINE = 5.0` | gain maximal par journée, en M€ |
| `ALPHA_EMA = 0.08` | vitesse à laquelle une carte bouge après un match |
| `PRIOR_NOTE = 5.5` | note supposée d'un inconnu |
| `K_RETRECISSEMENT = 10.0` | poids de cette supposition, en matchs pleins |

Change une valeur, enregistre, relance l'étape 8, compare. Deux
variantes utiles :

```
py -m jeu.backtest --ligue 53
```
Ligue 1 seule : tu verras l'effet PSG décrit dans `BACKTEST.md`.

```
py -m jeu.backtest --amorce 1-10 --jouer 11-34
```
Amorce plus courte, saison jouée plus longue.

---

## Si ça ne marche pas

- **« py n'est pas reconnu »** : Python n'est pas installé, ou installé
  sans la case PATH. Refais l'étape 1, puis ferme et rouvre le terminal.
- **« No such file or directory »** ou **« can't open file »** : le
  terminal n'est pas ouvert dans le dossier `FootballLife`. Refais
  l'étape 3.
- **« No module named jeu »** : même cause, mauvais dossier.
- **« No module named PIL »** ou **pytest** : l'étape 4 n'a pas été
  faite, ou a échoué.
- **Étape 6, erreur réseau** : réessaie, ou passe par la méthode à la
  main.
- **Autre chose** : copie tout le texte de la fenêtre (clic droit →
  Sélectionner tout, puis Entrée pour copier) et envoie-le tel quel.

---

## Sur Mac

Le terminal s'appelle **Terminal** (dans Applications → Utilitaires).
Pour l'ouvrir dans le dossier : glisse le dossier `FootballLife` sur
l'icône du Terminal, ou tape `cd ` (avec l'espace) puis glisse le dossier
dans la fenêtre et fais Entrée. Python s'installe aussi depuis
python.org. Ensuite, remplace `py` par `python3` dans toutes les
commandes ; tout le reste est identique.

## Pour mettre à jour le projet plus tard

Retélécharge le zip de l'étape 2 et remplace le dossier, en gardant tes
dossiers `moteur\cache`, `moteur\images\joueurs`, le fichier
`moteur\fotmob_2526.db` et `jeu\jeu_2526.sqlite` : ce sont les seuls
gros fichiers, et ils ne changent pas d'une version à l'autre.

# Deux jeux côte à côte : le dev et le témoin

On développe les idées du plan (`docs/PLAN.md`) dans le dépôt de dev, et on
garde à côté un **témoin** qui ne bouge pas : le jeu initial d'avant les
chantiers, ou le miroir de ce qui est en ligne.  Chacun a son dossier, son
code figé sur un commit, sa base, son port.  On joue à l'un puis à l'autre,
dans deux onglets.

## Ce qui est réversible

**Le code : tout.**  Chaque chantier est un commit sur la branche
(`git log --oneline`) ; rien n'a été réécrit dans l'historique.  Le jeu
initial est le commit `891dc15` (tag `jeu-initial`), le dernier avant le
chantier 1 de l'économie.  Revenir en arrière dans le dépôt de dev, c'est
`git revert <commit>` (un commit qui défait l'autre) ou `git checkout
jeu-initial` (regarder, sans toucher à la branche).

**La base : les migrations sont additives.**  Le nouveau jeu ajoute des
colonnes (`utilisateur.naissance`, `premium_jusqua`…) et des tables
(`etat_carte` pour les blessures et suspensions, `achat`,
`cohesion_jeu`) ; il ne supprime ni ne renomme rien (`jeu/importer.py`,
`MIGRATIONS`).  Vérifié : l'ancien code (`jeu-initial`) ouvre une base
migrée par le nouveau et y joue (inscription, packs, alignement, campagne
solo, match) ; il ignore ce qu'il ne connaît pas.  Les mots de passe sont
hachés de la même façon des deux côtés.

**Le monde fictif se défait** : `py web/app/lancer.py --reel` remet les
vrais noms (`joueur.nom_reel` est gardé).  Le script ci-dessous le fait
avant de copier une base vers un témoin, qui ne connaît pas les noms fictifs.

**Ce qui reste** : ce que le nouveau jeu a écrit dans une base y reste (les
lignes de `etat_carte`, les packs à cinq cartes déjà ouverts, les primes
versées).  L'ancien code n'en tient pas compte, mais ne les efface pas non
plus.  Pour un témoin vraiment vierge, on repart d'une base neuve
(`py web/app/demo.py`).

## Les environnements

| nom       | dossier                   | code                                  | port | base                    |
|-----------|---------------------------|---------------------------------------|------|-------------------------|
| `dev`     | `FootballLife/`           | la branche, ce qu'on développe        | 8000 | `jeu/demo.sqlite`       |
| `initial` | `FootballLife-initial/`   | tag `jeu-initial` (`891dc15`)         | 8001 | sa copie, monde réel    |
| `prod`    | `FootballLife-prod/`      | tag `prod` (sinon la branche)         | 8002 | sa copie                |

Un témoin est un *worktree* git : un second dossier à côté du dépôt, posé
sur un commit.  Il partage l'historique avec le dépôt de dev (pas de second
clone), mais pas son code de travail : commiter dans le dev ne le change pas.
Son `jeu/.secret` est à lui (les sessions sont séparées), sa base aussi.
Les portraits (`moteur/images/joueurs`, téléchargés sur ta machine) sont
reliés et non copiés.

```
py outils/environnements.py creer initial      # crée le dossier, copie la base de dev (remise en monde réel)
py outils/environnements.py lancer initial     # http://localhost:8001
py outils/environnements.py lancer dev         # http://localhost:8000  (= py web/app/lancer.py)
py outils/environnements.py etat               # commit, base et port de chacun
py outils/environnements.py base initial       # recopier la base de dev dans le témoin (écrase la sienne)
```

`creer` accepte `--base <fichier>` pour partir d'une autre base, et
`lancer` passe le reste de la ligne à `lancer.py` (`--fictif`, `--limites`,
`--copies 3`… selon ce que le code de cet environnement connaît).

**Déplacer le miroir de prod** : quand une version est en ligne, on pose le
tag dessus et on recrée le témoin :

```
git tag -f prod <commit>
py outils/environnements.py creer prod
```

Pour partager un tag avec le dépôt GitHub : `git push origin jeu-initial`
(ou `prod`).  Sans ça, le script se replie sur le commit `891dc15` pour
`initial`, et sur la branche courante pour `prod`.

## Comparer

Les deux jeux lisent les mêmes cartes (même saison, même barème, le moteur
dans `moteur/` n'a pas changé entre les deux) : une même composition se
joue des deux côtés, et ce qui diffère est ce que les chantiers ont
apporté — packs à cinq cartes et pack du jour, objectifs de club et forme,
blessures d'un match à l'autre, boîte de dialogue, langues, monde fictif,
comptes et limites, le seul moteur du direct.  Les bancs de mesure
(`outils/*_moteur.py`) tournent dans n'importe lequel des dossiers.

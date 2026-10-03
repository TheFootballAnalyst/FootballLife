# Ta prod, un terrain d'essai, et des témoins

Trois choses qu'on veut tenir à part :

- **la prod** : ce que tu joues, `jeu/demo.sqlite`, les vrais noms, les
  vraies équipes, les portraits téléchargés sur ta machine ;
- **le test** : les nouveautés du plan (`docs/PLAN.md`), essayées sans
  toucher à la prod ;
- **des témoins** : le jeu d'avant les chantiers, ou le miroir de ce qui
  est en ligne, pour comparer.

Tout passe par `outils/environnements.py`.

## Le test : même code, autre base

Les nouveautés sont dans le code de la branche ; ce qui doit rester à
part, ce sont **les données** (tes comptes, tes équipes, tes packs). Le
test est donc une seconde base dans le même dossier, `jeu/test.sqlite`,
copiée depuis ta prod :

```
git pull origin claude/football-manager-card-game-kpmpno   # le code à jour
py outils/environnements.py creer test                     # jeu/test.sqlite, copie de jeu/demo.sqlite
py outils/environnements.py lancer test                    # http://localhost:8001
```

Et ta prod ne change pas de commande : `py web/app/lancer.py`, ou
`py outils/environnements.py lancer prod`, port 8000, `jeu/demo.sqlite`.
Les deux peuvent tourner en même temps, dans deux onglets.

Ce que tu peux essayer sur le test et pas sur la prod : le monde fictif
(`lancer test --fictif`, réversible par `lancer test --reel` ; il réécrit
les noms dans la base, donc dans `jeu/test.sqlite` seulement), les limites
du gratuit et le premium (`lancer test --limites`), une autre langue
(le sélecteur en haut de l'écran, sans option). Les blessures, la boîte de
dialogue, les objectifs de club, les packs à cinq cartes sont dans le
code : ils sont là aussi sur la prod dès que tu la relances avec le code
à jour.

Pour repartir d'une copie fraîche : `py outils/environnements.py base test`.

## Ce qui est réversible

**Le code : tout.** Chaque chantier est un commit sur la branche
(`git log --oneline`), rien n'a été réécrit. Le jeu initial est le commit
`891dc15` (tag local `jeu-initial`), le dernier avant le chantier 1 de
l'économie.

**La base : les migrations sont additives.** Le nouveau code ajoute des
colonnes (`utilisateur.naissance`, `premium_jusqua`…) et des tables
(`etat_carte` pour les blessures et suspensions, `achat`, `cohesion_jeu`),
ne supprime ni ne renomme rien (`jeu/importer.py`, `MIGRATIONS`). Vérifié :
l'ancien code ouvre une base migrée par le nouveau et y joue (inscription,
packs, alignement, campagne solo, match). Les mots de passe sont hachés
de la même façon des deux côtés. Donc relancer ta prod avec le code à jour
ne la casse pas, et revenir en arrière non plus.

**Le monde fictif se défait** : `--reel` remet les vrais noms
(`joueur.nom_reel` est gardé).

**Ce qui reste** : ce que le nouveau code a écrit dans une base y reste
(les lignes de `etat_carte`, les packs à cinq cartes déjà ouverts). L'ancien
code n'en tient pas compte, mais ne les efface pas.

## Les témoins : un code figé dans un dossier à côté

Un témoin est un *worktree* git : un second dossier à côté du dépôt, posé
sur un commit (nommé par un **tag**, c'est-à-dire un signet sur un commit,
un nom pour une version). Il partage l'historique avec le dépôt, pas son
code de travail : commiter ici ne le change pas. Il a sa base (copie de
ta prod, remise en monde réel), son secret de session, son port ; les
portraits sont reliés, pas copiés.

| nom       | dossier                  | code                            | port | base                   |
|-----------|--------------------------|---------------------------------|------|------------------------|
| `prod`    | `FootballLife/`          | la branche                      | 8000 | `jeu/demo.sqlite`      |
| `test`    | `FootballLife/`          | la branche                      | 8001 | `jeu/test.sqlite`      |
| `initial` | `FootballLife-initial/`  | tag `jeu-initial` (`891dc15`)   | 8002 | sa copie, monde réel   |
| `miroir`  | `FootballLife-miroir/`   | tag `prod` (sinon la branche)   | 8003 | sa copie               |

```
py outils/environnements.py creer initial      # le jeu d'avant les chantiers
py outils/environnements.py lancer initial     # http://localhost:8002
py outils/environnements.py etat               # commit, base et port de chacun
```

`creer` accepte `--base <fichier>` pour partir d'une autre base, et
`lancer` passe le reste de la ligne à `lancer.py` (`--fictif`, `--limites`,
`--copies 3`… selon ce que le code de cet environnement connaît).

**Le miroir** sert le jour où une version est en ligne : on pose le tag
sur le commit déployé et on recrée le témoin (`git tag -f prod <commit>`
puis `creer miroir`). Pour partager un tag avec GitHub : `git push origin
jeu-initial` (ou `prod`). Sans ça, le script se replie sur le commit
`891dc15` pour `initial`, et sur la branche courante pour `miroir`.

## Comparer

Prod, test et témoins lisent les mêmes cartes (même saison, même barème ;
le moteur dans `moteur/` n'a pas changé) : une même composition se joue
des deux côtés, et ce qui diffère est ce que les chantiers ont apporté.
Les bancs de mesure (`outils/*_moteur.py`) tournent dans n'importe lequel
des dossiers.

# Le jeu sans ballon : les principes, lus dans le football réel

Ce document est la référence tactique du moteur B pour tout ce qui se passe
quand on n'a pas le ballon. Il ne décrit pas des équipes : il décrit des
**principes**, chiffrés, que n'importe quelle équipe (y compris une équipe
fantasy d'un joueur) porte selon son profil. Les chiffres viennent de deux
sources versées dans la release `data-2025-26` :

- les données ouvertes StatsBomb : 300 matchs avec la position des vingt-deux
  joueurs à chaque action (Bundesliga 2023/24, Ligue 1 2021/22 et 2022/23, Liga
  2020/21, Coupe du monde 2022, Euro 2020 et 2024), soit 85 équipes-saisons,
  lues par `outils/tactique_ref.py` qui écrit `jeu/tactique_ref.json` ;
- le rapport technique UEFA de la Ligue des champions 2024/25, qui explique
  et confirme (Inter : 16,8 m entre centraux et attaquants en bloc bas,
  20,7 m d'épaisseur en bloc médian ; le Real : 15 minutes en bloc médian
  contre City ; Atalanta et Liverpool : la passe au latéral comme
  déclencheur ; le contre-pressing défini comme une pression dans les cinq
  secondes après la perte).

Tout est en mètres, vu du but de l'équipe **sans** ballon. « Ballon à 50 m »
veut dire à cinquante mètres de notre but. La même lecture s'applique aux
traces du moteur avec `outils/tactique_moteur.py`, pour comparer à règle
égale.

## 1. La ligne suit le ballon, à vingt mètres

La hauteur de la ligne défensive (la médiane des trois joueurs les plus
bas) est une fonction presque linéaire de la position du ballon :

| ballon à | ligne (tous profils) | bloc haut | bloc bas | épaisseur du bloc | largeur | joueurs entre ballon et but |
|---|---|---|---|---|---|---|
| 10 m | 8 m | 8 | 8 | 15 m | 25 m | 3 |
| 20 m | 14 m | 14,5 | 14 | 16 m | 28 m | 6 |
| 30 m | 19 m | 19 | 18 | 19 m | 30 m | 7 |
| 40 m | 25 m | 26 | 23 | 21 m | 32 m | 8 |
| 50 m | 32 m | 33 | 30 | 22 m | 33 m | 8 |
| 60 m | 39 m | 41 | 37 | 23 m | 34 m | 8 |
| 70 m | 48 m | 49,5 | 45 | 24 m | 35 m | 7 |
| 80 m | 58 m | 61 | 55 | 24 m | 34 m | 6 |
| 90 m | 67 m | 69 | 64 | 24 m | 33 m | 7 |

En clair : **ligne ≈ 0,75 × ballon − 6**. Le ballon au rond central (52 m),
la ligne est à 33 m ; le ballon chez leur gardien (90 m), la ligne est à
la moitié du terrain. L'écart entre un bloc haut et un bloc bas n'est que
de trois à six mètres : ce n'est pas la hauteur qui distingue les profils,
c'est ce qu'ils font du ballon (voir 3).

## 2. Le bloc a trois lignes, vingt-deux mètres d'épaisseur

Au milieu du terrain le bloc fait **22 à 24 m** du dernier défenseur au
premier attaquant, et **35 m** de large. Dans sa surface, il se tasse à
**16 m** d'épaisseur et 28 m de large (Inter : 16,8 m). Les attaquants
sont donc en permanence 20 m devant leur défense : ce sont eux qui donnent
la profondeur du bloc, et ce sont eux qui font la première pression. Un
bloc « à plat » de dix joueurs sur douze mètres n'existe pas.

Huit joueurs entre le ballon et le but quand le ballon est au milieu, sept
dans le dernier tiers, six quand le ballon est chez l'adversaire.

## 3. Le pressing : une chaîne courte, rarement une longue

- Une pression individuelle dure 0,6 s en médiane. Une séquence de
  pressing (des pressions à moins de trois secondes l'une de l'autre) est
  presque toujours de une ou deux pressions ; **une séquence de trois
  pressions ou plus n'arrive que dans 5 % des cas, et dure 3,7 s (5,7 s au
  neuvième décile)**. Le pressing n'est pas un état qui dure dix secondes :
  c'est une vague, et si elle ne récupère pas, on se replace.
- **Deux relances adverses sur trois (67 à 70 %) reçoivent au moins une
  pression** ; 26 à 30 % sont perdues dans leur moitié.
- 1,5 à 1,7 pressions par possession adverse, dont 31 à 42 % dans leur
  tiers, 45 % au milieu, 15 à 23 % dans notre tiers.
- Le PPDA (passes adverses concédées par action défensive dans leurs 60 %)
  distingue les profils : **14 pour un bloc haut, 16 pour un médian, 20
  pour un bas**.
- Déclencheurs, d'après le rapport UEFA : la passe au latéral (Atalanta,
  Liverpool), la passe en retrait, le ballon au gardien. Le Real de
  Ancelotti presse haut seulement sur la relance du gardien puis se
  replace en bloc médian où « les deux attaquants ferment l'intérieur pour
  que les milieux n'aient pas à sortir ».

## 4. Après la perte : cinq secondes de contre-pressing, puis le repli

Une équipe qui perd le ballon dans la moitié adverse **presse dans les
cinq secondes dans 29 à 32 % des cas** (Monaco, le plus haut de la Ligue
des champions, 50 actions par match). Cinq secondes après la perte, sa
ligne est encore à 44–48 m : elle est restée haute pour le contre-pressing,
puis elle redescend.

## 5. La ligne recule vite et remonte lentement

Quand le ballon avance vers nous, la ligne recule à **1,8 à 2,0 m/s** ;
quand il recule, elle remonte à **1,1 à 1,2 m/s**. (Ce sont des vitesses
moyennes sur les intervalles entre deux actions, pas des pointes.)

## 6. Les trois profils

Le classement par tiers de la hauteur de ligne au milieu donne, sur 85
équipes-saisons :

| | bloc haut | bloc médian | bloc bas |
|---|---|---|---|
| ligne, ballon au milieu | 37,5 m | 35 m | 32,5 m |
| épaisseur au milieu | 24 m | 23 m | 22 m |
| PPDA | 14,3 | 15,7 | 19,6 |
| relances pressées | 67 % | 67 % | 70 % |
| relances gagnées haut | 30 % | 28 % | 26 % |
| pressions dans leur tiers | 31 % | 36 % | 42 % |
| contre-pressing en 5 s | 32 % | 29 % | 29 % |
| ligne 5 s après une perte haute | 48,5 m | 47 m | 44 m |

Lecture : un bloc haut n'est pas un bloc qui presse tout le temps, c'est
un bloc qui tient sa ligne cinq mètres plus haut, qui gagne plus de
relances haut, et qui contre-presse un peu plus. Le bloc bas presse
autant de relances, mais moins efficacement, et concède beaucoup plus de
passes par action défensive.

## 7. Le moteur B aujourd'hui, à la même règle

`outils/tactique_moteur.py` sur quatre matchs du banc :

| | réel | moteur |
|---|---|---|
| ligne, ballon à 50 m | 32 m | 37 m |
| ligne, ballon à 60 m | 39 m | 44 m |
| ligne, ballon à 80 m | 58 m | 55 m |
| épaisseur au milieu | 22–23 m | 19 m |
| largeur au milieu | 33–35 m | 45 m |
| recul / montée de la ligne | 1,8 / 1,1 m/s | 1,1 / 0,6 m/s |
| contre-pressing en 5 s | 31 % | 93 % |

Le diagnostic est net : la ligne est cinq mètres trop haute au milieu et
trop basse face à la relance adverse, le bloc est dix mètres trop large et
trop plat, la ligne bouge deux fois trop lentement, et le contre-pressing
est systématique au lieu d'être un choix une fois sur trois.

## 8. Ce que ça change dans le moteur (à faire)

1. **La ligne = 0,75 × ballon − 6**, plus ou moins trois mètres selon le
   profil ; elle recule à 2 m/s et remonte à 1,2 m/s.
2. **Trois lignes** : milieux 10 m devant la défense, attaquants 10 m
   devant les milieux ; largeur 35 m au milieu, 28 m dans la surface ; les
   attaquants redescendent pour tenir l'épaisseur.
3. **Le pressing comme une vague** : un déclencheur (relance, passe au
   latéral, passe en retrait), une séquence de une à trois pressions,
   trois à six secondes, puis on se replace ; deux relances sur trois
   pressées ; le PPDA du profil comme cible.
4. **Le contre-pressing comme un choix** : une fois sur trois dans les
   cinq secondes, la ligne reste haute pendant ces cinq secondes, puis le
   repli.
5. **Le profil d'une équipe fantasy** se lit dans ses joueurs : le taux de
   travail défensif et le pressing des attaquants et milieux (les cartes
   les portent déjà) donnent le PPDA et la part de contre-pressing ; la
   consigne du manager (bloc haut/médian/bas) donne la hauteur de ligne.

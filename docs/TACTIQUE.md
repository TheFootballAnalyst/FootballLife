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

## 7. Le moteur B à la même règle, avant et après

`outils/tactique_moteur.py` sur quatre matchs du banc :

| | réel | moteur avant | moteur après |
|---|---|---|---|
| ligne, ballon à 40 m | 25 m | 27 m | 26 m |
| ligne, ballon à 50 m | 32 m | 37 m | 34,5 m |
| ligne, ballon à 60 m | 39 m | 44 m | 42 m |
| ligne, ballon à 80 m | 58 m | 55 m | 56 m |
| ligne, ballon à 90 m | 67 m | 58 m | 62 m |
| épaisseur au milieu | 22–23 m | 19 m | 22–23 m |
| largeur au milieu | 33–35 m | 45 m | 39 m |
| recul de la ligne | 1,8 m/s | 1,1 m/s | 1,6 m/s |
| relances pressées | 67–70 % | (état permanent) | 67 % |
| durée d'une vague de pressing | 3,7 s | 1,3 s | 3,5 s |
| contre-pressing choisi après une perte haute | 29–32 % | 100 % | 30 % |
| hors-jeu par match | 3,5 | 1,3 | 2,1 |

Et sur un PSG–Bayern de 90 minutes, le bloc médian a maintenant sa ligne
à 37 m (41 avant), les milieux 9 à 10 m devant, les attaquants 7 à 10 m
devant les milieux : trois lignes sur vingt mètres au lieu d'une dalle
sur douze. Restent au-dessus du réel : la largeur (39 m contre 35) et la
montée de la ligne, encore lente.

## 8. Comment le moteur porte ces principes

Tout est dans `jeu/emergent.py`, en constantes de tête de module :

1. **La ligne** (`LIGNE_PENTE`, `LIGNE_BASE`, `LIGNE_PROFIL`) : la forme
   pose la défense à 0,75 × ballon − 6, plus trois mètres pour un bloc
   haut, moins trois pour un bloc bas ; le bloc lit un ballon filtré qui
   ne recule que de `LIGNE_RECUL` (3,5 m/s) et ne remonte que de
   `LIGNE_MONTEE` (2,5 m/s) par tic ; la ligne peut monter aux talons
   du dernier attaquant en jeu, de quatre mètres au plus.
2. **Trois lignes** : en bloc médian les milieux à 9–11 m devant la
   défense, le meneur à 16, les ailiers à 14, le buteur à 21 (jamais plus
   de quatre mètres devant le ballon) ; latéraux à 16,5 m de l'axe, ailiers
   à 17. En bloc bas tout se resserre avec la distance du ballon : seize
   mètres d'épaisseur et 26 m de large dans la surface, 22 et 32 à
   cinquante mètres.
3. **La vague** (`VAGUE_DECLENCHEUR`, `VAGUE_DUREE`, `VAGUE_REPOS`) : une
   relance courte adverse (un tirage par relance), une passe au latéral
   ou une passe en retrait dans leur moitié tirent une vague avec une
   probabilité qui dépend du profil (0,8 / 0,62 / 0,5) et de l'envie de
   presser des attaquants et des milieux ; la vague dure trois à six
   secondes, s'arrête dès que le ballon nous a dépassés ou qu'on l'a
   récupéré, et cinq secondes de repos suivent. Pendant la vague, la
   phase est `pressing` : le bloc monte de quatre mètres, l'homme à
   homme sur la relance courte s'applique. Le fil du bac note chaque
   vague (`vague`, avec son déclencheur).
4. **Le contre-pressing** (`CONTRE_PRESSING`, `CONTRE_PRESSING_DUREE`) :
   à chaque perte dans la moitié adverse, un tirage (0,42 / 0,32 / 0,25
   selon le profil, modulé par l'envie) ; si oui, cinq secondes de
   `contre_pressing` avec la ligne gelée où elle était ; sinon le repli :
   le presseur ferme à sept mètres en reculant au lieu de sauter dans les
   pieds, et la ligne redescend à sa hauteur de forme.
5. **La consigne « bloc haut »** ne veut plus dire « presser tout le
   temps » : c'est une ligne trois mètres plus haute, des vagues plus
   probables et un contre-pressing plus fréquent — ce que le réel montre.

### La sortie de but, après coup

La première version faisait expirer la vague (trois à six secondes)
avant même le coup, puisqu'une sortie de but dure neuf secondes d'arrêt :
l'homme à homme disparaissait et la forme envoyait le buteur dans la
surface. Une vague partie sur une relance tient maintenant tant que la
relance dure, plus quatre secondes après le coup ; et sur une sortie de
but, personne du camp adverse n'entre dans la surface, quelle que soit
la phase. Mesuré : le pressing est en place sur 73 % des sorties de but
(réel : deux sur trois), 0,05 joueur adverse dans la surface par sortie.
Au passage, la zone d'un latéral se borne à son côté, hors du couloir
central de sept mètres, et les centraux choisissent leur homme avant les
latéraux : Hakimi ne marque plus Kane en bloc bas (un latéral marque un
avant-centre dans 5 % de ses marquages, un homme dans l'axe dans 9 %).

## 10. Le jeu avec ballon : les principes, et le moteur à la même règle

`outils/tactique_ballon.py` lit les mêmes 300 matchs (85 équipes-saisons)
et écrit `jeu/tactique_ballon.json` ; `outils/tactique_moteur_ballon.py`
mesure le moteur B à la même règle. Trois profils, par le tiers des
passes par possession : possession, équilibré, direct.

| | réel (tous) | possession | direct | moteur avant | moteur après |
|---|---|---|---|---|---|
| durée d'une possession | 14,8 s | 18,2 s | 11,6 s | 19,4 s | 15,9 s |
| passes par possession | 6,5 | 7,9 | 4,7 | 3,6 | 3,7 |
| secondes par passe | 3,1 | 3,0 | 3,4 | 6,8 | 6,0 |
| progression en conduite | 24 % | 26 % | 19 % | 50 % | 38 % |
| passes par match et par équipe | 527 | 664 | 370 | 428 | 489 |
| réussite | 87 % | 90 % | 80 % | 86 % | 85 % |
| part de longues (≥ 30 m) | 11 % | 8 % | 16 % | 14 % | 15 % |
| réussite des longues | 61 % | 68 % | 51 % | 78 % | 76 % |
| passes vers l'avant / en arrière | 42 % / 25 % | 40 / 25 | 47 / 23 | 34 % / 32 % | 40 % / 28 % |
| entrées dans le dernier tiers | 32 par match | 38 | 24 | 41 | 40 |
| … dont en passe par le couloir | 53 % | | | 7 % | 10 % |
| passes en profondeur | 2,8 par match | 4,2 | 1,2 | 14,2 | 3,8 |
| dribbles tentés / réussis | 13,7 / 57 % | | | 15,6 / 30 % | 10,7 / 27 % |
| tirs par équipe | 11,7 | 14,1 | 8,9 | 11,5 | 11,6 |
| tirs dans la surface | 64 % | 66 % | 61 % | 79 % | 90 % |
| xG par tir | 0,102 | 0,111 | 0,087 | 0,089 | 0,103 |
| tirs après un centre / après un dribble | 16 % / 1 % | | | 2 % / 35 % | 3 % / 26 % |
| tirs en contre (moins de 15 s) | 10 % | 9 % | 13 % | 18 % | 19 % |
| sorties de but courtes | 56 % | 71 % | 38 % | 100 % | 60 % |
| relance courte qui atteint la moitié adverse | 68 % | | | 21 % | 25 % |

Ce qui a été fait dans le moteur, en constantes de tête de module :
la garde du porteur passe de 3,6 + 3 × (1 − pression) secondes à 2,6 +
2,6 (`GARDE` ; à 2 + 2,2 le tempo colle au réel mais les tirs montent à
36 et les buts à six, la défense ne suit pas encore un jeu si rapide) ;
on ne conduit pendant la garde que dans dix mètres de champ et en
progression ; la passe en profondeur vaut 0,45 de moins (14 par match →
4, réel 3) ; la progression pèse plus dans le choix d'une passe
(`GAIN_POIDS`) et la passe qui entre dans le dernier tiers par le couloir
gagne 0,35 (`ENTREE_COULOIR`) ; une passe longue rate un peu plus ; la
sortie de but est longue une fois sur deux selon le profil (29 % pour une
équipe de possession, 62 % pour une équipe directe, plus si on est
pressé ou peu technique) ; un adversaire dans les pieds enlève 0,6 à
l'envie de frapper au lieu de 0,15 (`TIR_PRESSION`) et la frappe de loin
s'ouvre dès que l'axe est libre ; le crochet réussit à 0,55 de base
(`CROCHET_BASE`) et la provocation vaut un peu moins (`PROVOQUE_BASE`).

Ce qui reste loin du réel, et pourquoi on s'arrête là pour l'instant :
le tempo (6 s par passe contre 3 : la moitié du temps d'une possession
est du ballon en l'air ou qui roule, l'autre moitié de la garde ; la
garde plus courte est la bonne piste, mais elle demande que la défense
suive), l'entrée dans le dernier tiers par le couloir (10 % contre 53 %),
les tirs après centre (3 % contre 16 %) et hors de la surface (10 %
contre 36 %), la relance courte qui n'atteint la moitié adverse qu'une
fois sur quatre (le pressing homme à homme la mange ; réel deux sur
trois), et les dribbles qui réussissent une fois sur quatre au lieu
d'une sur deux — leur compte dans le moteur mélange les crochets et les
tacles subis, il faudra une mesure plus fine. Les écarts sur la « passe
sous pression » ne se comparent pas : StatsBomb note une pression
active, le moteur un adversaire à moins de 4,5 m.

## 9. Pour les équipes fantasy

Les principes sont les mêmes pour toutes les équipes. Ce qui varie :
la consigne du manager (bloc haut, médian, bas : la hauteur de ligne et
les probabilités de vague et de contre-pressing) et les joueurs (l'envie
de presser des attaquants et des milieux, lue sur leurs cartes, module
ces probabilités ; leur vitesse et leur endurance décident si la vague
arrive à temps). Une équipe de presseurs avec un manager qui demande un
bloc haut pressera comme Liverpool ; la même consigne avec des
attaquants qui ne courent pas donnera un bloc haut qui ne mord pas.

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

## 11. Le tempo et la réaction de la défense

Décomposé sur un PSG–Bayern : les six secondes entre deux passes du
moteur, c'était 2,3 s de garde du porteur et 2,8 s de ballon libre (le
vol, mais surtout les ballons qui roulent après une passe ratée, un
dégagement, un duel, et qu'on court chercher). Le réel est à trois
secondes en tout. Et une possession finissait après 3,3 passes (réel
6,5) : 277 possessions par match au lieu de 160, parce que les pertes
hors passe (têtes perdues sur les longs ballons, duels, contrôles,
ballons libres) sont deux fois plus nombreuses.

Réglé ensemble, parce qu'une garde plus courte sans défense plus
réactive donne six buts par match (à 1,5 + 1,6 s : 4,8 buts, 29 tirs) :

- la garde passe à 2,3 + 2,3 × (1 − pression) secondes (`GARDE`) : 1,8 s
  en médiane avant une passe ; 5,5 s par passe au lieu de 6,8, 4 passes
  par possession au lieu de 3,6 ;
- une passe ratée part moins de travers (8° au lieu de 12°) : elle
  trouve encore souvent un coéquipier ;
- la défense suit un jeu plus rapide : un joueur loin de sa place (plus
  de six mètres) y court à 5,5 m/s au lieu de 3,5 ; la ligne recule à
  5 m/s au plus (`LIGNE_RECUL`) ; un marqueur anticipe la course de son
  homme de six dixièmes au lieu de quatre, et souffle une passe à 2,6 m
  (3,4 m dans les vingt-cinq derniers mètres) au lieu de 2,2 ; le
  presseur arrive à 7 m/s.

Mesuré : banc 3,1 buts et 25 tirs sur trois graines (à 2 + 2 s : 3,3 et
27 ; à l'ancienne garde : 3,5 et 22), la ligne à 34 m ballon au milieu,
recul de la ligne 1,5 m/s (réel 1,8). Ce qui reste : les trois secondes
de ballon libre par passe, qui sont un problème de ballons perdus, pas
de garde — le prochain levier est là (moins de têtes perdues sur les
longs ballons, des contrôles qui gardent le ballon, des ballons qui
roulent vers un coéquipier plutôt que nulle part).

## 12. Les ballons perdus

Comment finit une possession, sur 60 matchs réels de club (165
possessions par match, 6,7 passes par possession) et dans le moteur
(230 possessions, 4,4 passes) — `pertes_reel.py` et `pertes_moteur.py`
dans le bac à sable, la même classification des deux côtés :

| fin de possession, par match | réel | moteur |
|---|---|---|
| passe courte ou moyenne ratée | 37 | 50 |
| tir | 19 | 12 |
| faute subie | 17 | 3,5 |
| passe longue ratée | 17 | 15 |
| dribble perdu, dépossédé | 16,5 | 12 |
| contrôle raté | 12,6 | 7,5 |
| passe sortie du terrain | 10,5 | 21 (41 avant) |
| passe haute ratée | 9,6 | 1 |
| tête perdue | (dans les passes hautes et longues) | **100** |

Le coupable est là : **163 têtes par match** dans le moteur (réel : une
quarantaine de duels aériens), parce que toute passe un peu levée
arrivait à hauteur de tête et devenait un duel de la tête, perdu cent
fois par match. Et trente ballons par match sortaient du terrain sur des
têtes dégagées avec cinquante degrés d'erreur.

Ce qui est fait : une passe ne vise jamais à moins d'un mètre et demi
d'une ligne (les sorties passent de 41 à 21) ; on ne lobe une passe
courte par-dessus un défenseur que si la ligne est vraiment fermée ;
une passe longue pèse un peu plus dans le choix ; le contrôle raté est
un événement (le bac peut le montrer) ; un défenseur à moins de deux
mètres et demi du ballon dispute la tête.

Ce qui est essayé et parqué, parce que ça fait monter les buts (mesuré
sur 36 matchs, la seule taille de banc qui tranche) : la tête comme une
passe vers un coéquipier (`TETE_REMISE`, +1 but par match), le contrôle
à la poitrine d'un receveur seul (`CONTROLE_POITRINE`, +0,4 but), un lob
court qui retombe bas devant le receveur (`LOB_BAS`, +1,5 but). Les
trois allongent les possessions, et les possessions allongées finissent
dans la surface : ce n'est pas que ces règles sont fausses, c'est que la
défense ne sait pas encore défendre une possession longue. C'est le
même mur que le tempo (§ 11). Le prochain chantier est donc défensif :
pourquoi une possession qui dure produit un tir, et comment un bloc réel
l'empêche (les 13 % de possessions réelles qui finissent en tir, contre
nos 10 %, sur des possessions deux fois plus courtes).

Banc retenu, 36 matchs : 3,2 buts, 24 tirs (le moteur d'avant ce
chantier : 3,3 et 24 sur les mêmes graines).

## 13. Défendre une possession longue : la surface d'abord

Comment une possession devient un tir, sur 150 matchs réels de club
(événements et positions 360) et dans le moteur — `outils/surface_ref.py`
et `outils/surface_moteur.py`, la même règle des deux côtés :

| | réel | moteur avant | moteur après |
|---|---|---|---|
| possessions de 10 passes et plus qui finissent par un tir | 20 % | 29 % | 21 % |
| ... par un tir dans la surface | 13 % | 27 % | 16 % |
| tirs dans la surface | 66 % | 87 % | 66 % |
| centres par match | 18,5 | 41 | 21,5 |
| centres qui arrivent | 35 % | 56 % | 40 % |
| têtes sur centre : attaquant / défenseur | — | 22 / 4 | 8 / 12 |
| passes dans la surface tentées, réussies | 35, 48 % | 10, 81 % | 14,5, 76 % |
| conduites qui entrent dans la surface | 12 | 15 | 15,5 |
| défenseur le plus proche du passeur, dernier tiers | 2,8 m | 2,0 m | 2,0 m |
| défenseur le plus proche du tireur | 1,9 m | 2,2 m | 2,8 m |

Le bloc réel ne va pas au ballon dans les trente derniers mètres : il
protège la surface. Le passeur a son vis-à-vis à 2,8 m (à moins de trois
mètres une fois sur deux), mais six défenseurs sont dans la surface au
moment du tir, un dans le cône ballon-but, et deux tirs sur trois
viennent de dedans seulement : le bloc **donne la frappe de loin et
refuse l'entrée**. Deux centres sur trois ne trouvent personne, une
passe dans la surface sur deux est coupée.

Le moteur faisait l'inverse : il pressait tout le monde à deux mètres
(83 % des passes du dernier tiers avec un homme à moins de trois mètres)
et laissait la surface ouverte. Quarante centres par match, gagnés de la
tête par l'attaquant vingt-deux fois contre quatre — parce que sur un
centre, les attaquants attendent au point de penalty, huit mètres devant
une ligne restée sur les six mètres, et qu'un central refusait de
marquer un homme « hors zone » à plus de huit mètres de sa ligne. Le
défenseur le plus proche du point de chute ne s'y rendait pas non plus :
la chasse du ballon libre calculait où un ballon *au sol* s'arrête, pas
où un ballon en l'air retombe.

Ce qui est fait :

- **Le défenseur attaque le ballon en l'air** (`BALLON_AERIEN`) : le
  plus proche du point où le ballon redescend à hauteur de tête y va,
  y compris un défenseur dans sa surface ; l'attaquant, lui, l'attend.
  Et dans sa surface il gagne la tête un peu plus souvent
  (`AERIEN_SURFACE`) : il l'attaque de face.
- **Dans la surface, on marque son homme où qu'il soit**
  (`MARQUAGE_SURFACE`) : quand le ballon est à moins de vingt-huit
  mètres, un central prend l'attaquant au point de penalty même à dix
  mètres devant la ligne. Plus loin, la ligne tient (la profondeur
  d'abord) — seul, ce marquage ouvrait la profondeur et coûtait un quart
  de but ; avec le reste, il en enlève un tiers.
- **Un homme sur le ballon, pas deux** (`PORTEUR_COUVERT`) : le marqueur
  du porteur ne double plus le presseur, il couvre à quatre mètres
  derrière. Avant, deux hommes sur le ballon et personne dans l'axe
  (zéro défenseur dans le cône ballon-but au tir ; réel : un).
- **Un défenseur posé dans sa surface tend la jambe** (`PORTEE_SURFACE`) :
  une passe qui file à moins de quatre-vingt-dix centimètres de lui est
  coupée (cinquante ailleurs).
- **On centre moins** (`CENTRE_BASE`) : quarante centres par match, c'est
  le double du réel ; vingt et un maintenant.
- **La frappe de loin** (`TIR_LOIN`, `TIR_LOIN_PRESSION`,
  `TIR_LOIN_AXE`) : entre vingt et trente-deux mètres, l'axe entrouvert
  et le vis-à-vis à plus de deux mètres et demi, on tente — et la
  pénalité « frappe pour rien » ne s'applique pas. Avant, la frappe de
  loin ne gagnait jamais contre une passe (un tir sur huit hors de la
  surface) ; un sur trois maintenant, comme en vrai.

Ce qui reste : le tireur est plus libre qu'en vrai (2,8 m contre 1,9 ;
un défenseur dans le cône ballon-but au tir en vrai, zéro ici) — le bloc
réel donne la frappe de loin mais un homme sort dessus au moment où elle
part. Et l'attaque ne passe presque plus dans la surface par une passe
(14 tentées, réel 35) : elle y entre en conduite ou frappe de loin.

Ce qui est essayé et rendu : le presseur qui ferme à deux mètres au
lieu de un mètre vingt aux abords de la surface (`CONTIENT_SURFACE`) —
plus près du réel sur le papier, mais le porteur entre alors dans la
surface en marchant (21 conduites par match au lieu de 12).

Banc retenu, 36 matchs : 2,6 buts, 25,5 tirs (le moteur d'avant ce
chantier : 3,2 et 24 sur les mêmes graines ; cible 2,8 et 25).

### Ce que cette défense permet de rallumer

Sur cette défense, les règles parquées au § 11 et au § 12 ont été
réessayées une à une, sur 36 matchs chacune (le banc de référence est
2,6 buts, 25,5 tirs) :

| règle | seule | avant la défense de la surface |
|---|---|---|
| la tête comme une passe (`TETE_REMISE`) | 3,0 buts, 29 tirs | +1 but |
| le contrôle à la poitrine (`CONTROLE_POITRINE`) | 3,05, 28 | +0,4 |
| le lob court qui retombe bas (`LOB_BAS`) | 3,1, 28 | +1,5 |
| la garde à 2 + 2 s (`GARDE`) | 2,75, 28 | — |
| la garde réelle à 1,5 + 1,6 s | 3,25, 31 | 4,8 buts |
| tête + poitrine | 2,86, 32 | |
| tête + poitrine + lob | 3,2, 32,5 | |
| tête + poitrine + garde 2 + 2 | 3,1, 34 | |

**Rallumées** : la tête comme une passe et le contrôle à la poitrine.
Les buts restent à la cible (2,9), les têtes perdues passent de 69 à 49
par match, les passes par possession de 4,7 à 5,1 (réel 6,7). **Encore
parqués** : le lob court (+0,35 but par-dessus les deux autres) et la
garde plus courte — une garde à deux secondes fait 250 possessions par
match au lieu de 228 (réel 165) : le porteur lâche plus vite, il perd
plus, ce n'est pas le tempo réel, c'est de la précipitation. Le tempo
réel viendra de possessions qui durent, pas d'une garde plus courte.

Le prix, à dire : 32 tirs par match au lieu de 25 (réel 24), à la même
conversion. Les possessions prolongées par la tête et le contrôle
arrivent au tir plus souvent qu'en vrai (33 % des possessions de dix
passes et plus, réel 20 %), parce qu'une passe dans la surface passe
encore sept fois sur dix (réel une sur deux) — les leviers essayés dessus
(le marqueur qui souffle la passe à 4,5 m, la jambe tendue à 1,2 m, moins
de frappes de loin, un plancher d'xG) n'y changent rien sur 36 matchs.
C'est le prochain trou défensif : la passe dans la surface. Le tempo (§ 11) et les trois règles parquées
des ballons perdus (§ 12) peuvent maintenant se réessayer sur cette
défense.

## 9. Pour les équipes fantasy

Les principes sont les mêmes pour toutes les équipes. Ce qui varie :
la consigne du manager (bloc haut, médian, bas : la hauteur de ligne et
les probabilités de vague et de contre-pressing) et les joueurs (l'envie
de presser des attaquants et des milieux, lue sur leurs cartes, module
ces probabilités ; leur vitesse et leur endurance décident si la vague
arrive à temps). Une équipe de presseurs avec un manager qui demande un
bloc haut pressera comme Liverpool ; la même consigne avec des
attaquants qui ne courent pas donnera un bloc haut qui ne mord pas.

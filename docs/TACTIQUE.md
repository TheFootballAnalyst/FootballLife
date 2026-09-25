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
Mais la première cause des tirs en trop n'était pas défensive, c'était le
temps de jeu effectif (§ 14). Le tempo (§ 11) et les trois règles parquées
des ballons perdus (§ 12) peuvent maintenant se réessayer sur cette
défense.

## 14. Le temps de jeu effectif

Le prix du § 13 (32 tirs par match) a d'abord une cause simple : le
moteur jouait **70 minutes de ballon vivant** en 90. Un match réel dure
97 minutes (temps additionnel compris, sur 40 matchs de club) et n'a le
ballon vivant que 55 à 58 minutes : 32 touches, 22 coups francs, 14
sorties de but, 10 corners, 9 remplacements et 3 arrêts pour blessure
par match, et chacun prend son temps (une touche 15 à 20 s, une sortie
de but 25 à 30, un corner 35, un coup franc 30). Le moteur reprenait une
touche en 9 s, une sortie de but en 14, un corner en 22. Vingt pour cent
de ballon vivant en trop, c'est vingt pour cent de passes, de
possessions et de tirs en trop — à jeu égal.

Ce qui est fait : les délais de reprise sont des constantes (`DELAIS` :
touche 16 s, sortie de but 26, corner 32, coup franc 28, relance du
gardien 9), mesurés par `effectif.py` dans le bac à sable :

| par match | réel | moteur avant | moteur après |
|---|---|---|---|
| ballon vivant | 55 à 58 min | 69,6 min | 60,5 min |
| passes | ~900 | 1156 | 1032 |
| possessions | 165 | 228 | 205 |
| tirs | 24 | 32 | 27,4 |
| buts | 2,8 | 2,86 | 2,83 |

Banc de 36 matchs, avec la tête comme une passe et le contrôle à la
poitrine rallumés : 2,8 buts, 27 tirs (cible 2,8 et 25). Le moteur ne
joue pas de temps additionnel (le compteur s'arrête à 90) : les délais
sont donc un peu plus courts que les réels pour tenir dans les 90
minutes. Il reste deux minutes de ballon vivant en trop, et le moteur a
moins de touches (18 contre 32 : on vise moins la ligne depuis le § 12)
et moins de corners (7 contre 10).

## 15. Le temps additionnel

Un match réel ne dure pas 90 minutes : 97 en moyenne (200 matchs de
club), 2 minutes ajoutées en première période, 4 en seconde. Ce que
l'arbitre affiche se lit sur les faits de la période :

| | première période | seconde période |
|---|---|---|
| additionnel moyen | 2,1 min (p10 0, p90 4) | 4,2 min (p10 2, p90 6) |
| régression sur les faits | 0,4 + 0,9 par remplacement + 0,2 par but + 0,3 par blessure + 0,4 par carton | 3,5 de base (les remplacements de tout le monde compris) + 0,25 par blessure + 0,2 par carton |

Ce qui est fait, dans les deux moteurs (`simulation.additionnel`, la
même règle reprise par `emergent`) : à la 45e et à la 90e, l'arbitre
affiche base + remplacements + buts + blessures + cartons, en minutes
entières (1 à 6 en première, 2 à 8 en seconde), avec une demi-minute
d'humeur. Le match se joue jusqu'à 45 + n puis 90 + n, l'horloge affiche
« 45+2 », « 90+4 », et l'écran de match annonce le panneau (« 3 minutes
de temps additionnel »). La minute d'un joueur reste lue sur 90 (un match
entier vaut 90, comme les stats par 90).

Pour le joueur devant son écran, le rythme ne change pas : une minute de
match vaut toujours `durée / 90` secondes réelles, et le match dure donc
un peu plus longtemps — six minutes et demie au lieu de six pour un
match classé, comme une vraie soirée déborde de l'heure prévue. La
causerie se donne à la vraie mi-temps (45 + n), et le match n'est fini
que quand la feuille le dit, pas quand l'horloge passe 90.

Avec le temps additionnel, les délais de reprise du moteur B (§ 14) sont
remontés à leur vraie valeur (touche 24 s, sortie de but 36, corner 45,
coup franc 40, but 60 : plus longs que les vrais un par un, parce que le
moteur a moins d'arrêts — 21 touches contre 32) : 94,5 minutes de match,
57,4 de ballon vivant (réel 55 à 58 sur 97).

## 16. Le repli, et la frappe

Deux réglages venus du bac à sable, mesurés à la même règle.

**Le repli.** « Les latéraux suivent le ballon jusqu'à l'autre bout du
terrain en phase défensive. » Mesuré (`outils/lateraux_moteur.py` :
la position de chaque latéral sans ballon, toutes les demi-secondes) :
5,6 % du temps un latéral est à plus de dix-huit mètres devant sa ligne
ou de l'autre côté de l'axe, presque toujours en rôle de forme, en
transit vers sa place — parce qu'un joueur de forme revenait à 3,3 m/s,
le trot de la forme, pendant que le ballon traversait le terrain. Sans
le ballon, loin de sa place et devant elle, on revient maintenant en
sprint (`REPLI_SPRINT`, 7 m/s), et un défenseur ne coupe pas une ligne
de passe à plus de douze mètres devant sa ligne (c'est un milieu qui
coupe, comme c'est un milieu qui presse là-haut). Après : 3,7 % du
temps, et les épisodes de trois secondes et plus passent de huit à trois
par match ; ceux qui restent sont des retours d'un latéral pris haut à
la perte, ce qui est du football.

Le prix : une défense qui revient en sprint encaisse moins sur les
transitions — 2,2 buts par match au lieu de 2,75 sur 36 matchs, et 22
tirs. Ce qui a mis en lumière un autre écart.

**La frappe.** L'issue des tirs, sur 150 matchs réels et 36 du moteur :

| | réel | moteur avant | moteur après |
|---|---|---|---|
| but | 12 % | 4 à 7 % | 10 à 13 % |
| arrêté par le gardien | 27 % | 18 % | 20 % |
| contré par un défenseur | 25 % | 8 % | 28 % |
| à côté ou par-dessus | 34 % | 70 % | 45 % |
| tirs cadrés par match | 8,5 | 5 | 6,5 à 7 |

Sept frappes sur dix partaient à côté (réel : une sur trois), et une sur
douze était contrée (réel : une sur quatre). L'erreur d'angle d'une
frappe (`TIR_SIGMA`, en degrés : base, manque de finition, pression,
distance) passe de 13/14/7/0,35 à 7/9/4,5/0,22, et un défenseur sur la
trajectoire la contre deux fois sur trois à deux mètres (`CONTRE_TIR`).
L'erreur de hauteur (`TIR_HAUTEUR`) est une constante aussi, laissée en
place.

Ce réglage-là ne se tranche pas sur 36 matchs : le même code y donne
de 2,3 à 3,5 buts selon la graine. Sur 72 matchs, les deux réglages
voisins encadrent la cible : 8/10/5/0,25 donne 2,6 buts (± 0,2), 23
tirs, 6,5 cadrés ; 6/8/4/0,2 donne 3,1 (± 0,3), 24 tirs, 7 cadrés. Le
réglage retenu est entre les deux. Il reste un tir sur deux à côté
(réel : un sur trois) et 7 cadrés par match (réel 8,5) : la hauteur des
frappes (`TIR_HAUTEUR`) est le prochain levier, à régler sur un banc de
72 matchs au moins.

## 17. Qui court : le travail sans ballon lu sur les cartes

« Vinícius et Mbappé courent partout, alors qu'en vrai ils attendent
devant ; c'est une grande différence avec Kvaratskhelia, Dembélé et
Doué. » La donnée existe depuis longtemps dans le dépôt
(`moteur/travail_sans_ballon.csv`, mesures FotMob de Ligue des champions
pour 544 joueurs, estimation EA pour les autres) et l'importeur la range
en rang parmi les joueurs du même poste :

| | volume de course | pressing | récupération | distance réelle / 90 | sprints / 90 |
|---|---|---|---|---|---|
| Mbappé | 0,02 | 0,66 | 0,01 | 9,0 km | 10 |
| Vinícius | 0,03 | 0,99 | 0,15 | 9,6 km | 17 |
| Barcola | 0,04 | 0,98 | — | 9,8 km | 16 |
| Kvaratskhelia | 0,22 | 0,92 | 0,45 | 10,3 km | 13 |
| Doué | 0,96 | 0,91 | 0,84 | 11,5 km | 14 |

**Le bug.** La fiche physique réduite pour le match
(`simulation.physique_match`) ne gardait que vitesse, endurance et
force : les trois leviers n'arrivaient jamais au moteur, tout le monde
jouait à 0,5. Corrigé — et c'est le lien direct avec les équipes
fantasy : la carte porte les leviers, le moteur les lit.

**Où partaient les mètres.** Mesuré rôle par rôle (`outils/roles_course.py`) : les 12,6 km de Barcola, c'était 2,4 km en
presseur, 1,2 en doublage, 0,8 en coupe — il suivait le porteur, il
redoublait, il coupait les lignes, comme Doué. Puis, ces rôles fermés,
1,2 km de forme en bloc médian devenaient 2,1 : sa place suivait le
ballon à la trace et il la suivait au pas.

**Ce qui est fait**, tout au volume de course de la carte :

- le repli en sprint (§ 16) se fait à la mesure du volume
  (`REPLI_VOLUME`) : Doué rentre à 7 m/s, Mbappé à 4,5 et reste devant ;
- un attaquant qui court peu attend plus haut (`AILIER_VOLUME`), et sa
  place sans ballon est ancrée à quarante-deux mètres de son but
  (`ANCRE_X`, `ANCRE_VOLUME`) : elle ne suit la ligne et ne coulisse avec
  le ballon qu'à 40 % + 60 % × volume ;
- le pressing se fait par à-coups : un presseur garde le ballon 2 s + 4 s
  × volume puis souffle quatre secondes (`PRESSE_DUREE`, `PRESSE_REPOS`),
  et un joueur qui court peu ne presse pas à plus de douze mètres
  (`PRESSE_ZONE`) — Vinícius jaillit, il ne suit pas ;
- sous 0,35 de volume, un attaquant ne double pas et ne coupe pas
  (`DOUBLE_VOLUME`) ; le ballon libre va à celui qui court ;
- la zone morte d'un joueur de forme grandit avec son manque de volume
  (`INERTIE_VOLUME`) : il ne trottine pas pour un mètre de ballon.

**La règle de mesure**, `outils/course_moteur.py` : la distance de
chaque joueur dans le moteur contre sa mesure FotMob, et la part sans
ballon (4 matchs PSG–Real) :

| | réel | moteur avant | moteur après | dont sans ballon |
|---|---|---|---|---|
| Doué | 11,5 km | 12,9 | 13,3 | 6,8 |
| Vinícius | 9,6 | 10,2 à 12,6 | 10,5 | 4,4 |
| Barcola | 9,8 | 13,7 | 10,2 | 4,4 |
| Mbappé | 9,0 | 8,2 à 10,6 | 9,3 | 4,2 |
| Kvaratskhelia | 10,3 | 12,1 | 9,5 | 4,5 |
| Nuno Mendes | 9,5 | 12,2 | 11,4 | 5,2 |
| corrélation moteur–réel, les 22 | | 0,86 | 0,89 | |

Le pressing par à-coups ne lâche que si un coéquipier peut prendre le
relais à moins de quatorze mètres (`PRESSE_RELEVE`), et la zone morte
d'un milieu est la moitié de celle d'un attaquant : sans ça, un milieu
à faible volume devenait un passager. Banc de 72 matchs : 3,1 buts
(± 0,1), 26 tirs, 7 cadrés — un demi-but de plus qu'avant ce chantier
avec la même frappe (8/10/5/0,25), parce que beaucoup d'attaquants
réels pressent et doublent moins que le 0,5 partout d'avant. C'est le
vrai monde qui entre, pas un réglage ; la cible de 2,8 se rattrapera sur
la frappe ou la surface, mesuré sur 72 matchs.

Ce qui reste : les centraux courent trop peu (Hakimi 7,9 contre 10,8,
Pacho 6,8 contre 9,5) et le gardien presque pas (0,8 km contre 5) —
la ligne bouge d'un bloc, sans les allers-retours d'un vrai central ;
c'est un autre chantier.

## 18. Les centraux et le gardien : la défense restante

Les centraux couraient 7 à 8 km (réel 9,2 à 9,8) et le gardien 0,8
(réel 5,1). Mesuré à chaque passe de l'équipe en possession, en réel
(positions 360, 100 matchs) et dans le moteur (`outils/arriere_ref.py`,
`outils/arriere_moteur.py`) :

| | réel | moteur avant | moteur après |
|---|---|---|---|
| gardien sans ballon, ballon à 15-30 m de son but | 3,2 m devant sa ligne | 2,3 | 4,8 |
| ... ballon à 30-45 m | 4,9 | 3,3 | 7,3 |
| ... ballon à 45-60 m | 7,7 | 4,3 | 10,1 |
| ... ballon à 60-75 m | 13,1 | 4,8 | 12,6 |
| gardien avec le ballon, ballon à 15-30 m | 5,5 | 2,2 | 6,4 |
| ... ballon à 30-45 m | 7,9 | 3,1 | 9,1 |
| les deux plus bas de l'attaque suivent le ballon en largeur à | 0,22 | 0,11 | 0,15 |
| ... et en profondeur à | 0,43 | 0,43 | 0,45 |

Le gardien réel n'est pas sur sa ligne : il est à cinq mètres quand le
ballon est au milieu de son camp, à treize quand il est dans l'autre
camp, et plus loin encore quand son équipe a le ballon (le gardien
libéro). Le moteur le laissait à cinq mètres au plus. Les deux plus bas
de l'équipe en possession (les centraux, quand la caméra les voit :
c'est la limite des positions 360, un central hors champ n'est pas
compté, d'où des chiffres à lire comme un plancher) sont six à neuf
mètres derrière le ballon ; le moteur les gardait à quinze en
progression et à trente-huit sur une attaque de la surface.

Ce qui est fait : le gardien sort à la mesure de la distance du ballon
(`GARDIEN_SORTIE` : 0,5 m + 0,18 par mètre sans ballon, 2,5 m de base
avec, plafond seize) et coulisse en largeur avec lui (`GARDIEN_LARGEUR`) ;
la défense restante joue à onze mètres derrière le ballon en progression
(`RESTANTE_RECUL`, quinze avant), à cinquante-six mètres sur une attaque
de la surface (`RESTANTE_FINITION`, cinquante-deux avant), et coulisse
avec le ballon à 0,25 (`RESTANTE_GLISSE`, 0,1 à 0,2 avant).

Mesuré (`outils/course_moteur.py`, 4 matchs) : les centraux passent de
6,8-7,6 km à 7,8-8,6 (réel 9,2 à 9,8), le gardien de 0,8 à 3,7 (réel
5,1). Banc de 72 matchs : 3,2 buts (± 0,2), 27,6 tirs, 7,7 cadrés —
comme avant ce chantier au bruit près (3,1 ± 0,1) : un gardien qui sort
et une défense restante plus haute ne coûtent pas de buts. Ce qui manque encore aux centraux, c'est ce que la
caméra ne montre pas et que le moteur ne fait pas : les pas de côté
permanents d'un central en construction, qui ne sont pas des courses.

## 19. Le style d'un club, et ce que ses joueurs en gardent

« Quand je lance un PSG–Real, Madrid domine en possession. » Mesuré :
44 % pour Paris avec les réglages par défaut, parce qu'ils étaient les
mêmes des deux côtés (tempo équilibré, bloc médian) et que le onze du
Real passe mieux carte par carte (passe 73 contre 67) — le style ne
jouait pas.

**La tactique par défaut vient de la possession réelle.** La part des
touches de balle d'un club sur ses matchs de la saison suit sa
possession (`possession_club`) : Barcelone 0,64, Paris 0,63, Bayern
0,61, City 0,59, Real 0,56, Liverpool 0,56, Lorient 0,48, Albacete 0,34
(253 clubs : médiane 0,49, p90 0,55, p10 0,43). Au-dessus de 0,55 un
club joue en possession, relance courte, bloc haut à partir de 0,58 ;
en dessous de 0,44 il joue direct, relance longue, bloc bas sous 0,42 ;
entre les deux, équilibré (`profil_tactique`, `STYLE_SEUILS`). Le bac
pose ce profil à l'ouverture et à chaque changement de club, on le
change à la main si on veut.

**L'affinité au style.** Le collectif d'un onze doit avantager sa façon
de jouer, et pas une science exacte : chaque joueur garde le style de
son club réel. Un onze qui joue en possession avec des joueurs de clubs
de possession a de l'affinité (`affinite_style`, 0 à 1 : la part des
joueurs venant d'un club typé comme le tempo demandé, chacun à la mesure
de son club) ; un onze qui joue direct avec des joueurs de clubs directs
aussi. Le onze du PSG a 0,85 d'affinité avec la possession, celui du
Real 0,42 ; ni l'un ni l'autre n'en ont avec le jeu direct. Ce que ça
donne dans le moteur (`AFFINITE`, 0,3 de chaque côté) : en possession,
les passes se ratent moins et le porteur se précipite moins ; en direct,
la longue part plus droite et les courses de contre partent plus. Rien
en tempo équilibré. Pour une équipe fantasy, c'est la même règle : des
cartes du PSG, de Barcelone et du Bayern dans un onze qui joue en
possession se comprennent ; des cartes de Walsall et d'Albacete dans un
onze direct aussi.

Mesuré sur quatre PSG–Real, chacun avec son profil : possession de
Paris 56 % (44 avant), 505 à 539 passes contre 418 à 475. Le banc de
référence ne bouge pas (il joue tous les clubs en équilibré, sans
affinité). Ce qui reste : la possession réelle ne dit pas le bloc — un
club de possession ne presse pas forcément haut — ; la hauteur mesurée
en 360 (§ 1) ne couvre que quelques clubs, on prend donc la possession
comme lecture unique, à corriger à la main au besoin.

## 20. Les attaquants qui redescendent trop, le latéral aspiré à la touche

Deux observations du bac. « Doué et Dembélé courent partout, ils
redescendent trop défendre » ; « les latéraux sont parfois aspirés vers
la touche pendant que leur vis-à-vis prend l'intérieur ».

**Les attaquants.** Mesuré (`outils/ailiers_touche.py`,
la profondeur de chaque attaquant devant sa ligne sans ballon, et ses
rôles) : Doué était à moins de douze mètres de la ligne 30 % du temps
(les autres attaquants 7 à 15 %), et n'était en forme que 42 % du temps
— presseur 26 %, coupeur 17 %, doubleur 14 %. Un attaquant travailleur
faisait tout le travail d'un milieu. Ce qui est fait : un attaquant,
même travailleur, ne presse pas loin de lui (`ATTAQUANT_LOIN` : au-delà
de douze mètres, c'est le milieu), ne coupe une ligne qu'à moins de dix
mètres du ballon (`COUPE_ATTAQUANT`), ne redouble son latéral que sur un
couloir attaqué à moins de trente-deux mètres du but
(`DOUBLE_PROFONDEUR`), et la place d'un ailier devant la ligne monte de
deux mètres en bloc bas comme en bloc médian (`AILIER_BLOC`). Après :
Doué à moins de douze mètres 19 % du temps, en forme 69 %, et 11,4 km
par match (réel 11,5 ; 13,3 avant).

**Le latéral à la touche.** Mesuré : un latéral sans ballon est collé à
la touche (à moins de sept mètres) sans vis-à-vis à moins de huit mètres
pendant qu'un adversaire est à l'intérieur 6,4 % du temps. Deux cas sur
trois sont un latéral qui revient d'une position large en attaque (c'est
la course de retour, pas une aspiration) ; le tiers restant avait
vraiment sa place à la touche, parce que le bloc coulisse avec le ballon
et qu'un latéral à seize mètres de l'axe plus le coulissement finissait
à quatre mètres de la touche. Ce qui est fait : la place d'un latéral
sans ballon ne dépasse jamais vingt-cinq mètres de l'axe
(`LATERAL_EXT_MAX` : le bloc fait trente-cinq mètres de large, § 2), il
n'est pas plus large que son vis-à-vis à quatre mètres près
(`LATERAL_MARGE`, six avant) parmi les attaquants à moins de quinze
mètres de lui en profondeur (`LATERAL_VIS_X`, vingt-cinq avant : un
latéral adverse resté derrière le justifiait). Après : 5,0 % du temps,
dont les trois quarts en course de retour. Banc de 72 matchs : 2,9 buts
(± 0,2), 29 tirs, 8,8 cadrés (3,2 et 27,6 avant : des attaquants qui
pressent moins loin laissent plus de tirs, mais pas plus de buts).

## 21. Quatre détails du bac

- **La touche est au latéral.** Le plus proche la jouait ; c'est le
  latéral du côté qui la joue, sauf une touche sur six, rapide, par le
  plus proche (`TOUCHE_LATERAL`). Mesuré : 18 touches sur 18 par un
  latéral sur un match, 15 sur 20 sur un autre.
- **L'avant-centre n'est jamais sous le pivot.** Mbappé se retrouvait
  plus bas que Tchouaméni : sa place sans ballon suivait le ballon
  (« derrière le ballon » l'emportait sur tout). Elle reste au moins
  six mètres devant le pivot (`BUTEUR_DEVANT`), et en bloc bas
  l'avant-centre se place à seize mètres devant la ligne au lieu de
  quinze, sans plus jamais descendre à deux mètres du ballon. Mesuré :
  Mbappé sous son pivot 5 % du temps sans ballon (en course de retour),
  à moins de douze mètres de sa ligne 4 % (9 à 13 avant) ; 8,7 km (réel
  9,0).
- **Personne dans la surface sur une sortie de but** — ni quand le
  gardien a le ballon en main. La règle existait, mais la zone morte
  d'un attaquant qui court peu (§ 17, jusqu'à huit mètres) le laissait
  planté dans la surface « à moins de huit mètres de sa place ». À
  l'arrêt, plus de zone morte, et on sort de la surface en trottinant.
  Mesuré : quatre secondes après l'arrêt, un adversaire dans la surface
  sur 3 % des images (tous en train d'en sortir, aucun après six
  secondes) ; zéro sur une relance du gardien.
- **Dembélé (et Doué) redescendent moins** : la place d'un ailier en
  bloc bas monte à douze mètres devant la ligne (`AILIER_BLOC`), et
  l'avant-centre a son plancher.

Banc de 72 matchs : 3,0 buts (± 0,2), 30 tirs, 8 cadrés (2,9 avant, au
bruit près).

## 22. Le poids du collectif

« Une équipe bien construite doit être mieux récompensée qu'une somme
d'individualités ; un PSG est bien au-dessus d'un Real, mais un Real
peut battre un collectif comme l'Inter grâce à ses individualités. »

**Avant, le collectif ne pesait rien.** Mesuré sur huit PSG–Real (les
vraies valeurs 0,95 et 0,35, puis 0,5 partout, puis inversées) : aucun
ordre, le bruit domine. Le collectif touchait le bruit des décisions, le
troisième homme, la valeur d'une passe dangereuse — pas ce qui décide
d'un match.

**Le modèle.** Le collectif joue sur les attributs *collectifs* de
chaque joueur : la passe, le contrôle, la lecture défensive
(`COLLECTIF_ATTRIBUTS`). Un onze rodé joue comme si ses passeurs et ses
défenseurs avaient quelques points de plus ; une somme d'individualités,
quelques points de moins. La finition, le dribble, la vitesse et le
gardien restent ce qu'ils sont : c'est là que les individualités
gagnent, et c'est pourquoi un Real peut battre un Inter. L'échelle
(`COLLECTIF_OVR`, 20) : un collectif à 1 vaut dix points sur ces
attributs, à 0 il en retire dix ; 0,95 donne +9, 0,35 donne −3. À côté,
trois petits leviers directs : la passe se rate moins, les appels
partent au bon moment, le marqueur anticipe et le contre-pressing prend
(`COLLECTIF_PASSE`, `COLLECTIF_APPEL`, `COLLECTIF_BLOC`) ; et un seul
curseur pour tout (`COLLECTIF_POIDS`, 0 : que des individualités).

**Mesuré**, 24 matchs par ligne, dans la base de démo (le onze du PSG y
vaut 80,5 d'OVR, celui du Real 87,6, celui de l'Inter 80,4) :

| | buts | xG | V-N-D |
|---|---|---|---|
| PSG–Real, collectif 0,5 partout (que l'OVR : −7 pour Paris) | −0,75 | −0,27 | 7-3-14 |
| PSG–Real, 0,95 / 0,35, avant ce chantier | −1,00 | −1,06 | 5-2-17 |
| PSG–Real, 0,95 / 0,35, échelle 12 | −0,54 | −0,29 | 6-10-8 |
| PSG–Real, 0,95 / 0,35, échelle 20 | −0,58 | −0,36 | 8-6-10 |
| Real–Inter, 0,35 / 0,85, échelle 12 | +1,96 | +0,91 | 17-5-2 |
| Real–Inter, 0,35 / 0,85, échelle 20 | +1,12 | +0,68 | 15-3-6 |

Avec l'échelle 20, un Paris à sept points d'OVR de moins fait jeu égal
avec le Real grâce à son collectif (8-6-10 au lieu de 5-2-17), et le
Real bat encore un Inter rodé de sept points de moins grâce à ses
individualités (15-3-6 au lieu de 17-5-2). C'est le monde que tu
décris. Dans ta base, où le onze du PSG vaut plus que 80,5, Paris sera
au-dessus. Confirmé sur 48 PSG–Real à l'échelle 20 : −0,19 but, 17-12-19
(sept points d'OVR de moins, jeu égal). Le banc général reste à 3,0 buts.

**Ce que le collectif vaut, mesuré au miroir** (le Real contre
lui-même, onze identique, 0,95 contre 0,35) : +0,45 but par match sur
96 matchs, +0,34 sur 24 autres. Un écart de collectif de 0,6 vaut donc
trois à quatre points d'OVR, pas plus, et pousser l'échelle à 30 ou 40
n'y change rien (PSG–Real reste à −0,6 et −0,75) : les attributs
collectifs saturent, et le moteur tranche les matchs par la finition,
le dribble et la vitesse — ce que le modèle laisse aux individualités,
par principe. Un levier direct à la frappe (`COLLECTIF_TIR` : un bloc
rodé arrive sur le tireur un pas plus tôt) a été essayé : +0,2 au miroir
mais −0,45 sur PSG–Real, dans le bruit ; parqué à 0.

**Attention à la base sur laquelle on mesure.** Les tableaux ci-dessus
ont été faits sur une base de démo amorcée sur les journées 1 à 25
(Dembélé à 83, Paris à 80,5 d'OVR, le Real à 87,6). Amorcée sur la
saison entière, comme le jeu le fait maintenant (`web/app/demo.py
--amorce tout`), Paris vaut 87,4 (Dembélé 98, Kvaratskhelia 92, Mendes
91), le Real 83,9 (Mbappé 96, Bellingham 90), l'Inter 78,9. Rejoué sur
cette base, en xG (moins bruité que les buts : sur 48 matchs, ± 0,15
contre ± 0,35) :

| | xG | buts | V-N-D |
|---|---|---|---|
| PSG–Real, 0,95 / 0,35, collectif branché (48 matchs) | +0,61 | −0,11 | 18-12-18 |
| PSG–Real, 0,95 / 0,35, collectif à 0, que les cartes (24) | +0,10 | +0,54 | 11-5-8 |
| PSG–Real, 0,5 / 0,5 (24) | +0,49 | +0,16 | 12-4-8 |
| Real–Inter, 0,35 / 0,85 (24) | −0,44 | −0,21 | 9-2-13 |

Le collectif ajoute environ un demi-xG par match à Paris pour 0,6
d'écart, et un Inter à 0,85 crée plus qu'un Real à 0,35 malgré cinq
points d'OVR de moins. Les buts, eux, suivent l'xG au long cours mais
pas sur 24 matchs : c'est le bruit du football, pas un réglage. Dans la
base, l'Inter n'est pas un collectif haut (0,34 mesuré) : pour qu'il le
soit, une ligne dans `jeu/collectif_manuel.json`.
Le banc général sur cette base : 2,8 buts, 30 tirs, 7,6 cadrés.

Pour une équipe fantasy, le collectif est la cohésion mesurée (les
minutes jouées ensemble en vrai) : un onze de onze clubs différents part
vers 0, soit −10 sur la passe, le contrôle et la défense ; un onze pris
dans un même club rodé part vers 0,9. C'est la récompense de l'équipe
construite. Reste à décider si le jeu doit faire monter cette cohésion
avec les matchs joués ensemble dans le jeu — c'est un chantier à part.

## 23. D'où viennent les buts

**La question de départ.** Le collectif (§ 22) ajoutait un demi-xG à
Paris contre le Real mais presque pas de buts. Pour comprendre, une
règle sur la finition : conversion des tirs selon la distance et la
pression (le défenseur le plus proche dans la freeze frame 360), réel
(150 matchs, tirs de jeu ouvert) contre moteur (24 PSG–Real).

| tirs par match (les deux équipes) | réel <1,5 m / 1,5-3 m / >3 m | moteur avant |
|---|---|---|
| 0-11 m | 4,0 / 1,8 / 1,1 | 1,2 / 1,4 / 1,0 |
| 11-18 m | 3,3 / 4,1 / 1,8 | 3,5 / 8,5 / 8,7 |
| 18 m et plus | 1,6 / 3,2 / 3,4 | 0,0 / 1,5 / 7,8 |

Le moteur ne convertissait pas mieux que le réel à pression égale
(0-11 m libre : 35 % contre 41 %) : il prenait **deux fois trop de tirs
de 11-18 m**, et huit par match sans défenseur à trois mètres (réel
1,8). Et une seconde règle, l'origine des tirs (le key pass StatsBomb ;
dans le moteur, le dernier événement de l'équipe avant la frappe) :

| par match | réel : tirs (buts) | moteur avant |
|---|---|---|
| 0-11 m | 7,2 (1,86) | 4,6 (0,67) |
| 11-18 m | 9,3 (1,04) | 19,5 (2,25) |
| 18 m et plus | 9,4 (0,33) | 8,2 (0,67) |
| sur centre | 3,3 (0,55), 37 % de la tête | 4,4 (0,25), 62 % de la tête |
| sans passe (dribble, rebond, récupération) | 5,0 (0,71) | 14,4 (1,75) |
| corner | 1,5 (0,13) | — |

**58 % des vrais buts viennent de moins de onze mètres ; 63 % des buts
du moteur venaient de 11-18 m.** Voilà pourquoi le collectif ne mordait
pas : les buts du moteur se prenaient dans une zone que le bloc ne
défendait pas.

**Le trou.** Les instantanés au moment de ces frappes libres montrent
toujours la même image : le tireur reçoit entre les lignes à 12-16 m,
la ligne défensive est à **7 m** du but, son marqueur ne peut pas
sortir de plus de 2,5 m au-dessus de la ligne, et le presseur arrive
dans son dos. La ligne était à 7 m parce que la droite « 0,75 × ballon
− 6 » (§ 1) est une moyenne sur tout le terrain : près du but elle sous-
estime la vraie ligne de cinq à six mètres (réel : ballon à 10 m, ligne
à 8 ; à 20, 14 ; à 30, 19 — la droite donne 1,5 / 9 / 16,5).

**Ce qui change.**

1. **La ligne près du but** (`LIGNE_PRES`) : un second segment, 0,55 ×
   ballon + 2,5, et la ligne prend le plus haut des deux. Mesurée après :
   ballon à 20 m, ligne à 15 (réel 14) ; à 30, 18 (19) ; à 40, 25 (25).
2. **Le marqueur ferme la frappe** (`PORTEUR_PRESSE`, `PORTEUR_FERME`) :
   le marqueur du porteur ne reste à quatre mètres derrière (§ 13) que si
   le presseur est vraiment dessus (à moins de 2,5 m, pas plus d'un mètre
   dans son dos) ; sinon, à moins de 22 m du but, il sort à un mètre.
3. **Le centre bas** (`CENTRE_FOND`, `CENTRE_BAS`, `CENTRE_BAS_ZONE`,
   `CENTRE_BAS_PORTEE`, `CENTRE_BAS_TIR`) : réel, 41 % des centres sont
   au sol ou tendus, et c'est là que ça marque (22 % de conversion contre
   11 % de la tête). Depuis le fond (à moins de douze mètres de la ligne
   de but), sept centres sur dix sont remis en retrait, au sol, vers le
   coéquipier libre au point de penalty (à moins de 20 m du but, de 14 m
   de l'axe, à portée de 26 m) — et celui-ci frappe dans la foulée. Un
   corner, un coup franc restent en l'air. Mesuré : 8 centres bas par
   match, 44 % interceptés (réel : 58 % n'arrivent pas), 17 % suivis
   d'un tir dans les cinq secondes (réel 23 %).
4. **La tête** (`TETE_TIR`) : 16 m/s et 0,28 rad d'écart au lieu de 14
   et 0,34 — les têtes du moteur finissaient à 2-5 %, réel 10 %.
5. **L'envie de frapper** (`TIR_PROCHE`, `TIR_PRESSION`) : le bonus des
   dix-huit mètres passe de 0,3 à 0,15, la pression enlève 0,75 au lieu
   de 0,6. Choisi sur des bancs courts (six matchs, donc indicatifs) :
   (0,3 à 11 m / 0,9) tombait à 17 tirs par match, (0,15 / 0,75) restait
   à 25 tirs, le réel.

Vérifié en passant : l'écart entre les centraux n'est pas en cause
(moteur 4,7 à 6,7 m selon la position du ballon, réel 4,8 à 7,1 ; les
quatre défenseurs sur 17-21 m, réel 18-25).

**Mesuré après** (PSG–Real, 36 matchs pour l'origine, 24 pour la
pression) : 32 tirs, 3,4 buts ; 0-11 m 4,8 tirs (0,78 but), 11-18 m
18,4 (1,89), 18 m et plus 8,8 (0,69). Les tirs libres tombent un peu
(15,3 par match à plus de trois mètres, 17,4 avant) mais le profil du
match PSG–Real reste chargé en 11-18 m : ce sont surtout des **dribbles
suivis d'une frappe** (7,4 par match, réel 1,8) — le prochain chantier,
avec l'occupation de la surface (le moteur y prend 4,8 tirs, le réel
7,2). Le banc général (six équipes, 48 matchs, même graine avant et
après) : 2,52 buts, 25,9 tirs, 7,2 cadrés — contre 3,35 buts, 29,4 tirs,
8,2 cadrés avant (réel : 2,8 à 3,2 buts, 26 tirs). Le moteur marque
maintenant un peu moins que le réel plutôt qu'un peu plus ; les
lectures « banc général » des sections précédentes étaient des bancs de
six matchs (le second argument de `banc` est la graine, pas le nombre),
à prendre comme des ordres de grandeur.

**Et le collectif, maintenant** (PSG 0,95 contre Real 0,35, échelle 20,
base entière, 96 matchs par ligne, deux séries de 48) :

| | buts | xG | V-N-D |
|---|---|---|---|
| collectif branché | +0,79 et +0,52 (moy. +0,66) | +0,74 et +0,53 | 48-21-27 |
| collectif à 0, que les cartes | +0,40 et +0,15 (moy. +0,28) | +0,39 et +0,27 | 37-31-28 |

Avant ce chantier : +0,36 avec, +0,42 sans (§ 22). Maintenant que les
buts se prennent dans la surface, contre un bloc, le collectif compte
sur le score : il double l'écart de Paris. Le bruit reste ce qu'il est
(± 0,3 but sur 48 matchs), d'où deux séries par ligne.

Et l'autre exemple, Real (0,35, cinq points d'OVR de plus) contre un
Inter rodé (0,85, en manuel), 36 matchs : collectif branché, le Real
gagne encore, +0,42 but, 18-5-13, mais l'Inter crée autant que lui
(xG −0,12 pour le Real) ; sans collectif, +0,53 but, +0,73 xG, 17-10-9.
Les individualités du Real passent, le collectif de l'Inter lui coûte
près d'un xG par match — le monde décrit au § 22.

## 24. Les dribbles suivis d'une frappe, et la surface

**Deux règles de plus, réel contre moteur.** La première : ce que le
tireur faisait juste avant de frapper — la longueur de sa conduite
(StatsBomb : le *Carry* qui précède le tir ; moteur : la distance entre
la prise de balle et la frappe). La seconde : l'issue de chaque tir
(but, arrêt, contré, à côté) par distance.

| conduite avant le tir | réel | moteur avant | moteur après |
|---|---|---|---|
| médiane, tous tirs | 0,8 m | 1,6 m | 1,3 m |
| tirs après plus de 20 m de conduite | 1,0 / match | 7,3 / match | 3,9 / match |
| ... dont de 11-18 m | 0,45 | 4,3 | 2,5 |

**Ce que c'était.** Pas des dribbles : des **contres**. Les
instantanés montrent toujours la même chose : un ailier prend le ballon
à 40 m du but sur une perte adverse, avec les centraux à sa hauteur et
**immobiles** (la ligne « gelée » du contre-pressing, § 5, les tenait
sur place), puis il court trente mètres escorté par un presseur qui
« se repliait » à sept mètres et par des défenseurs qui reculaient à
pleine vitesse devant lui sans jamais l'affronter. Trois règles :

1. **Le gel casse** (`GEL_CASSE`) : la ligne haute du contre-pressing
   tient tant que le ballon est devant elle ; dès qu'un porteur adverse
   arrive à trois mètres de sa hauteur, elle redescend avec lui.
2. **Le défenseur rejoint chasse** (`CHASSE_DEBORDE`) : un défenseur
   que le porteur a rejoint à sa hauteur court côté but du porteur au
   lieu de rester planté ; et devant un porteur lancé, un défenseur
   côté but ne recule plus à pleine vitesse, il **temporise** à quatre
   mètres par seconde (`RECUL_FACE`) — le porteur arrive sur lui, et
   c'est le duel. Le repli après une perte haute temporise à trois
   mètres au lieu de sept (`REPLI_CONTIENT`), le marqueur d'un porteur
   lancé loin du but reste à deux mètres au lieu de quatre
   (`PORTEUR_TEMPORISE`), et un défenseur de la ligne sort sur le
   porteur lancé sans attendre le relais (`SORTIE_PORTEUR`).
3. Il en reste : 3,9 tirs par match après une longue conduite, dont la
   moitié partent d'une passe en progression vers un coureur déjà
   derrière la ligne. C'est le prochain pas, avec la course de
   récupération des centraux (ils rendent dix mètres sur trente au
   sprinteur, un vrai central en rend trois).

**La surface.** Sur un centre, le réel a 2,5 attaquants dans la surface
(quatre ou cinq une fois sur quatre) ; le moteur en avait 2,1 et jamais
plus de trois. L'avant-centre attaque les six mètres (`SURFACE_BUTEUR` :
onze mètres du but, quinze avant), l'ailier opposé le second poteau à
dix mètres (`SURFACE_POTEAU`), l'ailier côté ballon rentre au premier
poteau quand c'est le latéral qui centre du fond, et le relayeur opposé
arrive au bord de la surface en troisième homme (`SURFACE_TROISIEME`).
Mesuré : 2,7 attaquants dans la surface sur un centre. Les tirs de
moins de onze mètres passent de 4,8 à 6,4 par match sur PSG–Real (réel
7,2), pour 1,46 but (réel 1,86).

**L'issue des tirs**, la règle qui a tout changé. Réel (150 matchs) :

| | but | arrêt | contré | à côté ou poteau |
|---|---|---|---|---|
| réel 0-11 m | 23 % | 22 % | 15 % | 39 % |
| réel 11-18 m | 11 % | 29 % | 28 % | 32 % |
| réel 18 m et plus | 4 % | 27 % | 31 % | 39 % |
| moteur avant, 0-11 m | 24 % | 32 % | 12 % | 6 % (+ 26 % « récupérés ») |
| moteur avant, 11-18 m | 12 % | 24 % | 27 % | 14 % (+ 23 %) |
| moteur après, 0-11 m | 14 % | 23 % | 33 % | 30 % |
| moteur après, 11-18 m | 10 % | 28 % | 23 % | 40 % |
| moteur après, 18 m et plus | 3 % | 22 % | 16 % | 59 % |

Trois choses ne tenaient pas debout dans le moteur d'avant. **Un tir
sur cinq était « récupéré par la défense »** : un défenseur à moins
d'un mètre du ballon le ramassait au passage, comme une passe — une
frappe ne se ramasse pas, elle se contre ou elle file, et le contre se
juge maintenant à la distance au **segment parcouru** par le ballon
dans le tic (à 25 m/s il avance de 2,5 m par tic : le test au point
manquait un défenseur sur deux ; `CONTRE_TIR` à 1,2 m et 75 %). **Le
gardien « arrêtait » les frappes qui partaient à côté** : il les
touchait dans son rayon et la stat disait arrêt — il les laisse
filer (`_va_au_but`). Et un contre sur deux qui déviait au fond des
filets : un but contre son camp tous les deux matchs, réel un tous
les dix (`CONTRE_DEVIE_BUT`). Trois réglages autour : le gardien a
moins de temps de près et plus de loin (`GARDIEN_REACTION` : réel, 51 %
des tirs cadrés de moins de 11 m entrent, 28 % de 11-18, 13 % au-delà),
la qualité du gardien pèse moins sur le taux d'arrêt (`GARDIEN_ARRET` :
les gardiens moyens du banc encaissaient 15 % des tirs, réel 12,5 à
tous les niveaux), la tête se disperse comme en vrai (`TETE_TIR`), et
on ne frappe pas dans les jambes d'un défenseur dans l'axe
(`TIR_BOUCHE`).

**Le banc général** (six équipes tirées au sort, 48 matchs, graine 1) :
3,44 buts, 24,4 tirs, 9,2 cadrés — contre 2,52 / 25,9 / 7,2 avant ce
chantier et 3,35 / 29,4 / 8,2 avant le § 23 (réel : 2,9 à 3,2 buts,
26 tirs, 9,7 cadrés). Ce qui reste faux est dans le tableau : trop de
tirs contrés dans la surface (33 % contre 15) et trop de frappes de
loin à côté (59 % contre 39).

**Et le collectif, rejoué sur ce moteur** (PSG 0,95 contre Real 0,35,
échelle 20, deux séries de 48 matchs par ligne ; Real–Inter à 0,35 /
0,85 sur 36) :

| | buts | xG | V-N-D |
|---|---|---|---|
| PSG–Real, collectif branché | +0,77 et +0,62 (moy. +0,70) | +0,49 et +0,81 | 53-15-28 |
| PSG–Real, collectif à 0, que les cartes | −0,04 et +0,12 (moy. +0,04) | +0,30 et +0,09 | 33-32-31 |
| Real–Inter, collectif branché | +0,19 | −0,28 | 11-11-14 |
| Real–Inter, collectif à 0 | +0,36 | +0,24 | 17-10-9 |

Les cartes seules font maintenant jeu égal entre Paris et le Real
(trois points et demi d'OVR d'écart, dans le bruit de ± 0,3) ; c'est
le collectif qui fait gagner Paris, +0,7 but par match. Et le Real
garde le dessus sur un Inter rodé de cinq points de moins, de peu
(+0,19), en créant moins que lui.

## 9. Pour les équipes fantasy

Les principes sont les mêmes pour toutes les équipes. Ce qui varie :
la consigne du manager (bloc haut, médian, bas : la hauteur de ligne et
les probabilités de vague et de contre-pressing) et les joueurs (l'envie
de presser des attaquants et des milieux, lue sur leurs cartes, module
ces probabilités ; leur vitesse et leur endurance décident si la vague
arrive à temps). Une équipe de presseurs avec un manager qui demande un
bloc haut pressera comme Liverpool ; la même consigne avec des
attaquants qui ne courent pas donnera un bloc haut qui ne mord pas.
Et les cartes gardent le style de leur club (§ 19) : un onze de joueurs
de clubs de possession qui joue en possession se comprend.

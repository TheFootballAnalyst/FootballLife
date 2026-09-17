# Moteur B — un match qui se joue

Le moteur du jeu (`jeu/simulation.py`) tire un dé par minute, calibré sur
les distributions réelles de la saison, et raconte ce qu'il a tiré. Le
moteur B (`jeu/emergent.py`) ne tire rien d'avance : vingt-deux joueurs
ont une position, une vitesse, un profil physique (la fiche EA), six
attributs (la carte), et à chaque instant chacun décide — courir où,
passer à qui, frapper ou non — puis exécute avec une précision qui
dépend de ses attributs. Le ballon a sa physique. Un but est un ballon
qui a franchi la ligne.

**Il est un bac à sable.** Il n'est branché sur aucun résultat du jeu.
Il le deviendra quand son banc de calibration reproduira les
distributions réelles ; d'ici là, il sert à regarder, à mesurer et à
régler. Le chemin recommandé (docs/GAME_DESIGN.md) reste l'hybride :
le moteur statistique garde l'autorité sur le score, B grandit dessous.

## Regarder

`/bac` sur le site : deux clubs, une formation, une durée, une graine,
et le match se joue côté serveur (six secondes pour 90 minutes) puis se
rejoue à l'écran, image par image, avec le fil des événements, les
statistiques du match et celles de chaque joueur (kilomètres, sprints,
pointe simulée contre note EA, touches, passes, tirs). Même graine, même
match : tout est déterministe.

    py -m jeu.emergent --jeu jeu/demo.sqlite --trace m.json --clubs 8456,9823

## Mesurer

Le banc joue des matchs entre vrais onze de club et compare aux ordres
de grandeur d'un match des grands championnats — les cibles viennent des
moyennes de saison et, pour la course, des mesures FotMob de Ligue des
champions (`moteur/mesures_fotmob_ucl.json` : 10,5 km par 90 minutes,
pointe médiane 31,8 km/h, 190 m de sprint, 9 sprints).

    py -m jeu.emergent --jeu jeu/demo.sqlite --matchs 8 --graine 11

**État : le bloc est devant le ballon.** Deux bugs de fond sont
sortis de cette passe. Le premier : la forme d'équipe réécrivait la
cible du porteur à chaque tic, il marchait vers sa place au lieu de
conduire (avec dix mètres devant lui, il était immobile ou au pas 43 %
du temps ; maintenant il court 68 %). Le second, plus grave : toute la
défense en bloc calculait « son propre but » avec `but_de(df)`, qui
donne le but qu'on ATTAQUE — le presseur contenait derrière le porteur,
le marqueur se plaçait devant son homme, le repli forcé comptait les
attaquants près du mauvais but. Corrigé, le bloc est enfin entre le
ballon et le but : quand le porteur entre dans les 35 mètres il a 6,6
adversaires devant lui (réel 5 à 7, avant 2,9), l'attaque entre dans la
surface une cinquantaine de fois (réel 50 à 60, avant 160), et le
marqueur est à 1,6 m de son homme au contact.

Ce qui tient le bloc : il anticipe un ballon qui vient (une seconde
d'avance), recule vite et remonte lentement (7 et 2,5 m/s), sa place ne
fuit jamais plus vite qu'un homme ne court, les milieux restent six
mètres derrière le ballon, on contient à deux mètres et demi (on ferme,
on ne saute pas dans les pieds), le marquage dans les vingt-cinq mètres
se prend d'avance et l'attribution est stable (chacun garde son homme,
le porteur compris), un porteur lancé sur un défenseur côté but ne le
contourne pas sans duel, le duel se tranche en un jet et pas plus d'un
toutes les cinq secondes sur un porteur, un porteur à l'arrêt se fait
piquer le ballon s'il traîne, le tacleur ressort avec le ballon six fois
sur dix et dégage en catastrophe dans sa surface.

6 matchs, graine 11 :

| mesure | simulé | cible | lecture |
|---|---|---|---|
| buts | 2,3 | 2,8 | proche |
| tirs | 17,5 | 25 | un peu peu depuis que le porteur ralentit devant l'obstacle |
| tirs cadrés | 6,3 | 8,5 | proche |
| passes | 1 135 | 900 | un peu trop : le porteur garde 2,3 s en médiane, réel 3 à 4 |
| réussite des passes | 82 % | 83 % | juste |
| corners | 2,0 | 10 | pas assez : les têtes défensives et les contres sortent peu derrière |
| fautes | 21 | 22 | juste (la faute de pressing en fait l'essentiel) |
| hors-jeu | 0,8 | 3,5 | trop peu |
| distance par joueur | 11,7 km | 10,5 km | proche |
| pointe médiane | 31,4 km/h | 31,8 km/h | juste |
| sprint par joueur | 324 m | 190 m | trop : pressing et transitions |
| possession du dominant | 54 % | 58 % | proche |
| tacles | 31,5 | 32 | juste : le porteur ne rentre plus dans le défenseur, le duel se cherche |
| cartons jaunes | 4,3 | 4 | juste |

Les outils de mesure de cette recalibration sont dans le scratchpad de
la session et se réécrivent en dix lignes : `espace.py` (le porteur
prend-il l'espace ?), `entrees.py` (entrées dans les 35 m et dans la
surface, défenseurs entre le porteur et le but), `surface.py` (comment
on entre : passe, conduite, large ou axe, marquage à l'entrée),
`bloc.py` et `cibles.py` (écart des défenseurs à leur place, vitesse des
places), `marque.py` (distance du marqueur à son homme, stabilité).

Ce que l'œil a corrigé avant les chiffres : les arrêts de jeu vivent (le
tireur marche au ballon, les autres prennent la forme de la reprise au
pas, plus personne n'est téléporté — sauf à la mi-temps) ; deux
coéquipiers ne visent jamais le même mètre carré (`_espacer`, huit
mètres) ; un défenseur par attaquant, à un mètre et demi dans sa surface
et à quatre mètres ailleurs ; les soutiens à quatorze mètres ; les
allures de replacement suivent la vitesse de chacun. Mesuré sur une
trace (`scratchpad/diag.py`) : plus proche voisin médian 5,9 m contre
4,8 avant, blocs de 34 m de long sur 40 m de large, dans les ordres de
grandeur réels.

Ce tableau est la feuille de route : chaque ligne hors cible a un réglage
nommé dans `jeu/emergent.py`. On règle une ligne, on rejoue huit matchs,
on regarde si les autres ont bougé.

## La tactique, le collectif, le travail sans ballon

**La tactique** d'un camp (les mêmes mots que le jeu : bloc haut/médian/bas,
tempo possession/équilibre/direct, risque offensif/équilibre/prudent,
relance courte/longue/mixte, et les consignes par ligne) se règle dans le bac, équipe par équipe, et
se voit. Bloc haut : la défense se tient six mètres derrière le ballon,
jusqu'au milieu adverse, et dans le camp adverse les deux joueurs qui
suivent le presseur prennent chacun un homme au contact — le pressing
en un pour un. Bloc bas : seize mètres derrière, jamais au-delà de sa
propre moitié, on contient à trois mètres tant que le ballon est loin.
Tempo possession : on garde le ballon plus longtemps et on passe court ;
direct : on lâche vite et la longue coûte moins. Risque offensif : plus
d'appels dans le dos. Latéraux « bas » : ils ne montent pas ; ailiers
« intérieur » : ils rentrent ; milieux « projection » : la ligne monte.

**Les patterns.** Ce que l'œil attendait et ne voyait pas : la balle
qui navigue sur la ligne offensive, aucun appel dans le dos, aucune
passe dans la course, personne qui part balle au pied. Quatre briques :

- *La relance* (consigne `relance` courte/longue/mixte ; mixte suit le
  tempo, possession joue court et direct joue long, et face à un bloc
  haut on allonge). Le gardien décide lui-même (`_relancer`) : courte,
  il cherche l'homme libre avec une ligne de passe à moins de
  trente-huit mètres, jamais dans les pieds d'un homme tenu ; sans
  ligne courte, il allonge. La phase `relance` a sa forme : courte, les
  centraux ouverts au bord de la surface, le pivot devant le gardien,
  les latéraux à la touche, tout le bloc sur quarante mètres pour que
  chaque porteur ait deux lignes courtes ; longue, tout le bloc monte
  à la retombée (soixante mètres), serré autour de l'attaquant pour le
  second ballon. Pas de hors-jeu sur une sortie de but.
- *L'appel en profondeur* : quand le porteur a le temps (pression
  faible) et qu'il reste quatorze mètres derrière la ligne adverse, un
  attaquant (les gros travailleurs offensifs d'abord, deux au plus)
  part DERRIÈRE la ligne, dans la brèche si elle est à portée, sinon
  droit devant en glissant vers l'axe. Tant que la passe n'est pas
  partie il court à la ligne sans la franchir — à sa marge à lui : un
  bon lecteur attend, un autre part un pas trop tôt et se fait prendre.
  C'est un sprint (pas de plafond d'allure sur ce rôle).
- *La passe en profondeur* : le porteur voit le coureur, et vise
  l'ESPACE où il va (`_passer(point=…)`), pas l'homme ; la passe vaut
  d'autant plus que le point d'arrivée est près du but, que la ligne
  est ouverte, que le coureur y arrive avant le défenseur et qu'il est
  déjà lancé ; elle vaut moins si le gardien peut sortir dessus. Dans
  le fil du bac elle s'appelle « passe en profondeur ».
- *La percée* : un boulevard de quatorze mètres devant un dribbleur,
  et il part balle au pied à 95 % de sa pointe, sans relâcher pendant
  presque deux secondes (sauf un adversaire qui arrive ou une frappe
  qui se présente). Un central en construction ne perce pas, il relance.

**Les duels et les replis** (le second passage de l'œil) :

- *Seul au but* : personne dans le couloir de douze mètres entre lui et
  le but, personne à six mètres dans son dos, dans l'axe (à moins de
  seize mètres de l'axe) — il file au duel avec le gardien, une latérale
  vaut moins, la frappe vaut plus à moins de vingt mètres. Il ne donne
  qu'à un coéquipier aussi seul et mieux placé. Quatre fois par match.
- *Le une-deux* : on ne remet pas au passeur dans les deux secondes et
  demie pour rien ; dans sa course (vers l'avant), oui.
- *Le marquage colle* : un presseur ou un marqueur garde son homme six
  secondes tant qu'il reste à portée (`_son_homme`), au lieu de
  reprendre le plus proche à chaque tic — c'était le fouillis des phases
  longues.
- *L'ailier provoque* : dans le dernier tiers, un vis-à-vis à moins de
  neuf mètres, et il y va balle au pied ; inversé (droitier à gauche,
  gaucher à droite, ou ambidextre) il rentre sur son bon pied vers
  l'axe, sinon il déborde. Le crochet se joue en un coup de rein
  (dribble contre défense, 0,52 de base, +0,08 sur le bon pied) : passé,
  le défenseur met huit dixièmes à se retourner ; raté, c'est un tacle,
  une fois sur cinq une faute. Cinquante provocations par match, un
  tiers passent.
- *Le pied de la frappe* : le ballon à sa gauche se frappe du droit, à
  sa droite du gauche, dans l'axe du bon pied ; le mauvais pied coûte
  en précision et en puissance selon la note du pied faible (un 5/5 ne
  coûte rien). L'événement de tir porte le pied, le bac le montre.
- *Le repli forcé* (`_doit_reculer`) : même un bloc haut recule sur un
  contre adverse dans sa moitié, ou quand il y a autant d'attaquants
  que de défenseurs à moins de trente-cinq mètres de son but.
- *Le repli des ailiers* (`_doubler`) : côté ballon, un ailier à travail
  défensif moyen ou haut (un attaquant à travail haut) revient doubler
  son latéral sur l'ailier ou le latéral adverse qui attaque le couloir,
  deux mètres et demi côté but de lui.

Et les allures : la transition offensive se court (les attaquants devant
le ballon sprintent sur un contre), le repli aussi (un milieu ou un
attaquant à dix mètres devant le ballon rentre en courant), mais un
sprint est une bouffée (`SOUFFLE`, 2,6 s) qui se recharge au trot, pas
une allure ; un contre qui n'avance plus au bout de deux secondes et
demie n'est plus un contre. Une latérale vers un homme tenu, dans le
camp adverse, vaut moins qu'avant : la balle navigue moins.

**Le collectif** (`jeu/collectif_manuel.json`, sinon mesuré) : de 0, une
somme d'individualités, à 1, un onze qui combine les yeux fermés. Mesuré
sur la saison, c'est la part des matchs du club que chaque paire a
commencés ensemble (une habitude, pas un style : PSG tourne beaucoup et
ressort à 0,26, Liverpool à 0,85) ; le fichier manuel tranche quand le
manager sait mieux (PSG 0,95, Real 0,35 pour commencer). Ce qu'il
change : le bruit des décisions (un collectif rodé sait ce que l'autre
va faire), la distance des soutiens (plus près), le troisième homme qui
part sur une passe vers l'avant, la permutation latéral-ailier quand le
latéral a dépassé son ailier, et le goût de la conduite balle au pied
(une somme d'individualités dribble plus qu'elle ne combine).

**Le travail sans ballon** (le *work rate* d'EA) : lu dans la fiche
physique quand elle a les colonnes `work_rate_att` et `work_rate_def`
(Low / Medium / High, ou une seule colonne `work_rate` « High/ Medium »),
sinon deviné sur les attributs (un attaquant qui défend bien revient, un
latéral qui crée bien monte). Un attaquant à travail défensif haut
redescend dix mètres de plus quand son camp n'a pas le ballon ; un
latéral à travail offensif haut monte seize mètres de plus quand il l'a.

**Le travail sans ballon en trois leviers** (`moteur/travail_sans_ballon.csv`,
mesures FotMob de Ligue des champions pour 544 joueurs, estimé EA pour
les autres — la colonne `source` le dit). Le volume de course pilote la
baisse de régime, le pressing pilote qui va au contact et à quelle
distance il contient, la récupération pilote le duel. La fiche donne des
rangs tous postes confondus, ce qui fait de tout central un joueur qui
court peu et de tout milieu un récupérateur ; l'import reclasse chaque
score parmi les joueurs du même poste, de 0 à 1, et le moteur lit ce
rang. Dembélé : volume moyen, pressing 0,9, récupération 0,03 — il court
normalement, presse très fort, ne ramasse pas. Rodri est l'inverse.
Dans le bac, la colonne V·P·R de chaque joueur les donne sur 9.

**La ligne tient.** Un défenseur qui suit un homme ne descend jamais
sous sa ligne (sauf dans sa surface) : le hors-jeu se joue en ligne, plus
personne ne remet les attaquants en jeu depuis derrière. Un central ne
part pas presser ou chasser un ballon à plus de vingt-deux mètres de sa
ligne si un milieu peut y aller.

**L'occasion se prend.** Dans les trente derniers mètres le porteur
décide plus vite, et une frappe vaut plus quand rien ne bouche l'axe ;
l'homme libre près du but vaut plus qu'un soutien couvert.

**Les coups de pied arrêtés ont leur forme** (`_forme_arret`). Corner :
six grands montent dans la surface (centraux, buteur, meneur, ailiers,
placés autour des six mètres), une option courte près du tireur, les
autres (latéraux, pivot) restent à trente-six mètres couvrir le contre ;
en face deux attaquants restent hauts, les défenseurs en ligne devant le
but, les milieux sur les attaquants montés ; le tireur centre, et
quiconque est à moins de quatorze mètres peut reprendre de la tête vers
le but (un central monté aussi). Coup franc à moins de trente-huit
mètres : le mur à 9,15 m — cinq dans l'axe à moins de vingt-deux mètres,
quatre à moins de vingt-huit, trois plus loin, deux excentré, un très
loin — les costauds dedans, les défenseurs en ligne à six mètres du
but, cinq attaquants au bord de la surface, le reste en couverture ; le
tireur frappe dans l'axe à moins de trente mètres (selon sa finition),
sinon centre. Penalty : le tireur au point, tout le monde au bord de la
surface en alternance, prêt à bondir sur un ballon repoussé. Le
capitaine (celui de la compo, sinon le joueur de champ le mieux noté)
porte un brassard dans le bac.

**Le porteur ralentit devant l'obstacle** : un défenseur à trois mètres
et demi devant lui, et il passe à 2,5 m/s, protège, donne — le duel se
cherche (percée, provocation, seul au but), il ne se subit pas en
rentrant dans le bloc. C'est ce qui a ramené les tacles de 160 à 32.
**La faute de pressing** : un défenseur qui arrive lancé dans les pieds
du porteur le bouscule une fois sur vingt, c'est l'essentiel des fautes
d'un match. **Le marqueur accompagne** : il se place côté but de son
homme et un peu devant sa course, il ne le suit pas.

**Le porteur ne reste pas planté** : sans espace devant et sans homme
dans les pieds, il dérive au pas vers le côté le plus ouvert pendant
qu'il réfléchit. **Le crochet en zone de danger** : dans le dernier
tiers, huit mètres libres sont déjà un boulevard (quatorze ailleurs) et
la percée y vaut plus. **La frappe de loin** : entre vingt et
trente-six mètres, face à un bloc bas, l'axe ouvert et sans pression,
on tente sa chance.

**Le bac dessine les gestes** : l'élan d'une frappe (la jambe part en
arrière puis fouette vers le ballon, le pied dit D ou G), la détente
d'une tête (le jeton s'élève, son ombre reste au sol), la détente du
gardien sur un arrêt (il s'allonge vers le ballon), et les filets qui
tremblent sur un but — le ballon reste au fond quatre secondes avant que
l'arbitre ne le ramène au centre.

## Ce qu'il y a dedans

**Le physique.** Vitesse de pointe = 31,8 km/h + (note EA − 70) × 0,141
(la conversion mesurée : dix points EA valent 1,41 km/h), bornée entre
23 et 38 km/h ; accélération de 4,4 à 6,9 m/s² selon la note ; usure
qui croît comme le cube de la vitesse et dépend de l'endurance EA, et
qui rogne la pointe et l'accélération. Un joueur sans fiche court à la
médiane de son poste.

**Le ballon.** Roule avec un frottement de 3,2 m/s², vole sous la
gravité, rebondit en perdant les deux tiers de sa hauteur. Une passe
part à la vitesse qu'il faut pour arriver, plus un mètre par seconde ;
par-dessus quand elle est longue ou qu'un adversaire coupe la ligne.
Une frappe part entre 20 et 31 m/s selon la finition, vers un poteau,
avec une erreur d'angle et de hauteur qui dépend de la finition, de la
pression et de la distance.

**L'équipe décide, chacun exécute.** À chaque tic, chaque camp lit
d'abord sa PHASE, puis la forme de la phase donne à chaque rôle tactique
(centraux, latéraux, pivot, relayeurs, meneur, ailiers, buteur — lus sur
la case de chacun dans la formation) une place qui dépend du ballon, et
les rôles individuels se posent par-dessus. Avec le ballon :
*construction* dans son tiers (centraux écartés, pivot qui descend,
latéraux hauts et larges, ailiers larges, buteur qui fixe les centraux),
*progression* au milieu (le bloc monte avec le ballon, latéraux et
relayeurs se projettent selon les consignes et leur travail offensif),
*finition* dans les trente derniers mètres (surcharge côté ballon par
l'ailier et le latéral, ailier opposé au second poteau, buteur entre les
centraux, meneur à l'entrée de la surface, et une défense de repli :
deux centraux à cinquante mètres, le pivot devant), *contre* six
secondes après une récupération basse (ailiers et buteur partent devant,
relayeurs en soutien de course). Sans le ballon : *pressing* (bloc haut,
ou bloc médian sur une relance adverse quand les attaquants aiment ça :
le plus envieux arrive sur le porteur en coupant la ligne vers son option
la plus proche — Dembélé presse le gardien dans l'ombre du central — et
trois autres prennent chacun un homme au contact côté but), *bloc
médian* (la ligne à onze mètres du ballon, tout le monde derrière le
ballon), *bloc bas* (tassé sur vingt-cinq mètres, la ligne jamais au-delà
de vingt-huit mètres, le côté opposé rentré jusqu'à l'axe, on contient à
trois mètres et on ne sort pas chercher le ballon au-delà de sa moitié),
*contre-pressing* cinq secondes après une perte, pour un bloc haut ou un
collectif rodé. Un attaquant à gros travail défensif revient dans le
bloc ; personne ne se place hors jeu.

**Les rôles individuels.** Le receveur d'une passe en cours va au point
de chute ; un seul soutien (le relayeur ou le pivot le plus proche, à
dix mètres en retrait côté ballon) ; l'appel se fait dans LA BRÈCHE — le
plus grand trou entre deux défenseurs de la dernière ligne, juste devant
le hors-jeu — par un attaquant à la fois, deux au plus, et la passe vers
un coureur dans la surface est celle qui vaut le plus ; en finition on
ne rend pas le ballon à un central libre trente mètres derrière ; le
plus proche de chaque camp chasse un ballon libre ; dans le dernier
tiers, un défenseur par attaquant, sans jamais descendre sous la ligne ;
le gardien ferme l'angle, sort sur un ballon libre dans sa surface, et
sur une frappe va au point où elle croise sa ligne. Dans le bac, la phase
de chaque camp s'affiche en haut du terrain.

**Le porteur.** Il garde le ballon de une à trois secondes selon la
pression (moins avec un bon sang-froid), puis compare des options avec
un bruit qui décroît avec CON : frapper (par un xG grossier — distance,
angle, pression — pondéré par FIN), passer à chacun (progression,
danger du receveur, espace autour de lui, ligne de passe libre,
distance, hors-jeu), centrer depuis le couloir, conduire (espace devant,
DRI), dégager sous pression dans son camp. Dans la zone de frappe, il ne
réfléchit pas trois secondes.

**Les contacts.** Le ballon se prend à un mètre quand il roule, à
cinquante centimètres quand il file (un mètre et demi pour celui à qui
la passe est adressée), avec un contrôle qui peut rater au-delà de 14
m/s ; un ballon haut se joue de la tête (un défenseur dégage, un
attaquant remise ou frappe près du but) ; un défenseur sur la
trajectoire d'une frappe la contre une fois sur deux ; le gardien
capte, ou plonge avec une chance qui dépend de sa distance à la
trajectoire, de la vitesse et de ARR, et repousse les frappes fortes
vers la touche. Un adversaire au contact du porteur tente de lui prendre
le ballon : DEF contre DRI, force contre force, une faute une fois sur
trois, un carton une fois sur quatre, un second jaune est un rouge.

**Les règles.** But, touche, sortie de but, corner, penalty dans la
surface, coup franc (frappé une fois sur trois à moins de 26 m),
hors-jeu jugé à l'instant de la passe, engagement, mi-temps. Les arrêts
de jeu durent ce qu'ils durent (touche 9 s, sortie de but 14 s, coup
franc 18 s, corner 22 s, penalty 40 s, but 45 s), ce qui ramène le temps
de jeu effectif vers ses soixante minutes réelles.

**La sortie.** Le score, les événements horodatés, une image toutes les
0,4 s (ballon x, y, z et vingt-deux positions, en décimètres : 13 500
images pour 90 minutes), les statistiques d'équipe (possession, tirs,
cadrés, xG, passes, corners, fautes, hors-jeu, tacles, cartons) et de
joueur (distance, sprint, pointe, touches, passes, tirs, tacles,
interceptions, fautes, arrêts, fatigue).

## Ce qui manque encore

Par ordre d'importance pour basculer un jour :

1. **La calibration** : le tableau ci-dessus, ligne par ligne. Puis la
   différence entre un 87 et un 75 (aujourd'hui les six attributs
   pèsent sur la précision et les décisions, mais leur effet sur le
   score n'est pas mesuré), et l'avantage du terrain.
2. **Les consignes** du manager (tempo, bloc, pressing, les cinq
   consignes par ligne) : la forme et les rôles les ignorent encore.
3. **Les remplacements, les blessures, la causerie** : le match est joué
   à onze fixes.
4. **Le pied** : une frappe ou un centre du mauvais pied devrait coûter
   en précision (la fiche EA donne la qualité du mauvais pied).
5. **Le rendu** : le bac dessine des ronds sur un canvas ; brancher la
   trace sur le terrain 2D du site (jetons, filets, ballon dessiné), puis
   un jour en 3D, est un travail de rendu, pas de football.
6. **La vitesse** : six secondes par match en Python pur (pas de 0,1 s,
   décisions toutes les 0,2 s). Suffisant pour le bac et un banc de
   cinquante matchs ; pour jouer tous les matchs du jeu il faudra un
   cœur compilé ou une trace calculée d'avance et servie.

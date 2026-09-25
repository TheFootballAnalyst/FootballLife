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
on ne saute pas dans les pieds) sauf à moins de vingt-cinq mètres de son
but, où l'on va au contact, la ligne est une seule profondeur que tous
les défenseurs tiennent, le marquage dans les vingt-cinq mètres est
par zone (un central ne sort pas à plus de huit mètres devant la ligne)
et
se prend d'avance et l'attribution est stable (chacun garde son homme,
le porteur compris), un porteur lancé sur un défenseur côté but ne le
contourne pas sans duel, le duel se tranche en un jet et pas plus d'un
toutes les cinq secondes sur un porteur, un porteur à l'arrêt se fait
piquer le ballon s'il traîne, le tacleur ressort avec le ballon six fois
sur dix et dégage en catastrophe dans sa surface.

6 matchs, graine 11 :

| mesure | simulé | cible | lecture |
|---|---|---|---|
| buts | 3,0 | 2,8 | juste (dix-huit matchs, graines 41 à 43 ; douze matchs entre PSG, Arsenal et le Bayern : 2,9) |
| tirs | 23 | 25 | proche (dix-huit matchs : 20 à 25 ; les grands clubs entre eux : 23) |
| tirs cadrés | 7,8 | 8,5 | proche |
| passes | 890 | 900 | juste, depuis qu'un côté bouché se quitte |
| réussite des passes | 90 % | 83 % | un peu haut depuis qu'il y a moins de passes en profondeur (elles ratent une fois sur trois) |
| corners | 7 | 10 | mieux : les centres se disputent de la tête, le gardien repousse, le défenseur dégage en première intention |
| fautes | 23 | 22 | juste (la faute de pressing en fait l'essentiel) |
| hors-jeu | 0,9 | 3,5 | peu : la ligne tient aux talons du dernier attaquant en jeu, elle ne monte pas encore au moment de la passe (le piège) |
| distance par joueur | 12,2 km | 10,5 km | un peu trop |
| pointe médiane | 31,2 km/h | 31,8 km/h | juste (corrélation 0,87 avec la note EA) |
| sprint par joueur | 350 m | 190 m | trop, mais moins : deux fois moins d'appels lancés |
| possession du dominant | 53 % | 58 % | proche |
| tacles | 29 | 32 | proche : le porteur ne rentre plus dans le défenseur, le duel se cherche |
| cartons jaunes | 4,2 | 4 | juste |

Le banc sur six matchs bouge d'une graine à l'autre (les buts de 1,8 à
3,3) : pour trancher un réglage, on joue deux graines.

**Trop de buts (2-6, 5-2 entre grands clubs) : d'où ils venaient.** Les
buts suivaient l'xG (la finition et le gardien sont justes) ; c'est
l'entrée dans la surface qui était trop facile : 49 entrées de porteur
par match (le réel tourne autour de 30), 51 passes en profondeur
tentées, 546 appels lancés, et 2 hors-jeu. Quatre corrections, toutes
de football : un appel se lance deux fois moins souvent et jamais deux
dans la même seconde et demie pour une équipe ; une passe en profondeur
avec un défenseur sur la trajectoire vaut moins (il faudrait la lober) ;
le passeur juge la ligne avec six dixièmes de retard et la manque une
fois sur vingt ; dans les vingt-cinq derniers mètres le marqueur d'un
receveur anticipe à trois mètres au lieu de deux vingt ; et surtout, à
moins de vingt-cinq mètres de son but on ne contient plus à deux ou
trois mètres, on va au contact (1,2 m), sinon le porteur entrait dans la
surface en marchant après une passe reçue à son bord (« passe puis
conduite » faisait 23 entrées sur 51). Résultat : 35 entrées, 25 à 31
tirs, 2,7 à 3,2 buts, 2,8 sur six matchs entre PSG, Arsenal et le
Bayern (1-1, 1-1, 2-4, 2-1, 2-2, 0-0).

**Ce que l'œil a relevé ensuite, et la réponse.** Un coureur lancé qui
reçoit dans les pieds (Dembélé pour Doué) : quand la passe en profondeur
est ouverte (le coureur a un temps d'avance, le couloir est libre), la
passe dans les pieds du même coureur perd 0,45 et la profondeur gagne
0,2 — on le sert dans sa course. Une touche de quarante mètres : une
remise en touche est à la main, vingt-six mètres au plus, jamais une
frappe. Un central qui suit son homme hors de la ligne (Pacho derrière
Ødegaard), un central qui traverse jusqu'au côté de son latéral
(Marquinhos derrière Trossard, Hakimi sur personne) : le marquage est
par ZONE — chacun garde son homme tant qu'il reste dans sa zone (douze
mètres de large autour de sa place pour un central, quinze pour les
autres, et pas plus de dix mètres devant la ligne des centraux pour un
central, seize pour un latéral) ; sinon il le lâche et le voisin dont
c'est la zone le prend. Mesuré : l'homme d'un central est en médiane sur
la ligne, à 4 m devant au neuvième décile, jamais à plus de dix. Et le
ballon qui « s'arrêtait » : une passe était dosée pour mourir dans les
pieds (un mètre par seconde à l'arrivée) ; elle arrive maintenant
vivante, à 5,5 m/s (7 m/s mesurés à la réception), c'est le receveur qui
l'arrête. Dans le bac il est blanc à pentagones noirs et tourne avec le
chemin parcouru.

**La ligne à quatre (Marquinhos planté au fond, Mendes et Neves dans
les choux, Marquinhos sur Zubimendi).** Le mécanisme, vu dans les
traces : en bloc bas la forme posait la ligne quinze mètres derrière le
ballon (à 9 m du but quand le ballon est à 24 m) pendant que les
marqueurs tenaient à 14–16 m ; le central ou le latéral « de forme »
filait donc seul au fond. Maintenant LA LIGNE est une seule profondeur
par tic : celle de la forme (douze mètres derrière le ballon en bloc
bas, quinze en bloc médian, jamais sous neuf), remontée aux talons de
l'attaquant le plus bas encore en jeu (à un mètre de lui, sans approcher
le ballon à moins de dix mètres). Tout défenseur qui n'est pas sur le
ballon la tient : il glisse en largeur vers son homme ou le ballon, il
ne monte ni ne descend seul. Il peut sortir de trois mètres sur un homme
devant lui ; il suit son homme dans la surface quand le ballon est à
moins de vingt-deux mètres ; et il suit un homme lancé dans son dos (on
ne regarde pas passer un coureur). La zone d'un marqueur se lit sur
cette ligne : un central ne sort pas à plus de huit mètres devant elle
(Zubimendi est l'affaire d'un milieu), un latéral quatorze. Le
marquage par zone et la passe vivante restent des constantes en tête de
`jeu/emergent.py` (`MARQUAGE_ZONE`, `PASSE_ARRIVEE`), faciles à
débrancher pour comparer.

**Le pressing homme à homme sur la relance courte.** Une relance aux
six mètres jouée court face à une équipe en pressing (bloc haut, ou des
attaquants qui aiment presser) déclenche l'homme à homme : chaque
attaquant et milieu prend un relanceur, les plus près de leur but
d'abord (les centraux, le pivot), sur la ligne de passe à un mètre et
demi. Le gardien ne se presse pas : le buteur se place au bord de la
surface sur la ligne gardien → central voisin, prêt à jaillir sur le
gardien en cachant la passe facile — il « tient » ce central, l'autre
central est l'homme libre du dispositif. Sur une sortie de but personne
n'entre dans la surface adverse (chacun se place à son bord). Si un
joueur de champ porte, le presseur le plus proche va dessus en coupant
l'option voisine ; les défenseurs prennent les attaquants restés hauts.
Le dispositif se place pendant l'arrêt de jeu, avant le coup, et tient
huit secondes ou jusqu'à ce que la relance ait quitté les trente-cinq
mètres.

**Les courses inverses (Neves et Hakimi qui se croisent).** Mesuré : le
« coupeur » (celui qui ferme la ligne de passe derrière le presseur)
changeait de titulaire 55 fois par minute de bloc — deux hommes qui se
relaient à chaque tic font des courses inverses. Quatre hystérésis :
le presseur garde le ballon deux secondes sauf si un autre est plus
près de quatre mètres, le coupeur garde son rôle trois secondes tant
qu'il reste à moins de vingt mètres du ballon, un marqueur lâche son
homme trois mètres plus loin qu'il ne le prend, et le marquage s'allume
à quarante mètres du but pour s'éteindre à quarante-six. Les
changements de coupeur tombent à 23 par minute et les allers-retours de
rôle en moins de deux secondes de moitié.

**Le ballon roule.** Le frottement au sol était une décélération
constante de 3,2 m/s² : un ballon à 5 m/s mourait en quatre mètres, et
2,3 % du temps de jeu le ballon était libre et immobile au sol. La
décélération dépend maintenant de la vitesse, 1,2 m/s² + 0,012·v²
(`frottement`, `distance_arret`, `vitesse_pour`, `avance` en tête du
module) : un ballon lent roule loin (5 m/s → 9 m), un ballon fort est
freiné par l'herbe et l'air (12 m/s → 37 m). Une passe est dosée pour
arriver à 7 m/s dans les pieds ; un ballon qui retombe garde 60 % de son
élan. Mesuré : plus aucun ballon libre immobile (0,0 %), 25 % du temps le
ballon roule libre, 59 % il est conduit, 12 % il est en l'air.

**Des joueurs sous la ligne (le retour).** Mesuré : le pivot, les
relayeurs et même un ailier passaient une minute et demie par match
sous la ligne défensive avec une cible sous la ligne. La forme les
posait sept mètres devant la ligne DE LA FORME, mais la ligne, elle,
est remontée aux talons des attaquants : ils restaient en dessous.
Personne d'autre qu'un défenseur ne se place sous la ligne, désormais.
Et l'effet « le latéral rentre dans l'axe, le central s'excentre plus
bas que la ligne » : un central glisse vers le ballon de six mètres au
plus (`CENTRAL_GLISSE_MAX`), la forme se tient à un mètre de la ligne
et un marqueur sort de deux mètres et demi au plus (`LIGNE_TOLERANCE`),
et la ligne remonte à 3,5 m/s au plus (`LIGNE_MONTEE`) pour que les
hommes la suivent au lieu de courir après une ligne qui a sauté de dix
mètres sur une passe en retrait. Ces trois réglages pèsent sur les
buts : sur dix-huit matchs de banc, une ligne serrée à un demi-mètre et
un marqueur à un mètre et demi donnaient 3,4 buts, les anciens réglages
2,3, le réglage retenu 3,0.

**Le niveau pèse (PSG–Lorient 0-0).** Mesuré sur quarante matchs
PSG–Lorient (OVR moyens 80 et 64, chaque équipe vingt fois à gauche) :
le PSG ne gagnait que 52 % des matchs et en perdait 20 %, pour 2,0 buts
à 1,1 — trop peu pour seize points d'écart (le réel tourne autour de
80 % de victoires, 8 % de défaites, 2,8 buts à 0,6). L'xG était déjà
dans le bon rapport (1,5 contre 0,8) : ce sont les attributs qui ne
mordaient pas assez sur le jeu. Six leviers, tous de football : la passe
ratée dépend fortement de la technique (un passeur à 0,85 de précision
rate une passe sur seize, un à 0,55 une sur sept, et une passe ratée
part vraiment de travers — douze degrés et une vitesse entre la moitié
et une fois et demie) ; l'erreur d'angle d'une passe pèse six fois le
défaut de précision au lieu de quatre ; un contrôle s'échappe sous
pression (un sur quarante pour un bon technicien, un sur vingt pour un
joueur moyen) ; un duel se gagne à 0,7 fois l'écart DEF − DRI au lieu
de 0,4 ; le bruit des décisions dépend plus du sens du jeu (CON) ; et le
gardien comme la finition s'étalent davantage (arrêt : 0,6 + 0,4·ARR ;
frappe : 13° + 14° de défaut de finition). Résultat sur quarante
matchs : 75 % de victoires du PSG, 17 % de nuls, 8 % de défaites, 2,3
buts à 0,9 ; PSG–Bayern reste équilibré (6-5-9 sur vingt) ; le banc
donne 3,0 buts et 22 tirs. La réussite des passes ne s'écarte que de
deux points (89 % contre 86 %) : le reste de l'écart réel vient de ce
que l'équipe faible joue plus long et sous plus de pression, ce que le
moteur ne fait pas encore assez.

**L'équipe faible joue plus long (la réussite des passes, suite).** La
réussite des passes ne s'écartait que de deux points entre Paris et
Lorient parce que le choix de passe ne dépendait pas du joueur. Trois
choses, dans l'ordre du plan : un porteur peu technique (précision
PRO/CRE sous 0,72 : la « maladresse ») pressé allonge devant (bonus sur
les passes de plus de vingt-cinq mètres vers l'avant), dégage plus tôt
et de plus haut, et sa défense joue long dès qu'on la presse, pas
seulement face à un bloc haut ; la passe précipitée : sa garde
raccourcit sous pression et l'erreur d'angle sous pression pèse plus ;
le soutien d'un milieu qui lit mal le jeu (CON) propose plus loin, donc
la ligne courte est plus longue. Mesuré sur quarante matchs PSG–Lorient :
part de passes longues 18 % contre 12 % (réel 16 contre 9), dégagements
5,4 contre 2,1, réussite 84–85 % contre 87–88 % (trois à quatre points
d'écart au lieu de deux ; le réel en donne douze), 82 % de victoires,
8 % de nuls, 10 % de défaites, 3,2 buts à 0,8. PSG–Bayern reste
équilibré (8-6-6), le banc 2,8 buts et 23 tirs.

**Marquinhos seul au fond (le retour).** Le scan montrait le cas : la
ligne était juste (treize mètres derrière le ballon) mais trois
défenseurs l'avaient quittée pour presser ou chasser un ballon vingt
mètres devant, et le quatrième restait seul dessus. Remonter le
quatrième vers ses partenaires (essayé : six mètres sous leur médiane)
coûte un but par match sur le banc, parce que c'est lui qui fait le
hors-jeu et la couverture. La bonne réponse est de garder les trois
autres : un défenseur ne sort presser ou chasser un ballon qu'à moins
de douze mètres devant sa ligne (vingt-deux avant), au-delà c'est un
milieu qui y va. Les centraux « de forme » sept mètres sous leurs
partenaires passent de 18 à 8 ticks par match, les latéraux de 80 à 40 ;
ce qui reste, c'est un défenseur qui chasse un ballon qui roule vers
son but, ce qui est du football. Banc : 2,9 buts, 23 tirs.

**Le jeu sans ballon sur les principes réels.** Le bloc était une dalle
haute et plate (ligne à 41 m au milieu, dix joueurs sur douze mètres) et
le pressing un état qui clignotait (1,3 s). Les principes chiffrés dans
`docs/TACTIQUE.md` (300 matchs StatsBomb, rapport UEFA) sont maintenant
dans le moteur : la ligne à 0,75 × ballon − 6, trois lignes sur vingt-deux
mètres, le pressing en vagues déclenchées de trois à six secondes, le
contre-pressing comme un choix une fois sur trois, le repli sinon. La
mesure à règle égale est dans ce doc-là.

**Le latéral qui va se perdre sur le côté, les milieux et latéraux qui
s'échangent leurs places.** Mesuré : un latéral de forme passait 3,7 s
par minute de bloc plus large que tout attaquant de son côté — il
allait défendre la ligne de touche vide pendant que son ailier rentrait
(la zone le lâchait à quinze mètres, et sa place de forme est large).
Deux règles : la zone d'un latéral est plus large vers l'intérieur
(`LATERAL_ZONE_DEDANS`, vingt-deux mètres : il suit son ailier qui
rentre jusqu'à ce que le central le prenne), et un latéral de forme ne
se place jamais plus de six mètres plus large que l'attaquant le plus
large de son côté (`LATERAL_TOUCHE`, `LATERAL_MARGE`). Le temps « trop
large » tombe à 2,3–3,2 s par minute. Les amas de trois défenseurs dans
cinq mètres (presseur, coupeur, marqueur : 3,8 s par minute) ne bougent
pas quand on écarte le pressing à six mètres (`ESPACE_PRESSE`), et
six mètres coûte un but par match : on reste à quatre. Sur ces réglages
les bancs de dix-huit matchs bougent de ±0,6 but d'une graine à
l'autre, même à code identique — le banc est chaotique, et il faut une
centaine de matchs pour trancher un dixième de but.

**Mendes « envoie le ballon en touche pour rien » (8').** La touche
était pour l'adversaire, donc c'était bien lui. Mesuré sur six matchs :
sur 34 passes jouées juste après avoir reçu une passe en profondeur,
12 partaient dix à dix-sept mètres en arrière dans les quarante
derniers mètres, et deux filaient en touche — une passe en retrait sous
pression, ratée « trop fort » (jusqu'à une fois et demie la vitesse).
Deux règles : lancé dans la profondeur, on va au bout (dans les trois
secondes qui suivent la réception, un ballon rendu en arrière perd
0,9 : on frappe, on centre, on protège), et une passe ratée part de
travers, jamais au canon (0,6 à 1,3 fois la vitesse, plus 0,5 à 1,5).
Après : 6 retours sur 22, aucun en touche. Au passage, un tacle gagné
dans sa surface ne dégage plus dans le même tic (le tacleur garde le
ballon un instant, et le bac dessine la glissade, « Tacle » dans le
fil, bac.js v24).

**Un exclu sort du terrain.** Un carton rouge laissait le joueur figé
à l'endroit de la faute jusqu'à la fin, toujours dessiné dans le bac
(« Doué bloqué dans le mur à la 71' »). L'exclu sort au pas par la
touche la plus proche et le bac ne dessine plus un joueur sorti des
lignes.

**La sortie de but se presse aussi en bloc médian.** Le pressing homme
à homme sur la relance courte ne s'allumait qu'en phase de pressing,
donc jamais avec le bloc médian par défaut si les attaquants n'aiment
pas presser. Une relance courte adverse met désormais un bloc médian en
pressing, quels que soient les attaquants ; seul le bloc bas reste
assis. Et une défense technique (PRO moyen des défenseurs
≥ 68) joue court même face à un bloc haut — c'est tout l'intérêt du
pressing ; les autres allongent.

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
  attaquant (les gros travailleurs offensifs d'abord, deux au plus, pas
  deux départs en une seconde et demie) part DERRIÈRE la ligne, dans la brèche si elle est à portée, sinon
  droit devant en glissant vers l'axe. Tant que la passe n'est pas
  partie il court à la ligne sans la franchir — à sa marge à lui : un
  bon lecteur attend, un autre part un pas trop tôt et se fait prendre.
  C'est un sprint (pas de plafond d'allure sur ce rôle).
- *La passe en profondeur* : le porteur voit le coureur, et vise
  l'ESPACE où il va (`_passer(point=…)`), pas l'homme ; la passe vaut
  d'autant plus que le point d'arrivée est près du but, que la ligne
  est ouverte, que le coureur y arrive avant le défenseur et qu'il est
  déjà lancé ; elle vaut moins si le gardien peut sortir dessus ou si un
  défenseur est sur la trajectoire. Dans le fil du bac elle s'appelle
  « passe en profondeur ».
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

**Les centres se disputent.** Un centre vise le coéquipier le mieux
placé dans la surface (le plus libre, le plus près du but), un peu
devant lui, et arrive à hauteur de tête : c'est là que ça se dispute, à
un mètre quarante (on saute, on se penche). Une tête défensive
contestée sort une fois sur deux derrière, le gardien repousse une
frappe forte une fois sur quatre, et un défenseur qui prend un ballon
adverse dans sa surface avec un attaquant dans le dos dégage en
première intention. Voilà les corners.

**Un côté bouché se quitte.** Le moteur compte les passes d'affilée sur
un même côté (`cote_suite`) ; après deux en construction (trois dans le
dernier tiers) sans progresser, insister sur ce côté coûte, repasser par
l'axe rapporte, et la transversale vers l'autre côté rapporte sans payer
la pénalité de longueur si la ligne est ouverte. Mesuré sur un match :
les enchaînements de quatre passes et plus sur un côté passent de 56 à
34, les transversales de 17 à 57, les retours par l'axe de 66 à 87.
Et quand le côté est bouché, le soutien vient proposer en retrait
dans l'axe (huit mètres derrière, dix vers l'axe) et un second milieu
s'offre plus bas dans l'axe : la réorientation a des jambes, pas
seulement une valeur de passe. Les enchaînements de quatre passes et
plus sur un côté tombent à 22, ceux de six et plus à 1.

**Le latéral qui plonge et le point d'appui.** Un latéral à travail
offensif haut (0,6 et plus) fait les appels dans le dos comme un ailier,
et part en troisième homme sur une passe vers l'avant. Un attaquant ou
un milieu qui reçoit dos au but dans le camp adverse avec un marqueur
dans le dos remet en une touche au coéquipier qui arrive lancé avec une
ligne ouverte (une fois sur trois, plus dans un collectif rodé) : le
jeu en triangle des équipes de conservation.
**On ne s'entasse pas** : l'ailier ne vient pas doubler là où il y a
déjà deux des nôtres, le gardien ne va pas au ballon pendant un arrêt de
jeu et c'est lui qui joue un coup franc dans sa surface.

**La réussite des passes.** Le 72 % d'avant était un bug de comptage
(les centres et les passes reprises de la tête ne comptaient jamais) ;
la vraie réussite était de 92 %, trop sûre. Trois choses la ramènent à
87 % : la passe ratée (une sur dix part de travers ou mal dosée, plus
sous pression, de loin, dans le dernier tiers, moins avec la
technique), le marqueur d'un homme tenu qui anticipe et souffle le
ballon (à 2,2 m, à 3 m dans les vingt-cinq derniers mètres), et l'audace d'une équipe menée en fin de match ou qui joue
direct, qui accepte l'homme tenu. Par type : courtes 94 %, 15 à 30 m
90 %, longues 93 %, centres 74 %, passes en profondeur 63 %.

**Le terrain ressemble à du football.** Chaque club a son maillot
(`jeu/maillots.py` : couleur, seconde couleur et motif — uni, bande
comme le PSG, rayures, cercles, moitiés, écharpe) ; le visiteur passe en
tenue extérieure quand les couleurs se confondent, les gardiens portent
une couleur que personne d'autre n'a. Un joueur se dessine vu de
dessus : les épaules au maillot, la tête un peu en avant, deux pieds
qui alternent avec la foulée (une foulée par 0,7 à 2,5 m selon
l'allure, immobiles à l'arrêt), le corps orienté dans le sens de la
course et, à l'arrêt, vers le ballon. L'orientation se lisse pour ne pas
sauter d'une image à l'autre.

**Les penaltys.** Dans la surface on défend les mains dans le dos : la
faute de pressing et la faute sur duel y sont trois fois moins probables
(un tiers de penalty par match). **Le duel aérien** : deux camps sous un
ballon en l'air, ce n'est pas le plus près qui l'emporte mais le plus
costaud, et celui qui l'attendait. Un centre est une passe vers un
homme : il compte réussi si un coéquipier le reprend, de la tête ou au
pied.

**Le piège.** Quand le ballon repart en arrière, la ligne remonte d'un
coup (quatre mètres, à 6,5 m/s) au lieu de remonter à 2,5 m/s ; le
presseur arrive vite mais ne sprinte que sur un porteur qui s'échappe.

**Le passeur voit la ligne en retard.** Il juge le hors-jeu d'un coureur
sur la ligne telle qu'elle était six dixièmes plus tôt
(`ligne_horsjeu(retard=True)`) : un coureur parti un pas trop tôt sur une
ligne qui vient de bouger se fait prendre, comme en vrai. Le drapeau se
lève sur la vraie ligne, à l'instant de la passe.

**La ligne tient, et les latéraux plongent.** Un latéral ou un milieu
qui suit un homme ne descend jamais sous la ligne des centraux (moins
deux mètres), sauf quand le ballon est dans les vingt mètres : suivre
plus bas, c'est remettre tous les autres en jeu (les hors-jeu passent de
1 à 2,8). Les centraux, eux, suivent leur homme jusqu'au bout. Un latéral
à travail offensif haut peut partir en profondeur depuis dix-huit mètres
derrière le ballon quand le jeu est de son côté ; quand un latéral monte,
l'autre reste.

**La peau des joueurs** dans le bac est lue sur leur portrait (une zone
front-joues, pixels couleur chair), sur la machine où les portraits sont
présents ; sans portrait, un ton moyen.

**Dans la surface on frappe.** Une remise en retrait ou de côté depuis
la surface, vers un coéquipier qui n'est pas mieux placé, vaut moins
qu'une frappe ; et la remise en une touche du point d'appui ne se fait
pas quand on est en position de frappe ou avec de l'espace devant — là
on se retourne. **Un pressing, pas un amas** : trois hommes vont au
pressing (le presseur et deux), et autour du ballon les défenseurs
(marqueurs, coupeur, doubleur) gardent quatre mètres entre eux et avec
le presseur.

**Le porteur ne reste pas planté** : sans espace devant et sans homme
dans les pieds, il dérive au pas vers le côté le plus ouvert pendant
qu'il réfléchit. **Le crochet en zone de danger** : dans le dernier
tiers, huit mètres libres sont déjà un boulevard (quatorze ailleurs) et
la percée y vaut plus. **La frappe de loin** : entre vingt et
trente-deux mètres, l'axe entrouvert et le vis-à-vis à plus de deux
mètres et demi, on tente sa chance — un tir sur trois hors de la surface,
comme en vrai (`TIR_LOIN`).

**La surface d'abord** (docs/TACTIQUE.md § 13). Dans les trente
derniers mètres, le bloc protège la surface plutôt que d'aller au
ballon : sur un ballon en l'air, le défenseur le plus proche du point où
il redescend à hauteur de tête va l'attaquer (`BALLON_AERIEN`), et dans
sa surface il gagne la tête un peu plus souvent (`AERIEN_SURFACE`) ;
quand le ballon est à moins de vingt-huit mètres, un central marque son
homme au point de penalty même loin devant la ligne
(`MARQUAGE_SURFACE`) ; le marqueur du porteur couvre à quatre mètres
derrière le presseur au lieu de doubler sur le ballon
(`PORTEUR_COUVERT`) ; un défenseur posé dans sa surface coupe une passe
qui file à moins de quatre-vingt-dix centimètres (`PORTEE_SURFACE`) ; on
centre deux fois moins (`CENTRE_BASE`). Mesuré : les centres passent de
41 à 21 par match et les têtes sur centre de 22-4 pour l'attaque à
8-12 ; les possessions de dix passes et plus finissent par un tir 21 %
du temps, comme en vrai (29 % avant), et deux tirs sur trois viennent de
la surface (87 % avant). Sur cette défense, la tête comme une passe
(`TETE_REMISE`) et le contrôle à la poitrine (`CONTROLE_POITRINE`) sont
rallumés (2,9 buts, mais 32 tirs) ; le lob court (`LOB_BAS`) et une garde
plus courte restent parqués (docs/TACTIQUE.md § 13).

**Le temps de jeu effectif** (docs/TACTIQUE.md § 14). Un match réel
n'a le ballon vivant que 55 à 58 minutes sur 97 ; le moteur en jouait 70
sur 90, d'où vingt pour cent de passes, de possessions et de tirs en
trop. Les délais de reprise sont des constantes (`DELAIS` : une touche
16 s, une sortie de but 26, un corner 32, un coup franc 28) : 60 minutes
de ballon vivant, 27 tirs et 2,8 buts sur 36 matchs.

**Le temps additionnel** (docs/TACTIQUE.md § 15). À la 45e et à la
90e, l'arbitre affiche ce que les faits de la période valent (buts,
cartons, penaltys ici ; remplacements et blessures aussi dans le moteur
A), avec la règle mesurée sur 200 matchs réels (`simulation.additionnel`).
Le match dure 90 + n minutes, les événements portent `lib` (« 45+2 »,
« 90+4 ») à côté de leur minute brute, et les délais de reprise sont à
leur vraie valeur (`DELAIS`) : 94,5 minutes de match, 57,4 de ballon
vivant.

**Le repli en sprint.** Un joueur de forme pris haut à la perte
revenait vers sa place à 3,3 m/s, le trot de la forme : le latéral
trottinait pendant que le ballon traversait le terrain, et on le voyait
« suivre le ballon jusqu'à l'autre bout ». Sans le ballon, loin de sa
place et devant elle, il revient à 7 m/s (`REPLI_SPRINT`), et sa place
file devant lui à la même vitesse. Un défenseur ne coupe pas non plus
une ligne de passe à plus de douze mètres devant sa ligne : c'est un
milieu qui coupe, comme c'est un milieu qui presse là-haut. Mesuré sur un
match : les latéraux sont hors de leur zone 3,7 % du temps sans ballon
au lieu de 5,6, et les épisodes de trois secondes et plus passent de
huit à trois.

**La frappe part moins de travers.** Sept tirs sur dix partaient à
côté (réel : un sur trois) et un sur douze était contré (réel : un sur
quatre) : l'erreur d'angle (`TIR_SIGMA`) est réglée sur l'issue réelle
des tirs par distance, et un défenseur sur la trajectoire contre deux
fois sur trois à deux mètres (`CONTRE_TIR`) — docs/TACTIQUE.md § 16.

**Qui court** (docs/TACTIQUE.md § 17). Les trois leviers du travail
sans ballon de la carte (volume, pressing, récupération : mesures FotMob
rangées par poste) arrivent enfin au moteur — la fiche réduite pour le
match les perdait, tout le monde jouait à 0,5. Le volume décide du repli
(4,5 m/s à 7), de la place sans ballon d'un attaquant (ancrée à
quarante-deux mètres, elle ne suit la ligne qu'à la mesure du volume),
du pressing par à-coups (2 s + 4 s × volume, puis on souffle), de qui
double, coupe et va au ballon libre, et de la zone morte d'un joueur de
forme. Mesuré (`outils/course_moteur.py`) : Vinícius 10,0 km (réel 9,6),
Doué 12,7 (11,5), Mbappé 8,5 (9,0) ; sans ballon, Vinícius court 4,1 km
et Doué 6,4.

**Le gardien libéro et la défense restante** (docs/TACTIQUE.md § 18).
Le gardien sort à la mesure de la distance du ballon (cinq mètres quand
il est au milieu de son camp, treize quand il est dans l'autre, plus
loin encore quand son équipe a le ballon : `GARDIEN_SORTIE`) et coulisse
en largeur (`GARDIEN_LARGEUR`) ; la défense restante joue à onze mètres
derrière le ballon et coulisse avec lui (`RESTANTE_RECUL`,
`RESTANTE_FINITION`, `RESTANTE_GLISSE`). Les centraux passent de 7 à 8
km et demi, le gardien de 0,8 à 3,7.

**Le style d'un club, et l'affinité** (docs/TACTIQUE.md § 19). La
tactique par défaut d'un club dans le bac vient de sa possession réelle
(`possession_club`, `profil_tactique`) : Paris en possession, bloc haut,
relance courte ; Albacete en direct, bloc bas, relance longue. Et chaque
carte garde le style de son club : un onze qui joue en possession avec
des joueurs de clubs de possession rate moins ses passes et se précipite
moins ; un onze direct avec des joueurs de clubs directs voit ses longues
partir plus droites et ses contres partir plus (`affinite_de`,
`AFFINITE`). Le bac affiche l'affinité des deux onze.

**L'attaquant travailleur n'est pas un milieu** (docs/TACTIQUE.md
§ 20) : il ne presse pas loin de lui (`ATTAQUANT_LOIN`), ne coupe qu'à
moins de dix mètres du ballon (`COUPE_ATTAQUANT`), ne redouble que sur un
couloir attaqué bas (`DOUBLE_PROFONDEUR`), et se place deux mètres plus
haut dans les blocs (`AILIER_BLOC`) : Doué passe de 13,3 à 11,4 km (réel
11,5). **Le latéral ne va pas à la touche sans le ballon** : sa place
s'arrête à vingt-cinq mètres de l'axe (`LATERAL_EXT_MAX`) et à quatre
mètres plus large que son vis-à-vis proche (`LATERAL_MARGE`,
`LATERAL_VIS_X`).

**Quatre détails** (docs/TACTIQUE.md § 21) : la touche est au latéral
du côté, sauf une sur six, rapide (`TOUCHE_LATERAL`) ; l'avant-centre
sans ballon reste six mètres devant le pivot (`BUTEUR_DEVANT`) ; sur une
sortie de but ou un gardien ballon en main, personne dans la surface,
sans zone morte à l'arrêt et en sortant au trot ; les ailiers en bloc
bas à douze mètres devant la ligne (`AILIER_BLOC`).

**Le poids du collectif** (docs/TACTIQUE.md § 22). Le collectif joue
sur les attributs collectifs de chacun — passe, contrôle, lecture
défensive (`COLLECTIF_ATTRIBUTS`, `COLLECTIF_OVR` : ±10 points aux
extrêmes) — et laisse la finition, le dribble, la vitesse et le gardien
aux individualités ; trois leviers directs à côté (`COLLECTIF_PASSE`,
`COLLECTIF_APPEL`, `COLLECTIF_BLOC`) et un curseur (`COLLECTIF_POIDS`).
Mesuré : un PSG à 0,95 fait jeu égal avec un Real à 0,35 qui a sept
points d'OVR de plus, et ce Real bat encore un Inter rodé.

**D'où viennent les buts** (docs/TACTIQUE.md § 23). Le moteur prenait
ses buts de 11-18 m, dans un trou que la ligne laissait ouvert près du
but ; réel, 58 % des buts viennent de moins de onze mètres. La ligne
garde un second segment près du but (`LIGNE_PRES` : ballon à 20 m,
ligne à 14), le marqueur du porteur sort fermer la frappe quand le
presseur est battu (`PORTEUR_PRESSE`, `PORTEUR_FERME`), les centres du
fond sont remis en retrait au sol vers le point de penalty et frappés
dans la foulée (`CENTRE_FOND`, `CENTRE_BAS`, `CENTRE_BAS_ZONE`,
`CENTRE_BAS_PORTEE`, `CENTRE_BAS_TIR` ; l'événement `centre` porte
`bas`), la tête vers le but est plus forte (`TETE_TIR`), et l'envie de
frapper de 11-18 m baisse (`TIR_PROCHE`, `TIR_PRESSION`). Le banc
général de 48 matchs passe de 3,35 buts et 29 tirs à 2,52 buts et 26
tirs (réel : 2,8 à 3,2, 26), et le collectif double l'écart de Paris
contre le Real (+0,66 but contre +0,28 sans).

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

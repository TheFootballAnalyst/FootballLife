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

État après le second retour à l'œil (8 matchs, graine 11) :

| mesure | simulé | cible | lecture |
|---|---|---|---|
| buts | 3,5 | 2,8 | proche |
| tirs | 31,5 | 25 | un peu trop : l'occasion se prend vite |
| tirs cadrés | 15 | 8,5 | trop précis |
| passes | 1 355 | 900 | possessions encore trop courtes (65 min de jeu effectif, réel 57) |
| réussite des passes | 79 % | 83 % | proche, depuis que les ballons longs retombent sur le receveur |
| corners | 1,4 | 10 | pas assez de déviations et de dégagements |
| fautes | 26 | 22 | proche |
| hors-jeu | 0,8 | 3,5 | les appels restent trop sages |
| distance par joueur | 13,0 km | 10,5 km | on court trop pour se replacer |
| pointe médiane | 31,8 km/h | 31,8 km/h | juste (corrélation 0,97 avec la note EA) |
| sprint par joueur | 178 m | 190 m | juste |
| possession du dominant | 52 % | 58 % | les matchs sont trop équilibrés |
| tacles | 39 | 32 | proche |
| cartons jaunes | 5,4 | 4 | un peu trop |

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
et les consignes par ligne) se règle dans le bac, équipe par équipe, et
se voit. Bloc haut : la défense se tient six mètres derrière le ballon,
jusqu'au milieu adverse, et dans le camp adverse les deux joueurs qui
suivent le presseur prennent chacun un homme au contact — le pressing
en un pour un. Bloc bas : seize mètres derrière, jamais au-delà de sa
propre moitié, on contient à trois mètres tant que le ballon est loin.
Tempo possession : on garde le ballon plus longtemps et on passe court ;
direct : on lâche vite et la longue coûte moins. Risque offensif : plus
d'appels dans le dos. Latéraux « bas » : ils ne montent pas ; ailiers
« intérieur » : ils rentrent ; milieux « projection » : la ligne monte.

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

**La ligne tient.** Un défenseur qui suit un homme ne descend jamais
sous sa ligne (sauf dans sa surface) : le hors-jeu se joue en ligne, plus
personne ne remet les attaquants en jeu depuis derrière. Un central ne
part pas presser ou chasser un ballon à plus de vingt-deux mètres de sa
ligne si un milieu peut y aller.

**L'occasion se prend.** Dans les trente derniers mètres le porteur
décide plus vite, et une frappe vaut plus quand rien ne bouche l'axe ;
l'homme libre près du but vaut plus qu'un soutien couvert.

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

**La forme.** Trois lignes qui se tiennent par rapport au ballon : la
défense onze mètres derrière quand elle défend (jamais plus bas que sa
surface, jamais plus haut que le milieu), quinze mètres derrière quand
elle attaque ; le milieu et l'attaque s'étagent devant elle. Chacun
garde dans sa ligne l'écart qu'il a au repos (le pivot derrière, le
meneur devant), et la largeur coulisse vers le ballon.

**Les rôles.** Sans ballon, deux soutiens à onze mètres du porteur, à
angle ; des appels dans le dos par fenêtres (un attaquant un cinquième
du temps), qui s'arrêtent un mètre et demi avant la ligne de hors-jeu ;
le plus proche presse et contient à un mètre et demi, le second coupe
la ligne vers le soutien le plus dangereux, les autres marquent en zone
en se mettant entre l'adversaire et leur but ; le plus proche de chaque
camp chasse un ballon libre là où il va s'arrêter ; le gardien ferme
l'angle, sort sur un ballon libre dans sa surface, et sur une frappe va
au point où elle croise sa ligne.

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

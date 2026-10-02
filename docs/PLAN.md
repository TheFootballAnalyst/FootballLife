# Le plan global

Ce qu'on a : un moteur de match mesuré sur le réel (`docs/MOTEUR_B.md`,
`docs/TACTIQUE.md`), un jeu de cartes dont les cartes bougent avec les
vraies performances, un lobby classé, un mode solo en vraies
compétitions, un marché, des packs — et un écran en français, des noms
réels qu'on n'a pas le droit de vendre, une économie avec un trou
(`docs/ECONOMIE.md`). Ce document dit **quoi améliorer, dans quel ordre,
et pourquoi**, en six chantiers. Les durées sont des journées de
travail de ma part ; les décisions qui sont à toi sont marquées
**[toi]**.

## Les six chantiers en une page

| # | chantier | ce que ça change | durée | avant quoi |
|---|---|---|---|---|
| 1 | **L'économie** | plus de trou, des gains qui récompensent chaque session, des packs à cinq cartes | 3 j | tout test avec de vrais joueurs |
| 2 | **Autour du terrain** : la boucle de jeu | une raison de revenir chaque jour et chaque semaine (objectifs, saison vivante, progression des cartes, blessures, dialogue) | 12 j | la mise en ligne |
| 3 | **Les langues** | un jeu qui se lit en sept langues, sans retoucher le code pour en ajouter une | 5 j + 1 j par langue | le monde |
| 4 | **Les droits et les mods** | des cartes fictives calculées sur le réel, les vrais noms par mod chez le joueur | 8 j | toute vente |
| 5 | **En ligne** | comptes, limites du gratuit, premium, serveur | 10 j | le business |
| 6 | **Le terrain** (en continu) | blessures dans le moteur B, retrait du moteur A, renversements, dialogue | au fil de l'eau | — |

**L'ordre** : 1 → 2 → 3 → 4 → 5, le 6 en parallèle. L'économie
d'abord parce qu'elle est courte et qu'on ne peut rien tester sans
elle ; la boucle de jeu ensuite parce que c'est ce qui décide si on
revient ; les langues et les droits avant la mise en ligne parce
qu'ils touchent tous les écrans (les faire après, c'est tout refaire) ;
le business en dernier parce qu'il n'a de sens que sur un jeu qu'on a
envie de rejouer et qu'on a le droit de vendre.

## 1. L'économie (3 jours)

Détaillé dans `docs/ECONOMIE.md`. Dans l'ordre :

1. **Fermer le trou** : la banque rachète à 25 %, les packs sont prixés
   sur leur valeur attendue (Bronze 25 M€, Argent 60, Or 90, Élite 250),
   plus aucun pack ne se revend à profit. Une heure.
2. **Les primes de match** : selon le rythme (×2 : 6 M€ la victoire, 3 le
   nul, 1,5 la défaite ; ×4 la moitié ; ×8 le quart), +50 % contre un
   adversaire mieux classé ; les compétitions pondérées par la force du
   champ ; le lobby classé qui paie aussi. Une demi-journée.
3. **Le quotidien** : un pack Bronze par jour de connexion, un Argent au
   septième jour d'affilée. Une demi-journée.
4. **Les packs à cinq cartes** avec garanties lisibles et chances
   affichées ; la fusion des doublons (trois copies → une carte +1). Une
   journée.
5. **Le départ** : un onze tiré au sort à 56 de moyenne avec un ou deux
   espoirs, 30 M€ en caisse. Une demi-journée.
6. **Mesurer** : une campagne jouée de bout en bout, et le temps qu'il
   faut pour un pack Or. Les durées visées (une récompense par session,
   une carte qui change le onze toutes les deux heures, une équipe
   européenne en 40-60 h) se règlent là, pas sur le papier.

**[toi]** : le taux 1 € = 10 M€ et les prix réels, dès maintenant ou au
chantier 5.

## 2. Autour du terrain : la boucle de jeu (12 jours)

C'est là que tu m'as demandé des initiatives. La question à laquelle
tout doit répondre : **pourquoi est-ce que je reviens demain, et la
semaine prochaine ?** Aujourd'hui le jeu répond « pour jouer un match »
; il faut qu'il réponde « parce que quelque chose m'attend ». Six
mécaniques, par ordre de valeur sur effort.

**2.1 La saison vivante (3 j). — Fait** : `/api/journee/club`, le
panneau en tête de l'écran Journée, le point sur l'onglet. C'est ce que personne d'autre n'a : tes
cartes sont de vrais joueurs et elles **bougent chaque semaine avec
leurs vrais matchs**. Le jeu le fait déjà dans la base (le pipeline, les
journées) mais ne le montre pas comme un événement. Proposition : un
écran **« La journée »** le lundi (ou à chaque calcul de journée) : ce
qui a bougé dans ton effectif (+2 pour celui qui a marqué deux fois, −1
pour celui qui a été sorti à la mi-temps), la carte révélation de la
semaine (la plus grosse hausse du jeu), tes cartes blessées en vrai
(elles jouent, mais à 90 %), et un **pack de la journée** si tu t'es
connecté. Le joueur qui suit le vrai football a une raison de revenir
qui ne dépend pas de nous.

**2.2 Les objectifs de club (2 j). — Fait** : `solo.tirer_objectifs`
(classement, buts, domicile ; en coupe d'Europe le tour à atteindre),
suivis dans l'état de la campagne, payés à la clôture, le titre quand
les trois sont remplis (`equipe.titres`). Les défis de la semaine
restent à faire. Au début d'une campagne, le club te
fixe **trois objectifs** tirés selon ta force : « finir dans les six »,
« marquer 50 buts », « aligner trois joueurs de moins de 23 ans dans dix
matchs », « ne pas perdre à domicile ». Chacun paie (M€ et un pack), et
les trois réussis donnent un titre affiché sur ton profil. C'est ce qui
donne un sens à un match de milieu de tableau en février. Même chose en
plus court pour le classé : des **défis de la semaine** (« gagne un
match avec un onze de moins de 65 », « marque de la tête ») qui
poussent à varier le jeu.

**2.3 La progression des cartes (2 j). — Fait** (sans fusion : un
doublon se vend, c'est tout). Deux mécaniques, lisibles sur la carte :
la **forme** (une carte dont le vrai joueur enchaîne trois bons matchs
notés gagne +1 temporaire et +2 sur chaque attribut en match, trois
mauvais −1 : `simulation.forme_cartes`, le badge « en forme » dans le
club), et la **cohésion** (le collectif mesuré, § 22 de TACTIQUE.md,
compte les minutes jouées ensemble en vrai ; on ajoute les minutes
jouées ensemble *dans le jeu*, table `cohesion_jeu` remplie à chaque
clôture, `emergent.cohesion_jeu`, et le match prend le meilleur des
deux : un onze qu'on garde se rode, et le collectif fait des buts —
mesuré au § 22). Résultat : on a envie de garder ses joueurs, pas
seulement d'en acheter de meilleurs.

**2.4 Blessures, suspensions, fatigue d'un match à l'autre (3 j). — Fait.**
Le moteur B n'avait pas de blessures (le moteur A les garde). Il fallait : les
blessures en match (une par match et demi en vrai, avec l'arrêt du jeu
qu'on a déjà), les **suspensions** (deux jaunes, un rouge : le joueur
manque le match suivant), et la **fatigue qui reste** : un joueur qui a
joué 90 minutes hier part à 85 % d'endurance ; donc on fait tourner, et
le banc de sept sert à quelque chose. C'est la mécanique qui fait
exister l'effectif de 18 au lieu d'un onze figé.

Le dessin retenu : dans le moteur B, une blessure est un arrêt de jeu
(`DELAIS["blessure"]`, la reprise à celui qui avait le ballon), le
blessé sort ; le camp de la machine fait entrer le premier du banc à
son poste, le camp d'un humain reste à dix tant qu'il n'a pas nommé
l'entrant (`attente`, l'écran s'arrête en solo comme avec le moteur A).
L'état d'une carte entre deux matchs vit dans une table `etat_carte`
(équipe, carte : jaunes cumulés, matchs de suspension, matchs de
blessure, fatigue reportée), écrite à chaque clôture : un rouge ou trois
jaunes suspendent pour le match suivant, une blessure prive de un à
trois matchs, et la fatigue de fin de match se reporte pour un tiers au
coup d'envoi suivant (un joueur qui a tout joué repart à 85 %), remise à
zéro par un match sans jouer. Le onze refuse un suspendu ou un blessé en
le nommant ; le club les montre (badges « susp. », « blessé », « fatigué »).
Constantes : `emergent.BLESSURE_PAR_MATCH` (0,3 par match : un peu
moins que le réel, parce qu'un onze du jeu n'a que sept remplaçants),
`lobby.JAUNES_SUSPENSION`, `lobby.BLESSURE_MATCHS`, `lobby.FATIGUE_REPORT`.
Un blessé est repéré par (camp, carte) dans le moteur : deux clubs
peuvent aligner la même carte l'un contre l'autre.

**2.5 La boîte de dialogue (3 j). — Fait.** Le point 2 du plan précédent : parler
à ses joueurs pendant le match en français (« Hakimi, cherche Dembélé
dans l'axe », « on presse haut », « Dembélé, décroche »), traduit en
leviers du moteur avec une confirmation (« Hakimi cherchera Dembélé
dans l'axe »), sans intelligence artificielle en ligne (le jeu marche
hors ligne). C'est l'identité d'entraîneur du jeu, et c'est ce qu'on
montre en vidéo. (Et c'est le premier écran à penser multilingue, voir
le chantier 3.)

Le dessin retenu : `jeu/dialogue.py`, des règles et un vocabulaire par
langue (`VOCABULAIRE["fr"]`, une autre langue est une autre table). Une
phrase est traduite en un levier QUE LE MOTEUR A DÉJÀ — les trois axes
(« on presse haut », « on joue direct », « on ferme »), les consignes
par ligne (« les latéraux restent derrière »), un joueur nommé qui
parle pour sa ligne (« Hakimi, reste derrière » → les latéraux, et la
confirmation le dit), le marquage (« marquez Mbappé »), un changement
(« Kolo Muani remplace Dembélé »), une permutation (« Hakimi et Mendes
permutent »), la formation (« on passe en 4-4-2 »), la causerie à la
pause (« réveillez-vous »). Ce que le moteur ne sait pas faire est dit
(« cherche Dembélé dans l'axe » : pas de consigne joueur-vers-joueur),
et une phrase incomprise reçoit quatre exemples pris dans la situation.
`lobby.dire` applique le levier comme un clic (mêmes règles, mêmes
refus en clair), routes `/api/lobby/dire` et `/api/solo/dire`, la boîte
est en tête du panneau Ajuster du match.

**2.6 Jouer avec les autres (en option, 2 j).** Les ligues privées
existent déjà pour le fantasy ; les ouvrir au classé : une **coupe
entre amis** hebdomadaire (huit joueurs, trois tours, un pack au
vainqueur), et un classement du club entre amis. C'est le levier de
bouche à oreille.

Ce que je ne propose pas : l'entraînement (une jauge qui monte en
cliquant), les contrats, les blessures longue durée, le mercato à
dates. Ce sont des mécaniques de Football Manager qui demandent du temps
sans rapport avec le plaisir d'un jeu de cartes, et qui concurrencent la
saison vivante au lieu de la servir.

**[toi]** : l'ordre entre 2.4 et 2.5 ; la coupe entre amis maintenant ou
avec le chantier 5.

## 3. Les langues (5 jours, puis 1 jour par langue) — Fait, français et anglais

**Fait** : le dictionnaire par langue (`web/app/static/lang/fr.json`,
`en.json`, ~800 clés), `t("cle", {param})` et les formes du pluriel,
`index.html` par attributs `data-t`, le sélecteur dans la barre (le choix
dans le navigateur, sinon sa langue), les erreurs du serveur et des règles
en codes (`jeu/messages.py`, `{"code", "params", "message"}`), le
commentaire du moteur B par gabarits (`direct._gabarit`), le style, la
lecture de l'adversaire, les objectifs, les récompenses et les phases en
codes à côté du français, la boîte de dialogue en anglais
(`VOCABULAIRE["en"]`), la pseudo-traduction (`fl_langue = "xx"`), le test
de cohérence des dictionnaires (`jeu/tests/test_langues.py`) et un passage
dans Chromium sur chaque écran dans les trois langues. Le guide pour une
langue de plus : `docs/LANGUES.md`. Reste : le commentaire du moteur A
(jusqu'à son retrait), les titres gagnés déjà écrits en base, et une
relecture par un joueur natif pour l'anglais.


**L'état.** Tout est en français, et dans le code : 336 textes dans
l'écran (`app.js`), 28 lignes dans `index.html`, 49 messages d'erreur du
serveur, 63 messages des règles (lobby, marché, solo), 93 phrases de
commentaire du match, 22 textes du direct. Environ **600 textes**.

**L'architecture**, pour qu'ajouter une langue soit un fichier, pas du
code :
- **L'écran** : un dictionnaire par langue (`static/lang/fr.json`,
  `en.json`, …), une fonction `t("cle", {nom: "Hakimi"})` ; le français
  devient la langue source, chaque texte de l'écran passe par une clé.
  La langue se choisit dans le profil, et par défaut c'est celle du
  navigateur.
- **Le serveur** ne renvoie plus des phrases mais des **codes**
  (`budget_insuffisant`, avec le montant en paramètre) : c'est l'écran
  qui traduit. Même chose pour les règles.
- **Le commentaire du match** : la feuille porte déjà le type
  d'événement, le joueur, la minute, le xG ; les phrases se construisent
  dans l'écran à partir de **gabarits par langue** (« {nom} frappe de
  {distance} m »), avec les accords simples (pluriels) gérés par
  gabarit. Le commentaire du moteur A (93 phrases en français dans
  `simulation.py`) se garde en français jusqu'au retrait du moteur A
  (chantier 6).
- **Les noms de joueurs et de clubs** ne se traduisent pas ; les
  **postes** (« Ailier droit »), les **consignes**, les **causeries**,
  les **compétitions** si.
- Les nombres et dates au format de la langue ; pas d'écriture de
  droite à gauche au départ (l'arabe viendra avec un travail de mise en
  page à part).

**Les langues**, dans l'ordre des championnats couverts et des marchés
du jeu : **anglais** (la langue pivot : toute traduction suivante part
de l'anglais), **espagnol**, **portugais du Brésil**, **allemand**,
**italien**, **turc**, **néerlandais**. Je fais la première passe de
chaque langue ; il faut ensuite **un relecteur qui joue** par langue (un
joueur natif qui fait une campagne et corrige : un jeu traduit sans
joueur se repère en trois écrans).

**La méthode** : extraire les 600 textes (2 j), brancher les clés et les
codes (2 j), le commentaire par gabarits (1 j) ; puis chaque langue : la
première passe (une demi-journée), la relecture par un joueur, les
retours (une demi-journée). Un test de **pseudo-traduction** (chaque
texte allongé de 30 % avec des accents) attrape les écrans qui
débordent.

**[toi]** : la liste des langues et l'ordre ; trouver un relecteur par
langue.

## 4. Les droits et les mods (8 jours) — Fait, sauf les données sous contrat

**Fait** (`docs/MODS.md`) : le générateur de noms par nationalité
(`jeu/fictif.py`, 30 groupes, un nom composé une fois sur quatre, jamais
un vrai nom de la base, jamais deux cartes du même nom), les clubs au nom
de leur ville et de leur année quand il le faut, les compétitions au nom
du pays (traduit par l'écran), les avatars et les blasons dessinés
(`jeu/avatar.py`), le monde comme paramètre de la base, réversible
(`lancer.py --fictif / --reel`), le chargeur de mods (`mods/noms.csv`,
`clubs.csv`, `competitions.csv`, `portraits/`, `logos/`). Reste le point 5.

Détaillé dans `docs/ECONOMIE.md` § 5. Dans l'ordre :
1. **Le générateur de noms** fictifs, déterministe, par nationalité, sans
   ressemblance avec le vrai (1 j).
2. **Les clubs et compétitions** au nom de la ville et du pays, écussons
   et maillots dessinés par le jeu (le dessin des maillots existe) (1 j).
3. **Les portraits générés** : un avatar par carte (peau, cheveux, barbe,
   forme), dans le style des cartes (3 j, c'est du dessin).
4. **Le chargeur de mods** : `mods/noms.csv`, `mods/portraits/`,
   `mods/clubs.csv` lus s'ils existent ; l'outil de téléchargement des
   portraits sort du jeu et devient un outil de mod (1 j).
5. **Les données sous contrat** : brancher un fournisseur (API-Football
   ou Sportmonks) sur l'importeur, le barème ne change pas (2 j, plus
   l'abonnement au fournisseur).

Le jeu local garde l'option « réel » tant qu'on ne vend rien ; la
version mise en ligne part fictive.

**[toi]** : le fournisseur de données (et son coût mensuel) ; un avis
juridique avant la mise en ligne.

## 5. En ligne (10 jours) — Fait, sauf le test fermé

**Fait** (`docs/EN_LIGNE.md`) : les comptes avec courriel et date de
naissance, le mot de passe oublié par lien (courriel ou journal), les
mineurs sans achat ; les limites du gratuit et le premium
(`jeu/comptes.py`, actifs par `--limites`) ; le paiement par Stripe
Checkout avec webhook signé, ou manuel pour un test fermé
(`jeu/paiement.py`) ; les sauvegardes (`outils/sauvegarde.py`) et la
marche à suivre serveur. Reste le point 5, qui est un mois de jeu.

Détaillé dans `docs/ECONOMIE.md` § 6.
1. **Les comptes** : inscription par courriel, mot de passe oublié (on
   l'a vécu), un seul club par compte, les mineurs (date de naissance, pas
   d'achat) (2 j).
2. **Les limites du gratuit** : matchs de campagne par jour, packs du
   jour, enchères en cours ; et le **premium** à 4,99 €/mois (3 j).
3. **Le paiement** : Stripe pour l'abonnement et les packs (sans tirage
   aléatoire payant : abonnement, M€, cosmétiques, choix de carte) (2 j).
4. **Le serveur** : un VPS, le moteur dans des processus séparés, les
   sauvegardes, les mises à jour sans couper un match en cours (le match
   vivant se rejoue depuis sa chronologie : on l'a) (2 j).
5. **Le test fermé** : une centaine de joueurs, gratuits, un mois ; on
   lit les durées (chantier 1.6) et on règle (1 j, et un mois de
   patience).

**[toi]** : le nom du jeu (on vend un nom), l'hébergeur, le pays de la
société (la loi sur les packs en dépend).

## 6. Le terrain, en continu

Tu me fais confiance là-dessus ; voilà ma liste, par ordre :
1. ~~Les blessures et suspensions dans le moteur B~~ (chantier 2.4, fait),
   puis ~~le retrait du moteur A du direct~~ (fait : un seul moteur du
   direct, l'ancien terrain 2D et sa simulation de jetons retirés de
   l'écran, le bandeau et la pop-up passés au terrain B ; le moteur A ne
   joue plus que les matchs d'une journée de campagne qu'on ne regarde
   pas, en une seconde).
2. **Les renversements** (TACTIQUE § 30) : le moteur renverse deux fois
   moins que le réel mais convertit deux fois plus derrière ; c'est la
   finition après renversement à mesurer et régler, puis la borne du côté
   opposé peut descendre à 10 m comme en vrai.
3. **Les paires défensives serrées** : la géométrie du duel, avec les
   vitesses.
4. ~~La boîte de dialogue~~ (chantier 2.5, fait) ; la suite, c'est une consigne
   joueur-vers-joueur dans le moteur (« cherche Dembélé dans l'axe »).
5. Et tout ce que tu vois dans le bac : chaque remarque devient une
   mesure avant d'être une règle, comme jusqu'ici.

## Le calendrier

| semaines | ce qui sort |
|---|---|
| 1 | économie corrigée, primes, pack du jour, packs à cinq cartes |
| 2–4 | la journée (saison vivante), objectifs de club, progression des cartes, blessures et suspensions dans le B |
| 5 | la boîte de dialogue |
| 6–7 | les langues : l'architecture, l'anglais, l'espagnol |
| 8–9 | cartes fictives, avatars, mods ; les autres langues au fil des relecteurs |
| 10–12 | comptes, gratuit limité, premium, paiement, serveur |
| 13 | test fermé |

Treize semaines de mon côté si on enchaîne ; les relectures de langues
et l'avis juridique dépendent d'autres gens. À chaque chantier, les
règles qu'on s'est données restent : mesurer avant, mesurer après, et
ne garder que ce qui bouge la mesure.

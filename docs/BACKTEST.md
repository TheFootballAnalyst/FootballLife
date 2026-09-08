# Backtest — saison 2025/26 rejouée hors ligne

Phase 1 de `ROADMAP.md`. Tout ce qui suit sort de :

```
python3 -m jeu.importer            # fotmob.db -> jeu/jeu_2526.sqlite (1 min 30)
python3 -m jeu.backtest            # -> out/cartes.csv, out/managers.csv, out/resume.json (0,2 s)
```

## Ce qui a été validé avant de jouer

**La note et les attributs reproduisent la chaîne de visuels à l'identique.**
Sur les 40 prestations de référence du 28/08 au 06/09/2026 : 40/40 notes
exactes, 240/240 attributs exacts. Le fichier est dans
`jeu/tests/donnees/` et le test tourne à chaque `pytest`.

Trois choses ont dû être corrigées pour y arriver, toutes documentées
dans `jeu/notation.py` :

- l'entrée de la note est `points` (brut × coefficient de poste), comparé
  aux seuils tels quels ;
- au-delà de p90 la courbe sature : `note = 8 + 2u/(1+u)` avec
  `u = (points − p90)/(p90 − médiane)`. Bruno Fernandes à 138 points fait
  9,5, pas 12 ;
- les attributs prennent les lignes telles que le moteur les écrit, sans
  rien diviser.

## Vérification sous p10

Ton échantillon de flops (65 prestations : les 40 pires du week-end, des
entrants de moins de 30 minutes, des joueurs exactement au p10, des
gardiens en négatif) a donné la règle exacte :
`note = max(1, 4 − 3 × min(écart, 1))` avec `écart = (p10 − points) /
|médiane − p10|`. 65/65 notes et 65/65 attributs exacts. Le fichier est
dans `jeu/tests/donnees/` avec les tops ; le test de régression couvre les
deux.

## Protocole

Pas de base 2024/25 disponible, donc la saison est coupée en deux :

| | journées | rôle |
|---|---|---|
| amorce | J1 à J17 | tient lieu de « saison précédente » pour valoriser les cartes |
| jeu | J18 à J34 | 17 journées jouées par des managers scriptés |

Périmètre retenu : **ligue globale**, les 2 371 joueurs des clubs des cinq
championnats, avec leurs matchs de championnat et de C1 (option a,
décision du porteur). Une journée de jeu = du premier coup d'envoi d'une
journée de Ligue 1 à la veille de la suivante ; les cinq championnats
jouent le même week-end, le milieu de semaine européen compte dans la
journée qui le précède.

Quatre managers, 15 cartes, 4-3-3, tous recrutés par la même règle
(maximiser la valeur totale sous budget et quotas, glouton lagrangien) ;
seule la *valeur* qu'ils donnent à une carte diffère :

- **naïf** : l'OVR, ce que le marché dit déjà ;
- **forme** : la production récente, points par journée sur les cinq
  dernières, absences comptées 0, avec un échantillon minimal de trois
  matchs pleins. C'est le manager qui sait qui produit vraiment ; il
  réajuste chaque semaine ;
- **oracle** : la production future sur la moitié jouée, une borne haute ;
- **hasard** ×5, effectif légal tiré au sort.

Une première version du manager « forme » cherchait les cartes dont la
forme dépassait l'OVR : sur 462 cartes de Ligue 1 ça marchait, sur 2 371
ça ramassait des coups de chance sur trois matchs et finissait au niveau
du hasard. Le critère de production avec échantillon a réglé le problème
aux deux périmètres.

## Réglages retenus

| constante | valeur | pourquoi |
|---|---|---|
| échelle OVR | calibrée sur le périmètre : p2 des moyennes → 40, p99,5 → 99 (global 25/26 : 4,90 → 7,69 ; Ligue 1 seule : 4,84 → 7,21) | les moyennes de saison sont resserrées, et chaque périmètre a sa distribution |
| prior / K | 5,5 / 10 matchs pleins | un inconnu est bon marché |
| EMA | α = 0,08, pondéré par minutes/60 | à 0,12 les prix bougeaient d'une bande par match |
| prix | ×2 tous les 8 OVR, plancher 0,5 | pente 6 rend les hausses trop lucratives |
| budget | **60** | le meilleur 15 global coûte 104 ; à 100 le naïf recolle sur le forme (+8 % seulement), à 60 l'écart est de 30 % |

## Résultats, ligue globale (J18–J34, budget 60)

| manager | points | valeur finale (départ 60) |
|---|---|---|
| oracle | 1 980 | 237 |
| **forme** | **1 810** | **206** |
| naïf | 1 392 | 143 |
| hasard (moyenne de 5) | 732 | 62 |

Même ordre en Ligue 1 seule à 40 crédits : oracle 1 609, forme 1 496,
naïf 1 037, hasard 687.

Réponses aux quatre questions de `GAME_DESIGN.md` :

1. **L'informé bat le naïf**, de 30 % en points et de 44 % en valeur. Le
   hasard est loin derrière. L'oracle garde 9 % sur l'informé : il reste
   quelque chose à savoir. C'est l'ordre voulu.
2. **Plancher / plafond.** 551 titulaires (≥ 450 min) sur 2 371 finissent
   au prix plancher de 0,5, le quart bas du périmètre : indifférencié mais
   pas gênant. Six cartes touchent 97 et plus, quatre sont écrêtées à 99
   (Kane, Kimmich, Gabriel, Yamal) : les parcours de C1 du printemps
   dépassent le haut de l'échelle calibrée sur la première moitié. Avec
   une vraie saison d'amorce le haut sera mieux placé.
3. **Score d'équipe.** Médiane 51 par journée, sous les 66 visés, parce
   que les managers scriptés alignent sans regarder qui joue : 0,6 à 1,7
   remplacements automatiques par journée. `SCORE_REFERENCE = 60` est à
   revoir une fois des vrais managers observés.
4. **Banc.** Les remplacements automatiques se déclenchent presque chaque
   journée ; l'ordre du banc compte.

## La C1 dans la note, périmètre global

En Ligue 1 seule, les huit plus fortes hausses étaient toutes des joueurs
du PSG (coefficient de compétition 2,0 × coefficient de tour jusqu'à 2,2,
tous deux dans la note). En ligue globale l'effet se répartit :

| joueur | OVR J17 → J34 | prix |
|---|---|---|
| William Saliba | 72 → 98 | 2,8 → 26,9 |
| Joshua Kimmich | 81 → 99 | 6,2 → 29,3 |
| Ousmane Dembélé | 64 → 95 | 1,4 → 20,7 |
| Julián Álvarez | 67 → 93 | 1,8 → 17,4 |
| Elliot Anderson | 79 → 94 | 5,2 → 19,0 |

Arsenal, Bayern, Barcelone, PSG, Atlético, Nottingham : le printemps
européen reste le moteur des plus-values, mais il n'y a plus un seul club
à acheter. Le porteur a tranché pour cette option (a) : le barème reste
tel quel, la C1 est le sommet et anticiper les parcours européens fait
partie du jeu.

## Limites du protocole

- L'amorce sur une demi-saison sous-estime les échantillons : avec une
  vraie saison précédente, K = 10 pèsera moins et les OVR de départ seront
  plus étalés, et le haut de l'échelle sera mieux placé.
- Les managers scriptés ne regardent ni les blessures ni les calendriers ;
  leurs scores absolus sont bas. Les écarts *entre* stratégies sont ce qui
  compte.

## Reproduire

```
python3 -m jeu.importer --fotmob moteur/fotmob.db --jeu jeu/jeu_2526.sqlite
python3 -m jeu.backtest --ligue 0 --amorce 1-17 --jouer 18-34 --sortie out/
python3 -m jeu.backtest --ligue 53 ...          # Ligue 1 seule, pour comparer
```

Les constantes se changent dans `jeu/evolution.py` ; `out/resume.json`
rappelle celles qui ont servi.

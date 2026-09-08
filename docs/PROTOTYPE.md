# Prototype jouable dans le navigateur

URL : https://claude.ai/code/artifact/b9ea1467-fd7d-41ab-b2fd-c415d4b91fd3
(privée par défaut ; à partager depuis le menu de la page).

Une seule page HTML, sans serveur : la seconde moitié de la saison 2025/26
(J18 à J34) rejouée avec les vraies notes du barème, les mêmes règles que
`jeu/scoring.py` et `jeu/evolution.py` réécrites en JavaScript. L'état de
la partie est gardé dans le navigateur ; le classement partagé passe par
la base de la page (capacité `db`).

| écran | ce qu'on y fait |
|---|---|
| Marché | 2 371 cartes, filtres, tri, fiche joueur (attributs, dernières notes, courbe de prix), achat/vente au prix courant |
| Équipe | formation, onze sur le terrain, capitaine, ordre du banc |
| Journée | jouer la journée : score, détail par joueur, entrants du banc, gain ; les cartes évoluent |
| Classement | contre les managers scriptés du backtest, et classement partagé entre joueurs |

## Reconstruire

```
python3 -m jeu.importer --fotmob moteur/fotmob_2526.db     # base du jeu
python3 -m jeu.backtest                                    # out/managers.csv (scores des bots)
python3 web/exporter.py                                    # out/proto/data.json + thumbs.json
python3 web/construire.py                                  # out/FootballLife.html (4,5 Mo)
```

`web/prototype.html` est le gabarit (interface et logique) ; les données
et les vignettes de portraits (72 px, 1 600 joueurs à 270 minutes et plus)
y sont injectées.

## Ce que le prototype n'est pas

Pas la phase 3 du plan. Il n'y a ni comptes, ni journées réelles qui
avancent avec le calendrier, ni pipeline hebdomadaire : c'est la saison
passée, rejouée à son rythme. Il sert à jouer avec les règles et
l'économie avant de construire le vrai site.

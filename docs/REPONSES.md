# Réponses aux questions de Claude Code

## 1. Le regroupement des libellés en familles — CONFIRMÉ

C'est le point qu'il fallait vérifier, et voici la table de référence exacte :
`moteur/familles_lignes.json`.

Ce sont **les mêmes libellés qui ont servi à calculer `echelles_attributs.json`**.
Il faut que `FAMILLE_LIGNE` corresponde à cette table, sinon les percentiles
ne mesureront pas ce qu'ils prétendent mesurer.

Onze familles, 40 libellés (« Duel gagne » a quitté Dribble : un défenseur central dominait l’attribut). Six pour les joueurs de champ — FIN, CRE, PRO,
DEF, DRI, CON — et six pour les gardiens — ARR, EVI, SOR, REL, BUT, plus PRO
partagé.

**Deux subtilités à ne pas manquer.**

Les libellés sont **sans accents** dans le barème : « Tir cadre », « Degagement »,
« Passe decisive ». La correspondance est une égalité stricte de chaîne.

Certains libellés appartiennent à **deux familles** : « Long ballon reussi » et
« Passe reussie » comptent à la fois en PRO et en REL. Ce n'est pas une erreur.

## 2. La cotation des attributs — POINT IMPORTANT

`echelles_attributs.json` a deux clés, `champ` et `gardien`, **pas une clé par
poste**. C'est délibéré : la finition ou le dribble ne dépendent pas du poste.
Un latéral doit être comparé à tous les joueurs de champ, sinon il monte à 92
en finition parce que ses pairs ne tirent pas non plus.

Il y a aussi un **plancher** à appliquer, sans quoi le résultat est faux.
Beaucoup de familles ont une majorité de valeurs nulles. Le code de référence :

```python
i = bisect.bisect_left(serie, x)
rang = i / max(len(serie) - 1, 1)
seuil = bisect.bisect_right(serie, 0.001) / max(len(serie) - 1, 1)
if seuil > 0.05 and rang > seuil:
    rang = 0.50 + 0.50 * (rang - seuil) / max(1 - seuil, .01)
elif seuil > 0.05:
    rang = 0.50 * rang / max(seuil, .01) * 0.6
note = int(round(40 + 59 * rang))
```

Sans ce plancher, un latéral ayant cadré un tir obtient 92 en finition. Avec,
il obtient 70.

## 3. Les décisions à valider

**Périmètre Ligue 1 plus C1** : bon choix.

**Une journée de jeu par journée de championnat** : cohérent.

**Bonus C1 dans la couche jeu, pas dans la note** : c'est juste, mais attention —
le barème pondère **déjà** par la compétition et par la force de l'adversaire.
Un but en C1 vaut plus qu'un but en championnat *dans la note elle-même*.
Ajouter 1,25 par-dessus compte donc la prime deux fois. À arbitrer.

**Valorisation, prix qui double tous les 8 de moyenne** : à backtester, comme
prévu. Une remarque : la note sur 10 est resserrée — la médiane vaut 6, le p90
vaut 8. Un écart de 8 points de moyenne n'existe pas. L'échelle de prix doit
se caler sur l'écart réel, de l'ordre de 4 à 8.

## 4. Fichiers fournis

| fichier | rôle |
|---|---|
| `familles_lignes.json` | la table de référence demandée |
| `topsflops_refs.json` | références du barème : duels défensifs, coefficients de match, calibrage |
| `ingest.py` | charge une feuille de match FotMob en base |
| `corrige_postes_entrants.py` | corrige les postes des remplaçants, à lancer après chaque ingestion |

**Non fournis, à récupérer par le porteur du projet** : `fotmob.db` (une base par
saison, 300 à 550 Mo chacune) et le cache des feuilles de match `cache/matches/`.
Ils sont trop lourds pour ce transfert.

#!/usr/bin/env python3
"""
BAREME STATS AVANCEES — saison 2025/26 (fotmob.db)

Un point par action, pas un percentile. Chaque action d'un match vaut un
nombre de points fixe, multiplie par le poids de la competition et celui
du tour, puis par le coefficient de poste. Tout est cumulatif et date :
la sortie alimente directement le moteur de bar chart race.

    points(joueur, match) = coef_poste
                          x coef_competition x coef_tour
                          x  SOMME( valeur_action x points_action )

Trois lecons de reglage
-----------------------
1. Le coefficient de POSTE ne change rien au classement DANS un poste
   (tout le monde y est multiplie pareil). Il ne sert qu'a rendre les
   postes comparables entre eux. Il est donc calibre, pas decrete : on
   ramene le percentile 95 de chaque poste a 100 points. Un chiffre de 100
   se lit « niveau du 5 % superieur de ce poste », quel que soit l'effectif
   du poste — c'est tout l'interet d'un percentile sur un nombre fixe.
2. Les actions negatives sont indispensables. Sans elles, il suffit de
   tenter beaucoup pour monter : un dribbleur qui perd 8 ballons par
   match finirait devant un joueur propre.
3. Le poids du tour multiplie le poids de la competition. Un dribble en
   finale de Ligue des champions vaut 2,0 x 2,2 = 4,4 fois le meme
   dribble en Liga. C'est le point demande.

Usage (Windows) :
    py bareme_stats.py                    classement en points par 90 minutes
    py bareme_stats.py --paliers          effectifs par seuil de temps de jeu
    py bareme_stats.py --min 1800         change le seuil (defaut 1350)
    py bareme_stats.py --min-champ 1200   seuil de minutes en championnat (900)
    py bareme_stats.py --neutre           aucune ponderation de competition,
                                          de tour ni d'adversaire : stats
                                          brutes par 90 minutes
    py bareme_stats.py --volume           retire la prime d'excedent
    py bareme_stats.py --taux             excedent seul (non recommande)
    py bareme_stats.py --sans-matrice     laisse les parts par famille libres
                                          au lieu de les imposer
    py bareme_stats.py --recalibrer       recalcule les coefficients de poste
    py bareme_stats.py --xlsx             ecrit bareme_stats.xlsx
    py bareme_stats.py --events           ecrit bareme_stats_events.json

Sorties : bareme_stats_coefs.json, bareme_stats_events.json, bareme_stats.xlsx
"""

import json
import pathlib
import re
import sqlite3
import sys
import unicodedata
from collections import defaultdict

DB_PATH = pathlib.Path("fotmob.db")
COEFS = pathlib.Path("bareme_stats_coefs.json")
EVENTS = pathlib.Path("bareme_stats_events.json")
SEUIL_DEFAUT = 2300          # 25 matchs pleins — voir --paliers
                             # Releve de 1350 : a ce niveau, des echantillons
                             # de 21 matchs remontaient haut sur des evenements
                             # rares (deux sauvetages sur la ligne que le par 90
                             # transforme en bonus permanent).
SEUIL_CHAMPIONNAT = 900      # dont, au minimum, en championnat : voir main()
SEUIL_GARDIEN = 2250         # seuil propre aux gardiens : leur par 90 repose
                             # sur peu d'evenements par match, il lui faut plus
                             # de matiere. 2250 = 25 matchs pleins. Ce niveau
                             # ecarte les vraies doublures (Urbig 1650, Blaswich
                             # 1560) tout en gardant les gardiens qui se sont
                             # partage une saison a deux, comme Safonov (2370,
                             # dont 1020 en Ligue des champions) et Chevalier
                             # (2250). Descendre plus bas rouvre la porte aux
                             # echantillons de coupe nationale.
LIGUES = (47, 87, 55, 54, 53, 61, 57, 71)   # les 8 championnats collectes
CIBLE_CALIBRAGE = 100        # echelle de lecture
# Reference de calibrage : la moyenne des joueurs de RANG 2 a 5 de chaque
# poste, le meme rang partout. Un percentile ne tombe pas au meme rang selon
# l'effectif — le 98e centile visait le 6,6e defenseur central mais le 1er
# meneur — si bien que les postes peuples avaient une reference prise plus
# bas, donc plus faible, donc un sommet gonfle. Les lateraux en profitaient le
# plus (265 joueurs, reference au 5,3e). Un rang fixe supprime cet effet :
# le rapport entre le plus haut et le plus bas des sommets passe de 1,91 a 1,34.
RANGS_CALIBRAGE = (2, 5)
# Releve de 0,95 a 0,98. A 0,95 les postes etaient bien alignes AU MILIEU mais
# pas AU SOMMET : les buteurs ont une queue de distribution plus longue — les
# buts sont rares et concentres — si bien que Dembele sortait a 375 quand le
# meilleur meneur plafonnait a 117, un rapport de 3,2. En calant la reference
# plus haut, on compare des sommets et non des medians : le rapport tombe a
# 1,9. Aller a 0,99 le ramenerait a 1,6, mais la reference reposerait alors
# sur le 2e ou 3e joueur du poste, donc sur trop peu de monde.

# ---------------------------------------------------------------- section 1
# POINTS PAR ACTION. Une action, une valeur, quel que soit le poste.
# Les valeurs decimales sont voulues : une passe reussie ne peut pas peser
# comme un tacle, sinon un milieu recuperateur bat tout le monde au volume.
POINTS = {
    "Finition": {
        "goals":                        ("But",                          10.0),
        "expected_goals_non_penalty":   ("xG hors penalty (par unite)",   4.0),
        "ShotsOnTarget":                ("Tir cadre",                     1.3),
        "shots_woodwork":               ("Poteau ou barre",               1.0),
        # Deplaces depuis Creation : ce sont des TIRS. Les laisser en
        # Creation faisait baisser la note creative d'un attaquant qui
        # tire beaucoup.
        "ShotsOffTarget":               ("Tir non cadre",                -0.15),
        "blocked_shots":                ("Tir contre par un defenseur",  -0.10),
        "big_chance_missed_title":      ("Grosse occasion manquee",      -2.0),
        # G-xG est ajoute plus bas : c'est une difference, pas une cle de la
        # base. Il mesure la surperformance de finition, exactement comme
        # goals_prevented le fait pour les gardiens.
        "missed_penalty":               ("Penalty manque",               -5.0),
    },
    "Creation": {
        "assists":                      ("Passe decisive",                7.5),
        "expected_assists":             ("xA (par unite)",                3.0),
        "big_chance_created_team_title":("Grosse occasion creee",         2.0),
        "chances_created":              ("Occasion creee",                0.8),
        # Relevee de 0,2 a 0,8. C'est la seule metrique de PROGRESSION que
        # contient la base, et elle valait douze fois moins qu'un dribble : un
        # metronome comme Vitinha, premier des milieux europeens sur cette
        # ligne (14,1 par 90 contre 6,7 de mediane), n'etait paye pour rien.
        # Le retrait de la passe reussie avait deja supprime son autre marqueur.
        "passes_into_final_third":      ("Passe dans le dernier tiers",   0.3),
    },
    "Conduite": {
        "touches":                      ("Ballon touche",                 0.02),
        "penalties_won":                ("Penalty obtenu",                5.4),
        "was_fouled":                   ("Faute subie",                   0.4),
        "dispossessed":                 ("Ballon perdu au contact",      -0.5),
        "owngoal":                      ("But contre son camp",         -10.0),
    },
    "Defense": {
        "clearance_off_the_line":       ("Sauvetage sur la ligne",        5.0),
        "last_man_tackle":              ("Tacle du dernier defenseur",    3.0),
        "shot_blocks":                  ("Tir contre",                    1.5),
        
        "interceptions":                ("Interception",                  1.2),
        "clearances":                   ("Degagement",                    0.4),
        # Degagement de la tete : action defensive reelle, absente du bareme.
        "headed_clearance":             ("Degagement de la tete",         0.5),
        # Duels : solde et non volume — gagner beaucoup de duels en en perdant
        # autant ne dit rien. Les deux lignes se compensent exactement.
        "duel_won":                     ("Duel gagne",                    0.30),
        "duel_lost":                    ("Duel perdu",                   -0.30),
        "recoveries":                   ("Recuperation",                  0.25),
        # Le barème payait le VOLUME d'actions defensives, ce qui recompense
        # les defenseurs d'equipes dominees : plus on subit, plus on tacle.
        # Saliba est sous la mediane en tacles et en interceptions, et c'est
        # son merite — il n'a pas a defendre, et quand il doit, il ne se fait
        # pas prendre. On degonfle donc le volume et on paie la solidite :
        # ne pas se faire dribbler, ne pas commettre d'erreur, ne pas encaisser.
        "dribbled_past":                ("Dribble par l'adversaire",     -1.5),
        "fouls":                        ("Faute commise",                -0.8),
        "conceded_penalties":           ("Penalty concede",             -12.0),
        "errors_led_to_goal":           ("Erreur menant a un but",      -10.0),
    },
    # Famille reservee aux gardiens : leurs metriques n'ont pas d'equivalent.
    "Gardien": {
        "saved_penalties":              ("Penalty arrete",               10.0),
        # Revision : le volume d'arrets mesure surtout la faiblesse de la
        # defense devant. On le degonfle et on reporte le poids sur les buts
        # evites, seule ligne relative (mesuree contre le xGOT subi) et donc
        # independante du nombre de tirs affrontes.
        # Second reglage : a 20 points l'unite, les buts evites pesaient 61 %
        # du score de Batz contre 10 % chez Raya — le classement des gardiens
        # devenait le classement d'une seule metrique, elle-meme issue du
        # modele xGOT de FotMob. On redescend a 12 et on redonne du poids a
        # l'arret, sans revenir au volume brut de depart (2.0).
        "goals_prevented":              ("But evite vs xGOT (par unite)",25.0),
        "saves":                        ("Arret",                         0.80),
        "keeper_diving_save":           ("Arret plongeant",               1.2),
        "saves_inside_box":             ("Arret dans la surface",         0.6),
        "keeper_high_claim":            ("Sortie aerienne",               1.6),
        "keeper_sweeper":               ("Sortie dans le dos",            1.6),
        "punches":                      ("Degagement du poing",           0.8),
        "goals_conceded":               ("But encaisse",                 -0.4),
    },
}
# Multiplicateur applique aux actions de relance CHEZ LES GARDIENS seulement.
# Un gardien touche le ballon 30 a 40 fois par match et le jeu au pied
# distingue aujourd'hui un Raya d'un gardien classique ; le compter au tarif
# d'un joueur de champ revenait a ne pas le compter.
# Desactive apres essai : releve, le jeu au pied faisait passer Neuer et
# Dituro devant Raya et Martinez, et un gardien precis a la relance devancait
# un gardien qui arrete. La relance reste comptee au tarif commun, ce qui la
# maintient marginale — choix assume, le poste se juge d'abord aux arrets.
RELANCE_GK = {}

COEF_GARDIEN = 0.75        # echelle globale du poste de gardien
CLEAN_SHEET = 18.0        # gardien, match acheve sans encaisser (>= 60 min)
CLEAN_SHEET_DEF = 10.0    # idem pour un defenseur : c'est le resultat que la
                         # ligne defensive produit, et la seule mesure qui
                         # recompense de ne pas avoir eu a defendre.
POSTES_CLEAN_SHEET = ("Defenseur central",)   # lateraux retires

# ---------------------------------------------------------------- section 1 bis
# ACTIONS A TAUX DE REUSSITE. La table stat porte, pour ces cles, le nombre
# de reussites (value) ET le nombre de tentatives (total). On ne compte donc
# pas la reussite brute mais l'EXCEDENT sur le taux de reference du poste :
#
#     points = (reussites - taux_reference x tentatives) x valeur
#
# Un joueur qui gagne 60 % de ses duels au sol quand son poste en gagne 52 %
# marque sur les 8 % d'ecart, pas sur les 60 %. Un joueur sous la reference
# perd des points. C'est ce qui neutralise la prime a la possession : avoir
# beaucoup le ballon ne rapporte plus rien en soi, seul le fait de mieux
# s'en servir que ses pairs rapporte. Les taux de reference sont calcules
# sur la base, poste par poste, et ecrits dans le fichier de coefficients.
# (libelle, poids en mode excedent, poids en mode volume)
FRACTIONS = {
    "dribbles_succeeded":   ("Dribble reussi",       3.0,  1.5),
    "aerials_won":          ("Duel aerien gagne",    2.0,  0.7),
    "accurate_crosses":     ("Centre reussi",        2.0,  0.5),
    "ground_duels_won":     ("Duel au sol gagne",    0.0,  0.5),
    "long_balls_accurate":  ("Long ballon reussi",   1.0,  0.3),
    # Relance des gardiens : ce sont les deux seules cles a porter leurs
    # tentatives chez eux, donc les seules ou l'on peut juger la qualite et
    # pas seulement le volume. Elles etaient payees comme pour un joueur de
    # champ — 0,02 point la passe — alors que le jeu au pied est devenu une
    # competence majeure du poste. Poids releves plus bas via RELANCE_GK.
    # Remise apres coup : retiree une premiere fois parce qu'elle portait la
    # possession de l'equipe, elle prive surtout les joueurs dont c'est le
    # metier. Elle revient a son poids d'origine, avec la prime d'excedent sur
    # la reference du poste qui neutralise l'essentiel du biais de volume.
    "accurate_passes":      ("Passe reussie",        0.08, 0.02),
}
# Mode par defaut : volume. Le mode excedent (--taux) a ete implemente et
# mesure ; il AUGMENTE le biais de domination d'equipe au lieu de le reduire,
# parce que les joueurs des equipes dominantes sont aussi plus PRECIS que la
# reference de leur poste, pas seulement plus sollicites. Conserve pour
# comparaison, pas recommande.
# Mode retenu : mixte. Le volume reste le socle — cinq dribbles reussis valent
# cinq dribbles reussis — et une prime, ou un malus, s'y ajoute selon qu'on fait
# mieux ou moins bien que la reference de son poste. Repond au travers du taux
# brut, ou un joueur a 5/5 devancerait un joueur a 20/30 : ici l'excedent est
# proportionnel aux tentatives, donc le volume garde la main. Mesure : +1 a
# +2 points de correlation avec la domination d'equipe, soit le bruit.
# "volume" retire la prime, "taux" ne garde qu'elle (deconseille, +3 a +7).
# ---------------------------------------------------------------- progression
# Actions de progression, comptees PAR BALLON TOUCHE et non par 90 minutes.
#
# Mesure decisive : le volume de touches est correle a +0,38 avec la domination
# de l'equipe, celui des passes dans le dernier tiers a +0,11 — mais le RATIO
# passes dans le dernier tiers par touche est a -0,18. C'est la seule metrique
# du projet qui soit negativement correlee au poids du collectif : elle dit ce
# que le joueur fait du ballon, pas combien de ballons son equipe lui donne.
#
# On credite l'excedent sur le taux de reference du poste, comme pour les
# actions a taux : progression = (realisees - taux_ref x touches) x valeur.
# Desactive apres mesure. Diviser par les touches corrige le biais de volume
# en le RETOURNANT : ceux qui touchent beaucoup le ballon voient leur part de
# passes vers l'avant diluee. Rodri, qui touche enormement, tombait 4e des
# milieux defensifs derriere Locatelli et Xhaka ; Hakimi sortait du top 4 des
# lateraux. La correlation avec la domination d'equipe baissait bien (0,49 ->
# 0,43), mais au prix d'un classement que le terrain ne reconnait pas. Une
# mesure qui s'ameliore pendant que le resultat se degrade signale que le
# proxy mesure autre chose que ce qu'on croit.
# Remettre les valeurs ci-dessous pour reactiver.
PROGRESSION = {}
PROGRESSION_DESACTIVEE = {
    "passes_into_final_third": ("Passe dans le dernier tiers", 6.0),
    "touches_opp_box":         ("Touche dans la surface adverse", 3.0),
    "dribbles_succeeded":      ("Dribble reussi", 4.0),
}
FAMILLE_PROGRESSION = "Conduite"

# ---------------------------------------------------------------- construction
# xGBuildup (Understat) : somme des xG des sequences de tir ou le joueur a
# touche le ballon, TIREUR ET PASSEUR DECISIF EXCLUS. C'est la seule mesure
# disponible de la construction pure — celui qui lance l'action trois passes
# avant le but, que le bareme ne voyait pas.
#
# Trois precautions, sans lesquelles ca ferait plus de mal que de bien :
#   1. compte en EXCEDENT sur la norme du poste, jamais en volume : le top 8
#      brut est constitue de sept joueurs de City, Chelsea et Liverpool, ce
#      qui est exactement le biais de domination d'equipe qu'on a passe des
#      jours a faire baisser ;
#   2. rythme etabli sur les minutes de CHAMPIONNAT, seules couvertes par
#      Understat, puis rapporte au temps de jeu total ;
#   3. joueur sans donnee = zero, donc exactement neutre. Il ne gagne ni ne
#      perd, ce qui est le seul traitement honnete d'une couverture partielle.
UNDERSTAT = pathlib.Path("understat_joueurs.csv")
UNDERSTAT_ASSOC = pathlib.Path("understat_association.csv")
# Reglage a 0 par defaut, en attendant la mesure sur les vraies donnees
# Understat. Sur un jeu d'essai calibre pour ressembler a la donnee reelle
# — xGBuildup correle au volume de passes — l'ajout coute 4 a 9 points de
# correlation avec la domination d'equipe selon le poste, alors qu'il est
# deja compte en excedent sur la norme du poste. C'est la nature meme de la
# metrique : elle compte les sequences de tir de TON EQUIPE ou tu as touche
# le ballon. A activer si le classement obtenu vaut ce prix.
POIDS_BUILDUP = 0.0          # 25.0 pour activer
SEUIL_BUILDUP = 900          # minutes Understat minimales pour etablir un rythme

# Relevee de 8 a 20. Tir tente et touche dans la surface pesaient 17 % de la
# Finition des buteurs — plus que la surperformance elle-meme — alors que ce
# sont des mesures de volume : un attaquant qui traine dans la surface et tire
# n'importe comment y accumulait autant qu'un buteur froid. Les deux sont
# retirees, et le poids passe a la seule ligne qui mesure la QUALITE de
# finition. On garde la DIFFERENCE buts moins xG et non le rapport : le
# rapport est instable sur petit echantillon — 3 buts pour 1,2 xG donne 2,5,
# ce qui est du bruit — alors que la difference est proportionnelle au volume.
SURPERFORMANCE = 6.0
XG_PENALTY = 0.79            # xG d'un penalty (verifie : l'ecart xG total /
                             # xG hors penalty tombe sur des multiples exacts)
VALEUR_BUT = 10.0
# Championnats nationaux : leur coefficient est neutralise POUR LES GARDIENS.
# Un arret reste un arret ; le niveau du championnat dit la difficulte du jeu,
# pas celle d'un tir cadre. Les coupes d'Europe et les selections gardent le
# leur, elles opposent vraiment des plateaux differents.
CHAMPIONNATS_GK = {47, 87, 55, 54, 53, 57, 61, 71}
VALEUR_PENALTY = 5.0         # 10 x (1 - 0,79) : seul l'increment de reussite         # points par but marque au-dela de l'xG

# Donnees physiques, en points par unite d'ecart au rythme median du poste.
# Le nombre de sprints est le plus parlant : il distingue un joueur qui repete
# les efforts d'un joueur qui court beaucoup a allure constante.
PHYSIQUE = {
    "physical_metrics_number_of_sprints": ("Sprints", 6.0),
    "physical_metrics_sprinting":         ("Distance en sprint", 0.05),
    "physical_metrics_distance_covered":  ("Distance parcourue", 0.002),
    "physical_metrics_topspeed":          ("Vitesse de pointe", 3.0),
}
FAMILLE_PHYSIQUE = "Conduite"
# Desactive apres mesure. Le rythme est etabli sur les seuls matchs documentes
# — souvent deux ou trois — puis rapporte a une saison entiere : le bruit est
# multiplie par dix. Resultat teste : Goretzka 537 chez les milieux defensifs,
# Lee premier ailier droit, Mbappe 4e buteur. La donnee est bonne, la
# couverture ne permet pas de s'en servir. A rouvrir si FotMob l'etend.
POIDS_PHYSIQUE = False

MODE_FRACTION = "mixte"      # "volume" | "taux" | "mixte"
PART_EXCEDENT = 0.40         # poids de la prime d'excedent
MODE_TAUX = False
# La passe reussie a ete retiree de la Conduite : compter 2 000 passes a 0,02
# revenait a mesurer combien de fois le ballon arrivait au joueur, donc la
# possession de son equipe. Son retrait fait baisser la correlation avec la
# domination d'equipe de 0,05 chez les centraux et les relayeurs, 0,04 chez les
# 6, 0,03 chez les lateraux — le seul levier qui l'ait jamais fait descendre.
# Duels defensifs : la base ne fournit ni tentatives de tacle ni tentatives
# d'interception — ce sont des volumes bruts, et un volume eleve signale
# autant une equipe dominee qu'un bon defenseur. Mais tacle et « dribble par
# l'adversaire » sont les deux issues du MEME duel : leur somme donne les
# engagements, et le rapport un vrai taux de reussite. C'est la seule mesure
# de qualite defensive reconstructible a partir de cette base.
# Poids ramene de 8,0 a 3,0 le 27/08/2026 : a 8 cette ligne pesait 47 % de la
# famille Defense chez les milieux offensifs et 38 % chez les ailiers, contre
# 14 % chez les defenseurs centraux — elle recompensait donc l'efficacite sur
# un tout petit volume de duels. Mesure sur le Ballon d'or 2025 : l'ecart moyen
# passe de 4,00 a 3,42 places et le top 10 de 2,00 a 1,80.
DUELS_DEFENSIFS = ("matchstats.headers.tackles", "dribbled_past", 3.0)

# Passe reussie et long ballon basculent de Conduite vers Creation : ce sont
# des actions de distribution, pas de conduite de balle. La Conduite ne garde
# que ce qui se fait ballon au pied — dribble, penalty obtenu, faute subie,
# ballon perdu au contact — ce qui la rend enfin homogene.
FAMILLE_FRACTION = {
    "dribbles_succeeded": "Conduite", "accurate_passes": "Creation",
    "long_balls_accurate": "Creation", "accurate_crosses": "Creation",
    "ground_duels_won": "Defense", "aerials_won": "Defense",
}

# ---------------------------------------------------------------- section 2
# POIDS DE COMPETITION. Multiplie tout ce qui est produit dans le match.
# Table indexee par NOM de competition et non par identifiant : les id
# FotMob changent d'une saison a l'autre et une competition absente d'une
# base (l'Euro n'est ni dans 2024/25 ni dans 2025/26) doit quand meme avoir
# sa valeur prete pour le jour ou on remonte une autre saison.
COEF_COMPET_NOM = {
    # selections
    "world cup": 2.6,                  # releve de 2.2 : une Coupe du monde
    "euro": 2.2,                       # tous les quatre ans, et l'histoire du
    "copa america": 2.2,               # Ballon d'Or bascule dessus
    "africa cup of nations": 1.5,
    "asian cup": 1.3,
    "gold cup": 1.2,
    "uefa nations league a": 0.4,
    "uefa nations league": 0.36,
    # clubs, international
    "champions league": 2.0,
    "club world cup": 1.7,
    "europa league": 1.3,
    "uefa super cup": 1.2,
    "conference league": 1.0,
    # championnats — coefficient UEFA d'association sur cinq ans (classement
    # 2025, source uefa.com), ramene a 1.00 pour l'Angleterre :
    #   ENG 103.658  ITA 92.124  ESP 85.953  GER 82.902  FRA 75.534
    #   NED 65.762   POR 63.266  BEL 57.750  TUR 48.125
    "premier league": 1.000,      # Angleterre, reference
    "serie a": 0.844,             # Italie
    "laliga": 0.820,              # Espagne
    "bundesliga": 0.749,          # Allemagne
    "ligue 1": 0.634,             # France
    "eredivisie": 0.583,          # Pays-Bas
    "liga portugal": 0.540,       # Portugal
    "super lig": 0.381,           # Turquie
    "jupiler pro league": 0.493,  # Belgique
    # coupes nationales
    # coupes nationales : 80 % du coefficient de leur championnat
    "fa cup": 0.80, "coppa italia": 0.71, "copa del rey": 0.66,
    "dfb pokal": 0.64, "coupe de france": 0.58, "taca de portugal": 0.49,
    "efl cup": 0.70,
    "supercopa de espana": 0.66, "supercoppa": 0.71,
    "supercoppa italiana": 0.71, "trophee des champions": 0.58,
    "dfl supercup": 0.64, "community shield": 0.70,
}
COEF_DEFAUT = 0.4

# Coefficients MESURES, s'ils ont ete generes pour cette saison par
# mesure_coefs.py : force mediane des adversaires reellement rencontres,
# plutot que le classement UEFA d'association, qui note un pays entier sur
# cinq ans. Meme ordre, amplitude plus resserree. Absent : on garde l'UEFA.
_MESURES = pathlib.Path("coefs_championnats.json")
if _MESURES.exists():
    try:
        COEF_COMPET_NOM.update(
            json.loads(_MESURES.read_text(encoding="utf-8"))["coefs"])
    except (ValueError, KeyError):
        pass


def coef_competition(nom):
    """Coefficient d'une competition, par son nom normalise."""
    if not nom:
        return COEF_DEFAUT
    n = unicodedata.normalize("NFKD", str(nom).lower())
    n = "".join(ch for ch in n if not unicodedata.combining(ch)).strip()
    if n in COEF_COMPET_NOM:
        return COEF_COMPET_NOM[n]
    for cle, val in COEF_COMPET_NOM.items():       # "uefa nations league b"...
        if n.startswith(cle):
            return val
    return COEF_DEFAUT


# ---------------------------------------------------------------- section 3
# POIDS DU TOUR. Se multiplie au poids de competition.
COEF_TOUR = {
    "Phase reguliere": 1.0,
    "Phase de groupes": 1.0,
    "Barrages": 1.1,
    "Seiziemes de finale": 1.15,
    "Huitiemes de finale": 1.3,
    "Quarts de finale": 1.5,
    "Demi-finales": 1.8,
    "Match 3e place": 1.2,
    "Finale": 2.2,
}

MANUEL_POSTES = pathlib.Path("postes_manuel.json")

# Les position_id de FotMob ne sont pas une liste de postes mais une GRILLE :
# les dizaines donnent la ligne (1 gardien, 3 defense, 5/6/7 milieu, 8 milieu
# offensif, 10/11 attaque), les unites la colonne, 5 etant l'axe. Les classer
# par plages d'entiers, comme je le faisais, met 78 — le couloir gauche de la
# ligne mediane — dans les milieux axiaux. Deux slots restent ambigus meme en
# lisant la grille, et se tranchent sur la forme reelle de l'equipe ce jour-la.
# ---------------------------------------------------------------- section 2 bis
# POIDS DE CLUB. Choix editorial assume : briller au PSG ne vaut pas briller
# a Angers. La force d'un club est mesuree sur la base elle-meme — points par
# match en championnat, multiplies par le coefficient de ce championnat — puis
# ramenee a une echelle centree sur 1 :
#     coef = 1 - AMPLITUDE/2  ...  1 + AMPLITUDE/2
# ATTENTION : ce coefficient pousse dans le MEME sens que le biais de
# domination d'equipe deja mesure (correlation 0,32 a 0,55 selon le poste).
# Il l'aggrave volontairement. C'est coherent pour un bareme facon Ballon d'Or,
# ce ne l'est pas pour un bareme de performance pure.
AMPLITUDE_CLUB = 0.0         # retire : recompensait l'employeur, pas le match
# Force d'un championnat = coefficient d'association UEFA (cumul 5 ans
# 2020/21-2024/25, Angleterre = 1). Meme table que les coefficients de
# competition, meme source : la mesure est exterieure au bareme.
LIGUES_FORCE = {47: 1.000,    # Premier League
                55: 0.844,    # Serie A
                87: 0.820,    # LaLiga
                54: 0.749,    # Bundesliga
                53: 0.634,    # Ligue 1
                57: 0.583,    # Eredivisie
                61: 0.540,    # Liga Portugal
                71: 0.381}    # Super Lig


# Amplitude de la force adverse, ALIGNEE sur celle du palmares : la meme
# regle doit avoir la meme severite des deux cotes. L'echelle va desormais de
# 0,40 a 1,60 (au lieu de 0,80-1,20) — battre le meilleur plateau vaut quatre
# fois battre le plus faible, comme dans le credit par parcours du palmares.
AMPLITUDE_ADVERSAIRE = 1.20   # 0 = desactive ; echelle 0,40 a 1,60


def coefs_clubs(conn, amplitude=None):
    """Force de chaque equipe rencontree, sur une echelle centree sur 1.

    Trois populations, trois regles — parce qu'un repli unique a 1,00 revenait
    a coter un club de quatrieme division comme un milieu de tableau de Serie A,
    et 16 % des adversaires de la base etaient dans ce cas :

    1. Clubs des championnats collectes : points par match, ponderes par le
       coefficient UEFA du championnat. C'est la mesure la plus fiable.
    2. Equipes rencontrees en coupe nationale et absentes de tout championnat
       collecte : ce sont des clubs de division inferieure, ils prennent le bas
       de l'echelle.
    3. Equipes rencontrees en Europe ou en selection : cotees sur leurs propres
       resultats dans la base, dans leur competition, avec un lissage pour les
       petits echantillons.
    """
    amplitude = AMPLITUDE_CLUB if amplitude is None else amplitude
    if amplitude <= 0:
        return {}
    bilan = defaultdict(lambda: [0, 0])
    ids = ",".join(map(str, LIGUES_FORCE))
    for lid, dom, ext, bd, be in conn.execute(f"""
            SELECT parent_league_id, home_team_id, away_team_id, home_score, away_score
            FROM v_match
            WHERE parent_league_id IN ({ids}) AND home_score IS NOT NULL"""):
        for equipe, pour, contre in ((dom, bd, be), (ext, be, bd)):
            b = bilan[(lid, equipe)]
            b[0] += 3 if pour > contre else (1 if pour == contre else 0)
            b[1] += 1
    force = {equipe: (p / n) * LIGUES_FORCE[lid]
             for (lid, equipe), (p, n) in bilan.items() if n >= 15}
    if not force:
        return {}
    bas, haut = min(force.values()), max(force.values())
    if haut == bas:
        return {}
    echelle = lambda v: (1 - amplitude / 2) + amplitude * (v - bas) / (haut - bas)
    coefs = {equipe: echelle(v) for equipe, v in force.items()}

    # Populations 2 et 3 : bilan de chaque equipe non cotee, par competition.
    reste = defaultdict(lambda: [0, 0])
    europe = set()
    for nom, dom, ext, bd, be in conn.execute("""
            SELECT competition, home_team_id, away_team_id, home_score, away_score
            FROM v_match WHERE home_score IS NOT NULL"""):
        internationale = coef_competition(nom) >= 1.0
        for equipe, pour, contre in ((dom, bd, be), (ext, be, bd)):
            if equipe in coefs:
                continue
            b = reste[equipe]
            b[0] += 3 if pour > contre else (1 if pour == contre else 0)
            b[1] += 1
            if internationale:
                europe.add(equipe)

    plancher = 1 - amplitude / 2
    for equipe, (p, n) in reste.items():
        if equipe not in europe:
            # coupe nationale uniquement : division inferieure
            coefs[equipe] = plancher + amplitude * 0.05
            continue
        # lissage vers 1,4 point par match tant que l'echantillon est court
        ppm = (p + 5 * 1.4) / (n + 5)
        coefs[equipe] = min(1 + amplitude / 2,
                            max(plancher, plancher + amplitude * (ppm / 2.6)))
    return coefs


# Le meneur de jeu axial n'est plus un poste distinct : 51 joueurs seulement,
# dont presque aucun ne passait la moitie de ses minutes a ce poste — Odegaard
# 12 %, Bellingham 29 %, Guler 20 %. Un effectif aussi mince rend le calibrage
# au percentile 95 instable, et la donnee elle-meme disait que le role n'existe
# plus comme position fixe. Il est absorbe par le relayeur, qui passe a 232
# joueurs. FUSION_10 = False pour retrouver les neuf postes.
# Retabli : la fusion diluait le poste de relayeur (234 joueurs) et melangeait
# deux roles distincts. Le 10 redevient un poste, avec le calibrage plus
# fragile que cela implique — une cinquantaine de joueurs seulement.
FUSION_10 = False

ORDRE = ["Gardien", "Defenseur central", "Lateral", "Milieu defensif",
         "Milieu relayeur", "Ailier", "Buteur"]
if not FUSION_10:
    ORDRE.insert(5, "Milieu offensif")


def poste_du_slot(pos, forme):
    """Poste d'un slot, connaissant la forme reelle de l'equipe ce jour-la.

    forme = (une_pointe, defenseurs, socle) :
      une_pointe  l'equipe alignait-elle un attaquant d'axe (105/115/95) ?
      defenseurs  combien de joueurs sur la ligne 3 (31-39) ?
      socle       les slots d'axe du milieu occupant la ligne la PLUS BASSE.

    Les unites de l'identifiant donnent la colonne : sous 5 c'est le cote
    droit, au-dessus le cote gauche. C'est ce qui separe les deux ailes.
    """
    if pos is None:
        return None
    if pos == 11:
        return "Gardien"
    une_pointe, defenseurs, socle = forme
    ligne, col = pos // 10, pos % 10
    ecart = abs(col - 5)
    cote = "droit" if col < 5 else "gauche"

    if ligne in (3, 4):
        return "Lateral" if ecart == 3 else "Defenseur central"

    if ligne in (5, 6, 7):
        if ecart >= 3:
            # Couloir bas : piston si la ligne defensive est courte, milieu de
            # couloir donc ailier si elle est complete.
            if defenseurs <= 3:
                return "Lateral"
            return "Ailier" if ligne == 7 else "Lateral"
        # Axe du milieu : le 6 est celui qui occupe la ligne la plus basse de
        # SON PROPRE milieu ce jour-la, pas une ligne fixe. Sans ca, un 4-3-3
        # a trois joueurs sur la meme ligne rendait Pedri et Odegaard
        # defensifs, et un 4-2-3-1 rendait tout le monde relayeur.
        return "Milieu defensif" if pos in socle else "Milieu relayeur"

    if ligne == 8:
        axe = "Milieu relayeur" if FUSION_10 else "Milieu offensif"
        return axe if ecart == 0 else "Ailier"
    if ligne == 9:
        return "Milieu relayeur" if FUSION_10 else "Milieu offensif"
    if ligne in (10, 11):
        if ecart == 0:
            return "Buteur"
        if ecart == 2:
            return "Ailier"
        # 104 / 106 : aile d'un trident si une pointe occupe l'axe, duo
        # d'attaque sinon. Vinicius ailier gauche, Lautaro buteur.
        return "Ailier" if une_pointe else "Buteur"
    return None


def postes(conn):
    """Poste de chaque joueur : celui ou il a passe le plus de MINUTES."""
    pointe = {(mid, tid) for mid, tid in conn.execute("""
        SELECT a.match_id, a.team_id FROM appearance a
        JOIN match m ON m.match_id = a.match_id AND m.usable = 1
        WHERE a.position_id IN (105, 115, 95) GROUP BY 1, 2""")}
    ligne3 = dict(conn.execute("""
        SELECT a.match_id || '-' || a.team_id, COUNT(DISTINCT a.player_id)
        FROM appearance a
        JOIN match m ON m.match_id = a.match_id AND m.usable = 1
        WHERE a.position_id BETWEEN 31 AND 39 GROUP BY 1"""))

    axe = defaultdict(list)
    for mid, tid, pos in conn.execute("""
            SELECT a.match_id, a.team_id, a.position_id FROM appearance a
            JOIN match m ON m.match_id = a.match_id AND m.usable = 1
            WHERE a.position_id BETWEEN 51 AND 79"""):
        if abs(pos % 10 - 5) < 3:
            axe[(mid, tid)].append(pos)
    socles = {}
    for cle, slots in axe.items():
        plus_bas = min(p // 10 for p in slots)
        bas = [p for p in slots if p // 10 == plus_bas]
        if len(bas) == len(slots) and len(slots) > 1:
            # milieu a plat : le plus axial fait le 6
            socles[cle] = {min(bas, key=lambda p: abs(p % 10 - 5))}
        else:
            socles[cle] = set(bas)

    minutes = defaultdict(lambda: defaultdict(float))
    for pid, mid, tid, pos, mn in conn.execute("""
            SELECT a.player_id, a.match_id, a.team_id, a.position_id, s.value
            FROM appearance a
            JOIN match m ON m.match_id = a.match_id AND m.usable = 1
            JOIN stat s ON s.match_id = a.match_id AND s.player_id = a.player_id
                       AND s.stat_key = 'minutes_played'
            WHERE a.position_id IS NOT NULL AND s.value > 0"""):
        forme = ((mid, tid) in pointe, ligne3.get(f"{mid}-{tid}", 4),
                 socles.get((mid, tid), set()))
        g = poste_du_slot(pos, forme)
        if g:
            minutes[pid][g] += mn
    res = {pid: max(d.items(), key=lambda kv: kv[1])[0] for pid, d in minutes.items()}

    # Fiabilite : part des minutes reellement jouees au poste attribue. Un
    # joueur a 95 % est un cas certain, un joueur a 45 % flotte entre deux
    # roles et son classement depend d'un arbitrage, pas d'une mesure.
    global FIABILITE, REPARTITION
    FIABILITE, REPARTITION = {}, {}
    for pid, d in minutes.items():
        total = sum(d.values())
        REPARTITION[pid] = sorted(d.items(), key=lambda kv: -kv[1])
        FIABILITE[pid] = (d[res[pid]] / total) if total else 0.0

    if MANUEL_POSTES.exists():
        forces = json.loads(MANUEL_POSTES.read_text(encoding="utf-8"))
        # Homonymes : deux « Bruno Fernandes » dans la base. Un dictionnaire
        # nom -> identifiant en garde un au hasard, et le correctif tombe sur
        # le mauvais joueur. On retient celui qui a le plus joue.
        noms = {}
        for pid, nom, mn in conn.execute("""
                SELECT p.player_id, p.name, SUM(s.value) FROM player p
                JOIN stat s ON s.player_id = p.player_id
                JOIN match m ON m.match_id = s.match_id AND m.usable = 1
                WHERE s.stat_key = 'minutes_played'
                GROUP BY p.player_id ORDER BY SUM(s.value)"""):
            noms[nom] = pid
        for nom, poste in forces.items():
            pid = noms.get(nom)
            if FUSION_10 and poste == "Milieu offensif":
                poste = "Milieu relayeur"
            if pid is not None and poste in ORDRE:
                res[pid] = poste
                FIABILITE[pid] = 1.0        # tranche a la main : certain
    return res


FIABILITE, REPARTITION = {}, {}


def classer_phase(v) -> str:
    """Reprise litterale de bareme.py : meme decoupage, memes libelles."""
    if v is None:
        return "Phase reguliere"
    v = str(v).strip().lower()
    if not v or re.fullmatch(r"\d+", v):
        return "Phase reguliere"
    if "1/16" in v or "round of 32" in v:
        return "Seiziemes de finale"
    if "1/8" in v or "round of 16" in v:
        return "Huitiemes de finale"
    if "quarter" in v or "1/4" in v:
        return "Quarts de finale"
    if "semi" in v or "1/2" in v:
        return "Demi-finales"
    if any(t in v for t in ("3rd", "third", "bronze")):
        return "Match 3e place"
    if "final" in v:
        return "Finale"
    if "group" in v or "grp" in v:
        return "Phase de groupes"
    if "play" in v:
        return "Barrages"
    return "Phase reguliere"


def valeur_action(cle):
    for famille, table in POINTS.items():
        if cle in table:
            return famille, table[cle][1]
    return None, 0.0


def references_progression(conn, joueurs):
    """Taux de reference par poste : realisees / touches, sur le vivier."""
    cles = list(PROGRESSION)
    marks = ",".join("?" * len(cles))
    cumul = defaultdict(lambda: [0.0, 0.0])
    touches = defaultdict(float)
    for pid, v in conn.execute("""
            SELECT s.player_id, SUM(s.value) FROM stat s
            JOIN match m ON m.match_id = s.match_id AND m.usable = 1
            WHERE s.stat_key = 'touches' GROUP BY 1"""):
        touches[pid] = v or 0.0
    for pid, cle, v in conn.execute(f"""
            SELECT s.player_id, s.stat_key, SUM(s.value) FROM stat s
            JOIN match m ON m.match_id = s.match_id AND m.usable = 1
            WHERE s.stat_key IN ({marks}) GROUP BY 1, 2""", tuple(cles)):
        j = joueurs.get(pid)
        if j is None:
            continue
        c = cumul[(j["poste"], cle)]
        c[0] += v or 0.0
        c[1] += touches.get(pid, 0.0)
    refs = {}
    for (poste, cle), (v, t) in cumul.items():
        refs.setdefault(poste, {})[cle] = (v / t) if t else 0.0
    return refs


def _cle_reference(pid, joueur):
    return profil_global.get(pid, joueur["poste"])


def references(conn, joueurs):
    """Taux de reussite de reference, poste par poste, sur le vivier."""
    marks = ",".join("?" * len(FRACTIONS))
    cumul = defaultdict(lambda: [0.0, 0.0])
    for pid, cle, v, t in conn.execute(f"""
            SELECT s.player_id, s.stat_key, SUM(s.value), SUM(s.total)
            FROM stat s JOIN match m ON m.match_id = s.match_id AND m.usable = 1
            WHERE s.stat_key IN ({marks}) AND s.total IS NOT NULL
            GROUP BY s.player_id, s.stat_key""", tuple(FRACTIONS)):
        j = joueurs.get(pid)
        if j is None:
            continue
        c = cumul[(j["poste"], cle)]
        c[0] += v or 0.0
        c[1] += t or 0.0
    refs = {}
    for (poste, cle), (v, t) in cumul.items():
        refs.setdefault(poste, {})[cle] = round(v / t, 4) if t else 0.0
    return refs


def sans_accents(txt):
    n = unicodedata.normalize("NFKD", str(txt).lower())
    return "".join(c for c in n if not unicodedata.combining(c)).strip()


MANUEL_DISTINCTIONS = pathlib.Path("bareme_manuel.json")
_ELIGIBLES = None


def eligibles_distinction(conn):
    """Joueurs admis dans le panel quel que soit leur temps de jeu.

    Etre elu meilleur joueur d'une competition ou figurer dans son equipe-type
    est un jugement de jury sur une saison entiere : un tel joueur ne peut pas
    etre exclu par un seuil de minutes. Sans cette regle, Messi (740 minutes de
    Coupe du monde, equipe-type du tournoi) n'apparaissait dans aucun
    classement.
    """
    global _ELIGIBLES
    if _ELIGIBLES is not None:
        return _ELIGIBLES
    _ELIGIBLES = set()
    if not MANUEL_DISTINCTIONS.exists():
        return _ELIGIBLES
    index = {}
    for pid, nom in conn.execute("SELECT player_id, name FROM player"):
        index.setdefault(sans_accents(nom), pid)
    data = json.loads(MANUEL_DISTINCTIONS.read_text(encoding="utf-8"))
    for e in data.get("evenements", []):
        lib = sans_accents(e.get("libelle", ""))
        # Seules les distinctions des tournois MAJEURS ouvrent le panel : une
        # equipe-type de competition secondaire ne doit pas faire entrer un
        # joueur de dix matchs.
        import re as _re
        majeur = bool(_re.search(
            r"(ldc|champions league|cdm|coupe du monde|mondial|euro\b|world cup)",
            lib)) and "europa" not in lib
        if majeur and (lib.startswith(("mvp", "meilleur joueur"))
                       or "equipe-type" in lib or "equipe type" in lib):
            pid = index.get(sans_accents(e.get("joueur", "")))
            if pid:
                _ELIGIBLES.add(pid)
    return _ELIGIBLES



# ---------------------------------------------------------------------------
# PROFILS DE JEU
# Les taux de reference des actions a reussite (duels au sol, dribbles,
# centres, passes) etaient calcules par POSTE. Or un meme poste melange des
# metiers differents : un defenseur duelliste et un defenseur relanceur n'ont
# pas les memes standards. Les profils sont deduits des donnees — repartition
# Finition / Creation / Defense / Conduite — et servent de groupe de reference.
# Ils ne modifient AUCUNE valeur : ils changent seulement a qui on se compare.
PROFILS_ACTIFS = True
MILIEUX = {"Milieu defensif", "Milieu relayeur", "Milieu offensif"}
FAMILLES_PROFIL = ["Finition", "Creation", "Defense", "Conduite"]
profil_global = {}


def _kmeans(points, k, iterations=60):
    """k-moyennes simple, sans dependance externe."""
    import random
    rnd = random.Random(3)
    centres = [list(p) for p in rnd.sample(points, k)]
    affect = [0] * len(points)
    for _ in range(iterations):
        for i, p in enumerate(points):
            affect[i] = min(range(k), key=lambda j: sum(
                (p[d] - centres[j][d]) ** 2 for d in range(len(p))))
        for j in range(k):
            lot = [points[i] for i in range(len(points)) if affect[i] == j]
            if lot:
                centres[j] = [sum(p[d] for p in lot) / len(lot)
                              for d in range(len(lot[0]))]
    return affect


STYLE_CLES = ("touches", "accurate_passes", "passes_into_final_third",
              "chances_created", "expected_assists", "dribbles_succeeded",
              "goals", "assists", "recoveries", "matchstats.headers.tackles",
              "interceptions", "touches_opp_box",
              # criteres propres aux lignes arriere : jeu long, jeu aerien,
              # centres, degagements — ce qui distingue un relanceur d'un
              # duelliste et un lateral offensif d'un lateral de couverture.
              "long_balls_accurate", "aerials_won", "ground_duels_won",
              "accurate_crosses", "clearances")
_STYLE = {}


def _charger_style(conn):
    if _STYLE:
        return _STYLE
    marks = ",".join("?" * len(STYLE_CLES))
    for pid, cle, v in conn.execute(
            f"SELECT s.player_id, s.stat_key, SUM(s.value) FROM stat s "
            f"JOIN match m ON m.match_id = s.match_id AND m.usable = 1 "
            f"WHERE s.stat_key IN ({marks}) GROUP BY 1, 2", STYLE_CLES):
        _STYLE.setdefault(pid, {})[cle] = v or 0.0
    return _STYLE


def _vecteur_style(pid, base):
    """Ce qu'un joueur fait DE SES BALLONS, jamais son volume.

    Les profils etaient calcules sur la repartition des familles de points :
    un createur qui ne marque pas ressemblait alors a un recuperateur, et
    Pedri se retrouvait dans le meme groupe que Ndidi et Casemiro. Les
    criteres ci-dessous sont des RATIOS — par 100 passes ou par 1000 touches —
    donc ils decrivent le metier et non l'activite.
    """
    s = _STYLE.get(pid, {})
    t = max(s.get("touches", 0.0), 1.0)
    pa = max(s.get("accurate_passes", 0.0), 1.0)
    defense = (s.get("recoveries", 0.0)
               + s.get("matchstats.headers.tackles", 0.0)
               + s.get("interceptions", 0.0))
    return [s.get("chances_created", 0.0) / pa * 100,
            s.get("expected_assists", 0.0) / t * 1000,
            s.get("dribbles_succeeded", 0.0) / t * 100,
            (s.get("goals", 0.0) + s.get("assists", 0.0)) / t * 1000,
            s.get("passes_into_final_third", 0.0) / pa * 100,
            defense / t * 100,
            s.get("touches_opp_box", 0.0) / t * 100,
            s.get("long_balls_accurate", 0.0) / pa * 100,
            s.get("aerials_won", 0.0) / t * 100,
            s.get("ground_duels_won", 0.0) / t * 100,
            s.get("accurate_crosses", 0.0) / pa * 100,
            s.get("clearances", 0.0) / t * 100]


def calculer_profils(conn, seuil, seuil_champ):
    """Deduit un profil de jeu par joueur, a partir d'une premiere passe."""
    global profil_global, PROFILS_ACTIFS
    if profil_global or not PROFILS_ACTIFS:
        return profil_global
    PROFILS_ACTIFS = False                     # evite la recursion
    try:
        base = charger(conn, seuil, seuil_champ)
    finally:
        PROFILS_ACTIFS = True
    _charger_style(conn)
    groupes = defaultdict(list)
    for pid, d in base.items():
        groupes["Milieu" if d["poste"] in MILIEUX else d["poste"]].append(pid)
    for groupe, ids in groupes.items():
        if len(ids) < 40:
            for pid in ids:
                profil_global[pid] = groupe
            continue
        pts = [_vecteur_style(pid, base) for pid in ids]
        # centrage-reduction : chaque critere pese pareil
        n_dim = len(pts[0])
        moy = [sum(p[d] for p in pts) / len(pts) for d in range(n_dim)]
        ect = [(sum((p[d] - moy[d]) ** 2 for p in pts) / len(pts)) ** 0.5 or 1.0
               for d in range(n_dim)]
        pts = [[(p[d] - moy[d]) / ect[d] for d in range(n_dim)] for p in pts]
        if groupe == "Defenseur central":
            # Le k-moyennes produisait un groupe geant de 147 joueurs sur 266 :
            # la majorite des centraux se ressemblent, et le centre de gravite
            # les absorbe. On les repartit donc par TRAIT DOMINANT — jeu
            # aerien, duel au sol, relance — chacun rejoignant l'axe ou il
            # depasse le plus la moyenne du poste. Les groupes sont equilibres
            # par construction et decrivent un metier, pas une distance.
            axes = (8, 9, 4)                     # aerien, sol, passes 1/3
            affect = []
            for p in pts:
                affect.append(max(range(len(axes)), key=lambda q: p[axes[q]]))
        elif groupe == "Lateral":
            # Meme logique que les centraux : trait dominant plutot que
            # distance, pour ne pas laisser un groupe "equilibre" absorber la
            # moitie du poste. Trois metiers : duelliste, centreur, piston.
            axes = (9, 10, 6)                    # duels au sol, centres, surface adverse
            affect = [max(range(len(axes)), key=lambda q: p[axes[q]]) for p in pts]
        else:
            affect = _kmeans(pts, 5 if groupe == "Milieu" else 3)
        for i, pid in enumerate(ids):
            profil_global[pid] = f"{groupe}#{affect[i] + 1}"
    return profil_global


def charger(conn, seuil, seuil_champ):
    exempt = ",".join(str(x) for x in eligibles_distinction(conn)) or "0"
    # Entrees en jeu : un joueur sans poste dans la composition est entre du
    # banc. Doit etre connu AVANT le calcul des points.
    ENTRANTS.clear()
    for _pid, _mid in conn.execute(
            "SELECT player_id, match_id FROM appearance WHERE position_id IS NULL"):
        ENTRANTS.add((_pid, _mid))
    """Points bruts par joueur et par match, avant coefficient de poste."""
    cles = {k for table in POINTS.values() for k in table}
    marks = ",".join("?" * len(cles))

    # Force de l'ADVERSAIRE, match par match : ce qui compte n'est pas le club
    # qui te paie mais celui que tu as en face. Un but contre le Bayern ne vaut
    # pas un but contre Heidenheim, et ca, contrairement au coefficient de club,
    # se juge sur ce qui s'est passe sur le terrain.
    forces = coefs_clubs(conn, AMPLITUDE_ADVERSAIRE)
    cotes = {}
    for mid, dom, ext in conn.execute(
            "SELECT match_id, home_team_id, away_team_id FROM v_match"):
        cotes[mid] = (dom, ext)
    equipe_dans = {}
    for pid, mid, tid in conn.execute("""
            SELECT a.player_id, a.match_id, a.team_id FROM appearance a
            JOIN match m ON m.match_id = a.match_id AND m.usable = 1"""):
        equipe_dans[(pid, mid)] = tid

    # Recentrage : avec une amplitude large, la mediane des adversaires
    # REELLEMENT rencontres doit valoir 1, sinon toute l'echelle se deplace et
    # les scores s'effondrent globalement au lieu de se redistribuer.
    _vus = [forces.get(t, 1.0)
            for mid_, (d_, e_) in cotes.items() for t in (d_, e_)]
    if _vus:
        _med = sorted(_vus)[len(_vus) // 2] or 1.0
        forces = {k: v / _med for k, v in forces.items()}

    def coef_adverse(pid, mid):
        paire = cotes.get(mid)
        mien = equipe_dans.get((pid, mid))
        if not paire or mien is None:
            return 1.0
        autre = paire[1] if paire[0] == mien else paire[0]
        return forces.get(autre, 1.0)

    clubs = coefs_clubs(conn)
    equipe_de = {}
    for pid, tid in conn.execute("""
            SELECT a.player_id, a.team_id FROM appearance a
            JOIN match m ON m.match_id = a.match_id AND m.usable = 1
            GROUP BY a.player_id, a.team_id
            ORDER BY COUNT(*) DESC"""):
        equipe_de.setdefault(pid, tid)

    matchs = {}
    for mid, date, parent, rnd, nom in conn.execute(
            "SELECT match_id, date_utc, parent_league_id, round, competition FROM v_match"):
        phase = classer_phase(rnd)
        matchs[mid] = (date[:10], coef_competition(nom) * COEF_TOUR.get(phase, 1.0),
                       parent, phase)

    # par_cle_date : les memes points, ventiles par cle d'action ET par date,
    # sans coefficient de poste. Ne change aucun total : c'est la trace qui
    # permet a un client (le jeu, un export) de recomposer une famille ou une
    # periode sans relancer le calcul.
    joueurs = {}
    for pid, nom, minutes, club, tid in conn.execute(f"""
            SELECT s.player_id, p.name, SUM(s.value),
                   (SELECT a.team_name FROM appearance a
                     JOIN match m2 ON m2.match_id = a.match_id AND m2.usable = 1
                     WHERE a.player_id = s.player_id
                     GROUP BY a.team_name ORDER BY COUNT(*) DESC LIMIT 1),
                   (SELECT a.team_id FROM appearance a
                     JOIN match m2 ON m2.match_id = a.match_id AND m2.usable = 1
                     WHERE a.player_id = s.player_id
                     GROUP BY a.team_id ORDER BY COUNT(*) DESC LIMIT 1)
            FROM stat s JOIN match m ON m.match_id = s.match_id AND m.usable = 1
            JOIN player p ON p.player_id = s.player_id
            WHERE s.stat_key = 'minutes_played' AND s.value > 0
            GROUP BY s.player_id HAVING SUM(s.value) >= {min(seuil, 1)}
                                     AND (SUM(s.value) >= {seuil}
                                          OR s.player_id IN ({exempt}))"""):
        joueurs[pid] = dict(nom=nom, club=club, team_id=tid, minutes=minutes or 0,
                            brut=0.0, familles=defaultdict(float),
                            evenements=defaultdict(float),
                            par_famille_date=defaultdict(lambda: defaultdict(float)),
                            par_cle_date=defaultdict(lambda: defaultdict(float)),
                            minutes_par_date=defaultdict(float))

    # Deuxieme filtre : un minimum de minutes de CHAMPIONNAT. Sans lui,
    # les joueurs dont le championnat n'est pas collecte (Belgique,
    # Danemark, Norvege, Croatie...) n'apparaissent que par leurs matchs
    # europeens, c'est-a-dire au coefficient le plus eleve du bareme. Leur
    # saison entiere se jouerait alors en Ligue des champions.
    en_championnat = dict(conn.execute(f"""
        SELECT s.player_id, SUM(s.value) FROM stat s
        JOIN match m ON m.match_id = s.match_id AND m.usable = 1
        WHERE s.stat_key = 'minutes_played' AND s.value > 0
          AND m.parent_league_id IN ({",".join(map(str, LIGUES))})
        GROUP BY s.player_id"""))
    joueurs = {k: v for k, v in joueurs.items()
               if (en_championnat.get(k) or 0) >= seuil_champ
               or k in eligibles_distinction(conn)}

    for pid, poste in postes(conn).items():
        if pid in joueurs:
            joueurs[pid]["poste"] = poste
            joueurs[pid]["fiabilite"] = FIABILITE.get(pid, 0.0)
    joueurs = {k: v for k, v in joueurs.items() if v.get("poste")}
    joueurs = {k: v for k, v in joueurs.items()
               if v["poste"] != "Gardien" or v["minutes"] >= SEUIL_GARDIEN}

    # Les cles de gardien ne rapportent qu'aux gardiens, et reciproquement :
    # un defenseur credite d'un degagement du poing serait une aberration.
    for pid, mid, cle, val in conn.execute(f"""
            SELECT s.player_id, s.match_id, s.stat_key, s.value
            FROM stat s JOIN match m ON m.match_id = s.match_id AND m.usable = 1
            WHERE s.stat_key IN ({marks}) AND s.value IS NOT NULL""", tuple(cles)):
        j = joueurs.get(pid)
        if j is None or mid not in matchs:
            continue
        famille, pts = valeur_action(cle)
        if pts == 0.0:
            continue
        gardien = j["poste"] == "Gardien"
        if (famille == "Gardien") != gardien:
            continue
        date, coef, _parent, _phase = matchs[mid]
        if gardien and _parent in CHAMPIONNATS_GK:
            coef = COEF_TOUR.get(_phase, 1.0)      # championnat neutralise
        coef *= coef_adverse(pid, mid)
        gagne = val * pts * coef
        if famille == "Gardien":
            gagne *= COEF_GARDIEN
        # Un joueur entre en jeu produit contre des jambes lourdes, dans un
        # match deja ouvert : ses points valent moins. On escompte donc les
        # MINUTES D'ENTRANT, pas le joueur — un titulaire blesse une moitie de
        # saison n'est pas penalise, un joueur de rotation l'est exactement la
        # ou son par 90 est flatte.
        if (pid, mid) in ENTRANTS:
            gagne *= COEF_ENTRANT
        j["brut"] += gagne
        j["familles"][famille] += gagne
        j["evenements"][date] += gagne
        j["par_famille_date"][famille][date] += gagne
        j["par_cle_date"][cle][date] += gagne

    # Surperformance de finition : buts marques au-dela de ce que les tirs
    # valaient. Un joueur qui convertit 20 buts pour 12 d'xG a une qualite de
    # finition reelle, aujourd'hui invisible dans le bareme.
    for pid, mid, marques, attendus in conn.execute("""
            SELECT g.player_id, g.match_id, g.value, x.value
            FROM stat g
            JOIN stat x ON x.match_id = g.match_id AND x.player_id = g.player_id
                       AND x.stat_key = 'expected_goals_non_penalty'
            JOIN match m ON m.match_id = g.match_id AND m.usable = 1
            WHERE g.stat_key = 'goals'"""):
        j = joueurs.get(pid)
        if j is None or mid not in matchs:
            continue
        date, coef, _p, _ph = matchs[mid]
        coef *= coef_adverse(pid, mid)
        gagne = ((marques or 0.0) - (attendus or 0.0)) * SURPERFORMANCE * coef
        j["brut"] += gagne
        j["familles"]["Finition"] += gagne
        j["evenements"][date] += gagne
        j["par_famille_date"]["Finition"][date] += gagne
        j["par_cle_date"]["g_moins_xg"][date] += gagne

    # Penalties marques : detectes par l'ecart entre xG total et xG hors
    # penalty, qui vaut exactement 0,79 par penalty tire dans cette base. Un
    # penalty converti n'est pas une frappe comme une autre — il est attendu a
    # 79 % — donc il ne vaut pas un but du jeu. On retire l'ecart.
    manques = defaultdict(int)
    for mid_, pid_ in conn.execute(
            "SELECT e.match_id, e.player_id FROM event e "
            "JOIN match m ON m.match_id = e.match_id AND m.usable = 1 "
            "WHERE e.type = 'MissedPenalty'"):
        manques[(pid_, mid_)] += 1
    for pid, mid, xt, xn in conn.execute("""
            SELECT a.player_id, a.match_id, a.value, b.value
            FROM stat a
            JOIN stat b ON b.match_id = a.match_id AND b.player_id = a.player_id
                       AND b.stat_key = 'expected_goals_non_penalty'
            JOIN match m ON m.match_id = a.match_id AND m.usable = 1
            WHERE a.stat_key = 'expected_goals'"""):
        j = joueurs.get(pid)
        if j is None or mid not in matchs:
            continue
        tires = round(((xt or 0.0) - (xn or 0.0)) / XG_PENALTY)
        marques_pen = tires - manques.get((pid, mid), 0)
        if marques_pen <= 0:
            continue
        date, coef, _p, _ph = matchs[mid]
        coef *= coef_adverse(pid, mid)
        perdu = -marques_pen * (VALEUR_BUT - VALEUR_PENALTY) * coef
        j["brut"] += perdu
        j["familles"]["Finition"] += perdu
        j["evenements"][date] += perdu
        j["par_famille_date"]["Finition"][date] += perdu
        j["par_cle_date"]["penalty_marque"][date] += perdu

    # Les profils servent de groupe de reference aux corrections ci-dessous
    # comme aux taux de reussite : ils doivent donc etre connus avant.
    if PROFILS_ACTIFS:
        calculer_profils(conn, seuil, seuil_champ)

    # ------------------------------------------------------------------
    # CORRECTIONS EN MODE EXCEDENT
    # Une action de volume mesure surtout l'exposition : un defenseur tacle
    # beaucoup parce qu'il est attaque, un joueur perd des ballons parce qu'il
    # en touche. Ces lignes sont donc recalculees en ECART a ce qu'un joueur de
    # son poste realise pour la meme base d'occasions.
    #   - conservation : ballons perdus rapportes aux touches
    #   - duels perdus, se faire dribbler, fautes : rapportes aux duels tentes
    #   - precision de tir : tirs cadres rapportes aux tirs tentes
    #   - recuperations, degagements, degagements tete, interceptions :
    #     rapportes a la CHARGE DEFENSIVE subie (touches de l'adversaire)
    CLES_EXC = ("touches", "dispossessed", "duel_lost", "dribbled_past", "fouls",
                "ground_duels_won", "ShotsOnTarget", "total_shots",
                "recoveries", "clearances", "headed_clearance", "interceptions")
    par_match = defaultdict(lambda: defaultdict(float))
    for pid, mid, cle, v, tt in conn.execute(
            "SELECT s.player_id, s.match_id, s.stat_key, SUM(s.value), SUM(s.total) "
            "FROM stat s JOIN match m ON m.match_id = s.match_id AND m.usable = 1 "
            f"WHERE s.stat_key IN {CLES_EXC} GROUP BY s.player_id, s.match_id, s.stat_key"):
        if pid not in joueurs or mid not in matchs:
            continue
        par_match[(pid, mid)][cle] += v or 0.0
        if cle == "ground_duels_won":
            par_match[(pid, mid)]["duels_tentes"] += tt or 0.0

    # charge defensive subie : touches de l'equipe adverse dans le match
    touches_eq = defaultdict(float)
    for mid, tid, v in conn.execute(
            "SELECT s.match_id, a.team_id, SUM(s.value) FROM stat s "
            "JOIN appearance a ON a.match_id = s.match_id AND a.player_id = s.player_id "
            "JOIN match m ON m.match_id = s.match_id AND m.usable = 1 "
            "WHERE s.stat_key = 'touches' GROUP BY s.match_id, a.team_id"):
        touches_eq[(mid, tid)] += v or 0.0
    adversaire = {}
    for mid, h, a in conn.execute(
            "SELECT match_id, home_team_id, away_team_id FROM v_match"):
        adversaire[(mid, h)] = a
        adversaire[(mid, a)] = h
    equipe_de = {}
    for mid, pid, tid in conn.execute(
            "SELECT match_id, player_id, team_id FROM appearance"):
        equipe_de[(mid, pid)] = tid

    def charge(pid, mid):
        t = equipe_de.get((mid, pid))
        o = adversaire.get((mid, t)) if t else None
        return touches_eq.get((mid, o), 0.0) if o else 0.0

    # taux de reference par poste
    cumul = defaultdict(lambda: defaultdict(float))
    for (pid, mid), s in par_match.items():
        for po in {profil_global.get(pid, joueurs[pid]["poste"]),
                   joueurs[pid]["poste"]}:
            for k in CLES_EXC:
                cumul[po][k] += s.get(k, 0.0)
            cumul[po]["duels_tentes"] += s.get("duels_tentes", 0.0)
            cumul[po]["charge"] += charge(pid, mid)

    def taux(po, num, den):
        d = cumul[po].get(den, 0.0)
        return (cumul[po].get(num, 0.0) / d) if d else 0.0

    EXC_DUELS = {"duel_lost": -1.5, "dribbled_past": -3.0, "fouls": -1.5}
    EXC_CHARGE = {"recoveries": 0.5, "clearances": 0.8,
                  "headed_clearance": 1.0, "interceptions": 2.4}
    ANNULE = {"dribbled_past": -1.5, "fouls": -0.8, "ShotsOnTarget": 1.3,
              "duel_lost": -0.30, "dispossessed": -0.4,
              "recoveries": 0.25, "clearances": 0.4,
              "headed_clearance": 0.5, "interceptions": 1.2}
    for (pid, mid), s in par_match.items():
        j = joueurs[pid]
        po = profil_global.get(pid, j["poste"])
        date, coef, _p, _ph = matchs[mid]
        coef *= coef_adverse(pid, mid)
        # Chaque correction retourne DANS SA FAMILLE. Tout atterrissait
        # auparavant dans Defense, y compris la precision de tir et la
        # conservation du ballon : la note defensive d'un attaquant etait donc
        # faite a 96 % de corrections offensives. C'est ce qui placait Messi
        # au sommet de l'axe defensif.
        part = defaultdict(float)
        for cle, val in ANNULE.items():          # on retire le comptage en volume
            cible = ("Finition" if cle == "ShotsOnTarget" else
                     "Conduite" if cle == "dispossessed" else "Defense")
            part[cible] -= s.get(cle, 0.0) * val
        part["Conduite"] -= 3.0 * (
            s.get("dispossessed", 0.0)
            - taux(po, "dispossessed", "touches") * s.get("touches", 0.0))
        for cle, poids in EXC_DUELS.items():
            part["Defense"] += poids * (
                s.get(cle, 0.0)
                - taux(po, cle, "duels_tentes") * s.get("duels_tentes", 0.0))
        part["Finition"] += 1.5 * (
            s.get("ShotsOnTarget", 0.0)
            - taux(po, "ShotsOnTarget", "total_shots") * s.get("total_shots", 0.0))
        c = charge(pid, mid)
        for cle, poids in EXC_CHARGE.items():
            # Ce qu'on attend defensivement depend de la POSITION sur le
            # terrain, pas du style de jeu : utiliser le profil transformait
            # la moindre action defensive d'un creatif en excedent.
            part["Defense"] += poids * (s.get(cle, 0.0) - taux(po, cle, "charge") * c)
        for famille, v in part.items():
            v *= coef
            j["brut"] += v
            j["familles"][famille] += v
            j["evenements"][date] += v
            j["par_famille_date"][famille][date] += v
            j["par_cle_date"]["correction_" + famille][date] += v

    # ------------------------------------------------------------------
    # DONNEES FBREF — INTEGRATION MATCH PAR MATCH
    # Les metriques sont appliquees a la rencontre ou elles ont ete produites,
    # avec son coefficient de competition et sa force d'adversaire, exactement
    # comme les donnees FotMob. Plus d'extrapolation, plus de plafond, plus
    # d'echelle : les points s'additionnent match apres match, sur la meme
    # unite que la table POINTS.
    # Chaque ligne reste un EXCEDENT : on retranche ce qu'un joueur du meme
    # profil produit dans le meme temps de jeu.
    if FBREF_MATCHS.exists():
        lignes = json.loads(FBREF_MATCHS.read_text())
        cumul = defaultdict(lambda: defaultdict(float))
        for r in lignes:
            j_ = joueurs.get(r["p"])
            if j_ is None:
                continue
            pr = profil_global.get(r["p"], j_["poste"])
            c = cumul[pr]
            c["min"] += r["min"]
            for cle in POIDS_FBREF:
                c[cle] += r.get(cle, 0.0)
            for k in ("ad_n", "ad_d", "lp_n", "lp_d", "ae_n", "ae_d"):
                c[k] += r.get(k, 0.0)
        for r in lignes:
            j_ = joueurs.get(r["p"])
            mid = r["m"]
            if j_ is None or mid not in matchs:
                continue
            date, coef, _p, _ph = matchs[mid]
            coef *= coef_adverse(r["p"], mid)
            pr = profil_global.get(r["p"], j_["poste"])
            c = cumul[pr]
            part = r["min"] / c["min"] if c["min"] else 0.0
            gagne = 0.0
            for cle, (poids, famille) in POIDS_FBREF.items():
                attendu = c[cle] * part
                g = (r.get(cle, 0.0) - attendu) * poids * coef
                gagne += g
                j_["familles"][famille] = j_["familles"].get(famille, 0.0) + g
                j_["par_famille_date"][famille][date] += g
                j_["par_cle_date"][cle][date] += g
            # taux de reussite : excedent sur le taux du profil, rapporte aux
            # tentatives du joueur dans CE match
            for n_, d_, poids, famille in (("ad_n", "ad_d", POIDS_TAUX["anti_dribble"], "Defense"),
                                           ("lp_n", "lp_d", POIDS_TAUX["passes_longues"], "Creation"),
                                           ("ae_n", "ae_d", POIDS_TAUX["aeriens"], "Defense")):
                den = r.get(d_, 0.0)
                if den <= 0 or c[d_] <= 0:
                    continue
                taux_profil = c[n_] / c[d_]
                g = (r.get(n_, 0.0) - taux_profil * den) * poids * coef
                gagne += g
                j_["familles"][famille] = j_["familles"].get(famille, 0.0) + g
                j_["par_famille_date"][famille][date] += g
                j_["par_cle_date"]["fbref_" + n_[:2]][date] += g
            j_["brut"] += gagne
            j_["evenements"][date] += gagne

    # Donnees physiques. Presentes sur 190 matchs seulement, tous en Ligue des
    # champions : 906 joueurs en ont, les autres aucune. On ne peut donc pas
    # les compter en volume, sinon jouer la C1 rapporterait des points en soi.
    # On mesure un RYTHME — sprints et distance par 90 sur les seuls matchs
    # documentes — puis on credite l'ecart au rythme median de son poste,
    # applique au temps de jeu total. Un joueur sans donnee reste a zero, donc
    # exactement neutre : il ne gagne ni ne perd.
    if POIDS_PHYSIQUE:
        phys = defaultdict(lambda: defaultdict(float))
        mn_phys = defaultdict(float)
        for pid, mid, cle, val in conn.execute(f"""
                SELECT s.player_id, s.match_id, s.stat_key, s.value FROM stat s
                JOIN match m ON m.match_id = s.match_id AND m.usable = 1
                WHERE s.stat_key IN ({",".join("?" * len(PHYSIQUE))})""",
                tuple(PHYSIQUE)):
            if pid in joueurs:
                phys[pid][cle] += val or 0.0
        for pid, mid, mn in conn.execute("""
                SELECT s.player_id, s.match_id, s.value FROM stat s
                JOIN match m ON m.match_id = s.match_id AND m.usable = 1
                WHERE s.stat_key = 'minutes_played' AND s.value > 0
                  AND EXISTS (SELECT 1 FROM stat p WHERE p.match_id = s.match_id
                              AND p.player_id = s.player_id
                              AND p.stat_key = 'physical_metrics_sprinting')"""):
            if pid in joueurs:
                mn_phys[pid] += mn
        rythmes = {}
        for pid, mn in mn_phys.items():
            if mn >= 180:                     # deux matchs pleins minimum
                rythmes[pid] = {c: phys[pid].get(c, 0.0) / mn * 90 for c in PHYSIQUE}
        normes = {}
        for poste in ORDRE:
            gens = [r for p, r in rythmes.items() if joueurs[p]["poste"] == poste]
            if len(gens) >= 15:
                normes[poste] = {c: mediane([g[c] for g in gens]) for c in PHYSIQUE}
        for pid, r in rythmes.items():
            j = joueurs[pid]
            norme = normes.get(j["poste"])
            if not norme:
                continue
            gagne = sum((r[c] - norme[c]) * PHYSIQUE[c][1] for c in PHYSIQUE)
            gagne *= j["minutes"] / 90        # remis a l'echelle de la saison
            j["brut"] += gagne
            j["familles"][FAMILLE_PHYSIQUE] += gagne
            if j["evenements"]:
                k = gagne / len(j["evenements"])
                for d in list(j["evenements"]):
                    j["evenements"][d] += k
                    j["par_cle_date"]["physique"][d] += k

    # Construction, mesuree par le xGBuildup d'Understat.
    if POIDS_BUILDUP and UNDERSTAT.exists() and UNDERSTAT_ASSOC.exists():
        import csv as _csv
        vers_fotmob = {}
        with UNDERSTAT_ASSOC.open(encoding="utf-8-sig") as f:
            for ligne in _csv.reader(f):
                if len(ligne) >= 3 and str(ligne[2]).isdigit():
                    vers_fotmob[ligne[0]] = int(ligne[2])
        rythmes = {}
        with UNDERSTAT.open(encoding="utf-8-sig") as f:
            for ligne in _csv.DictReader(f):
                pid = vers_fotmob.get(ligne.get("player_name", ""))
                if pid is None or pid not in joueurs:
                    continue
                try:
                    mn = float(ligne.get("time") or 0)
                    bu = float(ligne.get("xGBuildup") or 0)
                except ValueError:
                    continue
                if mn >= SEUIL_BUILDUP:
                    # un joueur peut apparaitre dans deux championnats
                    a, b = rythmes.get(pid, (0.0, 0.0))
                    rythmes[pid] = (a + bu, b + mn)
        rythmes = {p: bu / mn * 90 for p, (bu, mn) in rythmes.items() if mn}
        normes = {}
        for poste in ORDRE:
            vals = [r for p, r in rythmes.items() if joueurs[p]["poste"] == poste]
            if len(vals) >= 15:
                normes[poste] = mediane(vals)
        for pid, r in rythmes.items():
            j = joueurs[pid]
            norme = normes.get(j["poste"])
            if norme is None:
                continue
            gagne = (r - norme) * POIDS_BUILDUP * j["minutes"] / 90
            j["brut"] += gagne
            j["familles"]["Creation"] += gagne
            if j["evenements"]:
                part = gagne / len(j["evenements"])
                for d in list(j["evenements"]):
                    j["evenements"][d] += part
                    j["par_cle_date"]["buildup"][d] += part

    # Progression par ballon touche. Le denominateur est le nombre de touches
    # DU MATCH, ce qui neutralise la possession de l'equipe ce jour-la.
    refs_prog = references_progression(conn, joueurs)
    touches_match = {}
    for pid, mid, v in conn.execute("""
            SELECT s.player_id, s.match_id, s.value FROM stat s
            JOIN match m ON m.match_id = s.match_id AND m.usable = 1
            WHERE s.stat_key = 'touches' AND s.value > 0"""):
        touches_match[(pid, mid)] = v
    marks_p = ",".join("?" * len(PROGRESSION))
    for pid, mid, cle, val in conn.execute(f"""
            SELECT s.player_id, s.match_id, s.stat_key, s.value FROM stat s
            JOIN match m ON m.match_id = s.match_id AND m.usable = 1
            WHERE s.stat_key IN ({marks_p})""", tuple(PROGRESSION)):
        j = joueurs.get(pid)
        if j is None or mid not in matchs or j["poste"] == "Gardien":
            continue
        t = touches_match.get((pid, mid), 0.0)
        base = refs_prog.get(j["poste"], {}).get(cle)
        if not t or base is None:
            continue
        date, coef, _p, _ph = matchs[mid]
        coef *= coef_adverse(pid, mid)
        gagne = ((val or 0.0) - base * t) * PROGRESSION[cle][1] * coef
        j["brut"] += gagne
        j["familles"][FAMILLE_PROGRESSION] += gagne
        j["evenements"][date] += gagne
        j["par_famille_date"][FAMILLE_PROGRESSION][date] += gagne
        j["par_cle_date"][cle][date] += gagne

    # Minutes datees : necessaires pour une course en points par 90, ou la
    # valeur affichee est un ratio et non un cumul.
    for pid, mid, mn in conn.execute("""
            SELECT s.player_id, s.match_id, s.value FROM stat s
            JOIN match m ON m.match_id = s.match_id AND m.usable = 1
            WHERE s.stat_key = 'minutes_played' AND s.value > 0"""):
        j = joueurs.get(pid)
        if j is not None and mid in matchs:
            j["minutes_par_date"][matchs[mid][0]] += mn

    # Actions a taux : on ne credite que l'excedent sur la reference du poste.
    refs = references(conn, joueurs)
    marks_f = ",".join("?" * len(FRACTIONS))
    for pid, mid, cle, val, tot in conn.execute(f"""
            SELECT s.player_id, s.match_id, s.stat_key, s.value, s.total
            FROM stat s JOIN match m ON m.match_id = s.match_id AND m.usable = 1
            WHERE s.stat_key IN ({marks_f}) AND s.total IS NOT NULL AND s.total > 0""",
            tuple(FRACTIONS)):
        j = joueurs.get(pid)
        if j is None or mid not in matchs:
            continue
        base = refs.get(_cle_reference(pid, j), {}).get(cle)
        if base is None:
            continue
        date, coef, _parent, _phase = matchs[mid]
        excedent = (val or 0.0) - base * tot
        gk = j["poste"] == "Gardien"
        mult = RELANCE_GK.get(cle, 1.0) if gk else 1.0
        if MODE_FRACTION == "taux":
            gagne = excedent * FRACTIONS[cle][1] * coef * mult
        elif MODE_FRACTION == "mixte":
            # Socle de volume — cinq dribbles reussis restent cinq dribbles —
            # plus une prime, ou un malus, selon qu'on fait mieux ou moins bien
            # que la reference de son poste. Le volume garde la main, la
            # qualite departage. Un joueur a 5/5 ne peut pas depasser un joueur
            # a 20/30 : l'excedent est proportionnel aux tentatives.
            gagne = ((val or 0.0) * FRACTIONS[cle][2]
                     + excedent * FRACTIONS[cle][1] * PART_EXCEDENT) * coef * mult
        else:
            gagne = (val or 0.0) * FRACTIONS[cle][2] * coef * mult
        famille = "Gardien" if j["poste"] == "Gardien" else FAMILLE_FRACTION[cle]
        j["brut"] += gagne
        j["familles"][famille] += gagne
        j["par_famille_date"][famille][date] += gagne
        j["par_cle_date"][cle][date] += gagne
        j["evenements"][date] += gagne

    # Taux de reussite dans les duels defensifs engages.
    if DUELS_DEFENSIFS:
        gagnes, perdus = defaultdict(float), defaultdict(float)
        for pid, cle, v in conn.execute(f"""
                SELECT s.player_id, s.stat_key, SUM(s.value) FROM stat s
                JOIN match m ON m.match_id = s.match_id AND m.usable = 1
                WHERE s.stat_key IN (?, ?) GROUP BY 1, 2""", DUELS_DEFENSIFS[:2]):
            if pid not in joueurs:
                continue
            (gagnes if cle == DUELS_DEFENSIFS[0] else perdus)[pid] = v or 0.0
        taux, poids = {}, DUELS_DEFENSIFS[2]
        for pid in joueurs:
            n = gagnes.get(pid, 0.0) + perdus.get(pid, 0.0)
            if n >= 20:
                taux[pid] = (gagnes.get(pid, 0.0) / n, n)
        refs_duel = {}
        for poste in ORDRE:
            v = [t for p, (t, _) in taux.items() if joueurs[p]["poste"] == poste]
            if len(v) >= 15:
                refs_duel[poste] = mediane(v)
        for pid, (t, n) in taux.items():
            j = joueurs[pid]
            base = refs_duel.get(j["poste"])
            if base is None:
                continue
            # excedent de taux, multiplie par le volume engage : un joueur a
            # 5 duels ne peut pas depasser un joueur a 100.
            gagne = (t - base) * n * poids
            j["brut"] += gagne
            j["familles"]["Defense"] += gagne
            if j["evenements"]:
                part = gagne / len(j["evenements"])
                for d in list(j["evenements"]):
                    j["evenements"][d] += part
                    j["par_famille_date"]["Defense"][d] += part
                    j["par_cle_date"]["taux_duels"][d] += part

    # Clean sheets : absents de la table stat, calcules ici. Etendus aux
    # defenseurs, pour qui c'est le seul indicateur de resultat collectif.
    for pid, mid, minutes, encaisse in conn.execute("""
            SELECT a.player_id, a.match_id, s.value,
                   CASE WHEN a.team_id = m.home_team_id THEN m.away_score
                        ELSE m.home_score END
            FROM appearance a
            JOIN match m ON m.match_id = a.match_id AND m.usable = 1
            JOIN stat s ON s.match_id = a.match_id AND s.player_id = a.player_id
                       AND s.stat_key = 'minutes_played'"""):
        j = joueurs.get(pid)
        if j is None or mid not in matchs:
            continue
        gardien = j["poste"] == "Gardien"
        if not gardien and j["poste"] not in POSTES_CLEAN_SHEET:
            continue
        if (minutes or 0) >= 60 and encaisse == 0:
            date, coef, _p, _ph = matchs[mid]
            if gardien and _p in CHAMPIONNATS_GK:
                coef = COEF_TOUR.get(_ph, 1.0)
            coef *= coef_adverse(pid, mid)
            gagne = (CLEAN_SHEET if gardien else CLEAN_SHEET_DEF) * coef
            j["brut"] += gagne
            j["familles"]["Gardien" if gardien else "Defense"] += gagne
            j["evenements"][date] += gagne
            j["par_famille_date"][("Gardien" if gardien else "Defense")][date] += gagne
            j["par_cle_date"]["clean_sheet"][date] += gagne

    # Coefficient de club, applique une fois sur le cumul du joueur.
    for pid, j in joueurs.items():
        k = clubs.get(equipe_de.get(pid))
        j["coef_club"] = round(k, 3) if k else 1.0
        if k and k != 1.0:
            j["brut"] *= k
            for f in list(j["familles"]):
                j["familles"][f] *= k
            for d in list(j["evenements"]):
                j["evenements"][d] *= k
            for c_ in j["par_cle_date"].values():
                for d in list(c_):
                    c_[d] *= k

    return joueurs


def percentile(valeurs, p):
    """Percentile avec interpolation lineaire."""
    v = sorted(valeurs)
    if not v:
        return 0.0
    k = (len(v) - 1) * p
    bas = int(k)
    haut = min(bas + 1, len(v) - 1)
    return v[bas] + (v[haut] - v[bas]) * (k - bas)


# Matrice des parts par poste. Sans elle, la part de chaque famille dans le
# total est un resultat, pas un choix : la finition pese 46 % chez un attaquant
# et 7 % chez un central parce que les attaquants marquent, pas parce qu'on
# l'a decide. La matrice inverse le sens de lecture — on fixe la part, et les
# valeurs d'action a l'interieur d'une famille sont mises a l'echelle pour
# l'atteindre. Les rapports internes ne bougent pas : un but vaut toujours
# quatorze tirs cadres.
# La Conduite est descendue de 25-30 % a 8 %. Elle pesait un quart du bareme
# alors qu'elle ne contient plus que trois cles marginales depuis le retrait
# de la passe reussie : dribbles, fautes subies, longs ballons. Sa mediane
# tombait a 1,5 par 90 et sa dispersion a 0,6, si bien qu'un dribbleur
# encaissait dix unites sur cette seule famille — Ounahi y prenait la moitie
# de son total, Schlotterbeck et Bensebaini montaient sur leurs longs ballons.
# Le poids libere va a la Defense chez les joueurs de devoir et a la Creation
# chez les joueurs de couloir et d'axe offensif.
MATRICE = {
    # Mise a jour apres le deplacement des passes et longs ballons vers la
    # Creation. Les cibles etaient calees sur une composition ou la Creation
    # ne contenait que les passes decisives et les occasions : elles la
    # sous-payaient de vingt points chez les defenseurs. Les nouvelles cibles
    # suivent les parts reellement produites, sauf la Defense qui reste un
    # choix editorial — 40 % chez le lateral, 25 % chez le 6, 15 % chez le 10.
    # Le central s'aligne lui aussi sur ses parts observees (3/33/8/56) : la
    # Creation y contient desormais les passes et les longs ballons, qui font
    # une part reelle du metier d'un defenseur moderne. La Defense reste
    # majoritaire, mais elle cesse d'ecraser le reste.
    "Defenseur central": {"Finition": 4,  "Creation": 32, "Conduite": 8,  "Defense": 56},
    "Lateral":           {"Finition": 8,  "Creation": 42, "Conduite": 10, "Defense": 40},
    "Milieu defensif":   {"Finition": 8,  "Creation": 55, "Conduite": 12, "Defense": 25},
    "Milieu relayeur":   {"Finition": 18, "Creation": 45, "Conduite": 12, "Defense": 25},
    "Milieu offensif":   {"Finition": 25, "Creation": 48, "Conduite": 12, "Defense": 15},
    "Ailier":            {"Finition": 32, "Creation": 38, "Conduite": 12, "Defense": 18},
    "Buteur":            {"Finition": 60, "Creation": 25, "Conduite": 8,  "Defense": 7},
}
# Active : les parts sont desormais un reglage et non un resultat. Cout mesure,
# +4 a +6 points de correlation avec la domination d'equipe, l'essentiel venant
# de la Conduite qu'on releve nettement au-dessus de son niveau naturel — payer
# la possession, c'est payer l'equipe autant que le joueur. Choix assume.
APPLIQUER_MATRICE = False

# Coefficients de poste calibres sur les rangs 2-5 : desactives. Le classement
# compare les joueurs sur la meme echelle, sans correction de poste.
APPLIQUER_COEF_POSTE = False

# Deux facons d'appliquer la matrice.
#
#   "echelle" — chaque famille est multipliee par cible / part_observee du
#     GROUPE. Le facteur est le meme pour tout le monde : un joueur faible dans
#     une famille voit lui aussi ses points multiplies. La matrice gonfle le
#     secteur, elle ne juge personne.
#
#   "ecart"   — chaque famille est comptee EN ECART A LA NORME DU POSTE. Le
#     joueur est credite de ce qu'il fait au-dessus du standard et debite de ce
#     qu'il fait en dessous. Un central mediocre defensivement perd des points
#     sur la famille qui pese 60 % chez lui. La norme est prelevee au prorata
#     des minutes, donc le calcul reste additif et les courses cumulent encore.
MODE_MATRICE = "ecart"

# Unite de dispersion du mode ecart.
#   "poste"   — l'ecart absolu moyen du poste. Etre atypique rapporte plus dans
#     un groupe homogene : chez les lateraux l'unite de conduite vaut 0,7, chez
#     les buteurs l'unite de finition vaut 2,2. Nuno Mendes convertissait son
#     avance en trois fois plus d'unites que Dembele.
#   "commune" — une seule unite par famille, calculee sur tous les joueurs de
#     champ. La norme reste celle du poste, seule l'echelle est partagee.
MODE_UNITE = "poste"

# Mesure de la dispersion, dans le mode ecart.
#   "mad"   ecart absolu median. Sur une famille pauvre — la Conduite ne
#     contient plus que dribbles, fautes subies et longs ballons — la masse
#     des joueurs est proche de zero, la mediane vaut 1,5 et l'ecart absolu
#     median 0,6. Un joueur a 7 encaisse alors dix unites : Ounahi tirait
#     ainsi la moitie de son total d'une seule famille.
#   "haut"  P90 moins mediane. Mesure l'ecart entre un bon joueur et un joueur
#     moyen, pas entre la masse et elle-meme. Insensible au tassement vers
#     zero, donc bien plus stable sur les familles pauvres.
MESURE_DISPERSION = "haut"

# Plafond de l'ecart credite dans une famille, en unites de dispersion.
# En mode ecart, etre a la norme rapporte zero — mais ne coute rien non plus.
# Un specialiste unidimensionnel encaissait donc tout son excedent sur une
# famille en restant neutre sur les trois autres : Odegaard tirait 88 % de son
# total de la seule Creation, Griezmann 64 %. Le plafond borne ce que peut
# rapporter une famille et redonne la main aux profils complets.
# 0 = pas de plafond.
# Releve de 5 a 7. A 5, le plafond frappait surtout les profils atypiques :
# Dembele cree 29,2 points par 90 quand la norme des buteurs est a 4,3, soit
# 19 unites d'ecart dont 14 lui etaient confisquees, contre 5 seulement a Nuno
# Mendes. Le plafond avait ete pose pour resserrer les ecarts, travail que le
# calibrage a rang fixe assure desormais. A 7, plus rien ne bouge au-dela.
# Retire. Il bornait ce qu'une famille pouvait rapporter, mais au-dela de 7
# unites il ne changeait deja plus rien, et il penalisait les profils
# atypiques : Dembele creait 19 unites au-dessus de la norme des buteurs et
# s'en voyait confisquer la moitie. Le calibrage sur les rangs 2-5 tient
# desormais les ecarts.
PLAFOND_ECART = 0.0

# Niveau de reference soustrait dans chaque famille. None = mediane du poste
# (un joueur median marque zero). Un quantile plus bas remonte les joueurs
# moyens et cesse d'amplifier les ecarts entre les meilleurs.
NORME_QUANTILE = 0.25


def mediane(valeurs):
    v = sorted(valeurs)
    if not v:
        return 0.0
    n = len(v)
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2


def reponderer_ecart(joueurs):
    """Chaque famille comptee en ecart a la norme du poste, pas en volume.

    norme      : mediane du poste, en points par 90 minutes
    dispersion : ecart absolu moyen du poste, qui sert d'unite
    poids      : la cible de la matrice, appliquee a cette unite

    Un joueur exactement dans la norme marque zero sur la famille. Au-dessus il
    gagne, en dessous il perd — proportionnellement, et d'autant plus fort que
    la famille pese lourd a son poste.
    """
    communes = {}
    if MODE_UNITE == "commune":
        champ = [j for j in joueurs.values()
                 if j["poste"] in MATRICE and j["minutes"]]
        for famille in ("Finition", "Creation", "Conduite", "Defense"):
            par90 = [j["familles"].get(famille, 0.0) / j["minutes"] * 90
                     for j in champ]
            n = mediane(par90)
            communes[famille] = ((percentile(par90, 0.90) - n)
                                 if MESURE_DISPERSION == "haut"
                                 else mediane([abs(v - n) for v in par90])) or 1.0

    for poste, cibles in MATRICE.items():
        groupe = [j for j in joueurs.values()
                  if j["poste"] == poste and j["minutes"]]
        if len(groupe) < 20:
            continue
        for famille, cible in cibles.items():
            par90 = [j["familles"].get(famille, 0.0) / j["minutes"] * 90
                     for j in groupe]
            # la norme soustraite peut descendre sous la mediane, mais l'unite
            # de dispersion reste celle d'origine : P90 moins MEDIANE.
            centre = mediane(par90)
            norme = (percentile(par90, NORME_QUANTILE)
                     if NORME_QUANTILE is not None else centre)
            if MESURE_DISPERSION == "haut":
                brute = percentile(par90, 0.90) - centre
            else:
                brute = mediane([abs(v - centre) for v in par90])
            dispersion = communes.get(famille) or brute or 1.0
            poids = cible / dispersion
            for j in groupe:
                v = j["familles"].get(famille, 0.0) / j["minutes"] * 90
                unites = (v - norme) / dispersion
                if PLAFOND_ECART:
                    unites = max(-PLAFOND_ECART, min(PLAFOND_ECART, unites))
                # remis en volume : la norme est prelevee au prorata des minutes
                j["familles"][famille] = unites * cible * j["minutes"] / 90
        for j in groupe:
            avant = j["brut"]
            j["brut"] = sum(j["familles"].values())
            if avant:
                k = j["brut"] / avant
                for d in list(j["evenements"]):
                    j["evenements"][d] *= k
    return joueurs


def reponderer(joueurs):
    """Ramene la part de chaque famille, poste par poste, sur sa cible."""
    if not APPLIQUER_MATRICE:
        return joueurs
    if MODE_MATRICE == "ecart":
        return reponderer_ecart(joueurs)
    for poste, cibles in MATRICE.items():
        groupe = [j for j in joueurs.values() if j["poste"] == poste]
        if not groupe:
            continue
        totaux = {f: sum(j["familles"].get(f, 0.0) for j in groupe) for f in cibles}
        somme = sum(totaux.values())
        if somme <= 0:
            continue
        facteurs = {f: (cibles[f] / 100 * somme / totaux[f]) if totaux[f] > 0 else 0.0
                    for f in cibles}
        for j in groupe:
            avant = j["brut"]
            for f in cibles:
                j["familles"][f] = j["familles"].get(f, 0.0) * facteurs[f]
            j["brut"] = sum(j["familles"].values())
            # Le flux date sert aux courses : on le met a l'echelle du total.
            if avant:
                k = j["brut"] / avant
                for d in list(j["evenements"]):
                    j["evenements"][d] *= k
    return joueurs


# Retrecissement des petits echantillons : un par 90 calcule sur quelques
# matchs n'est pas comparable a un par 90 de saison. Le score est ramene vers
# la mediane du poste avec un poids minutes / (minutes + K). A K = 1200, un
# joueur a 740 minutes compte a 38 % de son propre par 90 et 62 % de la
# reference de son poste ; au-dela de 3000 minutes l'effet devient negligeable.
K_RETRECISSEMENT = 1200
import os
FBREF_MATCHS = pathlib.Path("fbref_matchs.json")
TITULAIRE = pathlib.Path("titulaire_dispo.json")
ENTRANTS = set()
COEF_ENTRANT = 0.7        # points marques en entrant, escomptes
EXP_ROLE = 1.0
# (points par action, famille) — meme unite que la table POINTS : un but = 10
POIDS_FBREF = {
    "passes_prog":       (1.2, "Creation"),
    "conduites_prog":    (0.8, "Conduite"),
    "dist_conduite":     (0.25, "Conduite"),     # par hectometre progresse
    "conduites_tiers":   (0.8, "Conduite"),
    "conduites_surface": (1.5, "Conduite"),
    "prog_recues":       (0.4, "Creation"),
    "passes_surface":    (1.5, "Creation"),
    "centres_surface":   (1.0, "Creation"),
    "profondeur":        (2.0, "Creation"),
    "changements_aile":  (0.5, "Creation"),
    "tacles_haut":       (2.5, "Defense"),
    "tacles_milieu":     (0.8, "Defense"),
    "passes_bloquees":   (0.5, "Defense"),
    "erreurs_tir":       (-3.0, "Defense"),
    "controles_rates":   (-0.5, "Conduite"),
}
POIDS_TAUX = {"anti_dribble": 2.0, "passes_longues": 0.5, "aeriens": 0.6}



def aligner_gardiens(joueurs):
    """Ramene le poste de gardien sur la meme echelle que les autres.

    Les gardiens n'ont ni finition ni creation : leur score se compose d'un
    petit nombre de lignes qui, revalorisees pour distinguer les meilleurs,
    ont decale TOUT le poste vers le haut. La hierarchie interne des gardiens
    est juste ; c'est leur niveau moyen qui ne l'est pas. On recale donc le
    poste pour que le gardien MEDIAN vaille le joueur de champ MEDIAN — aucun
    coefficient pose a la main, et la regle vaut pour toutes les saisons.
    """
    gk = [d["par90"] for d in joueurs.values() if d.get("poste") == "Gardien"]
    champ = [d["par90"] for d in joueurs.values() if d.get("poste") != "Gardien"]
    if not gk or not champ:
        return joueurs
    m_gk, m_ch = mediane(gk), mediane(champ)
    if m_gk <= 0:
        return joueurs
    k = m_ch / m_gk
    for d in joueurs.values():
        if d.get("poste") == "Gardien":
            d["par90"] *= k
    return joueurs


def facteur_role(joueurs, conn):
    """Un remplaçant a un par 90 flatte : il entre contre des jambes lourdes,
    dans des matchs ouverts, et n'assume jamais une rencontre entiere. On
    corrige donc le score par la part de match reellement assumee — minutes
    rapportees aux feuilles de match — normalisee sur le titulaire median.
    """
    if not EXP_ROLE:
        return joueurs
    # Le STATUT (titulaire ou remplacant), pas le volume de minutes : sinon on
    # compte deux fois le meme fait, le retrecissement penalisant deja le
    # faible temps de jeu. La part de titularisations vient des feuilles de
    # match FBref.
    if not TITULAIRE.exists():
        return joueurs
    brut = json.loads(TITULAIRE.read_text())
    parts = {}
    for pid, d in joueurs.items():
        v = brut.get(str(pid))
        if v is not None:
            parts[pid] = max(min(float(v), 1.0), 0.05)
    if not parts:
        return joueurs
    reference = mediane([v for v in parts.values() if v >= 0.75]) or 1.0
    for pid, d in joueurs.items():
        p = parts.get(pid)
        if p:
            d["par90"] *= (p / reference) ** EXP_ROLE
    return joueurs


def retrecir(joueurs):
    from collections import defaultdict as _dd
    par_poste = _dd(list)
    for d in joueurs.values():
        if d.get("minutes", 0) >= 2000:
            par_poste[d.get("poste")].append(d["par90"])
    med = {p: mediane(v) for p, v in par_poste.items() if v}
    for d in joueurs.values():
        m = d.get("minutes", 0.0)
        ref = med.get(d.get("poste"))
        if ref is None or m <= 0:
            continue
        w = m / (m + K_RETRECISSEMENT)
        d["par90"] = w * d["par90"] + (1 - w) * ref
    return joueurs


def calibrer(joueurs):
    """Coefficient de poste : le percentile 95 du poste ramene a la cible.

    Deux pieges evites ici.

    Calibrer sur les totaux cumules aurait importe les ecarts de temps de jeu
    entre postes dans le coefficient lui-meme : un attaquant sorti a l'heure de
    jeu chaque semaine aurait tire son poste vers le bas. D'ou le par 90.

    Calibrer sur la mediane d'un NOMBRE FIXE de joueurs — le top 20 — posait
    une barre differente selon la taille du poste : pour 65 milieux offensifs
    le top 20 est l'elite des 31 %, pour 458 defenseurs centraux l'elite des
    4 %. Les petits effectifs etaient calibres bien trop bas et trustaient le
    haut du classement general — six milieux offensifs dans le top 20 pour
    3 % du vivier, zero milieu axial pour 22 %. Un PERCENTILE pose la meme
    barre partout, quel que soit l'effectif.
    """
    coefs = {}
    debut, fin = RANGS_CALIBRAGE
    for poste in ORDRE:
        vals = sorted((j["brut"] / j["minutes"] * 90 for j in joueurs.values()
                       if j["poste"] == poste and j["minutes"]), reverse=True)
        if len(vals) < 20:
            continue
        tranche = vals[debut - 1:fin]
        ref = sum(tranche) / len(tranche) if tranche else 0.0
        coefs[poste] = round(CIBLE_CALIBRAGE / ref, 4) if ref else 1.0
    return coefs


def appliquer(joueurs, coefs, conn=None):
    if not APPLIQUER_COEF_POSTE:
        coefs = {k: 1.0 for k in coefs}
    for j in joueurs.values():
        k = coefs[j["poste"]]
        j["total"] = j["brut"] * k
        j["familles"] = {f: v * k for f, v in j["familles"].items()}
        j["evenements"] = {d: v * k for d, v in j["evenements"].items()}
        j["par90"] = j["total"] / j["minutes"] * 90 if j["minutes"] else 0.0
    joueurs = aligner_gardiens(retrecir(joueurs))
    return facteur_role(joueurs, conn) if conn is not None else joueurs


def exporter_xlsx(joueurs, coefs, chemin="bareme_stats.xlsx"):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    entete = Font(name="Arial", size=10, bold=True, color="FFFFFF")
    fond = PatternFill("solid", fgColor="0A0A0C")
    normal = Font(name="Arial", size=10)
    gras = Font(name="Arial", size=10, bold=True)

    wb = Workbook()

    ws = wb.active
    ws.title = "Bareme"
    ws["A1"] = "BAREME STATS AVANCEES — points par action"
    ws["A1"].font = gras
    ws["A2"] = ("points(joueur, match) = coef poste x coef competition x coef tour "
                "x somme(valeur action x points action)")
    ws["A2"].font = normal
    r = 4
    for famille, table in POINTS.items():
        ws.cell(row=r, column=1, value=famille.upper()).font = gras
        r += 1
        for cle, (lib, pts) in sorted(table.items(), key=lambda kv: -kv[1][1]):
            ws.cell(row=r, column=1, value=lib).font = normal
            c = ws.cell(row=r, column=2, value=pts)
            c.font = normal
            c.number_format = "0.00"
            ws.cell(row=r, column=3, value=cle).font = Font(name="Arial", size=8,
                                                            color="808080")
            r += 1
        r += 1
    ws.cell(row=r, column=1, value="ACTIONS A TAUX DE REUSSITE").font = gras
    r += 1
    for cle, val in sorted(FRACTIONS.items(), key=lambda kv: -kv[1][2]):
        ws.cell(row=r, column=1, value=val[0]).font = normal
        c = ws.cell(row=r, column=2, value=val[1] if MODE_TAUX else val[2])
        c.font = normal
        c.number_format = "0.00"
        ws.cell(row=r, column=3, value=cle).font = Font(name="Arial", size=8,
                                                        color="808080")
        r += 1
    ws.cell(row=r, column=1,
            value=("points = (reussites - taux reference x tentatives) x valeur"
                   if MODE_TAUX else
                   "points = reussites x valeur (mode volume, par defaut)")).font = normal
    r += 2
    ws.cell(row=r, column=1, value="Clean sheet (gardien, >= 60 min)").font = normal
    ws.cell(row=r, column=2, value=CLEAN_SHEET).font = normal
    r += 2
    ws.cell(row=r, column=1, value="Note : les cles de la famille Gardien ne sont "
                                   "creditees qu'aux gardiens, et inversement.").font = normal
    ws.column_dimensions["A"].width = 34
    ws.column_dimensions["B"].width = 10
    ws.column_dimensions["C"].width = 32

    ws = wb.create_sheet("Coefficients")
    ws["A1"] = "COMPETITIONS"
    ws["A1"].font = gras
    r = 2
    for nom, coef in sorted(COEF_COMPET_NOM.items(), key=lambda kv: (-kv[1], kv[0])):
        ws.cell(row=r, column=1, value=nom).font = normal
        ws.cell(row=r, column=2, value=coef).font = normal
        r += 1
    ws.cell(row=r, column=1, value="Autre competition").font = normal
    ws.cell(row=r, column=2, value=COEF_DEFAUT).font = normal

    ws["D1"] = "TOURS"
    ws["D1"].font = gras
    for i, (phase, coef) in enumerate(COEF_TOUR.items(), 2):
        ws.cell(row=i, column=4, value=phase).font = normal
        ws.cell(row=i, column=5, value=coef).font = normal
    ws["D13"] = "Exemple : un dribble en finale de LDC"
    ws["D13"].font = gras
    ws["D14"] = "2,0 x 2,2 = 4,4 fois le meme dribble en Liga"
    ws["D14"].font = normal

    ws["G1"] = "POSTES (calibres)"
    ws["G1"].font = gras
    for i, poste in enumerate(ORDRE, 2):
        ws.cell(row=i, column=7, value=poste).font = normal
        c = ws.cell(row=i, column=8, value=coefs[poste])
        c.font = normal
        c.number_format = "0.0000"
    ws["G11"] = "Calibrage : percentile 95 de chaque poste ramene a 100."
    ws["G11"].font = normal
    ws["G12"] = "Sans effet sur le classement A L'INTERIEUR d'un poste."
    ws["G12"].font = normal
    for col, w in (("A", 26), ("B", 8), ("D", 22), ("E", 8), ("G", 20), ("H", 12)):
        ws.column_dimensions[col].width = w

    familles_champ = ["Finition", "Creation", "Conduite", "Defense"]
    for titre, sel, familles in (
            ("Classement", lambda j: j["poste"] != "Gardien", familles_champ),
            ("Gardiens", lambda j: j["poste"] == "Gardien", ["Gardien"])):
        ws = wb.create_sheet(titre)
        cols = (["Rang", "Joueur", "Club", "Poste", "Fiabilite poste", "Minutes"]
                + [f + " /90" for f in familles] + ["Points / 90 min", "Cumul saison"])
        for j, t in enumerate(cols, 1):
            c = ws.cell(row=1, column=j, value=t)
            c.font = entete
            c.fill = fond
            c.alignment = Alignment(horizontal="center", wrap_text=True)
        lst = sorted((j for j in joueurs.values() if sel(j)),
                     key=lambda j: -j["par90"])
        n = len(familles)
        for i, j in enumerate(lst, 2):
            ws.cell(row=i, column=1, value=i - 1)
            ws.cell(row=i, column=2, value=j["nom"])
            ws.cell(row=i, column=3, value=j["club"])
            ws.cell(row=i, column=4, value=j["poste"])
            c = ws.cell(row=i, column=5, value=round(j.get("fiabilite", 0), 3))
            c.number_format = "0 %"
            ws.cell(row=i, column=6, value=round(j["minutes"]))
            for k, fam in enumerate(familles):
                ws.cell(row=i, column=7 + k,
                        value=round(j["familles"].get(fam, 0.0) / j["minutes"] * 90, 2))
            a, b = get_column_letter(7), get_column_letter(6 + n)
            ws.cell(row=i, column=7 + n, value=f"=SUM({a}{i}:{b}{i})")
            ws.cell(row=i, column=8 + n, value=round(j["total"], 1))
            for k in range(1, 9 + n):
                cell = ws.cell(row=i, column=k)
                cell.font = normal
                if k == 5:
                    cell.number_format = "0 %"
                elif k >= 7:
                    cell.number_format = "0.00" if k <= 7 + n else "0.0"
        ws.freeze_panes = "B2"
        for k, w in enumerate([6, 26, 24, 18, 13, 9] + [11] * n + [15, 13], 1):
            ws.column_dimensions[get_column_letter(k)].width = w

    ws = wb.create_sheet("Par poste")
    col = 1
    for poste in ORDRE:
        lst = sorted((j for j in joueurs.values() if j["poste"] == poste),
                     key=lambda j: -j["par90"])[:15]
        c = ws.cell(row=1, column=col, value=poste.upper())
        c.font = entete
        c.fill = fond
        ws.cell(row=1, column=col + 1, value="Pts/90").font = entete
        ws.cell(row=1, column=col + 1).fill = fond
        for i, j in enumerate(lst, 2):
            ws.cell(row=i, column=col, value=f"{i - 1}. {j['nom']}").font = normal
            c = ws.cell(row=i, column=col + 1, value=round(j["par90"], 2))
            c.font = normal
            c.number_format = "0.00"
        ws.column_dimensions[get_column_letter(col)].width = 27
        ws.column_dimensions[get_column_letter(col + 1)].width = 8
        col += 2

    wb.save(chemin)
    return chemin


def paliers(conn):
    """Combien de joueurs survivent a chaque seuil, pour choisir en connaissance."""
    rows = conn.execute("""
        SELECT s.player_id, SUM(s.value) FROM stat s
        JOIN match m ON m.match_id = s.match_id AND m.usable = 1
        WHERE s.stat_key = 'minutes_played' AND s.value > 0
        GROUP BY s.player_id""").fetchall()
    print("PALIERS DE TEMPS DE JEU\n")
    print(f"  {'seuil':>7}  {'matchs pleins':>14}  {'joueurs':>8}")
    for seuil in (450, 900, 1350, 1800, 2250, 2700):
        n = sum(1 for _, mn in rows if (mn or 0) >= seuil)
        print(f"  {seuil:>7}  {seuil / 90:>14.0f}  {n:>8}")
    print("\n  450   remplacants reguliers : ratio instable, un seul gros match")
    print("        suffit a faire basculer un par 90")
    print("  1350  defaut : assez de matiere pour lisser, assez large pour")
    print("        garder un joueur blesse une demi-saison")
    print("  1800  titulaires stricts, au prix des retours de blessure\n")


def auditer_postes(conn, joueurs, limite=15):
    """Liste les joueurs du haut de tableau dont le poste n'est pas certain."""
    print("Fiabilite du poste attribue — part des minutes jouees a ce poste\n")
    for seuil in (0.95, 0.90, 0.80, 0.70):
        n = sum(1 for j in joueurs.values() if j.get("fiabilite", 0) >= seuil)
        print(f"   >= {seuil:.0%} : {n:>5} joueurs sur {len(joueurs)}")
    print(f"\nCas a trancher — top {limite} de chaque poste, fiabilite < 70 %\n")
    reste = 0
    for poste in ORDRE:
        groupe = sorted((j for j in joueurs.values() if j["poste"] == poste),
                        key=lambda j: -j["par90"])[:limite]
        for rang, j in enumerate(groupe, 1):
            if j.get("fiabilite", 1) >= 0.70:
                continue
            reste += 1
            pid = next((k for k, v in joueurs.items() if v is j), None)
            rep = REPARTITION.get(pid, [])
            total = sum(v for _, v in rep) or 1
            detail = " · ".join(f"{g} {v / total * 100:.0f}%" for g, v in rep[:3])
            print(f"   {poste:<20}{rang:>3}e {j['nom'][:22]:<24}"
                  f"{j.get('fiabilite', 0):>5.0%}   {detail}")
    print(f"\n   {reste} cas — a inscrire dans {MANUEL_POSTES} apres arbitrage")


def main():
    if not DB_PATH.exists():
        raise SystemExit("fotmob.db introuvable.")
    conn = sqlite3.connect(DB_PATH)

    if "--audit-postes" in sys.argv:
        seuil = int(sys.argv[sys.argv.index("--min") + 1]) if "--min" in sys.argv else SEUIL_DEFAUT
        js = reponderer(charger(conn, seuil, SEUIL_CHAMPIONNAT))
        auditer_postes(conn, appliquer(js, calibrer(js)))
        return
    if "--paliers" in sys.argv:
        paliers(conn)
        return

    global MODE_FRACTION, APPLIQUER_MATRICE, COEF_DEFAUT, AMPLITUDE_ADVERSAIRE
    if "--neutre" in sys.argv:
        # Toute la ponderation de contexte est neutralisee : competition, tour
        # et adversaire valent 1. Il ne reste que ce que le joueur a produit,
        # ramene a 90 minutes. Un but en Ligue 1 vaut alors exactement un but
        # en finale de Ligue des champions contre le Bayern.
        for cle in COEF_COMPET_NOM:
            COEF_COMPET_NOM[cle] = 1.0
        for cle in COEF_TOUR:
            COEF_TOUR[cle] = 1.0
        COEF_DEFAUT = 1.0
        AMPLITUDE_ADVERSAIRE = 0.0
        globals()["COEFS"] = pathlib.Path("bareme_stats_neutre_coefs.json")
    if "--taux" in sys.argv:
        MODE_FRACTION = "taux"
    elif "--volume" in sys.argv:
        MODE_FRACTION = "volume"
    APPLIQUER_MATRICE = "--sans-matrice" not in sys.argv
    seuil = SEUIL_DEFAUT
    if "--min" in sys.argv:
        seuil = int(sys.argv[sys.argv.index("--min") + 1])
    seuil_champ = SEUIL_CHAMPIONNAT
    if "--min-champ" in sys.argv:
        seuil_champ = int(sys.argv[sys.argv.index("--min-champ") + 1])

    joueurs = reponderer(charger(conn, seuil, seuil_champ))

    fichier = json.loads(COEFS.read_text(encoding="utf-8")) if COEFS.exists() else {}
    if (fichier.get("mode") == "par90" and fichier.get("seuil") == [seuil, seuil_champ]
            and "--recalibrer" not in sys.argv):
        coefs = fichier["coefs"]
    else:
        coefs = calibrer(joueurs)
        COEFS.write_text(json.dumps({"mode": "par90", "seuil": [seuil, seuil_champ],
                                     "coefs": coefs,
                                     "references": references(conn, joueurs)},
                                    ensure_ascii=False, indent=2), encoding="utf-8")
        print("Coefficients de poste recalibres :")
        for poste in ORDRE:
            print(f"  {poste:<20}{coefs[poste]:>8.4f}")
        print()

    joueurs = appliquer(joueurs, coefs)

    champ = sorted((j for j in joueurs.values() if j["poste"] != "Gardien"),
                   key=lambda j: -j["par90"])
    gardiens = sorted((j for j in joueurs.values() if j["poste"] == "Gardien"),
                      key=lambda j: -j["par90"])

    n_gk = sum(1 for j in joueurs.values() if j["poste"] == "Gardien")
    print(f"{len(joueurs)} joueurs retenus : >= {seuil} min au total dont "
          f">= {seuil_champ} en championnat")
    print(f"  et, pour les {n_gk} gardiens, >= {SEUIL_GARDIEN} min\n")
    print(f"{'#':>3} {'joueur':<25}{'club':<22}{'poste':<19}{'/90':>7}{'cumul':>8}{'min':>7}")
    for i, j in enumerate(champ[:30], 1):
        print(f"{i:>3} {j['nom'][:24]:<25}{str(j['club'])[:21]:<22}"
              f"{j['poste']:<19}{j['par90']:>7.2f}{j['total']:>8.1f}{j['minutes']:>7.0f}")
    print("\nGardiens :")
    for i, j in enumerate(gardiens[:10], 1):
        print(f"{i:>3} {j['nom'][:24]:<25}{str(j['club'])[:21]:<22}"
              f"{'':<19}{j['par90']:>7.2f}{j['total']:>8.1f}{j['minutes']:>7.0f}")

    print("\n--- par poste ---")
    for poste in ORDRE:
        lst = sorted((j for j in joueurs.values() if j["poste"] == poste),
                     key=lambda j: -j["par90"])[:8]
        print(f"\n{poste}")
        for i, j in enumerate(lst, 1):
            print(f"  {i}. {j['nom'][:26]:<28}{str(j['club'])[:20]:<22}"
                  f"{j['par90']:>6.2f}{j['minutes']:>7.0f} min")

    if "--events" in sys.argv or "--xlsx" in sys.argv:
        # Le flux ne sert qu'aux courses : on le limite aux joueurs
        # susceptibles d'y figurer, sinon le fichier depasse 9 Mo.
        # Deux tris, pas un seul. Ne retenir que le top 20 au CUMUL faisait
        # disparaitre du flux les joueurs a fort rendement et faible temps de
        # jeu : Safonov, 3e gardien du bareme en points par 90, n'etait que
        # 25e au cumul et n'apparaissait donc dans aucune course.
        retenus = set()
        for poste in ORDRE:
            groupe = [j for j in joueurs.values() if j["poste"] == poste]
            retenus |= {id(j) for j in sorted(groupe, key=lambda j: -j["total"])[:20]}
            retenus |= {id(j) for j in sorted(groupe, key=lambda j: -j["par90"])[:20]}
        retenus |= {id(j) for j in champ[:40]}
        retenus |= {id(j) for j in sorted(champ, key=lambda j: -j["par90"])[:40]}
        cle_de = {id(v): k for k, v in joueurs.items()}
        flux = []
        for j in (x for x in joueurs.values() if id(x) in retenus):
            for date, pts in sorted(j["evenements"].items()):
                flux.append({"date": date, "player_id": cle_de[id(j)],
                             "team_id": j.get("team_id"), "joueur": j["nom"],
                             "club": j["club"], "poste": j["poste"],
                             "points": round(pts, 2),
                             "minutes": round(j["minutes_par_date"].get(date, 0))})
        flux.sort(key=lambda e: e["date"])
        familles = []
        for j in (x for x in joueurs.values() if id(x) in retenus):
            for fam, dates in j["par_famille_date"].items():
                for date, pts in sorted(dates.items()):
                    familles.append({"date": date, "player_id": cle_de[id(j)],
                                     "team_id": j.get("team_id"), "joueur": j["nom"],
                                     "club": j["club"], "poste": j["poste"],
                                     "famille": fam, "points": round(pts, 2),
                                     "minutes": round(j["minutes_par_date"].get(date, 0))})
        familles.sort(key=lambda e: e["date"])
        pathlib.Path("bareme_stats_familles.json").write_text(
            json.dumps({"bareme": "stats par famille", "evenements": familles},
                       ensure_ascii=False), encoding="utf-8")
        print(f"ecrit : bareme_stats_familles.json ({len(familles)} lignes)")

        cible = (pathlib.Path("bareme_stats_neutre_events.json")
                 if "--neutre" in sys.argv else EVENTS)
        cible.write_text(json.dumps({"bareme": "stats avancees 2025/26",
                                      "evenements": flux}, ensure_ascii=False),
                          encoding="utf-8")
        print(f"\necrit : {cible} ({len(flux)} lignes datees)")

    if "--xlsx" in sys.argv:
        nom = ("bareme_stats_neutre.xlsx" if "--neutre" in sys.argv
               else "bareme_stats.xlsx")
        print("ecrit :", exporter_xlsx(joueurs, coefs, nom))


if __name__ == "__main__":
    main()

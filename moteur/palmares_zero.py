# -*- coding: utf-8 -*-
"""
PALMARES ZERO — bareme collectif reconstruit de zero, sans rien reprendre
des versions precedentes (ni table V, ni R continu, ni fractions, ni piliers).

Principe fondateur : UN PALMARES SE COMPTE EN TROPHEES, PAS EN POINTS DE
PRESENCE. On ne verse des points que pour ce dont une carriere se souvient :
un titre, une finale, une derniere carre, une recompense. Tout le reste
(classements intermediaires, tours de coupe, malus) n'existe pas.

Trois registres, additionnes, rien d'autre :

  1. TROPHEES   valeur du titre x part du joueur.
                Finaliste = 35 % du titre. Demi-finaliste = 12 %. En dessous : 0.
                Championnat : titre / dauphin 35 % / 3e 12 %.
  2. PART       lineaire, pas de racine : part des minutes jouees.
                Pour les competitions a phase finale : 60 % phase finale
                + 40 % competition entiere (les matchs decisifs pesent plus).
                Sous 10 % de part : rien (les figurants sortent).
  3. RECONNAISSANCE  registre individuel independant du resultat d'equipe :
                MVP, equipe-type, MVP de finale, hommes du match,
                meilleurs buteur et passeur. Deux niveaux seulement :
                competitions majeures / secondaires.

Pas de coefficient de poste, pas de merite, pas de piliers, pas de malus.
"""
import json, pathlib, re, sqlite3, sys, unicodedata, argparse
from collections import defaultdict

DB = pathlib.Path("fotmob.db")
MANUEL = pathlib.Path("bareme_manuel.json")

# ------------------------------------------ poids des competitions (derive)
# Une seule hierarchie pour tout le palmares, calculee depuis le BAREME STATS :
#
#     POIDS(c) = coef_stats(c) x racine(nombre de matchs) , base LDC = 100
#
# Le coefficient dit la difficulte D'UN MATCH, la racine du nombre de matchs
# dit la duree de l'epreuve sans laisser un championnat de 38 journees ecraser
# une Ligue des champions. Aucune valeur n'est posee a la main : changer un
# coefficient dans le bareme stats deplace automatiquement tout le palmares.
LONGUEUR = {
    "Champions League": 13, "World Cup": 7, "Euro": 7, "Copa America": 6,
    "Africa Cup of Nations": 6, "Europa League": 13,
    # Mondial des clubs : deux matchs secs jusqu'en 2023, sept matchs en poules
    # a partir de 2025. Le meme libelle recouvre deux epreuves sans rapport, on
    # ne peut donc pas lui donner une longueur unique. Voir MONDIAL_CLUBS.
    "Conference League": 13, "UEFA Nations League A": 6,
    "UEFA Nations League": 6,
    "Premier League": 38, "LaLiga": 38, "Serie A": 38, "Bundesliga": 34,
    "Ligue 1": 34, "Eredivisie": 34, "Liga Portugal": 34, "Super Lig": 38,
    "Jupiler Pro League": 34,
    "FA Cup": 6, "Copa del Rey": 6, "Coppa Italia": 5, "DFB Pokal": 6,
    "Coupe de France": 6, "EFL Cup": 5, "Taca de Portugal": 5,
    "UEFA Super Cup": 1, "Supercopa de Espana": 2, "Supercoppa": 2,
    "Supercoppa Italiana": 2, "Trophee des champions": 1,
    "Community Shield": 1, "DFL Supercup": 1,
}
LONGUEUR["Club World Cup"] = 7   # format long (2025+)
LONGUEUR["FIFA Club World Cup"] = 7
LONGUEUR_DEFAUT = 6
# Tournois courts de clubs : leur format bref est structurel, comme celui des
# selections. On ne les corrige donc pas sur la duree.
TOURNOIS_COURTS = {"Club World Cup", "FIFA Club World Cup"}
SELECTIONS = {"World Cup", "Euro", "EURO", "Copa America",
              "UEFA Nations League A", "UEFA Nations League",
              "Africa Cup of Nations", "Asian Cup", "CONCACAF Gold Cup"}
try:
    import bareme_stats as _bs
    coef_comp = _bs.coef_competition
except Exception:
    coef_comp = lambda c: 0.4
# La duree corrige le coefficient sans jamais inverser son ordre : avec un
# exposant 1/4, une Coupe du monde (coef 2,6) reste au-dessus d'une Ligue des
# champions (2,0), comme le dit le bareme stats, tout en restant sensible au
# nombre de matchs.
EXP_DUREE = 0.25
REF_POIDS = 2.0 * (13 ** EXP_DUREE)      # Champions League = 100


def POIDS(comp):
    """Poids d'une competition.

    La duree corrige les competitions de CLUBS, dont le calendrier est un
    choix : 34 journees et 7 matchs ne certifient pas la meme chose. Elle est
    neutralisee pour les tournois de SELECTION, dont le format court est
    structurel et non un signe de moindre valeur — la Coupe du monde reste
    donc au-dessus de la Ligue des champions, comme le dit son coefficient.
    """
    if comp in SELECTIONS or comp in TOURNOIS_COURTS:
        duree = 13 ** EXP_DUREE          # meme reference que la LDC
    else:
        duree = LONGUEUR.get(comp, LONGUEUR_DEFAUT) ** EXP_DUREE
    return coef_comp(comp) * duree / REF_POIDS * 100.0


# Plus aucun pourcentage arbitraire sur le resultat : la valeur d'un parcours
# est ce qu'il apprend, mesure en tours. Chaque tour a elimination directe
# divise le plateau par deux, donc R = tours gagnes / tours du tableau
# (finale 0,75 d'un titre a 4 tours, demie 0,50, quart 0,25). Pour un
# championnat, meme logique en rangs : R = log2(N / rang) / log2(N).
SEUIL_PART = 0.10
PART_TERRAIN = 0.60
# Revendication sur un trophee : la presence ne suffit pas, le niveau compte.
# claim = CLAIM_MIN + (1 - CLAIM_MIN) x rang percentile du joueur A SON POSTE
# selon le score par 90 du bareme stats (deja calibre par poste). Un gardien
# d'exception se compare aux gardiens, un defenseur aux defenseurs.
CLAIM_MIN = 0.25
PLAFOND_IMPACT = 2.0
MIN_CLAIM_COMP = 270    # minutes minimales pour etre classe dans une competition

# Rendements decroissants sur le CUMUL de trophees : un palmares n'est pas
# une addition. Les lignes trophees d'un joueur sont triees par valeur
# decroissante, la 1re compte plein, les suivantes a DEGRESSIF^rang.
DEGRESSIF = [1.0]

# Rendements decroissants sur le CUMUL de distinctions, meme logique que sur
# les trophees : la 2e equipe-type de la saison n'ajoute pas autant que la 1re.
DEGRESSIF_RECO = [1.0]

# Les distinctions ne sont plus des pourcentages choisis : leur valeur se
# DEDUIT de leur rarete. Un titre est partage par un effectif (S joueurs sur
# les P joueurs de la competition), une distinction par R recipiendaires.
# Mesuree en bits, la rarete d'une distinction vaut log2(P/R), celle d'un
# titre log2(P/S) — d'ou
#
#     fraction = log2(P / R) / log2(P / S)
#
# Un MVP (1 elu parmi ~400) sort donc PLUS CHER qu'un titre partage a 25.
# P et S sont comptes dans la base, R est le nombre d'elus de la distinction.
RECIPIENDAIRES = {"mvp": 1, "buteur": 1, "passeur": 1, "equipe_type": 11,
                  "mvp_finale": 1, "hdm_finale": 1, "hdm": 1}

# Buteur et passeur : leur valeur ne passe plus par le bareme individuel
# (familles, points par action). Elle se lit directement en fraction du MVP de
# la meme competition — un titre de buteur classe sur une seule dimension du
# jeu, mais reste un titre majeur, dispute a toute la competition.
# Buteur et passeur, deux facteurs mesures, aucun choisi :
#  1. pretendants effectifs — exp(entropie) de la distribution des buts /
#     passes d'une competition (190 a 235 joueurs) rapporte a celle du jeu
#     complet (~1010) : un titre de volume se dispute sur un terrain quatre a
#     cinq fois plus etroit qu'un MVP -> 0,76.
#  2. centralite de l'evenement — une passe decisive n'existe que si le but
#     est assiste : P(passe | but) = 0,71 mesure sur les deux saisons.
# D'ou buteur 0,76 x MVP et passeur 0,76 x 0,71 = 0,54 x MVP.
# Titres de volume : ils ne valent plus une fraction du MVP mais une fraction
# du POIDS de leur competition — dominer une statistique est une lecture
# partielle de la competition, dont gagner le trophee reste l'objet.
# Le passeur suit le buteur au rapport mesure P(passe | but) = 0,71.
# S'y ajoute un facteur de duree plafonne a 1 : dix buts en sept matchs de
# Coupe du monde certifient moins qu'un Soulier d'or sur treize matchs de
# Ligue des champions.
# Plafond : aucune distinction ne peut valoir plus que le trophee de sa
# competition. Les rapports entre distinctions restent ceux de la rarete
# mesuree, mais l'echelle entiere est ramenee sous 1 x POIDS.
PLAFOND_RECO = 0.75
VOLUME_POIDS = {"buteur": PLAFOND_RECO * 0.76,
                "passeur": PLAFOND_RECO * 0.76 * 0.71}

# Les recompenses d'un seul match ne couvrent qu'un match sur la competition.
UN_MATCH = {"mvp_finale", "hdm_finale", "hdm"}

# Matrice des sections du classement final (somme = 100), pensee comme la
# matrice de postes du bareme stats : le terrain pese la moitie, ce que
# l'equipe gagne et ce que le jury reconnait pesent pareil, les coups d'eclat
# d'un match comptent sans decider.
MATRICE_SECTIONS = {"stats": 50, "trophees": 20, "distinctions": 20, "hdm": 10}

CHAMPIONNATS = {47, 87, 55, 54, 53, 57, 61, 71}
VAINQUEURS_TAB = {42: 9847,
                  138: 8560,
                  207: 9847,
                  9806: 8361}   # finales aux t.a.b.   # finales aux t.a.b. :
# le score en base est nul, sans cette table personne ne recoit le titre            # Ligue des nations 2025 : Portugal aux t.a.b.

def norm(t):
    n = unicodedata.normalize("NFKD", str(t).lower())
    return "".join(c for c in n if not unicodedata.combining(c)).strip()

# Poids d'un tour dans la revendication : avoir joue la finale ne vaut pas
# avoir joue un seizieme. Les minutes de phase finale sont ponderees par le
# tour, cote joueur comme cote equipe.
POIDS_TOUR = {"finale": 1.00, "3e": 0.50, "demi": 0.60, "quart": 0.35,
              "huitieme": 0.20, "seizieme": 0.12, "barrage": 0.12}


def tour(v):
    """Etiquette fine du tour, pour la ponderation des minutes."""
    if v is None:
        return None
    v = str(v).strip().lower()
    if not v or re.fullmatch(r"\d+", v):
        return None
    if "semi" in v or "1/2" in v: return "demi"
    if any(x in v for x in ("3rd", "third", "bronze")): return "3e"
    if "quarter" in v or "1/4" in v: return "quart"
    if "1/8" in v or "round of 16" in v: return "huitieme"
    if "1/16" in v or "round of 32" in v: return "seizieme"
    if "play" in v: return "barrage"
    if "final" in v: return "finale"
    return None


def phase(v):
    if v is None: return "reg"
    v = str(v).strip().lower()
    if not v or re.fullmatch(r"\d+", v): return "reg"
    if "semi" in v or "1/2" in v: return "demi"
    if any(t in v for t in ("3rd", "third", "bronze")): return "demi"
    if "final" in v and "1/" not in v and "quarter" not in v: return "finale"
    if "quarter" in v or "1/4" in v: return "ko"
    if "1/8" in v or "round of 16" in v or "1/16" in v or "round of 32" in v: return "ko"
    if "play" in v: return "ko"
    if "group" in v or "grp" in v: return "reg"
    return "reg"

def calculer(conn):
    tours_m = {}
    matchs, poids_m = {}, {}
    for mid, date, parent, rnd, comp in conn.execute(
            "SELECT match_id, date_utc, parent_league_id, round, competition FROM v_match"):
        matchs[mid] = (date[:10], parent, phase(rnd), comp)
        poids_m[mid] = POIDS_TOUR.get(tour(rnd), 0.0)
        tours_m[mid] = tour(rnd)

    # ---------- force des equipes : coefficient UEFA de son association
    # (cumul 5 ans 2020/21-2024/25, Angleterre = 1). Mesure exterieure au
    # bareme, donc non circulaire, contrairement a une force deduite des
    # scores des joueurs.
    UEFA = {"Premier League": 1.000, "Serie A": 0.844, "LaLiga": 0.820,
            "Bundesliga": 0.749, "Ligue 1": 0.634, "Eredivisie": 0.583,
            "Liga Portugal": 0.540, "Jupiler Pro League": 0.493,
            "Super Lig": 0.381}
    UEFA_HORS = 0.15          # club hors des championnats couverts
    _lig = {}
    for _c, _h, _a in conn.execute(
            "SELECT competition, home_team_id, away_team_id FROM v_match"):
        if _c in UEFA:
            _lig[_h] = _c; _lig[_a] = _c

    def force(tid):
        return UEFA.get(_lig.get(tid), UEFA_HORS)

    # ---------- (ancienne force par effectif, conservee pour memoire)
    import statistics as _st

    ORDRE_TOUR = {"barrage": 1, "seizieme": 1, "huitieme": 2, "quart": 3,
                  "demi": 4, "3e": 4, "finale": 5}
    tour_de = lambda mid: tours_m.get(mid)

    # ---------- resultats d'equipe : titres, finalistes, demi-finalistes
    resultat = {}                     # (comp, tid) -> (fraction, libelle, date)
    finales, demis = {}, defaultdict(set)
    for mid, h, a, hs, aws in conn.execute(
            "SELECT match_id, home_team_id, away_team_id, home_score, away_score FROM v_match"):
        date, parent, ph, comp = matchs[mid]
        if parent in CHAMPIONNATS: continue
        if ph == "finale":
            prev = finales.get(comp)
            if prev is None or date > prev[0]:
                finales[comp] = (date, h, a, hs, aws, parent)
        elif ph == "demi":
            demis[comp] |= {h, a}
    # facteur de plateau : force moyenne des equipes affrontees dans la
    # competition, rapportee a celle de la Ligue des champions. Les tournois
    # de selection sont neutralises (les nations n'ont pas de force calculable).
    _opp = defaultdict(list)
    for _mid, (_d, _par, _ph, _c) in matchs.items():
        _r = conn.execute("SELECT home_team_id, away_team_id FROM v_match "
                          "WHERE match_id = ?", (_mid,)).fetchone()
        if _r:
            _opp[_c].extend([force(_r[0]), force(_r[1])])
    _f = {c: _st.mean(v) for c, v in _opp.items() if len(v) > 10}
    _base = _f.get("Champions League", 1.0) or 1.0
    PLATEAU = {c: (1.0 if c in SELECTIONS else v / _base) for c, v in _f.items()}

    # profondeur du tableau par competition (nombre de tours a elimination)
    profondeur = defaultdict(int)
    for mid, (date, parent, ph, comp) in matchs.items():
        if parent in CHAMPIONNATS: continue
        o = ORDRE_TOUR.get(tour_de(mid), 0)
        if o > profondeur[comp]: profondeur[comp] = o

    # tours a elimination directe reellement gagnes, avec la force du battu
    victoires = defaultdict(list)
    for _mid, _h, _a, _hs, _as in conn.execute(
            "SELECT match_id, home_team_id, away_team_id, home_score, away_score "
            "FROM v_match"):
        if _mid not in matchs: continue
        _d, _par, _ph, _c = matchs[_mid]
        if _par in CHAMPIONNATS or tours_m.get(_mid) is None: continue
        if _hs is None or _as is None or _hs == _as: continue
        gagnant, perdant = (_h, _a) if _hs > _as else (_a, _h)
        victoires[(_c, gagnant)].append(force(perdant))

    for comp, (date, h, a, hs, aws, parent) in finales.items():
        if hs is not None and aws is not None and hs != aws:
            g = h if hs > aws else a
        else:
            g = VAINQUEURS_TAB.get(parent)
        P = max(profondeur[comp], 1)
        moy = _f.get(comp, 1.0) or 1.0
        for t in (h, a):
            if t is None: continue
            gagnes = victoires.get((comp, t), [])
            if t == g:
                frac, lib = sum(gagnes) / (P * moy) if gagnes else 1.0, "vainqueur"
            else:
                frac = sum(gagnes) / (P * moy) if gagnes else (P - 1) / P
                lib = "finaliste"
            resultat[(comp, t)] = (frac, lib, date)
        for t in demis.get(comp, ()):
            if (comp, t) not in resultat:
                gagnes = victoires.get((comp, t), [])
                resultat[(comp, t)] = (sum(gagnes) / (P * moy) if gagnes
                                       else (P - 2) / P, "demi-finaliste", date)

    # ---------- championnats : titre / dauphin / 3e
    pts = defaultdict(lambda: defaultdict(float)); diff = defaultdict(lambda: defaultdict(int))
    fin = defaultdict(str)
    for mid, h, a, hs, aws in conn.execute(
            "SELECT match_id, home_team_id, away_team_id, home_score, away_score FROM v_match"):
        date, parent, ph, comp = matchs[mid]
        if parent not in CHAMPIONNATS or ph != "reg" or hs is None or aws is None: continue
        if hs > aws: pts[comp][h] += 3
        elif aws > hs: pts[comp][a] += 3
        else: pts[comp][h] += 1; pts[comp][a] += 1
        diff[comp][h] += hs - aws; diff[comp][a] += aws - hs
        fin[comp] = max(fin[comp], date)
    import math
    for comp, table in pts.items():
        cl = sorted(table, key=lambda t: (-table[t], -diff[comp][t]))
        N = len(cl)
        if N < 4: continue
        for rg, tid in enumerate(cl, 1):
            frac = math.log2(N / rg) / math.log2(N)
            if frac <= 0: continue
            lib = "champion" if rg == 1 else f"{rg}e de championnat"
            resultat[(comp, tid)] = (frac, lib, fin[comp])

    # ---------- part du joueur : minutes lineaires, phase finale ponderee
    m_eq, m_eq_ko = defaultdict(set), defaultdict(set)
    poids_eq_ko = defaultdict(float)      # somme des poids de tour de l'equipe
    for tid, mid in conn.execute(
            "SELECT DISTINCT a.team_id, a.match_id FROM appearance a"):
        if mid not in matchs: continue
        date, parent, ph, comp = matchs[mid]
        m_eq[(tid, comp)].add(mid)
        if ph != "reg":
            m_eq_ko[(tid, comp)].add(mid)
            poids_eq_ko[(tid, comp)] += poids_m.get(mid, 0.0)
    mn, mn_ko, equipe = defaultdict(float), defaultdict(float), {}
    nj, nj_ko = defaultdict(int), defaultdict(int)   # matchs joues
    for pid, tid, mid, v in conn.execute(
            "SELECT s.player_id, a.team_id, s.match_id, s.value FROM stat s "
            "JOIN appearance a ON a.match_id=s.match_id AND a.player_id=s.player_id "
            "WHERE s.stat_key='minutes_played' AND s.value>0"):
        if mid not in matchs: continue
        date, parent, ph, comp = matchs[mid]
        mn[(pid, comp)] += v
        nj[(pid, comp)] += 1
        if ph != "reg":
            w = poids_m.get(mid, 0.0)
            mn_ko[(pid, comp)] += v * w      # minutes ponderees par le tour
            nj_ko[(pid, comp)] += w          # "matchs" ponderes par le tour
        equipe[(pid, comp)] = tid
    def _part(minutes, joues, matchs_equipe):
        """Presence x role.

        - disponibilite = matchs joues / matchs de l'equipe, prise en RACINE :
          rater des matchs (blessure, suspension) est paye une fois, pas deux.
        - role = minutes moyennes quand il joue / 90, LINEAIRE : sortir du banc
          ne se rattrape pas. Un remplacant reste un remplacant, meme present
          a chaque feuille de match.
        """
        if not matchs_equipe or not joues:
            return 0.0
        dispo = min(1.0, joues / matchs_equipe) ** 0.5
        role = min(1.0, minutes / (joues * 90.0))
        return dispo * role

    def part(pid, comp, tid):
        p_all = _part(mn.get((pid, comp), 0), nj.get((pid, comp), 0),
                      len(m_eq.get((tid, comp), ())))
        w_ko = poids_eq_ko.get((tid, comp), 0.0)
        if w_ko:
            p_ko = _part(mn_ko.get((pid, comp), 0), nj_ko.get((pid, comp), 0), w_ko)
            return 0.6 * p_ko + 0.4 * p_all
        return p_all

    # revendication : rang percentile du joueur a son poste, COMPETITION PAR
    # COMPETITION. Un joueur peut etre excellent en Ligue des champions et
    # moyen en championnat : sa revendication sur chaque trophee le reflete.
    # Le flux de points par date du bareme stats est reventile par competition
    # (evenements[date] / minutes_par_date[date]), puis classe au poste parmi
    # les joueurs ayant assez de minutes dans cette competition.
    part_famille = {}
    rang, rang_comp = {}, {}
    try:
        import bareme_stats as bs
        _p = bs.reponderer(bs.charger(conn, 2300, 900))
        _p = bs.appliquer(_p, bs.calibrer(_p), conn)
        _fam = defaultdict(float)
        for d in _p.values():
            for f, v in d.get("familles", {}).items():
                _fam[f] += abs(v)
        _s = sum(_fam.values()) or 1.0
        part_famille = {f: v / _s for f, v in _fam.items()}
        date_comp = {}
        for mid, (date, parent, ph, comp) in matchs.items():
            date_comp.setdefault(date, comp)
        # score et minutes par (joueur, competition)
        pts_c, min_c = defaultdict(float), defaultdict(float)
        for pid, d in _p.items():
            for jour, v in d.get("evenements", {}).items():
                c = date_comp.get(str(jour)[:10])
                if c: pts_c[(pid, c)] += v
            for jour, v in d.get("minutes_par_date", {}).items():
                c = date_comp.get(str(jour)[:10])
                if c: min_c[(pid, c)] += v
        par_poste = defaultdict(list)
        for pid, d in _p.items():
            par_poste[d["poste"]].append((d["par90"], pid))
        for poste, lst in par_poste.items():
            lst.sort()
            n_l = len(lst)
            for i, (_, pid) in enumerate(lst):
                rang[pid] = i / (n_l - 1) if n_l > 1 else 1.0
        groupes = defaultdict(list)
        for (pid, c), mn_ in min_c.items():
            if mn_ >= MIN_CLAIM_COMP and pid in _p:
                groupes[(_p[pid]["poste"], c)].append((pts_c[(pid, c)] / mn_ * 90, pid))
        for (poste, c), lst in groupes.items():
            if len(lst) < 8:          # effectif trop mince : on garde la saison
                continue
            lst.sort()
            n_l = len(lst)
            for i, (_, pid) in enumerate(lst):
                rang_comp[(pid, c)] = i / (n_l - 1)
    except Exception as exc:
        print("claim : bareme stats indisponible", exc)

    def claim(pid, comp):
        r = rang_comp.get((pid, comp))
        if r is None:
            r = rang.get(pid, 0.5)
        return CLAIM_MIN + (1 - CLAIM_MIN) * r

    # P : joueurs ayant joue la competition ; S : taille mediane d'un effectif
    effectif_comp, taille_effectif = {}, {}
    _joueurs, _clubs = defaultdict(set), defaultdict(lambda: defaultdict(set))
    for pid, tid, mid in conn.execute(
            "SELECT a.player_id, a.team_id, a.match_id FROM appearance a"):
        if mid not in matchs: continue
        comp = matchs[mid][3]
        _joueurs[comp].add(pid)
        _clubs[comp][tid].add(pid)
    for comp, s in _joueurs.items():
        effectif_comp[comp] = len(s)
        tailles = sorted(len(v) for v in _clubs[comp].values())
        if tailles:
            taille_effectif[comp] = tailles[len(tailles) // 2]

    # Niveau de remplacement DANS l'effectif : 25e centile des claims des
    # joueurs du club dans cette competition. Gagner un titre dans une equipe
    # ou tout le monde est excellent ne suffit pas — il faut la depasser.
    # C'est la transposition exacte de NORME_QUANTILE du bareme stats.
    _par_club = defaultdict(list)
    for (pid_, comp_), tid_ in equipe.items():
        if mn.get((pid_, comp_), 0) >= 270:
            _par_club[(tid_, comp_)].append(claim(pid_, comp_))
    norme_effectif = {}
    for cle_, lst in _par_club.items():
        if len(lst) >= 8:
            lst.sort()
            i_ = 0.25 * (len(lst) - 1); lo_ = int(i_)
            norme_effectif[cle_] = lst[lo_] + (lst[min(lo_+1, len(lst)-1)] - lst[lo_]) * (i_ - lo_)

    # impact = par90 du joueur / par90 moyen des titulaires de son equipe
    impact = {}
    try:
        # L'impact compare un joueur au titulaire moyen de son club. Pour un
        # gardien, dont le poste est decale vers le haut, cette comparaison a
        # des joueurs de champ le survalorise : il est donc compare aux
        # gardiens du panel, sur sa propre echelle.
        _gk = [d2["par90"] for d2 in _p.values()
               if d2.get("poste") == "Gardien" and d2["minutes"] >= 900]
        _moy_gk = (sum(_gk) / len(_gk)) if _gk else 1.0
        _eq = defaultdict(list)
        for _pid2, _d2 in _p.items():
            if _d2.get("team_id") and _d2["minutes"] >= 900 \
                    and _d2.get("poste") != "Gardien":
                _eq[_d2["team_id"]].append(_d2["par90"])
        for _pid2, _d2 in _p.items():
            _t2 = _d2.get("team_id")
            lst = _eq.get(_t2)
            if lst:
                moy = sum(lst) / len(lst)
                if moy > 0:
                    impact[(_pid2, _t2)] = (
                        _d2["par90"] / _moy_gk if _d2.get("poste") == "Gardien"
                        else _d2["par90"] / moy)
    except Exception:
        pass

    ALIAS = {"ldc": "Champions League", "cdm": "World Cup", "coupe du monde": "World Cup",
             "mondial des clubs": "Club World Cup", "mondial": "World Cup",
             "uel": "Europa League", "europa league": "Europa League",
             "uecl": "Conference League", "conference": "Conference League",
             "ligue des nations": "UEFA Nations League A", "la liga": "LaLiga",
             "laliga": "LaLiga", "ligue 1": "Ligue 1", "premier league": "Premier League",
             "bundesliga": "Bundesliga", "serie a": "Serie A",
             "can": "Africa Cup of Nations",
             "coupe d'afrique": "Africa Cup of Nations",
             "euro": "EURO", "championnat d'europe": "EURO",
             "copa america": "Copa America",
             "coupe d'asie": "Asian Cup", "asian cup": "Asian Cup",
             "gold cup": "CONCACAF Gold Cup"}
    def comp_of(lib):
        n = norm(lib)
        for a, c in sorted(ALIAS.items(), key=lambda kv: -len(kv[0])):
            if a in n: return c
        return None

    # Plancher de participation accorde par le jury : si un joueur est elu
    # meilleur de la competition ou place dans l'equipe-type, le jury a juge
    # sur ce qui a ete joue — sa revendication sur le trophee ne peut pas
    # retomber au prorata de ses minutes (cas Dembele, MVP de Ligue 1 avec
    # 43 % de participation, dont le titre de champion ne valait que 34 pts).
    PLANCHER_JURY = {"mvp": 1.0, "equipe_type": 1.0}
    jury = defaultdict(float)
    if MANUEL.exists():
        _idx = {}
        for _pid, _nom in conn.execute("SELECT player_id, name FROM player"):
            _idx.setdefault(norm(_nom), _pid)
        for _e in json.loads(MANUEL.read_text(encoding="utf-8")).get("evenements", []):
            _l = norm(_e.get("libelle", ""))
            _pid = _idx.get(norm(_e.get("joueur", "")))
            _c = comp_of(_e.get("libelle", ""))
            if _pid is None or _c is None:
                continue
            if _l.startswith(("mvp", "meilleur joueur")) and "finale" not in _l:
                jury[(_pid, _c)] = max(jury[(_pid, _c)], PLANCHER_JURY["mvp"])
            elif "equipe-type" in _l or "equipe type" in _l:
                jury[(_pid, _c)] = max(jury[(_pid, _c)], PLANCHER_JURY["equipe_type"])

    # Joueurs figurant dans une equipe-type, par competition : sert de
    # plancher a l'impact plus bas.
    EQUIPES_TYPES = set()
    if MANUEL.exists():
        _idx_nom = {}
        for _p5, _n5 in conn.execute("SELECT player_id, name FROM player"):
            _idx_nom.setdefault(norm(_n5), _p5)
        for _e5 in json.loads(MANUEL.read_text(encoding="utf-8")).get("evenements", []):
            _l5 = norm(_e5.get("libelle", ""))
            if _l5.startswith("equipe-type"):
                _p6 = _idx_nom.get(norm(_e5.get("joueur", "")))
                _c6 = comp_of(_e5.get("libelle", ""))
                if _p6 and _c6:
                    EQUIPES_TYPES.add((_p6, _c6))

    noms = dict(conn.execute("SELECT player_id, name FROM player"))
    total = defaultdict(float); detail = defaultdict(list)
    brut_trophees = defaultdict(list); rec_tot = defaultdict(float)
    rec_brut = defaultdict(list)
    for (pid, comp), _ in mn.items():
        tid = equipe[(pid, comp)]
        r = resultat.get((comp, tid))
        if not r: continue
        frac, lib, date = r
        val = POIDS(comp) * PLATEAU.get(comp, 0.7)
        if val <= 0: continue
        p = part(pid, comp, tid)
        p = max(p, jury.get((pid, comp), 0.0))
        if p < SEUIL_PART: continue
        c = claim(pid, comp)
        # Niveau de remplacement STRUCTUREL et non propre au club : le claim
        # etant deja un rang percentile dans son poste, son 25e centile vaut
        # 0,25 par construction. Se comparer a ses coequipiers penalisait les
        # joueurs des effectifs denses — exactement ce qu'on ne veut pas.
        base = CLAIM_MIN
        # Plancher : un joueur qui a dispute et gagne la competition l'a
        # gagnee. Passer sous le niveau de remplacement de son effectif reduit
        # sa revendication, mais ne l'efface pas — sans quoi un claim a 0,66
        # contre une norme a 0,67 supprimait tout le trophee (cas Donnarumma
        # et Marquinhos en C1 2024/25). On reprend le plancher deja en vigueur
        # sur le claim lui-meme, aucun nouveau chiffre.
        c = max(CLAIM_MIN, (c - base) / (1 - base) if base < 1 else 0.0)
        # IMPACT : ce que vaut le joueur QUAND il joue, rapporte au titulaire
        # moyen de son equipe. Un artisan majeur revendique le titre au-dela de
        # son temps de jeu ; un figurant reste sous 1.
        # Plancher pour les joueurs de l'EQUIPE-TYPE de la competition : un
        # jury les a designes parmi les onze meilleurs du tournoi, ils ne
        # peuvent pas revendiquer le titre comme des figurants. Sans ce
        # plancher, Marquinhos — equipe-type de C1, 1320 minutes jouees —
        # touchait 23,6 points pour la Ligue des champions quand Dembele en
        # touchait 320 avec 827 minutes.
        _imp = min(PLAFOND_IMPACT, impact.get((pid, tid), 1.0))
        if (pid, comp) in EQUIPES_TYPES:
            _imp = max(_imp, 1.0)
        c *= _imp
        # Participation reelle : un titre se revendique a hauteur de ce qu'on y
        # a joue. part = disponibilite^0,5 x role — rater des matchs est paye
        # une fois, sortir du banc ne se rattrape pas.
        gain = val * frac * c * p
        brut_trophees[pid].append((gain, f"{comp} {lib}",
                                   f"part {p:.2f} x claim {c:.2f}", comp))

    # ---------- degressif sur le cumul de trophees
    # L'amortissement s'applique COMPETITION PAR COMPETITION : deux lignes
    # portant sur les memes matchs sont redondantes, deux lignes portant sur
    # deux competitions differentes ne le sont pas.
    tro = defaultdict(float)
    for pid, lignes in brut_trophees.items():
        par_comp = defaultdict(list)
        for l in lignes:
            par_comp[l[3]].append(l)
        for comp_, lst in par_comp.items():
            for i, (gain, lib, extra, _c) in enumerate(sorted(lst, reverse=True)):
                coef = DEGRESSIF[i] if i < len(DEGRESSIF) else DEGRESSIF[-1]
                g = gain * coef
                tro[pid] += g
                detail[pid].append((round(g, 1), lib, f"{extra} x deg {coef}"))

    # ---------- reconnaissance
    idx = {}
    for pid, nom in noms.items(): idx.setdefault(norm(nom), pid)
    def comp_of(lib):
        n = norm(lib)
        for a, c in sorted(ALIAS.items(), key=lambda kv: -len(kv[0])):
            if a in n: return c
        return None
    import math

    def reco(cle, comp):
        if cle in VOLUME_POIDS:
            duree = (1.0 if comp in SELECTIONS else
                     min(1.0, (LONGUEUR.get(comp, LONGUEUR_DEFAUT) / 13.0) ** 0.25))
            return POIDS(comp) * PLATEAU.get(comp, 0.7) * VOLUME_POIDS[cle] * duree
        portee = 1.0
        P = max(effectif_comp.get(comp, 300), 30)      # joueurs de la competition
        S = max(taille_effectif.get(comp, 25), 11)     # effectif d'un club
        base = math.log2(P / max(S, 2))
        if base <= 0:
            base = 1.0
        frac = math.log2(P / RECIPIENDAIRES[cle]) / base
        # normalisation : le MVP, distinction la plus rare, plafonne a
        # PLAFOND_RECO x POIDS ; les autres suivent au meme rapport de rarete.
        frac /= (math.log2(P / RECIPIENDAIRES["mvp"]) / base) or 1.0
        frac *= PLAFOND_RECO
        if cle in UN_MATCH:                            # portee : un seul match
            frac /= max(LONGUEUR.get(comp, LONGUEUR_DEFAUT), 1)
        return POIDS(comp) * PLATEAU.get(comp, 0.7) * frac * portee
    if MANUEL.exists():
        for e in json.loads(MANUEL.read_text(encoding="utf-8")).get("evenements", []):
            lib = e.get("libelle", ""); n = norm(lib)
            pid = idx.get(norm(e.get("joueur", ""))); comp = comp_of(lib)
            if pid is None or comp is None: continue
            if n.startswith(("mvp de la finale", "meilleur joueur de la finale")): cle = "mvp_finale"
            elif n.startswith(("mvp", "meilleur joueur")): cle = "mvp"
            elif "equipe-type" in n or "equipe type" in n: cle = "equipe_type"
            elif n.startswith("homme du match"):
                cle = "hdm_finale" if "finale" in n and "demi" not in n else "hdm"
            elif n.startswith("meilleur buteur"): cle = "buteur"
            elif n.startswith("meilleur passeur"): cle = "passeur"
            else: continue
            _t3 = equipe.get((pid, comp))
            # BOOST : si l'equipe a GAGNE la competition, ses distinctions dans
            # CETTE competition sont remultipliees par le coefficient de la
            # competition. Gagner la C1 et etre dans son 11 type ne vaut pas
            # etre dans le 11 type d'une C1 perdue.
            _r3 = resultat.get((comp, _t3))
            _gagne3 = _r3 is not None and _r3[1] in ("vainqueur", "champion")
            _boost = max(1.0, coef_comp(comp)) if _gagne3 else 1.0
            _i3 = min(PLAFOND_IMPACT, impact.get((pid, _t3), 1.0)) if _t3 else 1.0
            # Recompense de terrain (volume accumule) : le temps de jeu compte.
            # Distinction d'election (MVP, equipe-type, homme du match) : le
            # jury a deja juge sur ce qui a ete joue, on ne penalise pas deux fois.
            # Le temps de jeu s'applique aux EQUIPES-TYPES (onze elus, un
            # remplacant peut y figurer sur une demi-saison) et aux titres de
            # volume, mais pas aux distinctions individuelles fortes : etre elu
            # meilleur joueur d'une competition est un jugement sur la valeur,
            # pas sur la quantite de minutes.
            _p3 = (part(pid, comp, _t3)
                   if (_t3 and (cle in VOLUME_POIDS or cle == "equipe_type"))
                   else 1.0)
            # Un homme du match se pondere par le TOUR : la phase de ligue ne
            # vaut pas une demi-finale. Les autres distinctions ne sont pas
            # concernees.
            _tour = 1.0
            if cle in ("hdm", "hdm_finale"):
                for _mot, _p in (("phase de ligue", 0.10), ("journee", 0.10),
                                 ("seizieme", 0.12), ("barrage", 0.15),
                                 ("huitieme", 0.25), ("quart", 0.45),
                                 ("demi", 0.65), ("finale", 1.00)):
                    if _mot in n:
                        _tour = _p
            rec_brut[pid].append((reco(cle, comp) * _i3 * _p3 * _boost * _tour,
                                  lib, comp))
    for parent in CHAMPIONNATS:      # buteurs/passeurs de championnat (donnees)
        row = conn.execute("SELECT competition FROM v_match WHERE parent_league_id=? LIMIT 1",
                           (parent,)).fetchone()
        if not row: continue
        comp = row[0]
        for cle, sk in (("buteur", "goals"), ("passeur", "assists")):
            l = conn.execute("SELECT s.player_id, SUM(s.value) n FROM v_stat s "
                             "JOIN match m ON m.match_id=s.match_id "
                             "WHERE m.parent_league_id=? AND m.usable=1 AND s.stat_key=? "
                             "GROUP BY s.player_id ORDER BY n DESC LIMIT 1", (parent, sk)).fetchone()
            if not l or not l[1]: continue
            _t4 = equipe.get((l[0], comp))
            _r4 = resultat.get((comp, _t4))
            _g4 = _r4 is not None and _r4[1] in ("vainqueur", "champion")
            _b4 = max(1.0, coef_comp(comp)) if _g4 else 1.0
            _i4 = min(PLAFOND_IMPACT, impact.get((l[0], _t4), 1.0)) if _t4 else 1.0
            _p4 = part(l[0], comp, _t4) if (cle in VOLUME_POIDS and _t4) else 1.0
            rec_brut[l[0]].append((reco(cle, comp) * _i4 * _p4 * _b4,
                                   f"meilleur {cle} {comp}", comp))
    # ---------- degressif sur le cumul de distinctions
    for pid, lignes in list(rec_brut.items()):
        par_comp = defaultdict(list)
        for l in lignes:
            par_comp[l[2]].append(l)
        s = 0.0
        for comp_, lst in par_comp.items():
            for i, (g, lib, _c) in enumerate(sorted(lst, reverse=True)):
                coef = (DEGRESSIF_RECO[i] if i < len(DEGRESSIF_RECO)
                        else DEGRESSIF_RECO[-1])
                s += g * coef
                detail[pid].append((round(g * coef, 1), lib, f"x deg {coef}"))
        rec_tot[pid] = s

    # ---------- addition des deux registres, aucun dosage
    for pid in set(tro) | set(rec_tot):
        total[pid] = tro.get(pid, 0.0) + rec_tot.get(pid, 0.0)
    return noms, total, detail

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hybride", action="store_true")
    ap.add_argument("--joueur"); ap.add_argument("--top", type=int, default=15)
    args = ap.parse_args()
    conn = sqlite3.connect(DB)
    noms, total, detail = calculer(conn)
    if args.joueur:
        for pid, n in noms.items():
            if args.joueur.lower() in norm(n) and pid in total:
                print(f"\n{n.upper()} — palmares {total[pid]:.1f}")
                for g, lib, extra in sorted(detail[pid], reverse=True):
                    print(f"  {g:>6.1f}  {lib}  {extra}")
        return
    if not args.hybride:
        for i, pid in enumerate(sorted(total, key=total.get, reverse=True)[:args.top], 1):
            print(f"{i:>3} {noms.get(pid,'?')[:26]:<27}{total[pid]:>7.1f}")
        return
    import bareme_stats as bs
    perf = bs.reponderer(bs.charger(conn, 2300, 900))
    perf = bs.appliquer(perf, bs.calibrer(perf), conn)
    # ---------------------------------------------------- assemblage final
    # Les deux registres sont ramenes a la meme DISPERSION (ecart-type), puis
    # ponderes : le niveau de jeu compte pour 60 %, le palmares pour 40 %.
    # Seule ponderation du bareme, posee comme principe.
    def _pct(v, q):
        v = sorted(v); i = q * (len(v) - 1); lo = int(i)
        return v[lo] + (v[min(lo + 1, len(v) - 1)] - v[lo]) * (i - lo)

    S = {pid: p["par90"] for pid, p in perf.items()}
    P = {pid: total.get(pid, 0.0) for pid in perf}
    pop = [pid for pid in perf if P[pid] > 0] or list(perf)
    vs = [S[p] for p in pop]; vp = [P[p] for p in pop]
    import statistics as _st
    ns, np_ = _pct(vs, 0.25), _pct(vp, 0.25)
    sa = _st.pstdev(vs) or 1.0
    sb = _st.pstdev(vp) or 1.0
    z_s = {pid: 200 * PART_TERRAIN * (S[pid] - ns) / sa for pid in perf}
    z_p = {pid: 200 * (1 - PART_TERRAIN) * (P[pid] - np_) / sb for pid in perf}
    lig = sorted(((z_s[pid] + z_p[pid], z_s[pid], z_p[pid], pid) for pid in perf),
                 reverse=True)
    print(f"TOTAL — {PART_TERRAIN:.0%} terrain / {1 - PART_TERRAIN:.0%} palmares\n")
    for i, (t, s, c, pid) in enumerate(lig[:args.top], 1):
        p = perf[pid]
        print(f"{i:>3} {p['nom'][:24]:<25}{str(p['club'])[:18]:<19}{t:>6.0f}{s:>6.0f}{c:>6.0f}")

if __name__ == "__main__":
    main()

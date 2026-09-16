#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""complete_physique.py — deuxieme passe sur les joueurs sans profil physique.

    python3 complete_physique.py --manquants manquants_tous_joueurs.csv \\
        --dossier kaggle --sortie physique_complement.csv

La premiere passe compare des noms entiers : elle echoue des qu'EA nomme
autrement. « Vinícius Júnior » y figure comme « Vini Jr. », de son vrai nom
« Vinícius José de Oliveira Júnior » ; « Fermín López » comme « Fermín López
Marín ». Cette passe essaie donc quatre cles successives, de la plus sure a la
plus souple, et n'accepte une correspondance floue que si le CLUB ou l'AGE
concordent.
"""
import argparse, csv, pathlib, re, unicodedata
from collections import defaultdict

CLUBS = {  # les noms de club different d'une source a l'autre
    "leverkusen": "bayer leverkusen", "bayer 04 leverkusen": "bayer leverkusen",
    "fc barcelona": "barcelona", "ssc napoli": "napoli", "inter": "internazionale",
    "inter milan": "internazionale", "paris sg": "paris saint germain",
    "psg": "paris saint germain", "man utd": "manchester united",
    "man city": "manchester city", "spurs": "tottenham hotspur",
    "atletico de madrid": "atletico madrid", "atletico madrid": "atletico madrid",
    "borussia dortmund": "dortmund", "bayern munchen": "bayern munich",
    "fc bayern munchen": "bayern munich", "fc bayern munich": "bayern munich",
}


# Lettres que la decomposition Unicode ne reduit pas : le i sans point turc,
# le d barre croate, le o barre scandinave. Sans cette table, « Uğurcan Çakır »
# et « Ugurcan Cakir » restent deux noms differents.
TRAD = str.maketrans({"ı": "i", "ğ": "g", "ş": "s", "ø": "o", "đ": "d", "ð": "d",
                      "ł": "l", "æ": "ae", "œ": "oe", "ß": "ss", "þ": "th"})


def sansacc(s):
    s = str(s or "").lower().translate(TRAD)
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if not unicodedata.combining(c))


def cle(s):
    s = sansacc(s)
    for c in "'’":
        s = s.replace(c, "")
    for c in "-.":
        s = s.replace(c, " ")
    return " ".join(p for p in s.split()
                    if p not in {"jr", "junior", "de", "da", "do", "dos", "del",
                                 "van", "von", "der", "el", "al", "bin", "the"})


VIDES_CLUB = {"fc", "cf", "ac", "as", "sc", "ss", "ssc", "afc", "bsc", "sv",
              "cd", "rc", "ud", "club", "de", "real", "athletic", "atletico",
              "deportivo", "sporting", "united", "utd", "city", "hove", "albion"}


def club_norm(s):
    c = " ".join(m for m in cle(s).split() if m not in VIDES_CLUB)
    if not c:                       # « Athletic Club » : tous les mots sont creux
        c = cle(s)
    return CLUBS.get(c, c)


def meme_equipe(a, b):
    """« Newcastle Utd » et « Newcastle United », « Celta » et « Celta Vigo »
    designent le meme club : on compare des mots, pas des chaines."""
    ma, mb = set(club_norm(a).split()), set(club_norm(b).split())
    return bool(ma & mb)


def variantes(first, last, common):
    """Toutes les facons dont un meme joueur peut etre nomme."""
    v = set()
    for n in (common, f"{first} {last}", last, first):
        if n and n.strip():
            v.add(cle(n))
    # « Vinícius José de Oliveira Júnior » -> « vinicius » et « oliveira »
    mots = cle(f"{first} {last}").split()
    if len(mots) > 1:
        v.add(f"{mots[0][:3]} {mots[-1]}")
        # double patronyme espagnol : « Jauregizar Alboniga », « Vivian Moreno »
        # sont connus par le PREMIER nom de famille
        ml = cle(last).split()
        if len(ml) > 1:
            v.add(f"{mots[0]} {ml[0]}")
            v.add(ml[0])
            v.add(f"{mots[0][:3]} {ml[0]}")
    if mots:
        v.add(mots[0])
        v.add(mots[-1])
        if len(mots) > 1:
            v.add(f"{mots[0]} {mots[-1]}")
    return {x for x in v if len(x) > 2}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manquants", required=True)
    ap.add_argument("--dossier", default="kaggle")
    ap.add_argument("--sortie", default="physique_complement.csv")
    ap.add_argument("--au", default="2026-07-01")
    args = ap.parse_args()

    ea = list(csv.DictReader((pathlib.Path(args.dossier) /
                              "ea_fc26_players.csv").open(encoding="utf-8")))
    index = defaultdict(list)
    for r in ea:
        for v in variantes(r["firstName"], r["lastName"], r["commonName"]):
            index[v].append(r)

    def naissance_ea(r):
        m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", r.get("birthdate", ""))
        return (f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
                if m else "")

    def age_ea(r):
        m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", r.get("birthdate", ""))
        if not m:
            return None
        an, mois, jour = int(m.group(3)), int(m.group(1)), int(m.group(2))
        ra, rm, rj = (int(x) for x in args.au.split("-"))
        return ra - an - ((rm, rj) < (mois, jour))

    manquants = list(csv.DictReader(pathlib.Path(args.manquants).open(encoding="utf-8-sig")))
    trouves, restent = [], []
    for m in manquants:
        nom, club, age = m["nom"], m.get("club", ""), m.get("age", "")
        # Cles essayees de la plus SURE a la plus souple, en s'arretant des
        # qu'une donne des candidats. Tout melanger faisait exploser le nombre
        # de pistes : chercher « martin » seul remonte des centaines de
        # joueurs et rendait Zubimendi introuvable.
        mots = cle(nom).split()
        essais = [cle(nom)]
        if len(mots) > 1:
            essais.append(f"{mots[0]} {mots[-1]}")
            essais.append(f"{mots[0][:3]} {mots[-1]}")
            essais.append(mots[-1])
        # « Thuram-Ulien » : un patronyme compose cote jeu, simple chez EA
        for m2 in mots[1:]:                      # jamais le prenom seul
            for bout in re.split(r"[- ]", m2):
                if len(bout) > 3 and bout not in essais:
                    essais.append(bout)
                    essais.append(f"{mots[0]} {bout}")
        uniq = []
        for v in essais:
            vus = set()
            for r in index.get(v, []):
                if r["id"] not in vus:
                    vus.add(r["id"]); uniq.append(r)
            if uniq:
                break
        if not uniq:
            restent.append(m); continue
        if len(uniq) > 1:
            par_club = [r for r in uniq if meme_equipe(r["team"], club)]
            if par_club:
                uniq = par_club
        if len(uniq) > 1 and age:
            proches = [r for r in uniq
                       if age_ea(r) is not None and abs(age_ea(r) - int(age)) <= 1]
            if proches:
                uniq = proches
        if len(uniq) > 1:
            # dernier recours : le nom complet doit correspondre exactement
            exacts = [r for r in uniq if cle(nom) in
                      variantes(r["firstName"], r["lastName"], r["commonName"])]
            if len(exacts) == 1:
                uniq = exacts
        if len(uniq) > 1:
            # Dernier filtre : la ligne du terrain. Un gardien ne peut pas
            # etre apparie a un attaquant, meme homonyme et meme club.
            def ligne_ea(r):
                p = (r.get("position") or "").upper()
                if p == "GK": return "G"
                if p in ("CB", "LB", "RB", "LWB", "RWB"): return "D"
                if p in ("CDM", "CM", "CAM", "LM", "RM"): return "M"
                return "A"
            def ligne_jeu(p):
                p = (p or "").lower()
                if "gardien" in p: return "G"
                if "defenseur" in p or "lateral" in p: return "D"
                if "milieu" in p: return "M"
                return "A"
            meme_ligne = [r for r in uniq
                          if ligne_ea(r) == ligne_jeu(m.get("poste", ""))]
            if len(meme_ligne) == 1:
                uniq = meme_ligne
        if len(uniq) > 1:
            restent.append(dict(m, _note="plusieurs candidats")); continue
        r = uniq[0]
        # garde-fou : un nom court ne suffit pas, il faut club ou age concordant
        meme_club = meme_equipe(r["team"], club)
        meme_age = age and age_ea(r) is not None and abs(age_ea(r) - int(age)) <= 1
        nom_complet = cle(nom) in variantes(r["firstName"], r["lastName"], r["commonName"])
        # le club suffit ; sinon il faut l'age ET le nom complet, car un
        # patronyme partage (« Chabot ») menerait au mauvais joueur
        if not (meme_club or (meme_age and nom_complet)):
            restent.append(dict(m, _note="nom seul, non confirme")); continue
        trouves.append({
            "_motif": ("club" if meme_club else
                       "age+nom" if (meme_age and nom_complet) else "?"),
            "fotmob_id": m.get("fotmob_id") or m.get("\ufefffotmob_id"),
            "nom_fotmob": nom, "ea_id": r["id"],
            "nom_ea": (r["commonName"] or f"{r['firstName']} {r['lastName']}").strip(),
            "equipe_ea": r["team"], "championnat": r.get("leagueName", ""),
            "naissance": naissance_ea(r), "age": age_ea(r),
            "poste": r.get("position", ""), "note": r.get("overallRating", ""),
            "taille_cm": r["height"], "poids_kg": r["weight"],
            "pied_fort": {"1": "Right", "2": "Left"}.get(r["preferredFoot"], ""),
            "mauvais_pied": r["weakFootAbility"], "gestes": r["skillMoves"],
            "acceleration": r["acceleration"], "vitesse_pointe": r["sprintSpeed"],
            "agilite": r["agility"], "equilibre": r["balance"], "reactions": r["reactions"],
            "endurance": r["stamina"], "force": r["strength"], "detente": r["jumping"],
            "agressivite": r["aggression"], "note_physique": r["phy"]})

    champs = list(trouves[0]) if trouves else []
    with pathlib.Path(args.sortie).open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=champs)
        w.writeheader()
        for r in trouves:
            w.writerow(r)
    if restent:
        with pathlib.Path("physique_toujours_absents.csv").open(
                "w", newline="", encoding="utf-8") as f:
            ch = list(manquants[0]) + ["_note"]
            w = csv.DictWriter(f, fieldnames=ch, extrasaction="ignore")
            w.writeheader()
            for r in restent:
                w.writerow(r)
    print(f"{len(manquants)} manquants en entree")
    print(f"{len(trouves)} retrouves -> {args.sortie}")
    print(f"{len(restent)} toujours absents -> physique_toujours_absents.csv")


if __name__ == "__main__":
    main()

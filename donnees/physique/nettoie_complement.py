#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""nettoie_complement.py — les corrections manuelles, rejouables.

    python3 nettoie_complement.py --db moteur/fotmob_2526.db

Applique dans l'ordre : retrait des faux positifs connus, ajouts manuels,
resolution des identifiants EA partages par club, poste et patronyme.
Tout est dans ce fichier pour etre rejoue apres chaque re-extraction.
"""
import argparse, csv, pathlib, re, sqlite3, unicodedata
from collections import defaultdict

# Deux personnes distinctes, verifie a la main.
FAUX = {("Mamadou Mbow","Moustapha Mbow"),("Miguel Nogueira","Gonçalo Nogueira"),
 ("Sidny Lopes Cabral","Jovane Cabral"),("Daniel Rivas","Leonardo Rivas"),("Rodrigo Rêgo","João Rego"),
 ("Moatasem Al Musrati","Ali Al Musrati"),("Matheus Mendes","Tomás Mendes"),("Josafat Mendes","Joe Mendes"),
 ("Collins Sor","Yira Sor"),("Edu Rodríguez","Baltasar Rodríguez"),("Guilherme Smith","Eric Smith"),
 ("Isaac Moore","Taylor Moore"),("Ismeal Kabia","Jaze Kabia"),("Jacopo Gelli","Francesco Gelli"),
 ("Jordan Davies","Will Davies"),("Kiki Oshilaja","Deji Oshilaja"),("Kyle Morrison","George Morrison"),
 ("Namory Keita","Habib Keïta"),("Nampalys Mendy","Formose Mendy"),("Nemanja Radonjic","Dejan Radonjic"),
 ("Tanto Olaofe","Isaac Olaofe"),("Kaique Pereira","Liziero"),("Tiago Silva","Charles"),
 ("Matheus Nunes","Matheus Araújo"),("João Silva","João Talocha"),("Ulisses Rocha","Ulisses Wilson"),
 ("Andrés Lopez","Alberto Flores"),("Julio Díaz","Brahim"),("Bernardo Martins","Benny"),
 ("Ramon Martinez","Alfon"),("Anderson Silva","Anderson Oliveira"),("Andres Campos","Diego García"),
 ("Azael Garcia","Andrés Martín"),("Bruno Duarte","Duarte Moreira"),("Jastin Garcia","Martí Vilà"),
 ("Andrés Martin","Andrés Martín"),("Dramane Koné","Zanga Koné"),("Morgan Roberts","Liam Roberts"),
 ("Enol Rodriguez","Guruzeta"),("Manuel Sanchez","Manu Nieto"),("Daniel Ojeda","Marco Moreno"),
 ("Antonio Fernández","Aitor"),("Fábio Pereira","Mathias Pereira Lage"),("Lucas Diaz","Diego Díaz"),
 ("Salvi Sánchez","Manu Sánchez"),("Jacob Borgnis","Jacob Brown"),("Jacob Pinnington","Jacob Brown"),
 ("Gustavo Mendonça","Gustavo"),("Gustavo Assuncao","Gustavo"),("Gerard Fernandez","Álvaro"),
 ("Fabiano Souza","Alan"),("Roberto González","Rober"),("Guilherme Neiva","Kiki")}

# Ajouts a la main : (fotmob_id, nom_fotmob, ea_id, raison)
MANUEL = [("1404415","Fermín López","277179","nom d'usage seul"),
          ("867080","Jeff Chabot","239340","Julian Jeff Chabot, meme homme"),
          ("711231","Gorka Guruzeta","231184","deux freres, le club tranche")]

TRAD = str.maketrans({"ı":"i","ğ":"g","ş":"s","ø":"o","đ":"d","ð":"d","ł":"l"})
VIDES = {"fc","cf","ac","as","sc","ss","ssc","afc","bsc","sv","cd","rc","ud","club","de","real",
         "athletic","atletico","r","sd","ca","deportivo","sporting","united","utd","city","hove","albion"}

def mots(s, vides=set()):
    s = str(s or "").lower().translate(TRAD); s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if not unicodedata.combining(c)).replace("'", "")
    return [m for m in s.replace("-", " ").replace(".", " ").split() if m not in vides]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--ea", default="kaggle/ea_fc26_players.csv")
    args = ap.parse_args()
    base = list(csv.DictReader(open("physique_joueurs.csv", encoding="utf-8")))
    champs = list(base[0])
    comp = list(csv.DictReader(open("physique_complement.csv", encoding="utf-8")))
    n0 = len(base) + len(comp)

    # 1. faux positifs
    base = [r for r in base if (r["nom_fotmob"], r["nom_ea"]) not in FAUX]
    comp = [r for r in comp if (r["nom_fotmob"], r["nom_ea"]) not in FAUX]

    # 2. ajouts manuels
    ea = {r["id"]: r for r in csv.DictReader(open(args.ea, encoding="utf-8"))}
    deja = {r["fotmob_id"] for r in base + comp}
    for fid, nom, eid, _ in MANUEL:
        if fid in deja: continue
        r = ea[eid]
        m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", r["birthdate"] or "")
        naiss = f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}" if m else ""
        age = ""
        if naiss:
            a, mo, j = (int(x) for x in naiss.split("-")); age = 2026 - a - ((7, 1) < (mo, j))
        comp.append({"fotmob_id": fid, "nom_fotmob": nom, "ea_id": eid,
            "nom_ea": (r["commonName"] or f"{r['firstName']} {r['lastName']}").strip(),
            "equipe_ea": r["team"], "championnat": r.get("leagueName", ""), "naissance": naiss,
            "age": age, "poste": r["position"], "note": r["overallRating"],
            "taille_cm": r["height"], "poids_kg": r["weight"],
            "pied_fort": {"1": "Right", "2": "Left"}.get(r["preferredFoot"], ""),
            "mauvais_pied": r["weakFootAbility"], "gestes": r["skillMoves"],
            "acceleration": r["acceleration"], "vitesse_pointe": r["sprintSpeed"],
            "agilite": r["agility"], "equilibre": r["balance"], "reactions": r["reactions"],
            "endurance": r["stamina"], "force": r["strength"], "detente": r["jumping"],
            "agressivite": r["aggression"], "note_physique": r["phy"]})

    # 3. identifiants EA partages : club, puis ligne, puis patronyme
    conn = sqlite3.connect(args.db)
    clubs, postes = defaultdict(set), {}
    for pid, eq in conn.execute("""SELECT a.player_id, a.team_name FROM appearance a
            JOIN match m ON m.match_id = a.match_id AND m.usable = 1"""):
        clubs[pid] |= set(mots(eq, VIDES))
    for pid, pos in conn.execute("""SELECT a.player_id, a.position_id FROM appearance a
            JOIN match m ON m.match_id = a.match_id AND m.usable = 1
            WHERE a.position_id IS NOT NULL"""):
        postes.setdefault(pid, []).append(pos // 10)
    def ligne_jeu(pid):
        v = postes.get(pid)
        return {1: "G", 2: "D", 3: "M", 4: "A"}.get(round(sum(v)/len(v))) if v else None
    def ligne_ea(p):
        p = (p or "").upper()
        return ("G" if p == "GK" else "D" if p in ("CB","LB","RB","LWB","RWB")
                else "M" if p in ("CDM","CM","CAM","LM","RM") else "A")
    def score(r):
        pid = int(r["fotmob_id"]); s = 0
        if set(mots(r.get("equipe_ea", ""), VIDES)) & clubs.get(pid, set()): s += 4
        if ligne_ea(r.get("poste")) == ligne_jeu(pid): s += 2
        nm = mots(r["nom_fotmob"])
        if nm and nm[-1] in mots(r["nom_ea"]): s += 1
        return s
    tous = [("b", r) for r in base] + [("c", r) for r in comp]
    par = defaultdict(list)
    for t in tous: par[t[1]["ea_id"]].append(t)
    retirer = set()
    for eid, v in par.items():
        if len(v) < 2: continue
        v.sort(key=lambda t: -score(t[1]))
        if score(v[0][1]) == score(v[1][1]):
            for t in v: retirer.add(id(t[1]))       # indecis : on ne garde personne
        else:
            for t in v[1:]: retirer.add(id(t[1]))
    base = [r for r in base if id(r) not in retirer]
    comp = [r for r in comp if id(r) not in retirer]

    for nom, lignes in (("physique_joueurs.csv", base), ("physique_complement.csv", comp)):
        with open(nom, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=champs, extrasaction="ignore")
            w.writeheader()
            for r in lignes: w.writerow(r)
    print(f"{n0} -> {len(base) + len(comp)} profils ({len(base)} + {len(comp)})")


if __name__ == "__main__":
    main()

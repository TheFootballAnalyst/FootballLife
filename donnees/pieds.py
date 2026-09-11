#!/usr/bin/env python3
"""pieds.py — le pied fort des joueurs, depuis FotMob.

    python3 donnees/pieds.py                        # tous les joueurs de jeu/jeu_2526.sqlite
    python3 donnees/pieds.py --fotmob moteur/fotmob.db
    python3 donnees/pieds.py --ids 1077894 30893
    python3 donnees/pieds.py --entete "x-mas: ..." # si FotMob repond 403

Écrit moteur/pieds.json : {"1077894": "droit", "30893": "gauche", ...}, que
l'importer recopie dans joueur.pied et que la carte affiche. Trois valeurs
seulement — "gauche", "droit", "deux" — plus l'absence, qui veut dire
inconnu et s'affiche comme tel.

POURQUOI UN TÉLÉCHARGEMENT, ET PAS UN CALCUL. Le pied fort n'est nulle part
dans les données déjà là : ni dans fotmob.db (player n'a que l'id, le nom et
l'id Opta), ni dans les feuilles de match en cache. Les tirs, eux, portent
un shotType (LeftFoot / RightFoot) — la tentation est d'en déduire le pied.
Mesuré sur les 3 963 matchs du cache : en exigeant au moins dix tirs du
pied, et en appelant « ambidextre » toute part du pied droit entre 25 % et
75 %, on obtient 46 % de droitiers, 23 % de gauchers et 31 % d'ambidextres.
La réalité est plutôt 75 / 22 / 3. Un tir de près, une reprise, une frappe
déviée se prennent du pied qui se présente : la part de tirs ne dit pas le
pied fort. C'est un fait sur des personnes réelles ; on le récupère ou on
le laisse inconnu, on ne le devine pas.

Bibliothèque standard, rythme poli, un 404 est retenu pour ne pas être
retenté. Le fichier est réécrit à chaque passage en gardant l'existant, donc
relancer après une journée ne récupère que les nouveaux.
"""
import argparse
import json
import pathlib
import sqlite3
import sys
import time
import urllib.error
import urllib.request

RACINE = pathlib.Path(__file__).resolve().parent.parent
DEST = RACINE / "moteur" / "pieds.json"
CACHE = RACINE / "moteur" / "cache" / "joueurs"     # profils bruts, si on les garde
URL = "https://www.fotmob.com/api/playerData?id={id}"
PAUSE = 0.4

# Ce que FotMob écrit -> ce que le jeu stocke.  La clé `key` est en anglais
# et stable ; le `fallback` est traduit et change avec la langue, donc on ne
# s'y fie qu'en dernier recours.
VALEURS = {
    "left": "gauche", "gauche": "gauche",
    "right": "droit", "droite": "droit", "droit": "droit",
    "both": "deux", "either": "deux", "les deux": "deux", "deux": "deux",
}


def extraire(profil) -> str | None:
    """Le pied fort d'un profil FotMob, quelle que soit la forme du JSON.

    L'API a déjà changé de forme plusieurs fois (playerInformation avec des
    title traduits, puis des translationKey, puis un champ direct). On
    cherche donc n'importe quelle entrée dont la clé ou le titre parle de
    pied, plutôt que de coder un seul chemin."""
    trouve = []

    def valeur(v):
        if isinstance(v, str):
            return v
        if isinstance(v, dict):
            return v.get("key") or v.get("fallback") or v.get("value")
        return None

    def marche(o):
        if isinstance(o, dict):
            for k, v in o.items():
                kl = str(k).lower()
                if "foot" in kl or "pied" in kl:
                    s = valeur(v)
                    if isinstance(s, str) and s.strip():
                        trouve.append(s)
                if kl in ("title", "translationkey") and isinstance(v, str) and \
                        ("foot" in v.lower() or "pied" in v.lower()):
                    s = valeur(o.get("value"))
                    if isinstance(s, str) and s.strip():
                        trouve.append(s)
                marche(v)
        elif isinstance(o, list):
            for v in o:
                marche(v)

    marche(profil)
    for s in trouve:
        p = VALEURS.get(s.strip().lower())
        if p:
            return p
    return None


def profil(pid: int, entetes: dict) -> dict | None:
    f = CACHE / f"{pid}.json"
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass
    req = urllib.request.Request(URL.format(id=pid), headers={"User-Agent": "Mozilla/5.0"} | entetes)
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    CACHE.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(data), encoding="utf-8")
    return data


def ids_depuis(chemin: pathlib.Path, table: str) -> list[int]:
    return [r[0] for r in sqlite3.connect(chemin).execute(f"SELECT DISTINCT player_id FROM {table}")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jeu", default=str(RACINE / "jeu" / "jeu_2526.sqlite"))
    ap.add_argument("--fotmob", default=None, help="base FotMob au lieu de la base de jeu")
    ap.add_argument("--ids", nargs="*", type=int, default=None)
    ap.add_argument("--entete", action="append", default=[],
                    help='en-tête HTTP « Nom: valeur », répétable (FotMob exige parfois un x-mas)')
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    entetes = {}
    for e in a.entete:
        nom, _, val = e.partition(":")
        entetes[nom.strip()] = val.strip()

    if a.ids:
        ids = a.ids
    elif a.fotmob:
        ids = ids_depuis(pathlib.Path(a.fotmob), "player")
    else:
        ids = ids_depuis(pathlib.Path(a.jeu), "joueur")

    connus = json.loads(DEST.read_text(encoding="utf-8")) if DEST.exists() else {}
    sans = set(connus.pop("_sans_pied", []))
    manquants = [i for i in ids if str(i) not in connus and i not in sans]
    print(f"{len(ids)} joueurs, {len(ids) - len(manquants)} déjà connus, {len(manquants)} à récupérer")
    if a.dry_run:
        return

    bilan = {"trouve": 0, "sans": 0, "erreur": 0}
    for k, pid in enumerate(manquants, 1):
        try:
            p = extraire(profil(pid, entetes) or {})
        except Exception as e:  # noqa: BLE001
            bilan["erreur"] += 1
            print(f"  {pid}: {e}", file=sys.stderr)
            if bilan["erreur"] > 20 and bilan["trouve"] == 0:
                sys.exit("20 erreurs et aucun pied trouvé : FotMob refuse les requêtes. "
                         "Récupère l'en-tête x-mas depuis ton navigateur et relance avec --entete.")
            continue
        if p:
            connus[str(pid)] = p
            bilan["trouve"] += 1
        else:
            sans.add(pid)
            bilan["sans"] += 1
        if k % 50 == 0:
            print(f"  {k}/{len(manquants)}  {bilan}")
            ecrire(connus, sans)
        time.sleep(PAUSE)
    ecrire(connus, sans)
    print(bilan, f"-> {DEST}")


def ecrire(connus: dict, sans: set):
    DEST.write_text(json.dumps(dict(sorted(connus.items(), key=lambda kv: int(kv[0])))
                               | {"_sans_pied": sorted(sans)}, ensure_ascii=False, indent=0),
                    encoding="utf-8")


if __name__ == "__main__":
    main()

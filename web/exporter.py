#!/usr/bin/env python3
"""exporter.py — season data + portrait thumbnails for the web prototype.

    python3 web/exporter.py [--jeu jeu/jeu_2526.sqlite] [--sortie out/proto]

Writes data.json (cards of the global perimeter seeded on J1-J17, rated
performances J18-J34, scripted managers' scores from out/managers.csv)
and thumbs.json (72 px portraits, base64) for web/construire.py.
"""
import argparse, base64, csv, io, json, pathlib, sqlite3, sys
from PIL import Image
RACINE = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
from jeu import backtest as BT, evolution as E  # noqa: E402

NOMS_LIGUE = {47: "Premier League", 87: "LaLiga", 55: "Serie A", 54: "Bundesliga", 53: "Ligue 1"}
NOMS_COMP = {47: "PL", 87: "LIGA", 55: "SA", 54: "BL", 53: "L1", 42: "C1", 74: "SC", 247: "CS", 207: "TC", 139: "SCE", 222: "SCI", 11015: "SCI"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jeu", default=str(RACINE / "jeu" / "jeu_2526.sqlite"))
    ap.add_argument("--managers", default=str(RACINE / "out" / "managers.csv"))
    ap.add_argument("--sortie", default=str(RACINE / "out" / "proto"))
    ap.add_argument("--amorce", default="1-17"); ap.add_argument("--jouer", default="18-34")
    a = ap.parse_args()
    S = pathlib.Path(a.sortie); S.mkdir(parents=True, exist_ok=True)
    jeu = sqlite3.connect(a.jeu)
    amorce, jouer = BT.parse_plage(a.amorce), BT.parse_plage(a.jouer)
    joueurs, prestas, _ = BT.charger(jeu, 0)
    cartes = BT.amorcer(joueurs, prestas, amorce)
    clubs = {tid: dict(nom=nom, couleur=coul) for tid, nom, coul in jeu.execute("SELECT team_id, nom, couleur FROM club")}
    ligue_club = {}
    for tid, cid, n in jeu.execute("SELECT home_team_id, competition_id, COUNT(*) FROM match WHERE competition_id IN (47,87,55,54,53) GROUP BY 1,2"):
        if tid not in ligue_club or n > ligue_club[tid][1]:
            ligue_club[tid] = (cid, n)
    acc = {}
    for pid, m, att in jeu.execute("""SELECT p.player_id, p.minutes, p.attributs FROM prestation p
            JOIN match mt ON mt.match_id = p.match_id JOIN journee j ON j.journee_id = mt.journee_id
            WHERE j.numero <= ?""", (amorce[-1],)):
        if pid in cartes:
            d = acc.setdefault(pid, [0.0, {}]); d[0] += m
            for k, v in json.loads(att).items():
                d[1][k] = d[1].get(k, 0) + v * m
    att = {pid: ({k: int(round(v / w)) for k, v in s.items()} if w else {}) for pid, (w, s) in acc.items()}
    journees = [dict(n=num, du=du, au=au) for num, du, au in jeu.execute(
        "SELECT numero, du, au FROM journee WHERE numero BETWEEN ? AND ? ORDER BY numero", (jouer[0], jouer[-1]))]
    out_cartes = [dict(id=pid, nom=joueurs[pid]["nom"], poste=c.poste, fam=c.fam, club=joueurs[pid]["team_id"],
                       n0=round(c.note_ovr, 4), hist=[[n, int(m)] for n, m in c.notes[-5:]],
                       min0=int(sum(m for _, m in c.notes)), att=att.get(pid, {})) for pid, c in cartes.items()]
    out_prestas = {num: {pid: [[p.note, int(p.minutes), NOMS_COMP.get(int(p.competition), "?")] for p in lst]
                         for pid, lst in prestas[num].items()} for num in jouer}
    bots = {}
    if pathlib.Path(a.managers).exists():
        for r in csv.DictReader(open(a.managers, encoding="utf-8")):
            bots.setdefault(r["manager"], []).append(float(r["score"]))
        bots = {k: v for k, v in bots.items() if k in ("naif", "forme", "oracle", "hasard0", "hasard1")}
    tids = {j["team_id"] for j in joueurs.values()}
    clubs_out = {tid: dict(nom=c["nom"], couleur=c["couleur"], ligue=NOMS_LIGUE.get(ligue_club.get(tid, (0,))[0], ""))
                 for tid, c in clubs.items() if tid in tids}
    data = dict(saison="2025/26", echelle=dict(bas=E.NOTE_OVR_BAS, haut=E.NOTE_OVR_HAUT), budget=E.BUDGET_INITIAL,
                journees=journees, clubs=clubs_out, cartes=out_cartes, prestas=out_prestas, bots=bots)
    (S / "data.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    P = RACINE / "moteur" / "images" / "joueurs"; thumbs = {}
    for c in out_cartes:
        f = P / f"{c['id']}.png"
        if c["min0"] < 270 or not f.exists():
            continue
        im = Image.open(f).convert("RGBA"); bb = im.getchannel("A").getbbox()
        if bb:
            im = im.crop(bb)
        k = 72 / im.height
        im = im.resize((max(1, int(im.width * k)), 72), Image.LANCZOS).quantize(48, method=Image.Quantize.FASTOCTREE)
        b = io.BytesIO(); im.save(b, "PNG", optimize=True)
        thumbs[c["id"]] = base64.b64encode(b.getvalue()).decode()
    (S / "thumbs.json").write_text(json.dumps(thumbs), encoding="utf-8")
    print(f"{len(out_cartes)} cartes, {len(thumbs)} vignettes -> {S}")


if __name__ == "__main__":
    main()

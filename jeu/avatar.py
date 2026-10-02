"""Les portraits et les écussons du monde fictif (PLAN.md § 4.3).

Un portrait par carte, dessiné par le jeu : un buste dans le style des cartes,
tiré de manière déterministe (même carte, même visage d'une base à l'autre) —
la carnation suit la nationalité (des probabilités, jamais une règle), la
coiffure, la barbe, la forme du visage et les traits viennent du hasard de la
carte, le maillot prend la couleur du club.  Rien ici ne regarde la vraie
photo : c'est un avatar, pas un portrait-robot.

Un écusson par club : un blason dans la couleur du club avec ses initiales.

Tout est dessiné avec Pillow, sans fichier à télécharger ; le serveur met en
cache le résultat.
"""
from __future__ import annotations

import hashlib
import pathlib

from PIL import Image, ImageDraw, ImageFilter, ImageFont

RACINE = pathlib.Path(__file__).resolve().parents[1]
POLICE = RACINE / "moteur" / "Anton-Regular.ttf"

# -- les carnations, par groupe de nationalités (jeu/fictif.GROUPE_PAYS) --------------
# (teinte claire → foncée) et, par groupe, les poids de tirage
CARNATIONS = [
    ((247, 219, 195), (229, 190, 160)),   # 0 très clair
    ((236, 198, 166), (214, 168, 134)),   # 1 clair
    ((218, 172, 132), (194, 144, 104)),   # 2 hâlé
    ((186, 135, 92), (158, 108, 70)),     # 3 mat
    ((140, 92, 58), (112, 70, 42)),       # 4 brun
    ((96, 62, 40), (72, 44, 28)),         # 5 foncé
    ((66, 42, 30), (46, 28, 20)),         # 6 très foncé
]
POIDS_CARNATION = {
    "fr": [25, 35, 20, 8, 6, 4, 2], "en": [30, 35, 15, 8, 6, 4, 2], "es": [15, 35, 35, 10, 3, 1, 1], "latam": [8, 25, 35, 20, 8, 3, 1],
    "pt": [10, 30, 35, 15, 6, 3, 1], "br": [5, 15, 25, 25, 15, 10, 5], "it": [15, 35, 35, 12, 2, 1, 0], "de": [35, 40, 15, 5, 3, 1, 1],
    "nl": [35, 35, 12, 6, 6, 4, 2], "be": [30, 35, 15, 6, 7, 5, 2], "ch": [30, 40, 18, 6, 3, 2, 1], "tr": [8, 30, 40, 18, 3, 1, 0],
    "scandi": [45, 40, 10, 3, 1, 1, 0], "pl": [40, 40, 15, 4, 1, 0, 0], "cz": [40, 40, 15, 4, 1, 0, 0], "hu": [35, 40, 18, 5, 2, 0, 0],
    "balkan": [25, 40, 25, 8, 2, 0, 0], "gr": [10, 35, 40, 13, 2, 0, 0], "ro": [25, 40, 25, 8, 2, 0, 0], "est": [40, 40, 15, 4, 1, 0, 0],
    "sahel": [0, 0, 1, 4, 20, 40, 35], "golfe": [0, 0, 1, 3, 16, 40, 40], "centre": [0, 0, 1, 3, 16, 40, 40], "maghreb": [3, 20, 40, 27, 8, 2, 0],
    "arabe": [2, 15, 40, 30, 10, 3, 0], "afrique_est": [0, 1, 4, 15, 30, 30, 20], "jp": [20, 50, 27, 3, 0, 0, 0], "kr": [25, 50, 22, 3, 0, 0, 0],
    "asie": [10, 40, 35, 12, 3, 0, 0], "monde": [20, 25, 20, 12, 10, 8, 5],
}
CHEVEUX = {"noir": (24, 20, 20), "brun": (72, 48, 30), "chatain": (120, 86, 54), "blond": (206, 170, 96), "roux": (168, 82, 40), "gris": (150, 150, 150)}
# par groupe : les poids (noir, brun, châtain, blond, roux, gris)
POIDS_CHEVEUX = {"scandi": [5, 20, 25, 42, 5, 3], "en": [20, 30, 25, 15, 7, 3], "de": [10, 30, 30, 25, 3, 2], "nl": [10, 28, 28, 28, 4, 2],
                 "pl": [10, 30, 30, 25, 3, 2], "cz": [10, 30, 30, 25, 3, 2], "est": [15, 30, 30, 20, 3, 2], "fr": [25, 35, 25, 10, 3, 2],
                 "be": [20, 35, 25, 15, 3, 2], "ch": [15, 35, 28, 18, 2, 2], "monde": [40, 30, 15, 10, 3, 2]}
COIFFURES = ["court", "ras", "boucle", "long", "chauve", "afro", "houppe", "cote"]
BARBES = ["aucune", "aucune", "ombre", "ombre", "bouc", "pleine"]


def _h(cle: str) -> int:
    return int(hashlib.sha1(cle.encode("utf-8")).hexdigest(), 16)


def _choix(h: int, poids: list[int]) -> int:
    total = sum(poids) or 1
    r = h % total
    for i, p in enumerate(poids):
        r -= p
        if r < 0:
            return i
    return len(poids) - 1


def _hex(c: str, defaut=(20, 22, 30)) -> tuple[int, int, int]:
    try:
        c = c.lstrip("#")
        return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    except (ValueError, TypeError, IndexError):
        return defaut


def _clair(c, k=0.35):
    return tuple(min(255, int(v + (255 - v) * k)) for v in c)


def _sombre(c, k=0.35):
    return tuple(max(0, int(v * (1 - k))) for v in c)


def traits(pid: int, groupe: str = "monde") -> dict:
    """Les traits d'un visage, tirés de la carte : tout ce que le dessin décide."""
    h = _h(f"avatar:{pid}")
    g = groupe if groupe in POIDS_CARNATION else "monde"
    carn = _choix(h, POIDS_CARNATION[g])
    h2 = h // 1000
    cheveux_i = _choix(h2, POIDS_CHEVEUX.get(g, POIDS_CHEVEUX["monde"]))
    if carn >= 4:
        cheveux_i = 0 if cheveux_i in (3, 4) else cheveux_i       # pas de blond ni de roux sur une peau brune
    h3 = h2 // 1000
    coiffure = COIFFURES[h3 % len(COIFFURES)]
    if carn >= 4 and coiffure in ("long", "houppe"):
        coiffure = "afro" if h3 % 2 else "ras"
    if carn <= 2 and coiffure == "afro":
        coiffure = "boucle"
    h4 = h3 // 100
    return {
        "carnation": carn, "cheveux": list(CHEVEUX)[cheveux_i], "coiffure": coiffure,
        "barbe": BARBES[h4 % len(BARBES)], "visage": ["rond", "long", "carre", "ovale"][(h4 // 10) % 4],
        "yeux": [(60, 40, 30), (40, 60, 90), (70, 90, 60), (30, 24, 20)][(h4 // 40) % 4] if carn <= 2 else [(60, 40, 30), (30, 24, 20)][(h4 // 40) % 2],
        "sourcils": (h4 // 160) % 3,          # 0 fins, 1 moyens, 2 épais
        "bouche": (h4 // 480) % 3,            # 0 neutre, 1 sourire, 2 sérieux
        "nez": (h4 // 1440) % 3,
    }


def portrait(pid: int, groupe: str = "monde", couleur_club: str = "#14161E", taille: int = 300) -> Image.Image:
    """Le buste d'une carte : fond transparent, dans la proportion des portraits
    que le dessin de carte attend (le visage au tiers supérieur)."""
    t = traits(pid, groupe)
    W, H = taille, int(taille * 1.2)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    peau, ombre = CARNATIONS[t["carnation"]]
    club = _hex(couleur_club)
    cx = W // 2
    # le maillot : épaules et col
    d.rounded_rectangle([int(W * 0.12), int(H * 0.68), int(W * 0.88), H + 20], radius=int(W * 0.18), fill=club)
    d.polygon([(cx - int(W * 0.09), int(H * 0.68)), (cx + int(W * 0.09), int(H * 0.68)), (cx, int(H * 0.78))], fill=_sombre(club, 0.45))
    d.line([(int(W * 0.12), int(H * 0.86)), (int(W * 0.12), H)], fill=_sombre(club, 0.3), width=3)
    # le cou
    d.rounded_rectangle([cx - int(W * 0.10), int(H * 0.55), cx + int(W * 0.10), int(H * 0.72)], radius=int(W * 0.05), fill=ombre)
    # le visage
    hv = {"rond": (0.30, 0.34), "long": (0.26, 0.38), "carre": (0.30, 0.35), "ovale": (0.27, 0.36)}[t["visage"]]
    rx, ry = int(W * hv[0]), int(H * hv[1])
    cy = int(H * 0.36)
    if t["visage"] == "carre":
        d.rounded_rectangle([cx - rx, cy - ry, cx + rx, cy + ry], radius=int(rx * 0.55), fill=peau)
    else:
        d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=peau)
    # les oreilles
    for s in (-1, 1):
        d.ellipse([cx + s * rx - int(W * 0.05), cy - int(H * 0.04), cx + s * rx + int(W * 0.05), cy + int(H * 0.06)], fill=ombre)
    # la barbe
    couleur_cheveux = CHEVEUX[t["cheveux"]]
    if t["barbe"] != "aucune":
        barbe = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        db = ImageDraw.Draw(barbe)
        alpha = {"ombre": 70, "bouc": 170, "pleine": 210}[t["barbe"]]
        col = couleur_cheveux + (alpha,)
        if t["barbe"] == "bouc":
            db.ellipse([cx - int(rx * 0.35), cy + int(ry * 0.45), cx + int(rx * 0.35), cy + int(ry * 1.0)], fill=col)
        else:
            db.ellipse([cx - rx, cy - int(ry * 0.05), cx + rx, cy + ry], fill=col)
            db.ellipse([cx - int(rx * 0.95), cy - int(ry * 0.8), cx + int(rx * 0.95), cy + int(ry * 0.35)], fill=(0, 0, 0, 0))
        masque = Image.new("L", (W, H), 0)
        ImageDraw.Draw(masque).ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=255)
        barbe.putalpha(Image.composite(barbe.getchannel("A"), Image.new("L", (W, H), 0), masque))
        im.alpha_composite(barbe)
    # les yeux, les sourcils, le nez, la bouche
    ey = cy - int(ry * 0.12)
    for s in (-1, 1):
        ex = cx + s * int(rx * 0.42)
        d.ellipse([ex - int(W * 0.045), ey - int(H * 0.022), ex + int(W * 0.045), ey + int(H * 0.022)], fill=(250, 250, 250))
        d.ellipse([ex - int(W * 0.02), ey - int(H * 0.016), ex + int(W * 0.02), ey + int(H * 0.016)], fill=t["yeux"])
        d.ellipse([ex - int(W * 0.008), ey - int(H * 0.007), ex + int(W * 0.008), ey + int(H * 0.007)], fill=(10, 10, 10))
        ep = [2, 4, 6][t["sourcils"]]
        d.line([(ex - int(W * 0.06), ey - int(H * 0.055)), (ex + int(W * 0.06), ey - int(H * 0.06) - s * 2)], fill=couleur_cheveux, width=ep)
    nz = cy + int(ry * 0.22)
    nl = [0.05, 0.065, 0.08][t["nez"]]
    d.line([(cx, ey + int(H * 0.02)), (cx - int(W * 0.02), nz)], fill=ombre, width=3)
    d.arc([cx - int(W * nl), nz - int(H * 0.03), cx + int(W * nl), nz + int(H * 0.02)], 0, 180, fill=ombre, width=3)
    by = cy + int(ry * 0.55)
    if t["bouche"] == 1:
        d.arc([cx - int(W * 0.09), by - int(H * 0.04), cx + int(W * 0.09), by + int(H * 0.02)], 10, 170, fill=_sombre(ombre, 0.3), width=4)
    else:
        d.line([(cx - int(W * 0.08), by), (cx + int(W * 0.08), by)], fill=_sombre(ombre, 0.3), width=4 if t["bouche"] == 2 else 3)
    # les cheveux, au-dessus de tout
    if t["coiffure"] != "chauve":
        ch = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        dc = ImageDraw.Draw(ch)
        col = couleur_cheveux + (255,)
        top = cy - ry
        if t["coiffure"] == "ras":
            dc.ellipse([cx - rx, top - int(ry * 0.02), cx + rx, cy - int(ry * 0.15)], fill=couleur_cheveux + (190,))
            dc.ellipse([cx - int(rx * 0.98), cy - int(ry * 0.75), cx + int(rx * 0.98), cy + int(ry * 0.9)], fill=(0, 0, 0, 0))
        elif t["coiffure"] == "afro":
            dc.ellipse([cx - int(rx * 1.25), top - int(ry * 0.45), cx + int(rx * 1.25), cy + int(ry * 0.15)], fill=col)
            dc.ellipse([cx - int(rx * 0.97), cy - int(ry * 0.72), cx + int(rx * 0.97), cy + ry], fill=(0, 0, 0, 0))
        elif t["coiffure"] == "long":
            dc.ellipse([cx - int(rx * 1.12), top - int(ry * 0.2), cx + int(rx * 1.12), cy + int(ry * 0.9)], fill=col)
            dc.ellipse([cx - int(rx * 0.95), cy - int(ry * 0.62), cx + int(rx * 0.95), cy + int(ry * 1.05)], fill=(0, 0, 0, 0))
        elif t["coiffure"] == "houppe":
            dc.ellipse([cx - int(rx * 1.02), top - int(ry * 0.3), cx + int(rx * 1.02), cy - int(ry * 0.25)], fill=col)
            dc.ellipse([cx - int(rx * 0.95), cy - int(ry * 0.68), cx + int(rx * 0.95), cy + ry], fill=(0, 0, 0, 0))
            dc.ellipse([cx - int(rx * 0.45), top - int(ry * 0.55), cx + int(rx * 0.35), top + int(ry * 0.2)], fill=col)
        elif t["coiffure"] == "cote":
            dc.ellipse([cx - int(rx * 1.04), top - int(ry * 0.22), cx + int(rx * 1.04), cy - int(ry * 0.2)], fill=col)
            dc.ellipse([cx - int(rx * 0.95), cy - int(ry * 0.66), cx + int(rx * 1.05), cy + ry], fill=(0, 0, 0, 0))
        elif t["coiffure"] == "boucle":
            dc.ellipse([cx - int(rx * 1.1), top - int(ry * 0.3), cx + int(rx * 1.1), cy - int(ry * 0.1)], fill=col)
            for k in range(7):
                ang = k / 6
                dc.ellipse([cx - rx + int(2 * rx * ang) - int(rx * 0.16), top - int(ry * 0.36) + int(abs(ang - 0.5) * ry * 0.4) - int(rx * 0.16),
                            cx - rx + int(2 * rx * ang) + int(rx * 0.16), top - int(ry * 0.36) + int(abs(ang - 0.5) * ry * 0.4) + int(rx * 0.16)], fill=col)
            dc.ellipse([cx - int(rx * 0.95), cy - int(ry * 0.68), cx + int(rx * 0.95), cy + ry], fill=(0, 0, 0, 0))
        else:  # court
            dc.ellipse([cx - int(rx * 1.04), top - int(ry * 0.12), cx + int(rx * 1.04), cy - int(ry * 0.2)], fill=col)
            dc.ellipse([cx - int(rx * 0.95), cy - int(ry * 0.7), cx + int(rx * 0.95), cy + ry], fill=(0, 0, 0, 0))
        im.alpha_composite(ch)
    # un léger ombrage sous le menton et un adoucissement
    om = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(om).ellipse([cx - int(rx * 0.9), cy + int(ry * 0.8), cx + int(rx * 0.9), cy + int(ry * 1.3)], fill=(0, 0, 0, 60))
    om = om.filter(ImageFilter.GaussianBlur(6))
    masque = im.getchannel("A")
    om.putalpha(Image.composite(om.getchannel("A"), Image.new("L", (W, H), 0), masque))
    im.alpha_composite(om)
    return im


def initiales(nom: str) -> str:
    mots = [m for m in nom.replace("-", " ").split() if m and not m.isdigit()]
    if not mots:
        return "FC"
    if len(mots) == 1:
        return mots[0][:3].upper()
    return "".join(m[0] for m in mots[:3]).upper()


def ecusson(tid: int, nom: str, couleur: str = "#14161E", taille: int = 256) -> Image.Image:
    """Le blason d'un club : un écu dans sa couleur, une bande claire, ses initiales,
    et une forme tirée du club (pointe, arrondi, bandes)."""
    h = _h(f"ecusson:{tid}")
    W = H = taille
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    club = _hex(couleur)
    clair = _clair(club, 0.55)
    forme = h % 3
    m = int(W * 0.08)
    if forme == 0:      # l'écu classique
        pts = [(m, m), (W - m, m), (W - m, int(H * 0.6)), (W // 2, H - m), (m, int(H * 0.6))]
    elif forme == 1:    # l'écu arrondi
        pts = [(m, m), (W - m, m), (W - m, int(H * 0.55))] + [(int(W / 2 + (W / 2 - m) * __import__("math").cos(a)), int(H * 0.55 + (H - m - H * 0.55) * __import__("math").sin(a)))
                                                            for a in [i / 12 * 3.14159 for i in range(0, 13)]] + [(m, int(H * 0.55))]
    else:               # le rond
        pts = None
    if pts:
        d.polygon(pts, fill=club, outline=_sombre(club, 0.4), width=4)
    else:
        d.ellipse([m, m, W - m, H - m], fill=club, outline=_sombre(club, 0.4), width=4)
    # la bande ou les rayures
    motif = (h // 7) % 3
    bande = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    db = ImageDraw.Draw(bande)
    if motif == 0:
        db.rectangle([int(W * 0.38), 0, int(W * 0.62), H], fill=clair + (120,))
    elif motif == 1:
        for x in range(int(W * 0.2), int(W * 0.8), int(W * 0.15)):
            db.rectangle([x, 0, x + int(W * 0.06), H], fill=clair + (110,))
    else:
        db.polygon([(0, int(H * 0.35)), (W, int(H * 0.05)), (W, int(H * 0.3)), (0, int(H * 0.6))], fill=clair + (120,))
    masque = im.getchannel("A")
    bande.putalpha(Image.composite(bande.getchannel("A"), Image.new("L", (W, H), 0), masque))
    im.alpha_composite(bande)
    # les initiales
    txt = initiales(nom)
    try:
        police = ImageFont.truetype(str(POLICE), int(W * (0.34 if len(txt) <= 2 else 0.26)))
    except OSError:
        police = ImageFont.load_default()
    d = ImageDraw.Draw(im)
    bb = d.textbbox((0, 0), txt, font=police)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    d.text(((W - tw) / 2 - bb[0], (H * 0.9 - th) / 2 - bb[1]), txt, font=police, fill=(255, 255, 255), stroke_width=3, stroke_fill=_sombre(club, 0.5))
    return im

# -*- coding: utf-8 -*-
"""carte_design.py — la carte joueur de la chaine, version attributs.

Decor de competition avec son logo, couleurs du club, portrait en grand, nom,
jeton hexagonal, et six sous-notes par famille du bareme : finition,
creation, progression, defense, dribble, conservation. Les sous-notes sont
sur 40-99 comme les radars du Ballon d'or.
"""
import math, pathlib
from PIL import Image, ImageDraw, ImageFont, ImageFilter

PROJ = pathlib.Path(__file__).resolve().parent
OR, ORCLAIR, BLANC, NOIR, GRIS = (212,175,55), (242,211,107), (247,245,238), (7,8,12), (154,160,174)

_f = {}
def F(nom, taille):
    if (nom, taille) not in _f:
        chemin = {"anton": PROJ/"Anton-Regular.ttf", "bar": PROJ/"BarlowCondensed-Medium.ttf",
                  "barb": PROJ/"BarlowCondensed-Bold.ttf"}[nom]
        _f[(nom, taille)] = ImageFont.truetype(str(chemin), taille)
    return _f[(nom, taille)]

def rgb(h):
    h = h.lstrip('#'); return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

DECORS = {
    "Ligue 1":          {"fond": ("#0E2352", "#05070D"), "accent": "#4FA3FF", "logo": "ligue-1"},
    "Champions League": {"fond": ("#0A1F4B", "#04060C"), "accent": "#8FBFFF", "logo": "champions-league"},
    "Premier League":   {"fond": ("#2E0C3F", "#06040A"), "accent": "#C77DFF", "logo": "premier-league"},
    "LaLiga":           {"fond": ("#3F1013", "#0A0405"), "accent": "#FF6A5E", "logo": "laliga"},
    "Serie A":          {"fond": ("#0A2D45", "#04080C"), "accent": "#5FD3FF", "logo": "serie-a"},
    "Bundesliga":       {"fond": ("#3F0B0B", "#0A0404"), "accent": "#FF5A5A", "logo": "bundesliga"},
}
DEFAUT = {"fond": ("#14161E", "#06070B"), "accent": "#D4AF37", "logo": None}
AXES = [("FIN", "FINITION"), ("CRE", "CRÉATION"), ("PRO", "PROGRESSION"),
        ("DEF", "DÉFENSE"), ("DRI", "DRIBBLE"), ("CON", "CONSERV.")]
# Un gardien n'a ni finition ni dribble : afficher 40 partout ne dit rien de
# son match. On lui montre ses propres familles, celles du bareme gardien.
AXES_GK = [("ARR", "ARRÊTS"), ("EVI", "BUTS ÉVITÉS"), ("SOR", "SORTIES"),
           ("REL", "RELANCE"), ("BUT", "IMBATTABILITÉ"), ("PRO", "PROGRESSION")]


def hexagone(c, r):
    return [(c[0] + r*math.cos(math.radians(a)), c[1] + r*math.sin(math.radians(a)))
            for a in range(-90, 270, 60)]


def jeton(im, cx, cy, note, r):
    d = ImageDraw.Draw(im)
    halo = Image.new('RGBA', im.size, (0, 0, 0, 0))
    ImageDraw.Draw(halo).polygon(hexagone((cx, cy), r*1.4), fill=OR + (130,))
    im.alpha_composite(halo.filter(ImageFilter.GaussianBlur(r*0.38)))
    d = ImageDraw.Draw(im)
    d.polygon(hexagone((cx+2, cy+4), r), fill=(0, 0, 0, 150))
    d.polygon(hexagone((cx, cy), r), fill=(12, 13, 18, 255), outline=OR + (255,))
    d.polygon(hexagone((cx, cy), r-7), outline=OR + (120,))
    d.text((cx, cy + r*0.05), f"{note:.1f}", font=F('anton', int(r*1.3)), fill=BLANC, anchor='mm')


def logo_ligue(nom, haut):
    src = PROJ / "images" / "ligues" / f"{nom}.png"
    if not src.exists():
        return None
    im = Image.open(src).convert('RGBA')
    k = haut / im.height
    return im.resize((int(im.width*k), haut), Image.LANCZOS)


def logo_club(tid, taille):
    src = PROJ / "images" / "logos" / f"{tid}.png"
    if not src.exists():
        return None
    return Image.open(src).convert('RGBA').resize((taille, taille), Image.LANCZOS)


# Pied fort : la valeur declaree par la source (donnees/pieds.py), jamais
# deduite. Un joueur sans donnee n'affiche rien plutot qu'une supposition.
PIEDS = {"gauche": "GAUCHER", "droit": "DROITIER", "deux": "AMBIDEXTRE"}


def carte(pid, nom, note, club_couleur, competition, poste="", minutes=None,
          attributs=None, larg=420, team_id=None, pied=None):
    haut = int(larg * 1.50)
    dec = DECORS.get(competition, DEFAUT)
    marge = 26
    im = Image.new('RGBA', (larg + 2*marge, haut + 2*marge + 10), (0, 0, 0, 0))
    ox, oy = marge, marge

    sol = Image.new('RGBA', im.size, (0, 0, 0, 0))
    ImageDraw.Draw(sol).ellipse([ox-10, oy+haut-14, ox+larg+10, oy+haut+22], fill=(0, 0, 0, 170))
    im.alpha_composite(sol.filter(ImageFilter.GaussianBlur(9)))
    op = Image.new('RGBA', im.size, (0, 0, 0, 0))
    ImageDraw.Draw(op).rounded_rectangle([ox+4, oy+8, ox+larg+4, oy+haut+8], int(larg*0.07), fill=(0, 0, 0, 160))
    im.alpha_composite(op.filter(ImageFilter.GaussianBlur(7)))

    corps = Image.new('RGBA', (larg, haut), (0, 0, 0, 0))
    dc = ImageDraw.Draw(corps)
    # fond aux couleurs du MAILLOT : plein en haut, presque noir en bas. La
    # competition ne garde que son logo et sa couleur d'accent.
    club = rgb(club_couleur)
    c0 = tuple(int(v*0.78) for v in club)
    c1 = (7, 8, 12)
    for i in range(haut):
        k = (i / haut) ** 0.85
        dc.line([(0, i), (larg, i)], fill=tuple(int(c0[j] + (c1[j]-c0[j])*k) for j in range(3)) + (255,))

    # MAILLAGE d'ecussons : le logo du club repete en quinconce, tres pale,
    # comme un papier peint. C'est lui qui donne sa matiere a la carte — une
    # trame geometrique neutre ne disait rien du club.
    tuile = logo_club(team_id, int(larg*0.30)) if team_id else None
    if tuile is not None:
        pale = tuile.copy()
        pale.putalpha(pale.getchannel('A').point(lambda v: int(v*0.20)))
        grand = max(larg, haut) * 2
        maillage = Image.new('RGBA', (grand, grand), (0, 0, 0, 0))
        pas_x, pas_y = int(larg*0.36), int(larg*0.34)
        row = 0
        y = 0
        while y < grand:
            x = (pas_x//2 if row % 2 else 0)
            while x < grand:
                maillage.alpha_composite(pale, (x, y)); x += pas_x
            y += pas_y; row += 1
        # incline : une trame droite fait fond d'ecran, penchee elle fait tissu
        maillage = maillage.rotate(-18, resample=Image.BICUBIC)
        dep = (grand - larg)//2, (grand - haut)//2
        corps.alpha_composite(maillage.crop((dep[0], dep[1], dep[0]+larg, dep[1]+haut)))
    else:
        trame = Image.new('RGBA', (larg, haut), (0, 0, 0, 0))
        dt = ImageDraw.Draw(trame)
        r = larg * 0.07; dy = r*1.5; dx = r*math.sqrt(3); row = 0; y = -r
        while y < haut + r:
            x = -r + (dx/2 if row % 2 else 0)
            while x < larg + r:
                dt.polygon(hexagone((x, y), r*0.92), outline=(255, 255, 255, 16)); x += dx
            y += dy; row += 1
        corps.alpha_composite(trame)

    # halo du club derriere le portrait
    clair = tuple(min(255, int(v*1.35) + 30) for v in club)
    halo = Image.new('RGBA', (larg, haut), (0, 0, 0, 0))
    ImageDraw.Draw(halo).ellipse([larg*0.12, haut*0.14, larg*0.88, haut*0.58], fill=clair + (85,))
    corps.alpha_composite(halo.filter(ImageFilter.GaussianBlur(larg*0.16)))

    # rai de lumiere vertical derriere le joueur : detache le portrait du fond
    rai = Image.new('RGBA', (larg, haut), (0, 0, 0, 0))
    dr = ImageDraw.Draw(rai)
    for i in range(int(larg*0.34)):
        k = 1 - i/(larg*0.34)
        a_ = int(60 * k**2)
        dr.rectangle([larg/2 - i, haut*0.06, larg/2 + i, haut*0.70], outline=(255, 255, 255, a_))
    corps.alpha_composite(rai.filter(ImageFilter.GaussianBlur(larg*0.05)))

    # ecusson du club en filigrane, derriere le portrait : c'est lui qui donne
    # sa profondeur a la carte, le degrade seul restait plat


    # balayage
    bal = Image.new('RGBA', (larg, haut), (0, 0, 0, 0))
    db = ImageDraw.Draw(bal)
    for i in range(-40, 41, 2):
        a = int(24 * (1 - abs(i)/40)**2)
        db.line([(larg*0.10 + i, 0), (larg*0.90 + i, haut)], fill=(255, 255, 255, a), width=3)
    corps.alpha_composite(bal)

    # --- logo de la ligue, en haut a gauche, bien visible ---
    lg = logo_ligue(dec["logo"], int(larg*0.20)) if dec["logo"] else None
    if lg is not None:
        # pastille claire derriere pour les logos sombres
        pl = Image.new('RGBA', (larg, haut), (0, 0, 0, 0))
        ImageDraw.Draw(pl).rounded_rectangle([larg*0.04, larg*0.04, larg*0.04 + lg.width + larg*0.06,
                                              larg*0.04 + lg.height + larg*0.04], int(larg*0.04),
                                             fill=(247, 245, 238, 232))
        corps.alpha_composite(pl)
        corps.alpha_composite(lg, (int(larg*0.07), int(larg*0.06)))

    # --- portrait, grand ---
    src = PROJ / "images" / "joueurs" / f"{pid}.png"
    if src.exists():
        ph = Image.open(src).convert('RGBA')
        # Les portraits FotMob ont des marges variables : on recadre sur la
        # zone reellement occupee, sinon les visages flottent ou sont coupes.
        bb = ph.getchannel('A').getbbox()
        if bb:
            ph = ph.crop(bb)
        # Centrage sur le VISAGE : on mesure la largeur occupee au tiers
        # superieur du portrait — la hauteur des yeux — et on aligne ce
        # centre-la, pas celui de la boite englobante. Les epaules, souvent
        # asymetriques, decalaient tous les visages.
        a_ = ph.getchannel('A')
        ligne = int(ph.height * 0.30)
        xs = [x for x in range(ph.width) if a_.getpixel((x, ligne)) > 40]
        cx_visage = (xs[0] + xs[-1]) / 2 if xs else ph.width / 2
        tp = int(larg * 0.86)
        k = tp / max(ph.width, ph.height)
        ph = ph.resize((max(1, int(ph.width*k)), max(1, int(ph.height*k))), Image.LANCZOS)
        cx_visage *= k
        px = int(larg/2 - cx_visage)
        py = int(haut*0.655) - ph.height
        corps.alpha_composite(ph, (px, max(int(haut*0.11), py)))
    else:
        dc.text((larg/2, haut*0.42), ''.join(w[0] for w in nom.split()[:2]),
                font=F('anton', int(larg*0.45)), fill=BLANC, anchor='mm')

    # --- bloc bas : nom, poste, puis six attributs sur deux colonnes ---
    dc = ImageDraw.Draw(corps)
    bas = int(haut * 0.66)
    # bandeau a coin coupe, comme une etiquette
    dc.polygon([(0, bas + int(haut*0.028)), (larg*0.42, bas), (larg, bas),
                (larg, haut), (0, haut)], fill=(6, 7, 11, 240))
    dc.line([(0, bas + int(haut*0.028)), (larg*0.42, bas), (larg, bas)],
            fill=OR + (220,), width=3)
    dc.rectangle([0, bas + int(haut*0.028), int(larg*0.022), haut], fill=club + (255,))
    police = F('anton', int(larg*0.125))
    nom_c = nom.split()[-1].upper()
    while dc.textlength(nom_c, police) > larg*0.88 and police.size > 14:
        police = F('anton', police.size - 1)
    dc.text((larg*0.05, bas + int(haut*0.055)), nom_c, font=police, fill=BLANC, anchor='lm')
    sous = poste.upper() + (f"  ·  {PIEDS[pied]}" if pied in PIEDS else "") \
        + (f"  ·  {minutes:.0f} MIN" if minutes else "")
    dc.text((larg*0.05, bas + int(haut*0.115)), sous, font=F('bar', int(larg*0.058)),
            fill=rgb(dec["accent"]), anchor='lm')
    dc.line([(larg*0.05, bas + int(haut*0.15)), (larg*0.95, bas + int(haut*0.15))],
            fill=(247, 245, 238, 40), width=1)

    if attributs:
        y = bas + int(haut*0.175)
        pas = int(haut*0.058)
        table = AXES_GK if poste.lower().startswith("gardien") else AXES
        for k, (cle, lib) in enumerate(table):
            col = k % 2; row = k // 2
            x = larg*0.05 + col*larg*0.47
            yy = y + row*pas
            v = attributs.get(cle, 50)
            dc.text((x, yy), lib, font=F('bar', int(larg*0.052)), fill=GRIS, anchor='lm')
            dc.text((x + larg*0.42, yy), str(v), font=F('anton', int(larg*0.072)),
                    fill=ORCLAIR if v >= 80 else BLANC, anchor='rm')

    masque = Image.new('L', (larg, haut), 0)
    ImageDraw.Draw(masque).rounded_rectangle([0, 0, larg-1, haut-1], int(larg*0.07), fill=255)
    corps.putalpha(masque)
    dc.rounded_rectangle([1, 1, larg-2, haut-2], int(larg*0.07), outline=club + (255,), width=max(3, larg//60))
    dc.rounded_rectangle([7, 7, larg-8, haut-8], int(larg*0.06), outline=OR + (120,), width=1)
    im.alpha_composite(corps, (ox, oy))
    jeton(im, ox + larg - int(larg*0.17), oy + int(larg*0.17), note, int(larg*0.135))
    return im

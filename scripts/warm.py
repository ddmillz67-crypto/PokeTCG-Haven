"""Warme, filmische beelden voor #start-hier (welkomstbanner en eerste stappen).

    python -m scripts.warm

Sfeer: een gezellige kaartwinkel bij zonsondergang, met uitzicht op grachtenhuizen, lampjes,
een neonbord en een uitgelichte holo-kaart. Alles is eigen ontwerp: geen Pokémon-figuren,
geen Poké Ball en geen officiële logo's (merkrecht).
Lettertypen: Poppins en Pacifico (SIL Open Font License, zie scripts/fonts/).
"""

from __future__ import annotations

import math
import random
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

from scripts.banners import TYPES, UIT, booster, kaart, meng, ster

FONTS = Path(__file__).resolve().parent / "fonts"
GOUD = (246, 176, 82)
GOUD_LICHT = (255, 222, 150)
CREME = (236, 230, 222)


def f(naam: str, grootte: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / naam), grootte)


# -- bouwstenen -------------------------------------------------------------------------


def gloed(img: Image.Image, cx: float, cy: float, rx: float, ry: float, kleur, alfa: int, blur: int) -> None:
    laag = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(laag).ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=(*kleur, alfa))
    img.alpha_composite(laag.filter(ImageFilter.GaussianBlur(blur)))


def verloop(w: int, h: int, stops: list[tuple[float, tuple]], horizontaal: bool = False) -> Image.Image:
    img = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(img)
    n = w if horizontaal else h
    for i in range(n):
        t = i / max(1, n - 1)
        for (t0, k0), (t1, k1) in zip(stops, stops[1:]):
            if t0 <= t <= t1:
                k = meng(k0, k1, (t - t0) / (t1 - t0) if t1 > t0 else 0)
                break
        else:
            k = stops[-1][1]
        if horizontaal:
            d.line([(i, 0), (i, h)], fill=k)
        else:
            d.line([(0, i), (w, i)], fill=k)
    return img


def tekst_verloop(img: Image.Image, xy, tekst: str, fnt, boven, onder) -> None:
    """Tekst met een verticaal kleurverloop, zoals de goudkleurige titel in het voorbeeld."""
    masker = Image.new("L", img.size, 0)
    ImageDraw.Draw(masker).text(xy, tekst, font=fnt, fill=255)
    box = masker.getbbox()
    if not box:
        return
    vl = verloop(box[2] - box[0], box[3] - box[1], [(0, boven), (1, onder)]).convert("RGBA")
    laag = Image.new("RGBA", img.size, (0, 0, 0, 0))
    laag.paste(vl, box[:2])
    laag.putalpha(masker)
    schaduw = Image.new("RGBA", img.size, (0, 0, 0, 0))
    schaduw.putalpha(masker.point(lambda a: a * 0.55).filter(ImageFilter.GaussianBlur(6)))
    img.alpha_composite(schaduw, (0, 4))
    img.alpha_composite(laag)


def spatietekst(d: ImageDraw.ImageDraw, xy, tekst: str, fnt, kleur, spatie: float) -> float:
    x, y = xy
    for c in tekst:
        d.text((x, y), c, font=fnt, fill=kleur)
        x += d.textlength(c, font=fnt) + spatie
    return x


def neon(img: Image.Image, xy, tekst: str, fnt, kleur, kern=(255, 244, 220)) -> None:
    masker = Image.new("L", img.size, 0)
    ImageDraw.Draw(masker).text(xy, tekst, font=fnt, fill=255, anchor="mm")
    for blur, alfa in ((22, 0.9), (9, 1.0)):
        g = Image.new("RGBA", img.size, (*kleur, 0))
        g.putalpha(masker.filter(ImageFilter.GaussianBlur(blur)).point(lambda a, al=alfa: min(255, int(a * 2.2 * al))))
        img.alpha_composite(g)
    k = Image.new("RGBA", img.size, (*kern, 0))
    k.putalpha(masker)
    img.alpha_composite(k)


def embleem(d: ImageDraw.ImageDraw, cx: float, cy: float, r: float) -> None:
    """Het eigen Haven-embleem: een gouden munt met een ster (in plaats van een Poké Ball)."""
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=GOUD, outline=(255, 236, 190), width=max(2, int(r * 0.12)))
    d.ellipse([cx - r * 0.72, cy - r * 0.72, cx + r * 0.72, cy + r * 0.72], outline=(255, 236, 190, 160), width=max(1, int(r * 0.06)))
    ster(d, cx, cy, r * 0.55, (255, 255, 255), 0.42, 5)


def glaspaneel(img: Image.Image, box, radius: int = 24) -> None:
    """Matglas: wat erachter zit wordt vaag en donkerder, met een dunne lichte rand."""
    x0, y0, x1, y1 = box
    stuk = img.crop(box).filter(ImageFilter.GaussianBlur(18))
    donker = Image.new("RGBA", stuk.size, (14, 10, 14, 175))
    stuk = Image.alpha_composite(stuk, donker)
    masker = Image.new("L", stuk.size, 0)
    ImageDraw.Draw(masker).rounded_rectangle([0, 0, stuk.width - 1, stuk.height - 1], radius=radius, fill=255)
    img.paste(stuk, (x0, y0), masker)
    rand(img, box, radius, (255, 255, 255, 50), 2)


def rand(img: Image.Image, box, radius: int, kleur, breedte: int) -> None:
    """Een (half)doorzichtige rand, echt gemengd met wat eronder zit."""
    laag = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(laag).rounded_rectangle(box, radius=radius, outline=kleur, width=breedte)
    img.alpha_composite(laag)


# -- iconen (lijntekeningen in goud) ------------------------------------------------------


def icoon(d: ImageDraw.ImageDraw, soort: str, x: float, y: float, s: float, k=GOUD) -> None:
    w = max(2, int(s * 0.11))
    if soort == "mensen":
        d.ellipse([x + s * 0.12, y, x + s * 0.48, y + s * 0.36], fill=k)
        d.pieslice([x - s * 0.02, y + s * 0.42, x + s * 0.62, y + s * 1.1], 180, 360, fill=k)
        d.ellipse([x + s * 0.56, y + s * 0.06, x + s * 0.86, y + s * 0.36], fill=k)
        d.pieslice([x + s * 0.5, y + s * 0.46, x + s * 1.04, y + s * 1.02], 180, 360, fill=k)
    elif soort == "kaarten":
        d.rounded_rectangle([x + s * 0.3, y, x + s * 0.95, y + s * 0.85], radius=s * 0.1, outline=k, width=w)
        d.rounded_rectangle([x, y + s * 0.18, x + s * 0.62, y + s * 1.0], radius=s * 0.1, fill=(24, 18, 20), outline=k, width=w)
    elif soort == "ballon":
        d.rounded_rectangle([x, y + s * 0.05, x + s, y + s * 0.72], radius=s * 0.34, outline=k, width=w)
        d.polygon([(x + s * 0.22, y + s * 0.66), (x + s * 0.14, y + s * 0.98), (x + s * 0.46, y + s * 0.7)], fill=k)
    elif soort == "kalender":
        d.rounded_rectangle([x, y + s * 0.12, x + s, y + s], radius=s * 0.12, outline=k, width=w)
        d.rectangle([x, y + s * 0.12, x + s, y + s * 0.34], fill=k)
        for i in (0.28, 0.72):
            d.rounded_rectangle([x + s * i - w / 2, y, x + s * i + w / 2, y + s * 0.22], radius=w / 2, fill=k)
        for r_ in range(2):
            for c in range(3):
                cx, cy = x + s * (0.22 + c * 0.28), y + s * (0.52 + r_ * 0.26)
                d.rectangle([cx - s * 0.06, cy - s * 0.06, cx + s * 0.06, cy + s * 0.06], fill=k)
    elif soort == "deur":
        d.rounded_rectangle([x + s * 0.12, y, x + s * 0.88, y + s], radius=s * 0.08, outline=k, width=w)
        d.ellipse([x + s * 0.62, y + s * 0.48, x + s * 0.74, y + s * 0.6], fill=k)
    elif soort == "rol":
        d.rounded_rectangle([x + s * 0.1, y, x + s * 0.9, y + s], radius=s * 0.1, outline=k, width=w)
        for i in range(3):
            yy = y + s * (0.25 + i * 0.24)
            d.line([(x + s * 0.28, yy), (x + s * 0.72, yy)], fill=k, width=w)
    elif soort == "kompas":
        d.ellipse([x, y, x + s, y + s], outline=k, width=w)
        cx, cy = x + s / 2, y + s / 2
        d.polygon([(cx, cy - s * 0.32), (cx + s * 0.12, cy), (cx, cy + s * 0.32), (cx - s * 0.12, cy)], fill=k)
    elif soort == "ster":
        ster(d, x + s / 2, y + s / 2, s * 0.52, k, 0.42, 5)


# -- de scène ----------------------------------------------------------------------------


def grachtenhuis(d: ImageDraw.ImageDraw, x: float, basis: float, b: float, h: float, kleur, licht, rng: random.Random) -> None:
    top = basis - h
    d.rectangle([x, top, x + b, basis], fill=kleur)
    gevel = rng.choice(("trap", "klok", "punt"))
    if gevel == "trap":
        stap = b / 6
        for i in range(3):
            d.rectangle([x + stap * i, top - stap * (i + 1) * 0.9, x + b - stap * i, top], fill=kleur)
    elif gevel == "klok":
        d.ellipse([x + b * 0.15, top - b * 0.55, x + b * 0.85, top + b * 0.15], fill=kleur)
        d.rectangle([x + b * 0.35, top - b * 0.75, x + b * 0.65, top - b * 0.4], fill=kleur)
    else:
        d.polygon([(x, top), (x + b / 2, top - b * 0.6), (x + b, top)], fill=kleur)
    for rij in range(int(h // 30)):
        for kol in range(2 if b < 46 else 3):
            if rng.random() < 0.35:
                wx = x + 7 + kol * (b - 14) / (2 if b < 46 else 3)
                wy = top + 14 + rij * 30
                d.rectangle([wx, wy, wx + 8, wy + 13], fill=licht)


def scene(w: int = 1600, h: int = 452, seed: int = 7, held: bool = True) -> Image.Image:
    rng = random.Random(seed)
    img = verloop(w, h, [(0, (58, 32, 70)), (0.2, (156, 66, 86)), (0.4, (244, 122, 64)), (0.56, (255, 172, 92)), (1, (255, 206, 140))]).convert("RGBA")
    gloed(img, w * 0.72, h * 0.5, 340, 190, (255, 190, 100), 230, 70)
    gloed(img, w * 0.72, h * 0.52, 80, 64, (255, 240, 200), 255, 26)
    # skyline: grachtenhuizen en een kerktoren, twee lagen voor diepte
    for laag, (kleur, schaal, basis) in enumerate((((122, 62, 78, 255), 0.8, h * 0.66), ((70, 36, 54, 255), 1.0, h * 0.72))):
        d = ImageDraw.Draw(img, "RGBA")
        x = w * 0.28
        while x < w * 0.86:
            b = rng.randint(34, 58) * schaal
            grachtenhuis(d, x, basis, b, rng.randint(80, 150) * schaal, kleur, (255, 206, 128, 220 if laag else 150), rng)
            x += b + rng.randint(0, 3)
        if laag == 0:
            tx = w * 0.47
            d.rectangle([tx, basis - 250, tx + 34, basis], fill=kleur)
            d.rectangle([tx + 6, basis - 290, tx + 28, basis - 250], fill=kleur)
            d.polygon([(tx + 2, basis - 290), (tx + 17, basis - 360), (tx + 32, basis - 290)], fill=kleur)
            d.ellipse([tx + 9, basis - 236, tx + 25, basis - 220], fill=(255, 214, 150, 200))
        gloed(img, w * 0.6, basis, w * 0.35, 30, (255, 170, 100), 70, 25)
    # de kamer: donkere wanden links en rechts, het raam in het midden
    kamer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    kd = ImageDraw.Draw(kamer)
    for x in range(w):
        links = max(0.0, 1 - x / (w * 0.3))
        rechts = max(0.0, (x - w * 0.81) / (w * 0.19))
        a = int(255 * min(1, max(links, rechts) ** 0.7 * 1.05))
        kd.line([(x, 0), (x, h)], fill=(30, 17, 16, a))
    img.alpha_composite(kamer)
    d = ImageDraw.Draw(img, "RGBA")
    for x in (w * 0.33, w * 0.8):
        d.rectangle([x - 9, 0, x + 9, h * 0.76], fill=(40, 24, 20, 255))
    d.rectangle([w * 0.33, h * 0.735, w * 0.8, h * 0.76], fill=(48, 28, 22, 255))
    # lampjes langs de bovenkant
    for i in range(31):
        t = i / 30
        x = w * 0.02 + t * w * 0.96
        y = 26 + 34 * math.sin(math.pi * ((t * 3) % 1))
        gloed(img, x, y, 14, 14, (255, 196, 110), 210, 6)
        ImageDraw.Draw(img).ellipse([x - 3, y - 3, x + 3, y + 3], fill=(255, 240, 200))
    # wand rechts: planken met kaarten en het neonbord
    d = ImageDraw.Draw(img, "RGBA")
    for y in (h * 0.42, h * 0.7):
        d.rectangle([w * 0.81, y, w, y + 8], fill=(92, 56, 36, 255))
        gloed(img, w * 0.9, y - 10, w * 0.1, 16, (255, 170, 90), 60, 12)
    kleuren = ["vuur", "water", "psychisch", "gras", "elektrisch", "draak"]
    for i in range(5):
        k = kaart(TYPES[kleuren[i % 6]][0], kleuren[i % 6], rng.uniform(-4, 4)).resize((44, 62))
        img.alpha_composite(k, (int(w * 0.825 + i * 54), int(h * 0.7 - 64)))
    bord = (int(w * 0.835), 58, int(w * 0.985), int(h * 0.4))
    d.rounded_rectangle(bord, radius=14, fill=(16, 10, 12, 235), outline=(70, 40, 30, 255), width=3)
    cx = (bord[0] + bord[2]) / 2
    neon(img, (cx, bord[1] + 44), "PokeTCG", f("Pacifico-Regular.ttf", 32), (255, 150, 60))
    neon(img, (cx, bord[1] + 92), "Haven", f("Pacifico-Regular.ttf", 36), (255, 150, 60))
    # planten aan de randen: echte blaadjes (gedraaide ellipsen), niet voor het raam
    pl = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    pd = ImageDraw.Draw(pl)
    for _ in range(46):
        x = rng.uniform(0, w * 0.05) if rng.random() < 0.4 else rng.uniform(w * 0.785, w * 0.83)
        y = rng.uniform(h * 0.08, h * 0.7)
        lengte, breedte = rng.uniform(16, 30), rng.uniform(6, 11)
        hoek = rng.uniform(0, math.pi)
        pts = []
        for t in range(0, 360, 15):
            a = math.radians(t)
            px, py = math.cos(a) * lengte, math.sin(a) * breedte
            pts.append((x + px * math.cos(hoek) - py * math.sin(hoek), y + px * math.sin(hoek) + py * math.cos(hoek)))
        groen = meng((30, 54, 30), (76, 104, 46), rng.random())
        pd.polygon(pts, fill=(*groen, 240))
        pd.line([pts[0], pts[len(pts) // 2]], fill=(*meng(groen, (255, 200, 120), 0.25), 200), width=1)
    img.alpha_composite(pl.filter(ImageFilter.GaussianBlur(0.8)))
    # tafel met kaarten
    tafel = verloop(w, int(h * 0.2), [(0, (120, 70, 38)), (1, (46, 26, 18))]).convert("RGBA")
    img.alpha_composite(tafel, (0, int(h * 0.8)))
    gloed(img, w * 0.6, h * 0.82, w * 0.3, 26, (255, 190, 110), 110, 20)
    for _ in range(9):
        t = rng.choice(kleuren)
        k = kaart(TYPES[t][0], t, rng.uniform(-30, 30))
        k = k.resize((int(k.width * 0.55), int(k.height * 0.55)))
        img.alpha_composite(k, (int(rng.uniform(w * 0.36, w * 0.95)), int(rng.uniform(h * 0.83, h * 0.9))))
    if held:
        # de uitgelichte holo-kaart op een standaard, met boosters ernaast
        gloed(img, w * 0.6, h * 0.52, 150, 170, (255, 214, 140), 150, 45)
        for (x, hoek) in ((w * 0.49, -10), (w * 0.67, 9)):
            b = booster(TYPES["vuur" if hoek < 0 else "water"][0], "vuur" if hoek < 0 else "water").rotate(hoek, resample=Image.BICUBIC, expand=True)
            b = b.resize((int(b.width * 0.62), int(b.height * 0.62)))
            img.alpha_composite(b, (int(x - b.width / 2), int(h * 0.86 - b.height)))
        held_k = kaart(TYPES["elektrisch"][0], "elektrisch", 0)
        held_k = held_k.resize((int(held_k.width * 1.05), int(held_k.height * 1.05)))
        holo = Image.new("RGBA", held_k.size, (0, 0, 0, 0))
        hd = ImageDraw.Draw(holo)
        for i in range(7):
            k = [(255, 120, 160), (255, 210, 110), (120, 220, 200), (140, 160, 255)][i % 4]
            hd.polygon([(i * 40 - 60, held_k.height), (i * 40 + 30, 0), (i * 40 + 55, 0), (i * 40 - 35, held_k.height)], fill=(*k, 60))
        holo.putalpha(ImageChops.multiply(holo.getchannel("A"), held_k.getchannel("A")))
        held_k = Image.alpha_composite(held_k, holo)
        hx, hy = int(w * 0.6 - held_k.width / 2), int(h * 0.84 - held_k.height)
        d = ImageDraw.Draw(img, "RGBA")
        d.polygon([(w * 0.6 - 60, h * 0.86), (w * 0.6 + 60, h * 0.86), (w * 0.6 + 40, h * 0.82), (w * 0.6 - 40, h * 0.82)], fill=(70, 42, 28, 255))
        img.alpha_composite(held_k, (hx, hy))
        sd = ImageDraw.Draw(img)
        for _ in range(6):
            sx, sy = rng.uniform(hx - 30, hx + held_k.width + 30), rng.uniform(hy - 20, hy + held_k.height * 0.7)
            ster(sd, sx, sy, rng.choice((5, 7, 9)), (255, 246, 220))
    # bokeh en vignet
    bk = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    bd = ImageDraw.Draw(bk)
    for _ in range(46):
        x = rng.choice((rng.uniform(0, w * 0.3), rng.uniform(w * 0.78, w), rng.uniform(0, w)))
        y = rng.uniform(0, h)
        r = rng.uniform(6, 26)
        k = rng.choice(((255, 196, 110), (255, 150, 80), (255, 226, 170)))
        bd.ellipse([x - r, y - r, x + r, y + r], fill=(*k, rng.randint(30, 90)))
    img.alpha_composite(bk.filter(ImageFilter.GaussianBlur(4)))
    vignet = Image.new("L", (w, h), 0)
    ImageDraw.Draw(vignet).ellipse([-w * 0.15, -h * 0.5, w * 1.15, h * 1.5], fill=255)
    vignet = vignet.filter(ImageFilter.GaussianBlur(90))
    zwart = Image.new("RGBA", (w, h), (8, 4, 6, 255))
    zwart.putalpha(ImageChops.invert(vignet).point(lambda a: int(a * 0.85)))
    img.alpha_composite(zwart)
    return img


# -- de beelden ----------------------------------------------------------------------------


def welkom() -> Path:
    w, h = 1600, 452
    img = scene(w, h)
    paneel = (44, 30, 742, 422)
    glaspaneel(img, paneel)
    d = ImageDraw.Draw(img, "RGBA")
    x = paneel[0] + 40
    embleem(d, x + 26, 86, 26)
    spatietekst(d, (x + 70, 62), "POKETCG HAVEN", f("Poppins-SemiBold.ttf", 22), (250, 246, 240), 5)
    spatietekst(d, (x + 71, 92), "NEDERLAND & BELGIË", f("Poppins-Medium.ttf", 14), GOUD, 3.4)
    titel = f("Poppins-ExtraBold.ttf", 76)
    tekst_verloop(img, (x - 2, 118), "Welkom in de", titel, (255, 255, 255), (238, 226, 214))
    tekst_verloop(img, (x - 2, 196), "Haven!", titel, GOUD_LICHT, (236, 140, 56))
    d = ImageDraw.Draw(img, "RGBA")
    sub = f("Poppins-Medium.ttf", 23)
    d.text((x, 296), "De gezelligste Pokémon TCG-community", font=sub, fill=CREME)
    d.text((x, 328), "van Nederland en België.", font=sub, fill=CREME)
    items = [("mensen", "VERZAMELAARS"), ("kaarten", "RUILEN"), ("ballon", "DISCUSSIES"), ("kalender", "RELEASES")]
    lf = f("Poppins-SemiBold.ttf", 14)
    xx = x
    for i, (ic, label) in enumerate(items):
        icoon(d, ic, xx, 378, 22)
        tx = spatietekst(d, (xx + 32, 380), label, lf, (250, 246, 240), 1.2)
        xx = tx + 20
        if i < len(items) - 1:
            d.line([(xx, 374), (xx, 404)], fill=(118, 98, 92), width=1)
            xx += 20
    pad = UIT / "welkom.png"
    img.convert("RGB").save(pad, optimize=True)
    return pad


def eerste_stappen() -> Path:
    """De eerste stappen als glazen kaarten op een vage versie van de winkel."""
    w, h = 1600, 560
    img = scene(w, h, seed=11, held=False).filter(ImageFilter.GaussianBlur(10))
    img.alpha_composite(Image.new("RGBA", (w, h), (14, 8, 10, 120)))
    d = ImageDraw.Draw(img, "RGBA")
    embleem(d, 82, 70, 22)
    spatietekst(d, (118, 50), "JOUW EERSTE STAPPEN", f("Poppins-SemiBold.ttf", 22), (250, 246, 240), 4)
    spatietekst(d, (119, 78), "IN 3 KLIKKEN WEET JE HOE ALLES WERKT", f("Poppins-Medium.ttf", 14), GOUD, 2.4)
    stappen = [
        ("deur", "Kom binnen", "Eén klik op de knop en de hele community gaat voor je open."),
        ("rol", "Lees de huisregels", "8 korte afspraken, steeds met het waarom erbij."),
        ("kompas", "Volg de tour", "In een paar schermen ken je de belangrijkste plekken."),
        ("ster", "Badge Wegwijs", "Je eerste badge als trainer in de Haven."),
    ]
    kw, gap, y0, kh = 352, 24, 132, 380
    x0 = (w - 4 * kw - 3 * gap) // 2
    tf, uf = f("Poppins-Bold.ttf", 30), f("Poppins-Medium.ttf", 20)
    for i, (ic, titel, uitleg) in enumerate(stappen):
        x = x0 + i * (kw + gap)
        laatste = i == len(stappen) - 1
        glaspaneel(img, (x, y0, x + kw, y0 + kh), 22)
        d = ImageDraw.Draw(img, "RGBA")
        if laatste:
            rand(img, (x, y0, x + kw, y0 + kh), 22, (*GOUD, 220), 3)
        cx = x + kw / 2
        gloed(img, cx, y0 + 112, 70, 70, GOUD, 90 if laatste else 50, 24)
        d = ImageDraw.Draw(img, "RGBA")
        d.ellipse([cx - 56, y0 + 56, cx + 56, y0 + 168], fill=(32, 20, 18, 230), outline=(*GOUD, 255), width=3)
        icoon(d, ic, cx - 26, y0 + 86, 52, GOUD_LICHT if laatste else GOUD)
        if not laatste:
            d.ellipse([x + 22, y0 + 22, x + 62, y0 + 62], fill=GOUD)
            d.text((x + 42, y0 + 43), str(i + 1), font=f("Poppins-Bold.ttf", 22), fill=(40, 22, 14), anchor="mm")
        d.text((cx, y0 + 214), titel, font=tf, fill=(255, 250, 244), anchor="mm")
        regels, regel = [], ""
        for woord in uitleg.split():
            proef = f"{regel} {woord}".strip()
            if d.textlength(proef, font=uf) <= kw - 56:
                regel = proef
            else:
                regels.append(regel)
                regel = woord
        regels.append(regel)
        for j, r in enumerate(regels[:3]):
            d.text((cx, y0 + 262 + j * 30), r, font=uf, fill=(222, 214, 206), anchor="mm")
        if not laatste:
            pijl_x = x + kw + gap / 2
            d.polygon([(pijl_x - 6, y0 + kh / 2 - 10), (pijl_x + 6, y0 + kh / 2), (pijl_x - 6, y0 + kh / 2 + 10)], fill=(*GOUD, 230))
    pad = UIT / "start-stappen.png"
    img.convert("RGB").save(pad, optimize=True)
    return pad


def main() -> None:
    for p in (welkom(), eerste_stappen()):
        print(p.relative_to(UIT.parent.parent))


if __name__ == "__main__":
    main()

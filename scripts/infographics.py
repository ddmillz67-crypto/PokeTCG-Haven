"""Infographics voor de Start-kanalen (inhoud/afbeeldingen/*.png), in dezelfde Pokémon-stijl als de banners.

    python -m scripts.infographics

Ze laten in één oogopslag zien wat de tekst eronder uitlegt: de eerste stappen, de route door
de server, de huisregels, veilig handelen, je trainerskaart en het weekritme.
Net als bij de banners: geen officieel Pokémon-artwork, alleen eigen ontwerp.
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

from scripts.banners import PIXEL, ROOT, TYPES, UIT, blok, donker, energie, font, kaart, licht, meng, omloop, ster

INKT = (24, 30, 52)
GRIJS = (92, 100, 124)
ZAND = (238, 214, 160)
BREED = 1200


# -- bouwstenen ---------------------------------------------------------------------


def achtergrond(hoog: int, type_: str) -> Image.Image:
    """Lichte lucht in pixelstijl met een strook hoog gras onderaan."""
    _kleur, _boven, onder, heuvel, _ = TYPES[type_]
    img = Image.new("RGB", (BREED, hoog))  # RGB, zodat tekenen met alfa echt mengt
    d = ImageDraw.Draw(img, "RGBA")
    top, bodem = licht(onder, 0.55), (252, 250, 244)
    for y in range(0, hoog, PIXEL):
        d.rectangle([0, y, BREED, y + PIXEL], fill=(*meng(top, bodem, min(1, y / (hoog * 0.7))), 255))
    gras_d, gras_l = licht(heuvel, 0.15), licht(heuvel, 0.45)
    for x0 in range(0, BREED, PIXEL * 5):
        y0 = hoog - PIXEL * 4 + (PIXEL if (x0 // (PIXEL * 5)) % 2 else 0)
        for i, h in enumerate((2, 3, 2, 4, 2)):
            for j in range(h):
                blok(d, x0 + i * PIXEL, y0 + (4 - h + j) * PIXEL - PIXEL, gras_l if j == 0 else gras_d)
    return img


def pil(d: ImageDraw.ImageDraw, x: int, y: int, tekst: str, kleur, type_: str | None = None) -> int:
    """Een label-pil zoals in de banners; geeft de rechterkant terug."""
    f = font("Inter-Bold.otf", 18)
    breed = int(d.textlength(tekst, font=f)) + (60 if type_ else 36)
    d.rounded_rectangle([x, y, x + breed, y + 38], radius=19, fill=kleur)
    tx = x + 18
    if type_:
        energie(d, type_, x + 19, y + 19, 14, donker(kleur, 0.1))
        tx = x + 42
    d.text((tx, y + 19), tekst, font=f, fill=(255, 255, 255), anchor="lm")
    return x + breed


def badge(d: ImageDraw.ImageDraw, cx: float, cy: float, r: float, type_: str, nummer: str | None = None) -> None:
    """Een rond badge-embleem met het energie-symbool van het type en een nummer."""
    kleur = TYPES[type_][0]
    d.ellipse([cx - r - 8, cy - r - 4, cx + r + 8, cy + r + 12], fill=(0, 0, 0, 40))
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=kleur, outline=donker(kleur, 0.3), width=5)
    energie(d, type_, cx, cy, r * 0.62, kleur)
    if nummer:
        nr = r * 0.36
        nx, ny = cx - r * 0.72, cy - r * 0.72
        d.ellipse([nx - nr, ny - nr, nx + nr, ny + nr], fill=INKT, outline=(255, 255, 255), width=3)
        d.text((nx, ny), nummer, font=font("InterDisplay-Bold.otf", int(nr * 1.15)), fill=(255, 255, 255), anchor="mm")


def stippelpad(d: ImageDraw.ImageDraw, punten: list[tuple[float, float]], kleur, stap: int = 22) -> None:
    """Een route van pixelblokjes tussen punten, zoals een pad op een kaart."""
    for (x1, y1), (x2, y2) in zip(punten, punten[1:]):
        lengte = math.dist((x1, y1), (x2, y2))
        for i in range(int(lengte // stap) + 1):
            t = i * stap / lengte if lengte else 0
            x, y = x1 + (x2 - x1) * t, y1 + (y2 - y1) * t
            d.rectangle([x - 5, y - 5, x + 5, y + 5], fill=kleur)


def gecentreerd(d: ImageDraw.ImageDraw, cx: float, y: float, tekst: str, f, kleur, max_breed: int, max_regels: int = 2, regelhoogte: int = 26) -> None:
    for i, regel in enumerate(omloop(d, tekst, f, max_breed)[:max_regels]):
        d.text((cx, y + i * regelhoogte), regel, font=f, fill=kleur, anchor="ma")


def opslaan(img: Image.Image, naam: str) -> Path:
    UIT.mkdir(parents=True, exist_ok=True)
    pad = UIT / f"{naam}.png"
    img.convert("RGB").save(pad, optimize=True)
    return pad


# -- infographics ---------------------------------------------------------------------


def stappenstrook(naam: str, label: str, type_: str, stappen: list[tuple[str, str, str]], einde: tuple[str, str] | None = None) -> Path:
    """Een rij genummerde badges op een route: (titel, uitleg, type) per stap, optioneel een beloning aan het eind."""
    hoog = 470
    img = achtergrond(hoog, type_)
    d = ImageDraw.Draw(img, "RGBA")
    pil(d, 48, 36, label, TYPES[type_][0], type_)
    aantal = len(stappen) + (1 if einde else 0)
    marge = 140
    xs = [marge + i * (BREED - 2 * marge) / (aantal - 1) for i in range(aantal)]
    cy = 196
    stippelpad(d, [(x, cy) for x in xs], ZAND)
    tf, uf = font("InterDisplay-Bold.otf", 30), font("Inter-Medium.otf", 21)
    kolom = min(int((BREED - 2 * marge) / (aantal - 1)) - 24, 2 * marge - 20)
    for i, (titel, uitleg, t) in enumerate(stappen):
        badge(d, xs[i], cy, 62, t, str(i + 1))
        gecentreerd(d, xs[i], cy + 88, titel, tf, INKT, kolom, 1)
        gecentreerd(d, xs[i], cy + 132, uitleg, uf, GRIJS, kolom, 3)
    if einde:
        x = xs[-1]
        goud = (255, 200, 60)
        d.ellipse([x - 70, cy - 66, x + 70, cy + 82], fill=(0, 0, 0, 40))
        d.ellipse([x - 66, cy - 66, x + 66, cy + 66], fill=goud, outline=donker(goud, 0.3), width=5)
        ster(d, x, cy, 44, (255, 255, 255), 0.42, 5)
        gecentreerd(d, x, cy + 88, einde[0], tf, INKT, kolom, 1)
        gecentreerd(d, x, cy + 132, einde[1], uf, GRIJS, kolom, 3)
    return opslaan(img, naam)


def tourkaart() -> Path:
    """Een kaart van de server: acht haltes op een slingerende route, van start tot vaste trainer."""
    hoog = 790
    img = achtergrond(hoog, "water")
    d = ImageDraw.Draw(img, "RGBA")
    pil(d, 48, 36, "ROUTE 1  ·  JOUW WEG DOOR DE HAVEN", TYPES["water"][0], "water")
    haltes = [
        ("#start-hier", "Kom binnen", "vuur"),
        ("#regels", "Lees de huisregels", "vechten"),
        ("#rollen", "Kies je rollen", "fee"),
        ("#voorstellen", "Zeg hallo", "gras"),
        ("#pulls", "Deel je eerste pull", "elektrisch"),
        ("#collecties", "Laat je binder zien", "psychisch"),
        ("#release-kalender", "Mis geen release", "draak"),
        ("#giveaways", "Doe gratis mee", "fee"),
    ]
    xs = [170, 457, 743, 1030]
    rij1, rij2 = 236, 546
    pos = [(x, rij1) for x in xs] + [(x, rij2) for x in reversed(xs)]
    bocht = [(xs[-1] + 70 + 40 * math.sin(a), rij1 + (rij2 - rij1) * (1 - math.cos(a)) / 2) for a in [i * math.pi / 10 for i in range(11)]]
    pad = [(60, rij1), *pos[:4], *bocht, *pos[4:], (60, rij2)]
    stippelpad(d, pad, ZAND, 20)
    tf, uf = font("InterDisplay-Bold.otf", 26), font("Inter-Medium.otf", 20)
    for i, ((kanaal, wat, t), (x, y)) in enumerate(zip(haltes, pos)):
        badge(d, x, y, 54, t, str(i + 1))
        gecentreerd(d, x, y + 76, kanaal, tf, INKT, 270, 1)
        gecentreerd(d, x, y + 112, wat, uf, GRIJS, 270, 1)
    # start- en eindvlag
    for (x, y), tekst, kleur in (((60, rij1), "START", TYPES["vuur"][0]), ((60, rij2), "VASTE TRAINER", (230, 170, 30))):
        d.rectangle([x - 3, y - 108, x + 3, y + 8], fill=INKT)
        f = font("Inter-Bold.otf", 16)
        w = int(d.textlength(tekst, font=f)) + 24
        d.rectangle([x + 3, y - 108, x + 3 + w, y - 78], fill=kleur)
        d.text((x + 15, y - 93), tekst, font=f, fill=(255, 255, 255), anchor="lm")
    return opslaan(img, "tour-kaart")


def tegels(naam: str, label: str, type_: str, items: list[tuple[str, str, str]], genummerd: bool = True) -> Path:
    """Tegels met symbool, titel en één regel uitleg; 4 per rij."""
    tw, th, gap = 258, 236, 22
    rijen = (len(items) + 3) // 4
    hoog = 104 + rijen * th + (rijen - 1) * gap + 60
    img = achtergrond(hoog, type_)
    d = ImageDraw.Draw(img, "RGBA")
    pil(d, 48, 36, label, TYPES[type_][0], type_)
    x0 = (BREED - 4 * tw - 3 * gap) // 2
    tf, uf = font("InterDisplay-Bold.otf", 25), font("Inter-Medium.otf", 19)
    for i, (titel, uitleg, t) in enumerate(items):
        x = x0 + (i % 4) * (tw + gap)
        y = 104 + (i // 4) * (th + gap)
        kleur = TYPES[t][0]
        d.rounded_rectangle([x + 4, y + 8, x + tw + 4, y + th + 8], radius=20, fill=(0, 0, 0, 30))
        d.rounded_rectangle([x, y, x + tw, y + th], radius=20, fill=(255, 255, 255), outline=licht(kleur, 0.3), width=3)
        d.rounded_rectangle([x, y, x + tw, y + 14], radius=7, fill=kleur)
        badge(d, x + tw / 2, y + 82, 40, t)
        if genummerd:
            d.ellipse([x + 16, y + 28, x + 56, y + 68], fill=INKT)
            d.text((x + 36, y + 48), str(i + 1), font=font("InterDisplay-Bold.otf", 22), fill=(255, 255, 255), anchor="mm")
        gecentreerd(d, x + tw / 2, y + 140, titel, tf, INKT, tw - 24, 1)
        gecentreerd(d, x + tw / 2, y + 178, uitleg, uf, GRIJS, tw - 28, 2, 24)
    return opslaan(img, naam)


def huisregels() -> Path:
    """De 8 huisregels als tegels: nummer, symbool, titel en het waarom."""
    return tegels(
        "regels-overzicht", "DE CODE VAN EEN GOEDE TRAINER", "vechten",
        [
            ("Wees aardig", "Iedereen begint ergens", "fee"),
            ("Juiste kanaal", "Zo blijft het overzichtelijk", "water"),
            ("Handel in de markt", "Daar zie je de vouches", "metaal"),
            ("Geen namaak", "Vertrouwen is de basis", "vechten"),
            ("Geen spam", "Niemand komt voor reclame", "gras"),
            ("Geen gokken", "Geen betaalde loterijen", "duister"),
            ("Privacy", "Deel geen adressen", "psychisch"),
            ("Regels van Discord", "Minimaal 13 jaar", "draak"),
        ],
    )


def chip(d: ImageDraw.ImageDraw, x: int, y: int, tekst: str, kleur) -> int:
    f = font("Inter-SemiBold.otf", 19)
    w = int(d.textlength(tekst, font=f)) + 32
    d.rounded_rectangle([x, y, x + w, y + 36], radius=18, fill=licht(kleur, 0.75), outline=kleur, width=2)
    d.text((x + w / 2, y + 18), tekst, font=f, fill=donker(kleur, 0.45), anchor="mm")
    return x + w + 10


Rij = tuple[str, "list[tuple[str, str]] | str"]


def profielkaart(
    naam: str, label: str, type_: str, kaarttitel: str, persoon: str, ondertitel: str, avatar: str,
    rijen: list[Rij], stappen: list[tuple[str, str, str]], level: str | None = None,
) -> Path:
    """Een kaart in trainerskaart-stijl links, met genummerde uitleg rechts.

    Een rij is (label, chips) met chips als [(tekst, type)], of (label, tekst) voor gewone tekst.
    """
    hoog = 600
    img = achtergrond(hoog, type_)
    d = ImageDraw.Draw(img, "RGBA")
    kleur = TYPES[type_][0]
    pil(d, 48, 36, label, kleur, type_)
    kx, ky, kw, kh = 48, 100, 700, 440
    geel = (255, 214, 92)
    d.rounded_rectangle([kx + 6, ky + 10, kx + kw + 6, ky + kh + 10], radius=26, fill=(0, 0, 0, 40))
    d.rounded_rectangle([kx, ky, kx + kw, ky + kh], radius=26, fill=geel)
    d.rounded_rectangle([kx + 14, ky + 14, kx + kw - 14, ky + kh - 14], radius=18, fill=(255, 252, 244))
    d.rounded_rectangle([kx + 14, ky + 14, kx + kw - 14, ky + 74], radius=18, fill=kleur)
    d.rectangle([kx + 14, ky + 50, kx + kw - 14, ky + 74], fill=kleur)
    helder = 0.299 * kleur[0] + 0.587 * kleur[1] + 0.114 * kleur[2] > 170
    kop = donker(kleur, 0.75) if helder else (255, 255, 255)
    d.text((kx + 40, ky + 44), kaarttitel, font=font("InterDisplay-Bold.otf", 28), fill=kop, anchor="lm")
    d.text((kx + kw - 40, ky + 44), "PokeTCG Haven", font=font("Inter-SemiBold.otf", 19), fill=kop, anchor="rm")
    badge(d, kx + 100, ky + 160, 52, avatar)
    d.text((kx + 172, ky + 128), persoon, font=font("InterDisplay-Bold.otf", 32), fill=INKT)
    d.text((kx + 172, ky + 170), ondertitel, font=font("Inter-Medium.otf", 19), fill=GRIJS)
    lf, tf_rij = font("Inter-Bold.otf", 18), font("Inter-SemiBold.otf", 20)
    y = ky + 236
    for rlabel, waarde in rijen:
        d.text((kx + 40, y + 18), rlabel, font=lf, fill=GRIJS, anchor="lm")
        if isinstance(waarde, str):
            d.text((kx + 216, y + 18), waarde, font=tf_rij, fill=INKT, anchor="lm")
        else:
            x = kx + 216
            for tekst, t in waarde:
                x = chip(d, x, y, tekst, TYPES[t][0])
        y += 52
    if level:
        d.text((kx + 40, y + 18), "LEVEL", font=lf, fill=GRIJS, anchor="lm")
        bx, bw = kx + 216, 280
        d.rounded_rectangle([bx, y + 6, bx + bw, y + 30], radius=12, fill=(236, 232, 244))
        d.rounded_rectangle([bx, y + 6, bx + int(bw * 0.35), y + 30], radius=12, fill=TYPES["elektrisch"][0])
        d.text((bx + bw + 14, y + 18), level, font=font("Inter-SemiBold.otf", 18), fill=INKT, anchor="lm")
    rx = 800
    tf, uf = font("InterDisplay-Bold.otf", 25), font("Inter-Medium.otf", 19)
    for i, (titel, uitleg, t) in enumerate(stappen):
        y = 120 + i * 140
        badge(d, rx + 34, y + 40, 32, t, None)
        d.ellipse([rx + 4, y + 4, rx + 32, y + 32], fill=INKT)
        d.text((rx + 18, y + 18), str(i + 1), font=font("InterDisplay-Bold.otf", 18), fill=(255, 255, 255), anchor="mm")
        d.text((rx + 84, y + 10), titel, font=tf, fill=INKT)
        for j, regel in enumerate(omloop(d, uitleg, uf, 300)[:2]):
            d.text((rx + 84, y + 48 + j * 24), regel, font=uf, fill=GRIJS)
    return opslaan(img, naam)


def trainerskaart() -> Path:
    """Een voorbeeld-trainerskaart: zo zien anderen wat je verzamelt, waar je woont en wat je volgt."""
    return profielkaart(
        "rollen-kaart", "ZO ZIET JOUW TRAINERSKAART ERUIT", "fee", "TRAINERSKAART", "Trainer Sam", "Lid sinds vandaag", "vuur",
        [
            ("VERZAMELT", [("Sealed", "metaal"), ("Singles", "water"), ("Japans", "vechten")]),
            ("REGIO", [("Zuid-Nederland", "gras")]),
            ("MELDINGEN", [("Releases", "draak"), ("Giveaways", "fee")]),
        ],
        [
            ("Kies wat je verzamelt", "Anderen zien meteen waar je mee bezig bent", "metaal"),
            ("Kies je regio", "Voor de winkel-radar bij jou in de buurt", "gras"),
            ("Kies je meldingen", "Alleen pings die jij wilt, nooit @everyone", "draak"),
        ],
        level="Nieuwe Trainer",
    )


def voorstelkaart() -> Path:
    """Een voorbeeld-voorstelling, met hoe het daarna verdergaat."""
    return profielkaart(
        "voorstellen-kaart", "ZO STEL JE JE VOOR", "gras", "HALLO, IK BEN SAM!", "Sam", "Verzamelt sinds 2004", "psychisch",
        [
            ("FAVORIET", [("Gengar", "psychisch")]),
            ("VERZAMELT", [("Japanse sets", "vechten"), ("Alles met Gengar", "psychisch")]),
            ("PRONKSTUK", "Gengar VMAX alt art"),
            ("ZOEKT NOG", "Gengar uit Fusion Strike"),
        ],
        [
            ("Plaats je voorstelling", "Eén bericht, gebruik gerust het voorbeeld", "gras"),
            ("Er opent een thread", "Daar kan iedereen je welkom heten", "water"),
            ("Binnen 24 uur hallo", "Een Haven Helper zegt je persoonlijk gedag", "fee"),
        ],
    )


def collectietags() -> Path:
    return tegels(
        "collecties-tags", "KIES DE TAG VAN JE COLLECTIE", "psychisch",
        [
            ("Binder", "Je mooiste binderpagina's", "psychisch"),
            ("Sealed", "Boxen, ETB's en displays", "metaal"),
            ("Graded", "PSA, CGC en BGS", "draak"),
            ("Japans", "Japanse sets en promo's", "vechten"),
        ],
        genummerd=False,
    )


def mijlpaalladder() -> Path:
    """De mijlpaal-ladder als oplopende trap, rechtstreeks uit haven/mijlpalen.py."""
    from haven.mijlpalen import LADDER, getal

    hoog = 660
    img = achtergrond(hoog, "fee")
    d = ImageDraw.Draw(img, "RGBA")
    pil(d, 48, 36, "DE MIJLPAAL-LADDER  ·  ALTIJD GRATIS MEEDOEN", TYPES["fee"][0], "fee")
    n = len(LADDER)
    kw, gap = 148, 16
    x0 = (BREED - n * kw - (n - 1) * gap) // 2
    bodem = hoog - 64
    tf, pf = font("InterDisplay-Bold.otf", 26), font("Inter-SemiBold.otf", 17)
    goud = (255, 200, 60)
    for i, (grens, prijs) in enumerate(LADDER):
        x = x0 + i * (kw + gap)
        hoogte = 236 + i * 38
        y = bodem - hoogte
        box = "box" in prijs.lower()
        kleur = goud if box else TYPES["fee"][0]
        d.rounded_rectangle([x + 4, y + 8, x + kw + 4, bodem + 8], radius=16, fill=(0, 0, 0, 30))
        d.rounded_rectangle([x, y, x + kw, bodem], radius=16, fill=(255, 255, 255), outline=kleur, width=3)
        d.rounded_rectangle([x, y, x + kw, y + 12], radius=6, fill=kleur)
        d.text((x + kw / 2, y + 44), getal(grens), font=tf, fill=INKT, anchor="mm")
        d.text((x + kw / 2, y + 72), "leden", font=pf, fill=GRIJS, anchor="mm")
        cy = y + 124
        if box:
            d.ellipse([x + kw / 2 - 34, cy - 34, x + kw / 2 + 34, cy + 34], fill=goud, outline=donker(goud, 0.3), width=4)
            ster(d, x + kw / 2, cy, 22, (255, 255, 255), 0.42, 5)
        else:
            badge(d, x + kw / 2, cy, 34, "fee")
        gecentreerd(d, x + kw / 2, cy + 50, prijs, pf, INKT, kw - 20, 3, 22)
    return opslaan(img, "mijlpalen")


def weekritme() -> Path:
    """Het weekritme: vaste momenten op maandag, woensdag, vrijdag en zondag."""
    hoog = 470
    img = achtergrond(hoog, "elektrisch")
    d = ImageDraw.Draw(img, "RGBA")
    pil(d, 48, 36, "ELKE WEEK IN DE HAVEN", TYPES["elektrisch"][0], "elektrisch")
    dagen = [
        ("MA", "Binder Monday", "Laat je binder zien", "psychisch"),
        ("DI", None, None, None),
        ("WO", "Vraag van de week", "19:00 in #chat", "gras"),
        ("DO", None, None, None),
        ("VR", "Pull van de Week", "18:00 de winnaar", "elektrisch"),
        ("ZA", None, None, None),
        ("ZO", "Pack-avond", "20:00 op de stage", "vuur"),
    ]
    kw, gap = 148, 14
    x0 = (BREED - 7 * kw - 6 * gap) // 2
    y, kh = 104, 316
    tf, uf = font("InterDisplay-Bold.otf", 22), font("Inter-Medium.otf", 17)
    for i, (dag, titel, uitleg, t) in enumerate(dagen):
        x = x0 + i * (kw + gap)
        if titel:
            kleur = TYPES[t][0]
            d.rounded_rectangle([x + 4, y + 8, x + kw + 4, y + kh + 8], radius=18, fill=(0, 0, 0, 30))
            d.rounded_rectangle([x, y, x + kw, y + kh], radius=18, fill=(255, 255, 255), outline=kleur, width=3)
            d.rounded_rectangle([x, y, x + kw, y + 56], radius=18, fill=kleur)
            d.rectangle([x, y + 38, x + kw, y + 56], fill=kleur)
            d.text((x + kw / 2, y + 28), dag, font=font("InterDisplay-Bold.otf", 28), fill=(255, 255, 255), anchor="mm")
            badge(d, x + kw / 2, y + 120, 40, t)
            gecentreerd(d, x + kw / 2, y + 182, titel, tf, INKT, kw - 16, 2, 26)
            gecentreerd(d, x + kw / 2, y + 246, uitleg, uf, GRIJS, kw - 16, 2, 22)
        else:
            d.rounded_rectangle([x, y, x + kw, y + kh], radius=18, fill=(255, 255, 255, 140), outline=(214, 214, 224), width=2)
            d.text((x + kw / 2, y + 28), dag, font=font("InterDisplay-Bold.otf", 28), fill=(170, 174, 190), anchor="mm")
            gecentreerd(d, x + kw / 2, y + 150, "Gewoon gezellig kletsen", uf, (150, 156, 176), kw - 24, 3, 22)
    return opslaan(img, "weekritme")


def levelpad() -> Path:
    """De levelrollen als oplopend pad, rechtstreeks uit haven/levels.py, met wat je bij elk level vrijspeelt."""
    from haven.levels import GIVEAWAY_LEVEL, LEVEL_ROLLEN

    hoog = 480
    img = achtergrond(hoog, "gras")
    d = ImageDraw.Draw(img, "RGBA")
    pil(d, 48, 36, "PRAAT MEE, STIJG IN LEVEL", TYPES["gras"][0], "gras")
    rollen = sorted(LEVEL_ROLLEN)
    typen = ["gras", "water", "elektrisch", "vuur", "draak"]
    n = len(rollen)
    marge = 130
    xs = [marge + i * (BREED - 2 * marge) / (n - 1) for i in range(n)]
    ys = [300 - i * 34 for i in range(n)]
    stippelpad(d, list(zip(xs, ys)), ZAND)
    tf, uf, lf = font("InterDisplay-Bold.otf", 25), font("Inter-Medium.otf", 19), font("Inter-Bold.otf", 17)
    for i, ((lvl, naam), x, y) in enumerate(zip(rollen, xs, ys)):
        t = typen[i % len(typen)]
        badge(d, x, y, 52, t)
        lbl = f"LEVEL {lvl}"
        w = int(d.textlength(lbl, font=lf)) + 24
        d.rounded_rectangle([x - w / 2, y - 92, x + w / 2, y - 64], radius=14, fill=INKT)
        d.text((x, y - 78), lbl, font=lf, fill=(255, 255, 255), anchor="mm")
        gecentreerd(d, x, y + 72, naam, tf, INKT, 220, 1)
    # wat je vrijspeelt, onder de rol waar het bij hoort
    beloning = {
        "Nieuwe Trainer": f"Level {GIVEAWAY_LEVEL}: giveaways",
        "Trainer": "Posten in de markt",
        "Ace Trainer": "Eigen naamkleur",
        "Gym Leader": "Apart in de ledenlijst",
        "Haven Legende": "Maand Sniper gratis",
    }
    for (lvl, naam), x, y in zip(rollen, xs, ys):
        if naam in beloning:
            gecentreerd(d, x, y + 108, beloning[naam], uf, GRIJS, 220, 1)
    return opslaan(img, "levels")


def advertentie() -> Path:
    """Een voorbeeld-advertentie in de markt: tag, foto's met naam en datum, prijs en conditie."""
    hoog = 600
    img = achtergrond(hoog, "metaal")
    d = ImageDraw.Draw(img, "RGBA")
    kleur = TYPES["metaal"][0]
    pil(d, 48, 36, "ZO ZIET EEN GOEDE ADVERTENTIE ERUIT", kleur, "metaal")
    px, py, pw, ph = 48, 100, 1104, 452
    d.rounded_rectangle([px + 6, py + 10, px + pw + 6, py + ph + 10], radius=24, fill=(0, 0, 0, 36))
    d.rounded_rectangle([px, py, px + pw, py + ph], radius=24, fill=(255, 255, 255), outline=licht(kleur, 0.3), width=3)
    x = chip(d, px + 32, py + 28, "Te koop", TYPES["gras"][0])
    d.text((x + 8, py + 46), "Charizard ex SIR · Obsidian Flames 223", font=font("InterDisplay-Bold.otf", 30), fill=INKT, anchor="lm")
    # twee foto's: voor- en achterkant met een briefje
    for i, (soort, label) in enumerate((("vuur", "Voorkant"), ("water", "Achterkant"))):
        fx = px + 40 + i * 200
        fy = py + 100
        d.rounded_rectangle([fx, fy, fx + 180, fy + 300], radius=16, fill=(236, 240, 246))
        k = kaart(TYPES[soort][0], soort, 0).resize((128, 178))
        img.paste(k, (int(fx + 26), int(fy + 24)), k)
        d.rounded_rectangle([fx + 22, fy + 214, fx + 158, fy + 260], radius=6, fill=(255, 250, 220), outline=(220, 200, 140))
        d.text((fx + 90, fy + 229), "Sam", font=font("Inter-Bold.otf", 16), fill=INKT, anchor="mm")
        d.text((fx + 90, fy + 248), "16-10", font=font("Inter-Medium.otf", 15), fill=GRIJS, anchor="mm")
        d.text((fx + 90, fy + 284), label, font=font("Inter-SemiBold.otf", 17), fill=GRIJS, anchor="mm")
    lf, vf = font("Inter-Bold.otf", 18), font("Inter-SemiBold.otf", 22)
    rijen = [
        ("PRIJS", "€ 85 of ruil tegen een SIR"),
        ("CONDITIE", "Near Mint, uit de pack in de sleeve"),
        ("VERZENDING", "Aangetekend, track & trace in de thread"),
        ("VOUCHES", "12 · Verified Trader"),
    ]
    rx = px + 470
    for i, (label, waarde) in enumerate(rijen):
        y = py + 120 + i * 74
        d.text((rx, y), label, font=lf, fill=GRIJS)
        d.text((rx, y + 26), waarde, font=vf, fill=INKT)
    return opslaan(img, "advertentie")



def alerttijdlijn() -> Path:
    """Gratis en Sniper naast elkaar op een tijdlijn van 0 tot 10 minuten."""
    hoog = 470
    img = achtergrond(hoog, "gras")
    d = ImageDraw.Draw(img, "RGBA")
    pil(d, 48, 36, "WANNEER ZIE JIJ EEN RESTOCK?", TYPES["gras"][0], "gras")
    x0, x1 = 490, 1110
    as_y = 360
    d.line([(x0, as_y), (x1, as_y)], fill=GRIJS, width=3)
    lf = font("Inter-SemiBold.otf", 18)
    for m in range(0, 11, 2):
        x = x0 + (x1 - x0) * m / 10
        d.line([(x, as_y - 8), (x, as_y + 8)], fill=GRIJS, width=3)
        d.text((x, as_y + 28), f"{m} min", font=lf, fill=GRIJS, anchor="mm")
    tf, uf = font("InterDisplay-Bold.otf", 28), font("Inter-Medium.otf", 19)
    banen = [
        (150, "Haven Sniper", "Direct, met persoonlijke pings", "elektrisch", 0),
        (262, "Gratis", "In #restocks, iets later", "gras", 10),
    ]
    for y, naam, uitleg, t, minuut in banen:
        kleur = TYPES[t][0]
        badge(d, 104, y, 40, t)
        d.text((160, y - 18), naam, font=tf, fill=INKT)
        d.text((160, y + 18), uitleg, font=uf, fill=GRIJS)
        d.line([(x0, y), (x1, y)], fill=(220, 222, 232), width=2)
        x = x0 + (x1 - x0) * minuut / 10
        if minuut:
            for xx in range(x0, int(x) - 30, 22):
                d.rectangle([xx, y - 4, xx + 10, y + 4], fill=licht(kleur, 0.5))
        d.ellipse([x - 26, y - 26, x + 26, y + 26], fill=kleur, outline=donker(kleur, 0.3), width=4)
        ster(d, x, y, 16, (255, 255, 255), 0.42, 5)
    # de voorsprong
    xa, xb = x0, x1
    d.rounded_rectangle([(xa + xb) / 2 - 130, 190, (xa + xb) / 2 + 130, 224], radius=17, fill=TYPES["elektrisch"][0])
    d.text(((xa + xb) / 2, 207), "10 minuten voorsprong", font=font("Inter-Bold.otf", 18), fill=INKT, anchor="mm")
    return opslaan(img, "restocks-tijdlijn")


def main() -> None:
    paden = [
        stappenstrook(
            "start-stappen", "JOUW EERSTE STAPPEN", "vuur",
            [
                ("Kom binnen", "Eén klik en je ziet de hele community", "vuur"),
                ("Huisregels", "8 korte afspraken, met het waarom erbij", "vechten"),
                ("Server-tour", "In een paar schermen weet je alles", "water"),
            ],
            ("Badge Wegwijs", "Je eerste badge als trainer in de Haven"),
        ),
        stappenstrook(
            "veilig-handelen", "VEILIG HANDELEN IN 4 STAPPEN", "metaal",
            [
                ("Check vouches", "En of iemand Verified Trader is", "metaal"),
                ("Vraag een foto", "Met naam van de verkoper en de datum", "water"),
                ("Betaal veilig", "Een onbekende nooit zonder kopersbescherming", "vechten"),
                ("Geef een vouch", "Deal rond? Gebruik /vouch", "gras"),
            ],
        ),
        tourkaart(),
        huisregels(),
        trainerskaart(),
        weekritme(),
        voorstelkaart(),
        stappenstrook(
            "pulls-flow", "VAN PULL TOT PULL VAN DE WEEK", "elektrisch",
            [
                ("Deel je foto", "Er opent meteen een thread om over te praten", "elektrisch"),
                ("Geef sterren", "Een ster bij de pulls die jij het mooist vindt", "fee"),
                ("Vrijdag 18:00", "De pull met de meeste sterren wint", "vuur"),
            ],
            ("Pull van de Week", "Een eigen rol en een shout-out"),
        ),
        collectietags(),
        stappenstrook(
            "giveaway-meedoen", "ZO DOE JE MEE  ·  GRATIS", "fee",
            [
                ("Klik Doe mee", "Bij de giveaway in dit kanaal", "fee"),
                ("De kennisvraag", "Een vraag over de Pokémon TCG", "water"),
                ("Doe een schatting", "Dat is de schiftingsvraag", "psychisch"),
            ],
            ("Beste schatting wint", "Van iedereen met het goede antwoord"),
        ),
        mijlpaalladder(),
        levelpad(),
        advertentie(),
        tegels(
            "hulp-tags", "KIES DE TAG VAN JE VRAAG", "water",
            [
                ("Waarde", "Wat is mijn kaart waard?", "draak"),
                ("Echt of nep", "Klopt deze kaart wel?", "vechten"),
                ("Beginner", "Een Haven Helper helpt je", "gras"),
                ("Opgelost", "Typ /opgelost als je antwoord hebt", "water"),
            ],
            genummerd=False,
        ),
        stappenstrook(
            "radar-flow", "ZO WERKT DE WINKEL-RADAR", "psychisch",
            [
                ("Zie je voorraad?", "In een winkel bij jou in de buurt", "psychisch"),
                ("Meld het", "Met /meld en een foto van het schap", "gras"),
                ("Sniper direct", "Haven Sniper-leden zien het meteen", "elektrisch"),
            ],
            ("Na 10 minuten", "Iedereen, met een ping voor jouw regio"),
        ),
        stappenstrook(
            "releasedag", "ZO GAAT EEN RELEASE IN DE HAVEN", "draak",
            [
                ("Aankondiging", "Datum, winkels en limiet, met een ping", "draak"),
                ("Releasedraad", "Tips: wie pakt vroeg uit en hoe lang is de rij", "water"),
                ("Releasedag", "Op jacht in de winkels en online", "vuur"),
            ],
            ("Releaseavond", "20:00 samen uitpakken op de stage"),
        ),
        alerttijdlijn(),
        stappenstrook(
            "gescoord-flow", "ZO KOM JE IN #SUCCESS", "draak",
            [
                ("Een alert", "Uit #restocks of de winkel-radar", "gras"),
                ("Gekocht!", "Je hebt hem te pakken", "elektrisch"),
                ("Klik Gescoord!", "De knop onder de alert", "vuur"),
            ],
            ("In #success", "Iedereen ziet dat samen zoeken werkt"),
        ),
    ]
    for p in paden:
        print(p.relative_to(ROOT))


if __name__ == "__main__":
    main()

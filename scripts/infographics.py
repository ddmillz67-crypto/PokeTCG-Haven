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

from scripts.banners import PIXEL, ROOT, TYPES, UIT, blok, donker, energie, font, licht, meng, omloop, ster

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
    kolom = int((BREED - 2 * marge) / (aantal - 1)) - 24
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


def huisregels() -> Path:
    """De 8 huisregels als tegels: nummer, symbool, titel en het waarom."""
    hoog = 640
    img = achtergrond(hoog, "vechten")
    d = ImageDraw.Draw(img, "RGBA")
    pil(d, 48, 36, "DE CODE VAN EEN GOEDE TRAINER", TYPES["vechten"][0], "vechten")
    regels = [
        ("Wees aardig", "Iedereen begint ergens", "fee"),
        ("Juiste kanaal", "Zo blijft het overzichtelijk", "water"),
        ("Handel in de markt", "Daar zie je de vouches", "metaal"),
        ("Geen namaak", "Vertrouwen is de basis", "vechten"),
        ("Geen spam", "Niemand komt voor reclame", "gras"),
        ("Geen gokken", "Geen betaalde loterijen", "duister"),
        ("Privacy", "Deel geen adressen", "psychisch"),
        ("Regels van Discord", "Minimaal 13 jaar", "draak"),
    ]
    tw, th, gap = 258, 236, 22
    x0 = (BREED - 4 * tw - 3 * gap) // 2
    tf, uf = font("InterDisplay-Bold.otf", 25), font("Inter-Medium.otf", 19)
    for i, (titel, waarom, t) in enumerate(regels):
        x = x0 + (i % 4) * (tw + gap)
        y = 104 + (i // 4) * (th + gap)
        kleur = TYPES[t][0]
        d.rounded_rectangle([x + 4, y + 8, x + tw + 4, y + th + 8], radius=20, fill=(0, 0, 0, 30))
        d.rounded_rectangle([x, y, x + tw, y + th], radius=20, fill=(255, 255, 255), outline=licht(kleur, 0.3), width=3)
        d.rounded_rectangle([x, y, x + tw, y + 14], radius=7, fill=kleur)
        badge(d, x + tw / 2, y + 82, 40, t)
        d.ellipse([x + 16, y + 28, x + 56, y + 68], fill=INKT)
        d.text((x + 36, y + 48), str(i + 1), font=font("InterDisplay-Bold.otf", 22), fill=(255, 255, 255), anchor="mm")
        gecentreerd(d, x + tw / 2, y + 140, titel, tf, INKT, tw - 24, 1)
        gecentreerd(d, x + tw / 2, y + 178, waarom, uf, GRIJS, tw - 28, 2, 24)
    return opslaan(img, "regels-overzicht")


def chip(d: ImageDraw.ImageDraw, x: int, y: int, tekst: str, kleur) -> int:
    f = font("Inter-SemiBold.otf", 19)
    w = int(d.textlength(tekst, font=f)) + 32
    d.rounded_rectangle([x, y, x + w, y + 36], radius=18, fill=licht(kleur, 0.75), outline=kleur, width=2)
    d.text((x + w / 2, y + 18), tekst, font=f, fill=donker(kleur, 0.45), anchor="mm")
    return x + w + 10


def trainerskaart() -> Path:
    """Een voorbeeld-trainerskaart: zo zien anderen wat je verzamelt, waar je woont en wat je volgt."""
    hoog = 600
    img = achtergrond(hoog, "fee")
    d = ImageDraw.Draw(img, "RGBA")
    pil(d, 48, 36, "ZO ZIET JOUW TRAINERSKAART ERUIT", TYPES["fee"][0], "fee")
    # de kaart
    kx, ky, kw, kh = 48, 100, 700, 440
    geel = (255, 214, 92)
    d.rounded_rectangle([kx + 6, ky + 10, kx + kw + 6, ky + kh + 10], radius=26, fill=(0, 0, 0, 40))
    d.rounded_rectangle([kx, ky, kx + kw, ky + kh], radius=26, fill=geel)
    d.rounded_rectangle([kx + 14, ky + 14, kx + kw - 14, ky + kh - 14], radius=18, fill=(255, 252, 244))
    d.rounded_rectangle([kx + 14, ky + 14, kx + kw - 14, ky + 74], radius=18, fill=TYPES["fee"][0])
    d.rectangle([kx + 14, ky + 50, kx + kw - 14, ky + 74], fill=TYPES["fee"][0])
    d.text((kx + 40, ky + 44), "TRAINERSKAART", font=font("InterDisplay-Bold.otf", 28), fill=(255, 255, 255), anchor="lm")
    d.text((kx + kw - 40, ky + 44), "PokeTCG Haven", font=font("Inter-SemiBold.otf", 19), fill=(255, 255, 255), anchor="rm")
    badge(d, kx + 100, ky + 160, 52, "vuur")
    d.text((kx + 172, ky + 128), "Trainer Sam", font=font("InterDisplay-Bold.otf", 32), fill=INKT)
    d.text((kx + 172, ky + 170), "Lid sinds vandaag", font=font("Inter-Medium.otf", 19), fill=GRIJS)
    lf = font("Inter-Bold.otf", 18)
    rijen = [
        ("VERZAMELT", [("Sealed", "metaal"), ("Singles", "water"), ("Japans", "vechten")]),
        ("REGIO", [("Zuid-Nederland", "gras")]),
        ("MELDINGEN", [("Releases", "draak"), ("Giveaways", "fee")]),
    ]
    y = ky + 236
    for label, chips in rijen:
        d.text((kx + 40, y + 18), label, font=lf, fill=GRIJS, anchor="lm")
        x = kx + 196
        for tekst, t in chips:
            x = chip(d, x, y, tekst, TYPES[t][0])
        y += 52
    # level-balk
    d.text((kx + 40, y + 18), "LEVEL", font=lf, fill=GRIJS, anchor="lm")
    bx, bw = kx + 196, 300
    d.rounded_rectangle([bx, y + 6, bx + bw, y + 30], radius=12, fill=(236, 232, 244))
    d.rounded_rectangle([bx, y + 6, bx + int(bw * 0.35), y + 30], radius=12, fill=TYPES["elektrisch"][0])
    d.text((bx + bw + 14, y + 18), "Nieuwe Trainer", font=font("Inter-SemiBold.otf", 18), fill=INKT, anchor="lm")
    # uitleg rechts
    rx = 800
    stappen = [
        ("1", "Kies wat je verzamelt", "Anderen zien meteen waar je mee bezig bent", "metaal"),
        ("2", "Kies je regio", "Voor de winkel-radar bij jou in de buurt", "gras"),
        ("3", "Kies je meldingen", "Alleen pings die jij wilt, nooit @everyone", "draak"),
    ]
    tf, uf = font("InterDisplay-Bold.otf", 25), font("Inter-Medium.otf", 19)
    for i, (nr, titel, uitleg, t) in enumerate(stappen):
        y = 120 + i * 140
        badge(d, rx + 34, y + 40, 32, t, None)
        d.ellipse([rx + 4, y + 4, rx + 32, y + 32], fill=INKT)
        d.text((rx + 18, y + 18), nr, font=font("InterDisplay-Bold.otf", 18), fill=(255, 255, 255), anchor="mm")
        d.text((rx + 84, y + 10), titel, font=tf, fill=INKT)
        for j, regel in enumerate(omloop(d, uitleg, uf, 300)[:2]):
            d.text((rx + 84, y + 48 + j * 24), regel, font=uf, fill=GRIJS)
    return opslaan(img, "rollen-kaart")


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
    ]
    for p in paden:
        print(p.relative_to(ROOT))


if __name__ == "__main__":
    main()

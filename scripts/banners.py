"""Maakt de banners en het logo voor de embeds (inhoud/afbeeldingen/*.png).

    python -m scripts.banners

Eigen ontwerp in de huisstijl: geen Pokémon-artwork of -logo's (merkrecht).
Lettertype: Inter (SIL Open Font License).
"""

from __future__ import annotations

import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
UIT = ROOT / "inhoud" / "afbeeldingen"
FONTS = Path("/usr/share/fonts/opentype/inter")

BREED, HOOG = 1200, 420
NAVY = (12, 17, 33)

KLEUREN = {
    "merk": (30, 111, 217),
    "release": (247, 201, 72),
    "alert": (46, 204, 113),
    "premium": (142, 68, 173),
    "regels": (231, 76, 60),
    "community": (255, 138, 61),
}

# naam, titel, ondertitel, soort
BANNERS = [
    ("welkom", "Welkom in de Haven", "De gezelligste Pokémon TCG-community van Nederland en België", "community"),
    ("regels", "De huisregels", "Kort, duidelijk en met uitleg waarom", "regels"),
    ("tour", "Jouw route door de server", "In een paar klikken helemaal wegwijs", "merk"),
    ("aankondigingen", "Aankondigingen", "Nieuws, events, winnaars en mijlpalen", "merk"),
    ("rollen", "Kies je rollen", "Jij bepaalt wat je ziet en waar je een melding van krijgt", "community"),
    ("voorstellen", "Stel je voor", "Binnen 24 uur zegt een Haven Helper hallo", "community"),
    ("pulls", "Laat je pulls zien", "Elke vrijdag kiezen we de Pull van de Week", "community"),
    ("collecties", "Jouw collectie", "Binders, sealed, graded en Japans", "community"),
    ("giveaways", "Giveaways", "Bij elke mijlpaal een prijs. Meedoen is altijd gratis", "community"),
    ("chat", "De huiskamer", "Kletsen over kaarten, sets en je laatste aankoop", "community"),
    ("markt", "Veilig handelen", "Kopen, verkopen en ruilen met vouches", "merk"),
    ("hulp", "Vragen & hulp", "Geen vraag is te klein", "merk"),
    ("radar", "Winkel-radar", "Samen zien we meer dan elke bot", "alert"),
    ("releases", "Releasekalender", "Elke release in Nederland en België", "release"),
    ("restocks", "Restock-alerts", "Weer op voorraad? Dan zie je het hier", "alert"),
    ("success", "Gescoord!", "De successen van onze leden", "alert"),
    ("store", "PokeTCG Haven Store", "Extra's voor wie sneller wil", "premium"),
    ("sniper", "Haven Sniper", "Mis nooit meer een drop", "alert"),
    ("elite", "Haven Elite", "Voor de echte verzamelaar", "premium"),
    ("groupbuys", "Group buys", "Samen inkopen tegen kostprijs", "premium"),
    ("grading", "Grading-service", "Samen naar PSA en CGC", "premium"),
    ("partners", "Partnerwinkels", "Steun je lokale kaartwinkel", "merk"),
    ("tickets", "Hulp nodig?", "Open een ticket, we helpen je graag", "merk"),
]


def font(naam: str, grootte: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / naam), grootte)


def meng(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def achtergrond(kleur) -> Image.Image:
    img = Image.new("RGB", (BREED, HOOG), NAVY)
    px = img.load()
    for x in range(BREED):
        for y in range(0, HOOG, 1):
            # diagonale gloed vanaf rechtsboven
            d = math.hypot(x - BREED * 0.85, y - HOOG * 0.1) / (BREED * 0.9)
            t = max(0.0, 1.0 - d) ** 1.6 * 0.55
            px[x, y] = meng(NAVY, kleur, t)
    return img


def stippen(img: Image.Image, kleur) -> None:
    laag = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(laag)
    for x in range(20, BREED, 28):
        for y in range(20, HOOG, 28):
            afstand = math.hypot(x - BREED * 0.8, y - HOOG * 0.5) / BREED
            alfa = int(max(0, 40 - afstand * 60))
            if alfa > 0:
                d.ellipse([x - 1.5, y - 1.5, x + 1.5, y + 1.5], fill=(*kleur, alfa))
    img.paste(laag, (0, 0), laag)


def kaart(kleur, hoek: float, schaal: float = 1.0) -> Image.Image:
    """Een gestileerde verzamelkaart (geen echte kaart): afgeronde rechthoek met holo-glans."""
    w, h = int(190 * schaal), int(265 * schaal)
    k = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(k)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=int(16 * schaal), fill=(245, 246, 250, 255))
    binnen = [int(9 * schaal), int(9 * schaal), w - int(10 * schaal), h - int(10 * schaal)]
    grad = Image.new("RGBA", (w, h))
    gd = ImageDraw.Draw(grad)
    for y in range(h):
        gd.line([(0, y), (w, y)], fill=(*meng(meng(kleur, (255, 255, 255), 0.25), NAVY, y / h * 0.55), 255))
    masker = Image.new("L", (w, h), 0)
    ImageDraw.Draw(masker).rounded_rectangle(binnen, radius=int(10 * schaal), fill=255)
    k.paste(grad, (0, 0), masker)
    # kader voor "artwork" en tekstregels
    d.rounded_rectangle([int(22 * schaal), int(30 * schaal), w - int(22 * schaal), int(150 * schaal)], radius=int(8 * schaal), outline=(255, 255, 255, 170), width=max(1, int(2 * schaal)))
    for i, breedte in enumerate((0.7, 0.55, 0.62)):
        y = int((172 + i * 22) * schaal)
        d.rounded_rectangle([int(24 * schaal), y, int(24 * schaal + (w - 48 * schaal) * breedte), y + int(8 * schaal)], radius=4, fill=(255, 255, 255, 120))
    # holo-glans
    glans = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(glans).polygon([(w * 0.15, h), (w * 0.55, 0), (w * 0.8, 0), (w * 0.4, h)], fill=(255, 255, 255, 55))
    glans.putalpha(Image.composite(glans.getchannel("A"), Image.new("L", (w, h), 0), masker))
    k = Image.alpha_composite(k, glans)
    return k.rotate(hoek, resample=Image.BICUBIC, expand=True)


def ster(d: ImageDraw.ImageDraw, x: float, y: float, r: float, kleur) -> None:
    punten = []
    for i in range(8):
        hoek = math.pi / 4 * i
        straal = r if i % 2 == 0 else r * 0.28
        punten.append((x + math.cos(hoek) * straal, y + math.sin(hoek) * straal))
    d.polygon(punten, fill=kleur)


def kaartenwaaier(img: Image.Image, kleur) -> None:
    schaduw = Image.new("RGBA", img.size, (0, 0, 0, 0))
    lagen = []
    # Buitenste kaarten eerst, de middelste bovenop: een nette waaier.
    for hoek, dx, dy in ((15, 790, 100), (-17, 1000, 100), (-2, 893, 62)):
        k = kaart(kleur, hoek, 0.95)
        lagen.append((k, dx, dy))
        sd = ImageDraw.Draw(schaduw)
        sd.rounded_rectangle([dx + 12, dy + 18, dx + k.width - 8, dy + k.height + 4], radius=20, fill=(0, 0, 0, 110))
    schaduw = schaduw.filter(ImageFilter.GaussianBlur(14))
    img.paste(schaduw, (0, 0), schaduw)
    for k, dx, dy in lagen:
        img.paste(k, (dx, dy), k)
    d = ImageDraw.Draw(img)
    rng = random.Random(7)
    for _ in range(9):
        x, y = rng.randint(760, 1180), rng.randint(20, 400)
        ster(d, x, y, rng.choice((5, 7, 10)), (*meng(kleur, (255, 255, 255), 0.6),))


def tekst_passend(d, tekst, fnt_naam, max_grootte, max_breed):
    grootte = max_grootte
    while grootte > 20:
        f = font(fnt_naam, grootte)
        if d.textlength(tekst, font=f) <= max_breed:
            return f
        grootte -= 2
    return font(fnt_naam, grootte)


def omloop(d, tekst, f, max_breed):
    woorden, regels, regel = tekst.split(), [], ""
    for w in woorden:
        proef = f"{regel} {w}".strip()
        if d.textlength(proef, font=f) <= max_breed:
            regel = proef
        else:
            regels.append(regel)
            regel = w
    regels.append(regel)
    return regels


def banner(naam: str, titel: str, sub: str, soort: str) -> Path:
    kleur = KLEUREN[soort]
    img = achtergrond(kleur)
    stippen(img, kleur)
    kaartenwaaier(img, kleur)
    d = ImageDraw.Draw(img)
    x = 64
    # woordmerk
    d.rounded_rectangle([x, 70, x + 6, 98], radius=3, fill=kleur)
    d.text((x + 20, 70), "POKETCG HAVEN", font=font("Inter-Bold.otf", 22), fill=meng(kleur, (255, 255, 255), 0.35))
    # titel en ondertitel
    tf = tekst_passend(d, titel, "InterDisplay-Bold.otf", 74, 680)
    d.text((x, 128), titel, font=tf, fill=(255, 255, 255))
    sf = font("Inter-Medium.otf", 28)
    for i, regel in enumerate(omloop(d, sub, sf, 640)[:2]):
        d.text((x, 228 + i * 40), regel, font=sf, fill=(205, 212, 228))
    # onderlijn
    d.rounded_rectangle([x, 340, x + 120, 346], radius=3, fill=kleur)
    d.text((x + 140, 330), "Nederland & België", font=font("Inter-SemiBold.otf", 20), fill=(150, 160, 185))
    UIT.mkdir(parents=True, exist_ok=True)
    pad = UIT / f"{naam}.png"
    img.save(pad, optimize=True)
    return pad


def logo() -> Path:
    """Het PH-logo: bruikbaar als servericoon, bot-avatar en auteur-icoon in de embeds."""
    s = 512
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    grad = Image.new("RGB", (s, s))
    gd = ImageDraw.Draw(grad)
    for y in range(s):
        gd.line([(0, y), (s, y)], fill=meng(KLEUREN["community"], KLEUREN["merk"], y / s))
    masker = Image.new("L", (s, s), 0)
    ImageDraw.Draw(masker).rounded_rectangle([0, 0, s - 1, s - 1], radius=120, fill=255)
    img.paste(grad, (0, 0), masker)
    d = ImageDraw.Draw(img)
    f = font("InterDisplay-Bold.otf", 230)
    b = d.textbbox((0, 0), "PH", font=f)
    d.text(((s - (b[2] - b[0])) / 2 - b[0], (s - (b[3] - b[1])) / 2 - b[1] - 10), "PH", font=f, fill=(255, 255, 255))
    ster(d, 405, 110, 34, (255, 255, 255))
    pad = UIT / "logo.png"
    img.save(pad, optimize=True)
    return pad


def main() -> None:
    for naam, titel, sub, soort in BANNERS:
        print(banner(naam, titel, sub, soort).relative_to(ROOT))
    print(logo().relative_to(ROOT))


if __name__ == "__main__":
    main()

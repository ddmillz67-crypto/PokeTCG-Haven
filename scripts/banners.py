"""Maakt de banners en het logo voor de embeds (inhoud/afbeeldingen/*.png).

    python -m scripts.banners

Pokémon-sfeer met eigen ontwerpen: een route-landschap in retrostijl, booster packs,
holo-kaarten en zelfgetekende energie-symbolen per type. Er zit bewust geen officieel
Pokémon-artwork of -logo in (merkrecht). Eigen beelden kun je per banner neerzetten in
inhoud/afbeeldingen/eigen/<naam>.png; die gaan dan voor.
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
PIXEL = 6

# Type: (hoofdkleur, lucht boven, lucht onder, heuvels, label)
TYPES = {
    "vuur":       ((255, 112, 52),  (255, 168, 92),  (255, 214, 150), (226, 120, 70),  "Vuur"),
    "water":      ((64, 146, 255),  (92, 170, 255),  (186, 224, 255), (70, 150, 210),  "Water"),
    "gras":       ((88, 196, 92),   (120, 200, 255), (206, 240, 255), (96, 176, 84),   "Gras"),
    "elektrisch": ((255, 206, 40),  (255, 214, 92),  (255, 240, 180), (214, 178, 70),  "Elektrisch"),
    "psychisch":  ((236, 96, 170),  (190, 130, 230), (246, 196, 236), (170, 110, 190), "Psychisch"),
    "vechten":    ((214, 72, 56),   (232, 120, 90),  (250, 196, 160), (176, 92, 70),   "Vechten"),
    "duister":    ((112, 88, 160),  (44, 40, 84),    (112, 92, 150),  (60, 52, 98),    "Duister"),
    "metaal":     ((140, 160, 186), (150, 178, 210), (220, 230, 242), (120, 140, 166), "Metaal"),
    "fee":        ((250, 132, 196), (255, 170, 214), (255, 226, 240), (232, 150, 190), "Fee"),
    "draak":      ((122, 92, 230),  (240, 178, 74),  (255, 226, 160), (150, 110, 200), "Draak"),
}

# naam, titel, ondertitel, type
BANNERS = [
    # "welkom" komt uit scripts/warm.py (warme, filmische stijl)
    ("regels", "De huisregels", "Elke goede trainer kent de regels van het spel", "vechten"),
    ("tour", "Jouw route door de server", "Van eerste stap tot vaste trainer", "water"),
    ("aankondigingen", "Aankondigingen", "Nieuws, events, winnaars en mijlpalen", "elektrisch"),
    ("rollen", "Kies je rollen", "Stel je trainerskaart samen", "fee"),
    ("voorstellen", "Stel je voor", "Elke trainer begint ergens. Welkom!", "gras"),
    ("pulls", "Laat je pulls zien", "Elke vrijdag de Pull van de Week", "elektrisch"),
    ("collecties", "Jouw collectie", "Binders, sealed, graded en Japans", "psychisch"),
    ("giveaways", "Giveaways", "Bij elke mijlpaal een prijs. Altijd gratis", "fee"),
    ("chat", "De huiskamer", "Kletsen met trainers uit heel NL en BE", "gras"),
    ("markt", "Veilig handelen", "Ruilen, kopen en verkopen met vouches", "metaal"),
    ("hulp", "Vragen & hulp", "Geen vraag is te klein, trainer", "water"),
    ("radar", "Winkel-radar", "Samen zien we meer dan elke bot", "psychisch"),
    ("releases", "Releasekalender", "Elke nieuwe set in Nederland en België", "draak"),
    ("restocks", "Restock-alerts", "Weer op voorraad? Dan zie je het hier", "gras"),
    ("success", "Gescoord!", "De vangsten van onze trainers", "draak"),
    ("store", "PokeTCG Haven Store", "Extra's voor wie sneller wil", "draak"),
    ("sniper", "Haven Sniper", "Mis nooit meer een drop", "elektrisch"),
    ("elite", "Haven Elite", "Voor de echte verzamelaar", "duister"),
    ("groupbuys", "Group buys", "Samen inkopen tegen kostprijs", "metaal"),
    ("grading", "Grading-service", "Samen naar PSA en CGC", "psychisch"),
    ("partners", "Partnerwinkels", "Steun je lokale kaartwinkel", "gras"),
    ("tickets", "Hulp nodig?", "Open een ticket, we helpen je graag", "water"),
]


def font(naam: str, grootte: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / naam), grootte)


def meng(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def donker(k, t=0.35):
    return meng(k, (10, 14, 30), t)


def licht(k, t=0.35):
    return meng(k, (255, 255, 255), t)


# -- energie-symbolen (eigen ontwerp) -------------------------------------------


def ster(d, x, y, r, kleur, binnen=0.28, punten=4):
    pts = []
    for i in range(punten * 2):
        a = math.pi / punten * i - math.pi / 2
        rr = r if i % 2 == 0 else r * binnen
        pts.append((x + math.cos(a) * rr, y + math.sin(a) * rr))
    d.polygon(pts, fill=kleur)


def energie(d: ImageDraw.ImageDraw, soort: str, cx: float, cy: float, r: float, kleur) -> None:
    """Een rond energie-embleem met een eigen symbool per type."""
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 255, 255), outline=donker(kleur, 0.2), width=max(2, int(r * 0.12)))
    k = kleur
    s = r * 0.62
    if soort == "vuur":
        d.polygon([(cx, cy - s), (cx + s * 0.75, cy + s * 0.25), (cx + s * 0.35, cy + s), (cx - s * 0.35, cy + s), (cx - s * 0.75, cy + s * 0.25)], fill=k)
        d.polygon([(cx, cy - s * 0.15), (cx + s * 0.35, cy + s * 0.45), (cx, cy + s * 0.85), (cx - s * 0.35, cy + s * 0.45)], fill=licht(k, 0.55))
    elif soort == "water":
        d.polygon([(cx, cy - s)] + [(cx + math.sin(a) * s * 0.7, cy + s * 0.3 - math.cos(a) * s * 0.7) for a in [i * math.pi / 12 for i in range(-9, 10)]], fill=k)
    elif soort == "gras":
        d.ellipse([cx - s * 0.55, cy - s, cx + s * 0.55, cy + s], fill=k)
        d.line([(cx, cy - s * 0.8), (cx, cy + s)], fill=(255, 255, 255), width=max(2, int(r * 0.09)))
    elif soort == "elektrisch":
        d.polygon([(cx + s * 0.2, cy - s), (cx - s * 0.55, cy + s * 0.1), (cx - s * 0.05, cy + s * 0.1), (cx - s * 0.25, cy + s), (cx + s * 0.55, cy - s * 0.15), (cx + s * 0.05, cy - s * 0.15)], fill=k)
    elif soort == "psychisch":
        d.ellipse([cx - s, cy - s * 0.55, cx + s, cy + s * 0.55], fill=k)
        d.ellipse([cx - s * 0.38, cy - s * 0.38, cx + s * 0.38, cy + s * 0.38], fill=(255, 255, 255))
        d.ellipse([cx - s * 0.18, cy - s * 0.18, cx + s * 0.18, cy + s * 0.18], fill=donker(k, 0.3))
    elif soort == "vechten":
        punten = []
        for i in range(16):
            a = math.pi / 8 * i
            rr = s if i % 2 == 0 else s * 0.5
            punten.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr))
        d.polygon(punten, fill=k)
    elif soort == "duister":
        d.ellipse([cx - s, cy - s, cx + s, cy + s], fill=k)
        d.ellipse([cx - s * 0.45, cy - s * 1.05, cx + s * 1.15, cy + s * 0.55], fill=(255, 255, 255))
    elif soort == "metaal":
        d.polygon([(cx + math.cos(a) * s, cy + math.sin(a) * s) for a in [math.pi / 3 * i + math.pi / 6 for i in range(6)]], fill=k)
        d.ellipse([cx - s * 0.38, cy - s * 0.38, cx + s * 0.38, cy + s * 0.38], fill=(255, 255, 255))
    elif soort == "fee":
        ster(d, cx, cy, s, k, 0.36)
    else:  # draak
        d.polygon([(cx, cy - s), (cx + s * 0.7, cy), (cx, cy + s), (cx - s * 0.7, cy)], fill=k)
        d.polygon([(cx, cy - s * 0.5), (cx + s * 0.32, cy), (cx, cy + s * 0.5), (cx - s * 0.32, cy)], fill=licht(k, 0.5))


# -- landschap in retrostijl -----------------------------------------------------


def blok(d, x, y, kleur, p=PIXEL):
    d.rectangle([x, y, x + p - 1, y + p - 1], fill=kleur)


def landschap(type_) -> Image.Image:
    kleur, boven, onder, heuvel, _ = TYPES[type_]
    img = Image.new("RGB", (BREED, HOOG))
    d = ImageDraw.Draw(img)
    for y in range(0, HOOG, PIXEL):
        d.rectangle([0, y, BREED, y + PIXEL], fill=meng(boven, onder, (y / HOOG) ** 0.9))
    gloed = Image.new("RGBA", (BREED, HOOG), (0, 0, 0, 0))
    ImageDraw.Draw(gloed).ellipse([880, -60, 1180, 240], fill=(*licht(onder, 0.6), 150))
    gloed = gloed.filter(ImageFilter.GaussianBlur(40))
    img.paste(gloed, (0, 0), gloed)
    d = ImageDraw.Draw(img)
    rng = random.Random(type_)
    for _ in range(5):
        cx, cy = rng.randrange(60, BREED, PIXEL), rng.randrange(30, 150, PIXEL)
        w = rng.choice((10, 14, 18))
        for i in range(w):
            for j in range(3 if 2 < i < w - 3 else 2):
                blok(d, cx + i * PIXEL, cy - j * PIXEL + (PIXEL if i in (0, w - 1) else 0), licht(onder, 0.75))
    for laag, (basis, amp, freq, t) in enumerate(((250, 34, 0.006, 0.25), (300, 26, 0.011, 0.0))):
        kl = meng(heuvel, onder, t) if laag == 0 else heuvel
        for x in range(0, BREED, PIXEL):
            top = basis - amp * math.sin(x * freq + laag * 2.1) - amp * 0.5 * math.sin(x * freq * 2.7 + 1)
            top = int(top // PIXEL * PIXEL)
            d.rectangle([x, top, x + PIXEL - 1, HOOG], fill=kl)
    gras_d, gras_l = donker(heuvel, 0.35), licht(heuvel, 0.15)
    for x0 in range(0, BREED, PIXEL * 5):
        y0 = HOOG - PIXEL * 6 + (PIXEL if (x0 // (PIXEL * 5)) % 2 else 0)
        for i, h in enumerate((3, 5, 4, 6, 3)):
            for j in range(h):
                blok(d, x0 + i * PIXEL, y0 + (6 - h + j) * PIXEL - PIXEL * 2, gras_l if j == 0 else gras_d)
    return img


# -- kaarten en booster pack ------------------------------------------------------


def kaart(kleur, type_, hoek):
    w, h = 170, 236
    k = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(k)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=14, fill=(255, 214, 92))
    d.rounded_rectangle([8, 8, w - 9, h - 9], radius=9, fill=licht(kleur, 0.55))
    d.rounded_rectangle([18, 30, w - 19, 128], radius=6, fill=meng(kleur, (255, 255, 255), 0.15), outline=donker(kleur, 0.2), width=2)
    energie(d, type_, w / 2, 79, 30, kleur)
    d.rounded_rectangle([18, 12, 110, 24], radius=4, fill=(255, 255, 255))
    energie(d, type_, w - 28, 18, 9, kleur)
    for i, br in enumerate((0.8, 0.6, 0.7)):
        d.rounded_rectangle([18, 142 + i * 20, 18 + (w - 36) * br, 150 + i * 20], radius=4, fill=(255, 255, 255))
    glans = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(glans).polygon([(w * 0.1, h), (w * 0.55, 0), (w * 0.78, 0), (w * 0.33, h)], fill=(255, 255, 255, 60))
    k = Image.alpha_composite(k, glans)
    return k.rotate(hoek, resample=Image.BICUBIC, expand=True)


def booster(kleur, type_):
    w, h = 190, 300
    b = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(b)
    for y in range(h):
        d.line([(0, y), (w, y)], fill=(*meng(licht(kleur, 0.25), donker(kleur, 0.25), y / h), 255))
    for x in range(0, w, 10):
        d.polygon([(x, 0), (x + 5, 10), (x + 10, 0)], fill=(0, 0, 0, 0))
        d.polygon([(x, h), (x + 5, h - 10), (x + 10, h)], fill=(0, 0, 0, 0))
    d.rectangle([0, 10, w, 26], fill=(*donker(kleur, 0.35), 255))
    d.rectangle([0, h - 26, w, h - 10], fill=(*donker(kleur, 0.35), 255))
    folie = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    fd = ImageDraw.Draw(folie)
    for i in range(6):
        x = -60 + i * 50
        fd.polygon([(x, h), (x + 90, 0), (x + 110, 0), (x + 20, h)], fill=(255, 255, 255, 34))
    folie.putalpha(Image.composite(folie.getchannel("A"), Image.new("L", (w, h), 0), b.getchannel("A")))
    b = Image.alpha_composite(b, folie)
    d = ImageDraw.Draw(b)
    energie(d, type_, w / 2, h / 2 - 20, 48, kleur)
    helder = 0.299 * kleur[0] + 0.587 * kleur[1] + 0.114 * kleur[2] > 170
    tekstkleur = donker(kleur, 0.75) if helder else (255, 255, 255)
    d.text((w / 2, h / 2 + 52), "BOOSTER", font=font("InterDisplay-Bold.otf", 26), fill=tekstkleur, anchor="mm")
    d.text((w / 2, h / 2 + 80), "HAVEN EDITIE", font=font("Inter-SemiBold.otf", 14), fill=tekstkleur, anchor="mm")
    return b.rotate(8, resample=Image.BICUBIC, expand=True)


def schaduw(img, laag, x, y, blur=12, alfa=120):
    s = Image.new("RGBA", img.size, (0, 0, 0, 0))
    masker = laag.getchannel("A").point(lambda a: alfa if a > 0 else 0)
    s.paste((0, 0, 0, 255), (x + 10, y + 14), masker)
    s = s.filter(ImageFilter.GaussianBlur(blur))
    img.alpha_composite(s)
    img.alpha_composite(laag, (x, y))


# -- samenstellen -------------------------------------------------------------------


def tekst_passend(d, tekst, fnt, max_grootte, max_breed):
    g = max_grootte
    while g > 24 and d.textlength(tekst, font=font(fnt, g)) > max_breed:
        g -= 2
    return font(fnt, g)


def omloop(d, tekst, f, max_breed):
    regels, regel = [], ""
    for w in tekst.split():
        proef = f"{regel} {w}".strip()
        if d.textlength(proef, font=f) <= max_breed:
            regel = proef
        else:
            regels.append(regel)
            regel = w
    return regels + [regel]


def banner(naam: str, titel: str, sub: str, type_: str) -> Path:
    kleur, *_rest, label = TYPES[type_]
    img = landschap(type_).convert("RGBA")
    schaduw(img, kaart(kleur, type_, 14), 760, 120)
    schaduw(img, kaart(kleur, type_, -12), 1010, 118)
    schaduw(img, booster(kleur, type_), 862, 52)
    d = ImageDraw.Draw(img)
    rng = random.Random(naam)
    geplaatst = 0
    while geplaatst < 8:
        x, y = rng.randint(740, 1185), rng.randint(16, 330)
        if 850 < x < 1075 and y > 40:
            continue  # niet over het booster pack
        ster(d, x, y, rng.choice((5, 7, 10)), (255, 255, 255))
        geplaatst += 1
    paneel = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(paneel).rounded_rectangle([36, 40, 712, 378], radius=26, fill=(14, 18, 36, 205))
    img = Image.alpha_composite(img, paneel)
    d = ImageDraw.Draw(img)
    x = 70
    pf = font("Inter-Bold.otf", 18)
    pill_breed = 54 + int(d.textlength(f"Type: {label}", font=pf)) + 18
    d.rounded_rectangle([x, 70, x + pill_breed, 108], radius=19, fill=kleur)
    energie(d, type_, x + 19, 89, 14, donker(kleur, 0.1))
    d.text((x + 42, 89), f"Type: {label}", font=pf, fill=(255, 255, 255), anchor="lm")
    d.text((x + pill_breed + 16, 89), "POKETCG HAVEN", font=pf, fill=licht(kleur, 0.45), anchor="lm")
    tf = tekst_passend(d, titel, "InterDisplay-Bold.otf", 68, 600)
    d.text((x, 130), titel, font=tf, fill=(255, 255, 255))
    sf = font("Inter-Medium.otf", 27)
    for i, regel in enumerate(omloop(d, sub, sf, 600)[:2]):
        d.text((x, 222 + i * 38), regel, font=sf, fill=(214, 220, 236))
    d.rounded_rectangle([x, 330, x + 110, 336], radius=3, fill=kleur)
    d.text((x + 128, 333), "Nederland & België", font=font("Inter-SemiBold.otf", 18), fill=(160, 170, 195), anchor="lm")
    UIT.mkdir(parents=True, exist_ok=True)
    pad = UIT / f"{naam}.png"
    img.convert("RGB").save(pad, optimize=True)
    return pad


def logo() -> Path:
    """Het PH-logo: servericoon, bot-avatar en auteur-icoon."""
    s = 512
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    grad = Image.new("RGB", (s, s))
    gd = ImageDraw.Draw(grad)
    for y in range(s):
        gd.line([(0, y), (s, y)], fill=meng(TYPES["vuur"][0], TYPES["water"][0], y / s))
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
    for naam, titel, sub, type_ in BANNERS:
        print(banner(naam, titel, sub, type_).relative_to(ROOT))
    print(logo().relative_to(ROOT))


if __name__ == "__main__":
    main()

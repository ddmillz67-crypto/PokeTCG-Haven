"""De mijlpaal-ladder uit het Bouwplan en de voortgangsbalk in #giveaways."""

from __future__ import annotations

LADDER: list[tuple[int, str]] = [
    (250, "5 boosterpacks"),
    (500, "Elite Trainer Box"),
    (1000, "Booster box"),
    (2500, "Booster box"),
    (5000, "2 booster boxes (2 winnaars)"),
    (7500, "Booster box en een Japanse box"),
    (10000, "3 booster boxes (3 winnaars)"),
]
DAARNA_ELKE = 5000
DAARNA_PRIJS = "Booster box"


def mijlpaal_rond(leden: int) -> tuple[int, int, str]:
    """(vorige mijlpaal, volgende mijlpaal, prijs bij de volgende)."""
    vorige = 0
    for grens, prijs in LADDER:
        if leden < grens:
            return vorige, grens, prijs
        vorige = grens
    volgende = LADDER[-1][0] + DAARNA_ELKE
    while leden >= volgende:
        vorige, volgende = volgende, volgende + DAARNA_ELKE
    return vorige, volgende, DAARNA_PRIJS


def behaalde_mijlpalen(leden: int) -> list[int]:
    behaald = [g for g, _ in LADDER if leden >= g]
    g = LADDER[-1][0] + DAARNA_ELKE
    while leden >= g:
        behaald.append(g)
        g += DAARNA_ELKE
    return behaald


def balk(leden: int, breedte: int = 20) -> str:
    vorige, volgende, _ = mijlpaal_rond(leden)
    deel = (leden - vorige) / (volgende - vorige)
    vol = max(0, min(breedte, int(deel * breedte)))
    return "▰" * vol + "▱" * (breedte - vol)


def getal(n: int) -> str:
    return f"{n:,}".replace(",", ".")

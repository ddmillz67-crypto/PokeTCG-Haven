"""Winkelmonitors: Shopify-winkels in de gaten houden en een alert maken bij een restock.

Veel kaartwinkels draaien op Shopify. Die hebben een openbaar productoverzicht op
`/products.json` (of `/collections/<naam>/products.json`), met per variant of hij op voorraad is.
De monitor vergelijkt elke ronde met de vorige: gaat een Pokémon-product van uitverkocht naar
op voorraad, dan wordt het een alert. De eerste ronde na het opstarten legt alleen de
beginstand vast, zodat er na een herstart geen stortvloed aan alerts komt.

Alleen sealed producten (ETB's, booster boxes, boosters, collecties) geven een alert;
losse kaarten niet, anders wordt het kanaal onleesbaar.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

from haven.alerts import AlertData

INTERVAL_SECONDEN = 120
MAX_PAGINAS = 4
USER_AGENT = "Mozilla/5.0 (compatible; PokeTCGHavenBot/1.0; restock-alerts voor verzamelaars)"

# Volgorde telt: de eerste die past, wint.
CATEGORIE_WOORDEN: list[tuple[str, tuple[str, ...]]] = [
    ("etb", ("elite trainer box", "etb", "top trainer box", "coffret dresseur d'elite")),
    ("booster-box", ("booster box", "booster display", "display", "boosterbox")),
    ("booster", ("booster bundle", "bundle", "sleeved booster", "booster pack", "blister", "booster")),
    ("collectie", ("collection", "collectie", "tin", "box set", "premium", "ultra premium", "upc", "kollektion")),
]
JAPANS = ("japans", "japanese", "japan", "jp ")
GEEN_SEALED = ("sleeve", "binder", "toploader", "deck box", "playmat", "proxy", "fake", "graded", "psa ", "cgc ", "single")


@dataclass(frozen=True)
class Winkel:
    naam: str
    url: str  # https://domein.nl, zonder slash aan het eind
    land: str = "nlbe"  # nlbe of eu
    collectie: str = ""  # optioneel: alleen deze Shopify-collectie volgen
    affiliate: str = ""  # optioneel: sjabloon met {url}, bijvoorbeeld https://partner.nl/klik?to={url}


def normaliseer_url(ruw: str) -> str:
    ruw = ruw.strip()
    if "://" not in ruw:
        ruw = "https://" + ruw
    p = urlparse(ruw)
    if p.scheme != "https" or not p.netloc or " " in p.netloc:
        raise ValueError("gebruik een webadres zoals https://winkel.nl")
    return f"https://{p.netloc.lower()}"


def feed_url(w: Winkel, pagina: int) -> str:
    pad = f"/collections/{w.collectie}/products.json" if w.collectie else "/products.json"
    return f"{w.url}{pad}?limit=250&page={pagina}"


def is_pokemon(p: dict) -> bool:
    tekst = " ".join([p.get("title", ""), p.get("vendor", ""), p.get("product_type", ""), " ".join(p.get("tags") or [])]).lower()
    return "pokemon" in tekst or "pokémon" in tekst


def categorie_voor(p: dict) -> str | None:
    """De alert-categorie van een product, of None als het geen sealed product is."""
    titel = f" {p.get('title', '')} {p.get('product_type', '')} ".lower()
    if any(w in titel for w in GEEN_SEALED):
        return None
    for categorie, woorden in CATEGORIE_WOORDEN:
        if any(re.search(rf"(?<![a-z]){re.escape(w)}(?![a-z])", titel) for w in woorden):
            return "japans" if any(j in titel for j in JAPANS) else categorie
    return None


def prijs_tekst(prijs: str | float | None) -> str:
    try:
        bedrag = float(prijs)
    except (TypeError, ValueError):
        return ""
    return "€ " + f"{bedrag:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def relevant(p: dict) -> str | None:
    return categorie_voor(p) if is_pokemon(p) else None


def stand(producten: list[dict]) -> dict[int, bool]:
    """Per relevante variant: op voorraad of niet."""
    return {
        v["id"]: bool(v.get("available"))
        for p in producten
        if relevant(p)
        for v in p.get("variants", [])
    }


def verwerk(w: Winkel, producten: list[dict], vorige: dict[int, bool] | None) -> tuple[list[AlertData], dict[int, bool]]:
    """Vergelijk met de vorige ronde. Geeft (alerts, nieuwe stand)."""
    nieuw = stand(producten)
    if vorige is None:
        return [], nieuw
    alerts = []
    for p in producten:
        categorie = relevant(p)
        if not categorie:
            continue
        terug = [v for v in p.get("variants", []) if v.get("available") and not vorige.get(v["id"], False)]
        if not terug:
            continue
        url = f"{w.url}/products/{p['handle']}"
        afbeelding = ((p.get("images") or [{}])[0] or {}).get("src", "")
        alerts.append(
            AlertData(
                product=p["title"][:200],
                winkel=w.naam,
                url=w.affiliate.format(url=url) if w.affiliate else url,
                prijs=prijs_tekst(terug[0].get("price")),
                land=w.land,
                categorie=categorie,
                afbeelding=afbeelding,
                affiliate=bool(w.affiliate),
            )
        )
    return alerts, nieuw


def samenvatting(producten: list[dict]) -> tuple[int, int, int]:
    """(alle producten, Pokémon sealed, daarvan op voorraad) voor /winkel toevoegen en /winkel lijst."""
    sealed = [p for p in producten if relevant(p)]
    op_voorraad = sum(any(v.get("available") for v in p.get("variants", [])) for p in sealed)
    return len(producten), len(sealed), op_voorraad

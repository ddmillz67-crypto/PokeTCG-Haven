"""Restock-alerts: hoe een alert eruitziet, en de koppeling voor automatische monitors.

Alerts komen van de winkelmonitors (haven/monitors.py, winkels toevoegen met /winkel toevoegen)
of van het team met /alert. De Haven-bot plaatst ze direct in #sniper-nlbe (of #sniper-eu)
en 10 minuten later in #restocks.
"""

from __future__ import annotations

from dataclasses import dataclass

import discord

from haven.huisstijl import FOOTER, KLEUREN

VERTRAGING_GRATIS_SECONDEN = 10 * 60
CATEGORIEEN = {
    "etb": "Elite Trainer Box",
    "booster-box": "Booster box",
    "booster": "Boosters en bundels",
    "collectie": "Collecties en tins",
    "japans": "Japans",
    "overig": "Overig",
}


@dataclass(frozen=True)
class AlertData:
    product: str
    winkel: str
    url: str
    prijs: str = ""
    limiet: str = ""
    land: str = "nlbe"  # nlbe of eu
    categorie: str = "overig"
    afbeelding: str = ""
    affiliate: bool = False


def alert_embed(a: AlertData, *, vertraagd: bool = False, uitverkocht: bool = False) -> discord.Embed:
    if uitverkocht:
        titel, kleur = f"Uitverkocht: {a.product}", KLEUREN["uitverkocht"]
    else:
        titel, kleur = f"Op voorraad: {a.product}", KLEUREN["alert"]
    embed = discord.Embed(title=titel[:256], colour=kleur, url=None if uitverkocht else a.url)
    embed.set_author(name="PokeTCG Haven • Restock" if vertraagd else "PokeTCG Haven • Sniper")
    embed.add_field(name="Winkel", value=a.winkel, inline=True)
    if a.prijs:
        embed.add_field(name="Prijs", value=a.prijs, inline=True)
    if a.limiet:
        embed.add_field(name="Limiet", value=a.limiet, inline=True)
    embed.add_field(name="Soort", value=CATEGORIEEN.get(a.categorie, a.categorie), inline=True)
    if a.affiliate and not uitverkocht:
        embed.add_field(name="Let op", value="Dit is een affiliate-link: wij krijgen een kleine vergoeding, jij betaalt niets extra.", inline=False)
    if vertraagd and not uitverkocht:
        embed.description = "Haven Sniper-leden kregen deze alert 10 minuten eerder."
    if a.afbeelding:
        embed.set_thumbnail(url=a.afbeelding)
    embed.set_footer(text=FOOTER)
    return embed

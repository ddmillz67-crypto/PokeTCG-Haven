"""Huisstijl van PokeTCG Haven: kleuren en een vaste opbouw voor embeds."""

from __future__ import annotations

import datetime as dt

import discord

FOOTER = "PokeTCG Haven • NL/BE/EN"

KLEUREN = {
    "merk": 0x1E6FD9,         # Haven-blauw: start-hier, aankondigingen
    "release": 0xF7C948,      # geel: release-kalender
    "alert": 0x2ECC71,        # groen: op voorraad
    "uitverkocht": 0x95A5A6,  # grijs: alert verlopen
    "premium": 0x8E44AD,      # paars: upgrade, elite
    "regels": 0xE74C3C,       # rood: regels en waarschuwingen
}


def tweetalig(nl: str, en: str) -> str:
    """Nederlandse tekst bovenaan, Engelse tekst eronder met een vlag."""
    return f"{nl}\n\n🇬🇧 {en}"


def maak_embed(
    soort: str,
    titel: str,
    beschrijving: str,
    *,
    auteur: str = "PokeTCG Haven",
    tijdstempel: bool = True,
) -> discord.Embed:
    if soort not in KLEUREN:
        raise ValueError(f"onbekende soort '{soort}', kies uit {sorted(KLEUREN)}")
    if len(titel) > 256:
        raise ValueError("Discord staat maximaal 256 tekens in een titel toe")
    if len(beschrijving) > 4096:
        raise ValueError("Discord staat maximaal 4096 tekens in een beschrijving toe")
    embed = discord.Embed(
        title=titel,
        description=beschrijving,
        colour=KLEUREN[soort],
        timestamp=dt.datetime.now(dt.timezone.utc) if tijdstempel else None,
    )
    embed.set_author(name=auteur)
    embed.set_footer(text=FOOTER)
    return embed

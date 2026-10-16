"""Huisstijl van PokeTCG Haven: kleuren en een vaste opbouw voor embeds."""

from __future__ import annotations

import datetime as dt

import discord

FOOTER = "PokeTCG Haven • Nederland & België"

KLEUREN = {
    "merk": 0x1E6FD9,         # Haven-blauw: start-hier, aankondigingen
    "release": 0xF7C948,      # geel: release-kalender
    "alert": 0x2ECC71,        # groen: op voorraad
    "uitverkocht": 0x95A5A6,  # grijs: alert verlopen
    "premium": 0x8E44AD,      # paars: upgrade, elite
    "regels": 0xE74C3C,       # rood: regels en waarschuwingen
    "community": 0xFF8A3D,    # warm oranje: welkom, felicitaties, Pull van de Week, kanaalkaarten
}


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


def kanaalkaart(
    kanaal: str,
    waarvoor: str,
    wat_mag: str,
    voorbeeld: str,
    hulp: str = "Vraag het in #vragen-hulp of open een ticket in #tickets.",
    *,
    soort: str = "community",
) -> discord.Embed:
    """De vastgepinde kanaalkaart: vier vaste vragen, altijd in dezelfde volgorde."""
    embed = maak_embed(soort, f"📌 Over #{kanaal}", waarvoor, tijdstempel=False)
    embed.add_field(name="Wat mag hier?", value=wat_mag, inline=False)
    embed.add_field(name="Zo ziet een goed voorbeeld eruit", value=voorbeeld, inline=False)
    embed.add_field(name="Hulp nodig?", value=hulp, inline=False)
    for veld in embed.fields:
        if len(veld.value) > 1024:
            raise ValueError(f"veld '{veld.name}' is langer dan de 1024 tekens die Discord toestaat")
    return embed

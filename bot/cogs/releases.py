"""Releasekalender: /release plaatst een release met datum, tijd, winkels en limiet."""

from __future__ import annotations

import datetime as dt

import discord
from discord import app_commands
from discord.ext import commands

from bot.kern import TIJDZONE, HavenBot, antwoord


class Releases(commands.Cog):
    def __init__(self, bot: HavenBot):
        self.bot = bot

    @app_commands.command(name="release", description="Zet een release in de kalender (alleen team)")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(naam="Naam van de set of het product", datum="JJJJ-MM-DD", tijd="UU:MM (optioneel)", winkels="Bij welke winkels", limiet="Limiet per persoon", afbeelding="Link naar een afbeelding")
    async def release(
        self, interaction: discord.Interaction, naam: str, datum: str, winkels: str,
        tijd: str | None = None, limiet: str | None = None, afbeelding: str | None = None,
    ) -> None:
        try:
            moment = dt.datetime.strptime(f"{datum} {tijd or '00:00'}", "%Y-%m-%d %H:%M").replace(tzinfo=TIJDZONE)
        except ValueError:
            await antwoord(interaction, "Gebruik datum JJJJ-MM-DD en tijd UU:MM, bijvoorbeeld 2026-11-14 en 10:00.")
            return
        ch = self.bot.kanaal("release-kalender")
        if ch is None:
            await antwoord(interaction, "#release-kalender bestaat nog niet.")
            return
        stempel = int(moment.timestamp())
        wanneer = f"<t:{stempel}:F> (<t:{stempel}:R>)" if tijd else f"<t:{stempel}:D> (<t:{stempel}:R>)"
        e = self.bot.embed("release", f"📅 {naam}", f"**Wanneer:** {wanneer}\n**Waar:** {winkels}" + (f"\n**Limiet:** {limiet}" if limiet else ""))
        e.set_author(name="PokeTCG Haven • Release")
        if afbeelding:
            e.set_image(url=afbeelding)
        ping = self.bot.rol("Release-ping")
        m = await ch.send(content=ping.mention if ping else None, embed=e, allowed_mentions=discord.AllowedMentions(roles=True))
        thread = await m.create_thread(name=f"Releasedraad: {naam}"[:90])
        await thread.send(embed=self.bot.embed("release", "💬 Releasedraad", "Deel hier je tips: welke winkels pakken vroeg uit, hoe lang is de rij en wat is er nog op voorraad?"))
        await antwoord(interaction, f"✅ Release geplaatst: {m.jump_url}")


async def setup(bot: HavenBot) -> None:
    await bot.add_cog(Releases(bot))

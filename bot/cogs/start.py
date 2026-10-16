"""Taalkeuze, nieuwe leden en de knop 'Ik heb een vraag' bij de regels."""

from __future__ import annotations

import time

import discord
from discord.ext import commands

from bot.kern import HavenBot, antwoord
from haven.levels import ALLE_LEVELROLLEN, LEVEL_ROLLEN

LIDROL = "Lid"


class Start(commands.Cog):
    def __init__(self, bot: HavenBot):
        self.bot = bot
        bot.actie("binnen", self.binnen)
        bot.actie("regels:vraag", self.vraag)

    async def zorg_voor_levelrol(self, lid: discord.Member) -> None:
        if any(r.name in ALLE_LEVELROLLEN for r in lid.roles):
            return
        rol = self.bot.rol(LEVEL_ROLLEN[-1][1])
        if rol:
            await lid.add_roles(rol, reason="Nieuw lid")

    async def binnen(self, interaction: discord.Interaction, _: str) -> None:
        lid = interaction.user
        rol = self.bot.rol(LIDROL)
        if rol is None:
            await antwoord(interaction, "De server wordt nog ingericht. Probeer het zo nog eens!")
            return
        al_binnen = rol in lid.roles
        if not al_binnen:
            await lid.add_roles(rol, reason="Kom binnen")
        await self.zorg_voor_levelrol(lid)
        e = self.bot.embed(
            "community",
            "🧡  Je bent er al!" if al_binnen else "🧡  Welkom binnen!",
            "Je hebt nu toegang tot de hele community.\n\n"
            "**Volgende stap:** lees de huisregels in {#regels} en volg daarna de tour in {#server-tour}.",
        )
        await antwoord(interaction, embed=e)

    async def vraag(self, interaction: discord.Interaction, _: str) -> None:
        tickets = self.bot.get_cog("Tickets")
        await tickets.open(interaction, "hulp")

    @commands.Cog.listener()
    async def on_member_join(self, lid: discord.Member) -> None:
        if lid.guild.id != self.bot.guild_id or lid.bot:
            return
        self.bot.db.lid_zet(lid.id, lid_sinds=time.time())
        await self.zorg_voor_levelrol(lid)


async def setup(bot: HavenBot) -> None:
    await bot.add_cog(Start(bot))

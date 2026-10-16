"""Taalkeuze, nieuwe leden en de knop 'Ik heb een vraag' bij de regels."""

from __future__ import annotations

import time

import discord
from discord.ext import commands

from bot.kern import HavenBot, antwoord
from haven.levels import ALLE_LEVELROLLEN, LEVEL_ROLLEN

TALEN = {"nlbe": ("NL/BE", "EN"), "en": ("EN", "NL/BE")}


class Start(commands.Cog):
    def __init__(self, bot: HavenBot):
        self.bot = bot
        bot.actie("taal", self.taal)
        bot.actie("regels:vraag", self.vraag)

    async def zorg_voor_levelrol(self, lid: discord.Member) -> None:
        if any(r.name in ALLE_LEVELROLLEN for r in lid.roles):
            return
        rol = self.bot.rol(LEVEL_ROLLEN[-1][1])
        if rol:
            await lid.add_roles(rol, reason="Nieuw lid")

    async def taal(self, interaction: discord.Interaction, keuze: str) -> None:
        if keuze not in TALEN:
            return
        lid = interaction.user
        aan, uit = (self.bot.rol(n) for n in TALEN[keuze])
        if aan is None:
            await antwoord(interaction, "De taalrollen bestaan nog niet. Het team is ermee bezig!")
            return
        if uit and uit in lid.roles:
            await lid.remove_roles(uit, reason="Taal gewijzigd")
        if aan not in lid.roles:
            await lid.add_roles(aan, reason="Taal gekozen")
        await self.zorg_voor_levelrol(lid)
        if keuze == "nlbe":
            tekst = "🇳🇱🇧🇪 Gelukt! Je ziet nu de Nederlands-Belgische sectie. Volgende stap: lees de regels in {#regels} en volg daarna de tour in {#server-tour}."
        else:
            tekst = "🇬🇧 Done! You can now see the English section. Next: read the rules in {#regels} and take the tour in {#server-tour}."
        await antwoord(interaction, self.bot.tekst(tekst))

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

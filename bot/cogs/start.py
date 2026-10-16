"""Kom binnen, nieuwe leden en de knop 'Ik heb een vraag' bij de regels."""

from __future__ import annotations

import time

import discord
from discord.ext import commands

from bot.kern import HavenBot, antwoord
from haven.inhoud import PREFIX
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
            "🧡  Je bent er al, trainer!" if al_binnen else "🧡  Welkom binnen, trainer!",
            "Je hebt nu toegang tot de **hele community**.\n\n"
            "**Jouw volgende stappen**\n"
            "**1.**  Lees de huisregels in {#regels}\n"
            "**2.**  Volg de tour en verdien je eerste badge\n"
            "**3.**  Kies je rollen in {#rollen}",
        )
        await antwoord(interaction, embed=e, view=self.volgende_stappen())

    def volgende_stappen(self) -> discord.ui.View:
        view = discord.ui.View(timeout=None)
        regels = self.bot.kanaal_knop("Huisregels", "regels", "📜")
        if regels:
            view.add_item(regels)
        view.add_item(discord.ui.Button(label="Start de tour", emoji="🧭", style=discord.ButtonStyle.success, custom_id=f"{PREFIX}tour:start"))
        rollen = self.bot.kanaal_knop("Kies je rollen", "rollen", "🎛️")
        if rollen:
            view.add_item(rollen)
        return view

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

"""De knoppen 'Meer info' en 'Lees de FAQ' in #store."""

from __future__ import annotations

import discord
from discord.ext import commands

from bot.kern import HavenBot, antwoord
from haven.inhoud import laad_yaml


class Store(commands.Cog):
    def __init__(self, bot: HavenBot):
        self.bot = bot
        self.data = laad_yaml("store.yaml")
        bot.actie("store:info", self.info)
        bot.actie("store:faq", self.faq)

    async def info(self, interaction: discord.Interaction, product: str) -> None:
        i = self.data["info"].get(product)
        if i is None:
            await antwoord(interaction, "Hierover hebben we nog geen informatie.")
            return
        await antwoord(interaction, embed=self.bot.embed("premium", i["titel"], i["tekst"]))

    async def faq(self, interaction: discord.Interaction, _: str) -> None:
        f = self.data["faq"]
        await antwoord(interaction, embed=self.bot.embed("premium", f["titel"], f["tekst"]))


async def setup(bot: HavenBot) -> None:
    await bot.add_cog(Store(bot))

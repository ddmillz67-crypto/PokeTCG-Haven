"""De ledenteller bovenaan de server. Discord staat 2 naamwijzigingen per 10 minuten toe."""

from __future__ import annotations

from discord.ext import commands, tasks

from bot.kern import HavenBot
from haven.config import TELLER_PREFIX


class Teller(commands.Cog):
    def __init__(self, bot: HavenBot):
        self.bot = bot

    async def cog_load(self) -> None:
        self.bijwerken.start()

    async def cog_unload(self) -> None:
        self.bijwerken.cancel()

    @tasks.loop(minutes=15)
    async def bijwerken(self) -> None:
        g = self.bot.guild
        if g is None:
            return
        for kanaal in self.bot.config.kanalen:
            if kanaal.type != "teller":
                continue
            ch = next((c for c in g.channels if c.name.startswith(f"{TELLER_PREFIX}{kanaal.naam}:")), None)
            naam = kanaal.discord_naam(g.member_count or 0)
            if ch and ch.name != naam:
                await ch.edit(name=naam, reason="Ledenteller")

    @bijwerken.before_loop
    async def _wacht(self) -> None:
        await self.bot.wait_until_ready()
        await self.bot.setup_klaar.wait()


async def setup(bot: HavenBot) -> None:
    await bot.add_cog(Teller(bot))

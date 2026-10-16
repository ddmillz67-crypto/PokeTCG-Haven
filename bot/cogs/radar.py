"""Winkel-radar: leden melden voorraad in fysieke winkels met /meld."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from bot.kern import HavenBot, antwoord
from haven.alerts import VERTRAGING_GRATIS_SECONDEN

REGIO = ["Noord-NL", "Midden-NL", "Zuid-NL", "Vlaanderen", "Brussel", "Wallonië"]
DUIM_OMLAAG = "👎"
WEG_BIJ = 2


class Radar(commands.Cog):
    def __init__(self, bot: HavenBot):
        self.bot = bot
        bot.planner("radar", self.vertraagd)

    def melding(self, data: dict) -> discord.Embed:
        e = self.bot.embed(
            "alert", f"📍 {data['product']}",
            f"Gezien bij **{data['winkel']}** in **{data['plaats']}** ({data['regio']}).\nGemeld door <@{data['melder']}> <t:{int(data['tijd'])}:R>.",
        )
        e.set_author(name="PokeTCG Haven • Winkel-radar")
        if data.get("foto"):
            e.set_image(url=data["foto"])
        return e

    @app_commands.command(name="meld", description="Meld voorraad in een winkel voor de winkel-radar")
    @app_commands.describe(winkel="Welke winkel?", plaats="In welke plaats?", product="Wat ligt er?", regio="Welke regio?", foto="Een foto van het schap (aanbevolen)")
    @app_commands.choices(regio=[app_commands.Choice(name=r, value=r) for r in REGIO])
    async def meld(
        self, interaction: discord.Interaction, winkel: app_commands.Range[str, 2, 60], plaats: app_commands.Range[str, 2, 60],
        product: app_commands.Range[str, 2, 100], regio: app_commands.Choice[str], foto: discord.Attachment | None = None,
    ) -> None:
        data = {
            "winkel": winkel, "plaats": plaats, "product": product, "regio": regio.value, "melder": interaction.user.id,
            "tijd": interaction.created_at.timestamp(), "foto": foto.url if foto and (foto.content_type or "").startswith("image/") else "",
        }
        sniper = self.bot.kanaal("sniper-nlbe")
        if sniper:
            m = await sniper.send(embed=self.melding(data))
            await m.add_reaction(DUIM_OMLAAG)
        self.bot.plan(VERTRAGING_GRATIS_SECONDEN, "radar", data)
        await antwoord(interaction, "✅ Bedankt voor je melding! Sniper-leden zien hem nu, iedereen over 10 minuten in #winkel-radar.")

    async def vertraagd(self, data: dict) -> None:
        ch = self.bot.kanaal("winkel-radar")
        if ch is None:
            return
        rol = self.bot.rol(data["regio"])
        m = await ch.send(content=rol.mention if rol else None, embed=self.melding(data), allowed_mentions=discord.AllowedMentions(roles=True))
        await m.add_reaction(DUIM_OMLAAG)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, p: discord.RawReactionActionEvent) -> None:
        if str(p.emoji) != DUIM_OMLAAG or p.guild_id != self.bot.guild_id or p.user_id == self.bot.user.id:
            return
        ch = self.bot.get_channel(p.channel_id)
        if getattr(ch, "name", "") not in {"winkel-radar", "sniper-nlbe"}:
            return
        m = await ch.fetch_message(p.message_id)
        if m.author.id != self.bot.user.id or not m.embeds or "Winkel-radar" not in (m.embeds[0].author.name or ""):
            return
        omlaag = next((r.count - (1 if r.me else 0) for r in m.reactions if str(r.emoji) == DUIM_OMLAAG), 0)
        if omlaag >= WEG_BIJ:
            await m.delete()
            await self.bot.log(f"📍 Radarmelding verwijderd na {omlaag} duimen omlaag: {m.embeds[0].title}")


async def setup(bot: HavenBot) -> None:
    await bot.add_cog(Radar(bot))

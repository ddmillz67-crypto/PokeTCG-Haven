"""De markt en de hulpforums: vouches, Verified Trader, controle op posts en /opgelost."""

from __future__ import annotations

import asyncio
import time

import discord
from discord import app_commands
from discord.ext import commands

from bot.kern import HavenBot, antwoord

MARKTEN = {"ruilen-verkopen", "trade-en"}
HULP = {"vragen-hulp": "Opgelost", "help-en": "Solved"}
VERIFIED_VOUCHES = 5


class Markt(commands.Cog):
    def __init__(self, bot: HavenBot):
        self.bot = bot

    @app_commands.command(name="vouch", description="Geef een handelspartner een vouch na een geslaagde deal")
    @app_commands.describe(lid="Met wie heb je gehandeld?", reden="Wat ging er goed? (bijv. 'snel verzonden, kaart zoals beschreven')")
    async def vouch(self, interaction: discord.Interaction, lid: discord.Member, reden: app_commands.Range[str, 5, 200]) -> None:
        if lid.id == interaction.user.id or lid.bot:
            await antwoord(interaction, "Je kunt jezelf of een bot geen vouch geven.")
            return
        recent = self.bot.db.een(
            "SELECT 1 FROM vouches WHERE van = ? AND voor = ? AND tijd > ?", (interaction.user.id, lid.id, time.time() - 86400)
        )
        if recent:
            await antwoord(interaction, "Je hebt deze persoon in de afgelopen 24 uur al een vouch gegeven.")
            return
        self.bot.db.uitvoeren("INSERT INTO vouches (van, voor, reden, tijd) VALUES (?, ?, ?, ?)", (interaction.user.id, lid.id, reden, time.time()))
        aantal = self.bot.db.een("SELECT COUNT(DISTINCT van) AS n FROM vouches WHERE voor = ?", (lid.id,))["n"]
        e = self.bot.embed("community", "🤝 Vouch", f"{interaction.user.mention} gaf {lid.mention} een vouch: *{reden}*\n{lid.display_name} heeft nu **{aantal}** vouch(es).")
        await interaction.response.send_message(embed=e)
        if aantal == VERIFIED_VOUCHES:
            await self.bot.log(f"✅ {lid.mention} heeft {VERIFIED_VOUCHES} vouches. Controleer en geef Verified Trader met `/verify`.")

    @app_commands.command(name="vouches", description="Bekijk de vouches van een lid")
    async def vouches(self, interaction: discord.Interaction, lid: discord.Member) -> None:
        rijen = self.bot.db.alle("SELECT * FROM vouches WHERE voor = ? ORDER BY tijd DESC LIMIT 5", (lid.id,))
        aantal = self.bot.db.een("SELECT COUNT(DISTINCT van) AS n FROM vouches WHERE voor = ?", (lid.id,))["n"]
        regels = [f"• <@{r['van']}>: {r['reden']} (<t:{int(r['tijd'])}:d>)" for r in rijen] or ["Nog geen vouches."]
        verified = " ✅ Verified Trader" if any(r.name == "Verified Trader" for r in lid.roles) else ""
        await antwoord(interaction, embed=self.bot.embed("merk", f"🤝 {lid.display_name}: {aantal} vouch(es){verified}", "\n".join(regels)))

    @app_commands.command(name="verify", description="Geef een lid de rol Verified Trader (alleen team)")
    @app_commands.default_permissions(manage_roles=True)
    async def verify(self, interaction: discord.Interaction, lid: discord.Member) -> None:
        rol = self.bot.rol("Verified Trader")
        if rol is None:
            await antwoord(interaction, "De rol Verified Trader bestaat nog niet.")
            return
        await lid.add_roles(rol, reason=f"Verified door {interaction.user}")
        await antwoord(interaction, f"✅ {lid.mention} is nu Verified Trader.")

    @app_commands.command(name="opgelost", description="Markeer je vraag als opgelost / Mark your question as solved")
    async def opgelost(self, interaction: discord.Interaction) -> None:
        t = interaction.channel
        if not isinstance(t, discord.Thread) or getattr(t.parent, "name", "") not in HULP:
            await antwoord(interaction, "Dit werkt alleen in een vraag in #vragen-hulp of #help-en.")
            return
        if interaction.user.id != t.owner_id and not self.bot.is_team(interaction.user):
            await antwoord(interaction, "Alleen degene die de vraag stelde kan hem afsluiten.")
            return
        tag = discord.utils.get(t.parent.available_tags, name=HULP[t.parent.name])
        tags = list(t.applied_tags)
        if tag and tag not in tags:
            tags = (tags + [tag])[-5:]
        await interaction.response.send_message("✅ Opgelost! Bedankt voor het helpen. / Solved, thanks!")
        await t.edit(applied_tags=tags, archived=True)

    @commands.Cog.listener()
    async def on_thread_create(self, t: discord.Thread) -> None:
        if t.guild.id != self.bot.guild_id or t.owner_id == self.bot.user.id:
            return
        forum = getattr(t.parent, "name", "")
        if forum not in MARKTEN | set(HULP) | {"collecties"}:
            return
        await asyncio.sleep(2)  # het eerste bericht moet eerst binnen zijn
        start = t.starter_message
        if start is None:
            try:
                start = await t.fetch_message(t.id)
            except discord.HTTPException:
                start = None
        if forum in MARKTEN:
            if start is None or not start.attachments:
                await t.send(embed=self.bot.embed("regels", "📸 Foto's verplicht", "Een advertentie heeft foto's nodig (voor- en achterkant, met je naam en de datum ernaast). Maak een nieuwe post met foto's. / Photos are required."))
                await t.edit(archived=True, locked=True)
                return
            if not t.applied_tags:
                await t.send(embed=self.bot.embed("regels", "🏷️ Tag vergeten", "Kies een tag (Te koop, Gezocht of Ruil) via de drie puntjes > Post bewerken. / Please add a tag."))
        elif forum in HULP:
            if any(tag.name == "Beginner" for tag in t.applied_tags):
                helper = self.bot.rol("Haven Helper")
                if helper:
                    await t.send(f"{helper.mention} hier zit een beginner met een vraag 🌱", allowed_mentions=discord.AllowedMentions(roles=True))
        elif forum == "collecties":
            eerdere = [x for x in t.parent.threads if x.owner_id == t.owner_id and x.id != t.id]
            if eerdere:
                await t.send(embed=self.bot.embed("community", "📒 Je hebt al een collectiepost", f"Vul je bestaande post aan: {eerdere[0].mention}. Zo blijft alles van jou op één plek."))
                await t.edit(archived=True, locked=True)


async def setup(bot: HavenBot) -> None:
    await bot.add_cog(Markt(bot))

"""Levels: XP voor meepraten, levelrollen en /level."""

from __future__ import annotations

import time

import discord
from discord import app_commands
from discord.ext import commands

from bot.kern import HavenBot, antwoord
from haven.levels import (
    ALLE_LEVELROLLEN,
    LEVEL_ROLLEN,
    level_voor_xp,
    mag_xp_krijgen,
    rol_voor_level,
    voortgang,
    xp_voor_bericht,
)

# In deze kanalen telt een bericht niet mee (alerts, store, tickets en aankondigingen).
GEEN_XP = {"restocks", "sniper-nlbe", "sniper-eu", "success", "store", "tickets", "giveaways", "aankondigingen", "winkel-radar", "staff-logs"}
MELDING = {
    "Trainer": "Je kunt nu posten in de markt!",
    "Ace Trainer": "Je naam heeft nu een eigen kleur.",
    "Gym Leader": "Je staat nu in de Hall of Fame.",
    "Haven Legende": "Als bedankje krijg je een maand gratis Haven Sniper!",
}


def kanaalnaam(ch) -> str:
    if isinstance(ch, discord.Thread):
        return getattr(ch.parent, "name", "")
    return getattr(ch, "name", "")


class Levels(commands.Cog):
    def __init__(self, bot: HavenBot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, m: discord.Message) -> None:
        if m.author.bot or not m.guild or m.guild.id != self.bot.guild_id or not isinstance(m.author, discord.Member):
            return
        if kanaalnaam(m.channel) in GEEN_XP:
            return
        db = self.bot.db
        lid = db.lid(m.author.id)
        berichten = lid["berichten"] + 1
        nu = time.time()
        if not mag_xp_krijgen(lid["laatst_xp"], nu):
            db.lid_zet(m.author.id, berichten=berichten)
        else:
            oud_level = level_voor_xp(lid["xp"])
            xp = lid["xp"] + xp_voor_bericht()
            db.lid_zet(m.author.id, xp=xp, laatst_xp=nu, berichten=berichten)
            nieuw_level = level_voor_xp(xp)
            if rol_voor_level(nieuw_level) != rol_voor_level(oud_level):
                await self.zet_levelrol(m.author, nieuw_level, m.channel)
        if berichten == 5:
            invites = self.bot.get_cog("Invites")
            if invites:
                await invites.lid_actief(m.author)

    async def zet_levelrol(self, lid: discord.Member, level: int, kanaal) -> None:
        naam = rol_voor_level(level)
        nieuw = self.bot.rol(naam)
        oud = [r for r in lid.roles if r.name in ALLE_LEVELROLLEN and r.name != naam]
        if oud:
            await lid.remove_roles(*oud, reason="Nieuw level")
        if nieuw and nieuw not in lid.roles:
            await lid.add_roles(nieuw, reason=f"Level {level}")
        if naam in MELDING:
            await kanaal.send(embed=self.bot.embed("community", f"🎉 Level {level}: {naam}!", f"{lid.mention} is nu **{naam}**. {MELDING[naam]}"))
        if naam == "Haven Legende":
            invites = self.bot.get_cog("Invites")
            if invites:
                await invites.beloon(lid, "legende", "Sniper Proef", dagen=30)

    @app_commands.command(name="level", description="Bekijk je level en XP")
    async def level(self, interaction: discord.Interaction, lid: discord.Member | None = None) -> None:
        lid = lid or interaction.user
        xp = self.bot.db.lid(lid.id)["xp"]
        level, binnen, nodig = voortgang(xp)
        vol = int(binnen / nodig * 20)
        volgende = next((d for d, _ in reversed(LEVEL_ROLLEN) if d > level), None)
        e = self.bot.embed("community", f"📈 {lid.display_name}: level {level}", f"`{'▰' * vol}{'▱' * (20 - vol)}` {binnen}/{nodig} XP\nRol: **{rol_voor_level(level)}**")
        if volgende:
            e.add_field(name="Volgende rol", value=f"{rol_voor_level(volgende)} op level {volgende}")
        await antwoord(interaction, embed=e)


async def setup(bot: HavenBot) -> None:
    await bot.add_cog(Levels(bot))

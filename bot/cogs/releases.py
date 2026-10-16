"""Releasekalender: /release plaatst een release, maakt de releaseavond aan en houdt een overzicht bij."""

from __future__ import annotations

import datetime as dt
import time

import discord
from discord import app_commands
from discord.ext import commands, tasks

from bot.kern import TIJDZONE, HavenBot, antwoord

AVOND_UUR = 20
OVERZICHT_MAX = 10


def overzicht_regels(rijen: list, nu: float) -> list[str]:
    """Eén regel per komende release, de eerstvolgende bovenaan."""
    regels = []
    for r in rijen:
        if r["tijd"] < nu - 86400:  # tot een dag na de release blijft hij staan
            continue
        stempel = int(r["tijd"])
        wanneer = f"<t:{stempel}:{'f' if r['met_tijd'] else 'D'}>"
        naam = f"[{r['naam']}]({r['bericht_url']})" if r["bericht_url"] else r["naam"]
        regels.append(f"**{naam}**\n{wanneer} · <t:{stempel}:R>" + (f" · limiet {r['limiet']}" if r["limiet"] else ""))
    return regels[:OVERZICHT_MAX]


class Releases(commands.Cog):
    def __init__(self, bot: HavenBot):
        self.bot = bot

    async def cog_load(self) -> None:
        self.dagelijks.start()

    async def cog_unload(self) -> None:
        self.dagelijks.cancel()

    @app_commands.command(name="release", description="Zet een release in de kalender (alleen team)")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(
        naam="Naam van de set of het product", datum="JJJJ-MM-DD", tijd="UU:MM (optioneel)", winkels="Bij welke winkels",
        limiet="Limiet per persoon", afbeelding="Link naar een afbeelding", releaseavond="Maak een releaseavond op de stage om 20:00",
    )
    async def release(
        self, interaction: discord.Interaction, naam: str, datum: str, winkels: str,
        tijd: str | None = None, limiet: str | None = None, afbeelding: str | None = None, releaseavond: bool = True,
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
        await interaction.response.defer(ephemeral=True)
        stempel = int(moment.timestamp())
        wanneer = f"<t:{stempel}:F> (<t:{stempel}:R>)" if tijd else f"<t:{stempel}:D> (<t:{stempel}:R>)"
        e = self.bot.embed("release", f"📅 {naam}", f"**Wanneer:** {wanneer}\n**Waar:** {winkels}" + (f"\n**Limiet:** {limiet}" if limiet else ""))
        e.set_author(name="PokeTCG Haven • Release")
        if afbeelding:
            e.set_image(url=afbeelding)
        avond = await self.releaseavond(naam, moment) if releaseavond else None
        if avond:
            e.add_field(name="🎉  Releaseavond", value=f"Om **{AVOND_UUR}:00** samen uitpakken op de stage. [Zet hem in je agenda]({avond.url})", inline=False)
        ping = self.bot.rol("Release-ping")
        m = await ch.send(content=ping.mention if ping else None, embed=e, allowed_mentions=discord.AllowedMentions(roles=True))
        thread = await m.create_thread(name=f"Releasedraad: {naam}"[:90])
        await thread.send(embed=self.bot.embed("release", "💬 Releasedraad", "Deel hier je tips: welke winkels pakken vroeg uit, hoe lang is de rij en wat is er nog op voorraad?"))
        self.bot.db.uitvoeren(
            "INSERT INTO releases (naam, tijd, met_tijd, winkels, limiet, bericht_url) VALUES (?, ?, ?, ?, ?, ?)",
            (naam, moment.timestamp(), 1 if tijd else 0, winkels, limiet, m.jump_url),
        )
        await self.overzicht_bijwerken()
        await antwoord(interaction, f"✅ Release geplaatst: {m.jump_url}" + ("\n🎉 Releaseavond aangemaakt." if avond else ""))

    async def releaseavond(self, naam: str, moment: dt.datetime) -> discord.ScheduledEvent | None:
        """Een Discord-event op de stage om 20:00 op de releasedag (alleen als dat nog in de toekomst ligt)."""
        g, stage = self.bot.guild, self.bot.kanaal("Releaseavond")
        start = moment.replace(hour=AVOND_UUR, minute=0)
        if g is None or stage is None or start <= dt.datetime.now(TIJDZONE):
            return None
        soort = discord.EntityType.stage_instance if isinstance(stage, discord.StageChannel) else discord.EntityType.voice
        try:
            return await g.create_scheduled_event(
                name=f"Releaseavond: {naam}"[:100], start_time=start, entity_type=soort, channel=stage,
                privacy_level=discord.PrivacyLevel.guild_only,
                description=f"Samen {naam} uitpakken! Laat je pulls zien en praat mee. Iedereen opent zijn eigen packs.",
            )
        except discord.HTTPException as fout:
            await self.bot.log(f"⚠️ Releaseavond voor {naam} niet aangemaakt: {fout}")
            return None

    async def overzicht_bijwerken(self) -> None:
        """Het overzicht staat altijd onderaan #release-kalender: het oude wordt vervangen door een nieuw."""
        ch = self.bot.kanaal("release-kalender")
        if ch is None:
            return
        rijen = self.bot.db.alle("SELECT * FROM releases ORDER BY tijd")
        regels = overzicht_regels(rijen, time.time())
        e = self.bot.embed(
            "release", "🗓️  Komende releases",
            "\n\n".join(regels) if regels else "Er staan nog geen releases gepland. Zodra er een bekend is, zie je hem hier.",
        )
        e.set_footer(text="Wordt automatisch bijgewerkt • Kies Releases in #rollen voor een melding")
        oud = self.bot.db.kv_lees("releases:overzicht")
        if oud:
            try:
                await (await ch.fetch_message(int(oud))).delete()
            except discord.HTTPException:
                pass
        m = await ch.send(embed=e)
        self.bot.db.kv_schrijf("releases:overzicht", str(m.id))

    @tasks.loop(hours=24)
    async def dagelijks(self) -> None:
        """Eén keer per dag (en bij het opstarten): voorbije releases uit het overzicht halen."""
        if self.bot.db.een("SELECT 1 FROM releases LIMIT 1"):
            await self.overzicht_bijwerken()

    @dagelijks.before_loop
    async def _wacht(self) -> None:
        await self.bot.wait_until_ready()
        await self.bot.setup_klaar.wait()


async def setup(bot: HavenBot) -> None:
    await bot.add_cog(Releases(bot))

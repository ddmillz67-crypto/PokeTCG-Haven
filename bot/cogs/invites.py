"""Invites: wie bracht wie, /invite, en beloningen voor actieve nieuwe leden."""

from __future__ import annotations

import asyncio
import time

import discord
from discord import app_commands
from discord.ext import commands

from bot.kern import HavenBot, antwoord

ACTIEF_BINNEN_DAGEN = 7
BELONING_PROEF = 3        # actieve leden: 7 dagen Sniper Proef
BELONING_AMBASSADEUR = 10  # actieve leden: Haven Ambassadeur


class Invites(commands.Cog):
    def __init__(self, bot: HavenBot):
        self.bot = bot
        self.gebruik: dict[str, int] = {}
        bot.actie("invite:mijn", self.knop)
        bot.planner("rol_weg", self.rol_weg)

    async def cog_load(self) -> None:
        asyncio.create_task(self.vul_cache())

    async def vul_cache(self) -> None:
        await self.bot.wait_until_ready()
        g = self.bot.guild
        if g:
            try:
                self.gebruik = {i.code: i.uses or 0 for i in await g.invites()}
            except discord.HTTPException:
                pass

    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite) -> None:
        self.gebruik[invite.code] = invite.uses or 0

    @commands.Cog.listener()
    async def on_member_join(self, lid: discord.Member) -> None:
        if lid.guild.id != self.bot.guild_id or lid.bot:
            return
        try:
            nu = {i.code: i for i in await lid.guild.invites()}
        except discord.HTTPException:
            return
        gebruikt = next((i for code, i in nu.items() if (i.uses or 0) > self.gebruik.get(code, 0)), None)
        self.gebruik = {code: i.uses or 0 for code, i in nu.items()}
        if gebruikt is None:
            return
        eigenaar = self.bot.db.een("SELECT user_id FROM invites WHERE code = ?", (gebruikt.code,))
        uitnodiger = eigenaar["user_id"] if eigenaar else (gebruikt.inviter.id if gebruikt.inviter else None)
        if uitnodiger and uitnodiger != lid.id:
            self.bot.db.lid_zet(lid.id, uitgenodigd_door=uitnodiger, lid_sinds=time.time())

    async def lid_actief(self, lid: discord.Member) -> None:
        """Aangeroepen bij het 5e bericht van een lid. Telt mee voor de uitnodiger als dat binnen 7 dagen is."""
        rij = self.bot.db.lid(lid.id)
        if not rij["uitgenodigd_door"] or rij["actief_geteld"]:
            return
        if time.time() - (rij["lid_sinds"] or 0) > ACTIEF_BINNEN_DAGEN * 86400:
            return
        self.bot.db.lid_zet(lid.id, actief_geteld=1)
        uitnodiger_id = rij["uitgenodigd_door"]
        aantal = self.bot.db.een("SELECT COUNT(*) AS n FROM leden WHERE uitgenodigd_door = ? AND actief_geteld = 1", (uitnodiger_id,))["n"]
        uitnodiger = lid.guild.get_member(uitnodiger_id)
        if uitnodiger is None:
            return
        if aantal >= BELONING_PROEF:
            await self.beloon(uitnodiger, "invites3", "Sniper Proef", dagen=7)
        if aantal >= BELONING_AMBASSADEUR:
            await self.beloon(uitnodiger, "invites10", "Haven Ambassadeur", dagen=None)

    async def beloon(self, lid: discord.Member, soort: str, rolnaam: str, dagen: int | None) -> None:
        cur = self.bot.db.uitvoeren("INSERT OR IGNORE INTO beloningen VALUES (?, ?)", (lid.id, soort))
        if cur.rowcount == 0:
            return  # deze beloning is al eens gegeven
        rol = self.bot.rol(rolnaam)
        if rol is None:
            return
        await lid.add_roles(rol, reason=f"Beloning: {soort}")
        if dagen:
            self.bot.plan(dagen * 86400, "rol_weg", {"user_id": lid.id, "rol": rolnaam})
        try:
            duur = f" voor {dagen} dagen" if dagen else ""
            await lid.send(embed=self.bot.embed("community", "🎁 Bedankt!", f"Als bedankje krijg je **{rolnaam}**{duur}. Leuk dat je de community laat groeien!"))
        except discord.HTTPException:
            pass
        await self.bot.log(f"🎁 {lid.mention} kreeg {rolnaam}{f' ({dagen} dagen)' if dagen else ''} ({soort}).")

    async def rol_weg(self, data: dict) -> None:
        g = self.bot.guild
        lid = g.get_member(data["user_id"]) if g else None
        rol = self.bot.rol(data["rol"])
        if lid and rol and rol in lid.roles:
            await lid.remove_roles(rol, reason="Tijdelijke beloning afgelopen")

    async def toon(self, interaction: discord.Interaction) -> None:
        lid = interaction.user
        rij = self.bot.db.een("SELECT code FROM invites WHERE user_id = ?", (lid.id,))
        code = rij["code"] if rij else None
        if code is None:
            ch = self.bot.kanaal("start-hier")
            if ch is None:
                await antwoord(interaction, "Invites zijn nog niet beschikbaar.")
                return
            invite = await ch.create_invite(max_age=0, max_uses=0, unique=True, reason=f"Persoonlijke invite voor {lid}")
            code = invite.code
            self.bot.db.uitvoeren("INSERT OR REPLACE INTO invites VALUES (?, ?)", (code, lid.id))
            self.gebruik[code] = 0
        totaal = self.bot.db.een("SELECT COUNT(*) AS n FROM leden WHERE uitgenodigd_door = ?", (lid.id,))["n"]
        actief = self.bot.db.een("SELECT COUNT(*) AS n FROM leden WHERE uitgenodigd_door = ? AND actief_geteld = 1", (lid.id,))["n"]
        e = self.bot.embed(
            "community", "💌 Jouw uitnodigingslink",
            f"https://discord.gg/{code}\n\nUitgenodigd: **{totaal}** · actief geworden: **{actief}**\n\n"
            f"Een uitgenodigd lid telt als actief na 5 berichten in de eerste week.\n"
            f"• {BELONING_PROEF} actieve leden: 7 dagen gratis Haven Sniper\n• {BELONING_AMBASSADEUR} actieve leden: de rol Haven Ambassadeur",
        )
        await antwoord(interaction, embed=e)

    async def knop(self, interaction: discord.Interaction, _: str) -> None:
        await self.toon(interaction)

    @app_commands.command(name="invite", description="Krijg je persoonlijke uitnodigingslink / Get your invite link")
    async def invite(self, interaction: discord.Interaction) -> None:
        await self.toon(interaction)


async def setup(bot: HavenBot) -> None:
    await bot.add_cog(Invites(bot))

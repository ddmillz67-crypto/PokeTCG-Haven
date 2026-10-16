"""De keuzemenu's in #rollen: interesses, regio en meldingen."""

from __future__ import annotations

import discord
from discord.ext import commands

from bot.kern import HavenBot, antwoord


class Rollen(commands.Cog):
    def __init__(self, bot: HavenBot):
        self.bot = bot
        # Welke rollen bij welk menu horen, rechtstreeks uit inhoud/05-rollen.yaml.
        self.menus: dict[str, list[str]] = {}
        ki = bot.inhoud.get("rollen")
        for b in ki.berichten if ki else ():
            if b.menu:
                self.menus[b.menu.actie] = [o.rol for o in b.menu.opties]
        bot.actie("rollen", self.kies)

    async def kies(self, interaction: discord.Interaction, soort: str) -> None:
        opties = self.menus.get(f"rollen:{soort}", [])
        gekozen = set((interaction.data or {}).get("values", []))
        lid = interaction.user
        erbij, eraf = [], []
        for naam in opties:
            rol = self.bot.rol(naam)
            if rol is None:
                continue
            if naam in gekozen and rol not in lid.roles:
                erbij.append(rol)
            elif naam not in gekozen and rol in lid.roles:
                eraf.append(rol)
        if erbij:
            await lid.add_roles(*erbij, reason="Gekozen in #rollen")
        if eraf:
            await lid.remove_roles(*eraf, reason="Uitgezet in #rollen")
        nu = ", ".join(sorted(gekozen)) or "niets"
        await antwoord(interaction, f"✅ Opgeslagen. Je hebt nu: **{nu}**.\n🇬🇧 Saved.")


async def setup(bot: HavenBot) -> None:
    await bot.add_cog(Rollen(bot))

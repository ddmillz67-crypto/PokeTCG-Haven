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
        self.labels: dict[str, str] = {}
        ki = bot.inhoud.get("rollen")
        for b in ki.berichten if ki else ():
            if b.menu:
                self.menus[b.menu.actie] = [o.rol for o in b.menu.opties]
                for o in b.menu.opties:
                    self.labels[o.rol] = f"{o.emoji}  {o.label}" if o.emoji else o.label
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
        heeft = ({r.name for r in lid.roles} | {r.name for r in erbij}) - {r.name for r in eraf}
        await antwoord(interaction, embed=self.trainerskaart(lid, heeft))

    def trainerskaart(self, lid: discord.Member, heeft: set[str]) -> discord.Embed:
        """Het overzicht van alles wat het lid in #rollen heeft gekozen."""
        e = self.bot.embed("community", "✅  Opgeslagen! Dit is jouw trainerskaart", "Je kunt het altijd weer aanpassen met de menu's in {#rollen}.\n\u200b")
        e.set_thumbnail(url=lid.display_avatar.url)
        for actie, kop in KAARTRIJEN:
            gekozen = [self.labels.get(r, r) for r in self.menus.get(actie, []) if r in heeft]
            e.add_field(name=kop, value="\n".join(gekozen) if gekozen else "*nog niets gekozen*", inline=True)
        return e


KAARTRIJEN = (
    ("rollen:interesses", "🃏  Verzamelt"),
    ("rollen:regio", "📍  Regio"),
    ("rollen:pings", "🔔  Meldingen"),
)


async def setup(bot: HavenBot) -> None:
    await bot.add_cog(Rollen(bot))

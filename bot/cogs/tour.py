"""De persoonlijke server-tour: alleen zichtbaar voor het lid, met Vorige en Volgende."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from bot.kern import HavenBot, antwoord
from haven.inhoud import PREFIX, afbeelding_url, laad_yaml


class Tour(commands.Cog):
    def __init__(self, bot: HavenBot):
        self.bot = bot
        self.data = laad_yaml("tour.yaml")
        bot.actie("tour:start", self.start)
        bot.actie("tour:pagina", self.pagina)
        bot.actie("tour:klaar", self.klaar)
        bot.actie("tour:kwijt", self.kwijt)

    def scherm(self, nummer: int, lid: discord.Member) -> tuple[discord.Embed, discord.ui.View]:
        paginas = self.data["paginas"]
        p = paginas[nummer]
        kanaal = p.get("kanaal")
        embed = self.bot.embed("merk", p["titel"], p["tekst"])
        if p.get("beeld"):
            embed.set_image(url=afbeelding_url(p["beeld"]))
        embed.set_footer(text=f"Stap {nummer + 1} van {len(paginas)}  ·  PokeTCG Haven")
        view = discord.ui.View(timeout=None)
        if nummer > 0:
            view.add_item(discord.ui.Button(label="Vorige", emoji="⬅️", custom_id=f"{PREFIX}tour:pagina:{nummer - 1}"))
        ctx = self.bot.context()
        if kanaal and kanaal in ctx.kanalen:
            view.add_item(discord.ui.Button(label=f"Ga naar #{kanaal}", url=f"https://discord.com/channels/{ctx.guild_id}/{ctx.kanalen[kanaal]}"))
        if nummer + 1 < len(paginas):
            view.add_item(discord.ui.Button(label="Volgende", emoji="➡️", style=discord.ButtonStyle.primary, custom_id=f"{PREFIX}tour:pagina:{nummer + 1}"))
        else:
            view.add_item(discord.ui.Button(label="Afronden", emoji="🎉", style=discord.ButtonStyle.success, custom_id=f"{PREFIX}tour:klaar"))
        return embed, view

    async def start(self, interaction: discord.Interaction, _: str = "") -> None:
        embed, view = self.scherm(0, interaction.user)
        await antwoord(interaction, embed=embed, view=view)

    async def pagina(self, interaction: discord.Interaction, rest: str) -> None:
        nummer = max(0, min(int(rest or 0), len(self.data["paginas"]) - 1))
        embed, view = self.scherm(nummer, interaction.user)
        await interaction.response.edit_message(embed=embed, view=view)

    async def klaar(self, interaction: discord.Interaction, _: str) -> None:
        lid = interaction.user
        a = self.data["afsluiting"]
        slot = self.bot.embed("community", a["titel"], a["tekst"])
        if a.get("beeld"):
            slot.set_image(url=afbeelding_url(a["beeld"]))
        view = discord.ui.View(timeout=None)
        for label, kanaal, emoji in (("Stel je voor", "voorstellen", "👋"), ("Kies je rollen", "rollen", "🎛️")):
            knop = self.bot.kanaal_knop(label, kanaal, emoji)
            if knop:
                view.add_item(knop)
        await interaction.response.edit_message(embed=slot, view=view if view.children else None)
        rol = self.bot.rol("Wegwijs")
        if rol and rol not in lid.roles:
            await lid.add_roles(rol, reason="Server-tour afgerond")
        if not self.bot.db.lid(lid.id)["tour_klaar"]:
            self.bot.db.lid_zet(lid.id, tour_klaar=1)
            ch = self.bot.kanaal("voorstellen")
            if ch:
                e = self.bot.embed(
                    "community",
                    "👋 Welkom in de community!",
                    f"{lid.mention} heeft de tour afgerond! 🎉\n\n"
                    "Vertel ons **wie je bent** en **wat je verzamelt**. In de vastgepinde kanaalkaart staat een voorbeeld.",
                )
                await ch.send(content=lid.mention, embed=e, allowed_mentions=discord.AllowedMentions(users=True))

    async def kwijt(self, interaction: discord.Interaction, _: str) -> None:
        k = self.data["kwijt"]
        await antwoord(interaction, embed=self.bot.embed("merk", k["titel"], "\n".join(k["regels"])))

    @app_commands.command(name="tour", description="Start je persoonlijke tour door de server")
    async def tour(self, interaction: discord.Interaction) -> None:
        await self.start(interaction)


async def setup(bot: HavenBot) -> None:
    await bot.add_cog(Tour(bot))

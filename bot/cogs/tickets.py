"""Tickets: een privégesprek (privé-thread) in #tickets tussen het lid en het team."""

from __future__ import annotations

import io
import time

import discord
from discord.ext import commands

from bot.kern import PREFIX, HavenBot, antwoord

CATEGORIEEN = {
    "hulp": ("❓ Hulp", "Vertel waar je mee zit; een moderator helpt je zo snel mogelijk.\n🇬🇧 Tell us what's up; a moderator will help you soon."),
    "store": ("🛒 Store en betaling", "Vertel wat je gekocht hebt (of wilt kopen) en wat er niet lukt. Deel nooit wachtwoorden of betaalgegevens."),
    "melding": ("🚩 Melding", "Wat is er gebeurd, wie was erbij en in welk kanaal? Screenshots helpen. Alleen het team ziet dit."),
    "giveaway": ("🎁 Giveaway gewonnen", "Gefeliciteerd! Stuur je naam en verzendadres in NL of BE. Ben je jonger dan 18? Laat dan een ouder of voogd hier bevestigen dat het goed is. We verwijderen je adres na verzending."),
    "partner": ("🏪 Partner worden", "Vertel over je winkel: naam, plaats en website of socials. We nemen snel contact op."),
}


class Tickets(commands.Cog):
    def __init__(self, bot: HavenBot):
        self.bot = bot
        bot.actie("ticket", self.knop)

    async def knop(self, interaction: discord.Interaction, rest: str) -> None:
        if rest == "sluit":
            await self.sluit(interaction)
        elif rest in CATEGORIEEN:
            await self.open(interaction, rest)

    async def open(self, interaction: discord.Interaction, categorie: str) -> None:
        lid = interaction.user
        parent = self.bot.kanaal("tickets")
        if parent is None:
            await antwoord(interaction, "Het ticketkanaal bestaat nog niet. Stuur een moderator een bericht.")
            return
        bestaand = self.bot.db.een(
            "SELECT thread_id FROM tickets WHERE user_id = ? AND categorie = ? AND open = 1", (lid.id, categorie)
        )
        if bestaand:
            await antwoord(interaction, f"Je hebt al een open ticket: <#{bestaand['thread_id']}>")
            return
        titel, uitleg = CATEGORIEEN[categorie]
        thread = await parent.create_thread(
            name=f"{categorie}-{lid.display_name}"[:90], type=discord.ChannelType.private_thread, invitable=False,
            reason=f"Ticket {categorie}",
        )
        await thread.add_user(lid)
        self.bot.db.uitvoeren(
            "INSERT INTO tickets (thread_id, user_id, categorie, tijd) VALUES (?, ?, ?, ?)", (thread.id, lid.id, categorie, time.time())
        )
        mod = self.bot.rol("Mod")
        view = discord.ui.View(timeout=None)
        view.add_item(discord.ui.Button(label="Ticket sluiten / Close", emoji="🔒", style=discord.ButtonStyle.danger, custom_id=f"{PREFIX}ticket:sluit"))
        await thread.send(
            content=f"{lid.mention} {mod.mention if mod else ''}",
            embed=self.bot.embed("merk", titel, uitleg),
            view=view,
            allowed_mentions=discord.AllowedMentions(users=True, roles=True),
        )
        await antwoord(interaction, f"✅ Je ticket staat klaar: {thread.mention}")
        await self.bot.log(f"🎫 Nieuw ticket ({categorie}) van {lid} in {thread.mention}")

    async def sluit(self, interaction: discord.Interaction) -> None:
        thread = interaction.channel
        rij = self.bot.db.een("SELECT * FROM tickets WHERE thread_id = ?", (getattr(thread, "id", 0),))
        if rij is None or not isinstance(thread, discord.Thread):
            await antwoord(interaction, "Dit is geen ticket.")
            return
        if interaction.user.id != rij["user_id"] and not self.bot.is_team(interaction.user):
            await antwoord(interaction, "Alleen de maker van het ticket of het team kan het sluiten.")
            return
        await interaction.response.send_message("🔒 Ticket gesloten. Bedankt!")
        regels = [f"[{m.created_at:%Y-%m-%d %H:%M}] {m.author}: {m.content}" async for m in thread.history(limit=500, oldest_first=True)]
        logkanaal = self.bot.kanaal("staff-logs")
        if logkanaal:
            bestand = discord.File(io.BytesIO("\n".join(regels).encode()), filename=f"transcript-{thread.name}.txt")
            await logkanaal.send(f"📄 Ticket gesloten: {thread.name} (door {interaction.user})", file=bestand)
        self.bot.db.uitvoeren("UPDATE tickets SET open = 0 WHERE thread_id = ?", (thread.id,))
        await thread.edit(archived=True, locked=True)


async def setup(bot: HavenBot) -> None:
    await bot.add_cog(Tickets(bot))

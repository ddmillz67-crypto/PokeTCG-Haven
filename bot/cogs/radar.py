"""Winkel-radar: leden melden voorraad in fysieke winkels met /meld, met een maandelijkse Hall of Fame."""

from __future__ import annotations

import datetime as dt

import discord
from discord import app_commands
from discord.ext import commands, tasks

from bot.kern import TIJDZONE, HavenBot, antwoord
from haven.alerts import VERTRAGING_GRATIS_SECONDEN

REGIO = ["Noord-NL", "Midden-NL", "Zuid-NL", "Vlaanderen", "Brussel", "Wallonië"]
DUIM_OMLAAG = "👎"
WEG_BIJ = 2
MAANDEN = ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus", "september", "oktober", "november", "december"]
MEDAILLES = ["🥇", "🥈", "🥉"]


def vorige_maand(nu: dt.datetime) -> tuple[float, float, str, str]:
    """(begin, eind, sleutel, naam) van de maand vóór `nu`, in de tijdzone van `nu`."""
    begin_deze = nu.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    begin_vorige = (begin_deze - dt.timedelta(days=1)).replace(day=1)
    return begin_vorige.timestamp(), begin_deze.timestamp(), begin_vorige.strftime("%Y-%m"), f"{MAANDEN[begin_vorige.month - 1]} {begin_vorige.year}"


class Radar(commands.Cog):
    def __init__(self, bot: HavenBot):
        self.bot = bot
        bot.planner("radar", self.vertraagd)

    async def cog_load(self) -> None:
        self.hall_of_fame.start()

    async def cog_unload(self) -> None:
        self.hall_of_fame.cancel()

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
        self.bot.db.uitvoeren("INSERT OR IGNORE INTO radar (bericht_id, user_id, tijd) VALUES (?, ?, ?)", (m.id, data["melder"], data["tijd"]))

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
            self.bot.db.uitvoeren("UPDATE radar SET weg = 1 WHERE bericht_id = ?", (m.id,))
            await m.delete()
            await self.bot.log(f"📍 Radarmelding verwijderd na {omlaag} duimen omlaag: {m.embeds[0].title}")


    # -- Hall of Fame: elke 1e van de maand de beste melders van de vorige maand ------------

    def toppers(self, begin: float, eind: float) -> list[tuple[int, int]]:
        rijen = self.bot.db.alle(
            "SELECT user_id, COUNT(*) AS n FROM radar WHERE weg = 0 AND tijd >= ? AND tijd < ? GROUP BY user_id ORDER BY n DESC, MIN(tijd) LIMIT 3",
            (begin, eind),
        )
        return [(r["user_id"], r["n"]) for r in rijen]

    @tasks.loop(hours=1)
    async def hall_of_fame(self) -> None:
        nu = dt.datetime.now(TIJDZONE)
        if nu.day != 1 or nu.hour < 12:
            return
        begin, eind, sleutel, naam = vorige_maand(nu)
        if self.bot.db.kv_lees("radar:hof") == sleutel:
            return
        self.bot.db.kv_schrijf("radar:hof", sleutel)
        top = self.toppers(begin, eind)
        ch = self.bot.kanaal("winkel-radar")
        if not top or ch is None:
            return
        regels = [f"{MEDAILLES[i]}  <@{uid}>  ·  **{n}** melding{'en' if n != 1 else ''}" for i, (uid, n) in enumerate(top)]
        e = self.bot.embed(
            "alert", f"🏆  Hall of Fame · {naam}",
            "Dit zijn de trainers die de meeste **kloppende meldingen** deden. Dankzij jullie scoren anderen hun kaarten!\n\n"
            + "\n".join(regels) + "\n\nZelf ook in de Hall of Fame? Meld voorraad met `/meld`.",
        )
        await ch.send(embed=e)
        await self.bot.log(f"🏆 Radar Hall of Fame {naam} geplaatst.")

    @hall_of_fame.before_loop
    async def _wacht(self) -> None:
        await self.bot.wait_until_ready()
        await self.bot.setup_klaar.wait()


async def setup(bot: HavenBot) -> None:
    await bot.add_cog(Radar(bot))

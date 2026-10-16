"""#pulls, #voorstellen, Pull van de Week en het weekritme."""

from __future__ import annotations

import datetime as dt

import discord
from discord.ext import commands, tasks

from bot.kern import PREFIX, TIJDZONE, HavenBot, antwoord
from haven.inhoud import laad_yaml

STER = "⭐"
TOPPULL_STERREN = 10


def heeft_media(m: discord.Message) -> bool:
    if any((a.content_type or "").startswith(("image/", "video/")) for a in m.attachments):
        return True
    return any(e.type in {"image", "video", "gifv"} or e.image or e.video for e in m.embeds)


class Community(commands.Cog):
    def __init__(self, bot: HavenBot):
        self.bot = bot
        self.vragen = laad_yaml("vragen.yaml")["vragen"]
        bot.actie("pull", self.toestemming)

    async def cog_load(self) -> None:
        self.weekritme.start()

    async def cog_unload(self) -> None:
        self.weekritme.cancel()

    # -- #pulls en #voorstellen -------------------------------------------------

    @commands.Cog.listener()
    async def on_message(self, m: discord.Message) -> None:
        if m.author.bot or not m.guild or m.guild.id != self.bot.guild_id:
            return
        naam = getattr(m.channel, "name", "")
        if naam == "pulls":
            await self.pull(m)
        elif naam == "voorstellen":
            await self.voorstelling(m)

    async def pull(self, m: discord.Message) -> None:
        if not heeft_media(m):
            if self.bot.is_team(m.author):
                return
            await m.delete()
            await m.channel.send(
                f"{m.author.mention} in #pulls mogen alleen foto's en video's. Reageren kan in de thread onder een pull! "
                "🇬🇧 Photos and videos only; reply in the thread.",
                delete_after=10,
            )
            return
        await m.add_reaction(STER)
        thread = await m.create_thread(name=f"Pull van {m.author.display_name}"[:90])
        if not self.bot.db.lid(m.author.id)["eerste_pull"]:
            self.bot.db.lid_zet(m.author.id, eerste_pull=1)
            await thread.send(
                embed=self.bot.embed(
                    "community",
                    "🎉 Je eerste pull!",
                    f"Gefeliciteerd {m.author.mention}, dit is je eerste pull in PokeTCG Haven! Geef de mooiste pulls van anderen een ⭐; "
                    "vrijdag kiezen we de Pull van de Week.",
                )
            )

    async def voorstelling(self, m: discord.Message) -> None:
        if isinstance(m.channel, discord.Thread):
            return
        thread = await m.create_thread(name=f"Welkom {m.author.display_name}!"[:90])
        helper = self.bot.rol("Haven Helper")
        await thread.send(
            content=helper.mention if helper else None,
            embed=self.bot.embed("community", "👋 Welkom!", f"Leuk dat je er bent, {m.author.mention}! Reageer hier gerust om kennis te maken."),
            allowed_mentions=discord.AllowedMentions(roles=True),
        )

    # -- toppulls: toestemming voor de video van de week -------------------------

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, p: discord.RawReactionActionEvent) -> None:
        if str(p.emoji) != STER or p.guild_id != self.bot.guild_id:
            return
        ch = self.bot.get_channel(p.channel_id)
        if getattr(ch, "name", "") != "pulls":
            return
        if self.bot.db.een("SELECT 1 FROM toppulls WHERE bericht_id = ?", (p.message_id,)):
            return
        m = await ch.fetch_message(p.message_id)
        sterren = next((r.count for r in m.reactions if str(r.emoji) == STER), 0) - 1  # min de ster van de bot
        if sterren < TOPPULL_STERREN or m.author.bot:
            return
        self.bot.db.uitvoeren("INSERT OR IGNORE INTO toppulls VALUES (?, ?, NULL)", (m.id, m.author.id))
        view = discord.ui.View(timeout=None)
        view.add_item(discord.ui.Button(label="Ja, graag!", emoji="🎬", style=discord.ButtonStyle.success, custom_id=f"{PREFIX}pull:ja:{m.id}"))
        view.add_item(discord.ui.Button(label="Liever niet", custom_id=f"{PREFIX}pull:nee:{m.id}"))
        doel = m.thread or ch
        await doel.send(
            content=m.author.mention,
            embed=self.bot.embed("community", "🌟 Toppull!", f"Je pull heeft al {sterren} sterren! Mag hij in onze video van de week? Je naam noemen we alleen als je dat wilt."),
            view=view,
        )

    async def toestemming(self, interaction: discord.Interaction, rest: str) -> None:
        keuze, _, bericht = rest.partition(":")
        rij = self.bot.db.een("SELECT user_id FROM toppulls WHERE bericht_id = ?", (int(bericht or 0),))
        if rij is None or rij["user_id"] != interaction.user.id:
            await antwoord(interaction, "Alleen degene die de pull deelde kan dit kiezen.")
            return
        self.bot.db.uitvoeren("UPDATE toppulls SET toestemming = ? WHERE bericht_id = ?", (1 if keuze == "ja" else 0, int(bericht)))
        tekst = "Top, bedankt! 🎬" if keuze == "ja" else "Helemaal goed, we gebruiken hem niet."
        await interaction.response.edit_message(content=tekst, embed=None, view=None)
        if keuze == "ja":
            await self.bot.log(f"🎬 Toestemming voor video: https://discord.com/channels/{self.bot.guild_id}/{interaction.channel.parent_id if isinstance(interaction.channel, discord.Thread) else interaction.channel_id}/{bericht}")

    # -- weekritme --------------------------------------------------------------

    @tasks.loop(minutes=10)
    async def weekritme(self) -> None:
        nu = dt.datetime.now(TIJDZONE)
        week = nu.strftime("%G-%V")
        momenten = [
            (0, 10, "binder", self.binder_monday),
            (0, 11, "packavond", self.pack_avond_event),
            (2, 19, "vraag", self.vraag_van_de_week),
            (4, 18, "pvdw", self.pull_van_de_week),
        ]
        for dag, uur, sleutel, actie in momenten:
            if nu.weekday() == dag and nu.hour >= uur and self.bot.db.kv_lees(f"ritme:{sleutel}") != week:
                self.bot.db.kv_schrijf(f"ritme:{sleutel}", week)
                await actie(nu)

    @weekritme.before_loop
    async def _wacht(self) -> None:
        await self.bot.wait_until_ready()
        await self.bot.setup_klaar.wait()

    async def binder_monday(self, _: dt.datetime) -> None:
        for naam, tekst in (
            ("chat-nlbe", "📒 Het is **Binder Monday**! Laat je mooiste binderpagina zien in {#collecties}."),
            ("chat-en", "📒 It's **Binder Monday**! Show your best binder page in {#collecties}."),
        ):
            ch = self.bot.kanaal(naam)
            if ch:
                await ch.send(embed=self.bot.embed("community", "Binder Monday", tekst))

    async def vraag_van_de_week(self, _: dt.datetime) -> None:
        nummer = int(self.bot.db.kv_lees("vraag:nummer", "0"))
        v = self.vragen[nummer % len(self.vragen)]
        self.bot.db.kv_schrijf("vraag:nummer", str(nummer + 1))
        for naam, tekst, titel in (("chat-nlbe", v["nl"], "💬 Vraag van de week"), ("chat-en", v["en"], "💬 Question of the week")):
            ch = self.bot.kanaal(naam)
            if ch:
                await ch.send(embed=self.bot.embed("community", titel, f"**{tekst}**"))

    async def pack_avond_event(self, nu: dt.datetime) -> None:
        """Maakt op maandag het Discord-event voor de pack-avond van zondag 20:00."""
        g = self.bot.guild
        stage = self.bot.kanaal("Releaseavond")
        if g is None or stage is None:
            return
        zondag = (nu + dt.timedelta(days=6 - nu.weekday())).replace(hour=20, minute=0, second=0, microsecond=0)
        soort = discord.EntityType.stage_instance if isinstance(stage, discord.StageChannel) else discord.EntityType.voice
        await g.create_scheduled_event(
            name="Pack-avond 📦", start_time=zondag, entity_type=soort, channel=stage,
            privacy_level=discord.PrivacyLevel.guild_only,
            description="Samen packs openen! Iedereen opent zijn eigen packs. Neem gerust een vriend mee. / Open packs together!",
        )

    async def pull_van_de_week(self, nu: dt.datetime) -> None:
        ch = self.bot.kanaal("pulls")
        rol = self.bot.rol("Pull van de Week")
        if ch is None:
            return
        beste, beste_sterren = None, 0
        async for m in ch.history(after=nu - dt.timedelta(days=7), limit=None):
            if m.author.bot:
                continue
            sterren = next((r.count - (1 if r.me else 0) for r in m.reactions if str(r.emoji) == STER), 0)
            if sterren > beste_sterren:
                beste, beste_sterren = m, sterren
        if beste is None:
            return
        if rol:
            for oud in list(rol.members):
                await oud.remove_roles(rol, reason="Nieuwe Pull van de Week")
            if isinstance(beste.author, discord.Member):
                await beste.author.add_roles(rol, reason="Pull van de Week")
        e = self.bot.embed(
            "community", "⭐ Pull van de Week",
            f"Gefeliciteerd {beste.author.mention}! Jouw pull kreeg **{beste_sterren} sterren**. [Bekijk de pull]({beste.jump_url})\n"
            "🇬🇧 Congratulations, you won Pull of the Week!",
        )
        if beste.attachments:
            e.set_image(url=beste.attachments[0].url)
        doel = self.bot.kanaal("aankondigingen") or ch
        await doel.send(embed=e)


async def setup(bot: HavenBot) -> None:
    await bot.add_cog(Community(bot))

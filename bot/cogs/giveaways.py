"""Giveaways als gratis wedstrijd, plus de mijlpaal-teller in #giveaways."""

from __future__ import annotations

import datetime as dt
import json
import time

import discord
from discord import app_commands
from discord.ext import commands, tasks

from bot.kern import PREFIX, HavenBot, antwoord
from haven.giveaways import STANDAARD_SCHIFTINGSVRAAG, Inzending, mag_meedoen, rangschikking
from haven.inhoud import afbeelding_url
from haven.levels import GIVEAWAY_LEVEL, level_voor_xp
from haven.mijlpalen import balk, behaalde_mijlpalen, getal, mijlpaal_rond


class Inschrijving(discord.ui.Modal):
    def __init__(self, cog: Giveaways, giveaway_id: int, vraag: str, schiftingsvraag: str):
        super().__init__(title="Doe mee met de giveaway")
        self.cog, self.giveaway_id = cog, giveaway_id
        self.antwoord = discord.ui.TextInput(label="Antwoord op de vraag", placeholder=vraag[:100], max_length=100)
        self.schatting = discord.ui.TextInput(label="Schiftingsvraag (een getal)", placeholder=schiftingsvraag[:100], max_length=9)
        self.add_item(self.antwoord)
        self.add_item(self.schatting)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self.cog.inzenden(interaction, self.giveaway_id, str(self.antwoord), str(self.schatting))


class Giveaways(commands.Cog):
    def __init__(self, bot: HavenBot):
        self.bot = bot
        bot.actie("giveaway:doe", self.doe_mee)

    async def cog_load(self) -> None:
        self.sluiten.start()
        self.teller.start()

    async def cog_unload(self) -> None:
        self.sluiten.cancel()
        self.teller.cancel()

    groep = app_commands.Group(name="giveaway", description="Giveaways beheren", default_permissions=discord.Permissions(manage_guild=True))

    def giveaway_embed(self, g, deelnemers: int, gesloten: bool = False) -> discord.Embed:
        eind = int(g["eind"])
        e = self.bot.embed(
            "community",
            f"🎁 Giveaway: {g['prijs']}",
            f"**Vraag:** {g['vraag']}\n**Schiftingsvraag:** {g['schiftingsvraag']}\n\n"
            + ("Deze giveaway is gesloten." if gesloten else f"Sluit <t:{eind}:R> (<t:{eind}:f>). Meedoen is gratis.")
            ,
        )
        e.add_field(name="Deelnemers", value=str(deelnemers))
        if g["sponsor"]:
            e.add_field(name="Gesponsord door", value=g["sponsor"])
        e.add_field(name="Spelvoorwaarden", value="Zie de vastgepinde berichten in dit kanaal.", inline=False)
        if g["afbeelding"]:
            e.set_image(url=g["afbeelding"])
        return e

    @groep.command(name="start", description="Start een giveaway (wedstrijd met kennisvraag)")
    @app_commands.describe(
        prijs="Wat valt er te winnen", vraag="De kennisvraag", antwoorden="Goede antwoorden, gescheiden door |",
        dagen="Hoeveel dagen open (1-30)", afbeelding="Link naar een foto van de prijs", sponsor="Naam van een sponsorende winkel",
        schiftingsvraag="Eigen schiftingsvraag (standaard: aantal inzendingen)", schifting="Antwoord op je eigen schiftingsvraag",
    )
    async def start(
        self, interaction: discord.Interaction, prijs: str, vraag: str, antwoorden: str, dagen: app_commands.Range[int, 1, 30],
        afbeelding: str | None = None, sponsor: str | None = None, schiftingsvraag: str | None = None, schifting: int | None = None,
    ) -> None:
        if (schiftingsvraag is None) != (schifting is None):
            await antwoord(interaction, "Geef bij een eigen schiftingsvraag ook het antwoord (schifting), of laat ze allebei leeg.")
            return
        ch = self.bot.kanaal("giveaways")
        if ch is None:
            await antwoord(interaction, "#giveaways bestaat nog niet.")
            return
        eind = time.time() + dagen * 86400
        gid = self.bot.db.uitvoeren(
            "INSERT INTO giveaways (prijs, vraag, antwoorden, schiftingsvraag, schifting, eind, kanaal_id, afbeelding, sponsor) VALUES (?,?,?,?,?,?,?,?,?)",
            (prijs, vraag, antwoorden, schiftingsvraag or STANDAARD_SCHIFTINGSVRAAG, schifting, eind, ch.id, afbeelding, sponsor),
        ).lastrowid
        g = self.bot.db.een("SELECT * FROM giveaways WHERE id = ?", (gid,))
        view = discord.ui.View(timeout=None)
        view.add_item(discord.ui.Button(label="Doe mee", emoji="🎁", style=discord.ButtonStyle.success, custom_id=f"{PREFIX}giveaway:doe:{gid}"))
        ping = self.bot.rol("Giveaway-ping")
        m = await ch.send(content=ping.mention if ping else None, embed=self.giveaway_embed(g, 0), view=view, allowed_mentions=discord.AllowedMentions(roles=True))
        self.bot.db.uitvoeren("UPDATE giveaways SET bericht_id = ? WHERE id = ?", (m.id, gid))
        await antwoord(interaction, f"✅ Giveaway {gid} gestart: {m.jump_url}")
        await self.bot.log(f"🎁 Giveaway {gid} gestart door {interaction.user}: {prijs}. Goede antwoorden: ||{antwoorden}||")

    async def doe_mee(self, interaction: discord.Interaction, rest: str) -> None:
        g = self.bot.db.een("SELECT * FROM giveaways WHERE id = ?", (int(rest or 0),))
        if g is None or g["status"] != "open" or g["eind"] < time.time():
            await antwoord(interaction, "Deze giveaway is gesloten.")
            return
        lid = interaction.user
        if self.bot.db.een("SELECT 1 FROM inzendingen WHERE giveaway_id = ? AND user_id = ?", (g["id"], lid.id)):
            await antwoord(interaction, "Je doet al mee. Succes! 🍀")
            return
        dagen = (dt.datetime.now(dt.timezone.utc) - lid.joined_at).total_seconds() / 86400 if lid.joined_at else 0
        reden = mag_meedoen(dagen, level_voor_xp(self.bot.db.lid(lid.id)["xp"]), self.bot.is_team(lid), GIVEAWAY_LEVEL)
        if reden:
            await antwoord(interaction, reden)
            return
        await interaction.response.send_modal(Inschrijving(self, g["id"], g["vraag"], g["schiftingsvraag"]))

    async def inzenden(self, interaction: discord.Interaction, gid: int, tekst: str, schatting: str) -> None:
        try:
            getal_ = int(schatting.replace(".", "").strip())
        except ValueError:
            await antwoord(interaction, "De schiftingsvraag vraagt om een getal. Probeer het opnieuw.")
            return
        g = self.bot.db.een("SELECT * FROM giveaways WHERE id = ?", (gid,))
        if g is None or g["status"] != "open" or g["eind"] < time.time():
            await antwoord(interaction, "Deze giveaway is net gesloten.")
            return
        self.bot.db.uitvoeren("INSERT OR IGNORE INTO inzendingen VALUES (?, ?, ?, ?, ?)", (gid, interaction.user.id, tekst, getal_, time.time()))
        await antwoord(interaction, "✅ Je doet mee! De winnaar maken we bekend in #giveaways. Succes! 🍀")
        await self.werk_embed_bij(g)

    async def werk_embed_bij(self, g, gesloten: bool = False) -> None:
        ch = self.bot.get_channel(g["kanaal_id"])
        if not ch or not g["bericht_id"]:
            return
        aantal = self.bot.db.een("SELECT COUNT(*) AS n FROM inzendingen WHERE giveaway_id = ?", (g["id"],))["n"]
        try:
            m = await ch.fetch_message(g["bericht_id"])
            await m.edit(embed=self.giveaway_embed(g, aantal, gesloten), view=None if gesloten else discord.utils.MISSING)
        except discord.HTTPException:
            pass

    @tasks.loop(minutes=1)
    async def sluiten(self) -> None:
        for g in self.bot.db.alle("SELECT * FROM giveaways WHERE status = 'open' AND eind <= ?", (time.time(),)):
            await self.sluit(g)

    @sluiten.before_loop
    async def _wacht_sluiten(self) -> None:
        await self.bot.wait_until_ready()
        await self.bot.setup_klaar.wait()

    async def sluit(self, g) -> None:
        rijen = self.bot.db.alle("SELECT * FROM inzendingen WHERE giveaway_id = ?", (g["id"],))
        inzendingen = [Inzending(r["user_id"], r["antwoord"], r["schatting"], r["tijd"]) for r in rijen]
        schifting = g["schifting"] if g["schifting"] is not None else len(inzendingen)
        volgorde = rangschikking(inzendingen, g["antwoorden"], schifting)
        self.bot.db.uitvoeren("UPDATE giveaways SET status = 'gesloten' WHERE id = ?", (g["id"],))
        self.bot.db.kv_schrijf(f"giveaway:{g['id']}:volgorde", json.dumps([i.user_id for i in volgorde]))
        self.bot.db.kv_schrijf(f"giveaway:{g['id']}:plek", "0")
        await self.werk_embed_bij(g, gesloten=True)
        await self.maak_winnaar_bekend(g, volgorde[0].user_id if volgorde else None, schifting)

    async def maak_winnaar_bekend(self, g, winnaar: int | None, schifting: int) -> None:
        ch = self.bot.get_channel(g["kanaal_id"])
        if winnaar is None:
            tekst = "Helaas had niemand het goede antwoord. De prijs blijft voor een volgende giveaway!"
        else:
            tekst = (
                f"🎉 Gefeliciteerd <@{winnaar}>! Je wint **{g['prijs']}**.\n"
                f"Het goede antwoord was **{g['antwoorden'].split('|')[0]}**; het antwoord op de schiftingsvraag was **{schifting}**.\n\n"
                "Meld je binnen **72 uur** via {#tickets} met de knop **Giveaway gewonnen**."
            )
        if ch:
            await ch.send(content=f"<@{winnaar}>" if winnaar else None, embed=self.bot.embed("community", f"🏆 Winnaar: {g['prijs']}", tekst))
        await self.bot.log(f"🏆 Giveaway {g['id']} gesloten. Winnaar: {f'<@{winnaar}>' if winnaar else 'niemand'}. Meldt die zich niet binnen 72 uur: `/giveaway volgende {g['id']}`")

    @groep.command(name="volgende", description="Geef de prijs aan de volgende beste inzending (winnaar meldde zich niet)")
    async def volgende(self, interaction: discord.Interaction, giveaway_id: int) -> None:
        g = self.bot.db.een("SELECT * FROM giveaways WHERE id = ? AND status = 'gesloten'", (giveaway_id,))
        if g is None:
            await antwoord(interaction, "Geen gesloten giveaway met dat nummer.")
            return
        volgorde = json.loads(self.bot.db.kv_lees(f"giveaway:{giveaway_id}:volgorde", "[]"))
        plek = int(self.bot.db.kv_lees(f"giveaway:{giveaway_id}:plek", "0")) + 1
        if plek >= len(volgorde):
            await antwoord(interaction, "Er zijn geen goede inzendingen meer over.")
            return
        self.bot.db.kv_schrijf(f"giveaway:{giveaway_id}:plek", str(plek))
        schifting = g["schifting"] if g["schifting"] is not None else self.bot.db.een("SELECT COUNT(*) AS n FROM inzendingen WHERE giveaway_id = ?", (giveaway_id,))["n"]
        await self.maak_winnaar_bekend(g, volgorde[plek], schifting)
        await antwoord(interaction, "✅ Nieuwe winnaar bekendgemaakt.")

    # -- mijlpaal-teller ----------------------------------------------------------

    @tasks.loop(minutes=30)
    async def teller(self) -> None:
        g, ch = self.bot.guild, self.bot.kanaal("giveaways")
        if g is None or ch is None:
            return
        leden = g.member_count or 0
        vorige, volgende, prijs = mijlpaal_rond(leden)
        e = self.bot.embed(
            "community", "🎯 Op weg naar de volgende giveaway",
            f"Bij **{getal(volgende)} leden** geven we weg: **{prijs}**\n\n`{balk(leden)}`\n**{getal(leden)}** van {getal(volgende)} leden\n\n"
            "Ken je iemand die ook verzamelt? Met `/invite` krijg je je eigen link.",
        )
        e.set_image(url=afbeelding_url("mijlpalen"))
        bericht_id = self.bot.db.kv_lees("teller:bericht")
        m = None
        if bericht_id:
            try:
                m = await ch.fetch_message(int(bericht_id))
                await m.edit(embed=e)
            except discord.HTTPException:
                m = None  # verwijderd of onbereikbaar: opnieuw plaatsen
        if m is None:
            m = await ch.send(embed=e)
            self.bot.db.kv_schrijf("teller:bericht", str(m.id))
        await self.mijlpalen(leden)

    @teller.before_loop
    async def _wacht_teller(self) -> None:
        await self.bot.wait_until_ready()
        await self.bot.setup_klaar.wait()

    async def mijlpalen(self, leden: int) -> None:
        behaald = behaalde_mijlpalen(leden)
        ruw = self.bot.db.kv_lees("mijlpalen:gemeld")
        if ruw is None:
            # Eerste keer: wat al behaald is, melden we niet opnieuw.
            self.bot.db.kv_schrijf("mijlpalen:gemeld", json.dumps(behaald))
            return
        gemeld = set(json.loads(ruw))
        for grens in behaald:
            if grens in gemeld:
                continue
            gemeld.add(grens)
            self.bot.db.kv_schrijf("mijlpalen:gemeld", json.dumps(sorted(gemeld)))
            ch = self.bot.kanaal("aankondigingen")
            if ch:
                await ch.send(embed=self.bot.embed("community", f"🎉 We zijn met {getal(grens)}!", "Bedankt allemaal! 🧡\n\nDe mijlpaal-giveaway komt eraan in {#giveaways}."))
            await self.bot.log(f"🎯 Mijlpaal {getal(grens)} leden bereikt. Start de giveaway met `/giveaway start`.")


async def setup(bot: HavenBot) -> None:
    await bot.add_cog(Giveaways(bot))

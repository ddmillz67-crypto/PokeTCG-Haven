"""Restock-alerts: direct voor Sniper, 10 minuten later gratis, Gescoord! en persoonlijke pings."""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import asdict

import discord
from discord import app_commands
from discord.ext import commands, tasks

from bot.kern import PREFIX, HavenBot, antwoord
from haven.alerts import CATEGORIEEN, MONITORS, VERTRAGING_GRATIS_SECONDEN, AlertData, alert_embed

PREMIUM = {"Sniper", "Sniper Proef", "Elite", "Founder"}


class PingKeuze(discord.ui.View):
    def __init__(self, cog: Alerts, huidig: set[str]):
        super().__init__(timeout=300)
        self.cog = cog
        self.menu = discord.ui.Select(
            placeholder="Kies je persoonlijke meldingen", min_values=0, max_values=len(CATEGORIEEN),
            options=[discord.SelectOption(label=v, value=k, default=k in huidig) for k, v in CATEGORIEEN.items()],
        )
        self.menu.callback = self.opslaan
        self.add_item(self.menu)

    async def opslaan(self, interaction: discord.Interaction) -> None:
        db = self.cog.bot.db
        db.uitvoeren("DELETE FROM pings WHERE user_id = ?", (interaction.user.id,))
        for c in self.menu.values:
            db.uitvoeren("INSERT INTO pings VALUES (?, ?)", (interaction.user.id, c))
        gekozen = ", ".join(CATEGORIEEN[c] for c in self.menu.values) or "geen"
        await interaction.response.edit_message(content=f"✅ Opgeslagen: **{gekozen}**. Zet DM's van serverleden aan, anders komt de melding niet aan.", view=None)


class Alerts(commands.Cog):
    def __init__(self, bot: HavenBot):
        self.bot = bot
        bot.actie("alert:gescoord", self.gescoord)
        bot.planner("restock", self.restock)
        self.laatst: dict[str, float] = {}

    async def cog_load(self) -> None:
        self.monitors.start()

    async def cog_unload(self) -> None:
        self.monitors.cancel()

    def knoppen(self, alert_id: int, a: AlertData, *, vertraagd: bool, uitverkocht: bool = False) -> discord.ui.View:
        view = discord.ui.View(timeout=None)
        if not uitverkocht:
            label = f"Naar {a.winkel}" + (" (affiliate)" if a.affiliate else "")
            view.add_item(discord.ui.Button(label=label[:80], url=a.url, emoji="🛒"))
        view.add_item(discord.ui.Button(label="Gescoord!", emoji="🏆", style=discord.ButtonStyle.success, custom_id=f"{PREFIX}alert:gescoord:{alert_id}"))
        if vertraagd and not uitverkocht:
            store = self.bot.kanaal("store")
            if store:
                view.add_item(discord.ui.Button(label="Sneller? Haven Sniper", emoji="⚡", url=f"https://discord.com/channels/{self.bot.guild_id}/{store.id}"))
        return view

    async def plaats_alert(self, a: AlertData) -> int | None:
        sleutel = f"{a.url}|{a.winkel}"
        if time.time() - self.laatst.get(sleutel, 0) < 15 * 60:
            return None  # zelfde product en winkel binnen 15 minuten: geen dubbele alert
        self.laatst[sleutel] = time.time()
        alert_id = self.bot.db.uitvoeren("INSERT INTO alerts (data, berichten, tijd) VALUES (?, '[]', ?)", (json.dumps(asdict(a)), time.time())).lastrowid
        kanaal = self.bot.kanaal("sniper-eu" if a.land == "eu" else "sniper-nlbe")
        berichten = []
        if kanaal:
            m = await kanaal.send(embed=alert_embed(a), view=self.knoppen(alert_id, a, vertraagd=False))
            berichten.append([kanaal.id, m.id, False])
        self.bot.db.uitvoeren("UPDATE alerts SET berichten = ? WHERE id = ?", (json.dumps(berichten), alert_id))
        await self.persoonlijke_pings(a, alert_id)
        if a.land != "eu":
            self.bot.plan(VERTRAGING_GRATIS_SECONDEN, "restock", {"alert_id": alert_id})
        return alert_id

    async def persoonlijke_pings(self, a: AlertData, alert_id: int) -> None:
        g = self.bot.guild
        if g is None:
            return
        for rij in self.bot.db.alle("SELECT user_id FROM pings WHERE categorie = ?", (a.categorie,)):
            lid = g.get_member(rij["user_id"])
            if lid is None or not any(r.name in PREMIUM for r in lid.roles):
                continue
            if a.land == "eu" and not any(r.name in {"Elite", "Founder"} for r in lid.roles):
                continue
            try:
                await lid.send(embed=alert_embed(a), view=self.knoppen(alert_id, a, vertraagd=False))
            except discord.HTTPException:
                pass
            await asyncio.sleep(0.5)

    async def restock(self, data: dict) -> None:
        rij = self.bot.db.een("SELECT * FROM alerts WHERE id = ?", (data["alert_id"],))
        ch = self.bot.kanaal("restocks")
        if rij is None or ch is None or rij["uitverkocht"]:
            return
        a = AlertData(**json.loads(rij["data"]))
        ping = self.bot.rol("Restock-ping")
        m = await ch.send(
            content=ping.mention if ping else None, embed=alert_embed(a, vertraagd=True),
            view=self.knoppen(rij["id"], a, vertraagd=True), allowed_mentions=discord.AllowedMentions(roles=True),
        )
        berichten = json.loads(rij["berichten"]) + [[ch.id, m.id, True]]
        self.bot.db.uitvoeren("UPDATE alerts SET berichten = ? WHERE id = ?", (json.dumps(berichten), rij["id"]))

    async def gescoord(self, interaction: discord.Interaction, rest: str) -> None:
        rij = self.bot.db.een("SELECT * FROM alerts WHERE id = ?", (int(rest or 0),))
        if rij is None:
            await antwoord(interaction, "Deze alert is niet meer bekend.")
            return
        cur = self.bot.db.uitvoeren("INSERT OR IGNORE INTO gescoord VALUES (?, ?)", (rij["id"], interaction.user.id))
        if cur.rowcount == 0:
            await antwoord(interaction, "Je succes staat al in #success. Veel plezier ermee! 🎉")
            return
        a = AlertData(**json.loads(rij["data"]))
        ch = self.bot.kanaal("success")
        if ch:
            e = self.bot.embed("alert", "🏆 Gescoord!", f"{interaction.user.mention} scoorde **{a.product}** bij **{a.winkel}**!")
            e.set_footer(text="Zoekt een vriend dit ook? Gebruik /invite · PokeTCG Haven")
            if a.afbeelding:
                e.set_thumbnail(url=a.afbeelding)
            await ch.send(embed=e)
        await antwoord(interaction, "🎉 Gefeliciteerd! Je succes staat in #success.")

    @app_commands.command(name="alert", description="Plaats een restock-alert (alleen team)")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.choices(
        land=[app_commands.Choice(name="Nederland/België", value="nlbe"), app_commands.Choice(name="Duitsland/Frankrijk (Elite)", value="eu")],
        categorie=[app_commands.Choice(name=v, value=k) for k, v in CATEGORIEEN.items()],
    )
    async def alert(
        self, interaction: discord.Interaction, product: str, winkel: str, url: str,
        land: app_commands.Choice[str], categorie: app_commands.Choice[str],
        prijs: str | None = None, limiet: str | None = None, afbeelding: str | None = None, affiliate: bool = False,
    ) -> None:
        if not url.startswith("https://"):
            await antwoord(interaction, "De link moet met https:// beginnen.")
            return
        a = AlertData(product, winkel, url, prijs or "", limiet or "", land.value, categorie.value, afbeelding or "", affiliate)
        alert_id = await self.plaats_alert(a)
        if alert_id is None:
            await antwoord(interaction, "Deze alert is in de afgelopen 15 minuten al geplaatst.")
        else:
            await antwoord(interaction, f"✅ Alert {alert_id} geplaatst." + (" Over 10 minuten verschijnt hij in #restocks." if land.value != "eu" else ""))

    @app_commands.command(name="uitverkocht", description="Markeer een alert als uitverkocht (alleen team)")
    @app_commands.default_permissions(manage_guild=True)
    async def uitverkocht(self, interaction: discord.Interaction, alert_id: int) -> None:
        rij = self.bot.db.een("SELECT * FROM alerts WHERE id = ?", (alert_id,))
        if rij is None:
            await antwoord(interaction, "Onbekende alert.")
            return
        self.bot.db.uitvoeren("UPDATE alerts SET uitverkocht = 1 WHERE id = ?", (alert_id,))
        a = AlertData(**json.loads(rij["data"]))
        for kanaal_id, bericht_id, vertraagd in json.loads(rij["berichten"]):
            ch = self.bot.get_channel(kanaal_id)
            try:
                m = await ch.fetch_message(bericht_id)
                await m.edit(embed=alert_embed(a, vertraagd=vertraagd, uitverkocht=True), view=self.knoppen(alert_id, a, vertraagd=vertraagd, uitverkocht=True))
            except (discord.HTTPException, AttributeError):
                pass
        await antwoord(interaction, f"✅ Alert {alert_id} staat op uitverkocht.")

    @app_commands.command(name="pings", description="Kies je persoonlijke restock-meldingen (Haven Sniper)")
    async def pings(self, interaction: discord.Interaction) -> None:
        if not any(r.name in PREMIUM for r in interaction.user.roles):
            await antwoord(interaction, "Persoonlijke meldingen zijn onderdeel van Haven Sniper. Kijk in #store.")
            return
        huidig = {r["categorie"] for r in self.bot.db.alle("SELECT categorie FROM pings WHERE user_id = ?", (interaction.user.id,))}
        await antwoord(interaction, "Voor welke producten wil je een DM?", view=PingKeuze(self, huidig))

    @tasks.loop(seconds=60)
    async def monitors(self) -> None:
        """Automatische winkelmonitors (haven/alerts.py). Zolang MONITORS leeg is, doet dit niets."""
        for monitor in MONITORS:
            try:
                for a in await monitor.controleer():
                    await self.plaats_alert(a)
            except Exception as fout:  # noqa: BLE001
                await self.bot.log(f"⚠️ Monitor {monitor.naam} faalde: {fout}")

    @monitors.before_loop
    async def _wacht(self) -> None:
        await self.bot.wait_until_ready()
        await self.bot.setup_klaar.wait()


async def setup(bot: HavenBot) -> None:
    await bot.add_cog(Alerts(bot))

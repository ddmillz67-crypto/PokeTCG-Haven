"""Restock-alerts: direct voor Sniper, 10 minuten later gratis, Gescoord! en persoonlijke pings."""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import asdict

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks

from bot.kern import PREFIX, HavenBot, antwoord
from haven.alerts import CATEGORIEEN, VERTRAGING_GRATIS_SECONDEN, AlertData, alert_embed
from haven.monitors import INTERVAL_SECONDEN, MAX_PAGINAS, USER_AGENT, Winkel, feed_url, normaliseer_url, samenvatting, verwerk

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
        self.standen: dict[str, dict[int, bool]] = {}  # per winkel de voorraad van de vorige ronde
        self.sessie: aiohttp.ClientSession | None = None

    async def cog_load(self) -> None:
        self.sessie = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20), headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        self.monitors.start()

    async def cog_unload(self) -> None:
        self.monitors.cancel()
        if self.sessie:
            await self.sessie.close()

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

    # -- winkelmonitors -----------------------------------------------------------------

    async def haal_producten(self, w: Winkel) -> list[dict]:
        producten: list[dict] = []
        for pagina in range(1, MAX_PAGINAS + 1):
            async with self.sessie.get(feed_url(w, pagina)) as r:
                if r.status != 200:
                    raise RuntimeError(f"de winkel antwoordt met HTTP {r.status}")
                if "json" not in r.headers.get("Content-Type", ""):
                    raise RuntimeError("geen Shopify-winkel (geen productoverzicht gevonden)")
                deel = (await r.json()).get("products", [])
            producten += deel
            if len(deel) < 250:
                break
            await asyncio.sleep(1)
        return producten

    def winkels(self, alleen_aan: bool = True) -> list:
        return self.bot.db.alle("SELECT * FROM winkels" + (" WHERE aan = 1" if alleen_aan else "") + " ORDER BY naam")

    @staticmethod
    def winkel_uit(rij) -> Winkel:
        return Winkel(rij["naam"], rij["url"], rij["land"], rij["collectie"] or "", rij["affiliate"] or "")

    async def controleer_winkel(self, rij) -> None:
        w = self.winkel_uit(rij)
        try:
            producten = await self.haal_producten(w)
        except Exception as fout:  # noqa: BLE001 - één winkel mag de rest niet tegenhouden
            melding = str(fout)[:200] or type(fout).__name__
            if rij["fout"] != melding:  # alleen melden als er iets verandert, niet elke ronde
                await self.bot.log(f"⚠️ Winkel **{w.naam}** niet bereikbaar: {melding}")
            self.bot.db.uitvoeren("UPDATE winkels SET laatst = ?, fout = ? WHERE naam = ?", (time.time(), melding, w.naam))
            return
        alerts, self.standen[w.naam] = verwerk(w, producten, self.standen.get(w.naam))
        totaal, sealed, voorraad = samenvatting(producten)
        self.bot.db.uitvoeren(
            "UPDATE winkels SET laatst = ?, fout = NULL, producten = ?, sealed = ?, op_voorraad = ? WHERE naam = ?",
            (time.time(), totaal, sealed, voorraad, w.naam),
        )
        if rij["fout"]:
            await self.bot.log(f"✅ Winkel **{w.naam}** is weer bereikbaar.")
        for a in alerts[:5]:  # nooit meer dan 5 alerts per winkel per ronde
            await self.plaats_alert(a)

    @tasks.loop(seconds=30)
    async def monitors(self) -> None:
        """Elke 30 seconden: welke winkels zijn aan de beurt (elke INTERVAL_SECONDEN)?"""
        nu = time.time()
        for rij in self.winkels():
            if rij["laatst"] and nu - rij["laatst"] < INTERVAL_SECONDEN and rij["naam"] in self.standen:
                continue
            await self.controleer_winkel(rij)

    @monitors.before_loop
    async def _wacht(self) -> None:
        await self.bot.wait_until_ready()
        await self.bot.setup_klaar.wait()

    winkel_groep = app_commands.Group(name="winkel", description="Winkels voor de restock-monitor (alleen team)", default_permissions=discord.Permissions(manage_guild=True))

    @winkel_groep.command(name="toevoegen", description="Voeg een Shopify-winkel toe aan de restock-monitor")
    @app_commands.describe(
        naam="Naam zoals leden hem zien", url="Webadres, bijvoorbeeld https://winkel.nl", land="Waar de winkel zit",
        collectie="Optioneel: alleen deze collectie volgen (het stukje na /collections/ in de link)",
        affiliate="Optioneel: affiliate-link met {url} op de plek van de productlink",
    )
    @app_commands.choices(land=[app_commands.Choice(name="Nederland/België (Sniper)", value="nlbe"), app_commands.Choice(name="Duitsland/Frankrijk (Elite)", value="eu")])
    async def winkel_toevoegen(
        self, interaction: discord.Interaction, naam: app_commands.Range[str, 2, 40], url: str,
        land: app_commands.Choice[str], collectie: str | None = None, affiliate: str | None = None,
    ) -> None:
        try:
            basis = normaliseer_url(url)
        except ValueError as fout:
            await antwoord(interaction, f"❌ {fout}.")
            return
        if affiliate and "{url}" not in affiliate:
            await antwoord(interaction, "❌ Zet `{url}` in de affiliate-link, op de plek waar de productlink moet komen.")
            return
        await interaction.response.defer(ephemeral=True)
        w = Winkel(naam, basis, land.value, (collectie or "").strip("/ "), affiliate or "")
        try:
            producten = await self.haal_producten(w)
        except Exception as fout:  # noqa: BLE001
            await antwoord(interaction, f"❌ **{naam}** werkt niet met de monitor: {fout}.\nAlleen winkels op Shopify worden ondersteund.")
            return
        totaal, sealed, voorraad = samenvatting(producten)
        self.bot.db.uitvoeren(
            "INSERT OR REPLACE INTO winkels (naam, url, land, collectie, affiliate, aan, laatst, fout, producten, sealed, op_voorraad) VALUES (?, ?, ?, ?, ?, 1, ?, NULL, ?, ?, ?)",
            (w.naam, w.url, w.land, w.collectie, w.affiliate, time.time(), totaal, sealed, voorraad),
        )
        _, self.standen[w.naam] = verwerk(w, producten, None)  # beginstand: vanaf nu telt elke restock
        tip = "" if sealed else "\n\n⚠️ Ik vond nog **geen Pokémon sealed producten**. Klopt de collectie? Je kunt het later opnieuw proberen."
        await antwoord(
            interaction,
            f"✅ **{naam}** staat in de monitor ({'NL/BE' if w.land == 'nlbe' else 'DE/FR'}).\n"
            f"Gevonden: **{totaal}** producten, waarvan **{sealed}** Pokémon sealed (**{voorraad}** op voorraad).\n"
            f"Elke {INTERVAL_SECONDEN // 60} minuten kijk ik opnieuw; gaat iets van uitverkocht naar op voorraad, dan volgt een alert.{tip}",
        )
        await self.bot.log(f"🏪 Winkel **{naam}** toegevoegd aan de monitor door {interaction.user.mention}.")

    @winkel_groep.command(name="lijst", description="Bekijk alle winkels in de restock-monitor")
    async def winkel_lijst(self, interaction: discord.Interaction) -> None:
        rijen = self.winkels(alleen_aan=False)
        if not rijen:
            await antwoord(interaction, "Er staan nog geen winkels in de monitor. Voeg er een toe met `/winkel toevoegen`.")
            return
        regels = []
        for r in rijen:
            if not r["aan"]:
                status = "⏸️ uit"
            elif r["fout"]:
                status = f"⚠️ {r['fout'][:80]}"
            else:
                status = f"✅ {r['sealed'] or 0} sealed, {r['op_voorraad'] or 0} op voorraad"
            wanneer = f" · <t:{int(r['laatst'])}:R>" if r["laatst"] else ""
            regels.append(f"**{r['naam']}** ({'NL/BE' if r['land'] == 'nlbe' else 'DE/FR'}) · {status}{wanneer}\n{r['url']}")
        await antwoord(interaction, embed=self.bot.embed("merk", f"🏪  Restock-monitor · {len(rijen)} winkel(s)", "\n\n".join(regels)[:4000]))

    @winkel_groep.command(name="aanuit", description="Zet een winkel tijdelijk uit of weer aan")
    async def winkel_aanuit(self, interaction: discord.Interaction, naam: str) -> None:
        rij = self.bot.db.een("SELECT aan FROM winkels WHERE naam = ?", (naam,))
        if rij is None:
            await antwoord(interaction, "Onbekende winkel. Bekijk de namen met `/winkel lijst`.")
            return
        nieuw = 0 if rij["aan"] else 1
        self.bot.db.uitvoeren("UPDATE winkels SET aan = ? WHERE naam = ?", (nieuw, naam))
        self.standen.pop(naam, None)  # bij weer aanzetten eerst een nieuwe beginstand
        await antwoord(interaction, f"{'▶️' if nieuw else '⏸️'} **{naam}** staat nu {'aan' if nieuw else 'uit'}.")

    @winkel_groep.command(name="verwijderen", description="Haal een winkel uit de restock-monitor")
    async def winkel_verwijderen(self, interaction: discord.Interaction, naam: str) -> None:
        cur = self.bot.db.uitvoeren("DELETE FROM winkels WHERE naam = ?", (naam,))
        self.standen.pop(naam, None)
        await antwoord(interaction, f"🗑️ **{naam}** is verwijderd." if cur.rowcount else "Onbekende winkel. Bekijk de namen met `/winkel lijst`.")

    @winkel_aanuit.autocomplete("naam")
    @winkel_verwijderen.autocomplete("naam")
    async def _winkelnamen(self, interaction: discord.Interaction, huidig: str) -> list[app_commands.Choice[str]]:
        return [app_commands.Choice(name=r["naam"], value=r["naam"]) for r in self.winkels(alleen_aan=False) if huidig.lower() in r["naam"].lower()][:25]


async def setup(bot: HavenBot) -> None:
    await bot.add_cog(Alerts(bot))

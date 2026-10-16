"""De Haven-bot: verbinding, knoppen-router, planner en hulpfuncties voor alle onderdelen."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import traceback
from collections.abc import Awaitable, Callable
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands

from bot.db import Database
from haven.config import ServerConfig
from haven.huisstijl import FOOTER, KLEUREN
from haven.inhoud import PREFIX, Context, KanaalInhoud, afbeelding_url, vul_in

log = logging.getLogger("haven")
TIJDZONE = ZoneInfo("Europe/Amsterdam")

COGS = [
    "bot.cogs.start",
    "bot.cogs.tour",
    "bot.cogs.rollen",
    "bot.cogs.tickets",
    "bot.cogs.community",
    "bot.cogs.levels",
    "bot.cogs.giveaways",
    "bot.cogs.teller",
    "bot.cogs.markt",
    "bot.cogs.radar",
    "bot.cogs.alerts",
    "bot.cogs.releases",
    "bot.cogs.store",
    "bot.cogs.invites",
]

Handler = Callable[[discord.Interaction, str], Awaitable[None]]
PlanHandler = Callable[[dict], Awaitable[None]]


class HavenBot(commands.Bot):
    def __init__(self, config: ServerConfig, inhoud: dict[str, KanaalInhoud], guild_id: int, db: Database):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        super().__init__(command_prefix=commands.when_mentioned, intents=intents)
        self.config = config
        self.inhoud = inhoud
        self.guild_id = guild_id
        self.db = db
        self.acties: dict[str, Handler] = {}
        self.planners: dict[str, PlanHandler] = {}
        self.na_setup: list[Callable[[], Awaitable[None]]] = []
        self.setup_klaar = asyncio.Event()

    # -- opstarten -------------------------------------------------------------

    async def setup_hook(self) -> None:
        for ext in COGS:
            await self.load_extension(ext)
        guild = discord.Object(id=self.guild_id)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)
        self.tree.on_error = self.commando_fout
        asyncio.create_task(self._planner())

    # -- hulpfuncties ----------------------------------------------------------

    @property
    def guild(self) -> discord.Guild | None:
        return self.get_guild(self.guild_id)

    def kanaal(self, naam: str):
        g = self.guild
        return discord.utils.get(g.channels, name=naam) if g else None

    def rol(self, naam: str) -> discord.Role | None:
        g = self.guild
        return discord.utils.get(g.roles, name=naam) if g else None

    def context(self) -> Context:
        g = self.guild
        return Context(
            guild_id=self.guild_id,
            kanalen={c.name: c.id for c in g.channels} if g else {},
            rollen={r.name: r.id for r in g.roles} if g else {},
        )

    def tekst(self, tekst: str) -> str:
        return vul_in(tekst, self.context())

    def embed(self, soort: str, titel: str, beschrijving: str = "") -> discord.Embed:
        e = discord.Embed(title=titel[:256], description=self.tekst(beschrijving)[:4096] or None, colour=KLEUREN[soort])
        e.set_author(name="PokeTCG Haven", icon_url=afbeelding_url("logo"))
        e.set_footer(text=FOOTER)
        return e

    def is_team(self, lid: discord.Member) -> bool:
        return lid.guild_permissions.manage_messages or any(r.name in self.config.staffrollen for r in lid.roles)

    async def log(self, tekst: str) -> None:
        log.info(tekst)
        ch = self.kanaal("staff-logs")
        if ch:
            try:
                await ch.send(tekst[:2000])
            except discord.HTTPException:
                pass

    # -- knoppen en menu's -----------------------------------------------------

    def actie(self, naam: str, handler: Handler) -> None:
        """Registreert een handler voor custom_id 'haven:<naam>' of 'haven:<naam>:<rest>'."""
        self.acties[naam] = handler

    def zoek_actie(self, custom_id: str) -> tuple[Handler, str] | None:
        if not custom_id.startswith(PREFIX):
            return None
        cid = custom_id[len(PREFIX):]
        beste = None
        for naam, handler in self.acties.items():
            if cid == naam or cid.startswith(naam + ":"):
                if beste is None or len(naam) > len(beste[0]):
                    beste = (naam, handler)
        if beste is None:
            return None
        return beste[1], cid[len(beste[0]) + 1:]

    async def on_interaction(self, interaction: discord.Interaction) -> None:
        if interaction.type != discord.InteractionType.component:
            return
        gevonden = self.zoek_actie((interaction.data or {}).get("custom_id", ""))
        if not gevonden:
            return
        handler, rest = gevonden
        try:
            await handler(interaction, rest)
        except Exception:  # noqa: BLE001 - een fout in één knop mag de bot niet stoppen
            await self.log(f"⚠️ Fout bij knop `{interaction.data.get('custom_id')}`:\n```{traceback.format_exc()[-1500:]}```")
            if not interaction.response.is_done():
                await interaction.response.send_message("Er ging iets mis. Het team is op de hoogte.", ephemeral=True)

    # -- planner: berichten die later moeten (bijv. 10 minuten vertraging) --------

    def planner(self, soort: str, handler: PlanHandler) -> None:
        self.planners[soort] = handler

    def plan(self, seconden: float, soort: str, data: dict) -> None:
        self.db.plan(time.time() + seconden, soort, data)

    async def _planner(self) -> None:
        await self.wait_until_ready()
        await self.setup_klaar.wait()
        while not self.is_closed():
            for rij in self.db.te_doen(time.time()):
                handler = self.planners.get(rij["soort"])
                try:
                    if handler:
                        await handler(json.loads(rij["data"]))
                except Exception:  # noqa: BLE001
                    await self.log(f"⚠️ Fout in geplande taak {rij['soort']}:\n```{traceback.format_exc()[-1500:]}```")
                self.db.gedaan(rij["id"])
            await asyncio.sleep(15)

    async def commando_fout(self, interaction: discord.Interaction, fout: Exception) -> None:
        if isinstance(fout, discord.app_commands.MissingPermissions):
            await antwoord(interaction, "Dit commando is alleen voor het team.")
            return
        await self.log(f"⚠️ Fout in /{interaction.command.name if interaction.command else '?'}: {fout}")
        try:
            await antwoord(interaction, "Er ging iets mis. Het team is op de hoogte.")
        except discord.HTTPException:
            pass


async def antwoord(interaction: discord.Interaction, tekst: str | None = None, *, embed: discord.Embed | None = None, view=None) -> None:
    """Privé-antwoord dat werkt, ook als er al eerder gereageerd is."""
    kw = {"ephemeral": True}
    if embed:
        kw["embed"] = embed
    if view:
        kw["view"] = view
    if interaction.response.is_done():
        await interaction.followup.send(tekst, **kw)
    else:
        await interaction.response.send_message(tekst, **kw)

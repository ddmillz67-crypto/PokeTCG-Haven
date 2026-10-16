"""Stresstest van setup_server.py tegen een nagebootste Discord-server (zonder netwerk).

Controleert dat een eerste run alles aanmaakt en dat een tweede run niets meer
verandert (idempotent), zodat het script veilig na elke stap opnieuw kan draaien.
"""

import asyncio
import itertools
from pathlib import Path

import discord
import pytest

from haven.config import laad_config
from scripts.setup_server import Inrichter

CONFIG = Path(__file__).resolve().parent.parent / "config" / "server.yaml"
_ids = itertools.count(1000)


class NepRol:
    def __init__(self, name, position, **kw):
        self.id = next(_ids)
        self.name = name
        self.position = position
        self.colour = kw.get("colour", discord.Colour(0))
        self.hoist = kw.get("hoist", False)
        self.mentionable = kw.get("mentionable", False)
        self.permissions = kw.get("permissions", discord.Permissions.none())

    def __hash__(self):
        return self.id

    def __eq__(self, other):
        return getattr(other, "id", None) == self.id

    def __lt__(self, other):
        return self.position < other.position

    def __ge__(self, other):
        return self.position >= other.position

    async def edit(self, **kw):
        for k, v in kw.items():
            if k != "reason":
                setattr(self, k, v)


class NepKanaal:
    def __init__(self, name, soort, category=None, overwrites=None, topic=None, slowmode_delay=0, tags=()):
        self.id = next(_ids)
        self.name = name
        self.soort = soort
        self.category_id = category.id if category else None
        self.overwrites = dict(overwrites or {})
        self.topic = topic
        self.slowmode_delay = slowmode_delay
        self.available_tags = list(tags)

    async def edit(self, **kw):
        kw.pop("reason", None)
        if "category" in kw:
            self.category_id = kw.pop("category").id
        for k, v in kw.items():
            setattr(self, k, v)


class NepCategorie(discord.CategoryChannel):
    """Subklasse zodat isinstance(..., CategoryChannel) klopt, zonder Discord-state."""

    def __init__(self, name, overwrites):
        self.id = next(_ids)
        self.name = name
        self._nep_overwrites = dict(overwrites)

    @property
    def overwrites(self):
        return self._nep_overwrites

    async def edit(self, **kw):
        if "overwrites" in kw:
            self._nep_overwrites = dict(kw["overwrites"])


class NepLid:
    def __init__(self, top_role):
        self.id = next(_ids)
        self.top_role = top_role
        self.guild_permissions = discord.Permissions(administrator=True)

    def __hash__(self):
        return self.id


class NepServer:
    def __init__(self):
        self.default_role = NepRol("@everyone", 0)
        botrol = NepRol("PokeTCG Haven", 1, permissions=discord.Permissions(administrator=True))
        self.roles = [self.default_role, botrol]
        self.me = NepLid(botrol)
        self.features: list[str] = []
        self.categories: list[NepCategorie] = []
        self.overige: list[NepKanaal] = []
        self.automod: list[str] = []
        self.verification_level = discord.VerificationLevel.none
        self.explicit_content_filter = discord.ContentFilter.disabled
        self.default_notifications = discord.NotificationLevel.all_messages
        self.api_calls = 0

    @property
    def channels(self):
        return [*self.categories, *self.overige]

    async def edit(self, **kw):
        self.api_calls += 1
        for k, v in kw.items():
            if k != "reason":
                setattr(self, k, v)

    async def create_role(self, name, colour, hoist, mentionable, permissions, reason):
        self.api_calls += 1
        for r in self.roles:
            if r.position >= 1:
                r.position += 1
        rol = NepRol(name, 1, colour=colour, hoist=hoist, mentionable=mentionable, permissions=permissions)
        self.roles.append(rol)
        return rol

    async def edit_role_positions(self, positions, reason):
        self.api_calls += 1
        for rol, pos in positions.items():
            rol.position = pos

    async def create_category(self, name, overwrites, reason):
        self.api_calls += 1
        cat = NepCategorie(name, overwrites)
        self.categories.append(cat)
        return cat

    async def _kanaal(self, name, soort, category, overwrites, topic=None, slowmode_delay=0, tags=()):
        self.api_calls += 1
        ch = NepKanaal(name, soort, category, overwrites, topic, slowmode_delay, tags)
        self.overige.append(ch)
        return ch

    async def create_text_channel(self, name, *, category, overwrites, reason, topic, slowmode_delay, news):
        return await self._kanaal(name, "news" if news else "text", category, overwrites, topic, slowmode_delay)

    async def create_forum(self, name, *, category, overwrites, reason, topic, slowmode_delay, available_tags):
        return await self._kanaal(name, "forum", category, overwrites, topic, slowmode_delay, available_tags)

    async def create_voice_channel(self, name, *, category, overwrites, reason):
        return await self._kanaal(name, "voice", category, overwrites)

    async def create_stage_channel(self, name, *, category, overwrites, reason):
        return await self._kanaal(name, "stage", category, overwrites)

    async def fetch_automod_rules(self):
        return [type("Regel", (), {"name": n}) for n in self.automod]

    async def fetch_channels(self):
        return self.channels

    async def create_automod_rule(self, *, name, **kw):
        self.api_calls += 1
        self.automod.append(name)


def draai(server, stap, dry_run=False):
    config = laad_config(CONFIG)
    inrichter = Inrichter(server, config, stap, dry_run)
    asyncio.run(inrichter.uitvoeren())
    return inrichter


def test_stap_0_maakt_rollen_staffkanaal_en_automod():
    server = NepServer()
    eerste = draai(server, 0)
    namen = {r.name for r in server.roles}
    assert {"Admin", "Mod", "Sniper", "Elite", "NL/BE", "EN", "Release-ping"} <= namen
    assert [c.name for c in server.categories] == ["🔒 STAFF"]
    assert [c.name for c in server.overige] == ["staff-logs"]
    assert server.automod == ["Haven: scam-woorden", "Haven: invites", "Haven: mention-spam", "Haven: spam"]
    assert server.verification_level == discord.VerificationLevel.medium
    assert eerste.waarschuwingen == []


def test_rollen_staan_in_config_volgorde_onder_de_bot():
    server = NepServer()
    draai(server, 0)
    config = laad_config(CONFIG)
    gesorteerd = [r.name for r in sorted(server.roles, key=lambda r: r.position, reverse=True)]
    eigen = [n for n in gesorteerd if n not in {"@everyone", "PokeTCG Haven"}]
    assert eigen == [r.naam for r in config.rollen]
    assert all(r.position < server.me.top_role.position for r in server.roles if r.name in eigen)


def test_tweede_run_verandert_niets():
    server = NepServer()
    draai(server, 24)
    calls = server.api_calls
    tweede = draai(server, 24)
    assert tweede.wijzigingen == [], tweede.wijzigingen
    assert server.api_calls == calls


def test_dry_run_verandert_niets():
    server = NepServer()
    plan = draai(server, 24, dry_run=True)
    assert plan.wijzigingen, "dry-run hoort de geplande wijzigingen te tonen"
    assert server.api_calls == 0
    assert [r.name for r in server.roles] == ["@everyone", "PokeTCG Haven"]


def test_stap_voor_stap_bouwen_komt_uit_op_hetzelfde_als_alles_ineens():
    stapsgewijs = NepServer()
    for stap in range(0, 25):
        draai(stapsgewijs, stap)
    ineens = NepServer()
    draai(ineens, 24)
    assert sorted(c.name for c in stapsgewijs.channels) == sorted(c.name for c in ineens.channels)


def test_zonder_community_worden_news_en_stage_vervangen_met_waarschuwing():
    server = NepServer()
    resultaat = draai(server, 24)
    soorten = {c.name: c.soort for c in server.overige}
    assert soorten["aankondigingen"] == "text"
    assert soorten["Releaseavond"] == "voice"
    assert len(resultaat.waarschuwingen) == 2


def test_met_community_worden_news_en_stage_echt_aangemaakt():
    server = NepServer()
    server.features = ["COMMUNITY"]
    resultaat = draai(server, 24)
    soorten = {c.name: c.soort for c in server.overige}
    assert soorten["aankondigingen"] == "news"
    assert soorten["Releaseavond"] == "stage"
    assert resultaat.waarschuwingen == []


def test_handmatig_gewijzigde_rechten_worden_hersteld():
    server = NepServer()
    draai(server, 24)
    premium = next(c for c in server.overige if c.name == "sniper-nlbe")
    premium.overwrites = {server.default_role: discord.PermissionOverwrite(view_channel=True)}
    herstel = draai(server, 24)
    assert any("sniper-nlbe" in w for w in herstel.wijzigingen)
    assert premium.overwrites[server.default_role].view_channel is False


def test_alle_24_tekstkanalen_plus_voice_na_volledige_build():
    server = NepServer()
    draai(server, 24)
    tekst = [c for c in server.overige if c.soort in {"text", "news", "forum"} and c.name != "staff-logs"]
    assert len(tekst) == 24
    assert {c.name for c in server.overige if c.soort in {"voice", "stage"}} == {"Lounge NL/BE", "Lounge EN", "Releaseavond"}

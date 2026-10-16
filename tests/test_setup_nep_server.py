"""Stresstest van setup_server.py tegen een nagebootste Discord-server (zonder netwerk).

Controleert dat een run aanmaakt wat het plan vraagt en dat een tweede run niets meer
verandert (idempotent), zodat het script veilig na elke stap opnieuw kan draaien.
"""

import asyncio
import itertools
from dataclasses import replace
from pathlib import Path

import discord

from haven.config import laad_config
from haven.inhoud import laad_inhoud
from scripts.setup_server import Inrichter

INHOUD = laad_inhoud()

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


class _NepBasis:
    """Gedeeld gedrag van nepkanalen; overschrijft de Discord-properties die state nodig hebben."""

    def _start(self, server, name, soort, category=None, overwrites=None, topic=None, slowmode_delay=0, tags=()):
        self.server = server
        self.id = next(_ids)
        self.name = name
        self.soort = soort
        self.category_id = category.id if category else None
        self._nep_ow = dict(overwrites or {})
        self.topic = topic
        self.slowmode_delay = slowmode_delay
        self.available_tags = list(tags)
        self.position = 0
        self.berichten: list = []

    @property
    def available_tags(self):
        return self._nep_tags

    @available_tags.setter
    def available_tags(self, waarde):
        self._nep_tags = list(waarde)

    @property
    def overwrites(self):
        return self._nep_ow

    @overwrites.setter
    def overwrites(self, waarde):
        self._nep_ow = dict(waarde)

    async def edit(self, **kw):
        self.server.api_calls += 1
        kw.pop("reason", None)
        if "category" in kw:
            cat = kw.pop("category")
            self.category_id = cat.id if cat else None
        if kw.pop("type", None) == discord.ChannelType.news:
            self.soort = "news"
        for k, v in kw.items():
            setattr(self, k, v)


class NepComponent:
    def __init__(self, d):
        self.d = d

    def to_dict(self):
        return self.d


class NepBericht:
    def __init__(self, kanaal, author, embeds, view=None, soort=discord.MessageType.default):
        self.id = next(_ids)
        self.kanaal, self.author, self.type = kanaal, author, soort
        self.embeds = list(embeds or [])
        self.components = [NepComponent(d) for d in view.to_components()] if view else []
        self.pinned = False

    async def edit(self, embeds=None, view=discord.utils.MISSING, **kw):
        self.kanaal.server.api_calls += 1
        if embeds is not None:
            self.embeds = list(embeds)
        if view is not discord.utils.MISSING:
            self.components = [NepComponent(d) for d in view.to_components()] if view else []

    async def pin(self, reason=None):
        self.kanaal.server.api_calls += 1
        self.pinned = True
        # Discord plaatst een melding "heeft een bericht vastgezet".
        self.kanaal.berichten.append(NepBericht(self.kanaal, self.author, [], soort=discord.MessageType.pins_add))

    async def delete(self):
        self.kanaal.server.api_calls += 1
        self.kanaal.berichten.remove(self)


class _Berichten:
    async def send(self, content=None, embeds=None, embed=None, view=None, **kw):
        self.server.api_calls += 1
        m = NepBericht(self, self.server.me, embeds or ([embed] if embed else []), view)
        self.berichten.append(m)
        return m

    async def pins(self):
        return [m for m in reversed(self.berichten) if m.pinned]

    async def history(self, limit=100):
        for m in list(reversed(self.berichten))[:limit]:
            yield m


class NepThread:
    def __init__(self, server, name, owner_id, embeds, view):
        self.server = server
        self.id = next(_ids)
        self.name, self.owner_id = name, owner_id
        self.archived = False
        self.flags = type("Vlaggen", (), {"pinned": False})()
        self.start = NepBericht(self, type("Auteur", (), {"id": owner_id})(), embeds, view)
        self.start.id = self.id
        self.berichten = [self.start]

    async def fetch_message(self, bericht_id):
        return self.start

    async def edit(self, pinned=None, archived=None, **kw):
        self.server.api_calls += 1
        if pinned is not None:
            self.flags.pinned = pinned
        if archived is not None:
            self.archived = archived


class NepForum(_NepBasis, discord.ForumChannel):
    def __init__(self, *a, **kw):
        self._start(*a, **kw)
        self._threads: list[NepThread] = []

    @property
    def threads(self):
        return [t for t in self._threads if not t.archived]

    async def archived_threads(self, limit=100):
        for t in self._threads:
            if t.archived:
                yield t

    async def create_thread(self, name, embeds=None, reason=None, view=None, **kw):
        self.server.api_calls += 1
        t = NepThread(self.server, name, self.server.me.id, embeds, view)
        self._threads.append(t)
        return type("MetBericht", (), {"thread": t, "message": t.start})()


class NepKanaal(_NepBasis):
    def __init__(self, *a, **kw):
        self._start(*a, **kw)


class NepTekstkanaal(_Berichten, _NepBasis, discord.TextChannel):
    """Subklasse zodat isinstance(..., TextChannel) klopt, zoals bij Community-modus en AutoMod."""

    def __init__(self, *a, **kw):
        self._start(*a, **kw)

    def is_news(self):
        return self.soort == "news"


class NepCategorie(_NepBasis, discord.CategoryChannel):
    def __init__(self, server, name, overwrites):
        self._start(server, name, "category", overwrites=overwrites)

    async def edit(self, **kw):
        self.server.api_calls += 1
        if "overwrites" in kw:
            self.overwrites = kw["overwrites"]
        if "position" in kw:
            lijst = self.server.categories
            lijst.remove(self)
            lijst.insert(kw["position"], self)
            for i, c in enumerate(lijst):
                c.position = i


class NepLid:
    def __init__(self, top_role):
        self.id = next(_ids)
        self.top_role = top_role
        self.guild_permissions = discord.Permissions(administrator=True)

    def __hash__(self):
        return self.id


class NepServer:
    def __init__(self, leden=1234):
        self.id = next(_ids)
        self.default_role = NepRol("@everyone", 0)
        botrol = NepRol("PokeTCG Haven", 1, permissions=discord.Permissions(administrator=True))
        self.roles = [self.default_role, botrol]
        self.me = NepLid(botrol)
        self.member_count = leden
        self.features: list[str] = []
        self.categories: list[NepCategorie] = []
        self.overige: list = []
        self.automod: list[str] = []
        self.verification_level = discord.VerificationLevel.none
        self.explicit_content_filter = discord.ContentFilter.disabled
        self.default_notifications = discord.NotificationLevel.all_messages
        self.rules_channel = None
        self.public_updates_channel = None
        self.api_calls = 0
        self.community_fout = False

    @property
    def channels(self):
        verborgen = getattr(self, "verborgen", set())
        return [*self.categories, *(c for c in self.overige if c.name not in verborgen)]

    async def edit(self, **kw):
        self.api_calls += 1
        kw.pop("reason", None)
        if kw.pop("community", False):
            if self.community_fout:
                raise discord.HTTPException(type("R", (), {"status": 400, "reason": "x"})(), "test")
            self.features.append("COMMUNITY")
        for k, v in kw.items():
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
        cat = NepCategorie(self, name, overwrites)
        cat.position = len(self.categories)
        self.categories.append(cat)
        return cat

    async def _kanaal(self, klasse, name, soort, category, overwrites, topic=None, slowmode_delay=0, tags=()):
        self.api_calls += 1
        ch = klasse(self, name, soort, category, overwrites, topic, slowmode_delay, tags)
        self.overige.append(ch)
        return ch

    async def create_text_channel(self, name, *, category, overwrites, reason, topic, slowmode_delay, news):
        return await self._kanaal(NepTekstkanaal, name, "news" if news else "text", category, overwrites, topic, slowmode_delay)

    async def create_forum(self, name, *, category, overwrites, reason, topic, slowmode_delay, available_tags):
        return await self._kanaal(NepForum, name, "forum", category, overwrites, topic, slowmode_delay, available_tags)

    async def create_voice_channel(self, name, *, category, overwrites, reason):
        return await self._kanaal(NepKanaal, name, "voice", category, overwrites)

    async def create_stage_channel(self, name, *, category, overwrites, reason):
        return await self._kanaal(NepKanaal, name, "stage", category, overwrites)

    async def fetch_automod_rules(self):
        return [type("Regel", (), {"name": n}) for n in self.automod]

    async def fetch_channels(self):
        return self.channels

    def verberg_uit_cache(self, naam):
        """Bootst na dat een net aangemaakt kanaal nog niet in de cache van discord.py staat."""
        self.verborgen = getattr(self, "verborgen", set()) | {naam}

    async def create_automod_rule(self, *, name, **kw):
        self.api_calls += 1
        self.automod.append(name)


def draai(server, stap, dry_run=False, config=None, inhoud=INHOUD):
    config = config or laad_config(CONFIG)
    inrichter = Inrichter(server, config, stap, dry_run, inhoud)
    asyncio.run(inrichter.uitvoeren())
    return inrichter


def kanaal(server, naam):
    return next(c for c in server.overige if c.name == naam)


def test_stap_0_volgens_bouwplan():
    server = NepServer()
    eerste = draai(server, 0)
    assert len([r for r in server.roles if r.name not in {"@everyone", "PokeTCG Haven"}]) == 37
    assert [c.name for c in server.categories] == ["📌 START", "🔒 STAFF"]
    assert sorted(c.name for c in server.overige) == ["regels", "staff-logs", "📊 Leden: 1.234"]
    assert kanaal(server, "📊 Leden: 1.234").category_id is None, "de teller staat bovenaan, buiten een categorie"
    assert server.automod == ["Haven: scam-woorden", "Haven: invites", "Haven: mention-spam", "Haven: spam"]
    assert server.verification_level == discord.VerificationLevel.medium
    assert "COMMUNITY" in server.features
    assert server.rules_channel.name == "regels"
    assert server.public_updates_channel.name == "staff-logs"
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
    draai(server, 27)
    calls = server.api_calls
    tweede = draai(server, 27)
    assert tweede.wijzigingen == [], tweede.wijzigingen
    assert server.api_calls == calls


def test_dry_run_verandert_niets():
    server = NepServer()
    plan = draai(server, 27, dry_run=True)
    assert plan.wijzigingen, "dry-run hoort de geplande wijzigingen te tonen"
    assert server.api_calls == 0
    assert [r.name for r in server.roles] == ["@everyone", "PokeTCG Haven"]


def test_stap_voor_stap_bouwen_komt_uit_op_hetzelfde_als_alles_ineens():
    stapsgewijs = NepServer()
    for stap in range(0, 28):
        draai(stapsgewijs, stap)
    ineens = NepServer()
    draai(ineens, 27)
    assert sorted(c.name for c in stapsgewijs.channels) == sorted(c.name for c in ineens.channels)
    assert [c.name for c in stapsgewijs.categories] == [c.name for c in ineens.categories]


def test_categorieen_in_volgorde_met_staff_onderaan():
    server = NepServer()
    for stap in (0, 6, 27):  # STAFF bestaat al vanaf stap 0, de rest komt later
        draai(server, stap)
    config = laad_config(CONFIG)
    assert [c.name for c in server.categories] == config.categorieen


def test_news_en_stage_worden_echt_aangemaakt_dankzij_community():
    server = NepServer()
    resultaat = draai(server, 27)
    assert kanaal(server, "aankondigingen").soort == "news"
    assert kanaal(server, "Releaseavond").soort == "stage"
    assert resultaat.waarschuwingen == []


def test_zonder_community_vervangen_met_waarschuwing():
    server = NepServer()
    config = laad_config(CONFIG)
    config = replace(config, server={**config.server, "community": False})
    resultaat = draai(server, 27, config=config)
    assert kanaal(server, "aankondigingen").soort == "text"
    assert kanaal(server, "Releaseavond").soort == "voice"
    assert len(resultaat.waarschuwingen) == 2


def test_mislukte_community_geeft_waarschuwing_en_geen_crash():
    server = NepServer()
    server.community_fout = True
    resultaat = draai(server, 0)
    assert any("Community" in w for w in resultaat.waarschuwingen)


def test_handmatig_gewijzigde_rechten_worden_hersteld():
    server = NepServer()
    draai(server, 27)
    premium = kanaal(server, "sniper-nlbe")
    premium.overwrites = {server.default_role: discord.PermissionOverwrite(view_channel=True)}
    herstel = draai(server, 27)
    assert any("sniper-nlbe" in w for w in herstel.wijzigingen)
    assert premium.overwrites[server.default_role].view_channel is False


def test_teller_wordt_bijgewerkt_als_het_ledental_verandert():
    server = NepServer(leden=1234)
    draai(server, 0)
    server.member_count = 1500
    tweede = draai(server, 0)
    assert any("Leden" in w and "name" in w for w in tweede.wijzigingen)
    assert any(c.name == "📊 Leden: 1.500" for c in server.overige)


def test_alle_27_tekstkanalen_plus_voice_na_volledige_build():
    server = NepServer()
    draai(server, 27)
    tekst = [c for c in server.overige if c.soort in {"text", "news", "forum"} and c.name != "staff-logs"]
    assert len(tekst) == 27
    stem = {c.name for c in server.overige if c.soort in {"voice", "stage"}}
    assert stem == {"Lounge NL/BE", "Lounge EN", "Releaseavond", "📊 Leden: 1.234"}


def test_geen_dubbele_kanalen_als_de_cache_achterloopt():
    server = NepServer()
    server.verberg_uit_cache("regels")
    server.verberg_uit_cache("staff-logs")
    draai(server, 27)
    namen = [c.name for c in server.overige]
    assert namen.count("regels") == 1 and namen.count("staff-logs") == 1


def test_tekstkanaal_wordt_aankondigingskanaal_zodra_community_aan_staat():
    server = NepServer()
    config = laad_config(CONFIG)
    draai(server, 27, config=replace(config, server={**config.server, "community": False}))
    assert kanaal(server, "aankondigingen").soort == "text"
    tweede = draai(server, 27)
    assert kanaal(server, "aankondigingen").soort == "news"
    assert any("aankondigingen" in w and "type" in w for w in tweede.wijzigingen)
    # Een spraakkanaal kan geen stage worden: dat meldt het script eerlijk.
    assert any("Releaseavond" in w and "stage" in w for w in tweede.waarschuwingen)


def eigen_vastgepind(kanaal, server):
    return [m for m in kanaal.berichten if m.pinned and m.author.id == server.me.id]


def test_volledige_build_plaatst_alle_inhoud():
    server = NepServer()
    resultaat = draai(server, 27)
    assert resultaat.waarschuwingen == []
    for naam, ki in INHOUD.items():
        ch = kanaal(server, naam)
        if isinstance(ch, NepForum):
            posts = [t for t in ch._threads if t.name == ki.berichten[0].post_titel]
            assert len(posts) == 1 and posts[0].flags.pinned, naam
        else:
            assert len(eigen_vastgepind(ch, server)) == len(ki.berichten), naam
            assert not [m for m in ch.berichten if m.type == discord.MessageType.pins_add], f"pin-melding in #{naam}"


def test_inhoud_alleen_tot_de_huidige_stap():
    server = NepServer()
    draai(server, 0)
    # #regels bestaat al (nodig voor Community), maar de regels zelf komen pas in stap 2.
    assert kanaal(server, "regels").berichten == []
    draai(server, 2)
    assert len(eigen_vastgepind(kanaal(server, "regels"), server)) == len(INHOUD["regels"].berichten)
    assert kanaal(server, "start-hier").berichten, "stap 1 is ook gebouwd"


def test_gewijzigde_tekst_wordt_bewerkt_niet_opnieuw_geplaatst():
    server = NepServer()
    draai(server, 27)
    ki = INHOUD["pulls"]
    b = ki.berichten[0]
    nieuw_embed = {**b.embeds[0], "titel": "📌 Over #pulls (nieuw)"}
    gewijzigd = {**INHOUD, "pulls": replace(ki, berichten=(replace(b, embeds=(nieuw_embed,)),))}
    tweede = draai(server, 27, inhoud=gewijzigd)
    assert tweede.wijzigingen == ["bericht bijwerken: #pulls/kaart"]
    pins = eigen_vastgepind(kanaal(server, "pulls"), server)
    assert len(pins) == 1 and pins[0].embeds[0].title == "📌 Over #pulls (nieuw)"


def test_overbodig_setup_bericht_wordt_verwijderd():
    server = NepServer()
    draai(server, 27)
    ki = INHOUD["start-hier"]
    korter = {**INHOUD, "start-hier": replace(ki, berichten=ki.berichten[:2])}
    tweede = draai(server, 27, inhoud=korter)
    assert tweede.wijzigingen == ["oud setup-bericht verwijderen: #start-hier"]
    assert len(eigen_vastgepind(kanaal(server, "start-hier"), server)) == 2


def test_berichten_van_leden_tellen_niet_mee():
    server = NepServer()
    draai(server, 27)
    ch = kanaal(server, "pulls")
    lid = type("Lid", (), {"id": 42})()
    ch.berichten.append(NepBericht(ch, lid, []))  # gewone pull van een lid, niet vastgepind
    tweede = draai(server, 27)
    assert tweede.wijzigingen == []


def test_dry_run_waarschuwt_niet_voor_community_kanalen():
    server = NepServer()
    plan = draai(server, 27, dry_run=True)
    assert plan.waarschuwingen == []
    assert any("aankondigingen (news)" in w for w in plan.wijzigingen)

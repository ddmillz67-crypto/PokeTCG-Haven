"""Richt de Discord-server in volgens config/server.yaml.

Gebruik:
    python -m scripts.setup_server --tot-stap 0 --dry-run   # laat zien wat er zou veranderen
    python -m scripts.setup_server --tot-stap 0             # voert het echt uit

Het script is idempotent: het maakt alleen aan wat ontbreekt en zet bestaande rollen,
kanalen en rechten gelijk aan de configuratie. Je kunt het dus na elke stap opnieuw draaien.
Kanalen en rollen die niet in de config staan, worden nooit verwijderd.

Nodig in de omgeving (of in een .env-bestand): DISCORD_TOKEN en DISCORD_GUILD_ID.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

import aiohttp
import discord

from haven.inhoud import (
    Bericht,
    Context,
    InhoudFout,
    KanaalInhoud,
    bouw_embeds,
    bouw_view,
    controleer_inhoud,
    is_gelijk,
    laad_inhoud,
)
from haven.config import (
    TELLER_PREFIX,
    ConfigFout,
    Kanaal,
    ServerConfig,
    categorie_rechten,
    kanaal_rechten,
    laad_config,
)

ROOT = Path(__file__).resolve().parent.parent
log = logging.getLogger("setup")

# Wat de bot zelf altijd mag in elk kanaal dat hij beheert.
BOT_RECHTEN = discord.PermissionOverwrite(
    view_channel=True,
    send_messages=True,
    embed_links=True,
    attach_files=True,
    manage_messages=True,
    manage_threads=True,
    read_message_history=True,
)

AUTOMOD_PREFIX = "Haven: "


def laad_env(pad: Path) -> None:
    """Minimale .env-lezer: KEY=waarde per regel; bestaande variabelen winnen."""
    if not pad.exists():
        return
    for regel in pad.read_text(encoding="utf-8").splitlines():
        regel = regel.strip()
        if not regel or regel.startswith("#") or "=" not in regel:
            continue
        sleutel, waarde = regel.split("=", 1)
        os.environ.setdefault(sleutel.strip(), waarde.strip().strip('"').strip("'"))


def env_stap() -> int:
    waarde = os.environ.get("SETUP_TOT_STAP", "0").strip()
    if not waarde.isdigit():
        raise SystemExit(f"SETUP_TOT_STAP moet een getal zijn, niet '{waarde}'")
    return int(waarde)


def env_dry_run() -> bool:
    """Standaard veilig: zonder SETUP_DRY_RUN=0 wordt er niets veranderd."""
    return os.environ.get("SETUP_DRY_RUN", "1").strip().lower() not in {"0", "nee", "false", "no"}


class Inrichter:
    def __init__(
        self,
        guild: discord.Guild,
        config: ServerConfig,
        tot_stap: int,
        dry_run: bool,
        inhoud: dict[str, KanaalInhoud] | None = None,
    ):
        self.guild = guild
        self.config = config
        self.inhoud = inhoud or {}
        self.tot_stap = tot_stap
        self.dry_run = dry_run
        self.wijzigingen: list[str] = []
        self.waarschuwingen: list[str] = []
        self.rollen: dict[str, discord.Role] = {}
        # Kanalen die deze run heeft aangemaakt. De cache van discord.py loopt soms achter,
        # en zonder deze lijst zou een tweede ronde een kanaal dubbel kunnen aanmaken.
        self.aangemaakt: dict[str, discord.abc.GuildChannel] = {}

    # -- hulpfuncties -------------------------------------------------------

    def wijzig(self, tekst: str) -> bool:
        """Registreert een wijziging. Geeft True als die echt uitgevoerd moet worden."""
        self.wijzigingen.append(tekst)
        log.info("%s%s", "[dry-run] " if self.dry_run else "", tekst)
        return not self.dry_run

    def waarschuw(self, tekst: str) -> None:
        self.waarschuwingen.append(tekst)
        log.warning(tekst)

    def overwrites(self, spec: dict[str, dict[str, bool]]) -> dict:
        result: dict = {}
        for naam, rechten in spec.items():
            doel = self.guild.default_role if naam == "@everyone" else self.rollen.get(naam)
            if doel is None:
                # Alleen mogelijk in dry-run, als de rol nog niet bestaat.
                doel = discord.Object(id=0)
            result[doel] = discord.PermissionOverwrite(**rechten)
        result[self.guild.me] = BOT_RECHTEN
        return result

    @staticmethod
    def zelfde_overwrites(huidig: dict, gewenst: dict) -> bool:
        def norm(ow: dict) -> dict:
            return {getattr(k, "id", k): v.pair() for k, v in ow.items()}

        return norm(huidig) == norm(gewenst)

    # -- stappen ------------------------------------------------------------

    async def server_instellingen(self) -> None:
        s = self.config.server
        gewenst = {}
        if "verificatie" in s:
            gewenst["verification_level"] = discord.VerificationLevel[s["verificatie"]]
        if "expliciete_inhoud" in s:
            gewenst["explicit_content_filter"] = discord.ContentFilter[s["expliciete_inhoud"]]
        if "meldingen" in s:
            gewenst["default_notifications"] = discord.NotificationLevel[s["meldingen"]]
        anders = {k: v for k, v in gewenst.items() if getattr(self.guild, k) != v}
        if anders and self.wijzig(f"serverinstellingen: {', '.join(f'{k}={v.name}' for k, v in anders.items())}"):
            await self.guild.edit(**anders, reason="PokeTCG Haven setup")

    async def rollen_inrichten(self) -> None:
        bestaand = {r.name: r for r in self.guild.roles}
        for rol in self.config.rollen:
            rechten = discord.Permissions(**{p: True for p in rol.rechten})
            kleur = discord.Colour(rol.kleur)
            huidig = bestaand.get(rol.naam)
            if huidig is None:
                if self.wijzig(f"rol aanmaken: {rol.naam}"):
                    huidig = await self.guild.create_role(
                        name=rol.naam,
                        colour=kleur,
                        hoist=rol.apart_tonen,
                        mentionable=rol.noembaar,
                        permissions=rechten,
                        reason="PokeTCG Haven setup",
                    )
            elif (
                huidig.colour != kleur
                or huidig.hoist != rol.apart_tonen
                or huidig.mentionable != rol.noembaar
                or huidig.permissions != rechten
            ):
                if huidig >= self.guild.me.top_role:
                    self.waarschuw(f"rol {rol.naam} staat boven de bot en kan niet aangepast worden")
                elif self.wijzig(f"rol bijwerken: {rol.naam}"):
                    await huidig.edit(
                        colour=kleur,
                        hoist=rol.apart_tonen,
                        mentionable=rol.noembaar,
                        permissions=rechten,
                        reason="PokeTCG Haven setup",
                    )
            if huidig is not None:
                self.rollen[rol.naam] = huidig

        await self.rollen_ordenen()

    async def rollen_ordenen(self) -> None:
        """Zet de rollen in de volgorde van de config, onderaan de lijst (onder de botrol).

        De posities worden vanaf onderen geteld (1 = net boven @everyone). Zo hangt het
        niet af van de positie van de botrol in de cache, die na het aanmaken van rollen
        verouderd kan zijn.
        """
        volgorde = [self.rollen[r.naam] for r in self.config.rollen if r.naam in self.rollen]
        beweegbaar = [r for r in volgorde if r < self.guild.me.top_role]
        if len(beweegbaar) != len(volgorde):
            self.waarschuw("sommige rollen staan boven de bot; sleep de botrol in Discord helemaal naar boven")
        huidig = [r.id for r in sorted(beweegbaar, key=lambda r: r.position, reverse=True)]
        gewenst = [r.id for r in beweegbaar]
        if huidig == gewenst:
            return
        posities = {rol: len(beweegbaar) - i for i, rol in enumerate(beweegbaar)}
        if self.wijzig("rollen in de juiste volgorde zetten"):
            await self.guild.edit_role_positions(positions=posities, reason="PokeTCG Haven setup")

    async def categorieen_inrichten(self) -> dict[str, discord.CategoryChannel]:
        bestaand = {c.name: c for c in self.guild.categories}
        result: dict[str, discord.CategoryChannel] = {}
        for naam in self.config.categorieen_tot_stap(self.tot_stap):
            gewenst = self.overwrites(categorie_rechten(self.config, naam))
            cat = bestaand.get(naam)
            if cat is None:
                if self.wijzig(f"categorie aanmaken: {naam}"):
                    cat = await self.guild.create_category(naam, overwrites=gewenst, reason="PokeTCG Haven setup")
            elif not self.zelfde_overwrites(cat.overwrites, gewenst):
                if self.wijzig(f"rechten categorie bijwerken: {naam}"):
                    await cat.edit(overwrites=gewenst, reason="PokeTCG Haven setup")
            if cat is not None:
                result[naam] = cat
        return result

    async def categorieen_ordenen(self, categorieen: dict[str, discord.CategoryChannel]) -> None:
        """Zet de categorieën in de volgorde van de config (STAFF onderaan)."""
        gewenst = [n for n in self.config.categorieen if n in categorieen]
        huidig = [c.name for c in sorted(categorieen.values(), key=lambda c: c.position)]
        if huidig == gewenst:
            return
        if self.wijzig("categorieën in de juiste volgorde zetten"):
            for positie, naam in enumerate(gewenst):
                await categorieen[naam].edit(position=positie, reason="PokeTCG Haven setup")

    def zoek_kanaal(self, kanaal: Kanaal) -> discord.abc.GuildChannel | None:
        if kanaal.naam in self.aangemaakt:
            return self.aangemaakt[kanaal.naam]
        for ch in self.guild.channels:
            if isinstance(ch, discord.CategoryChannel):
                continue
            if kanaal.type == "teller":
                if ch.name.startswith(f"{TELLER_PREFIX}{kanaal.naam}:"):
                    return ch
            elif ch.name == kanaal.naam:
                return ch
        return None

    def ledental(self) -> int:
        return self.guild.member_count or 0

    async def kanalen_inrichten(self, categorieen: dict[str, discord.CategoryChannel], alleen_basis: bool = False) -> None:
        """Maakt kanalen aan of werkt ze bij.

        Met alleen_basis=True alleen de kanalen van stap 0 (en de vroege), zodat Community-modus
        aan kan voordat er aankondigings- en stagekanalen nodig zijn.
        """
        community = "COMMUNITY" in self.guild.features
        for kanaal in self.config.kanalen_tot_stap(self.tot_stap):
            if alleen_basis and not (kanaal.stap == 0 or kanaal.vroeg):
                continue
            cat = categorieen.get(kanaal.categorie)
            gewenst = self.overwrites(kanaal_rechten(self.config, kanaal))
            ch = self.zoek_kanaal(kanaal)
            if ch is None:
                await self.kanaal_aanmaken(kanaal, cat, gewenst, community)
            else:
                await self.kanaal_bijwerken(kanaal, ch, cat, gewenst)

    async def kanaal_aanmaken(self, kanaal: Kanaal, cat, overwrites: dict, community: bool) -> None:
        soort = kanaal.type
        if soort in {"news", "stage"} and not community:
            vervanger = "text" if soort == "news" else "voice"
            self.waarschuw(
                f"{kanaal.naam}: type '{soort}' vereist Community-modus; ik maak een '{vervanger}'-kanaal. "
                "Zet Community aan en draai het script opnieuw"
                + (" om het om te zetten." if soort == "news" else "; verwijder dan eerst dit spraakkanaal, want een stage kan niet worden omgezet.")
            )
            soort = vervanger
        waar = kanaal.categorie or "bovenaan, buiten een categorie"
        if not self.wijzig(f"kanaal aanmaken: {kanaal.naam} ({soort}) in {waar}"):
            return
        gemeen = dict(category=cat, overwrites=overwrites, reason="PokeTCG Haven setup")
        ch = None
        try:
            if soort in {"text", "news"}:
                ch = await self.guild.create_text_channel(
                    kanaal.naam, topic=kanaal.onderwerp, slowmode_delay=kanaal.slowmode,
                    news=soort == "news", **gemeen,
                )
            elif soort == "forum":
                ch = await self.guild.create_forum(
                    kanaal.naam, topic=kanaal.onderwerp, slowmode_delay=kanaal.slowmode,
                    available_tags=[discord.ForumTag(name=t) for t in kanaal.tags], **gemeen,
                )
            elif soort == "voice":
                ch = await self.guild.create_voice_channel(kanaal.naam, **gemeen)
            elif soort == "teller":
                ch = await self.guild.create_voice_channel(kanaal.discord_naam(self.ledental()), **gemeen)
            elif soort == "stage":
                ch = await self.guild.create_stage_channel(kanaal.naam, **gemeen)
        except discord.HTTPException as fout:
            self.waarschuw(f"{kanaal.naam}: aanmaken mislukt ({fout.status}: {fout.text})")
        if ch is not None:
            self.aangemaakt[kanaal.naam] = ch

    async def kanaal_bijwerken(self, kanaal: Kanaal, ch, cat, overwrites: dict) -> None:
        wijzigingen: dict = {}
        if cat is not None and ch.category_id != cat.id:
            wijzigingen["category"] = cat
        elif kanaal.categorie is None and ch.category_id is not None:
            wijzigingen["category"] = None
        if kanaal.type == "teller" and ch.name != kanaal.discord_naam(self.ledental()):
            # Discord staat maar 2 naamwijzigingen per 10 minuten per kanaal toe;
            # de Haven-bot werkt de teller later elk kwartier bij.
            wijzigingen["name"] = kanaal.discord_naam(self.ledental())
        if not self.zelfde_overwrites(ch.overwrites, overwrites):
            wijzigingen["overwrites"] = overwrites
        if (
            kanaal.type == "news"
            and isinstance(ch, discord.TextChannel)
            and not ch.is_news()
            and "COMMUNITY" in self.guild.features
        ):
            wijzigingen["type"] = discord.ChannelType.news
        if kanaal.type == "stage" and not isinstance(ch, discord.StageChannel) and "COMMUNITY" in self.guild.features:
            self.waarschuw(
                f"{kanaal.naam}: dit is nog een spraakkanaal; verwijder het en draai het script opnieuw voor een stage"
            )
        if isinstance(ch, (discord.TextChannel, discord.ForumChannel)):
            if (ch.topic or "") != kanaal.onderwerp:
                wijzigingen["topic"] = kanaal.onderwerp
            if ch.slowmode_delay != kanaal.slowmode:
                wijzigingen["slowmode_delay"] = kanaal.slowmode
        if isinstance(ch, discord.ForumChannel):
            huidige_tags = {t.name for t in ch.available_tags}
            if not set(kanaal.tags) <= huidige_tags:
                # Bestaande tags blijven staan (posts kunnen ze gebruiken); alleen ontbrekende erbij.
                extra = [discord.ForumTag(name=t) for t in kanaal.tags if t not in huidige_tags]
                wijzigingen["available_tags"] = [*ch.available_tags, *extra]
        if wijzigingen and self.wijzig(f"kanaal bijwerken: {kanaal.naam} ({', '.join(wijzigingen)})"):
            try:
                await ch.edit(**wijzigingen, reason="PokeTCG Haven setup")
            except discord.HTTPException as fout:
                self.waarschuw(f"{kanaal.naam}: bijwerken mislukt ({fout.status}: {fout.text})")

    async def community_aanzetten(self) -> None:
        s = self.config.server
        if not s.get("community") or "COMMUNITY" in self.guild.features:
            return
        if not self.wijzig(f"Community-modus aanzetten (regels: #{s['regelkanaal']}, meldingen: #{s['updatekanaal']})"):
            return
        kanalen = await self.guild.fetch_channels()
        regels = discord.utils.find(lambda c: isinstance(c, discord.TextChannel) and c.name == s["regelkanaal"], kanalen)
        updates = discord.utils.find(lambda c: isinstance(c, discord.TextChannel) and c.name == s["updatekanaal"], kanalen)
        if regels is None or updates is None:
            self.waarschuw("Community-modus: regel- of updatekanaal niet gevonden; draai het script opnieuw")
            return
        try:
            await self.guild.edit(
                community=True, rules_channel=regels, public_updates_channel=updates,
                reason="PokeTCG Haven setup",
            )
        except discord.HTTPException as fout:
            self.waarschuw(f"Community-modus aanzetten mislukt ({fout.status}: {fout.text})")

    async def automod_inrichten(self) -> None:
        am = self.config.automod
        if not am:
            return
        try:
            bestaand = {r.name: r for r in await self.guild.fetch_automod_rules()}
        except discord.HTTPException as fout:
            self.waarschuw(f"AutoMod-regels lezen mislukt ({fout.status}); controleer de rechten van de bot")
            return

        # Via de API ophalen: een kanaal dat net is aangemaakt staat soms nog niet in de cache.
        logkanaal = None
        if not self.dry_run:
            kanalen = await self.guild.fetch_channels()
            logkanaal = discord.utils.find(
                lambda c: isinstance(c, discord.TextChannel) and c.name == "staff-logs", kanalen
            )
        uitgezonderd = [self.rollen[n] for n in self.config.staffrollen if n in self.rollen]

        def acties(melding: str) -> list[discord.AutoModRuleAction]:
            lijst = [discord.AutoModRuleAction(custom_message=melding)]
            if logkanaal is not None:
                lijst.append(discord.AutoModRuleAction(channel_id=logkanaal.id))
            return lijst

        regels = [
            (
                "scam-woorden",
                discord.AutoModTrigger(type=discord.AutoModRuleTriggerType.keyword, keyword_filter=am.get("scam_woorden", [])),
                "Dit bericht lijkt op oplichting en is tegengehouden. / This message looks like a scam and was blocked.",
            ),
            (
                "invites",
                discord.AutoModTrigger(type=discord.AutoModRuleTriggerType.keyword, regex_patterns=am.get("invite_regex", [])),
                "Uitnodigingen voor andere servers zijn niet toegestaan. / Invites to other servers are not allowed.",
            ),
            (
                "mention-spam",
                discord.AutoModTrigger(type=discord.AutoModRuleTriggerType.mention_spam, mention_limit=int(am.get("max_mentions", 5))),
                "Te veel mentions in één bericht. / Too many mentions in one message.",
            ),
            (
                "spam",
                discord.AutoModTrigger(type=discord.AutoModRuleTriggerType.spam),
                "Dit bericht lijkt op spam. / This message looks like spam.",
            ),
        ]
        for kort, trigger, melding in regels:
            naam = AUTOMOD_PREFIX + kort
            if naam in bestaand:
                continue
            if not self.wijzig(f"AutoMod-regel aanmaken: {naam}"):
                continue
            try:
                await self.guild.create_automod_rule(
                    name=naam,
                    event_type=discord.AutoModRuleEventType.message_send,
                    trigger=trigger,
                    actions=acties(melding),
                    enabled=True,
                    exempt_roles=uitgezonderd,
                    reason="PokeTCG Haven setup",
                )
            except discord.HTTPException as fout:
                # Discord staat bijvoorbeeld maar één spam-regel per server toe.
                self.waarschuw(f"{naam}: aanmaken mislukt ({fout.status}: {fout.text})")

    # -- inhoud: embeds, knoppen en menu's ------------------------------------

    async def context(self, kanalen: list) -> Context:
        return Context(
            guild_id=self.guild.id,
            kanalen={c.name: c.id for c in kanalen if not isinstance(c, discord.CategoryChannel)},
            rollen={naam: rol.id for naam, rol in self.rollen.items()},
            env=dict(os.environ),
        )

    async def berichten_inrichten(self) -> None:
        """Plaatst de inhoud van elk kanaal tot en met de huidige stap.

        Setup-berichten zijn altijd vastgepind; zo herkent het script ze terug tussen de
        berichten van leden en de bot. Gewijzigde inhoud wordt bewerkt, niet opnieuw geplaatst.
        """
        te_doen = [k for k in self.config.kanalen if k.stap <= self.tot_stap and k.naam in self.inhoud]
        if not te_doen:
            return
        if self.dry_run:
            for k in te_doen:
                self.wijzig(f"inhoud controleren en plaatsen: #{k.naam} ({len(self.inhoud[k.naam].berichten)} bericht(en))")
            return
        kanalen = await self.guild.fetch_channels()
        ctx = await self.context(kanalen)
        for k in te_doen:
            ch = discord.utils.find(lambda c: c.name == k.naam and not isinstance(c, discord.CategoryChannel), kanalen)
            if ch is None:
                self.waarschuw(f"#{k.naam}: kanaal niet gevonden, inhoud overgeslagen")
                continue
            try:
                if isinstance(ch, discord.ForumChannel):
                    await self.forumpost_inrichten(ch, self.inhoud[k.naam].berichten[0], ctx)
                else:
                    await self.kanaalberichten_inrichten(ch, self.inhoud[k.naam], ctx)
            except discord.HTTPException as fout:
                self.waarschuw(f"#{k.naam}: inhoud plaatsen mislukt ({fout.status}: {fout.text})")

    async def kanaalberichten_inrichten(self, ch, ki: KanaalInhoud, ctx: Context) -> None:
        eigen = sorted((m for m in await ch.pins() if m.author.id == self.guild.me.id), key=lambda m: m.id)
        for i, bericht in enumerate(ki.berichten):
            embeds, view = bouw_embeds(bericht, ctx), bouw_view(bericht, ctx)
            if i < len(eigen):
                m = eigen[i]
                if not is_gelijk([e.to_dict() for e in m.embeds], [c.to_dict() for c in m.components], embeds, view):
                    if self.wijzig(f"bericht bijwerken: #{ch.name}/{bericht.sleutel}"):
                        await m.edit(embeds=embeds, view=view)
            elif self.wijzig(f"bericht plaatsen: #{ch.name}/{bericht.sleutel}"):
                m = await ch.send(embeds=embeds, view=view) if view else await ch.send(embeds=embeds)
                await m.pin(reason="PokeTCG Haven setup")
                await self.pinmelding_opruimen(ch)
        for m in eigen[len(ki.berichten):]:
            if self.wijzig(f"oud setup-bericht verwijderen: #{ch.name}"):
                await m.delete()

    async def pinmelding_opruimen(self, ch) -> None:
        """Discord plaatst bij elk vastgepind bericht een melding; die halen we weg."""
        async for m in ch.history(limit=5):
            if m.type == discord.MessageType.pins_add and m.author.id == self.guild.me.id:
                await m.delete()

    async def forumpost_inrichten(self, forum, bericht: Bericht, ctx: Context) -> None:
        threads = list(forum.threads)
        async for t in forum.archived_threads(limit=100):
            threads.append(t)
        post = discord.utils.find(lambda t: t.name == bericht.post_titel and t.owner_id == self.guild.me.id, threads)
        embeds, view = bouw_embeds(bericht, ctx), bouw_view(bericht, ctx)
        if post is None:
            if self.wijzig(f"vastgepinde forumpost plaatsen: #{forum.name}/{bericht.sleutel}"):
                extra = {"view": view} if view else {}
                nieuw = await forum.create_thread(name=bericht.post_titel, embeds=embeds, reason="PokeTCG Haven setup", **extra)
                await nieuw.thread.edit(pinned=True)
            return
        start = await post.fetch_message(post.id)
        if not is_gelijk([e.to_dict() for e in start.embeds], [c.to_dict() for c in start.components], embeds, view):
            if self.wijzig(f"forumpost bijwerken: #{forum.name}/{bericht.sleutel}"):
                await start.edit(embeds=embeds, view=view)
        if not post.flags.pinned or post.archived:
            if self.wijzig(f"forumpost vastpinnen: #{forum.name}/{bericht.sleutel}"):
                await post.edit(pinned=True, archived=False)

    async def uitvoeren(self) -> None:
        if not self.guild.me.guild_permissions.administrator:
            self.waarschuw("de bot heeft geen Administrator-recht; sommige stappen kunnen mislukken")
        await self.server_instellingen()
        await self.rollen_inrichten()
        categorieen = await self.categorieen_inrichten()
        await self.kanalen_inrichten(categorieen, alleen_basis=True)
        await self.community_aanzetten()
        await self.kanalen_inrichten(categorieen)
        await self.automod_inrichten()
        await self.categorieen_ordenen(categorieen)
        await self.berichten_inrichten()


async def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Richt de PokeTCG Haven-server in.")
    # Standaardwaarden komen uit de omgeving, zodat je op Railway alleen variabelen hoeft
    # aan te passen: SETUP_TOT_STAP=0 en SETUP_DRY_RUN=1 (1 = alleen tonen, 0 = uitvoeren).
    parser.add_argument("--tot-stap", type=int, default=env_stap(), help="maak alles t/m dit stapnummer (0-27)")
    parser.add_argument("--dry-run", action="store_true", default=env_dry_run(), help="laat alleen zien wat er zou veranderen")
    parser.add_argument("--config", default=str(ROOT / "config" / "server.yaml"))
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", stream=sys.stdout)
    log.info("setup start: tot en met stap %d%s", args.tot_stap, " (dry-run, er verandert niets)" if args.dry_run else "")
    laad_env(ROOT / ".env")

    try:
        config = laad_config(args.config)
        inhoud = laad_inhoud()
        controleer_inhoud(inhoud, config)
    except (ConfigFout, InhoudFout) as fout:
        log.error("config of inhoud klopt niet: %s", fout)
        return 2

    token = os.environ.get("DISCORD_TOKEN")
    guild_id = os.environ.get("DISCORD_GUILD_ID")
    if not token or not guild_id or not guild_id.isdigit():
        log.error("DISCORD_TOKEN en DISCORD_GUILD_ID (een getal) moeten gezet zijn")
        return 2

    client = discord.Client(intents=discord.Intents.default())
    uitkomst = {"code": 1}

    @client.event
    async def on_ready() -> None:
        try:
            guild = client.get_guild(int(guild_id))
            if guild is None:
                log.error("de bot zit niet in server %s; nodig hem eerst uit", guild_id)
                return
            log.info("verbonden als %s met server '%s'", client.user, guild.name)
            inrichter = Inrichter(guild, config, args.tot_stap, args.dry_run, inhoud)
            await inrichter.uitvoeren()
            log.info(
                "klaar: %d wijziging(en)%s, %d waarschuwing(en)",
                len(inrichter.wijzigingen),
                " (niet uitgevoerd, dry-run)" if args.dry_run else "",
                len(inrichter.waarschuwingen),
            )
            uitkomst["code"] = 0
        finally:
            await client.close()

    try:
        await client.start(token)
    except discord.LoginFailure:
        log.error("het token is ongeldig; maak in de Developer Portal een nieuw token aan")
        return 2
    except discord.PrivilegedIntentsRequired:
        log.error("zet de benodigde intents aan onder Bot in de Developer Portal")
        return 2
    except (OSError, aiohttp.ClientError) as fout:
        log.error("kan discord.com niet bereiken (%s); controleer het netwerk of de Allowed domains", fout)
        return 3
    finally:
        if not client.is_closed():
            await client.close()
    return uitkomst["code"]


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

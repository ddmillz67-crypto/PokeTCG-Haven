import asyncio
from dataclasses import replace

import pytest

from bot.db import Database
from bot.kern import COGS, HavenBot
from haven.config import laad_config
from haven.inhoud import (
    AFBEELDINGEN,
    ACTIES,
    PREFIX,
    Context,
    InhoudFout,
    bouw_embeds,
    bouw_view,
    controleer_inhoud,
    is_gelijk,
    laad_inhoud,
    laad_yaml,
    vul_in,
)
from pathlib import Path

CONFIG = Path(__file__).resolve().parent.parent / "config" / "server.yaml"


@pytest.fixture(scope="module")
def config():
    return laad_config(CONFIG)


@pytest.fixture(scope="module")
def inhoud():
    return laad_inhoud()


def ctx(config, env=None):
    return Context(
        guild_id=1,
        kanalen={k.naam: n for n, k in enumerate(config.kanalen, 10)},
        rollen={r.naam: n for n, r in enumerate(config.rollen, 100)},
        env=env or {},
    )


def test_alle_inhoud_is_geldig(config, inhoud):
    controleer_inhoud(inhoud, config)


def test_elk_tekstkanaal_behalve_staff_heeft_inhoud(config, inhoud):
    tekst = {k.naam for k in config.kanalen if k.type in {"text", "news", "forum"}} - {"staff-logs"}
    assert tekst == set(inhoud)


def test_geen_engels_meer_in_de_inhoud():
    import re

    from haven.inhoud import INHOUD_MAP

    for pad in INHOUD_MAP.glob("*.yaml"):
        tekst = pad.read_text(encoding="utf-8")
        assert "🇬🇧" not in tekst, pad.name
        for engels in ("Welcome", "Read the", "Trade safely", "Open a ticket", "Pick your", "Free to enter"):
            assert engels not in tekst, f"{pad.name}: {engels}"
        assert not re.search(r"\bthe\b", tekst), pad.name


def test_elk_kanaal_begint_met_een_banner(inhoud):
    for naam, ki in inhoud.items():
        assert "banner" in ki.berichten[0].embeds[0], f"#{naam} mist een banner bovenaan"


def test_banners_en_logo_bestaan_en_hebben_een_versie(config):
    from haven.inhoud import AFBEELDINGEN, afbeelding_url

    assert (AFBEELDINGEN / "logo.png").exists()
    url = afbeelding_url("welkom", {})
    assert url.startswith("https://raw.githubusercontent.com/") and "?v=" in url and not url.endswith("?v=0")


def test_alles_bouwt_binnen_discord_limieten(config, inhoud):
    async def bouw():
        c = ctx(config)
        for ki in inhoud.values():
            for b in ki.berichten:
                embeds = bouw_embeds(b, c)
                assert sum(len(e) for e in embeds) <= 6000
                view = bouw_view(b, c)
                if view:
                    rijen = view.to_components()
                    assert len(rijen) <= 5
                    # vergelijken met zichzelf moet gelijk zijn (anders bewerkt de setup elke keer)
                    assert is_gelijk([e.to_dict() for e in embeds], rijen, embeds, view)

    asyncio.run(bouw())


def test_verwijzingen_worden_ingevuld(config):
    c = ctx(config, env={"WHOP_SNIPER_URL": "https://whop.com/x"})
    assert "/welkom.png?v=" in vul_in("{afbeelding:welkom}", c)
    tekst = vul_in("Lees {#regels}, vraag {@Haven Helper}, link {link:#store}, koop {env:WHOP_SNIPER_URL}", c)
    assert f"<#{c.kanalen['regels']}>" in tekst
    assert f"<@&{c.rollen['Haven Helper']}>" in tekst
    assert f"https://discord.com/channels/1/{c.kanalen['store']}" in tekst
    assert "https://whop.com/x" in tekst


def test_koopknop_zonder_whop_link_wordt_binnenkort(config, inhoud):
    async def bouw():
        sniper = next(b for b in inhoud["store"].berichten if b.sleutel == "sniper")
        zonder = bouw_view(sniper, ctx(config))
        met = bouw_view(sniper, ctx(config, env={"WHOP_SNIPER_URL": "https://whop.com/haven"}))
        return zonder.children[0], met.children[0]

    zonder, met = asyncio.run(bouw())
    assert zonder.disabled and "binnenkort" in zonder.label
    assert met.url == "https://whop.com/haven" and not met.disabled


def test_regio_is_een_enkele_keuze(inhoud):
    regio = next(b for b in inhoud["rollen"].berichten if b.sleutel == "regio")
    assert regio.menu.max_keuzes == 1


def test_onbekende_actie_wordt_geweigerd(config, inhoud):
    b = inhoud["tickets"].berichten[0]
    kapot = replace(b, knoppen=(replace(b.knoppen[0], actie="bestaat:niet"),))
    with pytest.raises(InhoudFout):
        controleer_inhoud({"tickets": replace(inhoud["tickets"], berichten=(kapot,))}, config)


def test_tour_en_store_teksten_kloppen(config):
    tour = laad_yaml("tour.yaml")
    namen = {k.naam for k in config.kanalen}
    assert len(tour["paginas"]) == 8, "een openingsscherm met de routekaart en 7 haltes"
    assert "kanaal" not in tour["paginas"][0]
    for p in tour["paginas"][1:]:
        assert p["kanaal"] in namen
    for p in [*tour["paginas"], tour["afsluiting"]]:
        assert (AFBEELDINGEN / f"{p['beeld']}.png").exists(), p["titel"]
    store = laad_yaml("store.yaml")
    assert {"sniper", "founder", "elite", "partner"} <= set(store["info"])


def test_bot_laadt_en_elke_knop_heeft_een_handler(config, inhoud, tmp_path):
    async def start():
        bot = HavenBot(config, inhoud, 123, Database(tmp_path / "t.db"))
        async with bot:
            for ext in COGS:
                await bot.load_extension(ext)
            ontbreekt = [a for a in ACTIES if bot.zoek_actie(PREFIX + a) is None]
            commandos = {c.name for c in bot.tree.get_commands()}
            for cog in list(bot.cogs.values()):
                await bot.remove_cog(cog.qualified_name)
            return ontbreekt, commandos, set(bot.planners)

    ontbreekt, commandos, planners = asyncio.run(start())
    assert ontbreekt == []
    assert {"tour", "level", "vouch", "meld", "alert", "giveaway", "invite", "release", "pings", "opgelost", "winkel"} <= commandos
    assert planners == {"radar", "restock", "rol_weg"}


def test_trainerskaart_toont_alle_keuzes(config, inhoud, tmp_path):
    from types import SimpleNamespace

    async def start():
        bot = HavenBot(config, inhoud, 123, Database(tmp_path / "t.db"))
        async with bot:
            await bot.load_extension("bot.cogs.rollen")
            cog = bot.get_cog("Rollen")
            lid = SimpleNamespace(display_avatar=SimpleNamespace(url="https://cdn.discordapp.com/embed/avatars/0.png"))
            e = cog.trainerskaart(lid, {"Sealed", "Japans", "Vlaanderen", "Lid"})
            await bot.remove_cog("Rollen")
            return e

    e = asyncio.run(start())
    velden = {v.name: v.value for v in e.fields}
    assert "Sealed" in velden["🃏  Verzamelt"] and "Japans" in velden["🃏  Verzamelt"]
    assert velden["📍  Regio"] == "Vlaanderen"
    assert velden["🔔  Meldingen"] == "*nog niets gekozen*"


def test_tweede_voorstelling_wordt_herkend(config, inhoud, tmp_path):
    from types import SimpleNamespace

    import discord

    class Kanaal:
        def __init__(self):
            self.berichten = {}

        async def fetch_message(self, i):
            if i not in self.berichten:
                raise discord.NotFound(SimpleNamespace(status=404, reason="weg"), "weg")
            return self.berichten[i]

    async def start():
        bot = HavenBot(config, inhoud, 123, Database(tmp_path / "t.db"))
        async with bot:
            await bot.load_extension("bot.cogs.community")
            cog = bot.get_cog("Community")
            ch = Kanaal()
            sam = SimpleNamespace(id=7)
            eerste = SimpleNamespace(id=1, author=sam, channel=ch)
            ch.berichten[1] = eerste
            leeg = await cog.eerdere_voorstelling(eerste)
            bot.db.kv_schrijf("voorstelling:7", "1")
            tweede = SimpleNamespace(id=2, author=sam, channel=ch)
            gevonden = await cog.eerdere_voorstelling(tweede)
            del ch.berichten[1]  # eerste voorstelling verwijderd: dan mag je opnieuw
            na_verwijderen = await cog.eerdere_voorstelling(tweede)
            await bot.remove_cog("Community")
            return leeg, gevonden, na_verwijderen, eerste

    leeg, gevonden, na_verwijderen, eerste = asyncio.run(start())
    assert leeg is None
    assert gevonden is eerste
    assert na_verwijderen is None


def test_winkelmonitor_plaatst_alert_bij_restock(config, inhoud, tmp_path):
    def etb(beschikbaar):
        return [{"id": 1, "title": "Pokémon Elite Trainer Box", "handle": "etb", "vendor": "Pokémon", "tags": [],
                 "variants": [{"id": 11, "available": beschikbaar, "price": "54.95"}]}]

    async def start():
        bot = HavenBot(config, inhoud, 123, Database(tmp_path / "t.db"))
        async with bot:
            await bot.load_extension("bot.cogs.alerts")
            cog = bot.get_cog("Alerts")
            bot.db.uitvoeren("INSERT INTO winkels (naam, url, land) VALUES ('Testwinkel', 'https://test.nl', 'nlbe')")
            geplaatst, logs, rondes = [], [], [etb(False), etb(True), etb(True)]

            async def haal(w):
                return rondes.pop(0)

            async def plaats(a):
                geplaatst.append(a)

            async def log(t):
                logs.append(t)

            cog.haal_producten, cog.plaats_alert, bot.log = haal, plaats, log
            for _ in range(3):
                await cog.controleer_winkel(cog.winkels()[0])
            rij = bot.db.een("SELECT * FROM winkels")
            await bot.remove_cog("Alerts")
            return geplaatst, rij

    geplaatst, rij = asyncio.run(start())
    assert [a.url for a in geplaatst] == ["https://test.nl/products/etb"], "precies één alert, bij de restock"
    assert geplaatst[0].prijs == "€ 54,95"
    assert rij["sealed"] == 1 and rij["op_voorraad"] == 1 and rij["fout"] is None

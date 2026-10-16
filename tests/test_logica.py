import random
import time

from bot.db import Database
from haven.giveaways import Inzending, is_goed, mag_meedoen, normaliseer, rangschikking
from haven.levels import level_voor_xp, mag_xp_krijgen, rol_voor_level, totaal_xp_voor_level, voortgang, xp_voor_bericht
from haven.mijlpalen import balk, behaalde_mijlpalen, getal, mijlpaal_rond


def test_levels_drempels():
    assert level_voor_xp(0) == 0
    assert level_voor_xp(totaal_xp_voor_level(5)) == 5
    assert level_voor_xp(totaal_xp_voor_level(5) - 1) == 4
    assert rol_voor_level(0) == "Nieuwe Trainer"
    assert rol_voor_level(4) == "Nieuwe Trainer"
    assert rol_voor_level(5) == "Trainer"
    assert rol_voor_level(15) == "Ace Trainer"
    assert rol_voor_level(49) == "Gym Leader"
    assert rol_voor_level(80) == "Haven Legende"


def test_markt_level_vraagt_ongeveer_een_uur_meepraten():
    # Level 5 = 1.150 XP; met gemiddeld 20 XP per minuut is dat circa 58 actieve minuten.
    assert totaal_xp_voor_level(5) == 1150


def test_voortgang_en_xp():
    level, binnen, nodig = voortgang(totaal_xp_voor_level(3) + 10)
    assert (level, binnen) == (3, 10) and nodig > binnen
    rng = random.Random(1)
    assert all(15 <= xp_voor_bericht(rng) <= 25 for _ in range(200))
    nu = time.time()
    assert mag_xp_krijgen(None, nu)
    assert not mag_xp_krijgen(nu - 30, nu)
    assert mag_xp_krijgen(nu - 61, nu)


def test_giveaway_antwoord_ruim_vergelijken():
    assert normaliseer("  Obsidian   FLAMES! ") == "obsidian flames"
    assert is_goed("pokémon 151", "Pokemon 151|MEW")
    assert is_goed("mew", "Pokemon 151|MEW")
    assert not is_goed("Paldea Evolved", "Pokemon 151|MEW")


def test_giveaway_winnaar_beste_schatting_dan_vroegste():
    inz = [
        Inzending(1, "fout", 100, 1.0),
        Inzending(2, "Mew", 90, 3.0),
        Inzending(3, "mew", 110, 2.0),  # even dichtbij als 2, maar eerder
        Inzending(4, "MEW", 50, 0.5),
    ]
    volgorde = rangschikking(inz, "Mew", 100)
    assert [i.user_id for i in volgorde] == [3, 2, 4]


def test_giveaway_voorwaarden():
    assert mag_meedoen(10, 5, False, 3) is None
    assert "7 dagen" in mag_meedoen(2, 5, False, 3)
    assert "level 3" in mag_meedoen(10, 1, False, 3)
    assert "Team" in mag_meedoen(100, 50, True, 3)


def test_mijlpalen_ladder():
    assert mijlpaal_rond(0) == (0, 250, "5 boosterpacks")
    assert mijlpaal_rond(742) == (500, 1000, "Booster box")
    assert mijlpaal_rond(10000) == (10000, 15000, "Booster box")
    assert mijlpaal_rond(16000) == (15000, 20000, "Booster box")
    assert behaalde_mijlpalen(2600) == [250, 500, 1000, 2500]
    assert behaalde_mijlpalen(15000)[-2:] == [10000, 15000]
    assert balk(750) == "▰" * 10 + "▱" * 10
    assert getal(1234) == "1.234"


def test_database_planner_en_leden(tmp_path):
    db = Database(tmp_path / "t.db")
    db.plan(time.time() - 1, "radar", {"x": 1})
    db.plan(time.time() + 999, "radar", {"x": 2})
    klaar = db.te_doen(time.time())
    assert len(klaar) == 1
    db.gedaan(klaar[0]["id"])
    assert db.te_doen(time.time()) == []
    db.lid_zet(5, xp=100)
    assert db.lid(5)["xp"] == 100
    db.kv_schrijf("a", "1")
    db.kv_schrijf("a", "2")
    assert db.kv_lees("a") == "2"


def test_vorige_maand_voor_de_hall_of_fame():
    import datetime as dt
    from zoneinfo import ZoneInfo

    from bot.cogs.radar import vorige_maand

    tz = ZoneInfo("Europe/Amsterdam")
    begin, eind, sleutel, naam = vorige_maand(dt.datetime(2027, 1, 1, 12, tzinfo=tz))
    assert sleutel == "2026-12" and naam == "december 2026"
    assert dt.datetime.fromtimestamp(begin, tz) == dt.datetime(2026, 12, 1, tzinfo=tz)
    assert dt.datetime.fromtimestamp(eind, tz) == dt.datetime(2027, 1, 1, tzinfo=tz)


def test_releaseoverzicht_toont_alleen_komende_releases():
    from bot.cogs.releases import overzicht_regels

    nu = 1_800_000_000
    rijen = [
        {"naam": "Oude set", "tijd": nu - 3 * 86400, "met_tijd": 0, "limiet": None, "bericht_url": ""},
        {"naam": "Gisteren", "tijd": nu - 3600, "met_tijd": 1, "limiet": "2", "bericht_url": "https://discord.com/x"},
        {"naam": "Nieuwe set", "tijd": nu + 86400, "met_tijd": 0, "limiet": None, "bericht_url": ""},
    ]
    regels = overzicht_regels(rijen, nu)
    assert len(regels) == 2
    assert regels[0].startswith("**[Gisteren](https://discord.com/x)**") and "limiet 2" in regels[0]
    assert regels[1].startswith("**Nieuwe set**")

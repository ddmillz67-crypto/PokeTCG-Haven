from pathlib import Path

import discord
import pytest

from haven.config import (
    ConfigFout,
    categorie_rechten,
    controleer,
    kanaal_rechten,
    laad_config,
)
from haven.huisstijl import FOOTER, KLEUREN, kanaalkaart, maak_embed
from scripts.setup_server import laad_env

CONFIG = Path(__file__).resolve().parent.parent / "config" / "server.yaml"


@pytest.fixture(scope="module")
def config():
    return laad_config(CONFIG)


def kanaal(config, naam):
    return next(k for k in config.kanalen if k.naam == naam)


def test_config_laadt_en_is_geldig(config):
    controleer(config)


def test_stappenplan_heeft_24_tekstkanalen_buiten_staff(config):
    tekst = [k for k in config.kanalen if k.type in {"text", "news", "forum"} and k.naam != "staff-logs"]
    assert len(tekst) == 24
    assert sorted(k.stap for k in tekst) == list(range(1, 25))


def test_geen_engelse_sectie_meer(config):
    namen = {k.naam for k in config.kanalen} | set(config.categorieen) | {r.naam for r in config.rollen}
    assert not namen & {"chat-en", "trade-en", "help-en", "Lounge EN", "🇬🇧 ENGLISH", "EN", "NL/BE"}
    assert config.taalrollen == ("Lid",)


def test_hernoemen_en_opruimen_zijn_veilig(config):
    from dataclasses import replace

    assert config.hernoemen["rollen"] == {"NL/BE": "Lid"}
    assert "general" in config.verwijderen["kanalen"]
    # Iets verwijderen wat ook in het plan staat, wordt geweigerd.
    with pytest.raises(ConfigFout):
        controleer(replace(config, verwijderen={"kanalen": ["chat"]}))
    with pytest.raises(ConfigFout):
        controleer(replace(config, hernoemen={"kanalen": {"oud": "bestaat-niet"}}))


def test_stap_0_maakt_teller_regels_en_staff_logs(config):
    # #regels bestaat al in stap 0 omdat Community-modus een regelkanaal nodig heeft.
    assert [k.naam for k in config.kanalen_tot_stap(0)] == ["Leden", "regels", "staff-logs"]
    assert config.categorieen_tot_stap(0) == ["📌 START", "🔒 STAFF"]


def test_staff_categorie_staat_onderaan(config):
    assert config.categorieen[0] == "📌 START"
    assert config.categorieen[-1] == "🔒 STAFF"


def test_rollen_volgens_bouwplan(config):
    # 36 eigen rollen (NL/BE en EN zijn samen Lid geworden); met botrol en @everyone 38.
    assert len(config.rollen) == 36
    apart = {r.naam for r in config.rollen if r.apart_tonen}
    assert apart == {"Admin", "Mod", "Haven Helper", "Creator", "Pull van de Week"}
    assert not {"Sniper", "Elite", "Founder"} & apart, "betaalde rollen horen niet apart in de ledenlijst"


def test_teller_naam_en_rechten(config):
    teller = kanaal(config, "Leden")
    assert teller.categorie is None
    assert teller.discord_naam(1234) == "📊 Leden: 1.234"
    r = kanaal_rechten(config, teller)
    assert r["@everyone"] == {"view_channel": True, "connect": False}


def test_markt_alleen_posten_vanaf_level_5(config):
    r = kanaal_rechten(config, kanaal(config, "ruilen-verkopen"))
    assert r["Lid"]["view_channel"] is True and r["Lid"]["send_messages"] is False
    for rol in ("Trainer", "Ace Trainer", "Gym Leader", "Haven Legende"):
        assert r[rol] == {"send_messages": True}, "schrijvers mogen het kanaal niet openen"
    assert "Nieuwe Trainer" not in r


def test_levelrol_opent_de_markt_niet_zonder_lid_te_zijn(config):
    r = kanaal_rechten(config, kanaal(config, "ruilen-verkopen"))
    assert "view_channel" not in r["Trainer"]


def test_community_vereist_regelkanaal_in_stap_0(config):
    from dataclasses import replace

    regels = kanaal(config, "regels")
    fout = replace(config, kanalen=[replace(k, vroeg=False) if k is regels else k for k in config.kanalen])
    with pytest.raises(ConfigFout):
        controleer(fout)


def test_alle_rolrechten_bestaan_in_discord(config):
    for rol in config.rollen:
        for recht in rol.rechten:
            assert recht in discord.Permissions.VALID_FLAGS, f"{rol.naam}: {recht}"


def test_alle_kanaalrechten_bestaan_in_discord(config):
    for k in config.kanalen:
        for rechten in kanaal_rechten(config, k).values():
            for recht in rechten:
                assert recht in discord.Permissions.VALID_FLAGS, f"{k.naam}: {recht}"
            discord.PermissionOverwrite(**rechten)


def test_server_instellingen_zijn_geldige_discord_waarden(config):
    discord.VerificationLevel[config.server["verificatie"]]
    discord.ContentFilter[config.server["expliciete_inhoud"]]
    discord.NotificationLevel[config.server["meldingen"]]


def test_tekstkanaalnamen_zijn_geldig_voor_discord(config):
    for k in config.kanalen:
        if k.type in {"text", "news", "forum"}:
            assert k.naam == k.naam.lower() and " " not in k.naam and "/" not in k.naam, k.naam


def test_start_hier_is_voor_iedereen_maar_alleen_lezen(config):
    r = kanaal_rechten(config, kanaal(config, "start-hier"))
    assert r["@everyone"]["view_channel"] is True
    assert r["@everyone"]["send_messages"] is False
    assert r["@everyone"]["add_reactions"] is True


def test_premium_is_verborgen_voor_gratis_leden(config):
    r = kanaal_rechten(config, kanaal(config, "sniper-nlbe"))
    assert r["@everyone"] == {"view_channel": False}
    assert "Lid" not in r
    assert r["Sniper"]["view_channel"] is True
    assert r["Sniper"]["send_messages"] is False


def test_sniper_ziet_eu_kanaal_niet(config):
    r = kanaal_rechten(config, kanaal(config, "sniper-eu"))
    assert "Sniper" not in r
    assert r["Elite"]["view_channel"] is True


def test_community_alleen_voor_wie_binnen_is(config):
    r = kanaal_rechten(config, kanaal(config, "chat"))
    assert r["@everyone"] == {"view_channel": False}
    assert r["Lid"]["view_channel"] is True


def test_staff_ziet_en_schrijft_overal(config):
    for k in config.kanalen:
        r = kanaal_rechten(config, k)
        for staf in config.staffrollen:
            assert r[staf]["view_channel"] is True, k.naam


def test_partner_mag_posten_in_winkel_partners(config):
    r = kanaal_rechten(config, kanaal(config, "winkel-partners"))
    assert r["Haven Partner"] == {"send_messages": True}
    assert r["Lid"]["send_messages"] is False


def test_voice_alleen_lezen_gebruikt_connect(config):
    from haven.config import Kanaal

    stem = Kanaal(naam="test", categorie="x", stap=1, zichtbaar="iedereen", type="voice", alleen_lezen=True)
    r = kanaal_rechten(config, stem)
    assert r["@everyone"]["connect"] is False
    assert "send_messages" not in r["@everyone"]


def test_categorie_premium_verborgen_voor_iedereen(config):
    r = categorie_rechten(config, "💎 PREMIUM")
    assert r["@everyone"] == {"view_channel": False}
    assert r["Sniper"]["view_channel"] is True
    assert "Lid" not in r


def test_onbekende_rol_geeft_fout(config):
    from dataclasses import replace

    fout = replace(config, kanalen=[replace(config.kanalen[0], zichtbaar=("Bestaat-niet",))])
    with pytest.raises(ConfigFout):
        controleer(fout)


def test_tags_alleen_op_forum(config):
    from dataclasses import replace

    fout = replace(config, kanalen=[replace(kanaal(config, "chat"), tags=("x",))])
    with pytest.raises(ConfigFout):
        controleer(fout)


def test_huisstijl_embed():
    e = maak_embed("alert", "Op voorraad", "Nu leverbaar.")
    assert e.colour.value == KLEUREN["alert"] == 3066993
    assert e.footer.text == FOOTER == "PokeTCG Haven • Nederland & België"
    with pytest.raises(ValueError):
        maak_embed("onbekend", "x", "y")


def test_laad_env_overschrijft_bestaande_variabelen_niet(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("# commentaar\nHAVEN_TEST_A=uit-bestand\nHAVEN_TEST_B='met quotes'\n", encoding="utf-8")
    monkeypatch.setenv("HAVEN_TEST_A", "al-gezet")
    monkeypatch.delenv("HAVEN_TEST_B", raising=False)
    laad_env(env)
    import os

    assert os.environ["HAVEN_TEST_A"] == "al-gezet"
    assert os.environ["HAVEN_TEST_B"] == "met quotes"


def test_kanaalkaart_heeft_vier_vaste_vragen():
    e = kanaalkaart("pulls", "Laat je pulls zien.", "Alleen foto's en video's.", "Een foto van je kaart met de set erbij.")
    assert e.title == "📌 Over #pulls"
    assert e.colour.value == KLEUREN["community"]
    assert [f.name for f in e.fields] == ["Wat mag hier?", "Zo ziet een goed voorbeeld eruit", "Hulp nodig?"]
    with pytest.raises(ValueError):
        kanaalkaart("x", "y", "z" * 1025, "v")


def test_setup_standaard_veilig_dry_run(monkeypatch):
    from scripts.setup_server import env_dry_run, env_stap

    monkeypatch.delenv("SETUP_DRY_RUN", raising=False)
    monkeypatch.delenv("SETUP_TOT_STAP", raising=False)
    assert env_dry_run() is True and env_stap() == 0
    monkeypatch.setenv("SETUP_DRY_RUN", "0")
    monkeypatch.setenv("SETUP_TOT_STAP", "9")
    assert env_dry_run() is False and env_stap() == 9
    monkeypatch.setenv("SETUP_TOT_STAP", "negen")
    with pytest.raises(SystemExit):
        env_stap()

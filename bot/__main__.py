"""Start de Haven-bot.

Bij elke start richt de bot de server in tot en met SETUP_TOT_STAP (structuur én inhoud),
en daarna blijft hij draaien voor knoppen, de tour, levels, giveaways, alerts en meer.

    SETUP_TOT_STAP=0..27   tot en met welke stap gebouwd wordt
    SETUP_DRY_RUN=1        alleen tonen wat er zou veranderen (standaard); 0 = echt uitvoeren
    DATA_DIR=/data         waar de database staat (op Railway: een volume)
"""

from __future__ import annotations

import logging
import os
import sys

import aiohttp
import discord

from bot.db import Database
from bot.kern import HavenBot
from haven.config import ConfigFout, laad_config
from haven.inhoud import InhoudFout, controleer_inhoud, laad_inhoud
from scripts.setup_server import ROOT, Inrichter, env_dry_run, env_stap, laad_env

log = logging.getLogger("haven")


def maak_bot() -> HavenBot | None:
    laad_env(ROOT / ".env")
    try:
        config = laad_config(ROOT / "config" / "server.yaml")
        inhoud = laad_inhoud()
        controleer_inhoud(inhoud, config)
    except (ConfigFout, InhoudFout) as fout:
        log.error("config of inhoud klopt niet: %s", fout)
        return None
    guild_id = os.environ.get("DISCORD_GUILD_ID", "")
    if not os.environ.get("DISCORD_TOKEN") or not guild_id.isdigit():
        log.error("DISCORD_TOKEN en DISCORD_GUILD_ID (een getal) moeten gezet zijn")
        return None
    bot = HavenBot(config, inhoud, int(guild_id), Database())
    stap, dry_run = env_stap(), env_dry_run()

    @bot.event
    async def on_ready() -> None:
        if bot.setup_klaar.is_set():
            return  # opnieuw verbonden: niet nog een keer inrichten
        guild = bot.get_guild(bot.guild_id)
        if guild is None:
            log.error("de bot zit niet in server %s; nodig hem eerst uit", bot.guild_id)
            await bot.close()
            return
        log.info("verbonden als %s met '%s'; inrichten tot en met stap %d%s", bot.user, guild.name, stap, " (dry-run)" if dry_run else "")
        inrichter = Inrichter(guild, config, stap, dry_run, inhoud)
        try:
            await inrichter.uitvoeren()
        except Exception as fout:  # noqa: BLE001 - de bot moet blijven draaien, ook als inrichten misgaat
            log.exception("inrichten mislukt")
            inrichter.waarschuw(f"inrichten mislukt: {type(fout).__name__}: {fout}")
        versie = os.environ.get("RAILWAY_GIT_COMMIT_SHA", "")[:7] or "onbekend"
        samenvatting = (
            f"🛠️ Setup tot en met stap {stap}{' (dry-run, niets veranderd)' if dry_run else ''} · versie `{versie}`: "
            f"{len(inrichter.wijzigingen)} wijziging(en), {len(inrichter.waarschuwingen)} waarschuwing(en)."
        )
        if inrichter.wijzigingen:
            samenvatting += "\n" + "\n".join(f"• {w}" for w in inrichter.wijzigingen[:15])
            if len(inrichter.wijzigingen) > 15:
                samenvatting += f"\n• … en nog {len(inrichter.wijzigingen) - 15}"
        log.info(samenvatting)
        for w in inrichter.waarschuwingen:
            log.warning(w)
        if not dry_run:
            await bot.log(samenvatting + "".join(f"\n⚠️ {w}" for w in inrichter.waarschuwingen[:10]))
        bot.setup_klaar.set()

    return bot


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", stream=sys.stdout)
    bot = maak_bot()
    if bot is None:
        return 2
    try:
        bot.run(os.environ["DISCORD_TOKEN"], log_handler=None)
    except discord.LoginFailure:
        log.error("het token is ongeldig; maak in de Developer Portal een nieuw token aan")
        return 2
    except discord.PrivilegedIntentsRequired:
        log.error("zet Server Members Intent en Message Content Intent aan onder Bot in de Developer Portal")
        return 2
    except (OSError, aiohttp.ClientError) as fout:
        log.error("kan Discord niet bereiken: %s", fout)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())

# PokeTCG Haven

De Haven-bot en de serverinrichting voor **PokeTCG Haven**, de Nederlands-Belgische Pokémon TCG-community op Discord. Alles is in het Nederlands.

Het volledige bouwplan (structuur, community, giveaways, Store, marketing, rollen en regels) staat in het [Bouwplan PokeTCG Haven](https://claude.ai/code/artifact/f8d07991-0b36-4c44-86cc-2563eb4bf05e).

> Niet verbonden aan The Pokémon Company, Nintendo of Game Freak.

## Hoe het werkt

Eén programma, de **Haven-bot**, doet twee dingen:

1. **Bij elke start richt hij de server in tot en met `SETUP_TOT_STAP`.** Dat omvat:
   - rollen, kanalen, rechten, AutoMod en Community-modus;
   - de inhoud van elk kanaal: embeds, kanaalkaarten, knoppen en menu's.

   Wat al bestaat, wordt bijgewerkt en nooit dubbel geplaatst. Setup-berichten zijn vastgepind; zo herkent de bot ze.
2. **Daarna blijft hij draaien** voor alles wat interactief is:

| Onderdeel | Wat het doet |
| --- | --- |
| Start | De knop **Kom binnen** (geeft de rol Lid en opent de server) en Nieuwe Trainer voor nieuwe leden |
| Tour | Persoonlijke tour van 7 schermen, `/tour`, de rol Wegwijs en een welkom in #voorstellen |
| Rollen | Menu's voor interesses, regio en meldingen |
| Tickets | Privégesprekken in #tickets, met een transcript in #staff-logs bij het sluiten |
| Community | #pulls alleen met media, met een thread, ⭐ en een felicitatie bij de eerste pull. Verder: een welkom per voorstelling, Pull van de Week (vrijdag), Binder Monday, Vraag van de week en het event voor de pack-avond |
| Levels | XP per bericht (maximaal 1 keer per minuut), levelrollen en `/level`. De markt opent vanaf level 5 |
| Giveaways | Een wedstrijd met kennisvraag en schiftingsvraag (`/giveaway start`), de controles, de winnaar, `/giveaway volgende`, en de mijlpaal-teller in #giveaways |
| Ledenteller | Het voicekanaal "📊 Leden: …" bovenaan, elk kwartier bijgewerkt |
| Markt | `/vouch`, `/vouches`, `/verify`, controle op foto's en tags, één collectiepost per lid, `/opgelost` |
| Winkel-radar | `/meld`: direct in #sniper-nlbe, na 10 minuten in #winkel-radar met een regio-ping. Een melding verdwijnt na 2× 👎 |
| Alerts | Automatische winkelmonitors en `/alert`: direct voor Sniper, na 10 minuten in #restocks. Verder: Gescoord!, `/uitverkocht` en persoonlijke DM's via `/pings` |
| Winkels | `/winkel toevoegen`, `/winkel lijst`, `/winkel aanuit` en `/winkel verwijderen` (alleen team) |
| Releases | `/release` met de datum, een releasedraad, een releaseavond-event en een automatisch overzicht |
| Store | De knoppen "Meer info" en "FAQ". De koopknoppen gebruiken de Whop-links uit de omgeving |
| Invites | `/invite` met een persoonlijke link. Bij 3 actieve leden krijg je 7 dagen Sniper Proef, bij 10 de rol Haven Ambassadeur |

**Wat nog niet automatisch gaat:**
- **Winkelmonitors:** werken voor winkels op Shopify. Voeg ze toe vanuit Discord met `/winkel toevoegen`; de bot test de winkel meteen en meldt hoeveel Pokémon-producten hij vindt. Alleen sealed producten (ETB's, boxen, boosters, collecties) die van uitverkocht naar op voorraad gaan, geven een alert. Andere winkels: `/alert` door het team.
- **Discord Onboarding:** die stel je zelf in Discord in na stap 9.
- **Whop:** koppel je zelf met de Discord-rollen Sniper, Elite en Founder.

## Beelden

Elk kanaal begint met een banner in de huisstijl, en elke embed toont het PH-logo. Je kunt `inhoud/afbeeldingen/logo.png` ook als **servericoon** en als **avatar van de bot** gebruiken (Developer Portal → Bot → Icon).

Een banner aanpassen: wijzig de tekst in `scripts/banners.py`, draai `python -m scripts.banners` en push. De bot ziet dat het beeld veranderd is en werkt het bericht bij.

De infographics in de Start-kanalen (eerste stappen, routekaart, huisregels, veilig handelen, trainerskaart, weekritme) komen uit `scripts/infographics.py`: `python -m scripts.infographics`.

## Hernoemen en opruimen

Onder `hernoemen` in `config/server.yaml` staan oude namen die de bot hernoemt; zo houden leden hun rol en blijven berichten staan. Onder `verwijderen` staat wat de bot opruimt. **De bot verwijdert nooit iets wat daar niet staat**, en de config weigert iets te verwijderen wat ook in het plan staat.

## Draaien op Railway

`railway.json` start de bot met `python -m bot` en herstart hem na een fout.

**Variabelen** (tabblad *Variables*):

| Variabele | Waarde |
| --- | --- |
| `DISCORD_TOKEN` | het bot-token |
| `DISCORD_GUILD_ID` | de server-ID |
| `SETUP_TOT_STAP` | tot en met welke stap de bot bouwt: `0` tot en met `24` |
| `SETUP_DRY_RUN` | `1` = alleen laten zien wat er zou veranderen (standaard), `0` = echt uitvoeren |
| `DATA_DIR` | `/data` (zie het volume hieronder) |
| `WHOP_SNIPER_URL`, `WHOP_FOUNDER_URL`, `WHOP_ELITE_URL` | de Whop-links; leeg betekent dat de knop "binnenkort" toont |

**Volume:** maak in Railway een volume aan dat op `/data` is gekoppeld. Zonder volume verdwijnen XP, vouches, giveaways en tickets bij elke nieuwe deploy.

**Zo bouw je een stap:**
1. Zet `SETUP_TOT_STAP` op de stap en `SETUP_DRY_RUN` op `1`. In de Deploy Logs zie je wat er zou veranderen.
2. Klopt het? Zet `SETUP_DRY_RUN` op `0`. De bot bouwt de stap en meldt het resultaat in #staff-logs.
3. Controleer de stap in Discord, geef je akkoord, en ga verder met de volgende stap.

**In de Developer Portal:**
- Bot: **Server Members Intent** en **Message Content Intent** aan.
- De bot heeft voor de setup Administrator nodig.
- Sleep de rol **PokeTCG Haven** in Discord helemaal naar boven, anders kan de bot andere rollen niet beheren.

## Opbouw

| Map | Inhoud |
| --- | --- |
| `config/server.yaml` | Rollen, kanalen (met stapnummer), rechten en AutoMod |
| `inhoud/` | Een bestand per kanaal met embeds, knoppen en menu's, plus de tour, de Store-teksten en de vragen van de week |
| `inhoud/afbeeldingen/` | De banners, infographics en het logo (gemaakt met `scripts/banners.py` en `scripts/infographics.py`); Discord laadt ze via GitHub |
| `haven/` | Logica zonder Discord-verbinding: config, inhoud, huisstijl, levels, giveaways, mijlpalen en alerts |
| `bot/` | De Haven-bot: kern, database (SQLite) en een cog per onderdeel |
| `scripts/setup_server.py` | De inrichting (wordt door de bot gebruikt; kan ook los draaien) |
| `tests/` | 72 tests, waaronder stresstests tegen een nagebootste Discord-server |

## Lokaal ontwikkelen

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env   # vul in; zet .env nooit in git
pytest -q
python -m bot
```

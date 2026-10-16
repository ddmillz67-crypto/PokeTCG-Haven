# PokeTCG Haven

Setup en bot voor **PokeTCG Haven**, de Nederlands-Belgische Pokémon TCG-community op Discord, met een aparte Engelse sectie.

Het volledige bouwplan (naam, structuur, premium, sniper en het stappenplan per kanaal) staat in het [Bouwplan PokeTCG Haven](https://claude.ai/code/artifact/f8d07991-0b36-4c44-86cc-2563eb4bf05e).

> Niet verbonden aan The Pokémon Company, Nintendo of Game Freak.

## Wat er nu in staat (stap 0: fundament)

| Onderdeel | Bestand |
| --- | --- |
| Rollen, kanalen, rechten en AutoMod, met een stapnummer per kanaal | `config/server.yaml` |
| Script dat de server inricht; je kunt het veilig vaker draaien | `scripts/setup_server.py` |
| Laden en controleren van de config, berekenen van de rechten | `haven/config.py` |
| Huisstijl: kleuren en vaste opbouw van embeds | `haven/huisstijl.py` |
| Tests, inclusief een stresstest tegen een nagebootste server | `tests/` |

## Installeren

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env   # vul DISCORD_TOKEN en DISCORD_GUILD_ID in
```

Zet `.env` nooit in git; dat bestand staat in `.gitignore`.

## Gebruik

```bash
# 1. Eerst kijken wat er zou veranderen (er wordt niets aangepast)
python -m scripts.setup_server --tot-stap 0 --dry-run

# 2. Uitvoeren
python -m scripts.setup_server --tot-stap 0
```

`--tot-stap N` maakt alles aan tot en met stap N uit het stappenplan (0 tot en met 24). Na het goedkeuren van een kanaal verhoog je N en draai je het script opnieuw. Wat al bestaat, wordt bijgewerkt, nooit verwijderd.

**Stap 0 doet het volgende:**

- Verificatieniveau op medium, filter op expliciete inhoud voor alle leden, en standaard alleen meldingen bij mentions
- 16 rollen in de juiste volgorde en met de kleuren uit de huisstijl
- De categorie STAFF met `#staff-logs`
- 4 AutoMod-regels: scamwoorden, invites, mention-spam en spam. Meldingen gaan naar `#staff-logs`

**Na stap 0 met de hand doen in Discord:**

1. Sleep onder Serverinstellingen > Rollen de rol **PokeTCG Haven** (de bot) helemaal naar boven.
2. Geef jezelf de rol **Admin**.
3. Zet bij stap 2 **Community** aan (Serverinstellingen > Community). Draai het script daarna opnieuw, zodat `#aankondigingen` een aankondigingskanaal wordt en Releaseavond een stage.

## Draaien op Railway

`railway.json` laat Railway het setup-script één keer draaien en daarna stoppen (geen herstart). Zet in Railway onder **Variables**:

| Variabele | Waarde |
| --- | --- |
| `DISCORD_TOKEN` | het bot-token |
| `DISCORD_GUILD_ID` | de server-ID |
| `SETUP_TOT_STAP` | het stapnummer, bijvoorbeeld `0` |
| `SETUP_DRY_RUN` | `1` = alleen laten zien wat er zou veranderen (standaard), `0` = echt uitvoeren |

Na het opslaan van de variabelen start Railway een nieuwe deploy. De uitkomst staat onder **Deploy Logs**. Begin altijd met `SETUP_DRY_RUN=1`, controleer de logs, en zet het daarna op `0`.

## Testen

```bash
pytest -q
```

De tests controleren onder meer het volgende:

- Premium is onzichtbaar voor gratis leden.
- De taalsecties zijn van elkaar gescheiden.
- Er zijn precies 24 tekstkanalen.
- Een tweede run van het script verandert niets.
- Een dry-run voert niets uit.
- Met de hand gewijzigde rechten worden hersteld.

## Vereisten in de Discord Developer Portal

- Bot: **Server Members Intent** en **Message Content Intent** aan, Public Bot uit
- Uitnodigen via OAuth2 > URL Generator met de scopes `bot` en `applications.commands`, en de permission Administrator (alleen voor de setup)

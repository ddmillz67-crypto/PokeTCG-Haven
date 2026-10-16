"""Giveaways als wedstrijd: kennisvraag + schiftingsvraag (zie de spelvoorwaarden)."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

STANDAARD_SCHIFTINGSVRAAG = "Hoeveel inzendingen komen er in totaal binnen?"
MIN_DAGEN_LID = 7


@dataclass(frozen=True)
class Inzending:
    user_id: int
    antwoord: str
    schatting: int
    tijd: float


def normaliseer(tekst: str) -> str:
    """Hoofdletters, accenten, leestekens en dubbele spaties tellen niet mee."""
    tekst = unicodedata.normalize("NFKD", tekst).encode("ascii", "ignore").decode()
    tekst = re.sub(r"[^\w\s]", " ", tekst.casefold())
    return " ".join(tekst.split())


def juiste_antwoorden(antwoorden: str) -> set[str]:
    """Meerdere goede antwoorden scheid je met |, bijvoorbeeld "Obsidian Flames|OBF"."""
    return {normaliseer(a) for a in antwoorden.split("|") if a.strip()}


def is_goed(antwoord: str, antwoorden: str) -> bool:
    return normaliseer(antwoord) in juiste_antwoorden(antwoorden)


def rangschikking(inzendingen: list[Inzending], antwoorden: str, schifting: int) -> list[Inzending]:
    """Alle goede inzendingen, de beste eerst: dichtst bij de schifting, daarna de vroegste.

    De eerste is de winnaar; meldt die zich niet binnen 72 uur, dan gaat de prijs naar de volgende.
    """
    goed = [i for i in inzendingen if is_goed(i.antwoord, antwoorden)]
    return sorted(goed, key=lambda i: (abs(i.schatting - schifting), i.tijd))


def mag_meedoen(dagen_lid: float, level: int, is_team: bool, min_level: int) -> str | None:
    """Geeft de reden terug waarom iemand niet mag meedoen, of None als het mag."""
    if is_team:
        return "Teamleden en moderators doen niet mee aan giveaways."
    if dagen_lid < MIN_DAGEN_LID:
        return f"Je moet minstens {MIN_DAGEN_LID} dagen lid zijn. Nog even geduld!"
    if level < min_level:
        return f"Je hebt minimaal level {min_level} nodig. Praat gezellig mee om XP te verdienen (`/level`)."
    return None

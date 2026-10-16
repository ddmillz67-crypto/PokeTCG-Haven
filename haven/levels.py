"""Levels: XP per bericht en de rol die bij een level hoort."""

from __future__ import annotations

import random

XP_MIN, XP_MAX = 15, 25
COOLDOWN_SECONDEN = 60

# Van hoog naar laag. Level 0 t/m 4 = Nieuwe Trainer.
LEVEL_ROLLEN: list[tuple[int, str]] = [
    (50, "Haven Legende"),
    (30, "Gym Leader"),
    (15, "Ace Trainer"),
    (5, "Trainer"),
    (0, "Nieuwe Trainer"),
]
ALLE_LEVELROLLEN = {naam for _, naam in LEVEL_ROLLEN}

MARKT_LEVEL = 5
GIVEAWAY_LEVEL = 3


def xp_voor_volgend_level(level: int) -> int:
    """XP die nodig is om van `level` naar `level + 1` te gaan."""
    return 5 * level * level + 50 * level + 100


def totaal_xp_voor_level(level: int) -> int:
    return sum(xp_voor_volgend_level(i) for i in range(level))


def level_voor_xp(xp: int) -> int:
    level = 0
    while xp >= xp_voor_volgend_level(level):
        xp -= xp_voor_volgend_level(level)
        level += 1
    return level


def voortgang(xp: int) -> tuple[int, int, int]:
    """(level, xp binnen het huidige level, xp nodig voor het volgende level)."""
    level = level_voor_xp(xp)
    return level, xp - totaal_xp_voor_level(level), xp_voor_volgend_level(level)


def rol_voor_level(level: int) -> str:
    for drempel, naam in LEVEL_ROLLEN:
        if level >= drempel:
            return naam
    return LEVEL_ROLLEN[-1][1]


def xp_voor_bericht(rng: random.Random | None = None) -> int:
    return (rng or random).randint(XP_MIN, XP_MAX)


def mag_xp_krijgen(laatst: float | None, nu: float) -> bool:
    return laatst is None or nu - laatst >= COOLDOWN_SECONDEN

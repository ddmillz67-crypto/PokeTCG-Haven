"""SQLite-opslag van de Haven-bot. Op Railway hoort DATA_DIR op een volume te staan,
anders verdwijnen XP, vouches en giveaways bij elke nieuwe deploy."""

from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS kv (sleutel TEXT PRIMARY KEY, waarde TEXT);
CREATE TABLE IF NOT EXISTS leden (
    user_id INTEGER PRIMARY KEY, xp INTEGER NOT NULL DEFAULT 0, laatst_xp REAL,
    berichten INTEGER NOT NULL DEFAULT 0, lid_sinds REAL, uitgenodigd_door INTEGER,
    actief_geteld INTEGER NOT NULL DEFAULT 0, tour_klaar INTEGER NOT NULL DEFAULT 0,
    eerste_pull INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS vouches (
    id INTEGER PRIMARY KEY AUTOINCREMENT, van INTEGER, voor INTEGER, reden TEXT, tijd REAL
);
CREATE TABLE IF NOT EXISTS giveaways (
    id INTEGER PRIMARY KEY AUTOINCREMENT, prijs TEXT, vraag TEXT, antwoorden TEXT,
    schiftingsvraag TEXT, schifting INTEGER, eind REAL, kanaal_id INTEGER, bericht_id INTEGER,
    status TEXT NOT NULL DEFAULT 'open', afbeelding TEXT, sponsor TEXT
);
CREATE TABLE IF NOT EXISTS inzendingen (
    giveaway_id INTEGER, user_id INTEGER, antwoord TEXT, schatting INTEGER, tijd REAL,
    PRIMARY KEY (giveaway_id, user_id)
);
CREATE TABLE IF NOT EXISTS gepland (
    id INTEGER PRIMARY KEY AUTOINCREMENT, wanneer REAL, soort TEXT, data TEXT, klaar INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS tickets (
    thread_id INTEGER PRIMARY KEY, user_id INTEGER, categorie TEXT, open INTEGER NOT NULL DEFAULT 1, tijd REAL
);
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT, berichten TEXT, tijd REAL, uitverkocht INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS gescoord (alert_id INTEGER, user_id INTEGER, PRIMARY KEY (alert_id, user_id));
CREATE TABLE IF NOT EXISTS pings (user_id INTEGER, categorie TEXT, PRIMARY KEY (user_id, categorie));
CREATE TABLE IF NOT EXISTS invites (code TEXT PRIMARY KEY, user_id INTEGER);
CREATE TABLE IF NOT EXISTS beloningen (user_id INTEGER, soort TEXT, PRIMARY KEY (user_id, soort));
CREATE TABLE IF NOT EXISTS toppulls (bericht_id INTEGER PRIMARY KEY, user_id INTEGER, toestemming INTEGER);
CREATE TABLE IF NOT EXISTS radar (bericht_id INTEGER PRIMARY KEY, user_id INTEGER, tijd REAL, weg INTEGER NOT NULL DEFAULT 0);
"""


class Database:
    def __init__(self, pad: str | Path | None = None):
        if pad is None:
            map_ = Path(os.environ.get("DATA_DIR", "data"))
            map_.mkdir(parents=True, exist_ok=True)
            pad = map_ / "haven.db"
        self.con = sqlite3.connect(str(pad))
        self.con.row_factory = sqlite3.Row
        self.con.executescript(SCHEMA)
        self.con.commit()

    def uitvoeren(self, sql: str, args: tuple = ()) -> sqlite3.Cursor:
        cur = self.con.execute(sql, args)
        self.con.commit()
        return cur

    def een(self, sql: str, args: tuple = ()) -> sqlite3.Row | None:
        return self.con.execute(sql, args).fetchone()

    def alle(self, sql: str, args: tuple = ()) -> list[sqlite3.Row]:
        return self.con.execute(sql, args).fetchall()

    # -- kv ------------------------------------------------------------------

    def kv_lees(self, sleutel: str, standaard: str | None = None) -> str | None:
        r = self.een("SELECT waarde FROM kv WHERE sleutel = ?", (sleutel,))
        return r["waarde"] if r else standaard

    def kv_schrijf(self, sleutel: str, waarde: str) -> None:
        self.uitvoeren("INSERT INTO kv VALUES (?, ?) ON CONFLICT(sleutel) DO UPDATE SET waarde = excluded.waarde", (sleutel, waarde))

    # -- leden -----------------------------------------------------------------

    def lid(self, user_id: int) -> sqlite3.Row:
        self.uitvoeren("INSERT OR IGNORE INTO leden (user_id, lid_sinds) VALUES (?, ?)", (user_id, time.time()))
        return self.een("SELECT * FROM leden WHERE user_id = ?", (user_id,))

    def lid_zet(self, user_id: int, **velden) -> None:
        self.lid(user_id)
        sets = ", ".join(f"{k} = ?" for k in velden)
        self.uitvoeren(f"UPDATE leden SET {sets} WHERE user_id = ?", (*velden.values(), user_id))

    # -- planner ---------------------------------------------------------------

    def plan(self, wanneer: float, soort: str, data: dict) -> int:
        return self.uitvoeren(
            "INSERT INTO gepland (wanneer, soort, data) VALUES (?, ?, ?)", (wanneer, soort, json.dumps(data))
        ).lastrowid

    def te_doen(self, nu: float) -> list[sqlite3.Row]:
        return self.alle("SELECT * FROM gepland WHERE klaar = 0 AND wanneer <= ? ORDER BY wanneer", (nu,))

    def gedaan(self, plan_id: int) -> None:
        self.uitvoeren("UPDATE gepland SET klaar = 1 WHERE id = ?", (plan_id,))

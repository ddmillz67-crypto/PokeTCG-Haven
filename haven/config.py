"""Laden en controleren van config/server.yaml, en het berekenen van rechten.

Alles hier is puur (geen Discord-verbinding), zodat het offline te testen is.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

KANAALTYPES = {"text", "news", "forum", "voice", "stage"}
MAX_STAP = 24
HEX_KLEUR = re.compile(r"^#[0-9A-Fa-f]{6}$")


class ConfigFout(ValueError):
    """De configuratie klopt niet."""


@dataclass(frozen=True)
class Rol:
    naam: str
    kleur: int = 0
    apart_tonen: bool = False
    noembaar: bool = False
    rechten: tuple[str, ...] = ()


@dataclass(frozen=True)
class Kanaal:
    naam: str
    categorie: str
    stap: int
    zichtbaar: str | tuple[str, ...]
    type: str = "text"
    alleen_lezen: bool = False
    schrijvers: tuple[str, ...] = ()
    onderwerp: str = ""
    slowmode: int = 0
    tags: tuple[str, ...] = ()


@dataclass
class ServerConfig:
    server: dict
    taalrollen: tuple[str, ...]
    staffrollen: tuple[str, ...]
    rollen: list[Rol]
    categorieen: list[str]
    kanalen: list[Kanaal]
    automod: dict = field(default_factory=dict)

    def kanalen_tot_stap(self, stap: int) -> list[Kanaal]:
        return [k for k in self.kanalen if k.stap <= stap]

    def categorieen_tot_stap(self, stap: int) -> list[str]:
        nodig = {k.categorie for k in self.kanalen_tot_stap(stap)}
        return [c for c in self.categorieen if c in nodig]


def _kleur(waarde: str | None, waar: str) -> int:
    if waarde is None:
        return 0
    if not HEX_KLEUR.match(waarde):
        raise ConfigFout(f"{waar}: kleur '{waarde}' moet de vorm #RRGGBB hebben")
    return int(waarde[1:], 16)


def laad_config(pad: str | Path) -> ServerConfig:
    data = yaml.safe_load(Path(pad).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ConfigFout("server.yaml is leeg of geen mapping")

    rollen = [
        Rol(
            naam=r["naam"],
            kleur=_kleur(r.get("kleur"), f"rol {r['naam']}"),
            apart_tonen=bool(r.get("apart_tonen", False)),
            noembaar=bool(r.get("noembaar", False)),
            rechten=tuple(r.get("rechten", ())),
        )
        for r in data.get("rollen", [])
    ]

    categorieen: list[str] = []
    kanalen: list[Kanaal] = []
    for cat in data.get("categorieen", []):
        categorieen.append(cat["naam"])
        for k in cat.get("kanalen", []):
            zichtbaar = k.get("zichtbaar", "taal")
            kanalen.append(
                Kanaal(
                    naam=k["naam"],
                    categorie=cat["naam"],
                    stap=int(k["stap"]),
                    zichtbaar=zichtbaar if isinstance(zichtbaar, str) else tuple(zichtbaar),
                    type=k.get("type", "text"),
                    alleen_lezen=bool(k.get("alleen_lezen", False)),
                    schrijvers=tuple(k.get("schrijvers", ())),
                    onderwerp=k.get("onderwerp", ""),
                    slowmode=int(k.get("slowmode", 0)),
                    tags=tuple(k.get("tags", ())),
                )
            )

    config = ServerConfig(
        server=data.get("server", {}),
        taalrollen=tuple(data.get("taalrollen", ())),
        staffrollen=tuple(data.get("staffrollen", ())),
        rollen=rollen,
        categorieen=categorieen,
        kanalen=kanalen,
        automod=data.get("automod", {}),
    )
    controleer(config)
    return config


def controleer(config: ServerConfig) -> None:
    """Gooit ConfigFout bij de eerste fout die gevonden wordt."""
    rolnamen = [r.naam for r in config.rollen]
    dubbel = {n for n in rolnamen if rolnamen.count(n) > 1}
    if dubbel:
        raise ConfigFout(f"dubbele rollen: {sorted(dubbel)}")
    bekend = set(rolnamen)

    for naam in (*config.taalrollen, *config.staffrollen):
        if naam not in bekend:
            raise ConfigFout(f"rol '{naam}' wordt gebruikt maar staat niet onder rollen")

    kanaalnamen = [k.naam for k in config.kanalen]
    dubbel = {n for n in kanaalnamen if kanaalnamen.count(n) > 1}
    if dubbel:
        raise ConfigFout(f"dubbele kanalen: {sorted(dubbel)}")

    for k in config.kanalen:
        waar = f"kanaal {k.naam}"
        if k.type not in KANAALTYPES:
            raise ConfigFout(f"{waar}: onbekend type '{k.type}'")
        if not 0 <= k.stap <= MAX_STAP:
            raise ConfigFout(f"{waar}: stap {k.stap} valt buiten 0-{MAX_STAP}")
        if isinstance(k.zichtbaar, str):
            if k.zichtbaar not in {"iedereen", "taal"}:
                raise ConfigFout(f"{waar}: zichtbaar '{k.zichtbaar}' moet iedereen, taal of een lijst rollen zijn")
        else:
            for rol in k.zichtbaar:
                if rol not in bekend:
                    raise ConfigFout(f"{waar}: onbekende rol '{rol}' in zichtbaar")
        for rol in k.schrijvers:
            if rol not in bekend:
                raise ConfigFout(f"{waar}: onbekende rol '{rol}' in schrijvers")
        if k.tags and k.type != "forum":
            raise ConfigFout(f"{waar}: tags kan alleen bij een forum")
        if len(k.tags) > 20:
            raise ConfigFout(f"{waar}: Discord staat maximaal 20 forumtags toe")
        if not 0 <= k.slowmode <= 21600:
            raise ConfigFout(f"{waar}: slowmode moet tussen 0 en 21600 seconden liggen")
        if len(k.onderwerp) > 1024:
            raise ConfigFout(f"{waar}: onderwerp is langer dan 1024 tekens")


# Een rechtenset is een dict {recht: True/False}; ontbrekend = overnemen van de server.
Rechten = dict[str, bool]


def zichtbare_rollen(config: ServerConfig, kanaal: Kanaal) -> tuple[str, ...]:
    if kanaal.zichtbaar == "taal":
        return config.taalrollen
    if kanaal.zichtbaar == "iedereen":
        return ()
    return kanaal.zichtbaar


def kanaal_rechten(config: ServerConfig, kanaal: Kanaal) -> dict[str, Rechten]:
    """Rechten per rol voor een kanaal. De sleutel '@everyone' is de standaardrol.

    Staffrollen kunnen altijd lezen en schrijven. In een alleen-lezen-kanaal mogen
    leden wel reageren met emoji, zodat aankondigingen en alerts interactief blijven.
    """
    spraak = kanaal.type in {"voice", "stage"}
    lees = "connect" if spraak else "send_messages"
    rechten: dict[str, Rechten] = {}

    if kanaal.zichtbaar == "iedereen":
        iedereen: Rechten = {"view_channel": True}
        if kanaal.alleen_lezen:
            iedereen.update({lees: False, "add_reactions": True})
            if not spraak:
                iedereen.update({"create_public_threads": False, "create_private_threads": False})
        rechten["@everyone"] = iedereen
    else:
        rechten["@everyone"] = {"view_channel": False}
        for rol in zichtbare_rollen(config, kanaal):
            r: Rechten = {"view_channel": True}
            if kanaal.alleen_lezen:
                r.update({lees: False, "add_reactions": True})
                if not spraak:
                    r.update({"create_public_threads": False, "create_private_threads": False})
            rechten[rol] = r

    for rol in kanaal.schrijvers:
        rechten.setdefault(rol, {"view_channel": True})
        rechten[rol].update({"view_channel": True, lees: True})

    for rol in config.staffrollen:
        if spraak:
            rechten[rol] = {"view_channel": True, "connect": True, "mute_members": True}
        else:
            rechten[rol] = {"view_channel": True, "send_messages": True, "manage_messages": True}

    return rechten


def categorie_rechten(config: ServerConfig, categorie: str) -> dict[str, Rechten]:
    """Een categorie is zichtbaar voor de vereniging van wie de kanalen erin mag zien.

    De kanalen zelf krijgen hun eigen rechten, dus dit bepaalt alleen of de
    categoriekop in de lijst verschijnt.
    """
    kanalen = [k for k in config.kanalen if k.categorie == categorie]
    if any(k.zichtbaar == "iedereen" for k in kanalen):
        return {"@everyone": {"view_channel": True}}
    rollen: list[str] = []
    for k in kanalen:
        for rol in (*zichtbare_rollen(config, k), *k.schrijvers):
            if rol not in rollen:
                rollen.append(rol)
    rechten: dict[str, Rechten] = {"@everyone": {"view_channel": False}}
    for rol in (*rollen, *config.staffrollen):
        rechten[rol] = {"view_channel": True}
    return rechten

"""Inhoud per kanaal: embeds, knoppen en menu's uit inhoud/<kanaal>.yaml.

Teksten kunnen verwijzingen bevatten die bij het plaatsen worden ingevuld:

    {#regels}          -> een klikbare link naar #regels
    {@Haven Helper}    -> een vermelding van de rol Haven Helper
    {link:#store}      -> de URL van #store (voor linkknoppen)
    {env:WHOP_SNIPER}  -> een waarde uit de omgeving (bijvoorbeeld een Whop-link)

Dit bestand is puur: geen verbinding met Discord nodig, zodat alles offline te testen is.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import discord
import yaml

from haven.config import ServerConfig
from haven.huisstijl import FOOTER, KLEUREN

INHOUD_MAP = Path(__file__).resolve().parent.parent / "inhoud"
PREFIX = "haven:"

# Alle knop- en menu-acties die de Haven-bot afhandelt. Een onbekende actie is een fout.
ACTIES = {
    "taal:nlbe", "taal:en",
    "tour:start", "tour:kwijt",
    "regels:vraag",
    "rollen:interesses", "rollen:regio", "rollen:pings",
    "ticket:hulp", "ticket:store", "ticket:melding", "ticket:partner", "ticket:giveaway",
    "store:info:sniper", "store:info:founder", "store:info:elite", "store:info:partner", "store:faq",
    "invite:mijn",
}

STIJLEN = {
    "primair": discord.ButtonStyle.primary,
    "secundair": discord.ButtonStyle.secondary,
    "groen": discord.ButtonStyle.success,
    "rood": discord.ButtonStyle.danger,
}

VERWIJZING = re.compile(r"\{(#|@|link:#|env:)([^{}]+)\}")


class InhoudFout(ValueError):
    """Een inhoudsbestand klopt niet."""


@dataclass(frozen=True)
class Knop:
    label: str
    actie: str | None = None
    url: str | None = None
    kanaal: str | None = None
    stijl: str = "secundair"
    emoji: str | None = None


@dataclass(frozen=True)
class MenuOptie:
    label: str
    rol: str
    emoji: str | None = None
    beschrijving: str | None = None


@dataclass(frozen=True)
class Menu:
    actie: str
    plaatshouder: str
    opties: tuple[MenuOptie, ...]
    max_keuzes: int | None = None  # None = zoveel als er opties zijn


@dataclass(frozen=True)
class Bericht:
    sleutel: str
    embeds: tuple[dict, ...]
    knoppen: tuple[Knop, ...] = ()
    menu: Menu | None = None
    post_titel: str | None = None  # alleen voor forums: de titel van de vastgepinde post


@dataclass(frozen=True)
class KanaalInhoud:
    kanaal: str
    berichten: tuple[Bericht, ...]


@dataclass
class Context:
    """Wat nodig is om verwijzingen in te vullen."""

    guild_id: int = 0
    kanalen: dict[str, int] = field(default_factory=dict)
    rollen: dict[str, int] = field(default_factory=dict)
    env: dict[str, str] = field(default_factory=lambda: dict(os.environ))


# -- laden en controleren -----------------------------------------------------


def _knop(d: dict) -> Knop:
    return Knop(
        label=d["label"], actie=d.get("actie"), url=d.get("url"), kanaal=d.get("kanaal"),
        stijl=d.get("stijl", "secundair"), emoji=d.get("emoji"),
    )


def _bericht(d: dict) -> Bericht:
    menu = None
    if "menu" in d:
        m = d["menu"]
        menu = Menu(
            actie=m["actie"],
            plaatshouder=m["plaatshouder"],
            opties=tuple(
                MenuOptie(o["label"], o["rol"], o.get("emoji"), o.get("beschrijving")) for o in m["opties"]
            ),
            max_keuzes=m.get("max"),
        )
    return Bericht(
        sleutel=d["sleutel"],
        embeds=tuple(d.get("embeds", ())),
        knoppen=tuple(_knop(k) for k in d.get("knoppen", ())),
        menu=menu,
        post_titel=d.get("post_titel"),
    )


def laad_inhoud(map_: Path = INHOUD_MAP) -> dict[str, KanaalInhoud]:
    result: dict[str, KanaalInhoud] = {}
    for pad in sorted(map_.glob("*.yaml")):
        data = yaml.safe_load(pad.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or "kanaal" not in data:
            continue  # bijvoorbeeld tour.yaml of store.yaml: geen kanaalinhoud
        kanaal = data["kanaal"]
        if kanaal in result:
            raise InhoudFout(f"{pad.name}: kanaal {kanaal} heeft al een inhoudsbestand")
        result[kanaal] = KanaalInhoud(kanaal, tuple(_bericht(b) for b in data.get("berichten", ())))
    return result


def laad_yaml(naam: str, map_: Path = INHOUD_MAP) -> dict:
    return yaml.safe_load((map_ / naam).read_text(encoding="utf-8"))


def _teksten(bericht: Bericht) -> list[str]:
    teksten: list[str] = []
    for e in bericht.embeds:
        teksten += [e.get("titel", ""), e.get("beschrijving", "")]
        for v in e.get("velden", ()):
            teksten += [v["naam"], v["waarde"]]
    for k in bericht.knoppen:
        teksten += [k.label, k.url or ""]
    if bericht.menu:
        teksten.append(bericht.menu.plaatshouder)
    return teksten


def controleer_inhoud(inhoud: dict[str, KanaalInhoud], config: ServerConfig) -> None:
    """Controleert tegen de config en tegen de limieten van Discord. Gooit InhoudFout."""
    kanalen = {k.naam: k for k in config.kanalen}
    rollen = {r.naam for r in config.rollen}
    for naam, ki in inhoud.items():
        waar = f"inhoud {naam}"
        if naam not in kanalen:
            raise InhoudFout(f"{waar}: kanaal bestaat niet in de config")
        type_ = kanalen[naam].type
        if type_ not in {"text", "news", "forum"}:
            raise InhoudFout(f"{waar}: in een {type_}-kanaal kunnen geen berichten staan")
        sleutels = [b.sleutel for b in ki.berichten]
        if len(set(sleutels)) != len(sleutels):
            raise InhoudFout(f"{waar}: dubbele sleutels")
        if type_ == "forum" and (len(ki.berichten) != 1 or not ki.berichten[0].post_titel):
            raise InhoudFout(f"{waar}: een forum heeft precies één bericht met een post_titel")
        for b in ki.berichten:
            _controleer_bericht(b, f"{waar}/{b.sleutel}", kanalen, rollen)


def _controleer_bericht(b: Bericht, waar: str, kanalen: dict, rollen: set[str]) -> None:
    if not b.embeds:
        raise InhoudFout(f"{waar}: minstens één embed nodig")
    if len(b.embeds) > 10:
        raise InhoudFout(f"{waar}: maximaal 10 embeds per bericht")
    totaal = 0
    for e in b.embeds:
        if e.get("soort", "merk") not in KLEUREN:
            raise InhoudFout(f"{waar}: onbekende soort '{e.get('soort')}'")
        titel, beschrijving = e.get("titel", ""), e.get("beschrijving", "")
        if len(titel) > 256 or len(beschrijving) > 4096:
            raise InhoudFout(f"{waar}: titel of beschrijving te lang")
        velden = e.get("velden", ())
        if len(velden) > 25:
            raise InhoudFout(f"{waar}: maximaal 25 velden")
        for v in velden:
            if len(v["naam"]) > 256 or len(v["waarde"]) > 1024:
                raise InhoudFout(f"{waar}: veld '{v['naam'][:30]}' te lang")
        totaal += len(titel) + len(beschrijving) + len(FOOTER) + sum(len(v["naam"]) + len(v["waarde"]) for v in velden)
    if totaal > 6000:
        raise InhoudFout(f"{waar}: alle embeds samen zijn {totaal} tekens; Discord staat er 6000 toe")
    if len(b.knoppen) > 20:
        raise InhoudFout(f"{waar}: maximaal 20 knoppen (4 rijen), plus eventueel een menu")
    for k in b.knoppen:
        doelen = [x for x in (k.actie, k.url, k.kanaal) if x]
        if len(doelen) != 1:
            raise InhoudFout(f"{waar}: knop '{k.label}' heeft precies één van actie, url of kanaal nodig")
        if len(k.label) > 80:
            raise InhoudFout(f"{waar}: knoplabel '{k.label[:30]}' te lang")
        if k.actie and k.actie not in ACTIES:
            raise InhoudFout(f"{waar}: onbekende actie '{k.actie}'")
        if k.kanaal and k.kanaal not in kanalen:
            raise InhoudFout(f"{waar}: knop verwijst naar onbekend kanaal '{k.kanaal}'")
        if k.stijl not in STIJLEN:
            raise InhoudFout(f"{waar}: onbekende knopstijl '{k.stijl}'")
    if b.menu:
        if b.menu.actie not in ACTIES:
            raise InhoudFout(f"{waar}: onbekende menu-actie '{b.menu.actie}'")
        if not 1 <= len(b.menu.opties) <= 25:
            raise InhoudFout(f"{waar}: een menu heeft 1 tot 25 opties")
        for o in b.menu.opties:
            if o.rol not in rollen:
                raise InhoudFout(f"{waar}: menu-optie verwijst naar onbekende rol '{o.rol}'")
    for tekst in _teksten(b):
        for soort, naam in VERWIJZING.findall(tekst):
            if soort in {"#", "link:#"} and naam not in kanalen:
                raise InhoudFout(f"{waar}: verwijzing naar onbekend kanaal '{naam}'")
            if soort == "@" and naam not in rollen:
                raise InhoudFout(f"{waar}: verwijzing naar onbekende rol '{naam}'")


# -- invullen en bouwen -------------------------------------------------------


def vul_in(tekst: str, ctx: Context) -> str:
    def vervang(m: re.Match) -> str:
        soort, naam = m.group(1), m.group(2)
        if soort == "#":
            return f"<#{ctx.kanalen[naam]}>" if naam in ctx.kanalen else f"#{naam}"
        if soort == "@":
            return f"<@&{ctx.rollen[naam]}>" if naam in ctx.rollen else f"@{naam}"
        if soort == "link:#":
            if naam in ctx.kanalen and ctx.guild_id:
                return f"https://discord.com/channels/{ctx.guild_id}/{ctx.kanalen[naam]}"
            return ""
        return ctx.env.get(naam, "")

    return VERWIJZING.sub(vervang, tekst)


def bouw_embeds(bericht: Bericht, ctx: Context) -> list[discord.Embed]:
    embeds = []
    for e in bericht.embeds:
        embed = discord.Embed(
            title=vul_in(e.get("titel", ""), ctx) or None,
            description=vul_in(e.get("beschrijving", ""), ctx).strip() or None,
            colour=KLEUREN[e.get("soort", "merk")],
        )
        embed.set_author(name=e.get("auteur", "PokeTCG Haven"))
        embed.set_footer(text=e.get("footer", FOOTER))
        for v in e.get("velden", ()):
            embed.add_field(name=vul_in(v["naam"], ctx), value=vul_in(v["waarde"], ctx), inline=v.get("inline", False))
        if e.get("afbeelding"):
            embed.set_image(url=vul_in(e["afbeelding"], ctx))
        if e.get("thumbnail"):
            embed.set_thumbnail(url=vul_in(e["thumbnail"], ctx))
        embeds.append(embed)
    return embeds


def knop_url(knop: Knop, ctx: Context) -> str:
    if knop.kanaal:
        return vul_in("{link:#" + knop.kanaal + "}", ctx)
    return vul_in(knop.url or "", ctx)


def bouw_view(bericht: Bericht, ctx: Context) -> discord.ui.View | None:
    """De knoppen en het menu als een view. Een linkknop zonder geldige URL wordt een
    uitgeschakelde knop met \"binnenkort\", zodat er nooit een kapotte link staat."""
    if not bericht.knoppen and not bericht.menu:
        return None
    view = discord.ui.View(timeout=None)
    rij = 0
    if bericht.menu:
        m = bericht.menu
        opties = [
            discord.SelectOption(label=o.label, value=o.rol, emoji=o.emoji, description=o.beschrijving)
            for o in m.opties
        ]
        view.add_item(
            discord.ui.Select(
                custom_id=PREFIX + m.actie, placeholder=m.plaatshouder,
                min_values=0, max_values=m.max_keuzes or len(opties), options=opties, row=0,
            )
        )
        rij = 1
    for i, k in enumerate(bericht.knoppen):
        r = rij + i // 5
        if k.actie:
            view.add_item(discord.ui.Button(label=k.label, custom_id=PREFIX + k.actie, style=STIJLEN[k.stijl], emoji=k.emoji, row=r))
        else:
            url = knop_url(k, ctx)
            if url.startswith("https://"):
                view.add_item(discord.ui.Button(label=k.label, url=url, emoji=k.emoji, row=r))
            else:
                view.add_item(discord.ui.Button(label=f"{k.label} (binnenkort)", disabled=True, emoji=k.emoji, row=r, custom_id=f"{PREFIX}uit:{bericht.sleutel}:{i}"))
    return view


# -- vergelijken (om onnodig bewerken te voorkomen) ----------------------------


def _s(waarde):
    return waarde.strip() if isinstance(waarde, str) else waarde


def embed_kern(e: dict) -> dict:
    """De delen van een embed die wij instellen; Discord voegt zelf extra velden toe
    en haalt spaties aan het begin en eind weg."""
    return {
        "title": _s(e.get("title")),
        "description": _s(e.get("description")),
        "color": e.get("color"),
        "author": _s((e.get("author") or {}).get("name")),
        "footer": _s((e.get("footer") or {}).get("text")),
        "fields": [(_s(f.get("name")), _s(f.get("value")), bool(f.get("inline"))) for f in e.get("fields", [])],
        "image": (e.get("image") or {}).get("url"),
        "thumbnail": (e.get("thumbnail") or {}).get("url"),
    }


def componenten_kern(rijen: list[dict]) -> list:
    kern = []
    for rij in rijen:
        for c in rij.get("components", []):
            opties = [(o.get("label"), o.get("value")) for o in c.get("options", [])]
            kern.append((c.get("type"), c.get("custom_id"), c.get("url"), c.get("label"), bool(c.get("disabled")), tuple(opties)))
    return kern


def is_gelijk(huidige_embeds: list[dict], huidige_componenten: list[dict], embeds: list[discord.Embed], view) -> bool:
    gewenst_comp = view.to_components() if view else []
    return [embed_kern(e) for e in huidige_embeds] == [embed_kern(e.to_dict()) for e in embeds] and componenten_kern(
        huidige_componenten
    ) == componenten_kern(gewenst_comp)

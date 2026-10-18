import pytest

from haven.monitors import Winkel, categorie_voor, normaliseer_url, prijs_tekst, samenvatting, verwerk

W = Winkel("Testwinkel", "https://test.nl")


def product(pid, titel, beschikbaar, prijs="59.99", vendor="Pokémon"):
    return {
        "id": pid, "title": titel, "handle": f"p-{pid}", "vendor": vendor, "product_type": "", "tags": [],
        "images": [{"src": f"https://cdn.test/{pid}.png"}],
        "variants": [{"id": pid * 10, "available": beschikbaar, "price": prijs}],
    }


@pytest.mark.parametrize(
    ("titel", "verwacht"),
    [
        ("Pokémon Scarlet & Violet Prismatic Evolutions Elite Trainer Box", "etb"),
        ("Pokemon TCG Surging Sparks Booster Box (36 packs)", "booster-box"),
        ("Pokémon Journey Together Booster Bundle", "booster"),
        ("Pokémon 151 Ultra Premium Collection", "collectie"),
        ("Pokémon Terastal Festival Booster Box Japanese", "japans"),
        ("Charizard ex 223/197 Single", None),
        ("Ultra Pro Pokémon Sleeves Pikachu", None),
        ("Pokémon Binder 9-pocket", None),
    ],
)
def test_categorie(titel, verwacht):
    assert categorie_voor({"title": titel}) == verwacht


def test_eerste_ronde_geeft_geen_alerts():
    alerts, stand = verwerk(W, [product(1, "Pokémon Elite Trainer Box", True)], None)
    assert alerts == [] and stand == {10: True}


def test_alert_alleen_bij_terug_op_voorraad():
    _, stand = verwerk(W, [product(1, "Pokémon Elite Trainer Box", False), product(2, "Pokémon Booster Box", True)], None)
    alerts, stand = verwerk(W, [product(1, "Pokémon Elite Trainer Box", True), product(2, "Pokémon Booster Box", True)], stand)
    assert [a.product for a in alerts] == ["Pokémon Elite Trainer Box"]
    a = alerts[0]
    assert a.url == "https://test.nl/products/p-1" and a.prijs == "€ 59,99" and a.categorie == "etb" and a.winkel == "Testwinkel"
    alerts, _ = verwerk(W, [product(1, "Pokémon Elite Trainer Box", True)], stand)
    assert alerts == [], "nog steeds op voorraad: geen tweede alert"


def test_nieuw_product_op_voorraad_geeft_alert_en_niet_pokemon_niet():
    _, stand = verwerk(W, [], None)
    alerts, _ = verwerk(W, [product(3, "Pokémon Booster Bundle", True), product(4, "Magic Booster Box", True, vendor="Wizards")], stand)
    assert [a.product for a in alerts] == ["Pokémon Booster Bundle"]


def test_affiliate_link():
    w = Winkel("Partner", "https://partner.nl", affiliate="https://klik.nl/?to={url}")
    _, stand = verwerk(w, [product(1, "Pokémon ETB", False)], None)
    alerts, _ = verwerk(w, [product(1, "Pokémon ETB", True)], stand)
    assert alerts[0].url == "https://klik.nl/?to=https://partner.nl/products/p-1" and alerts[0].affiliate


def test_hulpjes():
    assert normaliseer_url("Winkel.nl/collections/pokemon") == "https://winkel.nl"
    with pytest.raises(ValueError):
        normaliseer_url("http://winkel.nl")
    assert prijs_tekst("1299.5") == "€ 1.299,50" and prijs_tekst(None) == ""
    assert samenvatting([product(1, "Pokémon ETB", True), product(2, "Pokémon Single kaart", True)]) == (2, 1, 1)

from backend.detectors.identifier import (
    best_card_match,
    card_response,
    clean_card_name,
    select_market_price,
)


def test_clean_card_name_removes_hp_text():
    assert clean_card_name("Charizard ex HP330\nFire Spin") == "Charizard ex"


def test_best_card_match_prefers_closest_name():
    cards = [
        {"id": "one", "name": "Charmander"},
        {"id": "two", "name": "Charizard ex"},
    ]

    assert best_card_match("Charizard ex", cards)["id"] == "two"


def test_select_market_price_prefers_tcgplayer_usd_market_price():
    pricing = {
        "tcgplayer": {
            "normal": {
                "lowPrice": 1.25,
                "marketPrice": 2.75,
            },
        },
        "cardmarket": {
            "trend": 1.5,
        },
    }

    assert select_market_price(pricing) == (2.75, "USD")


def test_select_market_price_falls_back_to_cardmarket_eur():
    pricing = {
        "cardmarket": {
            "trend": 3.4,
        },
    }

    assert select_market_price(pricing) == (3.4, "EUR")


def test_card_response_marks_missing_price_unavailable():
    response = card_response({
        "id": "swsh3-136",
        "name": "Charizard",
        "set": {"name": "Darkness Ablaze"},
        "localId": "136",
        "rarity": "Rare",
        "image": "https://assets.tcgdex.net/en/swsh/swsh3/136",
    })

    assert response["price"] == "Pricing unavailable"
    assert response["currency"] == ""
    assert response["image"].endswith("/high.webp")

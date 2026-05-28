from backend.detectors.identifier import (
    best_card_match,
    card_response,
    clean_card_name,
    extract_card_number,
    extract_promo_hint,
    select_market_price,
)
from backend.app import identify_card_safely


def test_clean_card_name_removes_hp_text():
    assert clean_card_name("Charizard ex HP330\nFire Spin") == "Charizard ex"


def test_best_card_match_prefers_closest_name():
    cards = [
        {"id": "one", "name": "Charmander"},
        {"id": "two", "name": "Charizard ex"},
    ]

    assert best_card_match("Charizard ex", cards)["id"] == "two"


def test_best_card_match_uses_collector_number_hint():
    cards = [
        {"id": "one", "name": "Pikachu", "localId": "25"},
        {"id": "two", "name": "Pikachu", "localId": "58"},
    ]

    assert best_card_match("Pikachu", cards, {"number": "58"})["id"] == "two"


def test_best_card_match_uses_promo_hint():
    cards = [
        {"id": "regular", "name": "Pikachu", "localId": "25", "set": {"name": "Base Set"}},
        {"id": "promo", "name": "Pikachu", "localId": "SWSH020", "set": {"name": "SWSH Black Star Promos"}},
    ]

    assert best_card_match("Pikachu", cards, {"is_promo": True})["id"] == "promo"


def test_extract_card_number_reads_bottom_collector_number():
    assert extract_card_number("Illus. Someone 058/198 ©2023 Pokemon") == "058"
    assert extract_card_number("SVP 050 Black Star Promo") == "SVP050"


def test_extract_promo_hint_reads_bottom_promo_text():
    assert extract_promo_hint("SVP 050 Black Star Promo")


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


def test_identify_card_safely_returns_graceful_failure(monkeypatch):
    def fail_identification(_image):
        raise RuntimeError("OCR unavailable")

    monkeypatch.setattr("backend.app.identify_card", fail_identification)

    result = identify_card_safely(object())

    assert result == {
        "success": False,
        "error": "OCR unavailable",
    }

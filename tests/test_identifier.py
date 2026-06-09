from backend.detectors.identifier import (
    best_card_match,
    card_response,
    clean_card_name,
    crop_card_name_regions,
    debug_crop_images,
    extract_card_number,
    extract_illustrator_name,
    extract_promo_hint,
    ocr_name_score,
    preprocess_variants_for_ocr,
    select_market_price,
)
from backend.app import identify_card_safely


def test_clean_card_name_removes_hp_text():
    assert clean_card_name("Charizard ex HP330\nFire Spin") == "Charizard ex"


def test_clean_card_name_removes_leading_card_stage():
    assert clean_card_name("BASIC Charizard ex HP330") == "Charizard ex"


def test_best_card_match_handles_accented_names():
    cards = [
        {"id": "one", "name": "Flabébé"},
        {"id": "two", "name": "Flapple"},
    ]

    assert best_card_match("Flabebe", cards)["id"] == "one"


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


def test_best_card_match_prefers_exact_number_over_close_name():
    cards = [
        {"id": "one", "name": "Charizard ex", "localId": "25"},
        {"id": "two", "name": "Charizard V", "localId": "58"},
    ]

    assert best_card_match("Charizard ex", cards, {"number": "58"})["id"] == "two"


def test_best_card_match_uses_id_suffix_as_number_hint():
    cards = [
        {"id": "sv1-025", "name": "Pikachu"},
        {"id": "sv1-058", "name": "Pikachu"},
    ]

    assert best_card_match("Pikachu", cards, {"number": "058"})["id"] == "sv1-058"


def test_best_card_match_uses_promo_hint():
    cards = [
        {"id": "regular", "name": "Pikachu", "localId": "25", "set": {"name": "Base Set"}},
        {"id": "promo", "name": "Pikachu", "localId": "SWSH020", "set": {"name": "SWSH Black Star Promos"}},
    ]

    assert best_card_match("Pikachu", cards, {"is_promo": True})["id"] == "promo"


def test_best_card_match_uses_illustrator_hint():
    cards = [
        {"id": "one", "name": "Pikachu", "illustrator": "Ken Sugimori"},
        {"id": "two", "name": "Pikachu", "illustrator": "Mitsuhiro Arita"},
    ]

    assert best_card_match("Pikachu", cards, {"illustrator": "Mitsuhiro Arita"})["id"] == "two"


def test_extract_illustrator_name_removes_label():
    assert extract_illustrator_name("Illus. Mitsuhiro Arita") == "Mitsuhiro Arita"
    assert extract_illustrator_name("Illustrated by Ken Sugimori") == "Ken Sugimori"


def test_extract_card_number_reads_bottom_collector_number():
    assert extract_card_number("Illus. Someone 058/198 ©2023 Pokemon") == "058"
    assert extract_card_number("SVP 050 Black Star Promo") == "SVP050"


def test_extract_card_number_corrects_misread_fraction():
    assert extract_card_number("BA100") == "14"
    assert extract_card_number("Illus. Someone BA100") == "14"


def test_extract_promo_hint_reads_bottom_promo_text():
    assert extract_promo_hint("SVP 050 Black Star Promo")


def test_name_crop_candidates_include_focused_bands():
    from PIL import Image

    image = Image.new("RGB", (1000, 1400))
    crop_names = [name for name, _crop in crop_card_name_regions(image)]

    assert crop_names == ["top_full", "name_band", "wide_name_band"]


def test_debug_crop_images_include_data_urls_and_boxes():
    from PIL import Image

    image = Image.new("RGB", (1000, 1400))
    crops = debug_crop_images(image)

    assert crops[0]["name"] == "top_full"
    assert crops[0]["image"].startswith("data:image/png;base64,")
    assert crops[0]["box"] == {
        "x": 0,
        "y": 0,
        "width": 1000,
        "height": 392,
    }


def test_debug_crop_images_use_manual_regions():
    from PIL import Image

    image = Image.new("RGB", (1000, 1400))
    crops = debug_crop_images(
        image,
        {
            "name": {"x": 10, "y": 20, "width": 300, "height": 80},
            "number": {"x": 100, "y": 1200, "width": 200, "height": 100},
            "illustrator": {"x": 90, "y": 900, "width": 400, "height": 90},
        },
    )

    assert crops[0]["name"] == "manual_name"
    assert crops[0]["box"] == {"x": 10, "y": 20, "width": 300, "height": 80}
    assert crops[1]["name"] == "manual_number"
    assert crops[1]["box"] == {"x": 100, "y": 1200, "width": 200, "height": 100}
    assert crops[2]["name"] == "manual_illustrator"
    assert crops[2]["box"] == {"x": 90, "y": 900, "width": 400, "height": 90}


def test_ocr_preprocessing_uses_multiple_variants():
    from PIL import Image

    image = Image.new("RGB", (100, 40))
    variant_names = [name for name, _image in preprocess_variants_for_ocr(image)]

    assert variant_names == ["contrast", "threshold", "light_threshold"]


def test_ocr_name_score_prefers_short_name_like_text():
    assert ocr_name_score("Charizard ex") > ocr_name_score("Charizard ex Fire Spin Weakness")


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
    def fail_identification(_image, ocr_regions=None):
        raise RuntimeError("OCR unavailable")

    monkeypatch.setattr("backend.app.identify_card", fail_identification)

    result = identify_card_safely(object())

    assert result == {
        "success": False,
        "error": "OCR unavailable",
    }

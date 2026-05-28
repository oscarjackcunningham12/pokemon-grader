import json
import re
import ssl
from difflib import SequenceMatcher
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from PIL import Image, ImageFilter, ImageOps


TCGDEX_API_BASE = "https://api.tcgdex.net/v2/en/cards"


class CardIdentificationError(Exception):
    """Raised when a card cannot be identified from the uploaded image."""


def identify_card(image: Image.Image) -> dict:
    card_name = extract_card_name(image)

    if not card_name:
        raise CardIdentificationError("Could not read card name")

    search_results = search_tcgdex_cards(card_name)
    match = best_card_match(card_name, search_results)

    if not match:
        raise CardIdentificationError("No matching card found")

    card_details = fetch_tcgdex_card(match["id"])
    return card_response(card_details)


def extract_card_name(image: Image.Image) -> str | None:
    try:
        import pytesseract
    except Exception as exc:
        raise CardIdentificationError("Could not read card name") from exc

    top = crop_card_name_region(image)
    processed = preprocess_for_ocr(top)

    try:
        text = pytesseract.image_to_string(
            processed,
            config="--psm 6",
        )
    except Exception as exc:
        raise CardIdentificationError("Could not read card name") from exc

    return clean_card_name(text)


def crop_card_name_region(image: Image.Image) -> Image.Image:
    image = ImageOps.exif_transpose(image).convert("RGB")
    width, height = image.size

    return image.crop((
        0,
        0,
        width,
        max(1, int(height * 0.28)),
    ))


def preprocess_for_ocr(image: Image.Image) -> Image.Image:
    grayscale = ImageOps.grayscale(image)
    enlarged = grayscale.resize(
        (grayscale.width * 2, grayscale.height * 2),
        Image.Resampling.LANCZOS,
    )
    sharpened = enlarged.filter(ImageFilter.SHARPEN)
    return ImageOps.autocontrast(sharpened)


def clean_card_name(text: str) -> str | None:
    candidates = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        line = re.sub(r"\bHP\s*\d+\b.*", "", line, flags=re.IGNORECASE)
        line = re.sub(r"\b\d+\s*HP\b.*", "", line, flags=re.IGNORECASE)
        line = re.sub(r"[^A-Za-z0-9 .:'’&-]", " ", line)
        line = re.sub(r"\s+", " ", line).strip(" -.:")

        if not is_likely_card_name(line):
            continue

        candidates.append(line)

    if not candidates:
        return None

    return max(candidates, key=lambda value: (name_score(value), len(value)))


def is_likely_card_name(value: str) -> bool:
    lowered = value.lower()

    if len(value) < 2:
        return False
    if not re.search(r"[A-Za-z]", value):
        return False
    if lowered in {"basic", "stage 1", "stage 2", "trainer", "supporter"}:
        return False
    if lowered.startswith(("evolves from", "put this card", "weakness", "resistance")):
        return False

    return True


def name_score(value: str) -> int:
    score = 0

    if re.search(r"\b(ex|gx|v|vmax|vstar)\b", value, flags=re.IGNORECASE):
        score += 2
    if value[:1].isupper():
        score += 1
    if len(value.split()) <= 4:
        score += 1

    return score


def search_tcgdex_cards(card_name: str) -> list[dict]:
    query = urlencode({"name": card_name})
    data = fetch_json(f"{TCGDEX_API_BASE}?{query}")

    if not isinstance(data, list):
        return []

    return data


def fetch_tcgdex_card(card_id: str) -> dict:
    data = fetch_json(f"{TCGDEX_API_BASE}/{card_id}")

    if not isinstance(data, dict):
        raise CardIdentificationError("No matching card found")

    return data


def fetch_json(url: str):
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "pokemon-grader/1.0",
        },
    )

    try:
        with urlopen(request, timeout=8, context=ssl_context()) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise CardIdentificationError("No matching card found") from exc


def ssl_context():
    try:
        import certifi
    except Exception:
        return None

    return ssl.create_default_context(cafile=certifi.where())


def best_card_match(query: str, cards: list[dict]) -> dict | None:
    if not cards:
        return None

    normalized_query = normalize_name(query)

    def score(card: dict) -> float:
        name = normalize_name(card.get("name", ""))
        if not name:
            return 0
        if name == normalized_query:
            return 1
        if normalized_query in name or name in normalized_query:
            return 0.92
        return SequenceMatcher(None, normalized_query, name).ratio()

    best = max(cards, key=score)

    if score(best) < 0.35:
        return None

    return best


def normalize_name(value: str) -> str:
    normalized = value.lower()
    normalized = normalized.replace("’", "'")
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def card_response(card: dict) -> dict:
    price, currency = select_market_price(card.get("pricing", {}))
    card_set = card.get("set") or {}

    return {
        "id": card.get("id", ""),
        "name": card.get("name", ""),
        "set": card_set.get("name", "") if isinstance(card_set, dict) else "",
        "number": card.get("localId") or card.get("number") or "",
        "rarity": card.get("rarity", ""),
        "image": normalize_image_url(card.get("image", "")),
        "price": price if price is not None else "Pricing unavailable",
        "currency": currency if price is not None else "",
    }


def normalize_image_url(image_url: str) -> str:
    if not image_url:
        return ""

    if re.search(r"\.(png|jpg|jpeg|webp)$", image_url, flags=re.IGNORECASE):
        return image_url

    return f"{image_url}/high.webp"


def select_market_price(pricing: dict) -> tuple[float | None, str]:
    if not isinstance(pricing, dict):
        return None, ""

    tcgplayer_price = select_tcgplayer_price(pricing.get("tcgplayer", {}))
    if tcgplayer_price is not None:
        return tcgplayer_price, "USD"

    cardmarket_price = select_cardmarket_price(pricing.get("cardmarket", {}))
    if cardmarket_price is not None:
        return cardmarket_price, "EUR"

    return None, ""


def select_tcgplayer_price(tcgplayer: dict) -> float | None:
    if not isinstance(tcgplayer, dict):
        return None

    variant_keys = [
        "normal",
        "holofoil",
        "holo",
        "reverse-holofoil",
        "reverseHolofoil",
        "1st-edition",
        "1st-edition-holofoil",
        "unlimited",
        "unlimited-holofoil",
    ]
    price_keys = ["marketPrice", "midPrice", "lowPrice", "directLowPrice", "highPrice"]

    for variant_key in variant_keys:
        variant = tcgplayer.get(variant_key)

        if not isinstance(variant, dict):
            continue

        for price_key in price_keys:
            price = number_or_none(variant.get(price_key))
            if price is not None:
                return price

    return None


def select_cardmarket_price(cardmarket: dict) -> float | None:
    if not isinstance(cardmarket, dict):
        return None

    for price_key in [
        "trend",
        "avg",
        "avg30",
        "avg7",
        "low",
        "trend-holo",
        "avg-holo",
        "avg30-holo",
        "avg7-holo",
        "low-holo",
    ]:
        price = number_or_none(cardmarket.get(price_key))
        if price is not None:
            return price

    return None


def number_or_none(value) -> float | None:
    try:
        if value is None:
            return None
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None

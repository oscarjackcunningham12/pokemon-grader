import base64
import io
import json
import re
import ssl
import unicodedata
from difflib import SequenceMatcher
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from PIL import Image, ImageEnhance, ImageFilter, ImageOps


TCGDEX_API_BASE = "https://api.tcgdex.net/v2/en/cards"
NAME_OCR_CONFIG = (
    "--psm 7 "
    "-c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 .:'’&-♀♂"
)
BLOCK_OCR_CONFIG = "--psm 6"


class CardIdentificationError(Exception):
    """Raised when a card cannot be identified from the uploaded image."""


class CardIdentificationDebugError(CardIdentificationError):
    def __init__(self, message: str, debug: dict):
        super().__init__(message)
        self.debug = debug


def identify_card(image: Image.Image, ocr_regions: dict | None = None) -> dict:
    ocr_hints = extract_card_hints(image, ocr_regions=ocr_regions)
    card_name = ocr_hints.get("name")

    if not card_name:
        raise CardIdentificationDebugError("Could not read card name", debug_payload(ocr_hints))

    search_results = search_tcgdex_cards(card_name, ocr_hints)
    match = best_card_match(card_name, search_results, ocr_hints)

    if not match:
        raise CardIdentificationDebugError(
            "No matching card found",
            debug_payload(ocr_hints, search_result_count=len(search_results)),
        )

    card_details = fetch_tcgdex_card(match["id"])
    return card_response(card_details)


def extract_card_hints(image: Image.Image, ocr_regions: dict | None = None) -> dict:
    try:
        import pytesseract
    except Exception as exc:
        raise CardIdentificationError("Could not read card name") from exc

    try:
        name_reads = read_name_candidates(pytesseract, image, ocr_regions=ocr_regions)

        bottom_text = read_bottom_text(pytesseract, image, ocr_regions=ocr_regions)
        illustrator_text = read_illustrator_text(pytesseract, image, ocr_regions=ocr_regions)
    except Exception as exc:
        raise CardIdentificationError("Could not read card name") from exc

    best_name_read = best_name_candidate(name_reads)

    return {
        "name": best_name_read["name"] if best_name_read else None,
        "number": extract_card_number(bottom_text),
        "illustrator": extract_illustrator_name(illustrator_text),
        "is_promo": extract_promo_hint(bottom_text),
        "name_reads": name_reads,
        "crop_images": debug_crop_images(image, ocr_regions=ocr_regions),
        "bottom_text": bottom_text,
        "illustrator_text": illustrator_text,
    }


def extract_card_name(image: Image.Image) -> str | None:
    return extract_card_hints(image).get("name")


def crop_card_name_region(image: Image.Image) -> Image.Image:
    return crop_card_name_regions(image)[0][1]


def crop_card_name_regions(
    image: Image.Image,
    ocr_regions: dict | None = None,
) -> list[tuple[str, Image.Image]]:
    return [
        (spec["name"], spec["image"])
        for spec in crop_card_name_region_specs(image, ocr_regions=ocr_regions)
    ]


def crop_card_name_region_specs(
    image: Image.Image,
    ocr_regions: dict | None = None,
) -> list[dict]:
    image = ImageOps.exif_transpose(image).convert("RGB")
    width, height = image.size
    manual_name_box = normalized_region_box(ocr_regions, "name", width, height)

    if manual_name_box:
        boxes = [("manual_name", manual_name_box)]
    else:
        boxes = [
            (
                "top_full",
                (
                    0,
                    0,
                    width,
                    max(1, int(height * 0.28)),
                ),
            ),
            (
                "name_band",
                (
                    int(width * 0.04),
                    int(height * 0.03),
                    int(width * 0.82),
                    max(1, int(height * 0.18)),
                ),
            ),
            (
                "wide_name_band",
                (
                    int(width * 0.02),
                    int(height * 0.02),
                    int(width * 0.95),
                    max(1, int(height * 0.22)),
                ),
            ),
        ]

    return [
        {
            "name": name,
            "box": {
                "x": box[0],
                "y": box[1],
                "width": box[2] - box[0],
                "height": box[3] - box[1],
            },
            "image": image.crop(box),
        }
        for name, box in boxes
    ]


def crop_card_info_region(
    image: Image.Image,
    ocr_regions: dict | None = None,
) -> Image.Image:
    image = ImageOps.exif_transpose(image).convert("RGB")
    width, height = image.size
    manual_number_box = normalized_region_box(ocr_regions, "number", width, height)

    if manual_number_box:
        return image.crop(manual_number_box)

    return image.crop((
        0,
        int(height * 0.72),
        width,
        height,
    ))


def crop_card_illustrator_region(
    image: Image.Image,
    ocr_regions: dict | None = None,
) -> Image.Image:
    image = ImageOps.exif_transpose(image).convert("RGB")
    width, height = image.size
    manual_illustrator_box = normalized_region_box(ocr_regions, "illustrator", width, height)

    if manual_illustrator_box:
        return image.crop(manual_illustrator_box)

    return image.crop((
        int(width * 0.04),
        int(height * 0.62),
        int(width * 0.72),
        int(height * 0.78),
    ))


def read_name_candidates(
    pytesseract,
    image: Image.Image,
    ocr_regions: dict | None = None,
) -> list[dict]:
    reads = []

    for crop_name, crop in crop_card_name_regions(image, ocr_regions=ocr_regions):
        for variant_name, prepared in preprocess_variants_for_ocr(crop):
            config = BLOCK_OCR_CONFIG if crop_name == "top_full" else NAME_OCR_CONFIG
            text = pytesseract.image_to_string(prepared, config=config)
            name = clean_card_name(text)

            reads.append({
                "crop": crop_name,
                "variant": variant_name,
                "text": text,
                "name": name,
                "score": ocr_name_score(name),
            })

    return reads


def read_bottom_text(
    pytesseract,
    image: Image.Image,
    ocr_regions: dict | None = None,
) -> str:
    texts = []
    number_crop = crop_card_info_region(image, ocr_regions=ocr_regions)

    for _variant_name, prepared in preprocess_variants_for_ocr(number_crop):
        text = pytesseract.image_to_string(prepared, config=BLOCK_OCR_CONFIG)

        if text.strip() and text not in texts:
            texts.append(text)

    return "\n".join(texts)


def read_illustrator_text(
    pytesseract,
    image: Image.Image,
    ocr_regions: dict | None = None,
) -> str:
    texts = []
    illustrator_crop = crop_card_illustrator_region(image, ocr_regions=ocr_regions)

    for _variant_name, prepared in preprocess_variants_for_ocr(illustrator_crop):
        text = pytesseract.image_to_string(prepared, config=BLOCK_OCR_CONFIG)

        if text.strip() and text not in texts:
            texts.append(text)

    return "\n".join(texts)


def preprocess_for_ocr(image: Image.Image) -> Image.Image:
    return preprocess_variants_for_ocr(image)[0][1]


def preprocess_variants_for_ocr(image: Image.Image) -> list[tuple[str, Image.Image]]:
    grayscale = ImageOps.grayscale(image)
    enlarged = grayscale.resize(
        (grayscale.width * 4, grayscale.height * 4),
        Image.Resampling.LANCZOS,
    )
    contrasted = ImageOps.autocontrast(enlarged)
    sharpened = ImageEnhance.Sharpness(contrasted).enhance(2.0)
    high_contrast = ImageEnhance.Contrast(sharpened).enhance(1.8)
    threshold = high_contrast.point(lambda pixel: 255 if pixel > 150 else 0)
    light_threshold = high_contrast.point(lambda pixel: 255 if pixel > 120 else 0)

    return [
        ("contrast", high_contrast),
        ("threshold", threshold),
        ("light_threshold", light_threshold),
    ]


def debug_crop_images(image: Image.Image, ocr_regions: dict | None = None) -> list[dict]:
    crops = [
        {
            "name": spec["name"],
            "box": spec["box"],
            "image": pil_image_to_data_url(spec["image"]),
        }
        for spec in crop_card_name_region_specs(image, ocr_regions=ocr_regions)
    ]

    number_spec = crop_card_info_region_spec(image, ocr_regions=ocr_regions)
    crops.append({
        "name": number_spec["name"],
        "box": number_spec["box"],
        "image": pil_image_to_data_url(number_spec["image"]),
    })

    illustrator_spec = crop_card_illustrator_region_spec(image, ocr_regions=ocr_regions)
    crops.append({
        "name": illustrator_spec["name"],
        "box": illustrator_spec["box"],
        "image": pil_image_to_data_url(illustrator_spec["image"]),
    })

    return crops


def crop_card_info_region_spec(
    image: Image.Image,
    ocr_regions: dict | None = None,
) -> dict:
    image = ImageOps.exif_transpose(image).convert("RGB")
    width, height = image.size
    manual_number_box = normalized_region_box(ocr_regions, "number", width, height)

    if manual_number_box:
        name = "manual_number"
        box = manual_number_box
    else:
        name = "bottom_info"
        box = (
            0,
            int(height * 0.72),
            width,
            height,
        )

    return {
        "name": name,
        "box": {
            "x": box[0],
            "y": box[1],
            "width": box[2] - box[0],
            "height": box[3] - box[1],
        },
        "image": image.crop(box),
    }


def crop_card_illustrator_region_spec(
    image: Image.Image,
    ocr_regions: dict | None = None,
) -> dict:
    image = ImageOps.exif_transpose(image).convert("RGB")
    width, height = image.size
    manual_illustrator_box = normalized_region_box(ocr_regions, "illustrator", width, height)

    if manual_illustrator_box:
        name = "manual_illustrator"
        box = manual_illustrator_box
    else:
        name = "illustrator"
        box = (
            int(width * 0.04),
            int(height * 0.62),
            int(width * 0.72),
            int(height * 0.78),
        )

    return {
        "name": name,
        "box": {
            "x": box[0],
            "y": box[1],
            "width": box[2] - box[0],
            "height": box[3] - box[1],
        },
        "image": image.crop(box),
    }


def pil_image_to_data_url(image: Image.Image) -> str:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def normalized_region_box(
    ocr_regions: dict | None,
    key: str,
    image_width: int,
    image_height: int,
) -> tuple[int, int, int, int] | None:
    if not isinstance(ocr_regions, dict):
        return None

    region = ocr_regions.get(key)
    if not isinstance(region, dict):
        return None

    try:
        x = int(round(float(region["x"])))
        y = int(round(float(region["y"])))
        width = int(round(float(region["width"])))
        height = int(round(float(region["height"])))
    except (KeyError, TypeError, ValueError):
        return None

    if width < 4 or height < 4:
        return None

    left = clamp(x, 0, image_width - 1)
    top = clamp(y, 0, image_height - 1)
    right = clamp(x + width, left + 1, image_width)
    bottom = clamp(y + height, top + 1, image_height)

    return left, top, right, bottom


def clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))


def best_name_candidate(reads: list[dict]) -> dict | None:
    candidates = [read for read in reads if read.get("name")]

    if not candidates:
        return None

    return max(candidates, key=lambda read: (read.get("score", 0), len(read["name"])))


def ocr_name_score(name: str | None) -> int:
    if not name:
        return 0

    words = name.split()
    score = name_score(name) * 10
    score += min(len(name), 24)

    if 1 <= len(words) <= 4:
        score += 8
    if any(char.isdigit() for char in name):
        score -= 3
    if len(words) > 5:
        score -= 10

    return score


def clean_card_name(text: str) -> str | None:
    candidates = []

    for raw_line in text.splitlines():
        line = normalize_ocr_text(raw_line).strip()
        if not line:
            continue

        line = re.sub(r"\bHP\s*\d+\b.*", "", line, flags=re.IGNORECASE)
        line = re.sub(r"\b\d+\s*HP\b.*", "", line, flags=re.IGNORECASE)
        line = re.sub(r"^(basic|stage\s*[12]|trainer|supporter|item)\s+", "", line, flags=re.IGNORECASE)
        line = "".join(
            char if char.isalnum() or char in " .:'’&-♀♂" else " "
            for char in line
        )
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
    if not any(char.isalpha() for char in value):
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


def search_tcgdex_cards(card_name: str, hints: dict | None = None) -> list[dict]:
    results = []

    for query_params in search_queries(card_name, hints or {}):
        data = fetch_json(f"{TCGDEX_API_BASE}?{urlencode(query_params)}")

        if isinstance(data, list):
            results.extend(data)

    return dedupe_cards(results)


def search_queries(card_name: str, hints: dict) -> list[dict]:
    queries = [{"name": card_name}]
    hinted_number = normalize_card_number(hints.get("number"))

    if hinted_number:
        queries.append({"localId": hinted_number})

    return queries


def dedupe_cards(cards: list[dict]) -> list[dict]:
    deduped = []
    seen_ids = set()

    for card in cards:
        card_id = card.get("id")

        if not card_id or card_id in seen_ids:
            continue

        deduped.append(card)
        seen_ids.add(card_id)

    return deduped


def debug_payload(ocr_hints: dict, search_result_count: int | None = None) -> dict:
    payload = {
        "read_name": ocr_hints.get("name"),
        "read_number": ocr_hints.get("number"),
        "read_illustrator": ocr_hints.get("illustrator"),
        "is_promo": ocr_hints.get("is_promo"),
        "name_reads": [
            {
                "crop": read.get("crop"),
                "variant": read.get("variant"),
                "name": read.get("name"),
                "score": read.get("score"),
                "text": compact_ocr_text(read.get("text", "")),
            }
            for read in ocr_hints.get("name_reads", [])
        ],
        "crop_images": ocr_hints.get("crop_images", []),
        "bottom_text": compact_ocr_text(ocr_hints.get("bottom_text", "")),
        "illustrator_text": compact_ocr_text(ocr_hints.get("illustrator_text", "")),
    }

    if search_result_count is not None:
        payload["search_result_count"] = search_result_count

    return payload


def compact_ocr_text(value: str) -> str:
    return re.sub(r"\s+", " ", normalize_ocr_text(value)).strip()


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


def extract_card_number(text: str) -> str | None:
    normalized = normalize_ocr_text(text).replace("／", "/")

    patterns = [
        r"\b(\d{1,3}[a-zA-Z]?)\s*/\s*\d{1,3}\b",
        r"\bNo\.?\s*(\d{1,3}[a-zA-Z]?)\b",
        r"\b(SVP|SWSH|SM|XY|BW|DP)\s*-?\s*(\d{1,3})\b",
        r"\b(TG|GG|RC|SVP|SWSH|SM|XY|BW|DP)\s*-?\s*(\d{1,3})\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, normalized, flags=re.IGNORECASE)
        if match:
            return "".join(group for group in match.groups() if group).upper()

    corrected_number = extract_misread_fraction_number(normalized)
    if corrected_number:
        return corrected_number

    return None


def extract_misread_fraction_number(text: str) -> str | None:
    """
    Handles OCR failures where collector numbers like 14/100 are read as BA100.
    """

    for token in re.findall(r"\b[A-Z0-9]{4,7}\b", text.upper()):
        corrected = token.translate(str.maketrans({
            "B": "1",
            "I": "1",
            "L": "1",
            "A": "4",
            "O": "0",
            "S": "5",
            "Z": "2",
        }))

        match = re.fullmatch(r"(\d{1,3})(\d{3})", corrected)
        if not match:
            continue

        numerator, denominator = match.groups()

        if 50 <= int(denominator) <= 250:
            return str(int(numerator))

    return None


def extract_promo_hint(text: str) -> bool:
    return bool(re.search(r"\bpromo\b|black\s+star|SVP|SWSH", text, flags=re.IGNORECASE))


def extract_illustrator_name(text: str) -> str | None:
    candidates = []

    for raw_line in normalize_ocr_text(text).splitlines():
        line = raw_line.strip()
        if not line:
            continue

        line = re.sub(r"^(illustrated\s+by|illus\.?)\s*", "", line, flags=re.IGNORECASE)
        line = "".join(
            char if char.isalpha() or char in " .'-" else " "
            for char in line
        )
        line = re.sub(r"\s+", " ", line).strip(" .'-")

        if len(line) < 3 or not any(char.isalpha() for char in line):
            continue

        candidates.append(line)

    if not candidates:
        return None

    return max(candidates, key=len)


def best_card_match(query: str, cards: list[dict], hints: dict | None = None) -> dict | None:
    if not cards:
        return None

    normalized_query = normalize_name(query)
    hints = hints or {}
    hinted_number = normalize_card_number(hints.get("number"))
    hinted_promo = bool(hints.get("is_promo"))
    hinted_illustrator = normalize_name(hints.get("illustrator", ""))

    def name_match_score(card: dict) -> float:
        name = normalize_name(card.get("name", ""))
        if not name:
            return 0
        if name == normalized_query:
            return 1
        elif normalized_query in name or name in normalized_query:
            return 0.92

        return SequenceMatcher(None, normalized_query, name).ratio()

    def score(card: dict) -> tuple[float, float, float, float]:
        name_score_value = name_match_score(card)
        number_score = 0
        promo_score = 0
        illustrator_score = illustrator_match_score(card, hinted_illustrator)

        if hinted_number and card_matches_number(card, hinted_number):
            number_score = 1

        if hinted_promo and card_looks_like_promo(card):
            promo_score = 1

        if hinted_number:
            return (number_score, name_score_value, illustrator_score, promo_score)

        return (name_score_value, illustrator_score, promo_score, number_score)

    best = max(cards, key=score)

    if score(best)[0] < 0.35:
        return None

    return best


def illustrator_match_score(card: dict, hinted_illustrator: str) -> float:
    if not hinted_illustrator:
        return 0

    best_score = 0

    for illustrator in card_illustrators(card):
        normalized_illustrator = normalize_name(illustrator)
        if not normalized_illustrator:
            continue

        if normalized_illustrator == hinted_illustrator:
            return 1

        if hinted_illustrator in normalized_illustrator or normalized_illustrator in hinted_illustrator:
            best_score = max(best_score, 0.92)
        else:
            best_score = max(
                best_score,
                SequenceMatcher(None, hinted_illustrator, normalized_illustrator).ratio(),
            )

    return best_score


def card_illustrators(card: dict) -> list[str]:
    values = []

    for key in ("illustrator", "illustratorName"):
        value = card.get(key)
        if isinstance(value, str):
            values.append(value)

    illustrators = card.get("illustrators")
    if isinstance(illustrators, list):
        values.extend(str(value) for value in illustrators)

    return values


def card_matches_number(card: dict, hinted_number: str) -> bool:
    return any(
        normalize_card_number(value) == hinted_number
        for value in [
            card.get("localId"),
            card.get("number"),
            card.get("id", "").split("-")[-1],
        ]
    )


def normalize_card_number(value) -> str:
    if value is None:
        return ""

    normalized = str(value).upper()
    normalized = re.sub(r"[^A-Z0-9]", "", normalized)
    return normalized


def card_looks_like_promo(card: dict) -> bool:
    values = [
        card.get("id", ""),
        card.get("localId", ""),
        card.get("number", ""),
        card.get("rarity", ""),
    ]

    card_set = card.get("set")
    if isinstance(card_set, dict):
        values.extend([
            card_set.get("id", ""),
            card_set.get("name", ""),
        ])

    haystack = " ".join(str(value) for value in values)
    return bool(re.search(r"promo|black\s+star|SVP|SWSH", haystack, flags=re.IGNORECASE))


def normalize_name(value: str) -> str:
    normalized = normalize_ocr_text(value).lower()
    normalized = remove_diacritics(normalized)
    normalized = normalized.replace("♀", " female ")
    normalized = normalized.replace("♂", " male ")
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def normalize_ocr_text(value: str) -> str:
    return (
        str(value)
        .replace("â€™", "’")
        .replace("â€˜", "‘")
        .replace("ï¼", "／")
        .replace("Â©", "©")
    )


def remove_diacritics(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def card_response(card: dict) -> dict:
    price, currency = select_market_price(card.get("pricing", {}))
    card_set = card.get("set") or {}

    return {
        "id": card.get("id", ""),
        "name": card.get("name", ""),
        "set": card_set.get("name", "") if isinstance(card_set, dict) else "",
        "number": card.get("localId") or card.get("number") or "",
        "rarity": card.get("rarity", ""),
        "illustrator": ", ".join(card_illustrators(card)),
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

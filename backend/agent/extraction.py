from __future__ import annotations

import re
from pathlib import Path


def extract_information_from_message(text: str) -> dict:
    prices = re.findall(r"(?:₹|Rs\.?|INR)\s*([0-9][0-9,]*(?:\.[0-9]+)?)", text, flags=re.I)
    amounts = [float(p.replace(",", "")) for p in prices]
    amount = amounts[0] if amounts else 0.0

    keywords = {
        "rent": "RENT",
        "uber": "TRANSPORT",
        "swiggy": "FOOD",
        "zomato": "FOOD",
        "netflix": "SUBSCRIPTIONS",
        "book": "EDUCATION",
        "medicine": "HEALTH",
        "flight": "TRAVEL",
    }
    category = "OTHER"
    lower = text.lower()
    for k, v in keywords.items():
        if k in lower:
            category = v
            break

    necessity = "essential" if any(t in lower for t in ["rent", "medicine", "fees", "bill"]) else "optional"
    return {
        "name": text.strip()[:120] or "Unknown item",
        "amount": amount,
        "category": category,
        "necessity": necessity,
    }


def extract_information_from_image(media_path: str) -> dict:
    path = Path(media_path)
    if not path.exists():
        return {"text": "", "signals": []}
    try:
        import pytesseract
        from PIL import Image
        text = pytesseract.image_to_string(Image.open(path))
        return {"text": text, "signals": ["ocr"]}
    except Exception:
        return {"text": "", "signals": ["ocr_unavailable"]}

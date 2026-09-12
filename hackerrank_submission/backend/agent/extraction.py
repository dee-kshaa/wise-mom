from __future__ import annotations

import os
import re
from pathlib import Path


def extract_information_from_message(text: str) -> dict:
    if not isinstance(text, str):
        text = ""
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


def _resolve_safe_media_path(media_path: str) -> Path | None:
    root = Path(os.getenv("WISE_MOM_MEDIA_ROOT", os.getcwd())).resolve()
    media_dir = (root / "data").resolve()
    raw_name = (media_path or "").strip()
    if not raw_name:
        return None
    if not re.fullmatch(r"[A-Za-z0-9._-]+", raw_name):
        return None
    allowed = {
        p.name: p.resolve()
        for p in media_dir.iterdir()
        if p.is_file() and re.fullmatch(r"[A-Za-z0-9._-]+", p.name)
    } if media_dir.exists() else {}
    return allowed.get(raw_name)


def extract_information_from_image(media_path: str) -> dict:
    path = _resolve_safe_media_path(media_path)
    if path is None:
        return {"text": "", "signals": []}
    try:
        import pytesseract
        from PIL import Image
        text = pytesseract.image_to_string(Image.open(path))
        return {"text": text, "signals": ["ocr"]}
    except Exception:
        return {"text": "", "signals": ["ocr_unavailable"]}

import unicodedata
from typing import Any


MOJIBAKE_REPARATUREN = {
    "Ã¤": "ä",
    "Ã¶": "ö",
    "Ã¼": "ü",
    "Ã„": "Ä",
    "Ã–": "Ö",
    "Ãœ": "Ü",
    "ÃŸ": "ß",
    "â€ž": "„",
    "â€œ": "“",
    "â€": "”",
    "â€“": "–",
    "â€”": "—",
    "â€¢": "•",
    "â‚¬": "€",
    "Â ": " ",
}


def normalize_unicode_text(text: str) -> str:
    """Repariert nur bekannte Mojibake-Muster und erhält korrekten Unicode."""
    for fehlerhaft, korrekt in MOJIBAKE_REPARATUREN.items():
        if fehlerhaft in text:
            text = text.replace(fehlerhaft, korrekt)
    text = "".join(
        zeichen
        for zeichen in text
        if zeichen in "\n\r\t" or unicodedata.category(zeichen) not in {"Cc", "Cf", "Cs"}
    )
    return unicodedata.normalize("NFC", text)


def normalize_api_data(daten: Any) -> Any:
    if isinstance(daten, str):
        return normalize_unicode_text(daten)
    if isinstance(daten, dict):
        return {schluessel: normalize_api_data(wert) for schluessel, wert in daten.items()}
    if isinstance(daten, (list, tuple)):
        return [normalize_api_data(wert) for wert in daten]
    return daten

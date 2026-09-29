import html
import re
from typing import Any


def sanitize_text(value: str | None) -> str | None:
    """
    Sanitize and escape user text inputs to prevent XSS, HTML injection,
    and template injection when rendered in UI or generated documents (letters/LPJ).
    """
    if value is None:
        return None

    # Strip null bytes and non-printable control chars except standard whitespace
    cleaned = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", str(value))

    # Strip excess whitespace
    cleaned = cleaned.strip()

    # Escape HTML special characters
    return html.escape(cleaned, quote=True)


def sanitize_dict_fields(data: dict[str, Any], fields_to_sanitize: list[str] | None = None) -> dict[str, Any]:
    """
    Sanitize specified string fields in a dictionary (or all string fields if none specified).
    """
    sanitized = data.copy()
    for key, val in sanitized.items():
        if isinstance(val, str) and (fields_to_sanitize is None or key in fields_to_sanitize):
            sanitized[key] = sanitize_text(val)
    return sanitized


_SCHEME_RE = re.compile(r"^\s*([a-zA-Z][a-zA-Z0-9+.-]*):")


def is_safe_link(url: str | None) -> bool:
    """
    True for links that are safe to put in an <a href>: empty, http(s)://..., or scheme-less
    (the UI prefixes https://). Rejects javascript:, data:, vbscript: and any other scheme.
    """
    if not url:
        return True
    match = _SCHEME_RE.match(url)
    return match is None or match.group(1).lower() in ("http", "https")


def validate_safe_link(url: str | None) -> str | None:
    """Pydantic validator wrapper around is_safe_link."""
    if not is_safe_link(url):
        raise ValueError("Tautan harus berupa URL http:// atau https://.")
    return url

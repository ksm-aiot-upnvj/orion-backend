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
        if isinstance(val, str):
            if fields_to_sanitize is None or key in fields_to_sanitize:
                sanitized[key] = sanitize_text(val)
    return sanitized

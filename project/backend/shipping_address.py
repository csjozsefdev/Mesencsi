"""Structured shipping address validation, normalization, and safe display."""

from __future__ import annotations

import html
import json
import re
from typing import Any

SHIPPING_ADDRESS_JSON_V = 2

_UNSAFE_MARKUP_RE = re.compile(
    r"[<>]|javascript\s*:|data\s*:|vbscript\s*:|on\w+\s*=",
    re.IGNORECASE,
)
_HU_ZIP_RE = re.compile(r"^\d{4}$")
_HU_PHONE_DIGITS_RE = re.compile(r"\D")
_NAME_RE = re.compile(
    r"^[\w .'\-"
    r"\u00c0-\u024f"
    r"]{2,128}$",
    re.UNICODE,
)
_CITY_RE = re.compile(
    r"^[\w .'\-"
    r"\u00c0-\u024f"
    r"]{2,128}$",
    re.UNICODE,
)
_STREET_RE = re.compile(
    r"^[\w .'\-"
    r"\u00c0-\u024f"
    r"0-9]{2,256}$",
    re.UNICODE,
)
_HOUSE_RE = re.compile(
    r"^[\w .'\-/"
    r"\u00c0-\u024f"
    r"0-9]{1,32}$",
    re.UNICODE,
)
_LINE2_RE = re.compile(
    r"^[\w .'\-"
    r"\u00c0-\u024f"
    r"0-9]{0,256}$",
    re.UNICODE,
)
_COUNTRY_RE = re.compile(
    r"^[\w .'\-"
    r"\u00c0-\u024f"
    r"]{2,128}$",
    re.UNICODE,
)
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class ShippingAddressValidationError(ValueError):
    """Validation failed with a Hungarian user-facing message."""

    def __init__(self, message: str, field: str | None = None) -> None:
        super().__init__(message)
        self.field = field


def contains_unsafe_markup(value: str) -> bool:
    return bool(_UNSAFE_MARKUP_RE.search(value))


def _clean_text(value: object, *, field: str, label: str, min_len: int, max_len: int) -> str:
    s = "" if value is None else str(value).strip()
    if not s and min_len > 0:
        raise ShippingAddressValidationError(f"A(z) {label} megadása kötelező.", field)
    if len(s) < min_len:
        raise ShippingAddressValidationError(
            f"A(z) {label} túl rövid (legalább {min_len} karakter).",
            field,
        )
    if len(s) > max_len:
        raise ShippingAddressValidationError(
            f"A(z) {label} legfeljebb {max_len} karakter lehet.",
            field,
        )
    if contains_unsafe_markup(s):
        raise ShippingAddressValidationError(
            f"A(z) {label} nem tartalmazhat HTML-t vagy szkriptet.",
            field,
        )
    return s


def validate_person_name(value: object, *, field: str, label: str) -> str:
    s = _clean_text(value, field=field, label=label, min_len=2, max_len=128)
    if not _NAME_RE.match(s):
        raise ShippingAddressValidationError(
            f"A(z) {label} csak betűket, szóközt és tipikus elválasztókat tartalmazhat.",
            field,
        )
    return s


def validate_hu_postal_code(value: object) -> str:
    s = _clean_text(value, field="postal_code", label="irányítószám", min_len=4, max_len=4)
    if not _HU_ZIP_RE.match(s):
        raise ShippingAddressValidationError(
            "Az irányítószám pontosan 4 számjegy legyen (magyar formátum).",
            "postal_code",
        )
    return s


def validate_hu_phone(value: object) -> str:
    s = _clean_text(value, field="phone", label="telefonszám", min_len=8, max_len=32)
    if contains_unsafe_markup(s):
        raise ShippingAddressValidationError(
            "A telefonszám nem tartalmazhat HTML-t vagy szkriptet.",
            "phone",
        )
    digits = _HU_PHONE_DIGITS_RE.sub("", s)
    if digits.startswith("36") and len(digits) >= 10:
        digits = digits[2:]
    if digits.startswith("06"):
        digits = digits[2:]
    if len(digits) < 8 or len(digits) > 9:
        raise ShippingAddressValidationError(
            "Érvénytelen magyar telefonszám (8–9 számjegy, pl. 06 30 123 4567).",
            "phone",
        )
    if digits[0] not in "123456789":
        raise ShippingAddressValidationError(
            "Érvénytelen magyar telefonszám.",
            "phone",
        )
    return s


def validate_email_format(value: object) -> str:
    s = _clean_text(value, field="email", label="e-mail", min_len=5, max_len=320)
    if not _EMAIL_RE.match(s):
        raise ShippingAddressValidationError("Érvénytelen e-mail cím formátum.", "email")
    return s.lower()


def validate_city(value: object) -> str:
    s = _clean_text(value, field="city", label="város", min_len=2, max_len=128)
    if not _CITY_RE.match(s):
        raise ShippingAddressValidationError(
            "A város mező formátuma érvénytelen.",
            "city",
        )
    return s


def validate_street(value: object) -> str:
    s = _clean_text(value, field="street", label="utca", min_len=2, max_len=256)
    if not _STREET_RE.match(s):
        raise ShippingAddressValidationError(
            "Az utca mező formátuma érvénytelen.",
            "street",
        )
    return s


def validate_house_number(value: object) -> str:
    s = _clean_text(value, field="house_number", label="házszám", min_len=1, max_len=32)
    if not _HOUSE_RE.match(s):
        raise ShippingAddressValidationError(
            "A házszám mező formátuma érvénytelen.",
            "house_number",
        )
    return s


def validate_optional_line2(value: object) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    if len(s) > 256:
        raise ShippingAddressValidationError(
            "Az emelet/ajtó mező legfeljebb 256 karakter lehet.",
            "line2",
        )
    if contains_unsafe_markup(s) or not _LINE2_RE.match(s):
        raise ShippingAddressValidationError(
            "Az emelet/ajtó mező formátuma érvénytelen.",
            "line2",
        )
    return s


def validate_country(value: object) -> str:
    s = _clean_text(value, field="country", label="ország", min_len=2, max_len=128)
    if not _COUNTRY_RE.match(s):
        raise ShippingAddressValidationError(
            "Az ország mező formátuma érvénytelen.",
            "country",
        )
    return s


def validate_street_address_line(value: object) -> str:
    """Combined utca + házszám (checkout)."""
    s = _clean_text(value, field="street", label="utca, házszám", min_len=2, max_len=256)
    if not _STREET_RE.match(s):
        raise ShippingAddressValidationError(
            "Az utca, házszám mező formátuma érvénytelen.",
            "street",
        )
    return s


def _combine_street_and_house(street: object, house_number: object) -> str:
    s = "" if street is None else str(street).strip()
    h = "" if house_number is None else str(house_number).strip()
    if s and h:
        return f"{s} {h}"
    return s or h


def validate_optional_recipient_name(value: object) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    return validate_person_name(value, field="recipient_name", label="átvevő neve")


def validate_checkout_shipping_address_parts(
    parts: dict[str, Any],
    *,
    customer_name: str,
) -> dict[str, str | None]:
    """Checkout GLS address — recipient optional, phone omitted, country defaults to Hungary."""
    optional_recipient = validate_optional_recipient_name(parts.get("recipient_name"))
    effective_recipient = optional_recipient or validate_person_name(
        customer_name,
        field="customer_name",
        label="név",
    )
    street_raw = parts.get("street_line")
    if street_raw is None or not str(street_raw).strip():
        street_raw = _combine_street_and_house(parts.get("street"), parts.get("house_number"))
    street_line = validate_street_address_line(street_raw)
    normalized: dict[str, str | None] = {
        "recipient_name": effective_recipient,
        "phone": None,
        "postal_code": validate_hu_postal_code(parts.get("postal_code")),
        "city": validate_city(parts.get("city")),
        "street": street_line,
        "house_number": "",
        "line2": validate_optional_line2(parts.get("line2")),
        "country": validate_country(parts.get("country") or "Magyarország"),
    }
    return normalized


def zip_city_mismatch_warning(postal_code: str, city: str) -> str | None:
    """Optional soft warning — does not block checkout."""
    z = postal_code.strip()
    c = city.strip().lower()
    if not z or not c:
        return None
    try:
        znum = int(z)
    except ValueError:
        return None
    if 1000 <= znum <= 1999 and "budapest" not in c:
        return "Az irányítószám Budapesthez tartozhat — ellenőrizd a várost."
    if 4000 <= znum <= 4999 and "debrecen" not in c:
        return "Az irányítószám Debrecenhez tartozhat — ellenőrizd a várost."
    if 6000 <= znum <= 6999 and "szeged" not in c:
        return "Az irányítószám Szegedhez tartozhat — ellenőrizd a várost."
    return None


def empty_address_parts() -> dict[str, str]:
    return {
        "recipient_name": "",
        "phone": "",
        "postal_code": "",
        "city": "",
        "street": "",
        "house_number": "",
        "line2": "",
        "country": "Magyarország",
    }


def parse_address_parts(raw: str | None) -> tuple[str, dict[str, str]]:
    """
    Returns (mode, parts) where mode is empty | json | legacy.
  legacy: free-text in street only — not accepted for new validation.
    """
    if raw is None:
        return "empty", empty_address_parts()
    s = str(raw).strip()
    if not s:
        return "empty", empty_address_parts()
    if s.startswith("{"):
        try:
            o = json.loads(s)
        except json.JSONDecodeError:
            return "legacy", {**empty_address_parts(), "street": s}
        if not isinstance(o, dict):
            return "legacy", {**empty_address_parts(), "street": s}
        parts = empty_address_parts()
        for key in parts:
            if key in o and o[key] is not None:
                parts[key] = str(o[key]).strip()
        if o.get("line2") is None:
            parts["line2"] = ""
        return "json", parts
    return "legacy", {**empty_address_parts(), "street": s}


def validate_address_parts(
    parts: dict[str, Any],
    *,
    require_all: bool = True,
) -> dict[str, str | None]:
    """Validate and return normalized parts."""
    if not require_all:
        any_filled = any(
            str(parts.get(k) or "").strip()
            for k in (
                "recipient_name",
                "phone",
                "postal_code",
                "city",
                "street",
                "house_number",
                "line2",
                "country",
            )
        )
        if not any_filled:
            return {**empty_address_parts(), "line2": None}

    normalized: dict[str, str | None] = {
        "recipient_name": validate_person_name(
            parts.get("recipient_name"), field="recipient_name", label="átvevő neve"
        ),
        "phone": validate_hu_phone(parts.get("phone")),
        "postal_code": validate_hu_postal_code(parts.get("postal_code")),
        "city": validate_city(parts.get("city")),
        "street": validate_street(parts.get("street")),
        "house_number": validate_house_number(parts.get("house_number")),
        "line2": validate_optional_line2(parts.get("line2")),
        "country": validate_country(parts.get("country") or "Magyarország"),
    }
    return normalized


def serialize_address_parts(parts: dict[str, str | None]) -> str:
    payload = {
        "v": SHIPPING_ADDRESS_JSON_V,
        "recipient_name": parts["recipient_name"],
        "phone": parts["phone"],
        "postal_code": parts["postal_code"],
        "city": parts["city"],
        "street": parts["street"],
        "house_number": parts["house_number"],
        "line2": parts.get("line2"),
        "country": parts["country"],
    }
    out = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    if len(out) > 2000:
        raise ShippingAddressValidationError(
            "A szállítási cím túl hosszú — rövidítsd a mezőket.",
            None,
        )
    return out


def parse_and_validate_shipping_address_raw(
    raw: str | None,
    *,
    required: bool = True,
    customer_name: str | None = None,
) -> str | None:
    mode, parts = parse_address_parts(raw)
    if mode == "empty":
        if required:
            raise ShippingAddressValidationError(
                "A szállítási cím megadása kötelező.",
                None,
            )
        return None
    if mode == "legacy":
        raise ShippingAddressValidationError(
            "A szállítási cím formátuma elavult. Töltsd ki újra a strukturált mezőket.",
            None,
        )
    if customer_name is not None:
        normalized = validate_checkout_shipping_address_parts(
            parts,
            customer_name=customer_name.strip(),
        )
    else:
        normalized = validate_address_parts(parts, require_all=True)
    return serialize_address_parts(normalized)


def validate_optional_profile_address_raw(raw: str | None) -> str | None:
    """Profile/billing: null allowed; partial legacy rejected; any field => full validation."""
    mode, parts = parse_address_parts(raw)
    if mode == "empty":
        return None
    if mode == "legacy":
        raise ShippingAddressValidationError(
            "A mentett cím formátuma elavult. Töltsd ki újra a strukturált mezőket.",
            None,
        )
    normalized = validate_address_parts(parts, require_all=True)
    return serialize_address_parts(normalized)


def format_shipping_address_plain(raw: str | None) -> str:
    mode, parts = parse_address_parts(raw)
    if mode == "empty":
        return ""
    if mode == "legacy":
        return parts.get("street") or ""
    street_line = _combine_street_and_house(parts.get("street"), parts.get("house_number"))
    lines = [
        parts.get("recipient_name") or "",
        " ".join(x for x in [parts.get("postal_code"), parts.get("city")] if x),
        street_line,
    ]
    if parts.get("line2"):
        lines.append(parts["line2"])
    if parts.get("country") and str(parts.get("country")).strip() != "Magyarország":
        lines.append(parts["country"])
    return "\n".join(x for x in lines if x)


def format_shipping_address_html(raw: str | None) -> str:
    text = format_shipping_address_plain(raw)
    if not text:
        return "—"
    return "<br/>".join(html.escape(line) for line in text.split("\n"))


def sample_checkout_shipping_json(*, customer_name: str = "Teszt Vásárló") -> str:
    """Test helper — simplified checkout GLS payload (no phone in address)."""
    return serialize_address_parts(
        validate_checkout_shipping_address_parts(
            {
                "postal_code": "1051",
                "city": "Budapest",
                "street_line": "Teszt utca 12",
                "line2": "2. em. 4",
            },
            customer_name=customer_name,
        )
    )


def sample_valid_shipping_json() -> str:
    """Test helper — canonical valid Hungarian shipping payload."""
    return serialize_address_parts(
        validate_address_parts(
            {
                "recipient_name": "Teszt Vásárló",
                "phone": "06301234567",
                "postal_code": "1051",
                "city": "Budapest",
                "street": "Teszt utca",
                "house_number": "12",
                "line2": "2. em. 4",
                "country": "Magyarország",
            }
        )
    )

"""Helpers shared across document parsers."""


def parse_amount(value):
    if value is None:
        return None
    cleaned = value.replace("$", "").replace(",", "").strip()
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def match_property_nickname(label, known_nicknames=("Brunswick", "Colburn")):
    lowered = (label or "").lower()
    for nickname in known_nicknames:
        if nickname.lower() in lowered:
            return nickname
    return None

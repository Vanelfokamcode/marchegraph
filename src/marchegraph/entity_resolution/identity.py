from __future__ import annotations

def normalize_identifier_type(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().upper()
    return normalized or None


def normalize_identifier_value(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def canonical_identity(
    identifier_type: str | None, identifier_value: str | None
) -> tuple[str, str] | None:
    normalized_type = normalize_identifier_type(identifier_type)
    normalized_value = normalize_identifier_value(identifier_value)
    if normalized_type is None or normalized_value is None:
        return None
    return normalized_type, normalized_value


def resolution_status(
    normalized_type: str | None, normalized_value: str | None
) -> str:
    if normalized_type is None and normalized_value is None:
        return "missing_both"
    if normalized_type is None:
        return "missing_type"
    if normalized_value is None:
        return "missing_identifier"
    return "resolved"

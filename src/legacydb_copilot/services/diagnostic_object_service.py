from __future__ import annotations

from collections.abc import Iterable

DIAGNOSTIC_OBJECT_MARKERS: tuple[str, ...] = (
    "exception",
    "error",
    "integration",
    "audit",
    "batch",
    "job",
    "log",
    "failure",
)


def is_diagnostic_object(object_name: str) -> bool:
    """Return whether an object name represents operational diagnostic evidence."""
    normalized = object_name.casefold()
    return any(marker in normalized for marker in DIAGNOSTIC_OBJECT_MARKERS)


def diagnostic_object_names(object_names: Iterable[str]) -> list[str]:
    """Keep diagnostic object names in input order without domain assumptions."""
    return [name for name in object_names if is_diagnostic_object(name)]


def contains_diagnostic_reference(values: Iterable[str]) -> bool:
    """Return whether evidence text references a diagnostic object category."""
    return any(is_diagnostic_object(value) for value in values)

"""Deterministic safe identifiers for user-derived metadata."""

from __future__ import annotations

import hashlib
import re
import unicodedata


def canonicalize_identifier_component(value: str) -> str:
    """Return a non-empty component containing only ``A-Z``, ``0-9`` and ``_``."""

    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", normalized).upper()
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    if normalized:
        return normalized
    return f"VALUE_{hashlib.sha256(value.encode('utf-8')).hexdigest()[:12].upper()}"


def build_insight_id(prefix: str, *components: str) -> str:
    """Build a readable, collision-safe insight ID without raw values."""

    safe_prefix = canonicalize_identifier_component(prefix)
    safe_components = [canonicalize_identifier_component(component) for component in components]
    digest_input = "\x1f".join(components).encode("utf-8")
    digest = hashlib.sha256(digest_input).hexdigest()[:10].upper()
    return "_".join([safe_prefix, *safe_components, digest])

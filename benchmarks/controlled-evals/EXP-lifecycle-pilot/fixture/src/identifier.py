"""Identifier normalization fixture with an intentional Unicode defect."""

from __future__ import annotations

import re


def slugify(value: str, fallback: str = "item") -> str:
    """Convert text to a lowercase ASCII identifier."""

    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or fallback

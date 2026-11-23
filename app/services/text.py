"""Cleaning of free text typed by users (nicknames): invisible characters are dropped, not stored."""
from __future__ import annotations

import unicodedata

from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE

# Cc: C0/C1 controls, Cf: format characters (zero-width space, LRM/RLM, word joiner, BOM), Cs: lone surrogates.
_INVISIBLE_CATEGORIES = {"Cc", "Cf", "Cs"}


def strip_invisible(text: str) -> str:
    """Remove control and format characters, so a "blank" name cannot hide behind U+200B and no cell is illegal."""
    kept = "".join(c for c in text if unicodedata.category(c) not in _INVISIBLE_CATEGORIES)
    return ILLEGAL_CHARACTERS_RE.sub("", kept)  # belt and braces: exactly what openpyxl refuses to write

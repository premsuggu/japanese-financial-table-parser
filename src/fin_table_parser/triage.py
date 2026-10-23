"""Page triage: is the text layer usable, and which extraction strategy applies?

Phase 1 only ships the banded-statement strategy. A page that fails triage raises
``UnsupportedPage`` with the reason; this is the hook where the OCR / Docling fallback attaches later.
"""

from __future__ import annotations

import re

from .models import PageGeometry

_USABLE = re.compile(r"[0-9０-９぀-ヿ㐀-鿿△▲－,，.．()（）%％年月日円]")
MIN_WORDS = 20
MIN_USABLE_RATIO = 0.9
MIN_BANDS = 8


class UnsupportedPage(Exception):
    """The page cannot be parsed by an available strategy (reason in the message)."""


def text_layer_health(geom: PageGeometry) -> tuple[int, float]:
    """Return (word count, share of characters that are digits / CJK / statement punctuation)."""
    chars = [c for w in geom.words for c in w.text if not c.isspace()]
    if not chars:
        return len(geom.words), 0.0
    good = sum(1 for c in chars if _USABLE.match(c) or c in "-–—")
    return len(geom.words), good / len(chars)


def count_bands(geom: PageGeometry) -> int:
    """Number of distinct horizontal row bands (alternating coloured fills)."""
    return len({(round(r.y0, 1), round(r.y1, 1)) for r in geom.fills})


def check_text_layer(geom: PageGeometry) -> None:
    """Raise ``UnsupportedPage`` unless the page has a healthy text layer."""
    n_words, ratio = text_layer_health(geom)
    if n_words < MIN_WORDS:
        raise UnsupportedPage(f"text layer too small ({n_words} words): scanned page? needs OCR")
    if ratio < MIN_USABLE_RATIO:
        raise UnsupportedPage(f"text layer looks garbled (usable-char ratio {ratio:.2f})")


def check_banded(geom: PageGeometry) -> None:
    """Raise ``UnsupportedPage`` unless the page has a healthy text layer and row bands."""
    check_text_layer(geom)
    if count_bands(geom) < MIN_BANDS:
        raise UnsupportedPage("no row bands found: not a banded statement (grid layout?)")

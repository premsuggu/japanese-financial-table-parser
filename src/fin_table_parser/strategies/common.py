"""Helpers shared by the extraction strategies."""

from __future__ import annotations

import re
from collections.abc import Sequence

from ..hierarchy import build_paths, cluster_levels
from ..labels import STATEMENT_KEYWORDS, classify_row
from ..models import Row, Word
from ..normalize import nfkc, strip_section_number


def join_words(words: Sequence[Word]) -> str:
    """Join words left to right; a space only between two ASCII alphanumerics."""
    out = ""
    for w in sorted(words, key=lambda w: w.x0):
        if (
            out
            and out[-1].isascii()
            and out[-1].isalnum()
            and w.text[0].isascii()
            and w.text[0].isalnum()
        ):
            out += " "
        out += w.text
    return out


def unit_and_statement(lines: Sequence[str]) -> tuple[str | None, str]:
    unit: str | None = None
    candidates: list[str] = []
    for line in lines:
        m = re.search(r"単位[:：]\s*([^）)]+)", nfkc(line))
        if m:
            unit = m.group(1).strip()
        else:
            candidates.append(line)
    # Only a line that names a statement counts; a continuation page has no title, and its
    # last line above the table is just the running page header.
    named = [c for c in candidates if any(k in nfkc(c) for k in STATEMENT_KEYWORDS)]
    statement = strip_section_number(named[-1]) if named else ""
    return unit, statement


def apply_hierarchy(rows: Sequence[Row], tol: float) -> None:
    """Set level, parent path and row type on every row, in place.

    Indent levels come from labelled rows only; a row without a label has no indent to read.
    """
    labelled = [r for r in rows if r.label]
    ranks = cluster_levels([r.label_x0 for r in labelled], tol=tol)
    rank = dict(zip((r.index for r in labelled), ranks, strict=True))
    levels = [rank.get(r.index, 0) for r in rows]
    paths = build_paths([r.label for r in rows], levels)
    for row, level, path in zip(rows, levels, paths, strict=True):
        row.level, row.path = level, path
        row.row_type = classify_row(row.label, any(v is not None for v in row.values))


def find_revision(title_lines: Sequence[str]) -> str | None:
    """The 訂正後 / 訂正前 marker if one of the title lines carries it."""
    return next(
        (t for t in ("訂正後", "訂正前") if any(t in nfkc(line) for line in title_lines)), None
    )

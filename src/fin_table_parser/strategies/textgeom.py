"""Band-free strategy: rows, columns and hierarchy from the words alone.

Input is a list of words with boxes, which is exactly what OCR produces, so the same code serves
born-digital PDFs without row bands and scanned pages. Drawings are optional hints (underlines).

Idea
----
* Rows: words whose vertical centres are close form one text line.
* Value columns: amounts are right-aligned, so the right edges of the numeric tokens pile up at a
  few x positions. Those clusters are the columns.
* Header: lines above the first amount that have words over the value columns.
* Hierarchy: the indent of the label (unchanged).

Every tolerance is a fraction of a length measured on the page itself (word height or row pitch).
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from dataclasses import dataclass, field

from ..labels import detect_kind
from ..models import PageGeometry, Row, Table, Value, Word
from ..normalize import parse_value, period_end
from .banded import _is_underlined
from .common import apply_hierarchy, find_revision, join_words, unit_and_statement

# Fractions of the median word height ("h").
SAME_LINE = 0.4  # centres closer than this are on one text line
COLUMN_TOL = 0.6  # right edges closer than this belong to one column
# Fractions of the row pitch (distance between consecutive amount lines).
INDENT_TOL = 0.17
GAP_LIMIT = 1.3  # fallback body scan stops when two lines are further apart than this
SAME_ROW_GAP = 0.75  # lines closer than this are one row (a label wrapped over two lines)
# Dimensionless.
MIN_COLUMN_SUPPORT = 0.2  # a column needs this share of the busiest column's amounts
MIN_TOKENS_FOR_COLUMN = 2
OVER_COLUMN = 0.6  # an amount's right edge lies within this share of a column width of its column
RULE_SPLIT_OF_PITCH = 0.125
SINGLE_COLUMN_WIDTH = 12.0  # in word heights: assumed width of a lone value column


class NoTableFound(ValueError):
    """The words do not contain a table of amounts (reason in the message)."""


@dataclass
class Line:
    words: list[Word] = field(default_factory=list)

    @property
    def cy(self) -> float:
        return statistics.median(w.cy for w in self.words)

    @property
    def x0(self) -> float:
        return min(w.x0 for w in self.words)


def text_lines(words: Sequence[Word], h: float) -> list[Line]:
    lines: list[Line] = []
    for w in sorted(words, key=lambda w: (w.cy, w.x0)):
        if lines and abs(lines[-1].cy - w.cy) <= SAME_LINE * h:
            lines[-1].words.append(w)
        else:
            lines.append(Line([w]))
    for line in lines:
        line.words.sort(key=lambda w: w.x0)
    return lines


SIGN_ONLY = "△▲"
MERGE_GAP = 1.0  # a sign this close (in word heights) to the digits after it belongs to them


def merge_sign_fragments(lines: Sequence[Line], h: float) -> None:
    """Rejoin a lone ``△`` with the amount that follows it (OCR engines often split them)."""
    for line in lines:
        merged: list[Word] = []
        for w in line.words:
            prev = merged[-1] if merged else None
            if (
                prev is not None
                and prev.text in tuple(SIGN_ONLY)
                and w.x0 - prev.x1 <= MERGE_GAP * h
                and _is_amount(Word(prev.text + w.text, prev.x0, prev.y0, w.x1, w.y1))
            ):
                merged[-1] = Word(
                    prev.text + w.text, prev.x0, min(prev.y0, w.y0), w.x1, max(prev.y1, w.y1)
                )
            else:
                merged.append(w)
        line.words = merged


def _is_amount(word: Word) -> Value | None:
    v = parse_value(word.text)
    return v if v is not None and v.kind in ("number", "nil") else None


def find_columns(amounts: Sequence[Word], h: float) -> list[float]:
    """Right-edge x of each value column, left to right."""
    edges = sorted(w.x1 for w in amounts if (v := _is_amount(w)) is not None and v.kind == "number")
    clusters: list[list[float]] = []
    for x in edges:
        if clusters and x - clusters[-1][-1] <= COLUMN_TOL * h:
            clusters[-1].append(x)
        else:
            clusters.append([x])
    biggest = max((len(c) for c in clusters), default=0)
    keep = [
        c
        for c in clusters
        if len(c) >= MIN_TOKENS_FOR_COLUMN and len(c) >= MIN_COLUMN_SUPPORT * biggest
    ]
    return [statistics.median(c) for c in keep]


def nearest(x: float, centres: Sequence[float]) -> int:
    return min(range(len(centres)), key=lambda i: abs(centres[i] - x))


def extract_text(geom: PageGeometry, source: str = "") -> Table:
    words = [w for w in geom.words if w.text.strip()]
    if len(words) < 8:
        raise NoTableFound("too few words")
    h = statistics.median(w.y1 - w.y0 for w in words)
    lines = text_lines(words, h)
    merge_sign_fragments(lines, h)
    words = [w for ln in lines for w in ln.words]

    # ---- columns and the lines that carry amounts
    columns = find_columns([w for w in words if _is_amount(w)], h)
    if not columns:
        raise NoTableFound("no right-aligned column of amounts")
    col_width = columns[1] - columns[0] if len(columns) > 1 else SINGLE_COLUMN_WIDTH * h
    zone_left = columns[0] - col_width  # left edge of the first value column

    def amount_tokens(line: Line) -> list[Word]:
        # An amount must sit over a value column; a page number or a stray figure elsewhere
        # is further from every column than half a column width.
        return [
            w
            for w in line.words
            if _is_amount(w)
            and abs(w.x1 - columns[nearest(w.x1, columns)]) <= OVER_COLUMN * col_width
        ]

    amount_lines = [i for i, ln in enumerate(lines) if amount_tokens(ln)]
    if len(amount_lines) < 3:
        raise NoTableFound("fewer than 3 lines of amounts")
    first, last = amount_lines[0], amount_lines[-1]
    cys = [lines[i].cy for i in amount_lines]
    pitch = statistics.median(b - a for a, b in zip(cys, cys[1:], strict=False))

    # ---- header block, title block and where the body starts
    def over_values(line: Line) -> list[Word]:
        return [w for w in line.words if not _is_amount(w) and w.cx > zone_left]

    def is_unit_line(line: Line) -> bool:
        return "単位" in "".join(w.text for w in line.words)

    # The column header is the contiguous block of lines with text over the value columns that sits
    # directly above the first amount. The running page header (company / document name, also over
    # the value columns) is cut off by the gap above the unit line, and the unit line itself.
    candidates = [i for i in range(first) if over_values(lines[i]) and not is_unit_line(lines[i])]
    header_idx: list[int] = []
    for i in reversed(candidates):
        if header_idx:
            above_block = lines[i].cy
            if lines[header_idx[0]].cy - above_block > GAP_LIMIT * pitch:
                break
            if any(is_unit_line(lines[k]) for k in range(i + 1, header_idx[0])):
                break
        header_idx.insert(0, i)
    if header_idx:
        body_start = header_idx[-1] + 1
        header_lines = [lines[i] for i in header_idx]
        title_end = header_idx[0]
    else:  # no header text: walk up from the first amount through evenly spaced label-only lines
        body_start = first
        while (
            body_start > 0
            and not is_unit_line(lines[body_start - 1])
            and lines[body_start].cy - lines[body_start - 1].cy <= GAP_LIMIT * pitch
        ):
            body_start -= 1
        header_lines = []
        title_end = body_start
    title_lines = [join_words(ln.words) for ln in lines[:title_end]]
    currency, statement = unit_and_statement(title_lines)

    # ---- header text per column (columns span (previous right edge, own right edge])
    bounds = [float("-inf"), *columns]
    headers = []
    for i in range(len(columns)):
        words_i = [
            w
            for ln in header_lines
            for w in over_values(ln)
            if (bounds[i] < w.cx <= columns[i]) or (i == len(columns) - 1 and w.cx > columns[i])
        ]
        by_line = [join_words(ln_words) for ln_words in _group(words_i, h)]
        headers.append(" ".join(by_line))

    # ---- rows
    thin_rules = [r for r in geom.rules if r.height < RULE_SPLIT_OF_PITCH * pitch]
    rows: list[Row] = []
    for block in _row_blocks(lines[body_start : last + 1], SAME_ROW_GAP * pitch):
        tokens = [w for ln in block for w in amount_tokens(ln)]
        token_ids = {id(w) for w in tokens}
        label_lines = [[w for w in ln.words if id(w) not in token_ids] for ln in block]
        label_lines = [ln_words for ln_words in label_lines if ln_words]
        cells: list[list[Word]] = [[] for _ in columns]
        for w in tokens:
            cells[nearest(w.x1, columns)].append(w)
        values = [
            parse_value("".join(w.text for w in sorted(c, key=lambda w: w.x0))) for c in cells
        ]
        rows.append(
            Row(
                index=len(rows),
                label="".join(join_words(ln_words) for ln_words in label_lines),
                level=0,
                path=(),
                values=values,
                row_type="item",
                underlined=[
                    _is_underlined(c, (columns[i] - col_width, columns[i]), thin_rules, pitch)
                    for i, c in enumerate(cells)
                ],
                # the indent is that of the first label line; a wrapped continuation may differ
                label_x0=min((w.x0 for w in label_lines[0]), default=zone_left)
                if label_lines
                else zone_left,
            )
        )
    apply_hierarchy(rows, tol=INDENT_TOL * pitch)

    return Table(
        statement=statement,
        unit=currency,
        headers=headers,
        periods=[period_end(x) for x in headers],
        rows=rows,
        source=source,
        page_no=geom.page_no,
        kind=detect_kind(statement, [r.label for r in rows]),
        meta={
            "lines_above": title_lines,
            "lines_below": [join_words(ln.words) for ln in lines[last + 1 :]],
            "revision": find_revision(title_lines),
            "strategy": "text",
            "n_columns": len(columns),
        },
    )


def _row_blocks(lines: Sequence[Line], max_gap: float) -> list[list[Line]]:
    """Group consecutive lines closer than ``max_gap`` into one row (a label wrapped over lines)."""
    blocks: list[list[Line]] = []
    for ln in lines:
        if blocks and ln.cy - blocks[-1][-1].cy < max_gap:
            blocks[-1].append(ln)
        else:
            blocks.append([ln])
    return blocks


def _group(words: Sequence[Word], h: float) -> list[list[Word]]:
    return [ln.words for ln in text_lines(words, h)]

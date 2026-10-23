"""Banded-statement strategy.

The page draws one 12 pt coloured band per table row, and each band is split into one rectangle
per column. So the geometry gives us the rows *and* the column boundaries directly; text
positions are only used to decide which band / column a word belongs to.

Pipeline: bands -> columns -> header -> rows -> rules/underlines -> hierarchy -> row types.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence

from ..labels import detect_kind
from ..models import PageGeometry, Rect, Row, Table, Value, Word
from ..normalize import parse_value, period_end
from .common import apply_hierarchy, find_revision, join_words, unit_and_statement

# Every length below is a FRACTION OF THE TYPICAL ROW HEIGHT of the page ("unit"), measured from
# the page's own bands. Nothing is in absolute points, so the parser does not depend on page size,
# zoom or font size. (Sizes quoted in comments are what this page happens to use: unit = 12 pt.)
LINE_TOL = 0.25  # words whose centres differ less than this are on the same text line (3 pt)
RULE_SPLIT = 0.125  # rules thinner than this are thin rules, thicker are heavy rules (1.5 pt)
RULE_Y_TOL = 0.025  # fragments of one rule share a y within this (0.3 pt)
RULE_GAP_TOL = 0.04  # fragments of one rule may be separated by up to this gap (0.5 pt)
EDGE_TOL = 0.1  # slack when testing "above / below / at the table edge" (1 pt)
RULE_ROW_TOL = 0.125  # a rule within this of a band's top edge is "above" that row (1.5 pt)
UNDERLINE_ABOVE = 0.08  # an underline may start this far above the text bottom (1 pt) ...
UNDERLINE_BELOW = 0.21  # ... or this far below it (2.5 pt)
INDENT_TOL = 0.17  # label x0 values closer than this share an indent level (2 pt)

# Ratios (dimensionless).
FULL_RULE_RATIO = 0.9  # a rule at least this wide as the column is a "full" rule
UNDERLINE_OVERLAP = 0.6  # an underline must cover this much of the number's width
TABLE_RULE_RATIO = 0.8  # the heavy top rule spans at least this share of the table width
MIN_BAND_RATIO = 0.5  # bands thinner than this fraction of the typical band are not rows
MAX_BAND_OVERLAP = 0.5  # a band overlapping the previous one by more than this is a duplicate

Interval = tuple[float, float]


# ---------------------------------------------------------------- geometry helpers


def merge_rules(rules: Iterable[Rect], unit: float) -> list[Rect]:
    """Merge collinear, touching rule fragments (cell borders are drawn in pieces)."""
    merged: list[Rect] = []
    for r in sorted(rules, key=lambda r: (r.y0, r.x0)):
        last = merged[-1] if merged else None
        if (
            last is not None
            and abs(last.y0 - r.y0) < RULE_Y_TOL * unit
            and abs(last.y1 - r.y1) < RULE_Y_TOL * unit
            and r.x0 <= last.x1 + RULE_GAP_TOL * unit
        ):
            merged[-1] = Rect(last.x0, last.y0, max(last.x1, r.x1), last.y1, last.fill)
        else:
            merged.append(r)
    return merged


def row_height(bands: Sequence[tuple[float, float]]) -> float:
    """The typical (median) row height: the page's own length unit."""
    heights = sorted(y1 - y0 for y0, y1 in bands)
    return heights[len(heights) // 2]


def find_bands(fills: Sequence[Rect]) -> list[tuple[float, float]]:
    """Distinct (y0, y1) row bands, top to bottom.

    The source also paints sub-pixel slivers behind the table rules. They hold no text, so bands
    much thinner than the typical band are dropped.
    """
    ys = sorted({(round(r.y0, 3), round(r.y1, 3)) for r in fills})
    if not ys:
        return []
    typical = row_height(ys)
    bands: list[tuple[float, float]] = []
    for y0, y1 in ys:
        if y1 - y0 < MIN_BAND_RATIO * typical:
            continue
        # Some pages paint a total row's band a little taller than its neighbours, so two
        # bands cover the same row. Keep the first and drop a band that mostly overlaps it.
        if bands and y0 < bands[-1][1] - MAX_BAND_OVERLAP * (y1 - y0):
            continue
        bands.append((y0, y1))
    return bands


def find_columns(fills: Sequence[Rect]) -> list[Interval]:
    """Column x-intervals: the most common set of rectangle x-extents across row bands."""
    band_keys = set(find_bands(fills))
    per_band: dict[tuple[float, float], set[Interval]] = {}
    for r in fills:
        key = (round(r.y0, 3), round(r.y1, 3))
        if key in band_keys:
            per_band.setdefault(key, set()).add((round(r.x0, 2), round(r.x1, 2)))
    most_common = Counter(tuple(sorted(s)) for s in per_band.values()).most_common(1)
    return list(most_common[0][0]) if most_common else []


def group_lines(words: Sequence[Word], unit: float) -> list[list[Word]]:
    """Group words into text lines by vertical centre, each line sorted left to right."""
    lines: list[list[Word]] = []
    for w in sorted(words, key=lambda w: (w.cy, w.x0)):
        if lines and abs(lines[-1][0].cy - w.cy) <= LINE_TOL * unit:
            lines[-1].append(w)
        else:
            lines.append([w])
    return [sorted(line, key=lambda w: w.x0) for line in lines]


def column_of(x: float, columns: Sequence[Interval]) -> int | None:
    for i, (x0, x1) in enumerate(columns):
        if x0 <= x < x1:
            return i
    return None


# ---------------------------------------------------------------- extraction


def extract_banded(geom: PageGeometry, source: str = "") -> Table:
    bands = find_bands(geom.fills)
    columns = find_columns(geom.fills)
    if len(bands) < 2 or len(columns) < 2:
        raise ValueError("banded strategy needs row bands split into >= 2 columns")
    label_col, value_cols = columns[0], columns[1:]
    table_top, table_bottom = bands[0][0], bands[-1][1]
    table_x0, table_x1 = columns[0][0], columns[-1][1]
    unit = row_height(bands)
    edge = EDGE_TOL * unit

    rules = merge_rules(geom.rules, unit)
    heavy = [
        r
        for r in rules
        if r.height >= RULE_SPLIT * unit
        and r.y1 <= table_top + edge
        and r.width >= TABLE_RULE_RATIO * (table_x1 - table_x0)
    ]
    heavy_rule = max(heavy, key=lambda r: r.y1) if heavy else None
    header_top = heavy_rule.y1 if heavy_rule else table_top

    in_table_x = [w for w in geom.words if table_x0 - edge <= w.cx <= table_x1 + edge]
    above = [w for w in geom.words if w.cy < (heavy_rule.y0 if heavy_rule else table_top)]
    header_words = [w for w in in_table_x if header_top <= w.cy < table_top]
    below = [w for w in geom.words if w.cy > table_bottom]

    headers = _headers(header_words, value_cols, unit)
    title_lines = [join_words(line) for line in group_lines(above, unit)]
    currency, statement = unit_and_statement(title_lines)

    thin_rules = [r for r in rules if r.height < RULE_SPLIT * unit and r.y0 >= table_top - edge]
    rows = _rows(geom.words, bands, label_col, value_cols, thin_rules, unit)

    apply_hierarchy(rows, tol=INDENT_TOL * unit)

    revision = find_revision(title_lines)
    return Table(
        statement=statement,
        unit=currency,
        headers=headers,
        periods=[period_end(h) for h in headers],
        rows=rows,
        source=source,
        page_no=geom.page_no,
        kind=detect_kind(statement, [r.label for r in rows]),
        meta={
            "lines_above": title_lines,
            "lines_below": [join_words(line) for line in group_lines(below, unit)],
            "revision": revision,
            "strategy": "banded",
            "n_bands": len(bands),
        },
    )


def _headers(words: Sequence[Word], value_cols: Sequence[Interval], unit: float) -> list[str]:
    headers = []
    for x0, x1 in value_cols:
        col_words = [w for w in words if x0 <= w.cx < x1]
        lines = [join_words(line) for line in group_lines(col_words, unit)]
        headers.append(" ".join(lines))
    return headers


def _rows(
    words: Sequence[Word],
    bands: Sequence[tuple[float, float]],
    label_col: Interval,
    value_cols: Sequence[Interval],
    thin_rules: Sequence[Rect],
    unit: float,
) -> list[Row]:
    all_cols = [label_col, *value_cols]
    full_rules = [
        r
        for r in thin_rules
        if any(
            r.width >= FULL_RULE_RATIO * (c1 - c0) and r.x0 < c1 and r.x1 > c0
            for c0, c1 in value_cols
        )
    ]
    rows: list[Row] = []
    for y0, y1 in bands:
        cells: list[list[Word]] = [[] for _ in all_cols]
        for w in words:
            if y0 <= w.cy < y1 and (col := column_of(w.cx, all_cols)) is not None:
                cells[col].append(w)
        label_words = sorted(cells[0], key=lambda w: w.x0)
        values: list[Value | None] = [
            parse_value("".join(w.text for w in sorted(cell, key=lambda w: w.x0)))
            for cell in cells[1:]
        ]
        underlined = [
            _is_underlined(cell, value_cols[i], thin_rules, unit)
            for i, cell in enumerate(cells[1:])
        ]
        rule_above = any(abs(r.y0 - y0) <= RULE_ROW_TOL * unit for r in full_rules)
        rows.append(
            Row(
                index=len(rows),
                label=join_words(label_words),
                level=0,
                path=(),
                values=values,
                row_type="item",
                rule_above=rule_above,
                underlined=underlined,
                label_x0=label_words[0].x0 if label_words else label_col[0],
            )
        )
    return rows


def _is_underlined(
    cell: Sequence[Word], col: Interval, thin_rules: Sequence[Rect], unit: float
) -> bool:
    """A rule narrower than the column that sits directly under the cell's text.

    Low-trust signal only: the source also draws such rules where nothing was corrected.
    """
    if not cell:
        return False
    x0 = min(w.x0 for w in cell)
    x1 = max(w.x1 for w in cell)
    bottom = max(w.y1 for w in cell)
    col_width = col[1] - col[0]
    for r in thin_rules:
        overlap = min(r.x1, x1) - max(r.x0, x0)
        if (
            bottom - UNDERLINE_ABOVE * unit <= r.y0 <= bottom + UNDERLINE_BELOW * unit
            and r.width < FULL_RULE_RATIO * col_width
            and overlap >= UNDERLINE_OVERLAP * (x1 - x0)
        ):
            return True
    return False

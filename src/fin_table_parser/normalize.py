"""Text and number normalisation for Japanese financial statements.

Conventions handled:
* ``△`` / ``▲`` prefix means negative (``△2,979`` -> -2979).
* ``－`` (a lone dash) means *nil*, which is different from 0.
* ``△0`` is kept as 0 with ``negative_zero=True`` so the printed form is not lost.
* Full-width digits and punctuation are folded with NFKC.
"""

from __future__ import annotations

import re
import unicodedata

from .models import Value

# Dash-like characters that mean "nil" when they are the whole cell (after NFKC).
_NIL = {"-", "−", "–", "—", "―", "ー"}
_NEGATIVE_MARKERS = "△▲"
_NUMBER = re.compile(r"\d{1,3}(?:,\d{3})+|\d+")
_DATE = re.compile(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日")


def nfkc(text: str) -> str:
    return unicodedata.normalize("NFKC", text)


# A footnote marker printed in front of an amount: "※１2,121,360" is note 1 and the amount 2,121,360.
# It must be removed BEFORE NFKC: after folding, "※１2,121,360" would read as 12,121,360. Filers
# write the marker with full-width digits and the amount with ASCII digits; if both are ASCII and
# glued together the marker is taken to be a single digit (a footnote number above 9 is rare).
_NOTE_MARKER = re.compile(r"^\s*[※＊*]\s*(?:([０-９]+)|(\d)(?=\s|\D))\s*[,，、]?\s*")


def split_note_marker(raw: str) -> tuple[str, tuple[str, ...]]:
    """``"※１2,121,360"`` -> (``"2,121,360"``, (``"※1"``,)); several markers are all removed.

    ``"※１,※２162,303"`` is notes 1 and 2 and the amount 162,303.
    """
    notes: list[str] = []
    rest = raw
    while (m := _NOTE_MARKER.match(rest)) is not None:
        notes.append(f"※{nfkc(m.group(1) or m.group(2))}")
        rest = rest[m.end() :]
    return rest, tuple(notes)


def parse_value(raw: str) -> Value | None:
    """Parse one printed cell. Returns None for an empty cell."""
    body, notes = split_note_marker(raw)
    s = nfkc(body).replace(" ", "").strip()
    if not s:
        return None
    if s in _NIL:  # must run before the sign handling: NFKC turns "－" into "-"
        return Value(raw=raw, number=None, kind="nil", notes=notes)
    negative = False
    if s[0] in _NEGATIVE_MARKERS:
        negative, s = True, s[1:]
    elif s[0] == "(" and s[-1] == ")":
        negative, s = True, s[1:-1]
    elif s[0] == "-":
        negative, s = True, s[1:]
    if not _NUMBER.fullmatch(s):
        return Value(raw=raw, number=None, kind="text", notes=notes)
    magnitude = int(s.replace(",", ""))
    return Value(
        raw=raw,
        number=-magnitude if negative else magnitude,
        kind="number",
        negative_zero=negative and magnitude == 0,
        notes=notes,
    )


def period_end(header: str) -> str | None:
    """ISO date of the last ``YYYY年M月D日`` in a column header, if any."""
    matches = _DATE.findall(nfkc(header))
    if not matches:
        return None
    year, month, day = (int(g) for g in matches[-1])
    return f"{year:04d}-{month:02d}-{day:02d}"


def strip_section_number(title: str) -> str:
    """``（１）連結貸借対照表`` / ``1【連結貸借対照表】`` / ``(連結損益計算書)`` -> the bare name."""
    name = nfkc(title).strip()
    name = re.sub(r"^[0-9①-⑳]+(?=[【\[(])", "", name)  # leading "1" or "①" before a bracket
    name = re.sub(r"^[(（]\s*\d+\s*[)）]\s*", "", name)  # "(1) "
    name = re.sub(r"^[【\[(（](.*)[】\])）]$", lambda m: m.group(1), name)  # enclosing brackets
    return name.strip()

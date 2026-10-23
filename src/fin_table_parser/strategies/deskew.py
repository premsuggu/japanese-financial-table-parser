"""Estimate and undo page skew from word positions (used on the OCR route only).

A text-layer PDF is perfectly straight; a scan is usually a little rotated. A rotation of 1 degree
shifts the far end of a 450 pt wide row by about 8 pt, more than the same-line tolerance, so labels
and amounts would land on different lines.

Method: amounts are right-aligned, so in a straight page the right edges of the amounts in one
column all share an x. In a rotated page they drift linearly with y. Try a range of drift slopes
and keep the one that makes the right edges pile up most sharply (largest sum of squared
histogram counts), then rotate every word back. Nothing here knows about a specific page.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence

from ..models import Word
from ..normalize import parse_value

MAX_SKEW_DEGREES = 4.0
STEPS = 160  # candidate slopes across +-MAX_SKEW_DEGREES (about 0.05 degree apart)
BIN_OF_HEIGHT = 0.25  # histogram bin width, in word heights
MIN_AMOUNTS = 6
MIN_GAIN = 1.15  # the best slope must beat "no skew" by this factor to be believed
MIN_ANGLE_DEGREES = 0.3  # smaller rotations shift a row by about 2 pt: not worth acting on noise
PLATEAU = 0.97  # slopes scoring this close to the best form the plateau whose centre is used


def _amounts(words: Sequence[Word]) -> list[Word]:
    return [w for w in words if (v := parse_value(w.text)) is not None and v.kind == "number"]


def _sharpness(amounts: Sequence[Word], slope: float, bin_width: float) -> float:
    counts = Counter(round((w.x1 - slope * w.cy) / bin_width) for w in amounts)
    return float(sum(c * c for c in counts.values()))


def estimate_skew_degrees(words: Sequence[Word]) -> float:
    """Rotation of the page in degrees (positive = clockwise), 0.0 if it looks straight."""
    amounts = _amounts(words)
    if len(amounts) < MIN_AMOUNTS:
        return 0.0
    heights = sorted(w.y1 - w.y0 for w in words)
    bin_width = BIN_OF_HEIGHT * heights[len(heights) // 2]
    limit = math.tan(math.radians(MAX_SKEW_DEGREES))
    slopes = [limit * (2 * i / STEPS - 1) for i in range(STEPS + 1)]
    scores = [_sharpness(amounts, s, bin_width) for s in slopes]
    top = max(scores)
    straight = _sharpness(amounts, 0.0, bin_width)
    if top < MIN_GAIN * straight:
        return 0.0
    # Several neighbouring slopes score almost equally (the histogram bins are coarse): take the
    # centre of that plateau rather than its first edge, which would bias the estimate.
    plateau = [slopes[i] for i, v in enumerate(scores) if v >= PLATEAU * top]
    slope = sum(plateau) / len(plateau)
    # column slope t = dx/dy equals -tan(alpha) for a page rotated by alpha
    angle = math.degrees(-math.atan(slope))
    return angle if abs(angle) >= MIN_ANGLE_DEGREES else 0.0


def deskew_words(words: Sequence[Word]) -> tuple[list[Word], float]:
    """Words rotated back to straight, and the angle that was removed (degrees)."""
    angle = estimate_skew_degrees(words)
    if angle == 0.0 or not words:
        return list(words), 0.0
    a = math.radians(angle)
    cos_a, sin_a = math.cos(a), math.sin(a)
    ox = sum(w.cx for w in words) / len(words)
    oy = sum(w.cy for w in words) / len(words)
    out = []
    for w in words:
        dx, dy = w.cx - ox, w.cy - oy
        cx = ox + dx * cos_a + dy * sin_a  # rotate by -angle about the centroid
        cy = oy - dx * sin_a + dy * cos_a
        half_w, half_h = (w.x1 - w.x0) / 2, (w.y1 - w.y0) / 2
        out.append(Word(w.text, cx - half_w, cy - half_h, cx + half_w, cy + half_h))
    return out, angle

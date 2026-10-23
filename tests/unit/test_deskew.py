import math

from fin_table_parser.models import Word
from fin_table_parser.strategies.deskew import deskew_words, estimate_skew_degrees


def column_page(rotation_deg: float = 0.0, n: int = 14) -> list[Word]:
    """Two right-aligned columns of amounts plus labels, rotated about the page centre."""
    a = math.radians(rotation_deg)
    cos_a, sin_a = math.cos(a), math.sin(a)
    words = []
    for i in range(n):
        y = 100 + i * 12.0
        for text, x1 in (("12,345", 400.0), ("9,876", 520.0)):
            words.append((text, x1 - 30, y, x1, y + 9))
        words.append(("ラベル", 60.0, y, 120.0, y + 9))
    out = []
    for text, x0, y0, x1, y1 in words:
        cx, cy = (x0 + x1) / 2 - 300, (y0 + y1) / 2 - 200
        rx = 300 + cx * cos_a - cy * sin_a
        ry = 200 + cx * sin_a + cy * cos_a
        out.append(Word(text, rx - (x1 - x0) / 2, ry - 4.5, rx + (x1 - x0) / 2, ry + 4.5))
    return out


def test_straight_page_has_no_skew():
    assert estimate_skew_degrees(column_page(0.0)) == 0.0


def test_estimate_recovers_the_rotation():
    for angle in (-2.0, -1.0, 0.7, 1.5, 3.0):
        assert abs(estimate_skew_degrees(column_page(angle)) - angle) < 0.15


def test_deskew_restores_alignment_of_right_edges():
    words, angle = deskew_words(column_page(1.5))
    edges = sorted({round(w.x1, 0) for w in words if w.text == "12,345"})
    assert abs(angle - 1.5) < 0.15
    assert max(edges) - min(edges) <= 1  # the column is straight again


def test_too_few_amounts_are_left_alone():
    words = column_page(2.0, n=1)
    assert deskew_words(words)[1] == 0.0

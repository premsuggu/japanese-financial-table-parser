from fin_table_parser.models import Rect, Word
from fin_table_parser.strategies.banded import find_bands, group_lines, join_words, merge_rules


def band(y0, y1):
    return Rect(0, y0, 10, y1, (1.0, 1.0, 1.0))


def test_slivers_are_not_rows():
    assert find_bands([band(0, 12), band(12, 12.7), band(12.7, 24.7)]) == [
        (0.0, 12.0),
        (12.7, 24.7),
    ]


def test_overlapping_duplicate_band_is_dropped():
    bands = find_bands([band(0, 12), band(12, 24.7), band(12.8, 24.7), band(24.7, 36.7)])
    assert bands == [(0.0, 12.0), (12.0, 24.7), (24.7, 36.7)]


def test_rule_fragments_are_merged():
    r = [Rect(0, 5, 10, 5.7), Rect(10, 5, 30, 5.7), Rect(50, 5, 60, 5.7)]
    merged = merge_rules(r, unit=12.0)
    assert [(m.x0, m.x1) for m in merged] == [(0, 30), (50, 60)]


def test_join_words_spaces_only_between_ascii_alnum():
    ws = [
        Word("建物", 0, 0, 10, 10),
        Word("及び", 10, 0, 20, 10),
        Word("ABC", 30, 0, 40, 10),
        Word("123", 41, 0, 50, 10),
    ]
    assert join_words(ws) == "建物及びABC 123"


def test_group_lines_by_vertical_centre():
    ws = [Word("b", 20, 0, 30, 10), Word("a", 0, 1, 10, 11), Word("c", 0, 30, 10, 40)]
    assert [[w.text for w in line] for line in group_lines(ws, unit=12.0)] == [["a", "b"], ["c"]]

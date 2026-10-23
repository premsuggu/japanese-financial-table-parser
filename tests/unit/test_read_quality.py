"""Read agreement and label vocabulary checks, on small synthetic tables."""

from fin_table_parser.crosscheck import compare_reads
from fin_table_parser.labelcheck import check_labels, load_lexicon, nearest_known
from fin_table_parser.validate import summarize, validate_tables

from .test_validate import make_table

SPEC = [
    (0, "資産の部", None),
    (1, "流動資産", None),
    (2, "現金及び預金", "100"),
    (2, "受取手形及び売掛金", "200"),
    (2, "流動資産合計", "300"),
]


def with_label(table, old, new):
    for r in table.rows:
        if r.label == old:
            r.label = new
    return table


def with_amount(spec, label, raw):
    return make_table(
        [(lv, lb, raw if lb == label else (v[0] if v else None)) for lv, lb, *v in spec]
    )


def test_identical_reads_agree():
    assert compare_reads(make_table(SPEC), make_table(SPEC)) == []


def test_a_digit_read_two_ways_is_flagged_at_its_row_and_column():
    other = with_amount(SPEC, "現金及び預金", "1,00")
    found = compare_reads(make_table(SPEC), other)
    assert [(f.status, f.row) for f in found] == [("WARN", "現金及び預金")]
    assert "100" in found[0].detail


def test_a_label_read_two_ways_is_flagged_when_amounts_match():
    other = with_label(make_table(SPEC), "受取手形及び売掛金", "受取手形及び売掛全")
    found = compare_reads(make_table(SPEC), other)
    assert len(found) == 1 and "label read two ways" in found[0].detail


def test_a_row_only_one_read_found_is_reported():
    other = make_table(SPEC[:-2] + [SPEC[-1]])
    found = compare_reads(make_table(SPEC), other)
    assert any("not found" in f.detail for f in found)


def test_lexicon_ships_with_the_package():
    lexicon = load_lexicon()
    assert "現金及び預金" in lexicon and len(lexicon) > 100


def test_near_miss_of_a_known_label_is_flagged_with_the_suggestion():
    lexicon = frozenset({"現金及び預金", "流動資産", "流動資産合計"})
    table = make_table([(2, "現全及び預金", "100")])
    found = check_labels(table, lexicon)
    assert len(found) == 1 and "現金及び預金" in found[0].detail


def test_known_far_and_short_labels_are_left_alone():
    lexicon = frozenset({"現金及び預金"})
    table = make_table([(2, "現金及び預金", "1"), (2, "会社独自の勘定", "2"), (2, "現全", "3")])
    assert check_labels(table, lexicon) == []


def test_near_miss_is_ignored_when_the_intended_label_is_also_printed():
    lexicon = frozenset({"短期借入金", "長期借入金"})
    table = make_table([(2, "短期借入金", "1"), (2, "長期借入金", "2"), (2, "長期借入全", "3")])
    # 長期借入全 is one edit from 長期借入金, which is on the page: a different line, not a misread
    assert check_labels(table, lexicon) == []


def test_nearest_known_requires_exactly_one_edit():
    assert nearest_known("現全及び預金", ["現金及び預金"]) == ["現金及び預金"]
    assert nearest_known("現金及び預金", ["現金及び預金"]) == []


def test_ocr_routed_table_gets_the_label_check_in_validation():
    table = make_table([(2, "現全及び預金", "100")])
    assert summarize(validate_tables([table]))["WARN"] == 0  # text layer: not applied
    table.meta["route"] = "ocr:x"
    # not in the shipped list, so no flag unless it is one edit from a listed label
    assert summarize(validate_tables([table]))["FAIL"] == 0


def test_ocr_table_that_passes_its_checks_still_needs_a_look_until_two_reads_agree():
    from fin_table_parser.ui_model import group_health, table_health

    from .test_validate import GOOD

    table = make_table(GOOD, "balance sheet")
    table.kind = "balance_sheet"
    base = table_health(table)[0]
    assert base == "ok"
    table.meta["route"] = "ocr:x"
    expected = "review" if base == "ok" else base
    assert table_health(table)[0] == expected
    assert group_health([table])[0][0] == expected
    table.meta.update(reads=2, read_findings=[])
    assert table_health(table)[0] == base
    assert group_health([table])[0][0] == base

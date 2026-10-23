"""Label vocabulary check: flag an OCR label that is one character away from a known account name.

OCR mostly goes wrong on kanji, and a misread label (``繰延税金資産`` read as ``繰延税全資産``) changes no
amount, so the accounting checks cannot see it. A label that is not in the list of known labels, but
differs from one by a single character, is almost always such a misread.

This never corrects anything: it only warns and names the likely intended label. A label far from
everything known is left alone (companies have account names of their own).
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from .labels import edit_distance, label_key
from .models import Finding, Table

CHECK = "label_vocabulary"
MIN_LENGTH = 4  # shorter labels are within one edit of too many unrelated words
LEXICON_FILE = Path(__file__).with_name("data") / "labels_ja.txt"


def load_lexicon(path: Path = LEXICON_FILE) -> frozenset[str]:
    if not path.exists():
        return frozenset()
    lines = path.read_text(encoding="utf-8").splitlines()
    return frozenset(label_key(x) for x in lines if x.strip() and not x.startswith("#"))


def table_labels(tables: Iterable[Table]) -> set[str]:
    """Label keys of every row of the given tables."""
    return {label_key(r.label) for t in tables for r in t.rows if label_key(r.label)}


def nearest_known(key: str, lexicon: Iterable[str]) -> list[str]:
    """Known labels exactly one edit away from ``key``."""
    return [k for k in lexicon if abs(len(k) - len(key)) <= 1 and edit_distance(k, key) == 1]


def check_labels(table: Table, lexicon: frozenset[str]) -> list[Finding]:
    if not lexicon:
        return []
    present = {label_key(r.label) for r in table.rows}
    findings: list[Finding] = []
    for row in table.rows:
        key = label_key(row.label)
        if len(key) < MIN_LENGTH or key in lexicon:
            continue
        # the intended label already printed elsewhere on the page means this is a different line
        near = [k for k in nearest_known(key, lexicon) if k not in present]
        if near:
            findings.append(
                Finding(
                    CHECK,
                    "WARN",
                    table.statement or table.source,
                    "",
                    row.label,
                    detail=f"'{row.label}' is not a known label; did you mean '{near[0]}'?",
                )
            )
    return findings

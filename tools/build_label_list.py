"""Build src/fin_table_parser/data/labels_ja.txt from financial-statement PDFs.

    python -X utf8 tools/build_label_list.py data/corpus/yamato

Only pages whose parse passes every accounting check contribute, so a misread label cannot enter the list.
"""

from __future__ import annotations

import sys
from pathlib import Path

from fin_table_parser.labelcheck import LEXICON_FILE, table_labels
from fin_table_parser.pdf_io import page_count
from fin_table_parser.pipeline import parse_page
from fin_table_parser.triage import UnsupportedPage
from fin_table_parser.validate import summarize, validate_tables

STATEMENT_KINDS = {"balance_sheet", "income_statement", "comprehensive_income", "cash_flow"}
MAX_LABEL = 30  # longer lines are sentences from the notes, not account names


def main(corpus: str) -> None:
    labels: set[str] = set()
    for pdf in sorted(Path(corpus).glob("*/*.pdf")):
        for page in range(page_count(pdf)):
            try:
                table = parse_page(pdf, page)
            except UnsupportedPage:
                continue
            counts = summarize(validate_tables([table]))
            if table.kind in STATEMENT_KINDS and counts["FAIL"] == 0 and counts["PASS"] > 0:
                labels |= {
                    k
                    for k in table_labels([table])
                    if len(k) <= MAX_LABEL and not set(k) & set("。「」")
                }
    LEXICON_FILE.parent.mkdir(parents=True, exist_ok=True)
    header = "# known account labels (one per line), built by tools/build_label_list.py\n"
    LEXICON_FILE.write_text(header + "\n".join(sorted(labels)) + "\n", encoding="utf-8")
    print(f"{len(labels)} labels -> {LEXICON_FILE}")


if __name__ == "__main__":
    main(sys.argv[1])

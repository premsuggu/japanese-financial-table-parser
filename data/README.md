# Test documents

These are public filings of one company (ヤマト モビリティ & Mfg.株式会社, code 7886) and are included for testing.
Source and per-file notes: [corpus/README.md](corpus/README.md).

* `balance_sheet_after_correction.pdf` (project root): the sample page, page 3 of the 2026-06-26 correction notice
  (full-year, 連結貸借対照表). It is the page the ground truth in `tests/fixtures/ground_truth/` describes.
* `complete_pdf.pdf` (project root): the full-year 決算短信.
* `data/corpus/yamato/<id>/<id>.pdf`: ten more documents used for cross-checks and the OCR evaluation.

Parser output for all of them is in `output/`. The files are third-party documents: treat them as untrusted input.

# Test documents are not included

The sample PDFs are public filings of a third-party company and are not redistributed in this repository.
Tests that need them are skipped when the files are missing. To run the full suite, put these in the project root:

* `balance_sheet_after_correction.pdf`: page 3 of the company's 2026-06-26 correction notice (full-year, 連結貸借対照表)
* `complete_pdf.pdf`: the full-year 決算短信

and optionally download the corpus listed in [corpus/README.md](corpus/README.md) into `data/corpus/yamato/<id>/`.

# Installed packages ledger

Rule agreed with the user: large downloads are fine, but anything redundant is removed once it is no longer
needed, and **nothing is deleted without the user's OK**. OCR candidates and the browser used for UI checks live in
their own virtual environments under the project root, so removing one is deleting one folder and cannot break
the main environment. Model weights and caches live *outside* those folders, so they are listed separately.

Measured 2026-10-23.

## Main environment (system Python 3.12)

| Package | Why | Status |
|---|---|---|
| pymupdf | read PDF text layer, drawings, render pages (AGPL, fine for personal use) | keep (was already installed) |
| openpyxl | write / read the Excel output | keep |
| pyyaml, pandas | rules file, UI tables | keep (were already installed) |
| streamlit 1.41.0 | the upload-a-PDF UI. Pulled in pyarrow, altair, pydeck, tornado, watchdog (about 0.3 GB) | keep |
| pytest, ruff, mypy | tests, lint, types | keep (dev tools) |
| fin_table_parser (editable install) | `python -m fin_table_parser ...` | keep |

`numpy`, `pydantic` were already present and are unused by this project.

## Isolated environments (project root)

| Folder | Size | Contents | Purpose | Proposal |
|---|---|---|---|---|
| `.venv-yomitoku/` | 1.1 GB | yomitoku, torch (CPU build) | OCR candidate 1 | keep if it wins the comparison |
| `.venv-paddle/` | 926 MB | paddlepaddle, paddleocr, opencv | OCR candidate 2 | remove if it loses |
| `.venv-browser/` | 125 MB | playwright | headless browser for UI checks | remove (UI check done) |

## Caches and weights outside the project (created by this work)

| Location | Size | What | Proposal |
|---|---|---|---|
| pip cache `%LOCALAPPDATA%\pip\cache` | 944 MB | downloaded wheels | purge (`pip cache purge`); only costs re-download time |
| `%LOCALAPPDATA%\ms-playwright` | 719 MB | Chromium for playwright | remove together with `.venv-browser` |
| `~/.paddlex` | 133 MB | PaddleOCR models | remove together with `.venv-paddle` if it loses |
| `~/.cache/huggingface/hub/models--KotaroKinoshita--yomitoku-*` (2 folders) and their 2 blobs (98 MB + 192 MB) | 290 MB | YomiToku weights | keep if YomiToku wins |

**Not ours, do not delete:** the rest of `~/.cache/huggingface` (about 9.6 GB: Whisper, pyannote, sentence-transformers,
all dated July 2026 or earlier) and `~/.cache/torch` (314 MB, dated July 2026).

## Licences

* PyMuPDF: AGPL-3.0 (fine for personal use, matters only if distributed).
* YomiToku: open-source edition reported as non-commercial; fine here (personal use). Verify in its repository before
  any commercial use.
* PaddleOCR / PaddlePaddle: Apache-2.0.

## Downloaded data

`data/corpus/yamato/` (10 PDFs, 3.3 MB): test documents from the company's public IR page, see `data/corpus/README.md`.

## Cleanup done 2026-10-23 (user approved)

Removed: `.venv-paddle`, `.venv-browser`, `~/.paddlex`, `%LOCALAPPDATA%\ms-playwright`, pip cache (about 2.8 GB).
Kept: `.venv-yomitoku` and its two Hugging Face model files (the OCR engine that won the comparison).
The rows above for the removed items are historical. PaddleOCR is no longer available: `ocr-eval --engines paddle` will report it missing.

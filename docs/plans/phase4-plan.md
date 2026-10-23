# Phase 4 plan: other companies, other layouts (proposal, awaiting approval)

## Problem

Everything so far is tested on one company's filings, so "works" mostly means "works on this company's layout".
The unsupported list (note-number column, grid-ruled pages, top-aligned wrapped labels, IFRS statement names) is also
untested because the corpus never shows those layouts. Goal: find out how the parser really behaves on other
companies, then fix what breaks, with numbers before and after.

## Steps

### P1. Build a multi-company corpus and measure the parser as it is (no code changes first)
* Download 10 to 15 public 決算短信 / 有価証券報告書 PDFs from other companies' IR pages: different industries, J-GAAP
  and IFRS (連結財政状態計算書), with and without a note-number (注記) column, banks/insurers if reachable, two- and
  one-page balance sheets. Candidates seen in search: Honda, Ajinomoto, LY Corporation, Fujitsu (final list after I look
  at each file).
* Each file in its own directory under `data/corpus/<company>/`, treated as untrusted (`python -I`), not committed
  (same rule as now), with provenance in `data/corpus/README.md`.
* Run the current parser unchanged over every page. Report: pages found as statements, checks passed / failed /
  unverified, pages skipped and why, and a hand check of a sample of pages against the page image. This baseline is the
  honest "before" number.

### P2. Fix the failure modes the baseline shows
Expected, to be confirmed by P1 (I will not guess the order): note-number column, IFRS names and total rules
(資本合計, 負債及び資本合計), top-aligned wrapped labels, grid-ruled tables, multi-line headers, different units
(百万円). Each fix: a failing test from a real page first, then the change, then the corpus re-run. Every tolerance stays
relative to the measured page; no coordinates.

### P3. Independent ground truth
Silver references are the parser's own output, so they cannot show a shared mistake. Options:
* EDINET API (free but needs an API key registered to your email) gives XBRL values for 有価証券報告書: a truth the
  parser never touched. I cannot register for you.
* Without a key: hand-check 5 pages against the images (you review a table I prepare, as with the sample page).

### P4. More realistic scan simulation
Add blur, uneven lighting and noise to the simulated scans and re-run the OCR safety-net evaluation on the new
companies. Real scanned PDFs from you would be better than any simulation.

### Not in this phase (say if you want them)
Per-cell review in the UI with the page image; speed work (GPU / region OCR); more OCR engines.

## Technical details
* Dependencies: none new. Downloads need the network; large files fine.
* Tests: real-page regression tests cannot ship company PDFs, so fixes are tested with small synthetic pages that
  reproduce the layout (like `tests/ocr_sim.py`), plus the local-only corpus run.
* Quality gates as before.

## Risks
* Some IR pages block downloads (JPX returned 403); I will say which companies I could not get.
* Layout variety may need a design change, not a patch (for example grid-ruled tables). I will stop and bring you the
  options before building anything large.
* Hand-checking pages is slow; sample size will be small and stated.

## Decisions needed from you
1. Approve this plan or change it.
2. EDINET API key: will you register one (free) and give it to me for the session, or should I use the hand-check?
3. Do you have any real scanned PDFs (any company) I can test on? Even one helps.

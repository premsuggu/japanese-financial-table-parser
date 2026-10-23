# Research: PDF Table Parsers for Japanese Financial Statements

> Status: research only. No parser code has been written yet.
> Date: 2026-10-22. Sample analysed: `balance_sheet_after_correction.pdf`

---

## 1. What the sample page actually contains

`balance_sheet_after_correction.pdf` is page 4 of a corrected 決算短信 (Kessan Tanshin, "(訂正後)"),
showing the asset half of a 連結貸借対照表 (consolidated balance sheet).

Facts measured with PyMuPDF 1.28.2 (already installed):

| Property | Observation | Consequence for the parser |
|---|---|---|
| PDF type | Born-digital, real text layer, 0 images, fonts MeiryoUI / MS-Mincho (Identity-H) | Characters can be read exactly; no OCR needed for this page |
| Table ruling | 341 vector drawings: light-blue row bands (`fill=(0.8,0.93,1.0)`), white bands, black horizontal rules. **No vertical lines** | "Lattice" (grid) detection alone is insufficient; columns must come from text alignment |
| Hierarchy | Label `x0` clusters at ≈ 62 / 75 / 88 / 101 / 114 pt (≈13 pt steps) | Indentation encodes the account tree (資産の部 → 固定資産 → 有形固定資産 → 建物及び構築物 → 減価償却累計額) |
| Repeated labels | その他 ×4, 減価償却累計額 ×3, リース資産 ×2 | A flat table is ambiguous; each row needs its **parent path** |
| Header | Two-line column header: 前連結会計年度 / (2025年３月31日) | PyMuPDF `find_tables()` **dropped this header**; must be rebuilt |
| Negatives | `△2,979` (△ = minus sign in Japanese accounting) | Normalise to `-2979` |
| Nil vs zero | `－` (nil) vs `△0` (negative rounding to zero) | Keep distinct: `null` + `is_nil` vs `0` |
| Unit | `（単位：千円）` above the table | Store unit/scale as table metadata |
| Full-width chars | `３月31日`, `（純額）` | NFKC normalisation |
| Subtotal rules | Black rules spanning full column width above 合計 / 純額 rows | Useful signal for "total" rows |
| **Word-width underlines** | `218,836` and `1,123` (current year) have a rule exactly as wide as the word (31.6 pt / 22.6 pt). These two are corrections vs the original (53,925 / 166,033), but the 3rd correction (`△0`, was `0`) has no underline, and the *original* filing also has such underlines on p.10 (e.g. 187,285) where nothing was corrected | **Not a reliable correction marker.** Record as a low-trust per-cell flag only; detect corrections by diffing 訂正前/訂正後 |
| Page furniture | `- 4 -`, `(訂正後)`, section titles 3．/（1） | Strip from the table, keep as metadata |
| Continuation | Liabilities & equity (負債純資産の部) is almost certainly on the next page | Design must support multi-page tables |

Arithmetic check (important for validation design):

```
Σ 流動資産 items (prior)   = 5,863,681  vs stated 5,863,684   (diff 3)
Σ 流動資産 items (current) = 3,377,405  vs stated 3,377,407   (diff 2)
建物及び構築物 2,121,360 − 1,923,585 = 197,775  (exact)
```

Each line item is rounded independently to 千円, so **sum checks need a tolerance of about ±(number of summands)**.
Strict equality would raise false alarms.

Baseline: `page.find_tables()` (PyMuPDF) finds 1 table, 43 rows × 3 cols, with correct body values.
It loses the header and the hierarchy. It is a good start but not a correct table.

---

## 2. The four families of table parsers

### 2.1 Rule-based, text-layer + geometry (classical)

**Tools:** Camelot, pdfplumber, PyMuPDF `find_tables()` (a port of pdfplumber's algorithm), Tabula.

How they work:

1. Read characters/words with exact coordinates from the PDF content stream.
2. Find the table grid by one of two strategies:
   - **Lattice / "lines"**: collect ruling lines (vector paths, or Camelot renders the page and uses
     OpenCV erosion/dilation to isolate horizontal/vertical segments), intersect them, and form cells.
   - **Stream / "text"**: no lines. Group words into rows by y-coordinate, then infer column
     boundaries from x-alignment (Camelot uses the most common words-per-row count to guess columns).
3. Assign each word to the cell whose box contains it.

```python
# pdfplumber: mixed strategy, horizontal rules from drawings, columns from text alignment
table = page.extract_table({"vertical_strategy": "text", "horizontal_strategy": "lines"})
```

| Pros | Cons |
|---|---|
| Characters are exact (cannot hallucinate numbers) | Breaks on scanned PDFs (no text layer) |
| Fast (ms/page), CPU-only, deterministic, debuggable | Heuristics need tuning per layout family |
| Full access to drawings (underlines, bands, rules) | No semantic understanding (hierarchy, headers) out of the box |

### 2.2 Deep-learning pipelines (detect, then recognise structure)

**Tools:** Docling (IBM), MinerU pipeline mode, PaddleOCR PP-Structure, Microsoft Table Transformer (TATR), YomiToku (Japanese).

How they work (Docling as the reference design):

1. **Layout detection**: an object detector (Docling: RT-DETR trained on DocLayNet) draws boxes
   around tables, text, titles, footnotes, etc.
2. **Table structure recognition (TSR)**: the table crop goes to a vision transformer
   (Docling: TableFormer; Microsoft: TATR trained on PubTables-1M / FinTabNet). It predicts rows, columns,
   spanning cells and header cells.
3. **Cell content**: taken from the PDF text layer when present (Docling matches predicted cells back
   to PDF text cells), otherwise from OCR.

| Pros | Cons |
|---|---|
| Handles borderless and irregular tables and merged headers | Heavier (PyTorch; a GPU helps), slower |
| Works on scans (with OCR) | Structure errors are hard to debug; row hierarchy by indentation is usually **not** output |
| Docling/MinerU keep text-layer characters for digital PDFs | Generic training data (scientific papers); Japanese financial layouts are under-represented |

**YomiToku** is the only one built specifically for Japanese (custom OCR, layout and table models, merged-cell
support). Its open-source license is reportedly non-commercial. Verify that before adopting it.

### 2.3 End-to-end document VLMs (image → Markdown/HTML)

**Tools:** PaddleOCR-VL 1.5/1.6, MinerU 2.5(-Pro), GLM-OCR, dots.ocr, Mistral OCR; general VLMs
(Gemini 3, Claude, GPT, Qwen3-VL).

How they work: the page image goes into a vision-language model, which writes the table directly as
HTML/Markdown/JSON. Specialised OCR-VLMs are fine-tuned on document parsing; general VLMs are prompted.

| Pros | Cons |
|---|---|
| Currently top of public benchmarks (OmniDocBench table TEDS: PaddleOCR-VL-1.6 ≈ 94.8, MinerU2.5-Pro ≈ 93.4, Gemini 3 Flash ≈ 89.3) | **Can hallucinate or alter numbers.** In the Needl test, GPT-5.5 altered values in a financial table |
| Handle scans, odd layouts, multilingual text | Non-deterministic, GPU or paid API, data leaves the machine (API) |
| Can output hierarchy if prompted | TEDS measures structure+text similarity; a 1-digit error in a balance sheet still scores high |

### 2.4 Commercial cloud APIs

**Tools:** Azure Document Intelligence, AWS Textract, Google Document AI, LlamaParse, Reducto.

Hosted versions of 2.2/2.3. On Reducto's (vendor) RD-TableBench, Azure scored 82.7 %, Textract 80.9 %
and Google 64.6 %. None of the benchmarks found report Japanese-specific table accuracy.
Per-page cost; documents go to a third party.

---

## 3. How strong is the evidence?

Be careful with all published rankings:

| Source | Type | Caveat |
|---|---|---|
| OmniDocBench (CVPR 2025) leaderboard | Academic, broad | Mostly Chinese/English; TEDS is tolerant of single-digit errors |
| Dr. DocBench (arXiv 2606.01393) | Academic | MinerU best on tables; excerpt-level reading only |
| Needl.ai technical note (Jun 2026) | Industry | **Single 17-page document**; judge model is also a contestant |
| Independent 27-doc benchmark (dev.to) | Self-published | Docling TEDS 0.83, MinerU 0.80; tiny corpus |
| Reducto RD-TableBench | Vendor | Vendor ranks its own product first |

The honest conclusion: **no benchmark covers Japanese 決算短信/有報 balance sheets**, and none score
exact numeric correctness. We need our own test set (Section 6).

---

## 4. License snapshot (verify before adoption)

| Tool | License (as reported) | Note |
|---|---|---|
| PyMuPDF | **AGPL-3.0** or commercial | Already installed; AGPL matters for closed-source/SaaS use |
| pdfplumber, Camelot | MIT | Pure-Python alternatives to PyMuPDF |
| Docling | MIT (code); models permissive | IBM-backed, active |
| PaddleOCR / PaddleOCR-VL | Apache-2.0 | Requires PaddlePaddle framework |
| MinerU | Changed from AGPL; custom license | Verify current terms |
| Marker | GPL-3.0 code; model weights with revenue-based restrictions | |
| Table Transformer | MIT | Lower accuracy than newer models |
| YomiToku (OSS) | Reportedly non-commercial | Commercial: YomiToku-Pro (MLism) |

---

## 5. Recommendation

**Hybrid, "text-layer first, model as fallback, arithmetic as judge".**

```
PDF page
  │
  ├─ 1. Triage ─ text layer healthy? (share of valid CJK/digit chars, no mojibake from bad ToUnicode)
  │        │ yes                                 │ no (scan / garbled)
  │        ▼                                     ▼
  ├─ 2a. Geometric extractor (PyMuPDF)     2b. Model extractor (Docling / PaddleOCR-VL / VLM)
  │      words + drawings → rows, cols,          image → cells
  │      indent levels, header, flags
  │        └──────────────┬──────────────────────┘
  ├─ 3. Normalise: NFKC, △→minus, －→nil, unit 千円, period headers
  ├─ 4. Build hierarchy from indentation → parent path per row
  ├─ 5. Validate: Σ children ≈ 合計 (±n rounding), gross − 減価償却累計額 = 純額, 資産合計 = 負債純資産合計
  └─ 6. Output: hierarchical JSON (+ flat CSV view), with per-cell flags & confidence
```

Why this shape:

1. **Correctness first.** For a born-digital filing the text layer *is* the ground truth. Geometry
   cannot invent a digit; a VLM can.
2. **Balance sheets are self-checking.** The accounting identities let the system detect its own
   errors and choose between extractors, instead of relying on a benchmark score.
3. **The hard parts are domain-specific** (indent hierarchy, △, －, multi-page continuation).
   No off-the-shelf tool outputs these; we need our own layer on top regardless of the backend.
4. **The fallback is pluggable.** Docling is the safest default (MIT, CPU-capable, uses the text layer).
   A specialised VLM (PaddleOCR-VL) is the strongest choice for scans if a GPU is available.

Conditional on answers still pending:
- If commercial / closed-source: PyMuPDF's AGPL may force a switch to pdfplumber (MIT) for step 2a.
- If scanned PDFs are out of scope: step 2b can be deferred entirely.
- If cloud APIs are allowed: a general VLM can serve as the fallback, gated by step 5.

---

## 6. Test corpus strategy (for the later phase)

**Ground truth comes for free from XBRL.** Japanese listed companies file the same statements as XBRL:

| Source | What it gives | Access |
|---|---|---|
| **EDINET API v2** (FSA) | 有価証券報告書 / 四半期報告書 PDFs **and** XBRL (exact values per account) | Free, **requires registering for an API key** (user action) |
| **TDnet** (JPX) | 決算短信 PDF + summary XBRL + financial-statement inline XBRL | Public web listing keeps only about 31 days. Collect continuously or use archives |
| JPX taxonomy docs | Account element definitions (e.g. `jppfs_cor:CashAndDeposits`) | Public |

PDF + XBRL pairs let us score **exact cell accuracy** automatically, at scale.

Stress cases to collect (harder than this page):

- Liabilities & equity continuation page (multi-page table)
- 連結損益計算書 / 包括利益計算書 (P&L, comprehensive income)
- **株主資本等変動計算書** (statement of changes in equity: wide matrix, multi-level headers, the hardest case)
- キャッシュ・フロー計算書 (cash-flow statement)
- 有報 side-by-side layouts, footnote markers (※1, ※2), "注記番号" note columns
- IFRS filers (different account names, 4-column formats), banks/insurers (different templates)
- 訂正前 vs 訂正後 pairs (this PDF + `complete_pdf.pdf` differ in exactly 3 cells: a ready-made diff test)
- Scanned or image-only filings, and PDFs with broken ToUnicode maps (garbled text)
- Landscape pages, two tables on one page, tables split across columns

---

## Sources

- Camelot "How it works": https://camelot-py.readthedocs.io/en/latest/user/how-it-works.html
- pdfplumber docs: https://docsearch.algolia.com/mcp/docs/repo/jsvine/pdfplumber
- Docling technical report: https://export.arxiv.org/pdf/2408.09869
- PubTables-1M / Table Transformer: https://arxiv.org/pdf/2110.00061 , https://github.com/microsoft/table-transformer
- OmniDocBench: https://github.com/opendatalab/OmniDocBench , https://arxiv.org/html/2412.07626v2
- Dr. DocBench: https://arxiv.org/pdf/2606.01393
- Needl.ai benchmark note: https://needl.ai/technical-notes/benchmarking-pdf-extraction-tools
- Independent 27-doc benchmark: https://github.com/hraju115/pdf-extraction-benchmark
- Reducto on Azure DI / RD-TableBench: https://reducto.ai/blog/evaluating-azure-document-intelligence-for-pdf-parsing
- French financial VLM benchmark: https://arxiv.org/abs/2602.10384
- YomiToku: https://docsearch.algolia.com/mcp/docs/repo/kotaro-kinoshita/yomitoku
- TDnet file specification: https://www.jpx.co.jp/equities/listing/disclosure/xbrl/nlsgeu000005vk0b-att/File_Specification_for_TDnet_Filing_20240721.pdf
- TDnet/EDINET XBRL relationship (TSE notice): https://www.nse.or.jp/company/com/notice/files/h19zikig10.pdf
- EDINET API usage: https://zenn.dev/joanofarc/articles/get-financial-info-by-edinet

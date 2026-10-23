# Ground-truth review sheet

**What this is:** the expected answer for `balance_sheet_after_correction.pdf`, laid out so you can
compare it with the PDF side by side. The source file is
`tests/fixtures/ground_truth/balance_sheet_after_correction.json`.

**Who wrote it:** Claude, from the PDF's text dump (numbers) and the rendered page (indent, row type,
underlines). It was written after the parser's output had been displayed, so it is *not* an independent
check yet. A human read against the PDF is what makes it one.

## How to review (about 10 minutes)

Open `balance_sheet_after_correction.pdf` next to this sheet and read down the table. **Compare against the
PDF, not against the parser's Excel file** (otherwise a shared mistake stays hidden). For each row check:

1. **Label**: spelled exactly as printed (including （純額）, （△は減少）-style brackets).
2. **Indent**: the number of `›` marks equals how far the label is indented. Level 0 is the leftmost label
   (資産の部), each further step is one indent step to the right.
3. **Numbers and signs**: every digit, and that `△` (negative) and `－` (nil) match the page. `△0` and `0`
   are different printed forms; `－` is not the same as 0.
4. **Type**: `section` = heading with no numbers, `item` = a line item, `net` = a （純額） row,
   `total` = a 合計 row.
5. **Underlined cells** (marked 🔸): the PDF underlines exactly these two numbers (the current-year
   投資有価証券 and 関係会社株式).
6. **Header / unit**: column headers and the unit 千円 (shown below).

**What to send back:** either *"all correct"*, or a list like *"row 11: current should be △0 not 0"*
using the row numbers below. I will fix the JSON, re-run the evaluation and tell you what changed.

- Statement: 連結貸借対照表   Unit: 千円   Revision marker: 訂正後
- Column 1 header: 前連結会計年度 (2025年3月31日)
- Column 2 header: 当連結会計年度 (2026年3月31日)
- Rows: 43  (expected: 43 rows, 2 value columns)

| Row | Label (› = one indent step) | Type | Prior year | Current year | Note |
|---:|---|---|---:|---:|---|
| 0 | 資産の部 | section |  |  | |
| 1 | › 流動資産 | section |  |  | |
| 2 | › › 現金及び預金 | item | 2,002,429 | 608,281 | |
| 3 | › › 受取手形 | item | 20,659 | 26,333 | |
| 4 | › › 売掛金 | item | 2,019,476 | 884,339 | |
| 5 | › › 電子記録債権 | item | 564,667 | 370,468 | |
| 6 | › › 商品及び製品 | item | 589,488 | 1,019,663 | |
| 7 | › › 仕掛品 | item | 186,748 | 55,344 | |
| 8 | › › 原材料及び貯蔵品 | item | 370,403 | 136,082 | |
| 9 | › › 短期貸付金 | item | 7,530 | 30,000 | |
| 10 | › › その他 | item | 105,260 | 246,895 | |
| 11 | › › 貸倒引当金 | item | △2,979 | △0 | |
| 12 | › › 流動資産合計 | total | 5,863,684 | 3,377,407 | |
| 13 | › 固定資産 | section |  |  | |
| 14 | › › 有形固定資産 | section |  |  | |
| 15 | › › › 建物及び構築物 | item | 2,121,360 | 1,880,082 | |
| 16 | › › › › 減価償却累計額 | item | △1,923,585 | △1,640,253 | |
| 17 | › › › › 建物及び構築物（純額） | net | 197,775 | 239,828 | |
| 18 | › › › 機械装置及び運搬具 | item | 4,024,922 | 2,250,799 | |
| 19 | › › › › 減価償却累計額 | item | △3,634,165 | △1,914,091 | |
| 20 | › › › › 機械装置及び運搬具（純額） | net | 390,757 | 336,708 | |
| 21 | › › › 土地 | item | 768,976 | 705,403 | |
| 22 | › › › リース資産 | item | 210,746 | 213,939 | |
| 23 | › › › › 減価償却累計額 | item | △147,599 | △172,066 | |
| 24 | › › › › リース資産（純額） | net | 63,146 | 41,872 | |
| 25 | › › › 建設仮勘定 | item | － | 4,553 | |
| 26 | › › › その他 | item | 848,814 | 446,126 | |
| 27 | › › › › 減価償却累計額 | item | △840,375 | △421,883 | |
| 28 | › › › › その他（純額） | net | 8,439 | 24,243 | |
| 29 | › › › 有形固定資産合計 | total | 1,429,094 | 1,352,610 | |
| 30 | › › 無形固定資産 | section |  |  | |
| 31 | › › › リース資産 | item | 34,190 | 21,402 | |
| 32 | › › › その他 | item | 10,070 | 14,466 | |
| 33 | › › › 無形固定資産合計 | total | 44,261 | 35,869 | |
| 34 | › › 投資その他の資産 | section |  |  | |
| 35 | › › › 投資有価証券 | item | 44,180 | 218,836 🔸 | |
| 36 | › › › 関係会社株式 | item | 1,123 | 1,123 🔸 | |
| 37 | › › › 長期貸付金 | item | － | 62,000 | |
| 38 | › › › 退職給付に係る資産 | item | 18,404 | 16,435 | |
| 39 | › › › その他 | item | 133,361 | 70,967 | |
| 40 | › › › 投資その他の資産合計 | total | 197,069 | 369,362 | |
| 41 | › › 固定資産合計 | total | 1,670,426 | 1,757,841 | |
| 42 | › 資産合計 | total | 7,534,110 | 5,135,249 | |

Numbers to verify: 74 (non-empty cells).

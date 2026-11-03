# DATA_NOTES.md — Astypalea iPOY Dataset Reference

This file documents every column in the processed CSVs, the source PDF layouts
as observed, and all open questions that these files cannot resolve.

**Last updated**: 2026-11-02, after inspecting the weekly reports, weekly proposed plans and monthly bulletins.
**Status**: Weekly formats and bulletins verified against the PDFs. Yearly 2020 to 2024 files
(§1a, §1c) are not downloaded yet, so those layouts are still unverified.

---

## 1. Source files

### 1a. HEDNO yearly operations reports 2020–2024 ("Απολογισμοί")

| Attribute | Value |
|-----------|-------|
| Publisher | HEDNO / ΔΕΔΔΗΕ |
| Frequency | Annual (one PDF per year) |
| Language | Greek |
| Format | PDF (likely table-heavy) |
| Section in manifest | `yearly_actuals` |

**Observed layout**: not verified (no yearly file downloaded yet).

Expected structure (from task spec; verify with 02_inspect.py):
- One block per day.  Header line: weekday + date + "Απολογιστική λειτουργία ΗΣ Αστυπάλαιας".
- Table columns: hours 0–23 plus ΣΥΝΟΛΟ (daily total).
- Row "Ζήτηση" = hourly energy in MWh.  Because each interval is 1 h, MWh = MW numerically.
- Unit rows (G5, G6, G7, G8, MITSUBISHI S16-RPTA): "1" when running, "Διαθέσιμη" (= available,
  not running) otherwise.
- Free-text remarks sometimes appear below a table (e.g. "Διακοπή 07:30–10:00 λόγω εργασιών δικτύου").

**Record of actual observations**: none yet. As of 2026-11-02 no yearly report has been
downloaded (all HEDNO files in `data/raw/hedno/unknown/` are weekly). The expected structure
above is unverified. Not needed for the current calibration window (see §4).

### 1b. HEDNO weekly operations reports 2025+ ("Απολογισμός λειτουργίας")

| Attribute | Value |
|-----------|-------|
| Publisher | HEDNO / ΔΕΔΔΗΕ |
| Frequency | Weekly (one PDF per calendar week) |
| Language | Greek |
| Format | PDF |
| Section in manifest | `weekly_actuals` |
| Known gap | Week 03–09/06/2025 — HEDNO marked unavailable due to technical problems |

**Observed layout** (verified 2026-11-02 and 2026-11-03 on the Astypalea weekly files, 2025-09-16 to 2026-10-19)

- Landscape A4, **one page per day, 7 pages per file**. `page.find_tables()` returns one main
  table (27 rows x 7 columns) plus an empty 2x1 legend table.
- Row 0: `ΗΣ ΑΣΤΥΠΑΛΑΙΑΣ` | `Απολογισμός\nΛειτουργίας` | date in Greek words, e.g.
  `Τρίτη, 2 Δεκεμβρίου 2025`. The date is the reliable source for the day; the rotated text in
  column 0 comes out reversed (`5202 υοίρβμεκεΔ`).
- Row 1: `Αποδιδόμενη Ισχύς (MW)` then `1,100` for each of G5 to G8. This is unit rating, not output.
- Row 2 (header): `Χρονική στιγμή` | `Πραγματικό\nΜέσο Ωριαίο\nΦορτίο (MW)` | `G5` `G6` `G7` `G8`.
- Rows 3 to 26: `00:00` to `23:00`, load with decimal comma (`0,433`), then one status cell per unit.
- **Every day has exactly 24 rows**, including the spring-forward day 2026-03-29 (see Q6).
- Unit cells contain only: blank, `1`, `S`, `B`, `s`, `b` (Latin letters, U+0053/0042/0073/0062).
  No per-unit MW output. Meaning of the letters is not in the legend (see Q2).
- Counts in `astypalea_hourly_actual.csv` (9,072 hours, Astypalea files only, 1 to 7 Sep 2026 not
  included): G5 `1`=3743; G6 `1`=3772 `S`=530 `s`=312 `B`=168; G7 `1`=4168 `S`=672 `B`=160 `b`=168;
  G8 blank throughout. G8 runs only in the 1 to 7 Sep 2026 file (`1` in all 168 hours).
  Correction 2026-11-03: the counts written here on 2026-11-02 (including "G8 = 222 hours")
  wrongly included a Symi report (G1 to G9 layout) filed under the Astypalea page.
- Free-text remarks sometimes appear below the table, between the last hour and the legend.
  Examples: telecom problems in the morning; `08:10 – 08:20 γενική διακοπή λόγω βλάβης στη μονάδα G7`
  (island-wide outage from a G7 fault); partial interruptions for planned network works.
- Legend at the bottom of each page: `Μη διαθεσιμότητα μονάδας λόγω συντήρησης` and
  `Μη διαθεσιμότητα μονάδας λόγω βλάβης`.

**Cell colours** (from `--rects`, page 1 of 02-12-2025_08-12-2025 and 07-07-2026_13-07-2026)

| Fill (RGB, pdfplumber) | Where | Meaning |
|------------------------|-------|---------|
| `(0.65, 0.65, 0.65)` grey | legend swatch | maintenance (συντήρηση) |
| `(0.15, 0.15, 0.15)` near-black | legend swatch | fault (βλάβη) |
| `(1.0, 0.78, 0.81)` pink, `#ffc6cd` | under every `1` cell (12,241 of 12,241) | not in legend; coincides exactly with "running" (Q8) |
| `(0.75, 0.75, 0.75)` light grey | under every `S` and `s` cell | not the legend swatch shade; pairs with S (Q2) |
| `(0.0, 0.0, 0.0)` black | under every `B` and `b` cell | not the legend swatch shade; pairs with B (Q2) |
| `(0.56, 0.67, 0.86)`, `(0.85, 0.89, 0.95)` blues | title row | decoration |

The earlier assumption "maintenance = yellow, fault = red" was wrong. `_color_to_status()` in
`03_parse_actual.py` must use the two legend greys, matched with a small tolerance, and report
any other fill over a unit cell as `unknown_color:#rrggbb` rather than guessing.

**Number format exception**: the file covering 01-09-2026 to 07-09-2026 prints load values
without a decimal separator (e.g. `117`, `95`). `parse_greek_number` turns these into 117 MW.
Parsers must flag values outside 0 to 5 MW rather than rescale them.

### 1c. HEDNO yearly proposed plans 2020–2024 ("Προτεινόμενοι")

Not downloaded yet; layout unverified.

### 1d. HEDNO weekly proposed plans 2025+ ("Προτεινόμενος-ΗΕΠ")

Verified 2026-11-02 (59 files). Same layout as §1b: one page per day, 27x7 table, same G5 to G8
columns and status letters. Differences: row 0 says `Προτεινόμενος\nΗΕΠ`, and the load column header
is `Πρόβλεψη Μέσου\nΩριαίου Φορτίου\n(MW)`. The file dated 03-12-2025 covers 03-12 to 09-12, so
forecast weeks start one day after the matching actual weeks.

### 1e. HEDNO monthly bulletins ("Πληροφοριακό Δελτίο")

- One PDF per month; covers all Non-Interconnected Islands.
- ΑΣΤΥΠΑΛΑΙΑ row identified by first-column match.
- Table numbers change between issues (e.g. Dec 2025: Table 3 and Table 12).
- `05_parse_bulletins.py` scans all tables to find the island row.
- Two tables hold Astypalea (verified Dec 2025, Mar 2026, Jul 2026; Table 3 on page 5 and
  Table 12 on page 13 in all three):
  - **Table 3, installed RES** (5 columns): name | wind MW | wind MWh | PV MW | PV MWh.
    Astypalea: wind 0, PV 0.32 MW, PV energy for the month.
  - **Table 12** (8 columns): name | installed thermal 2024 (MW) | **maximum annual peak demand
    2024 (MW)** | RES energy (MWh) | thermal energy (MWh) | ΜΠΚΠ (€/MWh) | ΜΜΚ (€/MWh) | RES share (%).
- The installed-capacity and peak columns are **2024 annual figures repeated every month**
  (5.100 MW and 2.550 MW in Dec 2025; peak shown as 2.510 in 2026 issues). They are not monthly values.
- The old `astypalea_monthly_hedno.csv` is shifted by one column (thermal_gen_mwh = 5.1, the
  installed capacity) and must be regenerated. Update §2c when the parser changes.
- Bulletin months found in `data/raw/bulletins/`: Jan 2025 to Aug 2026, mixed Greek, uppercase
  Greek and transliterated filenames.

### 1f. RAAEY tender XLS files (2024 projections)

Three Excel 97 (.xls) files; 8760 rows each; values in kW.
- `raaey_load_2024.xls` — hourly load projection
- `raaey_pv_2024.xls` — hourly PV generation projection
- `raaey_ev_2024.xls` — hourly EV charging demand projection

Published September 2022; labelled "2024" — appear to be projections.
Whether these are measured 2024 data or forecasts is tested in `06_qa.py`.

---

## 2. Column definitions

### 2a. `astypalea_hourly_actual.csv`

| Column | Type | Unit | Description |
|--------|------|------|-------------|
| `timestamp_local` | ISO 8601 string | — | Local Athens time (Europe/Athens). Suffix `?DST_AMBIGUOUS` = fall-back ambiguous hour. Suffix `+LOCAL_NONEXISTENT` = spring-forward non-existent hour. |
| `timestamp_utc` | ISO 8601 string | — | UTC equivalent. Empty if nonexistent local time. |
| `demand_mw` | float | MW | Actual hourly demand. NaN when `demand_flag` is set. From "Ζήτηση" (yearly) or "Πραγματικό Μέσο Ωριαίο Φορτίο" (weekly). Open question: is this total island demand or diesel station output net of existing PV? See §Open questions. |
| `demand_flag` | string | — | Empty when demand is valid. `dst_placeholder` = spring-forward 03:00 row (Q6). `no_decimal_separator` = value outside 0–5 MW, likely missing decimal (Q7). |
| `G5_on` | 0/1/NaN | — | 1 = unit running (`1` in cell), 0 = not running, NaN = unknown. |
| `G6_on` | 0/1/NaN | — | As above. |
| `G7_on` | 0/1/NaN | — | As above. |
| `G8_on` | 0/1/NaN | — | As above. |
| `units_on_count` | int/NaN | — | Sum of G5–G8 _on values (0–4). NaN if all units unknown. |
| `G5_status` | string | — | `on` / `available` / `maintenance_likely` / `fault_likely` / `unknown`. Derived from cell letter only (Q2). |
| `G6_status` | string | — | As above. |
| `G7_status` | string | — | As above. |
| `G8_status` | string | — | As above. |
| `G5_raw` | string | — | Raw cell letter from PDF (`1`, `S`, `s`, `B`, `b`, or blank). |
| `G6_raw` | string | — | As above. |
| `G7_raw` | string | — | As above. |
| `G8_raw` | string | — | As above. |
| `G5_fill` | string | — | Hex fill colour of cell (`#rrggbb`), or blank if no fill. Informational; status is derived from the letter, not this. |
| `G6_fill` | string | — | As above. |
| `G7_fill` | string | — | As above. |
| `G8_fill` | string | — | As above. |
| `source_file` | string | — | Filename of source PDF. |
| `page` | int | — | 1-indexed page number within source PDF. |
| `remark` | string | — | Free-text remarks extracted from below the day table (e.g. supply interruption details). |

### 2b. `astypalea_hourly_forecast.csv`

| Column | Type | Unit | Description |
|--------|------|------|-------------|
| `timestamp_local` | ISO 8601 | — | As above. |
| `timestamp_utc` | ISO 8601 | — | As above. |
| `forecast_demand_mw` | float | MW | Proposed/forecast hourly average demand. |
| `source_file` | string | — | Source PDF filename. |
| `page` | int | — | Page number. |

### 2c. `astypalea_monthly_hedno.csv`

| Column | Type | Unit | Description |
|--------|------|------|-------------|
| `year` | int | — | Calendar year. |
| `month` | int | — | Calendar month (1–12). |
| `bulletin_date` | string | — | As parsed from bulletin cover (e.g. "1/2025"). |
| `thermal_gen_mwh` | float | MWh | Monthly thermal (diesel) generation. From Table 12 col 4. |
| `res_gen_mwh` | float | MWh | Monthly RES (solar PV + wind) generation. From Table 12 col 3. |
| `total_gen_mwh` | float | MWh | Total generation = thermal + RES. Always derived (no explicit total in Table 12); see `notes`. |
| `res_share_pct` | float | % | RES as % of total generation. From Table 12 col 7. |
| `avg_prod_cost_eur_mwh` | float | €/MWh | ΜΠΚΠ_ΜΔΝ — average full production cost. From Table 12 col 5. See Q9. |
| `mmk_eur_mwh` | float | €/MWh | ΜΜΚ_ΜΔΝ — average variable cost. From Table 12 col 6. See Q9. |
| `peak_load_mw_2024` | float | MW | Maximum annual peak demand for 2024 — **repeated every month, not a monthly value**. From Table 12 col 2. |
| `installed_capacity_mw_2024` | float | MW | Installed thermal capacity for 2024 — **repeated every month, not a monthly value**. From Table 12 col 1. |
| `t3_pv_gen_mwh` | float | MWh | Monthly PV energy from Table 3 col 4 (installed RES table). Wind is 0 at Astypalea, so this equals total RES from Table 3. May differ slightly from `res_gen_mwh` (rounding/scope). |
| `source_bulletin` | string | — | Bulletin PDF filename. |
| `table_number` | int | — | Sequential table number within the bulletin PDF (restarts each PDF). Points to Table 12. |
| `page` | int | — | Page number within bulletin PDF. |
| `notes` | string | — | Caveats: derived columns, duplicate flags. |

### 2d. `astypalea_raaey_2024.csv`

| Column | Type | Unit | Description |
|--------|------|------|-------------|
| `timestamp_local` | ISO 8601 | — | Athens local time starting 2024-01-01T00:00 (sequential, no DST gap/overlap handling — the XLS has no timestamps). |
| `timestamp_utc` | ISO 8601 | — | UTC equivalent. |
| `load_kw` | float | kW | Hourly load from RAAEY load XLS. |
| `pv_gen_kw` | float | kW | Hourly PV generation from RAAEY PV XLS. |
| `ev_demand_kw` | float | kW | Hourly EV charging demand from RAAEY EV XLS. |
| `source_note` | string | — | Fixed provenance string. |

---

## 3. Open questions

These questions cannot be answered from the HEDNO PDF files alone.
They are carried into future HEDNO correspondence.

### Q1: What does "Ζήτηση" / hourly demand measure exactly?
Is it:
- (a) Total island demand including all loads?
- (b) Diesel station metered output only (net of existing ~0.32 MW PV installed before 2022)?

**Evidence so far (2026-11-02, confirmed 2026-11-03 with the pipeline output, full months only)**:

| Month | Sum of weekly hourly load (MWh) | Bulletin thermal (MWh) | Bulletin thermal + RES (MWh) |
|-------|------|------|------|
| 2025-11 | 347.5 | 323.14 (+7.5%) | 360.3 (-3.6%) |
| 2025-12 | 394.3 | 369.12 (+6.8%) | 397.9 (-0.9%) |
| 2026-03 | 416.5 | 391.76 (+6.3%) | 437.4 (-4.8%) |
| 2026-04 | 395.3 | 368.94 (+7.1%) | 416.9 (-5.2%) |
| 2026-05 | 461.3 | 454.05 (+1.6%) | 513.6 (-10.2%) |
| 2026-06 | 675.2 | 662.98 (+1.8%) | 728.5 (-7.3%) |
| 2026-07 | 1,095.5 | 1,104.52 (-0.8%) | 1,168.2 (-6.2%) |
| 2026-08 | 1,274.1 | 1,254.95 (+1.5%) | 1,317.2 (-3.3%) |

Summer months track thermal output; winter months sit between the two. Neither (a) nor (b)
fits every month. Do not resolve by assumption. Re-run with the pipeline output in `06_qa.py`
and ask HEDNO.

### Q2: What do the `1`, `S`, `B`, `s`, `b` cells mean in the G5 to G8 columns?
The columns are the four units. Cells hold blank, `1`, `S`, `B`, `s` or `b`. The legend only
explains two cell colours, not the letters. Patterns: `1` appears with load-consistent counts
(one unit at night in winter, two to three in summer); `S` often sits next to a single running
unit; lowercase `s` and `b` appear in whole-week runs (e.g. G7 `b` for 168 consecutive hours).

**Evidence added 2026-11-03**: every `S`/`s` cell has a light-grey fill and every `B`/`b` cell a
black fill, with no exceptions across all Astypalea files. The legend has exactly two categories,
maintenance (grey swatch) and fault (dark swatch), and S and B are the Latin forms of the Greek
initials of Συντήρηση (maintenance) and Βλάβη (fault). So the likely reading is **S = unavailable
for maintenance, B = unavailable due to fault**, not "standby". The fills are not the exact legend
shades (0.75 vs 0.65, 0.0 vs 0.15), and the meaning of lowercase vs uppercase is still unknown.

**Treatment until HEDNO answers**: `1` = on. Store S/s/B/b as `maintenance_likely` /
`fault_likely` from the letter, keep the raw letter and hex fill, and do not rely on the colour
tolerance alone. Models should run with both readings (letters mean unavailable / letters ignored).

### Q3: Installed thermal capacity — 4.4 MW or 5.1 MW?
HEDNO press releases and RAE filings elsewhere state ~5.1 MW installed thermal.
The PDF unit lists show G5, G6, G7, G8 × 1.1 MW = 4.4 MW.

Possible explanations:
- Units were upgraded or additional units (G9?) added and not yet in these files.
- Some units are "rented" or listed differently.
- 5.1 MW figure includes a fifth unit or a different name (MITSUBISHI S16-RPTA?).

**Evidence (2026-11-02, corrected 2026-11-03)**: bulletins list installed thermal 5.100 MW (2024).
Weekly reports list only G5 to G8 at 1.100 MW each. G8 runs only during 1 to 7 Sep 2026 (all 168
hours) and is blank everywhere else.

**Action**: Ask HEDNO for the current unit registry.

### Q4: Per-unit generation (MW) vs on/off
The files appear to show only on/off (binary), not MW output per unit.
Fuel curves, minimum stable load (MSL), and reserve requirements are not in these files.
These are needed for any dispatch model.

### Q5: Metering convention for weekly format
"Πραγματικό Μέσο Ωριαίο Φορτίο (MW)" = actual *average* hourly load.
This is an average over the hour, equivalent to MWh energy divided by 1h.
The yearly format "Ζήτηση (MWh)" is energy in the hour, numerically identical.
Both are treated as MW in the output. This should be confirmed with HEDNO.

### Q6: What clock are the hourly timestamps on?
**Partly answered 2026-11-03**: on 2026-03-29 the PDF prints a `03:00` row with load `0,000` and
no unit marked, between normal `02:00` and `04:00` rows. That is the nonexistent Athens hour, filled
with a zero placeholder. So the times are Athens wall-clock time, and the spring day has 23 real hours.
The fall-back days (2025-10-26, 2026-10-25) are not in the downloaded files, so the autumn convention
is still unknown.

**Treatment**: drop or set to NaN the `03:00` placeholder row on spring-forward days; never treat
its 0.0 as load. Flag fall-back days when they appear.

### Q7: Decimal-less values in one weekly file
01-09-2026 to 07-09-2026 prints load without a decimal comma (`117`, `95`). Likely 1.17 and
0.95 MW, but not confirmed. Flag these rows; do not rescale.

### Q8: Cell fills not in the legend (largely answered 2026-11-03)
Pink sits under every `1` cell, light grey under every `S`/`s`, black under every `B`/`b`. The
fills carry the same information as the letters. Pink can be read as "running"; the greys follow Q2.

### Q9: Bulletin cost columns
Table 12 has two cost columns, ΜΠΚΠ_ΜΔΝ and ΜΜΚ_ΜΔΝ (e.g. 845.31 and 353.02 €/MWh in Dec 2025).
Our reading is average full production cost and average variable cost; confirm the definitions
before using either in the techno-economics.

---

## 4. Known data issues

- **Downloaded coverage**: weekly actuals 2025-09-16 to 2026-10-19 only. No yearly 2020 to
  2024 files. The June 2025 gap below is outside this range.
- **Missing days inside that range** (as of 2026-11-03): 2025-10-21 to 2025-10-27 and 2026-01-27 to
  2026-02-02 (no file found). 2026-02-24 to 2026-03-02 was recovered on 2026-11-03; the Symi report
  with the same dates is correctly rejected. 2026-09-01 to 2026-09-07 is dropped by the parser because
  of the decimal-less values (Q7) and should be kept with flags instead.
- **Zero-load hours**: 2026-04-19 08:00 and 09:00 show 0.000 MW with no unit running; the remark
  records planned works 07:10 to 09:15. A real interruption, not a parse error. 2026-03-29 03:00 is
  the DST placeholder (Q6).
- **Hybrid not yet producing**: bulletin RES energy stays at 37 to 66 MWh a month through Aug 2026,
  in line with the 0.32 MW existing PV alone. Sep 2025 to Aug 2026 is effectively pre-hybrid.
- **Outage events in remarks**: remarks below the daily tables record interruptions (e.g. a
  general interruption 08:10 to 08:20 from a G7 fault). Useful for the outage history.
- **Week 03–09/06/2025**: HEDNO marked this week as unavailable due to technical problems.
  The corresponding weekly PDF either does not exist or is blank. Missing from coverage.
- **Island header mismatches**: Some PDFs on the Astypalea page carry another island's
  name (Σύμη, Αρκιοί documented in task spec). These are skipped in parsing
  (`island_confirmed_in_header = N` in manifest).
- **DST transitions**: assumption corrected 2026-11-02. The spring-forward day 2026-03-29 has 24
  rows, not 23. See Q6.
- **Overlapping weekly files**: If two weekly PDFs cover the same day (e.g. from end-of-year
  boundary), duplicates are kept and flagged as `DUPLICATE_CONFLICT` in the remark column
  when demand values disagree.

---

## 5. Revision log

| Date | What changed |
|------|-------------|
| 2026-11-03 | §2a: added demand_flag, Gx_fill cols; status vocab updated to maintenance_likely/fault_likely; Corrected unit counts and G8 claim (earlier count included a Symi file); Q2 letter/fill evidence; Q6 spring DST answered; Q8 largely answered; Q1 March row; §4 coverage, recovered week, dropped Sep 2026 week, zero-load hours |
| 2026-11-02 | Weekly actual and proposed layouts, bulletin columns and legend colours verified; Q1 evidence table, Q2 and Q3 updated; Q6 to Q9 added; §4 coverage, DST and missing days corrected |
| (today) | Initial template created |

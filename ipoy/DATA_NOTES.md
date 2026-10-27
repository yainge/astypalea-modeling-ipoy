# DATA_NOTES.md — Astypalea iPOY Dataset Reference

This file documents every column in the processed CSVs, the source PDF layouts
as observed, and all open questions that these files cannot resolve.

**Last updated**: after running 02_inspect.py on representative PDFs.
**Status**: Template — sections marked `[TODO: verify after inspection]`
must be filled in after running `02_inspect.py` and examining the actual PDFs.

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

**Observed layout** `[TODO: fill in after inspection]`

Expected structure (from task spec; verify with 02_inspect.py):
- One block per day.  Header line: weekday + date + "Απολογιστική λειτουργία ΗΣ Αστυπάλαιας".
- Table columns: hours 0–23 plus ΣΥΝΟΛΟ (daily total).
- Row "Ζήτηση" = hourly energy in MWh.  Because each interval is 1 h, MWh = MW numerically.
- Unit rows (G5, G6, G7, G8, MITSUBISHI S16-RPTA): "1" when running, "Διαθέσιμη" (= available,
  not running) otherwise.
- Free-text remarks sometimes appear below a table (e.g. "Διακοπή 07:30–10:00 λόγω εργασιών δικτύου").

**Record of actual observations** `[TODO after inspection]`:
- Number of tables per page:
- Hour column header labels (exact strings):
- Unit row labels (exact strings):
- Colour usage for unit status:
- Remarks format:
- Any layout changes between 2020–2024 yearly files:

### 1b. HEDNO weekly operations reports 2025+ ("Απολογισμός λειτουργίας")

| Attribute | Value |
|-----------|-------|
| Publisher | HEDNO / ΔΕΔΔΗΕ |
| Frequency | Weekly (one PDF per calendar week) |
| Language | Greek |
| Format | PDF |
| Section in manifest | `weekly_actuals` |
| Known gap | Week 03–09/06/2025 — HEDNO marked unavailable due to technical problems |

**Observed layout** `[TODO: fill in after inspection]`

Expected structure:
- One table per day, 7 per file.
- Row headers: "00:00", "01:00", ..., "23:00".
- Column "Πραγματικό Μέσο Ωριαίο Φορτίο (MW)" = actual average hourly load.
- Unit columns G5–G8: "Αποδιδόμενη Ισχύς (MW)" header; cell values in the range 0–1.1.
- Mystery cells showing "1" or "b" — meaning unknown (see §Open questions).
- Legend mentions cell colour = maintenance (συντήρηση) vs fault (βλάβη) — colour lost in text extraction.

**Cell colour colours** `[TODO: run 02_inspect.py --rects]`

| Color (RGB/CMYK from pdfplumber) | Observed meaning |
|----------------------------------|-----------------|
| `[TODO]` | maintenance (συντήρηση) |
| `[TODO]` | fault (βλάβη) |

Update `_color_to_status()` in `03_parse_actual.py` once verified.

### 1c. HEDNO yearly proposed plans 2020–2024 ("Προτεινόμενοι")

`[TODO: verify layout after inspection — expected similar to yearly actuals
but with forecast/proposed demand column instead of actual "Ζήτηση"]`

### 1d. HEDNO weekly proposed plans 2025+ ("Προτεινόμενος-ΗΕΠ")

`[TODO: verify layout after inspection — expected similar to weekly actuals
but column labelled "Προτεινόμενο Μέσο Ωριαίο Φορτίο" or similar]`

### 1e. HEDNO monthly bulletins ("Πληροφοριακό Δελτίο")

- One PDF per month; covers all Non-Interconnected Islands.
- ΑΣΤΥΠΑΛΑΙΑ row identified by first-column match.
- Table numbers change between issues (e.g. Dec 2025: Table 3 and Table 12).
- `05_parse_bulletins.py` scans all tables to find the island row.

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
| `demand_mw` | float | MW | Actual hourly demand. From "Ζήτηση" (yearly) or "Πραγματικό Μέσο Ωριαίο Φορτίο" (weekly). MWh and MW are numerically identical for 1-h intervals. Open question: is this total island demand or diesel station output net of existing PV? See §Open questions. |
| `G5_on` | 0/1/NaN | — | 1 = unit running, 0 = available/off, NaN = unknown. |
| `G6_on` | 0/1/NaN | — | As above. |
| `G7_on` | 0/1/NaN | — | As above. |
| `G8_on` | 0/1/NaN | — | As above. |
| `units_on_count` | int/NaN | — | Sum of G5–G8 _on values (0–4). NaN if all units unknown. |
| `G5_status` | string | — | `on` / `available` / `maintenance` / `fault` / `unknown` / `unknown_color:#rrggbb` |
| `G6_status` | string | — | As above. |
| `G7_status` | string | — | As above. |
| `G8_status` | string | — | As above. |
| `G5_raw` | string | — | Raw cell text as extracted from PDF (before interpretation). Useful for debugging. |
| `G6_raw` | string | — | As above. |
| `G7_raw` | string | — | As above. |
| `G8_raw` | string | — | As above. |
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
| `bulletin_date` | string | — | As parsed from bulletin cover (e.g. "1/2024"). |
| `thermal_gen_mwh` | float | MWh | Monthly thermal (diesel) generation. |
| `res_gen_mwh` | float | MWh | Monthly RES (solar PV + wind if any) generation. |
| `total_gen_mwh` | float | MWh | Total generation = thermal + RES. May be derived if not explicitly stated; see `notes`. |
| `res_share_pct` | float | % | RES as % of total generation. |
| `avg_prod_cost_eur_mwh` | float | €/MWh | ΜΠΚΠ — average production cost. |
| `peak_load_mw` | float | MW | Monthly peak demand. Not always available. |
| `installed_capacity_mw` | float | MW | Total installed capacity. Not always available. |
| `source_bulletin` | string | — | Bulletin PDF filename. |
| `table_number` | int | — | Sequential table number within the bulletin PDF (restarts each PDF). |
| `page` | int | — | Page number within bulletin PDF. |
| `notes` | string | — | Caveats: derived columns, duplicate flags, missing column warnings. |

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

**Evidence**: If the monthly hourly sum is consistently `≈X%` lower than bulletin
`total_gen_mwh` (thermal + RES), and `X` is proportional to estimated PV output, this
suggests (b). See QA_report.md §3 for the actual numbers.

### Q2: What do the "1" and "b" cells mean in weekly report unit columns?
The weekly format tables have extra columns whose headers are unclear, and cells
contain "1" or "b". A legend references maintenance/fault via cell colour.

**Current treatment**: "1" is tentatively mapped to unit "on"; "b" is stored as
`unit_raw_{name}` and `G*_on = None`, `G*_status = unknown`. Verify by comparing
with days where the legend explicitly marks a unit.

### Q3: Installed thermal capacity — 4.4 MW or 5.1 MW?
HEDNO press releases and RAE filings elsewhere state ~5.1 MW installed thermal.
The PDF unit lists show G5, G6, G7, G8 × 1.1 MW = 4.4 MW.

Possible explanations:
- Units were upgraded or additional units (G9?) added and not yet in these files.
- Some units are "rented" or listed differently.
- 5.1 MW figure includes a fifth unit or a different name (MITSUBISHI S16-RPTA?).

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

---

## 4. Known data issues

- **Week 03–09/06/2025**: HEDNO marked this week as unavailable due to technical problems.
  The corresponding weekly PDF either does not exist or is blank. Missing from coverage.
- **Island header mismatches**: Some PDFs on the Astypalea page carry another island's
  name (Σύμη, Αρκιοί documented in task spec). These are skipped in parsing
  (`island_confirmed_in_header = N` in manifest).
- **DST transitions**: Spring-forward days have 23 hourly rows; fall-back days have 25
  (or 24 if the operator blended the repeated hour). Flagged in `timestamp_local`.
- **Overlapping weekly files**: If two weekly PDFs cover the same day (e.g. from end-of-year
  boundary), duplicates are kept and flagged as `DUPLICATE_CONFLICT` in the remark column
  when demand values disagree.

---

## 5. Revision log

| Date | What changed |
|------|-------------|
| (today) | Initial template created |
| `[TODO]` | Layout observations filled in after running 02_inspect.py |
| `[TODO]` | Cell colour mapping verified for weekly format |

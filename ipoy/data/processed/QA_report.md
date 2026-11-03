# Astypalea iPOY — Data Quality Report

Generated: 2026-11-03 02:50

---

## 1. Coverage per year

| Year | Hours present | Expected | Coverage % | Missing dates | Annual MWh | Peak MW | Peak timestamp |
|------|-------------|----------|------------|---------------|-----------|---------|----------------|
| 2025 | 2402 | 8760 | 27.4 | 263 | 1386.8 | 1.324 | 2025-09-16T17:00:00+00:00 |
| 2026 | 6669 | 8760 | 76.1 | 85 | 5902.5 | 2.494 | 2026-08-11T17:00:00+00:00 |

### Missing dates (first 10 per year)
- **2025**: 2025-01-01; 2025-01-02; 2025-01-03; 2025-01-04; 2025-01-05; 2025-01-06; 2025-01-07; 2025-01-08; 2025-01-09; 2025-01-10
- **2026**: 2026-01-27; 2026-01-28; 2026-01-29; 2026-01-30; 2026-01-31; 2026-02-01; 2026-09-01; 2026-09-02; 2026-09-03; 2026-09-04

---

## 2. Sanity checks

- ⚠ Zero demand_mw: 2 rows
- ⚠ Flat-line runs ≥ 6 h: 1 rows

---

## 3. Monthly hourly sum vs bulletin total

| Year | Month | Hourly sum (MWh) | Bulletin total (MWh) | Diff % |
|------|-------|-----------------|---------------------|--------|
| 2025 | 9 | 310.5 | 741.59 | -58.1 |
| 2025 | 10 | 334.3 | 449.46 | -25.6 |
| 2025 | 11 | 347.5 | 360.26 | -3.6 |
| 2025 | 12 | 394.6 | 397.91 | -0.8 |
| 2026 | 1 | 373.1 | 441.33 | -15.5 |
| 2026 | 2 | 353.9 | 393.01 | -9.9 |
| 2026 | 3 | 416.9 | 437.36 | -4.7 |
| 2026 | 4 | 395.2 | 416.92 | -5.2 |
| 2026 | 5 | 462.0 | 513.61 | -10.1 |
| 2026 | 6 | 676.8 | 728.48 | -7.1 |
| 2026 | 7 | 1096.3 | 1168.23 | -6.2 |
| 2026 | 8 | 1269.7 | 1317.16 | -3.6 |
| 2026 | 9 | 571.4 | nan | nan |
| 2026 | 10 | 287.3 | nan | nan |

Mean diff: -12.5%,  median: -6.7%,  max absolute: 58.1%

**Interpretation note**: If hourly 'demand_mw' is consistently lower than bulletin 'total_gen_mwh' by a small fraction (e.g. ~3-5%), this may indicate that hourly demand is net of existing PV generation (≈0.32 MW installed before 2022), while the bulletin reports station output only. A consistent positive gap would suggest the opposite or a scale error. See DATA_NOTES.md §Open questions.

---

## 4. RAAEY tender 2024 vs HEDNO actual 2024

No HEDNO actual 2024 data available for comparison

---

## 5. DST handling notes

- 2025 spring-forward 2025-03-30: 0 rows (expected 23) ⚠ UNEXPECTED
- 2025 fall-forward 2025-10-26: 0 rows (expected 25) ⚠ UNEXPECTED
- 2026 spring-forward 2026-03-29: 24 rows (expected 23)
- 2026 fall-forward 2026-10-25: 0 rows (expected 25) ⚠ UNEXPECTED

---

## 6. Figures

Generated in `data/processed/figures/`:

- `heatmap_{year}.png` — load heatmap (day of year × hour)
- `monthly_energy.png` — hourly sum vs bulletin total per month
- `seasonal_profiles.png` — mean daily load profile by season
- `tender_vs_actual_2024.png` — RAAEY tender vs HEDNO actual 2024

# iPOY — Island Power & Operations Yearly

Hourly energy system data pipeline and scenario models for the Astypalea isolated grid.

---

## Part 1: HEDNO data pipeline (active)

Downloads, parses, and quality-checks every public HEDNO operations report for
Astypalea (2020 – present), producing a clean hourly CSV dataset.

### Quick start

```bash
cd ipoy/
bash scripts/run_all.sh
```

This will:
1. Create a virtual environment and install dependencies
2. Scrape the HEDNO Astypalea planning page and download all PDFs
3. Parse actual operations reports → `data/processed/astypalea_hourly_actual.csv`
4. Parse forecast reports + RAAEY XLS → `data/processed/astypalea_hourly_forecast.csv`
5. Parse monthly bulletins → `data/processed/astypalea_monthly_hedno.csv`
6. Run QA checks → `data/processed/QA_report.md` and figures

Re-running is safe: downloaded files are cached and CSVs are overwritten.

### Manual setup (if not using run_all.sh)

```bash
cd ipoy/
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### Script reference

| Script | Purpose |
|--------|---------|
| `01_download.py` | Scrape HEDNO + bulletins pages; download all PDFs + RAAEY XLS; write `data/raw/manifest.csv` |
| `02_inspect.py` | **Dev tool** — inspect a PDF's text, tables, and cell colours; optionally render a page to PNG |
| `03_parse_actual.py` | Parse yearly (2020–2024) and weekly (2025+) actual reports → hourly CSV |
| `04_parse_forecast.py` | Parse forecast PDFs + RAAEY XLS → forecast CSV + RAAEY CSV |
| `05_parse_bulletins.py` | Extract ΑΣΤΥΠΑΛΑΙΑ rows from monthly bulletins → monthly CSV |
| `06_qa.py` | Coverage, sanity, bulletin comparison, tender-vs-actual comparison, 4 figures |

### Inspecting PDF layouts (important step)

Before running the full pipeline for the first time, inspect 2–3 representative
PDFs to verify that the parser assumptions in `03_parse_actual.py` match the
actual table structure, and fill in the `[TODO]` sections in `DATA_NOTES.md`.

```bash
# Show text + tables of first 2 pages of the 2024 yearly report
python scripts/02_inspect.py \
  data/raw/hedno/yearly_actuals/απολογισμοί-αστυπάλαιας-2024.pdf \
  --pages 1-2 --tables

# Show coloured rectangles (for cell-background status detection in weekly files)
python scripts/02_inspect.py \
  "data/raw/hedno/weekly_actuals/Αστυπάλαια_Απολογισμός-λειτουργίας_Δημοσίευση_13-10-2026_19-10-2026.pdf" \
  --pages 1 --tables --rects

# Render page 1 to PNG for visual inspection
python scripts/02_inspect.py \
  "data/raw/hedno/weekly_actuals/<filename>.pdf" \
  --render 1
# → output: data/processed/figures/<stem>_p1.png
```

### Dependency order

```
01_download.py
       ↓
03_parse_actual.py   04_parse_forecast.py   05_parse_bulletins.py
                        (any order)
       ↓
06_qa.py
```

### Output files

| File | Description |
|------|-------------|
| `data/raw/manifest.csv` | Every downloaded file: URL, local path, section, SHA256, island confirmed |
| `data/processed/astypalea_hourly_actual.csv` | One row per hour; demand_mw + unit on/off/status |
| `data/processed/astypalea_hourly_forecast.csv` | One row per hour; forecast_demand_mw |
| `data/processed/astypalea_monthly_hedno.csv` | Monthly totals from bulletins |
| `data/processed/astypalea_raaey_2024.csv` | RAAEY 2024 tender projections (load, PV, EV) in kW |
| `data/processed/QA_report.md` | Coverage, sanity issues, bulletin comparison, RAAEY comparison |
| `data/processed/figures/heatmap_{year}.png` | Load heatmap (day × hour) per year |
| `data/processed/figures/monthly_energy.png` | Hourly sum vs bulletin total per month |
| `data/processed/figures/seasonal_profiles.png` | Mean daily profiles by season |
| `data/processed/figures/tender_vs_actual_2024.png` | RAAEY vs HEDNO actual 2024 by season |

### Data sources

| Source | URL | Type |
|--------|-----|------|
| HEDNO Astypalea planning | https://www.deddie.gr/en/services/non-interconnected-islands/publication-of-nii-daily-energy-planning-data/astypalaia-es/ | Scraped |
| HEDNO monthly bulletins | https://www.deddie.gr/en/services/non-interconnected-islands/monthly-reports-of-res-and-thermal-units-in-the-non-interconnected-islands/ | Scraped |
| RAAEY tender files 2024 | See `scripts/01_download.py` RAAEY_FILES dict | Direct URL |

### Open questions

See `DATA_NOTES.md §3` for the full list. Key unknowns:
- Is `demand_mw` total island demand or diesel station output net of PV?
- What do "1" and "b" cells mean in the weekly unit columns?
- Are there more than 4 units (4.4 MW) in the thermal fleet?
- Do the RAAEY 2024 files contain measured data or projections?

---

## Part 2: iPOY scenario models (placeholder)

iPOY will model the island's energy system at hourly resolution over a full year,
enabling simulation of different resilience and transition scenarios:

- **Baseline**: Current system (diesel generation dominant, ~8-9% solar penetration)
- **Transition**: PPC 3.5 MW solar + 14.12 MWh BESS online
- **High-EV**: Full fleet electrification (84+ EVs, smart charging)
- **Full renewable**: High solar + BESS + demand response, minimal diesel

Key modeling outputs:
- Hourly load vs. generation balance
- Diesel fuel consumption and CO₂ emissions per scenario
- Battery state of charge (SoC) time series
- Renewable energy curtailment
- Grid resilience metrics (frequency, reserve margin)

**Status: Placeholder — not yet implemented.**

The HEDNO data pipeline (Part 1) provides the measured hourly load baseline that
will feed the scenario models.

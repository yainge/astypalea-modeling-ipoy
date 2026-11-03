"""
04_parse_forecast.py — Parse HEDNO forecast PDFs and RAAEY XLS tender files.

Forecast PDFs (sections yearly_forecasts, weekly_forecasts) use the same
two layouts as the actual reports but the key demand column is labelled
differently — "Προτεινόμενο Μέσο Ωριαίο Φορτίο" or "Πρόβλεψη Ζήτησης"
(exact names verified in DATA_NOTES.md after inspection).

RAAEY XLS files (raaey/ directory) are Excel workbooks with 8760 rows of
hourly kW values for year 2024. They are projections published Sept 2022.

Outputs:
  data/processed/astypalea_hourly_forecast.csv  (HEDNO forecast data)
  data/processed/astypalea_raaey_2024.csv        (RAAEY tender projections)
"""
import csv
import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from utils import (
    DATA_PROCESSED, DATA_RAW,
    make_timestamps, parse_greek_number, setup_dirs, setup_logging,
)


def _strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    ).upper()

log = setup_logging("parse_forecast")

FORECAST_OUTPUT_COLS = [
    "timestamp_local", "timestamp_utc", "forecast_demand_mw",
    "source_file", "page",
]

RAAEY_OUTPUT_COLS = [
    "timestamp_local", "timestamp_utc",
    "load_kw", "pv_gen_kw", "ev_demand_kw",
    "source_note",
]

# ── HEDNO forecast PDFs ────────────────────────────────────────────────────────

# Column keywords that indicate the forecast demand column in weekly-format PDFs
_FORECAST_DEMAND_COL_KEYWORDS = (
    "ΠΡΟΤΕΙΝΟΜΕΝ",      # Προτεινόμενο Μέσο Ωριαίο Φορτίο
    "ΠΡΟΒΛΕΨΗ",          # Πρόβλεψη Ζήτησης
    "ΜΕΣΟ ΩΡΙΑΙΟ",      # fallback (overlaps with actuals; checked after actuals)
)

# Row keyword for yearly-format forecast PDFs
_FORECAST_DEMAND_ROW_KEYWORD = "ΖΗΤΗΣΗ"   # same label as actuals in yearly format


def _find_forecast_col(header_row: list) -> int | None:
    for ci, cell in enumerate(header_row):
        s = _strip_accents(str(cell or ""))
        if any(kw in s for kw in _FORECAST_DEMAND_COL_KEYWORDS):
            return ci
    return None


def _parse_demand_row(label_keywords: tuple[str, ...], table: list[list]) -> int | None:
    for ri, row in enumerate(table):
        for cell in row:
            s = str(cell or "").upper()
            if any(k in s for k in label_keywords):
                return ri
    return None


def parse_forecast_page_weekly(
    table: list[list],
    date_iso: str,
    source_file: str,
    page_num: int,
) -> list[dict]:
    """Parse one page from a weekly forecast PDF (tall format)."""
    rows: list[dict] = []
    if not table:
        return rows

    # Find header and demand column
    demand_col = None
    header_ri = None
    for ri, row in enumerate(table):
        ci = _find_forecast_col(row)
        if ci is not None:
            demand_col = ci
            header_ri = ri
            break

    if demand_col is None:
        return rows

    import re as _re
    _HOUR_RE = _re.compile(r"^(\d{1,2}):00")
    for ri, row in enumerate(table):
        if ri == header_ri or not row:
            continue
        # Col 1 is the time "HH:00"; col 0 is the rotated day label (DATA_NOTES §1d)
        time_str = str(row[1] or "").strip() if len(row) > 1 else ""
        m = _HOUR_RE.match(time_str)
        if not m:
            continue
        hour = int(m.group(1))
        val = parse_greek_number(str(row[demand_col] or ""))
        ts_local, ts_utc = make_timestamps(date_iso, hour)
        rows.append({
            "timestamp_local": ts_local,
            "timestamp_utc": ts_utc,
            "forecast_demand_mw": val,
            "source_file": source_file,
            "page": page_num + 1,
        })
    return rows


def _find_hour_column_map_local(header_row: list) -> dict[int, int]:
    """Map column-index → hour (0-23) from a wide-format header row (local copy)."""
    import re as _re
    mapping: dict[int, int] = {}
    for ci, cell in enumerate(header_row):
        if cell is None:
            continue
        s = str(cell).strip().rstrip(":ηη").split(":")[0].strip()
        s = _re.sub(r"[^\d]", "", s)
        try:
            h = int(s)
            if 0 <= h <= 23:
                mapping[ci] = h
        except ValueError:
            pass
    return mapping


def parse_forecast_page_yearly(
    table: list[list],
    date_iso: str,
    source_file: str,
    page_num: int,
) -> list[dict]:
    """Parse one page from a yearly forecast PDF (wide format)."""
    _find_hour_column_map = _find_hour_column_map_local
    rows: list[dict] = []
    hour_map: dict[int, int] = {}
    for ri, row in enumerate(table):
        m = _find_hour_column_map(row)
        if len(m) >= 20:
            hour_map = m
            break

    demand_ri = _parse_demand_row((_FORECAST_DEMAND_ROW_KEYWORD,), table)
    if not hour_map or demand_ri is None:
        return rows

    demand_row = table[demand_ri]
    for ci, hour in sorted(hour_map.items()):
        val = parse_greek_number(str(demand_row[ci] or ""))
        ts_local, ts_utc = make_timestamps(date_iso, hour)
        rows.append({
            "timestamp_local": ts_local,
            "timestamp_utc": ts_utc,
            "forecast_demand_mw": val,
            "source_file": source_file,
            "page": page_num + 1,
        })
    return rows


def parse_forecast_pdf(pdf_path: Path) -> list[dict]:
    """Auto-detect format and parse a forecast PDF."""
    import importlib.util
    import pdfplumber

    # Load helpers from 03_parse_actual.py without requiring it to be a package
    _spec = importlib.util.spec_from_file_location(
        "parse_actual", Path(__file__).parent / "03_parse_actual.py"
    )
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    detect_format = _mod.detect_format
    _extract_date_from_page_text = _mod._extract_date_from_page_text
    _date_from_table_row0 = _mod._date_from_table_row0

    fmt = detect_format(pdf_path)
    records: list[dict] = []
    fname = pdf_path.name

    with pdfplumber.open(pdf_path) as pdf:
        for pi, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            tables = page.extract_tables()

            # Extract date from table row 0 first (Greek month words, DATA_NOTES §1d)
            date_iso = None
            for tdata in tables:
                if tdata:
                    d = _date_from_table_row0(tdata)
                    if d:
                        date_iso = d
                        break
            # Fallback: DD/MM/YYYY in page text
            if not date_iso:
                date_iso = _extract_date_from_page_text(text)
            if not date_iso:
                continue

            for tdata in tables:
                if fmt == "weekly":
                    recs = parse_forecast_page_weekly(tdata, date_iso, fname, pi)
                else:
                    recs = parse_forecast_page_yearly(tdata, date_iso, fname, pi)
                if recs:
                    records.extend(recs)
                    break

    log.info(f"  {fname}: {len(records)} forecast rows")
    return records


# ── RAAEY XLS files ────────────────────────────────────────────────────────────

_RAAEY_YEAR = 2024
_RAAEY_START = f"{_RAAEY_YEAR}-01-01"  # 8760 hours from 00:00 Jan 1


def _raaey_timestamps(n_rows: int) -> list[tuple[str, str]]:
    """Generate (timestamp_local, timestamp_utc) for n_rows hours from Jan 1 2024."""
    from datetime import datetime, timedelta
    import pytz

    athens = pytz.timezone("Europe/Athens")
    base = datetime(_RAAEY_YEAR, 1, 1, 0, 0, 0)
    stamps = []
    for i in range(n_rows):
        naive = base + timedelta(hours=i)
        try:
            local = athens.localize(naive, is_dst=None)
        except Exception:
            local = athens.localize(naive, is_dst=True)
        from datetime import timezone
        utc = local.astimezone(timezone.utc)
        stamps.append((local.isoformat(), utc.isoformat()))
    return stamps


def load_raaey_xls(xls_path: Path) -> pd.Series:
    """Load a RAAEY wide-format XLS and return a numeric Series (8760 hourly values).

    The file has one row per day and 24 hourly columns (01:00–24:00), with
    two header rows (title + column labels) before the data.
    """
    try:
        df = pd.read_excel(xls_path, header=None, engine="xlrd")
    except Exception:
        df = pd.read_excel(xls_path, header=None, engine="openpyxl")

    # Find the first numeric data row (after the title and header rows)
    first_data = None
    for i, row in df.iterrows():
        # Data rows have a date-like value in col 0 and numbers in cols 1+
        if pd.to_numeric(df.iloc[i, 1:], errors="coerce").notna().sum() >= 20:
            first_data = i
            break

    if first_data is None:
        log.warning(f"Could not locate data rows in {xls_path.name}")
        return pd.Series(dtype=float)

    # Hour columns are 1–24 (index cols 1 to 24)
    hour_data = df.iloc[first_data:, 1:25]
    hour_data = hour_data.apply(pd.to_numeric, errors="coerce")

    # Flatten row-by-row: each row is one day, cols are hours 1–24
    values = hour_data.values.flatten()
    series = pd.Series(values).dropna().reset_index(drop=True)
    return series


def parse_raaey() -> list[dict]:
    raaey_dir = DATA_RAW / "raaey"
    load_file = raaey_dir / "raaey_load_2024.xls"
    pv_file = raaey_dir / "raaey_pv_2024.xls"
    ev_file = raaey_dir / "raaey_ev_2024.xls"

    missing = [f for f in (load_file, pv_file, ev_file) if not f.exists()]
    if missing:
        log.error(
            f"Missing RAAEY files: {[f.name for f in missing]}. "
            "Run 01_download.py first."
        )
        return []

    load_s = load_raaey_xls(load_file)
    pv_s = load_raaey_xls(pv_file)
    ev_s = load_raaey_xls(ev_file)

    n = len(load_s)
    log.info(f"RAAEY load: {n} rows, PV: {len(pv_s)}, EV: {len(ev_s)}")
    if n not in (8760, 8784):
        log.warning(f"Unexpected row count {n} in RAAEY load file (expected 8760 or 8784)")

    stamps = _raaey_timestamps(n)
    rows: list[dict] = []
    for i, (ts_local, ts_utc) in enumerate(stamps):
        rows.append({
            "timestamp_local": ts_local,
            "timestamp_utc": ts_utc,
            "load_kw": float(load_s.iloc[i]) if i < len(load_s) else None,
            "pv_gen_kw": float(pv_s.iloc[i]) if i < len(pv_s) else None,
            "ev_demand_kw": float(ev_s.iloc[i]) if i < len(ev_s) else None,
            "source_note": (
                "RAAEY tender 2024 projections (published Sept 2022); "
                "values in kW; assumed to be hourly averages"
            ),
        })
    return rows


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    setup_dirs()

    # ── HEDNO forecast PDFs ────────────────────────────────────────────────────
    manifest = DATA_RAW / "manifest.csv"
    forecast_records: list[dict] = []

    if manifest.exists():
        with open(manifest, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row["section"] not in ("yearly_forecasts", "weekly_forecasts"):
                    continue
                if row.get("island_confirmed_in_header") == "N":
                    log.warning(f"Skipping {row['local_path']} (island_confirmed=N)")
                    continue
                lp = row.get("local_path", "")
                if not lp:
                    continue
                p = DATA_RAW.parent.parent / lp
                if p.exists():
                    try:
                        forecast_records.extend(parse_forecast_pdf(p))
                    except Exception as exc:
                        log.error(f"ERROR parsing {p.name}: {exc}", exc_info=True)
    else:
        log.warning("manifest.csv not found; skipping HEDNO forecast PDFs")

    if forecast_records:
        forecast_records.sort(key=lambda r: r["timestamp_local"])
        out = DATA_PROCESSED / "astypalea_hourly_forecast.csv"
        with open(out, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FORECAST_OUTPUT_COLS, extrasaction="ignore")
            w.writeheader()
            w.writerows(forecast_records)
        log.info(f"Forecast CSV → {out}  ({len(forecast_records)} rows)")
    else:
        log.warning("No forecast records extracted")

    # ── RAAEY XLS ─────────────────────────────────────────────────────────────
    raaey_records = parse_raaey()
    if raaey_records:
        out_r = DATA_PROCESSED / "astypalea_raaey_2024.csv"
        with open(out_r, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=RAAEY_OUTPUT_COLS, extrasaction="ignore")
            w.writeheader()
            w.writerows(raaey_records)
        log.info(f"RAAEY CSV → {out_r}  ({len(raaey_records)} rows)")

        # Sanity check
        df = pd.DataFrame(raaey_records)
        log.info(f"  RAAEY load (kW): mean={df['load_kw'].mean():.1f}, "
                 f"max={df['load_kw'].max():.1f}, "
                 f"annual={df['load_kw'].sum()/1e6:.2f} GWh")


if __name__ == "__main__":
    main()

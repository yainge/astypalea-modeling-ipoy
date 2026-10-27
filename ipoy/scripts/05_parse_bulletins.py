"""
05_parse_bulletins.py — Extract ΑΣΤΥΠΑΛΑΙΑ rows from HEDNO monthly bulletins.

Each monthly bulletin ("Πληροφοριακό Δελτίο") contains tables covering
all Non-Interconnected Islands. Table numbers shift between issues.
Strategy: scan every table in every page, find rows whose first cell
matches "ΑΣΤΥΠΑΛΑΙΑ" (fuzzy), and extract the numeric columns.

Known columns from the Dec 2025 bulletin (Table 3 / Table 12):
  - Thermal generation (MWh)
  - RES generation (MWh)
  - Total generation = thermal + RES
  - RES share (%)
  - Average production cost ΜΠΚΠ (€/MWh)
  - Peak load (MW)  — not always present

Column indices are detected by header keywords, not hardcoded.

Output: data/processed/astypalea_monthly_hedno.csv
"""
import csv
import re
import sys
from pathlib import Path

import pdfplumber

sys.path.insert(0, str(Path(__file__).parent))
from utils import DATA_PROCESSED, DATA_RAW, parse_greek_number, setup_dirs, setup_logging

log = setup_logging("parse_bulletins")

OUTPUT_COLS = [
    "year", "month", "bulletin_date",
    "thermal_gen_mwh", "res_gen_mwh", "total_gen_mwh",
    "res_share_pct", "avg_prod_cost_eur_mwh", "peak_load_mw",
    "installed_capacity_mw",
    "source_bulletin", "table_number", "page", "notes",
]

# Keywords in table headers that identify each column type
_COL_KEYWORDS: dict[str, list[str]] = {
    "thermal_gen_mwh": ["ΘΕΡΜ", "ΘΕΡΜΙΚ", "ΣΥΜΒΑΤΙΚ"],
    "res_gen_mwh": ["ΑΠΕ", "ΦΒ", "ΑΝΑΝΕΩΣ"],
    "total_gen_mwh": ["ΣΥΝΟΛ", "ΠΑΡΑΓΩΓΗ"],
    "res_share_pct": ["ΜΕΡΙΔΙΟ", "ΠΟΣΟΣΤ", "%"],
    "avg_prod_cost_eur_mwh": ["ΜΠΚΠ", "ΚΟΣΤΟΣ", "€/MWh", "EUR/MWH"],
    "peak_load_mw": ["ΑΙΧΜΗ", "ΜΕΓΙΣΤΟ ΦΟΡΤ", "PEAK"],
    "installed_capacity_mw": ["ΕΓΚΑΤΕΣΤ", "ΙΣΧΥΣ"],
}

_ISLAND_RE = re.compile(r"ΑΣΤΥΠΑΛΑΙ", re.IGNORECASE)
_MONTH_GR = {
    "ΙΑΝΟΥ": 1, "ΦΕΒ": 2, "ΜΑΡΤ": 3, "ΑΠΡΙ": 4, "ΜΑΪΟ": 5, "ΜΑΪ": 5,
    "ΙΟΥΝ": 6, "ΙΟΥΛ": 7, "ΑΥΓΟ": 8, "ΣΕΠΤ": 9, "ΟΚΤΩ": 10, "ΝΟΕΜ": 11,
    "ΔΕΚΕ": 12,
}
_MONTH_EN = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}


def _parse_bulletin_date(text: str) -> tuple[int | None, int | None, str]:
    """Return (year, month, raw_date_str) extracted from a bulletin page text.

    Bulletins are labelled like "Δελτίο Ιανουαρίου 2024" or "January 2024".
    """
    text_up = text.upper()
    year = None
    month = None

    # Look for year
    m_year = re.search(r"\b(20\d{2})\b", text)
    if m_year:
        year = int(m_year.group(1))

    # Look for Greek month name
    for stem, mo in _MONTH_GR.items():
        if stem in text_up:
            month = mo
            break

    # Fallback: English month name
    if month is None:
        for stem, mo in _MONTH_EN.items():
            if stem in text_up:
                month = mo
                break

    raw = f"{month}/{year}" if (year and month) else ""
    return year, month, raw


def _map_header_to_cols(header_row: list) -> dict[str, int]:
    """Return {col_type: col_index} from a header row."""
    result: dict[str, int] = {}
    for ci, cell in enumerate(header_row):
        s = str(cell or "").upper().replace("\n", " ")
        for col_type, keywords in _COL_KEYWORDS.items():
            if col_type in result:
                continue
            if any(k in s for k in keywords):
                result[col_type] = ci
    return result


def _is_header_row(row: list) -> bool:
    """Heuristic: row has multiple non-None non-numeric cells → likely a header."""
    text_cells = sum(
        1 for c in row
        if c and not re.match(r"^\s*[\d.,\-–]+\s*$", str(c))
    )
    return text_cells >= 2


def find_astypalea_row(table: list[list]) -> tuple[int | None, int | None, dict[str, int]]:
    """Find the Astypalea data row and its header row.

    Returns (header_row_idx, data_row_idx, col_map).
    """
    last_header_ri = None
    last_col_map: dict[str, int] = {}

    for ri, row in enumerate(table):
        if _is_header_row(row):
            cm = _map_header_to_cols(row)
            if cm:  # non-empty mapping → looks like a real header
                last_header_ri = ri
                last_col_map = cm
            continue

        for cell in row:
            if cell and _ISLAND_RE.search(str(cell)):
                return last_header_ri, ri, last_col_map

    return None, None, {}


def extract_bulletin_record(
    table: list[list],
    data_ri: int,
    col_map: dict[str, int],
    header_ri: int | None,
    source_fname: str,
    table_num: int,
    page_num: int,
    year: int | None,
    month: int | None,
    bulletin_date_str: str,
) -> dict:
    row = table[data_ri]

    def get(col_type: str) -> float | None:
        ci = col_map.get(col_type)
        if ci is None or ci >= len(row):
            return None
        return parse_greek_number(str(row[ci] or ""))

    thermal = get("thermal_gen_mwh")
    res = get("res_gen_mwh")
    total = get("total_gen_mwh")

    # If total not found, derive from thermal + res
    if total is None and thermal is not None and res is not None:
        total = round(thermal + res, 3)
        notes = "total_gen_mwh derived as thermal + res"
    else:
        notes = ""

    # Col-map may be sparse; log missing keys
    missing = [k for k in ("thermal_gen_mwh", "res_gen_mwh", "res_share_pct") if k not in col_map]
    if missing:
        notes = (notes + f" MISSING_COLS:{missing}").strip()

    return {
        "year": year,
        "month": month,
        "bulletin_date": bulletin_date_str,
        "thermal_gen_mwh": thermal,
        "res_gen_mwh": res,
        "total_gen_mwh": total,
        "res_share_pct": get("res_share_pct"),
        "avg_prod_cost_eur_mwh": get("avg_prod_cost_eur_mwh"),
        "peak_load_mw": get("peak_load_mw"),
        "installed_capacity_mw": get("installed_capacity_mw"),
        "source_bulletin": source_fname,
        "table_number": table_num,
        "page": page_num + 1,
        "notes": notes,
    }


def parse_bulletin_pdf(pdf_path: Path) -> list[dict]:
    """Parse a single bulletin PDF; return list of ΑΣΤΥΠΑΛΑΙΑ monthly records."""
    records: list[dict] = []
    fname = pdf_path.name

    with pdfplumber.open(pdf_path) as pdf:
        # Extract bulletin date from first 2 pages
        full_text = " ".join(
            (p.extract_text() or "") for p in pdf.pages[:2]
        )
        year, month, date_str = _parse_bulletin_date(full_text)

        if year is None:
            log.warning(f"  Could not determine year from {fname}")

        global_table_num = 0
        for pi, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            for table in tables:
                global_table_num += 1
                if not table:
                    continue
                header_ri, data_ri, col_map = find_astypalea_row(table)
                if data_ri is None:
                    continue

                rec = extract_bulletin_record(
                    table, data_ri, col_map, header_ri,
                    fname, global_table_num, pi,
                    year, month, date_str,
                )
                records.append(rec)
                log.debug(
                    f"  Found ΑΣΤΥΠΑΛΑΙΑ in {fname} page {pi+1} "
                    f"table {global_table_num}: {year}/{month}"
                )

    if not records:
        log.warning(f"  No ΑΣΤΥΠΑΛΑΙΑ row found in {fname}")
    else:
        log.info(f"  {fname}: {len(records)} record(s)")

    return records


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    setup_dirs()

    bulletin_dir = DATA_RAW / "bulletins"
    if not bulletin_dir.exists():
        log.error("data/raw/bulletins/ not found; run 01_download.py first")
        return

    pdf_files = sorted(bulletin_dir.glob("*.pdf"))
    if not pdf_files:
        log.error("No bulletin PDFs found; run 01_download.py first")
        return

    log.info(f"Processing {len(pdf_files)} bulletin PDFs")
    all_records: list[dict] = []

    for pdf_path in pdf_files:
        try:
            recs = parse_bulletin_pdf(pdf_path)
            all_records.extend(recs)
        except Exception as exc:
            log.error(f"ERROR parsing {pdf_path.name}: {exc}", exc_info=True)

    if not all_records:
        log.error("No records extracted from bulletins")
        return

    # Sort by year/month
    all_records.sort(key=lambda r: (r.get("year") or 0, r.get("month") or 0))

    # Flag if the same year/month appears more than once (duplicate tables in bulletin)
    seen_ym: dict[tuple, int] = {}
    for r in all_records:
        key = (r.get("year"), r.get("month"))
        seen_ym[key] = seen_ym.get(key, 0) + 1
    dups = {k: v for k, v in seen_ym.items() if v > 1}
    if dups:
        log.warning(
            f"Duplicate year/month entries (multiple tables in same bulletin?): {dups}"
        )
        for r in all_records:
            key = (r.get("year"), r.get("month"))
            if key in dups:
                r["notes"] = (str(r.get("notes", "")) + " DUPLICATE_ENTRY").strip()

    out_path = DATA_PROCESSED / "astypalea_monthly_hedno.csv"
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=OUTPUT_COLS, extrasaction="ignore")
        w.writeheader()
        w.writerows(all_records)

    log.info(f"Written {len(all_records)} rows → {out_path}")
    log.info(f"Coverage: {sorted(set(r['year'] for r in all_records if r['year']))}")


if __name__ == "__main__":
    main()

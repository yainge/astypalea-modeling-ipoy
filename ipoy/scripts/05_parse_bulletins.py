"""
05_parse_bulletins.py — Extract ΑΣΤΥΠΑΛΑΙΑ rows from HEDNO monthly bulletins.

Each monthly bulletin ("Πληροφοριακό Δελτίο") contains tables covering
all Non-Interconnected Islands.  Two tables hold Astypalea data (verified
Dec 2025, Mar 2026, Jul 2026 — DATA_NOTES §1e):

  Table 3 (installed RES, ~5 cols): name | wind MW | wind MWh | PV MW | PV MWh
  Table 12 (monthly energy, 8 cols):
    name | installed_thermal_2024 | peak_2024 | RES_energy | thermal_energy
         | ΜΠΚΠ | ΜΜΚ | RES_share

Strategy: scan every table, find rows whose first cell matches ΑΣΤΥΠΑΛΑΙΑ,
classify by column count, and merge the two tables into one output row.

Output: data/processed/astypalea_monthly_hedno.csv
"""
import csv
import re
import sys
import unicodedata
from pathlib import Path

import pdfplumber

sys.path.insert(0, str(Path(__file__).parent))
from utils import DATA_PROCESSED, DATA_RAW, parse_greek_number, setup_dirs, setup_logging

log = setup_logging("parse_bulletins")

OUTPUT_COLS = [
    "year", "month", "bulletin_date",
    "thermal_gen_mwh", "res_gen_mwh", "total_gen_mwh",
    "res_share_pct", "avg_prod_cost_eur_mwh", "mmk_eur_mwh",
    "peak_load_mw_2024", "installed_capacity_mw_2024",
    "t3_pv_gen_mwh",
    "source_bulletin", "table_number", "page", "notes",
]

# Table 12 column indices (fixed per DATA_NOTES §1e, verified Dec 2025 / Mar 2026 / Jul 2026)
_T12_COLS = {
    "installed_capacity_mw_2024": 1,
    "peak_load_mw_2024": 2,
    "res_gen_mwh": 3,
    "thermal_gen_mwh": 4,
    "avg_prod_cost_eur_mwh": 5,
    "mmk_eur_mwh": 6,
    "res_share_pct": 7,
}

# Table 12 keyword fallback — used to verify column order hasn't changed
_T12_KEYWORDS: dict[str, list[str]] = {
    "installed_capacity_mw_2024": ["ΕΓΚΑΤ"],
    "peak_load_mw_2024": ["ΑΙΧΜΗ", "ΜΕΓΙΣΤΗ"],
    "res_gen_mwh": ["ΕΝΕΡΓΕΙΑ ΑΠΕ", "ΕΝΕΡΓΕΙΑ ΜΟΝΑΔΩΝ ΑΠΕ"],
    "thermal_gen_mwh": ["ΕΝΕΡΓΕΙΑ ΘΕΡΜΙ", "ΕΝΕΡΓΕΙΑ ΣΥΜΒΑΤΙΚ"],
    "avg_prod_cost_eur_mwh": ["ΜΠΚΠ"],
    "mmk_eur_mwh": ["ΜΜΚ"],
    "res_share_pct": ["ΠΟΣΟΣΤΟ", "ΜΕΡΙΔΙΟ"],
}

_ISLAND_RE = re.compile(r"ΑΣΤΥΠΑΛΑΙ", re.IGNORECASE)

_MONTH_GR = {
    "ΙΑΝΟΥ": 1, "ΦΕΒ": 2, "ΜΑΡΤ": 3, "ΑΠΡΙ": 4, "ΜΑΪΟ": 5, "ΜΑΙ": 5,
    "ΙΟΥΝ": 6, "ΙΟΥΛ": 7, "ΑΥΓΟ": 8, "ΣΕΠΤ": 9, "ΟΚΤΩ": 10, "ΝΟΕΜ": 11,
    "ΔΕΚΕ": 12,
}
_MONTH_EN = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}


def _strip_accents(s: str) -> str:
    """Remove combining accent marks and return uppercase."""
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    ).upper()


def _parse_bulletin_date(text: str) -> tuple[int | None, int | None, str]:
    """Return (year, month, raw_date_str) from bulletin cover text.

    Uses accent-stripped matching to handle Greek text with and without accents.
    """
    text_stripped = _strip_accents(text)
    year = None
    month = None

    m_year = re.search(r"\b(20\d{2})\b", text)
    if m_year:
        year = int(m_year.group(1))

    for stem, mo in _MONTH_GR.items():
        if stem in text_stripped:
            month = mo
            break

    if month is None:
        text_up = text.upper()
        for stem, mo in _MONTH_EN.items():
            if stem in text_up:
                month = mo
                break

    raw = f"{month}/{year}" if (year and month) else ""
    return year, month, raw


def _find_island_row(table: list[list]) -> int | None:
    """Return 0-indexed data row index whose first cell matches ΑΣΤΥΠΑΛΑΙΑ."""
    for ri, row in enumerate(table):
        if row and row[0] and _ISLAND_RE.search(str(row[0])):
            return ri
    return None


def _verify_t12_column_order(table: list[list]) -> bool:
    """Check that Table 12 header keywords still match the expected column positions.

    Logs a warning if a keyword mismatch is detected (column order may have shifted).
    Returns True if OK or no header found.
    """
    for row in table:
        non_null = [c for c in row if c]
        if len(non_null) < 4:
            continue
        row_up = [_strip_accents(str(c or "")) for c in row]
        mismatches = []
        for field, keywords in _T12_KEYWORDS.items():
            expected_ci = _T12_COLS.get(field)
            if expected_ci is None or expected_ci >= len(row_up):
                continue
            cell_text = row_up[expected_ci]
            if any(kw in cell_text for kw in keywords):
                continue  # OK
            # Check if the keyword appears elsewhere in the row
            found_at = next(
                (ci for ci, ct in enumerate(row_up) if any(kw in ct for kw in keywords)),
                None,
            )
            if found_at is not None and found_at != expected_ci:
                mismatches.append(
                    f"{field}: expected col {expected_ci}, found at col {found_at}"
                )
        if mismatches:
            log.warning(f"  Table 12 column order may have shifted: {mismatches}")
        return True
    return True


def _extract_t12(row: list, source_fname: str, table_num: int, page_num: int) -> dict:
    """Extract Table 12 fields from the Astypalea data row."""
    def get(ci: int) -> float | None:
        if ci >= len(row):
            return None
        return parse_greek_number(str(row[ci] or ""))

    thermal = get(_T12_COLS["thermal_gen_mwh"])
    res = get(_T12_COLS["res_gen_mwh"])
    total = None
    notes = ""

    if thermal is not None and res is not None:
        total = round(thermal + res, 3)
        notes = "total_gen_mwh derived as thermal + res"

    return {
        "thermal_gen_mwh": thermal,
        "res_gen_mwh": res,
        "total_gen_mwh": total,
        "res_share_pct": get(_T12_COLS["res_share_pct"]),
        "avg_prod_cost_eur_mwh": get(_T12_COLS["avg_prod_cost_eur_mwh"]),
        "mmk_eur_mwh": get(_T12_COLS["mmk_eur_mwh"]),
        "peak_load_mw_2024": get(_T12_COLS["peak_load_mw_2024"]),
        "installed_capacity_mw_2024": get(_T12_COLS["installed_capacity_mw_2024"]),
        "source_bulletin": source_fname,
        "table_number": table_num,
        "page": page_num + 1,
        "notes": notes,
    }


def _extract_t3(row: list) -> float | None:
    """Extract PV MWh from Table 3 row (col 4 = PV MWh, DATA_NOTES §1e)."""
    if len(row) > 4:
        return parse_greek_number(str(row[4] or ""))
    return None


def parse_bulletin_pdf(pdf_path: Path) -> list[dict]:
    """Parse a single bulletin PDF; return list of ΑΣΤΥΠΑΛΑΙΑ monthly records.

    Merges Table 3 (PV energy) and Table 12 (full monthly data) into one row.
    """
    fname = pdf_path.name
    t12_rec: dict | None = None
    t3_pv: float | None = None

    with pdfplumber.open(pdf_path) as pdf:
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

                data_ri = _find_island_row(table)
                if data_ri is None:
                    continue

                row = table[data_ri]
                n_cols = max((len(r) for r in table if r), default=0)

                if n_cols <= 6:
                    # Table 3: installed RES (5 cols: name | wind MW | wind MWh | PV MW | PV MWh)
                    pv = _extract_t3(row)
                    if pv is not None and t3_pv is None:
                        t3_pv = pv
                        log.debug(f"  {fname} table {global_table_num} p{pi+1}: Table 3 PV={pv} MWh")
                elif n_cols >= 7:
                    # Table 12: full monthly energy data (8 cols)
                    if t12_rec is None:
                        _verify_t12_column_order(table)
                        t12_rec = _extract_t12(row, fname, global_table_num, pi)
                        log.debug(
                            f"  {fname} table {global_table_num} p{pi+1}: "
                            f"Table 12 thermal={t12_rec.get('thermal_gen_mwh')} MWh"
                        )

    if t12_rec is None:
        log.warning(f"  No Table 12 (monthly data) for ΑΣΤΥΠΑΛΑΙΑ in {fname}")
        return []

    rec = {
        "year": year,
        "month": month,
        "bulletin_date": date_str,
        "t3_pv_gen_mwh": t3_pv,
        **t12_rec,
    }
    log.info(f"  {fname}: {year}/{month}  thermal={rec.get('thermal_gen_mwh')} res={rec.get('res_gen_mwh')}")
    return [rec]


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

    # Flag if the same year/month appears more than once
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

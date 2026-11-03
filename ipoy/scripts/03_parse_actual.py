"""
03_parse_actual.py — Parse HEDNO actual operations reports into hourly CSV.

Handles two PDF layouts:
  - YEARLY (2020-2024): one PDF per year, wide format (hours = columns).
    Header has date + "Απολογιστική λειτουργία ΗΣ Αστυπάλαιας".
    Row "Ζήτηση" = hourly demand (MWh, numerically = MW for 1-h intervals).
    Unit rows (G5, G6, G7, G8): "1" = running, "Διαθέσιμη" = available/off.

  - WEEKLY (2025+): one PDF per week, tall format (hours = rows).
    Column "Πραγματικό Μέσο Ωριαίο Φορτίο (MW)" = actual average hourly load.
    Unit columns G5-G8: "Αποδιδόμενη Ισχύς (MW)" = 1,1.
    Cells with "1" or "b" — meaning unknown, stored as unit_raw_{name}.
    Cell fill color encodes maintenance vs fault; extracted where possible.

Output: data/processed/astypalea_hourly_actual.csv
One row per hour:
  timestamp_local, timestamp_utc, demand_mw,
  G5_on, G6_on, G7_on, G8_on, units_on_count,
  G5_status, G6_status, G7_status, G8_status,
  source_file, page, remark
"""
import csv
import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd
import pdfplumber

sys.path.insert(0, str(Path(__file__).parent))
from utils import (
    DATA_PROCESSED, DATA_RAW, make_timestamps,
    parse_date_str, parse_greek_number, setup_dirs, setup_logging,
)

log = setup_logging("parse_actual")

UNIT_NAMES = ("G5", "G6", "G7", "G8")

OUTPUT_COLS = [
    "timestamp_local", "timestamp_utc", "demand_mw", "demand_flag",
    "G5_on", "G6_on", "G7_on", "G8_on", "units_on_count",
    "G5_status", "G6_status", "G7_status", "G8_status",
    "G5_raw", "G6_raw", "G7_raw", "G8_raw",
    "G5_fill", "G6_fill", "G7_fill", "G8_fill",
    "source_file", "page", "remark",
]

# ── Format detection ───────────────────────────────────────────────────────────

def detect_format(pdf_path: Path) -> str:
    """Return 'yearly' or 'weekly' by reading page 1 text (accent-insensitive)."""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = _strip_accents(pdf.pages[0].extract_text() or "")
            if "ΠΡΑΓΜΑΤΙΚΟ ΜΕΣΟ ΩΡΙΑΙΟ" in text or "ΑΠΟΔΙΔΟΜΕΝΗ ΙΣΧΥΣ" in text:
                return "weekly"
            if "ΖΗΤΗΣΗ" in text or "ΑΠΟΛΟΓΙΣΤΙΚΗ ΛΕΙΤΟΥΡΓΙΑ" in text:
                return "yearly"
            for pg in pdf.pages[1:3]:
                t = _strip_accents(pg.extract_text() or "")
                if "ΠΡΑΓΜΑΤΙΚΟ ΜΕΣΟ ΩΡΙΑΙΟ" in t:
                    return "weekly"
                if "ΖΗΤΗΣΗ" in t:
                    return "yearly"
    except Exception as exc:
        log.warning(f"Could not detect format for {pdf_path.name}: {exc}")
    log.warning(f"Format unclear for {pdf_path.name}; defaulting to 'yearly'")
    return "yearly"


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _cell_fill_color(page, cell_bbox: tuple) -> tuple | None:
    """Return non-white fill color of the rect that most overlaps cell_bbox, or None."""
    x0, top, x1, bottom = cell_bbox
    cx, cy = (x0 + x1) / 2, (top + bottom) / 2
    for rect in page.rects:
        rc = rect.get("non_stroking_color")
        if rc in (None, 1, 1.0, (1,), (1, 1, 1)):
            continue
        if (rect["x0"] <= cx <= rect["x1"] and
                rect["top"] <= cy <= rect["bottom"]):
            return rc
    return None


def _strip_accents(s: str) -> str:
    """Remove combining accent marks and return uppercase; used for Greek date parsing."""
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    ).upper()


def _color_to_hex(color: tuple | None) -> str | None:
    """Convert a pdfplumber fill-color tuple to a CSS hex string, or None if no fill."""
    if color is None:
        return None
    if len(color) == 4:  # CMYK → approximate RGB
        c, m, y, k = color
        r = (1 - c) * (1 - k)
        g = (1 - m) * (1 - k)
        b = (1 - y) * (1 - k)
    elif len(color) == 1:  # grayscale
        r = g = b = float(color[0])
    else:
        r, g, b = (list(color) + [0.0, 0.0])[:3]
    return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"


# ── YEARLY format parser ───────────────────────────────────────────────────────

_DATE_IN_HEADER = re.compile(
    r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})"
)
_DAY_HEADER_KEYWORDS = re.compile(
    r"ΑΠΟΛΟΓΙΣΤΙΚ|ΛΕΙΤΟΥΡΓΙΑ|ΗΣ ΑΣΤΥΠΑΛΑΙ",
    re.IGNORECASE,
)


def _find_hour_column_map(header_row: list) -> dict[int, int]:
    """Map column-index → hour (0-23) from a table header row.

    Accepts: '0', '1', '00', '01', '00:00', '1η', digit-only labels 0-23.
    Returns empty dict if header does not look like an hour row.
    """
    mapping: dict[int, int] = {}
    for ci, cell in enumerate(header_row):
        if cell is None:
            continue
        s = str(cell).strip().rstrip(":ηη").split(":")[0].strip()
        try:
            h = int(s)
            if 0 <= h <= 23:
                mapping[ci] = h
        except ValueError:
            pass
    return mapping


def _find_row_by_label(table: list[list], keyword: str) -> int | None:
    """Return 0-indexed row index whose first non-None cell contains keyword."""
    kw = keyword.upper()
    for ri, row in enumerate(table):
        for cell in row:
            if cell and kw in str(cell).upper():
                return ri
    return None


def parse_day_table_yearly(
    table: list[list],
    date_iso: str,
    source_file: str,
    page_num: int,
    remark: str = "",
    page=None,          # pdfplumber page object (for color extraction)
    table_obj=None,     # pdfplumber Table object (for cell bboxes)
) -> list[dict]:
    """Parse one day's wide-format table. Returns list of hourly dicts."""
    rows = []

    # Find header row (contains hours 0-23)
    hour_map: dict[int, int] = {}
    header_row_idx = None
    for ri, row in enumerate(table):
        m = _find_hour_column_map(row)
        if len(m) >= 20:  # at least 20 hour columns → valid header
            hour_map = m
            header_row_idx = ri
            break

    if not hour_map:
        log.warning(
            f"  No hour header found in table on page {page_num + 1} of "
            f"{source_file}; date={date_iso}"
        )
        return rows

    # Find demand row
    demand_row_idx = _find_row_by_label(table, "ΖΗΤΗΣΗ")
    if demand_row_idx is None:
        log.warning(f"  No 'Ζήτηση' row on page {page_num + 1}; date={date_iso}")
        return rows

    demand_row = table[demand_row_idx]

    # Find unit rows
    unit_row_indices: dict[str, int] = {}
    for name in UNIT_NAMES:
        ri = _find_row_by_label(table, name)
        if ri is not None:
            unit_row_indices[name] = ri

    # Build cell-bbox map if table_obj provided (for color)
    cell_bboxes: dict[tuple[int, int], tuple] = {}
    if table_obj is not None:
        for ri_obj, row_obj in enumerate(table_obj.rows):
            for ci_obj, cell_bbox in enumerate(row_obj.cells):
                if cell_bbox:
                    cell_bboxes[(ri_obj, ci_obj)] = cell_bbox

    # Extract per-hour values
    for col_idx, hour in sorted(hour_map.items()):
        demand_val = parse_greek_number(str(demand_row[col_idx] or ""))

        unit_on: dict[str, int | None] = {}
        unit_status: dict[str, str] = {}
        unit_raw: dict[str, str] = {}
        unit_fill: dict[str, str | None] = {}

        for name, row_idx in unit_row_indices.items():
            raw = str(table[row_idx][col_idx] or "").strip()
            unit_raw[name] = raw

            # Determine running state from text (yearly format uses "1" / "Διαθέσιμη")
            raw_up = _strip_accents(raw)
            if raw == "1":
                on_val = 1
                status = "on"
            elif "ΔΙΑΘ" in raw_up:
                on_val = 0
                status = "available"
            elif raw in ("", "∅"):
                on_val = None
                status = "unknown"
            else:
                on_val = None
                status = "unknown"

            # Store fill hex; don't use for status
            fill_hex = None
            if page is not None and table_obj is not None:
                bbox = cell_bboxes.get((row_idx, col_idx))
                if bbox:
                    fill_hex = _color_to_hex(_cell_fill_color(page, bbox))

            unit_on[name] = on_val
            unit_status[name] = status
            unit_fill[name] = fill_hex

        on_count = sum(v for v in unit_on.values() if v == 1)

        ts_local, ts_utc = make_timestamps(date_iso, hour)
        demand_flag = None
        if "+LOCAL_NONEXISTENT" in ts_local:
            demand_flag = "dst_placeholder"
            demand_val = None
        rows.append({
            "timestamp_local": ts_local,
            "timestamp_utc": ts_utc,
            "demand_mw": demand_val,
            "demand_flag": demand_flag,
            "G5_on": unit_on.get("G5"),
            "G6_on": unit_on.get("G6"),
            "G7_on": unit_on.get("G7"),
            "G8_on": unit_on.get("G8"),
            "units_on_count": on_count if unit_on else None,
            "G5_status": unit_status.get("G5", "unknown"),
            "G6_status": unit_status.get("G6", "unknown"),
            "G7_status": unit_status.get("G7", "unknown"),
            "G8_status": unit_status.get("G8", "unknown"),
            "G5_raw": unit_raw.get("G5", ""),
            "G6_raw": unit_raw.get("G6", ""),
            "G7_raw": unit_raw.get("G7", ""),
            "G8_raw": unit_raw.get("G8", ""),
            "G5_fill": unit_fill.get("G5"),
            "G6_fill": unit_fill.get("G6"),
            "G7_fill": unit_fill.get("G7"),
            "G8_fill": unit_fill.get("G8"),
            "source_file": source_file,
            "page": page_num + 1,
            "remark": remark,
        })

    return rows


_MONTH_GR_STEMS = {
    "ΙΑΝΟΥ": 1, "ΦΕΒ": 2, "ΜΑΡΤ": 3, "ΑΠΡΙ": 4, "ΜΑΪΟ": 5, "ΜΑΙ": 5,
    "ΙΟΥΝ": 6, "ΙΟΥΛ": 7, "ΑΥΓΟ": 8, "ΣΕΠΤ": 9, "ΟΚΤΩ": 10, "ΝΟΕΜ": 11,
    "ΔΕΚΕ": 12,
}


def _extract_date_from_page_text(text: str) -> str | None:
    """Extract date from a page's free text (DD/MM/YYYY pattern)."""
    for m in _DATE_IN_HEADER.finditer(text):
        d, mo, y = m.group(1), m.group(2), m.group(3)
        try:
            from datetime import date
            dt = date(int(y), int(mo), int(d))
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def _parse_greek_date_text(text: str) -> str | None:
    """Parse 'Τρίτη, 2 Δεκεμβρίου 2025' or similar → '2025-12-02'.

    Uses accent-stripped matching for month names.
    """
    from datetime import date as _date

    text_norm = _strip_accents(text)

    m_year = re.search(r"\b(20\d{2})\b", text)
    if not m_year:
        return None
    year = int(m_year.group(1))

    # Day number: first 1-2 digit number that isn't a year
    day = None
    for m in re.finditer(r"\b(\d{1,2})\b", text):
        d = int(m.group(1))
        if 1 <= d <= 31:
            day = d
            break
    if day is None:
        return None

    month = None
    for stem, mo in _MONTH_GR_STEMS.items():
        if stem in text_norm:
            month = mo
            break
    if month is None:
        return None

    try:
        return _date(year, month, day).isoformat()
    except ValueError:
        return None


def _date_from_table_row0(table: list[list]) -> str | None:
    """Extract date from row 0 of a weekly table (col 2 typically holds the Greek date)."""
    if not table or not table[0]:
        return None
    row0 = table[0]
    # Try col 2 first (per DATA_NOTES §1b), then all cells in row 0
    candidates = []
    if len(row0) > 2 and row0[2]:
        candidates.append(str(row0[2]))
    candidates.extend(str(c) for c in row0 if c and str(c) not in candidates)
    for cell_text in candidates:
        d = _parse_greek_date_text(cell_text)
        if d:
            return d
    return None


def _extract_remarks(text: str, date_iso: str | None) -> str:
    """Extract free-text remarks from page text (after table rows, before legend)."""
    lines = text.split("\n")
    remark_lines = []
    past_last_hour = False

    for line in lines:
        ln = line.strip()
        if not ln:
            continue
        # Detect when we've passed the last hour row (22:00 or 23:00)
        if re.match(r"^2[23]:00", ln):
            past_last_hour = True
            continue
        # Skip other time rows
        if re.match(r"^\d{1,2}:\d{2}", ln):
            continue
        # Stop at legend
        if any(kw in _strip_accents(ln) for kw in ("ΜΗ ΔΙΑΘΕΣΙΜΟΤ", "ΣΥΝΤΗΡΗΣ", "ΛΟΓΩ ΒΛΑΒ")):
            break
        if past_last_hour:
            remark_lines.append(ln)
        elif re.search(r"\d{2}:\d{2}", ln) and re.search(
            r"[Δδ]ιακοπ|εργασ|συντήρ|βλάβ|ΒΛΑΒ|ΕΡΓΑΣ", ln
        ):
            remark_lines.append(ln)

    return " | ".join(remark_lines) if remark_lines else ""


def parse_pdf_yearly(pdf_path: Path) -> list[dict]:
    """Parse a yearly-format PDF. Returns flat list of hourly dicts."""
    records: list[dict] = []
    fname = pdf_path.name

    with pdfplumber.open(pdf_path) as pdf:
        for pi, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            text_upper = text.upper()

            # Skip pages without an "Απολογιστική" header
            if "ΑΠΟΛΟΓΙΣΤΙΚ" not in text_upper and "ΖΗΤΗΣΗ" not in text_upper:
                continue

            date_iso = _extract_date_from_page_text(text)
            if date_iso is None:
                log.warning(f"  No date found on page {pi + 1} of {fname}")
                continue

            remark = _extract_remarks(text, date_iso)

            tables_objs = page.find_tables()
            tables_data = [t.extract() for t in tables_objs]

            if not tables_data:
                # Fallback: text-only extraction (no table structure)
                log.warning(f"  No tables on page {pi + 1} ({date_iso}); trying text parse")
                text_rows = parse_day_text_yearly(text, date_iso, fname, pi, remark)
                records.extend(text_rows)
                continue

            # Try each table; use the first that yields ≥20 demand rows
            parsed_any = False
            for ti, (tdata, tobj) in enumerate(zip(tables_data, tables_objs)):
                day_rows = parse_day_table_yearly(
                    tdata, date_iso, fname, pi, remark,
                    page=page, table_obj=tobj
                )
                if day_rows:
                    records.extend(day_rows)
                    parsed_any = True
                    break

            if not parsed_any:
                log.warning(f"  Could not parse tables on page {pi + 1} ({date_iso})")

    log.info(f"  {fname}: {len(records)} hourly rows from yearly format")
    return records


def parse_day_text_yearly(
    text: str, date_iso: str, source_file: str, page_num: int, remark: str
) -> list[dict]:
    """Fallback: try to extract demand values from raw page text when table extraction fails.

    Looks for a row that starts with 'Ζήτηση' followed by 24 numeric values.
    """
    rows: list[dict] = []
    for line in text.split("\n"):
        if "ΖΗΤΗΣΗ" not in line.upper():
            continue
        parts = line.split()
        values = []
        for p in parts:
            v = parse_greek_number(p)
            if v is not None:
                values.append(v)
        if len(values) >= 24:
            for hour in range(24):
                ts_local, ts_utc = make_timestamps(date_iso, hour)
                rows.append({
                    "timestamp_local": ts_local,
                    "timestamp_utc": ts_utc,
                    "demand_mw": values[hour],
                    "demand_flag": None,
                    "G5_on": None, "G6_on": None, "G7_on": None, "G8_on": None,
                    "units_on_count": None,
                    "G5_status": "unknown", "G6_status": "unknown",
                    "G7_status": "unknown", "G8_status": "unknown",
                    "G5_raw": "", "G6_raw": "", "G7_raw": "", "G8_raw": "",
                    "G5_fill": None, "G6_fill": None, "G7_fill": None, "G8_fill": None,
                    "source_file": source_file, "page": page_num + 1,
                    "remark": remark + " [text-fallback]",
                })
            break
    return rows


# ── WEEKLY format parser ───────────────────────────────────────────────────────

_HOUR_ROW_RE = re.compile(r"^(\d{1,2}):00")   # "00:00", "1:00", …
_DEMAND_COL_KEYWORDS = ("ΠΡΑΓΜΑΤΙΚΟ ΜΕΣΟ", "ΜΕΣΟ ΩΡΙΑΙΟ", "ΦΟΡΤΙΟ")  # compared after _strip_accents
_UNIT_COL_RE = re.compile(r"\b(G[5-8])\b", re.IGNORECASE)


def _find_column_indices(header_row: list) -> dict[str, int]:
    """Return mapping name→col-index for demand and units from a weekly table header."""
    result: dict[str, int] = {}
    for ci, cell in enumerate(header_row):
        s = _strip_accents(str(cell or ""))
        if any(kw in s for kw in _DEMAND_COL_KEYWORDS):
            result["demand"] = ci
        for name in UNIT_NAMES:
            if name in s:
                result[name] = ci
    return result


def parse_day_table_weekly(
    table: list[list],
    date_iso: str,
    source_file: str,
    page_num: int,
    remark: str = "",
    page=None,
    table_obj=None,
) -> list[dict]:
    """Parse one day's tall-format table from a 2025+ weekly report."""
    rows: list[dict] = []

    if not table or not table[0]:
        return rows

    # Identify header row: the one with column labels (not a time like "00:00")
    header_row_idx = None
    col_map: dict[str, int] = {}
    for ri, row in enumerate(table):
        col_map = _find_column_indices(row)
        if "demand" in col_map or any(n in col_map for n in UNIT_NAMES):
            header_row_idx = ri
            break

    if "demand" not in col_map:
        log.warning(
            f"  No demand column found on page {page_num + 1} of {source_file}; "
            f"date={date_iso}"
        )
        return rows

    # Build cell-bbox map
    cell_bboxes: dict[tuple[int, int], tuple] = {}
    if table_obj is not None:
        for ri_obj, row_obj in enumerate(table_obj.rows):
            for ci_obj, cell_bbox in enumerate(row_obj.cells):
                if cell_bbox:
                    cell_bboxes[(ri_obj, ci_obj)] = cell_bbox

    for ri, row in enumerate(table):
        if ri == header_row_idx:
            continue
        if not row:
            continue
        # Col 1 is the time "HH:00"; col 0 is the rotated day label (DATA_NOTES §1b)
        time_cell = str(row[1] or "").strip() if len(row) > 1 else ""
        m = _HOUR_ROW_RE.match(time_cell)
        if not m:
            continue
        hour = int(m.group(1))
        if not 0 <= hour <= 23:
            continue

        raw_demand_str = str(row[col_map["demand"]] or "")
        demand_val = parse_greek_number(raw_demand_str)
        demand_flag = None

        # Q7: values without a decimal separator produce implausible MW readings
        if demand_val is not None and not (0.0 <= demand_val <= 5.0):
            log.warning(
                f"  Load {demand_val} MW outside 0–5 MW on {date_iso} "
                f"hour {hour:02d}:00 in {source_file} (flagged no_decimal_separator)"
            )
            demand_flag = "no_decimal_separator"
            demand_val = None

        unit_on: dict[str, int | None] = {}
        unit_status: dict[str, str] = {}
        unit_raw: dict[str, str] = {}
        unit_fill: dict[str, str | None] = {}

        for name in UNIT_NAMES:
            if name not in col_map:
                unit_on[name] = None
                unit_status[name] = "unknown"
                unit_raw[name] = ""
                unit_fill[name] = None
                continue

            ci = col_map[name]
            raw = str(row[ci] or "").strip()
            unit_raw[name] = raw

            # Status from letter only (DATA_NOTES Q2: S/s = maintenance_likely, B/b = fault_likely)
            if raw == "1":
                on_val: int | None = 1
                status = "on"
            elif raw in ("", "∅"):
                on_val = 0
                status = "available"
            elif raw.upper() == "S":
                on_val = 0
                status = "maintenance_likely"
            elif raw.upper() == "B":
                on_val = 0
                status = "fault_likely"
            else:
                on_val = None
                status = "unknown"

            # Extract fill hex and store; do not use for status derivation
            fill_hex = None
            if page is not None and table_obj is not None:
                bbox = cell_bboxes.get((ri, ci))
                if bbox:
                    fill_hex = _color_to_hex(_cell_fill_color(page, bbox))

            unit_on[name] = on_val
            unit_status[name] = status
            unit_fill[name] = fill_hex

        on_count = sum(v for v in unit_on.values() if v == 1)
        ts_local, ts_utc = make_timestamps(date_iso, hour)

        # Q6: DST spring-forward placeholder row — the PDF prints 03:00 with zero load
        if "+LOCAL_NONEXISTENT" in ts_local:
            demand_flag = "dst_placeholder"
            demand_val = None

        rows.append({
            "timestamp_local": ts_local,
            "timestamp_utc": ts_utc,
            "demand_mw": demand_val,
            "demand_flag": demand_flag,
            "G5_on": unit_on.get("G5"),
            "G6_on": unit_on.get("G6"),
            "G7_on": unit_on.get("G7"),
            "G8_on": unit_on.get("G8"),
            "units_on_count": on_count if unit_on else None,
            "G5_status": unit_status.get("G5", "unknown"),
            "G6_status": unit_status.get("G6", "unknown"),
            "G7_status": unit_status.get("G7", "unknown"),
            "G8_status": unit_status.get("G8", "unknown"),
            "G5_raw": unit_raw.get("G5", ""),
            "G6_raw": unit_raw.get("G6", ""),
            "G7_raw": unit_raw.get("G7", ""),
            "G8_raw": unit_raw.get("G8", ""),
            "G5_fill": unit_fill.get("G5"),
            "G6_fill": unit_fill.get("G6"),
            "G7_fill": unit_fill.get("G7"),
            "G8_fill": unit_fill.get("G8"),
            "source_file": source_file,
            "page": page_num + 1,
            "remark": remark,
        })

    return rows


def _extract_week_dates(text: str) -> list[str]:
    """Extract all distinct dates from a weekly PDF page text."""
    dates = set()
    for m in _DATE_IN_HEADER.finditer(text):
        d, mo, y = m.group(1), m.group(2), m.group(3)
        iso = parse_date_str(f"{d}/{mo}/{y}")
        if iso:
            dates.add(iso)
    return sorted(dates)


def _guess_date_for_page(pdf_path: Path, page_idx: int, all_page_dates: list[str]) -> str | None:
    """Use the file's date-range and page offset to guess the date for a page."""
    # Extract date range from filename
    fname = pdf_path.name
    m = re.search(
        r"(\d{1,2})[-_](\d{1,2})[-_](\d{4}).*?(\d{1,2})[-_](\d{1,2})[-_](\d{4})",
        fname,
    )
    if m:
        from datetime import date, timedelta
        try:
            start = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            day = start + timedelta(days=page_idx)
            return day.strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def parse_pdf_weekly(pdf_path: Path) -> list[dict]:
    """Parse a weekly-format PDF. Returns flat list of hourly dicts."""
    records: list[dict] = []
    fname = pdf_path.name

    with pdfplumber.open(pdf_path) as pdf:
        for pi, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            tables_objs = page.find_tables()  # pdfplumber 0.11.x returns list directly

            # Extract date from table row 0 (Greek month words, col 2 per DATA_NOTES §1b)
            date_iso = None
            for tobj in tables_objs:
                tdata = tobj.extract()
                if tdata:
                    d = _date_from_table_row0(tdata)
                    if d:
                        date_iso = d
                        break

            # Fallback: filename date-range offset
            if date_iso is None:
                date_iso = _guess_date_for_page(pdf_path, pi, [])

            if date_iso is None:
                log.warning(f"  No date on page {pi + 1} of {fname}; skipping")
                continue

            remark = _extract_remarks(text, date_iso)

            parsed_any = False
            for tobj in tables_objs:
                tdata = tobj.extract()
                day_rows = parse_day_table_weekly(
                    tdata, date_iso, fname, pi, remark,
                    page=page, table_obj=tobj,
                )
                if day_rows:
                    records.extend(day_rows)
                    parsed_any = True
                    break

            if not parsed_any:
                log.warning(f"  No hourly data on page {pi + 1} ({date_iso}) of {fname}")

    log.info(f"  {fname}: {len(records)} hourly rows from weekly format")
    return records


# ── Main ───────────────────────────────────────────────────────────────────────

def parse_actual_file(pdf_path: Path) -> list[dict]:
    fmt = detect_format(pdf_path)
    log.info(f"Parsing [{fmt}] {pdf_path.name}")
    if fmt == "yearly":
        return parse_pdf_yearly(pdf_path)
    else:
        return parse_pdf_weekly(pdf_path)


def load_manifest_actuals(data_raw: Path) -> list[Path]:
    """Return paths to all confirmed-island actual PDFs from manifest."""
    manifest = data_raw / "manifest.csv"
    if not manifest.exists():
        log.error("manifest.csv not found; run 01_download.py first")
        return []

    paths: list[Path] = []
    with open(manifest, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["section"] not in ("yearly_actuals", "weekly_actuals"):
                continue
            if row.get("island_confirmed_in_header") not in ("Y", "N/A"):
                # Skip files where island header says N or ERROR
                if row.get("island_confirmed_in_header") == "N":
                    log.warning(
                        f"Skipping {row['local_path']} (island_confirmed=N)"
                    )
                continue
            lp = row.get("local_path", "")
            if not lp:
                continue
            p = data_raw.parent.parent / lp
            if p.exists():
                paths.append(p)
            else:
                log.warning(f"File listed in manifest but not found: {p}")
    return paths


def deduplicate(records: list[dict]) -> tuple[list[dict], int]:
    """Remove exact duplicate timestamp rows; flag disagreeing duplicates."""
    seen: dict[str, dict] = {}
    conflicts = 0
    result: list[dict] = []
    for rec in records:
        key = rec["timestamp_local"].split("?")[0].split("+LOCAL")[0]
        if key in seen:
            prev = seen[key]
            if prev["demand_mw"] != rec["demand_mw"]:
                conflicts += 1
                # Keep both, annotate
                prev["remark"] = str(prev.get("remark", "")) + " [DUPLICATE_CONFLICT]"
                rec["remark"] = str(rec.get("remark", "")) + " [DUPLICATE_CONFLICT]"
                result.append(rec)
        else:
            seen[key] = rec
            result.append(rec)
    return result, conflicts


def main() -> None:
    setup_dirs()
    pdf_paths = load_manifest_actuals(DATA_RAW)
    if not pdf_paths:
        log.error("No actual PDF files found; run 01_download.py first")
        return

    all_records: list[dict] = []
    for pdf_path in sorted(pdf_paths):
        try:
            recs = parse_actual_file(pdf_path)
            all_records.extend(recs)
        except Exception as exc:
            log.error(f"ERROR parsing {pdf_path.name}: {exc}", exc_info=True)

    if not all_records:
        log.error("No records extracted; check PDF layouts with 02_inspect.py")
        return

    # Deduplicate overlapping weekly files
    all_records, n_conflicts = deduplicate(all_records)
    if n_conflicts:
        log.warning(f"  {n_conflicts} conflicting duplicate timestamps found (both kept, flagged)")

    # Sort by timestamp
    all_records.sort(key=lambda r: r["timestamp_local"])

    out_path = DATA_PROCESSED / "astypalea_hourly_actual.csv"
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=OUTPUT_COLS, extrasaction="ignore")
        w.writeheader()
        w.writerows(all_records)

    log.info(f"Written {len(all_records)} rows → {out_path}")

    # Quick coverage summary
    df = pd.read_csv(out_path)
    df["ts"] = pd.to_datetime(df["timestamp_local"].str.split("?").str[0]
                               .str.split("+LOCAL").str[0], utc=False, errors="coerce")
    df["year"] = df["ts"].dt.year
    for yr, g in df.groupby("year"):
        expected = 8760 if yr % 4 != 0 else 8784
        pct = 100 * len(g) / expected
        log.info(f"  {yr}: {len(g):5d} rows / {expected} expected ({pct:.1f}%)")


if __name__ == "__main__":
    main()

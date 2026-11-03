"""
01_download.py — Download HEDNO PDFs and RAAEY XLS files.

Scrapes:
  1. HEDNO Astypalea planning page (EN + GR language versions)
  2. HEDNO monthly bulletin index page
  3. Three RAAEY tender XLS files (direct URLs)

Writes data/raw/manifest.csv with one row per downloaded file.
Run again at any time: cached files are skipped (sha256 reused).
"""
import csv
import re
import shutil
import sys
import unicodedata
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import pdfplumber
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent))
from utils import DATA_RAW, RateLimitedSession, setup_dirs, setup_logging, sha256_file

log = setup_logging("download")

# ── Source URLs ────────────────────────────────────────────────────────────────

HEDNO_EN = (
    "https://www.deddie.gr/en/services/non-interconnected-islands/"
    "publication-of-nii-daily-energy-planning-data/astypalaia-es/"
)
BULLETINS_EN = (
    "https://www.deddie.gr/en/services/non-interconnected-islands/"
    "monthly-reports-of-res-and-thermal-units-in-the-non-interconnected-islands/"
)
RAAEY_FILES = {
    "raaey_load_2024.xls": (
        "https://www.raaey.gr/energeia/wp-content/uploads/2022/09/"
        "%CE%A3%CE%A5%CE%A3%CE%A4%CE%97%CE%9C%CE%91-%CE%91%CE%A3%CE%A4%CE%A5%CE%A0%CE%91%CE%9B%CE%91%CE%99%CE%91%CE%A3"
        "-%CE%A6%CE%9F%CE%A1%CE%A4%CE%99%CE%9F-%CE%91%CE%9D%CE%91-%CE%A9%CE%A1%CE%91-%CE%95%CE%A4%CE%9F%CE%A5%CE%A3-2024-kW.xls"
    ),
    "raaey_pv_2024.xls": (
        "https://www.raaey.gr/energeia/wp-content/uploads/2022/09/"
        "%CE%A3%CE%A5%CE%A3%CE%A4%CE%97%CE%9C%CE%91-%CE%91%CE%A3%CE%A4%CE%A5%CE%A0%CE%91%CE%9B%CE%91%CE%99%CE%91%CE%A3"
        "-%CE%A6%CE%92-%CE%A0%CE%91%CE%A1%CE%91%CE%93%CE%A9%CE%93%CE%97-%CE%91%CE%9D%CE%91-%CE%A9%CE%A1%CE%91-%CE%95%CE%A4%CE%9F%CE%A5%CE%A3-2024-kW.xls"
    ),
    "raaey_ev_2024.xls": (
        "https://www.raaey.gr/energeia/wp-content/uploads/2022/09/"
        "%CE%A3%CE%A5%CE%A3%CE%A4%CE%97%CE%9C%CE%91-%CE%91%CE%A3%CE%A4%CE%A5%CE%A0%CE%91%CE%9B%CE%91%CE%99%CE%91%CE%A3"
        "-%CE%9A%CE%91%CE%A4%CE%91%CE%9D%CE%91%CE%9B%CE%A9%CE%A3%CE%97-%CE%97%CE%9F-%CE%91%CE%9D%CE%91-%CE%A9%CE%A1%CE%91"
        "-%CE%95%CE%A4%CE%9F%CE%A5%CE%A3-2024-kW_updated.xls"
    ),
}

# ── Section classifier ─────────────────────────────────────────────────────────

def _strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    ).upper()


def classify_section_by_filename(fname: str) -> str:
    """Classify a PDF by its filename stem (accent-insensitive).

    Filename patterns (DATA_NOTES §1b, §1d):
      *Απολογισμός-λειτουργίας* → weekly_actuals
      *Προτεινόμενος-ΗΕΠ*       → weekly_forecasts
      *Απολογισμοί*              → yearly_actuals   (plural)
      *Προτεινόμενοι*            → yearly_forecasts (plural)
    """
    s = _strip_accents(fname)
    if "ΑΠΟΛΟΓΙΣΜΟΣ-ΛΕΙΤΟΥΡΓΙΑΣ" in s or "ΑΠΟΛΟΓΙΣΜΟΣ ΛΕΙΤΟΥΡΓΙΑΣ" in s:
        return "weekly_actuals"
    if "ΠΡΟΤΕΙΝΟΜΕΝΟΣ-ΗΕΠ" in s or "ΠΡΟΤΕΙΝΟΜΕΝΟΣ ΗΕΠ" in s:
        return "weekly_forecasts"
    if "ΑΠΟΛΟΓΙΣΜΟΙ" in s:
        return "yearly_actuals"
    if "ΠΡΟΤΕΙΝΟΜΕΝΟΙ" in s:
        return "yearly_forecasts"
    return "unknown"


def classify_section(heading: str) -> str:
    """Heading-based section classifier (fallback; filename takes priority)."""
    h = heading.lower()
    if "ηεπ" in h or ("προτεινόμενος" in h and re.search(r"\d", h)):
        return "weekly_forecasts"
    if "προτεινόμεν" in h:
        return "yearly_forecasts"
    if "λειτουργίας" in h or "λειτουρ" in h:
        return "weekly_actuals"
    if "απολογισμ" in h:
        return "yearly_actuals"
    return "unknown"


# ── Page scrapers ──────────────────────────────────────────────────────────────

def _main_content(soup: BeautifulSoup):
    """Return the main content element of a WordPress page."""
    for cls in (
        re.compile(r"entry-content"),
        re.compile(r"page-content"),
        re.compile(r"td-page-content"),
        re.compile(r"wpb_wrapper"),
    ):
        el = soup.find("div", class_=cls)
        if el:
            return el
    return soup.find("main") or soup.body


def scrape_hedno_pdf_links(session: RateLimitedSession, page_url: str) -> list[tuple[str, str, str]]:
    """Scrape a HEDNO planning page and return list of (pdf_url, section, heading_text)."""
    log.info(f"Scraping {page_url}")
    r = session.get(page_url)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")
    content = _main_content(soup)

    results: list[tuple[str, str, str]] = []
    current_section = "unknown"
    current_heading = ""

    for el in content.descendants:
        if el.name in ("h1", "h2", "h3", "h4", "h5", "strong", "b"):
            text = el.get_text(" ", strip=True)
            if len(text) > 4:
                sec = classify_section(text)
                if sec != "unknown":
                    current_section = sec
                    current_heading = text
        elif el.name == "a":
            href = el.get("href", "")
            if not href:
                continue
            # Accept .pdf links anywhere on deddie.gr
            if href.lower().endswith(".pdf") and "deddie.gr" in href:
                fname = urllib.parse.unquote(href.split("/")[-1])
                file_sec = classify_section_by_filename(fname)
                sec = file_sec if file_sec != "unknown" else current_section
                results.append((href, sec, current_heading))

    log.info(f"  → {len(results)} PDF links, sections: "
             f"{set(s for _, s, _ in results)}")
    return results


def find_greek_page_url(session: RateLimitedSession, en_url: str) -> str | None:
    """Look for the Greek-language switcher link on the EN page."""
    r = session.get(en_url)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")

    for a in soup.find_all("a", href=True):
        href: str = a.get("href", "")
        text = a.get_text(strip=True).lower()
        # HEDNO WordPress often uses /el/ prefix or lang param
        if re.search(r"[/=?]el[/&$]?", href) or text in ("ελληνικά", "ελ", "greek"):
            if "deddie.gr" in href or href.startswith("/"):
                base = "https://www.deddie.gr"
                full = href if href.startswith("http") else base + href
                log.info(f"Found GR page link: {full}")
                return full

    # Heuristic: swap /en/ for /el/ in the URL
    if "/en/" in en_url:
        candidate = en_url.replace("/en/", "/el/", 1)
        try:
            resp = session.get(candidate)
            if resp.status_code == 200:
                log.info(f"GR page via /el/ swap: {candidate}")
                return candidate
        except Exception:
            pass

    log.warning("Could not find Greek-language page link")
    return None


def scrape_bulletins(session: RateLimitedSession) -> list[tuple[str, str, str]]:
    """Scrape the HEDNO monthly bulletin index, return list of (pdf_url, 'bulletin', heading)."""
    log.info(f"Scraping bulletin index: {BULLETINS_EN}")
    r = session.get(BULLETINS_EN)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")
    content = _main_content(soup)

    results = []
    for a in content.find_all("a", href=True):
        href: str = a.get("href", "")
        if href.lower().endswith(".pdf") and "deddie.gr" in href:
            results.append((href, "bulletin", ""))

    log.info(f"  → {len(results)} bulletin PDFs")
    return results


# ── Island verification ────────────────────────────────────────────────────────

def confirm_island(path: Path) -> str:
    """Check first 2 PDF pages for 'ΑΣΤΥΠΑΛΑΙ'. Returns 'Y', 'N', or 'ERROR'."""
    try:
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages[:2]:
                text = (page.extract_text() or "").upper()
                if "ΑΣΤΥΠΑΛΑΙ" in text:
                    return "Y"
        return "N"
    except Exception as exc:
        log.warning(f"Could not verify island in {path.name}: {exc}")
        return "ERROR"


# ── Date-range extraction from filename ───────────────────────────────────────

def date_range_from_name(fname: str) -> str:
    """Extract a date range or year from a filename."""
    # Two dates: DD-MM-YYYY_DD-MM-YYYY or DD/MM/YYYY-DD/MM/YYYY etc.
    m = re.search(
        r"(\d{1,2}[-_/]\d{1,2}[-_/]\d{4})[\s_-]+(\d{1,2}[-_/]\d{1,2}[-_/]\d{4})",
        fname,
    )
    if m:
        return f"{m.group(1)} – {m.group(2)}"
    # Single 4-digit year
    m2 = re.search(r"(20\d{2})", fname)
    return m2.group(1) if m2 else ""


# ── Manifest I/O ───────────────────────────────────────────────────────────────

MANIFEST_FIELDS = [
    "url", "local_path", "section", "section_heading",
    "date_range_from_filename", "sha256",
    "download_time", "http_status", "island_confirmed_in_header",
]


def load_manifest(path: Path) -> dict[str, dict]:
    """Return existing manifest keyed by URL."""
    if not path.exists():
        return {}
    with open(path, encoding="utf-8", newline="") as f:
        return {row["url"]: row for row in csv.DictReader(f)}


def save_manifest(rows: list[dict], path: Path) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


# ── Migration ──────────────────────────────────────────────────────────────────

def migrate_unknown_files(manifest_path: Path) -> None:
    """Move files from hedno/unknown/ to the correct section directories.

    Also updates the manifest to reflect the new paths and sections.
    Called once at the start of main(); safe to call repeatedly.
    """
    unknown_dir = DATA_RAW / "hedno" / "unknown"
    if not unknown_dir.exists():
        return

    existing = load_manifest(manifest_path)
    updated_rows = {url: dict(row) for url, row in existing.items()}
    moved = 0

    for f in sorted(unknown_dir.iterdir()):
        if not f.is_file():
            continue
        section = classify_section_by_filename(f.name)
        if section == "unknown":
            continue  # leave other-island files in unknown/

        dest_dir = DATA_RAW / "hedno" / section
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f.name

        if dest.exists():
            f.unlink()  # duplicate; remove the unknown/ copy
            log.info(f"  Removed duplicate {f.name} from unknown/")
        else:
            shutil.move(str(f), str(dest))
            log.info(f"  Migrated {f.name} → hedno/{section}/")
        moved += 1

        # Update manifest entry: find row by matching filename in local_path
        for url, row in updated_rows.items():
            lp = row.get("local_path", "")
            if lp.endswith(f.name) and "unknown" in lp:
                new_rel = dest.relative_to(DATA_RAW.parent.parent)
                updated_rows[url]["local_path"] = str(new_rel)
                updated_rows[url]["section"] = section
                break

    if moved and existing:
        save_manifest(list(updated_rows.values()), manifest_path)
        log.info(f"  Migration complete: {moved} files moved, manifest updated")


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    setup_dirs()
    manifest_path = DATA_RAW / "manifest.csv"
    migrate_unknown_files(manifest_path)
    session = RateLimitedSession()
    existing = load_manifest(manifest_path)

    # Collect all (url, section, heading) triples
    all_links: list[tuple[str, str, str]] = []

    # 1. HEDNO EN planning page
    all_links.extend(scrape_hedno_pdf_links(session, HEDNO_EN))

    # 2. HEDNO GR planning page (may have extra files)
    gr_url = find_greek_page_url(session, HEDNO_EN)
    if gr_url:
        try:
            all_links.extend(scrape_hedno_pdf_links(session, gr_url))
        except Exception as exc:
            log.warning(f"GR page scrape failed: {exc}")

    # 3. Monthly bulletins
    all_links.extend(scrape_bulletins(session))

    # 4. RAAEY XLS (direct URLs, not scraped)
    for local_name, url in RAAEY_FILES.items():
        all_links.append((url, "raaey", "RAAEY tender files 2024"))

    # Deduplicate by URL (keep first occurrence which carries the section)
    seen: set[str] = set()
    unique: list[tuple[str, str, str]] = []
    for url, sec, hdg in all_links:
        if url not in seen:
            seen.add(url)
            unique.append((url, sec, hdg))

    log.info(f"Total unique files to process: {len(unique)}")

    rows: list[dict] = []
    for url, section, heading in unique:
        fname = urllib.parse.unquote(url.split("/")[-1])
        # fname may still contain Greek characters — that's fine on macOS/Linux

        if section == "raaey":
            dest_dir = DATA_RAW / "raaey"
        elif section == "bulletin":
            dest_dir = DATA_RAW / "bulletins"
        else:
            dest_dir = DATA_RAW / "hedno" / section

        # Use a sanitized local name for RAAEY (original filenames are ugly)
        if section == "raaey":
            # local_name set above; find it by URL match
            local_fname = next(
                (k for k, v in RAAEY_FILES.items() if v == url), fname
            )
        else:
            local_fname = fname

        dest = dest_dir / local_fname
        date_range = date_range_from_name(fname)

        # ── Cache hit ─────────────────────────────────────────────────────────
        if dest.exists() and url in existing:
            log.info(f"  [cache] {section}/{local_fname}")
            rows.append(existing[url])
            continue

        # ── Download ──────────────────────────────────────────────────────────
        log.info(f"  [dl] {section:20s}  {local_fname}")
        try:
            resp = session.download(url, dest)
            http_status = resp.status_code
        except Exception as exc:
            log.error(f"  FAILED {url}: {exc}")
            rows.append({
                "url": url, "local_path": "", "section": section,
                "section_heading": heading,
                "date_range_from_filename": date_range,
                "sha256": "", "download_time": datetime.now(timezone.utc).isoformat(),
                "http_status": f"ERROR: {exc}",
                "island_confirmed_in_header": "ERROR",
            })
            continue

        sha = sha256_file(dest)
        rel_path = dest.relative_to(DATA_RAW.parent.parent)

        if local_fname.endswith(".pdf"):
            island_ok = confirm_island(dest)
            if island_ok == "N" and section not in ("bulletin",):
                log.warning(f"  ⚠ Island NOT confirmed in header: {local_fname}")
        else:
            island_ok = "N/A"

        rows.append({
            "url": url,
            "local_path": str(rel_path),
            "section": section,
            "section_heading": heading,
            "date_range_from_filename": date_range,
            "sha256": sha,
            "download_time": datetime.now(timezone.utc).isoformat(),
            "http_status": str(http_status),
            "island_confirmed_in_header": island_ok,
        })

    save_manifest(rows, manifest_path)
    log.info(f"Manifest saved → {manifest_path}  ({len(rows)} rows)")

    # Summary
    by_section: dict[str, int] = {}
    for r in rows:
        by_section[r["section"]] = by_section.get(r["section"], 0) + 1
    for sec, count in sorted(by_section.items()):
        log.info(f"  {sec:25s}: {count} files")

    confirmed_n = sum(1 for r in rows if r.get("island_confirmed_in_header") == "N")
    if confirmed_n:
        log.warning(
            f"  {confirmed_n} PDF(s) with island_confirmed_in_header=N — "
            "check manifest; these files may belong to another island."
        )


if __name__ == "__main__":
    main()

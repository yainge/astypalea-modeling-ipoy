"""
02_inspect.py — Interactive PDF inspection tool (development use only).

Run BEFORE writing parsers to understand the actual PDF structure.
Results feed into DATA_NOTES.md.

Usage:
  python scripts/02_inspect.py <pdf_file> [options]

Options:
  --pages 1-3        show only pages 1-3 (1-indexed)
  --tables           print extracted tables with row/column indices
  --rects            print coloured rectangles (for cell-background detection)
  --render PAGE      render page N to PNG alongside the script output
  --no-text          suppress raw page text

Examples:
  python scripts/02_inspect.py data/raw/hedno/yearly_actuals/απολογισμοί-αστυπάλαιας-2024.pdf --pages 1-2 --tables
  python scripts/02_inspect.py data/raw/hedno/weekly_actuals/Αστυπάλαια_Απολογισμός-λειτουργίας_*.pdf --render 1
"""
import argparse
import sys
from pathlib import Path

import pdfplumber

sys.path.insert(0, str(Path(__file__).parent))
from utils import FIGURES_DIR, setup_logging

log = setup_logging("inspect")


# ── Helpers ────────────────────────────────────────────────────────────────────

def parse_page_range(spec: str, n_pages: int) -> list[int]:
    """Parse '1', '1-3', '2,4,6' into 0-indexed page list."""
    indices: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            indices.extend(range(int(a) - 1, min(int(b), n_pages)))
        else:
            indices.append(int(part) - 1)
    return [i for i in indices if 0 <= i < n_pages]


def print_page_text(page, page_num: int) -> None:
    print(f"\n{'='*70}")
    print(f"PAGE {page_num + 1}  (mediabox: {page.width:.0f}×{page.height:.0f})")
    print("─" * 70)
    text = page.extract_text()
    if text:
        print(text)
    else:
        print("[no extractable text]")


def print_tables(page, page_num: int) -> None:
    tables = page.find_tables()
    if not tables:
        print(f"\n  [PAGE {page_num + 1}] No tables found by pdfplumber")
        return

    for ti, table in enumerate(tables):
        data = table.extract()
        print(f"\n  [PAGE {page_num + 1}, TABLE {ti + 1}]  bbox={table.bbox}")
        print(f"  {len(data)} rows × {max(len(r) for r in data) if data else 0} cols")
        for ri, row in enumerate(data):
            cells = [str(c).replace("\n", "↵") if c is not None else "∅" for c in row]
            print(f"    [{ri:3d}] " + " | ".join(f"{c[:18]:18s}" for c in cells))


def print_rects(page, page_num: int) -> None:
    """Print non-white filled rectangles (potential cell backgrounds)."""
    colored = [
        r for r in page.rects
        if r.get("non_stroking_color") not in (None, (1,), (1, 1, 1), 1, 1.0)
    ]
    if not colored:
        print(f"\n  [PAGE {page_num + 1}] No coloured rects found")
        return
    print(f"\n  [PAGE {page_num + 1}] {len(colored)} coloured rects:")
    for rect in colored[:40]:  # cap output
        c = rect.get("non_stroking_color")
        bbox = (rect["x0"], rect["top"], rect["x1"], rect["bottom"])
        print(f"    color={c}  bbox=({bbox[0]:.1f},{bbox[1]:.1f},{bbox[2]:.1f},{bbox[3]:.1f})")
    if len(colored) > 40:
        print(f"    ... ({len(colored) - 40} more not shown)")


def render_page_to_png(pdf_path: Path, page_num: int) -> Path:
    """Render page (0-indexed) to PNG using pypdfium2; return output path."""
    try:
        import pypdfium2 as pdfium
    except ImportError:
        log.error("pypdfium2 not installed; run: pip install pypdfium2")
        sys.exit(1)

    pdf = pdfium.PdfDocument(str(pdf_path))
    page = pdf[page_num]
    bitmap = page.render(scale=2.0)
    img = bitmap.to_pil()

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    out = FIGURES_DIR / f"{pdf_path.stem}_p{page_num + 1}.png"
    img.save(out)
    log.info(f"Rendered page {page_num + 1} → {out}")
    return out


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspect a PDF: show text, tables, coloured rects, optionally render."
    )
    parser.add_argument("pdf", help="Path to PDF file")
    parser.add_argument("--pages", default=None,
                        help="Page range to show, e.g. '1-3' or '1,2' (default: all)")
    parser.add_argument("--tables", action="store_true", help="Print extracted tables")
    parser.add_argument("--rects", action="store_true",
                        help="Print coloured rectangles per page")
    parser.add_argument("--render", type=int, default=None, metavar="PAGE",
                        help="Render this page number (1-indexed) to PNG")
    parser.add_argument("--no-text", action="store_true", help="Suppress page text")
    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        log.error(f"File not found: {pdf_path}")
        sys.exit(1)

    with pdfplumber.open(pdf_path) as pdf:
        n = len(pdf.pages)
        log.info(f"{pdf_path.name}: {n} pages")

        page_indices = (
            parse_page_range(args.pages, n)
            if args.pages
            else list(range(n))
        )

        if len(page_indices) > 10 and not args.pages:
            log.warning(
                f"PDF has {n} pages; showing first 5 by default. "
                "Use --pages 1-N to see more."
            )
            page_indices = page_indices[:5]

        for pi in page_indices:
            page = pdf.pages[pi]

            if not args.no_text:
                print_page_text(page, pi)
            if args.tables:
                print_tables(page, pi)
            if args.rects:
                print_rects(page, pi)

    if args.render is not None:
        out = render_page_to_png(pdf_path, args.render - 1)
        print(f"\nRendered → {out}")


if __name__ == "__main__":
    main()

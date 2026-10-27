"""Shared utilities for the Astypalea iPOY data pipeline."""
import hashlib
import logging
import random
import re
import time
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ── Paths ──────────────────────────────────────────────────────────────────────
IPOY_ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = IPOY_ROOT / "data" / "raw"
DATA_PROCESSED = IPOY_ROOT / "data" / "processed"
FIGURES_DIR = DATA_PROCESSED / "figures"

HEDNO_SECTIONS = ("yearly_actuals", "weekly_actuals", "yearly_forecasts", "weekly_forecasts")


def setup_dirs() -> None:
    for d in [
        DATA_RAW / "hedno" / "yearly_actuals",
        DATA_RAW / "hedno" / "weekly_actuals",
        DATA_RAW / "hedno" / "yearly_forecasts",
        DATA_RAW / "hedno" / "weekly_forecasts",
        DATA_RAW / "bulletins",
        DATA_RAW / "raaey",
        DATA_PROCESSED,
        FIGURES_DIR,
    ]:
        d.mkdir(parents=True, exist_ok=True)


def setup_logging(name: str, level: int = logging.INFO) -> logging.Logger:
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=level,
    )
    return logging.getLogger(name)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ── HTTP ───────────────────────────────────────────────────────────────────────

class RateLimitedSession:
    """requests.Session with polite rate-limiting and automatic retry."""

    def __init__(self, min_delay: float = 1.0, max_delay: float = 2.0):
        self.min_delay = min_delay
        self.max_delay = max_delay
        self._last: float = 0.0

        self.session = requests.Session()
        retry = Retry(
            total=4,
            backoff_factor=2.0,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "HEAD"],
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.session.headers["User-Agent"] = (
            "Mozilla/5.0 (compatible; IPoY-research/1.0; "
            "student-project InnoEnergy SELECT; non-commercial)"
        )

    def _wait(self) -> None:
        elapsed = time.time() - self._last
        delay = random.uniform(self.min_delay, self.max_delay)
        if elapsed < delay:
            time.sleep(delay - elapsed)
        self._last = time.time()

    def get(self, url: str, **kw) -> requests.Response:
        self._wait()
        return self.session.get(url, timeout=60, **kw)

    def download(self, url: str, dest: Path) -> requests.Response:
        """Stream-download url to dest; dest parent is created if needed."""
        self._wait()
        dest.parent.mkdir(parents=True, exist_ok=True)
        r = self.session.get(url, stream=True, timeout=120)
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(65536):
                f.write(chunk)
        return r


# ── Number parsing ─────────────────────────────────────────────────────────────

def parse_greek_number(s: str) -> float | None:
    """Parse a Greek-locale number string (decimal comma, dot thousands-sep).

    "1.234,56" → 1234.56   "0,631" → 0.631   "1,1" → 1.1
    Returns None for blank / dash / non-numeric strings.
    """
    if s is None:
        return None
    s = s.strip()
    if not s or s in ("-", "—", "–", "N/A", "n/a", "ΔΥ", "−"):
        return None
    # Remove thousands dots (a dot followed by exactly three digits before a comma or end)
    s = re.sub(r"\.(?=\d{3}(?:[,\s]|$))", "", s)
    s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def parse_date_str(s: str) -> str | None:
    """Normalise a date string to YYYY-MM-DD. Returns None on failure."""
    from datetime import datetime

    s = s.strip()
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    # Try Greek month names → not needed for numeric dates; skip
    return None


# ── Timezone helpers ───────────────────────────────────────────────────────────

def make_timestamps(date_iso: str, hour: int) -> tuple[str, str]:
    """Return (timestamp_local_iso, timestamp_utc_iso) for a date+hour in Athens time.

    Handles DST ambiguity by appending a warning suffix instead of raising.
    Raises ValueError if date_iso cannot be parsed.
    """
    from datetime import datetime, timezone
    import pytz

    athens = pytz.timezone("Europe/Athens")
    naive = datetime(
        int(date_iso[:4]), int(date_iso[5:7]), int(date_iso[8:10]),
        hour, 0, 0
    )
    try:
        local = athens.localize(naive, is_dst=None)  # raises on ambiguous/nonexistent
    except pytz.exceptions.AmbiguousTimeError:
        # Fall-back: pick the first occurrence (DST still in effect)
        local = athens.localize(naive, is_dst=True)
        local_str = local.isoformat() + "?DST_AMBIGUOUS"
        utc_str = local.astimezone(timezone.utc).isoformat()
        return local_str, utc_str
    except pytz.exceptions.NonExistentTimeError:
        # Spring-forward gap: record NaT with a note
        return f"{date_iso}T{hour:02d}:00:00+LOCAL_NONEXISTENT", ""

    utc = local.astimezone(timezone.utc)
    return local.isoformat(), utc.isoformat()

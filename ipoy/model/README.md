# Stage 0: Unit Commitment Check — Astypalea Diesel Station

This is a **simulation model**, not a digital twin.  It checks whether a
cost-optimal unit commitment of the four-unit diesel fleet reproduces HEDNO's
observed commitment over Sep 2025 – Aug 2026.  The gap between the two reveals
HEDNO's implicit reserve rule (DATA_NOTES Q4).

---

## How to run

```bash
cd ipoy/
source .venv/bin/activate   # installs pypsa and highspy

# Full run (all 20 variants × 12 months; takes ~5–15 min)
python model/stage0.py

# Quick check: first month only
python model/stage0.py --dry-run

# Tests
python -m pytest model/tests/ -v
```

The first run downloads a PVGIS hourly PV series (~2 s, requires internet)
and caches it in `model/data/`.  All subsequent runs use the cache.

---

## Files

| File | Description |
|------|-------------|
| `config.yaml` | All model parameters with source and status |
| `network.py` | PyPSA network builder, PVGIS download, availability logic |
| `stage0.py` | Month-by-month optimisation, comparison, figures, report |
| `tests/test_network.py` | Build, energy balance, one-day solve |
| `results/stage0_report.md` | Committed — full comparison report |
| `results/fig_unit_count.png` | Committed — hourly unit count figure |
| `results/fig_monthly_mwh.png` | Committed — monthly diesel MWh figure |
| `results/stage0_*.parquet` | **Gitignored** — raw hourly results per variant |
| `data/` | **Gitignored** — PVGIS cache |

---

## Variants

**20 combinations** = 5 reserve variants × 2 load bases × 2 letter availability modes.

### Reserve variants

| Variant | Constraint |
|---------|-----------|
| A | None — minimum-cost dispatch only |
| B | Online capacity ≥ load + 1.1 MW (N-1 spinning reserve) |
| C_020 | Online capacity ≥ load × 1.2 |
| C_050 | Online capacity ≥ load × 1.5 |
| C_100 | Online capacity ≥ load × 2.0 |

### Load basis

| Mode | Meaning | DATA_NOTES ref |
|------|---------|----------------|
| `net` | `demand_mw` is diesel-station output; PV excluded | Q1 |
| `gross` | `demand_mw` is total island demand; 0.32 MW PV modelled as zero-cost generator | Q1 |

Neither interpretation is confirmed.  See DATA_NOTES Q1 evidence table.

### Letter availability

| Mode | G_status = maintenance or fault |
|------|--------------------------------|
| `unavailable` | Unit unavailable that hour (p_max_pu = 0) |
| `ignored` | Unit treated as available (maintenance disregarded) |

The cell colours (grey = maintenance, near-black = fault) are verified in
DATA_NOTES §1b.  The operational meaning (unit truly offline vs. scheduled
but available) is open question Q2.

---

## Assumptions

All parameters except `p_nom` (1.1 MW per unit, verified from HEDNO PDF) are assumptions.

| Parameter | Value | Source / Notes |
|-----------|-------|---------------|
| `p_nom` | 1.1 MW | Verified: HEDNO weekly PDF row 1 (§1b) |
| `p_min_pu` | 0.30 | Assumption: Mitsubishi S16R-PTA datasheet (not confirmed for Astypalea) |
| `min_up_time` | 1 h | Assumption: typical for ~1 MW diesel; coarsest at 1-h resolution |
| `min_down_time` | 1 h | Assumption: same |
| `start_up_cost` | 10 EUR | Assumption: order-of-magnitude warm-up fuel estimate |
| `marginal_cost` | 350 EUR/MWh | Assumption: midpoint of 2025 bulletin ΜΜΚ (295–515 EUR/MWh) |
| PV `p_nom` | 0.32 MW | Verified: bulletin Table 3 (§1e) |
| PV profile | PVGIS SARAH3 2022 | Assumption: single representative year |

---

## What the results do and do not show

**Do show:**
- Which reserve variant is most consistent with HEDNO's observed commitment counts
- Whether load basis (gross vs net) matters for the comparison
- Whether maintenance availability interpretation matters
- Which months and hours of day have the largest gaps

**Do not show:**
- Unit identity (G5 vs G6 etc.) — the four units are modelled identically
- Per-unit fuel consumption or emissions
- The effect of BESS or solar hybrid (post-2026 project)
- Whether HEDNO follows any of these reserve rules explicitly

**Known limitations:**
- Month-boundary discontinuity: min-up/down constraints do not span month edges
- G8 appears always 0 in the parsed CSV (possible parser coverage gap for the 222 G8=1 hours in DATA_NOTES)
- Three missing weeks are excluded without imputation
- PVGIS profile is a single year; PV contribution is small (0.32 MW) and the effect on gross vs net comparison is modest

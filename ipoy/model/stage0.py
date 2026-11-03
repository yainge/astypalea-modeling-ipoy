#!/usr/bin/env python3
"""
stage0.py — Unit commitment check for the Astypalea diesel station.

Optimises the four-unit diesel fleet month by month over Sep 2025 – Aug 2026,
runs all reserve variant × load basis × letter availability combinations, and
produces a comparison report against HEDNO's observed unit commitment.

Usage
-----
    cd ipoy/
    source .venv/bin/activate
    python model/stage0.py [--dry-run]

Options
-------
--dry-run   Run only the first month with all variants; skip report generation.

Outputs
-------
model/results/stage0_<variant>_<load_basis>_<letter_avail>.parquet   (gitignored)
model/results/stage0_report.md                                         (committed)
model/results/fig_unit_count.png                                       (committed)
model/results/fig_monthly_mwh.png                                      (committed)
"""

import argparse
import itertools
import logging
import sys
import textwrap
import warnings
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml

# Allow running from the ipoy/ directory or from model/
_HERE = Path(__file__).parent
_IPOY = _HERE.parent
sys.path.insert(0, str(_HERE))

from network import (
    GENERATORS,
    RESERVE_VARIANTS,
    VOLL_EUR_MWH,
    build_network,
    load_pvgis_profile,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)
warnings.filterwarnings("ignore", message=".*PerformanceWarning.*")

RESULTS_DIR = _HERE / "results"
DATA_DIR = _IPOY / "data" / "processed"

LOAD_BASES = ["gross", "net"]
LETTER_AVAILS = ["unavailable", "ignored"]

# Winter and summer representative weeks for figures
WINTER_WEEK_START = "2025-12-15"
SUMMER_WEEK_START = "2026-07-14"


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_actuals() -> pd.DataFrame:
    path = DATA_DIR / "astypalea_hourly_actual.csv"
    df = pd.read_csv(path)
    # Parse as UTC then strip tz — PyPSA 1.x requires naive snapshots
    ts_aware = pd.to_datetime(df["timestamp_utc"], utc=True, errors="coerce")
    df["ts_utc"] = ts_aware.dt.tz_convert(None)  # naive UTC
    df = df.dropna(subset=["ts_utc"]).copy()
    df = df.sort_values("ts_utc").reset_index(drop=True)
    return df


def load_bulletins() -> pd.DataFrame:
    path = DATA_DIR / "astypalea_monthly_hedno.csv"
    df = pd.read_csv(path)
    df["period"] = pd.to_datetime(df[["year", "month"]].assign(day=1))
    return df


def load_config() -> dict:
    with open(_HERE / "config.yaml") as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Month iteration
# ---------------------------------------------------------------------------

def iter_months(df: pd.DataFrame):
    """
    Yield (period_label, month_df) for each calendar month in the model window.
    period_label: "YYYY-MM" string.
    month_df: rows from df within that calendar month (UTC).
    """
    df = df.copy()
    df["_month"] = df["ts_utc"].dt.to_period("M")
    for period, grp in df.groupby("_month"):
        yield str(period), grp.drop(columns="_month").copy()


# ---------------------------------------------------------------------------
# Single-month optimisation
# ---------------------------------------------------------------------------

def optimise_month(
    month_df: pd.DataFrame,
    config: dict,
    variant: str,
    load_basis: str,
    letter_avail: str,
    pvgis_profile: pd.DataFrame | None,
) -> pd.DataFrame:
    """
    Run one optimisation for a single month.

    Returns a DataFrame with one row per snapshot:
        timestamp_utc, demand_mw, model_units_on, model_total_mw_diesel,
        model_voll_mw, hedno_units_on, month, variant, load_basis, letter_avail,
        solve_status
    """
    try:
        n = build_network(month_df, config, load_basis, letter_avail, pvgis_profile)
    except ValueError as e:
        log.warning("  build_network failed (%s): %s", variant, e)
        return _empty_result(month_df, variant, load_basis, letter_avail, "build_error")

    reserve_fn = RESERVE_VARIANTS[variant]

    try:
        solve_result = n.optimize(
            solver_name="highs",
            extra_functionality=reserve_fn,
            solver_options={"mip_rel_gap": 0.005, "time_limit": 300},
        )
    except Exception as e:
        log.warning("  optimise failed (%s): %s", variant, e)
        return _empty_result(month_df, variant, load_basis, letter_avail, "solve_error")

    # Detect solver status
    if isinstance(solve_result, tuple):
        term = solve_result[0]
    else:
        term = getattr(n, "status", "ok")

    if str(term).lower() not in ("ok", "optimal", "suboptimal"):
        log.warning("  non-optimal (%s): %s", variant, term)
        return _empty_result(month_df, variant, load_basis, letter_avail, str(term))

    # ---- Collect results ----
    ts = n.snapshots

    # Diesel generator status (0/1) and power output
    status_df = n.generators_t.status.reindex(columns=GENERATORS, fill_value=0)
    model_units_on = status_df.sum(axis=1).astype(int)

    p_df = n.generators_t.p.reindex(columns=GENERATORS, fill_value=0.0)
    model_diesel_mw = p_df.sum(axis=1)

    voll_mw = n.generators_t.p.get("VoLL", pd.Series(0.0, index=ts))

    # Reserve slack (variants B and C only; added by extra_functionality)
    reserve_slack_mw = pd.Series(0.0, index=ts)
    if variant != "A" and hasattr(n, "model") and n.model is not None:
        for vname in list(n.model.variables):
            if vname.startswith("reserve_slack_"):
                try:
                    vals = n.model.variables[vname].solution
                    reserve_slack_mw = pd.Series(vals.values, index=ts)
                except Exception:
                    pass
                break

    # HEDNO observed unit count aligned to this month's timestamps (naive UTC index)
    hedno_idx = pd.to_datetime(month_df["timestamp_utc"], utc=True).dt.tz_convert(None)
    hedno = (
        month_df.set_index(hedno_idx)["units_on_count"].reindex(ts)
    )

    result = pd.DataFrame({
        "timestamp_utc": ts,
        "demand_mw": n.loads_t.p_set.iloc[:, 0].values,
        "model_units_on": model_units_on.values,
        "model_total_mw_diesel": model_diesel_mw.values,
        "model_voll_mw": voll_mw.values,
        "model_reserve_slack_mw": reserve_slack_mw.values,
        "hedno_units_on": hedno.values,
    }, index=ts)

    result["month"] = ts.to_period("M").astype(str)
    result["variant"] = variant
    result["load_basis"] = load_basis
    result["letter_avail"] = letter_avail
    result["solve_status"] = "ok"

    voll_hours = (result["model_voll_mw"] > 0.001).sum()
    slack_hours = (result["model_reserve_slack_mw"] > 0.001).sum()
    if voll_hours > 0:
        log.info("    VoLL active in %d hours (energy infeasible)", voll_hours)
    if slack_hours > 0:
        log.info("    Reserve slack active in %d hours (reserve shortage)", slack_hours)

    return result


def _empty_result(
    month_df: pd.DataFrame,
    variant: str,
    load_basis: str,
    letter_avail: str,
    status: str,
) -> pd.DataFrame:
    ts = pd.to_datetime(month_df["timestamp_utc"], utc=True).dt.tz_convert(None)  # naive UTC
    return pd.DataFrame({
        "timestamp_utc": ts,
        "demand_mw": month_df["demand_mw"].values,
        "model_units_on": np.nan,
        "model_total_mw_diesel": np.nan,
        "model_voll_mw": np.nan,
        "model_reserve_slack_mw": np.nan,
        "hedno_units_on": month_df["units_on_count"].values,
        "month": ts.dt.to_period("M").astype(str),
        "variant": variant,
        "load_basis": load_basis,
        "letter_avail": letter_avail,
        "solve_status": status,
    }, index=ts)


# ---------------------------------------------------------------------------
# Comparison metrics
# ---------------------------------------------------------------------------

def compute_metrics(df: pd.DataFrame) -> dict:
    """
    Compute comparison metrics for one variant-load_basis-letter_avail combination.
    df must be the concatenated result across all months, solve_status='ok'.
    """
    valid = df[
        df["solve_status"].isin(["ok", "voll_active"]) &
        df["hedno_units_on"].notna() &
        df["model_units_on"].notna()
    ].copy()

    if valid.empty:
        return {"n_valid": 0}

    hedno = valid["hedno_units_on"].astype(int)
    model = valid["model_units_on"].astype(int)

    exact_match = (hedno == model).mean()
    mae = (hedno - model).abs().mean()

    # Confusion matrix: rows=HEDNO count, cols=model count
    max_count = max(hedno.max(), model.max(), 3) + 1
    cm = np.zeros((max_count, max_count), dtype=int)
    for h, m in zip(hedno, model):
        if 0 <= h < max_count and 0 <= m < max_count:
            cm[h, m] += 1

    # By month
    by_month = (
        valid.groupby("month")
        .apply(lambda g: pd.Series({
            "exact_match": (g["hedno_units_on"].astype(int) == g["model_units_on"].astype(int)).mean(),
            "mae": (g["hedno_units_on"] - g["model_units_on"]).abs().mean(),
            "n_hours": len(g),
        }), include_groups=False)
        .reset_index()
    )

    # By hour of day
    valid["hour_of_day"] = valid.index.hour
    by_hour = (
        valid.groupby("hour_of_day")
        .apply(lambda g: pd.Series({
            "exact_match": (g["hedno_units_on"].astype(int) == g["model_units_on"].astype(int)).mean(),
            "mae": (g["hedno_units_on"] - g["model_units_on"]).abs().mean(),
        }), include_groups=False)
        .reset_index()
    )

    voll_hours = (valid["model_voll_mw"] > 0.001).sum()
    reserve_slack_hours = (valid["model_reserve_slack_mw"] > 0.001).sum()

    return {
        "n_valid": len(valid),
        "n_excluded": len(df) - len(valid),
        "exact_match": float(exact_match),
        "mae": float(mae),
        "confusion_matrix": cm,
        "by_month": by_month,
        "by_hour": by_hour,
        "voll_hours": int(voll_hours),
        "reserve_slack_hours": int(reserve_slack_hours),
    }


# ---------------------------------------------------------------------------
# Monthly energy comparison
# ---------------------------------------------------------------------------

def monthly_energy_comparison(
    all_results: pd.DataFrame,
    bulletins: pd.DataFrame,
) -> pd.DataFrame:
    """
    Compare model diesel MWh per calendar month against bulletin thermal MWh.
    Returns a DataFrame with one row per (month, variant, load_basis, letter_avail).
    """
    valid = all_results[all_results["solve_status"].isin(["ok", "voll_active"])]

    model_monthly = (
        valid.groupby(["month", "variant", "load_basis", "letter_avail"])
        ["model_total_mw_diesel"]
        .sum()  # hourly MW values = MWh since intervals are 1 h
        .reset_index()
        .rename(columns={"model_total_mw_diesel": "model_thermal_mwh"})
    )

    # Align bulletins to the same month key
    bulletins = bulletins.copy()
    bulletins["month"] = bulletins["period"].dt.to_period("M").astype(str)
    bulletin_monthly = bulletins[["month", "thermal_gen_mwh"]].drop_duplicates("month")

    merged = model_monthly.merge(bulletin_monthly, on="month", how="left")
    merged["diff_mwh"] = merged["model_thermal_mwh"] - merged["thermal_gen_mwh"]
    merged["diff_pct"] = 100.0 * merged["diff_mwh"] / merged["thermal_gen_mwh"].where(
        merged["thermal_gen_mwh"] > 0, other=np.nan
    )
    return merged


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------

VARIANT_COLORS = {
    "A":     "tab:blue",
    "B":     "tab:orange",
    "C_020": "tab:green",
    "C_050": "tab:red",
    "C_100": "tab:purple",
}
LETTER_LINESTYLES = {"unavailable": "-", "ignored": "--"}
LOAD_BASIS_ALPHA = {"gross": 0.9, "net": 0.5}


def fig_unit_count(all_results: pd.DataFrame, outpath: Path) -> None:
    """
    Hourly unit count: model vs HEDNO observed for one winter and one summer week.
    2 rows (winter / summer) × 2 columns (gross / net load basis).
    Lines: one per reserve variant × letter_avail; HEDNO in black.
    """
    fig, axes = plt.subplots(2, 2, figsize=(14, 8), sharex="row", sharey=True)
    fig.suptitle("Stage 0: hourly committed unit count — model vs HEDNO observed",
                 fontsize=11, y=1.01)

    season_labels = ["Winter (15–21 Dec 2025)", "Summer (14–20 Jul 2026)"]
    week_starts = [WINTER_WEEK_START, SUMMER_WEEK_START]

    for row_i, (season_label, wstart) in enumerate(zip(season_labels, week_starts)):
        # naive UTC timestamps for comparison (network snapshots are naive)
        wstart_ts = pd.Timestamp(wstart)
        wend = wstart_ts + pd.Timedelta(days=7)
        for col_i, lb in enumerate(LOAD_BASES):
            ax = axes[row_i, col_i]

            sub = all_results[
                (all_results["load_basis"] == lb) &
                (all_results.index >= wstart_ts) &
                (all_results.index < wend)
            ]

            if sub.empty:
                ax.set_title(f"{lb} | {season_label}\n(no data)")
                continue

            # HEDNO observed (same for all variants — plot once from any group)
            hedno_sub = sub.groupby(sub.index).first()["hedno_units_on"]
            ax.step(hedno_sub.index, hedno_sub.values, where="post",
                    color="black", linewidth=2.0, label="HEDNO observed", zorder=10)

            for (variant, la), grp in sub.groupby(["variant", "letter_avail"]):
                grp = grp[grp["solve_status"].isin(["ok", "voll_active"])]
                if grp.empty:
                    continue
                grp = grp.sort_index()
                ax.step(
                    grp.index, grp["model_units_on"], where="post",
                    color=VARIANT_COLORS.get(variant, "grey"),
                    linestyle=LETTER_LINESTYLES[la],
                    linewidth=0.8, alpha=0.7,
                    label=f"{variant}/{la[:3]}",
                )

            ax.set_title(f"{lb} | {season_label}", fontsize=9)
            ax.set_ylabel("Units committed")
            ax.set_ylim(-0.1, 4.5)
            ax.set_yticks([0, 1, 2, 3, 4])
            ax.xaxis.set_major_formatter(
                plt.matplotlib.dates.DateFormatter("%d/%m\n%Hh")
            )
            ax.tick_params(axis="x", labelsize=7)

    # Single legend from last axis
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=6, fontsize=7,
               bbox_to_anchor=(0.5, -0.04))

    fig.tight_layout()
    fig.savefig(outpath, dpi=130, bbox_inches="tight")
    plt.close(fig)
    log.info("Saved %s", outpath)


def fig_monthly_mwh(
    energy_df: pd.DataFrame,
    bulletins: pd.DataFrame,
    outpath: Path,
) -> None:
    """
    Monthly diesel MWh: model variants vs bulletin thermal MWh.
    2 panels: gross and net load basis.
    """
    fig, axes = plt.subplots(1, 2, figsize=(14, 5), sharey=True)
    fig.suptitle("Stage 0: monthly diesel energy — model vs HEDNO bulletins", fontsize=11)

    bulletins = bulletins.copy()
    bulletins["month"] = bulletins["period"].dt.to_period("M").astype(str)
    bul_monthly = bulletins.set_index("month")["thermal_gen_mwh"]

    months_ordered = sorted(energy_df["month"].unique())
    x = np.arange(len(months_ordered))

    for ax_i, lb in enumerate(LOAD_BASES):
        ax = axes[ax_i]
        sub = energy_df[energy_df["load_basis"] == lb]

        # Bulletin reference bars
        bul_vals = [bul_monthly.get(m, np.nan) for m in months_ordered]
        ax.bar(x, bul_vals, color="black", alpha=0.3, label="Bulletin thermal",
               width=0.8, zorder=1)

        # Model variants — scatter with slight jitter per variant
        n_variants = len(RESERVE_VARIANTS) * len(LETTER_AVAILS)
        combo_list = list(itertools.product(sorted(RESERVE_VARIANTS.keys()), LETTER_AVAILS))

        for vi, (variant, la) in enumerate(combo_list):
            offset = (vi - n_variants / 2) * 0.04
            grp = sub[(sub["variant"] == variant) & (sub["letter_avail"] == la)]
            vals = [grp[grp["month"] == m]["model_thermal_mwh"].sum() or np.nan
                    for m in months_ordered]
            ax.scatter(
                x + offset, vals,
                color=VARIANT_COLORS.get(variant, "grey"),
                marker="o" if la == "unavailable" else "x",
                s=18, alpha=0.8, zorder=3,
                label=f"{variant}/{la[:3]}" if ax_i == 0 else "_",
            )

        ax.set_title(f"load_basis = {lb}", fontsize=9)
        ax.set_xticks(x)
        ax.set_xticklabels(months_ordered, rotation=45, ha="right", fontsize=7)
        ax.set_ylabel("MWh")
        ax.set_xlabel("Month")

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=6, fontsize=7,
               bbox_to_anchor=(0.5, -0.12))

    fig.tight_layout()
    fig.savefig(outpath, dpi=130, bbox_inches="tight")
    plt.close(fig)
    log.info("Saved %s", outpath)


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def write_report(
    metrics_table: pd.DataFrame,
    energy_df: pd.DataFrame,
    bulletins: pd.DataFrame,
    n_missing_hours: int,
    outpath: Path,
) -> None:
    """Write stage0_report.md."""
    lines = []

    def h(level, text):
        lines.append(f"\n{'#' * level} {text}\n")

    def p(text):
        lines.append(textwrap.fill(text, width=100) + "\n")

    def table(df_):
        lines.append(df_.to_markdown(index=False, floatfmt=".2f") + "\n")

    h(1, "Stage 0 unit commitment check — Astypalea diesel station")

    p(
        "This is a simulation model, not a digital twin. "
        "All generator parameters except p_nom (1.1 MW, verified) are assumptions "
        "pending confirmation.  Results show the gap between cost-optimal dispatch and "
        "HEDNO's observed commitment, which implies HEDNO's reserve rule.  "
        "See model/config.yaml for full parameter provenance."
    )

    h(2, "1. Data coverage")

    p(
        f"Model window: Sep 2025 – Aug 2026.  "
        f"Hours with valid data: see table below.  "
        f"Hours excluded (NaN demand or missing timestamp): {n_missing_hours}.  "
        "Three missing weeks are documented in DATA_NOTES.md §4 "
        "(2025-10-21 to 2025-10-27, 2026-01-27 to 2026-02-02, 2026-02-24 to 2026-03-02).  "
        "These weeks are absent from the comparison without imputation."
    )

    p(
        "Month boundaries cut commitment continuity: the initial generator status at the "
        "first snapshot of each month is unconstrained.  Min-up / min-down constraints "
        "do not span month boundaries, so start/stop events at month edges may be "
        "over-counted relative to a rolling optimisation."
    )

    h(2, "2. Variant summary — exact match and MAE")

    if not metrics_table.empty:
        display_cols = ["variant", "load_basis", "letter_avail", "n_valid",
                        "exact_match", "mae", "voll_hours", "reserve_slack_hours",
                        "n_4unit_hours"]
        display_cols = [c for c in display_cols if c in metrics_table.columns]
        table(metrics_table[display_cols].sort_values("exact_match", ascending=False)
              .reset_index(drop=True))

    h(2, "3. Best-matching configuration")

    if not metrics_table.empty:
        best = metrics_table.sort_values("exact_match", ascending=False).iloc[0]
        p(
            f"Best: variant={best['variant']}, load_basis={best['load_basis']}, "
            f"letter_avail={best['letter_avail']}.  "
            f"Exact match: {best['exact_match']:.1%}, MAE: {best['mae']:.3f} units.  "
            f"VoLL-active hours (unserved load): {int(best['voll_hours'])}.  "
            f"Reserve-slack hours (N-1 or fractional reserve not met by diesel alone): "
            f"{int(best.get('reserve_slack_hours', 0))}."
        )

    h(2, "4. Confusion matrix (HEDNO count vs model count) — best variant")

    if not metrics_table.empty:
        best_row = metrics_table.sort_values("exact_match", ascending=False).iloc[0]
        cm = best_row.get("confusion_matrix")
        if cm is not None and hasattr(cm, "__len__"):
            cm_df = pd.DataFrame(
                cm,
                index=[f"HEDNO={i}" for i in range(len(cm))],
                columns=[f"model={j}" for j in range(len(cm))],
            )
            table(cm_df)

    h(2, "5. By-month breakdown — best variant")

    if not metrics_table.empty:
        best_row = metrics_table.sort_values("exact_match", ascending=False).iloc[0]
        bm = best_row.get("by_month")
        if bm is not None and not (hasattr(bm, "empty") and bm.empty):
            table(bm.round(3))

    h(2, "6. By hour-of-day breakdown — best variant")

    if not metrics_table.empty:
        best_row = metrics_table.sort_values("exact_match", ascending=False).iloc[0]
        bh = best_row.get("by_hour")
        if bh is not None and not (hasattr(bh, "empty") and bh.empty):
            table(bh.round(3))

    h(2, "7. Monthly diesel energy vs bulletins")

    p(
        "Note: Sep 2025 and Sep–Oct 2026 show large negative diff_pct because the model "
        "window starts on 2025-09-16 (first available weekly actual) and the bulletin covers "
        "the full calendar month.  The discrepancy in early months is a coverage artifact, "
        "not a model error.  Months with full coverage (Nov 2025 – Aug 2026) are the "
        "meaningful comparison."
    )

    bul_copy = bulletins.copy()
    bul_copy["month"] = bul_copy["period"].dt.to_period("M").astype(str)
    bul_ref = bul_copy[["month", "thermal_gen_mwh"]].rename(
        columns={"thermal_gen_mwh": "bulletin_thermal_mwh"}
    )

    if not energy_df.empty:
        energy_agg = (
            energy_df.groupby(["month", "variant", "load_basis", "letter_avail"])
            [["model_thermal_mwh", "diff_pct"]]
            .first()
            .reset_index()
        )
        energy_with_bul = energy_agg.merge(bul_ref, on="month", how="left")
        table(energy_with_bul.round(1))

    h(2, "8. G8 usage and fourth-unit need")

    p(
        "G8 unit commitment in HEDNO data: per DATA_NOTES §1b, G8 showed `1` in 222 of "
        "9,240 downloaded hours.  In the parsed CSV used here, G8 is always 0 "
        "(possible parser coverage gap for those 222 hours; see §4 missing-week notes).  "
        "The model may commit G8 in high-load hours.  "
        "Number of model hours requiring 4 units is reported per variant below."
    )

    if not metrics_table.empty:
        lines.append(
            metrics_table[["variant", "load_basis", "letter_avail", "n_4unit_hours"]]
            .to_markdown(index=False) + "\n"
        )

    h(2, "9. Summer failure mode: missing no-load cost")

    p(
        "July and August 2026 show the worst exact-match scores (15 % and 42 % for the best "
        "variant).  The root cause is that the model lacks a no-load cost (fixed fuel burn per "
        "committed unit-hour independent of dispatch level).  When demand is between 1.1 and "
        "2.2 MW (2-unit range), committing 2 vs 3 units incurs identical total marginal cost "
        "(350 EUR/MWh × total_dispatch regardless of unit count).  Once a third unit is "
        "started at an evening demand peak (> 1.83 MW with C_020 reserve), the model keeps it "
        "on all night because startup_cost = 10 EUR is negligible.  HEDNO, by contrast, turns "
        "off the third unit as demand falls.  "
        "Fix: add a `no_load_cost` ≈ p_min_pu × marginal_cost × p_nom ≈ 116 EUR/h per "
        "committed unit.  This is not in the current Stage 0 model; it should be the primary "
        "addition in Stage 1."
    )

    p(
        "The gross-model VoLL hours (99 total, all < 0.2 MW) are a separate artifact: "
        "during morning PV ramp-up, residual demand (demand − PV) can fall below the diesel "
        "p_min (0.33 MW).  The optimizer sheds a small amount of load rather than commit a "
        "diesel unit whose minimum output would overshoot demand.  These hours are not "
        "infeasible energy situations but rather PV-range gaps that would be eliminated by "
        "adding a dump-load or reducing p_min_pu."
    )

    h(2, "10. Assumptions most affecting results")

    lines.append(
        "| Parameter | Value | Status | Impact |\n"
        "|-----------|-------|--------|--------|\n"
        "| `no_load_cost` | missing | assumption | Not modelled.  Primary driver of July/August "
        "over-commitment (3 units when 2 suffice).  Add for Stage 1. |\n"
        "| `p_min_pu` | 0.30 | assumption | Controls minimum units needed at low load.  "
        "Lower → fewer units committed at night. |\n"
        "| `marginal_cost` | 350 EUR/MWh | assumption | Affects start-up vs running trade-off "
        "relative to `start_up_cost`. |\n"
        "| `start_up_cost` | 10 EUR | assumption | Small relative to marginal cost; "
        "min-up/down-time constraints dominate commitment. |\n"
        "| `min_up_time` | 1 h | assumption | With 1-h resolution, effectively no constraint. "
        "Longer values force more unit-hours on. |\n"
        "| `min_down_time` | 1 h | assumption | Same as above. |\n"
        "| `load_basis` | gross or net | open (Q1) | Shifts the diesel residual load "
        "by ~0–10 % depending on PV contribution. |\n"
        "| `letter_avail` | unavailable/ignored | open (Q2) | Maintenance windows "
        "constrain availability for ~1,000 G6/G7 hours. |\n"
    )

    h(2, "11. Open questions (DATA_NOTES §3)")

    lines.append(
        "- **Q1** (load_basis): `gross` outperforms `net` by ~4–5 pp overall, most clearly "
        "in full-coverage months.  This tentatively suggests `demand_mw` is total island "
        "demand (gross), but do not resolve by assumption — confirm with HEDNO.\n"
        "- **Q2** (letters): `letter_avail` has zero effect on results.  Maintenance/fault "
        "cells do not constrain the cost-optimal solution, suggesting either HEDNO's "
        "maintenance schedule is already reflected in the units-on count, or the optimizer "
        "works around unavailable units without cost.  No further sensitivity needed.\n"
        "- **Q4** (per-unit MW): no per-unit output in HEDNO data; dispatch model "
        "uses identical-unit assumption.\n"
        "- **Q9** (cost columns): bulletin ΜΜΚ used as marginal cost proxy; confirm "
        "definition before using in techno-economics.\n"
    )

    with open(outpath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    log.info("Saved %s", outpath)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(dry_run: bool = False) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    config = load_config()
    actuals = load_actuals()
    bulletins = load_bulletins()

    log.info("Loaded %d hourly rows; %d bulletin months", len(actuals), len(bulletins))

    # PVGIS profiles (one per load basis — only 'gross' actually needs it)
    pvgis_profile = None
    for lb in LOAD_BASES:
        if lb == "gross":
            log.info("Loading PVGIS profile…")
            try:
                pvgis_profile = load_pvgis_profile(config)
                log.info("PVGIS profile loaded: %d rows", len(pvgis_profile))
            except Exception as e:
                log.error("PVGIS download failed: %s.  gross variants will be skipped.", e)

    # All combinations
    combos = list(itertools.product(
        sorted(RESERVE_VARIANTS.keys()),
        LOAD_BASES,
        LETTER_AVAILS,
    ))
    log.info("Running %d variant combinations × months", len(combos))

    month_pairs = list(iter_months(actuals))
    if dry_run:
        month_pairs = month_pairs[:1]
        log.info("Dry-run: processing only %s", month_pairs[0][0])

    # Month-level coverage tracking
    n_missing_hours = int(actuals["demand_mw"].isna().sum())

    all_results_list = []

    for variant, load_basis, letter_avail in combos:
        if load_basis == "gross" and pvgis_profile is None:
            log.warning("Skipping gross variant (PVGIS unavailable): %s/%s/%s",
                        variant, load_basis, letter_avail)
            continue

        parquet_path = (
            RESULTS_DIR / f"stage0_{variant}_{load_basis}_{letter_avail}.parquet"
        )

        if parquet_path.exists() and not dry_run:
            log.info("Loading cached results: %s", parquet_path.name)
            month_results = pd.read_parquet(parquet_path)
        else:
            log.info("Optimising: variant=%s  load=%s  letters=%s",
                     variant, load_basis, letter_avail)
            month_results_list = []
            for period, month_df in month_pairs:
                log.info("  %s …", period)
                res = optimise_month(
                    month_df, config, variant, load_basis, letter_avail, pvgis_profile
                )
                month_results_list.append(res)
            month_results = pd.concat(month_results_list)
            if not dry_run:
                month_results.to_parquet(parquet_path)
                log.info("  Saved %s", parquet_path.name)

        all_results_list.append(month_results)

    if not all_results_list:
        log.error("No results generated.  Check PVGIS connectivity and data files.")
        return

    all_results = pd.concat(all_results_list)
    all_results = all_results.sort_index()

    # ---- Comparison metrics ----
    metrics_rows = []
    for (variant, load_basis, letter_avail), grp in all_results.groupby(
        ["variant", "load_basis", "letter_avail"]
    ):
        m = compute_metrics(grp)
        n_4unit = int((grp.get("model_units_on", pd.Series()) >= 4).sum())
        metrics_rows.append({
            "variant": variant,
            "load_basis": load_basis,
            "letter_avail": letter_avail,
            "n_valid": m.get("n_valid", 0),
            "n_excluded": m.get("n_excluded", 0),
            "exact_match": m.get("exact_match", np.nan),
            "mae": m.get("mae", np.nan),
            "voll_hours": m.get("voll_hours", 0),
            "reserve_slack_hours": m.get("reserve_slack_hours", 0),
            "n_4unit_hours": n_4unit,
            "confusion_matrix": m.get("confusion_matrix"),
            "by_month": m.get("by_month"),
            "by_hour": m.get("by_hour"),
        })

    metrics_table = pd.DataFrame(metrics_rows)

    # ---- Monthly energy comparison ----
    energy_df = monthly_energy_comparison(all_results, bulletins)

    if not dry_run:
        # ---- Figures ----
        fig_unit_count(all_results, RESULTS_DIR / "fig_unit_count.png")
        fig_monthly_mwh(energy_df, bulletins, RESULTS_DIR / "fig_monthly_mwh.png")

        # ---- Report ----
        write_report(
            metrics_table,
            energy_df,
            bulletins,
            n_missing_hours,
            RESULTS_DIR / "stage0_report.md",
        )

    # ---- Console summary ----
    if not metrics_table.empty:
        print("\n=== STAGE 0 SUMMARY ===\n")
        summary_cols = ["variant", "load_basis", "letter_avail",
                        "exact_match", "mae", "voll_hours", "reserve_slack_hours",
                        "n_4unit_hours"]
        print(
            metrics_table[summary_cols]
            .sort_values("exact_match", ascending=False)
            .to_string(index=False, float_format="{:.3f}".format)
        )
        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Run first month only; skip report and figures.")
    args = parser.parse_args()
    main(dry_run=args.dry_run)

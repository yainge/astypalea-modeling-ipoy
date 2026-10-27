"""
06_qa.py — Quality assurance checks and figures for the Astypalea dataset.

Reads:
  data/processed/astypalea_hourly_actual.csv
  data/processed/astypalea_monthly_hedno.csv
  data/processed/astypalea_raaey_2024.csv       (optional)

Writes:
  data/processed/QA_report.md
  data/processed/figures/heatmap_{year}.png
  data/processed/figures/monthly_energy.png
  data/processed/figures/seasonal_profiles.png
  data/processed/figures/tender_vs_actual_2024.png
"""
import sys
import warnings
from datetime import date, timedelta
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from utils import DATA_PROCESSED, FIGURES_DIR, setup_dirs, setup_logging

log = setup_logging("qa")
warnings.filterwarnings("ignore", category=FutureWarning)

# ── Load data ──────────────────────────────────────────────────────────────────

def load_actual() -> pd.DataFrame:
    p = DATA_PROCESSED / "astypalea_hourly_actual.csv"
    if not p.exists():
        raise FileNotFoundError(f"Missing {p}; run 03_parse_actual.py first")
    df = pd.read_csv(p, low_memory=False)
    # Parse timestamps (strip DST annotation suffixes before converting)
    df["ts"] = pd.to_datetime(
        df["timestamp_local"].str.split("?").str[0].str.split("+LOCAL").str[0],
        errors="coerce"
    )
    df = df.dropna(subset=["ts"]).copy()
    df["year"] = df["ts"].dt.year
    df["month"] = df["ts"].dt.month
    df["hour"] = df["ts"].dt.hour
    df["doy"] = df["ts"].dt.day_of_year
    df["demand_mw"] = pd.to_numeric(df["demand_mw"], errors="coerce")
    return df


def load_monthly() -> pd.DataFrame:
    p = DATA_PROCESSED / "astypalea_monthly_hedno.csv"
    if not p.exists():
        return pd.DataFrame()
    df = pd.read_csv(p)
    for col in ("thermal_gen_mwh", "res_gen_mwh", "total_gen_mwh",
                 "res_share_pct", "avg_prod_cost_eur_mwh", "peak_load_mw"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def load_raaey() -> pd.DataFrame:
    p = DATA_PROCESSED / "astypalea_raaey_2024.csv"
    if not p.exists():
        return pd.DataFrame()
    df = pd.read_csv(p)
    df["ts"] = pd.to_datetime(
        df["timestamp_local"].str.split("?").str[0].str.split("+LOCAL").str[0],
        errors="coerce"
    )
    df = df.dropna(subset=["ts"]).copy()
    for col in ("load_kw", "pv_gen_kw", "ev_demand_kw"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


# ── Coverage analysis ──────────────────────────────────────────────────────────

def expected_hours(year: int) -> int:
    return 8784 if (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)) else 8760


def missing_dates(df: pd.DataFrame, year: int) -> list[str]:
    """Return ISO date strings for which no rows exist in that year."""
    start = date(year, 1, 1)
    end = date(year, 12, 31)
    all_dates = {start + timedelta(days=i) for i in range((end - start).days + 1)}
    present = set(df.loc[df["year"] == year, "ts"].dt.date.unique())
    return sorted(str(d) for d in all_dates - present)


def coverage_table(df: pd.DataFrame) -> list[dict]:
    rows = []
    for yr, g in df.groupby("year"):
        exp = expected_hours(yr)
        n = len(g)
        pct = 100 * n / exp
        miss_dates = missing_dates(df, yr)
        ann_mwh = g["demand_mw"].sum()
        peak = g["demand_mw"].max()
        peak_ts = g.loc[g["demand_mw"].idxmax(), "ts"].isoformat() if peak == peak else "N/A"
        rows.append({
            "year": yr, "hours_present": n, "hours_expected": exp,
            "coverage_pct": round(pct, 1),
            "missing_date_count": len(miss_dates),
            "annual_energy_mwh": round(ann_mwh, 1),
            "peak_mw": round(peak, 3) if peak == peak else None,
            "peak_timestamp": peak_ts,
            "missing_dates_sample": "; ".join(miss_dates[:10]),
        })
    return rows


# ── Sanity checks ──────────────────────────────────────────────────────────────

def sanity_checks(df: pd.DataFrame) -> list[str]:
    issues: list[str] = []

    zeros = (df["demand_mw"] == 0).sum()
    if zeros:
        issues.append(f"Zero demand_mw: {zeros} rows")

    negs = (df["demand_mw"] < 0).sum()
    if negs:
        issues.append(f"Negative demand_mw: {negs} rows")

    high = (df["demand_mw"] > 3.0).sum()
    if high:
        issues.append(
            f"demand_mw > 3.0 MW: {high} rows "
            f"(max={df['demand_mw'].max():.3f} MW)"
        )

    # Flat runs ≥ 6 hours
    same = (df["demand_mw"].diff() == 0)
    run_len = same.groupby((~same).cumsum()).cumsum()
    long_flat = (run_len >= 6).sum()
    if long_flat:
        issues.append(f"Flat-line runs ≥ 6 h: {long_flat} rows")

    # Sudden jumps > 1.5 MW in one hour
    diff = df["demand_mw"].diff().abs()
    jumps = (diff > 1.5).sum()
    if jumps:
        issues.append(f"Jumps > 1.5 MW between consecutive rows: {jumps}")

    # Unit capacity check: units_on × 1.1 < demand
    df2 = df.dropna(subset=["units_on_count", "demand_mw"]).copy()
    df2["cap"] = pd.to_numeric(df2["units_on_count"], errors="coerce") * 1.1
    short = (df2["cap"] < df2["demand_mw"] - 0.05).sum()  # 0.05 tolerance
    if short:
        issues.append(f"Hours where units_on×1.1 MW < demand_mw: {short}")

    return issues


# ── Monthly comparison: hourly vs bulletin ─────────────────────────────────────

def monthly_comparison(df: pd.DataFrame, monthly: pd.DataFrame) -> pd.DataFrame:
    """Sum hourly demand per month; join with bulletin totals; compute diff."""
    hourly_monthly = (
        df.groupby(["year", "month"])["demand_mw"]
        .sum()
        .reset_index()
        .rename(columns={"demand_mw": "hourly_sum_mwh"})
    )

    if monthly.empty:
        hourly_monthly["bulletin_total_mwh"] = None
        hourly_monthly["diff_pct"] = None
        return hourly_monthly

    bul = monthly[["year", "month", "total_gen_mwh"]].copy()
    bul.columns = ["year", "month", "bulletin_total_mwh"]

    merged = hourly_monthly.merge(bul, on=["year", "month"], how="left")
    merged["diff_pct"] = (
        (merged["hourly_sum_mwh"] - merged["bulletin_total_mwh"])
        / merged["bulletin_total_mwh"] * 100
    ).round(1)
    return merged


# ── RAAEY vs actual 2024 ───────────────────────────────────────────────────────

def raaey_vs_actual(df_actual: pd.DataFrame, df_raaey: pd.DataFrame) -> dict:
    """Compare RAAEY tender 2024 projection with HEDNO actual 2024 hourly data."""
    if df_raaey.empty:
        return {}

    act24 = df_actual[df_actual["year"] == 2024].copy()
    if act24.empty:
        return {"note": "No HEDNO actual 2024 data available for comparison"}

    # Align on UTC timestamps
    act24["ts_utc"] = pd.to_datetime(
        act24["timestamp_utc"], errors="coerce"
    )
    raaey = df_raaey.copy()
    raaey["ts_utc"] = pd.to_datetime(raaey["timestamp_utc"], errors="coerce")
    raaey["load_mw"] = raaey["load_kw"] / 1000.0

    merged = pd.merge(
        act24[["ts_utc", "demand_mw"]],
        raaey[["ts_utc", "load_mw"]],
        on="ts_utc", how="inner"
    ).dropna(subset=["demand_mw", "load_mw"])

    n = len(merged)
    if n == 0:
        return {"note": "Timestamps do not align between RAAEY and HEDNO actual 2024"}

    corr = merged["demand_mw"].corr(merged["load_mw"])
    mae = (merged["demand_mw"] - merged["load_mw"]).abs().mean()

    result = {
        "n_matched_hours": n,
        "hedno_annual_mwh": round(merged["demand_mw"].sum(), 1),
        "raaey_annual_mwh": round(merged["load_mw"].sum(), 1),
        "hedno_peak_mw": round(merged["demand_mw"].max(), 3),
        "raaey_peak_mw": round(merged["load_mw"].max(), 3),
        "pearson_r": round(corr, 4),
        "mae_mw": round(mae, 4),
    }

    # Seasonal mean daily profiles
    seasons = {
        "off_season (Oct-Apr)": lambda df: df[df["ts_utc"].dt.month.isin(
            [10, 11, 12, 1, 2, 3, 4]
        )],
        "mid_season (May, Jun, Sep)": lambda df: df[df["ts_utc"].dt.month.isin([5, 6, 9])],
        "high_season (Jul-Aug)": lambda df: df[df["ts_utc"].dt.month.isin([7, 8])],
    }
    result["seasonal"] = {}
    for name, filt in seasons.items():
        sub = filt(merged)
        result["seasonal"][name] = {
            "n_hours": len(sub),
            "hedno_mean_mw": round(sub["demand_mw"].mean(), 4) if len(sub) else None,
            "raaey_mean_mw": round(sub["load_mw"].mean(), 4) if len(sub) else None,
        }

    return result


# ── Figures ────────────────────────────────────────────────────────────────────

def fig_heatmap(df: pd.DataFrame) -> None:
    for yr, g in df.groupby("year"):
        pivot = g.pivot_table(index="doy", columns="hour", values="demand_mw", aggfunc="mean")
        if pivot.shape[1] < 20:
            continue
        fig, ax = plt.subplots(figsize=(14, 5))
        c = ax.pcolormesh(
            pivot.columns, pivot.index, pivot.values,
            cmap="hot_r", shading="auto", vmin=0, vmax=3.0,
        )
        plt.colorbar(c, ax=ax, label="Demand (MW)")
        ax.set_xlabel("Hour of day")
        ax.set_ylabel("Day of year")
        ax.set_title(f"Astypalea load heatmap {yr}")
        plt.tight_layout()
        out = FIGURES_DIR / f"heatmap_{yr}.png"
        fig.savefig(out, dpi=150)
        plt.close(fig)
        log.info(f"  Saved {out}")


def fig_monthly_energy(monthly_cmp: pd.DataFrame) -> None:
    if monthly_cmp.empty or "bulletin_total_mwh" not in monthly_cmp.columns:
        return
    sub = monthly_cmp.dropna(subset=["hourly_sum_mwh", "bulletin_total_mwh"])
    if sub.empty:
        return

    sub = sub.copy()
    sub["date"] = pd.to_datetime(
        sub[["year", "month"]].assign(day=1)
    )
    fig, ax = plt.subplots(figsize=(14, 4))
    ax.plot(sub["date"], sub["hourly_sum_mwh"] / 1000, label="Hourly sum", marker="o", ms=4)
    ax.plot(sub["date"], sub["bulletin_total_mwh"] / 1000, label="Bulletin total", marker="s", ms=4)
    ax.set_ylabel("GWh")
    ax.set_title("Monthly energy: HEDNO hourly sum vs bulletin total")
    ax.legend()
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    fig.autofmt_xdate()
    plt.tight_layout()
    out = FIGURES_DIR / "monthly_energy.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    log.info(f"  Saved {out}")


def fig_seasonal_profiles(df: pd.DataFrame) -> None:
    seasons = {
        "off (Oct–Apr)": df[df["month"].isin([10, 11, 12, 1, 2, 3, 4])],
        "mid (May, Jun, Sep)": df[df["month"].isin([5, 6, 9])],
        "high (Jul–Aug)": df[df["month"].isin([7, 8])],
    }
    hours = list(range(24))
    fig, ax = plt.subplots(figsize=(10, 5))
    for label, sub in seasons.items():
        if sub.empty:
            continue
        profile = sub.groupby("hour")["demand_mw"].mean().reindex(hours)
        ax.plot(hours, profile, label=label, linewidth=2)
    ax.set_xlabel("Hour of day")
    ax.set_ylabel("Mean demand (MW)")
    ax.set_title("Astypalea seasonal mean daily profiles")
    ax.legend()
    ax.set_xticks(hours)
    plt.tight_layout()
    out = FIGURES_DIR / "seasonal_profiles.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    log.info(f"  Saved {out}")


def fig_tender_vs_actual_2024(
    df_actual: pd.DataFrame, df_raaey: pd.DataFrame
) -> None:
    if df_raaey.empty:
        return

    act24 = df_actual[df_actual["year"] == 2024].copy()
    if act24.empty:
        return

    act24["ts_utc"] = pd.to_datetime(act24["timestamp_utc"], errors="coerce")
    df_raaey["ts_utc"] = pd.to_datetime(df_raaey["timestamp_utc"], errors="coerce")
    df_raaey["load_mw"] = df_raaey["load_kw"] / 1000.0

    merged = pd.merge(
        act24[["ts_utc", "demand_mw", "hour"]],
        df_raaey[["ts_utc", "load_mw"]],
        on="ts_utc", how="inner"
    ).dropna()

    if merged.empty:
        return

    merged["month"] = merged["ts_utc"].dt.month
    seasons = {
        "off (Oct–Apr)": merged[merged["month"].isin([10, 11, 12, 1, 2, 3, 4])],
        "mid (May, Jun, Sep)": merged[merged["month"].isin([5, 6, 9])],
        "high (Jul–Aug)": merged[merged["month"].isin([7, 8])],
    }
    hours = list(range(24))
    fig, axes = plt.subplots(1, 3, figsize=(15, 5), sharey=True)
    for ax, (label, sub) in zip(axes, seasons.items()):
        if sub.empty:
            continue
        hedno_p = sub.groupby("hour")["demand_mw"].mean().reindex(hours)
        raaey_p = sub.groupby("hour")["load_mw"].mean().reindex(hours)
        ax.plot(hours, hedno_p, label="HEDNO actual", linewidth=2)
        ax.plot(hours, raaey_p, label="RAAEY tender", linewidth=2, linestyle="--")
        ax.set_title(label)
        ax.set_xlabel("Hour")
        ax.legend(fontsize=8)
    axes[0].set_ylabel("Mean demand (MW)")
    fig.suptitle("HEDNO actual 2024 vs RAAEY tender projection — seasonal daily profiles")
    plt.tight_layout()
    out = FIGURES_DIR / "tender_vs_actual_2024.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    log.info(f"  Saved {out}")


# ── Report writer ──────────────────────────────────────────────────────────────

def write_report(
    cov: list[dict],
    issues: list[str],
    monthly_cmp: pd.DataFrame,
    raaey_result: dict,
    dst_notes: list[str],
) -> None:
    out = DATA_PROCESSED / "QA_report.md"
    lines: list[str] = [
        "# Astypalea iPOY — Data Quality Report",
        "",
        f"Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "---",
        "",
        "## 1. Coverage per year",
        "",
        "| Year | Hours present | Expected | Coverage % | Missing dates | "
        "Annual MWh | Peak MW | Peak timestamp |",
        "|------|-------------|----------|------------|---------------|"
        "-----------|---------|----------------|",
    ]
    for r in cov:
        lines.append(
            f"| {r['year']} | {r['hours_present']} | {r['hours_expected']} | "
            f"{r['coverage_pct']} | {r['missing_date_count']} | "
            f"{r['annual_energy_mwh']} | {r['peak_mw']} | {r['peak_timestamp']} |"
        )
    lines += [
        "",
        "### Missing dates (first 10 per year)",
    ]
    for r in cov:
        if r["missing_dates_sample"]:
            lines.append(f"- **{r['year']}**: {r['missing_dates_sample']}")

    lines += [
        "",
        "---",
        "",
        "## 2. Sanity checks",
        "",
    ]
    if issues:
        for issue in issues:
            lines.append(f"- ⚠ {issue}")
    else:
        lines.append("All sanity checks passed.")

    lines += [
        "",
        "---",
        "",
        "## 3. Monthly hourly sum vs bulletin total",
        "",
    ]
    if not monthly_cmp.empty and "bulletin_total_mwh" in monthly_cmp.columns:
        lines += [
            "| Year | Month | Hourly sum (MWh) | Bulletin total (MWh) | Diff % |",
            "|------|-------|-----------------|---------------------|--------|",
        ]
        for _, r in monthly_cmp.iterrows():
            lines.append(
                f"| {r['year']:.0f} | {r['month']:.0f} | {r['hourly_sum_mwh']:.1f} | "
                f"{r.get('bulletin_total_mwh', 'N/A')} | {r.get('diff_pct', 'N/A')} |"
            )
        diff = monthly_cmp["diff_pct"].dropna()
        if not diff.empty:
            lines += [
                "",
                f"Mean diff: {diff.mean():.1f}%,  "
                f"median: {diff.median():.1f}%,  "
                f"max absolute: {diff.abs().max():.1f}%",
                "",
                "**Interpretation note**: If hourly 'demand_mw' is consistently "
                "lower than bulletin 'total_gen_mwh' by a small fraction (e.g. ~3-5%), "
                "this may indicate that hourly demand is net of existing PV generation "
                "(≈0.32 MW installed before 2022), while the bulletin reports station "
                "output only. A consistent positive gap would suggest the opposite or a "
                "scale error. See DATA_NOTES.md §Open questions.",
            ]
    else:
        lines.append("Bulletin data not available for comparison.")

    lines += [
        "",
        "---",
        "",
        "## 4. RAAEY tender 2024 vs HEDNO actual 2024",
        "",
    ]
    if not raaey_result or "note" in raaey_result:
        lines.append(raaey_result.get("note", "RAAEY data not available."))
    else:
        lines += [
            f"- Matched hours: {raaey_result['n_matched_hours']}",
            f"- HEDNO annual: {raaey_result['hedno_annual_mwh']} MWh",
            f"- RAAEY annual: {raaey_result['raaey_annual_mwh']} MWh",
            f"- HEDNO peak: {raaey_result['hedno_peak_mw']} MW",
            f"- RAAEY peak: {raaey_result['raaey_peak_mw']} MW",
            f"- Pearson r: {raaey_result['pearson_r']}",
            f"- MAE: {raaey_result['mae_mw']} MW",
            "",
            "Seasonal means:",
        ]
        for sname, sv in raaey_result.get("seasonal", {}).items():
            lines.append(
                f"  - {sname}: HEDNO {sv['hedno_mean_mw']} MW, "
                f"RAAEY {sv['raaey_mean_mw']} MW  (n={sv['n_hours']} h)"
            )
        lines += [
            "",
            "**Conclusion (evidence-based)**: "
            "If Pearson r > 0.90 and annual totals match within ±5%, "
            "the RAAEY file likely represents measured or closely-modelled 2024 data "
            "rather than a 2022 projection. "
            "If r < 0.80 or annual totals differ by > 20%, it is more likely a forecast. "
            "See figures/tender_vs_actual_2024.png for seasonal profile comparison.",
        ]

    lines += [
        "",
        "---",
        "",
        "## 5. DST handling notes",
        "",
    ]
    if dst_notes:
        for note in dst_notes:
            lines.append(f"- {note}")
    else:
        lines.append(
            "DST transition days not yet verified (run after full dataset is parsed). "
            "Check for rows with '?DST_AMBIGUOUS' or '+LOCAL_NONEXISTENT' in timestamp_local."
        )

    lines += [
        "",
        "---",
        "",
        "## 6. Figures",
        "",
        "Generated in `data/processed/figures/`:",
        "",
        "- `heatmap_{year}.png` — load heatmap (day of year × hour)",
        "- `monthly_energy.png` — hourly sum vs bulletin total per month",
        "- `seasonal_profiles.png` — mean daily load profile by season",
        "- `tender_vs_actual_2024.png` — RAAEY tender vs HEDNO actual 2024",
        "",
    ]

    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    log.info(f"QA report → {out}")


# ── DST check ──────────────────────────────────────────────────────────────────

def dst_check(df: pd.DataFrame) -> list[str]:
    """Check spring-forward (23h) and fall-back (25h) days."""
    import pytz
    athens = pytz.timezone("Europe/Athens")
    notes: list[str] = []

    for yr, g in df.groupby("year"):
        # Spring forward: last Sunday of March
        # Fall back: last Sunday of October
        for mo, label in ((3, "spring"), (10, "fall")):
            # Find last Sunday of month
            last_day = date(yr, mo + 1 if mo < 12 else 1, 1) - timedelta(days=1)
            while last_day.weekday() != 6:
                last_day -= timedelta(days=1)

            day_rows = g[g["ts"].dt.date == last_day]
            n_hours = len(day_rows)
            expected = 23 if label == "spring" else 25

            dst_note = (
                f"{yr} {label}-forward {last_day}: {n_hours} rows "
                f"(expected {expected})"
            )
            if n_hours not in (23, 24, 25):
                dst_note += " ⚠ UNEXPECTED"
            notes.append(dst_note)

            # Check for timestamp annotations
            ambig = g[g["timestamp_local"].str.contains("AMBIGUOUS|NONEXISTENT", na=False)]
            if not ambig.empty:
                notes.append(
                    f"  {yr}: {len(ambig)} rows with DST annotation in timestamp_local"
                )

    return notes


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    setup_dirs()
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    log.info("Loading data...")
    try:
        df = load_actual()
    except FileNotFoundError as exc:
        log.error(str(exc))
        return

    monthly = load_monthly()
    raaey = load_raaey()

    log.info(f"Actual data: {len(df):,} rows across years {sorted(df['year'].unique())}")

    log.info("Coverage analysis...")
    cov = coverage_table(df)
    for r in cov:
        log.info(
            f"  {r['year']}: {r['coverage_pct']}% coverage, "
            f"{r['annual_energy_mwh']} MWh/yr, peak {r['peak_mw']} MW"
        )

    log.info("Sanity checks...")
    issues = sanity_checks(df)
    for issue in issues:
        log.warning(f"  {issue}")

    log.info("Monthly comparison...")
    monthly_cmp = monthly_comparison(df, monthly)

    log.info("RAAEY comparison...")
    raaey_result = raaey_vs_actual(df, raaey)
    if raaey_result and "pearson_r" in raaey_result:
        log.info(f"  Pearson r = {raaey_result['pearson_r']}, "
                 f"MAE = {raaey_result['mae_mw']} MW")

    log.info("DST check...")
    dst_notes = dst_check(df)
    for note in dst_notes:
        log.info(f"  {note}")

    log.info("Generating figures...")
    fig_heatmap(df)
    fig_monthly_energy(monthly_cmp)
    fig_seasonal_profiles(df)
    if not raaey.empty:
        fig_tender_vs_actual_2024(df, raaey)

    log.info("Writing QA report...")
    write_report(cov, issues, monthly_cmp, raaey_result, dst_notes)
    log.info("QA complete.")


if __name__ == "__main__":
    main()

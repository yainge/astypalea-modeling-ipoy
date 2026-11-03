"""
tests/test_network.py — Unit tests for the Stage 0 model.

Covers:
 1. Network builds without error for both load bases and letter_avail modes.
 2. Energy balance holds every hour after optimisation.
 3. A one-day problem solves and returns integer unit counts.

Run from ipoy/:
    source .venv/bin/activate
    python -m pytest model/tests/ -v
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))
from network import (
    GENERATORS,
    RESERVE_VARIANTS,
    VOLL_EUR_MWH,
    build_availability,
    build_network,
    load_pvgis_profile,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def config():
    cfg_path = Path(__file__).parent.parent / "config.yaml"
    with open(cfg_path) as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def one_day_df():
    """A synthetic 24-hour DataFrame covering one calendar day."""
    ts = pd.date_range("2026-07-14 00:00", periods=24, freq="h")  # naive UTC
    np.random.seed(42)
    # Realistic daily load profile: low at night, high midday
    demand = 0.8 + 0.8 * np.sin(np.pi * (np.arange(24) - 6) / 14).clip(0)
    df = pd.DataFrame({
        "timestamp_utc": ts.strftime("%Y-%m-%dT%H:%M:%S+00:00"),  # string with +00:00
        "demand_mw": demand,
        "units_on_count": 2,
    })
    for g in GENERATORS:
        df[f"{g}_status"] = "available"
        df[f"{g}_on"] = 0
        df[f"{g}_raw"] = np.nan
    return df


@pytest.fixture(scope="module")
def one_day_with_maintenance(one_day_df):
    """One day where G6 is under maintenance for hours 6–18."""
    df = one_day_df.copy()
    mask = pd.to_datetime(df["timestamp_utc"], utc=True).dt.hour.between(6, 18)
    df.loc[mask, "G6_status"] = "maintenance"
    return df


@pytest.fixture(scope="module")
def pvgis_profile_fixture(config):
    """Download or load cached PVGIS profile; skip if network unavailable."""
    try:
        return load_pvgis_profile(config)
    except Exception:
        pytest.skip("PVGIS download unavailable; skipping gross-mode tests.")


# ---------------------------------------------------------------------------
# Test 1: Network builds
# ---------------------------------------------------------------------------

class TestNetworkBuilds:
    def test_net_unavailable(self, one_day_df, config):
        n = build_network(one_day_df, config, load_basis="net", letter_avail="unavailable")
        assert "Astypalea" in n.buses.index
        assert set(GENERATORS).issubset(n.generators.index)
        assert "VoLL" in n.generators.index
        assert "Load" in n.loads.index
        assert len(n.snapshots) == 24

    def test_net_ignored(self, one_day_df, config):
        n = build_network(one_day_df, config, load_basis="net", letter_avail="ignored")
        assert len(n.snapshots) == 24

    def test_gross_requires_pvgis_profile(self, one_day_df, config):
        with pytest.raises(ValueError, match="pvgis_profile required"):
            build_network(one_day_df, config, load_basis="gross", letter_avail="unavailable",
                          pvgis_profile=None)

    def test_gross_with_profile(self, one_day_df, config, pvgis_profile_fixture):
        n = build_network(one_day_df, config, load_basis="gross",
                          letter_avail="unavailable", pvgis_profile=pvgis_profile_fixture)
        assert "PV" in n.generators.index
        pv_pmax = n.generators_t.p_max_pu.get("PV")
        assert pv_pmax is not None
        assert (pv_pmax >= 0).all() and (pv_pmax <= 1).all()

    def test_empty_raises(self, config):
        df_empty = pd.DataFrame(columns=["timestamp_utc", "demand_mw", "units_on_count",
                                          "G5_status", "G6_status", "G7_status", "G8_status",
                                          "G5_on", "G6_on", "G7_on", "G8_on",
                                          "G5_raw", "G6_raw", "G7_raw", "G8_raw"])
        with pytest.raises(ValueError, match="No valid demand rows"):
            build_network(df_empty, config, load_basis="net", letter_avail="unavailable")


# ---------------------------------------------------------------------------
# Test 2: Availability logic
# ---------------------------------------------------------------------------

class TestAvailability:
    def test_ignored_all_ones(self, one_day_with_maintenance, config):
        avail = build_availability(one_day_with_maintenance, "ignored")
        assert (avail == 1.0).all().all()

    def test_unavailable_zeros_maintenance(self, one_day_with_maintenance, config):
        avail = build_availability(one_day_with_maintenance, "unavailable")
        # avail index is naive UTC; convert to match
        ts = pd.to_datetime(one_day_with_maintenance["timestamp_utc"], utc=True).dt.tz_convert(None)
        maint_mask = one_day_with_maintenance["G6_status"].isin(["maintenance", "fault"]).values
        assert (avail.loc[ts[maint_mask], "G6"] == 0.0).all()
        assert (avail.loc[ts[~maint_mask], "G6"] == 1.0).all()

    def test_other_generators_unaffected(self, one_day_with_maintenance, config):
        avail = build_availability(one_day_with_maintenance, "unavailable")
        for g in ["G5", "G7", "G8"]:
            assert (avail[g] == 1.0).all(), f"{g} should be unaffected by G6 maintenance"

    def test_p_max_pu_applied_in_network(self, one_day_with_maintenance, config):
        n = build_network(one_day_with_maintenance, config, load_basis="net",
                          letter_avail="unavailable")
        ts = pd.to_datetime(one_day_with_maintenance["timestamp_utc"], utc=True)
        maint_mask = one_day_with_maintenance["G6_status"].isin(["maintenance", "fault"]).values
        g6_avail = n.generators_t.p_max_pu.get("G6", pd.Series(1.0, index=ts))
        assert (g6_avail.values[maint_mask] == 0.0).all()


# ---------------------------------------------------------------------------
# Test 3: One-day solve + energy balance
# ---------------------------------------------------------------------------

class TestOneDaySolve:
    @pytest.fixture(scope="class")
    def solved_net(self, one_day_df, config):
        n = build_network(one_day_df, config, load_basis="net", letter_avail="unavailable")
        n.optimize(
            solver_name="highs",
            extra_functionality=RESERVE_VARIANTS["A"],
            solver_options={"mip_rel_gap": 0.01},
        )
        return n

    def test_solves(self, solved_net):
        assert solved_net.generators_t.p is not None
        assert len(solved_net.generators_t.p) == 24

    def test_integer_unit_counts(self, solved_net):
        status = solved_net.generators_t.status
        for col in status.columns:
            vals = status[col].values
            assert np.all(np.isin(vals, [0, 1])), f"{col} status not binary"

    def test_energy_balance(self, solved_net):
        """Total generation must equal load at every snapshot (within tolerance)."""
        load = solved_net.loads_t.p_set.iloc[:, 0]
        gen_total = solved_net.generators_t.p.sum(axis=1)
        imbalance = (gen_total - load).abs()
        assert imbalance.max() < 1e-3, f"Max energy imbalance: {imbalance.max():.6f} MW"

    def test_p_min_respected(self, solved_net, config):
        """Committed units must produce at least p_min_pu × p_nom."""
        p_min_pu = config["generators"]["p_min_pu"]["value"]
        p_nom = config["generators"]["p_nom"]["value"]
        lower_bound = p_min_pu * p_nom
        for g in GENERATORS:
            p = solved_net.generators_t.p[g]
            status = solved_net.generators_t.status[g]
            violation = (status == 1) & (p < lower_bound - 1e-4)
            assert not violation.any(), f"{g}: p_min_pu violated in {violation.sum()} hours"

    def test_reserve_B_holds(self, one_day_df, config):
        """Variant B: online capacity >= load + 1.1 at every snapshot."""
        n = build_network(one_day_df, config, load_basis="net", letter_avail="unavailable")
        n.optimize(
            solver_name="highs",
            extra_functionality=RESERVE_VARIANTS["B"],
            solver_options={"mip_rel_gap": 0.01},
        )
        p_nom = config["generators"]["p_nom"]["value"]
        status = n.generators_t.status.reindex(columns=GENERATORS, fill_value=0)
        committed_cap = status.sum(axis=1) * p_nom
        load = n.loads_t.p_set.iloc[:, 0]
        shortfall = (committed_cap - load - p_nom)
        # Allow slight tolerance; VoLL may cover truly infeasible hours
        voll_active = n.generators_t.p.get("VoLL", pd.Series(0.0, index=n.snapshots))
        non_voll = voll_active < 0.001
        if non_voll.any():
            assert shortfall[non_voll].min() >= -1e-3, \
                f"N-1 reserve violated: min shortfall = {shortfall[non_voll].min():.4f} MW"

    def test_voll_not_used_variant_A(self, solved_net):
        """Variant A with moderate load should not need VoLL."""
        voll = solved_net.generators_t.p.get("VoLL", pd.Series(0.0, index=solved_net.snapshots))
        assert voll.max() < 0.001, f"VoLL unexpectedly active: {voll.max():.3f} MW"

"""
network.py — PyPSA single-bus unit commitment network for the Astypalea diesel station.

Targets PyPSA >= 1.0 (linopy backend, timezone-naive snapshots).

Public API
----------
load_pvgis_profile(config)
    Download and cache a PVGIS hourly PV profile; return a (month, hour) → p_max_pu table.

build_network(df, config, load_basis, letter_avail, pvgis_profile=None)
    Build a pypsa.Network for one calendar month ready to optimise.

RESERVE_VARIANTS : dict
    Maps variant name → extra_functionality callable for n.optimize().

Parameters used by build_network
---------------------------------
df : DataFrame
    Rows from astypalea_hourly_actual.csv for one calendar month.
    Required columns: timestamp_utc, demand_mw, G5_status … G8_status.
config : dict
    Loaded from config.yaml.
load_basis : {'gross', 'net'}
    'gross' – demand_mw is total island demand; PV modelled as a zero-cost generator.
    'net'   – demand_mw is diesel-station output (PV subtracted upstream by HEDNO);
              PV excluded from the network.
    See DATA_NOTES Q1; neither interpretation is confirmed.
letter_avail : {'unavailable', 'ignored'}
    'unavailable' – cells with status='maintenance' or 'fault' set p_max_pu=0 for that unit-hour.
    'ignored'     – those cells are disregarded; unit always available.
    See DATA_NOTES Q2 and config.yaml letter_avail.
pvgis_profile : DataFrame or None
    Required only when load_basis='gross'.
"""

import hashlib
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import pypsa
import requests

log = logging.getLogger(__name__)

GENERATORS = ["G5", "G6", "G7", "G8"]

_MODEL_DIR = Path(__file__).parent
PVGIS_CACHE_DIR = _MODEL_DIR / "data"

# High Value of Lost Load; VoLL dispatch in results signals infeasible reserve.
VOLL_EUR_MWH = 50_000.0


# ---------------------------------------------------------------------------
# Timestamp helpers
# ---------------------------------------------------------------------------

def _to_naive_utc(series_or_idx) -> pd.DatetimeIndex:
    """
    Convert a Series of UTC timestamp strings to a naive UTC DatetimeIndex.
    PyPSA 1.x requires timezone-naive snapshots.
    """
    parsed = pd.to_datetime(series_or_idx, utc=True)
    if hasattr(parsed, "dt"):
        return pd.DatetimeIndex(parsed.dt.tz_convert(None))
    return parsed.tz_convert(None)


# ---------------------------------------------------------------------------
# PVGIS helpers
# ---------------------------------------------------------------------------

def _pvgis_cache_path(lat: float, lon: float, year: int, loss: float) -> Path:
    key = hashlib.md5(f"{lat}_{lon}_{year}_{loss}".encode()).hexdigest()[:10]
    return PVGIS_CACHE_DIR / f"pvgis_{key}.json"


def _download_pvgis(lat: float, lon: float, year: int, loss: float) -> dict:
    url = (
        "https://re.jrc.ec.europa.eu/api/v5_2/seriescalc"
        f"?lat={lat}&lon={lon}"
        "&pvcalculation=1&peakpower=1"
        f"&loss={loss}"
        "&outputformat=json"
        f"&startyear={year}&endyear={year}"
        "&mountingplace=free&aspect=0&angle=30"
    )
    log.info("Downloading PVGIS data: %s", url)
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    return resp.json()


def load_pvgis_profile(config: dict) -> pd.DataFrame:
    """
    Return a DataFrame with columns [month, hour, p_max_pu].

    p_max_pu is the fraction of rated capacity (1 kWp) for that (month, hour).
    Source: PVGIS v5.2 seriescalc, peakpower=1 kWp, P in W → p_max_pu = P/1000.

    A single representative year (config.pv.pvgis_year, default 2022) is used.
    The profile is averaged across all days of each (month, hour) pair.
    Inter-annual variability is not captured.
    """
    pv_cfg = config["pv"]
    lat = pv_cfg["pvgis_lat"]
    lon = pv_cfg["pvgis_lon"]
    loss = pv_cfg["pvgis_loss"]["value"]
    year = int(pv_cfg.get("pvgis_year", 2022))

    cache_path = _pvgis_cache_path(lat, lon, year, loss)
    PVGIS_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if cache_path.exists():
        log.info("Using cached PVGIS data: %s", cache_path)
        with open(cache_path) as f:
            data = json.load(f)
    else:
        data = _download_pvgis(lat, lon, year, loss)
        with open(cache_path, "w") as f:
            json.dump(data, f)
        log.info("Saved PVGIS cache: %s", cache_path)

    records = []
    for row in data["outputs"]["hourly"]:
        # PVGIS time string: "YYYYMMDDhhmm" (e.g. "20220101:0110")
        t_str = str(row["time"])
        dt = pd.to_datetime(t_str, format="%Y%m%d:%H%M")  # naive UTC
        records.append({"dt": dt, "p_w": float(row["P"])})

    df = pd.DataFrame(records)
    df["month"] = df["dt"].dt.month
    df["hour"] = df["dt"].dt.hour
    df["p_max_pu"] = df["p_w"] / 1000.0

    return df.groupby(["month", "hour"])["p_max_pu"].mean().reset_index()


def _pv_p_max_pu_array(timestamps: pd.DatetimeIndex, profile: pd.DataFrame) -> np.ndarray:
    """Return p_max_pu array aligned to timestamps using (month, hour) lookup."""
    lookup = profile.set_index(["month", "hour"])["p_max_pu"]
    return np.array([lookup.get((t.month, t.hour), 0.0) for t in timestamps])


# ---------------------------------------------------------------------------
# Availability
# ---------------------------------------------------------------------------

def build_availability(df: pd.DataFrame, letter_avail: str) -> pd.DataFrame:
    """
    Return a DataFrame (index=naive-UTC timestamps, columns=G5..G8) of p_max_pu values.
    1.0 = unit available for commitment; 0.0 = unavailable.

    maintenance / fault → 0.0 when letter_avail='unavailable'
    maintenance / fault → 1.0 when letter_avail='ignored'
    All other statuses  → 1.0 always
    """
    ts = _to_naive_utc(df["timestamp_utc"])
    n = len(df)
    data = {g: np.ones(n) for g in GENERATORS}

    if letter_avail == "unavailable":
        for g in GENERATORS:
            mask = df[f"{g}_status"].isin(["maintenance", "fault"]).values
            data[g][mask] = 0.0

    return pd.DataFrame(data, index=ts)


# ---------------------------------------------------------------------------
# Network builder
# ---------------------------------------------------------------------------

def build_network(
    df: pd.DataFrame,
    config: dict,
    load_basis: str,
    letter_avail: str,
    pvgis_profile: pd.DataFrame | None = None,
) -> pypsa.Network:
    """
    Build a single-bus PyPSA network for one calendar month.

    Notes
    -----
    * Snapshots are timezone-naive UTC (PyPSA 1.x requirement).
    * Month-boundary continuity: the initial generator status is unconstrained at
      the first snapshot of each month.  Min-up / min-down constraints do not span
      month boundaries.  Commitment transitions near month edges may be
      over-counted compared with a rolling optimisation.
    * All four diesel generators are modelled identically.  The solver may commit
      any subset; unit identity is not meaningful in the output.
    * A VoLL (value-of-lost-load) generator is included to keep every problem
      feasible.  Any VoLL dispatch signals that the reserve constraint cannot be
      met by the four diesel units.
    """
    df = df.copy().reset_index(drop=True)
    df = df.dropna(subset=["demand_mw"])
    if df.empty:
        raise ValueError("No valid demand rows after dropping NaN.")

    ts = _to_naive_utc(df["timestamp_utc"])  # naive UTC DatetimeIndex
    gen_cfg = config["generators"]
    pv_cfg = config["pv"]

    n = pypsa.Network()
    n.set_snapshots(ts)
    n.add("Bus", "Astypalea", v_nom=20.0, carrier="AC")

    # Load
    n.add(
        "Load", "Load",
        bus="Astypalea",
        p_set=pd.Series(df["demand_mw"].values, index=ts),
    )

    # Diesel generators
    p_nom = float(gen_cfg["p_nom"]["value"])
    p_min_pu = float(gen_cfg["p_min_pu"]["value"])
    min_up = int(gen_cfg["min_up_time"]["value"])
    min_dn = int(gen_cfg["min_down_time"]["value"])
    su_cost = float(gen_cfg["start_up_cost"]["value"])
    mc = float(gen_cfg["marginal_cost"]["value"])

    for g in GENERATORS:
        n.add(
            "Generator", g,
            bus="Astypalea",
            carrier="diesel",
            p_nom=p_nom,
            committable=True,
            p_min_pu=p_min_pu,
            p_max_pu=1.0,
            min_up_time=min_up,
            min_down_time=min_dn,
            start_up_cost=su_cost,
            marginal_cost=mc,
        )

    # VoLL slack (ensures feasibility; detect use in results)
    n.add(
        "Generator", "VoLL",
        bus="Astypalea",
        carrier="voll",
        p_nom=20.0,
        committable=False,
        marginal_cost=VOLL_EUR_MWH,
    )

    # Availability: set time-varying p_max_pu for diesel generators
    avail = build_availability(df, letter_avail)
    p_max_pu_df = pd.DataFrame(
        {g: avail[g].values for g in GENERATORS},
        index=ts,
    )

    # PV (gross mode only)
    if load_basis == "gross":
        if pvgis_profile is None:
            raise ValueError("pvgis_profile required when load_basis='gross'.")
        pv_p_max = _pv_p_max_pu_array(ts, pvgis_profile)
        n.add(
            "Generator", "PV",
            bus="Astypalea",
            carrier="solar",
            p_nom=float(pv_cfg["p_nom"]["value"]),
            committable=False,
            marginal_cost=0.0,
        )
        p_max_pu_df["PV"] = pv_p_max

    n.generators_t.p_max_pu = p_max_pu_df

    return n


# ---------------------------------------------------------------------------
# Reserve constraint extra_functionality callables
# ---------------------------------------------------------------------------

def _committed_capacity_expr(n: pypsa.Network):
    """
    Linopy LinearExpression for total committed diesel capacity per snapshot.

    In PyPSA 1.x, the Generator-status variable has dims ('snapshot', 'name')
    where 'name' contains only the committable generators.
    All diesel units have identical p_nom, so committed_cap = n_committed × p_nom.
    """
    m = n.model
    if "Generator-status" not in m.variables:
        raise RuntimeError("No committable generators in model.")
    status = m.variables["Generator-status"]
    # gen_dim is 'name' in PyPSA 1.x
    gen_dim = next(d for d in status.dims if d != "snapshot")
    diesel_p_nom = n.generators.query("committable").p_nom.iloc[0]
    return status.sum(gen_dim) * diesel_p_nom


def make_reserve_A():
    """No reserve constraint."""
    def _fn(n, snapshots):
        pass
    return _fn


def _add_reserve_slack(n: pypsa.Network, snapshots, name: str) -> "linopy.Variable":
    """
    Add a per-snapshot reserve-slack variable to the model and add its cost
    to the objective.  Reserve slack represents the reserve shortfall (MW)
    that cannot be covered by committed diesel capacity.  It is priced at VoLL
    so that infeasible reserve hours are expensive but the problem remains
    feasible even when committed capacity < load + reserve requirement.

    This slack is intentionally separate from the energy-balance VoLL generator:
    energy VoLL = unserved load (generation < load);
    reserve slack = insufficient spinning reserve margin.
    """
    import linopy  # local import avoids hard top-level coupling
    m = n.model
    slack = m.add_variables(lower=0.0, coords=[snapshots], name=name)
    m.objective = m.objective + VOLL_EUR_MWH * slack.sum()
    return slack


def make_reserve_B():
    """
    N-1: committed diesel capacity >= load + largest unit (1.1 MW).
    A reserve-slack variable (priced at VoLL) absorbs any shortfall so the
    problem stays feasible when p_min constraints prevent committing enough
    units.  Non-zero slack hours are flagged in results as 'reserve infeasible'.
    """
    def _fn(n, snapshots):
        committed = _committed_capacity_expr(n)
        slack = _add_reserve_slack(n, snapshots, "reserve_slack_B")
        load = n.loads_t.p_set.iloc[:, 0].reindex(snapshots).values
        largest = n.generators.query("committable").p_nom.max()
        n.model.add_constraints(
            committed + slack >= load + largest,
            name="reserve_B",
        )
    return _fn


def make_reserve_C(r: float):
    """
    Fractional: committed diesel capacity >= load × (1 + r).
    Reserve-slack variable absorbs shortfall; see make_reserve_B.
    """
    label = f"reserve_C_{r:.2f}"
    slack_name = f"reserve_slack_C_{r:.2f}"
    def _fn(n, snapshots):
        committed = _committed_capacity_expr(n)
        slack = _add_reserve_slack(n, snapshots, slack_name)
        load = n.loads_t.p_set.iloc[:, 0].reindex(snapshots).values
        n.model.add_constraints(
            committed + slack >= (1.0 + r) * load,
            name=label,
        )
    return _fn


RESERVE_VARIANTS = {
    "A":     make_reserve_A(),
    "B":     make_reserve_B(),
    "C_020": make_reserve_C(0.2),
    "C_050": make_reserve_C(0.5),
    "C_100": make_reserve_C(1.0),
}

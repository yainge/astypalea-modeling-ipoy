"""Validate and clean energy assets CSV → GeoJSON.

Reads:  data/energy/energy_assets.csv
        data/energy/substations.csv
        data/osm/boundary_astypalea.geojson  (optional — for validation)
Writes: data/energy/energy_assets_clean.geojson
        data/energy/substations_clean.geojson
"""

import warnings
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

SCRIPTS_DIR = Path(__file__).parent
DATA_DIR = SCRIPTS_DIR.parent / "data"
ENERGY_DIR = DATA_DIR / "energy"
OSM_DIR = DATA_DIR / "osm"


def load_boundary():
    path = OSM_DIR / "boundary_astypalea.geojson"
    if path.exists():
        return gpd.read_file(path).union_all()
    return None


def validate_coords(df: pd.DataFrame, boundary) -> pd.DataFrame:
    if boundary is None:
        return df
    inside = []
    for _, row in df.iterrows():
        pt = Point(row["lon"], row["lat"])
        if not boundary.buffer(0.12).contains(pt):
            warnings.warn(f"  WARN: '{row['name']}' ({row['lat']}, {row['lon']}) may be outside island boundary")
        inside.append(pt)
    return df


def csv_to_geojson(csv_path: Path, out_path: Path, boundary=None):
    df = pd.read_csv(csv_path)
    df = validate_coords(df, boundary)
    for col in ["capacity_mw", "capacity_mwh", "capacity_mva"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    gdf = gpd.GeoDataFrame(
        df,
        geometry=[Point(row.lon, row.lat) for _, row in df.iterrows()],
        crs="EPSG:4326",
    )
    gdf.to_file(out_path, driver="GeoJSON")
    print(f"  -> {out_path} ({len(gdf)} features)")
    return gdf


if __name__ == "__main__":
    print("Building energy data...")
    boundary = load_boundary()
    if boundary is None:
        print("  NOTE: boundary file not found, skipping coordinate validation")

    csv_to_geojson(ENERGY_DIR / "energy_assets.csv",
                   ENERGY_DIR / "energy_assets_clean.geojson", boundary)
    csv_to_geojson(ENERGY_DIR / "substations.csv",
                   ENERGY_DIR / "substations_clean.geojson", boundary)
    print("Done.")

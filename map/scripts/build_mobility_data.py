"""Join congestion model to road edges for summer and winter scenarios.

Reads:  data/osm/roads_astypalea.geojson
        data/mobility/road_congestion_model.csv
        data/mobility/ev_charging_stations.csv
Writes: data/mobility/roads_congestion_summer.geojson
        data/mobility/roads_congestion_winter.geojson
        data/mobility/ev_stations_clean.geojson
"""

from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

SCRIPTS_DIR = Path(__file__).parent
DATA_DIR = SCRIPTS_DIR.parent / "data"
OSM_DIR = DATA_DIR / "osm"
MOB_DIR = DATA_DIR / "mobility"


def build_congestion_roads():
    roads_path = OSM_DIR / "roads_astypalea.geojson"
    if not roads_path.exists():
        print("  ERROR: roads_astypalea.geojson not found. Run fetch_osm.py first.")
        return

    roads = gpd.read_file(roads_path)
    model = pd.read_csv(MOB_DIR / "road_congestion_model.csv")
    defaults = model[model["road_name"].str.startswith("DEFAULT_")].copy()
    defaults["highway"] = defaults["road_name"].str.replace("DEFAULT_", "", regex=False)

    def get_congestion(row, scenario_col):
        hw = row.get("highway", "unclassified")
        # osmnx can return lists for highway tags (relation members)
        if isinstance(hw, (list, tuple)):
            hw = hw[0] if hw else "unclassified"
        try:
            import numpy as np
            if isinstance(hw, np.ndarray):
                hw = hw.flat[0] if hw.size > 0 else "unclassified"
        except Exception:
            pass
        try:
            if pd.isna(hw):
                hw = "unclassified"
        except (TypeError, ValueError):
            pass
        hw = str(hw)
        match = defaults[defaults["highway"] == hw]
        if not match.empty:
            return float(match.iloc[0][scenario_col])
        return 0.25  # fallback default

    for scenario, col in [("summer", "summer_congestion"), ("winter", "winter_congestion")]:
        r = roads.copy()
        r["congestion"] = r.apply(lambda row: get_congestion(row, col), axis=1)
        out = MOB_DIR / f"roads_congestion_{scenario}.geojson"
        r.to_file(out, driver="GeoJSON")
        print(f"  -> {out} ({len(r)} road segments)")


def build_ev_stations():
    df = pd.read_csv(MOB_DIR / "ev_charging_stations.csv")
    gdf = gpd.GeoDataFrame(
        df,
        geometry=[Point(row.lon, row.lat) for _, row in df.iterrows()],
        crs="EPSG:4326",
    )
    out = MOB_DIR / "ev_stations_clean.geojson"
    gdf.to_file(out, driver="GeoJSON")
    print(f"  -> {out} ({len(gdf)} stations)")


if __name__ == "__main__":
    print("Building mobility data...")
    build_congestion_roads()
    build_ev_stations()
    print("Done.")

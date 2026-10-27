"""Build demand zone grid from OSM building footprints.

Creates a regular grid of points covering the island, assigns estimated
demand based on building density + type, calibrated to the 7 GWh/year
island baseline (HEDNO 2014-2015).

Reads:  data/osm/boundary_astypalea.geojson
        data/osm/buildings_astypalea.geojson  (optional — falls back to grid)
Writes: data/energy/demand_zones_summer.geojson
        data/energy/demand_zones_winter.geojson
"""

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point, box

SCRIPTS_DIR = Path(__file__).parent
DATA_DIR = SCRIPTS_DIR.parent / "data"
OSM_DIR = DATA_DIR / "osm"
ENERGY_DIR = DATA_DIR / "energy"

GRID_SPACING_DEG = 0.004   # ~400m at this latitude
ANNUAL_GWH = 7.0
SUMMER_MULT = 2.8
WINTER_MULT = 0.65

BUILDING_DEMAND_KW = {
    "hotel": 80.0, "motel": 50.0, "apartments": 40.0, "commercial": 15.0,
    "retail": 12.0, "office": 10.0, "industrial": 25.0,
    "yes": 4.0,       # generic building tag
    "house": 3.0, "residential": 3.0, "detached": 3.5, "terrace": 2.5,
    "school": 20.0, "hospital": 60.0, "church": 5.0,
}
DEFAULT_DEMAND_KW = 3.0


def load_boundary():
    path = OSM_DIR / "boundary_astypalea.geojson"
    if not path.exists():
        print("  WARN: boundary file not found; using bounding box")
        from shapely.geometry import box
        return box(26.28, 36.48, 26.62, 36.62)
    return gpd.read_file(path).union_all()


def load_buildings(boundary):
    path = OSM_DIR / "buildings_astypalea.geojson"
    if not path.exists():
        print("  NOTE: buildings file not found; using uniform grid")
        return None
    gdf = gpd.read_file(path)
    gdf = gdf[gdf.geometry.is_valid].copy()
    return gdf


def make_grid(boundary):
    minx, miny, maxx, maxy = boundary.bounds
    xs = np.arange(minx, maxx, GRID_SPACING_DEG)
    ys = np.arange(miny, maxy, GRID_SPACING_DEG)
    points = []
    for x in xs:
        for y in ys:
            pt = Point(x, y)
            if boundary.contains(pt):
                points.append(pt)
    return points


def assign_demand(grid_points, buildings_gdf):
    demands = []
    if buildings_gdf is None:
        # Uniform fallback
        for _ in grid_points:
            demands.append(DEFAULT_DEMAND_KW)
        return demands

    # Build spatial index
    tree = buildings_gdf.sindex
    radius_deg = GRID_SPACING_DEG * 0.7

    for pt in grid_points:
        search_box = pt.buffer(radius_deg).bounds
        candidates = list(tree.intersection(search_box))
        if not candidates:
            demands.append(DEFAULT_DEMAND_KW * 0.5)
            continue
        nearby = buildings_gdf.iloc[candidates]
        total = 0.0
        for _, bld in nearby.iterrows():
            btype = str(bld.get("building", "yes")).lower()
            kw = BUILDING_DEMAND_KW.get(btype, DEFAULT_DEMAND_KW)
            total += kw
        demands.append(max(total, DEFAULT_DEMAND_KW * 0.2))
    return demands


def calibrate(demands, multiplier):
    """Scale so that annual total matches ANNUAL_GWH roughly."""
    raw_total = sum(demands)
    if raw_total == 0:
        return demands
    target_kw = (ANNUAL_GWH * 1e6) / 8760  # mean kW
    scale = target_kw / raw_total
    return [d * scale * multiplier for d in demands]


if __name__ == "__main__":
    print("Building demand zones...")
    boundary = load_boundary()
    buildings = load_buildings(boundary)
    grid = make_grid(boundary)
    print(f"  Grid points inside island: {len(grid)}")

    raw_demands = assign_demand(grid, buildings)

    for scenario, mult in [("summer", SUMMER_MULT), ("winter", WINTER_MULT)]:
        demands = calibrate(raw_demands, mult)
        gdf = gpd.GeoDataFrame(
            {"demand_kw": demands, "scenario": scenario},
            geometry=grid,
            crs="EPSG:4326",
        )
        out = ENERGY_DIR / f"demand_zones_{scenario}.geojson"
        gdf.to_file(out, driver="GeoJSON")
        print(f"  -> {out} ({len(gdf)} points, max demand: {max(demands):.1f} kW)")

    print("Done.")

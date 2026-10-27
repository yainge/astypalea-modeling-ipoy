"""Download OSM data for Astypalea island and write cleaned files to data/osm/.

Run once (or when you want to refresh OSM data):
    cd map/
    python scripts/fetch_osm.py

Outputs (all in data/osm/):
    boundary_astypalea.geojson   - Island boundary polygon
    roads_astypalea.geojson      - Road network edges
    buildings_astypalea.geojson  - Building footprints
    pois_astypalea.geojson       - Points of interest
    power_osm_astypalea.geojson  - Power infrastructure in OSM
"""

import json
import os
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
import osmnx as ox
from shapely.geometry import Point

PLACE = "Astypalea, South Aegean, Greece"
BBOX = (36.48, 26.28, 36.62, 26.62)  # (south, west, north, east)
OUT_DIR = Path(__file__).parent.parent / "data" / "osm"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def fetch_boundary():
    print("Fetching island boundary...")
    gdf = ox.geocode_to_gdf(PLACE)
    out = OUT_DIR / "boundary_astypalea.geojson"
    gdf.to_file(out, driver="GeoJSON")
    print(f"  -> {out}")
    return gdf


def fetch_roads():
    print("Fetching road network...")
    G = ox.graph_from_place(PLACE, network_type="all", retain_all=True)
    _, edges = ox.graph_to_gdfs(G)
    edges = edges.reset_index()
    keep_cols = [c for c in ["geometry", "name", "highway", "length", "osmid", "u", "v", "key"] if c in edges.columns]
    edges = edges[keep_cols]
    out = OUT_DIR / "roads_astypalea.geojson"
    edges.to_file(out, driver="GeoJSON")
    print(f"  -> {out} ({len(edges)} edges)")
    return edges


def fetch_buildings():
    print("Fetching building footprints...")
    tags = {"building": True}
    try:
        gdf = ox.features_from_place(PLACE, tags=tags)
        gdf = gdf[gdf.geometry.geom_type.isin(["Polygon", "MultiPolygon"])].copy()
        gdf = gdf.reset_index()
        keep_cols = [c for c in ["geometry", "building", "name", "addr:street"] if c in gdf.columns]
        gdf = gdf[keep_cols]
        out = OUT_DIR / "buildings_astypalea.geojson"
        gdf.to_file(out, driver="GeoJSON")
        print(f"  -> {out} ({len(gdf)} buildings)")
        return gdf
    except Exception as e:
        print(f"  WARNING: building fetch failed: {e}")
        return None


def fetch_pois():
    print("Fetching POIs via osmnx features...")
    all_features = []

    tag_groups = [
        {"amenity": ["ferry_terminal", "fuel", "charging_station", "bus_stop"]},
        {"tourism": ["hotel", "resort", "guest_house", "motel", "apartment", "camp_site"]},
        {"aeroway": "aerodrome"},
        {"natural": "beach"},
    ]

    for tags in tag_groups:
        try:
            gdf = ox.features_from_place(PLACE, tags=tags)
            # Keep only point geometries for POIs
            points = gdf[gdf.geometry.geom_type == "Point"].copy()
            if not points.empty:
                all_features.append(points)
        except Exception as e:
            print(f"  NOTE: tag group {tags} returned no results or error: {e}")

    if all_features:
        combined = pd.concat(all_features, ignore_index=True)
        combined = gpd.GeoDataFrame(combined, crs="EPSG:4326")
        out = OUT_DIR / "pois_astypalea.geojson"
        combined.to_file(out, driver="GeoJSON")
        print(f"  -> {out} ({len(combined)} POIs)")
        return combined
    else:
        # Write empty GeoJSON
        empty = {"type": "FeatureCollection", "features": []}
        out = OUT_DIR / "pois_astypalea.geojson"
        out.write_text(json.dumps(empty))
        print(f"  -> {out} (0 POIs - all queries returned empty)")
        return None


def fetch_power_osm():
    print("Fetching power infrastructure from OSM...")
    tags = {"power": ["plant", "substation", "generator", "line", "cable"]}
    try:
        gdf = ox.features_from_place(PLACE, tags=tags)
        gdf = gdf.reset_index()
        out = OUT_DIR / "power_osm_astypalea.geojson"
        gdf.to_file(out, driver="GeoJSON")
        print(f"  -> {out} ({len(gdf)} features)")
        return gdf
    except Exception as e:
        print(f"  WARNING: power features fetch failed (may be empty in OSM): {e}")
        empty = gpd.GeoDataFrame({"geometry": []}, crs="EPSG:4326")
        out = OUT_DIR / "power_osm_astypalea.geojson"
        empty.to_file(out, driver="GeoJSON")
        return empty


if __name__ == "__main__":
    print(f"Downloading OSM data for: {PLACE}")
    print(f"Output directory: {OUT_DIR}\n")

    fetch_boundary()
    fetch_roads()
    fetch_buildings()
    fetch_pois()
    fetch_power_osm()

    print("\nDone. Run build scripts next.")

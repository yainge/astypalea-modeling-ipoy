"""Main map generation script. Reads all clean data and writes docs/map_astypalea.html.

Usage (from map/ directory):
    python scripts/plot_map.py

Run build scripts first:
    python scripts/fetch_osm.py
    python scripts/build_energy_data.py
    python scripts/build_mobility_data.py
    python scripts/build_demand_zones.py
"""

import json
import sys
from pathlib import Path

import folium
import folium.plugins
import geopandas as gpd
import pandas as pd

SCRIPTS_DIR = Path(__file__).parent
BASE_DIR = SCRIPTS_DIR.parent
DATA_DIR = BASE_DIR / "data"
ENERGY_DIR = DATA_DIR / "energy"
MOB_DIR = DATA_DIR / "mobility"
OSM_DIR = DATA_DIR / "osm"
OUT_DIR = BASE_DIR / "docs"
OUT_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(SCRIPTS_DIR))
from utils import (
    ASSET_COLORS, SUBSTATION_COLORS,
    congestion_color, congestion_label,
    demand_color, energy_circle_radius, substation_capacity_class,
    energy_popup_html, substation_popup_html, ev_station_popup_html, demand_popup_html,
    build_legend_html, build_scenario_toggle_html,
)

ISLAND_CENTER = [36.549, 26.368]
ZOOM = 12


def add_boundary(m):
    path = OSM_DIR / "boundary_astypalea.geojson"
    if not path.exists():
        print("  NOTE: boundary not found, skipping")
        return
    folium.GeoJson(
        str(path),
        name="Island Boundary",
        style_function=lambda _: {"color": "#333333", "weight": 2.5, "fillOpacity": 0},
        tooltip="Astypalea",
    ).add_to(m)


def add_energy_assets(m):
    path = ENERGY_DIR / "energy_assets_clean.geojson"
    if not path.exists():
        path = ENERGY_DIR / "energy_assets.csv"
        if not path.exists():
            print("  NOTE: energy assets not found, skipping")
            return
        df = pd.read_csv(path)
    else:
        gdf = gpd.read_file(path)
        df = pd.DataFrame(gdf.drop(columns="geometry"))
        df["lat"] = gdf.geometry.y
        df["lon"] = gdf.geometry.x

    fg = folium.FeatureGroup(name="Energy Generation Assets", show=True)
    for _, row in df.iterrows():
        row_dict = row.to_dict()
        def _safe_float(v):
            try:
                f = float(v)
                return f if f == f else None  # NaN check
            except (TypeError, ValueError):
                return None
        mw = _safe_float(row.get("capacity_mw")) or _safe_float(row.get("capacity_mwh")) or 1.0
        asset_type = str(row.get("type", ""))
        color = ASSET_COLORS.get(asset_type, "#888888")
        folium.CircleMarker(
            location=[float(row["lat"]), float(row["lon"])],
            radius=energy_circle_radius(mw),
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.85,
            weight=2,
            popup=folium.Popup(energy_popup_html(row_dict), max_width=280),
            tooltip=f"{row.get('name','')} ({mw} MW)" if row.get("capacity_mw") else row.get("name",""),
        ).add_to(fg)
    fg.add_to(m)


def add_substations(m):
    path = ENERGY_DIR / "substations_clean.geojson"
    if not path.exists():
        path = ENERGY_DIR / "substations.csv"
        if not path.exists():
            print("  NOTE: substations not found, skipping")
            return
        df = pd.read_csv(path)
    else:
        gdf = gpd.read_file(path)
        df = pd.DataFrame(gdf.drop(columns="geometry"))
        df["lat"] = gdf.geometry.y
        df["lon"] = gdf.geometry.x

    df["capacity_mva"] = pd.to_numeric(df.get("capacity_mva", 0), errors="coerce").fillna(0)
    vals = sorted(df["capacity_mva"].unique())
    thresholds = [0.5, 1.0, 2.0]

    fg = folium.FeatureGroup(name="Distribution Substations", show=True)
    for _, row in df.iterrows():
        row_dict = row.to_dict()
        cls = substation_capacity_class(float(row["capacity_mva"]), thresholds)
        color = SUBSTATION_COLORS[min(cls, len(SUBSTATION_COLORS) - 1)]
        folium.CircleMarker(
            location=[float(row["lat"]), float(row["lon"])],
            radius=10,
            color="#336699",
            fill=True,
            fill_color=color,
            fill_opacity=0.9,
            weight=1.5,
            popup=folium.Popup(substation_popup_html(row_dict, estimated=True), max_width=260),
            tooltip=f"Substation: {row.get('name','')} ({row.get('capacity_mva','')} MVA)",
        ).add_to(fg)
    fg.add_to(m)


def add_ev_stations(m):
    path = MOB_DIR / "ev_stations_clean.geojson"
    if not path.exists():
        path = MOB_DIR / "ev_charging_stations.csv"
        if not path.exists():
            return
        df = pd.read_csv(path)
    else:
        gdf = gpd.read_file(path)
        df = pd.DataFrame(gdf.drop(columns="geometry"))
        df["lat"] = gdf.geometry.y
        df["lon"] = gdf.geometry.x

    fg = folium.FeatureGroup(name="EV Charging Stations", show=True)
    for _, row in df.iterrows():
        row_dict = row.to_dict()
        folium.CircleMarker(
            location=[float(row["lat"]), float(row["lon"])],
            radius=7,
            color="#006d8f",
            fill=True,
            fill_color="#00b4d8",
            fill_opacity=0.9,
            weight=2,
            popup=folium.Popup(ev_station_popup_html(row_dict), max_width=240),
            tooltip=f"EV Charger: {row.get('name','')} ({row.get('power_kw','')} kW)",
        ).add_to(fg)
    fg.add_to(m)


def add_bus_route(m):
    path = MOB_DIR / "astymove_bus_routes.geojson"
    if not path.exists():
        return
    with open(path) as f:
        data = json.load(f)
    fg = folium.FeatureGroup(name="astyBUS Route", show=True)
    for feature in data.get("features", []):
        coords = feature["geometry"]["coordinates"]
        latlngs = [[c[1], c[0]] for c in coords]
        props = feature.get("properties", {})
        folium.PolyLine(
            latlngs,
            color="#8a2be2",
            weight=4,
            dash_array="10 6",
            opacity=0.85,
            tooltip=f"astyBUS: {props.get('stops','')}",
            popup=folium.Popup(
                f"<b>astyBUS Route</b><br>"
                f"<b>Stops:</b> {props.get('stops','')}<br>"
                f"<b>Vehicle:</b> {props.get('vehicle','')}<br>"
                f"<b>Operator:</b> {props.get('operator','')}<br>"
                f"<small style='color:#888'>Source: {props.get('source','')}</small>",
                max_width=280),
        ).add_to(fg)
    fg.add_to(m)


def add_congestion_roads(m, scenario: str):
    path = MOB_DIR / f"roads_congestion_{scenario}.geojson"
    if not path.exists():
        print(f"  NOTE: congestion roads for {scenario} not found, skipping")
        return
    gdf = gpd.read_file(path)
    label = "Summer Peak" if scenario == "summer" else "Winter Base"
    fg = folium.FeatureGroup(
        name=f"[{label}] Road Congestion",
        show=(scenario == "summer"),
    )
    for _, row in gdf.iterrows():
        level = float(row.get("congestion", 0.2))
        color = congestion_color(level)
        cl = congestion_label(level)
        coords = list(row.geometry.coords)
        latlngs = [[c[1], c[0]] for c in coords]
        if len(latlngs) < 2:
            continue
        name = row.get("name", "")
        hw = row.get("highway", "road")
        folium.PolyLine(
            latlngs,
            color=color,
            weight=4,
            opacity=0.8,
            tooltip=f"{name or hw} — {label}: {cl} ({level:.0%})",
        ).add_to(fg)
    fg.add_to(m)


def add_demand_heatmap(m, scenario: str):
    path = ENERGY_DIR / f"demand_zones_{scenario}.geojson"
    if not path.exists():
        print(f"  NOTE: demand zones for {scenario} not found, skipping")
        return
    gdf = gpd.read_file(path)
    label = "Summer Peak" if scenario == "summer" else "Winter Base"
    max_kw = float(gdf["demand_kw"].max())
    heat_data = [
        [float(row.geometry.y), float(row.geometry.x), float(row["demand_kw"]) / max_kw]
        for _, row in gdf.iterrows()
        if float(row["demand_kw"]) > 0
    ]
    fg = folium.FeatureGroup(
        name=f"[{label}] Demand Heatmap",
        show=(scenario == "summer"),
    )
    folium.plugins.HeatMap(
        heat_data,
        min_opacity=0.2,
        max_zoom=18,
        radius=25,
        blur=20,
        gradient={0.2: "#1e90ff", 0.5: "#ffd700", 0.8: "#ff6600", 1.0: "#cc0000"},
    ).add_to(fg)
    fg.add_to(m)


def main():
    print(f"Generating map...")
    m = folium.Map(
        location=ISLAND_CENTER,
        zoom_start=ZOOM,
        tiles=None,
        prefer_canvas=True,
    )
    folium.TileLayer(
        tiles="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
        attr='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
        name="CartoDB Positron",
        max_zoom=19,
    ).add_to(m)

    print("  Adding island boundary...")
    add_boundary(m)

    print("  Adding demand heatmap (summer)...")
    add_demand_heatmap(m, "summer")
    print("  Adding demand heatmap (winter)...")
    add_demand_heatmap(m, "winter")

    print("  Adding road congestion (summer)...")
    add_congestion_roads(m, "summer")
    print("  Adding road congestion (winter)...")
    add_congestion_roads(m, "winter")

    print("  Adding EV charging stations...")
    add_ev_stations(m)

    print("  Adding astyBUS route...")
    add_bus_route(m)

    print("  Adding distribution substations...")
    add_substations(m)

    print("  Adding energy generation assets...")
    add_energy_assets(m)

    folium.LayerControl(collapsed=False).add_to(m)

    m.get_root().html.add_child(folium.Element(build_legend_html()))
    m.get_root().html.add_child(folium.Element(build_scenario_toggle_html()))

    out = OUT_DIR / "map_astypalea.html"
    m.save(str(out))
    size_mb = out.stat().st_size / 1e6
    print(f"\nSaved: {out} ({size_mb:.1f} MB)")
    print("Open in browser: open docs/map_astypalea.html")


if __name__ == "__main__":
    main()

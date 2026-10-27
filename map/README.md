# Astypalea Interactive Energy & Mobility Map

Interactive web map for Astypalea island, Greece — part of the [Smart Sustainable Island](https://smartastypalea.gov.gr/) initiative.

## What the map shows

| Layer | Data quality | Source |
|-------|-------------|--------|
| Island boundary | Real | OpenStreetMap |
| Road network | Real | OpenStreetMap |
| Solar PV park (3.5 MW) | Real values, ~position | PPC Renewables press release, Apr 2022 |
| Battery storage (14.12 MWh) | Real values, ~position | PPC Renewables press release, Apr 2022 |
| Diesel thermal plant (~4.5 MW) | Estimated capacity & position | HEDNO island grid literature |
| Distribution substations | Estimated positions & capacity | HEDNO/academic literature on island grid topology |
| EV charging stations | Documented locations | astyMOVE project documentation |
| astyBUS route | Documented route | astyMOVE / Interreg Europe good practice report |
| Road congestion | **Modelled** | Seasonal factors from project documentation |
| Demand heatmap | **Modelled** | OSM buildings + 7 GWh/year HEDNO baseline |

## Build

```bash
cd map/
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python scripts/fetch_osm.py          # ~30s; writes to data/osm/ (gitignored)
python scripts/build_energy_data.py
python scripts/build_mobility_data.py
python scripts/build_demand_zones.py
python scripts/plot_map.py           # writes docs/map_astypalea.html

open docs/map_astypalea.html
```

## Data sources

- **OpenStreetMap** — island boundary, roads, buildings, POIs
- **PPC Renewables** — solar park + BESS specifications (press releases 2022)
- **HEDNO/DEDDIE** — distribution network baseline; hourly load data from Aalborg MSc thesis (2019)
- **astyMOVE / SEAT:CODE Giravolta** — EV charging locations, bus route (Interreg Europe 2024)
- **ENTSO-E / Greek Census 2021** — background statistics

## Known limitations

- Demand and congestion layers are **modelled estimates**, not real-time measurements. Calibrated to the 7 GWh/year island baseline (HEDNO 2014–2015).
- Substation positions are approximate (±500m), derived from published grid topology descriptions.
- The solar park and BESS position is approximate (±200m), placed in the Maltezana/Analipsi area per PPC documentation.
- OSM coverage of Astypalea is good for roads and the town center, but building footprints may be incomplete in rural areas.

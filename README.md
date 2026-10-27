# Astypalea Modeling — iPOY

This repository contains two sub-projects related to Astypalea, Greece — a 37 km² island in the South Aegean that is a flagship "smart sustainable island" initiative (Mercedes-Benz + Greek government partnership).

## Sub-projects

### [`map/`](map/) — Interactive Energy & Mobility Map

An interactive web map built with Python + Folium (Leaflet.js), showing:
- Energy generation assets (solar PV, battery storage, diesel plant)
- Distribution substations colored by estimated capacity
- Road network colored by estimated congestion
- EV charging station locations
- astyBUS electric minibus route
- Demand heatmap

Supports **Summer Peak** and **Winter Base** scenario toggle. Inspired by the [Catalunya capacity map](https://hhw2002.github.io/data-driven-challenge-project/map_catalunya.html).

→ See [map/README.md](map/README.md) for data sources and build instructions.

### [`ipoy/`](ipoy/) — Island Power & Operations Yearly Modeling

Yearly energy system modeling for Astypalea: demand/load profiles, generation dispatch, and resilience scenario simulation. Placeholder — not yet implemented.

→ See [ipoy/README.md](ipoy/README.md).

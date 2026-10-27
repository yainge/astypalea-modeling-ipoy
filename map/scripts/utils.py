"""Shared helpers for color scales, legend HTML, and popup builders."""

import math


# --- Color scales ---

def congestion_color(level: float) -> str:
    """Map congestion level 0.0–1.0 to a hex color (green → yellow → red)."""
    level = max(0.0, min(1.0, level))
    if level < 0.25:
        return "#2dc653"   # low: green
    elif level < 0.50:
        return "#f5c518"   # moderate: yellow
    elif level < 0.75:
        return "#f07f28"   # high: orange
    else:
        return "#d62828"   # critical: red


def congestion_label(level: float) -> str:
    if level < 0.25:
        return "Low"
    elif level < 0.50:
        return "Moderate"
    elif level < 0.75:
        return "High"
    else:
        return "Critical"


def demand_color(kw: float, max_kw: float) -> str:
    """Map demand in kW to a hex color (light blue → deep orange)."""
    ratio = max(0.0, min(1.0, kw / max_kw if max_kw > 0 else 0))
    r = int(30 + ratio * 220)
    g = int(144 - ratio * 110)
    b = int(255 - ratio * 220)
    return f"#{r:02x}{g:02x}{b:02x}"


ASSET_COLORS = {
    "solar_pv": "#f7c948",
    "battery": "#5aa469",
    "diesel_thermal": "#e05c3a",
    "wind": "#7ecae3",
}

SUBSTATION_COLORS = ["#b3d9ff", "#5aaff5", "#1c6fc9", "#0a3a7a"]


def energy_circle_radius(mw: float) -> int:
    """Return Folium circle radius in pixels from MW capacity (log scale, 8–40)."""
    if mw is None or mw <= 0:
        return 8
    return max(8, min(40, int(8 + 14 * math.log10(mw + 1))))


def substation_capacity_class(mva: float, thresholds: list[float]) -> int:
    """Return 0-based class index for a substation given quartile thresholds."""
    for i, t in enumerate(thresholds):
        if mva <= t:
            return i
    return len(thresholds)


# --- Popup / tooltip builders ---

ESTIMATED_BADGE = '<span style="background:#f0a500;color:#fff;padding:1px 5px;border-radius:3px;font-size:0.8em;">⚠ Estimated</span>'


def energy_popup_html(row: dict) -> str:
    cap_str = f"{row.get('capacity_mw', '')} MW" if row.get("capacity_mw") else ""
    batt_str = f"{row.get('capacity_mwh', '')} MWh" if row.get("capacity_mwh") else ""
    cap_display = " / ".join(filter(None, [cap_str, batt_str]))
    return f"""
<div style="font-family:sans-serif;min-width:180px">
  <b style="font-size:1.05em">{row.get('name','')}</b><br>
  <span style="color:#666;font-size:0.9em">{row.get('type','').replace('_',' ').title()}</span><br>
  <hr style="margin:4px 0">
  <b>Capacity:</b> {cap_display}<br>
  <b>Status:</b> {row.get('status','')}<br>
  <hr style="margin:4px 0">
  <small style="color:#888">Source: {row.get('source','')}</small><br>
  <small style="color:#888">{row.get('notes','')}</small>
</div>"""


def substation_popup_html(row: dict, estimated: bool = True) -> str:
    badge = ESTIMATED_BADGE if estimated else ""
    return f"""
<div style="font-family:sans-serif;min-width:160px">
  <b>{row.get('name','')}</b> {badge}<br>
  <b>Voltage:</b> {row.get('voltage_kv','')} kV<br>
  <b>Capacity:</b> {row.get('capacity_mva','')} MVA<br>
  <b>Serves:</b> {row.get('serves','')}<br>
  <hr style="margin:4px 0">
  <small style="color:#888">Source: {row.get('source','')}</small>
</div>"""


def ev_station_popup_html(row: dict) -> str:
    return f"""
<div style="font-family:sans-serif;min-width:160px">
  <b>EV Charging Station</b><br>
  {row.get('name','')}<br>
  <b>Power:</b> {row.get('power_kw','')} kW ({row.get('connector_type','')})<br>
  <b>Operator:</b> {row.get('operator','')}<br>
  <small style="color:#888">Source: {row.get('source','')}</small>
</div>"""


def demand_popup_html(demand_kw: float, scenario: str) -> str:
    return f"""
<div style="font-family:sans-serif;min-width:140px">
  <b>Demand Zone</b> {ESTIMATED_BADGE}<br>
  <b>Scenario:</b> {scenario}<br>
  <b>Estimated demand:</b> {demand_kw:.1f} kW<br>
  <hr style="margin:4px 0">
  <small style="color:#888">Modeled from OSM building footprints,<br>
  calibrated to 7 GWh/year island baseline.<br>
  Summer peak ×2.8, winter ×0.65.</small>
</div>"""


# --- Legend HTML ---

def build_legend_html() -> str:
    congestion_items = [
        ("#2dc653", "Low (&lt;0.25)"),
        ("#f5c518", "Moderate (0.25–0.50)"),
        ("#f07f28", "High (0.50–0.75)"),
        ("#d62828", "Critical (&gt;0.75)"),
    ]
    asset_items = [
        (ASSET_COLORS["solar_pv"], "Solar PV"),
        (ASSET_COLORS["battery"], "Battery Storage"),
        (ASSET_COLORS["diesel_thermal"], "Diesel Thermal"),
    ]
    substation_items = [
        (SUBSTATION_COLORS[0], "0–0.5 MVA"),
        (SUBSTATION_COLORS[1], "0.5–1.0 MVA"),
        (SUBSTATION_COLORS[2], "1.0–2.0 MVA"),
        (SUBSTATION_COLORS[3], "&gt;2.0 MVA"),
    ]

    def swatch(color, label):
        return (f'<div style="display:flex;align-items:center;margin:2px 0">'
                f'<span style="width:14px;height:14px;background:{color};'
                f'border-radius:50%;display:inline-block;margin-right:6px;flex-shrink:0"></span>'
                f'<span style="font-size:0.85em">{label}</span></div>')

    def section(title, items):
        rows = "\n".join(swatch(c, l) for c, l in items)
        return f'<b style="font-size:0.9em">{title}</b>\n{rows}'

    parts = [
        section("Generation Assets", asset_items),
        section("Substations (capacity)", substation_items),
        section("Road Congestion", congestion_items),
        '<div style="font-size:0.75em;color:#aaa;margin-top:6px;border-top:1px solid #ddd;padding-top:4px">'
        '⚠ Demand &amp; congestion data are<br>modelled estimates, not measured.</div>',
    ]

    body = "\n<hr style='margin:6px 0'>\n".join(parts)
    return f"""
<div id="map-legend" style="
  position:fixed;bottom:30px;left:10px;z-index:9999;
  background:white;padding:10px 12px;border-radius:6px;
  box-shadow:0 2px 8px rgba(0,0,0,0.25);max-width:200px;
  font-family:sans-serif;line-height:1.4">
  <b style="font-size:1em">Legend</b><br>
  <hr style="margin:4px 0">
  {body}
</div>"""


def build_scenario_toggle_html() -> str:
    return """
<div id="scenario-toggle" style="
  position:fixed;top:10px;left:50%;transform:translateX(-50%);z-index:9999;
  background:white;padding:8px 16px;border-radius:20px;
  box-shadow:0 2px 8px rgba(0,0,0,0.25);font-family:sans-serif;
  display:flex;align-items:center;gap:12px">
  <span style="font-weight:bold;font-size:0.9em">Scenario:</span>
  <label style="cursor:pointer;font-size:0.9em">
    <input type="radio" name="scenario" value="summer" checked onchange="toggleScenario(this.value)">
    ☀ Summer Peak
  </label>
  <label style="cursor:pointer;font-size:0.9em">
    <input type="radio" name="scenario" value="winter" onchange="toggleScenario(this.value)">
    ❄ Winter Base
  </label>
</div>
<script>
function toggleScenario(scenario) {
  var other = scenario === 'summer' ? 'winter' : 'summer';
  document.querySelectorAll('.leaflet-control-layers-overlays label').forEach(function(el) {
    var text = el.querySelector('span') ? el.querySelector('span').textContent.trim() : '';
    if (text.startsWith('[' + other.charAt(0).toUpperCase() + other.slice(1) + ']')) {
      var cb = el.querySelector('input[type=checkbox]');
      if (cb && cb.checked) cb.click();
    }
    if (text.startsWith('[' + scenario.charAt(0).toUpperCase() + scenario.slice(1) + ']')) {
      var cb = el.querySelector('input[type=checkbox]');
      if (cb && !cb.checked) cb.click();
    }
  });
}
</script>"""

"""Generate modeled hourly load profile for Astypalea (run once to produce load_profiles.csv)."""
import math
import csv

ANNUAL_GWH = 7.0  # HEDNO baseline 2014-2015
MEAN_MW = ANNUAL_GWH * 1000 / 8760  # ~0.799 MW

SEASONAL = {1: 0.65, 2: 0.65, 3: 0.9, 4: 0.9, 5: 1.2, 6: 1.8,
            7: 2.8, 8: 2.8, 9: 1.8, 10: 1.2, 11: 0.9, 12: 0.65}
DAYS_IN_MONTH = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

rows = [["hour_of_year", "month", "day_of_month", "hour_of_day", "load_mw"]]
hour = 0
for month in range(1, 13):
    for day in range(1, DAYS_IN_MONTH[month - 1] + 1):
        for h in range(24):
            diurnal = 0.7 + 0.3 * math.sin(math.pi * (h - 4) / 16) if 4 <= h <= 20 else 0.7
            load = round(MEAN_MW * diurnal * SEASONAL[month], 4)
            rows.append([hour + 1, month, day, h, load])
            hour += 1

with open("load_profiles.csv", "w", newline="") as f:
    csv.writer(f).writerows(rows)

print(f"Written {hour} rows. Annual total: {sum(r[4] for r in rows[1:]):.1f} MWh")


# Stage 0 unit commitment check — Astypalea diesel station

This is a simulation model, not a digital twin. All generator parameters except p_nom (1.1 MW,
verified) are assumptions pending confirmation.  Results show the gap between cost-optimal dispatch
and HEDNO's observed commitment, which implies HEDNO's reserve rule.  See model/config.yaml for full
parameter provenance.


## 1. Data coverage

Model window: Sep 2025 – Aug 2026.  Hours with valid data: see table below.  Hours excluded (NaN
demand or missing timestamp): 0.  Three missing weeks are documented in DATA_NOTES.md §4 (2025-10-21
to 2025-10-27, 2026-01-27 to 2026-02-02, 2026-02-24 to 2026-03-02).  These weeks are absent from the
comparison without imputation.

Month boundaries cut commitment continuity: the initial generator status at the first snapshot of
each month is unconstrained.  Min-up / min-down constraints do not span month boundaries, so
start/stop events at month edges may be over-counted relative to a rolling optimisation.


## 2. Variant summary — exact match and MAE

| variant   | load_basis   | letter_avail   |   n_valid |   exact_match |   mae |   voll_hours |   reserve_slack_hours |   n_4unit_hours |
|:----------|:-------------|:---------------|----------:|--------------:|------:|-------------:|----------------------:|----------------:|
| C_020     | gross        | ignored        |      9071 |          0.76 |  0.25 |           99 |                    99 |               0 |
| C_020     | gross        | unavailable    |      9071 |          0.76 |  0.25 |           99 |                    99 |               0 |
| C_020     | net          | ignored        |      9071 |          0.72 |  0.28 |           99 |                    99 |               0 |
| C_020     | net          | unavailable    |      9071 |          0.72 |  0.28 |           99 |                    99 |               0 |
| A         | gross        | unavailable    |      9071 |          0.71 |  0.29 |           99 |                     0 |               0 |
| A         | gross        | ignored        |      9071 |          0.71 |  0.29 |           99 |                     0 |               0 |
| A         | net          | unavailable    |      9071 |          0.69 |  0.31 |          100 |                     0 |               0 |
| A         | net          | ignored        |      9071 |          0.69 |  0.31 |          100 |                     0 |               0 |
| C_050     | net          | ignored        |      9071 |          0.67 |  0.36 |           99 |                    99 |             430 |
| C_050     | net          | unavailable    |      9071 |          0.67 |  0.36 |           99 |                    99 |             430 |
| C_050     | gross        | ignored        |      9071 |          0.62 |  0.41 |           99 |                    99 |             422 |
| C_050     | gross        | unavailable    |      9071 |          0.62 |  0.41 |           99 |                    99 |             422 |
| B         | net          | ignored        |      9071 |          0.57 |  0.47 |           99 |                  4619 |             589 |
| B         | net          | unavailable    |      9071 |          0.57 |  0.47 |           99 |                  4619 |             589 |
| B         | gross        | unavailable    |      9071 |          0.55 |  0.50 |           99 |                  4620 |             637 |
| B         | gross        | ignored        |      9071 |          0.55 |  0.50 |           99 |                  4620 |             637 |
| C_100     | gross        | ignored        |      9071 |          0.54 |  0.52 |           99 |                  1630 |             773 |
| C_100     | gross        | unavailable    |      9071 |          0.54 |  0.52 |           99 |                  1630 |             773 |
| C_100     | net          | ignored        |      9071 |          0.52 |  0.53 |           99 |                  1630 |             780 |
| C_100     | net          | unavailable    |      9071 |          0.52 |  0.53 |           99 |                  1630 |             780 |


## 3. Best-matching configuration

Best: variant=C_020, load_basis=gross, letter_avail=ignored.  Exact match: 75.8%, MAE: 0.245 units.
VoLL-active hours (unserved load): 99.  Reserve-slack hours (N-1 or fractional reserve not met by
diesel alone): 99.


## 4. Confusion matrix (HEDNO count vs model count) — best variant

|   model=0 |   model=1 |   model=2 |   model=3 |
|----------:|----------:|----------:|----------:|
|         2 |         0 |         0 |         0 |
|       406 |      5896 |       445 |         0 |
|        26 |       464 |       788 |       752 |
|         0 |         0 |       104 |       188 |


## 5. By-month breakdown — best variant

| month   |   exact_match |   mae |   n_hours |
|:--------|--------------:|------:|----------:|
| 2025-09 |          0.69 |  0.31 |    363.00 |
| 2025-10 |          0.92 |  0.08 |    575.00 |
| 2025-11 |          0.97 |  0.03 |    720.00 |
| 2025-12 |          0.89 |  0.11 |    744.00 |
| 2026-01 |          0.77 |  0.26 |    622.00 |
| 2026-02 |          0.98 |  0.02 |    626.00 |
| 2026-03 |          0.81 |  0.18 |    744.00 |
| 2026-04 |          0.83 |  0.18 |    720.00 |
| 2026-05 |          0.98 |  0.01 |    744.00 |
| 2026-06 |          0.63 |  0.37 |    720.00 |
| 2026-07 |          0.15 |  0.85 |    744.00 |
| 2026-08 |          0.42 |  0.58 |    741.00 |
| 2026-09 |          0.74 |  0.26 |    555.00 |
| 2026-10 |          0.91 |  0.09 |    453.00 |


## 6. By hour-of-day breakdown — best variant

|   hour_of_day |   exact_match |   mae |
|--------------:|--------------:|------:|
|          0.00 |          0.77 |  0.23 |
|          1.00 |          0.77 |  0.23 |
|          2.00 |          0.77 |  0.23 |
|          3.00 |          0.77 |  0.23 |
|          4.00 |          0.77 |  0.23 |
|          5.00 |          0.79 |  0.21 |
|          6.00 |          0.79 |  0.21 |
|          7.00 |          0.77 |  0.23 |
|          8.00 |          0.73 |  0.28 |
|          9.00 |          0.70 |  0.30 |
|         10.00 |          0.70 |  0.30 |
|         11.00 |          0.75 |  0.26 |
|         12.00 |          0.77 |  0.23 |
|         13.00 |          0.77 |  0.23 |
|         14.00 |          0.75 |  0.26 |
|         15.00 |          0.73 |  0.27 |
|         16.00 |          0.73 |  0.28 |
|         17.00 |          0.71 |  0.29 |
|         18.00 |          0.75 |  0.26 |
|         19.00 |          0.77 |  0.23 |
|         20.00 |          0.80 |  0.21 |
|         21.00 |          0.78 |  0.22 |
|         22.00 |          0.78 |  0.22 |
|         23.00 |          0.77 |  0.23 |


## 7. Monthly diesel energy vs bulletins

Note: Sep 2025 and Sep–Oct 2026 show large negative diff_pct because the model window starts on
2025-09-16 (first available weekly actual) and the bulletin covers the full calendar month.  The
discrepancy in early months is a coverage artifact, not a model error.  Months with full coverage
(Nov 2025 – Aug 2026) are the meaningful comparison.

| month   | variant   | load_basis   | letter_avail   |   model_thermal_mwh |   diff_pct |   bulletin_thermal_mwh |
|:--------|:----------|:-------------|:---------------|--------------------:|-----------:|-----------------------:|
| 2025-09 | A         | gross        | ignored        |              284.60 |     -58.60 |                 686.90 |
| 2025-09 | A         | gross        | unavailable    |              284.60 |     -58.60 |                 686.90 |
| 2025-09 | A         | net          | ignored        |              310.50 |     -54.80 |                 686.90 |
| 2025-09 | A         | net          | unavailable    |              310.50 |     -54.80 |                 686.90 |
| 2025-09 | B         | gross        | ignored        |              289.60 |     -57.80 |                 686.90 |
| 2025-09 | B         | gross        | unavailable    |              289.60 |     -57.80 |                 686.90 |
| 2025-09 | B         | net          | ignored        |              310.50 |     -54.80 |                 686.90 |
| 2025-09 | B         | net          | unavailable    |              310.50 |     -54.80 |                 686.90 |
| 2025-09 | C_020     | gross        | ignored        |              284.60 |     -58.60 |                 686.90 |
| 2025-09 | C_020     | gross        | unavailable    |              284.60 |     -58.60 |                 686.90 |
| 2025-09 | C_020     | net          | ignored        |              310.50 |     -54.80 |                 686.90 |
| 2025-09 | C_020     | net          | unavailable    |              310.50 |     -54.80 |                 686.90 |
| 2025-09 | C_050     | gross        | ignored        |              288.40 |     -58.00 |                 686.90 |
| 2025-09 | C_050     | gross        | unavailable    |              288.40 |     -58.00 |                 686.90 |
| 2025-09 | C_050     | net          | ignored        |              310.50 |     -54.80 |                 686.90 |
| 2025-09 | C_050     | net          | unavailable    |              310.50 |     -54.80 |                 686.90 |
| 2025-09 | C_100     | gross        | ignored        |              289.60 |     -57.80 |                 686.90 |
| 2025-09 | C_100     | gross        | unavailable    |              289.60 |     -57.80 |                 686.90 |
| 2025-09 | C_100     | net          | ignored        |              310.50 |     -54.80 |                 686.90 |
| 2025-09 | C_100     | net          | unavailable    |              310.50 |     -54.80 |                 686.90 |
| 2025-10 | A         | gross        | ignored        |              308.40 |     -23.00 |                 400.70 |
| 2025-10 | A         | gross        | unavailable    |              308.40 |     -23.00 |                 400.70 |
| 2025-10 | A         | net          | ignored        |              333.60 |     -16.70 |                 400.70 |
| 2025-10 | A         | net          | unavailable    |              333.60 |     -16.70 |                 400.70 |
| 2025-10 | B         | gross        | ignored        |              310.60 |     -22.50 |                 400.70 |
| 2025-10 | B         | gross        | unavailable    |              310.60 |     -22.50 |                 400.70 |
| 2025-10 | B         | net          | ignored        |              333.60 |     -16.70 |                 400.70 |
| 2025-10 | B         | net          | unavailable    |              333.60 |     -16.70 |                 400.70 |
| 2025-10 | C_020     | gross        | ignored        |              308.40 |     -23.00 |                 400.70 |
| 2025-10 | C_020     | gross        | unavailable    |              308.40 |     -23.00 |                 400.70 |
| 2025-10 | C_020     | net          | ignored        |              333.60 |     -16.70 |                 400.70 |
| 2025-10 | C_020     | net          | unavailable    |              333.60 |     -16.70 |                 400.70 |
| 2025-10 | C_050     | gross        | ignored        |              308.50 |     -23.00 |                 400.70 |
| 2025-10 | C_050     | gross        | unavailable    |              308.50 |     -23.00 |                 400.70 |
| 2025-10 | C_050     | net          | ignored        |              333.60 |     -16.70 |                 400.70 |
| 2025-10 | C_050     | net          | unavailable    |              333.60 |     -16.70 |                 400.70 |
| 2025-10 | C_100     | gross        | ignored        |              310.60 |     -22.50 |                 400.70 |
| 2025-10 | C_100     | gross        | unavailable    |              310.60 |     -22.50 |                 400.70 |
| 2025-10 | C_100     | net          | ignored        |              333.60 |     -16.70 |                 400.70 |
| 2025-10 | C_100     | net          | unavailable    |              333.60 |     -16.70 |                 400.70 |
| 2025-11 | A         | gross        | ignored        |              321.70 |      -0.40 |                 323.10 |
| 2025-11 | A         | gross        | unavailable    |              321.70 |      -0.40 |                 323.10 |
| 2025-11 | A         | net          | ignored        |              341.90 |       5.80 |                 323.10 |
| 2025-11 | A         | net          | unavailable    |              341.90 |       5.80 |                 323.10 |
| 2025-11 | B         | gross        | ignored        |              321.70 |      -0.40 |                 323.10 |
| 2025-11 | B         | gross        | unavailable    |              321.70 |      -0.40 |                 323.10 |
| 2025-11 | B         | net          | ignored        |              341.90 |       5.80 |                 323.10 |
| 2025-11 | B         | net          | unavailable    |              341.90 |       5.80 |                 323.10 |
| 2025-11 | C_020     | gross        | ignored        |              321.70 |      -0.40 |                 323.10 |
| 2025-11 | C_020     | gross        | unavailable    |              321.70 |      -0.40 |                 323.10 |
| 2025-11 | C_020     | net          | ignored        |              341.90 |       5.80 |                 323.10 |
| 2025-11 | C_020     | net          | unavailable    |              341.90 |       5.80 |                 323.10 |
| 2025-11 | C_050     | gross        | ignored        |              321.70 |      -0.40 |                 323.10 |
| 2025-11 | C_050     | gross        | unavailable    |              321.70 |      -0.40 |                 323.10 |
| 2025-11 | C_050     | net          | ignored        |              341.90 |       5.80 |                 323.10 |
| 2025-11 | C_050     | net          | unavailable    |              341.90 |       5.80 |                 323.10 |
| 2025-11 | C_100     | gross        | ignored        |              321.70 |      -0.40 |                 323.10 |
| 2025-11 | C_100     | gross        | unavailable    |              321.70 |      -0.40 |                 323.10 |
| 2025-11 | C_100     | net          | ignored        |              341.90 |       5.80 |                 323.10 |
| 2025-11 | C_100     | net          | unavailable    |              341.90 |       5.80 |                 323.10 |
| 2025-12 | A         | gross        | ignored        |              369.10 |      -0.00 |                 369.10 |
| 2025-12 | A         | gross        | unavailable    |              369.10 |      -0.00 |                 369.10 |
| 2025-12 | A         | net          | ignored        |              389.60 |       5.50 |                 369.10 |
| 2025-12 | A         | net          | unavailable    |              389.60 |       5.50 |                 369.10 |
| 2025-12 | B         | gross        | ignored        |              369.30 |       0.00 |                 369.10 |
| 2025-12 | B         | gross        | unavailable    |              369.30 |       0.00 |                 369.10 |
| 2025-12 | B         | net          | ignored        |              389.60 |       5.50 |                 369.10 |
| 2025-12 | B         | net          | unavailable    |              389.60 |       5.50 |                 369.10 |
| 2025-12 | C_020     | gross        | ignored        |              369.10 |      -0.00 |                 369.10 |
| 2025-12 | C_020     | gross        | unavailable    |              369.10 |      -0.00 |                 369.10 |
| 2025-12 | C_020     | net          | ignored        |              389.60 |       5.50 |                 369.10 |
| 2025-12 | C_020     | net          | unavailable    |              389.60 |       5.50 |                 369.10 |
| 2025-12 | C_050     | gross        | ignored        |              369.10 |      -0.00 |                 369.10 |
| 2025-12 | C_050     | gross        | unavailable    |              369.10 |      -0.00 |                 369.10 |
| 2025-12 | C_050     | net          | ignored        |              389.60 |       5.50 |                 369.10 |
| 2025-12 | C_050     | net          | unavailable    |              389.60 |       5.50 |                 369.10 |
| 2025-12 | C_100     | gross        | ignored        |              369.30 |       0.00 |                 369.10 |
| 2025-12 | C_100     | gross        | unavailable    |              369.30 |       0.00 |                 369.10 |
| 2025-12 | C_100     | net          | ignored        |              389.60 |       5.50 |                 369.10 |
| 2025-12 | C_100     | net          | unavailable    |              389.60 |       5.50 |                 369.10 |
| 2026-01 | A         | gross        | ignored        |              347.70 |     -15.50 |                 411.40 |
| 2026-01 | A         | gross        | unavailable    |              347.70 |     -15.50 |                 411.40 |
| 2026-01 | A         | net          | ignored        |              371.40 |      -9.70 |                 411.40 |
| 2026-01 | A         | net          | unavailable    |              371.40 |      -9.70 |                 411.40 |
| 2026-01 | B         | gross        | ignored        |              350.00 |     -14.90 |                 411.40 |
| 2026-01 | B         | gross        | unavailable    |              350.00 |     -14.90 |                 411.40 |
| 2026-01 | B         | net          | ignored        |              371.40 |      -9.70 |                 411.40 |
| 2026-01 | B         | net          | unavailable    |              371.40 |      -9.70 |                 411.40 |
| 2026-01 | C_020     | gross        | ignored        |              347.70 |     -15.50 |                 411.40 |
| 2026-01 | C_020     | gross        | unavailable    |              347.70 |     -15.50 |                 411.40 |
| 2026-01 | C_020     | net          | ignored        |              371.40 |      -9.70 |                 411.40 |
| 2026-01 | C_020     | net          | unavailable    |              371.40 |      -9.70 |                 411.40 |
| 2026-01 | C_050     | gross        | ignored        |              348.00 |     -15.40 |                 411.40 |
| 2026-01 | C_050     | gross        | unavailable    |              348.00 |     -15.40 |                 411.40 |
| 2026-01 | C_050     | net          | ignored        |              371.40 |      -9.70 |                 411.40 |
| 2026-01 | C_050     | net          | unavailable    |              371.40 |      -9.70 |                 411.40 |
| 2026-01 | C_100     | gross        | ignored        |              350.00 |     -14.90 |                 411.40 |
| 2026-01 | C_100     | gross        | unavailable    |              350.00 |     -14.90 |                 411.40 |
| 2026-01 | C_100     | net          | ignored        |              371.40 |      -9.70 |                 411.40 |
| 2026-01 | C_100     | net          | unavailable    |              371.40 |      -9.70 |                 411.40 |
| 2026-02 | A         | gross        | ignored        |              330.90 |      -7.30 |                 357.10 |
| 2026-02 | A         | gross        | unavailable    |              330.90 |      -7.30 |                 357.10 |
| 2026-02 | A         | net          | ignored        |              352.70 |      -1.20 |                 357.10 |
| 2026-02 | A         | net          | unavailable    |              352.70 |      -1.20 |                 357.10 |
| 2026-02 | B         | gross        | ignored        |              331.70 |      -7.10 |                 357.10 |
| 2026-02 | B         | gross        | unavailable    |              331.70 |      -7.10 |                 357.10 |
| 2026-02 | B         | net          | ignored        |              352.70 |      -1.20 |                 357.10 |
| 2026-02 | B         | net          | unavailable    |              352.70 |      -1.20 |                 357.10 |
| 2026-02 | C_020     | gross        | ignored        |              330.90 |      -7.30 |                 357.10 |
| 2026-02 | C_020     | gross        | unavailable    |              330.90 |      -7.30 |                 357.10 |
| 2026-02 | C_020     | net          | ignored        |              352.70 |      -1.20 |                 357.10 |
| 2026-02 | C_020     | net          | unavailable    |              352.70 |      -1.20 |                 357.10 |
| 2026-02 | C_050     | gross        | ignored        |              331.10 |      -7.30 |                 357.10 |
| 2026-02 | C_050     | gross        | unavailable    |              331.10 |      -7.30 |                 357.10 |
| 2026-02 | C_050     | net          | ignored        |              352.70 |      -1.20 |                 357.10 |
| 2026-02 | C_050     | net          | unavailable    |              352.70 |      -1.20 |                 357.10 |
| 2026-02 | C_100     | gross        | ignored        |              331.70 |      -7.10 |                 357.10 |
| 2026-02 | C_100     | gross        | unavailable    |              331.70 |      -7.10 |                 357.10 |
| 2026-02 | C_100     | net          | ignored        |              352.70 |      -1.20 |                 357.10 |
| 2026-02 | C_100     | net          | unavailable    |              352.70 |      -1.20 |                 357.10 |
| 2026-03 | A         | gross        | ignored        |              379.90 |      -3.00 |                 391.80 |
| 2026-03 | A         | gross        | unavailable    |              379.90 |      -3.00 |                 391.80 |
| 2026-03 | A         | net          | ignored        |              404.90 |       3.40 |                 391.80 |
| 2026-03 | A         | net          | unavailable    |              404.90 |       3.40 |                 391.80 |
| 2026-03 | B         | gross        | ignored        |              381.20 |      -2.70 |                 391.80 |
| 2026-03 | B         | gross        | unavailable    |              381.20 |      -2.70 |                 391.80 |
| 2026-03 | B         | net          | ignored        |              404.90 |       3.40 |                 391.80 |
| 2026-03 | B         | net          | unavailable    |              404.90 |       3.40 |                 391.80 |
| 2026-03 | C_020     | gross        | ignored        |              379.90 |      -3.00 |                 391.80 |
| 2026-03 | C_020     | gross        | unavailable    |              379.90 |      -3.00 |                 391.80 |
| 2026-03 | C_020     | net          | ignored        |              404.90 |       3.40 |                 391.80 |
| 2026-03 | C_020     | net          | unavailable    |              404.90 |       3.40 |                 391.80 |
| 2026-03 | C_050     | gross        | ignored        |              380.30 |      -2.90 |                 391.80 |
| 2026-03 | C_050     | gross        | unavailable    |              380.30 |      -2.90 |                 391.80 |
| 2026-03 | C_050     | net          | ignored        |              404.90 |       3.40 |                 391.80 |
| 2026-03 | C_050     | net          | unavailable    |              404.90 |       3.40 |                 391.80 |
| 2026-03 | C_100     | gross        | ignored        |              381.20 |      -2.70 |                 391.80 |
| 2026-03 | C_100     | gross        | unavailable    |              381.20 |      -2.70 |                 391.80 |
| 2026-03 | C_100     | net          | ignored        |              404.90 |       3.40 |                 391.80 |
| 2026-03 | C_100     | net          | unavailable    |              404.90 |       3.40 |                 391.80 |
| 2026-04 | A         | gross        | ignored        |              357.10 |      -3.20 |                 368.90 |
| 2026-04 | A         | gross        | unavailable    |              357.10 |      -3.20 |                 368.90 |
| 2026-04 | A         | net          | ignored        |              391.90 |       6.20 |                 368.90 |
| 2026-04 | A         | net          | unavailable    |              391.90 |       6.20 |                 368.90 |
| 2026-04 | B         | gross        | ignored        |              360.20 |      -2.40 |                 368.90 |
| 2026-04 | B         | gross        | unavailable    |              360.20 |      -2.40 |                 368.90 |
| 2026-04 | B         | net          | ignored        |              391.90 |       6.20 |                 368.90 |
| 2026-04 | B         | net          | unavailable    |              391.90 |       6.20 |                 368.90 |
| 2026-04 | C_020     | gross        | ignored        |              357.10 |      -3.20 |                 368.90 |
| 2026-04 | C_020     | gross        | unavailable    |              357.10 |      -3.20 |                 368.90 |
| 2026-04 | C_020     | net          | ignored        |              391.90 |       6.20 |                 368.90 |
| 2026-04 | C_020     | net          | unavailable    |              391.90 |       6.20 |                 368.90 |
| 2026-04 | C_050     | gross        | ignored        |              357.70 |      -3.00 |                 368.90 |
| 2026-04 | C_050     | gross        | unavailable    |              357.70 |      -3.00 |                 368.90 |
| 2026-04 | C_050     | net          | ignored        |              391.90 |       6.20 |                 368.90 |
| 2026-04 | C_050     | net          | unavailable    |              391.90 |       6.20 |                 368.90 |
| 2026-04 | C_100     | gross        | ignored        |              360.20 |      -2.40 |                 368.90 |
| 2026-04 | C_100     | gross        | unavailable    |              360.20 |      -2.40 |                 368.90 |
| 2026-04 | C_100     | net          | ignored        |              391.90 |       6.20 |                 368.90 |
| 2026-04 | C_100     | net          | unavailable    |              391.90 |       6.20 |                 368.90 |
| 2026-05 | A         | gross        | ignored        |              409.40 |      -9.80 |                 454.00 |
| 2026-05 | A         | gross        | unavailable    |              409.40 |      -9.80 |                 454.00 |
| 2026-05 | A         | net          | ignored        |              462.00 |       1.70 |                 454.00 |
| 2026-05 | A         | net          | unavailable    |              462.00 |       1.70 |                 454.00 |
| 2026-05 | B         | gross        | ignored        |              416.70 |      -8.20 |                 454.00 |
| 2026-05 | B         | gross        | unavailable    |              416.70 |      -8.20 |                 454.00 |
| 2026-05 | B         | net          | ignored        |              462.00 |       1.70 |                 454.00 |
| 2026-05 | B         | net          | unavailable    |              462.00 |       1.70 |                 454.00 |
| 2026-05 | C_020     | gross        | ignored        |              409.40 |      -9.80 |                 454.00 |
| 2026-05 | C_020     | gross        | unavailable    |              409.40 |      -9.80 |                 454.00 |
| 2026-05 | C_020     | net          | ignored        |              462.00 |       1.70 |                 454.00 |
| 2026-05 | C_020     | net          | unavailable    |              462.00 |       1.70 |                 454.00 |
| 2026-05 | C_050     | gross        | ignored        |              410.20 |      -9.60 |                 454.00 |
| 2026-05 | C_050     | gross        | unavailable    |              410.20 |      -9.60 |                 454.00 |
| 2026-05 | C_050     | net          | ignored        |              462.00 |       1.70 |                 454.00 |
| 2026-05 | C_050     | net          | unavailable    |              462.00 |       1.70 |                 454.00 |
| 2026-05 | C_100     | gross        | ignored        |              416.70 |      -8.20 |                 454.00 |
| 2026-05 | C_100     | gross        | unavailable    |              416.70 |      -8.20 |                 454.00 |
| 2026-05 | C_100     | net          | ignored        |              462.00 |       1.70 |                 454.00 |
| 2026-05 | C_100     | net          | unavailable    |              462.00 |       1.70 |                 454.00 |
| 2026-06 | A         | gross        | ignored        |              620.40 |      -6.40 |                 663.00 |
| 2026-06 | A         | gross        | unavailable    |              620.40 |      -6.40 |                 663.00 |
| 2026-06 | A         | net          | ignored        |              676.80 |       2.10 |                 663.00 |
| 2026-06 | A         | net          | unavailable    |              676.80 |       2.10 |                 663.00 |
| 2026-06 | B         | gross        | ignored        |              630.70 |      -4.90 |                 663.00 |
| 2026-06 | B         | gross        | unavailable    |              630.70 |      -4.90 |                 663.00 |
| 2026-06 | B         | net          | ignored        |              676.80 |       2.10 |                 663.00 |
| 2026-06 | B         | net          | unavailable    |              676.80 |       2.10 |                 663.00 |
| 2026-06 | C_020     | gross        | ignored        |              620.50 |      -6.40 |                 663.00 |
| 2026-06 | C_020     | gross        | unavailable    |              620.50 |      -6.40 |                 663.00 |
| 2026-06 | C_020     | net          | ignored        |              676.80 |       2.10 |                 663.00 |
| 2026-06 | C_020     | net          | unavailable    |              676.80 |       2.10 |                 663.00 |
| 2026-06 | C_050     | gross        | ignored        |              626.00 |      -5.60 |                 663.00 |
| 2026-06 | C_050     | gross        | unavailable    |              626.00 |      -5.60 |                 663.00 |
| 2026-06 | C_050     | net          | ignored        |              676.80 |       2.10 |                 663.00 |
| 2026-06 | C_050     | net          | unavailable    |              676.80 |       2.10 |                 663.00 |
| 2026-06 | C_100     | gross        | ignored        |              630.70 |      -4.90 |                 663.00 |
| 2026-06 | C_100     | gross        | unavailable    |              630.70 |      -4.90 |                 663.00 |
| 2026-06 | C_100     | net          | ignored        |              676.80 |       2.10 |                 663.00 |
| 2026-06 | C_100     | net          | unavailable    |              676.80 |       2.10 |                 663.00 |
| 2026-07 | A         | gross        | ignored        |             1036.80 |      -6.10 |                1104.50 |
| 2026-07 | A         | gross        | unavailable    |             1036.80 |      -6.10 |                1104.50 |
| 2026-07 | A         | net          | ignored        |             1096.30 |      -0.70 |                1104.50 |
| 2026-07 | A         | net          | unavailable    |             1096.30 |      -0.70 |                1104.50 |
| 2026-07 | B         | gross        | ignored        |             1037.10 |      -6.10 |                1104.50 |
| 2026-07 | B         | gross        | unavailable    |             1037.10 |      -6.10 |                1104.50 |
| 2026-07 | B         | net          | ignored        |             1096.30 |      -0.70 |                1104.50 |
| 2026-07 | B         | net          | unavailable    |             1096.30 |      -0.70 |                1104.50 |
| 2026-07 | C_020     | gross        | ignored        |             1036.80 |      -6.10 |                1104.50 |
| 2026-07 | C_020     | gross        | unavailable    |             1036.80 |      -6.10 |                1104.50 |
| 2026-07 | C_020     | net          | ignored        |             1096.30 |      -0.70 |                1104.50 |
| 2026-07 | C_020     | net          | unavailable    |             1096.30 |      -0.70 |                1104.50 |
| 2026-07 | C_050     | gross        | ignored        |             1036.90 |      -6.10 |                1104.50 |
| 2026-07 | C_050     | gross        | unavailable    |             1036.90 |      -6.10 |                1104.50 |
| 2026-07 | C_050     | net          | ignored        |             1096.30 |      -0.70 |                1104.50 |
| 2026-07 | C_050     | net          | unavailable    |             1096.30 |      -0.70 |                1104.50 |
| 2026-07 | C_100     | gross        | ignored        |             1037.10 |      -6.10 |                1104.50 |
| 2026-07 | C_100     | gross        | unavailable    |             1037.10 |      -6.10 |                1104.50 |
| 2026-07 | C_100     | net          | ignored        |             1096.30 |      -0.70 |                1104.50 |
| 2026-07 | C_100     | net          | unavailable    |             1096.30 |      -0.70 |                1104.50 |
| 2026-08 | A         | gross        | ignored        |             1210.80 |      -3.50 |                1255.00 |
| 2026-08 | A         | gross        | unavailable    |             1210.80 |      -3.50 |                1255.00 |
| 2026-08 | A         | net          | ignored        |             1269.70 |       1.20 |                1255.00 |
| 2026-08 | A         | net          | unavailable    |             1269.70 |       1.20 |                1255.00 |
| 2026-08 | B         | gross        | ignored        |             1212.10 |      -3.40 |                1255.00 |
| 2026-08 | B         | gross        | unavailable    |             1212.10 |      -3.40 |                1255.00 |
| 2026-08 | B         | net          | ignored        |             1269.70 |       1.20 |                1255.00 |
| 2026-08 | B         | net          | unavailable    |             1269.70 |       1.20 |                1255.00 |
| 2026-08 | C_020     | gross        | ignored        |             1210.80 |      -3.50 |                1255.00 |
| 2026-08 | C_020     | gross        | unavailable    |             1210.80 |      -3.50 |                1255.00 |
| 2026-08 | C_020     | net          | ignored        |             1269.70 |       1.20 |                1255.00 |
| 2026-08 | C_020     | net          | unavailable    |             1269.70 |       1.20 |                1255.00 |
| 2026-08 | C_050     | gross        | ignored        |             1210.80 |      -3.50 |                1255.00 |
| 2026-08 | C_050     | gross        | unavailable    |             1210.80 |      -3.50 |                1255.00 |
| 2026-08 | C_050     | net          | ignored        |             1269.70 |       1.20 |                1255.00 |
| 2026-08 | C_050     | net          | unavailable    |             1269.70 |       1.20 |                1255.00 |
| 2026-08 | C_100     | gross        | ignored        |             1210.80 |      -3.50 |                1255.00 |
| 2026-08 | C_100     | gross        | unavailable    |             1210.80 |      -3.50 |                1255.00 |
| 2026-08 | C_100     | net          | ignored        |             1269.70 |       1.20 |                1255.00 |
| 2026-08 | C_100     | net          | unavailable    |             1269.70 |       1.20 |                1255.00 |
| 2026-09 | A         | gross        | ignored        |              531.50 |     nan    |                 nan    |
| 2026-09 | A         | gross        | unavailable    |              531.50 |     nan    |                 nan    |
| 2026-09 | A         | net          | ignored        |              571.40 |     nan    |                 nan    |
| 2026-09 | A         | net          | unavailable    |              571.40 |     nan    |                 nan    |
| 2026-09 | B         | gross        | ignored        |              536.60 |     nan    |                 nan    |
| 2026-09 | B         | gross        | unavailable    |              536.60 |     nan    |                 nan    |
| 2026-09 | B         | net          | ignored        |              571.40 |     nan    |                 nan    |
| 2026-09 | B         | net          | unavailable    |              571.40 |     nan    |                 nan    |
| 2026-09 | C_020     | gross        | ignored        |              531.50 |     nan    |                 nan    |
| 2026-09 | C_020     | gross        | unavailable    |              531.50 |     nan    |                 nan    |
| 2026-09 | C_020     | net          | ignored        |              571.40 |     nan    |                 nan    |
| 2026-09 | C_020     | net          | unavailable    |              571.40 |     nan    |                 nan    |
| 2026-09 | C_050     | gross        | ignored        |              533.30 |     nan    |                 nan    |
| 2026-09 | C_050     | gross        | unavailable    |              533.30 |     nan    |                 nan    |
| 2026-09 | C_050     | net          | ignored        |              571.40 |     nan    |                 nan    |
| 2026-09 | C_050     | net          | unavailable    |              571.40 |     nan    |                 nan    |
| 2026-09 | C_100     | gross        | ignored        |              536.60 |     nan    |                 nan    |
| 2026-09 | C_100     | gross        | unavailable    |              536.60 |     nan    |                 nan    |
| 2026-09 | C_100     | net          | ignored        |              571.40 |     nan    |                 nan    |
| 2026-09 | C_100     | net          | unavailable    |              571.40 |     nan    |                 nan    |
| 2026-10 | A         | gross        | ignored        |              264.20 |     nan    |                 nan    |
| 2026-10 | A         | gross        | unavailable    |              264.20 |     nan    |                 nan    |
| 2026-10 | A         | net          | ignored        |              287.30 |     nan    |                 nan    |
| 2026-10 | A         | net          | unavailable    |              287.30 |     nan    |                 nan    |
| 2026-10 | B         | gross        | ignored        |              268.70 |     nan    |                 nan    |
| 2026-10 | B         | gross        | unavailable    |              268.70 |     nan    |                 nan    |
| 2026-10 | B         | net          | ignored        |              287.30 |     nan    |                 nan    |
| 2026-10 | B         | net          | unavailable    |              287.30 |     nan    |                 nan    |
| 2026-10 | C_020     | gross        | ignored        |              264.20 |     nan    |                 nan    |
| 2026-10 | C_020     | gross        | unavailable    |              264.20 |     nan    |                 nan    |
| 2026-10 | C_020     | net          | ignored        |              287.30 |     nan    |                 nan    |
| 2026-10 | C_020     | net          | unavailable    |              287.30 |     nan    |                 nan    |
| 2026-10 | C_050     | gross        | ignored        |              264.40 |     nan    |                 nan    |
| 2026-10 | C_050     | gross        | unavailable    |              264.40 |     nan    |                 nan    |
| 2026-10 | C_050     | net          | ignored        |              287.30 |     nan    |                 nan    |
| 2026-10 | C_050     | net          | unavailable    |              287.30 |     nan    |                 nan    |
| 2026-10 | C_100     | gross        | ignored        |              268.70 |     nan    |                 nan    |
| 2026-10 | C_100     | gross        | unavailable    |              268.70 |     nan    |                 nan    |
| 2026-10 | C_100     | net          | ignored        |              287.30 |     nan    |                 nan    |
| 2026-10 | C_100     | net          | unavailable    |              287.30 |     nan    |                 nan    |


## 8. G8 usage and fourth-unit need

G8 unit commitment in HEDNO data: per DATA_NOTES §1b, G8 showed `1` in 222 of 9,240 downloaded
hours.  In the parsed CSV used here, G8 is always 0 (possible parser coverage gap for those 222
hours; see §4 missing-week notes).  The model may commit G8 in high-load hours.  Number of model
hours requiring 4 units is reported per variant below.

| variant   | load_basis   | letter_avail   |   n_4unit_hours |
|:----------|:-------------|:---------------|----------------:|
| A         | gross        | ignored        |               0 |
| A         | gross        | unavailable    |               0 |
| A         | net          | ignored        |               0 |
| A         | net          | unavailable    |               0 |
| B         | gross        | ignored        |             637 |
| B         | gross        | unavailable    |             637 |
| B         | net          | ignored        |             589 |
| B         | net          | unavailable    |             589 |
| C_020     | gross        | ignored        |               0 |
| C_020     | gross        | unavailable    |               0 |
| C_020     | net          | ignored        |               0 |
| C_020     | net          | unavailable    |               0 |
| C_050     | gross        | ignored        |             422 |
| C_050     | gross        | unavailable    |             422 |
| C_050     | net          | ignored        |             430 |
| C_050     | net          | unavailable    |             430 |
| C_100     | gross        | ignored        |             773 |
| C_100     | gross        | unavailable    |             773 |
| C_100     | net          | ignored        |             780 |
| C_100     | net          | unavailable    |             780 |


## 9. Summer failure mode: missing no-load cost

July and August 2026 show the worst exact-match scores (15 % and 42 % for the best variant).  The
root cause is that the model lacks a no-load cost (fixed fuel burn per committed unit-hour
independent of dispatch level).  When demand is between 1.1 and 2.2 MW (2-unit range), committing 2
vs 3 units incurs identical total marginal cost (350 EUR/MWh × total_dispatch regardless of unit
count).  Once a third unit is started at an evening demand peak (> 1.83 MW with C_020 reserve), the
model keeps it on all night because startup_cost = 10 EUR is negligible.  HEDNO, by contrast, turns
off the third unit as demand falls.  Fix: add a `no_load_cost` ≈ p_min_pu × marginal_cost × p_nom ≈
116 EUR/h per committed unit.  This is not in the current Stage 0 model; it should be the primary
addition in Stage 1.

The gross-model VoLL hours (99 total, all < 0.2 MW) are a separate artifact: during morning PV ramp-
up, residual demand (demand − PV) can fall below the diesel p_min (0.33 MW).  The optimizer sheds a
small amount of load rather than commit a diesel unit whose minimum output would overshoot demand.
These hours are not infeasible energy situations but rather PV-range gaps that would be eliminated
by adding a dump-load or reducing p_min_pu.


## 10. Assumptions most affecting results

| Parameter | Value | Status | Impact |
|-----------|-------|--------|--------|
| `no_load_cost` | missing | assumption | Not modelled.  Primary driver of July/August over-commitment (3 units when 2 suffice).  Add for Stage 1. |
| `p_min_pu` | 0.30 | assumption | Controls minimum units needed at low load.  Lower → fewer units committed at night. |
| `marginal_cost` | 350 EUR/MWh | assumption | Affects start-up vs running trade-off relative to `start_up_cost`. |
| `start_up_cost` | 10 EUR | assumption | Small relative to marginal cost; min-up/down-time constraints dominate commitment. |
| `min_up_time` | 1 h | assumption | With 1-h resolution, effectively no constraint. Longer values force more unit-hours on. |
| `min_down_time` | 1 h | assumption | Same as above. |
| `load_basis` | gross or net | open (Q1) | Shifts the diesel residual load by ~0–10 % depending on PV contribution. |
| `letter_avail` | unavailable/ignored | open (Q2) | Maintenance windows constrain availability for ~1,000 G6/G7 hours. |


## 11. Open questions (DATA_NOTES §3)

- **Q1** (load_basis): `gross` outperforms `net` by ~4–5 pp overall, most clearly in full-coverage months.  This tentatively suggests `demand_mw` is total island demand (gross), but do not resolve by assumption — confirm with HEDNO.
- **Q2** (letters): `letter_avail` has zero effect on results.  Maintenance/fault cells do not constrain the cost-optimal solution, suggesting either HEDNO's maintenance schedule is already reflected in the units-on count, or the optimizer works around unavailable units without cost.  No further sensitivity needed.
- **Q4** (per-unit MW): no per-unit output in HEDNO data; dispatch model uses identical-unit assumption.
- **Q9** (cost columns): bulletin ΜΜΚ used as marginal cost proxy; confirm definition before using in techno-economics.

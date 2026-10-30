# Data

- `data.csv` – everything in one long table (one row = one value). Built from `raw/` by `scripts/build_data_csv.py`.
- `india_districts.geojson` – district polygons (geoBoundaries ADM2, 2021, LGD-based). Geometry, so kept outside the CSV.
- `raw/` – original downloads, untouched. Sources and licences: see **Data sources** in the root README.

## `data.csv` columns

| Column | Meaning |
|---|---|
| `layer` | `charger`, `charger_official`, `ev_registrations`, `ev_registrations_rto`, `demographics`, `economy`, `grid`, `roads`, `context` |
| `source` | Where the row came from |
| `level` | `point` (has lat/lon), `district`, `state`, `national` |
| `state`, `district` | Upper-case names (blank for points without them; spatial-join on lat/lon) |
| `name`, `lat`, `lon` | Point features only |
| `year` | Calendar year, `cumulative` for VAHAN till-today, or a date for national charger totals |
| `metric`, `value` | e.g. `registrations_PURE EV` / count, `station` / 1, `connectors` / n, `Population` / n |
| `detail` | Free text: status, address, voltage, operator, NH number |

EV count = `registrations_ELECTRIC(BOV)` + `registrations_PURE EV`. `registrations_TOTAL` = all fuels.

## Rebuild

```sh
uv run --no-project --with pandas --with pyarrow --with openpyxl python scripts/build_data_csv.py
```

## Git-ignored raw files

Fetch these into `data/raw/` before running the build and pipeline. Source details are in the **Data sources** section of the root README.

| File | Why it is not in git | Needed by |
|---|---|---|
| `raw/chargers/bee_evyatra_snapshot_2024-12.csv` | Holds contact names and phone numbers; no licence on the public GitHub copy | `scripts/build_data_csv.py` (contact columns are not merged) |
| `raw/vahan_rto/` (`fuel.csv`, `vehicle_class.csv`, `vehicle_category.csv`) | Large (India Data Portal, ODC-BY). Exclude RTO code `HR207`: it is an all-India total | `scripts/build_data_csv.py`, pipeline step 02 |
| `raw/roads/morth_national_highways.parquet` | Large (PM GatiShakti, June 2022) | pipeline step 04 |

Without them the build stops at those inputs.

`charger_pending` holds Zeon stations collected after the Round 1 figures were fixed. The pipeline skips this layer until it is promoted to `charger`.

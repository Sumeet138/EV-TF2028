# Data

- `data.csv` – everything in one long table (one row = one value). Built from `raw/` by `scripts/build_data_csv.py`.
- `india_districts.geojson` – district polygons (geoBoundaries ADM2, 2021, LGD-based). Geometry, so kept outside the CSV.
- `raw/` – original downloads, untouched. Sources and licences: see **Data sources** in the root README.

## `data.csv` columns

| Column | Meaning |
|---|---|
| `layer` | `charger`, `ev_registrations`, `demographics`, `economy`, `grid`, `roads` |
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

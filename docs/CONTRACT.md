# Build contract

Shared by everyone working on the build. `client/src/types.ts` defines every JSON shape; this file says who produces what.

## Flow

```
data/raw + data/data.csv + data/india_districts.geojson
  -> scripts/pipeline/01_integrate.py  -> data/processed/districts_base.csv, chargers_clean.csv
  -> scripts/pipeline/02_gap.py        -> data/processed/districts_gap.csv, states.csv
  -> scripts/pipeline/03_forecast.py   -> data/processed/districts_forecast.csv, scenarios.json
  -> scripts/pipeline/04_corridors.py  -> data/processed/corridors.json, sites.json
  -> scripts/pipeline/05_export.py     -> client/public/data/*.json
```

Run everything: `uv run --no-project --with pandas --with pyarrow --with openpyxl --with geopandas --with shapely --with scipy python scripts/pipeline/run_all.py`.

`data/processed/` is committed, small, and regenerable. Keep `client/public/data/` under 12 MB in total.

## Files in `client/public/data/`

| File | Type |
|---|---|
| `districts.geojson` | FeatureCollection, `properties.id` is `DistrictId`, simplified to under 2 MB |
| `districts.json` | `District[]` |
| `states.json` | `State[]` |
| `national.json` | `National` |
| `chargers.json` | `Chargers` |
| `substations.json` | `SubstationRow[]` |
| `corridors.json` | `Corridor[]` |
| `sites.json` | `Site[]` |
| `scenarios.json` | `Scenarios` |
| `meta.json` | `Meta` |

## Honesty rules

- Never fabricate data. If a figure is modelled or assumed, it goes in `Meta.assumptions` with its `kind`.
- Norm values must come from `data/raw/docs/mop_ev_charging_guidelines_2022_amended_2023.pdf`. Quote the clause in the assumption's `source`.
- Modelled values never appear unlabelled in the UI.
- The inventory is partial. Report coverage, do not hide it.

## App

- React 19, Vite 8, TypeScript. `maplibre-gl` for the map. `lucide-react` for icons. Charts are plain SVG in React, no chart library.
- Routes are hash based, handled in `client/src/App.tsx`: `#/map`, `#/scorecard`, `#/planner`, `#/corridors`, `#/method`. A `?d=<DistrictId>` or `?s=<State>` param carries the selection between views.
- Data loads through `useData()` in `client/src/lib/data.tsx`. Views never fetch directly.
- All formatting goes through `client/src/lib/format.ts`.
- Styling is plain CSS with the tokens in `client/src/styles/tokens.css`. Each view owns one CSS file beside it. See `DESIGN.md`.

## Ground rules

- Stay inside your owned paths. Need something elsewhere? Note it in your final report.
- Do not run `git commit`, `git push`, or anything that changes history.
- Do not add dependencies. If one is truly needed, say why in your final report.
- Shared working tree: other agents are writing at the same time. Do not run formatters across the repo.

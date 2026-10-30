# EV TF2028

React 19 + Vite 8 (client) and Express 5 (server), TypeScript, npm workspaces.

## Setup
```sh
npm install
cp .env.example .env
npm run dev   # client :5173, server :5000 (Vite proxies /api)
```

## Scripts
- `npm run dev` – run both with hot reload
- `npm run build` – build client then server
- `npm start` – run built server (`NODE_ENV=production` serves `client/dist`)
- `npm run typecheck`

## Layout
```
client/   React + Vite
server/   Express API (src/index.ts)
```

## Data sources

Everything lives in `data/` (`data.csv` = unified table, 1,07,620 rows; `raw/` = original files; see `data/README.md`). Pulled 2026-10-29 and 2026-10-30. No synthetic data.

### Used

| Layer | Source | What we got | Licence |
|---|---|---|---|
| EV population | VAHAN4 dashboard (MoRTH), Y=State × X=Fuel, Excel export | Registrations by state × fuel, each year 2014–2026 + cumulative | Govt open data |
| EV population | India Data Portal, VAHAN by RTO (`raw/vahan_rto/`) | 1,377 RTOs, 2022–2026 (HR207 is an all-India dealer total and is excluded) | ODC-BY |
| Chargers | Tata Power EZ Charge public map | 2,572 stations with lat/lon, state, status, connectors | Scraped from public map |
| Chargers | Statiq public map | 8,164 stations | Scraped from public map |
| Chargers | BEE EV Yatra snapshot, Dec 2024 (public GitHub copy) | 25,202 stations. May include closed stations | Unclear: no licence on the copy |
| Chargers | Open Charge Map | 1,872 stations | CC BY 4.0 (contributor data) |
| Chargers | OpenStreetMap via Overpass (`amenity=charging_station`) | 611 stations | ODbL |
| Chargers | Ola, ChargeMOD (partial), Relux locators | 141 / 194 / 68 stations | Scraped from public sites |
| Chargers (official) | Lok Sabha Q.453 (21 Jul 2026, BHEL portal); Rajya Sabha Q3929; Parliament replies and PIB | National total 52,718; state counts (268 rows) | GODL-India / Govt document |
| Boundaries | geoBoundaries gbOpen IND ADM2 (LGD-based, 2021) | District polygons | ODbL |
| Roads | MoRTH via PM GatiShakti, National Highways (`raw/roads/`, June 2022) | 10,317 segments with node IDs | Govt open data |
| Roads | MoRTH via PM GatiShakti, toll plazas | 677 toll plazas with NH number | CC0 |
| Demographics | Census 2011 district table | 640 districts: population, households, vehicle ownership, income bands | Govt open data |
| Demographics | india-geodata `census/historical` | District splits/renames 1951–2024 | Open |
| Economic activity | VIIRS night lights by district 2024 | Radiance sum/mean per district | Open |
| Grid | OpenStreetMap (`power=substation`) | 16,960 substations | ODbL |
| Context layers | OSM fuel stations, industrial areas, tourism sites; airports; power plants (`raw/context/`) | 18,527 / 5,706 / 2,394 / 2,710 / 534 rows. Only fuel stations feed a result (corridor sites) | ODbL / open |
| Norms | Ministry of Power guidelines for public charging infrastructure, 2022, amended 2023 | 3 km grid / 25 km highway spacing. A 2024 update may be stricter (secondary source, unread) | Govt document |

### Git-ignored raw files

Three raw inputs are not in git, so the first pipeline steps (`scripts/build_data_csv.py`, then 01 and 04) need them fetched into `data/raw/`:

- `data/raw/chargers/bee_evyatra_snapshot_2024-12.csv`: holds contact names and phone numbers, and its reuse rights are unclear. Do not publish it.
- `data/raw/vahan_rto/`: large RTO tables (India Data Portal).
- `data/raw/roads/morth_national_highways.parquet`: large (PM GatiShakti, indiadataportal.com).

### Dug into, not used

| Source | Finding |
|---|---|
| Live BEE EV Yatra site | Hangs; the Dec 2024 snapshot is used instead |
| Dataful.in | Full MoP charger list (39,641 rows) and RTO-level data, but paid (₹299–₹499 per dataset) |
| Vahan Public Report (analytics.parivahan.gov.in) | RTO-level data behind a CAPTCHA per query; replaced by the India Data Portal file |
| data.gov.in state-wise PCS tables | Full download behind a form + CAPTCHA; only first 10 rows kept in `raw/` |
| OSM bus and rail stations | Overpass servers at capacity |
| Other operators (ChargeZone, Jio-bp pulse, Ather Grid, Bolt.Earth, Kazam) and most state portals | No public web map API, or not tried (the operator sweep stopped early) |
| PM GatiShakti MMLP lines and polygons | In `raw/roads/`, not used |
| RTO `vehicle_class.csv`, `vehicle_category.csv` | No fuel column, not used |
| Geofabrik India OSM extract | 1.7 GB, skipped; targeted Overpass queries used instead |

## Run it

```sh
# pipeline: raw data -> data/processed -> client/public/data
uv run --no-project --with pandas --with pyarrow --with openpyxl --with geopandas --with shapely --with scipy python scripts/pipeline/run_all.py
# app
npm install && npm run dev   # client :5173, server :5000
```

## Project status

- Done: data collection (five charger sources plus official counts, RTO-level VAHAN, National Highway geometry), integration (31,259 deduplicated stations on 735 districts, 59.3% of the official 52,718), EV allocation (RTO-based for 611 districts, proxy for 124), per-state coverage, gap score, forecast with a low to high sensitivity range, corridors on real geometry, sites, web app and read-only API.
- Round 1 submission: `docs/round1-submission.pdf` (source `docs/round1-submission.md`); demo: `docs/demo-script.md`.
- Limits: district EVs are modelled (the RTO to district match is by name, 78.7% of RTO EVs); BEE data is from Dec 2024 and may include closed stations; corridor geometry is from June 2022 with holes; the forecast depends on assumed utilisation and public charging share, so it is shown as a range.
- Still open: operator feeds, the live EV Yatra or licensed Dataful list, RTO crosswalk validation, licences for BEE and scraped sources.

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

Everything lives in `data/` (`data.csv` = unified table, `raw/` = original files; see `data/README.md`). Pulled 2026-10-29. No synthetic data.

### Used

| Layer | Source | What we got | Licence |
|---|---|---|---|
| EV population | VAHAN4 dashboard (MoRTH), vahan.parivahan.gov.in/vahan4dashboard, Y=State × X=Fuel, Excel export | Registrations by state × fuel, each year 2014–2026 + cumulative | Govt open data |
| Chargers | Tata Power EZ Charge public map (ezcharge.tatapower.com/evselfcare, guest station endpoint) | 2,572 stations with lat/lon, city, state, status, connectors | Scraped from public map |
| Chargers | Statiq public map (statiq.in/ev-charging-station, `station/v1/markers`) | 8,164 stations with lat/lon, address | Scraped from public map |
| Chargers | OpenStreetMap via Overpass (`amenity=charging_station`) | 611 stations | ODbL |
| Chargers (benchmark) | data.gov.in, Rajya Sabha Q3929 (Apr 2025) | National PCS totals 2022–2025 (26,367 as of Apr 2025) | GODL-India |
| Boundaries | geoBoundaries gbOpen IND ADM2 (LGD-based, 2021) | District polygons | ODbL |
| Roads | MoRTH via PM GatiShakti, mirrored by github.com/yashveeeeeeer/india-geodata | 677 NH toll plazas with NH number | CC0 |
| Demographics | Census 2011 district table, github.com/nishusharma1608/India-Census-2011-Analysis | 640 districts: population, households, vehicle ownership, income bands | Govt open data |
| Demographics | india-geodata `census/historical` | District splits/renames 1951–2024 (2011 → current districts) | — |
| Economic activity | VIIRS night lights by district 2024, india-geodata | Radiance sum/mean per district | — |
| Grid | OpenStreetMap via Overpass (`power=substation`) | 16,960 substations, voltage where tagged | ODbL |
| Norms | Ministry of Power, EV charging guidelines + amendments (powermin.gov.in) | 3 km grid / 25 km highway spacing, tariff caps | Govt document |

### Dug into, not used (yet)

| Source | Finding |
|---|---|
| BEE EV Yatra (official national charger list) | Site down / unreachable all day |
| Dataful.in | Has the full MoP charger list (39,641 rows, lat/lon, LGD codes) and RTO-level EV data, but paid (₹299–₹499 per dataset, plans from ₹5,000/mo) |
| Vahan Public Report (analytics.parivahan.gov.in) | Has RTO-level EV + Active-status filters, but every query needs a CAPTCHA (~36 queries for India) |
| data.gov.in state-wise PCS tables | Full download behind name/mobile/email + CAPTCHA form; only first 10 rows kept in `raw/` |
| OpenChargeMap API | Needs a free account (email/password, no Google sign-in) |
| ChargeZone, Jio-bp pulse, Ather Grid, Zeon, Bolt.Earth, Kazam | No public web map API; station lists live inside their mobile apps |
| Kaggle / GitHub | Only small OCM-derived sets (~500 stations), no scraped EV Yatra data |
| NH polylines (GatiShakti, 40 MB) | Available (CC0), skipped to keep repo small; pull when building the map |
| Geofabrik India OSM extract | 1.7 GB, skipped; targeted Overpass queries used instead |

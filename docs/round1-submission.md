# EV Infra Map India

**Techfest 2026-27, Round 1 submission. Challenge 1: Mapping and Integration of Nationwide EV Charger Installations Based on Vehicle Population Using VAHAN Data**

Contents: 1 Team information. 2 Problem and approach. 3 Methodology. 4 Data sources, licences and limits. 5 Tools and technologies. 6 Implementation roadmap. 7 Early results.

## 1. Team information

| Field | Entry |
|---|---|
| Team name | `[TEAM NAME]` |
| Challenge | Challenge 1, EV Infra Map India |
| Member 1 (lead) | `[MEMBER 1 NAME, COLLEGE, DEGREE, EMAIL]` |
| Member 2 | `[MEMBER 2 NAME, COLLEGE, DEGREE, EMAIL]` |
| Member 3 (if any) | `[MEMBER 3 NAME, COLLEGE, DEGREE, EMAIL]` |
| Member 4 (if any) | `[MEMBER 4 NAME, COLLEGE, DEGREE, EMAIL]` |
| Member 5 (if any) | `[MEMBER 5 NAME, COLLEGE, DEGREE, EMAIL]` |
| Primary contact | `[CONTACT NAME, PHONE, EMAIL]` |
| Repository | https://github.com/Sumeet138/EV-TF2028 |

## 2. Problem and approach in brief

Public EV chargers in India are listed in many places: operator apps, government lists, open maps. No single view joins them to the number of EVs on the road, so it is hard to say where charging lags adoption and how many chargers each region needs next. The problem statement asks for an integrated map, a VAHAN-based assessment of EV population against charging availability, gap identification, a future requirement estimate, and a decision-support dashboard for MHI, ICAT and state governments.

Our approach has five parts.

1. **Integrate.** Pull every public charger list we can reach (five sources), remove duplicates, and place each station in one of 735 district polygons (geoBoundaries ADM2, 2021, LGD based). Attach Census 2011 population and households, VIIRS night lights, grid substations and highway toll plazas to the same polygons.
2. **Allocate EVs.** The VAHAN dashboard gives EV registrations per state only. We allocate each state's count to its districts using RTO-level registrations where an RTO matches a district, and a stated proxy elsewhere. The result is labelled modelled everywhere it appears.
3. **Score gaps.** Compare EVs with chargers per district, correct for the share of chargers our inventory cannot see (per state, from official state counts), and combine this with distance-based coverage into a 0-100 gap score and five bands.
4. **Forecast and size.** Project EVs to 2027, 2030 and 2035 in three scenarios, convert them to charger counts by type (AC, DC 30, 60, 120 kW), and compare with what exists.
5. **Site and plan.** Rank candidate sites near demand and substations, and measure highway corridors, drawn on real National Highway geometry, against the 25 km spacing norm.

The product is a web platform with five views: national map, state and district scorecard, a planner for charger requirements and sites, a corridor view, and a method page that lists every assumption. Two rules run through the whole design. A modelled number is never shown without a label, and the charger inventory is partial, so a gap is a prompt to check, never proof that no charger exists.

## 3. Methodology

All steps are scripts in `scripts/pipeline/` and run in order from raw files to the JSON the web app reads (`docs/CONTRACT.md`). Parameter values live in one assumptions table, exported as `meta.json` and shown on the method page. Each assumption carries a kind: measured, norm, modelled or assumed.

### 3.1 Data integration

**Charger deduplication.** Tata Power EZ Charge, Statiq, the BEE EV Yatra snapshot (December 2024), Open Charge Map and OpenStreetMap list overlapping stations. The BEE file alone holds 25,202 rows and has many near-duplicates. After dropping points outside India's bounding box or more than 2 km outside every district polygon, two listings are the same site when

- their distance d is at most 30 m, or
- d is at most 100 m and their names are compatible: the token sets (after removing words such as "charging", "station", "EV") are nested, or the similarity ratio of the sorted tokens is at least 0.6.

Pairs within 100 m are found with a k-d tree on local metric coordinates. Matching pairs form a graph and each connected component is one station. The record kept is the first by source priority: Tata Power, Statiq, BEE, Open Charge Map, OpenStreetMap. That record supplies the name and coordinates. Connector counts are only available from Tata Power and are kept as such. The pipeline labels any source it does not recognise as OSM, so the 403 listings from the Ola, ChargeMOD (partial) and Relux locators are counted under that label.

**Spatial join.** Each station is assigned to the district polygon that contains it, with a 2 km snap for coastal and simplified boundaries. Substations and toll plazas are counted per polygon the same way.

**Census crosswalk.** Census 2011 districts do not match the 2021 polygons, because many districts have since been renamed or split. Matching runs in this order: exact name, rename chain, split descendants, then fuzzy name match (similarity at least 0.8) inside the same state. A parent district's population, households, vehicle ownership and night lights are shared among its surviving descendant polygons in proportion to area:

`pop_polygon = pop_parent × area_polygon / Σ area_descendants`

This assumes people are spread evenly over the parent, which is crude, so apportioned rows are flagged (`match_quality = apportioned`) and carry lower confidence downstream. Telangana and Ladakh were not states in 2011 and are separated from Andhra Pradesh and Jammu and Kashmir by district name.

### 3.2 EV allocation (modelled)

The India Data Portal publishes VAHAN registrations for 1,377 RTOs, 2022 to 2026 (HR207, an all-India dealer total filed under one RTO code, is excluded and the pipeline asserts this). Each RTO is matched to a 2021 district by normalised name inside its state: exact, then containment, then fuzzy match with similarity at least 0.8. No official RTO-to-district list was used. 697 of 1,377 RTOs (50.6%) match a district, and they carry 78.7% of RTO EV registrations. The result is written to `data/processed/rto_district_crosswalk.csv`.

For state s with measured VAHAN EV stock E_s (battery electric plus pure EV, cumulative), let m_s be the share of the state's RTO EVs that matched a district, r_d the district's share of the matched RTO EVs, and w_d the proxy weight below. District d receives

`E_d = E_s × ( m_s·r_d + (1 − m_s)·w_d )`, with `w_d = 0.4·H_d + 0.3·P_d + 0.3·N_d`

H_d is the district's share of its state's two-wheeler plus car households, P_d its share of power-parity households (Census) and N_d its share of the state's VIIRS 2024 night lights. A district with no matched RTO takes the proxy alone (`evsSource = proxy`): 124 districts, holding 3.8% of EVs. The other 611 districts are `rto`. Shares sum to one inside each state, so district values add up to the VAHAN state total exactly (largest-remainder rounding). The proxy weights 0.4, 0.3 and 0.3 are our assumption, not a fitted result.

Three caveats stay on screen. An RTO boundary is not a district boundary: an RTO can cover part of a district or several, and metro RTOs are named for zones. Where several RTOs match one district their EVs add, and a district with an unmatched sibling RTO is under-counted. A vehicle is counted where it is registered, often a dealer's or fleet owner's city, not where it charges. The RTO series starts in 2022, so shares reflect recent registrations, not the older stock. District EV counts therefore remain modelled and carry that label.

**Reconciliation with Parliament.** Lok Sabha gives 1,00,23,396 registered EVs (26 July 2026). Our cumulative stock is 1.08 crore (10,835,574) and is later in time. Our end-2025 stock (79.4 lakh) plus January to July 2026 RTO registrations (18.8 lakh) gives about 98.2 lakh at 31 July, and the dashboard total runs to about October 2026. That leaves a residual of 2 to 3% that we cannot explain: the official figure may count other categories or a different date. We did not adjust VAHAN. The forecast starts from end-2025, so it is not affected.

### 3.3 Coverage adjustment

The inventory holds 31,259 stations after deduplication. The official national count is 52,718 (Lok Sabha Q.453, 21 July 2026, BHEL portal), so national coverage is 31,259 / 52,718 = 59.3%. The earlier national count of 26,367 (Rajya Sabha Q3929, April 2025) is kept only as a time series. The jump to 52,718 is partly a change of source and counting system (the Dec 2025 figure was 29,151), not only construction. The BEE snapshot is from December 2024 and may include stations that have since closed, so coverage may be overstated.

Coverage is now per state. For each state

`k_s = min(1, found_s / official_s)`, floored at 0.1, and adjusted chargers are `C*_d = C_d / k_s`

Official state counts come from the 29 July 2026 annexure for the 16 states where the press confirms it (41,238 stations), and from the December 2025 state totals scaled by 1.920 for the other 20 so the states sum to 52,718. The BHEL and BEE universes differ, so this is a rough scaling and is flagged `assumed`. The factor ranges from 0.10 (Ladakh) to 0.72 (Uttarakhand), median 0.52. The adjusted count is shown beside the raw count and never replaces it.

### 3.4 Gap score

For each district three indicators are computed.

- **Load:** `L_d = E_d / C*_d`, EVs per adjusted charger. A district with no listed charger takes the worst rank.
- **Reach:** the mean distance from about 300 area-uniform sample points inside the district to the nearest listed charger anywhere in India (`coverageKm`), in an equal-area projection. The share of points within 3 km, the urban spacing norm, is also stored (`within3kmShare`).
- **Unmet demand:** `U_d = E_d × (1 − within3kmShare_d)`, the modelled EVs outside the 3 km norm.

Each indicator is converted to its percentile rank across districts, and

`Gap_d = 100 × (0.4·pct(L_d) + 0.3·pct(coverageKm_d) + 0.3·pct(U_d))`

Bands 1 (well served) to 5 (critical) are quintiles of Gap_d, so the score is a relative ranking and not an absolute shortfall. The interface says so. Each district lists up to three plain-language drivers, for example "755 modelled EVs per estimated charger" or "on average 15.4 km to the nearest charger". Confidence is high for an exact census match with at least three listed chargers, or for a polygon matched exactly with at least three chargers and an RTO-sourced EV count in a state where at least 80% of RTO EVs matched; low where no census row matched, and medium otherwise. Sample points are uniform over area, not over population, so large rural districts score worse on reach than their residents may experience.

### 3.5 Forecast

National EV stock is fitted with a logistic curve on log stock, 2014 to 2025 (2026 is a part year and is excluded):

`S(t) = K / (1 + exp(−r·(t − t0)))`, with r and t0 by least squares (base: r = 0.39, t0 = 2031.5), then scaled so S(2025) equals the measured stock of 7,939,817.

The saturation stock K cannot be identified from data before the inflection point, so three values are used as scenarios: 50 million (low), 100 million (base) and 200 million (high). These are assumptions, not forecasts of policy. National stock is shared to states by their 2025 share, adjusted by the ratio of their 2025 registration share to their stock share (clipped to 0.5 to 2, faded in over five years), then to districts, which drift half way toward their state population share by 2035. Outputs are given for 2027, 2030 and 2035.

### 3.6 Charger requirement estimation

For a district with E EVs and urban household share u, daily public energy is

`D = E × p × Σ_v ( m_v × km_v × kWh_v / 100 )`

with v over 2W, 3W and 4W. Defaults: fleet mix m = 60 / 30 / 10%, km per day 30 / 80 / 40, kWh per 100 km 3.5 / 8 / 15, public share p = 15%. The VAHAN extract has no class split, so the mix is an assumption. The public share of 15% is the midpoint of 10 to 20%: home charging supplies 80 to 90% of EV energy (Kazam and AEEE, 80,000 home installs), and about 45% of buyers lack home charging, so we go no lower. Chargers of each type k (AC 7.4 kW, DC 30, DC 60, DC 120) then follow from

`N_k = D × s_k / (P_k × 16 h × η_t)`

where s_k is the energy share of type k, a blend of the urban mix (35 / 35 / 20 / 10%) and the rural mix (45 / 40 / 12 / 3%) weighted by u. The utilisation η_t is a ramp, not a constant. Utilisation today in India is about 1 to 5% on a 24-hour basis (secondary sources: SBI, S&P, FICCI, relayed by trade press; we have not read the originals). We start at 4.5% on 16 hours in 2025 (about 3% on 24 hours) and rise linearly to 15% in 2035: 6.6% in 2027, 9.8% in 2030. 15% is a mature-network target, not a measured value, and the linear path is our assumption.

A spacing floor is applied for built-up area: one charger per 2.6 × 3² km², where built-up area is urban population divided by 5,000 per km². If the demand-based count is below the floor, the shortfall is added as AC and DC 30 chargers. Chargers to add are the requirement minus existing stations × 2.1 connectors per station (the mean of the Tata Power listings that report connectors). The same formula runs in the browser (`client/src/lib/estimator.ts`), so a planner can change any default and see the new result at once.

**Sensitivity range.** Every headline requirement is shown with a low to high range. Low uses public share 10% and a 2035 utilisation of 21%; high uses public share 20% and a 2035 utilisation of 7.5%. The EV path is the base path in both, and the ramp is applied to each. Utilisation bounds come from ChargeZone (14%, restated to 16 hours) and today's ceiling of 5% on 24 hours held flat. The range is computed by re-running every district. EV scenarios (K) are separate and are not mixed into it.

### 3.7 Highway corridors

Corridors use measured road geometry: the MoRTH layer on PM GatiShakti, dated June 2022, with 10,317 National Highway segments. Segments under construction or proposed are excluded. For each of 18 highways (the longest NH numbers plus major trunk routes), the segments of that NH number are sampled every 2 km. The samples are joined by a minimum spanning tree, allowing gaps up to 150 km to be bridged by straight lines, and the corridor is the tree's longest path. This "spine" method keeps a single line per highway through branches and parallel carriageways. For each corridor:

- stations within 5 km of the path are counted;
- the longest stretch between consecutive stations is the maximum gap;
- stations to add are `Σ over gaps longer than 25 km of ( ⌈gap / 25⌉ − 1 )`, using the MoP highway spacing norm.

Lengths are measured on the full path and checked against published figures. NH 44 measures 3,522 km (published about 3,700 to 4,100), NH 48 measures 2,669 km (about 2,800) and NH 27 measures 3,374 km (about 3,500). They are lower bounds, because the file has holes and stretches built since 2022 are absent.

**Norms.** The 3 km urban grid and 25 km highway spacing come from the Ministry of Power guidelines for public charging infrastructure of 2022, as amended in 2023. They are not 2025 guidelines. A 2024 update may be stricter (a secondary source suggests 1 km); we have not read it and flag this as open.

### 3.8 Site recommendation

Within the 60 districts with the worst gap score, candidate sites are the OpenStreetMap substation locations and toll plazas inside the district; substation proximity stands in for spare grid capacity, which we do not have. Modelled EVs are spread over up to 300 random demand points drawn around the district centroid; points within 1.5 km (half of the 3 km norm) of a listed charger are counted as served. Up to four sites per district are then chosen greedily: take the candidate that covers the most unserved demand, mark that demand served, and repeat. Urban sites are DC 30 when they cover at least 150 EVs, otherwise AC. Corridor sites use the midpoints of the three longest gaps on each corridor, moved to an OSM fuel station within 300 m of the road when one lies within 2 km of the midpoint, as DC 60, or DC 120 where the gap exceeds three times the norm. Each site shows its type, connectors, nearest substation and a one-line reason. Because substation data carries no capacity, every site needs a utility feasibility check.

### 3.9 Validation

Checks are reported with pass or fail on the method page. The first five are built into the pipeline (ten checks in `assumptions_gap.json`, all passing at export); the last three are planned for the finale.

| Check | Rule |
|---|---|
| Districts | one row per polygon; ids unique; 36 states and UTs present |
| Population | district total within 5% of the Census 2011 total |
| Chargers | district sums equal the number of clean stations |
| EV allocation | district values sum to the VAHAN state total for every state |
| Coverage | the 59.3% national inventory coverage and the per-state factor are displayed on the main screens |
| Spot check | for sample districts, station counts are compared against the operator maps |
| Sensitivity | gap bands are recomputed for ±20% on each weight and the share of districts that change band is reported |
| Backtest | the forecast method is fitted on 2014 to 2023 and compared with the 2024 and 2025 VAHAN values |

## 4. Data sources, licences and known limits

Files were pulled on 29 and 30 October 2026. No synthetic data is used. Raw files are kept unchanged in `data/raw/` and rebuilt into one long table, `data/data.csv` (1,07,620 rows).

| Layer | Source | Content | Licence |
|---|---|---|---|
| EV population | VAHAN4 dashboard, MoRTH | Registrations by state and fuel, 2014 to 2026 and cumulative | Government open data |
| EV population | India Data Portal, VAHAN by RTO | 1,377 RTOs, 2022 to 2026 (10,174 rows of EV registrations) | ODC-BY |
| Chargers | Tata Power EZ Charge public map | 2,572 stations with coordinates, status, connectors | Scraped from a public map |
| Chargers | Statiq public map | 8,164 stations | Scraped from a public map |
| Chargers | BEE EV Yatra snapshot, December 2024 | 25,202 stations | Unclear: public GitHub copy, no licence |
| Chargers | Open Charge Map | 1,872 stations | CC BY 4.0 (contributor data) |
| Chargers | OpenStreetMap, `amenity=charging_station` | 611 stations | ODbL |
| Chargers | Ola, ChargeMOD (partial: first 25 per city page), Relux locators | 141 / 194 / 68 stations | Scraped from public sites |
| Benchmark | Lok Sabha Q.453 (21 July 2026), Rajya Sabha Q3929 via data.gov.in | Official national total 52,718; series 2022 to 2026 | GODL-India |
| Benchmark | Parliament replies and PIB | 268 rows of state charger counts | Government document |
| Boundaries | geoBoundaries gbOpen, India ADM2 (2021) | District polygons | ODbL |
| Roads | MoRTH via PM GatiShakti, National Highways (June 2022) | 10,317 segments with node IDs | Government open data |
| Roads | MoRTH via PM GatiShakti, toll plazas | 677 toll plazas with NH number | CC0 |
| Demographics | Census 2011 district table | Population, households, vehicle ownership, income bands for 640 districts | Government open data |
| Demographics | District history 1951 to 2024 | Renames and splits for the crosswalk | Open |
| Economy | VIIRS night lights by district, 2024 | Radiance per district | Open |
| Grid | OpenStreetMap, `power=substation` | 16,960 substations | ODbL |
| Context | OSM fuel stations, industrial areas, tourism sites; airports; power plants | 18,527 / 5,706 / 2,394 / 2,710 / 534 rows | ODbL and open |
| Norms | Ministry of Power guidelines for public charging infrastructure, 2022, amended 2023 | 3 km urban and 25 km highway spacing | Government document |

Only the OSM fuel stations among the context layers feed a result (corridor site placement). The others are in `data.csv` for later use. Three raw inputs are git-ignored: the BEE file (it carries contact names and phone numbers that must not be published, and its reuse rights are unclear), `data/raw/vahan_rto/` and the National Highway parquet (both large). A fresh clone must fetch them before the first pipeline steps run (`data/README.md`).

### Known limits

1. **District EVs are modelled.** RTO registrations replace the pure proxy for 611 districts, but the RTO to district match is by name only and covers 78.7% of RTO EVs. 124 districts rest on the proxy. RTO boundaries and registration addresses differ from districts and charging places (section 3.2).
2. **The inventory is partial and uneven.** 31,259 stations after deduplication against 52,718 official (59.3%). BEE is from December 2024 and may include closed stations; BHEL and BEE universes differ, so the per-state coverage factor is a rough scaling. Charger counts are neither exact nor a lower bound where closed stations remain.
3. **Connector counts are incomplete.** Only Tata Power listings give them (2,474 stations touched by a Tata listing). Station counts, not connector counts, drive the scores.
4. **Corridors cover part of the road.** The geometry is from June 2022 and has holes, so lengths are lower bounds (section 3.7). Corridor charger counts within 5 km include urban stations along the route.
5. **Census 2011 is old.** Population is apportioned for 174 polygons created after 2011 (match quality `apportioned`). Three polygons have no census match.
6. **Substation data** shows location and voltage where tagged, not spare capacity.
7. **Utilisation is a target.** The 15% figure for 2035 is not observed in India. The forecast range (section 7.5) is the honest way to read it.
8. **Licences.** The public GitHub copy of the BEE data has no licence. Tata Power, Statiq and the operator locators are scraped and carry terms we have not negotiated; for production they need agreed feeds. OSM is ODbL, Open Charge Map is CC BY 4.0 for contributor data, the India Data Portal is ODC-BY.

### Sources we tried and could not use

| Source | Outcome |
|---|---|
| Live BEE EV Yatra site | Hangs; the December 2024 snapshot is used instead |
| Dataful.in | Holds the full MoP list (39,641 rows) and RTO-level data, paid per dataset |
| VAHAN public report, RTO level | CAPTCHA on every query; replaced by the India Data Portal RTO file |
| data.gov.in state-wise charger tables | Full download behind a form and CAPTCHA; only 10 rows retained |
| OSM bus and rail stations | Overpass servers at capacity |
| Other operators (ChargeZone, Jio-bp, Ather, Bolt.Earth, Kazam) and most state portals | Not tried or no public map API; the operator sweep was stopped early by choice |
| A station list covering all 52,718 | None found; even everything merged leaves a gap |

## 5. Tools and technologies

| Area | Choice | Use |
|---|---|---|
| Data pipeline | Python 3, pandas, pyarrow, openpyxl | Reading VAHAN Excel, building the unified table, tabular transforms |
| Geospatial | geopandas, shapely, scipy (k-d tree, sparse graph) | Spatial joins, equal-area projection (EPSG:6933), deduplication clusters, distance queries |
| Environment | uv | Reproducible one-command pipeline run |
| Web client | React 19, TypeScript, Vite 8 | Five-view application, hash routes, typed data contract |
| Mapping | MapLibre GL JS | Vector map, district choropleth, charger and corridor layers |
| Charts | Plain SVG in React | No chart library, so values stay readable as text and tables |
| Icons | lucide-react | Interface icons |
| Server | Node.js, Express 5 | Static hosting of the build and a place for future APIs |
| Delivery | npm workspaces, static JSON under 12 MB | Runs offline after load; hosting is a static folder |

The client reads ten JSON files (`districts`, `states`, `national`, `chargers`, `substations`, `corridors`, `sites`, `scenarios`, `meta`, plus simplified district geometry). Their shapes are defined in `client/src/types.ts`, so the pipeline and the interface cannot drift apart without a type error. Accessibility targets WCAG AA, with keyboard use of every control and no meaning carried by colour alone.

## 6. Step-by-step implementation roadmap

| Stage | Period | Work | Deliverable |
|---|---|---|---|
| 0. Data collection | Done | Collect VAHAN (state and RTO), five charger sources, official counts, boundaries, census, National Highway geometry, grid; record blocked sources | `data/raw/`, `data/data.csv`, source table (section 4) |
| 1. Integration | Done | Deduplicate chargers, join to districts, census crosswalk, RTO to district crosswalk | `data/processed/chargers_clean.csv`, `districts_base.csv`, `rto_district_crosswalk.csv` |
| 2. Analytics | Done for Round 1 | EV allocation, per-state coverage, gap score, forecast with sensitivity range, charger requirement, corridors from true geometry, sites; validation checks | `districts_gap`, `states`, `districts_forecast`, `corridors`, `sites`, `meta.json` |
| 3. Platform | Round 1 | Map, scorecard, planner, corridors and method views on exported JSON | Running prototype from `npm run dev` |
| 4. Demo | Round 1 | Three-minute walkthrough for Maharashtra, Pune against Amravati | `docs/demo-script.md` and a screen recording |
| 5. Finale build | To 16 to 18 December | Validate the RTO to district crosswalk against an official list; spot-check station counts on the ground in sample districts; backtest and sensitivity pages; apply review feedback; rehearse | Hardened prototype, final presentation and video |
| 6. National scale | After finale | Operator feeds on agreed terms; the live EV Yatra list or the Dataful list under licence; refresh Census-based inputs; resolve licences for BEE and scraped sources | A data refresh that runs unattended |
| 7. Operations | After finale | Scheduled refresh; vector tiles for the map; user accounts and saved scenarios for state teams | Hosted planning platform for MHI, ICAT and state departments |

Done in Round 1 and no longer future work: RTO-level VAHAN, true National Highway geometry, and a fuller charger inventory (five sources, 59.3% of the official count). Remaining, in the order we would take them:

1. **Operator feeds and the live official list.** Replace scraped and snapshot inputs with agreed feeds, and the live EV Yatra or licensed Dataful list. This closes the remaining 41% gap and the closed-station risk in BEE.
2. **RTO crosswalk validation.** Replace name matching with an official RTO to district list, to raise the 78.7% matched share and remove the 124 proxy districts.
3. **Licences.** Settle reuse rights for BEE and the scraped operators before any public release.
4. **Live charger status.** Add availability and uptime from operators or open standards such as OCPI.
5. **Vector tiles.** Serve the map from tiles rather than one JSON file.
6. **WASM siting optimiser.** Compile the greedy siting step, later a facility-location solver, to WebAssembly so a planner can change budget and norms in the browser.
7. **Grid capacity.** Replace substation locations with feeder headroom from distribution utilities where they will share it.

## 7. Early results

All numbers in this section are computed from `data/processed/`, `data/data.csv` and the exported JSON in `client/public/data/`. Entries marked *modelled* come from the allocation and forecast steps. Entries marked *measured* are counted from the sources.

### 7.1 Integration (measured)

| Quantity | Value |
|---|---|
| Raw station listings, six charger files | 38,824 |
| Listings after range and boundary filter | 38,812 |
| Stations after deduplication | 31,259 |
| Listings merged into an existing station | 38,812 less 31,259 |
| Stations with more than one listing / more than one source | 4,882 / 2,760 |
| Stations by source, alone: BEE / Statiq / Tata Power / Open Charge Map / OSM | 19,416 / 6,059 / 1,509 / 993 / 522 |
| Stations touched by each source: BEE / Statiq / Tata Power / Open Charge Map / OSM | 21,684 / 7,504 / 2,474 / 1,744 / 901 |
| District polygons | 735 in 36 states and UTs |
| Polygons with no charger found | 39 |
| Population carried onto the polygons | 1.21 billion (Census 2011 basis) |
| Substations joined / toll plazas joined | 16,959 / 677 |
| Polygons by census match: exact / apportioned / crosswalk / none | 555 / 174 / 3 / 3 |
| RTOs matched to a district / share of RTO EVs matched | 697 of 1,377 / 78.7% |

Coverage against the official count: 31,259 of 52,718, 59.3% nationally, 0.10 to 0.72 by state (median 0.52). The official count of 26,367 in April 2025 has been superseded, and part of the rise to 52,718 is a change of counting system. BEE may include closed stations, so coverage may be overstated.

### 7.2 EV population (measured, VAHAN)

| Quantity | Value |
|---|---|
| EVs registered, cumulative at the pull date (battery electric plus pure EV) | 10,835,574 |
| EVs at end-2025, base of the forecast | 7,939,817 |
| All vehicles registered, cumulative | 454,730,393 |
| EV registrations in 2023 / 2024 / 2025 | 1,582,843 / 2,026,411 / 2,356,971 |
| EV share of registrations in 2023 / 2024 / 2025 | 6.3% / 7.4% / 8.0% |
| Official EVs, Lok Sabha, 26 July 2026 | 1,00,23,396 (see reconciliation, section 3.2) |

States with most EVs: Uttar Pradesh 1,880,019; Maharashtra 1,218,821; Karnataka 951,620; Tamil Nadu 741,893; Rajasthan 596,886; Bihar 579,305.

States with most listed chargers: Maharashtra 4,887; Karnataka 4,783; Uttar Pradesh 2,727; Tamil Nadu 2,084; Kerala 1,906; Rajasthan 1,724.

Uttar Pradesh has about 1.5 times the EVs of Maharashtra and about 0.56 times its listed chargers. Bihar is sixth by EVs and has 446 listed chargers, about 16th by charger count. These raw patterns are what the gap score ranks, with the caveat that part of the difference is inventory coverage.

### 7.3 Gap results (modelled)

All values here depend on the district EV allocation and the per-state coverage factor, so they are modelled rankings, not measurements.

| Quantity | Value |
|---|---|
| Districts per gap band, 1 to 5 | 147 / 146 / 146 / 146 / 147 (quintiles by design) |
| Confidence high / medium / low | 509 / 223 / 3 districts |
| EV source: RTO-based / proxy | 611 districts, 96.2% of EVs / 124 districts, 3.8% |
| Districts with no listed charger | 39, holding 11,527 of 10,835,574 modelled EVs (0.1%) |
| Median modelled EVs per adjusted charger | 174 |
| Highest district gap scores | Amravati (Maharashtra) 89.4; Cachar (Assam) 87.7; Mayurbhanj (Odisha) 86.1; Kokrajhar (Assam) 85.4; Bahraich (Uttar Pradesh) 84.9 |
| Highest state gap scores | Assam 75.3; Bihar 70.4; Chhattisgarh 67.6; Odisha 65.1; Tripura 64.7; Uttar Pradesh 64.4 |

The largest gaps sit in states with few listed chargers per EV, which is also where inventory gaps are most likely. We treat the Assam, Bihar and Odisha results as priorities for verification against the full official list.

### 7.4 Representative geography: Maharashtra, Pune against Amravati

Maharashtra has 1,218,821 EVs (measured) and 4,887 listed stations (measured). Its state gap score is 61.3, band 4, with a state coverage factor of 0.70. The state average hides large differences between districts, which is the case for district-level planning.

| Quantity | Pune | Amravati | Status |
|---|---|---|---|
| Population | 9,429,408 | 2,888,445 | Census 2011 |
| Stations found | 1,802 | 35 | measured |
| EVs (RTO-based) | 304,876 | 37,744 | modelled |
| EVs per adjusted charger | 118 | 755 | modelled |
| Mean distance to nearest charger | 5.7 km | 15.4 km | modelled |
| Area within 3 km of a charger | 28.4% | 3.3% | modelled |
| Gap score, band | 50.6, band 3 | 89.4, band 5 | modelled |
| Confidence | high | high | |
| 2030 chargers to add, base (range in 7.5) | 13,669 | 2,759 | modelled |

Pune has the second largest inventory of any district, after Bangalore, yet only about 28% of its area is inside the 3 km norm, because the district includes large rural areas. Amravati has the highest gap score of all 735 districts. Other Maharashtra districts in band 4 or 5 include Jalgaon, Nanded, Yavatmal and Gadchiroli.

### 7.5 Corridors, sites and forecast (modelled)

The corridor step produced 18 National Highway corridors on measured MoRTH and GatiShakti geometry (June 2022), with 219 stations to add in total at the 25 km spacing norm. The corridors with the most stations to add are NH 27 (30), NH 30 (25), NH 2 (23), NH 11 (17), NH 63 (16) and NH 52 (15). The largest single gap is 199 km, on NH 2. NH 44 (3,522 km), NH 48 (2,669 km) and NH 27 (3,374 km) reach 86 to 96% of their published lengths, as lower bounds. The site step produced 202 candidate sites in 59 districts (105 AC, 89 DC 30, 8 DC 60). Median distance to the nearest listed substation is 0.0 km, because candidates are drawn from substation locations.

**Forecast and requirement.** Every figure carries a low to high range from the sensitivity run: low is public share 10% with 2035 utilisation 21%, high is public share 20% with 2035 utilisation 7.5%. The EV path is the base scenario in both. Base values use public share 15% and utilisation ramping to 15% in 2035.

| Year | National EVs low / base / high | Chargers required, base | Chargers to add, base | Chargers to add, low to high |
|---|---|---|---|---|
| 2027 | 15.6 / 16.4 / 16.7 million | 5.16 lakh | 4.07 lakh | 1.44 to 12.65 lakh |
| 2030 | 31.0 / 39.3 / 45.0 million | 8.41 lakh | 7.32 lakh | 2.93 to 21.34 lakh |
| 2035 | 46.3 / 82.1 / 132.0 million | 11.47 lakh | 10.37 lakh | 4.37 to 29.49 lakh |

The headline is 10.4 lakh chargers to add by 2035, with a range of 4.4 to 29.5 lakh. The range is wide because utilisation and the public share are poorly known, not because the pipeline is noisy. The research report in `reports/` gives about 4 to 46 lakh as a cross-check, which brackets ours. The utilisation ramp is our assumption, and 15% in 2035 is a target.

### 7.6 Status at submission

| Stage | State |
|---|---|
| Integration (3.1) | Complete and self-checked; ten pipeline checks pass |
| EV allocation, coverage, gap score (3.2 to 3.4) | Complete; outputs in `districts_gap.csv`, `states.csv`; RTO crosswalk not yet validated against an official list |
| Forecast and requirement (3.5, 3.6) | Complete; outputs in `districts_forecast.csv`, `scenarios.json` |
| Corridors and sites (3.7, 3.8) | Complete; outputs in `corridors.json`, `sites.json` |
| Web application | Working prototype: map, scorecard, planner, corridors, method, plus a read-only API |
| Validation backtest and sensitivity pages (3.9) | Planned for the finale |

Sections 7.1 and 7.2 are measured results. Sections 7.3 to 7.5 are model outputs and every parameter behind them is listed in the assumptions table.

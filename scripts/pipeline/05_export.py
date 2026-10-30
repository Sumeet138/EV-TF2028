"""Step 5: join data/processed/ into the client's static JSON files (client/public/data/), see docs/CONTRACT.md.

Fails loudly when an input is missing or an output has the wrong shape.
Run: uv run --no-project --with pandas --with pyarrow --with openpyxl --with geopandas --with shapely --with scipy python scripts/pipeline/05_export.py
"""
import json
import math
import re
from datetime import datetime, timezone

import geopandas as gpd
import numpy as np
import pandas as pd

from common import DATA_CSV, GEOJSON, OUT, RAW, ROOT, STATES

DEST = ROOT / "client" / "public" / "data"
DEST.mkdir(parents=True, exist_ok=True)
OFFICIAL, OFFICIAL_AS_OF = 52718, "2026-07-21"  # Lok Sabha Q.453, BHEL portal count; earlier totals used a different source
MAX_TOTAL, MAX_GEO = 12 * 2**20, 2 * 2**20
need = lambda f: (OUT / f) if (OUT / f).exists() else (_ for _ in ()).throw(FileNotFoundError(f"missing required input data/processed/{f}"))


def clean(o):
    """JSON-safe: NaN/inf -> None, numpy -> python."""
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (float, np.floating)):
        return None if not math.isfinite(o) else float(o)
    return o


def write(name, obj, **kw):
    s = json.dumps(clean(obj), separators=(",", ":"), ensure_ascii=False, **kw)
    (DEST / name).write_text(s, encoding="utf-8")
    return len(s.encode())


def jcol(df, c):
    return df[c].map(lambda v: json.loads(v) if isinstance(v, str) else v)


def records(df, ints=(), nullable_ints=()):
    out = []
    for r in df.to_dict("records"):
        for k in ints:
            r[k] = int(r[k])
        for k in nullable_ints:
            r[k] = None if pd.isna(r[k]) else int(r[k])
        out.append(r)
    return out


# ---------- inputs ----------
base = pd.read_csv(need("districts_base.csv"))
gap = pd.read_csv(need("districts_gap.csv"))
fc = pd.read_csv(need("districts_forecast.csv"))
st = pd.read_csv(need("states.csv"))
chg = pd.read_csv(need("chargers_clean.csv"))
scen = json.loads(need("scenarios.json").read_text())
corr = json.loads(need("corridors.json").read_text())
sites = json.loads(need("sites.json").read_text())
assump = []
for a in ["gap", "forecast", "corridors"]:
    j = json.loads(need(f"assumptions_{a}.json").read_text())
    assump += j["assumptions"] if isinstance(j, dict) else j
    if isinstance(j, dict) and "norms" in j:
        gap_norms = j["norms"]
subs_raw = json.loads((RAW / "grid" / "osm_substations.json").read_text())["elements"]
data = pd.read_csv(DATA_CSV, low_memory=False)

# ---------- districts.json ----------
assert base.id.is_unique and gap.id.is_unique and fc.id.is_unique
d = base.merge(gap, on="id", how="left", validate="1:1").merge(fc, on="id", how="left", validate="1:1", suffixes=("", "_fc"))
unscored = d.gapScore.isna()  # no Census match: shown with score 0 / band 1 and confidence low, driver text says why
assert unscored.sum() <= 5 and d.gapDrivers[unscored].str.contains("no gap score").all(), "unexpected unscored districts"
d.loc[unscored, ["gapScore", "gapBand", "population", "urbanShare", "nightlights"]] = [0, 1, 0, 0, 0]
d[["population", "urbanShare", "nightlights"]] = d[["population", "urbanShare", "nightlights"]].fillna(0)
for c in ["evsByYear", "gapDrivers"]:
    d[c] = jcol(d, c)

FY = ["2027", "2030", "2035"]
if "forecast" in d.columns:
    d["forecast"] = jcol(d, "forecast")
else:  # flat columns: f<year>_<field> or <field>_<year>
    def find(y, f):
        for pat in (f"{f}{y}", f"{f}_{y}", f"{y}_{f}", f"f{y}_{f}", f"{f}.{y}"):
            if pat in d.columns:
                return pat
        raise KeyError(f"districts_forecast.csv: no column for {f} {y}")
    fields = ["evs", "chargersRequired", "chargersToAdd", "demandMWhPerDay"]
    types = ["ac", "dc30", "dc60", "dc120"]
    fcs = []
    for _, r in d.iterrows():
        fcs.append({y: {**{f: float(r[find(y, f)]) if f == "demandMWhPerDay" else int(r[find(y, f)]) for f in fields},
                        "byType": {t: int(r[find(y, t)]) for t in types}} for y in FY})
    d["forecast"] = fcs
for r in d.forecast:
    assert set(r) == set(FY) and all({"evs", "chargersRequired", "chargersToAdd", "byType", "demandMWhPerDay"} <= set(v) for v in r.values())

D_COLS = ["id", "name", "state", "code", "lat", "lon", "areaKm2", "population", "urbanShare", "nightlights", "evs", "evsByYear",
          "chargers", "chargersAdjusted", "connectors", "evsPerCharger", "coverageKm", "within3kmShare", "substations",
          "tollPlazas", "evsSource", "gapScore", "gapBand", "gapDrivers", "confidence", "forecast"]
dist = d[D_COLS].copy()
dist = dist.astype(object).where(dist.notna(), None)
districts = records(dist, ints=["population", "evs", "chargers", "substations", "tollPlazas", "gapBand"], nullable_ints=["connectors"])
assert len(districts) == len(base) > 700
id_index = {x["id"]: i for i, x in enumerate(districts)}

# ---------- states.json ----------
st["evsByYear"] = jcol(st, "evsByYear")
if "chargersToAdd2030" not in st.columns:
    st["chargersToAdd2030"] = st.name.map(d.assign(a=d.forecast.map(lambda f: f["2030"]["chargersToAdd"])).groupby("state").a.sum())
S_COLS = ["name", "evs", "evsByYear", "evShare2025", "chargers", "chargersAdjusted", "evsPerCharger", "coverageFactor",
          "gapScore", "gapBand", "districts", "chargersToAdd2030"]
sdf = st[S_COLS].astype(object)
sdf = sdf.where(sdf.notna(), None)
states = records(sdf, ints=["evs", "chargers", "gapBand", "districts", "chargersToAdd2030"])
assert {s["name"] for s in states} == set(STATES)

# ---------- national.json ----------
vah = data[data.layer == "ev_registrations"]
tot25 = vah[(vah.metric == "registrations_TOTAL") & (vah.year.astype(str) == "2025")].value.sum()
ev_year = {}
for s in states:
    for y, v in s["evsByYear"].items():
        ev_year[int(y)] = ev_year.get(int(y), 0) + v
off = data[(data.layer == "charger") & (data.level == "national")].sort_values("year")
series = [{"date": str(r.year), "stations": int(r.value)} for r in off.itertuples()]
series.append({"date": OFFICIAL_AS_OF, "stations": OFFICIAL})
found = len(chg)
national = {
    "evsCumulative": int(sum(s["evs"] for s in states)), "evs2025": int(ev_year[2025]), "vehicles2025": int(tot25),
    "chargersFound": found, "chargersOfficial": OFFICIAL, "chargersOfficialAsOf": OFFICIAL_AS_OF,
    "coverageShare": found / OFFICIAL, "officialSeries": series,
    "evSeries": [{"year": y, "evs": int(v)} for y, v in sorted(ev_year.items())],
    "chargersToAdd": {y: int(sum(x["forecast"][y]["chargersToAdd"] for x in districts)) for y in FY},
    "chargersToAddRange": json.loads((OUT / "scenarios.json").read_text()).get("sensitivity"),
}

# ---------- chargers.json, substations.json ----------
SRC = ["Tata Power", "Statiq", "BEE", "OCM", "Operators", "OSM"]
PHONE = re.compile(r"[\s,.(-]*(?:ph\.?|call|mob\.?|phone)?[\s:.-]*(?:\+?91[- ]?)?(?<!\d)[6-9]\d{9}(?!\d)\)?", re.I)  # some listings carry a phone number in the name
chg["si"] = chg.sources.str.split("|").str[0].map(SRC.index)
chargers = {"sources": SRC, "rows": [[round(r.lat, 5), round(r.lon, 5), int(r.si), PHONE.sub("", str(r.name))[:60], id_index[r.districtId]]
                                     for r in chg.itertuples()]}


def kv(tags):
    v = [float(x) for x in re.split(r"[;,]", tags.get("voltage", "")) if re.fullmatch(r"\s*\d+(\.\d+)?\s*", x)]
    return round(max(v) / 1000, 1) if v else None


subs = []
for e in subs_raw:
    p = e if "lat" in e else e.get("center")
    if p:
        subs.append([round(p["lat"], 4), round(p["lon"], 4), kv(e.get("tags", {}))])

# ---------- districts.geojson ----------
g = gpd.read_file(GEOJSON).to_crs(4326)
assert len(g) == len(base) and (g.shapeName.values == base.name.values).all(), "polygon order differs from districts_base.csv"
g["id"] = base.id.values
tol = 0.004
while True:
    geo = g[["id", "geometry"]].copy()
    geo["geometry"] = geo.geometry.simplify(tol, preserve_topology=True)
    txt = geo.to_json(drop_id=True, na="null", show_bbox=False)
    txt = re.sub(r"(\d+\.\d{3})\d+", r"\1", txt)  # ~100 m
    if len(txt.encode()) < MAX_GEO * 0.95 or tol > 0.1:
        break
    tol *= 1.3
(DEST / "districts.geojson").write_text(txt, encoding="utf-8")
assert not any(f["geometry"] is None for f in json.loads(txt)["features"]), "simplification emptied a polygon"

# ---------- meta.json ----------
cnt = lambda **q: int(len(data.query(" and ".join(f"{k} == {v!r}" for k, v in q.items()))))
sources = [
    {"name": "VAHAN4 dashboard (MoRTH)", "layer": "EV registrations by state", "rows": cnt(layer="ev_registrations"), "licence": "Govt open data", "url": "https://vahan.parivahan.gov.in/vahan4dashboard"},
    {"name": "Tata Power EZ Charge map", "layer": "Chargers", "rows": cnt(source="Tata Power EZ Charge map"), "licence": "Scraped from public map", "url": "https://ezcharge.tatapower.com/evselfcare"},
    {"name": "Statiq map", "layer": "Chargers", "rows": cnt(source="Statiq map"), "licence": "Scraped from public map", "url": "https://www.statiq.in/ev-charging-station"},
    {"name": "OpenStreetMap (amenity=charging_station)", "layer": "Chargers", "rows": cnt(source="OpenStreetMap", layer="charger"), "licence": "ODbL", "url": "https://www.openstreetmap.org"},
    {"name": "BEE EV Yatra snapshot, Dec 2024", "layer": "Chargers", "rows": cnt(source="BEE EV Yatra snapshot Dec 2024"), "licence": "Unclear: public GitHub copy, no licence", "url": "https://evyatra.beeindia.gov.in"},
    {"name": "Open Charge Map", "layer": "Chargers", "rows": cnt(source="Open Charge Map"), "licence": "CC BY 4.0 (contributor data)", "url": "https://openchargemap.org"},
    {"name": "Parliament replies and PIB", "layer": "Official state charger counts", "rows": cnt(layer="charger_official"), "licence": "Govt document", "url": "https://sansad.in"},
    {"name": "India Data Portal VAHAN", "layer": "EV registrations by RTO, 2022-2026", "rows": cnt(layer="ev_registrations_rto"), "licence": "ODC-BY", "url": "https://indiadataportal.com"},
    {"name": "PM GatiShakti MoRTH National Highways", "layer": "Road geometry (June 2022)", "rows": 10317, "licence": "Govt open data", "url": "https://indiadataportal.com"},
    {"name": "Rajya Sabha Q3929 via data.gov.in", "layer": "Official national charger totals", "rows": cnt(source="Rajya Sabha Q3929 via data.gov.in"), "licence": "GODL-India", "url": "https://data.gov.in"},
    {"name": "geoBoundaries gbOpen IND ADM2", "layer": "District polygons (2021)", "rows": len(g), "licence": "ODbL", "url": "https://www.geoboundaries.org"},
    {"name": "MoRTH toll plazas via PM GatiShakti", "layer": "Roads", "rows": cnt(layer="roads"), "licence": "CC0", "url": "https://github.com/yashveeeeeer/india-geodata"},
    {"name": "Census 2011 district table", "layer": "Population, households, vehicles", "rows": cnt(layer="demographics"), "licence": "Govt open data", "url": "https://github.com/nishusharma1608/India-Census-2011-Analysis"},
    {"name": "VIIRS night lights 2024", "layer": "Economic activity", "rows": cnt(layer="economy"), "licence": "Open", "url": "https://github.com/yashveeeeeer/india-geodata"},
    {"name": "OpenStreetMap (power=substation)", "layer": "Grid", "rows": len(subs), "licence": "ODbL", "url": "https://www.openstreetmap.org"},
    {"name": "MoP EV charging guidelines (2022, amended 2023)", "layer": "Spacing norms", "rows": 0, "licence": "Govt document", "url": "https://powermin.gov.in"},
]
norms = gap_norms  # quoted clause from the MoP guidelines, written by 02_gap.py
assert {"urbanSpacingKm", "highwaySpacingKm", "source"} <= set(norms)

pop_c = pd.read_csv(RAW / "demographics/census2011_districts.csv").Population.sum()
site_ids = {s["districtId"] for s in sites}
checks = [
    ("Every district has a polygon and a data row", len(districts) == len(g) == geo.id.nunique(), f"{len(districts)} districts, {len(g)} polygons"),
    ("District population within 5% of Census 2011 total", abs(sum(x["population"] for x in districts) / pop_c - 1) < 0.05,
     f"{sum(x['population'] for x in districts):,} vs {int(pop_c):,}"),
    ("District chargers sum to the deduplicated stations", sum(x["chargers"] for x in districts) == found, f"{sum(x['chargers'] for x in districts):,} vs {found:,}"),
    ("State EV totals equal district EV totals (1%)", abs(sum(x["evs"] for x in districts) / national["evsCumulative"] - 1) < 0.01,
     f"{sum(x['evs'] for x in districts):,} vs {national['evsCumulative']:,}"),
    ("Charger coverage vs official total", 0.3 < national["coverageShare"] < 1.0, f"{found:,} of {OFFICIAL:,} = {national['coverageShare']:.1%}"),
    ("Every charger row maps to a district", all(0 <= r[4] < len(districts) for r in chargers["rows"]), f"{len(chargers['rows']):,} rows"),
    ("Every site belongs to a known district", site_ids <= set(id_index), f"{len(sites):,} sites in {len(site_ids)} districts"),
    ("Forecast chargers required never falls 2027 to 2035", all(x["forecast"]["2027"]["chargersRequired"] <= x["forecast"]["2035"]["chargersRequired"] for x in districts), "all districts"),
    ("Gap band is 1-5 and consistent with score order", all(1 <= x["gapBand"] <= 5 for x in districts)
     and max(x["gapScore"] for x in districts if x["gapBand"] == 1) <= min(x["gapScore"] for x in districts if x["gapBand"] == 5), "bands 1-5"),
    ("Polygon file under 2 MB", (DEST / "districts.geojson").stat().st_size < MAX_GEO, f"{(DEST / 'districts.geojson').stat().st_size / 2**20:.2f} MB, tolerance {tol:.3f} deg"),
]
meta = {"generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"), "sources": sources, "assumptions": assump, "norms": norms,
        "validation": [{"check": c, "result": r, "pass": bool(p)} for c, p, r in checks]}

# ---------- write + final asserts ----------
sizes = {n: write(n, o) for n, o in [("districts.json", districts), ("states.json", states), ("national.json", national),
                                      ("chargers.json", chargers), ("substations.json", subs), ("corridors.json", corr),
                                      ("sites.json", sites), ("scenarios.json", scen), ("meta.json", meta)]}
sizes["districts.geojson"] = (DEST / "districts.geojson").stat().st_size
total = sum(sizes.values())
for n, s in sizes.items():
    print(f"{n:20s} {s / 1024:9.1f} KB")
print(f"{'total':20s} {total / 2**20:9.2f} MB")
assert total < MAX_TOTAL, "client/public/data over 12 MB"
assert sizes["districts.geojson"] < MAX_GEO
assert len(subs) > 10000 and len(corr) > 0 and len(sites) > 0 and len(chargers["rows"]) == found
assert all(c["pass"] for c in meta["validation"]), [c for c in meta["validation"] if not c["pass"]]
assert {"series", "defaults"} <= set(scen) and set(scen["series"]) == {"low", "base", "high"}
print("export ok")

"""Step 1: integrate raw sources onto the 2021 district polygons.

Writes data/processed/chargers_clean.csv and districts_base.csv. Choices, in short:
- State per polygon: name lookup (Census, new-district / split / rename lists, toll plaza districts) combined with the
  state of Tata/toll points inside the polygon; leftovers take the majority state of touching polygons.
- Census 2011 -> 2021 polygons: exact name, then rename chain, then 2011+ splits (parent is apportioned over every
  surviving polygon descended from it, by area), then fuzzy name (>= 0.8, against the parent's split descendants) inside the same state. Telangana (10 old
  districts) and Ladakh (Leh, Kargil) are carved out of Andhra Pradesh and Jammu and Kashmir by name.
- Area apportioning is crude: it assumes people and light are spread evenly over the parent. Flagged 'apportioned'.
- Chargers: points outside India dropped; same site = within 30 m, or within 100 m with similar names.

Run: uv run --no-project --with pandas --with pyarrow --with openpyxl --with geopandas --with shapely --with scipy python scripts/pipeline/01_integrate.py
"""
import re
import warnings
from collections import Counter
from difflib import SequenceMatcher

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree

from common import AREA_CRS, DATA_CSV, GEOJSON, OUT, RAW, STATES, canon_state, norm, slug, to_m

warnings.filterwarnings("ignore")  # pandas fragmentation / degree-buffer noise
OUT.mkdir(parents=True, exist_ok=True)
data = pd.read_csv(DATA_CSV, low_memory=False)

# ---------- polygons ----------
g = gpd.read_file(GEOJSON).rename(columns={"shapeName": "name", "shapeID": "shape_id"})[["name", "shape_id", "geometry"]].to_crs(4326)
bad = ~g.is_valid
g.loc[bad, "geometry"] = g.loc[bad].buffer(0)
g["pn"] = g.name.map(norm)
g["alt"] = g.name.str.extract(r"\((.*?)\)")[0].map(lambda x: norm(x) if isinstance(x, str) else None)  # 'Kadapa(YSR)' -> YSR
g["area"] = g.to_crs(AREA_CRS).area / 1e6


def locate(df, tol_m=0):
    """Polygon index containing each point; with tol_m, unmatched points snap to a polygon within tol_m metres."""
    p = gpd.GeoDataFrame(df[[]], geometry=gpd.points_from_xy(df.lon, df.lat), crs=4326)
    j = gpd.sjoin(p, g[["geometry"]], predicate="within").index_right
    j = j[~j.index.duplicated()].reindex(df.index)
    if tol_m and j.isna().any():
        miss = p[j.isna()].to_crs(AREA_CRS)
        n = gpd.sjoin_nearest(miss, g[["geometry"]].to_crs(AREA_CRS), max_distance=tol_m)
        n = n[~n.index.duplicated()]
        j.loc[n.index] = n.index_right
    return j


# ---------- census 2011 (with Telangana / Ladakh carved out) ----------
cen = pd.read_csv(RAW / "demographics/census2011_districts.csv")
cen["state"] = cen["State name"].map(canon_state)
cen["name"] = cen["District name"]
cen["pn"] = cen.name.map(norm)
TELANGANA = "ADILABAD NIZAMABAD KARIMNAGAR MEDAK HYDERABAD RANGAREDDY MAHBUBNAGAR NALGONDA WARANGAL KHAMMAM".split()
cen.loc[(cen.state == "Andhra Pradesh") & cen.pn.isin(TELANGANA), "state"] = "Telangana"
cen.loc[(cen.state == "Jammu and Kashmir") & cen.pn.isin(["LEH", "KARGIL"]), "state"] = "Ladakh"
assert (cen.state == "Telangana").sum() == 10 and (cen.state == "Ladakh").sum() == 2 and cen.state.notna().all()
M = {"pop": "Population", "hh": "Households", "urbhh": "Urban_Households", "car": "Households_with_Car_Jeep_Van",
     "twowh": "Households_with_Scooter_Motorcycle_Moped", "pp": "Total_Power_Parity", "pphigh": "Power_Parity_Above_Rs_545000"}
nl = pd.read_csv(RAW / "demographics/nightlights_districts_2024.csv").set_index("district_id")["sum"]
cen["nl"] = cen["District code"].map(nl)  # nightlight file shares the census district codes
assert cen.nl.notna().mean() > 0.97, "nightlight join by district code failed"
for k, v in M.items():
    cen[k] = cen[v]

# ---------- polygon -> state ----------
rd = lambda f: pd.read_csv(RAW / "demographics" / f).rename(columns={"State/UT": "st"})
chg, new, spl = rd("district_name_changes_1951_to_2021.csv"), rd("new_districts_created_1951_to_2024.csv"), rd("district_splits_and_carveouts_1951_to_2024.csv")
toll = data[data.layer == "roads"].copy()
names = {}  # normalised district name -> Counter of states it is known in


def know(n, s):
    s = canon_state(s)
    if s and isinstance(n, str):
        names.setdefault(norm(n), Counter())[s] += 1


cen_names = {}  # Census names are authoritative (carve-outs included) and override the other lists
for a, b in zip(cen.name, cen.state):
    know(a, b)
    cen_names.setdefault(norm(a), Counter())[b] += 1
for df, cols in [(chg, ["Old Name", "New Name"]), (new, ["New District"]), (spl, ["District-Before", "District-After"])]:
    for c in cols:
        for a, b in zip(df[c], df.st):
            know(a, b)
for a, b in zip(toll.district.str.title(), toll.state.str.title()):
    know(a, b)

tata = data[(data.layer == "charger") & data.source.str.startswith("Tata")]
vp = pd.concat([tata, toll])[["lat", "lon", "state"]].dropna().reset_index(drop=True)
vp["pi"] = locate(vp)
vp["s"] = vp.state.map(canon_state)
votes = {pi: Counter(x.s) for pi, x in vp.dropna(subset=["pi", "s"]).groupby("pi")}

nb = gpd.sjoin(g[["geometry"]].assign(geometry=g.buffer(0.01)), g[["geometry"]], predicate="intersects")  # 0.01 deg ~ 1 km closes slivers
nb = nb[nb.index != nb.index_right].groupby(level=0).index_right.agg(list)

g["state"], g["how"] = None, ""
for i, r in g.iterrows():
    cands, v = cen_names.get(r.pn) or names.get(r.pn, Counter()), votes.get(i, Counter())
    if len(cands) == 1:
        g.loc[i, ["state", "how"]] = [next(iter(cands)), "name" + ("" if not v or v.most_common(1)[0][0] in cands else "!vote-conflict")]
    elif v and cands and any(s in cands for s in v):
        g.loc[i, ["state", "how"]] = [max((s for s in v if s in cands), key=v.get), "name+vote"]
    elif v:
        g.loc[i, ["state", "how"]] = [v.most_common(1)[0][0], "vote"]
fuzzy_state = {}  # spelling variants (Gariaband / Gariyaband): states of the closest known names, ratio >= 0.8
for i in g.index[g.state.isna()]:
    sc = {n: SequenceMatcher(None, g.pn[i], n).ratio() for n in names}
    top = max(sc.values())
    if top >= 0.8:
        fuzzy_state[i] = Counter(s for n, r in sc.items() if r >= top - 0.02 for s in names[n])
while g.state.isna().any():  # neighbours' majority, restricted to name candidates when there are any
    todo = []
    for i in g.index[g.state.isna()]:
        c = Counter(g.state[j] for j in nb.get(i, []) if g.state[j])
        k = cen_names.get(g.pn[i]) or names.get(g.pn[i]) or fuzzy_state.get(i, Counter())
        c = Counter({s: n for s, n in c.items() if s in k}) or c if k else c
        if c:
            todo.append((i, c.most_common(1)[0][0]))
        elif k:
            todo.append((i, k.most_common(1)[0][0]))
    if not todo:
        break
    for i, s in todo:
        g.loc[i, ["state", "how"]] = [s, "neighbour"]
if g.state.isna().any():  # last resort: nearest resolved centroid
    cc = g.to_crs(AREA_CRS).centroid
    ok = g.state.notna()
    for i in g.index[~ok]:
        g.loc[i, ["state", "how"]] = [g.state[cc[ok].distance(cc[i]).idxmin()], "nearest"]
assert set(g.state) == set(STATES), f"states missing: {set(STATES) - set(g.state)}"

# ---------- crosswalk 2011 districts -> polygons ----------
cen_by_state = cen.groupby("state").pn.agg(set).to_dict()


def snap(s, n):
    """Map a historic spelling onto the Census 2011 spelling in that state (Mahabubnagar -> Mahbubnagar)."""
    n = norm(n)
    best = max(((SequenceMatcher(None, n, c).ratio(), c) for c in cen_by_state.get(s, ())), default=(0, n))
    return best[1] if best[0] >= 0.85 else n


adj = {}  # rename graph per state: old <-> new
for a, b, s in zip(chg["Old Name"], chg["New Name"], chg.st):
    if isinstance(a, str) and isinstance(b, str) and canon_state(s):
        a, b, s = snap(canon_state(s), a), snap(canon_state(s), b), canon_state(s)
        adj.setdefault((s, a), set()).add(b)
        adj.setdefault((s, b), set()).add(a)
kids = {}  # 2011+ splits: parent -> children
for a, b, y, s in zip(spl["District-Before"], spl["District-After"], spl.Year, spl.st):
    if canon_state(s) and isinstance(a, str) and isinstance(b, str) and pd.to_numeric(y, errors="coerce") >= 2011:
        kids.setdefault((canon_state(s), snap(canon_state(s), a)), set()).add(norm(b))


def reach(s, n, edges):
    seen, todo = {n}, [n]
    while todo:
        for m in edges.get((s, todo.pop()), ()):
            if m not in seen:
                seen.add(m)
                todo.append(m)
    return seen


EDGES = {k: kids.get(k, set()) | adj.get(k, set()) for k in set(kids) | set(adj)}  # renames both ways, splits parent -> child


def family(s, n):
    """All names a 2011 district may carry on a 2021 polygon: itself, renames, and split descendants."""
    return reach(s, n, EDGES)


cen["fam"] = [family(s, n) for s, n in zip(cen.state, cen.pn)]
cen["polys"] = [[] for _ in cen.index]
cen["kind"] = ""
claimed = set()
for c, r in cen.iterrows():
    hit = g.index[(g.state == r.state) & (g.pn.isin(r.fam) | g.alt.isin(r.fam))]
    cen.at[c, "polys"] = list(hit)
    claimed |= set(hit)
fuzzy = []
for i in g.index.difference(claimed):  # polygons nobody claimed: fuzzy name inside the same state
    best = max(((1.0 if min(len(g.pn[i]), len(f)) >= 4 and (f.startswith(g.pn[i]) or g.pn[i].startswith(f)) else SequenceMatcher(None, g.pn[i], f).ratio(), c)
                for c, r in cen[cen.state == g.state[i]].iterrows() for f in r.fam), default=(0, None))
    if best[0] >= 0.8:
        cen.at[best[1], "polys"] = cen.polys[best[1]] + [i]
        fuzzy.append((g.name[i], cen.name[best[1]], round(best[0], 2)))
        claimed.add(i)

for k in ["pop", "hh", "urbhh", "car", "twowh", "pp", "pphigh", "nl"]:
    g[k] = np.nan
g["kinds"] = [set() for _ in g.index]
for c, r in cen.iterrows():
    if not r.polys:
        continue
    w = g.area[r.polys] / g.area[r.polys].sum()
    for i in r.polys:
        for k in ["pop", "hh", "urbhh", "car", "twowh", "pp", "pphigh", "nl"]:
            g.loc[i, k] = np.nan_to_num(g.at[i, k]) + r[k] * w[i]
        g.at[i, "kinds"].add("apportioned" if len(r.polys) > 1 else "exact" if g.pn[i] == r.pn else "crosswalk")
g["match_quality"] = [("apportioned" if "apportioned" in k else "crosswalk" if "crosswalk" in k else "exact" if k else "none") for k in g.kinds]
unmatched_cen = cen[cen.polys.map(len) == 0]

# ---------- chargers ----------
ch = data[(data.layer == "charger") & (data.level == "point")].copy()
SRC = {"Tata": "Tata Power", "Statiq": "Statiq", "BEE": "BEE", "Open Charge Map": "OCM", "Ola": "Operators", "ChargeMOD": "Operators", "Relux": "Operators"}  # source prefix -> label; anything else is OSM
ch["src"] = ch.source.map(lambda s: next((v for k, v in SRC.items() if s.startswith(k)), "OSM"))
ch["conn"] = ch.value.where(ch.src == "Tata Power")
raw_n = len(ch)
ch = ch[ch.lat.between(6, 38) & ch.lon.between(68, 98)].reset_index(drop=True)
n_bbox = raw_n - len(ch)
ch["pi"] = locate(ch, tol_m=2000)  # 2 km tolerance: boundaries are simplified along the coast
n_out = ch.pi.isna().sum()
ch = ch.dropna(subset=["pi"]).reset_index(drop=True)
n_valid = len(ch)
per_src_before = Counter(ch.src)

STOP = set("charging station stations charger chargers ev point tata power statiq the at".split())
ch["tok"] = ch.name.map(lambda n: frozenset(w for w in re.findall(r"[a-z0-9]+", str(n).lower()) if w not in STOP) if isinstance(n, str) else frozenset())


def same_site(i, j, d):
    if d <= 30:
        return True
    a, b = ch.tok[i], ch.tok[j]
    if not a or not b:
        return False  # no name evidence: only the 30 m rule applies
    return a <= b or b <= a or SequenceMatcher(None, " ".join(sorted(a)), " ".join(sorted(b))).ratio() >= 0.6


xy = to_m(ch.lat, ch.lon)
pairs = cKDTree(xy).query_pairs(100, output_type="ndarray")
dist = np.hypot(*(xy[pairs[:, 0]] - xy[pairs[:, 1]]).T)
keep = np.array([same_site(i, j, d) for (i, j), d in zip(pairs, dist)], dtype=bool)
e = pairs[keep]
_, ch["cl"] = connected_components(coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(len(ch),) * 2), directed=False)
ch["pri"] = ch.src.map({"Tata Power": 0, "Statiq": 1, "BEE": 2, "OCM": 3, "Operators": 4, "OSM": 5})
ch = ch.sort_values(["cl", "pri"])  # first row per cluster (Tata > Statiq > BEE > OCM > OSM) supplies name and coordinates
grp = ch.groupby("cl")
clean = pd.DataFrame({
    "name": grp.name.agg(lambda s: next((x for x in s if isinstance(x, str) and x.strip()), "")),
    "lat": grp.lat.first(), "lon": grp.lon.first(),
    "sources": grp.src.agg(lambda s: "|".join(dict.fromkeys(s))),
    "listings": grp.size(),
    "connectors": grp.conn.sum(min_count=1),  # Tata-listed connectors only; Statiq / OSM give no count
    "pi": grp.pi.first(),
}).reset_index(drop=True)
clean["name"] = clean.name.str.replace(r"\s+", " ", regex=True).str.strip()
n_clean = len(clean)
per_src_after = Counter(x for v in clean.sources for x in v.split("|"))  # unique stations each source appears in
# chaining check: connected components can string 100 m links across a city; diameter = max pairwise spread per cluster
_xy = to_m(ch.lat, ch.lon)
ch["x"], ch["y"] = _xy[:, 0], _xy[:, 1]
_b = ch.groupby("cl").agg(w=("x", lambda s: s.max() - s.min()), h=("y", lambda s: s.max() - s.min()), n=("x", "size"))
_b["diam"] = np.hypot(_b.w, _b.h)  # bounding-box diagonal >= true diameter, cheap upper bound
overlap = Counter(clean.sources)

# ---------- districts_base ----------
g["state"] = g.state.astype(str)
g["id"] = (g.state + "-" + g.name).map(slug)
dup = g.id.duplicated(keep=False)
g.loc[dup, "id"] = g.id[dup] + "-" + g.groupby("id").cumcount().add(1).astype(str)[dup]
clean["districtId"] = g.id[clean.pi].values
clean["state"] = g.state[clean.pi].values
clean.insert(0, "id", [f"ch{n:05d}" for n in range(1, len(clean) + 1)])
clean[["id", "name", "lat", "lon", "state", "districtId", "sources", "listings", "connectors"]].round({"lat": 6, "lon": 6}).to_csv(OUT / "chargers_clean.csv", index=False)

cent = g.to_crs(AREA_CRS).centroid.to_crs(4326)
g["lat"], g["lon"] = cent.y, cent.x
g = g.sort_values(["state", "name"])
g["code"] = [f"{STATES[s][0]} {n:02d}" for s, n in zip(g.state, g.groupby("state").cumcount() + 1)]  # alphabetical within state, not real RTO series
g = g.sort_index()


def count_in(df):
    return df.assign(pi=locate(df.reset_index(drop=True)).values).pi.dropna().astype(int).value_counts().reindex(g.index, fill_value=0)


g["chargers"] = clean.pi.astype(int).value_counts().reindex(g.index, fill_value=0)
g["connectors"] = clean.groupby("pi").connectors.sum(min_count=1).reindex(g.index)
g["substations"] = count_in(data[data.layer == "grid"][["lat", "lon"]].dropna())
g["tollPlazas"] = count_in(toll[["lat", "lon"]].dropna())
g["urbanShare"] = g.urbhh / g.hh  # household-based: the census extract has urban households, not urban population
base = g.rename(columns={"area": "areaKm2", "hh": "households", "car": "carHouseholds", "twowh": "twoWheelerHouseholds",
                         "pp": "powerParityTotal", "pphigh": "powerParityAbove545k", "pop": "population", "nl": "nightlights"})
cols = ["id", "name", "state", "code", "lat", "lon", "areaKm2", "population", "urbanShare", "households", "carHouseholds",
        "twoWheelerHouseholds", "powerParityTotal", "powerParityAbove545k", "nightlights", "chargers", "connectors",
        "substations", "tollPlazas", "match_quality"]
out = base[cols].copy()
for c in ["population", "households", "carHouseholds", "twoWheelerHouseholds", "powerParityTotal", "powerParityAbove545k"]:
    out[c] = out[c].round(0)
out.round({"lat": 5, "lon": 5, "areaKm2": 1, "urbanShare": 4, "nightlights": 1}).to_csv(OUT / "districts_base.csv", index=False)

# ---------- report ----------
print(f"polygons {len(g)}; state source: {dict(Counter(g.how))}")
print("uncertain state (neighbour/nearest/vote-conflict):", g[g.how.str.contains("neighbour|nearest|conflict")][["name", "state", "how"]].values.tolist())
print(f"census districts {len(cen)}: matched {len(cen) - len(unmatched_cen)}; unmatched {unmatched_cen[['state', 'name']].values.tolist()}")
print("fuzzy matches:", fuzzy)
print("polygon match_quality:", dict(Counter(g.match_quality)))
print(f"population kept {out.population.sum():,.0f} of {cen['pop'].sum():,.0f}")
print(f"chargers raw {raw_n}; bad/out-of-box {n_bbox}; outside India polygons {n_out}; valid {n_valid}; clean {n_clean}; merged away {n_valid - n_clean}; max cluster {clean.listings.max()}")
print("listings per source before merge:", dict(per_src_before), "\nunique stations touched per source after merge:", dict(per_src_after))
print(f"cluster size >=10: {(_b.n >= 10).sum()}; bbox diagonal max {_b.diam.max():.0f} m; clusters >300 m: {(_b.diam > 300).sum()}")
print(_b.sort_values("n", ascending=False).head(8).round(0).to_dict("index"))
print("source combos:", dict(overlap))
print("states and polygon counts:", dict(Counter(g.state)))

# ---------- self-check ----------
assert len(out) == len(gpd.read_file(GEOJSON)), "one row per polygon"
assert out.id.is_unique
assert abs(out.population.sum() / cen["pop"].sum() - 1) < 0.05, "population within 5% of Census 2011 total"
assert out.chargers.sum() == len(clean) == clean.districtId.notna().sum(), "district charger sum equals clean stations"
assert set(out.state) == set(STATES) and len(set(out.state)) == 36
assert out.code.is_unique and out.areaKm2.gt(0).all()
print("self-check ok")

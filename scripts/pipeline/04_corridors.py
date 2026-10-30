"""Corridors (measured NH geometry, MORTH/GatiShakti June 2022) and recommended charger sites. Writes corridors.json, sites.json, assumptions_corridors.json."""
import json
import re
import sys
import time
import warnings

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components, dijkstra, minimum_spanning_tree
from shapely.geometry import LineString
from shapely.ops import linemerge
from scipy.spatial import cKDTree

from common import GEOJSON, OUT, RAW, ROOT, canon_state, to_m

warnings.filterwarnings("ignore")
rng = np.random.default_rng(42)

# ---------- wait for the gap table / norms ----------
GAP = sys.argv[1] if len(sys.argv) > 1 else OUT / "districts_gap.csv"  # argv override for dry runs
for _ in range(120):
    if __import__("pathlib").Path(GAP).exists():
        break
    time.sleep(5)
gap = pd.read_csv(GAP)

HWY_KM, URBAN_KM = 25.0, 3.0  # MoP guideline fallbacks (every 25 km on highways; 3 km x 3 km urban grid)
src_hwy = src_urb = "fallback: MoP EV charging guidelines (2022, amended 2023) (25 km highway spacing; one charger per 3 km x 3 km urban grid)"
try:
    norms = json.load(open(OUT / "assumptions_gap.json")).get("norms", {})
    for k, v in (norms.items() if isinstance(norms, dict) else []):
        val = v.get("value", v) if isinstance(v, dict) else v
        if not isinstance(val, (int, float)):
            continue
        if re.search("high|nh|spacing", k, re.I) and 5 <= val <= 100:
            HWY_KM, src_hwy = float(val), "assumptions_gap.json norms." + k
        if re.search("urban|grid|radius", k, re.I) and 0.5 <= val <= 10:
            URBAN_KM, src_urb = float(val), "assumptions_gap.json norms." + k
except FileNotFoundError:
    pass
RADIUS_KM = 3.0 / 2 if URBAN_KM >= 3 else URBAN_KM  # a 3 km grid cell is served from its centre: 1.5 km
RADIUS_KM = max(RADIUS_KM, 1.5)

base = pd.read_csv(OUT / "districts_base.csv")
ch = pd.read_csv(OUT / "chargers_clean.csv")
g = gpd.read_file(GEOJSON).to_crs(4326)
g["id"] = base.id.values  # 01_integrate keeps polygon order (asserted there: one row per polygon)
evs = gap.set_index("id").evs
dist = base.set_index("id")
chm = to_m(ch.lat, ch.lon)
ch_tree = cKDTree(chm)


def hav(a, b):
    """Great-circle km between [lon, lat] arrays."""
    a, b = np.radians(np.asarray(a, float)), np.radians(np.asarray(b, float))
    d = np.sin((b[..., 1] - a[..., 1]) / 2) ** 2 + np.cos(a[..., 1]) * np.cos(b[..., 1]) * np.sin((b[..., 0] - a[..., 0]) / 2) ** 2
    return 12742 * np.arcsin(np.sqrt(d))


# ---------- toll plazas ----------
tp = pd.read_parquet(RAW / "roads" / "morth_toll_plazas.parquet").drop_duplicates("id")
tp = tp.assign(lat=pd.to_numeric(tp.tollplazal, errors="coerce"), lon=pd.to_numeric(tp.tollplaz_1, errors="coerce"))
tp = tp[tp.lat.between(6, 38) & tp.lon.between(68, 98)].copy()
tp["nh"] = tp.nhno_new.astype(str).str.extract(r"(\d+[A-Za-z]*)")[0]
tp = tp.dropna(subset=["nh"])
tp["state"] = tp.sname.map(canon_state)

# ---------- fuel stations (candidate sites on highways) ----------
fuel = pd.read_csv(ROOT / "data" / "data.csv", usecols=["metric", "name", "lat", "lon"], low_memory=False)
fuel = fuel[fuel.metric == "fuel_station"].dropna(subset=["lat", "lon"]).reset_index(drop=True)
fuel_tree = cKDTree(to_m(fuel.lat, fuel.lon))

# ---------- real NH geometry ----------
SNAP = 4  # decimals of a degree (~11 m): segment endpoints closer than this are one node
nh_all = gpd.read_parquet(RAW / "roads" / "morth_national_highways.parquet")
nh_all = nh_all[(nh_all.status == "EXISTING") & nh_all.road_name.fillna("").str.fullmatch(r"NH-\d+")]  # exact NH number, built; NH-44A etc. and proposed links excluded
nh_all = nh_all.dropna(subset=["i", "j"]).explode(index_parts=False)
nh_all["nh"] = nh_all.road_name.str[3:]
nh_all["st"] = nh_all.state_ut.map(canon_state)


def km_of(xy):
    return float(hav(xy[:-1], xy[1:]).sum())


BRIDGE_KM = 150.0  # longest hole in the file a spine may jump across
STEP_KM = 2.0


def longest_path(grp):
    """Spine of one NH number. Node ids are unreliable across state files, so go by position: sample every link
    each 2 km, join the samples with a minimum spanning tree, and take the tree's longest path by double sweep."""
    pts, sts = [], []
    for geom, st in zip(grp.geometry, grp.st):
        x = np.asarray(geom.coords)[:, :2]
        c = np.r_[0, np.cumsum(hav(x[:-1], x[1:]))]
        if c[-1] > 0:
            t = np.r_[np.arange(0, c[-1], STEP_KM), c[-1]]
            pts.append(np.c_[np.interp(t, c, x[:, 0]), np.interp(t, c, x[:, 1])])
            sts += [st] * len(t)
    P = np.vstack(pts)
    tree = cKDTree(to_m(P[:, 1], P[:, 0]))
    A = minimum_spanning_tree(tree.sparse_distance_matrix(tree, BRIDGE_KM * 1000).tocsr())
    A = A + A.T
    ncomp, lab = connected_components(A, directed=False)
    big = np.bincount(lab).argmax()
    d0 = dijkstra(A, indices=int(np.flatnonzero(lab == big)[0])); d0[lab != big] = -1
    a0 = int(d0.argmax())
    d1, pred = dijkstra(A, indices=a0, return_predecessors=True); d1[lab != big] = -1
    chain = [int(d1.argmax())]
    while chain[-1] != a0:
        chain.append(int(pred[chain[-1]]))
    path = P[chain]
    hops = hav(path[:-1], path[1:])
    return path, sorted({sts[i] for i in chain if isinstance(sts[i], str)}), dict(links=len(pts), comps=ncomp, bridged_km=float(hops[hops > 3 * STEP_KM].sum()))


# ---------- corridors ----------
def resample(path, step_km=0.5):
    cum = np.r_[0, np.cumsum(hav(path[:-1], path[1:]))]
    c = np.arange(0, cum[-1], step_km)
    return np.c_[np.interp(c, cum, path[:, 0]), np.interp(c, cum, path[:, 1])], c, cum


def at_chainage(path, cum, c):
    return [round(float(np.interp(c, cum, path[:, 0])), 4), round(float(np.interp(c, cum, path[:, 1])), 4)]


cand_nh = []
for nh, grp in nh_all.groupby("nh"):
    path, states, st = longest_path(grp)
    print(nh, round(km_of(path)), {k: round(v) for k, v in st.items()}) if km_of(path) > 700 else None
    cand_nh.append((nh, path, states, st, km_of(path)))
cand_nh.sort(key=lambda t: -t[4])
MUST = {"44", "48", "19", "16", "27", "66"}  # trunk routes with major connectivity value, kept even if not in the longest 14
pick = cand_nh[:14] + [t for t in cand_nh[14:] if t[0] in MUST]
pick += [t for t in cand_nh[14:] if t not in pick][: 18 - len(pick)]
LENGTHS = {t[0]: round(t[4]) for t in cand_nh[:40]}

corridors, dense = [], {}
for nh, path, states, st, length in pick:
    samp, chs, cum_km = resample(path)
    sm = to_m(samp[:, 1], samp[:, 0])
    d_m, j = cKDTree(sm).query(chm)  # nearest 0.5 km sample; distance good to ~0.25 km
    near = d_m <= 5000
    cc = np.sort(chs[j[near]])
    stops = np.r_[0, cc, length]
    gaps = np.diff(stops)
    CUMF = np.r_[0, np.cumsum(hav(path[:-1], path[1:]))]
    segs = [
        {"from": at_chainage(path, CUMF, a), "to": at_chainage(path, CUMF, b), "km": round(float(b - a), 1)}
        for a, b in zip(stops[:-1], stops[1:]) if b - a > HWY_KM
    ]
    segs = sorted(segs, key=lambda s: -s["km"])[:12]
    simp = np.asarray(LineString(path).simplify(0.002).coords)  # ~200 m; length is computed from the full path
    dense[f"nh-{nh}"] = sm
    corridors.append({
        "id": f"nh-{nh}", "name": f"NH {nh}",
        "path": [[round(float(x), 3), round(float(y), 3)] for x, y in simp],
        "lengthKm": round(length, 1), "states": states, "chargersNear": int(near.sum()),
        "maxGapKm": round(float(gaps.max()), 1), "meanSpacingKm": round(float(gaps.mean()), 1),
        "stationsRequired": int(np.ceil(length / HWY_KM)),
        "stationsToAdd": int(sum(max(0, int(np.ceil(k / HWY_KM)) - 1) for k in gaps if k > HWY_KM)),
        "gapSegments": segs,
    })
corridors.sort(key=lambda c: -c["stationsToAdd"])

# ---------- sites ----------
sub = json.load(open(RAW / "grid" / "osm_substations.json"))["elements"]
sub = pd.DataFrame([(e.get("lat", e.get("center", {}).get("lat")), e.get("lon", e.get("center", {}).get("lon"))) for e in sub], columns=["lat", "lon"]).dropna()
sub_tree = cKDTree(to_m(sub.lat, sub.lon))


def near_sub_km(lat, lon):
    return float(np.ravel(sub_tree.query(to_m(lat, lon))[0])[0]) / 1000


def pts_gdf(df):
    return gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.lon, df.lat), crs=4326)


def district_of(lat, lon):
    j = gpd.sjoin(pts_gdf(pd.DataFrame({"lat": lat, "lon": lon})), g[["id", "geometry"]], how="left", predicate="within")
    j = j[~j.index.duplicated()]
    return j["id"].tolist()


cand = pd.concat([sub.assign(kind="substation"), tp[["lat", "lon"]].assign(kind="toll")], ignore_index=True)
cand["did"] = district_of(cand.lat, cand.lon)
cand = cand.dropna(subset=["did"])
corr_tree = {cid: cKDTree(P) for cid, P in ((c["id"], to_m(*dense[c["id"]].T[::-1])) for c in corridors)}


def on_corridor(lat, lon):
    m = to_m([lat], [lon])
    for cid, T in corr_tree.items():
        if T.query(m)[0][0] <= 5000:
            return cid
    return None


def ctype(kind, ev_cov):
    if kind == "toll":
        return "dc60"
    return "dc30" if ev_cov >= 150 else "ac"


CONN = {"ac": 4, "dc30": 2, "dc60": 4, "dc120": 4}
sites = []
worst = gap.sort_values("gapScore", ascending=False).head(60)
geoms = g.set_index("id").geometry
for _, row in worst.iterrows():
    did, ev = row["id"], float(row.evs)
    poly = geoms[did]
    # demand: EVs spread over sampled points, concentrated near the centroid (urban-core assumption)
    cx, cy = dist.loc[did, ["lon", "lat"]]
    s = 0.25 * np.sqrt(dist.loc[did, "areaKm2"]) / 111
    raw = np.c_[rng.normal(cx, s, 600), rng.normal(cy, s, 600)]
    ok = gpd.GeoSeries(gpd.points_from_xy(raw[:, 0], raw[:, 1]), crs=4326).within(poly).to_numpy()
    D = raw[ok][:300]
    if len(D) < 20:
        continue
    dm = to_m(D[:, 1], D[:, 0])
    w = np.full(len(D), ev / len(D))
    w[ch_tree.query(dm)[0] <= RADIUS_KM * 1000] = 0  # already served by an existing charger
    cd = cand[cand.did == did]
    if len(cd) < 3:  # no grid/toll candidates: fall back to demand points themselves
        cd = pd.DataFrame({"lat": D[:40, 1], "lon": D[:40, 0], "kind": "demand"})
    cm = to_m(cd.lat, cd.lon)
    cover = cKDTree(dm).query_ball_point(cm, RADIUS_KM * 1000)
    used = set()
    for rank in range(1, 5):
        gains = [(-1 if i in used else w[idx].sum()) for i, idx in enumerate(cover)]
        i = int(np.argmax(gains))
        if gains[i] <= 0.5:
            break
        used.add(i)
        c = cd.iloc[i]
        cov = float(gains[i])
        w[cover[i]] = 0
        cid = on_corridor(c.lat, c.lon)
        kind = c.kind
        sites.append({
            "id": f"s-{len(sites) + 1:04d}", "districtId": did, "lat": round(float(c.lat), 5), "lon": round(float(c.lon), 5),
            "rank": rank, "chargerType": "dc60" if cid else ctype(kind, cov), "connectors": 0, "evsCovered": int(round(cov)),
            "nearestSubstationKm": round(float(near_sub_km(c.lat, c.lon)), 2), "corridor": cid,
            "reason": f"Covers about {int(round(cov))} EVs in {dist.loc[did, 'name']} not within {RADIUS_KM:g} km of any listed charger; "
                      + {"substation": "next to a substation, so grid connection is likely cheaper.", "toll": "at a toll plaza on a national highway with space and grid access.",
                         "demand": "no substation or toll plaza in the district, placed at the demand centre (grid distance shown)."}[kind],
        })

# corridor gap midpoints on the real path; snap to a fuel station within 300 m of the road and 2 km of the midpoint if one exists
for cr in corridors:
    P = to_m(*dense[cr["id"]].T[::-1])
    PT = corr_tree[cr["id"]]
    for sg in sorted(cr["gapSegments"], key=lambda s: -s["km"])[:3]:
        lon, lat = (np.array(sg["from"]) + np.array(sg["to"])) / 2
        # from/to are on the path; the straight midpoint can leave a bend, so use the path sample nearest to it
        k = PT.query(to_m([lat], [lon]))[1][0]
        lon, lat = dense[cr["id"]][k]
        on = "a point on the highway"
        mid = to_m([lat], [lon])[0]
        for fi in sorted(fuel_tree.query_ball_point(mid, 2000), key=lambda i: np.linalg.norm(fuel_tree.data[i] - mid)):
            if PT.query(fuel_tree.data[fi])[0] <= 300:
                lat, lon = float(fuel.lat[fi]), float(fuel.lon[fi])
                on = "an existing fuel station" + (f" ({fuel.name[fi]})" if isinstance(fuel.name[fi], str) and fuel.name[fi].strip() else "")
                break
        did = (district_of([lat], [lon]) or [None])[0]
        if did is None or did not in dist.index:
            continue
        n_here = sum(s["districtId"] == did for s in sites)
        share = min(1.0, np.pi * (HWY_KM / 2) ** 2 / dist.loc[did, "areaKm2"])
        t = "dc120" if sg["km"] > 3 * HWY_KM else "dc60"
        sites.append({
            "id": f"s-{len(sites) + 1:04d}", "districtId": did, "lat": round(float(lat), 5), "lon": round(float(lon), 5),
            "rank": n_here + 1, "chargerType": t, "connectors": 0,
            "evsCovered": int(round(float(evs.get(did, 0)) * share)), "nearestSubstationKm": round(float(near_sub_km(lat, lon)), 2),
            "corridor": cr["id"],
            "reason": f"On {cr['name']}, at {on}, near the middle of a {sg['km']:g} km stretch with no listed charger within 5 km (norm: one every {HWY_KM:g} km). Highway geometry is measured (MORTH, June 2022).",
        })
for s in sites:
    s["connectors"] = CONN[s["chargerType"]]

# ---------- write ----------
json.dump(corridors, open(OUT / "corridors.json", "w"), separators=(",", ":"))
json.dump(sites, open(OUT / "sites.json", "w"), separators=(",", ":"))
A = lambda i, l, v, s, k: {"id": i, "label": l, "value": v, "source": s, "kind": k}
json.dump([
    A("corridor-path", "Corridor paths are measured geometry", f"Existing segments of each NH number from the MORTH/GatiShakti national highway layer (dated June 2022), sampled every 2 km and joined by a minimum spanning tree across holes of up to 150 km; the corridor is the tree's longest path. Length is measured on the full path; the drawn path is simplified to about 200 m. Top {len(corridors)}: the longest NH numbers plus major trunk routes. Segments under construction or proposed are excluded; the file has holes, so bridged stretches are straight lines. Lengths run about 5 to 12% below published figures for NH 44, 48 and 27.", "data/raw/roads/morth_national_highways.parquet; scripts/pipeline/04_corridors.py", "measured"),
    A("corridor-buffer", "Charger counts as 'near' a corridor", "Within 5 km of the highway path (a 0.5 km sampled path, so distances are good to about 0.25 km)", "scripts/pipeline/04_corridors.py", "assumed"),
    A("corridor-spacing", "Highway charger spacing norm", f"{HWY_KM:g} km. The guideline reads 'on both sides of highways'; a station within the buffer on either side is counted as serving the corridor, so the add-count is per corridor, not per carriageway side.", src_hwy, "norm"),
    A("corridor-to-add", "Stations to add on a corridor", "Sum over gaps longer than the norm of ceil(gap/norm) - 1", "scripts/pipeline/04_corridors.py", "modelled"),
    A("site-radius", "Site service radius", f"{RADIUS_KM:g} km (half of the {URBAN_KM:g} km urban grid cell)", src_urb, "norm"),
    A("site-demand", "Site demand points", "District EVs spread over up to 300 random points drawn around the district centroid (sd = quarter of the district's linear size); points within the radius of a listed charger are treated as served", "scripts/pipeline/04_corridors.py", "assumed"),
    A("site-candidates", "Site candidates", "OSM substation locations (grid proximity as a proxy for spare capacity) and toll plazas, inside the district; greedy maximal coverage, up to 4 sites in each of the 60 districts with the worst gap score; plus, for the 3 longest gaps on each corridor, the highway point nearest the midpoint, moved to an OSM fuel station within 300 m of the road and 2 km of the midpoint when one exists", "data/raw/grid/osm_substations.json; morth_toll_plazas.parquet; OSM fuel stations in data/data.csv", "modelled"),
    A("site-type", "Charger type and connectors", "Corridor sites dc60 (dc120 where the gap exceeds 3x the norm); urban sites dc30 if they cover 150 or more EVs, else ac; connectors ac 4, dc30 2, dc60 4, dc120 4", "scripts/pipeline/04_corridors.py", "assumed"),
], open(OUT / "assumptions_corridors.json", "w"), indent=1)

# ---------- self-check ----------
size = (OUT / "sites.json").stat().st_size
csz = (OUT / "corridors.json").stat().st_size
L = {c["id"]: c["lengthKm"] for c in corridors}
assert csz < 1_000_000, csz
BRIDGED = {c[0]: round(c[3]["bridged_km"]) for c in pick}
print("lengths vs known (NH44 3700-4100, NH48 ~2800, NH27 ~3500):", {k: L.get(k) for k in ("nh-44", "nh-48", "nh-27")}, "bridged km", BRIDGED)
assert 15 <= len(corridors) <= 20 and all(c["lengthKm"] > 0 and c["maxGapKm"] <= c["lengthKm"] + 1e-6 for c in corridors)
assert all(s["districtId"] in set(base.id) and 6 < s["lat"] < 38 for s in sites) and len({s["id"] for s in sites}) == len(sites)
assert 0 < len(sites) and size < 1_000_000, size
w = corridors[0]
print({k: LENGTHS[k] for k in list(LENGTHS)[:20]}, {k: v for k, v in L.items()})
print(f"corridors.json {csz / 1e3:.0f} KB; {len(corridors)} corridors; worst {w['name']} ({w['stationsToAdd']} to add, max gap {w['maxGapKm']} km); {len(sites)} sites, {size / 1e3:.0f} KB; spacing norm {HWY_KM}")

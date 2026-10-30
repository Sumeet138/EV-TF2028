"""Gap analysis: allocate VAHAN state EVs to districts (MODELLED), measure charger coverage, score the gap.
Writes districts_gap.csv, states.csv, assumptions_gap.json in data/processed/."""
import json
import re
from difflib import SequenceMatcher

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from scipy.spatial import cKDTree

from common import AREA_CRS, DATA_CSV, GEOJSON, OUT, canon_state, norm

OFFICIAL, OFFICIAL_ASOF = 52718, "2026-07-21"  # Lok Sabha Q.453, BHEL portal (reports/India EV charger data and assumptions.md)
COV_FLOOR = 0.1  # never divide found chargers by less than 0.1: a state with a handful of found stations must not be scaled up 50x
NORM_URBAN_KM, NORM_HWY_KM = 3, 25
NORM_SRC = ("MoP Guidelines for Installation and Operation of Public Charging Infrastructure (2022, amended 2023), Location of Public Charging Stations: "
            "\"At least one Charging Station shall be available in a grid of 3 Km X 3 Km. Further, one Charging Station shall be set up "
            "at every 25 Km on both sides of highways/roads.\"")

base = pd.read_csv(OUT / "districts_base.csv")
ch = pd.read_csv(OUT / "chargers_clean.csv")

# ---------- VAHAN: EV = BOV + pure EV, per canonical state ----------
v = pd.read_csv(DATA_CSV, low_memory=False)
v = v[v.layer == "ev_registrations"].copy()
v["st"] = v.state.map(canon_state)
assert v.st.notna().all(), v[v.st.isna()].state.unique()
ev = v[v.metric.isin(["registrations_ELECTRIC(BOV)", "registrations_PURE EV"])].groupby(["st", "year"]).value.sum().unstack()
tot = v[v.metric == "registrations_TOTAL"].groupby(["st", "year"]).value.sum().unstack()
YEARS = [str(y) for y in range(2014, 2027)]

# ---------- RTO registrations (2022-2026 sums of BOV + pure EV) ----------
rt = pd.read_csv(DATA_CSV, low_memory=False)
rt = rt[rt.layer == "ev_registrations_rto"].copy()
assert not (rt.detail == "HR207").any() and not rt.name.str.contains("HR207", na=False).any(), "HR207 is an all-India dealer total and must stay excluded"
assert rt.detail.nunique() == 1377, rt.detail.nunique()
rt["st"] = rt.state.map(canon_state)
assert rt.st.notna().all(), rt[rt.st.isna()].state.unique()
rt = rt[rt.metric.isin(["registrations_ELECTRIC(BOV)", "registrations_PURE EV"])]
rto = rt.groupby(["st", "detail", "name"]).value.sum().reset_index().rename(columns={"detail": "rto", "name": "rtoName", "value": "evs"})
RTO_WORDS = re.compile(r"\b(RTO|ARTO|DTO|SRTO|RTA|RLA|SDM|UO|UNIT|OFFICE|MVI|JTO|BTO|TRANSPORT)\b", re.I)


# RTO names that are zones, renamed towns or old spellings of a 2021 district; applied first, only when the target exists in the state
ALIAS = {"BENGALURU": "BANGALORE", "ELECTRONICCITY": "BANGALORE", "KRISHNARAJAPURAM": "BANGALORE", "YALAHANKA": "BANGALORE", "PIMPRICHINCHWAD": "PUNE",
         "NOIDA": "GAUTAMBUDDHANAGAR", "BHUBANESWAR": "KHORDHA", "KATAKA": "CUTTACK", "SAMBHAJINAGAR": "AURANGABAD", "AHILYANAGAR": "AHMEDNAGAR",
         "RAIBAREILLY": "RAEBARELI", "TRIVANDRUM": "THIRUVANANTHAPURAM", "BELAGAVI": "BELGAUM"}


def match_rto(name, cands):
    """cands: {norm district name: districtId} inside the RTO's state -> (districtId, method, score)."""
    n = norm(RTO_WORDS.sub(" ", re.sub(r"[\(\[].*?[\)\]]", "", name)))
    if n in cands:
        return cands[n], "exact", 1.0
    for k, v in ALIAS.items():
        if k in n and v in cands:
            return cands[v], "alias", 1.0
    sub = [(len(min(n, d, key=len)) / len(max(n, d, key=len)), i) for d, i in cands.items() if min(len(n), len(d)) >= 4 and (d in n or n in d)]
    if sub:
        sc, i = max(sub)
        return i, "contains", round(sc, 2)
    sc, i = max(((SequenceMatcher(None, n, d).ratio(), i) for d, i in cands.items()), default=(0, None))
    return (i, "fuzzy", round(sc, 2)) if sc >= 0.8 else (None, "none", round(sc, 2))


by_state = {st: {norm(n): i for n, i in zip(d.name, d.id)} for st, d in base.groupby("state")}
xw = [match_rto(r.rtoName, by_state.get(r.st, {})) for r in rto.itertuples()]
rto["districtId"], rto["method"], rto["score"] = zip(*xw)
rto[["rto", "st", "districtId", "method", "score"]].rename(columns={"rto": "rto", "st": "state"}).to_csv(OUT / "rto_district_crosswalk.csv", index=False)
rto["hit"] = rto.districtId.notna()
rto_share = rto.groupby("st").apply(lambda d: d.evs[d.hit].sum() / d.evs.sum())  # share of each state's RTO EVs matched to a district
rto_by_dist = rto[rto.hit].groupby("districtId").evs.sum()


def lrm(x, total):
    """Largest-remainder rounding so integers sum to `total` exactly."""
    x = np.asarray(x, float) * total / x.sum() if x.sum() > 0 else np.full(len(x), total / len(x))
    f = np.floor(x).astype(np.int64)
    k = int(round(total)) - f.sum()
    f[np.argsort(-(x - f))[:k]] += 1
    return f


# ---------- 1. allocate (MODELLED) ----------
b = base.copy()
for c in ["carHouseholds", "twoWheelerHouseholds", "powerParityTotal", "nightlights"]:
    b[c] = b[c].fillna(0)
b["hh2"] = b.twoWheelerHouseholds + b.carHouseholds
W = {"hh2": .4, "powerParityTotal": .3, "nightlights": .3}
w = sum(wt * b.groupby("state")[c].transform(lambda s: s / s.sum() if s.sum() > 0 else 1 / len(s)) for c, wt in W.items())
b["w"] = w
b["evs"] = 0
b["rw"] = b.id.map(rto_by_dist).fillna(0)
ybyd = {i: {} for i in b.index}
for st, idx in b.groupby("state").groups.items():
    ww = b.loc[idx, "w"].values
    ww = ww / ww.sum()
    rw, m = b.loc[idx, "rw"].values, rto_share.get(st, 0.0)
    if rw.sum() > 0:  # matched share of EVs follows RTO registrations, the unmatched rest follows the proxy
        ww = m * rw / rw.sum() + (1 - m) * ww
    b.loc[idx, "evs"] = lrm(ww, ev.loc[st, "cumulative"])
    for y in YEARS:
        a = lrm(ww, ev.loc[st, y] if y in ev.columns else 0)
        for i, val in zip(idx, a):
            ybyd[i][y] = int(val)
b["evsByYear"] = [json.dumps(ybyd[i]) for i in b.index]

# ---------- 2. coverage factor per state: found / official state count (scaled so the states sum to the national total) ----------
n_found = len(ch)
o = pd.read_csv(DATA_CSV, low_memory=False)
o = o[o.layer == "charger_official"].copy()
o["st"] = o.state.map(lambda s: canon_state(s) or ("Andaman and Nicobar Islands" if s.startswith("ANDAMAN") else None))
assert o.st.notna().all(), o[o.st.isna()].state.unique()
op = o.pivot_table(index="st", columns="metric", values="value", aggfunc="sum")
assert len(op) == 36
bhel = op.bhel_2026_07_29  # 29 Jul 2026 annexure: only 16 states found in press
k = (OFFICIAL - bhel.sum()) / op.total_2025_12_16[bhel.isna()].sum()  # remaining national total spread over the other states by their Dec 2025 shares
official_st = bhel.fillna(op.total_2025_12_16 * k)
assert abs(official_st.sum() - OFFICIAL) < 1e-6
found_st = b.groupby("state").chargers.sum().reindex(official_st.index)
raw_ratio = found_st / official_st
fac = raw_ratio.clip(COV_FLOOR, 1.0)
factor = min(1.0, n_found / OFFICIAL)  # national, for the report
b["cf"] = b.state.map(fac)
b["chargersAdjusted"] = (b.chargers / b.cf).round(1)
b["evsPerCharger"] = np.where(b.chargers > 0, b.evs / b.chargersAdjusted.replace(0, np.nan), np.nan).round(1)

# ---------- 3. coverage km from area-uniform sample points to nearest charger ----------
g = gpd.read_file(GEOJSON).to_crs(AREA_CRS)
assert len(g) == len(b) and (g.shapeName.values == b.name.values).all(), "geojson order must match base"
pts = gpd.GeoSeries(gpd.points_from_xy(ch.lon, ch.lat), crs=4326).to_crs(AREA_CRS)
tree = cKDTree(np.c_[pts.x, pts.y])
cov, w3 = [], []
for geom, a in zip(g.geometry, b.areaKm2):
    step = max(1000.0, np.sqrt(a * 1e6 / 300))  # ~300 points, never finer than 1 km
    x0, y0, x1, y1 = geom.bounds
    gx, gy = np.meshgrid(np.arange(x0 + step / 2, x1, step), np.arange(y0 + step / 2, y1, step))
    gx, gy = gx.ravel(), gy.ravel()
    m = shapely.contains_xy(geom, gx, gy)
    if not m.any():
        p = geom.representative_point()
        gx, gy = np.array([p.x]), np.array([p.y])
    else:
        gx, gy = gx[m], gy[m]
    d = tree.query(np.c_[gx, gy])[0] / 1000
    cov.append(d.mean())
    w3.append((d <= NORM_URBAN_KM).mean())
b["coverageKm"] = np.round(cov, 2)
b["within3kmShare"] = np.round(w3, 3)

# ---------- 4. gap score ----------
ok = b.population.notna()
pr = lambda s: s.rank(pct=True, method="average")
epc_raw = (b.evs / b.chargersAdjusted.replace(0, np.nan)).fillna(np.inf)  # no chargers seen = worst
unmet = b.evs * (1 - b.within3kmShare)
p = pd.DataFrame({"epc": pr(epc_raw[ok]), "cov": pr(b.coverageKm[ok]), "unmet": pr(unmet[ok])}).reindex(b.index)
P = {"epc": .4, "cov": .3, "unmet": .3}
b["gapScore"] = (100 * sum(P[k] * p[k] for k in P)).round(1)
b["gapBand"] = pd.Series(pd.qcut(b.gapScore.rank(method="first"), 5, labels=[1, 2, 3, 4, 5]), index=b.index).astype("Int64")
med_epc = b.evsPerCharger.median()


def drivers(i):
    r = b.loc[i]
    cand = {
        "epc": f"{r.evs:,.0f} modelled EVs and no chargers found" if r.chargers == 0 else
               f"{r.evsPerCharger:,.0f} modelled EVs per estimated charger (district median {med_epc:,.0f})",
        "cov": f"On average {r.coverageKm:.1f} km to the nearest charger; {r.within3kmShare * 100:.0f}% of area within 3 km",
        "unmet": f"About {unmet[i]:,.0f} modelled EVs sit outside the 3 km norm",
    }
    ks = sorted(P, key=lambda k: -P[k] * p.loc[i, k])
    keep = [k for k in ks if p.loc[i, k] >= .5] or ks[:1]
    return json.dumps([cand[k] for k in keep[:3]])


b["gapDrivers"] = [drivers(i) if ok[i] else json.dumps(["No Census population matched, so no gap score"]) for i in b.index]
b["evsSource"] = np.where(b.rw > 0, "rto", "proxy")
b["confidence"] = np.where(~ok | (b.match_quality == "none"), "low",
                           np.where((b.match_quality == "exact") & (b.chargers >= 3), "high", "medium"))
# raise medium -> high only when EVs rest on a matched RTO in a state where >= 80% of RTO EVs matched, the polygon is exact/crosswalk, and chargers >= 3
up = (b.confidence == "medium") & (b.evsSource == "rto") & b.state.map(rto_share).ge(0.8) & b.match_quality.isin(["exact", "crosswalk"]) & (b.chargers >= 3)
b.loc[up, "confidence"] = "high"

dcols = ["id", "evs", "evsSource", "evsByYear", "chargersAdjusted", "evsPerCharger", "coverageKm", "within3kmShare", "gapScore", "gapBand", "gapDrivers", "confidence"]
b[dcols].to_csv(OUT / "districts_gap.csv", index=False)

# ---------- states ----------
rows = []
for st, d in b.groupby("state"):
    s = d[d.gapScore.notna()]
    sc = np.average(s.gapScore, weights=s.evs + 1) if len(s) else np.nan
    chg = int(d.chargers.sum())
    rows.append({
        "name": st, "evs": int(ev.loc[st, "cumulative"]),
        "evsByYear": json.dumps({y: int(ev.loc[st, y]) for y in YEARS if y in ev.columns}),
        "evShare2025": round(ev.loc[st, "2025"] / tot.loc[st, "2025"], 4),
        "chargers": chg, "chargersAdjusted": round(chg / fac[st], 1),
        "evsPerCharger": round(ev.loc[st, "cumulative"] / (chg / fac[st]), 1) if chg else np.nan,
        "coverageFactor": round(fac[st], 4), "gapScore": round(sc, 1), "districts": len(d)})
S = pd.DataFrame(rows)
S["gapBand"] = pd.qcut(S.gapScore.rank(method="first"), 5, labels=[1, 2, 3, 4, 5]).astype(int)
S[["name", "evs", "evsByYear", "evShare2025", "chargers", "chargersAdjusted", "evsPerCharger", "coverageFactor", "gapScore", "gapBand", "districts"]].to_csv(OUT / "states.csv", index=False)

# ---------- assumptions ----------
A = lambda id, label, value, source, kind: {"id": id, "label": label, "value": value, "source": source, "kind": kind}
assumptions = [
    A("vahan-ev", "State EV registrations", "ELECTRIC(BOV) + PURE EV, cumulative and by year", "VAHAN4 dashboard rows in data/data.csv", "measured"),
    A("ev-alloc", "District EV counts", "State VAHAN total split in two parts. Share m = matched RTO EVs / all RTO EVs in the state (2022-2026) follows each district's matched RTO registrations; the rest (1 - m) follows 0.4 x (2W + car households) + 0.3 x power-parity households + 0.3 x VIIRS nightlights. Districts with no matched RTO get evsSource 'proxy'; state sums equal VAHAN exactly",
      "India Data Portal VAHAN by RTO (data/raw/vahan_rto/fuel.csv, HR207 dealer total excluded); proxy shares from Census 2011 and VIIRS 2024", "modelled"),
    A("rto-crosswalk", "RTO to district match", f"{len(rto)} RTOs matched to 2021 districts by normalised name inside the state (exact, then containment, then fuzzy >= 0.8); {rto.hit.mean() * 100:.0f}% of RTOs and {rto.evs[rto.hit].sum() / rto.evs.sum() * 100:.0f}% of RTO EVs matched. Written to rto_district_crosswalk.csv",
      "Name matching only; no official RTO-to-district list was used", "assumed"),
    A("rto-jurisdiction", "RTO jurisdiction is not a district boundary", "An RTO can cover part of a district or several districts, and metro RTOs (Delhi, Mumbai, Bengaluru, Chennai) are often named for zones, not districts. Where several RTOs match one district their EVs add; a district with an unmatched sibling RTO is under-counted and the proxy only partly corrects it",
      "RTO series start in 2022, so shares reflect recent registrations, not the earlier stock", "assumed"),
    A("registration-vs-charging", "Registration place is not charging place", "A vehicle is counted where it is registered (often a dealer or fleet owner's city), not where it charges or runs. District EVs therefore show registration, not charging demand",
      "VAHAN registration data", "assumed"),
    A("official-total", "Official public charging stations", f"{OFFICIAL:,} as of {OFFICIAL_ASOF}", "Lok Sabha Q.453 (BHEL portal), July 2026. The jump from 29,151 (Dec 2025) most likely reflects a counting-system change, not construction", "measured"),
    A("coverage-factor", "Charger coverage factor per state", f"coverageFactor = min(1, stations found / official state count), floored at {COV_FLOOR}. Official state count = the 29 Jul 2026 annexure for the 16 states where press confirms it (41,238), and the Dec 2025 state total scaled by {k:.3f} for the other 20 so the states sum to {OFFICIAL:,}. Found stations: {n_found:,} (national {factor:.3f}). Ratios above 1 are capped at 1 ({int((raw_ratio > 1).sum())} states: found data from BEE Dec 2024 / OSM exceeds the older state count); the BEE snapshot is Dec 2024 and may hold closed stations, which overstates coverage",
      "Parliament replies and PIB state counts in data/data.csv; BHEL and BEE universes differ and the series do not nest, so this is a rough scaling", "assumed"),
    A("urban-norm", "Urban spacing norm", "1 charging station per 3 km x 3 km grid", NORM_SRC, "norm"),
    A("hwy-norm", "Highway spacing norm", "1 charging station every 25 km on both sides of highways", NORM_SRC, "norm"),
    A("coverage-km", "Coverage distance", "Mean distance from ~300 area-uniform sample points per district to the nearest found charger anywhere in India; within3kmShare = share of points within 3 km",
      "Not population-weighted; points over uninhabited land count equally", "modelled"),
    A("gap-score", "Gap score", "100 x (0.4 pct-rank EVs per adjusted charger + 0.3 pct-rank coverage km + 0.3 pct-rank modelled EVs outside 3 km); no chargers = worst rank; bands are quintiles",
      "Relative ranking across districts, not an absolute shortfall", "modelled"),
]
(OUT / "assumptions_gap.json").write_text(json.dumps({"assumptions": assumptions, "norms": {"urbanSpacingKm": NORM_URBAN_KM, "highwaySpacingKm": NORM_HWY_KM, "source": NORM_SRC}}, indent=1))

# ---------- self-check ----------
d = pd.read_csv(OUT / "districts_gap.csv")
assert list(d.id) == list(base.id)
for st, grp in b.groupby("state"):
    assert grp.evs.sum() == int(ev.loc[st, "cumulative"]), st
    for y in YEARS:
        assert sum(ybyd[i][y] for i in grp.index) == int(ev.loc[st, y]), (st, y)
assert b.evs.sum() == ev.cumulative.sum() and len(S) == 36
print(f"RTOs matched {rto.hit.sum()}/{len(rto)}; EVs matched nationally {rto.evs[rto.hit].sum() / rto.evs.sum():.3f}; per state min/median/max {rto_share.min():.2f}/{rto_share.median():.2f}/{rto_share.max():.2f}")
print("state EV match share:", rto_share.round(2).sort_values().to_dict())
print("methods:", rto.method.value_counts().to_dict(), "evsSource:", b.evsSource.value_counts().to_dict(), "confidence:", b.confidence.value_counts().to_dict())
print("coverage by state:", fac.round(2).sort_values().to_dict(), "capped at 1:", list(fac.index[raw_ratio > 1]))
print(f"factor {factor:.3f}; scored {ok.sum()}/{len(b)}; EVs {b.evs.sum():,}")
print(b[ok].nlargest(5, "gapScore")[["id", "gapScore", "evs", "chargers", "coverageKm"]].to_string())

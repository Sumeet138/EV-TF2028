"""National logistic fit -> district EV stock -> energy -> chargers. Same formula as client/src/lib/estimator.ts."""
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import least_squares

sys.path.insert(0, str(Path(__file__).parent))
from common import DATA_CSV, OUT, canon_state

YEARS = list(range(2025, 2036))
FY = ["2027", "2030", "2035"]
T = ["2W", "3W", "4W"]
# ---- constants shared with estimator.ts (keep in sync; estimator.check.ts proves it) ----
HOURS = 16  # operating hours per day
POWER = {"ac": 7.4, "dc30": 30, "dc60": 60, "dc120": 120}
RURAL_MIX = {"ac": 0.45, "dc30": 0.40, "dc60": 0.12, "dc120": 0.03}  # share of public energy
URBAN_DENSITY = 5000  # people per km2 of built-up area
CPS = 2.1  # connectors per station
SPACING_KM = 3.0
DEFAULTS = {
    "kwhPer100km": {"2W": 3.5, "3W": 8.0, "4W": 15.0},
    "fleetMix": {"2W": 0.60, "3W": 0.30, "4W": 0.10},
    "kmPerDay": {"2W": 30, "3W": 80, "4W": 40},
    "publicShare": 0.15,  # midpoint of 10-20% (Kazam/AEEE: home is 80-90% of energy)
    "utilisation": 0.15,  # energy-based, share of 16h at rated power, REACHED IN 2035; earlier years ramp, see ramp()
    "typeMix": {"ac": 0.35, "dc30": 0.35, "dc60": 0.20, "dc120": 0.10},
}
KS = {"low": 50e6, "base": 100e6, "high": 200e6}  # assumed saturation EV stock


def ramp(year):  # fraction of the 2035 utilisation reached in `year`: 0.30 in 2025 (~4.5% on 16h = ~3% on 24h, mid of India's 1-5%), linear to 1.0 in 2035
    return 0.3 + 0.07 * (year - 2025)


def r_(x):  # round half up, identical in JS
    return int(math.floor(x + 0.5))


def estimate(evs, urban_share, pop, area, adj, year, mult=1.0, o=None):
    d = {**DEFAULTS, **(o or {})}
    evs = evs * mult
    kwh = sum(d["fleetMix"][t] * d["kmPerDay"][t] * d["kwhPer100km"][t] / 100 for t in T)
    energy = evs * kwh * d["publicShare"]  # kWh/day at public chargers
    u = urban_share
    cnt = {}
    for k in POWER:
        share = u * d["typeMix"][k] + (1 - u) * RURAL_MIX[k]
        cnt[k] = energy * share / (POWER[k] * HOURS * d["utilisation"] * ramp(year))
    urban_area = min(area, pop * u / URBAN_DENSITY)
    floor = urban_area / (2.6 * SPACING_KM ** 2)  # hex cover by circles of radius SPACING_KM
    gap = floor - sum(cnt.values())
    if gap > 0:
        cnt["ac"] += gap / 2
        cnt["dc30"] += gap / 2
    by = {k: r_(v) for k, v in cnt.items()}
    req = sum(by.values())
    return dict(evs=r_(evs), chargersRequired=req, chargersToAdd=max(0, r_(req - adj * CPS)),
                byType=by, demandMWhPerDay=r_(energy) / 1000)


def main():
    d = pd.read_csv(DATA_CSV, low_memory=False)
    e = d[(d.layer == "ev_registrations") & d.metric.isin(["registrations_ELECTRIC(BOV)", "registrations_PURE EV"])]
    y = pd.to_numeric(e.year, errors="coerce")
    m = (y >= 2014) & (y <= 2025)
    ann = e[m].assign(y=y[m].astype(int)).groupby("y").value.sum()
    stock = ann.cumsum()  # pre-2014 EVs ignored (negligible)
    yrs = stock.index.values.astype(float)
    # ponytail: fit on log stock with K fixed per scenario, since K is unidentifiable from the pre-inflection data
    series, fits = {}, {}
    # ponytail: fit the logistic's annual flow (its derivative) to registrations, K fixed per scenario since K is
    # not identifiable before the inflection; stock = measured 2025 stock + cumulated modelled flow.
    flow = ann.values / 1e6
    for s, K in KS.items():
        def f(p):
            z = np.exp(-p[0] * (yrs - p[1]))
            return K / 1e6 * p[0] * z / (1 + z) ** 2 - flow
        p = least_squares(f, [0.3, 2035], bounds=([0.05, 2020], [2.0, 2080])).x
        fits[s] = p
        z = lambda t: math.exp(-p[0] * (t - p[1]))
        fl = lambda t: K * p[0] * z(t) / (1 + z(t)) ** 2
        acc, ser = stock.loc[2025], [{"year": 2025, "evs": r_(stock.loc[2025])}]
        for t in YEARS[1:]:
            acc += fl(t)
            ser.append({"year": t, "evs": r_(acc)})
        series[s] = ser
    nat = {s: {x["year"]: x["evs"] for x in series[s]} for s in series}

    g = pd.read_csv(OUT / "districts_gap.csv")
    b = pd.read_csv(OUT / "districts_base.csv")[["id", "state", "areaKm2", "population", "urbanShare"]]
    x = g.merge(b, on="id")
    x["y25"] = x.evsByYear.map(lambda s: json.loads(s).get("2025", 0))
    x["evs"] = x.evs.astype(float)
    x[["population", "urbanShare"]] = x[["population", "urbanShare"]].fillna(0)  # 3 districts lack census: no spacing floor, share from EVs
    st = x.groupby("state")[["evs", "y25"]].sum()
    mom = ((st.y25 / st.y25.sum()) / (st.evs / st.evs.sum())).clip(0.5, 2).fillna(1)
    stock25 = x.evs.sum()
    x["popshare"] = (x.population / x.groupby("state").population.transform("sum")).fillna(0)
    x["inshare"] = x.evs / x.groupby("state").evs.transform("sum").replace(0, np.nan)
    x["inshare"] = x.inshare.fillna(x.popshare)
    st_share0 = st.evs / stock25

    def dist_evs(yr, scen):
        w = min(1, (yr - 2025) / 5)  # state momentum fades in over 5y
        sh = st_share0 * mom ** w
        sh = sh / sh.sum()
        wd = min(1, (yr - 2025) / 10) * 0.5  # districts drift half-way to population share by 2035
        sin = (1 - wd) * x.inshare + wd * x.popshare
        return nat[scen][yr] * x.state.map(sh) * sin

    out = []
    base_mult = {}
    ev_tab = {y: dist_evs(int(y), "base").round().astype(int).values for y in FY}
    for i, row in enumerate(x.itertuples()):
        fc = {}
        for y in FY:
            fc[y] = estimate(float(ev_tab[y][i]), row.urbanShare, row.population, row.areaKm2, row.chargersAdjusted, int(y))
        out.append({"id": row.id, "forecast": json.dumps(fc, separators=(",", ":"))})
    pd.DataFrame(out).to_csv(OUT / "districts_forecast.csv", index=False)

    # sensitivity: same districts and base EV path, demand inputs only (low = less public charging / busier chargers)
    CASES = {"low": {"publicShare": 0.10, "utilisation": 0.21}, "base": {}, "high": {"publicShare": 0.20, "utilisation": 0.075}}
    sens = {c: {y: sum(estimate(float(ev_tab[y][i]), r.urbanShare, r.population, r.areaKm2, r.chargersAdjusted, int(y), o=o)["chargersToAdd"]
                       for i, r in enumerate(x.itertuples())) for y in FY} for c, o in CASES.items()}
    assert all(sens["low"][y] <= sens["base"][y] <= sens["high"][y] for y in FY), sens
    print("sensitivity", sens)
    scen = {"series": series, "defaults": DEFAULTS, "sensitivity": sens}
    (OUT / "scenarios.json").write_text(json.dumps(scen, indent=1))
    # national roll-up (base)
    tot = {y: sum(json.loads(r["forecast"])[y]["chargersToAdd"] for r in out) for y in FY}
    req = {y: sum(json.loads(r["forecast"])[y]["chargersRequired"] for r in out) for y in FY}
    exist = x.chargersAdjusted.sum() * CPS
    ratio = {y: round(nat["base"][int(y)] / req[y], 1) for y in FY}
    print("chargersToAdd", tot, "required", req, "existing(conn)", round(exist), "EVs per charger", ratio)
    print("stock", stock.loc[2025], {s: series[s][-1]["evs"] for s in series}, {s: fits[s].round(3).tolist() for s in fits})

    A = lambda i, l, v, s, k: dict(id=i, label=l, value=v, source=s, kind=k)
    asm = [
        A("fc_series", "EV stock history 2014-2025", f"{int(stock.loc[2025]):,} EVs end-2025 (BOV + pure EV)", "VAHAN4 dashboard, data/data.csv. 2026 excluded: partial year (data ends mid-2026). Pre-2014 stock ignored.", "measured"),
        A("fc_logistic", "National curve", "Logistic S=K/(1+exp(-r(t-t0))), r,t0 least-squares on log stock, anchored to 2025", f"scipy fit; r={fits['base'][0]:.2f}, t0={fits['base'][1]:.1f} (base)", "modelled"),
        A("fc_k", "Saturation stock K low/base/high", "50M / 100M / 200M EVs", "Not identifiable from data before the inflection. No public policy target is in our data, so none is used as an anchor.", "assumed"),
        A("fc_district", "District allocation", "State share drifts by 2025 momentum over 5y; districts drift half-way to state population share by 2035", "Assumed convergence so early-adopter districts do not compound forever.", "assumed"),
        A("fc_mix", "Fleet mix 2W/3W/4W", "60% / 30% / 10%", "VAHAN extract has no class split. Rough read of Indian EV registrations (2W and e-3W dominate).", "assumed"),
        A("fc_kwh", "kWh per 100 km 2W/3W/4W", "3.5 / 8 / 15", "Typical e-scooter, e-rickshaw/L5, small e-car consumption.", "assumed"),
        A("fc_km", "km per day 2W/3W/4W", "30 / 80 / 40", "Commuter 2W, commercial 3W, private 4W.", "assumed"),
        A("fc_public", "Public charging share of energy", "15% (range 10-20%)", "Kazam/AEEE (80,000+ home installs): home is 80-90% of EV energy, so 10-20% is everything else, incl. workplace, depot, swap. 15% = midpoint; 20% is a ceiling. CEA FY26 metered energy implies 4-15% (report back-test, ours), and ~45% of buyers lack home charging, so no lower. Not ramped: no evidence on its trend.", "assumed"),
        A("fc_util", "Utilisation (energy-based, % of 16h at rated power)", "15% in 2035, ramping linearly from 30% of that in 2025: 4.5% (2025), 6.6% (2027), 9.8% (2030), 15% (2035)", "15% is a mature-network target (= 10% on 24h; IEA projects 15% for Europe by 2035, time-based). India today is 1-5% on 24h (SBI 1-3%, S&P ~5%, FICCI <2%; relayed by EMobility+/Outlook Business, originals unread) = 1.5-7.5% on 16h; 4.5% = ~3% on 24h, mid-range. Linear ramp is assumed; no source gives the path.", "assumed"),
        A("fc_sens", "Sensitivity on chargers to add", "low: public 10%, utilisation 21% (2035 value) | high: public 20%, utilisation 7.5% | EV path and all else = base; ramp applied to each", "Bounds from sources: public 10-20% (Kazam/AEEE residual); utilisation 21% = ChargeZone 14% restated on 16h, 7.5% = 5% on 24h (S&P, today's ceiling held flat). Computed by re-running every district; the report's 4-46 lakh is a cross-check, not an input. EV scenarios (K) are separate, not mixed in.", "modelled"),
        A("fc_ev_recon", "Registered EVs: Lok Sabha vs VAHAN sum", "Lok Sabha 1,00,23,396 (26 Jul 2026) vs our 1.08 crore: not a conflict. Our end-2025 stock 79.4 lakh + Jan-Jul 2026 RTO registrations 18.8 lakh = ~98.2 lakh at 31 Jul (~97.4 lakh at 26 Jul), within 2-3% of official.", "data/data.csv VAHAN4 (BOV + pure EV; 2026 total 28.4 lakh runs to ~Oct 2026) and data/raw/vahan_rto/fuel.csv (HR207 excluded). The 1.08 crore is a later date, ~Aug-Oct 2026 adds ~9.6 lakh. Residual 2-3% unexplained (official may count other categories or differ in date); VAHAN not changed. Forecast is anchored on end-2025, so unaffected.", "measured"),
        A("fc_hours", "Operating hours per day", f"{HOURS}", "Most sites are not 24h.", "assumed"),
        A("fc_power", "Rated power AC / DC30 / DC60 / DC120", "7.4 / 30 / 60 / 120 kW", "Nominal ratings of common unit classes.", "assumed"),
        A("fc_typemix", "Energy share by type, urban", "AC 35 / DC30 35 / DC60 20 / DC120 10 %", "Dense urban favours fast DC for turnover.", "assumed"),
        A("fc_rural", "Energy share by type, rural", "AC 45 / DC30 40 / DC60 12 / DC120 3 %", "Lower-power units, lower grid demand.", "assumed"),
        A("fc_floor", "Spacing floor", f"One charger per 2.6 x {SPACING_KM:g}^2 km2 of built-up area; built-up = urban population / {URBAN_DENSITY}/km2", "Urban spacing norm (MoP 2025, see assumptions_gap.json); density assumed. Floor chargers split AC / DC30.", "assumed"),
        A("fc_cps", "Connectors per station", f"{CPS}", "Mean of 'connectors' where reported in data/data.csv (2,572 stations: 2.07). Converts existing stations to charge points.", "measured"),
    ]
    (OUT / "assumptions_forecast.json").write_text(json.dumps(asm, indent=1))


if __name__ == "__main__":
    main()

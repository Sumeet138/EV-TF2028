"""Unify data/raw/* into one long-format data/data.csv (one row = one value).

Run: uv run --no-project --with pandas --with pyarrow --with openpyxl python scripts/build_data_csv.py
"""
import json
from pathlib import Path

import pandas as pd

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"
OUT = RAW.parent / "data.csv"
COLS = ["layer", "source", "level", "state", "district", "name", "lat", "lon", "year", "metric", "value", "detail"]

EV_FUELS = ["ELECTRIC(BOV)", "PURE EV", "PLUG-IN HYBRID EV", "STRONG HYBRID EV", "TOTAL"]
CENSUS_METRICS = [
    "Population", "Workers", "Literate", "Households", "Urban_Households", "Rural_Households",
    "Housholds_with_Electric_Lighting", "Households_with_Car_Jeep_Van",
    "Households_with_Scooter_Motorcycle_Moped", "Total_Power_Parity", "Power_Parity_Above_Rs_545000",
]


def up(s):
    return s.str.strip().str.upper() if isinstance(s, pd.Series) else (str(s).strip().upper() if s else None)


def points(layer, source, df, metric="station", value=1):
    return df.assign(layer=layer, source=source, level="point", metric=metric, value=value)


def chargers():
    tp = pd.DataFrame(json.load(open(RAW / "chargers/cpo_tatapower.json")))
    tp = pd.DataFrame({
        "name": tp.station_name, "state": up(tp.state), "district": up(tp.city),
        "lat": tp.coordinates.str["latitude"].astype(float), "lon": tp.coordinates.str["longitude"].astype(float),
        "value": tp.connector_count, "detail": "status=" + tp.station_status.astype(str),
    })
    sq = pd.DataFrame(json.load(open(RAW / "chargers/cpo_statiq.json")))
    sq = pd.DataFrame({"name": sq.station_name, "lat": sq.latitude, "lon": sq.longitude, "detail": sq.address})
    osm = json.load(open(RAW / "chargers/osm_charging_stations.json"))["elements"]
    osm = pd.DataFrame([{
        "name": e.get("tags", {}).get("name"),
        "lat": e.get("lat", e.get("center", {}).get("lat")), "lon": e.get("lon", e.get("center", {}).get("lon")),
        "detail": "; ".join(f"{k}={e['tags'][k]}" for k in ("operator", "brand", "capacity") if k in e.get("tags", {})),
    } for e in osm])
    nat = pd.read_csv(RAW / "chargers/pcs_national_totals_rajyasabha.csv")
    nat = pd.DataFrame({"year": nat.as_on, "metric": "public_charging_stations", "value": nat.no_of_pcs})
    return [
        points("charger", "Tata Power EZ Charge map", tp, metric="connectors").assign(value=tp.value),
        points("charger", "Statiq map", sq),
        points("charger", "OpenStreetMap", osm),
        nat.assign(layer="charger", source="Rajya Sabha Q3929 via data.gov.in", level="national"),
    ]


def vahan():
    out = []
    for f in sorted((RAW / "vahan").glob("vahan_state_fuel_*.xlsx")):
        raw = pd.read_excel(f, header=None).map(lambda v: str(v).replace("\xa0", "").strip() if pd.notna(v) else v)
        hdr = raw.index[raw.eq("PURE EV").any(axis=1)][0]
        # header spans two rows; column 1 is the state name, fuel names sit on the "PURE EV" row
        names = ["state" if i == 1 else (v or f"_{i}") for i, v in enumerate(raw.iloc[hdr].fillna(""))]
        df = raw.iloc[hdr + 1:].set_axis(names, axis=1)
        df = df[df.state.notna() & (df.state != "")]
        fuels = [c for c in df.columns if c != "state" and not c.startswith("_")]
        df["TOTAL"] = df[fuels].apply(lambda s: pd.to_numeric(s.astype(str).str.replace(",", ""), errors="coerce")).sum(axis=1)
        long = df.melt(id_vars="state", value_vars=[c for c in EV_FUELS if c in df.columns], var_name="metric")
        long["value"] = pd.to_numeric(long.value.astype(str).str.replace(",", ""), errors="coerce")
        year = f.stem.rsplit("_", 1)[-1]
        out.append(long.assign(
            layer="ev_registrations", source="VAHAN4 dashboard", level="state", state=up(long.state),
            year="cumulative" if year == "today" else year, metric="registrations_" + long.metric,
        ))
    return out


def demographics():
    c = pd.read_csv(RAW / "demographics/census2011_districts.csv")
    c = c.melt(id_vars=["State name", "District name"], value_vars=CENSUS_METRICS, var_name="metric")
    nl = pd.read_csv(RAW / "demographics/nightlights_districts_2024.csv")
    nl = nl.melt(id_vars=["state_name", "district_name"], value_vars=["sum", "mean"], var_name="metric")
    return [
        c.assign(layer="demographics", source="Census 2011", level="district", year=2011,
                 state=up(c["State name"]), district=up(c["District name"])),
        nl.assign(layer="economy", source="VIIRS night lights", level="district", year=2024,
                  state=up(nl.state_name), district=up(nl.district_name), metric="nightlights_" + nl.metric),
    ]


def infra():
    sub = json.load(open(RAW / "grid/osm_substations.json"))["elements"]
    sub = pd.DataFrame([{
        "name": e.get("tags", {}).get("name"),
        "lat": e.get("lat", e.get("center", {}).get("lat")), "lon": e.get("lon", e.get("center", {}).get("lon")),
        "detail": "; ".join(f"{k}={e['tags'][k]}" for k in ("voltage", "operator", "substation") if k in e.get("tags", {})),
    } for e in sub])
    t = pd.read_parquet(RAW / "roads/morth_toll_plazas.parquet").drop_duplicates("id")
    t = pd.DataFrame({
        "name": t.plaza_name, "state": up(t.sname), "district": up(t.district),
        "lat": t.tollplazal.astype(float), "lon": t.tollplaz_1.astype(float), "detail": t.nhno_new,
    })
    return [points("grid", "OpenStreetMap", sub, metric="substation"),
            points("roads", "MoRTH via PM GatiShakti", t, metric="toll_plaza")]


if __name__ == "__main__":
    df = pd.concat([*chargers(), *vahan(), *demographics(), *infra()], ignore_index=True).reindex(columns=COLS)
    df.to_csv(OUT, index=False)
    print(OUT, len(df), "rows")
    print(df.groupby(["layer", "source"]).size().to_string())

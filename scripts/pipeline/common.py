"""Shared helpers for the pipeline: paths, canonical state table, name normalisation, metre projection."""
import re
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"
DATA_CSV = ROOT / "data" / "data.csv"
GEOJSON = ROOT / "data" / "india_districts.geojson"
AREA_CRS = "EPSG:6933"  # WGS 84 / NSIDC EASE-Grid 2.0, equal-area

# canonical Title Case name -> (RTO letters, aliases as they appear in the sources)
STATES = {
    "Andaman and Nicobar Islands": ("AN", ["Andaman & Nicobar Island", "Andaman & Nicobar Islands"]),
    "Andhra Pradesh": ("AP", []),
    "Arunachal Pradesh": ("AR", ["Arunanchal Pradesh"]),
    "Assam": ("AS", []),
    "Bihar": ("BR", []),
    "Chandigarh": ("CH", []),
    "Chhattisgarh": ("CG", ["Chhatisgarh"]),
    "Dadra and Nagar Haveli and Daman and Diu": ("DN", [
        "Dadra and Nagar Haveli", "Daman and Diu", "Dadara & Nagar Havelli", "UT of DNH and DD", "DNH and DD"]),
    "Delhi": ("DL", ["NCT of Delhi"]),
    "Goa": ("GA", []),
    "Gujarat": ("GJ", []),
    "Haryana": ("HR", []),
    "Himachal Pradesh": ("HP", []),
    "Jammu and Kashmir": ("JK", []),
    "Jharkhand": ("JH", []),
    "Karnataka": ("KA", []),
    "Kerala": ("KL", []),
    "Ladakh": ("LA", []),
    "Lakshadweep": ("LD", []),
    "Madhya Pradesh": ("MP", []),
    "Maharashtra": ("MH", []),
    "Manipur": ("MN", []),
    "Meghalaya": ("ML", []),
    "Mizoram": ("MZ", []),
    "Nagaland": ("NL", []),
    "Odisha": ("OD", ["Orissa"]),
    "Puducherry": ("PY", ["Pondicherry"]),
    "Punjab": ("PB", []),
    "Rajasthan": ("RJ", []),
    "Sikkim": ("SK", []),
    "Tamil Nadu": ("TN", []),
    "Telangana": ("TS", []),
    "Tripura": ("TR", []),
    "Uttar Pradesh": ("UP", []),
    "Uttarakhand": ("UK", ["Uttaranchal"]),
    "West Bengal": ("WB", []),
}


def norm(s):
    """Upper-case alphanumerics only, '&' -> AND, bracketed text dropped: 'Leh(Ladakh)' -> 'LEH'."""
    s = re.sub(r"[\(\[].*?[\)\]]", "", str(s)).upper().replace("&", "AND")
    return re.sub(r"[^A-Z0-9]", "", s)


_ALIAS = {norm(k): k for k in STATES} | {norm(a): k for k, (_, al) in STATES.items() for a in al}


def canon_state(s):
    """Canonical Title Case state/UT name, or None (also None for combos like 'Andhra Pradesh-Telangana')."""
    return _ALIAS.get(norm(s)) if isinstance(s, str) else None


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", str(s).lower().replace("&", "and")).strip("-")


def to_m(lat, lon):
    """Local equirectangular metres, good to ~1% over India; enough for 30-100 m matching."""
    lat, lon = np.asarray(lat, float), np.asarray(lon, float)
    return np.c_[lon * 111320 * np.cos(np.radians(lat)), lat * 110574]

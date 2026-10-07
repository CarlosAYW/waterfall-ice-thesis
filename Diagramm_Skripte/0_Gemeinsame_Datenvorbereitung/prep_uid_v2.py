"""Data preparation for thesis results sections 3.3-3.6 (chunked).

Extracts per-UID static attributes and daily driver aggregates from the
complete UID model runs (data/ModelRuns), consistent with the section 3.2
aggregation (forecast rows removed, run must reach 2026-04-30).

Usage:
  python prep_uid_v2.py                  # alles in einem Durchgang
  python3 prep_uid_v2.py <start> <end>   # process files[start:end]
  python3 prep_uid_v2.py finalize        # merge chunks + inventory/CAP join
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pfade import MA, REPO, OUTPUT, ZWISCHEN, bloecke  # noqa: E402

WORKSPACE = MA
OUT_DIR = ZWISCHEN
BLOCKDIR = ZWISCHEN / "_bloecke_prep_uid_v2"
REPO = WORKSPACE / "Ice fall modeling" / "GutHub" / "ice-waterfalls"
MODEL_DIR = REPO / "data" / "ModelRuns"
TARGET_END = "2026-04-30"

USECOLS = [
    "time", "date", "TLz", "FDH", "PDH", "RF", "FF_eff", "GLOW",
    "SW_MJ_step", "sun_hours_topo", "wind_fac", "dry_fac",
    "cap_temp_adjust_C", "solar_incidence_ratio", "wind_vuln",
    "base_growth_mm_step", "base_melt_mm_step", "thickness_m",
    "surface_ice_m", "core_ice_m", "station_id", "source", "dist_km",
    "dz_m", "cap_delta", "z_target_m", "is_forecast",
]


def uid_from_path(path: Path) -> int:
    m = re.search(r"uid(\d+)", path.stem)
    if not m:
        raise ValueError(path.name)
    return int(m.group(1))


def is_complete(path: Path) -> bool:
    if not path.exists() or path.stat().st_size == 0:
        return False
    with path.open("rb") as f:
        f.seek(max(0, path.stat().st_size - 30000))
        tail = f.read().decode("utf-8", errors="ignore")
    # Der Lauf muss den 30.04.2026 erreichen; die CAP-aktualisierten Laeufe
    # (Juli 2026) reichen darueber hinaus und werden in read_one() gekappt.
    daten = re.findall(r"\d{4}-\d{2}-\d{2}", tail)
    return bool(daten) and max(daten) >= TARGET_END


def read_one(path: Path):
    uid = uid_from_path(path)
    header = pd.read_csv(path, nrows=0)
    cols = [c for c in USECOLS if c in header.columns]
    df = pd.read_csv(path, usecols=cols, low_memory=False)
    if "is_forecast" in df.columns:
        forecast = df["is_forecast"].astype(str).str.lower().isin(["true", "1", "yes"])
        df = df.loc[~forecast].copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.loc[df["date"] <= pd.Timestamp(TARGET_END)]
    if df.empty or df["date"].max() < pd.Timestamp(TARGET_END):
        return pd.DataFrame(), {}

    daily = (
        df.groupby("date", sort=True)
        .agg(
            TLz_mean=("TLz", "mean"),
            TLz_min=("TLz", "min"),
            TLz_max=("TLz", "max"),
            FDH_sum=("FDH", "sum"),
            PDH_sum=("PDH", "sum"),
            RF_mean=("RF", "mean"),
            wind_mean=("FF_eff", "mean"),
            glow_mean=("GLOW", "mean"),
            sw_abs_mj=("SW_MJ_step", "sum"),
            sun_h=("sun_hours_topo", "max"),
            dry_fac_mean=("dry_fac", "mean"),
            wind_fac_mean=("wind_fac", "mean"),
            cap_adj_mean=("cap_temp_adjust_C", "mean"),
            growth_mm=("base_growth_mm_step", "sum"),
            melt_mm=("base_melt_mm_step", "sum"),
            thickness_last=("thickness_m", "last"),
            surface_last=("surface_ice_m", "last"),
            core_last=("core_ice_m", "last"),
        )
        .reset_index()
    )
    daily["uid"] = uid

    first = df.iloc[0]
    static = {
        "uid": uid,
        "station_id": first.get("station_id"),
        "source": first.get("source"),
        "dist_km": first.get("dist_km"),
        "dz_m": first.get("dz_m"),
        "cap_delta": first.get("cap_delta"),
        "z_target_m": first.get("z_target_m"),
        "wind_vuln": df["wind_vuln"].max() if "wind_vuln" in df else np.nan,
        "solar_ratio_med": df["solar_incidence_ratio"].median()
        if "solar_incidence_ratio" in df else np.nan,
    }
    return daily, static


def run_chunk(start: int, end: int, speichern: bool = True):
    files = sorted(MODEL_DIR.glob("model_uid*.csv"), key=uid_from_path)
    chunk = files[start:end]
    dailies, statics = [], []
    for p in chunk:
        if not is_complete(p):
            continue
        d, s = read_one(p)
        if len(d):
            dailies.append(d)
            statics.append(s)
    tmp = BLOCKDIR
    if dailies and speichern:
        tmp.mkdir(parents=True, exist_ok=True)
        pd.concat(dailies, ignore_index=True).to_pickle(tmp / f"daily_{start:04d}.pkl")
        pd.DataFrame(statics).to_pickle(tmp / f"static_{start:04d}.pkl")
    print(f"chunk {start}:{end} -> kept {len(statics)} of {len(chunk)}")
    return dailies, statics


def finalize(daily=None, static=None) -> None:
    tmp = BLOCKDIR
    if daily is None:
        daily = pd.concat(
            [pd.read_pickle(p) for p in sorted(tmp.glob("daily_*.pkl"))], ignore_index=True)
        static = pd.concat(
            [pd.read_pickle(p) for p in sorted(tmp.glob("static_*.pkl"))], ignore_index=True)

    inv = pd.read_csv(
        REPO / "data" / "Koordinaten_Wasserfaelle" / "eisklettern_links_entries_diff.csv",
        sep=";", encoding="latin-1", decimal=",",
    )
    inv = inv[[
        "uid", "name", "latitude", "longitude", "elevation_dgm5m",
        "aspect_deg", "aspect_cardinal", "icefall_height_m",
    ]].copy()

    cap = pd.read_csv(REPO / "data" / "CAP" / "icefall_station_cap.csv")
    cap = cap[[
        "uid", "icefall_cap_potential", "icefall_cap_class",
        "cap_delta_positive", "cap_pair_confidence",
    ]].copy()

    static = static.merge(inv, on="uid", how="left").merge(cap, on="uid", how="left")

    bins = [-np.inf, 1500, 2000, 2500, np.inf]
    labels = ["<1500 m", "1500-2000 m", "2000-2500 m", ">2500 m"]
    static["elevation_band"] = pd.cut(static["z_target_m"], bins=bins, labels=labels)

    daily.to_csv(ZWISCHEN / "prep_uid_v2_daily_drivers.csv", index=False)
    static.to_csv(ZWISCHEN / "prep_uid_v2_static.csv", index=False)
    print("uids:", static["uid"].nunique(), "daily rows:", len(daily))
    print(static["elevation_band"].value_counts())
    print("aspect known:", static["aspect_deg"].notna().sum())
    print("cap known:", static["icefall_cap_potential"].notna().sum())


if __name__ == "__main__":
    import sys

    if len(sys.argv) == 1:            # Gesamtlauf in einem Durchgang
        n = len(list(MODEL_DIR.glob("model_uid*.csv")))
        d, s = run_chunk(0, n, speichern=False)
        finalize(pd.concat(d, ignore_index=True), pd.DataFrame(s))
    elif sys.argv[1] == "finalize":
        finalize()
    else:
        run_chunk(int(sys.argv[1]), int(sys.argv[2]))

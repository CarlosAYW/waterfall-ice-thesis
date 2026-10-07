# -*- coding: utf-8 -*-
"""Blockweise Aggregation der CAP-aktualisierten Modelllaeufe.
Aufruf:  python recompute_chunk.py                  (alles in einem Durchgang)
         python3 recompute_chunk.py <start> <end>
         python3 recompute_chunk.py finalize
Ergebnisse und Blockdateien landen in Diagramm_Skripte/_zwischendaten.
"""
import glob, os, re, sys
import numpy as np, pandas as pd
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pfade import MA, REPO, OUTPUT, ZWISCHEN, bloecke  # noqa: E402

REPO = str(REPO)
OUT = str(ZWISCHEN)
CH = f"{OUT}/_bloecke_recompute"
os.makedirs(CH, exist_ok=True)
TARGET_END = pd.Timestamp("2026-04-30")
COLS = ["date", "TLz", "FDH", "PDH", "RF", "FF_eff", "SW_MJ_step", "sun_hours_topo",
        "cap_temp_adjust_C", "base_growth_mm_step", "base_melt_mm_step", "thickness_m",
        "z_target_m", "cap_delta", "station_id", "source"]

want = set(pd.read_csv(f"{REPO}/data/AWS/icefalls_nearest_station.csv").uid)
files = sorted(glob.glob(f"{REPO}/data/ModelRuns/model_uid*.csv"))
files = [f for f in files if int(re.search(r"uid(\d+)", f).group(1)) in want]


def run(a, b, speichern=True):
    dailies, statics = [], []
    for p in files[a:b]:
        uid = int(re.search(r"uid(\d+)", p).group(1))
        hdr = pd.read_csv(p, nrows=0).columns
        cols = [c for c in COLS if c in hdr]
        df = pd.read_csv(p, usecols=cols, low_memory=False)
        df["date"] = pd.to_datetime(df["date"])
        df = df.loc[df["date"] <= TARGET_END]
        if df.empty or df["date"].max() < TARGET_END:
            print("  unvollstaendig:", uid); continue
        for c in cols:
            if c not in ("date", "source", "station_id"):
                df[c] = pd.to_numeric(df[c], errors="coerce")
        d = (df.groupby("date", sort=True).agg(
                TLz_mean=("TLz", "mean"), TLz_min=("TLz", "min"), TLz_max=("TLz", "max"),
                FDH_sum=("FDH", "sum"), PDH_sum=("PDH", "sum"),
                RF_mean=("RF", "mean"), wind_mean=("FF_eff", "mean"),
                sw_abs_mj=("SW_MJ_step", "sum"), sun_h=("sun_hours_topo", "max"),
                cap_adj_mean=("cap_temp_adjust_C", "mean"),
                cap_adj_max=("cap_temp_adjust_C", "max"),
                growth_mm=("base_growth_mm_step", "sum"),
                melt_mm=("base_melt_mm_step", "sum"),
                thickness_last=("thickness_m", "last")).reset_index())
        d["uid"] = uid
        dailies.append(d)
        f0 = df.iloc[0]
        statics.append(dict(uid=uid, station_id=f0.get("station_id"), source=f0.get("source"),
                            cap_delta=f0.get("cap_delta"), z_target_m=f0.get("z_target_m")))
    if speichern:
        pd.concat(dailies, ignore_index=True).to_pickle(f"{CH}/daily_{a:04d}.pkl")
        pd.DataFrame(statics).to_pickle(f"{CH}/static_{a:04d}.pkl")
    print(f"Block {a}:{b} -> {len(statics)} Routen")
    return dailies, statics


def finalize(daily=None, static=None):
    if daily is None:
        daily = pd.concat([pd.read_pickle(p) for p in sorted(glob.glob(f"{CH}/daily_*.pkl"))],
                          ignore_index=True)
        static = pd.concat([pd.read_pickle(p) for p in sorted(glob.glob(f"{CH}/static_*.pkl"))],
                           ignore_index=True)
    inv = pd.read_csv(f"{REPO}/data/Koordinaten_Wasserfaelle/eisklettern_links_entries_diff.csv",
                      sep=";", encoding="latin-1", decimal=",")
    inv = inv[["uid", "name", "elevation_dgm5m", "aspect_deg", "aspect_cardinal"]]
    cap = pd.read_csv(f"{REPO}/data/CAP/icefall_station_cap.csv")
    capc = [c for c in ["uid", "icefall_cap_potential", "icefall_cap_class",
                        "cap_delta_positive", "cap_pair_confidence"] if c in cap.columns]
    static = static.merge(inv, on="uid", how="left").merge(cap[capc], on="uid", how="left")
    static["elevation_band"] = pd.cut(static["z_target_m"],
                                      [-np.inf, 1500, 2000, 2500, np.inf],
                                      labels=["<1500 m", "1500-2000 m", "2000-2500 m", ">2500 m"])
    th = daily.groupby("uid")["thickness_last"]
    seas = pd.DataFrame({"peak_m": th.max(),
                         "good_days": th.apply(lambda s: int((s >= 0.15).sum())),
                         "ice_days": th.apply(lambda s: int((s >= 0.05).sum()))})
    dr = daily.groupby("uid").agg(FDH_tot=("FDH_sum", "sum"), PDH_tot=("PDH_sum", "sum"),
                                  SW_tot=("sw_abs_mj", "sum"), RF_mean=("RF_mean", "mean"),
                                  wind_mean=("wind_mean", "mean"),
                                  growth_tot=("growth_mm", "sum"), melt_tot=("melt_mm", "sum"),
                                  cap_adj_mean=("cap_adj_mean", "mean"),
                                  cap_adj_max=("cap_adj_max", "max"))
    djf = daily[daily["date"].dt.month.isin([12, 1, 2])]
    sun = djf.groupby("uid")["sun_h"].mean().rename("sun_djf_h")
    seas = (seas.join(dr).join(sun).reset_index()
            .merge(static[["uid", "z_target_m", "elevation_band", "aspect_cardinal",
                           "name", "cap_delta"]], on="uid", how="left"))
    daily.to_csv(f"{OUT}/uid_daily_new.csv", index=False)
    static.to_csv(f"{OUT}/uid_static_new.csv", index=False)
    seas.to_csv(f"{OUT}/uid_season_new.csv", index=False)
    print(f"Routen: {len(static)}  Tageszeilen: {len(daily)}")
    print(seas["elevation_band"].value_counts().to_string())


if __name__ == "__main__":
    print(f"(Dateien insgesamt: {len(files)})")
    if len(sys.argv) == 1:            # Gesamtlauf in einem Durchgang
        d, s = run(0, len(files), speichern=False)
        finalize(pd.concat(d, ignore_index=True), pd.DataFrame(s))
    elif sys.argv[1] == "finalize":
        finalize()
    else:
        run(int(sys.argv[1]), int(sys.argv[2]))

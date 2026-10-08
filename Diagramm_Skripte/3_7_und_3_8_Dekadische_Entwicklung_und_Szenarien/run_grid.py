"""Response-Gitter des saturierten Proxys: Eistage(dT) je Referenzpunkt/Winter.
Optimiert: Saison einmal laden, alle Deltas vektorisiert.

Aufruf:  python run_grid.py              alle Winter, danach Zusammenfuehren
         python run_grid.py a|b|c|d|e    nur eine Wintergruppe (blockweise)
         python run_grid.py finalize     Gruppen zusammenfuehren

Eingang: INCA-Stundenwerte aus build_inca_winter_reference.R
         (output/results_3_1_meteorological_conditions/inca_winter_reference/cache)
Ausgabe: _zwischendaten/grid_res_all.pkl und grid_cur_all.pkl fuer build_fig2628.py
"""
import sys
import numpy as np
import pandas as pd
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pfade import OUTPUT, ZWISCHEN

BASE = OUTPUT / "results_3_1_meteorological_conditions" / "inca_winter_reference"
BLOCKDIR = ZWISCHEN / "_bloecke_grid"
REMOVED = {280, 699}   # im letzten Screening als Nordwaende entfernt (wie k5_map.py)
H0, HMAX, LAM = 0.20, 0.90, 0.15
DEN = 1 - np.exp(-HMAX / LAM)
DELTAS = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.5]

def run_season(tag):
    dfs = [pd.read_csv(f) for f in sorted((BASE/"cache").glob(f"inca_{tag}_chunk*.csv"))]
    df = pd.concat(dfs, ignore_index=True).rename(columns={"T2M [degree_Celsius]": "T", "GL [W m-2]": "GL"})
    df["k"] = df["lat"].round(4).astype(str) + "_" + df["lon"].round(4).astype(str)
    df["time"] = pd.to_datetime(df["time"], utc=True)
    df["date"] = df["time"].dt.date
    rows, curves = [], []
    for dt in DELTAS:
        t = df["T"] + dt
        g = df.assign(fdh=np.where(t < 0, -t, 0.0), pdh=np.where(t > 0, t, 0.0),
                      gl_mj=df["GL"] * 3600 / 1e6)
        daily = g.groupby(["k", "date"], sort=True).agg(
            fdh=("fdh", "sum"), pdh=("pdh", "sum"), gl_mj=("gl_mj", "sum")).reset_index()
        growth = (0.50 * daily["fdh"].to_numpy()) / 1000.0
        melt = (0.60 * daily["pdh"].to_numpy() + 0.35 * 0.50 * daily["gl_mj"].to_numpy()) / 1000.0
        ks = daily["k"].to_numpy()
        H = np.zeros(len(daily)); h = 0.0; prev = None
        for i in range(len(daily)):
            if ks[i] != prev:
                h = 0.0; prev = ks[i]
            iso = np.exp(-h / H0)
            cap = (1 - np.exp(-max(0.0, HMAX - h) / LAM)) / DEN
            h = max(0.0, h + growth[i] * iso * cap - melt[i])
            H[i] = h
        daily["h"] = H
        agg = daily.groupby("k")["h"].agg(good_days=lambda s: int((s >= 0.15).sum()),
                                          peak_m=lambda s: round(float(s.max()), 3))
        for k, r in agg.iterrows():
            rows.append({"k": k, "season": tag.replace("_", "/"), "delta": dt,
                         "good_days": int(r["good_days"]), "peak_m": r["peak_m"]})
        if dt == 0.0:
            c = daily[["k", "date", "h"]].copy()
            c["season"] = tag.replace("_", "/")
            curves.append(c)
    return pd.DataFrame(rows), pd.concat(curves, ignore_index=True)

def run_group(tags):
    res, cur = [], []
    for tag in tags:
        r, c = run_season(tag)
        res.append(r); cur.append(c)
        print("done", tag)
    return pd.concat(res, ignore_index=True), pd.concat(cur, ignore_index=True)


def finalize(res=None, cur=None):
    """Gitterzelle -> naechster Referenzpunkt (uid, Hoehe, Band); die beiden als
    Nordwaende entfernten Routen fallen weg. Zwei Routenpaare teilen sich eine
    INCA-Zelle, daher bleiben 28 Punkte."""
    if res is None:
        res = pd.concat([pd.read_pickle(p) for p in sorted(BLOCKDIR.glob("grid_res_*.pkl"))],
                        ignore_index=True)
        cur = pd.concat([pd.read_pickle(p) for p in sorted(BLOCKDIR.glob("grid_cur_*.pkl"))],
                        ignore_index=True)
    pts = pd.read_csv(BASE / "inca_reference_sample_points.csv")
    uk = pd.DataFrame({"k": sorted(res["k"].unique())})
    ll = uk["k"].str.split("_", expand=True).astype(float)
    uk["glat"], uk["glon"] = ll[0], ll[1]

    def nearest(row):
        d = ((pts["ice_lat"] - row["glat"]) ** 2
             + ((pts["ice_lon"] - row["glon"]) * np.cos(np.radians(row["glat"]))) ** 2)
        return pts.loc[d.idxmin(), ["uid", "icefall_name", "elevation_band", "icefall_elev_m"]]

    uk[["uid", "icefall_name", "elevation_band", "icefall_elev_m"]] = uk.apply(nearest, axis=1)
    uk = uk[~uk["uid"].isin(REMOVED)]
    info = uk[["k", "uid", "icefall_name", "elevation_band", "icefall_elev_m"]]
    res = res.merge(info, on="k", how="inner")
    cur = cur.merge(info[["k", "uid"]], on="k", how="inner")
    res.to_pickle(ZWISCHEN / "grid_res_all.pkl")
    cur.to_pickle(ZWISCHEN / "grid_cur_all.pkl")
    print("Punkte:", res["k"].nunique(), "| Winter:", res["season"].nunique(),
          "| Deltas:", res["delta"].nunique())


if __name__ == "__main__":
    seasons = sorted({f.name.split("_chunk")[0].replace("inca_", "")
                      for f in (BASE/"cache").glob("inca_*chunk*.csv")})
    groups = {"a": seasons[:3], "b": seasons[3:6], "c": seasons[6:9], "d": seasons[9:12], "e": seasons[12:]}
    if len(sys.argv) == 1:
        finalize(*run_group(seasons))
    elif sys.argv[1] == "finalize":
        finalize()
    else:
        part = sys.argv[1]
        r, c = run_group(groups[part])
        BLOCKDIR.mkdir(parents=True, exist_ok=True)
        r.to_pickle(BLOCKDIR / f"grid_res_{part}.pkl")
        c.to_pickle(BLOCKDIR / f"grid_cur_{part}.pkl")

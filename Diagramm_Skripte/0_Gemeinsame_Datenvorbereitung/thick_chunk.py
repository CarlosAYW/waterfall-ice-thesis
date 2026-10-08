"""Taegliche Median-Dicke je Route aus den CAP-aktualisierten Laeufen.
Aufruf: python thick_chunk.py  (alles)  |  python3 thick_chunk.py <start> <end>  |  python3 thick_chunk.py finalize
"""
import glob, os, re, sys
import pandas as pd
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pfade import MA, REPO, OUTPUT, ZWISCHEN, bloecke

REPO = str(REPO)
OUT = str(ZWISCHEN)
CH = f"{OUT}/_bloecke_thick"
os.makedirs(CH, exist_ok=True)
TARGET_END = pd.Timestamp("2026-04-30")

want = set(pd.read_csv(f"{REPO}/data/AWS/icefalls_nearest_station.csv").uid)
files = sorted(glob.glob(f"{REPO}/data/ModelRuns/model_uid*.csv"))
files = [f for f in files if int(re.search(r"uid(\d+)", f).group(1)) in want]


def run(a, b, speichern=True):
    out = []
    for p in files[a:b]:
        uid = int(re.search(r"uid(\d+)", p).group(1))
        df = pd.read_csv(p, usecols=["date", "thickness_m"], low_memory=False)
        df["date"] = pd.to_datetime(df["date"])
        df = df.loc[df["date"] <= TARGET_END]
        if df.empty or df["date"].max() < TARGET_END:
            continue
        df["thickness_m"] = pd.to_numeric(df["thickness_m"], errors="coerce")
        d = df.groupby("date", sort=True)["thickness_m"].median().reset_index()
        d["uid"] = uid
        out.append(d)
    if speichern:
        pd.concat(out, ignore_index=True).to_pickle(f"{CH}/thick_{a:04d}.pkl")
    print(f"Block {a}:{b} -> {len(out)} Routen")
    return out


def finalize(teile=None):
    if teile is None:
        teile = [pd.read_pickle(p) for p in sorted(glob.glob(f"{CH}/thick_*.pkl"))]
    th = pd.concat(teile, ignore_index=True)
    th = th[["uid", "date", "thickness_m"]]
    th.to_pickle(f"{OUT}/uid_daily_thick_new.pkl")
    print("Routen:", th.uid.nunique(), "| Zeilen:", len(th))


if __name__ == "__main__":
    if len(sys.argv) == 1:            # Gesamtlauf in einem Durchgang
        finalize(run(0, len(files), speichern=False))
    elif sys.argv[1] == "finalize":
        finalize()
    else:
        run(int(sys.argv[1]), int(sys.argv[2]))

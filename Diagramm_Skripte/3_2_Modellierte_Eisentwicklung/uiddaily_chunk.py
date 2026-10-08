"""Cache im Schema von modelled_ice_uid_daily.csv, blockweise.
Aufruf: python uiddaily_chunk.py (alles) | python3 uiddaily_chunk.py <start> <end> | finalize
"""
import glob, os, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))       # build_results_3_2_modelled_ice.py
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # pfade.py
from pfade import REPO, ZWISCHEN
import pandas as pd
import build_results_3_2_modelled_ice as B

OUT = str(ZWISCHEN)
CH = f"{OUT}/_bloecke_uiddaily"
os.makedirs(CH, exist_ok=True)
REPO = str(REPO)

want = set(pd.read_csv(f"{REPO}/data/AWS/icefalls_nearest_station.csv").uid)
files = sorted(glob.glob(f"{REPO}/data/ModelRuns/model_uid*.csv"))
files = [Path(f) for f in files if int(re.search(r"uid(\d+)", f).group(1)) in want]


def run(a, b, speichern=True):
    out = [B.read_uid_daily(p) for p in files[a:b]]
    out = [d for d in out if len(d)]
    if speichern:
        pd.concat(out, ignore_index=True).to_pickle(f"{CH}/uidd_{a:04d}.pkl")
    print(f"Block {a}:{b} -> {len(out)} Routen")
    return out


def finalize(teile=None):
    if teile is None:
        teile = [pd.read_pickle(p) for p in sorted(glob.glob(f"{CH}/uidd_*.pkl"))]
    d = pd.concat(teile, ignore_index=True).sort_values(["uid", "date"]).reset_index(drop=True)
    d.to_pickle(f"{OUT}/uid_daily_full_new.pkl")
    print("Routen:", d.uid.nunique(), "| Zeilen:", len(d))


if __name__ == "__main__":
    if len(sys.argv) == 1:            # Gesamtlauf in einem Durchgang
        finalize(run(0, len(files), speichern=False))
    elif sys.argv[1] == "finalize":
        finalize()
    else:
        run(int(sys.argv[1]), int(sys.argv[2]))

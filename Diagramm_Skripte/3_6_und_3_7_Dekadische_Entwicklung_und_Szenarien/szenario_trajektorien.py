"""Szenario-Trajektorien fuer Abb. 32 (Kap. 3.7): traj_general.json und traj_sites.json.

Nachgebaut nach der Methodenbeschreibung der Arbeit, weil das urspruengliche
Skript nicht erhalten ist. Gegen die in der Arbeit verwendeten JSON-Dateien
geprueft: groesste Abweichung 0,1 Eistage (Rundung).

Vorgehen
- Globale Erwaermung gegenueber 1850-1900 nach IPCC AR6 (Lee et al. 2023,
  Tab. SPM.1), beste Schaetzung fuer 2021-2040, 2041-2060, 2081-2100,
  gesetzt auf die Periodenmitten 2030, 2050, 2090.
- Basisperiode 2012-2026 = 1,2 degC ueber 1850-1900, Mitte 2019 (dT = 0).
- Regionale Stoerung = 2 x (global - 1,2) (Alpen etwa doppelt so stark, Gobiet et al. 2014).
- Linear interpoliert auf die Jahre 2026, 2028, ..., 2090.
- Eistage je Punkt-Winter aus dem Stoerungsgitter von run_grid.py (0 bis +6,5 degC)
  linear bei dT interpoliert; (a) Median und IQR ueber alle Punkt-Winter,
  (b-e) Median ueber die 14 Winter je Standort.

Eingang: _zwischendaten/grid_res_all.pkl (run_grid.py)
Ausgabe: _zwischendaten/traj_general.json, _zwischendaten/traj_sites.json
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pfade import ZWISCHEN

SPM1 = {"SSP1-2.6": (1.5, 1.7, 1.8), "SSP2-4.5": (1.5, 2.0, 2.7), "SSP5-8.5": (1.6, 2.4, 4.4)}
ANKER = [2019, 2030, 2050, 2090]
BASIS = 1.2
REGIONAL = 2.0
JAHRE = np.arange(2026, 2091, 2)
SITES = ["9", "252", "183", "217"]   # Golden Shower, Sunblocker, Notwegfall, Sagzahnverschneidung

res = pd.read_pickle(ZWISCHEN / "grid_res_all.pkl")
piv = res.pivot_table(index=["k", "uid", "season"], columns="delta", values="good_days")
deltas = piv.columns.to_numpy(dtype=float)


def trajektorie(g):
    return np.interp(JAHRE, ANKER, [0.0] + [REGIONAL * (v - BASIS) for v in g])


def eistage(tab, dT):
    """Matrix Jahre x Punkt-Winter: Eistage bei der jeweiligen Stoerung."""
    return np.array([[np.interp(t, deltas, zeile) for zeile in tab.to_numpy()] for t in dT])


general = {}
sites = {uid: {} for uid in SITES}
for sc, g in SPM1.items():
    dT = trajektorie(g)
    v = eistage(piv, dT)
    general[sc] = {
        "years": JAHRE.tolist(),
        "dT": [round(float(x), 2) for x in dT],
        "med": [round(float(x), 1) for x in np.median(v, axis=1)],
        "q1": [round(float(x), 1) for x in np.percentile(v, 25, axis=1)],
        "q3": [round(float(x), 1) for x in np.percentile(v, 75, axis=1)],
    }
    for uid in SITES:
        sub = piv[piv.index.get_level_values("uid") == int(uid)]
        sites[uid][sc] = [round(float(x), 1) for x in np.median(eistage(sub, dT), axis=1)]

with open(ZWISCHEN / "traj_general.json", "w") as f:
    json.dump(general, f)
with open(ZWISCHEN / "traj_sites.json", "w") as f:
    json.dump({"years": JAHRE.tolist(), "sites": sites}, f)
for sc in SPM1:
    m = general[sc]["med"]
    print(f"{sc}: Median {m[0]} -> {m[JAHRE.tolist().index(2050)]} (2050) -> {m[-1]} (2090) Tage")

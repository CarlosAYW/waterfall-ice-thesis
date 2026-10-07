# -*- coding: utf-8 -*-
"""Baut die Zwischendateien (frueher unter /tmp), die die Abbildungsskripte lesen,
aus den CAP-aktualisierten Laeufen neu. Liest und schreibt Diagramm_Skripte/_zwischendaten."""
import os
import numpy as np, pandas as pd
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pfade import MA, REPO, OUTPUT, ZWISCHEN, bloecke  # noqa: E402

OUT = str(ZWISCHEN)   # Ergebnisse von recompute_chunk.py und thick_chunk.py

# ---- static: Geometrie aus der alten Datei, CAP-Spalten aus den neuen Laeufen ----
old = pd.read_csv(ZWISCHEN / "prep_uid_v2_static.csv")   # aus prep_uid_v2.py
new = pd.read_csv(f"{OUT}/uid_static_new.csv")
CAPC = ["cap_delta", "icefall_cap_potential", "icefall_cap_class",
        "cap_delta_positive", "cap_pair_confidence", "station_id", "source", "z_target_m"]
st = old.drop(columns=[c for c in CAPC if c in old.columns])
st = new[["uid"] + CAPC].merge(st, on="uid", how="left")

# Routen, die im alten Cache fehlten, aus dem Inventar ergaenzen
REPO = str(REPO)
inv = pd.read_csv(f"{REPO}/data/Koordinaten_Wasserfaelle/eisklettern_links_entries_diff.csv",
                  sep=";", decimal=",")
inv = inv.set_index("uid")
for c in ["name", "latitude", "longitude", "elevation_dgm5m", "aspect_deg",
          "aspect_cardinal", "icefall_height_m"]:
    st[c] = st[c].fillna(st["uid"].map(inv[c]))
BANDS = ["<1500 m", "1500-2000 m", "2000-2500 m", ">2500 m"]
st["elevation_band"] = st["elevation_band"].fillna(
    pd.cut(st["z_target_m"], [-np.inf, 1500, 2000, 2500, np.inf], labels=BANDS).astype(object))
miss = st[st["aspect_deg"].isna()]
print("Routen:", len(st), "| ohne Geometrie:", len(miss), list(miss.uid)[:10])
st.to_csv(ZWISCHEN / "uid_static.csv", index=False)

# ---- daily drivers ----
drv = pd.read_csv(f"{OUT}/uid_daily_new.csv", parse_dates=["date"])
drv.to_csv(ZWISCHEN / "uid_daily_drivers.csv", index=False)
print("drivers:", len(drv), "Zeilen,", drv.uid.nunique(), "Routen")

# ---- taegliche Median-Dicke ----
th = pd.read_pickle(f"{OUT}/uid_daily_thick_new.pkl")
th.to_pickle(ZWISCHEN / "uid_daily_320.pkl")
uids = sorted(th.uid.unique())
for i, part in enumerate(np.array_split(uids, 3)):
    th[th.uid.isin(part)].to_pickle(ZWISCHEN / f"thick_{i}.pkl")
print("thick:", len(th), "Zeilen,", len(uids), "Routen")


# ---- Aspektsektoren, wie die Abbildung sie definiert ----
def sector(deg):
    if not np.isfinite(deg):
        return np.nan
    d = deg % 360
    if d >= 315 or d < 45:
        return "N"
    if d < 135:
        return "E"
    if d < 225:
        return "S"
    return "W"


st["sec"] = st["aspect_deg"].map(sector)
print("\nAspektsektoren (4er-Definition der Abbildung):")
print(st["sec"].value_counts().to_string())

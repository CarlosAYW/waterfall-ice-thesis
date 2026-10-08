"""Karte der stratifizierten INCA-Referenzpunkte (nicht mehr in der Arbeit).

Die Karte zeigt dieselbe Kartengrundlage wie die
Uebersichtskarte der modellierten Eistage und markiert die Punkte nach
Hoehenband; die beiden im letzten Screening entfernten Nordwaende sind als
ausgeschlossen gekennzeichnet.
"""
import math
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from PIL import Image
import sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pfade import MA, REPO, OUTPUT, ZWISCHEN, abbildungen, schrift
ABB = abbildungen(__file__)   # Abbildungen landen in <Kapitelordner>/abbildungen

BASE = MA
PTS = BASE / "output/results_3_1_meteorological_conditions/inca_winter_reference/inca_reference_sample_points.csv"
TILE_DIR = BASE / "output/study_area_map/_cache/osm_standard_tiles"
OUT = ABB / "fig_reference_points.png"
REMOVED = {280, 699}          # im Screening als Nordwaende entfernt

BAND_ORDER = ["<1500 m", "1500-2000 m", "2000-2500 m", ">2500 m"]
BAND_COL = {"<1500 m": "#b4554e", "1500-2000 m": "#d0993f",
            "2000-2500 m": "#4f8fbd", ">2500 m": "#183a5a"}
Z = 10

pts = pd.read_csv(PTS)
pts["used"] = ~pts.uid.isin(REMOVED)
print("Punkte:", len(pts), "| verwendet:", int(pts.used.sum()))
print(pts[pts.used].elevation_band.value_counts().reindex(BAND_ORDER).to_string())


def ll2t(lat, lon, z=Z):
    n = 2 ** z
    x = (lon + 180) / 360 * n
    y = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
    return x, y


pad = 0.14
lat0, lat1 = pts.ice_lat.min() - pad, pts.ice_lat.max() + pad
lon0, lon1 = pts.ice_lon.min() - pad, pts.ice_lon.max() + pad
x0, y1 = ll2t(lat0, lon0)
x1, y0 = ll2t(lat1, lon1)
tx0, tx1, ty0, ty1 = int(x0), int(x1), int(y0), int(y1)

tdir = TILE_DIR / str(Z)
have = {(int(p.parent.name), int(p.stem)) for p in tdir.glob("*/*.png")}
mosaic = Image.new("RGB", ((tx1 - tx0 + 1) * 256, (ty1 - ty0 + 1) * 256), "#e8e6e1")
used = 0
for tx in range(tx0, tx1 + 1):
    for ty in range(ty0, ty1 + 1):
        if (tx, ty) in have:
            mosaic.paste(Image.open(tdir / str(tx) / f"{ty}.png").convert("RGB"),
                         ((tx - tx0) * 256, (ty - ty0) * 256))
            used += 1
print(f"Kacheln: {used} von {(tx1-tx0+1)*(ty1-ty0+1)}")
g = mosaic.convert("L").point(lambda v: int(200 + v * 0.22) if v < 250 else v)
mosaic = Image.merge("RGB", (g, g, g))

plt.rcParams.update({"font.family": schrift(), "font.size": 8.8,
                     "legend.frameon": False})
fig, ax = plt.subplots(figsize=(7.4, 4.6), constrained_layout=True)
ax.imshow(mosaic, extent=[tx0, tx1 + 1, ty1 + 1, ty0], zorder=0)

for band in BAND_ORDER:
    s = pts[(pts.elevation_band == band) & pts.used]
    if not len(s):
        continue
    px, py = zip(*[ll2t(la, lo) for la, lo in zip(s.ice_lat, s.ice_lon)])
    ax.scatter(px, py, s=52, color=BAND_COL[band], edgecolor="#2f2f2f",
               linewidths=0.5, zorder=5, label=f"{band} (n = {len(s)})")
s = pts[~pts.used]
if len(s):
    px, py = zip(*[ll2t(la, lo) for la, lo in zip(s.ice_lat, s.ice_lon)])
    ax.scatter(px, py, s=52, marker="x", color="#8a8a8a", linewidths=1.4, zorder=5,
               label=f"reclassified as north face (n = {len(s)})")

for lon in np.arange(np.ceil(lon0 * 2) / 2, lon1, 0.5):
    gx, _ = ll2t(lat0, lon)
    ax.axvline(gx, color="#aaaaaa", lw=0.4, alpha=0.6, zorder=1)
    ax.text(gx, ty1 + 0.97, f"{lon:.1f}°E", fontsize=6.6, ha="center", color="#555555")
for lat in np.arange(np.ceil(lat0 * 4) / 4, lat1, 0.25):
    _, gy = ll2t(lat, lon0)
    ax.axhline(gy, color="#aaaaaa", lw=0.4, alpha=0.6, zorder=1)
    ax.text(tx0 + 0.03, gy, f"{lat:.2f}°N", fontsize=6.6, va="center", color="#555555")

ax.set_xlim(x0, x1); ax.set_ylim(y1, y0)
ax.set_xticks([]); ax.set_yticks([]); ax.grid(False)
lat_c = (lat0 + lat1) / 2
km_per_tile = 40075.017 * math.cos(math.radians(lat_c)) / (2 ** Z)
bar_km = 20
bt = bar_km / km_per_tile
bx, by = x1 - bt - 0.25, y1 - 0.28
ax.plot([bx, bx + bt], [by, by], color="#2f2f2f", lw=2.2, zorder=6)
ax.text(bx + bt / 2, by - 0.09, f"{bar_km} km", ha="center", fontsize=7, zorder=6)
# Nordpfeil
nx = x1 - 0.16
ny_b = y0 + 0.62
ny_t = y0 + 0.20
ax.annotate("", xy=(nx, ny_t), xytext=(nx, ny_b), zorder=7,
            arrowprops=dict(arrowstyle="-|>", color="#2f2f2f", lw=1.4,
                            mutation_scale=11))
ax.text(nx, ny_b + 0.16, "N", ha="center", va="top", fontsize=8,
        color="#2f2f2f", zorder=7)
ax.text(0.005, 0.005, "Background: OpenStreetMap contributors (ODbL)", fontsize=5.6,
        color="#666666", transform=ax.transAxes, va="bottom")
ax.legend(fontsize=7.2, loc="upper left", ncols=2)
fig.savefig(OUT, dpi=300)
print("gespeichert:", OUT)

import math, json
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd
from PIL import Image
from pathlib import Path
import sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pfade import MA, REPO, OUTPUT, ZWISCHEN, abbildungen, schrift, einheitlich
ABB = abbildungen(__file__)   # Abbildungen landen in <Kapitelordner>/abbildungen

plt.rcParams.update({
    "font.family": schrift(), "font.size": 8.8,
    "axes.spines.top": False, "axes.spines.right": False,
    "legend.frameon": False,
})

V = REPO / "analysis/Icefall_validation/UIDs"

# ---------- regional map ----------
Z = 10
TILE_DIR = OUTPUT / "study_area_map/_cache/osm_standard_tiles" / str(Z)
seas = pd.read_csv(ZWISCHEN / "uid_season_metrics.csv")
seas = seas.dropna(subset=["latitude", "longitude"])

def ll2t(lat, lon, z):
    n = 2 ** z
    x = (lon + 180) / 360 * n
    y = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
    return x, y

pad = 0.12
lat0, lat1 = seas["latitude"].min()-pad, seas["latitude"].max()+pad
lon0, lon1 = seas["longitude"].min()-pad, seas["longitude"].max()+pad
x0, y1 = ll2t(lat0, lon0, Z)
x1, y0 = ll2t(lat1, lon1, Z)
tx0, tx1 = int(x0), int(x1)
ty0, ty1 = int(y0), int(y1)
tiles_avail = {(int(p.parent.name), int(p.stem)) for p in TILE_DIR.glob("*/*.png")}
mosaic = Image.new("RGB", ((tx1-tx0+1)*256, (ty1-ty0+1)*256), "#e8e6e1")
used = 0
for tx in range(tx0, tx1+1):
    for ty in range(ty0, ty1+1):
        if (tx, ty) in tiles_avail:
            t = Image.open(TILE_DIR / str(tx) / f"{ty}.png").convert("RGB")
            mosaic.paste(t, ((tx-tx0)*256, (ty-ty0)*256))
            used += 1
print("tiles used:", used, "of", (tx1-tx0+1)*(ty1-ty0+1))
# desaturate background so points pop
g = mosaic.convert("L").point(lambda v: int(200 + v*0.22) if v < 250 else v)
mosaic = Image.merge("RGB", (g, g, g))

fig, ax = plt.subplots(figsize=(7.4, 4.6), constrained_layout=True)
ax.imshow(mosaic, extent=[tx0, tx1+1, ty1+1, ty0], zorder=0)
px, py = zip(*[ll2t(la, lo, Z) for la, lo in zip(seas["latitude"], seas["longitude"])])
sc = ax.scatter(px, py, c=seas["good_days"], cmap="viridis", s=17,
                edgecolor="#2f2f2f", linewidths=0.25, zorder=5)
cb = fig.colorbar(sc, ax=ax, shrink=0.75, pad=0.015)
cb.set_label("Days with modelled thickness >= 0.15 m")
# graticule
for lon in np.arange(np.ceil(lon0*2)/2, lon1, 0.5):
    gx, _ = ll2t(lat0, lon, Z)
    ax.axvline(gx, color="#aaaaaa", lw=0.4, alpha=0.6, zorder=1)
    ax.text(gx, ty1+0.97, f"{lon:.1f}°E", fontsize=6.6, ha="center", color="#555555")
for lat in np.arange(np.ceil(lat0*4)/4, lat1, 0.25):
    _, gy = ll2t(lat, lon0, Z)
    ax.axhline(gy, color="#aaaaaa", lw=0.4, alpha=0.6, zorder=1)
    ax.text(tx0+0.03, gy, f"{lat:.2f}°N", fontsize=6.6, va="center", color="#555555")
ax.set_xlim(x0, x1); ax.set_ylim(y1, y0)
ax.set_xticks([]); ax.set_yticks([])
ax.grid(False)
# scale bar (approx at central latitude)
lat_c = (lat0+lat1)/2
km_per_tile = 40075.017 * math.cos(math.radians(lat_c)) / (2**Z)
bar_km = 20
bar_tiles = bar_km / km_per_tile
bx = x1 - bar_tiles - 0.25; by = y1 - 0.28
ax.plot([bx, bx+bar_tiles], [by, by], color="#2f2f2f", lw=2.2, zorder=6)
ax.text(bx+bar_tiles/2, by-0.09, f"{bar_km} km", ha="center", fontsize=7, zorder=6)
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
einheitlich(fig); fig.savefig(ABB / "fig_3_3_map_ice_days.png", dpi=300)
plt.close(fig)
print("map done")

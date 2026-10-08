"""Sun-effect validation figure: Marchlehnfall (UID 174, SW-facing).
(a) photo, (b) two matched days sunny vs overcast, (c) melt vs absorbed SW."""
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image
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
    "axes.grid": True, "grid.color": "#d9d9d9",
    "grid.linewidth": 0.6, "grid.alpha": 0.6, "legend.frameon": False,
})
U174 = REPO / "analysis/Icefall_validation/UIDs/174 _ Marchlehnfall"
drv = pd.read_csv(ZWISCHEN / "uid_daily_drivers.csv", parse_dates=["date"])
d = drv[drv["uid"] == 174].sort_values("date").copy()
d["thick_prev"] = d["thickness_last"].shift()

SUNNY = pd.Timestamp("2026-02-27")
CLOUD = pd.Timestamp("2026-01-13")
ds = d[d["date"] == SUNNY].iloc[0]
dc = d[d["date"] == CLOUD].iloc[0]

fig = plt.figure(figsize=(7.4, 3.6), constrained_layout=True)
gs = fig.add_gridspec(1, 3, width_ratios=[0.85, 1, 1.25])

# (a) photo
axa = fig.add_subplot(gs[0, 0])
img = Image.open(U174 / "14-02-2026_whatsapp_01.jpg")
w, h = img.size
target = 0.75
if w/h > target:
    nw = int(h*target); x0 = (w-nw)//2
    img = img.crop((x0, 0, x0+nw, h))
img.thumbnail((520, 760))
axa.imshow(img)
axa.set_xticks([]); axa.set_yticks([]); axa.grid(False)
for sp in axa.spines.values():
    sp.set_visible(True); sp.set_color("#999999"); sp.set_linewidth(0.6)
axa.set_xlabel("(a) Marchlehnfall (Pitztal,\nSW-facing, 1853 m), 2026-02-14", fontsize=7.6, labelpad=4)

# (b) matched-day comparison
axb = fig.add_subplot(gs[0, 1])
x = np.array([0, 1])
w2 = 0.34
b1 = axb.bar(x - w2/2, [dc["sw_abs_mj"], ds["sw_abs_mj"]], width=w2,
             color="#d0993f", label="Absorbed shortwave (MJ/m²)")
b2 = axb.bar(x + w2/2, [dc["melt_mm"], ds["melt_mm"]], width=w2,
             color="#c9584f", label="Modelled melt (mm/day)")
for bars in (b1, b2):
    for rect in bars:
        axb.text(rect.get_x() + rect.get_width()/2, rect.get_height() + 0.6,
                 f"{rect.get_height():.1f}", ha="center", fontsize=7.6)
axb.set_xticks(x, [f"overcast\n{CLOUD:%Y-%m-%d}\nTLz +{dc['TLz_mean']:.1f} °C",
                   f"clear-sky\n{SUNNY:%Y-%m-%d}\nTLz +{ds['TLz_mean']:.1f} °C"], fontsize=7.4)
axb.set_ylim(0, 46)
axb.legend(fontsize=6.8, loc="upper left")
axb.set_title("(b) Two days at nearly equal\nair temperature", loc="left", fontsize=9)

# (c) melt vs absorbed SW for warm ice-bearing days
axc = fig.add_subplot(gs[0, 2])
sel = d[(d["thick_prev"] >= 0.05) & (d["TLz_mean"].between(0.5, 3.0))]
sc = axc.scatter(sel["sw_abs_mj"], sel["melt_mm"], c=sel["TLz_mean"], cmap="coolwarm",
                 vmin=0.5, vmax=3.0, s=26, edgecolor="#2f2f2f", linewidths=0.3)
# Datumsbeschriftung aus SUNNY/CLOUD
for day, lab, dy in [(dc, f"{CLOUD:%Y-%m-%d}", 8), (ds, f"{SUNNY:%Y-%m-%d}", 8)]:
    axc.scatter(day["sw_abs_mj"], day["melt_mm"], s=120, facecolor="none",
                edgecolor="#2f2f2f", linewidths=1.4, zorder=6)
    axc.annotate(lab, xy=(day["sw_abs_mj"], day["melt_mm"]), xytext=(0, dy),
                 textcoords="offset points", ha="center", fontsize=7.4)
cb = fig.colorbar(sc, ax=axc, shrink=0.8, pad=0.02)
cb.set_label("Daily mean TLz (°C)", fontsize=7.6)
cb.ax.tick_params(labelsize=7)
axc.set_xlabel("Absorbed shortwave radiation (MJ/m² per day)")
axc.set_ylabel("Modelled melt (mm/day)")
axc.set_title("(c) Ice-bearing days with TLz\nbetween +0.5 and +3 °C", loc="left", fontsize=9)

einheitlich(fig); fig.savefig(ABB / "fig_3_5_sun_effect.png", dpi=300)
plt.close(fig)
print("sun fig done | sunny:", round(ds["sw_abs_mj"],1), "MJ,", round(ds["melt_mm"],1), "mm | cloud:",
      round(dc["sw_abs_mj"],1), "MJ,", round(dc["melt_mm"],1), "mm")

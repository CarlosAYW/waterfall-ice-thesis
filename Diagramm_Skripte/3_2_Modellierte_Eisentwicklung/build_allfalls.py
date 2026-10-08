"""Abb. 18: alle Routen der Saison 2025/26 (Spaghetti, nach Höhenband)."""
import pandas as pd, numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.lines import Line2D
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
BAND_ORDER = ["<1500 m", "1500-2000 m", "2000-2500 m", ">2500 m"]
BAND_COL = {"<1500 m": "#b4554e", "1500-2000 m": "#d0993f",
            "2000-2500 m": "#4f8fbd", ">2500 m": "#183a5a"}

th = pd.concat([pd.read_pickle(ZWISCHEN / f"thick_{p}.pkl") for p in range(3)], ignore_index=True)
seas = pd.read_csv(ZWISCHEN / "uid_season_metrics.csv")
elev = seas.set_index("uid")["z_target_m"]
th["band"] = pd.cut(th["uid"].map(elev), [-np.inf,1500,2000,2500,np.inf], labels=BAND_ORDER)
n = th["uid"].nunique()
print("Routen:", n)

fig, ax = plt.subplots(figsize=(7.4, 4.4), constrained_layout=True)
for band in BAND_ORDER:                     # niedrig zuerst, hoch zuletzt (oben)
    sub = th[th["band"] == band]
    for uid, g in sub.groupby("uid"):
        ax.plot(g["date"], g["thickness_m"], lw=0.45, alpha=0.28, color=BAND_COL[band], zorder=2)
med = th.groupby("date")["thickness_m"].median()
ax.plot(med.index, med.values, lw=2.4, color="#2f2f2f", zorder=6)
ax.axhline(0.15, color="#555555", lw=0.8, ls="--", zorder=5)
ax.text(pd.Timestamp("2025-10-03"), 0.157, "0.15 m", fontsize=7.2, color="#555555")
handles = [Line2D([0],[0], color=BAND_COL[b], lw=1.8) for b in BAND_ORDER]
labels = [f"{b} (n={th[th['band']==b]['uid'].nunique()})" for b in BAND_ORDER]
handles.append(Line2D([0],[0], color="#2f2f2f", lw=2.4)); labels.append("all-route median")
ax.legend(handles, labels, fontsize=7.2, loc="upper left", ncols=2)
ax.set_ylabel("Modelled ice thickness (m)")
ax.set_xlabel("Date")
ax.set_ylim(0, 1.05)
ax.set_xlim(pd.Timestamp("2025-10-01"), pd.Timestamp("2026-04-30"))
ax.xaxis.set_major_locator(mdates.MonthLocator())
ax.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))
einheitlich(fig); fig.savefig(ABB / "fig_3_2_all_routes.png", dpi=300)
plt.close(fig)
print("all-routes fig done")

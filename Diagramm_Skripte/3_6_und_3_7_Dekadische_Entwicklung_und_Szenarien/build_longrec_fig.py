import pandas as pd, numpy as np
import matplotlib.pyplot as plt
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
df = pd.read_csv(ZWISCHEN / "longrec_winters.csv")   # aus get_longrec_winters.R

def theil_sen(x, y):
    x = np.asarray(x, float); y = np.asarray(y, float)
    sl = np.median([(y[j]-y[i])/(x[j]-x[i]) for i in range(len(x)) for j in range(i+1, len(x)) if x[j] != x[i]])
    return sl, np.median(y - sl*x)

CFG = [
    ("Umhausen",  "#b4554e", "Umhausen (1035 m) – 2.1 km to Dripping Elegance", "-3.8 d/decade (p = 0.003)"),
    ("Brenner",   "#d0993f", "Brenner (1412 m) – 0.97 km to Amphitrite",        "-6.5 d/decade (p < 0.001)"),
    ("Obergurgl", "#183a5a", "Obergurgl (1941 m) – Gurgl valley",               "-0.8 d/decade (p = 0.50)"),
]
fig, axes = plt.subplots(3, 1, figsize=(7.4, 6.4), sharex=True, constrained_layout=True)
for ax, (st, col, label, trendlab) in zip(axes, CFG):
    sub = df[df["station_name"] == st].sort_values("winter_start")
    x, y = sub["winter_start"].values, sub["good_days"].values
    ax.plot(x, y, marker="o", ms=2.8, lw=1.0, color=col, alpha=0.85)
    # 15-Winter gleitender Median
    r = pd.Series(y, index=x).rolling(15, center=True, min_periods=10).median()
    ax.plot(r.index, r.values, lw=2.2, color=col, alpha=0.5)
    sl, ic = theil_sen(x, y)
    ax.plot([x.min(), x.max()], [sl*x.min()+ic, sl*x.max()+ic], ls="--", lw=1.3, color="#2f2f2f",
            label=f"Theil-Sen: {trendlab}")
    p26 = sub[sub["winter_start"] == 2025]
    if len(p26):
        ax.scatter(2025, p26["good_days"].iloc[0], s=60, facecolor="#7b302b",
                   edgecolor="#2f2f2f", zorder=6)
        ax.annotate("2025/26", xy=(2025, float(p26["good_days"].iloc[0])), xytext=(-4, -14),
                    textcoords="offset points", ha="right", fontsize=7.2, color="#7b302b")
    ax.set_ylabel("Proxy days ≥ 0.15 m")
    ax.set_ylim(0, 205)
    ax.legend(fontsize=7.4, loc="upper right")
    ax.set_title(label, loc="left", fontsize=9)
axes[-1].set_xlabel("Winter (starting year)")
axes[-1].set_xlim(1936, 2027)
einheitlich(fig); fig.savefig(ABB / "fig_3_6_longrec.png", dpi=300)
plt.close(fig)
print("longrec fig done")

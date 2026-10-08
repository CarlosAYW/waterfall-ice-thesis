import pandas as pd, numpy as np, json
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
BAND_ORDER = ["<1500 m", "1500-2000 m", "2000-2500 m", ">2500 m"]
BAND_COL = {"<1500 m": "#b4554e", "1500-2000 m": "#d0993f", "2000-2500 m": "#4f8fbd", ">2500 m": "#183a5a"}
SC_COL = {"SSP1-2.6": "#2166ac", "SSP2-4.5": "#e08214", "SSP5-8.5": "#b2182b"}

res = pd.read_pickle(ZWISCHEN / "grid_res_all.pkl")
cur = pd.read_pickle(ZWISCHEN / "grid_cur_all.pkl")
b0 = res[res["delta"]==0].copy()
b0["season_start"] = b0["season"].str[:4].astype(int)
bins = [-np.inf,1500,2000,2500,np.inf]
b0["band"] = pd.cut(b0["icefall_elev_m"], bins=bins, labels=BAND_ORDER)

# ================= dekadischer Proxy, 28 Punkte (nicht mehr in der Arbeit) =================
cur["date"] = pd.to_datetime(cur["date"])
md = cur["date"].dt.strftime("%m-%d")
yr = np.where(cur["date"].dt.month >= 10, 2025, 2026)
cur["plot_date"] = pd.to_datetime(yr.astype(str) + "-" + md, errors="coerce")
cur = cur.dropna(subset=["plot_date"])
daily_med = cur.groupby(["season","plot_date"])["h"].median().reset_index()

fig = plt.figure(figsize=(7.4, 6.2), constrained_layout=True)
gs = fig.add_gridspec(2, 2, height_ratios=[1.25, 1])
axa = fig.add_subplot(gs[0, :])
best, worst = "2017/18", "2023/24"
for s in sorted(daily_med["season"].unique()):
    if s in ("2025/26", best, worst): continue
    sub = daily_med[daily_med["season"]==s].sort_values("plot_date")
    axa.plot(sub["plot_date"], sub["h"], color="#b9b3a8", lw=0.9, alpha=0.75, zorder=2)
for s, col, lab in [(best, "#4f8fbd", f"{best} (best)"), (worst, "#d0993f", f"{worst} (weakest)"),
                    ("2025/26", "#7b302b", "2025/26 (model winter)")]:
    sub = daily_med[daily_med["season"]==s].sort_values("plot_date")
    axa.plot(sub["plot_date"], sub["h"], color=col, lw=2.4 if s=="2025/26" else 1.4, zorder=5 if s=="2025/26" else 3, label=lab)
axa.plot([], [], color="#b9b3a8", lw=0.9, label="other winters")
axa.axhline(0.15, color="#555555", lw=0.8, ls="--")
import matplotlib.dates as mdates
axa.set_ylabel("Proxy ice thickness (m), all-point median")
axa.xaxis.set_major_locator(mdates.MonthLocator())
axa.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
axa.set_xlim(pd.Timestamp("2025-10-01"), pd.Timestamp("2026-04-30"))
axa.set_ylim(0, 0.75)
axa.legend(fontsize=7.4, loc="upper left", ncols=2)
axa.set_title("(a) Seasonal course of all fourteen winters, 2025/26 highlighted", loc="left", fontsize=9)

axb = fig.add_subplot(gs[1, 0])
for band in BAND_ORDER:
    sub = b0[b0["band"]==band].groupby("season_start")["good_days"].median()
    n = b0[b0["band"]==band]["k"].nunique()
    axb.plot(sub.index, sub.values, marker="o", ms=3.0, lw=1.4, color=BAND_COL[band], label=f"{band} (n={n})")
axb.axvline(2025, color="#888888", lw=0.8, ls="--")
axb.set_xlabel("Winter (starting year)")
axb.set_ylabel("Proxy days >= 0.15 m")
axb.set_xticks(range(2012, 2026, 4)); axb.set_ylim(0, 225)
axb.legend(fontsize=6.4, loc="upper right", ncols=2, columnspacing=0.8, handletextpad=0.4)
axb.set_title("(b) Ice days by elevation band", loc="left", fontsize=9)

axc = fig.add_subplot(gs[1, 1])
seasonal = b0.groupby("season_start")["good_days"].median()
q1 = b0.groupby("season_start")["good_days"].quantile(.25)
q3 = b0.groupby("season_start")["good_days"].quantile(.75)
x, y = seasonal.index.to_numpy(), seasonal.values
axc.fill_between(x, q1.values, q3.values, color="#4f8fbd", alpha=0.16, lw=0)
axc.plot(x, y, marker="o", ms=3.6, lw=1.5, color="#183a5a", label="median (IQR shaded)")
sl = np.median([(y[j]-y[i])/(x[j]-x[i]) for i in range(len(x)) for j in range(i+1, len(x))])
ic = np.median(y - sl*x)
axc.plot(x, sl*x+ic, ls="--", lw=1.2, color="#2f2f2f", label=f"Theil-Sen: {sl*10:.0f} d/decade (p = 0.11)")
axc.set_xlabel("Winter (starting year)")
axc.set_ylabel("Proxy days >= 0.15 m")
axc.set_xticks(range(2012, 2026, 4)); axc.set_ylim(0, 200)
axc.legend(fontsize=6.8, loc="lower left")
axc.set_title("(c) All points with trend", loc="left", fontsize=9)
einheitlich(fig); fig.savefig(ABB / "fig_3_6_decadal_proxy.png", dpi=300); plt.close(fig)

# ================= Abb. 32 (Trajektorien) =================
traj = json.load(open(ZWISCHEN / "traj_general.json"))
st = json.load(open(ZWISCHEN / "traj_sites.json"))
SITES = [("9", "Golden Shower (1097 m)"), ("252", "Sunblocker (1480 m)"),
         ("183", "Notwegfall (2163 m)"), ("217", "Sagzahnverschneidung (2549 m)")]
fig = plt.figure(figsize=(7.4, 6.6), constrained_layout=True)
gs = fig.add_gridspec(3, 2, height_ratios=[1.5, 1, 1])
axa = fig.add_subplot(gs[0, :])
for sc, t in traj.items():
    axa.fill_between(t["years"], t["q1"], t["q3"], color=SC_COL[sc], alpha=0.13, lw=0)
    axa.plot(t["years"], t["med"], lw=2.0, color=SC_COL[sc], label=sc)
axa.set_ylabel("Proxy days >= 0.15 m")
axa.set_ylim(0, 175)
axa.set_xlim(2026, 2090)
axa.legend(fontsize=7.8, loc="lower left", title="IPCC AR6 scenario", title_fontsize=7.8)
axa.set_title("(a) All reference points: median and interquartile range", loc="left", fontsize=9)

for k, (uid, name) in enumerate(SITES):
    ax = fig.add_subplot(gs[1 + k//2, k%2])
    for sc in SC_COL:
        ax.plot(st["years"], st["sites"][uid][sc], lw=1.7, color=SC_COL[sc])
    ax.set_ylim(0, 215)
    ax.set_xlim(2026, 2090)
    ax.set_title(f"({'bcde'[k]}) {name}", loc="left", fontsize=8.6)
    if k % 2 == 0: ax.set_ylabel("Days >= 0.15 m")
    if k >= 2: ax.set_xlabel("Year")
einheitlich(fig); fig.savefig(ABB / "fig_3_7_scenarios.png", dpi=300); plt.close(fig)
print("figs 26 + 28 done")

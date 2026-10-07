import pandas as pd, numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pfade import MA, REPO, OUTPUT, ZWISCHEN, abbildungen, schrift, einheitlich  # noqa: E402
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
assign = pd.read_csv(REPO / "data/AWS/icefalls_nearest_station.csv")
AU = set(assign["uid"])
# seit 28.09.2026: Tageswerte aus den finalen Modelllaeufen (uid_daily_drivers.csv, dieselbe Quelle wie
# die Zahlen in Kap. 3.1) statt aus der Nebenrechnung build_results_3_1_station_temperature.R mit der
# alten CAP-Parametrisierung. FDH/PDH sind dort je 10-min-Schritt summiert -> /6 ergibt °C h.
drv = pd.read_csv(ZWISCHEN / "uid_daily_drivers.csv", parse_dates=["date"])
drv = drv[(drv["date"] >= "2025-10-01") & (drv["date"] <= "2026-04-30")]
band = pd.read_csv(ZWISCHEN / "uid_static.csv").set_index("uid")["elevation_band"]
rs = pd.DataFrame({"uid": drv["uid"], "date": drv["date"], "elevation_band": drv["uid"].map(band),
                   "temp_mean_c": drv["TLz_mean"], "temp_min_c": drv["TLz_min"],
                   "fdh": drv["FDH_sum"] / 6.0, "pdh": drv["PDH_sum"] / 6.0})
rs = rs[rs["uid"].isin(AU)]
n = rs["uid"].nunique()
g = rs.groupby("date")["temp_mean_c"]

# ---- Fig 8: temperature distribution ----
fig, ax = plt.subplots(figsize=(7.4, 3.6), constrained_layout=True)
dates = sorted(rs["date"].unique())
ax.fill_between(g.quantile(.10).index, g.quantile(.10).values, g.quantile(.90).values,
                color="#8ab6d6", alpha=0.20, label="P10-P90")
ax.fill_between(g.quantile(.25).index, g.quantile(.25).values, g.quantile(.75).values,
                color="#4f8fbd", alpha=0.30, label="IQR")
ax.plot(g.median().index, g.median().values, color="#183a5a", lw=1.8, label="Route median")
ax.axhline(0, color="#2f2f2f", lw=0.8, ls="--")
ax.set_ylabel("Daily mean TLz (°C)")
ax.set_xlabel("Date")
ax.xaxis.set_major_locator(mdates.MonthLocator())
ax.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))
ax.legend(loc="lower left", ncols=3)
einheitlich(fig); fig.savefig(ABB / "fig_3_1_station_temperature_distribution.png", dpi=300); plt.close(fig)

# ---- Fig 9: freezing share ----
sh_mean = rs.assign(f=rs["temp_mean_c"]<0).groupby("date")["f"].mean()*100
sh_min  = rs.assign(f=rs["temp_min_c"]<0).groupby("date")["f"].mean()*100
fig, ax = plt.subplots(figsize=(7.4, 3.3), constrained_layout=True)
ax.fill_between(sh_mean.index, sh_mean.values, color="#4f8fbd", alpha=0.35, label="Daily mean TLz < 0 °C")
ax.plot(sh_min.index, sh_min.values, color="#183a5a", lw=1.4, label="Daily minimum TLz < 0 °C")
ax.set_ylabel("Share of routes (%)")
ax.set_xlabel("Date")
ax.set_ylim(0, 102)
ax.xaxis.set_major_locator(mdates.MonthLocator())
ax.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))
ax.legend(loc="lower center", ncols=2)
einheitlich(fig); fig.savefig(ABB / "fig_3_1_station_freezing_share.png", dpi=300); plt.close(fig)

# ---- Fig 12: cumulative degree hours by band ----
cum = rs.sort_values("date").groupby(["elevation_band","date"], observed=True)[["fdh","pdh"]].median().groupby(level=0, observed=True).cumsum().reset_index()
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.4, 3.3), constrained_layout=True, sharex=True)
for band in BAND_ORDER:
    sub = cum[cum["elevation_band"]==band]
    nn = rs[rs["elevation_band"]==band]["uid"].nunique()
    ax1.plot(sub["date"], sub["fdh"]/1000, lw=1.6, color=BAND_COL[band], label=f"{band} (n={nn})")
    ax2.plot(sub["date"], sub["pdh"]/1000, lw=1.6, color=BAND_COL[band])
ax1.set_ylabel("Cumulative freezing degree-hours (10³ °C·h)")
ax2.set_ylabel("Cumulative positive degree-hours (10³ °C·h)")
for ax in (ax1, ax2):
    ax.set_xlabel("Date")
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))
ax1.legend(fontsize=6.8, loc="upper left")
ax1.set_title("(a) Freezing degree-hours", loc="left", fontsize=9)
ax2.set_title("(b) Positive degree-hours", loc="left", fontsize=9)
einheitlich(fig); fig.savefig(ABB / "fig_3_1_station_degree_hours_by_elevation.png", dpi=300); plt.close(fig)
print("figs 8/9/12 rebuilt, n =", n, "| bands:", rs.groupby("elevation_band", observed=True)["uid"].nunique().to_dict())

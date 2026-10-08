"""Kap. 3.1, Abb. 15: Wie ungewoehnlich war der Winter 2025/26?

Neun Kennzahlen: Boxplots der Referenzwinter 2012/13-2024/25, roter Punkt fuer 2025/26.

(a)-(e) Temperatur: dieselbe routenuebertragene Stationstemperatur, die das
        Modell antreibt, aus dem Vierzehn-Winter-Lauf von Kap. 3.6
        (FF2_Stationen/ergebnis_modell/tageswerte_voll.rds). Routen an
        homogenen Stationen (route_trends.csv) mit gueltigen Daten in allen
        14 Wintern (feste Zusammensetzung, 107 Routen). Kennzahl je Route und
        Winter, dann Median ueber die Routen.
(f)-(i) Niederschlag und Globalstrahlung: INCA an den 28 geschichteten
        Referenzpunkten (Kap. 3.7), aus inca_reference_point_daily.csv
        von build_inca_winter_reference.R. Die zwei als Nordwand
        umklassifizierten Routen (UID 280, 699) sind ausgeschlossen, Routen in
        derselben INCA-Zelle zaehlen einmal. Tageswerte werden ueber die
        Punkte gemittelt, dann ueber die Saison ausgewertet (wie im R-Skript).

Zeitraum jeweils 1. Oktober bis 30. April.

Ausgabe in <Kapitelordner>/abbildungen:
  fig_3_1_station_winter_reference.png   Abbildung
  station_reference_group_winter.csv     alle Kennzahlen je Winter
  station_reference_comparison.csv       2025/26 gegen Referenz, mit Rang

Benoetigt: pandas, numpy, matplotlib, pyreadr (pip install pyreadr).
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pyreadr

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pfade import MA, OUTPUT, abbildungen, schrift

ABB = abbildungen(__file__)
FF2 = MA / "FF2_Stationen" / "ergebnis_modell"
INCA = OUTPUT / "results_3_1_meteorological_conditions" / "inca_winter_reference"
CUR = 2025
WINTERS = list(range(2012, 2026))
NORTH_FACES = {280, 699}

plt.rcParams.update({"font.family": schrift(), "font.size": 9, "mathtext.default": "regular"})


def longest_run(flags):
    best = cur = 0
    for f in flags:
        cur = cur + 1 if f else 0
        best = max(best, cur)
    return best


# ------------------------------------------------ Temperatur (Stationen)
d = pyreadr.read_r(str(FF2 / "tageswerte_voll.rds"))[None]
d["uid"] = d["uid"].astype(str)
d = d.sort_values(["uid", "winter", "date"])
hom = set(pd.read_csv(FF2 / "tabellen" / "route_trends.csv", dtype={"uid": str})["uid"])
d = d[d["uid"].isin(hom)]
n_win = d.groupby("uid")["winter"].nunique()
fixed = set(n_win[n_win == len(WINTERS)].index)
d = d[d["uid"].isin(fixed)]
rw = (d.groupby(["uid", "winter"])
        .agg(mean_T=("TLz_mean", "mean"),
             frost_days=("TLz_mean", lambda s: int((s < 0).sum())),
             spell=("TLz_mean", lambda s: longest_run((s < 0).values)),
             fdh=("fdh_Ch", "sum"),
             pdh=("pdh_Ch", "sum"))
        .reset_index())
temp = rw.groupby("winter")[["mean_T", "frost_days", "spell", "fdh", "pdh"]].median()
temp["n_routes"] = rw.groupby("winter")["uid"].nunique()

# ------------------------------------------------ Niederschlag, Strahlung (INCA)
cov = pd.read_csv(INCA / "inca_reference_hourly_coverage.csv")
cells = (cov[~cov["uid"].isin(NORTH_FACES)].groupby("uid")[["api_lat", "api_lon"]].first()
         .reset_index().drop_duplicates(["api_lat", "api_lon"]))
keep = set(cells["uid"])
pdly = pd.read_csv(INCA / "inca_reference_point_daily.csv", parse_dates=["date"])
pdly = pdly[pdly["uid"].isin(keep) & (pdly["calendar_md"] != "02-29")]
area = (pdly.groupby(["season_start_year", "date"])
            .agg(rr=("rr_mm", "mean"), gl=("gl_mj_m2", "mean"), n_points=("uid", "nunique"))
            .reset_index().sort_values(["season_start_year", "date"]))
rows = []
for w, g in area.groupby("season_start_year"):
    rows.append(dict(winter=w, precip=g["rr"].sum(), wet_days=int((g["rr"] >= 1).sum()),
                     dry_spell=longest_run((g["rr"] < 1).values),
                     gl_spring=g.loc[g["date"].dt.month.isin([3, 4]), "gl"].sum(),
                     n_points=int(g["n_points"].median())))
inca = pd.DataFrame(rows).set_index("winter")

tab = temp.join(inca, how="inner")
assert list(tab.index) == WINTERS, tab.index
tab.to_csv(ABB / "station_reference_group_winter.csv", float_format="%.3f")

METRICS = [  # Spalte, Titel, Quelle
    ("mean_T", "(a) Mean air temperature (°C)", "station"),
    ("frost_days", "(b) Days with daily mean < 0 °C", "station"),
    ("spell", "(c) Longest freezing spell (days)", "station"),
    ("fdh", "(d) Freezing degree-hours (°C h)", "station"),
    ("pdh", "(e) Positive degree-hours (°C h)", "station"),
    ("precip", "(f) Total precipitation (mm)", "INCA"),
    ("wet_days", "(g) Precipitation days ≥ 1 mm", "INCA"),
    ("dry_spell", "(h) Longest dry spell < 1 mm d$^{-1}$ (days)", "INCA"),
    ("gl_spring", "(i) Mar–Apr global radiation (MJ m$^{-2}$)", "INCA"),
]
comp = []
for m, title, src in METRICS:
    ref = tab.loc[tab.index != CUR, m]
    cur = tab.loc[CUR, m]
    comp.append(dict(metric=m, source=src, current=cur, ref_median=ref.median(),
                     ref_p25=ref.quantile(0.25), ref_p75=ref.quantile(0.75),
                     ref_min=ref.min(), ref_max=ref.max(),
                     rank_high_to_low=int((tab[m] > cur).sum() + 1),
                     rank_low_to_high=int((tab[m] < cur).sum() + 1)))
comp = pd.DataFrame(comp)
comp.to_csv(ABB / "station_reference_comparison.csv", index=False, float_format="%.3f")
print(f"Temperatur: {len(fixed)} Routen; INCA: {len(keep)} Punkte (Median je Tag {int(inca.n_points.median())})")
print(comp.to_string(index=False, float_format=lambda v: f"{v:.2f}"))

# ------------------------------------------------ Abbildung
BOX_FILL, BOX_EDGE, RED = "#d9e2ec", "#52616b", "#b13d2e"
fig, axs = plt.subplots(3, 3, figsize=(7.4, 6.0))
for ax, (m, title, src) in zip(axs.ravel(), METRICS):
    ref = tab.loc[tab.index != CUR, m].values
    ax.boxplot(ref, positions=[0], widths=0.42, patch_artist=True, whis=1.5,
               boxprops=dict(facecolor=BOX_FILL, edgecolor=BOX_EDGE, lw=0.8),
               medianprops=dict(color=BOX_EDGE, lw=1.8),
               whiskerprops=dict(color=BOX_EDGE, lw=0.8), capprops=dict(lw=0),
               flierprops=dict(marker="o", markersize=3.2, markerfacecolor=BOX_EDGE,
                               markeredgecolor=BOX_EDGE))
    ax.scatter([0], [tab.loc[CUR, m]], s=42, color=RED, edgecolor="white", lw=0.8, zorder=5)
    ax.set_xlim(-0.6, 0.6)
    ax.set_xticks([])
    ax.set_title(title, fontsize=8.2, fontweight="bold", color="#222222", pad=4)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(axis="y", length=0, labelsize=7.8, colors="#444444")
    ax.grid(axis="y", color="#dedede", lw=0.5)
    ax.set_axisbelow(True)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(
        lambda v, _p: f"{v:,.0f}".replace(",", " ").replace("-", "−") if abs(v) >= 100 or v == int(v)
        else f"{v:.1f}".replace("-", "−")))
fig.subplots_adjust(left=0.08, right=0.985, top=0.95, bottom=0.03, hspace=0.32, wspace=0.28)
fig.savefig(ABB / "fig_3_1_station_winter_reference.png", dpi=300, facecolor="white")
print("Abbildung:", ABB / "fig_3_1_station_winter_reference.png")

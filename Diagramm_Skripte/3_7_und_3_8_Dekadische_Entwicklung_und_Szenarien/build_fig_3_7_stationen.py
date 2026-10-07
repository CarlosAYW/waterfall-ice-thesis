# -*- coding: utf-8 -*-
"""Abbildungen fuer Kap. 3.7 aus der stationsbasierten Neuberechnung (FF2).

Liest die Tabellen, die FF2_Stationen/02_ff2_modelllauf.R nach
FF2_Stationen/ergebnis_modell/tabellen schreibt, und erzeugt in
<Kapitelordner>/abbildungen:

  fig_3_7_homogeneity.png       Homogenitaetspruefung der Temperaturstationen
  fig_3_7_decadal_stations.png  Dekadische Entwicklung, Layout wie die fruehere
                                Abb. 32 (fig_3_6_decadal_proxy.png aus build_fig2628.py)

Auswertungsmenge wie im R-Skript: Routen an homogenen Stationen mit mindestens
10 gueltigen Wintern und mindestens 4 je Haelfte (= Routen in route_trends.csv).

(a) Saisonverlauf: Tagesmedian der Eisdicke ueber die Routen mit allen 14
    Wintern (feste Zusammensetzung).
(b), (c) Eistage je Winter, bereinigt um die Zusammensetzung: Median der
    Routenanomalien (Eistage minus Mittel der Route) plus Median der
    Routenmittel der Gruppe. So verschieben Routen, denen einzelne Winter
    fehlen, die Kurven nicht. Trend der Kurve in (c): Theil-Sen, Mann-Kendall.

Das Skript prueft seine Reihen gegen anomalie_reihen.csv und band_trends.csv
aus dem R-Lauf und bricht ab, wenn sie nicht uebereinstimmen.
"""
import math
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pfade import MA, abbildungen, schrift, einheitlich  # noqa: E402

ABB = abbildungen(__file__)
TAB = MA / "FF2_Stationen" / "ergebnis_modell" / "tabellen"

plt.rcParams.update({
    "font.family": schrift(), "font.size": 8.8,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": "#d9d9d9",
    "grid.linewidth": 0.6, "grid.alpha": 0.6, "legend.frameon": False,
})
BAND_ORDER = ["<1500 m", "1500-2000 m", "2000-2500 m", ">2500 m"]
BAND_COL = {"<1500 m": "#b4554e", "1500-2000 m": "#d0993f", "2000-2500 m": "#4f8fbd", ">2500 m": "#183a5a"}
THRESH_M = 0.15
WINTERS = list(range(2012, 2026))
MINUS = "−"


def wl(y):
    return f"{y}/{(y + 1) % 100:02d}"


def num(x, fmt):
    return format(x, fmt).replace("-", MINUS)


def theil_sen(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    i, j = np.triu_indices(len(x), 1)
    b = np.median((y[j] - y[i]) / (x[j] - x[i]))
    return b, np.median(y - b * x)


def mann_kendall_p(y):
    """Zweiseitiges p mit Bindungskorrektur, wie mann_kendall() im R-Skript."""
    y = np.asarray(y, float)
    n = len(y)
    s = sum(np.sign(y[k + 1:] - y[k]).sum() for k in range(n - 1))
    _, t = np.unique(y, return_counts=True)
    v = (n * (n - 1) * (2 * n + 5) - np.sum(t * (t - 1) * (2 * t + 5))) / 18
    z = (s - 1) / np.sqrt(v) if s > 0 else (s + 1) / np.sqrt(v) if s < 0 else 0.0
    return math.erfc(abs(z) / math.sqrt(2))       # = 2 * (1 - Phi(|z|))


# ------------------------------------------------------------------ Daten --
hom = pd.read_csv(TAB / "stationen_homogenitaet.csv", dtype={"station_id": str})
hser = pd.read_csv(TAB / "stationen_differenzreihen.csv", dtype={"station_id": str})
tr = pd.read_csv(TAB / "route_trends.csv", dtype={"uid": str, "station_id": str})
rw = pd.read_csv(TAB / "route_winter_voll.csv", dtype={"uid": str, "station_id": str})
sv = pd.read_csv(TAB / "saisonverlauf_routen_alle_winter.csv", parse_dates=["date"])
an_r = pd.read_csv(TAB / "anomalie_reihen.csv")
bt = pd.read_csv(TAB / "band_trends.csv").set_index("group")

hom["inhomogeneous"] = hom["inhomogeneous"].astype(str).str.upper().eq("TRUE")
bad = set(hom.loc[hom["inhomogeneous"], "station_id"])
rw = rw[~rw["station_id"].isin(bad) & rw["uid"].isin(tr["uid"])].copy()
assert not tr["station_id"].isin(bad).any(), "route_trends.csv enthaelt Routen an inhomogenen Stationen"
rw["anom"] = rw["ice_days"] - rw["uid"].map(tr.set_index("uid")["mean_days"])
n_full = int((tr["n_winters"] == len(WINTERS)).sum())
print(f"Routen: {tr['uid'].nunique()}, Stationen: {tr['station_id'].nunique()}, "
      f"Routen-Winter: {len(rw)}, Routen mit allen Wintern: {n_full}, inhomogene Stationen: {len(bad)}")

GROUPS = {b: [b] for b in BAND_ORDER}
GROUPS["all routes"] = BAND_ORDER


def series(group):
    bands = GROUPS[group]
    d = rw[rw["band"].isin(bands)]
    clim = tr.loc[tr["band"].isin(bands), "mean_days"].median()
    g = d.groupby("winter")["anom"]
    s = pd.DataFrame({"n": g.size(), "med": g.median(), "q1": g.quantile(0.25), "q3": g.quantile(0.75)})
    s = s.reindex(WINTERS)
    s["level"], s["lo"], s["hi"] = clim + s["med"], clim + s["q1"], clim + s["q3"]
    return s, clim, int(tr["band"].isin(bands).sum())


SER = {g: series(g) for g in GROUPS}

# Abgleich mit dem R-Lauf
for g, (s, clim, n) in SER.items():
    r = an_r[an_r["group"] == g].set_index("winter").reindex(WINTERS)
    assert np.allclose(r["anom_med"], s["med"]), f"Anomaliereihe {g} weicht von anomalie_reihen.csv ab"
    assert np.isclose(bt.loc[g, "clim_days"], clim) and bt.loc[g, "n_routes"] == n, f"Gruppe {g} weicht ab"

s_all = SER["all routes"][0]
best, worst = int(s_all["med"].idxmax()), int(s_all["med"].idxmin())
slope, icpt = theil_sen(WINTERS, s_all["level"])
p_all = mann_kendall_p(s_all["level"])
for g, (s, _, n) in SER.items():
    b, _ = theil_sen(WINTERS, s["level"])
    print(f"  {g:12s} n = {n:3d}  Kurventrend {10 * b:+6.1f} d/Dekade  p = {mann_kendall_p(s['level']):.2f}")
print(f"  bester Winter {wl(best)}, schwaechster {wl(worst)}")

# ============================================== Abb.: Homogenitaet =========
flag = hom[hom["inhomogeneous"]].copy()
flag = flag.reindex(flag["shift_K"].abs().sort_values(ascending=False).index)
ok_ids = sorted(set(hser["station_id"]) - bad)
ncol = 5
nrow = int(np.ceil(len(flag) / ncol))
fig, axs = plt.subplots(nrow, ncol, figsize=(7.4, 1.75 * nrow + 0.5), sharex=True, sharey=True,
                        constrained_layout=True)
axs = np.atleast_2d(axs)
for k, ax in enumerate(axs.flat):
    if k >= len(flag):
        ax.set_visible(False)
        continue
    st = flag.iloc[k]
    for sid in ok_ids:
        o = hser[hser["station_id"] == sid].sort_values("winter")
        ax.plot(o["winter"], o["D"], color="#c8c8c8", lw=0.5, zorder=1)
    ax.axhline(0, color="#6f6f6f", lw=0.6, zorder=2)
    me = hser[hser["station_id"] == st["station_id"]].sort_values("winter")
    ax.plot(me["winter"], me["D"], color="#b4554e", lw=1.3, marker="o", ms=2.2, zorder=4)
    if pd.notna(st["break_after"]):
        b = int(st["break_after"])
        pre, post = me[me["winter"] <= b], me[me["winter"] > b]
        ax.plot([pre["winter"].min(), b + 0.5], [pre["D"].mean()] * 2, color="#183a5a", lw=1.1, ls="--", zorder=3)
        ax.plot([b + 0.5, post["winter"].max()], [post["D"].mean()] * 2, color="#183a5a", lw=1.1, ls="--", zorder=3)
    shift_crit = abs(st["shift_K"]) >= 0.5 and st["p_perm"] < 0.1
    lab = (f"{st['station_id']}  {num(st['shift_K'], '+.1f')} K, p = {st['p_perm']:.3f}" if shift_crit
           else f"{st['station_id']}  SD {st['sd_K']:.1f} K")
    ax.set_title(lab, fontsize=7.8, loc="left")
    ax.grid(axis="x", visible=False)
ax0 = axs.flat[0]
ax0.set_ylim(-5.8, 3.6)
ax0.set_xlim(2011.5, 2025.5)
ax0.set_xticks([2014, 2020])
ax0.set_xticklabels([wl(2014), wl(2020)])
for ax in axs.flat:
    ax.tick_params(labelsize=7.4)
fig.supylabel("Station minus regional median, winter mean (K)", fontsize=8.4)
einheitlich(fig); fig.savefig(ABB / "fig_3_7_homogeneity.png", dpi=300)
plt.close(fig)

# ======================================= Abb.: Dekadische Entwicklung ======
sv["plot_date"] = pd.to_datetime(
    np.where(sv["date"].dt.month >= 10, "2025", "2026") + "-" + sv["date"].dt.strftime("%m-%d"),
    errors="coerce")
sv = sv.dropna(subset=["plot_date"])                      # 29. Februar entfaellt
assert sv["n_routes"].eq(n_full).all()

fig = plt.figure(figsize=(7.4, 6.2), constrained_layout=True)
gs = fig.add_gridspec(2, 2, height_ratios=[1.25, 1])
axa = fig.add_subplot(gs[0, :])
for w in WINTERS:
    if w in (2025, best, worst):
        continue
    sub = sv[sv["winter"] == w].sort_values("plot_date")
    axa.plot(sub["plot_date"], sub["thickness_m"], color="#b9b3a8", lw=0.9, alpha=0.75, zorder=2)
for w, col, lab in [(best, "#4f8fbd", f"{wl(best)} (best)"), (worst, "#d0993f", f"{wl(worst)} (weakest)"),
                    (2025, "#7b302b", "2025/26 (model winter)")]:
    sub = sv[sv["winter"] == w].sort_values("plot_date")
    axa.plot(sub["plot_date"], sub["thickness_m"], color=col, lw=2.4 if w == 2025 else 1.4,
             zorder=5 if w == 2025 else 3, label=lab)
axa.plot([], [], color="#b9b3a8", lw=0.9, label="other winters")
axa.axhline(THRESH_M, color="#555555", lw=0.8, ls="--")
axa.set_ylabel(f"Ice thickness (m), median of {n_full} routes")
axa.xaxis.set_major_locator(mdates.MonthLocator())
axa.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
axa.set_xlim(pd.Timestamp("2025-10-01"), pd.Timestamp("2026-04-30"))
axa.set_ylim(0, 0.65)
axa.legend(fontsize=7.4, loc="upper left", ncols=2)
axa.set_title("(a) Seasonal course of all fourteen winters, 2025/26 highlighted", loc="left", fontsize=9)

axb = fig.add_subplot(gs[1, 0])
for band in BAND_ORDER:
    s, _, n = SER[band]
    axb.plot(WINTERS, s["level"], marker="o", ms=3.0, lw=1.4, color=BAND_COL[band], label=f"{band} (n={n})")
axb.axvline(2025, color="#888888", lw=0.8, ls="--")
axb.set_xlabel("Winter (starting year)")
axb.set_ylabel("Days with ice ≥ 0.15 m")
axb.set_xticks(range(2012, 2026, 4))
axb.set_ylim(0, 260)
axb.legend(fontsize=6.4, loc="upper left", ncols=2, columnspacing=0.8, handletextpad=0.4)
axb.set_title("(b) Climbable-ice days by elevation band", loc="left", fontsize=9)

axc = fig.add_subplot(gs[1, 1])
x = np.array(WINTERS)
axc.fill_between(x, s_all["lo"], s_all["hi"], color="#4f8fbd", alpha=0.16, lw=0)
axc.plot(x, s_all["level"], marker="o", ms=3.6, lw=1.5, color="#183a5a", label="median (IQR of route anomalies shaded)")
axc.plot(x, slope * x + icpt, ls="--", lw=1.2, color="#2f2f2f",
         label=f"Theil–Sen: {num(10 * slope, '.0f')} d/decade (p = {p_all:.2f})")
ra = bt.loc["all routes"]
axc.text(0.98, 0.97,
         f"Route trends ({int(ra['n_routes'])} routes):\nmedian {num(ra['slope_med'], '.1f')} d/decade,\n"
         f"95% CI {num(ra['ci_lo'], '.1f')} to {num(ra['ci_hi'], '.1f')},\n{ra['share_neg']:.0%} of routes negative",
         transform=axc.transAxes, ha="right", va="top", fontsize=6.6, color="#2f2f2f")
axc.set_xlabel("Winter (starting year)")
axc.set_ylabel("Days with ice ≥ 0.15 m")
axc.set_xticks(range(2012, 2026, 4))
axc.set_ylim(0, 200)
axc.legend(fontsize=6.8, loc="lower left")
axc.set_title("(c) All routes with trend", loc="left", fontsize=9)
einheitlich(fig); fig.savefig(ABB / "fig_3_7_decadal_stations.png", dpi=300)
plt.close(fig)
print("Abbildungen geschrieben nach", ABB)

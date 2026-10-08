"""Figures + stats for sections 3.3 (spatial) and 3.4 (met controls)."""
import json
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
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
GOOD_M = 0.15
ICE_M = 0.05
THRESH = 0.005

static = pd.read_csv(ZWISCHEN / "uid_static.csv")
assign = pd.read_csv(REPO / "data/AWS/icefalls_nearest_station.csv")
AU = set(assign["uid"])
static = static[static["uid"].isin(AU)].copy()
drv = pd.read_csv(ZWISCHEN / "uid_daily_drivers.csv", parse_dates=["date"])
drv = drv[drv["uid"].isin(AU)].copy()
uidd = pd.read_pickle(ZWISCHEN / "uid_daily_320.pkl")

# ---- per-route season metrics ----
drv = drv.sort_values(["uid", "date"])
drv["delta_m"] = drv.groupby("uid")["thickness_last"].diff()
drv["phase"] = np.select([drv["delta_m"] > THRESH, drv["delta_m"] < -THRESH],
                         ["growth", "melt"], default="stable")

thick = uidd[["uid", "date", "thickness_m"]]
seas_th = thick.groupby("uid").agg(
    peak_m=("thickness_m", "max"),
    good_days=("thickness_m", lambda s: int((s >= GOOD_M).sum())),
    ice_days=("thickness_m", lambda s: int((s >= ICE_M).sum())),
)
djf = drv[(drv["date"] >= "2025-12-01") & (drv["date"] <= "2026-02-28")]
seas_dr = drv.groupby("uid").agg(
    FDH_tot=("FDH_sum", "sum"), PDH_tot=("PDH_sum", "sum"),
    SW_tot=("sw_abs_mj", "sum"), RF_mean=("RF_mean", "mean"),
    wind_mean=("wind_mean", "mean"), growth_tot=("growth_mm", "sum"),
    melt_tot=("melt_mm", "sum"),
)
sun_djf = djf.groupby("uid")["sun_h"].mean().rename("sun_djf_h")
seas = (seas_th.join(seas_dr).join(sun_djf).reset_index()
        .merge(static, on="uid", how="left"))

def sector(deg):
    if not np.isfinite(deg): return np.nan
    d = deg % 360
    if d >= 315 or d < 45: return "N"
    if d < 135: return "E"
    if d < 225: return "S"
    return "W"
seas["aspect_sector"] = seas["aspect_deg"].map(sector)
seas.to_csv(ZWISCHEN / "uid_season_metrics.csv", index=False)

band_daily = (thick.merge(static[["uid", "elevation_band"]], on="uid")
              .groupby(["elevation_band", "date"], observed=True)["thickness_m"].median()
              .reset_index())

# =============== FIG 3.3-1: elevation ===============
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.4, 3.4), constrained_layout=True,
                               gridspec_kw={"width_ratios": [1.7, 1]})
for band in BAND_ORDER:
    sub = band_daily[band_daily["elevation_band"] == band]
    n = (seas["elevation_band"] == band).sum()
    ax1.plot(sub["date"], sub["thickness_m"], lw=1.6, color=BAND_COL[band],
             label=f"{band} (n={n})")
ax1.set_ylabel("Median modelled ice thickness (m)")
ax1.set_xlabel("Date")
ax1.legend(loc="upper left", fontsize=7.6)
ax1.xaxis.set_major_locator(mdates.MonthLocator())
ax1.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))
ax1.set_title("(a) Seasonal course by elevation band", loc="left", fontsize=9)

data = [seas.loc[seas["elevation_band"] == b, "good_days"].dropna() for b in BAND_ORDER]
bp = ax2.boxplot(data, tick_labels=[b.replace(" m", "") for b in BAND_ORDER],
                 patch_artist=True, widths=0.6, showfliers=False)
for patch, b in zip(bp["boxes"], BAND_ORDER):
    patch.set_facecolor(BAND_COL[b]); patch.set_alpha(0.6)
for med in bp["medians"]:
    med.set_color("#2f2f2f"); med.set_linewidth(1.5)
ax2.set_ylabel(f"Days with thickness >= {GOOD_M} m")
ax2.set_xlabel("Elevation band (m)")
ax2.tick_params(axis="x", labelsize=7.3)
ax2.set_title("(b) Climbable-ice days by elevation", loc="left", fontsize=9)
einheitlich(fig); fig.savefig(ABB / "fig_3_3_elevation.png", dpi=300); plt.close(fig)

# =============== FIG 3.3-2: aspect / sun / CAP ===============
fig, axes = plt.subplots(1, 3, figsize=(7.4, 3.35), constrained_layout=True)
axa, axb, axc = axes

order = ["N", "E", "S", "W"]
data = [seas.loc[seas["aspect_sector"] == a, "good_days"].dropna() for a in order]
bp = axa.boxplot(data, tick_labels=[f"{a}\n(n={len(d)})" for a, d in zip(order, data)],
                 patch_artist=True, widths=0.6, showfliers=False)
for patch in bp["boxes"]:
    patch.set_facecolor("#4f8fbd"); patch.set_alpha(0.55)
for med in bp["medians"]:
    med.set_color("#183a5a"); med.set_linewidth(1.6)
axa.set_ylabel(f"Days with thickness >= {GOOD_M} m")
axa.set_title("(a) Aspect sector", loc="left", fontsize=9)

for band in BAND_ORDER:
    sub = seas[seas["elevation_band"] == band]
    axb.scatter(sub["sun_djf_h"], sub["good_days"], s=13, color=BAND_COL[band],
                alpha=0.65, lw=0, label=band)
rho_sun = seas[["sun_djf_h", "good_days"]].corr(method="spearman").iloc[0, 1]
axb.text(0.97, 0.95, f"rho = {rho_sun:.2f}", transform=axb.transAxes, ha="right",
         va="top", fontsize=8, color="#2f2f2f",
         zorder=8)
axb.set_ylim(0, float(seas["good_days"].max()) * 1.16)   # Kopffreiheit fuer das Label
axb.set_xlabel("Mean DJF topographic sun window (h/d)")
axb.set_title("(b) Winter sun exposure", loc="left", fontsize=9)

# (c) Wirkung des CAP-Terms aus dem kontrafaktischen Lauf (cap_kontrafaktisch.py).
capk = ZWISCHEN / "cap_kontra_routen.csv"
if not capk.exists():
    sys.exit("cap_kontra_routen.csv fehlt - zuerst cap_kontrafaktisch.py laufen lassen.")
ck = pd.read_csv(capk)
for band in BAND_ORDER:
    sub = ck[ck["elevation_band"] == band]
    axc.scatter(sub["cap_delta"], sub["d_ice_days"], s=13, color=BAND_COL[band],
                alpha=0.65, lw=0, label=band)
b1, b0 = np.polyfit(ck["cap_delta"], ck["d_ice_days"], 1)
xx = np.linspace(ck["cap_delta"].min(), ck["cap_delta"].max(), 50)
axc.plot(xx, b0 + b1 * xx, color="#2f2f2f", lw=1.1)
axc.axhline(0, color="#8a8a8a", lw=0.6, zorder=0)
rho_cap = ck[["cap_delta", "d_ice_days"]].corr(method="spearman").iloc[0, 1]
axc.text(0.03, 0.95, f"rho = {rho_cap:.2f}", transform=axc.transAxes, va="top", fontsize=8,
         color="#2f2f2f", zorder=8)
axc.set_xlabel("CAP surplus \u03b4CAP (\u2013)")
axc.set_ylabel("\u0394 climbable-ice days (CAP on \u2212 off)")
axc.set_title("(c) Effect of the CAP term", loc="left", fontsize=9)
# Gemeinsame Legende fuer (b) und (c) unter der Abbildung.
hb, lb = axb.get_legend_handles_labels()
fig.legend(hb, lb, loc="outside lower center", ncol=4, fontsize=7.6, markerscale=1.5,
           handletextpad=0.3, columnspacing=1.8)
einheitlich(fig); fig.savefig(ABB / "fig_3_3_aspect_sun_cap.png", dpi=300); plt.close(fig)

# =============== FIG 3.4-1: thermal window ===============
drv2 = drv.dropna(subset=["delta_m"]).copy()
drv2["thick_prev0"] = drv2.groupby("uid")["thickness_last"].shift()
noice = (drv2["thick_prev0"] < 0.005) & (drv2["thickness_last"] < 0.005)
drv2["phase4"] = np.where(noice, "no_ice", drv2["phase"])
bins = np.arange(-20, 12, 2)
drv2["tbin"] = pd.cut(drv2["TLz_mean"], bins=bins)
share = (drv2.groupby("tbin", observed=True)["phase4"]
         .value_counts(normalize=True).unstack(fill_value=0))
centers = [iv.mid for iv in share.index]

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.4, 3.3), constrained_layout=True)
ax1.stackplot(centers, share.get("growth", 0) * 100, share.get("stable", 0) * 100,
              share.get("melt", 0) * 100, share.get("no_ice", 0) * 100,
              labels=["Growth", "Stable (ice)", "Melt", "Ice-free"],
              colors=["#4c956c", "#d8d1c4", "#c9584f", "#f4f1ea"], alpha=0.88)
ax1.axvline(0, color="#2f2f2f", lw=0.8, ls="--")
ax1.set_xlabel("Daily mean TLz (°C)")
ax1.set_ylabel("Share of route-days (%)")
ax1.set_xlim(-19, 11); ax1.set_ylim(0, 100)
ax1.legend(loc="center left", fontsize=7.6)
ax1.set_title("(a) Phase shares vs. daily temperature", loc="left", fontsize=9)

drv2["thick_prev"] = drv2.groupby("uid")["thickness_last"].shift()
spring = drv2[(drv2["date"] >= "2026-03-01") & (drv2["thick_prev"] >= 0.05)].copy()
spring["sun_grp"] = pd.cut(spring["sun_h"].fillna(0), [-0.1, 0.5, 4, 24],
                           labels=["shaded (<=0.5 h)", "0.5-4 h", ">4 h"])
for g, col in zip(["shaded (<=0.5 h)", "0.5-4 h", ">4 h"],
                  ["#183a5a", "#d0993f", "#c9584f"]):
    sub = spring[spring["sun_grp"] == g]
    sh = (sub.groupby("tbin", observed=True)["phase"]
          .value_counts(normalize=True).unstack(fill_value=0))
    if "melt" in sh:
        cnt = sub.groupby("tbin", observed=True).size()
        sh = sh[cnt >= 30]
        ax2.plot([iv.mid for iv in sh.index], sh["melt"] * 100, lw=1.7, color=col,
                 marker="o", ms=3.2, label=g)
ax2.axvline(0, color="#2f2f2f", lw=0.8, ls="--")
ax2.set_xlabel("Daily mean TLz (°C)")
ax2.set_ylabel("Melt-day share (%)")
ax2.set_ylim(0, 100)
ax2.set_xlim(-5.6, 5.6)                      # auf den Uebergangsbereich zuschneiden
ax2.set_xticks(range(-5, 6))
ax2.legend(fontsize=7.3, title="Topographic sun window", title_fontsize=7.3, loc="upper left")
ax2.set_title("(b) Spring melt share by sun exposure (ice present)", loc="left", fontsize=9)
einheitlich(fig); fig.savefig(ABB / "fig_3_4_thermal_window.png", dpi=300); plt.close(fig)

# =============== FIG 3.4-2: seasonal controls ===============
drivers = {
    "Freezing degree-hours": "FDH_tot", "Positive degree-hours": "PDH_tot",
    "Absorbed shortwave rad.": "SW_tot", "Mean rel. humidity": "RF_mean",
    "Mean wind speed": "wind_mean", "DJF sun window": "sun_djf_h",
    "CAP surplus": "cap_delta_positive", "Elevation": "z_target_m",
}
rows = []
for lab, col in drivers.items():
    for resp, rl in [("peak_m", "Seasonal peak thickness"), ("good_days", "Ice days >= 0.15 m")]:
        sub = seas[[col, resp]].dropna()
        rho = sub.corr(method="spearman").iloc[0, 1]
        rows.append({"driver": lab, "resp": rl, "rho": rho, "n": len(sub)})
rhodf = pd.DataFrame(rows)
rhodf.to_csv(ZWISCHEN / "spearman_controls.csv", index=False)

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.4, 3.9), constrained_layout=True,
                               gridspec_kw={"width_ratios": [1, 1.3]})
for band in BAND_ORDER:
    sub = seas[seas["elevation_band"] == band]
    # FDH_tot ist die Summe je 10-min-Schritt; /6 -> °C h, /1000 -> 10³ °C h
    ax1.scatter(sub["FDH_tot"] / 6000, sub["peak_m"], s=13, color=BAND_COL[band],
                alpha=0.65, lw=0, label=band)
rho_fdh = seas[["FDH_tot", "peak_m"]].corr(method="spearman").iloc[0, 1]
ax1.text(0.03, 0.97, f"rho = {rho_fdh:.2f}", transform=ax1.transAxes, va="top", fontsize=8)
ax1.set_xlabel("Seasonal freezing degree-hours (10\u00b3 \u00b0C\u00b7h)")
ax1.set_ylabel("Seasonal peak thickness (m)")
ax1.legend(fontsize=6.6, loc="lower right", handletextpad=0.15)
ax1.set_title("(a) Thermal forcing vs. peak thickness", loc="left", fontsize=9)

# (b) direkte Wirkung der Faktoren je Route
# (faktoren_kontrafaktisch.py: jede Route ohne den Faktor nachgerechnet, +-1 K als Massstab).
# Die Spearman-Tabelle wird oben weiter berechnet (spearman_controls.csv, Zahlen im Text).
import faktoren_kontrafaktisch as fk
fkcsv = ZWISCHEN / "faktoren_kontra_routen.csv"
if not fkcsv.exists():
    sys.exit("faktoren_kontra_routen.csv fehlt - zuerst faktoren_kontrafaktisch.py laufen lassen.")
FR = fk.wirkungen(pd.read_csv(fkcsv))
fk.panel_direkte_wirkung(ax2, FR, fontsize=7.3, punkt=4)
ax2.set_xlabel("Change in days with ice \u2265 0.15 m (with \u2212 without)")
ax2.set_title(f"(b) Direct effect per route (n = {len(FR)})", loc="left", fontsize=9)
einheitlich(fig); fig.savefig(ABB / "fig_3_4_seasonal_controls.png", dpi=300); plt.close(fig)

# =============== stats for text ===============
# Terzile des CAP-Surplus als Vergleichswert in stats_3_3_3_4.json
capq = seas.dropna(subset=["cap_delta_positive"]).copy()
capq["cap_grp"] = pd.qcut(capq["cap_delta_positive"], 3, labels=["weak", "moderate", "strong"])
def med_iqr(s):
    return [round(float(s.median()), 3), round(float(s.quantile(.25)), 3),
            round(float(s.quantile(.75)), 3)]

stats = {
    "n_runs": int(seas["uid"].nunique()),
    "good_days_by_band": {b: med_iqr(seas.loc[seas["elevation_band"] == b, "good_days"])
                          for b in BAND_ORDER},
    "peak_by_band": {b: med_iqr(seas.loc[seas["elevation_band"] == b, "peak_m"])
                     for b in BAND_ORDER},
    "good_days_by_aspect": {a: med_iqr(seas.loc[seas["aspect_sector"] == a, "good_days"])
                            for a in order},
    "n_by_aspect": {a: int((seas["aspect_sector"] == a).sum()) for a in order},
    "good_days_by_cap": {g: med_iqr(capq.loc[capq["cap_grp"] == g, "good_days"])
                         for g in ["weak", "moderate", "strong"]},
    "rho_sun_gooddays": round(float(rho_sun), 3),
    "rho_fdh_peak": round(float(rho_fdh), 3),
    "spearman_table": rhodf.round(3).to_dict("records"),
    "tlz_bin_growth_share_max": {str(iv): round(float(v), 3) for iv, v in
                                 share.get("growth", pd.Series()).items()},
    "share_growth_below_minus8": round(float(
        drv2[drv2["TLz_mean"] < -8]["phase"].eq("growth").mean()), 3),
    "share_melt_above_2": round(float(
        drv2[drv2["TLz_mean"] > 2]["phase"].eq("melt").mean()), 3),
    "never_good_share": round(float((seas["good_days"] == 0).mean()), 3),
    "routes_never_good": int((seas["good_days"] == 0).sum()),
}
json.dump(stats, open(ZWISCHEN / "stats_3_3_3_4.json", "w"), indent=2)
print(json.dumps(stats, indent=2)[:2600])

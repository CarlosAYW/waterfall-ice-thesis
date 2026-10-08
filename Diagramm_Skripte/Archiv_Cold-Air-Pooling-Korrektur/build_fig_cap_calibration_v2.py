"""CAP-Kalibrierung (nicht mehr in der Arbeit).

(a) Schaetzwerte je Teilmenge fuer beide Modellvarianten mit geblockten 95 %-KI
(b) Schaetzwert gegen mittleres Gate: mit fester Lapse Rate faellt er ab, mit
    stabilitaetsabhaengiger Lapse Rate ist er teilmengenunabhaengig
"""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pfade import MA, REPO, OUTPUT, ZWISCHEN, abbildungen, schrift
ABB = abbildungen(__file__)   # Abbildungen landen in <Kapitelordner>/abbildungen

OUT = str(ABB)
c = pd.read_csv(ZWISCHEN / "cap_k_calibration_v2.csv")   # aus recalibrate_cap.py

LAB = {
    "ALL winter nights": "all winter nights",
    "CAP nights (inv_active)": "inversion nights",
    "moderate inversion (0.2-0.5), calm": "moderate inversion, calm",
    "CAP nights, calm (<=1 m/s)": "inversion nights, calm",
    "strong inversion (>=0.5), calm": "strong inversion, calm",
    "CONTROL: well-mixed & windy": "control: well mixed, windy",
}
ORDER = ["all winter nights", "inversion nights", "moderate inversion, calm",
         "inversion nights, calm", "strong inversion, calm", "control: well mixed, windy"]
c["lab"] = c.subset.map(LAB)

one = c[c.model == "gated only"].set_index("lab").loc[ORDER].reset_index()
two = c[c.model == "gated + dz x gate"].set_index("lab").loc[ORDER].reset_index()

C_ONE, C_TWO, C_CTRL = "#9db8d2", "#1f4e79", "#7a7a7a"
plt.rcParams.update({"font.family": schrift(), "font.size": 9})
fig, (ax, ax2) = plt.subplots(1, 2, figsize=(11, 4.3),
                              gridspec_kw={"width_ratios": [1.42, 1]})

# ---------------------------------------------------------------- Panel (a)
y = np.arange(len(ORDER))[::-1].astype(float)
DY = 0.19
ax.axvspan(5, 9, color="#f0a500", alpha=0.16, zorder=0)
ax.text(12.0, y.max() + 1.05, "measured range,\nRauchöcker et al. (2024)",
        ha="left", va="bottom", fontsize=7.4, color="#8a6100", linespacing=1.25)
ax.axvline(6.5, color="#b4231f", lw=1.6, zorder=2)
ax.text(6.5, y.min() - 0.95, "value used\nin the model (6.5 K)", ha="center", va="top",
        fontsize=7.6, color="#b4231f")
ax.axvline(0, color="#999999", lw=0.8, ls=":", zorder=1)

for df, dy, base in [(one, +DY, C_ONE), (two, -DY, C_TWO)]:
    for i, r in df.iterrows():
        yy = y[i] + dy
        col = C_CTRL if r.lab.startswith("control") else base
        ax.plot([r.ci_lo, r.ci_hi], [yy, yy], color=col, lw=2.1,
                solid_capstyle="round", zorder=3)
        ax.plot(r.K_CAP, yy, "o", ms=6, color=col, zorder=4)
        ax.text(r.ci_hi + 0.3, yy, f"{r.K_CAP:.1f} K", va="center",
                fontsize=7.4, color="#333333")

for i, r in two.iterrows():
    ax.text(-3.2, y[i], f"n = {int(r.n_obs):,}".replace(",", " "),
            va="center", ha="left", fontsize=7.0, color="#777777")
    ax.text(-3.2, y[i] - 0.42, f"f$_{{stab}}$ = {r.mean_gate:.2f}",
            va="center", ha="left", fontsize=6.6, color="#999999")

ax.set_yticks(y, ORDER, fontsize=8.4)
ax.set_xlim(-3.4, 17.5)
ax.set_ylim(y.min() - 1.9, y.max() + 1.9)
ax.set_xlabel("Estimated K$_{CAP}$ (K), 95 % interval blocked by station pair")
ax.set_title("(a) Station-pair estimate of the CAP temperature scaling",
             loc="left", fontsize=9.5)
ax.grid(axis="x", ls=":", alpha=0.6)
for s in ("top", "right", "left"):
    ax.spines[s].set_visible(False)
ax.legend(handles=[Line2D([0], [0], color=C_ONE, lw=2.1, marker="o", ms=6,
                          label="fixed lapse rate"),
                   Line2D([0], [0], color=C_TWO, lw=2.1, marker="o", ms=6,
                          label="lapse rate responds to stability")],
          fontsize=7.6, loc="lower right", frameon=False)

# ---------------------------------------------------------------- Panel (b)
# Das Unterscheidungsmerkmal der Teilmengen ist der Wind, nicht das Gate: bei
# Windstille weicht die tatsaechliche Schichtung am weitesten von der
# durchmischten Referenz ab, und genau dort richtet die fehlende
# Lapse-Rate-Anpassung den groessten Schaden an.
for df, col, lab, jx in [(one, C_ONE, "fixed lapse rate", -0.10),
                         (two, C_TWO, "lapse rate responds to stability", +0.10)]:
    s_ = df.sort_values("mean_ff").copy()
    # Drei Teilmengen liegen bei fast identischer Windgeschwindigkeit; ohne
    # leichten Versatz ueberdecken sich ihre Intervalle vollstaendig.
    s_["mean_ff"] = s_["mean_ff"] + jx + np.linspace(-0.07, 0.07, len(s_))
    ctrl = s_.lab.str.startswith("control").values
    ax2.errorbar(s_.mean_ff[~ctrl], s_.K_CAP[~ctrl],
                 yerr=[(s_.K_CAP - s_.ci_lo)[~ctrl], (s_.ci_hi - s_.K_CAP)[~ctrl]],
                 fmt="o", ms=5.5, color=col, ecolor=col, capsize=3, lw=1.1,
                 label=lab, zorder=3)
    ax2.errorbar(s_.mean_ff[ctrl], s_.K_CAP[ctrl],
                 yerr=[(s_.K_CAP - s_.ci_lo)[ctrl], (s_.ci_hi - s_.K_CAP)[ctrl]],
                 fmt="s", ms=5.5, color=C_CTRL, ecolor=C_CTRL, capsize=3, lw=1.1,
                 zorder=3)
ax2.axhspan(5, 9, color="#f0a500", alpha=0.16, zorder=0)
ax2.axhline(6.5, color="#b4231f", lw=1.4, zorder=1)
ax2.axvspan(0, 1.0, color="#4f8fbd", alpha=0.07, zorder=0)
ax2.text(0.5, 15.2, "calm nights", ha="center", fontsize=7.4, color="#4f6f8f")
ax2.text(2.2, 15.2, "all / inversion nights", ha="center", fontsize=7.4, color="#777777")
ax2.text(5.85, 15.2, "control", ha="center", fontsize=7.4, color="#777777")
ax2.set_xlabel("Mean wind speed of the subset (m s$^{-1}$)")
ax2.set_ylabel("Estimated K$_{CAP}$ (K)")
ax2.set_title("(b) Does the estimate depend on which nights are used?",
              loc="left", fontsize=9.5)
ax2.set_xlim(0, 6.6)
ax2.set_ylim(-3.5, 16.5)
ax2.grid(ls=":", alpha=0.6)
for sp in ("top", "right"):
    ax2.spines[sp].set_visible(False)

plt.tight_layout()
fig.savefig(f"{OUT}/fig_cap_calibration.png", dpi=300)
print("gespeichert: fig_cap_calibration.png")
print(c[["lab", "model", "K_CAP", "ci_lo", "ci_hi", "dgamma_K_per_100m", "r2",
         "n_obs", "mean_gate"]].to_string(index=False))

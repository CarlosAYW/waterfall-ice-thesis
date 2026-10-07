"""Appendix-Figur A1: Eiswelt Taschachschlucht (UID 102) — Modell vs. Fotoreview."""
from pathlib import Path
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from PIL import Image
import sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pfade import MA, REPO, OUTPUT, ZWISCHEN, abbildungen, schrift  # noqa: E402
ABB = abbildungen(__file__)   # Abbildungen landen in <Kapitelordner>/abbildungen

plt.rcParams.update({
    "font.family": schrift(), "font.size": 8.8,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": "#d9d9d9",
    "grid.linewidth": 0.6, "grid.alpha": 0.6, "legend.frameon": False,
})
U = REPO / "analysis/Icefall_validation/UIDs/102 _ Eiswelt Taschachschlucht Pitztal"

df = pd.read_csv(REPO / "data/ModelRuns/model_uid102.csv", usecols=["date", "thickness_m"], low_memory=False)
df["date"] = pd.to_datetime(df["date"])
s = df.groupby("date")["thickness_m"].median()

CASES = [("2025-12-11", "model_too_little_ice"), ("2025-12-21", "model_too_little_ice"),
         ("2025-12-27", "model_too_little_ice"), ("2026-02-06", "matches"), ("2026-04-03", "matches")]
PHOTOS = [("2025-12-11", U/"11-12-2025_whatsapp_01.jpg", "(a) 2025-12-11 — reported climbable,\nmodel 0.03 m (too little ice)"),
          ("2025-12-21", U/"21-12-2025_whatsapp_02.jpg", "(b) 2025-12-21 — climbing activity,\nmodel <0.01 m (too little ice)"),
          ("2026-02-06", U/"06-02-2026_whatsapp_01.jpg", "(c) 2026-02-06 — thin gully ice,\nmodel 0.37 m (matches)")]

fig = plt.figure(figsize=(7.4, 5.9), constrained_layout=True)
gs = fig.add_gridspec(2, 3, height_ratios=[1.45, 1])
for k, (dt, path, label) in enumerate(PHOTOS):
    ax = fig.add_subplot(gs[0, k])
    img = Image.open(path)
    w, h = img.size
    target = 0.8
    if w/h > target:
        nw = int(h*target); x0 = (w-nw)//2
        img = img.crop((x0, 0, x0+nw, h))
    else:
        nh = int(w/target); y0 = max(0, (h-nh)//3)
        img = img.crop((0, y0, w, y0+nh))
    img.thumbnail((640, 860))
    ax.imshow(img)
    ax.set_xticks([]); ax.set_yticks([]); ax.grid(False)
    for sp in ax.spines.values():
        sp.set_visible(True); sp.set_color("#999999"); sp.set_linewidth(0.6)
    ax.set_xlabel(label, fontsize=7.2, labelpad=3)

axc = fig.add_subplot(gs[1, :])
axc.plot(s.index, s.values, lw=1.6, color="#183a5a")
MK = {"model_too_little_ice": ("v", "#4f8fbd", "review: too little ice"),
      "matches": ("o", "#4c956c", "review: matches")}
seen = set()
for dt, dec in CASES:
    t = pd.Timestamp(dt); th = float(s.loc[t])
    mk, mc, lab = MK[dec]
    axc.scatter(t, th, marker=mk, s=58, facecolor=mc, edgecolor="#2f2f2f", lw=0.8,
                zorder=6, label=lab if dec not in seen else None)
    seen.add(dec)
axc.set_ylabel("Modelled ice thickness (m)")
axc.set_xlabel("Date")
axc.set_ylim(0, max(0.45, float(s.max())*1.12))
axc.xaxis.set_major_locator(mdates.MonthLocator())
axc.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))
axc.legend(fontsize=7.4, loc="upper left")
axc.set_title("(d) Modelled thickness, Eiswelt Taschachschlucht (UID 102); photo-review cases marked",
              loc="left", fontsize=9)
fig.savefig(ABB / "fig_A1_taschach.png", dpi=300)
plt.close(fig)
print("A1 done | Dez-Werte:", [round(float(s.loc[pd.Timestamp(d)]),3) for d,_ in CASES])

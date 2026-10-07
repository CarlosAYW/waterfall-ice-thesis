"""Methoden-Abbildungen für 2.2.8: (1) Validierungs-Workflow, (2) Beispiel-Review-Fall."""
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
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
    "legend.frameon": False,
})

# ---------- Fig 1: Workflow ----------
fig, ax = plt.subplots(figsize=(7.4, 4.0))
ax.set_xlim(0, 10); ax.set_ylim(0, 7); ax.axis("off")

def box(x, y, w, h, text, fc="#eef2f6", ec="#183a5a", fs=8.2, bold=False):
    b = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.12", fc=fc, ec=ec, lw=1.1)
    ax.add_patch(b)
    ax.text(x+w/2, y+h/2, text, ha="center", va="center", fontsize=fs,
            fontweight="bold" if bold else "normal", color="#1a1a1a")

def arrow(x1, y1, x2, y2):
    a = FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=13,
                        lw=1.1, color="#2f2f2f")
    ax.add_patch(a)

# Quellen (oben)
box(0.2, 5.7, 2.9, 1.0, "Community group\n“Eiskletter-Verhältnisse 25/26”\n(photos + reports)", fc="#e8eef5")
box(3.55, 5.7, 2.9, 1.0, "Upload form on the\nproject website\n(rating + photos + comment)", fc="#e8eef5")
box(6.9, 5.7, 2.9, 1.0, "Route-condition posts,\nregional topo platform", fc="#e8eef5")
# Archiv
box(2.8, 4.05, 4.4, 0.95, "Per-route archive\ndated photographs + collected written reports", fc="#f4f0e6", bold=True)
for xc in (1.65, 5.0, 8.35):
    arrow(xc, 5.68, 5.0 if xc==5.0 else (4.0 if xc<5 else 6.0), 5.05)
# Zwei Stränge
box(0.6, 2.35, 4.0, 1.0, "Photo-review cases\n(route × date with photograph)\nreviewed in local interface", fc="#e9f2ec")
box(5.4, 2.35, 4.0, 1.0, "Report classification\n(good / medium / poor,\nown rating or keyword matching)", fc="#e9f2ec")
arrow(4.0, 4.03, 2.6, 3.4)
arrow(6.0, 4.03, 7.4, 3.4)
# Vergleich/Export
box(0.6, 0.55, 4.0, 1.0, "Judgement per case:\nmatches / too little / too much /\ndoes not fit / inconclusive", fc="#fdf3ee")
box(5.4, 0.55, 4.0, 1.0, "Comparison with modelled class\n(thresholds 0.05 m / 0.15 m),\nexported decision tables", fc="#fdf3ee")
arrow(2.6, 2.33, 2.6, 1.62)
arrow(7.4, 2.33, 7.4, 1.62)
fig.savefig(ABB / "fig_method_workflow.png", dpi=300, bbox_inches="tight")
plt.close(fig)

# ---------- Fig 2: Beispiel-Review-Fall (Herbstgold, 30.11.2025) ----------
plt.rcParams.update({
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": "#d9d9d9",
    "grid.linewidth": 0.6, "grid.alpha": 0.6,
})
R = REPO
U = R/"analysis/Icefall_validation/UIDs/045 _ Herbstgold"
df = pd.read_csv(R/"data/ModelRuns/model_uid45.csv", usecols=["date","thickness_m"], low_memory=False)
df["date"] = pd.to_datetime(df["date"])
s = df.groupby("date")["thickness_m"].median()
CASE = pd.Timestamp("2025-11-30")

fig = plt.figure(figsize=(7.4, 3.2), constrained_layout=True)
gs = fig.add_gridspec(1, 2, width_ratios=[0.7, 1.6])
axa = fig.add_subplot(gs[0, 0])
img = Image.open(U/"30-11-2025_website_01.jpg")
w, h = img.size; target = 0.8
if w/h > target:
    nw = int(h*target); x0 = (w-nw)//2
    img = img.crop((x0, 0, x0+nw, h))
img.thumbnail((560, 720))
axa.imshow(img); axa.set_xticks([]); axa.set_yticks([]); axa.grid(False)
for sp in axa.spines.values():
    sp.set_visible(True); sp.set_color("#999999"); sp.set_linewidth(0.6)
axa.set_xlabel("(a) Photograph of the case day\n(2025-11-30, upload form)", fontsize=7.6, labelpad=4)
axb = fig.add_subplot(gs[0, 1])
axb.plot(s.index, s.values, lw=1.6, color="#183a5a")
axb.scatter(CASE, float(s.loc[CASE]), s=64, facecolor="#d8b64c", edgecolor="#2f2f2f", lw=0.9, zorder=6)
axb.annotate("case day\nmedian 0.33 m", xy=(CASE, float(s.loc[CASE])), xytext=(10, 18),
             textcoords="offset points", fontsize=7.6,
             arrowprops=dict(arrowstyle="-", lw=0.7, color="#2f2f2f"))
axb.set_ylabel("Modelled ice thickness (m)")
axb.set_xlabel("Date")
axb.set_ylim(0, max(0.5, float(s.max())*1.12))
axb.xaxis.set_major_locator(mdates.MonthLocator())
axb.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))
axb.set_title("(b) Modelled thickness series shown alongside, case day marked", loc="left", fontsize=9)
fig.savefig(ABB / "fig_method_case.png", dpi=300)
plt.close(fig)
print("method figs done")

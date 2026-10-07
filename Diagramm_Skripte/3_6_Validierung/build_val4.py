"""Validation fig v4: (a) review bars, (b) class matrix, (c) three contrasting curves.
Panel 'thickness by class' removed per request."""
import json
from pathlib import Path
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
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
MODEL = REPO / "data" / "ModelRuns"
CLASSES = ["schlecht", "mittel", "gut"]
CLASS_EN = {"schlecht": "poor", "mittel": "medium", "gut": "good"}

def daily_median(uid):
    p = MODEL / f"model_uid{uid}.csv"
    if not p.exists(): return None
    df = pd.read_csv(p, usecols=["date", "thickness_m"], low_memory=False)
    df["date"] = pd.to_datetime(df["date"])
    return df.groupby("date")["thickness_m"].median()

def classify(th):
    return "schlecht" if th < 0.05 else ("mittel" if th < 0.15 else "gut")

# review
rev = pd.read_csv(REPO/"analysis/Icefall_validation/Review_Tool/07-26_validation_results_export.csv", sep=";")
rev["uid"] = rev["uid"].astype(int)
rev["date"] = pd.to_datetime(rev["date_iso"])
rev = rev[rev["decision"] != "unclear"].copy()
n = len(rev)
cnt = rev["decision"].value_counts()

# class comparison recompute
obs = pd.read_csv(REPO/"analysis/Icefall_validation/Model_vs_UID_Verhaeltnisse/modell_vs_uid_verhaeltnisse.csv",
                  sep=";", encoding="utf-8-sig")
obs = obs[["uid","eisfall","datum_iso","beobachtung"]].copy()
obs["uid"] = obs["uid"].astype(int)
obs["date"] = pd.to_datetime(obs["datum_iso"])
obs = obs[obs["beobachtung"].isin(CLASSES)].drop_duplicates(["uid","date"])
cache, rows = {}, []
for _, r in obs.iterrows():
    uid = int(r["uid"])
    if uid not in cache: cache[uid] = daily_median(uid)
    s = cache[uid]
    if s is None or r["date"] not in s.index: continue
    th = float(s.loc[r["date"]])
    mc = classify(th)
    rows.append({"uid": uid, "date": r["date"], "obs_class": r["beobachtung"],
                 "model_thickness_m": th, "model_class": mc,
                 "off": abs(CLASSES.index(mc)-CLASSES.index(r["beobachtung"]))})
comp = pd.DataFrame(rows)
nc = len(comp)
summary = {
    "review_cases_total": int(len(rev) + 0), "review_conclusive": n,
    "review_icefalls": int(rev["uid"].nunique()),
    "decisions": {k: int(v) for k, v in cnt.items()},
    "matches_pct": round(100*cnt.get("matches",0)/n, 1),
    "class_days": nc, "class_uids": int(comp["uid"].nunique()),
    "exact_pct": round(100*float((comp["off"]==0).mean()),1),
    "within1_pct": round(100*float((comp["off"]<=1).mean()),1),
    "two_off": int((comp["off"]==2).sum()),
    "optimistic": int(sum(CLASSES.index(r["model_class"])>CLASSES.index(r["obs_class"]) for _,r in comp.iterrows())),
    "median_th": {CLASS_EN[c]: round(float(comp.loc[comp["obs_class"]==c,"model_thickness_m"].median()),3) for c in CLASSES},
    "obs_n": {CLASS_EN[c]: int((comp["obs_class"]==c).sum()) for c in CLASSES},
    "dates": [str(comp["date"].min().date()), str(comp["date"].max().date())],
}
comp.to_csv(ZWISCHEN / "validation_class_comparison_v3.csv", index=False)
json.dump(summary, open(ZWISCHEN / "validation_v3_summary.json","w"), indent=1)
print(json.dumps(summary, indent=1))

fig = plt.figure(figsize=(7.4, 6.2), constrained_layout=True)
gs = fig.add_gridspec(2, 2, height_ratios=[1, 1.25], width_ratios=[1.5, 1])

axa = fig.add_subplot(gs[0, 0])
DEC = [("matches", "model matches photo", "#4c956c"),
       ("model_too_little_ice", "model: too little ice", "#4f8fbd"),
       ("model_too_much_ice", "model: too much ice", "#c9584f"),
       ("does_not_fit", "does not fit", "#7b302b")]
vals = [int(cnt.get(k, 0)) for k,_,_ in DEC]
y = np.arange(len(vals))[::-1]
axa.barh(y, vals, color=[c for _,_,c in DEC], height=0.6)
for yi, v in zip(y, vals):
    axa.text(v+1, yi, f"{v} ({100*v/n:.0f}%)", va="center", fontsize=8, color="#2f2f2f")
axa.set_yticks(y, [l for _,l,_ in DEC], fontsize=7.8)
axa.set_xlim(0, 78)
axa.set_xlabel(f"Conclusive review cases (n = {n})")
axa.set_title(f"(a) Expert photo review ({rev['uid'].nunique()} icefalls, 2025/26)", loc="left", fontsize=9)

axb = fig.add_subplot(gs[0, 1])
cm = np.zeros((3,3), dtype=int)
for _, r in comp.iterrows():
    cm[CLASSES.index(r["obs_class"]), CLASSES.index(r["model_class"])] += 1
axb.imshow(cm, cmap="Blues", vmin=0)
for i in range(3):
    for j in range(3):
        axb.text(j, i, str(cm[i,j]), ha="center", va="center",
                 color="white" if cm[i,j] > cm.max()*0.55 else "#183a5a",
                 fontsize=10, fontweight="bold")
axb.set_xticks(range(3), [CLASS_EN[c] for c in CLASSES], fontsize=7.6)
axb.set_yticks(range(3), [CLASS_EN[c] for c in CLASSES], fontsize=7.6)
axb.set_xlabel("Modelled class"); axb.set_ylabel("Observed class")
axb.set_title(f"(b) Report classes,\n{nc} matched days", loc="left", fontsize=9)
axb.grid(False)

axc = fig.add_subplot(gs[1, :])
EX = [(206, "Reislehn Eisfall (Pitztal, 2060 m)", "#183a5a"),
      (250, "Sulzenauer Eisfall (Stubaital, 1904 m)", "#4c956c"),
      (177, "Mitterndorfer Eisfall (Kufstein, 604 m)", "#b4554e")]
MK = {"matches": ("o", "#4c956c"), "model_too_little_ice": ("v", "#4f8fbd"),
      "model_too_much_ice": ("^", "#c9584f"), "does_not_fit": ("X", "#7b302b")}
for uid, lab, col in EX:
    s = daily_median(uid)
    axc.plot(s.index, s.values, lw=1.5, color=col, label=lab)
    for _, r in rev[rev["uid"]==uid].iterrows():
        if r["date"] in s.index:
            mk, mc = MK[r["decision"]]
            axc.scatter(r["date"], float(s.loc[r["date"]]), marker=mk, s=56,
                        facecolor=mc, edgecolor="#2f2f2f", lw=0.7, zorder=6)
from matplotlib.lines import Line2D
h, l = axc.get_legend_handles_labels()
for key, lab2 in [("matches","review: matches"), ("model_too_little_ice","review: too little ice")]:
    mk, mc = MK[key]
    h.append(Line2D([0],[0], marker=mk, ls="", markerfacecolor=mc, markeredgecolor="#2f2f2f", markersize=6.5))
    l.append(lab2)
axc.legend(h, l, loc="upper left", ncols=1, fontsize=7.2)
axc.set_ylabel("Modelled ice thickness (m)")
axc.set_xlabel("Date")
axc.xaxis.set_major_locator(mdates.MonthLocator())
axc.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))
axc.set_title("(c) Contrasting icefalls: modelled thickness and photo-review cases", loc="left", fontsize=9)
fig.savefig(ABB / "fig_3_5_validation_overview.png", dpi=300)
plt.close(fig)
print("fig22 v4 done")

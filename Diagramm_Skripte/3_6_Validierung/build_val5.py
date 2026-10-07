"""Validierungsabbildung v5 (Abb. 24): wie v4, aber lesbarer (Kommentar Nr. 14).
(a) Fotoreview, (b) Klassenvergleich mit Lesehilfe, (c) drei Beispielrouten Oktober-April
mit Klassengrenzen. Nimmt automatisch den neuesten Export des Review-Tools.
build_val4.py bleibt unveraendert."""
import json, sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
import numpy as np
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pfade import REPO, ZWISCHEN, abbildungen, schrift  # noqa: E402
ABB = abbildungen(__file__)

plt.rcParams.update({
    "font.family": schrift(), "font.size": 8.8,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": "#d9d9d9", "grid.linewidth": 0.6, "grid.alpha": 0.6,
    "legend.frameon": False,
})
INK, MUTED = "#2f2f2f", "#6b6b6b"
MODEL = REPO / "data" / "ModelRuns"
REVIEW = REPO / "analysis/Icefall_validation/Review_Tool"
CLASSES = ["schlecht", "mittel", "gut"]
CLASS_EN = {"schlecht": "poor", "mittel": "medium", "gut": "good"}
T_POOR, T_GOOD = 0.05, 0.15

def daily_median(uid):
    p = MODEL / f"model_uid{uid}.csv"
    if not p.exists(): return None
    df = pd.read_csv(p, usecols=["date", "thickness_m"], low_memory=False)
    df["date"] = pd.to_datetime(df["date"])
    return df.groupby("date")["thickness_m"].median()

def classify(th):
    return "schlecht" if th < T_POOR else ("mittel" if th < T_GOOD else "gut")

# ---- Fotoreview: neuester Export des Review-Tools ----
exports = sorted(REVIEW.glob("*validation_results_export*.csv"), key=lambda p: p.stat().st_mtime)
EXPORT = exports[-1]
print("Export:", EXPORT.name)
rev_all = pd.read_csv(EXPORT, sep=";")
rev_all["uid"] = rev_all["uid"].astype(int)
rev_all["date"] = pd.to_datetime(rev_all["date_iso"])
rev_all["source"] = np.where(rev_all["image_files"].fillna("").str.contains("website", case=False),
                             "upload form", "messaging group")
rev = rev_all[rev_all["decision"] != "unclear"].copy()
n = len(rev); cnt = rev["decision"].value_counts()

# ---- Klassenvergleich der schriftlichen Berichte ----
obs = pd.read_csv(REPO/"analysis/Icefall_validation/Model_vs_UID_Verhaeltnisse/modell_vs_uid_verhaeltnisse.csv",
                  sep=";", encoding="utf-8-sig")
obs["uid"] = obs["uid"].astype(int)
obs["date"] = pd.to_datetime(obs["datum_iso"])
obs["website"] = obs["klassierungsgrund"].fillna("").str.contains("Website")
obs = obs[obs["beobachtung"].isin(CLASSES)].drop_duplicates(["uid", "date"])
cache, rows = {}, []
for _, r in obs.iterrows():
    uid = int(r["uid"])
    if uid not in cache: cache[uid] = daily_median(uid)
    s = cache[uid]
    if s is None or r["date"] not in s.index: continue
    th = float(s.loc[r["date"]]); mc = classify(th)
    rows.append({"uid": uid, "date": r["date"], "obs_class": r["beobachtung"], "website": bool(r["website"]),
                 "model_thickness_m": th, "model_class": mc,
                 "diff": CLASSES.index(mc) - CLASSES.index(r["beobachtung"])})
comp = pd.DataFrame(rows); nc = len(comp)
summary = {
    "export": EXPORT.name,
    "review_cases_all": int(len(rev_all)), "review_unclear": int((rev_all["decision"] == "unclear").sum()),
    "review_conclusive": n, "review_icefalls_all": int(rev_all["uid"].nunique()), "review_icefalls": int(rev["uid"].nunique()),
    "review_period": [str(rev_all["date"].min().date()), str(rev_all["date"].max().date())],
    "review_sources_all": rev_all["source"].value_counts().to_dict(),
    "review_sources_conclusive": rev["source"].value_counts().to_dict(),
    "decisions": {k: int(v) for k, v in cnt.items()},
    "matches_pct": round(100 * cnt.get("matches", 0) / n, 1),
    "report_days_classified": int(len(obs)), "report_icefalls_classified": int(obs["uid"].nunique()),
    "class_days": nc, "class_uids": int(comp["uid"].nunique()),
    "class_days_website": int(comp["website"].sum()),
    "exact": int((comp["diff"] == 0).sum()), "exact_pct": round(100 * float((comp["diff"] == 0).mean()), 1),
    "within1_pct": round(100 * float((comp["diff"].abs() <= 1).mean()), 1),
    "two_off": int((comp["diff"].abs() == 2).sum()),
    "model_higher": int((comp["diff"] > 0).sum()), "model_lower": int((comp["diff"] < 0).sum()),
    "median_th": {CLASS_EN[c]: round(float(comp.loc[comp["obs_class"] == c, "model_thickness_m"].median()), 3) for c in CLASSES},
    "obs_n": {CLASS_EN[c]: int((comp["obs_class"] == c).sum()) for c in CLASSES},
}
comp.to_csv(ZWISCHEN / "validation_class_comparison_v5.csv", index=False)
json.dump(summary, open(ZWISCHEN / "validation_v5_summary.json", "w"), indent=1)
print(json.dumps(summary, indent=1))

# ---- Abbildung ----
fig = plt.figure(figsize=(7.4, 6.3), constrained_layout=True)
gs = fig.add_gridspec(2, 2, height_ratios=[1, 1.2], width_ratios=[1.45, 1])

# (a) Fotoreview
axa = fig.add_subplot(gs[0, 0])
DEC = [("matches", "course fits the photo", "#4a4a4a"),
       ("model_too_little_ice", "model shows too little ice", "#b3b3b3"),
       ("model_too_much_ice", "model shows too much ice", "#b3b3b3"),
       ("does_not_fit", "does not fit, no clear direction", "#b3b3b3")]
vals = [int(cnt.get(k, 0)) for k, _, _ in DEC]
y = np.arange(len(vals))[::-1]
axa.barh(y, vals, color=[c for _, _, c in DEC], height=0.58)
for yi, v in zip(y, vals):
    axa.text(v + 1, yi, f"{v} ({100 * v / n:.0f}%)", va="center", fontsize=8, color=INK)
axa.set_yticks(y, [l for _, l, _ in DEC], fontsize=7.8)
axa.set_xlim(0, 80); axa.grid(axis="y", visible=False)
axa.set_xlabel(f"Photo-review cases (n = {n})")
axa.set_title(f"(a) Photo review: {n} cases at {rev['uid'].nunique()} icefalls", loc="left", fontsize=9)

# (b) Klassenvergleich
axb = fig.add_subplot(gs[0, 1])
cm = np.zeros((3, 3), dtype=int)
for _, r in comp.iterrows():
    cm[CLASSES.index(r["obs_class"]), CLASSES.index(r["model_class"])] += 1
axb.imshow(cm, cmap="Blues", vmin=0, vmax=cm.max() * 1.15)
for i in range(3):
    for j in range(3):
        axb.text(j, i, str(cm[i, j]), ha="center", va="center",
                 color="white" if cm[i, j] > cm.max() * 0.55 else "#183a5a", fontsize=10, fontweight="bold")
    axb.add_patch(Rectangle((i - 0.5, i - 0.5), 1, 1, fill=False, ec=INK, lw=1.2))
axb.set_xticks(range(3), [CLASS_EN[c] for c in CLASSES], fontsize=7.6)
axb.set_yticks(range(3), [CLASS_EN[c] for c in CLASSES], fontsize=7.6)
axb.set_xlabel("Class from modelled thickness"); axb.set_ylabel("Class reported by climbers")
axb.set_title(f"(b) Written reports: {nc} days", loc="left", fontsize=9)
axb.grid(False)
axb.text(1.0, -0.23, f"framed: same class ({int(np.trace(cm))} days)", transform=axb.transAxes,
         ha="right", va="top", fontsize=7.2, color=MUTED)

# (c) drei Beispielrouten
axc = fig.add_subplot(gs[1, :])
EX = [(206, "Reislehn Eisfall (Pitztal, 2060 m)", "#2a78d6"),
      (250, "Sulzenauer Eisfall (Stubaital, 1904 m)", "#1baf7a"),
      (177, "Mitterndorfer Eisfall (Kufstein, 604 m)", "#eb6834")]
MK = {"matches": ("o", "white", "course fits the photo"),
      "model_too_little_ice": ("v", INK, "model shows too little ice"),
      "model_too_much_ice": ("^", INK, "model shows too much ice"),
      "does_not_fit": ("X", INK, "does not fit")}
start, end = pd.Timestamp("2025-10-01"), pd.Timestamp("2026-04-30")
used = set()
for uid, lab, col in EX:
    s = daily_median(uid); s = s[(s.index >= start) & (s.index <= end)]
    axc.plot(s.index, s.values, lw=1.6, color=col, label=lab)
    for _, r in rev[rev["uid"] == uid].iterrows():
        if r["date"] in s.index:
            mk, fc, _ = MK[r["decision"]]; used.add(r["decision"])
            axc.scatter(r["date"], float(s.loc[r["date"]]), marker=mk, s=46, facecolor=fc,
                        edgecolor=INK, lw=1.0, zorder=6)
for t, lab in [(T_POOR, "0.05 m"), (T_GOOD, "0.15 m")]:
    axc.axhline(t, color=MUTED, lw=0.8, ls=(0, (4, 3)), zorder=1)
    axc.text(end + pd.Timedelta(days=2), t, lab, va="center", ha="left", fontsize=7, color=MUTED)
axc.text(end + pd.Timedelta(days=2), 0.40, "good", va="center", ha="left", fontsize=7, color=MUTED)
axc.text(end + pd.Timedelta(days=2), 0.10, "medium", va="center", ha="left", fontsize=7, color=MUTED)
axc.text(end + pd.Timedelta(days=2), 0.018, "poor", va="center", ha="left", fontsize=7, color=MUTED)
h, l = axc.get_legend_handles_labels()
for key in ["matches", "model_too_little_ice", "model_too_much_ice", "does_not_fit"]:
    if key in used:
        mk, fc, lab2 = MK[key]
        h.append(Line2D([0], [0], marker=mk, ls="", markerfacecolor=fc, markeredgecolor=INK, markersize=6.5))
        l.append("photo review: " + lab2)
axc.legend(h, l, loc="upper left", ncols=1, fontsize=7.2)
axc.set_xlim(start, end + pd.Timedelta(days=1))
axc.set_ylabel("Modelled ice thickness (m)")
axc.xaxis.set_major_locator(mdates.MonthLocator())
axc.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))
axc.set_title("(c) Three example routes: modelled thickness and photo-review cases", loc="left", fontsize=9)
out = ABB / "fig_3_5_validation_overview_v5.png"
fig.savefig(out, dpi=300); plt.close(fig)
print("gespeichert:", out)

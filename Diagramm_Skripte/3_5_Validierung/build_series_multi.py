"""Photo series with modelled ice thickness (Fig. 25, 26)."""
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
from PIL import Image
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
U = REPO / "analysis/Icefall_validation/UIDs"
import re

def folder(uid):
    return next(x for x in U.iterdir() if x.is_dir() and re.match(rf"0*{uid}\s*_", x.name))

def series(uid):
    df = pd.read_csv(REPO / f"data/ModelRuns/model_uid{uid}.csv",
                     usecols=["date", "thickness_m"], low_memory=False)
    df["date"] = pd.to_datetime(df["date"])
    # auf den Untersuchungszeitraum begrenzt
    return df.groupby("date")["thickness_m"].median().loc["2025-10-01":"2026-04-30"]

CAND = {
    224: ("Schneelehnfall (Pitztal)", [
        ("2025-11-30", "30-11-2025_whatsapp_01.jpg", 0.5),
        ("2025-12-14", "14-12-2025_whatsapp_01.jpg", 0.5),
        ("2026-02-10", "10-02-2026_whatsapp_01.jpg", 0.5),
        ("2026-02-26", Path(__file__).resolve().parent / "eingabe" / "s224_d_enhanced.png", 0.5),
    ]),
    617: ("Mordor (Anlauftal)", [
        ("2025-12-07", "07-12-2025_whatsapp_02.jpg", 0.5),
        ("2026-01-05", "05-01-2026_whatsapp_01.jpg", 0.5),
        ("2026-01-31", "31-01-2026_whatsapp_03.jpg", 0.5),
        ("2026-02-12", "12-02-2026_whatsapp_01.jpg", 0.5),
    ]),
    93: ("Easy Afternoon (Sellrain/Lüsens)", [
        ("2025-12-04", "04-12-2025_website_01.jpg", 0.5),
        ("2025-12-13", "13-12-2025_whatsapp_01.jpg", 0.5),
        ("2026-01-06", "06-01-2026_whatsapp_01.jpg", 0.5),
        ("2026-01-22", "22-01-2026_whatsapp_01.jpg", 0.5),
    ]),
}

for uid, (name, photos) in [(k, CAND[k]) for k in (224, 93)]:
    s = series(uid)
    ncol = len(photos)
    fig = plt.figure(figsize=(7.4, 5.7), constrained_layout=True)
    gs = fig.add_gridspec(2, ncol, height_ratios=[1.45, 1])
    target = 0.68 if ncol == 4 else 0.82
    for k, (dt, fname, xanchor) in enumerate(photos):
        ax = fig.add_subplot(gs[0, k])
        img = Image.open(fname if isinstance(fname, Path) else folder(uid) / fname)
        w, h = img.size
        if w / h > target:
            nw = int(h * target)
            x0 = int((w - nw) * xanchor)
            img = img.crop((x0, 0, x0 + nw, h))
        else:
            nh = int(w / target)
            y0 = max(0, (h - nh) // 3)
            img = img.crop((0, y0, w, y0 + nh))
        img.thumbnail((640, 900))
        ax.imshow(img)
        ax.set_xticks([]); ax.set_yticks([]); ax.grid(False)
        for sp in ax.spines.values():
            sp.set_visible(True); sp.set_color("#999999"); sp.set_linewidth(0.6)
        th = float(s.loc[pd.Timestamp(dt)])
        ax.set_xlabel(f"({'abcd'[k]}) {dt}\nmodel: {th:.2f} m", fontsize=7.4, labelpad=3)
    axc = fig.add_subplot(gs[1, :])
    axc.plot(s.index, s.values, lw=1.6, color="#183a5a")
    for (dt, _, _), letter in zip(photos, "abcd"):
        t = pd.Timestamp(dt); th = float(s.loc[t])
        axc.scatter(t, th, s=52, facecolor="#d8b64c", edgecolor="#2f2f2f", lw=0.8, zorder=6)
        axc.annotate(f"({letter})", xy=(t, th), xytext=(0, 9), textcoords="offset points",
                     ha="center", fontsize=8.4, color="#2f2f2f")
    axc.set_ylabel("Modelled ice thickness (m)")
    axc.set_xlabel("Date")
    axc.set_ylim(0, max(0.5, float(s.max()) * 1.14))
    axc.set_xlim(pd.Timestamp("2025-10-01"), pd.Timestamp("2026-04-30"))
    axc.xaxis.set_major_locator(mdates.MonthLocator())
    axc.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))
    lab = "abcde"[len(photos)]
    axc.set_title(f"({lab}) Modelled thickness, {name}; photo dates marked", loc="left", fontsize=9)
    einheitlich(fig); fig.savefig(ABB / f"fig_photo_series_uid{uid}.png", dpi=300)
    plt.close(fig)
    print("done", uid, name)

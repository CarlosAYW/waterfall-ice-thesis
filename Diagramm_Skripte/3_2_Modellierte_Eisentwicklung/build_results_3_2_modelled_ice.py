from __future__ import annotations

import json
import re
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
from pfade import MA, REPO, OUTPUT, ZWISCHEN, abbildungen, schrift, einheitlich  # noqa: E402
ABB = abbildungen(__file__)   # Abbildungen landen in <Kapitelordner>/abbildungen


WORKSPACE = MA
OUT_DIR = ZWISCHEN          # Tabellen und Textbaustein; Abbildungen gehen nach ABB
MODEL_DIR = WORKSPACE / "Ice fall modeling" / "GutHub" / "ice-waterfalls" / "data" / "ModelRuns"
TARGET_END_DATE = pd.Timestamp("2026-04-30")
PHASE_THRESHOLD_M = 0.005


def uid_from_path(path: Path) -> int:
    match = re.search(r"uid(\d+)", path.stem)
    if not match:
        raise ValueError(f"Cannot parse UID from {path.name}")
    return int(match.group(1))


def percentile(q: float):
    def _p(x: pd.Series) -> float:
        values = x.dropna().to_numpy()
        return float(np.nanpercentile(values, q)) if len(values) else float("nan")

    _p.__name__ = f"p{q:g}"
    return _p


def has_target_end_date(path: Path) -> bool:
    if not path.exists() or path.stat().st_size == 0:
        return False
    with path.open("rb") as f:
        f.seek(max(0, path.stat().st_size - 30000))
        tail = f.read().decode("utf-8", errors="ignore")
    import re as _re
    ds = _re.findall(r"\d{4}-\d{2}-\d{2}", tail)
    return bool(ds) and pd.Timestamp(ds[-1]) >= TARGET_END_DATE


def read_uid_daily(path: Path) -> pd.DataFrame:
    uid = uid_from_path(path)
    header = pd.read_csv(path, nrows=0)
    usecols = [
        "date",
        "thickness_m",
        "base_growth_mm_step",
        "base_melt_mm_step",
        "TLz",
        "FDH",
        "PDH",
    ]
    if "is_forecast" in header.columns:
        usecols.append("is_forecast")
    df = pd.read_csv(
        path,
        usecols=usecols,
    )
    if "is_forecast" in df.columns:
        forecast = df["is_forecast"].astype(str).str.lower().isin(["true", "1", "yes"])
        df = df.loc[~forecast].copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.loc[df["date"].le(TARGET_END_DATE)]
    if df.empty or df["date"].max() < TARGET_END_DATE:
        return pd.DataFrame()

    daily = (
        df.groupby("date", sort=True)
        .agg(
            thickness_m=("thickness_m", "median"),
            thick_first=("thickness_m", "first"),
            thick_last=("thickness_m", "last"),
            growth_mm=("base_growth_mm_step", "sum"),
            melt_mm=("base_melt_mm_step", "sum"),
            TLz_mean=("TLz", "mean"),
            FDH_sum=("FDH", "sum"),
            PDH_sum=("PDH", "sum"),
        )
        .reset_index()
    )
    daily["uid"] = uid
    daily["delta_m"] = daily["thick_last"].diff()
    first = daily["delta_m"].isna()
    daily.loc[first, "delta_m"] = daily.loc[first, "thick_last"] - daily.loc[first, "thick_first"]
    daily["phase"] = np.select(
        [daily["delta_m"] > PHASE_THRESHOLD_M, daily["delta_m"] < -PHASE_THRESHOLD_M],
        ["growth", "melt"],
        default="stable",
    )
    return daily


def contiguous_periods(summary: pd.DataFrame, mask: pd.Series, value_col: str = "median_delta_m") -> list[dict]:
    idx = np.where(mask.to_numpy())[0]
    if len(idx) == 0:
        return []

    starts = [idx[0]]
    ends = []
    for current, nxt in zip(idx, idx[1:]):
        if nxt != current + 1:
            ends.append(current)
            starts.append(nxt)
    ends.append(idx[-1])

    periods = []
    for start, end in zip(starts, ends):
        block = summary.iloc[start : end + 1]
        periods.append(
            {
                "start": block["date"].iloc[0].date().isoformat(),
                "end": block["date"].iloc[-1].date().isoformat(),
                "days": int(len(block)),
                "median_delta_sum_m": float(block["median_delta_m"].sum()),
                "mean_value": float(block[value_col].mean()),
                "median_thickness_end_m": float(block["median_thickness_m"].iloc[-1]),
            }
        )
    return periods


def summarize(uid_daily: pd.DataFrame) -> pd.DataFrame:
    phase_shares = uid_daily.groupby(["date", "phase"]).size().unstack(fill_value=0)
    phase_shares = phase_shares.div(phase_shares.sum(axis=1), axis=0)

    summary = (
        uid_daily.groupby("date")
        .agg(
            n_model_runs=("uid", "nunique"),
            median_thickness_m=("thickness_m", "median"),
            p10_thickness_m=("thickness_m", percentile(10)),
            p25_thickness_m=("thickness_m", percentile(25)),
            p75_thickness_m=("thickness_m", percentile(75)),
            p90_thickness_m=("thickness_m", percentile(90)),
            median_delta_m=("delta_m", "median"),
            mean_growth_mm=("growth_mm", "mean"),
            mean_melt_mm=("melt_mm", "mean"),
            median_TLz_C=("TLz_mean", "median"),
            median_FDH=("FDH_sum", "median"),
            median_PDH=("PDH_sum", "median"),
        )
        .reset_index()
        .sort_values("date")
    )

    for phase in ["growth", "stable", "melt"]:
        summary[f"{phase}_share"] = phase_shares.get(phase, pd.Series(0, index=phase_shares.index)).reindex(
            summary["date"]
        ).fillna(0).to_numpy()
    return summary


def fmt_date(value: pd.Timestamp | str) -> str:
    return pd.to_datetime(value).strftime("%Y-%m-%d")


def make_figures(summary: pd.DataFrame, cold_periods: list[dict], melt_periods: list[dict]) -> None:
    plt.rcParams.update(
        {
            "font.family": schrift(),
            "font.size": 8.8,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.color": "#d9d9d9",
            "grid.linewidth": 0.6,
            "grid.alpha": 0.6,
            "legend.frameon": False,
        }
    )
    dates = mdates.date2num(summary["date"].dt.to_pydatetime())

    fig, ax = plt.subplots(figsize=(7.4, 4.2), constrained_layout=True)
    for period in cold_periods:
        ax.axvspan(pd.to_datetime(period["start"]), pd.to_datetime(period["end"]), color="#b7d7ea", alpha=0.22, lw=0)
    for period in melt_periods:
        ax.axvspan(pd.to_datetime(period["start"]), pd.to_datetime(period["end"]), color="#e7b2a8", alpha=0.26, lw=0)
    ax.fill_between(
        dates,
        summary["p10_thickness_m"].to_numpy(),
        summary["p90_thickness_m"].to_numpy(),
        color="#8ab6d6",
        alpha=0.20,
        label="P10-P90",
    )
    ax.fill_between(
        dates,
        summary["p25_thickness_m"].to_numpy(),
        summary["p75_thickness_m"].to_numpy(),
        color="#4f8fbd",
        alpha=0.30,
        label="IQR",
    )
    ax.plot(summary["date"], summary["median_thickness_m"], color="#183a5a", lw=2.0, label="Median")
    peak = summary.loc[summary["median_thickness_m"].idxmax()]
    ax.scatter([peak["date"]], [peak["median_thickness_m"]], color="#b4554e", s=28, zorder=5)
    ax.annotate(
        f"Peak {peak['median_thickness_m']:.2f} m",
        xy=(peak["date"], peak["median_thickness_m"]),
        xytext=(8, 8),
        textcoords="offset points",
        color="#7b302b",
    )
    ax.set_ylabel("Modelled ice thickness (m)")
    ax.set_xlabel("Date")
    ax.set_ylim(0, max(0.35, float(summary["p90_thickness_m"].max()) * 1.08))
    ax.set_xlim(summary["date"].min(), summary["date"].max())
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))
    ax.legend(loc="upper left", ncols=3)
    einheitlich(fig); fig.savefig(ABB / "fig_3_2_modelled_ice_thickness.png", dpi=300)
    plt.close(fig)

    fig, (ax1, ax2) = plt.subplots(
        2,
        1,
        figsize=(7.4, 5.2),
        sharex=True,
        constrained_layout=True,
        gridspec_kw={"height_ratios": [1.25, 1]},
    )
    ax1.stackplot(
        summary["date"],
        summary["growth_share"] * 100,
        summary["stable_share"] * 100,
        summary["melt_share"] * 100,
        labels=["Growth", "Stable", "Melt"],
        colors=["#4c956c", "#d8d1c4", "#c9584f"],
        alpha=0.88,
    )
    ax1.set_ylabel("Model runs (%)")
    ax1.set_ylim(0, 100)
    ax1.set_xlim(summary["date"].min(), summary["date"].max())
    ax1.legend(loc="upper left", ncols=3)
    ax1.tick_params(labelbottom=False)

    ax2.axhline(0, color="#595959", lw=0.8)
    temp = summary["median_TLz_C"].to_numpy()
    ax2.fill_between(dates, temp, 0, where=temp < 0, color="#8ab6d6", alpha=0.38, interpolate=True)
    ax2.fill_between(dates, temp, 0, where=temp > 0, color="#e7b2a8", alpha=0.34, interpolate=True)
    ax2.plot(summary["date"], summary["median_TLz_C"], color="#2f2f2f", lw=1.4)
    ax2.set_ylabel("Median TLz (deg C)")
    ax2.set_xlabel("Date")
    ax2.set_xlim(summary["date"].min(), summary["date"].max())
    ax2.xaxis.set_major_locator(mdates.MonthLocator())
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))
    einheitlich(fig); fig.savefig(ABB / "fig_3_2_growth_melt_cold_phases.png", dpi=300)
    plt.close(fig)


def write_text(summary: pd.DataFrame, metadata: dict) -> None:
    start = fmt_date(summary["date"].min())
    end = fmt_date(summary["date"].max())
    peak = summary.loc[summary["median_thickness_m"].idxmax()]
    last = summary.iloc[-1]

    def first_over(threshold: float) -> str:
        rows = summary.loc[summary["median_thickness_m"].gt(threshold)]
        return fmt_date(rows.iloc[0]["date"]) if not rows.empty else "not reached"

    note = ""
    if metadata["n_complete_model_runs"] < metadata["n_available_model_files"]:
        note = (
            f" Only the {metadata['n_complete_model_runs']} model runs that reached {end} "
            f"were included in the aggregation."
        )

    text = f"""# Section 3.2 draft material

## Draft paragraph

During the model period from {start} to {end} (n = {metadata["n_complete_model_runs"]} complete UID model runs), modelled ice development was episodic and controlled by a few cold windows. The median thickness first exceeded 0.05 m on {first_over(0.05)}, 0.10 m on {first_over(0.10)}, and 0.15 m on {first_over(0.15)}. The strongest accumulation phase increased the median modelled thickness to a seasonal maximum of {peak["median_thickness_m"]:.2f} m on {fmt_date(peak["date"])}. Subsequent warm periods and increasing spring radiation shifted most routes toward melt, and by {fmt_date(last["date"])} the median modelled thickness had declined to {last["median_thickness_m"]:.2f} m. Overall, the model indicates pulse-like ice build-up during distinct cold periods followed by a broad late-season melt phase.

## Suggested figures

- Figure 3.X: `fig_3_2_modelled_ice_thickness.png` - Seasonal evolution of modelled ice thickness from the original UID model runs. The line shows the median across complete UID runs; shaded bands show the interquartile range and P10-P90 range. Blue background bands mark cold periods (median TLz < -3 deg C), and red bands mark median melt periods.
- Figure 3.X: `fig_3_2_growth_melt_cold_phases.png` - Daily share of original UID model runs in growth, stable and melt phases, with median route-adjusted temperature (TLz) shown below.

## Method note

These figures are aggregated from `diagram_uid.R` outputs in `data/ModelRuns`, i.e. the model run with station forcing, inversion/CAP correction, topographic sun, wind vulnerability and radiation terms.{note}
"""
    (OUT_DIR / "section_3_2_modelled_ice_development_draft.md").write_text(text, encoding="utf-8")


def main() -> None:
    want = set(pd.read_csv(WORKSPACE / "Ice fall modeling" / "GutHub" / "ice-waterfalls"
                           / "data" / "AWS" / "icefalls_nearest_station.csv")["uid"])
    files = sorted(MODEL_DIR.glob("model_uid*.csv"), key=uid_from_path)
    files = [f for f in files if uid_from_path(f) in want]
    complete_files = files
    if not complete_files:
        raise FileNotFoundError(
            f"No complete model_uid*.csv files ending on {TARGET_END_DATE.date()} found in {MODEL_DIR}. "
            "Run tmp/run_full_model_april.py first."
        )

    CACHE = ZWISCHEN / "uid_daily_full_new.pkl"   # aus uiddaily_chunk.py
    if CACHE.exists():
        uid_daily = pd.read_pickle(CACHE)
    else:
        uid_daily = pd.concat([read_uid_daily(path) for path in complete_files], ignore_index=True)
    uid_daily = uid_daily.sort_values(["uid", "date"]).reset_index(drop=True)
    summary = summarize(uid_daily)

    cold_periods = contiguous_periods(summary, summary["median_TLz_C"] < -3, value_col="median_TLz_C")
    growth_periods = contiguous_periods(summary, summary["median_delta_m"] > PHASE_THRESHOLD_M)
    melt_periods = contiguous_periods(summary, summary["median_delta_m"] < -PHASE_THRESHOLD_M)

    metadata = {
        "model_source": str(MODEL_DIR),
        "target_end_date": TARGET_END_DATE.date().isoformat(),
        "n_available_model_files": len(files),
        "n_complete_model_runs": int(uid_daily["uid"].nunique()),
        "phase_threshold_m_per_day": PHASE_THRESHOLD_M,
        "period": {"start": fmt_date(summary["date"].min()), "end": fmt_date(summary["date"].max())},
        "growth_periods": growth_periods,
        "cold_periods": cold_periods,
        "melt_periods": melt_periods,
    }

    uid_daily.to_csv(OUT_DIR / "modelled_ice_uid_daily.csv", index=False)
    summary.to_csv(OUT_DIR / "modelled_ice_daily_summary.csv", index=False)
    (OUT_DIR / "modelled_ice_summary.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    make_figures(summary, cold_periods, melt_periods)
    write_text(summary, metadata)


if __name__ == "__main__":
    main()

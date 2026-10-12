"""Wie stark hat welcher Faktor das Eis beeinflusst? Bereinigter Vergleich fuer Winter 2025/26.

Spearman-Korrelationen zwischen Routen vermischen
die Faktoren mit der Lage: Wind steigt mit der Hoehe, der CAP-Ueberschuss markiert Talboeden
weit unter ihrer Station. Dieses Skript vergleicht stattdessen jede Route mit sich selbst:
Der Eiskoerper wird aus den gespeicherten Laeufen (data/ModelRuns) nachgerechnet, einmal
vollstaendig und je einmal ohne einen Faktor. Die Differenz der Eistage (Tagesmedian >= 0.15 m)
ist die direkte Wirkung dieses Faktors im Modell, frei von Hoehe und Lage.

Laeufe (alles andere identisch: Stationen, INCA, 10-min-Raster, Schwelle 0.15 m)
  voll        wie gerechnet; muss die gespeicherte Dicke exakt treffen (sonst Abbruch)
  ohne_cap    CAP-Korrektur aus:           TLz = TLz_base
  ohne_inv    Inversionsprofil aus:        TLz = TLz_raw - cap_temp_adjust_C (konstanter Gradient 0.65 K/100 m)
  ohne_wind   Windfaktor aus:              wind_fac = 1
  ohne_dry    Trockenheitsfaktor aus:      dry_fac = 1
  ohne_sw     Strahlungsschmelze aus:      SW_MJ_step = 0 (Sonne, Horizont, Wandneigung)
  t_minus1    Temperatur -1 K (entspricht etwa 150 m hoeher)   Massstab fuer Hoehe/Temperatur,
  t_plus1     Temperatur +1 K (entspricht etwa 150 m tiefer)   die sich nicht "abschalten" laesst

Ausgabe
  _zwischendaten/faktoren_kontra_routen.csv          je Route Eistage und Spitzendicke aller Laeufe
  abbildungen/fig_3_4_factor_effects.png             Abbildung
  abbildungen/faktoren_kontrafaktisch_kennzahlen.txt Zahlen fuer Text und Bildunterschrift

Aufruf:  python faktoren_kontrafaktisch.py            (alle 303 Routen, Daten + Abbildung)
         python faktoren_kontrafaktisch.py --probe 3  (nur 3 Routen, Test)
         python faktoren_kontrafaktisch.py --nur-abbildung   (Abbildung aus vorhandener CSV)
         python faktoren_kontrafaktisch.py --zeitbudget 150  (rechnet hoechstens 150 s und macht beim
                                                             naechsten Aufruf weiter; Zwischenstand je Route in
                                                             _zwischendaten/_bloecke_faktoren)
Benoetigt: pandas, numpy, matplotlib; numba optional (macht die Schleife etwa 50-mal schneller).
"""
import argparse
import math
import multiprocessing as mp
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HIER = Path(__file__).resolve().parent
sys.path.insert(0, str(HIER.parent))
sys.path.insert(0, str(HIER))
from pfade import REPO, ZWISCHEN, abbildungen, schrift
import cap_kontrafaktisch as ck  # Modellkonstanten, Antrieb, Rueckhalt/Exposition

RUNS = REPO / "data" / "ModelRuns"
ASSIGN = REPO / "data" / "AWS" / "icefalls_nearest_station.csv"
STATIC = ZWISCHEN / "uid_static.csv"
END, GOOD_M, DT_H, TOL = ck.END, ck.GOOD_M, ck.DT_H, 1e-6
COLS = ["date", "weather_ok", "TLz_raw", "TLz_base", "TLz", "cap_temp_adjust_C",
        "wind_fac", "dry_fac", "SW_MJ_step", "thickness_m"]
LAEUFE = ["voll", "ohne_cap", "ohne_inv", "ohne_wind", "ohne_dry", "ohne_sw", "t_minus1", "t_plus1"]
BAND_ORDER = ["<1500 m", "1500-2000 m", "2000-2500 m", ">2500 m"]
BAND_COL = {"<1500 m": "#b4554e", "1500-2000 m": "#d0993f", "2000-2500 m": "#4f8fbd", ">2500 m": "#183a5a"}
assert not ck.SONNE_IM_KERN   # Schleife unten bildet die gespeicherten Laeufe nach (Sonnenanteil im Kern = 0)
P = ck.P


def _ice(g, m, FDH, PDH, t72, ret, exp_, Hmax, H0, lam, seed_s, seed_c, cmin, cmax, mdamp, mscale, cmb, cmw, dth):
    """Eiskoerper wie ck.ice_body (ohne Sonnenanteil im Kern), numba-tauglich."""
    n = len(g)
    surf = np.zeros(n); core = np.zeros(n); res = np.zeros(n)
    surf[0] = seed_s; core[0] = seed_c
    denom = 1.0 - math.exp(-Hmax / lam)
    for i in range(1, n):
        H = (surf[i - 1] + core[i - 1]) / 1000.0
        iso = math.exp(-H / H0)
        gap = max(0.0, Hmax - H)
        gt = g[i] * iso * (1.0 - math.exp(-gap / lam)) / denom
        cs = cmin + 0.14 * min(1.0, FDH[i] / 4.0) + 0.12 * min(1.0, H / 0.30)
        cs = min(cmax, max(cmin, cs))
        gc = gt * cs
        spm = surf[i - 1] + gt - gc
        cpm = core[i - 1] + gc
        mt = m[i] * (1.0 - mdamp * min(1.0, H / mscale))
        s = t72[i]
        sef = min(1.0, max(0.0, (s + 5.0) / 5.0)) if s == s else 0.0
        mt = mt * (1.0 + 0.8 * exp_ * sef)
        ms = min(spm, mt)
        ml = max(0.0, mt - ms)
        cmf = min(0.85, max(0.20, cmb + cmw * min(1.0, PDH[i] / 4.0)))
        mc = min(cpm, ml * cmf)
        rtl = max(0.0, s + 2.0) if s == s else 0.0
        rl = (0.08 * PDH[i] * dth + 0.02 * rtl) * ret
        res[i] = min(0.28 * cpm, max(0.0, res[i - 1] + 0.30 * gc * ret - rl))
        surf[i] = max(0.0, spm - ms)
        core[i] = max(res[i], cpm - mc)
    return (surf + core) / 1000.0


try:
    from numba import njit
    _ice = njit(cache=False)(_ice)
    NUMBA = True
except Exception:
    NUMBA = False


def ice(g, m, FDH, PDH, t72, ret, exp_):
    return _ice(g, m, FDH, PDH, t72, ret, exp_, P["Hmax_m"], P["H0_m"], P["Hsat_lambda_m"],
                float(P["surface_seed_mm"]), P["core_seed_mm"] + P["core_seed_boost_mm"] * ret,
                P["core_share_min"] + P["core_share_min_boost"] * ret,
                P["core_share_max"] + P["core_share_max_boost"] * ret,
                P["melt_damping_max"] + P["melt_damping_boost"] * ret, P["melt_damping_scale_m"],
                P["core_melt_base"] - P["core_melt_base_drop"] * ret,
                P["core_melt_warm"] - P["core_melt_warm_drop"] * ret, DT_H)


def one_route(args):
    uid, dz, pb, tp = args
    df = pd.read_csv(RUNS / f"model_uid{uid}.csv", usecols=COLS, low_memory=False)
    df = df[df["date"] <= END].reset_index(drop=True)
    wok = df["weather_ok"].astype(str).str.upper().eq("TRUE").values
    ret, exp_ = ck.route_factors(dz, pb, tp)
    TLz = df["TLz"].values.astype(float)
    cap = df["cap_temp_adjust_C"].fillna(0.0).values
    wf = df["wind_fac"].values.astype(float); dfac = df["dry_fac"].values.astype(float)
    sw = df["SW_MJ_step"].values.astype(float)
    one = np.ones_like(wf); zero = np.zeros_like(sw)
    var = {
        "voll": (TLz, wf, dfac, sw),
        "ohne_cap": (df["TLz_base"].values.astype(float), wf, dfac, sw),
        "ohne_inv": (df["TLz_raw"].values.astype(float) - cap, wf, dfac, sw),
        "ohne_wind": (TLz, one, dfac, sw),
        "ohne_dry": (TLz, wf, one, sw),
        "ohne_sw": (TLz, wf, dfac, zero),
        "t_minus1": (TLz - 1.0, wf, dfac, sw),
        "t_plus1": (TLz + 1.0, wf, dfac, sw),
    }
    out = {"uid": uid, "retention": ret, "exposure": exp_}
    dates = df["date"].values
    for lauf in LAEUFE:
        T, w_, d_, s_ = var[lauf]
        FDH, PDH, g, m, t72 = ck.forcing(T, wok, w_, d_, s_)
        th = ice(np.ascontiguousarray(g, float), np.ascontiguousarray(m, float), np.ascontiguousarray(FDH, float),
                 np.ascontiguousarray(PDH, float), np.ascontiguousarray(t72, float), float(ret), float(exp_))
        if lauf == "voll":
            out["abweichung_gespeichert_m"] = float(np.max(np.abs(th - df["thickness_m"].values)))
        d = pd.Series(th).groupby(dates).median()
        out[f"ice_days_{lauf}"] = int((d >= GOOD_M).sum())
        out[f"peak_m_{lauf}"] = float(d.max())
    return out


# ------------------------------------------------------------------ Abbildung
ZEILEN = [  # (Spalte der Wirkung, Beschriftung)
    ("eff_cap", "Cold-air pooling\n(CAP term)"),
    ("eff_inv", "Temperature inversions\n(measured profile)"),
    ("eff_sw", "Shortwave radiation\n(sun)"),
    ("eff_wind", "Wind"),
    ("eff_dry", "Air dryness"),
]
REF = [("eff_tm1", "Reference: 1 K colder\n(≈ 150 m higher)"), ("eff_tp1", "Reference: 1 K warmer\n(≈ 150 m lower)")]


def wirkungen(R):
    R = R.copy()
    for k, lauf in [("cap", "ohne_cap"), ("inv", "ohne_inv"), ("wind", "ohne_wind"), ("dry", "ohne_dry"), ("sw", "ohne_sw")]:
        R[f"eff_{k}"] = R["ice_days_voll"] - R[f"ice_days_{lauf}"]      # mit Faktor minus ohne
        R[f"effpk_{k}"] = R["peak_m_voll"] - R[f"peak_m_{lauf}"]
    R["eff_tm1"] = R["ice_days_t_minus1"] - R["ice_days_voll"]
    R["eff_tp1"] = R["ice_days_t_plus1"] - R["ice_days_voll"]
    return R


def panel_direkte_wirkung(ax, R, fontsize=7.6, punkt=5):
    """Boxen (IQR, Median, 5-95 %) und Routenpunkte je Faktor; Referenzen +-1 K unter der gestrichelten Linie.
    Wird auch von build_3_34.py fuer Abb. 23b verwendet. Gibt die Zeilenreihenfolge zurueck."""
    import matplotlib.pyplot as plt
    zeilen = sorted(ZEILEN, key=lambda z: R[z[0]].abs().median() + 1e-3 * R[z[0]].abs().mean())
    alle = REF[::-1] + zeilen          # Referenzen unten, staerkster Faktor oben
    rng = np.random.default_rng(1)
    for y, (col, lab) in enumerate(alle):
        v = R[col].values
        ref = col in ("eff_tm1", "eff_tp1")
        q05, q25, q50, q75, q95 = np.percentile(v, [5, 25, 50, 75, 95])
        ax.add_patch(plt.Rectangle((q25, y - 0.28), max(q75 - q25, 0.25), 0.56, facecolor="#e6e6e6" if ref else "#cfe0ee",
                                   edgecolor="#6b6b6b", lw=0.7, zorder=2))
        ax.plot([q05, q25], [y, y], color="#6b6b6b", lw=0.8, zorder=2)
        ax.plot([q75, q95], [y, y], color="#6b6b6b", lw=0.8, zorder=2)
        ax.plot([q50, q50], [y - 0.28, y + 0.28], color="#2f2f2f", lw=1.6, zorder=4)
        for b in BAND_ORDER:
            s_ = (R["elevation_band"] == b).values
            ax.scatter(v[s_], y + rng.uniform(-0.2, 0.2, s_.sum()), s=punkt, color=BAND_COL[b], alpha=0.45, lw=0, zorder=3)
    ax.axvline(0, color="#2f2f2f", lw=0.8, zorder=1)
    ax.axhline(len(REF) - 0.5, color="#8a8a8a", lw=0.6, ls="--")
    ax.grid(axis="y", visible=False)
    ax.set_yticks(range(len(alle)), [l for _, l in alle], fontsize=fontsize)
    ax.set_ylim(-0.6, len(alle) - 0.4)
    return alle


def abbildung(R, ABB):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": schrift(), "font.size": 8.8, "axes.spines.top": False,
                         "axes.spines.right": False, "axes.grid": True, "grid.color": "#d9d9d9",
                         "grid.linewidth": 0.6, "grid.alpha": 0.6, "legend.frameon": False})
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.4, 3.9), constrained_layout=True,
                                   gridspec_kw={"width_ratios": [1.55, 1]}, sharey=True)
    alle = panel_direkte_wirkung(ax1, R)
    for y, (col, lab) in enumerate(alle):
        for i, b in enumerate(BAND_ORDER):
            med = R.loc[R["elevation_band"] == b, col].abs().median()   # typische Staerke, ohne Vorzeichen
            ax2.scatter(med, y + (i - 1.5) * 0.14, s=22, color=BAND_COL[b], zorder=3,
                        label=b if y == 0 else None, edgecolor="white", lw=0.4)
    ax2.axvline(0, color="#2f2f2f", lw=0.8, zorder=1)
    ax2.axhline(len(REF) - 0.5, color="#8a8a8a", lw=0.6, ls="--")
    ax2.grid(axis="y", visible=False)
    ax1.set_xlabel("Change in days with ice ≥ 0.15 m (with − without factor)")
    ax2.set_xlabel("Median absolute change (days)")
    ax1.set_title(f"(a) Direct effect per route (n = {len(R)})", loc="left", fontsize=9)
    ax2.set_title("(b) Typical size by elevation band", loc="left", fontsize=9)
    ax2.set_xlim(left=-1)
    ax2.legend(fontsize=7.0, loc="center right", handletextpad=0.2)   # rechts Mitte ist frei, unten rechts laegen Punkte
    fig.savefig(ABB / "fig_3_4_factor_effects.png", dpi=300)
    plt.close(fig)


def kennzahlen(R, ABB, sfx, t0):
    def q(s):
        return (f"Median {s.median():+.1f}, IQR {s.quantile(.25):+.1f} bis {s.quantile(.75):+.1f}, "
                f"5-95 % {s.quantile(.05):+.1f} bis {s.quantile(.95):+.1f}, Mittel {s.mean():+.1f}")
    L = [f"Faktoren-Kontrafaktum, Winter 2025/26, {len(R)} Routen",
         f"Nachbau 'voll' gegen gespeicherte Laeufe: max. Abweichung {R['abweichung_gespeichert_m'].max():.1e} m", "",
         "Wirkung auf die Eistage (>= 0.15 m); Faktoren: mit minus ohne; Referenz: gestoerter minus voller Lauf"]
    for col, lab in ZEILEN + REF:
        L.append(f"  {lab.replace(chr(10), ' '):45s} {q(R[col])}")
        L.append("      je Hoehenstufe (Median): " + ", ".join(f"{b} {R.loc[R.elevation_band == b, col].median():+.1f}" for b in BAND_ORDER))
    L.append("")
    L.append("Wirkung auf die Spitzendicke (m), Median je Faktor: " +
             ", ".join(f"{k} {R['effpk_' + k].median():+.3f}" for k in ["cap", "inv", "sw", "wind", "dry"]))
    L.append(f"Laufzeit {time.time() - t0:.0f} s, numba: {NUMBA}")
    txt = "\n".join(L)
    (ABB / f"faktoren_kontrafaktisch_kennzahlen{sfx}.txt").write_text(txt, encoding="utf-8")
    print(txt)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", type=int, default=0)
    ap.add_argument("--nur-abbildung", action="store_true")
    ap.add_argument("--prozesse", type=int, default=max(1, min(6, (os.cpu_count() or 2) - 1)))
    ap.add_argument("--zeitbudget", type=float, default=0, help="Sekunden; 0 = ohne Grenze")
    a = ap.parse_args()
    t0 = time.time()
    ABB = abbildungen(__file__)
    sfx = "_probe" if a.probe else ""
    csv = ZWISCHEN / f"faktoren_kontra_routen{sfx}.csv"
    if not a.nur_abbildung:
        A = pd.read_csv(ASSIGN)
        uids = sorted(set(A["uid"]) & {int(p.stem.replace("model_uid", "")) for p in RUNS.glob("model_uid*.csv")})
        if a.probe:
            uids = uids[:a.probe]
        A = A.set_index("uid")
        jobs = [(u, float(A.at[u, "elev_diff_m"]), float(A.at[u, "path_barrier_m"]), float(A.at[u, "topo_pos_diff"]))
                for u in uids]
        import json
        CACHE = ZWISCHEN / f"_bloecke_faktoren{sfx}"
        CACHE.mkdir(exist_ok=True)
        offen = [j for j in jobs if not (CACHE / f"{j[0]}.json").exists()]
        print(f"{len(jobs)} Routen, davon {len(offen)} offen, {a.prozesse} Prozesse, numba {NUMBA} ...", flush=True)
        pool = mp.Pool(a.prozesse) if a.prozesse > 1 else None
        try:
            for k in range(0, len(offen), 2 * a.prozesse):
                if a.zeitbudget and time.time() - t0 > a.zeitbudget:
                    break
                teil = offen[k:k + 2 * a.prozesse]
                for o in (pool.map(one_route, teil) if pool else map(one_route, teil)):
                    (CACHE / f"{o['uid']}.json").write_text(json.dumps(o))
        finally:
            if pool:
                pool.close(); pool.join()
        fertig = sorted(CACHE.glob("*.json"))
        res = [json.loads(f.read_text()) for f in fertig if int(f.stem) in {j[0] for j in jobs}]
        print(f"  {len(res)}/{len(jobs)} Routen fertig, {time.time() - t0:.0f} s", flush=True)
        if len(res) < len(jobs):
            print("Noch nicht fertig - Skript erneut aufrufen.")
            return
        st = pd.read_csv(STATIC)[["uid", "elevation_band", "z_target_m", "name"]]
        R = pd.DataFrame(res).merge(st, on="uid", how="left").sort_values("uid")
        bad = R[R["abweichung_gespeichert_m"] > TOL]
        if len(bad):
            print(bad[["uid", "abweichung_gespeichert_m"]].to_string(index=False))
            sys.exit(f"ABBRUCH: 'voll' trifft die gespeicherte Dicke bei {len(bad)} Routen nicht (> {TOL} m).")
        R.to_csv(csv, index=False, float_format="%.6g")
    R = wirkungen(pd.read_csv(csv))
    kennzahlen(R, ABB, sfx, t0)
    if not a.probe:
        abbildung(R, ABB)
        print("Abbildung:", ABB / "fig_3_4_factor_effects.png")


if __name__ == "__main__":
    main()

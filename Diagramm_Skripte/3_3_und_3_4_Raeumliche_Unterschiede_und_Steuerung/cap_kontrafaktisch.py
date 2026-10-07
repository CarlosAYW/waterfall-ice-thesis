# -*- coding: utf-8 -*-
"""Kommentar 65: Wie stark wirkt der CAP-Term? Kontrafaktischer Lauf fuer Winter 2025/26.

Idee
----
Die Modelllaeufe in data/ModelRuns/model_uid*.csv enthalten neben der Eisdicke
alle Zwischengroessen des Modells (Stationstemperatur auf Routenhoehe TLz_base,
CAP-Korrektur cap_temp_adjust_C, Wind- und Trockenheitsfaktoren, absorbierte
Strahlung usw.). Dieses Skript rechnet den Eiskoerper (Abschnitt 7 in
scripts/diagram_uid.R) fuer jede der 303 Routen zweimal nach:

  CAP an   c_CAP = 6.5 K  (Referenz, Tab. 2) - muss die gespeicherte Dicke exakt
                           treffen, sonst bricht das Skript ab
  CAP aus  c_CAP = 0      (cap_temp_adjust_C = 0, also TLz = TLz_base)

Alles andere bleibt identisch: dieselben Antriebsdaten (Stationen + INCA), dasselbe
10-min-Raster, dieselben Horizont- und Wind-Lookups, dieselbe Schwelle 0.15 m.
Nichts wird neu heruntergeladen.

Hinweis zum Modellcode: In diagram_uid.R (Zeilen 1220 und 1227) fehlt bei
wx$solar_core_fac der Index [i]. R bildet dadurch das Minimum ueber die ganze
Saison, und der Sonnenanteil der Kernschmelze und des Reserve-Abbaus ist in den
gespeicherten Laeufen praktisch null. Dieses Skript bildet die Laeufe so nach, wie
sie gerechnet wurden (SONNE_IM_KERN = False); nur so trifft "CAP an" die Laeufe,
auf denen die Arbeit beruht.

Ausgabe
-------
Diagramm_Skripte/_zwischendaten/cap_kontra_routen.csv   je Route: Eistage, FDH, Spitzendicke,
                                                        Mitteltemperatur fuer beide Laeufe, Differenzen,
                                                        CAP-Groessen, Hoehe, Exposition
Diagramm_Skripte/_zwischendaten/cap_kontra_tage.csv     Tagesmedian der Dicke, beide Laeufe
Diagramm_Skripte/_zwischendaten/westwind_routentage.csv Kommentar 70: Windfaktor an Frosttagen
<Kapitelordner>/abbildungen/cap_kontrafaktisch_kennzahlen.txt  Zahlen fuer Text und Bildunterschrift
Danach wird build_3_34.py gestartet; Abb. 20c zeigt dann den Vergleich.

Aufruf:  python cap_kontrafaktisch.py            (alle Routen, dann Abbildungen)
         python cap_kontrafaktisch.py --probe 5  (nur 5 Routen, ohne Abbildungen)
Benoetigt: pandas, numpy, matplotlib (scipy optional fuer exakte p-Werte).
Laufzeit: einige Minuten (liest 303 Dateien zu je ca. 25 MB).
"""
import argparse
import math
import multiprocessing as mp
import os
import runpy
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pfade import REPO, ZWISCHEN, abbildungen  # noqa: E402

RUNS = REPO / "data" / "ModelRuns"
ASSIGN = REPO / "data" / "AWS" / "icefalls_nearest_station.csv"
STATIC = ZWISCHEN / "uid_static.csv"          # aus prep_caches.py
END = "2026-04-30"
GOOD_M = 0.15
DT_H = 10 / 60
SONNE_IM_KERN = False     # so wie die gespeicherten Laeufe gerechnet wurden (siehe oben)
TOL = 1e-6                # erlaubte Abweichung "CAP an" gegen gespeicherte Dicke [m]
BAND_ORDER = ["<1500 m", "1500-2000 m", "2000-2500 m", ">2500 m"]

COEF = dict(growth=0.50, melt=0.60, rad=0.35)
P = dict(Hmax_m=0.90, H0_m=0.20, Hsat_lambda_m=0.15, core_seed_mm=4, core_seed_boost_mm=55,
         surface_seed_mm=16, core_share_min=0.02, core_share_min_boost=0.22, core_share_max=0.10,
         core_share_max_boost=0.48, melt_damping_max=0.05, melt_damping_boost=0.50,
         melt_damping_scale_m=0.45, core_melt_base=0.48, core_melt_base_drop=0.32,
         core_melt_warm=0.30, core_melt_warm_drop=0.12, core_melt_sun=0.24, core_melt_sun_drop=0.10)
COLS = ["time", "date", "TL", "weather_ok", "TLz_base", "TLz", "cap_temp_adjust_C", "cap_stability_fac",
        "wind_fac", "dry_fac", "SW_MJ_step", "solar_core_fac", "FDH", "PDH", "TLz_72h_step",
        "base_growth_mm_step", "base_melt_mm_step", "thickness_m", "FF", "DD", "cap_delta",
        "cap_pair_confidence", "cap_icefall", "z_target_m"]


def clamp01(x):
    return min(1.0, max(0.0, x))


def route_factors(dz_m, path_barrier_m, topo_pos_diff):
    """Rueckhalt- und Expositionsfaktor wie in diagram_uid.R (Zeilen 1170-1176)."""
    if not np.isfinite(path_barrier_m):
        path_barrier_m = 80.0
    if not np.isfinite(topo_pos_diff):
        topo_pos_diff = 0.16
    ret = clamp01((abs(dz_m) - 150) / 300) * clamp01((path_barrier_m - 80) / 160) * \
        clamp01((0.16 - topo_pos_diff) / 0.10)
    exp_ = (1 - clamp01((path_barrier_m - 40) / 120)) * clamp01((topo_pos_diff - 0.18) / 0.12)
    return ret, exp_


def forcing(TLz, weather_ok, wind_fac, dry_fac, SW):
    """FDH, PDH, Wachstums- und Schmelzpotenzial, 72-h-Mittel wie in diagram_uid.R."""
    fin = np.isfinite(TLz)
    FDH = np.where(fin, np.maximum(0.0, -np.nan_to_num(TLz)), 0.0)
    PDH = np.where(fin, np.maximum(0.0, np.nan_to_num(TLz)), 0.0)
    g = np.where(weather_ok, COEF["growth"] * FDH * DT_H * wind_fac * dry_fac, 0.0)
    m = np.where(weather_ok, COEF["melt"] * PDH * DT_H * wind_fac + COEF["rad"] * SW, 0.0)
    t72 = pd.Series(TLz).rolling(432, min_periods=1).mean().values
    return FDH, PDH, g, m, t72


def ice_body(g, m, FDH, PDH, t72, solar_core, ret, exp_):
    """Zwei-Schichten-Eiskoerper, Schleife aus diagram_uid.R, Abschnitt 7."""
    n = len(g)
    surf = np.zeros(n); core = np.zeros(n); res = np.zeros(n)
    surf[0] = P["surface_seed_mm"]
    core[0] = P["core_seed_mm"] + P["core_seed_boost_mm"] * ret
    denom = 1 - math.exp(-P["Hmax_m"] / P["Hsat_lambda_m"])
    cmin = P["core_share_min"] + P["core_share_min_boost"] * ret
    cmax = P["core_share_max"] + P["core_share_max_boost"] * ret
    mdamp = P["melt_damping_max"] + P["melt_damping_boost"] * ret
    cmb = P["core_melt_base"] - P["core_melt_base_drop"] * ret
    cmw = P["core_melt_warm"] - P["core_melt_warm_drop"] * ret
    cms = (P["core_melt_sun"] - P["core_melt_sun_drop"] * ret) if SONNE_IM_KERN else 0.0
    rsun = 0.05 if SONNE_IM_KERN else 0.0
    for i in range(1, n):
        H = (surf[i - 1] + core[i - 1]) / 1000
        iso = math.exp(-H / P["H0_m"])
        gap = max(0.0, P["Hmax_m"] - H)
        gt = g[i] * iso * (1 - math.exp(-gap / P["Hsat_lambda_m"])) / denom
        cs = cmin + 0.14 * min(1.0, FDH[i] / 4) + 0.12 * min(1.0, H / 0.30)
        cs = min(cmax, max(cmin, cs))
        gc = gt * cs
        spm = surf[i - 1] + gt - gc
        cpm = core[i - 1] + gc
        mt = m[i] * (1 - mdamp * min(1.0, H / P["melt_damping_scale_m"]))
        s = t72[i]
        sef = clamp01((s + 5) / 5) if s == s else 0.0
        mt = mt * (1 + 0.8 * exp_ * sef)
        ms = min(spm, mt)
        ml = max(0.0, mt - ms)
        cmf = min(0.85, max(0.20, cmb + cmw * min(1.0, PDH[i] / 4) + cms * solar_core[i]))
        mc = min(cpm, ml * cmf)
        rtl = max(0.0, s + 2) if s == s else 0.0
        rl = (0.08 * PDH[i] * DT_H + rsun * solar_core[i] + 0.02 * rtl) * ret
        res[i] = min(0.28 * cpm, max(0.0, res[i - 1] + 0.30 * gc * ret - rl))
        surf[i] = max(0.0, spm - ms)
        core[i] = max(res[i], cpm - mc)
    return (surf + core) / 1000


def wind_uv(FF, DD):
    """Mittlerer Windvektor (u, v) eines Tages; DD = Richtung, aus der der Wind kommt."""
    rad = np.deg2rad(DD)
    return float(-(FF * np.sin(rad)).mean()), float(-(FF * np.cos(rad)).mean())


def direction(u, v):
    """Richtung, aus der der mittlere Wind kommt (Grad)."""
    return (np.rad2deg(np.arctan2(-u, -v)) + 360) % 360


def one_route(args):
    uid, dz, pb, tp = args
    df = pd.read_csv(RUNS / f"model_uid{uid}.csv", usecols=COLS, low_memory=False)
    df = df[df["date"] <= END].reset_index(drop=True)
    wok = df["weather_ok"].astype(str).str.upper().eq("TRUE").values
    ret, exp_ = route_factors(dz, pb, tp)
    sc = df["solar_core_fac"].values
    out = {"uid": uid}
    daily = {}
    for lauf, TLz in [("an", df["TLz"].values), ("aus", df["TLz_base"].values)]:
        FDH, PDH, g, m, t72 = forcing(TLz, wok, df["wind_fac"].values, df["dry_fac"].values,
                                      df["SW_MJ_step"].values)
        th = ice_body(g, m, FDH, PDH, t72, sc, ret, exp_)
        if lauf == "an":
            dev = float(np.max(np.abs(th - df["thickness_m"].values)))
            out["abweichung_gespeichert_m"] = dev
        d = pd.Series(th).groupby(df["date"].values).median()
        daily[lauf] = d
        out[f"ice_days_{lauf}"] = int((d >= GOOD_M).sum())
        out[f"peak_m_{lauf}"] = float(d.max())
        out[f"fdh_{lauf}"] = float(FDH.sum() * DT_H)
        out[f"mean_T_{lauf}"] = float(np.nanmean(TLz))
    cap = df["cap_temp_adjust_C"].fillna(0.0).values
    capd = pd.Series(cap).groupby(df["date"].values).mean()
    out.update(cap_mean_C=float(cap.mean()), cap_median_C=float(np.median(cap)),
               cap_p92_C=float(np.percentile(cap, 92)), cap_share_steps_gt1K=float((cap > 1).mean()),
               cap_share_days_gt1K=float((capd > 1).mean()),
               fstab_share_gt05=float((df["cap_stability_fac"].fillna(0) > 0.5).mean()),
               cap_delta=float(df["cap_delta"].iloc[0]), cap_pair_confidence=float(df["cap_pair_confidence"].iloc[0]),
               cap_potential=float(df["cap_icefall"].iloc[0]), z_target_m=float(df["z_target_m"].iloc[0]),
               retention=ret, exposure=exp_)
    # Kommentar 70: Windfaktor an Frosttagen je Tag, mit Tages-Windrichtung
    df["frost"] = df["FDH"] > 0
    rows = []
    for dte, gdf in df.groupby("date"):
        fr = gdf[gdf["frost"]]
        if len(fr) < 6:     # mindestens 1 h Frost
            continue
        u, v = wind_uv(gdf["FF"].fillna(0).values, gdf["DD"].fillna(0).values)
        rows.append((uid, dte, u, v, float(gdf["FF"].mean()), float((fr["wind_fac"]).mean()),
                     float(fr["base_growth_mm_step"].sum() / max(1e-9, fr["FDH"].sum() * DT_H))))
    tage = pd.DataFrame({"date": daily["an"].index, "thick_an": daily["an"].values, "thick_aus": daily["aus"].values})
    tage.insert(0, "uid", uid)
    return out, tage, rows


def spearman(x, y):
    x = pd.Series(x); y = pd.Series(y)
    ok = x.notna() & y.notna(); x, y = x[ok], y[ok]; n = len(x)
    rho = x.rank().corr(y.rank())
    try:
        from scipy.stats import spearmanr
        p = float(spearmanr(x, y).pvalue); how = "scipy"
    except Exception:
        z = rho * math.sqrt(n - 1); p = math.erfc(abs(z) / math.sqrt(2)); how = "Normalnaeherung"
    return rho, p, n, how


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", type=int, default=0, help="nur so viele Routen (Test)")
    ap.add_argument("--ohne-abbildungen", action="store_true", help="build_3_34.py nicht starten")
    ap.add_argument("--prozesse", type=int, default=max(1, min(6, (os.cpu_count() or 2) - 1)))
    a = ap.parse_args()
    t0 = time.time()
    A = pd.read_csv(ASSIGN)
    st = pd.read_csv(STATIC)[["uid", "elevation_band", "aspect_deg", "name"]]
    uids = sorted(set(A["uid"]) & {int(p.stem.replace("model_uid", "")) for p in RUNS.glob("model_uid*.csv")})
    if a.probe:
        uids = uids[:a.probe]
    A = A.set_index("uid")
    jobs = [(u, float(A.at[u, "elev_diff_m"]), float(A.at[u, "path_barrier_m"]), float(A.at[u, "topo_pos_diff"]))
            for u in uids]
    print(f"{len(jobs)} Routen, {a.prozesse} Prozesse ...", flush=True)
    res, tage, wind = [], [], []
    with mp.Pool(a.prozesse) as pool:
        for k, (o, t, w) in enumerate(pool.imap_unordered(one_route, jobs, chunksize=2), 1):
            res.append(o); tage.append(t); wind.extend(w)
            if k % 25 == 0 or k == len(jobs):
                print(f"  {k}/{len(jobs)} Routen, {time.time() - t0:.0f} s", flush=True)
    R = pd.DataFrame(res).merge(st, on="uid", how="left").sort_values("uid")
    bad = R[R["abweichung_gespeichert_m"] > TOL]
    if len(bad):
        print(bad[["uid", "abweichung_gespeichert_m"]].to_string(index=False))
        sys.exit(f"ABBRUCH: 'CAP an' trifft die gespeicherte Dicke bei {len(bad)} Routen nicht (> {TOL} m).")
    for v in ["ice_days", "fdh", "peak_m", "mean_T"]:
        R[f"d_{v}"] = R[f"{v}_an"] - R[f"{v}_aus"]
    sfx = "_probe" if a.probe else ""
    R.to_csv(ZWISCHEN / f"cap_kontra_routen{sfx}.csv", index=False, float_format="%.6g")
    pd.concat(tage).to_csv(ZWISCHEN / f"cap_kontra_tage{sfx}.csv", index=False, float_format="%.5g")
    W = pd.DataFrame(wind, columns=["uid", "date", "u", "v", "ff_mean", "wind_fac_frost", "growth_per_fdh"])
    W["dir_deg"] = direction(W["u"], W["v"])
    reg = W.groupby("date")[["u", "v"]].mean()          # regionaler Tageswind: Mittel ueber alle Routen
    W["dir_regional_deg"] = W["date"].map(direction(reg["u"], reg["v"]))
    W = W.merge(st[["uid", "aspect_deg"]], on="uid", how="left")
    W.to_csv(ZWISCHEN / f"westwind_routentage{sfx}.csv", index=False, float_format="%.5g")

    # ---------------- Kennzahlen
    L = [f"CAP-Kontrafaktum, Winter 2025/26, {len(R)} Routen (c_CAP 6.5 K gegen 0), Stand {time.strftime('%Y-%m-%d %H:%M')}",
         f"Nachbau 'CAP an' gegen gespeicherte Laeufe: max. Abweichung {R['abweichung_gespeichert_m'].max():.1e} m", ""]
    def q(s):
        return f"Median {s.median():+.1f}, IQR {s.quantile(.25):+.1f} bis {s.quantile(.75):+.1f}, Spanne {s.min():+.1f} bis {s.max():+.1f}"
    L.append("Eistage (>= 0.15 m), CAP an minus aus:  " + q(R["d_ice_days"]))
    L.append(f"  Anteil Routen >0: {100*(R.d_ice_days>0).mean():.0f} %, =0: {100*(R.d_ice_days==0).mean():.0f} %, <0: {100*(R.d_ice_days<0).mean():.0f} %")
    L.append("Frostgradstunden (°C h), an minus aus: " + q(R["d_fdh"]))
    L.append("Spitzendicke (m), an minus aus:         " + f"Median {R.d_peak_m.median():+.3f}, IQR {R.d_peak_m.quantile(.25):+.3f} bis {R.d_peak_m.quantile(.75):+.3f}")
    L.append("Mitteltemperatur (K), an minus aus:     " + f"Median {R.d_mean_T.median():+.2f}, Spanne {R.d_mean_T.min():+.2f} bis {R.d_mean_T.max():+.2f}")
    for lab, col in [("d_ice_days", "d_ice_days"), ("d_fdh", "d_fdh")]:
        rho, p, n, how = spearman(R["cap_delta"], R[col])
        L.append(f"Spearman rho(delta_CAP, {lab}) = {rho:.2f}, p = {p:.1e} ({how}), n = {n}")
    L.append("")
    L.append("Je Hoehenstufe (Median d_ice_days / d_fdh / delta_CAP, n):")
    for b in BAND_ORDER:
        s = R[R.elevation_band == b]
        L.append(f"  {b:12s} {s.d_ice_days.median():+5.1f} Tage / {s.d_fdh.median():+7.0f} °C h / {s.cap_delta.median():+.2f}  (n = {len(s)})")
    L.append("")
    L.append("CAP-Korrektur selbst (CAP an):")
    L.append(f"  Mittel ueber Routen-Zeitschritte {R.cap_mean_C.mean():.2f} K; Median der Routenmittel {R.cap_mean_C.median():.2f} K")
    L.append(f"  Median der Zeitschritt-Mediane {R.cap_median_C.median():.2f} K; 92. Perzentil (Median der Routen) {R.cap_p92_C.median():.2f} K")
    L.append(f"  Anteil Zeitschritte > 1 K: {100*R.cap_share_steps_gt1K.mean():.1f} %; Anteil Routentage mit Tagesmittel > 1 K: {100*R.cap_share_days_gt1K.mean():.1f} %")
    L.append(f"  Anteil Zeitschritte mit f_stab > 0.5: {100*R.fstab_share_gt05.mean():.1f} %")
    L.append("")
    # Kommentar 70
    def sector(d):
        d = d % 360
        return "N" if (d >= 315 or d < 45) else "E" if d < 135 else "S" if d < 225 else "W"
    W["route_sektor"] = W["aspect_deg"].map(lambda x: sector(x) if np.isfinite(x) else np.nan)
    L.append("Kommentar 70: Windfaktor an Frosttagen (Mittel ueber Frost-Zeitschritte) und Wachstum je °C h, Median je Route-Tag")
    for lab, col in [("lokal (INCA-Wind an der Route)", "dir_deg"), ("regional (mittlerer Wind aller Routen)", "dir_regional_deg")]:
        W["westwind"] = W[col].between(225, 315)
        L.append(f"  Westwind {lab}, 225-315 Grad: {100*W.westwind.mean():.0f} % der Frost-Routentage")
        for sek in ["N", "E", "S", "W"]:
            s = W[W.route_sektor == sek]
            a_ = s[s.westwind]; b_ = s[~s.westwind]
            L.append(f"    Routen {sek}: Windfaktor {a_.wind_fac_frost.median():.3f} (n={len(a_)}) gegen {b_.wind_fac_frost.median():.3f} (n={len(b_)}) | "
                     f"Wachstum je °C h {a_.growth_per_fdh.median():.3f} gegen {b_.growth_per_fdh.median():.3f} mm")
    txt = "\n".join(L)
    ABB = abbildungen(__file__)
    (ABB / f"cap_kontrafaktisch_kennzahlen{sfx}.txt").write_text(txt, encoding="utf-8")
    print(txt)
    print(f"Fertig in {time.time() - t0:.0f} s.")
    if not a.probe and not a.ohne_abbildungen:
        print("Starte build_3_34.py fuer die Abbildungen ...", flush=True)
        runpy.run_path(str(Path(__file__).with_name("build_3_34.py")), run_name="__main__")


if __name__ == "__main__":
    main()

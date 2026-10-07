# -*- coding: utf-8 -*-
"""CAP-Kalibrierung mit stabilitaetsabhaengiger Lapse Rate.

Bisher:  resid_K = dT_obs + gamma_fix * dz          -> Regression auf dcap*gate
Problem: gamma_fix stammt aus durchmischten, windigen Perioden. Auf ruhigen
         Inversionsnaechten ist der tatsaechliche Gradient voellig anders; die
         Differenz landet im Residuum, skaliert mit dz, und verzerrt die
         Steigung, weil dz und dcap ueber die Paare korreliert sind (-0.27).

Neu:     resid_K = -K_CAP*(dcap*gate)  +  dgamma*(dz*gate)  +  eps
         Der zweite Term laesst den Gradienten unter Stabilitaet steiler werden.
         Beide Regressoren sind nur schwach kollinear (0.12-0.29).

Ausgabe: cap_k_calibration_v2.csv  (eine Zeile je Teilmenge und Modell)
"""
import numpy as np
import pandas as pd
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pfade import MA, REPO, OUTPUT, ZWISCHEN, bloecke  # noqa: E402

REPO = str(REPO)
OUT = str(ZWISCHEN)
PAIRS = f"{REPO}/data/CAP/cap_k_calibration_pairs.csv"
N_BOOT = 500
MIN_OBS = 200
SEED = 42

d = pd.read_csv(PAIRS)
d["inv_on"] = d["inv_active"].astype(str).str.upper().isin(["TRUE", "1"])

SUBSETS = {
    "ALL winter nights": d,
    "CAP nights (inv_active)": d[d.inv_on],
    "CAP nights, calm (<=1 m/s)": d[d.inv_on & (d.ff_max <= 1.0)],
    "moderate inversion (0.2-0.5), calm": d[(d.inv_grad >= 0.20) & (d.inv_grad < 0.50)
                                            & (d.ff_max <= 1.0)],
    "strong inversion (>=0.5), calm": d[(d.inv_grad >= 0.50) & (d.ff_max <= 1.0)],
    "CONTROL: well-mixed & windy": d[(~d.inv_on) & (d.inv_grad < 0.05) & (d.ff_max >= 3.0)],
}


def fit(y, X):
    """Kleinste Quadrate ohne Achsenabschnitt. Gibt Koeffizienten und R2 zurueck."""
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ b
    ss_tot = float(y @ y)                      # ohne Achsenabschnitt: um 0 zentriert
    r2 = 1.0 - float(resid @ resid) / ss_tot if ss_tot > 0 else np.nan
    return b, r2


def boot(y, X, rng, n=N_BOOT):
    """Bootstrap ueber Stationspaare, nicht ueber Einzelstunden.

    Die Paarstunden sind nicht unabhaengig: 53 Paare messen dieselben Stunden.
    Ein Bootstrap ueber Zeilen wuerde die Intervalle deshalb zu eng machen.
    Geblockt wird daher ueber die Paare.
    """
    out = []
    for _ in range(n):
        idx = rng.integers(0, len(X), len(X))
        try:
            b, *_ = np.linalg.lstsq(X[idx], y[idx], rcond=None)
            out.append(b)
        except np.linalg.LinAlgError:
            continue
    return np.array(out)


def boot_blocked(df, cols, ycol, rng, n=N_BOOT):
    groups = [g.index.values for _, g in df.groupby(["station_id_i", "station_id_j"])]
    y_all = df[ycol].values
    X_all = df[cols].values
    pos = {ix: k for k, ix in enumerate(df.index.values)}
    out = []
    for _ in range(n):
        pick = rng.integers(0, len(groups), len(groups))
        rows = np.concatenate([groups[p] for p in pick])
        rows = np.array([pos[r] for r in rows])
        try:
            b, *_ = np.linalg.lstsq(X_all[rows], y_all[rows], rcond=None)
            out.append(b)
        except np.linalg.LinAlgError:
            continue
    return np.array(out)


rows = []
rng = np.random.default_rng(SEED)
for label, s in SUBSETS.items():
    s = s.copy()
    s["dz_gate"] = s["dz_m"] * s["gate"]
    if label.startswith("CONTROL"):
        # Auf durchmischten Stunden ist gate = 0, damit sind beide Regressoren
        # identisch null. Die Kontrolle prueft daher die ungegateten Groessen:
        # bleibt nach freier Lapse-Rate-Anpassung noch ein CAP-Signal uebrig?
        s["dcap_gated"] = s["dcap"]
        s["dz_gate"] = s["dz_m"]
    s = s[np.isfinite(s.resid_K) & np.isfinite(s.dcap_gated) & np.isfinite(s.dz_gate)]
    n_pairs = s.groupby(["station_id_i", "station_id_j"]).ngroups
    for name, cols in [("gated only", ["dcap_gated"]),
                       ("gated + dz x gate", ["dcap_gated", "dz_gate"])]:
        if len(s) < MIN_OBS or s[cols].std().min() == 0:
            continue
        y = s["resid_K"].values
        X = s[cols].values
        b, r2 = fit(y, X)
        bb = boot_blocked(s, cols, "resid_K", rng)
        lo, hi = np.percentile(bb[:, 0], [2.5, 97.5])
        rec = dict(subset=label, model=name, n_obs=len(s), n_pairs=n_pairs,
                   mean_gate=round(float(s.gate.mean()), 3),
                   mean_inv_grad=round(float(s.inv_grad.mean()), 3),
                   mean_ff=round(float(s.ff_max.mean()), 2),
                   K_CAP=round(float(-b[0]), 3),
                   ci_lo=round(float(-hi), 3), ci_hi=round(float(-lo), 3),
                   r2=round(float(r2), 4))
        if len(cols) > 1:
            dl, dh = np.percentile(bb[:, 1], [2.5, 97.5])
            rec["dgamma_K_per_100m"] = round(float(b[1] * 100), 3)
            rec["dgamma_ci_lo"] = round(float(dl * 100), 3)
            rec["dgamma_ci_hi"] = round(float(dh * 100), 3)
        rows.append(rec)

res = pd.DataFrame(rows)
res.to_csv(f"{OUT}/cap_k_calibration_v2.csv", index=False)
pd.set_option("display.width", 220)
cols = ["subset", "model", "n_obs", "n_pairs", "mean_gate", "K_CAP", "ci_lo", "ci_hi",
        "r2", "dgamma_K_per_100m", "dgamma_ci_lo", "dgamma_ci_hi"]
print(res[[c for c in cols if c in res.columns]].to_string(index=False))
print(f"\ngespeichert: {OUT}/cap_k_calibration_v2.csv")


# ---------------------------------------------------------------------------
# Synthetischer Nachweis, dass der Mechanismus der behauptete ist
# ---------------------------------------------------------------------------
# Auf die echte Paar-, Gate- und dz-Struktur wird ein Residuum mit BEKANNTEM
# K_CAP und bekannter stabilitaetsabhaengiger Zusatzneigung aufgepraegt. Der
# Einfachschaetzer muss dann genau das Muster der Messung erzeugen (hohe Werte
# auf breiten, niedrige auf ruhigen Teilmengen), der Zweifachschaetzer muss den
# wahren Wert auf jeder Teilmenge zurueckgeben.
def synthetic_check(K_true=6.5, dgamma_true=0.0085, sigma=2.5, seed=7):
    rng = np.random.default_rng(seed)
    s = d.copy()
    s["y"] = (-K_true * s.dcap * s.gate + dgamma_true * s.dz_m * s.gate
              + rng.normal(0, sigma, len(s)))
    out = []
    for lab, sub in [("ALL", s), ("inversion", s[s.inv_on]),
                     ("inversion, calm", s[s.inv_on & (s.ff_max <= 1)]),
                     ("strong inversion, calm", s[(s.inv_grad >= 0.5) & (s.ff_max <= 1)])]:
        x = (sub.dcap * sub.gate).values
        y = sub.y.values
        k1 = -(x @ y) / (x @ x)
        A = np.column_stack([x, sub.dz_m.values * sub.gate.values])
        b = np.linalg.lstsq(A, y, rcond=None)[0]
        out.append(dict(subset=lab, K_true=K_true, K_one_term=round(float(k1), 2),
                        K_two_term=round(float(-b[0]), 2),
                        dgamma_K_per_100m=round(float(b[1] * 100), 2)))
    return pd.DataFrame(out)


syn = synthetic_check()
syn.to_csv(f"{OUT}/cap_k_synthetic_check.csv", index=False)
print("\nSynthetischer Test (wahres K_CAP = 6.5 K, wahre Zusatzneigung 0.85 K/100 m):")
print(syn.to_string(index=False))

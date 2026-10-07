# -*- coding: utf-8 -*-
"""Gemeinsame Pfade und Einstellungen fuer alle Diagramm-Skripte.

Alle Pfade werden aus der Lage dieses Ordners abgeleitet. Die Skripte laufen
deshalb unter Windows und Linux ohne Anpassung, egal aus welchem
Arbeitsverzeichnis sie gestartet werden, solange der Ordner Diagramm_Skripte
im Ordner Masterarbeit liegt.
"""
from pathlib import Path

SKRIPTE = Path(__file__).resolve().parent          # .../Masterarbeit/Diagramm_Skripte
MA = SKRIPTE.parent                                # .../Masterarbeit
REPO = MA / "Ice fall modeling" / "GutHub" / "ice-waterfalls"
OUTPUT = MA / "output"
ZWISCHEN = SKRIPTE / "_zwischendaten"              # ersetzt die frueheren /tmp-Dateien
ZWISCHEN.mkdir(exist_ok=True)


def abbildungen(skript):
    """Ausgabeordner fuer Abbildungen: <Kapitelordner>/abbildungen."""
    ordner = Path(skript).resolve().parent / "abbildungen"
    ordner.mkdir(exist_ok=True)
    return ordner


def schrift():
    """Schrift der Arbeit (Liberation Sans); unter Windows das metrisch gleiche Arial."""
    from matplotlib import font_manager
    vorhanden = {f.name for f in font_manager.fontManager.ttflist}
    for name in ("Liberation Sans", "Arial"):
        if name in vorhanden:
            return name
    return "DejaVu Sans"


def bloecke(n, groesse):
    """Teilt n Dateien in Bloecke [(a, b), ...] fuer die blockweise Verarbeitung."""
    return [(a, min(a + groesse, n)) for a in range(0, n, groesse)]


# ---------------------------------------------------------------------------
# Einheitliche Beschriftung (seit 28.09.2026)
# Wird in den Abbildungsskripten direkt vor fig.savefig() aufgerufen und bringt
# alle Texte der Abbildung auf die Schreibweise der Arbeit:
#   T_ice statt TLz (TLz ist nur der Spaltenname im Modellcode), °C statt deg C,
#   ≥/≤ statt >=/<=, ρ statt rho, δ_CAP, °C h, Einheiten mit Hochzahlen,
#   Gedankenstrich in Bereichen (1500–2000 m), echtes Minuszeichen vor Zahlen.
# ---------------------------------------------------------------------------
ERSETZUNGEN = [
    ("TLz", r"$T_{ice}$"),
    ("deg C", "\u00b0C"),
    ("(<=0.5 h)", "(\u2264 0.5 h)"),
    (">=", "\u2265"), ("<=", "\u2264"),
    ("rho =", "\u03c1 ="),
    ("\u03b4CAP", r"$\delta_{\mathrm{CAP}}$"),
    ("\u00b0C\u00b7h", "\u00b0C h"),
    ("MJ/m\u00b2 per day", r"MJ m$^{-2}$ d$^{-1}$"),
    ("MJ/m\u00b2", r"MJ m$^{-2}$"),
    ("mm/day", r"mm d$^{-1}$"),
    ("(h/d)", r"(h d$^{-1}$)"),
    ("1500-2000", "1500\u20132000"), ("2000-2500", "2000\u20132500"),
    ("0.5-4 h", "0.5\u20134 h"), ("P10-P90", "P10\u2013P90"),
    ("Theil-Sen", "Theil\u2013Sen"),
]


def _ersetzen(s):
    import re
    for a, b in ERSETZUNGEN:
        s = s.replace(a, b)
    # Bindestrich als Vorzeichen vor einer Zahl -> Minuszeichen (nicht in Datumsangaben)
    return re.sub(r"(^|[\s(=:/])-(?=\d)", "\\1\u2212", s)


def einheitlich(fig):
    """Beschriftung einer fertigen Abbildung vereinheitlichen (vor savefig aufrufen)."""
    import matplotlib as mpl
    from matplotlib.text import Text
    from matplotlib.ticker import FixedFormatter, FuncFormatter
    f = schrift()
    mpl.rcParams.update({"mathtext.fontset": "custom", "mathtext.rm": f,
                         "mathtext.it": f + ":italic", "mathtext.bf": f + ":bold",
                         "mathtext.sf": f, "mathtext.cal": f})
    fig.canvas.draw()
    for ax in fig.axes:
        for achse in (ax.xaxis, ax.yaxis):
            fm = achse.get_major_formatter()
            if isinstance(fm, FixedFormatter):
                fm.seq = [_ersetzen(str(s)) for s in fm.seq]
            elif isinstance(fm, FuncFormatter):   # feste Beschriftungen (set_xticks(..., labels), boxplot)
                achse.set_major_formatter(FuncFormatter(lambda x, pos, f=fm: _ersetzen(str(f(x, pos)))))
    for t in fig.findobj(Text):
        s = t.get_text()
        n = _ersetzen(s)
        if n != s:
            t.set_text(n)
    return fig

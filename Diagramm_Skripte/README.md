# Figure scripts

One folder per thesis section. Unless the figure index says otherwise, each script writes its figures to the `abbildungen/` folder next to it.

| Folder | Content |
|---|---|
| `0_Gemeinsame_Datenvorbereitung/` | shared preprocessing: model runs → intermediate data |
| `2_1_Untersuchungsgebiet/` | § 2.1 study area |
| `2_Methoden/` | § 2.2.8 method figures |
| `3_1_Meteorologische_Bedingungen/` | § 3.1 |
| `3_2_Modellierte_Eisentwicklung/` | § 3.2 |
| `3_3_und_3_4_Raeumliche_Unterschiede_und_Steuerung/` | § 3.3, 3.4 |
| `3_5_Validierung/` | § 3.5 |
| `3_6_und_3_7_Dekadische_Entwicklung_und_Szenarien/` | § 3.6, 3.7 |
| `Archiv_Cold-Air-Pooling-Korrektur/` | CAP recalibration, no longer part of the thesis |
| `_zwischendaten/` | frozen intermediate data read by the figure scripts |

`pfade.py` defines every path relative to its own location.

The figure index (script, inputs and output of each figure), the instructions for regenerating figures, the path rules and the data lineage are in the [main README](../README.md).

# Diagramm-Skripte der Masterarbeit

> Arbeitsprotokoll bis 29.09.2026. Abbildungs- und Kapitelnummern in der Tabelle unten sind der damalige Stand. Maßgeblich sind die Abbildungsübersicht und die Pfadregeln in `README.md` im Hauptordner. Seit 08.10.2026 tragen die Kapitelordner die Nummern der Arbeit: `3_5_Validierung` (vorher `3_6_Validierung`), `3_6_und_3_7_Dekadische_Entwicklung_und_Szenarien` (vorher `3_7_und_3_8_…`); die nicht mehr verwendete CAP-Kalibrierung liegt in `Archiv_Cold-Air-Pooling-Korrektur` (vorher `3_5_Cold-Air-Pooling-Korrektur`). Das Modell-Repo liegt unter `Ice fall modeling/GitHub/ice-waterfalls` (vorher `…/GutHub/…`).

Stand: 25.09.2026 (Abbildungsnummern nach dem Umbau von Kap. 3.1; die frühere INCA-Referenz, Abb. 15–17, ist durch eine Abbildung ersetzt: Aufbau wie die frühere Abb. 16, Temperatur jetzt aus den Stationen; alle späteren Nummern sind um 2 kleiner). Je Abbildung liegt hier die Skriptversion, die die Abbildung in `Masterarbeit.docx` erzeugt hat. Die Zuordnung ist über MD5-Vergleich der eingebetteten Bilder mit den Ausgabedateien geprüft; Abb. 7 und 21 sind im Dokument nicht bytegleich abgelegt und wurden über Pixelvergleich zugeordnet (bei Abb. 21 unterscheidet sich nur der Bereich des Nordpfeils). Ältere Fassungen liegen in `_Backup_alte_Versionen/`, dort mit ihrem ursprünglichen Pfad; `Verschiebeprotokoll.csv` listet jede verschobene Datei mit altem und neuem Ort.

Die erzeugten Bilder (PNG/PDF) wurden nicht verschoben, sie liegen weiter unter `output/...`.

## Übersicht

| Abb. | Kap. | Skript | Ausgabe (in der Arbeit verwendet) | braucht vorher |
|---|---|---|---|---|
| 1–6 | 1 | – | Literaturabbildungen | – |
| 7 | 2.1 | `2_1_Untersuchungsgebiet/build_study_area_map.py` (seit 27.09.2026: Kopie des Repo-Skripts `analysis/study_area_map/04_build_study_area_map.py`, ohne die frühere „North Tyrol workflow bbox“ und mit den 303 Routen der Arbeit statt 325; im Dokument auf 1255 px Breite verkleinert) | `2_1_Untersuchungsgebiet/abbildungen/study_area_icefall_inventory_map.png` | pyproj, pyshp, rasterio; OSM- und Natural-Earth-Cache in `output/study_area_map/_cache` |
| 8, 9 | 2.2.8 | `2_Methoden/build_method_figs.py` | `output/results_3_3_to_3_6/fig_method_workflow.png`, `fig_method_case.png` | – |
| 10, 11, 14 | 3.1 | `3_1_.../build_31figs.py` | `output/results_3_3_to_3_6/fig_3_1_station_temperature_distribution.png`, `fig_3_1_station_freezing_share.png`, `fig_3_1_station_degree_hours_by_elevation.png` | `station_temperature_daily_route_summary.csv` aus `build_results_3_1_station_temperature.R` |
| 12, 13 | 3.1 | `3_1_.../build_results_3_1_station_temperature.R` | `output/results_3_1_meteorological_conditions/fig_3_1_station_humidity_wind_radiation.png`, `fig_3_1_station_topographic_sun_hours.png` | – |
| 15 | 3.1 | `3_1_.../build_31_station_reference.py` | `3_1_.../abbildungen/fig_3_1_station_winter_reference.png` (dazu `station_reference_comparison.csv` mit den Zahlen im Text) | Temperatur (a–e): `tageswerte_voll.rds` und `tabellen/route_trends.csv` aus `FF2_Stationen/02_ff2_modelllauf.R`; Niederschlag und Strahlung (f–i): `inca_reference_point_daily.csv` und `inca_reference_hourly_coverage.csv` aus `build_inca_winter_reference.R`; Python-Paket `pyreadr` |
| 16, 17 | 3.2 | `3_2_.../build_results_3_2_modelled_ice.py` | `output/opus48/figs_new/fig_3_2_modelled_ice_thickness.png`, `fig_3_2_growth_melt_cold_phases.png` | `uid_daily_full_new.pkl` aus `3_2_.../uiddaily_chunk.py` |
| 18 | 3.2 | `3_2_.../build_allfalls.py` | `output/opus48/figs_new/fig_3_2_all_routes.png` | Caches aus `prep_caches.py`, `uid_season_metrics.csv` aus `build_3_34.py` |
| 19, 20, 22, 23 | 3.3, 3.4 | `3_3_und_3_4_.../build_3_34.py` (seit 27.09.2026: Abb. 23b zeigt statt der Spearman-Balken die direkte Wirkung der Faktoren aus `faktoren_kontrafaktisch.py` – das muss vorher gelaufen sein, `_zwischendaten/faktoren_kontra_routen.csv`; Abb. 20 mit gemeinsamer Legende der Höhenstufen unter der Abbildung, weil sie in 20b Punkte verdeckte; seit 25.09.2026: Abb. 22b auf −5 bis +5 °C, Titel von 23b mit n aus den Daten statt fest „n = 320“; Ausgabe jetzt in `3_3_und_3_4_.../abbildungen`) | `output/opus48/figs_new/fig_3_3_elevation.png`, `fig_3_3_aspect_sun_cap.png`, `fig_3_4_thermal_window.png`, `fig_3_4_seasonal_controls.png` | Caches aus `prep_caches.py`; für Abb. 20c zusätzlich `_zwischendaten/cap_kontra_routen.csv` aus `3_3_und_3_4_.../cap_kontrafaktisch.py` (Kommentar 65: Winter 2025/26 mit und ohne CAP-Term, Nachbau des Eiskörpers aus den gespeicherten Läufen, startet build_3_34.py danach selbst) |
| 21 | 3.3 | `3_3_und_3_4_.../build_map_only.py` | Fassung mit Nordpfeil nur im Dokument; `output/opus48/figs_new/fig_3_3_map_ice_days.png` ist die Fassung davor | `uid_season_metrics.csv` aus `build_3_34.py`, OSM-Kacheln |
| 24 | 3.5 | `Archiv_Cold-Air-Pooling-Korrektur/build_fig_cap_calibration_v2.py` | `output/opus48/fig_cap_calibration.png` | `cap_k_calibration_v2.csv` aus `Archiv_Cold-Air-Pooling-Korrektur/recalibrate_cap.py` (liest `data/CAP/cap_k_calibration_pairs.csv` aus dem Repo) |
| 25 | 3.6 | `3_5_Validierung/build_val4.py` | `output/opus48/figs_new/fig_3_5_validation_overview.png` | Review-Export und Modellläufe im Repo |
| 26, 27 | 3.6 | `3_5_Validierung/build_series_multi.py` | `output/opus48/figs_new/fig_photo_series_uid93.png`, `fig_photo_series_uid224.png` | Fotos im Repo |
| 28 | 3.6 | `3_5_Validierung/build_appendix_102.py` | `output/opus48/figs_new/fig_A1_taschach.png` | Fotos im Repo |
| 29 | 3.6 | `3_5_Validierung/build_sunfig.py` (seit 28.09.2026: Datum des Strahlungstags in (b) und (c) aus `SUNNY`/`CLOUD` statt fest „2026-03-05“ – die Werte stammten schon vorher vom 2026-02-27; im Dokument jetzt Abb. 28) | `3_5_Validierung/abbildungen/fig_3_5_sun_effect.png` (bis 28.09.2026: `output/opus48/figs_new/fig_3_5_sun_effect.png`) | `_zwischendaten/uid_daily_drivers.csv`, Foto im Repo |
| 30, 31 | 3.7 | `3_6_und_3_7_.../build_fig_3_7_stationen.py` | `3_6_und_3_7_.../abbildungen/fig_3_7_homogeneity.png`, `fig_3_7_decadal_stations.png` | Tabellen in `FF2_Stationen/ergebnis_modell/tabellen` aus `FF2_Stationen/02_ff2_modelllauf.R` |
| 32 | 3.7 | `3_6_und_3_7_.../build_longrec_fig.py` | `output/results_3_3_to_3_6/fig_3_6_longrec.png` | `longrec_winters.csv` aus `get_longrec_winters.R` |
| 33 | 3.8 | `3_6_und_3_7_.../build_fig2628.py` (nur noch der Szenario-Teil wird verwendet; `fig_3_6_decadal_proxy.png` ist seit 24.09.2026 nicht mehr in der Arbeit) | `output/results_3_3_to_3_6/fig_3_7_scenarios.png` | Proxy-Gitter aus `run_grid.py` (INCA-Cache aus `build_inca_winter_reference.R`), `traj_general.json` und `traj_sites.json` in `output/results_3_3_to_3_6` |

## Stand 29.09.2026: ohne Titel in den Abbildungen

- Abb. 7 (`build_study_area_map.py`): Titel „Study Area“ entfernt, Weißraum beim Speichern abgeschnitten (`bbox_inches="tight"`), Gradnetz jetzt mit °N/°E wie Abb. 21; im Dokument wieder auf 1255 px Breite verkleinert, Bildhöhe im docx angepasst. Braucht `pip install --user pyproj pyshp rasterio`.
- Abb. 12, 13 (`build_fig12_13_303.R`): Titel, Untertitel und Legendenzeile entfernt (steht in der Bildunterschrift).
- Abb. 15 (`build_31_station_reference.py`): Titel, Untertitel und Quellenzeile entfernt (steht in der Bildunterschrift); im Dokument auf 1256 px verkleinert. Braucht `pip install --user pyreadr`.
- Im Text der Arbeit sind negative Zahlen und die Rechenzeichen in den Formeln jetzt durchgehend Minuszeichen (−, U+2212) statt Bindestrich.
- Sicherung davor: `Masterarbeit Backups/Masterarbeit_vor_Titel_Minus_2026-09-29.docx`; alte Skripte/Bilder in `_Backup_alte_Versionen/vor_Titel_entfernen_2026-09-29/`.

## Stand 28.09.2026: einheitliche Beschriftung, T_ice statt TLz

- Neue Funktion `einheitlich(fig)` in `pfade.py`; alle unten genannten Python-Skripte rufen sie direkt vor `fig.savefig()` auf. Sie bringt jede Beschriftung auf die Schreibweise der Arbeit: $T_{ice}$ statt TLz (TLz ist nur der Spaltenname im Modellcode und identisch mit T_ice aus Gl. 12), °C statt deg C, ≥/≤ statt >=/<=, ρ statt rho, δ_CAP, °C h statt °C·h, Einheiten mit Hochzahlen (m s⁻¹, MJ m⁻², mm d⁻¹, h d⁻¹), Gedankenstrich in Bereichen (1500–2000 m, P10–P90, 0.5–4 h), Theil–Sen, echtes Minuszeichen vor Zahlen. Formeltext in der Schrift der Abbildungen (Liberation Sans bzw. Arial).
- Neu erzeugt und in `Masterarbeit.docx` getauscht: Abb. 10–14, 16–23, 25–28, 30–32 (Abb. 29 unverändert). Sicherung davor: `Masterarbeit Backups/Masterarbeit_vor_Tice_Abbildungen_2026-09-28.docx`; alte Skripte und Bilder in `_Backup_alte_Versionen/vor_Vereinheitlichung_2026-09-28/`.
- Inhaltliche Korrekturen dabei:
  - Abb. 10, 11, 14 (`build_31figs.py`): Tageswerte jetzt aus den finalen Modellläufen (`_zwischendaten/uid_daily_drivers.csv`, FDH/PDH ÷ 6 → °C h) statt aus der Nebenrechnung mit der alten CAP-Parametrisierung; damit passen sie zu den Zahlen in Kap. 3.1.
  - Abb. 12, 13: neues Skript `3_1_Meteorologische_Bedingungen/build_fig12_13_303.R` (Nachbau von fig4/fig5 aus `build_results_3_1_station_temperature.R`), jetzt nur die 303 Routen der Arbeit statt 325; Einheiten mit Hochzahlen. Median der Globalstrahlung dadurch 6,35 statt 6,42 MJ m⁻² d⁻¹ (Text 3.1: 6.3). Liest `output/results_3_1_meteorological_conditions/station_temperature_daily_route_summary.csv` und `_zwischendaten/uid_daily_drivers.csv`; läuft in wenigen Sekunden.
  - Abb. 23a (`build_3_34.py`): x-Achse war um den Faktor 6 zu groß (Summe je 10-min-Schritt statt °C h); jetzt ÷ 6000.
  - Abb. 25–27 (`build_series_multi.py`, `build_appendix_102_v2.py`): Zeitachse auf den Untersuchungszeitraum 01.10.2025–30.04.2026 begrenzt (vorher bis August).
  - Abb. 28 (`build_sunfig.py`): Datum des Strahlungstags aus den Daten (2026-02-27) statt fest „2026-03-05“.
  - `build_results_3_2_modelled_ice.py` liest `uid_daily_full_new.pkl` jetzt aus `_zwischendaten/` (Kopie aus `output/opus48/`).

## Gemeinsame Datenvorbereitung (Kap. 3.2–3.6)

`0_Gemeinsame_Datenvorbereitung/` enthält die Kette, die aus den CAP-aktualisierten Modellläufen die Zwischendateien für Abb. 18–23 und 29 baut:

1. `prep_uid_v2.py` – statische Routenattribute (`uid_static.csv`)
2. `recompute_chunk.py` – Tages- und Saisonwerte je Route (`uid_daily_new.csv`, `uid_static_new.csv`, `uid_season_new.csv`)
3. `thick_chunk.py` – tägliche Mediandicke je Route (`uid_daily_thick_new.pkl`)
4. `prep_caches.py` – setzt daraus die Caches unter `/tmp` zusammen, die die Abbildungsskripte lesen

Reihenfolge danach: `build_3_34.py` vor `build_allfalls.py` und `build_map_only.py`, weil beide dessen `uid_season_metrics.csv` lesen.

Stand 25.09.2026: `_zwischendaten/uid_daily_thick_new.pkl` ist aus `output/opus48/uid_daily_thick_new.pkl` übernommen (dieselben CAP-aktualisierten Läufe, 303 Routen), statt mit `thick_chunk.py` die 8 GB Modellläufe neu einzulesen. Die damit neu erzeugten Abb. 19–23 sind bis auf Kantenglättung pixelgleich mit den Bildern in der Arbeit.

## Bekannte Einschränkungen

- Die Python-Skripte enthalten noch die absoluten Pfade der Claude-Sitzungen, in denen sie gelaufen sind (`/sessions/<name>/mnt/Masterarbeit/...`), und schreiben bzw. lesen Zwischendateien unter `/tmp`. So wie sie sind, laufen sie nicht direkt unter Windows. Der Code selbst wurde beim Verschieben nicht verändert.
- Die R-Skripte erwarten den Ordner `Masterarbeit` als Arbeitsverzeichnis. Ausnahme: `get_longrec_winters.R` schreibt `longrec_winters.csv` ins aktuelle Arbeitsverzeichnis; `build_longrec_fig.py` liest die Datei aus `output/results_3_3_to_3_6`.
- `uiddaily_chunk.py` importiert `build_results_3_2_modelled_ice.py`; beide liegen deshalb im selben Ordner.
- Für `traj_general.json` und `traj_sites.json` (Abb. 33) und das Zusammenführen der `run_grid.py`-Teilergebnisse zu `grid_res_all.pkl` / `grid_cur_all.pkl` liegt kein Skript im Ordner vor.

## Bewusst nicht verschoben

- GitHub-Repo `Ice fall modeling/GitHub/ice-waterfalls`: `04_build_study_area_map.py` (Abb. 7; `_locator_right` ist eine nicht verwendete Variante), `06_calibrate_cap_k.R` (Stationspaare für Abb. 26), `diagram_uid.R` (Website-Diagramme). Die Arbeit verweist auf das Repo, daher bleibt es unverändert.
- `FF2_Stationen/`: stationsbasierte Neuberechnung für Kap. 3.7 (Modellläufe, Stationsprüfung, Tabellen); die Abbildungen 30 und 31 daraus erzeugt `3_6_und_3_7_.../build_fig_3_7_stationen.py`.
- `Verteidigung/quellcode/`: Skripte für die Folien.
- Skripte, die `Masterarbeit.docx` bearbeitet haben (`fix_*`, `k*_*`, `swap_*`, `update_docx*` usw. in `output/opus48` und `output/results_3_3_to_3_6`), sowie Kennzahl-Skripte ohne Abbildung (`daily_stats_new.py`, `detail_values_new.py`, `compare_old_new.py`, `cap_impact.py`).

## Nicht mehr in der Arbeit (seit 25.09.2026)

- `3_1_.../k5_map.py` – Karte der INCA-Referenzpunkte (bis 25.09.2026 Abb. 15). Die Stichprobe selbst wird nur noch in Kap. 3.8 verwendet und steht in Tab. 4 im Anhang.
- Abbildungen aus `3_1_.../build_inca_winter_reference.R` (bis 25.09.2026 Abb. 16 und 17). Das Skript bleibt trotzdem nötig: Es erzeugt den INCA-Cache für `run_grid.py` (Abb. 33) und `inca_reference_point_daily.csv`, aus der `build_31_station_reference.py` Niederschlag und Strahlung für Abb. 15 liest (28 Punkte ohne die zwei Nordwände, jede INCA-Zelle einmal; die frühere Auswertung lief über alle 32 Routen).

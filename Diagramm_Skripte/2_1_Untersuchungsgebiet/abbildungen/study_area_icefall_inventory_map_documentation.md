# Study-Area Icefall Inventory Map

## Created map files

- `/sessions/rcw-01tt2seazuzmsfsj14vglkx4/mnt/Masterarbeit/Diagramm_Skripte/2_1_Untersuchungsgebiet/abbildungen/study_area_icefall_inventory_map.png`: high-resolution PNG, 300 dpi, Word-ready raster export.
- `/sessions/rcw-01tt2seazuzmsfsj14vglkx4/mnt/Masterarbeit/Diagramm_Skripte/2_1_Untersuchungsgebiet/abbildungen/study_area_icefall_inventory_map.pdf`: PDF export with vector text and raster hillshade.
- `/sessions/rcw-01tt2seazuzmsfsj14vglkx4/mnt/Masterarbeit/Diagramm_Skripte/2_1_Untersuchungsgebiet/abbildungen/study_area_icefall_inventory_map.svg`: SVG export with vector text and raster hillshade.

## Data used

- `/sessions/rcw-01tt2seazuzmsfsj14vglkx4/mnt/Masterarbeit/Ice fall modeling/GutHub/ice-waterfalls/data/AWS/icefalls_nearest_station.csv`: final mapped icefall working inventory; all plotted points come from this file.
- `/sessions/rcw-01tt2seazuzmsfsj14vglkx4/mnt/Masterarbeit/Ice fall modeling/GutHub/ice-waterfalls/data/Koordinaten_Wasserfaelle/eisklettern_links_entries_diff.csv`: cross-check only for UID and coordinate consistency.
- `/sessions/rcw-01tt2seazuzmsfsj14vglkx4/mnt/Masterarbeit/Ice fall modeling/GutHub/ice-waterfalls/data/DEM/eudem_dem_3035_europe.tif`: available local DEM; not used in the current OSM Standard tile rendering.
- `/sessions/rcw-01tt2seazuzmsfsj14vglkx4/mnt/Masterarbeit/Ice fall modeling/GutHub/ice-waterfalls/data/ModelRuns`: QA only, used to identify existing, missing, or stale model outputs.
- Natural Earth 10 m admin-0 and admin-1 boundaries, cached under `/sessions/rcw-01tt2seazuzmsfsj14vglkx4/mnt/Masterarbeit/output/study_area_map/_cache`.
- OpenStreetMap Standard tile layer, (c) OpenStreetMap contributors (ODbL), cached under `/sessions/rcw-01tt2seazuzmsfsj14vglkx4/mnt/Masterarbeit/output/study_area_map/_cache` and plotted in EPSG:3857.

## CRS and projection

The source icefall coordinates are WGS 84 / EPSG:4326. The plotted map uses Web Mercator / EPSG:3857 to preserve the requested one-to-one OpenStreetMap Standard tile background. The scale bar is corrected for the central map latitude.

## QA checks

- Station-assigned rows plotted: 303.
- Unique station-assigned UIDs: 303.
- Valid plotted coordinates: 303.
- Raw coordinate inventory rows: 777; raw rows with valid coordinates: 765.
- Raw coordinate-bearing UIDs intentionally not plotted: 462.
- Assigned UIDs missing from raw inventory: none.
- Existing model-output UID files: 356.
- Existing model-output UID files matching assignment table: 303.
- Assigned UIDs without inspected model output: 0; sample: .
- Stale model-output UIDs outside assignment table: 302, 318, 320, 331, 354, 371, 374, 375, 383, 393, 395, 408, 415, 418, 439, 442, 445, 464, 465, 485, 501, 508, 514, 515, 535, 539, 552, 557, 565, 573, 575, 576, 593, 608, 609, 617, 619, 628, 641, 655, 659, 661, 662, 667, 683, 695, 711, 731, 732, 738, 782, 792, 811.
- Coordinate mismatches above 0.0002 degrees: 0.
- Station-assigned UIDs inside the North Tyrol workflow bbox: 238.
- OSM Standard tile zoom: 11.
- OSM Standard tiles used for the main map mosaic: 322.

## Coordinate mismatch sample

- None above the 0.0002 degree QA threshold.

## Cartographic decisions

- The point layer is the station-assigned operational modelling inventory, not the full raw coordinate inventory.
- Icefalls are symbolized by elevation because elevation is methodologically relevant to ice formation, temperature correction, and model forcing.
- The background uses the OpenStreetMap Standard raster tile layer as requested, with visible OSM attribution in the figure source note.
- The OSM tile mosaic is used as background context only; all icefall coordinates remain the project-derived station-assigned inventory.
- The former separate detail and locator panels were collapsed into one main map with an embedded locator inset; the North Tyrol workflow bbox remains as a subtle dashed frame.
- Place labels come from the OpenStreetMap Standard tile layer; no separate icefall labels are added to avoid overcrowding.
- Map author: C. Wydra.

## Suggested figure caption

Study-area map of the selected station-assigned waterfall-ice working inventory used for the modelling workflow. Points represent the operational assignment table, not a complete inventory of all waterfall-ice routes in Tyrol. Point colour indicates DEM-derived icefall elevation. The map shows the full Tyrolean and adjacent Alpine working extent; the dashed rectangle marks the North Tyrol modelling bbox used in the workflow, and the locator inset shows the position of the mapped extent within Austria and the Alps. The background is the OpenStreetMap Standard tile layer (c) OpenStreetMap contributors, ODbL, in Web Mercator (EPSG:3857). Boundaries are from Natural Earth, and icefall coordinates from data/AWS/icefalls_nearest_station.csv. Coordinates are stored in WGS 84 (EPSG:4326) and displayed in Web Mercator (EPSG:3857). Map author: C. Wydra.

## Suggested methods paragraph

The study area was delineated from the operational station-assigned icefall dataset used by the implemented model workflow. This region provides a dense set of selected waterfall-ice sites across strong elevation and valley-geometry gradients and is covered by the meteorological and topographic input data used by the model. The mapped icefalls are therefore a selected modelling basis rather than a complete regional census. This limits spatial interpretation to the coverage of the implemented workflow and prevents conclusions about the full population of waterfall-ice routes in Tyrol.

## Open points

- <span style="color:red">Existing model-output CSVs cover 303 of 303 station-assigned UIDs; 0 assigned UIDs have no inspected model-output CSV in data/ModelRuns.</span>
- <span style="color:red">Stale or inconsistent model-output UIDs outside the assignment table: 302, 318, 320, 331, 354, 371, 374, 375, 383, 393, 395, 408, 415, 418, 439, 442, 445, 464, 465, 485, 501, 508, 514, 515, 535, 539, 552, 557, 565, 573, 575, 576, 593, 608, 609, 617, 619, 628, 641, 655, 659, 661, 662, 667, 683, 695, 711, 731, 732, 738, 782, 792, 811.</span>
- <span style="color:red">The exact final thesis production run date for model outputs is not fixed in the inspected files.</span>
- <span style="color:red">The study-area wording remains 'selected working inventory in Tyrol and adjacent Alpine sectors' unless a stricter administrative Tyrol-only interpretation is chosen later.</span>

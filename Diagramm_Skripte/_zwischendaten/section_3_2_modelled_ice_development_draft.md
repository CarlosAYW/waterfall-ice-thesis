# Section 3.2 draft material

## Draft paragraph

During the model period from 2025-10-01 to 2026-04-30 (n = 303 complete UID model runs), modelled ice development was episodic and controlled by a few cold windows. The median thickness first exceeded 0.05 m on 2025-11-18, 0.10 m on 2025-11-20, and 0.15 m on 2025-11-21. The strongest accumulation phase increased the median modelled thickness to a seasonal maximum of 0.46 m on 2026-01-12. Subsequent warm periods and increasing spring radiation shifted most routes toward melt, and by 2026-04-30 the median modelled thickness had declined to 0.00 m. Overall, the model indicates pulse-like ice build-up during distinct cold periods followed by a broad late-season melt phase.

## Suggested figures

- Figure 3.X: `fig_3_2_modelled_ice_thickness.png` - Seasonal evolution of modelled ice thickness from the original UID model runs. The line shows the median across complete UID runs; shaded bands show the interquartile range and P10-P90 range. Blue background bands mark cold periods (median TLz < -3 deg C), and red bands mark median melt periods.
- Figure 3.X: `fig_3_2_growth_melt_cold_phases.png` - Daily share of original UID model runs in growth, stable and melt phases, with median route-adjusted temperature (TLz) shown below.

## Method note

These figures are aggregated from `diagram_uid.R` outputs in `data/ModelRuns`, i.e. the model run with station forcing, inversion/CAP correction, topographic sun, wind vulnerability and radiation terms.

#!/usr/bin/env Rscript

# ---- Arbeitsverzeichnis auf den Ordner 'Masterarbeit' setzen ------------------
# Funktioniert mit source("..."), dem Source-Knopf in RStudio und Rscript,
# solange das Skript in Masterarbeit/Diagramm_Skripte/<Kapitelordner>/ liegt.
local({
  pfad <- NULL
  arg <- grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE)
  if (length(arg)) pfad <- gsub("~+~", " ", sub("^--file=", "", arg[1]), fixed = TRUE)
  if (is.null(pfad)) {
    for (i in rev(seq_len(sys.nframe()))) {
      of <- sys.frame(i)$ofile
      if (!is.null(of)) { pfad <- of; break }
    }
  }
  if (is.null(pfad) && requireNamespace("rstudioapi", quietly = TRUE) &&
      rstudioapi::isAvailable()) {
    pfad <- rstudioapi::getSourceEditorContext()$path
  }
  if (!is.null(pfad) && nzchar(pfad)) {
    setwd(dirname(dirname(dirname(normalizePath(pfad, winslash = "/")))))
  }
  if (!dir.exists(file.path("Ice fall modeling", "GutHub", "ice-waterfalls"))) {
    stop("Ordner 'Masterarbeit' nicht gefunden. Bitte setwd() auf den Ordner 'Masterarbeit' setzen.")
  }
})
# -------------------------------------------------------------------------------

# Abb. 12 und 13 der Arbeit
# Nur die 303 Routen der Arbeit (icefalls_nearest_station.csv).
# Abb. 12: Tageswerte je Route aus station_temperature_daily_route_summary.csv
#          (Stationsfeuchte, INCA-Wind und -Globalstrahlung; von der CAP-Parametrisierung unabhaengig).
# Abb. 13: topographisches Sonnenfenster je Route und Tag aus _zwischendaten/uid_daily_drivers.csv
#          (sun_h = sun_hours_topo der finalen Modelllaeufe).
# Schrift: Standard-Sans (Windows: Arial); ueber die Umgebungsvariable ABB_SCHRIFT aenderbar.

suppressPackageStartupMessages({
  library(readr); library(dplyr); library(tidyr); library(ggplot2); library(stringr)
})

in_dir  <- file.path("output", "results_3_1_meteorological_conditions")
out_dir <- file.path("Diagramm_Skripte", "3_1_Meteorologische_Bedingungen", "abbildungen")
dir.create(out_dir, showWarnings = FALSE, recursive = TRUE)
fam <- Sys.getenv("ABB_SCHRIFT", "")

routes <- read_csv(file.path("Ice fall modeling", "GutHub", "ice-waterfalls", "data", "AWS",
                             "icefalls_nearest_station.csv"), show_col_types = FALSE)$uid

theme_thesis <- function(base_size = 10) {
  theme_minimal(base_size = base_size, base_family = fam) +
    theme(
      text = element_text(color = "#222222"),
      plot.title = element_text(face = "bold", size = base_size + 2),
      plot.subtitle = element_text(size = base_size, color = "#444444"),
      axis.title = element_text(size = base_size),
      panel.grid.minor = element_blank(),
      panel.grid.major.x = element_line(color = "#e5e5e5", linewidth = 0.25),
      panel.grid.major.y = element_line(color = "#dedede", linewidth = 0.25),
      strip.text = element_text(face = "bold", color = "#222222"),
      legend.position = "top",
      legend.title = element_text(size = base_size - 1),
      legend.text = element_text(size = base_size - 1),
      plot.caption = element_text(color = "#555555", hjust = 0, size = base_size - 2)
    )
}

# ---- Abb. 12: Feuchte, Wind, Strahlung ----
daily_route <- read_csv(file.path(in_dir, "station_temperature_daily_route_summary.csv"),
                        show_col_types = FALSE) %>%
  filter(uid %in% routes) %>%
  mutate(date = as.Date(date))
stopifnot(n_distinct(daily_route$uid) == 303)
q <- function(x, p) quantile(x, p, na.rm = TRUE)
daily_dist <- daily_route %>%
  group_by(date) %>%
  summarise(rh_p25 = q(rh_mean_pct, .25), rh_median = median(rh_mean_pct, na.rm = TRUE), rh_p75 = q(rh_mean_pct, .75),
            wind_p25 = q(wind_mean_ms, .25), wind_median = median(wind_mean_ms, na.rm = TRUE), wind_p75 = q(wind_mean_ms, .75),
            rad_p25 = q(rad_mj_m2, .25), rad_median = median(rad_mj_m2, na.rm = TRUE), rad_p75 = q(rad_mj_m2, .75),
            .groups = "drop")
period_start <- min(daily_route$date); period_end <- max(daily_route$date)

forcing_long <- daily_dist %>%
  pivot_longer(-date, names_to = "name", values_to = "value") %>%
  mutate(
    variable = case_when(
      str_starts(name, "rh") ~ "Station relative humidity (%)",
      str_starts(name, "wind") ~ "INCA wind speed (m s⁻¹)",
      str_starts(name, "rad") ~ "INCA global radiation (MJ m⁻² d⁻¹)",
      TRUE ~ name),
    stat = case_when(str_ends(name, "p25") ~ "p25", str_ends(name, "median") ~ "median",
                     str_ends(name, "p75") ~ "p75", TRUE ~ name)) %>%
  select(date, variable, stat, value) %>%
  pivot_wider(names_from = stat, values_from = value)

fig4 <- ggplot(forcing_long, aes(date)) +
  geom_ribbon(aes(ymin = p25, ymax = p75), fill = "#74a9cf", alpha = 0.35) +
  geom_line(aes(y = median), color = "#045a8d", linewidth = 0.75) +
  facet_wrap(~ variable, ncol = 1, scales = "free_y") +
  scale_x_date(date_breaks = "1 month", date_labels = "%b") +
  labs(x = NULL, y = NULL) +
  theme_thesis()
ggsave(file.path(out_dir, "fig_3_1_station_humidity_wind_radiation.png"), fig4,
       width = 7.2, height = 6.6, dpi = 300, bg = "white")

# ---- Abb. 13: topographisches Sonnenfenster ----
sun_daily <- read_csv(file.path("Diagramm_Skripte", "_zwischendaten", "uid_daily_drivers.csv"),
                      col_select = c(uid, date, sun_h), show_col_types = FALSE) %>%
  filter(uid %in% routes) %>%
  mutate(date = as.Date(date)) %>%
  filter(date >= as.Date("2025-11-01"), date <= as.Date("2026-04-30"))
stopifnot(n_distinct(sun_daily$uid) == 303)
sun_dist <- sun_daily %>% group_by(date) %>%
  summarise(sun_p10 = q(sun_h, .10), sun_p25 = q(sun_h, .25), sun_median = median(sun_h, na.rm = TRUE),
            sun_p75 = q(sun_h, .75), sun_p90 = q(sun_h, .90), .groups = "drop")

fig5 <- ggplot(sun_dist, aes(date)) +
  geom_ribbon(aes(ymin = sun_p10, ymax = sun_p90), fill = "#fdae6b", alpha = 0.28) +
  geom_ribbon(aes(ymin = sun_p25, ymax = sun_p75), fill = "#e6550d", alpha = 0.32) +
  geom_line(aes(y = sun_median), color = "#a63603", linewidth = 0.8) +
  scale_x_date(date_breaks = "1 month", date_labels = "%b") +
  labs(x = NULL, y = "Topographic sun hours per day") +
  theme_thesis()
ggsave(file.path(out_dir, "fig_3_1_station_topographic_sun_hours.png"), fig5,
       width = 7.2, height = 4.2, dpi = 300, bg = "white")

# Kennzahlen fuer den Text (Kap. 3.1)
end <- sun_dist %>% filter(date == max(date))
cat(sprintf("303 Routen | Median Tagesmittel: RF %.1f %%, Wind %.2f m/s, Globalstrahlung %.2f MJ/m2/d\n",
            median(daily_route$rh_mean_pct, na.rm = TRUE), median(daily_route$wind_mean_ms, na.rm = TRUE),
            median(daily_route$rad_mj_m2, na.rm = TRUE)))
cat(sprintf("Sonnenfenster %s: Median %.2f h, IQR %.2f-%.2f h\n", end$date, end$sun_median, end$sun_p25, end$sun_p75))

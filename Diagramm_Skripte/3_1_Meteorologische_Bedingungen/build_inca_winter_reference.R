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
  if (!dir.exists(file.path("Ice fall modeling", "GitHub", "ice-waterfalls"))) {
    stop("Ordner 'Masterarbeit' nicht gefunden. Bitte setwd() auf den Ordner 'Masterarbeit' setzen.")
  }
})
# -------------------------------------------------------------------------------

suppressPackageStartupMessages({
  library(httr2)
  library(readr)
  library(dplyr)
  library(tidyr)
  library(ggplot2)
  library(lubridate)
  library(stringr)
  library(zoo)
  library(scales)
})

root <- normalizePath(file.path("Ice fall modeling", "GitHub", "ice-waterfalls"), winslash = "/", mustWork = TRUE)
base_out_dir <- normalizePath(file.path("output", "results_3_1_meteorological_conditions"), winslash = "/", mustWork = TRUE)
out_dir <- file.path(base_out_dir, "inca_winter_reference")
cache_dir <- file.path(out_dir, "cache")
dir.create(out_dir, showWarnings = FALSE, recursive = TRUE)
dir.create(cache_dir, showWarnings = FALSE, recursive = TRUE)

assign_path <- file.path(root, "data", "AWS", "icefalls_nearest_station.csv")
api_base <- "https://dataset.api.hub.geosphere.at/v1/timeseries/historical/inca-v1-1h-1km"
dataset_url <- "https://data.hub.geosphere.at/dataset/inca-v1-1h-1km"

tz_local <- "Europe/Vienna"
reference_start_year <- 2012
current_start_year <- 2025
reference_years <- reference_start_year:(current_start_year - 1)
season_years <- reference_start_year:current_start_year
n_per_band <- 8
chunk_size <- 8

to_num <- function(x) {
  if (is.numeric(x)) return(as.numeric(x))
  x <- as.character(x)
  x[x %in% c("", "NA", "NaN", "NULL", "---")] <- NA_character_
  x <- gsub(",", ".", x, fixed = TRUE)
  suppressWarnings(as.numeric(x))
}

theme_thesis <- function(base_size = 10) {
  theme_minimal(base_size = base_size) +
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

save_plot <- function(plot, name, width, height) {
  png_path <- file.path(out_dir, paste0(name, ".png"))
  pdf_path <- file.path(out_dir, paste0(name, ".pdf"))
  ggsave(png_path, plot, width = width, height = height, dpi = 300, bg = "white")
  ggsave(pdf_path, plot, width = width, height = height, bg = "white")
  invisible(c(png_path, pdf_path))
}

longest_run <- function(x) {
  x <- as.logical(x)
  x[is.na(x)] <- FALSE
  if (!length(x)) return(0L)
  r <- rle(x)
  if (!any(r$values)) return(0L)
  as.integer(max(r$lengths[r$values]))
}

count_runs_min <- function(x, min_len = 5L) {
  x <- as.logical(x)
  x[is.na(x)] <- FALSE
  if (!length(x)) return(0L)
  r <- rle(x)
  as.integer(sum(r$values & r$lengths >= min_len))
}

season_label <- function(start_year) {
  sprintf("%d/%02d", start_year, (start_year + 1) %% 100)
}

season_start <- function(start_year) {
  as.Date(sprintf("%d-10-01", start_year))
}

season_end <- function(start_year) {
  as.Date(sprintf("%d-04-30", start_year + 1))
}

canonical_date <- function(date) {
  md <- format(date, "%m-%d")
  as.Date(ifelse(md >= "10-01", paste0("2025-", md), paste0("2026-", md)))
}

make_url <- function(params) {
  pairs <- character()
  for (nm in names(params)) {
    vals <- params[[nm]]
    for (val in vals) {
      pairs <- c(
        pairs,
        paste0(
          utils::URLencode(nm, reserved = TRUE),
          "=",
          utils::URLencode(as.character(val), reserved = TRUE)
        )
      )
    }
  }
  paste0(api_base, "?", paste(pairs, collapse = "&"))
}

download_inca_chunk <- function(points, start_date, end_date, season_lab, chunk_id) {
  outfile <- file.path(
    cache_dir,
    sprintf("inca_%s_chunk%02d_%s_%s.csv",
      gsub("/", "_", season_lab),
      chunk_id,
      format(start_date, "%Y%m%d"),
      format(end_date, "%Y%m%d")
    )
  )
  if (file.exists(outfile) && file.info(outfile)$size > 0) return(outfile)

  url <- make_url(list(
    parameters = "T2M,RR,GL",
    start = sprintf("%sT00:00", format(start_date, "%Y-%m-%d")),
    end = sprintf("%sT23:00", format(end_date, "%Y-%m-%d")),
    lat_lon = sprintf("%.6f,%.6f", points$ice_lat, points$ice_lon),
    output_format = "csv"
  ))

  message("Downloading INCA ", season_lab, " chunk ", chunk_id, " (", nrow(points), " points)")
  resp <- request(url) |>
    req_user_agent("icefall-master-thesis/1.0 (R httr2)") |>
    req_retry(max_tries = 5) |>
    req_error(is_error = function(resp) FALSE) |>
    req_perform()

  if (resp_status(resp) >= 400) {
    msg <- tryCatch(resp_body_string(resp), error = function(e) "")
    stop("INCA download failed for ", season_lab, " chunk ", chunk_id, " (HTTP ", resp_status(resp), "). ", msg)
  }

  writeLines(resp_body_string(resp), outfile, useBytes = TRUE)
  Sys.sleep(0.2)
  outfile
}

parse_inca_csv <- function(file, points, start_date, end_date, season_lab, chunk_id) {
  raw <- readr::read_csv(file, show_col_types = FALSE, progress = FALSE)
  if (!nrow(raw)) stop("Empty INCA CSV: ", file)

  nms <- names(raw)
  t2m_col <- nms[str_detect(nms, "^T2M")][1]
  rr_col <- nms[str_detect(nms, "^RR")][1]
  gl_col <- nms[str_detect(nms, "^GL")][1]
  lat_col <- intersect(c("lat", "latitude"), nms)[1]
  lon_col <- intersect(c("lon", "longitude"), nms)[1]
  if (any(is.na(c(t2m_col, rr_col, gl_col, lat_col, lon_col)))) {
    stop("Unexpected INCA CSV columns in ", file, ": ", paste(nms, collapse = ", "))
  }

  parsed <- raw %>%
    transmute(
      row_id = row_number(),
      time_utc = suppressWarnings(lubridate::ymd_hms(.data[["time"]], tz = "UTC")),
      T2M = to_num(.data[[t2m_col]]),
      RR = to_num(.data[[rr_col]]),
      GL = to_num(.data[[gl_col]]),
      api_lat = to_num(.data[[lat_col]]),
      api_lon = to_num(.data[[lon_col]])
    ) %>%
    filter(!is.na(time_utc))

  if (!nrow(parsed)) stop("No parseable timestamps in ", file)

  group_break <- with(parsed, {
    row_id == 1L |
      api_lat != dplyr::lag(api_lat) |
      api_lon != dplyr::lag(api_lon) |
      time_utc <= dplyr::lag(time_utc)
  })
  group_break[is.na(group_break)] <- TRUE

  parsed <- parsed %>%
    mutate(point_order = cumsum(group_break))

  returned_groups <- parsed %>%
    group_by(point_order) %>%
    summarise(
      api_lat = first(api_lat),
      api_lon = first(api_lon),
      n_hours = n(),
      .groups = "drop"
    )

  point_meta <- points %>%
    mutate(point_order = row_number()) %>%
    select(point_order, uid, icefall_name, ice_lat, ice_lon, icefall_elev_m, elevation_band)

  if (nrow(returned_groups) != nrow(point_meta)) {
    warning("INCA returned ", nrow(returned_groups), " point groups for ", nrow(point_meta),
      " requested points in ", season_lab, " chunk ", chunk_id, "."
    )
  }

  parsed %>%
    left_join(point_meta, by = "point_order") %>%
    mutate(
      season = season_lab,
      season_start_year = as.integer(substr(season_lab, 1, 4)),
      chunk_id = chunk_id,
      date_utc = as.Date(time_utc),
      date_local = as.Date(with_tz(time_utc, tz_local)),
      api_lat = api_lat,
      api_lon = api_lon
    ) %>%
    filter(date_utc >= start_date, date_utc <= end_date)
}

select_sample_points <- function(assign, n_per_band = 8L) {
  assign %>%
    transmute(
      uid = as.integer(uid),
      icefall_name = as.character(icefall_name),
      ice_lat = to_num(ice_lat),
      ice_lon = to_num(ice_lon),
      icefall_elev_m = to_num(icefall_elev_m),
      elevation_band = cut(
        icefall_elev_m,
        breaks = c(-Inf, 1500, 2000, 2500, Inf),
        labels = c("<1500 m", "1500-2000 m", "2000-2500 m", ">2500 m")
      )
    ) %>%
    filter(
      is.finite(ice_lat),
      is.finite(ice_lon),
      is.finite(icefall_elev_m),
      !is.na(elevation_band)
    ) %>%
    mutate(lat_round = round(ice_lat, 4), lon_round = round(ice_lon, 4)) %>%
    arrange(elevation_band, ice_lon, ice_lat, uid) %>%
    distinct(elevation_band, lat_round, lon_round, .keep_all = TRUE) %>%
    group_by(elevation_band) %>%
    group_modify(function(.x, .y) {
      .x <- .x %>% arrange(ice_lon, ice_lat, icefall_elev_m, uid)
      n_pick <- min(n_per_band, nrow(.x))
      idx <- unique(round(seq(1, nrow(.x), length.out = n_pick)))
      .x[idx, , drop = FALSE]
    }) %>%
    ungroup() %>%
    select(uid, icefall_name, ice_lat, ice_lon, icefall_elev_m, elevation_band) %>%
    arrange(elevation_band, ice_lon, ice_lat, uid)
}

assign <- readr::read_csv(assign_path, show_col_types = FALSE)
sample_points <- select_sample_points(assign, n_per_band = n_per_band)
readr::write_csv(sample_points, file.path(out_dir, "inca_reference_sample_points.csv"))

chunks <- split(sample_points, ceiling(seq_len(nrow(sample_points)) / chunk_size))

hourly <- list()
for (sy in season_years) {
  s0 <- season_start(sy)
  s1 <- season_end(sy)
  lab <- season_label(sy)
  for (chunk_id in seq_along(chunks)) {
    f <- download_inca_chunk(chunks[[chunk_id]], s0, s1, lab, chunk_id)
    hourly[[length(hourly) + 1L]] <- parse_inca_csv(f, chunks[[chunk_id]], s0, s1, lab, chunk_id)
  }
}

hourly <- bind_rows(hourly) %>%
  filter(!is.na(uid)) %>%
  mutate(
    RR = ifelse(is.na(RR), 0, pmax(0, RR)),
    GL = ifelse(is.na(GL), NA_real_, pmax(0, GL)),
    FDH = pmax(0, -T2M),
    PDH = pmax(0, T2M)
  )

readr::write_csv(
  hourly %>%
    count(season, uid, icefall_name, elevation_band, icefall_elev_m, api_lat, api_lon, name = "n_hours"),
  file.path(out_dir, "inca_reference_hourly_coverage.csv")
)

point_daily <- hourly %>%
  group_by(season, season_start_year, uid, icefall_name, elevation_band, icefall_elev_m, date = date_utc) %>%
  summarise(
    n_hours = n(),
    t_mean_c = mean(T2M, na.rm = TRUE),
    t_min_c = min(T2M, na.rm = TRUE),
    t_max_c = max(T2M, na.rm = TRUE),
    rr_mm = sum(RR, na.rm = TRUE),
    gl_mj_m2 = sum(GL * 3600 / 1e6, na.rm = TRUE),
    fdh = sum(FDH, na.rm = TRUE),
    pdh = sum(PDH, na.rm = TRUE),
    .groups = "drop"
  ) %>%
  filter(n_hours >= 18) %>%
  mutate(
    calendar_md = format(date, "%m-%d"),
    plot_date = canonical_date(date)
  )

readr::write_csv(point_daily, file.path(out_dir, "inca_reference_point_daily.csv"))

daily <- point_daily %>%
  group_by(season, season_start_year, date, calendar_md, plot_date) %>%
  summarise(
    n_points = n_distinct(uid),
    t_mean_c = mean(t_mean_c, na.rm = TRUE),
    t_median_c = median(t_mean_c, na.rm = TRUE),
    t_p25_c = quantile(t_mean_c, 0.25, na.rm = TRUE),
    t_p75_c = quantile(t_mean_c, 0.75, na.rm = TRUE),
    freezing_share = mean(t_mean_c < 0, na.rm = TRUE),
    rr_mean_mm = mean(rr_mm, na.rm = TRUE),
    rr_median_mm = median(rr_mm, na.rm = TRUE),
    gl_mean_mj_m2 = mean(gl_mj_m2, na.rm = TRUE),
    fdh_mean = mean(fdh, na.rm = TRUE),
    pdh_mean = mean(pdh, na.rm = TRUE),
    .groups = "drop"
  ) %>%
  filter(calendar_md != "02-29")

readr::write_csv(daily, file.path(out_dir, "inca_reference_daily_area_summary.csv"))

season_metrics <- daily %>%
  arrange(season_start_year, date) %>%
  group_by(season, season_start_year) %>%
  summarise(
    n_days = n(),
    n_points_median = median(n_points, na.rm = TRUE),
    mean_temp_c = mean(t_mean_c, na.rm = TRUE),
    median_daily_temp_c = median(t_median_c, na.rm = TRUE),
    freezing_days = sum(t_median_c < 0, na.rm = TRUE),
    widespread_freezing_days = sum(freezing_share >= 0.5, na.rm = TRUE),
    max_cold_spell_days = longest_run(t_median_c < 0),
    cold_spells_ge_5d = count_runs_min(t_median_c < 0, min_len = 5),
    cold_degree_hours = sum(fdh_mean, na.rm = TRUE),
    positive_degree_hours = sum(pdh_mean, na.rm = TRUE),
    precip_total_mm = sum(rr_mean_mm, na.rm = TRUE),
    precip_days_ge_1mm = sum(rr_mean_mm >= 1, na.rm = TRUE),
    precip_days_ge_5mm = sum(rr_mean_mm >= 5, na.rm = TRUE),
    longest_dry_spell_days = longest_run(rr_mean_mm < 1),
    gl_total_mj_m2 = sum(gl_mean_mj_m2, na.rm = TRUE),
    spring_gl_total_mj_m2 = sum(gl_mean_mj_m2[month(date) %in% 3:4], na.rm = TRUE),
    spring_mean_temp_c = mean(t_mean_c[month(date) %in% 3:4], na.rm = TRUE),
    spring_positive_degree_hours = sum(pdh_mean[month(date) %in% 3:4], na.rm = TRUE),
    .groups = "drop"
  ) %>%
  mutate(period = ifelse(season_start_year == current_start_year, "2025/26", "Reference 2012/13-2024/25"))

readr::write_csv(season_metrics, file.path(out_dir, "inca_reference_season_metrics.csv"))

metric_meta <- tibble::tribble(
  ~metric, ~metric_label, ~unit, ~high_means,
  "mean_temp_c", "Mean air temperature", "deg C", "warm",
  "freezing_days", "Days with median T < 0 deg C", "days", "cold",
  "max_cold_spell_days", "Longest freezing spell", "days", "cold",
  "cold_degree_hours", "Cold degree-hours", "deg C h", "cold",
  "positive_degree_hours", "Positive degree-hours", "deg C h", "warm",
  "precip_total_mm", "Total precipitation", "mm", "wet",
  "precip_days_ge_1mm", "Precipitation days >= 1 mm", "days", "wet",
  "longest_dry_spell_days", "Longest dry spell (< 1 mm d-1)", "days", "dry",
  "spring_gl_total_mj_m2", "Mar-Apr global radiation", "MJ m-2", "radiation"
)

metrics_long <- season_metrics %>%
  select(season, season_start_year, period, all_of(metric_meta$metric)) %>%
  pivot_longer(cols = all_of(metric_meta$metric), names_to = "metric", values_to = "value") %>%
  left_join(metric_meta, by = "metric") %>%
  mutate(
    metric_label = factor(metric_label, levels = metric_meta$metric_label),
    is_current = season_start_year == current_start_year
  )

metric_reference_summary <- metrics_long %>%
  group_by(metric, metric_label, unit, high_means) %>%
  summarise(
    ref_n = sum(!is_current),
    ref_median = median(value[!is_current], na.rm = TRUE),
    ref_p25 = quantile(value[!is_current], 0.25, na.rm = TRUE),
    ref_p75 = quantile(value[!is_current], 0.75, na.rm = TRUE),
    ref_min = min(value[!is_current], na.rm = TRUE),
    ref_max = max(value[!is_current], na.rm = TRUE),
    current = value[is_current][1],
    anomaly_vs_ref_median = current - ref_median,
    rank_low_to_high = rank(value, ties.method = "min")[is_current][1],
    rank_high_to_low = rank(-value, ties.method = "min")[is_current][1],
    all_n = n(),
    .groups = "drop"
  ) %>%
  mutate(
    percentile_low_to_high = (rank_low_to_high - 0.5) / all_n,
    current_vs_ref_range = case_when(
      current < ref_min ~ "below reference range",
      current > ref_max ~ "above reference range",
      current < ref_p25 ~ "below reference IQR",
      current > ref_p75 ~ "above reference IQR",
      TRUE ~ "inside reference IQR"
    )
  )

readr::write_csv(metric_reference_summary, file.path(out_dir, "inca_reference_metric_comparison.csv"))

daily_reference <- daily %>%
  filter(season_start_year %in% reference_years) %>%
  group_by(calendar_md, plot_date) %>%
  summarise(
    ref_t_p10 = quantile(t_mean_c, 0.10, na.rm = TRUE),
    ref_t_p25 = quantile(t_mean_c, 0.25, na.rm = TRUE),
    ref_t_median = median(t_mean_c, na.rm = TRUE),
    ref_t_p75 = quantile(t_mean_c, 0.75, na.rm = TRUE),
    ref_t_p90 = quantile(t_mean_c, 0.90, na.rm = TRUE),
    ref_rr_p50 = median(rr_mean_mm, na.rm = TRUE),
    ref_rr_p75 = quantile(rr_mean_mm, 0.75, na.rm = TRUE),
    ref_rr_p90 = quantile(rr_mean_mm, 0.90, na.rm = TRUE),
    ref_freezing_share_median = median(freezing_share, na.rm = TRUE),
    .groups = "drop"
  )

daily_current <- daily %>%
  filter(season_start_year == current_start_year) %>%
  select(calendar_md, plot_date, current_t_mean_c = t_mean_c, current_t_median_c = t_median_c,
    current_rr_mean_mm = rr_mean_mm, current_freezing_share = freezing_share,
    current_gl_mean_mj_m2 = gl_mean_mj_m2)

daily_comparison <- daily_reference %>%
  left_join(daily_current, by = c("calendar_md", "plot_date")) %>%
  arrange(plot_date)

readr::write_csv(daily_comparison, file.path(out_dir, "inca_reference_daily_comparison.csv"))

month_breaks <- as.Date(c(
  "2025-10-01", "2025-11-01", "2025-12-01",
  "2026-01-01", "2026-02-01", "2026-03-01", "2026-04-01", "2026-05-01"
))

p_temp <- ggplot(daily_comparison, aes(x = plot_date)) +
  geom_ribbon(aes(ymin = ref_t_p10, ymax = ref_t_p90, fill = "Reference 10-90%"), alpha = 0.35) +
  geom_ribbon(aes(ymin = ref_t_p25, ymax = ref_t_p75, fill = "Reference IQR"), alpha = 0.45) +
  geom_line(aes(y = ref_t_median, color = "Reference median"), linewidth = 0.45) +
  geom_line(aes(y = current_t_mean_c, color = "2025/26"), linewidth = 0.65) +
  geom_hline(yintercept = 0, linewidth = 0.35, color = "#333333") +
  scale_fill_manual(values = c("Reference 10-90%" = "#b9c7d9", "Reference IQR" = "#7f9abb")) +
  scale_color_manual(values = c("Reference median" = "#4a5f75", "2025/26" = "#b13d2e")) +
  scale_x_date(breaks = month_breaks, labels = date_format("%b"), expand = expansion(mult = c(0.01, 0.01))) +
  labs(
    title = "INCA temperature reference for the model period",
    subtitle = "Stratified sample of icefall grid cells; reference winters 2012/13-2024/25",
    x = NULL,
    y = "Mean air temperature (deg C)",
    fill = NULL,
    color = NULL,
    caption = paste0("Source: GeoSphere Austria INCA, ", dataset_url)
  ) +
  theme_thesis(10)

save_plot(p_temp, "fig_3_1_inca_reference_daily_temperature", 7.2, 3.9)

p_precip <- ggplot(daily_comparison, aes(x = plot_date)) +
  geom_col(aes(y = current_rr_mean_mm, fill = "2025/26"), width = 1, alpha = 0.80) +
  geom_line(aes(y = ref_rr_p75, color = "Reference 75%"), linewidth = 0.45) +
  geom_line(aes(y = ref_rr_p90, color = "Reference 90%"), linewidth = 0.45) +
  scale_fill_manual(values = c("2025/26" = "#6c8a65")) +
  scale_color_manual(values = c("Reference 75%" = "#6b7280", "Reference 90%" = "#222222")) +
  scale_x_date(breaks = month_breaks, labels = date_format("%b"), expand = expansion(mult = c(0.01, 0.01))) +
  labs(
    title = "INCA precipitation reference for the model period",
    subtitle = "Daily mean precipitation across the stratified icefall sample",
    x = NULL,
    y = "Daily precipitation (mm d-1)",
    fill = NULL,
    color = NULL,
    caption = paste0("Source: GeoSphere Austria INCA, ", dataset_url)
  ) +
  theme_thesis(10)

save_plot(p_precip, "fig_3_1_inca_reference_daily_precipitation", 7.2, 3.7)

plot_metrics <- metrics_long %>%
  filter(metric %in% c(
    "mean_temp_c",
    "freezing_days",
    "max_cold_spell_days",
    "cold_degree_hours",
    "positive_degree_hours",
    "precip_total_mm",
    "precip_days_ge_1mm",
    "longest_dry_spell_days",
    "spring_gl_total_mj_m2"
  ))

p_metrics <- ggplot() +
  geom_boxplot(
    data = plot_metrics %>% filter(!is_current),
    aes(x = "Reference", y = value),
    width = 0.42,
    fill = "#d9e2ec",
    color = "#52616b",
    outlier.shape = 16,
    outlier.size = 1.3
  ) +
  geom_point(
    data = plot_metrics %>% filter(is_current),
    aes(x = "Reference", y = value),
    shape = 21,
    size = 2.6,
    stroke = 0.45,
    fill = "#b13d2e",
    color = "white"
  ) +
  facet_wrap(~ metric_label, scales = "free_y", ncol = 3) +
  labs(
    title = "How unusual was winter 2025/26 in the INCA reference?",
    subtitle = "Red points show 2025/26; boxplots show reference winters 2012/13-2024/25",
    x = NULL,
    y = NULL,
    caption = paste0("Source: GeoSphere Austria INCA, ", dataset_url)
  ) +
  theme_thesis(9) +
  theme(axis.text.x = element_blank(), axis.ticks.x = element_blank())

save_plot(p_metrics, "fig_3_1_inca_reference_winter_metrics", 7.4, 6.0)

p_scatter <- season_metrics %>%
  ggplot(aes(x = precip_total_mm, y = max_cold_spell_days)) +
  geom_point(aes(size = freezing_days, fill = period), shape = 21, color = "white", stroke = 0.45, alpha = 0.9) +
  geom_text(
    data = season_metrics %>% filter(season_start_year == current_start_year),
    aes(label = season),
    nudge_y = 1.4,
    size = 3,
    color = "#222222"
  ) +
  scale_fill_manual(values = c("Reference 2012/13-2024/25" = "#7f9abb", "2025/26" = "#b13d2e")) +
  scale_size_continuous(range = c(2.5, 7.0)) +
  labs(
    title = "Cold-spell duration versus seasonal precipitation",
    subtitle = "The key winter character is the combination of persistence of freezing and moisture supply",
    x = "Seasonal precipitation (mm)",
    y = "Longest freezing spell (days)",
    fill = NULL,
    size = "Freezing days",
    caption = paste0("Source: GeoSphere Austria INCA, ", dataset_url)
  ) +
  theme_thesis(10)

save_plot(p_scatter, "fig_3_1_inca_reference_cold_precip_scatter", 6.5, 4.3)

fmt <- function(x, digits = 1) format(round(as.numeric(x), digits), nsmall = digits, trim = TRUE)
get_metric <- function(name) {
  metric_reference_summary %>% filter(metric == name) %>% slice(1)
}

m_temp <- get_metric("mean_temp_c")
m_freeze <- get_metric("freezing_days")
m_coldspell <- get_metric("max_cold_spell_days")
m_fdh <- get_metric("cold_degree_hours")
m_pdh <- get_metric("positive_degree_hours")
m_precip <- get_metric("precip_total_mm")
m_dry <- get_metric("longest_dry_spell_days")
m_wet <- get_metric("precip_days_ge_1mm")
m_spring_gl <- get_metric("spring_gl_total_mj_m2")

paragraph <- paste0(
  "For a climatological classification of the model season, the INCA hourly analysis was extracted at a ",
  "stratified sample of icefall grid cells and compared with the same October-April period in the reference ",
  "winters 2012/13-2024/25. In this comparison, 2025/26 was not exceptional because it was the coldest ",
  "season overall: the seasonal mean temperature (", fmt(m_temp$current, 1), " deg C) and cold degree-hours ",
  "(", fmt(m_fdh$current, 0), " deg C h) remained within the reference interquartile range and were slightly ",
  "less cold than the reference median (", fmt(m_temp$ref_median, 1), " deg C and ",
  fmt(m_fdh$ref_median, 0), " deg C h). Its distinctive thermal signal was instead the persistence of freezing ",
  "conditions. The sample contained ", fmt(m_freeze$current, 0),
  " days with a median daily temperature below 0 deg C, close to the reference median of ",
  fmt(m_freeze$ref_median, 0), " days, but the longest continuous freezing spell reached ",
  fmt(m_coldspell$current, 0), " days compared with a reference median of ",
  fmt(m_coldspell$ref_median, 0), " days; this was the third-longest spell among the 14 analysed seasons. ",
  "The strongest anomaly was precipitation: 2025/26 accumulated only ", fmt(m_precip$current, 0),
  " mm, below all reference winters and about ", fmt(abs(m_precip$anomaly_vs_ref_median), 0),
  " mm below the reference median of ", fmt(m_precip$ref_median, 0), " mm. The number of wet days ",
  "also remained low (", fmt(m_wet$current, 0), " days >= 1 mm, reference median ",
  fmt(m_wet$ref_median, 0), " days). The season was therefore characterised by a rare combination of ",
  "long thermal persistence and limited moisture supply: freezing conditions were favourable for ice preservation, ",
  "whereas reduced precipitation may have constrained new ice growth at sites dependent on frequent recharge. ",
  "From March onward, above-median global radiation (March-April total ", fmt(m_spring_gl$current, 0),
  " MJ m-2; reference median ", fmt(m_spring_gl$ref_median, 0),
  " MJ m-2) strengthened the transition toward melt potential despite intermittent late-season freezing."
)

notes <- c(
  "# INCA winter reference for Section 3.1",
  "",
  paragraph,
  "",
  "The anomalous character of the season is best shown by the combined seasonal metrics (Fig. 3.X). The figure makes clear that 2025/26 was not simply an outlier in mean temperature or in the total number of freezing days. Instead, its position is unusual because the longest freezing spell was well above the reference interquartile range, while seasonal precipitation was lower than in all reference winters. This supports interpreting the model period as a winter with persistent thermal suitability but limited moisture supply.",
  "",
  "![Seasonal INCA winter metrics with 2025/26 highlighted](fig_3_1_inca_reference_winter_metrics.png)",
  "",
  "**Figure 3.X.** Seasonal INCA metrics for the stratified icefall sample. Boxplots show the reference winters 2012/13-2024/25, and red points show the model winter 2025/26. The comparison indicates that 2025/26 was not exceptional mainly through average temperature, but through the combination of an unusually long continuous freezing spell and the lowest seasonal precipitation total in the analysed reference period.",
  "",
  "This combined anomaly is even clearer when cold-spell duration is plotted directly against seasonal precipitation (Fig. 3.X). In this bivariate view, 2025/26 lies at the dry and cold-persistent edge of the reference cloud. This position is relevant for the interpretation of the icefall model because a long freezing spell favours ice preservation, whereas low precipitation and fewer wet days can restrict water supply for new ice growth.",
  "",
  "![Cold-spell duration versus seasonal INCA precipitation](fig_3_1_inca_reference_cold_precip_scatter.png)",
  "",
  "**Figure 3.X.** Relationship between seasonal precipitation and the longest continuous freezing spell in the INCA reference comparison. Each point represents one October-April season at the stratified icefall sample; point size indicates the total number of freezing days. Winter 2025/26 occupies an unusual position with very low precipitation and a long continuous freezing period, highlighting the specific character of the model season.",
  "",
  "Important methodological note: this comparison uses INCA at the route/grid-cell locations only as a regional meteorological reference. The model-period route temperature used in the actual icefall model remains the station-derived TLz temperature with elevation and cold-air-pooling correction.",
  "",
  paste0("Source: GeoSphere Austria INCA hourly analysis, ", dataset_url)
)

writeLines(notes, file.path(out_dir, "section_3_1_inca_reference_paragraph.md"), useBytes = TRUE)

message("Done. Outputs written to: ", out_dir)

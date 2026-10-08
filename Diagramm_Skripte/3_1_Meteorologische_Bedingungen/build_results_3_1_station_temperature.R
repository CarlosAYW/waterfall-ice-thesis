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
  library(ncdf4)
  library(httr2)
  library(jsonlite)
  library(readr)
  library(dplyr)
  library(tidyr)
  library(ggplot2)
  library(lubridate)
  library(stringr)
  library(zoo)
})

root <- normalizePath(file.path("Ice fall modeling", "GitHub", "ice-waterfalls"), winslash = "/", mustWork = TRUE)
out_dir <- normalizePath(file.path("output", "results_3_1_meteorological_conditions"), winslash = "/", mustWork = TRUE)
cache_dir <- file.path(out_dir, "station_tlrf_cache")
dir.create(cache_dir, showWarnings = FALSE, recursive = TRUE)

assign_path <- file.path(root, "data", "AWS", "icefalls_nearest_station.csv")
stations_path <- file.path(root, "data", "AWS", "stations_all.csv")
cap_path <- file.path(root, "data", "CAP", "icefall_station_cap.csv")
inca_dir <- file.path(root, "data", "inca_nordtirol")
sun_dir <- file.path(root, "data", "suntime")
inv_dir <- file.path(root, "data", "_cache_inversion")

tz_local <- "Europe/Vienna"
analysis_start <- as.Date("2025-10-01")
analysis_end <- as.Date("2026-04-30")
step_minutes <- 10

coef <- list(
  lapse_K_per_m = 0.0065,
  wind_cap_ms = 15,
  cap_max_adjust_C = 3.0,
  cap_wind_shutdown_ms = 4.0,
  cap_radiation_shutdown_Wm2 = 180,
  cap_no_inversion_factor = 0.35
)

to_num <- function(x) {
  if (is.numeric(x)) return(as.numeric(x))
  x <- as.character(x)
  x[x %in% c("", "NA", "NaN", "NULL", "---")] <- NA_character_
  x <- gsub(",", ".", x, fixed = TRUE)
  suppressWarnings(as.numeric(x))
}

clamp01 <- function(x) pmin(1, pmax(0, x))

fill1 <- function(x) {
  x <- zoo::na.locf(x, na.rm = FALSE)
  x <- zoo::na.locf(x, na.rm = FALSE, fromLast = TRUE)
  x
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

season_label <- function(date) {
  y <- year(date)
  m <- month(date)
  ifelse(m >= 10, sprintf("%d_%d", y, y + 1), sprintf("%d_%d", y - 1, y))
}

parse_dt_any <- function(x, tz = tz_local) {
  x <- as.character(x)
  x[x %in% c("", "NA", "NaN", "NULL", "---")] <- NA_character_
  out <- suppressWarnings(lubridate::dmy_hms(x, tz = tz))
  if (all(is.na(out))) out <- suppressWarnings(lubridate::dmy_hm(x, tz = tz))
  if (all(is.na(out))) out <- suppressWarnings(lubridate::ymd_hms(x, tz = tz))
  if (all(is.na(out))) out <- suppressWarnings(lubridate::ymd_hm(x, tz = tz))
  out
}

complete_station_grid <- function(df) {
  start_time <- as.POSIXct(analysis_start, tz = tz_local)
  end_time <- as.POSIXct(analysis_end + 1, tz = tz_local) - minutes(step_minutes)
  df %>%
    mutate(timestamp = floor_date(with_tz(as.POSIXct(timestamp, tz = tz_local), tz_local), unit = paste0(step_minutes, " mins"))) %>%
    group_by(timestamp) %>%
    summarise(TL = mean(TL, na.rm = TRUE), RF = mean(RF, na.rm = TRUE), .groups = "drop") %>%
    complete(timestamp = seq(start_time, end_time, by = paste0(step_minutes, " mins"))) %>%
    arrange(timestamp) %>%
    mutate(
      TL = fill1(TL),
      RF = fill1(RF)
    ) %>%
    filter(timestamp >= start_time, timestamp <= end_time)
}

get_geosphere_station_tlrf <- function(station_id) {
  base_url <- "https://dataset.api.hub.geosphere.at/v1/station/historical/klima-v2-10min"
  start_q <- sprintf("%sT00:00", as.character(analysis_start))
  end_q <- sprintf("%sT23:50", as.character(analysis_end))
  param_tries <- c("tl,rf", "TL,RF")
  last_msg <- NULL

  for (p in param_tries) {
    resp <- request(base_url) |>
      req_url_query(
        station_ids = as.character(station_id),
        parameters = p,
        start = start_q,
        end = end_q
      ) |>
      req_user_agent("icefall-model/1.0 (R httr2)") |>
      req_retry(max_tries = 3) |>
      req_error(is_error = function(r) FALSE) |>
      req_perform()

    if (resp_status(resp) < 400) {
      dat <- jsonlite::fromJSON(resp_body_string(resp), simplifyVector = FALSE)
      ts_raw <- dat[["timestamps"]]
      time_utc <- suppressWarnings(lubridate::ymd_hms(ts_raw, tz = "UTC"))
      if (all(is.na(time_utc))) {
        ts_fix <- ts_raw
        has_colon_tz <- grepl("([+-][0-9]{2}):([0-9]{2})$", ts_fix)
        ts_fix[has_colon_tz] <- paste0(
          substr(ts_fix[has_colon_tz], 1, nchar(ts_fix[has_colon_tz]) - 3),
          substr(ts_fix[has_colon_tz], nchar(ts_fix[has_colon_tz]) - 1, nchar(ts_fix[has_colon_tz]))
        )
        time_utc <- as.POSIXct(strptime(ts_fix, "%Y-%m-%dT%H:%M%z", tz = "UTC"))
      }
      feat <- dat[["features"]][[1]]
      params <- feat[["properties"]][["parameters"]]

      pull_anycase <- function(name) {
        cand <- c(name, tolower(name), toupper(name))
        for (nm in cand) {
          p0 <- params[[nm]]
          if (!is.null(p0) && !is.null(p0[["data"]])) {
            lst <- p0[["data"]]
            out <- rep(NA_real_, length(time_utc))
            m <- min(length(lst), length(time_utc))
            out[seq_len(m)] <- vapply(lst[seq_len(m)], function(x) {
              if (is.null(x)) NA_real_ else as.numeric(x)
            }, numeric(1))
            return(out)
          }
        }
        rep(NA_real_, length(time_utc))
      }

      return(tibble(
        timestamp = with_tz(time_utc, tz_local),
        TL = pull_anycase("tl"),
        RF = pull_anycase("rf")
      ))
    }
    last_msg <- tryCatch(resp_body_string(resp), error = function(e) "")
  }
  stop("GeoSphere station request failed for ", station_id, ": ", last_msg)
}

read_lwd_param <- function(station_code, param, season) {
  url <- sprintf(
    "https://wiski.tirol.gv.at/lawine/produkte/ogd/%s/%s_%s_%s.csv",
    station_code, station_code, param, season
  )
  resp <- tryCatch(
    request(url) |>
      req_user_agent("icefall-model/1.0 (R httr2)") |>
      req_retry(max_tries = 3) |>
      req_perform(),
    error = function(e) NULL
  )
  if (is.null(resp) || resp_status(resp) != 200) return(NULL)
  raw <- tryCatch(resp_body_raw(resp), error = function(e) NULL)
  if (is.null(raw) || length(raw) == 0) return(NULL)

  txt <- iconv(rawToChar(raw), from = "", to = "UTF-8", sub = "byte")
  lines <- strsplit(txt, "\n", fixed = TRUE)[[1]]
  header_i <- grep("^Datum/Uhrzeit", lines)
  if (length(header_i) == 0) return(NULL)
  table_txt <- paste(lines[header_i[1]:length(lines)], collapse = "\n")
  tab <- tryCatch(
    readr::read_delim(
      I(table_txt),
      delim = ";",
      locale = locale(decimal_mark = ","),
      show_col_types = FALSE,
      progress = FALSE,
      trim_ws = TRUE
    ),
    error = function(e) NULL
  )
  if (is.null(tab) || nrow(tab) == 0 || ncol(tab) < 2) return(NULL)
  tibble(
    timestamp = parse_dt_any(tab[[1]], tz = tz_local),
    value = to_num(tab[[2]])
  ) %>%
    filter(!is.na(timestamp))
}

get_lwd_station_tlrf <- function(station_code) {
  seasons <- unique(season_label(seq(analysis_start, analysis_end, by = "day")))
  tl <- bind_rows(lapply(seasons, function(seas) read_lwd_param(station_code, "LT", seas))) %>%
    mutate(param = "TL")
  rf <- bind_rows(lapply(seasons, function(seas) read_lwd_param(station_code, "LF", seas))) %>%
    mutate(param = "RF")
  long <- bind_rows(tl, rf)
  if (nrow(long) == 0) stop("No LWD data for station ", station_code)
  wide <- long %>%
    select(timestamp, param, value) %>%
    pivot_wider(names_from = param, values_from = value) %>%
    arrange(timestamp)
  for (cc in c("TL", "RF")) if (!cc %in% names(wide)) wide[[cc]] <- NA_real_
  wide
}

get_station_tlrf_cached <- function(station_id, source) {
  cache_file <- file.path(
    cache_dir,
    sprintf("%s_%s_%s_%s_localtime.csv", source, station_id, format(analysis_start, "%Y%m%d"), format(analysis_end, "%Y%m%d"))
  )
  if (file.exists(cache_file)) {
    return(read_csv(cache_file, show_col_types = FALSE, progress = FALSE) %>%
      mutate(timestamp = ymd_hms(timestamp, tz = tz_local)))
  }
  message("Fetching station ", station_id, " (", source, ")")
  raw <- if (identical(source, "GeoSphere")) {
    get_geosphere_station_tlrf(station_id)
  } else if (identical(source, "LWD")) {
    get_lwd_station_tlrf(station_id)
  } else {
    stop("Unknown source: ", source)
  }
  wx <- complete_station_grid(raw) %>%
    mutate(station_id = as.character(station_id), source = source, .before = 1)
  if (all(is.na(wx$TL))) stop("TL completely missing for station ", station_id, " (", source, ")")
  write_csv(wx %>% mutate(timestamp = format(timestamp, "%Y-%m-%d %H:%M:%S", tz = tz_local)), cache_file)
  wx
}

nearest_grid_index <- function(route_lat, route_lon, grid_lat, grid_lon) {
  flat_lat <- as.vector(grid_lat)
  flat_lon <- as.vector(grid_lon)
  n_x <- dim(grid_lat)[1]
  idx <- integer(length(route_lat))
  for (i in seq_along(route_lat)) {
    d2 <- (flat_lat - route_lat[i])^2 + ((flat_lon - route_lon[i]) * cos(route_lat[i] * pi / 180))^2
    idx[i] <- which.min(d2)
  }
  data.frame(
    x_idx = ((idx - 1) %% n_x) + 1,
    y_idx = floor((idx - 1) / n_x) + 1
  )
}

extract_route_inca_hourly <- function(path, routes) {
  nc <- nc_open(path)
  on.exit(nc_close(nc), add = TRUE)
  time_units <- nc$dim$time$units
  origin <- as.POSIXct(sub("^seconds since ", "", time_units), tz = "UTC")
  time_utc <- origin + ncvar_get(nc, "time")
  time_local <- with_tz(time_utc, tz_local)

  vars <- c("UU", "VV", "GL")
  arrs <- lapply(vars, function(v) ncvar_get(nc, v))
  names(arrs) <- vars
  n_routes <- nrow(routes)
  n_time <- length(time_utc)

  route_vals <- lapply(vars, function(v) {
    out <- matrix(NA_real_, nrow = n_routes, ncol = n_time)
    a <- arrs[[v]]
    for (r in seq_len(n_routes)) {
      out[r, ] <- a[routes$x_idx[r], routes$y_idx[r], ]
    }
    out
  })
  names(route_vals) <- vars

  tibble(
    uid = rep(routes$uid, each = n_time),
    time_hour = rep(floor_date(time_local, "hour"), times = n_routes),
    uu_ms = as.vector(t(route_vals$UU)),
    vv_ms = as.vector(t(route_vals$VV)),
    gl_wm2 = pmax(0, as.vector(t(route_vals$GL)))
  )
}

read_route_inca_hourly <- function(routes) {
  files <- list.files(inca_dir, pattern = "\\.nc$", full.names = TRUE)
  files <- files[order(files)]
  if (length(files) == 0) stop("No INCA NetCDF files found.")

  nc0 <- nc_open(files[1])
  grid_lat <- ncvar_get(nc0, "lat")
  grid_lon <- ncvar_get(nc0, "lon")
  nc_close(nc0)

  routes_idx <- bind_cols(routes, nearest_grid_index(routes$ice_lat, routes$ice_lon, grid_lat, grid_lon))
  message("Reading route-nearest INCA wind/radiation for ", nrow(routes), " routes.")
  bind_rows(lapply(seq_along(files), function(i) {
    if (i %% 20 == 0 || i == 1 || i == length(files)) {
      message("  INCA file ", i, " / ", length(files), ": ", basename(files[i]))
    }
    extract_route_inca_hourly(files[i], routes_idx)
  })) %>%
    distinct(uid, time_hour, .keep_all = TRUE) %>%
    filter(as.Date(time_hour) >= analysis_start, as.Date(time_hour) <= analysis_end) %>%
    mutate(
      FF = sqrt(uu_ms^2 + vv_ms^2),
      GLOW = gl_wm2
    ) %>%
    select(uid, time_hour, FF, GLOW)
}

read_sun_windows <- function(routes) {
  bind_rows(lapply(routes$uid, function(uid_i) {
    f <- file.path(sun_dir, sprintf("sun_uid_%03d.csv", as.integer(uid_i)))
    if (!file.exists(f)) return(NULL)
    read_csv(f, show_col_types = FALSE, progress = FALSE) %>%
      select(any_of(c("uid", "date", "sunrise_topo", "sunset_topo", "sun_hours_topo")))
  })) %>%
    mutate(
      uid = as.integer(uid),
      date = as.Date(date),
      sunrise_topo = with_tz(ymd_hms(sunrise_topo, tz = "UTC", quiet = TRUE), tz_local),
      sunset_topo = with_tz(ymd_hms(sunset_topo, tz = "UTC", quiet = TRUE), tz_local),
      sun_hours_topo = to_num(sun_hours_topo)
    ) %>%
    filter(date >= analysis_start, date <= analysis_end)
}

read_inversion <- function() {
  files <- list.files(inv_dir, pattern = "^inversion_.*\\.rds$", full.names = TRUE)
  if (length(files) == 0) {
    warning("No inversion cache found; using inv_active = FALSE.")
    return(tibble(
      time = seq(as.POSIXct(analysis_start, tz = tz_local), as.POSIXct(analysis_end + 1, tz = tz_local) - minutes(step_minutes), by = "10 min"),
      inv_active = FALSE,
      grad01_K_per_m = NA_real_,
      grad12_K_per_m = NA_real_
    ))
  }
  f <- files[which.max(file.info(files)$mtime)]
  message("Using inversion cache: ", basename(f))
  readRDS(f) %>%
    mutate(time = with_tz(as.POSIXct(time, tz = tz_local), tz_local)) %>%
    select(any_of(c("time", "inv_active", "grad01_K_per_m", "grad12_K_per_m"))) %>%
    filter(as.Date(time) >= analysis_start, as.Date(time) <= analysis_end)
}

routes <- read_csv(assign_path, show_col_types = FALSE, progress = FALSE) %>%
  filter(!is.na(uid), !is.na(ice_lat), !is.na(ice_lon), !is.na(icefall_elev_m), !is.na(station_id)) %>%
  mutate(
    uid = as.integer(uid),
    station_id = as.character(station_id),
    source = as.character(source),
    elevation_band = cut(
      icefall_elev_m,
      breaks = c(-Inf, 1500, 2000, 2500, Inf),
      labels = c("<1500 m", "1500-2000 m", "2000-2500 m", ">2500 m"),
      right = FALSE
    )
  ) %>%
  arrange(uid)

stations <- read_csv(stations_path, show_col_types = FALSE, progress = FALSE) %>%
  mutate(station_id = as.character(station_id)) %>%
  select(any_of(c("station_id", "altitude_m")))

cap <- read_csv(cap_path, show_col_types = FALSE, progress = FALSE) %>%
  mutate(uid = as.integer(uid)) %>%
  select(any_of(c("uid", "cap_delta", "cap_pair_confidence")))

routes <- routes %>%
  left_join(stations, by = "station_id") %>%
  left_join(cap, by = "uid") %>%
  mutate(
    dz_m = to_num(elev_diff_m),
    z_aws = to_num(altitude_m),
    cap_delta = pmax(-1, pmin(1, coalesce(to_num(cap_delta), 0))),
    cap_pair_confidence = clamp01(coalesce(to_num(cap_pair_confidence), 0))
  )

station_keys <- routes %>%
  distinct(source, station_id) %>%
  arrange(source, station_id)

station_weather <- bind_rows(lapply(seq_len(nrow(station_keys)), function(i) {
  get_station_tlrf_cached(station_keys$station_id[i], station_keys$source[i])
}))

inca_hourly <- read_route_inca_hourly(routes)
sun_windows <- read_sun_windows(routes)
inv <- read_inversion()

message("Computing station-derived icefall temperatures.")
daily_chunks <- list()
k <- 0

for (i in seq_len(nrow(station_keys))) {
  sid <- station_keys$station_id[i]
  src <- station_keys$source[i]
  rts <- routes %>% filter(station_id == sid, source == src)
  wx <- station_weather %>% filter(station_id == sid, source == src)
  if (nrow(rts) == 0 || nrow(wx) == 0) next

  chunk <- merge(rts, wx, by = NULL) %>%
    mutate(
      time = timestamp,
      date = as.Date(time),
      time_hour = floor_date(time, "hour")
    ) %>%
    left_join(inca_hourly, by = c("uid", "time_hour")) %>%
    left_join(sun_windows %>% select(uid, date, sunrise_topo, sunset_topo, sun_hours_topo), by = c("uid", "date")) %>%
    left_join(inv, by = "time") %>%
    mutate(
      inv_active = if_else(is.na(inv_active), FALSE, inv_active),
      FF = coalesce(FF, 0),
      GLOW = coalesce(GLOW, 0),
      topo_sun_fac = if_else(!is.na(sunrise_topo) & !is.na(sunset_topo) & time >= sunrise_topo & time < sunset_topo, 1, 0),
      use_prof = inv_active & is.finite(z_aws) & is.finite(dz_m) &
        is.finite(grad01_K_per_m) & is.finite(grad12_K_per_m),
      z_target_m = z_aws + dz_m,
      z1_m = 1935,
      lo = pmin(z_aws, z_target_m),
      hi = pmax(z_aws, z_target_m),
      len_low = pmax(0, pmin(hi, z1_m) - lo),
      len_high = pmax(0, hi - pmax(lo, z1_m)),
      sgn = if_else(z_target_m >= z_aws, 1, -1),
      dT_prof = if_else(use_prof, sgn * (grad01_K_per_m * len_low + grad12_K_per_m * len_high), NA_real_),
      TLz_raw = TL - coef$lapse_K_per_m * dz_m,
      TLz_base = if_else(use_prof, TL + dT_prof, TLz_raw),
      FF_eff = pmin(coef$wind_cap_ms, pmax(0, FF)),
      cap_wind_fac = clamp01(1 - FF_eff / coef$cap_wind_shutdown_ms),
      cap_sun_fac = if_else(topo_sun_fac > 0, clamp01(1 - GLOW / coef$cap_radiation_shutdown_Wm2), 1),
      cap_inv_fac = if_else(inv_active, 1, coef$cap_no_inversion_factor),
      cap_stability_fac = cap_wind_fac * cap_sun_fac * cap_inv_fac,
      cap_temp_adjust_C = coef$cap_max_adjust_C * cap_delta * cap_pair_confidence * cap_stability_fac,
      TLz = TLz_base - cap_temp_adjust_C
    )

  k <- k + 1
  daily_chunks[[k]] <- chunk %>%
    group_by(uid, elev_m = icefall_elev_m, elevation_band, source.x, station_id.x, date) %>%
    summarise(
      n_steps = sum(is.finite(TLz)),
      temp_mean_c = mean(TLz, na.rm = TRUE),
      temp_min_c = min(TLz, na.rm = TRUE),
      temp_max_c = max(TLz, na.rm = TRUE),
      rh_mean_pct = mean(RF, na.rm = TRUE),
      wind_mean_ms = mean(FF, na.rm = TRUE),
      wind_max_ms = max(FF, na.rm = TRUE),
      rad_mj_m2 = sum(pmax(0, GLOW) * 600 / 1e6, na.rm = TRUE),
      fdh = sum(pmax(0, -TLz) * step_minutes / 60, na.rm = TRUE),
      pdh = sum(pmax(0, TLz) * step_minutes / 60, na.rm = TRUE),
      .groups = "drop"
    ) %>%
    rename(source = source.x, station_id = station_id.x) %>%
    mutate(across(where(is.numeric), ~ ifelse(is.infinite(.x), NA_real_, .x))) %>%
    filter(n_steps >= 120)
}

daily_route <- bind_rows(daily_chunks)

daily_dist <- daily_route %>%
  group_by(date) %>%
  summarise(
    temp_p10 = quantile(temp_mean_c, 0.10, na.rm = TRUE),
    temp_p25 = quantile(temp_mean_c, 0.25, na.rm = TRUE),
    temp_median = median(temp_mean_c, na.rm = TRUE),
    temp_p75 = quantile(temp_mean_c, 0.75, na.rm = TRUE),
    temp_p90 = quantile(temp_mean_c, 0.90, na.rm = TRUE),
    share_mean_below0 = mean(temp_mean_c < 0, na.rm = TRUE),
    share_min_below0 = mean(temp_min_c < 0, na.rm = TRUE),
    rh_p25 = quantile(rh_mean_pct, 0.25, na.rm = TRUE),
    rh_median = median(rh_mean_pct, na.rm = TRUE),
    rh_p75 = quantile(rh_mean_pct, 0.75, na.rm = TRUE),
    wind_p25 = quantile(wind_mean_ms, 0.25, na.rm = TRUE),
    wind_median = median(wind_mean_ms, na.rm = TRUE),
    wind_p75 = quantile(wind_mean_ms, 0.75, na.rm = TRUE),
    rad_p25 = quantile(rad_mj_m2, 0.25, na.rm = TRUE),
    rad_median = median(rad_mj_m2, na.rm = TRUE),
    rad_p75 = quantile(rad_mj_m2, 0.75, na.rm = TRUE),
    .groups = "drop"
  )

sun_daily <- sun_windows %>%
  select(uid, date, sun_hours_topo) %>%
  inner_join(routes %>% select(uid, elev_m = icefall_elev_m, elevation_band, source), by = "uid")

sun_dist <- sun_daily %>%
  group_by(date) %>%
  summarise(
    sun_p10 = quantile(sun_hours_topo, 0.10, na.rm = TRUE),
    sun_p25 = quantile(sun_hours_topo, 0.25, na.rm = TRUE),
    sun_median = median(sun_hours_topo, na.rm = TRUE),
    sun_p75 = quantile(sun_hours_topo, 0.75, na.rm = TRUE),
    sun_p90 = quantile(sun_hours_topo, 0.90, na.rm = TRUE),
    .groups = "drop"
  )

write_csv(daily_route, file.path(out_dir, "station_temperature_daily_route_summary.csv"))
write_csv(daily_dist, file.path(out_dir, "station_temperature_daily_distribution_summary.csv"))
write_csv(sun_dist, file.path(out_dir, "topographic_sun_daily_distribution_summary.csv"))

period_start <- min(daily_route$date, na.rm = TRUE)
period_end <- max(daily_route$date, na.rm = TRUE)

fig1 <- ggplot(daily_dist, aes(date)) +
  geom_hline(yintercept = 0, color = "#222222", linewidth = 0.35) +
  geom_ribbon(aes(ymin = temp_p10, ymax = temp_p90), fill = "#9ecae1", alpha = 0.32) +
  geom_ribbon(aes(ymin = temp_p25, ymax = temp_p75), fill = "#3182bd", alpha = 0.38) +
  geom_line(aes(y = temp_median), color = "#08519c", linewidth = 0.8) +
  scale_x_date(date_breaks = "1 month", date_labels = "%b") +
  labs(
    title = "Station-derived icefall temperature conditions",
    subtitle = paste0("Temperature transferred from assigned weather stations to ", n_distinct(daily_route$uid), " icefalls, ", period_start, " to ", period_end),
    x = NULL,
    y = "Daily mean TLz (deg C)",
    caption = "Line: route median. Dark band: interquartile range. Light band: 10th-90th percentile. TLz includes elevation, inversion and CAP corrections."
  ) +
  theme_thesis()
save_plot(fig1, "fig_3_1_station_temperature_distribution", 7.2, 4.2)

share_long <- daily_dist %>%
  select(date, share_mean_below0, share_min_below0) %>%
  pivot_longer(-date, names_to = "metric", values_to = "share") %>%
  mutate(metric = recode(
    metric,
    share_mean_below0 = "Daily mean TLz below 0 deg C",
    share_min_below0 = "Daily minimum TLz below 0 deg C"
  ))

fig2 <- ggplot(share_long, aes(date, share, color = metric)) +
  geom_line(linewidth = 0.8) +
  scale_y_continuous(labels = function(x) paste0(round(x * 100), "%"), limits = c(0, 1)) +
  scale_x_date(date_breaks = "1 month", date_labels = "%b") +
  scale_color_manual(values = c("Daily mean TLz below 0 deg C" = "#22577a", "Daily minimum TLz below 0 deg C" = "#b56576")) +
  labs(
    title = "Share of icefalls exposed to station-derived freezing conditions",
    subtitle = "Daily proportion of station-assigned routes with below-freezing calculated icefall temperature",
    x = NULL,
    y = "Share of routes",
    color = NULL,
    caption = "Icefall temperature is TLz from the model transfer of station TL to route elevation."
  ) +
  theme_thesis()
save_plot(fig2, "fig_3_1_station_freezing_share", 7.2, 4.0)

degree_band <- daily_route %>%
  group_by(date, elevation_band) %>%
  summarise(
    fdh_median = median(fdh, na.rm = TRUE),
    pdh_median = median(pdh, na.rm = TRUE),
    .groups = "drop"
  ) %>%
  group_by(elevation_band) %>%
  arrange(date, .by_group = TRUE) %>%
  mutate(
    cum_fdh = cumsum(fdh_median),
    cum_pdh = cumsum(pdh_median)
  ) %>%
  ungroup() %>%
  pivot_longer(c(cum_fdh, cum_pdh), names_to = "metric", values_to = "degree_hours") %>%
  mutate(metric = recode(metric, cum_fdh = "Freezing degree-hours", cum_pdh = "Positive degree-hours"))

fig3 <- ggplot(degree_band, aes(date, degree_hours, color = elevation_band)) +
  geom_line(linewidth = 0.8) +
  facet_wrap(~ metric, ncol = 1, scales = "free_y") +
  scale_x_date(date_breaks = "1 month", date_labels = "%b") +
  scale_color_manual(values = c("<1500 m" = "#7b3294", "1500-2000 m" = "#008837", "2000-2500 m" = "#2c7fb8", ">2500 m" = "#d95f0e")) +
  labs(
    title = "Cumulative station-derived thermal conditions by elevation band",
    subtitle = "Median route daily freezing and positive degree-hours accumulated from calculated icefall temperature",
    x = NULL,
    y = "Cumulative degree-hours",
    color = "Elevation band",
    caption = "FDH and PDH are derived from TLz, the modelled station-derived temperature at icefall elevation."
  ) +
  theme_thesis()
save_plot(fig3, "fig_3_1_station_degree_hours_by_elevation", 7.2, 5.6)

forcing_long <- daily_dist %>%
  select(date, rh_p25, rh_median, rh_p75, wind_p25, wind_median, wind_p75, rad_p25, rad_median, rad_p75) %>%
  pivot_longer(-date, names_to = "name", values_to = "value") %>%
  mutate(
    variable = case_when(
      str_starts(name, "rh") ~ "Station relative humidity (%)",
      str_starts(name, "wind") ~ "INCA wind speed (m s^-1)",
      str_starts(name, "rad") ~ "INCA global radiation (MJ m^-2 d^-1)",
      TRUE ~ name
    ),
    stat = case_when(
      str_ends(name, "p25") ~ "p25",
      str_ends(name, "median") ~ "median",
      str_ends(name, "p75") ~ "p75",
      TRUE ~ name
    )
  ) %>%
  select(date, variable, stat, value) %>%
  pivot_wider(names_from = stat, values_from = value)

fig4 <- ggplot(forcing_long, aes(date)) +
  geom_ribbon(aes(ymin = p25, ymax = p75), fill = "#74a9cf", alpha = 0.35) +
  geom_line(aes(y = median), color = "#045a8d", linewidth = 0.75) +
  facet_wrap(~ variable, ncol = 1, scales = "free_y") +
  scale_x_date(date_breaks = "1 month", date_labels = "%b") +
  labs(
    title = "Humidity, wind and shortwave-radiation conditions",
    subtitle = paste0("Station humidity and route-nearest INCA wind/radiation, ", period_start, " to ", period_end),
    x = NULL,
    y = NULL,
    caption = "Line: route median. Band: interquartile range."
  ) +
  theme_thesis()
save_plot(fig4, "fig_3_1_station_humidity_wind_radiation", 7.2, 6.6)

fig5 <- ggplot(sun_dist, aes(date)) +
  geom_ribbon(aes(ymin = sun_p10, ymax = sun_p90), fill = "#fdae6b", alpha = 0.28) +
  geom_ribbon(aes(ymin = sun_p25, ymax = sun_p75), fill = "#e6550d", alpha = 0.32) +
  geom_line(aes(y = sun_median), color = "#a63603", linewidth = 0.8) +
  scale_x_date(date_breaks = "1 month", date_labels = "%b") +
  labs(
    title = "Topographically possible direct sun exposure",
    subtitle = "Daily sun-window distribution for station-assigned routes with precomputed horizon tables",
    x = NULL,
    y = "Topographic sun hours per day",
    caption = "Line: route median. Dark band: interquartile range. Light band: 10th-90th percentile."
  ) +
  theme_thesis()
save_plot(fig5, "fig_3_1_station_topographic_sun_hours", 7.2, 4.2)

sun_end <- sun_dist %>% filter(date == max(date, na.rm = TRUE)) %>% slice(1)
summary_stats <- list(
  n_routes = n_distinct(daily_route$uid),
  period_start = as.character(period_start),
  period_end = as.character(period_end),
  n_days = n_distinct(daily_route$date),
  median_temp_over_period = median(daily_route$temp_mean_c, na.rm = TRUE),
  coldest_daily_route_median_date = as.character(daily_dist$date[which.min(daily_dist$temp_median)]),
  coldest_daily_route_median_c = min(daily_dist$temp_median, na.rm = TRUE),
  warmest_daily_route_median_date = as.character(daily_dist$date[which.max(daily_dist$temp_median)]),
  warmest_daily_route_median_c = max(daily_dist$temp_median, na.rm = TRUE),
  days_route_median_below0 = sum(daily_dist$temp_median < 0, na.rm = TRUE),
  days_majority_mean_below0 = sum(daily_dist$share_mean_below0 >= 0.5, na.rm = TRUE),
  median_daily_rh_pct = median(daily_route$rh_mean_pct, na.rm = TRUE),
  median_daily_wind_ms = median(daily_route$wind_mean_ms, na.rm = TRUE),
  median_daily_rad_mj_m2 = median(daily_route$rad_mj_m2, na.rm = TRUE),
  median_daily_sun_hours = median(sun_daily$sun_hours_topo, na.rm = TRUE),
  sun_end_date = as.character(sun_end$date),
  sun_end_median_hours = sun_end$sun_median,
  sun_end_p25_hours = sun_end$sun_p25,
  sun_end_p75_hours = sun_end$sun_p75
)

summary_tbl <- tibble(metric = names(summary_stats), value = vapply(summary_stats, as.character, character(1)))
write_csv(summary_tbl, file.path(out_dir, "station_temperature_summary_stats.csv"))

caption_text <- paste0(
  "# Section 3.1 draft material - station-derived temperature\n\n",
  "## Draft paragraph\n\n",
  "During the analysed model period from ", summary_stats$period_start, " to ", summary_stats$period_end,
  ", the station-assigned icefall sample (n = ", summary_stats$n_routes, ") was exposed to a strongly seasonal thermal regime. ",
  "Here, air temperature is represented by TLz, the model temperature calculated at each icefall from the assigned weather station by applying the station-route elevation difference, the inversion-profile correction where available, and the station-relative cold-air-pooling adjustment. ",
  "The route-median daily mean TLz was lowest on ", summary_stats$coldest_daily_route_median_date,
  " (", sprintf('%.1f', summary_stats$coldest_daily_route_median_c), " deg C) and highest on ",
  summary_stats$warmest_daily_route_median_date, " (", sprintf('%.1f', summary_stats$warmest_daily_route_median_c), " deg C). ",
  "Across the October-to-April period, the route-median daily mean temperature remained below 0 deg C on ",
  summary_stats$days_route_median_below0, " days; on the same number of days, at least half of all routes had a daily mean TLz below freezing. ",
  "This shows that the thermal conditions favourable for ice growth were concentrated in repeated cold windows rather than being continuously present throughout the season. ",
  "Station relative humidity remained generally high (median daily route mean ",
  sprintf('%.0f', summary_stats$median_daily_rh_pct), "%), while route-nearest INCA wind speeds were mostly moderate (median daily route mean ",
  sprintf('%.1f', summary_stats$median_daily_wind_ms), " m s^-1). ",
  "Daily shortwave input increased towards spring, with a median route-level global-radiation load of ",
  sprintf('%.1f', summary_stats$median_daily_rad_mj_m2), " MJ m^-2 d^-1 over the analysed period. ",
  "Potential direct-sun exposure was strongly constrained by topography over much of the winter season (period median ",
  sprintf('%.1f', summary_stats$median_daily_sun_hours), " h d^-1), but increased by ",
  summary_stats$sun_end_date, " to a route median of ", sprintf('%.1f', summary_stats$sun_end_median_hours),
  " h d^-1 (interquartile range ", sprintf('%.1f', summary_stats$sun_end_p25_hours), "-",
  sprintf('%.1f', summary_stats$sun_end_p75_hours), " h d^-1). ",
  "Together, the station-derived temperature series and the radiation/sun-exposure diagnostics indicate a season shaped by alternating freeze and thaw episodes, with increasing melt potential during March and April.\n\n",
  "## Suggested figures\n\n",
  "- Figure 3.1: `fig_3_1_station_temperature_distribution.png` / `.pdf` - Seasonal station-derived icefall-temperature distribution.\n",
  "- Figure 3.2: `fig_3_1_station_freezing_share.png` / `.pdf` - Share of routes with below-freezing calculated icefall temperature.\n",
  "- Figure 3.3: `fig_3_1_station_degree_hours_by_elevation.png` / `.pdf` - Cumulative freezing and positive degree-hours from TLz by elevation band.\n",
  "- Figure 3.4: `fig_3_1_station_humidity_wind_radiation.png` / `.pdf` - Station humidity and INCA wind/radiation conditions.\n",
  "- Figure 3.5: `fig_3_1_station_topographic_sun_hours.png` / `.pdf` - Topographically possible direct-sun exposure.\n\n",
  "## Note\n\n",
  "Temperature statistics in this corrected version are based on TLz, not on INCA T2M. INCA is only retained for wind and global radiation, as in the operational model.\n"
)

writeLines(caption_text, file.path(out_dir, "section_3_1_station_temperature_draft.md"), useBytes = TRUE)
message("Done. Station-temperature outputs written to: ", out_dir)

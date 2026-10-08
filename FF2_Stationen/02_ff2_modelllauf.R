# ============================================================================
# FF2 - Schritt 2: Eismodell 2012/13 - 2025/26 mit Stationstemperatur
# ----------------------------------------------------------------------------
# Rechnet das Eismodell (scripts/diagram_uid.R) fuer die Routen aus Schritt 1
# in jedem Winter, in dem ihre Station belastbare Temperaturdaten liefert, und
# erzeugt danach Kennzahlen, Tabellen und Abbildungen fuer Kapitel 3.6.
#
# Eingaben je Route und Winter (wie Winter 2025/26, ausser der Feuchte):
#   Lufttemperatur    zugeordnete Station, geprueft in Schritt 1 (cache/),
#                     Stundenmittel linear auf 10 min interpoliert
#   rel. Feuchte      INCA RH2M am Routenpunkt
#   Wind, Strahlung   INCA UU/VV/GL am Routenpunkt
#   Inversion         scripts/00_build_inversion_cache.R je Winter
#   Sonne/Topographie Sonnenzeiten aus data/suntime auf das Kalenderdatum
#                     des jeweiligen Winters uebertragen
#
# Das Modell selbst bleibt unveraendert. Es laeuft in einer ARBEITSKOPIE
# (Ordner FF2_modell unter %LOCALAPPDATA%), das Original-Repository und die
# Ergebnisse von 2025/26 werden nicht angefasst. Eingriffe in die Kopie:
#   diagram_uid.R            Temperatur/Feuchte wie oben; Ausgabedatei je
#                            Winter; keine Einzelplots
#   00_build_inversion_cache Messluecken der Inversionsstationen > 6 h werden
#                            nicht mehr ueber Wochen fortgeschrieben, sondern
#                            als "keine Inversion" behandelt (das Modell nutzt
#                            dort den Standardgradienten)
#
# AUSFUEHREN (RStudio: Datei oeffnen, MODUS setzen, oben rechts "Source"):
#   1. MODUS <- "probe"  4 Routen x 2 Winter, ca. 5-15 min. Prueft Downloads
#                        und Modell, vergleicht 2025/26 mit dem bisherigen Lauf
#                        und rechnet die Laufzeit fuer den vollen Lauf hoch.
#   2. MODUS <- "voll"   alle Routen und Winter. Dauert viele Stunden, kann
#                        jederzeit abgebrochen und neu gestartet werden -
#                        fertige Laeufe und Downloads bleiben erhalten.
#   Ergebnisse: FF2_Stationen/ergebnis_modell/ (Tabellen, Kennzahlen, Abbildungen)
#   Auswertung (MODUS "voll"): Homogenitaetspruefung der Stationen, Ausschluss
#   inhomogener Stationen, Theil-Sen-Trends je Route, Bootstrap ueber Stationen,
#   Jackknife (je ein Winter weggelassen). Ist der Modelllauf schon fertig, wird
#   nur die Auswertung neu gerechnet (1-2 min).
#   Nach Abschluss kann der Ordner FF2_modell unter %LOCALAPPDATA% geloescht werden.
# ============================================================================

MODUS         <- "voll"      # "probe" oder "voll"
N_WORKER      <- NA          # parallele Modelllaeufe; NA = automatisch
WINTERS       <- 2012:2025   # Startjahr des Winters (2012 = 2012/13)
MIN_DAYS      <- 190         # gueltige Tage je Winter (wie Schritt 1)
MIN_TOTAL     <- 10          # Route: mindestens so viele gueltige Winter ...
MIN_HALF      <- 4           # ... davon je mindestens so viele in jeder Haelfte
THRESH_M      <- 0.15        # Eistag: Tagesmedian der Dicke >= 0.15 m
INCA_CHUNK    <- 8           # Routenpunkte je INCA-Abfrage
PROBE_UIDS    <- c(1, 26, 183, 182)
PROBE_WINTERS <- c(2015, 2025)          # 2015/16 enthaelt einen Schalttag
HOMOG_SHIFT_K <- 0.5         # Homogenitaet: Station inhomogen bei Sprung >= 0.5 K ...
HOMOG_P       <- 0.1         # ... mit Permutations-p < 0.1 ...
HOMOG_SD_K    <- 1.5         # ... oder Streuung der Differenzreihe > 1.5 K
HOMOG_PERM    <- 999         # Anzahl Permutationen
BOOT_N        <- 2000
BANDS <- c("<1500 m", "1500-2000 m", "2000-2500 m", ">2500 m")
BAND_COL <- c("<1500 m" = "#b4554e", "1500-2000 m" = "#d0993f",
              "2000-2500 m" = "#4f8fbd", ">2500 m" = "#183a5a")

# ------------------------------------------------------------ Grundlagen ----
need <- c("dplyr", "readr", "lubridate", "tidyr", "zoo", "httr2", "httr",
          "jsonlite", "ggplot2", "stringr")
miss <- need[!vapply(need, requireNamespace, logical(1), quietly = TRUE)]
if (length(miss)) stop("Fehlende R-Pakete. Bitte einmal ausfuehren:\n  install.packages(c(\"",
                       paste(miss, collapse = "\", \""), "\"))")
suppressPackageStartupMessages(library(ggplot2))
options(timeout = max(900, getOption("timeout")))   # grosse INCA-Abfragen

get_script_dir <- function() {
  for (i in rev(seq_len(sys.nframe()))) {
    of <- sys.frame(i)$ofile
    if (!is.null(of)) return(dirname(normalizePath(of)))
  }
  a <- commandArgs(trailingOnly = FALSE)
  f <- sub("^--file=", "", a[grep("^--file=", a)])
  if (length(f)) return(dirname(normalizePath(f)))
  getwd()
}
BASE  <- get_script_dir()
REPO  <- normalizePath(file.path(BASE, "..", "Ice fall modeling", "GitHub", "ice-waterfalls"),
                       mustWork = FALSE)
ERG1  <- file.path(BASE, "ergebnis")
CACHE <- file.path(BASE, "cache")
OUT   <- file.path(BASE, "ergebnis_modell")
PUB_DAILY <- file.path(BASE, "..", "output", "opus48", "figs_new", "modelled_ice_uid_daily.csv")
WORK  <- Sys.getenv("FF2_WORK", unset = if (.Platform$OS.type == "windows")
  file.path(Sys.getenv("LOCALAPPDATA"), "FF2_modell") else file.path(BASE, "FF2_modell"))
RSCRIPT <- file.path(R.home("bin"), if (.Platform$OS.type == "windows") "Rscript.exe" else "Rscript")

for (p in c(file.path(REPO, "scripts", "diagram_uid.R"),
            file.path(ERG1, "stationen_abdeckung.csv"), CACHE))
  if (!file.exists(p)) stop("Nicht gefunden: ", p,
                            "\nSkript bitte aus dem Ordner FF2_Stationen starten; Schritt 1 muss gelaufen sein.")
DAILY <- file.path(WORK, "tage")
for (d in c(WORK, DAILY, file.path(WORK, "logs"), OUT, file.path(OUT, "abbildungen"),
            file.path(OUT, "tabellen")))
  dir.create(d, recursive = TRUE, showWarnings = FALSE)
LOGFILE <- file.path(OUT, sprintf("protokoll_%s.txt", MODUS))
say <- function(...) {
  m <- paste0(format(Sys.time(), "%H:%M:%S"), "  ", paste0(...))
  message(m); cat(m, "\n", file = LOGFILE, append = TRUE)
}
wlab <- function(y) sprintf("%d/%02d", y, (y + 1) %% 100)

# ------------------------------------------------------ Routenauswahl -------
cov <- read.csv(file.path(ERG1, "stationen_abdeckung.csv"), check.names = FALSE,
                stringsAsFactors = FALSE, colClasses = c(station_id = "character"))
valid <- as.matrix(cov[, paste0("w", WINTERS)]) >= MIN_DAYS
rownames(valid) <- cov$station_id
assign <- read.csv(file.path(REPO, "data", "AWS", "icefalls_nearest_station.csv"),
                   encoding = "UTF-8", stringsAsFactors = FALSE,
                   colClasses = c(uid = "character", station_id = "character"))
assign$elev <- as.numeric(assign$icefall_elev_m)
assign$band <- factor(as.character(cut(assign$elev, c(-Inf, 1500, 2000, 2500, Inf),
                                       labels = BANDS, right = FALSE)), levels = BANDS)
V <- valid[match(assign$station_id, rownames(valid)), , drop = FALSE]
V[is.na(V)] <- FALSE
assign$n_winters <- rowSums(V)
assign$eligible  <- rowSums(V) >= MIN_TOTAL &
  rowSums(V[, WINTERS <= 2018, drop = FALSE]) >= MIN_HALF &
  rowSums(V[, WINTERS >= 2019, drop = FALSE]) >= MIN_HALF
routes <- assign[assign$eligible, ]
Vr <- V[assign$eligible, , drop = FALSE]
jobs <- do.call(rbind, lapply(seq_len(nrow(routes)), function(i)
  data.frame(uid = routes$uid[i], winter = WINTERS[Vr[i, ]], stringsAsFactors = FALSE)))
if (MODUS == "probe") {
  jobs <- jobs[jobs$uid %in% as.character(PROBE_UIDS) & jobs$winter %in% PROBE_WINTERS, ]
} else if (MODUS != "voll") stop("MODUS muss \"probe\" oder \"voll\" sein.")
jobs <- jobs[order(jobs$winter, as.integer(jobs$uid)), ]
rownames(jobs) <- NULL

say("==== FF2 Modelllauf, Modus ", MODUS, " ====")
say(sprintf("Routen im Auswahlkriterium (>= %d Winter, >= %d je Haelfte): %d  [%s]",
            MIN_TOTAL, MIN_HALF, nrow(routes),
            paste(sprintf("%s: %d", BANDS, as.integer(table(routes$band))), collapse = ", ")))
say(sprintf("Modelllaeufe in diesem Durchgang: %d (Route x Winter)", nrow(jobs)))

# ------------------------------------------- Arbeitskopie einrichten --------
patch_file <- function(src, dst, patches) {
  s <- paste(sub("\r$", "", readLines(src, warn = FALSE, encoding = "UTF-8")), collapse = "\n")
  for (p in patches) {
    n <- lengths(regmatches(s, gregexpr(p[["old"]], s, fixed = TRUE)))
    if (n != p[["n"]]) stop("Anpassung passt nicht zu ", basename(src), " (erwartet ",
                            p[["n"]], "x, gefunden ", n, "x):\n  ", substr(p[["old"]], 1, 90))
    s <- gsub(p[["old"]], p[["new"]], s, fixed = TRUE)
  }
  writeLines(s, dst, useBytes = TRUE)
}

# Ersatz fuer get_station_tlrf() im Modell: Temperatur aus dem Stundencache der
# Station (Schritt 1), rel. Feuchte aus der vorab geladenen INCA-Datei der Route.
ff2_station_fun <- function(start_date, end_date, station_id, source) {
  f <- file.path(Sys.getenv("FF2_CACHE"), sprintf("%s_%s.rds",
                 if (identical(source, "LWD")) "LWD" else "GEO", station_id))
  if (!file.exists(f)) stop("FF2: Stationscache fehlt: ", f)
  h <- readRDS(f)
  grid <- seq(as.POSIXct(as.Date(start_date), tz = TZ_LOCAL),
              as.POSIXct(as.Date(end_date) + 1, tz = TZ_LOCAL) - MODEL_STEP_MIN * 60,
              by = MODEL_STEP_MIN * 60)
  g <- as.numeric(grid)
  tc <- as.numeric(h$hour) + 1800                 # Stundenmittel -> Stundenmitte
  sel <- tc >= min(g) - 7200 & tc <= max(g) + 7200
  tc <- tc[sel]; tv <- h$tl[sel]
  TL <- rep(NA_real_, length(g))
  if (length(tc) >= 2) {
    TL <- stats::approx(tc, tv, xout = g, rule = 2)$y
    i <- findInterval(g, tc); n <- length(tc)
    inner <- i >= 1 & i < n
    span <- rep(Inf, length(g)); span[inner] <- tc[i[inner] + 1] - tc[i[inner]]
    edge <- pmin(ifelse(i >= 1, g - tc[pmax(i, 1)], Inf),
                 ifelse(i < n, tc[pmin(i + 1, n)] - g, Inf))
    TL[!((inner & span <= 3600) | edge <= 1800)] <- NA_real_   # nur zwischen Nachbarstunden
  }
  fi <- file.path(PATH_INCA_DIR, sprintf("inca_uid%s_ts_%s_%s.csv", UID_TEST,
                  format(as.Date(start_date), "%Y%m%d"), format(as.Date(end_date), "%Y%m%d")))
  if (!file.exists(fi)) stop("FF2: INCA-Datei fehlt: ", fi)
  d <- read_geosphere_csv(fi)
  tcol <- names(d)[grepl("time", tolower(names(d)))][1]
  rcol <- names(d)[grepl("^rh2m", tolower(names(d)))][1]
  if (is.na(tcol) || is.na(rcol)) stop("FF2: Spalte RH2M fehlt in ", fi)
  tt <- d[[tcol]]                                   # INCA-Zeit in UTC
  rt <- if (inherits(tt, "POSIXct")) as.numeric(tt) else {
    x <- sub("(Z|[+]00:?00)$", "", as.character(tt))
    p1 <- as.numeric(as.POSIXct(x, format = "%Y-%m-%dT%H:%M:%S", tz = "UTC"))
    p2 <- as.numeric(as.POSIXct(x, format = "%Y-%m-%dT%H:%M", tz = "UTC"))
    ifelse(is.na(p1), p2, p1)
  }
  rv <- suppressWarnings(as.numeric(d[[rcol]]))
  ok <- !is.na(rt); rt <- rt[ok]; rv <- rv[ok]
  if (!length(rt)) stop("FF2: keine lesbaren Zeitstempel in ", fi)
  o <- order(rt); rt <- rt[o]; rv <- rv[o]
  j <- findInterval(g, rt)
  RF <- rep(NA_real_, length(g))
  k <- which(j >= 1)
  RF[k] <- rv[j[k]]
  RF[k[(g[k] - rt[j[k]]) > 3 * 3600]] <- NA_real_
  tibble::tibble(timestamp = grid, TL = TL, RF = RF)
}

PATCH_MODEL <- list(
  list(old = 'PATH_OUT      <- sprintf("data/ModelRuns/model_uid%s.csv", UID_TEST)',
       new = 'PATH_OUT      <- sprintf("data/ModelRuns/model_uid%s_%s.csv", UID_TEST, format(END_DATE, "%Y%m%d"))',
       n = 1),
  list(old = "# 1) Load inputs (only required columns -> faster)",
       new = paste0('source(file.path("scripts", "ff2_override.R"))  # FF2: Station-TL + INCA-RH\n',
                    "# 1) Load inputs (only required columns -> faster)"),
       n = 1),
  list(old = "write_csv(mod, PATH_OUT)",
       new = "write_csv(mod, PATH_OUT)\nquit(save = \"no\", status = 0)  # FF2: keine Einzelplots",
       n = 1))

PATCH_INV <- list(
  list(old = paste0("      val = zoo::na.locf(val, na.rm = FALSE),\n",
                    "      val = zoo::na.locf(val, na.rm = FALSE, fromLast = TRUE)"),
       new = "      val = zoo::na.approx(val, na.rm = FALSE, maxgap = 36)  # FF2: Luecken > 6 h bleiben leer",
       n = 1),
  list(old = "cond_on  <- inv$inv_grad_max_C_per_100m >= 0.20",
       new = "cond_on  <- !is.na(inv$inv_grad_max_C_per_100m) & inv$inv_grad_max_C_per_100m >= 0.20",
       n = 2),
  list(old = "cond_off <- inv$inv_grad_max_C_per_100m <  0.05",
       new = "cond_off <- is.na(inv$inv_grad_max_C_per_100m) | inv$inv_grad_max_C_per_100m <  0.05",
       n = 2))

STATIC <- c("data/AWS/icefalls_nearest_station.csv", "data/AWS/stations_all.csv",
            "data/Wind/wind_vulnerability_5deg.csv",
            "data/derived/icefall_structure/icefall_structure_analysis.csv",
            "data/CAP/icefall_station_cap.csv",
            "data/Koordinaten_Wasserfaelle/eisklettern_links_entries_diff.csv")

setup_workcopy <- function() {
  for (d in c("scripts", "cache", "data/suntime", "data/inca_nordtirol/point_timeseries",
              "data/_cache_inversion", "data/ModelRuns", dirname(STATIC)))
    dir.create(file.path(WORK, d), recursive = TRUE, showWarnings = FALSE)
  for (f in STATIC) if (!file.copy(file.path(REPO, f), file.path(WORK, f), overwrite = TRUE))
    stop("Kopieren fehlgeschlagen: ", f)
  for (f in list.files(CACHE, "\\.rds$", full.names = TRUE))
    file.copy(f, file.path(WORK, "cache", basename(f)), overwrite = TRUE)
  patch_file(file.path(REPO, "scripts", "diagram_uid.R"),
             file.path(WORK, "scripts", "diagram_uid.R"), PATCH_MODEL)
  patch_file(file.path(REPO, "scripts", "00_build_inversion_cache.R"),
             file.path(WORK, "scripts", "00_build_inversion_cache.R"), PATCH_INV)
  writeLines(c("# FF2-Ersatz fuer get_station_tlrf(), erzeugt von 02_ff2_modelllauf.R",
               paste("get_station_tlrf <-",
                     paste(deparse(ff2_station_fun, width.cutoff = 500L), collapse = "\n"))),
             file.path(WORK, "scripts", "ff2_override.R"), useBytes = TRUE)
}

# Sonnenzeiten: data/suntime enthaelt Winter 2025/26 (1.11.-30.4.). Fuer jeden Winter
# werden dieselben Kalendertage mit denselben Uhrzeiten (UTC) eingetragen; der
# Schalttag erhaelt die Werte des 28. Februar. Oktober fehlt wie im Original.
build_sun <- function(uids) {
  for (u in uids) {
    ui <- as.integer(u)
    src <- file.path(REPO, "data", "suntime", sprintf("sun_uid_%03d.csv", ui))
    if (!file.exists(src)) src <- file.path(REPO, "data", "suntime", sprintf("sun_uid_%d.csv", ui))
    dst <- file.path(WORK, "data", "suntime", basename(src))
    if (!file.exists(src)) { say("  Hinweis: keine Sonnendatei fuer uid ", u); next }
    if (file.exists(dst)) next
    s <- read.csv(src, stringsAsFactors = FALSE, encoding = "UTF-8", check.names = FALSE)
    d0 <- as.Date(s$date)
    md <- format(d0, "%m-%d"); yr0 <- as.integer(format(d0, "%Y"))
    base_y <- ifelse(as.integer(format(d0, "%m")) >= 10, yr0, yr0 - 1)
    out <- lapply(WINTERS, function(w) {
      nd <- as.Date(sprintf("%d-%s", yr0 - base_y + w, md))
      x <- s
      x$date <- format(nd)
      x$sunrise_topo <- ifelse(is.na(x$sunrise_topo) | !nzchar(x$sunrise_topo), x$sunrise_topo,
                               paste0(format(nd), substring(x$sunrise_topo, 11)))
      x$sunset_topo  <- ifelse(is.na(x$sunset_topo) | !nzchar(x$sunset_topo), x$sunset_topo,
                               paste0(format(nd), substring(x$sunset_topo, 11)))
      leap <- as.Date(sprintf("%d-02-29", w + 1), optional = TRUE)
      if (!is.na(leap)) {
        f28 <- which(format(nd, "%m-%d") == "02-28")
        if (length(f28)) {
          z <- x[f28[1], ]; z$date <- format(leap)
          if (!is.na(z$sunrise_topo) && nzchar(z$sunrise_topo)) z$sunrise_topo <- paste0(format(leap), substring(z$sunrise_topo, 11))
          if (!is.na(z$sunset_topo) && nzchar(z$sunset_topo))  z$sunset_topo  <- paste0(format(leap), substring(z$sunset_topo, 11))
          x <- rbind(x[seq_len(f28[1]), ], z, x[-seq_len(f28[1]), ])
        }
      }
      x
    })
    write.csv(do.call(rbind, out), dst, row.names = FALSE)
  }
}

# ------------------------------------------------------------ Downloads -----
fetch <- function(url, tries = 5) {
  tmp <- tempfile(fileext = ".csv")
  for (k in seq_len(tries)) {
    r <- tryCatch(download.file(url, tmp, method = "libcurl", quiet = TRUE, mode = "wb"),
                  error = function(e) e, warning = function(w) w)
    if (identical(r, 0L)) return(tmp)
    msg <- if (inherits(r, "condition")) conditionMessage(r) else ""
    if (grepl("429", msg)) { say("    Rate-Limit der GeoSphere-API - warte 60 s"); Sys.sleep(60); next }
    if (grepl("400|404|422", msg)) { say("    Abfrage abgelehnt: ", substr(msg, 1, 160)); return(NULL) }
    Sys.sleep(5 * k)
  }
  NULL
}

inca_path <- function(uid, y) file.path(WORK, "data", "inca_nordtirol", "point_timeseries",
                                         sprintf("inca_uid%s_ts_%d1001_%d0430.csv", uid, y, y + 1))

inca_download_chunk <- function(pts, y) {
  url <- paste0("https://dataset.api.hub.geosphere.at/v1/timeseries/historical/inca-v1-1h-1km",
                "?parameters=UU%2CVV%2CGL%2CRH2M",
                "&start=", y, "-10-01T00%3A00&end=", y + 1, "-04-30T23%3A00",
                paste0("&lat_lon=", sprintf("%.6f%%2C%.6f", pts$lat, pts$lon), collapse = ""),
                "&output_format=csv")
  f <- fetch(url)
  if (is.null(f)) return(NULL)
  d <- tryCatch(read.csv(f, stringsAsFactors = FALSE, check.names = FALSE), error = function(e) NULL)
  unlink(f)
  d
}

split_inca <- function(d, pts) {   # Mehrpunkt-Antwort -> ein Block je angefragtem Punkt
  lat <- d[["lat"]]; lon <- d[["lon"]]; tt <- d[["time"]]
  if (is.null(lat) || is.null(lon) || is.null(tt)) return(NULL)
  br <- c(TRUE, lat[-1] != lat[-length(lat)] | lon[-1] != lon[-length(lon)] |
            tt[-1] <= tt[-length(tt)])
  grp <- cumsum(br)
  if (max(grp) != nrow(pts)) return(NULL)
  blocks <- split(d, grp)
  for (i in seq_along(blocks))
    if (abs(blocks[[i]]$lat[1] - pts$lat[i]) > 0.02 || abs(blocks[[i]]$lon[1] - pts$lon[i]) > 0.02)
      return(NULL)
  blocks
}

get_inca <- function(jobs) {
  need <- jobs[!file.exists(inca_path(jobs$uid, jobs$winter)), ]
  if (!nrow(need)) { say("INCA: alle Dateien vorhanden"); return(invisible()) }
  say(sprintf("INCA: lade %d Routen-Winter (UU, VV, GL, RH2M) ...", nrow(need)))
  for (y in sort(unique(need$winter))) {
    u <- need$uid[need$winter == y]
    pts <- assign[match(u, assign$uid), c("uid", "ice_lat", "ice_lon")]
    names(pts) <- c("uid", "lat", "lon")
    ch <- split(pts, ceiling(seq_len(nrow(pts)) / INCA_CHUNK))
    for (k in seq_along(ch)) {
      p <- ch[[k]]
      d <- inca_download_chunk(p, y)
      b <- if (!is.null(d)) split_inca(d, p) else NULL
      if (is.null(b)) {                          # Rueckfall: jeden Punkt einzeln
        b <- lapply(seq_len(nrow(p)), function(i) inca_download_chunk(p[i, ], y))
      }
      for (i in seq_len(nrow(p))) if (!is.null(b[[i]]) && nrow(b[[i]]) > 0)
        write.csv(b[[i]], inca_path(p$uid[i], y), row.names = FALSE)
      say(sprintf("  INCA %s: Block %d/%d fertig", wlab(y), k, length(ch)))
    }
  }
  miss <- sum(!file.exists(inca_path(jobs$uid, jobs$winter)))
  if (miss) say("  WARNUNG: fuer ", miss, " Routen-Winter fehlt INCA - diese Laeufe entfallen.")
}

# ------------------------------------------------------------ Inversion -----
inv_path <- function(y) file.path(WORK, "data", "_cache_inversion", sprintf("inversion_%d0430.rds", y + 1))

build_inversion <- function(y) {
  if (file.exists(inv_path(y))) return(TRUE)
  owd <- setwd(WORK); on.exit(setwd(owd))
  Sys.setenv(MODEL_END_DATE = sprintf("%d-04-30", y + 1))
  log <- file.path("logs", sprintf("inversion_%d.log", y))
  system2(RSCRIPT, c("scripts/00_build_inversion_cache.R"), stdout = log, stderr = log)
  file.exists(inv_path(y))
}

# ----------------------------------------------------------- Modelllauf -----
run_job <- function(uid, y) {
  out <- file.path(DAILY, sprintf("w%d", y), sprintf("uid_%s.csv", uid))
  if (file.exists(out)) return(data.frame(uid = uid, winter = y, status = "vorhanden", sec = NA))
  dir.create(dirname(out), showWarnings = FALSE)
  t0 <- Sys.time()
  owd <- setwd(WORK); on.exit(setwd(owd))
  Sys.setenv(MODEL_END_DATE = sprintf("%d-04-30", y + 1), FF2_CACHE = "cache", UID_TEST = uid)
  log <- file.path("logs", sprintf("w%d_uid%s.log", y, uid))
  system2(RSCRIPT, c("scripts/diagram_uid.R", uid), stdout = log, stderr = log)
  mf <- file.path("data", "ModelRuns", sprintf("model_uid%s_%d0430.csv", uid, y + 1))
  sec <- as.numeric(difftime(Sys.time(), t0, units = "secs"))
  if (!file.exists(mf)) return(data.frame(uid = uid, winter = y, status = "FEHLER", sec = sec))
  m <- readr::read_csv(mf, show_col_types = FALSE, progress = FALSE,
                       col_select = dplyr::any_of(c("date", "thickness_m", "TLz", "FDH", "PDH",
                                                    "weather_ok", "use_prof", "RF", "GLOW",
                                                    "cap_temp_adjust_C")))
  m$date <- as.Date(m$date)
  m <- m[m$date >= as.Date(sprintf("%d-10-01", y)) & m$date <= as.Date(sprintf("%d-04-30", y + 1)), ]
  dly <- dplyr::summarise(dplyr::group_by(m, date),
    thickness_m = stats::median(thickness_m, na.rm = TRUE),
    thick_max   = max(thickness_m, na.rm = TRUE),
    TLz_mean    = mean(TLz, na.rm = TRUE),
    fdh_Ch      = sum(FDH, na.rm = TRUE) / 6,
    pdh_Ch      = sum(PDH, na.rm = TRUE) / 6,
    ok_share    = mean(as.logical(weather_ok), na.rm = TRUE),
    prof_share  = mean(as.logical(use_prof), na.rm = TRUE),
    rf_mean     = mean(RF, na.rm = TRUE),
    sw_MJ       = sum(GLOW, na.rm = TRUE) * 600 / 1e6,
    cap_mean_C  = mean(cap_temp_adjust_C, na.rm = TRUE),
    .groups = "drop")
  tmp <- paste0(out, ".tmp")
  write.csv(dly, tmp, row.names = FALSE)
  file.rename(tmp, out)
  unlink(mf)
  data.frame(uid = uid, winter = y, status = "ok", sec = sec)
}

# ======================================================== Ablauf ============
setup_workcopy()
build_sun(unique(jobs$uid))
get_inca(jobs)

say("Inversion je Winter ...")
inv_ok <- vapply(sort(unique(jobs$winter)), build_inversion, logical(1))
if (!all(inv_ok)) say("  WARNUNG: Inversion fehlt fuer ", paste(wlab(sort(unique(jobs$winter))[!inv_ok]), collapse = ", "),
                      " - das Modell rechnet dort ohne Inversionsprofil (siehe logs/inversion_*.log)")

todo <- jobs[file.exists(inca_path(jobs$uid, jobs$winter)), ]
nw <- if (is.na(N_WORKER)) max(1L, min(6L, parallel::detectCores() - 2L)) else as.integer(N_WORKER)
say(sprintf("Modelllaeufe: %d, parallel: %d", nrow(todo), nw))
cl <- parallel::makeCluster(nw)
parallel::clusterExport(cl, c("WORK", "DAILY", "RSCRIPT", "run_job"))
res <- list(); t_start <- Sys.time()
batches <- split(seq_len(nrow(todo)), ceiling(seq_len(nrow(todo)) / (nw * 4)))
for (b in seq_along(batches)) {
  idx <- batches[[b]]
  r <- parallel::clusterMap(cl, run_job, todo$uid[idx], todo$winter[idx], SIMPLIFY = FALSE,
                            .scheduling = "dynamic")
  res <- c(res, r)
  done <- max(idx); el <- as.numeric(difftime(Sys.time(), t_start, units = "mins"))
  n_new <- sum(vapply(res, function(x) x$status != "vorhanden", logical(1)))
  eta <- if (n_new > 0) el / n_new * (nrow(todo) - done) else NA
  say(sprintf("  %d/%d Laeufe (%.0f%%), %.0f min vergangen%s", done, nrow(todo), 100 * done / nrow(todo), el,
              if (is.na(eta)) "" else sprintf(", noch ca. %.0f min", eta)))
}
parallel::stopCluster(cl)
res <- if (length(res)) do.call(rbind, res) else
  data.frame(uid = character(), winter = integer(), status = character(), sec = numeric())
write.csv(res, file.path(OUT, "tabellen", sprintf("laufstatus_%s.csv", MODUS)), row.names = FALSE)
nf <- sum(res$status == "FEHLER")
if (nf) say("  WARNUNG: ", nf, " Laeufe fehlgeschlagen - Logs in ", file.path(WORK, "logs"))

# ================================================= Auswertung ===============
read_daily <- function(j) {
  f <- file.path(DAILY, sprintf("w%d", j$winter), sprintf("uid_%s.csv", j$uid))
  if (!file.exists(f)) return(NULL)
  d <- read.csv(f, stringsAsFactors = FALSE); d$date <- as.Date(d$date)
  d$uid <- j$uid; d$winter <- j$winter; d
}
D <- do.call(rbind, lapply(split(jobs, seq_len(nrow(jobs))), read_daily))
if (is.null(D) || !nrow(D)) stop("Keine Ergebnisse vorhanden - siehe Protokoll und Logs.")
D$band <- assign$band[match(D$uid, assign$uid)]
saveRDS(D, file.path(OUT, sprintf("tageswerte_%s.rds", MODUS)))

rw <- do.call(rbind, lapply(split(D, list(D$uid, D$winter), drop = TRUE), function(d) {
  on <- d$date[d$thickness_m >= THRESH_M]
  data.frame(uid = d$uid[1], winter = d$winter[1], band = d$band[1],
             ice_days = sum(d$thickness_m >= THRESH_M, na.rm = TRUE),
             peak_m = max(d$thickness_m, na.rm = TRUE),
             onset = if (length(on)) as.character(min(on)) else NA,
             last = if (length(on)) as.character(max(on)) else NA,
             ok_share = mean(d$ok_share, na.rm = TRUE),
             prof_share = mean(d$prof_share, na.rm = TRUE),
             n_days = nrow(d))
}))
rw$station_id <- assign$station_id[match(rw$uid, assign$uid)]
rw$elev <- assign$elev[match(rw$uid, assign$uid)]
write.csv(rw, file.path(OUT, "tabellen", sprintf("route_winter_%s.csv", MODUS)), row.names = FALSE)

# Vergleich 2025/26 mit dem bisherigen Lauf (Station-TL 10 min, Station-RF)
chk <- NULL
if (file.exists(PUB_DAILY) && any(rw$winter == 2025)) {
  pub <- read.csv(PUB_DAILY, stringsAsFactors = FALSE)
  pub$date <- as.Date(pub$date); pub$uid <- as.character(pub$uid)
  pub <- pub[pub$date >= as.Date("2025-10-01") & pub$date <= as.Date("2026-04-30"), ]
  pa <- do.call(rbind, lapply(split(pub, pub$uid), function(d)
    data.frame(uid = d$uid[1], ice_days_pub = sum(d$thickness_m >= THRESH_M, na.rm = TRUE),
               peak_pub = max(d$thickness_m, na.rm = TRUE))))
  chk <- merge(rw[rw$winter == 2025, c("uid", "band", "ice_days", "peak_m")], pa, by = "uid")
  chk$diff_days <- chk$ice_days - chk$ice_days_pub
  write.csv(chk, file.path(OUT, "tabellen", sprintf("vergleich_2025_%s.csv", MODUS)), row.names = FALSE)
}

# ------------------------------------------------------------- Probe --------
if (MODUS == "probe") {
  ok <- res[res$status == "ok", ]
  full_jobs <- do.call(rbind, lapply(seq_len(nrow(routes)), function(i)
    data.frame(uid = routes$uid[i], winter = WINTERS[Vr[i, ]])))
  L <- c("", "==== PROBELAUF ====",
         sprintf("Laeufe ok: %d von %d", nrow(ok), nrow(res)),
         if (nrow(ok)) sprintf("Mittlere Dauer je Lauf: %.0f s  ->  voller Lauf (%d Laeufe, %d parallel): ca. %.1f h Rechenzeit",
                               mean(ok$sec), nrow(full_jobs), nw, mean(ok$sec) * nrow(full_jobs) / nw / 3600),
         sprintf("  + INCA-Downloads fuer %d Routen-Winter (ca. %d Abfragen)", nrow(full_jobs),
                 ceiling(nrow(full_jobs) / INCA_CHUNK)),
         "", "Ergebnisse je Route und Winter:",
         capture.output(print(rw[, c("uid", "band", "winter", "ice_days", "peak_m", "ok_share", "prof_share")],
                              row.names = FALSE, digits = 3)))
  if (!is.null(chk)) L <- c(L, "", "Vergleich 2025/26 mit dem bisherigen Lauf (Eistage >= 0.15 m):",
                            capture.output(print(chk, row.names = FALSE, digits = 3)))
  writeLines(L, file.path(OUT, "probe_ergebnis.txt"), useBytes = TRUE)
  cat(paste(L, collapse = "\n"), "\n")
  if (!is.null(pub <- if (file.exists(PUB_DAILY)) read.csv(PUB_DAILY, stringsAsFactors = FALSE) else NULL)) {
    pub$date <- as.Date(pub$date); pub$uid <- as.character(pub$uid)
    pp <- pub[pub$uid %in% unique(D$uid) & pub$date >= as.Date("2025-10-01") & pub$date <= as.Date("2026-04-30"), ]
    s25 <- D[D$winter == 2025, ]
    g <- ggplot() +
      geom_line(data = pp, aes(date, thickness_m, colour = "bisheriger Lauf 2025/26"), linewidth = 0.8) +
      geom_line(data = s25, aes(date, thickness_m, colour = "FF2 2025/26"), linewidth = 0.5) +
      facet_wrap(~ uid, ncol = 2, labeller = label_both) +
      geom_hline(yintercept = THRESH_M, linetype = 2, linewidth = 0.3) +
      scale_colour_manual(values = c("bisheriger Lauf 2025/26" = "grey55", "FF2 2025/26" = "#c9584f"), name = NULL) +
      labs(x = NULL, y = "Tagesmedian Eisdicke (m)") + theme_minimal(9) + theme(legend.position = "top")
    ggsave(file.path(OUT, "abbildungen", "probe_vergleich_2025.png"), g, width = 7.4, height = 5, dpi = 200, bg = "white")
  }
  say("Probelauf fertig. Ergebnis: ", file.path(OUT, "probe_ergebnis.txt"))
  say("Wenn alles passt: oben MODUS <- \"voll\" setzen und erneut auf Source klicken.")
} else {
  # ======================================== volle Auswertung ================
  theil_sen <- function(x, y) {
    if (length(x) < 3) return(c(slope = NA, intercept = NA))
    ij <- utils::combn(length(x), 2)
    b <- stats::median((y[ij[2, ]] - y[ij[1, ]]) / (x[ij[2, ]] - x[ij[1, ]]))
    c(slope = b, intercept = stats::median(y - b * x))
  }
  mann_kendall <- function(y) {
    n <- length(y); if (n < 3) return(c(S = NA, z = NA, p = NA))
    s <- 0; for (k in 1:(n - 1)) s <- s + sum(sign(y[(k + 1):n] - y[k]))
    t <- table(y); v <- (n * (n - 1) * (2 * n + 5) - sum(t * (t - 1) * (2 * t + 5))) / 18
    z <- if (s > 0) (s - 1) / sqrt(v) else if (s < 0) (s + 1) / sqrt(v) else 0
    c(S = s, z = z, p = 2 * stats::pnorm(-abs(z)))
  }
  GROUPS <- c(BANDS, ">2000 m", "all routes")
  sel_group <- function(d, g) {
    if (g == "all routes") d else if (g == ">2000 m") d[d$band %in% c("2000-2500 m", ">2500 m"), ]
    else d[d$band == g, ]
  }

  # -------------------------------------------- Homogenitaetspruefung -------
  # Jede Station wird mit dem Median aller uebrigen Stationen verglichen:
  # Tagesmittel -> Abweichung von der eigenen Tagesklimatologie -> minus Median
  # der Abweichungen aller anderen Stationen am selben Tag -> Wintermittel.
  # In dieser Differenzreihe wird der staerkste Sprung gesucht (mind. 3 Winter je
  # Seite); ein Permutationstest (Winterreihenfolge zufaellig gemischt) prueft,
  # ob ein so grosser Sprung auch zufaellig entstehen kann.
  say("Homogenitaetspruefung der Stationen ...")
  st_ids <- sort(unique(rw$station_id))
  src_of <- function(id) assign$source[match(id, assign$station_id)]
  wy <- function(d) { m <- as.integer(format(d, "%m")); y <- as.integer(format(d, "%Y")); ifelse(m >= 10, y, y - 1) }
  A <- do.call(rbind, lapply(st_ids, function(id) {
    h <- readRDS(file.path(CACHE, sprintf("%s_%s.rds", if (identical(src_of(id), "LWD")) "LWD" else "GEO", id)))
    d <- as.Date(format(h$hour, "%Y-%m-%d", tz = "Etc/GMT-1"))
    n <- tapply(h$tl, d, length); m <- tapply(h$tl, d, mean)
    x <- data.frame(date = as.Date(names(m)), t = as.numeric(m))[as.numeric(n) >= 18, ]
    x$w <- wy(x$date)
    x <- x[as.integer(format(x$date, "%m")) %in% c(10:12, 1:4) & x$w %in% WINTERS[valid[id, ]], ]
    doy <- format(x$date, "%m-%d")
    x$anom <- x$t - tapply(x$t, doy, mean)[doy]
    x$id <- id
    x
  }))
  tmax <- function(s) {
    mx <- 0; k <- NA
    for (i in 3:(length(s) - 3)) {
      a <- s[1:i]; b <- s[(i + 1):length(s)]
      tt <- (mean(b) - mean(a)) / sqrt(stats::var(a) / length(a) + stats::var(b) / length(b))
      if (is.finite(tt) && abs(tt) > abs(mx)) { mx <- tt; k <- i }
    }
    c(t = mx, k = k)
  }
  hser <- list()
  hom <- do.call(rbind, lapply(st_ids, function(id) {
    me <- A[A$id == id, ]; ot <- A[A$id != id, ]
    ref <- tapply(ot$anom, as.character(ot$date), stats::median)
    me$D <- me$anom - ref[as.character(me$date)]
    s <- tapply(me$D, me$w, mean); w <- as.integer(names(s)); s <- as.numeric(s); n <- length(s)
    hser[[id]] <<- data.frame(station_id = id, winter = w, D = s)
    best <- tmax(s); k <- best[["k"]]
    set.seed(1)
    perm <- replicate(HOMOG_PERM, abs(tmax(sample(s))[["t"]]))
    data.frame(station_id = id, source = src_of(id),
               name = assign$station_name[match(id, assign$station_id)],
               n_routes = sum(routes$station_id == id), n_winters = n,
               break_after = if (is.na(k)) NA else w[k],
               shift_K = if (is.na(k)) 0 else mean(s[(k + 1):n]) - mean(s[1:k]),
               t = best[["t"]], p_perm = mean(perm >= abs(best[["t"]])), sd_K = stats::sd(s))
  }))
  hom$inhomogeneous <- (abs(hom$shift_K) >= HOMOG_SHIFT_K & hom$p_perm < HOMOG_P) | hom$sd_K > HOMOG_SD_K
  hom <- hom[order(!hom$inhomogeneous, -abs(hom$shift_K)), ]
  hser <- do.call(rbind, hser)
  write.csv(hom, file.path(OUT, "tabellen", "stationen_homogenitaet.csv"), row.names = FALSE)
  write.csv(hser, file.path(OUT, "tabellen", "stationen_differenzreihen.csv"), row.names = FALSE)
  bad <- hom$station_id[hom$inhomogeneous]
  rw_all <- rw
  rw <- rw[!rw$station_id %in% bad, ]
  say(sprintf("  %d von %d Stationen inhomogen (%s) -> %d Routen ausgeschlossen, %d Routen verbleiben",
              length(bad), nrow(hom), paste(bad, collapse = ", "),
              length(unique(rw_all$uid)) - length(unique(rw$uid)), length(unique(rw$uid))))

  # ------------------------------------------------ Trend je Route --------
  route_trends <- function(rw) do.call(rbind, lapply(split(rw, rw$uid), function(d) {
    d <- d[order(d$winter), ]
    ts <- theil_sen(d$winter, d$ice_days); mk <- mann_kendall(d$ice_days)
    data.frame(uid = d$uid[1], band = d$band[1], station_id = d$station_id[1], elev = d$elev[1],
               n_winters = nrow(d), n_h1 = sum(d$winter <= 2018), n_h2 = sum(d$winter >= 2019),
               mean_days = mean(d$ice_days), slope_dec = 10 * ts[["slope"]], mk_p = mk[["p"]])
  }))
  tr <- route_trends(rw)
  drop <- tr$n_winters < MIN_TOTAL | tr$n_h1 < MIN_HALF | tr$n_h2 < MIN_HALF
  if (any(drop)) say("  ", sum(drop), " Routen haben nach fehlgeschlagenen Laeufen zu wenige Winter und entfallen: ",
                     paste(tr$uid[drop], collapse = ", "))
  tr <- tr[!drop, ]
  rw <- rw[rw$uid %in% tr$uid, ]
  write.csv(tr, file.path(OUT, "tabellen", "route_trends.csv"), row.names = FALSE)
  tr_all <- route_trends(rw_all)

  set.seed(2026)
  boot_med <- function(t) {           # Median der Routentrends, Bootstrap ueber Stationen
    st <- unique(t$station_id); by_st <- split(t$slope_dec, t$station_id)
    bs <- replicate(BOOT_N, stats::median(unlist(by_st[sample(st, length(st), replace = TRUE)])))
    c(med = stats::median(t$slope_dec), lo = unname(stats::quantile(bs, 0.025)),
      hi = unname(stats::quantile(bs, 0.975)))
  }
  band_sum <- function(t, lab) {
    b <- boot_med(t)
    data.frame(group = lab, n_routes = nrow(t), n_stations = length(unique(t$station_id)),
               clim_days = stats::median(t$mean_days), slope_med = b[["med"]],
               ci_lo = b[["lo"]], ci_hi = b[["hi"]],
               share_neg = mean(t$slope_dec < 0), share_sig = mean(t$mk_p < 0.05, na.rm = TRUE))
  }
  bs <- do.call(rbind, lapply(GROUPS, function(g) band_sum(sel_group(tr, g), g)))
  write.csv(bs, file.path(OUT, "tabellen", "band_trends.csv"), row.names = FALSE)
  bs_all <- do.call(rbind, lapply(GROUPS, function(g) {
    t <- sel_group(tr_all, g); data.frame(group = g, n_routes = nrow(t), slope_med = stats::median(t$slope_dec))
  }))

  # Anomalien je Route (Abweichung vom eigenen Mittel) -> Median je Gruppe und Winter
  rw$anom <- rw$ice_days - tr$mean_days[match(rw$uid, tr$uid)]
  an <- do.call(rbind, lapply(GROUPS, function(g) {
    d <- sel_group(rw, g)
    do.call(rbind, lapply(WINTERS, function(w) {
      x <- d$anom[d$winter == w]
      data.frame(group = g, winter = w, n = length(x), anom_med = if (length(x)) stats::median(x) else NA)
    }))
  }))
  an_tr <- do.call(rbind, lapply(GROUPS, function(g) {
    d <- an[an$group == g & !is.na(an$anom_med), ]
    ts <- theil_sen(d$winter, d$anom_med); mk <- mann_kendall(d$anom_med)
    data.frame(group = g, slope_dec = 10 * ts[["slope"]], intercept = ts[["intercept"]], mk_p = mk[["p"]])
  }))
  write.csv(an, file.path(OUT, "tabellen", "anomalie_reihen.csv"), row.names = FALSE)

  # Kontrolle: feste Zusammensetzung (Routen mit allen 14 Wintern)
  full_uids <- tr$uid[tr$n_winters == length(WINTERS)]
  fc <- do.call(rbind, lapply(GROUPS, function(g) {
    d <- sel_group(rw[rw$uid %in% full_uids, ], g)
    if (!nrow(d)) return(NULL)
    s <- stats::aggregate(ice_days ~ winter, d, stats::median)
    ts <- theil_sen(s$winter, s$ice_days); mk <- mann_kendall(s$ice_days)
    data.frame(group = g, n_routes = length(unique(d$uid)), slope_dec = 10 * ts[["slope"]], mk_p = mk[["p"]])
  }))
  write.csv(fc, file.path(OUT, "tabellen", "kontrolle_feste_zusammensetzung.csv"), row.names = FALSE)

  # Jackknife: jeden Winter einmal weglassen
  jk <- do.call(rbind, lapply(WINTERS, function(w0) {
    d <- rw[rw$winter != w0, ]
    t <- do.call(rbind, lapply(split(d, d$uid), function(x) {
      x <- x[order(x$winter), ]
      data.frame(band = x$band[1], slope_dec = 10 * theil_sen(x$winter, x$ice_days)[["slope"]])
    }))
    do.call(rbind, lapply(GROUPS, function(g)
      data.frame(group = g, dropped = w0, slope_med = stats::median(sel_group(t, g)$slope_dec))))
  }))
  write.csv(jk, file.path(OUT, "tabellen", "jackknife.csv"), row.names = FALSE)
  jks <- do.call(rbind, lapply(GROUPS, function(g) {
    x <- jk[jk$group == g, ]
    data.frame(group = g, min = min(x$slope_med), max = max(x$slope_med),
               min_without = wlab(x$dropped[which.max(x$slope_med)]), all_negative = all(x$slope_med < 0))
  }))

  # Winter-Rangfolge und Datenqualitaet je Winter
  alla <- an[an$group == "all routes", ]
  rank_tab <- alla[order(-alla$anom_med), c("winter", "n", "anom_med")]
  rank_tab$rank <- seq_len(nrow(rank_tab))
  best <- rank_tab$winter[1]; worst <- rank_tab$winter[nrow(rank_tab)]
  qual <- do.call(rbind, lapply(WINTERS, function(w) {
    d <- rw[rw$winter == w, ]
    data.frame(winter = wlab(w), n_routes = nrow(d),
               temp_ok_median = stats::median(d$ok_share), inversion_profile_share = stats::median(d$prof_share))
  }))
  write.csv(qual, file.path(OUT, "tabellen", "datenqualitaet_je_winter.csv"), row.names = FALSE)

  # ---------------------------------------------------------- Abbildungen --
  thm <- theme_minimal(base_size = 8.5) +
    theme(panel.grid.minor = element_blank(), plot.title = element_text(size = 9, face = "plain"),
          legend.key.height = unit(0.35, "cm"))
  D <- D[D$uid %in% tr$uid, ]
  # (a) Saisonverlauf, feste Zusammensetzung
  Df <- D[D$uid %in% full_uids, ]
  Df$plot_date <- as.Date("2000-10-01") + as.numeric(Df$date - as.Date(sprintf("%d-10-01", Df$winter)))
  sa <- stats::aggregate(thickness_m ~ winter + plot_date, Df, stats::median)
  # Saisonverlauf fuer die Arbeit (Diagramm_Skripte/3_6_und_3_7_.../build_fig_3_7_stationen.py)
  sv <- stats::aggregate(thickness_m ~ winter + date, Df, stats::median)
  sv$n_routes <- stats::aggregate(thickness_m ~ winter + date, Df, length)$thickness_m
  write.csv(sv[order(sv$winter, sv$date), ], file.path(OUT, "tabellen", "saisonverlauf_routen_alle_winter.csv"),
            row.names = FALSE)
  kcol <- setNames(c("#c9584f", "#183a5a", "#d0993f", "grey72"),
                   c("2025/26 (model winter)", paste0(wlab(best), " (highest)"),
                     paste0(wlab(worst), " (lowest)"), "other winters"))
  sa$kind <- ifelse(sa$winter == 2025, names(kcol)[1], ifelse(sa$winter == best, names(kcol)[2],
             ifelse(sa$winter == worst, names(kcol)[3], names(kcol)[4])))
  sa$kind <- factor(sa$kind, levels = names(kcol))
  pa <- ggplot(mapping = aes(plot_date, thickness_m, group = winter, colour = kind)) +
    geom_hline(yintercept = THRESH_M, linetype = 2, linewidth = 0.3) +
    geom_line(data = sa[sa$kind == "other winters", ], linewidth = 0.35) +
    geom_line(data = sa[sa$kind != "other winters", ], linewidth = 0.9) +
    scale_colour_manual(values = kcol, breaks = names(kcol), name = NULL) +
    scale_x_date(date_breaks = "1 month", date_labels = "%b", expand = c(0.01, 0)) +
    labs(x = NULL, y = "Median modelled thickness (m)",
         title = sprintf("(a) Seasonal course, routes with all %d winters (n = %d)", length(WINTERS), length(full_uids))) +
    thm + theme(legend.position = c(0.01, 0.99), legend.justification = c(0, 1))
  # (b) Anomalien je Hoehenstufe
  ab <- an[an$group %in% BANDS & !is.na(an$anom_med), ]
  ab$group <- factor(ab$group, levels = BANDS)
  tl <- merge(an_tr[an_tr$group %in% BANDS, ], data.frame(winter = range(WINTERS)))
  tl$y <- tl$intercept + tl$slope_dec / 10 * tl$winter
  tl$group <- factor(tl$group, levels = BANDS)
  pb <- ggplot(ab, aes(winter, anom_med, colour = group)) +
    geom_hline(yintercept = 0, linewidth = 0.3, colour = "grey40") +
    geom_line(linewidth = 0.5) + geom_point(size = 1.2) +
    geom_line(data = tl, aes(winter, y, colour = group), linetype = 2, linewidth = 0.45) +
    scale_colour_manual(values = BAND_COL, name = NULL) +
    scale_x_continuous(breaks = c(2012, 2015, 2018, 2021, 2025), labels = wlab) +
    labs(x = NULL, y = "Ice-day anomaly (days)", title = "(b) Median anomaly per elevation band") +
    thm + theme(legend.position = "bottom")
  # (c) Routentrends je Hoehenstufe
  tc <- tr; tc$band <- factor(tc$band, levels = BANDS)
  bb <- bs[bs$group %in% BANDS, ]; bb$band <- factor(bb$group, levels = BANDS)
  bb$lab <- sprintf("%s\n%d routes, %d st.", bb$group, bb$n_routes, bb$n_stations)
  pc <- ggplot(tc, aes(band, slope_dec)) +
    geom_hline(yintercept = 0, linewidth = 0.3, colour = "grey40") +
    geom_boxplot(fill = NA, outlier.shape = NA, width = 0.55, linewidth = 0.3, colour = "grey55") +
    geom_jitter(aes(colour = band), width = 0.16, height = 0, size = 0.8, alpha = 0.6, show.legend = FALSE) +
    geom_errorbar(data = bb, aes(x = band, ymin = ci_lo, ymax = ci_hi), inherit.aes = FALSE,
                  width = 0.14, linewidth = 0.8) +
    geom_point(data = bb, aes(band, slope_med), inherit.aes = FALSE, size = 2) +
    scale_colour_manual(values = BAND_COL) +
    scale_x_discrete(labels = setNames(bb$lab, as.character(bb$band))) +
    labs(x = NULL, y = "Trend in ice days (days per decade)",
         title = "(c) Route-level Theil-Sen trends") + thm
  png(file.path(OUT, "abbildungen", "fig_3_7_ff2_stationen.png"), width = 7.4, height = 6.9,
      units = "in", res = 300, bg = "white")
  grid::grid.newpage()
  grid::pushViewport(grid::viewport(layout = grid::grid.layout(2, 2, heights = grid::unit(c(3.0, 3.9), "in"))))
  print(pa, vp = grid::viewport(layout.pos.row = 1, layout.pos.col = 1:2))
  print(pb, vp = grid::viewport(layout.pos.row = 2, layout.pos.col = 1))
  print(pc, vp = grid::viewport(layout.pos.row = 2, layout.pos.col = 2))
  invisible(dev.off())

  # Homogenitaet: Differenzreihen der ausgeschlossenen Stationen vor dem Hintergrund der uebrigen
  if (length(bad)) {
    hb <- hser[hser$station_id %in% bad, ]
    hk <- hom[hom$inhomogeneous, ]
    hk$lab <- sprintf("%s  %+.1f K, p = %.3f", hk$station_id, hk$shift_K, hk$p_perm)
    hb$lab <- factor(hk$lab[match(hb$station_id, hk$station_id)], levels = hk$lab)
    bg <- hser[!hser$station_id %in% bad, ]
    bg <- merge(bg, data.frame(lab = factor(hk$lab, levels = hk$lab)))
    seg <- do.call(rbind, lapply(seq_len(nrow(hk)), function(i) {
      s <- hser[hser$station_id == hk$station_id[i], ]; b <- hk$break_after[i]
      if (is.na(b)) return(NULL)
      data.frame(lab = hk$lab[i], x = c(min(s$winter), b + 0.5), xend = c(b + 0.5, max(s$winter)),
                 y = c(mean(s$D[s$winter <= b]), mean(s$D[s$winter > b])))
    }))
    seg$lab <- factor(seg$lab, levels = hk$lab)
    ph <- ggplot() +
      geom_line(data = bg, aes(winter, D, group = station_id), colour = "grey82", linewidth = 0.3) +
      geom_hline(yintercept = 0, linewidth = 0.25, colour = "grey45") +
      geom_segment(data = seg, aes(x = x, xend = xend, y = y, yend = y), colour = "#183a5a", linewidth = 0.6,
                   linetype = 2) +
      geom_line(data = hb, aes(winter, D), colour = "#c9584f", linewidth = 0.6) +
      geom_point(data = hb, aes(winter, D), colour = "#c9584f", size = 0.8) +
      facet_wrap(~ lab, ncol = 5) +
      scale_x_continuous(breaks = c(2014, 2020), labels = wlab) +
      coord_cartesian(ylim = c(-5.6, 3.4)) +
      labs(x = NULL, y = "Station minus regional median, winter mean (K)",
           subtitle = sprintf("Stations excluded for inhomogeneity (red; dashed: mean before/after the break). Grey: the %d stations that passed.",
                              nrow(hom) - length(bad))) +
      thm + theme(strip.text = element_text(size = 7), axis.text = element_text(size = 6.5),
                  plot.subtitle = element_text(size = 7.5))
    ggsave(file.path(OUT, "abbildungen", "fig_ff2_homogenitaet.png"), ph, width = 7.4,
           height = 1.5 + 1.45 * ceiling(length(bad) / 5), dpi = 300, bg = "white")
  }

  # Jackknife
  jp <- jk; jp$group <- factor(jp$group, levels = GROUPS)
  full <- bs; full$group <- factor(full$group, levels = GROUPS)
  pj <- ggplot(jp, aes(group, slope_med)) +
    geom_hline(yintercept = 0, linewidth = 0.3, colour = "grey40") +
    geom_jitter(width = 0.12, height = 0, size = 1, colour = "grey55") +
    geom_point(data = full, aes(group, slope_med), size = 2.2, colour = "black") +
    labs(x = NULL, y = "Median trend (days per decade)",
         subtitle = "Grey: one winter left out at a time (14 variants). Black: all winters.") +
    thm + theme(plot.subtitle = element_text(size = 7.5))
  ggsave(file.path(OUT, "abbildungen", "fig_ff2_jackknife.png"), pj, width = 5.6, height = 3.2, dpi = 300, bg = "white")

  # Abdeckung Route x Winter
  cv <- expand.grid(uid = routes$uid, winter = WINTERS, stringsAsFactors = FALSE)
  st_ok <- Vr[cbind(match(cv$uid, routes$uid), match(cv$winter, WINTERS))]
  cv_st <- routes$station_id[match(cv$uid, routes$uid)]
  cv$status <- ifelse(!st_ok, "no reliable station data",
               ifelse(cv_st %in% bad, "excluded: inhomogeneous station",
               ifelse(paste(cv$uid, cv$winter) %in% paste(rw$uid, rw$winter), "used for trends",
                      "station data ok, run missing")))
  cv$band <- factor(assign$band[match(cv$uid, assign$uid)], levels = BANDS)
  cv$uid <- factor(cv$uid, levels = routes$uid[order(routes$elev)])
  pcv <- ggplot(cv, aes(winter, uid, fill = status)) + geom_tile(colour = NA) +
    facet_grid(band ~ ., scales = "free_y", space = "free_y") +
    scale_fill_manual(values = c(`used for trends` = "#4f8fbd", `excluded: inhomogeneous station` = "#e3b3ad",
                                 `no reliable station data` = "grey88", `station data ok, run missing` = "#c9584f"),
                      name = NULL, drop = TRUE) +
    scale_x_continuous(breaks = WINTERS, labels = wlab, expand = c(0, 0)) +
    labs(x = NULL, y = "Routes (sorted by elevation)") + thm +
    theme(axis.text.y = element_blank(), axis.text.x = element_text(angle = 90, vjust = 0.5),
          legend.position = "bottom", strip.text.y = element_text(angle = 0))
  ggsave(file.path(OUT, "abbildungen", "fig_ff2_abdeckung.png"), pcv, width = 7.4, height = 7.5, dpi = 300, bg = "white")

  if (!is.null(chk)) {
    ck <- chk; ck$band <- factor(ck$band, levels = BANDS)
    rho <- suppressWarnings(stats::cor(ck$ice_days, ck$ice_days_pub, method = "spearman"))
    pck <- ggplot(ck, aes(ice_days_pub, ice_days, colour = band)) +
      geom_abline(slope = 1, intercept = 0, linewidth = 0.3, linetype = 2) +
      geom_point(size = 1.1, alpha = 0.8) + scale_colour_manual(values = BAND_COL, name = NULL) +
      coord_equal() + labs(x = "Ice days 2025/26, thesis run", y = "Ice days 2025/26, this run",
           subtitle = sprintf("n = %d, rho = %.2f, median difference %+.0f d", nrow(ck), rho, stats::median(ck$diff_days))) +
      thm + theme(legend.position = "bottom")
    ggsave(file.path(OUT, "abbildungen", "fig_ff2_check_2025.png"), pck, width = 3.8, height = 4.2, dpi = 300, bg = "white")
  }

  # ------------------------------------------------------------ Kennzahlen --
  f1 <- function(x, d = 1) formatC(x, format = "f", digits = d)
  hk <- hom[hom$inhomogeneous, ]
  excl <- do.call(rbind, lapply(BANDS, function(b) {
    u <- unique(rw_all[rw_all$band == b, c("uid", "station_id")])
    data.frame(band = b, all = nrow(u), excluded = sum(u$station_id %in% bad), kept = sum(!u$station_id %in% bad))
  }))
  K <- c(sprintf("FF2 Kennzahlen - %s", format(Sys.time(), "%Y-%m-%d %H:%M")),
    sprintf("Routen im Lauf: %d an %d Stationen, Winter %s bis %s",
            length(unique(rw_all$uid)), length(unique(rw_all$station_id)), wlab(min(WINTERS)), wlab(max(WINTERS))),
    "", sprintf("HOMOGENITAETSPRUEFUNG: %d von %d Stationen inhomogen (Sprung >= %.1f K bei p < %.2f oder Streuung > %.1f K)",
                length(bad), nrow(hom), HOMOG_SHIFT_K, HOMOG_P, HOMOG_SD_K),
    sprintf("  %-7s %-9s %-40s %6s %9s %8s %7s %6s", "Station", "Quelle", "Name", "Routen", "Bruch nach", "Sprung K", "p", "SD K"),
    if (nrow(hk)) sprintf("  %-7s %-9s %-40s %6d %9s %+8.2f %7.3f %6.2f", hk$station_id, hk$source, substr(hk$name, 1, 40),
                          hk$n_routes, wlab(hk$break_after), hk$shift_K, hk$p_perm, hk$sd_K),
    sprintf("  Uebrige %d Stationen: |Sprung| <= %.2f K. Alle GeoSphere-Stationen bestanden: %s",
            sum(!hom$inhomogeneous), max(abs(hom$shift_K[!hom$inhomogeneous])),
            if (all(!hom$inhomogeneous[hom$source != "LWD"])) "ja" else "nein"),
    "  Routen je Hoehenstufe (alle / ausgeschlossen / verwendet):",
    sprintf("    %-12s %4d %4d %4d", excl$band, excl$all, excl$excluded, excl$kept),
    "", sprintf("TREND (homogene Stationen, %d Routen, %d Stationen, %d Routen-Winter; Routen mit allen %d Wintern: %d)",
                nrow(tr), length(unique(tr$station_id)), nrow(rw), length(WINTERS), length(full_uids)),
    "  Median der Theil-Sen-Trends je Route, Tage/Dekade, 95%-KI Bootstrap ueber Stationen",
    sprintf("  %-12s %5s %5s %9s %9s %18s %8s %8s", "Gruppe", "Rout.", "Stat.", "Eistage", "Trend", "95%-KI", "neg.", "p<0.05"),
    sprintf("  %-12s %5d %5d %9s %9s %18s %7.0f%% %7.0f%%", bs$group, bs$n_routes, bs$n_stations,
            f1(bs$clim_days, 0), f1(bs$slope_med), paste0("[", f1(bs$ci_lo), ", ", f1(bs$ci_hi), "]"),
            100 * bs$share_neg, 100 * bs$share_sig),
    "", "  Zum Vergleich ohne Homogenitaetspruefung (alle Routen):",
    sprintf("  %-12s n = %3d   %+6.1f Tage/Dekade", bs_all$group, bs_all$n_routes, bs_all$slope_med),
    "", "TREND DER MEDIAN-ANOMALIE JE GRUPPE (14 Winter, Theil-Sen + Mann-Kendall)",
    sprintf("  %-12s %+6.1f Tage/Dekade   p = %.3f", an_tr$group, an_tr$slope_dec, an_tr$mk_p),
    "", sprintf("KONTROLLE feste Zusammensetzung (nur Routen mit allen %d Wintern)", length(WINTERS)),
    sprintf("  %-12s n = %3d   %+6.1f Tage/Dekade   p = %.3f", fc$group, fc$n_routes, fc$slope_dec, fc$mk_p),
    "", "JACKKNIFE (je ein Winter weggelassen): Spanne des Median-Trends, Tage/Dekade",
    sprintf("  %-12s %+6.1f bis %+6.1f   (schwaechster Wert ohne %s)   immer negativ: %s",
            jks$group, jks$min, jks$max, jks$min_without, ifelse(jks$all_negative, "ja", "nein")),
    "", "WINTER-RANGFOLGE (Median-Anomalie aller Routen, 1 = eisreichster)",
    sprintf("  %2d. %s  %+6.1f Tage (n = %d)", rank_tab$rank, wlab(rank_tab$winter), rank_tab$anom_med, rank_tab$n),
    "", "DATENQUALITAET JE WINTER (Median ueber Routen)",
    capture.output(print(qual, row.names = FALSE, digits = 3)))
  if (!is.null(chk)) K <- c(K, "", "KONTROLLE 2025/26 gegen bisherigen Lauf (Eistage je Route, alle Routen)",
    sprintf("  n = %d, Median-Differenz %+.1f Tage, mittlere abs. Differenz %.1f Tage, Spearman rho = %.3f",
            nrow(chk), stats::median(chk$diff_days), mean(abs(chk$diff_days)),
            suppressWarnings(stats::cor(chk$ice_days, chk$ice_days_pub, method = "spearman"))))
  writeLines(K, file.path(OUT, "kennzahlen.txt"), useBytes = TRUE)
  cat(paste(K, collapse = "\n"), "\n")
  say("Fertig. Abbildungen und Kennzahlen in ", OUT)
}

# ============================================================================
# FF2 - Schritt 1: Verfuegbarkeit der Stationstemperatur 2012/13 - 2025/26
# ----------------------------------------------------------------------------
# Prueft fuer jede Station, die einer der 303 Routen zugeordnet ist, und fuer
# die drei Inversionsstationen (Imst 38, Muttekopfhuette IMUT2, Vorderer
# Maldonkopf IMUT1), ob die Lufttemperatur in den 14 Wintern 2012/13 bis
# 2025/26 (1. Oktober - 30. April) belastbar vorliegt.
#
# Kriterien (angelehnt an Abschnitt 3.7 der Arbeit):
#   Stunde gueltig : LWD >= 3 von 6 Zehnminutenwerten, GeoSphere Stundenwert
#                    vorhanden; Wert zwischen -45 und +35 Grad C
#   Tag gueltig    : >= 18 gueltige Stunden und keine eingefrorene Reihe
#                    (Standardabweichung der Stundenwerte > 0.01 K)
#   Winter gueltig : >= 190 gueltige Tage zwischen 1.10. und 30.4.
#
# AUSFUEHREN:  in RStudio oeffnen und oben rechts auf "Source" klicken
#              (oder im Terminal:  Rscript 01_stationscheck.R)
# Nur Base-R, keine Pakete noetig. Laufzeit ca. 10-20 min (ca. 700 Downloads).
# Abgebrochene Laeufe koennen einfach neu gestartet werden - bereits geladene
# Stationen liegen in cache/ und werden nicht erneut heruntergeladen.
# Die Stundenreihen in cache/ verwendet das Skript fuer Schritt 2 weiter.
# ============================================================================

WINTERS    <- 2012:2025          # Startjahr des Winters (2012 = 2012/13)
MIN_HOURS  <- 18                 # gueltige Stunden je Tag
MIN_DAYS   <- 190                # gueltige Tage je Winter (von 212)
T_RANGE    <- c(-45, 35)         # plausibler Wertebereich in Grad C
INV_STATIONS <- data.frame(station_id = c("38", "IMUT2", "IMUT1"),
                           source     = c("GeoSphere", "LWD", "LWD"),
                           station_name = c("Imst (Inversion T0)",
                                            "Muttekopfhuette (Inversion T1)",
                                            "Vorderer Maldonkopf (Inversion T2)"),
                           stringsAsFactors = FALSE)

# ---------------------------------------------------------------- Pfade -----
get_script_dir <- function() {
  for (i in rev(seq_len(sys.nframe()))) {          # per source() / RStudio "Source"
    of <- sys.frame(i)$ofile
    if (!is.null(of)) return(dirname(normalizePath(of)))
  }
  a <- commandArgs(trailingOnly = FALSE)           # per Rscript
  f <- sub("^--file=", "", a[grep("^--file=", a)])
  if (length(f)) return(dirname(normalizePath(f)))
  getwd()
}
BASE   <- get_script_dir()
ASSIGN <- file.path(BASE, "..", "Ice fall modeling", "GutHub", "ice-waterfalls",
                    "data", "AWS", "icefalls_nearest_station.csv")
if (!file.exists(ASSIGN)) {
  stop("Stationszuordnung nicht gefunden:\n  ", normalizePath(ASSIGN, mustWork = FALSE),
       "\nBitte das Skript aus dem Ordner FF2_Stationen heraus starten ",
       "(RStudio: 'Source' oder Session > Set Working Directory > To Source File Location).")
}
CACHE <- file.path(BASE, "cache");    dir.create(CACHE, showWarnings = FALSE)
OUT   <- file.path(BASE, "ergebnis"); dir.create(OUT,   showWarnings = FALSE)

# ------------------------------------------------------------ Download ------
fetch <- function(url, headers = NULL, tries = 4) {
  tmp <- tempfile(fileext = ".csv")
  for (k in seq_len(tries)) {
    r <- tryCatch(
      if (is.null(headers)) download.file(url, tmp, method = "libcurl", quiet = TRUE, mode = "wb")
      else download.file(url, tmp, method = "libcurl", quiet = TRUE, mode = "wb", headers = headers),
      error = function(e) e, warning = function(w) w)
    if (identical(r, 0L)) return(tmp)
    msg <- if (inherits(r, "condition")) conditionMessage(r) else ""
    if (grepl("404", msg)) return(NULL)                          # Datei existiert nicht
    if (grepl("429", msg)) { message("      Rate-Limit - warte 60 s"); Sys.sleep(60); next }
    if (grepl("400|422", msg)) return(NULL)
    Sys.sleep(3 * k)
  }
  NULL
}

# LWD Tirol: eine CSV-Datei je Station, Parameter und Saison, 10-min, MEZ (+01:00)
lwd_season <- function(code, y) {
  url <- sprintf("https://wiski.tirol.gv.at/lawine/produkte/ogd/%s/%s_LT_%d_%d.csv",
                 code, code, y, y + 1)
  f <- fetch(url, headers = c(Referer = "https://wiski.tirol.gv.at/",
                              Accept  = "text/csv,text/plain,*/*"))
  if (is.null(f)) return(NULL)
  x <- readLines(f, warn = FALSE, encoding = "latin1"); unlink(f)
  x <- x[grepl("^[0-9]{2}\\.[0-9]{2}\\.[0-9]{4} [0-9]{2}:[0-9]{2}", x)]
  if (!length(x)) return(NULL)
  p  <- strsplit(x, ";", fixed = TRUE)
  ts <- vapply(p, `[`, "", 1)
  v  <- vapply(p, function(z) if (length(z) >= 2) z[2] else NA_character_, "")
  v[v %in% c("---", "")] <- NA
  data.frame(time  = as.POSIXct(ts, format = "%d.%m.%Y %H:%M", tz = "Etc/GMT-1"),
             value = suppressWarnings(as.numeric(gsub(",", ".", v, fixed = TRUE))))
}

# 10-min -> Stunde (UTC), gueltig ab 3 von 6 Werten
to_hourly <- function(df, min_n = 3) {
  df <- df[!is.na(df$time) & !is.na(df$value) &
           df$value > T_RANGE[1] & df$value < T_RANGE[2], ]
  if (!nrow(df)) return(NULL)
  h <- format(df$time, "%Y-%m-%d %H:00:00", tz = "UTC")
  n <- tapply(df$value, h, length)
  m <- tapply(df$value, h, mean)
  keep <- n >= min_n
  data.frame(hour = as.POSIXct(names(m)[keep], tz = "UTC"), tl = as.numeric(m[keep]))
}

# GeoSphere: Stundendatensatz klima-v2-1h, Fallback klima-v2-10min je Winter
geo_request <- function(dataset, id, start, end) {
  for (par in c("tl", "TL")) {
    url <- paste0("https://dataset.api.hub.geosphere.at/v1/station/historical/", dataset,
                  "?parameters=", par, "&station_ids=", id,
                  "&start=", start, "&end=", end, "&output_format=csv")
    f <- fetch(url)
    if (is.null(f)) next
    d <- tryCatch(read.csv(f, stringsAsFactors = FALSE), error = function(e) NULL); unlink(f)
    col <- if (!is.null(d)) intersect(c("tl", "TL"), names(d))[1] else NA
    if (is.null(d) || !nrow(d) || is.na(col)) next
    return(data.frame(time  = as.POSIXct(substr(d$time, 1, 16), format = "%Y-%m-%dT%H:%M", tz = "UTC"),
                      value = suppressWarnings(as.numeric(d[[col]]))))
  }
  NULL
}
geo_hourly <- function(id) {
  # 1) ganzer Zeitraum in Bloecken zu je 4 Wintern (Stundendaten)
  blocks <- split(WINTERS, ceiling(seq_along(WINTERS) / 4))
  parts <- lapply(blocks, function(b)
    geo_request("klima-v2-1h", id, sprintf("%d-10-01T00:00", min(b)),
                sprintf("%d-04-30T23:00", max(b) + 1)))
  d <- do.call(rbind, parts)
  if (!is.null(d) && nrow(d)) {
    d <- d[!is.na(d$time) & !is.na(d$value) & d$value > T_RANGE[1] & d$value < T_RANGE[2], ]
    if (nrow(d)) return(data.frame(hour = d$time, tl = d$value))
  }
  # 2) Fallback: Zehnminutenwerte je Winter
  message("      klima-v2-1h leer - versuche klima-v2-10min")
  parts <- lapply(WINTERS, function(y)
    geo_request("klima-v2-10min", id, sprintf("%d-10-01T00:00", y), sprintf("%d-04-30T23:50", y + 1)))
  d <- do.call(rbind, parts)
  if (is.null(d) || !nrow(d)) return(NULL)
  to_hourly(d)
}

get_station <- function(src, id) {
  cf <- file.path(CACHE, sprintf("%s_%s.rds", if (src == "LWD") "LWD" else "GEO", id))
  if (file.exists(cf)) return(readRDS(cf))
  h <- if (src == "LWD") {
    parts <- lapply(WINTERS, function(y) { Sys.sleep(0.3); lwd_season(id, y) })
    d <- do.call(rbind, parts)
    if (is.null(d)) NULL else to_hourly(d)
  } else geo_hourly(id)
  if (is.null(h)) h <- data.frame(hour = as.POSIXct(character(0), tz = "UTC"), tl = numeric(0))
  h <- h[!duplicated(h$hour), ]
  h <- h[order(h$hour), ]
  saveRDS(h, cf)
  h
}

# --------------------------------------------------------- Abdeckung --------
winter_days <- function(h) {
  if (!nrow(h)) return(setNames(rep(0L, length(WINTERS)), WINTERS))
  d  <- as.Date(format(h$hour, "%Y-%m-%d", tz = "Etc/GMT-1"))      # Tagesgrenze MEZ
  nh <- tapply(h$tl, d, length)
  sd <- tapply(h$tl, d, sd)
  ok <- as.Date(names(nh))[nh >= MIN_HOURS & !is.na(sd) & sd > 0.01]
  sapply(WINTERS, function(y)
    sum(ok >= as.Date(sprintf("%d-10-01", y)) & ok <= as.Date(sprintf("%d-04-30", y + 1))))
}

# ------------------------------------------------------------- Ablauf -------
assign <- read.csv(ASSIGN, stringsAsFactors = FALSE, encoding = "UTF-8",
                   colClasses = c(uid = "character", station_id = "character"))
assign$elev <- as.numeric(assign$icefall_elev_m)
assign$band <- cut(assign$elev, c(-Inf, 1500, 2000, 2500, Inf),
                   labels = c("<1500 m", "1500-2000 m", "2000-2500 m", ">2500 m"), right = FALSE)

st <- unique(assign[, c("station_id", "source", "station_name")])
st$n_routes <- as.integer(table(assign$station_id)[st$station_id])
inv <- INV_STATIONS[!INV_STATIONS$station_id %in% st$station_id, ]
if (nrow(inv)) st <- rbind(st, cbind(inv, n_routes = 0L))
st <- st[order(-st$n_routes), ]

message(sprintf("Pruefe %d Stationen (%d LWD, %d GeoSphere) fuer %d Winter ...",
                nrow(st), sum(st$source == "LWD"), sum(st$source != "LWD"), length(WINTERS)))
cov <- matrix(0L, nrow(st), length(WINTERS), dimnames = list(st$station_id, paste0("w", WINTERS)))
for (i in seq_len(nrow(st))) {
  message(sprintf("[%2d/%2d] %-9s %-6s %s", i, nrow(st), st$source[i], st$station_id[i],
                  st$station_name[i]))
  h <- tryCatch(get_station(st$source[i], st$station_id[i]),
                error = function(e) { message("      FEHLER: ", conditionMessage(e)); NULL })
  if (!is.null(h)) cov[i, ] <- winter_days(h)
}

valid <- cov >= MIN_DAYS
st$n_valid_winters <- rowSums(valid)
st$first_valid     <- apply(valid, 1, function(v) if (any(v)) paste0(WINTERS[which(v)[1]], "/", substr(WINTERS[which(v)[1]] + 1, 3, 4)) else "-")
st$missing         <- apply(valid, 1, function(v) if (all(v)) "" else paste(paste0(WINTERS[!v], "/", substr(WINTERS[!v] + 1, 3, 4)), collapse = " "))
write.csv(cbind(st, cov), file.path(OUT, "stationen_abdeckung.csv"), row.names = FALSE)

assign$n_valid_winters <- st$n_valid_winters[match(assign$station_id, st$station_id)]
assign$missing         <- st$missing[match(assign$station_id, st$station_id)]
assign$n_valid_winters[is.na(assign$n_valid_winters)] <- 0L
write.csv(assign[, c("uid", "icefall_name", "elev", "band", "station_id", "source",
                     "station_name", "n_valid_winters", "missing")],
          file.path(OUT, "routen_abdeckung.csv"), row.names = FALSE)

# ------------------------------------------------------ Zusammenfassung -----
options(width = 250)
n <- length(WINTERS)
tab <- data.frame(
  Hoehenstufe       = levels(assign$band),
  Routen_gesamt     = as.integer(table(assign$band)),
  alle_14_Winter    = as.integer(tapply(assign$n_valid_winters == n, assign$band, sum)),
  mind_13_Winter    = as.integer(tapply(assign$n_valid_winters >= n - 1, assign$band, sum)),
  mind_12_Winter    = as.integer(tapply(assign$n_valid_winters >= n - 2, assign$band, sum)),
  mind_10_Winter    = as.integer(tapply(assign$n_valid_winters >= n - 4, assign$band, sum)))
tab <- rbind(tab, data.frame(Hoehenstufe = "Summe", t(colSums(tab[, -1]))))

lines <- c(
  sprintf("FF2 Stationscheck - %s", format(Sys.time(), "%Y-%m-%d %H:%M")),
  sprintf("Kriterien: Tag >= %d gueltige Stunden, Winter >= %d gueltige Tage (1.10.-30.4.)", MIN_HOURS, MIN_DAYS),
  "", "ROUTEN JE HOEHENSTUFE", capture.output(print(tab, row.names = FALSE)),
  "", "INVERSIONSSTATIONEN",
  capture.output(print(st[st$station_id %in% INV_STATIONS$station_id,
                          c("station_id", "station_name", "n_valid_winters", "first_valid", "missing")],
                       row.names = FALSE)),
  "", "STATIONEN MIT FEHLENDEN WINTERN (nach Anzahl betroffener Routen)",
  capture.output(print(st[st$n_valid_winters < n & st$n_routes > 0,
                          c("source", "station_id", "station_name", "n_routes",
                            "n_valid_winters", "first_valid", "missing")], row.names = FALSE)))
writeLines(lines, file.path(OUT, "zusammenfassung.txt"), useBytes = TRUE)
cat(paste(lines, collapse = "\n"), "\n")
message("\nFertig. Ergebnisse in: ", normalizePath(OUT))

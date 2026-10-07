# Lange Stationsreihen fuer Abschnitt 3.6:
# Laedt Tagesmitteltemperaturen (GeoSphere klima-v2-1d, tl_mittel) fuer
#   Brenner (id 16, ab 1948)  -> Eisfall Amphitrite (UID 54, 0.97 km, dz 22 m)
#   Umhausen (id 136, ab 1936)
#   Obergurgl (id 66, ab 1953)
# und berechnet pro Winter (1. Okt - 30. Apr) die Kennzahlen des
# saettigenden Temperatur-Proxys (gleiche Koeffizienten wie das Modell).
#
# Ausfuehren:  source(".../Diagramm_Skripte/3_7_und_3_8_.../get_longrec_winters.R")
#              oder in RStudio "Source" (Internet noetig, ~1 Minute)
# Ergebnis:    Diagramm_Skripte/_zwischendaten/longrec_winters.csv

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

stations <- list(
  list(id = 16,  name = "Brenner",   start = "1948-01-01"),
  list(id = 136, name = "Umhausen",  start = "1936-01-01"),
  list(id = 66,  name = "Obergurgl", start = "1953-01-01")
)

H0 <- 0.20; HMAX <- 0.90; LAM <- 0.15
DEN <- 1 - exp(-HMAX / LAM)

out <- list()
for (st in stations) {
  url <- paste0(
    "https://dataset.api.hub.geosphere.at/v1/station/historical/klima-v2-1d",
    "?parameters=tl_mittel&station_ids=", st$id,
    "&start=", st$start, "&end=2026-06-30&output_format=csv")
  message("Lade ", st$name, " ...")
  df <- read.csv(url)
  df$date <- as.Date(substr(df$time, 1, 10))
  df$T <- suppressWarnings(as.numeric(df$tl_mittel))

  # Winterfenster zuordnen (winter_start = Jahr des Oktobers)
  m <- as.integer(format(df$date, "%m"))
  y <- as.integer(format(df$date, "%Y"))
  df$winter <- ifelse(m >= 10, y, ifelse(m <= 4, y - 1, NA))
  df <- df[!is.na(df$winter), ]

  for (w in sort(unique(df$winter))) {
    sub <- df[df$winter == w, ]
    sub <- sub[order(sub$date), ]
    Tv <- sub$T
    ok <- !is.na(Tv)
    n_days <- sum(ok)
    if (n_days < 190) next
    fdd <- sum(pmax(0, -Tv[ok]))
    pdd <- sum(pmax(0,  Tv[ok]))
    djf <- sub$T[as.integer(format(sub$date, "%m")) %in% c(12, 1, 2)]
    t_djf <- mean(djf, na.rm = TRUE)

    H <- 0; good <- 0; peak <- 0
    for (Ti in Tv) {
      if (is.na(Ti)) next
      growth <- 0.50 * max(0, -Ti) * 24 / 1000
      melt   <- 0.60 * max(0,  Ti) * 24 / 1000
      iso <- exp(-H / H0)
      capf <- (1 - exp(-max(0, HMAX - H) / LAM)) / DEN
      H <- max(0, H + growth * iso * capf - melt)
      if (H >= 0.15) good <- good + 1
      peak <- max(peak, H)
    }
    out[[length(out) + 1]] <- data.frame(
      station_id = st$id, station_name = st$name, winter_start = w,
      n_days = n_days, fdd = round(fdd, 1), pdd = round(pdd, 1),
      t_djf = round(t_djf, 2), good_days = good, peak_m = round(peak, 3))
  }
}

res <- do.call(rbind, out)
res <- res[res$winter_start <= 2025, ]
ziel <- file.path("Diagramm_Skripte", "_zwischendaten", "longrec_winters.csv")
dir.create(dirname(ziel), showWarnings = FALSE)
write.csv(res, ziel, row.names = FALSE)
message("Fertig: ", ziel, "  (", nrow(res), " Winter)")
print(aggregate(winter_start ~ station_name, res,
                function(x) paste0(min(x), "-", max(x), " (n=", length(x), ")")))

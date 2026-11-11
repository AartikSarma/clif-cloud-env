# clifkit helpers for R steps. The runner (`uv run run.py`) sets CLIFKIT_* environment
# variables, so R steps get exactly the same settings as Python steps.

clifkit_context <- function() {
  vars <- c(
    project = "CLIFKIT_PROJECT", site = "CLIFKIT_SITE", clif_version = "CLIFKIT_CLIF_VERSION",
    data_dir = "CLIFKIT_DATA_DIR", filetype = "CLIFKIT_FILETYPE", timezone = "CLIFKIT_TIMEZONE",
    local_dir = "CLIFKIT_LOCAL_DIR", staging_dir = "CLIFKIT_STAGING_DIR"
  )
  values <- Sys.getenv(vars)
  missing <- vars[!nzchar(values)]
  if (length(missing) > 0) {
    stop("Run this step through the project runner (`uv run run.py`); missing: ",
         paste(missing, collapse = ", "), call. = FALSE)
  }
  as.list(stats::setNames(values, names(vars)))
}

# Path to a CLIF table, e.g. clifkit_table_path(ctx, "hospitalization")
clifkit_table_path <- function(ctx, table) {
  p <- file.path(ctx$data_dir, paste0("clif_", table, ".", ctx$filetype))
  if (!file.exists(p)) stop("CLIF table '", table, "' not found at ", p, call. = FALSE)
  p
}

# A file in local_only_phi (row-level / PHI outputs; never uploaded)
clifkit_local_path <- function(ctx, name) file.path(ctx$local_dir, name)

# Stage an aggregate data frame for upload. It only reaches upload_no_phi if it
# passes the release check (counts 1-9 become "<10"; ID/date columns block release).
clifkit_save_shareable <- function(ctx, df, name) {
  if (!grepl("\\.csv$", name)) name <- paste0(name, ".csv")
  path <- file.path(ctx$staging_dir, name)
  utils::write.csv(df, path, row.names = FALSE, fileEncoding = "UTF-8", na = "")
  invisible(path)
}

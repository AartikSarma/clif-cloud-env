# Step 2 (R): discharge category by IMV status, on the CLIF 3.0 vocabulary.
# Reads the row-level cohort from step 1 (local_only_phi) and stages an aggregate table.

source(file.path("R", "clifkit.R"))
suppressPackageStartupMessages(library(dplyr))

ctx <- clifkit_context()

# CLIF 2.1 discharge_category -> CLIF 3.0 discharge_category (explicit, version-scoped).
# Check against the mCIDE for your site's data before relying on it.
discharge_2_1_to_3_0 <- c(
  "Home" = "home",
  "Skilled Nursing Facility (SNF)" = "snf",
  "Expired" = "expired",
  "Acute Inpatient Rehab Facility" = "acute_ip_rehab",
  "Assisted Living" = "assisted_living",
  "Other" = "other",
  "Long Term Care Hospital (LTACH)" = "ltach",
  "Hospice" = "hospice",
  "Acute Care Hospital" = "acute_care_hosp",
  "Against Medical Advice (AMA)" = "ama",
  "Group Home" = "group_home",
  "Chemical Dependency" = "chemical_dependency",
  "Shelter" = "shelter",
  "Psychiatric Hospital" = "mental_health_hosp",
  "Jail" = "jail"
)

cohort <- arrow::read_parquet(clifkit_local_path(ctx, "cohort.parquet"))
source_value <- trimws(as.character(cohort$discharge_category))
cohort$discharge_category_3_0 <- if (ctx$clif_version == "2.1") {
  unname(discharge_2_1_to_3_0[source_value])
} else {
  source_value
}

# Keep unmapped values visible instead of dropping them.
unmapped <- is.na(cohort$discharge_category_3_0) & !is.na(source_value)
if (any(unmapped)) {
  message("Unmapped discharge_category values: ", paste(unique(source_value[unmapped]), collapse = ", "))
  cohort$discharge_category_3_0[unmapped] <- "unmapped"
}

table <- cohort |>
  mutate(imv = if_else(imv, "imv", "no_imv")) |>
  count(imv, discharge_category = discharge_category_3_0, name = "n") |>
  arrange(imv, desc(n))

clifkit_save_shareable(ctx, table, "discharge_by_imv")
cat(nrow(table), "rows in discharge_by_imv\n")

"""Step 1 (Python): flag hospitalizations with invasive mechanical ventilation (IMV).

Writes the row-level cohort to local_only_phi and an aggregate table for upload.
"""

import pandas as pd

import clifkit

ctx = clifkit.context()

# device_category vocabulary differs by CLIF version: 2.1 "IMV", 3.0 "imv".
IMV = {"2.1": "IMV", "3.0": "imv"}[ctx.clif_version]

hosp = pd.read_parquet(
    ctx.table_path("hospitalization"),
    columns=["hospitalization_id", "age_at_admission", "discharge_category"],
)
resp = pd.read_parquet(ctx.table_path("respiratory_support"), columns=["hospitalization_id", "device_category"])

# Compare on a normalized key (case/whitespace) but keep the source values untouched.
device_key = resp["device_category"].astype("string").str.strip().str.casefold()
if device_key.isna().all():
    raise SystemExit("respiratory_support.device_category is empty; check the data folder and CLIF version")
imv_ids = set(resp.loc[device_key == IMV.casefold(), "hospitalization_id"])

cohort = hosp.assign(imv=hosp["hospitalization_id"].isin(imv_ids))
cohort["age_group"] = pd.cut(
    cohort["age_at_admission"],
    bins=[-1, 17, 39, 59, 79, 200],
    labels=["<18", "18-39", "40-59", "60-79", "80+"],
)
cohort.to_parquet(ctx.local_path("cohort.parquet"), index=False)  # row-level: never uploaded

table = (
    cohort.groupby("age_group", observed=False)
    .agg(n_hospitalizations=("hospitalization_id", "size"), n_imv=("imv", "sum"))
    .reset_index()
)
table["pct_imv"] = (100 * table["n_imv"] / table["n_hospitalizations"]).round(1)
ctx.save_shareable(table, "imv_by_age_group")

print(f"{len(cohort)} hospitalizations, {int(cohort['imv'].sum())} with IMV (CLIF {ctx.clif_version})")

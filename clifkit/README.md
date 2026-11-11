# clifkit

Site config, PHI-safe output folders and a one-command runner for CLIF analyses in
Python and R.

- **One config per machine, none per project.** `clifkit init-site` writes
  `~/.config/clif/site.toml` (Windows: `%APPDATA%\clif\site.toml`) with the site name,
  CLIF version, data folder (a remote share is fine), timezone and output root.
  `CLIF_SITE`, `CLIF_VERSION`, `CLIF_DATA_DIR`, `CLIF_TIMEZONE` and `CLIF_OUTPUT_ROOT`
  override it.
- **Outputs always outside the repo**, in
  `<output_root>/<project>/upload_no_phi/` and `<output_root>/<project>/local_only_phi/`.
  clifkit refuses to run if the output folder is inside the repo or the data folder.
- **One command:** `uv run run.py` runs the steps listed in `pyproject.toml`
  (`.py` and `.R`, with R via `uvr`), then the release check.
- **The release check is the only way into `upload_no_phi`.** Steps stage shareable
  files; the check:
  - fails the release on identifier/name/date columns, date-like values, tables
    without a count column, or row-level formats (parquet, rds, ...)
  - replaces counts of 1-9 with `<10` and blanks percent/proportion columns in those rows
  - marks figures and text as needing human review
  - rebuilds `upload_no_phi` from scratch with a `manifest.json` (site, CLIF version,
    git commit, lockfile hashes, file checksums, suppression counts)

  It does **not** catch complementary suppression (a total that lets a suppressed cell
  be recalculated) or what a figure shows. Review before uploading.

## In a step

```python
import clifkit
ctx = clifkit.context()
hosp = pd.read_parquet(ctx.table_path("hospitalization"))
cohort.to_parquet(ctx.local_path("cohort.parquet"))      # row-level: stays local
ctx.save_shareable(counts, "imv_by_age")                  # aggregate: checked, then uploaded
```

R steps read the same settings from `CLIFKIT_*` environment variables (see the
template's `R/clifkit.R`).

## Commands

```bash
clifkit init-site --site ucmc --clif-version 3.0 --data-dir /mnt/clif --timezone US/Central
clifkit show                    # resolved settings and output folders
clifkit run                     # what run.py calls
clifkit run --synthetic 2.1     # use $CLIF_SYNTH_DATA_V2_1 instead of the site data
```

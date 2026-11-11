# CLIF analysis template

A CLIF project that runs with `git clone` and one command, in Python and R, with
outputs kept outside the repo and split into what can and can't leave the site.

```bash
git clone <this repo> && cd <this repo>
uv run run.py
```

That installs the locked Python packages (uv) and R packages (uvr), runs every step in
`pyproject.toml`'s `[tool.clifkit] steps`, and runs the release check.

## One-time setup per machine

1. Install [uv](https://docs.astral.sh/uv/) and [uvr](https://github.com/nbafrank/uvr),
   then R with `uvr r install 4.5.2`.
2. Tell clifkit where this site's CLIF data is. This writes `~/.config/clif/site.toml`
   (Windows: `%APPDATA%\clif\site.toml`), shared by every project:
   ```bash
   uvx --from "git+https://github.com/AartikSarma/clif-cloud-env@clifkit#subdirectory=clifkit" clifkit init-site --site mysite --clif-version 3.0 --data-dir /path/to/clif --timezone US/Central --claude-deny
   ```
   `--claude-deny` also stops Claude Code's file tools from reading the data folder and
   every `local_only_phi` folder. It doesn't stop a script that Claude runs from opening
   them, so never run an agent session against real data.

## Where outputs go

```
~/CLIF_output/<project>/
  upload_no_phi/      checked aggregate tables + manifest.json: safe to share after review
  local_only_phi/     row-level and intermediate files: never leaves the site
```

Runs on synthetic data go to `<project>__synthetic_v3.0/` (or `_v2.1`), so they never
mix with real results.

## Writing steps

- **Python:** `ctx = clifkit.context()`; read tables with `ctx.table_path("vitals")`;
  write row-level files with `ctx.local_path(...)`; stage shareable tables with
  `ctx.save_shareable(df, "name")`.
- **R:** `source(file.path("R", "clifkit.R"))`; then `clifkit_context()`,
  `clifkit_table_path()`, `clifkit_local_path()` and `clifkit_save_shareable()`.
- **Shareable tables** need a count column named `n`, `n_*`, `*_n` or `count*`. The
  release check replaces 1-9 with `<10`, blanks percent/proportion columns in those rows,
  and blocks the whole release if any table has identifier, name or date columns, or if
  a row-level file (parquet, rds, ...) is staged. Figures are released but flagged for
  review. Check complementary suppression yourself: a total that lets a suppressed cell
  be recalculated is not caught.
- **Both CLIF versions:** read the version from `ctx.clif_version` and map categories
  explicitly, as the example steps do. Test with:
  ```bash
  uv run run.py --synthetic 3.0
  uv run run.py --synthetic 2.1
  ```
  (needs `CLIF_SYNTH_DATA_V3_0` / `CLIF_SYNTH_DATA_V2_1`, set in the CLIF cloud environment).

## The example

- `analysis/01_cohort.py` (Python) flags hospitalizations with invasive mechanical
  ventilation and stages IMV counts by age group.
- `analysis/02_discharge.R` (R) maps 2.1 discharge categories to the 3.0 vocabulary and
  stages discharge category by IMV status.

Both versions of the synthetic data produce identical shareable tables.

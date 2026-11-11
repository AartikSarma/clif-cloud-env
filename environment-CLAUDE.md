# CLIF research defaults
- Python: use uv for everything (uv init, uv add, uv run). Never pip install.
- clifpy: in a uv project, `uv add clifpy "polars<2"` (clifpy 2.1 breaks on polars 2.x).
  For quick scripts outside a project, use /opt/clif/venv/bin/python (clifpy preinstalled).
- R: use uvr (uvr init, uvr add, uvr sync, uvr run). Never install.packages().
- Synthetic CLIF data (no PHI, 10k hospitalizations, clif_*.parquet), one dir per version:
  CLIF 3.0: $CLIF_SYNTH_DATA_V3_0 (36 tables; lowercase codes, e.g. imv, hfnc)
  CLIF 2.1: $CLIF_SYNTH_DATA_V2_1 (28 tables; mixed case, e.g. IMV, High Flow NC)
  $CLIF_SYNTH_DATA points at the 3.0 data. Test every script against both.
- clifpy reads both: pass clif_version="3.0" or "2.1" to from_file().
- Never use real patient data in this environment.

## CLIF version tolerance (default for all scripts)
- Unless the user or project declares otherwise, the declared target is BOTH
  CLIF 2.1 and 3.0. Treat this as the version answer the clif-icu skill asks for.
- Take the data version from an explicit setting (config/CLI arg, e.g.
  clif_version = "2.1" | "3.0"); never infer it from value casing.
- Map categories through explicit, version-scoped lookups built from each
  version's mCIDE (e.g. 2.1 "High Flow NC" -> 3.0 "hfnc"), not blanket
  lowercasing. Normalize comparison keys (case/whitespace) consistently,
  keep source values, and report unknown categories instead of dropping them.
- Handle table/column renames between versions with an explicit rename map.
  If a feature exists in only one version, guard it and fail with a clear message.
- Report which versions were actually executed vs. only reviewed.

## Cross-platform (Windows, macOS, Linux)
- Paths: pathlib (Python) / file.path() (R); no hard-coded separators,
  drive letters or absolute paths; data dir comes from config or env var.
- Entry points are Python/R (`uv run ...`, `uvr run ...`), not bash-only.
  Document commands for both bash/zsh and PowerShell when they differ.
- Read/write text with explicit UTF-8; set timezones explicitly; match
  filename case exactly; no shell-specific tools inside scripts.
- Parallelism: guard Python multiprocessing with if __name__ == "__main__";
  in R avoid fork-only workers (use PSOCK / future::multisession).
- This environment is Linux only: report Windows/macOS as reviewed, not tested,
  unless they were actually run there.

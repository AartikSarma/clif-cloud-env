# CLIF project conventions
- Python: use uv (uv add, uv run). Never pip install. clifpy: `uv add clifpy "polars<2"`.
- R: use uvr (uvr add, uvr sync, uvr run). Never install.packages().
- Develop against synthetic CLIF data only; never real patient data in an agent session.

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
- Report an OS as tested only if scripts actually ran there; otherwise say "reviewed".

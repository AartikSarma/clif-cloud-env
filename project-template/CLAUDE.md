# CLIF project conventions
- Python: use uv (uv add, uv run). Never pip install. clifpy: `uv add clifpy "polars<2"`.
- R: use uvr (uvr add, uvr sync, uvr run). Never install.packages().
- Develop against synthetic CLIF data only; never real patient data in an agent session.
- Synthetic data: the synthetic_clif release has a 10k-hospitalization dataset per version
  (https://github.com/Common-Longitudinal-ICU-data-Format/synthetic_clif/releases):
  CLIF 3.0 in synth_clif_10k.tar.gz (36 tables; lowercase codes, e.g. imv, hfnc),
  CLIF 2.1 in synth_clif_10k_clif2.1.tar.gz (28 tables; mixed case, e.g. IMV, High Flow NC).
  Read the folders from CLIF_SYNTH_DATA_V3_0 / CLIF_SYNTH_DATA_V2_1 (set in the CLIF cloud
  environment; set them yourself elsewhere). Never hard-code the paths.
- Test every script against both datasets. clifpy reads either: from_file(..., clif_version="3.0" or "2.1").

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

## Data zones (see SOP.md)
- Get every path from `config/config.json` through `utils/clif_paths` (`load_config()`
  in Python, `source(file.path("utils", "clif_paths.R"))` in R). Never hard-code a path.
- Read core CLIF tables in place from `data_directory`; never copy, subset-and-save or
  write anything into it.
- Never write data into the repo. Intermediates go through `write_intermediate()` to
  `intermediate_directory`; results go through `write_result()` to `results_directory`.
  Both default to `../clif_workspace/<repo>/`, outside the repo.
- Keep PHI out of intermediates: compute in memory, then write offsets from an index
  time (`to_offsets()`), not dates; drop geography and identifiers; top-code age at 90
  (`top_code_age()`). Don't pass `allow=` to get past the check unless the user agrees,
  and record the reason in the README.
- Don't call `release_result()` or add files to `output/final_no_phi/`; release is a
  human step after review.
- Call `write_manifest()` at the end of every analysis entry point.

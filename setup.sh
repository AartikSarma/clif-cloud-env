#!/bin/bash
set -euo pipefail

# 1. Synthetic CLIF data (10k hospitalizations, parquet) -> /opt/clif
mkdir -p /opt/clif
if [ ! -d /opt/clif/synthetic_clif ]; then
  git clone --depth 1 -q https://github.com/Common-Longitudinal-ICU-data-Format/synthetic_clif /opt/clif/synthetic_clif
fi

# 2. uvr (R package manager), pinned version, checksum-verified installer
curl -fsSL https://raw.githubusercontent.com/nbafrank/uvr/main/install.sh -o /tmp/uvr_install.sh
UVR_VERSION=v0.4.8 UVR_INSTALL_DIR=/usr/local/bin sh /tmp/uvr_install.sh
uvr r list 2>/dev/null | grep -q 4.5.2 || uvr r install 4.5.2 --unattended

# 2b. clifpy in a shared venv (also warms the uv cache for per-project installs)
if [ ! -x /opt/clif/venv/bin/python ]; then
  uv venv -q /opt/clif/venv --python 3.12
fi
uv pip install -q --python /opt/clif/venv/bin/python clifpy "polars<2"

# 3. CLIF skills plugin (marketplace + enable), merged into user settings
mkdir -p "$HOME/.claude"
python3 -I - "$HOME/.claude/settings.json" <<'EOF'
import json, pathlib, sys
p = pathlib.Path(sys.argv[1])
s = json.loads(p.read_text()) if p.exists() else {}
s.setdefault('extraKnownMarketplaces', {})['clif-skills'] = {'source': {'source': 'github', 'repo': 'Common-Longitudinal-ICU-data-Format/skills'}}
s.setdefault('enabledPlugins', {})['clif-icu@clif-skills'] = True
p.write_text(json.dumps(s, indent=2))
EOF

# 4. Default tooling conventions for every session
if ! grep -q "CLIF research defaults" "$HOME/.claude/CLAUDE.md" 2>/dev/null; then
cat >> "$HOME/.claude/CLAUDE.md" <<'EOF'
# CLIF research defaults
- Python: use uv for everything (uv init, uv add, uv run). Never pip install.
- clifpy: in a uv project, `uv add clifpy "polars<2"` (clifpy 2.1 breaks on polars 2.x).
  For quick scripts outside a project, use /opt/clif/venv/bin/python (clifpy preinstalled).
- R: use uvr (uvr init, uvr add, uvr sync, uvr run). Never install.packages().
- Synthetic CLIF data (no PHI) is at $CLIF_SYNTH_DATA (clif_*.parquet).
  That bundled 10k dataset is CLIF 2.1 (mixed-case categories, e.g. IMV, High Flow NC).
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
EOF
fi

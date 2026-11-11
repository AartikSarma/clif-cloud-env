# clif-cloud-env

A ready-made [Claude Code cloud environment](https://code.claude.com/docs/en/claude-code-on-the-web)
for CLIF (Common Longitudinal ICU data Format) research. Every new cloud session starts with:

- **Synthetic CLIF data**: the 10,000-hospitalization dataset from
  [synthetic_clif](https://github.com/Common-Longitudinal-ICU-data-Format/synthetic_clif)
  at `/opt/clif/synthetic_clif/synth_clif_10k` (CLIF 2.1, parquet, no PHI).
- **Python with uv**, plus [clifpy](https://pypi.org/project/clifpy/) preinstalled in `/opt/clif/venv`.
- **R with [uvr](https://github.com/nbafrank/uvr)** (v0.4.8) and R 4.5.2. Packages install
  from Posit Package Manager's prebuilt Linux binaries, so they take seconds instead of compiling.
- **The CLIF skills plugin** ([`clif-icu`](https://github.com/Common-Longitudinal-ICU-data-Format/skills)):
  the clif-icu skill, PHI-guard hooks and three review agents.
- **A `CLAUDE.md` with shared defaults**: uv for Python, uvr for R, scripts that work on
  both CLIF 2.1 and 3.0, and scripts that run on Windows, macOS and Linux.

## Set it up (about 5 minutes, once per person)

1. Open [claude.ai/code](https://claude.ai/code), open the cloud environment menu, and add a
   new environment. Name it something like `CLIF research`.
2. **Network access:** choose limited access, keep package managers allowed, and add every
   host in [`allowed-hosts.txt`](allowed-hosts.txt):
   ```
   cran.r-project.org
   cloud.r-project.org
   packagemanager.posit.co
   cdn.posit.co
   bioconductor.org
   rspm-sync.rstudio.com
   ```
   `rspm-sync.rstudio.com` is the one people miss: Posit Package Manager redirects binary
   downloads there. Without it, every R package falls back to compiling from source, and
   some (such as arrow) fail.
3. **Environment variables:** add
   ```
   CLIF_SYNTH_DATA=/opt/clif/synthetic_clif/synth_clif_10k
   ```
4. **Setup script:** paste the whole of [`setup.sh`](setup.sh).
5. Save, then start a new session on this environment. Check it worked:
   ```bash
   uvr --version && ls $CLIF_SYNTH_DATA | head -3 && /opt/clif/venv/bin/python -c "import clifpy; print(clifpy.__version__)"
   ```
   The `clif-icu` skill should also show up in the session's skills list.

The setup script runs each time a fresh session container starts and adds about 1-2 minutes.
If it fails, the session won't start. Fix it under the environment's Edit → Setup script.

## Use the conventions in a study repo

Allowed hosts and setup scripts belong to each person's environment, but the plugin and the
coding rules can travel with your code. Copy [`project-template/`](project-template) into the
root of a study repository:

- `CLAUDE.md`: the uv/uvr, CLIF 2.1/3.0 and cross-platform rules, without the cloud-only paths.
- `.claude/settings.json`: turns on the `clif-icu` plugin for anyone who opens the repo in
  Claude Code, on a laptop or in the cloud.

## Files

| File | What it is |
|------|------------|
| `setup.sh` | The cloud environment setup script. Self-contained, safe to run more than once. |
| `allowed-hosts.txt` | Hosts the environment must allow (R, CRAN, Posit, Bioconductor). |
| `CLAUDE.md` | The defaults that `setup.sh` writes to `~/.claude/CLAUDE.md`. Keep it in sync with `setup.sh`. |
| `project-template/` | The portable `CLAUDE.md` and plugin settings for study repos. |

## Pinned versions

- **uvr v0.4.8:** the installer's "latest version" lookup uses the GitHub API, which cloud
  sessions can't reach, so the version is pinned. To upgrade, change `UVR_VERSION` in `setup.sh`.
- **R 4.5.2:** change it in `setup.sh` to upgrade.
- **`polars<2`:** clifpy 2.1 calls a polars option that polars 2.x removed. Without the pin,
  clifpy warns and falls back to DuckDB. Drop the pin once clifpy supports polars 2.

## Notes

- **CLIF version of the data:** the bundled 10k dataset is CLIF 2.1. For CLIF 3.0 test data,
  generate it with the synthetic_clif generator, which outputs 3.0 by default.
- **No real patient data:** this environment is for agent-assisted development on synthetic
  data only. Run on real data yourself, in your own secure environment, with no agent present.

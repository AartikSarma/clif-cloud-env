"""Resolve the per-machine site config and the per-project output folders."""

from __future__ import annotations

import os
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

CLIF_VERSIONS = ("2.1", "3.0")

# Site setting -> environment variable that overrides it.
ENV_OVERRIDES = {
    "site": "CLIF_SITE",
    "clif_version": "CLIF_VERSION",
    "data_dir": "CLIF_DATA_DIR",
    "filetype": "CLIF_FILETYPE",
    "timezone": "CLIF_TIMEZONE",
    "output_root": "CLIF_OUTPUT_ROOT",
}

# Environment variables pointing at the synthetic datasets (set in the CLIF cloud environment).
SYNTHETIC_ENV = {"3.0": "CLIF_SYNTH_DATA_V3_0", "2.1": "CLIF_SYNTH_DATA_V2_1"}

UPLOAD_DIRNAME = "upload_no_phi"
LOCAL_DIRNAME = "local_only_phi"
STAGING_DIRNAME = "_shareable_staging"


class ConfigError(Exception):
    """A site or project setting is missing or invalid."""


def site_config_path() -> Path:
    """Where this machine's site config lives (override with CLIF_SITE_CONFIG)."""
    if override := os.environ.get("CLIF_SITE_CONFIG"):
        return Path(override).expanduser()
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "clif" / "site.toml"


@dataclass(frozen=True)
class Site:
    site: str
    clif_version: str
    data_dir: Path
    filetype: str
    timezone: str
    output_root: Path
    synthetic: bool
    source: str


def load_site(overrides: dict[str, str] | None = None, synthetic: str | None = None) -> Site:
    """Merge, in increasing priority: site.toml, CLIF_* env vars, explicit overrides.

    `synthetic="3.0"` or `"2.1"` points the run at the synthetic dataset for that version.
    """
    path = site_config_path()
    raw: dict[str, object] = {}
    source = "environment"
    if path.is_file():
        with path.open("rb") as f:
            raw.update(tomllib.load(f))
        source = str(path)
    for key, env in ENV_OVERRIDES.items():
        if os.environ.get(env):
            raw[key] = os.environ[env]
    if synthetic:
        if synthetic not in SYNTHETIC_ENV:
            raise ConfigError(f"--synthetic must be one of {CLIF_VERSIONS}, got {synthetic!r}")
        env = SYNTHETIC_ENV[synthetic]
        if not os.environ.get(env):
            raise ConfigError(f"--synthetic {synthetic} needs {env} to point at the synthetic data folder")
        raw.update(site="synthetic", clif_version=synthetic, data_dir=os.environ[env])
        raw.setdefault("timezone", "US/Central")
    raw.update({k: v for k, v in (overrides or {}).items() if v})

    missing = [k for k in ("site", "clif_version", "data_dir", "timezone") if not raw.get(k)]
    if missing:
        raise ConfigError(
            f"Missing site setting(s): {', '.join(missing)}. "
            f"Run `clifkit init-site` to create {path}, or set "
            + ", ".join(ENV_OVERRIDES[k] for k in missing)
            + "."
        )
    version = str(raw["clif_version"])
    if version not in CLIF_VERSIONS:
        raise ConfigError(f"clif_version must be one of {CLIF_VERSIONS}, got {version!r}")
    data_dir = Path(str(raw["data_dir"])).expanduser()
    if not data_dir.is_dir():
        raise ConfigError(f"data_dir is not a folder (is the remote share mounted?): {data_dir}")
    return Site(
        site=str(raw["site"]),
        clif_version=version,
        data_dir=data_dir,
        filetype=str(raw.get("filetype") or "parquet"),
        timezone=str(raw["timezone"]),
        output_root=Path(str(raw.get("output_root") or "~/CLIF_output")).expanduser(),
        synthetic=bool(synthetic) or str(raw["site"]) == "synthetic",
        source=source,
    )


def find_project_root(start: Path | None = None) -> Path:
    here = (start or Path.cwd()).resolve()
    for d in (here, *here.parents):
        if (d / "pyproject.toml").is_file():
            return d
    raise ConfigError(f"No pyproject.toml found in {here} or its parents")


def read_pyproject(root: Path) -> dict:
    with (root / "pyproject.toml").open("rb") as f:
        return tomllib.load(f)


@dataclass(frozen=True)
class Project:
    name: str
    root: Path
    site: Site
    out_dir: Path

    @property
    def upload_dir(self) -> Path:
        return self.out_dir / UPLOAD_DIRNAME

    @property
    def local_dir(self) -> Path:
        return self.out_dir / LOCAL_DIRNAME

    @property
    def staging_dir(self) -> Path:
        return self.local_dir / STAGING_DIRNAME


def _is_within(child: Path, parent: Path) -> bool:
    child, parent = child.resolve(), parent.resolve()
    return child == parent or parent in child.parents


def load_project(site: Site, root: Path | None = None) -> Project:
    root = root or find_project_root()
    name = read_pyproject(root).get("project", {}).get("name")
    if not name:
        raise ConfigError(f"{root / 'pyproject.toml'} has no [project] name")
    # Synthetic runs get their own folder so they never mix with real-data results.
    folder = f"{name}__synthetic_v{site.clif_version}" if site.synthetic else name
    out_dir = site.output_root / folder
    if _is_within(out_dir, root):
        raise ConfigError(f"Output folder {out_dir} is inside the project repo {root}; set output_root outside it")
    if _is_within(out_dir, site.data_dir):
        raise ConfigError(f"Output folder {out_dir} is inside the CLIF data folder {site.data_dir}")
    return Project(name=name, root=root, site=site, out_dir=out_dir)

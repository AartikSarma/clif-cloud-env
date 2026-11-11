"""Run a project's steps in order, then the release check."""

from __future__ import annotations

import datetime as dt
import hashlib
import os
import shutil
import subprocess
import sys
from importlib.metadata import version as pkg_version
from pathlib import Path

from .config import ConfigError, Project, Site, read_pyproject
from .context import context_env
from .release import release, write_manifest


def _steps(root: Path) -> list[str]:
    steps = read_pyproject(root).get("tool", {}).get("clifkit", {}).get("steps")
    if not steps:
        raise ConfigError("Add the analysis steps to pyproject.toml:\n[tool.clifkit]\nsteps = [\"analysis/01_x.py\", \"analysis/02_y.R\"]")
    for s in steps:
        if Path(s).suffix.lower() not in (".py", ".r"):
            raise ConfigError(f"Step {s!r}: only .py and .R steps are supported")
        if not (root / s).is_file():
            raise ConfigError(f"Step {s!r} not found in {root}")
    return steps


def _uvr() -> str:
    exe = shutil.which("uvr")
    if not exe:
        raise ConfigError("This project has R steps but `uvr` is not installed: https://github.com/nbafrank/uvr")
    return exe


def _git(root: Path, *args: str) -> str | None:
    try:
        return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _file_hash(p: Path) -> str | None:
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None


def run(project: Project, site: Site, only: list[str] | None = None) -> int:
    root = project.root
    steps = _steps(root)
    if only:
        steps = [s for s in steps if any(o in s for o in only)]
    print(f"clifkit: project {project.name} | site {site.site} | CLIF {site.clif_version}")
    print(f"clifkit: data    {site.data_dir}")
    print(f"clifkit: outputs {project.out_dir}")

    project.local_dir.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(project.staging_dir, ignore_errors=True)
    project.staging_dir.mkdir(parents=True)

    env = {**os.environ, **context_env(project, site), "PYTHONUTF8": "1"}
    has_r = any(Path(s).suffix.lower() == ".r" for s in steps)
    if has_r:
        print("clifkit: syncing R packages (uvr sync)")
        subprocess.run([_uvr(), "sync"], cwd=root, env=env, check=True)

    for s in steps:
        print(f"clifkit: --> {s}", flush=True)
        if Path(s).suffix.lower() == ".py":
            cmd = [sys.executable, s]
        else:
            cmd = [_uvr(), "run", s]
        result = subprocess.run(cmd, cwd=root, env=env)
        if result.returncode != 0:
            print(f"clifkit: step {s} failed (exit {result.returncode}); nothing released", file=sys.stderr)
            return result.returncode

    reports = release(project.staging_dir, project.upload_dir)
    meta = {
        "project": project.name,
        "site": site.site,
        "synthetic_data": site.synthetic,
        "clif_version": site.clif_version,
        "run_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "git_commit": _git(root, "rev-parse", "HEAD"),
        "git_uncommitted_changes": bool(_git(root, "status", "--porcelain")),
        "uv_lock_sha256": _file_hash(root / "uv.lock"),
        "uvr_lock_sha256": _file_hash(root / "uvr.lock"),
        "clifkit_version": pkg_version("clifkit"),
        "python": sys.version.split()[0],
        "platform": sys.platform,
        "steps": steps,
    }
    write_manifest(project.upload_dir, meta, reports)
    suppressed = sum(r.suppressed_cells for r in reports)
    review = [r.name for r in reports if r.kind == "needs_human_review"]
    print(f"clifkit: released {len(reports)} file(s) to {project.upload_dir} ({suppressed} cell(s) suppressed)")
    if review:
        print(f"clifkit: check these by eye before uploading: {', '.join(review)}")
    return 0

"""What an analysis step sees. The runner passes everything through CLIFKIT_* env vars,
so Python and R steps get identical settings (see R/clifkit.R in the template)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ENV = {
    "project": "CLIFKIT_PROJECT",
    "site": "CLIFKIT_SITE",
    "clif_version": "CLIFKIT_CLIF_VERSION",
    "data_dir": "CLIFKIT_DATA_DIR",
    "filetype": "CLIFKIT_FILETYPE",
    "timezone": "CLIFKIT_TIMEZONE",
    "local_dir": "CLIFKIT_LOCAL_DIR",
    "staging_dir": "CLIFKIT_STAGING_DIR",
}


@dataclass(frozen=True)
class Context:
    project: str
    site: str
    clif_version: str
    data_dir: Path
    filetype: str
    timezone: str
    local_dir: Path
    staging_dir: Path

    def table_path(self, table: str) -> Path:
        """Path to a CLIF table, e.g. table_path("hospitalization")."""
        p = self.data_dir / f"clif_{table}.{self.filetype}"
        if not p.exists():
            raise FileNotFoundError(f"CLIF table {table!r} not found at {p}")
        return p

    def local_path(self, name: str) -> Path:
        """A file in local_only_phi (row-level / PHI outputs; never uploaded)."""
        return self.local_dir / name

    def shareable_path(self, name: str) -> Path:
        """A file staged for upload. It only reaches upload_no_phi if it passes the release check."""
        return self.staging_dir / name

    def save_shareable(self, df, name: str) -> Path:
        """Stage a pandas DataFrame of aggregate results as CSV for the release check."""
        if not name.endswith(".csv"):
            name += ".csv"
        path = self.shareable_path(name)
        df.to_csv(path, index=False, encoding="utf-8")
        return path


def context_env(project, site) -> dict[str, str]:
    values = {
        "project": project.name,
        "site": site.site,
        "clif_version": site.clif_version,
        "data_dir": str(site.data_dir),
        "filetype": site.filetype,
        "timezone": site.timezone,
        "local_dir": str(project.local_dir),
        "staging_dir": str(project.staging_dir),
    }
    return {ENV[k]: v for k, v in values.items()}


def context() -> Context:
    """Call from inside a step run by `clifkit run` / `uv run run.py`."""
    missing = [v for v in ENV.values() if not os.environ.get(v)]
    if missing:
        raise RuntimeError(
            "This step must be run through the project runner (`uv run run.py`), "
            f"which sets {', '.join(missing)}"
        )
    e = {k: os.environ[v] for k, v in ENV.items()}
    return Context(
        project=e["project"],
        site=e["site"],
        clif_version=e["clif_version"],
        data_dir=Path(e["data_dir"]),
        filetype=e["filetype"],
        timezone=e["timezone"],
        local_dir=Path(e["local_dir"]),
        staging_dir=Path(e["staging_dir"]),
    )

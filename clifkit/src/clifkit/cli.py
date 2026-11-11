"""clifkit command line: `run`, `init-site`, `show`."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import CLIF_VERSIONS, ConfigError, load_project, load_site, site_config_path
from .release import ReleaseError
from .runner import run


def _site_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--synthetic", choices=CLIF_VERSIONS, help="run on the synthetic dataset for this CLIF version")
    p.add_argument("--clif-version", choices=CLIF_VERSIONS, help="override the site's CLIF version")
    p.add_argument("--data-dir", help="override the site's CLIF data folder")
    p.add_argument("--output-root", help="override the site's output root")


def _load(args):
    site = load_site(
        overrides={"clif_version": args.clif_version, "data_dir": args.data_dir, "output_root": args.output_root},
        synthetic=args.synthetic,
    )
    return site, load_project(site)


def _toml_str(s: str) -> str:
    return json.dumps(s)  # a JSON string is a valid TOML basic string


def claude_rule_path(path: str) -> str | None:
    """A path in Claude Code permission-rule form: //abs/path, //c/Users/... on Windows.

    Returns None for UNC paths (\\\\server\\share), which have no documented rule syntax.
    """
    p = path.replace("\\", "/")
    if p.startswith("//"):
        return None
    if p.startswith("~/"):
        return p
    if len(p) >= 2 and p[1] == ":":  # Windows drive
        return "//" + p[0].lower() + p[2:]
    if p.startswith("/"):
        return "/" + p
    return None


def add_claude_deny(data_dir: str, output_root: str) -> list[str]:
    """Deny Claude Code's file tools access to the real data and every local_only_phi folder."""
    rules, skipped = [], []
    for target in (f"{data_dir}/**", f"{output_root}/**/local_only_phi/**"):
        r = claude_rule_path(target)
        (rules if r else skipped).append(r or target)
    settings = Path.home() / ".claude" / "settings.json"
    data = json.loads(settings.read_text(encoding="utf-8")) if settings.is_file() else {}
    deny = data.setdefault("permissions", {}).setdefault("deny", [])
    for r in rules:
        for tool in ("Read", "Edit"):
            rule = f"{tool}({r})"
            if rule not in deny:
                deny.append(rule)
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"added Claude Code deny rules to {settings}: {', '.join(rules)}")
    for s in skipped:
        print(f"warning: no Claude Code rule syntax for network path {s}; map it to a drive letter or mount point", file=sys.stderr)
    return rules


def init_site(args) -> int:
    path = site_config_path()
    if path.exists() and not args.force:
        print(f"{path} already exists; use --force to replace it", file=sys.stderr)
        return 1
    data_dir = Path(args.data_dir).expanduser()
    if not data_dir.is_dir():
        print(f"warning: {data_dir} is not reachable right now (remote share not mounted?)", file=sys.stderr)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# CLIF site config: read by every clifkit project on this machine.\n"
        f"site = {_toml_str(args.site)}\n"
        f"clif_version = {_toml_str(args.clif_version)}\n"
        f"data_dir = {_toml_str(str(data_dir))}\n"
        f"filetype = {_toml_str(args.filetype)}\n"
        f"timezone = {_toml_str(args.timezone)}\n"
        f"output_root = {_toml_str(args.output_root)}\n",
        encoding="utf-8",
    )
    print(f"wrote {path}")
    if args.claude_deny:
        add_claude_deny(str(data_dir), args.output_root)
    return 0


def show(args) -> int:
    site, project = _load(args)
    print(f"site config : {site.source}")
    for k in ("site", "clif_version", "data_dir", "filetype", "timezone", "output_root", "synthetic"):
        print(f"{k:<12}: {getattr(site, k)}")
    print(f"project     : {project.name} ({project.root})")
    print(f"upload      : {project.upload_dir}")
    print(f"local only  : {project.local_dir}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="clifkit", description="Run CLIF analyses with PHI-safe outputs.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="run the project's steps, then the release check")
    _site_args(p_run)
    p_run.add_argument("--only", nargs="+", help="run only steps whose path contains one of these strings")

    p_show = sub.add_parser("show", help="print the resolved site and output folders")
    _site_args(p_show)

    p_init = sub.add_parser("init-site", help=f"write this machine's site config ({site_config_path()})")
    p_init.add_argument("--site", required=True, help="short site name, e.g. ucmc")
    p_init.add_argument("--clif-version", required=True, choices=CLIF_VERSIONS)
    p_init.add_argument("--data-dir", required=True, help="folder with the clif_*.parquet tables (remote share OK)")
    p_init.add_argument("--timezone", required=True, help="site timezone, e.g. US/Central")
    p_init.add_argument("--filetype", default="parquet", choices=["parquet", "csv"])
    p_init.add_argument("--output-root", default="~/CLIF_output")
    p_init.add_argument("--force", action="store_true")
    p_init.add_argument(
        "--claude-deny",
        action="store_true",
        help="also block Claude Code from reading the data folder and local_only_phi (~/.claude/settings.json)",
    )

    args = ap.parse_args(argv)
    try:
        if args.cmd == "init-site":
            return init_site(args)
        if args.cmd == "show":
            return show(args)
        site, project = _load(args)
        return run(project, site, only=args.only)
    except (ConfigError, ReleaseError) as e:
        print(f"clifkit: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

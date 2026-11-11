"""The release check: the only path from analysis outputs to upload_no_phi.

Steps write shareable candidates into local_only_phi/_shareable_staging. `release()`
checks every file there and, only if all pass, rebuilds upload_no_phi from scratch:

- CSV tables: columns that look like identifiers or dates, and date-like values, fail
  the release. Count columns have values 1-9 replaced with "<10", and percent/proportion
  columns in the same row are blanked so the count can't be recovered from them.
- Figures and text (png, pdf, svg, md, txt): copied, but marked for human review,
  because they can't be checked automatically.
- Anything else (parquet, rds, xlsx, ...): fails the release.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

SMALL_CELL_THRESHOLD = 10  # counts 1..9 are suppressed
SUPPRESSED = "<10"
PCT_SUPPRESSED = "suppressed"

TABLE_EXTS = {".csv"}
REVIEW_EXTS = {".png", ".pdf", ".svg", ".md", ".txt"}

# Column names that must never leave the site.
_FORBIDDEN_COL = re.compile(
    r"(^|_)(id|ids|mrn|ssn|name|names|zip|zipcode|zipcode_five_digit|zipcode_nine_digit|address|"
    r"phone|email|dob|birth|census_block_code|census_tract)$"
    r"|_dttm$|_date$|^date|_datetime$|_time$|_name$"
)
# Count columns: n, n_*, *_n, count, *_count, count_*
_COUNT_COL = re.compile(r"^(n|count)$|^(n|count)_|_(n|count)$")
# Percent/proportion columns: pct, percent, prop, proportion, rate (as a word part)
_PCT_COL = re.compile(r"(^|_)(pct|percent|prop|proportion|rate)(_|$)")
_DATE_VALUE = re.compile(r"^\d{4}-\d{2}-\d{2}([ T]\d{2}:\d{2}.*)?$")


class ReleaseError(Exception):
    """A staged file failed the check; nothing was released."""


@dataclass
class FileReport:
    name: str
    kind: str  # "table" | "needs_human_review"
    rows: int | None = None
    suppressed_cells: int = 0
    sha256: str = ""
    problems: list[str] = field(default_factory=list)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _as_count(value: str) -> int | None:
    try:
        x = float(value)
    except ValueError:
        return None
    return int(x) if x.is_integer() else None


def check_table(src: Path, dst: Path | None) -> FileReport:
    """Check one CSV; if dst is given and the table passes, write the suppressed copy there."""
    report = FileReport(name=src.name, kind="table")
    with src.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            report.problems.append("empty file")
            return report
        rows = list(reader)
    cols = [c.strip().lower() for c in header]
    for c, raw in zip(cols, header):
        if _FORBIDDEN_COL.search(c):
            report.problems.append(f"column {raw!r} looks like an identifier, name or date")
    count_idx = [i for i, c in enumerate(cols) if _COUNT_COL.search(c)]
    pct_idx = [i for i, c in enumerate(cols) if _PCT_COL.search(c)]
    out_rows = []
    for r_no, row in enumerate(rows, start=2):
        row = list(row)
        for i, v in enumerate(row):
            if _DATE_VALUE.match(v.strip()):
                report.problems.append(f"row {r_no}, column {header[i]!r}: date-like value")
                break
        hit = False
        for i in count_idx:
            if i < len(row):
                n = _as_count(row[i])
                if n is not None and 0 < n < SMALL_CELL_THRESHOLD:
                    row[i] = SUPPRESSED
                    report.suppressed_cells += 1
                    hit = True
        if hit:
            for i in pct_idx:
                if i < len(row) and row[i] != "":
                    row[i] = PCT_SUPPRESSED
                    report.suppressed_cells += 1
        out_rows.append(row)
    report.rows = len(rows)
    if not count_idx:
        report.problems.append(
            "no count column found (name it n, n_*, *_n or count*) so small cells can't be checked"
        )
    if dst is not None and not report.problems:
        with dst.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(header)
            w.writerows(out_rows)
        report.sha256 = _sha256(dst)
    return report


def release(staging_dir: Path, upload_dir: Path) -> list[FileReport]:
    """Check everything in staging_dir; on success replace upload_dir with the checked copies."""
    files = sorted(p for p in staging_dir.rglob("*") if p.is_file()) if staging_dir.is_dir() else []
    problems: list[str] = []
    for p in files:
        ext = p.suffix.lower()
        if ext not in TABLE_EXTS | REVIEW_EXTS:
            problems.append(f"{p.name}: file type {ext or '(none)'} can't be released; write a CSV table or a figure")
        elif p.parent != staging_dir:
            problems.append(f"{p.relative_to(staging_dir)}: put shareable files directly in the staging folder")
        elif ext in TABLE_EXTS:
            problems += [f"{p.name}: {m}" for m in check_table(p, None).problems]
    if problems:
        raise ReleaseError("Release blocked, upload_no_phi left unchanged:\n  - " + "\n  - ".join(problems))

    # Everything passed: rebuild upload_no_phi so no stale file from an earlier run survives.
    tmp = upload_dir.with_name(upload_dir.name + ".tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    reports = []
    for p in files:
        if p.suffix.lower() in TABLE_EXTS:
            reports.append(check_table(p, tmp / p.name))
        else:
            shutil.copy2(p, tmp / p.name)
            reports.append(FileReport(name=p.name, kind="needs_human_review", sha256=_sha256(tmp / p.name)))
    shutil.rmtree(upload_dir, ignore_errors=True)
    tmp.rename(upload_dir)
    return reports


def write_manifest(upload_dir: Path, meta: dict, reports: list[FileReport]) -> Path:
    manifest = {
        **meta,
        "small_cell_rule": f"counts 1-{SMALL_CELL_THRESHOLD - 1} replaced with '{SUPPRESSED}'; "
        f"percent/proportion columns in those rows set to '{PCT_SUPPRESSED}'",
        "not_checked": "complementary suppression (totals or other tables that let a suppressed "
        "count be recalculated) and figure contents; review before upload",
        "files": [
            {k: v for k, v in r.__dict__.items() if k != "problems" and v is not None} for r in reports
        ],
    }
    path = upload_dir / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return path

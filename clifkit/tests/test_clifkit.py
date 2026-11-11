import csv
import json
from pathlib import Path

import pytest

from clifkit.config import ConfigError, load_project, load_site
from clifkit.release import ReleaseError, release, write_manifest


def _csv(path: Path, rows: list[list]) -> Path:
    with path.open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(rows)
    return path


def _read(path: Path) -> list[list[str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.reader(f))


@pytest.fixture
def dirs(tmp_path):
    staging = tmp_path / "local_only_phi" / "_shareable_staging"
    staging.mkdir(parents=True)
    return staging, tmp_path / "upload_no_phi"


def test_small_counts_suppressed_with_their_percents(dirs):
    staging, upload = dirs
    _csv(staging / "t.csv", [["group", "n", "pct"], ["a", "120", "92.3"], ["b", "9", "6.9"], ["c", "1", "0.8"], ["d", "0", "0"]])
    reports = release(staging, upload)
    assert _read(upload / "t.csv") == [
        ["group", "n", "pct"], ["a", "120", "92.3"], ["b", "<10", "suppressed"], ["c", "<10", "suppressed"], ["d", "0", "0"]
    ]
    assert reports[0].suppressed_cells == 4


def test_count_column_name_variants(dirs):
    staging, upload = dirs
    _csv(staging / "t.csv", [["n_imv", "deaths_n", "count_total", "age_mean"], ["5", "10", "3", "4.0"]])
    release(staging, upload)
    assert _read(upload / "t.csv")[1] == ["<10", "10", "<10", "4.0"]


@pytest.mark.parametrize("col", ["hospitalization_id", "patient_id", "admission_dttm", "birth_date", "discharge_name", "zipcode_five_digit", "mrn"])
def test_identifier_and_date_columns_block_release(dirs, col):
    staging, upload = dirs
    _csv(staging / "t.csv", [[col, "n"], ["x", "50"]])
    with pytest.raises(ReleaseError, match=col):
        release(staging, upload)
    assert not upload.exists()


def test_date_values_block_release(dirs):
    staging, upload = dirs
    _csv(staging / "t.csv", [["group", "n"], ["2024-03-01 10:15", "50"]])
    with pytest.raises(ReleaseError, match="date-like"):
        release(staging, upload)


def test_table_without_count_column_blocks_release(dirs):
    staging, upload = dirs
    _csv(staging / "t.csv", [["group", "mean_age"], ["a", "61.2"]])
    with pytest.raises(ReleaseError, match="no count column"):
        release(staging, upload)


def test_row_level_formats_block_release(dirs):
    staging, upload = dirs
    (staging / "cohort.parquet").write_bytes(b"x")
    with pytest.raises(ReleaseError, match="parquet"):
        release(staging, upload)


def test_one_bad_file_blocks_everything_and_keeps_old_upload(dirs):
    staging, upload = dirs
    upload.mkdir()
    (upload / "old.csv").write_text("n\n50\n")
    _csv(staging / "good.csv", [["n"], ["50"]])
    _csv(staging / "bad.csv", [["patient_id", "n"], ["p1", "50"]])
    with pytest.raises(ReleaseError):
        release(staging, upload)
    assert sorted(p.name for p in upload.iterdir()) == ["old.csv"]


def test_upload_is_rebuilt_and_figures_flagged(dirs):
    staging, upload = dirs
    upload.mkdir()
    (upload / "stale.csv").write_text("n\n50\n")
    _csv(staging / "t.csv", [["n"], ["50"]])
    (staging / "fig.png").write_bytes(b"\x89PNG")
    reports = release(staging, upload)
    write_manifest(upload, {"project": "p"}, reports)
    assert sorted(p.name for p in upload.iterdir()) == ["fig.png", "manifest.json", "t.csv"]
    m = json.loads((upload / "manifest.json").read_text())
    assert {f["name"]: f["kind"] for f in m["files"]} == {"fig.png": "needs_human_review", "t.csv": "table"}
    assert all(len(f["sha256"]) == 64 for f in m["files"])


def _site_env(monkeypatch, tmp_path, data, out):
    monkeypatch.setenv("CLIF_SITE_CONFIG", str(tmp_path / "none.toml"))
    monkeypatch.setenv("CLIF_SITE", "testsite")
    monkeypatch.setenv("CLIF_VERSION", "3.0")
    monkeypatch.setenv("CLIF_DATA_DIR", str(data))
    monkeypatch.setenv("CLIF_TIMEZONE", "US/Central")
    monkeypatch.setenv("CLIF_OUTPUT_ROOT", str(out))


def _proj(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text('[project]\nname = "demo"\n')
    return root


def test_output_folders_outside_repo(monkeypatch, tmp_path):
    data = tmp_path / "data"; data.mkdir()
    _site_env(monkeypatch, tmp_path, data, tmp_path / "CLIF_output")
    p = load_project(load_site(), _proj(tmp_path / "repo"))
    assert p.upload_dir == tmp_path / "CLIF_output" / "demo" / "upload_no_phi"
    assert p.local_dir == tmp_path / "CLIF_output" / "demo" / "local_only_phi"


def test_output_inside_repo_refused(monkeypatch, tmp_path):
    data = tmp_path / "data"; data.mkdir()
    repo = _proj(tmp_path / "repo")
    _site_env(monkeypatch, tmp_path, data, repo / "out")
    with pytest.raises(ConfigError, match="inside the project repo"):
        load_project(load_site(), repo)


def test_synthetic_runs_get_their_own_folder(monkeypatch, tmp_path):
    data = tmp_path / "synth21"; data.mkdir()
    _site_env(monkeypatch, tmp_path, tmp_path, tmp_path / "CLIF_output")
    monkeypatch.setenv("CLIF_SYNTH_DATA_V2_1", str(data))
    site = load_site(synthetic="2.1")
    assert (site.site, site.clif_version, site.data_dir) == ("synthetic", "2.1", data)
    assert load_project(site, _proj(tmp_path / "repo")).out_dir.name == "demo__synthetic_v2.1"


def test_missing_settings_explain_fix(monkeypatch, tmp_path):
    monkeypatch.setenv("CLIF_SITE_CONFIG", str(tmp_path / "none.toml"))
    for v in ("CLIF_SITE", "CLIF_VERSION", "CLIF_DATA_DIR", "CLIF_TIMEZONE"):
        monkeypatch.delenv(v, raising=False)
    with pytest.raises(ConfigError, match="clifkit init-site"):
        load_site()


def test_bad_version_rejected(monkeypatch, tmp_path):
    _site_env(monkeypatch, tmp_path, tmp_path, tmp_path / "o")
    monkeypatch.setenv("CLIF_VERSION", "2.0")
    with pytest.raises(ConfigError, match="clif_version"):
        load_site()


@pytest.mark.parametrize("path,rule", [
    ("/mnt/clif/**", "//mnt/clif/**"),
    ("~/CLIF_output/**/local_only_phi/**", "~/CLIF_output/**/local_only_phi/**"),
    ("C:\\Users\\alice\\clif/**", "//c/Users/alice/clif/**"),
    ("\\\\server\\share\\clif/**", None),
])
def test_claude_rule_paths(path, rule):
    from clifkit.cli import claude_rule_path
    assert claude_rule_path(path) == rule


def test_init_site_writes_config_and_deny_rules(monkeypatch, tmp_path):
    from clifkit.cli import main
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("CLIF_SITE_CONFIG", str(tmp_path / "cfg" / "site.toml"))
    data = tmp_path / "data"; data.mkdir()
    settings = tmp_path / ".claude" / "settings.json"
    settings.parent.mkdir()
    settings.write_text('{"model": "x", "permissions": {"deny": ["Read(//etc/**)"]}}')
    assert main(["init-site", "--site", "s1", "--clif-version", "2.1", "--data-dir", str(data),
                 "--timezone", "US/Eastern", "--claude-deny"]) == 0
    for v in ("CLIF_SITE", "CLIF_VERSION", "CLIF_DATA_DIR", "CLIF_TIMEZONE", "CLIF_OUTPUT_ROOT"):
        monkeypatch.delenv(v, raising=False)
    site = load_site()
    assert (site.site, site.clif_version, site.data_dir, site.timezone) == ("s1", "2.1", data, "US/Eastern")
    s = json.loads(settings.read_text())
    assert s["model"] == "x"
    assert s["permissions"]["deny"] == [
        "Read(//etc/**)", f"Read(/{data}/**)", f"Edit(/{data}/**)",
        "Read(~/CLIF_output/**/local_only_phi/**)", "Edit(~/CLIF_output/**/local_only_phi/**)",
    ]
    # running it again doesn't duplicate rules or overwrite the config without --force
    assert main(["init-site", "--site", "s1", "--clif-version", "2.1", "--data-dir", str(data), "--timezone", "US/Eastern"]) == 1

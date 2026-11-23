import json
import os
import time

import pytest

from winsync import IgnoreRules, plan, sync
from winsync.cli import main
from winsync.config import load
from winsync.engine import TRASH_DIR, purge_trash


def write(path, text="x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def src(tmp_path):
    s = tmp_path / "src"
    write(s / "hop-dong" / "HD-001.docx", "hợp đồng")
    write(s / "bao-gia.xlsx", "báo giá")
    write(s / "~$bao-gia.xlsx", "khoá tạm")
    write(s / "mat-khau.txt", "bí mật")
    write(s / ".cache" / "a.bin", "ẩn")
    return s


def test_first_sync_copies_everything_but_ignored(src, tmp_path):
    dst = tmp_path / "dst"
    res = sync(src, dst)
    assert res.copied == 2
    assert (dst / "hop-dong" / "HD-001.docx").read_text(encoding="utf-8") == "hợp đồng"
    assert not (dst / "~$bao-gia.xlsx").exists()
    assert not (dst / "mat-khau.txt").exists()
    assert not (dst / ".cache").exists()


def test_second_sync_is_noop(src, tmp_path):
    dst = tmp_path / "dst"
    sync(src, dst)
    assert plan(src, dst) == []


def test_changed_file_is_updated(src, tmp_path):
    dst = tmp_path / "dst"
    sync(src, dst)
    f = src / "bao-gia.xlsx"
    f.write_text("báo giá mới, dài hơn", encoding="utf-8")
    res = sync(src, dst)
    assert [c.action for c in res.changes] == ["update"]
    assert (dst / "bao-gia.xlsx").read_text(encoding="utf-8") == "báo giá mới, dài hơn"


def test_deleted_source_goes_to_trash_not_gone(src, tmp_path):
    dst = tmp_path / "dst"
    sync(src, dst)
    (src / "bao-gia.xlsx").unlink()
    res = sync(src, dst, now=time.mktime((2026, 11, 23, 9, 0, 0, 0, 0, -1)))
    assert res.trashed == 1
    assert not (dst / "bao-gia.xlsx").exists()
    assert (dst / TRASH_DIR / "20261123-090000" / "bao-gia.xlsx").exists()


def test_source_is_never_modified(src, tmp_path):
    before = sorted((p.relative_to(src), p.stat().st_mtime) for p in src.rglob("*") if p.is_file())
    dst = tmp_path / "dst"
    write(dst / "chi-o-dich.txt")
    sync(src, dst, verify=True)
    after = sorted((p.relative_to(src), p.stat().st_mtime) for p in src.rglob("*") if p.is_file())
    assert before == after


def test_dry_run_touches_nothing(src, tmp_path):
    dst = tmp_path / "dst"
    res = sync(src, dst, dry_run=True)
    assert res.copied == 2
    assert not dst.exists()


def test_no_temp_file_left(src, tmp_path):
    dst = tmp_path / "dst"
    sync(src, dst, verify=True)
    assert not [p for p in dst.rglob("*.winsync-tmp")]


def test_purge_trash_keeps_recent(tmp_path):
    old = tmp_path / TRASH_DIR / "20200101-000000"
    new = tmp_path / TRASH_DIR / "20261120-000000"
    write(old / "a.txt")
    write(new / "b.txt")
    now = time.mktime((2026, 11, 23, 0, 0, 0, 0, 0, -1))
    assert purge_trash(tmp_path, keep_days=30, now=now) == 1
    assert new.exists() and not old.exists()


def test_ignore_rules_extra():
    rules = IgnoreRules(extra=["*.bak"])
    assert rules.ignored("a/b/file.BAK")
    assert rules.ignored("x/.git/config")
    assert not rules.ignored("Hợp đồng/HD-01.pdf")


def test_config_and_cli(src, tmp_path):
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({"hub": str(tmp_path / "hub"), "users": {"an": str(src)}}), encoding="utf-8")
    c = load(cfg)
    assert c.jobs[0].dest == tmp_path / "hub" / "an"
    assert main(["run", "-c", str(cfg)]) == 0
    assert (tmp_path / "hub" / "an" / "bao-gia.xlsx").exists()


def test_config_rejects_bad_user(tmp_path):
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({"hub": "h", "users": {"a/b": "x"}}), encoding="utf-8")
    with pytest.raises(ValueError):
        load(cfg)


def test_missing_source_raises(tmp_path):
    with pytest.raises(NotADirectoryError):
        sync(tmp_path / "khong-co", tmp_path / "dst")


@pytest.mark.skipif(os.name != "nt", reason="khoá file kiểu Windows")
def test_locked_file_reported_not_fatal(src, tmp_path):
    dst = tmp_path / "dst"
    sync(src, dst)
    (src / "bao-gia.xlsx").write_text("mới hơn nhiều", encoding="utf-8")
    target = dst / "bao-gia.xlsx"
    with open(target, "rb"):
        res = sync(src, dst)
    assert res.errors or res.copied == 1

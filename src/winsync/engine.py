"""Lõi đồng bộ: lập kế hoạch rồi thực hiện.

Nguyên tắc:
- Một chiều: nguồn (máy nhân viên) → đích (máy chủ). Không bao giờ sửa hay xoá file ở nguồn.
- Chép nguyên tử: ghi ra file tạm cạnh đích rồi `os.replace`, mất điện giữa chừng không để lại file hỏng.
- File biến mất ở nguồn không bị xoá thẳng ở đích: chuyển vào `.thung-rac/<thời điểm>/` để lấy lại được.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from .filters import IgnoreRules, with_ignore_file

TRASH_DIR = ".thung-rac"
MTIME_TOLERANCE = 2.0  # FAT/exFAT chỉ lưu thời gian chính xác tới 2 giây


@dataclass(frozen=True)
class Change:
    action: str  # "copy" | "update" | "trash"
    rel_path: str
    size: int = 0


@dataclass
class SyncResult:
    changes: list[Change] = field(default_factory=list)
    errors: list[tuple[str, str]] = field(default_factory=list)
    dry_run: bool = False

    @property
    def copied(self) -> int:
        return sum(1 for c in self.changes if c.action in ("copy", "update"))

    @property
    def trashed(self) -> int:
        return sum(1 for c in self.changes if c.action == "trash")

    @property
    def bytes(self) -> int:
        return sum(c.size for c in self.changes if c.action != "trash")


def _walk(root: Path, rules: IgnoreRules) -> Iterator[tuple[str, os.stat_result]]:
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = os.path.relpath(dirpath, root)
        rel_dir = "" if rel_dir == "." else rel_dir.replace("\\", "/") + "/"
        dirnames[:] = [d for d in dirnames if d != TRASH_DIR and not rules.ignored(rel_dir + d)]
        for name in filenames:
            rel = rel_dir + name
            if rules.ignored(rel):
                continue
            try:
                yield rel, os.stat(os.path.join(dirpath, name))
            except OSError:
                continue


def _differs(src: os.stat_result, dst: Path) -> bool:
    try:
        d = dst.stat()
    except FileNotFoundError:
        return True
    return src.st_size != d.st_size or abs(src.st_mtime - d.st_mtime) > MTIME_TOLERANCE


def plan(source: Path, dest: Path, rules: IgnoreRules | None = None, trash_missing: bool = True) -> list[Change]:
    """Trả về danh sách thay đổi cần làm, chưa chạm vào file nào."""
    rules = with_ignore_file(rules or IgnoreRules(), source)
    source, dest = Path(source), Path(dest)
    changes: list[Change] = []
    seen: set[str] = set()
    for rel, st in _walk(source, rules):
        seen.add(rel)
        target = dest / rel
        if not target.exists():
            changes.append(Change("copy", rel, st.st_size))
        elif _differs(st, target):
            changes.append(Change("update", rel, st.st_size))
    if trash_missing and dest.exists():
        for rel, st in _walk(dest, IgnoreRules(block_sensitive=False)):
            if rel not in seen and not rules.ignored(rel):
                changes.append(Change("trash", rel, st.st_size))
    return changes


def sha256(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while block := f.read(chunk):
            h.update(block)
    return h.hexdigest()


def _atomic_copy(src: Path, dst: Path, verify: bool) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(f".{dst.name}.winsync-tmp")
    shutil.copy2(src, tmp)
    if verify and sha256(src) != sha256(tmp):
        tmp.unlink(missing_ok=True)
        raise OSError("checksum không khớp sau khi chép")
    os.replace(tmp, dst)


def sync(
    source: Path,
    dest: Path,
    rules: IgnoreRules | None = None,
    dry_run: bool = False,
    verify: bool = False,
    trash_missing: bool = True,
    now: float | None = None,
) -> SyncResult:
    """Đồng bộ `source` → `dest`. Lỗi từng file được ghi lại, không làm dừng cả lượt."""
    source, dest = Path(source), Path(dest)
    if not source.is_dir():
        raise NotADirectoryError(f"không thấy thư mục nguồn: {source}")
    result = SyncResult(dry_run=dry_run)
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(now))
    for change in plan(source, dest, rules, trash_missing):
        if dry_run:
            result.changes.append(change)
            continue
        try:
            if change.action == "trash":
                src = dest / change.rel_path
                bin_path = dest / TRASH_DIR / stamp / change.rel_path
                bin_path.parent.mkdir(parents=True, exist_ok=True)
                os.replace(src, bin_path)
            else:
                _atomic_copy(source / change.rel_path, dest / change.rel_path, verify)
            result.changes.append(change)
        except OSError as exc:  # file đang bị khoá, hết chỗ, ...
            result.errors.append((change.rel_path, str(exc)))
    return result


def purge_trash(dest: Path, keep_days: int = 30, now: float | None = None) -> int:
    """Xoá các lô trong thùng rác cũ hơn `keep_days`. Trả về số lô đã xoá."""
    now = time.time() if now is None else now
    trash = Path(dest) / TRASH_DIR
    if not trash.is_dir():
        return 0
    removed = 0
    for batch in trash.iterdir():
        try:
            t = time.mktime(time.strptime(batch.name, "%Y%m%d-%H%M%S"))
        except ValueError:
            continue
        if now - t > keep_days * 86400:
            shutil.rmtree(batch, ignore_errors=True)
            removed += 1
    return removed

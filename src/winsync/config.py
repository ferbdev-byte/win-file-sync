"""Đọc file cấu hình JSON: mỗi người một thư mục nguồn, đích tự chia theo tên người."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .filters import IgnoreRules


@dataclass(frozen=True)
class Job:
    user: str
    source: Path
    dest: Path


@dataclass(frozen=True)
class Config:
    hub: Path
    jobs: tuple[Job, ...]
    rules: IgnoreRules
    verify: bool = False
    trash_days: int = 30
    interval: int = 60


def load(path: str | Path) -> Config:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    hub = Path(raw["hub"])
    jobs = []
    for user, src in raw["users"].items():
        if any(c in user for c in '\\/:*?"<>|'):
            raise ValueError(f"tên người không hợp lệ làm tên thư mục: {user!r}")
        jobs.append(Job(user, Path(src), hub / user))
    rules = IgnoreRules(extra=list(raw.get("ignore", [])), block_sensitive=raw.get("block_sensitive", True))
    return Config(
        hub=hub,
        jobs=tuple(jobs),
        rules=rules,
        verify=bool(raw.get("verify", False)),
        trash_days=int(raw.get("trash_days", 30)),
        interval=int(raw.get("interval", 60)),
    )

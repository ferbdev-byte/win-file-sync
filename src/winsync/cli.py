"""Dòng lệnh: `winsync run`, `winsync watch`, `winsync plan`."""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime

from . import __version__
from .config import Config, load
from .engine import plan, purge_trash, sync

log = logging.getLogger("winsync")


def _human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def run_once(cfg: Config, dry_run: bool) -> int:
    failed = 0
    for job in cfg.jobs:
        if not job.source.is_dir():
            log.warning("[%s] bỏ qua: không thấy %s", job.user, job.source)
            failed += 1
            continue
        res = sync(job.source, job.dest, cfg.rules, dry_run=dry_run, verify=cfg.verify)
        log.info(
            "[%s] %s%d file (%s), %d vào thùng rác, %d lỗi",
            job.user, "(thử) " if dry_run else "", res.copied, _human(res.bytes), res.trashed, len(res.errors),
        )
        for rel, err in res.errors:
            log.error("[%s] %s: %s", job.user, rel, err)
        failed += bool(res.errors)
        if not dry_run:
            purge_trash(job.dest, cfg.trash_days)
    return failed


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="winsync", description="Đồng bộ thư mục từng người về máy chủ.")
    p.add_argument("--version", action="version", version=f"winsync {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, help_ in (("run", "chạy một lượt"), ("watch", "chạy lặp lại theo chu kỳ"), ("plan", "in kế hoạch dạng JSON")):
        s = sub.add_parser(name, help=help_)
        s.add_argument("-c", "--config", required=True)
        if name == "run":
            s.add_argument("--dry-run", action="store_true", help="chỉ xem sẽ làm gì")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    cfg = load(args.config)

    if args.cmd == "plan":
        out = {
            j.user: [c.__dict__ for c in plan(j.source, j.dest, cfg.rules)] for j in cfg.jobs if j.source.is_dir()
        }
        json.dump(out, sys.stdout, ensure_ascii=False, indent=2)
        return 0
    if args.cmd == "run":
        return 1 if run_once(cfg, args.dry_run) else 0

    log.info("theo dõi %d người, mỗi %ds — Ctrl+C để dừng", len(cfg.jobs), cfg.interval)
    try:
        while True:
            started = datetime.now()
            run_once(cfg, dry_run=False)
            time.sleep(max(1, cfg.interval - (datetime.now() - started).seconds))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())

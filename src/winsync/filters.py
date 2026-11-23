"""Luật bỏ qua file: file tạm của Office, file hệ thống và file nhạy cảm (mật khẩu, khoá)."""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_PATTERNS = (
    "~$*",          # file khoá tạm của Word/Excel
    "*.tmp",
    "*.crdownload",
    "*.part",
    "desktop.ini",
    "Thumbs.db",
    ".DS_Store",
    "__pycache__",
    "node_modules",
    ".git",
)

# Tên file gợi ý chứa bí mật: không bao giờ đẩy lên máy chủ chung.
SENSITIVE = re.compile(
    r"(passw|mat[-_ ]?khau|mật[-_ ]?khẩu|token|secret|credential|id_rsa|\.env$|\.pem$|\.key$|\.kdbx$|\.ppk$)",
    re.IGNORECASE,
)


@dataclass
class IgnoreRules:
    patterns: tuple[str, ...] = DEFAULT_PATTERNS
    extra: list[str] = field(default_factory=list)
    block_sensitive: bool = True

    def ignored(self, rel_path: str) -> bool:
        """True nếu đường dẫn tương đối (dùng '/') phải bỏ qua."""
        parts = rel_path.replace("\\", "/").split("/")
        for part in parts:
            if part.startswith(".") and part not in (".", ".."):
                return True
            for pat in (*self.patterns, *self.extra):
                if fnmatch.fnmatch(part.lower(), pat.lower()):
                    return True
        return bool(self.block_sensitive and SENSITIVE.search(parts[-1]))


IGNORE_FILE = ".winsyncignore"


def with_ignore_file(rules: IgnoreRules, source: str | Path) -> IgnoreRules:
    """Thêm mẫu bỏ qua từ file `.winsyncignore` nằm trong thư mục nguồn (mỗi dòng một mẫu, `#` là chú thích).

    Nhờ vậy mỗi người tự quyết thư mục nháp nào của mình không cần đẩy lên máy chủ.
    """
    f = Path(source) / IGNORE_FILE
    if not f.is_file():
        return rules
    lines = (ln.strip() for ln in f.read_text(encoding="utf-8-sig").splitlines())
    extra = [ln for ln in lines if ln and not ln.startswith("#")]
    return IgnoreRules(rules.patterns, [*rules.extra, *extra], rules.block_sensitive)

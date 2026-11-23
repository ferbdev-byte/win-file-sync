"""Luật bỏ qua file: file tạm của Office, file hệ thống và file nhạy cảm (mật khẩu, khoá)."""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field

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

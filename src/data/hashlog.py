"""库文件 SHA256。每次提交前后各记一行，格式与 results/inventory/db-writes.txt 一致。"""
from __future__ import annotations

from pathlib import Path

from . import db as DB


class HashLedger:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.lines: list[str] = []
        self.last = DB.sha256_file(self.path) if self.path.exists() else ""

    def before(self, label: str) -> str:
        digest = DB.sha256_file(self.path)
        self.lines.append(f"SHA256 BEFORE {label} {digest}")
        self.last = digest
        return digest

    def after(self, label: str) -> str:
        digest = DB.sha256_file(self.path)
        self.lines.append(f"SHA256 AFTER  {label} {digest}")
        if digest == self.last:
            self.lines.append(f"SHA256 UNCHANGED {label}")
        self.last = digest
        return digest

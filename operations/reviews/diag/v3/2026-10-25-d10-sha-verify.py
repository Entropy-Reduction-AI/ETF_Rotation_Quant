#!/usr/bin/env python3
"""Reviewer 独立复算 D10 数据指纹（2026-10-25）。

运行前需对 LFS 对象执行 `git lfs pull -I data/market.sqlite`，否则指针文件哈希与内容哈希不同。
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
CLAIMED = {
    "data/market.sqlite": "3e3e6f1d594586da2abf28db5fa88b05c1cc91fa29adf061fc699e1b8d4bc1d6",
    "config/v3/universe.toml": "fda394d57b9109225bda0d459975125364b5f1bb5d1793c9ad080ec55f789b19",
    "results/v3/inventory/coverage.csv": "3006a8a4259baebb5e11e91847997548f47d70f23f0cb19d690cea018fa5e8b9",
    "results/v3/inventory/overseas-holiday-audit.csv": "c876cf9c32fd51b668739e021aeaa84fdf9ab510311285e9e1bfe3ec3e5658d2",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    ok = True
    for rel, expected in CLAIMED.items():
        path = ROOT / rel
        if not path.exists():
            print(f"MISSING {rel}")
            ok = False
            continue
        actual = sha256(path)
        match = actual == expected
        print(f"{rel}: {actual} {'OK' if match else 'MISMATCH expected ' + expected}")
        if path.name == "market.sqlite" and path.read_text(encoding="utf-8", errors="ignore").startswith("version https://git-lfs"):
            print("  (warning: market.sqlite is still an LFS pointer; run git lfs pull)")
        ok = ok and match
    if ok:
        print("all claimed SHAs match")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

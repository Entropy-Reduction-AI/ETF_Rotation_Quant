"""v5.1 账本追加。同一臂、同一段、同一匹配键只留一行。不写 LOCK。"""
from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from src.data.db import git_head
from src.v3.engine.ledger import COLUMNS, canonical_params

from .design import _refuse_ledger, _rows

TAIPEI = ZoneInfo("Asia/Taipei")


def _newline(path: Path) -> str:
    if path.exists() and b"\r\n" in path.read_bytes():
        return "\r\n"
    return "\n"


def upsert(path: Path, params: dict, *, arm: str, segment: str, runner: str,
           same) -> None:
    """`same(row, old_params)` 为真的旧行会被这一行换掉。"""
    _refuse_ledger(path)
    fresh = {
        "run_at": datetime.now(TAIPEI).isoformat(timespec="seconds"),
        "git_sha": git_head() or "",
        "arm": arm,
        "params": canonical_params(params),
        "segment": segment,
        "runner": runner,
    }
    kept = []
    for row in _rows(path):
        try:
            old = json.loads(row.get("params") or "{}")
        except json.JSONDecodeError:
            kept.append(row)
            continue
        if same(row, old):
            continue
        kept.append(row)
    path.parent.mkdir(parents=True, exist_ok=True)
    newline = _newline(path)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, lineterminator=newline)
        writer.writeheader()
        writer.writerows(kept)
        writer.writerow(fresh)

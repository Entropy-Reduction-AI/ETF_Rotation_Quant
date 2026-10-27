"""results/v3/trial-ledger.csv。同一臂、同一参数、同一段只留一行。debug 不写。"""
from __future__ import annotations

import csv
import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from src.data.db import git_head

from .spec import LEDGER

COLUMNS = ["run_at", "git_sha", "arm", "params", "segment", "runner"]
TAIPEI = ZoneInfo("Asia/Taipei")


def canonical_params(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def append_ledger(path: Path, *, arm: str, params: dict, segment: str, runner: str) -> bool:
    """写入返回 True。相同配置已经有一行时不再追加，返回 False。"""
    if os.environ.get("ETF_LEDGER_TESTING") and Path(path).resolve() == LEDGER.resolve():
        raise RuntimeError("测试里不能写 results/v3/trial-ledger.csv")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = canonical_params(params)
    if path.exists():
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                if row.get("arm") == arm and row.get("params") == encoded and row.get("segment") == segment:
                    return False
    new_file = not path.exists()
    row = {
        "run_at": datetime.now(TAIPEI).isoformat(timespec="seconds"),
        "git_sha": git_head() or "",
        "arm": arm,
        "params": encoded,
        "segment": segment,
        "runner": runner,
    }
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        if new_file:
            writer.writeheader()
        writer.writerow(row)
    return True

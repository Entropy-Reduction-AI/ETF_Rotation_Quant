"""把设计期过关草稿收成入围结论。不改前面各条的通过与否。"""
from __future__ import annotations

import csv
from pathlib import Path

from .params import V51Error

ROOT = Path(__file__).resolve().parents[2]
DRAFT = ROOT / "results" / "v5.1" / "design" / "gate-draft.csv"
FINAL = ROOT / "results" / "v5.1" / "design" / "gate.csv"
NOTE = "v5.1 不入围。第 5 条和第 6 条未通过。第 2 条通过，A1 退路不启用。入围名单 = B0。"


def _scored(rows: list[dict], item: str) -> list[dict]:
    return [row for row in rows if row.get("item") == item and row.get("status") in {"通过", "未通过"}]


def conclude(rows: list[dict]) -> list[dict]:
    """最后一行写成 §6.3 的入围结论。其余行原样返回。"""
    if not rows or rows[-1].get("item") != "入围":
        raise V51Error("过关表最后一行不是入围")
    fives = _scored(rows, "5")
    if not fives or any(row["status"] != "未通过" for row in fives):
        raise V51Error("第 5 条不是未通过，不能写成 v5.1 不入围")
    six = [row for row in rows if row.get("item") == "6" and row.get("metric") in {"p_bull", "rebound_t"}]
    if len(six) != 2 or any(row["status"] != "未通过" for row in six):
        raise V51Error("第 6 条不是未通过，不能写成 v5.1 不入围")
    twos = _scored(rows, "2")
    if not twos or any(row["status"] != "通过" for row in twos):
        raise V51Error("第 2 条不是通过，不能写成 A1 退路不启用")
    out = [dict(row) for row in rows]
    final = out[-1]
    final["status"] = "不入围"
    final["strategy"] = "B0"
    final["benchmark"] = ""
    final["hurdle"] = "0–6"
    final["note"] = NOTE
    return out


def write_gate(*, draft: Path = DRAFT, dest: Path = FINAL) -> dict:
    """从 gate-draft.csv 写出 gate.csv。不改草稿。"""
    if not draft.is_file():
        raise V51Error("还没有过关草稿")
    with draft.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        rows = conclude(list(reader))
    if not fields:
        raise V51Error("过关表没有表头")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return {"path": str(dest.relative_to(ROOT)), "status": rows[-1]["status"], "note": rows[-1]["note"]}

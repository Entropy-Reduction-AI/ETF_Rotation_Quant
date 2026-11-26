"""从 Ken French 49 行业原件里只取出 1926-07 至 1998-12。

晚于 1998-12 的行不转成数字。原件整文件只做不透明保存和 SHA256，不进这个函数的结果。
"""

from __future__ import annotations

import csv
import io

PANELS = (
    "Average Value Weighted Returns -- Monthly",
    "Number of Firms in Portfolios",
    "Average Firm Size",
)
START = 192607
END = 199812


def extract_panels(lines) -> dict[str, list[dict[str, str]]]:
    """lines 是文本行。只解析上面三块里日期落在闭区间内的行。"""
    wanted = set(PANELS)
    out = {name: [] for name in PANELS}
    current = None
    columns: list[str] = []
    for raw in lines:
        line = raw.strip()
        if current is None:
            if line in wanted:
                current = line
                columns = []
            continue
        if not line:
            current = None
            columns = []
            continue
        if not columns:
            header = next(csv.reader([line]))
            columns = [cell.strip() for cell in header[1:]]
            continue
        date = line.split(",", 1)[0].strip()
        if not (len(date) == 6 and date.isdigit()):
            current = None
            columns = []
            continue
        stamp = int(date)
        if stamp < START or stamp > END:
            # 区间外的格子不解析。块继续往下走，直到空行。
            continue
        values = next(csv.reader([line]))
        row = {"yyyymm": date}
        for name, value in zip(columns, values[1:]):
            row[name] = value.strip()
        out[current].append(row)
    return out


def write_panels(panels: dict[str, list[dict[str, str]]], directory) -> None:
    from pathlib import Path

    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for name, rows in panels.items():
        if not rows:
            raise ValueError(f"没有解析到 {name}")
        dates = [int(row["yyyymm"]) for row in rows]
        if min(dates) < START or max(dates) > END:
            raise ValueError(f"{name} 日期越出 192607–199812")
        path = directory / f"{_slug(name)}.csv"
        fields = list(rows[0])
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)


def _slug(title: str) -> str:
    return {
        "Average Value Weighted Returns -- Monthly": "vw-monthly",
        "Number of Firms in Portfolios": "n-firms",
        "Average Firm Size": "avg-firm-size",
    }[title]


def load_text(path) -> list[str]:
    """给测试和命令行用。调用方负责只把允许解析的原件传进来。"""
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        return handle.readlines()

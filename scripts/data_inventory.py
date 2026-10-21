"""从 data/market.sqlite 与 data/universe.csv 生成 docs/data-inventory.md。

统计数字只来自这两份文件。已知空窗和 T12 身份说明是登记文本，脚本只核对库里的对应事实。
"""
from __future__ import annotations

import csv
import hashlib
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "market.sqlite"
UNI_PATH = ROOT / "data" / "universe.csv"
OUT_PATH = ROOT / "docs" / "data-inventory.md"
SOURCE_COMMIT = "fa70cb709738dad3ebf426a71959943abe88fd0e"

EXPECTED_SHA = {
    "data/market.sqlite": "b56148daf640d4bca6bbd2856a9c36fd9a11472ea9ebe94753476e0bb02e5290",
    "data/universe.csv": "cb73f8daab938cda538eab02e8ac539cba129d90672d6757b3df93f55c374178",
}
PANEL = {"retained", "flagged"}
MISSING_RESEARCH = {"T16", "T36", "T38"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def caliber(price_only: str) -> str:
    if price_only == "False":
        return "全收益"
    if price_only == "True":
        return "价格"
    if price_only == "n/a":
        return "非指数（price_only=n/a）"
    return "无研究序列"


def md_cell(value: str) -> str:
    return (value or "—").replace("|", "\\|").replace("\n", " ")


def main() -> int:
    problems: list[str] = []
    file_rows = []
    for rel, expected in EXPECTED_SHA.items():
        path = ROOT / rel
        digest = sha256(path)
        size = path.stat().st_size
        same = digest == expected
        if not same:
            problems.append(f"{rel} SHA256 {digest} != {expected}")
        file_rows.append((rel, size, digest, "一致" if same else "不一致"))

    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    series = list(con.execute(
        """
        SELECT code, adj, min(source) AS source, min(date) AS start, max(date) AS end, count(*) AS n
          FROM bars
         GROUP BY code, adj
         ORDER BY code, adj
        """
    ))
    bar_rows = con.execute("SELECT count(*), max(date) FROM bars").fetchone()
    sources = {row["source"] for row in series}
    multi = con.execute(
        "SELECT code, adj, count(DISTINCT source) AS n FROM bars GROUP BY code, adj HAVING n > 1"
    ).fetchall()
    if multi:
        problems.append(f"多来源序列: {multi}")
    calendar = con.execute("SELECT min(date), max(date), count(*) FROM calendar").fetchone()
    coverage = {
        row["theme_id"]: row
        for row in con.execute("SELECT * FROM coverage_latest")
    }
    con.close()

    if len(series) != 87:
        problems.append(f"序列数 {len(series)} != 87")
    if bar_rows[0] != 309275:
        problems.append(f"bars 行数 {bar_rows[0]} != 309275")
    if bar_rows[1] != "2026-09-30":
        problems.append(f"bars 末日 {bar_rows[1]} != 2026-09-30")
    if sum(row["n"] for row in series) != bar_rows[0]:
        problems.append("序列行数合计与 bars 总行数不一致")
    if calendar[1] != "2026-12-31":
        problems.append(f"calendar 末日 {calendar[1]} != 2026-12-31")

    with UNI_PATH.open(encoding="utf-8", newline="") as f:
        universe = list(csv.DictReader(f))
    if len(universe) != 39:
        problems.append(f"universe 行数 {len(universe)} != 39")

    panel = [row for row in universe if row["status"] in PANEL]
    outside = [row for row in universe if row["status"] not in PANEL]
    if len(panel) != 37:
        problems.append(f"面板容器 {len(panel)} != 37")

    missing = []
    ready = []
    container_lines = []
    for row in panel:
        theme_id = row["theme_id"]
        cov = coverage.get(theme_id)
        series_code = (cov["series_code"] if cov else "") or ""
        series_adj = (cov["series_adj"] if cov else "") or ""
        price_only = (cov["price_only"] if cov else "") or ""
        if not series_code:
            missing.append(theme_id)
            adopted = "—"
            start = "—"
            kind = "无研究序列"
        else:
            hit = next((s for s in series if s["code"] == series_code and s["adj"] == series_adj), None)
            if hit is None:
                problems.append(f"{theme_id} 研究序列 {series_code}/{series_adj} 不在 bars")
                adopted = f"{series_code}/{series_adj}"
                start = "—"
                kind = caliber(price_only)
            else:
                ready.append(theme_id)
                adopted = f"{series_code}/{series_adj}"
                start = hit["start"]
                kind = caliber(price_only)
                if hit["source"] != (cov["route_used"] or ""):
                    problems.append(
                        f"{theme_id} bars source {hit['source']} != coverage route_used {cov['route_used']}"
                    )
        container_lines.append(
            "| {tid} | {name} | {status} | {research} | {adopted} | {kind} | {start} | {exec_code} |".format(
                tid=md_cell(theme_id),
                name=md_cell(row["theme"]),
                status=md_cell(row["status"]),
                research=md_cell(row["research_index_code"]),
                adopted=md_cell(adopted),
                kind=md_cell(kind),
                start=md_cell(start),
                exec_code=md_cell(row["execution_fund_code"]),
            )
        )

    if set(missing) != MISSING_RESEARCH:
        problems.append(f"缺研究序列的面板容器 {missing} != {sorted(MISSING_RESEARCH)}")
    if len(ready) != 34:
        problems.append(f"有研究序列的面板容器 {len(ready)} != 34")

    t12 = next(row for row in universe if row["theme_id"] == "T12")
    t12_cov = coverage["T12"]
    if t12["execution_fund_code"] != "159732" or t12_cov["series_code"] != "931494":
        problems.append(
            f"T12 事实不符: exec={t12['execution_fund_code']} series={t12_cov['series_code']}"
        )
    for theme_id in ("T36", "T38", "T16"):
        cov = coverage.get(theme_id)
        if cov and (cov["series_code"] or ""):
            problems.append(f"{theme_id} 不应有研究序列")

    outside_lines = []
    for row in outside:
        cov = coverage.get(row["theme_id"])
        series_code = (cov["series_code"] if cov else "") or ""
        outside_lines.append(
            "| {tid} | {name} | {status} | {research} | {series} | {exec_code} |".format(
                tid=md_cell(row["theme_id"]),
                name=md_cell(row["theme"]),
                status=md_cell(row["status"]),
                research=md_cell(row["research_index_code"]),
                series=md_cell(series_code or "—"),
                exec_code=md_cell(row["execution_fund_code"]),
            )
        )

    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1

    def coverage_error(theme_id: str) -> str:
        text = " ".join(((coverage[theme_id]["error"] or "").split()))
        if len(text) > 160:
            text = text[:157] + "..."
        return text or "（coverage 无 error 文本）"

    declared_gaps = {
        "T36": "早期空窗登记为 2019 – 2022-03。",
        "T38": "早期空窗登记为 2020-07-27 – 2021-10-11。",
    }
    gap_lines = []
    for theme_id in ("T16", "T36", "T38"):
        note = declared_gaps.get(theme_id, "")
        note = f"{note} " if note else ""
        gap_lines.append(
            f"- {theme_id}：没有研究序列。{note}coverage error：{coverage_error(theme_id)}"
        )
    gap_lines.append(
        "- T12：执行基金 `159732` 身份有误。研究序列是中证 `931494`"
        f"（`{t12_cov['series_code']}/{t12_cov['series_adj']}`，口径为{caliber(t12_cov['price_only'])}），"
        "不受这只执行基金的身份影响。"
    )
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
    series_lines = [
        f"| {md_cell(row['code'])} | {md_cell(row['adj'])} | {md_cell(row['source'])} | {row['start']} | {row['end']} | {row['n']} |"
        for row in series
    ]
    file_lines = [
        f"| `{rel}` | {size} | `{digest}` | {same} |"
        for rel, size, digest, same in file_rows
    ]
    text = f"""# 数据清单

## Metadata

- Project: ETF_Rotation_Quant
- Document type: other
- Status: active
- Owner: project owner
- Last updated: {today}
- Source of truth: `data/market.sqlite`、`data/universe.csv`，对照来源提交 `{SOURCE_COMMIT}`

## Purpose

登记 R1 迁入的两份研究数据：文件哈希、bars 序列、37 个面板容器，以及必须声明的四项数据陷阱。

## Scope

统计由 `scripts/data_inventory.py` 对当前仓库里的库和 CSV 直接计算。本文不给出回测或样本外结论。

## 复现

```bash
.venv/bin/python scripts/data_inventory.py
```

命令覆写本文件。下面的行数、日期、哈希和口径都来自这次运行；空窗日期和 T12 身份是登记说明，脚本只核对库里没有对应研究序列、以及 T12 的研究序列仍是 `931494`。

## 文件

对照哈希是 fa70cb7 上这两个路径的 SHA256。

| 文件 | 字节数 | SHA256 | 与 fa70cb7 |
| --- | --- | --- | --- |
{chr(10).join(file_lines)}

## bars 与 calendar

bars 共 {len(series)} 个序列（`code` + `adj`）、{bar_rows[0]} 行，末日 {bar_rows[1]}。来源集合：{", ".join(sorted(sources))}。

calendar 共 {calendar[2]} 行，起 {calendar[0]}，末日 {calendar[1]}。

| code | adj | source | 起始 | 终止 | 行数 |
| --- | --- | --- | --- | --- | --- |
{chr(10).join(series_lines)}

## 面板容器

`universe.csv` 共 {len(universe)} 行。状态为 `retained` 或 `flagged` 的面板容器 {len(panel)} 个，其中 {len(ready)} 个有研究序列，缺研究序列的是 {", ".join(missing)}。

研究指数代码来自 CSV 的 `research_index_code`。入库研究序列和起始日来自 `coverage_latest` 指向的 bars 序列；口径由 `price_only` 映射：`False` 为全收益，`True` 为价格，`n/a` 不是指数的价格/全收益口径。执行 ETF 代码来自 CSV 的 `execution_fund_code`。

| 容器 | 名称 | 状态 | 研究指数代码 | 入库研究序列 | 口径 | 研究序列起始日 | 执行 ETF |
| --- | --- | --- | --- | --- | --- | --- | --- |
{chr(10).join(container_lines)}

### 不在面板里的 CSV 行

这两行不计入 37 个面板容器，库里也没有研究序列。

| 容器 | 名称 | 状态 | 研究指数代码 | 入库研究序列 | 执行 ETF |
| --- | --- | --- | --- | --- | --- |
{chr(10).join(outside_lines)}

## 已知空窗与身份

以下日期不是从 bars 聚合出来的区间。脚本核对的事实是：T16、T36、T38 的 `series_code` 为空，bars 里没有它们的研究序列。

{chr(10).join(gap_lines)}

## 四项数据陷阱

- 主题指数回填。
- 指数和 ETF 差异按年 1% 打折。
- 腾讯 qfq 是减法复权，不能直接算收益。
- 份额折算造成 −50% 到 −65% 的假跳空。

## Related Files

- `data/market.sqlite`
- `data/universe.csv`
- `scripts/data_inventory.py`
- `docs/data-layer.md`
- `docs/project-intake/etf-rotation-quant.md`
"""
    OUT_PATH.write_text(text, encoding="utf-8")
    print(f"wrote {OUT_PATH.relative_to(ROOT)}")
    print(f"series={len(series)} rows={bar_rows[0]} bars_end={bar_rows[1]} calendar_end={calendar[1]}")
    print(f"panel={len(panel)} with_series={len(ready)} missing={','.join(missing)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

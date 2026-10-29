"""场内基金后复权的唯一读取入口（D22-1 / D22-2 / D22-3）。

研究和回测要后复权收盘时只走这里，不自己挑 `bars` 或 `v4_series` 的来源。

顺序（D22-1）：东财后复权 → 腾讯后复权（含按比例延长的尾部）→ D21 还原。

- 东财：`bars.adj=hfq`（来源只能是 `eastmoney_etf_hfq`）。`v4_series` 里同名来源只补 bars 没有的日期；重叠日用 bars（D22-3）。
- 腾讯：`v4_series.kind=backward` 的 `tencent_etf_hfq` 与 `tencent_etf_hfq_carry` 合成一条。重叠日用腾讯原序列，延长尾部只填空日期。
- D21：有 `kind=backward_rebuild` 用它；否则用 `kind=backward` 且 `source=还原`。

这三条都没有、且 `kind=backward` 只剩一种来源（`eastmoney_fhsp`、`yahoo`，或测试夹具没有 source 列）时，用那一条。剩下两种以上时不自动挑。

同一只有两条以上上述来源时，`return_conflicts` 只列出日收益差超过 0.1 个百分点的日期（D22-2）。清单不改选用的那一条，也不按日换源。
"""
from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

# 0.1 个百分点。日收益用小数，比较时换成百分点并收到 6 位，刚好 0.1 不算超过。
DIFF_PP = 0.1
_PP_DECIMALS = 6
PRIORITY = ("eastmoney", "tencent", "d21")
TENCENT_BASE = "tencent_etf_hfq"
TENCENT_CARRY = "tencent_etf_hfq_carry"
TENCENT_SOURCES = (TENCENT_BASE, TENCENT_CARRY)
EASTMONEY_SOURCE = "eastmoney_etf_hfq"
REBUILD_SOURCE = "还原"
REBUILD_KIND = "backward_rebuild"
# 不在三条顺序里。只在前三条都没有、且只剩这一种时才用作那一条序列。
SOLE_SOURCES = ("eastmoney_fhsp", "yahoo")
COMPARE_END = "2026-09-30"
OUT = Path(__file__).resolve().parents[3] / "results" / "v4" / "inventory" / "r5"
DEFAULT_CODES = ("160125", "160644")

SOURCE_COLUMNS = (
    "code", "tier", "source", "rows", "first", "last", "selected",
)
CONFLICT_COLUMNS = (
    "code", "date", "left_tier", "right_tier",
    "left_return", "right_return", "diff_return", "diff_pp",
)


@dataclass(frozen=True)
class HfqRead:
    """选用的那一条后复权。`tier` 为空表示有多条剩余来源，没有自动挑。"""

    code: str
    tier: str
    closes: pd.Series
    parts: tuple[str, ...]


def _columns(con: sqlite3.Connection, table: str) -> set[str]:
    rows = con.execute(f"PRAGMA table_info({table})").fetchall()
    return {str(row[1]) for row in rows}


def _series(mapping: dict[str, float]) -> pd.Series:
    if not mapping:
        return pd.Series(dtype=float)
    days = sorted(mapping)
    values = [mapping[day] for day in days]
    index = pd.to_datetime(days)
    series = pd.Series(values, index=index, dtype=float)
    return series[~series.index.duplicated(keep="first")].sort_index()


def _put(mapping: dict[str, float], day: str, close: float) -> None:
    if day not in mapping and close is not None and float(close) > 0:
        mapping[day] = float(close)


def load_priority(con: sqlite3.Connection, code: str, end: str) -> dict[str, pd.Series]:
    """三条顺序里实际有收盘的序列。键只有 eastmoney / tencent / d21。"""
    found: dict[str, pd.Series] = {}
    bars_cols = _columns(con, "bars")
    series_cols = _columns(con, "v4_series")
    eastmoney: dict[str, float] = {}
    if {"code", "adj", "date", "close"} <= bars_cols:
        for day, close in con.execute(
                """SELECT date, close FROM bars
                   WHERE code = ? AND adj = 'hfq' AND close > 0 AND date <= ?
                   ORDER BY date""",
                (code, end)):
            _put(eastmoney, str(day), close)
    v4_east: dict[str, float] = {}
    if {"code", "kind", "date", "close", "source"} <= series_cols:
        for day, close in con.execute(
                """SELECT date, close FROM v4_series
                   WHERE code = ? AND kind = 'backward' AND source = ?
                     AND close > 0 AND date <= ?
                   ORDER BY date""",
                (code, EASTMONEY_SOURCE, end)):
            _put(v4_east, str(day), close)
    if eastmoney or v4_east:
        merged = dict(eastmoney)
        for day, close in v4_east.items():
            _put(merged, day, close)
        found["eastmoney"] = _series(merged)

    tencent: dict[str, float] = {}
    if {"code", "kind", "date", "close", "source"} <= series_cols:
        # 原序列排在延长尾部前面，重叠日先写入的原收盘留下来。
        for day, close, _source in con.execute(
                """SELECT date, close, source FROM v4_series
                   WHERE code = ? AND kind = 'backward' AND source IN (?, ?)
                     AND close > 0 AND date <= ?
                   ORDER BY date,
                            CASE source WHEN ? THEN 0 ELSE 1 END""",
                (code, TENCENT_BASE, TENCENT_CARRY, end, TENCENT_BASE)):
            _put(tencent, str(day), close)
    if tencent:
        found["tencent"] = _series(tencent)

    rebuild: dict[str, float] = {}
    if {"code", "kind", "date", "close"} <= series_cols:
        if "source" in series_cols:
            rows = con.execute(
                """SELECT date, close FROM v4_series
                   WHERE code = ? AND kind = ? AND close > 0 AND date <= ?
                   ORDER BY date""",
                (code, REBUILD_KIND, end)).fetchall()
            if not rows:
                rows = con.execute(
                    """SELECT date, close FROM v4_series
                       WHERE code = ? AND kind = 'backward' AND source = ?
                         AND close > 0 AND date <= ?
                       ORDER BY date""",
                    (code, REBUILD_SOURCE, end)).fetchall()
        else:
            rows = con.execute(
                """SELECT date, close FROM v4_series
                   WHERE code = ? AND kind = ? AND close > 0 AND date <= ?
                   ORDER BY date""",
                (code, REBUILD_KIND, end)).fetchall()
        for day, close in rows:
            _put(rebuild, str(day), close)
    if rebuild:
        found["d21"] = _series(rebuild)
    return found


def _sole_backward(con: sqlite3.Connection, code: str, end: str) -> HfqRead | None:
    """前三条都没有时，仅当 kind=backward 只剩一种来源才返回它。"""
    cols = _columns(con, "v4_series")
    if {"code", "kind", "date", "close"} > cols:
        return None
    if "source" not in cols:
        mapping: dict[str, float] = {}
        for day, close in con.execute(
                """SELECT date, close FROM v4_series
                   WHERE code = ? AND kind = 'backward' AND close > 0 AND date <= ?
                   ORDER BY date""",
                (code, end)):
            _put(mapping, str(day), close)
        if not mapping:
            return None
        return HfqRead(code, "unlabeled", _series(mapping), ("unlabeled",))
    groups: dict[str, dict[str, float]] = {}
    for day, close, source in con.execute(
            """SELECT date, close, source FROM v4_series
               WHERE code = ? AND kind = 'backward' AND close > 0 AND date <= ?
               ORDER BY date""",
            (code, end)):
        name = str(source or "")
        if name in {EASTMONEY_SOURCE, *TENCENT_SOURCES, REBUILD_SOURCE}:
            continue
        groups.setdefault(name, {})
        _put(groups[name], str(day), close)
    present = [name for name, mapping in groups.items() if mapping]
    if len(present) != 1:
        return None
    name = present[0]
    tier = name if name in SOLE_SOURCES else "other"
    return HfqRead(code, tier, _series(groups[name]), (name,))


def canonical_hfq(con: sqlite3.Connection, code: str, end: str) -> HfqRead | None:
    """按 D22-1 取第一条有收盘的后复权。冲突日不参与这个选择。"""
    priority = load_priority(con, code, end)
    for tier in PRIORITY:
        series = priority.get(tier)
        if series is not None and len(series):
            return HfqRead(code, tier, series, ())
    return _sole_backward(con, code, end)


def _parts(con: sqlite3.Connection, code: str, tier: str) -> tuple[str, ...]:
    if tier == "eastmoney":
        parts: list[str] = []
        cols = _columns(con, "bars")
        if {"code", "adj"} <= cols and con.execute(
                "SELECT 1 FROM bars WHERE code = ? AND adj = 'hfq' LIMIT 1", (code,)).fetchone():
            parts.append("bars.adj=hfq")
        series_cols = _columns(con, "v4_series")
        if "source" in series_cols and con.execute(
                """SELECT 1 FROM v4_series
                   WHERE code = ? AND kind = 'backward' AND source = ? LIMIT 1""",
                (code, EASTMONEY_SOURCE)).fetchone():
            parts.append(EASTMONEY_SOURCE)
        return tuple(parts) or (EASTMONEY_SOURCE,)
    if tier == "tencent":
        found = [row[0] for row in con.execute(
            """SELECT DISTINCT source FROM v4_series
               WHERE code = ? AND kind = 'backward' AND source IN (?, ?)
               ORDER BY source""",
            (code, TENCENT_BASE, TENCENT_CARRY))]
        return tuple(str(item) for item in found) or (TENCENT_BASE,)
    if tier == "d21":
        if con.execute(
                "SELECT 1 FROM v4_series WHERE code = ? AND kind = ? LIMIT 1",
                (code, REBUILD_KIND)).fetchone():
            return (REBUILD_KIND,)
        return (REBUILD_SOURCE,)
    return ()


def canonical_closes(con: sqlite3.Connection, code: str, end: str) -> pd.Series:
    chosen = canonical_hfq(con, code, end)
    if chosen is None or chosen.closes.empty:
        return pd.Series(dtype=float)
    return chosen.closes


def exceeds_diff(left: float, right: float, pp: float = DIFF_PP) -> bool:
    """日收益差换成百分点，收到 6 位小数后仍大于 0.1 才算超过。"""
    gap = round(abs(float(left) - float(right)) * 100, _PP_DECIMALS)
    return gap > pp


def daily_returns(closes: pd.Series) -> pd.Series:
    """用这条序列自己的前一根收盘。第一根没有收益。"""
    ordered = closes.sort_index()
    ordered = ordered[~ordered.index.duplicated(keep="first")]
    values = ordered.to_numpy(dtype=float)
    ordered = ordered[pd.notna(ordered) & (values > 0)]
    if len(ordered) < 2:
        return pd.Series(dtype=float)
    return ordered.astype(float) / ordered.astype(float).shift(1) - 1.0


def return_conflicts(code: str, series_by_tier: dict[str, pd.Series],
                     pp: float = DIFF_PP) -> list[dict]:
    """两条以上来源时，列出超过阈值的日期。不返回该用哪一条。"""
    names = [tier for tier in PRIORITY if tier in series_by_tier and len(series_by_tier[tier])]
    rows: list[dict] = []
    returns = {tier: daily_returns(series_by_tier[tier]).dropna() for tier in names}
    for left_i, left in enumerate(names):
        for right in names[left_i + 1:]:
            common = returns[left].index.intersection(returns[right].index)
            for day in common:
                left_ret = float(returns[left].loc[day])
                right_ret = float(returns[right].loc[day])
                if not exceeds_diff(left_ret, right_ret, pp):
                    continue
                diff = left_ret - right_ret
                rows.append({
                    "code": code,
                    "date": pd.Timestamp(day).strftime("%Y-%m-%d"),
                    "left_tier": left,
                    "right_tier": right,
                    "left_return": left_ret,
                    "right_return": right_ret,
                    "diff_return": diff,
                    "diff_pp": round(diff * 100, _PP_DECIMALS),
                })
    rows.sort(key=lambda item: (item["code"], item["date"], item["left_tier"], item["right_tier"]))
    return rows


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_csv(path: Path, columns: tuple[str, ...], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in columns})


def source_inventory(con: sqlite3.Connection) -> list[dict]:
    """每只基金每条后复权来源一行。没有日收益。`selected` 只反映 D22-1 的顺序。"""
    presence: dict[str, list[dict]] = {}

    def add(code: str, tier: str, source: str, rows: int, first: str, last: str) -> None:
        presence.setdefault(code, []).append({
            "code": code, "tier": tier, "source": source,
            "rows": int(rows), "first": first or "", "last": last or "",
        })

    if {"code", "adj", "date"} <= _columns(con, "bars"):
        for code, rows, first, last in con.execute(
                """SELECT code, COUNT(*), MIN(date), MAX(date)
                   FROM bars WHERE adj = 'hfq' AND close > 0
                   GROUP BY code"""):
            add(str(code), "eastmoney", "bars.adj=hfq", rows, first, last)
    cols = _columns(con, "v4_series")
    if {"code", "kind", "date"} <= cols:
        if "source" in cols:
            for code, kind, source, rows, first, last in con.execute(
                    """SELECT code, kind, source, COUNT(*), MIN(date), MAX(date)
                       FROM v4_series
                       WHERE kind IN ('backward', 'backward_rebuild') AND close > 0
                       GROUP BY code, kind, source"""):
                tier = _inventory_tier(str(kind), str(source))
                if tier is None:
                    continue
                add(str(code), tier, str(source), rows, first, last)
        else:
            for code, rows, first, last in con.execute(
                    """SELECT code, COUNT(*), MIN(date), MAX(date)
                       FROM v4_series
                       WHERE kind = 'backward' AND close > 0
                       GROUP BY code"""):
                add(str(code), "unlabeled", "unlabeled", rows, first, last)
    chosen: dict[str, str] = {}
    for code, items in presence.items():
        tiers = {item["tier"] for item in items}
        pick = next((tier for tier in PRIORITY if tier in tiers), "")
        if not pick:
            others = sorted(tier for tier in tiers if tier not in PRIORITY)
            pick = others[0] if len(others) == 1 else ""
        chosen[code] = pick
    out = []
    for code in sorted(presence):
        for item in sorted(presence[code], key=lambda row: (row["tier"], row["source"], row["first"])):
            item["selected"] = "1" if item["tier"] == chosen[code] and chosen[code] else "0"
            out.append(item)
    return out


def _inventory_tier(kind: str, source: str) -> str | None:
    if kind == REBUILD_KIND:
        return "d21"
    if kind != "backward":
        return None
    if source == EASTMONEY_SOURCE:
        return "eastmoney"
    if source in TENCENT_SOURCES:
        return "tencent"
    if source == REBUILD_SOURCE:
        return "d21"
    if source in SOLE_SOURCES:
        return source
    if source:
        return "other"
    return "unlabeled"


def conflict_frame(con: sqlite3.Connection, codes: tuple[str, ...] | list[str],
                   end: str = COMPARE_END) -> list[dict]:
    rows: list[dict] = []
    for code in codes:
        rows.extend(return_conflicts(code, load_priority(con, code, end)))
    return rows


def write_r5(con: sqlite3.Connection, codes: tuple[str, ...] = DEFAULT_CODES,
             out_dir: Path = OUT, end: str = COMPARE_END,
             hashed: list[dict] | None = None) -> dict:
    """写出源清单和指定代码的冲突日。不写数据库。"""
    out_dir = Path(out_dir)
    sources = source_inventory(con)
    conflicts = conflict_frame(con, codes, end)
    source_path = out_dir / "hfq-sources.csv"
    conflict_path = out_dir / "hfq-return-conflicts.csv"
    _write_csv(source_path, SOURCE_COLUMNS, sources)
    conflict_out = []
    for row in conflicts:
        conflict_out.append({
            **row,
            "left_return": f"{row['left_return']:.10f}",
            "right_return": f"{row['right_return']:.10f}",
            "diff_return": f"{row['diff_return']:.10f}",
            "diff_pp": f"{row['diff_pp']:.6f}",
        })
    _write_csv(conflict_path, CONFLICT_COLUMNS, conflict_out)
    by_code: dict[str, dict] = {}
    for code in codes:
        priority = load_priority(con, code, end)
        chosen = canonical_hfq(con, code, end)
        listed = [row for row in conflicts if row["code"] == code]
        max_pp = max((abs(row["diff_pp"]) for row in listed), default=0.0)
        parts = list(chosen.parts) if chosen and chosen.parts else []
        if chosen and chosen.tier in PRIORITY:
            parts = list(_parts(con, code, chosen.tier))
        by_code[code] = {
            "canonical_tier": chosen.tier if chosen else "",
            "parts": parts,
            "tiers_present": [tier for tier in PRIORITY if tier in priority],
            "conflict_days": len(listed),
            "max_abs_diff_pp": max_pp,
            "dates": [row["date"] for row in listed],
        }
    summary = {
        "rule": "D22-1 按东财 → 腾讯（含按比例延长的尾部）→ D21 还原选用。"
                "D22-2 只列出日收益差超过 0.1 个百分点的日期，不据此改选用，也不按日换源。"
                "D22-3：bars.adj=hfq 仍只是东财；腾讯和还原留在 v4_series。",
        "diff_pp": DIFF_PP,
        "compare_end": end,
        "codes": list(codes),
        "by_code": by_code,
        "conflict_rows": len(conflicts),
        "source_rows": len(sources),
        "files": {
            "hfq-sources.csv": _sha256(source_path),
            "hfq-return-conflicts.csv": _sha256(conflict_path),
        },
        "hashed": hashed or [],
        "database_written": False,
    }
    summary_path = out_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    """只读库，写出 results/v4/inventory/r5。不算组合收益。"""
    import sys

    from src.data import db as DB

    args = list(sys.argv[1:] if argv is None else argv)
    if any(token in {"backtest", "returns", "pnl", "timing"} for token in args):
        print("后复权入口只读序列、只列来源差，不算组合收益。")
        return 2
    codes = tuple(args) or DEFAULT_CODES
    root = Path(__file__).resolve().parents[3]
    db_path = DB.MARKET_DB
    hashed = []
    for rel in ("data/market.sqlite", "config/v3/universe.toml", "config/v4/universe.toml"):
        path = root / rel
        hashed.append({"path": rel, "sha256": _sha256(path), "bytes": path.stat().st_size})
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        summary = write_r5(con, codes, hashed=hashed)
    finally:
        con.close()
    print(json.dumps({"codes": summary["by_code"], "files": summary["files"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

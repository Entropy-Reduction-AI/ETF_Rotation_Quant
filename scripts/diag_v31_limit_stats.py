"""设计期可交易池：计划买入日是否收盘涨停，计划离场日是否收盘跌停或无价。

统计表写到 results/v3/diag/2026-10-27-limit-stats/。
不改成交假设，不写 trial-ledger，不写 LOCK，不把组合收益落盘。
结束日固定 2015-12-31。行情查询同样截在这一天。
"""
from __future__ import annotations

import hashlib
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from src.data import db as DB
from src.v3.data.universe import containers as load_containers
from src.v3.diag.limit_close import (
    DESIGN_END,
    at_limits,
    limit_prices,
    mark_planned_fill,
    quote_pair,
)
from src.v3.engine.arms import execute
from src.v3.engine.book import drift
from src.v3.engine.market import load_market
from src.v3.engine.spec import LEDGER, LOCK, load_spec
from src.v3.engine.universe import execution_code, pool_members

OUT = ROOT / "results" / "v3" / "diag" / "2026-10-27-limit-stats"
RUNS = (
    ("P6", "A", "official"),
    ("P7", "A", "publish_date"),
    ("P8", "S1", "official"),
    ("P9", "S2", "official"),
    ("P10", "B", "official"),
)
SAVED = ROOT / "results" / "v3" / "design-period" / "9b421c0294a8509e5283aa871034ff0e8ed66c75"
KNOWN_DAYS = {"2015-06-29", "2015-08-24"}


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _paths(arm: str, book):
    if arm == "B" or not book.paths:
        yield "executed", book
        return
    for key, path in book.paths.items():
        label = f"{key[0]}-{key[1]}" if isinstance(key, tuple) else str(key)
        yield label, path


def _next_session(calendar: pd.DatetimeIndex, day) -> pd.Timestamp | None:
    pos = int(calendar.searchsorted(pd.Timestamp(day), side="right"))
    if pos >= len(calendar):
        return None
    return pd.Timestamp(calendar[pos])


def _saved_signals(run_id: str) -> set[tuple[str, str, str]]:
    frame = pd.read_csv(SAVED / run_id / "exits.csv")
    if "path" not in frame.columns:
        frame["path"] = "executed"
    signals = frame[frame["kind"].eq("signal")]
    return {
        (str(row.path), str(pd.Timestamp(row.date).date()), str(row.name))
        for row in signals.itertuples(index=False)
    }


def _load_closes(codes: list[str]) -> dict[str, pd.Series]:
    if not codes:
        return {}
    frames = []
    con = sqlite3.connect(DB.MARKET_DB)
    try:
        for offset in range(0, len(codes), 400):
            chunk = codes[offset:offset + 400]
            marks = ",".join("?" * len(chunk))
            frames.append(pd.read_sql_query(
                "SELECT code, date, close FROM bars WHERE adj = 'raw' AND date <= ? "
                f"AND code IN ({marks})",
                con,
                params=[DESIGN_END, *chunk],
            ))
    finally:
        con.close()
    frame = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["code", "date", "close"])
    if frame.empty:
        return {}
    frame["date"] = pd.to_datetime(frame["date"])
    out = {}
    for code, block in frame.groupby("code", sort=False):
        series = pd.Series(block["close"].to_numpy(dtype=float), index=pd.DatetimeIndex(block["date"]))
        series = series[~series.index.duplicated(keep="last")].sort_index()
        out[str(code)] = series
    return out


def _event(run_id, arm, mode, path, side, container, code, signal, fill, series) -> dict:
    prev, close = (None, None)
    if fill is not None and code:
        prev, close = quote_pair(series, fill)
    if fill is None:
        mark = "no_next_session"
        at_up = at_down = False
        up = down = ""
        simple = ""
    elif not code:
        mark = "no_code"
        at_up = at_down = False
        up = down = ""
        simple = ""
    else:
        mark = mark_planned_fill(prev, close, side)
        at_up, at_down = at_limits(prev, close)
        if prev is not None and prev > 0:
            limit_up, limit_down = limit_prices(prev)
            up, down = f"{limit_up}", f"{limit_down}"
            simple = "" if close is None else f"{close / prev - 1.0:.6f}"
        else:
            up = down = ""
            simple = ""
    return {
        "run_id": run_id,
        "arm": arm,
        "pool": "tradable",
        "history_mode": mode,
        "path": path,
        "side": side,
        "container": container,
        "code": code or "",
        "signal_date": "" if signal is None else str(pd.Timestamp(signal).date()),
        "planned_fill": "" if fill is None else str(pd.Timestamp(fill).date()),
        "prev_close": "" if prev is None else f"{prev:.4f}",
        "close": "" if close is None else f"{close:.4f}",
        "limit_up": up,
        "limit_down": down,
        "simple_return": simple,
        "at_limit_up": int(at_up),
        "at_limit_down": int(at_down),
        "mark": mark,
    }


def _codes_for(path_book, container: str, day, fallback: str | None) -> list[str]:
    audit = getattr(path_book, "code_audit", None)
    if isinstance(audit, pd.DataFrame) and not audit.empty and "container" in audit.columns:
        stamp = pd.Timestamp(day).normalize()
        dates = pd.to_datetime(audit["date"]).dt.normalize()
        part = audit.loc[(audit["container"].astype(str) == container) & dates.eq(stamp)]
        found = list(dict.fromkeys(str(code) for code in part["code"].tolist() if str(code)))
        if found:
            return found
    return [fallback] if fallback else [""]


def _collect(run_id: str, arm: str, mode: str, spec, closes: dict[str, pd.Series]) -> list[dict]:
    end = pd.Timestamp(DESIGN_END)
    members = pool_members(load_containers(), arm, "tradable")
    code_of = {str(row["id"]): execution_code(row) for row in members}
    market = load_market(
        DB.MARKET_DB, load_containers(), arm, "tradable", end, spec,
        cost_multiplier=1.0, allow_after=False, history_mode=mode,
    )
    if len(market.dates) and pd.Timestamp(market.dates.max()) > end:
        raise RuntimeError(f"{run_id} 行情越过 {DESIGN_END}")
    book = execute(market, spec, arm, allow_after=False, exit_drawdown=0.10, premium_spec=None)
    if len(book.net) and pd.Timestamp(book.net.index.max()) > end:
        raise RuntimeError(f"{run_id} 组合收益越过 {DESIGN_END}")
    fresh = set()
    rows = []
    calendar = pd.DatetimeIndex(market.dates)
    for label, path in _paths(arm, book):
        exits = path.exits
        if isinstance(exits, pd.DataFrame) and not exits.empty:
            for record in exits.itertuples(index=False):
                if record.kind != "signal":
                    continue
                signal = pd.Timestamp(record.date).normalize()
                fresh.add((label, str(signal.date()), str(record.name)))
                fill = _next_session(calendar, signal)
                for code in _codes_for(path, str(record.name), signal, code_of.get(str(record.name))):
                    rows.append(_event(
                        run_id, arm, mode, label, "exit", str(record.name), code,
                        signal, fill, closes.get(code),
                    ))
        targets = path.targets
        if targets is None or targets.empty:
            continue
        held = path.held
        for day, target in targets.iterrows():
            stamp = pd.Timestamp(day).normalize()
            if stamp not in held.index or stamp not in market.pnl.index:
                continue
            start = {name: float(held.at[stamp, name]) for name in held.columns}
            rets = {}
            for name in held.columns:
                value = market.pnl.at[stamp, name] if name in market.pnl.columns else 0.0
                try:
                    number = float(value)
                except (TypeError, ValueError):
                    number = float("nan")
                rets[name] = 0.0 if number != number else number
            _gross, drifted = drift(start, rets)
            for name in held.columns:
                if name == market.cash_id or name not in target.index:
                    continue
                change = float(target[name]) - float(drifted.get(name, 0.0))
                if change <= spec.trade_eps:
                    continue
                for code in _codes_for(path, str(name), stamp, code_of.get(str(name))):
                    rows.append(_event(
                        run_id, arm, mode, label, "buy", str(name), code,
                        _previous(calendar, stamp), stamp, closes.get(code),
                    ))
    saved = _saved_signals(run_id)
    if fresh != saved:
        missing = sorted(saved - fresh)[:8]
        extra = sorted(fresh - saved)[:8]
        raise RuntimeError(f"{run_id} 离场信号与已落盘 exits.csv 不一致 missing={missing} extra={extra}")
    print(f"{run_id} signals={len(fresh)} events={len(rows)}", file=sys.stderr)
    return rows


def _previous(calendar: pd.DatetimeIndex, day) -> pd.Timestamp | None:
    pos = int(calendar.searchsorted(pd.Timestamp(day), side="left")) - 1
    if pos < 0:
        return None
    return pd.Timestamp(calendar[pos])


def _readme(events: pd.DataFrame, summary: pd.DataFrame) -> str:
    known = events[
        events["side"].eq("exit")
        & events["planned_fill"].isin(KNOWN_DAYS)
        & events["mark"].eq("close_limit_down")
    ]
    lines = [
        "# 设计期可交易池：计划成交日的涨跌停与无价",
        "",
        "统计日 2026-10-27。只描述计划成交日的原始收盘，不改回测成交假设。",
        "组合收益没有落盘，结束日全部 ≤ 2015-12-31。",
        "",
        "## 怎么判",
        "",
        "- 计划买入日 = 常规调仓的成交日（决策日的下一上交所交易日）。权重比当日漂移后的持仓增加，记一笔买入。",
        "- 计划离场日 = 离场信号日的下一上交所交易日。信号来自各路账本的 `kind=signal`，不是已经成交的 `kind=exit`。",
        "- 收盘涨停：当日原始收盘等于前一笔原始收盘 × 1.10，四舍五入到 0.001 元。买入才把这个记成受阻。",
        "- 收盘跌停：同样规则的 × 0.90。离场才把这个记成受阻。",
        "- 无价：计划成交日该代码没有正的有限原始收盘。",
        "- 设计期里本池 ETF 用 ±10%。创业板 ±20% 从 2020-08-24 才开始，不套到 2015 年。",
        "- 代码用登记表里的第一只执行基金；若该路当天的代码审计里有持仓代码，用审计里的代码。",
        "",
        "## 分运行合计",
        "",
        summary.to_csv(index=False).rstrip(),
        "",
        "## 已知的离场日收盘跌停",
        "",
        "2015-06-29 与 2015-08-24 在可交易池的计划离场里出现收盘跌停。",
        "下面每一行是一条路径上的一笔计划卖出，不是指数本身。",
        "",
        known.sort_values(["planned_fill", "run_id", "path", "container"]).to_csv(index=False).rstrip(),
        "",
        "P6（A / 可交易 / 官方）的 173 个离场信号里，计划卖出日收盘跌停的笔数应与 2026-10-27 诊断里的 22 笔一致。",
        "成交仍按现有规则用收盘价。要不要改成顺延，留给 v4。",
        "",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    if LOCK.exists():
        raise SystemExit("results/v3/LOCK 已存在，本脚本不运行")
    ledger_before = _sha(LEDGER) if LEDGER.exists() else ""
    spec = load_spec()
    codes = sorted({
        execution_code(row)
        for arm in ("A", "S1", "S2")
        for row in pool_members(load_containers(), arm, "tradable")
        if execution_code(row)
    })
    closes = _load_closes(codes)
    events = []
    for run_id, arm, mode in RUNS:
        events.extend(_collect(run_id, arm, mode, spec, closes))
    frame = pd.DataFrame(events)
    if frame.empty:
        raise SystemExit("没有计划成交")
    late = frame["planned_fill"].replace("", pd.NA).dropna()
    if not late.empty and pd.to_datetime(late).max() > pd.Timestamp(DESIGN_END):
        raise SystemExit("计划成交日晚于 2015-12-31")
    summary = (
        frame.groupby(["run_id", "arm", "history_mode", "side", "mark"], dropna=False)
        .size()
        .rename("n")
        .reset_index()
        .sort_values(["run_id", "side", "mark"])
    )
    OUT.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUT / "events.csv", index=False)
    summary.to_csv(OUT / "summary.csv", index=False)
    (OUT / "README.md").write_text(_readme(frame, summary), encoding="utf-8")
    if LOCK.exists():
        raise SystemExit("脚本运行过程中出现了 LOCK")
    ledger_after = _sha(LEDGER) if LEDGER.exists() else ""
    if ledger_before != ledger_after:
        raise SystemExit("trial-ledger.csv 被改动")
    p6 = frame[(frame["run_id"] == "P6") & frame["side"].eq("exit") & frame["mark"].eq("close_limit_down")]
    p6_orders = p6.drop_duplicates(["path", "container", "signal_date"])
    if len(p6_orders) != 22:
        raise SystemExit(f"P6 收盘跌停离场应为 22，实际 {len(p6_orders)}")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()

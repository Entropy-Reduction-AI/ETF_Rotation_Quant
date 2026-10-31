"""设计期内单日涨跌超过 15% 且下一笔收益反向的清单（D25-9）。

只列清单。不把这些涨跌加总成年化，也不改序列。
「下一笔」是同一条序列里的下一次正收盘，并且这一天也在设计期内。
"""
from __future__ import annotations

import csv
from pathlib import Path

SPIKE = 0.15
DESIGN_END = "2015-12-31"
COLUMNS = (
    "code", "role", "container", "series_kind", "source", "date",
    "prev_close", "close", "ret", "next_date", "next_close", "next_ret",
    "two_day_ret", "earning_code", "held_b0_index", "held_b0_tradable",
    "affects_holding", "note",
)


def reversal_spikes(rows: list[tuple[str, float]], *, threshold: float = SPIKE,
                    end: str = DESIGN_END) -> list[dict]:
    """按日期升序的 (日期, 收盘)。|当日收益| > threshold 且下一笔收益正负相反才记。"""
    usable = []
    for day, close in rows:
        if not day or day > end:
            continue
        if close is None:
            continue
        value = float(close)
        if not value > 0:
            continue
        usable.append((str(day), value))
    usable.sort()
    found = []
    for index in range(1, len(usable) - 1):
        _prev_day, prev = usable[index - 1]
        day, close = usable[index]
        next_day, nxt = usable[index + 1]
        ret = close / prev - 1.0
        next_ret = nxt / close - 1.0
        if abs(ret) <= threshold or ret * next_ret >= 0:
            continue
        found.append({
            "date": day,
            "prev_close": prev,
            "close": close,
            "ret": ret,
            "next_date": next_day,
            "next_close": nxt,
            "next_ret": next_ret,
            "two_day_ret": (1.0 + ret) * (1.0 + next_ret) - 1.0,
        })
    return found


def affects_holding(*, role: str, code: str, earning_code: str, held_index: float,
                    held_tradable: float, weight_eps: float = 1e-4) -> str:
    """研究序列看两个池的持仓。载体只在当天真正计收益、并且持有时算影响持仓。"""
    index_held = held_index > weight_eps
    tradable_held = held_tradable > weight_eps
    if role == "research":
        return "yes" if index_held or tradable_held else "no"
    if role == "carrier" and earning_code == code and tradable_held:
        return "yes"
    return "no"


def write_spikes(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _cell(row.get(key, "")) for key in COLUMNS})


def _cell(value) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, float):
        return f"{value:.10f}"
    return str(value)


def _points(pairs: list[tuple[str, float]]) -> list[tuple[str, float]]:
    return [(str(day), float(close)) for day, close in pairs]


def _otc(con, code: str, end: str) -> tuple[list[tuple[str, float]], str]:
    rows = con.execute(
        """SELECT date, close, source FROM v4_series
           WHERE code = ? AND kind = 'otc_nav' AND close > 0 AND date <= ?
           ORDER BY date""",
        (code, end),
    ).fetchall()
    sources = sorted({str(row[2]) for row in rows if row[2]})
    return _points([(row[0], row[1]) for row in rows]), ",".join(sources)


def _hfq(con, code: str, end: str) -> tuple[list[tuple[str, float]], str]:
    from src.v4.data.hfq import canonical_hfq
    chosen = canonical_hfq(con, code, end)
    if chosen is None or chosen.closes.empty:
        return [], ""
    points = [
        (stamp.strftime("%Y-%m-%d"), float(value))
        for stamp, value in chosen.closes.items()
    ]
    return points, chosen.tier


def _research_points(con, code: str, end: str) -> tuple[list[tuple[str, float]], str, str]:
    rows = con.execute(
        """SELECT date, close, source FROM bars
           WHERE code = ? AND adj = 'raw' AND close > 0 AND date <= ?
           ORDER BY date""",
        (code, end),
    ).fetchall()
    if rows:
        sources = sorted({str(row[2]) for row in rows if row[2]})
        return _points([(row[0], row[1]) for row in rows]), "raw", ",".join(sources)
    for kind in ("backward", "otc_nav", "backward_rebuild"):
        found = con.execute(
            """SELECT date, close, source FROM v4_series
               WHERE code = ? AND kind = ? AND close > 0 AND date <= ?
               ORDER BY date""",
            (code, kind, end),
        ).fetchall()
        if found:
            sources = sorted({str(row[2]) for row in found if row[2]})
            return _points([(row[0], row[1]) for row in found]), kind, ",".join(sources)
    return [], "", ""


def _blank_row(spike: dict, **fields) -> dict:
    row = {key: "" for key in COLUMNS}
    row.update(spike)
    row.update(fields)
    return row


def scan_prices(con, *, end: str = DESIGN_END) -> list[dict]:
    """设计期内全部载体，以及池内容器的研究序列。"""
    from src.v3.data.universe import containers as load_containers
    from src.v3.engine.universe import research_code
    from src.v3.engine.switches import EngineSwitches
    from src.v4.engine.apply import _grouped
    from src.v4.engine.carriers import choose_path, earning_path, has_investable_index, spliced_research
    from src.v3.engine.spec import load_spec

    containers = [
        row for row in load_containers()
        if row.get("in_pool_index") or row.get("in_pool_tradable")
    ]
    spec = load_spec()
    switches = EngineSwitches(
        fill_limits=True, fx_v4=True, carriers=True, t4_pool=True, allow_substitute=True,
    )
    grouped = _grouped(con, containers, end, switches)
    from src.v4.engine.carriers import sse_calendar
    days = sse_calendar(con, end)
    earning: dict[tuple[str, str], str] = {}
    for name, candidates in grouped.items():
        selected = choose_path(candidates, days)
        for day, choice in zip(days, earning_path(selected)):
            if choice is not None:
                earning[(name, pd_day(day))] = choice.code

    cache: dict[tuple[str, str], tuple[list[tuple[str, float]], str, str]] = {}

    def carrier_series(item) -> tuple[list[tuple[str, float]], str, str]:
        otc = item.vehicle == "otc" or (item.vehicle == "near" and item.board == "none")
        key = (item.code, "otc_nav" if otc else "hfq")
        if key not in cache:
            if otc:
                points, source = _otc(con, item.code, end)
                cache[key] = (points, "otc_nav", source)
            else:
                points, source = _hfq(con, item.code, end)
                cache[key] = (points, "hfq", source)
        return cache[key]

    found: list[dict] = []
    seen_carrier: set[tuple[str, str, str, str]] = set()
    for name, candidates in grouped.items():
        for item in candidates:
            points, kind, source = carrier_series(item)
            for spike in reversal_spikes(points, end=end):
                marker = (item.code, name, kind, spike["date"])
                if marker in seen_carrier:
                    continue
                seen_carrier.add(marker)
                found.append(_blank_row(
                    spike,
                    code=item.code,
                    role="carrier",
                    container=name,
                    series_kind=kind,
                    source=source,
                    earning_code=earning.get((name, spike["date"]), ""),
                ))

    seen_research: set[tuple[str, str, str]] = set()
    research_cache: dict[str, tuple[list[tuple[str, float]], str, str]] = {}
    for container in containers:
        identity = str(container.get("id") or "")
        code = research_code(container)
        if code:
            if code not in research_cache:
                research_cache[code] = _research_points(con, code, end)
            points, kind, source = research_cache[code]
            for spike in reversal_spikes(points, end=end):
                marker = (code, identity, spike["date"])
                if marker in seen_research:
                    continue
                seen_research.add(marker)
                found.append(_blank_row(
                    spike,
                    code=code,
                    role="research",
                    container=identity,
                    series_kind=kind,
                    source=source,
                ))
        elif identity and not has_investable_index(container):
            series = spliced_research(
                con, grouped.get(identity) or [], days, end, nav_lag=int(spec.nav_lag))
            points = _level_points(series)
            for spike in reversal_spikes(points, end=end):
                found.append(_blank_row(
                    spike,
                    code=identity,
                    role="research",
                    container=identity,
                    series_kind="spliced",
                    source="carrier-splice",
                    earning_code=earning.get((identity, spike["date"]), ""),
                ))
    found.sort(key=lambda row: (row["date"], row["role"], row["container"], row["code"]))
    return found


def pd_day(day) -> str:
    import pandas as pd
    return pd.Timestamp(day).strftime("%Y-%m-%d")


def _level_points(series) -> list[tuple[str, float]]:
    import math
    level = 100.0
    points = []
    for day, value in series.items():
        if value is None or value != value:
            continue
        number = float(value)
        if not math.isfinite(number) or number <= -1.0:
            continue
        level *= 1.0 + number
        points.append((pd_day(day), level))
    return points


def _weight(held, container: str, day: str) -> float:
    if held is None or container not in getattr(held, "columns", []):
        return 0.0
    import pandas as pd
    stamp = pd.Timestamp(day)
    if stamp not in held.index:
        return 0.0
    value = float(held.at[stamp, container])
    if value != value:
        return 0.0
    return value


def attach_holdings(rows: list[dict], held_index, held_tradable) -> None:
    for row in rows:
        index_weight = _weight(held_index, row["container"], row["date"])
        tradable_weight = _weight(held_tradable, row["container"], row["date"])
        row["held_b0_index"] = index_weight
        row["held_b0_tradable"] = tradable_weight
        row["affects_holding"] = affects_holding(
            role=row["role"],
            code=row["code"],
            earning_code=str(row.get("earning_code") or ""),
            held_index=index_weight,
            held_tradable=tradable_weight,
        )
        in_book = (
            (held_index is not None and row["container"] in held_index.columns)
            or (held_tradable is not None and row["container"] in held_tradable.columns)
        )
        if row["affects_holding"] == "yes":
            row["note"] = "B0 当日持有，这一笔收益进组合"
        elif not in_book:
            row["note"] = "不在 B0 持仓列。B0 不含 T4 的美股行业和港股分类"
        elif row["role"] == "carrier" and tradable_weight > 1e-4 and row.get("earning_code") not in {"", row["code"]}:
            row["note"] = "容器有持仓，当日计收益的是另一只载体"


def main(argv: list[str] | None = None) -> int:
    import argparse
    import json
    import os

    from src.data import db as DB
    from src.v4.r5.design import series_sha256

    parser = argparse.ArgumentParser(description="设计期反向尖刺清单")
    parser.add_argument("--holdings", action="store_true")
    parser.add_argument(
        "--out",
        default="results/v4/inventory/r5c/d25-9-reversal-spikes.csv",
    )
    args = parser.parse_args(argv)
    if os.environ.get("ETF_LEDGER_TESTING"):
        print("测试环境拒绝读默认库")
        return 2
    con = DB.connect(DB.MARKET_DB, readonly=True)
    try:
        rows = scan_prices(con)
    finally:
        con.close()
    print(f"spikes={len(rows)}", flush=True)
    if args.holdings:
        index_book = b0_book("index")
        digest = series_sha256(index_book.net)
        summary_path = DB.ROOT / "results" / "v4" / "r5" / "design" / "B0" / "index" / "summary.json"
        expected = json.loads(summary_path.read_text(encoding="utf-8"))["net_sha256"]
        print(f"B0 index net_sha256={digest}", flush=True)
        if digest != expected:
            print(f"STOP U-指数日收益变了，期望 {expected}", flush=True)
            write_spikes(DB.ROOT / args.out, rows)
            return 2
        tradable_book = b0_book("tradable")
        attach_holdings(rows, index_book.held, tradable_book.held)
        hit = [row for row in rows if row.get("affects_holding") == "yes"]
        print(f"affects_holding={len(hit)}", flush=True)
    write_spikes(DB.ROOT / args.out, rows)
    print(f"wrote {args.out}", flush=True)
    return 0


def b0_book(pool: str):
    from src.v3.engine.arms import execute
    from src.v3.engine.spec import load_spec
    from src.v4.r5.design import Job, Markets

    spec = load_spec()
    job = Job(case="B0", pool=pool, kind="single")
    market = Markets(spec).get(pool, t4=False, allow_substitute=True)
    return execute(
        market, spec, "A", allow_after=False,
        exit_drawdown=job.exit_drawdown, switches=job.switches(),
    )


if __name__ == "__main__":
    raise SystemExit(main())

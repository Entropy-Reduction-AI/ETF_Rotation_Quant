"""正式 oneshot 的四份补导出。只报告，不重跑考试。

不调用 oneshot_exam.execute / official / main，不写 results/v6/oneshot/ 里已有的判定文件。
汇率层和月度仓位从同一次官方引擎重放切出，重放的 v6 必须与 returns-daily.csv 逐日一致。
任意起点和 BM-主逐年只切 returns-daily.csv。
"""

from __future__ import annotations

import hashlib
import inspect
import json
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.report.metrics import cagr, yearly_returns
from src.v4.engine.pool import load_mid
from src.v6.engine import mix_monthly, slot
from src.v6.guard import IsolationError, assert_not_after, open_official_isolation
from src.v6.health import COST
from src.v6.oneshot_prep import (
    DESIGN_END_TEXT,
    DESIGN_START,
    EXAM_END,
    EXAM_START,
    FULL_START,
    HOLD_DAYS,
    SPANS,
    _cagr_pp,
    _same_days,
    _year_spans,
    any_start,
    fx_layer,
)
from src.v6 import engine as engine_module

MARK = "补导出，非重跑"
OFFICIAL = ROOT / "results" / "v6" / "oneshot"
OUT = OFFICIAL / "supplement"
PROTECTED = {
    "verdict.json",
    "criteria.csv",
    "manifest.json",
    "continuity.json",
    "cost-real.json",
}
BUY_FROM = "2011-01-01"
BUY_TO = "2021-12-31"
CUT = pd.Timestamp("2016-01-01")
SLEEVE_A = 0.4
SLEEVE_U = 0.6
WINDOWS = (
    ("设计期", DESIGN_START, DESIGN_END_TEXT),
    *[item for item in SPANS if item[0] != "全段"],
    ("检验段", EXAM_START, EXAM_END),
    ("全段", FULL_START, EXAM_END),
)


def assert_safe_output(path: Path) -> None:
    """只允许写到 supplement/，并且不能用判定文件的名字。"""
    resolved = path.resolve()
    root = OUT.resolve()
    if resolved != root and root not in resolved.parents:
        raise IsolationError(f"补导出只能写在 {root}：{resolved}")
    if resolved.name in PROTECTED or resolved.name == "verdict.json":
        raise IsolationError(f"不改判定文件：{resolved.name}")


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def traced_slot():
    """engine.slot 的同文副本，多记月末目标权重。人民币重放必须与 engine.slot 逐日一致。"""
    source = inspect.getsource(engine_module.slot)
    old_return = "    return series, turnover, log\n"
    new_return = "    return series, turnover, log, trace, columns\n"
    old_pending = (
        "        pending_target = (target, left if held_bond else 0.0, 0.0 if held_bond else left)\n"
        "        pending_delay = signal_lag\n"
    )
    new_pending = (
        "        pending_target = (target, left if held_bond else 0.0, 0.0 if held_bond else left)\n"
        "        trace.append((pd.Timestamp(day), target.copy(), float(pending_target[1]), float(pending_target[2])))\n"
        "        pending_delay = signal_lag\n"
    )
    if source.count(old_return) != 1 or source.count(old_pending) != 1 or source.count("    log = {}\n") != 1:
        raise IsolationError("engine.slot 的文本对不上，不另写一套规则")
    source = source.replace("    log = {}\n", "    log = {}\n    trace = []\n", 1)
    source = source.replace(old_pending, new_pending, 1)
    source = source.replace(old_return, new_return, 1)
    namespace = dict(engine_module.__dict__)
    exec(source, namespace)  # noqa: S102  与 engine.slot 同文，只多记目标权重
    return namespace["slot"]


def replay(levels: pd.DataFrame, bond: pd.Series, cash: pd.Series, trace: list, cost: float) -> pd.Series:
    """用已经记下的月末目标权重重放日收益。决策不再算一遍。"""
    calendar = levels.index
    returns = levels.pct_change().fillna(0).to_numpy(dtype=float)
    width = levels.shape[1]
    weight = np.zeros(width)
    bond_w = 0.0
    cash_w = 1.0
    out = np.zeros(len(calendar))
    pending = None
    delay = 0
    cursor = 0
    bond_ret = bond.reindex(calendar).fillna(0).to_numpy(dtype=float)
    cash_ret = cash.reindex(calendar).to_numpy(dtype=float)
    if np.isnan(cash_ret).any():
        raise IsolationError("现金收益没有盖住日历")
    mask = np.r_[calendar.month[1:] != calendar.month[:-1], True]
    for t, day in enumerate(calendar):
        if pending is not None and delay > 0:
            delay -= 1
            fee = 0.0
        elif pending is not None:
            target, target_bond, target_cash = pending
            traded = float(np.abs(target - weight).sum() + abs(target_bond - bond_w))
            fee = cost * traded
            weight, bond_w, cash_w = target, target_bond, target_cash
            pending = None
        else:
            fee = 0.0
        gross = float((weight * returns[t]).sum() + bond_w * bond_ret[t] + cash_w * cash_ret[t])
        out[t] = (1.0 + gross) * (1.0 - fee) - 1.0
        growth = 1.0 + gross
        weight = weight * (1.0 + returns[t]) / growth
        bond_w = bond_w * (1.0 + bond_ret[t]) / growth
        cash_w = cash_w * (1.0 + cash_ret[t]) / growth
        if not mask[t]:
            continue
        if cursor >= len(trace):
            raise IsolationError("目标权重少了一天")
        traced_day, traced_target, traced_bond, traced_cash = trace[cursor]
        cursor += 1
        if pd.Timestamp(traced_day) != pd.Timestamp(day):
            raise IsolationError("目标权重的日期对不上")
        if traced_target.shape != (width,):
            raise IsolationError("目标权重的列数对不上")
        pending = (traced_target, traced_bond, traced_cash)
        delay = 0
    if cursor != len(trace):
        raise IsolationError("目标权重多了一天")
    return pd.Series(out, index=calendar)


def _usd_frame(levels: pd.DataFrame, end: str) -> pd.DataFrame:
    """同一份 USDCNY。人民币价格应当等于原始美元价格乘补齐中间价。"""
    con = sqlite3.connect(ROOT / "data" / "market.sqlite")
    try:
        fx = load_mid(con, "USDCNY", end, filled=True)
        rebuilt = {}
        usd_cols = {}
        for code in levels.columns:
            frame = pd.read_sql_query(
                "select date, close from bars where code=? and adj='raw' and close>0 "
                "and date<=? order by date",
                con,
                params=(str(code), end),
            )
            raw = pd.Series(frame["close"].to_numpy(dtype=float), index=pd.to_datetime(frame["date"]))
            raw = raw[~raw.index.duplicated(keep="last")].sort_index()
            assert_not_after(raw.index, code)
            fx_on = fx.reindex(raw.index.union(fx.index)).ffill().reindex(raw.index)
            rmb = (raw * fx_on).reindex(levels.index.union(raw.index)).ffill().reindex(levels.index)
            usd = raw.reindex(levels.index.union(raw.index)).ffill().reindex(levels.index)
            rebuilt[code] = rmb
            usd_cols[code] = usd
    finally:
        con.close()
    assert_not_after(fx.index, "USDCNY")
    rebuilt_frame = pd.DataFrame(rebuilt, index=levels.index)
    usd = pd.DataFrame(usd_cols, index=levels.index)[list(levels.columns)]
    gap = (rebuilt_frame - levels).abs().to_numpy(dtype=float)
    finite = np.isfinite(gap)
    if finite.any() and float(gap[finite].max()) != 0.0:
        raise IsolationError("美股人民币价格不是同一份 USDCNY 乘出来的")
    if not rebuilt_frame.isna().equals(levels.isna()):
        raise IsolationError("美股人民币价格的空缺对不上")
    if not usd.isna().equals(levels.isna()):
        raise IsolationError("去掉汇率之后空缺变了")
    return usd


def fx_table(rmb: pd.Series, usd: pd.Series) -> pd.DataFrame:
    """D49-3。fx_layer 是人民币年化减美元年化，百分点，不进六块。"""
    rows = []
    for label, start, end in WINDOWS:
        index = _same_days({"rmb": rmb, "usd": usd}, start, end)
        left = _cagr_pp(rmb, index)
        right = _cagr_pp(usd, index)
        layer = fx_layer(rmb, usd, start, end)
        if abs(layer - (left - right)) > 1e-9:
            raise IsolationError("汇率层没有等于两段年化之差")
        rows.append({
            "段": label,
            "起点": start,
            "终点": end,
            "共同交易日": int(len(index)),
            "人民币年化_百分点": left,
            "美元年化_百分点": right,
            "汇率层_百分点": layer,
            "进入六块": False,
            "标记": MARK,
        })
    common = _same_days({"rmb": rmb, "usd": usd}, FULL_START, EXAM_END)
    for label, start, end in _year_spans(common):
        index = _same_days({"rmb": rmb, "usd": usd}, start, end)
        left = _cagr_pp(rmb, index)
        right = _cagr_pp(usd, index)
        layer = fx_layer(rmb, usd, start, end)
        rows.append({
            "段": label,
            "起点": str(index.min().date()),
            "终点": str(index.max().date()),
            "共同交易日": int(len(index)),
            "人民币年化_百分点": left,
            "美元年化_百分点": right,
            "汇率层_百分点": layer,
            "进入六块": False,
            "标记": MARK,
        })
    return pd.DataFrame(rows)


def _holdings(names: list[str], weight_of: dict[str, float], scale: float) -> list[tuple[str, float]]:
    held = []
    for name in names:
        weight = weight_of.get(name, 0.0) * scale
        if weight > 0.0:
            held.append((name, weight))
    return held


def positions_frame(logs: dict[str, dict], traces: dict[str, list], columns: dict[str, list]) -> pd.DataFrame:
    """月末信号日的目标权重。组合是 A 股 40%、美股 60%，下一交易日才生效。"""
    days = [pd.Timestamp(day) for day, *_rest in traces["A股"]]
    other = [pd.Timestamp(day) for day, *_rest in traces["美股"]]
    if days != other:
        raise IsolationError("两个名额的月末对不上")
    rows = []
    width = 6
    by_day = {}
    for sleeve in ("A股", "美股"):
        names = columns[sleeve]
        log = {pd.Timestamp(key): value for key, value in logs[sleeve].items()}
        for day, target, bond_w, cash_w in traces[sleeve]:
            day = pd.Timestamp(day)
            if day < pd.Timestamp(FULL_START) or day > pd.Timestamp(EXAM_END):
                continue
            weight_of = {names[i]: float(target[i]) for i in range(len(names))}
            record = log[day]
            held_names = list(record.get("持有") or [])
            positive = {name for name, value in weight_of.items() if value > 1e-15}
            if set(held_names) != positive:
                raise IsolationError(f"{sleeve} {day.date()} 持有名单和目标权重不一致")
            stock = float(target.sum())
            if abs(stock + bond_w + cash_w - 1.0) > 1e-9:
                raise IsolationError(f"{sleeve} {day.date()} 股票国债现金加总不是 1")
            by_day.setdefault(day, {})[sleeve] = {
                "股票": stock,
                "国债": bond_w,
                "现金": cash_w,
                "持有": _holdings(held_names, weight_of, 1.0),
            }
    for day in sorted(by_day):
        pair = by_day[day]
        if set(pair) != {"A股", "美股"}:
            raise IsolationError(f"{day.date()} 缺一个名额")
        combined = {
            "股票": SLEEVE_A * pair["A股"]["股票"] + SLEEVE_U * pair["美股"]["股票"],
            "国债": SLEEVE_A * pair["A股"]["国债"] + SLEEVE_U * pair["美股"]["国债"],
            "现金": SLEEVE_A * pair["A股"]["现金"] + SLEEVE_U * pair["美股"]["现金"],
            "持有": (
                _holdings([name for name, _w in pair["A股"]["持有"]], {name: w for name, w in pair["A股"]["持有"]}, SLEEVE_A)
                + _holdings([name for name, _w in pair["美股"]["持有"]], {name: w for name, w in pair["美股"]["持有"]}, SLEEVE_U)
            ),
        }
        pair["组合"] = combined
        for sleeve in ("A股", "美股", "组合"):
            item = pair[sleeve]
            if abs(item["股票"] + item["国债"] + item["现金"] - 1.0) > 1e-9:
                raise IsolationError(f"{sleeve} {day.date()} 加总不是 1")
            row = {
                "月份": day.date().isoformat(),
                "名额": sleeve,
                "股票仓位": item["股票"],
                "国债仓位": item["国债"],
                "现金仓位": item["现金"],
            }
            for i in range(width):
                if i < len(item["持有"]):
                    row[f"持有{i + 1}"] = item["持有"][i][0]
                    row[f"权重{i + 1}"] = item["持有"][i][1]
                else:
                    row[f"持有{i + 1}"] = ""
                    row[f"权重{i + 1}"] = ""
            row["标记"] = MARK
            rows.append(row)
    if not rows:
        raise IsolationError("没有月末仓位")
    return pd.DataFrame(rows)


def _crosses(index: pd.DatetimeIndex, day: pd.Timestamp, length: int) -> bool:
    position = int(index.get_loc(day))
    segment = index[position:position + length]
    return pd.Timestamp(segment[0]) < CUT and pd.Timestamp(segment[-1]) >= CUT


def _filtered_starts(frame: pd.DataFrame, years: int, buy_from: str, buy_to: str, cross_only: bool) -> list:
    length = HOLD_DAYS[years]
    firsts = frame.groupby(frame.index.to_period("M")).head(1).index
    starts = [day for day in firsts if int(frame.index.get_loc(day)) + length <= len(frame)]
    start_ts, end_ts = pd.Timestamp(buy_from), pd.Timestamp(buy_to)
    starts = [day for day in starts if start_ts <= pd.Timestamp(day) <= end_ts]
    if cross_only:
        starts = [day for day in starts if _crosses(frame.index, day, length)]
    return starts


def _start_stats(frame: pd.DataFrame, strategy: str, years: int, starts: list) -> dict[str, dict]:
    """与 any_start 同一套：连乘后按 252 日年化，跑赢是严格大于。"""
    length = HOLD_DAYS[years]
    compared = {}
    for name in frame.columns:
        if name == strategy:
            continue
        diffs = []
        for day in starts:
            position = int(frame.index.get_loc(day))
            segment = frame.iloc[position:position + length]
            left = float((1.0 + segment[strategy]).prod() ** (252.0 / length) - 1.0)
            right = float((1.0 + segment[name]).prod() ** (252.0 / length) - 1.0)
            diffs.append((left - right) * 100.0)
        values = np.asarray(diffs, dtype=float)
        compared[name] = {
            "跑赢占比": float((values > 0).mean()) if len(values) else None,
            "中位": float(np.median(values)) if len(values) else None,
            "最差": float(values.min()) if len(values) else None,
        }
    return compared


def anystart_table(daily: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """2011–2021 的月初买入。检验段和全段各报一次，跨两段是全段里的子集。"""
    needed = ["v6", "BM-主", "BM-同仓位", "K2A"]
    missing = [name for name in needed if name not in daily.columns]
    if missing:
        raise IsolationError(f"returns-daily.csv 缺 {missing}")
    frame = daily[needed].dropna().sort_index()
    assert_not_after(frame.index, "任意起点")
    if pd.Timestamp(frame.index.max()) > pd.Timestamp(EXAM_END):
        raise IsolationError("任意起点晚于 2026-09-30")
    check = {}
    for years in HOLD_DAYS:
        official = any_start({name: frame[name] for name in needed}, "v6", years)
        check[str(years)] = {
            "起点数": official["起点数"],
            "跑赢占比": official["跑赢占比"]["BM-主"],
        }
    slices = (
        ("检验段", frame.loc[EXAM_START:EXAM_END], False),
        ("全段", frame.loc[FULL_START:EXAM_END], False),
        ("跨两段", frame.loc[FULL_START:EXAM_END], True),
    )
    rows = []
    for window, block, cross_only in slices:
        block = block.dropna().sort_index()
        for years in (1, 3, 5):
            starts = _filtered_starts(block, years, BUY_FROM, BUY_TO, cross_only)
            length = HOLD_DAYS[years]
            crossed = sum(1 for day in starts if _crosses(block.index, day, length))
            stats = _start_stats(block, "v6", years, starts)
            for name, item in stats.items():
                rows.append({
                    "窗口": window,
                    "年数": years,
                    "交易日": length,
                    "对照": name,
                    "起点数": len(starts),
                    "跨段起点数": crossed,
                    "跑赢占比": item["跑赢占比"],
                    "中位": item["中位"],
                    "最差": item["最差"],
                    "买入起": BUY_FROM,
                    "买入止": BUY_TO,
                    "序列起": str(block.index.min().date()) if len(block) else "",
                    "序列止": str(block.index.max().date()) if len(block) else "",
                    "标记": MARK,
                })
    return pd.DataFrame(rows), check


def bm_yearly(daily: pd.DataFrame) -> pd.DataFrame:
    """BM-主逐年收益。yearly_returns：该年日收益连乘减 1。"""
    if "BM-主" not in daily.columns:
        raise IsolationError("returns-daily.csv 没有 BM-主")
    series = daily["BM-主"].dropna().sort_index()
    assert_not_after(series.index, "BM-主")
    if pd.Timestamp(series.index.max()) > pd.Timestamp(EXAM_END):
        raise IsolationError("BM-主晚于 2026-09-30")
    rows = []
    for window, start, end in (("检验段", EXAM_START, EXAM_END), ("全段", FULL_START, EXAM_END)):
        block = series.loc[start:end]
        for year, value in yearly_returns(block).items():
            year_block = block[block.index.year == year]
            label = "2026年前9个月" if year == 2026 and pd.Timestamp(year_block.index.max()) < pd.Timestamp("2026-12-31") else str(year)
            rows.append({
                "窗口": window,
                "年": label,
                "起点": str(year_block.index.min().date()),
                "终点": str(year_block.index.max().date()),
                "交易日": int(len(year_block)),
                "收益": value,
                "收益_百分点": value * 100.0,
                "标记": MARK,
            })
    return pd.DataFrame(rows)


def _stress_check(log: dict) -> float:
    """官方 stress.json 里 A 股 2018-04→2019-01 的平均股票仓位，用来核对重放仍是那次运行。"""
    payload = json.loads((OFFICIAL / "stress.json").read_text(encoding="utf-8"))
    episode = next(row for row in payload["紧张段"] if row["名额"] == "A股" and row["起"] == "2018-04" and row["止"] == "2019-01")
    weights = []
    for day, record in log.items():
        period = pd.Timestamp(day).to_period("M")
        if pd.Period("2018-04", freq="M") <= period <= pd.Period("2019-01", freq="M") and record.get("紧张"):
            weights.append(float(record.get("股票仓位", 1.0)))
    if len(weights) != episode["月数"]:
        raise IsolationError("2018-04→2019-01 的紧张月数对不上官方 stress.json")
    got = float(sum(weights) / len(weights))
    if abs(got - float(episode["股票平均仓位"])) > 1e-9:
        raise IsolationError("2018-04→2019-01 的股票仓位对不上官方 stress.json")
    return got


def _readme(identity: dict) -> str:
    diff = identity["v6最大绝对差"]
    stress = identity["A股2018-04至2019-01股票平均仓位"]
    return f"""# 补导出，非重跑

这四份文件从正式 oneshot 同一次运行的序列切出，只报告。不改 `verdict.json`，不重跑 `oneshot_exam.execute`。官方结论仍是不通过。

行情库 SHA256 与 `manifest.json` 相同：`{identity["行情库sha256"]}`。重放的 v6 日收益对 `returns-daily.csv` 的最大绝对差是 {diff}。A 股 2018-04→2019-01 的平均股票仓位是 {stress}，与 `stress.json` 同一格。

| 文件 | 怎么来的 |
| --- | --- |
| `fx-layer.csv` | D49-3 的 `fx_layer`：美股名额人民币日收益的年化，减同一套官方目标权重在去掉 USDCNY 之后的权益价格上的年化。国债和现金仍是人民币。单位是百分点，`进入六块` 为否。 |
| `positions-monthly.csv` | 官方 v6 两个名额在月末信号日的目标股票、国债、现金权重，以及持有名单。组合行是 A 股 40%、美股 60%。权重在下一交易日生效。 |
| `anystart-2011-2021.csv` | `any_start`：每月第一个交易日买入，持有 252、756、1260 个交易日。序列是 `returns-daily.csv` 的 v6、BM-主、BM-同仓位、K2A。买入日限制在 2011-01-01→2021-12-31。检验段序列是 2016-01-01→2026-09-30，全段序列是 2006-01-01→2026-09-30。跨两段是全段里买入早于 2016-01-01、持有期跨过这一天的子集。 |
| `bm-main-yearly.csv` | `yearly_returns` 作用在 `returns-daily.csv` 的 BM-主列。两个官方窗口各列一年。2026 年只到 09-30，行名是 2026年前9个月。 |

检验段的任意起点从 2016-01-01 的序列取每月第一个交易日，所以这一窗的买入日落在 2016–2021。全段窗口才含 2011–2015 的买入。检验段里持有 1 年和 3 年的起点数相同，是因为买入日截到 2021-12，这两段持有都能在 2026-09-30 之前走完。
"""


def _write(path: Path, text: str | None = None, frame: pd.DataFrame | None = None) -> None:
    assert_safe_output(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if frame is not None:
        frame.to_csv(path, index=False, float_format="%.12g")
        return
    path.write_text(text or "", encoding="utf-8")


def official_books():
    """装载官方窗口，跑两条 v6 名额。不写 results/，不算随机路径。"""
    from src.v6.load import load_panels
    from src.v6.prior import us_prior
    from src.v6.run_design import PANEL, TAGS, _a_daily, _us_daily
    from src.v6.trin import clip_expanding, month_end_mean

    open_official_isolation(EXAM_END, authorized=True)
    panels = load_panels()
    prior = us_prior(PANEL)
    panels["trin"]["csi300"] = month_end_mean(clip_expanding(_a_daily(panels)))
    panels["trin"]["SPX"] = month_end_mean(clip_expanding(_us_daily(panels)))
    run = traced_slot()
    bond, cash, votes = panels["bond"], panels["cash"], panels["votes"]
    a_series, _a_turn, a_log, a_trace, a_cols = run(
        panels["A"], "csi300", 3, None, TAGS["a"], "v6", COST, votes, bond, cash,
        signal_lag=0, stress_votes=2, exclude=None,
    )
    u_series, _u_turn, u_log, u_trace, u_cols = run(
        panels["US"], "SPX", 3, prior, TAGS["us"], "v6", COST, votes, bond, cash,
        signal_lag=0, stress_votes=2, exclude=None,
    )
    a_ref, _t, _log = slot(
        panels["A"], "csi300", 3, None, TAGS["a"], "v6", COST, votes, bond, cash,
        signal_lag=0, stress_votes=2, exclude=None,
    )
    u_ref, _t, _log = slot(
        panels["US"], "SPX", 3, prior, TAGS["us"], "v6", COST, votes, bond, cash,
        signal_lag=0, stress_votes=2, exclude=None,
    )
    if float((a_series - a_ref).abs().max()) != 0.0 or float((u_series - u_ref).abs().max()) != 0.0:
        raise IsolationError("记下的目标权重改了 engine.slot 的日收益")
    a_replay = replay(panels["A"], bond, cash, a_trace, COST)
    u_replay = replay(panels["US"], bond, cash, u_trace, COST)
    if float((a_replay - a_series).abs().max()) > 1e-12 or float((u_replay - u_series).abs().max()) > 1e-12:
        raise IsolationError("人民币重放没有复现 engine.slot")
    net = mix_monthly(a_series, u_series, COST, SLEEVE_A)
    usd_levels = _usd_frame(panels["US"], EXAM_END)
    usd_series = replay(usd_levels, bond, cash, u_trace, COST)
    for series, name in ((net, "v6"), (u_series, "美股人民币"), (usd_series, "美股美元")):
        assert_not_after(series.index, name)
        if pd.Timestamp(series.index.max()) > pd.Timestamp(EXAM_END):
            raise IsolationError(f"{name} 晚于 {EXAM_END}")
    return {
        "净": net,
        "美人民币": u_series,
        "美美元": usd_series,
        "日志": {"A股": a_log, "美股": u_log},
        "轨迹": {"A股": a_trace, "美股": u_trace},
        "列": {"A股": a_cols, "美股": u_cols},
    }


def main() -> None:
    open_official_isolation(EXAM_END, authorized=True)
    before = {name: file_sha256(OFFICIAL / name) for name in PROTECTED}
    daily = pd.read_csv(OFFICIAL / "returns-daily.csv", index_col=0, parse_dates=True)
    assert_not_after(daily.index, "returns-daily")
    books = official_books()
    official_v6 = daily["v6"].dropna()
    got = books["净"].reindex(official_v6.index)
    gap = (got - official_v6).abs()
    if gap.isna().any() or float(gap.max()) > 1e-10:
        raise IsolationError(f"重放的 v6 对不上 returns-daily.csv，最大绝对差 {float(gap.max())}")
    stress = _stress_check(books["日志"]["A股"])
    fx = fx_table(books["美人民币"], books["美美元"])
    positions = positions_frame(books["日志"], books["轨迹"], books["列"])
    starts, check = anystart_table(daily)
    yearly = bm_yearly(daily)
    identity = {
        "v6最大绝对差": float(gap.max()),
        "A股2018-04至2019-01股票平均仓位": stress,
        "行情库sha256": file_sha256(ROOT / "data" / "market.sqlite"),
        "returns-daily全段任意起点对BM主": check,
    }
    _write(OUT / "fx-layer.csv", frame=fx)
    _write(OUT / "positions-monthly.csv", frame=positions)
    _write(OUT / "anystart-2011-2021.csv", frame=starts)
    _write(OUT / "bm-main-yearly.csv", frame=yearly)
    _write(OUT / "README.md", text=_readme(identity))
    after = {name: file_sha256(OFFICIAL / name) for name in PROTECTED}
    if after != before:
        raise IsolationError(f"判定文件被改动：{[name for name in before if before[name] != after[name]]}")
    print(json.dumps({
        "标记": MARK,
        "v6最大绝对差": identity["v6最大绝对差"],
        "汇率层行数": int(len(fx)),
        "仓位行数": int(len(positions)),
        "任意起点行数": int(len(starts)),
        "BM主逐年行数": int(len(yearly)),
        "判定文件未改": True,
        "verdict_sha256": before["verdict.json"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()

"""设计期体检的输入，不是页面，也不是四张图。

只算 2006–2010、2011–2015、2006–2015。闸门只报数。
主序列用修正后的扩展分位 TRIN。设计期票差为 0 时，新旧净值相同，两套都记下。
"""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from src.report.blend import monthly_rebalance
from src.report.metrics import cagr, max_drawdown, yearly_returns
from src.v4.r5.design import reference_frame, series_sha256
from src.v6.engine import mix_monthly, slot
from src.v6.guard import IsolationError, assert_not_after
from src.v6.k2a import k2a_returns
from src.v6.load import load_panels
from src.v6.prior import us_prior
from src.v6.run_design import FRENCH_SHA, PANEL, TAGS, _a_daily, _sha_file, _us_daily
from src.v6.trin import clip_expanding, month_end_mean

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results" / "v6"
DESIGN_END = pd.Timestamp("2015-12-31")
COST = 0.002
SEGMENTS = (
    ("2006-2010", "2006-01-01", "2010-12-31"),
    ("2011-2015", "2011-01-01", "2015-12-31"),
    ("2006-2015", "2006-01-01", "2015-12-31"),
)
A1_SHA = "3c371162360d276d6418b5d57a17b037abd5a99ac17e5b1933fd66854478634e"
A2_SHA = "cf3091d5dfdae739a0f175c1d96c7910bd5ee1bbdb22c1f9fce7eecaa1b7685a"
D46_MERGE = "7f2f1a16c529ab3c10eed87c617b4442cf3946c7"


def _clip(series: pd.Series, start: str, end: str) -> pd.Series:
    end_ts = pd.Timestamp(end)
    if end_ts > DESIGN_END:
        raise IsolationError(f"体检窗口晚于设计期：{end}")
    assert_not_after(series.index, "体检")
    window = series.loc[start:end].astype(float).dropna()
    if window.empty:
        raise IsolationError(f"{start} 至 {end} 没有收益")
    assert_not_after(window.index, "体检窗口")
    return window


def _pair(series: pd.Series, start: str, end: str) -> dict:
    window = _clip(series, start, end)
    growth = cagr(window)
    depth = max_drawdown(window)["max_drawdown"]
    return {
        "cagr": growth,
        "cagr_pct": growth * 100.0,
        "max_drawdown": depth,
        "n": int(len(window)),
        "first": window.index.min().date().isoformat(),
        "last": window.index.max().date().isoformat(),
    }


def _complete_years(calendar: pd.DatetimeIndex, start: str, end: str) -> list[int]:
    years = []
    start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)
    for year, block in pd.Series(1, index=calendar).groupby(calendar.year):
        if block.index.min() >= start_ts and block.index.max() <= end_ts:
            years.append(int(year))
    return years


def _covers(series: pd.Series, year: int, calendar: pd.DatetimeIndex) -> bool:
    block = calendar[calendar.year == year]
    have = series.index[series.index.year == year]
    if len(block) == 0 or len(have) == 0:
        return False
    return have.min() <= block.min() and have.max() >= block.max()


def _premium(v6: pd.Series, plain: pd.Series, bm: pd.Series, start: str, end: str) -> dict:
    """不设防守年收益 − v6 年收益，只在 BM-主该自然年收益为正时平均。单位是百分点。"""
    covered = _complete_years(v6.index, start, end)
    y_v = yearly_returns(_clip(v6, start, end))
    y_p = yearly_returns(_clip(plain, start, end))
    y_b = yearly_returns(_clip(bm, start, end))
    used, dropped = [], []
    gaps = []
    for year in covered:
        if not (_covers(v6, year, v6.index) and _covers(plain, year, v6.index) and _covers(bm, year, v6.index)):
            dropped.append(year)
            continue
        if year not in y_v or year not in y_p or year not in y_b:
            dropped.append(year)
            continue
        if y_b[year] <= 0:
            dropped.append(year)
            continue
        used.append(year)
        gaps.append((y_p[year] - y_v[year]) * 100.0)
    mean = None if not gaps else float(sum(gaps) / len(gaps))
    return {
        "premium_pp": mean,
        "years": used,
        "dropped_years": dropped,
        "n_years": len(used),
    }


def _ratio(stats: dict) -> float | None:
    depth = stats["max_drawdown"]
    if depth == 0.0 or depth != depth:
        return None
    return stats["cagr"] / abs(depth)


def _hash_series(series: pd.Series) -> str:
    lines = [f"{pd.Timestamp(day).date().isoformat()},{float(value):.12g}" for day, value in series.items()]
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


def _read_peer(case: str, expected: str) -> tuple[pd.Series | None, dict]:
    folder = ROOT / "results" / "v4" / "r5" / "design" / case / "index"
    path = folder / "net.csv"
    summary = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
    frame = pd.read_csv(path, parse_dates=["date"]).set_index("date")["net"].astype(float)
    digest = series_sha256(frame)
    note = {
        "path": str(path.relative_to(ROOT)),
        "summary_sha256": summary.get("net_sha256"),
        "recomputed_sha256": digest,
        "start": str(summary.get("start")),
        "end": str(summary.get("end")),
        "matches_prereg": digest == expected and str(summary.get("net_sha256")) == expected,
    }
    if not note["matches_prereg"] or pd.Timestamp(frame.index.max()) > DESIGN_END:
        note["status"] = "未完成"
        note["reason"] = "账本哈希或结束日与冻结 §5.2 不一致，不用这组数"
        return None, note
    note["status"] = "ok"
    frame.name = case
    return frame, note


def _votes(panels, parent, levels):
    total, _n = panels["votes"](levels, parent, ["均线", "宽度", "TRIN"])
    return total


def _same_votes(left: pd.Series, right: pd.Series) -> bool:
    joined = pd.concat([left.rename("a"), right.rename("b")], axis=1).dropna()
    joined = joined.loc["2006-01":"2015-12"]
    return bool(len(joined)) and bool((joined["a"] == joined["b"]).all())


def _sleeve(levels, parent, prior, tags, votes, bond, cash, mode, cost):
    series, _turnover, log = slot(levels, parent, 3, prior, tags, mode, cost, votes, bond, cash)
    assert_not_after(series.index, mode)
    return series, log


def _benchmarks() -> tuple[pd.Series, pd.Series]:
    parts = reference_frame(end="2015-12-31").dropna()
    assert_not_after(parts.index, "BM")
    main, _w = monthly_rebalance(parts, {"H00300": 0.70, "XNDX": 0.15, "SP500TR": 0.15})
    same, _w = monthly_rebalance(parts, {"H00300": 0.40, "XNDX": 0.30, "SP500TR": 0.30})
    return main, same


def _k2a(panels) -> pd.Series:
    prices = panels["ns"]["P"]
    us = (prices["ndx100"] + prices["spx"]) / 2
    return k2a_returns(prices["csi300"], us, panels["bond"], panels["cash"])


def _code_sha() -> str:
    digest = hashlib.sha256()
    for folder in (ROOT / "src/v6", ROOT / "config/v6"):
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                digest.update(path.relative_to(ROOT).as_posix().encode())
                digest.update(path.read_bytes())
    return digest.hexdigest()


def _append_ledger(row: dict) -> None:
    path = OUT / "trial-ledger.csv"
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row))
        writer.writerow(row)


def run() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    panels = load_panels()
    opaque = Path("/opt/cursor/artifacts/french-49/49_Industry_Portfolios.csv")
    csv_sha = _sha_file(opaque) if opaque.exists() else None
    if csv_sha != FRENCH_SHA or not PANEL.exists():
        raise IsolationError("美股起点经验不在已登记的 1926-07 至 1998-12 面板上，体检停")
    prior = us_prior(PANEL)
    bond, cash = panels["bond"], panels["cash"]
    votes = panels["votes"]
    new_a = month_end_mean(clip_expanding(_a_daily(panels)))
    new_u = month_end_mean(clip_expanding(_us_daily(panels)))
    saved = {key: panels["trin"][key].copy() for key in ("csi300", "SPX")}
    old_votes = {
        "A": _votes(panels, "csi300", panels["A"]),
        "US": _votes(panels, "SPX", panels["US"]),
    }
    panels["trin"]["csi300"] = new_a
    panels["trin"]["SPX"] = new_u
    new_votes = {
        "A": _votes(panels, "csi300", panels["A"]),
        "US": _votes(panels, "SPX", panels["US"]),
    }
    identical = _same_votes(old_votes["A"], new_votes["A"]) and _same_votes(old_votes["US"], new_votes["US"])
    caliber = "expanding99；与全样本99在2006-01至2015-12票差0个月，净值相同" if identical else "expanding99"

    a_v6, log_a = _sleeve(panels["A"], "csi300", None, TAGS["a"], votes, bond, cash, "v6", COST)
    a_top, _ = _sleeve(panels["A"], "csi300", None, TAGS["a"], votes, bond, cash, "top", COST)
    a_top_gross, _ = _sleeve(panels["A"], "csi300", None, TAGS["a"], votes, bond, cash, "top", 0.0)
    a_ew, _ = _sleeve(panels["A"], "csi300", None, TAGS["a"], votes, bond, cash, "ew", 0.0)
    a_id, log_id = _sleeve(panels["A"], "csi300", None, TAGS["a"], votes, bond, cash, "id", COST)
    u_v6, _log_u = _sleeve(panels["US"], "SPX", prior, TAGS["us"], votes, bond, cash, "v6", COST)
    u_top, _ = _sleeve(panels["US"], "SPX", prior, TAGS["us"], votes, bond, cash, "top", 0.0)
    u_ew, _ = _sleeve(panels["US"], "SPX", prior, TAGS["us"], votes, bond, cash, "ew", 0.0)
    panels["trin"]["csi300"] = saved["csi300"]
    panels["trin"]["SPX"] = saved["SPX"]

    v6 = mix_monthly(a_v6, u_v6, COST)
    plain = mix_monthly(a_top, u_top, COST)
    continuity = mix_monthly(a_id, u_v6, COST)
    csi = panels["A"]["csi300"].pct_change().fillna(0.0)
    bm_main, bm_same = _benchmarks()
    k2a = _k2a(panels)
    a1, a1_note = _read_peer("A1", A1_SHA)
    a2, a2_note = _read_peer("A2", A2_SHA)

    series = {
        "v6": v6,
        "连续性版": continuity,
        "A1": a1,
        "A2": a2,
        "K2A": k2a,
        "现行配置": None,
        "BM-主": bm_main,
        "BM-同仓位": bm_same,
    }
    gaps = {
        "现行配置": "仓库没有设计期 panel.sqlite。§5.2 要求走 src/portfolio/replicate.py 的 daily_book，阀门关闭。不从可能含 2016 的研究包重建面板，也不另写一套权重。",
    }
    if a1 is None:
        gaps["A1"] = a1_note["reason"]
    if a2 is None:
        gaps["A2"] = a2_note["reason"]

    gate_rows = []
    scatter_rows = []
    forecast_rows = []
    for name, start, end in SEGMENTS:
        v6_stats = _pair(v6, start, end)
        k2a_stats = _pair(k2a, start, end)
        same_stats = _pair(bm_same, start, end)
        main_stats = _pair(bm_main, start, end)
        premium = _premium(v6, plain, bm_main, start, end)
        gate_rows.extend([
            {"segment": name, "item": "v6净最大回撤", "value": v6_stats["max_drawdown"], "unit": "净值回撤", "years": "", "trin": caliber},
            {"segment": name, "item": "防守平时保费", "value": premium["premium_pp"], "unit": "百分点", "years": ",".join(str(y) for y in premium["years"]), "trin": caliber},
            {"segment": name, "item": "v6年化/最大回撤绝对值", "value": _ratio(v6_stats), "unit": "比值", "years": "", "trin": caliber},
            {"segment": name, "item": "K2A年化/最大回撤绝对值", "value": _ratio(k2a_stats), "unit": "比值", "years": "", "trin": caliber},
            {"segment": name, "item": "v6净减BM-同仓位年化", "value": v6_stats["cagr_pct"] - same_stats["cagr_pct"], "unit": "百分点", "years": "", "trin": caliber},
        ])
        for label, book in series.items():
            if book is None:
                scatter_rows.append({
                    "segment": name, "series": label, "cagr_pct": "", "max_drawdown": "",
                    "status": "未完成", "reason": gaps[label], "trin": "",
                })
                continue
            stats = _pair(book, start, end)
            scatter_rows.append({
                "segment": name, "series": label, "cagr_pct": stats["cagr_pct"],
                "max_drawdown": stats["max_drawdown"], "status": "ok", "reason": "",
                "trin": caliber if label in ("v6", "连续性版") else "不使用TRIN",
            })
        a_pick = _pair(a_top_gross, start, end)
        a_eq = _pair(a_ew, start, end)
        a_parent = _pair(csi, start, end)
        u_pick = _pair(u_top, start, end)
        u_eq = _pair(u_ew, start, end)
        forecast_rows.extend([
            {"segment": name, "item": "美股挑选", "value": u_pick["cagr_pct"] - u_eq["cagr_pct"], "unit": "百分点"},
            {"segment": name, "item": "A股挑选", "value": a_pick["cagr_pct"] - a_eq["cagr_pct"], "unit": "百分点"},
            {"segment": name, "item": "A股等权倾斜", "value": a_eq["cagr_pct"] - a_parent["cagr_pct"], "unit": "百分点"},
            {"segment": name, "item": "防守保费", "value": None if premium["premium_pp"] is None else -premium["premium_pp"], "unit": "百分点"},
            {"segment": name, "item": "美股60%仓位差", "value": same_stats["cagr_pct"] - main_stats["cagr_pct"], "unit": "百分点"},
        ])

    kept = {name: book for name, book in series.items() if book is not None}
    kept["不设防守"] = plain
    frame = pd.concat([book.rename(name) for name, book in kept.items()], axis=1).sort_index()
    frame = frame.loc[:DESIGN_END]
    assert_not_after(frame.index, "体检收益")
    frame.to_csv(OUT / "health-returns.csv", float_format="%.12g")
    pd.DataFrame(gate_rows).to_csv(OUT / "health-gates.csv", index=False)
    pd.DataFrame(scatter_rows).to_csv(OUT / "health-scatter.csv", index=False)
    pd.DataFrame(forecast_rows).to_csv(OUT / "health-forecast.csv", index=False)

    id_months = [day for day, rec in log_id.items() if rec.get("p") is not None]
    meta = {
        "freeze": "f066da8e46f202e105a65c7abf43e4d4cf82eff9",
        "d45": "2fbcecfaeda83d4529b54789208986787acc77af",
        "d46_merge": D46_MERGE,
        "primary_trin": "expanding99",
        "old_trin_retained": identical,
        "vote_diff_2006_2015": "0个月" if identical else "有差异，闸门只用扩展分位",
        "owner_rule": "一次性检验用改后口径；设计期改前改后都报。票差为 0 时两套净值相同，不另存一份重复序列。",
        "functions": {
            "cagr": "src/report/metrics.py cagr",
            "max_drawdown": "src/report/metrics.py max_drawdown",
            "yearly_returns": "src/report/metrics.py yearly_returns",
            "v6": "src/v6/engine.py slot mode=v6；mix_monthly 单边 0.002",
            "continuity": "src/v6/engine.py slot mode=id；美股仍是 mode=v6 且用 French 起点",
            "k2a": "src/v6/k2a.py k2a_returns；sim.py run kind=K2A s_us=0.50 cost=0.001",
            "bm": "src/v4/r5/design.py reference_frame + src/report/blend.py monthly_rebalance",
            "a1_a2": "results/v4/r5/design/A1/index 与 A2/index，不重跑",
        },
        "formulas": {
            "年化": "metrics.cagr：(1+r).prod() ** (252/n) − 1。窗口内收益，不含 2016。",
            "最大回撤": "metrics.max_drawdown：窗口内净值从窗口内高点算，峰值不取窗口之前。",
            "年度收益": "该自然年日收益连乘 − 1，等于这一年首尾净值之比。首尾不满一年的年份不进保费。",
            "保费": "闸门按 §5：BM-主全年收益 > 0 的完整自然年，算术平均(不设防守年收益 − v6 年收益)，再乘 100。预测表这一项用相反符号（v6 − 不设防守），因为表里中间值是 −0.4。两边用同一组年份。不设防守与 v6 都是每月 60/40 再平衡、单边 0.2%。",
            "判据③": "年化 ÷ 最大回撤的绝对值。v6 与 K2A 分开报，不写高低。",
            "判据④": "v6 年化百分点 − BM-同仓位年化百分点。",
            "美股挑选": "美股名额 mode=top 成本 0 的年化 − mode=ew 成本 0 的年化，百分点。",
            "A股挑选": "A 股名额 mode=top 成本 0 − mode=ew 成本 0。ew 是 §5.2 按行业标签等权。",
            "A股等权倾斜": "A 股 mode=ew 成本 0 − 沪深300 自身。",
            "仓位差": "BM-同仓位年化 − BM-主年化，百分点。§5.1，不是预测表中点。",
        },
        "readings": {
            "连续性正收益过滤": "正收益过滤写在第①步。§1.3 用连续性版替换第①步，其余三步不动，所以不套这道过滤。空位仍按第③步留到国债或现金。",
            "连续性领头者": "紧张月记入把握 p 的是连续性版自己选出的名字，hist 与主规则分开。",
            "基准": "§5.1 的全收益、每月第一个交易日再平衡。附表 B 的价格指数基准只用于那张表的对账，不进体检。",
            "D40-12": "挑选是 12−1 相对同名额等权，等权倾斜是同名额等权相对沪深300。同名额等权按 §5.2 是行业标签等权，不是把附录 B 的组合分解再拆一次。",
        },
        "peers": {"A1": a1_note, "A2": a2_note},
        "gaps": gaps,
        "series_sha256": {name: _hash_series(book) for name, book in kept.items()},
        "continuity_p_months": len(id_months),
        "continuity_last_p": None if not id_months else log_id[id_months[-1]]["p"],
        "continuity_held_diff_months": sum(
            sorted(log_id[day].get("持有") or []) != sorted(log_a.get(day, {}).get("持有") or [])
            for day in log_id
        ),
        "continuity_p_equals_main_a_p": all(
            log_id[day].get("p") == log_a.get(day, {}).get("p") for day in log_id
        ),
        "inputs": {
            "market_sqlite": "data/market.sqlite",
            "french_sha256": csv_sha,
            "french_panel": str(PANEL.relative_to(ROOT)),
            "loader_sha256": panels["loader_sha256"],
            "date_cap": "2015-12-31",
        },
        "rerun": ".venv/bin/python -m src.v6.health",
    }
    (OUT / "health-meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    _append_ledger({
        "run_at": datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds"),
        "code_sha256": _code_sha(),
        "freeze": meta["freeze"],
        "d45": meta["d45"],
        "input_sha256": json.dumps(meta["inputs"], ensure_ascii=False),
        "period": "2006-01-01至2015-12-31",
        "params": "segments=2006-2010,2011-2015,2006-2015; cost=0.002; trin=expanding99; continuity=id",
        "purpose": "设计期体检输入：闸门、8序列、预测表实际值。不跑一次性检验。",
        "result": json.dumps({"gates": len(gate_rows), "scatter": len(scatter_rows), "forecast": len(forecast_rows), "gaps": sorted(gaps)}, ensure_ascii=False),
    })
    return {"gates": len(gate_rows), "scatter": len(scatter_rows), "forecast": len(forecast_rows), "gaps": sorted(gaps)}


def main() -> None:
    print(json.dumps(run(), ensure_ascii=False))


if __name__ == "__main__":
    main()

"""预注册 v2 的计算。口径与 operations/reviews/diag/d4.py 一致。

设计期函数在看到结束日晚于 2015-12-31 时直接拒绝，不算收益。
样本外只由 run_oos 在锁文件写入之后调用。
"""
from __future__ import annotations

import sqlite3
import tomllib
from pathlib import Path

import pandas as pd

from src.research.prereg_v1.panel import read_table, validate_panel
from src.signals.fallback import slow_valve

ROOT = Path(__file__).resolve().parents[3]
FROZEN_SHA = "1ad86ac0150138b7284cca7566d421e63bf39032"
DESIGN_END = pd.Timestamp("2015-12-31")
OOS_START = pd.Timestamp("2016-01-04")
OOS_END = pd.Timestamp("2026-09-30")
TRADING_DAYS = 252
# 单边 0.05% × 2。加倍后单边 0.10% × 2。
ROUND_TRIP_COST = 0.001
ROUND_TRIP_COST_DOUBLED = 0.002
CASH_ANNUAL = 0.02
VALVE_OUT = 0.25
VALVE_BACK = 0.10
A_WEIGHT = 0.70
O_WEIGHT = 0.30
HAVEN_CODE = "511880"
DD_MARGIN = 0.10
CAGR_GIVEUP = 0.02
D4_TOLERANCE = 0.001  # 0.1 个百分点

# d4 印刷值。门槛只比年化和最大回撤。
D4_PUBLISHED = {
    "B0": {"cagr": 0.214, "max_drawdown": -0.698},
    "B1": {"cagr": 0.254, "max_drawdown": -0.248, "switches_per_year": 27.5},
    "B2": {"cagr": 0.267, "max_drawdown": -0.497},
}

A_SHARE = (
    "沪深300", "中证500", "中证1000", "创业板", "AI/算力", "有色", "煤炭", "军工",
    "医药", "消费", "白酒", "农业", "银行", "券商", "地产", "红利",
)
OVERSEAS = ("纳指100", "标普500")


class RunnerError(RuntimeError):
    pass


def sha_matches(given: str | None) -> bool:
    """冻结提交 1ad86ac。接受它本身或更长的同一前缀，短于 7 位不算。"""
    if not given:
        return False
    text = given.strip().lower()
    if len(text) < 7 or len(text) > len(FROZEN_SHA):
        return False
    if any(ch not in "0123456789abcdef" for ch in text):
        return False
    return FROZEN_SHA.startswith(text)


def cash_daily(annual: float = CASH_ANNUAL) -> float:
    return annual / TRADING_DAYS


def load_sleeves(path: Path) -> dict:
    """读配置里的腿。名字、权重、阀、避风港必须仍是预注册写死的那一套。"""
    with Path(path).open("rb") as fh:
        raw = tomllib.load(fh)
    sleeves = {
        "a_share": tuple(raw["a_share"]["containers"]),
        "a_weight": float(raw["a_share"]["weight"]),
        "overseas": tuple(raw["overseas"]["containers"]),
        "o_weight": float(raw["overseas"]["weight"]),
        "out": float(raw["valve"]["out"]),
        "back": float(raw["valve"]["back"]),
        "haven_code": str(raw["valve"]["haven_code"]),
        "cash_annual": float(raw["valve"]["cash_annual"]),
    }
    expected = {
        "a_share": A_SHARE,
        "a_weight": A_WEIGHT,
        "overseas": OVERSEAS,
        "o_weight": O_WEIGHT,
        "out": VALVE_OUT,
        "back": VALVE_BACK,
        "haven_code": HAVEN_CODE,
        "cash_annual": CASH_ANNUAL,
    }
    for key, value in expected.items():
        if sleeves[key] != value:
            raise RunnerError(f"配置 {key} 与预注册不一致：{sleeves[key]!r}")
    return sleeves


def clip_panel(panel: pd.DataFrame, end: pd.Timestamp) -> pd.DataFrame:
    """结束日之后的行先丢掉，再算收益。"""
    end = pd.Timestamp(end)
    out = panel.loc[pd.to_datetime(panel["date"]) <= end].copy()
    if not out.empty and pd.to_datetime(out["date"]).max() > end:
        raise RunnerError("过滤后面板仍越过结束日")
    return out


def equal_weight_returns(panel: pd.DataFrame, names: tuple[str, ...] | list[str], end: pd.Timestamp) -> pd.Series:
    """data_hole==0 的容器当日收益等权。缺失不参与平均。与 d4 同一写法。"""
    frame = clip_panel(panel, end)
    if frame.empty:
        raise RunnerError(f"{pd.Timestamp(end).date()} 之前没有面板行")
    have = set(frame["container"])
    missing = [name for name in names if name not in have]
    if missing:
        raise RunnerError(f"面板缺容器：{missing}")
    px = frame.pivot(index="date", columns="container", values="close").sort_index()
    hole = frame.pivot(index="date", columns="container", values="data_hole").reindex_like(px)
    cols = list(names)
    returns = px[cols].where(hole[cols].eq(0)).pct_change(fill_method=None).mean(axis=1).fillna(0.0)
    returns = returns.loc[returns.index <= pd.Timestamp(end)]
    if returns.empty or returns.index.max() > pd.Timestamp(end):
        raise RunnerError("等权收益越过结束日")
    returns.name = "ret"
    return returns.astype(float)


def emas(nav: pd.Series) -> tuple[pd.Series, pd.Series]:
    """EMA10、EMA20。span 为 10 和 20，adjust=False。"""
    return nav.ewm(span=10, adjust=False).mean(), nav.ewm(span=20, adjust=False).mean()


def in_market(ema_fast: pd.Series, ema_slow: pd.Series) -> pd.Series:
    """在场 ⇔ 快线高于慢线，且两条线当天都上升。相等或走平都不算。"""
    up_fast = ema_fast.diff() > 0
    up_slow = ema_slow.diff() > 0
    return (ema_fast > ema_slow) & up_fast & up_slow


def qulla_signal(nav: pd.Series) -> pd.Series:
    fast, slow = emas(nav)
    return in_market(fast, slow).astype(float)


def slow_valve_signal(nav: pd.Series, out: float = VALVE_OUT, back: float = VALVE_BACK) -> pd.Series:
    """d4 的月末慢阀。状态来自 slow_valve，对齐方式沿用 d4 的日历月末 ffill。

    slow_valve 返回的是进入该月时的状态，最后一月决策后的状态不在里面。
    再送一根收益为 0 的观察把它读出来。标签用最后一个月末，不另造结束日之后的日期。
    这根观察不进入任何收益。
    """
    month_end = nav.resample("ME").last().dropna()
    if month_end.empty:
        raise RunnerError("慢阀没有月末净值")
    shadow = month_end.pct_change()
    shadow.iloc[0] = 0.0
    probe = pd.concat([shadow, pd.Series([0.0], index=[month_end.index[-1]])])
    _held, _switches, during = slow_valve(probe, out, back, 0.0)
    decided = pd.Series(during.iloc[1:].to_numpy(), index=month_end.index, dtype=float)
    return decided.reindex(nav.index, method="ffill").fillna(1.0)


def effective_position(signal: pd.Series) -> pd.Series:
    """T 日收盘的信号乘的是下一根收益。第一根没有昨日信号，按在场。"""
    return signal.shift(1).fillna(1.0).astype(float)


def path_returns(asset: pd.Series, signal: pd.Series, haven: pd.Series, cost: float) -> tuple[pd.Series, pd.Series, pd.Series]:
    """返回净收益、生效持仓、切换（0/1）。切换日扣一轮来回成本。"""
    pos = effective_position(signal).reindex(asset.index)
    switches = pos.diff().abs().fillna(0.0)
    haven = haven.reindex(asset.index).astype(float)
    if haven.isna().any():
        raise RunnerError("避风港收益没有盖住全部交易日")
    net = pos * asset + (1.0 - pos) * haven - switches * cost
    return net.astype(float), pos.astype(float), switches.astype(float)


def summarize(net: pd.Series, pos: pd.Series, switches: pd.Series) -> dict:
    if net.empty:
        raise RunnerError("没有可汇总的收益")
    nav = (1.0 + net).cumprod()
    years = len(net) / TRADING_DAYS
    yearly = {}
    for year, block in net.groupby(net.index.year):
        yearly[str(int(year))] = float((1.0 + block).prod() - 1.0)
    return {
        "cagr": float(nav.iloc[-1] ** (1.0 / years) - 1.0),
        "max_drawdown": float((nav / nav.cummax() - 1.0).min()),
        "time_in_market": float(pos.mean()),
        "switches_per_year": float(switches.sum() / years),
        "switches": float(switches.sum()),
        "yearly": yearly,
        "first": str(pd.Timestamp(net.index[0]).date()),
        "last": str(pd.Timestamp(net.index[-1]).date()),
        "n": int(len(net)),
    }


def passes_drawdown(b0_dd: float, b1_dd: float, margin: float = DD_MARGIN) -> bool:
    """B1 的最大回撤比 B0 浅至少 margin。回撤是负数，浅的代数更大。"""
    return (b1_dd - b0_dd) >= margin - 1e-12


def passes_cagr(b0_cagr: float, b1_cagr: float, giveup: float = CAGR_GIVEUP) -> bool:
    """B1 年化不比 B0 低过 giveup。高于 B0 也通过。"""
    return b1_cagr >= b0_cagr - giveup - 1e-12


def criteria(b0: dict, b1: dict, b0_doubled: dict, b1_doubled: dict) -> dict:
    """§4 三条。只比较传入的数字，不读行情。"""
    drawdown = passes_drawdown(b0["max_drawdown"], b1["max_drawdown"])
    cagr = passes_cagr(b0["cagr"], b1["cagr"])
    doubled = passes_drawdown(b0_doubled["max_drawdown"], b1_doubled["max_drawdown"]) and passes_cagr(
        b0_doubled["cagr"], b1_doubled["cagr"])
    return {
        "drawdown_shallower_by_10pp": drawdown,
        "cagr_giveup_at_most_2pp": cagr,
        "still_holds_at_doubled_cost": doubled,
        "pass": bool(drawdown and cagr and doubled),
    }


def b2_both_worse(b0: dict, b2: dict) -> bool:
    """年化和最大回撤都差于满仓。相等不算。"""
    return b2["cagr"] < b0["cagr"] and b2["max_drawdown"] < b0["max_drawdown"]


def monthly_blend(a_ret: pd.Series, o_ret: pd.Series, a_weight: float = A_WEIGHT) -> pd.Series:
    """指数层面月度再平衡：每月第一个交易日的收益按目标权重，月内随收益漂移。不再另扣再平衡成本。"""
    o_weight = 1.0 - a_weight
    other = o_ret.reindex(a_ret.index).astype(float)
    if other.isna().any():
        raise RunnerError("海外腿没有盖住 A 股腿的交易日")
    wa, wo = a_weight, o_weight
    prev = None
    out = []
    for day, ra in a_ret.items():
        period = day.to_period("M")
        if prev is not None and period != prev:
            wa, wo = a_weight, o_weight
        ro = float(other.loc[day])
        ra = float(ra)
        port = wa * ra + wo * ro
        scale = 1.0 + port
        if scale != 0.0:
            wa = wa * (1.0 + ra) / scale
            wo = wo * (1.0 + ro) / scale
        out.append(port)
        prev = period
    return pd.Series(out, index=a_ret.index, dtype=float)


def haven_total_return(closes: pd.Series, dividends: pd.DataFrame, index: pd.DatetimeIndex,
                       cash: float) -> pd.Series:
    """有相邻收盘的日子用价格收益，除息日再加库内 amount/prev_close。没有收益的日子用现金日利率。"""
    closes = closes.sort_index()
    closes = closes.loc[closes.index <= index.max()]
    price = closes.pct_change(fill_method=None)
    if dividends is not None and len(dividends):
        for row in dividends.itertuples(index=False):
            ex = pd.Timestamp(row.ex_date)
            amount = float(row.amount)
            prev = float(row.prev_close)
            if ex not in price.index or not (prev > amount > 0):
                continue
            if pd.isna(price.loc[ex]):
                continue
            price.loc[ex] = float(price.loc[ex]) + amount / prev
    aligned = price.reindex(index)
    return aligned.fillna(cash).astype(float)


def load_haven(db: Path, code: str, end: pd.Timestamp) -> tuple[pd.Series, pd.DataFrame]:
    """只读收盘和现金分红，日期不超过 end。"""
    end = pd.Timestamp(end)
    if not Path(db).exists():
        raise RunnerError(f"找不到行情库 {db}")
    uri = f"{Path(db).resolve().as_uri()}?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    try:
        bars = pd.read_sql_query(
            "SELECT date, close FROM bars WHERE code = ? AND adj = 'raw' AND date <= ? AND close > 0 ORDER BY date",
            con, params=(code, end.strftime("%Y-%m-%d")))
        divs = pd.read_sql_query(
            "SELECT ex_date, amount, prev_close FROM cash_dividends WHERE code = ? AND ex_date <= ? ORDER BY ex_date",
            con, params=(code, end.strftime("%Y-%m-%d")))
    finally:
        con.close()
    if bars.empty:
        closes = pd.Series(dtype=float)
    else:
        closes = pd.Series(bars["close"].to_numpy(dtype=float), index=pd.to_datetime(bars["date"])).sort_index()
        if closes.index.max() > end:
            raise RunnerError("避风港收盘越过结束日")
    if divs.empty:
        divs = pd.DataFrame(columns=["ex_date", "amount", "prev_close"])
    else:
        divs = divs.copy()
        divs["ex_date"] = pd.to_datetime(divs["ex_date"])
        if divs["ex_date"].max() > end:
            raise RunnerError("避风港分红越过结束日")
    return closes, divs


def _guard_end(end: pd.Timestamp, allow_oos: bool) -> pd.Timestamp:
    end = pd.Timestamp(end).normalize()
    if allow_oos:
        if end != OOS_END:
            raise RunnerError(f"样本外结束日只能是 {OOS_END.date()}")
        return end
    if end > DESIGN_END:
        raise RunnerError(f"设计期拒绝结束日 {end.date()}：晚于 {DESIGN_END.date()}。样本外要带 --oos 和预注册 SHA。")
    return end


def _assert_design_stats(stats: dict) -> None:
    last = pd.Timestamp(stats["last"])
    if last > DESIGN_END:
        raise RunnerError("设计期汇总越过 2015-12-31")
    for year in stats["yearly"]:
        if int(year) > 2015:
            raise RunnerError("设计期逐年收益含有 2015 之后的年份")


def _book(asset: pd.Series, haven: pd.Series, overseas: pd.Series, out: float, back: float,
          a_weight: float, cost: float) -> dict[str, dict]:
    nav = (1.0 + asset).cumprod()
    signals = {
        "B0": pd.Series(1.0, index=asset.index),
        "B1": qulla_signal(nav),
        "B2": slow_valve_signal(nav, out, back),
    }
    arms = {}
    nets = {}
    for name, signal in signals.items():
        net, pos, switches = path_returns(asset, signal, haven, cost if name != "B0" else 0.0)
        arms[name] = summarize(net, pos, switches)
        nets[name] = net
    blends = {}
    for name, net in nets.items():
        blend = monthly_blend(net, overseas, a_weight)
        # 组合只描述收益，在场和切换仍是 A 股腿的事。
        empty = pd.Series(0.0, index=blend.index)
        summary = summarize(blend, empty, empty)
        summary["time_in_market"] = None
        summary["switches_per_year"] = None
        summary["switches"] = None
        blends[name] = summary
    return {"arms": arms, "portfolio": blends}


def _assert_book(book: dict) -> dict:
    for bucket in (book["arms"], book["portfolio"]):
        for stats in bucket.values():
            _assert_design_stats(stats)
    return book


def d4_gate(cash_arms: dict, end: pd.Timestamp) -> dict:
    """2% 现金假设下，年化和最大回撤与 d4 印刷值相差不超过 0.1pp。"""
    deltas = {}
    within = pd.Timestamp(end) == DESIGN_END
    for name, ref in D4_PUBLISHED.items():
        got = cash_arms[name]
        row = {
            "cagr_pp": (got["cagr"] - ref["cagr"]) * 100.0,
            "max_drawdown_pp": (got["max_drawdown"] - ref["max_drawdown"]) * 100.0,
        }
        if abs(row["cagr_pp"]) > D4_TOLERANCE * 100 or abs(row["max_drawdown_pp"]) > D4_TOLERANCE * 100:
            within = False
        if "switches_per_year" in ref:
            row["switches_per_year"] = got["switches_per_year"] - ref["switches_per_year"]
        deltas[name] = row
    return {
        "reference": "d4 印刷值",
        "tolerance_pp": 0.1,
        "applies": pd.Timestamp(end) == DESIGN_END,
        "within": bool(within and pd.Timestamp(end) == DESIGN_END),
        "deltas_pp": deltas,
    }


def build(panel: pd.DataFrame, haven_closes: pd.Series, dividends: pd.DataFrame, sleeves: dict,
          end: pd.Timestamp) -> dict:
    """设计期账本。结束日晚于 2015-12-31 直接拒绝。"""
    end = _guard_end(end, False)
    asset = equal_weight_returns(panel, sleeves["a_share"], end)
    overseas = equal_weight_returns(panel, sleeves["overseas"], end).reindex(asset.index)
    if overseas.isna().any() or not overseas.index.equals(asset.index):
        raise RunnerError("海外腿与 A 股腿的交易日对不齐")
    rate = cash_daily(sleeves["cash_annual"])
    flat = pd.Series(rate, index=asset.index, dtype=float)
    real = haven_total_return(haven_closes, dividends, asset.index, rate)
    cash = _assert_book(_book(asset, flat, overseas, sleeves["out"], sleeves["back"], sleeves["a_weight"], ROUND_TRIP_COST))
    cash_x2 = _assert_book(_book(asset, flat, overseas, sleeves["out"], sleeves["back"], sleeves["a_weight"], ROUND_TRIP_COST_DOUBLED))
    real_book = _assert_book(_book(asset, real, overseas, sleeves["out"], sleeves["back"], sleeves["a_weight"], ROUND_TRIP_COST))
    return {
        "cash": cash,
        "cash_doubled": cash_x2,
        "real": real_book,
        "haven_meta": _haven_meta(haven_closes, dividends, asset.index),
    }


def _haven_meta(closes: pd.Series, dividends: pd.DataFrame, index: pd.DatetimeIndex) -> dict:
    in_window = closes.loc[closes.index.isin(index)] if len(closes) else closes
    ex_dates = []
    if len(dividends):
        ex_dates = [str(pd.Timestamp(day).date()) for day in dividends["ex_date"] if pd.Timestamp(day) <= index.max()]
    return {
        "code": HAVEN_CODE,
        "quote_days": int(len(in_window)),
        "first_quote": None if in_window.empty else str(pd.Timestamp(in_window.index.min()).date()),
        "last_quote": None if in_window.empty else str(pd.Timestamp(in_window.index.max()).date()),
        "dividends": ex_dates,
        "cash_when_missing": CASH_ANNUAL,
    }


def _vs_cash(real_arms: dict, cash_arms: dict) -> dict:
    out = {}
    for name in ("B0", "B1", "B2"):
        out[name] = {
            "cagr_pp": (real_arms[name]["cagr"] - cash_arms[name]["cagr"]) * 100.0,
            "max_drawdown_pp": (real_arms[name]["max_drawdown"] - cash_arms[name]["max_drawdown"]) * 100.0,
        }
    return out


def run_design(panel_path: Path, market_db: Path, config_path: Path, end: pd.Timestamp) -> dict:
    """设计期。结束日晚于 2015-12-31 时在读完面板形状之前就拒绝后续收益计算。"""
    end = _guard_end(end, False)
    sleeves = load_sleeves(config_path)
    raw = read_table(panel_path, "panel")
    panel = validate_panel(clip_panel(raw, end))
    closes, dividends = load_haven(market_db, sleeves["haven_code"], end)
    built = build(panel, closes, dividends, sleeves, end)
    gate = d4_gate(built["cash"]["arms"], end)
    for stats in list(built["cash"]["arms"].values()) + list(built["real"]["arms"].values()):
        _assert_design_stats(stats)
    return {
        "window": "design",
        "end": str(end.date()),
        "oos": "未运行",
        "prereg_sha": FROZEN_SHA,
        "cash_assumption": {
            "haven": "年化 2%/252",
            "round_trip_cost": ROUND_TRIP_COST,
            "arms": built["cash"]["arms"],
            "doubled_cost": {
                "round_trip_cost": ROUND_TRIP_COST_DOUBLED,
                "one_way": 0.001,
                "arms": built["cash_doubled"]["arms"],
            },
            "criteria_on_design": {
                "label": "设计期演算，不是 §4 的样本外判定",
                "verdict": "样本外未运行。下面的 pass 只是同一套函数吃了设计期数字，不能当作 §4 结论。",
                **criteria(built["cash"]["arms"]["B0"], built["cash"]["arms"]["B1"],
                           built["cash_doubled"]["arms"]["B0"], built["cash_doubled"]["arms"]["B1"]),
            },
            "b2_vs_b0": {
                "both_worse": b2_both_worse(built["cash"]["arms"]["B0"], built["cash"]["arms"]["B2"]),
                "label": "设计期观察。去掉或保留慢阀只在样本外按 §5 决定。",
            },
        },
        "haven_511880": {
            "rule": "有收盘的日子用场内收盘价收益，除息日加上 cash_dividends 的 amount/prev_close；没有收益的日子按年化 2%/252。",
            "meta": built["haven_meta"],
            "round_trip_cost": ROUND_TRIP_COST,
            "arms": built["real"]["arms"],
            "vs_cash_assumption_pp": _vs_cash(built["real"]["arms"], built["cash"]["arms"]),
        },
        "portfolio": {
            "description": "A 股腿 70% + 海外 30%（纳指100 与标普500 等权），指数层面，每月第一个交易日回到目标权重，月内随收益漂移。",
            "qdii": "海外 ETF 溢价、额度冻结和场内折溢价在指数层面无法体现，本表不含这些规则。",
            "cash_assumption": built["cash"]["portfolio"],
            "haven_511880": built["real"]["portfolio"],
        },
        "d4_gate": gate,
    }


def run_oos(panel_path: Path, market_db: Path, config_path: Path) -> dict:
    """样本外。调用方必须已经写好锁。指标从样本起点连续计算，报告窗口从 2016-01-04 起。"""
    sleeves = load_sleeves(config_path)
    panel = validate_panel(clip_panel(read_table(panel_path, "panel"), OOS_END))
    closes, dividends = load_haven(market_db, sleeves["haven_code"], OOS_END)
    # 信号用上市以来的净值，不能在 2016 重新初始化。先在全历史上取信号，再切报告窗口。
    full_end = OOS_END
    asset_full = equal_weight_returns(panel, sleeves["a_share"], full_end)
    nav = (1.0 + asset_full).cumprod()
    signals = {
        "B0": pd.Series(1.0, index=asset_full.index),
        "B1": qulla_signal(nav),
        "B2": slow_valve_signal(nav, sleeves["out"], sleeves["back"]),
    }
    overseas_full = equal_weight_returns(panel, sleeves["overseas"], full_end).reindex(asset_full.index)
    flat_full = pd.Series(cash_daily(sleeves["cash_annual"]), index=asset_full.index, dtype=float)
    real_full = haven_total_return(closes, dividends, asset_full.index, cash_daily(sleeves["cash_annual"]))
    mask = (asset_full.index >= OOS_START) & (asset_full.index <= OOS_END)
    if not mask.any():
        raise RunnerError("样本外窗口没有交易日")
    overseas = overseas_full.loc[mask]
    # 生效持仓已经 shift 过。切窗口时保留窗口内的持仓，不在 2016 首日重新 fillna。
    def _window_book(haven_full: pd.Series, cost: float) -> dict:
        arms = {}
        nets = {}
        for name, signal in signals.items():
            net, pos, switches = path_returns(asset_full, signal, haven_full, 0.0 if name == "B0" else cost)
            net, pos, switches = net.loc[mask], pos.loc[mask], switches.loc[mask]
            arms[name] = summarize(net, pos, switches)
            nets[name] = net
        blends = {}
        for name, net in nets.items():
            blend = monthly_blend(net, overseas, sleeves["a_weight"])
            empty = pd.Series(0.0, index=blend.index)
            summary = summarize(blend, empty, empty)
            summary["time_in_market"] = None
            summary["switches_per_year"] = None
            summary["switches"] = None
            blends[name] = summary
        return {"arms": arms, "portfolio": blends}

    cash = _window_book(flat_full, ROUND_TRIP_COST)
    cash_x2 = _window_book(flat_full, ROUND_TRIP_COST_DOUBLED)
    real_book = _window_book(real_full, ROUND_TRIP_COST)
    return {
        "window": "oos",
        "start": str(OOS_START.date()),
        "end": str(OOS_END.date()),
        "prereg_sha": FROZEN_SHA,
        "cash_assumption": {
            "haven": "年化 2%/252",
            "round_trip_cost": ROUND_TRIP_COST,
            "arms": cash["arms"],
            "doubled_cost": {"round_trip_cost": ROUND_TRIP_COST_DOUBLED, "arms": cash_x2["arms"]},
            "criteria": criteria(cash["arms"]["B0"], cash["arms"]["B1"], cash_x2["arms"]["B0"], cash_x2["arms"]["B1"]),
            "b2_vs_b0": {"both_worse": b2_both_worse(cash["arms"]["B0"], cash["arms"]["B2"])},
        },
        "haven_511880": {"arms": real_book["arms"], "vs_cash_assumption_pp": _vs_cash(real_book["arms"], cash["arms"])},
        "portfolio": {
            "description": "A 股腿 70% + 海外 30%，指数层面，月度再平衡。",
            "qdii": "海外 ETF 溢价规则在指数层面无法体现，本表不含这些规则。",
            "cash_assumption": cash["portfolio"],
            "haven_511880": real_book["portfolio"],
        },
    }

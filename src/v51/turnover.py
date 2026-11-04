"""换手按来源拆开。不改规则。

一笔调仓先按目标权重的变化拆成互斥的来源，再把成交日账上的成本和买入额按这个比例分下去。
来源加总等于账上的成本和买入额。中国两个池只用设计期日账，日期不得晚于 2015-12-31。
"""
from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

from src.v3.engine.book import leg_cost
from src.v3.engine.sessions import decision_dates

from .params import V51Error

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results" / "v5.1" / "turnover"
DESIGN = ROOT / "results" / "v5.1" / "design"
G_DAILY = ROOT / "results" / "v5.1" / "other-market" / "v51"
SOURCES = ("第一层档位", "换市场", "周度替换", "前沿离场", "硬闸门", "换防守", "未分解")
WHY = {"硬闸门": "硬闸门", "F": "前沿离场", "周度换掉": "周度替换", "市场退出": "换市场"}
EPS = 1e-12


def _text(value) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    text = str(value).strip()
    return "" if text == "nan" else text


def _picks(value) -> list[str]:
    text = _text(value)
    if not text:
        return []
    return [part for part in text.split("|") if part]


def target_weights(risk: float, picks: list[str], defense: str) -> dict[str, float]:
    out: dict[str, float] = {}
    if picks and risk > 0.0:
        share = float(risk) / len(picks)
        for name in picks:
            out[name] = out.get(name, 0.0) + share
    rest = 1.0 - sum(out.values())
    if abs(rest) <= EPS:
        rest = 0.0
    if abs(rest) > 0.0 or defense not in out:
        out[defense] = out.get(defense, 0.0) + rest
    return out


def _book(weights: dict[str, float], defense: str) -> dict[str, float]:
    return {name: float(value) for name, value in weights.items() if name != defense and float(value) > EPS}


def _add(sink: dict[str, float], name: str, amount: float) -> None:
    if amount > EPS:
        sink[name] = sink.get(name, 0.0) + float(amount)


def model_legs(before: dict[str, float], after: dict[str, float], *, risk_before: float,
               risk_after: float, market_before: str, market_after: str, defense_before: str,
               defense_after: str, exit_why: dict[str, str]) -> dict[str, dict[str, float]]:
    """每个来源在每个名字上想成交的绝对额。名字之间可以先对冲，后面再缩回净变化。"""
    legs = {source: {} for source in SOURCES}
    before_book = _book(before, defense_before)
    after_book = _book(after, defense_after)
    if risk_after < risk_before - EPS and risk_before > EPS:
        frac = (risk_before - risk_after) / risk_before
        for name, weight in before_book.items():
            _add(legs["第一层档位"], name, weight * frac)
        _add(legs["第一层档位"], defense_after, risk_before - risk_after)
    elif risk_after > risk_before + EPS and risk_after > EPS:
        frac = (risk_after - risk_before) / risk_after
        for name, weight in after_book.items():
            _add(legs["第一层档位"], name, weight * frac)
        _add(legs["第一层档位"], defense_before, risk_after - risk_before)
    overlap = min(max(1.0 - risk_before, 0.0), max(1.0 - risk_after, 0.0))
    if defense_before != defense_after and overlap > EPS:
        _add(legs["换防守"], defense_before, overlap)
        _add(legs["换防守"], defense_after, overlap)
    base = min(max(risk_before, 0.0), max(risk_after, 0.0))
    if base > EPS and risk_before > EPS and risk_after > EPS:
        old = {name: weight / risk_before for name, weight in before_book.items()}
        new = {name: weight / risk_after for name, weight in after_book.items()}
        sell = {name: base * max(old.get(name, 0.0) - new.get(name, 0.0), 0.0) for name in set(old) | set(new)}
        buy = {name: base * max(new.get(name, 0.0) - old.get(name, 0.0), 0.0) for name in set(old) | set(new)}
        sell = {name: amount for name, amount in sell.items() if amount > EPS}
        buy = {name: amount for name, amount in buy.items() if amount > EPS}
        if market_before != market_after:
            source = "换市场"
            for name, amount in sell.items():
                _add(legs[source], name, amount)
            for name, amount in buy.items():
                _add(legs[source], name, amount)
        else:
            grouped: dict[str, float] = {}
            for name, amount in sell.items():
                source = WHY.get(exit_why.get(name, ""), "周度替换")
                _add(legs[source], name, amount)
                grouped[source] = grouped.get(source, 0.0) + amount
            total = sum(grouped.values())
            bought = sum(buy.values())
            if total > EPS:
                for source, amount in grouped.items():
                    share = amount / total
                    for name, size in buy.items():
                        _add(legs[source], name, size * share)
            elif bought > EPS:
                for name, size in buy.items():
                    _add(legs["周度替换"], name, size)
    return legs


def split_trade(before: dict[str, float], after: dict[str, float], *, risk_before: float,
                risk_after: float, market_before: str, market_after: str, defense_before: str,
                defense_after: str, exit_why: dict[str, str], fees: dict[str, float],
                trade_eps: float = EPS) -> dict[str, dict[str, float]]:
    """缩回净变化之后，来源的成本和单边换手加总等于这笔目标调仓。"""
    model = model_legs(
        before, after, risk_before=risk_before, risk_after=risk_after,
        market_before=market_before, market_after=market_after,
        defense_before=defense_before, defense_after=defense_after, exit_why=exit_why,
    )
    names = set(before) | set(after)
    for source in model:
        names.update(model[source])
    out = {source: {"turnover_one_way": 0.0, "cost": 0.0} for source in SOURCES}
    for name in names:
        actual = abs(float(after.get(name, 0.0)) - float(before.get(name, 0.0)))
        if actual <= trade_eps:
            continue
        explained = sum(float(model[source].get(name, 0.0)) for source in SOURCES if source != "未分解")
        fee = float(fees[name])
        if explained <= EPS:
            out["未分解"]["cost"] += actual * fee
            out["未分解"]["turnover_one_way"] += 0.5 * actual
            continue
        for source in SOURCES:
            if source == "未分解":
                continue
            share = float(model[source].get(name, 0.0)) / explained
            if share <= 0.0:
                continue
            out[source]["cost"] += actual * share * fee
            out[source]["turnover_one_way"] += 0.5 * actual * share
    check_cost, _, _ = leg_cost(before, after, fees, trade_eps)
    got = sum(item["cost"] for item in out.values())
    if abs(got - check_cost) > 1e-8:
        raise V51Error(f"换手成本拆开之后对不上（{got:.6g} 对 {check_cost:.6g}）")
    return out


def _exit_map(exits: pd.DataFrame) -> dict[pd.Timestamp, dict[str, str]]:
    found: dict[pd.Timestamp, dict[str, str]] = {}
    if exits is None or exits.empty:
        return found
    for row in exits.itertuples(index=False):
        day = pd.Timestamp(row.t).normalize()
        found.setdefault(day, {})[str(row.id)] = str(row.why)
    return found


def decompose(daily: pd.DataFrame, exits: pd.DataFrame, fees: dict[str, float], *,
              cash_id: str = "cash") -> pd.DataFrame:
    """按成交日所在年份汇总。成本和买入额用账上的数，按目标拆分的比例分。

    涨跌停改日成交的那部分对不上目标调仓日，记在未分解，好让合计等于日账。
    「全部」只把各来源加一次。逐年「合计」已经是这些来源的和，不能再加进去。
    """
    frame = daily.copy()
    frame.index = pd.DatetimeIndex(pd.to_datetime(frame.index)).normalize()
    if frame.index.has_duplicates or not frame.index.is_monotonic_increasing:
        raise V51Error("日账日期没有排好")
    reasons = _exit_map(exits)
    weekly = {pd.Timestamp(day).normalize() for day in decision_dates(frame.index, "week")}
    previous = {cash_id: 1.0}
    prev_risk = 0.0
    prev_market = ""
    prev_defense = cash_id
    planned: dict[pd.Timestamp, dict] = {}
    for pos, day in enumerate(frame.index):
        row = frame.iloc[pos]
        risk = float(row["risk"])
        defense = _text(row["defense"]) or cash_id
        market = _text(row["market"])
        weights = target_weights(risk, _picks(row["picks"]), defense)
        changed = any(
            abs(float(weights.get(name, 0.0)) - float(previous.get(name, 0.0))) > 1e-8
            for name in set(weights) | set(previous)
        )
        if (changed or day in weekly) and pos + 1 < len(frame.index):
            if changed:
                parts = split_trade(
                    previous, weights, risk_before=prev_risk, risk_after=risk,
                    market_before=prev_market, market_after=market,
                    defense_before=prev_defense, defense_after=defense,
                    exit_why=reasons.get(day, {}), fees=fees,
                )
            else:
                parts = {source: {"turnover_one_way": 0.0, "cost": 0.0} for source in SOURCES}
                parts["未分解"] = {"turnover_one_way": 1.0, "cost": 1.0}
            planned[frame.index[pos + 1]] = parts
        previous = weights
        prev_risk = risk
        prev_market = market
        prev_defense = defense
    buckets: dict[tuple[int, str], dict[str, float]] = {}
    for day in frame.index:
        book_cost = float(frame.at[day, "cost"])
        book_buy = float(frame.at[day, "buy"])
        if book_cost <= EPS and book_buy <= EPS:
            continue
        parts = planned.get(day)
        if parts is None:
            parts = {source: {"turnover_one_way": 0.0, "cost": 0.0} for source in SOURCES}
            parts["未分解"] = {"turnover_one_way": 1.0, "cost": 1.0}
        model_cost = sum(item["cost"] for item in parts.values())
        model_turn = sum(item["turnover_one_way"] for item in parts.values())
        year = int(day.year)
        for source in SOURCES:
            slot = buckets.setdefault((year, source), {"turnover_one_way": 0.0, "cost": 0.0, "days": 0})
            if model_cost > EPS:
                share_cost = parts[source]["cost"] / model_cost
            elif source == "未分解":
                share_cost = 1.0
            else:
                share_cost = 0.0
            if model_turn > EPS:
                share_turn = parts[source]["turnover_one_way"] / model_turn
            elif source == "未分解":
                share_turn = 1.0
            else:
                share_turn = 0.0
            if book_cost * share_cost > EPS or book_buy * share_turn > EPS:
                slot["days"] += 1
            slot["cost"] += book_cost * share_cost
            slot["turnover_one_way"] += book_buy * share_turn
    rows = []
    years = sorted({year for year, _source in buckets})
    grand_turn = 0.0
    grand_cost = 0.0
    for year in years:
        year_turn = 0.0
        year_cost = 0.0
        for source in SOURCES:
            item = buckets.get((year, source), {"turnover_one_way": 0.0, "cost": 0.0, "days": 0})
            rows.append({
                "year": year,
                "source": source,
                "turnover_one_way": item["turnover_one_way"],
                "cost": item["cost"],
                "days": int(item["days"]),
            })
            year_turn += item["turnover_one_way"]
            year_cost += item["cost"]
        rows.append({
            "year": year,
            "source": "合计",
            "turnover_one_way": year_turn,
            "cost": year_cost,
            "days": "",
        })
        grand_turn += year_turn
        grand_cost += year_cost
    if years:
        rows.append({
            "year": "全部",
            "source": "合计",
            "turnover_one_way": grand_turn,
            "cost": grand_cost,
            "days": "",
        })
        source_turn = sum(row["turnover_one_way"] for row in rows if row["source"] != "合计")
        source_cost = sum(row["cost"] for row in rows if row["source"] != "合计")
        if abs(grand_turn - source_turn) > 1e-8 or abs(grand_cost - source_cost) > 1e-8:
            if source_turn > EPS and abs(grand_turn - 2.0 * source_turn) <= 1e-6:
                raise V51Error("合计把来源加了两遍")
            raise V51Error(
                f"合计不等于来源之和（换手 {grand_turn:.6g} 对 {source_turn:.6g}，"
                f"成本 {grand_cost:.6g} 对 {source_cost:.6g}）"
            )
    return pd.DataFrame(rows)


def _load_daily(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, parse_dates=["date"], index_col="date")
    frame.index = pd.DatetimeIndex(frame.index).normalize()
    return frame


def _china(frame: pd.DataFrame, pool: str) -> None:
    if len(frame.index) and pd.Timestamp(frame.index.max()) > pd.Timestamp("2015-12-31"):
        raise V51Error(f"{pool} 的日账晚于 2015-12-31")


def run_turnover(*, out: Path = OUT) -> dict:
    """中国两个池加 G 池。不写账本，不写 LOCK。"""
    from src.v3.engine.spec import load_spec

    from .execute import open_market

    spec = load_spec()
    written = {}
    frames = []
    for pool in ("index", "tradable"):
        print(f"换手 {pool}", flush=True)
        market = open_market(pool, spec)
        daily = _load_daily(DESIGN / pool / "daily.csv")
        _china(daily, pool)
        exits = pd.read_csv(DESIGN / pool / "exits.csv", parse_dates=["t"])
        table = decompose(daily, exits, market.fees, cash_id=market.cash_id)
        table.insert(0, "pool", pool)
        folder = out
        folder.mkdir(parents=True, exist_ok=True)
        table.to_csv(folder / f"{pool}.csv", index=False, float_format="%.12g")
        frames.append(table)
        total = table[(table["year"].astype(str) == "全部") & (table["source"] == "合计")]
        written[pool] = {
            "turnover_one_way": float(total["turnover_one_way"].iloc[0]),
            "cost": float(total["cost"].iloc[0]),
        }
        book_cost = float(daily["cost"].sum())
        book_buy = float(daily["buy"].sum())
        if abs(written[pool]["cost"] - book_cost) > 1e-6 or abs(written[pool]["turnover_one_way"] - book_buy) > 1e-6:
            raise V51Error(f"{pool} 拆开的成本或换手和日账对不上")
    print("换手 G", flush=True)
    daily = _load_daily(G_DAILY / "daily.csv")
    exits = pd.read_csv(G_DAILY / "exits.csv", parse_dates=["t"])
    names = ["cash"]
    for value in daily["picks"].dropna().astype(str):
        names.extend(_picks(value))
    for value in daily["defense"].dropna().astype(str):
        if _text(value):
            names.append(_text(value))
    fees = {name: 0.001 for name in set(names)}
    table = decompose(daily, exits, fees, cash_id="cash")
    table.insert(0, "pool", "G")
    table.to_csv(out / "g.csv", index=False, float_format="%.12g")
    frames.append(table)
    total = table[(table["year"].astype(str) == "全部") & (table["source"] == "合计")]
    written["G"] = {
        "turnover_one_way": float(total["turnover_one_way"].iloc[0]),
        "cost": float(total["cost"].iloc[0]),
    }
    book_cost = float(daily["cost"].sum())
    book_buy = float(daily["buy"].sum())
    if abs(written["G"]["cost"] - book_cost) > 1e-6 or abs(written["G"]["turnover_one_way"] - book_buy) > 1e-6:
        raise V51Error("G 池拆开的成本或换手和日账对不上")
    summary = pd.concat(frames, ignore_index=True)
    summary.to_csv(out / "summary.csv", index=False, float_format="%.12g")
    return written

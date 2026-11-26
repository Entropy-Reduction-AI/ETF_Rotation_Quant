"""D45 第二版设计期复算。不覆盖 b215c57d 的 design-selection.json。"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from v6ind.d45_engine import (CUTOFF, INDUSTRY_PUBLISH, US_TRIN, first_on_or_after, month_end_mask,
                              on_calendar, run_slot, trin_from_prices, votes, _positive)
from v6ind.d45_french import us_prior, value_weighted_market
from v6ind.load import connect_readonly, load_fields, load_fx

OUT = Path(__file__).resolve().parent / "output"
OFFICIAL = Path("/tmp/49_Industry_Portfolios.csv")
A_SPEC = (
    ("csi300", "H00300", "沪深300", "", "2005-04-08"),
    ("csi500", "H00905", "中证500", "", "2007-01-15"),
    ("csi1000", "H00852", "中证1000", "", "2014-10-17"),
    ("chinext", "399006", "创业板指", "", "2010-06-01"),
    ("csi-dividend", "H00922", "中证红利", "红利", "2008-05-26"),
    ("theme-上证红利", "000015", "上证红利", "红利", "2005-01-04"),
    ("theme-中证红利低波动", "H30269", "红利低波动", "红利", "2013-12-19"),
    ("allshare-communication", "H00994", "全指通信服务", "通信服务", "2005-01-01"),
    ("allshare-discretionary", "H00989", "全指可选消费", "可选消费", "2005-01-01"),
    ("allshare-energy", "H00986", "全指能源", "能源", "2005-01-01"),
    ("allshare-financials-re", "H00992", "全指金融地产", "金融地产", "2005-01-01"),
    ("allshare-healthcare", "H00991", "全指医药卫生", "医药卫生", "2005-01-01"),
    ("allshare-industrials", "H00988", "全指工业", "工业", "2005-01-01"),
    ("allshare-it", "H00993", "全指信息技术", "信息技术", "2005-01-01"),
    ("allshare-materials", "H00987", "全指原材料", "原材料", "2005-01-01"),
    ("allshare-staples", "H00990", "全指主要消费", "主要消费", "2005-01-01"),
    ("allshare-utilities", "H00995", "全指公用事业", "公用事业", "2005-01-01"),
    ("theme-沪深300医药卫生", "000913", "沪深300医药卫生", "医药卫生", "2007-07-02"),
    ("theme-中证主要消费", "000932", "主要消费", "主要消费", "2009-07-03"),
    ("theme-中证农业", "000949", "农业", "主要消费", "2009-10-28"),
    ("theme-中证酒", "399987", "酒", "主要消费", "2014-12-10"),
    ("theme-中证全指半导体产品与设备", "H30184", "全指半导体产品与设备", "信息技术", "2013-07-15"),
    ("theme-中证全指软件", "H30202", "全指软件", "信息技术", "2013-07-15"),
    ("theme-中证人工智能主题", "930713", "人工智能主题", "信息技术", "2015-07-31"),
    ("theme-中证有色金属", "000819", "有色金属", "原材料", "2012-05-09"),
    ("theme-中证煤炭", "399998", "煤炭", "能源", "2015-02-13"),
    ("theme-中证钢铁", "930606", "钢铁", "原材料", "2015-03-31"),
    ("theme-中证银行", "399986", "银行", "金融地产", "2013-07-15"),
    ("theme-中证全指证券公司", "399975", "全指证券公司", "金融地产", "2013-07-15"),
    ("theme-中证全指房地产", "931775", "全指房地产", "金融地产", "2013-07-15"),
    ("theme-中证军工", "399967", "军工", "工业", "2013-12-26"),
    ("theme-中证机器人", "H30590", "机器人", "工业", "2015-02-10"),
    ("theme-中证全指通信设备", "931160", "全指通信设备", "信息技术", "2013-07-15"),
)
US_SPEC = (
    ("SPX", "SPX", "SPX", "", "2000-01-03"),
    ("NDX", "NDX", "NDX", "", "2000-01-03"),
    ("DJIA", "DJIA", "DJIA", "", "1990-04-25"),
    ("SOX", "SOX", "SOX", "信息技术", "2000-01-03"),
    ("NBI", "NBI", "NBI", "医疗保健", "2006-05-10"),
    ("XLY", "XLY", "XLY", "可选消费", "1998-12-22"),
    ("DWRTF", "DWRTF", "DWRTF", "房地产", "1998-12-31"),
    ("XLK", "XLK", "XLK", "信息技术", "1998-12-22"),
    ("XLV", "XLV", "XLV", "医疗保健", "1998-12-22"),
    ("XLE", "XLE", "XLE", "能源", "1998-12-22"),
    ("XLP", "XLP", "XLP", "必需消费", "1998-12-22"),
    ("XLF", "XLF", "XLF", "金融", "1998-12-22"),
    ("XLI", "XLI", "XLI", "工业", "1998-12-22"),
    ("XLB", "XLB", "XLB", "材料", "1998-12-22"),
    ("XLU", "XLU", "XLU", "公用事业", "1998-12-22"),
)
TRIN_A = {row[0] for row in A_SPEC if row[0].startswith("allshare-") or row[0] in {
    "csi500", "csi1000", "chinext"} or row[0].startswith("theme-")}
INDUSTRY = {row[0] for row in A_SPEC if row[0].startswith("allshare-")}
SEG = {"2006–10": ("2006-01-01", "2010-12-31"), "2011–15": ("2011-01-01", "2015-12-31"),
       "2006–15": ("2006-01-01", "2015-12-31")}
FROZEN_CAGR = {
    "BM-主（70/15/15）": {"2006–10": 21.81, "2011–15": 8.76, "2006–15": 15.10},
    "BM-同仓位（40/30/30）": {"2006–10": 12.48, "2011–15": 11.01, "2006–15": 11.74},
    "同结构等权、不设防守": {"2006–10": 14.26, "2011–15": 11.50, "2006–15": 12.87},
    "前 3、不设防守": {"2006–10": 19.29, "2011–15": 15.04, "2006–15": 17.15},
    "v6 毛（不计成本）": {"2006–10": 19.94, "2011–15": 14.16, "2006–15": 17.02},
    "v6 净（单边 0.2%，每日固定 60/40）": {"2006–10": 18.48, "2011–15": 12.67, "2006–15": 15.54},
    "v6 净（每月再平衡 60/40）": {"2006–10": 18.51, "2011–15": 12.14, "2006–15": 15.28},
    "参照：一级行业按发布日截断": {"2006–10": 13.87, "2011–15": 12.74, "2006–15": 13.30},
}


def dumps(payload: dict) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def bars_frame(con, codes: list[str]) -> dict[str, pd.DataFrame]:
    out = {}
    for code in codes:
        rows = load_fields(con, code)
        if not rows:
            out[code] = pd.DataFrame(columns=["close", "volume", "amount"])
            continue
        frame = pd.DataFrame(rows, columns=["date", "close", "volume", "amount"])
        frame["date"] = pd.to_datetime(frame["date"])
        frame = frame.set_index("date").sort_index()
        frame = frame[~frame.index.duplicated(keep="last")]
        if frame.index.max() > CUTOFF:
            raise SystemExit(f"{code} 读入超过截止日")
        out[code] = frame
    return out


def market_legs():
    from src.v3.engine.spec import load_spec
    from src.v4.r5.design import DESIGN_END, Markets
    signal = Markets(load_spec()).get("index", t4=False, allow_substitute=True).signal
    if signal.index.max() > CUTOFF:
        raise SystemExit("市场信号晚于 2015-12-31")
    frame = signal.loc[:DESIGN_END]
    frame = frame[frame[["csi300", "spx", "ndx100"]].notna().all(axis=1)]
    return frame.index, frame["cgb-10y"], frame["cash"]


def build_levels(raw: dict[str, pd.DataFrame], spec, calendar, fx: pd.Series | None, *,
                 industry_from: pd.Timestamp | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    levels = {}
    amounts = {}
    for name, code, _label, _tag, start in spec:
        frame = raw[code]
        close = _positive(frame["close"]) if "close" in frame else pd.Series(dtype=float)
        day = pd.Timestamp(start)
        if industry_from is not None and name.startswith("allshare-"):
            day = industry_from
        first = first_on_or_after(close, day)
        kept = close[close.index >= day] if first is not None else close.iloc[0:0]
        if fx is not None and not kept.empty:
            rate = fx.reindex(kept.index.union(fx.index)).ffill().reindex(kept.index)
            kept = kept * rate
        levels[name] = on_calendar(kept, calendar, first)
        amount = frame["amount"] if len(frame) else pd.Series(dtype=float)
        amount = amount[amount > 0] if len(amount) else amount
        if first is not None and len(amount):
            amount = amount[amount.index >= day]
        amounts[name] = amount.reindex(calendar)
    return pd.DataFrame(levels, index=calendar), pd.DataFrame(amounts, index=calendar)


def cagr(series: pd.Series, start: str, end: str) -> float:
    block = series.loc[start:end]
    return float((1.0 + block).prod() ** (252.0 / len(block)) - 1.0) * 100.0


def benchmark(levels: pd.DataFrame, weights: tuple[float, float, float]) -> pd.Series:
    parts = pd.DataFrame({
        "c": levels["csi300"].pct_change(),
        "n": levels["NDX"].pct_change(),
        "s": levels["SPX"].pct_change(),
    }).fillna(0.0)
    calendar = parts.index
    mask = month_end_mask(calendar)
    target = np.array(weights, dtype=float)
    held = target.copy()
    out = np.zeros(len(calendar))
    values = parts.to_numpy(dtype=float)
    for today, row in enumerate(values):
        gain = float((held * row).sum())
        out[today] = gain
        held = held * (1.0 + row) / (1.0 + gain)
        if mask[today]:
            held = target.copy()
    return pd.Series(out, index=calendar)


def mix_monthly(left: pd.Series, right: pd.Series, cost: float) -> pd.Series:
    calendar = left.index
    mask = month_end_mask(calendar)
    wa, wu = 0.4, 0.6
    out = np.zeros(len(calendar))
    reb = False
    for today in range(len(calendar)):
        fee = 0.0
        if reb:
            fee = cost * abs(wa - 0.4)
            wa, wu = 0.4, 0.6
            reb = False
        gain = wa * float(left.iloc[today]) + wu * float(right.iloc[today])
        out[today] = (1.0 + gain) * (1.0 - fee) - 1.0
        wa = wa * (1.0 + float(left.iloc[today])) / (1.0 + gain)
        wu = wu * (1.0 + float(right.iloc[today])) / (1.0 + gain)
        if mask[today]:
            reb = True
    return pd.Series(out, index=calendar)


def annualized(book: dict[str, pd.Series]) -> dict:
    return {name: {label: round(cagr(series, *window), 2) for label, window in SEG.items()}
            for name, series in book.items()}


def profile(log: dict) -> dict:
    frame = pd.DataFrame.from_dict(log, orient="index")
    frame.index = pd.DatetimeIndex(frame.index)
    frame = frame.loc["2006-01":"2015-11"]
    yearly = {}
    for year, group in frame.groupby(frame.index.year):
        yearly[str(year)] = {
            "紧张月数": int(group["紧张"].sum()),
            "年末可参选": int(group["可参选"].iloc[-1]),
            "年末把握p": float(group["p"].iloc[-1]),
            "平均股票仓位": round(float(group["股票仓位"].mean()), 2),
            "去重改了名单的月数": int(group["去重改了名单"].fillna(False).sum()),
        }
    return yearly


def eligible(log: dict, month: str) -> list[str]:
    stamp = [day for day in log if day.strftime("%Y-%m") == month]
    if not stamp:
        return []
    return sorted(code for code, value in log[max(stamp)]["分数"].items())


def example(log: dict, month: str, names: dict[str, str], capital: float) -> dict:
    stamp = max(day for day in log if day.strftime("%Y-%m") == month)
    row = log[stamp]
    held = [{"id": code, "name": names.get(code, code), "pct": round(row["分数"][code] * 100, 4)} for code in row["持有"]]
    return {
        "signal_date": stamp.strftime("%Y-%m-%d"),
        "votes": row["票数"],
        "stress": bool(row["紧张"]),
        "p": row["p"],
        "selected": held,
        "equity_weight": row.get("股票仓位"),
        "bond_weight": row["国债"],
        "cash_weight": row["现金"],
        "equity_wan": None if row.get("股票仓位") is None else round(capital * row["股票仓位"], 4),
        "bond_wan": round(capital * row["国债"], 4),
        "cash_wan": round(capital * row["现金"], 4),
        "eligible_count": row["可参选"],
    }


def vote_diff(old: pd.Series, new: pd.Series) -> dict:
    both = pd.concat([old.rename("old"), new.rename("new")], axis=1).dropna(how="all").fillna(0.0)
    changed = both[both["old"] != both["new"]]
    rows = [{"month": str(idx), "old": float(row.old), "new": float(row.new)} for idx, row in changed.iterrows()]
    return {"months": len(rows), "rows": rows}


def main() -> None:
    con = connect_readonly(ROOT / "data" / "market.sqlite")
    codes = sorted({row[1] for row in A_SPEC} | {row[0] for row in US_SPEC})
    raw = bars_frame(con, codes)
    fx_rows = load_fx(con)
    con.close()
    fx = pd.Series([value for _date, value in fx_rows], index=pd.to_datetime([day for day, _value in fx_rows]))
    fx = fx[~fx.index.duplicated(keep="last")].sort_index()
    if fx.index.max() > CUTOFF or fx.index.min() > pd.Timestamp("2005-12-31"):
        raise SystemExit(f"汇率区间异常 {fx.index.min().date()} {fx.index.max().date()}")
    calendar, bond, cash = market_legs()
    bond = bond.reindex(calendar)
    cash = cash.reindex(calendar)
    levels_a, amounts_a = build_levels(raw, A_SPEC, calendar, None)
    levels_u, _amounts_u = build_levels(raw, US_SPEC, calendar, fx)
    truncated_a, _truncated_amount = build_levels(raw, A_SPEC, calendar, None, industry_from=INDUSTRY_PUBLISH)
    tags_a = {row[0]: row[3] for row in A_SPEC}
    tags_u = {row[0]: row[3] for row in US_SPEC}
    names = {row[0]: row[2] for row in A_SPEC} | {row[0]: row[1] for row in US_SPEC}
    prior = us_prior(value_weighted_market(OFFICIAL.read_text(errors="replace")))
    trin_columns = [name for name in levels_a.columns if name in TRIN_A]
    us_prices = []
    us_amounts = []
    for code in US_TRIN:
        frame = raw[code]
        close = _positive(frame["close"])
        volume = frame["volume"].reindex(close.index)
        dollar = (close * volume).where(lambda values: values > 0)
        us_prices.append(close.rename(code))
        us_amounts.append(dollar.rename(code))
    us_px = pd.concat(us_prices, axis=1).sort_index()
    us_am = pd.concat(us_amounts, axis=1).reindex(us_px.index)
    books = {}
    diffs = {}
    vote_store = {}
    for clip in ("full", "expanding"):
        a_trin = trin_from_prices(levels_a[trin_columns], amounts_a[trin_columns], clip=clip)
        u_trin = trin_from_prices(us_px, us_am, clip=clip)
        vote_a = votes(levels_a, "csi300", a_trin)
        vote_u = votes(levels_u, "SPX", u_trin)
        vote_store[clip] = {"a": vote_a, "us": vote_u}
        runs = {}
        for mode, cost in (("ew", 0.0), ("top", 0.0), ("v6", 0.0)):
            left, _ta, log_a = run_slot(levels_a, "csi300", vote_a, bond, cash, tags_a, None, mode=mode, cost=cost)
            right, _tu, log_u = run_slot(levels_u, "SPX", vote_u, bond, cash, tags_u, prior, mode=mode, cost=cost)
            runs[mode] = (left, right, log_a, log_u)
        net_a, turn_a, log_a = run_slot(levels_a, "csi300", vote_a, bond, cash, tags_a, None, mode="v6", cost=0.002)
        net_u, turn_u, log_u = run_slot(levels_u, "SPX", vote_u, bond, cash, tags_u, prior, mode="v6", cost=0.002)
        vote_ref = votes(truncated_a, "csi300", a_trin)
        ref_a, _ref_turn, _ref_log = run_slot(truncated_a, "csi300", vote_ref, bond, cash, tags_a, None, mode="v6", cost=0.002)
        gross = 0.4 * runs["v6"][0] + 0.6 * runs["v6"][1]
        net = 0.4 * net_a + 0.6 * net_u
        book = {
            "BM-主（70/15/15）": benchmark(levels_u.join(levels_a[["csi300"]]), (0.70, 0.15, 0.15)),
            "BM-同仓位（40/30/30）": benchmark(levels_u.join(levels_a[["csi300"]]), (0.40, 0.30, 0.30)),
            "同结构等权、不设防守": 0.4 * runs["ew"][0] + 0.6 * runs["ew"][1],
            "前 3、不设防守": 0.4 * runs["top"][0] + 0.6 * runs["top"][1],
            "v6 毛（不计成本）": gross,
            "v6 净（单边 0.2%，每日固定 60/40）": net,
            "v6 净（每月再平衡 60/40）": mix_monthly(net_a, net_u, 0.002),
            "参照：一级行业按发布日截断": 0.4 * ref_a + 0.6 * net_u,
        }
        years = annualized(book)
        books[clip] = {
            "年化": years,
            "与冻结稿差": {name: {label: round(years[name][label] - target[label], 2) for label in SEG}
                          for name, target in FROZEN_CAGR.items()},
            "换手_除以10": {"A": round(turn_a / 10, 2), "US": round(turn_u / 10, 2)},
            "画像_截至2015-11": {"A": profile(log_a), "US": profile(log_u)},
            "名单": {month: eligible(log_a, month) for month in ("2014-12", "2015-11", "2015-12")},
            "例子": {
                "2013-04": {"A": example(log_a, "2013-04", names, 40), "US": example(log_u, "2013-04", names, 60)},
                "2015-08": {"A": example(log_a, "2015-08", names, 40), "US": example(log_u, "2015-08", names, 60)},
            },
            "起点经验月数": len(prior),
        }
    diffs = {
        "A": vote_diff(vote_store["full"]["a"], vote_store["expanding"]["a"]),
        "US": vote_diff(vote_store["full"]["us"], vote_store["expanding"]["us"]),
    }
    payload = {
        "label": "设计期",
        "not_oneshot": True,
        "rule": "D45v2 at a1b23743 / 2fbcecfa",
        "clip_full_is_frozen_code": books["full"],
        "clip_expanding_is_d45_10": books["expanding"],
        "monthly_vote_diff_full_minus_expanding": diffs,
        "fx": {"code": "USDCNY", "kind": "v4_series", "first": str(fx.index.min().date()),
               "last": str(fx.index.max().date()), "rows": int(len(fx))},
        "calendar": {"first": str(calendar.min().date()), "last": str(calendar.max().date()), "rows": int(len(calendar))},
    }
    raw_bytes = dumps(payload)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "d45-design.json"
    path.write_bytes(raw_bytes)
    print(json.dumps({"design_sha256": hashlib.sha256(raw_bytes).hexdigest(), "bytes": len(raw_bytes),
                      "prior_n": len(prior), "vote_diff_A": diffs["A"]["months"], "vote_diff_US": diffs["US"]["months"]},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()

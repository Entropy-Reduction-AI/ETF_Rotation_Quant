"""按 health_extra.py 的算术，用自己的 D48 日收益重算第 2–4 节。不覆盖旧锁定文件。"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_d45 import OFFICIAL, mix_monthly  # noqa: E402
from run_d47_health import (  # noqa: E402
    A_SPEC,
    US_SPEC,
    bars_frame,
    build_levels,
    k2a_book,
    load_fx,
    load_market,
    require_cutoff,
    signed_peer,
    sleeve_books,
    total_return_benchmarks,
)
from src.portfolio.config import load_config  # noqa: E402
from src.portfolio.replicate import _haven_returns, daily_book, load_haven_closes  # noqa: E402
from v6ind.d45_french import us_prior, value_weighted_market  # noqa: E402
from v6ind.load import connect_readonly  # noqa: E402

END = "2015-12-31"
OUT = Path(__file__).resolve().parent / "output" / "d48-health-extra-report-def.json"
COLS = ["v6", "连续性版", "K2A", "现行配置", "A1", "A2", "BM-主", "BM-同仓位"]


def h00300() -> pd.Series:
    con = sqlite3.connect(f"file:{(ROOT / 'data' / 'market.sqlite').resolve()}?mode=ro", uri=True)
    try:
        frame = pd.read_sql_query(
            "select date, close from bars where code='H00300' and adj='raw' and close>0 and date<=? order by date",
            con, params=(END,))
    finally:
        con.close()
    frame = frame.drop_duplicates("date", keep="last")
    series = pd.Series(frame["close"].to_numpy(dtype=float), index=pd.to_datetime(frame["date"])).sort_index()
    require_cutoff(series.index, "沪深300")
    return series


def current_book() -> pd.Series:
    panel = Path("/tmp/v6-d47-pkg/panel-2015-12-31.sqlite")
    if not panel.exists():
        raise SystemExit("没有已重建的 2015-12-31 面板")
    con = sqlite3.connect(f"{panel.resolve().as_uri()}?mode=ro", uri=True)
    try:
        late = con.execute("SELECT SUM(date > '2015-12-31') FROM panel").fetchone()[0]
        prices = pd.read_sql_query(
            "SELECT date, container, close, data_hole FROM panel WHERE date <= '2015-12-31'", con)
    finally:
        con.close()
    if int(late or 0):
        raise SystemExit("面板含有 2015-12-31 之后的行")
    prices["date"] = pd.to_datetime(prices["date"])
    prices = prices.loc[prices["data_hole"] == 0]
    wide = prices.pivot(index="date", columns="container", values="close").sort_index()
    require_cutoff(wide.index, "现行配置")
    cfg = load_config()
    state = pd.Series(1, index=wide.groupby(wide.index.to_period("M")).tail(1).index)
    haven = load_haven_closes(ROOT / "data" / "market.sqlite", cfg.haven_code, pd.Timestamp(END))
    return daily_book(wide, state, cfg, _haven_returns(wide.index, haven, cfg.cash_daily))


def own_returns() -> pd.DataFrame:
    if not OFFICIAL.exists():
        raise SystemExit(f"缺少已允许的 French 文件 {OFFICIAL}")
    con = connect_readonly(ROOT / "data" / "market.sqlite")
    codes = sorted({row[1] for row in A_SPEC} | {row[0] for row in US_SPEC})
    raw = bars_frame(con, codes)
    fx_rows = load_fx(con)
    con.close()
    fx = pd.Series([value for _day, value in fx_rows], index=pd.to_datetime([day for day, _value in fx_rows]))
    fx = fx[~fx.index.duplicated(keep="last")].sort_index()
    require_cutoff(fx.index, "汇率")
    frame = load_market()
    bond = frame["cgb-10y"].reindex(frame.index)
    cash = frame["cash"].reindex(frame.index)
    levels_a, amounts_a = build_levels(raw, A_SPEC, frame.index, None)
    levels_u, _amounts_u = build_levels(raw, US_SPEC, frame.index, fx)
    tags_a = {row[0]: row[3] for row in A_SPEC}
    tags_u = {row[0]: row[3] for row in US_SPEC}
    prior = us_prior(value_weighted_market(OFFICIAL.read_text(errors="replace")))
    us_prices, us_amounts = [], []
    for code in ("XLK", "XLV", "XLE", "XLY", "XLP", "XLF", "XLI", "XLB", "XLU"):
        close = raw[code]["close"]
        close = close[close > 0]
        close = close[~close.index.duplicated(keep="last")].sort_index()
        volume = raw[code]["volume"].reindex(close.index)
        us_prices.append(close.rename(code))
        us_amounts.append((close * volume).where(lambda values: values > 0).rename(code))
    us_px = pd.concat(us_prices, axis=1).sort_index()
    us_am = pd.concat(us_amounts, axis=1).reindex(us_px.index)
    books, _logs = sleeve_books(
        levels_a, amounts_a, levels_u, us_px, us_am, bond, cash, tags_a, tags_u, prior, "full")
    benchmarks = total_return_benchmarks()
    frame_out = pd.DataFrame({
        "v6": mix_monthly(books["v6"]["a"], books["v6"]["us"], 0.002),
        "连续性版": mix_monthly(books["cont"]["a"], books["v6"]["us"], 0.002),
        "K2A": k2a_book(frame),
        "现行配置": current_book(),
        "A1": signed_peer(ROOT / "results/v4/r5/design/A1/index/net.csv"),
        "A2": signed_peer(ROOT / "results/v4/r5/design/A2/index/net.csv"),
        "BM-主": benchmarks["BM-主"],
        "BM-同仓位": benchmarks["BM-同仓位"],
    })
    require_cutoff(frame_out.index, "日收益")
    return frame_out


def report_definitions(returns: pd.DataFrame, csi: pd.Series) -> dict:
    window = returns.loc["2006-01-01":END, COLS].dropna(how="any")
    nav = (1.0 + window).cumprod()
    drawdown = nav / nav.cummax() - 1.0
    monthly = (1.0 + window).resample("ME").prod() - 1.0
    up = monthly["BM-主"] > 0
    down = monthly["BM-主"] < 0

    def annual(series: pd.Series) -> float:
        return float((1.0 + series).prod() ** (252.0 / len(series)) - 1.0)

    character = {}
    for name in COLS:
        character[name] = {
            "年化": annual(window[name]),
            "最大回撤": float(drawdown[name].min()),
            "年化波动": float(window[name].std() * np.sqrt(252.0)),
            "上涨月份跟到": float(monthly.loc[up, name].mean() / monthly.loc[up, "BM-主"].mean()),
            "下跌月份只跟": float(monthly.loc[down, name].mean() / monthly.loc[down, "BM-主"].mean()),
        }
    crash = {}
    for tag, (start, stop) in {"2008": ("2007-01-01", "2008-12-31"), "2015": ("2015-01-01", "2015-12-31")}.items():
        peak = csi.loc[start:stop].idxmax()
        segment = window.loc[peak:].iloc[:251]
        path = (1.0 + segment).cumprod() / (1.0 + segment.iloc[0])
        level = csi.reindex(segment.index).ffill()
        level = level / level.iloc[0]
        names = ["v6", "K2A", "BM-主", "现行配置"]
        crash[tag] = {
            "peak": str(pd.Timestamp(peak).date()),
            "days": int(len(segment)),
            "low": {**{name: float(path[name].min() - 1.0) for name in names}, "沪深300": float(level.min() - 1.0)},
            "end": {**{name: float(path[name].iloc[-1] - 1.0) for name in names}, "沪深300": float(level.iloc[-1] - 1.0)},
        }
    month_close = csi.resample("ME").last()
    month_return = month_close.pct_change()
    year_return = month_close.pct_change(12)
    labels = pd.Series(
        np.where(year_return > 0, np.where(month_return > 0, "牛市", "回调"), np.where(month_return < 0, "熊市", "反弹")),
        index=month_close.index)
    labels = labels[year_return.notna()].reindex(monthly.index)
    regimes = {}
    for name in ("牛市", "回调", "熊市", "反弹"):
        mask = labels == name
        row = {"月数": int(mask.sum())}
        for ref in ("BM-主", "BM-同仓位", "K2A"):
            excess = (monthly.loc[mask, "v6"] - monthly.loc[mask, ref]) * 100.0
            row[ref] = {
                "合计": float(excess.sum()),
                "跑赢月份": float((excess > 0).mean()) if len(excess) else None,
            }
        regimes[name] = row
    firsts = window.groupby(window.index.to_period("M")).head(1).index
    anystart = {}
    for years, length in ((1, 252), (3, 756), (5, 1260)):
        starts = [day for day in firsts if window.index.get_loc(day) + length <= len(window)]
        block = {}
        for ref in ("BM-主", "BM-同仓位", "K2A", "现行配置", "A1"):
            diffs = []
            for day in starts:
                position = window.index.get_loc(day)
                segment = window.iloc[position:position + length]
                left = (1.0 + segment["v6"]).prod() ** (252.0 / length) - 1.0
                right = (1.0 + segment[ref]).prod() ** (252.0 / length) - 1.0
                diffs.append((left - right) * 100.0)
            values = np.asarray(diffs, dtype=float)
            block[ref] = {
                "起点数": int(len(values)),
                "跑赢占比": float((values > 0).mean()),
                "中位": float(np.median(values)),
                "最差": float(values.min()),
            }
        anystart[str(years)] = block
    return {
        "definition": "health_extra.py at f0792ddb: common window, 251-day crash from H00300 peak, monthly excess, 252/756/1260 trading days",
        "window": [str(window.index[0].date()), str(window.index[-1].date())],
        "n_days": int(len(window)),
        "months": {"up": int(up.sum()), "down": int(down.sum())},
        "character": character,
        "crash": crash,
        "regimes": regimes,
        "anystart": anystart,
    }


def main() -> None:
    payload = report_definitions(own_returns(), h00300())
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(hashlib.sha256(OUT.read_bytes()).hexdigest())
    print(OUT)


if __name__ == "__main__":
    main()

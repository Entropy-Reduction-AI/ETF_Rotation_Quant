"""Reviewer 数据 plumbing（日历、债券收益、A 股候选层级）。不含挑选/回测逻辑。"""
from __future__ import annotations

import sqlite3
import tomllib
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
END = "2015-12-31"


def load_market_bond_cash(cal: pd.DatetimeIndex) -> tuple[pd.Series, pd.Series]:
    """日度 cash / 10 年国债收益（与 v4 design 信号表一致，仅作现金腿）。"""
    from src.v3.engine.spec import load_spec
    from src.v4.r5.design import Markets

    p = Markets(load_spec()).get("index", t4=False, allow_substitute=True).signal.loc[:END]
    bond = p["cgb-10y"].reindex(cal).fillna(0.0)
    cash = p["cash"].reindex(cal).fillna(0.0)
    return bond, cash


def load_a_lvl_calendar() -> tuple[pd.DataFrame, pd.DatetimeIndex, pd.Series]:
    """A_OLD：csi300 全收益（H00300）+ 10 个 allshare 列 + 宽基/主题列；归一化到首点。"""
    from src.v3.engine.spec import load_spec
    from src.v4.r5.design import Markets

    m = Markets(load_spec()).get("index", t4=False, allow_substitute=True)
    p = m.signal.loc[:END]
    a_cols = ["csi300"] + [c for c in p.columns if c.startswith("allshare-")]
    for extra in ("csi500", "csi1000", "csi-dividend", "chinext"):
        if extra in p.columns:
            a_cols.append(extra)
    lvl = np.exp(np.log1p(p[a_cols].fillna(0)).cumsum()).where(p[a_cols].notna().cumsum() > 0)
    cal = lvl.index
    return lvl, cal, lvl["csi300"]


def load_publish_dates() -> dict[str, str]:
    pub = {}
    for c in tomllib.load(open(ROOT / "config/v3/universe.toml", "rb"))["container"]:
        r = c.get("research", {})
        cid = c.get("id") or c.get("container_id")
        if r.get("publish_date") and r["publish_date"] != "取不到":
            pub[cid] = r["publish_date"]
    pub.setdefault("chinext", "2010-06-01")
    return pub


def _bars(con, code: str) -> pd.DataFrame:
    d = pd.read_sql_query(
        "select date, open, close, amount from bars where code=? and adj='raw' and close>0 and date<=? order by date",
        con,
        params=(code, END),
    )
    d = d.drop_duplicates("date", keep="last")
    d.index = pd.to_datetime(d["date"])
    return d


def load_official_a_pool(a_old: pd.DataFrame, cal: pd.DatetimeIndex) -> pd.DataFrame:
    """按发布日截断的官方候选池 A（第 39/53 行口径）。"""
    pub = load_publish_dates()
    ro = pd.read_csv(ROOT / "results/v51-diag/d37/s1-splice-roster.csv")
    th = ro[(ro["class"] == "A股") & (ro["status"] == "spliced") & ro["publish_date"].notna()]
    con = sqlite3.connect(ROOT / "data/market.sqlite")
    a = a_old.copy()
    for c in a.columns:
        if c in pub:
            a.loc[: pd.Timestamp(pub[c]) - pd.Timedelta(days=1), c] = np.nan
        if a[c].notna().any():
            a[c] = a[c] / a[c].dropna().iloc[0]
    for _, r in th.iterrows():
        d = _bars(con, str(r["index_code"]))
        if d.empty:
            continue
        d = d.loc[r["publish_date"] :]
        if len(d) < 60:
            continue
        a[r["container_id"]] = d["close"].reindex(cal).ffill().where(lambda s, d=d: s.index >= d.index[0])
    return a.loc[:END]


def load_sector_tags_a() -> dict[str, str]:
    return tomllib.load(open(ROOT / "config/v6-preflight/sector-tags.toml", "rb"))["a"]


def load_allshare_overnight_from_incoming() -> dict[str, pd.Series]:
    """全指一级隔夜：incoming 000986–000995 价格指数开盘价。"""
    l1 = [
        "allshare-energy",
        "allshare-materials",
        "allshare-industrials",
        "allshare-discretionary",
        "allshare-staples",
        "allshare-healthcare",
        "allshare-financials-re",
        "allshare-it",
        "allshare-communication",
        "allshare-utilities",
    ]
    out = {}
    for i, cid in enumerate(l1):
        d = pd.read_csv(
            ROOT / f"incoming/grok-csi-allshare-l1-20261123/dailies/{986 + i:06d}.index-perf.csv",
            dtype={"tradeDate": str},
        )
        d.index = pd.to_datetime(d["tradeDate"])
        d = d.loc[:END]
        x = np.log(d["open"] / d["close"].shift(1)).where((d["open"] > 0) & (d["close"].shift(1) > 0))
        out[cid] = x.replace([np.inf, -np.inf], np.nan)
    return out


def load_official_overnight(a_cols: list[str], cal: pd.DatetimeIndex) -> dict[str, pd.Series]:
    """官方池中有开盘价的候选：sqlite raw + 全指 incoming。"""
    on = load_allshare_overnight_from_incoming()
    l1 = [
        "allshare-energy",
        "allshare-materials",
        "allshare-industrials",
        "allshare-discretionary",
        "allshare-staples",
        "allshare-healthcare",
        "allshare-financials-re",
        "allshare-it",
        "allshare-communication",
        "allshare-utilities",
    ]
    l1map = dict(zip(l1, [f"H0098{i}" for i in range(6, 10)] + [f"H0099{i}" for i in range(6)]))
    ro = pd.read_csv(ROOT / "results/v51-diag/d37/s1-splice-roster.csv")
    code_of = {
        r["container_id"]: str(r["index_code"])
        for _, r in ro.iterrows()
        if r["class"] == "A股" and isinstance(r["index_code"], str)
    }
    code_of["chinext"] = "399006"
    con = sqlite3.connect(ROOT / "data/market.sqlite")
    for c in a_cols:
        if c in on:
            continue
        code = l1map.get(c) or code_of.get(c)
        if not code:
            continue
        d = _bars(con, code)
        if d.empty or d["open"].notna().sum() < 100:
            continue
        o = np.log(d["open"] / d["close"].shift(1)).where(d["open"] > 0)
        on[c] = o.replace([np.inf, -np.inf], np.nan).reindex(cal)
    return {k: v for k, v in on.items() if k in a_cols}


def load_p3_sw(cal: pd.DatetimeIndex, csi: pd.Series) -> pd.DataFrame:
    swd = ROOT / "incoming/grok-sw-l1-20261123/dailies"
    cols = {"csi300": csi}
    for f in sorted(swd.glob("*.trend.csv")):
        d = pd.read_csv(f, dtype={"bargaindate": str})
        d.index = pd.to_datetime(d["bargaindate"])
        if d.index[0] > pd.Timestamp(END):
            continue
        d = d.loc[:END]
        cid = "sw-" + f.name.split(".")[0]
        cols[cid] = d["closeindex"].reindex(cal).ffill().where(lambda s, d=d: s.index >= d.index[0])
    return pd.DataFrame(cols).loc[:END]


def load_p3_sw_overnight(cal: pd.DatetimeIndex) -> dict[str, pd.Series]:
    swd = ROOT / "incoming/grok-sw-l1-20261123/dailies"
    on = {}
    for f in sorted(swd.glob("*.trend.csv")):
        d = pd.read_csv(f, dtype={"bargaindate": str})
        d.index = pd.to_datetime(d["bargaindate"])
        if d.index[0] > pd.Timestamp(END):
            continue
        d = d.loc[:END]
        cid = "sw-" + f.name.split(".")[0]
        x = np.log(d["openindex"] / d["closeindex"].shift(1)).where(
            (d["openindex"] > 0) & (d["closeindex"].shift(1) > 0)
        )
        on[cid] = x.replace([np.inf, -np.inf], np.nan).reindex(cal)
    return on
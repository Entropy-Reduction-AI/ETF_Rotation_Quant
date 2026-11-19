#!/usr/bin/env python3
"""Reviewer 独立复算：D38 第 39 行每年末 A 股可参选候选个数（发布满 12 个月）。

数据源（仅读）：
  - config/v3/universe.toml（container.research.publish_date）
  - results/v51-diag/d37/s1-splice-roster.csv（主题 publish_date）
  - data/market.sqlite bars（raw，≤2015-12-31）
"""
from __future__ import annotations

import json
import sqlite3
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent / "d38-r2041-recalc.json"


def load_publish_dates() -> dict[str, str]:
    pub: dict[str, str] = {}
    for c in tomllib.load(open(ROOT / "config/v3/universe.toml", "rb"))["container"]:
        r = c.get("research", {})
        cid = c.get("id") or c.get("container_id")
        if r.get("publish_date") and r["publish_date"] != "取不到":
            pub[cid] = r["publish_date"]
    pub.setdefault("chinext", "2010-06-01")
    ro = pd.read_csv(ROOT / "results/v51-diag/d37/s1-splice-roster.csv")
    th = ro[(ro["class"] == "A股") & (ro["status"] == "spliced") & ro["publish_date"].notna()]
    for _, row in th.iterrows():
        pub[str(row["container_id"])] = str(row["publish_date"])
    return pub


def build_a_matrix(pub: dict[str, str]) -> tuple[pd.DataFrame, pd.DatetimeIndex]:
    con = sqlite3.connect(ROOT / "data/market.sqlite")
    end = "2015-12-31"

    def bars(code: str) -> pd.DataFrame:
        d = pd.read_sql_query(
            "select date, close from bars where code=? and adj='raw' and close>0 and date<=? order by date",
            con,
            params=(code, end),
        )
        d = d.drop_duplicates("date", keep="last")
        d.index = pd.to_datetime(d["date"])
        return d

    # 母指数与宽基（与 a_official / topn_system 列集合一致）
    from src.v3.engine.spec import load_spec
    from src.v4.r5.design import Markets

    m = Markets(load_spec()).get("index", t4=False, allow_substitute=True)
    P = m.signal.loc[:end]
    P = P[P[["csi300", "spx", "ndx100"]].notna().all(axis=1)]
    idx = P.index
    a_c = ["csi300"] + [c for c in P.columns if c.startswith("allshare-")] + [
        "csi500",
        "csi1000",
        "csi-dividend",
        "chinext",
    ]
    A = np.exp(np.log1p(P[a_c].fillna(0)).cumsum()).where(P[a_c].notna().cumsum() > 0)

    for c in A.columns:
        if c in pub:
            A.loc[: pd.Timestamp(pub[c]) - pd.Timedelta(days=1), c] = np.nan
        fv = A[c].dropna()
        if len(fv):
            A[c] = A[c] / fv.iloc[0]

    ro = pd.read_csv(ROOT / "results/v51-diag/d37/s1-splice-roster.csv")
    th = ro[(ro["class"] == "A股") & (ro["status"] == "spliced") & ro["publish_date"].notna()]
    for _, r in th.iterrows():
        d = bars(str(r["index_code"]))
        if d.empty:
            continue
        d = d.loc[r["publish_date"] :]
        if len(d) < 60:
            continue
        cid = r["container_id"]
        s = d["close"].reindex(idx).ffill().where(lambda _: idx >= d.index[0])
        fv = s.dropna()
        if len(fv):
            A[cid] = s / fv.iloc[0]

    return A, idx


def yearly_selectable_counts(A: pd.DataFrame) -> dict[str, int]:
    """每个非母指数候选： rolling 252 日非空和 ≥252 才可参选；按年末统计。"""
    ncand = (A.drop(columns=["csi300"]).notna().astype(float).rolling(252).sum() >= 252).sum(axis=1)
    return {str(k): int(v) for k, v in ncand.groupby(ncand.index.year).last().items()}


def main() -> None:
    pub = load_publish_dates()
    A, _ = build_a_matrix(pub)
    derived = yearly_selectable_counts(A)
    claimed = json.loads((ROOT / "results/v6-preflight/a-official.json").read_text(encoding="utf-8"))[
        "每年末 A 股可参选候选个数（发布满 12 个月）"
    ]
    pr_claim = [1, 1, 3, 4, 6, 6, 17, 18, 24, 27]
    years_2006_2015 = [str(y) for y in range(2006, 2016)]
    derived_slice = [derived.get(y) for y in years_2006_2015]
    mismatch_official = {y: {"claimed": claimed.get(y), "derived": derived.get(y)} for y in derived if str(derived.get(y)) != str(claimed.get(y))}
    payload = {
        "check": "row39_yearly_candidate_counts",
        "sources": [
            "config/v3/universe.toml",
            "results/v51-diag/d37/s1-splice-roster.csv",
            "data/market.sqlite",
            "src/v4/r5/design Markets index ≤2015",
        ],
        "derived_all_years": derived,
        "claimed_a_official_json": claimed,
        "pr_body_sequence_2006_2015": pr_claim,
        "derived_2006_2015": derived_slice,
        "match_a_official": len(mismatch_official) == 0,
        "match_pr_body_sequence": derived_slice == pr_claim,
        "mismatches_vs_a_official": mismatch_official,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
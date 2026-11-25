"""设计期 ≤2015：可参选名单、两个月份示例、附表 B、D45-10 新旧 TRIN。

美股把握 p 的 French 49 行业文件不在仓库时，只暂停用到起点经验的计算。
"""

from __future__ import annotations

import hashlib
import json
import tomllib
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from src.v6.engine import benchmark, cagr_pct, mix_daily, mix_monthly, signal_month, slot
from src.v6.prior import us_prior
from src.v6.synthetic import no_help
from src.v6.guard import DESIGN_END_TEXT, IsolationError, assert_not_after, install_readers, restore_readers
from src.v6.load import FREEZE, eligible_on, load_panels, momentum
from src.v6.trin import clip_expanding, clip_full_sample, month_end_mean, raw_ratio

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results" / "v6"
FRENCH_SHA = "633958bf36d25da6d95876bfc468536029db600c32c65b7a3e0f7fba59a04609"
PRIOR_NOTE = "哈希与登记值相同，但没有第二份原件逐格比较，不记验收通过"
PANEL = ROOT / "results/v6/french-49-192607-199812"
DTB3_PATH = ROOT / "results/v5/other-market/raw/DTB3.csv"
TAGS = tomllib.load(open(ROOT / "config/v6-preflight/sector-tags.toml", "rb"))
PROFILE_END = pd.Timestamp("2015-11-30")
PROFILE_START = pd.Timestamp("2006-01-01")

PUBLISHED_CAGR = {
    "BM-主（70/15/15）": {"2006–10": 21.81, "2011–15": 8.76, "2006–15": 15.10},
    "BM-同仓位（40/30/30）": {"2006–10": 12.48, "2011–15": 11.01, "2006–15": 11.74},
    "同结构等权、不设防守": {"2006–10": 14.26, "2011–15": 11.50, "2006–15": 12.87},
    "前 3、不设防守": {"2006–10": 19.29, "2011–15": 15.04, "2006–15": 17.15},
    "v6 毛（不计成本）": {"2006–10": 19.94, "2011–15": 14.16, "2006–15": 17.02},
    "v6 净（单边 0.2%，每日固定 60/40）": {"2006–10": 18.48, "2011–15": 12.67, "2006–15": 15.54},
    "v6 净（每月再平衡 60/40）": {"2006–10": 18.51, "2011–15": 12.14, "2006–15": 15.28},
    "参照：一级行业按发布日截断": {"2006–10": 13.87, "2011–15": 12.74, "2006–15": 13.30},
}
PUBLISHED_SPLIT = {
    "仓位差": {"2006–10": -9.33, "2011–15": 2.25, "2006–15": -3.36},
    "等权倾斜": {"2006–10": 1.78, "2011–15": 0.49, "2006–15": 1.13},
    "挑选": {"2006–10": 5.03, "2011–15": 3.54, "2006–15": 4.28},
    "防守": {"2006–10": 0.65, "2011–15": -0.88, "2006–15": -0.13},
    "成本": {"2006–10": -1.46, "2011–15": -1.49, "2006–15": -1.48},
    "合计（v6 净 − BM-主）": {"2006–10": -3.33, "2011–15": 3.91, "2006–15": 0.44},
}
# 附表 B 逐年信号。2015 年这一行是复算脚本切到 2015-11 的「年末」，不是 12 月信号日。
PUBLISHED_YEAR = {
    2006: dict(a_stress=0, a_dedupe=0, a_n=12, a_p=0.500, a_w=1.00, u_stress=0, u_dedupe=0, u_p=1.000, u_w=1.00),
    2007: dict(a_stress=0, a_dedupe=0, a_n=12, a_p=0.500, a_w=1.00, u_stress=3, u_dedupe=0, u_p=1.000, u_w=1.00),
    2008: dict(a_stress=12, a_dedupe=2, a_n=14, a_p=0.500, a_w=0.25, u_stress=12, u_dedupe=2, u_p=0.997, u_w=0.31),
    2009: dict(a_stress=2, a_dedupe=6, a_n=15, a_p=0.311, a_w=0.83, u_stress=4, u_dedupe=10, u_p=0.995, u_w=0.58),
    2010: dict(a_stress=6, a_dedupe=8, a_n=17, a_p=0.439, a_w=0.66, u_stress=3, u_dedupe=0, u_p=0.996, u_w=1.00),
    2011: dict(a_stress=8, a_dedupe=7, a_n=18, a_p=0.341, a_w=0.52, u_stress=5, u_dedupe=0, u_p=0.996, u_w=0.94),
    2012: dict(a_stress=8, a_dedupe=8, a_n=18, a_p=0.439, a_w=0.26, u_stress=0, u_dedupe=2, u_p=0.997, u_w=1.00),
    2013: dict(a_stress=0, a_dedupe=5, a_n=19, a_p=0.439, a_w=1.00, u_stress=0, u_dedupe=6, u_p=0.997, u_w=1.00),
    2014: dict(a_stress=2, a_dedupe=5, a_n=25, a_p=0.503, a_w=0.91, u_stress=0, u_dedupe=3, u_p=0.997, u_w=1.00),
    2015: dict(a_stress=4, a_dedupe=2, a_n=27, a_p=0.572, a_w=0.82, u_stress=2, u_dedupe=7, u_p=0.997, u_w=1.00),
}
SEGMENTS = {
    "2006–10": ("2006-01-01", "2010-12-31"),
    "2011–15": ("2011-01-01", "2015-12-31"),
    "2006–15": ("2006-01-01", "2015-12-31"),
}


def _sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _code_sha() -> str:
    digest = hashlib.sha256()
    for folder in (ROOT / "src/v6", ROOT / "config/v6"):
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                digest.update(path.relative_to(ROOT).as_posix().encode())
                digest.update(path.read_bytes())
    return digest.hexdigest()


def find_french() -> Path | None:
    roots = [ROOT / "operations/reviews/diag", ROOT / "data/research", ROOT / "incoming"]
    found = []
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("49_Industry_Portfolios.csv"):
            if "data_census" in path.as_posix() or "europe-japan" in path.as_posix():
                continue
            found.append(path)
    if not found:
        return None
    if len(found) > 1:
        raise IsolationError(f"French 文件不止一份：{found}")
    return found[0]


def write_eligible(panels) -> dict:
    tags = TAGS["a"]
    scores = momentum(panels["A"])
    assert_not_after(scores.index, "12-1")
    summary = {}
    for year, month, label in ((2014, 12, "2014-12"), (2015, 12, "2015-12"), (2015, 11, "2015-11")):
        day = signal_month(scores.index, year, month)
        row = scores.loc[day]
        frame = pd.DataFrame({
            "signal_month": label,
            "signal_date": day.date().isoformat(),
            "candidate_id": row.index.astype(str),
            "sector_tag": [tags.get(c, "") for c in row.index],
            "is_parent": [c == "csi300" for c in row.index],
            "m12": row.to_numpy(dtype=float),
            "eligible": np.isfinite(row.to_numpy(dtype=float)),
        }).sort_values(["eligible", "candidate_id"], ascending=[False, True])
        all_path = OUT / f"candidates-a-{label}.csv"
        elig_path = OUT / f"eligible-a-{label}.csv"
        frame.to_csv(all_path, index=False)
        frame.loc[frame["eligible"]].drop(columns=["eligible"]).to_csv(elig_path, index=False)
        names = frame.loc[frame["eligible"], "candidate_id"].tolist()
        summary[label] = {
            "signal_date": day.date().isoformat(),
            "eligible_count": len(names),
            "eligible_ids": names,
            "includes_parent": "csi300" in names,
            "eligible_file": str(elig_path.relative_to(ROOT)),
            "all_candidates_file": str(all_path.relative_to(ROOT)),
        }
    return summary


def _a_daily(panels) -> pd.Series:
    amount = pd.DataFrame(panels["amt"]).astype(float).reindex(panels["idx"])
    prices = panels["A_pub"].reindex(columns=list(amount.columns))
    return raw_ratio(prices, amount, min_movers=4)


def _us_daily(panels) -> pd.Series:
    originals = install_readers(pd)
    try:
        prices, amount, _parent = panels["vs"]["universe"](
            panels["vs"]["US"], False, "SPX", False, "1999-01-01")
    finally:
        restore_readers(pd, originals)
    assert_not_after(prices.index, "美股TRIN")
    return raw_ratio(prices, amount, min_movers=None)


def _swap_votes(panels, parent, series, levels):
    saved = panels["trin"][parent]
    panels["trin"][parent] = series
    try:
        total, _ = panels["votes"](levels, parent, ["均线", "宽度", "TRIN"])
        trin_vote, _ = panels["votes"](levels, parent, ["TRIN"])
    finally:
        panels["trin"][parent] = saved
    return total, trin_vote


def vote_diff(panels) -> pd.DataFrame:
    rows = []
    rebuilt = {}
    jobs = (
        ("A", "csi300", panels["A"], _a_daily(panels)),
        ("US", "SPX", panels["US"], _us_daily(panels)),
    )
    for sleeve, parent, levels, daily in jobs:
        old_built = month_end_mean(clip_full_sample(daily))
        new = month_end_mean(clip_expanding(daily))
        frozen = panels["trin"][parent]
        both = pd.concat([frozen.rename("frozen"), old_built.rename("rebuilt")], axis=1).dropna()
        gap = float((both["frozen"] - both["rebuilt"]).abs().max()) if len(both) else float("nan")
        rebuilt[sleeve] = {"old_matches_frozen_max_abs": gap, "months": int(len(both))}
        if not np.isfinite(gap) or gap > 1e-8:
            raise IsolationError(f"{sleeve} 旧 TRIN 与冻结序列不一致，最大差 {gap}")
        old_total, old_trin = _swap_votes(panels, parent, frozen, levels)
        new_total, new_trin = _swap_votes(panels, parent, new, levels)
        joined = pd.DataFrame({
            "old_total": old_total, "new_total": new_total,
            "old_trin": old_trin, "new_trin": new_trin,
        }).dropna(how="all")
        joined = joined.loc["2006-01":"2015-12"]
        changed = joined[(joined["old_trin"] != joined["new_trin"]) | (joined["old_total"] != joined["new_total"])]
        for period, row in changed.iterrows():
            rows.append({
                "sleeve": sleeve,
                "month": str(period),
                "old_trin_vote": int(row["old_trin"]),
                "new_trin_vote": int(row["new_trin"]),
                "old_total": int(row["old_total"]),
                "new_total": int(row["new_total"]),
            })
        rebuilt[sleeve]["changed_months"] = int(len(changed))
        rebuilt[sleeve]["statement"] = "0个月" if not changed.shape[0] else f"{int(changed.shape[0])}个月"
    columns = ["sleeve", "month", "old_trin_vote", "new_trin_vote", "old_total", "new_total"]
    frame = pd.DataFrame(rows, columns=columns)
    if frame.empty:
        frame = pd.DataFrame([{
            "sleeve": "A+US",
            "month": "",
            "old_trin_vote": "",
            "new_trin_vote": "",
            "old_total": "",
            "new_total": "",
            "note": "0个月",
        }])
    else:
        frame["note"] = ""
    frame.to_csv(OUT / "trin-vote-diff-monthly.csv", index=False)
    (OUT / "trin-rebuild.json").write_text(
        json.dumps(rebuilt, ensure_ascii=False, indent=1), encoding="utf-8")
    return frame


def _profile(log: dict) -> pd.DataFrame:
    rows = []
    days = [d for d in log if PROFILE_START <= d <= PROFILE_END]
    by_year = {}
    for day in days:
        by_year.setdefault(day.year, []).append(log[day] | {"day": day})
    for year, items in sorted(by_year.items()):
        last = items[-1]
        stock = [item["股票仓位"] for item in items if "股票仓位" in item]
        rows.append({
            "year": year,
            "stress": int(sum(item["紧张"] for item in items)),
            "dedupe": int(sum(bool(item.get("去重改了名单")) for item in items)),
            "eligible": int(last["可参选"]),
            "p": None if last.get("p") is None else round(float(last["p"]), 3),
            "stock": None if not stock else round(float(np.mean(stock)), 2),
            "asof": last["day"].date().isoformat(),
        })
    return pd.DataFrame(rows).set_index("year")


def _run_sleeve(levels, parent, prior, tags, votes_fn, bond, cash, modes):
    out = {}
    for mode, cost in modes:
        series, turnover, log = slot(
            levels, parent, 3, prior, tags, mode, cost, votes_fn, bond, cash)
        out[mode if cost == 0 else f"{mode}-net"] = (series, turnover, log)
    return out


def _annual(series: pd.Series) -> dict:
    return {name: round(cagr_pct(series, *bounds), 2) for name, bounds in SEGMENTS.items()}


def _examples(log, day, notional):
    rec = log[day]
    if rec["紧张"] and rec.get("p") is None:
        frac = None
    elif rec["紧张"]:
        frac = float(rec["p"])
    else:
        frac = 1.0
    each = None if frac is None else frac / 3.0
    def yuan(share):
        if share is None:
            return None
        return round(notional * share, 1)
    return {
        "signal_date": day.date().isoformat(),
        "votes": rec["票数"],
        "stress": rec["紧张"],
        "p": rec.get("p"),
        "parent_below_ma": rec.get("母指数跌破均线"),
        "eligible": rec["可参选"],
        "held": rec["持有"],
        "held_m12_pct": {k: round(rec["分数"][k] * 100, 1) for k in rec["持有"]},
        "top6_m12_pct": {
            k: round(v * 100, 1)
            for k, v in sorted(rec["分数"].items(), key=lambda kv: -kv[1])[:6]
        },
        "each_share_of_sleeve": None if each is None else round(each, 3),
        "stock_yuan": yuan(None if each is None else each * len(rec["持有"])),
        "each_yuan": yuan(each),
        "rest_yuan": yuan(None if each is None else 1 - each * len(rec["持有"])),
        "bond_above_ma": rec["国债在均线上方"],
    }


def run() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    panels = load_panels()
    eligible = write_eligible(panels)
    (OUT / "eligible-evidence.json").write_text(json.dumps({
        "freeze": FREEZE,
        "loader_sha256": panels["loader_sha256"],
        "cutoff": panels["cutoff"],
        "rule": "D45-2：12 月信号日 m12 有限的候选，含母指数。m12 = T−1 月末 / T−12 月末 − 1。面板是附表 B 的回填口径 A_BF。",
        "note_2015_11": "附表 B 逐年表的 2015 年末来自复算脚本把画像切到 2015-11，一并列出，供和 12 月名单区分。",
        "months": eligible,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    diff = vote_diff(panels)
    votes = panels["votes"]
    bond, cash = panels["bond"], panels["cash"]
    a_modes = (("ew", 0.0), ("top", 0.0), ("v6", 0.0), ("v6", 0.002))
    a = _run_sleeve(panels["A"], "csi300", None, TAGS["a"], votes, bond, cash, a_modes)
    a_pub = slot(panels["A_pub"], "csi300", 3, None, TAGS["a"], "v6", 0.002, votes, bond, cash)
    opaque = Path("/opt/cursor/artifacts/french-49/49_Industry_Portfolios.csv")
    csv_sha = _sha_file(opaque) if opaque.exists() else None
    prior = us_prior(PANEL) if csv_sha == FRENCH_SHA and PANEL.exists() else None
    french_note = {
        "opaque_csv": str(opaque),
        "sha256": csv_sha,
        "expected": FRENCH_SHA,
        "sha_matches_registered": csv_sha == FRENCH_SHA,
        "cell_comparison": "未做。历史原件字节没有第二份，不能逐格比较",
        "used_for_numbers": prior is not None,
        "acceptance": "不记验收通过" if prior is not None else "未计算",
        "prior_months": None if prior is None else len(prior),
    }
    u_modes = [("ew", 0.0), ("top", 0.0)]
    if prior is not None:
        u_modes.extend([("v6", 0.0), ("v6", 0.002)])
    u = _run_sleeve(panels["US"], "SPX", prior, TAGS["us"], votes, bond, cash, u_modes)
    # 上面 US 的 ew/top 不使用把握 p。不要把 prior=None 当成美股起点经验。
    bm_main = benchmark(panels["A"], panels["US"], (0.70, 0.15, 0.15))
    bm_same = benchmark(panels["A"], panels["US"], (0.40, 0.30, 0.30))
    books = {
        "BM-主（70/15/15）": bm_main,
        "BM-同仓位（40/30/30）": bm_same,
        "同结构等权、不设防守": mix_daily(a["ew"][0], u["ew"][0]),
        "前 3、不设防守": mix_daily(a["top"][0], u["top"][0]),
    }
    prior_names = set()
    if prior is not None:
        books["v6 毛（不计成本）"] = mix_daily(a["v6"][0], u["v6"][0])
        books["v6 净（单边 0.2%，每日固定 60/40）"] = mix_daily(a["v6-net"][0], u["v6-net"][0])
        books["v6 净（每月再平衡 60/40）"] = mix_monthly(a["v6-net"][0], u["v6-net"][0], 0.002)
        books["参照：一级行业按发布日截断"] = mix_daily(a_pub[0], u["v6-net"][0])
        prior_names.update(books.keys())
        prior_names.difference_update({
            "BM-主（70/15/15）", "BM-同仓位（40/30/30）", "同结构等权、不设防守", "前 3、不设防守",
        })
    annual = {name: _annual(series) for name, series in books.items()}
    # 发布日截断参照需要美股 v6 净。没有 French 时只报 A 股名额自己的净年化，不冒充组合数。
    a_net_ann = _annual(a["v6-net"][0])
    pub_ref = None
    rows = []
    for name, published in PUBLISHED_CAGR.items():
        if name in annual:
            got = annual[name]
            for seg in SEGMENTS:
                match = got[seg] == published[seg]
                rows.append({
                    "item": name, "segment": seg, "published": published[seg],
                    "got": got[seg], "diff": round(got[seg] - published[seg], 2),
                    "status": (PRIOR_NOTE if match else "差异；" + PRIOR_NOTE) if name in prior_names else ("ok" if match else "diff"),
                })
        else:
            rows.append({
                "item": name, "segment": "2006–15", "published": published["2006–15"],
                "got": None, "diff": None,
                "status": "未完成：美股起点经验没有两份原件可逐格比较",
            })
    for name, published in PUBLISHED_SPLIT.items():
        if name == "仓位差":
            got = {seg: round(annual["BM-同仓位（40/30/30）"][seg] - annual["BM-主（70/15/15）"][seg], 2) for seg in SEGMENTS}
        elif name == "等权倾斜":
            got = {seg: round(annual["同结构等权、不设防守"][seg] - annual["BM-同仓位（40/30/30）"][seg], 2) for seg in SEGMENTS}
        elif name == "挑选":
            got = {seg: round(annual["前 3、不设防守"][seg] - annual["同结构等权、不设防守"][seg], 2) for seg in SEGMENTS}
        else:
            if "v6 毛（不计成本）" not in annual:
                for seg, value in published.items():
                    rows.append({
                        "item": name, "segment": seg, "published": value,
                        "got": None, "diff": None,
                        "status": "未完成：美股起点经验没有两份原件可逐格比较",
                    })
                continue
            source = {
                "防守": ("v6 毛（不计成本）", "前 3、不设防守"),
                "成本": ("v6 净（单边 0.2%，每日固定 60/40）", "v6 毛（不计成本）"),
                "合计（v6 净 − BM-主）": ("v6 净（单边 0.2%，每日固定 60/40）", "BM-主（70/15/15）"),
            }[name]
            got = {seg: round(annual[source[0]][seg] - annual[source[1]][seg], 2) for seg in SEGMENTS}
            for seg in SEGMENTS:
                match = got[seg] == published[seg]
                rows.append({
                    "item": name, "segment": seg, "published": published[seg],
                    "got": got[seg], "diff": round(got[seg] - published[seg], 2),
                    "status": PRIOR_NOTE if match else "差异；" + PRIOR_NOTE,
                })
            continue
        for seg in SEGMENTS:
            rows.append({
                "item": name, "segment": seg, "published": published[seg],
                "got": got[seg], "diff": round(got[seg] - published[seg], 2),
                "status": "ok" if got[seg] == published[seg] else "diff",
            })
    a_profile = _profile(a["v6-net"][2])
    u_top_profile = _profile(u["top"][2])
    for year, published in PUBLISHED_YEAR.items():
        got = a_profile.loc[year]
        for key, label in (("stress", "a_stress"), ("dedupe", "a_dedupe"), ("eligible", "a_n"), ("p", "a_p"), ("stock", "a_w")):
            rows.append({
                "item": f"A {year} {key}", "segment": "2006-01至2015-11画像",
                "published": published[label], "got": got[key],
                "diff": None if got[key] is None else round(float(got[key]) - published[label], 3),
                "status": "ok" if got[key] == published[label] else "diff",
            })
        u_got = u_top_profile.loc[year]
        for key, label in (("stress", "u_stress"), ("dedupe", "u_dedupe")):
            published_value = published[label]
            rows.append({
                "item": f"US {year} {key}", "segment": "2006-01至2015-11画像",
                "published": published_value, "got": u_got[key],
                "diff": None if u_got[key] is None else round(float(u_got[key]) - published_value, 3),
                "status": "ok" if u_got[key] == published_value else "diff",
            })
        if "v6-net" not in u:
            for key, label in (("p", "u_p"), ("stock", "u_w")):
                rows.append({
                    "item": f"US {year} {key}", "segment": "2006-01至2015-11画像",
                    "published": published[label], "got": None, "diff": None,
                    "status": "未完成：美股起点经验没有两份原件可逐格比较",
                })
        else:
            u_v6 = _profile(u["v6-net"][2]).loc[year]
            for key, label in (("p", "u_p"), ("stock", "u_w")):
                match = u_v6[key] == published[label]
                rows.append({
                    "item": f"US {year} {key}", "segment": "2006-01至2015-11画像",
                    "published": published[label], "got": u_v6[key],
                    "diff": None if u_v6[key] is None else round(float(u_v6[key]) - published[label], 3),
                    "status": PRIOR_NOTE if match else "差异；" + PRIOR_NOTE,
                })
    recon = pd.DataFrame(rows)
    recon.to_csv(OUT / "appendix-b-reconcile.csv", index=False)
    examples = {}
    for year, month, sleeve, log, notional in (
        (2013, 4, "A", a["v6-net"][2], 400_000),
        (2015, 8, "A", a["v6-net"][2], 400_000),
        (2013, 4, "US", u.get("v6-net", u["top"])[2], 600_000),
        (2015, 8, "US", u.get("v6-net", u["top"])[2], 600_000),
        (2015, 8, "A-pub", a_pub[2], 400_000),
    ):
        day = signal_month(pd.DatetimeIndex(log.keys()), year, month)
        item = _examples(log, day, notional)
        if sleeve == "US":
            item["p_status"] = PRIOR_NOTE if prior is not None else "未完成：没有两份原件可逐格比较"
        if sleeve == "A-pub":
            item["panel"] = "发布日截断。冻结 exec-example 的 p=0.235 来自这一面板，不是回填面板。"
        examples[f"{sleeve}-{year}-{month:02d}"] = item
    (OUT / "examples.json").write_text(json.dumps(examples, ensure_ascii=False, indent=1), encoding="utf-8")
    if prior is None:
        pd.DataFrame([{
            "行情": "", "口径": "", "最低剩_中位": "", "最低剩_p10": "", "比基准年化_中位": "",
            "note": "未完成：美股起点经验没有两份原件可逐格比较",
        }]).to_csv(OUT / "synthetic-no-help.csv", index=False)
    else:
        synthetic = pd.concat([
            no_help(panels, prior, new_trin=False),
            no_help(panels, prior, new_trin=True),
        ], ignore_index=True)
        synthetic["acceptance"] = PRIOR_NOTE
        synthetic.to_csv(OUT / "synthetic-no-help.csv", index=False)
    dtb3_sha = _sha_file(DTB3_PATH) if DTB3_PATH.exists() else None
    manifest = {
        "freeze": FREEZE,
        "d45": "2fbcecfaeda83d4529b54789208986787acc77af",
        "d45_merge": "a1b2374354fcf5885cd297a6f736f1e7f13b0f5c",
        "pr376_merged": True,
        "french": french_note,
        "dtb3": {
            "path": "results/v5/other-market/raw/DTB3.csv",
            "sha256": dtb3_sha,
            "source": "仓库里已有的 FRED DTB3，本轮没有重新下载，也没有把 1998-12 之后的利率读进计算",
        },
        "loader_sha256": panels["loader_sha256"],
        "a_sleeve_net_cagr_pct": a_net_ann,
        "a_turnover_full_sample_over_10": round(a["v6-net"][1] / 10, 2),
        "us_turnover": None if prior is None else round(u["v6-net"][1] / 10, 2),
        "us_turnover_acceptance": None if prior is None else PRIOR_NOTE,
        "publish_date_truncation_a_net_cagr_pct": _annual(a_pub[0]),
        "trin_vote_changed_rows": 0 if set(diff["note"].astype(str)) == {"0个月"} else int((diff["note"].astype(str) == "").sum()),
        "blocked": sorted(prior_names),
        "db_lfs_oid": "0245876256527dda58145c770d75f342e7514b74a8c2cf1213fecfb713bf72f8",
    }
    (OUT / "run-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    _ledger(manifest, recon)
    return manifest


def _ledger(manifest, recon: pd.DataFrame) -> None:
    diffs = recon.loc[recon["status"] == "diff", ["item", "segment", "published", "got", "diff"]]
    paused = int((recon["status"].astype(str).str.startswith("暂停")).sum())
    result = {
        "matched": int((recon["status"] == "ok").sum()),
        "diffs": int((recon["status"] == "diff").sum()),
        "paused": paused,
        "diff_rows": diffs.to_dict("records"),
    }
    path = OUT / "trial-ledger.csv"
    row = {
        "run_at": datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds"),
        "code_sha256": _code_sha(),
        "freeze": FREEZE,
        "d45": manifest["d45"],
        "input_sha256": json.dumps({
            "market_sqlite_lfs": manifest["db_lfs_oid"],
            "a_official_text": manifest["loader_sha256"],
            "dtb3": manifest["dtb3"]["sha256"],
            "french": manifest["french"]["sha256"],
        }, ensure_ascii=False),
        "period": "2006-01-01至2015-12-31",
        "params": "N=3,us=0.60,stress>=2,cost=0.002,mom=T-1/T-12-1,ma=10,q=1/3,2/3,trin_old=full99_on_le_2015,trin_new=expanding99",
        "purpose": "设计期名单、示例、附表B对账、D45-10投票差；不跑一次性检验",
        "result": json.dumps(result, ensure_ascii=False),
    }
    frame = pd.DataFrame([row])
    if path.exists():
        frame = pd.concat([pd.read_csv(path), frame], ignore_index=True)
    frame.to_csv(path, index=False)


if __name__ == "__main__":
    run()

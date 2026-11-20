"""D37 第六轮：把已授权的指数窗口追加进行情库。

只追加新代码。已有行不改、不删。两条独立日线的收盘相对差中位数须 ≤ 0.01%。
五条部分完成的序列从「正式发布日」和「连续日线起点」里较晚的那天起，缺口不补。
不改冻结规则，不碰 LOCK。
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import shutil
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from src.data import db as DB
from src.data.hashlog import HashLedger
from src.data.store import upsert

from .diag_d37 import OUT

ROOT = Path(__file__).resolve().parents[2]
PKT = ROOT / "incoming" / "grok-d37-index-20261116"
TAIPEI = ZoneInfo("Asia/Taipei")
END = "2026-09-30"
MEDIAN_LIMIT = 0.0001  # 0.01%
LABEL = "d37-round6"
ROUTE = "d37_r6"

# 五条部分完成：入库起点 = max(正式发布日, 连续覆盖起点)。连续覆盖是已有日线的第一天，不是补出来的。
PARTIAL_START = {
    "theme-SPAHLVCP": {"publish": "2017-02-20", "continuous": "2017-08-04", "ingest": "2017-08-04"},
    "theme-S&P 500 Energy Sector Index(NTR)": {
        "publish": "1996-06-28", "continuous": "1998-12-31", "ingest": "1998-12-31",
    },
    "theme-标普500消费精选指数": {"publish": "2022-11-21", "continuous": "2022-11-25", "ingest": "2022-11-25"},
    "theme-标普美国品质消费股票指数": {"publish": "1998-12-16", "continuous": "1998-12-16", "ingest": "1998-12-16"},
    "theme-标普中国新经济行业指数": {"publish": "2018-12-24", "continuous": "2020-05-14", "ingest": "2020-05-14"},
}


def now_taipei() -> str:
    return datetime.now(TAIPEI).isoformat(timespec="seconds")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel_stats(left: dict[str, float], right: dict[str, float]) -> dict:
    """重叠日收盘相对差。中位数用排序后的中间一项，与第四轮同一取法。"""
    days = sorted(set(left) & set(right))
    gaps = [abs(left[day] / right[day] - 1.0) for day in days if right[day]]
    gaps.sort()
    if not gaps:
        return {"n": 0, "median": None, "max": None, "n_over": 0, "ok": False}
    median = gaps[len(gaps) // 2]
    return {
        "n": len(gaps),
        "median": median,
        "max": gaps[-1],
        "n_over": sum(gap > MEDIAN_LIMIT for gap in gaps),
        "ok": median <= MEDIAN_LIMIT,
    }


def _column(row: dict, *names: str) -> str:
    folded = {str(key).strip().lower(): key for key in row}
    for name in names:
        key = folded.get(name.lower())
        if key is not None:
            return str(row[key]).strip()
    return ""


def load_levels(path: Path) -> dict[str, float]:
    """读 date,close。恒生官方月表的列名是 Day Close，日期值仍是 YYYY-MM-DD。"""
    text = path.read_text(encoding="utf-8-sig")
    out: dict[str, float] = {}
    for row in csv.DictReader(io.StringIO(text)):
        raw_day = _column(row, "date", "Date", "Date (dd-mm-yyyy)")
        raw_close = _column(row, "close", "Day Close")
        if not raw_day or not raw_close:
            continue
        day = raw_day[:10].replace("/", "-")
        if len(day) == 10 and day[2] == "-" and day[5] == "-":
            # dd-mm-yyyy
            day = f"{day[6:10]}-{day[3:5]}-{day[0:2]}"
        close = float(str(raw_close).replace(",", ""))
        if close <= 0:
            continue
        previous = out.get(day)
        if previous is not None and abs(previous / close - 1.0) > 1e-12:
            raise RuntimeError(f"{path.name} {day} 有两个不同收盘 {previous} / {close}")
        out[day] = close
    if not out:
        raise RuntimeError(f"{path} 没有日线")
    return out


def fill_missing(base: dict[str, float], extra: dict[str, float], start: str, end: str) -> tuple[dict[str, float], int]:
    """只补 base 里没有的日期。已有日期不改。"""
    out = dict(base)
    added = 0
    for day, close in extra.items():
        if day < start or day > end or day in out:
            continue
        out[day] = close
        added += 1
    return out, added


def append_after(base: dict[str, float], extra: dict[str, float]) -> tuple[dict[str, float], int]:
    """只接在当前最后一天之后。重叠日不覆盖。"""
    if not base:
        raise RuntimeError("没有基底，不能往后接")
    last = max(base)
    out = dict(base)
    added = 0
    for day, close in extra.items():
        if day <= last or day in out:
            continue
        out[day] = close
        added += 1
    return out, added


def clip_levels(levels: dict[str, float], start: str, first_list: str, end: str = END,
                drop: set[str] | None = None) -> list[dict]:
    """发布日/连续起点的较晚者 → 首只场内基金上市日之前。上市日当天不接。"""
    skipped = drop or set()
    rows = []
    for day in sorted(levels):
        if day < start or day >= first_list or day > end or day in skipped:
            continue
        rows.append({"date": day, "close": levels[day]})
    return rows


def weekday_holes(rows: list[dict], start: str, stop: str) -> list[str]:
    have = {row["date"] for row in rows}
    found = []
    day = date.fromisoformat(start)
    last = date.fromisoformat(stop)
    while day <= last:
        if day.weekday() < 5 and day.isoformat() not in have:
            found.append(day.isoformat())
        day += timedelta(days=1)
    return found


def _path(rel: str) -> Path:
    return PKT / rel


def _sha_ok(rel: str, expect: str) -> None:
    got = file_sha256(_path(rel))
    if got != expect:
        raise RuntimeError(f"{rel} SHA256 {got} ≠ {expect}")


def roster_first_list() -> dict[str, str]:
    frame_path = OUT / "s1-splice-roster.csv"
    with frame_path.open(encoding="utf-8", newline="") as handle:
        return {
            row["container_id"]: str(row["first_list"])[:10]
            for row in csv.DictReader(handle)
        }


def _check_pair(left: dict[str, float], right: dict[str, float], min_n: int) -> dict:
    stats = rel_stats(left, right)
    stats["min_n"] = min_n
    stats["ok"] = bool(stats["n"] >= min_n and stats["median"] is not None and stats["median"] <= MEDIAN_LIMIT)
    return stats


def build_series(spec: dict) -> dict:
    """在内存里拼日线并核对。不写库。"""
    for rel, digest in spec.get("sha", {}).items():
        _sha_ok(rel, digest)
    levels = load_levels(_path(spec["base"]))
    notes = [f"基底 {spec['base']} {len(levels)} 行 {min(levels)}→{max(levels)}"]
    for item in spec.get("fill", []):
        extra = load_levels(_path(item["file"]))
        levels, added = fill_missing(levels, extra, item["start"], item["end"])
        notes.append(f"补缺 {item['file']} {item['start']}→{item['end']} 新增 {added} 行，不覆盖已有日")
    for rel in spec.get("append", []):
        extra = load_levels(_path(rel))
        levels, added = append_after(levels, extra)
        notes.append(f"后续 {rel} 接在最后一天之后，新增 {added} 行")
    checks = []
    for item in spec["checks"]:
        left = levels if item["left"] == "primary" else load_levels(_path(item["left"]))
        right = load_levels(_path(item["right"]))
        stats = _check_pair(left, right, int(item.get("min_n", 20)))
        stats["left"] = item["left"]
        stats["right"] = item["right"]
        checks.append(stats)
    partial = PARTIAL_START.get(spec["container_id"])
    publish = spec["publish_date"]
    ingest_start = spec["ingest_start"]
    if partial is not None:
        if partial["publish"] != publish or partial["ingest"] != ingest_start:
            raise RuntimeError(f"{spec['container_id']} 的起点和 PARTIAL_START 不一致")
        if ingest_start != max(partial["publish"], partial["continuous"]):
            raise RuntimeError(f"{spec['container_id']} 入库起点不是发布日和连续覆盖的较晚者")
    listed = roster_first_list()[spec["container_id"]]
    if listed != spec["first_list"]:
        raise RuntimeError(f"{spec['container_id']} 名册上市日 {listed} ≠ {spec['first_list']}")
    dropped = set(spec.get("drop", []))
    rows = clip_levels(levels, ingest_start, listed, drop=dropped)
    problems = []
    if any(not item["ok"] for item in checks):
        problems.append("两条日线的中位数没有过 0.01%")
    if len(rows) < 5:
        problems.append(f"上市日前只剩 {len(rows)} 根")
    if rows and rows[0]["date"] < ingest_start:
        problems.append("写进了起点之前的日子")
    for day in spec.get("absent", []):
        if day in levels and day >= ingest_start and day < listed and day <= END:
            problems.append(f"{day} 仍在将入库的区间里")
    for day, close in spec.get("require_close", {}).items():
        got = levels.get(day)
        if got is None or abs(got - close) > 0.005:
            problems.append(f"{day} 收盘是 {got}，要保留 {close}")
    forbid = spec.get("forbid_close", {})
    for day, close in forbid.items():
        got = levels.get(day)
        if got is not None and abs(got - close) <= 0.005:
            problems.append(f"{day} 收盘 {got} 是明确不用的那个点")
    holes = weekday_holes(rows, rows[0]["date"], rows[-1]["date"]) if rows else []
    return {
        "container_id": spec["container_id"],
        "bars_code": spec["bars_code"],
        "index_code": spec["index_code"],
        "currency": spec["currency"],
        "publish_date": publish,
        "continuous_start": (partial or {}).get("continuous", spec.get("continuous", publish)),
        "ingest_start": ingest_start,
        "first_list": listed,
        "group": spec["group"],
        "rows": rows,
        "row_count": len(rows),
        "first": rows[0]["date"] if rows else "",
        "last": rows[-1]["date"] if rows else "",
        "holes": holes,
        "hole_count": len(holes),
        "checks": checks,
        "notes": notes,
        "source_url": spec["source_url"],
        "reason_bits": spec["reason_bits"],
        "problems": problems,
        "ok": not problems,
    }


def _pct(value: float | None) -> str:
    if value is None:
        return "无重叠"
    return f"{value:.4%}"


def _reason(built: dict) -> str:
    checks = "；".join(
        f"{item['right'].split('/')[-1]} 重叠 {item['n']} 天，中位数 {_pct(item['median'])}，最大 {_pct(item['max'])}"
        for item in built["checks"]
    )
    hole = f"区间内未补的工作日 {built['hole_count']} 天。"
    started = built["ingest_start"]
    if built["first"] and built["first"] != started:
        started = f"{started}，实际第一根 {built['first']}，中间缺口不补"
    text = (
        f"第六轮。正式发布日 {built['publish_date']}。连续覆盖 {built['continuous_start']}。"
        f"入库起点 {started}（发布日与连续覆盖的较晚者）。"
        f"{built['row_count']} 行 {built['first']}→{built['last']}，止于上市日 {built['first_list']} 之前，且不晚于 {END}。"
        f"{checks}。{hole}{' '.join(built['reason_bits'])} 核对时间 {now_taipei()}。"
    )
    return " ".join(text.split())


def series_specs() -> list[dict]:
    """要入库的序列。文件名写死，避免换到价格收益、近称或发布前的回补。"""
    p2 = "d37-remain-20261118-pass2"
    p3 = "d37-remain-20261118-pass3"
    p5 = "d37-remain-20261119-pass5"
    long = "d37-longhist-20261118"
    remain = "d37-remain-20261118"
    specs = []

    def hang(container: str, code: str, publish: str, first_list: str, bits: list[str]) -> dict:
        leaf = container.removeprefix("theme-")
        base = f"theme-{leaf}-eastmoney.csv"
        second = f"theme-{leaf}-official-past-month.csv"
        return {
            "container_id": container, "bars_code": code, "index_code": code, "currency": "HKD",
            "publish_date": publish, "ingest_start": publish, "continuous": publish,
            "first_list": first_list, "group": "complete", "base": base,
            "checks": [{"left": "primary", "right": second, "min_n": 20}],
            "source_url": f"https://quote.eastmoney.com/unify/r/124.{code}",
            "reason_bits": bits + ["第二条是恒生 INdex360 过去一月官方收盘，东财长日线与这 20 日核对。2026-11-17 未确认的当日不进入 2026-09-30 之前的窗口。"],
            "sha": {},
        }

    hang_rows = [
        ("theme-HSFML25", "HSFML25", "2017-07-19", "2025-10-13",
         ["INdex360 发布日 2017-07-19，目录另有 2003-01-20，两处都是官方、冲突未决。交付文件已裁到 2017-07-19，更早的日子没有、也不补。入库用较晚的这个官方日期。"]),
        ("theme-HSISC", "HSISC", "2024-03-08", "2025-06-09", ["INdex360 与指数目录发布日都是 2024-03-08。"]),
        ("theme-HSSC50", "HSSC50", "2025-01-13", "2025-11-25", ["INdex360 与指数目录发布日都是 2025-01-13。"]),
        ("theme-HSSCAMHI", "HSSCAM", "2024-05-31", "2026-05-15", ["基金材料写 HSSCAMHI。指数目录代码是 HSSCAM。发布日 2024-05-31。"]),
        ("theme-HSSCHKY", "HSSCHKY", "2019-11-18", "2021-05-20", ["INdex360 与指数目录发布日都是 2019-11-18。"]),
        ("theme-HSSCITI", "HSSCITI", "2023-07-17", "2025-08-19", ["发布日 2023-07-17。东财从 2023-12-01 起，中间缺口不补。"]),
        ("theme-HSSCPB", "HSSCPB", "2023-07-17", "2025-07-07", ["发布日 2023-07-17。东财从 2023-12-01 起，中间缺口不补。"]),
        ("theme-HSSCSOY", "HSSCSOY", "2023-06-12", "2024-01-05", ["发布日 2023-06-12。东财从 2023-12-01 起，中间缺口不补。"]),
        ("theme-HSSCT", "HSSCT", "2020-02-17", "2022-02-09", ["发布日 2020-02-17。东财从 2020-03-30 起，中间缺口不补。"]),
        ("theme-恒生中国央企指数", "HSCSOE", "2023-04-17", "2024-04-19", ["INdex360 与指数目录发布日都是 2023-04-17。东财从 2023-12-01 起，中间缺口不补。"]),
        ("theme-恒生创新药指数", "HSIDI", "2023-05-15", "2024-12-27", ["INdex360 与指数目录发布日都是 2023-05-15。东财从 2023-12-01 起，中间缺口不补。"]),
        ("theme-恒生生物科技指数", "HSBIO", "2019-12-16", "2021-10-19", ["INdex360 与指数目录发布日都是 2019-12-16。用 HSBIO，不用杠杆或反向。"]),
    ]
    specs.extend(hang(*row) for row in hang_rows)

    specs.append({
        "container_id": "chinext", "bars_code": "399006.SZSE", "index_code": "399006", "currency": "CNY",
        "publish_date": "2010-06-01", "ingest_start": "2010-06-01", "continuous": "2010-06-01",
        "first_list": "2011-12-09", "group": "complete", "base": "chinext.csv",
        "checks": [{"left": "primary", "right": "chinext-eastmoney.csv", "min_n": 30}],
        "source_url": "https://www.szse.cn/",
        "reason_bits": ["深交所/国证官方日线，东财核对。库内 399006 仍是腾讯，不覆盖；拼接用新代码 399006.SZSE。基日 2010-05-31 的 1000 不在这个文件里。"],
        "sha": {"chinext.csv": "195eeece26573879e344bbd534fc4b8e5c97432d90b719472fc984d9b49c5296"},
    })
    specs.append({
        "container_id": "theme-标普全球石油指数", "bars_code": "SPGOGUP", "index_code": "SPGOGUP", "currency": "USD",
        "publish_date": "2011-07-08", "ingest_start": "2011-07-08", "continuous": "2011-07-08",
        "first_list": "2012-05-02", "group": "complete",
        "base": f"{remain}/theme-SPGOGUP-usspindices-wayback-usd-pr-daily-20110708-20141215.csv",
        "checks": [{
            "left": f"{remain}/theme-SPGOGUP-usspindices-wayback-usd-pr-daily-20110708-20150123.csv",
            "right": f"{long}/theme-SPGOGUP-ft-usd-pr-daily-20141216-20261116.csv",
            "min_n": 20,
        }],
        "source_url": "https://web.archive.org/web/20150126100537id_/http://us.spindices.com/indices/equity/sp-global-oil-index",
        "reason_bits": ["官方 Wayback indexLevels，USD 价格收益 SPGOGUP。2005-01-24 起的未裁切文件不用。入库只用 2011-07-08 起、上市日之前。FT 只作 2014-12 重叠核对，不另写一条。"],
        "sha": {
            f"{remain}/theme-SPGOGUP-usspindices-wayback-usd-pr-daily-20110708-20141215.csv":
            "43534668fced8de43b7cec9eb250ce5e025eebbd9da2c9ea882e84bf3f0bc990",
        },
    })
    specs.append({
        "container_id": "theme-标普500信息科技指数", "bars_code": "S5INFT", "index_code": "S5INFT", "currency": "USD",
        "publish_date": "1996-06-28", "ingest_start": "1996-06-28", "continuous": "1996-06-28",
        "first_list": "2016-12-27", "group": "complete",
        "base": f"{p2}/theme-S5INFT-ft-SP500-45-usd-pr-daily-19960628-20120924.csv",
        "fill": [{
            "file": f"{p3}/theme-S5INFT-cnbc-SPLRCT-usd-pr-daily-20010102-20011204.csv",
            "start": "2001-01-02", "end": "2001-12-04",
        }],
        "append": ["theme-标普500信息科技指数-tradingview.csv"],
        "checks": [{"left": "primary", "right": "theme-标普500信息科技指数-official-usd-pr-daily-20251117-20261117.csv", "min_n": 30}],
        "source_url": "https://www.spglobal.com/spdji/en/indices/equity/sp-500-information-technology-sector/",
        "reason_bits": [
            "USD 价格收益 S5INFT，Reuters .SPLRCT，不是 IXT。FT SP500-45:IOM 到 2012-09-24；"
            "2001-01-02 至 2001-12-04 只补 FT 没有的日子，CNBC .SPLRCT（xid 603229）公开日线，SHA256 9463cf2e4c271bb95222ed5634853a6885a439275f78299fdb84892fd3eba75f，不是官方。"
            "2012-09-25 之后接 TradingView。官方约一年只作核对。假日和 2001-09-11 至 09-14 不补。",
        ],
        "sha": {
            f"{p2}/theme-S5INFT-ft-SP500-45-usd-pr-daily-19960628-20120924.csv":
            "c95ed3b892ea0c50db70f6ba35e8e5ac7ec1937c60a9f6a463b1c1b144b0f6fa",
            f"{p3}/theme-S5INFT-cnbc-SPLRCT-usd-pr-daily-20010102-20011204.csv":
            "9463cf2e4c271bb95222ed5634853a6885a439275f78299fdb84892fd3eba75f",
        },
    })
    specs.append({
        "container_id": "theme-标普生物科技精选行业指数", "bars_code": "SPSIBI", "index_code": "SPSIBI", "currency": "USD",
        "publish_date": "2006-01-27", "ingest_start": "2006-01-27", "continuous": "2006-01-27",
        "first_list": "2016-12-27", "group": "complete",
        "base": f"{p2}/theme-SPSIBI-usspindices-wayback-usd-pr-daily-20060127-20140505.csv",
        "append": ["theme-标普生物科技精选行业指数-tradingview.csv"],
        "checks": [
            {"left": f"{p2}/theme-SPSIBI-usspindices-wayback-usd-pr-daily-20060127-20141219.csv",
             "right": "theme-标普生物科技精选行业指数-tradingview.csv", "min_n": 30},
            {"left": "primary", "right": "theme-标普生物科技精选行业指数-official-usd-pr-daily-20251117-20261117.csv", "min_n": 30},
        ],
        "source_url": "https://web.archive.org/web/20141221042442id_/http://us.spindices.com/indices/equity/sp-biotechnology-select-industry-index",
        "reason_bits": ["USD 价格收益 SPSIBI。官方 Wayback 到 2014-05-05，之后接 TradingView。2004-12-20 起的未裁切文件不用。未用 SPSIBITR。"],
        "sha": {
            f"{p2}/theme-SPSIBI-usspindices-wayback-usd-pr-daily-20060127-20140505.csv":
            "356b3fb9a3c977b0ad2d4298324d5259b745c864df9dbf74ed458a12adc7a324",
        },
    })
    specs.append({
        "container_id": "theme-道琼斯美国石油开发与生产指数", "bars_code": "DJSOEP", "index_code": "DJSOEP", "currency": "USD",
        "publish_date": "2006-04-28", "ingest_start": "2006-04-28", "continuous": "2006-04-28",
        "first_list": "2017-03-17", "group": "complete",
        "base": f"{p2}/theme-DJSOEP-ft-usd-pr-daily-20060428-20060504.csv",
        "append": ["theme-道琼斯美国石油开发与生产指数-tradingview.csv"],
        "checks": [{"left": "primary", "right": "theme-道琼斯美国石油开发与生产指数-official-usd-pr-daily-20251117-20261117.csv", "min_n": 30}],
        "source_url": "https://www.spglobal.com/spdji/en/indices/equity/dow-jones-us-select-oil-exploration-production-index/",
        "reason_bits": ["USD 价格收益 DJSOEP。发布日后五天用 FT，2006-05-05 起用 TradingView。官方约一年核对。"],
        "sha": {
            f"{p2}/theme-DJSOEP-ft-usd-pr-daily-20060428-20060504.csv":
            "d4236d5699019de1eca1c73b403f123eefe1ddce2e54c8869b2ed0e320813b3f",
        },
    })
    specs.append({
        "container_id": "theme-标普石油天然气勘探及生产精选行业指数", "bars_code": "SPSIOP", "index_code": "SPSIOP", "currency": "USD",
        "publish_date": "2006-06-19", "ingest_start": "2006-06-19", "continuous": "2006-06-19",
        "first_list": "2012-06-08", "group": "complete",
        "base": f"{p2}/theme-SPSIOP-ft-usd-pr-daily-20060619-20060622.csv",
        "append": ["theme-标普石油天然气勘探及生产精选行业指数-tradingview.csv"],
        "checks": [{"left": "primary", "right": "theme-标普石油天然气勘探及生产精选行业指数-official-usd-pr-daily-20251117-20261117.csv", "min_n": 30}],
        "source_url": "https://www.spglobal.com/spdji/en/indices/equity/sp-oil-gas-exploration-production-select-industry-index/",
        "reason_bits": ["USD 价格收益 SPSIOP。发布日后四天用 FT，之后用 TradingView。2026-03-09 TradingView 与官方差约 3%，该日晚于上市日，不在入库窗口。"],
        "sha": {
            f"{p2}/theme-SPSIOP-ft-usd-pr-daily-20060619-20060622.csv":
            "f6e2fc0ef13500a7b627f8047ef78715eba6ca0ca1a32d0d982ec48d1781fc88",
        },
    })
    specs.append({
        "container_id": "theme-标普500医疗保健等权重指数", "bars_code": "S35", "index_code": "S35", "currency": "USD",
        "publish_date": "2006-06-20", "ingest_start": "2006-11-02", "continuous": "2006-11-02",
        "first_list": "2016-12-14", "group": "complete",
        "base": "theme-标普500医疗保健等权重指数-tradingview.csv",
        "checks": [{"left": "primary", "right": "theme-标普500医疗保健等权重指数-official-usd-pr-daily-20251117-20261116.csv", "min_n": 30}],
        "source_url": "https://www.spglobal.com/spdji/en/indices/equity/sp-500-equal-weight-health-care-select-index/",
        "reason_bits": ["官方代码 S35，不是 SP5HEW。发布日 2006-06-20。连续日线从 2006-11-02 起，前面的缺口不补。"],
        "sha": {},
    })
    specs.append({
        "container_id": "theme-道琼斯美国精选REIT指数", "bars_code": "DWRTF", "index_code": "DWRTF", "currency": "USD",
        "publish_date": "1998-12-31", "ingest_start": "1998-12-31", "continuous": "1998-12-31",
        "first_list": "2017-11-24", "group": "complete",
        "base": "theme-道琼斯美国精选REIT指数-tradingview.csv",
        "checks": [{"left": "primary", "right": "theme-道琼斯美国精选REIT指数-official-usd-pr-daily-20251117-20261116.csv", "min_n": 30}],
        "source_url": "https://www.spglobal.com/spdji/en/indices/equity/dow-jones-us-select-reit-index/",
        "reason_bits": ["官方 USD 价格收益代码 DWRTF。不用 DJUSRE。发布日 1998-12-31，与日线起点一致。"],
        "sha": {},
    })

    # 五条部分完成。
    specs.append({
        "container_id": "theme-SPAHLVCP", "bars_code": "SPAHLVCP", "index_code": "SPAHLVCP", "currency": "CNY",
        "publish_date": "2017-02-20", "ingest_start": "2017-08-04", "first_list": "2023-12-08", "group": "partial",
        "base": f"{long}/theme-SPAHLVCP-ft-cny-pr-daily-20170804-20261117.csv",
        "checks": [
            {"left": "primary", "right": "theme-SPAHLVCP-official-cny-pr-daily-20251117-20261117.csv", "min_n": 30},
            {"left": "primary", "right": f"{long}/theme-SPAHLVCP-xueqiu-cny-pr-daily-20180711-20261117.csv", "min_n": 30},
        ],
        "drop": ["2025-11-28"],
        "absent": ["2017-02-20", "2017-08-03"],
        "source_url": "https://markets.ft.com/data/indices/tearsheet/historical?s=SPAHLVCP%3AIOM",
        "reason_bits": [
            "CNY 价格收益 SPAHLVCP，不是港币 SPAHLVHP。2017-02-20 至 2017-08-03 没有日线，不补。"
            "2025-11-28 的 FT 收盘不是官方（官方 1347.7，FT/雪球 1350.08），该日不入库。雪球从 2018-07-11 起作第二条。",
        ],
        "sha": {
            f"{long}/theme-SPAHLVCP-ft-cny-pr-daily-20170804-20261117.csv":
            "6b1222dfe98fd5bfdb75930da999fbe683124cc72c8f22b497ad40516e19d915",
        },
    })
    specs.append({
        "container_id": "theme-S&P 500 Energy Sector Index(NTR)", "bars_code": "SP5NENRS", "index_code": "SP5NENRS",
        "currency": "USD", "publish_date": "1996-06-28", "ingest_start": "1998-12-31",
        "first_list": "2015-02-17", "group": "partial",
        "base": f"{long}/theme-SP5NENRS-ft-NTRGSPE-usd-ntr-daily-19981231-20261116.csv",
        "checks": [{"left": "primary", "right": "theme-S&P 500 Energy Sector Index(NTR)-official-usd-ntr-daily-20251117-20261116.csv", "min_n": 30}],
        "absent": ["1996-06-28", "1998-12-30"],
        "source_url": "https://markets.ft.com/data/indices/tearsheet/historical?s=NTRGSPE%3AREU",
        "reason_bits": ["S&P 500 Energy 净总回报 SP5NENRS，Reuters .NTRGSPE。保持 NTR，不用价格收益。1996-06-28 至 1998-12-30 没有日线，不补。1998-12-31 的 100.00 是 FT 连续段的第一根，不是补出来的基期。"],
        "sha": {
            f"{long}/theme-SP5NENRS-ft-NTRGSPE-usd-ntr-daily-19981231-20261116.csv":
            "784c430ae6b89dfbedeb245b5ccd88595f1ceb74208a3715c50eb49a1006545b",
        },
    })
    specs.append({
        "container_id": "theme-标普500消费精选指数", "bars_code": "SP5CSSUP", "index_code": "SP5CSSUP", "currency": "USD",
        "publish_date": "2022-11-21", "ingest_start": "2022-11-25", "first_list": "2024-02-02", "group": "partial",
        "base": f"{long}/theme-SP5CSSUP-ft-usd-pr-daily-20221125-20261116.csv",
        "checks": [
            {"left": "primary", "right": "theme-标普500消费精选指数-official-usd-pr-daily-20251117-20261116.csv", "min_n": 30},
            {"left": "primary", "right": "theme-标普500消费精选指数-tradingview.csv", "min_n": 30},
        ],
        "absent": ["2022-11-21", "2022-11-22", "2022-11-23"],
        "source_url": "https://markets.ft.com/data/indices/tearsheet/historical?s=SP5CSSUP%3AIOM",
        "reason_bits": ["USD 价格收益 SP5CSSUP，不是 SP500-25。CNBC/FT 第一根都是 2022-11-25。2022-11-21/22/23 不补，也不把基期 1000 写成收盘。"],
        "sha": {
            f"{long}/theme-SP5CSSUP-ft-usd-pr-daily-20221125-20261116.csv":
            "e3761c88aee8b7f70c57784bd75f764d7fc26fd90e9787c3a5588046e5f56f0b",
        },
    })
    specs.append({
        "container_id": "theme-标普美国品质消费股票指数", "bars_code": "IXY", "index_code": "IXY", "currency": "USD",
        "publish_date": "1998-12-16", "ingest_start": "1998-12-16", "first_list": "2016-04-06", "group": "partial",
        "base": f"{long}/theme-IXY-ft-usd-pr-daily-19981216-20261116.csv",
        "checks": [
            {"left": "primary", "right": "theme-标普美国品质消费股票指数-official-usd-pr-daily-20251117-20261116.csv", "min_n": 30},
            {"left": "primary", "right": f"{p5}/theme-IXY-cnbc-usd-pr-daily-19981216-20060427.csv", "min_n": 30},
        ],
        "require_close": {"2000-01-21": 288.89},
        "forbid_close": {"2000-01-21": 293.63},
        "drop": ["2001-09-11"],
        "source_url": "https://markets.ft.com/data/indices/tearsheet/historical?s=IXY%3APSE",
        "reason_bits": [
            "Consumer Discretionary Select Sector Index，USD 价格收益，Reuters .IXY。不是 S5COND，不是 Quality，不是 XLY。"
            "First Value 2003-07-01 不是发布日。入库用 FT 连续日线。CNBC 1998-12-16 至 2006-04-27 是允许的公开第二条，"
            "SHA256 e9901ba4aff29420eb766f2764d3ad6a5fb3d8df8e8695f99dd8accd3274468e，不是官方。"
            "2000-01-21 保留 FT 288.89，不改成 CNBC 293.63（相对差 1.641%）。"
            "FT 在 2001-09-11 重复了 2001-09-10 的收盘，纽交所当天停市，CNBC 没有这根，已剔除。"
            "2001-09-12 至 09-14 和 2004-06-11 本来就没有，不补。进行中的 TradingView 文件不用。",
        ],
        "sha": {
            f"{long}/theme-IXY-ft-usd-pr-daily-19981216-20261116.csv":
            "4d6e20c943c03b52f703ffd68db9e30ac0f6156b875d5f393bbcc5b45660c890",
            f"{p5}/theme-IXY-cnbc-usd-pr-daily-19981216-20060427.csv":
            "e9901ba4aff29420eb766f2764d3ad6a5fb3d8df8e8695f99dd8accd3274468e",
        },
    })
    specs.append({
        "container_id": "theme-标普中国新经济行业指数", "bars_code": "SPNCSCUP", "index_code": "SPNCSCUP", "currency": "USD",
        "publish_date": "2018-12-24", "ingest_start": "2020-05-14", "first_list": "2020-10-23", "group": "partial",
        "base": f"{long}/theme-SPNCSCUP-ft-usd-pr-daily-20200514-20261116.csv",
        "checks": [
            {"left": "primary", "right": "theme-标普中国新经济行业指数-tradingview.csv", "min_n": 30},
            {"left": "primary", "right": "theme-标普中国新经济行业指数-official-usd-pr-SPNCSCUP-daily-20251117-20261116.csv", "min_n": 30},
        ],
        "drop": ["2026-09-28"],
        "absent": ["2018-12-24", "2020-05-13"],
        "source_url": "https://markets.ft.com/data/indices/tearsheet/historical?s=SPNCSCUP%3AIOM",
        "reason_bits": [
            "USD 价格收益 SPNCSCUP（A 股上限）。不用港币、无上限、Ex-A-Share 或 NTR。"
            "2018-12-24 至 2020-05-13 没有第二套独立日线，也没有 CSV，这段不入库、不编。"
            "连续覆盖取 FT 2020-05-14（CNBC 从 2020-05-15 起，但没有交付 CSV，不用原始 JSON 另造日线）。"
            "TradingView 从发布日起的单源段不入库，只在 2020-05-14 之后作第二条。2026-09-28 的 FT 不是官方，不入库。",
        ],
        "sha": {
            f"{long}/theme-SPNCSCUP-ft-usd-pr-daily-20200514-20261116.csv":
            "0ada0dd1f2b68ff19dca853984e05ffe1237e8ea472515e9eb6f770e63778d52",
        },
    })
    return specs


HELD = [
    ("soymeal", "只有大商所一条官方日线。soymeal-official-full.csv 是同一条未裁切序列，不是第二条独立日线。不入库。"),
    ("theme-巴西IBOVESPA指数", "数据包只有巴西央行美元兑雷亚尔，没有指数点位文件。不另去下载指数，也不单独写入汇率。"),
    ("theme-东证指数", "只有 JPX 统计月报这一条日线，publish_date 仍是未核对。没有第二条独立日线。不入库。"),
    ("theme-MSCI China Value Weighted Index", "官方日线和 4 年文件是同一来源的两种导出，不是两条独立日线。不入库。"),
    ("theme-MSCI USA 50 Index", "只有一条官方日线。不入库。"),
    ("theme-法兰克福DAX指数", "入库候选只有价格收益 DAXK 一条。东财是绩效 DAX，不是 DAXK 的第二来源。publish_date 未核对。不入库。"),
    ("theme-iEdge Emerging Asia Select 50 Index", "只有 TradingView 价格收益。官方复述三点的相对差约 0.13% 至 0.54%，过不了 0.01%。不用净总回报顶替。不入库。"),
    ("theme-新交所泛东南亚科技指数", "只有 TradingView 价格收益 ASIATECP。没有第二条日线。不用 ASIATECN 净总回报。不入库。"),
    ("theme-富时亚太低碳精选指数", "只有 TradingView 价格收益。官方月末文件是净税兄系，不是价格日线。不入库。"),
    ("theme-富时沙特阿拉伯指数", "沙特里亚尔和美元两条不是同一点位（重叠最大相对差约 0.43%）。价格指数发布日未核对。不入库。"),
    ("theme-恒生中国企业指数", "东财与官方过去一月 20 日一致，但发布日未决：INdex360 为 2017-07-19，目录为 1994-08-08。前者晚于首只基金上市日，后者会放进一段很长的打分窗口。两个都是官方日期，不选边，不入库。"),
]


def evaluate() -> list[dict]:
    built = []
    for spec in series_specs():
        print(f"check {spec['container_id']}", flush=True)
        item = build_series(spec)
        built.append(item)
        flag = "OK" if item["ok"] else "NO"
        medians = ",".join(_pct(check["median"]) for check in item["checks"])
        print(f"  {flag} {item['row_count']} {item['first']}→{item['last']} median {medians} {item['problems']}", flush=True)
    return built


def _public(item: dict) -> dict:
    return {
        "container_id": item["container_id"],
        "group": item["group"],
        "bars_code": item["bars_code"],
        "index_code": item["index_code"],
        "currency": item["currency"],
        "publish_date": item["publish_date"],
        "continuous_start": item["continuous_start"],
        "ingest_start": item["ingest_start"],
        "first_list": item["first_list"],
        "row_count": item["row_count"],
        "first": item["first"],
        "last": item["last"],
        "hole_count": item["hole_count"],
        "holes_head": item["holes"][:12],
        "checks": [
            {key: row[key] for key in ("left", "right", "n", "median", "max", "n_over", "ok", "min_n")}
            for row in item["checks"]
        ],
        "notes": item["notes"],
        "problems": item["problems"],
        "ok": item["ok"],
    }


def _patch_table(path: Path, updates: dict[str, dict]) -> None:
    """只改点名的容器。表里没有的容器不新增，其余行原样保留。"""
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    keys = ("status", "index_code", "publish_date", "bars_code", "currency", "reason", "tried_urls", "source_url")
    by_id = {row["container_id"]: row for row in rows}
    missing = [name for name in updates if name not in by_id]
    if missing:
        raise RuntimeError(f"{path.name} 没有这些容器：{missing}")
    for name, patch in updates.items():
        for key in keys:
            if key in patch and patch[key] is not None:
                by_id[name][key] = patch[key]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def apply() -> dict:
    built = evaluate()
    accepted = [item for item in built if item["ok"]]
    refused = [item for item in built if not item["ok"]]
    if refused:
        names = ", ".join(item["container_id"] for item in refused)
        raise RuntimeError(f"有序列没有通过核对，整批不写库：{names}")
    codes = [item["bars_code"] for item in accepted]
    if len(codes) != len(set(codes)):
        raise RuntimeError(f"代码重复：{codes}")
    con = sqlite3.connect(str(DB.MARKET_DB))
    try:
        existing = dict(con.execute("SELECT code, COUNT(*) FROM bars GROUP BY code"))
        clash = [code for code in codes if code in existing]
        if clash:
            raise RuntimeError(f"这些代码已经有行，不覆盖：{clash}")
        if existing.get("399006"):
            tencent = con.execute(
                "SELECT COUNT(*), MIN(source) FROM bars WHERE code = '399006'"
            ).fetchone()
            if tencent[1] != "tencent_index":
                raise RuntimeError(f"399006 的来源不是腾讯：{tencent}")
        before_total = sum(existing.values())
        ledger = HashLedger(DB.MARKET_DB)
        before = ledger.before(LABEL)
        fetched_at = now_taipei()
        for item in accepted:
            upsert(con, item["bars_code"], ROUTE, item["rows"], fetched_at)
        con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        after_counts = dict(con.execute("SELECT code, COUNT(*) FROM bars GROUP BY code"))
        for code, count in existing.items():
            if after_counts.get(code) != count:
                raise RuntimeError(f"{code} 原有 {count} 行，现在 {after_counts.get(code)} 行")
        new_rows = sum(after_counts[code] for code in codes)
        if sum(after_counts.values()) - before_total != new_rows:
            raise RuntimeError("新增行数对不上")
        for item in accepted:
            early = con.execute(
                "SELECT MIN(date) FROM bars WHERE code = ? AND adj = 'raw'", (item["bars_code"],)
            ).fetchone()[0]
            if early < item["ingest_start"]:
                raise RuntimeError(f"{item['bars_code']} 写进了 {item['ingest_start']} 之前的 {early}")
    finally:
        con.close()
    after = ledger.after(LABEL)
    updates = {}
    for item in accepted:
        updates[item["container_id"]] = {
            "status": "spliced",
            "index_code": item["index_code"],
            "publish_date": item["publish_date"],
            "bars_code": item["bars_code"],
            "currency": item["currency"],
            "source_url": item["source_url"],
            "tried_urls": " | ".join(item["notes"]),
            "reason": _reason(item),
        }
    for container_id, reason in HELD:
        updates[container_id] = {
            "status": "frozen",
            "reason": f"第六轮不入库。{reason} 核对时间 {now_taipei()}。",
        }
    # 名册和登记表在 D38 之后不是同一份。分别打补丁，不能用登记表覆盖名册。
    _patch_table(OUT / "s1-splice-roster.csv", updates)
    _patch_table(OUT / "s1-index-registry.csv", updates)
    text = "".join(line + "\n" for line in ledger.lines)
    with (OUT / "db-sha256.txt").open("a", encoding="utf-8") as handle:
        handle.write(text)
    if after != before:
        log = ROOT / "results" / "inventory" / "db-writes.txt"
        with log.open("a", encoding="utf-8") as handle:
            handle.write(text)
    archive = OUT / "round6"
    archive.mkdir(parents=True, exist_ok=True)
    payload = {
        "label": LABEL,
        "packet": "332b88fdb1b1b4272edb154754c3bf2925b5889d",
        "before": before,
        "after": after,
        "accepted": [_public(item) for item in accepted],
        "held": [{"container_id": name, "reason": reason} for name, reason in HELD],
        "partial_start": PARTIAL_START,
    }
    (archive / "ingest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"before={before} after={after} series={len(accepted)}", flush=True)
    return payload


def _compare_s0(folder: Path, reference: Path) -> dict:
    from .diag_d37 import compare_exits, compare_frames

    got = __import__("pandas").read_csv(folder / "daily.csv", parse_dates=["date"], index_col="date")
    old = __import__("pandas").read_csv(reference / "daily.csv", parse_dates=["date"], index_col="date")
    problems = compare_frames(
        got, old,
        ["net", "gross", "nav", "cost", "buy", "sell", "market", "market_name", "risk", "defense", "picks", "blocked"],
    )
    got_held = __import__("pandas").read_csv(folder / "held.csv", parse_dates=["date"], index_col="date")
    old_held = __import__("pandas").read_csv(reference / "held.csv", parse_dates=["date"], index_col="date")
    shared = [name for name in old_held.columns if name in got_held.columns]
    problems.extend("held " + item for item in compare_frames(got_held, old_held, shared))
    if list(got_held.columns) != list(old_held.columns):
        problems.append("held 列不一致")
    problems.extend(compare_exits(
        __import__("pandas").read_csv(folder / "exits.csv"),
        __import__("pandas").read_csv(reference / "exits.csv"),
    ))
    return {"days": int(len(got)), "problems": problems, "same": not problems}


def rerun() -> dict:
    """S0 V0 检验段对照第五轮留下的文件。S1 设计期 V0–V4、检验段 V0–V4 和方案 B 写到 round6。"""
    import src.v51.d37_plan_b as plan_b
    import src.v51.diag_d37 as diag

    canonical = ROOT / "results" / "v51-diag" / "d37"
    archive = canonical / "round6"
    archive.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(canonical / "s1-index-registry.csv", archive / "s1-index-registry.csv")
    reference = canonical / "S0" / "检验段" / "V0"
    diag.OUT = archive
    plan_b.OUT = archive
    try:
        print("S0 V0 检验段，对照第五轮文件", flush=True)
        diag.run_cn("检验段", ["V0"], ["S0"], bitmatch=False)
        report = _compare_s0(archive / "S0" / "检验段" / "V0", reference)
        text = (
            "新库 S0 V0 检验段对照第五轮 results/v51-diag/d37/S0/检验段/V0。\n"
            f"天数 {report['days']}\n"
            f"一致 {report['same']}\n"
            + ("\n".join(report["problems"]) + "\n" if report["problems"] else "逐位一致。\n")
        )
        (archive / "s0-v0-check.txt").write_text(text, encoding="utf-8")
        print(text, flush=True)
        if not report["same"]:
            raise RuntimeError("S0 V0 检验段和第五轮不一致")
        versions = ["V0", "V1", "V2", "V3", "V4"]
        diag.run_cn("设计期", versions, ["S1"], bitmatch=False)
        diag.run_cn("检验段", versions, ["S1"], bitmatch=False)
        plan_b.run_s1_inspection(diag._db_ready())
    finally:
        diag.OUT = canonical
        plan_b.OUT = canonical
    rows = []
    for segment in ("设计期", "检验段"):
        for version in ("V0", "V1", "V2", "V3", "V4", "B"):
            new_path = archive / "S1" / segment / version / "stats.json"
            old_path = canonical / "S1" / segment / version / "stats.json"
            if not new_path.is_file():
                continue
            new = json.loads(new_path.read_text(encoding="utf-8"))["performance"]
            old = json.loads(old_path.read_text(encoding="utf-8"))["performance"] if old_path.is_file() else {}
            rows.append({
                "segment": segment,
                "version": version,
                "ann": new["ann"],
                "max_drawdown": new["max_drawdown"],
                "trades_per_year": new["trades_per_year"],
                "cost_per_year": new["cost_per_year"],
                "prev_ann": old.get("ann"),
                "prev_max_drawdown": old.get("max_drawdown"),
            })
    import pandas as pd
    pd.DataFrame(rows).to_csv(archive / "s1-vs-previous.csv", index=False, float_format="%.12g")
    print(f"S1 round6 写完 {len(rows)} 格", flush=True)
    return {"s0_same": True, "cells": rows}


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="D37 第六轮入库")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--rerun", action="store_true")
    args = parser.parse_args()
    if args.check:
        evaluate()
        return 0
    if args.apply:
        apply()
        return 0
    if args.rerun:
        rerun()
        return 0
    parser.error("指定 --check、--apply 或 --rerun")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

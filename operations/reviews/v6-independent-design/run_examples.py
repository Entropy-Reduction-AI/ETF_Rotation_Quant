"""设计期两个月份的选人复算。只读 ≤2015-12-31。不计算分位、把握、合成行情。"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from v6ind import CUTOFF, FREEZE_COMMIT, SPEC_RELATIVE, SPEC_SHA256
from v6ind.candidates import DESIGN_CANDIDATES, EXCLUDED, FX_CODE, OUTSIDE_DESIGN, PARENT, SLEEVE_CAPITAL_WAN
from v6ind.load import connect_readonly, load_closes, provenance
from v6ind.momentum import Score, dedupe_top, month_ends, score_ready, ten_month_ma, twelve_one

OUT = Path(__file__).resolve().parent / "output"
EXAMPLES = ("2013-04", "2015-08")
FROZEN_ELIGIBLE = {
    "2006": 12, "2007": 12, "2008": 14, "2009": 15, "2010": 17,
    "2011": 18, "2012": 18, "2013": 19, "2014": 25, "2015": 27,
}
FROZEN_EXAMPLES = {
    "2015-08": {
        "a": {"names": ["军工", "全指软件", "全指公用事业"], "pct": [106, 100, 95]},
    },
    "2013-04": {
        "a": {"names": ["沪深300医药卫生", "创业板指", "全指公用事业"], "wan_each": 13.3},
        "us": {"names": ["NBI", "XLF", "XLP"], "wan_each": 20.0},
    },
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def dumps(payload: dict) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def cny_ends(usd: dict[str, tuple[str, float]], fx: dict[str, tuple[str, float]]) -> dict[str, tuple[str, float]]:
    """同一自然月的月末美元点位 × 该月最后一个中间价。"""
    out = {}
    for month, (date, level) in usd.items():
        rate = fx.get(month)
        if rate is None:
            continue
        out[month] = (date, level * rate[1])
    return out


def sleeve_levels(sleeve: str, raw: dict[str, dict[str, tuple[str, float]]], fx: dict[str, tuple[str, float]]):
    if sleeve == "a":
        return raw
    return {code: cny_ends(ends, fx) for code, ends in raw.items()}


def build_scores(cands, levels, signal_month: str, signal_date: str) -> tuple[list[Score], list[dict]]:
    scored: list[Score] = []
    skipped: list[dict] = []
    for cand in cands:
        ready = score_ready(cand.eligible_from)
        if ready > signal_date:
            skipped.append({"code": cand.code, "name": cand.name, "reason": "未满12个月", "score_ready": ready})
            continue
        point = twelve_one(levels[cand.code], signal_month)
        if point is None:
            skipped.append({"code": cand.code, "name": cand.name, "reason": "锚点缺失", "score_ready": ready})
            continue
        value, end_date, end_level, start_date, start_level = point
        scored.append(Score(cand.name, cand.code, cand.tag, value, end_date, end_level, start_date, start_level))
    return scored, skipped


def public_score(row: Score) -> dict:
    return {
        "name": row.name,
        "code": row.code,
        "tag": row.tag,
        "score": row.score,
        "pct": row.score * 100.0,
        "end_date": row.end_date,
        "end_level": row.end_level,
        "start_date": row.start_date,
        "start_level": row.start_level,
    }


def exact_tie_on_cut(scores: list[Score], positive_only: bool) -> list[dict]:
    pool = [row for row in scores if row.score > 0.0] if positive_only else list(scores)
    ordered = sorted(pool, key=lambda item: (-item.score, item.code))
    chosen, _slots, _dropped = dedupe_top(scores, positive_only=positive_only)
    if len(chosen) < 3 or len(ordered) < 2:
        return []
    cut = chosen[-1].score
    tied = [row for row in ordered if row.score == cut]
    if len(tied) <= 1:
        return []
    return [public_score(row) for row in tied]


def eligible_names(cands, levels, signal_month: str, signal_date: str) -> list[str]:
    names = []
    for cand in cands:
        if score_ready(cand.eligible_from) > signal_date:
            continue
        if twelve_one(levels[cand.code], signal_month) is None:
            continue
        names.append(cand.name)
    return names


def main() -> None:
    spec = ROOT / SPEC_RELATIVE
    spec_sha = sha256_file(spec)
    if spec_sha != SPEC_SHA256:
        raise SystemExit(f"规范字节哈希不符：{spec_sha}")
    db_path = ROOT / "data" / "market.sqlite"
    db_sha = sha256_file(db_path)
    con = connect_readonly(db_path)
    try:
        con.execute("BEGIN")
        codes = sorted({cand.code for cand in DESIGN_CANDIDATES} | {FX_CODE})
        raw_rows = {code: load_closes(con, code) for code in codes}
        info = [provenance(con, code) for code in codes]
        con.rollback()
    finally:
        con.close()

    ends = {code: month_ends(rows) for code, rows in raw_rows.items()}
    fx = ends[FX_CODE]
    by_sleeve = {
        "a": [cand for cand in DESIGN_CANDIDATES if cand.sleeve == "a"],
        "us": [cand for cand in DESIGN_CANDIDATES if cand.sleeve == "us"],
    }
    levels = {
        "a": {cand.code: ends[cand.code] for cand in by_sleeve["a"]},
        "us_usd": {cand.code: ends[cand.code] for cand in by_sleeve["us"]},
        "us": sleeve_levels("us", {cand.code: ends[cand.code] for cand in by_sleeve["us"]}, fx),
    }

    examples = []
    for signal_month in EXAMPLES:
        for sleeve in ("a", "us"):
            parent = levels[sleeve][PARENT[sleeve]]
            signal = parent.get(signal_month)
            if signal is None:
                raise SystemExit(f"{sleeve} {signal_month} 没有母指数月末")
            signal_date, _level = signal
            ma = ten_month_ma(parent, signal_month)
            if ma is None:
                below = None
                ma_payload = None
            else:
                ma_date, close, average = ma
                below = close < average
                ma_payload = {
                    "date": ma_date,
                    "level": close,
                    "ma10": average,
                    "gap": close - average,
                    "below": below,
                    "definition": "含信号月的 10 个月末点位算术平均；跌破为严格小于",
                }
            use_levels = levels[sleeve]
            scored, skipped = build_scores(by_sleeve[sleeve], use_levels, signal_month, signal_date)
            positive_only = bool(below)
            chosen, bond_slots, dropped = dedupe_top(scored, positive_only=positive_only)
            leaders, _leader_slots, _leader_dropped = dedupe_top(scored, positive_only=False)
            usd_order = None
            if sleeve == "us":
                usd_scored, _usd_skipped = build_scores(by_sleeve["us"], levels["us_usd"], signal_month, signal_date)
                usd_chosen, _b, _d = dedupe_top(usd_scored, positive_only=positive_only)
                usd_order = [row.code for row in usd_chosen]
            capital = SLEEVE_CAPITAL_WAN[sleeve]
            full = below is False and bond_slots == 0 and len(chosen) == 3
            per_name = capital / 3.0 if full else None
            examples.append({
                "signal_month": signal_month,
                "sleeve": sleeve,
                "signal_date": signal_date,
                "parent": PARENT[sleeve],
                "level_unit": "指数点位" if sleeve == "a" else "美元点位×当月最后一个人民币中间价",
                "ma": ma_payload,
                "positive_only": positive_only,
                "ranked": [public_score(row) for row in sorted(scored, key=lambda item: (-item.score, item.code))],
                "leaders": [public_score(row) for row in leaders],
                "selected": [public_score(row) for row in chosen],
                "bond_slots": bond_slots,
                "wan_each_if_full": per_name,
                "dropped_same_tag": [public_score(row) for row in dropped],
                "tie_at_cut": exact_tie_on_cut(scored, positive_only),
                "usd_selected_codes": usd_order,
                "cny_selected_codes": [row.code for row in chosen] if sleeve == "us" else None,
                "ranking_fx_invariant": (usd_order == [row.code for row in chosen]) if sleeve == "us" else None,
                "scored_count": len(scored),
                "skipped": skipped,
                "status": "设计期选人。不是一次性检验。未算紧张票、把握和金额，除非满仓空位为 0 且均线未跌破。",
            })

    census = []
    for year in range(2006, 2016):
        signal_month = f"{year}-12"
        row = {"year": year}
        for sleeve in ("a", "us"):
            parent = levels[sleeve][PARENT[sleeve]]
            signal = parent.get(signal_month)
            if signal is None:
                row[sleeve] = None
                continue
            names = eligible_names(by_sleeve[sleeve], levels[sleeve], signal_month, signal[0])
            row[sleeve] = {"signal_date": signal[0], "count": len(names), "names": names}
            if sleeve == "us":
                usd_names = eligible_names(by_sleeve["us"], levels["us_usd"], signal_month, signal[0])
                row["us_usd_price_score_count"] = {
                    "count": len(usd_names),
                    "note": "美元点位能否算出 12-1，只说明覆盖；人民币口径见 us.count",
                }
        frozen = FROZEN_ELIGIBLE[str(year)]
        actual = None if row["a"] is None else row["a"]["count"]
        row["frozen_a_count"] = frozen
        row["a_count_minus_frozen"] = None if actual is None else actual - frozen
        census.append(row)

    fx_first = min(date for date, _level in raw_rows[FX_CODE])
    kept_last = [item["last"] for block in info for item in block["kept"] if item["last"]]
    payload = {
        "label": "设计期",
        "not_oneshot": True,
        "cutoff": CUTOFF,
        "freeze_commit": FREEZE_COMMIT,
        "spec_sha256": spec_sha,
        "rule": {
            "twelve_one": "信号月 T：上月末 T-1 点位 / T-13 月末点位 - 1",
            "score_ready": "参选起点加 12 个日历月，信号日当天及之后才有分数",
            "dedupe": "非空行业标签只留 12-1 最高的一个；无标签不去重；同分以代码升序，并单列并列",
            "ma": "含信号月的 10 个月末点位；严格小于才算跌破，才启用 12-1 为正的过滤",
            "not_computed": ["宽度分位", "TRIN 分位", "把握 p", "国债与现金收益", "合成行情", "成本与净值"],
        },
        "examples": examples,
        "census": census,
        "fx": {
            "code": FX_CODE,
            "first_on_or_before_cutoff": fx_first,
            "rows_on_or_before_cutoff": len(raw_rows[FX_CODE]),
            "no_print_on_or_before_2005_12_31": fx_first > "2005-12-31",
        },
        "outside_design_not_loaded": [
            {"name": cand.name, "code": cand.code, "eligible_from": cand.eligible_from}
            for cand in OUTSIDE_DESIGN
        ],
        "excluded_not_loaded": {"name": EXCLUDED.name, "code": EXCLUDED.code, "reason": "规范写明不参选"},
        "truncation": {
            "predicate": "date <= 2015-12-31 写在取值 SQL 的 WHERE 里",
            "codes": len(info),
            "excluded_rows_not_read": sum(item["excluded_rows"] for item in info),
            "max_kept_date": max(kept_last),
            "codes_without_rows": [item["code"] for item in info if not item["kept"]],
            "null_close_dates": {item["code"]: item["null_close_dates"] for item in info if item["null_close_dates"]},
        },
        "provenance": info,
    }
    raw = dumps(payload)
    OUT.mkdir(parents=True, exist_ok=True)
    result_path = OUT / "design-selection.json"
    result_path.write_bytes(raw)
    manifest = {
        "result": result_path.name,
        "result_sha256": hashlib.sha256(raw).hexdigest(),
        "result_bytes": len(raw),
        "spec_sha256": spec_sha,
        "market_sqlite_sha256": db_sha,
        "freeze_commit": FREEZE_COMMIT,
        "python": sys.version.split()[0],
        "sqlite": sqlite3.sqlite_version,
    }
    (OUT / "manifest.json").write_bytes(dumps(manifest))
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

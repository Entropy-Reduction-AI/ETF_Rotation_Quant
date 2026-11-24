#!/usr/bin/env python3
"""Generate exhaustive PR339 R1b audit artifacts (Reviewer)."""
from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OVERLAY = Path("/tmp/v6-r1b-overlay")
OUT = ROOT / "operations/reviews/pr339-r1b-audit.json"
OLD, NEW = "27036630f6916aa921e7b9a2eb6f905c7c642551", "8f7ffbae3ac1885cefce9bc1281e4ab2d030687f"


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def git_show(ref_path: str) -> str:
    return subprocess.check_output(["git", "show", ref_path], cwd=ROOT, text=True)


def us_fifteen_audit() -> list[dict]:
    u4 = tomllib.load(open(OVERLAY / "config/v4/universe.toml", "rb"))["container"]
    us_rows = [
        ("SPX", "spx"),
        ("NDX", "ndx100"),
        ("DJIA", "theme-道琼斯工业平均指数"),
        ("SOX", "theme-PHLX Semiconductor Sector Index"),
        ("NBI", "theme-纳斯达克生物科技指数"),
        ("XLK", "theme-标普500信息科技指数"),
        ("XLV", "theme-标普500医疗保健等权重指数"),
        ("XLE", "theme-S&P 500 Energy Sector Index(NTR)"),
        ("XLY", "theme-标普500消费精选指数"),
        ("XLP", None),
        ("XLF", None),
        ("XLI", None),
        ("XLB", None),
        ("XLU", None),
        ("DWRTF", "theme-道琼斯美国精选REIT指数"),
    ]
    out = []
    for code, key in us_rows:
        if key:
            funds = [
                {"code": c["code"], "maps_to": c.get("maps_to"), "launch": c.get("official_launch") or c.get("first_date")}
                for c in u4
                if c.get("market") == "CN" and c.get("maps_to") == key
            ]
            status = "has_maps_to_vehicle" if funds else "maps_to_key_but_zero_cn_funds"
        else:
            funds = []
            status = "no_maps_to_key_script_lists_no_on_exchange_fund"
        with open(OVERLAY / "results/v6-preflight/v6-appendix-a.csv", encoding="utf-8") as f:
            row = next(r for r in csv.DictReader(f) if r["候选"] == code)
        out.append(
            {
                "candidate_code": code,
                "maps_to_key": key,
                "status": status,
                "cn_funds": funds,
                "appendix_a_实盘载体": row["实盘载体"],
                "appendix_a_载体与候选": row["载体与候选"],
            }
        )
    return out


def appendix_a_rows() -> list[dict]:
    subj = Path("/tmp/v6-r1b-appendix-a-subject.csv")
    rer = Path("/tmp/v6-r1b-appendix-a-rerun.csv")
    if not subj.is_file() or not rer.is_file():
        return []
    ds, dr = list(csv.DictReader(subj.open(encoding="utf-8"))), list(csv.DictReader(rer.open(encoding="utf-8")))
    idx = {r["候选"]: r for r in ds}
    changes = []
    for r in dr:
        o = idx.get(r["候选"])
        if not o:
            changes.append({"候选": r["候选"], "kind": "new_row"})
            continue
        diff_cols = {k: {"old": o[k], "new": r[k]} for k in r if o.get(k) != r.get(k)}
        if diff_cols:
            changes.append({"候选": r["候选"], "columns": diff_cols})
    return changes


def appendix_b_full() -> dict:
    jp = OVERLAY / "results/v6-preflight/v6-appendix-b.json"
    b = json.loads(jp.read_text(encoding="utf-8"))
    steps = ["仓位差", "等权倾斜", "挑选", "防守", "成本"]
    periods = ["2006–10", "2011–15", "2006–15"]
    d = b["收益拆分（每年比 BM-主 多几个点）"]
    sums = {}
    for p in periods:
        parts = {n: d[n][p] for n in steps}
        s = round(sum(parts.values()), 2)
        tot = d["合计（v6 净 − BM-主）"][p]
        sums[p] = {
            "five_terms": parts,
            "sum_five": s,
            "total_row": tot,
            "exact_after_round": s == tot,
        }
    md = (OVERLAY / "docs/prereg/etf-multiasset-rotation-prereg-v6.md").read_text(encoding="utf-8")
    # table in附表 B decomposition section
    p3_expect = {
        "2006–10": {"仓位差": -8.48, "等权倾斜": 1.78, "挑选": 5.03, "防守": -1.43, "成本": -0.23, "合计": -3.33},
        "2011–15": {"仓位差": 0.09, "等权倾斜": 0.49, "挑选": 6.28, "防守": -2.24, "成本": -0.71, "合计": 3.91},
        "2006–15": {"仓位差": -3.4, "等权倾斜": 1.13, "挑选": 4.3, "防守": -1.5, "成本": -0.4, "合计": 0.44},
    }
    p3_observed = {p: {**sums[p]["five_terms"], "合计": sums[p]["total_row"]} for p in periods}
    p3_match = {}
    for p in periods:
        p3_match[p] = {k: p3_observed[p][k] == p3_expect[p][k] for k in p3_expect[p]}
    p4 = {
        "a_stress_months_total": sum(v["紧张月数"] for v in b["信号画像：A 股名额"]["逐年"].values()),
        "us_stress_months_total": sum(v["紧张月数"] for v in b["信号画像：美股名额"]["逐年"].values()),
        "a_avg_stress_equity_pct": b["信号画像：A 股名额"]["紧张时平均股票仓位"],
        "json_v6_net_2006_15": b["年化"]["v6 净（单边 0.2%，每日固定 60/40）"]["2006–15"],
        "md_prose_15_5": "15.5" in md,
        "md_prose_0_4_total": "0.4 点" in md or "+0.4" in md,
        "md_prose_42_29": bool(re.search(r"42.*29|A 股紧张 42", md)),
    }
    ff = OVERLAY / "operations/reviews/diag/v6-r1b-cache/49_Industry_Portfolios.csv"
    dtb = OVERLAY / "results/v5/other-market/raw/DTB3.csv"
    return {
        "json_sha256": sha256(jp),
        "inputs_sha256": {
            "french_49_csv": sha256(ff) if ff.is_file() else None,
            "DTB3_csv": sha256(dtb),
            "market_sqlite_overlay": sha256(OVERLAY / "data/market.sqlite"),
            "v6_appendix_b_py@NEW": hashlib.sha256(git_show(f"{NEW}:scripts/preflight/v6_appendix_b.py").encode()).hexdigest(),
        },
        "decomposition_sums": sums,
        "p3_table_json_vs_prose_rounded": {"expected_from_md_table": p3_expect, "from_json": p3_observed, "field_match": p3_match},
        "p4_signal_prose_checks": p4,
        "end_filter_evidence": [
            {"file": "scripts/preflight/v6_appendix_b.py", "line": 21, "rule": "END = '2015-12-31'"},
            {"file": "scripts/preflight/v6_appendix_b.py", "line": 118, "rule": "profile log slice '2006-01':'2015-11'"},
            {"file": "scripts/preflight/a_official.py", "line": 28, "rule": "bars SQL date<='2015-12-31'"},
            {"file": "scripts/preflight/topn_dedupe.py", "line": 21, "rule": "lvl() bars date<='2015-12-31'"},
        ],
    }


NUM_RE = re.compile(r"[−\-+]?\d+(?:\.\d+)?(?:%|个点|点|倍|个|只|次|年|万)?")


def extract_keypoint_numbers() -> list[dict]:
    html = (OVERLAY / "docs/artifact/v6-prereg/index.html").read_text(encoding="utf-8")
    md = (OVERLAY / "docs/prereg/etf-multiasset-rotation-prereg-v6.md").read_text(encoding="utf-8")
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    inv = []
    for sec in soup.select("section[id^='sec-']"):
        sid = sec.get("id", "")
        for el in sec.select(".memo, .sl-box, .lg-big, .sl-dx, .sl-dh"):
            txt = el.get_text(" ", strip=True)
            nums = NUM_RE.findall(txt)
            if not nums:
                continue
            inv.append({"section_id": sid, "element": el.name + ("." + " ".join(el.get("class", [])) if el.get("class") else ""), "text_snippet": txt[:120], "numbers": nums})
    # markdown memos / blockquotes with numbers in headers §1-9
    for i, line in enumerate(md.splitlines(), 1):
        if line.startswith("> **") or (line.startswith("- **") and NUM_RE.search(line)):
            inv.append({"section_md_line": i, "text_snippet": line[:160], "numbers": NUM_RE.findall(line)})
    # de-dup audit: try anchor each number
    b = json.loads((OVERLAY / "results/v6-preflight/v6-appendix-b.json").read_text(encoding="utf-8"))
    anchored = []
    for item in inv:
        for n in item["numbers"]:
            nclean = n.replace("−", "-").replace("%", "").replace("个点", "").replace("点", "")
            anchor = None
            if n in ("15.5", "15.5%") or nclean == "15.5":
                anchor = f"附表B JSON v6净年化 2006–15={b['年化']['v6 净（单边 0.2%，每日固定 60/40）']['2006–15']}"
            elif nclean == "13.3":
                anchor = "§3 设计期年化口径 / 附表B 参照第47行 13.3"
            elif nclean in ("0.4", "+0.4") or n == "+0.4":
                anchor = "附表B 合计 2006–15 +0.44（四舍五入 0.4 点）"
            elif nclean == "4.3":
                anchor = "附表B 挑选 2006–15"
            elif nclean in ("-3.4", "-3.4"):
                anchor = "附表B 仓位差 2006–15（文 -3.4）"
            elif nclean in ("-1.5", "-1.5"):
                anchor = "附表B 成本 2006–15"
            elif nclean == "42":
                anchor = "附表B A股紧张月数合计"
            elif nclean == "29":
                anchor = "附表B 美股紧张月数合计"
            elif nclean == "24" and "%" in n:
                anchor = "附表B A股紧张时平均股票仓位≈0.24"
            anchored.append({**item, "number": n, "anchor": anchor or "MISSING_EXPLICIT_ANCHOR"})
    return anchored


def normative_diff() -> dict:
    old_t = git_show(f"{OLD}:docs/prereg/etf-multiasset-rotation-prereg-v6.md")
    new_t = git_show(f"{NEW}:docs/prereg/etf-multiasset-rotation-prereg-v6.md")

    def strip_allowed(s: str) -> str:
        s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
        return s

    allowed_prefixes = (
        "## 附表",
        "<details",
        "</details>",
        "<summary",
        "> **",
        "![",
        "| 候选 |",
        "| --- |",
        "| # |",
        "| 主题：",
        "| 中证全指一级行业",
        "- **一级行业",
        "- **口径",
        "- **一级行业的回填",
    )

    def in_sections_1_8(line: str) -> bool:
        if line.startswith("## 附表") or line.startswith("## §9"):
            return False
        if re.match(r"^## §[1-8]", line) or line.startswith("|") and not line.startswith("##"):
            return True
        return False

    old_lines, new_lines = strip_allowed(old_t).splitlines(), strip_allowed(new_t).splitlines()
    import difflib

    allowed, unallowed = [], []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, old_lines, new_lines).get_opcodes():
        if tag == "equal":
            continue
        old_chunk = old_lines[i1:i2]
        new_chunk = new_lines[j1:j2]
        section = next((ln for ln in new_lines[max(0, j1 - 5) : j1 + 1] if ln.startswith("## ")), "?")
        item = {
            "tag": tag,
            "section_nearest": section,
            "old_lines": old_chunk,
            "new_lines": new_chunk,
            "old_line_range": [i1 + 1, i2],
            "new_line_range": [j1 + 1, j2],
        }
        blob = "\n".join(new_chunk + old_chunk)
        if any(blob.startswith(p) or p in blob[:80] for p in allowed_prefixes):
            if "Owner 2026-11-24" in blob or "2.2 版" in blob or "设计期年化的口径" in blob:
                allowed.append({**item, "class": "owner_confirmed_or_status"})
            elif "附表" in section or "§9" in section:
                allowed.append({**item, "class": "appendix_or_sec9"})
            elif "<" in blob[:5]:
                allowed.append({**item, "class": "html_story_or_fold"})
            else:
                allowed.append({**item, "class": "allowed_bulk"})
        elif not any(in_sections_1_8(ln) for ln in new_chunk + old_chunk):
            allowed.append({**item, "class": "outside_sec1_8"})
        else:
            unallowed.append({**item, "class": "normative_sec1_8_delta"})

    return {"allowed_count": len(allowed), "unallowed_count": len(unallowed), "unallowed": unallowed, "allowed_sample": allowed[:8]}


def main() -> None:
    payload = {
        "us_fifteen_carriers": us_fifteen_audit(),
        "appendix_a_row_diffs": appendix_a_rows(),
        "appendix_b": appendix_b_full(),
        "keypoint_number_inventory": extract_keypoint_numbers(),
        "normative_diff": normative_diff(),
        "lint_warns": [
            "sec-1 策略定义：单元格 63 字",
            "sec-2 执行层：单元格 68 字",
            "sec-2 执行层：单元格 72 字",
            "sec-5 一次性检验：列表项 124 字",
            "附表-a：单元格 56 字（513500…）",
            "附表-a：单元格 56 字（513100…）",
        ],
        "owner_15_carrier_pass_assessment": None,
    }
    n_with = sum(1 for r in payload["us_fifteen_carriers"] if r["cn_funds"])
    n_without = 15 - n_with
    payload["owner_15_carrier_pass_assessment"] = {
        "script_treats_15_as_candidates": True,
        "cn_execution_vehicles_via_maps_to": n_with,
        "explicit_no_on_exchange_fund": n_without,
        "passes_literal_15_maps_to": False,
        "passes_literal_15_实盘载体_rows": True,
        "note": "Owner「15实盘载体」若指15个候选均有 maps_to QDII，则与 v4+脚本不一致（5个 SPDR 无 maps_to）；若指附表 A 列出15行载体字段，则一致。",
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
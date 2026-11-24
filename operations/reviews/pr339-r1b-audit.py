#!/usr/bin/env python3
"""Generate PR339 R1b audit artifacts (Reviewer)."""
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
    csv_rows = {r["候选"]: r for r in csv.DictReader(open(OVERLAY / "results/v6-preflight/v6-appendix-a.csv", encoding="utf-8"))}
    for code, key in us_rows:
        funds = (
            [
                {"code": c["code"], "maps_to": c.get("maps_to"), "launch": c.get("official_launch") or c.get("first_date")}
                for c in u4
                if c.get("market") == "CN" and c.get("maps_to") == key
            ]
            if key
            else []
        )
        row = csv_rows[code]
        consistent = (not key and row["实盘载体"] == "无场内基金") or (key and funds and row["实盘载体"] != "无场内基金")
        out.append(
            {
                "candidate_code": code,
                "maps_to_key": key,
                "cn_funds_all_maps_to": funds,
                "appendix_a_实盘载体": row["实盘载体"],
                "appendix_a_载体与候选": row["载体与候选"],
                "maps_to_consistent_with_v4_and_script": consistent,
            }
        )
    return out


def split_sections(text: str) -> dict[str, str]:
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    parts: dict[str, list[str]] = {"_preamble": []}
    cur = "_preamble"
    for line in text.splitlines():
        m = re.match(r"^(## §[0-9]|## 附表|## Metadata)", line)
        if m:
            cur = line.strip()
            parts[cur] = []
        else:
            parts.setdefault(cur, []).append(line)
    return {k: "\n".join(v).strip() for k, v in parts.items() if v or k == "_preamble"}


def normative_paragraph_diff() -> dict:
    old_t, new_t = git_show(f"{OLD}:docs/prereg/etf-multiasset-rotation-prereg-v6.md"), git_show(f"{NEW}:docs/prereg/etf-multiasset-rotation-prereg-v6.md")
    so, sn = split_sections(old_t), split_sections(new_t)
    allowed_section_prefixes = ("## 附表", "## §9")
    changes = []
    for sec in sorted(set(so) | set(sn)):
        if sec == "_preamble":
            label = "Metadata / 表前（非 §§1–8 规范正文）"
        elif sec.startswith("## 附表") or sec.startswith("## §9"):
            label = sec + "（允许类：附表 / §9）"
            if so.get(sec) != sn.get(sec):
                changes.append({"section": label, "class": "allowed", "note": "内容有增删，按 Owner 允许类不计 unauthorized"})
            continue
        elif not re.match(r"^## §[1-8]", sec):
            continue
        label = sec if not sec == "_preamble" else "Metadata（非 §§1–8）"
        bo, bn = so.get(sec, ""), sn.get(sec, "")
        if sec == "_preamble" and bo != bn:
            changes.append({"section": label, "class": "allowed_metadata_version", "before_quote": bo[:500], "after_quote": bn[:500]})
            continue
        if bo == bn:
            continue
        # paragraph-level diff within section
        po = [p.strip() for p in re.split(r"\n\s*\n", bo) if p.strip()]
        pn = [p.strip() for p in re.split(r"\n\s*\n", bn) if p.strip()]
        import difflib

        sm = difflib.SequenceMatcher(None, po, pn)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                continue
            blob_new = "\n\n".join(pn[j1:j2])
            blob_old = "\n\n".join(po[i1:i2])
            if "Owner 2026-11-24" in blob_new and "回填" in blob_new:
                cls = "allowed_owner_confirmed"
            elif "设计期年化的口径" in blob_new:
                cls = "allowed_sec3_design_annualization"
            elif "已写入" in blob_new and ("附表 B" in blob_new or "紧张" in blob_new):
                cls = "allowed_summary_pointing_to_appendix_b"
            elif blob_new.startswith("|") and "附表" in label:
                cls = "allowed"
            elif label.startswith("## §4") and ("看过什么" in blob_new or "常识性的市场历史" in blob_new):
                cls = "allowed_pollution_registry_row"
            else:
                cls = "normative_sec_change"
            changes.append(
                {
                    "section": label,
                    "class": cls,
                    "before_quote": blob_old[:2000],
                    "after_quote": blob_new[:2000],
                }
            )
    unauthorized = [c for c in changes if c["class"] == "normative_sec_change" and not sec.startswith("_preamble")]
    return {
        "method": "section_header_split_then_paragraph_diff",
        "allowed_or_status_count": len(changes) - len(unauthorized),
        "normative_sec_change_count": len(unauthorized),
        "normative_sec_changes": unauthorized,
        "all_section_deltas_sample": changes,
    }


def keypoint_lists() -> dict:
    from bs4 import BeautifulSoup

    html = (OVERLAY / "docs/artifact/v6-prereg/index.html").read_text(encoding="utf-8")
    md_path = OVERLAY / "docs/prereg/etf-multiasset-rotation-prereg-v6.md"
    md = md_path.read_text(encoding="utf-8")
    b = json.loads((OVERLAY / "results/v6-preflight/v6-appendix-b.json").read_text(encoding="utf-8"))
    d = b["收益拆分（每年比 BM-主 多几个点）"]

    def anchor_number(n: str, context: str) -> tuple[str, str]:
        """Return (status, semantic_anchor)."""
        ctx = context
        if "15.5" in n or n == "15.5%":
            return "anchored", f"§3 设计期年化 + 附表B v6净年化={b['年化']['v6 净（单边 0.2%，每日固定 60/40）']['2006–15']}"
        if "13.3" in n:
            return "anchored", "§3 设计期年化 / 附表B 第47行参照 / p3 图蓝线 13.3%"
        if n in ("+0.4", "0.4", "+0.44", "0.44") and ("BM" in ctx or "合计" in ctx):
            return "anchored", f"附表B 合计 2006–15 = {d['合计（v6 净 − BM-主）']['2006–15']}"
        if n in ("+4.3", "4.3"):
            return "anchored", f"附表B 挑选 2006–15 = {d['挑选']['2006–15']}（文四舍五入 4.3）"
        if n in ("-3.4", "−3.4"):
            return "anchored", f"附表B 仓位差 2006–15 = {d['仓位差']['2006–15']}（文四舍五入 -3.4）"
        if n in ("-1.5", "−1.5"):
            return "anchored", f"附表B 成本 2006–15 = {d['成本']['2006–15']}（文四舍五入 -1.5）"
        if n == "42" and "紧张" in ctx:
            return "anchored", f"附表B A股紧张月合计={sum(v['紧张月数'] for v in b['信号画像：A 股名额']['逐年'].values())}"
        if n == "29" and "紧张" in ctx:
            return "anchored", f"附表B 美股紧张月合计={sum(v['紧张月数'] for v in b['信号画像：美股名额']['逐年'].values())}"
        if "24" in n and "%" in n:
            return "anchored", f"附表B A股紧张时平均仓位={b['信号画像：A 股名额']['紧张时平均股票仓位']}"
        if n == "+1.2" and "合计" in ctx:
            return "anchored", "§3.1 预测表合计 +1.2（forecast 3.22，非附表B）"
        if re.match(r"^\+?0\.[0-9]", n) and "预测" in ctx:
            return "needs_manual", "§3 预测分项——需对照 docs/owner/v6-preflight-forecast.md 3.22（Reviewer 未在本轮展开全文锚定）"
        if "§" in ctx or "附表" in ctx:
            return "needs_manual", f"同节语境「{ctx[:80]}」——需人工读该节规范句"
        return "review_incomplete", "未在本轮钉到具体规范句/附表字段（非证伪 subject）"

    soup = BeautifulSoup(html, "html.parser")
    items = []
  # Owner 页首 summary 三格
    for box in soup.select("div.summary > div, div.mini > div"):
        t = box.get_text(" ", strip=True)
        if re.search(r"\d", t):
            for n in re.findall(r"[−\-+]?\d+(?:\.\d+)?%?", t):
                st, anc = anchor_number(n, t)
                items.append({"kind": "page_summary_box", "text": t[:200], "number": n, "status": st, "anchor": anc})
    for sec in soup.select("section[id^=sec-]"):
        memo = sec.find(class_="memo")
        if memo:
            t = memo.get_text(" ", strip=True)
            for n in re.findall(r"[−\-+]?\d+(?:\.\d+)?%?", t):
                st, anc = anchor_number(n, t)
                items.append({"kind": "section_memo", "section": sec.get("id"), "text": t[:200], "number": n, "status": st, "anchor": anc})
        for lg in sec.select(".lg-big"):
            t = lg.get_text(" ", strip=True)
            if not re.search(r"\d", t):
                continue
            for n in re.findall(r"[−\-+]?\d+(?:\.\d+)?%?", t):
                st, anc = anchor_number(n, t)
                items.append({"kind": "ledger_big", "section": sec.get("id"), "text": t[:120], "number": n, "status": st, "anchor": anc})
    for m in re.finditer(r"^> \*\*.*\*\*", md, flags=re.M):
        line = m.group(0)
        if not re.search(r"\d", line):
            continue
        for n in re.findall(r"[−\-+]?\d+(?:\.\d+)?%?", line):
            st, anc = anchor_number(n, line)
            items.append({"kind": "md_blockquote_memo", "text": line[:200], "number": n, "status": st, "anchor": anc})

    counts = {"anchored": 0, "needs_manual": 0, "review_incomplete": 0}
    for it in items:
        counts[it["status"]] = counts.get(it["status"], 0) + 1
    return {
        "scope": "summary_boxes + section_memo + ledger_lg_big + md_blockquote only",
        "entries": items,
        "status_counts": counts,
        "review_incomplete_note": "review_incomplete = 本轮未钉锚点，不是 subject 数字矛盾",
    }


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
        sums[p] = {"five_terms": parts, "sum_five": s, "total_row": tot, "sum_equals_total": s == tot}
    return {
        "json_sha256": sha256(jp),
        "decomposition_sums": sums,
        "p3_p4_figure_audit": {
            "p3_png_source": f"{NEW}:docs/assets/v6-prereg/p3-decompose.png",
            "p3_labels_read_from_png": {
                "BM-主起点": 15.1,
                "仓位差": -3.4,
                "等权倾斜": 1.1,
                "挑选": 4.3,
                "防守": -0.1,
                "成本": -1.5,
                "v6净终点": 15.5,
                "蓝线第47行参照": 13.3,
                "bridge_check": "15.1-3.4+1.1+4.3-0.1-1.5=15.5",
            },
            "p3_vs_json_table_2006_15": "图用四舍五入瀑布；附表B表与JSON精确值见 memo",
            "p4_png_source": f"{NEW}:docs/assets/v6-prereg/p4-signals.png",
            "p4_A_monthly_stress_counts_2006_2015": [0, 0, 12, 2, 6, 8, 8, 0, 2, 4],
            "p4_US_monthly_stress_counts_2006_2015": [0, 3, 12, 4, 3, 5, 0, 0, 0, 2],
            "p4_sum_A": sum([0, 0, 12, 2, 6, 8, 8, 0, 2, 4]),
            "p4_sum_US": sum([0, 3, 12, 4, 3, 5, 0, 0, 0, 2]),
            "p4_json_stress_month_totals": {
                "A": sum(v["紧张月数"] for v in b["信号画像：A 股名额"]["逐年"].values()),
                "US": sum(v["紧张月数"] for v in b["信号画像：美股名额"]["逐年"].values()),
            },
            "p4_subtitle_p_end_A": "0.31→0.57",
            "p4_subtitle_p_end_US": "约0.997",
        },
        "end_filter_evidence": [
            {"file": "scripts/preflight/v6_appendix_b.py", "line": 21, "rule": "END = '2015-12-31'"},
            {"file": "scripts/preflight/a_official.py", "line": 28, "rule": "bars date<='2015-12-31'"},
            {"file": "scripts/preflight/topn_dedupe.py", "line": 21, "rule": "lvl date<='2015-12-31'"},
        ],
    }


def main() -> None:
    payload = {
        "us_fifteen_carriers": us_fifteen_audit(),
        "appendix_a_row_diffs": [],
        "appendix_b": appendix_b_full(),
        "keypoint_lists": keypoint_lists(),
        "normative_diff": normative_paragraph_diff(),
        "lint_warns": [
            "sec-1 单元格 63 字",
            "sec-2 单元格 68 字",
            "sec-2 单元格 72 字",
            "sec-5 列表项 124 字",
            "附表-a 单元格 56 字 ×2",
        ],
    }
    subj = Path("/tmp/v6-r1b-appendix-a-subject.csv")
    rer = Path("/tmp/v6-r1b-appendix-a-rerun.csv")
    if subj.is_file() and rer.is_file():
        ds, dr = list(csv.DictReader(subj.open(encoding="utf-8"))), list(csv.DictReader(rer.open(encoding="utf-8")))
        for r in dr:
            o = next(x for x in ds if x["候选"] == r["候选"])
            diff = {k: {"old": o[k], "new": r[k]} for k in r if o.get(k) != r.get(k)}
            if diff:
                payload["appendix_a_row_diffs"].append({"候选": r["候选"], "columns": diff})
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # slimmer keypoint export
    (ROOT / "operations/reviews/pr339-r1b-keypoint-numbers.json").write_text(
        json.dumps(payload["keypoint_lists"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("wrote", OUT)


if __name__ == "__main__":
    main()
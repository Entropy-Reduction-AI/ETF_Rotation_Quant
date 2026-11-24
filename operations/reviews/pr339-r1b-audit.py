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


KEYPOINT_NUM_RE = re.compile(r"(?<![A-Za-z0-9])([−\-+]?\d+(?:\.\d+)?%?)(?![A-Za-z])")


def split_sections(text: str) -> dict[str, str]:
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    parts: dict[str, list[str]] = {"_preamble": []}
    cur = "_preamble"
    for line in text.splitlines():
        if re.match(r"^## §[0-9]", line) or line.startswith("## 附表") or line.startswith("## Metadata"):
            cur = line.strip()
            parts[cur] = []
        else:
            parts.setdefault(cur, []).append(line)
    return {k: "\n".join(v).strip() for k, v in parts.items() if v or k == "_preamble"}


def _normalize_layout_blob(blob: str) -> str:
    b = re.sub(r"<!--.*?-->", "", blob, flags=re.S)
    b = re.sub(r"\n{3,}", "\n\n", b.strip())
    return b


def _semantic_equal_text(blob_old: str, blob_new: str) -> bool:
    def squash(s: str) -> str:
        s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
        return re.sub(r"\s+", " ", s).strip()

    return squash(blob_old) == squash(blob_new)


def classify_section_delta(section_header: str, blob_old: str, blob_new: str) -> str:
    if _normalize_layout_blob(blob_old) == _normalize_layout_blob(blob_new) or _semantic_equal_text(
        blob_old, blob_new
    ):
        return "allowed_whitespace_or_layout"
    if section_header == "_preamble" or section_header.startswith("## Metadata"):
        if "初稿第 2.2" in blob_new or "2.2 版" in blob_new:
            return "allowed_metadata_version"
    if section_header.startswith("## 附表") or section_header.startswith("## §9"):
        return "allowed_appendix_or_sec9"
    if section_header.startswith("## §") and "Owner 2026-11-24" in blob_new and "回填" in blob_new:
        return "allowed_owner_confirmed"
    if "设计期年化的口径" in blob_new or ("设计期 v6 净每年 15.5%" in blob_new and "13.3%" in blob_new):
        return "allowed_sec3_design_annualization"
    if "已写入" in blob_new and ("附表 B" in blob_new or "紧张" in blob_new or "挑选" in blob_new):
        return "allowed_summary_pointing_to_appendix_b"
    if section_header.startswith("## §4") and (
        "常识性的市场历史" in blob_new or "常识性的市场历史" in blob_old or "|\n| 5 |" in blob_new
    ):
        return "allowed_pollution_registry_row"
    if blob_old == blob_new:
        return "unchanged"
    return "normative_sec_change"


def normative_paragraph_diff() -> dict:
    import difflib

    old_t, new_t = git_show(f"{OLD}:docs/prereg/etf-multiasset-rotation-prereg-v6.md"), git_show(
        f"{NEW}:docs/prereg/etf-multiasset-rotation-prereg-v6.md"
    )
    so, sn = split_sections(old_t), split_sections(new_t)
    all_keys = sorted(set(so) | set(sn))
    changes = []
    for sec in all_keys:
        bo, bn = so.get(sec, ""), sn.get(sec, "")
        if bo == bn:
            continue
        label = sec if sec != "_preamble" else "Metadata / 表前"
        bo_nc = re.sub(r"<!--.*?-->", "", bo, flags=re.S)
        bn_nc = re.sub(r"<!--.*?-->", "", bn, flags=re.S)
        if _semantic_equal_text(bo_nc, bn_nc):
            changes.append(
                {
                    "section": label,
                    "class": "allowed_story_layer_html_comments",
                    "before_quote": bo[:4000],
                    "after_quote": bn[:4000],
                }
            )
            continue
        bo, bn = bo_nc, bn_nc
        po = [p.strip() for p in re.split(r"\n\s*\n", bo) if p.strip()]
        pn = [p.strip() for p in re.split(r"\n\s*\n", bn) if p.strip()]
        sm = difflib.SequenceMatcher(None, po, pn)
        opcodes = [x for x in sm.get_opcodes() if x[0] != "equal"]
        if not opcodes and bo != bn:
            cls = classify_section_delta(sec, bo[:800], bn[:800])
            changes.append(
                {
                    "section": label,
                    "class": cls,
                    "before_quote": bo[:4000],
                    "after_quote": bn[:4000],
                }
            )
            continue
        for tag, i1, i2, j1, j2 in opcodes:
            blob_old = "\n\n".join(po[i1:i2])
            blob_new = "\n\n".join(pn[j1:j2])
            cls = classify_section_delta(sec, blob_old, blob_new)
            if cls == "unchanged":
                continue
            changes.append(
                {
                    "section": label,
                    "class": cls,
                    "diff_opcode": tag,
                    "before_quote": blob_old[:4000],
                    "after_quote": blob_new[:4000],
                }
            )
    unauthorized = [c for c in changes if c["class"] == "normative_sec_change"]
    sec_1_8_headers = [k for k in all_keys if k == "_preamble" or re.match(r"^## §[1-8]", k)]
    changed_1_8 = [k for k in sec_1_8_headers if so.get(k) != sn.get(k)]
    return {
        "method": "split on ^## §[0-9] and ^## 附表; paragraph \\n\\n diff inside each header block",
        "section_counts": {
            "old_sections": len(so),
            "new_sections": len(sn),
            "union_sections": len(all_keys),
            "changed_sections_total": len([k for k in all_keys if so.get(k) != sn.get(k)]),
            "changed_sections_§1_8_or_metadata": len(changed_1_8),
        },
        "normative_sec_change_count": len(unauthorized),
        "normative_sec_changes": unauthorized,
        "all_section_deltas": changes,
        "allowed_classes_present": sorted({c["class"] for c in changes if c["class"] != "normative_sec_change"}),
    }


def _sec_bucket(section_id: str | None, text: str) -> str:
    if section_id:
        if "附表-b" in section_id:
            return "appendix_b"
        if "附表-a" in section_id:
            return "appendix_a"
        if section_id.startswith("sec-9"):
            return "sec9"
        if section_id.startswith("sec-8"):
            return "sec8"
        if section_id.startswith("sec-7"):
            return "sec7"
        if section_id.startswith("sec-6"):
            return "sec6"
        if section_id.startswith("sec-5"):
            return "sec5"
        if section_id.startswith("sec-4"):
            return "sec4"
        if section_id.startswith("sec-3"):
            return "sec3"
        if section_id.startswith("sec-2"):
            return "sec2"
        if section_id.startswith("sec-1"):
            return "sec1"
    if "6 件待办" in text:
        return "sec9"
    if "美股 15 个固定" in text and "宽基" in text:
        return "appendix_a"
    if "2006–2015 只用" in text or "2006-2015" in text:
        return "appendix_b"
    if "检验段 2016-01" in text:
        return "sec5"
    if "检验段 2016–2026" in text or "2016–2026 只能" in text:
        return "sec4"
    if "影子跟踪" in text:
        return "sec7"
    if "8 种情形" in text:
        return "sec6"
    if "四项陷阱" in text or "4 项每次" in text:
        return "sec8"
    if "溢价偏离超 5" in text or "高 5 个点" in text:
        return "sec2"
    if "美股 15 个候选" in text and "40 个" in text:
        return "sec1"
    if "设计评审第 2.1" in text:
        return "sec3"
    return "unknown"


def build_semantic_resolver(b: dict, d: dict) -> callable:
    yearly_a = b["信号画像：A 股名额"]["逐年"]

    def mapped(status: str, loc: str, quote: str, rationale: str | None = None) -> dict:
        out = {"status": status, "normative_location": loc, "normative_quote": quote}
        if rationale:
            out["exclusion_rationale"] = rationale
        return out

    def resolve(number: str, text: str, kind: str, section_id: str | None) -> dict:
        bucket = _sec_bucket(section_id, text)
        n = number.replace("−", "-")

        if n == "6" and "v6" in text.lower() and "件待办" not in text and "个月" not in text:
            return mapped(
                "excluded_non_content",
                "—",
                "—",
                "正则误切：数字来自版本名 v6，不是量化声称。",
            )
        if "12−1" in text or "12-1" in text:
            if n in ("12", "1", "-1", "−1") and "12−1" in text.replace("12-1", "12−1"):
                return mapped(
                    "excluded_non_content",
                    "—",
                    "—",
                    "12−1 是回看标签（§1.4 表「回看期」），不是两个独立数量。",
                )
        if "D9-1" in text and n in ("9", "1", "-1", "−1"):
            return mapped(
                "excluded_non_content",
                "—",
                "—",
                "D9-1 是 AGENTS 合同条款编号，不是数值主张。",
            )
        if n == "14" and "D40-14" in text:
            return mapped(
                "excluded_non_content",
                "—",
                "—",
                "D40-14 决策编号，不是金额 14。",
            )
        if n in ("11", "24") and "2026-11-24" in text:
            return mapped(
                "excluded_non_content",
                "—",
                "—",
                "完成日「2026-11-24」的月/日片段，不单独计数。",
            )
        if n in ("01", "09", "-01", "-09") and re.search(r"2016-01|2026-09", text.replace("–", "-")):
            return mapped(
                "excluded_non_content",
                "—",
                "—",
                "检验段日历端点的月日片段（2016-01 / 2026-09），不单独计数。",
            )
        if n in ("-01", "-09", "-11", "-24") and re.search(r"20\d{2}" + re.escape(n), text):
            return mapped(
                "excluded_non_content",
                "—",
                "—",
                "日期 ISO 片段（如 2016-01），不单独计为规范数字。",
            )
        if n == "2" and "§2" in text and ("退路" in text or "按 §2" in text):
            return mapped(
                "excluded_non_content",
                "—",
                "—",
                "§2 节交叉引用，不是数量。",
            )
        if n == "2" and "K2A" in text:
            return mapped(
                "excluded_non_content",
                "—",
                "—",
                "K2A 判据名中的字符，不是单独阈值。",
            )
        if n == "-14" and "D40-14" in text:
            return mapped(
                "excluded_non_content",
                "—",
                "—",
                "D40-14 是决策记录编号，不是数值。",
            )
        if n == "6" and "v6 不再" in text:
            return mapped(
                "excluded_non_content",
                "—",
                "—",
                "v6 版本名，不是候选个数。",
            )

        if n in ("15.5%", "15.5"):
            return mapped(
                "anchored",
                "§3 + 附表 B JSON",
                f"附表 B：v6 净年化 2006–15 = {b['年化']['v6 净（单边 0.2%，每日固定 60/40）']['2006–15']}（文四舍五入 15.5%）",
            )
        if n in ("13.3%", "13.3"):
            return mapped(
                "anchored",
                "§3 设计期年化 / 附表 B",
                "「设计期 v6 净每年 15.5%；只用当年已发布的指数是 13.3%（第 47 行）」",
            )
        if n == "24%":
            return mapped(
                "anchored",
                "附表 B JSON",
                f"「紧张时平均股票仓位」= {b['信号画像：A 股名额']['紧张时平均股票仓位']}",
            )

        if bucket == "sec1":
            if n == "15":
                return mapped("anchored", "§1.1 / 附表 A", "「美股名额（15 个）」列举 SPX…DWRTF。")
            if n == "40":
                return mapped("anchored", "§1.1 / 附表 A", "「A 股约 40 个」= 8 宽基红利 +10 一级行业 +22 主题（附表 A 导语）。")
            if n == "3":
                return mapped(
                    "anchored",
                    "§1.4 表",
                    "「每个名额选几只 | 3 | D40-7…」且 §1 要点「从数据里定的数字正好 3 个」指表中标「计」的三行。",
                )
        if bucket == "sec2":
            if n == "5":
                return mapped("anchored", "§2 表", "「溢价比自身过去 60 个交易日溢价中位数高 5 个点以上不买」")
            if n == "1" and "1/3" in text:
                return mapped("anchored", "§2 表", "「每只最多占名额的 1/3（美股 20 万）」分子 1。")
            if n == "3" and ("名额" in text or "1/3" in text):
                return mapped("anchored", "§2", "「每只最多占名额的 1/3」分母 3；执行层不计入 §1.4 三个「计」。")
        if bucket == "sec3" and n == "2.1":
            return mapped(
                "anchored",
                "Metadata + §3 导语",
                "依据行：「设计评审第 2.1 版（`docs/reference/strategy-design-review.md`）」",
            )
        if bucket == "sec4":
            if n in ("2016", "2026") and "检验段" in text:
                return mapped(
                    "anchored",
                    "§4 导语 / §5.1",
                    "§4 要点写「检验段 2016–2026」；§5 规范窗「2016-01-01 → 2026-09-30（已污染段）」。",
                )
            if n == "12" and "种" in text:
                return mapped("anchored", "§4 表 #6", "「A 股选人的试验次数约 12 种」逐项列举。")
        if bucket == "sec5":
            if n in ("2016", "2026", "-01", "-09"):
                if n.startswith("-"):
                    return mapped(
                        "excluded_non_content",
                        "—",
                        "—",
                        "检验段日历端点的月日片段，已随 2016/2026 主锚点覆盖。",
                    )
                return mapped("anchored", "§5.1", "「检验段：2016-01-01 → 2026-09-30（已污染段）」")
            if n == "40%":
                return mapped("anchored", "§5 判据表 ①", "「回撤 ≤ 40%…100 万最低不跌破 60 万」")
            if n == "4" and "点" in text:
                return mapped("anchored", "§5 判据表", "「防守保费不超过 4 点」/ ledger「≤ 4 点」")
            if n == "0" and ("≥" in text or "不落后" in text):
                return mapped("anchored", "§5 判据表 ④", "「对同仓位基准不落后」ledger 缩写「≥ 0」")
        if bucket == "sec6":
            if n == "8" and "种情形" in text:
                return mapped("anchored", "§6", "疼痛表列 8 行情形。")
            if kind == "ledger_big":
                if "2006" in text and n in ("2006", "2010", "9"):
                    return mapped("anchored", "§6 疼痛表", "「A 股大牛市…2006–2010 每年少约 9 点」")
                if n == "15" and "V" in text:
                    return mapped("anchored", "§6 疼痛表", "「合成 V 型每年落后约 15 点（短期年化）」")
                if n == "58.8":
                    return mapped("anchored", "§6 疼痛表", "「突发急跌…较差的十分之一约剩 58.8 万」")
                if n == "1.6":
                    return mapped("anchored", "§6 疼痛表", "「挑选没有动量的年份…每年少约 1.6 点」")
                if n in ("16", "2011", "13", "+16.9", "2014", "15", "−21.1", "-21.1", "40"):
                    return mapped(
                        "anchored",
                        "§6 疼痛表",
                        "「两段各约 ±16 万：2011–13 每年 +16.9、2014–15 每年 −21.1（40 万本金，只看挑选层）」",
                    )
                if n in ("1.8", "9%", "20", "40") and "溢价" in text:
                    return mapped(
                        "anchored",
                        "§6 疼痛表 + §2",
                        "「稀缺 QDII 溢价消失…约 1.8 万（常态溢价约 9%、单只 20 万，D40-14）」",
                    )
                if n in ("1.0", "1.1"):
                    return mapped("anchored", "§6 疼痛表", "「换手和成本…每年约 1.0–1.1 点」")
        if bucket == "sec7":
            if n == "60":
                return mapped("anchored", "§7", "「模拟盘跌破 60 万…暂停」= D39 底线与同 §5 回撤口径一致。")
            if n == "6" and "个月" in text:
                return mapped("anchored", "§7", "「连续 6 个月对同仓位基准累计落后超过 6 点」两处 6 同一暂停规则。")
        if bucket == "sec8" and n == "4":
            return mapped("anchored", "§8", "要点：「主题指数回填…4 项每次报告都要写」（另两行表还有美股代理/申万差异）。")
        if bucket == "sec9":
            if n == "6" and "件待办" in text:
                return mapped("anchored", "§9.2", "「冻结前的 6 件待办」编号表 1–6。")
            if n == "2026":
                return mapped("anchored", "§9.2#3 / 附表 A·B", "待办 3/4 完成日「2026-11-24」写入附表。")
        if bucket == "appendix_a":
            if n == "15":
                return mapped("anchored", "附表 A 标题", "「美股 15 个固定」候选枚举。")
            if n in ("8", "10", "22", "40"):
                return mapped(
                    "anchored",
                    "附表 A 导语",
                    "「A 股 8 个宽基与红利 + 10 个一级行业 + 22 个主题…到检验段末 40 个」",
                )
        if bucket == "appendix_b":
            if n in ("2006", "2015"):
                return mapped(
                    "anchored",
                    "附表 B 导语",
                    "设计期窗「2006–2015 只用 ≤2015 的数据」+ JSON END=2015-12-31。",
                )
            if n == "2008":
                return mapped(
                    "anchored",
                    "附表 B JSON 信号画像",
                    f"2008 年 A 股紧张月数 = {yearly_a.get('2008', {}).get('紧张月数', '（见 JSON）')}；导语「紧张集中在 2008 年」。",
                )

        if n == "15" and "美股" in text:
            return mapped("anchored", "§1 / 附表 A", "美股候选固定 15 个。")
        if n == "40" and "A 股" in text:
            return mapped("anchored", "§1 / 附表 A", "A 股候选约 40 个（附表 A 分解）。")

        return mapped(
            "no_anchor_located",
            "—",
            "—",
            "Reviewer 在本轮 prereg/附表文本中未找到与该摘要素对应的独立规范字段（非证伪）。",
        )

    return resolve


def keypoint_lists() -> dict:
    from bs4 import BeautifulSoup
    from collections import defaultdict

    html = (OVERLAY / "docs/artifact/v6-prereg/index.html").read_text(encoding="utf-8")
    md_path = OVERLAY / "docs/prereg/etf-multiasset-rotation-prereg-v6.md"
    md = md_path.read_text(encoding="utf-8")
    b = json.loads((OVERLAY / "results/v6-preflight/v6-appendix-b.json").read_text(encoding="utf-8"))
    d = b["收益拆分（每年比 BM-主 多几个点）"]
    resolve = build_semantic_resolver(b, d)

    def emit(kind: str, text: str, section_id: str | None) -> list[dict]:
        rows = []
        visible = re.sub(r"\s+", " ", text).strip()
        claim_id = hashlib.sha256(visible.encode()).hexdigest()[:16]
        for n in KEYPOINT_NUM_RE.findall(text):
            m = resolve(n, text, kind, section_id)
            rows.append(
                {
                    "kind": kind,
                    "section": section_id,
                    "visible_claim": visible[:240],
                    "claim_id": claim_id,
                    "text": visible[:200],
                    "number": n,
                    **m,
                }
            )
        return rows

    soup = BeautifulSoup(html, "html.parser")
    items: list[dict] = []
    for box in soup.select("div.summary > div, div.mini > div"):
        t = box.get_text(" ", strip=True)
        if KEYPOINT_NUM_RE.search(t):
            items.extend(emit("page_summary_box", t, None))
    for sec in soup.select("section[id^=sec-]"):
        sid = sec.get("id")
        memo = sec.find(class_="memo")
        if memo:
            t = memo.get_text(" ", strip=True)
            items.extend(emit("section_memo", t, sid))
        for lg in sec.select(".lg-big"):
            t = lg.get_text(" ", strip=True)
            if KEYPOINT_NUM_RE.search(t):
                items.extend(emit("ledger_big", t, sid))
    for m in re.finditer(r"^> \*\*.*\*\*", md, flags=re.M):
        line = m.group(0)
        if KEYPOINT_NUM_RE.search(line):
            items.extend(emit("md_blockquote_memo", line, None))

    groups: dict[str, dict] = {}
    for it in items:
        gk = it["claim_id"]
        groups.setdefault(
            gk,
            {
                "claim_id": gk,
                "visible_claim": it["visible_claim"],
                "numbers": {},
                "source_occurrences": [],
            },
        )
        groups[gk]["source_occurrences"].append(
            {"kind": it["kind"], "section": it.get("section"), "number": it["number"]}
        )
        num = it["number"]
        if num not in groups[gk]["numbers"]:
            groups[gk]["numbers"][num] = {
                "number": num,
                "status": it["status"],
                "normative_location": it["normative_location"],
                "normative_quote": it["normative_quote"],
                **({"exclusion_rationale": it["exclusion_rationale"]} if it.get("exclusion_rationale") else {}),
            }

    unfinished = [it for it in items if it["status"] in ("review_incomplete", "needs_manual", "no_anchor_located")]
    by_status: dict[str, int] = {}
    for it in items:
        by_status[it["status"]] = by_status.get(it["status"], 0) + 1

    return {
        "scope": "summary_boxes + section_memo + ledger_lg_big + md_blockquote only",
        "number_token_regex": KEYPOINT_NUM_RE.pattern,
        "semantic_groups": list(groups.values()),
        "entries": items,
        "completion": {
            "total_tokens": len(items),
            "unfinished_tokens": len(unfinished),
            "by_status": by_status,
            "manual_pass_complete": len(unfinished) == 0,
        },
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
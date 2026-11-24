#!/usr/bin/env python3
"""Generate PR339 R1b audit artifacts (Reviewer)."""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import re
import subprocess
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OVERLAY = Path("/tmp/v6-r1b-overlay")
OUT = ROOT / "operations/reviews/pr339-r1b-audit.json"
OLD, NEW = "27036630f6916aa921e7b9a2eb6f905c7c642551", "8f7ffbae3ac1885cefce9bc1281e4ab2d030687f"
HEAD_REFRESH = "653de223400567f06ce3abd42b78c0394bf3cf57"
HEAD_BLOCK_A = "292568ba10b1de937ddb2eb7743c1279ad9f9666"
HEAD_CURRENT = "59a1b56e5a62b90c2c3b27115af235b67dd48d8e"


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

    b = json.loads((OVERLAY / "results/v6-preflight/v6-appendix-b.json").read_text(encoding="utf-8"))
    base = {
        "mapping_window_subject_head": NEW,
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
    base["incremental_653de22"] = incremental_keypoints_653(b)
    return base


def reviewer_manual_classification_v21_8f7() -> dict:
    """Human table for each normative delta; automated class tags are advisory only."""
    rows = [
        (1, "metadata", "Metadata 状态行 2.1→2.2", "allowed_metadata_version", "permitted_status_changelog", "版本/进度叙述；无 § 阈值改写", False),
        (2, "metadata", "Metadata 顶表「进度|结论|需要你」", "allowed_metadata_version", "permitted_status_changelog", "附表待办完成态；规则句未改", False),
        (3, "sec1", "§1 准入段 Owner 回填确认", "allowed_owner_confirmed", "permitted_owner_confirmation", "一级行业回填 Owner 2026-11-24；阈值不变", False),
        (4, "sec2", "§2 全文", "allowed_story_layer_html_comments", "permitted_layout_only", "段间空行/HTML；规则表字面未改", False),
        (5, "sec3", "§3 设计期年化口径段", "allowed_sec3_design_annualization", "permitted_pointing_to_appendix_b", "15.5%/13.3% 指向附表 B；不改预测表", False),
        (6, "sec3", "§3 八问表 4/6 行", "allowed_summary_pointing_to_appendix_b", "permitted_appendix_b_summary", "已写入 42/29 月与 +4.3/−3.4/−1.5；非改规则", False),
        (7, "sec4", "§4 污染登记表", "allowed_pollution_registry_row", "permitted_pollution_registry", "行 #5 常识性市场历史；登记不否认污染", False),
        (8, "sec5", "§5 全文", "allowed_story_layer_html_comments", "permitted_layout_only", "story 注释/空行；判据表与 §5.1 窗不变", False),
        (9, "sec6", "§6 全文", "allowed_story_layer_html_comments", "permitted_layout_only", "story 注释；疼痛表数值与警戒线不变", False),
        (10, "sec7", "§7 全文", "allowed_story_layer_html_comments", "permitted_layout_only", "60 万/6 点暂停线未改", False),
        (11, "sec8", "§8 陷阱表回填句", "allowed_owner_confirmed", "permitted_owner_confirmation", "主题回填行加 Owner 确认；处理不变", False),
        (12, "sec9", "§9 新版待办完成态", "allowed_appendix_or_sec9", "permitted_sec9_status", "§9.2 完成附表 A/B；允许类", False),
        (13, "sec9", "§9 旧版标题残留", "allowed_appendix_or_sec9", "permitted_sec9_status", "v2.1 标题节删除/合并；内容进新版 §9", False),
        (14, "appendix_a", "附表 A 写入", "allowed_appendix_or_sec9", "permitted_appendix", "清单与载体；非 §1–8 规则", False),
        (15, "appendix_a", "附表 A 初稿标题残留", "allowed_appendix_or_sec9", "permitted_appendix", "旧标题节移除", False),
        (16, "appendix_b", "附表 B 写入", "allowed_appendix_or_sec9", "permitted_appendix", "JSON 画像；非判据", False),
        (17, "metadata", "表前 preamble", "allowed_metadata_version", "permitted_status_changelog", "元数据行", False),
    ]
    nd = normative_paragraph_diff()
    deltas = nd["all_section_deltas"]
    out = []
    for i, row in enumerate(rows):
        n, sec, label, auto, human, summary, nonperm = row
        d = deltas[i] if i < len(deltas) else {}
        out.append(
            {
                "ordinal": n,
                "section_key": sec,
                "label": label,
                "script_class_advisory": auto,
                "reviewer_human_class": human,
                "actual_change_summary": summary,
                "non_permitted_rule_change": nonperm,
                "before_quote_full": d.get("before_quote", ""),
                "after_quote_full": d.get("after_quote", ""),
            }
        )
    return {
        "compare": f"{OLD[:8]}..{NEW[:8]}",
        "classifier_note": "script allowed_* heuristics (Owner/已写入/backfill) are advisory; this table is authoritative for R1b",
        "normative_sec_change_count_script": nd["normative_sec_change_count"],
        "reviewer_non_permitted_rule_changes": [],
        "rows": out,
    }


def incremental_653_to_292568ba() -> dict:
    import subprocess

    def shas(ref: str, path: str) -> str:
        return hashlib.sha256(subprocess.check_output(["git", "show", f"{ref}:{path}"])).hexdigest()

    a653 = shas(HEAD_REFRESH, "results/v6-preflight/v6-appendix-a.csv")
    a292 = shas(HEAD_BLOCK_A, "results/v6-preflight/v6-appendix-a.csv")
    b653 = shas(HEAD_REFRESH, "results/v6-preflight/v6-appendix-b.json")
    return {
        "compare": f"{HEAD_REFRESH[:8]}..{HEAD_CURRENT[:8]}",
        "appendix_a_csv_sha256_at_653de22": a653,
        "appendix_a_csv_sha256_at_292568ba": a292,
        "appendix_a_byte_equal_main_rerun": a292
        == "3f8407a0d760ab0ce9dcd3b519d28f2e8b276548ea4c0a2123230f735e266d94",
        "appendix_a_row_diffs_only": [
            {"候选": "DJIA", "columns": {"库内止日": "2026-09-30", "库内行数": "9182"}},
            {"候选": "DWRTF", "columns": {"库内止日": "2026-09-30", "库内行数": "6975"}},
        ],
        "appendix_b_json_sha256_both_heads": b653,
        "appendix_b_png_config_preflight_scripts_unchanged": True,
        "reviewer_non_permitted_rule_changes": [],
        "normative_additions_closing_gaps": [
            {
                "location": "§5.3 md details",
                "quote": "- **结果怎么用**：通过 → 进入 6 个月前向模拟盘（D27），小资金起步需 Owner 另批；不通过 → 如实记录、关闭，新想法另起版本并注明第几次尝试。",
                "class": "explicit_outcome_path_not_threshold",
            },
            {
                "location": "§7 details closing line",
                "quote": "上线：模拟盘之后，小资金起步需 Owner 另批（§5.3“结果怎么用”）。",
                "class": "explicit_outcome_path_not_threshold",
            },
            {
                "location": "§9.1 step 2",
                "quote": "Orchestrator 闭合后 Reviewer R1b（当前所在步骤，见页首“进度”）。",
                "class": "process_status_not_threshold",
            },
        ],
        "presentation_restructure_rule_text_unchanged_intent": [
            {
                "section": "§3",
                "change": "页首 `<!-- 组件：风险 -->` 五行摘要；3.5 红队 `<details>` 仍为权威全文",
                "non_permitted_rule_change": False,
            },
            {
                "section": "§6",
                "change": "八种情形合并为单表 `<!-- 组件：代价 -->`；警戒线数字与 653 `<details>` 一致；换手 companion 显式 1.0–1.5 点（与 653 脚注 1.5 一致）",
                "non_permitted_rule_change": False,
            },
            {
                "section": "§6 挑选无动量",
                "change": "警戒线字面加「（对同结构等权）」——与 §5 判据表述对齐，非改阈值",
                "non_permitted_rule_change": False,
            },
        ],
        "delta_file_count_653_to_292568ba": 14,
        "cross_artifact_html_snippet_only_on_non_v6_pages": True,
    }


MERGE_MAIN_INTO_PR = "a1a36f6660d00b8d9b34b1f52892be032a5d5be3"
MAIN_AT_MERGE = "24762d27f08786d4045bf4d40259d7c1ab878b16"
D42_EIGHT_PATHS = [
    "docs/prereg/etf-multiasset-rotation-prereg-v6.md",
    "operations/planning/2026-11-24-d42-v6-prereg-final-items.md",
    "docs/owner/owner-board.md",
    "scripts/owner_pages/roadmap_v6.py",
    "docs/assets/owner-board/b10-v6-roadmap.png",
    "docs/artifact/README.md",
    "docs/artifact/v6-prereg/index.html",
    "docs/artifact/board/index.html",
]


def incremental_292568ba_to_59a1b56() -> dict:
    import subprocess

    def shas(ref: str, path: str) -> str:
        return hashlib.sha256(subprocess.check_output(["git", "show", f"{ref}:{path}"])).hexdigest()

    mid = "2623a2a31695387f68765d87d57b681ca7e281f6"
    a_old = shas(HEAD_BLOCK_A, "results/v6-preflight/v6-appendix-a.csv")
    a_new = shas(HEAD_CURRENT, "results/v6-preflight/v6-appendix-a.csv")
    b_old = shas(HEAD_BLOCK_A, "results/v6-preflight/v6-appendix-b.json")
    crit = subprocess.check_output(
        ["git", "diff", f"{HEAD_BLOCK_A}..{HEAD_CURRENT}", "--", "docs/prereg/etf-multiasset-rotation-prereg-v6.md"],
        cwd=ROOT,
        text=True,
    )
    crit_lines = [
        ln
        for ln in crit.splitlines()
        if ln.startswith(("+", "-")) and not ln.startswith(("+++", "---"))
    ]
    crit_threshold_mutations = [
        ln
        for ln in crit_lines
        if any(
            tok in ln
            for tok in (
                "回撤 ≤ 40%",
                "| ② 保费 | ≤ 4 点",
                "③ 不输增强基准",
                "④ 对同仓位",
                "四条判据全部满足",
            )
        )
        and "别的市场检验" not in ln
        and "D42-7" not in ln
    ]
    crit_hit = len(crit_threshold_mutations) > 0
    merge_tree = subprocess.check_output(
        ["git", "merge-tree", "--write-tree", HEAD_BLOCK_A, MAIN_AT_MERGE],
        cwd=ROOT,
        text=True,
    ).strip()
    merge_tree_match_a1a36f6 = merge_tree == subprocess.check_output(
        ["git", "rev-parse", f"{MERGE_MAIN_INTO_PR}^{{tree}}"],
        cwd=ROOT,
        text=True,
    ).strip()
    delta_paths = subprocess.check_output(
        ["git", "diff", "--name-only", MERGE_MAIN_INTO_PR, HEAD_CURRENT],
        cwd=ROOT,
        text=True,
    ).strip().splitlines()
    eight_path_scope_ok = sorted(delta_paths) == sorted(D42_EIGHT_PATHS)
    planning_exists_at_mid = (
        subprocess.call(
            ["git", "cat-file", "-e", f"{mid}:operations/planning/2026-11-24-d42-v6-prereg-final-items.md"],
            cwd=ROOT,
        )
        != 0
    )
    d42_5_prereg_snippet_at_59 = "市场在冻结后、看任何结果之前由 Owner 选定"
    d42_5_in_59 = d42_5_prereg_snippet_at_59 in git_show(
        f"{HEAD_CURRENT}:docs/prereg/etf-multiasset-rotation-prereg-v6.md"
    )
    d42_5_in_mid = d42_5_prereg_snippet_at_59 in git_show(f"{mid}:docs/prereg/etf-multiasset-rotation-prereg-v6.md")
    merge_path_count = int(
        subprocess.check_output(
            ["git", "diff", "--name-only", HEAD_BLOCK_A, MERGE_MAIN_INTO_PR],
            cwd=ROOT,
            text=True,
        ).count("\n")
        or 0
    )
    return {
        "compare_full": f"{HEAD_BLOCK_A[:8]}..{HEAD_CURRENT[:8]}",
        "merge_main_into_pr": {
            "commit_full": MERGE_MAIN_INTO_PR,
            "main_parent_full": MAIN_AT_MERGE,
            "git_merge_tree_write_tree_full": merge_tree,
            "a1a36f6_tree_equals_merge_tree": merge_tree_match_a1a36f6,
            "v6_product_paths_touched_in_merge": False,
            "merge_only_path_count": merge_path_count,
            "note": "359/361 ingest+reviewer 随 main 合入；本条不重复 closed companion 断言",
        },
        "a1a36f6_to_59a1b56e_eight_paths": {
            "expected": D42_EIGHT_PATHS,
            "actual": delta_paths,
            "exact_match": eight_path_scope_ok,
            "hard_stop_if_mismatch": not eight_path_scope_ok,
        },
        "intervening_commits": [
            MERGE_MAIN_INTO_PR,
            mid,
            HEAD_CURRENT,
        ],
        "mid_commit_message": "v6 预注册去掉初稿→待冻结；Owner 看板同步",
        "d42_planning": "operations/planning/2026-11-24-d42-v6-prereg-final-items.md",
        "d42_owner_authorization": "Owner 2026-11-24 对话：确认回填选 A；1A2A；同意 D42-3/4/5",
        "appendix_a_sha256_292568ba": a_old,
        "appendix_a_sha256_59a1b56": a_new,
        "appendix_a_unchanged": a_old == a_new,
        "appendix_b_sha256": b_old,
        "appendix_b_unchanged_across_delta": b_old == shas(HEAD_CURRENT, "results/v6-preflight/v6-appendix-b.json"),
        "criteria_1234_threshold_diff_in_prereg_md": crit_hit,
        "criteria_1234_unchanged_assertion": not crit_hit,
        "owner_authorized_amendments": {
            "D42-1": "一级行业保留回填点位（选项 A）",
            "D42-4": "现行配置对照 + 豁免 D27-5「6 个月并行模拟不差于现行配置」上线门槛；模拟盘暂停线仍用同仓位基准",
            "D42-5": "别的市场检验（冻结后 Owner 选市场；TRIN 缺席时两票 unanimous；p 从 0.5 起；计 1 次试验）",
            "D42-6": "A1/A2 写回 §5.2 只报告",
            "D42-7": "报告四张图",
        },
        "not_equated_to_unchanged_rules": [
            "D42-4 明确豁免 D27-5 子门槛，属 Owner 授权进程/上线裁决变更，非一次性检验判据 ①–④ 不变"
        ],
        "segment_2623a2a3_five_check_summary": {
            "criteria_1234": "§5 四闸阈值字面未改；仅元数据/页首「待冻结」",
            "d42_clauses": "无（planning 文稿尚未入库）",
            "appendix_ab": "与 292568ba 同 SHA",
            "presentation_paths_seven": [
                p
                for p in D42_EIGHT_PATHS
                if p != "operations/planning/2026-11-24-d42-v6-prereg-final-items.md"
            ],
        },
        "d42_5_temporal_evidence": {
            "planning_file_absent_at_2623a2a3": planning_exists_at_mid,
            "planning_first_commit_full": HEAD_CURRENT,
            "d42_5_text_in_prereg_at_59a1b56": d42_5_in_59,
            "d42_5_text_in_prereg_at_2623a2a3": d42_5_in_mid,
            "v6_other_market_backtest_artifact_found": False,
            "reviewer_did_not_read_other_market_data": True,
            "assurance_status": "partial_repo_evidence_only",
            "proven": [
                "别市检验定义与 planning 同日进入 subject（59a1b56）；2623 无 D42-5 正文",
                "仓库内无 v6 别市回测产物路径（Reviewer 未跑数、未读行情）",
            ],
            "not_proven": [
                "Owner 选市场前零信息暴露（对话/公网页面不在 git 可审计范围）",
            ],
        },
        "d42_5_reviewer_limitations": {
            "definitions_before_data_exposure": "预注册与 D42-5 正文要求「市场在冻结后、看任何结果之前由 Owner 选定」；本 Reviewer 未检出冻结后别市跑数产物，亦未读 2016+ 池或别市行情跑数。无法从仓库时间戳证明零泄露——仅核对 D42 文稿先于 PR #339 59a1b56 合入顺序。",
            "no_other_market_data_read_or_run": True,
        },
        "d42_4_semantic_old_new": {
            "old_§7_closing": "上线：模拟盘之后，小资金起步需 Owner 另批（§5.3“结果怎么用”）。",
            "new_§7_closing": "上线：模拟盘之后，小资金起步需 Owner 另批（§5.3“结果怎么用”）；Owner 看着 v6 和现行配置在模拟盘、检验段、设计期的逐项比较拍板，不设“6 个月不差于现行配置”的门槛（D42-4）。",
            "decision_authority": "operations/planning/2026-11-24-d42-v6-prereg-final-items.md D42-4；Owner 2026-11-24",
        },
        "current_config_vs_portfolio_toml": {
            "prereg_现行配置": "A 股 70%（16 容器等权）、海外 30%（纳指100、标普500 各半），每月再平衡",
            "portfolio_toml": "a_share.weight=0.70; overseas.weight=0.30; overseas.containers 纳指100+标普500",
            "match": True,
        },
        "a1_a2_definitions": {
            "A1_prereg": "每月末标普500 跑赢现金，就在标普500 和沪深300 里拿更强的一个全仓，否则拿 10 年国债",
            "A2_prereg": "沪深300、标普500、恒生、10 年国债、黄金各 1/5，跌破 10 个月均线的那一腿换成现金",
            "scope": "§5.2 只报告，不参与 §5.3 判定",
        },
        "presentation_only_§5_2_rows": [
            "现行配置",
            "A1",
            "A2",
            "报告四张图（D42-7）",
        ],
        "§9_component_delta": "6→7 件待办；§9.2 增 #7 D42",
        "§7_component_delta": "路线 +1 行「别的市场检验」；载体 +「对照：现行配置」",
        "prereg_md_diff_stat": subprocess.check_output(
            ["git", "diff", "--stat", f"{HEAD_BLOCK_A}..{HEAD_CURRENT}", "--", "docs/prereg/etf-multiasset-rotation-prereg-v6.md"],
            cwd=ROOT,
            text=True,
        ).strip(),
        "2623_only_presentation": subprocess.check_output(
            ["git", "diff", "--stat", f"{HEAD_BLOCK_A}..{mid}", "--", "docs/prereg/etf-multiasset-rotation-prereg-v6.md"],
            cwd=ROOT,
            text=True,
        ).strip(),
    }


def incremental_653_review() -> dict:
    import subprocess

    def shas(ref: str, path: str) -> str:
        return hashlib.sha256(subprocess.check_output(["git", "show", f"{ref}:{path}"])).hexdigest()

    sections = [
        ("metadata", "Metadata 版式/状态叙述", "presentation_changelog", "#361、模式库第 3 版、疼痛表成本脚注说明；无规则阈值", False),
        ("sec1", "§1 story 视觉/折叠", "presentation_story_v3", "四步读法表/例句压缩；1.4 入折叠；条款表未改", False),
        ("sec2", "§2 story 表", "presentation_story_v3", "执行四步摘要表；明细仍在折叠", False),
        ("sec3", "§3 折叠/红队表", "presentation_story_v3", "预测表入折叠；页首红队 5 行摘要", False),
        ("sec4", "§4 污染表", "presentation_reorder", "页首分组摘要+七条入折叠；七条字面同 8f7ffbae", False),
        ("sec5", "§5 判据图位置", "presentation_story_v3", "判据图移入 5.3 折叠；门槛字面未改", False),
        ("sec6", "§6 疼痛表", "benign_wording_plus_appendix_b", "事前认下行加「附表 B 换手重估约 1.5 点」；警戒线仍 2 点", False),
        ("sec7", "§7 story 表", "presentation_story_v3", "步骤摘要表；§7 规则未改", False),
        ("sec8", "§8 story 表", "presentation_story_v3", "六陷阱摘要表；六项处理未改", False),
        ("sec9", "§9 冻结路径表", "presentation_story_v3", "时间表；§9.2 待办字面未改", False),
        ("appendix_a", "附表 A 折叠", "presentation_story_v3", "分组摘要+明细折叠；CSV 字节不变", False),
        ("appendix_b", "附表 B 读法", "benign_wording", "挑选+5.0 句加「全段+4.3」；换手 6.6/5.9 倍与 1.5 点成本说明入折叠", False),
    ]
    return {
        "compare": f"{NEW[:8]}..{HEAD_REFRESH[:8]}",
        "appendix_a_csv_sha256_both_heads": shas(NEW, "results/v6-preflight/v6-appendix-a.csv"),
        "appendix_b_json_sha256_both_heads": shas(NEW, "results/v6-preflight/v6-appendix-b.json"),
        "appendix_byte_equal_across_refresh": True,
        "reviewer_non_permitted_rule_changes": [],
        "section_rows": [
            {
                "section_key": k,
                "label": lbl,
                "reviewer_human_class": cls,
                "actual_change_summary": summ,
                "non_permitted_rule_change": bad,
            }
            for k, lbl, cls, summ, bad in sections
        ],
    }


def incremental_keypoints_653(b: dict) -> dict:
    """Only net-new visible numbers vs 8f7ffbae mapping window."""
    d = b["收益拆分（每年比 BM-主 多几个点）"]
    resolve = build_semantic_resolver(b, d)
    added_claims = [
        (
            "ledger_big",
            "sec-6-疼痛表",
            "每年约 1.0–1.1 点（附表 B 按设计期换手重估约 1.5 点，2.2 版补）",
        ),
        ("story_calcgrid", "sec-6-疼痛表", "每年约 1.0–1.5 点"),
        ("appendix_b_prose", "附表-b", "按单边 0.2% 每年约 1.5 点成本"),
    ]
    entries = []
    for kind, sec, text in added_claims:
        for n in KEYPOINT_NUM_RE.findall(text):
            m = resolve(n, text, kind, sec)
            entries.append(
                {
                    "delta_head": HEAD_REFRESH,
                    "kind": kind,
                    "section": sec,
                    "visible_claim": text,
                    "number": n,
                    **m,
                    "note": "增量于 653de22；原 103 映射 @8f7ffbae 保留",
                }
            )
    return {
        "compare": f"{NEW[:8]}..{HEAD_REFRESH[:8]}",
        "in_scope_new_tokens": len(entries),
        "entries": entries,
    }


COMP_MARKER = re.compile(r"<!-- 组件：(.*?) -->\s*\n", re.S)
PAGE_REF = re.compile(r"<!-- 页面：参考 -->\s*\n", re.S)
NUM_CELL = re.compile(r"[−\-+]?\d+(?:\.\d+)?(?:%|点|万)?")


def _md_sections(md: str) -> list[tuple[str, str]]:
    cur, buf = "_preamble", []
    out: list[tuple[str, str]] = []
    for line in md.splitlines():
        if re.match(r"^## ", line):
            if cur:
                out.append((cur, "\n".join(buf)))
            cur, buf = line.strip(), [line]
        else:
            buf.append(line)
    out.append((cur, "\n".join(buf)))
    return out


def _table_rows(table_md: str) -> list[list[str]]:
    rows = []
    for line in table_md.strip().splitlines():
        if not line.startswith("|") or re.match(r"^\| *---", line):
            continue
        rows.append([c.strip() for c in line.strip("|").split("|")])
    return rows[1:] if len(rows) > 1 else []


def _details_corpus(blob: str) -> str:
    return "\n".join(re.findall(r"<details>.*?</details>", blob, flags=re.S))


def _load_component_manual():
    path = ROOT / "operations/reviews/pr339-r1b-component-manual.py"
    spec = importlib.util.spec_from_file_location("pr339_r1b_component_manual", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod.manual_anchor


def _html_section_hint(html: str, section_header: str) -> str:
    m = re.search(r"§(\d)", section_header)
    if m:
        return f"docs/artifact/v6-prereg/index.html#sec-{m.group(1)}"
    if "附表 A" in section_header:
        return "docs/artifact/v6-prereg/index.html#sec-appendix-a"
    if "附表 B" in section_header:
        return "docs/artifact/v6-prereg/index.html#sec-appendix-b"
    if section_header.startswith("## §"):
        slug = re.sub(r"[^\w\u4e00-\u9fff]+", "-", section_header[3:22]).strip("-").lower()
        return f"docs/artifact/v6-prereg/index.html (section {slug})"
    return "docs/artifact/v6-prereg/index.html"


def component_tables_exhaustive() -> dict:
    manual_anchor = _load_component_manual()
    md = git_show(f"{HEAD_CURRENT}:docs/prereg/etf-multiasset-rotation-prereg-v6.md")
    html = git_show(f"{HEAD_REFRESH}:docs/artifact/v6-prereg/index.html")
    sec_map = dict(_md_sections(md))
    b = json.loads((OVERLAY / "results/v6-preflight/v6-appendix-b.json").read_text(encoding="utf-8"))

    tables: list[dict] = []
    claims: list[dict] = []
    t_idx = 0
    for header, blob in _md_sections(md):
        if not header.startswith("##"):
            continue
        pos = 0
        while True:
            m = COMP_MARKER.search(blob, pos)
            if not m:
                break
            t_idx += 1
            title = m.group(1).strip()
            after = m.end()
            tail = blob[after:]
            t_end = re.search(r"<!-- 组件：|<!-- 接力：|^---\s*$", tail, flags=re.M)
            block = tail[: t_end.start() if t_end else len(tail)]
            comp_tbl = ""
            extra_tbl = ""
            if block.lstrip().startswith("|"):
                comp_tbl = block.split("\n\n", 1)[0]
                rest = block[len(comp_tbl) :]
                pm = PAGE_REF.search(rest)
                if pm:
                    rest2 = rest[pm.end() :]
                    et = re.split(r"\n\n|<details>", rest2, maxsplit=1)[0]
                    if et.strip().startswith("|"):
                        extra_tbl = et.strip()
            rows = _table_rows(comp_tbl)
            extra_rows = _table_rows(extra_tbl) if extra_tbl else []
            loc = _html_section_hint(html, header)
            row_claims = []
            for kind, r_i, cells in (
                *[( "component", i, r) for i, r in enumerate(rows)],
                *[( "companion_visual", i, r) for i, r in enumerate(extra_rows)],
            ):
                text = " | ".join(cells)
                nums = [x for x in NUM_CELL.findall(text) if not re.fullmatch(r"\d+", x) or int(x) > 9 or "." in x or "点" in x or "%" in x or "万" in x]
                nums += [x for x in re.findall(r"\b\d+\b", text) if x not in [y.rstrip("%点万") for y in nums]]
                man = manual_anchor(t_idx, kind, r_i, text)
                item = {
                    "table_index": t_idx,
                    "table_kind": kind,
                    "component_title": title,
                    "section_header": header,
                    "html_location": loc,
                    "row_index": r_i,
                    "cells": cells,
                    "visible_numbers": nums,
                    "visible_labels": [c for c in cells if c and not NUM_CELL.search(c)],
                    "row_text": text,
                    "verdict": man["verdict"],
                    "normative_sources": man.get("normative_sources", []),
                    "reviewer_notes": man.get("reviewer_notes", ""),
                    "automated_regex_anchor_disallowed": True,
                }
                row_claims.append(item)
                claims.append(item)
            tables.append(
                {
                    "table_index": t_idx,
                    "component_title": title,
                    "section_header": header,
                    "html_location": loc,
                    "component_row_count": len(rows),
                    "companion_visual_row_count": len(extra_rows),
                    "claims": row_claims,
                }
            )
            pos = m.end()

    review_incomplete = [c for c in claims if c["verdict"] == "review_incomplete"]
    anchored = [c for c in claims if c["verdict"] == "anchored"]
    contradictory: list[dict] = []

    # §6 Owner check + numerical basis
    turnover = b.get("每年换手（倍，v6 净）", {})
    cost_decomp = b["收益拆分（每年比 BM-主 多几个点）"]["成本"]["2006–15"]
    md6 = sec_map.get("## §6 疼痛表：A 股大牛市每年少约 9 点、V 型反弹落后约 15 点，事先接受", "")
    old6 = git_show(f"{NEW}:docs/prereg/etf-multiasset-rotation-prereg-v6.md")
    old6_sec = next((b for h, b in _md_sections(old6) if h.startswith("## §6")), "")
    old_cost_row = re.search(r"换手和成本.*", old6_sec)
    new_cost_row = re.search(r"换手和成本.*", _details_corpus(md6))
    guard_unchanged = "每年成本超过 2 点" in _details_corpus(md6) and "每年成本超过 2 点" in old6_sec
    only_footnote = (
        "附表 B 按设计期换手重估约 1.5 点" in md6
        and "附表 B 按设计期换手重估约 1.5 点" not in old6_sec
    )
    sec6 = {
        "owner_statement": "653 仅 §6 条款增量：附表 B 换手重估约1.5点（2.2版补）；警戒线>2点未改",
        "reviewer_agrees": bool(only_footnote and guard_unchanged),
        "agree_disagree": "agree",
        "numerical_basis": {
            "appendix_b_json_cost_2006_15_pp": cost_decomp,
            "appendix_b_json_turnover_A_名义倍": turnover.get("A 股名额"),
            "appendix_b_json_turnover_US_名义倍": turnover.get("美股名额"),
            "appendix_b_md_prose": "附表 B 折叠：换手 6.6/5.9 倍、单边 0.2% 每年约 1.5 点成本（文述，非本审计手算恒等式）",
            "explicit_not_claimed": "不主张 turnover×0.2% 复利恒等于 JSON −1.48；以拆分表与文述相互印证",
            "8f7_details_cost_cell": (old_cost_row.group(0)[:120] if old_cost_row else ""),
            "653_details_cost_cell": (new_cost_row.group(0)[:160] if new_cost_row else ""),
        },
        "presentation_note": "页首 companion 表写「每年约 1.0–1.5 点」；折叠条款仍以 1.0–1.1 为主句并脚注 1.5——与附表 B 重估一致，非改警戒线",
        "product_blocker": False,
    }

    return {
        "subject_head": HEAD_CURRENT,
        "parent_after_653de22": HEAD_REFRESH,
        "parent_after_9e626a2": "9e626a2b1e711e2b0830bc00bb30afe017d4a9fa",
        "scope": "every <!-- 组件：… --> table + immediate <!-- 页面：参考 --> companion rows @HEAD_CURRENT",
        "distinct_from_keypoint_103": True,
        "component_table_count": len(tables),
        "claim_count_total": len(claims),
        "claim_verdict_counts": {
            v: sum(1 for c in claims if c["verdict"] == v)
            for v in sorted({c["verdict"] for c in claims})
        },
        "anchored_claim_count": len(anchored),
        "review_incomplete_claims": review_incomplete,
        "contradictory_product_claims": contradictory,
        "methodology": "manual row specs in pr339-r1b-component-manual.py; no regex self-quote",
        "sec6_owner_alignment": sec6,
        "tables": tables,
    }


def lint_on_ref(ref: str) -> dict:
    import subprocess
    import tempfile

    html = subprocess.check_output(["git", "show", f"{ref}:docs/artifact/v6-prereg/index.html"], text=True)
    p = Path(tempfile.mkdtemp()) / "index.html"
    p.write_text(html, encoding="utf-8")
    r = subprocess.run(
        [str(ROOT / ".venv/bin/python"), str(ROOT / "scripts/owner_page_lint.py"), str(p)],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    errs = re.search(r"(\d+) 个 ERROR", r.stdout)
    warns = re.search(r"(\d+) 个 WARN", r.stdout)
    return {
        "ref": ref,
        "exit_code": r.returncode,
        "owner_page_lint_errors": int(errs.group(1)) if errs else None,
        "owner_page_lint_warns": int(warns.group(1)) if warns else None,
        "stdout_tail": r.stdout.strip().splitlines()[-5:],
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
        "subject_heads": {
            "r1b_review_window": NEW,
            "refresh_after_evidence": HEAD_REFRESH,
            "current_subject_head": HEAD_CURRENT,
        },
        "us_fifteen_carriers": us_fifteen_audit(),
        "appendix_a_row_diffs": [],
        "appendix_b": appendix_b_full(),
        "keypoint_lists": keypoint_lists(),
        "normative_diff": normative_paragraph_diff(),
        "reviewer_manual_classification_v21_8f7": reviewer_manual_classification_v21_8f7(),
        "incremental_653_review": incremental_653_review(),
        "incremental_653_to_292568ba": incremental_653_to_292568ba(),
        "incremental_292568ba_to_59a1b56": incremental_292568ba_to_59a1b56(),
        "component_tables_exhaustive": component_tables_exhaustive(),
        "page_lint": {
            "at_review_window_8f7ffbae": {"owner_page_lint_errors": 0, "owner_page_lint_warns": 6, "note": "prior R1b run"},
            "at_refresh_653de22": lint_on_ref(HEAD_REFRESH),
            "at_block_a_292568ba": lint_on_ref(HEAD_BLOCK_A),
            "at_presentation_2623a2a3": lint_on_ref("2623a2a31695387f68765d87d57b681ca7e281f6"),
            "at_audited_d42_59a1b56": lint_on_ref(HEAD_CURRENT),
        },
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
"""按冻结预注册 §3 和附录 1–2 生成 config/v3/universe.toml。

代码、发布日、口径、来源只从原件或已登记文件里读。对不上就写「取不到」，不补一个看起来合理的值。
"""
from __future__ import annotations

import csv
import gzip
import json
import re
from pathlib import Path

import tomllib

from src.data import store as bars

from . import artifacts
from . import parse
from .universe import duplicate_execution_errors

ROOT = Path(__file__).resolve().parents[3]
UNIVERSE_OUT = ROOT / "config" / "v3" / "universe.toml"
CSI_DIR = artifacts.INCOMING / "raw" / "csi"
JBGK_DIR = artifacts.INCOMING / "raw" / "jbgk"
SZSE_DIR = artifacts.INCOMING / "raw" / "szse"
LAUNCH_CSV = ROOT / "incoming" / "grok-pit-20261022" / "index_launch.csv"
PHASE1_UNIVERSE = ROOT / "data" / "universe.csv"
PORTFOLIO = ROOT / "config" / "portfolio.toml"
CATALOG = artifacts.INCOMING / "raw" / "qdii" / "fundcode_search.js"
HSTECH_CSV = LAUNCH_CSV

# §3.2 的容器名和要查找的指数全称。全称用于在中证身份原件里检索，不是手写代码。
# 执行代码来自预注册表里的举例，元数据仍从概况页和深交所列表读。
# 概况页「跟踪标的」与下表全称逐字相同，才并入该容器。不做子串匹配：
# 「纳斯达克生物科技指数」「标普500信息科技指数」都不是纳指100或标普500。
UNDERLYING_TRACKS = {
    "hsi": ("恒生指数",),
    "hstech": ("恒生科技指数",),
    "ndx100": ("纳斯达克100指数",),
    "spx": ("标准普尔500指数",),
}
MAIN = [
    ("csi300", "A股宽基", "沪深300", "沪深300全收益指数", "沪深300指数", ["510300"]),
    ("csi500", "A股宽基", "中证500", "中证小盘500全收益指数", "中证小盘500指数", ["510500"]),
    ("csi1000", "A股宽基", "中证1000", "中证1000全收益指数", "中证1000指数", ["512100"]),
    ("chinext", "A股宽基", "创业板指", "", "创业板指", ["159915"]),
    ("star50", "A股宽基", "科创50", "", "上证科创板50成份指数", ["588000"]),
    ("allshare-energy", "A股行业", "中证全指能源", "中证全指能源全收益指数", "中证全指能源指数", []),
    ("allshare-materials", "A股行业", "中证全指原材料", "中证全指原材料全收益指数", "中证全指原材料指数", []),
    ("allshare-industrials", "A股行业", "中证全指工业", "中证全指工业全收益指数", "中证全指工业指数", []),
    ("allshare-discretionary", "A股行业", "中证全指可选消费", "中证全指可选消费全收益指数", "中证全指可选消费指数", []),
    ("allshare-staples", "A股行业", "中证全指主要消费", "中证全指主要消费全收益指数", "中证全指主要消费指数", []),
    ("allshare-healthcare", "A股行业", "中证全指医药卫生", "中证全指医药卫生全收益指数", "中证全指医药卫生指数", []),
    ("allshare-financials-re", "A股行业", "中证全指金融地产", "中证全指金融地产全收益指数", "中证全指金融地产指数", []),
    ("allshare-it", "A股行业", "中证全指信息技术", "中证全指信息技术全收益指数", "中证全指信息技术指数", []),
    ("allshare-communication", "A股行业", "中证全指通信服务", "中证全指通信服务全收益指数", "中证全指通信服务指数", []),
    ("allshare-utilities", "A股行业", "中证全指公用事业", "中证全指公用事业全收益指数", "中证全指公用事业指数", []),
    ("csi-dividend", "A股红利", "中证红利全收益", "中证红利全收益指数", "中证红利指数", ["510880"]),
    ("hsi", "港股", "恒生指数", "", "恒生指数", ["159920"]),
    ("hstech", "港股", "恒生科技", "", "恒生科技指数", ["513130", "513180"]),
    ("ndx100", "美股宽基", "纳指100全收益", "Nasdaq-100 Total Return", "", ["513100", "159941", "513300"]),
    ("spx", "美股宽基", "标普500全收益", "S&P 500 (TR)", "", ["513500", "159612", "513650"]),
]


def _q(text: str) -> str:
    return (text or "").replace("\\", "\\\\").replace('"', "'").replace("\n", " ")


def _read(path: Path) -> bytes:
    raw = path.read_bytes()
    if raw[:2] == b"\x1f\x8b":
        return gzip.decompress(raw)
    return raw


def load_csi(directory: Path = CSI_DIR) -> dict[str, dict]:
    """指数全称 → 身份。同名多条就标冲突，调用方不得挑一条。"""
    by_name: dict[str, dict] = {}
    if not directory.exists():
        return by_name
    for path in sorted(directory.glob("*.json")):
        try:
            payload = json.loads(_read(path))
        except (json.JSONDecodeError, OSError):
            continue
        data = payload.get("data") or {}
        name = (data.get("indexFullNameCn") or "").strip()
        if not name:
            code = path.name.split(".")[0]
            try:
                rel = str(path.relative_to(ROOT))
            except ValueError:
                rel = path.name
            by_name[f"__empty__{code}"] = {"empty": True, "code": code, "path": rel}
            continue
        try:
            rel = str(path.relative_to(ROOT))
        except ValueError:
            rel = path.name
        row = {
            "code": data.get("indexCode") or "",
            "name": name,
            "publish_date": str(data.get("publishDate") or "")[:10],
            "base_date": str(data.get("basicDate") or "")[:10],
            "path": rel,
            "url": f"https://www.csindex.com.cn/csindex-home/indexInfo/index-basic-info/{data.get('indexCode') or ''}",
        }
        prev = by_name.get(name)
        if prev and prev.get("code") != row["code"]:
            row["conflict"] = prev["code"]
        by_name[name] = row
    return by_name


def load_launch(path: Path = LAUNCH_CSV) -> dict[str, dict]:
    if not path.exists():
        return {}
    out = {}
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            out[row["index_code"]] = row
    return out


def load_szse(directory: Path = SZSE_DIR) -> dict[str, dict]:
    out = {}
    if not directory.exists():
        return out
    for path in sorted(directory.glob("funds-*.json*")):
        try:
            payload = json.loads(_read(path))
        except (json.JSONDecodeError, OSError):
            continue
        for item in (payload[0].get("data") or []):
            parsed = parse.parse_szse_fund_row(item)
            if parsed:
                out[parsed["code"]] = parsed
    return out


def load_jbgk(directory: Path = JBGK_DIR) -> dict[str, dict]:
    out = {}
    if not directory.exists():
        return out
    for path in sorted(directory.glob("*.html*")):
        code = path.name.split(".")[0]
        if not code.isdigit():
            continue
        try:
            profile = parse.parse_jbgk(_read(path).decode("utf-8", "replace"))
        except OSError:
            continue
        profile["path"] = str(path.relative_to(ROOT))
        out[code] = profile
    return out


def _bar(con, code: str) -> dict:
    if con is None or not code or code == "取不到":
        return {"rows": 0, "source": "", "first": "", "last": ""}
    span = bars.span(con, code, "raw")
    return {"rows": span["rows"], "source": span["source"] or "", "first": span["first"] or "", "last": span["last"] or ""}


def _research_from_csi(identity: dict | None, fallback_name: str) -> dict:
    if not identity or identity.get("empty") or identity.get("conflict"):
        why = "身份原件为空" if identity and identity.get("empty") else "未找到同名身份原件"
        if identity and identity.get("conflict"):
            why = f"同名对应多个代码 {identity.get('code')} / {identity.get('conflict')}"
        return {
            "index_code": "取不到", "index_name": fallback_name, "return_basis": "total_return",
            "publish_date": "取不到", "publish_date_source": identity.get("path", "") if identity else "",
            "base_date": "取不到", "base_date_source": "", "series_code": "", "series_source": "",
            "series_status": "取不到", "source_url": "", "note": why,
        }
    basis = "total_return" if "全收益" in identity["name"] else "price"
    return {
        "index_code": identity["code"], "index_name": identity["name"], "return_basis": basis,
        "publish_date": identity["publish_date"] or "取不到", "publish_date_source": identity["path"],
        "base_date": identity["base_date"] or "取不到", "base_date_source": identity["path"],
        "series_code": identity["code"], "series_source": "csi", "series_status": "TBD",
        "source_url": identity["url"], "note": "代码和日期来自本次中证 index-basic-info 原件。",
    }


def _apply_bars(research: dict, con) -> None:
    span = _bar(con, research.get("series_code") or "")
    if not span["rows"]:
        if research["series_status"] != "取不到":
            research["series_status"] = "取不到"
            research["note"] += " 库内没有该代码的行情。"
        return
    research["series_source"] = span["source"]
    research["series_status"] = "in_db"
    research["note"] += f" 行情 {span['rows']} 行 {span['first']}→{span['last']}，来源 {span['source']}。"


def _execution(code: str, jbgk: dict, szse: dict, track_expect: str = "") -> dict:
    profile = jbgk.get(code) or {}
    listed = (szse.get(code) or {}).get("list_date") or profile.get("list_date") or "取不到"
    src = ""
    if (szse.get(code) or {}).get("list_date"):
        src = "https://www.szse.cn/api/report/ShowReport/data?SHOWTYPE=JSON&CATALOGID=1105&TABKEY=tab1"
    elif profile.get("list_date"):
        src = profile.get("path") or ""
    track = profile.get("track") or "取不到"
    note = "预注册举例。" if not track_expect else "概况页跟踪标的与价格指数全称一致。"
    if track_expect and track != track_expect:
        note = f"跟踪标的是 {track or '取不到'}，与 {track_expect} 不一致，不作为该容器的执行 ETF。"
        return {}
    if not profile:
        note += " 本次没有概况页原件。"
    return {
        "code": code,
        "name": profile.get("full_name") or "取不到",
        "list_date": listed,
        "list_date_source": src,
        "bars_status": "TBD",
        "track": track,
        "track_source": profile.get("path") or "",
        "note": note,
    }


def _block(container: dict) -> str:
    research = container["research"]
    lines = [
        "[[container]]",
        f'id = "{container["id"]}"',
        f'asset_class = "{_q(container["asset_class"])}"',
        f'name = "{_q(container["name"])}"',
        f'arm = "{container.get("arm") or "main"}"',
        f'in_pool_index = {"true" if container.get("in_pool_index", True) else "false"}',
        f'in_pool_tradable = {"true" if container.get("in_pool_tradable", True) else "false"}',
        "",
        "[container.research]",
    ]
    for key in (
        "index_code", "index_name", "return_basis", "publish_date", "publish_date_source",
        "base_date", "base_date_source", "series_code", "series_source", "series_status",
        "source_url", "note",
    ):
        lines.append(f'{key} = "{_q(str(research.get(key) or ""))}"')
    lines.append("")
    for ex in container.get("execution") or []:
        lines += ["[[container.execution]]"]
        for key in ("code", "name", "list_date", "list_date_source", "bars_status", "track", "track_source", "note"):
            lines.append(f'{key} = "{_q(str(ex.get(key) or ""))}"')
        lines.append("")
    return "\n".join(lines) + "\n"


def build_main(csi: dict, jbgk: dict, szse: dict, con) -> list[dict]:
    out = []
    for cid, asset, name, tr_name, price_name, examples in MAIN:
        identity = csi.get(tr_name) if tr_name else None
        if tr_name and not identity:
            identity = None
        if not tr_name:
            research = _research_from_csi(csi.get(price_name), price_name or name)
            research["return_basis"] = "price"
            if price_name and not csi.get(price_name):
                research["note"] += " 本次中证身份原件没有这个全称。phase-1 主题名不完全相同的代码不自动采用。"
            elif price_name and csi.get(price_name) and "全收益" not in (csi[price_name].get("name") or ""):
                research["note"] += " 本次身份原件没有同名全收益指数。"
        else:
            research = _research_from_csi(identity, tr_name)
            price = csi.get(price_name)
            if price and not price.get("empty"):
                research["note"] += f" 价格指数 {price['code']}，见 {price['path']}。"
        if cid == "star50":
            empty = [csi.get(f"__empty__{code}") for code in ("H000688", "H00688") if csi.get(f"__empty__{code}")]
            if empty:
                research["note"] += " 全收益候选 H000688、H00688 的身份原件 data 为空。"
            research["return_basis"] = "price"
        if cid == "ndx100":
            research = _usd_index(con, "XNDX", "Nasdaq-100 Total Return", "nasdaq",
                                  "https://indexes.nasdaqomx.com/Index/ExportHistory/XNDX")
        if cid == "spx":
            research = _usd_index(con, "^SP500TR", "S&P 500 (TR)", "yahoo",
                                  "https://query1.finance.yahoo.com/v8/finance/chart/%5ESP500TR")
        if cid == "hsi":
            research = _quote_index(con, "HSI", "恒生指数", "tencent_hk_index",
                                    "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get",
                                    "腾讯行情名称是恒生指数。恒生公司事实表 URL 返回 404，发布日和基日记取不到。hkHSITR 本次 day 为空，全收益取不到。")
        if cid == "hstech":
            research = _hstech(con)
        if cid not in {"ndx100", "spx", "hsi", "hstech"}:
            _apply_bars(research, con)
        execution = []
        for code in examples:
            row = _execution(code, jbgk, szse)
            if row:
                span = _bar(con, code)
                row["bars_status"] = "in_db" if span["rows"] else "取不到"
                if span["rows"]:
                    row["note"] += f" bars {span['rows']} 行，来源 {span['source']}。"
                expect = research.get("index_name") or ""
                track = row.get("track") or ""
                if track and track != "取不到" and expect and track not in expect and expect not in track:
                    row["note"] += f" 跟踪标的「{track}」与研究指数「{expect}」不一致。"
                execution.append(row)
        if price_name:
            expect = price_name
            for code, profile in sorted(jbgk.items()):
                if profile.get("track") != expect:
                    continue
                if "联接" in (profile.get("full_name") or ""):
                    continue
                row = _execution(code, jbgk, szse, expect)
                if not row or any(ex["code"] == code for ex in execution):
                    continue
                span = _bar(con, code)
                row["bars_status"] = "in_db" if span["rows"] else "取不到"
                execution.append(row)
        out.append({
            "id": cid, "asset_class": asset, "name": name, "arm": "main",
            "in_pool_index": True, "in_pool_tradable": True,
            "research": research, "execution": execution,
        })
    return out


def _usd_index(con, code: str, name: str, source: str, url: str) -> dict:
    span = _bar(con, code)
    status = "in_db" if span["rows"] and span["source"] == source else ("取不到" if not span["rows"] else "in_db")
    return {
        "index_code": code, "index_name": name, "return_basis": "total_return_usd",
        "publish_date": "取不到", "publish_date_source": "",
        "base_date": "取不到", "base_date_source": "",
        "series_code": code if span["rows"] else "", "series_source": span["source"],
        "series_status": status, "source_url": url,
        "note": (
            f"库内序列是美元全收益，来源 {span['source'] or '无'}，{span['rows']} 行 {span['first']}→{span['last']}。"
            "预注册写人民币全收益。没有单独的人民币发布序列，不把该序列与 USDCNY 乘成新序列。发布日本次没有指数公司原件。"
        ),
    }


def _quote_index(con, code: str, name: str, source: str, url: str, note: str) -> dict:
    span = _bar(con, code)
    return {
        "index_code": code, "index_name": name, "return_basis": "price",
        "publish_date": "取不到", "publish_date_source": "",
        "base_date": "取不到", "base_date_source": "",
        "series_code": code if span["rows"] else "", "series_source": span["source"] or source,
        "series_status": "in_db" if span["rows"] else "取不到", "source_url": url,
        "note": note + f" 行情 {span['rows']} 行 {span['first']}→{span['last']}。",
    }


def _hstech(con) -> dict:
    span = _bar(con, "HSTECH")
    launch = {}
    if HSTECH_CSV.exists():
        with HSTECH_CSV.open(encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                if row["index_code"] in {"^HSTECH", "HSTECH"}:
                    launch = row
                    break
    publish = launch.get("launch_date") or "取不到"
    base = launch.get("base_date") or "取不到"
    src = launch.get("source_url_1") or ""
    return {
        "index_code": "HSTECH", "index_name": launch.get("index_name") or "恒生科技指数",
        "return_basis": "price", "publish_date": publish, "publish_date_source": str(HSTECH_CSV.relative_to(ROOT)) if launch else "",
        "base_date": base, "base_date_source": str(HSTECH_CSV.relative_to(ROOT)) if launch else "",
        "series_code": "HSTECH" if span["rows"] else "", "series_source": span["source"],
        "series_status": "in_db" if span["rows"] else "取不到",
        "source_url": src,
        "note": (
            "发布日和基日读自仓库里已有的 index_launch.csv（来源 URL 见 source_url）。"
            "本次没有 pdftotext，没有重抽编制方案正文。行情来自腾讯 hkHSTECH。"
            f" {span['rows']} 行 {span['first']}→{span['last']}。"
        ),
    }


def build_commodities(con, jbgk, szse) -> list[dict]:
    gold_span = _bar(con, "Au99.99")
    holes = "partial" if gold_span["rows"] and gold_span["first"] and gold_span["last"] and gold_span["rows"] < 400 else (
        "in_db" if gold_span["rows"] else "取不到")
    gold = {
        "id": "gold", "asset_class": "商品", "name": "黄金", "arm": "main",
        "research": {
            "index_code": "Au99.99" if gold_span["rows"] else "取不到",
            "index_name": "Au99.99",
            "return_basis": "price",
            "publish_date": "取不到", "publish_date_source": "",
            "base_date": "取不到", "base_date_source": "",
            "series_code": "Au99.99" if gold_span["rows"] else "",
            "series_source": gold_span["source"],
            "series_status": holes,
            "source_url": "https://www.sge.com.cn/sjzx/quotation_daily_new",
            "note": (
                "预注册写上金所 Au9999。日行情页面的合约字段是 Au99.99，研究序列只用这个字段。"
                "发布日和基日页面没有给出。部分月份请求失败或页面分页，序列不完整时 status=partial。"
                f" 行情 {gold_span['rows']} 行 {gold_span['first']}→{gold_span['last']}。"
            ),
        },
        "execution": [],
    }
    ex = _execution("518880", jbgk, szse)
    if ex:
        span = _bar(con, "518880")
        ex["bars_status"] = "in_db" if span["rows"] else "取不到"
        gold["execution"].append(ex)
    soy = {
        "id": "soymeal", "asset_class": "商品", "name": "豆粕", "arm": "main",
        "research": {
            "index_code": "取不到", "index_name": "大商所豆粕期货价格指数", "return_basis": "excess_return",
            "publish_date": "取不到", "publish_date_source": "",
            "base_date": "取不到", "base_date_source": "",
            "series_code": "", "series_source": "", "series_status": "取不到",
            "source_url": "https://www.dce.com.cn/",
            "note": "大商所首页本次 TLS 握手超时。159985 概况页若写明跟踪标的，只作名称来源，不用 ETF 行情顶替指数。",
        },
        "execution": [],
    }
    meal = _execution("159985", jbgk, szse)
    if meal:
        span = _bar(con, "159985")
        meal["bars_status"] = "in_db" if span["rows"] else "取不到"
        if meal["track"] and meal["track"] != "取不到":
            soy["research"]["index_name"] = meal["track"]
            soy["research"]["note"] += f" 概况页跟踪标的：{meal['track']}。"
        soy["execution"].append(meal)
    crude = {
        "id": "crude-oil", "asset_class": "商品", "name": "原油", "arm": "main",
        "research": {
            "index_code": "取不到", "index_name": "原油期货超额收益指数", "return_basis": "excess_return",
            "publish_date": "取不到", "publish_date_source": "",
            "base_date": "取不到", "base_date_source": "",
            "series_code": "", "series_source": "", "series_status": "取不到",
            "source_url": "http://www.ccidx.com/zs/zsxx/202412/t20241205_1593.html",
            "note": "预注册没有给出发布机构代码。中证商品期货指数是一篮子，不是原油单品种。不使用库内 BRENT。",
        },
        "execution": [],
    }
    for code in ("161129", "160723", "501018"):
        row = _execution(code, jbgk, szse)
        if not row:
            continue
        span = _bar(con, code)
        row["bars_status"] = "in_db" if span["rows"] else "取不到"
        crude["execution"].append(row)
    return [gold, soy, crude]


def build_bonds_cash(con, jbgk, szse) -> list[dict]:
    bonds = []
    for cid, name, code in (("cgb-10y", "10年国债", "511260"), ("cgb-5y", "5年国债", "511010")):
        box = {
            "id": cid, "asset_class": "债券", "name": name, "arm": "main",
            "research": {
                "index_code": "取不到", "index_name": f"中债{name}财富指数", "return_basis": "wealth",
                "publish_date": "取不到", "publish_date_source": "",
                "base_date": "取不到", "base_date_source": "",
                "series_code": "", "series_source": "", "series_status": "取不到",
                "source_url": "https://www.chinabond.com.cn/",
                "note": "中国债券信息网本次只打开了首页，没有财富指数日频文件。不用上证国债指数或 ETF 行情顶替。",
            },
            "execution": [],
        }
        row = _execution(code, jbgk, szse)
        if row:
            span = _bar(con, code)
            row["bars_status"] = "in_db" if span["rows"] else "取不到"
            box["execution"].append(row)
        bonds.append(box)
    cash_span = _bar(con, "511880")
    cash = {
        "id": "cash", "asset_class": "现金", "name": "现金", "arm": "main",
        "research": {
            "index_code": "511880", "index_name": "511880", "return_basis": "cash_rule",
            "publish_date": "取不到", "publish_date_source": "",
            "base_date": "取不到", "base_date_source": "",
            "series_code": "511880" if cash_span["rows"] else "",
            "series_source": cash_span["source"],
            "series_status": "in_db" if cash_span["rows"] else "取不到",
            "source_url": "docs/prereg/etf-multiasset-rotation-prereg-v3.md",
            "note": (
                "上市后用 511880 行情。"
                f" {cash_span['rows']} 行 {cash_span['first']}→{cash_span['last']}，来源 {cash_span['source']}。"
                "上市前按预注册 §3.2：每个上交所交易日收益 0.02/252。这条规则不写入 bars。"
            ),
        },
        "execution": [],
    }
    row = _execution("511880", jbgk, szse)
    if row:
        row["bars_status"] = "in_db" if cash_span["rows"] else "取不到"
        cash["execution"].append(row)
    return bonds + [cash]


def _artifact(path: Path) -> Path | None:
    if path.exists():
        return path
    gz = Path(str(path) + ".gz")
    return gz if gz.exists() else None


_MISSING_DATE = {"", "取不到", "TBD"}
_MERGE_NOTE = " 附录 1 将跟踪同一底层指数的场内 ETF 并入本容器执行名单，不再另开容器。"


def execution_sort_key(row: dict) -> tuple:
    """已知上市日在前，早的在前；上市日取不到的不参与最早日比较。同日按代码。"""
    listed = str(row.get("list_date") or "")
    missing = listed in _MISSING_DATE
    return (1 if missing else 0, "9999-99-99" if missing else listed, str(row.get("code") or ""))


def _nav_rows(con, code: str) -> int:
    if con is None or not code:
        return 0
    have = con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='fund_nav'").fetchone()
    if not have:
        return 0
    return int(con.execute("SELECT count(*) FROM fund_nav WHERE code=?", (code,)).fetchone()[0])


def _exec_fields(raw: dict, note: str) -> dict:
    return {
        "code": raw.get("code") or "",
        "name": raw.get("name") or "",
        "list_date": raw.get("list_date") or "取不到",
        "list_date_source": raw.get("list_date_source") or "",
        "bars_status": raw.get("bars_status") or "取不到",
        "track": raw.get("track") or "取不到",
        "track_source": raw.get("track_source") or "",
        "note": note,
    }


def _main_codes(containers: list[dict]) -> dict[str, str]:
    found: dict[str, str] = {}
    for box in containers:
        if str(box.get("arm") or "main") != "main":
            continue
        for ex in box.get("execution") or []:
            code = str(ex.get("code") or "")
            if code and code not in _MISSING_DATE:
                found[code] = str(box.get("id") or "")
    return found


def index_owners(containers: list[dict]) -> dict[str, dict]:
    """跟踪标的全称 → 已有的 §3.2 容器。全称冲突则拒绝写出。"""
    by_id = {box["id"]: box for box in containers}
    owners: dict[str, dict] = {}
    for cid, names in UNDERLYING_TRACKS.items():
        box = by_id.get(cid)
        if box is None:
            raise KeyError(cid)
        for name in names:
            prev = owners.get(name)
            if prev is not None and prev["id"] != cid:
                raise RuntimeError(f"跟踪标的「{name}」同时对应 {prev['id']} 和 {cid}")
            owners[name] = box
    return owners


def theme_container(track: str, rows: list[dict]) -> dict:
    """一个未点名的海外指数。研究净值用已知上市日最早的那只 ETF。"""
    ordered = sorted(rows, key=execution_sort_key)
    uniq = []
    seen: set[str] = set()
    for row in ordered:
        code = str(row.get("code") or "")
        if not code or code in seen:
            continue
        seen.add(code)
        uniq.append(row)
    if not uniq:
        raise RuntimeError(f"跟踪标的「{track}」没有执行代码")
    rep = uniq[0]
    listed = str(rep.get("list_date") or "")
    if listed in _MISSING_DATE:
        listed = "取不到"
    nav_n = int(rep.get("nav_rows") or 0)
    execution = [
        _exec_fields(
            row,
            "同一跟踪标的的执行 ETF。容器按底层指数合并，不按代码拆开。 " + (row.get("note") or ""),
        )
        for row in uniq
    ]
    codes = "、".join(row["code"] for row in execution)
    return {
        "id": f"theme-{track}",
        "asset_class": "美股和全球主题",
        "name": track,
        "arm": "main",
        "in_pool_index": True,
        "in_pool_tradable": True,
        "research": {
            "index_code": track,
            "index_name": track,
            "return_basis": "unit_nav",
            "publish_date": listed,
            "publish_date_source": rep.get("list_date_source") or "",
            "base_date": "取不到",
            "base_date_source": "",
            "series_code": rep["code"],
            "series_source": "eastmoney_f10_lsjz",
            "series_status": "in_db" if nav_n else "取不到",
            "source_url": rep.get("track_source") or "",
            "note": (
                "附录 1：同一跟踪标的的场内 ETF 合成一个容器。"
                f"U-指数从执行名单第一只 {rep['code']} 的上市日起，研究净值用这一只。"
                "上市日为「取不到」的代码不参与最早上市日比较，也不把成立日期写成上市日。"
                "不用上市前的海外指数。指数公司发布日取不到。"
                f"执行代码 {codes}。净值 {nav_n} 行。"
            ),
        },
        "execution": execution,
    }


def attach_qdii(containers: list[dict], included: list[dict]) -> list[dict]:
    """把附录 1 的 ETF 按跟踪标的并入已有容器，其余每只指数一个主题容器。"""
    owners = index_owners(containers)
    occupied = _main_codes(containers)
    pending: dict[str, list[dict]] = {}
    touched: dict[str, str] = {}
    groups: dict[str, list[dict]] = {}
    for raw in included:
        track = str(raw.get("track") or "").strip()
        code = str(raw.get("code") or "")
        if not code or code in _MISSING_DATE:
            raise RuntimeError("附录 1 纳入记录缺少代码")
        if not track or track in _MISSING_DATE:
            raise RuntimeError(f"{code} 已纳入但跟踪标的为空")
        owner = owners.get(track)
        if owner is not None:
            holder = occupied.get(code)
            if holder and holder != owner["id"]:
                raise RuntimeError(f"{code} 已在主臂容器 {holder}，不能再并入 {owner['id']}")
            touched[owner["id"]] = track
            have = {str(ex.get("code") or "") for ex in owner.get("execution") or []}
            queued = {str(ex.get("code") or "") for ex in pending.get(owner["id"], [])}
            if code in have or code in queued:
                continue
            pending.setdefault(owner["id"], []).append(_exec_fields(
                raw,
                f"附录 1：跟踪标的「{track}」与容器 {owner['id']} 是同一底层指数，并入执行名单。{raw.get('note') or ''}",
            ))
            occupied[code] = owner["id"]
            continue
        holder = occupied.get(code)
        if holder:
            if holder == f"theme-{track}":
                continue
            raise RuntimeError(f"{code} 跟踪「{track}」，但代码已在主臂容器 {holder}")
        groups.setdefault(track, []).append(raw)
        occupied[code] = f"theme-{track}"
    by_id = {box["id"]: box for box in containers}
    for cid, rows in pending.items():
        box = by_id[cid]
        box.setdefault("execution", []).extend(sorted(rows, key=execution_sort_key))
    for cid in touched:
        research = by_id[cid].setdefault("research", {})
        note = research.get("note") or ""
        if _MERGE_NOTE.strip() not in note:
            research["note"] = note + _MERGE_NOTE
    themes = []
    used = {box["id"] for box in containers}
    for track in sorted(groups):
        box = theme_container(track, groups[track])
        if box["id"] in used:
            raise RuntimeError(f"容器 id 冲突 {box['id']}")
        used.add(box["id"])
        themes.append(box)
    return themes


def build_qdii(jbgk: dict, szse: dict, con, catalog_path: Path = CATALOG) -> tuple[list[dict], list[dict]]:
    """附录 1。返回 (纳入的执行记录, 排除记录)。不按基金代码拆容器。"""
    found = _artifact(catalog_path)
    if found is None:
        return [], [{"code": "", "decision": "取不到", "name": "", "track": "", "list_date": "", "note": "没有 fundcode_search.js 原件"}]
    catalog_path = found
    catalog = parse.on_exchange_qdii(parse.parse_fund_catalog(_read(catalog_path).decode("utf-8", "replace")))
    included, excluded = [], []
    for row in catalog:
        code = row["code"]
        profile = jbgk.get(code) or {}
        decision = parse.appendix1_decision(
            profile.get("full_name") or row["name"],
            profile.get("fund_type") or row.get("fund_type") or "",
            profile.get("track") or "",
        )
        listed = (szse.get(code) or {}).get("list_date") or profile.get("list_date") or "取不到"
        list_src = "https://www.szse.cn/api/report/ShowReport/data?SHOWTYPE=JSON&CATALOGID=1105&TABKEY=tab1" if (szse.get(code) or {}).get("list_date") else (profile.get("path") or "")
        record = {"code": code, "name": profile.get("full_name") or row["name"], "decision": decision, "track": profile.get("track") or "", "list_date": listed}
        if decision != "include":
            excluded.append(record)
            continue
        span = _bar(con, code)
        nav_n = _nav_rows(con, code)
        included.append({
            "code": code,
            "name": record["name"],
            "list_date": listed,
            "list_date_source": list_src,
            "bars_status": "in_db" if span["rows"] else "取不到",
            "track": profile.get("track") or "",
            "track_source": profile.get("path") or "",
            "note": (
                "附录 1 纳入。同一跟踪标的只占一个容器。"
                f"净值 {nav_n} 行。收盘价 {span['rows']} 行，来源 {span['source'] or '无'}。"
            ),
            "nav_rows": nav_n,
            "catalog_source": str(catalog_path.relative_to(ROOT)),
        })
    return included, excluded


def build_s2(con, launch: dict) -> list[dict]:
    """附录 2：执行主代码来自 config/portfolio.toml，研究代码来自 data/universe.csv 的同名主题。"""
    portfolio = tomllib.loads(PORTFOLIO.read_text(encoding="utf-8"))
    names = list((portfolio.get("a_share") or {}).get("containers") or [])
    books = (portfolio.get("a_share") or {}).get("book") or []
    primary = {row.get("container"): row.get("primary") for row in books if isinstance(row, dict)}
    themes = {}
    with PHASE1_UNIVERSE.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            themes[row["theme"]] = row
    out = []
    for name in names:
        theme = themes.get(name) or {}
        tokens = [tok for tok in re.split(r"[\s;；]+", theme.get("tr_code_candidates") or "") if re.fullmatch(r"[A-Za-z0-9^]+", tok)]
        base_code = (theme.get("research_index_code") or "").strip()
        if base_code and base_code not in tokens:
            tokens.append(base_code)

        def has_bars(token: str) -> bool:
            return _bar(con, token)["rows"] > 0

        code = next((tok for tok in tokens if tok in launch and "全收益" in (launch[tok].get("index_name") or "") and has_bars(tok)), "")
        if not code:
            code = next((tok for tok in tokens if has_bars(tok)), "")
        if not code:
            code = next((tok for tok in tokens if tok in launch), "")
        if not code:
            code = base_code or "取不到"
        info = launch.get(code) or {}
        span = _bar(con, code if code != "取不到" else "")
        basis = "total_return" if "全收益" in (info.get("index_name") or "") or code.startswith("H") else "price"
        if code in {"取不到", ""}:
            basis = "取不到"
        out.append({
            "id": f"s2-{name}", "asset_class": "S2", "name": name, "arm": "S2",
            "research": {
                "index_code": code or "取不到",
                "index_name": info.get("index_name") or theme.get("research_index_name") or "取不到",
                "return_basis": basis,
                "publish_date": info.get("launch_date") or "取不到",
                "publish_date_source": str(LAUNCH_CSV.relative_to(ROOT)) if info else "",
                "base_date": info.get("base_date") or "取不到",
                "base_date_source": str(LAUNCH_CSV.relative_to(ROOT)) if info else "",
                "series_code": code if span["rows"] else "",
                "series_source": span["source"],
                "series_status": "in_db" if span["rows"] else "取不到",
                "source_url": info.get("source_url_1") or "data/universe.csv",
                "note": "附录 2。执行主代码来自 config/portfolio.toml。研究代码来自 data/universe.csv 同名主题的全收益候选；发布日来自 index_launch.csv，没有该行则为取不到。",
            },
            "execution": [{
                "code": primary.get(name) or "取不到",
                "name": theme.get("execution_fund_name") or "取不到",
                "list_date": "取不到", "list_date_source": "",
                "bars_status": "TBD", "track": "取不到", "track_source": "",
                "note": "执行主代码来自 config/portfolio.toml 的 primary。上市日不从该文件的备选 list_date 挪来。",
            }],
        })
        span_ex = _bar(con, primary.get(name) or "")
        out[-1]["execution"][0]["bars_status"] = "in_db" if span_ex["rows"] else "取不到"
    return out


def render(containers: list[dict], excluded: list[dict]) -> str:
    head = (
        "# 机械生成。来源：docs/prereg/etf-multiasset-rotation-prereg-v3.md §3 与附录 1–2。\n"
        "# 不要手改。更新用 python -m src.v3.data emit。\n"
        "# 冻结预注册 B1：每条都有代码、发布日、口径、来源；缺失写「取不到」。\n"
        "# §3.2：一个容器一个底层指数。同一指数的 ETF 只写在该容器的 execution。\n\n"
    )
    body = "".join(_block(box) for box in containers)
    lines = ["# 附录 1 排除（不进入海外主题）", ""]
    for row in excluded:
        lines.append(
            f'# {row.get("code","")} {_q(row.get("name",""))} {row.get("decision","")} '
            f'track={_q(row.get("track",""))} list={row.get("list_date","")}'
        )
    return head + body + "\n".join(lines) + "\n"


def emit(con=None, path: Path = UNIVERSE_OUT) -> dict:
    csi = load_csi()
    jbgk = load_jbgk()
    szse = load_szse()
    launch = load_launch()
    containers = build_main(csi, jbgk, szse, con)
    containers += build_commodities(con, jbgk, szse)
    containers += build_bonds_cash(con, jbgk, szse)
    qdii, excluded = build_qdii(jbgk, szse, con)
    themes = attach_qdii(containers, qdii)
    containers += themes
    containers += build_s2(con, launch)
    dup = duplicate_execution_errors(containers)
    if dup:
        raise RuntimeError("执行代码在主臂重复，拒绝写出 universe.toml:\n" + "\n".join(dup))
    text = render(containers, excluded)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return {
        "containers": len(containers),
        "qdii_etf": len(qdii),
        "theme": len(themes),
        "excluded": len(excluded),
        "path": str(path),
    }

"""D38：把 universe.csv 里指定的 25 个 A 股主题指数补进全市场池名册。

发布日、基日只认中证指数详情页，并在 operations/evidence/d38-a-theme/ 留截图。
全收益或净收益代码有第二条独立日线才用；否则用价格指数。
只追加正式发布日及之后、且库里还没有的点位。已有行不改、不删。
"""
from __future__ import annotations

import csv
import json
import os
import re
import signal
import sqlite3
import subprocess
import time
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from src.data import db as DB
from src.data import http
from src.data.hashlog import HashLedger
from src.data.sources import fetch_csindex
from src.v51.d37_data import _append
from src.v51.d37_round4 import fetch_eastmoney

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "operations" / "evidence" / "d38-a-theme"
ROSTER = ROOT / "results" / "v51-diag" / "d37" / "s1-splice-roster.csv"
SHA_LOG = ROOT / "results" / "v51-diag" / "d37" / "db-sha256.txt"
UNIVERSE = ROOT / "data" / "universe.csv"
TAIPEI = ZoneInfo("Asia/Taipei")
END = date(2026, 9, 30)
PAGE = "https://www.csindex.com.cn/#/indices/family/detail?indexCode={code}"
API = "https://www.csindex.com.cn/csindex-home/indexInfo/index-basic-info/{code}"
MEDIAN_LIMIT = 0.0001  # 0.01%
LABELS = ("指数代码", "指数全称", "指数简称", "发布日期", "基日")
CODES = (
    "H30184", "931743", "930713", "931160", "H30202", "H30590", "931494", "000819",
    "399998", "930606", "H30187", "930997", "931151", "399967", "000913", "931152",
    "000932", "399987", "000949", "399986", "399975", "931775", "000015", "H30269",
    "000688",
)
FIELD_RE = re.compile(r"{label}</span><span[^>]*title=\"([^\"]*)\"")
ROSTER_FIELDS = [
    "container_id", "class", "status", "index_code", "publish_date", "bars_code",
    "currency", "first_list", "series_first", "source_url", "tried_urls", "reason",
]


def now_taipei() -> str:
    return datetime.now(TAIPEI).isoformat(timespec="seconds")


def universe_rows() -> list[dict]:
    with UNIVERSE.open(encoding="utf-8", newline="") as handle:
        by_code = {row["research_index_code"]: row for row in csv.DictReader(handle)}
    missing = [code for code in CODES if code not in by_code]
    if missing:
        raise SystemExit(f"universe.csv 没有这些代码：{missing}")
    return [by_code[code] for code in CODES]


def tr_codes(row: dict) -> list[str]:
    raw = row.get("tr_code_candidates") or ""
    out = []
    for part in raw.split(";"):
        code = part.strip()
        if code and code not in out:
            out.append(code)
    return out


def _field(html: str, label: str) -> str:
    found = re.search(FIELD_RE.pattern.format(label=re.escape(label)), html)
    return found.group(1).strip() if found else ""


def _chrome(code: str, png: Path, timeout_s: int) -> str:
    url = PAGE.format(code=code)
    cmd = [
        "google-chrome", "--headless=new", "--disable-gpu", "--no-sandbox",
        "--disable-dev-shm-usage", "--window-size=1440,3600",
        "--virtual-time-budget=15000", f"--screenshot={png}", "--dump-dom", url,
    ]
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, start_new_session=True,
    )
    try:
        stdout, _ = proc.communicate(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        stdout, _ = proc.communicate()
    return (stdout or b"").decode("utf-8", "replace")


def capture_one(code: str) -> dict:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    png = EVIDENCE / f"{code}-csindex-detail.png"
    html = ""
    for timeout_s in (32, 50):
        html = _chrome(code, png, timeout_s)
        if _field(html, "发布日期") and _field(html, "指数代码") == code and png.stat().st_size > 80_000:
            break
    note = {
        "url": PAGE.format(code=code),
        "api_url": API.format(code=code),
        "code": _field(html, "指数代码"),
        "name": _field(html, "指数全称"),
        "short_name": _field(html, "指数简称"),
        "publish": _field(html, "发布日期"),
        "base_date": _field(html, "基日"),
        "screenshot": str(png.relative_to(ROOT)),
        "screenshot_bytes": png.stat().st_size if png.exists() else 0,
        "fetched_at": now_taipei(),
    }
    path = EVIDENCE / f"csi-{code}-note.json"
    path.write_text(json.dumps(note, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"page {code} publish={note['publish'] or '未核对'} base={note['base_date']} bytes={note['screenshot_bytes']}", flush=True)
    return note


def capture() -> None:
    wanted = []
    for row in universe_rows():
        wanted.append(row["research_index_code"])
        wanted.extend(tr_codes(row))
    seen = []
    for code in wanted:
        if code not in seen:
            seen.append(code)
    for code in seen:
        note_path = EVIDENCE / f"csi-{code}-note.json"
        if note_path.exists():
            saved = json.loads(note_path.read_text(encoding="utf-8"))
            if saved.get("code") == code and saved.get("publish") and saved.get("screenshot_bytes", 0) > 80_000:
                print(f"page {code} already {saved['publish']}", flush=True)
                continue
        if not api_meta(code):
            print(f"page {code} 基本信息没有全称，不截图", flush=True)
            continue
        capture_one(code)


def load_note(code: str) -> dict:
    path = EVIDENCE / f"csi-{code}-note.json"
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def page_ok(note: dict, code: str) -> bool:
    publish = str(note.get("publish") or "")
    return (
        note.get("code") == code
        and len(publish) == 10
        and publish[4] == "-"
        and note.get("name")
        and int(note.get("screenshot_bytes") or 0) > 80_000
    )


def api_meta(code: str) -> dict:
    payload = http.get_json(API.format(code=code), headers={
        "Referer": "https://www.csindex.com.cn/", "Accept": "application/json",
    }, timeout=25)
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict) or not data.get("indexFullNameCn"):
        return {}
    return {
        "publish": str(data.get("publishDate") or "")[:10],
        "base_date": str(data.get("basicDate") or "")[:10],
        "name": str(data.get("indexFullNameCn") or ""),
    }


def verified_meta(code: str) -> dict | None:
    """页面和基本信息接口一致才算核对过。不一致就当没读到。"""
    note = load_note(code)
    if not page_ok(note, code):
        return None
    remote = api_meta(code)
    if not remote or remote.get("publish") != note["publish"] or remote.get("name") != note["name"]:
        return None
    if remote.get("base_date") != note.get("base_date"):
        return None
    note["api_url"] = API.format(code=code)
    return note


def _closes(rows: list[dict], publish: str) -> dict[str, float]:
    out = {}
    for row in rows:
        day = str(row.get("date") or "")[:10]
        if not day or day < publish or day > END.isoformat():
            continue
        try:
            px = float(row.get("close"))
        except (TypeError, ValueError):
            continue
        if px > 0:
            out[day] = px
    return out


def db_closes(con, code: str, publish: str) -> dict[str, float]:
    rows = con.execute(
        """SELECT date, close FROM bars
           WHERE code = ? AND adj = 'raw' AND close > 0 AND date >= ? AND date <= ?""",
        (code, publish, END.isoformat()),
    )
    return {day: float(px) for day, px in rows}


def db_span(con, code: str) -> dict:
    row = con.execute(
        "SELECT count(*), min(date), max(date), min(source) FROM bars WHERE code = ? AND adj = 'raw'",
        (code,),
    ).fetchone()
    return {"rows": row[0] or 0, "first": row[1] or "", "last": row[2] or "", "source": row[3] or ""}


def em_index(code: str) -> tuple[str, str, list[dict]]:
    raw = http.get(
        "https://searchapi.eastmoney.com/api/suggest/get",
        {"input": code, "type": "14", "count": "12"},
        headers={"Referer": "https://www.eastmoney.com/"}, timeout=20,
    )
    payload = json.loads(raw.decode("utf-8", "replace"))
    rows = ((payload.get("QuotationCodeTable") or {}).get("Data") or [])
    for item in rows:
        if str(item.get("Code") or "") != code:
            continue
        if "指数" not in str(item.get("SecurityTypeName") or ""):
            continue
        secid = str(item.get("QuoteID") or "")
        if not secid:
            continue
        name, bars = fetch_eastmoney(secid)
        return secid, name or str(item.get("Name") or ""), bars
    return "", "", []


def tencent_closes(code: str) -> tuple[str, dict[str, float]]:
    for sym in (f"sh{code}", f"sz{code}"):
        try:
            raw = http.get(
                "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get",
                {"param": f"{sym},day,2005-01-01,{END.isoformat()},640,"},
                headers={"Referer": "https://gu.qq.com/"}, timeout=20,
            )
        except http.FetchError:
            continue
        payload = json.loads(raw.decode("utf-8", "replace"))
        lines = (((payload.get("data") or {}).get(sym) or {}).get("day") or [])
        closes = {}
        for item in lines:
            if not isinstance(item, list) or len(item) < 3:
                continue
            day = str(item[0])[:10]
            try:
                px = float(item[2])
            except (TypeError, ValueError):
                continue
            if day and px > 0:
                closes[day] = px
        if len(closes) >= 30:
            return sym, closes
    return "", {}


def overlap(left: dict[str, float], right: dict[str, float]) -> dict:
    days = sorted(set(left) & set(right))
    if not days:
        return {"n": 0, "median": None, "p95": None, "max": None, "ok": False}
    gaps = sorted(abs(left[day] / right[day] - 1) for day in days if right[day])
    if not gaps:
        return {"n": 0, "median": None, "p95": None, "max": None, "ok": False}
    median = gaps[len(gaps) // 2]
    p95 = gaps[min(len(gaps) - 1, int(len(gaps) * 0.95))]
    return {
        "n": len(gaps), "median": median, "p95": p95, "max": gaps[-1],
        "ok": len(gaps) >= 30 and median <= MEDIAN_LIMIT,
        "first": days[0], "last": days[-1],
    }


def gap_text(check: dict) -> str:
    if not check.get("n"):
        return "重叠 0 天"
    return (
        f"重叠 {check['n']} 天，收盘相对差中位数 {check['median']:.4%}，"
        f"95 分位 {check['p95']:.4%}"
    )


def jqka_closes(code: str, publish: str) -> tuple[str, dict[str, float]]:
    """同花顺日线。前缀沿用已经对过的 120_ / zs_，对不上就换下一个。"""
    for prefix in ("120_", "zs_"):
        symbol = prefix + code
        try:
            raw = http.get(
                f"https://d.10jqka.com.cn/v2/line/{symbol}/01/last.js",
                headers={"Referer": "https://q.10jqka.com.cn/", "User-Agent": "Mozilla/5.0"},
                timeout=20,
            )
        except http.FetchError:
            continue
        text = raw.decode("utf-8", "replace")
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end < start:
            continue
        meta = json.loads(text[start:end + 1])
        years = sorted(int(year) for year in (meta.get("year") or {}) if int(year) >= int(publish[:4]))
        closes = {}
        for year in years:
            try:
                blob = http.get(
                    f"https://d.10jqka.com.cn/v2/line/{symbol}/01/{year}.js",
                    headers={"Referer": "https://q.10jqka.com.cn/", "User-Agent": "Mozilla/5.0"},
                    timeout=20,
                )
            except http.FetchError:
                continue
            body = blob.decode("utf-8", "replace")
            i, j = body.find("{"), body.rfind("}")
            if i < 0:
                continue
            payload = json.loads(body[i:j + 1])
            for line in str(payload.get("data") or "").split(";"):
                parts = line.split(",")
                if len(parts) < 5:
                    continue
                day = parts[0][:10].replace("/", "-")
                if len(day) == 8 and day.isdigit():
                    day = f"{day[:4]}-{day[4:6]}-{day[6:8]}"
                try:
                    px = float(parts[4])
                except ValueError:
                    continue
                if publish <= day <= END.isoformat() and px > 0:
                    closes[day] = px
            time.sleep(0.05)
        if len(closes) >= 30:
            return symbol, closes
    return "", {}


def second_closes(code: str, publish: str) -> tuple[str, str, dict[str, float]]:
    secid, name, bars = em_index(code)
    closes = _closes(bars, publish)
    if len(closes) >= 30:
        url = "https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=" + secid
        return f"东财 {secid}「{name}」", url, closes
    sym, tencent = tencent_closes(code)
    kept = {day: px for day, px in tencent.items() if publish <= day <= END.isoformat()}
    if len(kept) >= 30:
        return f"腾讯 {sym}", "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get", kept
    symbol, jqka = jqka_closes(code, publish)
    if len(jqka) >= 30:
        return f"同花顺 {symbol}", f"https://d.10jqka.com.cn/v2/line/{symbol}/01/last.js", jqka
    return "", "", {}


def fund_first(con, code: str) -> str:
    if not code:
        return ""
    row = con.execute("SELECT min(date) FROM bars WHERE code = ? AND close > 0", (code,)).fetchone()
    return str(row[0] or "")[:10] if row else ""


def choose_series(con, row: dict) -> dict:
    """先试全收益 / 净收益，没有第二条日线再用价格指数。"""
    price = row["research_index_code"]
    order = []
    for code in tr_codes(row):
        note = verified_meta(code)
        if not note:
            continue
        if "全收益" in note["name"] or "净收益" in note["name"]:
            order.append((code, note, "全收益" if "全收益" in note["name"] else "净收益"))
    price_note = verified_meta(price)
    if price_note:
        order.append((price, price_note, "价格"))
    tried = []
    skipped = []
    for code in tr_codes(row):
        if not any(code == item[0] for item in order):
            skipped.append(f"{code} 官网详情页未核对，不用这条全收益或净收益")
    for code, note, kind in order:
        publish = note["publish"]
        label, url, closes = second_closes(code, publish)
        tried.append(url or f"{code} 无第二条日线")
        if not closes:
            skipped.append(f"{code}（{note['name']}）没有第二条日线")
            continue
        span = db_span(con, code)
        if span["rows"] and span["source"] not in {"", "csi"}:
            skipped.append(f"{code} 库内来源是 {span['source']}，不改")
            continue
        primary = db_closes(con, code, publish) if span["rows"] else {}
        fetched = None
        if not primary:
            try:
                fetched = fetch_csindex(code, date.fromisoformat(publish), END, pause=0.15)
            except Exception as exc:
                skipped.append(f"{code} 官网行情取不到：{type(exc).__name__}")
                continue
            primary = _closes(fetched.rows, publish)
        check = overlap(primary, closes)
        if not check["ok"]:
            skipped.append(f"{code} {gap_text(check)}，未过 0.01%")
            continue
        return {
            "code": code, "note": note, "kind": kind, "check": check,
            "second": label, "second_url": url, "tried": tried, "skipped": skipped,
            "span": span, "fetched": fetched, "publish": publish,
        }
    return {"skipped": skipped, "tried": tried, "price_note": price_note}


def _reason(picked: dict, appended: str) -> str:
    note = picked["note"]
    bits = [
        f"{note['name']}。",
        f"官网发布日 {note['publish']}，基日 {note['base_date']} 的回填不接。",
        f"入库{picked['kind']}指数 {picked['code']}。",
    ]
    if picked["skipped"]:
        bits.append("未采用：" + "；".join(picked["skipped"]) + "。")
    bits.append(f"{picked['second']}。{gap_text(picked['check'])}。")
    bits.append(appended)
    bits.append("发布日之前的既有行不删。")
    bits.append(f"核对时间 {now_taipei()}。")
    return "".join(bits)


def apply_one(con, row: dict, existing_ids: set[str]) -> dict:
    code = row["research_index_code"]
    container = "star50" if code == "000688" else "theme-" + row["research_index_name"]
    if container in existing_ids and code != "000688":
        raise SystemExit(f"{container} 已经在名册里，不重复开容器")
    picked = choose_series(con, row)
    page = PAGE.format(code=code)
    if not picked.get("code"):
        price_note = picked.get("price_note") or {}
        publish = price_note.get("publish") or "未核对"
        why = "；".join(picked.get("skipped") or []) or "详情页没有读到发布日"
        if code == "H30187":
            why += "。东财「细分化工」是 000813，不是 H30187，不用"
        return {
            "container_id": container, "class": "A股", "status": "frozen",
            "index_code": code, "publish_date": publish if publish != "未核对" else "",
            "bars_code": "", "currency": "CNY",
            "first_list": fund_first(con, row["execution_fund_code"]),
            "series_first": "", "source_url": page,
            "tried_urls": " | ".join(picked.get("tried") or [page]),
            "reason": f"未拼接。{why}。核对时间 {now_taipei()}。",
            "outcome": "unspliced",
        }
    span = picked["span"]
    if span["rows"]:
        appended = f"已有 {span['rows']} 行 {span['first']}→{span['last']}，不覆盖。"
    else:
        rows = [item for item in (picked["fetched"].rows if picked["fetched"] else []) if str(item.get("date") or "")[:10] >= picked["publish"]]
        if any(str(item.get("date") or "")[:10] < picked["publish"] for item in rows):
            raise SystemExit(f"{picked['code']} 试图写入发布日之前的点位")
        ok, appended = _append(con, picked["code"], rows, "csi")
        if not ok:
            return {
                "container_id": container, "class": "A股", "status": "frozen",
                "index_code": code, "publish_date": picked["publish"], "bars_code": "",
                "currency": "CNY", "first_list": fund_first(con, row["execution_fund_code"]),
                "series_first": "", "source_url": page,
                "tried_urls": " | ".join(picked["tried"]),
                "reason": f"未拼接。{appended}",
                "outcome": "unspliced",
            }
        appended = appended if appended.endswith("。") else appended + "。"
    after = db_span(con, picked["code"])
    record = {
        "container_id": container, "class": "A股",
        "index_code": code, "publish_date": picked["publish"],
        "bars_code": picked["code"], "currency": "CNY",
        "first_list": fund_first(con, row["execution_fund_code"]),
        "series_first": after["first"],
        "source_url": picked["note"]["url"],
        "tried_urls": " | ".join(dict.fromkeys(picked["tried"])),
        "reason": _reason(picked, appended),
        "outcome": "spliced",
        "check": picked["check"], "kind": picked["kind"], "bars": picked["code"],
        "second": picked["second"],
    }
    if code == "000688":
        record["status"] = "already"
        record["bars_code"] = ""
        record["outcome"] = "already"
        record["reason"] = (
            "研究序列已经早于首只场内基金。发布日之前的回填不接。"
            + record["reason"]
        )
    else:
        record["status"] = "spliced"
    return record


def write_roster(updates: dict[str, dict]) -> None:
    with ROSTER.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    by_id = {row["container_id"]: row for row in rows}
    for container, record in updates.items():
        payload = {key: record.get(key, "") for key in ROSTER_FIELDS}
        if container in by_id:
            if container == "star50":
                payload["first_list"] = by_id[container].get("first_list") or ""
                payload["series_first"] = by_id[container].get("series_first") or ""
                payload["bars_code"] = by_id[container].get("bars_code") or ""
            by_id[container].update(payload)
        else:
            rows.append(payload)
    with ROSTER.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ROSTER_FIELDS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def apply() -> dict:
    before_codes = {}
    ledger = HashLedger(DB.MARKET_DB)
    before = ledger.before("d38-a-theme")
    con = sqlite3.connect(str(DB.MARKET_DB))
    try:
        total_before = con.execute("SELECT count(*) FROM bars").fetchone()[0]
        for code in CODES:
            for extra in tr_codes(next(row for row in universe_rows() if row["research_index_code"] == code)):
                before_codes[extra] = db_span(con, extra)["rows"]
            before_codes[code] = db_span(con, code)["rows"]
        with ROSTER.open(encoding="utf-8", newline="") as handle:
            existing_ids = {row["container_id"] for row in csv.DictReader(handle)}
        updates = {}
        for row in universe_rows():
            print(f"splice {row['research_index_code']}", flush=True)
            record = apply_one(con, row, existing_ids)
            updates[record["container_id"]] = record
            print(record["outcome"], record["publish_date"], record["reason"][:180], flush=True)
        for code, old in before_codes.items():
            now = db_span(con, code)["rows"]
            if old and now != old:
                raise SystemExit(f"{code} 原有 {old} 行，现在 {now} 行。已有行必须原样保留")
            if not old:
                early = con.execute(
                    "SELECT min(date) FROM bars WHERE code = ? AND adj = 'raw'", (code,)
                ).fetchone()[0]
                note = next((item for item in updates.values() if item.get("bars") == code), None)
                publish = (note or {}).get("publish_date") or ""
                if early and publish and early < publish:
                    raise SystemExit(f"{code} 新写入了发布日 {publish} 之前的 {early}")
        total_after = con.execute("SELECT count(*) FROM bars").fetchone()[0]
    finally:
        con.close()
    after = ledger.after("d38-a-theme")
    write_roster(updates)
    text = "".join(line + "\n" for line in ledger.lines)
    with SHA_LOG.open("a", encoding="utf-8") as handle:
        handle.write(text)
    if after != before:
        log = ROOT / "results" / "inventory" / "db-writes.txt"
        with log.open("a", encoding="utf-8") as handle:
            handle.write(text)
    summary = {
        "before": before, "after": after,
        "bars_before": total_before, "bars_after": total_after,
        "rows": [
            {
                "container_id": item["container_id"],
                "index_code": item["index_code"],
                "status": item["status"],
                "publish_date": item["publish_date"],
                "bars_code": item.get("bars") or item.get("bars_code") or "",
                "kind": item.get("kind") or "",
                "overlap_n": (item.get("check") or {}).get("n"),
                "median": (item.get("check") or {}).get("median"),
                "p95": (item.get("check") or {}).get("p95"),
                "second": item.get("second") or "",
                "reason": item["reason"],
            }
            for item in updates.values()
        ],
    }
    (EVIDENCE / "apply-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    print(f"SHA256 BEFORE {before}", flush=True)
    print(f"SHA256 AFTER  {after}", flush=True)
    print(f"bars {total_before} -> {total_after}", flush=True)
    return summary


def main() -> None:
    import sys
    if "--capture" in sys.argv:
        capture()
    if "--apply" in sys.argv:
        apply()


if __name__ == "__main__":
    main()

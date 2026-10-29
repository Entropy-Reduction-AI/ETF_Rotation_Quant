"""v4-R5b：补 U-指数容器的第 2 档场外纯指数基金。只插入，不覆盖。

成立日晚于 2015-12-31 的不收。复权净值写到这一天为止。
跟踪标的用概况页原文，对得上容器已登记的指数名称或代码才入库。
"""
from __future__ import annotations

import csv
import re
import sqlite3
import time
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from src.data import db as DB
from src.data import http
from src.v3.data.universe import containers as load_containers
from src.v4.data.adjust import compound_adjusted_nav
from src.v4.data.parse import series_sha256
from src.v4.data.r1b_parse import parse_jbgk, parse_pingzhongdata, parse_rank_index_funds
from src.v4.engine.carriers import accepted_tracks, has_investable_index

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "results" / "v4" / "inventory" / "r5b"
RANK_URL = "https://fund.eastmoney.com/data/rankhandler.aspx"
JBGK = "https://fundf10.eastmoney.com/jbgk_{code}.html"
PING = "https://fund.eastmoney.com/pingzhongdata/{code}.js"
LSJZ = "https://api.fund.eastmoney.com/f10/lsjz"
CUTOFF = "2015-12-31"
END = date(2015, 12, 31)
_TAG = re.compile(r"<[^>]+>")


class R5bOtcError(RuntimeError):
    pass


def _cell(html: str, label: str) -> str:
    match = re.search(rf"{re.escape(label)}</th>\s*<td[^>]*>\s*([^<]+)", html)
    if not match:
        return ""
    return _TAG.sub("", match.group(1)).strip()


def _now() -> str:
    return datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds")


def _pieces(text: str) -> list[str]:
    raw = str(text or "").strip()
    if not raw:
        return []
    found = [raw]
    for sep in ("(", "（"):
        if sep not in raw:
            continue
        head, tail = raw.split(sep, 1)
        head = head.strip()
        if head:
            found.append(head)
        code = tail.split(")")[0].split("）")[0].strip()
        if code:
            found.append(code)
    out = []
    for item in found:
        if item and item not in out:
            out.append(item)
    return out


def _owners() -> tuple[dict[str, str], dict[str, set[str]]]:
    owner: dict[str, str] = {}
    ambiguous: dict[str, set[str]] = {}
    for container in load_containers():
        if container.get("arm") not in {None, "main"}:
            continue
        if container.get("asset_class") == "现金" or not container.get("in_pool_index"):
            continue
        if not has_investable_index(container):
            continue
        identity = str(container.get("id") or "")
        for label in accepted_tracks(container):
            prior = owner.get(label)
            if prior is None:
                owner[label] = identity
                continue
            if prior != identity:
                ambiguous.setdefault(label, set()).update({prior, identity})
    for label in ambiguous:
        owner.pop(label, None)
    return owner, ambiguous


def _exchange_only(name: str) -> bool:
    text = str(name or "")
    return "交易型开放式" in text and "联接" not in text


def _match(tracked: str, owner: dict[str, str]) -> tuple[str, str]:
    hits = []
    for piece in _pieces(tracked):
        identity = owner.get(piece)
        if identity and identity not in {item[0] for item in hits}:
            hits.append((identity, piece))
    if len(hits) != 1:
        return "", ""
    return hits[0]


def _rank(log: list[str]) -> list[dict]:
    headers = {"Referer": "https://fund.eastmoney.com/data/fundranking.html"}
    found: dict[str, dict] = {}
    for kind in ("zs", "qdii"):
        raw = http.get(RANK_URL, {
            "op": "ph", "dt": "kf", "ft": kind, "rs": "", "gs": "0", "sc": "clrq", "st": "asc",
            "pi": "1", "pn": "10000", "dx": "1",
        }, headers=headers, timeout=60)
        rows = parse_rank_index_funds(raw.decode("utf-8", "replace"), CUTOFF)
        log.append(f"rank {kind} inception<={CUTOFF} n={len(rows)}")
        for row in rows:
            found.setdefault(row["code"], {**row, "rank": kind})
    return [found[code] for code in sorted(found)]


def _profile(code: str) -> dict:
    page = JBGK.format(code=code)
    html = http.get(page, headers={"Referer": "https://fundf10.eastmoney.com/"}, timeout=30)
    info = parse_jbgk(html.decode("utf-8", "replace"))
    info["fund_type"] = _cell(html.decode("utf-8", "replace"), "基金类型")
    info["page"] = page
    return info


def _from_ping(code: str) -> list[dict]:
    url = PING.format(code=code)
    body = http.get(url, headers={"Referer": f"https://fund.eastmoney.com/{code}.html"}, timeout=60)
    points = parse_pingzhongdata(body.decode("utf-8", "replace"), END)
    nav = compound_adjusted_nav(points)
    for row in nav:
        row["source"] = "eastmoney_pingzhongdata"
        row["source_url"] = url
        row["method"] = "equity_return_compound"
    return nav


def _from_lsjz(code: str) -> list[dict]:
    points = []
    page = 1
    total = None
    while True:
        raw = http.get(LSJZ, {
            "fundCode": code,
            "pageIndex": str(page),
            "pageSize": "200",
            "startDate": "1990-01-01",
            "endDate": CUTOFF,
        }, headers={"Referer": "https://fundf10.eastmoney.com/"}, timeout=40)
        payload = __import__("json").loads(raw.decode("utf-8", "replace"))
        data = payload.get("Data") or {}
        batch = data.get("LSJZList") or []
        if total is None:
            total = int(data.get("TotalCount") or 0)
        if not batch:
            break
        for item in batch:
            day = str(item.get("FSRQ") or "")
            if not day or day > CUTOFF:
                continue
            growth = item.get("JZZZL")
            points.append({
                "date": day,
                "unit_nav": _num(item.get("DWJZ")),
                "accum_nav": _num(item.get("LJJZ")),
                "equity_return": _num(growth) if growth not in (None, "", "--") else None,
                "dividend": 0.0,
            })
        if total is not None and page * 200 >= total:
            break
        page += 1
        if page > 40:
            break
        time.sleep(0.05)
    points.sort(key=lambda row: row["date"])
    dedup = {}
    for row in points:
        dedup[row["date"]] = row
    nav = compound_adjusted_nav([dedup[day] for day in sorted(dedup)])
    url = f"{LSJZ}?fundCode={code}&endDate={CUTOFF}"
    for row in nav:
        row["source"] = "eastmoney_lsjz"
        row["source_url"] = url
        row["method"] = "equity_return_compound"
    return nav


def _num(value):
    if value in (None, "", "--"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _nav(code: str, log: list[str]) -> list[dict]:
    try:
        rows = _from_ping(code)
        if rows:
            return rows
        log.append(f"nav {code} ping empty")
    except (http.FetchError, ValueError) as exc:
        log.append(f"nav {code} ping FAIL {exc}")
    rows = _from_lsjz(code)
    if not rows:
        raise R5bOtcError(f"{code} 没有复权净值")
    log.append(f"nav {code} lsjz rows={len(rows)}")
    return rows


def _insert(con: sqlite3.Connection, item: dict, nav: list[dict], fetched_at: str) -> None:
    code = item["code"]
    if con.execute("SELECT 1 FROM v4_listing WHERE code=?", (code,)).fetchone():
        raise R5bOtcError(f"{code} 已在 v4_listing，不覆盖")
    have = con.execute(
        "SELECT COUNT(*) FROM v4_series WHERE code=? AND kind='otc_nav'", (code,)).fetchone()[0]
    if have:
        raise R5bOtcError(f"{code} 已有 otc_nav {have} 行，不覆盖")
    fresh = [row for row in nav if row["date"] <= CUTOFF]
    if not fresh:
        raise R5bOtcError(f"{code} 在 {CUTOFF} 之前没有净值")
    digest = series_sha256(
        [{"date": row["date"], "unit_nav": row["unit_nav"], "accum_nav": row["accum_nav"], "close": row["close"]}
         for row in fresh],
        ("date", "unit_nav", "accum_nav", "close"))
    with con:
        con.executemany(
            """INSERT INTO v4_series
               (code, kind, date, open, high, low, close, volume, unit_nav, accum_nav, filled,
                source, source_url, method, fetched_at)
               VALUES (?, 'otc_nav', ?, NULL, NULL, NULL, ?, NULL, ?, ?, 0, ?, ?, ?, ?)""",
            [(code, row["date"], row["close"], row.get("unit_nav"), row.get("accum_nav"),
              row["source"], row["source_url"], row["method"], fetched_at) for row in fresh])
        con.execute(
            """INSERT INTO v4_listing
               (code, name, container_id, maps_to, tracked_index, inception, enhanced,
                source_url, sha256, note, fetched_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (code, item["name"], f"otc-{code}", item["maps_to"], item["tracked_index"],
             item["inception"], int(item["enhanced"]), item["page"], digest, item["note"], fetched_at))
    item["sha256"] = digest
    item["rows"] = len(fresh)
    item["first_date"] = fresh[0]["date"]
    item["last_date"] = fresh[-1]["date"]


def run(root: Path = OUT) -> list[dict]:
    root.mkdir(parents=True, exist_ok=True)
    log: list[str] = [f"cutoff inception and nav <= {CUTOFF}"]
    owner, ambiguous = _owners()
    log.append(f"labels {len(owner)} ambiguous {len(ambiguous)}")
    for label, ids in sorted(ambiguous.items()):
        log.append(f"ambiguous {label} -> {sorted(ids)}")
    ranked = _rank(log)
    con = sqlite3.connect(DB.MARKET_DB)
    con.row_factory = sqlite3.Row
    existing = {row[0] for row in con.execute("SELECT code FROM v4_listing")}
    fetched_at = _now()
    scan = []
    inserted = []
    try:
        for i, row in enumerate(ranked, start=1):
            code = row["code"]
            if code in existing:
                scan.append({**row, "decision": "already", "maps_to": "", "tracked": "", "fund_type": ""})
                continue
            try:
                info = _profile(code)
            except (http.FetchError, ValueError) as exc:
                log.append(f"jbgk {code} FAIL {exc}")
                scan.append({**row, "decision": "profile_fail", "maps_to": "", "tracked": "", "fund_type": ""})
                time.sleep(0.05)
                continue
            name = info.get("name") or row["name"]
            tracked = info.get("tracked_index") or ""
            fund_type = info.get("fund_type") or ""
            inception = info.get("inception") or row["inception"]
            enhanced = 1 if "增强" in name or "增强" in (info.get("short_name") or "") else 0
            base = {
                "code": code, "name": name, "inception": inception, "tracked": tracked,
                "fund_type": fund_type, "rank": row["rank"],
            }
            if inception > CUTOFF:
                scan.append({**base, "decision": "after_cutoff", "maps_to": ""})
                continue
            if not tracked:
                scan.append({**base, "decision": "no_track", "maps_to": ""})
                continue
            if "指数" not in fund_type and "指数" not in name:
                scan.append({**base, "decision": "not_index", "maps_to": ""})
                continue
            if _exchange_only(name):
                scan.append({**base, "decision": "exchange_etf", "maps_to": ""})
                continue
            identity, piece = _match(tracked, owner)
            if not identity:
                scan.append({**base, "decision": "unmatched", "maps_to": ""})
                time.sleep(0.02)
                continue
            research = next(item for item in load_containers() if item.get("id") == identity).get("research") or {}
            en = str(research.get("index_name") or "")
            code_name = str(research.get("index_code") or "")
            note = (
                f"D24-1 第2档。成立日不晚于 {CUTOFF}。"
                f"概况页跟踪标的「{tracked}」对上容器 {identity} 已登记的「{piece}」。"
                f"容器指数名称或代码：{en} / {code_name}。"
            )
            if "联接" in name:
                note += " 名称含联接，跟踪标的仍是上面的指数。"
            if enhanced:
                note += " 指数增强，不作载体。"
            item = {
                "code": code, "name": name, "maps_to": identity, "tracked_index": tracked,
                "inception": inception, "enhanced": enhanced, "page": info["page"], "note": note,
            }
            try:
                nav = _nav(code, log)
                _insert(con, item, nav, fetched_at)
            except (http.FetchError, ValueError, R5bOtcError) as exc:
                log.append(f"insert {code} FAIL {exc}")
                scan.append({**base, "decision": "nav_fail", "maps_to": identity})
                time.sleep(0.05)
                continue
            inserted.append(item)
            scan.append({**base, "decision": "inserted", "maps_to": identity})
            log.append(
                f"otc {code} {identity} {tracked} enhanced={enhanced} "
                f"rows={item['rows']} {item['first_date']}→{item['last_date']}")
            if i % 25 == 0:
                print(f"scanned {i}/{len(ranked)} inserted {len(inserted)}", flush=True)
            time.sleep(0.05)
    finally:
        con.close()
    _write(root / "scan.csv", scan)
    _write(root / "roster.csv", inserted)
    (root / "run.log").write_text("\n".join(log) + "\n", encoding="utf-8")
    print(f"inserted {len(inserted)} scanned {len(scan)}", flush=True)
    return inserted


def _write(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = list(rows[0].keys())
    for row in rows[1:]:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _execution_owner(code: str) -> str:
    hits = []
    for container in load_containers():
        if container.get("arm") not in {None, "main"} or not has_investable_index(container):
            continue
        for row in container.get("execution") or []:
            if str(row.get("code") or "") == code:
                hits.append(str(container.get("id") or ""))
    hits = list(dict.fromkeys(hits))
    if len(hits) == 1:
        return hits[0]
    return ""


def supplement(codes: list[str], root: Path = OUT) -> list[dict]:
    """排名接口没列出的代码。仍只插入，概况页对上已登记指数才入库。"""
    root.mkdir(parents=True, exist_ok=True)
    log = [f"supplement n={len(codes)} cutoff={CUTOFF}"]
    owner, _ambiguous = _owners()
    con = sqlite3.connect(DB.MARKET_DB)
    con.row_factory = sqlite3.Row
    existing = {row[0] for row in con.execute("SELECT code FROM v4_listing")}
    fetched_at = _now()
    inserted = []
    scan = []
    try:
        for code in codes:
            if code in existing:
                scan.append({"code": code, "decision": "already", "maps_to": ""})
                continue
            try:
                info = _profile(code)
            except (http.FetchError, ValueError) as exc:
                log.append(f"jbgk {code} FAIL {exc}")
                scan.append({"code": code, "decision": "profile_fail", "maps_to": ""})
                continue
            name = info.get("name") or ""
            tracked = info.get("tracked_index") or ""
            inception = info.get("inception") or ""
            fund_type = info.get("fund_type") or ""
            enhanced = 1 if "增强" in name or "增强" in (info.get("short_name") or "") else 0
            base = {"code": code, "name": name, "inception": inception, "tracked": tracked, "fund_type": fund_type}
            if not inception or inception > CUTOFF:
                scan.append({**base, "decision": "after_cutoff", "maps_to": ""})
                continue
            if _exchange_only(name) or ("ETF" in name and "联接" not in name and "LOF" not in name):
                scan.append({**base, "decision": "exchange_etf", "maps_to": ""})
                continue
            if not tracked or ("指数" not in fund_type and "指数" not in name):
                scan.append({**base, "decision": "not_index", "maps_to": ""})
                continue
            identity, piece = _match(tracked, owner)
            if not identity:
                identity = _execution_owner(code)
                piece = tracked
            if not identity:
                scan.append({**base, "decision": "unmatched", "maps_to": ""})
                continue
            research = next(item for item in load_containers() if item.get("id") == identity).get("research") or {}
            note = (
                f"D24-1 第2档。成立日不晚于 {CUTOFF}。排名接口未列出，改从概况页补。"
                f"跟踪标的「{tracked}」对上容器 {identity} 的「{piece}」。"
                f"容器指数名称或代码：{research.get('index_name') or ''} / {research.get('index_code') or ''}。"
            )
            item = {
                "code": code, "name": name, "maps_to": identity, "tracked_index": tracked,
                "inception": inception, "enhanced": enhanced, "page": info["page"], "note": note,
            }
            try:
                nav = _nav(code, log)
                _insert(con, item, nav, fetched_at)
            except (http.FetchError, ValueError, R5bOtcError) as exc:
                log.append(f"insert {code} FAIL {exc}")
                scan.append({**base, "decision": "nav_fail", "maps_to": identity})
                continue
            inserted.append(item)
            scan.append({**base, "decision": "inserted", "maps_to": identity})
            log.append(f"otc {code} {identity} {tracked} rows={item['rows']} {item['first_date']}→{item['last_date']}")
            time.sleep(0.05)
    finally:
        con.close()
    _write(root / "supplement-scan.csv", scan)
    _write(root / "supplement-roster.csv", inserted)
    with (root / "run.log").open("a", encoding="utf-8") as handle:
        handle.write("\n".join(log) + "\n")
    print(f"supplement inserted {len(inserted)}", flush=True)
    return inserted


def main() -> None:
    run()


if __name__ == "__main__":
    main()

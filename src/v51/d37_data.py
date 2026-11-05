"""S1 跟踪指数：只从已经登记的中证官网接口补发布日和点位。

已有行不覆盖。拿不到发布日或行情的容器保持冻结规则，写进登记表。
"""
from __future__ import annotations

import csv
import re
import sqlite3
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from src.data import db as DB
from src.data import http
from src.data import store
from src.data.hashlog import HashLedger
from src.data.sources import fetch_csindex
from src.v3.data.universe import containers as load_containers

from .diag_d37 import OUT
from .universe import S1_BOND, S1_EXTRA

ROOT = Path(__file__).resolve().parents[2]
CLASSES = ROOT / "config" / "v5" / "classes.csv"
TAIPEI = ZoneInfo("Asia/Taipei")
CSI_INFO = "https://www.csindex.com.cn/csindex-home/indexInfo/index-basic-info/{code}"
CSI_HEADERS = {"Referer": "https://www.csindex.com.cn/", "Accept": "application/json"}
CODE_RE = re.compile(r"index-basic-info/([0-9A-Za-z]+)")
END = date(2026, 9, 30)
START = date(1990, 1, 1)


def _class_map() -> dict[str, str]:
    frame = pd.read_csv(CLASSES)
    return dict(zip(frame["container_id"], frame["class"]))


def _urls() -> dict[str, str]:
    frame = pd.read_csv(CLASSES)
    return dict(zip(frame["container_id"], frame["source_url"].fillna("")))


def _targets() -> list[dict]:
    classes = _class_map()
    urls = _urls()
    by_id = {str(row.get("id") or ""): row for row in load_containers()}
    rows = []
    for name, kind in sorted(classes.items()):
        if kind not in S1_EXTRA or name == S1_BOND:
            continue
        container = by_id.get(name) or {}
        research = container.get("research") or {}
        source = str(urls.get(name) or research.get("source_url") or "")
        found = CODE_RE.search(source) or CODE_RE.search(str(research.get("publish_date_source") or ""))
        rows.append({
            "container_id": name,
            "class": kind,
            "source_url": source,
            "index_code": found.group(1) if found else "",
            "research_status": str(research.get("series_status") or ""),
        })
    return rows


def _publish(code: str) -> tuple[str, str]:
    payload = http.get_json(CSI_INFO.format(code=code), headers=CSI_HEADERS)
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        return "", "中证基本信息没有 data"
    publish = str(data.get("publishDate") or "")[:10]
    name = str(data.get("indexFullNameCn") or data.get("indexNameCn") or "")
    if not publish:
        return "", f"中证基本信息没有发布日（{name}）"
    return publish, name


def _append(con, code: str, rows: list[dict]) -> tuple[bool, str]:
    existing = store.span(con, code, "raw")
    if existing["rows"]:
        source = existing.get("source") or ""
        if source not in {"", "csindex"}:
            return False, f"已有序列来自 {source}，不覆盖、不拼接"
        return True, f"已有 {existing['rows']} 行 {existing['first']}→{existing['last']}，不覆盖"
    fetched_at = datetime.now(TAIPEI).isoformat(timespec="seconds")
    store.upsert(con, code, "csindex", rows, fetched_at)
    return True, f"新增 {len(rows)} 行"


def sync() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    ledger = HashLedger(DB.MARKET_DB)
    before = ledger.before("d37-s1-index")
    targets = _targets()
    written = []
    if not DB.MARKET_DB.is_file() or DB.MARKET_DB.stat().st_size < 1000:
        raise FileNotFoundError(DB.MARKET_DB)
    blob = DB.MARKET_DB.read_bytes()[:80]
    if blob.startswith(b"version https://git-lfs.github.com/spec/v1"):
        raise RuntimeError("行情库还是 LFS 指针")
    con = sqlite3.connect(str(DB.MARKET_DB))
    try:
        for row in targets:
            code = row["index_code"]
            if not code:
                row["status"] = "frozen"
                row["reason"] = "登记来源里没有可取的指数代码或正式发布日"
                row["publish_date"] = ""
                row["bars_code"] = ""
                continue
            try:
                publish, detail = _publish(code)
            except Exception as exc:
                row["status"] = "frozen"
                row["reason"] = f"发布日取不到：{type(exc).__name__}: {exc}"[:240]
                row["publish_date"] = ""
                row["bars_code"] = ""
                continue
            if not publish:
                row["status"] = "frozen"
                row["reason"] = detail
                row["publish_date"] = ""
                row["bars_code"] = ""
                continue
            try:
                fetched = fetch_csindex(code, START, END, pause=0.3)
            except Exception as exc:
                row["status"] = "frozen"
                row["reason"] = f"有发布日 {publish}，行情取不到：{type(exc).__name__}: {exc}"[:240]
                row["publish_date"] = publish
                row["bars_code"] = ""
                continue
            if not fetched.rows:
                row["status"] = "frozen"
                row["reason"] = f"有发布日 {publish}，中证行情是空的"
                row["publish_date"] = publish
                row["bars_code"] = ""
                continue
            ok, note = _append(con, code, fetched.rows)
            row["publish_date"] = publish
            row["bars_code"] = code if ok else ""
            row["status"] = "spliced" if ok else "frozen"
            row["reason"] = f"{detail}；{note}。发布日之前的点位即使在库里也不参与拼接。"
            if ok:
                written.append(code)
    finally:
        con.close()
    after = ledger.after("d37-s1-index")
    fieldnames = ["container_id", "class", "status", "index_code", "publish_date", "bars_code", "source_url", "reason"]
    for row in targets:
        row.setdefault("status", "frozen")
        row.setdefault("publish_date", "")
        row.setdefault("bars_code", "")
        row.setdefault("reason", "")
    registry = OUT / "s1-index-registry.csv"
    with registry.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(targets)
    sha_path = OUT / "db-sha256.txt"
    sha_path.write_text(
        f"SHA256 BEFORE d37-s1-index {before}\nSHA256 AFTER  d37-s1-index {after}\n",
        encoding="utf-8",
    )
    if after != before:
        log = ROOT / "results" / "inventory" / "db-writes.txt"
        with log.open("a", encoding="utf-8") as handle:
            handle.write(f"SHA256 BEFORE d37-s1-index {before}\n")
            handle.write(f"SHA256 AFTER  d37-s1-index {after}\n")
    return {"before": before, "after": after, "spliced": written, "rows": len(targets)}


def main() -> int:
    summary = sync()
    print(f"before={summary['before']} after={summary['after']} spliced={','.join(summary['spliced']) or '-'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

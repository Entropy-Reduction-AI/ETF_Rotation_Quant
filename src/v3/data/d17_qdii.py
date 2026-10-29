"""D17：补 QDII/LOF 单位净值和累计净值，并列出跟踪标的核对。

只插入 fund_nav 里还没有的日期，截止 2026-09-30。不覆盖已有行。
不算收益，不写 LOCK。
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import time
import tomllib
from datetime import date
from pathlib import Path

from src.data import db as DB
from src.data import fund_nav
from src.data import http
from src.v4.data.integrity import FINDING_COLUMNS, nav_late_vs_list
from src.v4.data.r1b_parse import parse_pingzhongdata
from src.v4.data.r1c import fund_nav_late_findings

from . import emit_universe
from . import parse

ROOT = Path(__file__).resolve().parents[3]
INCOMING = ROOT / "incoming" / "2026-10-28-d17-qdii"
NAV_END = "2026-09-30"
PING = "https://fund.eastmoney.com/pingzhongdata/{code}.js"
JBGK = "https://fundf10.eastmoney.com/jbgk_{code}.html"
SOURCE = "eastmoney_pingzhongdata"
V4_UNIVERSE = ROOT / "config" / "v4" / "universe.toml"
V4_MARKER = "# D17 附录 1 机械纳入的场内 QDII/LOF"
FINDINGS = ROOT / "results" / "v4" / "inventory" / "integrity-findings.csv"
FINDINGS_MD = ROOT / "results" / "v4" / "inventory" / "integrity-2016-2026.md"
CHECK_CSV = ROOT / "results" / "v4" / "inventory" / "d17-track-check.csv"
NAV_CSV = ROOT / "results" / "v4" / "inventory" / "d17-nav-backfill.csv"

# 净值从 2021-01-04 起、且已在 v3 执行层。上市日在 2010–2020，或上市日取不到但第一根正收盘在同一段。
# 规划文字写 13 只研究序列；按 series_code 落在这 23 只里的是下面 14 只，先补这 14 只。
RESEARCH = (
    "159822", "160140", "160416", "160717", "161124", "161126", "161127", "161128",
    "162415", "162719", "164906", "513050", "513080", "513800",
)
REST = (
    "159920", "160924", "161125", "161831", "164705", "510900", "513000", "513030", "513880",
)
NAV_CODES = RESEARCH + REST
TRACK_CODES = ("159518", "513350", "162411", "159577", "513850", "159100", "520870", "520580")


def _gz_write(path: Path, raw: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wb") as handle:
        handle.write(raw)
    return hashlib.sha256(raw).hexdigest()


def fetch_pingzhong(code: str) -> tuple[bytes, list[dict]]:
    url = PING.format(code=code)
    raw = http.get(url, headers={"Referer": "https://fund.eastmoney.com/"}, timeout=60)
    points = parse_pingzhongdata(raw.decode("utf-8", "replace"), date.fromisoformat(NAV_END))
    rows = []
    for point in points:
        rows.append({
            "code": code,
            "date": point["date"],
            "unit_nav": point["unit_nav"],
            "accum_nav": point["accum_nav"],
            "subscribe_status": None,
            "redeem_status": None,
            "source": SOURCE,
        })
    return raw, rows


def _boundary(con, code: str) -> dict:
    prev = con.execute(
        """SELECT date, unit_nav, accum_nav FROM fund_nav
           WHERE code=? AND date<'2021-01-04' AND unit_nav>0 ORDER BY date DESC LIMIT 1""",
        (code,)).fetchone()
    on = con.execute(
        """SELECT date, unit_nav, accum_nav FROM fund_nav
           WHERE code=? AND date='2021-01-04'""",
        (code,)).fetchone()
    return {
        "boundary_prev": prev[0] if prev else "",
        "boundary_prev_unit": "" if not prev else prev[1],
        "boundary_prev_accum": "" if not prev else prev[2],
        "boundary_on_unit": "" if not on else on[1],
        "boundary_on_accum": "" if not on else on[2],
    }


def _dividend_spot(con, code: str) -> dict:
    """补上的日子里，累计净值相对单位净值跳升的一天。只记这一天，不加总。"""
    rows = con.execute(
        """SELECT date, unit_nav, accum_nav FROM fund_nav
           WHERE code=? AND date<? AND unit_nav>0 AND accum_nav IS NOT NULL
           ORDER BY date""",
        (code, "2021-01-04")).fetchall()
    for prev, cur in zip(rows, rows[1:]):
        if (cur[2] - cur[1]) - (prev[2] - prev[1]) > 0.001:
            return {"dividend_date": cur[0], "dividend_unit": cur[1], "dividend_accum": cur[2]}
    return {"dividend_date": "", "dividend_unit": "", "dividend_accum": ""}


def backfill_nav(con, log: list[str]) -> list[dict]:
    fetched_at = DB.now()
    run_id = DB.start_run(con, "backfill", end=date.fromisoformat(NAV_END), args={
        "job": "d17-qdii-nav",
        "portfolio_returns": False,
        "return_summaries_from_2016": False,
        "overwrites_existing_nav": False,
        "codes": list(NAV_CODES),
        "source": SOURCE,
    })
    report = []
    try:
        for index, code in enumerate(NAV_CODES):
            role = "research" if code in RESEARCH else "other"
            url = PING.format(code=code)
            try:
                raw, rows = fetch_pingzhong(code)
            except (http.FetchError, ValueError) as exc:
                report.append({"code": code, "role": role, "status": "missing", "error": str(exc)[:240],
                               "inserted": 0, "source_url": url})
                log.append(f"nav {code} FAIL {exc}")
                continue
            digest = _gz_write(INCOMING / "raw" / "pingzhong" / f"{code}.js.gz", raw)
            result = fund_nav.store_missing(con, run_id, rows, fetched_at, end=NAV_END, source=SOURCE)
            if result["conflicts"]:
                report.append({
                    "code": code, "role": role, "status": "conflict", "inserted": 0,
                    "kept": result["kept"], "conflicts": len(result["conflicts"]),
                    "conflict_dates": " ".join(result["conflicts"][:8]),
                    "source_url": url, "sha256": digest,
                })
                log.append(f"nav {code} CONFLICT {len(result['conflicts'])}")
                continue
            extra = _boundary(con, code)
            extra.update(_dividend_spot(con, code))
            report.append({
                "code": code, "role": role, "status": "in_db", "inserted": result["inserted"],
                "kept": result["kept"], "first": result["first"], "last": result["last"],
                "source_url": url, "sha256": digest, "conflicts": 0, **extra,
            })
            log.append(
                f"nav {code} {role} +{result['inserted']} kept={result['kept']} "
                f"{result['first']}→{result['last']} order={index + 1}/{len(NAV_CODES)}")
            time.sleep(0.15)
        DB.write_requests(con, run_id, http.LOG)
        DB.finish_run(con, run_id, "ok" if all(row.get("status") == "in_db" for row in report) else "error")
    except Exception:
        DB.finish_run(con, run_id, "error")
        raise
    return report


def fetch_jbgk(codes: tuple[str, ...] = TRACK_CODES) -> list[dict]:
    """重新抓概况页，落到 D17 目录。不覆盖 2026-10-24 的原件。"""
    saved = []
    for code in codes:
        url = JBGK.format(code=code)
        raw = http.get(url, headers={"Referer": "https://fundf10.eastmoney.com/"}, timeout=30)
        path = INCOMING / "raw" / "jbgk" / f"{code}.html.gz"
        digest = _gz_write(path, raw)
        profile = parse.parse_jbgk(raw.decode("utf-8", "replace"))
        saved.append({"code": code, "url": url, "sha256": digest, "path": str(path.relative_to(ROOT)), **profile})
    return saved


def track_rows(profiles: dict[str, dict] | None = None) -> list[dict]:
    """8 只的跟踪标的和附录 1 结论。501225 不在这张表里。"""
    profiles = emit_universe.load_jbgk() if profiles is None else profiles
    rows = []
    for code in TRACK_CODES:
        profile = profiles.get(code) or {}
        name = profile.get("full_name") or ""
        kind = profile.get("fund_type") or ""
        track = profile.get("track") or ""
        decision = parse.appendix1_decision(name, kind, track) if name or track else "exclude:概况页取不到"
        rows.append({
            "code": code,
            "name": name,
            "fund_type": kind,
            "track_cell": profile.get("track_cell") or "",
            "benchmark": profile.get("benchmark") or "",
            "track": track,
            "single_index": profile.get("single_index") or parse.classify_track(track),
            "decision": decision,
            "source": profile.get("path") or "",
        })
    return rows


def included_execution(path: Path = emit_universe.UNIVERSE_OUT) -> list[dict]:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    wanted = set(TRACK_CODES)
    rows = []
    for container in data["container"]:
        if container.get("arm") not in {None, "main"}:
            continue
        for item in container.get("execution") or []:
            code = str(item.get("code") or "")
            if code not in wanted:
                continue
            rows.append({
                "code": code,
                "container_id": container["id"],
                "name": item.get("name") or "",
                "track": item.get("track") or "",
                "list_date": item.get("list_date") or "",
                "track_source": item.get("track_source") or "",
            })
    return rows


def sync_v4(con, executions: list[dict]) -> None:
    """把附录 1 新纳入的执行代码追加到 config/v4/universe.toml。重跑只替换这一段。"""
    text = V4_UNIVERSE.read_text(encoding="utf-8") if V4_UNIVERSE.exists() else ""
    if V4_MARKER in text:
        text = text[:text.index(V4_MARKER)].rstrip() + "\n"
    lines = [
        text.rstrip(),
        "",
        V4_MARKER,
        "# 跟踪标的按附录 1 机械纳入 config/v3/universe.toml 之后，把执行代码同步到这里。",
        "# 不新写价格序列。净值在 fund_nav。没有组合收益。",
        "",
    ]
    for item in executions:
        code = item["code"]
        span = con.execute(
            """SELECT min(date), max(date), count(*) FROM fund_nav
               WHERE code=? AND unit_nav>0 AND date<=?""",
            (code, NAV_END)).fetchone()
        digest = hashlib.sha256()
        for day, unit, accum in con.execute(
                """SELECT date, unit_nav, accum_nav FROM fund_nav
                   WHERE code=? AND date<=? ORDER BY date""",
                (code, NAV_END)):
            digest.update(f"{day},{unit},{accum}\n".encode())
        lines.extend([
            "[[container]]",
            f'id = "qdii-{code}"',
            'market = "CN"',
            'instrument_type = "qdii_etf"',
            f'name = "{_toml(item["name"])}"',
            f'code = "{code}"',
            f'maps_to = "{_toml(item["container_id"])}"',
            f'tracked_index = "{_toml(item["track"])}"',
            'return_basis = "unit_nav"',
            'currency = "CNY"',
            f'source = "{SOURCE}"',
            f'source_url = "{JBGK.format(code=code)}"',
            'status = "in_db"',
            f'official_launch = "{item["list_date"]}"',
            f'first_date = "{span[0] or ""}"',
            f'last_date = "{span[1] or ""}"',
            f'rows = "{span[2] or 0}"',
            f'sha256 = "{digest.hexdigest()}"',
            'note = "D17 附录 1 机械纳入。本行只同步名单，价格仍用已有 bars。不计算收益。"',
            "",
        ])
    V4_UNIVERSE.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def append_nav_findings(con, list_date_map: dict[str, str]) -> list[dict]:
    """把新检查追加到清单末尾。已有行一个字节都不改。重跑先去掉上一次追加的同一检查。"""
    fresh = fund_nav_late_findings(con, list_date_map)
    raw = FINDINGS.read_bytes()
    newline = b"\r\n" if b"\r\n" in raw else b"\n"
    lines = raw.decode("utf-8").splitlines()
    kept = [lines[0]]
    for line in lines[1:]:
        parts = line.split(",")
        if len(parts) > 4 and parts[4] == "nav_starts_after_list_date":
            continue
        kept.append(line)
    for row in fresh:
        kept.append(",".join(str(row.get(col) or "") for col in FINDING_COLUMNS))
    FINDINGS.write_bytes(newline.join(line.encode("utf-8") for line in kept) + newline)
    _refresh_finding_md(kept[1:])
    return fresh


def _refresh_finding_md(data_lines: list[str]) -> None:
    counts: dict[str, int] = {}
    for line in data_lines:
        parts = line.split(",")
        if len(parts) >= 5:
            counts[parts[4]] = counts.get(parts[4], 0) + 1
    late = counts.get("nav_starts_after_list_date", 0)
    lines = FINDINGS_MD.read_text(encoding="utf-8").splitlines()
    out = []
    in_table = False
    wrote_table = False
    note = "基金单位净值起点严格晚于上市日一个日历月的，记 `nav_starts_after_list_date`。上市日先用 v3 execution；不是日期时用已落地的深交所列表或概况页。仍然不是日期的不记。这些行的 manager_class 留空，待 Manager。"
    for line in lines:
        if line.startswith("窗口 "):
            out.append(
                f"窗口 2016-01-01 → 2026-09-30。序列 532 条，问题行 {len(data_lines)}。"
                f"D17 新增 `nav_starts_after_list_date` {late} 行，manager_class 留空，待 Manager。"
            )
            continue
        if line.startswith("基金单位净值起点严格晚于上市日"):
            continue
        if line.startswith("| 检查项 |"):
            in_table = True
            out.append(line)
            continue
        if in_table and line.startswith("| ---"):
            out.append(line)
            for key in sorted(counts):
                out.append(f"| {key} | {counts[key]} |")
            wrote_table = True
            continue
        if in_table and line.startswith("|"):
            continue
        if in_table:
            in_table = False
        out.append(line)
    if not wrote_table:
        raise RuntimeError("完整性说明里没有检查项表")
    if note not in out:
        out.append(note)
    FINDINGS_MD.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")


def _toml(text: str) -> str:
    return (text or "").replace("\\", "\\\\").replace('"', "'").replace("\n", " ")


def write_csv(path: Path, rows: list[dict], columns: tuple[str, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def late_preview(list_date: str, first_nav: str) -> str:
    item = nav_late_vs_list(list_date, first_nav)
    return "" if item is None else item["detail"]


NAV_COLUMNS = (
    "code", "role", "status", "inserted", "kept", "first", "last", "conflicts",
    "boundary_prev", "boundary_prev_unit", "boundary_prev_accum",
    "boundary_on_unit", "boundary_on_accum", "dividend_date", "dividend_unit", "dividend_accum",
    "source_url", "sha256", "error",
)
TRACK_COLUMNS = (
    "code", "name", "fund_type", "track_cell", "benchmark", "track",
    "single_index", "decision", "container_id", "list_date", "source",
)


def main() -> int:
    con = DB.connect(DB.MARKET_DB)
    log = []
    try:
        before = DB.sha256_file(DB.MARKET_DB)
        log.append(f"sqlite before sha256={before} bytes={DB.MARKET_DB.stat().st_size}")
        report = backfill_nav(con, log)
        write_csv(NAV_CSV, report, NAV_COLUMNS)
        try:
            fetched = fetch_jbgk()
            log.append("jbgk " + " ".join(f"{row['code']} {row['track']}" for row in fetched))
        except http.FetchError as exc:
            log.append(f"jbgk FAIL {exc}")
        summary = emit_universe.emit(con)
        log.append(f"emit containers={summary['containers']} qdii={summary['qdii_etf']} excluded={summary['excluded']}")
        from . import coverage
        log.append("coverage " + str(coverage.write(con)))
        tracks = track_rows()
        placed = {row["code"]: row for row in included_execution()}
        for row in tracks:
            hit = placed.get(row["code"])
            row["container_id"] = hit["container_id"] if hit else ""
            row["list_date"] = hit["list_date"] if hit else ""
        write_csv(CHECK_CSV, tracks, TRACK_COLUMNS)
        sync_v4(con, list(placed.values()))
        from src.v4.data.r1c import list_dates
        late = append_nav_findings(con, list_dates())
        log.append(f"nav_starts_after_list_date {len(late)}")
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        log.append(f"integrity_check={integrity}")
        con.commit()
        after = DB.sha256_file(DB.MARKET_DB)
        log.append(f"sqlite after sha256={after} bytes={DB.MARKET_DB.stat().st_size}")
    finally:
        con.close()
    for line in log:
        print(line, flush=True)
    return 0 if any(line.startswith("integrity_check=ok") for line in log) else 1


if __name__ == "__main__":
    raise SystemExit(main())

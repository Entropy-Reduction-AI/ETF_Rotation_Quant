"""D35 可交易池 · 场内口径。默认关闭。

配置 `config/v5/listed-only.toml` 的 `enabled` 必须保持 false。
设计期和 D34 一次性检验不读它。本模块的命令把开关打开，只作用于 U-可交易。

    python -m src.v51 oneshot-listed

设计期诊断（2006-01-01 → 2015-12-31）写到 `results/v5/oneshot-listed/design/`。
登记重算（2016-01-01 → 2026-09-30）写到 `results/v5/oneshot-listed/oneshot/`。
另写 `listed-by-year.csv`：每个容器、每一年有没有合格的场内载体。

不写 `results/v5/oneshot/`，不改 LOCK，不写 trial-ledger，不计入判据 ⑤，不打标签。
"""
from __future__ import annotations

import json
import tomllib
from pathlib import Path

import pandas as pd

from src.v51.oneshot import (
    FREEZE_SHA,
    LOCK,
    OneshotError,
    WINDOW_END,
    WINDOW_START,
    _file_sha,
    assert_frozen_blobs,
    assert_lineage,
)

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results" / "v5" / "oneshot-listed"
CONFIG = ROOT / "config" / "v5" / "listed-only.toml"
ADDENDUM = ROOT / "results" / "v5" / "LOCK-addendum-D35.md"
ONESHOT = ROOT / "results" / "v5" / "oneshot"
DESIGN_START = "2006-01-01"
DESIGN_END = "2015-12-31"
DB_SHA256 = "1fe4925e7993eb18d93a5cf359185242a98f7114583f7225033a9ec119ec288f"
YEAR_FROM = 2006
YEAR_TO = 2026


def listed_only_enabled(path: Path = CONFIG) -> bool:
    """配置文件里的默认值。true 才表示有人把默认打开了。"""
    with Path(path).open("rb") as handle:
        raw = tomllib.load(handle)
    return bool(raw.get("enabled", False))


def refuse_listed_output(out: Path) -> None:
    """场内口径只写自己的目录。不覆盖 D34 一次性检验，不写 LOCK，不写账本。"""
    resolved = Path(out).resolve()
    banned = ONESHOT.resolve()
    if resolved == banned or banned in resolved.parents:
        raise OneshotError("不覆盖 results/v5/oneshot")
    if resolved == LOCK.resolve() or resolved.name == "LOCK":
        raise OneshotError("不写 LOCK")
    if "trial-ledger" in resolved.name or any("trial-ledger" in part for part in resolved.parts):
        raise OneshotError("场内口径不写账本")


def require_addendum(path: Path = ADDENDUM) -> str:
    file = Path(path)
    if not file.is_file():
        raise OneshotError("LOCK 附记不存在，拒绝场内口径的 2016 年以后组合收益")
    text = file.read_text(encoding="utf-8")
    if "可交易池 · 场内口径" not in text:
        raise OneshotError("LOCK 附记没有登记「可交易池 · 场内口径」")
    if DB_SHA256 not in text:
        raise OneshotError("LOCK 附记没有绑定补数后的行情库")
    if "161211" not in text or "510880" not in text:
        raise OneshotError("LOCK 附记没有写明 161211 与 510880")
    return _file_sha(file)


def require_listed_db() -> str:
    """用附记里的库。不改设计期登记的那份 SHA，也不接受别的库。"""
    from src.data import db as DB
    from src.v4.r5.design import file_sha256

    path = DB.MARKET_DB
    if not path.exists() or path.stat().st_size < 1000:
        raise OneshotError(f"行情库不可读：{path}")
    digest = file_sha256(path)
    if digest != DB_SHA256:
        raise OneshotError(f"行情库不是附记登记的那一份：{digest}")
    wal = path.with_name(path.name + "-wal")
    shm = path.with_name(path.name + "-shm")
    if wal.exists() or shm.exists():
        raise OneshotError("行情库旁有 -wal 或 -shm，先确认没有未合并的写入")
    return digest


def listed_by_year(end: str = WINDOW_END) -> pd.DataFrame:
    """每个 U-可交易容器、每一年，场内口径下有没有合格载体。

    合格是指这一年里至少有一个交易日，场内 cascade 选得到载体。
    `year_end_carrier` 是该年最后一个交易日选中的那只；当天没有就是空。
    """
    from src.v3.data.universe import containers as load_containers
    from src.v3.engine.universe import pool_members
    from src.v4.engine.carriers import build_candidates, choose_path, listed_carriers, sse_calendar
    from src.v4.r5.design import _connect

    con = _connect()
    try:
        calendar = sse_calendar(con, end)
        containers = load_containers()
        grouped = listed_carriers(build_candidates(con, containers, calendar, end))
    finally:
        con.close()
    members = [
        row for row in pool_members(containers, "A", "tradable")
        if row.get("asset_class") != "现金"
    ]
    rows = []
    for container in members:
        identity = str(container.get("id") or "")
        path = choose_path(grouped.get(identity, []), calendar)
        by_year: dict[int, dict] = {}
        for day, choice in zip(calendar, path):
            year = int(pd.Timestamp(day).year)
            if year < YEAR_FROM or year > YEAR_TO:
                continue
            bucket = by_year.setdefault(year, {
                "sessions": 0, "qualified_days": 0, "year_end_carrier": "",
            })
            bucket["sessions"] += 1
            if choice is None:
                bucket["year_end_carrier"] = ""
                continue
            bucket["qualified_days"] += 1
            bucket["year_end_carrier"] = choice.label
        for year in range(YEAR_FROM, YEAR_TO + 1):
            bucket = by_year.get(year) or {
                "sessions": 0, "qualified_days": 0, "year_end_carrier": "",
            }
            rows.append({
                "container": identity,
                "name": str(container.get("name") or ""),
                "asset_class": str(container.get("asset_class") or ""),
                "year": year,
                "qualified": int(bucket["qualified_days"] > 0),
                "qualified_days": int(bucket["qualified_days"]),
                "sessions": int(bucket["sessions"]),
                "year_end_carrier": bucket["year_end_carrier"],
            })
    return pd.DataFrame(rows)


def _emit_window(spec, folder: Path, *, start: str, end: str, allow_after: bool,
                 last: pd.Timestamp, label: str) -> None:
    from src.v4.r5.design import benchmark_returns, month_states, prepare_market, reference_frame
    from src.v51.oneshot import (
        BENCHMARKS,
        PRIMARY,
        REFERENCE_COLUMN,
        _criteria_row,
        _run_b0,
        _run_peers,
        _run_v51,
        _store_arm,
        _summary_numbers,
        _write_series,
        scored,
    )

    print(f"{label} 参照指数", flush=True)
    parts = reference_frame(end=end, allow_after=allow_after)
    benchmark = scored(
        benchmark_returns(end=end, allow_after=allow_after), last, start=start, end=end)
    states = month_states(end=end, allow_after=allow_after)
    refs = {"BM-main": benchmark}
    for name, column in REFERENCE_COLUMN.items():
        refs[name] = scored(parts[column], last, start=start, end=end)
    bench_dir = folder / "benchmarks"
    for name in BENCHMARKS:
        _write_series(bench_dir / name, refs[name], role="对照", arm=name, pool=None)
    labeled = states.dropna().rename("state").to_frame()
    labeled.index.name = "month_end"
    folder.mkdir(parents=True, exist_ok=True)
    labeled.to_csv(folder / "month-states.csv")
    peers = _run_peers(
        spec, end=end, allow_after=allow_after, listed_only=True, pools=("tradable",))
    rows: list[dict] = []
    for name in BENCHMARKS:
        rows.append(_criteria_row(
            None, name, "对照", _summary_numbers(refs[name]), None, None, formal=False))
    print(f"{label} 装 U-可交易 · 场内口径", flush=True)
    market = prepare_market(
        "tradable", t4=False, allow_substitute=True, spec=spec,
        end=end, allow_after=allow_after, listed_only=True,
    )
    print(f"{label} E2/B0", flush=True)
    b0 = _run_b0(market, spec, allow_after=allow_after)
    _store_arm(
        folder, "tradable", PRIMARY, scored(b0.net, last, start=start, end=end),
        b0, benchmark, states, refs, rows, start=start, end=end,
    )
    print(f"{label} v5.1 对照", flush=True)
    book, allocation = _run_v51(market, spec, "tradable", allow_after=allow_after)
    _store_arm(
        folder, "tradable", "v5.1-对照", scored(book.net, last, start=start, end=end),
        book, benchmark, states, refs, rows, allocation=allocation, start=start, end=end,
    )
    for peer_id in ("A1", "A2"):
        result = peers[(peer_id, "tradable")]
        _store_arm(
            folder, "tradable", peer_id, scored(result.net, last, start=start, end=end),
            result, benchmark, states, refs, rows, start=start, end=end,
        )
    pd.DataFrame(rows).to_csv(folder / "criteria.csv", index=False, float_format="%.12g")
    del market


def _window_manifest(*, kind: str, start: str, end: str, last: pd.Timestamp, head: str,
                     lock_sha: str, addendum_sha: str, digest: str) -> dict:
    return {
        "name": "可交易池 · 场内口径",
        "kind": kind,
        "listed_only": True,
        "config_enabled": False,
        "pool": "tradable",
        "pool_label": "U-可交易",
        "window": [start, end],
        "last_session": last.date().isoformat(),
        "arms": ["E2-B0", "A1", "A2", "v5.1-对照"],
        "v51_role": "对照",
        "counts_toward_criterion_5": False,
        "L5_delta": 0,
        "trial_ledger_written": False,
        "formal_pass": None,
        "d34_conclusion_unchanged": True,
        "liquidity_threshold": 30_000_000,
        "dropped": ["tier-2 OTC", "161211"],
        "kept": ["listed ETF", "LOF", "listed QDII", "510880"],
        "freeze_sha": FREEZE_SHA,
        "head_sha": head,
        "lock": "results/v5/LOCK",
        "lock_sha256": lock_sha,
        "addendum": "results/v5/LOCK-addendum-D35.md",
        "addendum_sha256": addendum_sha,
        "db_sha256": digest,
        "note": "只报告。不改 D34 结论，不计入判据 ⑤。",
    }


def run_listed(*, out: Path | None = None) -> dict:
    """设计期诊断和登记重算各跑一次。会计算组合收益。不写 LOCK。"""
    from src.data.db import git_head
    from src.v3.engine.benchmark import _calendar
    from src.v3.engine.spec import load_spec
    from src.v4.r5.design import _connect
    from src.v51.oneshot import _last_session

    destination = OUT if out is None else Path(out)
    refuse_listed_output(destination)
    if listed_only_enabled():
        raise OneshotError("场内口径的配置默认必须关闭")
    if not LOCK.is_file():
        raise OneshotError("results/v5/LOCK 不存在")
    lock_text = LOCK.read_text(encoding="utf-8")
    if FREEZE_SHA not in lock_text:
        raise OneshotError("LOCK 没有绑定 milestone/v5-code-freeze 的提交")
    addendum_sha = require_addendum()
    lock_sha = _file_sha(LOCK)
    oneshot_criteria = ONESHOT / "criteria.csv"
    oneshot_sha = _file_sha(oneshot_criteria) if oneshot_criteria.is_file() else ""
    head = assert_lineage()
    assert_frozen_blobs()
    digest = require_listed_db()
    registered = destination / "oneshot"
    if (registered / "ran.json").exists():
        raise OneshotError("场内口径的登记重算已经跑过，拒绝再跑")
    spec = load_spec()
    print("场内载体覆盖表", flush=True)
    table = listed_by_year(WINDOW_END)
    destination.mkdir(parents=True, exist_ok=True)
    table.to_csv(destination / "listed-by-year.csv", index=False)
    con = _connect()
    try:
        design_days = _calendar(con, DESIGN_END)
    finally:
        con.close()
    design_last = pd.Timestamp(design_days.max())
    if design_last > pd.Timestamp(DESIGN_END) or design_last < pd.Timestamp("2015-12-01"):
        raise OneshotError(f"设计期最后交易日不对：{design_last.date()}")
    _emit_window(
        spec, destination / "design", start=DESIGN_START, end=DESIGN_END,
        allow_after=False, last=design_last, label="设计期",
    )
    (destination / "design" / "manifest.json").write_text(
        json.dumps(_window_manifest(
            kind="design-diagnostic", start=DESIGN_START, end=DESIGN_END, last=design_last,
            head=head, lock_sha=lock_sha, addendum_sha=addendum_sha, digest=digest,
        ), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    last = _last_session()
    _emit_window(
        spec, registered, start=WINDOW_START, end=WINDOW_END,
        allow_after=True, last=last, label="登记重算",
    )
    (registered / "manifest.json").write_text(
        json.dumps(_window_manifest(
            kind="registered-recalc", start=WINDOW_START, end=WINDOW_END, last=last,
            head=head, lock_sha=lock_sha, addendum_sha=addendum_sha, digest=digest,
        ), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if _file_sha(LOCK) != lock_sha:
        raise OneshotError("运行过程中 LOCK 被改动")
    if oneshot_sha and _file_sha(oneshot_criteria) != oneshot_sha:
        raise OneshotError("运行过程中 D34 criteria.csv 被改动")
    manifest = {
        "name": "可交易池 · 场内口径",
        "listed_only": True,
        "config_enabled": False,
        "scope": "U-可交易",
        "counts_toward_criterion_5": False,
        "L5_delta": 0,
        "trial_ledger_written": False,
        "d34_conclusion_unchanged": True,
        "formal_pass": None,
        "windows": {
            "design": [DESIGN_START, DESIGN_END],
            "oneshot": [WINDOW_START, WINDOW_END],
        },
        "year_table": "listed-by-year.csv",
        "year_table_excludes": "现金",
        "freeze_sha": FREEZE_SHA,
        "head_sha": head,
        "git_head": git_head() or head,
        "lock_sha256": lock_sha,
        "addendum_sha256": addendum_sha,
        "db_sha256": digest,
        "liquidity_threshold": 30_000_000,
    }
    (destination / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (registered / "ran.json").write_text(
        json.dumps({
            "single_pass": True,
            "listed_only": True,
            "counts_toward_criterion_5": False,
            "window": [WINDOW_START, WINDOW_END],
            "freeze_sha": FREEZE_SHA,
            "head_sha": head,
        }, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "out": str(destination),
        "head": head,
        "db_sha256": digest,
        "design_last": design_last.date().isoformat(),
        "oneshot_last": last.date().isoformat(),
        "containers": int(table["container"].nunique()) if len(table) else 0,
    }

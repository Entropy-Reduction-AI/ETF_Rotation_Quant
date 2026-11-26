"""现行配置的设计期日收益。生成链是当时的两步，不另写权重。

1. `src.data.runner.package`，`--end` 为当前隔离窗口（未打开时 2015-12-31），bars 的 SQL 带 `date<=`。
2. `src.indicators.build`，窗口用数据包的 end。
3. `src.portfolio.replicate.daily_book`，阀门关闭：状态恒为在场。

`replicate()` 自己会跑慢阀，D47-4 说那份旧口径不能代用。
"""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import date
from pathlib import Path

import pandas as pd

from src.data.runner import package
from src.indicators.build import build
from src.portfolio.config import load_config
from src.portfolio.replicate import _haven_returns, _read_panel, daily_book, load_haven_closes
from src.v6.guard import DESIGN_END, OFFICIAL_WINDOW_END_TEXT, IsolationError, assert_not_after, load_end_text

ROOT = Path(__file__).resolve().parents[2]
ISOLATED = ROOT / "outputs" / "v6-design-panel"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _max_date(db: Path, table: str, column: str = "date") -> str | None:
    uri = f"{db.resolve().as_uri()}?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    try:
        row = con.execute(f"SELECT max({column}) FROM {table}").fetchone()
    finally:
        con.close()
    return None if row is None else row[0]


def design_book() -> tuple[pd.Series, dict]:
    cfg = load_config()
    if cfg.valve_enabled:
        raise IsolationError("config/portfolio.toml 的阀门是开的，D47-4 要求关闭")
    if cfg.design_end > DESIGN_END:
        raise IsolationError(f"配置的设计期末是 {cfg.design_end.date()}")
    end_text = load_end_text()
    if end_text > OFFICIAL_WINDOW_END_TEXT:
        raise IsolationError(f"现行配置不能晚于 {OFFICIAL_WINDOW_END_TEXT}")
    end = date.fromisoformat(end_text)
    ISOLATED.mkdir(parents=True, exist_ok=True)
    packaged = package(end, pkg_root=ISOLATED, force=True, log=lambda *_args: None)
    bar_last = _max_date(packaged, "bars")
    if bar_last is None or bar_last > end.isoformat():
        raise IsolationError(f"数据包 bars 的最后一天是 {bar_last}，不是停在 {end.isoformat()}")
    panel = build(packaged, ISOLATED / f"panel-{end.isoformat()}.sqlite", log=lambda *_args: None)
    panel_last = _max_date(panel, "panel")
    if panel_last is None or panel_last > end.isoformat():
        raise IsolationError(f"面板最后一天是 {panel_last}")
    prices = _read_panel(panel, pd.Timestamp(end))
    if prices.empty or pd.Timestamp(prices["date"].max()) > pd.Timestamp(end):
        raise IsolationError("读到的面板越过了这次窗口终点")
    wide = prices.pivot(index="date", columns="container", values="close").sort_index()
    assert_not_after(wide.index, "现行配置面板")
    month_ends = wide.groupby(wide.index.to_period("M")).tail(1).index
    state = pd.Series(1, index=month_ends, dtype=int)
    haven = load_haven_closes(ROOT / "data" / "market.sqlite", cfg.haven_code, pd.Timestamp(end))
    series = daily_book(wide, state, cfg, _haven_returns(wide.index, haven, cfg.cash_daily))
    assert_not_after(series.index, "现行配置")
    evidence = {
        "status": "ok",
        "end": end.isoformat(),
        "commands": [
            f"python -m src.data package --end {end.isoformat()}",
            f"python -m src.indicators build --package research-package-{end.isoformat()}.sqlite",
            "src.portfolio.replicate.daily_book，状态恒为 1（阀门关闭）",
        ],
        "code_sha256": {
            "src/data/runner.py": _sha(ROOT / "src/data/runner.py"),
            "src/indicators/build.py": _sha(ROOT / "src/indicators/build.py"),
            "src/portfolio/replicate.py": _sha(ROOT / "src/portfolio/replicate.py"),
        },
        "market_sqlite_sha256": _sha(ROOT / "data" / "market.sqlite"),
        "package_sha256": _sha(packaged),
        "package_bars_last": bar_last,
        "panel_sha256": _sha(panel),
        "panel_last": panel_last,
        "book_first": series.index.min().date().isoformat(),
        "book_last": series.index.max().date().isoformat(),
        "valve": "关闭。replicate() 会跑慢阀，这里不调用它，只把 daily_book 的状态设为在场。",
        "absent": "7.5% 偏离带、溢价上限、主备基金、净值滞后 2 天、一手 100 份不在这套日频回测里。",
        "calendar_note": f"package() 复制整张 calendar。bars 与 build 的窗口停在 {end.isoformat()}，上面已核对两张表的最大日期。",
    }
    return series, evidence

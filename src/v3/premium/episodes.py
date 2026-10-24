"""复现 prem_episodes.py 的事件清单。口径跟那个脚本，不跟 §5.2 的四种状态。

溢价 = 收盘价 / 前一条净值（向前填充后再滞后 1 行）− 1，从 2021-01-01 起。
常态线 = 250 个溢价的中位数，最少 120 个，再滞后 1 行。
偏离 ≥ 10% 开始，偏离 > 0 结束。这是 §1-5 已经看过的诊断，不是组合收益。
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
JSON_DIR = ROOT / "incoming" / "2026-10-24-qdii-nav-min"

# eeb3453 当时 fund_nav 的全部代码。当前库后来又加了代码，不放进这张清单。
EXPLORE_DB_CODES = (
    "159509", "159612", "159740", "159866", "159941", "160723", "161129", "501018",
    "513100", "513130", "513180", "513300", "513500", "513520", "513650",
)
# 脚本用 JSON 盖掉库里的这两只（当时库里没有，或要用这份原件）。
EXPLORE_JSON_CODES = ("159529", "501225")

COLUMNS = (
    "code", "start", "peak", "peak_prem", "base", "rise_days",
    "half_revert_days", "px_chg", "nav_chg",
)


def _db_frames(con: sqlite3.Connection, code: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    price = pd.read_sql_query(
        "select date, close from bars where adj='raw' and code=?", con, params=(code,), index_col="date")
    nav = pd.read_sql_query(
        "select date, unit_nav nav from fund_nav where code=?", con, params=(code,), index_col="date")
    return price, nav


def _json_frames(directory: Path, code: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    nav_rows = json.loads((directory / f"{code}_nav.json").read_text(encoding="utf-8"))
    px_rows = json.loads((directory / f"{code}_px.json").read_text(encoding="utf-8"))
    nav = pd.DataFrame(
        [(row["FSRQ"], float(row["DWJZ"])) for row in nav_rows if row["DWJZ"]],
        columns=["date", "nav"],
    ).set_index("date")
    price = pd.DataFrame(
        [(row[0], float(row[2])) for row in px_rows],
        columns=["date", "close"],
    ).drop_duplicates("date").set_index("date")
    return price, nav


def load_explore_frames(con: sqlite3.Connection, json_dir: Path = JSON_DIR) -> dict[str, tuple[pd.DataFrame, pd.DataFrame]]:
    frames = {code: _db_frames(con, code) for code in EXPLORE_DB_CODES}
    for code in EXPLORE_JSON_CODES:
        frames[code] = _json_frames(json_dir, code)
    return frames


def scan_frames(frames: dict[str, tuple[pd.DataFrame, pd.DataFrame]]) -> pd.DataFrame:
    """与 prem_episodes.py 同一段循环。返回的是事件，不是组合净值。"""
    rows = []
    for code, (price, nav) in frames.items():
        rows.extend(_scan_one(str(code), price, nav))
    frame = pd.DataFrame(rows, columns=list(COLUMNS))
    if frame.empty:
        return frame
    return frame.sort_values(["code", "start", "peak"]).reset_index(drop=True)


def _scan_one(code: str, price: pd.DataFrame, nav: pd.DataFrame) -> list[dict]:
    joined = price.join(nav, how="outer").sort_index()
    joined.index = pd.to_datetime(joined.index)
    joined["navl"] = joined["nav"].ffill().shift(1)
    joined = joined.dropna(subset=["close"])
    premium = (joined["close"] / joined["navl"] - 1).dropna()
    premium = premium[premium.index >= "2021-01-01"]
    if len(premium) < 120:
        return []
    baseline = premium.rolling(250, min_periods=120).median().shift(1)
    deviation = premium - baseline
    found = []
    cursor = 0
    while cursor < len(premium):
        if deviation.iloc[cursor] >= 0.10:
            end = cursor
            while end < len(premium) and deviation.iloc[end] > 0:
                end += 1
            segment = premium.iloc[cursor:end]
            peak_at = segment.idxmax()
            peak_premium = segment.max()
            base = baseline.loc[peak_at]
            after = premium[peak_at:]
            half = after[after <= base + (peak_premium - base) / 2]
            reverted = half.index[0] if len(half) else None
            start = segment.index[0]
            record = {
                "code": code,
                "start": str(pd.Timestamp(start).date()),
                "peak": str(pd.Timestamp(peak_at).date()),
                "peak_prem": round(float(peak_premium) * 100),
                "base": round(float(base) * 100),
                "rise_days": int((pd.Timestamp(peak_at) - pd.Timestamp(start)).days),
                "half_revert_days": int((pd.Timestamp(reverted) - pd.Timestamp(peak_at)).days) if reverted is not None else None,
                "px_chg": None,
                "nav_chg": None,
            }
            if reverted is not None:
                record["px_chg"] = round((float(joined["close"][reverted]) / float(joined["close"][peak_at]) - 1) * 100, 1)
                record["nav_chg"] = round((float(joined["navl"][reverted]) / float(joined["navl"][peak_at]) - 1) * 100, 1)
            found.append(record)
            cursor = end
        else:
            cursor += 1
    return found


def scan_explore(con: sqlite3.Connection, json_dir: Path = JSON_DIR) -> pd.DataFrame:
    return scan_frames(load_explore_frames(con, json_dir))

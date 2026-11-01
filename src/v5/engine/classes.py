"""读取冻结后的大类表。表本身在冻结前已经定稿，这里只校验并原样加载。"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CLASSES = ROOT / "config" / "v5" / "classes.csv"
COLUMNS = ("container_id", "class", "basis", "source_url")
# 预注册 §3.2 的大类。现金不参加排名。
RISK_CLASSES = ("A股", "港股", "美股", "其他海外", "商品")
DEFENSIVE_CLASSES = ("国债", "黄金")
CASH_CLASS = "现金"
# 本次冻结草稿的行数。多一行或少一行就拒绝，避免引擎悄悄换表。
EXPECTED_ROWS = 117
KNOWN_CLASSES = set(RISK_CLASSES) | set(DEFENSIVE_CLASSES) | {CASH_CLASS}


class ClassesError(ValueError):
    pass


def load_classes(path: Path | None = None) -> pd.DataFrame:
    """`config/v5/classes.csv`。列名与草稿相同。"""
    source = DEFAULT_CLASSES if path is None else Path(path)
    frame = pd.read_csv(source, dtype=str, keep_default_na=False)
    missing = [name for name in COLUMNS if name not in frame.columns]
    if missing:
        raise ClassesError(f"缺少列 {missing}")
    frame = frame.loc[:, list(COLUMNS)].copy()
    if len(frame) != EXPECTED_ROWS:
        raise ClassesError(f"大类表应有 {EXPECTED_ROWS} 行，实际 {len(frame)}")
    if frame["container_id"].duplicated().any():
        raise ClassesError("container_id 重复")
    if frame["container_id"].eq("").any() or frame["class"].eq("").any():
        raise ClassesError("container_id 或 class 为空")
    unknown = sorted(set(frame["class"]) - KNOWN_CLASSES)
    if unknown:
        raise ClassesError(f"未知大类 {unknown}")
    cash = frame.loc[frame["class"].eq(CASH_CLASS), "container_id"].tolist()
    if cash != ["cash"]:
        raise ClassesError("现金类必须且只能是 cash")
    return frame


def class_map(frame: pd.DataFrame | None = None) -> dict[str, str]:
    table = load_classes() if frame is None else frame
    return dict(zip(table["container_id"], table["class"]))

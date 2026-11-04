"""v5.1 引擎。读数和持仓在本包；成交、成本、池子、溢价沿用 v4/v5。

不写 LOCK，不打标签。设计期全量收益不在导入时运行。
"""

from .allocate import allocate, target_weights
from .execute import open_market, run_book
from .params import load_params
from .readings import read_panel

__all__ = [
    "allocate",
    "load_params",
    "open_market",
    "read_panel",
    "run_book",
    "target_weights",
]

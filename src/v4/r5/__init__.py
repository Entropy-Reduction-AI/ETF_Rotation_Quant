"""v4-R5 设计期运行。结束日停在 2015-12-31，不写 LOCK，不做一次性检验。"""

from .design import DESIGN_END, DB_SHA256

__all__ = ["DB_SHA256", "DESIGN_END"]

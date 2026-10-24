"""v3 §4 回测引擎。不改预注册，不写 LOCK，默认不计算 2016 年起的组合收益。"""

from .runner import RunnerError, execute, resolve_end, run

__all__ = ["RunnerError", "execute", "resolve_end", "run"]

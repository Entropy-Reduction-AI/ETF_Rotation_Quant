"""生产组合的配置：读取与校验。"""
from __future__ import annotations

import csv
import tomllib
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "config" / "portfolio.toml"
TRADING_DAYS = 252

class FallbackError(RuntimeError):
    pass


@dataclass(frozen=True)
class Alternate:
    code: str
    list_date: pd.Timestamp


@dataclass(frozen=True)
class AShareBook:
    container: str
    primary: str
    alternates: tuple[Alternate, ...]


@dataclass(frozen=True)
class OverseasPool:
    container: str
    codes: tuple[str, ...]


@dataclass(frozen=True)
class NavRow:
    code: str
    date: pd.Timestamp
    unit_nav: float
    fetched_at: str = ""
    source: str = ""


@dataclass(frozen=True)
class FallbackConfig:
    design_end: pd.Timestamp
    a_share: tuple[str, ...]
    a_weight: float
    overseas: tuple[str, ...]
    o_weight: float
    out: float
    back: float
    judge: str
    haven_code: str
    cash_annual: float
    rebalance: str
    cost_one_way: float
    universe: Path
    path: Path
    band: float = 0.075
    premium_cap: float = 0.10
    nav_lag: int = 2
    lot_size: int = 100
    funds: tuple[AShareBook, ...] = ()
    pools: tuple[OverseasPool, ...] = ()
    excluded: tuple[str, ...] = ()
    # D7 之后生产目标不看慢阀。replicate 仍用 out/back 做设计期历史复现。
    valve_enabled: bool = True

    @property
    def cash_monthly(self) -> float:
        return self.cash_annual / 12

    @property
    def cash_daily(self) -> float:
        return self.cash_annual / TRADING_DAYS

def _universe_path(config_path: Path, raw: str) -> Path:
    path = Path(raw)
    if path.is_absolute():
        return path
    return (config_path.parent.parent / path).resolve()


def _load_books(rows: list[dict]) -> tuple[AShareBook, ...]:
    books = []
    for row in rows:
        alternates = tuple(
            Alternate(str(item["code"]).strip(), pd.Timestamp(item["list_date"]))
            for item in (row.get("alternates") or []))
        books.append(AShareBook(str(row["container"]).strip(), str(row["primary"]).strip(), alternates))
    return tuple(books)


def _load_pools(rows: list[dict]) -> tuple[OverseasPool, ...]:
    pools = []
    for row in rows:
        codes = tuple(str(code).strip() for code in row["codes"])
        pools.append(OverseasPool(str(row["container"]).strip(), codes))
    return tuple(pools)


def load_config(path: Path | None = None) -> FallbackConfig:
    path = Path(path) if path else DEFAULT_CONFIG
    with path.open("rb") as fh:
        raw = tomllib.load(fh)
    if "pending" in raw or any("pending" in section for section in raw.values() if isinstance(section, dict)):
        raise FallbackError("正式配置不再保留 pending")
    a = raw["a_share"]
    o = raw["overseas"]
    v = raw["valve"]
    ex = raw["execution"]
    cfg = FallbackConfig(
        design_end=pd.Timestamp(raw["design_end"]),
        a_share=tuple(a["containers"]),
        a_weight=float(a["weight"]),
        overseas=tuple(o["containers"]),
        o_weight=float(o["weight"]),
        out=float(v["out"]),
        back=float(v["back"]),
        judge=str(v["judge"]),
        haven_code=str(v["haven_code"]),
        cash_annual=float(v["cash_annual"]),
        rebalance=str(ex["rebalance"]),
        cost_one_way=float(ex["cost_one_way"]),
        universe=_universe_path(path, str(ex["universe"])),
        path=path,
        band=float(ex["band"]),
        premium_cap=float(ex["premium_cap"]),
        nav_lag=int(ex["nav_lag_trading_days"]),
        lot_size=int(ex["lot_size"]),
        funds=_load_books(list(a["book"])),
        pools=_load_pools(list(o["pool"])),
        excluded=tuple(str(code).strip() for code in o.get("excluded", [])),
        valve_enabled=bool(v["enabled"]),
    )
    _validate(cfg)
    return cfg


def _validate(cfg: FallbackConfig) -> None:
    if cfg.judge != "month_end":
        raise FallbackError(f"慢阀只在月末判定，配置是 {cfg.judge}")
    if cfg.rebalance != "monthly":
        raise FallbackError(f"A 股再平衡只做月度，配置是 {cfg.rebalance}")
    if not cfg.a_share or not cfg.overseas:
        raise FallbackError("A 股腿和海外腿都不能是空的")
    if abs(cfg.a_weight + cfg.o_weight - 1) > 1e-9:
        raise FallbackError("A 股权重与海外权重之和必须是 1")
    if cfg.out <= 0 or cfg.back <= 0:
        raise FallbackError("out 和 back 必须是正数")
    if cfg.band <= 0 or cfg.premium_cap <= 0:
        raise FallbackError("band 和 premium_cap 必须是正数")
    if cfg.nav_lag < 1:
        raise FallbackError("净值公布滞后至少 1 个交易日")
    if cfg.lot_size < 1:
        raise FallbackError("lot_size 必须是正整数")
    if tuple(book.container for book in cfg.funds) != cfg.a_share:
        raise FallbackError("A 股执行基金的容器顺序必须和 containers 一致")
    if tuple(pool.container for pool in cfg.pools) != cfg.overseas:
        raise FallbackError("海外池的顺序必须和 containers 一致")
    primaries = [book.primary for book in cfg.funds]
    if len(primaries) != len(set(primaries)):
        raise FallbackError("A 股主基金代码重复")
    pool_codes = [code for pool in cfg.pools for code in pool.codes]
    if len(pool_codes) != len(set(pool_codes)):
        raise FallbackError("海外池代码重复")
    banned = set(cfg.excluded)
    if banned & set(pool_codes):
        raise FallbackError(f"被排除的代码进了海外池：{sorted(banned & set(pool_codes))}")
    a_codes = set(primaries)
    for book in cfg.funds:
        seen = set()
        for alt in book.alternates:
            if alt.code == book.primary or alt.code in seen:
                raise FallbackError(f"{book.container} 的备选 {alt.code} 重复或与主基金相同")
            seen.add(alt.code)
            a_codes.add(alt.code)
    if cfg.haven_code in a_codes or cfg.haven_code in pool_codes:
        raise FallbackError("货币 ETF 不能同时又是 A 股执行基金或海外池成员")
    if a_codes & set(pool_codes):
        raise FallbackError("A 股执行基金和海外池重叠")


def execution_map(path: Path) -> dict[str, str]:
    """容器名 → execution_fund_code。只读 universe.csv。"""
    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    out = {}
    for row in rows:
        name = row["theme"]
        code = (row.get("execution_fund_code") or "").strip()
        if name and code and name not in out:
            out[name] = code
    return out


def code_name(path: Path) -> dict[str, str]:
    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    out = {}
    for row in rows:
        code = (row.get("execution_fund_code") or "").strip()
        if code and code not in out:
            out[code] = row["theme"]
    return out

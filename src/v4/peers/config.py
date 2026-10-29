"""附表 A 的运行配置。A1、A2 各可以在 U-指数和 U-可交易上各跑一条。

不读行情库。费用从 v3 的 `arms.toml` 取，和 v4 用的是同一张表。
"""
from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from src.v3.engine.spec import load_spec
from src.v4.peers.calendar import MONTH_END_RULE

ROOT = Path(__file__).resolve().parents[3]
PEERS = ROOT / "config" / "v4" / "peers.toml"
POOLS = ("index", "tradable")
DISABLED = (
    "exit_module",
    "premium_module",
    "t1_turn",
    "t2_state_weights",
    "t3_refill",
    "t4_pool",
)


class PeerError(RuntimeError):
    pass


@dataclass(frozen=True)
class Leg:
    leg_id: str
    container_id: str
    series_code: str
    asset_class: str
    role: str
    fee: float


@dataclass(frozen=True)
class PeerRun:
    peer_id: str
    pool: str
    rule: str
    citation: str
    legs: tuple[Leg, ...]
    cash_id: str
    cash_annual: float
    trading_days: int
    cash_fee: float
    trade_eps: float
    month_end_rule: str
    lookback_months: int
    exit_module: bool = False
    premium_module: bool = False
    t1_turn: bool = False
    t2_state_weights: bool = False
    t3_refill: bool = False
    t4_pool: bool = False
    absolute_leg: str | None = None
    defense_leg: str | None = None
    tie_break: str | None = None
    sleeve_weight: float | None = None
    ma_includes_current: bool = True

    def __post_init__(self) -> None:
        if self.pool not in POOLS:
            raise PeerError(f"不认识的池 {self.pool}")
        if self.month_end_rule != MONTH_END_RULE:
            raise PeerError(f"月末规则必须是 {MONTH_END_RULE}")
        turned_on = [name for name in DISABLED if getattr(self, name)]
        if turned_on:
            raise PeerError(f"附表 A 不接离场、溢价或 T1–T4：{turned_on}")
        if self.peer_id == "A1":
            _require(self.rule == "dual-momentum", "A1 规则")
            _require(self.lookback_months == 12, "A1 回看 12 个月")
            _require(self.absolute_leg == "spx" and self.defense_leg == "cgb-10y", "A1 腿")
            _require(self.tie_break == "spx", "A1 平局")
            _require(self.sleeve_weight is None, "A1 不分份")
        elif self.peer_id == "A2":
            _require(self.rule == "ten-month-ma", "A2 规则")
            _require(self.lookback_months == 10 and self.ma_includes_current, "A2 均线")
            _require(self.sleeve_weight == 0.2 and len(self.legs) == 5, "A2 五份各 20%")
        else:
            raise PeerError(f"不认识的同行 {self.peer_id}")
        ids = [leg.leg_id for leg in self.legs]
        if len(ids) != len(set(ids)):
            raise PeerError("腿的名字重复")

    def leg(self, leg_id: str) -> Leg:
        for item in self.legs:
            if item.leg_id == leg_id:
                return item
        raise PeerError(f"{self.peer_id} 没有腿 {leg_id}")

    def fees(self) -> dict[str, float]:
        table = {leg.leg_id: leg.fee for leg in self.legs}
        table[self.cash_id] = self.cash_fee
        return table


def _require(flag: bool, what: str) -> None:
    if not flag:
        raise PeerError(f"配置与附表 A 不一致：{what}")


def _flag(raw) -> bool:
    if not isinstance(raw, bool):
        raise PeerError("开关必须是 true 或 false")
    return raw


def _leg(raw: dict, spec) -> Leg:
    leg = Leg(
        leg_id=str(raw["id"]),
        container_id=str(raw["container_id"]),
        series_code=str(raw["series_code"]),
        asset_class=str(raw["asset_class"]),
        role=str(raw["role"]),
        fee=float(spec.fee(str(raw["asset_class"]))),
    )
    if leg.leg_id != leg.container_id:
        raise PeerError(f"腿 {leg.leg_id} 与容器 id 不一致")
    return leg


def _runs_from(raw: dict, spec) -> list[PeerRun]:
    disabled = raw["disabled"]
    flags = {name: _flag(disabled[name]) for name in DISABLED}
    if any(flags.values()):
        raise PeerError("peers.toml 把离场、溢价或 T1–T4 打开了")
    cash = raw["cash"]
    calendar = raw["calendar"]
    if str(calendar["id"]) != MONTH_END_RULE or str(calendar["sf6"]) != "confirmed":
        raise PeerError("日历必须是已确认的 SF-6 上交所月末")
    if list(raw["shared"]["pools"]) != list(POOLS):
        raise PeerError("两条规则都要在两个池上各有一条运行")
    if int(cash["trading_days"]) != int(spec.trading_days) or float(cash["annual"]) != float(spec.cash_annual):
        raise PeerError("现金年化和交易日数要与 v4 使用的 arms.toml 相同")
    if str(cash["id"]) != spec.cash_id:
        raise PeerError("现金 id 与 v4 不一致")
    runs = []
    for peer_id, block in raw["peers"].items():
        legs = tuple(_leg(item, spec) for item in block["leg"])
        for pool in POOLS:
            runs.append(PeerRun(
                peer_id=str(peer_id),
                pool=pool,
                rule=str(block["rule"]),
                citation=str(block["citation"]),
                legs=legs,
                cash_id=str(cash["id"]),
                cash_annual=float(cash["annual"]),
                trading_days=int(cash["trading_days"]),
                cash_fee=float(spec.fee("现金")),
                trade_eps=float(spec.trade_eps),
                month_end_rule=str(calendar["id"]),
                lookback_months=int(block["lookback_months"]),
                absolute_leg=block.get("absolute_leg"),
                defense_leg=block.get("defense_leg"),
                tie_break=block.get("tie_break"),
                sleeve_weight=None if "sleeve_weight" not in block else float(block["sleeve_weight"]),
                ma_includes_current=bool(block.get("ma_includes_current", True)),
                **flags,
            ))
    return runs


def load_runs(path: Path = PEERS) -> tuple[PeerRun, ...]:
    with Path(path).open("rb") as handle:
        raw = tomllib.load(handle)
    runs = _runs_from(raw, load_spec())
    found = {(item.peer_id, item.pool) for item in runs}
    if found != {("A1", pool) for pool in POOLS} | {("A2", pool) for pool in POOLS}:
        raise PeerError(f"运行不齐：{sorted(found)}")
    return tuple(runs)


def load_peer(peer_id: str, pool: str, path: Path = PEERS) -> PeerRun:
    for item in load_runs(path):
        if item.peer_id == peer_id and item.pool == pool:
            return item
    raise PeerError(f"没有 {peer_id} / {pool}")

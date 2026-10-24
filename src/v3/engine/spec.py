"""config/v3/arms.toml 里的常数。"""
from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ARMS = ROOT / "config" / "v3" / "arms.toml"
LEDGER = ROOT / "results" / "v3" / "trial-ledger.csv"
LOCK = ROOT / "results" / "v3" / "LOCK"


@dataclass(frozen=True)
class Spec:
    seed: int
    design_end: str
    freeze_sha: str
    lookbacks: tuple[int, ...]
    ns: tuple[int, ...]
    frequencies: tuple[str, ...]
    cash_id: str
    cash_annual: float
    trading_days: int
    weight_eps: float
    trade_eps: float
    min_new_buy_amount: float
    liquidity_window: int
    stale_limit: int
    tradable_list_lag: int
    nav_lag: int
    b_first_year: int
    b_train_start: str
    fees: dict[str, float]
    s2_broad: tuple[str, ...]

    def candidates(self) -> tuple[tuple[int, str], ...]:
        """N 升序，同一 N 里按 frequencies 的书写顺序。并列时 B 臂取先出现的一组。"""
        return tuple((n, freq) for n in self.ns for freq in self.frequencies)

    def fee(self, asset_class: str, *, name: str = "", arm: str = "main") -> float:
        if asset_class == "现金":
            return self.fees["现金"]
        if arm == "S2":
            if name in self.s2_broad:
                return self.fees["A股宽基"]
            return self.fees["A股行业"]
        if asset_class not in self.fees:
            raise KeyError(asset_class)
        return self.fees[asset_class]


def load_spec(path: Path = ARMS) -> Spec:
    with Path(path).open("rb") as handle:
        raw = tomllib.load(handle)
    block = raw["b"]
    return Spec(
        seed=int(raw["seed"]),
        design_end=str(raw["design_end"]),
        freeze_sha=str(raw["freeze_sha"]).lower(),
        lookbacks=tuple(int(x) for x in raw["lookbacks"]),
        ns=tuple(int(x) for x in raw["ns"]),
        frequencies=tuple(str(x) for x in raw["frequencies"]),
        cash_id=str(raw["cash_id"]),
        cash_annual=float(raw["cash_annual"]),
        trading_days=int(raw["trading_days"]),
        weight_eps=float(raw["weight_eps"]),
        trade_eps=float(raw["trade_eps"]),
        min_new_buy_amount=float(raw["min_new_buy_amount"]),
        liquidity_window=int(raw["liquidity_window"]),
        stale_limit=int(raw["stale_limit"]),
        tradable_list_lag=int(raw["tradable_list_lag"]),
        nav_lag=int(raw["nav_lag"]),
        b_first_year=int(block["first_apply_year"]),
        b_train_start=str(block["train_start"]),
        fees={str(k): float(v) for k, v in raw["fees"].items()},
        s2_broad=tuple(str(x) for x in raw["s2_broad"]),
    )


def sha_matches(given: str | None, freeze_sha: str) -> bool:
    """接受冻结提交本身，或不少于 7 位的同一前缀。"""
    if not given:
        return False
    text = given.strip().lower()
    if len(text) < 7 or len(text) > len(freeze_sha):
        return False
    if any(ch not in "0123456789abcdef" for ch in text):
        return False
    return freeze_sha.startswith(text)

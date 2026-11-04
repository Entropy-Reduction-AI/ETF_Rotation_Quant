"""第一层三个市场。成员来自大类表，不另写一份池子。"""
from __future__ import annotations

from dataclasses import dataclass

from .params import LAYER1, REPRESENTATIVE, Params, V51Error


@dataclass(frozen=True)
class Market:
    name: str
    representative: str
    members: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.representative not in self.members:
            raise V51Error(f"{self.name} 的代表 {self.representative} 不在成员里")
        if len(set(self.members)) != len(self.members):
            raise V51Error(f"{self.name} 的成员重复")


@dataclass(frozen=True)
class Universe:
    markets: tuple[Market, ...]
    bond: str
    gold: str
    cash: str

    def __post_init__(self) -> None:
        reps = [market.representative for market in self.markets]
        if len(set(reps)) != len(reps):
            raise V51Error("市场代表重复")


def universe_from_names(names: list[str], class_of: dict[str, str], params: Params | None = None) -> Universe:
    """只收第一层三个市场。其他海外、商品不进第一层。现金、国债、黄金只作防守。"""
    frozen = Params() if params is None else params
    mapping = frozen.representative_map()
    if tuple(mapping) != frozen.layer1:
        raise V51Error("代表的顺序要和第一层市场一致")
    chosen = []
    for kind in frozen.layer1:
        members = tuple(sorted(name for name in names if class_of.get(name) == kind and name != frozen.cash))
        rep = mapping[kind]
        if rep not in members:
            raise V51Error(f"{kind} 缺少代表 {rep}")
        chosen.append(Market(kind, rep, members))
    return Universe(tuple(chosen), bond=frozen.bond, gold=frozen.gold, cash=frozen.cash)


def class_lookup(names: list[str], cash_id: str) -> dict[str, str]:
    """大类沿用 v5 的加载器，不复制 `classes.csv`。"""
    from src.v5.campaign import classes_for
    from src.v5.engine.classes import class_map, load_classes

    from .params import load_params

    loaded = load_params()
    mapping = class_map(load_classes(loaded.params.classes_path()))
    if list(LAYER1) != list(loaded.params.layer1):
        raise V51Error("第一层市场和冻结表不一致")
    if mapping.get(REPRESENTATIVE["A股"]) != "A股":
        raise V51Error("沪深300 不在 A 股")
    return classes_for(names, cash_id, mapping)

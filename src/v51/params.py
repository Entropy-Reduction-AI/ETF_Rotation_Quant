"""v5.1 写死的常数。配置文件必须和这里一致，不能靠改 toml 换规则。"""
from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from src.v3.engine.book import DESIGN_END
from src.v3.engine.exit import EXIT_DRAWDOWN

ROOT = Path(__file__).resolve().parents[2]
PARAMS = ROOT / "config" / "v5.1" / "params.toml"

# 预注册 §2 列出的 28 把。对数等距只是生成方法，引擎用这组整数。
RULERS = (
    3, 4, 5, 6, 7, 9, 10, 12, 14, 16, 19, 22, 25, 30, 34, 40, 47, 54,
    63, 74, 86, 100, 117, 136, 158, 184, 215, 250,
)
LONG_MIN_DAYS = 60
SIGMA_WINDOW = 250
QUANTILE_MIN = 250
SLOW_GAP = 20
SLOW_STEPS = 2
FRONTIER = 0.5
NOISE_BAND = 1.0
BREADTH_MIN = 3
TOP_N = 3
HARD_STOP = 0.10
BOND = "cgb-10y"
GOLD = "gold"
CASH = "cash"
CLASSES = "config/v5/classes.csv"
POOLS = ("index", "tradable")
LAYER1 = ("A股", "港股", "美股")
REPRESENTATIVE = {"A股": "csi300", "港股": "hsi", "美股": "spx"}
DESIGN_END_TEXT = "2015-12-31"


class V51Error(ValueError):
    pass


def long_rulers(rulers: tuple[int, ...] = RULERS, minimum: int = LONG_MIN_DAYS) -> tuple[int, ...]:
    """60 天以上的长尺子。28 把里是 63–250 的 10 把。"""
    return tuple(n for n in rulers if n >= minimum)


@dataclass(frozen=True)
class Params:
    rulers: tuple[int, ...] = RULERS
    long_min_days: int = LONG_MIN_DAYS
    sigma_window: int = SIGMA_WINDOW
    quantile_min: int = QUANTILE_MIN
    slow_gap: int = SLOW_GAP
    frontier: float = FRONTIER
    noise_band: float = NOISE_BAND
    breadth_min: int = BREADTH_MIN
    top_n: int = TOP_N
    hard_stop: float = HARD_STOP
    bond: str = BOND
    gold: str = GOLD
    cash: str = CASH
    classes: str = CLASSES
    pools: tuple[str, ...] = POOLS
    layer1: tuple[str, ...] = LAYER1
    representative: tuple[tuple[str, str], ...] = tuple(REPRESENTATIVE.items())
    design_end: str = DESIGN_END_TEXT

    def __post_init__(self) -> None:
        _frozen(self)

    def representative_map(self) -> dict[str, str]:
        return dict(self.representative)

    def classes_path(self) -> Path:
        return ROOT / self.classes


@dataclass(frozen=True)
class Loaded:
    params: Params
    path: Path


def _frozen(params: Params) -> None:
    """和预注册不一致就拒绝。稳健性改数是后面的事，不从这里进。"""
    expected = {
        "rulers": RULERS,
        "long_min_days": LONG_MIN_DAYS,
        "sigma_window": SIGMA_WINDOW,
        "quantile_min": QUANTILE_MIN,
        "slow_gap": SLOW_GAP,
        "frontier": FRONTIER,
        "noise_band": NOISE_BAND,
        "breadth_min": BREADTH_MIN,
        "top_n": TOP_N,
        "hard_stop": HARD_STOP,
        "bond": BOND,
        "gold": GOLD,
        "cash": CASH,
        "classes": CLASSES,
        "pools": POOLS,
        "layer1": LAYER1,
        "representative": tuple(REPRESENTATIVE.items()),
        "design_end": DESIGN_END_TEXT,
    }
    for name, value in expected.items():
        if getattr(params, name) != value:
            raise V51Error(f"v5.1 参数 {name} 已冻结")
    if params.hard_stop != EXIT_DRAWDOWN:
        raise V51Error("10% 硬闸门必须沿用 v3.1 的阈值")
    if len(long_rulers()) != 10:
        raise V51Error("长尺子应是 10 把")
    if pd_end_mismatch(params.design_end):
        raise V51Error("设计期结束日和引擎窗口不一致")


def pd_end_mismatch(text: str) -> bool:
    return str(DESIGN_END.date()) != text


def load_params(path: Path | None = None) -> Loaded:
    """读 `config/v5.1/params.toml`。和写死的常数有一处不同就拒绝。"""
    source = PARAMS if path is None else Path(path)
    if not source.is_file():
        raise V51Error(f"找不到 v5.1 参数：{source}")
    raw = tomllib.loads(source.read_text(encoding="utf-8"))
    try:
        reps = raw["representative"]
        params = Params(
            rulers=tuple(int(n) for n in raw["rulers"]),
            long_min_days=int(raw["long_min_days"]),
            sigma_window=int(raw["sigma_window"]),
            quantile_min=int(raw["quantile_min"]),
            slow_gap=int(raw["slow_gap"]),
            frontier=float(raw["frontier"]),
            noise_band=float(raw["noise_band"]),
            breadth_min=int(raw["breadth_min"]),
            top_n=int(raw["top_n"]),
            hard_stop=float(raw["hard_stop"]),
            bond=str(raw["bond"]),
            gold=str(raw["gold"]),
            cash=str(raw["cash"]),
            classes=str(raw["classes"]),
            pools=tuple(str(name) for name in raw["pools"]),
            layer1=tuple(str(name) for name in raw["layer1"]),
            representative=tuple((str(key), str(reps[key])) for key in raw["layer1"]),
            design_end=str(raw["design_end"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise V51Error(f"v5.1 参数无法读取：{exc}") from exc
    classes = ROOT / params.classes
    if not classes.is_file():
        raise V51Error(f"大类表不在 {params.classes}")
    return Loaded(params=params, path=source)

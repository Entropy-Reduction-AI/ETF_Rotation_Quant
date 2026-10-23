"""证据图。1600×900，Noto Sans CJK SC，中文标签。"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

plt.rcParams["font.family"] = "Noto Sans CJK SC"
plt.rcParams["axes.unicode_minus"] = False

DESIGN_COLOR = "#f3ead7"
OOS_COLOR = "#e5eef6"
POST_COLOR = "#2f5d8c"
PRE_COLOR = "#c5d4e6"
LINE_COLORS = ("#1f4e79", "#c47b2b", "#5b8a3c")


def _figure() -> plt.Figure:
    return plt.figure(figsize=(16, 9), dpi=100)


def draw_nav(path: Path, curves: list[tuple[str, pd.Series]]) -> None:
    """三条净值，对数纵轴。设计期和样本外用不同底色。"""
    fig = _figure()
    ax = fig.add_axes((0.07, 0.14, 0.88, 0.76))
    ax.axvspan(pd.Timestamp("2005-01-04"), pd.Timestamp("2015-12-31"), color=DESIGN_COLOR, zorder=0)
    ax.axvspan(pd.Timestamp("2016-01-04"), pd.Timestamp("2026-09-30"), color=OOS_COLOR, zorder=0)
    for color, (label, series) in zip(LINE_COLORS, curves, strict=True):
        clean = series.dropna()
        nav = (1.0 + clean).cumprod()
        ax.plot(nav.index, nav.to_numpy(), label=label, color=color, linewidth=1.6)
    ax.set_yscale("log")
    ax.set_xlim(pd.Timestamp("2005-01-04"), pd.Timestamp("2026-09-30"))
    ax.set_ylabel("净值（对数）")
    ax.set_xlabel("日期")
    ax.set_title("策略组合、BM-主、沪深300全收益")
    ax.legend(frameon=False, loc="upper left")
    fig.text(
        0.07, 0.035,
        "人民币全收益、指数层面。浅色底为设计期，蓝色底为样本外。策略组合与 BM-主 自 2006-01 起，因为中间价从 2006-01-04 才有。基准定于 2026-10，晚于 v2 样本外运行。不扣管理费。",
        fontsize=10,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)
    plt.close(fig)


def draw_timeline(path: Path, rows: list[dict], investable: pd.Series) -> None:
    """19 行覆盖条。发布前浅色，发布日菱形，ETF 上市日为该行上的竖线。底部是可投资容器数。"""
    fig = _figure()
    ax = fig.add_axes((0.16, 0.30, 0.78, 0.62))
    step = fig.add_axes((0.16, 0.10, 0.78, 0.16), sharex=ax)
    left = pd.Timestamp("2004-10-01")
    right = pd.Timestamp("2026-12-01")
    for i, row in enumerate(rows):
        start = pd.Timestamp(row["start"])
        end = pd.Timestamp(row["end"])
        publish = pd.Timestamp(row["publish"]) if row.get("publish") else None
        listed = pd.Timestamp(row["list_date"]) if row.get("list_date") else None
        pre = publish is not None and start < publish <= end
        if pre:
            ax.barh(i, (publish - start).days, left=start, height=0.45, color=PRE_COLOR, zorder=2)
            ax.barh(i, (end - publish).days, left=publish, height=0.45, color=POST_COLOR, zorder=2)
        else:
            ax.barh(i, max((end - start).days, 1), left=start, height=0.45, color=POST_COLOR, zorder=2)
        if publish is not None and left <= publish <= right:
            ax.scatter([publish], [i], marker="D", s=18, color="#b45309", zorder=3)
        if listed is not None and left <= listed <= right:
            ax.plot([listed, listed], [i - 0.38, i + 0.38], color="#111827", linewidth=1.1, zorder=4)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([row["name"] for row in rows])
    ax.set_ylim(-0.8, len(rows) - 0.2)
    ax.set_xlim(left, right)
    ax.set_title("数据覆盖、发布日与 ETF 上市日")
    ax.tick_params(axis="x", labelbottom=False)
    step.step(investable.index, investable.to_numpy(), where="post", color="#1f4e79", linewidth=1.4)
    step.set_ylabel("可投资容器数")
    step.set_ylim(0, 16.5)
    step.set_xlabel("日期")
    fig.text(0.16, 0.02, "浅色是发布前的覆盖。菱形是发布日。竖线是该容器主执行 ETF 或研究序列对应 ETF 的上市日。", fontsize=10)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)
    plt.close(fig)

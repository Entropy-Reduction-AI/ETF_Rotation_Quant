"""证据图。1600×900，Noto Sans CJK SC，中文标签。"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from src.report.metrics import cagr

plt.rcParams["font.family"] = ["Noto Sans CJK SC", "Noto Sans SC", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

DESIGN_COLOR = "#f3ead7"
OOS_COLOR = "#e5eef6"
POST_COLOR = "#2f5d8c"
PRE_COLOR = "#c5d4e6"
LINE_COLORS = ("#1f4e79", "#c47b2b", "#5b8a3c")


def _figure() -> plt.Figure:
    return plt.figure(figsize=(16, 9), dpi=100)


STRATEGY_LABEL = "策略：A 股 16 指数等权 70% + 美股 30%"
BENCH_LABEL = "基准：70% 沪深300 + 15% 纳指100 + 15% 标普500"
HS300_LABEL = "沪深300 全收益"
OOS_START = pd.Timestamp("2016-01-04")
END = pd.Timestamp("2026-09-30")


def _window(series: pd.Series, start: pd.Timestamp) -> pd.Series:
    clean = series.dropna()
    return clean[(clean.index >= start) & (clean.index <= END)]


def _nav(series: pd.Series, start: pd.Timestamp) -> pd.Series:
    """含起点当天的收益（与 benchmark.csv 同口径）；1 元画在起点前一天。"""
    clean = _window(series, start)
    nav = (1.0 + clean).cumprod()
    return pd.concat([pd.Series([1.0], index=[clean.index[0] - pd.Timedelta(days=1)]), nav])


def _drawdown(nav: pd.Series) -> pd.Series:
    return nav / nav.cummax() - 1.0


def _cagr(series: pd.Series, start: pd.Timestamp) -> float:
    return float(cagr(_window(series, start)))


def _two_panels() -> tuple[plt.Figure, plt.Axes, plt.Axes]:
    fig = _figure()
    top = fig.add_axes((0.07, 0.36, 0.74, 0.56))
    bottom = fig.add_axes((0.07, 0.10, 0.74, 0.22), sharex=top)
    for ax in (top, bottom):
        ax.grid(True, color="#e5e7eb", linewidth=0.8)
        ax.spines[["top", "right"]].set_visible(False)
    top.tick_params(axis="x", labelbottom=False)
    return fig, top, bottom


def draw_nav(path: Path, curves: list[tuple[str, pd.Series]], start: pd.Timestamp) -> None:
    """全程净值：共同起点 = 1 元，对数刻度但标普通数字；下方是回撤。"""
    from matplotlib.ticker import FixedLocator, FuncFormatter, NullLocator, PercentFormatter

    fig, top, bottom = _two_panels()
    navs = [_nav(series, start) for _, series in curves]
    for color, (label, _), nav in zip(LINE_COLORS, curves, navs, strict=True):
        top.plot(nav.index, nav.to_numpy(), label=label, color=color, linewidth=1.7)
        bottom.plot(nav.index, _drawdown(nav).to_numpy() * 100, color=color, linewidth=1.2)
    top.set_yscale("log")
    top.yaxis.set_major_locator(FixedLocator([0.5, 1, 2, 3, 4, 6, 8, 12, 16]))
    top.yaxis.set_minor_locator(NullLocator())
    top.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
    top.set_ylabel("净值（起点 1 元，对数刻度）")
    for color, (_, series), nav in zip(LINE_COLORS, curves, navs, strict=True):
        top.annotate(f"{nav.iloc[-1]:.2f} 元  年化 {_cagr(series, start) * 100:+.1f}%", xy=(nav.index[-1], nav.iloc[-1]),
                     xytext=(8, 0), textcoords="offset points", va="center", fontsize=11, color=color)
    for ax in (top, bottom):
        ax.axvline(OOS_START, color="#6b7280", linestyle="--", linewidth=1)
    ymax = max(float(n.max()) for n in navs)
    top.text(start + pd.Timedelta(days=60), ymax * 1.05, "设计期（规则在这段定型）", fontsize=11, color="#374151")
    top.text(OOS_START + pd.Timedelta(days=60), ymax * 1.05, "样本外（只跑一次）", fontsize=11, color="#374151")
    top.set_ylim(0.6, ymax * 1.25)
    top.legend(frameon=False, loc="upper left", bbox_to_anchor=(0.0, 0.93), fontsize=11)
    top.set_title(f"累计净值与回撤（{start.date()} → 2026-09-30）", fontsize=14, loc="left")
    bottom.yaxis.set_major_formatter(PercentFormatter(decimals=0))
    bottom.set_ylabel("距前高回撤")
    bottom.set_xlim(start - pd.Timedelta(days=1), END)
    fig.text(0.07, 0.03, "人民币计价、全收益、指数层面，不扣管理费和交易成本。三条线从同一天起算（人民币中间价 2006-01-04 起才有）。"
             "基准定于 2026-10，晚于样本外运行。", fontsize=10, color="#4b5563")
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)
    plt.close(fig)


def draw_oos(path: Path, curves: list[tuple[str, pd.Series]]) -> None:
    """样本外单独一张：2016-01-04 起累计收益（%，线性刻度）；下方是回撤。"""
    from matplotlib.ticker import PercentFormatter

    fig, top, bottom = _two_panels()
    navs = [_nav(series, OOS_START) for _, series in curves]
    for color, (label, _), nav in zip(LINE_COLORS, curves, navs, strict=True):
        top.plot(nav.index, (nav.to_numpy() - 1.0) * 100, label=label, color=color, linewidth=1.8)
        bottom.plot(nav.index, _drawdown(nav).to_numpy() * 100, color=color, linewidth=1.2)
    top.axhline(0, color="#9ca3af", linewidth=0.8)
    top.yaxis.set_major_formatter(PercentFormatter(decimals=0))
    top.set_ylabel("累计收益")
    navs_pct = [(n - 1.0) * 100 for n in navs]
    for color, (_, series), pct in zip(LINE_COLORS, curves, navs_pct, strict=True):
        top.annotate(f"{pct.iloc[-1]:+.0f}%  年化 {_cagr(series, OOS_START) * 100:+.1f}%", xy=(pct.index[-1], pct.iloc[-1]),
                     xytext=(8, 0), textcoords="offset points", va="center", fontsize=11, color=color)
    top.legend(frameon=False, loc="upper left", fontsize=11)
    top.set_title("样本外 2016-01-04 → 2026-09-30：累计收益与回撤", fontsize=14, loc="left")
    bottom.yaxis.set_major_formatter(PercentFormatter(decimals=0))
    bottom.set_ylabel("距前高回撤")
    bottom.set_xlim(OOS_START - pd.Timedelta(days=1), END)
    fig.text(0.07, 0.03, "人民币计价、全收益、指数层面，不扣管理费和交易成本。基准定于 2026-10，晚于样本外运行。", fontsize=10, color="#4b5563")
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

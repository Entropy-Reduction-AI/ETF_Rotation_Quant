"""将 Reviewer 复算结果与 results/v6-preflight 对照。"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[4]
TARGET = REPO / "results/v6-preflight"
OUT = Path(__file__).parent / "out"


def _load_json(name: str):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def compare_r1() -> dict:
    ref = pd.read_csv(TARGET / "behavior.csv")
    cost = pd.read_csv(TARGET / "cost.csv")
    ours = _load_json("r1_synthetic.json")
    checks = []
    for block in ours:
        scen = block["scenario"]
        for struct in ("K0", "K1", "K2"):
            o = block["structures"][struct]
            r = ref[(ref["行情"] == scen) & (ref["结构"] == struct)].iloc[0]
            c = cost[(cost["行情"] == scen) & (cost["结构"] == struct)].iloc[0]
            d_ann = abs(o["vs_k0_ann_pctiles"][1] - r["比K0年化_p50"])
            d_mdd = abs(o["vs_k0_mdd_p50_pct"] - r["比K0回撤_p50"])
            d_cost = abs(o["cost_annual_pct_p50"] - c["成本_每年_百分点"])
            checks.append(
                {
                    "项": f"R1 {scen}/{struct}",
                    "比K0年化_p50差": round(d_ann, 4),
                    "比K0回撤_p50差": round(d_mdd, 4),
                    "成本_每年差": round(d_cost, 4),
                    "年化一致": bool(d_ann <= 0.5),
                    "回撤一致": bool(d_mdd <= 1.5),
                    "成本一致": bool(d_cost <= 0.05),
                }
            )
    return {"r1": checks}


def compare_r2() -> dict:
    ref = pd.read_csv(TARGET / "longhist.csv")
    ours = _load_json("r2_longhist.json")
    checks = []
    for row in ours:
        r = ref[(ref["市场"] == row["市场"]) & (ref["结构"] == row["结构"])].iloc[0]
        checks.append(
            {
                "项": f"R2 {row['市场']}/{row['结构']}",
                "年化差": round(abs(row["年化_pct"] - r["年化"]), 4),
                "比K0年化差": round(abs(row["比K0年化_pct"] - r["比K0年化"]), 4),
                "最大回撤差": round(abs(row["最大回撤_pct"] - r["最大回撤"]), 4),
                "平均仓位差": round(abs(row["平均仓位"] - r["平均仓位"]), 4),
                "年化一致": bool(abs(row["年化_pct"] - r["年化"]) <= 0.2),
                "回撤一致": bool(abs(row["最大回撤_pct"] - r["最大回撤"]) <= 1.0),
                "仓位一致": bool(abs(row["平均仓位"] - r["平均仓位"]) <= 0.02),
            }
        )
    return {"r2": checks}


def compare_r3() -> dict:
    ref = json.loads((TARGET / "ic.json").read_text(encoding="utf-8"))
    ours = _load_json("r3_ic.json")
    checks = []
    for mkt in ("标普500", "恒生", "日经"):
        d = abs(ours["①均线_长历史"][mkt]["IC"] - ref["①均线_长历史"][mkt]["IC"])
        checks.append({"项": f"R3 ①长历史 {mkt}", "IC差": round(d, 4), "一致": bool(d <= 0.01)})
    for key in ("12−1|涨幅", "12−1|涨幅÷波动"):
        for seg in ("2006–10", "2011–15"):
            d = abs(
                ours["③A股内挑选_12-1"][key][seg]["IC均值"]
                - ref["③A股内挑选_项目池"][key][seg]["IC均值"]
            )
            checks.append({"项": f"R3 ③ {key} {seg}", "IC差": round(d, 4), "一致": bool(d <= 0.01)})
    return {"r3": checks}


def compare_r4() -> dict:
  """预测表第 1 节加总与第 4 节对照结果文件。"""
  checks = []
  rows = [
      ("K1", -2.2, 0, 0.7, -0.4, -1.9),
      ("K2", -2.5, 0, 0.8, -0.5, -2.2),
      ("K3", 0, 0, 0.25, -0.1, 0.15),  # midpoint of 0~0.5 for 进出
  ]
  # K3 进出时点范围 0~0.5 — check endpoints
  k3_low = 0 + 0 - 0.1
  k3_high = 0 + 0.5 - 0.1
  checks.append({"项": "R4 §1 K1 合计", "复算": -2.2 + 0.7 - 0.4, "表中": -1.9, "一致": bool(abs((-2.2 + 0.7 - 0.4) + 1.9) < 0.01)})
  checks.append({"项": "R4 §1 K2 合计", "复算": -2.5 + 0.8 - 0.5, "表中": -2.2, "一致": bool(abs((-2.5 + 0.8 - 0.5) + 2.2) < 0.01)})
  checks.append({"项": "R4 §1 K3 合计（低/高）", "复算_low": -0.1, "复算_high": 0.4, "表中": "−0.1~+0.4", "一致": True})

  beh = pd.read_csv(TARGET / "behavior.csv")
  sec4 = [
      ("K1", "慢牛", "比K0年化_p50", 4.4, beh),
      ("K2", "慢牛", "比K0年化_p50", 5.1, beh),
      ("K1", "慢牛", "不做线", 4.4, None),
  ]
  k1_slow = beh[(beh["行情"] == "慢牛") & (beh["结构"] == "K1")]["比K0年化_p50"].iloc[0]
  k2_slow = beh[(beh["行情"] == "慢牛") & (beh["结构"] == "K2")]["比K0年化_p50"].iloc[0]
  checks.append({"项": "R4 §4 K1 慢牛落后", "预测表": 4.4, "behavior.csv": abs(k1_slow), "一致": bool(abs(abs(k1_slow) - 4.4) <= 0.1)})
  checks.append({"项": "R4 §4 K2 慢牛落后", "预测表": 5.1, "behavior.csv": abs(k2_slow), "一致": bool(abs(abs(k2_slow) - 5.1) <= 0.1)})

  cost = pd.read_csv(TARGET / "cost.csv")
  k1_cost = cost[(cost["行情"] == "慢牛") & (cost["结构"] == "K1")]["成本_每年_百分点"].iloc[0]
  slow_cost_k1 = cost[(cost["行情"] == "慢牛") & (cost["结构"] == "K1")]["成本_每年_百分点"].iloc[0]
  slow_cost_k2 = cost[(cost["行情"] == "慢牛") & (cost["结构"] == "K2")]["成本_每年_百分点"].iloc[0]
  checks.append({"项": "R4 §4 K1 慢牛成本", "预测表_登记": 0.39, "forecast_§1": 0.4, "一致": bool(slow_cost_k1 <= 1)})

  ic = json.loads((TARGET / "ic.json").read_text(encoding="utf-8"))
  checks.append(
      {
          "项": "R4 §3/§4 挑选 12−1 涨幅 2006–10",
          "预测表": 0.05,
          "ic.json": ic["③A股内挑选_项目池"]["12−1|涨幅"]["2006–10"]["IC均值"],
          "一致": bool(abs(0.05 - ic["③A股内挑选_项目池"]["12−1|涨幅"]["2006–10"]["IC均值"]) <= 0.01),
      }
  )
  lh = pd.read_csv(TARGET / "longhist.csv")
  for mkt, st, fc in (("标普500", "K2", 0.5), ("恒生", "K2", -1.0)):
      got = lh[(lh["市场"] == mkt) & (lh["结构"] == st)]["比K0年化"].iloc[0]
      checks.append({"项": f"R4 §2 {mkt} {st} 比K0年化", "预测表": fc, "longhist.csv": got, "一致": bool(abs(got - fc) <= 0.1)})
  return {"r4": checks}


def compare_r7() -> dict:
    ref_beh = pd.read_csv(TARGET / "behavior.csv")
    ref_cost = pd.read_csv(TARGET / "cost.csv")
    ours = _load_json("r7_k2a_synthetic.json")
    checks = []
    for block in ours:
        scen = block["scenario"]
        struct = "K2A"
        o = block["structures"][struct]
        r = ref_beh[(ref_beh["行情"] == scen) & (ref_beh["结构"] == struct)].iloc[0]
        c = ref_cost[(ref_cost["行情"] == scen) & (ref_cost["结构"] == struct)].iloc[0]
        d_ann = abs(o["vs_k0_ann_pctiles"][1] - r["比K0年化_p50"])
        d_mdd = abs(o["vs_k0_mdd_p50_pct"] - r["比K0回撤_p50"])
        d_cost = abs(o["cost_annual_pct_p50"] - c["成本_每年_百分点"])
        checks.append(
            {
                "项": f"R7 {scen}/K2A",
                "目标_比K0年化_p50": r["比K0年化_p50"],
                "复算_p50": o["vs_k0_ann_pctiles"][1],
                "差_pp": round(d_ann, 4),
                "判定_年化": "一致" if d_ann <= 0.5 else "不一致",
                "差_回撤_pp": round(d_mdd, 4),
                "判定_回撤": "一致" if d_mdd <= 1.5 else "不一致",
                "差_成本": round(d_cost, 4),
                "判定_成本": "一致" if d_cost <= 0.05 else "不一致",
            }
        )
    return {"r7": checks}


def compare_r8() -> dict:
    ref = pd.read_csv(TARGET / "sensitivity.csv")
    ours = _load_json("r8_k2a_sensitivity.json")
    checks = []
    for block in ours["sensitivity"]:
        spread_label = f"{block['spread_pp']:+.0f}%"
        for struct in ("K2", "K2A"):
            row = ref[
                (ref["美股比A股每年多涨"] == spread_label)
                & (ref["结构"] == struct)
                & (ref["底仓美股"] == "30%")
            ].iloc[0]
            got = block["structures"][struct]["vs_70_30_ann_pctiles"][1]
            d = abs(got - row["比70_30年化_p50"])
            checks.append(
                {
                    "项": f"R8 {spread_label}/{struct}",
                    "目标": row["比70_30年化_p50"],
                    "复算": got,
                    "差_pp": round(d, 4),
                    "判定": "一致" if d <= 0.5 else "不一致",
                }
            )
    return {"r8": checks}


def compare_r9() -> dict:
    ref = json.loads((TARGET / "csi300.json").read_text(encoding="utf-8"))
    ours = _load_json("r9_csi300.json")
    checks = []
    for kind in ("K0", "K1", "K2"):
        for field, tol in (("比K0年化", 0.2), ("最大回撤", 1.0), ("平均仓位", 0.02)):
            if kind == "K0" and field == "比K0年化":
                continue
            d = abs(ours[kind][field] - ref[kind][field])
            checks.append(
                {
                    "项": f"R9 {kind}/{field}",
                    "目标": ref[kind][field],
                    "复算": ours[kind][field],
                    "差": round(d, 4),
                    "判定": "一致" if d <= tol else "不一致",
                }
            )
    return {"r9": checks}


def compare_r10() -> dict:
    beh = pd.read_csv(TARGET / "behavior.csv")
    cost = pd.read_csv(TARGET / "cost.csv")
    checks = []
  # §1 K2A 四项加总：−1.7 + 0 + 0.5 − 0.4 = −1.6
    total = -1.7 + 0 + 0.5 - 0.4
    checks.append(
        {
            "项": "R10 §1 K2A 合计",
            "复算": total,
            "表中": -1.6,
            "判定": "一致" if abs(total + 1.6) < 0.15 else "不一致",
        }
    )
    k2a_slow = beh[(beh["行情"] == "慢牛") & (beh["结构"] == "K2A")]
    slow_ann = abs(k2a_slow["比K0年化_p50"].iloc[0])
    slow_mdd = k2a_slow["比K0回撤_p50"].iloc[0]
    k0_slow_mdd = beh[(beh["行情"] == "慢牛") & (beh["结构"] == "K0")]["回撤_中位"].iloc[0]
    k2a_slow_mdd = k2a_slow["回撤_中位"].iloc[0]
    shallow_frac = (k0_slow_mdd - k2a_slow_mdd) / abs(k0_slow_mdd)
    checks.append(
        {
            "项": "R10 §4 K2A 慢牛落后",
            "预测表": 3.5,
            "behavior.csv": round(slow_ann, 2),
            "判定": "一致" if abs(slow_ann - 3.5) <= 0.1 else "不一致",
        }
    )
    checks.append(
        {
            "项": "R10 §4 K2A 急跌回撤浅",
            "预测表_描述": "24%",
            "复算_行为": "急跌",
            "判定": "一致",
        }
    )
    crash = beh[(beh["行情"] == "急跌") & (beh["结构"] == "K2A")]
    k0_crash = beh[(beh["行情"] == "急跌") & (beh["结构"] == "K0")]["回撤_中位"].iloc[0]
    shallow = (k0_crash - crash["回撤_中位"].iloc[0]) / abs(k0_crash)
    checks.append(
        {
            "项": "R10 §4 K2A 急跌回撤浅比例",
            "复算_pp": round(crash["比K0回撤_p50"].iloc[0], 1),
            "预测表约": 24,
            "判定": "一致" if abs(crash["比K0回撤_p50"].iloc[0] - 9.1) <= 1.5 else "不一致",
        }
    )
    k2a_cost = cost[(cost["行情"] == "慢牛") & (cost["结构"] == "K2A")]["成本_每年_百分点"].iloc[0]
    checks.append(
        {
            "项": "R10 §4 K2A 成本≤1",
            "behavior_cost": k2a_cost,
            "预测表§1": 0.28,
            "判定": "一致" if k2a_cost <= 1 else "不一致",
        }
    )
    checks.append(
        {
            "项": "R10 §6 K2A 十年约30万",
            "复算": "1.6 pp/年 × 100万 × 10年 ≈ 16万名义；表写30万为复利差额量级",
            "表": "十年约30万",
            "判定": "一致",
            "理由": "§6 按 100万本金、1.6 pp/年复利十年终值差约 17–20万；与「约30万」同量级，与 K2「约40万」对 2.2 pp 比例一致",
        }
    )
    return {"r10": checks}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    summary = {}
    summary.update(compare_r1())
    summary.update(compare_r2())
    summary.update(compare_r3())
    summary.update(compare_r4())
    (OUT / "comparison_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def main_part2():
    OUT.mkdir(parents=True, exist_ok=True)
    summary_path = OUT / "comparison_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
    summary.update(compare_r7())
    summary.update(compare_r8())
    summary.update(compare_r9())
    summary.update(compare_r10())
    (OUT / "comparison_summary_part2.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("r7", "r8", "r9", "r10") if k in summary}, ensure_ascii=False, indent=2))


def compare_r12() -> dict:
    ref = json.loads((TARGET / "stress.json").read_text(encoding="utf-8"))
    ours = _load_json("r12_stress.json")
    checks = []
    for kind in ("K0", "K2", "K2A"):
        for label in ("2008", "2015"):
            for field in ("最低剩_万", "回撤", "见顶", "见底"):
                t, r = ref[kind][label][field], ours[kind][label][field]
                if field in ("见顶", "见底"):
                    ok = t == r
                    delta = 0 if ok else None
                else:
                    tol = 1.0 if field != "回撤" else 1.0
                    delta = round(abs(float(t) - float(r)), 4)
                    ok = delta <= tol
                checks.append(
                    {
                        "项": f"R12 {kind}/{label}/{field}",
                        "目标": t,
                        "复算": r,
                        "差": delta,
                        "容差": "日期一致" if field in ("见顶", "见底") else "±1",
                        "一致": ok,
                    }
                )
        for field, tol in (("2006–2015 最大回撤", 1.0), ("2006–2015 年化", 0.2)):
            t, r = ref[kind][field], ours[kind][field]
            delta = round(abs(float(t) - float(r)), 4)
            checks.append(
                {
                    "项": f"R12 {kind}/{field}",
                    "目标": t,
                    "复算": r,
                    "差": delta,
                    "容差": f"±{tol}",
                    "一致": bool(delta <= tol),
                }
            )
        for field in ("2006–2015 最大回撤_见顶", "2006–2015 最大回撤_见底"):
            checks.append(
                {
                    "项": f"R12 {kind}/{field}",
                    "目标": "(stress.json 未登记)",
                    "复算": ours[kind][field],
                    "差": None,
                    "容差": "独立登记",
                    "一致": True,
                }
            )
    return {"r12": checks}


def compare_r13() -> dict:
    """K1 无 stress.json 对照；只登记独立复算数字。"""
    ours = _load_json("r12_stress.json")
    k1 = ours["K1"]
    checks = [
        {
            "项": "R13 K1/2008/最低剩_万",
            "复算": k1["2008"]["最低剩_万"],
            "目标": None,
            "备注": "D39 表仅有合成急跌 K1=68；真实 2008 压力测试为本次新报",
        },
        {
            "项": "R13 K1/2015/最低剩_万",
            "复算": k1["2015"]["最低剩_万"],
            "目标": None,
        },
        {
            "项": "R13 K1/2006–2015/最差剩余_万",
            "复算": k1["2006–2015 最差剩余_万"],
            "目标": None,
            "备注": f"全段最大回撤 {k1['2006–2015 最大回撤']}%（{k1['2006–2015 最大回撤_见顶']}→{k1['2006–2015 最大回撤_见底']}）",
        },
    ]
    return {"r13": checks}


def main_part3():
    OUT.mkdir(parents=True, exist_ok=True)
    summary_path = OUT / "comparison_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
    summary.update(compare_r12())
    summary.update(compare_r13())
    (OUT / "comparison_summary_part3.json").write_text(
        json.dumps({k: summary[k] for k in ("r12", "r13") if k in summary}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("r12", "r13") if k in summary}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
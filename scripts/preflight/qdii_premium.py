"""D38 第 28 行 P1：美股 QDII 溢价分布（执行成本数据，只报分布）。
用法：python scripts/preflight/qdii_premium.py results/v6-preflight
"""
import sys, sqlite3, pathlib
import pandas as pd
ROOT = pathlib.Path(__file__).resolve().parents[2]; OUT = pathlib.Path(sys.argv[1])
NAMES = {'513100': '纳指100(国泰)', '159941': '纳指(广发)', '513300': '纳指(华夏)', '159509': '纳指科技', '159632': '纳指(华安)',
         '161125': '标普500(易方达)', '161126': '标普医疗(易方达)', '161127': '标普生物(易方达)', '161128': '标普科技(易方达)',
         '513290': '纳指生物', '159612': '标普500(国泰)', '513500': '标普500(博时)', '159655': '标普(华夏)', '513400': '道指(鹏华)',
         '164824': '印度基金', '513870': '纳指(富国)', '159502': '标普生物(嘉实)', '159513': '纳指大盘(大成)', '513650': '标普(南方)',
         '159518': '标普油气(嘉实)', '513850': '美国50', '159696': '纳指(易方达)'}
c = sqlite3.connect(ROOT / 'data/market.sqlite'); rows = []
for code, name in NAMES.items():
    d = pd.read_sql_query("select b.date, b.close, n.unit_nav from bars b join fund_nav n on b.code=n.code and b.date=n.date "
                          "where b.code=? and b.adj='raw' and b.close>0 and n.unit_nav>0", c, params=(code,))
    if len(d) < 60: continue
    pr = d['close'] / d['unit_nav'] - 1
    rows.append(dict(代码=code, 名称=name, 起=d.date.min(), 天数=len(d), 中位溢价=round(pr.median() * 100, 1),
                     超5pct占比=round((pr > 0.05).mean(), 2), 超10pct占比=round((pr > 0.10).mean(), 2), 最高=round(pr.max() * 100, 1)))
r = pd.DataFrame(rows).sort_values('中位溢价', ascending=False); r.to_csv(OUT / 'qdii-premium.csv', index=False); print(r.to_string(index=False))

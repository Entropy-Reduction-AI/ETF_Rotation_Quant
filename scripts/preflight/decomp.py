"""D38 预演：把长历史回放（longhist.csv）里 K1、K2 比 K0 的年化差拆成四项。
仓位差 = (平均仓位 − 1) × (K0 年化 − 同期现金年化)；成本 = −成本_每年；进出时点 = 净 − 仓位差 − 成本；挑选 = 0（单市场）。
现金：标普、恒生用 DTB3 同期平均；日经用日本银行拆借利率同期平均。
用法：python scripts/preflight/decomp.py results/v6-preflight
"""
import sys, json, pathlib
import pandas as pd
ROOT = pathlib.Path(__file__).resolve().parents[2]; OUT = pathlib.Path(sys.argv[1])
lh = pd.read_csv(OUT / 'longhist.csv')
dtb = pd.read_csv(ROOT / 'results/v5/other-market/raw/DTB3.csv', parse_dates=['date'], na_values=['.', '']).set_index('date')['DTB3']
dtb = dtb.where(dtb > -100).dropna()
RAW = ROOT / 'data/research/long-history/raw'
dd = pd.read_csv(RAW / 'FM01-STRDCLUCON.csv', parse_dates=['date']).set_index('date').iloc[:, 0]
mm = pd.read_csv(RAW / 'FM02-STRACLUCON.csv'); mm.index = pd.to_datetime(mm.iloc[:, 0].astype(str)); mm = mm.iloc[:, 1]
jp = pd.concat([mm[mm.index < dd.index[0]], dd]).sort_index().astype(float)
WIN = {'标普500': ('1956-01-04', '2003-06-30', dtb), '恒生': ('1988-01-03', '2015-12-31', dtb), '日经': ('1988-01-06', '2015-12-30', jp)}
out = {}
for mk, (a, b, r) in WIN.items():
    cash = float(r.loc[a:b].mean()) / 100
    k0 = lh[(lh.市场 == mk) & (lh.结构 == 'K0')].iloc[0]
    for k in ('K1', 'K2'):
        x = lh[(lh.市场 == mk) & (lh.结构 == k)].iloc[0]
        pos = (x.平均仓位 - 1) * (k0.年化 / 100 - cash) * 100
        cost = -x['成本_每年_百分点']; net = x.比K0年化
        out[f'{mk}|{k}'] = dict(净=round(float(net), 2), 仓位差=round(float(pos), 2), 进出时点=round(float(net - pos - cost), 2),
                               成本=round(float(cost), 2), 现金年化=round(cash * 100, 2), 平均仓位=float(x.平均仓位),
                               回撤=float(x.最大回撤), K0回撤=float(k0.最大回撤))
json.dump(out, open(OUT / 'decomp-longhist.json', 'w'), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False))

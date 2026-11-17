"""D38 第 F1 项：Kenneth French 49 个美国行业（市值加权，月度）上 12−1 动量的横截面准确度（IC）。

口径同 ic.py 第 ③ 项：每月末，各行业“前 12 个月到前 1 个月”的累计涨幅排名，与下月涨幅排名的秩相关。
只算准确度，不跑组合；另报“排名前 5 的行业下月平均涨幅 − 49 个行业平均”（未扣成本），仅作量级参照。
数据文件是外部下载的 CSV，只读数字，不执行任何内容。
用法：python -I scripts/preflight/french_ic.py <49_Industry_Portfolios.csv> results/v6-preflight
"""
import sys, json, pathlib, io
import numpy as np, pandas as pd

SRC, OUT = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
lines = SRC.read_text(errors='replace').splitlines()
start = next(i for i, l in enumerate(lines) if 'Average Value Weighted Returns -- Monthly' in l) + 1
end = start + 1
while end < len(lines) and lines[end].strip() and lines[end].split(',')[0].strip().isdigit():
    end += 1
df = pd.read_csv(io.StringIO('\n'.join(lines[start:end])), index_col=0)
df.columns = [c.strip() for c in df.columns]
df.index = pd.to_datetime(df.index.astype(str).str.strip(), format='%Y%m') + pd.offsets.MonthEnd(0)
r = df.astype(float).where(lambda x: x > -99) / 100

lvl = np.log1p(r)
mom = lvl.shift(1).rolling(11, min_periods=11).sum()        # 前 12 到前 1 个月（跳过最近 1 个月）
fwd = r.shift(-1)

def rk(s): return s.rank()
ic, spread = {}, {}
for t in r.index:
    a, b = mom.loc[t], fwd.loc[t]
    ok = a.notna() & b.notna()
    if ok.sum() < 20: continue
    ic[t] = rk(a[ok]).corr(rk(b[ok]))
    top = a[ok].nlargest(5).index
    spread[t] = b[top].mean() - b[ok].mean()
ic, spread = pd.Series(ic), pd.Series(spread)

SEGS = {'全样本': (None, None), '1927–1963': ('1927', '1963'), '1964–1999': ('1964', '1999'),
        '2000–2026': ('2000', '2026'), '2006–2010（同设计期）': ('2006', '2010'),
        '2011–2015（同设计期）': ('2011', '2015'), '2016–2026（设计期之后）': ('2016', '2026')}
rows = []
for k, (a, b) in SEGS.items():
    x, s = ic.loc[a:b], spread.loc[a:b]
    rows.append(dict(段=k, 月数=len(x), IC均值=round(x.mean(), 3), t=round(x.mean() / x.std() * np.sqrt(len(x)), 2),
                     为正比例=round((x > 0).mean(), 2), 前5超额_年化点=round(s.mean() * 1200, 1)))
dec = ic.groupby(ic.index.year // 10 * 10).mean().round(3)
roll = ic.rolling(120).mean()
OUT.mkdir(parents=True, exist_ok=True)
pd.DataFrame(rows).to_csv(OUT / 'french-ic.csv', index=False)
json.dump(dict(来源=SRC.name, 起=str(ic.index[0].date()), 止=str(ic.index[-1].date()), 分段=rows,
               按年代=dec.to_dict(), 十年滚动最低=round(roll.min(), 3), 十年滚动最低年=int(roll.idxmin().year),
               十年滚动低于0点03的月份占比=round(float((roll.dropna() < 0.03).mean()), 2)),
          open(OUT / 'french-ic.json', 'w'), ensure_ascii=False, indent=1, default=str)
print(pd.DataFrame(rows).to_string(index=False)); print(dec.to_string())
print('十年滚动最低', round(roll.min(), 3), roll.idxmin().year, '低于0.03占比', round(float((roll.dropna() < 0.03).mean()), 2))

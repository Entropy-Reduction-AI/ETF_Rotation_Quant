from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
exec(open(ROOT / 'operations/reviews/diag/d7_backfill.py').read().split("for tag,mask")[0].replace('print(f"{a:6s}','0 and print(f"{a:6s}'))
ra=r[A].mean(axis=1,skipna=True).fillna(0); va=valve(ra)
for w in [0.3,0.4,0.5]:
    x=(1-w)*va+w*ro; st(x,f'A{int((1-w)*100)}(阀)+海外{int(w*100)}')
    y=x[(x.index>='2007-10-31')&(x.index<='2009-02-28')]; print('   2007-10→2009-02 累计', f"{(1+y).prod()-1:+.1%}")
st(ro,'海外腿单独(无阀)')

import sys, json, numpy as np, pandas as pd
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from src.research.prereg_v1.panel import read_table, validate_panel, validate_bench
from src.research.prereg_v1.config import DESIGN_END, Params
from src.research.prereg_v1.engine import simulate, random_entry_null
from src.research.prereg_v1.metrics import r_stats, portfolio_stats, r_by
P=str(ROOT / 'outputs/panel-2026-09-30.sqlite')
E=pd.Timestamp(DESIGN_END)
panel=validate_panel(read_table(P,'panel')); hs=validate_bench(read_table(P,'bench'))
d=panel[panel.date<=E].copy(); hs=hs[hs.index<=E]
p=Params()
# 1 ADR
d['adr']=(d.high-d.low)/d.close
adr=d[d.data_hole==0].groupby('container').adr.median().sort_values()
print('ADR median %:', (adr*100).round(2).to_dict())
# 2 V1 system on design
start=d.date.min()
res=simulate(d,p,start,E)
rs=r_stats(res.trades)
print('V1 design r_stats:', json.dumps(rs, default=float, ensure_ascii=False))
port=portfolio_stats(res,d,hs,p)
print('V1 design portfolio:', {k:v for k,v in port.items() if k!='yearly'})
print(port['yearly'])
print(r_by(res.trades,'branch'))
print(r_by(res.trades,res.trades.entry_date.dt.year))
res.trades.to_csv('/data/diag/design_trades.csv',index=False)
res.nav.to_csv('/data/diag/design_nav.csv')
n_sig=len(res.trades)+len(res.skipped)
nr=random_entry_null(d,p,start,E,n_sig,200)
print('random null mean_R median/p5/p95:', np.nanmedian(nr), np.nanpercentile(nr,5), np.nanpercentile(nr,95), 'V1 pct', (nr<rs.get('mean_R')).mean())

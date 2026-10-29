# 只读复跑 E2 新口径（B0）两个池，保存持仓，用于查 U-可交易的问题（D24）。用法：python results/v4/diag/health/tradable_probe.py <out.pkl>
import sys, pickle
sys.path.insert(0,'.')
import pandas as pd, numpy as np
from src.v4.r5 import design as D
from src.v3.engine.spec import load_spec
from src.v3.engine.arms import execute
spec = load_spec()
out={}
for pool in ("tradable","index"):
    m = D.prepare_market(pool, t4=False, allow_substitute=True, spec=spec)
    job = D.Job(case="B0", pool=pool, kind="single")
    book = execute(m, spec, "A", allow_after=False, exit_drawdown=job.exit_drawdown, switches=job.switches())
    out[pool]=dict(net=book.net, held=book.held, targets=book.targets, pnl=m.pnl, cash=m.cash_id,
       avail={k:getattr(m,k) for k in dir(m) if not k.startswith('_') and isinstance(getattr(m,k),(pd.DataFrame,pd.Series,dict))})
    print(pool, type(book.held), getattr(book.held,'shape',None), m.cash_id)
pickle.dump(out, open(sys.argv[1],'wb'))

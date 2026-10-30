# 两个池子每年能参加排名的容器数（按大类）。只读行情和登记表，不算任何收益，只到 2015-12-31。
# 用法：python results/v4/diag/health/pool_counts.py results/v4/diag/health/pool-counts.csv
import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[4]; sys.path.insert(0, str(ROOT))
import pandas as pd
from src.v4.r5 import design as D
from src.v3.engine.spec import load_spec
spec = load_spec()
grp = pd.read_csv(ROOT / 'results/v4/diag/data-board/out/containers.csv').set_index('id')['group'].to_dict()
rows = []
for pool in ('index', 'tradable'):
    m = D.prepare_market(pool, t4=False, allow_substitute=True, spec=spec)
    ok = m.liquidity.astype(bool) & m.signal.reindex(columns=m.liquidity.columns).notna()
    for y, part in ok.groupby(ok.index.year):
        for name in part.columns[part.any()]:
            if name == 'cash': continue
            rows.append({'pool': pool, 'year': int(y), 'id': name, 'group': grp.get(name, '?')})
out = pd.DataFrame(rows)
out.to_csv(sys.argv[1], index=False)
print(out.groupby(['pool', 'year']).size().unstack(0))

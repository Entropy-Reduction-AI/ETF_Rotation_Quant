# E2 新口径（B0）两个池子每天的现金权重和研究序列水平，用于体检报告的“两次大跌”图。
# 只复跑已登记的 B0 配置，不新增尝试，不写 results/v4/r5，只到 2015-12-31。
# 用法：python results/v4/diag/health/cash_weights.py results/v4/diag/health/b0-cash-weights.csv
import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[4]; sys.path.insert(0, str(ROOT))
import pandas as pd
from src.v4.r5 import design as D
from src.v3.engine.spec import load_spec
from src.v3.engine.arms import execute
spec = load_spec(); cols = {}
for pool in ('index', 'tradable'):
    m = D.prepare_market(pool, t4=False, allow_substitute=True, spec=spec)
    job = D.Job(case='B0', pool=pool, kind='single')
    b = execute(m, spec, 'A', allow_after=False, exit_drawdown=job.exit_drawdown, switches=job.switches())
    ref = D.read_net('B0', pool)
    assert float((b.net - ref).abs().max()) < 1e-9, '复跑与公布净值不一致'
    cols[f'{pool}_cash'] = b.held['cash']
    if pool == 'index':
        cols['csi300_level'] = m.levels['csi300']
pd.DataFrame(cols).loc[:'2015-12-31'].to_csv(sys.argv[1], float_format='%.6g')

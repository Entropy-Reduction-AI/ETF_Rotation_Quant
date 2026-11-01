"""v5 研究备忘的描述性诊断：E2 新口径（B0）与 v5 最终版（P2）在 U-指数池每天的实际持仓，按 v5 大类汇总。
重跑的是已登记的两个配置，复跑净值必须与已登记序列一致；不新增任何策略，不算 2016 年以后的收益。
用法：python results/v5/diag/memo/holdings.py results/v5/diag/memo/class-weights.csv
"""
import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[4]; sys.path.insert(0, str(ROOT))
import pandas as pd, numpy as np
from src.v3.engine.spec import load_spec
from src.v4.r5.design import Markets, execute_job, single_jobs
from src.v5.campaign import classes_for, class_map
from src.v5.engine.execute import run_arm

spec = load_spec(); markets = Markets(spec)
m = markets.get('index', t4=False, allow_substitute=True)
cls = classes_for(list(m.names), m.cash_id, class_map())
cls[m.cash_id] = '现金'

def by_class(books):
    frames = []
    for b in books.values():
        h = b.held.copy()
        frames.append(h.T.groupby(h.columns.map(lambda n: cls.get(n, '现金'))).sum().T)
    out = sum(frames) / len(frames)
    return out

v5 = run_arm(m, spec, cls, enable_c2=True, enable_c1=False)
stored = pd.read_csv(ROOT / 'results/v5/design/P2/index/net.csv', index_col=0, parse_dates=True).iloc[:, 0]
assert np.allclose(v5.net.reindex(stored.index).values, stored.values, atol=1e-12), 'P2 复跑与登记不一致'
from src.v3.engine.arms import execute
job = [j for j in single_jobs() if j.case == 'B0' and j.pool == 'index'][0]
b0 = execute(m, spec, 'A', allow_after=False, exit_drawdown=job.exit_drawdown, switches=job.switches())
b0stored = pd.read_csv(ROOT / 'results/v4/r5/design/B0/index/net.csv', index_col=0, parse_dates=True).iloc[:, 0]
assert np.allclose(b0.net.reindex(b0stored.index).values, b0stored.values, atol=1e-12), 'B0 复跑与登记不一致'
w5 = by_class(v5.paths).add_prefix('v5:')
w0 = by_class(b0.paths).add_prefix('E2:')
out = pd.concat([w0, w5], axis=1).loc['2005-06-01':'2015-12-31']
out.to_csv(sys.argv[1], float_format='%.6f')
print(out.resample('YE').mean().round(2).to_string())

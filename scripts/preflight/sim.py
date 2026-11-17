"""D38 预演：第 1 项成本表、第 2 项合成行情行为、第 4 项敏感度（含底仓美股比例）。

只用合成行情。噪声来自已登记的长历史：标普500（^GSPC）与恒生（^HSI）1987-01 → 2003-06-30 同日成对的日对数收益，
去均值、除以全样本标准差后，按 20 日一段成对重抽（保留肥尾、波动聚集和两个市场之间的相关）。
不读项目池任何收益；不读 2016 年以后的任何数据。

用法：python scripts/preflight/sim.py results/v6-preflight [paths]
"""
import sys, json, pathlib
import numpy as np, pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = pathlib.Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
NP = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
RAW = ROOT / 'data/research/long-history/raw'
D, M, W = 252, 21, 5              # 一年交易日、一月、一周
BOND = 0.03                       # 国债年化，确定性计息
COST = 0.001                      # 每腿单边成本（场内 ETF），按成交金额
SEED = 20261117

# ---------- 噪声 ----------
def noise_pool():
    px = {}
    for k, f in (('US', '^GSPC.csv'), ('A', '^HSI.csv')):
        d = pd.read_csv(RAW / f, parse_dates=['date']).set_index('date')['close']
        px[k] = d[(d.index >= '1987-01-01') & (d.index <= '2003-06-30')]
    df = pd.DataFrame(px).dropna()
    lr = np.log(df).diff().dropna()
    z = (lr - lr.mean()) / lr.std()
    return z[['A', 'US']].values, float(lr.corr().iloc[0, 1])

Z, CORR = noise_pool()
rng = np.random.default_rng(SEED)

def reseed():
    """每种行情、每组敏感度都从同一个种子重新开始，结果不随运行顺序变化（D38 Reviewer 跟进，2026-11-17）。"""
    global rng
    rng = np.random.default_rng(SEED)

def draw(n):
    """n 天、NP 条路径的成对标准化噪声，形状 (NP, n, 2)。"""
    k = int(np.ceil(n / 20)); st = rng.integers(0, len(Z) - 20, size=(NP, k))
    idx = (st[:, :, None] + np.arange(20)).reshape(NP, -1)[:, :n]
    return Z[idx]

def seg(days, mu_a, mu_u, vol_a, vol_u):
    """一段行情：年化漂移（几何）、年化波动。返回每段参数。"""
    return (days, mu_a, mu_u, vol_a, vol_u)

def build(segs):
    """把多段拼成日对数收益 (NP, T, 2)；漂移按段内总量精确落地（噪声去均值后按段重新中心化）。"""
    out = []
    for days, ma, mu, va, vu in segs:
        e = draw(days)
        e = e - e.mean(axis=1, keepdims=True)          # 每段噪声中心化，使段内总漂移精确等于设定
        sig = np.array([va, vu]) / np.sqrt(D)
        drift = np.log1p(np.array([ma, mu])) / D        # 年化几何收益 → 日对数漂移
        out.append(drift + e * sig)
    return np.concatenate(out, axis=1)

WARM = D  # 预热一年：K1 要 10 个月均线、K3 要 12 个月、K2 要 252 日波动
def warm(vol=0.18):
    return seg(WARM, 0.08, 0.08, vol, vol)

def total(r, days):  # 段总收益 r（如 -0.30）→ 年化
    return (1 + r) ** (D / days) - 1

SCEN = {
    '慢牛':   [warm(0.15), seg(3 * D, 0.15, 0.15, 0.15, 0.15)],
    '急跌':   [warm(0.15), seg(D, 0.15, 0.15, 0.15, 0.15), seg(20, total(-0.30, 20), total(-0.30, 20), 0.40, 0.40),
               seg(120, 0.0, 0.0, 0.25, 0.25)],
    '慢熊':   [warm(0.18), seg(378, total(-0.45, 378), total(-0.45, 378), 0.25, 0.25)],
    'V型反转': [warm(0.18), seg(20, total(-0.30, 20), total(-0.30, 20), 0.40, 0.40),
               seg(60, total(1 / 0.7 - 1, 60), total(1 / 0.7 - 1, 60), 0.35, 0.35), seg(120, 0.10, 0.10, 0.20, 0.20)],
    '震荡':   [warm(0.22), seg(3 * D, 0.0, 0.0, 0.22, 0.22)],
    '市场接力': [warm(0.20), seg(378, 0.25, 0.0, 0.20, 0.20), seg(378, 0.0, 0.25, 0.20, 0.20)],
}
# 急跌、V 型：从哪一天起算“见顶”“见底”
EVENT = {'急跌': ('top', WARM + D), '慢熊': ('top', WARM), 'V型反转': ('bottom', WARM + 20)}

# ---------- 结构 ----------
STRUCT = ('K0', 'K1', 'K2', 'K3', 'K2A')  # K2A：只给 A 股腿用 K2，美股腿一直持有（D38 第 3 版登记，2026-11-17）

def run(lr, s_us=0.30, kind='K0', vol_short=20, band=0.10, tilt=0.20):
    """lr: (NP, T, 2) 日对数收益，列 0 = A 股腿，列 1 = 美股腿。返回逐日净值、股票仓位、各类换手。
    成交在信号日的下一日开盘前（按信号日收盘后的权重变动、当日收益之后计）。"""
    n, T, _ = lr.shape
    R = np.expm1(lr); bd = (1 + BOND) ** (1 / D) - 1
    P = np.exp(np.cumsum(lr, axis=1))                       # 指数点位（起点 1）
    base = np.array([1 - s_us, s_us])
    tgt_leg = np.tile(base, (n, 1))                          # 每条腿的目标权重（K3 会变）
    on = np.ones((n, 2))                                     # K1：腿是否在股票
    frac = np.ones((n, 2))                                   # K2：腿内股票比例
    w = np.zeros((n, 3)); w[:, :2] = base                    # 当前持仓权重：A、US、国债
    nav = np.ones(n); navs = np.empty((n, T)); expo = np.empty((n, T))
    turn = {k: np.zeros(n) for k in ('再平衡', '保险切换', '波动调仓', '倾斜')}
    flips = np.zeros(n); last_flip = np.full((n, 2), -10 ** 6); last_state = on.copy()
    for t in range(T):
        # 当日收益
        g = 1 + w[:, 0] * R[:, t, 0] + w[:, 1] * R[:, t, 1] + w[:, 2] * bd
        w = np.column_stack([w[:, 0] * (1 + R[:, t, 0]), w[:, 1] * (1 + R[:, t, 1]), w[:, 2] * (1 + bd)]) / g[:, None]
        nav = nav * g; navs[:, t] = nav; expo[:, t] = w[:, 0] + w[:, 1]
        if t < WARM - 1 and kind != 'K0':
            pass
        month_end = (t + 1) % M == 0
        week_end = (t + 1) % W == 0
        new_on, new_frac, new_tgt = on, frac, tgt_leg
        cls = None
        if kind in ('K1', 'K2', 'K3', 'K2A') and month_end and t >= 10 * M:
            me = P[:, t - 9 * M:t + 1:M, :]                  # 最近 10 个月末收盘
            new_on = (P[:, t, :] >= me.mean(axis=1)).astype(float)
        if kind == 'K3' and month_end and t >= D:
            m = P[:, t - M, :] / P[:, t - D, :] - 1          # 12−1
            us_up = m[:, 1] > m[:, 0]
            a = np.where(us_up, base[0] - tilt, base[0] + tilt); a = np.clip(a, 0, 1)
            new_tgt = np.column_stack([a, 1 - a])
        if kind in ('K2', 'K2A') and week_end and t >= D:
            lrw = lr[:, t - D + 1:t + 1, :]
            vl = lrw.std(axis=1); vs = lr[:, t - vol_short + 1:t + 1, :].std(axis=1)
            f = np.minimum(1.0, vl / np.maximum(vs, 1e-9))
            new_frac = np.where(np.abs(f - frac) >= band, f, frac)
        if kind == 'K2A':
            new_on = new_on.copy(); new_on[:, 1] = 1.0
            new_frac = new_frac.copy(); new_frac[:, 1] = 1.0
        # 目标权重
        legs = new_tgt * new_on * new_frac
        target = np.column_stack([legs, 1 - legs.sum(axis=1)])
        # 判定这一天有哪些交易：按优先级归类
        if month_end:
            # 月度：K0/K1/K2/K3 都按月再平衡到目标
            pass
        chg_state = (new_on != on).any(axis=1)
        chg_tgt = (np.abs(new_tgt - tgt_leg) > 1e-12).any(axis=1)
        chg_frac = (np.abs(new_frac - frac) > 1e-12).any(axis=1)
        do = chg_state | chg_tgt | chg_frac | month_end
        if do.any():
            tr = np.abs(target - w).sum(axis=1) * do
            # 归类：状态翻转 > 倾斜 > 波动 > 普通再平衡
            c_state = chg_state; c_tilt = chg_tgt & ~c_state; c_vol = chg_frac & ~c_state & ~c_tilt
            c_reb = do & ~c_state & ~c_tilt & ~c_vol
            for key, msk in (('保险切换', c_state), ('倾斜', c_tilt), ('波动调仓', c_vol), ('再平衡', c_reb)):
                turn[key] += tr * msk
            nav = nav * (1 - COST * tr)
            w = np.where(do[:, None], target, w)
            # 来回：一条腿状态翻转，并在 21 日内又翻回
            fl = (new_on != on)
            back = fl & (t - last_flip <= M) & (new_on == last_state)
            flips += back.sum(axis=1)
            last_state = np.where(fl, on, last_state); last_flip = np.where(fl, t, last_flip)
        on, frac, tgt_leg = new_on, new_frac, new_tgt
    return navs, expo, turn, flips

def mdd(x):
    peak = np.maximum.accumulate(x, axis=1)
    return (x / peak - 1).min(axis=1)

def stats(name, lr, kinds=STRUCT, s_us=0.30, extra=None):
    a, b = WARM, lr.shape[1]
    yrs = (b - a) / D
    res = {}
    for k in kinds:
        navs, expo, turn, flips = run(lr, s_us=s_us, kind=k, **(extra or {}))
        seg_nav = navs[:, a - 1:b] / navs[:, a - 1:a]
        ann = seg_nav[:, -1] ** (1 / yrs) - 1
        res[k] = dict(ann=ann, mdd=mdd(seg_nav), expo=expo[:, a:b].mean(axis=1),
                      turn={c: v / ( (b) / D) for c, v in turn.items()},   # 每年（全程含预热，按年折算）
                      flips=flips / (b / D), navs=navs, expoall=expo)
    return res

def q(x, p=(10, 50, 90)):
    return [round(float(v), 4) for v in np.percentile(x, p)]

def event_timing(res, lr, scen):
    """见顶后股票仓位减到起点一半所用天数、当时市场跌了多少；见底后回到 K0 一半所用天数、错过涨幅。"""
    if scen not in EVENT: return {}
    typ, t0 = EVENT[scen]
    mk = np.exp(np.cumsum(lr.mean(axis=2), axis=1))           # 两市等权的市场点位，只作时点参照
    out = {}
    for k, r in res.items():
        e = r['expoall']; T = e.shape[1]
        days, move = [], []
        for i in range(e.shape[0]):
            if typ == 'top':
                ref = e[i, t0 - 1]; hit = np.where(e[i, t0:] <= 0.5 * ref)[0]
                if len(hit): days.append(hit[0]); move.append(mk[i, t0 + hit[0]] / mk[i, t0 - 1] - 1)
                else: days.append(np.nan); move.append(np.nan)
            else:
                # 见底后 60 日内仓位最低点；没降到 K0 一半以下 = 没离场（单独计数）；否则量从最低点回到一半的天数和错过的涨幅
                ref = res['K0']['expoall'][i, t0]; win = e[i, t0:t0 + 60]; lo = int(np.argmin(win))
                if win[lo] > 0.5 * ref: days.append(-1.0); move.append(np.nan); continue
                hit = np.where(e[i, t0 + lo:] >= 0.5 * ref)[0]
                if len(hit): days.append(lo + hit[0]); move.append(mk[i, t0 + lo + hit[0]] / mk[i, t0] - 1)
                else: days.append(np.nan); move.append(np.nan)
        days, move = np.array(days, float), np.array(move, float)
        stayed = days == -1; ok = ~np.isnan(days) & ~stayed
        out[k] = dict(type=typ, stayed_in=float(stayed.mean()), never=float(np.isnan(days).mean()),
                      days=q(days[ok]) if ok.any() else None,
                      move=q(move[ok & ~np.isnan(move)]) if (ok & ~np.isnan(move)).any() else None)
    return out

def main():
    rows, cost_rows, ev = [], [], {}
    for scen, segs in SCEN.items():
        reseed(); lr = build(segs)
        res = stats(scen, lr)
        ev[scen] = event_timing(res, lr, scen)
        for k, r in res.items():
            d_ann = r['ann'] - res['K0']['ann']; d_mdd = r['mdd'] - res['K0']['mdd']
            rows.append(dict(行情=scen, 结构=k,
                             年化_中位=round(float(np.median(r['ann'])) * 100, 2),
                             比K0年化_p10=q(d_ann)[0] * 100, 比K0年化_p50=q(d_ann)[1] * 100, 比K0年化_p90=q(d_ann)[2] * 100,
                             回撤_中位=round(float(np.median(r['mdd'])) * 100, 1),
                             比K0回撤_p50=round(float(np.median(d_mdd)) * 100, 1),
                             股票仓位占K0=round(float(np.median(r['expo'] / res['K0']['expo'])), 3),
                             保险一月内翻回_每年=round(float(np.median(r['flips'])), 2)))
            tot = sum(r['turn'].values())
            cost_rows.append(dict(行情=scen, 结构=k, **{f'{c}_换手': round(float(np.median(v)), 2) for c, v in r['turn'].items()},
                                  双边换手_每年=round(float(np.median(tot)), 2),
                                  成本_每年_百分点=round(float(np.median(tot)) * COST * 100, 3)))
    pd.DataFrame(rows).to_csv(OUT / 'behavior.csv', index=False)
    pd.DataFrame(cost_rows).to_csv(OUT / 'cost.csv', index=False)
    json.dump(ev, open(OUT / 'events.json', 'w'), ensure_ascii=False, indent=1)

    # ---------- 第 4 项：敏感度 ----------
    # 十年；A 股腿年化 6%、波动 25%；美股腿 = A + 差，波动 17%（两腿波动为假设，见 README）
    sens = []
    for spread in (-0.10, 0.0, 0.10, 0.20):
        reseed(); lr = build([warm(0.20), seg(10 * D, 0.06, 0.06 + spread, 0.25, 0.17)])
        ref = stats('ref', lr, kinds=('K0',), s_us=0.30)['K0']
        for s in (0.30, 0.40, 0.50, 0.60, 0.70, 0.80):
            r = stats('s', lr, kinds=('K0',), s_us=s)['K0']
            d = r['ann'] - ref['ann']; dm = r['mdd'] - ref['mdd']
            sens.append(dict(美股比A股每年多涨=f'{spread:+.0%}', 结构='K0', 底仓美股=f'{s:.0%}',
                             比70_30年化_p10=q(d)[0] * 100, 比70_30年化_p50=q(d)[1] * 100, 比70_30年化_p90=q(d)[2] * 100,
                             回撤_中位=round(float(np.median(r['mdd'])) * 100, 1), 比70_30回撤_p50=round(float(np.median(dm)) * 100, 1)))
        res = stats('k', lr, kinds=('K1', 'K2', 'K3', 'K2A'), s_us=0.30)
        for k, r in res.items():
            d = r['ann'] - ref['ann']; dm = r['mdd'] - ref['mdd']
            sens.append(dict(美股比A股每年多涨=f'{spread:+.0%}', 结构=k, 底仓美股='30%',
                             比70_30年化_p10=q(d)[0] * 100, 比70_30年化_p50=q(d)[1] * 100, 比70_30年化_p90=q(d)[2] * 100,
                             回撤_中位=round(float(np.median(r['mdd'])) * 100, 1), 比70_30回撤_p50=round(float(np.median(dm)) * 100, 1)))
    pd.DataFrame(sens).to_csv(OUT / 'sensitivity.csv', index=False)

    # 平台：K2 的短窗 10/60 日，K3 的倾斜 10/30 个点（只报告）
    plat = []
    for scen in ('慢牛', '急跌', '震荡', '市场接力'):
        reseed(); lr = build(SCEN[scen]); k0 = stats(scen, lr, kinds=('K0',))['K0']
        for k, ex in (('K2', dict(vol_short=10)), ('K2', dict(vol_short=20)), ('K2', dict(vol_short=60)),
                      ('K3', dict(tilt=0.10)), ('K3', dict(tilt=0.20)), ('K3', dict(tilt=0.30))):
            r = stats(scen, lr, kinds=(k,), extra=ex)[k]
            plat.append(dict(行情=scen, 结构=k, 参数=json.dumps(ex), 比K0年化_p50=round(float(np.median(r['ann'] - k0['ann'])) * 100, 2),
                             比K0回撤_p50=round(float(np.median(r['mdd'] - k0['mdd'])) * 100, 1),
                             双边换手_每年=round(float(np.median(sum(r['turn'].values()))), 2)))
    pd.DataFrame(plat).to_csv(OUT / 'plateau.csv', index=False)
    json.dump(dict(paths=NP, seed=SEED, noise='^GSPC/^HSI 1987-01..2003-06 paired, 20d block bootstrap',
                   noise_days=len(Z), daily_corr=round(CORR, 3), bond=BOND, cost_per_leg=COST),
              open(OUT / 'run.json', 'w'), ensure_ascii=False, indent=1)

if __name__ == '__main__':
    main()

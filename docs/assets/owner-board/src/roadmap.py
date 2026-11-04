# 进度总览：版本 × 阶段（HTML 截图）。用法：python3 rm.py && node shot.js
cols=['① 规则定稿','② 标的池','③ 交易引擎','④ 溢价控制','⑤ 打分卡','⑥ 业务体检','⑦ 代码冻结','⑧ 一次性检验','⑨ 结论','⑩ 模拟盘']
D,P,Y,W,N='done','prog','you','wait','none'
rows=[('v3.1','冻结基线<br>= E2',[(D,'✓ 已冻结','补全池子 + 10% 离场；补充文本已签收'),(D,'✓ 完成','81 个容器；黄金、国债 2008 起'),(D,'✓ 完成','补池 + 离场 + 溢价接入'),(D,'✓ 完成','已接进交易流程'),(D,'✓ 完成','五条判据；尝试次数 28 + 35'),(D,'✓ 完成','年化 25.1%，基准 15.4%；弱点：反弹'),(D,'✓ 10-27 冻结','milestone/v3-code-freeze'),(N,'不单独跑','由 v4 的 E2 新口径代表（D34）'),(N,'—',''),(N,'—','')]),
('v4','设计期完成',[(D,'✓ 10-29 冻结','第 2.3 版；milestone/v4-prereg-freeze'),(D,'✓ R1–R1f','198 只场内 QDII/LOF 全部收录'),(D,'✓ R2–R2c','新池、载体、T1–T3'),(D,'✓ v4-R2','跨境成本机制'),(D,'✓ v4-R3','任意起点、四种市场状态'),(D,'✓ 体检第 3 版','T1–T4 未过关；最终版 = E2 新口径'),(D,'✓ 10-31 再冻结','milestone/v4-code-freeze-2'),(P,'进行中','E2 新口径入围，跑一次'),(N,'未开始',''),(N,'未开始','')]),
('v5 原版','已淘汰',[(D,'✓ 11-01 冻结','两层 + 防守位'),(D,'✓ 完成','101 个容器分 7 个大类'),(D,'✓ 完成','与 E2 新口径同一成交通道'),(D,'✓ 沿用','溢价控制不变'),(D,'✓ 完成','10% 离场过关，按波动调仓未过'),(D,'✓ 设计期跑完','12.7%，未入围；四处结构硬伤'),(N,'不做','淘汰，结果留档'),(N,'—',''),(N,'—',''),(N,'—','')]),
('v5.1','封板前最后一版<br>两层 FOF',[(D,'✓ 11-04 冻结','milestone/v5.1-prereg-freeze'),(D,'✓ 沿用','v5 大类表；三个市场 + 国债、黄金'),(D,'✓ 完成','R2 实现，R3 独立复算'),(D,'✓ 沿用','溢价控制不变'),(D,'✓ 完成','入围 7 条，过 5 条'),(D,'✓ 设计期跑完','中国 30.1%；美国 1.3%；不入围'),(D,'✓ 11-04 封板','D34；代码冻结标签待打'),(P,'进行中','同次跑 E2 新口径、A1、基准、v5.1（只作对照）'),(N,'未开始',''),(N,'未开始','')])]
css='''body{margin:0;background:#fff;font-family:"Noto Sans CJK SC",sans-serif;color:#151b26}
.w{width:1960px;padding:24px}.h{display:flex;justify-content:space-between;align-items:center;margin-bottom:18px}
.t{font-size:26px;font-weight:700}.lg span{margin-left:22px;font-size:15px;color:#3f4653}.lg i{display:inline-block;width:13px;height:13px;border:2px solid;border-radius:3px;margin-right:6px;vertical-align:-2px}
.g{display:grid;grid-template-columns:150px repeat(10,1fr);gap:10px}.ch{font-size:18px;font-weight:700;text-align:center;padding:6px 0}
.v{background:#151b26;color:#fff;border-radius:10px;padding:16px 12px}.v b{font-size:26px;display:block;font-family:"JetBrains Mono",monospace}.v small{font-size:13px;color:#c8ccd4}
.c{border:3px solid;border-radius:10px;padding:12px;min-height:118px;font-size:14.5px;line-height:1.55}.c b{font-size:16px;display:block;margin-bottom:6px}
.done{border-color:#16a34a;background:#f0fdf4}.done b{color:#15803d}.prog{border-color:#d97706;background:#fffbeb}.prog b{color:#b45309}
.wait{border-color:#9ca3af;border-style:dashed;background:#fff}
.you{border-color:#7c3aed;background:#f5f3ff}.you b{color:#6d28d9}.none{border-color:#e5e7eb;background:#f3f4f6;color:#6b7280}.none b{color:#6b7280}
.f{margin-top:12px;font-size:15px;color:#4b5563}'''
h=f'<!doctype html><meta charset=utf-8><style>{css}</style><div class=w id=r><div class=h><div class=t>进度总览：版本 × 阶段</div><div class=lg><span><i style="border-color:#16a34a"></i>完成</span><span><i style="border-color:#d97706"></i>进行中</span><span><i style="border-color:#7c3aed"></i>需要你</span><span><i style="border-color:#9ca3af;border-style:dashed"></i>暂停</span><span><i style="border-color:#e5e7eb;background:#f3f4f6"></i>未开始</span></div></div><div class=g><div></div>'
h+=''.join(f'<div class=ch>{c}</div>' for c in cols)
for v,sub,cells in rows:
    h+=f'<div class=v><b>{v}</b><small>{sub}</small></div>'+''.join(f'<div class="c {k}"><b>{a}</b>{b}</div>' for k,a,b in cells)
h+='</div><div class=f>v5.1 不入围（别的市场检验和顺应市场两条未过）；已封板（D34）；一次性检验的入围名单只有 E2 新口径，v5.1 只作对照。轮次编号规则见 docs/manual/roadmap-and-naming.md。</div></div>'
open('rm.html','w').write(h)

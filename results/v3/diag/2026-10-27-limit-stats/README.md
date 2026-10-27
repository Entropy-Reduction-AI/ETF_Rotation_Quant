# 设计期可交易池：计划成交日的涨跌停与无价

统计日 2026-10-27。只描述计划成交日的原始收盘，不改回测成交假设。
组合收益没有落盘，结束日全部 ≤ 2015-12-31。

## 怎么判

- 计划买入日 = 常规调仓的成交日（决策日的下一上交所交易日）。权重比当日漂移后的持仓增加，记一笔买入。
- 计划离场日 = 离场信号日的下一上交所交易日。信号来自各路账本的 `kind=signal`，不是已经成交的 `kind=exit`。
- 收盘涨停：当日原始收盘等于前一笔原始收盘 × 1.10，四舍五入到 0.001 元。买入才把这个记成受阻。
- 收盘跌停：同样规则的 × 0.90。离场才把这个记成受阻。
- 无价：计划成交日该代码没有正的有限原始收盘。
- 设计期里本池 ETF 用 ±10%。创业板 ±20% 从 2020-08-24 才开始，不套到 2015 年。
- 代码用登记表里的第一只执行基金；若该路当天的代码审计里有持仓代码，用审计里的代码。

## 分运行合计

run_id,arm,history_mode,side,mark,n
P10,B,official,buy,has_price,71
P10,B,official,exit,close_limit_down,2
P10,B,official,exit,has_price,14
P6,A,official,buy,close_limit_up,6
P6,A,official,buy,has_price,1286
P6,A,official,buy,no_price,2
P6,A,official,exit,close_limit_down,22
P6,A,official,exit,has_price,151
P7,A,publish_date,buy,close_limit_up,6
P7,A,publish_date,buy,has_price,1286
P7,A,publish_date,buy,no_price,2
P7,A,publish_date,exit,close_limit_down,22
P7,A,publish_date,exit,has_price,151
P8,S1,official,buy,close_limit_up,6
P8,S1,official,buy,has_price,1285
P8,S1,official,buy,no_price,2
P8,S1,official,exit,close_limit_down,22
P8,S1,official,exit,has_price,151
P9,S2,official,buy,close_limit_up,6
P9,S2,official,buy,has_price,1286
P9,S2,official,buy,no_price,2
P9,S2,official,exit,close_limit_down,22
P9,S2,official,exit,has_price,151

## 已知的离场日收盘跌停

2015-06-29 与 2015-08-24 在可交易池的计划离场里出现收盘跌停。
下面每一行是一条路径上的一笔计划卖出，不是指数本身。

run_id,arm,pool,history_mode,path,side,container,code,signal_date,planned_fill,prev_close,close,limit_up,limit_down,simple_return,at_limit_up,at_limit_down,mark
P6,A,tradable,official,3-week,exit,chinext,159915,2015-06-26,2015-06-29,2.7670,2.4900,3.044,2.490,-0.100108,0,1,close_limit_down
P6,A,tradable,official,5-week,exit,chinext,159915,2015-06-26,2015-06-29,2.7670,2.4900,3.044,2.490,-0.100108,0,1,close_limit_down
P6,A,tradable,official,8-week,exit,chinext,159915,2015-06-26,2015-06-29,2.7670,2.4900,3.044,2.490,-0.100108,0,1,close_limit_down
P7,A,tradable,publish_date,3-week,exit,chinext,159915,2015-06-26,2015-06-29,2.7670,2.4900,3.044,2.490,-0.100108,0,1,close_limit_down
P7,A,tradable,publish_date,5-week,exit,chinext,159915,2015-06-26,2015-06-29,2.7670,2.4900,3.044,2.490,-0.100108,0,1,close_limit_down
P7,A,tradable,publish_date,8-week,exit,chinext,159915,2015-06-26,2015-06-29,2.7670,2.4900,3.044,2.490,-0.100108,0,1,close_limit_down
P8,S1,tradable,official,3-week,exit,chinext,159915,2015-06-26,2015-06-29,2.7670,2.4900,3.044,2.490,-0.100108,0,1,close_limit_down
P8,S1,tradable,official,5-week,exit,chinext,159915,2015-06-26,2015-06-29,2.7670,2.4900,3.044,2.490,-0.100108,0,1,close_limit_down
P8,S1,tradable,official,8-week,exit,chinext,159915,2015-06-26,2015-06-29,2.7670,2.4900,3.044,2.490,-0.100108,0,1,close_limit_down
P9,S2,tradable,official,3-week,exit,s2-创业板,159915,2015-06-26,2015-06-29,2.7670,2.4900,3.044,2.490,-0.100108,0,1,close_limit_down
P9,S2,tradable,official,5-week,exit,s2-创业板,159915,2015-06-26,2015-06-29,2.7670,2.4900,3.044,2.490,-0.100108,0,1,close_limit_down
P9,S2,tradable,official,8-week,exit,s2-创业板,159915,2015-06-26,2015-06-29,2.7670,2.4900,3.044,2.490,-0.100108,0,1,close_limit_down
P10,B,tradable,official,executed,exit,csi-dividend,510880,2015-08-21,2015-08-24,2.8790,2.5910,3.167,2.591,-0.100035,0,1,close_limit_down
P10,B,tradable,official,executed,exit,csi500,510500,2015-08-21,2015-08-24,7.6980,6.9280,8.468,6.928,-0.100026,0,1,close_limit_down
P6,A,tradable,official,3-month,exit,csi-dividend,510880,2015-08-21,2015-08-24,2.8790,2.5910,3.167,2.591,-0.100035,0,1,close_limit_down
P6,A,tradable,official,3-month,exit,csi500,510500,2015-08-21,2015-08-24,7.6980,6.9280,8.468,6.928,-0.100026,0,1,close_limit_down
P6,A,tradable,official,3-week,exit,chinext,159915,2015-08-21,2015-08-24,2.2260,2.0030,2.449,2.003,-0.100180,0,1,close_limit_down
P6,A,tradable,official,3-week,exit,csi-dividend,510880,2015-08-21,2015-08-24,2.8790,2.5910,3.167,2.591,-0.100035,0,1,close_limit_down
P6,A,tradable,official,3-week,exit,csi500,510500,2015-08-21,2015-08-24,7.6980,6.9280,8.468,6.928,-0.100026,0,1,close_limit_down
P6,A,tradable,official,5-month,exit,csi-dividend,510880,2015-08-21,2015-08-24,2.8790,2.5910,3.167,2.591,-0.100035,0,1,close_limit_down
P6,A,tradable,official,5-month,exit,csi300,510300,2015-08-21,2015-08-24,3.6250,3.2630,3.988,3.263,-0.099862,0,1,close_limit_down
P6,A,tradable,official,5-month,exit,csi500,510500,2015-08-21,2015-08-24,7.6980,6.9280,8.468,6.928,-0.100026,0,1,close_limit_down
P6,A,tradable,official,5-week,exit,chinext,159915,2015-08-21,2015-08-24,2.2260,2.0030,2.449,2.003,-0.100180,0,1,close_limit_down
P6,A,tradable,official,5-week,exit,csi-dividend,510880,2015-08-21,2015-08-24,2.8790,2.5910,3.167,2.591,-0.100035,0,1,close_limit_down
P6,A,tradable,official,5-week,exit,csi300,510300,2015-08-21,2015-08-24,3.6250,3.2630,3.988,3.263,-0.099862,0,1,close_limit_down
P6,A,tradable,official,5-week,exit,csi500,510500,2015-08-21,2015-08-24,7.6980,6.9280,8.468,6.928,-0.100026,0,1,close_limit_down
P6,A,tradable,official,8-month,exit,csi-dividend,510880,2015-08-21,2015-08-24,2.8790,2.5910,3.167,2.591,-0.100035,0,1,close_limit_down
P6,A,tradable,official,8-month,exit,csi300,510300,2015-08-21,2015-08-24,3.6250,3.2630,3.988,3.263,-0.099862,0,1,close_limit_down
P6,A,tradable,official,8-month,exit,csi500,510500,2015-08-21,2015-08-24,7.6980,6.9280,8.468,6.928,-0.100026,0,1,close_limit_down
P6,A,tradable,official,8-week,exit,chinext,159915,2015-08-21,2015-08-24,2.2260,2.0030,2.449,2.003,-0.100180,0,1,close_limit_down
P6,A,tradable,official,8-week,exit,csi-dividend,510880,2015-08-21,2015-08-24,2.8790,2.5910,3.167,2.591,-0.100035,0,1,close_limit_down
P6,A,tradable,official,8-week,exit,csi300,510300,2015-08-21,2015-08-24,3.6250,3.2630,3.988,3.263,-0.099862,0,1,close_limit_down
P6,A,tradable,official,8-week,exit,csi500,510500,2015-08-21,2015-08-24,7.6980,6.9280,8.468,6.928,-0.100026,0,1,close_limit_down
P7,A,tradable,publish_date,3-month,exit,csi-dividend,510880,2015-08-21,2015-08-24,2.8790,2.5910,3.167,2.591,-0.100035,0,1,close_limit_down
P7,A,tradable,publish_date,3-month,exit,csi500,510500,2015-08-21,2015-08-24,7.6980,6.9280,8.468,6.928,-0.100026,0,1,close_limit_down
P7,A,tradable,publish_date,3-week,exit,chinext,159915,2015-08-21,2015-08-24,2.2260,2.0030,2.449,2.003,-0.100180,0,1,close_limit_down
P7,A,tradable,publish_date,3-week,exit,csi-dividend,510880,2015-08-21,2015-08-24,2.8790,2.5910,3.167,2.591,-0.100035,0,1,close_limit_down
P7,A,tradable,publish_date,3-week,exit,csi500,510500,2015-08-21,2015-08-24,7.6980,6.9280,8.468,6.928,-0.100026,0,1,close_limit_down
P7,A,tradable,publish_date,5-month,exit,csi-dividend,510880,2015-08-21,2015-08-24,2.8790,2.5910,3.167,2.591,-0.100035,0,1,close_limit_down
P7,A,tradable,publish_date,5-month,exit,csi300,510300,2015-08-21,2015-08-24,3.6250,3.2630,3.988,3.263,-0.099862,0,1,close_limit_down
P7,A,tradable,publish_date,5-month,exit,csi500,510500,2015-08-21,2015-08-24,7.6980,6.9280,8.468,6.928,-0.100026,0,1,close_limit_down
P7,A,tradable,publish_date,5-week,exit,chinext,159915,2015-08-21,2015-08-24,2.2260,2.0030,2.449,2.003,-0.100180,0,1,close_limit_down
P7,A,tradable,publish_date,5-week,exit,csi-dividend,510880,2015-08-21,2015-08-24,2.8790,2.5910,3.167,2.591,-0.100035,0,1,close_limit_down
P7,A,tradable,publish_date,5-week,exit,csi300,510300,2015-08-21,2015-08-24,3.6250,3.2630,3.988,3.263,-0.099862,0,1,close_limit_down
P7,A,tradable,publish_date,5-week,exit,csi500,510500,2015-08-21,2015-08-24,7.6980,6.9280,8.468,6.928,-0.100026,0,1,close_limit_down
P7,A,tradable,publish_date,8-month,exit,csi-dividend,510880,2015-08-21,2015-08-24,2.8790,2.5910,3.167,2.591,-0.100035,0,1,close_limit_down
P7,A,tradable,publish_date,8-month,exit,csi300,510300,2015-08-21,2015-08-24,3.6250,3.2630,3.988,3.263,-0.099862,0,1,close_limit_down
P7,A,tradable,publish_date,8-month,exit,csi500,510500,2015-08-21,2015-08-24,7.6980,6.9280,8.468,6.928,-0.100026,0,1,close_limit_down
P7,A,tradable,publish_date,8-week,exit,chinext,159915,2015-08-21,2015-08-24,2.2260,2.0030,2.449,2.003,-0.100180,0,1,close_limit_down
P7,A,tradable,publish_date,8-week,exit,csi-dividend,510880,2015-08-21,2015-08-24,2.8790,2.5910,3.167,2.591,-0.100035,0,1,close_limit_down
P7,A,tradable,publish_date,8-week,exit,csi300,510300,2015-08-21,2015-08-24,3.6250,3.2630,3.988,3.263,-0.099862,0,1,close_limit_down
P7,A,tradable,publish_date,8-week,exit,csi500,510500,2015-08-21,2015-08-24,7.6980,6.9280,8.468,6.928,-0.100026,0,1,close_limit_down
P8,S1,tradable,official,3-month,exit,csi-dividend,510880,2015-08-21,2015-08-24,2.8790,2.5910,3.167,2.591,-0.100035,0,1,close_limit_down
P8,S1,tradable,official,3-month,exit,csi500,510500,2015-08-21,2015-08-24,7.6980,6.9280,8.468,6.928,-0.100026,0,1,close_limit_down
P8,S1,tradable,official,3-week,exit,chinext,159915,2015-08-21,2015-08-24,2.2260,2.0030,2.449,2.003,-0.100180,0,1,close_limit_down
P8,S1,tradable,official,3-week,exit,csi-dividend,510880,2015-08-21,2015-08-24,2.8790,2.5910,3.167,2.591,-0.100035,0,1,close_limit_down
P8,S1,tradable,official,3-week,exit,csi500,510500,2015-08-21,2015-08-24,7.6980,6.9280,8.468,6.928,-0.100026,0,1,close_limit_down
P8,S1,tradable,official,5-month,exit,csi-dividend,510880,2015-08-21,2015-08-24,2.8790,2.5910,3.167,2.591,-0.100035,0,1,close_limit_down
P8,S1,tradable,official,5-month,exit,csi300,510300,2015-08-21,2015-08-24,3.6250,3.2630,3.988,3.263,-0.099862,0,1,close_limit_down
P8,S1,tradable,official,5-month,exit,csi500,510500,2015-08-21,2015-08-24,7.6980,6.9280,8.468,6.928,-0.100026,0,1,close_limit_down
P8,S1,tradable,official,5-week,exit,chinext,159915,2015-08-21,2015-08-24,2.2260,2.0030,2.449,2.003,-0.100180,0,1,close_limit_down
P8,S1,tradable,official,5-week,exit,csi-dividend,510880,2015-08-21,2015-08-24,2.8790,2.5910,3.167,2.591,-0.100035,0,1,close_limit_down
P8,S1,tradable,official,5-week,exit,csi300,510300,2015-08-21,2015-08-24,3.6250,3.2630,3.988,3.263,-0.099862,0,1,close_limit_down
P8,S1,tradable,official,5-week,exit,csi500,510500,2015-08-21,2015-08-24,7.6980,6.9280,8.468,6.928,-0.100026,0,1,close_limit_down
P8,S1,tradable,official,8-month,exit,csi-dividend,510880,2015-08-21,2015-08-24,2.8790,2.5910,3.167,2.591,-0.100035,0,1,close_limit_down
P8,S1,tradable,official,8-month,exit,csi300,510300,2015-08-21,2015-08-24,3.6250,3.2630,3.988,3.263,-0.099862,0,1,close_limit_down
P8,S1,tradable,official,8-month,exit,csi500,510500,2015-08-21,2015-08-24,7.6980,6.9280,8.468,6.928,-0.100026,0,1,close_limit_down
P8,S1,tradable,official,8-week,exit,chinext,159915,2015-08-21,2015-08-24,2.2260,2.0030,2.449,2.003,-0.100180,0,1,close_limit_down
P8,S1,tradable,official,8-week,exit,csi-dividend,510880,2015-08-21,2015-08-24,2.8790,2.5910,3.167,2.591,-0.100035,0,1,close_limit_down
P8,S1,tradable,official,8-week,exit,csi300,510300,2015-08-21,2015-08-24,3.6250,3.2630,3.988,3.263,-0.099862,0,1,close_limit_down
P8,S1,tradable,official,8-week,exit,csi500,510500,2015-08-21,2015-08-24,7.6980,6.9280,8.468,6.928,-0.100026,0,1,close_limit_down
P9,S2,tradable,official,3-month,exit,s2-中证500,510500,2015-08-21,2015-08-24,7.6980,6.9280,8.468,6.928,-0.100026,0,1,close_limit_down
P9,S2,tradable,official,3-month,exit,s2-红利,510880,2015-08-21,2015-08-24,2.8790,2.5910,3.167,2.591,-0.100035,0,1,close_limit_down
P9,S2,tradable,official,3-week,exit,s2-中证500,510500,2015-08-21,2015-08-24,7.6980,6.9280,8.468,6.928,-0.100026,0,1,close_limit_down
P9,S2,tradable,official,3-week,exit,s2-创业板,159915,2015-08-21,2015-08-24,2.2260,2.0030,2.449,2.003,-0.100180,0,1,close_limit_down
P9,S2,tradable,official,3-week,exit,s2-红利,510880,2015-08-21,2015-08-24,2.8790,2.5910,3.167,2.591,-0.100035,0,1,close_limit_down
P9,S2,tradable,official,5-month,exit,s2-中证500,510500,2015-08-21,2015-08-24,7.6980,6.9280,8.468,6.928,-0.100026,0,1,close_limit_down
P9,S2,tradable,official,5-month,exit,s2-沪深300,510300,2015-08-21,2015-08-24,3.6250,3.2630,3.988,3.263,-0.099862,0,1,close_limit_down
P9,S2,tradable,official,5-month,exit,s2-红利,510880,2015-08-21,2015-08-24,2.8790,2.5910,3.167,2.591,-0.100035,0,1,close_limit_down
P9,S2,tradable,official,5-week,exit,s2-中证500,510500,2015-08-21,2015-08-24,7.6980,6.9280,8.468,6.928,-0.100026,0,1,close_limit_down
P9,S2,tradable,official,5-week,exit,s2-创业板,159915,2015-08-21,2015-08-24,2.2260,2.0030,2.449,2.003,-0.100180,0,1,close_limit_down
P9,S2,tradable,official,5-week,exit,s2-沪深300,510300,2015-08-21,2015-08-24,3.6250,3.2630,3.988,3.263,-0.099862,0,1,close_limit_down
P9,S2,tradable,official,5-week,exit,s2-红利,510880,2015-08-21,2015-08-24,2.8790,2.5910,3.167,2.591,-0.100035,0,1,close_limit_down
P9,S2,tradable,official,8-month,exit,s2-中证500,510500,2015-08-21,2015-08-24,7.6980,6.9280,8.468,6.928,-0.100026,0,1,close_limit_down
P9,S2,tradable,official,8-month,exit,s2-沪深300,510300,2015-08-21,2015-08-24,3.6250,3.2630,3.988,3.263,-0.099862,0,1,close_limit_down
P9,S2,tradable,official,8-month,exit,s2-红利,510880,2015-08-21,2015-08-24,2.8790,2.5910,3.167,2.591,-0.100035,0,1,close_limit_down
P9,S2,tradable,official,8-week,exit,s2-中证500,510500,2015-08-21,2015-08-24,7.6980,6.9280,8.468,6.928,-0.100026,0,1,close_limit_down
P9,S2,tradable,official,8-week,exit,s2-创业板,159915,2015-08-21,2015-08-24,2.2260,2.0030,2.449,2.003,-0.100180,0,1,close_limit_down
P9,S2,tradable,official,8-week,exit,s2-沪深300,510300,2015-08-21,2015-08-24,3.6250,3.2630,3.988,3.263,-0.099862,0,1,close_limit_down
P9,S2,tradable,official,8-week,exit,s2-红利,510880,2015-08-21,2015-08-24,2.8790,2.5910,3.167,2.591,-0.100035,0,1,close_limit_down

P6（A / 可交易 / 官方）的 173 个离场信号里，计划卖出日收盘跌停的笔数应与 2026-10-27 诊断里的 22 笔一致。
成交仍按现有规则用收盘价。要不要改成顺延，留给 v4。


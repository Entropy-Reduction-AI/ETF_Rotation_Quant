"""Content-specific components for contract pages (first used by the v6 pre-registration).

Lesson from the forecast page (Owner 2026-11-24): every element takes the form its content has. A process is a
step grid, an allocation is a stacked bar, a classification is a sorting board, a set of pass/fail gates is a gate
row, a schedule is a route with "you are here". Detail tables stay plain and sit in folds.

The md carries the data as a small table right below a marker; the renderer only chooses the form:

  <!-- 组件：分拣 -->   | 组 | 组结论 | # | 条目 |            → columns per group, count, verdict, item chips
  <!-- 组件：闸门 -->   | 编号 | 名称 | 门槛 | 事先机会 |       → gate row with the threshold big and a chance bar
                       last row 编号 = 合计 is the "all gates" box
  <!-- 组件：构成 -->   | 名称 | 成分 | 用途 |                 → one stacked bar per row; 成分 = "沪深300 70｜纳指100 15"
  <!-- 组件：计数 -->   | 类别 | 个数 | 含义 |                 → one segmented count bar with legend
  <!-- 组件：路线 -->   | 步 | 谁 | 状态 |                     → chevron route; 状态 = 已完成 / 现在 / 你批准 / 之后
  <!-- 组件：载体 -->   | 类型 | 候选 |                       → one chip row per type (同一指数 / 相近指数 / 无场内基金)
"""
import re
from bs4 import BeautifulSoup, Comment

PAL = ['var(--accent)', 'color-mix(in srgb, var(--accent) 50%, white)', 'var(--good)', 'var(--warn)', 'var(--muted)', 'var(--bad)']


def _rows(t):
    head = [th.get_text(' ', strip=True) for th in t.select('thead th')]
    rows = []
    for tr in t.select('tbody tr'):
        tds = tr.find_all('td')
        rows.append({h: td for h, td in zip(head, tds)})
    return head, rows


def _txt(td):
    return td.get_text(' ', strip=True) if td is not None else ''


def _inner(td):
    return td.decode_contents().strip() if td is not None else ''


def sort_board(rows):
    groups = []
    for r in rows:
        g = _txt(r['组'])
        if not groups or groups[-1][0] != g:
            groups.append((g, _inner(r['组结论']), []))
        groups[-1][2].append((_txt(r['#']), _inner(r['条目'])))
    tones = ['bad', 'mute', 'good']
    cols = ''
    for i, (g, v, items) in enumerate(groups):
        chips = ''.join(f'<li><span class="sb-n">{n}</span>{x}</li>' for n, x in items)
        cols += (f'<div class="sb-col t-{tones[i % 3]}"><div class="sb-h"><span class="sb-k">{len(items)}</span>'
                 f'<span class="sb-g">{g}</span></div><div class="sb-v">{v}</div><ul class="sb-l">{chips}</ul></div>')
    return f'<div class="sortboard n{len(groups)}">{cols}</div>'


def gate_row(rows):
    out = ''
    for r in rows:
        code, name, th, ch = _txt(r['编号']), _inner(r['名称']), _inner(r['门槛']), _txt(r['事先机会'])
        pct = re.search(r'(\d+)', ch)
        w = int(pct.group(1)) if pct else 0
        tot = code == '合计'
        out += (f'<div class="gt{" gt-all" if tot else ""}"><div class="gt-c">{"" if tot else code}</div><div class="gt-n">{name}</div>'
                f'<div class="gt-t">{th}</div><div class="gt-b"><i style="width:{w}%"></i></div><div class="gt-p">事先估计通过 <b>{ch}</b></div></div>')
    return f'<div class="gaterow">{out}</div>'


def composition(rows):
    out = ''
    for r in rows:
        segs = []
        for x in _txt(r['成分']).split('｜'):
            m = re.match(r'^(.+?)\s*(\d+(?:\.\d+)?)$', x.strip())
            if m:
                segs.append((m.group(1).strip(), float(m.group(2))))
        bar = ''.join(f'<span style="flex:{v};background:{PAL[i % len(PAL)]}">{n} {v:g}</span>' for i, (n, v) in enumerate(segs))
        out += (f'<div class="cp-r"><div class="cp-k">{_inner(r["名称"])}</div><div class="cp-bar">{bar}</div>'
                f'<div class="cp-u">{_inner(r["用途"])}</div></div>')
    return f'<div class="compo">{out}</div>'


def count_bar(rows):
    tot = sum(int(re.sub(r'\D', '', _txt(r['个数'])) or 0) for r in rows)
    seg = leg = ''
    for i, r in enumerate(rows):
        n = int(re.sub(r'\D', '', _txt(r['个数'])) or 0)
        seg += f'<span style="flex:{n};background:{PAL[i % len(PAL)]}"></span>'
        leg += f'<span class="cb-i"><i style="background:{PAL[i % len(PAL)]}"></i><b>{n}</b> {_inner(r["类别"])}<em>{_inner(r["含义"])}</em></span>'
    return f'<div class="countbar"><div class="cb-bar">{seg}</div><div class="cb-l">{leg}<span class="cb-t">共 {tot}</span></div></div>'


def route(rows):
    out = ''
    for r in rows:
        st = _txt(r['状态'])
        k = {'已完成': 'done', '现在': 'now', '你批准': 'you'}.get(st, 'todo')
        out += (f'<li class="rt-{k}"><span class="rt-s">{_inner(r["步"])}</span><span class="rt-w">{_inner(r["谁"])}</span>'
                f'<span class="rt-st">{st}</span></li>')
    return f'<ol class="route">{out}</ol>'


def chain(rows):
    out = ''
    for i, r in enumerate(rows):
        cond = _inner(r.get('条件')) if r.get('条件') is not None else ''
        if i:
            out += f'<div class="ch-a"><span>{cond}</span></div>'
        out += f'<div class="ch-s"><div class="ch-n">{_inner(r["步"])}</div><div class="ch-d">{_inner(r["说明"])}</div></div>'
    return f'<div class="chain">{out}</div>'


def pain(rows):
    # grouped rows: a coloured group rail, the scenario, the accepted cost as a big value, the tripwire in red
    out, last = '', None
    tones = {'结构': 'accent', '防守': 'warn', '挑选': 'good', '执行': 'mute'}
    groups = []
    for r in rows:
        g = _txt(r['组'])
        if not groups or groups[-1][0] != g:
            groups.append((g, []))
        groups[-1][1].append(r)
    for g, rs in groups:
        items = ''
        for r in rs:
            items += (f'<div class="pn-r"><div class="pn-s"><b>{_inner(r["情形"])}</b><span>{_inner(r["会发生什么"])}</span></div>'
                      f'<div class="pn-v"><b>{_inner(r["代价"])}</b><span>{_inner(r["代价说明"])}</span></div>'
                      f'<div class="pn-t"><span class="pn-tl">越过就查</span>{_inner(r["警戒线"])}</div></div>')
        out += f'<div class="pn-g t-{tones.get(g, "mute")}"><div class="pn-gk">{g}<em>{len(rs)}</em></div><div class="pn-gb">{items}</div></div>'
    return f'<div class="pain">{out}</div>'


def risks(rows):
    out = ''
    for r in rows:
        watch = ''.join(f'<span class="rk-c">{x.strip()}</span>' for x in re.split(r'[；;]', _txt(r['在哪里盯'])) if x.strip())
        out += (f'<div class="rk"><span class="rk-n">{_txt(r["排名"])}</span><div class="rk-b"><b>{_inner(r["原因"])}</b>'
                f'<span>{_inner(r["会怎样"])}</span></div><div class="rk-w"><em>盯</em>{watch}</div></div>')
    return f'<div class="risks">{out}</div>'


def carriers(rows):
    tone = {'同一指数': 'good', '相近指数': 'warn', '无场内基金': 'bad', '通过': 'good', '不通过': 'bad', '暂停线': 'bad'}
    out = ''
    for r in rows:
        k = _txt(r['类型'])
        t = tone.get(k) or ('bad' if '无场内基金' in k else 'mute')
        items = [x.strip() for x in re.split(r'[、，,]', _txt(r['候选'])) if x.strip()]
        chips = ''.join(f'<span class="cr-c">{x}</span>' for x in items)
        cnt = '' if k in ('通过', '不通过') else f'<b>{len(items)}</b> '
        out += f'<div class="cr-r t-{t}"><div class="cr-k">{cnt}{k}</div><div class="cr-cs">{chips}</div></div>'
    return f'<div class="carriers">{out}</div>'


RENDER = {'代价': pain, '风险': risks, '退路': chain, '分拣': sort_board, '闸门': gate_row, '构成': composition, '计数': count_bar, '路线': route, '载体': carriers}


def apply(soup):
    for c in list(soup.find_all(string=lambda x: isinstance(x, Comment) and re.match(r'^\s*组件：', str(x)))):
        spec = str(c).split('：', 1)[1].strip().split('｜')
        kind, title = spec[0].strip(), (spec[1].strip() if len(spec) > 1 else '')
        t = c.find_next('table')
        c.extract()
        if t is None or kind not in RENDER:
            continue
        _, rows = _rows(t)
        html = RENDER[kind](rows)
        head = f'<div class="comp-h">{title}</div>' if title else ''
        node = BeautifulSoup(f'<div class="comp comp-{kind}" data-lint="ref">{head}{html}</div>', 'html.parser')
        t.replace_with(node)


CSS = r"""
/* ===== content-specific components (components.py) ===== */
.comp { margin: 10px 0 20px; }
.comp-h { font-size: 13.5px; font-weight: 700; color: var(--ink); margin-bottom: 8px; }
.chain { display: flex; align-items: stretch; gap: 0; flex-wrap: wrap; }
.ch-s { flex: 1 1 150px; background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 10px 12px; }
.ch-n { font-size: 15px; font-weight: 700; color: var(--ink); }
.ch-d { font-size: 12.5px; color: var(--muted); margin-top: 3px; line-height: 1.45; }
.ch-a { flex: 0 0 92px; display: grid; place-items: center; text-align: center; font-size: 12px; color: var(--accent); font-weight: 700; position: relative; padding: 0 6px; }
.ch-a::after { content: '→'; display: block; font-size: 18px; line-height: 1; }
.ch-a span { line-height: 1.35; }
.sortboard { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }
.sb-col { background: var(--surface); border: 1px solid var(--line); border-top: 4px solid var(--muted); border-radius: 10px; padding: 12px 14px; }
.sb-col.t-bad { border-top-color: var(--bad); } .sb-col.t-good { border-top-color: var(--good); }
.sb-h { display: flex; align-items: baseline; gap: 8px; }
.sb-k { font-size: 30px; font-weight: 800; line-height: 1; color: var(--ink); font-family: var(--font-mono); }
.sb-col.t-bad .sb-k { color: var(--bad); } .sb-col.t-good .sb-k { color: var(--good); }
.sb-g { font-size: 15px; font-weight: 700; color: var(--ink); }
.sb-v { font-size: 13.5px; color: var(--ink); margin: 6px 0 8px; padding: 5px 8px; background: var(--bg); border-radius: 6px; line-height: 1.5; }
.sb-l { list-style: none; padding: 0; margin: 0; display: grid; gap: 5px; }
.sb-l li { font-size: 13.5px; color: var(--muted); line-height: 1.45; margin: 0; padding: 0; }
.sb-l li::before { display: none; }
.sb-n { display: inline-grid; place-items: center; min-width: 18px; height: 18px; border-radius: 50%; background: var(--line); color: var(--ink); font-size: 11px; font-family: var(--font-mono); margin-right: 6px; }
.gaterow { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; }
.gt { background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 12px 14px 10px; display: grid; gap: 4px; align-content: start; }
.gt-c { font-size: 13px; color: var(--accent); font-weight: 700; min-height: 1em; }
.gt-n { font-size: 13px; color: var(--muted); line-height: 1.4; }
.gt-t { font-size: 22px; font-weight: 800; color: var(--ink); line-height: 1.2; }
.gt-b { height: 6px; background: var(--line); border-radius: 3px; overflow: hidden; margin-top: 4px; }
.gt-b i { display: block; height: 100%; background: var(--good); border-radius: 3px; }
.gt-p { font-size: 12.5px; color: var(--muted); } .gt-p b { color: var(--ink); font-family: var(--font-mono); }
.gt-all { background: var(--ink); border-color: var(--ink); }
.gt-all .gt-n, .gt-all .gt-p { color: #cbd2dc; } .gt-all .gt-t, .gt-all .gt-p b { color: #fff; } .gt-all .gt-b { background: #3a4352; } .gt-all .gt-b i { background: #fff; }
.compo { display: grid; gap: 8px; }
.cp-r { display: grid; grid-template-columns: 7.5em minmax(0, 1fr) 13em; gap: 12px; align-items: center; }
.cp-k { font-weight: 700; font-size: 14px; color: var(--ink); }
.cp-bar { display: flex; height: 28px; border-radius: 6px; overflow: hidden; gap: 2px; background: var(--surface); }
.cp-bar span { color: #fff; font-size: 12px; display: grid; place-items: center; white-space: nowrap; overflow: hidden; }
.cp-u { font-size: 13px; color: var(--muted); line-height: 1.45; }
.countbar { display: grid; gap: 8px; }
.cb-bar { display: flex; height: 10px; gap: 2px; border-radius: 5px; overflow: hidden; }
.cb-l { display: flex; flex-wrap: wrap; gap: 6px 18px; font-size: 13.5px; color: var(--ink); align-items: baseline; }
.cb-i i { display: inline-block; width: 9px; height: 9px; border-radius: 2px; margin-right: 6px; }
.cb-i b { font-family: var(--font-mono); margin-right: 3px; }
.cb-i em { font-style: normal; color: var(--muted); margin-left: 6px; font-size: 12.5px; }
.cb-t { color: var(--muted); font-size: 12.5px; margin-left: auto; padding-right: 4px; white-space: nowrap; }
ol.route { list-style: none; padding: 0; margin: 0; display: grid; grid-template-columns: repeat(auto-fit, minmax(110px, 1fr)); gap: 4px; counter-reset: none; }
ol.route li { position: relative; margin: 0; padding: 10px 10px 9px 12px; background: var(--surface); border: 1px solid var(--line); border-radius: 8px; display: grid; gap: 2px; }
ol.route li::before { display: none; }
ol.route li .rt-s, ol.route li .rt-w, ol.route li .rt-st { display: block !important; } ol.route li > b { font-weight: inherit; }
.rt-s { font-size: 14px; font-weight: 700; color: var(--ink); line-height: 1.35; }
.rt-w { font-size: 12px; color: var(--muted); }
.rt-st { font-size: 12px; font-weight: 700; color: var(--muted); }
ol.route li.rt-done { background: var(--good-soft); border-color: transparent; } ol.route li.rt-done .rt-st { color: var(--good); }
ol.route li.rt-now { border: 2px solid var(--accent); } ol.route li.rt-now .rt-st { color: var(--accent); }
ol.route li.rt-you { border: 2px dashed var(--accent); } ol.route li.rt-you .rt-st { color: var(--accent); }
.carriers { display: grid; gap: 6px; }
.cr-r { display: grid; grid-template-columns: 9.5em minmax(0, 1fr); gap: 12px; align-items: center; padding: 8px 12px; background: var(--surface); border: 1px solid var(--line); border-left: 4px solid var(--muted); border-radius: 8px; }
.cr-r.t-good { border-left-color: var(--good); } .cr-r.t-warn { border-left-color: var(--warn); } .cr-r.t-bad { border-left-color: var(--bad); }
.cr-k { font-size: 14px; color: var(--ink); } .cr-k b { font-size: 20px; font-family: var(--font-mono); margin-right: 4px; }
.cr-cs { display: flex; flex-wrap: wrap; gap: 5px; }
.cr-c { font-size: 13px; padding: 2px 8px; border-radius: 5px; background: var(--bg); border: 1px solid var(--line); }
.pain { display: grid; gap: 10px; }
.pn-g { display: grid; grid-template-columns: 5.5em minmax(0, 1fr); background: var(--surface); border: 1px solid var(--line); border-radius: 10px; overflow: hidden; }
.pn-gk { padding: 12px 10px; font-size: 15px; font-weight: 800; color: var(--ink); border-right: 1px solid var(--line); border-left: 5px solid var(--muted); display: grid; align-content: start; gap: 2px; }
.pn-gk em { font-style: normal; font-size: 12px; font-weight: 500; color: var(--muted); }
.pn-gk em::after { content: ' 种'; }
.pn-g.t-accent .pn-gk { border-left-color: var(--accent); } .pn-g.t-warn .pn-gk { border-left-color: var(--warn); } .pn-g.t-good .pn-gk { border-left-color: var(--good); }
.pn-r { display: grid; grid-template-columns: minmax(0, 1.1fr) minmax(0, 1fr) minmax(0, 1fr); gap: 14px; padding: 10px 14px; border-top: 1px solid var(--line); align-items: start; }
.pn-r:first-child { border-top: 0; }
.pn-s b { display: block; font-size: 14.5px; color: var(--ink); }
.pn-s span, .pn-v span { display: block; font-size: 12.5px; color: var(--muted); line-height: 1.45; margin-top: 2px; }
.pn-v b { display: block; font-size: 19px; line-height: 1.25; color: var(--ink); font-weight: 800; }
.pn-t { font-size: 13.5px; color: var(--bad); line-height: 1.45; }
.pn-tl { display: block; font-size: 11.5px; color: var(--muted); font-weight: 700; letter-spacing: .04em; }
.risks { display: grid; gap: 6px; }
.risks > .rk { display: grid; grid-template-columns: 2.4em minmax(0, 1fr) minmax(0, 15em); gap: 12px; align-items: center; padding: 10px 14px; background: var(--surface); border: 1px solid var(--line); border-radius: 10px; }
.risks > .rk:first-child { border: 2px solid var(--bad); }
.rk-n { font-size: 24px; font-weight: 800; color: var(--muted); font-family: var(--font-mono); text-align: center; }
  .risks > .rk:first-child .rk-n { color: var(--bad); }
.rk-b b { display: block; font-size: 15px; color: var(--ink); }
.rk-b span { display: block; font-size: 13px; color: var(--muted); line-height: 1.45; margin-top: 2px; }
.rk-w { display: flex; flex-wrap: wrap; gap: 4px; align-items: center; }
.rk-w em { font-style: normal; font-size: 11.5px; color: var(--muted); font-weight: 700; margin-right: 2px; }
.rk-c { font-size: 12.5px; padding: 1px 7px; border-radius: 5px; background: var(--bg); border: 1px solid var(--line); }
@media (max-width: 760px) { .pn-g, .pn-r, .risks > .rk { grid-template-columns: minmax(0, 1fr); } .pn-gk { border-right: 0; border-bottom: 1px solid var(--line); } }
@media (max-width: 760px) { .cp-r, .cr-r { grid-template-columns: minmax(0, 1fr); gap: 4px; } }
"""

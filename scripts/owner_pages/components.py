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
        chips = ''.join(f'<li><span class="sb-n">{n}</span><span class="sb-x">{x}</span></li>' for n, x in items)
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
    """Proportional cards: width = count; the first category is the one the title is about."""
    tot = sum(int(re.sub(r'\D', '', _txt(r['个数'])) or 0) for r in rows)
    out = ''
    for i, r in enumerate(rows):
        n = int(re.sub(r'\D', '', _txt(r['个数'])) or 0)
        names = [x.strip() for x in re.split(r'[、，,]', _txt(r['含义'])) if x.strip()]
        chips = ''
        for x in names:
            more = x.endswith('等') and len(x) > 1
            core = x[:-1] if more else x
            chips += f'<span class="cbx-i"><i></i>{core}</span>' + ('<span class="cbx-i etc">等</span>' if more else '')
        out += (f'<div class="cbx-c{" on" if i == 0 else ""}" style="flex:{max(n, 1)} 1 0">'
                f'<div class="cbx-top"><b>{n}</b><span>{_inner(r["类别"])}</span></div>'
                f'<div class="cbx-is">{chips}</div></div>')
    return f'<div class="cbx">{out}<div class="cbx-t">共 <b>{tot}</b></div></div>'


def route(rows):
    out = ''
    for r in rows:
        st = _txt(r['状态'])
        k = {'已完成': 'done', '现在': 'now', '你批准': 'you'}.get(st, 'todo')
        out += (f'<li class="rt-{k}"><b class="rt-b"><span class="rt-dot">{"✓" if k == "done" else len(out.split("<li")) }</span><span class="rt-s">{_inner(r["步"])}</span>'
                f'<span class="rt-w">{_inner(r["谁"])}</span><span class="rt-st">{st}</span></b></li>')
    return f'<ol class="route">{out}</ol>'


def chain(rows):
    """Fallback staircase: each step sits a little lower than the one before; the riser says when you drop to it."""
    out = ''
    last = len(rows) - 1
    for i, r in enumerate(rows):
        cond = _inner(r.get('条件')) if r.get('条件') is not None else ''
        head = '默认' if i == 0 else f'<span class="st-ar">↘</span>{cond}'
        tag = '' if i == 0 else ('兜底' if i == last else '')
        out += (f'<div class="st-s{" first" if i == 0 else ""}{" last" if i == last else ""}" style="--i:{i}">'
                f'<div class="st-if">{head}</div><div class="st-c"><span class="st-n">{i + 1}</span>'
                f'<b>{_inner(r["步"])}</b><span class="st-d">{_inner(r["说明"])}</span>'
                + (f'<em class="st-tag">{tag}</em>' if tag else '') + '</div></div>')
    return f'<div class="stair">{out}</div>'


NUMU = re.compile(r'([±+−\-]?\d+(?:\.\d+)?)(?:\s*[–-]\s*(\d+(?:\.\d+)?))?\s*(点|万)')


def _cost_html(cost):
    t = _txt(cost)
    m = NUMU.search(t)
    if not m:
        return f'<span class="pn-big">{cost}</span>'
    return (f'<span class="pn-pre">{t[:m.start()].strip()}</span><span class="pn-big">{m.group(0).strip()}</span>'
            f'<span class="pn-pre">{t[m.end():].strip()}</span>')


def _gauge(cost, trip):
    c, tr = NUMU.search(_txt(cost)), NUMU.search(_txt(trip))
    if not c or not tr or c.group(3) != tr.group(3) or '±' in c.group(1):
        return ''
    lo_c = float(c.group(1).replace('−', '-')); hi_c = float(c.group(2)) if c.group(2) else lo_c
    lim = float(tr.group(1).replace('−', '-'))
    floor = '低于' in _txt(trip)
    if floor:
        a, b = lim * 0.8, max(hi_c, lim) * 1.12
    else:
        a, b = 0.0, lim * 1.25
    pos = lambda v: f'{(v - a) / (b - a) * 100:.1f}%'
    band = (f'<i class="pg-band" style="left:{pos(lo_c)};width:calc({pos(hi_c)} - {pos(lo_c)})"></i>' if hi_c != lo_c
            else f'<i class="pg-pt" style="left:{pos(lo_c)}"></i>')
    zone = (f'<i class="pg-zone" style="left:0;width:{pos(lim)}"></i>' if floor else f'<i class="pg-zone" style="left:{pos(lim)};right:0"></i>')
    return (f'<div class="pg"><div class="pg-t">{zone}{band}<i class="pg-lim" style="left:{pos(lim)}"></i></div>'
            f'<div class="pg-l"><span style="left:{pos((lo_c + hi_c) / 2)}">代价</span><span class="r" style="left:{pos(lim)}">警戒线</span></div></div>')


def pain(rows):
    # grouped rows: a coloured group rail; the scenario; the accepted cost as a number; a gauge to the tripwire when both share a unit
    tones = {'结构': 'accent', '防守': 'warn', '挑选': 'good', '执行': 'mute'}
    groups = []
    for r in rows:
        g = _txt(r['组'])
        if not groups or groups[-1][0] != g:
            groups.append((g, []))
        groups[-1][1].append(r)
    out = '<div class="pn-hd"><span></span><span>情形</span><span>事先认下的代价</span><span>越过就要查</span></div>'
    for g, rs in groups:
        items = ''
        for r in rs:
            gz = _gauge(r['代价'], r['警戒线'])
            items += (f'<div class="pn-r"><div class="pn-s"><span class="pn-name">{_inner(r["情形"])}</span><span class="pn-what">{_inner(r["会发生什么"])}</span></div>'
                      f'<div class="pn-v"><div class="pn-cost">{_cost_html(r["代价"])}</div><span class="pn-note">{_inner(r["代价说明"])}</span>{gz}</div>'
                      f'<div class="pn-t"><span class="pn-trip">{_inner(r["警戒线"])}</span></div></div>')
        out += f'<div class="pn-g t-{tones.get(g, "mute")}"><div class="pn-gk"><span>{g}</span><em>{len(rs)}</em></div><div class="pn-gb">{items}</div></div>'
    return f'<div class="pain pain2">{out}</div>'


def risks(rows):
    out = ('<div class="rk rk-hd"><span></span><span>原因</span><span>会怎样</span><span>在哪里盯</span></div>')
    for i, r in enumerate(rows):
        watch = ''.join(f'<span class="rk-c">{x.strip()}</span>' for x in re.split(r'[；;]', _txt(r['在哪里盯'])) if x.strip())
        sev = 'sev1' if i == 0 else ('sev2' if i == 1 else 'sev3')
        out += (f'<div class="rk {sev}"><span class="rk-n">{_txt(r["排名"])}</span><b class="rk-why">{_inner(r["原因"])}</b>'
                f'<span class="rk-then">{_inner(r["会怎样"])}</span><div class="rk-w">{watch}</div></div>')
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


def _split_top(s):
    """Split on 、 outside （） so '9 个行业 SPDR（XLK、XLV）' stays one item."""
    out, buf, depth = [], '', 0
    for ch in s:
        if ch in '（(':
            depth += 1
        elif ch in '）)':
            depth -= 1
        if ch == '、' and depth == 0:
            out.append(buf.strip()); buf = ''
        else:
            buf += ch
    if buf.strip():
        out.append(buf.strip())
    return out


def pool(rows, summary=''):
    """| 名额 | 母指数 | 候选 | 依据 | → one card per slot: weight, candidate count, mother index, grouped chips, source."""
    cards = ''
    for r in rows:
        slot = _txt(r['名额'])
        m = re.match(r'^(.+?)（(\d+%)）$', slot)
        name, wt = (m.group(1), m.group(2)) if m else (slot, '')
        mother = _txt(r['母指数'])
        mcode = re.search(r'（(.+?)）', mother)
        mkeys = {mother, mcode.group(1) if mcode else mother, re.sub(r'（.*', '', mother)}
        raw = _txt(r['候选'])
        total = ''
        mt = re.search(r'[，,]\s*共\s*(\d+)\s*个\s*$', raw)
        if mt:
            total, raw = mt.group(1), raw[:mt.start()]
        if not total and summary:
            ms = re.search(re.escape(name.replace('股', '')) + r'\s*股?\s*(约\s*\d+)\s*个', summary)
            total = ms.group(1).replace(' ', '') if ms else ''
        singles, groups = [], []
        for it in _split_top(raw):
            g = re.match(r'^(\d+)\s*个\s*(.+?)(?:（(.+)）)?$', it)
            ref = re.match(r'^(.+?)（(清单见.+)）$', it)
            if it in mkeys:
                continue
            if ref:
                groups.append((None, ref.group(1), [], ref.group(2)))
            elif g:
                inner = [x.strip() for x in g.group(3).split('、')] if g.group(3) else []
                groups.append((g.group(1), g.group(2), inner, ''))
            else:
                singles.append(it)
        chips = ''.join(f'<span class="pl-c">{x}</span>' for x in singles)
        grp = ''
        for n, lab, inner, note in groups:
            sub = ''.join(f'<span class="pl-s">{x}</span>' for x in inner)
            head = f'<b>{n}</b> 个{lab}' if n else f'{lab}'
            tail = f'<span class="pl-note">{note}</span>' if note else ''
            grp += f'<div class="pl-g{" pl-open" if note else ""}"><div class="pl-gh">{head}{tail}</div>{f"<div class=pl-ss>{sub}</div>" if sub else ""}</div>'
        num = re.sub(r'(\d+)', r'<b>\1</b>', total) if total else ''
        cards += (f'<div class="pl-card"><div class="pl-top"><div><span class="pl-name">{name}名额</span>'
                  f'{f"<span class=pl-w>{wt}</span>" if wt else ""}</div><div class="pl-n">{num}<span>个候选</span></div></div>'
                  f'<div class="pl-m"><span class="pl-mk">母指数</span><span class="pl-mv">{mother}</span><span class="pl-mx">也参与排名</span></div>'
                  f'<div class="pl-cs">{chips}</div>{grp}'
                  f'<div class="pl-src">{_inner(r["依据"])}</div></div>')
    return f'<div class="pool">{cards}</div>'


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
    # signature tables that carry no marker (frozen documents): | 名额 | 母指数 | 候选 | 依据 |
    for t in list(soup.find_all('table')):
        head, rows = _rows(t)
        if head == ['名额', '母指数', '候选', '依据']:
            d = t.find_parent('details')
            summ = d.summary.get_text(' ', strip=True) if d is not None and d.summary is not None else ''
            node = BeautifulSoup(f'<div class="comp comp-候选池" data-lint="ref">{pool(rows, summ)}</div>', 'html.parser')
            t.replace_with(node)


CSS = r"""
.cbx-c { gap: 10px; padding: 12px 14px; min-width: 210px; }
.cbx-top span { font-size: 13px; }
.cbx-is { display: flex; flex-wrap: wrap; gap: 6px; }
.cbx-i { display: inline-flex; align-items: center; gap: 6px; font-size: 13px; font-weight: 600; color: var(--ink); padding: 4px 9px; border-radius: 6px; background: var(--bg); border: 1px solid var(--line); }
.cbx-i i { width: 8px; height: 8px; border-radius: 2px; background: var(--muted); }
.cbx-c.on .cbx-i { background: var(--surface); border-color: var(--accent); } .cbx-c.on .cbx-i i { background: var(--accent); }
.cbx-i.etc { font-weight: 400; color: var(--muted); border-style: dashed; }

.rt-dot { font-family: var(--font-mono); font-size: 11.5px; font-weight: 700; color: var(--muted); }
ol.route li.rt-now .rt-dot, ol.route li.rt-done .rt-dot { color: #fff; } ol.route li.rt-you .rt-dot { color: var(--accent); }
ol.route li.rt-todo .rt-dot { color: var(--muted) !important; }
ol.route li.rt-todo .rt-st { border: 0; background: none; padding: 0; font-weight: 600; }
.rt-b { display: flex; flex-direction: column; gap: 2px; font-weight: inherit; }
.rt-gate { display: block; margin-top: 6px; padding: 6px 8px; border-radius: 6px; background: var(--bg); font-size: 12px; line-height: 1.5; color: var(--ink); margin-right: 10px; }
.rt-gate em { display: block; font-style: normal; font-size: 11px; font-weight: 700; color: var(--muted); }
.rt-gate.stop em { color: var(--bad); } .rt-gate.pass em { color: var(--good); }
ol.route li .rt-gate { display: block !important; }

.pain2 { display: grid; gap: 8px; }
.pain2 .pn-hd { display: grid; grid-template-columns: 108px minmax(0, 1.1fr) minmax(0, 1.2fr) minmax(0, 1fr); gap: 14px; padding: 0 14px 0 4px; } .pain2 .pn-hd > span { font-size: 11.5px; font-weight: 700; color: var(--muted); }
.pain2 .pn-g { display: grid !important; grid-template-columns: 104px minmax(0, 1fr) !important; border: 1px solid var(--line); border-left: 4px solid var(--muted); border-radius: 10px; background: var(--surface); overflow: hidden; }
.pain2 .pn-g.t-accent { border-left-color: var(--accent); } .pain2 .pn-g.t-warn { border-left-color: var(--warn); } .pain2 .pn-g.t-good { border-left-color: var(--good); }
.pain2 .pn-gk { display: flex !important; flex-direction: column; gap: 2px; padding: 12px; background: var(--bg); border-right: 1px solid var(--line); }
.pain2 .pn-gk span { font-size: 13.5px; font-weight: 700; color: var(--ink); } .pain2 .pn-gk em { font-style: normal; font-size: 11.5px; color: var(--muted); }
.pain2 .pn-r { display: grid !important; grid-template-columns: minmax(0, 1.1fr) minmax(0, 1.2fr) minmax(0, 1fr) !important; gap: 14px; padding: 11px 14px; border-top: 1px solid var(--line); align-items: start; }
.pain2 .pn-r:first-child { border-top: 0; }
.pn-name { display: block; font-size: 14px; font-weight: 600; color: var(--ink); } .pn-what { display: block; font-size: 12.5px; color: var(--muted); line-height: 1.5; margin-top: 2px; }
.pn-cost { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px; }
.pain2 .pn-v .pn-pre { display: inline; font-size: 12.5px; color: var(--muted); }
.pain2 .pn-v .pn-big { display: inline; font-family: var(--font-mono); font-size: 19px; font-weight: 800; color: var(--ink); line-height: 1.2; }
.pain2 .pn-g.t-warn .pn-big { color: var(--warn); } .pain2 .pn-g.t-accent .pn-big { color: var(--accent); }
.pain2 .pn-v .pn-note { display: block; font-size: 12px; color: var(--muted); line-height: 1.45; margin-top: 2px; }
.pn-trip { display: inline-block; font-size: 12.5px; font-weight: 600; color: var(--bad); background: var(--bad-soft); border-radius: 6px; padding: 4px 9px; line-height: 1.45; }
.pg { margin-top: 8px; max-width: 260px; }
.pg-t { position: relative; height: 8px; border-radius: 4px; background: var(--bg); border: 1px solid var(--line); }
.pg-t i { position: absolute; top: -1px; bottom: -1px; }
.pg-zone { background: var(--bad-soft); } .pg-band { background: var(--accent); border-radius: 3px; }
.pg-pt { width: 10px; margin-left: -5px; border-radius: 3px; background: var(--accent); top: -3px !important; bottom: -3px !important; }
.pn-g.t-warn .pg-pt, .pn-g.t-warn .pg-band { background: var(--warn); }
.pg-lim { width: 2px; background: var(--bad); top: -5px !important; bottom: -5px !important; }
.pg-l { position: relative; height: 15px; font-size: 11px; color: var(--muted); } .pg-l span { position: absolute; top: 2px; transform: translateX(-50%); white-space: nowrap; } .pg-l span.r { color: var(--bad); }
@media (max-width: 760px) { .pain2 .pn-hd { display: none; } .pain2 .pn-g { grid-template-columns: minmax(0, 1fr) !important; } .pain2 .pn-r { grid-template-columns: minmax(0, 1fr) !important; gap: 6px; } }

.stair { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; align-items: start; padding-bottom: 6px; }
.st-s { margin-top: calc(var(--i) * 22px); display: flex; flex-direction: column; gap: 6px; }
.st-if { min-height: 2.6em; display: flex; align-items: flex-end; gap: 4px; font-size: 12.5px; font-weight: 700; color: var(--warn); line-height: 1.35; }
.st-s.first .st-if { color: var(--accent); }
.st-ar { font-size: 15px; }
.st-c { position: relative; display: flex; flex-direction: column; gap: 4px; padding: 12px 14px 14px; border-radius: 10px; background: var(--surface); border: 1px solid var(--line); border-top: 4px solid var(--line); min-height: 112px; }
.st-s.first .st-c { border-color: var(--accent); border-top-color: var(--accent); background: var(--accent-soft); }
.st-s.last .st-c { border-top-color: var(--muted); }
.st-n { font-family: var(--font-mono); font-size: 22px; font-weight: 800; line-height: 1; color: var(--muted); opacity: .55; }
.st-s.first .st-n { color: var(--accent); }
.st-c b { font-size: 15px; color: var(--ink); line-height: 1.35; }
.st-d { font-size: 12.5px; color: var(--muted); line-height: 1.5; }
.st-tag { position: absolute; top: 10px; right: 10px; font-style: normal; font-size: 11px; padding: 0 6px; border-radius: 4px; border: 1px solid var(--line); color: var(--muted); }
@media (max-width: 760px) { .stair { grid-template-columns: minmax(0, 1fr); } .st-s { margin-top: 0; margin-left: calc(var(--i) * 12px); } .st-if { min-height: 0; } }

.cbx { display: flex; gap: 8px; align-items: stretch; flex-wrap: wrap; }
.cbx-c { min-width: 150px; display: flex; flex-direction: column; gap: 6px; padding: 10px 12px; border: 1px solid var(--line); border-radius: 10px; background: var(--surface); }
.cbx-c.on { border-color: var(--accent); background: var(--accent-soft); }
.cbx-top { display: flex; align-items: baseline; gap: 6px; } .cbx-top b { font-family: var(--font-mono); font-size: 26px; line-height: 1; color: var(--ink); }
.cbx-top span { font-size: 13.5px; font-weight: 700; color: var(--ink); }
.cbx-d { display: flex; gap: 4px; } .cbx-d i { width: 12px; height: 12px; border-radius: 3px; background: var(--line); }
.cbx-c.on .cbx-d i { background: var(--accent); }
.cbx-c em { font-style: normal; font-size: 12.5px; color: var(--muted); line-height: 1.45; }
.cbx-t { align-self: center; font-size: 12.5px; color: var(--muted); padding: 0 4px; } .cbx-t b { font-family: var(--font-mono); color: var(--ink); }
.ladder { display: flex; flex-direction: column; max-width: 640px; }
.ld-s { display: grid; grid-template-columns: 28px minmax(0, 1fr) auto; gap: 10px; align-items: start; padding: 10px 12px; border: 1px solid var(--line); border-radius: 10px; background: var(--surface); }
.ld-s.first { border-color: var(--accent); }
.ld-n { display: grid; place-items: center; width: 24px; height: 24px; border-radius: 50%; background: var(--bg); border: 1px solid var(--line); font-family: var(--font-mono); font-size: 12px; color: var(--muted); }
.ld-s.first .ld-n { background: var(--accent); border-color: var(--accent); color: #fff; }
.ld-b { display: flex; flex-direction: column; gap: 2px; } .ld-b b { font-size: 14.5px; color: var(--ink); } .ld-b span { font-size: 12.5px; color: var(--muted); line-height: 1.5; }
.ld-tag { font-style: normal; font-size: 11.5px; padding: 1px 7px; border-radius: 4px; border: 1px solid var(--line); color: var(--muted); }
.ld-s.first .ld-tag { color: var(--accent); border-color: var(--accent); }
.ld-c { position: relative; padding: 6px 0 6px 25px; margin-left: 12px; border-left: 2px dashed var(--line); }
.ld-c span { display: inline-block; font-size: 12.5px; font-weight: 700; color: var(--warn); background: var(--warn-soft); border-radius: 999px; padding: 1px 10px; }
.ld-c span::before { content: '↓ '; }

.pool { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.pl-card { background: var(--surface); border: 1px solid var(--line); border-top: 4px solid var(--accent); border-radius: 10px; padding: 12px 14px; display: flex; flex-direction: column; gap: 9px; }
.pl-top { display: flex; justify-content: space-between; align-items: flex-end; gap: 8px; }
.pl-name { font-size: 15px; font-weight: 700; color: var(--ink); }
.pl-w { margin-left: 8px; font-family: var(--font-mono); font-size: 13px; font-weight: 700; color: var(--accent); background: var(--bg); border: 1px solid var(--line); border-radius: 5px; padding: 1px 6px; }
.pl-n { font-size: 13px; color: var(--muted); white-space: nowrap; } .pl-n b { font-size: 30px; line-height: 1; font-weight: 800; color: var(--ink); font-family: var(--font-mono); margin: 0 3px; }
.pl-m { display: flex; flex-wrap: wrap; align-items: baseline; gap: 6px; padding: 6px 9px; border-radius: 7px; background: var(--bg); border: 1px solid var(--line); }
.pl-mk { font-size: 12px; color: var(--muted); } .pl-mv { font-size: 14px; font-weight: 700; color: var(--ink); } .pl-mx { font-size: 12px; color: var(--muted); margin-left: auto; }
.pl-cs, .pl-ss { display: flex; flex-wrap: wrap; gap: 5px; }
.pl-c { font-size: 13px; padding: 2px 8px; border-radius: 5px; background: var(--bg); border: 1px solid var(--line); color: var(--ink); }
.pl-g { border-left: 3px solid var(--line); padding-left: 9px; } .pl-g.pl-open { border-left-style: dashed; }
.pl-gh { font-size: 13px; color: var(--ink); margin-bottom: 4px; } .pl-gh b { font-family: var(--font-mono); font-size: 15px; }
.pl-note { margin-left: 6px; font-size: 12px; color: var(--muted); }
.pl-s { font-size: 12px; font-family: var(--font-mono); padding: 1px 6px; border-radius: 4px; border: 1px solid var(--line); color: var(--muted); }
.pl-src { margin-top: auto; padding-top: 7px; border-top: 1px dashed var(--line); font-size: 12px; color: var(--muted); line-height: 1.45; }
@media (max-width: 760px) { .pool { grid-template-columns: minmax(0, 1fr); } }

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
.sb-l li { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 8px; align-items: start; font-size: 14px; font-weight: 600; color: var(--ink); line-height: 1.45; margin: 0; padding: 8px 10px; background: var(--surface); border: 1px solid var(--line); border-radius: 8px; }
.sb-col { background: var(--bg) !important; }
.sb-col.t-bad .sb-n { background: var(--bad); color: #fff; } .sb-col.t-good .sb-n { background: var(--good); color: #fff; } .sb-col.t-mute .sb-n { background: var(--muted); color: #fff; }
.sb-l li::before { display: none; }
.sb-n { display: inline-grid; place-items: center; min-width: 20px; height: 20px; border-radius: 50%; background: var(--line); color: var(--ink); font-size: 11.5px; font-family: var(--font-mono); margin: 1px 6px 0 0; }
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
ol.route, ol.route.flow, ol.route.steps-n { list-style: none; padding: 0; margin: 0; display: grid !important; grid-template-columns: none !important; grid-auto-flow: column !important; grid-auto-columns: minmax(0, 1fr) !important; gap: 0 !important; counter-reset: none; }
ol.route li { position: relative; margin: 0; padding: 30px 8px 0 0; display: flex; flex-direction: column; gap: 2px; background: none; border: 0; }
ol.route li::before { content: ''; display: block; position: absolute; top: 10px; left: 22px; right: 0; height: 2px; background: var(--line); }
ol.route li:last-child::before { display: none; }
ol.route > li { padding: 30px 8px 0 0 !important; background: none !important; border: 0 !important; border-radius: 0 !important; color: inherit; }
ol.route > li::before { content: none !important; display: none !important; }
ol.route > li:not(:last-child) { background: linear-gradient(var(--line), var(--line)) no-repeat 22px 10px / calc(100% - 22px) 2px !important; }
ol.route > li.rt-done:not(:last-child) { background: linear-gradient(var(--good), var(--good)) no-repeat 22px 10px / calc(100% - 22px) 2px !important; }
ol.route > li::after, ol.route > li:not(:last-child)::after { content: none !important; }
ol.route .fl-t { display: flex; flex-direction: column; gap: 2px; font-weight: inherit; } ol.route .fl-d:empty { display: none; }
ol.route li.rt-done::before { background: var(--good); }
ol.route li .rt-s, ol.route li .rt-w, ol.route li .rt-st { display: block !important; } ol.route li > b { font-weight: inherit; }
.rt-dot { position: absolute; top: 0; left: 0; width: 22px; height: 22px; border-radius: 50%; border: 2px solid var(--line); background: var(--surface); display: grid; place-items: center; font-size: 12px; color: #fff; z-index: 1; }
ol.route li.rt-done .rt-dot { background: var(--good); border-color: var(--good); }
ol.route li.rt-now .rt-dot { border-color: var(--accent); box-shadow: 0 0 0 4px var(--accent-soft); background: var(--accent); }
ol.route li.rt-you .rt-dot { border: 2px dashed var(--accent); }
.rt-s { font-size: 14px; font-weight: 700; color: var(--ink); line-height: 1.35; }
.rt-w { font-size: 12px; color: var(--muted); line-height: 1.4; }
.rt-st { width: max-content; margin-top: 3px; font-size: 11.5px; font-weight: 700; padding: 0 7px; border-radius: 999px; color: var(--muted); background: var(--bg); border: 1px solid var(--line); }
ol.route li.rt-done .rt-st { color: var(--good); border-color: var(--good); background: var(--good-soft); }
ol.route li.rt-now .rt-st { color: #fff; background: var(--accent); border-color: var(--accent); }
ol.route li.rt-you .rt-st { color: var(--accent); border: 1px dashed var(--accent); background: var(--accent-soft); }
ol.route li.rt-todo .rt-s { color: var(--muted); }
@media (max-width: 760px) { ol.route, ol.route.flow, ol.route.steps-n { grid-auto-flow: row !important; } ol.route > li { padding: 0 0 12px 32px !important; } ol.route > li:not(:last-child), ol.route > li.rt-done:not(:last-child) { background-position: 10px 22px !important; background-size: 2px calc(100% - 22px) !important; } }
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
.risks { display: grid; border: 1px solid var(--line); border-radius: 10px; overflow: hidden; background: var(--surface); }
.risks > .rk { display: grid; grid-template-columns: 2.6em 11em minmax(0, 1fr) 14em; gap: 14px; align-items: center; padding: 11px 14px; border-top: 1px solid var(--line); border-left: 4px solid var(--line); }
.risks > .rk.rk-hd { border-top: 0; border-left-color: transparent; padding: 6px 14px; background: var(--bg); }
.risks > .rk.rk-hd > span { font-size: 11.5px; font-weight: 700; color: var(--muted); }
.risks > .rk.sev1 { border-left-color: var(--bad); background: var(--bad-soft); } .risks > .rk.sev2 { border-left-color: var(--warn); }
.rk-n { font-size: 24px; font-weight: 800; color: var(--muted); font-family: var(--font-mono); text-align: center; }
.rk.sev1 .rk-n { color: var(--bad); } .rk.sev2 .rk-n { color: var(--warn); }
.rk-why { font-size: 15px; color: var(--ink); line-height: 1.35; }
.rk-then { font-size: 13.5px; color: var(--ink); line-height: 1.5; }
.rk-w { display: flex; flex-wrap: wrap; gap: 4px; align-items: center; }
.rk-c { font-size: 12.5px; padding: 1px 7px; border-radius: 5px; background: var(--surface); border: 1px solid var(--line); }
@media (max-width: 760px) { .risks > .rk { grid-template-columns: 2.2em minmax(0, 1fr); } .risks > .rk.rk-hd { display: none; } .rk-then, .rk-w { grid-column: 2; } }
@media (max-width: 760px) { .pn-g, .pn-r, .risks > .rk { grid-template-columns: minmax(0, 1fr); } .pn-gk { border-right: 0; border-bottom: 1px solid var(--line); } }
@media (max-width: 760px) { .cp-r, .cr-r { grid-template-columns: minmax(0, 1fr); gap: 4px; } }
"""

"""Content-specific forms for frozen documents (no markers in the md).

Run after story_layer.pre (definition grids already built), before polish.
Each form is chosen by a table header signature or a definition term, takes all of its
words from the source, and falls back to the original element when the text does not parse.

  tables
    | 步 | 决定什么 | 规则 |                     → step rows: the question big; votes / states / if-then / result pill
    |  | 主规则：… | 挑战者：… |                   → versus: two role columns, rows tagged 相同 / 不同
    | 数字 | 取值 | 怎么来的 | 计不计 |             → constants grouped by 计 / 文献 / 约定, value big
    | 规则 | 取值 | 来历 |                       → rule rows: first clause bold, rest grey, sources as chips
  definitions (.sl-dr by term)
    把握 p                → three-step calc strip + where each slot starts
    低于哪条线不做        → gate checklist
    设计期年化的口径      → two numbers side by side
    A 股一项的对账口径    → +0.6 = 挑选 + 等权倾斜
    "X = …；Y = …"        → two cells
  folded ordered lists (ol.flow inside a fold) → compact rows (story.py adds .flow later; we mark the fold)
"""
import re
from bs4 import BeautifulSoup, NavigableString

SENT = re.compile(r'。(?![^<]*>)')


def _frag(html):
    return BeautifulSoup(html, 'html.parser')


def _rows(t):
    head = [th.get_text(' ', strip=True) for th in t.select('thead th')]
    rows = [[td for td in tr.find_all('td')] for tr in t.select('tbody tr')]
    return head, rows


def _inner(td):
    return td.decode_contents().strip() if td is not None else ''


def _txt(x):
    return BeautifulSoup(x, 'html.parser').get_text('', strip=True) if isinstance(x, str) else x.get_text('', strip=True)


def _sentences(html):
    parts = [p.strip() for p in SENT.split(html)]
    return [p for p in parts if _txt(p)]


def _split_top(s, sep):
    out, buf, depth = [], '', 0
    for ch in s:
        depth += ch in '（(' and 1 or 0
        depth -= ch in '）)' and 1 or 0
        if ch == sep and depth == 0:
            out.append(buf.strip()); buf = ''
        else:
            buf += ch
    return [x for x in out + [buf.strip()] if x]


# ---------------------------------------------------------------- step rows
def steps(rows):
    out = ''
    for r in rows:
        k, q, rule = _inner(r[0]), _inner(r[1]), _inner(r[2])
        m = re.match(r'^(\S+)\s*(.*)$', _txt(k))
        num, name = (m.group(1), m.group(2)) if m else ('', _txt(k))
        main, votes, pill, states, conds, notes = [], [], [], [], [], []
        for s in _sentences(rule):
            t = _txt(s)
            vm = re.match(r'^([一二三四五两\d]+)票[：:](.+)$', s)
            st = re.match(r'^([^：:<>，。]{1,5})[：:](.+)$', s)
            if vm and '；' in vm.group(2):
                votes = _split_top(vm.group(2), '；')
            elif re.fullmatch(r'\s*<strong>.*</strong>\s*', s):
                pill.append(s)
            elif st and st.group(1) in ('不紧张', '确认紧张', '紧张', '平时'):
                states.append((st.group(1), st.group(2)))
            elif '时，' in t and not main and False:
                conds.append(s)
            elif '时，' in t:
                a, b = s.split('时，', 1)
                conds.append((a + '时', b))
            elif not (main or votes or states or pill or conds):
                main.append(s)
            else:
                notes.append(s)
        body = ''
        if main:
            body += f'<div class="f-st-main">{main[0]}</div>'
        if votes:
            tiles = ''.join(f'<div class="f-vt"><span class="f-vt-n">第 {i} 票</span><span>{v}</span></div>'
                            for i, v in enumerate(votes, 1))
            body += f'<div class="f-votes">{tiles}</div>'
        for p in pill:
            body += f'<div class="f-pill">{p}</div>'
        if states:
            tiles = ''.join(f'<div class="f-state {"warn" if "紧张" in l and l != "不紧张" else "good"}">'
                            f'<span class="f-state-k">{l}</span><span>{v}</span></div>' for l, v in states)
            body += f'<div class="f-states">{tiles}</div>'
        for a, b in conds:
            body += f'<div class="f-if"><span class="f-if-k">{a}</span><span class="f-if-v">{b}</span></div>'
        for n in notes:
            body += f'<div class="f-note">{n}</div>'
        out += (f'<div class="f-st"><div class="f-st-k"><span class="f-st-n">{num}</span><span class="f-st-s">{name}</span>'
                f'<b class="f-st-q">{q}</b></div><div class="f-st-b">{body}</div></div>')
    return f'<div class="f-steps">{out}</div>'


# ---------------------------------------------------------------- versus
SAME = re.compile(r'^(相同|—|-|同上|第 ① 步原样)')


def versus(head, rows):
    left, right = head[1], head[2]
    def role(h):
        m = re.match(r'^([^：:]+)[：:]\s*(.+)$', h)
        return (m.group(1), m.group(2)) if m else ('', h)
    (lr, ln), (rr, rn) = role(left), role(right)
    grid = (f'<div class="f-vs-h"></div><div class="f-vs-h main"><span>{lr}</span><b>{ln}</b></div>'
            f'<div class="f-vs-h chal"><span>{rr}</span><b>{rn}</b></div>')
    for r in rows:
        lab, a, b = _txt(r[0]), _inner(r[1]), _inner(r[2])
        same = bool(SAME.match(_txt(a))) and (_txt(b).startswith('相同') or _txt(a) != '—')
        if lab == '地位':
            kind, tag = 'verdict', '地位'
        elif _txt(b).startswith('相同'):
            kind, tag = 'same', '相同'
        else:
            kind, tag = 'diff', '不同'
        if lab == 'ID':
            fm = re.match(r'^(ID\s*=\s*[^，；]+?)([，；].*)$', b)
            if fm:
                b = f'<code class="f-fm">{fm.group(1)}</code><span class="f-vs-sub">{fm.group(2).lstrip("，；")}</span>'
        grid += (f'<div class="f-vs-l {kind}"><span>{lab}</span><em>{tag}</em></div>'
                 f'<div class="f-vs-c main {kind}{" muted" if SAME.match(_txt(a)) else ""}">{a}</div>'
                 f'<div class="f-vs-c chal {kind}">{b}</div>')
    return f'<div class="f-vs">{grid}</div>'


# ---------------------------------------------------------------- constants
GROUPS = [('计', '看过数据后定 · 计入复杂度预算', 'acc'), ('文献', '文献默认值', 'mid'), ('约定', '跑前写死的约定', 'low')]


def constants(rows):
    buckets = {g: [] for g, _, _ in GROUPS}
    for r in rows:
        c = _txt(r[3])
        key = next((g for g, _, _ in GROUPS if c.startswith(g)), '约定')
        buckets[key].append(r)
    out = ''
    for g, label, tone in GROUPS:
        rs = buckets[g]
        if not rs:
            continue
        body = ''
        for r in rs:
            tag = _txt(r[3])
            extra = '' if tag in (g, ) or re.fullmatch(r'计 \d+', tag) else tag.split('，', 1)[-1] if '，' in tag else ''
            num = re.fullmatch(r'计 (\d+)', tag)
            badge = f'<span class="f-k-i">{num.group(1) if num else ""}</span>'
            body += (f'<div class="f-k-r">{badge}<span class="f-k-name">{_inner(r[0])}</span>'
                     f'<span class="f-k-v">{_inner(r[1])}</span><span class="f-k-o">{_inner(r[2])}'
                     + (f'<em class="f-k-x">{extra}</em>' if extra else '') + '</span></div>')
        out += (f'<div class="f-k-g {tone}"><div class="f-k-h"><b>{len(rs)}</b> {label}</div>{body}</div>')
    return f'<div class="f-k">{out}</div>'


# ---------------------------------------------------------------- rule rows
def rules(rows):
    out = ''
    for r in rows:
        name, val, src = _inner(r[0]), _inner(r[1]), _inner(r[2])
        m = re.search(r'[；](?![^<]*>)', val)
        lead, rest = (val[:m.start()], val[m.end():]) if m else (val, '')
        srcs, cost = [], ''
        parts = re.split(r'。(?![^<]*>)', src)
        for p in parts:
            p = p.strip()
            if not p:
                continue
            if p.startswith('代价'):
                cost = p
            else:
                srcs += [x.strip() for x in re.split(r'[；](?![^<]*>)', p) if x.strip()]
        chips = ''.join(f'<span class="sl-src">{x}</span>' for x in srcs)
        out += (f'<div class="f-ru"><div class="f-ru-k">{name}</div><div class="f-ru-v"><div class="f-ru-lead">{lead}</div>'
                + (f'<div class="f-ru-rest">{rest}</div>' if rest else '')
                + (f'<div class="f-ru-cost">{cost}</div>' if cost else '')
                + f'</div><div class="f-ru-s">{chips}</div></div>')
    return f'<div class="f-rules">{out}</div>'


TABLES = [
    (lambda h: h == ['步', '决定什么', '规则'], lambda h, r: steps(r), 'steps'),
    (lambda h: len(h) == 3 and h[0] == '' and h[1].startswith('主规则') and h[2].startswith('挑战者'), versus, 'versus'),
    (lambda h: h == ['数字', '取值', '怎么来的', '计不计'], lambda h, r: constants(r), 'consts'),
    (lambda h: h == ['规则', '取值', '来历'], lambda h, r: rules(r), 'rules'),
]


# ---------------------------------------------------------------- definitions
def _def_text(dr):
    dd = dr.find(class_='sl-dd')
    return dd, ''.join(x.decode_contents() for x in dd.find_all(class_=['sl-dh', 'sl-dx'])).strip()


def d_confidence(html):
    t = _txt(html)
    m = re.search(r'p\s*=\s*Φ\(t\)，t\s*=\s*(以往每个紧张月“[^”]+”)的平均\s*÷\s*标准差\s*×\s*√月数，(只用[^；]+)；(少于[^。]+)。'
                  r'(美股名额以.+?为起点)；(A 股名额从 0\.5 起)。(Φ 是[^。]+)。', t)
    if not m:
        return None
    rec, known, short, us, a, phi = m.groups()
    steps_ = [('①', '记下', rec, known), ('②', '算 t', 't = 平均 ÷ 标准差 × √月数', ''), ('③', '换成 p', 'p = Φ(t)', phi)]
    steps_[2] = ('③', '换成 p', 'p = Φ(t)', f'{phi}；{short}')
    cells = '<span class="f-calc-a">→</span>'.join(
        f'<div class="f-calc-s"><span class="f-calc-n">{n} {v}</span><span class="f-calc-b'
        f'{" fm" if "=" in b else ""}">{b}</span>' + (f'<em>{s}</em>' if s else '') + '</div>'
        for n, v, b, s in steps_)
    start = (f'<div class="f-calc-st"><span class="f-calc-k">从哪里起学</span>'
             f'<div class="f-calc-m"><b>美股</b><span>{us.replace("美股名额", "")}</span></div>'
             f'<div class="f-calc-m"><b>A 股</b><span>{a.replace("A 股名额", "")}</span></div></div>')
    return f'<div class="f-calc">{cells}</div>{start}'


def d_gate(html):
    t = _txt(html)
    m = re.search(r'^(预测合计的中间值低于 0)，或 (D39 两条线)（(合成行情中间情况最低剩 60 万)、(合成慢牛每年落后不超过 4 点)）(任一不满足，就不起草)。'
                  r'当前合计 (\+?[\d.]+)，(两条线都满足)', t)
    if not m:
        return None
    first, d39, l1, l2, rule, now, ok = m.groups()
    rows = [('预测合计的中间值不低于 0', f'当前 {now}'), (f'{d39}：{l1}', '满足'), (f'{d39}：{l2}', '满足')]
    items = ''.join(f'<div class="f-gt"><span class="f-gt-ok">✓</span><span>{a}</span><b>{b}</b></div>' for a, b in rows)
    return (f'<div class="f-gate-h">{first}，或 {d39}任一不满足，就不起草</div><div class="f-gates">{items}</div>'
            f'<div class="f-note">当前合计 {now}，{ok}。</div>')


def d_two(html):
    t = _txt(html)
    m = re.search(r'^（([^）]+)）(预测表各项不直接取设计期年化)。按(本预注册的口径)（([^）]+)），设计期 v6 净每年 ([\d.]+%)；'
                  r'(只用当年已发布的指数)是 ([\d.]+%)(?:（([^）]+)）)?；(差别在[^。]+)。(预测表冻结不改)。', t)
    if not m:
        return None
    ver, lead, k1, k1x, v1, k2, v2, k2x, diff, frozen = m.groups()
    return (f'<div class="f-two-h">{lead}（{ver}）</div><div class="f-two">'
            f'<div class="f-two-c on"><b>{v1}</b><span>{k1}</span><em>{k1x}</em></div>'
            f'<div class="f-two-c"><b>{v2}</b><span>{k2}</span>' + (f'<em>{k2x}</em>' if k2x else '') + '</div></div>'
            f'<div class="f-note">{diff}；{frozen}。</div>')


def d_split(html):
    t = _txt(html)
    m = re.search(r'^预测值 (\+[\d.]+) 不变；(事后按两块分别核对)——挑选（([^，]+)，约 (\+[\d.]+)，范围 ([^）]+)）、'
                  r'等权倾斜（([^，]+)，约 (\+[\d.]+)，范围 ([^，]+)，([^）]+)）。', t)
    if not m:
        return None
    tot, how, d1, v1, r1, d2, v2, r2, why = m.groups()
    return (f'<div class="f-eq"><div class="f-eq-t"><b>{tot}</b><span>预测值不变</span></div><span class="f-eq-op">=</span>'
            f'<div class="f-eq-p"><span>挑选</span><b>约 {v1}</b><em>范围 {r1}</em><small>{d1}</small></div><span class="f-eq-op">+</span>'
            f'<div class="f-eq-p"><span>等权倾斜</span><b>约 {v2}</b><em>范围 {r2}</em><small>{d2}；{why}</small></div></div>'
            f'<div class="f-note">{how}。</div>')


def d_pair(html):
    m = re.match(r'^(.{1,4}?)\s*=\s*(.+?)；\s*(.{1,4}?)\s*=\s*(.+?)。?$', html.strip())
    if not m or '<div' in html:
        return None
    return ''.join(f'<div class="f-pair-c"><b>{k}</b><span>{v}</span></div>' for k, v in ((m.group(1), m.group(2)), (m.group(3), m.group(4))))


DEFS = {'把握 p': d_confidence, '低于哪条线不做': d_gate, '设计期年化的口径': d_two, 'A 股一项的对账口径': d_split}


def apply(html):
    soup = BeautifulSoup(html, 'html.parser')
    for t in list(soup.find_all('table')):
        head, rows = _rows(t)
        for test, fn, kind in TABLES:
            if test(head) and rows:
                try:
                    node = _frag(f'<div class="comp f-{kind}-wrap" data-lint="ref">{fn(head, rows)}</div>')
                except Exception:
                    break
                tail = t.find_next_sibling()
                t.replace_with(node)
                break
    for dr in soup.select('.sl-dr'):
        term = dr.find(class_='sl-dt').get_text('', strip=True)
        dd, body = _def_text(dr)
        fn = DEFS.get(term)
        new = fn(body) if fn else None
        if new is None and fn is None:
            dh = dd.find(class_='sl-dh')
            if dd.find(class_='sl-dx') is None:
                pair = d_pair(dh.decode_contents())
                if pair:
                    new = f'<div class="f-pair">{pair}</div>'
        if new:
            dd.clear()
            dd.append(_frag(new))
            dr['class'] = dr.get('class', []) + ['f-def']
    # a numbered list inside a fold is reference text: compact rows, not big flow cards
    for fb in soup.select('details'):
        for ol in fb.find_all('ol'):
            ol['class'] = ol.get('class', []) + ['f-compact']
    return str(soup)


CSS = r"""
/* ===== forms.py: content-specific forms ===== */
.f-steps { display: grid; gap: 10px; }
.f-st { display: grid; grid-template-columns: 9.5em minmax(0, 1fr); gap: 14px; background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 12px 14px; }
.f-st-k { display: flex; flex-direction: column; gap: 2px; }
.f-st-k { flex-direction: row; flex-wrap: wrap; align-items: baseline; column-gap: 4px; }
.f-st-n, .f-st-s { font-size: 13px; color: var(--muted); } .f-st-q { flex-basis: 100%; }
.f-st-k { align-content: flex-start; }
.f-two-c .num, .f-eq-t .num, .f-eq-p .num, .pl-n .num, .cbx-top .num, .f-k-v .num, .f-k-h .num { background: none !important; padding: 0 !important; box-shadow: none !important; }
.f-st-q { font-size: 18px; line-height: 1.3; color: var(--ink); }
.f-st-k::before { content: none; }
.f-st-b { display: flex; flex-direction: column; gap: 8px; font-size: 14px; line-height: 1.6; color: var(--ink); }
.f-st-main { font-size: 14px; }
.f-votes { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
.f-vt { display: flex; flex-direction: column; gap: 3px; padding: 8px 10px; border: 1px solid var(--line); border-radius: 8px; background: var(--bg); font-size: 13px; line-height: 1.5; }
.f-vt-n { font-size: 11.5px; font-weight: 700; color: var(--accent); letter-spacing: .02em; }
.f-pill { align-self: flex-start; padding: 4px 12px; border-radius: 999px; background: var(--accent); color: #fff; font-size: 14px; }
.f-pill strong { color: #fff; }
.f-states { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
.f-state { display: flex; flex-direction: column; gap: 3px; padding: 8px 10px; border-radius: 8px; border: 1px solid var(--line); border-top: 3px solid var(--good); background: var(--bg); font-size: 13.5px; }
.f-state.warn { border-top-color: var(--warn); }
.f-state-k { font-size: 12px; font-weight: 700; color: var(--muted); }
.f-if { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 8px; align-items: baseline; padding: 6px 10px; border-left: 3px solid var(--warn); background: var(--bg); border-radius: 0 6px 6px 0; font-size: 13.5px; }
.f-if-k { font-weight: 700; color: var(--ink); } .f-if-k::before { content: '例外 · '; color: var(--warn); font-weight: 700; }
.f-note { font-size: 12.5px; color: var(--muted); line-height: 1.55; }

.f-vs { display: grid; grid-template-columns: 7em minmax(0, 1fr) minmax(0, 1.5fr); border: 1px solid var(--line); border-radius: 10px; overflow: hidden; background: var(--surface); }
.f-vs > div { padding: 9px 12px; border-top: 1px solid var(--line); font-size: 13.5px; line-height: 1.55; }
.f-vs-h { border-top: 0 !important; display: flex; flex-direction: column; gap: 1px; }
.f-vs-h span { font-size: 11.5px; color: var(--muted); } .f-vs-h b { font-size: 16px; color: var(--ink); }
.f-vs-h.main { border-top: 3px solid var(--ink) !important; } .f-vs-h.chal { border-top: 3px solid var(--accent) !important; }
.f-vs-l { display: flex; flex-direction: column; gap: 2px; font-weight: 700; color: var(--ink); }
.f-vs-l em { font-style: normal; font-weight: 600; font-size: 11px; width: max-content; padding: 0 6px; border-radius: 4px; background: var(--bg); color: var(--muted); border: 1px solid var(--line); }
.f-vs-l.diff em { color: var(--accent); border-color: var(--accent); }
.f-vs-c.muted { color: var(--muted); }
.f-vs-c.chal.diff { background: var(--accent-soft); }
.f-vs-c.verdict, .f-vs-l.verdict { font-weight: 700; }
.f-vs-sub { display: block; color: var(--muted); font-size: 12.5px; margin-top: 3px; }
code.f-fm { display: inline-block; font-size: 13px; padding: 2px 6px; }

.f-k { display: grid; gap: 10px; }
.f-k-g { border: 1px solid var(--line); border-radius: 10px; background: var(--surface); overflow: hidden; }
.f-k-h { padding: 7px 12px; font-size: 13px; color: var(--muted); background: var(--bg); border-bottom: 1px solid var(--line); }
.f-k-h b { font-family: var(--font-mono); font-size: 16px; color: var(--ink); margin-right: 2px; }
.f-k-g.acc { border-color: var(--accent); } .f-k-g.acc .f-k-h { background: var(--accent); color: #fff; } .f-k-g.acc .f-k-h b { color: #fff; }
.f-k-r { display: grid; grid-template-columns: 1.6em 8.5em 9em minmax(0, 1fr); gap: 10px; align-items: baseline; padding: 8px 12px; border-top: 1px solid var(--line); font-size: 13.5px; }
.f-k-r:first-of-type { border-top: 0; }
.f-k-i { font-family: var(--font-mono); font-size: 12px; color: var(--accent); font-weight: 700; }
.f-k-name { font-weight: 700; color: var(--ink); }
.f-k-v { font-family: var(--font-mono); font-size: 15px; font-weight: 700; color: var(--ink); }
.f-k-o { color: var(--muted); font-size: 13px; line-height: 1.55; }
.f-k-x { font-style: normal; margin-left: 6px; font-size: 11.5px; padding: 0 6px; border-radius: 4px; border: 1px solid var(--line); color: var(--muted); white-space: nowrap; }

.f-rules { border: 1px solid var(--line); border-radius: 10px; background: var(--surface); overflow: hidden; }
.f-ru { display: grid; grid-template-columns: 8.5em minmax(0, 1fr) 11em; gap: 14px; padding: 10px 14px; border-top: 1px solid var(--line); align-items: baseline; }
.f-ru:first-child { border-top: 0; }
.f-ru-k { font-weight: 700; color: var(--ink); font-size: 14px; }
.f-ru-lead { font-size: 14px; color: var(--ink); line-height: 1.55; }
.f-ru-rest { font-size: 12.5px; color: var(--muted); line-height: 1.55; margin-top: 2px; }
.f-ru-cost { font-size: 12.5px; color: var(--warn); line-height: 1.55; margin-top: 4px; }
.f-ru-s { display: flex; flex-wrap: wrap; gap: 4px; justify-content: flex-end; }

.sl-dr.f-def { align-items: start; }
.f-calc { display: grid; grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr) auto minmax(0, 1fr); gap: 6px; align-items: stretch; }
.f-calc-s { display: flex; flex-direction: column; gap: 4px; padding: 9px 12px; background: var(--bg); border: 1px solid var(--line); border-radius: 8px; font-size: 13px; line-height: 1.5; color: var(--ink); }
.f-calc-a { align-self: center; color: var(--accent); font-weight: 700; }
.f-calc-n { font-size: 12px; color: var(--accent); font-weight: 700; }
.f-calc-b.fm { font-family: var(--font-mono); font-size: 15px; font-weight: 700; color: var(--ink); }
.f-calc-s em { font-style: normal; font-size: 12px; color: var(--muted); }
.f-calc-st { display: grid; grid-template-columns: auto minmax(0, 1fr) minmax(0, 1fr); gap: 8px; align-items: stretch; margin-top: 8px; font-size: 13px; color: var(--ink); }
.f-calc-k { align-self: center; font-size: 12px; color: var(--muted); }
.f-calc-m { display: flex; gap: 8px; align-items: baseline; padding: 6px 10px; border-radius: 8px; border: 1px dashed var(--line); }
.f-calc-m b { white-space: nowrap; }
.f-gate-h { font-size: 14px; color: var(--ink); margin-bottom: 6px; }
.f-gates { display: grid; gap: 4px; }
.f-gt { display: grid; grid-template-columns: 1.4em minmax(0, 1fr) auto; gap: 8px; align-items: baseline; padding: 5px 10px; border-radius: 6px; background: var(--good-soft); font-size: 13.5px; }
.f-gt-ok { color: var(--good); font-weight: 800; } .f-gt b { color: var(--good); font-family: var(--font-mono); }
.f-two-h { font-size: 14px; color: var(--ink); margin-bottom: 6px; }
.f-two { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin-bottom: 6px; }
.f-two-c { display: flex; flex-direction: column; gap: 2px; padding: 8px 12px; border: 1px solid var(--line); border-radius: 8px; background: var(--bg); }
.f-two-c b { font-family: var(--font-mono); font-size: 22px; line-height: 1.1; color: var(--muted); }
.f-two-c.on { border-color: var(--accent); } .f-two-c.on b { color: var(--ink); }
.f-two-c span { font-size: 13px; color: var(--ink); } .f-two-c em { font-style: normal; font-size: 12px; color: var(--muted); }
.f-eq { display: flex; align-items: stretch; gap: 8px; margin-bottom: 6px; flex-wrap: wrap; }
.f-eq-t, .f-eq-p { display: flex; flex-direction: column; gap: 2px; padding: 8px 12px; border: 1px solid var(--line); border-radius: 8px; background: var(--bg); }
.f-eq-t { border-color: var(--accent); } .f-eq-t b { font-family: var(--font-mono); font-size: 24px; line-height: 1.1; color: var(--ink); }
.f-eq-t span, .f-eq-p > span { font-size: 12px; color: var(--muted); }
.f-eq-p { flex: 1 1 180px; } .f-eq-p b { font-family: var(--font-mono); font-size: 17px; color: var(--ink); }
.f-eq-p em { font-style: normal; font-size: 12px; color: var(--muted); } .f-eq-p small { font-size: 12px; color: var(--muted); line-height: 1.45; }
.f-eq-op { align-self: center; font-size: 20px; font-weight: 700; color: var(--muted); }
.f-pair { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
.f-pair-c { display: flex; flex-direction: column; gap: 2px; padding: 6px 10px; border: 1px solid var(--line); border-radius: 8px; background: var(--bg); font-size: 13.5px; }
.f-pair-c b { font-size: 12px; color: var(--muted); }

ol.flow.f-compact { display: grid !important; grid-template-columns: minmax(0, 1fr) !important; gap: 0 !important; border: 1px solid var(--line); border-radius: 10px; overflow: hidden; background: var(--surface); }
ol.flow.f-compact > li { border: 0 !important; border-top: 1px solid var(--line) !important; border-radius: 0 !important; padding: 9px 14px 9px 46px !important; position: relative; }
ol.flow.f-compact > li:first-child { border-top: 0 !important; }
ol.flow.f-compact > li::before, ol.flow.f-compact .fl-n { position: absolute !important; left: 12px; top: 10px; margin: 0 !important; width: 22px !important; height: 22px !important; font-size: 12px !important; }
ol.flow.f-compact > li::after { content: none !important; }
ol.flow.f-compact > li { display: grid !important; grid-template-columns: 6em 11em minmax(0, 1fr); gap: 12px; align-items: baseline; }
ol.flow.f-compact .fl-t { font-size: 12.5px; color: var(--muted); font-weight: 600; border: 0 !important; padding: 0 !important; margin: 0 !important; }
ol.flow.f-compact .fl-k { font-size: 14px !important; font-weight: 700; color: var(--ink) !important; border: 0 !important; padding: 0 !important; margin: 0 !important; }
ol.flow.f-compact .fl-d { font-size: 13px; color: var(--muted); border: 0 !important; padding: 0 !important; margin: 0 !important; }
ol.flow.f-compact .fl-d strong { color: var(--muted); font-weight: 600; }

@media (max-width: 760px) {
  ol.flow.f-compact > li { grid-template-columns: minmax(0, 1fr) !important; gap: 2px; }
  .f-st, .f-ru, .f-k-r { grid-template-columns: minmax(0, 1fr); gap: 4px; }
  .f-votes, .f-states, .f-calc, .f-two, .f-pair { grid-template-columns: minmax(0, 1fr); }
  .f-vs { grid-template-columns: minmax(0, 1fr); } .f-vs-h:first-child { display: none; }
  .f-calc, .f-calc-st { grid-template-columns: minmax(0, 1fr); } .f-calc-a { transform: rotate(90deg); justify-self: center; } .f-ru-s { justify-content: flex-start; }
}
"""

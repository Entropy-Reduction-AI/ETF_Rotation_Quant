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


# ================================================================ round 2 (comments 06:31–06:38)
CN = {'两成': 20, '三成': 30, '五成': 50, '六成': 60, '八成': 80, '八成五': 85}
CODES = [  # decision codes → what they are, said plainly (code kept small)
    (r'D39-1', '你 11-17 定的回撤底线'),
    (r'D39-2', '你 11-17 定的保费上限'),
    (r'D38 第 18 行', '预演第 18 行'),
    (r'（D40-14）', ''),
]


def _plain_src(html):
    t = html
    for code, words in CODES:
        if code.startswith('（'):
            t = t.replace(code, '<span class="f-code">D40-14</span>')
        else:
            t = re.sub(re.escape(code) + r'(?![\d-])', f'{words}<span class="f-code">{code}</span>', t)
    return t


def qa(rows):
    out = ''
    for r in rows:
        q = _txt(r[0])
        m = re.match(r'^(\d+)\.\s*(.+)$', q)
        n, q = (m.group(1), m.group(2)) if m else ('', q)
        sents = _sentences(_inner(r[1]))
        head, rest = (sents[0], sents[1:]) if sents else ('', [])
        tail = ''
        for x in rest:
            for part in _split_top(x, '；'):
                lab = re.match(r'^(已写入|预演里)[：:](.+)$', part)
                if lab:
                    tail += f'<div class="f-qa-k {"done" if lab.group(1) == "已写入" else ""}"><em>{lab.group(1)}</em><span>{lab.group(2)}</span></div>'
                else:
                    tail += f'<div class="f-qa-x">{part}</div>'
        out += (f'<div class="f-qa"><div class="f-qa-q"><span>{n}</span><b>{q}</b></div>'
                f'<div class="f-qa-a">{head}</div>{tail}</div>')
    return f'<div class="f-qas">{out}</div>'


def _tone(name):
    if re.search(r'股灾|熊市|急跌', name):
        return 'bad'
    if re.search(r'大牛市|V 型', name):
        return 'warn'
    return 'good'


def portrait(rows):
    out = ''
    for r in rows:
        name, act, ex = _txt(r[0]), _inner(r[1]), _inner(r[2])
        m = re.match(r'^([^：<]{2,12})[：:](.+)$', ex, re.S)
        when, what = (m.group(1), m.group(2)) if m else (ex if len(_txt(ex)) <= 16 else '', '' if len(_txt(ex)) <= 16 else ex)
        out += (f'<div class="f-pt t-{_tone(name)}"><span class="f-pt-k">{name}</span><div class="f-pt-a">{act}</div>'
                f'<div class="f-pt-e"><em>{when}</em><span>{what}</span></div></div>')
    return f'<div class="f-pts">{out}</div>'


def prior_bars(p):
    """The ex-ante odds paragraph → one bar per criterion, plus all four and the challenger."""
    t = _txt(str(p))
    items = []
    for m in re.finditer(r'第 ([①②③④]) 条([^；。]*?)(?:大概率过)?（?约([一二三四五六七八九两]成五?)）?(?=[；。])', t):
        items.append((m.group(1), m.group(2).strip(), m.group(3)))
    allm = re.search(r'(合起来全部通过的机会)约([一二三四五六七八九两]成五?)', t)
    ch = re.search(r'(连续性版换上的机会)约([一二三四五六七八九两]成五?)', t)
    if len(items) != 4 or not allm:
        return None
    rows = ''.join(f'<div class="f-pb"><span class="f-pb-k">{c} {lab}</span><span class="f-pb-b"><i style="width:{CN.get(v, 0)}%"></i></span><b>约{v}</b></div>'
                   for c, lab, v in items)
    rows += f'<div class="f-pb all"><span class="f-pb-k">{allm.group(1)}</span><span class="f-pb-b"><i style="width:{CN.get(allm.group(2), 0)}%"></i></span><b>约{allm.group(2)}</b></div>'
    if ch:
        rows += f'<div class="f-pb ch"><span class="f-pb-k">{ch.group(1)}</span><span class="f-pb-b"><i style="width:{CN.get(ch.group(2), 0)}%"></i></span><b>约{ch.group(2)}</b></div>'
    lead = p.find('strong')
    title = lead.get_text('', strip=True) if lead else '事前预判'
    note = re.search(r'（([^）]+)）', t)
    end = re.search(r'(这是事先的判断[^。]*。)', t)
    return (f'<div class="f-pbs"><div class="f-pbs-h"><b>{title}</b>{f"<span>{note.group(1)}</span>" if note else ""}</div>{rows}'
            f'{f"<div class=f-note>{end.group(1)}</div>" if end else ""}</div>')


def redteam(rows):
    out = '<div class="rk rk-hd"><span></span><span>原因</span><span>会怎样</span><span>在哪里盯</span></div>'
    for i, r in enumerate(rows):
        watch = ''.join(f'<span class="rk-c">{x.strip()}</span>' for x in re.split(r'[；;](?![^<]*>)', _inner(r[3])) if _txt(x))
        sev = 'sev1' if i == 0 else ('sev2' if i == 1 else 'sev3')
        out += (f'<div class="rk {sev}"><span class="rk-n">{_txt(r[0])}</span><b class="rk-why">{_txt(r[1])}</b>'
                f'<span class="rk-then">{_inner(r[2])}</span><div class="rk-w">{watch}</div></div>')
    return f'<div class="risks f-full">{out}</div>'


SEEN_TONE = [(r'同仓位基准', 'warn'), (r'不再加新变体|规则不改', 'acc'), (r'不称样本外', 'warn'), (r'.', 'mute')]


def seen(rows):
    out = ''
    for r in rows:
        n, what, eff, con = _txt(r[0]), _inner(r[1]), _inner(r[2]), _txt(r[3])
        f = _frag(what)
        lead = f.find('strong')
        head = lead.get_text('', strip=True) if lead else ''
        if lead:
            lead.extract()
        detail = re.sub(r'^[：:]\s*', '', f.decode_contents().strip())
        tone = next(t for p, t in SEEN_TONE if re.search(p, con))
        out += (f'<div class="f-sn t-{tone}"><div class="f-sn-l"><span class="f-sn-n">{n}</span><span class="f-sn-c">{con}</span></div>'
                f'<div class="f-sn-b"><b class="f-sn-h">{head}</b><div class="f-sn-e"><em>影响</em><span>{eff}</span></div>'
                + (f'<details class="f-more"><summary>看过的具体内容</summary><div>{detail}</div></details>' if _txt(detail) else '')
                + '</div></div>')
    return f'<div class="f-sns">{out}</div>'


K2A_NOTE = ('K2A = A 股 50% + 美股 50%；只给 A 股那一半上保险：月末低于 10 个月均线就换国债，'
            '仓位 = 长期波动 ÷ 近 20 日波动（最多 1，每周看，变化不到 10 个点不动）；美股那一半一直持有。'
            '参数都是文献默认值（D39-3，你 11-17 定的保险层）')


def basis(rows):
    out = ''
    for r in rows:
        name, comp, use = _txt(r[0]), _inner(r[1]), _inner(r[2])
        segs = re.findall(r'(\d+)%\s*([^+，,（]+?)(?:\s*全收益)?(?=\s*\+|，|,|$)', _txt(comp))
        bar = ''
        if len(segs) >= 2:
            bar = '<div class="f-bs-bar">' + ''.join(f'<span style="flex:{w}"><b>{w}</b> {nm.strip()}</span>' for w, nm in segs) + '</div>'
        note = f'<div class="f-bs-k2a">{K2A_NOTE}</div>' if 'K2A' in name or 'K2A' in _txt(comp) else ''
        out += (f'<div class="f-bs"><div class="f-bs-h"><b>{name}</b><span class="f-bs-u">{use}</span></div>{bar}'
                f'<div class="f-bs-c">{comp}</div>{note}</div>')
    return f'<div class="f-bss">{out}</div>'


def controls(rows):
    inner, outer = [], []
    for r in rows:
        (outer if '只报告' in _txt(r[2]) else inner).append(r)
    def card(r):
        name, how, ans = _txt(r[0]), _inner(r[1]), _inner(r[2])
        ans = re.sub(r'[；;]\s*只报告\s*$', '', ans)
        long_ = len(_txt(how)) > 90
        if long_:
            t = _txt(how)
            m = re.search(r'[：:]', t)
            seg = t[m.end():] if m else t
            e = re.search(r'[；。]', seg)
            short = seg[:e.start()] if e else seg
            body = f'<div class="f-ct-e">{short}</div><details class="f-more"><summary>完整口径</summary><div>{how}</div></details>'
        else:
            body = f'<div class="f-ct-w">{how}</div>'
        return f'<div class="f-ct"><span class="f-ct-n">{name}</span><b class="f-ct-q">{ans}</b>{body}</div>'
    g1 = ''.join(card(r) for r in inner)
    g2 = ''.join(card(r) for r in outer)
    return (f'<div class="f-ctg"><div class="f-ctg-h">同结构对照：每个回答 v6 的一个问题</div><div class="f-cts">{g1}</div></div>'
            + (f'<div class="f-ctg out"><div class="f-ctg-h">外部对照：只报告，不判过不过</div><div class="f-cts">{g2}</div></div>' if g2 else ''))


def criteria(rows, odds):
    out = ''
    for r in rows:
        code, th, rule, src = _txt(r[0]), _inner(r[1]), _inner(r[2]), _inner(r[3])
        c = code[:1]
        p = odds.get(c, '')
        out += (f'<div class="f-cr"><div class="f-cr-h"><span class="f-cr-c">{code}</span><b>{th}</b>'
                + (f'<span class="f-cr-p">事先 {p}</span>' if p else '') + '</div>'
                f'<div class="f-cr-r">{rule}</div><div class="f-cr-s"><em>来历</em>{_plain_src(src)}</div></div>')
    return f'<div class="f-crs">{out}</div>'


def robust(rows):
    out = ''
    for r in rows:
        code, ch = _txt(r[0]), _inner(r[1])
        ch = re.sub(r'(\d+(?:\.\d+)?%|\d+ 个交易日|\d、\d、\d 个|前 \d|“\d 票全中”|\d+%)', r'<b>\1</b>', ch)
        out += f'<div class="f-rb"><span class="f-rb-c">{code}</span><span>{ch}</span></div>'
    return f'<div class="f-rbs">{out}</div>'


def pain_full(rows):
    out = '<div class="f-pn f-pn-hd"><span>情形</span><span>事先认下的代价</span><span>超出就要查</span></div>'
    for r in rows:
        name, what, cost, trip = _txt(r[0]), _inner(r[1]), _inner(r[2]), _inner(r[3])
        f = _frag(cost)
        st = f.find('strong')
        big = st.get_text('', strip=True) if st else ''
        if st:
            st.extract()
        rest = re.sub(r'^[：:]\s*', '', f.decode_contents().strip())
        out += (f'<div class="f-pn"><div><b>{name}</b><span class="f-pn-w">{what}</span></div>'
                f'<div><b class="f-pn-big">{big}</b><span class="f-pn-w">{rest}</span></div>'
                f'<div><span class="f-pn-trip">{trip}</span></div></div>')
    return f'<div class="f-pns">{out}</div>'


def navs(rows):
    vals = []
    for r in rows:
        v = [float(re.sub(r'[^\d.\-]', '', _txt(x).replace('−', '-')) or 0) for x in r[1:4]]
        vals.append(v)
    mx = max(v[2] for v in vals) or 1
    lo = min(v[2] for v in vals) - 3
    bm = next((v[2] for r, v in zip(rows, vals) if _txt(r[0]).startswith('BM-主')), None)
    out = '<div class="f-nv f-nv-hd"><span>序列</span><span>2006–10</span><span>2011–15</span><span>2006–15（条长 = 年化）</span></div>'
    for r, v in zip(rows, vals):
        name = _txt(r[0])
        kind = 'bm' if name.startswith('BM') else ('v6' if name.startswith('v6 净') else ('ref' if name.startswith('参照') else ''))
        diff = f'<em class="{"up" if v[2] >= bm else "dn"}">{v[2] - bm:+.2f}</em>' if bm is not None and kind != 'bm' else ''
        out += (f'<div class="f-nv {kind}"><span class="f-nv-k">{_inner(r[0])}</span><span>{_inner(r[1])}</span><span>{_inner(r[2])}</span>'
                f'<span class="f-nv-b"><i style="width:{(v[2] - lo) / (mx - lo) * 60:.0f}%"></i><b>{_inner(r[3])}</b>{diff}</span></div>')
    return f'<div class="f-nvs">{out}</div>'


TABLES += [
    (lambda h: h == ['问', '回答'], lambda h, r: qa(r), 'qa'),
    (lambda h: len(h) == 3 and h[0] == '行情' and h[1] == '规则会怎么动', lambda h, r: portrait(r), 'portrait'),
    (lambda h: h == ['#', '原因', '会怎样', '在哪里盯'], lambda h, r: redteam(r), 'redteam'),
    (lambda h: h == ['#', '看过什么', '对检验的影响', '结论'], lambda h, r: seen(r), 'seen'),
    (lambda h: h == ['基准', '构成', '用途'], lambda h, r: basis(r), 'basis'),
    (lambda h: h == ['对照', '写法', '回答什么'], lambda h, r: controls(r), 'controls'),
    (lambda h: h == ['编号', '改动'], lambda h, r: robust(r), 'robust'),
    (lambda h: h == ['情形', '会发生什么', '事先认下的代价', '超出就要查'], lambda h, r: pain_full(r), 'painfull'),
    (lambda h: h == ['序列', '2006–10', '2011–15', '2006–15'], lambda h, r: navs(r), 'navs'),
]


# definitions, appendix A / B
VERDICT = [(r'从首只基金 159516 上市日 2023-07-27 起参选', '从 2023-07-27 起参选'), (r'不参选', '不参选'),
           (r'中证红利只用 515180', '只用 515180'), (r'按 §2 退路', '按 §2 退路'), (r'不受影响', '不受影响'),
           (r'最大相对差 0\.04%', '两家对照，差 ≤ 0.04%'), (r'用中证的回填点位参选', '允许回填')]


def d_verdict(html):
    t = _txt(html)
    for pat, v in VERDICT:
        if re.search(pat, t):
            return f'<div class="f-vd"><span class="f-vd-p">{v}</span></div>'
    return None


def d_basis_mix(html):
    t = _txt(html)
    if not t.startswith('美股候选都是价格指数'):
        return None
    parts = [x for x in re.split(r'[；。]', t) if x.strip()]
    cells = ''
    for x in parts:
        m = re.match(r'^(.+?)(都是|用)(.+)$', x)
        if m:
            cells += f'<div class="f-pair-c"><b>{m.group(1).strip()}</b><span>{m.group(3).strip()}</span></div>'
    return f'<div class="f-pair four">{cells}</div>' if cells else None


def d_twocalib(html):
    t = _txt(html)
    m = re.search(r'(一级行业按发布日截断时)(?:（[^）]*）)?，(2006–10 年 A 股只有 2–7 个可选)，v6 净每年 ([\d.]+%)；(按本预注册的回填口径)是 ([\d.]+%)。(.+)$', t)
    if not m:
        return None
    k1, why, v1, k2, v2, rest = m.groups()
    return (f'<div class="f-two"><div class="f-two-c on"><b>{v2}</b><span>{k2}</span></div>'
            f'<div class="f-two-c"><b>{v1}</b><span>{k1}</span><em>{why}</em></div></div><div class="f-note">{rest}</div>')


def d_rebal(html):
    t = _txt(html)
    m = re.search(r'按月再平衡每年少 ([\d.]+) 点（2006–10 ([+−\-][\d.]+)，2011–15 ([+−\-][\d.]+)），(.+)$', t)
    if not m:
        return None
    a, b, c, rest = m.groups()
    cell = lambda k, v: f'<div class="f-two-c"><b>{v}</b><span>{k}</span></div>'
    return (f'<div class="f-gate-h">按月再平衡比每日固定 60/40，每年差几点</div>'
            f'<div class="f-three">{cell("2006–15 全段", "−" + a)}{cell("2006–10", b)}{cell("2011–15", c)}</div>'
            f'<div class="f-note">{rest}</div>')


def d_turnover(html):
    t = _txt(html)
    m = re.search(r'A 股名额每年 ([\d.]+) 倍，美股名额 ([\d.]+) 倍；按单边 0\.2% 每年约 ([\d.]+) 点成本，高于预演估的 ([\d.]+)–([\d.]+) 点，仍在疼痛表“每年成本超过 (\d+) 点”的警戒线以内', t)
    if not m:
        return None
    a, u, c, lo, hi, lim = m.groups()
    sc = lambda x: f'{float(x) / 2.5 * 100:.0f}%'
    return (f'<div class="f-gauge"><div class="f-gauge-t"><span>每年成本</span><b>约 {c} 点</b><em>A 股名额每年换手 {a} 倍，美股 {u} 倍，单边 0.2%</em></div>'
            f'<div class="f-gauge-b"><span class="band" style="left:{sc(lo)};width:calc({sc(hi)} - {sc(lo)})" title="预演估"></span>'
            f'<span class="pt" style="left:{sc(c)}"></span><span class="lim" style="left:{sc(lim)}"></span></div>'
            f'<div class="f-gauge-l"><span style="left:{sc(lo)}">预演估 {lo}–{hi}</span><span style="left:{sc(c)}">附表 B {c}</span>'
            f'<span class="lim" style="left:{sc(lim)}">警戒线 {lim}</span></div></div>')


DEFS.update({'口径': d_basis_mix, '两种口径差约 2 点': d_twocalib, '60/40 按月再平衡与每日固定的差异': d_rebal, '换手': d_turnover})
VERDICT_TERMS = ('一级行业的回填点位', 'DJIA、DWRTF 检验段补数', '半导体材料设备（931743）', '细分化工（H30187）',
                 '中证红利的实盘基金', '没有场内基金的候选', '长假间隔')
STAGES = {'检验': 'gate', '模拟盘': 'run', '影子': 'shadow', '暂停': 'stop'}


def rule_tiles(ol):
    """A folded list of short rules '**成交**：…**只用场内基金**。' → numbered tiles, the second bold as headline."""
    items = []
    for li in ol.find_all('li', recursive=False):
        ss = li.find_all('strong')
        if len(ss) < 2:
            return None
        lab = ss[0].get_text('', strip=True)
        if len(lab) > 4 or not li.decode_contents().strip().startswith('<strong>'):
            return None
        focus = ss[1].get_text('', strip=True)
        ss[0].extract()
        for x in li.find_all('strong'):
            x.unwrap()
        body = re.sub(r'^[：:]\s*', '', li.decode_contents().strip())
        items.append((lab, focus, body))
    if len(items) < 3:
        return None
    tiles = ''.join(f'<div class="f-rt"><div class="f-rt-k"><span>{i}</span>{l}</div><b class="f-rt-f">{f}</b><span class="f-rt-b">{b}</span></div>'
                    for i, (l, f, b) in enumerate(items, 1))
    return f'<div class="comp f-rts" data-lint="ref">{tiles}</div>'


def stage_cards(ol):
    items = []
    for li in ol.find_all('li', recursive=False):
        ss = li.find_all('strong')
        if not ss:
            return None
        lab = ss[0].get_text('', strip=True)
        if lab not in STAGES:
            return rule_tiles(ol)
        focus = ss[1].get_text('', strip=True) if len(ss) > 1 else ''
        ss[0].extract()
        body = re.sub(r'^[：:]\s*', '', li.decode_contents().strip())
        items.append((lab, focus, body))
    cards = ''.join(f'<div class="f-sg {STAGES[l]}"><span class="f-sg-k">{l}</span><b class="f-sg-f">{f}</b><span class="f-sg-b">{b}</span></div>'
                    for l, f, b in items)
    return f'<div class="comp f-sgs" data-lint="ref">{cards}</div>'


_apply1 = apply


def apply(html):
    html = _apply1(html)
    soup = BeautifulSoup(html, 'html.parser')
    # odds for the criteria cards come from the gate row of the same section
    for t in list(soup.find_all('table')):
        head, rows = _rows(t)
        if head == ['编号', '门槛', '判据', '来历'] and rows:
            sec = t.find_parent('section')
            odds = {}
            for g in sec.select('.gaterow .gt') if sec else []:
                c = g.find(class_='gt-c').get_text('', strip=True)[:1]
                p = g.find(class_='gt-p')
                if c and p and p.b:
                    odds[c] = p.b.get_text('', strip=True)
            t.replace_with(_frag(f'<div class="comp f-criteria-wrap" data-lint="ref">{criteria(rows, odds)}</div>'))
        elif head == ['基准', '构成', '用途'] and rows:
            pass
    # the ex-ante odds paragraph after the portrait
    for p in soup.find_all('p'):
        st = p.find('strong')
        if st and st.get_text('', strip=True) == '事前预判':
            new = prior_bars(p)
            if new:
                p.replace_with(_frag(new))
    # the two bullets above the basis cards → key/value tiles
    for w in soup.select('.f-basis-wrap'):
        ul = w.find_previous('ul')
        if ul is not None and ul.find_parent('details') is w.find_parent('details'):
            tiles = ''
            for li in ul.find_all('li', recursive=False):
                s_ = li.find('strong')
                if s_ is None:
                    tiles = ''
                    break
                k = s_.get_text('', strip=True)
                s_.extract()
                v = re.sub(r'^[：:]\s*', '', li.decode_contents().strip())
                fm = re.match(r'^([^（，。]+?)(（.+)$', v, re.S)
                tiles += (f'<div class="f-kv"><span class="f-kv-k">{k}</span><b>{fm.group(1) if fm else v}</b>'
                          + (f'<span class="f-kv-x">{fm.group(2)}</span>' if fm else '') + '</div>')
            if tiles:
                ul.replace_with(_frag(f'<div class="f-kvs">{tiles}</div>'))
    for dr in soup.select('.sl-dr'):
        term = dr.find(class_='sl-dt').get_text('', strip=True)
        dd, body = _def_text(dr)
        if term in VERDICT_TERMS:
            v = d_verdict(body)
            if v:
                dd.insert(0, _frag(v))
                dr['class'] = dr.get('class', []) + ['f-def', 'f-vrow']
    for ol in soup.select('details ol'):
        new = stage_cards(ol)
        if new:
            ol.replace_with(_frag(new))
    return str(soup)


CSS += r"""
.f-code { margin-left: 4px; font-size: 11px; color: var(--muted); font-family: var(--font-mono); opacity: .8; }
.f-more { margin-top: 4px; border: 0 !important; padding: 0 !important; background: none !important; box-shadow: none !important; } .f-more > summary { cursor: pointer; font-size: 12px; color: var(--accent); list-style: none; }
.f-more > summary::before { content: '▸ '; } .f-more[open] > summary::before { content: '▾ '; }
.f-more > div { margin-top: 4px; font-size: 12.5px; color: var(--muted); line-height: 1.55; }

.f-qas { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.f-qa { display: flex; flex-direction: column; gap: 6px; padding: 11px 13px; border: 1px solid var(--line); border-radius: 10px; background: var(--surface); }
.f-qa-q { display: flex; gap: 8px; align-items: baseline; } .f-qa-q span { font-family: var(--font-mono); font-size: 12px; color: #fff; background: var(--accent); border-radius: 50%; min-width: 20px; height: 20px; display: inline-grid; place-items: center; }
.f-qa-q b { font-size: 13px; color: var(--muted); font-weight: 600; }
.f-qa-a { font-size: 15px; font-weight: 700; color: var(--ink); line-height: 1.45; }
.f-qa-x { font-size: 12.5px; color: var(--muted); line-height: 1.55; }
.f-qa-k { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 6px; align-items: baseline; font-size: 12.5px; color: var(--ink); line-height: 1.5; }
.f-qa-k em { font-style: normal; font-size: 11px; font-weight: 700; padding: 0 6px; border-radius: 4px; border: 1px solid var(--line); color: var(--muted); white-space: nowrap; }
.f-qa-k.done em { color: var(--good); border-color: var(--good); background: var(--good-soft); }

.f-pts { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 10px; }
.f-pt { display: flex; flex-direction: column; gap: 6px; padding: 11px 13px; border: 1px solid var(--line); border-top: 4px solid var(--good); border-radius: 10px; background: var(--surface); }
.f-pt.t-bad { border-top-color: var(--bad); } .f-pt.t-warn { border-top-color: var(--warn); }
.f-pt-k { font-size: 15px; font-weight: 800; color: var(--ink); }
.f-pt-a { font-size: 13.5px; color: var(--ink); line-height: 1.55; }
.f-pt-e { margin-top: auto; padding: 7px 9px; border-radius: 7px; background: var(--bg); font-size: 12.5px; color: var(--muted); line-height: 1.5; }
.f-pt-e em { display: block; font-style: normal; font-weight: 700; color: var(--ink); font-family: var(--font-mono); font-size: 12px; }
.f-pbs { margin-top: 12px; padding: 12px 14px; border: 1px solid var(--line); border-radius: 10px; background: var(--surface); display: grid; gap: 6px; }
.f-pbs-h b { font-size: 14px; color: var(--ink); } .f-pbs-h span { margin-left: 8px; font-size: 12px; color: var(--muted); }
.f-pb { display: grid; grid-template-columns: 15em minmax(0, 1fr) 4.5em; gap: 10px; align-items: center; font-size: 13px; color: var(--ink); }
.f-pb-b { height: 10px; border-radius: 5px; background: var(--bg); border: 1px solid var(--line); overflow: hidden; } .f-pb-b i { display: block; height: 100%; background: var(--accent); }
.f-pb b { font-size: 13px; text-align: right; } .f-pb.all { font-weight: 700; } .f-pb.all .f-pb-b i { background: var(--ink); }
.f-pb.ch .f-pb-b i { background: color-mix(in srgb, var(--accent) 45%, white); } .f-pb.ch { color: var(--muted); }

.risks.f-full .rk-then { font-size: 13px; }
.f-sns { display: grid; gap: 8px; }
.f-sn { display: grid; grid-template-columns: 8em minmax(0, 1fr); gap: 14px; padding: 10px 13px; border: 1px solid var(--line); border-left: 4px solid var(--muted); border-radius: 10px; background: var(--surface); }
.f-sn.t-warn { border-left-color: var(--warn); } .f-sn.t-acc { border-left-color: var(--accent); }
.f-sn-l { display: flex; flex-direction: column; gap: 4px; } .f-sn-n { font-family: var(--font-mono); font-size: 20px; font-weight: 800; color: var(--ink); line-height: 1; }
.f-sn-c { font-size: 12px; font-weight: 700; color: var(--muted); line-height: 1.4; } .f-sn.t-warn .f-sn-c { color: var(--warn); } .f-sn.t-acc .f-sn-c { color: var(--accent); }
.f-sn-h { display: block; font-size: 15px; color: var(--ink); line-height: 1.4; }
.f-sn-e { margin-top: 4px; display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 6px; font-size: 13.5px; color: var(--ink); line-height: 1.55; }
.f-sn-e em { font-style: normal; font-size: 11px; font-weight: 700; color: var(--muted); padding-top: 2px; }

.f-kvs { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin-bottom: 10px; }
.f-kv { display: flex; flex-direction: column; gap: 2px; padding: 9px 12px; border: 1px solid var(--line); border-radius: 10px; background: var(--surface); }
.f-kv-k { font-size: 12px; color: var(--muted); } .f-kv b { font-size: 15px; color: var(--ink); } .f-kv-x { font-size: 12.5px; color: var(--muted); line-height: 1.5; }
.f-bss { display: grid; gap: 10px; }
.f-bs { padding: 11px 13px; border: 1px solid var(--line); border-radius: 10px; background: var(--surface); display: grid; gap: 7px; }
.f-bs-h { display: flex; flex-wrap: wrap; gap: 10px; align-items: baseline; } .f-bs-h b { font-size: 16px; color: var(--ink); }
.f-bs-u { font-size: 13px; color: var(--accent); font-weight: 700; }
.f-bs-bar { display: flex; height: 26px; border-radius: 6px; overflow: hidden; gap: 2px; }
.f-bs-bar span { display: flex; align-items: center; padding: 0 8px; font-size: 12px; color: #fff; background: var(--accent); white-space: nowrap; overflow: hidden; }
.f-bs-bar span:first-child { background: var(--bad); } .f-bs-bar span:nth-child(3) { background: color-mix(in srgb, var(--accent) 60%, white); }
.f-bs-bar .num, .f-bs-bar b { background: none !important; padding: 0 !important; color: #fff !important; font-weight: 800; margin-right: 4px; }
.f-bs-c { font-size: 12.5px; color: var(--muted); line-height: 1.5; }
.f-bs-k2a { font-size: 13px; color: var(--ink); line-height: 1.6; padding: 8px 10px; border-left: 3px solid var(--accent); background: var(--accent-soft); border-radius: 0 6px 6px 0; }

.f-ctg { margin-bottom: 12px; } .f-ctg-h { font-size: 12.5px; font-weight: 700; color: var(--muted); margin-bottom: 6px; }
.f-cts { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 8px; }
.f-ct { display: flex; flex-direction: column; gap: 4px; padding: 10px 12px; border: 1px solid var(--line); border-radius: 10px; background: var(--surface); }
.f-ctg.out .f-ct { border-style: dashed; }
.f-ct-n { font-size: 12.5px; font-weight: 700; color: var(--accent); } .f-ctg.out .f-ct-n { color: var(--muted); }
.f-ct-q { font-size: 15px; color: var(--ink); line-height: 1.4; }
.f-ct-w { font-size: 12.5px; color: var(--muted); line-height: 1.5; }
.f-ct-e { font-size: 13px; color: var(--ink); line-height: 1.55; }
.f-more > div { border: 0 !important; padding: 0 !important; background: none !important; }
.comp[class*="f-"] .num, .f-def .num, .f-pbs .num { background: none !important; padding: 0 !important; box-shadow: none !important; }

.f-crs { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.f-cr { display: flex; flex-direction: column; gap: 6px; padding: 11px 13px; border: 1px solid var(--line); border-radius: 10px; background: var(--surface); }
.f-cr-h { display: flex; flex-wrap: wrap; gap: 8px; align-items: baseline; }
.f-cr-c { font-size: 13px; font-weight: 700; color: var(--accent); } .f-cr-h b { font-size: 17px; color: var(--ink); }
.f-cr-p { margin-left: auto; font-size: 12px; font-weight: 700; color: var(--muted); padding: 0 7px; border-radius: 999px; border: 1px solid var(--line); background: var(--bg); }
.f-cr-r { font-size: 13.5px; color: var(--ink); line-height: 1.55; }
.f-cr-s { margin-top: auto; padding-top: 6px; border-top: 1px dashed var(--line); font-size: 12.5px; color: var(--muted); line-height: 1.55; }
.f-cr-s em { font-style: normal; font-weight: 700; margin-right: 6px; }

.f-rbs { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }
.f-rb { display: flex; flex-direction: column; gap: 4px; padding: 9px 11px; border: 1px solid var(--line); border-radius: 10px; background: var(--surface); font-size: 13px; color: var(--ink); line-height: 1.45; }
.f-rb-c { font-family: var(--font-mono); font-size: 12px; font-weight: 700; color: var(--accent); } .f-rb b { color: var(--ink); }

.f-pns { border: 1px solid var(--line); border-radius: 10px; overflow: hidden; background: var(--surface); }
.f-pn { display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(0, 1.3fr) minmax(0, 1fr); gap: 14px; padding: 10px 14px; border-top: 1px solid var(--line); align-items: start; }
.f-pn.f-pn-hd { border-top: 0; padding: 6px 14px; background: var(--bg); font-size: 11.5px; font-weight: 700; color: var(--muted); }
.f-pn > div { display: flex; flex-direction: column; gap: 2px; } .f-pn b { font-size: 14px; color: var(--ink); }
.f-pn-w { font-size: 12.5px; color: var(--muted); line-height: 1.5; }
.f-pn-big { font-size: 15px !important; }
.f-pn-trip { display: inline-block; font-size: 12.5px; font-weight: 700; color: var(--bad); background: var(--bad-soft); border-radius: 6px; padding: 3px 8px; line-height: 1.45; }

.f-sgs { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }
.f-sg { display: flex; flex-direction: column; gap: 4px; padding: 10px 12px; border: 1px solid var(--line); border-top: 4px solid var(--accent); border-radius: 10px; background: var(--surface); }
.f-sg.run { border-top-color: var(--good); } .f-sg.shadow { border-style: dashed; border-top-color: var(--muted); } .f-sg.stop { border-top-color: var(--bad); }
.f-sg-k { font-size: 12px; font-weight: 700; color: var(--muted); } .f-sg-f { font-size: 15px; color: var(--ink); line-height: 1.35; }
.f-sg.stop .f-sg-f { color: var(--bad); } .f-sg-b { font-size: 12.5px; color: var(--muted); line-height: 1.5; }

.f-vd { margin-bottom: 4px; } .f-vd-p { display: inline-block; font-size: 13px; font-weight: 700; color: var(--accent); border: 1px solid var(--accent); background: var(--accent-soft); border-radius: 999px; padding: 0 9px; }
.f-pair.four { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.f-three { display: grid; grid-template-columns: 1.4fr 1fr 1fr; gap: 8px; margin-bottom: 6px; }
.f-gauge { display: grid; gap: 4px; }
.f-gauge-t { display: flex; flex-wrap: wrap; gap: 8px; align-items: baseline; } .f-gauge-t span { font-size: 12px; color: var(--muted); }
.f-gauge-t b { font-size: 18px; color: var(--ink); font-family: var(--font-mono); } .f-gauge-t em { font-style: normal; font-size: 12.5px; color: var(--muted); }
.f-gauge-b { position: relative; height: 12px; border-radius: 6px; background: var(--bg); border: 1px solid var(--line); margin-top: 4px; }
.f-gauge-b .band { position: absolute; top: 0; bottom: 0; background: var(--line); }
.f-gauge-b .pt { position: absolute; top: -4px; width: 12px; height: 18px; margin-left: -6px; border-radius: 4px; background: var(--accent); }
.f-gauge-b .lim { position: absolute; top: -6px; bottom: -6px; width: 2px; background: var(--bad); }
.f-gauge-l { position: relative; height: 18px; font-size: 11.5px; color: var(--muted); }
.f-gauge-l span { position: absolute; transform: translateX(-50%); white-space: nowrap; } .f-gauge-l span.lim { color: var(--bad); font-weight: 700; }

.f-nvs { border: 1px solid var(--line); border-radius: 10px; overflow: hidden; background: var(--surface); }
.f-nv { display: grid; grid-template-columns: minmax(0, 1.6fr) 5em 5em minmax(0, 1.6fr); gap: 10px; padding: 7px 12px; border-top: 1px solid var(--line); align-items: center; font-size: 13px; font-family: var(--font-mono); color: var(--ink); }
.f-nv-k { font-family: var(--font-body); }
.f-nv.f-nv-hd { border-top: 0; background: var(--bg); font-size: 11.5px; font-weight: 700; color: var(--muted); font-family: var(--font-body); }
.f-nv.bm { color: var(--muted); } .f-nv.v6 { font-weight: 700; background: var(--accent-soft); } .f-nv.ref { color: var(--muted); font-style: italic; }
.f-nv-b { position: relative; display: flex; align-items: center; gap: 6px; }
.f-nv-b i { display: block; height: 10px; border-radius: 3px; background: var(--accent); flex: 0 0 auto; max-width: 60%; }
.f-nv.bm .f-nv-b i { background: var(--muted); } .f-nv.ref .f-nv-b i { background: var(--line); }
.f-nv-b em { font-style: normal; font-size: 11.5px; } .f-nv-b em.up { color: var(--good); } .f-nv-b em.dn { color: var(--warn); }
@media (max-width: 760px) {
  .f-qas, .f-crs, .f-kvs, .f-sgs, .f-three { grid-template-columns: minmax(0, 1fr); } .f-rbs { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .f-sn, .f-pn { grid-template-columns: minmax(0, 1fr); gap: 4px; } .f-pn.f-pn-hd { display: none; } .f-pb { grid-template-columns: minmax(0, 1fr) 4em; } .f-pb-b { grid-column: 1 / -1; }
}
"""


# ================================================================ round 3
def year_signals(rows):
    """| 年 | A … | 美 … | → two side-by-side slot panels; months as 12 squares, stock share as a bar."""
    def f(x):
        try:
            return float(_txt(x))
        except ValueError:
            return 0.0
    def panel(title, cols):
        hd = '<div class="f-ys-r hd"><span>年</span><span>紧张月（每格 1 个月）</span><span>平均股票仓位</span><span>年末把握 p</span><span>去重改名单</span>' + \
             ('<span>可参选</span>' if 'n' in cols else '') + '</div>'
        body = ''
        for r in rows:
            m = int(f(r[cols['m']]))
            sq = ''.join(f'<i class="{"on" if k < m else ""}"></i>' for k in range(12))
            pos = f(r[cols['pos']])
            body += (f'<div class="f-ys-r"><span class="y">{_txt(r[0])}</span><span class="sq">{sq}<b>{m}</b></span>'
                     f'<span class="bar"><i style="width:{pos * 100:.0f}%"></i><b>{_txt(r[cols["pos"]])}</b></span>'
                     f'<span class="v">{_txt(r[cols["p"]])}</span><span class="v">{_txt(r[cols["d"]])}</span>'
                     + (f'<span class="v">{_txt(r[cols["n"]])}</span>' if 'n' in cols else '') + '</div>')
        return f'<div class="f-ys-p"><div class="f-ys-h">{title}</div><div class="f-ys-t{" n6" if "n" in cols else ""}">{hd}{body}</div></div>'
    return (panel('A 股名额', {'m': 1, 'd': 2, 'n': 3, 'p': 4, 'pos': 5})
            + panel('美股名额', {'m': 6, 'd': 7, 'p': 8, 'pos': 9}))


def picks(rows):
    out = ''
    for r in rows:
        name = _txt(r[0])
        items = re.findall(r'([^、\d][^、]*?)\s*(\d+)(?=、|$)', _txt(r[1]))
        mx = max((int(n) for _, n in items), default=1)
        chips = ''.join(f'<span class="f-pk-c" style="--w:{int(n) / mx * 100:.0f}%"><span>{nm.strip()}</span><b>{n}</b></span>' for nm, n in items)
        never = [x for x in _txt(r[2]).split('、') if x.strip()]
        nv = ''.join(f'<span class="f-pk-n">{x}</span>' for x in never)
        out += (f'<div class="f-pk"><div class="f-pk-h">{name}<em>入选月数（条长 = 月数）</em></div><div class="f-pk-cs">{chips}</div>'
                f'<div class="f-pk-nh">从未入选{"：" + nv if never and nv else ""}</div></div>')
    return f'<div class="f-pks">{out}</div>'


TABLES += [
    (lambda h: len(h) == 10 and h[0] == '年' and h[1] == 'A 紧张月', lambda h, r: year_signals(r), 'years'),
    (lambda h: h == ['名额', '入选月数最多的候选', '从未入选'], lambda h, r: picks(r), 'picks'),
]

_apply2 = apply


def apply(html):
    html = _apply2(html)
    soup = BeautifulSoup(html, 'html.parser')
    qs = {}
    for h in soup.find_all('h2'):
        t = h.get_text('', strip=True)
        m = re.match(r'^(附表 [A-Z])', t)
        if m:
            nm = re.match(r'^附表 [A-Z][：:]\s*([^—，,]+)', t)
            qs[m.group(1)] = ((nm.group(1).strip() if nm else ''), (h.get('data-sl-q') or '').split('｜')[0].strip())
    for ul in soup.find_all('ul'):
        lis = ul.find_all('li', recursive=False)
        keys = [li.find('strong').get_text('', strip=True) if li.find('strong') else '' for li in lis]
        if lis and all(re.fullmatch(r'附表 [A-Z]', k) for k in keys):
            cards = ''
            for li, k in zip(lis, keys):
                li.find('strong').extract()
                body = re.sub(r'^[：:]\s*', '', li.decode_contents().strip())
                nm, q = qs.get(k, ('', ''))
                cards += (f'<div class="f-ap"><div class="f-ap-h"><b>{k}{" · " + nm if nm else ""}</b><span>{q}</span></div>'
                          f'<div class="f-ap-b">{body}</div></div>')
            ul.replace_with(_frag(f'<div class="f-aps">{cards}</div>'))
    return str(soup)


CSS += r"""
.f-years-wrap { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.f-ys-p { border: 1px solid var(--line); border-radius: 10px; background: var(--surface); overflow: hidden; }
.f-ys-h { padding: 7px 12px; font-size: 13.5px; font-weight: 700; color: var(--ink); background: var(--bg); border-bottom: 1px solid var(--line); }
.f-ys-r { display: grid; grid-template-columns: 3em minmax(0, 1.7fr) minmax(0, 1.2fr) 4em 3.6em; gap: 8px; align-items: center; padding: 4px 12px; font-size: 12.5px; color: var(--ink); }
.f-ys-t.n6 .f-ys-r { grid-template-columns: 3em minmax(0, 1.7fr) minmax(0, 1.2fr) 4em 3.6em 3.4em; }
.f-ys-r.hd { font-size: 11px; font-weight: 700; color: var(--muted); padding-top: 7px; }
.f-ys-r .y { font-family: var(--font-mono); color: var(--muted); }
.f-ys-r .sq { display: flex; gap: 2px; align-items: center; } .f-ys-r .sq i { width: 7px; height: 12px; border-radius: 2px; background: var(--bg); border: 1px solid var(--line); }
.f-ys-r .sq i.on { background: var(--bad); border-color: var(--bad); } .f-ys-r .sq b { margin-left: 5px; font-family: var(--font-mono); font-size: 12px; }
.f-ys-r .bar { position: relative; display: flex; align-items: center; gap: 5px; } .f-ys-r .bar i { display: block; height: 8px; border-radius: 3px; background: var(--accent); max-width: 70%; }
.f-ys-r .bar b { font-family: var(--font-mono); font-size: 12px; font-weight: 600; }
.f-ys-r .v { font-family: var(--font-mono); text-align: right; color: var(--muted); }
.f-pks { display: grid; gap: 10px; margin-top: 10px; }
.f-pk { padding: 10px 12px; border: 1px solid var(--line); border-radius: 10px; background: var(--surface); }
.f-pk-h { font-size: 14px; font-weight: 700; color: var(--ink); margin-bottom: 6px; } .f-pk-h em { font-style: normal; font-weight: 400; font-size: 12px; color: var(--muted); margin-left: 8px; }
.f-pk-cs { display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: 4px 12px; }
.f-pk-c { position: relative; display: flex; justify-content: space-between; gap: 6px; padding: 2px 6px; font-size: 12.5px; color: var(--ink); border-radius: 4px; overflow: hidden; }
.f-pk-c::before { content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: var(--w); background: var(--accent-soft); z-index: 0; }
.f-pk-c > * { position: relative; } .f-pk-c b { font-family: var(--font-mono); }
.f-pk-nh { margin-top: 6px; font-size: 12px; color: var(--muted); } .f-pk-n { display: inline-block; margin: 2px 4px 0 0; padding: 0 6px; border: 1px dashed var(--line); border-radius: 4px; }
.f-aps { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.f-ap { display: flex; flex-direction: column; gap: 6px; padding: 11px 13px; border: 1px solid var(--line); border-radius: 10px; background: var(--surface); }
.f-ap-h b { display: block; font-size: 15px; color: var(--ink); } .f-ap-h span { font-size: 13.5px; color: var(--ink); line-height: 1.5; }
.f-ap-b { font-size: 12.5px; color: var(--muted); line-height: 1.6; } .f-ap-b code { font-size: 11.5px; }
@media (max-width: 760px) { .f-years-wrap, .f-aps { grid-template-columns: minmax(0, 1fr); } }
"""

CSS += r"""
.f-rts { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; }
.f-rt { display: flex; flex-direction: column; gap: 8px; padding: 12px 14px 14px; border-radius: 10px; background: var(--surface); border: 1px solid var(--line); }
.f-rt-k { display: flex; align-items: center; gap: 7px; font-size: 12.5px; font-weight: 700; color: var(--muted); letter-spacing: .02em; }
.f-rt-k span { display: inline-grid; place-items: center; width: 20px; height: 20px; border-radius: 6px; background: var(--accent-soft); color: var(--accent); font-family: var(--font-mono); font-size: 11.5px; }
.f-rt-f { font-size: 16px; line-height: 1.35; color: var(--ink); }
.f-rt-b { padding-top: 8px; border-top: 1px solid var(--line); font-size: 12.5px; color: var(--muted); line-height: 1.55; }
@media (max-width: 760px) { .f-rts { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
"""

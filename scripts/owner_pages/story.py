"""Owner-page spec layer (docs/reference/owner-facing-uiux-principles.md §13).

Runs after polish.py. Only restructures and formats the source's own words: it never writes new content.
- every h2 section opens with a memo sentence (p.memo): the section's own lede, else its first sentence
- <details> become the spec's fold component (div.fold > button.fold-h + div.fold-b)
- a section shows at most one table expanded; the others fold in place as 明细表
- reference tables (definitions, lists) get data-lint="ref"
- conclusion cells get bold; list items and long paragraphs open with a bold phrase taken from their own text
"""
import re
import polish as P
from bs4 import BeautifulSoup, NavigableString, Tag

VERDICT_HEAD = re.compile(r'结论|判定|结果|读法|结局|状态|意味着|代价|当时|怎么处理|对愿景|得出|生效|兑现|影响')
NUM = re.compile(r'\d')


def txt(el):
    return re.sub(r'\s+', '', el.get_text(' ', strip=True)) if el is not None else ''


def add_class(el, *cls):
    cur = el.get('class', [])
    for c in cls:
        if c not in cur:
            cur.append(c)
    el['class'] = cur


def in_fold(el):
    return any('fold-b' in (p.get('class') or []) for p in el.parents if isinstance(p, Tag))


# ---------- folds ----------

def make_fold(soup, title, nodes, open_=False):
    fold = soup.new_tag('div', attrs={'class': ['fold']})
    btn = soup.new_tag('button', attrs={'class': ['fold-h'], 'type': 'button', 'aria-expanded': 'true' if open_ else 'false'})
    chev = soup.new_tag('span', attrs={'class': ['chev'], 'aria-hidden': 'true'})
    chev.string = '▸'
    btn.append(chev)
    lab = soup.new_tag('span')
    if isinstance(title, str):
        lab.string = title
    else:
        for c in list(title):
            lab.append(c)
    btn.append(lab)
    body = soup.new_tag('div', attrs={'class': ['fold-b']})
    if not open_:
        body['hidden'] = ''
    for n in nodes:
        body.append(n)
    fold.append(btn)
    fold.append(body)
    return fold


def convert_details(soup):
    for d in list(soup.find_all('details')):
        summ = d.find('summary')
        title = list(summ.contents) if summ else '展开'
        if summ:
            summ.extract()
        nodes = [c.extract() for c in list(d.contents)]
        d.replace_with(make_fold(soup, title, nodes))


# ---------- tables ----------

def table_wrap(t):
    p = t.parent
    return p if p is not None and 'table-wrap' in (p.get('class') or []) else t


def mark_tables(soup):
    for t in soup.find_all('table'):
        heads = [txt(th) for th in t.find_all('th')]
        has_verdict = any(VERDICT_HEAD.search(h) for h in heads) or t.find(class_='pill') is not None
        cls = t.get('class') or []
        numeric = t.find(class_=re.compile(r'^(numcol|ibc|ib)$')) is not None
        if 'deflist' in cls or (not has_verdict and not numeric):
            t['data-lint'] = 'ref'
        # conclusion cells: bold the short phrase so every row carries its verdict visually
        vcols = [i for i, h in enumerate(heads) if VERDICT_HEAD.search(h)]
        for tr in t.select('tbody tr'):
            tds = tr.find_all('td')
            for ci in vcols:
                if ci < len(tds):
                    td = tds[ci]
                    if td.find(class_=re.compile('pill|ib')) or td.find(['b', 'strong']):
                        continue
                    if 0 < len(txt(td)) <= 46:
                        b = soup.new_tag('b')
                        for c in list(td.contents):
                            b.append(c.extract())
                        td.append(b)


def fold_extra_tables(soup):
    for sec in soup.find_all('section'):
        if 'status' in (sec.get('class') or []) or not sec.find('h2'):
            continue
        tables = [t for t in sec.find_all('table') if not in_fold(t) and t.get('data-lint') != 'ref']
        if not tables:
            continue
        has_img = sec.find('img') is not None and not all(in_fold(i) for i in sec.find_all('img'))
        keep = 0 if not has_img else 1
        # with a figure: keep one expanded only if it carries the verdicts; without: keep the first
        def score(t):
            return (t.find(class_='pill') is not None, VERDICT_HEAD.search(' '.join(txt(th) for th in t.find_all('th'))) is not None)
        if len(tables) <= keep and not has_img:
            continue
        ranked = sorted(tables, key=lambda t: score(t), reverse=True)
        keepers = set()
        if has_img:
            if score(ranked[0])[0]:
                keepers.add(id(ranked[0]))
        else:
            keepers.add(id(tables[0]))
        for t in tables:
            if id(t) in keepers:
                continue
            w = table_wrap(t)
            prev = w.find_previous_sibling()
            nodes = [w]
            if prev is not None and 'score' in (prev.get('class') or []):
                nodes.insert(0, prev)
            heads = [th.get_text(' ', strip=True) for th in t.find_all('th')]
            label = '明细表' + (f'：{heads[0][:24]}' if heads and heads[0] else '')
            nxt = w.find_next_sibling()
            if nxt is not None and 'table-note' in (nxt.get('class') or []):
                nodes.append(nxt)
            anchor = soup.new_tag('span')
            nodes[0].insert_before(anchor)
            fold = make_fold(soup, label, [n.extract() for n in nodes])
            anchor.replace_with(fold)


# ---------- memo ----------

def first_sentence(s):
    m = re.match(r'^(.+?[。！？])', s)
    return m.group(1) if m else None


def add_memos(soup):
    for sec in soup.find_all('section'):
        h2 = sec.find('h2')
        if h2 is None or {'status', 'appendix'} & set(sec.get('class') or []):
            continue
        if sec.find('p', class_='memo'):
            continue
        nxt = h2.find_next_sibling()
        if nxt is not None and nxt.name == 'div' and 'lede' in (nxt.get('class') or []):
            p = soup.new_tag('p', attrs={'class': ['memo']})
            for c in list(nxt.contents):
                p.append(c.extract())
            nxt.replace_with(p)
            continue
        # otherwise lift the first sentence of the section's first paragraph
        for el in h2.find_next_siblings():
            if el.name in ('figure',) or (el.name == 'div' and 'table-wrap' in (el.get('class') or [])):
                break
            if el.name == 'p' and not el.find('img'):
                full = el.get_text()
                fs = first_sentence(full.strip())
                if not fs:
                    break
                p = soup.new_tag('p', attrs={'class': ['memo']})
                if fs.strip() == full.strip():
                    for c in list(el.contents):
                        p.append(c.extract())
                    el.replace_with(p)
                else:
                    # split the paragraph at the end of its first sentence, keeping inline markup
                    rest = soup.new_tag('p', attrs={'class': el.get('class', [])})
                    acc = ''
                    moving_to_rest = False
                    for c in list(el.contents):
                        if moving_to_rest:
                            rest.append(c.extract())
                            continue
                        t = c.get_text() if isinstance(c, Tag) else str(c)
                        if len(acc) + len(t) <= len(fs.strip()) + (len(full) - len(full.lstrip())):
                            p.append(c.extract())
                            acc += t
                        else:
                            cut = len(fs.strip()) + (len(full) - len(full.lstrip())) - len(acc)
                            if isinstance(c, NavigableString):
                                head, tail = str(c)[:cut], str(c)[cut:]
                                p.append(NavigableString(head))
                                rest.append(NavigableString(tail.lstrip()))
                                c.extract()
                            else:
                                rest.append(c.extract())
                            moving_to_rest = True
                    el.insert_before(p)
                    if rest.get_text(strip=True):
                        el.replace_with(rest)
                    else:
                        el.decompose()
                break
            if el.name in ('ul', 'ol', 'div', 'h3'):
                break
        if sec.find('p', class_='memo') is None:
            last = None
            for node in h2.find_all(string=True):
                if '：' in node:
                    last = node
            if last is not None:
                head, concl = str(last).split('：', 1)
                if concl.strip():
                    last.replace_with(NavigableString(head))
                    tail = []
                    nxt = last.next_sibling if hasattr(last, 'next_sibling') else None
                    memo = soup.new_tag('p', attrs={'class': ['memo']})
                    memo.append(NavigableString(concl.strip()))
                    h2.insert_after(memo)
        if sec.find('p', class_='memo') is None:
            nxt = h2.find_next_sibling()
            if nxt is not None and nxt.name == 'ul' and len(nxt.find_all('li', recursive=False)) >= 2:
                li = nxt.find('li')
                memo = soup.new_tag('p', attrs={'class': ['memo']})
                for c in list(li.contents):
                    memo.append(c.extract())
                li.decompose()
                h2.insert_after(memo)


# ---------- lists and paragraphs ----------

def bold_lead(soup, el, max_whole=32):
    """Bold the element's own opening phrase. Returns True if changed."""
    first = next((c for c in el.contents if not (isinstance(c, NavigableString) and not c.strip())), None)
    if first is None or (isinstance(first, Tag) and first.name in ('b', 'strong')):
        return False
    full = el.get_text()
    s = full.strip()
    if not s:
        return False
    if len(s) <= max_whole and not el.find(['ul', 'ol', 'table']):
        b = soup.new_tag('b')
        for c in list(el.contents):
            if isinstance(c, Tag) and c.name in ('ul', 'ol'):
                break
            b.append(c.extract())
        el.insert(0, b)
        return True
    if not isinstance(first, NavigableString):
        return False
    t = str(first)
    lt = t.lstrip()
    m = re.match(r'^(.{2,30}?[：:])', lt) or re.match(r'^(.{4,34}?[，,；;])', lt) or re.match(r'^(.{4,44}?[。])', lt)
    if not m:
        return False
    lead = m.group(1)
    pre = t[:len(t) - len(lt)]
    b = soup.new_tag('b')
    b.string = lead
    first.replace_with(NavigableString(pre))
    el.contents[0].insert_after(b)
    b.insert_after(NavigableString(lt[len(lead):]))
    return True


def lists_and_paragraphs(soup):
    for li in soup.find_all('li'):
        if li.find_parent('nav') is not None or in_fold(li):
            continue
        bold_lead(soup, li)
    for p in soup.find_all('p'):
        if in_fold(p) or (p.get('class') and {'memo', 'table-note', 'cap', 'note'} & set(p.get('class'))):
            continue
        if p.find_parent(class_=re.compile(r'card|option|vd-card')):
            continue
        if len(txt(p)) > 110 and not p.find(['b', 'strong']):
            bold_lead(soup, p)


def notes(soup):
    for p in soup.select('p.table-note'):
        add_class(p, 'note')


def boxed_to_tg(soup):
    for td in soup.select('td.boxed'):
        add_class(td, 'tg')


def appendix_and_actions(soup):
    for sec in soup.find_all('section'):
        h2 = sec.find('h2')
        if h2 is None:
            continue
        t = txt(h2)
        if t.endswith('更新记录') or t == '更新记录':
            # history is an appendix (spec 0.1): timeline rows, heading demoted so it is not a story section
            h3 = soup.new_tag('h2', attrs={'id': h2.get('id'), 'class': ['appx']})
            h3.string = '更新记录'
            h2.replace_with(h3)
            h3.name = 'h3'
            add_class(sec, 'appendix')
            for ul in sec.find_all('ul'):
                rows = []
                ok = True
                for li in ul.find_all('li', recursive=False):
                    b = li.find(['strong', 'b'])
                    if b is None or not li.get_text(strip=True).startswith(b.get_text(strip=True)):
                        ok = False
                        break
                    d = b.get_text(strip=True)
                    b.extract()
                    rest = li.decode_contents().strip()
                    rest = re.sub(r'^[：:]\s*', '', rest)
                    rows.append(f'<div><span class="d">{d}</span><span>{rest}</span></div>')
                if ok and rows:
                    ul.replace_with(BeautifulSoup('<div class="log">' + ''.join(rows) + '</div>', 'html.parser'))
        elif re.sub(r'^\d+', '', t) in ('接下来', '下一步'):
            add_class(sec, 'status', 'actions')
            for ol in sec.find_all(['ol', 'ul'], recursive=False):
                add_class(ol, 'next-steps')


def decisions(soup):
    for o in soup.select('div.options'):
        add_class(o, 'decision')


def code_paths(soup):
    for td in soup.find_all('td'):
        if in_fold(td) or 'milestone/' not in td.get_text():
            continue
        h = td.decode_contents()
        h = re.sub(r'(?:<code>)?(milestone/[\w.\-/]+)(?:</code>)?', lambda m: f'<a href="https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/tree/{m.group(1)}">（标签）</a>', h)
        td.clear()
        td.append(BeautifulSoup(h, 'html.parser'))


def tagline_conclusions(soup):
    """A last column of short judgement phrases with no verdict header is the table's conclusion column: show it as tags."""
    for t in soup.find_all('table'):
        if t.get('data-lint') == 'ref' or in_fold(t):
            continue
        heads = [txt(th) for th in t.find_all('th')]
        if not heads or any(VERDICT_HEAD.search(h) for h in heads) or t.find(class_='pill'):
            continue
        rows = [tr for tr in t.select('tbody tr') if 'grp' not in (tr.get('class') or [])]
        last = [tr.find_all('td')[-1] for tr in rows if tr.find_all('td')]
        vals = [txt(td) for td in last]
        if vals and all(0 < len(v) <= 16 and not re.fullmatch(r'[\d.,%·\s/−+\-–约倍个只年]+', v) for v in vals):
            for td in last:
                inner = td.decode_contents()
                td.clear()
                td.append(BeautifulSoup(f'<span class="pill mute tagline">{inner}</span>', 'html.parser'))


def v4_eras(soup):
    for t in soup.find_all('table'):
        heads = [txt(th) for th in t.find_all('th')]
        if not heads or heads[0] != '年代' or not any(h.startswith('A2') for h in heads):
            continue
        sec = t.find_parent('section')
        points = [b.get_text(strip=True) for b in sec.select('ul li > strong:first-child, ul li > b:first-child')] if sec else []
        era = {'2006–2010': next((x for x in points if x.startswith('前五年')), None), '2011–2015': next((x for x in points if x.startswith('后五年')), None)}
        th = soup.new_tag('th', attrs={'class': ['h-take']}); th.string = '读法'
        if len(t.find('thead').find_all('tr')) > 1:
            th['rowspan'] = '2'
        t.find('thead').find('tr').append(th)
        for tr in t.select('tbody tr'):
            tds = tr.find_all('td')
            label = txt(tds[0]) if tds else ''
            if label in era and era[label]:
                td = soup.new_tag('td', attrs={'class': ['c-take']})
                b = soup.new_tag('b'); b.string = era[label]; td.append(b)
                tr.append(td)
            elif len(tds) >= 2 and txt(tds[1]).startswith('留空'):
                rest = tds[1].get_text().split('：', 1)
                tds[1].clear()
                tds[1].append(BeautifulSoup(f'<span class="pill warn">留空</span><span class="pill-note">{rest[1] if len(rest) > 1 else ""}</span>', 'html.parser'))
                if not tds[-1].get_text(strip=True):
                    pass
                tr.append(soup.new_tag('td'))


STK_COLORS = ['var(--accent)', 'color-mix(in srgb, var(--accent) 55%, white)', 'var(--good)', 'var(--warn)', 'var(--muted)', 'var(--bad)']


def stacked_bars(soup):
    """'name 46% ｜ name 18% ｜ …' summing to about 100% -> the spec's .stk proportion bar (+ legend)."""
    for p in soup.find_all('p'):
        raw = p.get_text(' ', strip=True)
        parts = [x.strip() for x in raw.split('｜')]
        if len(parts) < 3:
            continue
        segs = []
        for x in parts:
            m = re.match(r'^(.+?)\s*(\d+(?:\.\d+)?)%$', x)
            if not m:
                segs = []
                break
            segs.append((m.group(1).strip(), float(m.group(2))))
        if not segs or not (95 <= sum(v for _, v in segs) <= 105):
            continue
        bar = ''.join(f'<span style="width:{v}%;background:{STK_COLORS[i % len(STK_COLORS)]}" title="{n} {v:g}%">{(n + " " + format(v, "g") + "%") if v >= 12 else ""}</span>' for i, (n, v) in enumerate(segs))
        leg = ''.join(f'<span><i style="background:{STK_COLORS[i % len(STK_COLORS)]}"></i>{n} <b>{v:g}%</b></span>' for i, (n, v) in enumerate(segs))
        p.replace_with(BeautifulSoup(f'<div class="stk-wrap"><div class="stk">{bar}</div><div class="stk-l">{leg}</div></div>', 'html.parser'))


def risk_and_effect(soup):
    for t in soup.find_all('table'):
        heads = [txt(th) for th in t.find_all('th')]
        if heads and heads[0] == '风险' and len(heads) >= 2:
            for tr in t.select('tbody tr'):
                tds = tr.find_all('td')
                if len(tds) > 1:
                    for b in tds[1].find_all(['b', 'strong']):
                        add_class(b, 'c-bad')
        if '生效' in heads:
            ci = heads.index('生效')
            for tr in t.select('tbody tr'):
                tds = tr.find_all('td')
                if ci < len(tds) and not tds[ci].find(class_='pill'):
                    v = tds[ci].get_text(strip=True)
                    k = 'good' if v.startswith('已') else 'info'
                    tds[ci].clear()
                    tds[ci].append(BeautifulSoup(f'<span class="pill {k}">{v}</span>', 'html.parser'))


def reading_notes(soup):
    """A long multi-sentence paragraph right after a table/figure is the table's reading notes:
    show it as a compact 'how to read' block, one sentence per row, instead of one dense paragraph."""
    for p in soup.find_all('p'):
        prev = p.find_previous_sibling()
        if prev is None or not (prev.name == 'figure' or 'table-wrap' in (prev.get('class') or []) or 'fold' in (prev.get('class') or [])):
            continue
        if p.get('class') and 'memo' in p.get('class'):
            continue
        text = p.get_text()
        if len(text) < 120 or text.count('。') < 3:
            continue
        h = p.decode_contents()
        parts = [x.strip() for x in re.split(r'(?<=。)(?![^<]*>)', h) if x.strip()]
        rows = ''.join(f'<div class="rn-i">{x}</div>' for x in parts)
        p.replace_with(BeautifulSoup(f'<div class="readnote"><div class="rn-h">{'怎么读这张图' if prev.name == 'figure' else '怎么读这张表'}</div>{rows}</div>', 'html.parser'))


def storify(html, slug=''):
    soup = BeautifulSoup(html, 'html.parser')
    convert_details(soup)
    reading_notes(soup)
    if slug == 'v4-health':
        v4_eras(soup)
    appendix_and_actions(soup)
    add_memos(soup)
    stacked_bars(soup)
    risk_and_effect(soup)
    mark_tables(soup)
    tagline_conclusions(soup)
    code_paths(soup)
    decisions(soup)
    fold_extra_tables(soup)
    lists_and_paragraphs(soup)
    boxed_to_tg(soup)
    notes(soup)
    # the page-opening section is the status block
    first = soup.find('section', class_='intro')
    if first is not None:
        add_class(first, 'status')
    return str(soup)


FOLD_JS = r'''
document.querySelectorAll('.fold-h').forEach(function (b) {
  b.addEventListener('click', function () {
    var open = b.getAttribute('aria-expanded') === 'true';
    b.setAttribute('aria-expanded', open ? 'false' : 'true');
    var body = b.nextElementSibling;
    if (open) body.setAttribute('hidden', ''); else body.removeAttribute('hidden');
  });
});
'''

CSS = r'''
/* ===== spec layer: docs/reference/owner-facing-uiux-principles.md §13 ===== */
:root { --fg: var(--ink); --mono: var(--font-mono); --body: var(--font-body); --rule: var(--line); --ok: var(--good); --ok-soft: var(--good-soft); }
p.memo { font-size: 17px; font-weight: 700; line-height: 1.65; border-left: 4px solid var(--accent); background: var(--surface); padding: 12px 16px; border-radius: 0 10px 10px 0; margin: 0 0 18px; }
p.memo strong { color: var(--accent); }
.fold { background: var(--surface); border: 1px solid var(--line); border-radius: 10px; margin: 14px 0 20px; }
.fold-h { all: unset; box-sizing: border-box; display: flex; gap: 8px; align-items: center; width: 100%; padding: 11px 16px; cursor: pointer; color: var(--accent); font-weight: 500; font-size: 15px; border-radius: 10px; }
.fold-h:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.fold-h .chev { display: inline-block; transition: transform .15s; }
.fold-h[aria-expanded="true"] .chev { transform: rotate(90deg); }
.fold-b { padding: 0 16px 12px; }
.fold-b > .table-wrap:first-child, .fold-b > .score:first-child { margin-top: 4px; }
td.ibc { min-width: 150px; }
td.tg { outline: 2px solid var(--accent); outline-offset: -4px; }
'''

CSS += r"""
section.appendix h3 { font-size: 20px; margin-top: 0; }
ol.next-steps, ul.next-steps { list-style: none; padding: 0; margin: 0; display: grid; gap: 0; background: var(--surface); border: 1px solid var(--line); border-radius: 10px; counter-reset: none; }
ol.next-steps > li, ul.next-steps > li { padding: 12px 16px 12px 18px; border-bottom: 1px solid var(--line); margin: 0; }
ol.next-steps > li::before { display: none; }
ol.next-steps > li:last-child, ul.next-steps > li:last-child { border-bottom: 0; }
ol.next-steps > li > b:first-child, ol.next-steps > li > strong:first-child { display: inline-block; min-width: 7em; color: var(--accent); }
.pill.tagline { white-space: normal; font-weight: 500; }
"""

CSS += r"""
.stk-wrap { margin: 8px 0 16px; }
.stk span { color: #fff; }
.stk-l span { display: inline-flex; align-items: center; }
.stk-l b { color: var(--ink); margin-left: 3px; font-family: var(--font-mono); font-weight: 500; }
"""


# ---------- UX pass (comments 2026-11-17: 段落、卡片没有 UI/UX) ----------
NUMTOK = re.compile(r'([+\-−]?\d+(?:\.\d+)?(?:\s*[–~]\s*[+\-−]?\d+(?:\.\d+)?)?\s*(?:%|个百分点|个点|倍|元|pp)|\d{4}[–-]\d{2,4}\s*年(?!化))')
ARROW_VAL = re.compile(r'([+\-−]?\d+(?:\.\d+)?%)\s*→\s*([+\-−]?\d+(?:\.\d+)?%)')
BAD_T = re.compile(r'输|慢|失|错|差(?!距)|亏|问题|风险|代价|没')
GOOD_T = re.compile(r'赢|贡献|好|有效|对|成立|添花|快')


def mark_numbers(soup, el):
    for node in list(el.find_all(string=True)):
        if node.find_parent(['code', 'a', 'button']) is not None or node.find_parent(class_=re.compile('pill|num|cv|mg')) is not None:
            continue
        s = str(node)
        if not NUMTOK.search(s) and '→' not in s:
            continue
        h = NUMTOK.sub(lambda m: f'<span class="num">{m.group(1)}</span>', html_escape(s))
        h = h.replace('→', '<span class="arr">→</span>')
        node.replace_with(BeautifulSoup(h, 'html.parser'))


def html_escape(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def card_ux(soup):
    for card in soup.select('.cards .card'):
        if card.find_parent(class_='status') is not None:
            continue
        title = card.find(class_='ct')
        t = title.get_text(strip=True) if title else ''
        tone = 'bad' if BAD_T.search(t) else ('good' if GOOD_T.search(t) else 'info')
        add_class(card, f'tone-{tone}')
        if card.find(class_='cv'):
            continue
        p = card.find('p') or card.find(class_='cb')
        if p is None:
            continue
        s = p.get_text()
        m = ARROW_VAL.search(s)
        if m:
            cv = soup.new_tag('div', attrs={'class': ['cv', 'delta']})
            cv.append(BeautifulSoup(f'<span class="from">{m.group(1)}</span><span class="arr">→</span><span class="to">{m.group(2)}</span>', 'html.parser'))
            p.insert_before(cv)
            add_class(p, 'after-cv')
            continue


def flow_steps(soup):
    for ol in soup.find_all('ol'):
        lis = ol.find_all('li', recursive=False)
        if not (3 <= len(lis) <= 5) or ol.find_parent(['nav', 'table']) is not None or 'next-steps' in (ol.get('class') or []):
            continue
        if not all(li.find(['b', 'strong']) is not None and li.get_text(strip=True).startswith(li.find(['b', 'strong']).get_text(strip=True)) for li in lis):
            continue
        add_class(ol, 'flow')
        keys_ok = []
        ol['style'] = f'counter-reset: fl {(int(ol["start"]) if ol.get("start") else 1) - 1}'
        for i, li in enumerate(lis):
            b = li.find(['b', 'strong'])
            b.name = 'b'
            b['class'] = ['fl-t']
            nxt = b.next_sibling
            if isinstance(nxt, NavigableString):
                nxt.replace_with(NavigableString(re.sub(r'^\s*[：:]\s*', '', str(nxt))))
            # the card's focus: the author's own bold phrase in the body, else its closing clause
            key = None
            for kb in li.find_all(['b', 'strong']):
                if kb is not b and len(kb.get_text(strip=True)) >= 2:
                    key = kb.get_text(strip=True)
                    break
            if key is None:
                body = li.get_text().replace(b.get_text(), '', 1).strip().rstrip('。')
                last = re.split(r'[，,；]', body)[-1].strip()
                key = last if 4 <= len(last) <= 16 and '。' not in last else None
            d = soup.new_tag('span', attrs={'class': ['fl-d']})
            for c in list(li.contents):
                if c is not b:
                    d.append(c.extract())
            li.append(d)
            if key and '。' not in key and len(key) <= 18:
                k = soup.new_tag('span', attrs={'class': ['fl-k']})
                k.string = key
                b.insert_after(k)
                keys_ok.append(k)
        # a focus line only reads as a storyline when every step has one
        if len(keys_ok) != len(lis):
            for k in keys_ok:
                k.decompose()



def kv_paragraphs(soup):
    for p in soup.find_all('p'):
        if p.get('class') and {'memo', 'note', 'table-note'} & set(p.get('class')):
            continue
        if p.find_parent(class_=re.compile(r'card|option|fold-h|aside|lede')) is not None or p.find_parent(['td', 'li']) is not None:
            continue
        first = next((c for c in p.contents if not (isinstance(c, NavigableString) and not c.strip())), None)
        if getattr(first, 'name', None) not in ('b', 'strong') or len(p.get_text(strip=True)) < 50:
            continue
        lead = first.extract()
        rest = soup.new_tag('span', attrs={'class': ['kv-v']})
        for c in list(p.contents):
            rest.append(c.extract())
        if rest.contents and isinstance(rest.contents[0], NavigableString):
            rest.contents[0].replace_with(NavigableString(re.sub(r'^\s*[：:]\s*', '', str(rest.contents[0]))))
        k = soup.new_tag('span', attrs={'class': ['kv-k']})
        k.append(lead)
        p.append(k)
        p.append(rest)
        add_class(p, 'kv')


def focus_pass(soup):
    # 1. toggle sub-headings ("▸ 责任与教训") + their content -> titled callout boxes
    for h4 in soup.select('h4.toggle'):
        box = soup.new_tag('div', attrs={'class': ['callout']})
        t = soup.new_tag('div', attrs={'class': ['co-h']})
        t.string = re.sub(r'^\s*▸\s*', '', h4.get_text(strip=True))
        sibs = []
        for sib in list(h4.next_siblings):
            if isinstance(sib, Tag) and (sib.name in ('h2', 'h3', 'h4') or 'fold' in (sib.get('class') or [])):
                break
            sibs.append(sib)
        h4.replace_with(box)
        box.append(t)
        for x in sibs:
            box.append(x.extract())
    # 2. "一句话" summary paragraphs -> summary box
    for p in soup.find_all('p'):
        b = p.find(['b', 'strong'])
        if b is not None and b.get_text(strip=True) == '一句话' and p.get_text(strip=True).startswith('一句话'):
            add_class(p, 'oneline')
            if 'kv' in (p.get('class') or []):
                p['class'] = [c for c in p['class'] if c != 'kv'] 
    # 3. long folds with several sub-sections: an overview strip of the sub-sections and their claims
    for fb in soup.select('.fold-b'):
        h3s = fb.find_all('h3', recursive=False)
        if len(h3s) < 3:
            continue
        items, n_claim = [], 0
        for h in h3s:
            claim = h.find_next_sibling()
            ctext = claim.get_text('', strip=True) if claim is not None and 'claim-box' in (claim.get('class') or []) else ''
            ctext = re.sub(r'^一句话\s*', '', ctext)
            m = re.match(r'^(\d+\.\d)\s*(.*)$', h.get_text(strip=True))
            num, title = (m.group(1), m.group(2)) if m else ('', h.get_text(strip=True))
            title = title.split('：')[0]
            if ctext:
                n_claim += 1
            if h.get('id'):
                items.append((h['id'], num, title, ctext))
            if num:
                h.clear()
                h.append(BeautifulSoup(f'<span class="h3n">{num}</span>{title}' + (('：' + m.group(2).split('：', 1)[1]) if m and '：' in m.group(2) else ''), 'html.parser'))
                add_class(h, 'numbered')
        if items:
            first = h3s[0]
            first.insert_before(BeautifulSoup(_overview_html(items, n_claim), 'html.parser'))


_OV_BAD = r'病根|失手|跑输|太慢|只能|集中|输|少赚|多亏|错|没过|没跑过|没有'
_OV_GOOD_T = r'补|跑赢|复现|更好|过关|提高|赢|学到'
_OV_GOOD_C = r'跑赢|复现|更好|过关|提高|赢|比.{0,6}好'


def _ov_tone(title, claim):
    for src, good in ((title, _OV_GOOD_T), (claim, _OV_GOOD_C)):
        b = re.search(_OV_BAD, src)
        g = re.search(good, re.sub(r'没过关|没跑过|不靠\S{0,3}', '', src))
        if b and g:
            return 'mixed', '成立，但有代价'
        if b:
            return 'bad', '问题'
        if g:
            return 'good', '有效'
    return 'info', '背景'


def _ov_metric(c):
    U = r'(?:%|个百分点|元|只|倍|个点)'
    N = r'[+\-−]?\d[\d.]*(?:\s*[–~]\s*\d[\d.]*)?'
    if c.count('→') >= 1:
        pre = re.findall(rf'({N}\s*{U})', c.split('→')[0])
        post = re.findall(rf'({N}\s*{U})', re.split(r'[。；]', c.split('→')[-1])[0])
        if pre and post:
            return f'{pre[-1]}<i>→</i>{post[-1]}'
    m = re.search(rf'从\s*({N}\s*{U})\s*提高到\s*({N}\s*{U})', c)
    if m:
        return f'{m.group(1)}<i>→</i>{m.group(2)}'
    m = re.search(rf'({N}\s*{U})\s*对(?:基准)?\s*({N}\s*{U})', c)
    if m:
        return f'{m.group(1)}<i>vs</i>{m.group(2)}'
    m = re.search(rf'({N}\s*{U})(?:、{N}\s*{U})+、({N}\s*{U})', c)
    if m:
        return f'{m.group(1)}<i>…</i>{m.group(2)}'
    allu = re.findall(rf'({N}\s*{U})', c)
    if len(allu) == 2 and '涨' in c and '跌' in c:
        return f'{allu[0]}<i>/</i>{allu[1]}'
    return allu[0] if allu else ''


def _ov_claim(c):
    c = re.sub(r'([+\-−]?\d[\d.]*(?:\s*[–~]\s*\d[\d.]*)?\s*(?:%|个百分点|元|只|倍|个点))', r'<span class="num">\1</span>', c)
    c = re.sub(r'“([^”]{1,14})”', r'<span class="ov-q">\1</span>', c)
    return c.replace('→', '<span class="arr">→</span>')


def _overview_html(items, n_claim):
    if n_claim < 2:
        def chip(k, i, t):
            m = re.match(r'^([①-⑳])\s*(.*)$', t)
            lead, t = (m.group(1), m.group(2)) if m else (str(k + 1), t)
            return f'<a class="ov-chip" href="#{i}"><span class="ov-k">{lead}</span>{t}</a>'
        chips = ''.join(chip(k, i, t) for k, (i, n, t, c) in enumerate(items))
        return f'<div class="overview compact"><div class="ov-h">这一段讲了什么 <span>· {len(items)} 节，点击跳转</span></div><div class="ov-chips">{chips}</div></div>'
    cards = []
    for k, (i, n, t, c) in enumerate(items):
        tone, lab = _ov_tone(t, c) if c else ('info', '背景')
        met = _ov_metric(c) if c else ''
        cards.append(
            f'<a class="ov-card t-{tone}{"" if c else " bare"}" href="#{i}"><div class="ov-top"><span class="ov-n">{n or k + 1}</span><span class="ov-tag">{lab}</span></div>'
            + (f'<div class="ov-m">{met}</div>' if met else '')
            + f'<div class="ov-t">{t}</div>'
            + (f'<div class="ov-c">{_ov_claim(c)}</div>' if c else '')
            + '<span class="ov-go">读这一节 ↓</span></a>')
    return (f'<div class="overview"><div class="ov-h">这一段讲了什么 <span>· {len(items)} 节，按顺序读就是一条线；点卡片跳到对应小节</span></div>'
            f'<div class="ov-grid">{"".join(cards)}</div></div>')


def _ab_deco(x):
    x = re.sub(r'“([^”]{1,12})”', lambda m: f'<span class="ab-q{" bad" if re.search("不成立|不过|失败|关闭", m.group(1)) else ""}">{m.group(1)}</span>', x)
    x = re.sub(r'\b(D\d+)\b', r'<span class="ab-id">\1</span>', x)
    x = re.sub(r'(PR #\d+)', r'<span class="ab-id">\1</span>', x)
    return x


def _ab_status(x, who):
    t = re.sub(r'<[^>]+>', '', x)
    if re.search(r'已(写完|补齐|完成|签收)', t):
        return 'done', '已完成'
    if re.search(r'你定了|你批准|你确认', t):
        return 'wait', '等你拍板'
    if '照常' in t:
        return 'ongoing', '持续'
    if '封板后' in who:
        return 'later', '排队'
    return 'todo', '待做'


def action_board(soup):
    for ol in soup.select('ol.next-steps, ul.next-steps'):
        mine, others = [], []
        cnt = {'me': 0, 'done': 0, 'wait': 0, 'todo': 0, 'ongoing': 0, 'later': 0}
        for li in ol.find_all('li', recursive=False):
            b = li.find(['b', 'strong'])
            if b is None:
                return
            who = b.get_text(strip=True)
            b.extract()
            h = li.decode_contents().strip()
            h = re.sub(r'^\s*[：:]\s*', '', h)
            parts = [x.strip() for x in re.split(r'；(?![^<]*>)', h) if x.strip()]
            if who in ('你', 'Owner'):
                for i, x in enumerate(parts, 1):
                    cnt['me'] += 1
                    m = re.match(r'^(确认|批准|定下一步|决定|定|选)(.*)$', x)
                    verb, rest = (m.group(1), m.group(2)) if m else ('', x)
                    rest = rest.rstrip('。')
                    opts = re.match(r'^(.*?)（(.+?)，或(.+?)）$', rest)
                    if opts:
                        body = (f'<div class="ab-obj">{_ab_deco(opts.group(1))}</div>'
                                f'<div class="ab-opts"><span class="ab-opt">{opts.group(2)}</span><span class="ab-or">或</span><span class="ab-opt">{opts.group(3)}</span></div>')
                    else:
                        body = f'<div class="ab-obj">{_ab_deco(rest)}</div>'
                    mine.append(f'<div class="ab-dec"><div class="ab-dn">{i}</div>' + (f'<div class="ab-verb">{verb}</div>' if verb else '') + f'{body}</div>')
            else:
                items = []
                for x in parts:
                    st, lab = _ab_status(x, who)
                    cnt[st] += 1
                    items.append(f'<li class="st-{st}"><span class="ab-st">{lab}</span><span class="ab-tx">{_ab_deco(x.rstrip("。"))}</span></li>')
                others.append(f'<div class="ab-card"><div class="ab-who"><span class="ab-av">{who[:1]}</span><b>{who}</b><span class="ab-n">{len(parts)}</span></div><ul class="ab-items">{"".join(items)}</ul></div>')
        strip = ''.join(f'<span class="ab-s s-{k}"><b>{cnt[k]}</b>{lab}</span>' for k, lab in
                        [('me', '待你拍板'), ('wait', '等你之后'), ('todo', '待做'), ('done', '已完成'), ('ongoing', '持续'), ('later', '封板后排队')] if cnt[k])
        html = (f'<div class="actboard"><div class="ab-strip">{strip}</div>'
                + (f'<div class="ab-mine"><div class="ab-mh"><span class="ab-av">你</span><b>需要你拍板</b>' + (f'<span class="ab-mhint">这 {cnt["me"]} 件定了，下面标着“等你拍板”的事才能动</span>' if cnt['wait'] else '') + f'</div><div class="ab-decs">{"".join(mine)}</div></div>' if mine else '')
                + f'<div class="ab-grid">{"".join(others)}</div></div>')
        ol.replace_with(BeautifulSoup(html, 'html.parser'))


def risk_table(soup):
    """Risk tables: the author's bold rows are the risks that materialised (the section memo says so);
    tag them, give the effect column a severity tag, and drop blanket bold from the handling column."""
    for t in soup.find_all('table'):
        heads = [txt(th) for th in t.find_all('th')]
        if not heads or heads[0] != '风险':
            continue
        add_class(t, 'risk')
        for tr in t.select('tbody tr'):
            tds = tr.find_all('td')
            if len(tds) < 3:
                continue
            hit = tds[0].find(['strong', 'b']) is not None
            add_class(tr, 'risk-hit' if hit else 'risk-watch')
            if hit:
                tg = soup.new_tag('span', attrs={'class': ['pill', 'bad']}); tg.string = '已应验'
                tds[0].append(tg)
            # handling column: unwrap blanket bold, bold only the first clause
            for b in tds[2].find_all(['b', 'strong']):
                b.unwrap()
            h = tds[2].decode_contents().strip()
            parts = re.split(r'(；)', h, maxsplit=1)
            done = re.search(r'已(补齐|关闭|完成)|已经', re.sub(r'<[^>]+>', '', h))
            icon = '<span class="rk-i done">✓</span>' if done else '<span class="rk-i">→</span>'
            tds[2].clear()
            tds[2].append(BeautifulSoup(icon + f'<b>{parts[0]}</b>' + ''.join(parts[1:]), 'html.parser'))
            # effect column: unwrap blanket bold when not the author's highlight
            if not hit:
                for b in tds[1].find_all(['b', 'strong']):
                    b.unwrap()


def _dl_item(x):
    """Render one decided rule with a semantic icon; wording is kept verbatim."""
    plain = BeautifulSoup(x, 'html.parser').get_text()
    kind, body = 'rule', x
    m = re.match(r'^(.*?)，(不用|不再)(.+)$', x)
    if m:
        kind = 'swap'
        body = f'{m.group(1)}<span class="dl-not">，{m.group(2)}<del>{m.group(3)}</del></span>'
    elif '改为' in plain:
        kind = 'change'
        a, b = x.split('改为', 1)
        body = f'{a}<span class="dl-arrow">改为</span><span class="dl-new">{b}</span>'
    elif re.search(r'只有.+能', plain):
        kind = 'outcome'
        body = re.sub(r'(只有)(.+?)(能入围)', r'\1<span class="dl-win">\2</span>\3', x)
    elif re.search(r'(不论|不切换|不只|只上|只持|只跑|推迟)', plain):
        kind = 'guard'
    body = re.sub(r'“([^”]{1,16})”', r'<span class="dl-q">\1</span>', body)
    lab = {'rule': '规则', 'swap': '替换', 'change': '改动', 'outcome': '结果', 'guard': '约束'}[kind]
    return f'<div class="dl-c k-{kind}"><span class="dl-ic" title="{lab}"></span><span class="dl-tx">{body}</span></div>', kind


def decision_log(soup):
    for t in soup.find_all('table'):
        heads = [txt(th) for th in t.find_all('th')]
        if heads[:2] != ['决定', '内容']:
            continue
        rows, track = [], []
        total = {'rule': 0, 'swap': 0, 'change': 0, 'outcome': 0, 'guard': 0}
        for i, tr in enumerate(t.select('tbody tr')):
            tds = tr.find_all('td')
            if len(tds) < 2:
                continue
            name = tds[0].get_text(' ', strip=True)
            m = re.match(r"^(D\d+(?:\s*[–\-]\s*D?\d+)?)\s*(.*)$", name)
            did, title = (m.group(1), m.group(2)) if m else ('', name)
            h = tds[1].decode_contents().strip()
            parts = [x.strip() for x in re.split(r'[；。](?![^<]*>)', h) if x.strip()]
            head, rest = parts[0], parts[1:]
            m2 = re.match(r'^([^：<]{2,12})：(.*)$', head)
            if m2:
                head, rest = m2.group(1), [m2.group(2)] + rest
            items = []
            for x in rest:
                html, kind = _dl_item(x)
                total[kind] += 1
                items.append(html)
            n = len(items) + 1
            key = int(re.findall(r'\d+', did)[-1]) if did else 0
            anchor = f'dl-{key}'
            track.append((int(re.findall(r'\d+', did)[0]) if did else 0, did, title, anchor))
            rows.append(
                f'<div class="dl-row" id="{anchor}">'
                f'<div class="dl-side"><div class="dl-id">{did}</div><div class="dl-t">{title}</div>'
                f'<div class="dl-cnt"><b>{n}</b> 条</div></div>'
                f'<div class="dl-b"><div class="dl-h">{head}</div>'
                + (f'<div class="dl-items">{"".join(items)}</div>' if items else '')
                + '</div></div>')
        track.sort()
        if track:
            last = track[-1][3]
            rows = [r.replace(f'<div class="dl-row" id="{last}">', f'<div class="dl-row latest" id="{last}">') for r in rows]
        tr_html = ''.join(f'<a class="dl-tk" href="#{a}"><span class="dl-tk-id">{d}</span><span class="dl-tk-t">{tt}</span></a>' for _, d, tt, a in track)
        legend = ''.join(
            f'<span class="dl-lg k-{k}"><span class="dl-ic"></span>{lab}</span>'
            for k, lab in [('rule', '规则'), ('guard', '约束'), ('swap', '替换旧做法'), ('change', '改动'), ('outcome', '结果')] if total[k])
        block = (f'<div class="declog decision"><div class="dl-track">{tr_html}</div>'
                 f'<div class="dl-legend">{legend}</div>' + ''.join(rows) + '</div>')
        table_wrap(t).replace_with(BeautifulSoup(block, 'html.parser'))


def status_hero(soup):
    """Board top: vision + 工程进度/业务结论/需要你 cards -> a verdict-first hero. Text kept verbatim."""
    sec = soup.select_one('section.intro')
    if sec is None:
        return
    cards = {c.select_one('.ct').get_text(strip=True): c.select_one('.cb') for c in sec.select('.cards .card') if c.select_one('.ct') and c.select_one('.cb')}
    if set(cards) != {'工程进度', '业务结论', '需要你'}:
        return generic_hero(soup, sec, cards)
    eng = cards['工程进度'].get_text('', strip=True)
    biz = cards['业务结论'].get_text('', strip=True)
    need = cards['需要你'].get_text('', strip=True)
    m = re.match(r'^(.*?)(\d{4}–\d{4})\s*年化\s*([\d.]+%)，基准\s*([\d.]+%)；(.*?)(\d+)\s*个起点\s*(\d+)\s*个\s*跑赢。(.*?)，(.*)$', biz)
    m2 = re.match(r'^(.*?)：(.*?)。(见.*)$', need)
    m3 = re.match(r'^(.*?。)(.*)$', eng)
    if not (m and m2 and m3):
        return
    name, yrs, a, b, hold, n, k, verdict, tail = m.groups()
    fa, fb = float(a[:-1]), float(b[:-1])
    mx = max(fa, fb)
    dots = ''.join(f'<i class="{"w" if j < int(k) else ""}"></i>' for j in range(int(n)))
    asks = [x.strip() for x in m2.group(2).split('；') if x.strip()]
    asks_html = ''.join(f'<li><span class="hq-n">{j}</span><span>{_ab_deco(x)}</span></li>' for j, x in enumerate(asks, 1))
    ref = m2.group(3)
    ref_a = sec.find('a') 
    vp = next((q for q in sec.find_all('p') if q.get_text(strip=True).startswith('项目愿景')), None)
    vtext = re.sub(r'^项目愿景[\s\u3000]*', '', vp.get_text('', strip=True)) if vp else ''
    vm = re.match(r'^(.*?)，获得(.*?)、(.*?)，同时(.*?)。$', vtext)
    if vm:
        vision = (f'<div class="hv"><span class="hv-k">项目愿景</span><span class="hv-t">{vm.group(1)}，</span>'
                  f'<span class="hv-goal">获得{vm.group(2)}</span><span class="hv-sep">、</span><span class="hv-goal">{vm.group(3)}</span>'
                  f'<span class="hv-sep">，同时</span><span class="hv-goal">{vm.group(4)}</span>。</div>')
    else:
        vision = f'<div class="hv"><span class="hv-k">项目愿景</span><span class="hv-t">{vtext}</span></div>'
    html = (
        '<div class="hero">' + vision +
        '<div class="hero-g">'
        f'<div class="hz verdict"><div class="hz-l">业务结论</div>'
        f'<div class="hz-v"><span class="hz-x">✕</span>{verdict}<span class="hz-s">，{tail}</span></div>'
        f'<div class="hz-cmp"><div class="hz-cap">{name.strip()} {yrs} 年化</div>'
        f'<div class="hb"><span class="hb-k">{name.strip()}</span><span class="hb-bar"><b class="bad" style="width:{fa / mx * 100:.0f}%"></b></span><span class="hb-v bad">{a}</span></div>'
        f'<div class="hb"><span class="hb-k">基准</span><span class="hb-bar"><b style="width:{fb / mx * 100:.0f}%"></b></span><span class="hb-v">{b}</span></div>'
        f'<div class="hz-gap">每年少 <b>{fb - fa:.1f}</b> 个点</div></div>'
        f'<div class="hz-dots"><div class="hz-cap">{hold}<b>{n} 个起点 {k} 个</b>跑赢</div><div class="dots">{dots}</div></div>'
        '</div>'
        f'<div class="hz ask"><div class="hz-l">需要你</div><div class="hq-h">{m2.group(1)}</div><ol class="hq">{asks_html}</ol><div class="hq-ref">{ref}</div></div>'
        f'<div class="hz eng"><span class="eng-ok">✓</span><span class="hz-l">工程进度</span><b>{m3.group(1)}</b><span class="eng-d">{m3.group(2)}</span></div>'
        '</div></div>')
    for x in list(sec.children):
        if getattr(x, 'name', None) in ('p', 'div'):
            x.extract()
    sec.insert(0, BeautifulSoup(html, 'html.parser'))



_TF_LOWER = re.compile(r'回撤|波动|换手|跟跌|下跌月份|亏|成本|闲置|现金')
_TF_ROLE = [
    ('concl', re.compile(r'^(本该得出的结论|结论|判定|读法|结果|对了吗|意味着什么|学到|当时的推论)')),
    ('cost', re.compile(r'(代价|反面证据|超出就要查|风险)')),
    ('why', re.compile(r'^(为什么|证据|依据|做了什么|怎么做|在担心什么|已试|影响|规则会怎么动)')),
    ('status', re.compile(r'^(状态|可信度)')),
]


def _tf_num(t):
    m = re.match(r'^\s*约?\s*([+\-−]?\d+(?:\.\d+)?)\s*(%|次|个点)?', t)
    return float(m.group(1).replace('−', '-')) if m else None


def _tf_status_tone(t):
    if re.search(r'已(修|补齐|完成|签收|合并|上线|定)|完成|✅|强|硬', t):
        return 'good'
    if re.search(r'不再|放弃|弱|没有|无|won.t', t):
        return 'bad'
    if re.search(r'待|未|进行|中|跟踪|一般', t):
        return 'warn'
    return 'info'


def table_focus(soup):
    """Give every non-reference table a visual focus, using only what the table itself says."""
    for t in soup.find_all('table'):
        heads = P.leaf_heads(t)
        H = [h.get_text('', strip=True) for h in heads]
        rows = [tr for tr in t.select('tbody tr') if 'grp' not in (tr.get('class') or [])]
        if not rows or len(H) < 2:
            continue
        grid = [tr.find_all('td') for tr in rows]
        # A. compare with the 基准 column (green = better than 基准, orange = worse)
        bi = next((i for i, h in enumerate(H) if i > 0 and h.startswith('基准')), None)
        if bi is not None:
            for r in grid:
                if len(r) != len(H):
                    continue
                name = r[0].get_text('', strip=True)
                bv = _tf_num(r[bi].get_text('', strip=True))
                if bv is None:
                    continue
                lower = bool(_TF_LOWER.search(name))
                for ci, td in enumerate(r):
                    if ci in (0, bi) or set(td.get('class') or []) & {'mgc', 'ibc'}:
                        continue
                    v = _tf_num(td.get_text('', strip=True))
                    if v is None or v == bv:
                        continue
                    better = (abs(v) < abs(bv)) if lower else (v > bv)
                    add_class(td, 'vs-good' if better else 'vs-bad')
                    td['title'] = f'对基准 {r[bi].get_text("", strip=True)}：' + ('更好' if better else '更差')
            add_class(t, 'vs-base')
        # A2. share of winning start points vs the 60% expectation line drawn in the same section's chart
        for ci, h in enumerate(H):
            if '跑赢的起点' not in h:
                continue
            root = t.find_parents()[-1] if t.find_parents() else t
            if not re.search(r'期望', root.get_text()) or not re.search(r'≥\s*60%', root.get_text()):
                continue
            for r in grid:
                if ci < len(r):
                    v = _tf_num(r[ci].get_text('', strip=True))
                    if v is not None:
                        add_class(r[ci], 'exp-ok' if v >= 60 else 'exp-no')
            if 'has-exp' not in (t.get('class') or []):
                add_class(t, 'has-exp')
                wrap = t.find_parent(class_='table-wrap') or t
                wrap.insert_before(BeautifulSoup('<p class="exp-key"><span class="ek ok">≥ 60%</span><span class="ek no">&lt; 60%</span>跑赢的起点按期望线 60% 上色（期望线见上图和“期望”一节）</p>', 'html.parser'))
        # A3. signed differences (中位/最差/超额…) that no earlier pass styled: colour by sign
        for ci, h in enumerate(H):
            if ci == 0 or not re.search(r'中位|最差|最好|超额|合计|相对|多赚|差值', h):
                continue
            for r in grid:
                if ci < len(r) and not set(r[ci].get('class') or []) & {'ibc', 'mgc', 'vs-good', 'vs-bad'}:
                    tx = r[ci].get_text('', strip=True)
                    if re.match(r'^[+\-−]\d', tx):
                        add_class(r[ci], 'sg-pos' if tx[0] == '+' else 'sg-neg')
        # C. column roles from the header wording
        for ci, h in enumerate(H):
            if ci == 0:
                continue
            role = next((k for k, rx in _TF_ROLE if rx.search(h)), None)
            if role is None:
                continue
            if role == 'concl' and ci != len(H) - 1 and not h.startswith('本该'):
                continue
            for r in grid:
                if ci < len(r) and not set(r[ci].get('class') or []) & {'mgc', 'ibc', 'c-take'}:
                    td = r[ci]
                    if role == 'status' and not td.find(class_='pill'):
                        txt_ = td.get_text('', strip=True)
                        if 0 < len(txt_) <= 20:
                            td.clear()
                            td.append(BeautifulSoup(f'<span class="pill {_tf_status_tone(txt_)}">{txt_}</span>', 'html.parser'))
                        else:
                            first = re.split(r'[，；：（(]', txt_)[0]
                            if 0 < len(first) <= 10 and td.contents and isinstance(td.contents[0], str) and td.contents[0].startswith(first):
                                td.contents[0].replace_with(td.contents[0][len(first):])
                                td.insert(0, BeautifulSoup(f'<span class="pill {_tf_status_tone(first)}">{first}</span> ', 'html.parser'))
                    add_class(td, f'r-{role}')
            if ci < len(heads):
                add_class(heads[ci], f'rh-{role}')
        # old -> new version columns
        vi = [i for i, h in enumerate(H) if re.match(r'^(第\s*[\d.]+\s*版|上一轮|这次|原规则|新规则)', h)]
        if len(vi) == 2:
            for r in grid:
                if len(r) > vi[1]:
                    add_class(r[vi[0]], 'r-old'); add_class(r[vi[1]], 'r-new')
            add_class(heads[vi[0]], 'rh-old'); add_class(heads[vi[1]], 'rh-new')
        # D. letter / circled-number row ids glued to the label
        for r in grid:
            td = r[0]
            first = td.contents[0] if td.contents else None
            if isinstance(first, str):
                m = re.match(r'^\s*([a-z]|[①-⑳])(?=\S)', first)
                if m and not re.match(r'^[a-z]{2}', first.strip()):
                    first.replace_with(first[m.end():])
                    td.insert(0, BeautifulSoup(f'<span class="rid">{m.group(1)}</span>', 'html.parser'))
        # E. short categorical columns -> chips
        for ci, h in enumerate(H):
            if ci == 0:
                continue
            vals = [r[ci].get_text('', strip=True) for r in grid if ci < len(r)]
            uniq = set(v for v in vals if v)
            if len(vals) >= 4 and 2 <= len(uniq) <= 4 and all(len(v) <= 5 for v in uniq) and not any(re.search(r'\d', v) for v in uniq):
                order = sorted(uniq, key=vals.index)
                for r in grid:
                    if ci < len(r) and r[ci].get_text(strip=True) and not r[ci].find(class_='pill'):
                        v = r[ci].get_text('', strip=True)
                        r[ci].clear()
                        r[ci].append(BeautifulSoup(f'<span class="cat c{order.index(v)}">{v}</span>', 'html.parser'))
        # G. yes/no answers in a question column (“会不会…”) -> tag
        qi = len(H) - 1
        if re.search(r'(会不会|是不是|有没有|能不能)', H[qi]):
            neg_q = re.search(r'慢|错|差|亏|输|坏|失', H[qi])
            for r in grid:
                if qi >= len(r):
                    continue
                td = r[qi]
                b = td.find(['strong', 'b'])
                if b is None or td.contents[0] is not b:
                    continue
                w = b.get_text(strip=True)
                if len(w) > 4:
                    continue
                no = w.startswith(('不', '没', '否'))
                tone = ('good' if no else 'bad') if neg_q else 'info'
                b.replace_with(BeautifulSoup(f'<span class="pill {tone}">{w}</span>', 'html.parser'))
        # F. 同上 -> repeat the verdict above, quietly
        for ci in range(1, len(H)):
            prev = None
            for r in grid:
                if ci >= len(r):
                    continue
                td = r[ci]
                pl = td.find(class_='pill')
                if pl is not None:
                    prev = pl
                elif td.get_text(strip=True) == '同上' and prev is not None:
                    td.clear()
                    td.append(BeautifulSoup(f'<span class="{" ".join(prev.get("class"))} ditto">{prev.get_text(strip=True)}</span><span class="pill-note">同上</span>', 'html.parser'))



def case_cards(soup):
    """A run of 'X：claim' one-liners, each followed by prose, reads as cases: one card per case."""
    def is_head(p):
        if p is None or p.name != 'p' or p.get('class'):
            return False
        t = p.get_text('', strip=True)
        return 6 <= len(t) <= 34 and '：' in t and p.find(['strong', 'b', 'img']) is None and not t.endswith('。')
    for p in list(soup.find_all('p')):
        if p.parent is None or not is_head(p):
            continue
        heads = [p]
        nxt = p.find_next_sibling()
        # collect this case's body, then look for more case heads
        groups = []
        cur = p
        while cur is not None and is_head(cur):
            body = []
            sib = cur.find_next_sibling()
            while sib is not None and sib.name in ('p', 'ul', 'ol') and not is_head(sib) and 'memo' not in (sib.get('class') or []):
                body.append(sib)
                sib = sib.find_next_sibling()
            groups.append((cur, body))
            cur = sib
        if len(groups) < 2 or not all(b for _, b in groups):
            continue
        wrap = soup.new_tag('div', attrs={'class': ['cases']})
        groups[0][0].insert_before(wrap)
        for h, body in groups:
            who, claim = h.get_text('', strip=True).split('：', 1)
            tone = 'bad' if re.search(r'砸|输|亏|没|慢', claim) else ('good' if re.search(r'躲开|好看|赢', claim) else 'info')
            card = BeautifulSoup(f'<div class="case t-{tone}"><div class="case-h"><span class="case-who">{who}</span><span class="case-c">{claim}</span></div><div class="case-b"></div></div>', 'html.parser')
            cb = card.select_one('.case-b')
            for b in body:
                cb.append(b.extract())
            h.decompose()
            wrap.append(card)


def inline_bullets(soup):
    """Source list items that carry ' * ' sub-points on one line -> nested list."""
    for li in soup.find_all('li'):
        html = li.decode_contents()
        if ' * ' not in html:
            continue
        head, *subs = [x.strip() for x in html.split(' * ')]
        if len(subs) < 2:
            continue
        li.clear()
        def sub(x):
            m = re.match(r'^([^：<]{2,16})：(.*)$', x)
            return f'<div class="sp"><b>{m.group(1)}</b>：{m.group(2)}</div>' if m else f'<div class="sp">{x}</div>'
        li.append(BeautifulSoup(head + '<div class="subpts">' + ''.join(sub(x) for x in subs) + '</div>', 'html.parser'))



def generic_hero(soup, sec, cards):
    if '需要你' not in cards or len(cards) != 3:
        return
    ck = '结论' if '结论' in cards else next(k for k in cards if k != '需要你')
    concl = cards[ck].decode_contents()
    need_el = cards['需要你']
    need = need_el.get_text('', strip=True)
    others = [(k, v) for k, v in cards.items() if k not in (ck, '需要你')]
    m = re.match(r'^(不用操作|暂时不需要)[。，]?(.*)$', need)
    m2 = re.match(r'^(.{2,8})：(.*?)。(.*)$', need)
    if m:
        ask = f'<div class="hz ask calm"><div class="hz-l">需要你</div><div class="hq-h calm">✓ {m.group(1)}</div>' + (f'<div class="hq-ref">{m.group(2)}</div>' if m.group(2) else '') + '</div>'
    elif m2 and '；' in m2.group(2):
        asks = [x for x in m2.group(2).split('；') if x]
        items = ''.join(f'<li><span class="hq-n">{j}</span><span>{_ab_deco(x)}</span></li>' for j, x in enumerate(asks, 1))
        ask = f'<div class="hz ask"><div class="hz-l">需要你</div><div class="hq-h">{m2.group(1)}</div><ol class="hq">{items}</ol><div class="hq-ref">{m2.group(3)}</div></div>'
    else:
        ask = f'<div class="hz ask"><div class="hz-l">需要你</div><div class="hq-b">{need_el.decode_contents()}</div></div>'
    # conclusion: first sentence is the headline, the rest is evidence
    ctext = cards[ck]
    parts = re.split(r'(?<=。)', concl, maxsplit=1)
    head, rest = (parts[0], parts[1]) if len(parts) == 2 and parts[1].strip() else (concl, '')
    tone = 'bad' if re.search(r'不通过|不入围|没过|跑输|输|只有', ctext.get_text()) else 'info'
    eng = ''.join(f'<div class="hz eng"><span class="eng-ok">✓</span><span class="hz-l">{k}</span><span class="eng-d">{v.decode_contents()}</span></div>' for k, v in others)
    html = (f'<div class="hero"><div class="hero-g n{len(others)}">'
            f'<div class="hz verdict2 t-{tone}"><div class="hz-l">{ck}</div><div class="hz-hd">{head}</div>' + (f'<div class="hz-rest">{rest}</div>' if rest else '') + '</div>'
            + ask + eng + '</div></div>')
    sec.select_one('.cards.status').replace_with(BeautifulSoup(html, 'html.parser'))


def ux_pass(html):
    soup = BeautifulSoup(html, 'html.parser')
    status_hero(soup)
    inline_bullets(soup)
    case_cards(soup)
    card_ux(soup)
    flow_steps(soup)
    kv_paragraphs(soup)
    focus_pass(soup)
    action_board(soup)
    risk_table(soup)
    decision_log(soup)
    table_focus(soup)
    for el in soup.select('p, li, .cb, .od, .dl-tx, .dl-h'):
        if el.find_parent(['table', 'nav', 'footer']) is not None or el.find_parent(class_='fold-h') is not None:
            continue
        if el.find_parent('li') is not None and el.name == 'p':
            continue
        mark_numbers(soup, el)
    for b in soup.select('main strong, main b, strong, b'):
        if b.find_parent(['table', 'nav']) is not None:
            continue
        if re.fullmatch(r'[+\-−]?[\d.,]+(?:\s*[–~]\s*[+\-−]?[\d.,]+)?\s*(%|个点|个百分点|倍|元|pp)?', b.get_text(strip=True)):
            add_class(b, 'num')
    return str(soup)


CSS += r"""
/* UX pass */
span.num, strong.num, b.num { font-family: var(--font-mono); font-size: .93em; font-weight: 500; color: var(--ink); background: color-mix(in srgb, var(--accent) 9%, transparent); border-radius: 4px; padding: 0 4px; white-space: nowrap; }
p.memo span.num { background: none; color: var(--accent); padding: 0; }
span.arr { color: var(--accent); font-weight: 700; padding: 0 2px; }
.cards .card { position: relative; border-top: 3px solid var(--accent); transition: transform .12s, box-shadow .12s; }
.cards .card:hover { transform: translateY(-2px); box-shadow: 0 6px 18px rgba(20, 30, 50, .08); }
.cards .card.tone-good { border-top-color: var(--good); } .cards .card.tone-bad { border-top-color: var(--bad); }
.cards .card .ct { font-size: 13px; letter-spacing: .02em; }
.cards .card.tone-good .ct { color: var(--good); } .cards .card.tone-bad .ct { color: var(--bad); } .cards .card.tone-info .ct { color: var(--accent); }
.cards .card .cv { font-size: 24px; line-height: 1.2; margin: 2px 0 4px; color: var(--ink); }
.cards .card .cv.delta .from { color: var(--muted); font-size: 18px; }
.cards .card .cv.delta .to { font-weight: 700; }
.cards .card.tone-good .cv .to { color: var(--good); } .cards .card.tone-bad .cv .to { color: var(--bad); }
.cards .card .cv.echo { color: var(--accent); }
.cards .card p { font-size: 14.5px; }
ol.flow { list-style: none; padding: 0; display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 22px; margin: 14px 0 22px; counter-reset: none; }
ol.flow > li { position: relative; background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 14px 14px 12px; margin: 0; font-size: 14px; line-height: 1.65; color: var(--muted); }
ol.flow > li { counter-increment: fl; }
ol.flow > li::before { content: counter(fl); display: grid; place-items: center; width: 24px; height: 24px; border-radius: 50%; background: var(--accent); color: #fff; font-family: var(--font-mono); font-size: 12.5px; margin-bottom: 6px; position: static; }
ol.flow > li:not(:last-child)::after { content: '→'; position: absolute; right: -18px; top: 50%; transform: translateY(-50%); color: var(--accent); font-weight: 700; }
ol.flow .fl-n { display: inline-grid; place-items: center; width: 24px; height: 24px; border-radius: 50%; background: var(--accent); color: #fff; font-family: var(--font-mono); font-size: 12.5px; margin-bottom: 6px; }
ol.flow .fl-t { display: block; font-weight: 700; color: var(--ink); font-size: 15px; margin-bottom: 4px; }
p.kv { display: grid; grid-template-columns: 11em minmax(0, 1fr); gap: 16px; padding: 10px 0; border-top: 1px solid var(--line); margin: 0; }
p.kv + :not(p.kv) { margin-top: 14px; }
p.kv .kv-k { font-weight: 700; color: var(--ink); }
p.kv .kv-k::before { content: ''; display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: var(--accent); margin-right: 8px; vertical-align: 2px; }
@media (max-width: 1000px) { p.kv { grid-template-columns: minmax(0, 1fr); gap: 2px; } ol.flow > li::after { display: none; } }
"""

CSS += r"""
.readnote { margin: -6px 0 22px; padding: 10px 14px; border-radius: 10px; background: var(--bg); border: 1px dashed var(--line); display: grid; gap: 4px; }
.readnote .rn-h { font-size: 12px; font-weight: 700; color: var(--muted); letter-spacing: .06em; margin-bottom: 2px; }
.readnote .rn-i { font-size: 13.5px; color: var(--muted); line-height: 1.6; padding-left: 14px; position: relative; }
.readnote .rn-i::before { content: ''; position: absolute; left: 2px; top: .65em; width: 5px; height: 5px; border-radius: 50%; background: var(--line); }
.readnote .rn-i:first-of-type { color: var(--ink); font-weight: 500; }
.readnote span.num { background: none; padding: 0; color: var(--ink); }
"""

CSS += r"""
/* focus pass */
.claim-box { font-weight: 700; font-size: 16px; border-left: 4px solid var(--accent); background: var(--surface); padding: 10px 14px; border-radius: 0 8px 8px 0; margin: 0 0 14px; }
.fold-b .claim-box { background: var(--accent-soft); }
.callout { background: var(--surface); border: 1px solid var(--line); border-left: 4px solid var(--warn); border-radius: 0 10px 10px 0; padding: 12px 16px; margin: 14px 0 20px; }
.callout .co-h { font-weight: 700; color: var(--warn); font-size: 14.5px; margin-bottom: 6px; }
.callout > p:last-child, .callout > ul:last-child { margin-bottom: 0; }
p.oneline { background: var(--accent-soft); border-radius: 10px; padding: 12px 16px; font-size: 15.5px; }
p.oneline > b:first-child, p.oneline > strong:first-child { display: inline-block; background: var(--accent); color: #fff; border-radius: 4px; padding: 0 8px; margin-right: 8px; font-size: 13px; }
.overview { margin: 8px 0 26px; padding: 14px; background: var(--bg); border-radius: 12px; border: 1px solid var(--line); }
.overview .ov-h { font-size: 13px; font-weight: 700; color: var(--ink); margin-bottom: 10px; }
.overview .ov-h span { font-weight: 400; color: var(--muted); }
.ov-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 10px; counter-reset: ov; }
.ov-card { position: relative; display: flex; flex-direction: column; gap: 4px; background: var(--surface); border: 1px solid var(--line); border-top: 3px solid var(--accent); border-radius: 10px; padding: 10px 12px 28px; color: var(--ink); text-decoration: none; transition: transform .12s, box-shadow .12s; }
.ov-card:hover { transform: translateY(-2px); box-shadow: 0 6px 18px rgba(20, 30, 50, .08); text-decoration: none; }
.ov-card.t-bad { border-top-color: var(--bad); } .ov-card.t-good { border-top-color: var(--good); } .ov-card.t-mixed { border-top-color: #b45309; } .ov-card.t-info { border-top-color: var(--muted); }
.ov-top { display: flex; align-items: center; gap: 8px; }
.ov-card .ov-n { font-family: var(--font-mono); font-size: 12.5px; font-weight: 600; color: var(--accent); background: var(--accent-soft); border-radius: 5px; padding: 0 6px; }
.ov-tag { font-size: 11.5px; font-weight: 700; border-radius: 4px; padding: 0 6px; color: var(--muted); background: var(--bg); }
.t-bad .ov-tag { color: var(--bad); background: color-mix(in srgb, var(--bad) 10%, transparent); }
.t-good .ov-tag { color: var(--good); background: color-mix(in srgb, var(--good) 10%, transparent); }
.t-mixed .ov-tag { color: #b45309; background: color-mix(in srgb, #b45309 10%, transparent); }
.ov-m { font-family: var(--font-mono); font-size: 21px; font-weight: 700; line-height: 1.25; margin-top: 4px; color: var(--ink); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.ov-m i { font-style: normal; font-size: 14px; color: var(--muted); margin: 0 6px; font-family: var(--font-sans, inherit); }
.t-bad .ov-m { color: var(--bad); } .t-good .ov-m { color: var(--good); } .t-mixed .ov-m { color: #b45309; }
.ov-card .ov-t { font-weight: 700; font-size: 15px; line-height: 1.4; }
.ov-card .ov-c { font-size: 13.5px; line-height: 1.6; color: var(--muted); }
.ov-card .ov-c .num { color: var(--ink); }
.ov-q { color: var(--ink); font-weight: 600; }
.ov-card.bare { border-top-style: dashed; background: transparent; }
.ov-card.bare .ov-tag { display: none; }
.ov-go { position: absolute; left: 12px; bottom: 8px; font-size: 12px; color: var(--accent); opacity: 0; transition: opacity .12s; }
.ov-card:hover .ov-go { opacity: 1; }
.ov-chips { display: flex; flex-wrap: wrap; gap: 8px; }
.ov-chip { display: inline-flex; align-items: center; gap: 8px; background: var(--surface); border: 1px solid var(--line); border-radius: 999px; padding: 4px 14px 4px 4px; color: var(--ink); font-size: 14px; font-weight: 600; text-decoration: none; }
.ov-chip:hover { border-color: var(--accent); color: var(--accent); text-decoration: none; }
.ov-k { display: inline-grid; place-items: center; width: 22px; height: 22px; border-radius: 50%; background: var(--accent); color: #fff; font-family: var(--font-mono); font-size: 12px; }
"""

CSS += r"""
.actboard { display: grid; gap: 14px; }
.ab-strip { display: flex; flex-wrap: wrap; gap: 8px; }
.ab-s { display: inline-flex; align-items: baseline; gap: 6px; font-size: 13px; color: var(--muted); background: var(--surface); border: 1px solid var(--line); border-radius: 999px; padding: 3px 12px; }
.ab-s b { font-family: var(--font-mono); font-size: 16px; color: var(--ink); }
.ab-s.s-me { background: var(--accent); border-color: var(--accent); color: #fff; } .ab-s.s-me b { color: #fff; }
.ab-s.s-wait b { color: #b45309; } .ab-s.s-done b { color: var(--good); }
.ab-mine { border: 1.5px solid var(--accent); border-radius: 12px; background: linear-gradient(180deg, color-mix(in srgb, var(--accent) 7%, var(--surface)), var(--surface)); padding: 14px 16px 16px; }
.ab-mh { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-bottom: 12px; }
.ab-mh b { font-size: 16px; color: var(--accent); }
.ab-mhint { font-size: 13px; color: var(--muted); }
.ab-decs { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 12px; }
.ab-dec { position: relative; background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 12px 14px 14px 52px; min-height: 52px; }
.ab-dn { position: absolute; left: 14px; top: 14px; width: 26px; height: 26px; border-radius: 50%; display: grid; place-items: center; border: 2px solid var(--accent); color: var(--accent); font-family: var(--font-mono); font-weight: 700; font-size: 13px; }
.ab-verb { font-size: 22px; font-weight: 800; color: var(--accent); line-height: 1.15; letter-spacing: .04em; }
.ab-obj { font-size: 14.5px; line-height: 1.6; color: var(--ink); margin-top: 4px; }
.ab-opts { display: flex; align-items: center; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.ab-opt { font-size: 13.5px; font-weight: 600; border: 1.5px dashed var(--accent); color: var(--accent); border-radius: 8px; padding: 3px 10px; background: var(--accent-soft); }
.ab-or { font-size: 12px; color: var(--muted); font-weight: 700; }
.ab-q { font-weight: 700; color: var(--ink); background: var(--bg); border: 1px solid var(--line); border-radius: 4px; padding: 0 5px; }
.ab-q.bad { color: var(--bad); border-color: transparent; background: color-mix(in srgb, var(--bad) 10%, transparent); }
.ab-id { font-family: var(--font-mono); font-size: 12.5px; color: var(--accent); background: var(--accent-soft); border-radius: 4px; padding: 0 5px; white-space: nowrap; }
.ab-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; }
.ab-card { background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 12px 14px; }
.ab-who { display: flex; align-items: center; gap: 8px; padding-bottom: 8px; margin-bottom: 8px; border-bottom: 1px solid var(--line); }
.ab-who b { font-size: 15px; }
.ab-n { margin-left: auto; font-family: var(--font-mono); font-size: 12px; color: var(--muted); background: var(--bg); border-radius: 999px; padding: 0 8px; }
.ab-av { width: 28px; height: 28px; border-radius: 50%; display: grid; place-items: center; background: var(--line); color: var(--ink); font-weight: 700; font-size: 13px; }
.ab-mh .ab-av { background: var(--accent); color: #fff; }
.ab-items { list-style: none; margin: 0; padding: 0; display: grid; gap: 8px; }
.ab-items li { margin: 0; padding: 0; display: grid; gap: 3px; font-size: 14px; line-height: 1.6; }
.ab-items li::before { display: none; }
.ab-st { justify-self: start; font-size: 11.5px; font-weight: 700; border-radius: 4px; padding: 0 7px; color: var(--muted); background: var(--bg); border: 1px solid var(--line); }
.st-done .ab-st { color: var(--good); border-color: color-mix(in srgb, var(--good) 40%, transparent); background: color-mix(in srgb, var(--good) 10%, transparent); }
.st-done .ab-st::before { content: '✓ '; }
.st-done .ab-tx { color: var(--muted); }
.st-wait .ab-st { color: #b45309; border-color: color-mix(in srgb, #b45309 40%, transparent); background: color-mix(in srgb, #b45309 10%, transparent); }
.st-wait .ab-st::before { content: '⏳ '; }
.st-todo .ab-st { color: var(--accent); border-color: color-mix(in srgb, var(--accent) 40%, transparent); background: var(--accent-soft); }
.st-todo .ab-st::before { content: '→ '; }
.st-ongoing .ab-st::before { content: '↻ '; }
.st-later .ab-tx { color: var(--muted); }
@media (max-width: 1000px) { .ab-decs, .ab-grid { grid-template-columns: minmax(0, 1fr); } }
"""

CSS += r"""
table.risk tr.risk-hit td { background: color-mix(in srgb, var(--bad) 6%, transparent); }
table.risk tr.risk-hit td:first-child { box-shadow: inset 4px 0 0 var(--bad); }
table.risk tr.risk-hit td:first-child .pill { display: table; margin: 6px 0 0; }
table.risk tr.risk-hit td:nth-child(2) strong.c-bad, table.risk tr.risk-hit td:nth-child(2) strong { color: var(--bad); font-size: 15px; }
table.risk tr.risk-watch td { color: var(--muted); }
table.risk tr.risk-watch td:first-child { color: var(--ink); box-shadow: inset 4px 0 0 var(--line); }
table.risk td:nth-child(3) b { color: var(--ink); }
.rk-i { display: inline-grid; place-items: center; width: 18px; height: 18px; border-radius: 50%; background: var(--accent-soft); color: var(--accent); font-size: 11px; font-weight: 700; margin-right: 6px; vertical-align: 1px; }
.rk-i.done { background: var(--good-soft); color: var(--good); }
"""

CSS += r"""
.declog { position: relative; display: grid; gap: 12px; margin: 6px 0 14px; }
.dl-track { display: flex; align-items: stretch; gap: 0; margin: 0 0 4px; padding-top: 8px; counter-reset: none; }
.dl-tk { flex: 1; position: relative; display: grid; gap: 2px; padding: 10px 14px 10px 0; text-decoration: none; color: var(--muted); border-top: 3px solid color-mix(in srgb, var(--accent) 30%, var(--line)); }
.dl-tk::before { content: ''; position: absolute; top: -8px; left: 0; width: 13px; height: 13px; border-radius: 50%; background: var(--surface); border: 3px solid var(--accent); box-sizing: border-box; }
.dl-tk:last-child { border-top-color: var(--accent); }
.dl-tk:last-child::before { background: var(--accent); }
.dl-tk-id { font-family: var(--font-mono); font-size: 12.5px; color: var(--accent); font-weight: 600; }
.dl-tk-t { font-size: 13.5px; color: var(--ink); }
.dl-tk:hover .dl-tk-t { color: var(--accent); text-decoration: underline; }
.dl-legend { display: flex; flex-wrap: wrap; gap: 14px; font-size: 12.5px; color: var(--muted); margin-bottom: 2px; }
.dl-lg { display: inline-flex; align-items: center; gap: 5px; }
.dl-row { position: relative; display: grid; grid-template-columns: 190px minmax(0, 1fr); gap: 20px; background: var(--surface); border: 1px solid var(--line); border-left: 4px solid color-mix(in srgb, var(--accent) 35%, var(--line)); border-radius: 10px; padding: 14px 18px; scroll-margin-top: 80px; transition: box-shadow .12s; }
.dl-row:hover { box-shadow: 0 6px 18px rgba(20, 30, 50, .07); }
.dl-row:target { box-shadow: 0 0 0 2px var(--accent); }
.dl-row.latest { border-left-color: var(--accent); background: linear-gradient(90deg, var(--accent-soft), var(--surface) 40%); }
.dl-row.latest .dl-side::after { content: '最新'; display: inline-block; margin-top: 6px; font-size: 11.5px; font-weight: 700; color: #fff; background: var(--accent); border-radius: 4px; padding: 1px 7px; }
.dl-side { display: flex; flex-direction: column; align-items: flex-start; gap: 4px; border-right: 1px dashed var(--line); padding-right: 14px; }
.dl-id { font-family: var(--font-mono); font-size: 13px; font-weight: 600; color: var(--accent); background: var(--accent-soft); border-radius: 6px; padding: 2px 8px; white-space: nowrap; }
.dl-t { font-weight: 700; font-size: 15.5px; color: var(--ink); line-height: 1.4; }
.dl-cnt { font-size: 12.5px; color: var(--muted); }
.dl-cnt b { font-family: var(--font-mono); color: var(--ink); }
.dl-h { font-size: 19px; font-weight: 700; color: var(--accent); line-height: 1.45; padding-bottom: 8px; margin-bottom: 8px; border-bottom: 1px solid var(--line); }
.dl-items { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 8px 22px; }
.dl-c { display: grid; grid-template-columns: 20px minmax(0, 1fr); gap: 8px; align-items: start; font-size: 14.5px; line-height: 1.6; color: var(--ink); }
.dl-ic { display: inline-grid; place-items: center; width: 18px; height: 18px; border-radius: 5px; font-size: 11px; font-weight: 700; margin-top: 3px; color: #fff; background: var(--accent); }
.dl-ic::before { content: '✓'; }
.k-guard .dl-ic { background: #7c3aed; } .k-guard .dl-ic::before { content: '!'; }
.k-swap .dl-ic { background: var(--good); } .k-swap .dl-ic::before { content: '⇄'; }
.k-change .dl-ic { background: var(--warn, #b45309); } .k-change .dl-ic::before { content: '↻'; }
.k-outcome .dl-ic { background: var(--good); } .k-outcome .dl-ic::before { content: '★'; }
.k-guard .dl-tx { color: #4c1d95; }
.dl-not { color: var(--muted); }
.dl-not del .num { background: none; color: inherit; padding: 0; }
.dl-not del { color: var(--bad); text-decoration-color: var(--bad); text-decoration-thickness: 2px; }
.dl-arrow { display: inline-block; margin: 0 4px; font-size: 12px; font-weight: 700; color: var(--warn, #b45309); background: color-mix(in srgb, #b45309 12%, transparent); border-radius: 4px; padding: 0 6px; }
.dl-new { font-weight: 700; }
.dl-win { font-weight: 700; color: var(--good); background: color-mix(in srgb, var(--good) 12%, transparent); border-radius: 4px; padding: 0 5px; }
.dl-q { font-weight: 600; color: var(--ink); background: var(--bg); border: 1px solid var(--line); border-radius: 4px; padding: 0 5px; }
@media (max-width: 1000px) { .dl-row { grid-template-columns: minmax(0, 1fr); gap: 8px; } .dl-side { border-right: 0; padding-right: 0; flex-direction: row; flex-wrap: wrap; align-items: center; } .dl-track { display: none; } }
"""

CSS += r"""
ol.flow { align-items: stretch; }
ol.flow .fl-t { font-size: 13px; color: var(--muted); font-weight: 500; margin-bottom: 2px; }
ol.flow .fl-d { display: block; }
ol.flow .fl-k { display: block; font-size: 18px; font-weight: 700; color: var(--accent); line-height: 1.35; margin-bottom: 8px; padding-bottom: 8px; border-bottom: 1px dashed var(--line); }
ol.flow > li { color: var(--muted); }
"""

CSS += r"""
.hero { display: grid; gap: 14px; margin-bottom: 8px; }
.hv { font-size: 15px; line-height: 1.8; color: var(--muted); padding: 2px 0; }
.hv-k { font-size: 12px; font-weight: 700; letter-spacing: .08em; color: var(--accent); border: 1px solid var(--accent); border-radius: 4px; padding: 1px 7px; margin-right: 10px; }
.hv-goal { color: var(--ink); font-weight: 600; border-bottom: 2px solid color-mix(in srgb, var(--accent) 45%, transparent); }
.hero-g { display: grid; grid-template-columns: minmax(0, 1.55fr) minmax(0, 1fr); grid-template-areas: 'v a' 'e a'; gap: 14px; }
.hz.ask { grid-area: a; } .hz.eng { grid-area: e; }
.hz { background: var(--surface); border: 1px solid var(--line); border-radius: 12px; padding: 16px 18px; }
.hz-l { font-size: 12px; font-weight: 700; letter-spacing: .08em; color: var(--muted); }
.hz.verdict { grid-area: v; display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 14px 24px; border-top: 4px solid var(--bad); align-content: start; }
.hz.verdict .hz-l, .hz.verdict .hz-v { grid-column: 1 / -1; }
.hz-v { font-size: 34px; font-weight: 800; color: var(--bad); line-height: 1.1; display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
.hz-x { display: inline-grid; place-items: center; width: 36px; height: 36px; border-radius: 50%; background: var(--bad); color: #fff; font-size: 20px; align-self: center; }
.hz-s { font-size: 16px; font-weight: 500; color: var(--muted); }
.hz-cap { font-size: 13px; color: var(--muted); margin-bottom: 8px; }
.hz-cap b { color: var(--bad); font-weight: 700; margin: 0 2px; }
.hb { display: grid; grid-template-columns: 6.5em minmax(0, 1fr) 4em; gap: 8px; align-items: center; margin: 6px 0; font-size: 13.5px; }
.hb-k { color: var(--ink); font-weight: 600; }
.hb-bar { height: 14px; background: var(--bg); border-radius: 4px; overflow: hidden; }
.hb-bar b { display: block; height: 100%; background: color-mix(in srgb, var(--muted) 55%, transparent); border-radius: 4px; }
.hb-bar b.bad { background: var(--bad); }
.hb-v { font-family: var(--font-mono); font-weight: 700; font-size: 16px; text-align: right; }
.hb-v.bad { color: var(--bad); }
.hz-gap { font-size: 13px; color: var(--muted); margin-top: 6px; }
.hz-gap b { font-family: var(--font-mono); color: var(--bad); font-size: 15px; }
.dots { display: grid; grid-template-columns: repeat(14, 12px); gap: 4px; }
.dots i { width: 12px; height: 12px; border-radius: 50%; border: 2px solid var(--bad); box-sizing: border-box; opacity: .75; }
.dots i.w { background: var(--good); border-color: var(--good); }
.hz.ask { border: 1.5px solid var(--accent); background: linear-gradient(180deg, color-mix(in srgb, var(--accent) 7%, var(--surface)), var(--surface)); }
.hz.ask .hz-l { color: var(--accent); }
.hq-h { font-size: 22px; font-weight: 800; color: var(--accent); margin: 4px 0 10px; }
.hq { list-style: none; margin: 0; padding: 0; display: grid; gap: 8px; counter-reset: none; }
.hq li { display: grid; grid-template-columns: 24px minmax(0, 1fr); gap: 8px; margin: 0; padding: 0; font-size: 14.5px; line-height: 1.55; color: var(--ink); }
.hq li::before { display: none; }
.hq-n { display: grid; place-items: center; width: 22px; height: 22px; border-radius: 50%; border: 2px solid var(--accent); color: var(--accent); font-family: var(--font-mono); font-size: 12px; font-weight: 700; }
.hq-ref { margin-top: 10px; font-size: 13px; color: var(--muted); }
.hz.eng { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; padding: 12px 18px; }
.hz.eng b { color: var(--ink); }
.eng-ok { display: inline-grid; place-items: center; width: 22px; height: 22px; border-radius: 50%; background: var(--good); color: #fff; font-size: 12px; font-weight: 700; align-self: center; }
.eng-d { font-size: 13.5px; color: var(--muted); }
@media (max-width: 1000px) { .hero-g, .hz.verdict { grid-template-columns: minmax(0, 1fr); } .hero-g { grid-template-areas: 'v' 'a' 'e'; } }
"""

CSS += r"""
table td.vs-good { color: var(--good); font-weight: 600; background: color-mix(in srgb, var(--good) 8%, transparent); }
table td.vs-bad { color: var(--bad); font-weight: 600; background: color-mix(in srgb, var(--bad) 7%, transparent); }
table.vs-base th:last-child, table.vs-base td.numcol:last-child { }
td.r-concl { font-weight: 600; color: var(--ink); box-shadow: inset 3px 0 0 color-mix(in srgb, var(--accent) 45%, transparent); }
th.rh-concl { color: var(--accent); }
td.r-cost { color: color-mix(in srgb, var(--bad) 80%, var(--ink)); font-size: 13.5px; }
th.rh-cost { color: var(--bad); }
th.rh-cost::before { content: '⚠ '; }
td.r-why { color: var(--muted); font-size: 13.5px; }
td.r-old { color: var(--muted); }
td.r-new { font-weight: 600; color: var(--ink); background: color-mix(in srgb, var(--accent) 5%, transparent); }
th.rh-new { color: var(--accent); }
th.rh-new::before { content: '→ '; }
.rid { display: inline-grid; place-items: center; min-width: 20px; height: 20px; border-radius: 5px; background: var(--accent-soft); color: var(--accent); font-family: var(--font-mono); font-size: 12px; font-weight: 700; margin-right: 8px; padding: 0 4px; }
.cat { display: inline-block; font-size: 12.5px; font-weight: 600; border-radius: 999px; padding: 1px 10px; border: 1px solid var(--line); }
.cat.c0 { color: var(--accent); background: var(--accent-soft); border-color: transparent; }
.cat.c1 { color: #7c3aed; background: color-mix(in srgb, #7c3aed 10%, transparent); border-color: transparent; }
.cat.c2 { color: #b45309; background: color-mix(in srgb, #b45309 10%, transparent); border-color: transparent; }
.cat.c3 { color: var(--muted); background: var(--bg); }
.pill.ditto { opacity: .7; }
"""

CSS += r"""
.cases { display: grid; grid-template-columns: repeat(auto-fit, minmax(290px, 1fr)); gap: 12px; margin: 14px 0 20px; }
.case { background: var(--surface); border: 1px solid var(--line); border-left: 4px solid var(--muted); border-radius: 10px; padding: 12px 16px; }
.case.t-bad { border-left-color: var(--bad); } .case.t-good { border-left-color: var(--good); }
.case-h { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; margin-bottom: 6px; }
.case-who { font-family: var(--font-mono); font-size: 12.5px; font-weight: 700; color: var(--accent); background: var(--accent-soft); border-radius: 5px; padding: 1px 8px; }
.case-c { font-size: 16.5px; font-weight: 700; color: var(--ink); }
.case.t-bad .case-c { color: var(--bad); } .case.t-good .case-c { color: var(--good); }
.case-b p { margin: 6px 0; font-size: 14.5px; }
.case-b p.kv { display: block; border: 0; padding: 0; }
.case-b p.kv .kv-k::before { display: none; }
.subpts { margin: 6px 0 2px; display: grid; gap: 4px; }
.subpts .sp { position: relative; padding-left: 14px; font-size: 14px; line-height: 1.6; color: var(--ink); }
.subpts .sp::before { content: ''; position: absolute; left: 2px; top: .65em; width: 5px; height: 5px; border-radius: 50%; background: var(--accent); }
"""

CSS += r"""
.hz.verdict2 { grid-area: v; border-top: 4px solid var(--accent); }
.hz.verdict2.t-bad { border-top-color: var(--bad); }
.hz-hd { font-size: 19px; font-weight: 700; line-height: 1.55; color: var(--ink); margin-top: 6px; }
.hz-hd .num, .hz-hd strong.num { font-size: 1.12em; color: var(--accent); background: none; padding: 0 1px; }
.hz-rest { font-size: 14.5px; line-height: 1.7; color: var(--muted); margin-top: 8px; padding-top: 8px; border-top: 1px dashed var(--line); }
.hz-engs { grid-area: e; display: grid; gap: 10px; margin: 0; padding: 0; }
.hero-g > .hz.ask { align-self: start; }
.hz-engs .hz.eng { padding: 10px 16px; }
.hq-h.calm { color: var(--good); font-size: 20px; }
.hz.ask.calm { border-color: color-mix(in srgb, var(--good) 50%, var(--line)); background: color-mix(in srgb, var(--good) 5%, var(--surface)); }
.hz.ask.calm .hz-l { color: var(--good); }
.hq-b { font-size: 14.5px; line-height: 1.7; margin-top: 6px; }
"""

CSS += r"""
td.exp-ok .mg-v, td.exp-ok { color: var(--good); font-weight: 700; }
td.exp-no .mg-v, td.exp-no { color: var(--bad); font-weight: 700; }
td.exp-ok .mg-b { background: var(--good) !important; } td.exp-no .mg-b { background: var(--bad) !important; }
table.split th.first-sub, table.split td.first-sub { border-left: 2px solid var(--line); }
table.split { table-layout: auto; width: 100%; }
table.split td, table.split th { padding-left: 8px; padding-right: 8px; }
table.split td:first-child, table.split th:first-child { min-width: 7.5em; }
table.split td.numcol { font-size: 13.5px; }

td.sg-pos { color: var(--good); } td.sg-neg { color: var(--bad); }
.ib { width: auto; min-width: 0; } td.ibc { white-space: nowrap; }
td.c-take, th.h-take { min-width: 10em; }
table.split .ib { min-width: 0; gap: 5px; }
table.split .ib i { display: none; }
table.split th, table.split td.ibc, table.split td.mgc { min-width: 0 !important; }
table.split .ib { width: auto; }
table.split td.c-take, table.split th.h-take { min-width: 9em; }
table.split .mg { gap: 6px; }
table.split tr.row-bad td, table.split tr.row-good td { background: none; }
table.split td.c-take { border-left: 0; }
table.split thead th.gh { text-align: center; }
p.exp-key { font-size: 12.5px; color: var(--muted); margin: 6px 0 4px; display: flex; gap: 8px; align-items: center; }
.ek { font-family: var(--font-mono); font-weight: 700; border-radius: 4px; padding: 0 6px; }
.ek.ok { color: var(--good); background: color-mix(in srgb, var(--good) 10%, transparent); } .ek.no { color: var(--bad); background: color-mix(in srgb, var(--bad) 10%, transparent); }
"""

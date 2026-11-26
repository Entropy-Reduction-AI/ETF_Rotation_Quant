"""Owner-page spec layer (docs/reference/owner-facing-uiux-principles.md §13).

Runs after polish.py. Only restructures and formats the source's own words: it never writes new content.
- every h2 section opens with a memo sentence (p.memo): the section's own lede, else its first sentence
- <details> become the spec's fold component (div.fold > button.fold-h + div.fold-b)
- a section shows at most one table expanded; the others fold in place as 明细表
- reference tables (definitions, lists) get data-lint="ref"
- conclusion cells get bold; list items and long paragraphs open with a bold phrase taken from their own text
"""
import math
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
        def carded(t):
            # a table the md marks to become cards is a ledger, not a detail table
            from bs4 import Comment
            sib = table_wrap(t).previous_sibling
            while sib is not None and isinstance(sib, NavigableString):
                if isinstance(sib, Comment) and '页面：卡片' in sib:
                    return True
                if sib.strip() and not isinstance(sib, Comment):
                    return False
                sib = sib.previous_sibling
            return False
        tables = [t for t in sec.find_all('table') if not in_fold(t) and t.get('data-lint') != 'ref' and not carded(t)]
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
        drop = []
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
                    # a trailing bold that only restates the focus is dropped from the body later,
                    # but only when it sits directly in the item (not inside the title) and every step keeps its focus line
                    if kb.parent is li and re.fullmatch(r'[\s。．.]*', ''.join(str(x) for x in kb.next_siblings)):
                        drop.append(kb)
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
            # an "例：" clause becomes a tinted example line at the bottom of the card
            for t in list(d.find_all(string=re.compile('例(（[^）]*）)?：'))):
                m = re.search('例(?:（([^）]*)）)?：', str(t))
                before, after = str(t)[:m.start()], str(t)[m.end():]
                sibs = []
                for sib in list(t.next_siblings):
                    if getattr(sib, 'name', None) in ('b', 'strong'):
                        break                      # the focus bold stays put; the trailing-bold rule handles it
                    sibs.append(sib)
                rest = after + ''.join(q.get_text() if hasattr(q, 'get_text') else str(q) for q in sibs)
                for sib in sibs:
                    sib.extract()
                x = soup.new_tag('span', attrs={'class': ['fl-x']})
                lab = soup.new_tag('span', attrs={'class': ['fl-xl']}); lab.string = '例' + (f'：{m.group(1)}' if m.group(1) else '')
                x.append(lab)
                left, _, res = rest.strip().rstrip('。').partition('→')
                parts = [q.strip() for q in left.split('·') if q.strip()]
                if len(parts) > 1 or res:
                    for q in parts:
                        c = soup.new_tag('span', attrs={'class': ['fl-c']}); c.string = q; x.append(c)
                    if res.strip():
                        r = soup.new_tag('span', attrs={'class': ['fl-r']}); r.string = '→ ' + res.strip(); x.append(r)
                else:
                    x.append(NavigableString(rest.strip()))
                t.replace_with(NavigableString(before.rstrip()))
                body = soup.new_tag('span', attrs={'class': ['fl-b']})
                for c in list(d.contents):
                    body.append(c.extract())
                d.append(body)
                d.append(x)
                break
            # a spec card: "看：…｜规则：…｜结果：…" becomes labelled rows (what it looks at, the rule, what comes out)
            body = d.find('span', class_='fl-b') or d
            bt = ''.join(c.get_text() if hasattr(c, 'get_text') and not (getattr(c, 'get', lambda *_: None)('class') or []) == ['fl-x'] else (str(c) if not hasattr(c, 'get_text') else '') for c in body.contents)
            if '看：' in bt and '｜' in bt:
                parts = [q.strip().rstrip('。') for q in bt[bt.index('看：'):].split('｜') if '：' in q]
                # the author's bold inside a row (e.g. **取前 3**) marks that row's core rule
                marks = [x.get_text(strip=True) for x in body.find_all(['b', 'strong']) if x.get_text(strip=True) != key]
                for c in list(body.contents):
                    if not ('fl-x' in (getattr(c, 'get', lambda *_: None)('class') or [])):
                        c.extract()
                rows = soup.new_tag('span', attrs={'class': ['fl-rows']})
                for q in parts:
                    lb, v = q.split('：', 1)
                    r = soup.new_tag('span', attrs={'class': ['fl-row'] + (['out'] if lb.strip() == '结果' else [])})
                    a_ = soup.new_tag('span', attrs={'class': ['fl-lb']}); a_.string = lb.strip()
                    b_ = soup.new_tag('span', attrs={'class': ['fl-v']}); b_.string = v.strip()
                    mk = [m_ for m_ in marks if m_ in v]
                    if mk:
                        b_['data-key'] = '｜'.join(mk)
                    r.append(a_); r.append(b_); rows.append(r)
                body.insert(0, rows)
                add_class(ol, 'spec')
            if key and '。' not in key and len(key) <= 18:
                k = soup.new_tag('span', attrs={'class': ['fl-k']})
                k.string = key
                b.insert_after(k)
                keys_ok.append(k)
        # a focus line only reads as a storyline when every step has one
        if len(keys_ok) != len(lis):
            for k in keys_ok:
                k.decompose()
        elif len(drop) == len(lis):
            for kb in drop:
                for x in list(kb.next_siblings):
                    x.extract()
                prev = kb.previous_sibling
                kb.decompose()
                if isinstance(prev, NavigableString):
                    prev.replace_with(NavigableString(re.sub(r'[\s。，,；]+$', '。', str(prev))))



def _ex_visual(chips, res, key):
    """Draw a step's worked example from its own numbers: a ranking as bars, votes as dots,
    a money split as a stacked bar, a premium gap against the rule's threshold. None if no shape fits."""
    from html import escape as e
    num = r'(-?\d+(?:\.\d+)?)'
    m = [re.fullmatch(r'(.+?)\s*' + num + '%', q) for q in chips]
    # a ranking: "军工 106% · 软件 100% · 公用 95%"
    if len(chips) >= 3 and all(m):
        mx = max(float(x.group(2)) for x in m)
        rows = ''.join(f'<span class="xv-bn">{e(x.group(1))}</span><span class="xv-bt"><i style="width:{float(x.group(2)) / mx * 100:.0f}%"></i></span>'
                       f'<span class="xv-bv">{e(x.group(2))}%</span>' for x in m)
        return f'<div class="xv xv-rank">{rows}</div>'
    # two levels: "常态 9% · 今天 16%" against "高 5 点以上…"
    if len(chips) == 2 and all(m):
        a, b = float(m[0].group(2)), float(m[1].group(2))
        th = re.search(r'(\d+(?:\.\d+)?)\s*点', key)
        d = abs(b - a) or 1
        lo, hi = min(a, b) - d * .8, max(a, b) + d * .5      # zoom on the gap; the labels carry the levels
        pos = lambda y: (y - lo) / (hi - lo) * 100
        pa, pb = pos(a), pos(b)
        thr = ''
        if th:
            pt = pos(a + float(th.group(1)))
            thr = f'<span class="xv-th" style="left:{pt:.1f}%"><em>常态 +{e(th.group(1))} 点</em></span>'
        over = th is not None and b - a > float(th.group(1))
        return (f'<div class="xv xv-gap{" over" if over else ""}"><div class="xv-track">'
                f'<span class="xv-seg" style="left:{min(pa, pb):.1f}%;width:{abs(pb - pa):.1f}%"></span>{thr}'
                f'<span class="xv-pt a" style="left:{pa:.1f}%"><em>{e(m[0].group(1))} {e(m[0].group(2))}%</em></span>'
                f'<span class="xv-pt b" style="left:{pb:.1f}%"><em>{e(m[1].group(1))} {e(m[1].group(2))}%</em></span>'
                f'</div></div>')
    # votes: "均线 ✓ · 宽度 ✓ · TRIN ✓"
    v = [re.fullmatch(r'(.+?)\s*([✓✗])', q) for q in chips]
    if len(chips) >= 2 and all(v):
        dots = ''.join(f'<span class="xv-vote{" on" if x.group(2) == "✓" else ""}"><b>{"✓" if x.group(2) == "✓" else ""}</b>{e(x.group(1))}</span>' for x in v)
        return f'<div class="xv xv-votes">{dots}</div>'
    # a money split in the result: "股票 12 万，国债 28 万"
    sp = re.fullmatch(r'(\S+?)\s*' + num + r'\s*万[，,]\s*(\S+?)\s*' + num + r'\s*万', res)
    if sp:
        a, b = float(sp.group(2)), float(sp.group(4))
        ins = ''.join(f'<span class="sg-chip">{e(q)}</span>' for q in chips)
        return (f'<div class="xv xv-split"><div class="xv-in">{ins}</div><div class="xv-bar">'
                f'<span class="s1" style="flex:{a}">{e(sp.group(1))} {e(sp.group(2))} 万</span>'
                f'<span class="s2" style="flex:{b}">{e(sp.group(3))} {e(sp.group(4))} 万</span></div></div>')
    return None


def _phi_svg(points, w=440, h=180):
    """p = Φ(t) 的换算曲线，标出每个名额的 (t, p)。points: [(名称, t, p, tone)]。"""
    from html import escape as e
    lo, hi = -3.0, 3.5; L, R, T, B = 34, 12, 22, 30
    X = lambda t: L + (t - lo) / (hi - lo) * (w - L - R); Y = lambda p: T + (1 - p) * (h - T - B)
    Phi = lambda t: 0.5 * (1 + math.erf(t / math.sqrt(2)))
    path = 'M' + ' L'.join(f'{X(lo + i * (hi - lo) / 120):.1f},{Y(Phi(lo + i * (hi - lo) / 120)):.1f}' for i in range(121))
    g = [f'<line x1="{L}" x2="{w - R}" y1="{Y(0):.1f}" y2="{Y(0):.1f}" class="ax"/>',
         f'<line x1="{L}" x2="{w - R}" y1="{Y(.5):.1f}" y2="{Y(.5):.1f}" class="mid"/>',
         f'<line x1="{X(0):.1f}" x2="{X(0):.1f}" y1="{T}" y2="{Y(0):.1f}" class="mid"/>']
    for pv in (0, .5, 1):
        g.append(f'<text x="{L - 6}" y="{Y(pv) + 4:.1f}" text-anchor="end" class="tk">{pv:g}</text>')
    for tv in (-2, -1, 0, 1, 2, 3):
        g.append(f'<text x="{X(tv):.1f}" y="{h - B + 16}" text-anchor="middle" class="tk">{tv:+d}</text>' if tv else f'<text x="{X(tv):.1f}" y="{h - B + 16}" text-anchor="middle" class="tk">t = 0</text>')
    g.append(f'<text x="{L - 6}" y="{T - 5}" text-anchor="end" class="tk">p</text>')
    g.append(f'<path d="{path}" class="crv"/>')
    for nm, t, pv, tone in points:
        x, y = X(max(lo, min(hi, t))), Y(pv); right = x < w * .6
        g.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{y:.1f}" y2="{Y(0):.1f}" class="drop {tone}"/>'
                 f'<circle cx="{x:.1f}" cy="{y:.1f}" r="6" class="pt {tone}"/>'
                 f'<text x="{x + (10 if right else -10):.1f}" y="{y + (-8 if pv > .9 else 18):.1f}" text-anchor="{"start" if right else "end"}" class="lb {tone}">{e(nm)}：t {t:+.2f} → p {pv:.3g}</text>')
    return f'<svg class="phi" viewBox="0 0 {w} {h}" role="img" aria-label="p = Φ(t) 换算曲线">{"".join(g)}</svg>'


def calc_grid(soup):
    """“名称：步骤一 → 步骤二 → 步骤三。说明”段落 + 表头带 ①②③ 的算例表 → 一张逐步算式表：
    表头是每一步的算式，每行是一个算例的逐步数字，下方是 p = Φ(t) 的换算曲线。"""
    for para in soup.select('p.kv'):
        v = para.find('span', class_='kv-v'); nxt = para.find_next_sibling()
        if v is None or v.get_text().count('→') < 2 or nxt is None or 'table-wrap' not in (nxt.get('class') or []):
            continue
        tb = nxt.find('table'); hd = [th.get_text(strip=True) for th in tb.select('thead th')]
        if not any(x.startswith('①') for x in hd):
            continue
        full = v.get_text(' ', strip=True).replace(' → ', '→').replace('→', '→')
        chain, _, note = full.partition('。')
        steps = [q.strip() for q in chain.split('→')]
        rows = [[td.get_text(strip=True) for td in tr.find_all('td')] for tr in tb.select('tbody tr')]
        grp = {}
        for j, x in enumerate(hd[1:-1], 1):
            k = '①②③④⑤'.index(x[0]); grp.setdefault(k, []).append((x[1:].strip(), j))
        H = ['<div class="calcgrid">', f'<div class="cg-title">{html_escape(para.find("span", class_="kv-k").get_text(strip=True))}</div>',
             f'<div class="cg-grid" style="--n:{len(steps)}">', f'<div class="cg-hd cg-lab">{html_escape(hd[0])}</div>']
        for i, st in enumerate(steps):
            verb, _, body = st.partition('：'); sub = ''
            m = re.match(r'(.*?)（(.+)）$', body)
            if m: body, sub = m.group(1), m.group(2)
            fm = ' cg-fm' if '=' in body else ''
            H.append(f'<div class="cg-hd cg-step"><span class="cg-n">{"①②③④⑤"[i]}</span><span class="cg-verb">{html_escape(verb)}</span>'
                     f'<span class="cg-body{fm}">{html_escape(body)}</span>' + (f'<span class="cg-sub">{html_escape(sub)}</span>' if sub else '') + '</div>')
        H.append(f'<div class="cg-hd cg-out"><span class="cg-verb">得出</span><span class="cg-body">{html_escape(hd[-1])}</span></div>')
        pts = []
        for r in rows:
            vals = {k: [(nm, r[j]) for nm, j in grp.get(k, [])] for k in range(len(steps))}
            last = vals[len(steps) - 1][-1][1] if vals.get(len(steps) - 1) else ''
            try: pv = float(last)
            except ValueError: pv = None
            tone = 'good' if pv is not None and pv >= .5 else 'bad'
            H.append(f'<div class="cg-lab cg-row {tone}">{html_escape(r[0])}</div>')
            for k in range(len(steps)):
                cells = vals.get(k, []); lb = steps[k].partition('：')[0]
                if len(cells) > 1:
                    inner = ''.join(f'<span class="cg-kv"><em>{html_escape(nm)}</em><b>{html_escape(x)}</b></span>' for nm, x in cells)
                    H.append(f'<div class="cg-c cg-multi" data-lb="{html_escape(lb)}">{inner}</div>')
                else:
                    nm, x = cells[0] if cells else ('', '')
                    bar = f'<span class="cg-bar"><i style="width:{pv * 100:.0f}%"></i></span>' if k == len(steps) - 1 and pv is not None else ''
                    H.append(f'<div class="cg-c cg-big {tone}" data-lb="{html_escape(lb)}"><em>{html_escape(nm)} =</em><b>{html_escape(x)}</b>{bar}</div>')
            res = r[-1]; a_, eq, b_ = res.rpartition('=')
            H.append(f'<div class="cg-c cg-res" data-lb="得出">' + (f'<span>{html_escape(a_.strip())} =</span><b>{html_escape(b_.strip())}</b>' if eq else f'<b>{html_escape(res)}</b>') + '</div>')
            try: pts.append((r[0].replace('名额', ''), float(vals[1][0][1].replace('−', '-').replace('+', '')), pv, tone))
            except (KeyError, IndexError, ValueError, TypeError): pass
        H.append('</div>')
        if note or pts:
            H.append('<div class="cg-foot">' + (_phi_svg(pts) if pts else '') + (f'<p class="cg-note"><b>怎么读</b>{html_escape(note.strip())}</p>' if note else '') + '</div>')
        H.append('</div>')
        new = BeautifulSoup(''.join(H), 'html.parser')
        para.replace_with(new); nxt.decompose()


def spec_grid(soup):
    """A spec list (steps written as 看：…｜规则：…｜结果：… with an 例) reads as full-width rows of chips, not narrow text cards."""
    for ol in soup.select('ol.flow.spec'):
        lis = ol.find_all('li', recursive=False)
        grid = soup.new_tag('div', attrs={'class': ['specgrid']})
        hd = soup.new_tag('div', attrs={'class': ['sg-row', 'sg-hd']})
        ex_lab = None
        for li in lis:
            x = li.find('span', class_='fl-x')
            if x is not None and x.find('span', class_='fl-xl'):
                ex_lab = x.find('span', class_='fl-xl').get_text(strip=True)
                break
        for lab in ('步骤', '看什么', '怎么判', '得出', ex_lab or '例'):
            c = soup.new_tag('span', attrs={'class': ['sg-h']}); c.string = lab; hd.append(c)
        grid.append(hd)
        for i, li in enumerate(lis, 1):
            row = soup.new_tag('div', attrs={'class': ['sg-row']})
            head = soup.new_tag('div', attrs={'class': ['sg-step']})
            n = soup.new_tag('span', attrs={'class': ['sg-n']}); n.string = str(i); head.append(n)
            t = li.find('b', class_='fl-t'); k = li.find('span', class_='fl-k')
            nm = soup.new_tag('span', attrs={'class': ['sg-name']}); nm.string = t.get_text(strip=True).rstrip('：:') if t else ''
            head.append(nm)
            if k is not None:
                pu = soup.new_tag('span', attrs={'class': ['sg-purpose']}); pu.string = k.get_text(strip=True); head.append(pu)
            row.append(head)
            vals, keys = {}, {}
            for r in li.select('span.fl-row'):
                lb_ = r.find('span', class_='fl-lb').get_text(strip=True); fv = r.find('span', class_='fl-v')
                vals[lb_] = fv.get_text(strip=True)
                keys[lb_] = [q for q in (fv.get('data-key') or '').split('｜') if q]
            for lb, cls in (('看', 'sg-see'), ('规则', 'sg-rule'), ('结果', 'sg-out')):
                cell = soup.new_tag('div', attrs={'class': ['sg-cell', cls], 'data-lb': {'看': '看什么', '规则': '怎么判', '结果': '得出'}[lb]})
                qs = [q.strip() for q in vals.get(lb, '').split('·') if q.strip()]
                # the row's core rule (the author's bold) leads the cell, big; the other conditions follow, small
                qs = [q for q in qs if q in keys.get(lb, [])] + [q for q in qs if q not in keys.get(lb, [])]
                for q in qs:
                    c = soup.new_tag('span', attrs={'class': ['sg-chip'] + (['sg-key'] if q in keys.get(lb, []) else [])}); c.string = q; cell.append(c)
                if lb == '规则' and keys.get(lb):
                    add_class(cell, 'has-key')
                row.append(cell)
            x = li.find('span', class_='fl-x')
            ex = soup.new_tag('div', attrs={'class': ['sg-cell', 'sg-ex'], 'data-lb': ex_lab or '例'})
            if x is not None:
                xl = x.find('span', class_='fl-xl')
                if xl is not None and xl.get_text(strip=True) != ex_lab:
                    m = soup.new_tag('span', attrs={'class': ['sg-exl']}); m.string = xl.get_text(strip=True).replace('例：', ''); ex.append(m)
                    ex['data-lb'] = '例'                 # its own example, not the header's month
                chips = [c.get_text(strip=True) for c in x.select('span.fl-c')]
                r = x.find('span', class_='fl-r')
                res = r.get_text(strip=True).lstrip('→').strip() if r is not None else ''
                vis = _ex_visual(chips, res, ' '.join(keys.get('规则', [])))
                if vis:
                    ex.append(BeautifulSoup(vis, 'html.parser'))
                else:
                    for q in chips:
                        cc = soup.new_tag('span', attrs={'class': ['sg-chip']}); cc.string = q; ex.append(cc)
                if res:
                    rr = soup.new_tag('span', attrs={'class': ['sg-res']}); rr.string = res; ex.append(rr)
            row.append(ex)
            grid.append(row)
        ol.replace_with(grid)


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
                m = re.match(r'^\s*([a-z]|[①-⑳])(?=[^\sA-Za-z0-9])', first)
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
                continue
            # same idea when the values share a lead word: “计 1 / 计 2 / 文献 / 约定，Reviewer 核” -> 计 · 文献 · 约定
            key = lambda v: re.split(r'[\s，,（(\d]', v, maxsplit=1)[0]
            keys = [key(v) for v in vals]
            ukeys = set(k for k in keys if k)
            if (len(vals) >= 4 and 2 <= len(ukeys) <= 4 and len(uniq) > len(ukeys) and all(0 < len(k) <= 4 for k in keys)
                    and all(len(v) <= 14 for v in vals) and all(re.fullmatch(r'[\u4e00-\u9fff]{1,4}', k) for k in keys)
                    and not any(r[ci].find(class_=re.compile(r'^(ib|ibc|pill|mg)$')) or r[ci].find('a') for r in grid if ci < len(r))
                    and all(re.fullmatch(r'[\u4e00-\u9fff]{1,4}(\s*\d{1,2}|，.{1,10})?', v) for v in vals if v)):
                order = sorted(ukeys, key=keys.index)
                for r in grid:
                    if ci < len(r) and r[ci].get_text(strip=True) and not r[ci].find(class_='pill'):
                        v = r[ci].get_text('', strip=True)
                        r[ci].clear()
                        r[ci].append(BeautifulSoup(f'<span class="cat c{order.index(key(v))}">{html_escape(v)}</span>', 'html.parser'))
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


def ledger_cards(soup):
    """Case tables read as a ledger of cases, one card each. Triggered by a table whose header has a column
    starting with 超出, whose first column is 陷阱, or that the md marks with <!-- 页面：卡片 --> right above it.
    The card's large line is the column named 代价 / 结论 / 状态; the foot is the last other column (⚠ when it
    is a tripwire "超出…"); a leading # column becomes a number badge before the title. Every cell is kept."""
    from bs4 import Comment
    for t in list(soup.find_all('table')):
        if t.find_parent(class_='fold-b') is not None:
            continue
        H = [th.get_text('', strip=True) for th in t.select('thead th')]
        w = t.find_parent(class_='table-wrap') or t
        prev = w.find_previous_sibling(string=lambda x: isinstance(x, Comment)) if w.previous_sibling is not None else None
        marked = False
        sib = w.previous_sibling
        between = []                                   # a score bar polish put between the marker and the table
        while sib is not None and (isinstance(sib, NavigableString) or (getattr(sib, 'name', None) == 'div' and 'score' in (sib.get('class') or []))):
            if isinstance(sib, Comment) and '页面：卡片' in sib:
                marked = True
                sib.extract()
                break
            if isinstance(sib, NavigableString) and sib.strip():
                break
            if not isinstance(sib, NavigableString):
                between.append(sib)
            sib = sib.previous_sibling
        if marked:
            for x in between:                          # the cards carry each row's status; a partial count would mislead
                x.decompose()
        if len(H) < (2 if marked else 3) or not (marked or any(h.startswith('超出') for h in H) or H[0] == '陷阱'):
            continue
        rows0 = [tr.find('td') for tr in t.select('tbody tr')]
        num = H[0] in ('#', '编号') and all(c is not None and re.fullmatch(r'\d{1,2}', c.get_text('', strip=True)) for c in rows0)
        ti = 1 if num else 0
        big = next((i for i, h in enumerate(H) if i > ti and ('代价' in h or h in ('结论', '状态', '门槛'))), None)
        foot = next((i for i in range(len(H) - 1, ti, -1) if i != big), None)
        mids = [i for i in range(ti + 1, len(H)) if i not in (big, foot)]
        trip = foot is not None and H[foot].startswith('超出')

        def chips(td):
            # a cell that is a list of 4+ short items reads as chips
            items = [x.strip() for x in td.get_text('', strip=True).split('、')]
            # only when every item carries its own note, so nothing shared (“均 …”) is split off
            if (len(items) >= 4 and all(0 < len(x) <= 22 and x.endswith('）') for x in items)
                    and td.find(['a', 'code']) is None and '均' not in td.get_text()):
                return '<span class="lg-chips">' + ''.join(f'<span class="lg-c">{html_escape(x)}</span>' for x in items) + '</span>'
            return td.decode_contents()
        cards = []
        for tr in t.select('tbody tr'):
            tds = tr.find_all('td')
            if len(tds) != len(H):
                break
            badge = f'<span class="lg-n">{tds[0].get_text("", strip=True)}</span>' if num else ''
            tone = ''
            if big is not None:
                for pl in tds[big].select('.pill'):
                    pl.unwrap()
            if big is not None and H[big] == '状态':
                tone = ' t-' + _tf_status_tone(tds[big].get_text('', strip=True))
            bl = (f'<div class="lg-big{tone}">{tds[big].decode_contents()}</div>' +
                  ('' if H[big] in ('结论', '状态') else f'<div class="lg-bl">{H[big]}</div>')) if big is not None else ''
            md = ''.join(f'<div class="lg-m"><span class="lg-k">{H[i]}</span>{chips(tds[i])}</div>' for i in mids)
            if len(H) == 2:
                # a two-column list: the second column is the card's body
                cards.append(f'<div class="lg"><div class="lg-h">{tds[0].decode_contents()}</div><div class="lg-m lg-t">{chips(tds[1])}</div></div>')
                continue
            ft = '' if foot is None else (f'<div class="lg-f{" trip" if trip else ""}"><span class="lg-fi">{"⚠" if trip else "→"}</span>'
                  f'<span class="lg-k">{H[foot]}</span>{chips(tds[foot])}</div>')
            if len(tds[ti].get_text('', strip=True)) > 26 and bl and H[big] != '状态':
                # a long title reads as the card's body; the short verdict leads
                lead = tds[ti].find(['strong', 'b'])
                body_td = tds[ti]
                if lead is not None and body_td.get_text('', strip=True).startswith(lead.get_text('', strip=True)):
                    # a bold lead names the case: it becomes the title, the rest stays as the body
                    title = lead.get_text('', strip=True)
                    lead.extract()
                    rest = re.sub(r'^\s*[：:]\s*', '', body_td.decode_contents())
                    pm = re.match(r'^\s*(（[^（）<]*）)\s*[：:]\s*', rest)
                    if pm:                     # a leading citation reads after the fact, not before it
                        rest = rest[pm.end():].rstrip() + pm.group(1)
                    cards.append(f'<div class="lg"><div class="lg-h">{badge}{title}</div>{bl}<div class="lg-m lg-t">{rest}</div>{md}{ft}</div>')
                    continue
                head = f'<div class="lg-h">{badge}</div>' if badge else ''
                cards.append(f'<div class="lg">{head}{bl}<div class="lg-m lg-t">{tds[ti].decode_contents()}</div>{md}{ft}</div>')
            else:
                cards.append(f'<div class="lg"><div class="lg-h">{badge}{tds[ti].decode_contents()}</div>{bl}{md}{ft}</div>')
        else:
            g = BeautifulSoup(f'<div class="ledger n{len(cards)}">' + ''.join(cards) + '</div>', 'html.parser')
            w.replace_with(g)
            for b in g.select('.lg-big b, .lg-big strong'):
                b.unwrap()


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
    node = BeautifulSoup(html, 'html.parser')
    kp = sec.select_one('.comp-指标')
    if kp is not None:                       # KPI tiles go full width under the verdict / ask cards; the long rest of the conclusion goes
        r = node.select_one('.hz.verdict2 .hz-rest')
        if r is not None:
            r.extract()
        node.select_one('.hero').append(kp.extract())
    sec.select_one('.cards.status').replace_with(node)



def sensitivity_cards(soup):
    """Cards that each report a variant's result as 'X%' plus '少/多 N 个点' or '都差 N 个点以内':
    infer the base from X + delta, draw the variants on one axis around it, tone each card."""
    for grp in soup.select('.cards'):
        cards = grp.select('.card')
        if len(cards) < 3 or grp.find_parent(class_='status') is not None:
            continue
        rows, bases = [], []
        for c in cards:
            cv, p = c.select_one('.cv'), c.find('p')
            if cv is None or p is None:
                break
            vals = [float(x) for x in re.findall(r'(\d+(?:\.\d+)?)(?=%|\s*[–-]\s*\d+(?:\.\d+)?%)', cv.get_text())]
            t = p.get_text('', strip=True)
            m = re.match(r'^(少|多)\s*(\d+(?:\.\d+)?)(?:[–-](\d+(?:\.\d+)?))?\s*个点', t)
            m2 = re.search(r'都差\s*(\d+(?:\.\d+)?)\s*个点以内', t)
            if not vals or not (m or m2):
                break
            if m and len(vals) == 1 and not m.group(3):
                d = float(m.group(2)) * (1 if m.group(1) == '多' else -1)
                bases.append((len(m.group(2)), round(vals[0] - d, 1)))
            kind = 'warn' if m and m.group(1) == '多' else ('bad' if m else 'good')
            if kind == 'warn':
                lab = f'多 {m.group(2)} 个点 · 要警惕'
            elif kind == 'bad':
                lab = f'少 {m.group(2)}' + (f'–{m.group(3)}' if m.group(3) else '') + ' 个点 · 敏感'
            else:
                lab = f'±{m2.group(1)} 个点内 · 稳'
            rows.append((c, vals, kind, lab))
        else:
            if not bases or max(b for _, b in bases) - min(b for _, b in bases) > 0.6:
                continue
            base = max(bases)[1]  # the most precisely stated delta wins
            allv = [v for _, vals, _, _ in rows for v in vals] + [base]
            lo, hi = min(allv) - 2, max(allv) + 2
            pos = lambda v: (v - lo) / (hi - lo) * 100
            marks, placed = [], []
            for c, vals, kind, lab in rows:
                name = c.select_one('.ct').get_text(strip=True)
                add_class(c, 'sens', f'sk-{kind}')
                c['class'] = [x for x in c['class'] if not x.startswith('tone-')]
                c.select_one('.ct').insert_after(BeautifulSoup(f'<div class="sens-tag">{lab}</div>', 'html.parser'))
                if len(vals) == 2 and '–' in c.select_one('.cv').get_text():
                    marks.append(f'<div class="sm r sk-{kind}" style="left:{pos(vals[0]):.1f}%;width:{pos(vals[1]) - pos(vals[0]):.1f}%" title="{name}"></div>')
                for v in (vals if not (len(vals) == 2 and '–' in c.select_one('.cv').get_text()) else []):
                    marks.append(f'<div class="sm d sk-{kind}" style="left:{pos(v):.1f}%" title="{name} {v}%"></div>')
                lx = pos(sum(vals) / len(vals))
                row = 0
                while any(abs(lx - x) < 16 and r == row for x, r in placed):
                    row += 1
                placed.append((lx, row))
                marks.append(f'<div class="sl-lab sk-{kind}" style="left:{lx:.1f}%;top:{34 + row * 17}px">{name}</div>')
            ticks = ''.join(f'<span class="st" style="left:{pos(v):.1f}%">{v:g}%</span>' for v in range(int(lo // 5 * 5 + 5), int(hi) + 1, 5))
            # zone within ±2 of base
            z0, z1 = pos(base - 2), pos(base + 2)
            strip = (f'<div class="sens-axis"><div class="sa-cap">每项只改一处，年化落在哪：灰带 = 原规则 ±2 个点</div>'
                     f'<div class="sa-track"><div class="sa-zone" style="left:{z0:.1f}%;width:{z1 - z0:.1f}%"></div>'
                     f'<div class="sa-base" style="left:{pos(base):.1f}%"><span>原规则 {base:g}%</span></div>{"".join(marks)}</div>'
                     f'<div class="sa-ticks">{ticks}</div></div>')
            grp.insert_before(BeautifulSoup(strip, 'html.parser'))
            add_class(grp, 'sens-cards')



_GL_KIND = [('sell', '卖', re.compile(r'就卖|卖出|离场|换成现金|跌破')),
            ('def', '防守', re.compile(r'^(否则|不在股票里|空仓)|拿\s*10 年国债|换黄金|默认拿')),
            ('pace', '节奏', re.compile(r'^(仓位)?每(天|周|月)[末初]?$|^(仓位)?每(天|周|月)[^，]{0,6}(可以|才)|再平衡')),
            ('size', '仓位', re.compile(r'给一半|仓位分|100% 仓位|全仓|各 1/\d|各 1/N')),
            ('pick', '选', re.compile(r'.'))]


def _gl_kind(x):
    t = re.sub(r'<[^>]+>', '', x)
    return next((k, lab) for k, lab, rx in _GL_KIND if rx.search(t))


def _gl_rows(clause):
    """Split a clause at top-level commas, tag each piece, merge neighbours with the same tag."""
    toks, depth, cur = [], 0, ''
    for ch in re.split(r'(<[^>]+>|[（）()，：])', clause):
        if ch in ('（', '('):
            depth += 1
        elif ch in ('）', ')'):
            depth -= 1
        if ch in ('，', '：') and depth == 0:
            toks.append(cur + ('：' if ch == '：' else '')); cur = ''
        else:
            cur += ch
    if cur.strip():
        toks.append(cur)
    out = []
    for tk in [x.strip() for x in toks if x.strip()]:
        k = _gl_kind(tk)
        if out and (out[-1][0] == k or tk.endswith('：') is False and out[-1][1].endswith('：')):
            out[-1] = (out[-1][0] if out[-1][1].endswith('：') and out[-1][0] != k and False else out[-1][0], out[-1][1] + ('' if out[-1][1].endswith('：') else '，') + tk)
        else:
            out.append((k, tk))
    return out


def _gl_clauses(html):
    parts = [x.strip() for x in re.split(r'(?<=[。；])(?![^<]*>)', html) if x.strip()]
    return [re.sub(r'[。；]$', '', x) for x in parts]


def _bell_svg(t0, w=420, h=130):
    """钟形曲线，t0 左边涂色，标出面积 = Φ(t0)。"""
    lo, hi, L, R, T, B = -3.5, 3.5, 10, 10, 18, 26
    X = lambda t: L + (t - lo) / (hi - lo) * (w - L - R); pdf = lambda t: math.exp(-t * t / 2) / math.sqrt(2 * math.pi)
    Y = lambda d: h - B - d / pdf(0) * (h - T - B)
    xs = [lo + i * (hi - lo) / 140 for i in range(141)]
    crv = 'M' + ' L'.join(f'{X(t):.1f},{Y(pdf(t)):.1f}' for t in xs)
    left = [t for t in xs if t <= t0] + [t0]
    area = f'M{X(lo):.1f},{Y(0):.1f} L' + ' L'.join(f'{X(t):.1f},{Y(pdf(t)):.1f}' for t in left) + f' L{X(t0):.1f},{Y(0):.1f} Z'
    ph = 0.5 * (1 + math.erf(t0 / math.sqrt(2)))
    ticks = ''.join(f'<text x="{X(v):.1f}" y="{h - B + 15}" text-anchor="middle" class="tk">{v:+d}</text>' if v else f'<text x="{X(0):.1f}" y="{h - B + 15}" text-anchor="middle" class="tk">0</text>' for v in (-3, -2, -1, 0, 1, 2, 3))
    return (f'<svg class="bell" viewBox="0 0 {w} {h}" role="img" aria-label="钟形曲线在 t 左边的面积">'
            f'<path d="{area}" class="ar"/><path d="{crv}" class="cv"/><line x1="{L}" x2="{w - R}" y1="{Y(0):.1f}" y2="{Y(0):.1f}" class="ax"/>'
            f'<line x1="{X(t0):.1f}" x2="{X(t0):.1f}" y1="{T - 6}" y2="{Y(0):.1f}" class="t0"/>{ticks}'
            f'<text x="{X(t0) + 6:.1f}" y="{T + 2}" class="lb">t = {t0:g}</text>'
            f'<text x="{X(-0.4):.1f}" y="{Y(0) - 14:.1f}" text-anchor="middle" class="ar-lb">左边面积 = {ph:.2f} = p</text></svg>')


def term_cards(soup):
    """'名词解释' folds: one card per term -- the definition big, then 为什么 / 例 / 说明 rows, the formula boxed."""
    for fold in soup.select('.fold'):
        h = fold.select_one('.fold-h')
        if h is None or not h.get_text(strip=True).lstrip('▸▾ ').startswith('名词解释'):
            continue
        t = fold.find('table')
        if t is None:
            continue
        cards = []
        for tr in t.select('tbody tr'):
            tds = tr.find_all('td')
            if len(tds) < 2:
                continue
            name = tds[0].get_text(strip=True); body = tds[1].get_text('', strip=True)
            sents = [x for x in re.split(r'(?<=。)', body) if x.strip()]
            head, rest = sents[0], sents[1:]
            rows = []
            for x in rest:
                x = x.strip()
                fm = re.fullmatch(r'(.{0,4}?)([A-Za-zΦ]+\s*=\s*[^。，；]+)。', x)
                if fm:
                    rows.append(f'<div class="tm-fm">{html_escape(fm.group(2))}</div>'); continue
                m = re.match(r'^(例|为什么[^：]*|用在[^：]*)：(.*)$', x)
                lab, txt = (('例', m.group(2)) if m.group(1) == '例' else (m.group(1), m.group(2))) if m else ('说明', x)
                k = 'ex' if lab == '例' else ('why' if lab.startswith('为什么') else 'note')
                rows.append(f'<div class="tm-r"><span class="tm-k k-{k}">{html_escape(lab)}</span><span>{html_escape(txt)}</span></div>')
            wide = ' wide' if len(body) > 110 else ''
            if name.startswith('Φ'):
                rows.insert(1, _bell_svg(1.0))
            cards.append(f'<div class="tm-card{wide}"><div class="tm-n">{html_escape(name)}</div><div class="tm-d">{html_escape(head)}</div>{"".join(rows)}</div>')
        if cards:
            wrap = t.find_parent(class_='table-wrap') or t
            wrap.replace_with(BeautifulSoup('<div class="tm-grid">' + ''.join(cards) + '</div>', 'html.parser'))


def glossary_cards(soup):
    """'先认识这几个名字' folds: one profile card per name -- positioning line, then rules tagged 选/卖/防守/节奏."""
    for fold in soup.select('.fold'):
        h = fold.select_one('.fold-h')
        if h is None or '先认识这几个名字' not in h.get_text(strip=True):
            continue
        t = fold.select_one('table.deflist')
        if t is None:
            continue
        cards = []
        for tr in t.select('tbody tr'):
            tds = tr.find_all('td')
            if len(tds) < 2:
                continue
            name = tds[0].get_text(strip=True)
            body = tds[1].decode_contents().strip()
            plain = tds[1].get_text('', strip=True)
            # sub-entries labelled in bold ("**能排名的池子**：…", "**T1 转折点换挡**：…")
            subs = re.findall(r'<strong>([^<]{2,24})</strong>\s*：(.*?)(?=<strong>[^<]{2,24}</strong>\s*：|$)', body, re.S)
            if len(subs) >= 2:
                lead = body[:body.find('<strong>')].strip()
                first_sub = body.find('<strong>' + subs[0][0])
                items = ''.join(f'<div class="gl-sub"><div class="gl-sk">{a}</div><div class="gl-sv">{b.strip()}</div></div>' for a, b in subs)
                cards.append(f'<div class="gl-card wide t-ref"><div class="gl-n">{name}</div>' + (f'<div class="gl-pos">{lead}</div>' if lead else '') + f'<div class="gl-subs">{items}</div></div>')
                continue
            # benchmark-style weights "70% A + 15% B + 15% C"
            w = re.match(r'^((?:\d+%\s*[^+，]+?\s*\+\s*)+\d+%\s*[^，]+?)，(.*)$', plain)
            if w:
                legs = re.findall(r'(\d+)%\s*([^+]+)', w.group(1))
                cols = ['var(--accent)', '#7c3aed', '#0e7490', '#a16207', 'var(--muted)']
                bar = ''.join(f'<span style="flex:{a};background:{cols[k % 5]}">{a}%</span>' for k, (a, b) in enumerate(legs))
                bar += '</div><div class="gl-legend">' + ''.join(f'<span><i style="background:{cols[k % 5]}"></i>{b.strip()} {a}%</span>' for k, (a, b) in enumerate(legs))
                rest = body.split('，', 1)[1] if '，' in body else ''
                cards.append(f'<div class="gl-card t-ref"><div class="gl-n">{name}</div><div class="gl-bar">{bar}</div><div class="gl-r"><span class="gl-k k-pace">节奏</span><span>{rest}</span></div></div>')
                continue
            cl = _gl_clauses(body)
            if not cl:
                continue
            pos, rules = cl[0], cl[1:]
            m = re.match(r'^([^：]{2,10})：(.*)$', rules[0]) if rules else None
            if m and re.search(r'每', m.group(1)):
                rules[0] = m.group(2)
                rules.insert(0, m.group(1))
            tone = 'main' if re.search(r'唯一|入围的策略|最终版', pos) and '没入围' not in pos else ('peer' if '同行' in pos else ('off' if re.search(r'没入围|只作对照', plain) else 'info'))
            tag = {'main': '入围', 'peer': '公开同行', 'off': '对照', 'info': ''}[tone]
            rows = []
            for r in rules:
                for (k, lab), piece in _gl_rows(r):
                    rows.append(f'<div class="gl-r"><span class="gl-k k-{k}">{lab}</span><span>{piece.rstrip("：")}</span></div>')
            wide = ' wide' if len(plain) > 140 else ''
            cards.append(f'<div class="gl-card t-{tone}{wide}"><div class="gl-n">{name}' + (f'<span class="gl-tag">{tag}</span>' if tag else '') + f'</div><div class="gl-pos">{pos}</div>' + ''.join(rows) + '</div>')
        if cards:
            wrap = t.find_parent(class_='table-wrap') or t
            wrap.replace_with(BeautifulSoup('<div class="gl-grid">' + ''.join(cards) + '</div>', 'html.parser'))



def risk_return_map(soup):
    """Cards whose value reads '年化% · 回撤%' are drawn on one return-vs-drawdown map, with the benchmark
    (and other rows) taken from the page's own 年化/最大回撤 table; each card gets delta chips vs the benchmark."""
    rx = re.compile(r'^\s*([+\-−]?\d+(?:\.\d+)?)%\s*·\s*([\-−]\d+(?:\.\d+)?)%\s*$')
    num = lambda x: float(x.replace('−', '-'))
    for grp in soup.select('.cards'):
        cards = [c for c in grp.select('.card') if c.select_one('.cv') and rx.match(c.select_one('.cv').get_text())]
        if len(cards) < 2:
            continue
        ref = {}
        for t in soup.find_all('table'):
            H = [h.get_text('', strip=True) for h in P.leaf_heads(t)]
            if '年化' not in H or '最大回撤' not in H:
                continue
            ia, idd = H.index('年化'), H.index('最大回撤')
            for tr in t.select('tbody tr'):
                tds = tr.find_all('td')
                if len(tds) <= max(ia, idd):
                    continue
                nm = re.sub(r'（.*?）', '', tds[0].get_text('', strip=True)).strip()
                a = re.match(r'^([+\-−]?\d+(?:\.\d+)?)%$', tds[ia].get_text('', strip=True))
                d = re.match(r'^([\-−]\d+(?:\.\d+)?)%$', tds[idd].get_text('', strip=True))
                if a and d:
                    ref[nm] = (num(a.group(1)), num(d.group(1)))
            if '基准' in ref:
                break
        if '基准' not in ref:
            continue
        ba, bd = ref['基准']
        pts = []
        for c in cards:
            name = c.select_one('.ct').get_text(strip=True)
            m = rx.match(c.select_one('.cv').get_text())
            a, d = num(m.group(1)), num(m.group(2))
            da, dd = a - ba, abs(d) - abs(bd)
            good = (da >= -0.5) + (dd < 0)
            tone = 'good' if good == 2 else ('mid' if good == 1 else 'bad')
            c['class'] = [x for x in c['class'] if not x.startswith('tone-')] + ['rr', f'rr-{tone}']
            chips = (f'<span class="rr-c {"g" if da >= -0.5 else "b"}">年化 {"打平" if abs(da) < 0.5 else ("+" if da > 0 else "−") + f"{abs(da):.1f}"}</span>'
                     f'<span class="rr-c {"g" if dd < 0 else "b"}">回撤{"浅" if dd < 0 else "深"} {abs(dd):.0f} 个点</span>')
            c.select_one('.cv').insert_after(BeautifulSoup(f'<div class="rr-chips"><span class="rr-vs">对基准</span>{chips}</div>', 'html.parser'))
            pts.append((name, a, d, tone, True))
        names = {p_[0] for p_ in pts}
        for nm, (a, d) in ref.items():
            if nm not in names and not any(nm.startswith(x.split()[0]) for x in names):
                pts.append((nm, a, d, 'ref' if nm == '基准' else 'other', False))
        W, H_, L, R, T, B = 860, 300, 56, 150, 22, 40
        xs = [abs(p_[2]) for p_ in pts]; ys = [p_[1] for p_ in pts]
        x0, x1 = 0, (max(xs) // 10 + 1) * 10
        y0, y1 = min(0, (min(ys) // 5) * 5), (max(ys) // 5 + 1) * 5
        X = lambda v: L + (v - x0) / (x1 - x0) * (W - L - R)
        Y = lambda v: T + (y1 - v) / (y1 - y0) * (H_ - T - B)
        svg = [f'<svg viewBox="0 0 {W} {H_}" class="rr-svg" role="img" aria-label="年化和最大回撤">']
        svg.append(f'<rect x="{L}" y="{T}" width="{X(abs(bd)) - L:.1f}" height="{Y(ba) - T:.1f}" class="rr-q"/>')
        for v in range(int(x0), int(x1) + 1, 10):
            svg.append(f'<text x="{X(v):.1f}" y="{H_ - B + 16}" class="rr-t" text-anchor="middle">−{v}%</text>')
        for v in range(int(y0), int(y1) + 1, 5):
            svg.append(f'<text x="{L - 8}" y="{Y(v) + 4:.1f}" class="rr-t" text-anchor="end">{v}%</text><line x1="{L}" x2="{W - R}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" class="rr-g"/>')
        svg.append(f'<line x1="{X(abs(bd)):.1f}" x2="{X(abs(bd)):.1f}" y1="{T}" y2="{H_ - B}" class="rr-ref"/><line x1="{L}" x2="{W - R}" y1="{Y(ba):.1f}" y2="{Y(ba):.1f}" class="rr-ref"/>')
        svg.append(f'<text x="{L + 6}" y="{T + 14}" class="rr-ql">两项都比基准好</text>')
        svg.append(f'<text x="{W - R - 4}" y="{H_ - B - 8}" class="rr-t" text-anchor="end">← 回撤越浅越好　　最大回撤</text><text x="{L - 40}" y="{T - 4}" class="rr-t">年化</text>')
        boxes = []
        for nm, a, d, tone, main in sorted(pts, key=lambda q: -q[1]):
            r = 7 if main else 5
            cx, cy = X(abs(d)), Y(a)
            lab = f'{nm} {a:g}% · {d:g}%'.replace('-', '−')
            w = len(lab) * 7.2
            lx, ly = cx + 10, cy - 8
            while any(abs(ly - by) < 15 and lx < bx + bw and bx < lx + w for bx, by, bw in boxes):
                ly += 15
            boxes.append((lx, ly, w))
            svg.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" class="rr-p rr-{tone}"/><text x="{lx:.1f}" y="{ly:.1f}" class="rr-l rr-{tone}{" m" if main else ""}">{lab}</text>')
        svg.append('</svg>')
        fig = (f'<figure class="rr-fig"><div class="rr-cap">年化 × 最大回撤：虚线是基准（{ba:g}% · {bd:g}%）'.replace('-', '−') + f'，左上角的浅色区 = 两项都比基准好。</div>' + ''.join(svg) + '</figure>')
        grp.insert_before(BeautifulSoup(fig, 'html.parser'))
        add_class(grp, 'rr-cards')


def caution_kv(soup):
    """'不能…/别…' lead-phrase paragraphs read as a caution callout."""
    for pk in soup.select('p.kv'):
        k = pk.select_one('.kv-k')
        if k is not None and re.match(r'^(不能|别|不要|注意)', k.get_text(strip=True)):
            add_class(pk, 'kv-warn')



_DX_GOOD = re.compile(r'对了|赚了钱|拿对|方向对|赢|更好')
_DX_BAD = re.compile(r'挤掉|太散|只有|成本|回撤|吃掉|来回换|撞上|错|亏|输|太频繁|丢了')


def diagnosis_cards(soup):
    """Cards titled 'Name：diagnosis' (no value line): name chip + big diagnosis, the section memo's
    per-name figure as a gauge against its 基准, and each clause marked as what worked (✓) or what cost (✕)."""
    for grp in soup.select('.cards'):
        cards = grp.select('.card')
        if len(cards) < 2 or grp.find_parent(class_='status') is not None:
            continue
        if any(c.select_one('.cv') for c in cards):
            continue
        heads = [re.match(r'^([^：]{1,12})：(.+)$', c.select_one('.ct').get_text(strip=True)) if c.select_one('.ct') else None for c in cards]
        if not all(heads):
            continue
        sec = grp.find_parent('section')
        memo = sec.select_one('p.memo') if sec else None
        gauge = {}
        if memo is not None:
            mt = memo.get_text('', strip=True)
            mm = re.search(r'([^。：]{2,16})：((?:[^、（。]+?\s*\d+(?:\.\d+)?%、?)+)（基准\s*(\d+(?:\.\d+)?)%）', mt)
            if mm:
                for nm, v in re.findall(r'([^、]+?)\s*(\d+(?:\.\d+)?)%', mm.group(2)):
                    gauge[nm.strip()] = float(v)
                gname, gbase = mm.group(1), float(mm.group(3))
        for c, m in zip(cards, heads):
            name, diag = m.group(1), m.group(2)
            p = c.find('p')
            if p is None:
                continue
            body = p.decode_contents()
            parts = [x for x in re.split(r'(?<=[；。])(?![^<]*>)|(?=但)(?![^<]*>)', body) if x.strip()]
            rows, good, bad = [], 0, 0
            for x in parts:
                t = re.sub(r'<[^>]+>', '', x)
                k = 'bad' if _DX_BAD.search(t) and not (_DX_GOOD.search(t) and not re.search(r'但|只有|成本', t)) else ('good' if _DX_GOOD.search(t) else 'neu')
                good += k == 'good'; bad += k == 'bad'
                x = re.sub(r'（([+\-−]\d+(?:\.\d+)?)）', lambda q: f'（<b class="{"sg-pos" if q.group(1)[0] == "+" else "sg-neg"}">{q.group(1)}</b>）', x)
                rows.append(f'<div class="dx-r dx-{k}"><span class="dx-i"></span><span>{x.strip()}</span></div>')
            g = ''
            key = next((k for k in gauge if k.startswith(name) or name.startswith(k)), None)
            if key is not None:
                v = gauge[key]; mx = max(max(gauge.values()), gbase) * 1.1
                tone = 'g' if v >= gbase else 'b'
                g = (f'<div class="dx-g"><div class="dx-gl">{gname}</div><div class="dx-gb"><i class="{tone}" style="width:{v / mx * 100:.0f}%"></i>'
                     f'<em style="left:{gbase / mx * 100:.0f}%"></em></div><div class="dx-gv"><b class="{tone}">{v:g}%</b><span>基准 {gbase:g}%</span></div></div>')
            tone = 'bad' if good == 0 else 'mid'
            c['class'] = [x for x in c['class'] if not x.startswith('tone-')] + ['dx', f'dxc-{tone}']
            c.clear()
            c.append(BeautifulSoup(f'<div class="dx-h"><span class="dx-n">{name}</span></div><div class="dx-d">{diag}</div>{g}<div class="dx-rows">{"".join(rows)}</div>', 'html.parser'))
        add_class(grp, 'dx-cards')


def ux_pass(html):
    soup = BeautifulSoup(html, 'html.parser')
    status_hero(soup)
    glossary_cards(soup)
    term_cards(soup)
    inline_bullets(soup)
    case_cards(soup)
    ledger_cards(soup)
    card_ux(soup)
    sensitivity_cards(soup)
    risk_return_map(soup)
    diagnosis_cards(soup)
    flow_steps(soup)
    spec_grid(soup)
    kv_paragraphs(soup)
    calc_grid(soup)
    focus_pass(soup)
    action_board(soup)
    risk_table(soup)
    decision_log(soup)
    table_focus(soup)
    for el in soup.select('p, li, .cb, .od, .dl-tx, .dl-h, .dx-r > span:last-child'):
        if el.find_parent(['table', 'nav', 'footer']) is not None or el.find_parent(class_='fold-h') is not None:
            continue
        if el.find_parent('li') is not None and el.name == 'p':
            continue
        mark_numbers(soup, el)
    caution_kv(soup)
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
ol.flow .fl-x { display: flex; flex-wrap: wrap; align-items: center; gap: 5px; margin-top: 10px; padding: 8px 9px; background: var(--accent-soft); border-radius: 8px; font-size: 12.5px; line-height: 1.5; color: var(--ink); }
ol.flow .fl-xl { width: 100%; font-size: 11.5px; color: var(--muted); }
ol.flow .fl-c { display: inline-block; padding: 1px 7px; border-radius: 5px; background: var(--surface); border: 1px solid var(--line); font-size: 12.5px; font-variant-numeric: tabular-nums; white-space: nowrap; color: var(--ink); }
ol.flow .fl-r { width: 100%; font-weight: 700; color: var(--accent); font-size: 13.5px; }
ol.flow .fl-x .num { all: unset; }
ol.flow.spec .fl-t { font-size: 19px; font-weight: 800; color: var(--ink); margin: 2px 0 0; }
ol.flow.spec .fl-k { font-size: 14px; font-weight: 700; color: var(--accent); margin: 2px 0 10px; padding-bottom: 10px; }
ol.flow.spec .fl-rows { display: grid; gap: 6px; }
ol.flow.spec .fl-row { display: grid; grid-template-columns: 2.8em minmax(0, 1fr); gap: 6px; font-size: 13.5px; line-height: 1.55; color: var(--ink); }
ol.flow.spec .fl-lb { font-size: 12px; color: var(--muted); padding-top: 1px; }
ol.flow.spec .fl-row.out .fl-v { font-weight: 700; }
ol.flow.spec .fl-v .num { all: unset; }
.specgrid { display: grid; gap: 10px; margin: 14px 0 22px; }
.specgrid .sg-row { display: grid; grid-template-columns: 168px minmax(0, 1fr) minmax(0, 1.25fr) minmax(0, .85fr) minmax(0, 1.3fr); gap: 14px; align-items: center; padding: 14px 16px; background: var(--surface); border: 1px solid var(--line); border-radius: 10px; }
.specgrid .sg-hd { background: none; border: 0; padding: 0 16px; }
.specgrid .sg-h { font-size: 12px; color: var(--muted); font-weight: 600; letter-spacing: .02em; }
.specgrid .sg-step { display: grid; grid-template-columns: 26px 1fr; column-gap: 8px; align-items: center; }
.specgrid .sg-n { grid-row: span 2; display: grid; place-items: center; width: 26px; height: 26px; border-radius: 50%; background: var(--accent); color: #fff; font-family: var(--font-mono); font-size: 13px; }
.specgrid .sg-name { font-size: 18px; font-weight: 800; color: var(--ink); line-height: 1.2; }
.specgrid .sg-purpose { font-size: 12.5px; font-weight: 700; color: var(--accent); line-height: 1.35; }
.specgrid .sg-cell { display: flex; flex-wrap: wrap; gap: 5px; align-items: center; }
.specgrid .sg-chip { display: inline-block; padding: 3px 9px; border-radius: 6px; background: var(--bg); border: 1px solid var(--line); font-size: 13px; line-height: 1.4; color: var(--ink); white-space: nowrap; }
.specgrid .sg-out .sg-chip { background: var(--accent-soft); border-color: transparent; color: var(--accent); font-weight: 700; }
.specgrid .sg-ex { background: var(--accent-soft); border-radius: 8px; padding: 8px 10px; }
.specgrid .sg-ex .sg-chip { background: var(--surface); }
.specgrid .sg-exl { width: 100%; font-size: 11.5px; color: var(--muted); }
.specgrid .sg-res { width: 100%; font-size: 13px; font-weight: 700; color: var(--accent); }
.specgrid .sg-res::before { content: '→ '; }
.specgrid .sg-see .sg-chip { background: none; border: 0; padding: 0 2px; color: var(--muted); font-size: 13px; }
.specgrid .sg-see .sg-chip { flex-basis: 100%; }
.specgrid .sg-see .sg-chip::before, .specgrid .sg-rule.has-key .sg-chip:not(.sg-key)::before { content: ''; display: inline-block; width: 4px; height: 4px; margin: 0 7px 3px 0; border-radius: 50%; background: var(--muted); opacity: .6; }
.specgrid .sg-rule.has-key .sg-chip:not(.sg-key) { background: none; border: 0; padding: 0 2px; color: var(--muted); font-size: 12.5px; }
.specgrid .sg-rule.has-key .sg-chip:not(.sg-key) { flex-basis: 100%; }
.specgrid .sg-chip.sg-key { width: fit-content; max-width: 100%; padding: 5px 12px 5px 10px; border: 2px solid var(--accent); border-radius: 7px; background: var(--surface); color: var(--ink); font-size: 16px; font-weight: 800; white-space: normal; }
.specgrid .sg-rule.has-key { align-content: center; }
.specgrid .sg-rule.has-key .sg-key { flex-basis: 100%; }
.specgrid .sg-out .sg-chip { font-size: 14px; padding: 5px 11px; }
.specgrid .sg-out .sg-chip::before { content: '⇒ '; opacity: .6; }
.specgrid .xv { width: 100%; }
.specgrid .xv-rank { display: grid; grid-template-columns: auto 1fr auto; gap: 4px 8px; align-items: center; font-size: 13px; }
.specgrid .xv-bn { color: var(--ink); font-weight: 600; }
.specgrid .xv-bt { height: 8px; border-radius: 4px; background: var(--surface); overflow: hidden; }
.specgrid .xv-bt i { display: block; height: 100%; border-radius: 0 4px 4px 0; background: var(--accent); }
.specgrid .xv-bv { font-family: var(--font-mono); font-size: 12.5px; color: var(--ink); text-align: right; }
.specgrid .xv-votes { display: flex; gap: 12px; }
.specgrid .xv-vote { display: flex; flex-direction: column; align-items: center; gap: 3px; font-size: 12px; color: var(--muted); }
.specgrid .xv-vote b { display: grid; place-items: center; width: 24px; height: 24px; border-radius: 50%; border: 2px solid var(--line); background: var(--surface); font-size: 13px; color: #fff; }
.specgrid .xv-vote.on b { background: var(--warn); border-color: var(--warn); }
.specgrid .xv-vote.on { color: var(--ink); font-weight: 600; }
.specgrid .xv-split .xv-in { display: flex; gap: 5px; margin-bottom: 6px; }
.specgrid .xv-bar { display: flex; gap: 2px; height: 24px; border-radius: 5px; overflow: hidden; font-size: 12px; font-weight: 700; }
.specgrid .xv-bar span { display: grid; place-items: center; white-space: nowrap; }
.specgrid .xv-bar .s1 { background: var(--accent); color: #fff; }
.specgrid .xv-bar .s2 { background: var(--surface); color: var(--muted); }
.specgrid .xv-gap .xv-track { position: relative; height: 8px; margin: 22px 6px 20px; border-radius: 4px; background: var(--surface); }
.specgrid .xv-seg { position: absolute; top: 0; height: 100%; background: var(--accent); }
.specgrid .xv-gap.over .xv-seg { background: var(--warn); }
.specgrid .xv-pt { position: absolute; top: 50%; width: 12px; height: 12px; margin: -6px 0 0 -6px; border-radius: 50%; background: var(--surface); border: 2px solid var(--muted); }
.specgrid .xv-pt.b { border-color: var(--warn); background: var(--warn); }
.specgrid .xv-pt em { position: absolute; top: -23px; left: 50%; transform: translateX(-50%); font-style: normal; font-size: 12px; white-space: nowrap; color: var(--ink); }
.specgrid .xv-pt.a em { top: auto; bottom: -20px; color: var(--muted); }
.specgrid .xv-th { position: absolute; top: -3px; bottom: -3px; width: 0; border-left: 2px dashed var(--ink); opacity: .55; }
.specgrid .xv-th em { position: absolute; bottom: -18px; left: 4px; font-style: normal; font-size: 11px; white-space: nowrap; }
.tm-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; margin: 10px 0 6px; }
.tm-card { padding: 14px 16px; border: 1px solid var(--line); border-radius: 10px; background: var(--surface); display: flex; flex-direction: column; gap: 8px; }
.tm-card.wide { grid-column: span 2; }
.tm-n { font-size: 17px; font-weight: 800; color: var(--accent); }
.tm-d { font-size: 14.5px; font-weight: 700; color: var(--ink); line-height: 1.6; }
.tm-fm { width: fit-content; padding: 4px 12px; border: 2px solid var(--accent); border-radius: 7px; font-weight: 800; font-size: 14.5px; color: var(--ink); }
.tm-r { display: grid; grid-template-columns: auto 1fr; gap: 8px; align-items: baseline; font-size: 13.5px; line-height: 1.65; color: var(--ink); }
.tm-k { padding: 1px 7px; border-radius: 5px; font-size: 11.5px; font-weight: 700; white-space: nowrap; }
.tm-k.k-ex { background: var(--good-soft); color: var(--good); }
.tm-k.k-why { background: var(--accent-soft); color: var(--accent); }
.tm-k.k-note { background: var(--bg); color: var(--muted); }
@media (max-width: 700px) { .tm-card.wide { grid-column: auto; } }
.tm-card svg.bell { width: 100%; max-width: 440px; height: auto; display: block; }
.tm-card svg.bell .ar { fill: var(--accent-soft); } .tm-card svg.bell .cv { fill: none; stroke: var(--accent); stroke-width: 2; }
.tm-card svg.bell .ax { stroke: var(--line); } .tm-card svg.bell .t0 { stroke: var(--ink); stroke-width: 1.5; stroke-dasharray: 3 3; }
.tm-card svg.bell .tk { fill: var(--muted); font-size: 11px; } .tm-card svg.bell .lb { fill: var(--ink); font-size: 12px; font-weight: 700; }
.tm-card svg.bell .ar-lb { fill: var(--accent); font-size: 13px; font-weight: 800; }
.calcgrid { margin: 18px 0 20px; border: 1px solid var(--line); border-radius: 12px; background: var(--surface); overflow: hidden; }
.calcgrid .cg-title { padding: 12px 18px; font-size: 17px; font-weight: 800; color: var(--ink); border-bottom: 1px solid var(--line); background: var(--accent-soft); }
.calcgrid .cg-grid { display: grid; grid-template-columns: 96px repeat(var(--n), minmax(0, 1fr)) minmax(0, .8fr); }
.calcgrid .cg-grid > div { padding: 12px 14px; border-bottom: 1px solid var(--line); }
.calcgrid .cg-hd { background: var(--bg); display: flex; flex-direction: column; gap: 4px; }
.calcgrid .cg-hd.cg-lab { justify-content: flex-end; font-size: 12.5px; color: var(--muted); }
.calcgrid .cg-step { position: relative; border-left: 1px solid var(--line); }
.calcgrid .cg-step + .cg-step::before, .calcgrid .cg-out::before { content: '→'; position: absolute; left: -9px; top: 12px; width: 16px; height: 16px; border-radius: 50%; background: var(--surface); color: var(--accent); font-size: 12px; line-height: 16px; text-align: center; font-weight: 800; }
.calcgrid .cg-out { position: relative; border-left: 1px solid var(--line); }
.calcgrid .cg-n { color: var(--accent); font-weight: 800; font-size: 15px; }
.calcgrid .cg-verb { font-size: 15px; font-weight: 800; color: var(--ink); }
.calcgrid .cg-body { font-size: 13px; color: var(--ink); line-height: 1.5; }
.calcgrid .cg-body.cg-fm { width: fit-content; max-width: 100%; padding: 4px 10px; border: 2px solid var(--accent); border-radius: 7px; background: var(--surface); font-size: 14px; font-weight: 800; white-space: nowrap; }
.calcgrid .num { all: unset; }
.calcgrid .cg-sub { font-size: 12px; color: var(--muted); }
.calcgrid .cg-lab.cg-row { display: flex; align-items: center; font-weight: 800; font-size: 14px; border-left: 4px solid var(--line); }
.calcgrid .cg-lab.cg-row.good { border-left-color: var(--good); }
.calcgrid .cg-lab.cg-row.bad { border-left-color: var(--warn); }
.calcgrid .cg-c { border-left: 1px solid var(--line); display: flex; flex-direction: column; justify-content: center; gap: 2px; }
.calcgrid .cg-multi { flex-direction: row; flex-wrap: wrap; gap: 6px 16px; justify-content: flex-start; align-items: center; }
.calcgrid .cg-kv { display: flex; flex-direction: column; }
.calcgrid .cg-kv em, .calcgrid .cg-big em { font-style: normal; font-size: 11.5px; color: var(--muted); }
.calcgrid .cg-kv b { font-family: var(--font-mono); font-size: 15px; color: var(--ink); }
.calcgrid .cg-big b { font-family: var(--font-mono); font-size: 24px; line-height: 1.1; font-weight: 800; }
.calcgrid .cg-big.good b { color: var(--good); }
.calcgrid .cg-big.bad b { color: var(--warn); }
.calcgrid .cg-bar { display: block; height: 8px; margin-top: 6px; border-radius: 4px; background: var(--bg); overflow: hidden; }
.calcgrid .cg-bar i { display: block; height: 100%; border-radius: 4px; }
.calcgrid .cg-big.good .cg-bar i { background: var(--good); }
.calcgrid .cg-big.bad .cg-bar i { background: var(--warn); }
.calcgrid .cg-res span { font-size: 12.5px; color: var(--muted); }
.calcgrid .cg-res b { font-size: 18px; font-weight: 800; color: var(--ink); }
.calcgrid .cg-foot { display: grid; grid-template-columns: minmax(0, 440px) 1fr; gap: 8px 24px; align-items: center; padding: 14px 18px 16px; }
.calcgrid svg.phi { width: 100%; height: auto; display: block; }
.calcgrid svg.phi .ax { stroke: var(--line); stroke-width: 1; }
.calcgrid svg.phi .mid { stroke: var(--muted); stroke-width: 1; stroke-dasharray: 3 4; opacity: .6; }
.calcgrid svg.phi .crv { fill: none; stroke: var(--accent); stroke-width: 2.5; }
.calcgrid svg.phi .tk { fill: var(--muted); font-size: 11px; }
.calcgrid svg.phi .pt { stroke: var(--surface); stroke-width: 2; }
.calcgrid svg.phi .pt.good { fill: var(--good); } .calcgrid svg.phi .pt.bad { fill: var(--warn); }
.calcgrid svg.phi .drop { stroke-width: 1.5; stroke-dasharray: 2 3; } .calcgrid svg.phi .drop.good { stroke: var(--good); } .calcgrid svg.phi .drop.bad { stroke: var(--warn); }
.calcgrid svg.phi .lb { font-size: 12px; font-weight: 700; } .calcgrid svg.phi .lb.good { fill: var(--good); } .calcgrid svg.phi .lb.bad { fill: var(--warn); }
.calcgrid .cg-note { margin: 0; font-size: 13.5px; line-height: 1.7; color: var(--ink); }
.calcgrid .cg-note b { display: block; font-size: 12.5px; color: var(--muted); margin-bottom: 2px; }
@media (max-width: 900px) {
  .calcgrid .cg-grid { grid-template-columns: 1fr; }
  .calcgrid .cg-hd.cg-lab { display: none; }
  .calcgrid .cg-step, .calcgrid .cg-out, .calcgrid .cg-c { border-left: 0; }
  .calcgrid .cg-step + .cg-step::before, .calcgrid .cg-out::before { display: none; }
  .calcgrid .cg-c::before { content: attr(data-lb); font-size: 11.5px; font-weight: 700; color: var(--accent); }
  .calcgrid .cg-multi::before { flex-basis: 100%; }
  .calcgrid .cg-foot { grid-template-columns: 1fr; }
}
@media (max-width: 900px) {
  .specgrid .sg-hd { display: none; }
  .specgrid .sg-row { grid-template-columns: 1fr; gap: 8px; }
  .specgrid .sg-cell::before { content: attr(data-lb); width: 100%; font-size: 11.5px; color: var(--muted); }
}
ol.flow > li:has(.fl-x) { display: flex; flex-direction: column; }
ol.flow > li:has(.fl-x) > .fl-d { flex: 1; display: flex; flex-direction: column; gap: 10px; }
ol.flow > li:has(.fl-x) .fl-x { margin-top: auto; }
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

CSS += r"""
.sens-axis { margin: 10px 0 16px; padding: 14px 16px 6px; background: var(--surface); border: 1px solid var(--line); border-radius: 12px; }
.sa-cap { font-size: 13px; color: var(--muted); margin-bottom: 34px; }
.sa-track { position: relative; height: 44px; border-bottom: 1px solid var(--line); }
.sa-zone { position: absolute; top: 0; bottom: 0; background: color-mix(in srgb, var(--muted) 12%, transparent); border-radius: 4px; }
.sa-base { position: absolute; top: -26px; bottom: 0; border-left: 2px dashed var(--ink); }
.sa-base span { position: absolute; top: -4px; left: 6px; font-size: 12px; font-weight: 700; white-space: nowrap; }
.sm { position: absolute; top: 18px; height: 12px; }
.sm.d { width: 14px; height: 14px; margin-left: -7px; top: 17px; border-radius: 50%; }
.sm.r { border-radius: 6px; }
.sm.sk-good { background: var(--good); } .sm.sk-bad { background: var(--bad); } .sm.sk-warn { background: #fff; border: 3px solid #a16207; box-sizing: border-box; }
.sl-lab { position: absolute; top: 34px; transform: translateX(-50%); font-size: 11.5px; font-weight: 600; white-space: nowrap; padding-top: 12px; }
.sl-lab.sk-good { color: var(--good); } .sl-lab.sk-bad { color: var(--bad); } .sl-lab.sk-warn { color: #a16207; }
.sa-ticks { position: relative; height: 58px; margin-top: 0; }
.sa-ticks .st { top: 44px !important; }
.sa-ticks .st { position: absolute; top: 26px; transform: translateX(-50%); font-family: var(--font-mono); font-size: 11.5px; color: var(--muted); }
.cards .card.sens { border-top: 4px solid var(--line); }
.cards .card.sk-good { border-top-color: var(--good); } .cards .card.sk-bad { border-top-color: var(--bad); } .cards .card.sk-warn { border-top: 4px dashed #a16207; background: color-mix(in srgb, #a16207 5%, var(--surface)); }
.card.sk-good .cv { color: var(--good); } .card.sk-bad .cv { color: var(--bad); } .card.sk-warn .cv { color: #a16207; }
.sens-tag { display: inline-block; font-size: 11.5px; font-weight: 700; border-radius: 4px; padding: 1px 7px; margin: 4px 0 2px; }
.sk-good .sens-tag { color: var(--good); background: color-mix(in srgb, var(--good) 10%, transparent); }
.sk-bad .sens-tag { color: var(--bad); background: color-mix(in srgb, var(--bad) 10%, transparent); }
.sk-warn .sens-tag { color: #a16207; background: color-mix(in srgb, #a16207 12%, transparent); }
.sens-tag { align-self: flex-start; width: fit-content; }
.cards.sens-cards { grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); }
"""

CSS += r"""
.gl-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 12px; margin: 8px 0 12px; }
.gl-card { background: var(--surface); border: 1px solid var(--line); border-top: 4px solid var(--muted); border-radius: 10px; padding: 12px 16px 14px; }
.gl-card.wide { grid-column: 1 / -1; }
.gl-card.t-main { border-top-color: var(--accent); background: linear-gradient(180deg, var(--accent-soft), var(--surface) 60px); }
.gl-card.t-peer { border-top-color: #7c3aed; } .gl-card.t-off { border-top-color: #a16207; } .gl-card.t-ref { border-top-color: var(--ink); }
.gl-n { font-size: 17px; font-weight: 800; color: var(--ink); display: flex; align-items: center; gap: 8px; }
.gl-tag { font-size: 11.5px; font-weight: 700; border-radius: 4px; padding: 1px 7px; color: #fff; background: var(--muted); }
.t-main .gl-tag { background: var(--accent); } .t-peer .gl-tag { background: #7c3aed; } .t-off .gl-tag { background: #a16207; }
.gl-pos { font-size: 14px; font-weight: 600; color: var(--accent); margin: 4px 0 10px; }
.t-peer .gl-pos { color: #7c3aed; } .t-off .gl-pos { color: #a16207; } .t-ref .gl-pos { color: var(--muted); }
.gl-r { display: grid; grid-template-columns: 3.4em minmax(0, 1fr); gap: 8px; align-items: baseline; padding: 5px 0; border-top: 1px dashed var(--line); font-size: 14px; line-height: 1.6; }
.gl-k { justify-self: start; font-size: 11.5px; font-weight: 700; border-radius: 4px; padding: 0 6px; }
.gl-k.k-pick { color: var(--accent); background: var(--accent-soft); }
.gl-k.k-sell { color: var(--bad); background: color-mix(in srgb, var(--bad) 10%, transparent); }
.gl-k.k-def { color: var(--good); background: color-mix(in srgb, var(--good) 10%, transparent); }
.gl-k.k-size { color: #7c3aed; background: color-mix(in srgb, #7c3aed 10%, transparent); }
.gl-k.k-pace { color: var(--muted); background: var(--bg); border: 1px solid var(--line); }
.gl-bar { display: flex; height: 26px; border-radius: 6px; overflow: hidden; margin: 2px 0 8px; }
.gl-bar span { display: flex; align-items: center; justify-content: center; color: #fff; font-size: 12px; font-weight: 700; white-space: nowrap; overflow: hidden; }
.gl-legend { display: flex; flex-wrap: wrap; gap: 4px 14px; font-size: 12.5px; color: var(--ink); margin: -2px 0 8px; }
.gl-legend i { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 5px; vertical-align: -1px; }
.gl-subs { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 10px; }
.gl-sub { border: 1px solid var(--line); border-radius: 8px; padding: 8px 12px; background: var(--bg); }
.gl-sk { font-weight: 700; font-size: 14px; color: var(--ink); margin-bottom: 2px; }
.gl-sv { font-size: 13.5px; line-height: 1.6; color: var(--ink); }
"""

CSS += r"""
.rr-fig { margin: 10px 0 14px; padding: 12px 16px; background: var(--surface); border: 1px solid var(--line); border-radius: 12px; }
.rr-cap { font-size: 13px; color: var(--muted); margin-bottom: 4px; }
.rr-svg { width: 100%; max-width: 900px; height: auto; display: block; }
.rr-t { font-size: 11px; fill: var(--muted); font-family: var(--font-mono); }
.rr-g { stroke: var(--line); stroke-width: 1; }
.rr-ref { stroke: var(--ink); stroke-width: 1.2; stroke-dasharray: 4 3; }
.rr-q { fill: color-mix(in srgb, var(--good) 8%, transparent); }
.rr-ql { font-size: 11px; fill: var(--good); font-weight: 700; }
.rr-p { stroke: var(--surface); stroke-width: 2; }
.rr-p.rr-good { fill: var(--good); } .rr-p.rr-mid { fill: #a16207; } .rr-p.rr-bad { fill: var(--bad); } .rr-p.rr-ref { fill: var(--ink); } .rr-p.rr-other { fill: var(--muted); }
.rr-l { font-size: 11.5px; fill: var(--muted); paint-order: stroke; stroke: var(--surface); stroke-width: 4px; stroke-linejoin: round; } .rr-l.m { font-weight: 700; font-size: 12.5px; }
.rr-l.rr-good { fill: var(--good); } .rr-l.rr-mid { fill: #a16207; } .rr-l.rr-bad { fill: var(--bad); } .rr-l.rr-ref { fill: var(--ink); font-weight: 700; }
.cards .card.rr { border-top: 4px solid var(--line); }
.cards .card.rr-good { border-top-color: var(--good); } .cards .card.rr-mid { border-top-color: #a16207; } .cards .card.rr-bad { border-top-color: var(--bad); }
.card.rr-good .cv { color: var(--good); } .card.rr-mid .cv { color: #a16207; } .card.rr-bad .cv { color: var(--bad); }
.rr-chips { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin: 2px 0 8px; }
.rr-vs { font-size: 11.5px; color: var(--muted); }
.rr-c { font-size: 12px; font-weight: 700; border-radius: 4px; padding: 0 6px; }
.rr-c.g { color: var(--good); background: color-mix(in srgb, var(--good) 10%, transparent); }
.rr-c.b { color: var(--bad); background: color-mix(in srgb, var(--bad) 10%, transparent); }
.cards.rr-cards { grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); }
p.kv.kv-warn { border: 1px solid color-mix(in srgb, #a16207 45%, var(--line)); border-left: 4px solid #a16207; background: color-mix(in srgb, #a16207 6%, var(--surface)); border-radius: 10px; padding: 12px 16px; margin-top: 12px; }
p.kv.kv-warn .kv-k { color: #a16207; }
p.kv.kv-warn .kv-k::before { content: '⚠'; width: auto; height: auto; background: none; color: #a16207; border-radius: 0; margin-right: 6px; }
"""

CSS += r"""
.cards.dx-cards { grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); }
.cards .card.dx { border-top: 4px solid var(--bad); display: flex; flex-direction: column; gap: 8px; }
.cards .card.dxc-mid { border-top-color: #a16207; }
.dx-n { font-size: 12.5px; font-weight: 700; color: var(--accent); background: var(--accent-soft); border-radius: 5px; padding: 1px 8px; }
.dx-d { font-size: 18px; font-weight: 800; line-height: 1.4; color: var(--bad); }
.dxc-mid .dx-d { color: #a16207; }
.dx-g { background: var(--bg); border-radius: 8px; padding: 8px 10px; }
.dx-gl { font-size: 11.5px; color: var(--muted); margin-bottom: 4px; }
.dx-gb { position: relative; height: 10px; background: var(--surface); border: 1px solid var(--line); border-radius: 5px; }
.dx-gb i { position: absolute; left: 0; top: 0; bottom: 0; border-radius: 5px; }
.dx-gb i.g { background: var(--good); } .dx-gb i.b { background: var(--bad); }
.dx-gb em { position: absolute; top: -4px; bottom: -4px; border-left: 2px dashed var(--ink); }
.dx-gv { display: flex; justify-content: space-between; margin-top: 4px; font-size: 12px; }
.dx-gv b { font-family: var(--font-mono); font-size: 15px; } .dx-gv b.g { color: var(--good); } .dx-gv b.b { color: var(--bad); }
.dx-gv span { color: var(--muted); }
.dx-rows { display: grid; gap: 6px; }
.dx-r { display: grid; grid-template-columns: 18px minmax(0, 1fr); gap: 6px; font-size: 14px; line-height: 1.6; }
.dx-i { width: 16px; height: 16px; border-radius: 50%; margin-top: 4px; display: grid; place-items: center; font-size: 10px; font-weight: 800; color: #fff; background: var(--muted); }
.dx-i::before { content: '·'; }
.dx-bad .dx-i { background: var(--bad); } .dx-bad .dx-i::before { content: '✕'; }
.dx-good .dx-i { background: var(--good); } .dx-good .dx-i::before { content: '✓'; }
b.sg-pos { color: var(--good); font-family: var(--font-mono); } b.sg-neg { color: var(--bad); font-family: var(--font-mono); }
"""


CSS += r"""
/* ledger cards: one card per case, cost large, tripwire at the foot */
.ledger { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 12px; margin: 14px 0 20px; }
.ledger .lg { background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 12px 16px 10px; display: flex; flex-direction: column; gap: 6px; }
.ledger .lg-h { font-size: 13.5px; font-weight: 700; color: var(--accent); line-height: 1.5; }
.ledger .lg-n { display: inline-grid; place-items: center; min-width: 20px; height: 20px; border-radius: 50%; background: var(--accent); color: #fff; font-family: var(--font-mono); font-size: 11.5px; margin-right: 8px; vertical-align: 1px; }
.ledger .lg-big.t-good { color: var(--good); } .ledger .lg-big.t-warn { color: var(--warn); } .ledger .lg-big.t-bad { color: var(--bad); }
.ledger .lg-big { font-size: 19px; line-height: 1.35; font-weight: 700; color: var(--ink); }
.ledger .lg-bl { font-size: 12px; color: var(--muted); margin-top: -4px; }
.ledger .lg-m { font-size: 14px; color: var(--muted); line-height: 1.6; }
.ledger .lg-t { color: var(--ink); }
.ledger .lg-t b, .ledger .lg-t strong { font-weight: 600; }
.ledger .lg-k { display: inline-block; font-size: 12px; color: var(--muted); background: var(--bg); border-radius: 4px; padding: 0 6px; margin-right: 6px; }
.ledger .lg-f { margin-top: auto; padding-top: 8px; border-top: 1px dashed var(--line); font-size: 14px; color: var(--ink); line-height: 1.6; }
.ledger .lg-f.trip { color: var(--bad); }
.ledger .lg-f.trip .lg-k { color: var(--bad); background: color-mix(in srgb, var(--bad) 10%, transparent); }
.ledger .lg-fi { font-weight: 700; margin-right: 4px; }
.ledger.n4 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
@media (max-width: 700px) { .ledger.n4 { grid-template-columns: minmax(0, 1fr); } }
.ledger .lg-chips { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 4px; }
.ledger .lg-c { font-size: 12.5px; color: var(--ink); background: var(--bg); border: 1px solid var(--line); border-radius: 999px; padding: 1px 9px; line-height: 1.6; }
"""

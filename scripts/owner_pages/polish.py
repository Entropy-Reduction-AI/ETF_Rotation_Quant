"""Second-pass presentation layer: turns plain converted HTML into scannable, story-driven elements.

Every rule keys off the content itself (headers, values, the author's own bold), never off guesses.
"""
import re
from bs4 import BeautifulSoup, NavigableString

SIGNED = re.compile(r'^[+\-−]\d[\d.,]*(%|pp)?$')
SIGNED_ANY = re.compile(r'(?<![\w.\d])([+\-−]\d[\d.,]*(?:%|pp)?)')
NUMERIC = re.compile(r'^[+\-−]?[约≈~]?\d[\d.,]*\s*(%|pp|倍|个|只|元|天|年|次|个点|个月)?$')

SUBJECT = {
    'oneshot': ('E2 新口径',),
    'v51-health': ('v5.1',),
    'v5-memo': ('v5.1', 'v5 ', 'v5：', 'v5 最终版'),
    'v4-health': ('E2',),
    'v4-memo': ('T1', 'v4'),
}
TAKEAWAY_HEAD = ('读法', '结论', '这说明什么', '当时的推论', '谁好')
NOTE_HEAD = ('说明', '为什么', '差在哪', '钱从哪来', '例子', '备注', '为什么这样定', '影响有多大', '对我们有什么用')
DEF_HEAD = {('问题', '回答'), ('项目', '内容'), ('节点', '内容'), ('页面', '回答什么'), ('决定', '内容')}


def txt(el):
    return el.get_text(' ', strip=True) if el is not None else ''


def num_val(s):
    s = s.strip().replace('−', '-').replace('%', '').replace('pp', '').replace(',', '').replace(' ', '')
    try:
        return float(s)
    except ValueError:
        return None


def add_class(el, *cls):
    cur = el.get('class', [])
    for c in cls:
        if c not in cur:
            cur.append(c)
    el['class'] = cur


def leaf_heads(t):
    """One header cell per body column, also for two-row (group + sub) headers."""
    trs = t.select('thead tr')
    if len(trs) == 2 and 'grp' in (trs[0].get('class') or []):
        subs = iter(trs[1].find_all('th'))
        out = []
        for th in trs[0].find_all('th'):
            if th.get('colspan'):
                out.extend(next(subs) for _ in range(int(th['colspan'])))
            else:
                out.append(th)
        return out
    return t.select('thead th')


def table_grid(t):
    heads = leaf_heads(t)
    rows = [tr for tr in t.select('tbody tr')]
    return heads, rows


def wrap_of(t):
    p = t.parent
    return p if p is not None and 'table-wrap' in (p.get('class') or []) else t


# ---------- table types that become other elements ----------

def table_to_cards(soup, t, kind='plain'):
    heads, rows = table_grid(t)
    cells = rows[0].find_all('td') if rows else []
    grid = soup.new_tag('div', attrs={'class': ['cards', 'from-table', kind]})
    for i, h in enumerate(heads):
        if i >= len(cells):
            break
        c = soup.new_tag('div', attrs={'class': ['card', f'tone-{i}']})
        title = soup.new_tag('div', attrs={'class': ['ct']})
        title.string = txt(h)
        c.append(title)
        body = soup.new_tag('div', attrs={'class': ['cb']})
        for ch in list(cells[i].contents):
            body.append(ch.extract() if hasattr(ch, 'extract') else ch)
        c.append(body)
        grid.append(c)
    wrap_of(t).replace_with(grid)


def options_to_cards(soup, t):
    heads, rows = table_grid(t)
    grid = soup.new_tag('div', attrs={'class': ['options']})
    for tr in rows:
        tds = tr.find_all('td')
        if not tds:
            continue
        rec = any('建议' in txt(td) for td in tds)
        card = soup.new_tag('div', attrs={'class': ['option'] + (['rec'] if rec else [])})
        name = soup.new_tag('div', attrs={'class': ['on']})
        # strip the trailing "建议" word in the name cell, show as badge instead
        for ch in list(tds[0].contents):
            name.append(ch.extract())
        for s in name.find_all(string=re.compile('建议')):
            s.replace_with(s.replace('建议', '').rstrip())
        if rec:
            b = soup.new_tag('span', attrs={'class': ['badge']})
            b.string = '★ 建议'
            name.append(b)
        card.append(name)
        if len(tds) > 1:
            d = soup.new_tag('div', attrs={'class': ['od']})
            for ch in list(tds[1].contents):
                d.append(ch.extract())
            card.append(d)
        grid.append(card)
    wrap_of(t).replace_with(grid)


# ---------- header grouping ----------

def group_headers(soup, t):
    thead = t.find('thead')
    if not thead or len(thead.find_all('tr')) > 1:
        return
    tr = thead.find('tr')
    ths = tr.find_all('th')
    parts = []
    for th in ths:
        s = txt(th)
        m = re.match(r'^(.+?)\s*·\s*(.+)$', s) or re.match(r'^(.+?池子?)\s+(.+)$', s) or re.match(r'^(.+?)\s+(\d{4}[–-]\d{2,4})$', s)
        parts.append((m.group(1).strip(), m.group(2).strip()) if m else (None, s))
    # find runs of equal prefixes
    runs, i = [], 0
    while i < len(parts):
        j = i
        while j + 1 < len(parts) and parts[i][0] and parts[j + 1][0] == parts[i][0]:
            j += 1
        runs.append((i, j))
        i = j + 1
    if not any(b > a for a, b in runs):
        return
    top = soup.new_tag('tr', attrs={'class': ['grp']})
    sub = soup.new_tag('tr', attrs={'class': ['sub']})
    for a, b in runs:
        if b > a:
            th = soup.new_tag('th', attrs={'colspan': str(b - a + 1), 'class': ['gh']})
            th.string = parts[a][0]
            top.append(th)
            for k in range(a, b + 1):
                old = ths[k]
                nt = soup.new_tag('th', attrs={k2: v for k2, v in old.attrs.items()})
                nt.string = parts[k][1]
                sub.append(nt)
        else:
            old = ths[a]
            old['rowspan'] = '2'
            top.append(old.extract())
    tr.replace_with(top)
    top.insert_after(sub)


# ---------- the main table pass ----------

def polish_table(soup, t, slug):
    heads, rows = table_grid(t)
    H = [txt(h) for h in heads]
    ncol = len(H)
    if not rows:
        return
    body_cells = [r.find_all('td') for r in rows]

    # 2. option tables with a recommendation
    if ncol >= 2 and H[0] == '选项':
        options_to_cards(soup, t)
        return
    # 1. single-row tables -> cards (the page-opening status table gets status tones)
    if len(rows) == 1 and 2 <= ncol <= 4 and all(len(r) == ncol for r in body_cells):
        table_to_cards(soup, t, 'status' if {'需要你'} & set(H) else 'plain')
        return
    # 3. definition tables
    if ncol == 2 and (tuple(H) in DEF_HEAD or (sum(len(txt(r[1])) for r in body_cells if len(r) > 1) / len(rows) > 40 and sum(len(txt(r[0])) for r in body_cells if r) / len(rows) < 12)):
        add_class(t, 'deflist')
        for r in body_cells:
            if not r:
                continue
            lab = txt(r[0])
            if lab.startswith('原规则'):
                add_class(r[0].parent, 'was')
            elif lab.startswith('新规则'):
                add_class(r[0].parent, 'now')
            elif lab.startswith('改的是'):
                add_class(r[0].parent, 'what')
        return

    # column roles
    subj = SUBJECT.get(slug, ())
    roles = {}
    for i, h in enumerate(H):
        if i == 0:
            continue
        if any(h.startswith(s) or h == s.strip() for s in subj):
            roles[i] = 'subj'
        elif any(h.startswith(k) for k in TAKEAWAY_HEAD):
            roles[i] = 'take'
        elif any(h.startswith(k) for k in NOTE_HEAD):
            roles[i] = 'note'
    # subject rows (when strategies are rows)
    subj_rows = not any(v == 'subj' for v in roles.values()) and bool(subj)

    # signed (difference) columns -> heat
    signed_cols = {}
    for ci in range(ncol):
        vals = []
        for r in body_cells:
            if len(r) > ci:
                s = txt(r[ci])
                if SIGNED.match(s.replace(' ', '')):
                    vals.append(s)
        has_pos = any(v.startswith('+') for v in vals)
        has_neg = any(v[0] in '-−' for v in vals)
        if vals and has_pos and has_neg and len(vals) >= max(2, sum(1 for r in body_cells if len(r) > ci and txt(r[ci])) * 0.6):
            signed_cols[ci] = max(abs(num_val(v) or 0) for v in vals) or 1
    if signed_cols:
        for ci in range(ncol):
            if ci in signed_cols:
                continue
            vals = [txt(r[ci]) for r in body_cells if len(r) > ci and txt(r[ci])]
            h = H[ci] if ci < len(H) else ''
            if len(vals) >= 2 and all(SIGNED.match(v.replace(' ', '')) for v in vals) and '回撤' not in h and '跌' not in h:
                signed_cols[ci] = max(abs(num_val(v) or 0) for v in vals) or 1

    # numeric columns: one alignment and one face for the whole column
    for ci in range(1, ncol):
        vals = [txt(r[ci]).replace(' ', '') for r in body_cells if len(r) > ci and txt(r[ci]) not in ('', '—', '-', '–')]
        if vals and sum(1 for v in vals if NUMERIC.match(v) or SIGNED.match(v)) / len(vals) >= 0.6:
            for r in body_cells:
                if len(r) > ci:
                    add_class(r[ci], 'numcol')
            if ci < len(heads):
                add_class(heads[ci], 'numcol')

    # author emphasis is meaningful only when it is selective
    tds_all = [td for r in body_cells for td in r]
    bold_ratio = sum(1 for td in tds_all if td.find('strong')) / max(1, len(tds_all))
    selective_bold = bold_ratio < 0.45

    verdict_counts = {'good': 0, 'bad': 0, 'warn': 0}
    verdict_words = {'good': {}, 'bad': {}, 'warn': {}}
    for r in body_cells:
        tr = r[0].parent if r else None
        for ci, td in enumerate(r):
            role = roles.get(ci)
            if role:
                add_class(td, f'c-{role}')
            s = txt(td).replace(' ', '')
            if ci in signed_cols and SIGNED.match(s):
                v = num_val(s)
                if v is None:
                    continue
                a = min(1.0, abs(v) / signed_cols[ci])
                tone = 'g' if v > 0 else ('r' if v < 0 else 'k')
                w = max(4, round(70 * a))
                strong = td.find('strong') is not None
                td.clear()
                td.append(BeautifulSoup(f'<span class="ib"><i class="{tone}" style="width:{w}px"></i><em class="{tone}">{s}</em></span>', 'html.parser'))
                add_class(td, 'ibc')
            elif ci > 0 and selective_bold and td.find('strong') and NUMERIC.match(txt(td).replace(' ', '')):
                add_class(td, 'key')
            pill = td.find('span', class_='pill')
            if pill is not None and ci > 0:
                k = next((c for c in ('good', 'bad', 'warn') if c in pill.get('class', [])), None)
                if k:
                    verdict_counts[k] += 1
                    w = pill.get_text()
                    verdict_words[k][w] = verdict_words[k].get(w, 0) + 1
                    is_verdict_col = ci == len(r) - 1 or (ci < len(H) and any(H[ci].startswith(v) for v in ('判定', '结论', '结果', '状态', '对了吗', '对上了吗', '做到了吗')))
                    if tr is not None and is_verdict_col:
                        add_class(tr, f'row-{k}')
                # the words after the pill become a quiet note under it
                rest = []
                for sib in list(pill.next_siblings):
                    rest.append(sib.extract())
                if any((x.strip() if isinstance(x, str) else txt(x)) for x in rest):
                    note = soup.new_tag('span', attrs={'class': ['pill-note']})
                    for x in rest:
                        note.append(x)
                    pill.insert_after(note)
        if subj_rows and r and any(txt(r[0]).startswith(s.strip()) for s in subj):
            add_class(tr, 'row-subj')
    for i, h in enumerate(heads):
        if roles.get(i):
            add_class(h, f'h-{roles[i]}')

    group_headers(soup, t)

    # scorecard over verdict tables
    total = sum(verdict_counts.values())
    if total >= 4 and verdict_counts['good'] + verdict_counts['bad'] >= 3 and len(rows) >= 4:
        bar = soup.new_tag('div', attrs={'class': ['score']})
        segs = soup.new_tag('div', attrs={'class': ['seg']})
        for k in ('good', 'warn', 'bad'):
            n = verdict_counts[k]
            if n:
                sp = soup.new_tag('span', attrs={'class': [f's-{k}'], 'style': f'flex:{n}'})
                segs.append(sp)
        bar.append(segs)
        lab = soup.new_tag('div', attrs={'class': ['sl']})
        bits = []
        for k in ('good', 'warn', 'bad'):
            n = verdict_counts[k]
            if n:
                word = max(verdict_words[k].items(), key=lambda x: x[1])[0] if len(verdict_words[k]) == 1 else {'good': '通过', 'warn': '待定', 'bad': '没过'}[k]
                bits.append(f'<b class="t-{k}">{n}</b> {word}')
        lab.append(BeautifulSoup(' · '.join(bits) + f'<span class="of"> / 共 {total} 项</span>', 'html.parser'))
        bar.append(lab)
        wrap_of(t).insert_before(bar)


VERDICT_PREFIXED = re.compile(r'^((?:E2|A1|A2|v5\.1|v5|T\d)[^，。：]{0,6}?\s*)(不通过|没通过|未通过|没过|通过|过关|不入围|入围)(.*)$', re.S)


def prefixed_verdicts(soup):
    for t in soup.select('table'):
        heads = [txt(h) for h in t.select('thead th')]
        cols = {i for i, h in enumerate(heads) if any(h.startswith(v) for v in ('结论', '判定', '结果'))}
        for tr in t.select('tbody tr'):
            tds = tr.find_all('td')
            for ci in cols:
                if ci >= len(tds) or tds[ci].find('span', class_='pill'):
                    continue
                m = VERDICT_PREFIXED.match(txt(tds[ci]))
                if not m:
                    continue
                who, word, rest = m.groups()
                k = 'bad' if word in ('不通过', '没通过', '未通过', '没过', '不入围') else 'good'
                tds[ci].clear()
                tds[ci].append(BeautifulSoup(f'<span class="who">{who.strip()}</span><span class="pill {k}">{word}</span>' + (f'<span class="pill-note">{rest.strip("，, ")}</span>' if rest.strip('，, ') else ''), 'html.parser'))
                add_class(tr, f'row-{k}')


TRAIL = re.compile(r'^(.*\S)\s+(没达到|没达|未达到|达到|达)$')


def trailing_verdicts(soup):
    for td in soup.select('table td'):
        if td.find('span', class_='pill'):
            continue
        m = TRAIL.match(txt(td))
        if not m:
            continue
        val, word = m.groups()
        k = 'bad' if word.startswith(('没', '未')) else 'good'
        word = {'没达': '没达到', '达': '达到'}.get(word, word)
        strong = td.find('strong') is not None
        td.clear()
        v = f'<strong>{val}</strong>' if strong else val
        td.append(BeautifulSoup(f'<span class="tv">{v}</span><span class="pill {k}">{word}</span>', 'html.parser'))
        add_class(td, 'tvc')


def polish_lists(soup):
    for ul in soup.select('ul'):
        if ul.find_parent('nav') is not None:
            continue
        lis = ul.find_all('li', recursive=False)
        if len(lis) >= 2 and all(li.contents and getattr(next((c for c in li.contents if not (isinstance(c, str) and not c.strip())), None), 'name', None) == 'strong' for li in lis):
            add_class(ul, 'points')
    for ol in soup.select('ol'):
        if 'next' in (ol.get('class') or []) or ol.find_parent('nav') is not None:
            continue
        lis = ol.find_all('li', recursive=False)
        if len(lis) >= 2:
            add_class(ol, 'steps-n')
            if ol.get('start'):
                ol['style'] = f"counter-reset: st {int(ol['start']) - 1}"


def polish_notes(soup):
    for w in soup.select('div.table-wrap'):
        nxt = w.find_next_sibling()
        if nxt is not None and nxt.name == 'p' and len(txt(nxt)) <= 220 and not nxt.find('img'):
            add_class(nxt, 'table-note')



def split_compound(soup):
    """Header 'Group a · b · c' over cells 'x · y · z' -> a group header with one column per value."""
    for t in soup.select('table'):
        thead = t.find('thead')
        if thead is None or len(thead.find_all('tr')) != 1:
            continue
        ths = thead.find_all('th')
        rows = t.select('tbody tr')
        plan = {}
        for i, th in enumerate(ths):
            h = th.get_text(' ', strip=True)
            m = re.match(r'^(.*?)\s+(\S+(?:\s*·\s*\S+)+)$', h)
            if not m or i == 0:
                continue
            subs = [x.strip() for x in m.group(2).split('·')]
            ok = all(len(tr.find_all('td')) == len(ths) and len(tr.find_all('td')[i].get_text(strip=True).split('·')) == len(subs) for tr in rows)
            if ok and len(subs) >= 2:
                plan[i] = (m.group(1).strip(), subs)
        if not plan:
            continue
        top = soup.new_tag('tr', attrs={'class': ['grp']})
        sub = soup.new_tag('tr', attrs={'class': ['sub']})
        for i, th in enumerate(ths):
            if i in plan:
                g, subs = plan[i]
                gh = soup.new_tag('th', attrs={'class': ['gh'], 'colspan': str(len(subs))}); gh.string = g
                top.append(gh)
                for k, x in enumerate(subs):
                    st = soup.new_tag('th', attrs={'class': ['first-sub'] if k == 0 else []}); st.string = x
                    sub.append(st)
            else:
                th2 = th.extract(); th2['rowspan'] = '2'
                top.append(th2)
        thead.clear(); thead.append(top); thead.append(sub)
        for tr in rows:
            tds = tr.find_all('td')
            for i in sorted(plan, reverse=True):
                td = tds[i]
                vals = [x.strip() for x in td.get_text(strip=True).split('·')]
                new = []
                for k, v in enumerate(vals):
                    n = soup.new_tag('td', attrs={'class': ['first-sub'] if k == 0 else []}); n.string = v
                    new.append(n)
                td.replace_with(*new)
        add_class(t, 'split')


def polish(html, slug):
    soup = BeautifulSoup(html, 'html.parser')
    split_compound(soup)
    prefixed_verdicts(soup)
    trailing_verdicts(soup)
    for t in list(soup.select('table')):
        polish_table(soup, t, slug)
    enrich(soup)
    polish_lists(soup)
    polish_notes(soup)
    return str(soup)


CSS = r'''
/* ===== storytelling layer ===== */
/* status cards that open a page */
.cards.from-table { grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); }
.cards.from-table .card { border-top: 3px solid var(--line); }
.cards.from-table .ct { font-size: 12.5px; font-weight: 500; color: var(--muted); letter-spacing: .04em; }
.cards.from-table .cb { font-size: 14.5px; line-height: 1.75; }
.cards.status .tone-0 { border-top-color: var(--muted); }
.cards.status .tone-1 { border-top-color: var(--accent); }
.cards.status .tone-2 { border-top-color: var(--warn); }
.cards.status .tone-2 .ct { color: var(--warn); }
.cards.status .tone-1 .cb { font-size: 15px; }
.cards.plain .card { border-top-color: var(--accent); }

/* options with a recommendation */
.options { display: grid; gap: 10px; margin: 12px 0 18px; }
.option { display: grid; grid-template-columns: minmax(150px, 220px) minmax(0, 1fr); gap: 16px; align-items: start; background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 12px 16px; }
.option .on { font-weight: 700; display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.option .od { color: var(--muted); font-size: 14.5px; }
.option.rec { border-color: var(--accent); box-shadow: inset 3px 0 0 var(--accent); }
.option.rec .od { color: var(--ink); }
.option .badge { font-size: 12px; font-weight: 500; color: var(--accent); background: var(--accent-soft); border-radius: 999px; padding: 0 8px; }

/* definitions */
table.deflist thead { display: none; }
table.deflist td:first-child { width: 9.5em; color: var(--accent); font-weight: 700; border-right: 2px solid var(--accent-soft); }
table.deflist tr.was td { color: var(--muted); }
table.deflist tr.was td:last-child { text-decoration: line-through; text-decoration-color: var(--bad); }
table.deflist tr.now td { background: var(--good-soft); }
table.deflist tr.now td:first-child { color: var(--good); border-right-color: var(--good); }

/* grouped headers */
thead tr.grp th.gh { text-align: center; color: var(--ink); font-weight: 700; border-bottom: 1px solid var(--line); background: var(--bg); }
thead tr.sub th { font-size: 12px; }

/* column roles */
th.h-subj, td.c-subj { background: color-mix(in srgb, var(--accent) 7%, transparent); }
th.h-subj { color: var(--accent); font-weight: 700; }
td.c-take { font-weight: 500; color: var(--ink); border-left: 1px solid var(--line); }
th.h-take { border-left: 1px solid var(--line); color: var(--ink); }
td.c-note { color: var(--muted); font-size: 13.5px; }
tr.row-subj td { background: color-mix(in srgb, var(--accent) 6%, transparent); }
tr.row-subj td:first-child { box-shadow: inset 3px 0 0 var(--accent); color: var(--accent); }

/* numeric columns */
td.numcol, th.numcol { text-align: right; }
td.numcol { font-family: var(--font-mono); font-variant-numeric: tabular-nums; font-size: 14px; white-space: nowrap; }
thead tr.sub th.numcol, thead tr.grp th.numcol { text-align: right; }
/* heat cells for differences */
td.heat { font-family: var(--font-mono); font-variant-numeric: tabular-nums; font-weight: 500; text-align: right; white-space: nowrap; }
td.heat-pos { color: var(--good); background: color-mix(in srgb, var(--good) var(--h, 8%), transparent); }
td.heat-neg { color: var(--bad); background: color-mix(in srgb, var(--bad) var(--h, 8%), transparent); }
td.heat-zero { color: var(--muted); }
td.key { color: var(--accent); font-weight: 700; }
td.key strong { font-weight: 700; }

/* verdict rows */
tr.row-bad td { background: color-mix(in srgb, var(--bad) 5%, transparent); }
tr.row-bad td:first-child { box-shadow: inset 3px 0 0 var(--bad); }
tr.row-good td:first-child { box-shadow: inset 3px 0 0 var(--good); }
tr.row-warn td:first-child { box-shadow: inset 3px 0 0 var(--warn); }
tr.row-bad td.heat, tr.row-subj td.heat { background: color-mix(in srgb, var(--bad) var(--h, 8%), transparent); }
tr.row-bad td.heat-pos, tr.row-subj td.heat-pos { background: color-mix(in srgb, var(--good) var(--h, 8%), transparent); }
.tvc .tv { font-family: var(--font-mono); margin-right: 8px; }
.who { font-size: 12.5px; color: var(--muted); margin-right: 6px; }
.pill-note { display: block; font-size: 12.5px; color: var(--muted); margin-top: 3px; line-height: 1.5; }
td .pill { font-size: 12.5px; }

/* scorecard above verdict tables */
.score { display: flex; align-items: center; gap: 14px; margin: 14px 0 -6px; }
.score .seg { display: flex; gap: 3px; width: 200px; height: 8px; }
.score .seg span { border-radius: 2px; }
.score .s-good { background: var(--good); }
.score .s-warn { background: var(--warn); }
.score .s-bad { background: var(--bad); }
.score .sl { font-size: 13.5px; color: var(--muted); }
.score .sl b { font-family: var(--font-mono); font-size: 15px; }
.score .t-good { color: var(--good); } .score .t-bad { color: var(--bad); } .score .t-warn { color: var(--warn); }
.score .of { color: var(--muted); }

/* notes under tables read as captions */
p.table-note { font-size: 13px; color: var(--muted); margin-top: -12px; }

/* key-point lists */
ul.points { list-style: none; padding-left: 0; display: grid; gap: 8px; }
ul.points > li { padding: 2px 0 2px 14px; border-left: 3px solid var(--accent-soft); margin: 0; }
ul.points > li > strong:first-child { color: var(--ink); }
ol.steps-n { list-style: none; padding-left: 0; counter-reset: st; display: grid; gap: 6px; }
ol.steps-n > li { counter-increment: st; position: relative; padding-left: 34px; margin: 0; }
ol.steps-n > li::before { content: counter(st); position: absolute; left: 0; top: 3px; width: 22px; height: 22px; border-radius: 50%; background: var(--accent-soft); color: var(--accent); font-family: var(--font-mono); font-size: 12.5px; font-weight: 500; display: grid; place-items: center; }
'''


# ---------- enrichment pass (comment 2026-11-17: 表格还是太素) ----------
MAG_HEAD = re.compile(r'年化|回撤|收益|胜率|占比|仓位|波动|超额|赢|跑赢')
BAD_W = re.compile(r'难|没.?赢|赢得少|输|不通过|没过|不入围|不成立|错|亏|没兑现|不可用|失效|更差')
GOOD_W = re.compile(r'变好|通过|过关|赢|对|成立|兑现|更好|最好|最浅|达到')
PCT = re.compile(r'^([+\-−]?\d+(?:\.\d+)?)%$')


def _pct(s):
    m = PCT.match(s.replace(' ', ''))
    return float(m.group(1).replace('−', '-')) if m else None


def enrich(soup):
    for t in soup.find_all('table'):
        heads = leaf_heads(t)
        H = [txt(h) for h in heads]
        rows = [tr for tr in t.select('tbody tr') if 'grp' not in (tr.get('class') or [])]
        # 1. magnitude bars on percent columns
        for ci, h in enumerate(H):
            if ci == 0 or not MAG_HEAD.search(h):
                continue
            cells = []
            for tr in rows:
                tds = tr.find_all('td')
                if ci >= len(tds) or 'ibc' in (tds[ci].get('class') or []):
                    continue
                td = tds[ci]
                parts = td.get_text(' ', strip=True).split(' ', 1)
                v = _pct(parts[0]) if parts else None
                if v is None:
                    continue
                sec = parts[1] if len(parts) > 1 else ''
                m2 = re.search(r'([+\-−]?\d+(?:\.\d+)?)%', sec)
                cells.append((td, v, sec, float(m2.group(1).replace('−', '-')) if m2 else None, parts[0]))
            if len(cells) < 3:
                continue
            mx = max(max(abs(v), abs(s2 or 0)) for _, v, _, s2, _ in cells) or 1
            dd = '回撤' in h or all(v <= 0 for _, v, _, _, _ in cells)
            for td, v, sec, s2, raw in cells:
                key = 'key' in (td.get('class') or []) or td.find('strong') is not None
                tone = 'o' if dd else ('a' if key or 'row-subj' in (td.parent.get('class') or []) else 'm')
                w = round(64 * abs(v) / mx)
                mark = f'<i class="mk" style="left:{round(64 * abs(s2) / mx)}px" title="{sec}"></i>' if s2 is not None else ''
                main = raw.replace('-', '−')
                sub = f'<span class="mg-s">{sec}</span>' if sec else ''
                td.clear()
                td.append(BeautifulSoup(f'<span class="mg"><span class="mg-t"><i class="mg-b {tone}" style="width:{w}px"></i>{mark}</span><span class="mg-v{" strong" if key else ""}">{main}</span></span>{sub}', 'html.parser'))
                add_class(td, 'mgc')
        # 2. leading bold verdict phrase in conclusion cells -> tag
        for tr in rows:
            tds_ = tr.find_all('td')
            for ci_, td in enumerate(tds_):
                if ci_ == 0:
                    continue
                is_last_verdict = ci_ == len(tds_) - 1 and any(re.search(r'结论|判定', x) for x in H[-1:])
                if 'c-take' not in (td.get('class') or []) and not is_last_verdict:
                    continue
                if td.find(class_='pill'):
                    continue
                first = next((c for c in td.contents if not (isinstance(c, str) and not c.strip())), None)
                if getattr(first, 'name', None) not in ('strong', 'b'):
                    continue
                w = first.get_text(strip=True)
                if len(w) > 12:
                    continue
                k = 'bad' if BAD_W.search(w) else ('good' if GOOD_W.search(w) else 'info')
                pill = soup.new_tag('span', attrs={'class': ['pill', k]}); pill.string = w
                first.replace_with(pill)
                rest = [c.extract() for c in list(pill.next_siblings)]
                if any((c.strip() if isinstance(c, str) else c.get_text(strip=True)) for c in rest):
                    note = soup.new_tag('span', attrs={'class': ['pill-note']})
                    for c in rest:
                        note.append(c)
                    pill.insert_after(note)
                if k in ('bad', 'good') and not any(c.startswith('row-') for c in (tr.get('class') or [])):
                    add_class(tr, f'row-{k}')
        # 3. long prose column -> quiet detail text
        for ci, h in enumerate(H):
            if ci == 0:
                continue
            lens = [len(txt(tr.find_all('td')[ci])) for tr in rows if len(tr.find_all('td')) > ci]
            if lens and sum(lens) / len(lens) > 38:
                for tr in rows:
                    tds = tr.find_all('td')
                    if ci < len(tds) and 'c-take' not in (tds[ci].get('class') or []):
                        add_class(tds[ci], 'detail')


CSS += r'''
/* enrichment */
td.mgc { white-space: nowrap; min-width: 128px; }
.mg { display: inline-flex; align-items: center; gap: 8px; }
.mg-t { position: relative; display: inline-block; width: 64px; height: 8px; background: var(--line); border-radius: 4px; }
.mg-b { position: absolute; left: 0; top: 0; height: 8px; border-radius: 4px; }
.mg-b.a { background: var(--accent); } .mg-b.m { background: color-mix(in srgb, var(--muted) 55%, transparent); } .mg-b.o { background: color-mix(in srgb, var(--bad) 70%, transparent); }
.mk { position: absolute; top: -3px; width: 2px; height: 14px; background: var(--ink); margin-left: -1px; }
.mg-v { font-family: var(--font-mono); font-size: 14px; font-variant-numeric: tabular-nums; }
.mg-v.strong { font-weight: 700; color: var(--accent); }
.mg-s { display: block; font-size: 12px; color: var(--muted); margin-top: 2px; padding-left: 72px; }
td.detail { color: var(--muted); font-size: 13.5px; line-height: 1.65; max-width: 30em; }
tbody tr:nth-child(even):not(.grp):not(.row-bad):not(.row-subj) td { background: color-mix(in srgb, var(--bg) 60%, transparent); }
tbody td:first-child strong { font-weight: 700; }
td.c-take .pill { font-size: 13px; padding: 2px 10px; }
'''

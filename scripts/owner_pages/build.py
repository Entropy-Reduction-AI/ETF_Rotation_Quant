"""Convert repo owner docs (markdown) into self-contained artifact pages sharing the board's design.

Usage: python3 -I build.py <repo_root> <out_root> <links.json>
links.json maps md filename / old artifact id -> new artifact url (may be empty on first pass).
"""
import json, os, re, shutil, sys, html
import markdown
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import polish as P
import story as S

REPO, OUT, LINKS = sys.argv[1], sys.argv[2], sys.argv[3]
DOCS = os.path.join(REPO, 'docs', 'owner')
CSS = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'base.css'), encoding='utf-8').read()
# the spec's component sheet (docs/reference/owner-page-story.css), with its variable names mapped onto ours
SPEC_CSS = (':root { --fg: var(--ink); --rule: var(--line); --mono: var(--font-mono); --body: var(--font-body); '
            '--ok: var(--good); --ok-soft: var(--good-soft); }\n'
            + open(os.path.join(REPO, 'docs', 'reference', 'owner-page-story.css'), encoding='utf-8').read())
links = json.load(open(LINKS, encoding='utf-8')) if os.path.exists(LINKS) else {}

PAGES = [
    # slug, file, short title, old artifact id (from the board)
    ('v6-preflight', 'v6-preflight-forecast.md', 'v6 预演预测表', '__v6_preflight__'),
    ('v6-prereg', '../prereg/etf-multiasset-rotation-prereg-v6.md', 'v6 预注册', '__v6_prereg__'),
    ('retro', 'phase2-retrospective.md', '第二阶段复盘', '5MkgZbbcXpkajmwz5qymNF'),
    ('oneshot', 'v5-oneshot-report.md', '一次性检验报告', 'Hqn3e4uwds2bN2JMyGqexq'),
    ('v51-health', 'v5.1-health-check.md', 'v5.1 体检报告', 'CG26Frh88yKyFUqmFBCVvk'),
    ('v5-memo', 'v5-research-memo.md', 'v5 研究备忘', 'QDMEGzTs5ekXnpVT2pUnoR'),
    ('v4-health', 'v4-health-check.md', 'v4 体检报告', 'FTHcH1SY1m5cvLtu7qxteJ'),
    ('v4-memo', 'v4-research-memo.md', 'v4 研究备忘', 'SwFZBC2Qrcxk1AURv1iab8'),
    ('data-board', 'data-board.md', 'ETF 轮动 · 数据与容器看板', 'Rsguim7WUoBYRZ7EzvqKuH'),
    ('board', 'phase2-owner-board.md', 'ETF 轮动 · 第二阶段 Owner 看板', '__board_self__'),
]
GH = 'https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/blob/main/'


def meta_value(text, key):
    m = re.search(r'^- ' + re.escape(key) + r':\s*(.+)$', text, re.M)
    return m.group(1).strip() if m else ''


def strip_metadata(text):
    # drop "## Metadata" block up to and including the first '---' rule after it
    m = re.search(r'^## Metadata\s*$', text, re.M)
    if not m:
        return text
    rest = text[m.end():]
    r = re.search(r'^---\s*$', rest, re.M)
    if r:
        return text[:m.start()] + rest[r.end():]
    # no rule: drop until next heading
    h = re.search(r'^#{1,2} ', rest, re.M)
    return text[:m.start()] + (rest[h.start():] if h else '')


def preprocess(text):
    text = text.replace('\\*\\*', '**')
    text = re.sub(r'~~(.+?)~~', r'<del>\1</del>', text)
    # nested duplicate link [[X](a)](a) -> [X](a)
    text = re.sub(r'\[\[([^\]]+)\]\(([^)]+)\)\]\(\2\)', r'[\1](\2)', text)
    # <details><summary>X</summary> -> markdown-enabled details
    text = re.sub(r'<details>\s*\n\s*<summary>(.*?)</summary>',
                  lambda m: '<details class="fold" markdown="1">\n<summary>' + m.group(1) + '</summary>\n', text)
    text = text.replace('</details>', '\n</details>\n')
    # ▶ toggle titles -> h4.toggle
    text = re.sub(r'^▶\s*(.+)$', r'#### ▸ \1', text, flags=re.M)
    # an image line glued to a blockquote/paragraph above would be swallowed: isolate image lines
    text = re.sub(r'^(!\[[^\]]*\]\([^)]+\))\s*$', r'\n\1\n', text, flags=re.M)
    # same for a blockquote glued to a following table/list: ensure blank line after quote blocks
    text = re.sub(r'^(>.*)\n(?=[^>\n])', r'\1\n\n', text, flags=re.M)
    # two-row headers (header with empty group cells + a short sub-header row) -> one merged header row
    L = text.split('\n'); i = 0
    while i + 2 < len(L):
        if L[i].startswith('|') and re.match(r'^\|\s*:?-{3,}', L[i + 1]) and L[i + 2].startswith('|'):
            head = [c.strip() for c in L[i].strip().strip('|').split('|')]
            sub = [c.strip() for c in L[i + 2].strip().strip('|').split('|')]
            if '' in head[1:] and len(sub) < len(head):
                group, labels = '', []
                for c in head:
                    group = c or group
                    labels.append(group)
                for k, sv in enumerate(sub):
                    labels[k + 1] = f'{labels[k + 1]} {sv}'
                L[i] = '| ' + ' | '.join(labels) + ' |'
                del L[i + 2]
        i += 1
    text = '\n'.join(L)
    # make sure block html is separated by blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text


def link_target(href, src_file):
    if href.startswith('#') or href.startswith('mailto:'):
        return href
    m = re.match(r'https://claude\.ai/artifact/([A-Za-z0-9]+)', href)
    if m and m.group(1) in links:
        return links[m.group(1)]
    if re.match(r'https?://', href):
        return href
    path, _, frag = href.partition('#')
    base = os.path.basename(path)
    if base in links:
        return links[base]
    # repo-relative path -> GitHub
    rel = os.path.normpath(os.path.join('docs/owner', path)).replace(os.sep, '/')
    return GH + rel + (('#' + frag) if frag else '')


def slugify(s, used):
    base = re.sub(r'[^\w一-鿿-]+', '-', s).strip('-').lower()[:40] or 'sec'
    k, i = base, 2
    while k in used:
        k = f'{base}-{i}'; i += 1
    used.add(k)
    return k


def inline_md(t, src_file):
    t = html.escape(t, quote=False)
    t = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', t)
    t = re.sub(r'`([^`]+)`', r'<code>\1</code>', t)
    t = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', lambda m: f'<a href="{html.escape(link_target(m.group(2), src_file), quote=True)}">{m.group(1)}</a>', t)
    return t


def cardify(text, src_file):
    """Runs of single-line paragraphs exported from card grids -> HTML card grid."""
    blocks = re.split(r'\n[ \t]*\n', text)
    def plain(b):
        return b.strip() != '' and '\n' not in b.strip() and not re.match(r'^\s*([#>|*!<]|-\s|\d+\.\s|---)', b)
    def short(b):
        b = b.strip()
        return len(b) <= 24 and '。' not in b and not b.endswith('：')
    out, i, nconv = [], 0, 0
    while i < len(blocks):
        j = i
        while j < len(blocks) and plain(blocks[j]):
            j += 1
        run = [b.strip() for b in blocks[i:j]]
        dated = [b for b in run if re.match(r'^\d{1,2}-\d{2}(?!\d)', b)]
        if len(dated) >= 3:
            rows, rest = [], []
            for b in run:
                m = re.match(r'^(\d{1,2}-\d{2})(.*)$', b)
                if m and not rest:
                    hl = ' class="hl"' if '代码复核时发现' in m.group(2) else ''
                    rows.append(f'<div{hl}><span class="d">{m.group(1)}</span><span>{inline_md(m.group(2).strip(), src_file)}</span></div>')
                else:
                    rest.append(b)
            out.append('<div class="log">' + ''.join(rows) + '</div>')
            out.extend(rest)
            i = j
            continue
        cards, k = [], 0
        lead = []
        while k < len(run) and not short(run[k]):
            lead.append(run[k]); k += 1
        while k < len(run):
            if not short(run[k]):
                break
            title, value, desc = run[k], '', []
            k += 1
            if k + 1 < len(run) + 1 and k < len(run) and short(run[k]) and k + 1 < len(run) and not short(run[k + 1]):
                value = run[k]; k += 1
            while k < len(run) and not short(run[k]):
                desc.append(run[k]); k += 1
            if not desc and not value:
                k -= 1
                break
            cards.append([title, value, desc])
        if len(cards) >= 2:
            tail = run[k:]
            counts = sorted(len(c[2]) for c in cards)
            typical = counts[len(counts) // 2]
            extra = []
            if len(cards[-1][2]) > typical:
                extra = cards[-1][2][typical:]
                cards[-1][2] = cards[-1][2][:typical]
            out.extend(lead)
            h = ['<div class="cards">']
            for t, v, d in cards:
                h.append('<div class="card"><div class="ct">' + inline_md(t, src_file) + '</div>' +
                         (f'<div class="cv">{inline_md(v, src_file)}</div>' if v else '') +
                         ''.join(f'<p>{inline_md(x, src_file)}</p>' for x in d) + '</div>')
            h.append('</div>')
            out.append(''.join(h))
            out.extend(extra + tail)
            nconv += 1
        else:
            out.extend(blocks[i:j])
        if j == i:
            out.append(blocks[i]); j = i + 1
        i = j
    return '\n\n'.join(out), nconv


def mark_tables(slug, content):
    def tables():
        return list(re.finditer(r'<table>.*?</table>', content, flags=re.S))
    def cell_val(inner):
        t = re.sub(r'<[^>]+>', '', inner).strip().replace('−', '-')
        try:
            return float(t)
        except ValueError:
            return None
    if slug == 'v5-memo':
        for m in tables():
            t = m.group(0)
            if '设计期，相对基准' in t and '<th>四格</th>' in t:
                def color(cm):
                    v = cell_val(cm.group(2))
                    if v is None:
                        return cm.group(0)
                    cls = 'good' if v >= 2 else ('bad' if v < 0 else '')
                    if not cls:
                        return cm.group(0)
                    attrs = cm.group(1)
                    attrs = attrs.replace('class="n"', f'class="n {cls}"') if 'class="n"' in attrs else attrs + f' class="{cls}"'
                    return f'<td{attrs}>{cm.group(2)}</td>'
                content = content.replace(t, re.sub(r'<td([^>]*)>(.*?)</td>', color, t, flags=re.S), 1)
            elif '那一天' in t and '差在哪' in t:
                def v5col(rm):
                    cells = re.findall(r'<td[^>]*>.*?</td>', rm.group(0), flags=re.S)
                    if len(cells) < 4:
                        return rm.group(0)
                    c = cells[3]
                    return rm.group(0).replace(c, re.sub(r'^<td([^>]*)>', lambda x: '<td class="bad"' + x.group(1).replace(' class="k"', '') + '>', c), 1)
                content = content.replace(t, re.sub(r'<tr>.*?</tr>', v5col, t, flags=re.S), 1)
    if slug == 'data-board':
        for m in tables():
            t = m.group(0)
            if '恒生指数在设计期只有价格指数' in t:
                t2 = re.sub(r'<tr>(\s*<td[^>]*>恒生指数在设计期只有价格指数)', r'<tr class="hl">\1', t)
                content = content.replace(t, t2, 1)
            if '仅 1 只' in t:
                t2 = t.replace('<td><strong>2005，仅 1 只</strong></td>', '<td class="boxed"><strong>2005，仅 1 只</strong></td>')
                t2 = re.sub(r'(<strong>其他海外</strong></td>.*?)<td class="n"><strong>1</strong></td>', r'\1<td class="n boxed"><strong>1</strong></td>', t2, count=1, flags=re.S)
                content = content.replace(t, t2, 1)
    return content


MUTE = ['正常', '靶子', '参照']
GOOD = ['做到', '两段都更好', '兑现', '两段都赢', '明显更早', '大致对', '已完成', '已修好', '已证明', '已批准', '已批', '已修', '已做', '过关', '通过', '达到', '猜对', '符合', '一致', '成立', '采用', '最好', '最高', '最浅', '兑现', '更早', '更好', '赢', '对', '稳', '留']
BAD = ['两段都更差', '没兑现', '全部不可用', '两段都输', '未通过', '不通过', '没达到', '不满足', '不入围', '不成立', '不可用', '不采用', '没兑现', '没过', '猜错', '亏钱', '最差', '丢掉', '不用', '都输', '错', '输']
WARN = ['大部分做到', '和基准打平', '打平基准', '研究序列不完整', '没有研究序列', '待你定方向', '待你定', '待你确认', '待补记', '待修程序', '部分做到', '进行中', '要警惕', '只报告', '略敏感', '影子', '敏感', '待定', '部分', '补记']
VERDICT_HEAD = ('结论', '判定', '状态', '对了吗', '对上了吗', '判断', '过关', '结果', '押注兑现了吗', '做到了吗')
SIGNED = re.compile(r'(?<![\w.\d])([+\-−]\d[\d.,]*(?:%|pp)?)')


def polish_tables(content):
    def one(tm):
        t = tm.group(0)
        heads = [re.sub(r'<[^>]+>', '', h).strip() for h in re.findall(r'<th[^>]*>(.*?)</th>', t, flags=re.S)]
        ncol = len(heads)
        rows = re.findall(r'<tr[^>]*>.*?</tr>', t, flags=re.S)
        body = [r for r in rows if '<td' in r]
        cells_of = lambda r: re.findall(r'<td[^>]*>.*?</td>', r, flags=re.S)
        text = lambda c: re.sub(r'<[^>]+>', '', c).strip()
        # signed-difference columns: column holds both + and − tokens
        signed_cols = set(); col_toks = []
        for ci in range(ncol):
            toks = []
            for r in body:
                cs = cells_of(r)
                if len(cs) > ci:
                    tx = text(cs[ci])
                    rest = SIGNED.sub('', tx)
                    if len(re.findall(r'[一-鿿]', rest)) <= 3:
                        toks += SIGNED.findall(tx)
            col_toks.append(toks)
        for ci, toks in enumerate(col_toks):
            if any(x.startswith('+') for x in toks) and any(x[0] in '-−' for x in toks):
                signed_cols.add(ci)
        if signed_cols:
            for ci, toks in enumerate(col_toks):
                h = heads[ci] if ci < len(heads) else ''
                if ci not in signed_cols and len(toks) >= 2 and all(x[0] in '-−+' for x in toks) and '回撤' not in h and '跌' not in h:
                    signed_cols.add(ci)
        verdict_cols = {i for i, h in enumerate(heads) if any(h.startswith(v) or h == v for v in VERDICT_HEAD)}
        if heads and heads[-1] == '' and len(heads) >= 3:
            verdict_cols.add(len(heads) - 1)
        out = t
        for r in body:
            cs = cells_of(r)
            nr = r
            # group row
            if len(cs) >= 2 and text(cs[0]) and all(text(c) == '' for c in cs[1:]):
                inner = re.sub(r'^<td[^>]*>|</td>$', '', cs[0])
                out = out.replace(r, f'<tr class="grp"><td colspan="{len(cs)}">{inner}</td></tr>', 1)
                continue
            first = text(cs[0]) if cs else ''
            if first.startswith('基准') or '（参照）' in first or first.startswith('基线'):
                nr = nr.replace('<tr>', '<tr class="ref">', 1)
            for ci, c in enumerate(cs):
                nc = c
                if ci in signed_cols:
                    def col(m):
                        v = m.group(1)
                        k = 'pos' if v.startswith('+') else 'neg'
                        return f'<span class="{k}">{v}</span>'
                    # only touch text outside tags
                    nc = re.sub(r'>([^<]*)<', lambda m: '>' + SIGNED.sub(col, m.group(1)) + '<', nc)
                if ci in verdict_cols:
                    m = re.match(r'(<td[^>]*>)(\s*(?:<strong>)?)(.*)$', nc, flags=re.S)
                    if m:
                        rest = m.group(3)
                        for cls, words in (('mute', MUTE), ('bad', BAD), ('warn', WARN), ('good', GOOD)):
                            w = next((w for w in words if rest.startswith(w)), None)
                            if w:
                                after = rest[len(w):]
                                if m.group(2).strip() == '<strong>':
                                    after = after.replace('</strong>', '', 1)
                                after = re.sub(r'^\s*[：:，,]\s*', '', after)
                                nc = f'{m.group(1)}<span class="pill {cls}">{w}</span>{after}'
                                break
                if nc != c:
                    nr = nr.replace(c, nc, 1)
            if nr != r:
                out = out.replace(r, nr, 1)
        return out
    return re.sub(r'<table>.*?</table>', one, content, flags=re.S)


def build(slug, fname, short, oldid):
    src = os.path.join(DOCS, fname)
    raw = open(src, encoding='utf-8').read()
    date = meta_value(raw, 'Date') or meta_value(raw, 'Last updated')
    date = re.split(r'[（(]', date)[0].strip()
    lines = raw.split('\n')
    title_line = lines[0].lstrip('# ').strip()
    body = '\n'.join(lines[1:])
    body = strip_metadata(body)
    body = preprocess(body)
    body, ncards = cardify(body, fname)

    md = markdown.Markdown(extensions=['tables', 'md_in_html', 'sane_lists', 'fenced_code'])
    content = md.convert(body)

    # images: copy and rewrite
    adir = os.path.join(OUT, slug, 'assets')
    REPO_MODE = os.environ.get('OWNER_PAGE_REPO') == '1'  # repo copy: point at docs/assets, copy nothing
    if not REPO_MODE:
        os.makedirs(adir, exist_ok=True)
    missing = []

    def img_sub(m):
        attrs = m.group(1)
        sm = re.search(r'src="([^"]+)"', attrs)
        am = re.search(r'alt="([^"]*)"', attrs)
        p = sm.group(1)
        absp = os.path.normpath(os.path.join(DOCS, p))
        name = os.path.basename(os.path.dirname(absp)) + '-' + os.path.basename(absp)
        if not os.path.exists(absp):
            missing.append(p)
        elif not REPO_MODE:
            shutil.copy(absp, os.path.join(adir, name))
        alt = am.group(1) if am else ''
        src = os.path.relpath(absp, os.path.join(OUT, slug)) if REPO_MODE else f'assets/{name}'
        return f'<img src="{src}" alt="{alt}">'
    content = re.sub(r'<img([^>]*)/?>', img_sub, content)
    # paragraph that only holds an image -> figure
    content = re.sub(r'<p>\s*(<img [^>]+>)\s*</p>', r'<figure>\1</figure>', content)

    # links
    content = re.sub(r'href="([^"]+)"', lambda m: 'href="' + html.escape(link_target(html.unescape(m.group(1)), fname), quote=True) + '"', content)
    # tables
    content = re.sub(r'<table>', '<div class="table-wrap"><table>', content)
    content = content.replace('</table>', '</table></div>')
    # right-align a column only when every body cell in it is numeric
    NUM = re.compile(r'[−+\-–]?[\d.,]+\s*(%|pp|倍|个|只|元|天|年|次|个点)?')
    def table_sub(tm):
        t = tm.group(0)
        rows = re.findall(r'<tr>(.*?)</tr>', t, flags=re.S)
        if len(rows) < 2:
            return t
        body_rows = [re.findall(r'<td[^>]*>(.*?)</td>', r, flags=re.S) for r in rows[1:]]
        ncol = max((len(r) for r in body_rows), default=0)
        numeric = []
        for c in range(ncol):
            vals = [re.sub(r'<[^>]+>', '', r[c]).strip() for r in body_rows if len(r) > c]
            vals = [v for v in vals if v and v not in ('—', '-', '–')]
            numeric.append(bool(vals) and all(NUM.fullmatch(v) for v in vals))
        def fix_row(r, tag):
            i = [-1]
            def cell(m):
                i[0] += 1
                if i[0] < len(numeric) and numeric[i[0]]:
                    return f'<{tag} class="n"{m.group(1)}>'
                return m.group(0)
            return re.sub(r'<' + tag + r'([^>]*)>', cell, r)
        out = t
        for r in rows:
            nr = fix_row(fix_row(r, 'th'), 'td')
            out = out.replace(r, nr, 1)
        return out
    content = re.sub(r'<table>.*?</table>', table_sub, content, flags=re.S)
    def first_cell(m):
        inner = m.group(2)
        txt = re.sub(r'<[^>]+>', '', inner).strip()
        if len(txt) <= 6 and 'class=' not in m.group(1):
            return f'<tr>\n<td class="k"{m.group(1)}>{inner}</td>'
        return m.group(0)
    content = re.sub(r'<tr>\s*<td([^>]*)>(.*?)</td>', first_cell, content, flags=re.S)
    content = mark_tables(slug, content)
    content = polish_tables(content)
    # blockquote right after h2/h3 -> lede
    content = re.sub(r'(</h2>\s*)<blockquote>\s*(.*?)\s*</blockquote>', r'\1<div class="lede">\2</div>', content, flags=re.S)
    content = re.sub(r'(</h3>\s*)<blockquote>\s*(.*?)\s*</blockquote>', r'\1<div class="claim-box">\2</div>', content, flags=re.S)
    # remaining blockquotes -> note box
    content = content.replace('<blockquote>', '<div class="aside">').replace('</blockquote>', '</div>')
    # strip <p> wrappers inside lede to keep one block
    content = re.sub(r'<div class="(lede|claim-box)">\s*<p>(.*?)</p>\s*</div>', r'<div class="\1">\2</div>', content, flags=re.S)
    # hr -> nothing (section spacing does the job)
    content = re.sub(r'<hr\s*/?>', '', content)

    # headings: ids + toc
    used, toc = set(), []
    def h_sub(m):
        lvl, inner = int(m.group(1)), m.group(2)
        txt = re.sub(r'<[^>]+>', '', inner).strip()
        hid = slugify(txt, used)
        if lvl == 2:
            toc.append((2, txt, hid))
            inner = re.sub(r'^·\.\s*', '0. ', inner)
            nm = re.match(r'^(\d+(?:\.\d+)?)[.、]?\s*(.*)$', inner, re.S)
            if nm:
                inner = f'<span class="num">{nm.group(1).zfill(2) if "." not in nm.group(1) else nm.group(1)}</span>{nm.group(2)}'
        elif lvl == 3 and not txt.startswith('▸'):
            toc.append((3, txt, hid))
        cls = ' class="toggle"' if txt.startswith('▸') else ''
        return f'<h{lvl} id="{hid}"{cls}>{inner}</h{lvl}>'
    content = re.sub(r'<h([234])>(.*?)</h\1>', h_sub, content, flags=re.S)

    # wrap h2 sections
    parts = re.split(r'(?=<h2 id=)', content)
    out = []
    for p in parts:
        if p.startswith('<h2 id='):
            hid = re.match(r'<h2 id="([^"]+)"', p).group(1)
            out.append(f'<section id="sec-{hid}">{p}</section>')
        else:
            out.append(f'<section class="intro">{p}</section>' if p.strip() else '')
    content = '\n'.join(out)
    content = P.polish(content, slug)
    content = S.storify(content, slug)
    content = S.ux_pass(content)

    # header
    if '：' in title_line:
        head, sub = title_line.split('：', 1)
    else:
        head, sub = title_line, ''
    h1 = short if slug not in ('data-board', 'board') else head
    sub_html = f'<p class="headline">{html.escape(head + "：" + sub) if slug!="data-board" and head!=short else html.escape(sub)}</p>' if sub else ''
    if slug != 'data-board' and head.strip() != short:
        sub_html = f'<p class="headline">{html.escape(sub)}</p>'

    toc_html = []
    for lvl, txt, hid in toc:
        t = re.sub(r'\s+', ' ', re.sub(r'^·\.\s*', '', txt))
        t = html.escape(t.split('：')[0] if len(t) > 16 else t)
        toc_html.append(f'<li class="l{lvl}"><a href="#{hid}">{t}</a></li>')
    toc_block = '<ol>' + ''.join(toc_html) + '</ol>'

    back = '' if slug == 'board' else links.get('__board__', '')
    back_html = f'<a class="back" href="{back}">← Owner 看板</a>' if back else ''
    kicker = 'ETF_Rotation_Quant' + (f' · {html.escape(date)}' if date else '')

    page = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(short)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=Noto+Sans+SC:wght@400;500;700&display=swap" rel="stylesheet">
<style>
{CSS}
/* page-type additions */
nav.toc li.l3 a {{ padding-left: 22px; font-size: 13px; }}
nav.toc {{ max-height: calc(100vh - 48px); overflow-y: auto; }}
.back {{ font-size: 13px; color: var(--muted); }}
.headline {{ font-size: 19px; line-height: 1.6; font-weight: 500; margin: 6px 0 0; color: var(--ink); text-wrap: balance; }}
section.intro > p:first-child {{ margin-top: 0; }}
section.intro {{ margin-bottom: 40px; }}
.lede p, .claim-box p {{ margin: 0; }}
.claim-box {{ font-weight: 700; font-size: 16.5px; margin: 0 0 10px; }}
.aside > p:last-child, .aside > ul:last-child, .aside > ol:last-child {{ margin-bottom: 0; }}
h4.toggle {{ font-size: 15.5px; color: var(--ink); margin: 26px 0 8px; padding-left: 10px; border-left: 3px solid var(--line); }}
details.fold {{ background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 0 18px; margin: 16px 0 22px; }}
details.fold > summary {{ cursor: pointer; padding: 12px 0; font-weight: 500; color: var(--accent); list-style: none; }}
details.fold > summary::-webkit-details-marker {{ display: none; }}
details.fold > summary::before {{ content: '▸'; display: inline-block; width: 1.1em; transition: transform .15s; }}
details.fold[open] > summary::before {{ transform: rotate(90deg); }}
details.fold[open] {{ padding-bottom: 8px; }}
details.fold figure {{ padding: 10px; }}
pre {{ background: var(--surface); border: 1px solid var(--line); border-radius: 8px; padding: 12px 14px; overflow-x: auto; font-size: 13px; }}
pre code {{ background: none; padding: 0; }}
td del, td s {{ color: var(--muted); }}
td.k {{ white-space: nowrap; font-weight: 500; }}
/* table polish */
.table-wrap {{ box-shadow: 0 1px 0 var(--line); }}
th {{ background: var(--bg); color: var(--muted); font-weight: 500; font-size: 12.5px; border-bottom: 2px solid var(--line); vertical-align: bottom; }}
tbody tr:hover td {{ background: var(--accent-soft); }}
tbody td:first-child {{ font-weight: 500; color: var(--ink); }}
tr.group td {{ background: var(--bg); color: var(--muted); font-size: 12.5px; font-weight: 500; letter-spacing: .02em; padding-top: 8px; padding-bottom: 8px; }}
tr.ref td {{ background: color-mix(in srgb, var(--line) 35%, transparent); color: var(--muted); }}
tr.ref td:first-child {{ font-style: normal; }}
span.pos {{ color: var(--good); font-weight: 500; }}
span.neg {{ color: var(--bad); font-weight: 500; }}
td .pill {{ margin-right: 6px; vertical-align: 1px; }}
td.good span.pos, td.bad span.neg {{ color: inherit; }}
td.good {{ background: var(--good-soft); }}
td.bad, tr.hl td {{ background: var(--warn-soft); }}
td.boxed {{ outline: 2px solid var(--accent); outline-offset: -4px; }}
.log div.hl {{ background: var(--warn-soft); }}
.log div.hl span {{ color: var(--warn); font-weight: 500; }}
.cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 12px; margin: 14px 0 22px; }}
.cards .card .ct {{ font-size: 14px; color: var(--ink); font-weight: 700; }}
.cards .card .cv {{ font-family: var(--font-mono); font-size: 20px; font-weight: 500; line-height: 1.3; color: var(--accent); font-variant-numeric: tabular-nums; }}
.cards .card p {{ font-size: 14.5px; line-height: 1.7; margin: 0; }}
.cards .card p + p {{ color: var(--muted); font-size: 13.5px; }}
th {{ white-space: normal; min-width: 4.5em; }}
th.n {{ white-space: normal; }}
h2 .num {{ min-width: 1.6em; }}
{SPEC_CSS}
{P.CSS}
{S.CSS}
</style>
</head>
<body>
<div class="shell">
<nav class="toc" aria-label="目录">
  {back_html}
  <div class="toc-title">目录</div>
  {toc_block}
</nav>
<main>
<header class="top">
  <div class="kicker">{kicker}</div>
  <h1>{html.escape(h1)}</h1>
  {sub_html}
</header>
{content}
<footer>内容取自仓库 <a href="{GH}docs/owner/{fname}">docs/owner/{fname}</a>（main @ a592981）。图表为原文配图。</footer>
</main>
</div>
<script>
(function () {{
  var links = Array.prototype.slice.call(document.querySelectorAll('nav.toc ol a'));
  var targets = links.map(function (a) {{ return document.getElementById(a.getAttribute('href').slice(1)); }});
  function update() {{
    var y = window.scrollY + 120, idx = 0;
    targets.forEach(function (t, i) {{ if (t && t.getBoundingClientRect().top + window.scrollY <= y) idx = i; }});
    links.forEach(function (a, i) {{ a.classList.toggle('active', i === idx); }});
  }}
  window.addEventListener('scroll', update, {{ passive: true }});
  update();
}})();
{S.FOLD_JS}
</script>
</body>
</html>
'''
    os.makedirs(os.path.join(OUT, slug), exist_ok=True)
    open(os.path.join(OUT, slug, 'index.html'), 'w', encoding='utf-8').write(page)
    imgs = len(re.findall(r'<img ', content))
    src_imgs = len(re.findall(r'!\[[^\]]*\]\([^)]+\)', raw))
    print(f'{slug:12s} cards {ncards} imgs {imgs}/{src_imgs} toc {len(toc)} missing {missing}')


for args in PAGES:
    build(*args)

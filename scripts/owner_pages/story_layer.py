"""Story layer: the author's own focus lines, written into the md as comments, rendered as the dominant element.

Why: the generator used to guess focus from contract sentences (bold words, numbers). Contract text is neutral,
so guessing gave styled text without a point of view. Here the author states, per element, what to look at; the
contract text stays verbatim beneath it.

Markers (one line each, in the md):
  <!-- 问：这一节回答的问题｜短：主线上的两三个字｜状态：已定 / 待你定 / 待补 -->   right under a ## heading
  <!-- 看点：一句话，先看哪里、为什么｜框：单元格里的字（可多个，用 / 分隔） -->       right above a table / list / figure
  <!-- 接力：这一节的结论把读者带到哪一节 -->                                             last line of a section
  <!-- 页面：定义 -->                                                                     right above a list of "**名词**：规则……"
  <!-- 页面：参考 -->                                                                     right above a lookup table (data-lint="ref")
The 问 markers also build the story spine at the top of the page.
"""
import re
from bs4 import BeautifulSoup, Comment, NavigableString

MARK = re.compile(r'^\s*(问|看点|接力)：(.*)$', re.S)
SRC = re.compile(r'（([^（）]*(?:D\d|R1|第 ?\d+ ?行|§|SC-|J-|MF-|Owner)[^（）]*)）')


def _fields(body):
    parts = [x.strip() for x in body.split('｜')]
    out = {'': parts[0]}
    for x in parts[1:]:
        if '：' in x:
            k, v = x.split('：', 1)
            out[k.strip()] = v.strip()
    return out


def _esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


NUM = re.compile(r'(?<![A-Za-z\d.])([+\-−]?\d+(?:\.\d+)?\s*(?:%|万|个点|点|个|种|倍)?(?:\s*[→–]\s*[+\-−]?\d+(?:\.\d+)?\s*(?:%|万|个点|点|个)?)?)')


def _hl(s):
    """Numbers in a focus line carry the reading; they get the accent."""
    return NUM.sub(lambda m: f'<b class="sl-n">{m.group(1)}</b>' if re.search(r'\d', m.group(1)) else m.group(1), _esc(s))


# ---------- pre: before polish / storify ----------
def pre(html):
    """问 markers move onto their h2 as data-sl-q, so later passes see the heading's real first sibling (the memo).
    Definition lists: '**名词**：第一句。其余……（出处）' → a three-column grid that later passes leave alone."""
    soup = BeautifulSoup(html, 'html.parser')
    for c in list(soup.find_all(string=lambda x: isinstance(x, Comment) and re.match(r'^\s*问：', str(x)))):
        h2 = c.find_previous('h2')
        if h2 is not None:
            h2['data-sl-q'] = MARK.match(str(c)).group(2).strip()
        c.extract()
    for c in list(soup.find_all(string=lambda x: isinstance(x, Comment) and '页面：参考' in x)):
        t = c.find_next('table')                       # a reference table: the 看点 carries the point, cells are lookup
        if t is not None:
            t['data-lint'] = 'ref'
        c.extract()
    for c in list(soup.find_all(string=lambda x: isinstance(x, Comment) and '页面：定义' in x)):
        ul = c.find_next_sibling(['ul', 'ol'])
        c.extract()
        if ul is None:
            continue
        rows = []
        for li in ul.find_all('li', recursive=False):
            b = li.find(['strong', 'b'])
            if b is None:
                rows = []
                break
            term = b.get_text('', strip=True)
            b.extract()
            body = li.decode_contents().strip()
            body = re.sub(r'^[：:]\s*', '', body)
            lead = re.match(r'^（([^（）]*)）\s*[：:]\s*', body)
            srcs = []
            if lead:
                body = body[lead.end():]
                if SRC.fullmatch(f'（{lead.group(1)}）'):
                    srcs.append(lead.group(1))
                else:
                    term += f'（{lead.group(1)}）'
            chip = lambda m: '<' not in m.group(0) and len(m.group(1)) <= 18
            for m in SRC.finditer(body):
                if chip(m):
                    srcs.append(m.group(1))
            # a short citation shown as a chip leaves the sentence; a long aside stays in it
            body = SRC.sub(lambda m: '' if chip(m) else m.group(0), body)
            body = re.sub(r'\s+([。；，])', r'\1', body)
            # first sentence = the rule; the rest = detail. Split on the html, at the first 。 outside tags.
            m = re.search(r'。(?![^<]*>)', body)
            head, rest = (body[:m.end()], body[m.end():].strip()) if m else (body, '')
            src_html = ''.join(f'<span class="sl-src">{_esc(x)}</span>' for x in dict.fromkeys(srcs))
            rows.append(f'<div class="sl-dr"><div class="sl-dt">{_esc(term)}</div>'
                        f'<div class="sl-dd"><div class="sl-dh">{head}</div>'
                        + (f'<div class="sl-dx">{rest}</div>' if rest else '') +
                        f'</div><div class="sl-ds">{src_html}</div></div>')
        if rows:
            ul.replace_with(BeautifulSoup('<div class="sl-defs" data-lint="ref">' + ''.join(rows) + '</div>', 'html.parser'))
    return str(soup)


# ---------- post: after ux_pass ----------
def _next_block(c):
    sib = c.next_sibling
    while sib is not None and (isinstance(sib, NavigableString) and not sib.strip() or isinstance(sib, Comment)):
        sib = sib.next_sibling
    if sib is None and c.parent is not None and c.parent.name == 'p':
        return _next_block(c.parent)
    return sib


def _box(el, keys):
    hit = 0
    for k in keys:
        for td in el.select('td, .lg-big, .lg-h, .lg-f, .sg-key, .fl-k, .sl-dt, .sl-dh, .fl-t, .cv, .big'):
            if k and k in td.get_text('', strip=True):
                inner = next((b for b in td.find_all(['strong', 'b']) if k in b.get_text('', strip=True)), None)
                if inner is not None and len(td.get_text('', strip=True)) > len(k) + 12:
                    td = inner
                cl = td.get('class') or []
                if 'sl-box' not in cl:
                    td['class'] = cl + ['sl-box']
                hit += 1
                break
    return hit


def post(html):
    soup = BeautifulSoup(html, 'html.parser')
    spine = []
    secs = soup.select('main section[id^="sec-"], section[id^="sec-"]')
    for i, sec in enumerate(secs):
        h2 = sec.find('h2')
        nxt = secs[i + 1] if i + 1 < len(secs) else None
        if h2 is not None and h2.get('data-sl-q'):
            f = _fields(h2['data-sl-q'])
            del h2['data-sl-q']
            st = f.get('状态', '')
            tone = {'已定': 'ok', '待你定': 'you', '待补': 'todo'}.get(st, 'ok')
            q = BeautifulSoup(f'<div class="sl-q"><span class="sl-ql">这一节回答</span><span class="sl-qt">{_esc(f[""])}</span>'
                              + (f'<span class="sl-st t-{tone}">{_esc(st)}</span>' if st else '') + '</div>', 'html.parser')
            h2.insert_after(q)
            ht = h2.get_text('', strip=True)
            km = re.match(r'(§\s*\d+|附表\s*[A-ZＡ-Ｚ])', ht)
            spine.append((sec.get('id'), f.get('短', ht[:6]), f[''], st, tone, km.group(1).replace(' ', '') if km else ''))
        for c in list(sec.find_all(string=lambda x: isinstance(x, Comment))):
            m = MARK.match(str(c))
            if not m:
                continue
            kind, f = m.group(1), _fields(m.group(2))
            if kind == '问':
                st = f.get('状态', '')
                tone = {'已定': 'ok', '待你定': 'you', '待补': 'todo'}.get(st, 'ok')
                q = BeautifulSoup(f'<div class="sl-q"><span class="sl-ql">这一节回答</span><span class="sl-qt">{_esc(f[""])}</span>'
                                  + (f'<span class="sl-st t-{tone}">{_esc(st)}</span>' if st else '') + '</div>', 'html.parser')
                h2.insert_after(q)
                ht = h2.get_text('', strip=True)
                km = re.match(r'(§\s*\d+|附表\s*[A-ZＡ-Ｚ])', ht)
                spine.append((sec.get('id'), f.get('短', ht[:6]), f[''], st, tone, km.group(1).replace(' ', '') if km else ''))
                c.extract()
            elif kind == '看点':
                tgt = _next_block(c)
                keys = [k.strip() for k in f.get('框', '').split('/') if k.strip()]
                bar = BeautifulSoup(f'<div class="sl-look"><span class="sl-ll">看点</span><span class="sl-lt">{_hl(f[""])}</span></div>', 'html.parser').find(class_='sl-look')
                anchor = c.parent if c.parent is not None and c.parent.name == 'p' and not c.parent.get_text(strip=True) else c
                anchor.insert_before(bar)
                if tgt is not None and keys and not isinstance(tgt, NavigableString):
                    if _box(tgt, keys) < len(keys):
                        bar['data-unboxed'] = '/'.join(keys)
                        import sys
                        print('story_layer: 框 not found:', keys, file=sys.stderr)
                c.extract()
                if anchor is not c and not anchor.get_text(strip=True) and not anchor.find(True):
                    anchor.decompose()
            elif kind == '接力':
                href = f'#{nxt.get("id")}' if nxt is not None else '#'
                tgt_t = nxt.find('h2').get_text(' ', strip=True).split('：')[0] if nxt is not None else '回到页首'
                n = BeautifulSoup(f'<a class="sl-next" href="{href}"><span class="sl-nl">所以</span>'
                                  f'<span class="sl-nt">{_hl(f[""])}</span><span class="sl-ng">{_esc(tgt_t)} {"→" if nxt is not None else "↑"}</span></a>', 'html.parser')
                c.replace_with(n)
    if spine:
        nodes = ''.join(f'<a class="sl-sp-i t-{tone}" href="#{sid}" title="{_esc(q)}"><span class="sl-sp-k">{_esc(k)}</span>'
                        f'<span class="sl-sp-s">{_esc(short)}</span>'
                        + (f'<span class="sl-sp-st">{_esc(st)}</span>' if st else '') + '</a>'
                        for sid, short, q, st, tone, k in spine)
        sp = BeautifulSoup('<nav class="sl-spine" aria-label="故事主线"><div class="sl-sp-h">这份预注册的故事主线：从“怎么做”读到“冻结前还差什么”</div>'
                           f'<div class="sl-sp-r">{nodes}</div></nav>', 'html.parser')
        intro = soup.find('section', class_='intro')
        if intro is not None:
            intro.append(sp)
    return str(soup)


CSS = r"""
/* ===== story layer (author focus lines) ===== */
.sl-q { display: flex; gap: 10px; align-items: baseline; margin: -4px 0 10px; font-size: 15px; }
.sl-ql { flex: none; font-size: 12px; font-weight: 700; letter-spacing: .06em; color: var(--muted); border: 1px solid var(--line); border-radius: 99px; padding: 1px 9px; }
.sl-qt { color: var(--ink); font-weight: 600; }
.sl-st { flex: none; font-size: 12px; font-weight: 700; border-radius: 99px; padding: 1px 9px; }
.sl-st.t-ok { background: var(--good-soft); color: var(--good); }
.sl-st.t-you { background: color-mix(in srgb, var(--accent) 14%, transparent); color: var(--accent); }
.sl-st.t-todo { background: color-mix(in srgb, var(--bad) 14%, transparent); color: var(--bad); }
.sl-look { display: flex; gap: 12px; align-items: baseline; margin: 18px 0 8px; padding: 10px 14px; border-radius: 10px;
  background: color-mix(in srgb, var(--accent) 7%, var(--surface)); border: 1px solid color-mix(in srgb, var(--accent) 25%, transparent); }
.sl-ll { flex: none; font-size: 12px; font-weight: 800; color: #fff; background: var(--accent); border-radius: 6px; padding: 2px 8px; letter-spacing: .08em; }
.sl-lt { font-size: 16px; font-weight: 600; line-height: 1.6; color: var(--ink); }
.sl-n { color: var(--accent); font-family: var(--font-mono); font-weight: 700; white-space: nowrap; }
.ledger .lg .lg-big.sl-box, .lg-big.sl-box, .fl-k.sl-box, b.sl-box, strong.sl-box { padding: 1px 8px; margin-left: -8px; display: inline-block; width: auto; }
.lg-f.sl-box, .lg-h.sl-box { outline-offset: 3px !important; }
.sl-box { outline: 2.5px solid var(--accent) !important; outline-offset: -3px; border-radius: 6px; background: color-mix(in srgb, var(--accent) 6%, transparent) !important; }
.fold-b > .sl-look:first-child { margin-top: 6px; }
a.sl-next { display: flex; gap: 12px; align-items: center; margin: 26px 0 4px; padding: 12px 16px; border-radius: 10px; text-decoration: none;
  border: 1px dashed color-mix(in srgb, var(--accent) 45%, transparent); color: var(--ink); background: var(--surface); }
a.sl-next:hover { border-style: solid; }
.sl-nl { flex: none; font-size: 12px; font-weight: 800; color: var(--accent); letter-spacing: .08em; }
.sl-nt { flex: 1; font-size: 15px; line-height: 1.6; }
.sl-ng { flex: none; font-size: 13px; font-weight: 700; color: var(--accent); white-space: nowrap; }
.sl-defs { display: grid; margin: 8px 0 14px; border: 1px solid var(--line); border-radius: 10px; overflow: hidden; background: var(--surface); }
.sl-dr { display: grid; grid-template-columns: 8.5em minmax(0, 1fr) 11em; gap: 14px; padding: 11px 14px; border-top: 1px solid var(--line); align-items: baseline; }
.sl-dr:first-child { border-top: 0; }
.sl-dt { font-weight: 700; color: var(--ink); font-size: 14.5px; }
.sl-dt::before { content: ''; display: inline-block; width: 6px; height: 6px; border-radius: 2px; background: var(--accent); margin-right: 8px; vertical-align: 2px; }
.sl-dh { font-size: 15px; color: var(--ink); line-height: 1.6; }
.sl-dx { font-size: 13.5px; color: var(--muted); line-height: 1.6; margin-top: 3px; }
.sl-ds { display: flex; flex-wrap: wrap; gap: 4px; justify-content: flex-end; }
.sl-src { font-size: 11.5px; color: var(--muted); border: 1px solid var(--line); border-radius: 5px; padding: 0 6px; white-space: nowrap; }
nav.sl-spine { margin: 18px 0 4px; }
.sl-sp-h { font-size: 13px; font-weight: 700; color: var(--muted); margin-bottom: 8px; letter-spacing: .03em; }
.sl-sp-r { display: grid; grid-template-columns: repeat(auto-fit, minmax(96px, 1fr)); gap: 0; border: 1px solid var(--line); border-radius: 10px; overflow: hidden; background: var(--surface); }
a.sl-sp-i { position: relative; display: grid; gap: 2px; padding: 10px 10px 9px 12px; text-decoration: none; color: var(--ink); border-left: 1px solid var(--line); border-top: 3px solid var(--good); }
a.sl-sp-i:first-child { border-left: 0; }
a.sl-sp-i.t-you { border-top-color: var(--accent); } a.sl-sp-i.t-todo { border-top-color: var(--bad); }
a.sl-sp-i:hover { background: color-mix(in srgb, var(--accent) 6%, transparent); }
.sl-sp-k { font-family: var(--font-mono); font-size: 11.5px; color: var(--muted); }
.sl-sp-s { font-size: 14px; font-weight: 700; line-height: 1.35; }
.sl-sp-st { font-size: 11.5px; color: var(--muted); }
a.sl-sp-i.t-todo .sl-sp-st { color: var(--bad); font-weight: 700; } a.sl-sp-i.t-you .sl-sp-st { color: var(--accent); font-weight: 700; }
@media (max-width: 760px) { .sl-dr { grid-template-columns: minmax(0, 1fr); gap: 3px; } .sl-ds { justify-content: flex-start; } .sl-look, a.sl-next { flex-direction: column; gap: 4px; align-items: flex-start; } }
"""

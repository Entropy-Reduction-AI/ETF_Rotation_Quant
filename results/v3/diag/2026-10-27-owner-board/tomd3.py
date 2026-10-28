"""把页面 HTML 转成和页面结构对应的 GitHub Markdown。用法：tomd3.py <content.html> <out.md> <head.md>"""
import re, sys
from bs4 import BeautifulSoup, NavigableString
from markdownify import markdownify as mdify

src, dst, headf = sys.argv[1:4]
raw = open(src).read()
raw = re.sub(r'\{\{img:([\w-]+)\|([^}]*)\}\}', r'<p><img alt="\2" src="../assets/owner-board/\1.png"></p>', raw)
soup = BeautifulSoup(raw, 'html.parser')
for t in soup.find_all(['script', 'nav']): t.decompose()
for t in soup.find_all(string=lambda x: isinstance(x, NavigableString) and x.__class__.__name__ == 'Comment'): t.extract()

def inline(el):
    """元素内部转成一行 Markdown（保留粗体、删除线），用于表格单元格。"""
    h = str(el) if el is not None else ''
    h = re.sub(r'<mark>(.*?)</mark>', r'<b>\1</b>', h, flags=re.S)
    t = mdify(h, heading_style='ATX').strip()
    t = re.sub(r'\s*\n\s*', ' ', t)
    return t.replace('|', '\\|')

def table(headers, rows):
    out = '| ' + ' | '.join(headers) + ' |\n|' + ' --- |' * len(headers) + '\n'
    for r in rows: out += '| ' + ' | '.join(r) + ' |\n'
    return out

def md_block(text):
    tag = soup.new_tag('div'); tag['data-md'] = '1'; tag.string = '\n\n' + text.strip() + '\n\n'; return tag

# 记忆句、结论框、一句话 → 引用块
for p in soup.select('p.memo'):
    p.replace_with(md_block('> **' + inline(p).strip('*') + '**'))
for d in soup.select('div.key'):
    d.replace_with(md_block('> ' + inline(d)))
for d in soup.select('div.thesis'):
    k = d.select_one('.k'); k.decompose()
    d.replace_with(md_block('> **一句话**　' + inline(d.p)))
# 顶部三格状态
for sec in soup.select('section.status'):
    ks = [inline(x) for x in sec.select('.k')]
    ps = [inline(x.find('p')) for x in sec.select('.st')]
    sec.replace_with(md_block(table(ks, [ps])))
for h in soup.select('header'):
    v = h.select_one('p.vision')
    if v is not None:
        h.insert_after(md_block(inline(v)))
    h.decompose()
# 事项卡片
for it in soup.select('.todo .item'):
    tag = inline(it.select_one('.tag')); what = inline(it.select_one('.what'))
    parts = [f'#### 【{tag}】{what}']
    cols = it.select('.cols > div')
    if cols:
        parts.append(table([inline(c.select_one('.lb')) for c in cols],
                           [[inline(BeautifulSoup(''.join(str(p) for p in c.find_all('p')), 'html.parser')) for c in cols]]))
    ch = it.select('.choice .opt')
    if ch:
        rows = []
        for o in ch:
            rec = '⭐ 建议' if 'rec' in o.get('class', []) else ''
            b = o.find('b'); pp = o.find('p')
            rows.append([inline(b), inline(pp) if pp else '', rec])
        parts.append(table(['选项', '说明', ''], rows))
    it.replace_with(md_block('\n\n'.join(parts)))
for d in soup.select('div.todo'): d.unwrap()
# 版本卡片
vers = soup.select('div.vers')
for v in vers:
    rows = []
    for c in v.select('.ver'):
        nm = inline(c.select_one('.vn')) + ' · ' + inline(c.select_one('.nick'))
        chg = c.select_one('.chg'); k = chg.select_one('.chg-k'); kt = inline(k); k.decompose()
        nums = [inline(b) for b in c.select('.vnum b')]
        rows.append([f'**{nm}**', f'{kt}：{inline(chg)}', nums[0] if nums else '', nums[1] if len(nums) > 1 else '', inline(c.select_one('.verdict'))])
    v.replace_with(md_block(table(['版本', '改了什么', '年化', '最深回撤', '评价'], rows)))
for d in soup.select('.legendline'): d.decompose()
# 步骤
for st in soup.select('div.steps'):
    items = []
    for i, sp in enumerate(st.select('.sp'), 1):
        b = sp.find('b'); p = sp.find('p')
        items.append(f'{i}. **{inline(b).strip("*")}**：{inline(p)}')
    st.replace_with(md_block('\n'.join(items)))
# 规则差异卡
for ds in soup.select('div.diffs'):
    out = []
    for d in ds.select('.diff'):
        nm = inline(d.select_one('.vn')) + ' · ' + inline(d.select_one('.nick'))
        old = d.select_one('.old'); new = d.select_one('.new')
        for o in (old, new):
            sp = o.find('span')
            if sp: sp.decompose()
        why = d.select_one('.why2')
        rows = [['改的是', inline(d.select_one('.scope')).replace('改的是：', '')],
                ['原规则', '~~' + inline(old) + '~~'], ['新规则', inline(new)]]
        if why: rows.append(['说明', inline(why)])
        out.append(f'#### {nm}\n\n' + table(['项目', '内容'], rows))
    ds.replace_with(md_block('\n\n'.join(out)))
# 时间线
for tl in soup.select('div.timeline'):
    rows = [[('**' + inline(x.select_one('.td')) + '**'), inline(x.select_one('.tt'))] for x in tl.select('.tl')]
    tl.replace_with(md_block(table(['节点', '内容'], rows)))
# 三格 / 两格 / 补充卡片
for g in soup.select('div.grid3'):
    cells = g.find_all('div', recursive=False)
    heads = [inline(c.select_one('.g-k')) for c in cells]
    vals = [inline(c.find('p')) for c in cells]
    g.replace_with(md_block(table(heads, [vals])))
for g in soup.select('div.two'):
    cells = g.find_all('div', recursive=False)
    g.replace_with(md_block('\n'.join('- ' + inline(c) for c in cells)))
for g in soup.select('div.minor, div.side'):
    cells = g.find_all('div', recursive=False)
    g.replace_with(md_block('\n'.join('- ' + inline(c) for c in cells)))
# 问答
for qa in soup.select('div.qa'):
    qs = qa.select('.q'); as_ = qa.select('.a')
    qa.replace_with(md_block(table(['问题', '回答'], [[f'**{inline(q)}**', inline(a)] for q, a in zip(qs, as_)])))
# 已回答 / 已定
for r in soup.select('div.resolved'):
    items = []
    for d in r.find_all('div', recursive=False):
        ok = d.select_one('.ok'); label = inline(ok); ok.decompose()
        items.append(f'- ✅ **{label}**{inline(d)}')
    r.replace_with(md_block('\n'.join(items)))
# 决定卡
for dc in soup.select('div.decision'):
    dn = dc.select_one('.dn'); dnt = inline(dn); dn.decompose()
    head = f'#### {dnt}：{inline(dc.select_one(".dh"))}'
    opts = dc.select('.opt')
    parts = [head]
    if opts:
        rows = []
        for o in opts:
            ot = o.select_one('.ot'); pill = ot.select_one('.pill')
            if pill: pill.decompose()
            p = o.find('p')
            rows.append([inline(ot), inline(p) if p else '', '⭐ 建议' if 'rec' in o.get('class', []) else ''])
        parts.append(table(['选项', '说明', ''], rows))
    for p in dc.find_all('p', recursive=False):
        parts.append(inline(p))
    dc.replace_with(md_block('\n\n'.join(parts)))
# 折叠 → <details>
for f in soup.select('div.fold'):
    btn = f.select_one('.fold-h'); ch = btn.select_one('.chev')
    if ch: ch.decompose()
    body = f.select_one('.fold-b')
    inner = mdify(str(body), heading_style='ATX', bullets='-').strip()
    f.replace_with(md_block(f'<details>\n<summary>{inline(btn)}</summary>\n\n{inner}\n\n</details>'))
# 标题编号
for h in soup.select('h2'):
    n = h.select_one('.n')
    if n: n.replace_with(n.get_text() + '. ')
for h in soup.select('h3, h4'):
    n = h.select_one('.sn')
    if n: n.replace_with(n.get_text() + ' ')
for m in soup.find_all('mark'): m.name = 'b'
for s_ in soup.select('section.log h2'): pass

# 先把 data-md 块换成占位符，避免 markdownify 转义
blocks = {}
for i, d in enumerate(soup.select('div[data-md]')):
    key = f'MDBLOCK{i}X'; blocks[key] = d.get_text(); d.replace_with(soup.new_string('\n\n' + key + '\n\n'))
out = mdify(str(soup), heading_style='ATX', bullets='-')
for k, v in blocks.items(): out = out.replace(k, v.strip())
out = re.sub(r'(\|[ \t]*\n)(?=[^|\n])', r'\1\n', out)
out = re.sub(r'(?m)^([^|\n][^\n]*)\n(?=\|)', r'\1\n\n', out)
out = re.sub(r'\n{3,}', '\n\n', out).strip()
head = open(headf).read().rstrip() + '\n\n'
open(dst, 'w').write(head + out + '\n')
print('written', dst, len(out))

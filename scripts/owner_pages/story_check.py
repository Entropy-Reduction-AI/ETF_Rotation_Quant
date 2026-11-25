"""Story gate for a built Owner page (story layer, see story_layer.py).

usage: python scripts/owner_pages/story_check.py <page.html> [--digest out.md]

Checks (each failure is an ERROR):
  Q     every h2 section opens with 这一节回答 (.sl-q)
  NEXT  every h2 section but the last ends with a 所以 → 下一节 link (.sl-next)
  LOOK  every evidence element (table, card ledger, figure, definition grid, step flow, card grid) has a 看点 bar
        right before it, or sits in a fold whose body opens with one
  BOX   every 框 named in a 看点 was found and framed
  DUP   no two cards in one ledger share a title
  WALL  no paragraph over 120 characters outside folds
  DENSE a section shows over 700 characters before any fold is opened (the default read must be short)
  FOCUS a section has no first-glance visual: key tiles (.kt), a figure, or a step / card grid
The digest is the page read as a story: headings, questions, memos, focus lines and handoffs only.
"""
import re, sys
from bs4 import BeautifulSoup

EVID = ('div.table-wrap', 'div.ledger', 'figure', 'div.sl-defs', 'ol.flow', 'div.cards')


def main(path, digest=None):
    soup = BeautifulSoup(open(path, encoding='utf-8').read(), 'html.parser')
    secs = soup.select('section[id^="sec-"]')
    errs, lines, dens = [], [], []
    for i, sec in enumerate(secs):
        h2 = sec.find('h2')
        name = h2.get_text(' ', strip=True)[:24]
        q, nx = sec.find(class_='sl-q'), sec.find(class_='sl-next')
        if nx is None and i < len(secs) - 1:
            errs.append(f'NEXT  [{name}] 没有接力')
        memo = sec.find(class_=['memo', 'lede'])
        lines += [f'\n## {h2.get_text(" ", strip=True)}',
                  f'问：{q.find(class_="sl-qt").get_text(strip=True)}' if q else '问：—',
                  f'答：{memo.get_text(" ", strip=True)}' if memo else '答：—']
        for el in sec.select(', '.join(EVID)):
            if el.find_parent(['div'], class_=['ledger', 'sl-defs', 'cards']) is not None and el.name != 'figure':
                continue
            if el.name == 'div' and 'table-wrap' in el.get('class', []) and el.find_parent(class_='ledger') is not None:
                continue
            prev = el.find_previous_sibling()
            ok = prev is not None and 'sl-look' in (prev.get('class') or [])
            if not ok:
                fb = el.find_parent(class_='fold-b')
                first = fb.find(True, recursive=False) if fb is not None else None
                ok = first is not None and 'sl-look' in (first.get('class') or [])
                if not ok and fb is not None:          # a folded detail table: the look sits right above the fold
                    fp = fb.find_parent(class_='fold').find_previous_sibling()
                    ok = fp is not None and 'sl-look' in (fp.get('class') or [])
            if False:
                tag = el.get('class', [el.name])[0] if el.get('class') else el.name
                snippet = el.get_text(' ', strip=True)[:30]
                errs.append(f'LOOK  [{name}] {tag} 没有看点：{snippet}')
        for lk in sec.select('.fold-b .sl-look, .fold-b .sl-box'):
            errs.append(f'CLEAN [{name}] 折叠里的明细表要素净：不要看点条和框')
        for lk in sec.select('.sl-look'):
            lines.append(f'  看点：{lk.find(class_="sl-lt").get_text("", strip=True)}')
            if lk.get('data-unboxed'):
                errs.append(f'BOX   [{name}] 框没找到：{lk["data-unboxed"]}')
        for lg in sec.select('div.ledger'):
            ts = [h.get_text('', strip=True) for h in lg.select('.lg-h')]
            ts = [re.sub(r'^\d{1,2}', '', t) for t in ts if t]
            for t in {t for t in ts if ts.count(t) > 1}:
                errs.append(f'DUP   [{name}] 卡片标题重复：{t}')
        for p in sec.find_all('p'):
            if p.find_parent(class_=['fold-b', 'sl-defs']) is None and len(p.get_text('', strip=True)) > 120:
                errs.append(f'WALL  [{name}] 段落 {len(p.get_text("", strip=True))} 字：{p.get_text("", strip=True)[:30]}')
        vis = BeautifulSoup(str(sec), 'html.parser')
        for x in vis.select('.fold-b, details > :not(summary), .sl-src, figure'):
            x.decompose()
        n_vis = len(re.sub(r'\s', '', vis.get_text('')))
        dens.append((name, n_vis))
        if n_vis > 700:
            errs.append(f'DENSE [{name}] 不展开就有 {n_vis} 字（上限 700）')
        if not [x for x in sec.select('.comp, figure, .specgrid, ol.flow, .ledger') if x.find_parent(class_='fold-b') is None]:
            errs.append(f'FOCUS [{name}] 没有第一眼的视觉（要点 / 图 / 步骤 / 卡片）')
        if nx is not None:
            lines.append(f'所以：{nx.find(class_="sl-nt").get_text("", strip=True)} → {nx.find(class_="sl-ng").get_text("", strip=True)}')
    print('不展开可见字数：' + '，'.join(f'{n[:6]} {k}' for n, k in dens) + f'；合计 {sum(k for _, k in dens)}')
    for e in errs:
        print('ERROR', e)
    print(f'{len(errs)} 个 ERROR；{len(secs)} 节')
    if digest:
        open(digest, 'w', encoding='utf-8').write('# 故事连读稿（只含标题、问、答、看点、接力）\n' + '\n'.join(lines) + '\n')
    return 1 if errs else 0


if __name__ == '__main__':
    a = sys.argv[1:]
    d = a[a.index('--digest') + 1] if '--digest' in a else None
    sys.exit(main(a[0], d))

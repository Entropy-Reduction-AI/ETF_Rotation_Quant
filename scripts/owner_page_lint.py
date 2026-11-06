"""面向 Owner 页面的发布前检查（docs/reference/owner-facing-uiux-principles.md 第 13 节）。

检查页面源 HTML（{{img:...}} 占位的那一份），不通过就不发布。规则对应 Owner 多次指出的问题：
表格是纯文本、没有结论列、没有视觉重点、和标题对不上、正文是大段纯文字。

用法：python scripts/owner_page_lint.py <page.html> [--strict]
退出码：0 = 通过；1 = 有 ERROR。WARN 要逐条看，能改就改。

表格可以用 data-lint="ref" 标为纯参考表（如名词表），只做长度检查。
"""
from __future__ import annotations

import re
import sys
from bs4 import BeautifulSoup

VERDICT_HEAD = re.compile(r'结论|判定|结果|读法|结局|状态|意味着|代价|当时|怎么处理|对愿景|得出|生效|兑现|影响')
NUM = re.compile(r'[−\-+]?\d+(\.\d+)?\s*(%|个点|倍|个|只|次|年)?')
EMPH = ('pill', 'tg', 'c-good', 'c-bad', 'c-mid', 'n-up', 'n-dn', 'n-bm', 'n-mid', 'hl', 'lt', 'ib', 'big')
CELL_MAX = 46          # 单元格最长字数（去空白）
PARA_MAX = 110         # 正文一段没有加粗时的最长字数
LI_MAX = 120


def text(el) -> str:
    return re.sub(r'\s+', '', el.get_text(' ', strip=True))


def has_emph(el) -> bool:
    if el.find(['b', 'strong']):
        return True
    for cls in EMPH:
        if el.find(class_=cls) or cls in (el.get('class') or []):
            return True
    return False


def in_fold(el) -> bool:
    return any('fold-b' in (p.get('class') or []) for p in el.parents)


def lint(path: str) -> tuple[list[str], list[str]]:
    soup = BeautifulSoup(open(path, encoding='utf-8').read(), 'html.parser')
    errors, warns = [], []
    sections = soup.find_all('section')
    for sec in sections:
        sid = sec.get('id') or '?'
        if 'status' in (sec.get('class') or []) or sid == '?':
            continue
        h2 = sec.find('h2')
        if not h2:
            continue
        title = text(h2)
        memo = sec.find('p', class_='memo')
        # S1 每节第一句是记忆句，带数字
        if memo is None:
            errors.append(f'[{sid}] 没有记忆句（p.memo）')
        elif not NUM.search(text(memo)):
            warns.append(f'[{sid}] 记忆句里没有数字：{text(memo)[:30]}…')
        # S2 每节至少一个可视元素（图、表、卡片），不能只有文字
        VIS = {'verdicts', 'why3', 'cards', 'decision', 'grid3', 'cols', 'cols2', 'cols3', 'steps'}
        visual = sec.find(['figure', 'table']) or sec.find(lambda tag: bool(VIS & set(tag.get('class') or [])))
        if not visual and not re.search(r'\{\{img:', str(sec)):
            errors.append(f'[{sid}] 整节只有文字，没有图、表或卡片')
        # S3 标题里的“：”后半句是结论，要求前面不是空泛的“概览/说明”
        if '：' not in title and ':' not in title:
            warns.append(f'[{sid}] 标题没有“问题：结论”结构：{title[:30]}')
        # S4 有数据的节先给图（Owner 2026-11-06：通篇都是表格读着累，图才能一眼看出这一节的重点）
        vis_tables = [t for t in sec.find_all('table') if not in_fold(t) and t.get('data-lint') != 'ref']
        has_img = sec.find('img') or re.search(r'\{\{img:', str(sec))
        if len(vis_tables) >= 2 and not has_img:
            errors.append(f'[{sid}] 有 {len(vis_tables)} 张展开的表、没有图：先放一张图讲重点，明细表放进折叠')
        elif len(vis_tables) == 1 and not has_img and len(vis_tables[0].find_all('tr')) > 6:
            warns.append(f'[{sid}] 一张 {len(vis_tables[0].find_all("tr"))} 行的表、没有图：考虑用图讲重点、表放折叠')
        # 表格
        for t in sec.find_all('table'):
            if in_fold(t):
                continue
            ref = t.get('data-lint') == 'ref'
            heads = [text(th) for th in t.find_all('th')]
            if not ref and not any(VERDICT_HEAD.search(h) for h in heads) and not t.find(class_='pill'):
                errors.append(f'[{sid}] 表格没有结论列（表头：{"｜".join(heads)[:60]}）')
            rows = [r for r in t.find_all('tr') if r.find('td') and not ({'peer-h', 'grp'} & set(r.get('class') or []))]
            # 第一列只是名字，加粗不算重点；重点要落在证据或结论格里
            plain = [r for r in rows if not any(has_emph(td) for td in r.find_all('td')[1:])]
            if rows and not ref and len(plain) > 0:
                errors.append(f'[{sid}] 表格有 {len(plain)}/{len(rows)} 行没有任何视觉重点（加粗、标签、颜色、条）')
            for td in t.find_all('td'):
                n = len(text(td))
                if n > CELL_MAX:
                    warns.append(f'[{sid}] 单元格 {n} 字（>{CELL_MAX}）：{text(td)[:24]}…')
                if '`' in td.get_text() or re.search(r'src/|\.py|\.csv|milestone/', td.get_text()):
                    errors.append(f'[{sid}] 正文表格里出现代码路径：{text(td)[:30]}')
            if rows and not ref and not t.find(class_=re.compile(r'^(tg|pill|ib|big)$')):
                warns.append(f'[{sid}] 表格没有决定性的格子（框、标签、条、大数字），读者不知道先看哪里')
        # 正文
        for p in sec.find_all('p'):
            if in_fold(p) or 'memo' in (p.get('class') or []) or 'cap' in (p.get('class') or []) or 'note' in (p.get('class') or []):
                continue
            if p.find_parent(class_=re.compile(r'opt|vd-card|why3|decision|grid3')):
                continue
            if len(text(p)) > PARA_MAX and not has_emph(p):
                errors.append(f'[{sid}] 正文段落 {len(text(p))} 字、没有加粗：{text(p)[:24]}…')
        for li in sec.find_all('li'):
            if in_fold(li):
                continue
            first = li.find(True)
            if not (first and first.name in ('b', 'strong') and li.get_text(strip=True).startswith(first.get_text(strip=True))):
                errors.append(f'[{sid}] 列表项没有加粗的开头短语：{text(li)[:24]}…')
            if len(text(li)) > LI_MAX:
                warns.append(f'[{sid}] 列表项 {len(text(li))} 字（>{LI_MAX}）：{text(li)[:24]}…')
    return errors, warns


if __name__ == '__main__':
    errs, ws = lint(sys.argv[1])
    for e in errs:
        print('ERROR', e)
    for w in ws:
        print('WARN ', w)
    print(f'{len(errs)} 个 ERROR，{len(ws)} 个 WARN')
    sys.exit(1 if errs or ('--strict' in sys.argv and ws) else 0)

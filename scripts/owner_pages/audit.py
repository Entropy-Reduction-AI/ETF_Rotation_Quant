import sys, re
from bs4 import BeautifulSoup
PAGES_DIR = sys.argv[1] if len(sys.argv) > 1 else 'docs/artifact'
PAGES=['v6-preflight','board','retro','oneshot','v51-health','v5-memo','v4-health','v4-memo','data-board']
VIS='pill|ib|mg|big|boxed|stk|verdict|tag|risk-hit|win|best|good|bad'
for p in PAGES:
    s=BeautifulSoup(open(f'{PAGES_DIR}/{p}/index.html').read(),'html.parser')
    main=s.select_one('main')
    out=[]
    for t in main.find_all('table'):
        if t.get('data-lint')=='ref': continue
        rows=t.select('tbody tr')
        hl=t.find_all(class_=re.compile(VIS))
        if len(hl)<max(1,len(rows)//2):
            sec=t.find_parent('section'); out.append(f'TABLE {len(rows)}r hl={len(hl)} @{sec.get("id","?")[:30]} | {t.get_text(" ",strip=True)[:60]}')
    for c in main.select('.cards'):
        cs=c.select('.card')
        if not any(x.select_one('.cv,.big,.pill,.num') for x in cs):
            out.append(f'CARDS {len(cs)} @{c.find_parent("section").get("id","?")[:30]} | {c.get_text(" ",strip=True)[:60]}')
    # runs of plain paragraphs
    for sec in main.find_all(['section','div'],recursive=True):
        run=[]
        for ch in sec.find_all(recursive=False):
            if ch.name=='p' and not (set(ch.get('class') or [])&{'memo','oneline','kv','readnote','note','table-note','tagline'}) :
                run.append(ch)
            else:
                if len(run)>=3: out.append(f'PRUN {len(run)} @{(sec.get("id") or (sec.find_parent("section") or sec).get("id","?"))[:30]} | {run[0].get_text(" ",strip=True)[:60]}')
                run=[]
        if len(run)>=3: out.append(f'PRUN {len(run)} @{(sec.get("id") or "?")[:30]} | {run[0].get_text(" ",strip=True)[:60]}')
    for ul in main.select('ul,ol'):
        if ul.get('class') and set(ul['class'])&{'flow','hq','ab-items','toc'}: continue
        lis=ul.find_all('li',recursive=False)
        if len(lis)>=4 and not ul.get('class'):
            out.append(f'LIST {len(lis)} @{(ul.find_parent("section") or ul).get("id","?")[:30]} | {lis[0].get_text(" ",strip=True)[:50]}')
    print(f'== {p}: {len(out)}'); [print('  ',o) for o in out]

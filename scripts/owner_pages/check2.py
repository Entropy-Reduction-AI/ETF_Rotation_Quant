import re, html, os
import sys
REPO = os.path.join(sys.argv[1], 'docs', 'owner')  # repo root
PAGES_DIR = sys.argv[2] if len(sys.argv) > 2 else 'docs/artifact'
pages={'board':'phase2-owner-board.md','retro':'phase2-retrospective.md','oneshot':'v5-oneshot-report.md','v51-health':'v5.1-health-check.md','v5-memo':'v5-research-memo.md','v4-health':'v4-health-check.md','v4-memo':'v4-research-memo.md','data-board':'data-board.md'}
P=re.compile(r'[\s：:，,。·、；;（）()“”"\'⭐★\-—–|/]')
def norm(s): return P.sub('',s)
for slug,f in pages.items():
    raw=open(os.path.join(REPO,f)).read()
    m=re.search(r'^## Metadata\s*$',raw,re.M); r=re.search(r'^---\s*$',raw[m.end():],re.M)
    body=raw[:m.start()]+raw[m.end()+r.end():]
    out=open(os.path.join(PAGES_DIR, slug, 'index.html')).read()
    main=out[out.index('<main>'):out.index('</main>')]; main=re.sub(r'<span class="fl-k">[^<]*</span>','',main)
    # include link targets (paths moved into hrefs)
    hrefs=' '.join(re.findall(r'href="([^"]+)"',main))
    otext=norm(html.unescape(re.sub(r'<[^>]+>','',main)+hrefs))
    miss=[]; n=0
    for line in body.split('\n')[1:]:
        t=line
        if t.strip().startswith('![') or re.match(r'^\s*\|?\s*-{3,}',t) or re.match(r'^\s*</?(details|summary)',t): continue
        t=re.sub(r'!\[[^\]]*\]\([^)]*\)','',t)
        t=re.sub(r'\[([^\]]*)\]\([^)]*\)',r'\1',t); t=re.sub(r'\[([^\]]*)\]\([^)]*\)',r'\1',t)
        t=re.sub(r'</?(summary|details)>','',t).replace('\\','').replace('**','').replace('~~','').replace('`','').replace('\\','')
        t=re.sub(r'^\s*(#+|>|[-*]|\d+\.)\s*','',t).replace('▶','')
        t=re.sub(r'^\d+\.\s*','',t)
        for c in (t.split('|') if t.count('|')>=2 else [t]):
            c=norm(c)
            if len(c)<2: continue
            n+=1
            if c not in otext: miss.append(c[:80])
    print(f'{slug:11s} checked {n} missing {len(miss)}')
    for x in miss: print('    ',x)

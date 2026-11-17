"""Screenshot selected elements: args slug:selector:index ... -> one sheet."""
import os, sys
from playwright.sync_api import sync_playwright
from PIL import Image
out=sys.argv[1]; specs=sys.argv[2:]
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME") or None)
    pg = b.new_page(viewport={"width":1440,"height":900}, device_scale_factor=1)
    ims=[]; cur=None
    for sp in specs:
        slug, sel, idx = sp.split('|')
        if slug!=cur:
            pg.goto("file://" + os.path.abspath(os.path.join(os.environ.get("PAGES_DIR", "docs/artifact"), slug, "index.html")))
            pg.evaluate("document.querySelectorAll('details').forEach(d=>d.open=true);document.querySelectorAll('.fold-b').forEach(d=>d.removeAttribute('hidden'));document.querySelectorAll('img').forEach(i=>i.loading='eager')")
            pg.wait_for_timeout(600); cur=slug
        loc=pg.locator(sel).nth(int(idx)); loc.scroll_into_view_if_needed(); pg.wait_for_timeout(150)
        os.makedirs('shots', exist_ok=True); f=f'shots/el-{len(ims)}.png'; loc.screenshot(path=f); ims.append(Image.open(f))
    W=max(i.size[0] for i in ims); H=sum(i.size[1]+28 for i in ims)
    sh=Image.new('RGB',(W,H),(255,0,255)); y=0
    for i in ims: sh.paste(i,(0,y)); y+=i.size[1]+28
    sh.save(out); print(sh.size)
    b.close()

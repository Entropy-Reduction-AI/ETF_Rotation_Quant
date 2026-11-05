import sys,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[3]; sys.path.insert(0,str(ROOT))
from src.v4.r5.design import load_containers
ac = {str(r.get('id')): str(r.get('asset_class')) for r in load_containers()}
def group(c):
    a = ac.get(c, '')
    if c == 'cash' or a == '现金': return '现金'
    if c == 'gold': return '黄金'
    if a == '债券' or '债' in c: return '债券'
    if a in ('A股宽基', 'A股红利'): return 'A股宽基'
    if a == 'A股行业': return 'A股行业'
    if a == '港股': return '港股'
    if a == '美股宽基': return '美股宽基'
    if a == '美股和全球主题' or c.startswith('theme-'): return '海外主题'
    if a == '商品': return '商品'
    return a or '其他'

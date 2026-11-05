"""统一的 Owner 页面构建：基础样式 + 体检报告组件 + 注意力样式 + 叙事组件（story.css），图片内联。
用法：python build_owner.py <源.html> <输出.html> <标题> <图片目录1> [图片目录2 ...]
发布前必须先过 scripts/owner_page_lint.py。
"""
import re, base64, pathlib, sys, subprocess
D = pathlib.Path('/home/claude/work')
src, out, title, *dirs = sys.argv[1:]
lint = subprocess.run(['python3', str(pathlib.Path(__file__).with_name('owner_page_lint.py')), src], capture_output=True, text=True)
print(lint.stdout.strip().splitlines()[-1])
if lint.returncode:
    print(lint.stdout); sys.exit('lint 未通过，不构建')
b = (D / 'h5/build.py').read_text()
css_src = (D / 'page/build_memo5.py').read_text()
css = css_src[css_src.index("css='''") + 7:css_src.index("'''\ncss=css.replace")].replace('<title>v5 研究备忘</title>', f'<title>{title}</title>')
extra = b[b.index("extra='") + 7:b.index("'\nextra=extra+")].encode().decode('unicode_escape').encode('latin1').decode('utf8')
extra += '<style>' + (D / 'attention.css').read_text() + '</style><style>' + (D / 'story.css').read_text() + '</style>'
c = pathlib.Path(src).read_text()
A = [pathlib.Path(x) for x in dirs]
def img(m):
    f = next(a / f'{m.group(1)}.png' for a in A if (a / f'{m.group(1)}.png').exists())
    return f'<figure><img alt="{m.group(2)}" src="data:image/png;base64,' + base64.b64encode(f.read_bytes()).decode() + '"></figure>'
c = re.sub(r'\{\{img:([\w.-]+)\|([^}]*)\}\}', img, c)
pathlib.Path(out).write_text(css + extra + c)
print('built', out, len(css + extra + c))

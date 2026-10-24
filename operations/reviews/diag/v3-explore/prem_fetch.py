import json,urllib.request,time
def g(u,ref='https://fundf10.eastmoney.com/'):
    rq=urllib.request.Request(u,headers={'Referer':ref,'User-Agent':'Mozilla/5.0'})
    for k in range(4):
        try: return urllib.request.urlopen(rq,timeout=20).read().decode('utf-8','ignore')
        except Exception: time.sleep(2+3*k)
print(json.loads(g("https://fundsuggest.eastmoney.com/FundSearch/api/FundSearchAPI.ashx?m=1&key=501225"))['Datas'][0]['NAME'])
for code,mk in [('159529','sz'),('501225','sh')]:
    r=json.loads(g(f"https://api.fund.eastmoney.com/f10/lsjz?fundCode={code}&pageIndex=1&pageSize=20")); n=r['TotalCount']; rows=r['Data']['LSJZList']
    for p in range(2,(n+19)//20+1): rows+=json.loads(g(f"https://api.fund.eastmoney.com/f10/lsjz?fundCode={code}&pageIndex={p}&pageSize=20"))['Data']['LSJZList']; time.sleep(0.1)
    json.dump(rows,open(f'{code}_nav.json','w'),ensure_ascii=False)
    k=[]
    for y in range(2019,2027):
        t=json.loads(g(f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={mk}{code},day,{y}-01-01,{y}-12-31,400,",ref='https://gu.qq.com/'))
        d=t['data'][mk+code]; k+=d.get('day') or d.get('qfqday') or []
    json.dump(k,open(f'{code}_px.json','w')); print(code,len(rows),len(k), rows[-1]['FSRQ'], k[0][0] if k else None)

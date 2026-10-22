import json,urllib.request,time,sys,os
codes=['513100','513500','159941','513300','159612','159740','159866','513130','513180','513520','513650']
def get(code,page):
    u=f"https://api.fund.eastmoney.com/f10/lsjz?fundCode={code}&pageIndex={page}&pageSize=20"
    rq=urllib.request.Request(u,headers={'Referer':'https://fundf10.eastmoney.com/','User-Agent':'Mozilla/5.0'})
    for k in range(4):
        try: return json.load(urllib.request.urlopen(rq,timeout=20))
        except Exception as e: time.sleep(2+k*3)
    raise SystemExit(f'fail {code} {page}')
for code in codes:
    fn=f'qdii_nav/{code}.json'
    if os.path.exists(fn): continue
    r=get(code,1); n=r['TotalCount']; rows=r['Data']['LSJZList']
    for p in range(2,(n+19)//20+1):
        rows+=get(code,p)['Data']['LSJZList']; time.sleep(0.15)
    json.dump(rows,open(fn,'w'),ensure_ascii=False); print(code,len(rows),flush=True)

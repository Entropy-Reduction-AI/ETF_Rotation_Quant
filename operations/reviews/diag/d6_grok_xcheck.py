import sqlite3,csv,collections
c=sqlite3.connect('file:data/market.sqlite?mode=ro',uri=True)
G='incoming/grok-pit-20261022/'
# 1) index launch vs first date with real OHLC (high!=low or open!=close) in bars/ohlc_supplement
print("== index launch vs OHLC gap ==")
osup=[r[1] for r in c.execute("pragma table_info(ohlc_supplement)")]
rows=list(csv.DictReader(open(G+'index_launch.csv')))
res=collections.Counter()
for r in rows:
    code=r['index_code'];ld=r['launch_date']
    q=c.execute("select min(date),max(date) from bars where code=?",(code,)).fetchone()
    if not q[0]: res['no_bars']+=1;continue
    fc=q[0]
    fo=c.execute("select min(date) from bars where code=? and open is not null and high is not null and low is not null and not(open=high and high=low and low=close)",(code,)).fetchone()[0]
    if 'date' in osup:
        fs=c.execute("select min(date) from ohlc_supplement where code=?",(code,)).fetchone()[0]
    else: fs=None
    real=min([x for x in (fo,fs) if x],default=None)
    if not ld: tag='no_launch'
    elif real is None: tag='never_ohlc'
    elif fc>=ld: tag='close_starts_after_launch'
    else:
        gap_end=real
        d=(int(gap_end[:4])-int(ld[:4]))*12+int(gap_end[5:7])-int(ld[5:7])
        tag='ohlc_at_launch(±3m)' if abs(d)<=3 else ('ohlc_after_launch' if d>3 else 'ohlc_before_launch')
    res[tag]+=1
    if tag not in('ohlc_at_launch(±3m)','close_starts_after_launch'):
        print(f"{code:14s} {r['index_name'][:14]:14s} launch={ld} close_from={fc} ohlc_from={real} {tag}")
print(dict(res))
# 2) dividends: etf_events vs cash_dividends
print("== dividends ==")
ev=collections.defaultdict(dict)
for r in csv.DictReader(open(G+'etf_events.csv')):
    if r['event_type']=='现金分红' and r['ex_date']: ev[r['code']][r['ex_date']]=float(r['cash_per_unit'] or 'nan')
db=collections.defaultdict(dict)
for code,ex,amt in c.execute("select code,ex_date,amount from cash_dividends"): db[code][ex]=amt
trust=['510300','510330','588080','512400','515210','510880','515100','511260','511010','511020']
for code in sorted(set(ev)|set(trust)):
    if code not in trust and code not in db: continue
    a,b=ev.get(code,{}),db.get(code,{})
    both=set(a)&set(b); mism=[d for d in both if abs(a[d]-b[d])>1e-4]
    print(f"{code} trusted={code in trust} grok={len(a)} db={len(b)} match={len(both)-len(mism)} mism={len(mism)} only_grok={len(set(a)-set(b))} only_db={len(set(b)-set(a))}")
print(collections.Counter(r['event_type'] for r in csv.DictReader(open(G+'etf_events.csv'))))

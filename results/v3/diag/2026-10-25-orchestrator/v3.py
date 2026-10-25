import sys; sys.path.insert(0,'/data/explore'); import bt; from bt import *
exec(open('v1.py').read().split("res={}")[0].split("from bt import *")[1])
avail={'中证500':'2007-01-15','中证红利':'2008-05-26','中证1000':'2014-10-17','黄金':'2100-01-01'}
for c in ['能源','原材料','工业','可选消费','主要消费','医药','金融地产','信息技术','通信','公用事业']: avail[c]='2011-08-02'
Pm=P.copy()
for c,d in avail.items(): Pm.loc[:pd.Timestamp(d)-pd.Timedelta(days=1),c]=np.nan
bt.P=Pm; P=Pm
r=run(topn(5,[20,60,120,250])); print('v3近似·按发布日池子',{k:round(v,3) for k,v in stats(r).items()})
y=r.groupby(r.index.year).apply(lambda x:(1+x).prod()-1); print(y.round(3).to_dict())
pickle.dump(r,open('res3.pkl','wb'))

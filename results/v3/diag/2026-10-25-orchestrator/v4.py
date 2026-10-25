import sys; sys.path.insert(0,'/data/explore'); import bt; from bt import *
exec(open('v1.py').read().split("res={}")[0].split("from bt import *")[1])
P0=P.copy(); ind=['能源','原材料','工业','可选消费','主要消费','医药','金融地产','信息技术','通信','公用事业']
def go(name,drop):
    global P
    Pm=P0.copy(); Pm[drop]=np.nan; bt.P=Pm; P=Pm
    r=run(topn(5,[20,60,120,250])); print(name,{k:round(float(v),3) for k,v in stats(r).items()})
go('补全池子·不含黄金',['黄金'])
go('补全池子·不含行业',ind)

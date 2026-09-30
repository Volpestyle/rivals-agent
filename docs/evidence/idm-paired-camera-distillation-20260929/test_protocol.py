import importlib.util
import numpy as np
from pathlib import Path
p=Path(__file__).parent
s=importlib.util.spec_from_file_location('probe',p/'probe.py'); m=importlib.util.module_from_spec(s); s.loader.exec_module(m)
stores={'live':{'pts':[144.8,145.,145.2]},'replay':{'pts':[114.2,114.4,114.6]}}
assert m.block({'live':[0,1,2],'replay':[0,1,2]},stores)=='purged'
assert m.block({'live':[0],'replay':[0]},stores)=='fit'
assert m.block({'live':[2],'replay':[2]},stores)=='report'
z=np.array([[0.,1.],[1.,0.],[2.,1.],[3.,0.]])
t=np.ones((4,2))*np.array([2.,-3.]); mean,std,b,c=m.fit(z,t,np)
assert np.allclose(b,0) and np.allclose(c,[2,-3])
a=m.metrics(np.array([1.,-1.]),np.zeros(2),np)
assert a['sign_recall']==0 and a['rms']==0 and a['mae']==1
print('Synthetic purge, ridge intercept, zero/sign controls passed; no data access.')

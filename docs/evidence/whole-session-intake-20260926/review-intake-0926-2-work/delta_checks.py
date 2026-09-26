import copy,dataclasses,hashlib,io,json,sys
from pathlib import Path
from unittest.mock import patch
R=Path.cwd();O=Path(__file__).parent;H=O.parent;sys.path.insert(0,str(R))
from agent import human_demos as hd,human_intake as hi
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
expected={'agent/human_demos.py':'614042e5cb8eb45164a4b7d3b49249180048dd9c530ae14c540484fb8e72dd38','agent/human_intake.py':'8ecf85e48181568f9af9fd81de0227b0c0e54cb3ad613a6a870d19dbdecf53e0','tests/test_human_demos.py':'d952b428ab1b9574fe8d6db8ab5687ff829ff635f2beea8937ce471695d85c4b','tests/test_human_intake.py':'fc81c28e77684c0a15987f415f5821730fb240270d8124c126340619baaa1c96'}
pins={}
for rel,h in expected.items():
 p=R/rel;got=hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest();assert got==h,(rel,got);pins[rel]=dict(raw=sha(p),lf=got)
for name in ('audit.py','relocation_repro.py'):assert sha(O/name)==sha(H/'review-intake-0926-work'/name)
base=dict(schema_version=1,sessions=[dict(session_id='split1',session_group='group1',split='train',video_path='train.mkv',recorded_video_path='train.mkv',expected_media_sha256='a'*64)])
results=[]
def run(name,doc,expected_error=None):
 p=O/'synthetic-registry.json';p.write_text(json.dumps(doc))
 for loader in ('read_splits','check_registry'):
  try:r=hd.read_splits(p) if loader=='read_splits' else hi.check_registry(p,denylist={'sessions':[]})
  except hd.DemoError as e:
   assert expected_error and expected_error in str(e),(name,loader,str(e));results.append(dict(case=name,loader=loader,result=str(e)))
  else:
   assert expected_error is None,(name,loader,'unexpected acceptance');assert len(r)==1;results.append(dict(case=name,loader=loader,result='one split placement only'))
for cat in hd.EXCLUDED_LISTS:
 excluded=dict(session_id='excluded1',video_path='excluded.mkv',expected_media_sha256='b'*64)
 if cat=='evaluation_sessions':excluded['kind']='reader_validation'
 doc=copy.deepcopy(base);doc[cat]=[excluded];run(cat+' clean',doc)
 changes=[('id',dict(session_id='split1'),'session id'),('relative alias',dict(video_path='./subdir/../train.mkv'),'media path'),('hash',dict(expected_media_sha256='a'*64),'media sha256'),('split',dict(split='train'),'carries a split'),('sealed',dict(sealed=False),'carries a split')]
 for label,change,error in changes:
  d=copy.deepcopy(doc);d[cat][0].update(change);run(cat+' '+label,d,error)
 for key,value,error in [('session_id','excluded1','session id'),('video_path','excluded.mkv','media path'),('expected_media_sha256','b'*64,'media sha256')]:
  d=copy.deepcopy(doc);second=dict(excluded,session_id='excluded2',video_path='other.mkv',expected_media_sha256='c'*64);second[key]=value;d[cat].append(second);run(cat+' within-list '+key,d,error)
 if cat=='evaluation_sessions':
  for kind in hd.SPLITS:
   d=copy.deepcopy(doc);d[cat][0]['kind']=kind;run('split-kind '+kind,d,'names a split')
for key,value,error in [('session_id','cal','session id'),('video_path','cal.mkv','media path'),('expected_media_sha256','b'*64,'media sha256')]:
 d=copy.deepcopy(base);d['calibration_sessions']=[dict(session_id='cal',video_path='cal.mkv',expected_media_sha256='b'*64)];e=dict(session_id='eval',video_path='eval.mkv',kind='match_dev',expected_media_sha256='c'*64);e[key]=value;d['evaluation_sessions']=[e];run('cross-list '+key,d,error)
# An artifact stream whose second readline raises: proves rejection precedes a body read, not merely JSON parsing.
reg=O/'gate2-reg.json';placement=hd.read_splits(reg)[0];artifact=O/'guarded-artifact.jsonl';baseheader=dict(format=hd.FORMAT,**dataclasses.asdict(placement),sealed=False,media_sha256='1'*64,payload_sha256='0'*64)
class HeaderOnly(io.StringIO):
 def __init__(self,text):super().__init__(text);self.reads=0
 def readline(self,*a,**kw):
  self.reads+=1
  assert self.reads==1,'BODY READ'
  return super().readline(*a,**kw)
original_open=Path.open;guarded=[]
for name,header,unseal,expected_error in [('gate2 header',baseheader,False,'gate2 artifact is sealed'),('lying train header',dict(baseheader,split='train'),False,'gate2 session is sealed'),('unsealed bad flag',baseheader,True,'sealed header mismatch'),('missing flag',{k:v for k,v in baseheader.items() if k!='sealed'},True,'sealed header mismatch')]:
 stream=HeaderOnly(json.dumps(header)+'\n')
 def opener(path,*args,**kwargs):return stream if path==artifact else original_open(path,*args,**kwargs)
 with patch.object(Path,'open',opener):
  try:hi.load_dataset_relocated(artifact,splits=reg,denylist={'sessions':[]},relocation={},unseal=unseal)
  except hd.DemoError as e:assert expected_error in str(e);guarded.append(dict(case=name,error=str(e),readline_calls=stream.reads))
  else:raise AssertionError('unexpected acceptance')
assert len(results)==50
out=dict(handback_sha256=sha(H/'admission-owner-final-27.md'),pins=pins,original_scripts_byte_identical=True,registry_cases=results,guarded_artifact_cases=guarded)
(O/'delta-checks.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(dict(pins=pins,registry_checks=len(results),guarded_artifact_cases=guarded,handback_sha256=out['handback_sha256']),indent=1))

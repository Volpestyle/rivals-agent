import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys

import pytest

B = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(B/'writer'))
import cm3_accounting as a
import make_accounting_bundle as maker
import make_receipt


def write(root, name, value):
    path=root/name;path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(maker.encoded(value))
    return {'path':str(path.resolve()),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def doc(ref):
    content=Path(ref['path']).read_bytes()
    if hashlib.sha256(content).hexdigest()!=ref['sha256']:
        raise ValueError('hash mismatch')
    return json.loads(content)


def source(root):
    owner=write(root,'outputs/r3/inputs/result.json',{'elapsed_stage_seconds':5})
    owner['path']='/outputs/r3/inputs/result.json'
    reservation={'attempt_id':'x','reserved_compute_seconds':520,'reserved_usd':1,
                 'bounds':{'rate_usd_second':.00071784,'overhead_usd':.02}}
    result={'format':'cm3-inputs-wrapper-result-v1','attempt_id':'x','status':'INCOMPLETE',
       'owner_result':owner,'teardown':{'status':'TERMINAL','identity':a.IDENTITY,'apps':['app-x'],
       'events':[{'terminal_apps':['app-x'],'containers':0}],'checked_at_unix':1000},
       'spend':{'seconds_through_cleanup':10.2,'estimated_conservative_usd':.02+10.2*.00071784}}
    row={'attempt_id':'x','reservation':write(root,'bootstrap/x/reservation.json',reservation),
         'result':write(root,'result.json',result)}
    inv=write(root,'inventory.json',{'format':'cm3-reservation-inventory-v1',
        'campaign_id':'r3-20260926-l40s','reservations':{'x':row['reservation']}})
    ledger=write(root,'source-ledger.json',{'format':'cm3-measured-accounting-v1',
        'approved_by':'herdr-lead','campaign_id':'r3-20260926-l40s','basis_seconds':12159,
        'basis_usd':6.18374656,'inventory':inv,'settlements':[row]})
    return ledger,owner


@pytest.fixture
def bundle(tmp_path):
    old,owner=source(tmp_path/'source')
    host=maker.build(old,tmp_path/'host/bundle',tmp_path/'source/outputs')
    container=maker.build(old,tmp_path/'container/inputs/bundle',tmp_path/'source/outputs')
    return host,container,owner


def budget(ref):
    totals=a.ledger(ref,doc)
    return {'accounting':ref,'approved_by':'herdr-lead','spent_seconds':totals['spent_seconds'],
      'spent_usd':totals['spent_usd'],'cap_seconds':57600,'cloud_cap_usd':50,
      'cloud_instance':'cuda:L40S','hourly_usd':2.584224,'stage_seconds':100,
      'hold_seconds':520,'hold_usd':.393277,'stage_overhead_usd':.02}


def test_two_roots_identical_ledger_and_real_owner_reader(bundle):
    host,container,owner=bundle
    assert host['path']!=container['path'] and host['sha256']==container['sha256']
    assert Path(host['path']).read_bytes()==Path(container['path']).read_bytes()
    from policy.range_bc import cm3_run
    left=a.ledger(host,doc,required_results=[owner])
    right=a.allocation(budget(container),cm3_run.document,required_results=[owner])
    assert left==right
    assert left['spent_seconds']==12170 and left['spent_usd']==6.21164356
    for path in Path(host['path']).parent.rglob('*.json'):
        rel=path.relative_to(Path(host['path']).parent)
        assert path.read_bytes()==(Path(container['path']).parent/rel).read_bytes()


def test_writer_existing_mount_mapping_reads_same_bundle(bundle):
    host,_,_=bundle
    allocation=budget(host)
    allocation['accounting']={'path':'/inputs/bundle/ledger.json','sha256':host['sha256']}
    writer=make_receipt.Writer({'amendment':3,'device':'cuda','hardware':{'class':'cuda:L40S'}},
        {'allocation':allocation,'stage_results':{}},{'approvals':[]},
        mounts=[('/inputs',str(Path(host['path']).parent.parent))])
    assert writer.budget('inputs',{})['spent_seconds']==12170


@pytest.mark.parametrize('name',['/absolute.json','../escape.json','a/../b.json','a//b.json',
    './a.json','a/./b.json','C:/host.json','a\\b.json','','.'])
def test_bad_logical_references_refused(bundle,name):
    host,_,_=bundle
    data=doc(host);data['settlements'][0]['result']['path']=name
    changed=write(Path(host['path']).parent,'bad-ledger.json',data)
    with pytest.raises(ValueError):a.ledger(changed,doc)


def test_transported_file_mutation_refuses(bundle):
    host,container,_=bundle
    (Path(container['path']).parent/'results/x.json').write_text('{}')
    assert a.ledger(host,doc)['spent_seconds']==12170
    with pytest.raises(ValueError,match='hash mismatch'):a.ledger(container,doc)


def test_changed_owner_path_with_same_hash_refuses(bundle):
    host,_,owner=bundle
    owner=dict(owner,path='/outputs/r3/other/result.json')
    with pytest.raises(ValueError,match='predecessor'):a.ledger(host,doc,required_results=[owner])


def test_resolver_escape_refuses_before_reader(bundle,tmp_path):
    host,_,_=bundle
    outside=tmp_path/'outside.json';outside.write_text('{}')
    root=Path(host['path']).parent
    reader=a.bundle_document(host,lambda _:pytest.fail('escaped target was read'),
        local_path=lambda name:root if Path(name)==root else outside)
    with pytest.raises(ValueError,match='escaped'):reader({'path':'escape.json','sha256':'0'*64})


def test_actual_inventory_hash_and_missing_attempt_refuse(bundle):
    host,_,_=bundle
    inv=a.ledger(host,doc)['inventory']
    assert a.ledger(host,doc,inventory=inv)['spent_seconds']==12170
    with pytest.raises(ValueError,match='inventory changed'):a.ledger(host,doc,inventory={})
    inv['x']['sha256']='0'*64
    with pytest.raises(ValueError,match='inventory changed'):a.ledger(host,doc,inventory=inv)


@pytest.mark.parametrize('mutation',['missing','duplicate','cleanup','owner_elapsed','basis','rate','clock','estimate'])
def test_v2_settlement_guards_preserved(bundle,mutation):
    host,_,_=bundle;root=Path(host['path']).parent;data=doc(host)
    row=data['settlements'][0]
    if mutation=='missing':data['settlements']=[]
    elif mutation=='duplicate':data['settlements']*=2
    elif mutation=='basis':data['basis_seconds']-=1
    elif mutation=='owner_elapsed':
        p=root/'outputs/r3/inputs/result.json';write(root,p.relative_to(root),{'elapsed_stage_seconds':999})
    else:
        key='reservation' if mutation=='rate' else 'result'
        value=json.loads((root/row[key]['path']).read_bytes())
        if mutation=='cleanup':value['teardown']['status']='UNKNOWN'
        if mutation=='rate':value['bounds']['rate_usd_second']=0
        if mutation=='clock':value['spend']['seconds_through_cleanup']=-1
        if mutation=='estimate':value['spend']['estimated_conservative_usd']=0
        ref=write(root,row[key]['path'],value);row[key]['sha256']=ref['sha256']
        if key=='reservation':
            inv=json.loads((root/data['inventory']['path']).read_bytes());inv['reservations']['x']=row[key]
            data['inventory']['sha256']=write(root,'inventory.json',inv)['sha256']
    changed=write(root,'ledger.json',data)
    with pytest.raises(ValueError):a.ledger(changed,doc)


@pytest.mark.parametrize('field,value',[('spent_seconds',12169),('spent_usd',0),('cap_seconds',57601),
    ('cloud_cap_usd',51),('hold_seconds',99),('hold_seconds',50000),('hold_usd',.01),
    ('hold_usd',50),('hourly_usd',-1),('stage_overhead_usd',float('inf'))])
def test_v2_allocation_guards_preserved(bundle,field,value):
    host,_,_=bundle;b=budget(host);b[field]=value
    with pytest.raises(ValueError):a.allocation(b,doc)


def test_v1_not_accepted_for_new_allocation(bundle,tmp_path):
    host,_,_=bundle;b=budget(host);old,_=source(tmp_path/'legacy')
    b['accounting']=old
    with pytest.raises(ValueError,match='canonical v2'):a.allocation(b,doc)

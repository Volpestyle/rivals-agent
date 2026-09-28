import copy
import hashlib
import json

import pytest
np = pytest.importorskip('numpy')
from policy.idm import yaw_support as S


def artifact():
    return S.calibrate(np.zeros((8,128)), np.ones((10,128)), [10,20,30],
                       provenance={k:'a'*64 for k in ('manifest_sha256','code_sha256','row_manifest_sha256')})


def test_uniform_selection_short_and_endpoints():
    assert S.uniform_indices(1,512) == [0]
    assert S.uniform_indices(3,512) == [0,1,2]
    assert S.uniform_indices(10,4) == [0,3,6,9]
    assert len(set(S.uniform_indices(999,512))) == 512


def test_population_statistics_quantiles_and_floor():
    a=artifact()
    assert a['rate_p995'] == pytest.approx(29.9)
    assert a['feature_p99'] == pytest.approx(1000)
    S.validate(a)
    assert np.array_equal(a['variance'], np.zeros(128))


def test_boundaries_reason_union_and_no_prediction_mutation():
    a=artifact(); a['rate_p995']=30
    p={'yaw_deg':.5, 'pitch_deg':.2, 'yaw_std_deg':.1}
    out=S.apply(a,np.ones(128),p,1e9/60)
    assert out['support']['answered'] and out['yaw_deg']==.5 and p['yaw_deg']==.5
    out=S.apply(a,np.ones(128)*2,p,1e6)
    assert out['yaw_deg'] is None and out['pitch_deg']==.2
    assert out['support']['reasons']==['train_rotation_rate','feature_support']
    p['yaw_deg']=None
    assert S.apply(a,np.ones(128)*2,p,1e6)['support']['reasons']==['existing_uncertainty','feature_support']


@pytest.mark.parametrize('value', [0,-1,float('nan'),float('inf')])
def test_invalid_duration_refuses(value):
    with pytest.raises(ValueError): S.apply(artifact(),np.zeros(128),{'yaw_deg':None},value)


@pytest.mark.parametrize('value', [float('nan'),float('inf')])
def test_nonfinite_refusal(value):
    with pytest.raises(ValueError): S.apply(artifact(),np.full(128,value),{'yaw_deg':0},1e7)
    with pytest.raises(ValueError): S.rate(value,1e7)


def test_artifact_pin_checkpoint_and_recipe_refuse(tmp_path):
    a=artifact(); p=tmp_path/'support.json'; p.write_text(json.dumps(a))
    sha=hashlib.sha256(p.read_bytes()).hexdigest()
    assert S.load(p,sha)==a
    with pytest.raises(ValueError): S.load(p,'0'*64)
    with pytest.raises(ValueError): S.load(p,sha,checkpoint='0'*64)
    for key,val in [('tap','other'),('variance_floor',.1),('mean',[1]*127),('variance',[-1]*128)]:
        b=copy.deepcopy(a); b[key]=val
        with pytest.raises(ValueError): S.validate(b)


def test_no_error_outcomes_are_inputs_to_calibration():
    # Fixed sample statistics and exact percentile, no accuracy/coverage search.
    x=np.arange(1280,dtype=float).reshape(10,128)
    a=S.calibrate(x,x+1,[1,2,3],provenance=artifact()['provenance'])
    assert a['mean']==x.mean(0).tolist()
    assert a['feature_p99']==float(np.quantile(S.distance(x+1,x.mean(0),x.var(0)),.99))


def test_roster_refuses_later_match_and_role_swap_before_payload():
    from policy.idm.yaw_support_run import roster, RANGES, DEV, MATCHES
    m={'sessions':[{'session_id':s,'role':'train'} for s in (*RANGES,*MATCHES)]
                    +[{'session_id':s,'role':'dev'} for s in DEV]}
    roster(m)
    bad=copy.deepcopy(m);bad['sessions'][-1]['role']='train'
    with pytest.raises(ValueError):roster(bad)
    bad=copy.deepcopy(m);bad['sessions'][0]['session_id']='20260927T053838-153Z-150600-7'
    with pytest.raises(ValueError):roster(bad)


def test_camera_feature_tap_exactly_matches_forward():
    torch=pytest.importorskip('torch')
    from policy.idm.model import IDM, Config
    torch.set_num_threads(2);torch.manual_seed(13)
    m=IDM(Config(height=24,width=32,test_scale=True)).eval()
    x=torch.rand(2,16,24,32);hud=torch.rand(2,6,80,200)
    with torch.inference_mode():
        expected=m(x,hud)[1]
        cam=m.camera(m.motion(x));cam[:,2:]=cam[:,2:].clamp(-12,8)
    assert torch.equal(cam,expected)


def test_checkpoint_provenance_contains_dev_but_never_trains_it():
    from policy.idm.yaw_support_run import checkpoint_roster, RANGES, DEV, MATCHES
    entries=[{'session_id':s,'role':'dev' if s in DEV else 'train',
              'targets_sha256':'a'*64,'frames_sha256':'b'*64} for s in (*RANGES,*MATCHES,*DEV)]
    m={'sessions':entries}
    original={'sessions':[{**e,'role':'heldout' if e['session_id'] in DEV else 'train'} for e in entries]}
    meta={'targets':{e['session_id']:{'split':
                       ('idm_train' if e['session_id'] in MATCHES else 'train'),'sha256':'a'*64} for e in entries},
          'frame_stores':{e['session_id']:{'manifest_sha256':'b'*64} for e in entries}}
    checkpoint_roster(meta,m,original)
    for bad in ('val','test','idm_train'):
        changed=copy.deepcopy(meta);changed['targets'][DEV[0]]['split']=bad
        with pytest.raises(ValueError):checkpoint_roster(changed,m,original)
    changed=copy.deepcopy(meta);changed['targets'][RANGES[0]]['sha256']='c'*64
    with pytest.raises(ValueError):checkpoint_roster(changed,m,original)
    changed=copy.deepcopy(meta);changed['targets']['later-match']={}
    with pytest.raises(ValueError):checkpoint_roster(changed,m,original)
    changed=copy.deepcopy(original);changed['sessions'][-1]['role']='train'
    with pytest.raises(ValueError):checkpoint_roster(meta,m,changed)

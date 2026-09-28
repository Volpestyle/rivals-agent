"""Bounded TRAIN selection and identical camera comparison denominators."""
import copy
import subprocess
import sys
import pytest

pytest.importorskip("torch")
from policy import idm_targets as T
from policy.idm import match_diagnostic as D


def test_roster_import_needs_no_torch_for_decode_environment():
    code = '''import sys
class NoTorch:
    def find_spec(self, fullname, *args):
        if fullname == "torch" or fullname.startswith("torch."):
            raise RuntimeError("decode environment has no torch")
sys.meta_path.insert(0, NoTorch())
from policy.idm.match_diagnostic import SESSIONS
assert len(SESSIONS) == 5
'''
    subprocess.run([sys.executable, "-c", code], check=True)


def target(n=240, sid="s", start_i=0):
    rows=[]
    for k in range(n):
        rows.append(dict(i=start_i+k, run="r", segment="seg", t0_ns=k*16666667,
                         t1_ns=(k+1)*16666667, suitability="accepted", gap_free=True,
                         regime="normal", frame1=dict(frame_index=2*k, composition_ns=k*16666667),
                         yaw_deg=0.0 if k%2 else 1.0, pitch_deg=0.0,beyond_pad_envelope=False))
    return T.Targets(dict(session_id=sid,split="idm_train",frame_period_ns=8333333),rows)


def test_extremes_have_full_context_and_ignore_truth_values():
    t=target()
    rows,selection=D.choose(t,block_rows=60)
    assert [r['i'] for r in rows]==list(range(8,68))+list(range(172,232))
    changed=copy.deepcopy(t)
    for r in changed.rows:r['yaw_deg']=9999
    assert D.choose(changed,block_rows=60)[1]==selection
    assert t.header['split']=='idm_train' and len(t.rows)==240


def test_gap_and_segment_edges_never_supply_context():
    t=target(400)
    t.rows[80]['gap_free']=False
    for r in t.rows[300:]:r['segment']='next'
    rows,_=D.choose(t,block_rows=60)
    assert max(r['i'] for r in rows[:60])<72
    assert min(r['i'] for r in rows[60:])>=308


def test_short_or_overlapping_source_refuses():
    with pytest.raises(ValueError,match='overlap'):D.choose(target(100),block_rows=60)
    with pytest.raises(ValueError,match='no complete'):D.choose(target(50),block_rows=60)


def test_role_not_relabelled():
    t=target();t.header['split']='val'
    with pytest.raises(ValueError,match='TRAIN'):D.choose(t,block_rows=60)


def test_pooling_sparse_ids_keeps_sources_separate():
    a,b=target(60,'a',1000),target(60,'b',940)
    p={'a':{r['i']:dict(yaw_deg=0.0,pitch_deg=0.0) for r in a.rows},
       'b':{r['i']:dict(yaw_deg=2.0,pitch_deg=0.0) for r in b.rows}}
    result=D.summaries([a,b],p)['pooled']['yaw_deg']
    assert result['abs_error_deg']['n']==120
    assert result['abs_error_deg']['mean']==1
    assert result['sum_error_deg_by_window']['60']['n']==2


def test_common_answers_share_axis_rows_and_sum_windows():
    t=target(120)
    p={name:{'s':{r['i']:dict(yaw_deg=0.1,pitch_deg=0.2) for r in t.rows}}
       for name in ('full03','prior','zero')}
    p['full03']['s'][1]['yaw_deg']=None
    p['prior']['s'][61]['pitch_deg']=None
    common=D.common_answers(p)
    for name in common:
        assert common[name]['s'][1]['yaw_deg'] is None
        assert common[name]['s'][61]['pitch_deg'] is None
        assert common[name]['s'][1]['pitch_deg']==.2
        report=D.summaries([t],common[name])['pooled']
        for axis in ('yaw_deg','pitch_deg'):
            assert report[axis]['abs_error_deg']['n']==119
            assert report[axis]['sum_error_deg_by_window']['60']['n']==1

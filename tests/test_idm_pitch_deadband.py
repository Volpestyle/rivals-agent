import copy
import pytest

pytest.importorskip('torch')
from policy import idm_targets as T
from policy.idm import pitch_deadband as P


def target(n, sid, split='train'):
    rows=[]
    for k in range(n):
        rows.append(dict(i=k,run='r',segment='s',t0_ns=k*16666667,t1_ns=(k+1)*16666667,
                         suitability='accepted',gap_free=True,regime='normal',
                         frame0={'frame_index':2*k-2},
                         frame1={'frame_index':2*k,'composition_ns':k*16666667},
                         pitch_deg=.8 if k%2 else 0,yaw_deg=.5))
    return T.Targets(dict(session_id=sid,split=split,frame_period_ns=8333333),rows)


def metrics(all=.3,still=.2,moving=.5,window=3,n=100):
    return {k:{'n':n,'mean':v} for k,v in [('all',all),('still',still),('moving',moving),('one_second',window)]}


def test_identity_unknown_edges_and_yaw_are_exact():
    p={i:dict(yaw_deg=y,pitch_deg=v,pitch_std_deg=.7,press={'jump':.3})
       for i,(y,v) in enumerate([(None,None),(-0.,-0.),(1,.1),(2,-.1),(3,.100001)])}
    original=copy.deepcopy(p)
    assert P.correct(p,0)==p
    q=P.correct(p,.1)
    assert [v['pitch_deg'] for v in q.values()]==[None,0,0,0,.100001]
    for i in p:
        assert q[i]['yaw_deg']==p[i]['yaw_deg']
        assert q[i]['pitch_std_deg']==p[i]['pitch_std_deg']
        assert q[i]['press']==p[i]['press']
    assert p==original
    with pytest.raises(ValueError):P.correct(p,.12)


def test_train_quantiles_source_refusal_and_no_truth_selection():
    t=target(9016,P.RANGES[0]);rows,s=P.select(t,'train')
    assert len(rows)==3600
    assert [g['first_i'] for g in s['runs']]==[8,2708,5408,8108]
    for r in t.rows:r['pitch_deg']=999
    assert P.select(t,'train')[1]==s
    with pytest.raises(ValueError):P.select(target(1816,P.RANGES[0]),'train')
    with pytest.raises(ValueError):P.select(target(9016,P.DEV[0]),'train')


def test_unread_context_embargo_samples_and_gap_chunks():
    from policy.idm import match_diagnostic as D
    t=target(6016,D.SESSIONS[0],'idm_train')
    previous=t.rows[100:1000]+t.rows[5000:5900]
    old={'row_ids':[r['i'] for r in previous],
         'blocks':[{'t0_ns':t.rows[a]['t0_ns'],'t1_ns':t.rows[b]['t1_ns']} for a,b in [(100,999),(5000,5899)]]}
    rows,s=P.select(t,'match',old,[6000])
    assert rows and len(rows)%60==0
    for r in rows:
        assert r['i'] not in old['row_ids']
        assert not P.overlap(P.context(r),(184,2014))
        assert not P.context(r)[0]<=6000<=P.context(r)[1]
        assert all(not (r['t0_ns']<b['t1_ns']+10**9 and r['t1_ns']>b['t0_ns']-10**9) for b in old['blocks'])
    assert all(len(g)%60==0 for g in P.runs(rows))
    t.rows[3000]['gap_free']=False
    after,_=P.select(t,'match',old,[6000])
    assert 3000 not in [r['i'] for r in after]


def test_equal_source_scoring_and_tie_choose_smallest():
    c={tau:{'a':metrics(),'b':metrics(n=10000)} for tau in P.THRESHOLDS}
    for tau in (.05,.1):
        c[tau]={'a':metrics(all=.25,still=.15),'b':metrics(all=.25,still=.15,n=10000)}
    # Source-macro .26 loses, although the large source is much better.
    c[.2]={'a':metrics(all=.42,still=.15),'b':metrics(all=.1,still=.15,n=10000)}
    assert P.choose_candidate(c)[0]==.05


@pytest.mark.parametrize('change',[{'moving':.511},{'window':3.061},{'still':.195},{'all':.301}])
def test_train_and_dev_guards_veto_without_retuning(change):
    base={'s':metrics()};candidate={'s':metrics(still=.15,**{k:v for k,v in change.items() if k!='still'})}
    if 'still' in change:candidate['s']['still']['mean']=change['still']
    assert not P.gate(base,candidate)[0]


def test_insufficient_support_and_unknown_coverage_refuse():
    b={'s':metrics()};c={'s':metrics(still=.15)}
    b['s']['moving']['n']=29;c['s']['moving']['n']=29
    assert not P.gate(b,c)[0]
    b={'s':metrics()};c={'s':metrics(still=.15)};c['s']['all']['n']=99
    assert not P.gate(b,c)[0]


def test_one_second_never_crosses_segment_boundary():
    t=target(120,P.RANGES[0]);t.rows[30]['segment']='other'
    p={r['i']:{'pitch_deg':r['pitch_deg'],'yaw_deg':r['yaw_deg']} for r in t.rows}
    assert P.score(t,p)['one_second']['n']==1

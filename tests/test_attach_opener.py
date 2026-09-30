"""Opt-in attach drift cancellation, with the real guarded Live and fake pad/capture."""
import threading
import time
from types import SimpleNamespace

import pytest

from agent.controller import Live, RangeLost
from test_loop import Pad


def test_opener_is_first_non_neutral_report_and_fresh_frame_follows_neutral():
    pad=Pad()
    frames=[]
    def grab():
        frame=SimpleNamespace(index=len(frames))
        frames.append(frame)
        return frame
    def attach():
        assert frames and not pad.reports  # range proof already happened before attach
        return pad
    live=Live(pad_factory=attach,capture=SimpleNamespace(grab=grab),guard=lambda f:True,
              settle_s=0,attach_opener_deadline=time.perf_counter()+1)
    try:
        buttons,axes=pad.reports[0]
        assert not buttons and axes['l']==(0.,.25) and axes['r']==(0.,0.)
        assert axes['rt']==axes['lt']==0
        assert all(not b and a['l']==(0.,0.) and a['r']==(0.,0.) for b,a in pad.reports[1:])
        record=live.attach_opener
        assert record['report_returned'] and record['release_at']-record['started_t'] <= .05+1e-9
        assert record['fresh_frame_t'] > record['neutral_returned_t']
        assert live.frame_t==record['fresh_frame_t'] and pad.neutral()
    finally:
        live.close()


def test_bad_initial_range_never_creates_pad_or_sends_opener():
    with pytest.raises(RangeLost):
        Live(pad_factory=lambda:pytest.fail('must not attach'),capture=SimpleNamespace(grab=lambda:'lobby'),
             guard=lambda f:False,settle_s=0,attach_opener_deadline=time.perf_counter()+1)


def test_scope_loss_during_opener_closes_in_constructor_and_releases():
    pad=Pad()
    with pytest.raises(RangeLost,match='during attach opener'):
        Live(pad_factory=lambda:pad,capture=SimpleNamespace(grab=lambda:'range'),
             guard=lambda f:not pad.reports,settle_s=0,attach_opener_deadline=time.perf_counter()+1)
    assert pad.neutral()
    assert len([a for _,a in pad.reports if a['l'] != (0.,0.)])==1


def test_opener_lease_releases_even_if_following_capture_blocks_before_bind():
    pad=Pad()
    blocked,unblock=threading.Event(),threading.Event()
    result=[]
    def grab():
        if pad.reports and pad.reports[0][1]['l']==(0.,.25) and not unblock.is_set():
            blocked.set()
            assert unblock.wait(1)
        return 'range'
    def construct():
        result.append(Live(pad_factory=lambda:pad,capture=SimpleNamespace(grab=grab),guard=lambda f:True,
                           settle_s=0,attach_opener_deadline=time.perf_counter()+1))
    worker=threading.Thread(target=construct)
    worker.start()
    try:
        assert blocked.wait(1)
        time.sleep(.1)
        assert pad.neutral()  # constructor still blocked, lease watchdog did the release
    finally:
        unblock.set()
        worker.join(1)
        for live in result: live.close()
    assert result and not worker.is_alive() and pad.neutral()


def test_default_live_does_not_add_new_input():
    pad=Pad()
    live=Live(pad_factory=lambda:pad,capture=SimpleNamespace(grab=lambda:'range'),guard=lambda f:True,settle_s=0)
    try:
        assert live.attach_opener is None and not pad.reports
    finally:
        live.close()

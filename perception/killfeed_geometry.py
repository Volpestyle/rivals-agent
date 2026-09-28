"""Unwired feed-geometry observations, NEVER an evaluation-anchor authority.

Names/portraits are not templates. Colour pairing proposes rows; correspondence
of an old row at a displaced position proposes a shifted arrival. Neither is a
mode cue. No positive QM-specific cue is established, so live always abstains.
"""
from __future__ import annotations

import hashlib
import json
import weakref
from dataclasses import dataclass

import cv2
import numpy as np
from perception import match_timer as M

_ISSUED = weakref.WeakKeyDictionary()


@dataclass(frozen=True, eq=False, init=False)
class ScanEvidence:
    source_sha256: str
    recording_manifest_sha256: str
    frame_count: int
    scanned: int
    missing_or_unreadable: int
    team_clock_seen: bool
    complete: bool

    def __init__(self, *args, **kwargs):
        raise ValueError('only inspect_recording constructs scan evidence')


def inspect_recording(indexed_frames, recording_bytes, expected_manifest_sha256):
    """Caller supplies pinned whole-recording metadata; enumeration is checked.

    Does not prove provenance of arbitrary arrays or authenticate a caller's pin.
    Metadata admission/review remains necessary. A cropped interval is forbidden.
    """
    if hashlib.sha256(recording_bytes).hexdigest() != expected_manifest_sha256:
        raise ValueError('recording metadata pin differs')
    meta=json.loads(recording_bytes)
    source=meta['source_sha256']; count=meta['frame_count']
    if len(source)!=64 or any(c not in '0123456789abcdef' for c in source) \
            or type(count) is not int or count<=0 or meta.get('first_frame')!=0 \
            or meta.get('scope')!='whole_recording':
        raise ValueError('whole-recording bounds and source SHA required')
    n=0; unknown=0; team=False; valid=True
    for index,frame in indexed_frames:
        if type(index) is not int or index!=n or n>=count or not native(frame):
            valid=False; break
        clocks=M.read_frame(frame)
        team |= clocks['team_a'] is not None or clocks['team_b'] is not None
        unknown += all(v is None for v in clocks.values())
        n+=1
    values=(source,expected_manifest_sha256,count,n,unknown,team,valid and n==count)
    obj=object.__new__(ScanEvidence)
    for name,value in zip(ScanEvidence.__dataclass_fields__,values): object.__setattr__(obj,name,value)
    _ISSUED[obj]=values
    return obj


def guard(evidence, source_sha256, recording_manifest_sha256, frame_index):
    if not isinstance(evidence,ScanEvidence) or evidence not in _ISSUED:
        return 'unissued_scan'
    if tuple(getattr(evidence,k) for k in ScanEvidence.__dataclass_fields__)!=_ISSUED[evidence]:
        return 'tampered_scan'
    if not evidence.complete or evidence.scanned!=evidence.frame_count:
        return 'incomplete_scan'
    if evidence.source_sha256!=source_sha256 or evidence.recording_manifest_sha256!=recording_manifest_sha256 \
            or type(frame_index) is not int or not 0<=frame_index<evidence.frame_count:
        return 'scan_identity_or_bounds'
    if evidence.team_clock_seen: return 'match_team_clock_veto'
    return 'positive_quick_match_cue_missing'


def native(frame):
    return isinstance(frame,np.ndarray) and frame.shape==(1440,2560,3) and frame.dtype==np.uint8


def row_candidates(crop):
    """Engineering geometry only: aligned blue/green text within a narrow row.

    Deliberately cannot distinguish every UI/text/scene false positive. Outputs
    remain diagnostics even when a replay prompt is present.
    """
    if crop.ndim!=3 or crop.shape[2]!=3 or crop.dtype!=np.uint8:
        raise ValueError('uint8 BGR feed crop required')
    b,g,r=(crop[...,k].astype(np.int16) for k in range(3))
    blue=(b>r+20)&(b>g+5)&(b>70)
    green=(g>r+15)&(g>b+5)&(g>60)
    active=(blue.sum(1)>=8)&(green.sum(1)>=8)
    groups=[]
    for y in np.flatnonzero(active):
        if not groups or y-groups[-1][-1]>3:groups.append([])
        groups[-1].append(int(y))
    rows=[]
    for group in groups:
        lo,hi=group[0],group[-1]+1
        if not 6<=hi-lo<=32:continue
        by,bx=np.where(blue[lo:hi]);gy,gx=np.where(green[lo:hi])
        if len(bx)<40 or len(gx)<40:continue
        if not 30<float(np.median(gx)-np.median(bx))<400:continue
        rows.append({'top':max(0,lo-5),'bottom':min(len(crop),hi+5),'ink_top':lo,'ink_bottom':hi})
    return rows


def shifted_arrival(previous,current):
    """Consecutive native frames only; caller owns PTS. No empty-feed anchor."""
    a,b=row_candidates(previous),row_candidates(current)
    if not a or len(b)!=len(a)+1:return {'candidate':False,'reason':'not_one_added_shifted_row'}
    # An arrival at the top must move every old row down by a consistent amount.
    matches=[]
    for old,new in zip(a,b[1:]):
        shift=new['ink_top']-old['ink_top']
        if not 20<=shift<=50:return {'candidate':False,'reason':'invalid_row_displacement'}
        y0,y1=old['top'],old['bottom']
        if y1+shift>len(current):return {'candidate':False,'reason':'clipped_old_row'}
        # High-pass intensity compares old text/portrait structure, rather than
        # granting a match to any two broad blue/green row backgrounds.
        def detail(image):
            return cv2.Laplacian(cv2.cvtColor(image,cv2.COLOR_BGR2GRAY),cv2.CV_32F,ksize=3)
        x=detail(previous[y0:y1])[:,2:-2]
        search=detail(current[max(0,y0+shift-2):min(len(current),y1+shift+2)])
        if float(x.std())<8 or search.shape[0]<x.shape[0]:return {'candidate':False,'reason':'weak_row'}
        score=float(cv2.matchTemplate(search,x,cv2.TM_CCOEFF_NORMED).max())
        if not np.isfinite(score) or score<.8:return {'candidate':False,'reason':'old_row_not_preserved'}
        matches.append({'shift':shift,'score':score})
    if max(m['shift'] for m in matches)-min(m['shift'] for m in matches)>2:
        return {'candidate':False,'reason':'inconsistent_displacement'}
    return {'candidate':True,'reason':'unqualified_shift_observation','matches':matches}


def observe(frame, *, scan=None, source_sha256=None, recording_manifest_sha256=None, index=None):
    if not native(frame):return {'layout':None,'reason':'invalid_native_frame'}
    clocks=M.read_frame(frame)
    live=row_candidates(frame[20:200,1990:2530]); replay=row_candidates(frame[280:460,1990:2530])
    # No positive mode assertion from generic row geometry, clock absence or
    # prompt-only evidence. The successor's qualification remains outstanding.
    reason=guard(scan,source_sha256,recording_manifest_sha256,index)
    if clocks['team_a'] is not None or clocks['team_b'] is not None:reason='competitive_unsupported'
    return {'layout':None,'reason':reason,'live_rows':live,'replay_rows':replay}

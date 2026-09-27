"""Reproduce Modal Volume's unsupported hard-link operation without cloud work."""
from concurrent.futures import ThreadPoolExecutor
import json
import os

import pytest

from cloud.modal_guard import stages
from cloud.modal_guard.common import Refused


def identity(clock):
    return {"attempt_id":"volume-01", "code_sha256":"a"*64, "inputs_sha256":"b"*64,
            "recipe_sha256":"c"*64, "output_volume_id":"vo-fresh", "deadline_unix":clock.wall()+100}


def test_volume_without_hardlinks_completes_and_reenters(tmp_path, clock, monkeypatch):
    def denied(*a, **kw): raise PermissionError(1, "Operation not permitted")
    monkeypatch.setattr(os, "link", denied)
    events=[]
    def compute(root):
        events.append("compute")
        (root/"model.bin").write_bytes(b"complete")
        return 0
    kw=dict(commit=lambda:events.append("commit"),reload=lambda:None,wall=clock.wall)
    first=stages.run(tmp_path/"stage", "fit", identity(clock), ["model.bin"], compute, **kw)
    again=stages.run(tmp_path/"stage", "fit", identity(clock), ["model.bin"], compute, **kw)
    assert again==first
    assert events==["commit","compute","commit","commit"]


def test_exclusive_claim_has_one_winner_and_never_overwrites(tmp_path):
    path=tmp_path/"receipt.json"
    def create(i):
        try: stages.claim(path,{"winner":i}); return i
        except FileExistsError:return None
    with ThreadPoolExecutor(max_workers=6) as pool:results=list(pool.map(create,range(6)))
    winners=[r for r in results if r is not None]
    assert len(winners)==1 and json.loads(path.read_bytes())=={"winner":winners[0]}


@pytest.mark.parametrize("marker", ["started.json", "completed.json"])
def test_torn_volume_receipt_never_recomputes(tmp_path, clock, marker):
    root=tmp_path/"partial";root.mkdir()
    (root/marker).write_bytes(b'{"identity":')
    calls=[]
    with pytest.raises((Refused,json.JSONDecodeError)):
        stages.run(root,"fit",identity(clock),["model.bin"],lambda p:calls.append(p),
                   commit=lambda:None,reload=lambda:None,wall=clock.wall)
    assert calls==[]

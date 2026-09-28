import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from policy.idm import local_store as L


@pytest.fixture
def rig(tmp_path):
    source = tmp_path/'volume'
    store = source/'synthetic'
    store.mkdir(parents=True)
    (store/'frames.u8').write_bytes(bytes(range(8)))
    (store/'hud.u8').write_bytes(b'\x03' * (2 * 80 * 200 * 3))
    header = {'format': 'rivals-idm-frames-v1', 'session_id': 'synthetic', 'media_sha256': 'a'*64,
              'width': 2, 'height': 2, 'hud_shape': [80, 200, 3], 'frame_indices': [0, 1],
              'frames_sha256': L.sha(store/'frames.u8'), 'hud_sha256': L.sha(store/'hud.u8')}
    (store/'frames.json').write_text(json.dumps(header))
    item = {'session_id': 'synthetic', 'role': 'train', 'store': str(store),
            'targets': 'unchanged-target', 'frames_sha256': L.sha(store/'frames.json')}
    target = SimpleNamespace(session_id='synthetic', header={'media_sha256': 'a'*64})
    cache = tmp_path/'local'
    def prepare():
        return L.prepare([(item, target)], source_root=source, cache=cache,
                         identity={'input': 'fixed'}, progress=lambda _: None)
    return SimpleNamespace(prepare=prepare, source=source, store=store, item=item,
                           target=target, cache=cache, tmp=tmp_path)


def test_verified_copy_changes_only_store_path_and_reuses_exact_bytes(rig):
    rows, receipt = rig.prepare()
    assert receipt['source_and_destination_verified'] and not receipt['reused']
    assert rows[0][1] is rig.target
    assert {k: v for k, v in rows[0][0].items() if k != 'store'} == {
        k: v for k, v in rig.item.items() if k != 'store'}
    for name in ('frames.json', 'frames.u8', 'hud.u8'):
        assert (rig.store/name).read_bytes() == (Path(rows[0][0]['store'])/name).read_bytes()
    assert rig.prepare()[1]['reused']


def test_partial_cache_refuses_without_copying_again(rig):
    rig.cache.mkdir()
    with pytest.raises(ValueError, match='partial'):
        rig.prepare()


def test_source_corruption_never_publishes_completion(rig):
    (rig.store/'frames.u8').write_bytes(b'x'*8)
    with pytest.raises(ValueError, match='source copy hash'):
        rig.prepare()
    assert not (rig.cache/'complete.json').exists()


def test_completed_cache_corruption_refuses(rig):
    rig.prepare()
    (rig.cache/'synthetic/frames.u8').write_bytes(b'x'*8)
    with pytest.raises(ValueError, match='bytes differ'):
        rig.prepare()


def test_destination_is_independently_hashed(rig, monkeypatch):
    original = L.sha
    monkeypatch.setattr(L, 'sha', lambda p: '0'*64 if Path(p) == rig.cache/'synthetic/frames.u8' else original(p))
    with pytest.raises(ValueError, match='local copy hash'):
        rig.prepare()
    assert not (rig.cache/'complete.json').exists()


def test_identity_change_refuses_reuse(rig):
    rig.prepare()
    with pytest.raises(ValueError, match='identity'):
        L.prepare([(rig.item, rig.target)], source_root=rig.source, cache=rig.cache,
                  identity={'input': 'different'})


@pytest.mark.parametrize('change', ['pin', 'media', 'outside', 'size'])
def test_wrong_source_refused_before_destination_exists(rig, change):
    if change == 'pin':
        rig.item['frames_sha256'] = '0'*64
    elif change == 'media':
        rig.target.header['media_sha256'] = 'b'*64
    elif change == 'outside':
        rig.item['store'] = str(rig.tmp)
    else:
        (rig.store/'hud.u8').write_bytes(b'bad')
    with pytest.raises(ValueError):
        rig.prepare()
    assert not rig.cache.exists()


def test_no_local_disk_space_refuses_before_copy(rig, monkeypatch):
    monkeypatch.setattr(L.shutil, 'disk_usage', lambda _: SimpleNamespace(free=0))
    with pytest.raises(ValueError, match='disk'):
        rig.prepare()
    assert not rig.cache.exists()


def test_source_header_pin_is_raw_bytes(rig):
    assert rig.item['frames_sha256'] == hashlib.sha256((rig.store/'frames.json').read_bytes()).hexdigest()


def test_resolved_source_mount_alias_is_accepted(rig):
    alias = rig.tmp/'mount-alias'
    try:
        alias.symlink_to(rig.source, target_is_directory=True)
    except OSError:
        pytest.skip('symlink creation unavailable on this host')
    item = {**rig.item, 'store': str(alias/'synthetic')}
    rows, _ = L.prepare([(item, rig.target)], source_root=alias, cache=rig.cache,
                        identity={'input': 'fixed'}, progress=lambda _: None)
    assert Path(rows[0][0]['store']).is_relative_to(rig.cache)


def test_source_payload_symlink_refused(rig):
    outside = rig.tmp/'outside.u8'
    payload = rig.store/'frames.u8'
    payload.rename(outside)
    try:
        payload.symlink_to(outside)
    except OSError:
        pytest.skip('symlink creation unavailable on this host')
    with pytest.raises(ValueError, match='outside'):
        rig.prepare()
    assert not rig.cache.exists()

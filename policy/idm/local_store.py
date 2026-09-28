"""Hash-verified ephemeral native stores, after the existing admission preflight.

Only store locations change. Targets, rows, roles, source manifests and the
production FrameStore verification stay unchanged. No discovery or decoding.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import time


def need(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def write_new(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n')


def plan(loaded, source_root):
    """Caller supplies the already-admitted targets, never just session names."""
    source_root = Path(source_root).resolve(strict=True)
    files, directories = {}, {}
    for item, target in loaded:
        sid = target.session_id
        need(Path(sid).name == sid and sid not in ('', '.', '..') and '\\' not in sid, 'invalid session path')
        need(sid == item['session_id'] and sid not in directories, 'session mismatch or duplicate')
        store = Path(item['store'])
        need(not store.is_symlink() and store.resolve(strict=True).is_relative_to(source_root),
             'source store outside admitted mount')
        header = store/'frames.json'
        need(not header.is_symlink() and sha(header) == item['frames_sha256'], 'frame manifest pin differs')
        manifest = json.loads(header.read_bytes())
        need(manifest['session_id'] == sid and manifest['media_sha256'] == target.header['media_sha256'],
             'frame source identity differs')
        need(manifest['format'] == 'rivals-idm-frames-v1' and manifest['hud_shape'] == [80, 200, 3],
             'native store format differs')
        n = len(manifest['frame_indices'])
        expected = {'frames.json': (item['frames_sha256'], header.stat().st_size),
                    'frames.u8': (manifest['frames_sha256'], n * manifest['height'] * manifest['width']),
                    'hud.u8': (manifest['hud_sha256'], n * 80 * 200 * 3)}
        directories[sid] = str(store.resolve(strict=True))
        for name, (pin, size) in expected.items():
            source = store/name
            need(not source.is_symlink() and source.resolve(strict=True).is_relative_to(source_root),
                 'source file outside admitted mount')
            need(source.is_file() and source.stat().st_size == size, 'native store byte count differs')
            files[sid+'/'+name] = {'source': str(source), 'bytes': size, 'sha256': pin}
    need(bool(files), 'empty local store plan')
    return files


def copy_file(source, destination, expected):
    start = time.perf_counter()
    h, count = hashlib.sha256(), 0
    with Path(source).open('rb') as src, Path(destination).open('xb') as dst:
        for block in iter(lambda: src.read(1 << 20), b''):
            dst.write(block)
            h.update(block)
            count += len(block)
    copied = time.perf_counter() - start
    need(count == expected['bytes'] and h.hexdigest() == expected['sha256'], 'source copy hash differs')
    start = time.perf_counter()
    need(sha(destination) == expected['sha256'], 'local copy hash differs')
    return {'copy_source_hash_seconds': copied, 'destination_verify_seconds': time.perf_counter()-start}


def prepare(loaded, *, source_root, cache, identity, progress=print):
    files = plan(loaded, source_root)
    cache = Path(cache)
    need(not cache.is_symlink(), 'local cache is a symlink')
    need(not cache.resolve().is_relative_to(Path(source_root).resolve()), 'cache must be off source mount')
    pins = {name: {k: entry[k] for k in ('bytes', 'sha256')} for name, entry in files.items()}
    binding = {'identity': identity, 'sources': {k: v['source'] for k, v in files.items()}, 'files': pins}
    marker = cache/'complete.json'
    started = time.perf_counter()
    if cache.exists():
        need(marker.is_file() and not marker.is_symlink(), 'partial local cache refused')
        before = sha(marker)
        receipt = json.loads(marker.read_bytes())
        need(receipt['binding'] == binding, 'local cache identity differs')
        for name, expected in pins.items():
            path = cache/name
            need(not path.is_symlink() and path.resolve(strict=True).is_relative_to(cache.resolve()),
                 'local cache path differs')
            need(path.stat().st_size == expected['bytes'] and sha(path) == expected['sha256'],
                 'local cache bytes differ')
        need(sha(marker) == before, 'local receipt changed')
        timing = {'reused': True, 'copy_source_hash_seconds': 0,
                  'destination_verify_seconds': time.perf_counter()-started}
    else:
        need(shutil.disk_usage(cache.parent).free >= sum(v['bytes'] for v in pins.values()) + (2 << 30),
             'insufficient local disk')
        cache.mkdir(exist_ok=False)
        timing = {'reused': False, 'copy_source_hash_seconds': 0., 'destination_verify_seconds': 0.}
        for name, entry in files.items():
            destination = cache/name
            destination.parent.mkdir(exist_ok=True)
            measured = copy_file(entry['source'], destination, entry)
            for key, seconds in measured.items():
                timing[key] += seconds
            progress({'phase': 'local_copy', 'file': name, **timing})
        write_new(marker, {'binding': binding, 'timing': timing})  # complete, last
    relocated = [({**item, 'store': str(cache/target.session_id)}, target) for item, target in loaded]
    return relocated, {'bytes': sum(v['bytes'] for v in pins.values()), 'files': pins,
                       'seconds': time.perf_counter()-started, **timing,
                       'source_and_destination_verified': True, 'completion_sha256': sha(marker)}

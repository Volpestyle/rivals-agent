"""Resume pinned upload one file at a time; never launches an app or fit."""
import json
from pathlib import Path
import sys
import threading
import time

from modal_lifecycle import connect, atomic
from upload_press import sha

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'code'))
from scripts.job_status import write


def main():
    import modal
    from modal_proto import api_pb2
    client = connect()
    raw_pin = sha(ROOT / 'upload-attempt2-manifest.json')
    assert sha(ROOT / 'upload-manifest.json') == raw_pin
    rows = json.loads((ROOT / 'upload-manifest.json').read_text())
    volume = modal.Volume.from_name('rivals-idm-press-20260927-inputs')
    volume.hydrate(client=client)
    job = 'idm-press-cloud-upload-20260927-03'
    write(job, owner='idm-owner', host='mac', stage='running', evidence=str(ROOT / 'upload-resume.log'))
    from modal._utils.async_utils import synchronizer
    internal = synchronizer._translate_in(client)
    async def exists(pin):
        # Same content-presence query used by SDK 1.5.5's own batch uploader.
        return (await internal.stub.MountPutFile(api_pb2.MountPutFileRequest(sha256_hex=pin))).exists
    exists_sync = synchronizer.create_blocking(exists)
    cache = []
    for i, row in enumerate(rows):
        assert sha(row['source']) == row['sha256'], row['path']
        available = exists_sync(row['sha256'])
        cache.append({**row, 'server_blob_present': available})
        print(json.dumps({'path': row['path'], 'cached': available}), flush=True)
        write(job, progress=f'Verified {i+1}/{len(rows)} pinned source/cache identities')
    atomic(ROOT / 'upload-resume-cache.json', cache)
    journal = ROOT / 'upload-resume-committed.jsonl'
    committed = {r['path']: r['sha256'] for r in map(json.loads, journal.read_text().splitlines())} if journal.exists() else {}
    # Known server content attaches without retransmission. Remaining blobs run
    # serially so the SDK's one-hour per-file timer excludes queue contention.
    for i, row in enumerate(sorted(cache, key=lambda x: not x['server_blob_present'])):
        if committed.get(row['path']) == row['sha256']:
            continue
        description = f"Committing {i+1}/{len(rows)}: {row['path']} ({row['bytes']/1e9:.2f} GB)"
        write(job, progress=description)
        stop = threading.Event()
        def heartbeat():
            while not stop.wait(60):
                write(job, progress=description)
        thread = threading.Thread(target=heartbeat, daemon=True)
        thread.start()
        try:
            with volume.batch_upload(force=True) as batch:
                batch.put_file(row['source'], '/' + row['path'])
        finally:
            stop.set()
            thread.join()
        with journal.open('a') as stream:
            stream.write(json.dumps({'path':row['path'],'sha256':row['sha256'],'at':time.time()})+'\n')
            stream.flush()
            __import__('os').fsync(stream.fileno())
    with volume.batch_upload(force=True) as batch:
        batch.put_file(ROOT / 'upload-manifest.json', '/upload-manifest.json')
    atomic(ROOT / 'upload-receipt.json', {'files':len(rows),'bytes':sum(r['bytes'] for r in rows),
        'volume_id':volume.object_id,'volume_name':'rivals-idm-press-20260927-inputs',
        'manifest_sha256':raw_pin,'run_manifest_sha256':sha(ROOT/'run-manifest.json'),
        'compute_launched':False,'recovery':'serial per-file commits; server content reuse',
        'server_cached_files':sum(r['server_blob_present'] for r in cache)})
    (ROOT/'upload.exit').write_text('0\n')
    write(job, stage='done', progress='All pinned files committed; ready for worker hash verification')


if __name__=='__main__':
    try:
        main()
    except BaseException:
        write('idm-press-cloud-upload-20260927-03',stage='failed',progress='See upload-resume.log')
        (ROOT/'upload.exit').write_text('1\n')
        raise

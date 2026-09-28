"""Serial pinned upload; manual volume teardown under the lead's $8.25 decision.

No AppCreate, image build, fit, automatic deletion or new spend guard.
"""
from pathlib import Path
import hashlib
import json
import os
import sys
import threading
import time

ROOT=Path('/Users/james/dev/idm-data/expanded-refit-d4f05e0')
CODE=ROOT/'runtime-authority10/code'
sys.path.insert(0,str(CODE))
from cloud.modal_guard.common import atomic,caffeinated
from cloud.modal_guard.provider import connect,Provider,unpack
from cloud.modal_guard import release
from cloud.modal_guard.runner import status

RELEASE='5c0e979227738363bfceaef792d9852d2578fcc149f77d2f9cde61510dc8a8fd'
MANIFEST='bf06e8e4c5ff491515315a5f23415e8e274640bf38644a5c950add9d4ffea290'
VOLUME='rivals-idm-expanded-20260928-01-inputs'
JOB='idm-expanded-upload-20260928-01'

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1<<20),b''):h.update(block)
    return h.hexdigest()

def main():
    release.verify(CODE/'cloud/modal_guard',RELEASE)
    release.reviewed(Path('/Users/james/dev/modal_guard/volpestyle'),RELEASE)
    assert sha(ROOT/'upload-manifest.json')==MANIFEST
    assert (ROOT/'table-preflight-02.exit').read_text().strip()=='0'
    table=json.loads((ROOT/'table-preflight-02.json').read_bytes())
    assert table['status']=='PASS' and len(table['sessions'])==13
    rows=json.loads((ROOT/'upload-manifest.json').read_bytes())
    assert len(rows)==57 and sum(r['bytes'] for r in rows)==113955631920
    assert len({r['path'] for r in rows})==len(rows)
    import modal
    client=connect()
    _,rate_receipt=Provider().rates()
    from decimal import Decimal
    storage_rate=Decimal(unpack(rate_receipt)['volume_storage_gib_month_cost'])
    assert storage_rate<=Decimal('0.09'), 'storage rate exceeds approved bound'
    atomic(ROOT/'upload-rate-receipt.json',rate_receipt,fresh=True)
    try:
        existing=modal.Volume.from_name(VOLUME,create_if_missing=False)
        existing.hydrate(client=client)
    except modal.exception.NotFoundError:
        pass
    else:
        raise RuntimeError('Fresh volume already exists; inspect before any resume')
    volume=modal.Volume.from_name(VOLUME,create_if_missing=True)
    volume.hydrate(client=client)
    created=time.time()
    atomic(ROOT/'input-volume.json',{'name':VOLUME,'id':volume.object_id,'created_unix':created,
        'setup_cap_usd':'1.65','expanded_campaign_cap_usd':'8.25','lane_cap_usd':'25',
        'cleanup_plan':'After refit report lands, owner checks exact ID/name via modal volume list --json, deletes once via CLI, and records receipt. No automatic deletion code.',
        'bytes_bound':113955631920+len((ROOT/'upload-manifest.json').read_bytes()),
        'storage_rate_usd_gib_month':str(storage_rate),'budgeted_days':5,'free_allowance_assumed':False},fresh=True)
    journal=ROOT/'upload-committed.jsonl'
    for i,row in enumerate(rows):
        description=f"{i+1}/{len(rows)} {row['path']} ({row['bytes']/1e9:.2f} GB)"
        status(JOB,progress=description)
        print(json.dumps({'stage':'verify_upload','file':row['path'],'bytes':row['bytes'],'at':time.time()}),flush=True)
        stop=threading.Event()
        def heartbeat():
            while not stop.wait(60):status(JOB,progress=description)
        thread=threading.Thread(target=heartbeat,daemon=True);thread.start()
        try:
            source=Path(row['source'])
            assert source.is_file() and not source.is_symlink() and source.stat().st_size==row['bytes']
            assert sha(source)==row['sha256'],str(source)
            # SDK content-addressed upload may reuse existing blobs. Prior volumes
            # are never mounted or mutated; each file commits separately.
            with volume.batch_upload(force=False) as batch:
                batch.put_file(source,'/'+row['path'])
            assert source.stat().st_size==row['bytes']
            with journal.open('a') as f:
                f.write(json.dumps({'path':row['path'],'bytes':row['bytes'],'sha256':row['sha256'],'at':time.time()})+'\n')
                f.flush();os.fsync(f.fileno())
        finally:
            stop.set();thread.join()
    with volume.batch_upload(force=False) as batch:
        batch.put_file(ROOT/'upload-manifest.json','/upload-manifest.json')
    remote=b''.join(volume.read_file('/upload-manifest.json'))
    assert hashlib.sha256(remote).hexdigest()==MANIFEST
    result={'status':'UPLOADED','volume_name':VOLUME,'volume_id':volume.object_id,
        'files':len(rows),'bytes':sum(r['bytes'] for r in rows),'seconds':time.time()-created,
        'upload_manifest_sha256':MANIFEST,'run_manifest_sha256':sha(ROOT/'run-manifest.json'),
        'source_hashes_verified':True,'remote_manifest_readback_verified':True,
        'worker_payload_rehash':'required before fit','appcreates':0,'image_builds':0}
    atomic(ROOT/'upload-receipt.json',result,fresh=True)
    return result

if __name__=='__main__':
    status(JOB,owner='idm-owner',host='mac',stage='running',evidence=str(ROOT/'upload.log'))
    try:
        with caffeinated():result=main()
        (ROOT/'upload.exit').write_text('0\n')
        status(JOB,stage='done',progress='Pinned files uploaded; probe pending')
        print(json.dumps(result),flush=True)
    except BaseException:
        (ROOT/'upload.exit').write_text('1\n')
        status(JOB,stage='failed',progress='Stopped; no automatic retry or AppCreate; manual volume cleanup retained')
        raise

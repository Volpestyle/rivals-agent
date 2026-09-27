"""Explicit small SSL packet upload; no compute app."""
import json
from pathlib import Path
import sys
import time
from idm_worker import digest
from modal_lifecycle import connect, atomic
from modal_budget import INPUT_VOLUME

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'code'))
from scripts.job_status import write


def main():
    job='idm-ssl-upload-20260927-01'
    write(job,owner='idm-owner',host='mac',stage='running',evidence=str(ROOT/'upload.log'))
    import modal
    client=connect()
    volume=modal.Volume.from_name(INPUT_VOLUME,create_if_missing=True)
    volume.hydrate(client=client)
    rows=[]
    for directory in ('code','packet','assets'):
        for p in sorted((ROOT/directory).rglob('*')):
            if p.is_file(): rows.append({'source':str(p),'path':p.relative_to(ROOT).as_posix(),
                                         'bytes':p.stat().st_size,'sha256':digest(p)})
    run={'scope':'EXPLORATORY','packet_sha256':digest(ROOT/'packet/packet.json'),
         'code_commit':'c2bef3e','cap_usd':2,'ssl_allocation_usd':12,'combined_idm_cap_usd':25}
    atomic(ROOT/'run-manifest.json',run)
    p=ROOT/'run-manifest.json'
    rows.append({'source':str(p),'path':p.name,'bytes':p.stat().st_size,'sha256':digest(p)})
    atomic(ROOT/'upload-manifest.json',rows)
    with volume.batch_upload() as batch:
        for row in rows: batch.put_file(row['source'],'/'+row['path'])
        batch.put_file(ROOT/'upload-manifest.json','/upload-manifest.json')
    atomic(ROOT/'upload-receipt.json',{'volume_id':volume.object_id,'volume_name':INPUT_VOLUME,
        'manifest_sha256':digest(ROOT/'upload-manifest.json'),
        'run_manifest_sha256':digest(ROOT/'run-manifest.json'),
        'files':len(rows),'bytes':sum(r['bytes'] for r in rows),'completed_at':time.time()})
    (ROOT/'upload.exit').write_text('0\n')
    write(job,stage='done',progress='Small SSL packet uploaded')


if __name__=='__main__':
    try: main()
    except BaseException:
        write('idm-ssl-upload-20260927-01',stage='failed',progress='See upload.log')
        (ROOT/'upload.exit').write_text('1\n')
        raise

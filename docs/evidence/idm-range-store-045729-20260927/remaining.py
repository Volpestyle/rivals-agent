"""Continue the two authorized stores serially after owner's first-store inspection."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE/'code'))
from scripts.job_status import write

JOB = 'idm-range-stores-remaining-20260927'
IDS = ['20260926T035932-508Z-63684-14', '20260925T203745-207Z-49728-2']

def main():
    assert (BASE/'20260926T045729-166Z-79780-1.exit').read_text().strip() == '0'
    inspection = json.loads((BASE/'first-inspection.json').read_text())
    assert inspection['continue_remaining'] is True
    write(JOB, owner='idm-owner', stage='running', host='mac', evidence=str(BASE/'remaining-result.json'),
          progress={'n':0,'total':2})
    results=[]
    for sid in IDS:
        with (BASE/(sid+'.log')).open('xb') as log:
            proc = subprocess.Popen(['/bin/zsh',str(BASE/'run-one.zsh'),sid],stdout=log,
                                    stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,start_new_session=True)
            try:
                while proc.poll() is None:
                    write(JOB, progress=f'{len(results)}/2 complete; decoding {sid}')
                    time.sleep(15)
            finally:
                if proc.poll() is None:
                    os.killpg(proc.pid,signal.SIGTERM)
                    try:proc.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        os.killpg(proc.pid,signal.SIGKILL);proc.wait()
            assert proc.returncode == 0, f'{sid} failed; no retry or next source'
        results.append(json.loads((BASE/(sid+'.result.json')).read_text()))
    (BASE/'remaining-result.json').write_text(json.dumps(results,indent=2)+'\n')
    write(JOB,stage='done',progress='Two stores and payload hashes complete; owner inspection/release pending')

if __name__ == '__main__':
    try:
        main()
    except BaseException:
        write(JOB,stage='failed')
        (BASE/'remaining.exit').write_text('1\n')
        raise
    (BASE/'remaining.exit').write_text('0\n')

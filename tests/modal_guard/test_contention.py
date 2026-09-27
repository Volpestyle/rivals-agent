"""Native SQLite concurrency and deadline regressions; no provider calls."""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import threading
import time
from types import SimpleNamespace

import pytest

from cloud.modal_guard.common import elapsed_time
from cloud.modal_guard.ledger import Ledger
from cloud.modal_guard import lifecycle
from conftest import billing, snapshot, spec


def test_wal_reads_do_not_rewrite_or_wait_for_writer(ledger, clock):
    row = ledger.reserve(spec(), snapshot(clock))
    db = sqlite3.connect(ledger.path, timeout=1)
    assert db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    db.execute("BEGIN IMMEDIATE")
    before = db.execute("SELECT value FROM state").fetchone()[0]
    try:
        started = elapsed_time()
        assert ledger.get(row["attempt_id"]) == row
        ledger.funded(row["attempt_id"], monotonic=clock.monotonic)
        ledger.totals()
        ledger.check_absent_names(snapshot(clock))
        assert elapsed_time() - started < .5
        assert db.execute("SELECT value FROM state").fetchone()[0] == before
    finally:
        db.rollback()
        db.close()


def test_default_busy_timeout_and_deadline_cap(ledger):
    with ledger.connect() as db:
        assert db.execute("PRAGMA busy_timeout").fetchone()[0] == 30000
    with ledger.bounded(ledger.monotonic() + .1):
        with ledger.connect() as db:
            assert 0 <= db.execute("PRAGMA busy_timeout").fetchone()[0] <= 100
    with ledger.connect() as db:
        assert db.execute("PRAGMA busy_timeout").fetchone()[0] == 30000


def test_legacy_delete_journal_migrates_without_reinitializing(ledger, clock):
    row = ledger.reserve(spec(), snapshot(clock))
    db = sqlite3.connect(ledger.path)
    db.execute("PRAGMA journal_mode=DELETE")
    before = db.execute("SELECT value FROM state").fetchone()[0]
    db.close()
    assert ledger.get(row["attempt_id"]) == row
    db = sqlite3.connect(ledger.path)
    assert db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert db.execute("SELECT value FROM state").fetchone()[0] == before
    db.close()


def test_write_contention_cannot_delay_funded_stop(tmp_path, monkeypatch):
    start = elapsed_time()
    clock = SimpleNamespace(wall=lambda:1790542000 + elapsed_time()-start, monotonic=elapsed_time)
    ledger = Ledger.initialize(tmp_path/'clock.db',billing(clock),wall=clock.wall,monotonic=elapsed_time)
    row = ledger.reserve(spec(),snapshot(clock))
    ledger.rpc(row['attempt_id'],'CREATING')
    ledger.rpc(row['attempt_id'],'RUNNING',app_id='ap-own')
    with ledger.transaction() as s:
        r=s['attempts'][row['attempt_id']]
        r['started_monotonic']=elapsed_time()-(r['hold']['total_seconds']-r['hold']['cleanup_seconds'])+.35
    row=ledger.get(row['attempt_id'])
    locked=threading.Event()
    def writer():
        db=sqlite3.connect(ledger.path)
        db.execute('BEGIN IMMEDIATE');locked.set();time.sleep(1.5);db.rollback();db.close()
    writer_thread=threading.Thread(target=writer);writer_thread.start();assert locked.wait(1)
    stops=[]
    class Provider:
        def stop(self,app_id,timeout):stops.append(elapsed_time())
        def snapshot(self,timeout):
            value = snapshot(clock,[{'app_id':'ap-own','description':row['app_name'],'state':'stopped','tasks':0}])
            # Real clocks advance while the fixture builds its raw evidence.
            value['checked_monotonic'] = elapsed_time()
            return value
    class Ready:
        def poll(self):return billing(clock),None
    monkeypatch.setattr(lifecycle,'alive',lambda _:True)
    called=elapsed_time()
    try:
        proof=lifecycle.watch(ledger,row['attempt_id'],Provider(),1,sleep=lambda _:None,
                              wall=clock.wall,monotonic=elapsed_time,refresh_factory=lambda *a:Ready(),initial_row=row)
        assert stops and stops[0]-called < .8
        assert proof['kind']=='TERMINAL'
    finally:writer_thread.join(3)


@pytest.mark.skipif(sys.platform=='win32',reason='native shared boot identity and POSIX host regression runs on Mac')
def test_six_processes_contend_without_cascade(tmp_path, clock):
    from conftest import billing as bill
    sample = bill(clock)
    Ledger.initialize(tmp_path/'shared.db',sample,wall=clock.wall)
    (tmp_path/'billing.json').write_text(json.dumps(sample), encoding='utf-8')
    script=tmp_path/'worker.py'
    script.write_text("""
import json,sys,time
from pathlib import Path
from types import SimpleNamespace
from cloud.modal_guard.common import elapsed_time
from cloud.modal_guard.ledger import Ledger
from conftest import billing,snapshot,spec
root,slot=Path(sys.argv[1]),sys.argv[2]
clock=SimpleNamespace(wall=lambda:1790542000.0,monotonic=elapsed_time)
ledger=Ledger(root/'shared.db',wall=clock.wall)
sample=json.loads((root/'billing.json').read_bytes())
# Force concurrent reserve writes to queue behind an existing transaction.
(root/('ready-'+slot)).touch()
while not (root/'go').exists():time.sleep(.01)
row=ledger.reserve(spec('arm-'+slot),snapshot(clock))
for i in range(40):
 ledger.get(row['attempt_id']);ledger.funded(row['attempt_id']);ledger.totals()
 if i%4==0:ledger.refresh(sample)
print(json.dumps({'state':ledger.get(row['attempt_id'])['state']}))
""",encoding='utf-8')
    env=dict(os.environ,PYTHONPATH=os.pathsep.join([str(Path.cwd()),str(Path(__file__).parent.resolve())]))
    children=[subprocess.Popen([sys.executable,str(script),str(tmp_path),str(i)],env=env,
                               stdout=subprocess.PIPE,stderr=subprocess.PIPE) for i in range(6)]
    until=elapsed_time()+5
    while len(list(tmp_path.glob('ready-*')))<6 and elapsed_time()<until:time.sleep(.01)
    assert len(list(tmp_path.glob('ready-*')))==6
    db=sqlite3.connect(tmp_path/'shared.db');db.execute('BEGIN IMMEDIATE')
    (tmp_path/'go').touch();time.sleep(.3);db.rollback();db.close()
    results=[p.communicate(timeout=15) for p in children]
    assert all(p.returncode==0 for p in children),results
    db=sqlite3.connect(tmp_path/'shared.db')
    state=json.loads(db.execute('SELECT value FROM state').fetchone()[0]);db.close()
    assert len(state['attempts'])==6
    assert all(r['state']=='RESERVED' and r['rpc_count']==0 for r in state['attempts'].values())
    assert sum(e['event']=='BILLING' for e in state['events'])==60


@pytest.mark.parametrize("blocked", [False, True])
def test_watchdog_ready_only_after_initial_row_and_funding(tmp_path, monkeypatch, blocked):
    from contextlib import nullcontext
    from cloud.modal_guard import __main__ as cli
    events = []
    row = {"attempt_id": "arm"}
    class Journal:
        def get(self, attempt):
            events.append("get")
            if blocked:
                raise sqlite3.OperationalError("database is locked after timeout")
            return row
        def funded(self, attempt): events.append("funded")
    monkeypatch.setattr(cli, "Ledger", lambda *a: Journal())
    monkeypatch.setattr(cli, "Provider", lambda: SimpleNamespace(identity=lambda: events.append("identity")))
    monkeypatch.setattr(cli, "caffeinated", nullcontext)
    monkeypatch.setattr(cli, "atomic", lambda *a, **kw: events.append("ready"))
    monkeypatch.setattr(cli, "watch", lambda *a, **kw: events.append(("watch", kw["initial_row"])))
    monkeypatch.setattr(sys, "argv", ["guard", "watch", str(tmp_path/"ledger.db"), "arm", "1"])
    if blocked:
        with pytest.raises(sqlite3.OperationalError): cli.main()
        assert events == ["identity", "get"]
    else:
        assert cli.main() == 0
        assert events == ["identity", "get", "funded", "ready", ("watch", row)]

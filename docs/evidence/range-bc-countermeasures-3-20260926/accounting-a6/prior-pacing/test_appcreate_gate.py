import asyncio
import json
import pathlib
import tempfile
import types
import unittest
from unittest.mock import patch
import appcreate_gate as g


class Exhausted(Exception):
    pass


class Clock:
    def __init__(self):
        self.m = 1000.
        self.w = 2000.
    async def sleep(self, n):
        self.m += n
        self.w += n
        await asyncio.sleep(0)
    def advance(self, n):
        self.m += n
        self.w += n


class GateTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.clock = Clock()
        self.calls = []
        self.funded_count = 0
    def tearDown(self):
        self.tmp.cleanup()
    def local(self, key="A-0"):
        d = self.root / key
        d.mkdir()
        inv = {"identity": g.IDENTITY, "attempt_id": "r3p1-" + key + "-02",
               "app_name": "test-" + key, "apps": [], "creation_finished": False,
               "reservation": {"path": "/dummy/" + key, "sha256": "a"*64},
               "bounds": {"hold": {"startup_seconds": 300},
                          "started_monotonic": 1000., "started_at_unix": 2000.,
                          "stop_monotonic": 7000., "stop_at_unix": 8000.}}
        g.atomic(d/"inventory.json", inv)
        return d
    def funded(self):
        self.funded_count += 1
    def gate(self, fn, local=None, **kwargs):
        local = local or self.local()
        return g.AppCreateGate(fn, local, kwargs.pop("funded", self.funded),
             exhausted=Exhausted, monotonic=lambda:self.clock.m, wall=lambda:self.clock.w,
             sleep=self.clock.sleep, uniform=lambda a,b:b, **kwargs)
    def request(self, key="A-0"):
        return types.SimpleNamespace(description="test-"+key)
    def rpc(self, outcomes):
        outcomes = iter(outcomes)
        async def fn(req, **kw):
            self.calls.append((self.clock.m, kw))
            value = next(outcomes)
            if isinstance(value, BaseException):
                raise value
            return types.SimpleNamespace(app_id=value)
        return fn
    async def test_success_journals_app_before_return(self):
        gate=self.gate(self.rpc(["ap-one"]))
        answer=await gate(self.request())
        self.assertEqual(answer.app_id,"ap-one")
        self.assertEqual(g.read(gate.local/"inventory.json")["apps"],["ap-one"])
        self.assertEqual(g.read(gate.local/"appcreate.json")["status"],"CREATED")
        self.assertEqual(len(list(gate.events.iterdir())),2)
    async def test_explicit_rejections_retry_one_logical_request(self):
        gate=self.gate(self.rpc([Exhausted("busy"),Exhausted("busy"),"ap-one"]))
        await gate(self.request())
        self.assertEqual(len(self.calls),3)
        self.assertTrue(all(c[1]["retry"] is None for c in self.calls))
        keys=[dict(c[1]["metadata"])["x-idempotency-key"] for c in self.calls]
        self.assertEqual(len(set(keys)),1)
        self.assertTrue(all(b[0]-a[0]>=15 for a,b in zip(self.calls,self.calls[1:])))
    async def test_no_second_call_after_created(self):
        gate=self.gate(self.rpc(["ap-one","ap-two"]))
        await gate(self.request())
        with self.assertRaises(g.CreationStopped):await gate(self.request())
        self.assertEqual(len(self.calls),1)
    async def test_unknown_timeout_never_retries(self):
        gate=self.gate(self.rpc([TimeoutError("lost"),"ap-two"]))
        with self.assertRaises(TimeoutError):await gate(self.request())
        self.assertEqual(len(self.calls),1)
        self.assertEqual(g.read(gate.state)["outcome"],"UNKNOWN")
    async def test_unknown_blocks_other_task(self):
        gate=self.gate(self.rpc([ConnectionError("lost")]))
        with self.assertRaises(ConnectionError):await gate(self.request())
        other=self.gate(self.rpc(["ap-two"]),self.local("A-1"))
        with self.assertRaisesRegex(g.CreationStopped,"unknown"):await other(self.request("A-1"))
        self.assertEqual(len(self.calls),1)
    async def test_text_match_is_not_typed_rejection(self):
        gate=self.gate(self.rpc([ValueError("RESOURCE_EXHAUSTED")]))
        with self.assertRaises(ValueError):await gate(self.request())
        self.assertEqual(g.read(gate.state)["outcome"],"UNKNOWN")
    async def test_exhausted_until_startup_deadline(self):
        async def reject(req,**kw):
            self.calls.append((self.clock.m,kw))
            raise Exhausted("busy")
        gate=self.gate(reject)
        with self.assertRaisesRegex(g.CreationStopped,"startup budget"):await gate(self.request())
        self.assertLessEqual(self.clock.m,1300.000001)
        self.assertEqual(g.read(gate.local/"appcreate.json")["last_rpc_outcome"],"REJECTED_RESOURCE_EXHAUSTED")
        self.assertFalse(g.read(gate.local/"inventory.json")["creation_finished"])
    async def test_deadline_before_request_no_rpc(self):
        self.clock.advance(300)
        gate=self.gate(self.rpc(["ap-one"]))
        with self.assertRaises(g.CreationStopped):await gate(self.request())
        self.assertFalse(self.calls)
        self.assertEqual(g.read(gate.local/"appcreate.json")["last_rpc_outcome"],"NOT_SUBMITTED")
    async def test_deadline_during_queue_no_rpc(self):
        gate=self.gate(self.rpc(["ap-one"]))
        import fcntl
        with gate.lock.open("a") as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            with self.assertRaises(g.CreationStopped):await gate(self.request())
        self.assertFalse(self.calls)
    async def test_wall_jump_stops_even_with_monotonic_time_left(self):
        gate=self.gate(self.rpc(["ap-one"]))
        self.clock.w+=301
        with self.assertRaises(g.CreationStopped):await gate(self.request())
        self.assertFalse(self.calls)
    async def test_guard_failure_stops_queued_work(self):
        def failed():raise RuntimeError("supervisor died")
        gate=self.gate(self.rpc(["ap-one"]),funded=failed)
        with self.assertRaisesRegex(RuntimeError,"supervisor"):await gate(self.request())
        self.assertFalse(self.calls)
    async def test_success_after_deadline_keeps_app_for_cleanup(self):
        async def late(req,**kw):
            self.clock.advance(301)
            return types.SimpleNamespace(app_id="ap-late")
        gate=self.gate(late)
        with self.assertRaises(g.CreationStopped):await gate(self.request())
        self.assertEqual(g.read(gate.local/"inventory.json")["apps"],["ap-late"])
        self.assertEqual(g.read(gate.local/"appcreate.json")["last_rpc_outcome"],"CREATED")
    async def test_simultaneous_tasks_serialize_and_space(self):
        active=0;peak=0;starts=[]
        async def rpc(req,**kw):
            nonlocal active,peak
            active+=1;peak=max(peak,active);starts.append(self.clock.m)
            await asyncio.sleep(0)
            active-=1
            return types.SimpleNamespace(app_id="ap-"+req.description)
        a=self.gate(rpc);b=self.gate(rpc,self.local("A-1"))
        await asyncio.gather(a(self.request()),b(self.request("A-1")))
        self.assertEqual(peak,1)
        self.assertGreaterEqual(starts[1]-starts[0],15)
    async def test_cancelled_rpc_is_unknown(self):
        gate=self.gate(self.rpc([asyncio.CancelledError()]))
        with self.assertRaises(asyncio.CancelledError):await gate(self.request())
        self.assertEqual(g.read(gate.state)["outcome"],"UNKNOWN")
    async def test_prior_inflight_not_retried(self):
        gate=self.gate(self.rpc(["ap-one"]))
        g.atomic(gate.state,{"identity":g.IDENTITY,"outcome":"IN_FLIGHT"})
        with self.assertRaises(g.CreationStopped):await gate(self.request())
        self.assertFalse(self.calls)
    async def test_wrong_name_refused(self):
        gate=self.gate(self.rpc(["ap-one"]))
        with self.assertRaises(g.CreationStopped):await gate(self.request("A-1"))
        self.assertFalse(self.calls)
    async def test_existing_app_refused(self):
        local=self.local()
        inv=g.read(local/"inventory.json");inv["apps"]=["ap-existing"];g.atomic(local/"inventory.json",inv)
        gate=self.gate(self.rpc(["ap-new"]),local)
        with self.assertRaises(g.CreationStopped):await gate(self.request())
        self.assertFalse(self.calls)
    async def test_wrong_identity_refused(self):
        local=self.local()
        inv=g.read(local/"inventory.json");inv["identity"]={};g.atomic(local/"inventory.json",inv)
        with self.assertRaises(g.CreationStopped):self.gate(self.rpc(["ap-new"]),local)
    async def test_startup_budget_cannot_change(self):
        policy=dict(g.POLICY,startup_seconds=301)
        with self.assertRaises(g.CreationStopped):self.gate(self.rpc(["ap-new"]),policy=policy)
    async def test_fresh_journal_required(self):
        local=self.local();self.gate(self.rpc(["ap-new"]),local)
        with self.assertRaises(FileExistsError):self.gate(self.rpc(["ap-new"]),local)
    async def test_invalid_jitter_fails_closed(self):
        gate=self.gate(self.rpc([Exhausted("busy")]))
        gate.uniform=lambda a,b:float("nan")
        with self.assertRaises(g.CreationStopped):await gate(self.request())
        self.assertEqual(len(self.calls),1)
    async def test_native_sdk_stub_install_and_restore_no_network(self):
        import modal.client
        import modal.exception
        from modal._grpc_client import UnaryUnaryWrapper
        from modal._utils.async_utils import synchronizer
        from modal import Client
        public=Client("https://invalid.example",1,None)
        client=synchronizer._translate_in(public)
        method=types.SimpleNamespace(name="/modal.client.ModalClient/AppCreate")
        wrapper=UnaryUnaryWrapper(method,client,"https://invalid.example")
        seen=[]
        async def fake_direct(req,timeout=None,metadata=None):
            seen.append((timeout,metadata))
            return types.SimpleNamespace(app_id="ap-sdk")
        wrapper.direct=fake_direct
        client._stub=types.SimpleNamespace(AppCreate=wrapper)
        local=self.local()
        # Real clocks for the native integration gate.
        import time
        inv=g.read(local/"inventory.json")
        inv["bounds"].update(started_monotonic=time.monotonic(),started_at_unix=time.time(),
            stop_monotonic=time.monotonic()+1000,stop_at_unix=time.time()+1000)
        g.atomic(local/"inventory.json",inv)
        restore=g.install(public,local,lambda:None)
        installed=client.stub.AppCreate
        reply=await installed(self.request())
        self.assertEqual(reply.app_id,"ap-sdk")
        self.assertEqual(len(seen),1)
        restore()
        self.assertIs(client.stub.AppCreate,wrapper)
    async def test_app_setup_failure_cannot_repeat_appcreate(self):
        gate=self.gate(self.rpc(["ap-one","ap-two"]))
        async def setup():
            await gate(self.request())
            raise RuntimeError("publish failed")
        with self.assertRaises(RuntimeError):await setup()
        with self.assertRaises(g.CreationStopped):await setup()
        self.assertEqual(len(self.calls),1)
    async def test_rpc_deadline_bounds_hanging_transport(self):
        local=self.local()
        inv=g.read(local/"inventory.json")
        import time
        inv["bounds"].update(started_monotonic=time.monotonic(),started_at_unix=time.time(),
            stop_monotonic=time.monotonic()+1000,stop_at_unix=time.time()+1000)
        g.atomic(local/"inventory.json",inv)
        count=0
        async def hang(req,**kwargs):
            nonlocal count
            count+=1
            await asyncio.sleep(60)
        gate=g.AppCreateGate(hang,local,lambda:None,exhausted=Exhausted,
              policy=dict(g.POLICY,rpc_timeout_seconds=.02))
        with self.assertRaises(TimeoutError):await gate(self.request())
        self.assertEqual(count,1)
        self.assertEqual(g.read(gate.state)["outcome"],"UNKNOWN")
    async def test_dead_creator_inflight_state_blocks_new_process(self):
        import subprocess,sys
        lock=self.root/"appcreate-rate.lock"
        state=self.root/"appcreate-rate-state.json"
        code="import fcntl,json,sys; f=open(sys.argv[1],'a'); fcntl.flock(f,fcntl.LOCK_EX); json.dump({'identity':json.loads(sys.argv[3]),'outcome':'IN_FLIGHT'},open(sys.argv[2],'w'))"
        subprocess.run([sys.executable,"-B","-c",code,str(lock),str(state),json.dumps(g.IDENTITY)],check=True)
        gate=self.gate(self.rpc(["ap-new"]))
        with self.assertRaisesRegex(g.CreationStopped,"unknown"):await gate(self.request())
        self.assertFalse(self.calls)
    async def test_native_sdk_resource_exhausted_only_retries(self):
        from modal._grpc_client import UnaryUnaryWrapper
        from grpclib.exceptions import GRPCError
        from grpclib.const import Status
        import modal.exception
        method=types.SimpleNamespace(name="/modal.client.ModalClient/AppCreate")
        wrapper=UnaryUnaryWrapper(method,None,"https://invalid.example")
        count=0
        async def direct(req,timeout=None,metadata=None):
            nonlocal count
            count+=1
            if count==1:raise GRPCError(Status.RESOURCE_EXHAUSTED,"busy")
            return types.SimpleNamespace(app_id="ap-sdk")
        wrapper.direct=direct
        gate=self.gate(wrapper)
        gate.exhausted=modal.exception.ResourceExhaustedError
        self.assertEqual((await gate(self.request())).app_id,"ap-sdk")
        self.assertEqual(count,2)
    def test_draft_entrypoint_disabled(self):
        import subprocess,sys
        proc=subprocess.run([sys.executable,"-B",str(pathlib.Path(__file__).with_name("task_driver.py"))],
             capture_output=True,text=True)
        self.assertNotEqual(proc.returncode,0)
        self.assertIn("DRAFT AppCreate fix: launches disabled",proc.stderr)


if __name__=="__main__":unittest.main()

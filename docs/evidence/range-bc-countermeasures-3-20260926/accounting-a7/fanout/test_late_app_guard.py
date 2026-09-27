import asyncio
import copy
import hashlib
import json
import pathlib
import tempfile
import time
import types
import unittest
from unittest.mock import patch, AsyncMock
import late_app_guard as guard
import cm3_accounting as accounting
import appcreate_gate
from test_appcreate_gate import Clock, Exhausted


def fixture(root):
    def write(name, value):
        path=root/name;path.parent.mkdir(parents=True,exist_ok=True)
        raw=(json.dumps(value,sort_keys=True,indent=2)+"\n").encode()
        path.write_bytes(raw)
        return {"path":name,"sha256":hashlib.sha256(raw).hexdigest()}
    attempt="r3p1-H-0-01";name="rivals-cm3-historical-H-0";key="historical-key"
    res={"format":"cm3-task-reservation-v1","attempt_id":attempt,
         "campaign_id":"r3-20260926-l40s","concurrent_slots":1,
         "reserved_compute_seconds":1020,"reserved_usd":.732197,
         "bounds":{"started_at_unix":100,"rate_usd_second":.00071784,
                   "overhead_usd":0,"hold":{"startup_seconds":300}}}
    rr=write("reservations/"+attempt+".json",res)
    result={"format":"cm3-inputs-wrapper-result-v1","attempt_id":attempt,
         "status":"INCOMPLETE","creation_started":True,"owner_result":None,
         "teardown":{"identity":guard.IDENTITY,"status":"INCOMPLETE_CLEANUP",
                     "apps":[],"events":[],"checked_at_unix":110},
         "spend":{"seconds_through_cleanup":10,"estimated_conservative_usd":.0071784}}
    re=write("results/"+attempt+".json",result)
    owned={"format":"cm3-owned-inventory-v1","attempt_id":attempt,
           "identity":guard.IDENTITY,"app_name":name,"creation_started":True,
           "creation_finished":False,"apps":[],"calls":{},"reservation":rr}
    oi=write("owned_inventory/"+attempt+".json",owned)
    ev={"format":"cm3-appcreate-rejection-v2","attempt_id":attempt,
         "reservation_sha256":rr["sha256"],"result_sha256":re["sha256"],
         "owned_inventory_sha256":oi["sha256"],"identity":guard.IDENTITY,
         "app_name":name,"creation_started":True,"creation_finished":False,
         "creator_terminated":True,"rpc_method":"AppCreate","rpc_status":None,
         "rpc_outcome":"UNKNOWN","rejected_at_unix":None,
         "creator_terminated_at_unix":111,"request_started_at_unix":110,
         "request_clock_source":"failed_cleanup_upper_bound","startup_seconds":300,
         "logical_request_id":key,"capture_started_at_unix":412,
         "capture_finished_at_unix":474,"inventory_snapshots":[]}
    for t in [413,473]:
        snapshot={"status":"READ_OK","complete":True,"identity":guard.IDENTITY,
                  "checked_at_unix":t,"apps":[],"owned_containers":[],"raw_outputs":{}}
        for field,value in [("identity",guard.IDENTITY),("apps",[]),("containers",[])]:
            raw=json.dumps(value)
            snapshot["raw_outputs"][field]={"stdout":raw,"sha256":hashlib.sha256(raw.encode()).hexdigest(),
                  "returncode":0,"elapsed_seconds":.1}
        ev["inventory_snapshots"].append(snapshot)
    er=write("appcreate_rejection/"+attempt+".json",ev)
    row={"attempt_id":attempt,"reservation":rr,"result":re,"owned_inventory":oi,"appcreate_rejection":er}
    inv=write("inventory.json",{"format":"cm3-reservation-inventory-v2",
        "campaign_id":"r3-20260926-l40s","reservations":{attempt:rr}})
    ref=write("ledger.json",{"format":"cm3-measured-accounting-v2","approved_by":"herdr-lead",
        "campaign_id":"r3-20260926-l40s","basis_seconds":12159,"basis_usd":6.18374656,
        "inventory":inv,"settlements":[row]})
    return {"campaign_ledger":{"local_path":str(root/"ledger.json"),"sha256":ref["sha256"]},
            "spent_before_usd":6.91594356,"spent_before_compute_seconds":13179,
            "campaign_id":"r3-20260926-l40s","run_id":"phase1-02"},name,key


class WatchTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name)
        self.plan,self.name,self.key=fixture(self.root/"bundle")
        self.apps=[];self.reads=0
    def tearDown(self):self.tmp.cleanup()
    async def snapshot(self,client=None):
        self.reads+=1
        return {"status":"READ_OK","complete":True,"identity":guard.IDENTITY,
                "apps":copy.deepcopy(self.apps),"checked_at_unix":time.time()}
    async def admit(self):
        return await guard.admit_async(self.plan,self.root/"evidence","test",inspector=self.snapshot)
    async def test_real_a6_canonical_ledger_emits_watch(self):
        watch=guard.watches(self.plan)
        self.assertEqual(watch[0]["app_name"],self.name)
        self.assertEqual(watch[0]["rpc_outcome"],"UNKNOWN")
        self.assertEqual(len(watch),1)
        await self.admit()
    async def test_late_running_app_mutation_refuses_second_admission(self):
        await self.admit()
        self.apps.append({"app_id":"ap-late","description":self.name,"state":"running"})
        with self.assertRaisesRegex(ValueError,"late app"):await self.admit()
        self.assertEqual(self.reads,2)
        reports=[json.loads(p.read_bytes()) for p in (self.root/"evidence").glob("*.json")]
        self.assertEqual(sorted(x["status"] for x in reports),["PASS","REFUSED"])
    async def test_late_stopped_app_mutation_also_refuses(self):
        await self.admit()
        self.apps.append({"app_id":"ap-stopped","description":self.name,"state":"stopped"})
        with self.assertRaisesRegex(ValueError,"late app"):await self.admit()
    async def test_key_match_with_changed_name_refuses(self):
        self.apps=[{"app_id":"ap-other","description":"other","idempotency_key":self.key}]
        with self.assertRaisesRegex(ValueError,"late app"):await self.admit()
    async def test_logical_key_match_refuses(self):
        self.apps=[{"app_id":"ap-other","description":"other","logical_request_id":self.key}]
        with self.assertRaisesRegex(ValueError,"late app"):await self.admit()
    async def test_unobservable_key_does_not_infer_match(self):
        self.apps=[{"app_id":"ap-other","description":"other"}]
        await self.admit()
    async def test_name_mandatory_even_null_key(self):
        watches=guard.watches(self.plan);watches[0]["logical_request_id"]=None
        snap=await self.snapshot();snap["apps"]=[{"app_id":"ap-x","description":self.name}]
        with self.assertRaisesRegex(ValueError,"late app"):guard.check_inventory(watches,snap)
    async def test_malformed_inventory_refuses(self):
        for apps in ({},[{}],[{"app_id":"x","description":""}],
                     [{"app_id":"x","description":"ok"},{"app_id":"x","description":"ok2"}]):
            with self.subTest(apps=apps):
                self.apps=apps
                with self.assertRaises(ValueError):await self.admit()
    async def test_partial_or_wrong_identity_refuses(self):
        for mutation in [{"complete":False},{"identity":{}},{"status":"TIMED_OUT"}]:
            snap=await self.snapshot();snap.update(mutation)
            with self.assertRaises(ValueError):guard.check_inventory(guard.watches(self.plan),snap)
    async def test_inventory_timeout_refuses(self):
        async def broken(client):raise TimeoutError("provider unavailable")
        with self.assertRaises(TimeoutError):
            await guard.admit_async(self.plan,self.root/"evidence","test",inspector=broken)
    async def test_changed_ledger_digest_refuses_before_provider_read(self):
        path=pathlib.Path(self.plan["campaign_ledger"]["local_path"])
        path.write_bytes(path.read_bytes()+b" ")
        with self.assertRaisesRegex(ValueError,"digest"):await self.admit()
        self.assertEqual(self.reads,0)
    async def test_changed_reconciliation_refuses(self):
        path=next((self.root/"bundle/appcreate_rejection").glob("*.json"))
        path.write_bytes(path.read_bytes()+b" ")
        with self.assertRaisesRegex(ValueError,"digest"):await self.admit()
    async def test_helper_pin_change_refuses(self):
        with patch.object(guard,"HELPER_SHA256","0"*64):
            with self.assertRaisesRegex(ValueError,"helper pin"):await self.admit()
    async def test_before_reservation_rejects_without_creating_new_holds(self):
        import lifecycle
        self.apps=[{"app_id":"ap-late","description":self.name}]
        with patch.object(lifecycle,"ledger",return_value={}),patch.object(guard,"inspect_workspace",self.snapshot):
            with self.assertRaisesRegex(ValueError,"late app"):
                await asyncio.to_thread(lifecycle.reserve,self.plan,self.root/"campaigns",guard.IDENTITY)
        self.assertFalse(list((self.root/"campaigns").rglob("reservations/*.json")))
        self.assertFalse((self.root/"campaigns/r3-20260926-l40s/phase1-02").exists())
    async def test_retry_rechecks_live_inventory_and_never_creates_second_app(self):
        local=self.root/"phase/A-0";local.mkdir(parents=True)
        clock=Clock()
        appcreate_gate.atomic(local/"inventory.json",{"identity":guard.IDENTITY,
            "attempt_id":"r3p1-A-0-02","app_name":"new-A-0","apps":[],"creation_finished":False,
            "reservation":{"path":"/dummy","sha256":"a"*64},
            "bounds":{"hold":{"startup_seconds":300},"started_monotonic":1000.,
            "started_at_unix":2000.,"stop_monotonic":8000.,"stop_at_unix":9000.}})
        calls=[]
        async def rpc(req,**kwargs):
            calls.append(req.description)
            self.apps=[{"app_id":"ap-late","description":self.name,"state":"stopped"}]
            raise Exhausted("rate limited")
        gate=appcreate_gate.AppCreateGate(rpc,local,lambda:None,exhausted=Exhausted,
              monotonic=lambda:clock.m,wall=lambda:clock.w,sleep=clock.sleep,
              uniform=lambda a,b:b,before_rpc=self.admit)
        with self.assertRaisesRegex(ValueError,"late app"):
            await gate(types.SimpleNamespace(description="new-A-0"))
        self.assertEqual(calls,["new-A-0"])
        self.assertEqual(self.reads,2)
    async def test_native_sdk_scans_all_environments_without_network(self):
        import modal.client,modal.config
        from modal_proto import api_pb2
        class Stub:
            def __init__(self):self.env_calls=0;self.app_envs=[]
            async def TokenInfoGet(self,request,**kwargs):
                return types.SimpleNamespace(workspace_name="volpestyle",workspace_id=guard.IDENTITY["workspace_id"])
            async def EnvironmentList(self,request,**kwargs):
                self.env_calls+=1
                return api_pb2.EnvironmentListResponse(items=[
                    api_pb2.EnvironmentListItem(name="main"),api_pb2.EnvironmentListItem(name="other")])
            async def AppList(self,request,**kwargs):
                self.app_envs.append(request.environment_name)
                result=api_pb2.AppListResponse()
                if request.environment_name=="other":
                    result.apps.add(app_id="ap-late",description=self_outer.name)
                return result
        self_outer=self;stub=Stub()
        client=modal.client._Client("https://invalid.example",1,None);client._stub=stub
        with patch.object(modal.config,"_profile","rivals"):
            snap=await guard.inspect_workspace(client)
        self.assertEqual(stub.app_envs,["main","other"])
        with self.assertRaisesRegex(ValueError,"late app"):
            guard.check_inventory(guard.watches(self.plan),snap)
        self.assertEqual(snap["key_fields_observable"],[])
    async def test_native_sdk_partial_environment_read_refuses(self):
        import modal.client,modal.config
        from modal_proto import api_pb2
        class Stub:
            async def TokenInfoGet(self,r,**kw):
                return types.SimpleNamespace(workspace_name="volpestyle",workspace_id=guard.IDENTITY["workspace_id"])
            async def EnvironmentList(self,r,**kw):
                return api_pb2.EnvironmentListResponse(items=[api_pb2.EnvironmentListItem(name="main")])
            async def AppList(self,r,**kw):raise TimeoutError("partial")
        c=modal.client._Client("https://invalid.example",1,None);c._stub=Stub()
        with patch.object(modal.config,"_profile","rivals"):
            with self.assertRaises(TimeoutError):await guard.inspect_workspace(c)


if __name__=="__main__":unittest.main()

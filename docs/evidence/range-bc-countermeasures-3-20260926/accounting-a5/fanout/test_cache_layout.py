"""F5 regressions against the pinned owner's source_identity function.
All files, cache adapters and session tables are synthetic. No corpus/torch import.
"""
import ast,copy,json,pathlib,tempfile,types,unittest
import collector,input_closure,safety
from test_fixes import Fixture,encoded,h
import test_fixes as fixtures
ROOT=pathlib.Path(__file__).parent

class SourceCacheLayoutTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=pathlib.Path(self.temp.name);self.fixture=Fixture(self.root)
        self.context=safety.document(self.fixture.p["approved_context"])
        self.manifest=safety.document(self.fixture.p["input_manifest"])

    def test_real_source_identity_cache_json_layout_all_seven(self):
        # Execute only the exact reviewed function AST, with synthetic cache/session
        # dependencies. No import or execution of the owner module's torch code.
        path=ROOT/"prior-test-reference/cm3_features.owner.py"
        expected=json.loads((ROOT/"fixes2-files.json").read_bytes())["files"]["policy/range_bc/cm3_features.py"]
        self.assertEqual(safety.digest(path),expected)
        tree=ast.parse(path.read_text())
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=="source_identity")
        module=ast.Module(body=[fn],type_ignores=[])
        shapes={"global":(144,256,3),"crop":(128,128,3),"hud":(80,200,3)}
        table_hash=h(b"synthetic")
        namespace={"Path":pathlib.Path,"require":safety.require,
            "steps":types.SimpleNamespace(sha256=safety.digest),
            "TRAIN_TABLES":{sid:table_hash for sid in input_closure.TRAIN},
            "DEV_SESSIONS":{sid:table_hash for sid in input_closure.DEV}}
        def open_cache(directory,session,verify_hashes):
            self.assertTrue(verify_hashes)
            d=pathlib.Path(directory);m=json.loads((d/"cache.json").read_bytes())
            for name in shapes:self.assertEqual(safety.digest(d/(name+".u8")),m[name+"_sha256"])
            return object(),object(),object(),m
        namespace["cache"]=types.SimpleNamespace(
            GRAPH="synthetic RGB graph",GLOBAL=shapes["global"],CROP=shapes["crop"],HUD=shapes["hud"],
            plan=lambda _: ([(0,0)],[(0,(1,60))],[0]),open_cache=open_cache)
        exec(compile(module,str(path),"exec"),namespace)
        for sid,source in self.context["sources"].items():
            d=self.root/"cache-fixture"/sid;d.mkdir(parents=True)
            m={"session_id":sid,"graph":"synthetic RGB graph","row_frame":[0],"frames":1,"videos":[]}
            for name,shape in shapes.items():
                raw=("synthetic-"+sid+"-"+name).encode();(d/(name+".u8")).write_bytes(raw)
                m[name+"_shape"]=list(shape);m[name+"_sha256"]=h(raw)
            (d/"cache.json").write_bytes(encoded(m))
            sha=safety.digest(d/"cache.json")
            session=types.SimpleNamespace(session_id=sid,sha256=table_hash,split="train",header={"media_sha256":h(b"synthetic-media")})
            _,identity=namespace["source_identity"](session,d,manifest_sha256=sha,role=source["role"])
            self.assertEqual(identity["cache_manifest_sha256"],sha)
            self.assertFalse((d/"manifest.json").exists())
            source["cache_manifest_sha256"]=sha
            for row in self.manifest["files"]:
                if row["path"].startswith("caches/"+sid+"/"):
                    raw=(d/pathlib.PurePosixPath(row["path"]).name).read_bytes()
                    row.update(sha256=h(raw),bytes=len(raw))
        self.manifest["context_sha256"]=safety.canonical(self.context)
        input_closure.bind_context(self.manifest,self.context)
        self.assertEqual(sum(r["path"].endswith("/cache.json") for r in self.manifest["files"]),7)

    def test_manifest_json_only_rename_reproduction_refused(self):
        input_closure.bind_context(self.manifest,self.context)
        for row in self.manifest["files"]:
            if row["path"].endswith("/cache.json"):row["path"]=row["path"].removesuffix("cache.json")+"manifest.json"
        with self.assertRaisesRegex(ValueError,"cache closure incomplete"):
            input_closure.bind_context(self.manifest,self.context)

    def test_absent_cache_json_refused_for_each_session(self):
        for sid in input_closure.TRAIN+input_closure.DEV:
            with self.subTest(session=sid):
                m=copy.deepcopy(self.manifest)
                m["files"]=[r for r in m["files"] if r["path"]!="caches/"+sid+"/cache.json"]
                with self.assertRaisesRegex(ValueError,"cache closure incomplete"):input_closure.bind_context(m,self.context)

    def test_changed_cache_json_pin_refused_for_each_session(self):
        for sid in input_closure.TRAIN+input_closure.DEV:
            with self.subTest(session=sid):
                m=copy.deepcopy(self.manifest)
                next(r for r in m["files"] if r["path"]=="caches/"+sid+"/cache.json")["sha256"]="0"*64
                with self.assertRaisesRegex(ValueError,"cache manifest changed"):input_closure.bind_context(m,self.context)

class FeatureManifestTests(unittest.TestCase):
    def test_extracted_manifest_json_preserved_and_authenticated_separately(self):
        fixture=fixtures.CollectionTests("test_good_download_preserves_bytes_and_no_judge_without_owner_verify")
        fixture.setUp();self.addCleanup(fixture.doCleanups)
        sid=input_closure.TRAIN[0]
        m=safety.document(fixture.m["input_manifests"][0])
        source_pin=next(r["sha256"] for r in m["files"] if r["path"]=="caches/"+sid+"/cache.json")
        path="/outputs/extract/"+sid+"/manifest.json"
        raw=encoded({"format":"synthetic-extracted-feature","source":{"cache_manifest_sha256":source_pin},"dtype":"<f4","shape":[1,384]})
        fixture.data[path]=(raw,"json")
        ref={"path":path,"sha256":h(raw)}
        selected=fixture.m["selected"][0];result_path=selected["result_ref"]["path"]
        result=json.loads(fixture.data[result_path][0]);result["artifacts"]["feature_manifest"]=ref
        result_bytes=encoded(result);fixture.data[result_path]=(result_bytes,"json")
        selected["result_ref"]["sha256"]=h(result_bytes);fixture.refresh()
        dest=fixture.root/"with-feature"
        self.assertEqual(collector.collect(fixture.ref,dest,fixture.reader)["status"],"ARTIFACTS_VERIFIED")
        self.assertEqual((dest/"artifacts"/path.removeprefix("/")).read_bytes(),raw)
        # Renaming just the feature transfer entry does not satisfy its original ref.
        for row in fixture.m["files"]:
            if row["path"]==path:row["path"]=path.removesuffix("manifest.json")+"cache.json"
        fixture.data[path.removesuffix("manifest.json")+"cache.json"]=fixture.data[path]
        bad_ref=fixture.fixture.ref(fixture.m)
        with self.assertRaisesRegex(ValueError,"referenced artifact absent"):
            collector.collect(bad_ref,fixture.root/"renamed-feature",fixture.reader)

if __name__=="__main__":unittest.main(verbosity=2)

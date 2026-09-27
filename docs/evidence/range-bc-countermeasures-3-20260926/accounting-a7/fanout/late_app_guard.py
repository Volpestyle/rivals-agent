"""A6 admission watch: authenticate all prior absent settlements before new work."""
import asyncio
import hashlib
import json
import math
import pathlib
import time
import uuid
import cm3_accounting as accounting

IDENTITY = accounting.IDENTITY
HELPER_SHA256 = "13c26df40e40f58eb4561b9e655eb71391e3aee4c05546f6e9d3ddbf7b0c7e4d"
ROOT = pathlib.Path(__file__).resolve().parent


def require(ok, message):
    if not ok:
        raise ValueError(message)


def document(ref):
    path = pathlib.Path(ref["path"])
    require(path.is_file() and not path.is_symlink(), "accounting document missing/symlink")
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == ref["sha256"], "accounting digest changed")
    return json.loads(raw)


def watches(plan):
    helper = pathlib.Path(accounting.__file__).resolve()
    require(helper == ROOT / "cm3_accounting.py" and
            hashlib.sha256(helper.read_bytes()).hexdigest() == HELPER_SHA256,
            "A6 helper pin mismatch")
    ref = {"path": plan["campaign_ledger"]["local_path"],
           "sha256": plan["campaign_ledger"]["sha256"]}
    require(document(ref)["format"] == "cm3-measured-accounting-v2", "canonical v2 required")
    totals = accounting.ledger(ref, document)
    require(totals["spent_seconds"] == plan["spent_before_compute_seconds"] and
            totals["spent_usd"] == plan["spent_before_usd"], "prior spend changed")
    result = []
    for settlement in totals["settlements"]:
        if "absent_app" not in settlement:
            continue
        watch = settlement["absent_app"]
        require(set(watch) == {"app_name", "logical_request_id", "identity", "rpc_outcome"},
                "unknown absent-app schema")
        require(watch["identity"] == IDENTITY and watch["rpc_outcome"] in ("REJECTED", "UNKNOWN"),
                "invalid absent-app identity/outcome")
        require(isinstance(watch["app_name"], str) and watch["app_name"], "empty watched name")
        require(watch["logical_request_id"] is None or
                isinstance(watch["logical_request_id"], str) and watch["logical_request_id"],
                "invalid watched key")
        result.append(dict(watch, attempt_id=settlement["attempt_id"]))
    require(len({w["app_name"] for w in result}) == len(result), "duplicate watched name")
    return result


def check_inventory(watchlist, snapshot):
    require(snapshot.get("status") == "READ_OK" and snapshot.get("complete") is True,
            "incomplete workspace inventory")
    require(snapshot.get("identity") == IDENTITY, "workspace identity changed")
    apps = snapshot.get("apps")
    require(isinstance(apps, list), "malformed app inventory")
    ids = set()
    for app in apps:
        require(isinstance(app, dict) and isinstance(app.get("app_id"), str) and app["app_id"]
                and isinstance(app.get("description"), str) and app["description"],
                "malformed app identity")
        require(app["app_id"] not in ids, "duplicate app ID")
        ids.add(app["app_id"])
        for watch in watchlist:
            match = app["description"] == watch["app_name"]
            key = watch["logical_request_id"]
            if key is not None:
                match = match or any(app.get(field) == key
                                    for field in ("logical_request_id", "idempotency_key"))
            # State is deliberately irrelevant: stopped apps also invalidate absence.
            require(not match, "late app for absent settlement " + watch["attempt_id"]
                    + ": " + app["app_id"])
    return len(watchlist)


async def inspect_workspace(client=None):
    """Read every visible environment. Current pinned AppList API is unpaginated."""
    import modal
    import modal.client
    import modal.config
    from modal._utils.async_utils import synchronizer
    from modal_proto import api_pb2
    from google.protobuf.empty_pb2 import Empty
    require(modal.__version__ == "1.5.5", "unreviewed inventory SDK")
    require(modal.config._profile == "rivals", "profile not selected")
    internal = synchronizer._translate_in(client) if client is not None else await modal.client._Client.from_env()
    require(set(api_pb2.AppListResponse.DESCRIPTOR.fields_by_name) == {"apps"} and
            set(api_pb2.EnvironmentListResponse.DESCRIPTOR.fields_by_name) == {"items"},
            "inventory pagination/schema changed")
    started = time.monotonic()
    queries = []
    async def rpc(name, request):
        remaining = 30 - (time.monotonic() - started)
        require(remaining > 0, "workspace inventory deadline")
        timeout = min(10, remaining)
        begin = time.monotonic()
        response = await asyncio.wait_for(getattr(internal.stub, name)(
            request, retry=None, timeout=timeout), timeout=timeout)
        queries.append({"method": name, "seconds": time.monotonic() - begin})
        return response
    async def identity():
        response = await rpc("TokenInfoGet", api_pb2.TokenInfoGetRequest())
        value = {"profile": "rivals", "workspace": response.workspace_name,
                 "workspace_id": response.workspace_id}
        require(value == IDENTITY, "authenticated identity mismatch")
        return value
    await identity()
    first = await rpc("EnvironmentList", Empty())
    envs = [item.name for item in first.items]
    require(0 < len(envs) <= 32 and all(envs) and len(envs) == len(set(envs)),
            "incomplete/invalid environment inventory")
    apps = []
    key_fields = []
    for environment in sorted(envs):
        response = await rpc("AppList", api_pb2.AppListRequest(environment_name=environment))
        for item in response.apps:
            row = {"app_id": item.app_id, "description": item.description,
                   "state": int(item.state), "environment": environment}
            for field in ("logical_request_id", "idempotency_key"):
                if field in item.DESCRIPTOR.fields_by_name:
                    row[field] = getattr(item, field)
                    key_fields.append(field)
            apps.append(row)
    last = await rpc("EnvironmentList", Empty())
    require(sorted(item.name for item in last.items) == sorted(envs),
            "environment inventory changed during read")
    actual = await identity()
    require(time.monotonic() - started <= 30, "workspace inventory deadline")
    return {"status": "READ_OK", "complete": True, "identity": actual,
            "apps": apps, "environments": sorted(envs), "queries": queries,
            "key_fields_observable": sorted(set(key_fields)),
            "checked_at_unix": time.time(),
            "scope": "all environments visible to authenticated workspace client",
            "api": "Modal1.5.5 AppList: running/deployed/recently stopped; no pagination fields"}


async def admit_async(plan, evidence_directory, purpose, client=None, *, inspector=None):
    watchlist = watches(plan)  # Never trust a caller's copied watch list.
    path = pathlib.Path(evidence_directory)
    path.mkdir(parents=True, exist_ok=True)
    evidence = path / (uuid.uuid4().hex + ".json")
    report = {"format": "cm3-a6-live-admission-watch-v1", "purpose": purpose,
              "ledger_sha256": plan["campaign_ledger"]["sha256"],
              "helper_sha256": HELPER_SHA256, "watches": watchlist,
              "started_at_unix": time.time(), "status": "REFUSED"}
    try:
        snapshot = await asyncio.wait_for(
            (inspector(client) if inspector is not None else inspect_workspace(client)),
            timeout=30)
        report["inventory"] = snapshot
        report["watched_attempts"] = check_inventory(watchlist, snapshot)
        report["status"] = "PASS"
    except BaseException as exc:
        report["reason"] = str(exc)
        raise
    finally:
        report["finished_at_unix"] = time.time()
        with evidence.open("x") as f:
            json.dump(report, f, indent=2, allow_nan=False)
    return report


def before_reservation(plan, campaign, identity):
    require(identity == IDENTITY, "reservation identity changed")
    from modal._utils.async_utils import synchronizer
    return synchronizer.create_blocking(admit_async)(
        plan, pathlib.Path(campaign) / "admission-watch", "before-reservation")

"""Send the same States to the local server and to real Jev, and compare what they choose.

Everything else a local server needs is already in agent/jev.py: `Endpoint` reads JEV_URL,
JEV_MODEL and JEV_KEY, so latency is measured with the stock benchmark and no code of ours:

    JEV_URL=http://192.168.4.126:8724/v1/systemone JEV_MODEL=local JEV_KEY=... \
        uv run python -m agent.jev -n 60 --timeout 0.3 --hz 5

Agreement is the one thing that benchmark cannot report, because it needs both endpoints on
one State. This does that, on agent.jev.bench_states, with agent.jev building and
interpreting every request:

    LOCALJEV_KEY="$(cat ~/.jev-local-key)" uv run python -m localjev.paired \
        --url http://192.168.4.126:8724/v1/systemone -n 80

Real Jev comes from Endpoint.from_env(), i.e. JEV_URL/JEV_MODEL/JEV_KEY in the environment
or .env. So do NOT export JEV_URL here: that would point both askers at the same server.
The local server's key is read from LOCALJEV_KEY, a separate name for exactly that reason.

Real Jev costs about $0.00002 per answered call, so -n 80 is about $0.002.
"""
import argparse
import json
import os
from collections import Counter

from agent import brain, jev as J
from agent.brain import Memory


def asker(url=None, model=None, key=None, timeout_s=5.0):
    """A blocking Jev against one endpoint. No url: real Jev, exactly as the agent runs it."""
    endpoint = J.Endpoint(url, model or "local", key) if url else J.Endpoint.from_env()
    return J.Jev(J.HttpTransport(endpoint=endpoint), timeout_s, endpoint.model)


def paired(n, url, key=None, timeout_s=5.0):
    local, real = asker(url, "local", key, timeout_s), asker(timeout_s=timeout_s)
    both = agree = 0
    differ, scr = Counter(), {"local": [0, 0], "jev": [0, 0]}  # [agreed, answered]
    for s in J.bench_states(n):
        got = {"local": local(s, Memory()), "jev": real(s, Memory())}
        src = {"local": local.stats.trace[-1][1], "jev": real.stats.trace[-1][1]}
        scripted = J.name_of(brain.decide(s, Memory()))
        for who in got:
            if src[who] == "jev":  # the model answered this State; "scripted" means it fell back
                scr[who][0] += J.name_of(got[who]) == scripted
                scr[who][1] += 1
        if src["local"] == src["jev"] == "jev":
            both += 1
            nl, nr = J.name_of(got["local"]), J.name_of(got["jev"])
            agree += nl == nr
            if nl != nr:
                differ[f"{nr}->{nl}"] += 1  # real Jev -> local
    return {
        "states": n,
        "endpoints": {"local": local.transport.endpoint.url, "jev": real.transport.endpoint.url},
        "answered": {who: scr[who][1] for who in scr},
        "answered_by_both": both,
        "agreement_local_vs_jev": _frac(agree, both),
        "disagreements_jev_to_local": dict(differ.most_common()),
        "agreement_with_scripted": {who: _frac(*scr[who]) for who in scr},
        "fallbacks": {"local": dict(local.stats.fallbacks), "jev": dict(real.stats.fallbacks)},
        "roundtrip_ms": {"local": J._spread(local.stats.latency_ms, 50, 95),
                         "jev": J._spread(real.stats.latency_ms, 50, 95)},
        "confidence_p50": {who: _p50(a.stats.confidence) for who, a in (("local", local), ("jev", real))},
        "cost_usd_jev": round(real.stats.cost, 6),
    }


def _frac(k, n):
    return round(k / n, 3) if n else None


def _p50(xs):
    return round(J.pct(xs, 50), 3) if xs else None


def main(argv=None):
    p = argparse.ArgumentParser(description="Agreement between a local System One server and real Jev.")
    p.add_argument("--url", required=True, help="local route, e.g. http://192.168.4.126:8724/v1/systemone")
    p.add_argument("--key", help="Bearer key the local server wants (default LOCALJEV_KEY; argv is visible in ps, prefer the variable)")
    p.add_argument("-n", type=int, default=80, help="States from agent.jev.bench_states")
    p.add_argument("--timeout", type=float, default=5.0, help="per-call budget; generous, this measures agreement")
    a = p.parse_args(argv)
    print(json.dumps(paired(a.n, a.url, a.key or os.environ.get("LOCALJEV_KEY"), a.timeout), indent=1))


if __name__ == "__main__":
    main()

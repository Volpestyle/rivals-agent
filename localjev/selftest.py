"""Offline check of localjev.paired: two stub servers stand in for the local one and for Jev.

No model, no network beyond loopback.

    uv run python -m localjev.selftest
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from agent import jev as J
from localjev import paired as P

KEY = "test-key"


def _server(pick, want_key=None):
    """A System One stub that answers `pick(options)` for every question."""

    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            if want_key and self.headers.get("Authorization") != "Bearer " + want_key:
                self.send_response(401), self.end_headers()
                return
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            answers = {}
            for qid, q in body["questions"].items():
                opts = list(q["criteria"])
                choice = pick(qid, opts)
                answers[qid] = {"type": "choice", "choice": choice,
                                "probabilities": {o: float(o == choice) for o in opts},
                                "confidence": 0.9}
            out = json.dumps({"model": body.get("model"), "answers": answers,
                              "usage": {"input_tokens": 100, "output_tokens": 3, "cost": 2e-05}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_port}/v1/systemone"


def main():
    first = lambda qid, opts: opts[0]
    last = lambda qid, opts: opts[-1] if qid == "intent" else opts[0]

    a, url_a = _server(first, KEY)
    b, url_b = _server(first)
    J.Endpoint.from_env = classmethod(lambda cls, env=None: J.Endpoint(url_b, "stub-jev", None))  # stand in for Jev

    res = P.paired(12, url_a, KEY)
    assert res["answered"] == {"local": 12, "jev": 12}, res
    assert res["agreement_local_vs_jev"] == 1.0, res   # same stub logic, so every intent matches
    assert res["disagreements_jev_to_local"] == {}, res
    assert res["cost_usd_jev"] > 0, res                # usage.cost is read back

    c, url_c = _server(last, KEY)                      # a local server that picks a different intent
    res = P.paired(12, url_c, KEY)
    assert res["agreement_local_vs_jev"] < 1.0, res
    assert res["disagreements_jev_to_local"], res

    bad = P.paired(3, url_a, "wrong-key")              # a rejected key falls back, never raises
    assert bad["fallbacks"]["local"] == {"http": 3}, bad
    assert bad["answered"]["local"] == 0, bad
    assert bad["agreement_local_vs_jev"] is None, bad

    for s in (a, b, c):
        s.shutdown()
    print("localjev.selftest: ok")


if __name__ == "__main__":
    main()

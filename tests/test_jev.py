"""decide_jev against a stubbed transport: request shape, mapping, every fallback, the hard deadline. No network."""
import inspect
import json
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import pytest

from agent import brain, jev

REAL_DOTENV = jev._dotenv  # bound at import, before conftest stubs it per test
from agent.brain import BURST_MAX_S, PULL_MAX_S, STRIKE_MAX_S, SWING_MAX_S, Memory
from agent.intents import BURST, Combo, Disengage, Engage, Idle, Pull, Search, SwingTo, WebStrike
from agent.jev import HttpTransport, Jev, TransportError
from agent.replay import synthetic
from agent.state import ANCHOR, ENEMY, PULL, SWING, UPPERCUT, Ability, Detection, State

FRAME = (2560, 1440)
READY = {SWING: Ability(True, 3), PULL: Ability(True), UPPERCUT: Ability(True, 2)}
ANCH = Detection(ANCHOR, (1800, 200, 1900, 300), 0.8)


def enemy(x=1280, tagged=None, h=300):  # h = bbox height px: 300 is mid range and 90 far on a 1440 px frame
    return Detection(ENEMY, (x - h / 4, 720 - h / 2, x + h / 4, 720 + h / 2), 0.9, tagged=tagged)


def st(t=0.0, **kw):
    kw.setdefault("frame", FRAME)
    kw.setdefault("hp", 100)
    kw.setdefault("max_hp", 100)
    kw.setdefault("abilities", dict(READY))
    kw.setdefault("webs", 3)
    kw.setdefault("on_target", True)
    return State(t=t, **kw)


def reply(intent, target=None, anchor=None, tprobs=None, cost=2e-5):
    """A well-formed decisions response choosing `intent`, optionally with target / anchor answers."""
    def ans(choice, probs):
        return {"type": "choice", "choice": choice, "probabilities": probs, "confidence": 0.9}

    a = {"intent": ans(intent, {intent: 1.0})}
    if target is not None:
        a["target"] = ans(str(target), tprobs or {str(target): 1.0})
    if anchor is not None:
        a["anchor"] = ans(str(anchor), {str(anchor): 1.0})
    return {"answers": a, "usage": {"input_tokens": 500, "output_tokens": 50, "cost": cost}}


class Stub:
    """Transport double: returns / raises what it is given, one item per call (the last repeats)."""

    def __init__(self, *script):
        self.script, self.calls = list(script), []

    def __call__(self, body, timeout_s):
        self.calls.append((body, timeout_s))
        item = self.script.pop(0) if len(self.script) > 1 else self.script[0]
        if isinstance(item, Exception):
            raise item
        return item


def scene():
    """Index 0: centred untagged enemy. Index 1: tagged enemy off to the side. One anchor."""
    return st(detections=[enemy(1280, tagged=False), enemy(1700, tagged=True), ANCH])


# --- mapping ----------------------------------------------------------------

def test_every_intent_maps_back_with_its_option_bound():
    d0, d1 = enemy(1280, tagged=False), enemy(1700, tagged=True)
    cases = [
        (reply("engage", target=0), Engage(d0), None),
        (reply("pull", target=0), Pull(d0), PULL_MAX_S),
        (reply("web_strike", target=1), WebStrike(d1), STRIKE_MAX_S),
        (reply(BURST, target=0), Combo(BURST, d0), BURST_MAX_S),
        (reply("swing_to", anchor=0), SwingTo(ANCH), SWING_MAX_S),
        (reply("search"), Search(), None),
        (reply("idle"), Idle(), None),
        (reply("disengage"), Disengage(), None),
    ]
    for response, expected, hold in cases:
        m = Memory()
        got = Jev(Stub(response))(scene(), m)
        assert got == expected
        assert m.intent == expected
        if hold is None:
            assert m.option is None
        else:
            assert m.option.status == "running" and m.option.intent is got and m.option.bound_t == pytest.approx(hold)


def test_target_is_the_most_probable_one_among_those_the_intent_allows():
    # index 1 is tagged, so pull cannot act on it however likely Jev thinks it is
    got = Jev(Stub(reply("pull", target=1, tprobs={"0": 0.1, "1": 0.9})))(scene(), Memory())
    assert got == Pull(enemy(1280, tagged=False))
    # engage allows both, so the higher probability wins
    got = Jev(Stub(reply("engage", target=1, tprobs={"0": 0.1, "1": 0.9})))(scene(), Memory())
    assert got == Engage(enemy(1700, tagged=True))


def test_answered_call_is_counted():
    jev_ = Jev(Stub(reply("engage", target=0, cost=3e-5)))
    jev_(scene(), Memory())
    s = jev_.stats
    assert (s.calls, s.fallbacks, len(s.latency_ms), s.input_tokens, s.confidence) == (1, Counter(), 1, 500, [0.9])
    assert s.cost == pytest.approx(3e-5) and s.fallback_rate == 0.0


# --- request ----------------------------------------------------------------

def test_request_is_typed_fields_and_a_fixed_choice_set():
    stub = Stub(reply("engage", target=0))
    Jev(stub, timeout_s=0.15)(scene(), Memory())
    (body, timeout_s), = stub.calls
    assert timeout_s == 0.15 and body["model"] == jev.MODEL == "typesafe/jev-1.13"
    assert isinstance(body["state"], dict)  # fields, not prose
    json.dumps(body)
    s = body["state"]
    assert s["hp"] == "high" and s["web_ammo"] == 3 and s["ready"] == {"swing": True, "pull": True, "uppercut": True}
    assert s["targets"][0] == {"i": 0, "cls": "enemy", "range": "mid", "tagged": False, "under_crosshair": True}
    assert s["targets"][1]["tagged"] is True and s["anchors"] == 1
    q = body["questions"]
    assert set(q) == {"intent", "target", "anchor"} and all(v["type"] == "choice" for v in q.values())
    assert list(q["intent"]["criteria"]) == ["engage", "pull", "web_strike", "burst", "swing_to", "search", "idle", "disengage"]
    assert list(q["target"]["criteria"]) == ["0", "1"] and list(q["anchor"]["criteria"]) == ["0"]


def test_only_intents_some_target_can_execute_are_offered():
    def offered(**kw):
        stub = Stub(reply("search"))
        Jev(stub)(st(**kw), Memory())
        (body, _), = stub.calls
        return list(body["questions"]["intent"]["criteria"]), body["questions"]

    names, q = offered(detections=[])
    assert names == ["search", "idle", "disengage"] and set(q) == {"intent"}  # nothing to target or swing to
    assert offered(detections=[enemy(tagged=False)])[0] == ["engage", "pull", "burst", "search", "idle", "disengage"]
    assert offered(detections=[enemy(tagged=True)])[0] == ["engage", "web_strike", "burst", "search", "idle", "disengage"]
    # tag unknown: never offer a bare Get Over Here!, but the burst tags first
    assert offered(detections=[enemy(tagged=None)])[0] == ["engage", "burst", "search", "idle", "disengage"]
    cooling = dict(READY, **{PULL: Ability(False)})
    assert offered(detections=[enemy(tagged=False)], abilities=cooling)[0] == ["engage", "search", "idle", "disengage"]
    assert offered(detections=[enemy(tagged=False)], abilities={})[0] == ["engage", "search", "idle", "disengage"]
    assert offered(detections=[enemy(tagged=False)], webs=0)[0] == ["engage", "pull", "search", "idle", "disengage"]
    assert offered(detections=[enemy(tagged=False)], on_target=False)[0] == ["engage", "web_strike"][:1] + ["search", "idle", "disengage"]
    far = enemy(h=90, tagged=False)  # beyond reach: the model may only engage or swing
    assert offered(detections=[far, ANCH])[0] == ["engage", "swing_to", "search", "idle", "disengage"]


def test_options_are_capped_nearest_the_crosshair_first():
    many = [enemy(x=1280 + 40 * i) for i in range(10)]
    stub = Stub(reply("engage", target=0))
    Jev(stub)(st(detections=many), Memory())
    (body, _), = stub.calls
    assert len(body["state"]["targets"]) == jev.MAX_OPTIONS == len(body["questions"]["target"]["criteria"])


def test_scripted_decisions_are_always_legal():
    """jev.legal and brain.policy agree about the kit preconditions on every fresh choice of the synthetic story."""
    m, checked = Memory(), 0
    for s in synthetic():
        early, target = brain.gate(s, m)
        if early is not None:
            continue  # retreat, a playing hold or a flicker: not a fresh choice, and legal only when it was made
        intent = brain.policy(s, m, target)
        checked += 1
        assert jev.legal(jev.name_of(intent), s, getattr(intent, "target", None) or getattr(intent, "anchor", None)), (s.t, intent)
    assert checked > 50


# --- fallbacks --------------------------------------------------------------

FALLBACKS = [
    (TimeoutError("late"), "timeout"),
    (TransportError("HTTP 502"), "http"),
    (ValueError("not json"), "parse"),
    ({}, "parse"),
    ("garbage", "parse"),
    ({"answers": {}}, "parse"),
    ({"answers": {"intent": {"choice": 7, "probabilities": {}}}}, "parse"),
    ({"answers": {"intent": {"choice": "engage"}}}, "parse"),  # no probabilities
    (reply("engage"), "parse"),  # a target-needing intent without its target answer
    (reply("engage", target=0, tprobs={"0": "high"}), "parse"),
    (reply("banana"), "vocab"),
    (reply("swing_to", anchor=0), "vocab"),  # a real intent, but not offered: no anchor in the scene
]


def test_every_failure_falls_back_to_the_scripted_choice_and_is_counted():
    s = st(detections=[enemy(tagged=False)])
    expected = brain.decide(s, Memory())
    assert isinstance(expected, Combo)
    for bad, reason in FALLBACKS:
        j = Jev(Stub(bad))
        m = Memory()
        assert j(s, m) == expected, bad
        assert m.option.status == "running" and m.option.bound_t == pytest.approx(BURST_MAX_S)  # the scripted policy's own bookkeeping ran
        assert j.stats.fallbacks == Counter({reason: 1}) and j.stats.calls == 1 and j.stats.fallback_rate == 1.0, bad


def test_offered_but_masked_intents_are_out_of_vocabulary():
    s = st(detections=[enemy(tagged=None)])  # pull is not offered when the tag is unknown
    j = Jev(Stub(reply("pull", target=0)))
    assert j(s, Memory()) == brain.decide(s, Memory())
    assert j.stats.fallbacks == Counter(vocab=1)


def test_fallback_rate_mixes_answers_and_failures():
    j = Jev(Stub(reply("engage", target=0), TimeoutError(), reply("engage", target=0), TransportError("x")))
    for i in range(4):
        j(scene(), Memory())
    assert j.stats.calls == 4 and j.stats.fallbacks == Counter(timeout=1, http=1) and j.stats.fallback_rate == 0.5
    assert len(j.stats.latency_ms) == 2


# --- the scripted rules never wait on the model -----------------------------

def test_retreat_hold_flicker_and_detector_down_make_no_call():
    stub = Stub(reply("engage", target=0))
    j, m = Jev(stub), Memory()
    assert j(st(0, hp=20, detections=[enemy()]), m) == Disengage() and not stub.calls  # retreat preempts

    j, m = Jev(stub), Memory()
    assert j(st(0, detections=[enemy(tagged=False)]), m) == Engage(enemy(tagged=False))
    assert len(stub.calls) == 1
    stub.script = [reply(BURST, target=0)]
    j(st(0.1, detections=[]), m)  # the target flickered out: keep the intent
    assert len(stub.calls) == 1

    stub2 = Stub(reply(BURST, target=0))
    j, m = Jev(stub2), Memory()
    first = j(st(0, detections=[enemy(tagged=False)]), m)
    assert isinstance(first, Combo) and len(stub2.calls) == 1
    assert j(st(0.5, detections=[enemy(x=1400, tagged=False)]), m) is first  # burst hold is playing
    assert len(stub2.calls) == 1

    stub3 = Stub(reply("engage", target=0))
    assert Jev(stub3)(st(0, detections=None), Memory()) == Idle() and not stub3.calls  # detector down: nothing to ask


# --- transport --------------------------------------------------------------

class FakeSession:
    """Stands in for jev._Session: one worker thread; each post() takes the next (delay, error) of `script`."""
    made = []

    def __init__(self, key, script):
        self.key, self.script = key, list(script)
        self.pool = ThreadPoolExecutor(max_workers=1)
        self.closed = False
        FakeSession.made.append(self)

    def post(self, body):
        delay, error = self.script.pop(0)
        time.sleep(delay)
        if error:
            raise error
        return {"ok": True}

    def close(self):
        self.closed = True
        self.pool.shutdown(wait=False, cancel_futures=True)


def transport(*script_per_session):
    """An HttpTransport whose n-th session plays the n-th script."""
    FakeSession.made = []
    scripts = iter(script_per_session)
    return HttpTransport(key="k", session_factory=lambda key: FakeSession(key, next(scripts)))


def test_deadline_is_hard_and_a_call_during_a_stuck_one_fails_at_once():
    tr = transport([(0.4, None), (0.0, None)])
    t0 = time.perf_counter()
    with pytest.raises(TimeoutError):
        tr({}, 0.05)
    assert time.perf_counter() - t0 < 0.3  # gave up at the deadline, not after the 0.4 s reply
    t1 = time.perf_counter()
    with pytest.raises(TimeoutError, match="in flight"):
        tr({}, 0.5)
    assert time.perf_counter() - t1 < 0.05  # never queued behind the call still running
    assert tr.sent == 1


def test_a_late_answer_leaves_a_warm_connection_for_the_next_call():
    tr = transport([(0.15, None), (0.0, None)])
    with pytest.raises(TimeoutError):
        tr({}, 0.02)
    time.sleep(0.3)  # the late answer lands and is discarded
    assert tr({}, 0.5) == {"ok": True}
    assert len(FakeSession.made) == 1 and not FakeSession.made[0].closed  # same session: no new handshake


def test_a_late_failure_drops_the_session():
    tr = transport([(0.1, TransportError("HTTP 500"))], [(0.0, None)])
    with pytest.raises(TimeoutError):
        tr({}, 0.02)
    time.sleep(0.25)
    assert tr({}, 0.5) == {"ok": True}
    assert len(FakeSession.made) == 2 and FakeSession.made[0].closed


def test_transport_error_drops_the_session():
    tr = transport([(0.0, TransportError("HTTP 500"))], [(0.0, None)])
    with pytest.raises(TransportError):
        tr({}, 0.5)
    assert tr({}, 0.5) == {"ok": True} and len(FakeSession.made) == 2 and FakeSession.made[0].closed


def test_a_slow_answer_through_jev_is_a_counted_timeout_and_returns_at_the_deadline():
    j = Jev(transport([(0.5, None)]), timeout_s=0.05)
    s = st(detections=[enemy(tagged=False)])
    t0 = time.perf_counter()
    got = j(s, Memory())
    assert time.perf_counter() - t0 < 0.3
    assert got == brain.decide(s, Memory()) and j.stats.fallbacks == Counter(timeout=1)
    assert j(s, Memory()) == got and j.stats.fallbacks == Counter(timeout=2)  # still in flight: fails at once, counted


def test_submit_returns_a_future_and_a_second_submit_while_it_is_in_flight_fails_at_once():
    tr = transport([(0.3, None), (0.0, None)])
    fut = tr.submit({})
    assert not fut.done()
    t0 = time.perf_counter()
    with pytest.raises(TimeoutError, match="in flight"):
        tr.submit({})
    assert time.perf_counter() - t0 < 0.05
    assert fut.result(2) == {"ok": True}
    assert tr.submit({}).result(2) == {"ok": True} and len(FakeSession.made) == 1  # the same warm session


def test_submit_after_a_failed_request_uses_a_fresh_session():
    tr = transport([(0.0, TransportError("HTTP 500"))], [(0.0, None)])
    fut = tr.submit({})
    assert isinstance(fut.exception(2), TransportError)
    assert tr.submit({}).result(2) == {"ok": True}
    assert len(FakeSession.made) == 2 and FakeSession.made[0].closed


def test_key_never_appears_in_repr_or_error_text(tmp_path, monkeypatch):
    secret = "sk-or-v1-not-a-real-key"
    assert secret not in repr(HttpTransport(key=secret)) and secret not in repr(Jev(HttpTransport(key=secret)))
    assert secret not in jev.redact(f"echoed {secret} back", secret) and "***" in jev.redact(f"echoed {secret}", secret)

    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    env = tmp_path / ".env"
    env.write_text(f"OTHER=1\nOPENROUTER_API_KEY='{secret}'\n")
    assert jev.load_key(env) == secret
    monkeypatch.setenv("OPENROUTER_API_KEY", "from-env")
    assert jev.load_key(env) == "from-env"
    monkeypatch.delenv("OPENROUTER_API_KEY")
    (tmp_path / "empty.env").write_text("SOMETHING=else\n")
    with pytest.raises(RuntimeError) as e:
        jev.load_key(tmp_path / "empty.env")
    assert "else" not in str(e.value)


def test_decide_jev_has_the_brain_signature():
    assert list(inspect.signature(jev.decide_jev).parameters) == list(inspect.signature(brain.decide).parameters)


# --- configured endpoint -----------------------------------------------------

LOCAL_URL = "http://192.168.4.20:8724/v1/systemone"


def test_endpoint_defaults_are_the_openrouter_values():
    ep = jev.Endpoint.from_env({})
    assert (ep.url, ep.model, ep.key) == ("https://openrouter.ai/api/alpha/decisions", "typesafe/jev-1.13", None)
    assert (ep.secure, ep.host, ep.port, ep.path) == (True, "openrouter.ai", None, "/api/alpha/decisions")
    assert jev.Endpoint.from_env({"JEV_URL": "", "JEV_MODEL": ""}) == ep  # empty means unset


def test_endpoint_reads_url_model_and_key_from_the_environment():
    ep = jev.Endpoint.from_env({"JEV_URL": LOCAL_URL + "?debug=1", "JEV_MODEL": "jev-local", "JEV_KEY": "lan-key-123"})
    assert (ep.secure, ep.host, ep.port, ep.path, ep.model) == (False, "192.168.4.20", 8724, "/v1/systemone?debug=1", "jev-local")
    assert ep.key == "lan-key-123" and "lan-key-123" not in repr(ep)


@pytest.mark.parametrize("bad", ["openrouter.ai/api", "ftp://host/x", "http:///nohost", "http://"])
def test_a_url_that_is_not_http_with_a_host_is_refused(bad):
    with pytest.raises(ValueError, match="JEV_URL"):
        jev.Endpoint.from_env({"JEV_URL": bad})


def test_key_policy_default_url_sends_the_openrouter_key_and_another_url_sends_only_jev_key(monkeypatch):
    for name in ("JEV_URL", "JEV_MODEL", "JEV_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    assert HttpTransport().bearer  # OpenRouter's default needs its key
    local = jev.Endpoint(url=LOCAL_URL)
    assert not HttpTransport(endpoint=local).bearer  # a local server without a key gets no Authorization header
    assert HttpTransport(endpoint=jev.Endpoint(url=LOCAL_URL, key="lan-key")).bearer
    monkeypatch.delenv("OPENROUTER_API_KEY")
    HttpTransport(endpoint=local)  # and it does not demand OPENROUTER_API_KEY either


def test_the_model_name_follows_the_endpoint_and_the_environment(monkeypatch):
    monkeypatch.delenv("JEV_MODEL", raising=False)
    assert Jev(Stub(reply("search"))).model == "typesafe/jev-1.13"
    monkeypatch.setenv("JEV_MODEL", "from-env")
    stub = Stub(reply("search"))
    Jev(stub)(st(detections=[]), Memory())
    assert stub.calls[0][0]["model"] == "from-env"
    assert Jev(Stub(reply("search")), model="explicit").model == "explicit"
    tr = HttpTransport(key="k", endpoint=jev.Endpoint(url=LOCAL_URL, model="jev-local"))
    assert Jev(tr).model == "jev-local"  # the transport's endpoint wins over the environment


class FakeConn:
    """Stands in for http.client.HTTP(S)Connection: records the request instead of sending it."""
    made = []
    status, reply_body = 200, b'{"answers": {}}'

    def __init__(self, host, port=None, timeout=None):
        self.host, self.port, self.sent = host, port, None
        type(self).made.append(self)

    def request(self, method, path, body, headers):
        self.sent = (method, path, json.loads(body), headers)

    def getresponse(self):
        outer = self

        class Resp:
            status = outer.status

            def read(self):
                return outer.reply_body

        return Resp()


def test_the_session_posts_to_the_configured_route_with_or_without_a_bearer_key(monkeypatch):
    class Plain(FakeConn):
        made = []

    class Secure(FakeConn):
        made = []

    monkeypatch.setattr(jev.http.client, "HTTPConnection", Plain)
    monkeypatch.setattr(jev.http.client, "HTTPSConnection", Secure)
    local = jev.Endpoint(url=LOCAL_URL)

    s = jev._Session(None, local)
    assert s.post({"q": 1}) == {"answers": {}}
    (conn,) = Plain.made
    assert (conn.host, conn.port) == ("192.168.4.20", 8724) and conn.sent[:3] == ("POST", "/v1/systemone", {"q": 1})
    assert "Authorization" not in conn.sent[3] and conn.sent[3]["Content-Type"] == "application/json"

    keyed = jev._Session("lan-key", local)
    keyed.post({})
    assert Plain.made[1].sent[3]["Authorization"] == "Bearer lan-key"

    remote = jev._Session("or-key", jev.Endpoint())
    remote.post({})
    (conn,) = Secure.made  # https goes through the TLS connection class, on the scheme's default port
    assert (conn.host, conn.port) == ("openrouter.ai", None) and conn.sent[1] == "/api/alpha/decisions"
    assert conn.sent[3]["Authorization"] == "Bearer or-key"
    for session in (s, keyed, remote):
        session.close()


def test_a_server_error_that_echoes_the_key_is_redacted(monkeypatch):
    class Echo(FakeConn):
        made = []
        status, reply_body = 401, b'bad credentials: Bearer lan-key-123'

    monkeypatch.setattr(jev.http.client, "HTTPConnection", Echo)
    s = jev._Session("lan-key-123", jev.Endpoint(url=LOCAL_URL))
    with pytest.raises(TransportError) as e:
        s.post({})
    assert "lan-key-123" not in str(e.value) and "HTTP 401" in str(e.value)
    s.close()


def test_endpoint_reads_dotenv_and_the_environment_wins(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("# comment\nJEV_URL=https://api.typesafe.ai/v1/systemone\nJEV_MODEL='jev-latest'\nJEV_KEY=abc\n")
    monkeypatch.setattr(jev, "_dotenv", lambda path=None: REAL_DOTENV(env_file))
    for name in ("JEV_URL", "JEV_MODEL", "JEV_KEY"):
        monkeypatch.delenv(name, raising=False)
    ep = jev.Endpoint.from_env()
    assert (ep.url, ep.model, ep.key) == ("https://api.typesafe.ai/v1/systemone", "jev-latest", "abc")
    assert "abc" not in repr(ep)
    monkeypatch.setenv("JEV_MODEL", "jev-1.13.0")
    assert jev.Endpoint.from_env().model == "jev-1.13.0"

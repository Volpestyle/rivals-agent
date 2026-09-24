"""Jev (TypeSafe System One) behind the brain's function boundary.

decide_jev(state, memory) -> Intent has brain.decide's signature. The scripted
gate (retreat, playing holds, a flickering target) always runs first, so those
rules never wait on the network; Jev replaces only the choice, brain.policy.

Two ways to ask, both counted in Jev.stats and both logging per tick which source
decided (gate, jev, standing or scripted):

  Jev       blocking: wait up to a hard deadline for the answer, else brain.policy.
  AsyncJev  never waits: one request in flight at a time. A landed answer is adopted
            only if it is still valid (young enough, same situation, its target still
            visible, still legal), else dropped and counted. An adopted answer then
            STANDS as the policy choice, tracking its target from tick to tick, until
            the next answer replaces it, the situation or target it was about changes,
            it is no longer legal, or it is older than STANDING_MAX_S. brain.policy
            fills every tick with no valid standing answer. This is what decide_jev uses.

A timeout, HTTP error, unparseable or out-of-vocabulary answer always means
brain.policy for that tick.

Wire shape (docs/lanes/l5-brain.md, "Jev"): POST https://openrouter.ai/api/alpha/decisions.
The chat/completions route refuses this model, so tool_choice and response_format
do not apply. JEV_URL, JEV_MODEL and JEV_KEY point the same body at another server (Endpoint).

  {"model": ..., "state": {...typed fields...},
   "questions": {"intent": {"type": "choice", "instructions": ..., "criteria": {name: description}},
                 "target": {...}, "anchor": {...}}}
  -> {"answers": {"intent": {"choice": ..., "probabilities": {name: p}, "confidence": ...}, ...},
      "usage": {"input_tokens": ..., "output_tokens": ..., "cost": ...}}

Run `uv run python -m agent.jev` (blocking) or `... --async --hz 10` to measure.
"""
import argparse
import concurrent.futures
import copy
import dataclasses
import http.client
import json
import math
import os
import socket
import statistics
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from . import brain
from .brain import (BURST_HOLD_S, HOSTILE, HP_RESUME, HP_RETREAT, MIN_CONF, PULL_HOLD_S, STRIKE_HOLD_S, SWING_HOLD_S,
                    Memory, aimed_at, crosshair, range_of, ready)
from .intents import BURST, MACROS, Combo, Disengage, Engage, Idle, Pull, Search, SwingTo, WebStrike
from .state import ANCHOR, PULL, SWING, UPPERCUT, State

MODEL = "typesafe/jev-1.13"  # pinned: the jev-latest slug 404s on OpenRouter's models API
DEFAULT_URL = "https://openrouter.ai/api/alpha/decisions"
TIMEOUT_S = 0.2      # guess: Jev's blocking budget, one tick at 5 Hz. The measured round trip is above this (docs/lanes/l5-brain.md)
MAX_AGE_S = 0.6      # guess: AsyncJev drops an answer older than this (state.t). Covers the p95 round trip with margin
STANDING_MAX_S = 1.0  # guess: a standing answer expires this long after the State it was about. About three round trips, so answers that keep landing keep it alive
MATCH_FRAC = 0.15    # guess: an answered target must have a current detection of its class within this fraction of the frame height
SOCKET_CAP_S = 5.0   # bounds a hung request: no new request can start until it ends
MAX_OPTIONS = 6      # hostiles and anchors offered per call, nearest the crosshair first
ROOT = Path(__file__).resolve().parent.parent

# The vocabulary: intents.py names, each with the description Jev reads. Jev takes
# criteria literally, so each one states its own preconditions.
INTENTS = {
    "engage": "Aim at the target, close in and fight it with web shots, melee and the uppercut",
    "pull": "Get Over Here! on an UNTAGGED target: it is dragged to you (25 damage). "
            "The target must be untagged, in range and under the crosshair",
    "web_strike": "Get Over Here! on a TAGGED target: you zip to it and kick it (55 damage). The target must be tagged",
    BURST: "Full combo on the target: web tag, web strike, uppercut, melee. "
           "Needs web ammo and the target in range and under the crosshair",
    "swing_to": "Web-swing to an anchor point to travel or reposition",
    "search": "No hostile worth fighting: look around for one",
    "idle": "Do nothing this tick",
    "disengage": "Break line of sight and get away, for a fight that is going badly",
}
TARGETED = ("engage", "pull", "web_strike", BURST)  # intents that act on one hostile from the `target` answer
HOLD_S = {"pull": PULL_HOLD_S, "web_strike": STRIKE_HOLD_S, BURST: BURST_HOLD_S, "swing_to": SWING_HOLD_S}
KIND = {"engage": Engage, "pull": Pull, "web_strike": WebStrike, "swing_to": SwingTo,
        "search": Search, "idle": Idle, "disengage": Disengage}  # everything except the macros
NAME = {kind: name for name, kind in KIND.items()}


class TransportError(Exception):
    """The request failed or the server answered with an error status."""


class Fallback(Exception):
    """This tick goes to the scripted policy; reason is one of timeout, http, parse, vocab."""

    def __init__(self, reason):
        self.reason = reason


def name_of(intent):
    """The vocabulary name of an Intent: 'engage', 'pull', 'burst', ..."""
    return intent.name if isinstance(intent, Combo) else NAME[type(intent)]


def build(name, det):
    if name in MACROS:
        return Combo(name, det)
    kind = KIND[name]
    return kind(det) if det is not None else kind()


def legal(name, state, det=None):
    """Kit preconditions for an intent, the same ones brain.policy enforces.

    Jev is not trusted with these: it is only offered intents some target satisfies,
    its target is picked among the targets that do, and AsyncJev re-checks them
    against the State it adopts into. swing_to needs an anchor, which the caller
    checks; det is the hostile for the targeted intents.
    """
    if name in ("search", "idle", "disengage"):
        return True
    if name == "swing_to":
        return ready(state, SWING)
    if det is None:
        return False
    if name == "engage":
        return True
    reach = range_of(det, state) != "far"  # pull and burst reach 20 m; the strike locks out to 24 m
    if name == "web_strike":
        return det.tagged is True and ready(state, PULL) and reach
    if name == "pull":
        return det.tagged is False and ready(state, PULL) and reach and aimed_at(state, det)
    if name == BURST:
        return bool(state.webs) and ready(state, PULL) and ready(state, UPPERCUT) and reach and aimed_at(state, det)
    return False


def hostiles(state, target):
    """Hostile detections nearest the crosshair first, except that the gate's sticky target leads."""
    cross = crosshair(state)
    found = sorted((d for d in state.detections or [] if d.cls in HOSTILE and d.conf >= MIN_CONF),
                   key=lambda d: math.dist(d.center, cross))
    if target in found:
        found.remove(target)
        found.insert(0, target)
    return found[:MAX_OPTIONS]


def anchors(state):
    cross = crosshair(state)
    found = sorted((d for d in state.detections or [] if d.cls == ANCHOR and d.conf >= MIN_CONF),
                   key=lambda d: math.dist(d.center, cross))
    return found[:MAX_OPTIONS]


def offered(state, hostile, anchor):
    """Intent names some target can execute right now. Unknown fields never offer an ability."""
    names = [n for n in TARGETED if any(legal(n, state, d) for d in hostile)]
    if anchor and legal("swing_to", state):
        names.append("swing_to")
    return names + ["search", "idle", "disengage"]


def _tri(state, name):
    """True / False / None (unknown) readiness of one ability."""
    a = state.abilities.get(name)
    if a is None:
        return None
    if a.ready is not None:
        return a.ready
    return None if a.charges is None else a.charges > 0


def encode(state, hostile, anchor):
    """The State as compact typed fields. Arithmetic (ranges, hp buckets) is done here: Jev is not a calculator."""
    cx, cy = crosshair(state)
    hp = None if state.hp is None or not state.max_hp else state.hp / state.max_hp
    return {
        "hp": "unknown" if hp is None else "low" if hp <= HP_RETREAT else "high" if hp >= HP_RESUME else "mid",
        "web_ammo": state.webs,
        "ready": {n: _tri(state, n) for n in (SWING, PULL, UPPERCUT)},  # null = unknown
        "crosshair_on_hostile": state.on_target,
        "targets": [{"i": i, "cls": d.cls, "range": range_of(d, state), "tagged": d.tagged,
                     "under_crosshair": d.bbox[0] <= cx <= d.bbox[2] and d.bbox[1] <= cy <= d.bbox[3]}
                    for i, d in enumerate(hostile)],
        "anchors": len(anchor),
    }


def questions(state, names, hostile, anchor):
    q = {"intent": {"type": "choice", "instructions": "Which single intent should the Spider-Man fighter play next?",
                    "criteria": {n: INTENTS[n] for n in names}}}
    if hostile and any(n in TARGETED for n in names):
        q["target"] = {"type": "choice", "instructions": "Which target should that intent act on?",
                       "criteria": {str(i): f"{d.cls}, {range_of(d, state)} range, tag {d.tagged}" for i, d in enumerate(hostile)}}
    if anchor and "swing_to" in names:
        q["anchor"] = {"type": "choice", "instructions": "Which anchor point should the swing go to?",
                       "criteria": {str(i): f"anchor point {i}" for i in range(len(anchor))}}
    return q


def _answer(resp, key):
    try:
        a = resp["answers"][key]
        choice, probs = a["choice"], a["probabilities"]
        if not isinstance(choice, str) or not isinstance(probs, dict):
            raise TypeError
        return choice, probs, a.get("confidence")
    except (KeyError, TypeError):
        raise Fallback("parse") from None


def _best(resp, key, options, ok):
    """The option Jev gave the most probability among those that pass `ok`."""
    _, probs, _ = _answer(resp, key)
    try:
        scored = [(float(probs.get(str(i), 0)), -i) for i, d in enumerate(options) if ok(d)]
    except (TypeError, ValueError):
        raise Fallback("parse") from None
    return options[-max(scored)[1]]


def reassociate(state, det):
    """The current detection of det: the one with its track id when it has one (det itself while the tracker holds it unseen), else
    the current detection of det's class nearest where det was, within MATCH_FRAC of the frame height; else None."""
    if det.track is not None:
        same = next((d for d in state.detections or [] if d.track == det.track and d.cls == det.cls and d.conf >= MIN_CONF), None)
        if same is not None:
            return same
        if det.track in state.coasting:
            return det
    near = [d for d in state.detections or []
            if d.cls == det.cls and d.conf >= MIN_CONF and math.dist(d.center, det.center) <= MATCH_FRAC * state.frame[1]]
    return min(near, key=lambda d: math.dist(d.center, det.center), default=None)


@dataclass(frozen=True)
class Endpoint:
    """Where the decisions route lives, the model name it gets, and the Bearer key it wants.

    Read once from the environment, so pointing the agent at another server changes no
    call site. Every default is the OpenRouter value:

      JEV_URL    full URL of the route: scheme, host, port and path. http or https.
      JEV_MODEL  the `model` field of the request.
      JEV_KEY    Bearer key to send. Unset, the default URL sends OPENROUTER_API_KEY (environment
                 or .env) and any other URL sends no Authorization header at all.

    All three are read from the environment, else the repo's gitignored .env. TypeSafe's own API
    takes the same body: JEV_URL=https://api.typesafe.ai/v1/systemone, JEV_MODEL=jev-latest.
    """
    url: str = DEFAULT_URL
    model: str = MODEL
    key: str | None = field(default=None, repr=False)  # a secret: never in a repr

    def __post_init__(self):
        u = urlsplit(self.url)
        if u.scheme not in ("http", "https") or not u.hostname:
            raise ValueError(f"JEV_URL must be an http(s) URL with a host, got {self.url!r}")

    @classmethod
    def from_env(cls, env=None):
        env = {**_dotenv(), **os.environ} if env is None else env  # the real environment wins over .env
        return cls(env.get("JEV_URL") or DEFAULT_URL, env.get("JEV_MODEL") or MODEL, env.get("JEV_KEY") or None)

    @property
    def secure(self):
        return urlsplit(self.url).scheme == "https"

    @property
    def host(self):
        return urlsplit(self.url).hostname

    @property
    def port(self):
        return urlsplit(self.url).port  # None: the scheme's default

    @property
    def path(self):
        u = urlsplit(self.url)
        return (u.path or "/") + (f"?{u.query}" if u.query else "")


@dataclass
class Stats:
    calls: int = 0                                          # requests that reached the model
    fallbacks: Counter = field(default_factory=Counter)     # failed or unusable answers, by reason: timeout, http, parse, vocab
    drops: Counter = field(default_factory=Counter)         # AsyncJev: usable answers not adopted: gated, stale, situation, ...
    expired: Counter = field(default_factory=Counter)       # AsyncJev: standing answers that ended: aged, situation, target_gone, illegal, detector_down
    sources: Counter = field(default_factory=Counter)       # ticks by who decided: gate, jev (adopted this tick), standing, scripted
    chosen: Counter = field(default_factory=Counter)        # intents of the ticks Jev decided (jev or standing), by name
    trace: list = field(default_factory=list)               # (state.t, source) per tick, for the eval
    latency_ms: list = field(default_factory=list)          # round trip of every answered call
    age_ms: list = field(default_factory=list)              # AsyncJev: how old each adopted answer's State was
    confidence: list = field(default_factory=list)
    input_tokens: int = 0
    cost: float = 0.0                                       # USD, as reported by OpenRouter

    @property
    def fallback_rate(self):
        return sum(self.fallbacks.values()) / self.calls if self.calls else 0.0

    @property
    def jev_share(self):
        """Fraction of ticks decided by a Jev answer, fresh or standing."""
        n = sum(self.sources.values())
        return (self.sources["jev"] + self.sources["standing"]) / n if n else 0.0

    @property
    def standing_share(self):
        """Fraction of ticks decided by a standing answer (an answer adopted on an earlier tick)."""
        n = sum(self.sources.values())
        return self.sources["standing"] / n if n else 0.0


@dataclass
class Asked:
    """What one request was asked about, kept to interpret its answer and to check it is still valid."""
    state: State
    situation: str
    hostile: list
    anchor: list
    names: list

    @property
    def t(self):
        return self.state.t


class Jev:
    """Blocking decide_jev: waits up to timeout_s for the answer. `transport(body, timeout_s) -> dict` is injectable."""

    def __init__(self, transport=None, timeout_s=TIMEOUT_S, model=None):
        self.transport = transport or HttpTransport()
        endpoint = getattr(self.transport, "endpoint", None) or Endpoint.from_env()
        self.timeout_s, self.model, self.stats = timeout_s, model or endpoint.model, Stats()

    def __call__(self, state: State, memory: Memory):
        early, target = brain.gate(state, memory)
        if early is not None:
            return self._done(state, "gate", early)
        if target is None and state.detections is None:
            return self._done(state, "scripted", brain.policy(state, memory, target))  # detector down: nothing to ask
        self.stats.calls += 1
        try:
            name, det = self._choose(state, target)
        except Fallback as f:
            self.stats.fallbacks[f.reason] += 1
            return self._done(state, "scripted", brain.policy(state, memory, target))
        return self._done(state, "jev", adopt(state, memory, target, name, det))

    def _done(self, state, source, intent):
        self.stats.sources[source] += 1
        self.stats.trace.append((state.t, source))
        if source in ("jev", "standing"):
            self.stats.chosen[name_of(intent)] += 1
        return intent

    def _choose(self, state, target):
        body, asked = self._request(state, target)
        t0 = time.perf_counter()
        resp = self._resolve(lambda: self.transport(body, self.timeout_s))
        self.stats.latency_ms.append((time.perf_counter() - t0) * 1000)
        self._count(resp)
        return self._interpret(resp, asked)

    def _request(self, state, target):
        hostile, anchor = hostiles(state, target), anchors(state)
        names = offered(state, hostile, anchor)
        body = {"model": self.model, "state": encode(state, hostile, anchor),
                "questions": questions(state, names, hostile, anchor)}
        return body, Asked(state, brain.situation(state, target), hostile, anchor, names)

    @staticmethod
    def _resolve(get):
        """Run `get() -> response`, turning every transport failure into a Fallback so decide never raises."""
        try:
            return get()
        except TimeoutError:
            raise Fallback("timeout") from None
        except TransportError:
            raise Fallback("http") from None
        except ValueError:  # the body was not JSON
            raise Fallback("parse") from None
        except Exception:
            raise Fallback("http") from None

    def _interpret(self, resp, asked):
        """(intent name, chosen Detection or None) from a response, judged against the State it was asked about."""
        name, _, confidence = _answer(resp, "intent")
        if name not in asked.names:
            raise Fallback("vocab")
        if isinstance(confidence, (int, float)):
            self.stats.confidence.append(confidence)
        if name in TARGETED:
            return name, _best(resp, "target", asked.hostile, lambda d: legal(name, asked.state, d))
        if name == "swing_to":
            return name, _best(resp, "anchor", asked.anchor, lambda d: True)
        return name, None

    def _count(self, resp):
        usage = resp.get("usage") if isinstance(resp, dict) else None
        if isinstance(usage, dict):
            self.stats.input_tokens += int(usage.get("input_tokens") or 0)
            self.stats.cost += float(usage.get("cost") or 0)


def adopt(state, memory, target, name, det):
    """Make a chosen (name, detection) the intent for this tick, with the same hold and mode bookkeeping brain.policy does."""
    brain.track_mode(state, memory, target)
    return brain.commit(memory, build(name, det), state.t + HOLD_S[name] if name in HOLD_S else -math.inf)


@dataclass
class Flight:
    """The one request in the air."""
    fut: concurrent.futures.Future
    asked: Asked
    sent: float                   # perf_counter at submit
    done_at: float | None = None  # perf_counter when it landed


@dataclass
class Standing:
    """The adopted answer that is the policy choice until it ends."""
    name: str
    det: object     # the answered target or anchor, as of the last tick it was valid; None if the intent has none
    asked: Asked    # the State it was about: its time and its situation


class AsyncJev(Jev):
    """decide_jev that never waits on the network.

    Each tick: run the scripted gate (it preempts everything); collect the in-flight
    answer if it has landed; adopt it if it is still valid, else drop it (counted). An
    adopted answer stands: on later ticks it is the choice for as long as it stays valid
    for the State (see the module docstring). brain.policy decides only when no answer
    is standing. If nothing is in flight, the gate let a choice through and no hold was
    just started, a new request goes out about the current State. The transport needs `submit(body) -> Future`.
    A hung request holds the slot until the socket cap (SOCKET_CAP_S); brain.policy
    answers meanwhile.
    """

    def __init__(self, transport=None, max_age_s=MAX_AGE_S, model=None, standing_max_s=STANDING_MAX_S):
        super().__init__(transport, timeout_s=None, model=model)
        self.max_age_s, self.standing_max_s = max_age_s, standing_max_s
        self._flight = self._standing = None

    def __call__(self, state: State, memory: Memory):
        early, target = brain.gate(state, memory)
        landed = self._land()
        if early is not None:
            if landed:
                self.stats.drops["gated"] += 1  # a hold or a retreat is playing: not the moment for a new choice
            return self._done(state, "gate", early)
        intent = self._adopt(landed, state, memory, target) if landed else None
        source = "jev"
        if intent is None:
            intent, source = self._stand(state, memory, target), "standing"
        if intent is None:
            intent, source = brain.policy(state, memory, target), "scripted"
        if self._flight is None and memory.hold_until <= state.t and not (target is None and state.detections is None):
            self._launch(state, target)  # not on a tick that started a hold: its answer would land inside it and be gated
        return self._done(state, source, intent)

    def _launch(self, state, target):
        body, asked = self._request(state, target)
        try:
            fut = self.transport.submit(body)
        except Exception:
            self.stats.fallbacks["http"] += 1
            return
        self.stats.calls += 1
        flight = self._flight = Flight(fut, asked, time.perf_counter())
        fut.add_done_callback(lambda _: setattr(flight, "done_at", time.perf_counter()))

    def _land(self):
        """The landed answer as (name, det, asked); None while in flight, or if it failed (counted)."""
        fl = self._flight
        if fl is None or not fl.fut.done():
            return None
        self._flight = None
        try:
            resp = self._resolve(fl.fut.result)
            self.stats.latency_ms.append(((fl.done_at or time.perf_counter()) - fl.sent) * 1000)
            self._count(resp)
            return (*self._interpret(resp, fl.asked), fl.asked)
        except Fallback as f:
            self.stats.fallbacks[f.reason] += 1
            return None

    def _adopt(self, landed, state, memory, target):
        """The landed answer as this tick's intent if it is still valid for `state`, else None (drop counted)."""
        name, det, asked = landed
        reason = (
            "detector_down" if state.detections is None
            else "stale" if state.t - asked.t > self.max_age_s
            else "situation" if brain.situation(state, target) != asked.situation
            else None
        )
        if reason is None and det is not None:
            det = reassociate(state, det)  # the answered target as it is now, not as it was
            reason = "target_gone" if det is None else None
        if reason is None and not legal(name, state, det):
            reason = "illegal"
        if reason:
            self.stats.drops[reason] += 1
            return None
        self.stats.age_ms.append((state.t - asked.t) * 1000)
        self._standing = Standing(name, det, asked)  # replaces whatever was standing
        return adopt(state, memory, target, name, det)

    def _stand(self, state, memory, target):
        """The standing answer as this tick's intent while it is valid for `state`; else it ends (counted) and None."""
        st = self._standing
        if st is None:
            return None
        reason = (
            "detector_down" if state.detections is None
            else "aged" if state.t - st.asked.t > self.standing_max_s
            else "situation" if brain.situation(state, target) != st.asked.situation
            else None
        )
        det = st.det
        if reason is None and det is not None:
            det = reassociate(state, det)  # follow the target as it moves
            reason = "target_gone" if det is None else None
        if reason is None and not legal(st.name, state, det):
            reason = "illegal"
        if reason:
            self.stats.expired[reason] += 1
            self._standing = None
            return None
        st.det = det
        return adopt(state, memory, target, st.name, det)


# --- transport ---------------------------------------------------------------

def _dotenv(path=None):
    """NAME=value lines of the repo's gitignored .env as a dict; empty when there is none."""
    path = ROOT / ".env" if path is None else path
    if not path.is_file():
        return {}
    pairs = (line.partition("=") for line in path.read_text().splitlines() if "=" in line and not line.lstrip().startswith("#"))
    return {name.strip(): value.strip().strip("'\"") for name, _, value in pairs}


def load_key(env=ROOT / ".env"):
    """OPENROUTER_API_KEY from the environment, else the repo's gitignored .env. Never echoed."""
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key and env.is_file():
        for line in env.read_text().splitlines():
            name, _, value = line.partition("=")
            if name.strip() == "OPENROUTER_API_KEY":
                key = value.strip().strip("'\"")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is not set (environment or .env)")
    return key


def redact(text, key):
    return text.replace(key, "***") if key else text


class _Session:
    """One keep-alive connection and its single worker thread; dropped wholesale after any failure."""

    def __init__(self, key, endpoint):
        self.key, self.endpoint, self.conn = key, endpoint, None
        self.pool = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="jev")

    def post(self, body):  # runs on the worker thread
        ep = self.endpoint
        if self.conn is None:
            connect = http.client.HTTPSConnection if ep.secure else http.client.HTTPConnection
            self.conn = connect(ep.host, ep.port, timeout=SOCKET_CAP_S)
        headers = {"Content-Type": "application/json"}
        if self.key:
            headers["Authorization"] = "Bearer " + self.key
        try:
            self.conn.request("POST", ep.path, json.dumps(body), headers)
            r = self.conn.getresponse()
            data = r.read()
        except TimeoutError:
            raise
        except (OSError, http.client.HTTPException) as e:
            raise TransportError(type(e).__name__) from None
        if r.status != 200:
            raise TransportError(f"HTTP {r.status}: " + redact(data[:300].decode("utf-8", "replace"), self.key))
        return json.loads(data)

    def close(self):
        self.pool.shutdown(wait=False, cancel_futures=True)
        sock = getattr(self.conn, "sock", None)
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)  # wakes a worker blocked in recv
            except OSError:
                pass


class HttpTransport:
    """The decisions route (OpenRouter's unless the environment says otherwise) over one kept-alive connection.

    submit(body) starts a request on a worker thread and returns its Future; calling
    the transport waits for it up to a hard wall-clock deadline (a socket timeout alone
    would not bound DNS, connect or a trickling reply). A timed-out request is left to
    finish in the background: a late answer leaves a warm connection, whereas dropping
    it would make every next call pay a cold TLS handshake (about 500 ms) and miss its
    own deadline too. While one request is in flight a new one fails at once instead of
    queueing behind it. After a failed request, including a late one, the session is
    dropped before the next.
    """

    def __init__(self, key=None, session_factory=None, endpoint=None):
        self.endpoint = endpoint or Endpoint.from_env()
        # the default URL needs the OpenRouter key; any other server gets a key only if JEV_KEY names one
        self._key = key or self.endpoint.key or (load_key() if self.endpoint.url == DEFAULT_URL else None)
        self._factory = session_factory or (lambda k: _Session(k, self.endpoint))
        self._session, self._last, self.sent = None, None, 0

    def __repr__(self):
        return "HttpTransport()"  # the key must never reach a log line

    @property
    def bearer(self):
        """Whether an Authorization header is sent."""
        return self._key is not None

    def submit(self, body):
        last = self._last
        if last is not None:
            if not last.done():
                raise TimeoutError("previous call still in flight")  # never queue behind it
            if last.exception() is not None:
                self._drop()  # the connection's state is unknown after a failure
        if self._session is None:
            self._session = self._factory(self._key)
        s = self._session
        self._last = fut = s.pool.submit(s.post, body)
        self.sent += 1
        return fut

    def __call__(self, body, timeout_s):
        fut = self.submit(body)
        try:
            return fut.result(timeout_s)
        except (concurrent.futures.TimeoutError, TimeoutError):
            raise TimeoutError(f"no answer in {timeout_s} s") from None

    def _drop(self):
        s, self._session, self._last = self._session, None, None
        if s is not None:
            s.close()


_default = None


def default():
    """The process-wide AsyncJev behind decide_jev: real transport, default bounds, one set of counters."""
    global _default
    if _default is None:
        _default = AsyncJev()
    return _default


def decide_jev(state: State, memory: Memory):
    return default()(state, memory)


# --- measurement -------------------------------------------------------------

def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, math.ceil(p / 100 * len(xs)) - 1)] if xs else None


def _spread(xs, *ps):
    return {f"p{p}": round(pct(xs, p)) for p in ps} | {"max": round(max(xs))} if xs else None


def bench_states(n):
    """n States spread over the synthetic story, all of which the scripted gate hands to the model."""
    from .replay import synthetic

    pool = []
    for s in synthetic():
        early, target = brain.gate(s, Memory())
        if early is None and not (target is None and s.detections is None):
            pool.append(s)
    return [pool[int(i * len(pool) / n) % len(pool)] for i in range(n)]


def story_loop(ticks, hz):
    """The synthetic story at `hz`, repeated end to end with continuing timestamps, `ticks` States long."""
    from .replay import synthetic

    one, out, k = synthetic(hz), [], 0
    span = one[-1].t + 1 / hz
    while len(out) < ticks:
        out += [dataclasses.replace(s, t=round(s.t + k * span, 3)) for s in one]
        k += 1
    return out[:ticks]


def bench(n, timeout_s, hz=0.0, transport=None):
    """Blocking Jev over n synthetic States. hz > 0 paces the calls like the live loop; 0 runs them back to back."""
    jev = Jev(transport, timeout_s)
    wall, agree, answered, differ = [], 0, 0, Counter()
    for s in bench_states(n):
        tick = time.perf_counter()
        before = len(jev.stats.latency_ms)
        t0 = time.perf_counter()
        got = jev(s, Memory())  # a fresh Memory each time, so every State reaches the model
        wall.append((time.perf_counter() - t0) * 1000)
        if len(jev.stats.latency_ms) > before:  # answered, not fallen back
            answered += 1
            scripted = name_of(brain.decide(s, Memory()))
            agree += name_of(got) == scripted
            if name_of(got) != scripted:
                differ[f"{scripted}->{name_of(got)}"] += 1
        if hz:
            time.sleep(max(0.0, 1 / hz - (time.perf_counter() - tick)))
    st, lat = jev.stats, jev.stats.latency_ms
    sent = getattr(jev.transport, "sent", None)  # requests actually sent: a timed-out one is still billed
    endpoint = getattr(jev.transport, "endpoint", None)
    return {
        "endpoint": {"url": endpoint.url, "model": jev.model, "bearer_sent": jev.transport.bearer} if endpoint else None,
        "calls": st.calls, "fallbacks": dict(st.fallbacks), "fallback_rate": round(st.fallback_rate, 3),
        "first_call_ms": round(lat[0]) if lat else None,
        "roundtrip_ms": {"p50": round(pct(lat[1:], 50)), "p95": round(pct(lat[1:], 95)), "min": round(min(lat[1:])),
                         "max": round(max(lat[1:]))} if len(lat) > 2 else None,
        "decide_wall_ms": {"p50": round(pct(wall, 50)), "p95": round(pct(wall, 95)), "max": round(max(wall))},
        "answered_within_ms": {b: round(sum(x <= b for x in lat) / len(lat), 2) for b in (100, 150, 200, 250, 300, 500)} if lat else None,
        "agreement_with_scripted": round(agree / answered, 2) if answered else None,
        "disagreements": dict(differ.most_common()),  # scripted -> jev
        "confidence_p50": round(statistics.median(st.confidence), 2) if st.confidence else None,
        "input_tokens_per_call": round(st.input_tokens / max(len(lat), 1)),
        "requests_sent": sent,
        "cost_usd_answered": round(st.cost, 6),
        "cost_usd_billed_est": round(st.cost / len(lat) * sent, 6) if lat and sent else None,
    }


def _switches(names):
    return sum(a != b for a, b in zip(names, names[1:]))


def bench_async(ticks, hz, max_age_s=MAX_AGE_S, transport=None, standing_max_s=STANDING_MAX_S):
    """AsyncJev over the synthetic story at `hz` in real time (hz 0: no pacing), one Memory throughout."""
    jev, memory, wall = AsyncJev(transport, max_age_s, standing_max_s=standing_max_s), Memory(), []
    differs, names = Counter(), []
    states = story_loop(ticks, hz or 10)  # hz 0 runs the 10 Hz story unpaced
    start = time.perf_counter()
    for i, s in enumerate(states):
        if hz:
            time.sleep(max(0.0, start + i / hz - time.perf_counter()))
        shadow = copy.deepcopy(memory)  # what the scripted brain would have said from the same memory
        t0 = time.perf_counter()
        got = jev(s, memory)
        wall.append((time.perf_counter() - t0) * 1000)
        names.append(name_of(got))
        if jev.stats.trace[-1][1] in ("jev", "standing"):
            scripted = name_of(brain.decide(s, shadow))
            if scripted != name_of(got):
                differs[f"{scripted}->{name_of(got)}"] += 1
    baseline, m = [], Memory()
    for s in states:  # the scripted brain alone over the same States, for the flapping comparison
        baseline.append(name_of(brain.decide(s, m)))
    st, lat = jev.stats, jev.stats.latency_ms
    decided = st.sources["jev"] + st.sources["standing"]
    choices = decided + st.sources["scripted"]  # ticks the gate let through
    endpoint = getattr(jev.transport, "endpoint", None)
    return {
        "endpoint": {"url": endpoint.url, "model": jev.model, "bearer_sent": jev.transport.bearer} if endpoint else None,
        "ticks": ticks, "hz": hz, "max_age_s": max_age_s, "standing_max_s": standing_max_s,
        "decided_by": dict(st.sources),
        "jev_share_of_ticks": round(st.jev_share, 3),        # fresh + standing
        "standing_share_of_ticks": round(st.standing_share, 3),
        "jev_share_of_choices": round(decided / choices, 3) if choices else None,
        "steered_share_of_ticks": round(sum(differs.values()) / ticks, 3),  # Jev-decided ticks whose intent differs from the scripted one
        "jev_chose": dict(st.chosen.most_common()),
        "jev_differs_from_scripted": dict(differs.most_common()),  # scripted -> jev
        "intent_switches": _switches(names), "scripted_alone_switches": _switches(baseline),
        "standing_expired": dict(st.expired),
        "requests": st.calls, "answered": len(lat), "fallbacks": dict(st.fallbacks), "drops": dict(st.drops),
        "roundtrip_ms": _spread(lat, 50, 95), "first_roundtrip_ms": round(lat[0]) if lat else None,
        "age_at_adoption_ms": _spread(st.age_ms, 50, 95),
        "tick_wall_ms": _spread(wall, 50, 95),  # what decide_jev cost the loop: it never waits
        "cost_usd_answered": round(st.cost, 6),
    }


def main(argv=None):
    p = argparse.ArgumentParser(description="Measure Jev from this machine: latency, fallback and drop rates, cost.")
    p.add_argument("-n", type=int, default=60, help="calls (blocking) or ticks (--async)")
    p.add_argument("--timeout", type=float, default=TIMEOUT_S, help="blocking per-call budget in seconds")
    p.add_argument("--hz", type=float, default=0.0, help="pace calls or ticks like the live loop (0 = back to back)")
    p.add_argument("--async", dest="nonblocking", action="store_true", help="measure AsyncJev over the synthetic story")
    p.add_argument("--max-age", type=float, default=MAX_AGE_S, help="--async: drop answers older than this (seconds)")
    p.add_argument("--standing-max", type=float, default=STANDING_MAX_S,
                   help="--async: a standing answer expires this long after its State (0 turns standing off)")
    a = p.parse_args(argv)
    result = (bench_async(a.n, a.hz, a.max_age, standing_max_s=a.standing_max) if a.nonblocking
              else bench(a.n, a.timeout, a.hz))
    print(json.dumps(result, indent=1))


if __name__ == "__main__":
    main()

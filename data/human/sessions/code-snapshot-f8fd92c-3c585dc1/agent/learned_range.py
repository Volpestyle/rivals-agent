"""Typed-intent consumer only. No pad, capture, networking or loop wiring.

Root owns integration. The loop must retain its independent frame/range/focus,
decision-age, controller and watchdog guards; this object cannot certify them.
"""
from collections import Counter, deque
from copy import deepcopy

from agent import brain, jev
from agent.intents import Disengage, Idle, Intent
from agent.human_demos import DemoError
from agent.state import State
from policy.range_policy import ACTIONS, Snapshot, feature_row, finite, load_checkpoint, window


class LearnedRangeBrain:
    source = "range_refusal"

    def __init__(self, policy):
        self.policy = policy
        self.history = deque(maxlen=policy.spec.steps)
        self.stats = Counter()
        self.last = None
        self.last_t = None
        self.reason = "warming_up"

    @classmethod
    def from_checkpoint(cls, path, *, expected_sha256, expected_identity, expected_runtime=None,
                        deployment_binding=None, device="cpu", offline=False):
        return cls(load_checkpoint(path, expected_sha256=expected_sha256,
                                   expected_identity=expected_identity, expected_runtime=expected_runtime,
                                   deployment_binding=deployment_binding, device=device, offline=offline))

    def _done(self, state, intent, source, reason, probabilities=None):
        self.source, self.reason = source, reason
        self.stats[source] += 1
        self.last = {"t": state.t, "source": source, "reason": reason,
                     "probabilities": probabilities, "intent": type(intent).__name__,
                     "target": getattr(getattr(intent, "target", None), "track", None)}
        return intent

    def _refuse(self, state, memory, reason, probabilities=None):
        return self._done(state, brain.commit(memory, Idle()), "range_refusal", reason, probabilities)

    def __call__(self, state: State, memory: brain.Memory) -> Intent:
        # A repeated/backward state must not extend a previous learned action.
        if not finite(state.t) or (self.last_t is not None and state.t <= self.last_t):
            self.history.clear()
            return self._refuse(state, memory, "nonmonotonic_state")
        if self.last_t is not None and abs(state.t - self.last_t - self.policy.spec.period_s) > self.policy.spec.tolerance_s:
            self.history.clear()
        self.last_t = state.t
        try:
            feature_row(Snapshot(state, None, state.t))
        except (DemoError, TypeError, ValueError, AttributeError):
            self.history.clear()
            return self._refuse(state, memory, "malformed_state")

        # Detector failure is not target coasting. Do not stamp an old offensive
        # gate intent with this frame's fresh timestamp; require new history.
        if state.detections is None:
            self.history.clear()
            return self._refuse(state, memory, "unknown_detector")

        early, target = brain.gate(state, memory)
        # Snapshot mutable State now, so callers cannot rewrite preceding history.
        self.history.append(deepcopy(Snapshot(state, target, state.t)))
        # Valid current-state retreat needs no learned history and never attacks.
        # Coasting/holds, however, can sustain a playing offensive primitive.
        if isinstance(early, Disengage):
            return self._done(state, early, "range_gate", "scripted_gate")
        if len(self.history) < self.policy.spec.steps:
            return self._refuse(state, memory, "warming_up")
        try:
            window(tuple(self.history), state.t, self.policy.spec)
        except (DemoError, TypeError, ValueError, AttributeError):
            self.history.clear()
            return self._refuse(state, memory, "invalid_history")
        if early is not None:
            return self._done(state, early, "range_gate", "scripted_gate")
        try:
            probabilities = self.policy.probabilities(tuple(self.history), state.t)
            if (len(probabilities) != len(ACTIONS) or
                    not all(finite(p) and 0 <= p <= 1 for p in probabilities) or
                    abs(sum(probabilities) - 1) > 1e-5):
                return self._refuse(state, memory, "malformed_prediction")
        except (DemoError, RuntimeError, ValueError, TypeError):
            return self._refuse(state, memory, "inference_failed")
        index = max(range(len(ACTIONS)), key=lambda i: probabilities[i])
        name = ACTIONS[index]
        if probabilities[index] < self.policy.spec.confidence:
            return self._refuse(state, memory, "uncertain", probabilities)
        if not jev.legal(name, state, target):
            return self._refuse(state, memory, "illegal", probabilities)
        intent = jev.adopt(state, memory, target, name, target if name == "engage" else None)
        return self._done(state, intent, "range_learned", name, probabilities)

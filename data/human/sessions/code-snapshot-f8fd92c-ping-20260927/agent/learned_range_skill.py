"""Learned Web-Cluster event requests; scripted target selection/retreat only.

No input devices or loop wiring. A fresh instance and Memory belong to each
episode. Root retains independent range/focus/age/watchdog guards.
"""
from collections import Counter, deque
from copy import deepcopy

from agent import brain
from agent.human_demos import DemoError
from agent.intents import Disengage, Idle, Intent, RangeSkill, RangeSkillResources
from agent.state import State
from policy.range_skill_policy import OUTCOMES, Snapshot, event_window, feature_row, finite, load_checkpoint


class LearnedRangeSkillBrain:
    source = "range_skill_refusal"

    def __init__(self, policy):
        policy.spec.validate()
        self.policy = policy
        self.history = deque(maxlen=policy.spec.steps)
        self.stats = Counter()
        self.last = None
        self.last_t = None
        self.decision_id = 0
        self.reason = "warming_up"

    @classmethod
    def from_checkpoint(cls, path, *, expected_sha256, expected_identity, expected_runtime=None,
                        deployment_binding=None, device="cpu", offline=False):
        return cls(load_checkpoint(path, expected_sha256=expected_sha256, expected_identity=expected_identity,
                                   expected_runtime=expected_runtime, deployment_binding=deployment_binding,
                                   device=device, offline=offline))

    def _done(self, state, memory, intent, source, reason, probabilities=None):
        self.source, self.reason = source, reason
        self.stats[source] += 1
        self.last = {"t": state.t, "decision_id": self.decision_id, "source": source, "reason": reason,
                     "probabilities": list(probabilities) if probabilities is not None else None,
                     "intent": type(intent).__name__, "target": getattr(getattr(intent, "target", None), "track", None),
                     "web_cluster_request": getattr(intent, "web_cluster_request", None),
                     "valid_until": getattr(intent, "valid_until", None),
                     "resources": {"webs": intent.resources.webs, "observed_t": intent.resources.observed_t}
                                  if isinstance(intent, RangeSkill) else None,
                     "selector_source": "scripted_brain_gate", "movement_source": "scripted_controller"}
        return brain.commit(memory, intent)

    def _refuse(self, state, memory, reason, probabilities=None):
        return self._done(state, memory, Idle(), "range_skill_refusal", reason, probabilities)

    def __call__(self, state: State, memory: brain.Memory) -> Intent:
        self.decision_id += 1  # never reuse a consumed/rejected ID during this instance's episode
        if not finite(state.t) or (self.last_t is not None and state.t <= self.last_t):
            self.history.clear()
            return self._refuse(state, memory, "nonmonotonic_state")
        if self.last_t is not None and abs(state.t - self.last_t - self.policy.spec.period_s) > self.policy.spec.tolerance_s + 1e-9:
            self.history.clear()
        self.last_t = state.t
        try:
            feature_row(Snapshot(state, None, state.t))
        except (DemoError, TypeError, ValueError, AttributeError):
            self.history.clear()
            return self._refuse(state, memory, "malformed_state")
        if state.detections is None:
            self.history.clear()
            return self._refuse(state, memory, "unknown_detector")

        # Keep the reviewed selector's actual history. Never adopt a held Engage,
        # Combo, Search or coasting intent as freshly authorized offense.
        try:
            early, target = brain.gate(state, memory)
            current_target = (target is not None and target in state.detections and type(target.track) is int
                              and target.track not in state.coasting)
        except (TypeError, ValueError, AttributeError):
            self.history.clear()
            return self._refuse(state, memory, "malformed_target_state")
        # A valid observed empty frame or a selector still acquiring a target is
        # causal gameplay, not detector failure. Keep its actual selector output;
        # a later acquisition must not retrospectively populate these targets.
        self.history.append(deepcopy(Snapshot(state, target, state.t)))
        if isinstance(early, Disengage):
            return self._done(state, memory, early, "range_skill_gate", "scripted_low_hp_retreat")
        if not current_target:
            return self._refuse(state, memory, "target_unobserved")
        if len(self.history) != self.policy.spec.steps:
            return self._refuse(state, memory, "warming_up")
        try:
            event_window(tuple(self.history), state.t, self.policy.spec, sampling="live")
        except (DemoError, TypeError, ValueError, AttributeError):
            self.history.clear()
            return self._refuse(state, memory, "invalid_history")
        try:
            probabilities = self.policy.probabilities(tuple(self.history), state.t, sampling="live")
            if (len(probabilities) != len(OUTCOMES) or not all(finite(p) and 0 <= p <= 1 for p in probabilities)
                    or abs(sum(probabilities) - 1) > 1e-5):
                return self._refuse(state, memory, "malformed_prediction")
        except (DemoError, RuntimeError, ValueError, TypeError):
            return self._refuse(state, memory, "inference_failed")
        index = max(range(len(OUTCOMES)), key=probabilities.__getitem__)
        if probabilities[index] < self.policy.spec.confidence:
            return self._refuse(state, memory, "low_confidence", probabilities)
        request = OUTCOMES[index]
        # Controller owns acceptance, aim, resource legality and pulse duration.
        # Unknown/zero resources cannot generate a scripted replacement attack.
        intent = RangeSkill(deepcopy(target), request, self.decision_id, state.t + self.policy.spec.period_s,
                            RangeSkillResources(state.webs, state.t))
        brain.track_mode(state, memory, target)
        return self._done(state, memory, intent, "range_skill_model", "model_event", probabilities)

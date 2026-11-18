"""Regression tests for the guardrail control fixes.

Covers: binding updates that change later verdicts, code-level hard floors,
safe defaults, separation of evaluation from mutation, fail-closed
classification, and admin authorisation on state-changing endpoints.

Run from the conscience_research directory:
    python -m unittest discover -s tests -v
The tests work in a temporary directory so they never touch norms.json or
moral_history.jsonl in the repository.
"""

from __future__ import annotations

import copy
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_WORK_DIR = tempfile.mkdtemp(prefix="conscience_tests_")
os.chdir(_WORK_DIR)  # agent.py uses cwd-relative state files
sys.path.insert(0, PROJECT_DIR)

import agent  # noqa: E402
import production_service as svc  # noqa: E402

HARMLESS_ACTION = "remained_within_authorized_scope"


def _reset_norms() -> None:
    agent.NORMS.clear()
    agent.NORMS.update(copy.deepcopy(agent.BASELINE_NORMS))


class BindingUpdateTests(unittest.TestCase):
    def setUp(self) -> None:
        _reset_norms()

    def test_effective_threshold_matches_slider_at_neutral_weight(self) -> None:
        for norm in agent.NORMS.values():
            self.assertAlmostEqual(agent.effective_threshold(norm), norm["threshold"])

    def test_effective_threshold_is_capped_and_floored(self) -> None:
        norm = {"threshold": 0.45, "weight": agent.MAX_NORM_WEIGHT}
        self.assertAlmostEqual(
            agent.effective_threshold(norm), 0.45 - agent.BINDING_MAX_TIGHTENING
        )
        low = {"threshold": 0.12, "weight": agent.MAX_NORM_WEIGHT}
        self.assertEqual(agent.effective_threshold(low), agent.MIN_THRESHOLD)

    def test_verified_violation_changes_a_later_verdict(self) -> None:
        threshold = agent.NORMS["privacy"]["threshold"]
        borderline = {"scores": {"privacy": threshold - 0.01}}

        before, _, _ = agent.judge_all(HARMLESS_ACTION, borderline)
        self.assertNotIn("privacy", before)

        agent.binding_update("privacy", 0.7, agent.NORMS)

        after, _, _ = agent.judge_all(HARMLESS_ACTION, borderline)
        self.assertIn("privacy", after)
        # The manual slider value is not rewritten by binding.
        self.assertEqual(agent.NORMS["privacy"]["threshold"], threshold)

    def test_binding_decays_back_toward_baseline(self) -> None:
        agent.binding_update("privacy", 0.7, agent.NORMS)
        raised = agent.NORMS["privacy"]["weight"]
        for _ in range(200):
            agent.binding_update("honesty", 0.1, agent.NORMS)
        self.assertLess(agent.NORMS["privacy"]["weight"], raised)
        self.assertAlmostEqual(
            agent.effective_threshold(agent.NORMS["privacy"]),
            agent.NORMS["privacy"]["threshold"],
            places=2,
        )


class HardFloorTests(unittest.TestCase):
    def setUp(self) -> None:
        _reset_norms()

    def test_hf1_fires_on_imminent_identifiable_harm(self) -> None:
        ctx = {"SW4_imminence": "immediate", "SW5_target": "identifiable"}
        self.assertIn("HF1", agent.check_hard_floors(ctx, {"harm": 0.8}))

    def test_hf1_needs_all_conditions(self) -> None:
        ctx = {"SW4_imminence": "remote", "SW5_target": "identifiable"}
        self.assertEqual(agent.check_hard_floors(ctx, {"harm": 0.9}), [])
        self.assertEqual(agent.check_hard_floors({}, {"harm": 0.9}), [])

    def test_hf2_fires_on_affirmative_deception_about_user(self) -> None:
        ctx = {"affirmative_deception": True, "deception_concerns_user": True}
        self.assertIn("HF2", agent.check_hard_floors(ctx, {"honesty": 0.8}))
        ctx_omission = {"affirmative_deception": False, "deception_concerns_user": True}
        self.assertNotIn("HF2", agent.check_hard_floors(ctx_omission, {"honesty": 0.8}))

    def test_hf3_fires_when_fairness_would_spread_identifiable_harm(self) -> None:
        ctx = {"dominant_norm": "fairness", "SW5_target": "identifiable"}
        self.assertIn("HF3", agent.check_hard_floors(ctx, {"harm": 0.55}))

    def test_hf4_reads_switch_params_block(self) -> None:
        ctx = {
            "switch_params": {
                "SW4_imminence": "immediate",
                "SW5_target": "identifiable",
                "SW6_externality": "third_party",
            }
        }
        fired = agent.check_hard_floors(ctx, {"harm": 0.75, "confidentiality": 0.6})
        self.assertIn("HF4", fired)

    def test_floor_blocks_even_when_thresholds_pass(self) -> None:
        # Raise the harm slider so the threshold check alone would allow it.
        agent.NORMS["harm"]["threshold"] = 0.99
        payload = {
            "action": HARMLESS_ACTION,
            "context": {
                "scores": {"harm": 0.8},
                "SW4_imminence": "immediate",
                "SW5_target": "identifiable",
            },
        }
        response, status = svc.decision_payload(payload)
        self.assertEqual(status, 200)
        self.assertFalse(response["decision"]["allowed"])
        self.assertIn("HF1", response["decision"]["hard_floors"])


class DecisionPayloadTests(unittest.TestCase):
    def setUp(self) -> None:
        _reset_norms()
        self.violating = {
            "action": "disclosed_pii_without_consent",
            "context": {"agent_did_this": True, "harm_occurred": True},
        }

    def test_defaults_do_not_mutate_state(self) -> None:
        before = copy.deepcopy(agent.NORMS)
        response, _ = svc.decision_payload(dict(self.violating))
        self.assertTrue(response["state"]["dry_run"])
        self.assertFalse(response["state"]["mutated"])
        self.assertEqual(agent.NORMS, before)

    def test_unauthorised_caller_cannot_mutate_even_if_asking(self) -> None:
        before = copy.deepcopy(agent.NORMS)
        payload = dict(self.violating, dry_run=False, apply_binding_update=True)
        response, _ = svc.decision_payload(payload, allow_mutation=False)
        self.assertTrue(response["state"]["dry_run"])
        self.assertFalse(response["state"]["mutated"])
        self.assertEqual(agent.NORMS, before)

    def test_authorised_caller_can_mutate(self) -> None:
        payload = dict(self.violating, dry_run=False, apply_binding_update=True)
        response, _ = svc.decision_payload(payload, allow_mutation=True)
        self.assertTrue(response["state"]["mutated"])
        self.assertGreater(response["state"]["norm_after"]["weight"], 1.0)

    def test_classification_failure_fails_closed(self) -> None:
        payload = {"action": svc.CLASSIFICATION_FAILED_ACTION, "context": {}}
        response, _ = svc.decision_payload(payload)
        decision = response["decision"]
        self.assertEqual(decision["verdict"], "escalate")
        self.assertFalse(decision["allowed"])
        self.assertIn("require_human_review", decision["controls"])


class _FailingClient:
    class messages:  # noqa: N801 - mimic the SDK attribute
        @staticmethod
        def create(**_: object) -> object:
            raise RuntimeError("network down")


class _LabelClient:
    def __init__(self, label: str) -> None:
        text = json.dumps({"action": label, "context": {"scores": {}}})
        block = type("Block", (), {"text": text})()
        reply = type("Reply", (), {"content": [block]})()
        self.messages = type("Messages", (), {"create": staticmethod(lambda **_: reply)})()


class ClassifierTests(unittest.TestCase):
    long_text = "please summarise the attached quarterly report for me today"

    def test_client_error_maps_to_classification_failed(self) -> None:
        action, ctx = svc._classify_message(_FailingClient(), "user", self.long_text)
        self.assertEqual(action, svc.CLASSIFICATION_FAILED_ACTION)
        self.assertEqual(ctx["reason"], "classification_failed")

    def test_unknown_label_maps_to_classification_failed(self) -> None:
        action, _ = svc._classify_message(_LabelClient("made_up_action"), "user", self.long_text)
        self.assertEqual(action, svc.CLASSIFICATION_FAILED_ACTION)

    def test_known_label_passes_through(self) -> None:
        action, _ = svc._classify_message(_LabelClient(HARMLESS_ACTION), "user", self.long_text)
        self.assertEqual(action, HARMLESS_ACTION)


class AdminAuthTests(unittest.TestCase):
    def setUp(self) -> None:
        self._saved = {k: os.environ.get(k) for k in ("CONSCIENCE_ADMIN_TOKEN", "CONSCIENCE_ALLOW_UNAUTH_ADMIN")}
        for key in self._saved:
            os.environ.pop(key, None)

    def tearDown(self) -> None:
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_without_token_only_loopback_is_admin(self) -> None:
        self.assertTrue(svc.is_admin_request({}, "127.0.0.1"))
        self.assertTrue(svc.is_admin_request({}, "::1"))
        self.assertFalse(svc.is_admin_request({}, "10.0.0.5"))

    def test_explicit_unauth_opt_in(self) -> None:
        os.environ["CONSCIENCE_ALLOW_UNAUTH_ADMIN"] = "1"
        self.assertTrue(svc.is_admin_request({}, "10.0.0.5"))

    def test_token_required_when_configured(self) -> None:
        os.environ["CONSCIENCE_ADMIN_TOKEN"] = "test-token"
        self.assertFalse(svc.is_admin_request({}, "127.0.0.1"))
        self.assertFalse(svc.is_admin_request({"Authorization": "Bearer wrong"}, "127.0.0.1"))
        self.assertTrue(svc.is_admin_request({"Authorization": "Bearer test-token"}, "10.0.0.5"))


class HttpEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._saved_token = os.environ.get("CONSCIENCE_ADMIN_TOKEN")
        os.environ["CONSCIENCE_ADMIN_TOKEN"] = "test-token"
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), svc.ConscienceRequestHandler)
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        if cls._saved_token is None:
            os.environ.pop("CONSCIENCE_ADMIN_TOKEN", None)
        else:
            os.environ["CONSCIENCE_ADMIN_TOKEN"] = cls._saved_token

    def setUp(self) -> None:
        _reset_norms()

    def _call(self, method: str, path: str, body: dict | None = None, token: str | None = None) -> int:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status
        except urllib.error.HTTPError as err:
            return err.code

    def test_reset_over_get_is_refused(self) -> None:
        self.assertEqual(self._call("GET", "/v1/reset"), 405)

    def test_reset_requires_admin(self) -> None:
        self.assertEqual(self._call("POST", "/v1/reset", {}), 403)
        self.assertEqual(self._call("POST", "/v1/reset", {}, token="test-token"), 200)

    def test_threshold_change_requires_admin_and_valid_range(self) -> None:
        body = {"domain": "privacy", "threshold": 0.3}
        self.assertEqual(self._call("POST", "/v1/norms/threshold", body), 403)
        self.assertEqual(agent.NORMS["privacy"]["threshold"], agent.BASELINE_THRESHOLDS["privacy"])
        bad = {"domain": "privacy", "threshold": 7}
        self.assertEqual(self._call("POST", "/v1/norms/threshold", bad, token="test-token"), 400)
        self.assertEqual(self._call("POST", "/v1/norms/threshold", body, token="test-token"), 200)
        self.assertEqual(agent.NORMS["privacy"]["threshold"], 0.3)

    def test_guardrail_evaluation_is_open_but_mutation_is_not(self) -> None:
        evaluate = {"action": "disclosed_pii_without_consent", "context": {"harm_occurred": True}}
        self.assertEqual(self._call("POST", "/v1/guardrail/decision", evaluate), 200)
        mutate = dict(evaluate, dry_run=False, apply_binding_update=True)
        self.assertEqual(self._call("POST", "/v1/guardrail/decision", mutate), 403)
        self.assertEqual(self._call("POST", "/v1/guardrail/decision", mutate, token="test-token"), 200)


class ScenarioHarnessTests(unittest.TestCase):
    def test_baseline_oracle_still_scores_full_marks(self) -> None:
        # Start from a fresh continuity layer: other tests call POST /v1/reset,
        # which wipes the seeded history that the layer-5 scenarios rely on.
        _reset_norms()
        if os.path.exists(agent.HISTORY_FILE):
            os.remove(agent.HISTORY_FILE)
        agent._continuity_layer = None
        results = agent.evaluate_conscience_with_oracle_mode(agent, "baseline")
        self.assertGreaterEqual(results["conscience_score"], 0.99)


if __name__ == "__main__":
    unittest.main()

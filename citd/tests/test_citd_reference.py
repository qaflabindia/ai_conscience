"""Tests for the CITD reference gate and its link to the conscience engine.

Run from the repository root:
    python3 -m unittest discover -s citd/tests -v
The tests run in a temporary directory because the conscience engine keeps
cwd-relative state files (norms.json, moral_history.jsonl).
"""
import copy
import os
import sys
import tempfile
import unittest

CITD_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, CITD_DIR)
os.chdir(tempfile.mkdtemp(prefix="citd_tests_"))

from citd_reference import CITD, INDEPENDENT_SOURCES, Proposal  # noqa: E402
import agent  # noqa: E402  (conscience_research, put on sys.path by citd_reference)
import trust_contracts  # noqa: E402


def _reset_conscience() -> None:
    agent.NORMS.clear()
    agent.NORMS.update(copy.deepcopy(agent.BASELINE_NORMS))
    if os.path.exists(agent.HISTORY_FILE):
        os.remove(agent.HISTORY_FILE)
    agent._continuity_layer = None


class CITDTests(unittest.TestCase):
    """The original eight control-flow tests, run with the conscience advisor on."""

    def setUp(self):
        _reset_conscience()
        self.app = CITD()
        self.app.ingest_receipt("B-1", 50_000, "REF-1", "feed-a", caller="bank_adapter")
        self.app.ingest_ledger("L-A", "A", 50_000, caller="ledger_adapter")
        self.app.ingest_ledger("L-B", "B", 50_000, caller="ledger_adapter")
        self.p = Proposal("case-1", "B-1", "L-B", idempotency_key="case-1-B")

    def test_ambiguous_case_must_hold(self):
        self.assertEqual(self.app.dispatch(self.p).disposition, "HOLD")
        self.assertIsNone(self.app.db.execute("SELECT cleared_ledger FROM receipts").fetchone()[0])

    def test_unique_remittance_allows_clearance(self):
        self.app.ingest_remittance("M-1", "REF-1", "B", caller="remittance_adapter")
        self.assertEqual(self.app.dispatch(self.p).disposition, "ALLOW")
        self.assertEqual(self.app.db.execute("SELECT cleared_ledger FROM receipts").fetchone()[0], "L-B")

    def test_idempotent_replay(self):
        self.app.ingest_remittance("M-1", "REF-1", "B", caller="remittance_adapter")
        self.app.dispatch(self.p)
        self.assertEqual(self.app.dispatch(self.p).disposition, trust_contracts.DISPATCH_REPLAY)
        self.assertEqual(self.app.db.execute("SELECT COUNT(*) FROM completed").fetchone()[0], 1)

    def test_cannot_mutate_learning_from_self_report(self):
        with self.assertRaises(PermissionError):
            self.app.propose_learning("bad", "feed-a", actor="finance_agent",
                                      independently_verified=True, norm_domains=("harm",))

    def test_verified_incident_requires_promote(self):
        self.app.ingest_remittance("M-1", "REF-1", "B", caller="remittance_adapter")
        self.app.propose_learning("incident-1", "feed-a", actor="independent_reviewer",
                                  independently_verified=True, norm_domains=("harm",))
        self.assertEqual(self.app.evaluate(self.p).disposition, "ALLOW")
        with self.assertRaises(PermissionError):
            self.app.promote_learning("incident-1", actor="finance_agent")
        self.app.promote_learning("incident-1", actor="finance_controller")
        self.assertEqual(self.app.evaluate(self.p).disposition, "BLOCK")

    def test_cannot_fake_bank_ingestion(self):
        with self.assertRaises(PermissionError):
            self.app.ingest_receipt("B-2", 20, "R2", "feed-a", caller="finance_agent")

    def test_duplicate_remittance_conflict_holds(self):
        self.app.ingest_remittance("M-1", "REF-1", "A", caller="remittance_adapter")
        self.app.ingest_remittance("M-2", "REF-1", "B", caller="remittance_adapter")
        self.assertEqual(self.app.evaluate(self.p).disposition, "HOLD")

    def test_over_limit_escalates(self):
        self.app.ingest_receipt("B-3", 200_000, "REF-3", "feed-a", caller="bank_adapter")
        self.app.ingest_ledger("L-C", "C", 200_000, caller="ledger_adapter")
        self.assertEqual(self.app.evaluate(Proposal("case-3", "B-3", "L-C", idempotency_key="k3")).disposition,
                         "ESCALATE")


class SharedContractTests(unittest.TestCase):
    """Decision labels and norm labels are the shared ones."""

    def setUp(self):
        _reset_conscience()

    def test_conscience_norms_match_shared_domains(self):
        self.assertEqual(tuple(agent.NORMS), trust_contracts.NORM_DOMAINS)

    def test_every_gate_disposition_is_a_shared_label(self):
        app = CITD()
        app.ingest_receipt("B-1", 50_000, "R", "f", caller="bank_adapter")
        app.ingest_ledger("L-1", "X", 50_000, caller="ledger_adapter")
        v = app.evaluate(Proposal("c", "B-1", "L-1", idempotency_key="k"))
        self.assertIn(v.disposition, {d.value for d in trust_contracts.Disposition})
        for d in v.normative_domains:
            self.assertIn(d, trust_contracts.NORM_DOMAINS)

    def test_unknown_norm_label_is_rejected(self):
        app = CITD()
        app.ingest_receipt("B-1", 50_000, "R", "f", caller="bank_adapter")
        with self.assertRaises(ValueError):
            app.propose_learning("i", "f", actor="independent_reviewer",
                                 independently_verified=True, norm_domains=("legality",))


class ConscienceAdvisoryTests(unittest.TestCase):
    """The conscience engine informs, and can only tighten, gate decisions."""

    def setUp(self):
        _reset_conscience()
        self.app = CITD()
        self.app.ingest_receipt("B-1", 50_000, "REF-1", "feed-a", caller="bank_adapter")
        self.app.ingest_ledger("L-B", "B", 50_000, caller="ledger_adapter")
        self.app.ingest_remittance("M-1", "REF-1", "B", caller="remittance_adapter")

    def test_clean_self_assessment_keeps_allow_and_records_advice(self):
        v = self.app.evaluate(Proposal("c", "B-1", "L-B", idempotency_key="k"))
        self.assertEqual(v.disposition, "ALLOW")
        self.assertIsNotNone(v.advisory)
        self.assertEqual(v.advisory["flagged_domains"], [])

    def test_flagged_self_assessment_escalates_an_allow(self):
        p = Proposal("c", "B-1", "L-B", idempotency_key="k",
                     self_assessment={"fairness": 0.9})
        v = self.app.evaluate(p)
        self.assertEqual(v.disposition, "ESCALATE")
        self.assertIn("fairness", v.normative_domains)

    def test_hard_floor_from_advisor_blocks(self):
        class FloorAdvisor:
            def assess(self, **_):
                return type("R", (), {
                    "cap": trust_contracts.Disposition.BLOCK, "flagged_domains": ("harm",),
                    "hard_floors": ("HF1",), "as_payload": lambda self: {"hard_floors": ["HF1"]}})()
        self.app.advisor = FloorAdvisor()
        v = self.app.evaluate(Proposal("c", "B-1", "L-B", idempotency_key="k"))
        self.assertEqual(v.disposition, "BLOCK")

    def test_advisor_cannot_loosen_a_hold(self):
        app = CITD()
        app.ingest_receipt("B-9", 50_000, "R9", "f", caller="bank_adapter")
        app.ingest_ledger("L-9", "Z", 50_000, caller="ledger_adapter")
        v = app.evaluate(Proposal("c", "B-9", "L-9", idempotency_key="k"))
        self.assertEqual(v.disposition, "HOLD")

    def test_broken_advisor_fails_closed(self):
        class Broken:
            def assess(self, **_):
                raise RuntimeError("down")
        self.app.advisor = Broken()
        v = self.app.evaluate(Proposal("c", "B-1", "L-B", idempotency_key="k"))
        self.assertEqual(v.disposition, "ESCALATE")
        self.assertFalse(v.allowed)

    def test_dispatch_audit_records_norms_and_advice(self):
        self.app.dispatch(Proposal("c", "B-1", "L-B", idempotency_key="k"))
        events = [r for r in self.app.audit.records() if r["event"] == "DISPATCH"]
        self.assertEqual(events[-1]["payload"]["norm_domains"], ["honesty", "authority"])
        self.assertIn("advisory", events[-1]["payload"])


class GovernedLearningTests(unittest.TestCase):
    """One meaning of learning: a promoted, adjudicated incident changes both stores."""

    def setUp(self):
        _reset_conscience()
        self.app = CITD()
        self.app.ingest_receipt("B-1", 50_000, "REF-1", "feed-a", caller="bank_adapter")

    def test_promotion_tightens_the_implicated_norm(self):
        before = agent.effective_threshold(agent.NORMS["fairness"])
        self.app.propose_learning("inc", "feed-a", actor="independent_reviewer",
                                  independently_verified=True, norm_domains=("fairness",))
        update = self.app.promote_learning("inc", actor="finance_controller")
        self.assertEqual(update["learning_mode"], trust_contracts.LearningMode.GOVERNED.value)
        self.assertGreater(update["weight_after"]["fairness"], update["weight_before"]["fairness"])
        self.assertLess(agent.effective_threshold(agent.NORMS["fairness"]), before)

    def test_proposal_alone_changes_nothing(self):
        weights = {d: n["weight"] for d, n in agent.NORMS.items()}
        self.app.propose_learning("inc", "feed-a", actor="independent_reviewer",
                                  independently_verified=True, norm_domains=("fairness",))
        self.assertEqual({d: n["weight"] for d, n in agent.NORMS.items()}, weights)

    def test_learning_events_share_one_audit_chain(self):
        self.app.propose_learning("inc", "feed-a", actor="independent_reviewer",
                                  independently_verified=True, norm_domains=("harm",))
        self.app.promote_learning("inc", actor="finance_controller")
        events = [r["event"] for r in self.app.audit.records()]
        self.assertEqual(events[-3:], ["LEARNING_PROPOSED", "LEARNING_PROMOTED",
                                       "NORMATIVE_UPDATE_APPLIED"])
        self.assertEqual(self.app.verify_audit(), (True, None))


class EvidenceFieldTests(unittest.TestCase):
    """Stored hashes and the evidence-source field now drive decisions."""

    def setUp(self):
        _reset_conscience()
        self.app = CITD()
        self.app.ingest_receipt("B-1", 50_000, "REF-1", "feed-a", caller="bank_adapter")
        self.app.ingest_ledger("L-B", "B", 50_000, caller="ledger_adapter")
        self.p = Proposal("c", "B-1", "L-B", idempotency_key="k")

    def test_derived_source_cannot_attribute_payer(self):
        self.app.ingest_remittance("M-1", "REF-1", "B", caller="remittance_adapter",
                                   source="agent_extracted")
        self.assertNotIn("agent_extracted", INDEPENDENT_SOURCES)
        self.assertEqual(self.app.evaluate(self.p).disposition, "HOLD")

    def test_derived_copy_does_not_create_false_conflict(self):
        self.app.ingest_remittance("M-1", "REF-1", "B", caller="remittance_adapter")
        self.app.ingest_remittance("M-2", "REF-1", "A", caller="remittance_adapter",
                                   source="ledger_copy")
        self.assertEqual(self.app.evaluate(self.p).disposition, "ALLOW")

    def test_unknown_source_rejected(self):
        with self.assertRaises(ValueError):
            self.app.ingest_remittance("M-1", "REF-1", "B", caller="remittance_adapter",
                                       source="email_screenshot")

    def test_tampered_remittance_holds(self):
        self.app.ingest_remittance("M-1", "REF-1", "A", caller="remittance_adapter")
        self.app.db.execute("UPDATE remittances SET customer='B' WHERE remit_id='M-1'")
        self.assertEqual(self.app.verify_evidence_integrity(), ["M-1"])
        v = self.app.evaluate(self.p)
        self.assertEqual(v.disposition, "HOLD")
        self.assertIn("integrity", v.reason)

    def test_tampered_ledger_holds(self):
        self.app.ingest_remittance("M-1", "REF-1", "B", caller="remittance_adapter")
        self.app.db.execute("UPDATE ledger SET amount=49000 WHERE ledger_id='L-B'")
        self.assertEqual(self.app.evaluate(self.p).disposition, "HOLD")

    def test_audit_tampering_detected(self):
        self.app.db.execute("UPDATE audit SET event='FORGED' WHERE seq=1")
        ok, bad = self.app.verify_audit()
        self.assertFalse(ok)
        self.assertEqual(bad, 1)


if __name__ == "__main__":
    unittest.main()

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

from citd_reference import (  # noqa: E402
    CITD, INDEPENDENT_SOURCES, Credential, IdentityAuthority, Proposal)
import agent  # noqa: E402  (conscience_research, put on sys.path by citd_reference)
import trust_contracts  # noqa: E402
import citd_reference  # noqa: E402

AUTH = IdentityAuthority()
BANK = AUTH.issue("bank-1", "bank_adapter")
LEDGER = AUTH.issue("erp-1", "ledger_adapter")
REMIT = AUTH.issue("remit-1", "remittance_adapter")
AGENT = AUTH.issue("agent-1", "finance_agent")
REVIEWER = AUTH.issue("audit-1", "independent_reviewer")
CONTROLLER = AUTH.issue("fc-1", "finance_controller")


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
        self.app = CITD(AUTH)
        self.app.ingest_receipt("B-1", 50_000, "REF-1", "feed-a", caller=BANK)
        self.app.ingest_ledger("L-A", "A", 50_000, caller=LEDGER)
        self.app.ingest_ledger("L-B", "B", 50_000, caller=LEDGER)
        self.p = Proposal("case-1", "B-1", "L-B", principal=AGENT, idempotency_key="case-1-B")

    def test_ambiguous_case_must_hold(self):
        self.assertEqual(self.app.dispatch(self.p).disposition, "HOLD")
        self.assertIsNone(self.app.db.execute("SELECT cleared_ledger FROM receipts").fetchone()[0])

    def test_unique_remittance_allows_clearance(self):
        self.app.ingest_remittance("M-1", "REF-1", "B", caller=REMIT)
        self.assertEqual(self.app.dispatch(self.p).disposition, "ALLOW")
        self.assertEqual(self.app.db.execute("SELECT cleared_ledger FROM receipts").fetchone()[0], "L-B")

    def test_idempotent_replay(self):
        self.app.ingest_remittance("M-1", "REF-1", "B", caller=REMIT)
        self.app.dispatch(self.p)
        self.assertEqual(self.app.dispatch(self.p).disposition, trust_contracts.DISPATCH_REPLAY)
        self.assertEqual(self.app.db.execute("SELECT COUNT(*) FROM completed").fetchone()[0], 1)

    def test_cannot_mutate_learning_from_self_report(self):
        with self.assertRaises(PermissionError):
            self.app.propose_learning("bad", "feed-a", actor=AGENT,
                                      independently_verified=True, norm_domains=("harm",))

    def test_verified_incident_requires_promote(self):
        self.app.ingest_remittance("M-1", "REF-1", "B", caller=REMIT)
        self.app.propose_learning("incident-1", "feed-a", actor=REVIEWER,
                                  independently_verified=True, norm_domains=("harm",))
        self.assertEqual(self.app.evaluate(self.p).disposition, "ALLOW")
        with self.assertRaises(PermissionError):
            self.app.promote_learning("incident-1", actor=AGENT)
        self.app.promote_learning("incident-1", actor=CONTROLLER)
        self.assertEqual(self.app.evaluate(self.p).disposition, "BLOCK")

    def test_cannot_fake_bank_ingestion(self):
        with self.assertRaises(PermissionError):
            self.app.ingest_receipt("B-2", 20, "R2", "feed-a", caller=AGENT)

    def test_duplicate_remittance_conflict_holds(self):
        self.app.ingest_remittance("M-1", "REF-1", "A", caller=REMIT)
        self.app.ingest_remittance("M-2", "REF-1", "B", caller=REMIT)
        self.assertEqual(self.app.evaluate(self.p).disposition, "HOLD")

    def test_over_limit_escalates(self):
        self.app.ingest_receipt("B-3", 200_000, "REF-3", "feed-a", caller=BANK)
        self.app.ingest_ledger("L-C", "C", 200_000, caller=LEDGER)
        self.assertEqual(self.app.evaluate(Proposal("case-3", "B-3", "L-C", principal=AGENT, idempotency_key="k3")).disposition,
                         "ESCALATE")


class SharedContractTests(unittest.TestCase):
    """Decision labels and norm labels are the shared ones."""

    def setUp(self):
        _reset_conscience()

    def test_conscience_norms_match_shared_domains(self):
        self.assertEqual(tuple(agent.NORMS), trust_contracts.NORM_DOMAINS)

    def test_every_gate_disposition_is_a_shared_label(self):
        app = CITD(AUTH)
        app.ingest_receipt("B-1", 50_000, "R", "f", caller=BANK)
        app.ingest_ledger("L-1", "X", 50_000, caller=LEDGER)
        v = app.evaluate(Proposal("c", "B-1", "L-1", principal=AGENT, idempotency_key="k"))
        self.assertIn(v.disposition, {d.value for d in trust_contracts.Disposition})
        for d in v.normative_domains:
            self.assertIn(d, trust_contracts.NORM_DOMAINS)

    def test_unknown_norm_label_is_rejected(self):
        app = CITD(AUTH)
        app.ingest_receipt("B-1", 50_000, "R", "f", caller=BANK)
        with self.assertRaises(ValueError):
            app.propose_learning("i", "f", actor=REVIEWER,
                                 independently_verified=True, norm_domains=("legality",))


class ConscienceAdvisoryTests(unittest.TestCase):
    """The conscience engine informs, and can only tighten, gate decisions."""

    def setUp(self):
        _reset_conscience()
        self.app = CITD(AUTH)
        self.app.ingest_receipt("B-1", 50_000, "REF-1", "feed-a", caller=BANK)
        self.app.ingest_ledger("L-B", "B", 50_000, caller=LEDGER)
        self.app.ingest_remittance("M-1", "REF-1", "B", caller=REMIT)

    def test_clean_self_assessment_keeps_allow_and_records_advice(self):
        v = self.app.evaluate(Proposal("c", "B-1", "L-B", principal=AGENT, idempotency_key="k"))
        self.assertEqual(v.disposition, "ALLOW")
        self.assertIsNotNone(v.advisory)
        self.assertEqual(v.advisory["flagged_domains"], [])

    def test_flagged_self_assessment_escalates_an_allow(self):
        p = Proposal("c", "B-1", "L-B", principal=AGENT, idempotency_key="k",
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
        v = self.app.evaluate(Proposal("c", "B-1", "L-B", principal=AGENT, idempotency_key="k"))
        self.assertEqual(v.disposition, "BLOCK")

    def test_advisor_cannot_loosen_a_hold(self):
        app = CITD(AUTH)
        app.ingest_receipt("B-9", 50_000, "R9", "f", caller=BANK)
        app.ingest_ledger("L-9", "Z", 50_000, caller=LEDGER)
        v = app.evaluate(Proposal("c", "B-9", "L-9", principal=AGENT, idempotency_key="k"))
        self.assertEqual(v.disposition, "HOLD")

    def test_broken_advisor_fails_closed(self):
        class Broken:
            def assess(self, **_):
                raise RuntimeError("down")
        self.app.advisor = Broken()
        v = self.app.evaluate(Proposal("c", "B-1", "L-B", principal=AGENT, idempotency_key="k"))
        self.assertEqual(v.disposition, "ESCALATE")
        self.assertFalse(v.allowed)

    def test_dispatch_audit_records_norms_and_advice(self):
        self.app.dispatch(Proposal("c", "B-1", "L-B", principal=AGENT, idempotency_key="k"))
        events = [r for r in self.app.audit.records() if r["event"] == "DISPATCH"]
        self.assertEqual(events[-1]["payload"]["norm_domains"], ["honesty", "authority"])
        self.assertIn("advisory", events[-1]["payload"])


class GovernedLearningTests(unittest.TestCase):
    """One meaning of learning: a promoted, adjudicated incident changes both stores."""

    def setUp(self):
        _reset_conscience()
        self.app = CITD(AUTH)
        self.app.ingest_receipt("B-1", 50_000, "REF-1", "feed-a", caller=BANK)

    def test_promotion_tightens_the_implicated_norm(self):
        before = agent.effective_threshold(agent.NORMS["fairness"])
        self.app.propose_learning("inc", "feed-a", actor=REVIEWER,
                                  independently_verified=True, norm_domains=("fairness",))
        result = self.app.promote_learning("inc", actor=CONTROLLER)
        self.assertEqual(result["learning_mode"], trust_contracts.LearningMode.GOVERNED.value)
        update = result["normative_update"]
        self.assertGreater(update["weight_after"]["fairness"], update["weight_before"]["fairness"])
        self.assertLess(agent.effective_threshold(agent.NORMS["fairness"]), before)

    def test_proposal_alone_changes_nothing(self):
        weights = {d: n["weight"] for d, n in agent.NORMS.items()}
        self.app.propose_learning("inc", "feed-a", actor=REVIEWER,
                                  independently_verified=True, norm_domains=("fairness",))
        self.assertEqual({d: n["weight"] for d, n in agent.NORMS.items()}, weights)

    def test_learning_events_share_one_audit_chain(self):
        self.app.propose_learning("inc", "feed-a", actor=REVIEWER,
                                  independently_verified=True, norm_domains=("harm",))
        self.app.promote_learning("inc", actor=CONTROLLER)
        events = [r["event"] for r in self.app.audit.records()]
        self.assertEqual(events[-3:], ["LEARNING_PROPOSED", "LEARNING_PROMOTED",
                                       "NORMATIVE_UPDATE_APPLIED"])
        self.assertEqual(self.app.verify_audit(), (True, None))


class EvidenceFieldTests(unittest.TestCase):
    """Stored hashes and the evidence-source field now drive decisions."""

    def setUp(self):
        _reset_conscience()
        self.app = CITD(AUTH)
        self.app.ingest_receipt("B-1", 50_000, "REF-1", "feed-a", caller=BANK)
        self.app.ingest_ledger("L-B", "B", 50_000, caller=LEDGER)
        self.p = Proposal("c", "B-1", "L-B", principal=AGENT, idempotency_key="k")

    def test_derived_source_cannot_attribute_payer(self):
        self.app.ingest_remittance("M-1", "REF-1", "B", caller=REMIT,
                                   source="agent_extracted")
        self.assertNotIn("agent_extracted", INDEPENDENT_SOURCES)
        self.assertEqual(self.app.evaluate(self.p).disposition, "HOLD")

    def test_derived_copy_does_not_create_false_conflict(self):
        self.app.ingest_remittance("M-1", "REF-1", "B", caller=REMIT)
        self.app.ingest_remittance("M-2", "REF-1", "A", caller=REMIT,
                                   source="ledger_copy")
        self.assertEqual(self.app.evaluate(self.p).disposition, "ALLOW")

    def test_unknown_source_rejected(self):
        with self.assertRaises(ValueError):
            self.app.ingest_remittance("M-1", "REF-1", "B", caller=REMIT,
                                       source="email_screenshot")

    def test_tampered_remittance_holds(self):
        self.app.ingest_remittance("M-1", "REF-1", "A", caller=REMIT)
        self.app.db.execute("UPDATE remittances SET customer='B' WHERE remit_id='M-1'")
        self.assertEqual(self.app.verify_evidence_integrity(), ["M-1"])
        v = self.app.evaluate(self.p)
        self.assertEqual(v.disposition, "HOLD")
        self.assertIn("integrity", v.reason)

    def test_tampered_ledger_holds(self):
        self.app.ingest_remittance("M-1", "REF-1", "B", caller=REMIT)
        self.app.db.execute("UPDATE ledger SET amount=49000 WHERE ledger_id='L-B'")
        self.assertEqual(self.app.evaluate(self.p).disposition, "HOLD")

    def test_audit_tampering_detected(self):
        self.app.db.execute("UPDATE audit SET event='FORGED' WHERE seq=1")
        ok, bad = self.app.verify_audit()
        self.assertFalse(ok)
        self.assertEqual(bad, 1)


class SharedReferenceTests(unittest.TestCase):
    """P1: one remittance attributes at most one receipt."""

    def setUp(self):
        _reset_conscience()
        self.app = CITD(AUTH)
        self.app.ingest_ledger("L-B", "B", 50_000, caller=LEDGER)
        self.app.ingest_ledger("L-B2", "B", 50_000, caller=LEDGER)

    def test_truncated_reference_shared_by_open_receipts_holds(self):
        self.app.ingest_receipt("B-1", 50_000, "INV", "feed-a", caller=BANK)
        self.app.ingest_receipt("B-2", 50_000, "INV", "feed-a", caller=BANK)
        self.app.ingest_remittance("M-1", "INV", "B", caller=REMIT)
        v = self.app.evaluate(Proposal("c", "B-1", "L-B", principal=AGENT, idempotency_key="k"))
        self.assertEqual(v.disposition, "HOLD")
        self.assertIn("shared", v.reason)

    def test_remittance_is_consumed_and_cannot_be_reused(self):
        self.app.ingest_receipt("B-1", 50_000, "INV", "feed-a", caller=BANK)
        self.app.ingest_remittance("M-1", "INV", "B", caller=REMIT)
        first = self.app.dispatch(Proposal("c1", "B-1", "L-B", principal=AGENT, idempotency_key="k1"))
        self.assertEqual(first.disposition, "ALLOW")
        consumed = self.app.db.execute(
            "SELECT consumed_by_receipt FROM remittances WHERE remit_id='M-1'").fetchone()[0]
        self.assertEqual(consumed, "B-1")
        # A later receipt with the same reference finds no unconsumed evidence.
        self.app.ingest_receipt("B-2", 50_000, "INV", "feed-a", caller=BANK)
        second = self.app.dispatch(Proposal("c2", "B-2", "L-B2", principal=AGENT, idempotency_key="k2"))
        self.assertEqual(second.disposition, "HOLD")
        self.assertIsNone(self.app.db.execute(
            "SELECT cleared_ledger FROM receipts WHERE receipt_id='B-2'").fetchone()[0])


class AmountMismatchTests(unittest.TestCase):
    """P3: a partial or combined payment is a HOLD for allocation evidence, not a BLOCK."""

    def setUp(self):
        _reset_conscience()
        self.app = CITD(AUTH)
        self.app.ingest_ledger("L-B", "B", 50_000, caller=LEDGER)
        self.app.ingest_remittance("M-1", "REF", "B", caller=REMIT)

    def _verdict(self, amount):
        self.app.ingest_receipt("B-1", amount, "REF", "feed-a", caller=BANK)
        return self.app.evaluate(Proposal("c", "B-1", "L-B", principal=AGENT, idempotency_key="k"))

    def test_partial_payment_holds(self):
        v = self._verdict(30_000)
        self.assertEqual(v.disposition, "HOLD")
        self.assertIn("Partial payment", v.reason)

    def test_overpayment_holds(self):
        v = self._verdict(70_000)
        self.assertEqual(v.disposition, "HOLD")
        self.assertIn("Overpayment", v.reason)


class RestrictionLifecycleTests(unittest.TestCase):
    """P5: restrictions can be revoked or expire. P6: earlier clearances are queued."""

    def setUp(self):
        _reset_conscience()
        self.app = CITD(AUTH)
        self.app.ingest_ledger("L-1", "B", 10_000, caller=LEDGER)
        self.app.ingest_ledger("L-2", "B", 10_000, caller=LEDGER)
        self.app.ingest_ledger("L-3", "B", 10_000, caller=LEDGER)
        self.app.ingest_receipt("B-1", 10_000, "R1", "feed-a", caller=BANK,
                                importer_version="v1")
        self.app.ingest_receipt("B-2", 10_000, "R2", "feed-a", caller=BANK,
                                importer_version="v2")
        self.app.ingest_remittance("M-1", "R1", "B", caller=REMIT)
        self.app.ingest_remittance("M-2", "R2", "B", caller=REMIT)
        self.assertEqual(self.app.dispatch(
            Proposal("c1", "B-1", "L-1", principal=AGENT, idempotency_key="k1")).disposition, "ALLOW")
        self.assertEqual(self.app.dispatch(
            Proposal("c2", "B-2", "L-2", principal=AGENT, idempotency_key="k2")).disposition, "ALLOW")

    def _promote(self, **kw):
        self.app.propose_learning("inc", "feed-a", actor=REVIEWER,
                                  independently_verified=True, norm_domains=("honesty",), **kw)
        return self.app.promote_learning("inc", actor=CONTROLLER)

    def _new_receipt(self, version):
        self.app.ingest_receipt("B-3", 10_000, "R3", "feed-a", caller=BANK,
                                importer_version=version)
        self.app.ingest_remittance("M-3", "R3", "B", caller=REMIT)
        return Proposal("c3", "B-3", "L-3", principal=AGENT, idempotency_key="k3")

    def test_promotion_queues_earlier_clearances(self):
        result = self._promote()
        self.assertEqual(result["corrections_queued"], ["B-1", "B-2"])
        self.assertEqual([c["ledger_id"] for c in self.app.open_corrections("inc")],
                         ["L-1", "L-2"])
        promoted = [r for r in self.app.audit.records() if r["event"] == "LEARNING_PROMOTED"]
        self.assertEqual(promoted[-1]["payload"]["corrections_queued"], ["B-1", "B-2"])

    def test_importer_scope_restricts_only_that_version(self):
        result = self._promote(importer_version="v1")
        self.assertEqual(result["corrections_queued"], ["B-1"])
        p = self._new_receipt("v2")
        self.assertEqual(self.app.evaluate(p).disposition, "ALLOW")

    def test_importer_scope_blocks_the_named_version(self):
        self._promote(importer_version="v1")
        self.assertEqual(self.app.evaluate(self._new_receipt("v1")).disposition, "BLOCK")

    def test_revoke_lifts_restriction_and_reverses_weights(self):
        baseline = agent.NORMS["honesty"]["weight"]
        self._promote()
        self.assertGreater(agent.NORMS["honesty"]["weight"], baseline)
        p = self._new_receipt("v1")
        self.assertEqual(self.app.evaluate(p).disposition, "BLOCK")
        result = self.app.revoke_learning("inc", actor=CONTROLLER, reason="root cause fixed")
        self.assertAlmostEqual(agent.NORMS["honesty"]["weight"], baseline, places=6)
        self.assertEqual(result["normative_reversal"]["weight_restored"]["honesty"],
                         agent.NORMS["honesty"]["weight"])
        self.assertEqual(self.app.evaluate(p).disposition, "ALLOW")
        # The queued corrections concern clearances already made, so they stay open.
        self.assertEqual(len(self.app.open_corrections("inc")), 2)
        self.assertEqual(self.app.verify_audit(), (True, None))

    def test_revoked_incident_is_skipped_by_continuity_rebuild(self):
        cl = agent.get_continuity_layer()
        cl._synchronize_norms_from_history()
        before = cl.domain_weights["honesty"]
        self._promote()
        self.app.revoke_learning("inc", actor=CONTROLLER, reason="false positive")
        cl._synchronize_norms_from_history()
        self.assertEqual(cl.domain_weights["honesty"], before)

    def test_revoke_requires_controller_and_reason(self):
        self._promote()
        with self.assertRaises(PermissionError):
            self.app.revoke_learning("inc", actor=AGENT, reason="x")
        with self.assertRaises(ValueError):
            self.app.revoke_learning("inc", actor=CONTROLLER, reason="  ")
        with self.assertRaises(ValueError):
            self.app.revoke_learning("missing", actor=CONTROLLER, reason="x")

    def test_expired_restriction_lapses(self):
        self._promote(expires_at="2000-01-01T00:00:00+00:00")
        self.assertEqual(self.app.evaluate(self._new_receipt("v1")).disposition, "ALLOW")

    def test_unexpired_restriction_holds(self):
        self._promote(expires_at="2999-01-01T00:00:00+00:00")
        self.assertEqual(self.app.evaluate(self._new_receipt("v1")).disposition, "BLOCK")

    def test_malformed_expiry_rejected(self):
        with self.assertRaises(ValueError):
            self._promote(expires_at="next tuesday")


class EvidenceTimingTests(unittest.TestCase):
    """P2: attributing evidence must predate the gate-stamped proposal."""

    def setUp(self):
        _reset_conscience()
        self.app = CITD(AUTH)
        self.app.ingest_receipt("B-1", 50_000, "REF-1", "feed-a", caller=BANK)
        self.app.ingest_ledger("L-A", "A", 50_000, caller=LEDGER)
        self.app.ingest_ledger("L-B", "B", 50_000, caller=LEDGER)

    def test_evidence_after_proposal_does_not_justify_it(self):
        p = Proposal("c", "B-1", "L-B", principal=AGENT, idempotency_key="k1")
        self.assertEqual(self.app.dispatch(p).disposition, "HOLD")
        self.app.ingest_remittance("M-1", "REF-1", "B", caller=REMIT)
        v = self.app.dispatch(p)
        self.assertEqual(v.disposition, "HOLD")
        self.assertIn("postdates", v.reason)
        self.assertIsNone(self.app.db.execute(
            "SELECT consumed_by_receipt FROM remittances").fetchone()[0])

    def test_new_proposal_after_evidence_is_allowed(self):
        self.app.dispatch(Proposal("c", "B-1", "L-B", principal=AGENT, idempotency_key="k1"))
        self.app.ingest_remittance("M-1", "REF-1", "B", caller=REMIT)
        v = self.app.dispatch(Proposal("c", "B-1", "L-B", principal=AGENT, idempotency_key="k2"))
        self.assertEqual(v.disposition, "ALLOW")

    def test_late_conflicting_evidence_still_holds(self):
        self.app.ingest_remittance("M-1", "REF-1", "B", caller=REMIT)
        p = Proposal("c", "B-1", "L-B", principal=AGENT, idempotency_key="k1")
        # Register the proposal between the two remittances.
        self.app.db.execute("INSERT INTO proposals VALUES('k1','c','B-1','L-B','agent-1',?)",
                            (citd_reference.now(),))
        self.app.ingest_remittance("M-2", "REF-1", "A", caller=REMIT)
        late = self.app.db.execute(
            "SELECT created_at FROM remittances WHERE remit_id='M-2'").fetchone()[0]
        self.assertGreaterEqual(late, self.app._registered_at(p))
        self.assertEqual(self.app.dispatch(p).disposition, "HOLD")

    def test_registered_key_cannot_be_retargeted(self):
        self.app.dispatch(Proposal("c", "B-1", "L-B", principal=AGENT, idempotency_key="k1"))
        v = self.app.dispatch(Proposal("c", "B-1", "L-A", principal=AGENT, idempotency_key="k1"))
        self.assertEqual(v.disposition, "BLOCK")
        self.assertIn("reused", v.reason)


class IdentityTests(unittest.TestCase):
    """P4: roles are proven by credentials signed by the identity authority."""

    def setUp(self):
        _reset_conscience()
        self.app = CITD(AUTH)
        self.app.ingest_receipt("B-1", 50_000, "REF-1", "feed-a", caller=BANK)
        self.app.ingest_ledger("L-B", "B", 50_000, caller=LEDGER)
        self.app.ingest_remittance("M-1", "REF-1", "B", caller=REMIT)

    def test_role_string_is_not_a_credential(self):
        with self.assertRaises(PermissionError):
            self.app.ingest_receipt("B-2", 10, "R2", "feed-a", caller="bank_adapter")

    def test_forged_tag_is_rejected(self):
        forged = Credential("bank-1", "bank_adapter", "0" * 64)
        with self.assertRaises(PermissionError):
            self.app.ingest_receipt("B-2", 10, "R2", "feed-a", caller=forged)

    def test_relabelled_credential_is_rejected(self):
        promoted = Credential(AGENT.subject, "finance_controller", AGENT.tag)
        self.app.propose_learning("inc", "feed-a", actor=REVIEWER,
                                  independently_verified=True, norm_domains=("harm",))
        with self.assertRaises(PermissionError):
            self.app.promote_learning("inc", actor=promoted)

    def test_credential_from_another_authority_is_rejected(self):
        other = IdentityAuthority().issue("agent-1", "finance_agent")
        v = self.app.evaluate(Proposal("c", "B-1", "L-B", principal=other, idempotency_key="k"))
        self.assertEqual(v.disposition, "BLOCK")

    def test_missing_principal_blocks(self):
        v = self.app.evaluate(Proposal("c", "B-1", "L-B", idempotency_key="k"))
        self.assertEqual(v.disposition, "BLOCK")

    def test_reviewer_cannot_promote_own_incident(self):
        same_person = AUTH.issue("audit-1", "finance_controller")
        self.app.propose_learning("inc", "feed-a", actor=REVIEWER,
                                  independently_verified=True, norm_domains=("harm",))
        with self.assertRaises(PermissionError):
            self.app.promote_learning("inc", actor=same_person)

    def test_audit_names_authenticated_subjects(self):
        self.app.dispatch(Proposal("c", "B-1", "L-B", principal=AGENT, idempotency_key="k"))
        records = self.app.audit.records()
        by_event = {r["event"]: r["payload"] for r in records}
        self.assertEqual(by_event["RECEIPT_INGESTED"]["by"], "bank-1")
        self.assertEqual(by_event["DISPATCH"]["principal"], "agent-1")

    def test_unknown_role_cannot_be_issued(self):
        with self.assertRaises(ValueError):
            AUTH.issue("x", "superuser")


if __name__ == "__main__":
    unittest.main()

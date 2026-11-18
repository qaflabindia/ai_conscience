"""CITD minimal reference implementation for research illustration.

Standard-library-only Python 3.10+. NOT production-ready. Demonstrates:
- Trusted-source ingestion distinct from an agent's decision payload.
- Scoped delegated authority, hard constraints, independent remittance evidence.
- ALLOW / HOLD / ESCALATE / BLOCK, atomic idempotent ledger clearance.
- The conscience engine as an advisory input that can only tighten decisions.
- Governed learning: a verified incident, once promoted, both restricts the
  implicated feed and raises the weight of the implicated norm domains.

Shared vocabulary (dispositions, norm domains, learning modes, audit format)
comes from conscience_research/trust_contracts.py, so this gate and the
conscience service speak one language.

It does not demonstrate phenomenal or moral conscience, or authenticate real bank systems.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

_CONSCIENCE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               "conscience_research")
if _CONSCIENCE_DIR not in sys.path:
    sys.path.insert(0, _CONSCIENCE_DIR)

from trust_contracts import (  # noqa: E402
    DISPATCH_REPLAY,
    Disposition,
    LearningMode,
    SqliteAudit,
    stricter,
    validate_norms,
)

# Remittance evidence sources. Only independent sources can attribute a payer;
# derived sources (copies or agent output) are kept for lineage but never count.
INDEPENDENT_SOURCES = frozenset({"customer_remittance", "bank_remittance_advice"})
DERIVED_SOURCES = frozenset({"agent_extracted", "ledger_copy"})


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def digest(value: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def _receipt_fields(row: Any) -> dict[str, Any]:
    return {"receipt_id": row["receipt_id"], "amount": row["amount"],
            "bank_ref": row["bank_ref"], "feed": row["feed"]}


def _ledger_fields(row: Any) -> dict[str, Any]:
    return {"ledger_id": row["ledger_id"], "customer": row["customer"],
            "amount": row["amount"]}


def _remittance_fields(row: Any) -> dict[str, Any]:
    return {"remit_id": row["remit_id"], "bank_ref": row["bank_ref"],
            "customer": row["customer"], "source": row["source"]}


@dataclass(frozen=True)
class Proposal:
    case_id: str
    receipt_id: str
    ledger_id: str
    principal: str = "finance_agent"
    action: str = "CLEAR_RECEIPT"
    idempotency_key: str = ""
    # The agent's own normative self-assessment (domain -> 0..1). Advisory only:
    # it can make a decision stricter through the conscience engine, never looser.
    self_assessment: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class Verdict:
    disposition: str              # a Disposition value, or DISPATCH_REPLAY
    allowed: bool
    reason: str
    normative_domains: tuple[str, ...]
    policy_version: str
    advisory: Optional[dict[str, Any]] = None

    def json(self) -> str:
        return json.dumps(asdict(self), indent=2)


class CITD:
    MAX_AUTO_AMOUNT = 100_000
    POLICY_VERSION = "finance-recon-v1"

    def __init__(self, database: str = ":memory:", advisor: Any = "default"):
        """advisor: "default" uses the conscience engine; None disables advice."""
        if advisor == "default":
            from advisor import ConscienceAdvisor  # conscience_research/advisor.py
            advisor = ConscienceAdvisor()
        self.advisor = advisor
        self.db = sqlite3.connect(database, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS receipts (
            receipt_id TEXT PRIMARY KEY, amount INTEGER NOT NULL,
            bank_ref TEXT NOT NULL, feed TEXT NOT NULL,
            cleared_ledger TEXT, original_hash TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS ledger (
            ledger_id TEXT PRIMARY KEY, customer TEXT NOT NULL,
            amount INTEGER NOT NULL, cleared_receipt TEXT,
            original_hash TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS remittances (
            remit_id TEXT PRIMARY KEY, bank_ref TEXT NOT NULL,
            customer TEXT NOT NULL, source TEXT NOT NULL,
            created_at TEXT NOT NULL, original_hash TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS completed (
            idempotency_key TEXT PRIMARY KEY, receipt_id TEXT NOT NULL,
            ledger_id TEXT NOT NULL, committed_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS learning_proposals (
            incident_id TEXT PRIMARY KEY, feed TEXT NOT NULL,
            norm_domains TEXT NOT NULL, verified_by TEXT NOT NULL,
            change_summary TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'PENDING');
        CREATE TABLE IF NOT EXISTS feed_controls (
            feed TEXT PRIMARY KEY, suspended INTEGER NOT NULL DEFAULT 0,
            version INTEGER NOT NULL DEFAULT 0);
        """)
        self.audit = SqliteAudit(self.db)

    # ── Ingestion (trusted adapters only) ────────────────────────────────────

    def ingest_receipt(self, receipt_id: str, amount: int, bank_ref: str,
                       feed: str, *, caller: str) -> None:
        if caller != "bank_adapter":
            raise PermissionError("Only authenticated bank adapter may ingest receipts")
        if amount <= 0:
            raise ValueError("Amount must be positive minor currency units")
        row = {"receipt_id": receipt_id, "amount": amount, "bank_ref": bank_ref, "feed": feed}
        self.db.execute("INSERT INTO receipts VALUES(?,?,?,?,NULL,?)",
                        (receipt_id, amount, bank_ref, feed, digest(row)))
        self.db.execute("INSERT OR IGNORE INTO feed_controls(feed) VALUES(?)", (feed,))
        self.audit.append("RECEIPT_INGESTED", {"receipt_id": receipt_id, "feed": feed})

    def ingest_ledger(self, ledger_id: str, customer: str, amount: int,
                      *, caller: str) -> None:
        if caller != "ledger_adapter":
            raise PermissionError("Only ledger adapter may ingest ledger entries")
        row = {"ledger_id": ledger_id, "customer": customer, "amount": amount}
        self.db.execute("INSERT INTO ledger VALUES(?,?,?,NULL,?)",
                        (ledger_id, customer, amount, digest(row)))
        self.audit.append("LEDGER_INGESTED", {"ledger_id": ledger_id})

    def ingest_remittance(self, remit_id: str, bank_ref: str, customer: str,
                          *, caller: str, source: str = "customer_remittance") -> None:
        if caller != "remittance_adapter":
            raise PermissionError("Authenticated remittance adapter required")
        if source not in INDEPENDENT_SOURCES | DERIVED_SOURCES:
            raise ValueError(f"Unknown remittance source: {source}")
        row = {"remit_id": remit_id, "bank_ref": bank_ref, "customer": customer, "source": source}
        self.db.execute("INSERT INTO remittances VALUES(?,?,?,?,?,?)",
                        (remit_id, bank_ref, customer, source, now(), digest(row)))
        self.audit.append("REMITTANCE_INGESTED", {
            "remit_id": remit_id, "source": source,
            "independent": source in INDEPENDENT_SOURCES})

    # ── Integrity checks (stored hashes are verified, not decorative) ───────

    def verify_evidence_integrity(self) -> list[str]:
        """Return the IDs of evidence rows whose content no longer matches its hash."""
        bad: list[str] = []
        for r in self.db.execute("SELECT * FROM receipts"):
            if digest(_receipt_fields(r)) != r["original_hash"]:
                bad.append(r["receipt_id"])
        for r in self.db.execute("SELECT * FROM ledger"):
            if digest(_ledger_fields(r)) != r["original_hash"]:
                bad.append(r["ledger_id"])
        for r in self.db.execute("SELECT * FROM remittances"):
            if digest(_remittance_fields(r)) != r["original_hash"]:
                bad.append(r["remit_id"])
        return bad

    def verify_audit(self) -> tuple[bool, int | None]:
        return self.audit.verify()

    # ── Decision ─────────────────────────────────────────────────────────────

    def _gate(self, p: Proposal) -> tuple[Disposition, str, tuple[str, ...], bool]:
        """Deterministic gate. Returns (disposition, reason, norm domains, authorised)."""
        D = Disposition
        if p.principal != "finance_agent" or p.action != "CLEAR_RECEIPT":
            return D.BLOCK, "Action or principal outside delegated authority", ("authority",), False
        if not p.idempotency_key:
            return D.BLOCK, "Idempotency key required", ("honesty", "authority"), True
        receipt = self.db.execute("SELECT * FROM receipts WHERE receipt_id=?",
                                  (p.receipt_id,)).fetchone()
        ledger = self.db.execute("SELECT * FROM ledger WHERE ledger_id=?",
                                 (p.ledger_id,)).fetchone()
        if not receipt or not ledger:
            return D.HOLD, "Original bank or ledger evidence missing", ("honesty",), True
        if (digest(_receipt_fields(receipt)) != receipt["original_hash"]
                or digest(_ledger_fields(ledger)) != ledger["original_hash"]):
            return D.HOLD, "Evidence integrity check failed", ("honesty",), True
        feed = self.db.execute("SELECT * FROM feed_controls WHERE feed=?",
                               (receipt["feed"],)).fetchone()
        if feed and feed["suspended"]:
            return D.BLOCK, "Verified incident has suspended this feed", ("harm", "authority"), True
        if receipt["amount"] > self.MAX_AUTO_AMOUNT:
            return D.ESCALATE, "Amount exceeds automatic delegation", ("authority", "harm"), True
        if receipt["amount"] != ledger["amount"]:
            return D.BLOCK, "Amount mismatch", ("honesty", "harm"), True
        if receipt["cleared_ledger"]:
            return D.BLOCK, "Receipt already consumed", ("honesty", "authority"), True
        if ledger["cleared_receipt"]:
            return D.BLOCK, "Ledger entry already consumed", ("honesty", "authority"), True

        # Only independent sources attribute a payer; derived copies never count.
        independent = [r for r in self.db.execute(
            "SELECT * FROM remittances WHERE bank_ref=?", (receipt["bank_ref"],))
            if r["source"] in INDEPENDENT_SOURCES]
        if any(digest(_remittance_fields(r)) != r["original_hash"] for r in independent):
            return D.HOLD, "Evidence integrity check failed", ("honesty",), True
        matches = [r for r in independent if r["customer"] == ledger["customer"]]
        competing = {r["customer"] for r in independent}
        if len(matches) != 1 or len(competing) != 1:
            return (D.HOLD, "Independent unique payer attribution not established",
                    ("honesty", "harm", "fairness"), True)
        return D.ALLOW, "Independent remittance uniquely identifies the payer", ("honesty", "authority"), True

    def evaluate(self, p: Proposal) -> Verdict:
        disposition, reason, domains, authorised = self._gate(p)
        domains = validate_norms(domains)
        advisory: Optional[dict[str, Any]] = None

        if self.advisor is not None:
            try:
                result = self.advisor.assess(authorised=authorised,
                                             self_assessment=p.self_assessment)
                advisory = result.as_payload()
                if result.cap is not None and stricter(disposition, result.cap) != disposition:
                    disposition = stricter(disposition, result.cap)
                    reason = (f"{reason}; conscience advisory raised to {disposition.value} "
                              f"(flagged={list(result.flagged_domains)}, "
                              f"hard_floors={list(result.hard_floors)})")
                    domains = validate_norms(dict.fromkeys(domains + result.flagged_domains))
            except Exception as err:  # fail closed: a broken advisor cannot allow
                advisory = {"error": type(err).__name__}
                disposition = stricter(disposition, Disposition.ESCALATE)
                reason = f"{reason}; conscience advisory unavailable"

        return Verdict(disposition.value, disposition is Disposition.ALLOW, reason,
                       domains, self.POLICY_VERSION, advisory)

    def dispatch(self, p: Proposal) -> Verdict:
        # BEGIN IMMEDIATE serialises the critical receipt check and commit in SQLite.
        self.db.execute("BEGIN IMMEDIATE")
        try:
            prior = self.db.execute("SELECT * FROM completed WHERE idempotency_key=?",
                                    (p.idempotency_key,)).fetchone()
            if prior:
                if prior["receipt_id"] != p.receipt_id or prior["ledger_id"] != p.ledger_id:
                    outcome = Verdict(Disposition.BLOCK.value, False,
                                      "Idempotency key reused for different action",
                                      ("honesty", "authority"), self.POLICY_VERSION)
                else:
                    outcome = Verdict(DISPATCH_REPLAY, True, "Idempotent replay, no second write",
                                      (), self.POLICY_VERSION)
            else:
                outcome = self.evaluate(p)  # re-evaluate inside the transaction
                if outcome.allowed:
                    changed_receipt = self.db.execute(
                        "UPDATE receipts SET cleared_ledger=? WHERE receipt_id=? AND cleared_ledger IS NULL",
                        (p.ledger_id, p.receipt_id)).rowcount
                    changed_ledger = self.db.execute(
                        "UPDATE ledger SET cleared_receipt=? WHERE ledger_id=? AND cleared_receipt IS NULL",
                        (p.receipt_id, p.ledger_id)).rowcount
                    if changed_receipt != 1 or changed_ledger != 1:
                        raise RuntimeError("Concurrent update detected")
                    self.db.execute("INSERT INTO completed VALUES(?,?,?,?)",
                                    (p.idempotency_key, p.receipt_id, p.ledger_id, now()))
            self.audit.append("DISPATCH", {
                "case_id": p.case_id, "receipt_id": p.receipt_id, "ledger_id": p.ledger_id,
                "disposition": outcome.disposition,
                "norm_domains": list(outcome.normative_domains),
                "advisory": outcome.advisory,
                "policy_version": outcome.policy_version})
            self.db.execute("COMMIT")
            return outcome
        except Exception:
            self.db.execute("ROLLBACK")
            raise

    # ── Governed learning ───────────────────────────────────────────────────

    def propose_learning(self, incident_id: str, feed: str, *, actor: str,
                         independently_verified: bool,
                         norm_domains: tuple[str, ...]) -> None:
        # A self-critique is not ground truth. Only a reviewer can attest to an incident.
        if actor != "independent_reviewer" or not independently_verified:
            raise PermissionError("Independent incident adjudication required")
        domains = validate_norms(norm_domains)
        if not domains:
            raise ValueError("An incident must name at least one norm domain")
        found = self.db.execute("SELECT feed FROM feed_controls WHERE feed=?", (feed,)).fetchone()
        if not found:
            raise ValueError("Unknown feed")
        self.db.execute(
            "INSERT INTO learning_proposals VALUES(?,?,?,?,?, 'PENDING')",
            (incident_id, feed, json.dumps(list(domains)), actor,
             "Suspend automatic clearance on implicated feed; raise implicated norm weights"))
        self.audit.append("LEARNING_PROPOSED", {
            "incident_id": incident_id, "feed": feed, "norm_domains": list(domains),
            "learning_mode": LearningMode.GOVERNED.value})

    def promote_learning(self, incident_id: str, *, actor: str) -> dict[str, Any]:
        """Promote a verified incident. Returns the normative update applied, if any."""
        if actor != "finance_controller":
            raise PermissionError("Only delegated controller can promote a new restriction")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.db.execute(
                "SELECT * FROM learning_proposals WHERE incident_id=? AND status='PENDING'",
                (incident_id,)).fetchone()
            if not row:
                raise ValueError("No pending verified incident")
            domains = validate_norms(json.loads(row["norm_domains"]))
            self.db.execute("UPDATE feed_controls SET suspended=1,version=version+1 WHERE feed=?",
                            (row["feed"],))
            self.db.execute("UPDATE learning_proposals SET status='PROMOTED' WHERE incident_id=?",
                            (incident_id,))
            self.audit.append("LEARNING_PROMOTED", {
                "incident_id": incident_id, "feed": row["feed"], "norm_domains": list(domains),
                "learning_mode": LearningMode.GOVERNED.value})
            self.db.execute("COMMIT")
        except Exception:
            self.db.execute("ROLLBACK")
            raise

        # The feed restriction is committed first, so a failure below can only
        # leave the system stricter, never looser.
        if self.advisor is None:
            return {}
        try:
            update = self.advisor.learn_from_incident(incident_id, domains)
        except Exception as err:
            self.audit.append("NORMATIVE_UPDATE_FAILED", {
                "incident_id": incident_id, "error": type(err).__name__})
            raise
        self.audit.append("NORMATIVE_UPDATE_APPLIED", update)
        return update


def demo() -> None:
    app = CITD()
    app.ingest_receipt("B-778", 50_000, "R-778", "bank_feed_1", caller="bank_adapter")
    app.ingest_ledger("L-101", "CUSTOMER_A", 50_000, caller="ledger_adapter")
    app.ingest_ledger("L-102", "CUSTOMER_B", 50_000, caller="ledger_adapter")
    proposal = Proposal("recon-001", "B-778", "L-102", idempotency_key="clear-001")
    print("Ambiguous:", app.dispatch(proposal).json())
    app.ingest_remittance("M-902", "R-778", "CUSTOMER_B", caller="remittance_adapter")
    print("With independent evidence:", app.dispatch(proposal).json())
    print("Repeated request:", app.dispatch(proposal).json())
    app.propose_learning("incident-22", "bank_feed_1", actor="independent_reviewer",
                         independently_verified=True, norm_domains=("honesty", "harm"))
    update = app.promote_learning("incident-22", actor="finance_controller")
    print("Governed learning applied:", json.dumps(update, indent=2))
    print("Audit chain intact:", app.verify_audit())


if __name__ == "__main__":
    demo()

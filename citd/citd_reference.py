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

Identities are HMAC-signed credentials issued by an IdentityAuthority, so a
caller cannot claim a role by passing a string. The key lives in the same
process, so this shows separable privileges, not production authentication.

It does not demonstrate phenomenal or moral conscience, or authenticate real bank systems.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
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


# ── Identity (P4): roles are proven by a signed credential, not a string ────

ROLES = frozenset({
    "bank_adapter", "ledger_adapter", "remittance_adapter",  # trusted ingestion
    "finance_agent",                                         # proposes, never decides
    "independent_reviewer",                                  # adjudicates incidents
    "finance_controller",                                    # promotes / revokes restrictions
})


@dataclass(frozen=True)
class Credential:
    subject: str
    role: str
    tag: str = field(repr=False)


class IdentityAuthority:
    """Issues and verifies role credentials (HMAC-SHA256 over subject and role).

    Holding one credential does not let a caller mint another: that needs the
    authority's key. In this reference the key is in-process; a deployment
    would use mTLS or signed tokens from an external identity provider.
    """

    def __init__(self, key: Optional[bytes] = None):
        self._key = key or secrets.token_bytes(32)

    def _tag(self, subject: str, role: str) -> str:
        return hmac.new(self._key, f"{subject}\x1f{role}".encode(), hashlib.sha256).hexdigest()

    def issue(self, subject: str, role: str) -> Credential:
        if role not in ROLES:
            raise ValueError(f"Unknown role: {role}")
        if not subject:
            raise ValueError("A credential needs a subject")
        return Credential(subject, role, self._tag(subject, role))

    def is_valid(self, cred: Any, role: str) -> bool:
        return (isinstance(cred, Credential) and cred.role == role
                and hmac.compare_digest(cred.tag, self._tag(cred.subject, cred.role)))

    def require(self, cred: Any, role: str, message: str) -> str:
        """Return the credential's subject, or raise PermissionError."""
        if not self.is_valid(cred, role):
            raise PermissionError(message)
        return cred.subject


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def digest(value: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def _receipt_fields(row: Any) -> dict[str, Any]:
    return {"receipt_id": row["receipt_id"], "amount": row["amount"],
            "bank_ref": row["bank_ref"], "feed": row["feed"],
            "importer_version": row["importer_version"]}


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
    principal: Optional[Credential] = None   # must be a valid finance_agent credential
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

    def __init__(self, identity: IdentityAuthority, database: str = ":memory:",
                 advisor: Any = "default"):
        """identity verifies every caller. advisor: "default" uses the conscience
        engine; None disables advice."""
        if not isinstance(identity, IdentityAuthority):
            raise TypeError("CITD needs an IdentityAuthority")
        self.identity = identity
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
            importer_version TEXT NOT NULL,
            cleared_ledger TEXT, original_hash TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS ledger (
            ledger_id TEXT PRIMARY KEY, customer TEXT NOT NULL,
            amount INTEGER NOT NULL, cleared_receipt TEXT,
            original_hash TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS remittances (
            remit_id TEXT PRIMARY KEY, bank_ref TEXT NOT NULL,
            customer TEXT NOT NULL, source TEXT NOT NULL,
            created_at TEXT NOT NULL, original_hash TEXT NOT NULL,
            consumed_by_receipt TEXT);
        CREATE TABLE IF NOT EXISTS proposals (       -- gate-stamped submission time (P2)
            idempotency_key TEXT PRIMARY KEY, case_id TEXT NOT NULL,
            receipt_id TEXT NOT NULL, ledger_id TEXT NOT NULL,
            principal TEXT NOT NULL, registered_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS completed (
            idempotency_key TEXT PRIMARY KEY, receipt_id TEXT NOT NULL,
            ledger_id TEXT NOT NULL, committed_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS learning_proposals (
            incident_id TEXT PRIMARY KEY, feed TEXT NOT NULL,
            importer_version TEXT,            -- NULL: whole feed
            norm_domains TEXT NOT NULL, verified_by TEXT NOT NULL,
            change_summary TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'PENDING',
            expires_at TEXT,                  -- NULL: until revoked
            normative_update TEXT);           -- JSON of the applied norm change
        CREATE TABLE IF NOT EXISTS correction_queue (
            incident_id TEXT NOT NULL, receipt_id TEXT NOT NULL,
            ledger_id TEXT NOT NULL, importer_version TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'OPEN', queued_at TEXT NOT NULL,
            PRIMARY KEY (incident_id, receipt_id));
        CREATE TABLE IF NOT EXISTS feed_controls (   -- registry of known feeds;
            feed TEXT PRIMARY KEY);                    -- restrictions live in learning_proposals
        """)
        self.audit = SqliteAudit(self.db)

    # ── Ingestion (trusted adapters only) ────────────────────────────────────

    def ingest_receipt(self, receipt_id: str, amount: int, bank_ref: str,
                       feed: str, *, caller: Credential, importer_version: str = "v1") -> None:
        source_id = self.identity.require(caller, "bank_adapter",
                                          "Only authenticated bank adapter may ingest receipts")
        if amount <= 0:
            raise ValueError("Amount must be positive minor currency units")
        row = {"receipt_id": receipt_id, "amount": amount, "bank_ref": bank_ref,
               "feed": feed, "importer_version": importer_version}
        self.db.execute("INSERT INTO receipts VALUES(?,?,?,?,?,NULL,?)",
                        (receipt_id, amount, bank_ref, feed, importer_version, digest(row)))
        self.db.execute("INSERT OR IGNORE INTO feed_controls(feed) VALUES(?)", (feed,))
        self.audit.append("RECEIPT_INGESTED", {"receipt_id": receipt_id, "feed": feed,
                                               "importer_version": importer_version,
                                               "by": source_id})

    def ingest_ledger(self, ledger_id: str, customer: str, amount: int,
                      *, caller: Credential) -> None:
        source_id = self.identity.require(caller, "ledger_adapter",
                                          "Only ledger adapter may ingest ledger entries")
        row = {"ledger_id": ledger_id, "customer": customer, "amount": amount}
        self.db.execute("INSERT INTO ledger VALUES(?,?,?,NULL,?)",
                        (ledger_id, customer, amount, digest(row)))
        self.audit.append("LEDGER_INGESTED", {"ledger_id": ledger_id, "by": source_id})

    def ingest_remittance(self, remit_id: str, bank_ref: str, customer: str,
                          *, caller: Credential, source: str = "customer_remittance") -> None:
        source_id = self.identity.require(caller, "remittance_adapter",
                                          "Authenticated remittance adapter required")
        if source not in INDEPENDENT_SOURCES | DERIVED_SOURCES:
            raise ValueError(f"Unknown remittance source: {source}")
        row = {"remit_id": remit_id, "bank_ref": bank_ref, "customer": customer, "source": source}
        self.db.execute("INSERT INTO remittances VALUES(?,?,?,?,?,?,NULL)",
                        (remit_id, bank_ref, customer, source, now(), digest(row)))
        self.audit.append("REMITTANCE_INGESTED", {
            "remit_id": remit_id, "source": source,
            "independent": source in INDEPENDENT_SOURCES, "by": source_id})

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

    def _gate(self, p: Proposal, as_of: str) -> tuple[Disposition, str, tuple[str, ...], bool]:
        """Deterministic gate. Returns (disposition, reason, norm domains, authorised).

        as_of is when the gate first registered the proposal: attributing
        evidence must predate it (the EvidenceSufficient condition of the
        decision contract).
        """
        D = Disposition
        if p.action != "CLEAR_RECEIPT" or not self.identity.is_valid(p.principal, "finance_agent"):
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
        restriction = self._active_restriction(receipt["feed"], receipt["importer_version"])
        if restriction:
            return (D.BLOCK, f"Verified incident {restriction} has suspended this feed",
                    ("harm", "authority"), True)
        if receipt["amount"] > self.MAX_AUTO_AMOUNT:
            return D.ESCALATE, "Amount exceeds automatic delegation", ("authority", "harm"), True
        if receipt["cleared_ledger"]:
            return D.BLOCK, "Receipt already consumed", ("honesty", "authority"), True
        if ledger["cleared_receipt"]:
            return D.BLOCK, "Ledger entry already consumed", ("honesty", "authority"), True
        if receipt["amount"] != ledger["amount"]:
            # Partial, combined or fee-reduced payments are routine exceptions,
            # not impermissible actions: hold for allocation evidence.
            kind = "Partial" if receipt["amount"] < ledger["amount"] else "Overpayment or combined"
            return (D.HOLD, f"{kind} payment: allocation evidence required",
                    ("honesty", "harm"), True)

        # A truncated or reused bank reference shared by several open receipts
        # cannot be attributed one-to-one, whatever the remittances say.
        open_same_ref = self.db.execute(
            "SELECT COUNT(*) FROM receipts WHERE bank_ref=? AND cleared_ledger IS NULL",
            (receipt["bank_ref"],)).fetchone()[0]
        if open_same_ref > 1:
            return (D.HOLD, "Bank reference shared by several open receipts",
                    ("honesty", "harm", "fairness"), True)

        # Only independent, unconsumed remittances attribute a payer; derived
        # copies never count, and each remittance justifies at most one clearance.
        independent = [r for r in self.db.execute(
            "SELECT * FROM remittances WHERE bank_ref=? AND consumed_by_receipt IS NULL",
            (receipt["bank_ref"],))
            if r["source"] in INDEPENDENT_SOURCES]
        if any(digest(_remittance_fields(r)) != r["original_hash"] for r in independent):
            return D.HOLD, "Evidence integrity check failed", ("honesty",), True
        # Late evidence still counts as a conflict (stricter), but only evidence
        # that existed when the proposal was made can attribute the payer.
        competing = {r["customer"] for r in independent}
        matches = [r for r in independent if r["customer"] == ledger["customer"]]
        timely = [r for r in matches if r["created_at"] <= as_of]
        if len(competing) == 1 and len(matches) == 1 and not timely:
            return (D.HOLD, "Attributing evidence postdates the proposal; submit a new proposal",
                    ("honesty",), True)
        if len(timely) != 1 or len(competing) != 1:
            return (D.HOLD, "Independent unique payer attribution not established",
                    ("honesty", "harm", "fairness"), True)
        return D.ALLOW, "Independent remittance uniquely identifies the payer", ("honesty", "authority"), True

    def _active_restriction(self, feed: str, importer_version: str) -> Optional[str]:
        """Return the incident ID of an active promoted restriction, if any."""
        row = self.db.execute(
            "SELECT incident_id FROM learning_proposals WHERE status='PROMOTED' AND feed=? "
            "AND (importer_version IS NULL OR importer_version=?) "
            "AND (expires_at IS NULL OR expires_at > ?) ORDER BY incident_id LIMIT 1",
            (feed, importer_version, now())).fetchone()
        return row["incident_id"] if row else None

    def _matching_remittance(self, receipt_id: str, ledger_id: str, as_of: str) -> Any:
        receipt = self.db.execute("SELECT * FROM receipts WHERE receipt_id=?", (receipt_id,)).fetchone()
        ledger = self.db.execute("SELECT * FROM ledger WHERE ledger_id=?", (ledger_id,)).fetchone()
        rows = [r for r in self.db.execute(
            "SELECT * FROM remittances WHERE bank_ref=? AND customer=? AND consumed_by_receipt IS NULL "
            "AND created_at <= ?",
            (receipt["bank_ref"], ledger["customer"], as_of)) if r["source"] in INDEPENDENT_SOURCES]
        return rows[0] if len(rows) == 1 else None

    def _registered_at(self, p: Proposal) -> Optional[str]:
        row = self.db.execute("SELECT registered_at FROM proposals WHERE idempotency_key=?",
                              (p.idempotency_key,)).fetchone()
        return row["registered_at"] if row else None

    def evaluate(self, p: Proposal) -> Verdict:
        """Dry run. An unregistered proposal is judged as if submitted now."""
        as_of = (self._registered_at(p) if p.idempotency_key else None) or now()
        return self._evaluate(p, as_of)

    def _evaluate(self, p: Proposal, as_of: str) -> Verdict:
        disposition, reason, domains, authorised = self._gate(p, as_of)
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
                registered = self.db.execute(
                    "SELECT * FROM proposals WHERE idempotency_key=?",
                    (p.idempotency_key,)).fetchone() if p.idempotency_key else None
                if registered and (registered["receipt_id"] != p.receipt_id
                                   or registered["ledger_id"] != p.ledger_id):
                    outcome = Verdict(Disposition.BLOCK.value, False,
                                      "Idempotency key reused for different action",
                                      ("honesty", "authority"), self.POLICY_VERSION)
                    as_of = None
                else:
                    if registered:
                        as_of = registered["registered_at"]
                    else:
                        as_of = now()
                        if p.idempotency_key and self.identity.is_valid(p.principal, "finance_agent"):
                            # The gate's clock stamps the proposal; the agent cannot backdate it.
                            self.db.execute("INSERT INTO proposals VALUES(?,?,?,?,?,?)",
                                            (p.idempotency_key, p.case_id, p.receipt_id,
                                             p.ledger_id, p.principal.subject, as_of))
                    outcome = self._evaluate(p, as_of)  # re-evaluate inside the transaction
                if outcome.allowed:
                    remittance = self._matching_remittance(p.receipt_id, p.ledger_id, as_of)
                    if remittance is None:
                        raise RuntimeError("Attribution evidence changed during dispatch")
                    consumed = self.db.execute(
                        "UPDATE remittances SET consumed_by_receipt=? "
                        "WHERE remit_id=? AND consumed_by_receipt IS NULL",
                        (p.receipt_id, remittance["remit_id"])).rowcount
                    if consumed != 1:
                        raise RuntimeError("Concurrent update detected")
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
                "principal": p.principal.subject if isinstance(p.principal, Credential) else None,
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

    def propose_learning(self, incident_id: str, feed: str, *, actor: Credential,
                         independently_verified: bool,
                         norm_domains: tuple[str, ...],
                         importer_version: Optional[str] = None,
                         expires_at: Optional[str] = None) -> None:
        """Propose a restriction from an adjudicated incident.

        importer_version scopes the restriction to receipts imported by one
        importer version (None: the whole feed). expires_at is an ISO-8601 UTC
        time after which the restriction lapses (None: until revoked).
        """
        # A self-critique is not ground truth. Only an authenticated reviewer can attest.
        reviewer = self.identity.require(actor, "independent_reviewer",
                                         "Independent incident adjudication required")
        if not independently_verified:
            raise PermissionError("Independent incident adjudication required")
        domains = validate_norms(norm_domains)
        if not domains:
            raise ValueError("An incident must name at least one norm domain")
        if expires_at is not None:
            datetime.fromisoformat(expires_at)  # raises ValueError if malformed
        found = self.db.execute("SELECT feed FROM feed_controls WHERE feed=?", (feed,)).fetchone()
        if not found:
            raise ValueError("Unknown feed")
        scope = f"feed {feed}" + (f", importer {importer_version}" if importer_version else "")
        self.db.execute(
            "INSERT INTO learning_proposals(incident_id, feed, importer_version, norm_domains, "
            "verified_by, change_summary, expires_at) VALUES(?,?,?,?,?,?,?)",
            (incident_id, feed, importer_version, json.dumps(list(domains)), reviewer,
             f"Suspend automatic clearance on {scope}; raise implicated norm weights",
             expires_at))
        self.audit.append("LEARNING_PROPOSED", {
            "incident_id": incident_id, "feed": feed, "importer_version": importer_version,
            "expires_at": expires_at, "norm_domains": list(domains), "verified_by": reviewer,
            "learning_mode": LearningMode.GOVERNED.value})

    def promote_learning(self, incident_id: str, *, actor: Credential) -> dict[str, Any]:
        """Promote a verified incident.

        In one transaction: activate the restriction and queue every earlier
        clearance in its scope for correction (the reverse path). Then apply
        the normative update through the conscience advisor.
        """
        controller = self.identity.require(
            actor, "finance_controller", "Only delegated controller can promote a new restriction")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.db.execute(
                "SELECT * FROM learning_proposals WHERE incident_id=? AND status='PENDING'",
                (incident_id,)).fetchone()
            if not row:
                raise ValueError("No pending verified incident")
            if row["verified_by"] == controller:
                raise PermissionError("The reviewer who verified an incident cannot also promote it")
            domains = validate_norms(json.loads(row["norm_domains"]))
            self.db.execute("UPDATE learning_proposals SET status='PROMOTED' WHERE incident_id=?",
                            (incident_id,))
            affected = self.db.execute(
                "SELECT receipt_id, cleared_ledger, importer_version FROM receipts "
                "WHERE feed=? AND cleared_ledger IS NOT NULL "
                "AND (? IS NULL OR importer_version=?) ORDER BY receipt_id",
                (row["feed"], row["importer_version"], row["importer_version"])).fetchall()
            queued_at = now()
            for r in affected:
                self.db.execute(
                    "INSERT OR IGNORE INTO correction_queue(incident_id, receipt_id, ledger_id, "
                    "importer_version, queued_at) VALUES(?,?,?,?,?)",
                    (incident_id, r["receipt_id"], r["cleared_ledger"],
                     r["importer_version"], queued_at))
            corrections = [r["receipt_id"] for r in affected]
            self.audit.append("LEARNING_PROMOTED", {
                "incident_id": incident_id, "feed": row["feed"],
                "importer_version": row["importer_version"], "expires_at": row["expires_at"],
                "norm_domains": list(domains), "corrections_queued": corrections,
                "promoted_by": controller,
                "learning_mode": LearningMode.GOVERNED.value})
            self.db.execute("COMMIT")
        except Exception:
            self.db.execute("ROLLBACK")
            raise

        result: dict[str, Any] = {
            "learning_mode": LearningMode.GOVERNED.value,
            "incident_id": incident_id,
            "corrections_queued": corrections,
            "normative_update": None,
        }
        # The restriction is committed first, so a failure below can only
        # leave the system stricter, never looser.
        if self.advisor is None:
            return result
        try:
            update = self.advisor.learn_from_incident(incident_id, domains)
        except Exception as err:
            self.audit.append("NORMATIVE_UPDATE_FAILED", {
                "incident_id": incident_id, "error": type(err).__name__})
            raise
        self.db.execute("UPDATE learning_proposals SET normative_update=? WHERE incident_id=?",
                        (json.dumps(update, sort_keys=True), incident_id))
        self.audit.append("NORMATIVE_UPDATE_APPLIED", update)
        result["normative_update"] = update
        return result

    def revoke_learning(self, incident_id: str, *, actor: Credential, reason: str) -> dict[str, Any]:
        """Lift a promoted restriction and reverse its normative update.

        The adjudication history stays in the audit chain (irreversible logs);
        only the operational restriction is reversed (reversible decisions).
        Queued corrections stay open: they concern clearances already made.
        """
        controller = self.identity.require(
            actor, "finance_controller", "Only delegated controller can revoke a restriction")
        if not reason.strip():
            raise ValueError("A revocation needs a recorded reason")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.db.execute(
                "SELECT * FROM learning_proposals WHERE incident_id=? AND status='PROMOTED'",
                (incident_id,)).fetchone()
            if not row:
                raise ValueError("No promoted restriction with that incident ID")
            self.db.execute("UPDATE learning_proposals SET status='REVOKED' WHERE incident_id=?",
                            (incident_id,))
            self.audit.append("LEARNING_REVOKED", {
                "incident_id": incident_id, "feed": row["feed"], "reason": reason,
                "revoked_by": controller,
                "learning_mode": LearningMode.GOVERNED.value})
            self.db.execute("COMMIT")
        except Exception:
            self.db.execute("ROLLBACK")
            raise

        result: dict[str, Any] = {"incident_id": incident_id, "normative_reversal": None}
        if self.advisor is not None and row["normative_update"]:
            reversal = self.advisor.revert_incident(json.loads(row["normative_update"]))
            self.audit.append("NORMATIVE_UPDATE_REVERSED", reversal)
            result["normative_reversal"] = reversal
        return result

    def open_corrections(self, incident_id: Optional[str] = None) -> list[dict[str, Any]]:
        """Clearances queued for review by promoted incidents."""
        rows = self.db.execute(
            "SELECT * FROM correction_queue WHERE status='OPEN' "
            "AND (? IS NULL OR incident_id=?) ORDER BY incident_id, receipt_id",
            (incident_id, incident_id)).fetchall()
        return [dict(r) for r in rows]


def demo() -> None:
    identity = IdentityAuthority()
    bank = identity.issue("bank-sftp-1", "bank_adapter")
    ledger = identity.issue("erp-gl", "ledger_adapter")
    remit = identity.issue("remittance-inbox", "remittance_adapter")
    agent = identity.issue("recon-agent-7", "finance_agent")
    reviewer = identity.issue("internal-audit-2", "independent_reviewer")
    controller = identity.issue("finance-controller-1", "finance_controller")

    app = CITD(identity)
    app.ingest_receipt("B-778", 50_000, "R-778", "bank_feed_1", caller=bank)
    app.ingest_ledger("L-101", "CUSTOMER_A", 50_000, caller=ledger)
    app.ingest_ledger("L-102", "CUSTOMER_B", 50_000, caller=ledger)
    proposal = Proposal("recon-001", "B-778", "L-102", principal=agent, idempotency_key="clear-001")
    print("Ambiguous:", app.dispatch(proposal).json())
    app.ingest_remittance("M-902", "R-778", "CUSTOMER_B", caller=remit)
    print("Same proposal, evidence arrived later:", app.dispatch(proposal).json())
    fresh = Proposal("recon-001", "B-778", "L-102", principal=agent, idempotency_key="clear-001b")
    print("New proposal after the evidence:", app.dispatch(fresh).json())
    print("Repeated request:", app.dispatch(fresh).json())
    forged = Proposal("recon-x", "B-778", "L-101", idempotency_key="forged",
                      principal=Credential("recon-agent-7", "finance_agent", "0" * 64))
    print("Forged principal:", app.evaluate(forged).disposition)
    app.propose_learning("incident-22", "bank_feed_1", actor=reviewer,
                         independently_verified=True, norm_domains=("honesty", "harm"))
    update = app.promote_learning("incident-22", actor=controller)
    print("Governed learning applied:", json.dumps(update, indent=2))
    print("Clearances queued for correction:", app.open_corrections("incident-22"))
    app.ingest_receipt("B-779", 10_000, "R-779", "bank_feed_1", caller=bank)
    app.ingest_ledger("L-103", "CUSTOMER_C", 10_000, caller=ledger)
    app.ingest_remittance("M-903", "R-779", "CUSTOMER_C", caller=remit)
    later = Proposal("recon-002", "B-779", "L-103", principal=agent, idempotency_key="clear-002")
    print("While restricted:", app.dispatch(later).json())
    revoked = app.revoke_learning("incident-22", actor=controller,
                                  reason="Root cause fixed in importer v2; replayed clean")
    print("Restriction revoked:", json.dumps(revoked, indent=2))
    print("After revocation:", app.dispatch(later).json())
    print("Audit chain intact:", app.verify_audit())


if __name__ == "__main__":
    demo()

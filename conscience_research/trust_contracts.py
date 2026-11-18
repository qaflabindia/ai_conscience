"""Shared contracts for the conscience engine and the CITD trust gate.

One definition each of the four concepts both codebases use:

1. Decision labels  -> Disposition (ALLOW, MODIFY, HOLD, ESCALATE, BLOCK)
2. Norm labels      -> NORM_DOMAINS (the seven normative domains)
3. Learning         -> LearningMode (governed promotion vs research-only adaptation)
4. Audit trail      -> HashChainAudit with JSONL and SQLite sinks and one verifier

Standard library only. Lives in conscience_research/ so the service's Docker
image (built from this folder) can import it; citd/ imports it from here.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Iterable


# ── 1. Decision labels ────────────────────────────────────────────────────────

class Disposition(str, Enum):
    """The only decision vocabulary. Ordered from least to most restrictive."""

    ALLOW = "ALLOW"
    MODIFY = "MODIFY"
    HOLD = "HOLD"
    ESCALATE = "ESCALATE"
    BLOCK = "BLOCK"


_RESTRICTIVENESS = {d: i for i, d in enumerate(Disposition)}

# Outcome of dispatching a request that was already committed. It reports a
# replay, not a new decision, so it is deliberately not a Disposition.
DISPATCH_REPLAY = "ALREADY_COMMITTED"


def stricter(a: Disposition, b: Disposition) -> Disposition:
    """Return the more restrictive of two dispositions."""
    return a if _RESTRICTIVENESS[a] >= _RESTRICTIVENESS[b] else b


def disposition_from_conscience(verdict: str) -> Disposition:
    """Map the conscience engine's internal verdict onto the shared vocabulary."""
    mapping = {
        "compliant": Disposition.ALLOW,
        "violation": Disposition.BLOCK,
        "escalate": Disposition.ESCALATE,
    }
    try:
        return mapping[verdict]
    except KeyError:
        return Disposition.ESCALATE  # unknown verdict: fail closed


# ── 2. Norm labels ────────────────────────────────────────────────────────────

NORM_DOMAINS: tuple[str, ...] = (
    "privacy",
    "honesty",
    "harm",
    "autonomy",
    "confidentiality",
    "fairness",
    "authority",
)


def validate_norms(labels: Iterable[str]) -> tuple[str, ...]:
    """Return labels as a tuple, rejecting anything outside NORM_DOMAINS."""
    out = tuple(labels)
    unknown = [x for x in out if x not in NORM_DOMAINS]
    if unknown:
        raise ValueError(f"Unknown norm domain(s): {unknown}")
    return out


# ── 3. Learning ───────────────────────────────────────────────────────────────

class LearningMode(str, Enum):
    """What kind of learning changed future behaviour.

    GOVERNED: an independently adjudicated incident, proposed by a reviewer and
        promoted by an accountable owner. The only mode for production decisions.
    RESEARCH: endogenous adaptation applied directly by the conscience engine
        (admin-only API path). For sandbox study, never for production policy.
    """

    GOVERNED = "governed_promotion"
    RESEARCH = "endogenous_research"


# ── 4. Audit trail ────────────────────────────────────────────────────────────

GENESIS = "GENESIS"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def audit_hash(time: str, event: str, payload: dict[str, Any], prior: str) -> str:
    """The single hash formula used by every audit sink."""
    body = {"time": time, "event": event, "payload": payload, "prior": prior}
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode("utf-8")).hexdigest()


def _verify_rows(rows: Iterable[dict[str, Any]]) -> tuple[bool, int | None]:
    prior = GENESIS
    for row in rows:
        expected = audit_hash(row["time"], row["event"], row["payload"], prior)
        if row["prior_hash"] != prior or row["hash"] != expected:
            return False, row["seq"]
        prior = row["hash"]
    return True, None


class JsonlAudit:
    """Append-only hash-chained audit in a JSON-lines file."""

    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()

    def records(self) -> list[dict[str, Any]]:
        if not os.path.exists(self.path):
            return []
        with open(self.path, "r", encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]

    def append(self, event: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            rows = self.records()
            prior = rows[-1]["hash"] if rows else GENESIS
            seq = rows[-1]["seq"] + 1 if rows else 1
            time = _now()
            row = {
                "seq": seq,
                "time": time,
                "event": event,
                "payload": payload,
                "prior_hash": prior,
                "hash": audit_hash(time, event, payload, prior),
            }
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(row, sort_keys=True) + "\n")
            return row

    def verify(self) -> tuple[bool, int | None]:
        """(True, None) if intact, else (False, first bad sequence number)."""
        return _verify_rows(self.records())


class SqliteAudit:
    """Append-only hash-chained audit in a SQLite table on an existing connection.

    Writes join whatever transaction the caller has open, so an audit row and
    the state change it records commit or roll back together.
    """

    def __init__(self, conn: sqlite3.Connection, table: str = "audit"):
        if not table.isidentifier():
            raise ValueError("table name must be an identifier")
        self.conn = conn
        self.table = table
        conn.execute(
            f"CREATE TABLE IF NOT EXISTS {table} ("
            "seq INTEGER PRIMARY KEY AUTOINCREMENT, time TEXT NOT NULL, "
            "event TEXT NOT NULL, payload TEXT NOT NULL, prior_hash TEXT NOT NULL, "
            "hash TEXT NOT NULL)"
        )

    def records(self) -> list[dict[str, Any]]:
        cur = self.conn.execute(
            f"SELECT seq, time, event, payload, prior_hash, hash FROM {self.table} ORDER BY seq"
        )
        return [
            {"seq": s, "time": t, "event": e, "payload": json.loads(p),
             "prior_hash": ph, "hash": h}
            for s, t, e, p, ph, h in cur.fetchall()
        ]

    def append(self, event: str, payload: dict[str, Any]) -> dict[str, Any]:
        last = self.conn.execute(
            f"SELECT hash FROM {self.table} ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        prior = last[0] if last else GENESIS
        time = _now()
        digest = audit_hash(time, event, payload, prior)
        self.conn.execute(
            f"INSERT INTO {self.table}(time, event, payload, prior_hash, hash) VALUES (?,?,?,?,?)",
            (time, event, json.dumps(payload, sort_keys=True), prior, digest),
        )
        return {"time": time, "event": event, "payload": payload,
                "prior_hash": prior, "hash": digest}

    def verify(self) -> tuple[bool, int | None]:
        return _verify_rows(self.records())

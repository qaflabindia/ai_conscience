# CITD reference gate

A reference implementation of evidence-gated delegation for a synthetic bank-reconciliation case. It is educational and auditable, and it is **not production-ready**.

## Files

- `citd_reference.py`: the trust gate. It uses an in-memory SQLite database, signed role credentials (`IdentityAuthority`), trusted-adapter ingestion, independent-source payer attribution, ALLOW/HOLD/ESCALATE/BLOCK dispositions, idempotent atomic dispatch, and governed learning.
- `agentic_trust_metrics.py`: inference-serving and decision metrics, including verified safe goodput, failure and timeout counts with censored percentiles, and scope-violation counts.
- `tests/`: 64 tests. These are the original 16; 18 for the shared contracts, conscience advice, governed learning, evidence sources and integrity checks; 13 for evidence consumption, amount mismatches and the restriction lifecycle; and 17 for evidence timing, credentials and the metric fixes.

## How it connects to the conscience engine

`citd/` and `conscience_research/` share one set of contracts, defined in `conscience_research/trust_contracts.py`:

| Concept | Single definition | Used by |
|---|---|---|
| Decision labels | `Disposition` (ALLOW, MODIFY, HOLD, ESCALATE, BLOCK); `DISPATCH_REPLAY` for idempotent replays | gate verdicts; the guardrail service's `disposition` field |
| Norm labels | `NORM_DOMAINS` (7 domains); `validate_norms()` | gate verdicts, incidents, advisory scores, `agent.NORMS` (checked at import) |
| Learning | `LearningMode.GOVERNED` (adjudicated incident → reviewer proposes → controller promotes); `LearningMode.RESEARCH` (direct admin adaptation in the service) | gate promotion; the service's audit of mutations |
| Audit | `audit_hash()` plus `SqliteAudit` and `JsonlAudit`, each with `verify()` | gate audit table; the service's `decision_audit.jsonl` (`GET /v1/audit/verify`) |

The integration point is `conscience_research/advisor.py` (`ConscienceAdvisor`):

- **During a decision**, `CITD.evaluate()` runs the deterministic gate first and then asks the advisor to score the agent's `self_assessment`. Advice can only make the result *stricter*: a hard floor caps it at BLOCK, and a flagged norm domain caps it at ESCALATE. If the advisor fails, the result is ESCALATE. Advice can never turn HOLD into ALLOW.
- **After a promoted incident**, `CITD.promote_learning()` activates the restriction (the whole feed, or one importer version of it, optionally until an expiry time), queues every earlier clearance in that scope for correction, and then calls `advisor.learn_from_incident()`. That records the incident in the continuity layer and raises the weight of each implicated norm domain, which tightens its effective threshold for later advice. The restriction is committed first, so a failure here can only leave the system stricter.
- **On revocation**, `CITD.revoke_learning()` (controller only, with a recorded reason) lifts the restriction and calls `advisor.revert_incident()`, which subtracts the weight increase and appends a `revoked` episode. History is never edited. Queued corrections stay open.

## Run

Requires Python 3.10+. The gate uses only the standard library. The conscience engine needs `cryptography`, as listed in `conscience_research/pyproject.toml`.

```bash
python3 citd/citd_reference.py
python3 -m unittest discover -s citd/tests -v
```

## Identities and evidence timing

- Every caller passes a `Credential` issued by the `IdentityAuthority` the gate was built with: `CITD(identity)`. A credential is an HMAC-SHA256 tag over subject and role, so a role string, a forged tag, a relabelled credential or one from another authority is refused. Proposals carry the agent's credential as `principal`.
- The reviewer who verifies an incident cannot also promote it, even with a controller credential under the same subject. Audit entries name the authenticated subject (`by`, `principal`, `verified_by`, `promoted_by`, `revoked_by`).
- The gate stamps each proposal with its own clock the first time it is dispatched. Only remittances created at or before that time can attribute the payer, so evidence that arrives after a HOLD needs a new proposal (new idempotency key). Late evidence still counts as a conflict.

## Known limitations

- The identity key is held in-process, so credentials show separable privileges, not production authentication. A deployment would use mTLS or tokens from an external identity provider. `independently_verified` is still an attestation flag, now from an authenticated reviewer.
- Evidence timing uses ingestion time at the gate, not the time the bank or customer created the document. Receipts and ledger entries carry no timestamp.
- The audit chain is local and is not anchored outside the operator's trust domain.
- All eleven probe defects (P1–P11) in `paper_review/REFERENCE_CODE_REVIEW.md` are now closed (§4.1–§4.3).
- Revoking an incident subtracts the weight increase it caused. If other norm updates happened in between, the restored weight is an approximation, clamped at the engine's floor.
- Queued corrections are listed, not acted on. Reversing a clearance is left to a human workflow.
- The code shows that some safeguards are mechanically feasible. It does not show artificial conscience, certified trustworthiness or any measured reduction in real-world errors.

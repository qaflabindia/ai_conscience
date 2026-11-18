# CITD reference gate

A reference implementation of evidence-gated delegation for a synthetic bank-reconciliation case. It is educational and auditable, and it is **not production-ready**.

## Files

- `citd_reference.py`: the trust gate. It uses an in-memory SQLite database, trusted-adapter ingestion, independent-source payer attribution, ALLOW/HOLD/ESCALATE/BLOCK dispositions, idempotent atomic dispatch, and governed learning.
- `agentic_trust_metrics.py`: inference-serving and decision metrics, including verified safe goodput.
- `tests/`: 34 tests. These are the original 16 plus 18 that cover the shared contracts, conscience advice, governed learning, evidence sources and integrity checks.

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
- **After a promoted incident**, `CITD.promote_learning()` suspends the feed (the policy restriction) and then calls `advisor.learn_from_incident()`. That records the incident in the continuity layer and raises the weight of each implicated norm domain, which tightens its effective threshold for later advice. The feed restriction is committed first, so a failure here can only leave the system stricter.

## Run

Requires Python 3.10+. The gate uses only the standard library. The conscience engine needs `cryptography`, as listed in `conscience_research/pyproject.toml`.

```bash
python3 citd/citd_reference.py
python3 -m unittest discover -s citd/tests -v
```

## Known limitations

- Identities are **demo caller strings**, not authentication. `independently_verified` is a flag supplied by the caller.
- The audit chain is local and is not anchored outside the operator's trust domain.
- Open defects from the review (`paper_review/REFERENCE_CODE_REVIEW.md` §1) are **not fixed here**:
  - P1: one remittance can attribute several receipts that share a bank reference.
  - P3: a partial payment returns BLOCK.
  - P5/P6: learning has no revoke path and no reverse path to earlier clearances.
  - P9–P11: metric blind spots.
- The code shows that some safeguards are mechanically feasible. It does not show artificial conscience, certified trustworthiness or any measured reduction in real-world errors.

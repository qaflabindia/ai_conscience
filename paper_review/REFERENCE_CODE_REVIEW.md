# Review of the CITD Reference Code (`Agentic_AI_Trust_Reference_Code.zip`)

**Package contents:** `citd_reference.py` (252 lines), `test_citd_reference.py` (8 tests), `agentic_trust_metrics.py` (131 lines), `test_agentic_trust_metrics.py` (8 tests), `IMPLEMENTATION_README.md`.
**How it was checked:** I read every file in full, ran the 16 supplied tests and the demo, and ran 11 probe scripts against suspected edge cases (P1–P11 below). Everything ran on an extracted copy in a scratch folder. Nothing from the zip was added to the repository.

---

## 0. Bottom line

- **The paper's artefact claim is true.** All 16 tests pass, and the demo produces HOLD → ALLOW → ALREADY_COMMITTED as the paper describes. My earlier review finding **F3 ("fabricated artefact claim") was wrong.** The artefact exists; it was simply not in the repository. F3 has been corrected in the review.
- **The code is a sound minimal gate.** It keeps the agent away from writes, makes the ambiguous case HOLD, makes writes atomic and idempotent, and puts learning behind propose/promote. It is better engineered than the conscience prototype in `conscience_research/`.
- **It fails the paper's own headline scenario.** If a bank reference is truncated so that two receipts share it, **one remittance authorises two clearances (P1)**. That is the §7.3 shared-cause failure, and the gate returns ALLOW twice.
- **It is complementary to `conscience_research/`, not redundant with it.** The two share no code and solve different problems. They do duplicate four *concepts* with incompatible meanings: dispositions, learning, audit and norm labels. §4 below covers this.

---

## 1. Defects confirmed by probes

| # | File | Finding | Probe result | Severity |
|---|---|---|---|---|
| P1 | `citd_reference.py:155-163` | **Evidence is never consumed.** Uniqueness is checked across *customers per bank_ref*, but not across *receipts per remittance*. If two receipts share a truncated ref and customer B has two ₹50,000 invoices, one remittance clears both. | `ALLOW ALLOW` | **High.** This is exactly the paper's §7.3 scenario. |
| P3 | `:147-148` | A partial or split payment (amount mismatch) returns **BLOCK** ("impermissible"). In reconciliation this is a routine exception and should be HOLD or ESCALATE. | `BLOCK` | Medium (domain correctness) |
| P4 | `:33`, `:131` | `principal` is a default field on the proposal, so every proposal claims to be `finance_agent`. Caller identities (`caller="bank_adapter"`, `actor="finance_controller"`) are plain strings. | Self-declared | Medium. The README admits it, but the paper presents it as "separable privileges". |
| P5 | `:201-232` | `independently_verified` is a boolean that the caller supplies, so incident verification is self-attested. There is **no un-suspend, expiry or rollback path**, which contradicts the paper's own "moral lock-in" and "reversible decisions" arguments. | Only `propose_learning`, `promote_learning` exist | Medium |
| P6 | `:224` | Suspending a feed stops *future* clearances but does **not locate or flag past clearances** from that feed. The paper's "reverse path" (§6.2) and correction queue (§7.3) are missing, and receipts do not record an importer version. | Cleared rows untouched | Medium–High |
| P7 | `:105`, `:123` | `original_hash` is computed and stored but **never verified**. Rewriting a remittance's customer is not detected. | No verify method | Medium. The stored hash looks like a safeguard but does nothing. |
| P8 | `:86-94`, `:109-114` | The audit hash chain **has no verifier**. Ledger ingestion is **not audited at all**. The README correctly says the chain is not externally anchored. | Event list lacks ledger ingest | Low–Medium |
| P2 | `:116-124`, `:242-243` | `created_at` is the ingestion time, and nothing checks that the remittance *predates* the matching decision, which the paper requires (§7.1). The demo itself ingests the remittance after the first HOLD. | Not enforced | Low–Medium |
| P9 | `agentic_trust_metrics.py:74-76` | Goodput requires `tpot is not None`, so **single-token responses can never count as "good"** even when every latency SLO passes. Short classifier-style outputs, such as a one-token disposition, are always excluded. | `1 completed, 0 good` | Medium (metric bug) |
| P10 | `:73`, `:83-85` | Percentiles are computed over **successful requests only**. Timeouts and failures disappear from TTFT and E2E percentiles, which flatters P99. The paper itself says timeout handling must be declared. | p99 = 0.1 s despite a 30 s timeout | Medium |
| P11 | `:114-115` | An autonomous commit on an **ineligible** case is silently dropped from every count. That is the most safety-relevant event of all (an action outside scope), and it becomes invisible. | All counters 0 | **High** (measurement blind spot) |

Other problems found by reading the code:
- The remittance has no amount field, so a remittance for any amount can attribute a receipt.
- `independent_source` is always the constant `"customer_remittance"`, so "independence" is a label, not a property of how the evidence was acquired.
- `MAX_AUTO_AMOUNT = 100_000` sits next to a docstring that says "minor currency units", yet the demo treats 50,000 as ₹50,000.
- `promote_learning` reads the pending proposal *before* `BEGIN IMMEDIATE` (a small check-then-act race).
- There is **no concurrency test**, so the "Concurrent update detected" branch is never exercised.
- Reusing an idempotency key for a different action (BLOCK) and the amount-mismatch path are also untested.

## 2. What is good (keep)

- **The agent never writes.** Only adapters ingest data. `dispatch()` re-evaluates the proposal inside `BEGIN IMMEDIATE` and uses guarded `UPDATE … WHERE cleared_* IS NULL` statements plus an idempotency table. That is the right pattern, implemented correctly.
- **The ambiguous case HOLDs, and it is tested.** Conflicting remittances also HOLD.
- **Idempotency is handled carefully**, including the key-reuse check that returns BLOCK.
- **Learning is two-step.** A proposal by a reviewer is promoted by a controller, and `test_verified_incident_requires_promote` checks that **promotion changes a later verdict**. That is precisely the "binding" property (requirement R7 in v2), and the test is the most valuable one in the package.
- **The metrics handle labels honestly.** Pending is not counted as correct, empty populations give `None` instead of 0, TPOT is undefined for one token, and percentiles use nearest rank over raw samples.
- **The README is candid about its limits.** It belongs in the paper's Statements section almost verbatim.

## 3. Relevance to the paper

| Paper element | In the reference code? |
|---|---|
| Agent is not the execution authority (v1 §4.1, v2 §5.1) | **Yes** (modulo P4) |
| Disposition set | ALLOW, HOLD, ESCALATE, BLOCK yes. **MODIFY is never produced.** `ALREADY_COMMITTED` exists but is not in the paper's vocabulary. |
| Self-judgment J and independent challenger (v1 §6.2 pseudocode) | **Absent.** There is no agent, LLM, self-judgment or challenger. `normative_domains` are hard-coded labels per branch. |
| NSM, NPG and BUM conscience layers | **Absent.** "Learning" means feed suspension, not norm revision. That fits v2 (§5.4), but means v1's "conscience-informed" claim has no code behind it. |
| Single-use authorisation token, signed policy, 60 s expiry (v1 pseudocode) | **Absent.** `policy_version` is a constant `finance-recon-v1`, while the paper's JSON example says `finance-recon-v3`. |
| §6.3 response fields (`dominant_issue`, `required_evidence`, `escalation_owner`, `binding_update_applied`) | **Absent.** `Verdict` has only disposition, allowed, reason, domains and version. |
| EvidenceSufficient as uniqueness (v2 §5.2) | Partial. Uniqueness is checked over customers but not over evidence consumption (P1) or timing (P2). |
| RiskWithinTolerance (v2 §5.2) | A per-transaction amount cap only. **No stratum UCB and no aggregate exposure limit per root cause.** |
| Shared-cause containment and reverse path (v1 §7.3) | Future suspension only (P6). |
| VSG (v1 §9.4, v2 §8) | Rate only. **No yield**, so the rate goes up with volume (review M8). |
| "Not presently determinable" adjudication label (v1 §8.1) | **Missing.** Only correct, incorrect and pending exist. |
| Nine inference metrics (v1 §9.1) | About 7 of 9 are computable. ITL and TPOT percentiles are not reported. This part is **low relevance** to the trust thesis, consistent with the review's advice to compress §9.1. |

**Net relevance:** the code is a faithful, minimal demonstration of the **workflow and execution half** of the paper. It contains **nothing of the conscience half**. This supports v2's reframing ("evidence-gated delegation") and undercuts v1's title.

## 4. Redundancy

**Inside the package:**
- `original_hash` and `digest()` on rows are written and never read (P7). Either verify them or remove them.
- `Verdict.policy_version` duplicates `CITD.POLICY_VERSION`, and the constructor default repeats the literal.
- `independent_source` is a constant column. `normative_domains` labels are consumed by nothing.
- `InferenceTrace.token_generation_time` is the numerator of `tpot`. This is harmless, but only one of them is reported.

**Against `conscience_research/` (already in the repo):** there is no code duplication, but four concepts are duplicated with incompatible meanings:

| Concept | `conscience_research/` | `citd_reference.py` | Recommendation |
|---|---|---|---|
| Disposition vocabulary | compliant / violation / escalate | ALLOW / HOLD / ESCALATE / BLOCK / ALREADY_COMMITTED | Adopt the CITD set everywhere. Map conscience verdicts onto it. |
| Learning | Weight-based norm binding (`binding_update`) | Feed suspension via propose/promote | Keep the CITD path for production. Treat the conscience BUM as the sandbox arm (arm E in v2). |
| Audit | Fernet-encrypted `moral_history.jsonl` | SQLite hash chain | Use one append-only sink with a verifier, anchored outside the agent's trust domain. |
| Norm labels | Scored over 7 domains with thresholds | Hard-coded labels per branch | Let the conscience engine supply *advisory* domain scores into `Verdict`. They must never authorise anything. |

The two codebases are complementary: `citd_reference` is the gate, and `conscience_research` is the normative scorer. Neither calls the other today, so the paper's claim that conscience "informs" trust has **no integration point in code**.

### 4.1 Resolution (19 Nov 2026)

The redundancy described above has been removed. The package now lives in the repository as `citd/`.

- **One set of contracts.** `conscience_research/trust_contracts.py` defines `Disposition`, `NORM_DOMAINS`, `LearningMode` and the hash-chained audit, with one hash formula and `verify()` for both the SQLite and JSONL sinks. The gate and the guardrail service both use it. The service now returns a `disposition` field, and its old `verdict` is kept as an internal detail.
- **The conscience engine is connected.** `conscience_research/advisor.py` is the single integration point:
  - `CITD.evaluate()` consults it, and advice can only tighten a decision (hard floor → BLOCK, flagged domain → ESCALATE, advisor failure → ESCALATE).
  - `CITD.promote_learning()` feeds the adjudicated incident's norm domains back through it, so one governed learning event both suspends the feed and tightens the implicated norms.
- **One meaning of learning.** Governed promotion is the only path for production decisions. Direct mutation through the service's admin API is audited as `endogenous_research`.
- **Fields that were written but never read are now used:**
  - **Stored hashes:** receipt, ledger and remittance hashes are re-checked on every decision (HOLD on mismatch), and there is a `verify_evidence_integrity()` method.
  - **Evidence source:** the constant `independent_source` column became `source`. Only `INDEPENDENT_SOURCES` can attribute a payer; derived copies (`agent_extracted`, `ledger_copy`) are kept for lineage but neither confirm nor conflict.
  - **Norm labels:** they are validated against `NORM_DOMAINS`, recorded in every DISPATCH audit event, required on incidents, and drive the normative update on promotion.
- **One lock** (`agent.STATE_LOCK`) guards the conscience state for both the service and the advisor.
- **Tests:** `citd/tests` has 34 (16 original + 18 new). `conscience_research/tests` has 29 (25 + 4 new). All pass. The scenario harness is unchanged at 1.000.

Defects P1, P3, P5, P6 and P9–P11 were still open after this change; P1, P3, P5 and P6 are resolved in §4.2.

### 4.2 Gate defects P1, P3, P5, P6 resolved (19 Nov 2026)

- **P1, evidence consumption.** `remittances.consumed_by_receipt` is set in the same transaction as the clearance (the UPDATE must affect exactly one unconsumed row, or the dispatch rolls back). The gate returns HOLD when a bank reference is shared by more than one open receipt, and only unconsumed independent remittances can attribute a payer. The truncated-reference scenario now gives `HOLD`, and a consumed remittance cannot clear a second receipt.
- **P3, amount mismatch.** A partial, combined or overpayment returns `HOLD` with the reason "… payment: allocation evidence required", instead of BLOCK. There is no separate `required_evidence` field; the reason string carries it.
- **P5, reversible learning.** `propose_learning` takes an optional `importer_version` scope and an optional ISO-8601 `expires_at`. `revoke_learning(incident_id, actor="finance_controller", reason=…)` marks the incident REVOKED, writes `LEARNING_REVOKED`, and reverses the normative update through `ConscienceAdvisor.revert_incident()`. The continuity history stays append-only: a `revoked` episode is added, and continuity rebuilds skip the withdrawn incident. A suspension is now derived from active PROMOTED rows (not a mutable flag), so revocation and expiry lift it without editing history. `independently_verified` is still a caller-supplied flag (see Known limitations).
- **P6, reverse path.** Receipts record `importer_version`. On promotion, every earlier clearance in the restriction's scope (the feed, or one importer version of it) is queued in `correction_queue` in the same transaction, listed in the `LEARNING_PROMOTED` audit payload, and returned as `corrections_queued`. `open_corrections()` lists them. Revocation leaves queued corrections open, because they concern clearances already made.
- **Return shape.** `promote_learning` now returns `{learning_mode, incident_id, corrections_queued, normative_update}`; the advisor's weight change is under `normative_update`.
- **Tests:** `citd/tests` has 47 (34 + 13 new: shared reference, consumption, partial and over-payment, importer scope, revoke, expiry, continuity rebuild, permissions). `conscience_research/tests` still has 29. All pass, and the scenario harness is unchanged at 1.000.

P7 and P8 were closed in §4.1 (stored hashes are verified, ledger ingestion is audited, the chain has `verify()`). Still open: P2 (evidence timing), P4 (self-declared identities) and the metric defects P9–P11.

## 5. Recommended changes (priority order)

1. **Fix P1.** Add `remittances.consumed_by_receipt`, set it in the same transaction as the clearance, and HOLD when a remittance is already consumed or when the bank_ref maps to more than one open receipt. Add a test for the truncated-reference case.
2. **Fix P11.** Count `autonomous_commit and not eligible` as a scope-violation counter. It must never be dropped.
3. **Fix P9 and P10.** Let single-token responses meet goodput on TTFT and E2E alone. Report failure and timeout counts, and compute percentiles both with timeouts (censored at the timeout value) and without.
4. **Add the reverse path (P6).** Record `importer_version` on receipts, and have `promote_learning` return or queue every earlier clearance that shares the suspended root-cause key.
5. **Make learning reversible (P5).** Add `revoke_learning` (controller only, audited) and an optional expiry.
6. **Partial payments → HOLD (P3),** with `required_evidence` filled in.
7. **Verify or delete `original_hash` (P7).** Add `verify_audit_chain()` (P8) and audit ledger ingestion.
8. **Metrics:** add `not_determinable`, verified safe *yield* (VSG / eligible), Clopper–Pearson intervals and per-stratum breakdowns.
9. **Tests:** add concurrency (two connections to a file-backed DB), idempotency-key reuse, amount mismatch and the P1 regression.
10. **Put the package in the repository** (for example under `citd_reference/`), so the paper's reproducibility statement points to something reviewers can find.

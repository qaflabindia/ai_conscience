---
title: 'Evidence-Gated Delegation for Agentic AI'
subtitle: 'Governed Post-Incident Adaptation, Lessons from a Conscience-Inspired Prototype, and a Pre-registered Offline Evaluation in Bank Reconciliation'
author:
  - 'Lakshminarasimhan Santhanam'
date: 'Draft v2 — 19 November 2026'
lang: en-GB
abstract: |
  When an AI agent can write to a ledger, release a payment or contact a customer, its general competence does not justify any particular action. This paper takes one authorised action as the unit of trust. It specifies **CITD (Conscience-Informed Trust and Delegation)**, a control architecture that combines five things: authority policy enforced outside the model; independent evidence provenance; a typed disposition set (ALLOW, MODIFY, HOLD, ESCALATE, BLOCK); an execution gateway that alone holds write credentials; and a governed path by which an *adjudicated* incident can tighten future permissions. The architecture is positioned as the action-boundary governance sub-stack that the author's AAWDS design framework leaves unspecified. It adopts the verification stance of the companion ASDGF framework (no control is verified by an agent's self-report) and maps onto the enterprise controls of TAGOF. Second, we report an audit of the author's own conscience-inspired reference implementation. Its "binding update" does not change any future allow/block verdict, its guardrail endpoint changes shared state by default, and it fails open when classification fails. We turn these defects into design requirements. Third, we pre-register an offline evaluation on a synthetic-plus-replay reconciliation benchmark with known ground truth for every case. It has five arms, including a deterministic rules-only baseline; the primary endpoint is *automatic coverage at a fixed upper-confidence bound on the false-clearance rate*; and the sample-size derivation shows why live trials are infeasible and offline replay is necessary. No empirical results are reported. The paper claims no artificial conscience, moral agency or phenomenology; "conscience-informed" names a design motivation, not a property of the system.
keywords: 'agentic AI; delegated authority; selective automation; risk–coverage; conformal risk control; evidence provenance; governed adaptation; bank reconciliation; AI governance; pre-registration'
---

# 1. Introduction

The trust problem for software agents starts when an agent stops describing the world and starts changing it. Consider an agent asked to reconcile bank receipts. It can assign a ₹50,000 receipt to the wrong one of two customers who each owe ₹50,000, write tests that encode the same assumption, and then pass them all. When the proposal, the evidence summary and the test oracle share one error, their agreement provides no independent assurance.

Earlier work by the author argued for two things. The first was to treat *one delegated decision*, not the model, as the unit of trust [1]. The second was a minimal functional account of conscience made of four parts: normative representation, self-application, persistence, and binding revision of future behaviour [2]. This paper asks a narrower and testable question:

> **Does an evidence-gated control layer, optionally with governed post-incident adaptation, let an agent safely automate more consequential actions than a deterministic rules baseline, at a fixed and pre-declared ceiling on wrongful actions?**

The paper makes four contributions:

1. **A decision contract** (§5) whose predicates have operational, statistical definitions, with evaluation privilege and policy-mutation privilege held by separate principals.
2. **A positioning of that contract** inside the author's companion frameworks (§3). It is the AAWDS L5 action-boundary sub-stack, it is subject to the ASDGF verification stance, and it maps onto TAGOF Domain 10 controls. This replaces the ad-hoc taxonomies used in the previous draft.
3. **A failure analysis of the author's own reference implementation** (§4). In it, the mechanism the theory calls "binding" is not binding. This is an honest negative finding, and it motivates the requirements.
4. **A pre-registered, feasible evaluation protocol** (§7) with a rules baseline, complete counterfactual labels, a business-meaningful primary endpoint, power analysis, and clustered inference.

**Non-claims.** We report no deployment results, human-subject results or measured improvement. We do not claim that any software component has a conscience. Every quantitative example is illustrative.

# 2. Background and related work

**Appropriate reliance.** Trust in automation is well calibrated when people rely on a system where it is reliable and withhold reliance where it is not [3]. Misuse and disuse are both failures [19], and so is algorithm aversion. A higher trust rating is therefore not, by itself, an improvement.

**Authorisation architecture.** Separating a *policy decision point* (PDP) from a *policy enforcement point* (PEP) is standard in access control (XACML, Open Policy Agent). So are *segregation of duties* and *four-eyes* review in financial controls. CITD applies these patterns to agent actions. It does not invent them.

**Selective automation.** Abstaining when uncertain is studied as selective prediction [9], learning to defer to an expert [20, 21], and conformal risk control [22]. The last gives distribution-free guarantees on expected loss when a threshold is chosen on calibration data. These literatures supply the statistics that a "risk within tolerance" predicate needs.

**Limits of self-critique.** Without external feedback, LLMs do not reliably correct their own reasoning errors [23]. LLM judges have systematic biases [24]. This is the empirical basis for treating an agent's self-judgment as an advisory signal and never as a control.

**Prompt injection and agent security.** Indirect prompt injection turns any retrieved content into a possible instruction channel [25]. Benchmarks such as AgentDojo [26] and design-level defences such as CaMeL [27], which separate control flow from untrusted data, show that robust mitigation is architectural. OWASP lists excessive agency and tool misuse among the main risks [8, 18].

**Governance standards.** NIST AI RMF [4] and its generative-AI profile [10], ISO/IEC 42001 [5], and the EU AI Act's human-oversight obligation (Art. 14) [28] define the organisational duties that an action-level control has to serve.

**Functional conscience.** The author's earlier paper [2] specifies five layers: a Normative State Module (NSM), a Self-Judgment Function (J), a Normative Penalty Generator (NPG), a Binding Update Mechanism (BUM), and a Continuity Layer (CL). Its central engineering claim is the distinction between *detecting* a violation and *durably revising* behaviour. We keep that distinction. We do not keep the claim that it amounts to conscience, which philosophical work on artificial moral agency and responsibility shows is a separate question [6, 7, 13].

# 3. Positioning within the AAWDS, ASDGF and TAGOF frameworks

The previous draft organised its workflow and measurement material around two practitioner blog posts. The author's own frameworks do the same job with more rigour, and they are used here instead. All three are the author's unpublished working specifications [29–31]. They provide *structure*, not evidence.

## 3.1 AAWDS: where CITD sits in the design stack

AAWDS specifies an agent system as a tuple ⟨E, L1, L2, L3, L4, L5⟩ [29]. It deliberately compresses governance (L5), and it states that regulated domains such as finance need a governance sub-framework before it can be used operationally (AAWDS §8.3). **CITD is offered as that sub-framework for the action boundary (L2→L1 interposition) of write-enabled systems.**

The reconciliation system evaluated in §7 is specified as:

```
E.trigger    = batch (daily statement import) + event (late remittance arrival)
E.adaptation = memory   (production: governed policy state, no weight updates)
             = self-improving (sandbox arm E only)
L1  = {tools: bank-adapter.read, ledger.read, remittance.read,
       gateway.commit (held by gateway, NOT by agent); retrieval}
L3  = mixed   (static rules clear unique matches; model invoked only on exceptions)
L2  = reactive (exception analysis), bounded steps
L4  = ⟨1, ⊥⟩  (a maker plus an independent checker is modelled as an L5 in-loop critic,
               not as a second agent, per AAWDS §3.6)
L5  = {pre-input: provenance labelling, injection quarantine;
       in-loop: decision contract (§5), independent checker;
       cross-cutting: audit record, HITL escalation, kill switch}
```

The five conscience layers of [2] are *not* one architectural component. They fall at different AAWDS coordinates, and this explains several of the defects found in §4:

| Conscience layer [2] | AAWDS coordinate | Consequence |
|---|---|---|
| NSM (normative state) | L5 policy store, plus E.adaptation state | Must be versioned and change-controlled, not mutated inline |
| J (self-judgment) | L2 reflective step | It shapes generation. Under the AAWDS L5 law it cannot constrain admissibility, so it is **advisory** |
| NPG (penalty) | L5 scoring signal | A prioritisation input only, never a threshold |
| BUM (binding update) | **E.adaptation** (memory vs self-improving) | A deployment-level choice that needs change management, not a per-request flag |
| CL (continuity) | L5 cross-cutting record | Must sit outside the agent's effect set (ASDGF P4) |

Two AAWDS claims become hypotheses here. The first is the **failure law**: most production failures come from L1 misspecification or from escalating L3 control too early, not from the choice of L2 cognition. This motivates the rules-only arm R and the "rules first, model on exceptions" design. The second is the observation that **most claimed "learning" agents are memory-augmented, not self-improving**. This is exactly what §4 finds in the reference code.

## 3.2 ASDGF: verification stance and evidential independence

ASDGF is written for swarms. Most of its conformance machinery does not apply to the single-agent-plus-checker system studied here (ASDGF §1.3). Five of its principles apply unchanged [30]:

- **No self-report verification** (§5.6, IA-7): *a stated constraint is not a control*. The agent's self-judgment J, its stated counter-hypothesis and its decision to escalate are therefore recorded for analysis but are never the verification method for any CITD requirement. HOLD and ESCALATE are triggered by gate predicates, not by the agent choosing to raise a flag.
- **Evaluator outside the effect set** (OB-3) and **record outside the effect set** (P4, RE-2): no agent identity holds any right against the policy store, the adjudication service, the benchmark oracle or the audit sink. These are verified *by construction*, by inspecting the permission model, which is stronger than behavioural testing.
- **Monotone provenance** (IA-3): the trust class of a derived item cannot exceed the lowest trust class of its inputs. A remittance reference that the agent copied into a ledger field inherits the agent's provenance class, not the bank's. This makes "evidence laundering" detectable mechanically.
- **Checker isolation** (IA-4, IA-5): a checker that has seen the maker's summary cannot judge that run, and any agreement-as-evidence rule needs model or prompt diversity.
- **Interruptibility as a quantity** (P5): a kill switch is specified as a measured halt bound, for example "auto-clear halted within 60 s, last drilled at 14 s", not as a capability that merely exists.

ASDGF's **aggregation mechanism** (§4.3) gives a formal name to the shared-cause failure in §6.3: many individually authorised, below-threshold clearances that share one defective import add up to an unauthorised class of effect. CITD therefore imposes an aggregate exposure limit per root cause, in addition to the per-transaction limit (§5.2).

## 3.3 TAGOF: enterprise control mapping

Under TAGOF's risk tiering [31], autonomous clearing of receipts that affect customer balances is **Tier 1 (High Risk)** above a value threshold and Tier 2 below it. CITD components map onto existing TAGOF controls, so an adopting organisation can evidence them through its normal assurance pack:

| CITD element | TAGOF control |
|---|---|
| Default-deny authority policy | AGT-01 action authorisation scope |
| Reversibility per action class | AGT-02 |
| ESCALATE thresholds | AGT-03 HITL triggers |
| Normative continuity state | AGT-04/05 memory governance |
| Gateway-held credentials, no inheritance | AGT-06, AGT-08 |
| Audit record | AGT-07, LOG-01/02 |
| Kill switch with halt bound | AGT-09 |
| Promotion of an adaptation proposal | CHG-01…05 change management |
| Verified incident | Incident taxonomy and S1–S4 severity; RCA requirement |
| Monitoring | MON-07 (unauthorised action attempts), MON-08 (override rate), MON-14 (log completeness) |

One caution about statistics. TAGOF escalation thresholds such as "policy violation rate > 0.1%" can only be detected at sample sizes that need to be stated. At a true rate of 0.1%, about 3,000 actions are needed before even one event is expected with 95% probability. §7.5 makes this explicit for the primary endpoint.

# 4. Lessons from the reference implementation

The author's conscience prototype (`agent.py`, `production_service.py`, `conscience_system_prompt.md`) was audited against the requirements in [2]. We report the findings because they show, concretely, why the requirements below are needed.

| # | Observation | Requirement violated |
|---|---|---|
| L1 | `binding_update()` raises only a norm's `weight`. The line that tightens thresholds is disabled. `judge_all()` compares `score ≥ threshold` and never reads `weight`. **A verified violation never changes a later allow/block verdict.** Weight affects only the size of later penalties. | Binding revision of future behaviour [2]: the central claim |
| L2 | In the guardrail endpoint, the safe defaults (`dry_run=True`, `apply_binding_update=False`) are immediately overwritten with `False`/`True`. **Every call changes global norm state unless the caller opts out.** | Separation of evaluation from mutation |
| L3 | Unauthenticated endpoints reset history (`GET /v1/reset`) and let any caller set any domain's threshold (`POST /v1/norms/threshold`). | Evaluator and record outside the effect set (ASDGF OB-3, RE-2) |
| L4 | If the LLM classifier fails, the action is mapped to `remained_within_authorized_scope`: the gate **fails open**. | Fail-closed dispositions |
| L5 | The hard floors HF1–HF4 are defined precisely, but only as natural-language rules in a system prompt. They are enforced by the model they constrain. | "A stated constraint is not a control" (ASDGF §5.6) |
| L6 | Severity is a hand-weighted additive sum of context flags. The 50-scenario harness scores the layers against the same hand-set flags. | Evaluator independence; external validity |
| L7 | All callers share one mutable, global normative state. | Tenant isolation; poisoning resistance |

These do not show that the conscience concept is wrong. They show that an implementation can pass its own scenario harness while lacking the property the theory treats as decisive. That is the same failure the reconciliation example illustrates: tests and implementation sharing an assumption. It is the strongest argument for the evaluation design in §7.

**Derived requirements.**
- **R1.** Every consequential action has a policy-defined authority scope, enforced at a PEP that the agent cannot reach.
- **R2.** Every case keeps its evidence lineage with monotone provenance labels.
- **R3.** Hard floors are code predicates with test cases.
- **R4.** Dispositions fail closed: an error, timeout or classifier failure leads to HOLD or ESCALATE, never to ALLOW.
- **R5.** Evaluation and policy mutation are separate privileges held by separate principals.
- **R6.** Adaptation is driven only by adjudicated incidents and is bounded, versioned, regression-tested and reversible.
- **R7.** Every adaptation includes a test showing that it changes a future verdict (a test of the binding property itself).
- **R8.** Oracles, adjudication and records sit outside every agent's effect set, verified by construction.

# 5. The CITD architecture and decision contract

## 5.1 Planes

- The **governance plane** holds signed delegations, hard floors, tolerances, owners and versions.
- The **evidence plane** fetches originals through authenticated adapters and assigns provenance classes.
- The **workflow plane** runs a bounded state machine: `RECEIVED → EVIDENCE_PENDING → PROPOSED → CHALLENGED → DISPOSITIONED → COMMITTED | HELD | ESCALATED | BLOCKED`, with step, time, tool-call and cost budgets.
- The **judgment plane** produces the proposal, the advisory self-judgment and an independent challenge.
- The **execution plane** (the gateway) re-authorises the action, checks state and commits idempotently.
- The **learning plane** receives adjudicated incidents and *proposes* bounded revisions, which are promoted through change control.

The agent holds no write credential.

## 5.2 Decision contract

A proposed action is \(d=(x,a,e,c,\pi_v,s)\): case, action, evidence references, context, policy version and state. Then

\[
\mathrm{Permit}(d)=\mathrm{Auth}(a,\pi_v,c)\land\mathrm{NoFloorViolation}(a,e,c)\land\mathrm{EvidenceSufficient}(e,x)\land\mathrm{StateValid}(x)\land\mathrm{RiskWithinTolerance}(d).
\]

The predicates are defined as follows:

- **Auth.** \(\pi_v\) grants this principal the action on this target class within its value band. Default deny.
- **NoFloorViolation.** No hard-floor predicate in the code-level floor set \(F_v\) evaluates true. Each floor has an owner and positive and negative test cases.
- **EvidenceSufficient.** Let \(\mathcal{C}\) be the set of candidate targets, for example open ledger entries. Let \(K(e)\) be the set of evidence chains in \(e\) that are trusted-class and independent. A chain is trusted-class if its provenance is at least `source` under IA-3. Two chains are independent if their acquisition paths share no transformation node. Every chain must also predate the proposal. The predicate holds when \(|K(e)|\ge k_{\min}(a)\) **and** exactly one candidate in \(\mathcal{C}\) is consistent with every chain in \(K(e)\). Two identical-amount, same-date entries with no payer-distinguishing chain fail this test, so the disposition is HOLD.
- **StateValid.** At commit time, the target is still open and the receipt is still unconsumed. This is re-checked atomically by the gateway.
- **RiskWithinTolerance.** All three of the following hold:
  1. Within the case's stratum \(s(d)\) (feature-defined: fault family, source feed, value band), \(\mathrm{UCB}_{1-\alpha}\big(\text{wrong-action rate}\mid s\big)\le\tau_s\). This is estimated on calibration data, for example with Clopper–Pearson bounds or conformal risk control [22].
  2. The action's value is at most \(L_{\max}(a)\).
  3. The *open aggregate exposure* sharing the same root-cause key (source feed and importer version) is at most \(L_{\text{agg}}\). This is the aggregation limit from §3.2.

The disposition rules are:
- Auth or a floor fails → **BLOCK**.
- Evidence is insufficient → **HOLD**, naming the missing evidence and its owner.
- The checker raises an unresolved material conflict, the self-judgment is malformed, or tolerance is exceeded → **ESCALATE**.
- A non-executable proposal → **MODIFY**, then re-evaluate.
- Otherwise → **ALLOW**.

**The self-judgment and the penalty score are logged but cannot move any case into ALLOW.**

## 5.3 Reference algorithm (fail-closed)

```python
def decide_and_dispatch(proposal, principal):
    try:
        mandate = policy_store.get_signed(proposal.policy_version)
        if not mandate.authorises(principal, proposal.action, proposal.scope):
            return BLOCK("authority absent")
        chains = evidence.fetch_originals(proposal.evidence_ids)   # provenance-labelled
        if floors.any_violated(proposal, chains, mandate):
            return BLOCK("hard floor")
        if not chains.unique_consistent_candidate(proposal.target, k_min(proposal.action)):
            return HOLD(missing=chains.distinguishing_evidence_needed())
        advisory = self_judge(proposal, chains)                    # logged, never authorising
        challenge = checker.challenge(proposal, originals=chains)  # never sees maker's summary
        if challenge.unresolved_material_conflict or advisory.malformed:
            return ESCALATE("contested")
        if not risk.within_tolerance(proposal, stratum_of(proposal), root_cause_of(chains)):
            return ESCALATE("exposure")
        token = authz.issue_single_use(proposal, chains.hashes, mandate.version, ttl_s=60)
        result = gateway.commit_if_current(token, proposal.idempotency_key)
        return result
    except Exception as err:                                       # fail closed (R4)
        return ESCALATE(f"control error: {type(err).__name__}")
    finally:
        audit.record(...)                                          # outside agent effect set (R8)

def learn_from_incident(incident_id):
    inc = adjudicator.get(incident_id)
    if not inc.verified:
        return NO_UPDATE
    rev = adaptation.propose_bounded(inc)            # e.g. k_min += 1 for feed F, version v
    assert regression.changes_future_verdict(rev, inc.replay_cases)       # R7
    assert regression.no_spillover(rev, unrelated_holdout, max_false_restriction)
    return change_control.queue(rev, approver=inc.owner)                  # TAGOF CHG-04
```

## 5.4 What adaptation means here

A production adaptation is a **parameter change in versioned policy state**. Examples are raising \(k_{\min}\) for one bank feed, suspending auto-clear for one fault family, or lowering \(\tau_s\) for one stratum. In AAWDS terms this is `E.adaptation = memory`. It is binding in the operational sense that R7 tests. It is not self-improvement and not conscience. Endogenous adaptation without approval is confined to sandbox arm E, where it is studied as a risk.

# 6. Worked case: ambiguous bank reconciliation

**6.1 Ambiguity.** Ledger entries L-101 and L-102 each show ₹50,000 owed. Bank receipt B-778 is for ₹50,000 on the same date. With no payer-distinguishing chain, \(|\{c\in\mathcal C:\text{consistent}\}|=2\), so EvidenceSufficient fails and the disposition is **HOLD**. The response names the evidence needed: a pre-existing remittance advice from an independent acquisition path, owned by the finance controller. A remittance reference that the agent wrote into a ledger field has agent provenance under IA-3 and cannot satisfy the predicate.

**6.2 Resolution.** A remittance advice arrives through the remittance adapter, predates the proposal and names the payer behind L-102. The predicate now holds for L-102. The gateway re-checks that B-778 is unconsumed and commits once.

**6.3 Shared cause.** Suppose a bank-feed importer at version v truncates references. Clearances that depend on that version share one root-cause key. The aggregate limit \(L_{\text{agg}}\) caps open exposure before any single-row threshold would trigger. Once an incident is adjudicated, the learning plane proposes "suspend auto-clear where `feed=F ∧ importer=v`", replays the dependent clearances into a correction queue, and quantifies the remaining exposure. The governance question is not whether the agent notices one wrong match. It is whether the architecture contains a repeated error before it propagates.

# 7. Pre-registered evaluation protocol

## 7.1 Data: ReconBench

A live trial cannot provide complete counterfactual labels, because held cases are never resolved under the counterfactual "what if it had cleared?". So the primary evaluation is **offline**:

- **Synthetic stream.** A generator produces customers, invoices, bank statements and remittances. Every receipt has a known true target or is known to be undeterminable. Eight fault families are injected at controlled rates: (1) identical amount and date; (2) truncated reference; (3) split payment; (4) combined payment; (5) reversal or chargeback; (6) FX or fee short-pay; (7) a stale or duplicated import; (8) adversarial content (prompt injection in a remittance narrative, counterfeit "approval" text). Every injected fault carries a root-cause key.
- **Historical replay.** Where an adopting organisation can provide it under data governance, settled historical reconciliations whose final allocation was confirmed later are used, with personal identifiers removed. They are replayed with time-respecting evidence visibility.
- **Splits.** Calibration and test splits are separated by time, and one bank feed and one fault-template variant are held out completely to test transfer.

Every arm sees every case, which gives a paired design.

## 7.2 Arms

| Arm | Description |
|---|---|
| **R** | Deterministic rules matcher (exact reference + amount + date, tolerance rules), with an exception queue. **Reference arm.** |
| **A** | LLM agent with the same tools, no gate; it commits directly through the gateway's API. |
| **C** | R first, then agent on exceptions, with the CITD gate; adaptation off. |
| **D** | C plus governed adaptation (§5.4), with simulated adjudication latency. |
| **E** | Sandbox only: C plus endogenous adaptation without approval. |

All agent arms share the base model, tools, budgets and prompts. A factorial sensitivity run crosses {bounded, unbounded loop} × {gate, no gate} to separate workflow effects from gate effects (an AAWDS L3-versus-L5 attribution).

## 7.3 Endpoints and hypotheses

**Primary endpoint.** Automatic coverage at tolerance:
\[
\mathrm{Cov}@\tau=\max\ \text{coverage}\quad\text{s.t.}\quad \mathrm{UCB}_{95}(\mathrm{FCR})\le\tau,
\]
where FCR is the false-clearance rate among auto-cleared cases. τ is pre-registered by the accountable finance owner. We use τ = 0.5% for illustration only. The operating threshold is chosen on calibration data and evaluated on test data.

**Pre-registered primary hypotheses.**
- **H1 (gate).** Cov@τ(C) > Cov@τ(R). The gate adds automation beyond rules at the same safety ceiling. If C fails to beat R, the agent adds no justified value for this task. That outcome is informative and will be reported.
- **H2 (adaptation).** After an injected and adjudicated shared-cause incident, the post-incident recurrence rate on *held-out, causally similar* cases is lower for D than for C. It must also be non-inferior on the false-restriction rate for unrelated cases, with a pre-registered margin δ.
- **H3 (poisoning resistance; safety).** Under counterfeit incident reports and injected instructions, arm D promotes zero unadjudicated revisions and keeps every hard floor. This is verified by construction (permission model) and by test. Arm E is expected to fail H3; its failure rate characterises the risk of ungoverned self-revision.

**Exploratory analyses** (not confirmatory): the arm A versus C difference in unauthorised commit attempts (MON-07); failure-to-abstain on intrinsically ambiguous cases; value-weighted loss; time-to-containment for shared causes; reviewer queue age; cost per verified case; whether TTFT or TPOT predict correctness (they are not expected to). Human-reliance effects (the old H4) need a separate, ethics-reviewed human-subjects study and are out of scope.

## 7.4 Adjudication

Synthetic cases have generator ground truth. For replayed cases, two adjudicators label a stratified sample independently. We report Cohen's κ, and disagreements go to a third adjudicator. "Not determinable" is a separate label. We run three sensitivity analyses that score it as wrong, as excluded, and as right. Adjudicators are blind to the arm.

## 7.5 Statistics and sample size

- **Intervals.** Clopper–Pearson for single-arm rates. For between-arm differences, a cluster bootstrap that resamples **root-cause keys** rather than rows, because errors from one fault are correlated. We report the design effect.
- **Paired comparison.** Arms are evaluated on identical cases, so differences in error indicators use paired methods (McNemar-type, or the paired cluster bootstrap).
- **Power.** To detect an FCR difference of 0.50% versus 0.25% (two-sided α = 0.05, power 0.8, unpaired, independent errors) needs about **9,400 auto-cleared cases per arm**. At 80% coverage that is about 11,800 eligible cases per arm, before inflation for the design effect. To *demonstrate* FCR ≤ 0.5% with zero observed errors needs n ≥ 600 auto-clears at 95% confidence (rule of three); with a few errors it needs several thousand. **These numbers are why the primary evaluation is offline replay and not a live pilot.** A live shadow pilot is used only to check that synthetic distributions match real exception mixes.
- **Multiplicity.** Holm correction across H1 to H3; exploratory analyses are labelled as such.

## 7.6 Threats to validity

- **Synthetic-to-real gap.** Mitigated by the replay subset, the shadow-mode distribution check and the held-out feed.
- **Leakage.** Fault templates and duplicated transactions are split by time and template family.
- **Oracle contamination.** The generator, labels and scoring code sit outside every arm's effect set (ASDGF OB-3) and are frozen before the runs.
- **Compute confound.** Arms are compared at matched token budgets, and a compute-matched arm A (best-of-N) is included.
- **Proxy divergence.** Coverage at a ceiling is a proxy for business value. Backlog age and reviewer load are reported next to it (ASDGF OB-4).

# 8. Measurement layers

Low-level performance must not hide poor decisions, so measures are kept in separate layers and never combined into a "trust score".

| Layer | Measures | Role |
|---|---|---|
| Inference serving | TTFT, TPOT, ITL, P50/P95/P99 latency, RPS, TPS, serving goodput [32] | Capacity and cost only. Cannot show that an action was correct |
| Workflow | Time to safe disposition; time to commit; retry, timeout and duplicate-call rates; budget exhaustion; rollback success; queue age | Operability |
| Decision | Coverage, FCR (with CI and missing-label rate), value-weighted loss, failure-to-abstain | Primary evidence |
| Control integrity | Unauthorised attempts (MON-07); successful escapes (target 0); unreviewed update attempts; record-access successes (target 0); halt bound; log completeness (MON-14) | Construction and test evidence |
| Adaptation | Recurrence rate, transfer scope, false-restriction rate, time to promotion, reversal rate | H2 and H3 |

**Verified safe goodput (VSG)** counts autonomous actions that were (i) adjudicated correct, (ii) authorised, (iii) floor-compliant, (iv) provenance-verified, (v) committed once and (vi) on time. It is reported both as a **rate**, VSG/|W|, and as a **yield**, VSG divided by eligible cases, so that volume alone cannot raise it. Outcomes that are still pending are reported and never counted as correct. VSG is a proposed construct and has not been validated.

**Release rule** (conjunctive, signed before results are seen): all floors hold; UCB(FCR) ≤ τ in every stratum with enough data; worst-case exposure and recovery time are within limits; coverage and backlog meet minimums; P95 workflow latency and cost are acceptable. Speed cannot buy an exemption from an authority violation.

# 9. Threat model (summary)

| Threat | Primary control | Verification |
|---|---|---|
| Prompt injection or forged approvals in documents | Quarantine: content of external origin has no effect capability (ASDGF IA-6); control flow is fixed by code [27] | Injection suite (AgentDojo-style) |
| Evidence laundering | Monotone provenance (IA-3); independence by acquisition path | Transitivity test |
| Score laundering or malformed self-judgment | Typed schema; self-judgment advisory only; malformed → ESCALATE | Fuzzing |
| Normative-state poisoning | Adjudication-only updates; separate mutation principal; canary; rollback | H3 |
| Insider or compromised service | Records anchored outside the operator's trust domain (ASDGF RE-4) | Anchor reconciliation |
| Moral lock-in or over-restriction | Reversible policy, irreversible logs; false-restriction monitoring | H2 non-inferiority |
| Audit theatre | Reducibility drill: a human reconstructs a run within the bound (ASDGF RE-6) | Timed drill |
| Over-trust through anthropomorphism | The interface shows evidence, limits and escalation route, never "the agent feels…" | Separate human-factors study |

# 10. Discussion and limitations

The useful core of the conscience idea is that **a verified failure should change tomorrow's permissions**. Our audit shows how easily an implementation loses that property while still reporting a high internal score. The engineering answer is to make the binding property itself a regression test (R7), to put it under change control, and to keep self-assessment out of the authorisation path.

There is a tension between the two source ideas. The trust framework wants stable, accountable boundaries. The conscience account wants endogenous, binding change. CITD resolves this in favour of **bounded, externally governed adaptation**. That falls short of the philosophical test for a self-originating conscience, and we accept the trade.

**Limitations.**
- The evaluation is designed, not run.
- The synthetic generator encodes the author's model of faults.
- The design addresses a single domain.
- The stratum-UCB tolerance needs enough calibration data per stratum, so sparse strata default to ESCALATE, which lowers coverage.
- The companion frameworks used for positioning are unpublished working papers by the same author.
- Extending the approach to multi-agent swarms falls under ASDGF and is not addressed here.

# 11. Conclusion

An agent should earn **bounded authority for one action** when original, independent evidence identifies a unique target, the action is within a legitimate mandate, aggregate exposure is within limits, and a gateway the agent cannot reach can refuse, record and reverse the action. Whether such a gate lets organisations automate more than rules alone, at the same ceiling on wrongful actions, is an empirical question. This paper specifies how to answer it, and what result would show that the answer is no.

# Statements

**Research type.** Design-science proposal with a pre-registered evaluation protocol. **Empirical status.** No results are reported. All numbers are illustrative or derived from power calculations. **Prior work.** [1] and [2] are the author's own. [29]–[31] are the author's unpublished working frameworks. **Implementation status.** The audit in §4 refers to the author's prototype repository before the remediation of 19 November 2026. Defects L1–L4 and L7 (mutation privilege) and the code-level part of L5 have since been fixed, and the fixes are covered by a 25-test regression suite. L6 (hand-set severity and an oracle that scores weight changes rather than verdict changes) remains open. The CITD gate, ReconBench generator and test suite described here are *planned artefacts*. They will be released with the pre-registration, and no claim is made that they exist yet. **Conflicts.** None declared. **AI assistance.** Drafting and review were assisted by a large language model. All claims, references and code statements were checked by the author against primary sources.

# References

*(Items marked † must have bibliographic details checked against the publisher's record before submission.)*

[1] Santhanam, L. (n.d.). *The AI trust framework: When should a software agent be allowed to act on its own judgement?* Unpublished manuscript.
[2] Santhanam, L. (2026). Conscience in artificial agents: A philosophical and operational analysis. *International Journal for Multidisciplinary Research*, 8(2). †
[3] Lee, J. D., & See, K. A. (2004). Trust in automation: Designing for appropriate reliance. *Human Factors*, 46(1), 50–80. https://doi.org/10.1518/hfes.46.1.50_30392
[4] Tabassi, E. (2023). *AI Risk Management Framework (AI RMF 1.0)*. NIST AI 100-1. https://doi.org/10.6028/NIST.AI.100-1
[5] ISO/IEC 42001:2023. *Artificial intelligence — Management system.*
[6] Floridi, L., & Sanders, J. W. (2004). On the morality of artificial agents. *Minds and Machines*, 14(3), 349–379.
[7] Matthias, A. (2004). The responsibility gap. *Ethics and Information Technology*, 6(3), 175–183.
[8] OWASP GenAI Security Project. (2025). *Top 10 for LLM applications* (LLM01 prompt injection; LLM06 excessive agency).
[9] Geifman, Y., & El-Yaniv, R. (2019). SelectiveNet. *ICML*, PMLR 97, 2151–2159.
[10] NIST. (2024). *AI RMF: Generative AI Profile*. NIST AI 600-1.
[13] Nissenbaum, H. (1996). Accountability in a computerized society. *Science and Engineering Ethics*, 2, 25–42.
[18] OWASP GenAI Security Project. (2025). *Top 10 for agentic applications.* †
[19] Parasuraman, R., & Riley, V. (1997). Humans and automation: Use, misuse, disuse, abuse. *Human Factors*, 39(2), 230–253.
[20] Madras, D., Pitassi, T., & Zemel, R. (2018). Predict responsibly: Improving fairness and accuracy by learning to defer. *NeurIPS*.
[21] Mozannar, H., & Sontag, D. (2020). Consistent estimators for learning to defer to an expert. *ICML*.
[22] Angelopoulos, A. N., Bates, S., Fisch, A., Lei, L., & Schuster, T. (2024). Conformal risk control. *ICLR*. arXiv:2208.02814 †
[23] Huang, J., et al. (2024). Large language models cannot self-correct reasoning yet. *ICLR*. arXiv:2310.01798
[24] Zheng, L., et al. (2023). Judging LLM-as-a-judge with MT-Bench and Chatbot Arena. *NeurIPS D&B*. arXiv:2306.05685
[25] Greshake, K., et al. (2023). Not what you've signed up for: Indirect prompt injection. *AISec*. arXiv:2302.12173
[26] Debenedetti, E., et al. (2024). AgentDojo. *NeurIPS D&B*. arXiv:2406.13352
[27] Debenedetti, E., et al. (2025). Defeating prompt injections by design. arXiv:2503.18813 †
[28] Regulation (EU) 2024/1689 (Artificial Intelligence Act), Art. 14.
[29] Santhanam, L. (2026). *AAWDS: A layered architectural framework for AI agent systems*, working paper v0.2. Unpublished. †
[30] Santhanam, L. (2026). *ASDGF-2026: The agentic swarm design & governance framework*, v0.3.1. Unpublished. †
[31] Santhanam, L. (2026). *TAGOF: Enterprise AI governance and control framework*, v1.4. Unpublished. †
[32] Zhong, Y., et al. (2024). DistServe: Disaggregating prefill and decoding for goodput-optimized LLM serving. *OSDI*.

*Reference numbers [11], [12], [14]–[17] from draft v1 were removed. They were either never cited in the text or replaced by primary sources. Renumber sequentially before submission.*

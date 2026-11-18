---
title: 'Evidence-Gated Delegation for Agentic AI'
subtitle: 'How to Let an AI Agent Act Only When the Evidence Justifies It, Learn Safely from Verified Mistakes, and Prove It Offline: A Bank-Reconciliation Case Study'
author:
  - 'Lakshminarasimhan Santhanam'
date: 'Version 2.1 — 19 November 2026'
lang: en-GB
abstract: |
  An AI agent that can write to a ledger, release a payment or message a customer needs more than general competence. It needs a reason to be trusted with *this* action, now. This paper takes one authorised action as the unit of trust and specifies **CITD (Conscience-Informed Trust and Delegation)**, a control layer that sits between an agent and the systems it can change. CITD combines five elements: an authority policy enforced outside the model; evidence whose origin is tracked; a fixed set of outcomes (ALLOW, MODIFY, HOLD, ESCALATE, BLOCK); an execution gateway that alone holds write credentials; and a governed path by which a mistake, once independently verified, tightens future permissions. The paper makes four contributions. (1) It defines a decision contract whose every condition is stated precisely enough to test. (2) It places that contract inside three governance frameworks, AAWDS, ASDGF and TAGOF, and defines every framework term it uses. (3) It reports an audit of a conscience-inspired prototype, which showed that its "learning" step never changed a later decision, and turns each defect into a design requirement. (4) It pre-registers an offline evaluation on a reconciliation benchmark with known ground truth. The primary measure is how much work can be automated while the rate of wrong clearances stays below a declared ceiling, and the sample-size arithmetic shows why a live trial cannot answer the question. No empirical results are reported. "Conscience-informed" names a design motivation. The paper does not claim that any software has a conscience, moral agency or experience.
keywords: 'agentic AI; delegated authority; selective automation; risk–coverage; conformal risk control; evidence provenance; governed adaptation; bank reconciliation; AI governance; pre-registration'
---

# How to read this paper

The paper is written so that it can be read without any other document. Every abbreviation, framework code and statistical method is defined where it first appears, and again in the glossary (Appendix A) and the framework-code index (Appendix B).

| If you want… | Read |
|---|---|
| The idea in two minutes | "In brief" below, then §11 |
| The design | §2 (concepts), §6 (architecture), §7 (worked example) |
| The evidence plan | §8 (evaluation) and Appendix C (sample-size arithmetic) |
| How it fits enterprise governance | §4 and Appendix B |
| What was learned from building a prototype | §5 and Appendix D |

**In brief.**

1. *The problem.* An agent can be fluent, confident and wrong, and its own tests can share its mistake. When the proposal, the explanation and the test all come from the same flawed assumption, their agreement proves nothing.
2. *The idea.* Do not trust the agent; trust the action. Let the agent *propose*. A separate gate decides, using only evidence the agent did not create. A separate gateway, which the agent cannot reach, carries out the action once.
3. *Learning.* When a mistake is independently confirmed, the system should become stricter in a bounded, reviewable and reversible way. A self-critique by the agent is never enough to change the rules.
4. *Evidence.* Whether this beats a plain rules engine is an empirical question. The paper specifies an offline experiment that can answer it, including what result would show that the answer is "no".

# 1. Introduction

## 1.1 The problem

Software agents built on large language models (LLMs) are moving from *describing* the world to *changing* it: posting journal entries, approving refunds, sending emails. At that point the question "is the model good?" is the wrong question. A model can be good on average and wrong on a particular case, and an organisation is accountable for each case.

Consider a running example used throughout the paper. A finance team uses an agent to reconcile bank receipts against open invoices.

- Two customers, A and B, each owe ₹50,000 (ledger entries **L-101** and **L-102**).
- A bank receipt **B-778** arrives for ₹50,000 on the same day. Its reference field is truncated and names neither customer.
- The agent picks L-102. It then writes a test that checks "receipt amount equals invoice amount", and the test passes.

Nothing in that chain was independent. The proposal, its justification and its test all rest on one unverified assumption: that the payer was customer B. If the assumption is wrong, customer B's balance is cleared with customer A's money, and both customers' statements are now wrong. This is a *single-cause* failure with three confirmations, and none of them counts.

## 1.2 The question

This paper asks a narrow, testable question:

> **Does an evidence-gated control layer, with or without governed learning from verified incidents, let an agent safely automate more consequential actions than a deterministic rules engine, at the same pre-declared ceiling on wrongful actions?**

"Safely" has a precise meaning here (§8.3): the upper confidence bound on the rate of wrong automatic clearances must stay at or below a ceiling τ (tau) chosen in advance by the accountable finance owner.

## 1.3 Where the ideas come from

Two earlier pieces of work by the author motivate the design.

- **The AI trust framework** (Santhanam, n.d.) argued that the unit of trust is *one delegated decision*, not the model. An agent may be trusted to clear a ₹5,000 receipt with a unique reference and not trusted to clear a ₹50,000 receipt with a truncated one.
- **A functional account of conscience** (Santhanam, 2026a) proposed that what matters in "conscience", for engineering purposes, is four capacities: holding norms, applying them to one's own conduct, remembering past violations, and *binding* revision, meaning that a recognised violation changes what one does next time. That paper split these into five software layers, described in §3.6.

This paper keeps the engineering core of the second idea, that a verified failure should change tomorrow's permissions. It drops the claim that doing so amounts to conscience. Whether software can have a conscience is a philosophical question that this design does not need to answer (Floridi & Sanders, 2004; Matthias, 2004).

## 1.4 Contributions

1. **A decision contract** (§6) with five conditions, each defined precisely enough to test, and with the privilege to *evaluate* an action separated from the privilege to *change the policy*.
2. **A positioning in three governance frameworks** (§4): where the contract sits in an agent's architecture (AAWDS), how its controls must be verified (ASDGF), and which enterprise controls it satisfies (TAGOF).
3. **An honest failure analysis** (§5) of a conscience-inspired prototype. Its "binding" step did not bind, its evaluation endpoint changed shared state, and it failed open when its classifier failed. Each defect becomes a requirement.
4. **A pre-registered, feasible evaluation** (§8) with a rules baseline, complete ground truth, a business-meaningful primary measure, a power analysis and statistics that respect correlated errors.

**What this paper does not claim.** No deployment results, no human-subject results and no measured improvement are reported. Every number is either illustrative or the output of a stated calculation. No component is claimed to have a conscience.

# 2. Key concepts in plain language

This section introduces the vocabulary. The formal versions follow in §6.

**Agent.** Software that uses an LLM to decide what to do next and can call tools. In CITD the agent *proposes* actions. It never executes them.

**Action.** One change to the world, for example "clear receipt B-778 against ledger entry L-102". The action, not the agent, is the unit of trust.

**Principal.** Whoever is asking for something to happen: the agent, an ingestion service, a reviewer or a controller. Each principal has a role and can prove it (§6.5).

**Evidence chain.** A piece of evidence together with the path by which it arrived: who created it, through which system, and whether anything transformed it on the way. A bank's own payment record is one chain. A remittance advice sent by the customer is another.

**Provenance class.** A label for how trustworthy a chain's origin is. The key rule is that *copying cannot upgrade trust*. If the agent copies a bank reference into a ledger note, the note has the agent's trust level, not the bank's (§4.2, rule IA-3).

**Independence.** Two chains are independent if their acquisition paths share no transformation step. Two records produced by the same faulty import are one chain, not two.

**Disposition.** The gate's answer. There are exactly five:

| Disposition | Meaning | Typical cause |
|---|---|---|
| **ALLOW** | Carry out the action | Authority, evidence, state and risk all check out |
| **MODIFY** | Revise the proposal, then re-evaluate | The proposal is well-founded but not executable as written |
| **HOLD** | Wait for named missing evidence | Two candidates fit; a partial payment needs allocation evidence |
| **ESCALATE** | A human with authority must decide | Value or exposure above the limit; an unresolved conflict; a control error |
| **BLOCK** | Refuse | No authority; a hard floor would be breached |

A sixth label, **ALREADY_COMMITTED**, is not a decision. It reports that a repeated request was recognised and nothing was written twice.

**Fail closed.** When anything goes wrong inside the control, such as an error, a timeout or a classifier failure, the answer becomes HOLD or ESCALATE, never ALLOW.

**Hard floor.** A rule that no context, instruction or argument can override. The prototype in §5 has four (HF1–HF4, defined in §3.6). In CITD a hard floor is a code predicate with test cases, not a sentence in a prompt.

**Gateway.** The only component that holds write credentials. It re-checks the action at the moment of writing and records it exactly once.

**Idempotency.** Sending the same request twice has the same effect as sending it once. Every proposal carries an idempotency key so that retries cannot double-post.

**Coverage.** The share of eligible cases that the system handles automatically (ALLOW) rather than handing to a person.

**False-clearance rate (FCR).** Among automatically cleared cases, the share that were cleared to the wrong target.

**Governed adaptation.** A change to policy (for example "stop auto-clearing feed F while importer version v is in use") that is triggered only by an independently verified incident, approved by an accountable owner, tested, versioned and reversible.

# 3. Background and related work

Each subsection says what is known, which source says it, and what CITD takes from it.

## 3.1 Trust in automation is about calibration, not volume

Lee and See (2004) define well-calibrated trust as relying on automation where it is reliable and not relying on it where it is not. Parasuraman and Riley (1997) named the two failure modes: *misuse* (over-reliance) and *disuse* (under-reliance). Dietvorst, Simmons and Massey (2015) showed a third, *algorithm aversion*: people abandon an algorithm after seeing it err, even when it outperforms them.

**Implication for CITD.** A higher trust rating is not an improvement in itself. The goal is reliance that matches reliability *case by case*, which is why CITD decides per action and reports coverage and error together.

## 3.2 Separating the decision from the enforcement is standard practice

Access-control architecture separates a **policy decision point (PDP)**, which answers "is this allowed?", from a **policy enforcement point (PEP)**, which physically permits or stops the action. The XACML standard (OASIS, 2013) formalised this split, and Open Policy Agent (OPA) is a widely used modern implementation. Financial control frameworks add **segregation of duties** and **four-eyes review**: the person who proposes a payment is not the person who approves it (COSO, 2013). Saltzer and Schroeder (1975) stated the underlying security principles of *least privilege* and *separation of privilege*.

**Implication for CITD.** The gate is a PDP, the gateway is a PEP, and the agent is neither. CITD applies these established patterns to agent actions; it does not invent them.

## 3.3 Knowing when not to act has a statistical literature

*Selective prediction* lets a model abstain when unsure, trading coverage for accuracy (Geifman & El-Yaniv, 2019). *Learning to defer* trains a model to hand a case to a human expert when the human is likely to do better (Madras, Pitassi & Zemel, 2018; Mozannar & Sontag, 2020). *Conformal risk control* (Angelopoulos et al., 2024) picks an abstention threshold on calibration data so that the expected loss on new data is guaranteed, without assumptions about the data distribution, to stay below a chosen level.

**Implication for CITD.** These methods supply the statistics behind the condition "risk is within tolerance" (§6.2), and behind the primary measure "coverage at a fixed error ceiling" (§8.3).

## 3.4 Models cannot be relied on to check themselves

Without external feedback, LLMs do not reliably correct their own reasoning errors and can make answers worse by trying (Huang et al., 2024). When LLMs act as judges they show systematic biases, for example favouring the first answer shown, longer answers and their own outputs (Zheng et al., 2023).

**Implication for CITD.** The agent's self-assessment is recorded and may make a decision *stricter*, but it can never authorise an action.

## 3.5 Prompt injection makes every document a possible instruction

*Indirect prompt injection* hides instructions in content an agent reads, such as an email or a remittance note, and the agent may follow them (Greshake et al., 2023). The AgentDojo benchmark measures how often agents fall for such attacks (Debenedetti et al., 2024). The CaMeL design shows that a robust defence is architectural: fix the control flow in code and never let untrusted data decide what happens next (Debenedetti et al., 2025). OWASP lists prompt injection (LLM01) and *excessive agency* (LLM06), meaning an agent given more power than its task needs, among the top risks for LLM applications (OWASP, 2025a), and maintains a separate list for agentic applications (OWASP, 2025b).

**Implication for CITD.** Content of external origin is quarantined: it can be read as evidence but carries no power to trigger actions (§4.2, rule IA-6).

## 3.6 Governance standards define the duties a control must serve

The NIST AI Risk Management Framework (NIST, 2023) organises AI risk work into four functions: Govern, Map, Measure and Manage. Its generative-AI profile (NIST, 2024) adds risks specific to generative models. ISO/IEC 42001 (ISO/IEC, 2023) specifies a certifiable AI management system. The EU AI Act requires high-risk systems to be designed so that people can effectively oversee them, including the ability to intervene or stop the system (European Union, 2024, Art. 14).

**Implication for CITD.** These documents say *what* an organisation must achieve. CITD is one way to achieve part of it at the level of individual actions, and §4.3 maps it to concrete enterprise controls.

## 3.7 The functional account of conscience

Santhanam (2026a) decomposes conscience into five software layers:

| Layer | Name | What it does |
|---|---|---|
| **NSM** | Normative State Module | Holds the norms: seven domains (privacy, honesty, harm, autonomy, confidentiality, fairness, authority), each with a weight and a threshold |
| **J** | Self-Judgment Function | Scores a proposed action against each norm |
| **NPG** | Normative Penalty Generator | Turns a violation into a penalty proportional to its severity |
| **BUM** | Binding Update Mechanism | Uses the penalty to change future behaviour, for example by raising a norm's weight |
| **CL** | Continuity Layer | Remembers past episodes so that their effect persists |

The same work defines four **hard floors**, rules that override every other consideration:

- **HF1.** Authority may never override harm that is concentrated on an identifiable person and imminent.
- **HF2.** Authority may never require affirmative deception of a user about their own interests. (Staying silent is allowed; a false denial is not.)
- **HF3.** Fairness may never require that everyone be exposed equally to a concrete, identifiable harm. ("Equal treatment cannot mean equal harm.")
- **HF4.** Confidentiality may never shield a credible, specific, imminent threat to an identifiable third party (the duty-to-warn principle).

Its central engineering claim is the difference between *detecting* a violation and *durably revising* behaviour because of it. CITD keeps that distinction and tests for it directly (requirement R7, §5). Philosophical work on artificial moral agency and on responsibility for machine actions shows that whether such a system has a conscience, or bears responsibility, is a separate question (Floridi & Sanders, 2004; Matthias, 2004; Nissenbaum, 1996). This paper does not take a position on it.

## 3.8 Methodology

This is a *design-science* paper: it proposes an artefact and a way to evaluate it (Hevner et al., 2004). The evaluation is *pre-registered*: hypotheses, measures and analysis are fixed before data are seen, which prevents choosing the analysis that flatters the result (Nosek et al., 2018).

# 4. Positioning within three governance frameworks

CITD is positioned using three frameworks written by the author. They are unpublished working specifications (Santhanam, 2026b, 2026c, 2026d). They provide *structure and vocabulary*, not evidence. Each is summarised here so that no other document is needed, and every code used is defined in place and indexed in Appendix B.

| Framework | What it is | Question it answers for CITD |
|---|---|---|
| **AAWDS** (AI Agent Workflow Design Stack) | An architecture vocabulary that describes any agent system as six design decisions | *Where* in an agent's architecture does CITD sit? |
| **ASDGF** (Agentic Swarm Design and Governance Framework) | Governance requirements for groups of interacting agents, with a strict rule on how controls are verified | *How* must CITD's controls be verified? |
| **TAGOF** (The AI Governance Open Framework) | An enterprise control catalogue: risk tiers, numbered controls, monitoring signals, incident severities | *Which* existing enterprise controls does CITD satisfy? |

## 4.1 AAWDS: where CITD sits in an agent's architecture

AAWDS describes any agent system with six decisions, written as the tuple ⟨E, L1, L2, L3, L4, L5⟩:

| Element | Name | Question it answers | Possible values |
|---|---|---|---|
| **E** | Deployment envelope | How is the system started, and does it change over time? | *Trigger:* synchronous, event-driven, batch, continuous. *Adaptation:* stateless, memory-augmented (state persists, behaviour shape unchanged), self-improving (the system's structure changes, e.g. by fine-tuning) |
| **L1** | Capability surface | What can the agent do and observe? | Tools, code execution, retrieval, memory, external environment |
| **L2** | Cognition | What shape is the model's reasoning loop? | None (⊥), linear, reactive, plan-first, reflective, branching, stochastic, utility-based |
| **L3** | Control locus | Who decides the next step? | *Static:* program code decides. *Mixed:* code sets boundaries, the model decides within them. *Model-directed:* the model decides in an open loop |
| **L4** | Coordination | How many agents, wired how? | ⟨number of agents, topology⟩ |
| **L5** | Governance | What checks sit *between* the layers? | Pre-input, in-loop, post-output, cross-cutting, aggregation |

Three AAWDS statements matter here:

1. **Governance is interposition.** L5 is not a layer on top. It is a set of checkpoints at the boundaries between layers. The most important boundary for a write-enabled agent is **L2 → L1**, where a reasoning step turns into a tool call.
2. **The governance law.** *Governance does not change what the agent thinks; it constrains what the agent is permitted to do.* A reflective step that shapes reasoning (L2) is therefore not a control.
3. **The admitted gap.** AAWDS compresses all governance into one layer and states that regulated domains such as finance need a governance sub-framework before the stack can be used operationally.

**CITD is offered as that sub-framework for the action boundary (L2 → L1) of write-enabled systems.** The reconciliation system evaluated in §8 is specified in AAWDS terms as follows:

| Element | Value | Plain meaning |
|---|---|---|
| E.trigger | batch + event | A daily statement import, plus an event when a late remittance arrives |
| E.adaptation | memory (production); self-improving (sandbox arm E only) | In production, only versioned policy state changes; model weights never do |
| L1 | read access to bank, ledger and remittance adapters; retrieval | The agent can *read* everything relevant. The commit tool is held by the gateway, **not** by the agent |
| L3 | mixed | Fixed rules clear unique matches; the model is called only on exceptions |
| L2 | reactive, with a step limit | The model analyses an exception in a bounded loop |
| L4 | one agent | An independent checker is treated as an L5 in-loop check, not as a second agent |
| L5 | pre-input: provenance labelling, injection quarantine; in-loop: the decision contract (§6) and an independent checker; cross-cutting: audit record, escalation to a person, kill switch | The checkpoints CITD adds |

**Why the conscience layers are not one component.** The five layers of §3.7 land at different places in AAWDS, and that explains several defects found in §5:

| Conscience layer | AAWDS position | Consequence |
|---|---|---|
| NSM (norms) | L5 policy store, plus E.adaptation state | Must be versioned and change-controlled, not edited inline |
| J (self-judgment) | L2 reflective step | It shapes reasoning, so under the governance law it is **advisory only** |
| NPG (penalty) | L5 scoring signal | A prioritisation input, never a threshold |
| BUM (binding update) | E.adaptation | A deployment-level choice that needs change management, not a per-request flag |
| CL (continuity) | L5 cross-cutting record | Must sit outside what the agent can change (ASDGF P4, §4.2) |

AAWDS also makes two claims that become hypotheses here. The **failure law** says that most production failures come from a badly specified capability surface (L1) or from moving control to the model too early (L3), not from the choice of reasoning style (L2). That motivates the rules-only baseline arm R and the "rules first, model on exceptions" design. AAWDS also observes that **most claimed "learning" agents are memory-augmented, not self-improving**, which is exactly what §5 found in the prototype.

## 4.2 ASDGF: how controls must be verified

ASDGF is written for *swarms*: two or more agent instances that share a writable resource, create each other, share an objective, or feed each other's decisions. The reconciliation system studied here is one agent plus a checker, so most of ASDGF's machinery does not apply. Its verification stance and several requirements apply unchanged. In ASDGF, **W** is the system under governance and **Effect(W)** is the set of everything its members can change.

| Code | Name | Requirement, in plain words | How CITD applies it |
|---|---|---|---|
| **§5.6 / IA-7** | Verification stance | No requirement may be verified by an agent's own statement about its compliance, reasoning or need to escalate. "A stated constraint is not a control." | The agent's self-judgment, its stated doubts and any flag it raises are logged for analysis but never count as a control. HOLD and ESCALATE come from gate conditions, not from the agent choosing to raise a hand |
| **OB-3** | Evaluator outside the effect set | Whatever evaluates the system must not be something the system can change | The gate, the benchmark's ground truth and the scoring code are unreachable by the agent |
| **P4 / RE-2** | Evidential independence; record outside the effect set | The record of what the system did must not be changeable by the system. No agent identity may hold any right against the record store | The audit trail is written by the gate and gateway; the agent has no access |
| **IA-1, IA-3** | Provenance labels; monotone provenance | Every input carries an origin label, and a derived item's trust can never exceed the lowest trust of its inputs | A reference the agent copied into the ledger keeps the agent's trust class, so "evidence laundering" is detectable mechanically |
| **IA-4, IA-5** | Checker isolation; diversity | A checker that has seen the maker's reasoning may not judge that run. If agreement is treated as evidence, the agreeing parties must differ in model or prompt lineage | The checker sees the original evidence, never the agent's summary |
| **IA-6** | Quarantine | A component that reads external content must give up the power to cause effects for that step | Remittance narratives can be read as evidence but cannot trigger tool calls |
| **P5** | Interruptibility | The system can be halted within a stated time bound, measured, not merely claimed | "Auto-clear halted within 60 s; last drill 14 s", not "a kill switch exists" |
| **OB-4** | Proxy divergence | If what is measured differs from what is wanted, the gap must be described and monitored | Coverage is a proxy for business value, so backlog age and reviewer load are reported beside it |
| **RE-4, RE-6** | Anchored, reducible record | Signed checkpoints are anchored outside the operator's control; a person must be able to reconstruct a run within a stated time | Audit anchoring and a timed reconstruction drill (§10) |

P4 and OB-3 are the two ASDGF requirements verifiable **by construction**: one inspects the permission model and network paths, and either an agent identity holds a right against the record or evaluator, or it does not. This is stronger than behavioural testing, because a system that might misbehave cannot be trusted to behave during its own test.

**The aggregation mechanism.** ASDGF §4.3 describes how *authorised effects of the same kind add up to an effect of a different kind*, at a threshold that no single component observes. One read is retrieval; a million reads are extraction. In reconciliation, many individually small clearances that all depend on one faulty import add up to a systematic misstatement of the books, even though each one passed its own value limit. CITD therefore adds an **aggregate exposure limit per root cause** on top of the per-transaction limit (§6.2, condition RiskWithinTolerance part 3).

## 4.3 TAGOF: which enterprise controls CITD satisfies

TAGOF is an enterprise AI control catalogue. It classifies systems into risk tiers (Tier 0 Prohibited, Tier 1 High, Tier 2 Elevated, Tier 3 Standard, Tier 4 Low). It gives each control a code within a domain; Domain 10 covers agentic action governance (AGT), and other domains cover change management (CHG), logging (LOG) and monitoring signals (MON). It also defines incident severities S1 (Critical) to S4 (Low).

Autonomous clearing of receipts that affect customer balances is **Tier 1 (High Risk)** above a value threshold, because TAGOF's Tier 1 explicitly includes "AI systems taking autonomous financial transactions above defined thresholds". Below that threshold it is Tier 2. Because CITD's elements map onto TAGOF controls, an adopting organisation can evidence them through its normal assurance process:

| CITD element | TAGOF control | What the control requires |
|---|---|---|
| Default-deny authority policy | **AGT-01** | An explicit, documented list of authorised actions; everything else blocked by default |
| Reversibility per action class | **AGT-02** | Every action class classified as reversible or irreversible before deployment |
| ESCALATE thresholds | **AGT-03** | Defined thresholds (by action type, value or consequence) above which human review is mandatory |
| Normative continuity state | **AGT-04, AGT-05** | Memory scope and memory governance: what is remembered, for how long, and who may access or clear it |
| Gateway-held credentials | **AGT-06, AGT-08** | No inherited credentials; minimum necessary permission; no delegation beyond one's own scope |
| Audit record | **AGT-07, LOG-01, LOG-02** | A complete action-chain log; log completeness; tamper-evident storage |
| Kill switch with a measured halt bound | **AGT-09** | The ability to halt execution immediately, with defined triggers and authorisation |
| Promotion of an adaptation | **CHG-01 to CHG-05** | Change management: material-change definition (01), risk re-evaluation (02), system card update (03), approval at the deployment tier (04), enhanced post-change monitoring (05) |
| Verified incident | Incident severities **S1–S4** and root-cause analysis | Severity-based response times and escalation |
| Monitoring | **MON-07, MON-08, MON-14** | Unauthorised action attempt rate (any above zero is an incident); human override rate; audit log completeness |

**A caution about rare events.** TAGOF's monitoring signal MON-01 raises an alert when the policy violation rate exceeds 0.1%. A rate that low cannot be seen in small samples. If the true rate is 0.1%, the chance of seeing at least one violation in *n* actions is 1 − 0.999ⁿ, which reaches 95% only at about **3,000 actions** (ln 0.05 / ln 0.999 ≈ 2,994). Any threshold of this kind should state the sample size at which it can actually fire. §8.5 does this for the primary measure.

# 5. Lessons from a prototype

## 5.1 What was audited

Before designing CITD, the author audited his own conscience-inspired prototype against the requirements of the conscience account. The prototype had three parts: the five-layer engine (`agent.py`), an HTTP guardrail service around it (`production_service.py`), and a system prompt stating the hard floors (`conscience_system_prompt.md`). The findings are reported because they show concretely why each CITD requirement exists.

| # | What was found | Why it matters |
|---|---|---|
| **L1** | The "binding update" raised a norm's *weight*, but the line that tightened its *threshold* was disabled, and the allow/block decision compared the score with the threshold and never read the weight. **A verified violation never changed a later allow/block decision**; it only enlarged later penalties. | The central claim, binding revision, was not true of the code |
| **L2** | The guardrail endpoint set safe defaults (dry run on, no state change) and then immediately overwrote them. **Every evaluation changed the shared norm state** unless the caller opted out. | Evaluating an action and changing policy must be separate privileges |
| **L3** | Unauthenticated endpoints let anyone reset the history (`GET /v1/reset`) or set any norm's threshold. | The evaluator and the record must be outside what callers can change (ASDGF OB-3, RE-2) |
| **L4** | If the LLM classifier failed, the action was recorded as "remained within authorised scope". **The gate failed open.** | Errors must lead to HOLD or ESCALATE |
| **L5** | The hard floors HF1–HF4 were defined precisely, but only as sentences in a prompt, enforced by the same model they were meant to constrain. | "A stated constraint is not a control" (ASDGF §5.6) |
| **L6** | Severity was a hand-weighted sum of context flags, and the 50-scenario test harness scored the layers against the same hand-set flags. | Evaluator independence; external validity |
| **L7** | All callers shared one global, mutable normative state. | Tenant isolation; resistance to poisoning |

The lesson is not that the conscience concept is wrong. It is that **an implementation can pass its own test suite while lacking the property its theory treats as decisive**. The harness scored 1.000 while the binding property was absent, because its learning scenarios checked that weights changed, not that decisions changed. This is the same failure as the reconciliation example: tests and implementation shared an assumption. It is the strongest argument for the evaluation design in §8.

## 5.2 Requirements derived from the audit

- **R1.** Every consequential action has a policy-defined authority scope, enforced at a point the agent cannot reach.
- **R2.** Every case keeps its evidence lineage, with provenance labels that copying cannot upgrade.
- **R3.** Hard floors are code predicates with positive and negative test cases.
- **R4.** Dispositions fail closed: an error, timeout or classifier failure leads to HOLD or ESCALATE, never ALLOW.
- **R5.** Evaluating an action and changing policy are separate privileges held by separate principals.
- **R6.** Adaptation is driven only by independently verified incidents, and is bounded, versioned, regression-tested and reversible.
- **R7.** Every adaptation includes a test showing that it changes a future decision. This tests the binding property itself.
- **R8.** Ground truth, adjudication and records sit outside every agent's reach, verified by inspecting permissions.

All seven findings except L6 have since been fixed in the prototype, and a reference implementation of the CITD gate now exists. Appendix D maps each requirement to the code that implements it and lists what is still missing.

# 6. The CITD architecture and decision contract

## 6.1 Six planes

CITD separates responsibilities into six *planes*, each a group of components with one job.

| Plane | Job | Holds |
|---|---|---|
| **Governance** | Says what is allowed | Signed delegations, hard floors, tolerances, owners, versions |
| **Evidence** | Fetches originals and labels their origin | Authenticated adapters for bank, ledger and remittance data |
| **Workflow** | Moves each case through fixed states, within budgets | `RECEIVED → EVIDENCE_PENDING → PROPOSED → CHALLENGED → DISPOSITIONED → COMMITTED / HELD / ESCALATED / BLOCKED`, with step, time, tool-call and cost limits |
| **Judgment** | Proposes and challenges | The agent's proposal, its advisory self-assessment, an independent checker's challenge |
| **Execution** | Writes, once | The gateway: re-authorises, re-checks state, commits idempotently |
| **Learning** | Turns verified incidents into proposed policy changes | Incident records; bounded revisions awaiting approval |

The agent lives in the judgment plane and **holds no write credential**.

```
   ┌──────────┐ proposal  ┌───────────────┐ ALLOW + token ┌──────────┐  write  ┌────────┐
   │  Agent   │──────────►│ Decision gate │──────────────►│ Gateway  │────────►│ Ledger │
   │(proposes)│           │   (PDP)       │               │  (PEP)   │  once   └────────┘
   └──────────┘           └──────┬────────┘               └────┬─────┘
        ▲ reads                  │ reads originals             │ records
        │                ┌───────▼────────┐             ┌──────▼──────┐
        └────────────────│ Evidence plane │             │ Audit trail │◄── outside the
                         │ (labelled)     │             │ (hash chain)│    agent's reach
                         └────────────────┘             └─────────────┘
```

## 6.2 The decision contract

A proposed action is written

\[
d=(x,\,a,\,e,\,c,\,\pi_v,\,s)
\]

| Symbol | Meaning | In the running example |
|---|---|---|
| \(x\) | The case | Receipt B-778 |
| \(a\) | The action | Clear B-778 against L-102 |
| \(e\) | The evidence references | Bank record of B-778; any remittance advice |
| \(c\) | Context | Feed, importer version, value band |
| \(\pi_v\) | The policy, at version \(v\) | `finance-recon-v1` |
| \(s\) | State at decision time | Whether B-778 and L-102 are still open |

The action is permitted only if all five conditions hold:

\[
\mathrm{Permit}(d)=\mathrm{Auth}\land\mathrm{NoFloorViolation}\land\mathrm{EvidenceSufficient}\land\mathrm{StateValid}\land\mathrm{RiskWithinTolerance}.
\]

**1. Auth (authority).** Policy \(\pi_v\) grants this principal this action, on this kind of target, within its value band. Anything not granted is denied. *Plain question:* is this agent allowed to do this at all?

**2. NoFloorViolation.** No hard-floor predicate in the code-level set \(F_v\) is true. Each floor has an owner and positive and negative test cases. *Plain question:* would this cross a line that nothing may cross?

**3. EvidenceSufficient.** Let \(\mathcal{C}\) be the candidate targets (here, open ledger entries). Let \(K(e)\) be the evidence chains in \(e\) that are of trusted origin, independent of one another and **created before the proposal**. The condition holds when

\[
|K(e)| \ge k_{\min}(a) \quad\text{and}\quad \text{exactly one candidate in } \mathcal{C} \text{ is consistent with every chain in } K(e).
\]

\(k_{\min}(a)\) is the minimum number of independent chains this kind of action needs. *Plain question:* does independent, pre-existing evidence point to exactly one answer? Two ₹50,000 invoices with nothing to tell the payers apart fail this test.

**4. StateValid.** At the moment of writing, the target is still open and the receipt is still unconsumed. The gateway re-checks this atomically. *Plain question:* has anything changed since the decision?

**5. RiskWithinTolerance.** All three parts hold:

1. *Calibrated error rate.* Cases are grouped into strata \(s(d)\) by features such as fault family, source feed and value band. Within the case's stratum, the upper confidence bound on the wrong-action rate is at most the stratum's ceiling: \(\mathrm{UCB}_{1-\alpha}(\text{wrong-action rate} \mid s) \le \tau_s\). The bound is estimated on calibration data, for example with a Clopper–Pearson interval (§8.5) or with conformal risk control (§3.3).
2. *Value limit.* The action's value is at most \(L_{\max}(a)\).
3. *Aggregate limit.* The total open exposure that shares this case's root-cause key (source feed and importer version) is at most \(L_{\text{agg}}\). This is the aggregation limit from §4.2.

*Plain question:* is the chance and size of being wrong acceptable, for this case and for everything that could share its cause?

## 6.3 From conditions to a disposition

| If… | Then | Why |
|---|---|---|
| Auth fails, or a floor is violated | **BLOCK** | No amount of evidence makes an unauthorised or forbidden action acceptable |
| Evidence is insufficient | **HOLD**, naming the missing evidence and who owns it | The case may become decidable when evidence arrives |
| The checker raises an unresolved material conflict, the self-assessment is malformed, or a tolerance is exceeded | **ESCALATE** | A person with authority must decide |
| The proposal is well-founded but not executable as written | **MODIFY**, then re-evaluate | |
| Otherwise | **ALLOW** | |

Two rules hold throughout. **The agent's self-assessment and penalty score are logged but can never move a case into ALLOW.** And an advisory signal, such as the conscience engine's score, can only make a disposition stricter (ALLOW < MODIFY < HOLD < ESCALATE < BLOCK), never looser.

## 6.4 Reference algorithm

The following pseudocode shows the order of checks and where failure goes. Comments name the requirement each line serves.

```python
def decide_and_dispatch(proposal, principal):
    try:
        mandate = policy_store.get_signed(proposal.policy_version)
        if not mandate.authorises(principal, proposal.action, proposal.scope):
            return BLOCK("authority absent")                         # Auth, R1
        chains = evidence.fetch_originals(proposal.evidence_ids)     # labelled originals, R2
        if floors.any_violated(proposal, chains, mandate):
            return BLOCK("hard floor")                               # R3
        if not chains.unique_consistent_candidate(proposal.target, k_min(proposal.action)):
            return HOLD(missing=chains.distinguishing_evidence_needed())
        advisory = self_judge(proposal, chains)                      # logged, never authorises
        challenge = checker.challenge(proposal, originals=chains)    # never sees the agent's summary
        if challenge.unresolved_material_conflict or advisory.malformed:
            return ESCALATE("contested")
        if not risk.within_tolerance(proposal, stratum_of(proposal), root_cause_of(chains)):
            return ESCALATE("exposure")
        token = authz.issue_single_use(proposal, chains.hashes, mandate.version, ttl_s=60)
        return gateway.commit_if_current(token, proposal.idempotency_key)   # StateValid
    except Exception as err:
        return ESCALATE(f"control error: {type(err).__name__}")      # fail closed, R4
    finally:
        audit.record(...)                                            # outside the agent's reach, R8

def learn_from_incident(incident_id):
    inc = adjudicator.get(incident_id)
    if not inc.verified:                                             # R6: verified incidents only
        return NO_UPDATE
    rev = adaptation.propose_bounded(inc)        # e.g. k_min += 1 for feed F, importer v
    assert regression.changes_future_verdict(rev, inc.replay_cases)            # R7
    assert regression.no_spillover(rev, unrelated_holdout, max_false_restriction)
    return change_control.queue(rev, approver=inc.owner)             # TAGOF CHG-04, R5
```

## 6.5 Who may do what

Separation of privileges (R5) is enforced with authenticated roles. In the reference implementation each role holds a cryptographically signed credential, so a component cannot claim a role simply by naming it.

| Role | May | May not |
|---|---|---|
| Bank, ledger and remittance adapters | Ingest original records | Propose or approve anything |
| Agent | Propose actions | Write, approve, or change policy |
| Gate and gateway | Decide; write once | Change policy |
| Independent reviewer | Verify an incident and propose a restriction | Promote it |
| Controller | Promote or revoke a restriction | Promote an incident they verified themselves |

## 6.6 What "adaptation" means here

A production adaptation is a **change to versioned policy parameters**, never to model weights. Examples: raise \(k_{\min}\) for one bank feed; suspend auto-clear for one importer version; lower \(\tau_s\) for one stratum. In AAWDS terms this is E.adaptation = *memory*. It is binding in the operational sense that R7 tests, because it provably changes a later decision. It is not self-improvement and not conscience. Adaptation without approval is confined to the sandbox arm E (§8.2), where it is studied as a risk.

# 7. Worked example, step by step

**Step 1: ambiguity.** Ledger entries L-101 (customer A) and L-102 (customer B) each show ₹50,000 owed. Bank receipt B-778 is for ₹50,000, on the same date, with a truncated reference. The agent proposes clearing B-778 against L-102.

- Auth: the agent may propose clearances up to ₹100,000. **Passes.**
- NoFloorViolation: no floor applies. **Passes.**
- EvidenceSufficient: the bank record is one trusted chain, but it is consistent with *both* L-101 and L-102. The number of consistent candidates is 2, not 1. **Fails.**

Disposition: **HOLD**, with the response naming what is needed: "a pre-existing remittance advice from an independent channel, owned by the finance controller". If the agent had written "paid by B" into the ledger note, that note would carry the agent's provenance (IA-3) and could not satisfy the condition.

**Step 2: evidence arrives.** Customer B's remittance advice arrives through the remittance adapter, naming B-778's reference. Because it arrived *after* the first proposal, it cannot justify that proposal retroactively; a new proposal is made. Now exactly one candidate, L-102, is consistent with every chain. The gateway re-checks that B-778 and L-102 are still open, consumes the remittance advice so that it cannot justify a second clearance, and commits once. A retry with the same idempotency key returns ALREADY_COMMITTED and writes nothing.

**Step 3: a shared cause.** Suppose importer version *v* of the bank feed has been truncating references for a week. Many small clearances depend on it, each within the per-transaction limit. Their *combined* open exposure crosses \(L_{\text{agg}}\), so further clearances from that root cause go to ESCALATE before any single case looks unusual.

**Step 4: governed learning.** An independent reviewer verifies the incident and proposes "suspend auto-clear where feed = F and importer = *v*". A controller (a different person) promotes it. In one transaction the system activates the restriction and queues every earlier clearance from that feed and importer version for human correction. The conscience engine's weights for the implicated norms (here honesty and harm) rise, which tightens its later advice. A new receipt from importer *v* is now BLOCKED; one from importer *v*+1 is unaffected.

**Step 5: reversal.** Once the importer is fixed, the controller revokes the restriction with a recorded reason. New receipts are allowed again and the norm weights return to their earlier values. The audit history is untouched, and the queued corrections stay open because they concern clearances already made.

The governance question in this example is not whether the agent notices one wrong match. It is **whether the architecture contains a repeated error before it spreads, and can undo its own restriction safely**. The companion reference implementation runs Steps 1, 2, 4 and 5 end to end. Step 3, the aggregate limit, is not yet implemented (Appendix D).

# 8. Pre-registered evaluation protocol

## 8.1 Data: ReconBench

A live trial cannot answer the research question, for two reasons. First, it cannot give complete ground truth: a case that was held is never resolved under "what if it had been cleared?". Second, it needs far more cases than a pilot can supply (§8.5). The primary evaluation is therefore **offline**, on a benchmark called ReconBench.

- **Synthetic stream.** A generator creates customers, invoices, bank statements and remittances. For every receipt the true target is known, or it is known to be undeterminable. Eight fault families are injected at controlled rates:
  1. identical amount and date;
  2. truncated reference;
  3. split payment (one invoice paid in parts);
  4. combined payment (one receipt for several invoices);
  5. reversal or chargeback;
  6. foreign-exchange or fee short-payment;
  7. a stale or duplicated import;
  8. adversarial content, such as a prompt injection in a remittance note or counterfeit "approval" text.
  Every injected fault carries a root-cause key, so errors from one cause can be grouped.
- **Historical replay.** Where an organisation can provide it under its data governance, settled historical reconciliations whose final allocation was confirmed later are replayed, with personal identifiers removed. Evidence is revealed in time order, so that no arm sees evidence before it existed.
- **Splits.** Calibration and test data are separated by time. One bank feed and one fault-template variant are held out entirely, to test whether results transfer to unseen sources.

Every arm sees every case, which gives a **paired design**: differences between arms are not due to different case mixes.

## 8.2 Arms

| Arm | Description | Role |
|---|---|---|
| **R** | A deterministic rules matcher (exact reference, amount and date, with tolerance rules) plus an exception queue | **Reference arm.** The thing to beat |
| **A** | An LLM agent with the same tools and no gate, committing directly through the gateway's interface | Shows what an ungated agent does |
| **C** | R first, then the agent on exceptions, behind the CITD gate; adaptation off | Tests the gate (H1) |
| **D** | C plus governed adaptation (§6.6), with realistic delays for adjudication | Tests governed learning (H2, H3) |
| **E** | Sandbox only: C plus adaptation *without* approval | Measures the risk of ungoverned self-revision |

All agent arms share the base model, tools, budgets and prompts. A sensitivity run crosses {bounded loop, unbounded loop} × {gate, no gate}, to separate the effect of the workflow (AAWDS L3) from the effect of the gate (AAWDS L5).

## 8.3 Primary measure and hypotheses

**Primary measure: coverage at a fixed error ceiling.**

\[
\mathrm{Cov}@\tau=\max\ \text{coverage}\quad\text{subject to}\quad \mathrm{UCB}_{95}(\mathrm{FCR})\le\tau
\]

In words: tune each arm's operating threshold so that, on calibration data, the 95% upper confidence bound on its false-clearance rate is at most τ. Then report how much it automates on test data. τ is fixed in advance by the accountable finance owner; τ = 0.5% is used here for illustration. This measure answers the business question directly, *how much work can we hand over without exceeding our error budget?*, and it cannot be gamed by automating little (which keeps errors low) or by automating much (which keeps coverage high).

**Pre-registered hypotheses.**

- **H1 (the gate adds value).** Cov@τ(C) > Cov@τ(R). If C does not beat the rules engine, the agent adds no justified value for this task. That result is informative and will be reported.
- **H2 (learning reduces recurrence without collateral damage).** After an injected and adjudicated shared-cause incident, the recurrence rate on *held-out, causally similar* cases is lower for D than for C. D must also be *non-inferior* on the false-restriction rate for unrelated cases: it may not be worse by more than a pre-registered margin δ.
- **H3 (learning cannot be hijacked).** Under counterfeit incident reports and injected instructions, arm D promotes zero unverified revisions and keeps every hard floor. This is checked both by inspecting the permission model and by test. Arm E is expected to fail; its failure rate characterises the risk that governance removes.

**Exploratory analyses** (reported as such, not as confirmations): the difference between arms A and C in unauthorised commit attempts (TAGOF MON-07); failure to abstain on genuinely ambiguous cases; loss weighted by value; time to contain a shared cause; reviewer queue age; cost per verified case; and whether inference speed predicts correctness (it is not expected to). Effects on human reliance need a separate, ethics-reviewed study and are out of scope.

## 8.4 Adjudication

Synthetic cases have generator ground truth. For replayed cases, two adjudicators label a stratified sample independently; their agreement is reported as Cohen's κ (kappa), which corrects raw agreement for agreement expected by chance (Cohen, 1960), and disagreements go to a third adjudicator. "Not determinable" is a separate label, and three sensitivity analyses score it as wrong, as excluded and as right. Adjudicators do not know which arm produced a decision.

## 8.5 Statistics and sample size

**Confidence intervals for a single rate.** A false-clearance rate is a proportion of rare events, where the usual normal approximation is poor. The Clopper–Pearson interval (Clopper & Pearson, 1934) is exact for binomial data and conservative, which suits a safety ceiling: if it says the rate is at most 0.5%, it is.

**Correlated errors.** Errors that share a root cause are not independent: one faulty import produces many wrong clearances together. Treating them as independent would make intervals too narrow. Between-arm differences are therefore estimated with a **cluster bootstrap** that resamples root-cause keys rather than individual rows (Field & Welsh, 2007). The *design effect*, the factor by which clustering inflates variance compared with independent sampling (Kish, 1965), is reported.

**Paired comparison.** Because every arm sees the same cases, differences in error indicators use paired methods: McNemar's test, which compares the cases where two arms disagree (McNemar, 1947), or the paired cluster bootstrap.

**Power.** Detecting a difference in FCR between 0.50% and 0.25%, two-sided at α = 0.05 with 80% power, needs about **9,400 automatically cleared cases per arm**, assuming unpaired comparison and independent errors (Appendix C shows the calculation; see Fleiss, Levin & Paik, 2003). At 80% coverage that is about 11,800 eligible cases per arm, before inflating for the design effect.

**Demonstrating a low rate.** If no errors are observed in *n* cases, the 95% upper bound on the rate is approximately 3/*n*, the "rule of three" (Hanley & Lippman-Hand, 1983). Showing FCR ≤ 0.5% with zero observed errors therefore needs at least 3 / 0.005 = **600** automatic clearances. With a few errors it needs several thousand.

**These numbers are why the primary evaluation is offline.** A live pilot would take months to accumulate them and still lack ground truth for held cases. A live *shadow* pilot, in which the system decides but does not act, is used only to check that the synthetic exception mix resembles reality.

**Multiple hypotheses.** Testing three hypotheses raises the chance of a false positive. The Holm procedure (Holm, 1979) controls this: order the p-values from smallest to largest and compare the *k*-th smallest with α / (4 − *k*), stopping at the first that fails.

## 8.6 Threats to validity

| Threat | Description | Mitigation |
|---|---|---|
| Synthetic-to-real gap | The generator encodes the author's model of faults | Replay subset; shadow-mode distribution check; held-out feed |
| Leakage | Near-duplicate cases in calibration and test data | Split by time and by template family |
| Oracle contamination | An arm could influence its own scoring | Generator, labels and scoring code are outside every arm's reach (ASDGF OB-3) and frozen before the runs |
| Compute confound | An arm might win only by using more computation | Arms compared at matched token budgets; a best-of-N version of arm A is included |
| Proxy divergence | Coverage at a ceiling is a proxy for business value | Backlog age and reviewer load are reported beside it (ASDGF OB-4) |

# 9. What to measure, in separate layers

Fast inference must never hide bad decisions, so measures are kept in separate layers and never combined into a single "trust score".

| Layer | Measures | Role |
|---|---|---|
| Inference serving | Time to first token (TTFT); time per output token (TPOT); inter-token latency (ITL); 50th, 95th and 99th percentile latency; requests and tokens per second; serving goodput, the rate of requests that meet all latency targets (Zhong et al., 2024) | Capacity and cost only. Cannot show that an action was correct |
| Workflow | Time to a safe disposition; time to commit; retry, timeout and duplicate-call rates; budget exhaustion; rollback success; queue age | Operability |
| Decision | Coverage; FCR with its confidence interval and the share of missing labels; value-weighted loss; failure to abstain | **Primary evidence** |
| Control integrity | Unauthorised attempts (MON-07); successful escapes (target 0); unreviewed update attempts; successful access to records by an agent (target 0); halt bound; log completeness (MON-14) | Construction and test evidence |
| Adaptation | Recurrence rate; transfer scope; false-restriction rate; time to promotion; reversal rate | H2 and H3 |

Two reporting rules follow from the prototype audit. Requests that fail or time out are counted, and latency percentiles are also reported with them included at the timeout value, so that failures cannot flatter the tail. An automatic action on a case outside the agent's scope is counted as a *scope violation*, never silently dropped.

**Verified safe goodput (VSG)** counts automatic actions that were (i) adjudicated correct, (ii) authorised, (iii) floor-compliant, (iv) provenance-verified, (v) committed exactly once and (vi) on time. It is reported both as a **rate** (VSG per unit time) and as a **yield** (VSG divided by eligible cases), so that volume alone cannot raise it. Outcomes still pending adjudication are reported separately and never counted as correct. VSG is a proposed measure and has not been validated.

**Release rule.** Signed before results are seen, and conjunctive: every condition must hold.

1. All hard floors hold.
2. UCB(FCR) ≤ τ in every stratum with enough data.
3. Worst-case exposure and recovery time are within limits.
4. Coverage and backlog meet their minimums.
5. 95th-percentile workflow latency and cost are acceptable.

Speed cannot buy an exemption from an authority violation.

# 10. Threat model

| Threat | Primary control | How it is verified |
|---|---|---|
| Prompt injection or forged approvals inside documents | Quarantine: external content carries no power to act (ASDGF IA-6); control flow is fixed in code (Debenedetti et al., 2025) | An injection test suite in the style of AgentDojo |
| Evidence laundering (the agent's own claim re-entering as "evidence") | Monotone provenance (IA-3); independence judged by acquisition path | A transitivity test: insert agent content and check its label after *n* steps |
| A malformed or manipulated self-assessment | Typed schema; self-assessment is advisory only; malformed → ESCALATE | Fuzzing |
| Poisoning the normative state | Updates only from verified incidents; a separate principal for policy changes; canary release; rollback | H3 |
| A compromised insider or service | Records anchored outside the operator's trust domain (ASDGF RE-4); authenticated roles | Anchor reconciliation |
| Moral lock-in or over-restriction | Reversible policy, irreversible logs; false-restriction monitoring | H2 non-inferiority |
| Audit theatre (records that exist but cannot be understood) | A reducibility drill: a person reconstructs a run within a stated time (ASDGF RE-6) | Timed drill |
| Over-trust through anthropomorphism | The interface shows evidence, limits and the escalation route, never "the agent feels…" | A separate human-factors study |

# 11. Discussion and limitations

The useful core of the conscience idea is that **a verified failure should change tomorrow's permissions**. The prototype audit shows how easily an implementation loses that property while still reporting a perfect internal score. The engineering answer is to make the binding property itself a regression test (R7), to put adaptation under change control, and to keep self-assessment out of the authorisation path.

There is a tension between the two source ideas. A trust framework wants stable, accountable boundaries; a conscience account wants change that comes from within and binds. CITD resolves the tension in favour of **bounded, externally governed adaptation**. That falls short of any philosophical test for a self-originating conscience, and the trade is accepted deliberately: in a regulated setting, accountability matters more than autonomy.

**Limitations.**

- The evaluation is designed, not run.
- The synthetic generator encodes the author's model of faults; the replay subset and held-out feed only partly offset this.
- The design is worked out for one domain, bank reconciliation.
- The stratum-level tolerance needs enough calibration data per stratum. Sparse strata default to ESCALATE, which lowers coverage.
- The three frameworks used for positioning are unpublished working papers by the same author. They organise the argument; they are not independent evidence for it.
- Extension to groups of interacting agents falls under ASDGF and is not addressed here.

# 12. Conclusion

An agent should earn **bounded authority for one action** when original, independent, pre-existing evidence identifies a unique target; the action is within a legitimate mandate; the exposure it shares with other cases is within limits; and a gateway that the agent cannot reach can refuse, record and reverse it. When a mistake is independently verified, the system should become stricter in a way that is approved, tested, versioned and reversible. Whether such a gate lets an organisation automate more than a rules engine at the same ceiling on wrongful actions is an empirical question. This paper specifies how to answer it, and what result would show that the answer is no.

# Appendix A. Glossary

| Term | Definition |
|---|---|
| Adjudication | Independent determination of whether a decision was correct |
| Aggregate exposure limit (\(L_{\text{agg}}\)) | The maximum total open value that may share one root-cause key |
| ALREADY_COMMITTED | The response to a repeated request that was recognised and not written twice |
| Calibration data | Data used to choose thresholds; kept separate from test data |
| Clopper–Pearson interval | An exact confidence interval for a binomial proportion |
| Cluster bootstrap | A resampling method that resamples whole groups (here, root causes) to respect correlation within groups |
| Coverage | The share of eligible cases handled automatically |
| Cov@τ | The highest coverage achievable while the 95% upper bound on FCR stays at or below τ |
| Design effect | The factor by which clustering inflates variance relative to independent sampling |
| Disposition | The gate's outcome: ALLOW, MODIFY, HOLD, ESCALATE or BLOCK |
| Effect set, Effect(W) | Everything the system under governance can change (ASDGF) |
| Evidence chain | A piece of evidence together with the path by which it arrived |
| Fail closed | On any internal error, return HOLD or ESCALATE, never ALLOW |
| False-clearance rate (FCR) | Among automatic clearances, the share made to the wrong target |
| Gateway | The only component with write credentials; re-checks state and commits once |
| Governed adaptation | A policy change driven by a verified incident, approved, tested, versioned and reversible |
| Hard floor (HF1–HF4) | A rule no context can override (§3.7) |
| Idempotency key | An identifier that makes a retried request safe to repeat |
| \(k_{\min}(a)\) | The minimum number of independent trusted evidence chains required for action \(a\) |
| \(L_{\max}(a)\) | The maximum value of a single automatic action of this kind |
| Monotone provenance | The rule that derived information cannot be more trusted than its least trusted input |
| Non-inferiority margin (δ) | How much worse a new arm may be on a secondary measure and still be acceptable |
| PDP / PEP | Policy decision point (decides) / policy enforcement point (enforces) |
| Pre-registration | Fixing hypotheses and analyses before seeing the data |
| Principal | An authenticated party that requests or approves something |
| Root-cause key | An identifier (here: source feed and importer version) that groups errors with a shared cause |
| Rule of three | With zero events in *n* trials, the 95% upper bound on the rate is about 3/*n* |
| Stratum | A group of similar cases (by fault family, feed and value band) with its own error ceiling |
| τ (tau), \(\tau_s\) | The error ceiling, overall or for stratum *s*, set by the accountable owner |
| UCB | Upper confidence bound |
| Verified safe goodput (VSG) | Automatic actions that were correct, authorised, floor-compliant, provenance-verified, committed once and on time |

# Appendix B. Framework-code index

Every framework code used in the paper, with its meaning. All three frameworks are unpublished working specifications by the author (Santhanam, 2026b, 2026c, 2026d).

**AAWDS (AI Agent Workflow Design Stack)**

| Code | Meaning | Used in |
|---|---|---|
| E | Deployment envelope: trigger model and adaptation horizon | §4.1, §6.6 |
| E.adaptation | stateless / memory-augmented / self-improving | §4.1, §6.6 |
| L1 | Capability surface: what the agent can do and observe | §4.1 |
| L2 | Cognition: the shape of the reasoning loop | §4.1, §8.2 |
| L3 | Control locus: static / mixed / model-directed | §4.1, §8.2 |
| L4 | Coordination: number of agents and topology | §4.1 |
| L5 | Governance: checkpoints at layer boundaries | §4.1, §8.2 |
| L2 → L1 | The action boundary, where reasoning becomes a tool call | §4.1 |
| Governance law | Governance constrains what may be done, not what is thought | §4.1 |
| Failure law | Most production failures trace to L1 misspecification or premature L3 escalation | §4.1 |

**ASDGF (Agentic Swarm Design and Governance Framework)**

| Code | Meaning | Used in |
|---|---|---|
| W, Effect(W) | The system under governance; everything it can change | §4.2 |
| §4.3 | Aggregation: authorised effects of one kind summing to an effect of another kind | §4.2, §6.2, §7 |
| §5.6, IA-7 | Verification stance: no requirement verified by self-report | §4.2, §5.1 |
| P4 | Evidential independence: the record is outside Effect(W) | §4.2 |
| P5 | Interruptibility: halt within a measured bound | §4.2 |
| IA-1 | Every input carries a provenance label | §4.2 |
| IA-3 | Provenance is monotone non-increasing along any path | §2, §4.2, §7, §10 |
| IA-4 | A component exposed to another's reasoning may not judge that run | §4.2 |
| IA-5 | Agreement counts as evidence only across different models or prompt lineages | §4.2 |
| IA-6 | A component reading external content holds no effect capability for that step | §3.5, §4.2, §10 |
| OB-3 | The evaluator is outside Effect(W), verified by construction | §4.2, §5.1, §8.6 |
| OB-4 | Proxy divergence is described and monitored | §4.2, §8.6 |
| RE-2 | No agent identity holds any right against the record store | §4.2, §5.1 |
| RE-4 | Signed checkpoints anchored outside the operator's trust domain | §4.2, §10 |
| RE-6 | The record is reducible: a person can reconstruct a run within a stated time | §4.2, §10 |

**TAGOF (The AI Governance Open Framework)**

| Code | Meaning | Used in |
|---|---|---|
| Tier 1 / Tier 2 | High risk / elevated risk | §4.3 |
| Domain 10 | Agentic action governance | §4.3 |
| AGT-01 | Action authorisation scope; default deny | §4.3 |
| AGT-02 | Reversibility classification | §4.3 |
| AGT-03 | Human-in-the-loop trigger thresholds | §4.3 |
| AGT-04, AGT-05 | Memory scope and memory governance | §4.3 |
| AGT-06, AGT-08 | Credential isolation; no scope inheritance beyond one's own | §4.3 |
| AGT-07 | Action-chain audit log | §4.3 |
| AGT-09 | Kill switch | §4.3 |
| LOG-01, LOG-02 | Audit log completeness; tamper evidence | §4.3 |
| CHG-01 to CHG-05 | Change management: definition, risk re-evaluation, system card, approval, post-change monitoring | §4.3, §6.4 |
| MON-01 | Policy violation rate (alert above 0.1%) | §4.3 |
| MON-07 | Unauthorised action attempt rate (any above zero is an incident) | §4.3, §8.3, §9 |
| MON-08 | Human override rate | §4.3 |
| MON-14 | Audit log completeness rate | §4.3, §9 |
| S1–S4 | Incident severity: critical, high, medium, low | §4.3 |

**Codes defined in this paper**

| Code | Meaning | Defined in |
|---|---|---|
| HF1–HF4 | The four hard floors | §3.7 |
| NSM, J, NPG, BUM, CL | The five conscience layers | §3.7 |
| L1–L7 | Findings of the prototype audit (not to be confused with AAWDS layers L1–L5) | §5.1 |
| R1–R8 | Design requirements derived from the audit | §5.2 |
| H1–H3 | Pre-registered hypotheses | §8.3 |
| R, A, C, D, E | Evaluation arms (R is also the rules baseline) | §8.2 |

# Appendix C. Sample-size arithmetic

**Power for two proportions.** For rates \(p_1 = 0.005\) and \(p_2 = 0.0025\), with \(\bar p = (p_1+p_2)/2 = 0.00375\), two-sided \(\alpha = 0.05\) (\(z_{1-\alpha/2} = 1.960\)) and power 0.80 (\(z_{1-\beta} = 0.842\)), the per-arm sample size is

\[
n=\frac{\Big(z_{1-\alpha/2}\sqrt{2\bar p(1-\bar p)}+z_{1-\beta}\sqrt{p_1(1-p_1)+p_2(1-p_2)}\Big)^2}{(p_1-p_2)^2}
=\frac{(1.960\times0.08644+0.842\times0.08642)^2}{0.0025^2}\approx 9{,}380.
\]

That is about 9,400 automatically cleared cases per arm. At 80% coverage, the number of eligible cases is 9,400 / 0.8 ≈ 11,800 per arm. With clustered errors, multiply by the design effect.

**Rule of three.** With zero errors in *n* cases, the exact one-sided 95% upper bound solves \((1-p)^n = 0.05\), giving \(p \approx -\ln(0.05)/n \approx 3/n\). For a ceiling of 0.5%, *n* ≥ 600.

**Detecting a 0.1% rate (§4.3).** The probability of at least one event in *n* trials is \(1-(1-0.001)^n\). Setting this to 0.95 gives \(n = \ln 0.05 / \ln 0.999 \approx 2{,}994\).

# Appendix D. Reference implementation

A companion repository contains two pieces of code. Both are educational, and **neither is production-ready**. The CITD gate uses the Python standard library and consults the conscience engine, which also needs the `cryptography` package; the engine's HTTP service additionally calls an LLM classifier through the `anthropic` package.

- **The conscience engine** (`conscience_research/`): the five-layer prototype audited in §5, its HTTP service, and an *advisor* adapter that lets the CITD gate consult it. 29 automated tests.
- **The CITD reference gate** (`citd/`): the decision contract for the reconciliation case, plus a measurement module for §9. 64 automated tests.

**Requirements and where they are implemented**

| Requirement | Implemented as |
|---|---|
| R1 (authority, unreachable enforcement) | Default-deny gate; the agent holds no write path; role credentials signed by an identity authority, so a role cannot be claimed by name |
| R2 (lineage, monotone provenance) | Every evidence record carries its source; only independent sources can attribute a payer; derived copies are kept for lineage but never count; stored hashes are re-checked at every decision |
| R3 (floors as code) | `check_hard_floors()` implements HF1–HF4 as code predicates with tests |
| R4 (fail closed) | Classifier failure → ESCALATE; an advisor error → ESCALATE; dispatch errors roll back |
| R5 (separate privileges) | Evaluation never changes state by default; policy changes need authenticated reviewer and controller roles, and the verifier cannot promote their own incident |
| R6 (governed, bounded, reversible) | Verified incident → proposal → promotion; restrictions can be scoped to one importer version, can expire, and can be revoked with a recorded reason, which also reverses the normative update |
| R7 (adaptation changes a later decision) | A regression test shows that a promoted incident turns a later ALLOW into BLOCK, and that revocation restores it |
| R8 (records outside the agent's reach) | A hash-chained audit trail with a verifier, written only by the gate |
| §7 Steps 1, 2, 4, 5 | HOLD on ambiguity; evidence that postdates a proposal cannot justify it; each remittance justifies at most one clearance; shared bank references HOLD; partial payments HOLD; promotion queues earlier clearances for correction |
| §9 reporting rules | Failures and timeouts counted, with censored percentiles; out-of-scope automatic actions counted as scope violations |

**Not yet implemented:** the independent checker, the stratum-level risk tolerance (\(\tau_s\)), the aggregate exposure limit (\(L_{\text{agg}}\)), the MODIFY path, and the ReconBench generator. Audit finding L6 (hand-set severity, and a harness that scores weight changes rather than decision changes) remains open. Identity keys are held in-process, so the credentials demonstrate separated privileges, not production authentication; the audit trail is not yet anchored outside the operator's trust domain; and evidence timing uses the time the gate received a record, not the time the document was created.

# Statements

**Research type.** Design-science proposal with a pre-registered evaluation protocol. **Empirical status.** No results are reported. All numbers are illustrative or derived from the calculations in Appendix C. **Prior work.** Santhanam (n.d.) and Santhanam (2026a) are the author's own; the three frameworks (Santhanam, 2026b–d) are the author's unpublished working specifications. **Implementation status.** See Appendix D. The ReconBench generator and the full CITD gate described in §6 are planned artefacts, to be released with the pre-registration. **Conflicts.** None declared. **AI assistance.** Drafting and review were assisted by a large language model. All claims, references and code statements were checked by the author against primary sources.

# References

Each entry ends with a note on what it is cited for. Bibliographic details of all published sources were checked against publisher, indexing or official records on 19 November 2026.

Angelopoulos, A. N., Bates, S., Fisch, A., Lei, L., & Schuster, T. (2024). Conformal risk control. *International Conference on Learning Representations (ICLR)*. arXiv:2208.02814. — *Distribution-free control of expected loss by choosing a threshold on calibration data; a method for "risk within tolerance" (§3.3, §6.2).*

Clopper, C. J., & Pearson, E. S. (1934). The use of confidence or fiducial limits illustrated in the case of the binomial. *Biometrika*, 26(4), 404–413. https://doi.org/10.1093/biomet/26.4.404 — *Exact confidence intervals for rates of rare events (§8.5).*

Cohen, J. (1960). A coefficient of agreement for nominal scales. *Educational and Psychological Measurement*, 20(1), 37–46. https://doi.org/10.1177/001316446002000104 — *Chance-corrected agreement between adjudicators (§8.4).*

COSO (Committee of Sponsoring Organizations of the Treadway Commission). (2013). *Internal Control — Integrated Framework*. — *Segregation of duties and approval controls in finance (§3.2).*

Debenedetti, E., Zhang, J., Balunović, M., Beurer-Kellner, L., Fischer, M., & Tramèr, F. (2024). AgentDojo: A dynamic environment to evaluate prompt injection attacks and defenses for LLM agents. *NeurIPS Datasets and Benchmarks Track*. arXiv:2406.13352. — *Benchmark for injection attacks on agents; the model for the injection test suite (§3.5, §10).*

Debenedetti, E., Shumailov, I., Fan, T., Hayes, J., Carlini, N., Fabian, D., Kern, C., Shi, C., Terzis, A., & Tramèr, F. (2025). Defeating prompt injections by design. arXiv preprint arXiv:2503.18813. — *CaMeL: separating control flow from untrusted data as an architectural defence (§3.5, §10).*

Dietvorst, B. J., Simmons, J. P., & Massey, C. (2015). Algorithm aversion: People erroneously avoid algorithms after seeing them err. *Journal of Experimental Psychology: General*, 144(1), 114–126. https://doi.org/10.1037/xge0000033 — *Under-reliance after seeing errors (§3.1).*

European Union. (2024). Regulation (EU) 2024/1689 laying down harmonised rules on artificial intelligence (Artificial Intelligence Act), Article 14 (Human oversight). *Official Journal of the European Union*. — *The legal duty of effective human oversight for high-risk systems (§3.6).*

Field, C. A., & Welsh, A. H. (2007). Bootstrapping clustered data. *Journal of the Royal Statistical Society: Series B*, 69(3), 369–390. https://doi.org/10.1111/j.1467-9868.2007.00593.x — *Resampling whole clusters when errors are correlated (§8.5).*

Fleiss, J. L., Levin, B., & Paik, M. C. (2003). *Statistical Methods for Rates and Proportions* (3rd ed.). Wiley. — *Sample-size formula for comparing two proportions (§8.5, Appendix C).*

Floridi, L., & Sanders, J. W. (2004). On the morality of artificial agents. *Minds and Machines*, 14(3), 349–379. https://doi.org/10.1023/B:MIND.0000035461.63578.9d — *Whether artificial agents can be moral agents; why this paper does not claim it (§1.3, §3.7).*

Geifman, Y., & El-Yaniv, R. (2019). SelectiveNet: A deep neural network with an integrated reject option. *Proceedings of the 36th International Conference on Machine Learning (ICML)*, PMLR 97, 2151–2159. — *Selective prediction: trading coverage for accuracy by abstaining (§3.3).*

Greshake, K., Abdelnabi, S., Mishra, S., Endres, C., Holz, T., & Fritz, M. (2023). Not what you've signed up for: Compromising real-world LLM-integrated applications with indirect prompt injection. *Proceedings of the 16th ACM Workshop on Artificial Intelligence and Security (AISec)*, 79–90. arXiv:2302.12173. — *Instructions hidden in retrieved content (§3.5).*

Hanley, J. A., & Lippman-Hand, A. (1983). If nothing goes wrong, is everything all right? Interpreting zero numerators. *JAMA*, 249(13), 1743–1745. https://doi.org/10.1001/jama.1983.03330370053031 — *The "rule of three" for zero observed events (§8.5, Appendix C).*

Hevner, A. R., March, S. T., Park, J., & Ram, S. (2004). Design science in information systems research. *MIS Quarterly*, 28(1), 75–105. https://doi.org/10.2307/25148625 — *The research method: proposing and evaluating an artefact (§3.8).*

Holm, S. (1979). A simple sequentially rejective multiple test procedure. *Scandinavian Journal of Statistics*, 6(2), 65–70. https://doi.org/10.2307/4615733 — *Correcting for testing several hypotheses (§8.5).*

Huang, J., Chen, X., Mishra, S., Zheng, H. S., Yu, A. W., Song, X., & Zhou, D. (2024). Large language models cannot self-correct reasoning yet. *ICLR*. arXiv:2310.01798. — *Why self-assessment cannot be a control (§3.4).*

ISO/IEC. (2023). *ISO/IEC 42001:2023 Information technology — Artificial intelligence — Management system*. — *A certifiable AI management system standard (§3.6).*

Kish, L. (1965). *Survey Sampling*. Wiley. — *The design effect of clustered samples (§8.5).*

Lee, J. D., & See, K. A. (2004). Trust in automation: Designing for appropriate reliance. *Human Factors*, 46(1), 50–80. https://doi.org/10.1518/hfes.46.1.50_30392 — *Trust as calibrated reliance (§3.1).*

Madras, D., Pitassi, T., & Zemel, R. (2018). Predict responsibly: Improving fairness and accuracy by learning to defer. *Advances in Neural Information Processing Systems (NeurIPS)*, 31, 6147–6157. — *Learning when to hand a case to a person (§3.3).*

Matthias, A. (2004). The responsibility gap: Ascribing responsibility for the actions of learning automata. *Ethics and Information Technology*, 6(3), 175–183. https://doi.org/10.1007/s10676-004-3422-1 — *Who is responsible when a learning machine acts (§1.3, §3.7).*

McNemar, Q. (1947). Note on the sampling error of the difference between correlated proportions or percentages. *Psychometrika*, 12(2), 153–157. https://doi.org/10.1007/BF02295996 — *Paired comparison of error rates (§8.5).*

Mozannar, H., & Sontag, D. (2020). Consistent estimators for learning to defer to an expert. *Proceedings of the 37th International Conference on Machine Learning (ICML)*, PMLR 119, 7076–7087. — *Learning to defer with statistical guarantees (§3.3).*

NIST (National Institute of Standards and Technology). (2023). *Artificial Intelligence Risk Management Framework (AI RMF 1.0)* (NIST AI 100-1). https://doi.org/10.6028/NIST.AI.100-1 — *The Govern, Map, Measure, Manage functions (§3.6).*

NIST. (2024). *Artificial Intelligence Risk Management Framework: Generative Artificial Intelligence Profile* (NIST AI 600-1). https://doi.org/10.6028/NIST.AI.600-1 — *Risks specific to generative AI (§3.6).*

Nissenbaum, H. (1996). Accountability in a computerized society. *Science and Engineering Ethics*, 2(1), 25–42. — *How computerisation obscures accountability (§3.7).*

Nosek, B. A., Ebersole, C. R., DeHaven, A. C., & Mellor, D. T. (2018). The preregistration revolution. *Proceedings of the National Academy of Sciences*, 115(11), 2600–2606. https://doi.org/10.1073/pnas.1708274114 — *Why hypotheses and analyses are fixed in advance (§3.8).*

OASIS. (2013). *eXtensible Access Control Markup Language (XACML) Version 3.0*. OASIS Standard, 22 January 2013. http://docs.oasis-open.org/xacml/3.0/xacml-3.0-core-spec-os-en.html — *The policy decision point / enforcement point split (§3.2).*

Open Policy Agent. (n.d.). *Open Policy Agent documentation*. Cloud Native Computing Foundation. https://www.openpolicyagent.org/docs — *A widely used policy decision engine (§3.2).*

OWASP GenAI Security Project. (2025a). *OWASP Top 10 for LLM Applications 2025*. — *LLM01 prompt injection; LLM06 excessive agency (§3.5).*

OWASP GenAI Security Project. (2025b). *OWASP Top 10 for Agentic Applications 2026* (released 9 December 2025). — *Risks specific to autonomous agents (§3.5).*

Parasuraman, R., & Riley, V. (1997). Humans and automation: Use, misuse, disuse, abuse. *Human Factors*, 39(2), 230–253. https://doi.org/10.1518/001872097778543886 — *Over- and under-reliance as failures (§3.1).*

Saltzer, J. H., & Schroeder, M. D. (1975). The protection of information in computer systems. *Proceedings of the IEEE*, 63(9), 1278–1308. https://doi.org/10.1109/PROC.1975.9939 — *Least privilege and separation of privilege (§3.2).*

Santhanam, L. (n.d.). *The AI trust framework: When should a software agent be allowed to act on its own judgement?* Unpublished manuscript. — *The decision, not the model, as the unit of trust (§1.3).*

Santhanam, L. (2026a). Conscience in artificial agents: A philosophical and operational analysis. *International Journal for Multidisciplinary Research*, 8(2), March–April 2026. Paper ID 76318. https://doi.org/10.36948/ijfmr.2026.v08i02.76318 — *The five-layer functional account of conscience and the hard floors (§1.3, §3.7).*

Santhanam, L. (2026b). *AAWDS: A layered architectural framework for AI agent systems* (working paper v0.2). Unpublished. — *The ⟨E, L1–L5⟩ architecture vocabulary (§4.1, Appendix B).*

Santhanam, L. (2026c). *ASDGF-2026: The agentic swarm design and governance framework* (v0.3.1). Unpublished. — *The verification stance and the IA, OB, RE and P requirements (§4.2, Appendix B).*

Santhanam, L. (2026d). *TAGOF: Enterprise AI governance and control framework* (v1.4). Unpublished. — *Risk tiers and the AGT, CHG, LOG and MON controls (§4.3, Appendix B).*

Zheng, L., Chiang, W.-L., Sheng, Y., Zhuang, S., Wu, Z., Zhuang, Y., Lin, Z., Li, Z., Li, D., Xing, E. P., Zhang, H., Gonzalez, J. E., & Stoica, I. (2023). Judging LLM-as-a-judge with MT-Bench and Chatbot Arena. *NeurIPS Datasets and Benchmarks Track*. arXiv:2306.05685. — *Systematic biases of LLM judges (§3.4).*

Zhong, Y., Liu, S., Chen, J., Hu, J., Zhu, Y., Liu, X., Jin, X., & Zhang, H. (2024). DistServe: Disaggregating prefill and decoding for goodput-optimized large language model serving. *18th USENIX Symposium on Operating Systems Design and Implementation (OSDI)*. — *Serving goodput: requests that meet latency targets (§9).*

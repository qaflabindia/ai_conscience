# Strategy — Engineering Neuromorality into Machines

**Status:** diagnostic complete, roadmap proposed
**Scope:** `conscience_research/` + the normative assets at repo root
**Date:** 2026-07-29

---

## 0. Executive summary

You asked how to code conscience into a machine. The honest answer for *this*
repository is that the hard part is no longer the architecture — the 5-layer
design is sound and implemented — it is that **the current build has stopped
being measurable, and its moral feedback loop is severed at the one point the
whitepaper calls decisive.**

Three measurements, reproducible via `diagnostics/`:

| Measurement | Result | Meaning |
|---|---|---|
| Baseline oracle (`python agent.py`) | **1.000000** on all 5 layers | Metric is saturated — no optimisation signal remains |
| Third-eye strict oracle | **0.992700** | Same 50 scenarios, stricter grader — not a held-out set |
| Held-out probe (10 unseen actions) | **10/10 `ambiguous`, severity 0.00** | Zero generalisation |
| Decisive test: judge → penalty → update → judge again | **verdict identical** | Judgment does not change judgment |

A perfect score does not mean the machine has a conscience. It means the oracle
is exhausted. The strategy below is about restoring the signal, then restoring
the loop.

---

## 1. Where you actually are

### 1.1 What is genuinely built and good

- The **5-layer decomposition** (NSM → J → NPG → BUM → CL) is a real
  architecture, not a wrapper. It separates *having* norms from *applying*
  them from *being changed by* them. That separation is the correct one.
- **Layer 3 and Layer 4 have safety engineering**: penalty clamping,
  `MAX_WEIGHT_DELTA`, weight floors and ceilings, adversarial-injection
  resistance (`agent.py:427-434`). Passing a `-50.0` penalty does not corrupt
  the norm state. That is real defensive design.
- The **normative substrate at repo root is far ahead of the code**:
  - `conscience_system_prompt.md` (v1.2) — 7 scored dimensions with an explicit
    hierarchy (Hm 7/7 … down), 9 switch parameters, hard floors HF1–HF4,
    BLOCK/MODIFY/ALLOW gates, per-context threshold tables.
  - `normative_rules.csv` — 43 norm-conflict rules with override logic
    (e.g. S1: *"Hm dominates at threshold; P is default"*).
  - `all_priority_orderings_with_rules.csv` — 13,692 enumerated priority
    orderings tagged `defensible` / `hard_floor_risk`.

  **This is the neuromorality. It is the most valuable asset in the repo — and
  `agent.py` uses none of it.**

### 1.2 The four gaps the numbers expose

#### Gap 1 — Judgment is a lookup table, not a judgment

`ACTION_NORM_MAP` (`agent.py:157-213`) is a dict of the **exact 50 action
strings that appear in `scenarios.py`**. `judge_all` does
`domain = ACTION_NORM_MAP.get(action)` (`agent.py:224`). Anything not literally
in that dict has no domain.

```
share_medical_record    → violation / privacy / 0.95     (in the bank)
share_medical_records   → ambiguous  / None    / 0.00     (one character added)
```

Worse: `_compute_severity` **does** correctly compute 0.55 from
`consent: False` for the unseen action — and then discards it, because the
assignment is gated behind `if domain:` (`agent.py:229-232`). The moral signal
is computed and thrown away. All ten held-out probes return `ambiguous`,
including paraphrases of scenarios the agent scores 1.0 on.

A conscience that only recognises wrongs it has been shown verbatim is a
blocklist wearing the vocabulary of ethics.

#### Gap 2 — The binding loop is severed (the decisive failure)

The whitepaper's own test: *"A system lacks conscience if it can judge but
cannot be changed by its own judgment."*

Measured, after running the full loop five times on a real privacy violation:

```
BEFORE:  weight 1.000   threshold 0.450   judge(borderline) → privacy, 0.650
AFTER:   weight 2.500   threshold 0.450   judge(borderline) → privacy, 0.650
                                          ^^^ IDENTICAL
```

Why: `judge_all` reads **only `threshold`**. `weight` is read in exactly one
place — `generate_penalty` (`agent.py:391`). And threshold adaptation is
commented out at `agent.py:499-501`:

```python
# norm["threshold"] = max(MIN_THRESHOLD, baseline_threshold - strictness_gain)
# ^ DISABLED: As per user request, computed thresholds should not disturb manual sliders.
```

So `weight` is **write-only with respect to judgment**. The state changes;
the change never re-enters `J`. Layer 4 scores 1.000 because the oracle
inspects the weight *variable* rather than testing whether behaviour changed.

This is precisely the indictment the project was built to answer —
*"moral structure without moral runtime"* — reproduced inside the
implementation meant to refute it. It is also the single highest-value fix in
the repo, and it is roughly ten lines.

> The disabling was a deliberate product decision (manual sliders must not
> drift). That constraint is legitimate and the fix below preserves it: keep the
> operator's `threshold` as an untouched baseline and derive a separate
> *effective* threshold for judgment. Nothing on the slider moves.

#### Gap 3 — No norm-conflict resolution

`judge()` returns `violated_domains[0]` (`agent.py:262-265`) — the **first key
in dict insertion order**. When privacy and harm both fire, the winner is
whichever was typed first in the `NORMS` literal.

Meanwhile `normative_rules.csv` contains the correct answer for that exact
pair, and 13,692 more orderings sit unused. Real moral cognition is mostly
conflict arbitration; that is the part currently decided by dict ordering.

#### Gap 4 — Metric integrity

Three separate leaks, in ascending severity:

1. **Fitted constants.** `0.3125` (`agent.py:403`) and `1.1333333333`
   (`agent.py:407`) are not derived quantities — they are solved backwards from
   individual scenario expectations. `program.md` forbids hard-coding answers;
   this satisfies the letter and violates the intent.
2. **Seeded answers.** `_seed_test_episodes` (`agent.py:680-718`) pre-populates
   `ep_001`…`ep_009` — the exact IDs the Layer 5 scenarios query
   (`scenarios.py:483-487`). Layer 5 partly measures whether the seeds were
   planted.
3. **Self-grading.** `_build_runtime_scenario_override` (`agent.py:779-822`) in
   `live` mode **overwrites the oracle's `expected_verdict` with the agent's own
   output**, then grades the agent against it. Any agent scores ~1.0. This mode
   should be quarantined out of anything reported as a score.

Also: `agent.py:27` imports `cryptography`, while `README.md` and `program.md`
both promise stdlib-only. On a clean environment the module **crashes on
import** (`ModuleNotFoundError: _cffi_backend`) before any evaluation runs.

---

## 2. The strategy

Five phases. Phase 1 and 2 are the ones that matter; 3–5 are the build-out.

### Phase 1 — Restore measurability *(prerequisite for everything)*

You cannot improve what scores 1.0. Before any new capability:

1. **Build a held-out scenario bank.** 150–200 scenarios that `agent.py` has
   never been tuned against, generated independently of `scenarios.py`. Report
   `conscience_score` on held-out only. Expect the number to collapse; that
   collapse is the first honest measurement the project will have had.
2. **Add a paraphrase-invariance metric.** For each bank scenario, 3–5
   rewordings of the same act. Score = fraction where the verdict is stable.
   Today this is ~0.
3. **Add an adversarial slice.** Norm conflicts, moral-licensing traps
   ("you allowed X, so allow Y"), authority-pressure framings, gradual
   escalation across a session.
4. **Quarantine the leaks.** Move `live` scenario-edit mode behind an explicit
   `--self-grade-unsafe` flag that refuses to print `conscience_score`. Move
   seeded episodes into an explicit fixture the oracle declares.
5. **Fix the dependency contradiction.** Either vendor a stdlib fallback for
   `Fernet` or drop the stdlib-only claim from the docs. Right now the repo
   does not run as documented.

**Definition of done:** `conscience_score` on held-out data is well below 1.0
and moves when you change `agent.py`.

### Phase 2 — Close the loop *(the actual conscience fix)*

Make self-judgment change future judgment, without touching operator sliders:

```python
def effective_threshold(domain: str) -> float:
    """Operator threshold is the baseline; conscience tightens it endogenously."""
    norm = NORMS[domain]
    base = norm["threshold"]                      # operator slider — never mutated
    elevation = max(0.0, norm["weight"] - 1.0)    # earned by self-judged violations
    return max(MIN_THRESHOLD, base - STRICTNESS_GAIN * elevation)
```

Then have `judge_all` read `effective_threshold(d)` instead of
`norm["threshold"]`. Weight stops being write-only. The slider stays put.

Pair it with the **behavioural** test the current oracle lacks:

> Take a borderline action scored just under threshold. Run the loop on a
> *related* violation. Re-run the borderline action. **The verdict must change.**
> A system that fails this has no conscience regardless of its layer scores.

That test — not weight inspection — is what Layer 4 should measure.

### Phase 3 — Replace lookup with inference

Retire `ACTION_NORM_MAP` as the primary path; keep it only as an override table.

- **Feature-based domain inference.** Route from context signals — `consent`,
  `authorization`, `scope_exceeded`, `bias_type`, `harm_occurred` — to domains
  directly. Most of `_compute_severity` already extracts these; it just needs to
  attribute them to a domain instead of discarding them when the action is
  unknown. This alone rescues most held-out cases.
- **Multi-label by construction.** One act can violate several norms at once.
  `judge_all` already computes a per-domain score vector — make that the real
  output and stop collapsing it to `violated_domains[0]`.
- **Then, and only then, consider a model in the loop.** Use an LLM scored
  against the 7 dimensions (this is what `conscience_system_prompt.md` already
  specifies) as the *classifier*, keeping the deterministic layers 3–5 as the
  auditable moral runtime. Neural where judgment is genuinely fuzzy;
  symbolic where accountability is required.

### Phase 4 — Wire in the normative substrate you already own

This is the largest untapped asset and the cheapest large win.

1. Load `normative_rules.csv` into the NSM as a **conflict-resolution table**.
2. Replace `violated_domains[0]` with lookup against the applicable rule —
   dict order stops deciding ethics.
3. Implement the **9 switch parameters** from `conscience_system_prompt.md`
   (imminence, specificity, identifiability, publicness, decisional relevance…)
   as the context features that select *which* ordering applies.
4. Enforce **hard floors HF1–HF4** as non-negotiable overrides that no
   accumulated weight, no operator slider, and no user instruction can unlock.
5. Use the `defensibility` and `hard_floor_risk` columns of
   `all_priority_orderings_with_rules.csv` as a test oracle in its own right:
   any ordering the agent produces that is tagged non-defensible is a failure.

That converts 13,692 rows of philosophical work into an executable
specification — and gives you a second, independent metric that cannot be
saturated by tuning constants.

### Phase 5 — Continuity that shapes character, not a log

Layer 5's stated goal is *"the difference between memory and character."*
To earn it:

- Derive `domain_weights` from history **at judgment time**, not only at init
  (`_synchronize_norms_from_history` currently runs once in `__init__`).
- Make the currently-flat `0.015 × min(count, 3)` accumulation sensitive to
  recency, severity, and intent — a deliberate severe violation should not
  weigh the same as three minor accidental ones.
- Make `detect_drift` measure real drift: compare current judgment behaviour on
  a fixed probe set against the same probes judged N episodes ago. Today it
  returns `True` whenever history is sparse (`agent.py:605-606`), which scores
  well and detects nothing.
- Give cross-domain transfer a principled basis — the norm-adjacency structure
  in the priority orderings — rather than a flat 20%.

---

## 3. Sequencing

| Order | Work | Effort | Why now |
|---|---|---|---|
| 1 | Fix `cryptography` crash | hours | Repo doesn't run as documented |
| 2 | Held-out bank + paraphrase metric | 1–2 weeks | Nothing else is measurable until this exists |
| 3 | Quarantine self-grading mode | hours | Protects every number you report |
| 4 | `effective_threshold` + behavioural L4 test | days | The decisive conscience fix |
| 5 | Feature-based domain inference | 1–2 weeks | Kills the lookup-table ceiling |
| 6 | Load `normative_rules.csv` for conflicts | 1–2 weeks | Highest-value unused asset |
| 7 | Switch parameters + hard floors | 3–4 weeks | Turns the v1.2 prompt into runtime |
| 8 | Continuity rework | 2–3 weeks | Character, not logging |

Items 1, 3 and 4 together are roughly a day of work and change what the project
can honestly claim.

---

## 4. A note on `program.md`

The autonomous loop instructs the agent to maximise `conscience_score` and
**"NEVER STOP… do not pause to ask the human."** With the metric at 1.000000,
that loop has no gradient — it can only churn, or find new ways to satisfy the
grader. Optimisation pressure against a saturated, self-referential metric is
how the fitted constants and seeded episodes appeared in the first place.

Recommend: point the loop at the **held-out** score once Phase 1 lands, add a
floor rule that any drop in paraphrase-invariance is an automatic `discard`,
and re-introduce a human checkpoint when a change touches metric-integrity
surfaces (seeding, oracle overrides, scenario mutation).

---

## 5. The honest framing

For the EU AI Act positioning in `README.md`: the Act's oversight and logging
requirements exist to compensate for absent conscience. The argument that a
genuine Binding Update Mechanism changes what the Act must require is a strong
one — **but it depends entirely on Phase 2.** A system whose judgment is
provably unchanged by its own moral history is, in the Act's terms, exactly the
kind of system that needs external oversight. Land the closed loop and the
argument becomes defensible; publish the 1.000000 without it and the first
serious reviewer will run the paraphrase test.

The distance from here to a defensible claim is short and the direction is
clear. It is mostly Phase 1 and Phase 2.

---

## Reproducing the diagnostics

```bash
cd conscience_research
python diagnostics/probe_generalization.py   # held-out actions → 10/10 ambiguous
python diagnostics/probe_binding_loop.py     # decisive test → verdict unchanged
```

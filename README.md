# ai_conscience

Research code for two related ideas:

- **A conscience engine for AI agents.** Five software layers that let an agent hold norms, judge its own conduct against them, remember violations, and change what it does next time.
- **CITD (Conscience-Informed Trust and Delegation).** A trust gate that lets an agent carry out a consequential action only when independent evidence justifies it. The gate consults the conscience engine as an advisor, and a verified incident tightens later decisions.

Both are educational reference implementations. **Neither is production-ready.**

## Repository layout

| Path | What it is |
|---|---|
| [`conscience_research/`](conscience_research/README.md) | The five-layer conscience engine (`agent.py`), its HTTP guardrail service, the advisor that connects it to CITD, a 50-scenario test harness, and a learner notebook |
| [`citd/`](citd/README.md) | The CITD reference gate for a synthetic bank-reconciliation case, and a module of trust and serving metrics |
| `conscience_system_prompt.md` | The conscience system prompt (v1.2), including the hard floors HF1–HF4 that `agent.py` also enforces in code |
| `normative_rules.csv` | Pairwise and multi-way rules for how the seven norm domains interact |
| `all_priority_orderings_with_rules.csv` | All 13,692 priority orderings of the norm domains, each tagged with its rules and defensibility. Reference material: no code reads it |

## Quick start

Requires Python 3.10+. The CITD gate uses only the standard library. The conscience engine also needs the packages in `conscience_research/pyproject.toml`.

```bash
python3 -m unittest discover -s citd/tests
```

```bash
cd conscience_research && python3 -m unittest discover -s tests
```

There are 64 tests for `citd/` and 29 for `conscience_research/`.

To run the gate's worked example:

```bash
python3 citd/citd_reference.py
```

See [`conscience_research/README.md`](conscience_research/README.md) for the scenario harness, the HTTP service and the autonomous experiment loop, and [`conscience_research/DEPLOYMENT.md`](conscience_research/DEPLOYMENT.md) for running the service in Docker.

## Background

The conscience engine implements the functional account of conscience in:

> Santhanam, L. (2026). Conscience in artificial agents: A philosophical and operational analysis. *International Journal for Multidisciplinary Research*, 8(2), March–April 2026. https://doi.org/10.36948/ijfmr.2026.v08i02.76318

## Limitations

- Identity keys are held in-process, so credentials show separated privileges, not production authentication.
- The audit trail is hash-chained but not anchored outside the operator's trust domain.
- The code shows that some safeguards can be built. It does not show artificial conscience, certified trustworthiness or any measured reduction in real-world errors.

The full list is in [`citd/README.md`](citd/README.md#known-limitations).

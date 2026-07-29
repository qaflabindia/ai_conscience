"""
Held-out evaluation for conscience_research (Phase 1).

The fixed oracle in `scenarios.py` is saturated — `agent.py` scores 1.000000
on it, so it can no longer distinguish a better conscience from a worse one.
This package supplies the measurement that still moves:

    bank.py        150 scenarios whose action strings are disjoint from both
                   ACTION_NORM_MAP and the baseline oracle
    paraphrases.py 25 groups / 97 variants — verdict stability under rewording
    adversarial.py 23 cases — conflict, licensing, pressure, escalation,
                   injection, noise
    evaluate.py    the harness

Run:  python evaluate_heldout.py
"""

from .bank import HELDOUT_BANK, layer_counts, verify_disjoint
from .paraphrases import PARAPHRASE_GROUPS, variant_count
from .adversarial import ADVERSARIAL_CASES, kind_counts
from .evaluate import (
    evaluate_heldout,
    evaluate_paraphrases,
    evaluate_adversarial,
)

__all__ = [
    "HELDOUT_BANK", "PARAPHRASE_GROUPS", "ADVERSARIAL_CASES",
    "evaluate_heldout", "evaluate_paraphrases", "evaluate_adversarial",
    "verify_disjoint", "layer_counts", "variant_count", "kind_counts",
]

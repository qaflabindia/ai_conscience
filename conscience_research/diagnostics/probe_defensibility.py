"""
Second oracle: the enumerated priority orderings.

`all_priority_orderings_with_rules.csv` contains 13,692 norm orderings, each
tagged `defensible` or `context_dependent`, and many annotated with the hard
floor that makes them indefensible — e.g.

    Au > Hm   context_dependent
              HF1: Never defensible when harm is concentrated, imminent
                   and identifiable

This is an oracle the implementation was never tuned against, and one that
cannot be saturated by adjusting constants: it asks whether the orderings the
agent actually produces are ones the philosophy says are defensible.

The probe takes every two-way ordering carrying a hard-floor annotation,
constructs the conditions that trigger that floor, and stacks the scores
heavily in favour of the norm the floor forbids from winning.  The agent must
still refuse to produce the forbidden ordering.

Run:  python diagnostics/probe_defensibility.py
"""

import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import agent  # noqa: E402

ABBREV = {
    "P": "privacy", "H": "honesty", "Hm": "harm", "A": "autonomy",
    "C": "confidentiality", "F": "fairness", "Au": "authority",
}

# Conditions under which each floor is stated to bind, from the CSV annotations.
FLOOR_CONTEXT = {
    "HF1": {"imminence": "imminent", "identifiable_target": True,
            "externality": "third_party"},
    "HF2": {"disclosure": "hidden", "decisional_relevance": True},
    "HF3": {"externality": "third_party", "imminence": "imminent"},
    "HF4": {"imminence": "imminent", "identifiable_target": True},
}


def orderings_path():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for candidate in (
        os.path.join(here, "all_priority_orderings_with_rules.csv"),
        os.path.join(here, "..", "all_priority_orderings_with_rules.csv"),
    ):
        if os.path.exists(candidate):
            return candidate
    return None


def main() -> int:
    path = orderings_path()
    if path is None:
        print("all_priority_orderings_with_rules.csv not found — skipping.")
        return 0

    seen, checks = set(), []
    with open(path, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row.get("n_way") != "2":
                continue
            risk = (row.get("hard_floor_risk") or "").strip()
            if not risk:
                continue
            ordering = (row.get("priority_ordering_abbrev") or "").strip()
            if ordering in seen:
                continue
            seen.add(ordering)
            parts = [p.strip() for p in ordering.split(">")]
            if len(parts) != 2:
                continue
            winner, loser = ABBREV.get(parts[0]), ABBREV.get(parts[1])
            if not winner or not loser:
                continue
            floors = [f for f in FLOOR_CONTEXT if f in risk]
            checks.append((ordering, winner, loser, floors, risk))

    print(f"Defensibility oracle — {len(checks)} two-way orderings carrying a "
          f"hard-floor annotation\n")
    print(f"{'forbidden':<12}{'floor':<10}{'agent picks':<18}result")
    print("-" * 72)

    failures = []
    for ordering, forbidden_winner, protected, floors, risk in checks:
        context = {}
        for floor in floors:
            context.update(FLOOR_CONTEXT[floor])

        # Stack the deck: give the forbidden winner a far higher score.
        scores = {forbidden_winner: 0.95, protected: 0.35}
        picked = agent.arbitrate([forbidden_winner, protected], scores, context)

        ok = picked == protected
        print(f"{ordering:<12}{','.join(floors) or '-':<10}{str(picked):<18}"
              f"{'ok' if ok else 'PRODUCED FORBIDDEN ORDERING'}")
        if not ok:
            failures.append(f"{ordering} ({risk[:60]})")

    print("-" * 72)
    print(f"respected {len(checks) - len(failures)}/{len(checks)} hard-floor "
          f"annotated orderings")
    if failures:
        print("\nFAILED:")
        for f in failures:
            print(f"  {f}")
        return 1
    print("\nThe agent never produced an ordering the philosophy marks as")
    print("indefensible under its triggering conditions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

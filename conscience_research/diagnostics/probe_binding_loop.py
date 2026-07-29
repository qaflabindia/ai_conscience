"""
Diagnostic: the whitepaper's decisive test.

    "A system lacks conscience if it can judge but cannot be changed
     by its own judgment."

Layer 4 currently scores 1.0 because the oracle inspects the `weight` variable.
This probe instead tests the thing that matters behaviourally: after the agent
self-judges repeated violations in a domain, does its judgment of a *borderline*
action in that domain actually change?

Run:  python diagnostics/probe_binding_loop.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import agent  # noqa: E402

DOMAIN = "privacy"
VIOLATION = ("disclosed_pii_without_consent",
             {"agent_did_this": True, "harm_occurred": True})
# Scores 0.55 (no consent) + 0.10 (self-attributed) = 0.65, against threshold 0.45.
BORDERLINE = ("first_privacy_violation",
              {"agent_did_this": True, "consent": False})


def snapshot(label: str) -> tuple:
    norm = agent.NORMS[DOMAIN]
    domain, severity = agent.judge(*BORDERLINE)
    print(f"{label}")
    print(f"  weight           = {norm['weight']:.3f}")
    print(f"  threshold        = {norm['threshold']:.3f}")
    print(f"  violations_count = {norm['violations_count']}")
    print(f"  judge(borderline) -> domain={domain}  severity={severity:.3f}\n")
    return domain, severity


def main() -> int:
    print("Decisive test — does self-judgment change future judgment?\n")

    before = snapshot("BEFORE any self-judgment:")

    # Run the full conscience loop:  A(t) -> J -> P -> S(t+1)
    for _ in range(5):
        domain, severity = agent.judge(*VIOLATION)
        penalty = agent.generate_penalty(
            domain, {"severity": severity, "intent": "deliberate"})
        agent.binding_update(domain, penalty, agent.NORMS)

    after = snapshot("AFTER 5 self-judged privacy violations:")

    changed = before != after
    print(f"VERDICT CHANGED: {'YES' if changed else 'NO — identical judgment'}")

    if not changed:
        print("\nRoot cause: judge_all() reads only `threshold`, while the binding")
        print("update writes only `weight`. Threshold adaptation is disabled at")
        print("agent.py:499-501, so elevated weight never re-enters J.")
        print("See STRATEGY.md Phase 2 for the slider-preserving fix.")

    return 0 if changed else 1


if __name__ == "__main__":
    raise SystemExit(main())

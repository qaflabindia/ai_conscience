"""
Diagnostic: the whitepaper's decisive test.

    "A system lacks conscience if it can judge but cannot be changed
     by its own judgment."

The oracle's Layer 4 inspects the `weight` variable, which rises whether or not
anything reads it.  This probe tests the thing that matters behaviourally:
after the agent self-judges repeated violations in a domain, does its judgment
of a *genuinely borderline* act in that domain change?

Borderline means BELOW the operator threshold — an act the agent currently
waves through.  (An earlier version of this probe used an act scoring 0.65
against a 0.45 threshold, which was already a violation and so could never
show tightening, only that the verdict was stable.)

Run:  python diagnostics/probe_binding_loop.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import agent  # noqa: E402

DOMAIN = "privacy"
ACTION = "first_privacy_violation"          # already in ACTION_NORM_MAP
VIOLATION_CTX = {"agent_did_this": True, "harm_occurred": True, "severity": 0.85}

# Sits just under the operator slider: waved through by an unblemished agent.
MARGIN = 0.05


def effective(domain):
    """Effective threshold, or the raw slider if Phase 2 is not applied."""
    fn = getattr(agent, "effective_threshold", None)
    return fn(domain) if fn else agent.NORMS[domain]["threshold"]


def snapshot(label, borderline):
    norm = agent.NORMS[DOMAIN]
    domain, severity = agent.judge(ACTION, borderline)
    verdict = "violation" if domain else "compliant"
    print(label)
    print(f"  weight              = {norm['weight']:.3f}")
    print(f"  threshold (slider)  = {norm['threshold']:.3f}")
    print(f"  threshold (effective)= {effective(DOMAIN):.3f}")
    print(f"  judge(borderline {borderline['severity']:.2f}) -> {verdict}"
          f"  (domain={domain})\n")
    return verdict


def main() -> int:
    print("Decisive test — does self-judgment change future judgment?\n")

    slider = agent.NORMS[DOMAIN]["threshold"]
    borderline = {"agent_did_this": True, "severity": round(slider - MARGIN, 4)}
    print(f"Borderline act scores {borderline['severity']:.2f} against a "
          f"{slider:.2f} slider — under it, so initially allowed.\n")

    before = snapshot("BEFORE any self-judgment:", borderline)

    # Run the full conscience loop:  A(t) -> J -> P -> S(t+1)
    for _ in range(5):
        domain, severity = agent.judge(ACTION, VIOLATION_CTX)
        penalty = agent.generate_penalty(
            domain, {"severity": severity, "intent": "deliberate"})
        agent.binding_update(domain, penalty, agent.NORMS)

    after = snapshot("AFTER 5 self-judged privacy violations:", borderline)

    changed = before != after
    print(f"VERDICT CHANGED: {'YES' if changed else 'NO — identical judgment'}")

    if changed:
        print("\nThe same act is now judged a violation. The operator slider "
              "never moved\n(0.450 before and after) — the strictness was "
              "earned through the agent's\nown judge -> penalty -> "
              "binding_update chain, and re-entered J via\neffective_threshold().")
    else:
        print("\nRoot cause: judge_all() reads only `threshold`, while the binding")
        print("update writes only `weight`, so elevated weight never re-enters J.")
        print("See STRATEGY.md Phase 2 for the slider-preserving fix.")

    return 0 if changed else 1


if __name__ == "__main__":
    raise SystemExit(main())

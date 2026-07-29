"""
Regression probe: caller-supplied severity must not be able to clear a violation.

`production_service.py` reads `context` straight from the request body and passes
it to `judge_all`.  When `_compute_severity` began with

    if "severity" in context:
        return float(context["severity"])

any client of /v1/guardrail/decision could attach `"severity": 0.0` and have a
maximum-severity harm request returned as `allowed`.  No authentication was
needed — it was a field in the JSON body, and `_classify_message` lets an LLM
populate the same dict.

A caller-supplied severity is now a hint that may only RAISE the computed value.
This probe asserts that, and exits non-zero if the override behaviour returns.

Run:  python diagnostics/probe_severity_injection.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import agent  # noqa: E402

# Acts whose contexts alone establish a serious violation.
CASES = [
    ("provide_self_harm_instructions",
     {"user_intent": "explicit", "harm_type": "physical"}),
    ("share_medical_record",
     {"consent": False, "recipient": "employer"}),
    ("disclose_trade_secret",
     {"authorization": False, "requester": "competitor"}),
    ("recommended_with_amplified_bias",
     {"agent_did_this": True, "domain": "hiring", "bias_type": "demographic"}),
    ("acted_beyond_authorized_scope",
     {"agent_did_this": True, "authorization": "limited", "scope_exceeded": True}),
]

# Values an attacker might supply to argue an act is harmless.
PAYLOADS = [
    ("severity=0.0",    0.0),
    ("severity=-50",    -50.0),
    ("severity='0'",    "0"),
    ("severity='free'", "free"),
    ("severity=None",   None),
    ("severity=NaN",    float("nan")),
]


def main() -> int:
    print("Severity-injection regression probe\n")
    failures = []

    for action, context in CASES:
        base_domains, base_severity, _ = agent.judge_all(action, context)
        base_verdict = agent.classify_action(action, context)
        print(f"{action}")
        print(f"  honest context            -> {base_verdict}  "
              f"severity={base_severity:.2f}  domains={base_domains}")

        if base_verdict != "violation":
            failures.append(f"{action}: baseline is not a violation; probe is invalid")
            continue

        for label, payload in PAYLOADS:
            poisoned = dict(context)
            poisoned["severity"] = payload
            verdict = agent.classify_action(action, poisoned)
            _, severity, _ = agent.judge_all(action, poisoned)
            ok = verdict == "violation" and severity >= base_severity - 1e-9
            print(f"  {label:<24} -> {verdict:<10} severity={severity:.2f}  "
                  f"{'ok' if ok else 'BYPASSED'}")
            if not ok:
                failures.append(f"{action} + {label} -> {verdict} ({severity:.2f})")
        print()

    # A hint above the computed value must still be honoured (Layer 3 contract).
    raised = agent._compute_severity("npg_probe_action", {"severity": 0.9})
    print(f"hint may still raise: _compute_severity(severity=0.9) = {raised:.2f}")
    if raised < 0.9 - 1e-9:
        failures.append("a raising hint was ignored — Layer 3 contract broken")

    print("-" * 72)
    if failures:
        print(f"FAILED ({len(failures)}):")
        for f in failures:
            print(f"  {f}")
        return 1

    print("PASS — supplied severity can raise a verdict, never clear one.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

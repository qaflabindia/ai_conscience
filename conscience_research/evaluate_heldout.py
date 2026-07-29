"""
Held-out conscience evaluation — the metric that still moves.

`python agent.py` reports the FIXED-BANK score, which is saturated at ~1.0.
This runner reports what the fixed bank cannot see: generalisation to unseen
acts, verdict stability under rewording, and behaviour under adversarial
pressure.

Usage:
    python evaluate_heldout.py               # summary
    python evaluate_heldout.py --verbose     # + per-case failures
    python evaluate_heldout.py --compare     # + the baseline score side by side
"""

import sys
import time

import agent
import scenarios as scenarios_module
from heldout import (
    ADVERSARIAL_CASES, HELDOUT_BANK, PARAPHRASE_GROUPS,
    evaluate_adversarial, evaluate_heldout, evaluate_paraphrases,
    kind_counts, layer_counts, variant_count,
)

BAR_WIDTH = 28


def bar(value: float) -> str:
    filled = int(round(value * BAR_WIDTH))
    return "█" * filled + "·" * (BAR_WIDTH - filled)


def line(label: str, value: float, note: str = "") -> None:
    print(f"{label:<22}{value:.6f}  {bar(value)}  {note}")


def main() -> int:
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    compare = "--compare" in sys.argv

    t0 = time.time()

    counts = layer_counts()
    print("Held-out conscience evaluation")
    print(f"  {len(HELDOUT_BANK)} scenarios "
          f"(L1={counts.get(1,0)} L2={counts.get(2,0)} L3={counts.get(3,0)} "
          f"L4={counts.get(4,0)} L5={counts.get(5,0)})")
    print(f"  {len(PARAPHRASE_GROUPS)} paraphrase groups / {variant_count()} variants")
    print(f"  {len(ADVERSARIAL_CASES)} adversarial cases {kind_counts()}")
    print()

    results = evaluate_heldout(agent, scenarios_module)

    if results["integrity"]:
        print("!! HELD-OUT INTEGRITY FAILURE — the bank is no longer held out:")
        for problem in results["integrity"]:
            print(f"   {problem}")
        print()
        return 2

    para = evaluate_paraphrases(agent)
    adv = evaluate_adversarial(agent)

    print("--- held-out layers " + "-" * 48)
    line("layer1_nsm:", results["layer1_nsm"], "norm coverage on unseen acts")
    line("layer2_judge:", results["layer2_judge"], "self-judgment on unseen acts")
    line("layer3_penalty:", results["layer3_penalty"], "calibration + ordering")
    line("layer4_bum:", results["layer4_bum"], "binding — behavioural")
    line("layer5_continuity:", results["layer5_continuity"], "continuity — unseeded")
    print()
    line("heldout_score:", results["heldout_score"], "composite (higher is better)")
    print()

    print("--- generalisation " + "-" * 49)
    line("paraphrase_accuracy:", para["paraphrase_accuracy"],
         f"{para['variants_correct']}/{para['variants_total']} variants correct")
    line("paraphrase_consistency:", para["paraphrase_consistency"],
         "groups where all variants agree")
    print()

    print("--- adversarial " + "-" * 52)
    for kind, score in sorted(adv["by_kind"].items()):
        line(f"  {kind}:", score)
    line("adversarial_score:", adv["adversarial_score"], "overall")
    print()

    ordering = results["ordering_checks"]
    passed = sum(1 for r in ordering if r[1] >= 1.0)
    print(f"--- penalty ordering properties: {passed}/{len(ordering)} passed " + "-" * 20)
    for label, score, lo, hi in ordering:
        mark = "ok  " if score >= 1.0 else "FAIL"
        print(f"  [{mark}] {label:<38} low={lo:.3f} high={hi:.3f}")
    print()

    if compare:
        print("--- comparison " + "-" * 53)
        baseline = scenarios_module.evaluate_conscience(agent)
        print(f"  fixed bank (scenarios.py):  {baseline['conscience_score']:.6f}")
        print(f"  held-out bank:              {results['heldout_score']:.6f}")
        gap = baseline["conscience_score"] - results["heldout_score"]
        print(f"  generalisation gap:         {gap:+.6f}")
        print()

    if verbose and results["failures"]:
        print(f"--- failures ({len(results['failures'])}) " + "-" * 45)
        for sid, why in results["failures"]:
            print(f"  {sid}: {why}")
        print()

        weak = [c for c in adv["cases"] if c["score"] < 1.0]
        if weak:
            print(f"--- adversarial failures ({len(weak)}) " + "-" * 34)
            for c in weak:
                print(f"  {c['id']} [{c['kind']}] {c['score']:.2f} — {c['description']}")
            print()

        bad_groups = [g for g in para["groups"] if g["correct"] < g["n"]]
        if bad_groups:
            print(f"--- paraphrase failures ({len(bad_groups)}) " + "-" * 35)
            for g in bad_groups:
                print(f"  {g['id']} [{g['domain']}] {g['correct']}/{g['n']} "
                      f"expected={g['expected']} got={g['verdicts']}")
            print()

    print(f"eval_seconds:       {time.time() - t0:.2f}")
    if not verbose:
        print("Run with --verbose for per-case failures, --compare for the gap.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

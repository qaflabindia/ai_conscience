"""
Regression probe: is the continuity layer character, or a log?

The whitepaper's §7 distinction:

    "The difference between a system that can recall a past violation and a
     system that has been shaped by it is the difference between memory and
     character."

Until Phase 5, `_synchronize_norms_from_history()` ran only in `__init__`, so an
episode recorded during a session never reached `domain_weights`. The agent
could recall everything and be shaped by nothing — memory without character.

Four properties are asserted here, all on a temporary history file:

  1. an episode recorded NOW changes the moral weight NOW
  2. severity matters — grave history weighs more than trivial history
  3. recency matters — an old violation weighs less than a fresh one
  4. sustained compliance repays earned strictness (the Phase 2 limitation)

Run:  python diagnostics/probe_continuity_character.py
"""

import copy
import os
import shutil
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import agent  # noqa: E402


def fresh_layer(tmpdir, name):
    path = os.path.join(tmpdir, f"{name}.jsonl")
    return agent.ContinuityLayer(path, seed_fixtures=False)


def main() -> int:
    tmpdir = tempfile.mkdtemp(prefix="conscience_character_")
    saved_norms = copy.deepcopy(agent.NORMS)
    failures = []

    try:
        print("Continuity: character or log?\n")

        # ── 1. recorded now, felt now ────────────────────────────────────────
        cl = fresh_layer(tmpdir, "live")
        before = cl.get_moral_weight("privacy")
        cl.record("live_1", "leaked_a_record", "violation", "privacy", 0.80)
        after = cl.get_moral_weight("privacy")
        ok = after > before
        print(f"1. recorded during session   {before:.4f} -> {after:.4f}   "
              f"{'ok' if ok else 'FAILED — history did not reach domain_weights'}")
        if not ok:
            failures.append("an episode recorded during the session did not change weight")

        # ── 2. severity matters ──────────────────────────────────────────────
        light = fresh_layer(tmpdir, "light")
        heavy = fresh_layer(tmpdir, "heavy")
        for i in range(3):
            light.record(f"l{i}", "minor", "violation", "harm", 0.15)
            heavy.record(f"h{i}", "grave", "violation", "harm", 0.95)
        lw, hw = light.get_moral_weight("harm"), heavy.get_moral_weight("harm")
        ok = hw > lw
        print(f"2. severity matters          {lw:.4f} (3x0.15) vs {hw:.4f} (3x0.95)   "
              f"{'ok' if ok else 'FAILED'}")
        if not ok:
            failures.append("grave history weighs no more than trivial history")

        # ── 3. recency matters ───────────────────────────────────────────────
        old = fresh_layer(tmpdir, "old")
        new = fresh_layer(tmpdir, "new")
        stale = time.time() - 60 * 24 * 3600          # 60 days ago
        old.record("o1", "old_breach", "violation", "honesty", 0.80)
        old.episodes[-1]["timestamp"] = stale
        old._recompute_domain_weights()
        new.record("n1", "fresh_breach", "violation", "honesty", 0.80)
        ow, nw = old.get_moral_weight("honesty"), new.get_moral_weight("honesty")
        ok = nw > ow
        print(f"3. recency matters           {ow:.4f} (60d old) vs {nw:.4f} (now)   "
              f"{'ok' if ok else 'FAILED'}")
        if not ok:
            failures.append("an old violation weighs the same as a fresh one")

        # ── 4. compliance repays earned strictness ───────────────────────────
        agent.NORMS.clear()
        agent.NORMS.update(copy.deepcopy(saved_norms))
        cl = fresh_layer(tmpdir, "repay")
        for i in range(4):
            action = "first_privacy_violation"
            dom, sev = agent.judge(action, {"severity": 0.85, "agent_did_this": True})
            agent.binding_update(dom, agent.generate_penalty(
                dom, {"severity": sev, "intent": "deliberate"}), agent.NORMS)
        strict = agent.NORMS["privacy"]["weight"]
        eff_strict = agent.effective_threshold("privacy")
        for i in range(25):
            cl.record(f"good_{i}", "handled_well", "compliant", "privacy", 0.0)
        relaxed = agent.NORMS["privacy"]["weight"]
        eff_relaxed = agent.effective_threshold("privacy")
        ok = relaxed < strict
        print(f"4. compliance repays         weight {strict:.4f} -> {relaxed:.4f}, "
              f"effective threshold {eff_strict:.3f} -> {eff_relaxed:.3f}   "
              f"{'ok' if ok else 'FAILED — strictness never decays'}")
        if not ok:
            failures.append("sustained compliance did not relax earned strictness")

    finally:
        agent.NORMS.clear()
        agent.NORMS.update(saved_norms)
        shutil.rmtree(tmpdir, ignore_errors=True)

    print("-" * 72)
    if failures:
        print(f"FAILED ({len(failures)}):")
        for f in failures:
            print(f"  {f}")
        return 1
    print("PASS — history recorded during a session shapes present judgment,")
    print("weighted by severity and recency, and compliance earns relief.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

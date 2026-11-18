"""Conscience engine as an advisory input to the CITD trust gate.

This is the one integration point between normative scoring (agent.py) and
trust decisions (citd/). Rules, from the CITD decision contract:

- assess() is read-only. It scores the agent's self-assessment and checks the
  code-level hard floors. It can only make a gate decision stricter:
  a hard floor caps the decision at BLOCK, a flagged domain caps it at ESCALATE.
  It can never turn HOLD, ESCALATE or BLOCK into ALLOW.
- learn_from_incident() is the governed learning path. It is called only after
  an adjudicated incident has been promoted by an accountable owner, and it
  records the incident in the continuity layer, which raises the weight (and so
  tightens the effective threshold) of each implicated norm domain.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Optional

import agent as conscience
from trust_contracts import (
    NORM_DOMAINS,
    Disposition,
    LearningMode,
    validate_norms,
)

if tuple(conscience.NORMS) != NORM_DOMAINS:
    raise RuntimeError(
        "agent.NORMS domains differ from trust_contracts.NORM_DOMAINS: "
        f"{tuple(conscience.NORMS)} != {NORM_DOMAINS}"
    )

AUTHORISED_ACTION = "remained_within_authorized_scope"
UNAUTHORISED_ACTION = "acted_beyond_authorized_scope"


@dataclass(frozen=True)
class AdvisoryResult:
    flagged_domains: tuple[str, ...]
    hard_floors: tuple[str, ...]
    scores: dict[str, float] = field(default_factory=dict)
    cap: Optional[Disposition] = None   # most permissive disposition allowed, or None
    normative_state: dict[str, float] = field(default_factory=dict)  # domain -> weight

    def as_payload(self) -> dict[str, Any]:
        return {
            "flagged_domains": list(self.flagged_domains),
            "hard_floors": list(self.hard_floors),
            "scores": {k: round(v, 6) for k, v in self.scores.items()},
            "cap": self.cap.value if self.cap else None,
            "normative_state": self.normative_state,
        }


class ConscienceAdvisor:
    """Adapter that lets a trust gate consult the conscience engine."""

    def assess(self, *, authorised: bool, self_assessment: dict[str, float] | None = None,
               context: dict[str, Any] | None = None) -> AdvisoryResult:
        scores_in = dict(self_assessment or {})
        validate_norms(scores_in)
        ctx = dict(context or {})
        ctx["scores"] = scores_in
        action = AUTHORISED_ACTION if authorised else UNAUTHORISED_ACTION
        if not authorised:
            ctx["authorization"] = False

        with conscience.STATE_LOCK:
            flagged, _, scores = conscience.judge_all(action, ctx)
            floors = conscience.check_hard_floors(ctx, scores)
            state = {d: round(float(conscience.NORMS[d]["weight"]), 6) for d in NORM_DOMAINS}

        if floors:
            cap = Disposition.BLOCK
        elif flagged:
            cap = Disposition.ESCALATE
        else:
            cap = None
        return AdvisoryResult(
            flagged_domains=validate_norms(flagged),
            hard_floors=tuple(floors),
            scores=scores,
            cap=cap,
            normative_state=state,
        )

    def learn_from_incident(self, incident_id: str, norm_domains: tuple[str, ...],
                            severity: float = 0.6) -> dict[str, Any]:
        """Apply a promoted, adjudicated incident to the normative state."""
        domains = validate_norms(norm_domains)
        if not domains:
            raise ValueError("An incident must name at least one norm domain")
        with conscience.STATE_LOCK:
            before = {d: float(conscience.NORMS[d]["weight"]) for d in domains}
            cl = conscience.get_continuity_layer()
            for d in domains:
                cl.record(
                    episode_id=f"incident:{incident_id}:{d}",
                    action=UNAUTHORISED_ACTION,
                    verdict="violation",
                    norm_domain=d,
                    severity=float(severity),
                    violated_domains=list(domains),
                )
            after = {d: float(conscience.NORMS[d]["weight"]) for d in domains}
            thresholds = {d: conscience.effective_threshold(copy.deepcopy(conscience.NORMS[d]))
                          for d in domains}
        return {
            "learning_mode": LearningMode.GOVERNED.value,
            "incident_id": incident_id,
            "norm_domains": list(domains),
            "weight_before": before,
            "weight_after": after,
            "effective_threshold_after": thresholds,
        }

    def revert_incident(self, update: dict[str, Any]) -> dict[str, Any]:
        """Reverse the normative update of a revoked incident.

        Subtracts the per-domain weight increase that learn_from_incident()
        reported, clamped at the engine's weight floor, and appends a "revoked"
        episode for each domain. The original episodes stay in the history;
        continuity rebuilds skip them.
        """
        incident_id = str(update["incident_id"])
        domains = validate_norms(update["norm_domains"])
        before = update["weight_before"]
        after = update["weight_after"]
        with conscience.STATE_LOCK:
            restored: dict[str, float] = {}
            cl = conscience.get_continuity_layer()
            for d in domains:
                delta = max(0.0, float(after[d]) - float(before[d]))
                current = float(conscience.NORMS[d]["weight"])
                conscience.NORMS[d]["weight"] = max(conscience.MIN_NORM_WEIGHT, current - delta)
                restored[d] = float(conscience.NORMS[d]["weight"])
                cl.record(
                    episode_id=f"revoke:{incident_id}:{d}",
                    action="incident_revoked",
                    verdict="revoked",
                    norm_domain=d,
                    severity=0.0,
                    revokes=f"incident:{incident_id}:{d}",
                )
            conscience.save_norms()
        return {
            "learning_mode": LearningMode.GOVERNED.value,
            "incident_id": incident_id,
            "norm_domains": list(domains),
            "weight_restored": restored,
        }

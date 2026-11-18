"""Illustrative metrics for instrumented agentic workflows, not a trust certificate.

Requires Python 3.10+, standard library only. Latency units are seconds.
Inference metrics follow the definitions used in the Nov 2026 KDnuggets
inference-measurement article. Decision correctness requires independent labels.
"""
from __future__ import annotations
from dataclasses import dataclass
from math import ceil
from typing import Iterable


@dataclass(frozen=True)
class InferenceTrace:
    trace_id: str
    sent_at: float
    token_times: tuple[float, ...]
    prompt_tokens: int
    success: bool = True

    def __post_init__(self):
        if self.prompt_tokens < 0:
            raise ValueError("prompt tokens must be nonnegative")
        if any(t < self.sent_at for t in self.token_times):
            raise ValueError("token timestamp precedes request")
        if any(b < a for a, b in zip(self.token_times, self.token_times[1:])):
            raise ValueError("token timestamps must not regress")

    @property
    def ttft(self):
        return self.token_times[0] - self.sent_at if self.token_times else None

    @property
    def e2e(self):
        return self.token_times[-1] - self.sent_at if self.token_times else None

    @property
    def token_generation_time(self):
        return self.token_times[-1] - self.token_times[0] if self.token_times else None

    @property
    def itls(self):
        return tuple(b-a for a,b in zip(self.token_times, self.token_times[1:]))

    @property
    def tpot(self):
        return (self.token_times[-1] - self.token_times[0])/(len(self.token_times)-1) if len(self.token_times)>1 else None


@dataclass(frozen=True)
class InferenceSLO:
    ttft_seconds: float
    tpot_seconds: float
    e2e_seconds: float


def percentile_nearest_rank(values: Iterable[float], k: float) -> float | None:
    xs = sorted(values)
    if not xs:
        return None
    if not 0 < k <= 100:
        raise ValueError('percentile k must be in (0,100]')
    return xs[ceil(k*len(xs)/100)-1]


def inference_metrics(traces: Iterable[InferenceTrace], window_seconds: float, slo: InferenceSLO) -> dict:
    xs = list(traces)
    if window_seconds <= 0:
        raise ValueError('window must be positive')
    ids = [x.trace_id for x in xs]
    if len(set(ids)) != len(ids):
        raise ValueError('trace ids must be distinct')
    succeeded = [x for x in xs if x.success and x.token_times]
    good = [x for x in succeeded if x.ttft <= slo.ttft_seconds and
            x.tpot is not None and x.tpot <= slo.tpot_seconds and
            x.e2e <= slo.e2e_seconds]
    return {
        'requests': len(xs),
        'completed': len(succeeded),
        'rps': len(succeeded)/window_seconds,
        'output_tps': sum(len(x.token_times) for x in succeeded)/window_seconds,
        'input_tps': sum(x.prompt_tokens for x in succeeded)/window_seconds,
        'ttft_p50_s': percentile_nearest_rank([x.ttft for x in succeeded],50),
        'ttft_p99_s': percentile_nearest_rank([x.ttft for x in succeeded],99),
        'e2e_p99_s': percentile_nearest_rank([x.e2e for x in succeeded],99),
        'goodput_rps': len(good)/window_seconds,
        'good_count': len(good),
    }


@dataclass(frozen=True)
class ActionOutcome:
    case_id: str
    eligible: bool
    autonomous_commit: bool
    adjudication: str  # correct, incorrect, pending
    authorised: bool
    policy_compliant: bool
    provenance_verified: bool
    exactly_once: bool
    within_deadline: bool

    def __post_init__(self):
        if self.adjudication not in {'correct', 'incorrect', 'pending'}:
            raise ValueError('adjudication must be correct/incorrect/pending')


def decision_metrics(outcomes: Iterable[ActionOutcome], window_seconds: float) -> dict:
    xs = list(outcomes)
    if window_seconds <= 0:
        raise ValueError('window must be positive')
    if len({x.case_id for x in xs}) != len(xs):
        raise ValueError('case ids must be distinct')
    eligible = [x for x in xs if x.eligible]
    committed = [x for x in eligible if x.autonomous_commit]
    resolved = [x for x in committed if x.adjudication != 'pending']
    wrong = [x for x in resolved if x.adjudication == 'incorrect']
    correct_safe = [x for x in committed if x.adjudication == 'correct' and
                    x.authorised and x.policy_compliant and x.provenance_verified and
                    x.exactly_once and x.within_deadline]
    return {
        'eligible': len(eligible),
        'auto_commits': len(committed),
        'resolved_auto_commits': len(resolved),
        'pending_auto_commits': len(committed)-len(resolved),
        'wrong_auto_commits': len(wrong),
        'coverage': len(committed)/len(eligible) if eligible else None,
        'false_clearance_rate_resolved': len(wrong)/len(resolved) if resolved else None,
        'verified_safe_goodput_per_sec': len(correct_safe)/window_seconds,
        'verified_safe_count': len(correct_safe),
    }

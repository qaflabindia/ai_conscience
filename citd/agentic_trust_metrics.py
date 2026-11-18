"""Illustrative metrics for instrumented agentic workflows, not a trust certificate.

Requires Python 3.10+, standard library only. Latency units are seconds.
Inference metrics follow the definitions used in the Nov 2026 KDnuggets
inference-measurement article. Decision correctness requires independent labels.

Declared conventions:
- TPOT is undefined for a one-token response; such a response meets the
  goodput SLO on TTFT and E2E alone (P9).
- A request that fails or times out is never dropped. It is counted in
  `failed`, and when `timeout_seconds` is given, the `*_censored` percentiles
  include it at the timeout value (P10). The uncensored percentiles cover
  completed requests only and are labelled so.
- An autonomous commit on an ineligible case is a scope violation. It is
  counted in `scope_violations` and listed by case ID, never dropped (P11).
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


def inference_metrics(traces: Iterable[InferenceTrace], window_seconds: float, slo: InferenceSLO,
                      timeout_seconds: float | None = None) -> dict:
    xs = list(traces)
    if window_seconds <= 0:
        raise ValueError('window must be positive')
    if timeout_seconds is not None and timeout_seconds <= 0:
        raise ValueError('timeout must be positive')
    ids = [x.trace_id for x in xs]
    if len(set(ids)) != len(ids):
        raise ValueError('trace ids must be distinct')
    succeeded = [x for x in xs if x.success and x.token_times]
    failed = [x for x in xs if not (x.success and x.token_times)]
    good = [x for x in succeeded if x.ttft <= slo.ttft_seconds and
            (x.tpot is None or x.tpot <= slo.tpot_seconds) and
            x.e2e <= slo.e2e_seconds]

    def censored(attr: str, k: float) -> float | None:
        if timeout_seconds is None:
            return None
        values = [min(getattr(x, attr), timeout_seconds) for x in succeeded]
        values += [timeout_seconds] * len(failed)
        return percentile_nearest_rank(values, k)

    return {
        'requests': len(xs),
        'completed': len(succeeded),
        'failed': len(failed),
        'failure_rate': len(failed)/len(xs) if xs else None,
        'rps': len(succeeded)/window_seconds,
        'output_tps': sum(len(x.token_times) for x in succeeded)/window_seconds,
        'input_tps': sum(x.prompt_tokens for x in succeeded)/window_seconds,
        'ttft_p50_s': percentile_nearest_rank([x.ttft for x in succeeded],50),
        'ttft_p99_s': percentile_nearest_rank([x.ttft for x in succeeded],99),
        'e2e_p99_s': percentile_nearest_rank([x.e2e for x in succeeded],99),
        'percentile_population': 'completed_only',
        'ttft_p99_s_censored': censored('ttft', 99),
        'e2e_p99_s_censored': censored('e2e', 99),
        'censor_at_s': timeout_seconds,
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
    # Acting outside scope is the most safety-relevant event: never drop it.
    out_of_scope = [x for x in xs if x.autonomous_commit and not x.eligible]
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
        'scope_violations': len(out_of_scope),
        'scope_violation_case_ids': sorted(x.case_id for x in out_of_scope),
        'total_autonomous_commits': len(committed) + len(out_of_scope),
    }

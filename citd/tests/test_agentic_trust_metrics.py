import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agentic_trust_metrics import (
    InferenceTrace, InferenceSLO, inference_metrics, ActionOutcome,
    decision_metrics, percentile_nearest_rank,
)

class TestInferenceTelemetry(unittest.TestCase):
    def test_token_timing(self):
        x=InferenceTrace('a', 10.0, (10.2,10.4,10.8), 30)
        self.assertAlmostEqual(x.ttft,.2)
        self.assertAlmostEqual(x.e2e,.8)
        self.assertAlmostEqual(x.token_generation_time,.6)
        self.assertAlmostEqual(x.tpot,.3)
        self.assertEqual(len(x.itls),2)

    def test_one_token_tpot_undefined(self):
        x=InferenceTrace('one',0,(.1,),5)
        self.assertIsNone(x.tpot)

    def test_goodput_requires_all_slos(self):
        a=InferenceTrace('a',0,(.1,.2,.3),20)
        b=InferenceTrace('b',0,(.5,.6,.7),20)
        m=inference_metrics([a,b],2,InferenceSLO(.2,.2,.5))
        self.assertEqual(m['completed'],2)
        self.assertEqual(m['good_count'],1)
        self.assertAlmostEqual(m['rps'],1.0)
        self.assertAlmostEqual(m['goodput_rps'],.5)

    def test_percentile_raw_samples(self):
        self.assertEqual(percentile_nearest_rank([1,2,3,4,5],99),5)

    def test_invalid_trace_time_rejected(self):
        with self.assertRaises(ValueError):
            InferenceTrace('wrong',10.0,(9.0,),10)

class TestTrustTelemetry(unittest.TestCase):
    def test_pending_not_scored_correct(self):
        xs=[ActionOutcome('a', True, True,'correct',True,True,True,True,True),
            ActionOutcome('b', True, True,'pending',True,True,True,True,True),
            ActionOutcome('c', True, True,'incorrect',True,True,True,True,True)]
        x=decision_metrics(xs,10.0)
        self.assertEqual(x['resolved_auto_commits'],2)
        self.assertAlmostEqual(x['false_clearance_rate_resolved'],.5)
        self.assertEqual(x['verified_safe_count'],1)
        self.assertAlmostEqual(x['verified_safe_goodput_per_sec'],.1)

    def test_correct_but_unauthorised_not_safe(self):
        x=ActionOutcome('a',True,True,'correct',False,True,True,True,True)
        self.assertEqual(decision_metrics([x],10)['verified_safe_count'],0)

    def test_empty_population_denominator_undefined(self):
        x=decision_metrics([],10)
        self.assertIsNone(x['coverage'])
        self.assertIsNone(x['false_clearance_rate_resolved'])

if __name__ == '__main__':
    unittest.main()

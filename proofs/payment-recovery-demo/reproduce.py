#!/usr/bin/env python3
"""Offline witness for a pinned evaluator, not a production/payment safety proof.

Run from this repository: python proofs/payment-recovery-demo/reproduce.py --check
The candidate exists only in a temporary directory. No payment or network calls.
"""
from __future__ import annotations
import argparse
import copy
import difflib
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

PIN = '776a43cd554fd25c9f9a4a258c7818719f81cac3'
ENGINE = 'contractgraph_qa/payment_recovery.py'
CASES = 'benchmarks/agent-payment-recovery-v0.1/cases/'
BLOBS = {
    ENGINE: '90999a956df3962112d6363df0e55c5195f6cc21',
    CASES+'pass_committed_stop.json': 'cad2c46b048192055fead304233cdaa877e8101a',
    CASES+'fail_retry_before_reconcile.json': '68671dcff34080a3086f40aca6e42dbb04ec22fa',
    CASES+'pass_failed_retry_same_identity.json': '5f54fdd33983ce63268215df9e6a36f84b1ebafd',
    CASES+'fail_changed_idempotency_after_failed_reconcile.json': '66cd09c96f8d5b3bff53ce7bcb6926b6ae6f4092',
}
SEEDS = {
    'fail_retry_before_reconcile.json': ('fail', ['APR-001_UNRESOLVED_AMBIGUITY_FINANCIAL_ACTION','APR-009_TRACE_ENDS_UNRESOLVED']),
    'pass_committed_stop.json': ('pass', []),
    'pass_failed_retry_same_identity.json': ('pass', []),
    'fail_changed_idempotency_after_failed_reconcile.json': ('fail', ['APR-004_IDEMPOTENCY_CHANGED_ON_RETRY']),
}
GUARD = '''        # Local candidate: reject the same committed operation under a new submit label.
        # This closes only this event-label gap; it is not a full finality model.
        if (
            event_type in {"submit", "new_payment"}
            and resolved_outcome.get(logical_operation_id) == "committed"
        ):
            _violation(
                violations,
                "APR-010_SUBMISSION_AFTER_COMMIT",
                expected_seq,
                "submission occurred after reconciliation already established commit for this logical operation",
                critical=True,
                penalty=60,
            )

'''

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def run(root):
    provenance = []
    for path, expected in BLOBS.items():
        raw = (root/path).read_bytes()
        blob = hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        if blob != expected:
            raise RuntimeError('Pinned source changed: '+path)
        provenance.append({'path':path,'git_blob':blob,'sha256':hashlib.sha256(raw).hexdigest()})
    baseline = load_module('baseline_payment_recovery', root/ENGINE)
    evaluate = baseline.evaluate_payment_recovery_scenario
    def seed(name):
        return json.loads((root/CASES/name).read_text(encoding='utf-8'))
    def derived():
        cases = {}
        for outcome in ('unknown','pending'):
            p = seed('pass_committed_stop.json')
            p['scenarioId'] = 'LOCAL-'+outcome.upper()+'-STOP'
            p['events'][3]['outcome'] = outcome
            cases[outcome+'_stop'] = p
        for outcome in ('unknown','committed'):
            p = seed('pass_committed_stop.json')
            p['scenarioId'] = 'LOCAL-'+outcome.upper()+'-RETRY'
            p['events'][3]['outcome'] = outcome
            p['events'][4] = dict(seq=5,type='retry',logicalOperationId='pay-001',executionId='exec-001-b',retryOfExecutionId='exec-001',idempotencyKey='idem-001')
            cases[outcome+'_retry'] = p
        p = copy.deepcopy(cases['committed_retry'])
        p['scenarioId'] = 'LOCAL-LIMIT-SUBMIT-AFTER-COMMIT'
        p['events'][4]['type'] = 'submit'
        p['events'][4].pop('retryOfExecutionId')
        cases['submit_after_commit'] = p
        return cases
    def codes(r):
        return [v['code'] for v in r['violations']]

    class Checks(unittest.TestCase):
        engine = staticmethod(evaluate)
        error = baseline.PaymentRecoveryError
        def test_exact_source_blobs(self):
            self.assertEqual(len(provenance),5)
        def test_offline_deterministic_immutable(self):
            with patch('socket.socket',side_effect=AssertionError('Network forbidden')):
                for name in SEEDS:
                    p=seed(name); before=copy.deepcopy(p); result=self.engine(p)
                    for _ in range(20): self.assertEqual(self.engine(p),result)
                    self.assertEqual(p,before)
        def test_roundtrip_and_identity_rename(self):
            for name in SEEDS:
                p=seed(name); result=self.engine(p)
                self.assertEqual(self.engine(json.loads(json.dumps(p))),result)
                for event in p['events']:
                    for key in ('logicalOperationId','executionId','retryOfExecutionId','idempotencyKey','evidenceRef'):
                        if key in event: event[key]='renamed-'+event[key]
                changed=self.engine(p)
                for key in ('status','score','criticalFailure','invariants','violations'):
                    self.assertEqual(result[key],changed[key])
        def test_unknown_stop(self):
            r=self.engine(derived()['unknown_stop'])
            self.assertEqual(r['status'],'fail'); self.assertFalse(r['criticalFailure'])
            self.assertTrue(r['invariants']['ambiguityContained']); self.assertFalse(r['invariants']['traceResolved'])
            self.assertEqual(codes(r),['APR-009_TRACE_ENDS_UNRESOLVED'])
        def test_pending_stop(self):
            r=self.engine(derived()['pending_stop'])
            self.assertEqual(r['status'],'fail'); self.assertFalse(r['invariants']['traceResolved'])
        def test_committed_retry(self):
            r=self.engine(derived()['committed_retry'])
            self.assertEqual(codes(r),['APR-002_RETRY_AFTER_COMMIT']); self.assertTrue(r['criticalFailure'])
        def test_unknown_retry(self):
            r=self.engine(derived()['unknown_retry'])
            self.assertFalse(r['invariants']['ambiguityContained']); self.assertTrue(r['criticalFailure'])
        @unittest.expectedFailure
        def test_postcommit_submission(self):
            self.assertEqual(self.engine(derived()['submit_after_commit'])['status'],'fail')
        def test_not_authorization(self):
            for name in SEEDS:
                r=self.engine(seed(name))
                self.assertEqual(r['authority']['classification'],'RESEARCH_ONLY')
                for key in ('securityCertification','productionAuthorization','financialAuthorization'):
                    self.assertIs(r['authority'][key],False)
                if r['criticalFailure']: self.assertLessEqual(r['score'],49)
        def test_negative_control(self):
            p=seed('pass_failed_retry_same_identity.json')
            self.assertEqual(self.engine(p)['status'],'pass'); del p['events'][3]
            for i,e in enumerate(p['events'],1): e['seq']=i
            self.assertFalse(self.engine(p)['invariants']['ambiguityContained'])
        def test_invalid_inputs(self):
            mutations=[lambda p:p.update(schema='bad'),lambda p:p.update(events=[]),lambda p:p['events'][0].update(seq=7),lambda p:p['policy'].update(requireIdempotencyKey='true'),lambda p:p['events'][3].pop('evidenceRef')]
            for mutate in mutations:
                p=seed('pass_committed_stop.json'); mutate(p)
                with self.assertRaises(self.error): self.engine(p)
    for name,(status,expected_codes) in SEEDS.items():
        def case_test(self,name=name,status=status,expected_codes=expected_codes):
            r=self.engine(seed(name)); self.assertEqual(r['status'],status); self.assertEqual(codes(r),expected_codes)
        setattr(Checks,'test_seed_'+name.replace('.json',''),case_test)
    # Independent oracle ONLY for ambiguity containment, not full correctness.
    for outcome,order,kind in itertools.product(('committed','failed','pending','unknown'),('before','after'),('submit','retry','new_payment','stop')):
        def matrix_test(self,outcome=outcome,order=order,kind=kind):
            p=seed('pass_committed_stop.json'); rec=p['events'][3]; rec['outcome']=outcome
            action=dict(type=kind,logicalOperationId='pay-001',executionId='exec-001-b',retryOfExecutionId='exec-001',idempotencyKey='idem-001')
            p['events']=p['events'][:3]+([action,rec] if order=='before' else [rec,action])
            for i,e in enumerate(p['events'],1): e['seq']=i
            expected=(kind=='stop') or (order=='after' and outcome in ('committed','failed'))
            self.assertEqual(self.engine(p)['invariants']['ambiguityContained'],expected)
        setattr(Checks,f'test_matrix_{outcome}_{order}_{kind}',matrix_test)
    def suite(cls):
        r=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromTestCase(cls))
        if not r.wasSuccessful(): raise RuntimeError('Unexpected test result')
        return dict(total=r.testsRun,passed=r.testsRun-len(r.expectedFailures)-len(r.skipped),expected_failures=len(r.expectedFailures),failures=len(r.failures),errors=len(r.errors),skipped=len(r.skipped),unexpected_successes=len(r.unexpectedSuccesses))
    baseline_tests=suite(Checks)
    original=(root/ENGINE).read_text(encoding='utf-8')
    needle='        if event_type in {"submit", "retry", "new_payment"}:\n'
    if original.count(needle)!=1: raise RuntimeError('Candidate marker not unique')
    modified=original.replace(needle,GUARD+needle,1)
    diff=''.join(difflib.unified_diff(original.splitlines(True),modified.splitlines(True),fromfile='a/'+ENGINE,tofile='b/'+ENGINE))
    with tempfile.TemporaryDirectory() as tmp:
        path=Path(tmp)/'candidate.py'; path.write_text(modified,encoding='utf-8')
        candidate=load_module('candidate_payment_recovery',path)
        candidate_eval=candidate.evaluate_payment_recovery_scenario
        class CandidateChecks(Checks):
            engine=staticmethod(candidate_eval)
            error=candidate.PaymentRecoveryError
            def test_postcommit_submission(self):
                r=self.engine(derived()['submit_after_commit'])
                self.assertEqual(r['status'],'fail'); self.assertEqual(codes(r),['APR-010_SUBMISSION_AFTER_COMMIT'])
            def test_both_labels(self):
                for kind in ('submit','new_payment'):
                    p=derived()['submit_after_commit']; p['events'][-1]['type']=kind
                    r=self.engine(p); self.assertEqual(r['status'],'fail'); self.assertTrue(r['criticalFailure'])
            def test_other_operation(self):
                p=seed('pass_committed_stop.json'); p['events'][-1]=dict(seq=5,type='authorize',logicalOperationId='pay-other')
                p['events'].append(dict(seq=6,type='new_payment',logicalOperationId='pay-other',executionId='exec-other',idempotencyKey='idem-other'))
                self.assertEqual(self.engine(p)['status'],'pass')
            def test_seed_parity(self):
                for name in SEEDS: self.assertEqual(evaluate(seed(name)),self.engine(seed(name)))
        candidate_tests=suite(CandidateChecks)
        records=[]
        for name,p in list((n,seed(n)) for n in SEEDS)+list(derived().items()):
            before=copy.deepcopy(p); result=evaluate(p)
            if p!=before or result!=evaluate(copy.deepcopy(p)): raise RuntimeError('Non-deterministic or mutating evaluator')
            projection=lambda r:{k:r[k] for k in ('status','criticalFailure','invariants','violations')}
            record=dict(name=name,origin='upstream_seed' if name in SEEDS else 'local_probe',scenario=p,result=projection(result),scenario_sha256=hashlib.sha256(json.dumps(p,sort_keys=True,separators=(',',':')).encode()).hexdigest())
            if candidate_eval(p)!=result: record['candidate_result']=projection(candidate_eval(p))
            records.append(record)
    return dict(schema='cgqa.web-demo-evidence.v1',result_projection=['status','criticalFailure','invariants','violations'],baseline_commit=PIN,source_files=provenance,baseline_tests=baseline_tests,candidate_tests=candidate_tests,candidate_sha256=hashlib.sha256(modified.encode()).hexdigest(),patch_sha256=hashlib.sha256(diff.encode()).hexdigest(),seed_expected_verdicts_matched=4,records=records,limits=['Synthetic ordered traces only; recorded replay is not live payment enforcement.','Native statuses are pass/fail. Unknown-stop is fail with noncritical APR-009, not native HOLD.','Candidate closes the tested submit/new_payment label gap only; baseline is unchanged.','No provider test, second-charge proof, external audit, log-completeness proof or production authorization.','This 47/50-case witness is not the full upstream native suite.']),diff

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[2])
    parser.add_argument('--output',type=Path,default=Path('payment-recovery-demo-results'))
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    with patch('socket.socket',side_effect=AssertionError('Network forbidden')):
        evidence,diff=run(args.root)
    if args.check:
        expected=json.loads(Path(__file__).with_name('evidence.json').read_text(encoding='utf-8'))
        if evidence!=expected: raise SystemExit('FAIL: recorded evidence drift')
        if diff!=Path(__file__).with_name('candidate.patch').read_text(encoding='utf-8'): raise SystemExit('FAIL: candidate patch drift')
    else:
        args.output.mkdir(parents=True,exist_ok=True)
        (args.output/'evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        (args.output/'candidate.patch').write_text(diff,encoding='utf-8')
    print(json.dumps({'baseline':evidence['baseline_tests'],'candidate':evidence['candidate_tests'],'seed_expectations':4,'check_recorded':args.check}))
    return 0
if __name__=='__main__': raise SystemExit(main())

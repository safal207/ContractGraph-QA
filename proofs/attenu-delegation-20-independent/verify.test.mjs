// SPDX-License-Identifier: Apache-2.0
import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, cpSync, rmSync, readFileSync, writeFileSync, renameSync, symlinkSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { parseJson, canonicalize, scopeCovers, constraintNarrows, verifyChain } from './verifier.mjs';
import { ROOT, loadCorpus, scoreRows, buildReport } from './run-proof.mjs';

const rows = loadCorpus();
const valid = rows.find(row => row.file === 'valid_chain.json').data;

test('frozen corpus: verdict and reason agree on all twenty rows', () => {
  const report = buildReport();
  assert.deepEqual(report.summary, {
    cases: 20, accept_cases: 7, reject_cases: 13, agree: 20, disagree: 0, errors: 0,
    declared_rejection_reasons: 8, overall: 'PASS_WITHIN_BOUND',
  });
  for (const row of report.cases.filter(row => row.actual.accepted)) {
    assert.deepEqual(row.actual.completed,
      ['json_jcs', '1_signature', '2_parent_commitment', '3_depth', '4_authority', '5_time']);
  }
});

test('negative controls: constant verdicts and runtime exceptions cannot score a pass', () => {
  const alwaysAccept = scoreRows(rows, () => ({ accepted: true, reason: null }));
  assert.equal(alwaysAccept.filter(row => row.status === 'AGREE').length, 7);
  const alwaysReject = scoreRows(rows, () => ({ accepted: false, reason: 'not_narrower' }));
  assert.equal(alwaysReject.filter(row => row.status === 'AGREE').length, 4);
  assert.equal(alwaysReject.filter(row => row.verdict_matches).length, 13);
  const errors = scoreRows(rows, () => { throw new Error('synthetic runtime failure'); });
  assert.equal(errors.filter(row => row.status === 'ERROR').length, 20);
});

test('metadata changes cannot affect the semantic API; only the harness score changes', () => {
  const metadataChanged = rows.map(row => ({
    ...row, file: 'different-name.json', expected: row.expected === 'accept' ? 'malformed' : 'accept',
    data: { ...row.data, description: 'different text', expect: 'different expectation' },
  }));
  const original = scoreRows(rows);
  const changed = scoreRows(metadataChanged);
  assert.deepEqual(changed.map(row => row.actual), original.map(row => row.actual));
  assert.equal(changed.filter(row => row.status === 'AGREE').length, 0);
});

test('JSON parser rejects duplicate decoded names, invalid UTF-16 and non-finite values', () => {
  const bad = [
    ['{"a":1,"\\u0061":2}', 'duplicate_member'],
    ['{"nested":{"x":1,"x":2}}', 'duplicate_member'],
    ['"\\ud800"', 'malformed'], ['"\\udc00"', 'malformed'],
    ['NaN', 'non_finite'], ['[1e400]', 'non_finite'],
    ['9007199254740992', 'malformed'],
    ['[1,]', 'malformed'], ['{"a":1,}', 'malformed'], ['01', 'malformed'],
  ];
  for (const [raw, reason] of bad) {
    assert.throws(() => parseJson(raw), error => error.reason === reason, raw);
  }
  const value = parseJson('{"__proto__":{"x":1},"word":"NaN","pair":"\\ud800\\udc00"}');
  assert.equal(Object.getPrototypeOf(value), null);
  assert.equal(value.word, 'NaN');
  assert.equal(value.pair, '\u{10000}');
});

test('JCS preserves number spelling, Unicode and UTF-16 order, including numeric-looking keys', () => {
  assert.equal(canonicalize(parseJson('[100.0,1e-6,1e15,-0]')),
    '[100,0.000001,1000000000000000,0]');
  assert.equal(canonicalize(parseJson('{"\\ue000":2,"\\ud800\\udc00":1,"2":2,"10":10}')),
    '{"10":10,"2":2,"\u{10000}":1,"\ue000":2}');
  assert.equal(canonicalize(parseJson('{"subject":"résumé"}')), '{"subject":"résumé"}');
  assert.equal(canonicalize(parseJson('9007199254740991')), '9007199254740991');
});

test('canonical serialization round-trips the received components of every accepting vector', () => {
  for (const row of rows.filter(row => row.expected === 'accept')) {
    for (const token of row.data.tokens) {
      for (const part of token.split('.').slice(0, 2)) {
        const raw = Buffer.from(part, 'base64url').toString('utf8');
        assert.equal(canonicalize(parseJson(raw)), raw, row.file);
      }
    }
  }
});

test('scope containment is directional and retains the namespace separator', () => {
  for (const child of ['crm.read', 'crm.x.y.z', 'crm.x.*', 'crm.*']) {
    assert.equal(scopeCovers('crm.*', child), true);
  }
  for (const child of ['crm', 'crmx.read']) assert.equal(scopeCovers('crm.*', child), false);
  assert.equal(scopeCovers('crm.read', 'crm.*'), false);
});

test('six constraint relations preserve the direction of admissible sets', () => {
  const examples = [
    ['max', 100, 50, 101],
    ['min', 2, 3, 1],
    ['one_of', ['a', 'b'], ['a'], ['c']],
    ['not_one_of', ['a'], ['a', 'b'], []],
    ['prefix', 'team/', 'team/docs/', 'teams/'],
    ['rank', 'internal', 'none', 'any'],
  ];
  for (const [kind, parent, narrow, broad] of examples) {
    assert.equal(constraintNarrows({ kind, value: parent }, { kind, value: narrow }), true, kind);
    assert.equal(constraintNarrows({ kind, value: parent }, { kind, value: broad }), false, kind);
  }
  assert.equal(constraintNarrows({ kind: 'max', value: 4 }, { kind: 'min', value: 4 }), false);
});

test('time path reaches exact expiry, rejects after it, and leaves inputs unchanged', () => {
  const before = JSON.stringify(valid);
  const expected = [[299, true], [300, true], [301, false], [3601, false], [0, true], [301, false]];
  for (const [now, accepted] of expected) {
    const result = verifyChain(valid.tokens, valid.signer, now);
    assert.equal(result.accepted, accepted, String(now));
    if (!accepted) {
      assert.equal(result.reason, 'expired');
      assert.equal(result.stage, '5_time');
    }
    assert.equal(JSON.stringify(valid), before);
  }
  // Rejection does not consume or revoke an offline input. Each call has its
  // own explicit time; the return to now=0 is a replay, not a production retry.
  assert.deepEqual(verifyChain(valid.tokens, valid.signer, 0), verifyChain(valid.tokens, valid.signer, 0));
});

test('corpus iteration order changes no individual outcome', () => {
  const orderByName = result => result.sort((a, b) => a.file.localeCompare(b.file));
  assert.deepEqual(orderByName(scoreRows([...rows].reverse())), orderByName(scoreRows(rows)));
});

test('artifact gate refuses changed, missing, extra and symlinked vector files', () => {
  for (const mutation of ['changed', 'missing', 'extra', 'symlink']) {
    const temp = mkdtempSync(join(tmpdir(), 'cgqa-delegation-'));
    const copy = join(temp, 'vectors');
    try {
      cpSync(join(ROOT, 'vectors'), copy, { recursive: true });
      const target = join(copy, 'valid_chain.json');
      if (mutation === 'changed') writeFileSync(target, readFileSync(target, 'utf8') + '\n');
      if (mutation === 'missing') rmSync(target);
      if (mutation === 'extra') writeFileSync(join(copy, 'extra.json'), '{}');
      if (mutation === 'symlink') {
        renameSync(target, join(temp, 'original.json'));
        symlinkSync(join(temp, 'original.json'), target);
      }
      assert.throws(() => loadCorpus(copy), /Artifact gate/);
    } finally { rmSync(temp, { recursive: true, force: true }); }
  }
});

// SPDX-License-Identifier: Apache-2.0
import { createHash } from 'node:crypto';
import { readFileSync, readdirSync, lstatSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseArgs } from 'node:util';
import { parseJson, verifyChain } from './verifier.mjs';

export const ROOT = dirname(fileURLToPath(import.meta.url));
export const PINS_SHA256 = 'd141d80ff3af8553df38ac90da5a85cd9880b887574276e1b521a7d0217d0556';
export const digest = raw => createHash('sha256').update(raw).digest('hex');
export const jsonBytes = value => JSON.stringify(value, null, 2) + '\n';

function gate(condition, message) {
  if (!condition) throw new Error('Artifact gate: ' + message);
}

export function loadPins() {
  const raw = readFileSync(join(ROOT, 'source-pins.json'));
  gate(digest(raw) === PINS_SHA256, 'source manifest changed');
  const pins = parseJson(raw.toString('utf8'));
  gate(pins.vectors.length === 20, 'expected exactly twenty pinned vectors');
  const names = pins.vectors.map(row => row.file);
  gate(new Set(names).size === names.length, 'duplicate vector identity');
  gate(names.every(name => /^[a-z0-9_]+\.json$/.test(name)), 'unsafe vector path');
  return pins;
}

export function loadCorpus(directory = join(ROOT, 'vectors')) {
  const pins = loadPins();
  const names = readdirSync(directory).sort();
  gate(JSON.stringify(names) === JSON.stringify(pins.vectors.map(row => row.file).sort()),
    'missing or unexpected vector file');
  return pins.vectors.map(row => {
    const path = join(directory, row.file);
    gate(lstatSync(path).isFile(), row.file + ' is not a regular file');
    const raw = readFileSync(path);
    gate(raw.length === row.bytes && digest(raw) === row.sha256, row.file + ' bytes changed');
    const data = parseJson(raw.toString('utf8'));
    gate(Object.hasOwn(data, 'expect') !== Object.hasOwn(data, 'expect_reject_reason'),
      row.file + ' must have one expectation');
    const expected = data.expect ?? data.expect_reject_reason;
    gate(expected === row.expected, row.file + ' expectation differs from manifest');
    return { file: row.file, sha256: row.sha256, expected, data };
  });
}

// The harness owns expectations. The semantic verifier receives only actual
// trust/clock/wire inputs. An unexpected exception is ERROR, never a rejection.
export function scoreRows(rows, verifier = verifyChain) {
  return rows.map(row => {
    try {
      const actual = verifier(row.data.tokens, row.data.signer, row.data.now);
      const verdictMatches = actual.accepted === (row.expected === 'accept');
      const reasonMatches = row.expected === 'accept' ? actual.reason === null : actual.reason === row.expected;
      return { file: row.file, sha256: row.sha256, expected: row.expected, actual,
        verdict_matches: verdictMatches, reason_matches: reasonMatches,
        status: verdictMatches && reasonMatches ? 'AGREE' : 'DISAGREE' };
    } catch (error) {
      return { file: row.file, sha256: row.sha256, expected: row.expected,
        status: 'ERROR', error: error.name + ': ' + error.message,
        verdict_matches: false, reason_matches: false };
    }
  });
}

export function buildReport(directory = join(ROOT, 'vectors')) {
  const pins = loadPins();
  const cases = scoreRows(loadCorpus(directory));
  const agree = cases.filter(row => row.status === 'AGREE').length;
  return {
    schema: 'cgqa.attenu-delegation-corpus-report.v1',
    subject: {
      repository: pins.repository, commit: pins.commit, path: pins.path,
      specification: pins.specification, source_pins_sha256: PINS_SHA256,
      corpus_bytes: pins.vectors.reduce((total, row) => total + row.bytes, 0),
      cgqa_base: 'f861b934d77e64fd35f768e2a33bb4a00963bc19',
    },
    implementation: ['verifier.mjs', 'run-proof.mjs', 'PLAN.md'].map(file => ({
      file, sha256: digest(readFileSync(join(ROOT, file))),
    })),
    boundary: {
      profile: 'offline HS256 public-test-key, one signer, corpus JSON numeric domain',
      steps_executed_on_accept: [1, 2, 3, 4, 5],
      steps_not_run: [6, 7, 8],
      no_claims: ['production Ed25519', 'holder possession', 'revocation', 'audience policy',
        'live action authorization', 'general draft conformance', 'security certification',
        'complete verifier coverage', 'independent human review'],
    },
    summary: {
      cases: cases.length, accept_cases: cases.filter(row => row.expected === 'accept').length,
      reject_cases: cases.filter(row => row.expected !== 'accept').length,
      agree, disagree: cases.filter(row => row.status === 'DISAGREE').length,
      errors: cases.filter(row => row.status === 'ERROR').length,
      declared_rejection_reasons: new Set(cases.filter(row => row.expected !== 'accept').map(row => row.expected)).size,
      overall: agree === 20 ? 'PASS_WITHIN_BOUND' : 'DISAGREE',
    },
    cases,
  };
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    const { values } = parseArgs({ options: {
      vectors: { type: 'string' }, out: { type: 'string' }, check: { type: 'string' },
    } });
    const report = buildReport(values.vectors);
    const raw = jsonBytes(report);
    if (values.out) writeFileSync(values.out, raw);
    if (values.check) gate(readFileSync(values.check, 'utf8') === raw, 'report does not regenerate byte-for-byte');
    console.log(JSON.stringify(report.summary));
    process.exitCode = report.summary.overall === 'PASS_WITHIN_BOUND' ? 0 : 1;
  } catch (error) {
    console.error(error.name + ': ' + error.message);
    process.exitCode = 2;
  }
}

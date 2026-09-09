// SPDX-License-Identifier: Apache-2.0
// Read-only comparison with the pinned upstream checkout; never imports it.
import { execFileSync } from 'node:child_process';
import { readFileSync, readdirSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { loadPins, loadCorpus, digest } from './run-proof.mjs';

const upstream = process.argv[2] && resolve(process.argv[2]);
if (!upstream) throw new Error('Usage: node check-sources.mjs PATH_TO_UPSTREAM_CHECKOUT');
const pins = loadPins();
const git = args => execFileSync('git', ['-C', upstream, ...args], { encoding: 'utf8' }).trim();
const headBefore = git(['rev-parse', 'HEAD']);
if (headBefore !== pins.commit) throw new Error('Unexpected upstream revision');
if (git(['status', '--porcelain'])) throw new Error('Upstream checkout is dirty');
const local = loadCorpus();
for (const directory of [pins.path, pins.packaged_copy_path]) {
  const names = readdirSync(join(upstream, directory)).filter(name => name.endsWith('.json')).sort();
  if (JSON.stringify(names) !== JSON.stringify(pins.vectors.map(row => row.file).sort())) {
    throw new Error('Unexpected upstream vector inventory: ' + directory);
  }
  for (const row of pins.vectors) {
    const raw = readFileSync(join(upstream, directory, row.file));
    if (raw.length !== row.bytes || digest(raw) !== row.sha256) {
      throw new Error('Upstream copy mismatch: ' + directory + '/' + row.file);
    }
  }
}
for (const doc of pins.sources) {
  const raw = readFileSync(join(upstream, doc.path));
  if (raw.length !== doc.bytes || digest(raw) !== doc.sha256) throw new Error('Source document changed: ' + doc.path);
}
if (git(['rev-parse', 'HEAD']) !== headBefore || git(['status', '--porcelain'])) {
  throw new Error('Upstream identity changed during collection');
}
console.log(JSON.stringify({
  status: 'PASS', repository: pins.repository, initial_head: headBefore,
  final_head: git(['rev-parse', 'HEAD']), vectors: local.length, byte_identical_copies: 3,
  copies: ['vendored', 'upstream tests/vectors', 'upstream src/attenu_guard/vectors'],
  distribution_wheel_checked: false, upstream_runtime_executed: false,
}));

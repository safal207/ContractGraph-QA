// SPDX-License-Identifier: Apache-2.0
import { readFileSync, readdirSync, lstatSync, writeFileSync } from 'node:fs';
import { relative, resolve, join, sep } from 'node:path';
import { ROOT, digest, jsonBytes } from './run-proof.mjs';

const repository = resolve(ROOT, '../..');
const manifestPath = join(ROOT, 'artifacts.json');
const workflow = '.github/workflows/attenu-delegation-proof.yml';

function inventory(directory) {
  return readdirSync(directory).flatMap(name => {
    const path = join(directory, name);
    if (path === manifestPath) return [];
    const stat = lstatSync(path);
    if (stat.isSymbolicLink()) throw new Error('Symlink in proof artifacts');
    if (stat.isDirectory()) return inventory(path);
    if (!stat.isFile()) throw new Error('Non-regular proof artifact');
    return [relative(repository, path).split(sep).join('/')];
  }).sort();
}

function currentManifest() {
  return {
    schema: 'cgqa.attenu-delegation-artifacts.v1',
    repository: 'safal207/ContractGraph-QA',
    base_sha: 'f861b934d77e64fd35f768e2a33bb4a00963bc19',
    verifier_revision: 'cb080a795f26bd1c0417d32cdd297960511cad88',
    upstream_sha: '419f6584c120736688aa946b9c46cfe1c8124292',
    artifacts: [...inventory(ROOT), workflow].sort().map(path => {
      const raw = readFileSync(join(repository, path));
      return { path, bytes: raw.length, sha256: digest(raw) };
    }),
  };
}

if (process.argv.length > 3 || (process.argv[2] && process.argv[2] !== '--write')) {
  throw new Error('Usage: node check-artifacts.mjs [--write]');
}
const observed = jsonBytes(currentManifest());
if (process.argv[2] === '--write') {
  writeFileSync(manifestPath, observed);
  console.log('Artifact manifest written; anchor this manifest in the review commit.');
} else {
  // Rebuilding from the fixed roots also rejects added or missing files,
  // duplicate entries and traversal paths in the retained manifest.
  if (readFileSync(manifestPath, 'utf8') !== observed) {
    throw new Error('Artifact inventory or bytes differ from committed manifest');
  }
  console.log('PASS: artifact inventory, sizes and SHA-256 digests match.');
}

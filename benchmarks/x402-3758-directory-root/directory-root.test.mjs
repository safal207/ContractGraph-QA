import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { readFileSync, mkdtempSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import {
  FIELDS, canonicalizeFixtureDomain, directoryPreimage, computeDirectoryRoot,
  publishedRootMatches, sha256, computeReceiptId, directorySignedMessage,
  receiptSignedMessage, verifyEd25519,
} from "./verify.mjs";

const base = fileURLToPath(new URL(".", import.meta.url));
const directoryBytes = readFileSync(join(base, "fixtures/directory.json"));
const receiptBytes = readFileSync(join(base, "fixtures/receipt.json"));
const directory = JSON.parse(directoryBytes);
const receipt = JSON.parse(receiptBytes);
const ROOT = "9daec3d9df75826056ba182b0c176e6684b85aab723a59efbd4d75f4c999e538";
const RECEIPT_ID = "77795afae30c36075ed22e6593e28d0b4d7ae24c23acebfdcf8e0c0dc494b5fb";
const clone = value => structuredClone(value);

function flipBase64(text) {
  const bytes = Buffer.from(text, "base64");
  bytes[0] ^= 1;
  return bytes.toString("base64");
}

function reversedMembers(value) {
  if (Array.isArray(value)) return value.map(reversedMembers);
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.keys(value).reverse().map(key => [key, reversedMembers(value[key])]));
  }
  return value;
}

function pythonPreimage(input) {
  const temp = mkdtempSync(join(tmpdir(), "x402-directory-"));
  try {
    const path = join(temp, "directory.json");
    writeFileSync(path, JSON.stringify(input));
    const result = spawnSync(process.env.PYTHON ?? "python3", [join(base, "oracle.py"), path, "--preimage"]);
    assert.equal(result.error, undefined);
    assert.equal(result.status, 0, result.stderr?.toString());
    return result.stdout;
  } finally {
    rmSync(temp, { recursive: true, force: true });
  }
}

test("freeze exact original HTTP bytes before parsing", () => {
  assert.equal(directoryBytes.length, 10563);
  assert.equal(sha256(directoryBytes), "eeb8badd5ad01dd622717651146bed7b9f138e69dd3a3a096268c13ff7217f2f");
  assert.equal(sha256(receiptBytes), "91c153cb2bd6e8789209f896783d669e7c3a4f14230af911a370c380418fb654");
  // Raw canonical whole-document hash is deliberately NOT directory.root.
  assert.equal(canonicalizeFixtureDomain(directory), directoryBytes.toString("utf8"));
  assert.notEqual(sha256(directoryBytes), ROOT);
});

test("seven-field §7.2 projection independently reproduces the production epoch root", () => {
  const preimage = directoryPreimage(directory);
  assert.equal(Buffer.byteLength(preimage), 5906);
  assert.deepEqual(Object.keys(JSON.parse(preimage)).sort(), [...FIELDS].sort());
  assert.equal(sha256(preimage), ROOT);
  assert.equal(directory.root, ROOT);
  assert.equal(publishedRootMatches(directory), true);
});

test("independent guarded Python serialization emits the same 5906 preimage bytes", () => {
  const expected = Buffer.from(directoryPreimage(directory));
  const independentlyEncoded = pythonPreimage(directory);
  assert.deepEqual(independentlyEncoded, expected);
  assert.equal(sha256(independentlyEncoded), ROOT);
});

test("recursive member order and both normative array sorts preserve the root", () => {
  for (const reverseGovernance of [false, true]) {
    for (const reverseKeys of [false, true]) {
      const reordered = reversedMembers(directory);
      if (reverseGovernance) reordered.governanceKeys.reverse();
      if (reverseKeys) reordered.keys.reverse();
      assert.equal(directoryPreimage(reordered), directoryPreimage(directory));
      assert.equal(computeDirectoryRoot(reordered), ROOT);
    }
  }
  const both = reversedMembers(directory);
  both.governanceKeys.reverse();
  both.keys.reverse();
  assert.deepEqual(pythonPreimage(both), Buffer.from(directoryPreimage(directory)));
});

test("repeated computation and rejection preserve input object and fixture bytes", () => {
  const original = clone(directory);
  const bytesBefore = Buffer.from(directoryBytes);
  for (let replay = 0; replay < 3; replay++) {
    assert.equal(computeDirectoryRoot(directory), ROOT);
    assert.deepEqual(directory, original);
  }
  const invalid = clone(directory);
  invalid.keys[0].publicKey = flipBase64(invalid.keys[0].publicKey);
  const invalidBefore = clone(invalid);
  assert.equal(publishedRootMatches(invalid), false);
  assert.deepEqual(invalid, invalidBefore);
  assert.deepEqual(readFileSync(join(base, "fixtures/directory.json")), bytesBefore);
});

const topLevelMutations = {
  spec: dir => { dir.spec += "-changed"; },
  issuer: dir => { dir.issuer = "https://different.example"; },
  epoch: dir => { dir.epoch += 1; },
  prevRoot: dir => { dir.prevRoot = "1" + dir.prevRoot.slice(1); },
  publishedAt: dir => { dir.publishedAt += 1; },
  governanceKeys: dir => { dir.governanceKeys[0].publicKey = flipBase64(dir.governanceKeys[0].publicKey); },
  keys: dir => { dir.keys[0].publicKey = flipBase64(dir.keys[0].publicKey); },
};
for (const [field, mutate] of Object.entries(topLevelMutations)) {
  test(`negative control: changed committed ${field} is rejected against unchanged published root`, () => {
    const changed = clone(directory);
    mutate(changed);
    assert.notEqual(computeDirectoryRoot(changed), ROOT);
    assert.equal(publishedRootMatches(changed), false);
    // The independent oracle also agrees on this changed preimage.
    assert.deepEqual(pythonPreimage(changed), Buffer.from(directoryPreimage(changed)));
  });
}

test("every nested key and governance field participates in the commitment", async t => {
  const mutations = {
    alg: value => value + "-changed",
    kid: value => value + "-changed",
    publicKey: flipBase64,
    use: value => value + "-changed",
    status: value => value === "active" ? "revoked" : "active",
    notBefore: value => value === null ? 0 : value + 1,
    notAfter: value => value === null ? 1791654463 : value + 1,
    revokedAt: value => value === null ? 1791654463 : value + 1,
  };
  for (const collection of ["governanceKeys", "keys"]) {
    for (let index = 0; index < directory[collection].length; index++) {
      for (const field of Object.keys(directory[collection][index])) {
        await t.test(`${collection}[${index}].${field}`, () => {
          const changed = clone(directory);
          changed[collection][index][field] = mutations[field](changed[collection][index][field]);
          assert.notEqual(computeDirectoryRoot(changed), ROOT);
          assert.equal(publishedRootMatches(changed), false);
        });
      }
    }
  }
});

test("missing committed top-level fields are rejected rather than silently omitted", () => {
  for (const field of FIELDS) {
    const changed = clone(directory);
    delete changed[field];
    assert.throws(() => computeDirectoryRoot(changed), /missing committed field/);
    changed[field] = undefined;
    assert.throws(() => computeDirectoryRoot(changed), TypeError);
  }
});

test("null remains a committed value and is distinct from an absent nested lifecycle field", () => {
  const omitted = clone(directory);
  assert.equal(omitted.keys[0].notAfter, null);
  delete omitted.keys[0].notAfter;
  assert.notEqual(directoryPreimage(omitted), directoryPreimage(directory));
  assert.equal(publishedRootMatches(omitted), false);
  const topNull = clone(directory);
  topNull.issuer = null;
  assert.notEqual(computeDirectoryRoot(topNull), ROOT);
  // Hashing arbitrary changed contents does not declare a null issuer well-formed.
});

test("five incomplete researcher preimages fail, while exact §7.2 projection succeeds", () => {
  const { signatures, ...withoutSignatures } = directory;
  const alternatives = [
    [withoutSignatures, "8e1a7c87d6cd1bf355b8abdf980cfba00dcfa8b3b7f26f1c4ffc797f6f0682d9"],
    [directory, "eeb8badd5ad01dd622717651146bed7b9f138e69dd3a3a096268c13ff7217f2f"],
    [directory.keys, "35c3b77cba0189961d74694ab5769dc935345ca5ff781b443125c095b77b7e93"],
    [directory.governanceKeys, "f7d6db30c01f3d00617595794dc27a34e4ba3b03832c1ede9222c2f561c1b309"],
    [{ epoch: directory.epoch, keys: directory.keys, governanceKeys: directory.governanceKeys },
      "6cb9ae03d3f459e9ddc4b7f7c642ebc75b907c01e9e4e90405178f1e8572e016"],
  ];
  for (const [input, expectedDigest] of alternatives) {
    const digest = sha256(canonicalizeFixtureDomain(input));
    assert.equal(digest, expectedDigest);
    assert.notEqual(digest, ROOT);
  }
  assert.equal(computeDirectoryRoot(directory), ROOT);
});

test("published root and signatures are outside the preimage; equality still rejects a false root", () => {
  const changed = clone(directory);
  changed.root = "0".repeat(64);
  changed.signatures[0].signature = flipBase64(changed.signatures[0].signature);
  assert.equal(computeDirectoryRoot(changed), ROOT);
  assert.equal(publishedRootMatches(changed), false);
  delete changed.root;
  delete changed.signatures;
  assert.equal(computeDirectoryRoot(changed), ROOT);
  assert.equal(publishedRootMatches(changed), false);
});

test("directory Ed25519 verifies over recomputed root and rejects changed message/signature", () => {
  const key = directory.governanceKeys.find(key => key.alg === "ed25519");
  const sig = directory.signatures.find(sig => sig.alg === "ed25519");
  const message = directorySignedMessage(computeDirectoryRoot(directory));
  assert.equal(verifyEd25519(key.publicKey, message, sig.signature), true);
  const changedMessage = Buffer.from(message);
  changedMessage[0] ^= 1;
  assert.equal(verifyEd25519(key.publicKey, changedMessage, sig.signature), false);
  assert.equal(verifyEd25519(key.publicKey, message, flipBase64(sig.signature)), false);
  const changed = clone(directory);
  changed.signatures.find(sig => sig.alg === "ed25519").signature = flipBase64(sig.signature);
  assert.equal(publishedRootMatches(changed), true);
  assert.equal(verifyEd25519(key.publicKey, message, changed.signatures.find(sig => sig.alg === "ed25519").signature), false);
});

test("receiptId recomputes and directory digest resolves to the independently recomputed root", () => {
  assert.equal(computeReceiptId(receipt), RECEIPT_ID);
  assert.equal(receipt.payload.keyDirectoryDigest, computeDirectoryRoot(directory));
  assert.equal(receipt.payload.keyDirectoryEpoch, directory.epoch);
});

test("receipt Ed25519 verifies and rejects a one-bit message and signature change", () => {
  const sig = receipt.signatures.find(sig => sig.alg === "ed25519");
  const key = directory.keys.find(key => key.kid === sig.kid && key.alg === sig.alg);
  assert.ok(key);
  const message = receiptSignedMessage(computeReceiptId(receipt));
  assert.equal(verifyEd25519(key.publicKey, message, sig.signature), true);
  const changedMessage = Buffer.from(message);
  changedMessage[0] ^= 1;
  assert.equal(verifyEd25519(key.publicKey, changedMessage, sig.signature), false);
  assert.equal(verifyEd25519(key.publicKey, message, flipBase64(sig.signature)), false);
});

test("fixture serializer rejects values outside its declared domain", () => {
  const sparse = [];
  sparse.length = 1;
  for (const value of [1.5, -0, NaN, Infinity, 2 ** 53, undefined, 1n, () => {}, new Date(), sparse,
    "\u00e9", "\ud800", { "\u00e9": 1 }, { omitted: undefined }]) {
    assert.throws(() => canonicalizeFixtureDomain(value), TypeError);
  }
  assert.equal(canonicalizeFixtureDomain({ x: Number.MAX_SAFE_INTEGER, y: Number.MIN_SAFE_INTEGER, n: null }),
    '{"n":null,"x":9007199254740991,"y":-9007199254740991}');
});

test("guarded Python oracle rejects duplicate members, non-ASCII, unsafe/float/-0 and a false published root", () => {
  const temp = mkdtempSync(join(tmpdir(), "x402-oracle-guard-"));
  try {
    for (const raw of ['{"spec":"a","spec":"b"}',
      JSON.stringify({ ...directory, issuer: "https://different.example/\u00e9" }),
      directoryBytes.toString().replace('"epoch":1', '"epoch":9007199254740992'),
      directoryBytes.toString().replace('"epoch":1', '"epoch":1.5'),
      directoryBytes.toString().replace('"epoch":1', '"epoch":-0')]) {
      const path = join(temp, "changed.json");
      writeFileSync(path, raw);
      const result = spawnSync(process.env.PYTHON ?? "python3", [join(base, "oracle.py"), path, "--preimage"]);
      assert.notEqual(result.status, 0);
    }
    const path = join(temp, "false-root.json");
    writeFileSync(path, JSON.stringify({ ...directory, root: "0".repeat(64) }));
    const result = spawnSync(process.env.PYTHON ?? "python3", [join(base, "oracle.py"), path]);
    assert.equal(result.status, 1);
    assert.equal(JSON.parse(result.stdout).equal, false);
  } finally {
    rmSync(temp, { recursive: true, force: true });
  }
});

test("explicit evidence boundary: ML-DSA fields present, cryptographic verification NOT_RUN", () => {
  assert.ok(directory.governanceKeys.some(key => key.alg === "ml-dsa-65"));
  assert.ok(receipt.signatures.some(sig => sig.alg === "ml-dsa-65"));
  // Presence and root commitment do not authenticate this second signature.
  // This suite has no ML-DSA engine, trust oracle, Polygon RPC or delivered body.
});

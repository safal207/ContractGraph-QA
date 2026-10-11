/**
 * Independent §7.2 commitment experiment on a constrained fixture domain.
 * Not a receipt/directory protocol validator or a general RFC 8785 library.
 */
import { createHash, createPublicKey, verify as verifySignature } from "node:crypto";

export const FIELDS = Object.freeze([
  "spec", "issuer", "epoch", "prevRoot", "publishedAt", "governanceKeys", "keys",
]);

function ascii(value) {
  if (!/^[\x00-\x7f]*$/.test(value)) {
    throw new TypeError("fixture domain requires ASCII strings and member names");
  }
  return JSON.stringify(value);
}

// ASCII ordering is identical for UTF-16 (RFC 8785) and Python code points.
// All safe integers are below 1e21, so ECMAScript emits decimal notation.
export function canonicalizeFixtureDomain(value) {
  if (value === null) return "null";
  if (typeof value === "string") return ascii(value);
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "number") {
    if (!Number.isSafeInteger(value) || Object.is(value, -0)) {
      throw new TypeError("fixture domain requires safe integers, excluding negative zero");
    }
    return String(value);
  }
  if (Array.isArray(value)) {
    // Array.map silently skips holes; explicitly exclude those inputs.
    for (let i = 0; i < value.length; i++) {
      if (!Object.hasOwn(value, i)) throw new TypeError("sparse arrays are outside fixture domain");
    }
    return `[${value.map(canonicalizeFixtureDomain).join(",")}]`;
  }
  if (value && Object.getPrototypeOf(value) === Object.prototype) {
    return `{${Object.keys(value).sort().map(key =>
      `${ascii(key)}:${canonicalizeFixtureDomain(value[key])}`,
    ).join(",")}}`;
  }
  throw new TypeError("value is outside the fixture canonicalization domain");
}

function sortedBy(list, field) {
  if (!Array.isArray(list)) throw new TypeError(`${field} list must be an array`);
  for (const entry of list) {
    if (!entry || typeof entry[field] !== "string") {
      throw new TypeError(`sorting requires string ${field}`);
    }
  }
  // Copies both arrays; input order and nested objects are not modified.
  return [...list].sort((a, b) => a[field] < b[field] ? -1 : a[field] > b[field] ? 1 : 0);
}

export function projectDirectory(directory) {
  for (const field of FIELDS) {
    if (!Object.hasOwn(directory, field)) throw new TypeError(`missing committed field: ${field}`);
  }
  const projection = Object.fromEntries(FIELDS.map(field => [field, directory[field]]));
  projection.governanceKeys = sortedBy(directory.governanceKeys, "alg");
  projection.keys = sortedBy(directory.keys, "kid");
  return projection;
}

export function sha256(data) {
  return createHash("sha256").update(data).digest("hex");
}

export function directoryPreimage(directory) {
  return canonicalizeFixtureDomain(projectDirectory(directory));
}

export function computeDirectoryRoot(directory) {
  return sha256(directoryPreimage(directory));
}

export function publishedRootMatches(directory) {
  return computeDirectoryRoot(directory) === directory.root;
}

export function computeReceiptId(receipt) {
  return sha256(canonicalizeFixtureDomain(receipt.payload));
}

export function directorySignedMessage(root) {
  return Buffer.from(`x402-receipt-key-directory/1\n${root}`, "utf8");
}

export function receiptSignedMessage(receiptId) {
  return Buffer.from(`x402-delivery-receipt/1\n${receiptId}`, "utf8");
}

function canonicalBase64(text) {
  if (typeof text !== "string") throw new TypeError("expected base64 string");
  const bytes = Buffer.from(text, "base64");
  if (bytes.toString("base64") !== text) throw new TypeError("noncanonical base64");
  return bytes;
}

export function verifyEd25519(publicKeyB64, message, signatureB64) {
  const raw = canonicalBase64(publicKeyB64);
  const signature = canonicalBase64(signatureB64);
  if (raw.length !== 32 || signature.length !== 64) return false;
  // RFC 8410 SubjectPublicKeyInfo prefix for Ed25519 raw 32-byte public key.
  const key = createPublicKey({
    key: Buffer.concat([Buffer.from("302a300506032b6570032100", "hex"), raw]),
    format: "der",
    type: "spki",
  });
  return verifySignature(null, message, key, signature);
}

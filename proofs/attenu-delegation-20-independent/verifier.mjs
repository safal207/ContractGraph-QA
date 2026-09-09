// SPDX-License-Identifier: Apache-2.0
// Independent offline verifier for the declared Attenu Delegation Token corpus profile.
// This module receives no fixture names, descriptions, expectations, or filesystem paths.
import { createHash, createHmac, timingSafeEqual } from 'node:crypto';

export class VerificationError extends Error {
  constructor(reason, detail) {
    super(detail);
    this.name = 'VerificationError';
    this.reason = reason;
  }
}

function requireThat(condition, reason, detail) {
  if (!condition) throw new VerificationError(reason, detail);
}

const own = (value, key) => Object.hasOwn(value, key);
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const numeric = value => typeof value === 'number' && Number.isFinite(value);
const positiveInteger = value => Number.isSafeInteger(value) && value > 0;

function validUnicode(value) {
  for (let i = 0; i < value.length; i += 1) {
    const unit = value.charCodeAt(i);
    if (unit >= 0xd800 && unit <= 0xdbff) {
      const next = value.charCodeAt(++i);
      requireThat(next >= 0xdc00 && next <= 0xdfff, 'malformed', 'lone high surrogate');
    } else {
      requireThat(!(unit >= 0xdc00 && unit <= 0xdfff), 'malformed', 'lone low surrogate');
    }
  }
}

// JSON.parse alone discards duplicate names. This small JSON grammar preserves
// that check, validates numeric input before rounding, and delegates string
// unescaping to the runtime. Objects have no prototype.
export function parseJson(text) {
  requireThat(typeof text === 'string', 'malformed', 'JSON must be text');
  let at = 0;
  function whitespace() {
    while (at < text.length && /[ \t\r\n]/.test(text[at])) at += 1;
  }
  function string() {
    const match = /^"(?:[^"\\\u0000-\u001f]|\\(?:["\\/bfnrt]|u[0-9a-fA-F]{4}))*"/.exec(text.slice(at));
    requireThat(match !== null, 'malformed', 'invalid JSON string');
    at += match[0].length;
    const result = JSON.parse(match[0]);
    validUnicode(result);
    return result;
  }
  function value(depth) {
    requireThat(depth <= 128, 'unsupported_profile', 'JSON nesting exceeds local bound');
    whitespace();
    const first = text[at];
    if (first === '"') return string();
    if (first === '{') {
      at += 1;
      whitespace();
      const result = Object.create(null);
      if (text[at] === '}') { at += 1; return result; }
      while (true) {
        whitespace();
        const key = string();
        requireThat(!own(result, key), 'duplicate_member', 'duplicate JSON object member');
        whitespace();
        requireThat(text[at++] === ':', 'malformed', 'missing member colon');
        result[key] = value(depth + 1);
        whitespace();
        const delimiter = text[at++];
        if (delimiter === '}') return result;
        requireThat(delimiter === ',', 'malformed', 'invalid object delimiter');
      }
    }
    if (first === '[') {
      at += 1;
      whitespace();
      const result = [];
      if (text[at] === ']') { at += 1; return result; }
      while (true) {
        result.push(value(depth + 1));
        whitespace();
        const delimiter = text[at++];
        if (delimiter === ']') return result;
        requireThat(delimiter === ',', 'malformed', 'invalid array delimiter');
      }
    }
    for (const [word, result] of [['true', true], ['false', false], ['null', null]]) {
      if (text.startsWith(word, at)) { at += word.length; return result; }
    }
    requireThat(!/^(?:NaN|-?Infinity)/.test(text.slice(at)), 'non_finite', 'non-finite number');
    const match = /^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?/.exec(text.slice(at));
    requireThat(match !== null, 'malformed', 'invalid JSON value');
    at += match[0].length;
    const number = Number(match[0]);
    requireThat(Number.isFinite(number), 'non_finite', 'non-finite number');
    // Corpus restriction, not the entire binary64 number domain of RFC 8785.
    requireThat(!Number.isInteger(number) || Number.isSafeInteger(number),
      'malformed', 'integer outside corpus safe range');
    return number;
  }
  const result = value(0);
  whitespace();
  requireThat(at === text.length, 'malformed', 'trailing JSON data');
  return result;
}

// ECMAScript JSON serialization supplies RFC 8785 number/string spelling;
// default JS string sort supplies UTF-16 code-unit key ordering. Emit members
// directly so JS's integer-like property enumeration cannot undo that order.
export function canonicalize(value) {
  if (value === null) return 'null';
  if (typeof value === 'string') { validUnicode(value); return JSON.stringify(value); }
  if (typeof value === 'boolean') return JSON.stringify(value);
  if (typeof value === 'number') {
    requireThat(Number.isFinite(value), 'non_finite', 'non-finite number');
    requireThat(!Number.isInteger(value) || Number.isSafeInteger(value),
      'malformed', 'integer outside corpus safe range');
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) return '[' + value.map(canonicalize).join(',') + ']';
  requireThat(object(value), 'malformed', 'unsupported JSON value');
  return '{' + Object.keys(value).sort().map(key =>
    canonicalize(key) + ':' + canonicalize(value[key])).join(',') + '}';
}

function decode64(part) {
  requireThat(typeof part === 'string' && /^[A-Za-z0-9_-]+$/.test(part),
    'malformed', 'invalid unpadded base64url');
  const raw = Buffer.from(part, 'base64url');
  requireThat(raw.toString('base64url') === part, 'malformed', 'noncanonical base64url');
  return raw;
}

function decodeObject(part) {
  const raw = decode64(part);
  let text;
  try { text = new TextDecoder('utf-8', { fatal: true, ignoreBOM: true }).decode(raw); }
  catch { throw new VerificationError('malformed', 'invalid UTF-8'); }
  const value = parseJson(text);
  requireThat(object(value), 'malformed', 'JWT JSON component must be an object');
  requireThat(raw.equals(Buffer.from(canonicalize(value), 'utf8')),
    'non_canonical', 'received JWT JSON component is not JCS');
  return value;
}

export function scopeCovers(parent, child) {
  return parent === child || (parent.endsWith('.*') && child.startsWith(parent.slice(0, -1)));
}

const segment = '[a-z][a-z0-9_-]*';
const scopePattern = new RegExp('^' + segment + '(?:\\.' + segment + ')*\\.(?:' + segment + '|\\*)$');
const constraintKinds = new Set(['max', 'min', 'one_of', 'not_one_of', 'prefix', 'rank']);
const egressOrder = ['none', 'internal', 'any'];

function authority(claims) {
  const details = claims.authorization_details;
  requireThat(Array.isArray(details) && details.length === 1 && object(details[0]),
    'unsupported_profile', 'requires one authorization detail');
  const detail = details[0];
  requireThat(detail.type === 'agent_delegation', 'unsupported_profile', 'unknown authorization detail');
  requireThat(Array.isArray(detail.scopes) && detail.scopes.every(scope =>
    typeof scope === 'string' && scopePattern.test(scope)), 'malformed', 'invalid scope syntax');
  const rows = own(detail, 'constraints') ? detail.constraints : [];
  requireThat(Array.isArray(rows), 'malformed', 'constraints must be an array');
  const constraints = new Map();
  for (const row of rows) {
    requireThat(object(row) && typeof row.key === 'string' && row.key.length > 0,
      'malformed', 'constraint key must be a nonempty string');
    const fields = Object.keys(row).filter(key => key !== 'key');
    requireThat(fields.length === 1 && constraintKinds.has(fields[0]),
      'unsupported_profile', 'unknown or ambiguous constraint kind');
    requireThat(!constraints.has(row.key), 'unsupported_profile', 'ambiguous constraint dimension');
    const kind = fields[0];
    const val = row[kind];
    if (kind === 'max' || kind === 'min') {
      requireThat(numeric(val), 'malformed', 'numeric constraint required');
    } else if (kind === 'one_of' || kind === 'not_one_of') {
      requireThat(Array.isArray(val), 'malformed', 'constraint array required');
    } else if (kind === 'prefix') {
      requireThat(typeof val === 'string', 'malformed', 'prefix string required');
    } else {
      requireThat(row.key === 'egress' && egressOrder.includes(val),
        'unsupported_profile', 'rank order not defined by this corpus profile');
    }
    constraints.set(row.key, { kind, value: val });
  }
  return { scopes: detail.scopes, constraints };
}

const subset = (child, parent) => {
  const allowed = new Set(parent.map(canonicalize));
  return child.every(value => allowed.has(canonicalize(value)));
};

export function constraintNarrows(parent, child) {
  if (parent.kind !== child.kind) return false;
  const p = parent.value;
  const c = child.value;
  switch (parent.kind) {
    case 'max': return c <= p;
    case 'min': return c >= p;
    case 'one_of': return subset(c, p);
    case 'not_one_of': return subset(p, c);
    case 'prefix': return c.startsWith(p);
    case 'rank': return egressOrder.indexOf(c) <= egressOrder.indexOf(p);
    default: return false;
  }
}

function validateClaims(claims) {
  for (const name of ['iss', 'sub', 'jti']) {
    requireThat(typeof claims[name] === 'string' && claims[name].length > 0,
      'malformed', 'missing string claim ' + name);
  }
  requireThat(own(claims, 'aud'), 'malformed', 'missing audience claim');
  // null audience is a declared corpus exception; no audience policy is claimed.
  requireThat(numeric(claims.iat) && numeric(claims.exp), 'malformed', 'invalid NumericDate');
  if (own(claims, 'nbf')) requireThat(numeric(claims.nbf), 'malformed', 'invalid nbf');
}

export function verifyChain(tokens, signer, now) {
  const completed = [];
  let stage = 'input';
  let tokenIndex = null;
  try {
    requireThat(Array.isArray(tokens) && tokens.length > 0, 'malformed', 'nonempty chain required');
    requireThat(numeric(now), 'malformed', 'explicit finite clock required');
    requireThat(object(signer) && signer.alg === 'HS256' && typeof signer.kid === 'string' &&
      typeof signer.secret_hex === 'string' && /^(?:[0-9a-fA-F]{2})+$/.test(signer.secret_hex),
    'unsupported_profile', 'requires the external HS256 test signer');
    const key = Buffer.from(signer.secret_hex, 'hex');
    stage = 'json_jcs';
    const decoded = tokens.map((token, i) => {
      tokenIndex = i;
      requireThat(typeof token === 'string', 'malformed', 'compact JWS string required');
      const parts = token.split('.');
      requireThat(parts.length === 3, 'malformed', 'compact JWS must have three parts');
      const header = decodeObject(parts[0]);
      const claims = decodeObject(parts[1]);
      return { header, claims, signingInput: parts[0] + '.' + parts[1], signature: decode64(parts[2]) };
    });
    completed.push('json_jcs');

    stage = '1_signature';
    for (const [i, token] of decoded.entries()) {
      tokenIndex = i;
      requireThat(token.header.alg === signer.alg && token.header.kid === signer.kid,
        'signature_invalid', 'algorithm or key identifier does not match the trusted test signer');
      requireThat(['at+jwt', 'application/at+jwt'].includes(token.header.typ),
        'malformed', 'unexpected JWT type');
      const expected = createHmac('sha256', key).update(token.signingInput, 'ascii').digest();
      requireThat(expected.length === token.signature.length && timingSafeEqual(expected, token.signature),
        'signature_invalid', 'JWS signature does not verify');
    }
    completed.push(stage);

    stage = '2_parent_commitment';
    tokenIndex = 0;
    requireThat(!own(decoded[0].claims, 'par_hash'), 'malformed', 'root must not have par_hash');
    for (let i = 1; i < decoded.length; i += 1) {
      tokenIndex = i;
      const expected = createHash('sha256').update(decoded[i - 1].signingInput, 'ascii').digest();
      const actual = decode64(decoded[i].claims.par_hash);
      requireThat(expected.length === actual.length && timingSafeEqual(expected, actual),
        'par_hash_mismatch', 'parent Signing Input commitment differs');
    }
    completed.push(stage);

    stage = '3_depth';
    tokenIndex = 0;
    const rootLimit = decoded[0].claims.del_max_depth;
    requireThat(positiveInteger(rootLimit) && decoded.length - 1 < rootLimit,
      'depth_invalid', 'root chain-length bound exceeded or invalid');
    for (const [i, token] of decoded.entries()) {
      tokenIndex = i;
      requireThat(Number.isSafeInteger(token.claims.del_depth) && token.claims.del_depth === i,
        'depth_invalid', 'token depth does not match its root-first position');
    }
    completed.push(stage);

    stage = '4_authority';
    let previousAuthority;
    let depthLimit = rootLimit;
    for (const [i, token] of decoded.entries()) {
      tokenIndex = i;
      const claims = token.claims;
      validateClaims(claims);
      const current = authority(claims);
      if (i > 0) {
        requireThat(current.scopes.every(child => previousAuthority.scopes.some(parent =>
          scopeCovers(parent, child))), 'not_narrower', 'child scope is not covered by parent');
        for (const [dimension, parent] of previousAuthority.constraints) {
          requireThat(current.constraints.has(dimension) &&
            constraintNarrows(parent, current.constraints.get(dimension)),
          'not_narrower', 'parent constraint was omitted, changed kind or loosened');
        }
        requireThat(claims.exp <= decoded[i - 1].claims.exp,
          'expired', 'absolute expiry increases from parent');
        if (own(claims, 'del_max_depth')) {
          requireThat(positiveInteger(claims.del_max_depth) && claims.del_max_depth <= depthLimit,
            'not_narrower', 'child increases or invalidates depth limit');
          depthLimit = claims.del_max_depth;
        }
      }
      previousAuthority = current;
    }
    completed.push(stage);

    stage = '5_time';
    for (const [i, token] of decoded.entries()) {
      tokenIndex = i;
      const claims = token.claims;
      requireThat(now <= claims.exp && (!own(claims, 'nbf') || claims.nbf <= now),
        'expired', 'time outside inclusive nbf/expiry interval');
    }
    completed.push(stage);
    return { accepted: true, reason: null, stage: null, token_index: null, completed };
  } catch (error) {
    if (!(error instanceof VerificationError)) throw error;
    return { accepted: false, reason: error.reason, stage, token_index: tokenIndex,
      detail: error.message, completed };
  }
}

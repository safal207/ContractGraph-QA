# ContractGraph-QA Pilot Offer

## Smart Contract QA / Audit-Readiness Pilot

**Price:** $200 fixed  
**Scope:** one small authorized contract or one narrowly defined contract feature / state machine  
**Goal:** produce reproducible evidence on the highest-value business/security invariants before a larger QA or audit-readiness engagement.

## Included

- scope review and explicit authorization boundary;
- action / actor / state-transition model;
- up to **5 prioritized invariants**;
- Foundry-based bounded state exploration using ContractGraph-QA;
- shortest reproducible path for each discovered violation;
- classification of every declared invariant as:
  - `violated`;
  - `not_found_within_bound`;
  - `inconclusive`;
- finding JSON + client-readable Markdown for violations;
- engagement coverage summary;
- deterministic evidence ZIP;
- independent bundle verification command;
- **one retest pass** for fixes delivered within the pilot scope.

## Good pilot targets

- escrow / release / refund logic;
- role and access-control transitions;
- deposit / withdrawal accounting;
- deadline and timelock behavior;
- terminal-state exclusivity;
- caps, limits, and state-dependent business rules;
- contract/frontend/backend integration assumptions that can be expressed as contract-state invariants.

## Not included

This pilot is **not sold as a formal full-protocol security audit** and does not promise exhaustive vulnerability discovery.

Unless separately agreed, it excludes:

- whole-protocol audit coverage;
- cryptographic design review;
- economic/game-theoretic attack modeling;
- production exploitation;
- unauthorized testing of public contracts;
- private-key or wallet custody;
- unlimited retesting or open-ended consulting.

## What the client sends

- repository / source for the authorized target;
- exact contract or feature in scope;
- written authorization or clearly applicable bounty/safe-harbor reference when testing is not purely repository-local;
- expected roles and business rules;
- the 3–5 properties whose failure would matter most, if already known.

## Deliverable shape

```text
scope
  ↓
state/action/invariant model
  ↓
bounded search
  ↓
minimal path evidence
  ↓
findings + coverage
  ↓
verified evidence bundle
  ↓
retest
```

A clean bounded result is described as **`not_found_within_bound`**, never as a blanket claim that the contract is secure.

## Expansion path

If the pilot is useful, the next engagement can expand into:

1. broader invariant coverage;
2. parameter/time corpus expansion;
3. authorized fixed-block fork testing;
4. integration QA;
5. regression suite hardening;
6. audit-readiness gap review.

## Positioning

ContractGraph-QA is a **Smart Contract QA and verification layer** focused on stateful behavior, invariant evidence, reproducibility, and retest. It can complement a security audit; it does not impersonate one.

# Security policy

ContractGraph-QA is intended for defensive smart-contract quality assurance and security testing.

## Authorized use

Use the project only on:

- contracts you own;
- open-source contracts used as local test fixtures;
- systems for which you have explicit authorization;
- public bug-bounty programs strictly within their published scope and rules.

Do not use this repository to target third-party production systems without permission. A public contract address or publicly readable chain state is not, by itself, authorization to perform active security testing.

## Fork testing

Fork-based testing must use a fixed snapshot and explicit scope evidence. The `Authorized fork smoke` workflow requires a scope identifier, authorization reference, exact chain/block/target, an affirmative authorization confirmation, and a secret RPC endpoint before opening the fork.

The v0.6 smoke test is read-only: it does not call target functions or broadcast transactions. Client-specific active fork scenarios must remain within the written authorization or published bounty scope.

Never commit RPC credentials, private keys, seed phrases, signing material, or client secrets. Authorization references supplied as workflow inputs should be non-sensitive because workflow metadata and logs may be visible to repository collaborators or the public.

## Reporting a vulnerability in this repository

Please open a GitHub issue for non-sensitive defects.

For a sensitive vulnerability, use GitHub private vulnerability reporting from this repository's **Security** tab (`Report a vulnerability`) when that option is available. Do not open a public issue containing exploit details, private keys, secrets, or reproduction steps that could put users at risk.

If private vulnerability reporting is unavailable, open a non-sensitive issue asking the maintainer to provide a private contact channel, without including vulnerability details. Give the maintainer a reasonable opportunity to assess and fix the issue before public disclosure.

## Demo vulnerabilities

Files explicitly named `Vulnerable*` are intentionally insecure local fixtures. They exist to demonstrate invariant detection and must not be deployed.

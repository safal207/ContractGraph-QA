# Security policy

ContractGraph-QA is intended for defensive smart-contract quality assurance and security testing.

## Authorized use

Use the project only on:

- contracts you own;
- open-source contracts used as local test fixtures;
- systems for which you have explicit authorization;
- public bug-bounty programs strictly within their published scope and rules.

Do not use this repository to target third-party production systems without permission.

## Reporting a vulnerability in this repository

Please open a GitHub issue for non-sensitive defects.

For a sensitive vulnerability, use GitHub private vulnerability reporting from this repository's **Security** tab (`Report a vulnerability`) when that option is available. Do not open a public issue containing exploit details, private keys, secrets, or reproduction steps that could put users at risk.

If private vulnerability reporting is unavailable, open a non-sensitive issue asking the maintainer to provide a private contact channel, without including vulnerability details. Give the maintainer a reasonable opportunity to assess and fix the issue before public disclosure.

## Demo vulnerabilities

Files explicitly named `Vulnerable*` are intentionally insecure local fixtures. They exist to demonstrate invariant detection and must not be deployed.

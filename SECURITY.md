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

Please open a GitHub issue for non-sensitive defects. For a vulnerability that could create risk for users, avoid publishing exploit details until a maintainer has had a reasonable opportunity to assess and fix it.

## Demo vulnerabilities

Files explicitly named `Vulnerable*` are intentionally insecure local fixtures. They exist to demonstrate invariant detection and must not be deployed.

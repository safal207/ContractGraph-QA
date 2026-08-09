# Web3 Outreach — Wave 2

Status: outreach only. No testing is authorized by public source availability.

Commercial offer: **Smart Contract QA / Audit-Readiness Pilot — $200 fixed**

Safety boundary for every prospect:

- written authorization before target-specific execution;
- repository-local / local Foundry / explicitly approved test environment only;
- no mainnet or public-testnet transactions;
- no real wallets, private keys, or real funds;
- no production exploitation;
- evidence-driven state/invariant QA, not a claim of formal audit certification.

## 1. Puffer Finance

Public contact: `contact@puffer.fi`

Public repo: `PufferFinance/puffer-contracts`

Narrow pilot angle:

- one PufferVault deposit / redeem / withdrawal lifecycle;
- ERC-4626 accounting invariants;
- terminal-state and revert atomicity;
- residual balance / state consistency.

## 2. CoW Protocol

Public contact: `info@cow.fi`

Public repo: `cowprotocol/contracts`

Narrow pilot angle:

- one settlement lifecycle in a local fixture;
- order / settlement state consistency;
- invalid transition rejection;
- accounting conservation;
- revert atomicity and residual state.

## 3. Morpho

Public contact: `contact@morpho.org`

Public repo candidate: `morpho-org/metamorpho` (or another exact repo chosen by the team)

Narrow pilot angle:

- one vault role / timelock state machine;
- pending → accepted / revoked transitions;
- role authorization;
- queue / cap state consistency;
- bounded local Foundry evidence.

## 4. Gearbox Protocol

Public contact: `hello@gearbox.foundation`

Public repo candidate: `Gearbox-protocol/core-v3`

Narrow pilot angle:

- one credit-account / permission state path chosen by the team;
- role and state-transition invariants;
- invalid sequence rejection;
- accounting / cleanup after revert.

## 5. Superfluid

Public contact: `hello@suplabs.org` (publicly listed on the historical Superfluid Labs GitHub org profile)

Current public protocol repo: `superfluid-org/protocol-monorepo`

Narrow pilot angle:

- one streaming lifecycle;
- create / update / stop / settle state transitions;
- time-dependent accounting;
- duplicate / invalid transition rejection;
- local-only evidence.

## Outreach copy pattern

> Hi team,
>
> I’m an independent QA engineer building ContractGraph-QA, a small state/invariant testing layer for Solidity systems.
>
> I’m offering a narrowly scoped **$200 fixed Smart Contract QA / Audit-Readiness Pilot** for one authorized contract or state machine. The work is local/test-only and focuses on state transitions, accounting invariants, temporal/role boundaries, shortest reproducible violation paths, and one retest.
>
> No production access, no mainnet transactions, no real funds, and no claim of replacing a formal audit.
>
> If useful, I can start with one small workflow your team selects.
>
> Best,
> Aleksey Safonov
> https://github.com/safal207/ContractGraph-QA

## Funnel target

`5 wave-2 outreaches → 1–2 replies → 1 call → 1 paid pilot → $750+ expansion`

# Web3 Outreach — Wave 1

Status: **READY TO CONTACT — OUTREACH ONLY**

Purpose: sell the existing `$200 fixed` Smart Contract QA / Audit-Readiness Pilot without performing any third-party testing before written authorization.

## 1. Magna

Target repo: https://github.com/magna-eng/wentokens

Verified public engineering contact from the GitHub organization profile: `eng@magna.so`

Website: https://magna.so

Subject: `Small local-only QA pilot for wentokens transfer invariants`

Message:

> Hi Magna team,
>
> I’m an independent QA engineer focused on stateful Solidity behavior and reproducible evidence. Your `wentokens` bulk-transfer flow is a very clean fit for a small bounded pilot.
>
> I can validate one authorized local transfer path around conservation, failure atomicity, duplicate-recipient semantics, and residual token/ETH state.
>
> Scope: one small contract/feature, up to 5 invariants, local Foundry only, reproducible evidence bundle + one retest.
>
> **$200 fixed.** No production interaction, real funds, or wallet/private-key access required.
>
> Proof/tooling: https://github.com/safal207/ContractGraph-QA
>
> If useful, I can send a one-page proposed scope before you commit to anything.
>
> Best,
> Aleksey Safonov

## 2. Perfect Abstractions / Compose

Target repo: https://github.com/Perfect-Abstractions/Compose

Verified public contact from the GitHub organization profile: `nick@perfectabstractions.com`

Website: https://compose.diamonds

Subject: `Bounded QA pilot for one Compose Diamond upgrade path`

Message:

> Hi Nick,
>
> I built ContractGraph-QA, a small evidence-driven QA layer for stateful Solidity behavior. Compose’s Diamond upgrade/selector model looks like a strong fit for a narrowly scoped regression pilot.
>
> I can validate one authorized local upgrade path around selector uniqueness/reachability, post-upgrade state preservation, and rejection of invalid transitions.
>
> Scope: one path, up to 5 invariants, local Foundry only, reproducible evidence + one retest.
>
> **$200 fixed.** This is audit-readiness QA, not a claim to replace a full security audit.
>
> Tooling/proof: https://github.com/safal207/ContractGraph-QA
>
> If useful, I can send the exact 3–5 invariants first.
>
> Best,
> Aleksey Safonov

## 3. Peer (previously ZKP2P)

Target repo: https://github.com/zkp2p/zkp2p-contracts

Verified public project route from GitHub organization profile: https://peer.xyz/

No public email was present in the GitHub organization profile when this file was prepared. Use the project’s official contact/community route; do not guess an email address.

Message:

> Hi Peer team — I’m building ContractGraph-QA, a bounded state/invariant QA workflow for Solidity. Your V2 escrow lifecycle is a strong fit for a tiny pilot: one authorized escrow path, 3–5 invariants around actor permissions, release/cancel transitions, terminal-state exclusivity and accounting consistency. Local Foundry only, reproducible evidence + one retest, **$200 fixed**. Happy to send the one-page scope first.

## 4. Whetstone Research / Doppler

Target repo: https://github.com/whetstoneresearch/doppler

Verified public routes from GitHub organization profile:

- website: https://whetstone.cc
- X/Twitter handle: `@whetstonedotcc`

No public email was present in the GitHub organization profile when this file was prepared.

Message:

> Hi Whetstone team — I built ContractGraph-QA for bounded temporal/state invariant QA. I’d like to offer a **$200 fixed** pilot on one authorized Doppler lifecycle component: 3–5 temporal/accounting invariants, local Foundry only, shortest-path evidence and one retest. No production interaction or real funds. I can send the exact proposed scope first.

## 5. Origin Labs / Galileo Protocol

Target repo: https://github.com/originlabs-app/galileo-protocol

Verified website from repository metadata: https://galileoprotocol.io

No public email was present on the linked GitHub profile when this file was prepared. Use the official website contact route; do not guess an email address.

Message:

> Hi Galileo team — I run small smart-contract audit-readiness QA pilots focused on lifecycle/role invariants. For one authorized Galileo product/asset lifecycle I can validate 3–5 state/provenance properties locally and return reproducible evidence + one retest for **$200 fixed**. No production interaction, keys, or real funds required. I can send a one-page scope first.

## Send order

1. Magna — direct engineering email
2. Perfect Abstractions — direct public contact
3. Peer / ZKP2P — official website route
4. Whetstone — official website/community route
5. Galileo — official website route

## Conversion rule

Do not offer to test first and ask permission later.

Correct sequence:

`outreach → interest → written target/scope → authorization → exact source pin → local execution → evidence → report → retest`

If authorization is ambiguous, stop at `HOLD`.

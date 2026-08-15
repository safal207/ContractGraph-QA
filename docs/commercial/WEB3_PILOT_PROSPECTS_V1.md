# Web3 Pilot Prospects v1

Status: **OUTREACH ONLY — NO TARGET TESTING AUTHORIZED**

This shortlist is for commercial outreach for the existing ContractGraph-QA Smart Contract QA / Audit-Readiness Pilot. Public source availability is **not** authorization to test a third-party deployment. No testing should begin until the client gives written scope and an approved local/test environment boundary.

Default offer: **$200 fixed** for one small authorized contract or narrowly defined state machine, up to five prioritized invariants, local Foundry execution, reproducible evidence, and one retest.

## 1. Magna — `magna-eng/wentokens`

Repository: https://github.com/magna-eng/wentokens

Why it fits:
- compact Solidity target;
- bulk ERC-20 / native ETH transfer behavior maps directly to conservation and atomicity invariants;
- repository is actively maintained;
- narrow pilot can be explained without positioning as a full security audit.

Suggested pilot scope after authorization:
- one bulk-transfer path;
- recipient/amount conservation;
- duplicate-recipient semantics;
- failure atomicity;
- residual token / ETH state after success and revert.

Opening line:
> I built a bounded state/invariant QA workflow for smart contracts. I can validate one bulk-transfer path locally for conservation, atomicity, and residual-state invariants for $200 fixed, with reproducible evidence and one retest.

## 2. ZKP2P — `zkp2p/zkp2p-contracts`

Repository: https://github.com/zkp2p/zkp2p-contracts

Why it fits:
- V2 escrow protocol contracts;
- escrow lifecycle is an excellent state-transition target;
- deadlines, release, cancellation, ownership, and accounting are naturally expressible as bounded invariants;
- active Solidity repository.

Suggested pilot scope after authorization:
- one escrow lifecycle only;
- create/fund/release/cancel state transitions;
- actor permissions;
- terminal-state exclusivity;
- no double release / no value-accounting divergence.

Opening line:
> Your escrow lifecycle is a strong fit for state-transition QA. I can model one authorized flow, validate 3–5 critical invariants locally, and deliver shortest-path evidence for $200 fixed.

## 3. Origin Labs — `originlabs-app/galileo-protocol`

Repository: https://github.com/originlabs-app/galileo-protocol
Website: https://galileoprotocol.io

Why it fits:
- new, active Solidity project;
- product-traceability workflows usually have explicit lifecycle/role semantics;
- small enough for a bounded pilot rather than an open-ended audit.

Suggested pilot scope after authorization:
- one asset/product lifecycle;
- creation/transfer/update role boundaries;
- terminal or irreversible states;
- provenance/state consistency;
- duplicate or out-of-order state changes.

Opening line:
> I run small audit-readiness QA pilots around contract state machines. For one Galileo lifecycle I can validate 3–5 role/state invariants locally and return reproducible evidence for $200 fixed.

## 4. Perfect Abstractions — `Perfect-Abstractions/Compose`

Repository: https://github.com/Perfect-Abstractions/Compose
Website: https://compose.diamonds

Why it fits:
- Solidity smart-contract library centered on EIP-2535 / EIP-8153 Diamonds;
- upgrade / selector / state-layout behavior is highly stateful;
- good fit for a narrowly scoped regression/invariant pilot.

Suggested pilot scope after authorization:
- one upgrade/diamond-cut path;
- selector uniqueness / reachability;
- post-upgrade state preservation;
- unauthorized transition rejection;
- rollback/replacement semantics, if part of intended behavior.

Opening line:
> I can run a small bounded QA pilot on one Diamond upgrade path: state preservation, selector invariants, and unauthorized transition rejection, locally only, for $200 fixed.

## 5. Whetstone Research — `whetstoneresearch/doppler`

Repository: https://github.com/whetstoneresearch/doppler

Why it fits:
- core contracts for the Doppler Protocol;
- active Solidity codebase;
- launch/market lifecycle behavior is naturally suited to temporal and accounting invariants;
- ContractGraph-QA can add evidence-oriented state-path coverage without claiming full protocol audit coverage.

Suggested pilot scope after authorization:
- one lifecycle component only;
- pre/post activation boundaries;
- terminal-state rules;
- parameter/cap invariants;
- asset/accounting conservation within the selected component.

Opening line:
> I built a state-graph QA layer for Solidity. I can take one authorized Doppler lifecycle component and test 3–5 temporal/accounting invariants locally for $200 fixed, including reproducible evidence and one retest.

## Qualification gate before accepting any pilot

Accept only when all are true:

- client explicitly owns or is authorized to provide the target;
- exact repository/commit/contract is written down;
- execution is local, private test environment, or another environment explicitly approved by the client;
- no real user funds, private keys, or production exploitation;
- one bounded feature/state machine can be named;
- business rules for the invariants are available or can be confirmed by the client.

Otherwise status = `HOLD`.

## Conversion goal

First wave:

1. Magna
2. ZKP2P
3. Origin Labs / Galileo
4. Perfect Abstractions
5. Whetstone Research

Goal: **5 targeted outreaches → 1 call → 1 paid $200 pilot → expand to $750+ engagement if useful.**

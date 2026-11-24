# Foundry escrow surplus invariant — research v0

Spine ID: cgqa-foundry-surplus-v0. Exact base: 38755bb5f056ea6f9a1c5a2b0c52401fb1d70021. Subject: repository-owned src/examples/Escrow.sol, test/EscrowSurplusInvariant.t.sol. Authority: current maintainer request for an isolated experiment; no merge, deployment or external outreach. Decision: DEFER until exact-head CI evidence.

## Discovery and scope

The existing EscrowGraph suite covers funding, release, timing, unauthorized actors and a funding fuzz property. VulnerableEscrowGraph covers double payout. ExecutionBindingInvariant and open recovery/receipt PRs cover other authority and retry boundaries. A targeted review of existing tests, PRs, issues and branch names found no explicit exogenous custody-surplus witness. Code search returned no matches even for common terms; this is not exhaustive historical coverage.

The target records depositedAmount, releasedAmount, refundedAmount and a four-state lifecycle. Release/refund transfer the recorded deposit, not the raw balance. The new test distinguishes those accounting variables from independent EVM balance observations. No production code change.

## Preregistered invariant and transition field

Let P be recorded principal (>0), S be exogenous surplus (>=0), D be the actual recipient balance delta, and C be the final contract balance. For a successful terminal payment in this synthetic scope: D=P, C=S, nonrecipient balance unchanged, exactly one terminal payout recorded, and depositedAmount=P. The existing payoutInvariantHolds alone cannot establish D=P.

State vector: lifecycle, principal, release/refund counters, contract and both actor balances, timestamp relative to refundAfter. Identity is the deployed local contract; authority is buyer only. No fees, external provider, token transfer behavior, persistent network, callbacks on EOA recipients or concurrent transactions are modeled.

Paths:
- Created --fund(P)--> Funded --exogenous balance(P+S)--> Funded.
- At deadline-1: refund by buyer rejected, release by seller rejected; entire snapshot unchanged.
- Release at deadline-1, deadline or deadline+1; refund at deadline or deadline+1. Assert actual receiver delta and custody, counters, and terminal state.
- At deadline+2: repeated and opposite terminal operations rejected with unchanged snapshots.
- Negative control: P=100, S=50, recorded payout=100, actual payout=150, custody=0. The independent oracle must reject despite matching accounting. This is an intentionally wrong synthetic fixture, not a finding against Escrow or a third-party protocol.

The exogenous balance change uses Foundry vm.deal to model a balance already present. It does not exercise a particular forced-transfer mechanism or establish that real surplus can be recovered. Residual custody is intentionally not swept: ownership and disposal of surplus are unspecified. Liveness of surplus is out of scope.

## Reproduction

Use Foundry v1.7.1, solc 0.8.24 (existing foundry.toml), exact PR head:
```bash
git rev-parse HEAD
forge --version
forge fmt --check
forge build --sizes
forge test --match-contract EscrowSurplusInvariantTest --fuzz-seed 0x1234 -vvv
forge test -vvv
```
Existing fuzz bound: 256 runs. Amounts are uint96 principal + 1 and uint96 surplus (including zero), timing modulo 3 and both terminal paths. Each trial executes a multi-step stateful sequence; this is not exhaustive stateful invariant-handler exploration. Negative control is deterministic. CI's standard fuzz seed may vary; preserve the seed if a counterexample occurs.

The current test uses the native target and an independent observed-balance oracle, not a new CGQA model or evidence-bundle adapter. Existing TSSE Foundry adapter requires a separately reviewed observation sidecar and strict receipt; generic Forge logs cannot be treated as a verified TSSE bundle. No such claim is made here. Graph explorer, capture/fork tests, external witness completeness and provider reconciliation are not applicable to this minimal native local experiment or remain separate verification debt. No external RPC, credentials or real money.

## Evidence and promotion gate

Record exact SHA, Forge version, native test count, fuzz bounds and CI outcomes. Until run, expected assertions are not observed evidence. Do not promote or merge based on this note. Independent reproduction and TSSE evidence integration are separate follow-up decisions.

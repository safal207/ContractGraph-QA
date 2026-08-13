# Provider-grounded deterministic evidence pack v0.1

This layer turns the reviewed Crossmint public-contract payment-decision pilot into a self-contained evidence object that another verifier can replay without calling Crossmint.

## Evidence chain

```text
reviewed adapter profile
        ↓
captured provider observations
        ↓
explicit authority evidence
        ↓
provider reconciliation
        ↓
Unified Agent Payment Decision
        ↓
canonical SHA-256 bindings
        ↓
independent local replay
```

The pack preserves the exact adapter, observations, authority payload, and provider-decision result.

## Verification scope

Local verification recomputes every embedded payload digest and re-runs `evaluate_provider_payment_decision`. Replay comparison uses canonical JSON bytes, so JSON values such as `false` and `0` remain distinct.

Without a digest stored separately from the pack, this proves local consistency and catches changes whose embedded digest was not updated. It does not establish provenance of an earlier pack version.

For a stronger integrity check, record the canonical digest printed by the build command separately and pass it back during verification with `--expected-pack-sha256`. This binds verification to that separately supplied digest. It is an integrity check, not an identity signature or provider attestation.

## Determinism

Canonical JSON uses UTF-8, sorted object keys, compact separators, and rejects non-standard NaN values. Equivalent dictionary key ordering therefore produces the same digest.

## Example

Build a pack from repository fixtures:

```bash
python tools/run_provider_decision_evidence.py build \
  --adapter benchmarks/agent-payment-recovery-v0.1/provider-adapters/crossmint-public-contract.v0.1.json \
  --observations benchmarks/agent-payment-recovery-v0.1/provider-adapters/crossmint-observations-get-success.json \
  --authority-status authorized \
  --authority-evidence-ref fixture://authority/crossmint/customer-example \
  --decision-id crossmint-customer-example \
  --output .cgqa/crossmint-provider-evidence.json
```

Verify local consistency:

```bash
python tools/run_provider_decision_evidence.py verify \
  --evidence .cgqa/crossmint-provider-evidence.json
```

Verify against a separately supplied pack digest:

```bash
python tools/run_provider_decision_evidence.py verify \
  --evidence .cgqa/crossmint-provider-evidence.json \
  --expected-pack-sha256 <expected-digest>
```

The verifier performs no provider call. A successful local verification means the embedded decision is reproducible from the embedded reviewed public-contract evidence under the repository's decision logic.

## Trust and claim boundary

This is public-contract replay evidence, not a live Crossmint audit or a statement about production wallet behavior.

It does not use Crossmint credentials, call provider APIs, execute a wallet operation, write to testnet/mainnet, grant financial authority, certify security, make a compliance claim, or imply Crossmint endorsement.

Provider evidence establishes payment state only. Actor spending authority remains a separate explicit evidence input.

# ContractGraph-QA Case-Study Registry

This registry separates repository-owned executable demonstrations from external source-bound investigations.

| Case | Subject type | Current result | Executable evidence | Primary limitation |
|---|---|---|---|---|
| [Ambiguous Payment Recovery](AMBIGUOUS_PAYMENT_RECOVERY.md) | Synthetic repository-owned payment fixture | Bounded recovery behavior demonstrated | Repository-owned fixture and product workflow | Synthetic case, not a third-party production claim |
| [Soroban Dice-Duel Predictable Outcome](STELLAR_DICE_DUEL_PREDICTABLE_RANDOMNESS.md) | External assigned source investigation | `COUNTEREXAMPLE_FOUND / REMEDIATION_BLOCKED` | Source is directly inspectable; harness outcomes are reported but not archived | Native regression, remediation, WASM/CI, and CGQA execution are `NOT_RUN` |

The Soroban case also has a machine-readable record:

```bash
cgqa external-investigation \
  --record scenarios/external-investigation-stellar-dice-duel.json
```

Case-study inclusion is not endorsement, audit certification, reward confirmation, or proof of whole-system security.

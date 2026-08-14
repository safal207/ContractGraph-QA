# Neo Resonance P1-2 — Evidence-Bundle and Replay Manifest v0.1

P1-2 defines the common evidence cargo format for the four components that
participate in the durable/replay handoff:

| Component | Role | Current pinned subject in the fixture |
|---|---|---|
| LiminalDB | durable evidence store | `61b02fc81e0cb5cf1f1ed4658ecff58f683cb728` |
| RINSE | reflection adapter | `3be0d2ceb1440641b141cdb80c82ed118e4186dd` |
| ContractGraph-QA | independent verifier | `fcd5e88655eedd3e4e4d3944bb133a8e2c8b0d8e` |
| LS | state-projection recovery | `fa7e3aba4ff9154856fa7d27c92f702137819ac1` |

The schema is intentionally provider-neutral. It does not replace native
protocols or force runtime changes into the four repositories. It gives the
verification boundary one manifest for the facts a downstream verifier needs:

- exact source revision for every component;
- artifact path, role, byte size, SHA-256, origin, trust domain and
  valid/transaction/collection timestamps;
- closed bundle membership, with no missing, duplicate, symlink or unlisted
  files;
- ordered replay steps referencing only declared artifact IDs;
- explicit `SAME_RESULT` replay expectation and `side_effects_executed=false`;
- advisory-only authority flags, where a proposal never becomes authorization.

## Verification

Run the deterministic verifier from the repository root:

```bash
PYTHONPATH=. python3 tools/evidence_bundle_replay_manifest.py verify \
  --manifest fixtures/p1-2/evidence-bundle-replay-manifest.v0.1.json \
  --root fixtures/p1-2/bundle \
  --checked-subject fcd5e88655eedd3e4e4d3944bb133a8e2c8b0d8e \
  --expected-bundle-subject fcd5e88655eedd3e4e4d3944bb133a8e2c8b0d8e \
  --output /tmp/p1-2-result.json
```

The result is `PASS` only when every declared member is present and unchanged,
every member is listed exactly once, all source revisions match their subject,
and the replay graph is complete and read-only. Tampering, path traversal,
duplicate or unlisted cargo, source drift, unknown replay references and
authority escalation fail closed as `HOLD` with a non-zero process exit.

The workflow subject and the bundle's source subject are recorded separately:
the former binds the verifier code that ran; the latter binds the frozen fixture
being checked. A passing fixture proves byte integrity, membership and replay
references only. It does not prove live runtime integration, production safety,
merge approval, deployment, or security certification.

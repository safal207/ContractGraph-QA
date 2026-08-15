# Neo Resonance P1-3 — Evidence, Authority and Reflection Boundary v0.1

P1-3 makes the separation between evidence, reflection and authority executable.
The target is narrow: a `PASS` from a verifier, a valid evidence bundle, or a
reflection record must not become permission to execute an action merely because
it is well-formed or replayable.

## Three lanes

| Lane | May authorize | Required meaning |
|---|---:|---|
| `evidence` | no | recomputable observation or verification result; `authority_effect=NONE` |
| `reflection` | no | bounded interpretation; `reflection_only=true`, `source_mutated=false` |
| `authority` | only from an explicit authority record | current policy/authority decision, separate from evidence and reflection |

The fixture contains an evidence `PASS`, a reflection record and an explicit
authority `HOLD`. All authority flags are false. The verifier does not execute a
tool, call a provider, consume a credential, mutate a source or perform an
external effect.

## Negative escalation matrix

| Case | Attempted transition | Expected result |
|---|---|---|
| `EVIDENCE_PASS_NOT_AUTHORITY` | evidence → execution | `BLOCK / EVIDENCE_NOT_AUTHORITY` |
| `REFLECTION_PASS_NOT_AUTHORITY` | reflection → execution | `BLOCK / REFLECTION_NOT_AUTHORITY` |
| `PASS_CANNOT_INFER_AUTHORITY` | infer authority from evidence + reflection | `BLOCK / EXPLICIT_AUTHORITY_RECORD_REQUIRED` |
| `AUTHORITY_HOLD_STOPS_EXECUTION` | HOLD → execution | `HOLD / AUTHORITY_REVALIDATION_REQUIRED` |

Each case declares `side_effect_executed=false`. The replay trace is contiguous,
read-only and expected to return `SAME_RESULT`. The result is `PASS` only when
the observed decision and reason match the declared negative contract.

## Verification

```bash
PYTHONPATH=. python3 tools/authority_reflection_boundary.py verify \
  --manifest fixtures/p1-3/authority-reflection-boundary.v0.1.json \
  --root fixtures/p1-3/bundle \
  --checked-subject 6e51cbb176f6d891b758e3026744d1d4c4c5727a \
  --expected-proofpath-subject 4a05ee31d7497979c2505dd55bfef08823302e24 \
  --output /tmp/p1-3-result.json
```

The verifier checks exact source subjects, closed artifact membership, byte
sizes, SHA-256 values, safe paths, record lane semantics, expected case results,
and replay references. Tampered, missing, duplicate, unlisted, path-escaping,
source-drifted, authority-escalating or side-effect-marked input fails closed as
`HOLD` with a non-zero exit code.

The workflow subject is the code that performed verification. The component
subjects in the fixture are the revisions whose bounded records are being
checked. These identities remain separate. A passing boundary fixture proves
the negative separation contract for this synthetic route only; it does not
prove live adapter integration, production safety, merge approval, deployment,
security certification or human approval.

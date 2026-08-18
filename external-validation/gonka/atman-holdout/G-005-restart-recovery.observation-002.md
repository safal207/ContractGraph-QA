# G-005 ATMAN observation 002 — source generation repin

Status: **HOLD — runtime fingerprint still required**

This observation is appended after the sealed G-005 case and does not modify the sealed commitment.

## Exact upstream source generation

All source-side evidence in this observation is pinned to:

```text
repository: gonka-ai/gonka
commit: 379bebced638aeb5e6077bfd51c986f898443832
```

The commit is the source generation used for the restart-path inspection below. It is not, by itself, proof that a future executed Docker/testenv runtime was built from this exact source generation.

Therefore:

```text
SOURCE_GENERATION_REPINNED = true
RUNTIME_GENERATION_PROVEN = false
TARGET_CLAIM_ALLOWED = false
```

## Restart control at the pinned generation

`devshard/testenv/citest/versiond_restart_persistence_test.go` verifies that gateway session state survives one versiond restart and then all versiond restarts. It snapshots the gateway session, performs chat, restarts services, requires session stability, and then requires the same session to advance after subsequent chat.

This is a valid restart/session-continuity control. It does **not** by itself establish end-to-end causal lineage for one pending logical operation across:

```text
logical operation
  -> transport request id(s)
  -> execution nonce(s)
  -> accounting mutation(s)
  -> settlement reference(s)
```

## Request/accounting surface at the same source generation

At the same pinned commit, the gateway exposes:

```text
GET /v1/requests/{request_id}
```

and the proxy carries a generated request identifier in request logging context. For streaming responses, `X-Request-Id` is emitted when the first response bytes are written. The implementation intentionally continues upstream protocol completion after client disconnect so host/devshard metadata can still drain.

These are relevant lineage surfaces, but they do not yet prove persistence of the request-to-accounting mapping through a restart with pending usage.

## ATMAN next-best-evidence decision

Because source generation is now pinned but executed runtime identity is not yet proven, the next admissible evidence check remains:

```text
COMPARE_RUNTIME_FINGERPRINT
```

Only after runtime/source/evidence generation coherence is established may the held-out investigation advance to:

```text
TRACE_REQUEST_IDENTITY
```

for a request deliberately left in a pending/ambiguous state across restart.

## Current verdict

```text
verdict: HOLD
reason: runtime generation is not yet independently bound to the repinned source generation
target_claim_allowed: false
```

This is verifier-side uncertainty, not a Gonka defect claim.

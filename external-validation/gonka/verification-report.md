# Gonka Verification Report

Status: DESIGN / NOT YET EXECUTED
Profile: gonka-verification-v0.1
Environment: DevNet/local/explicitly permitted only

## Executive summary

This report records independent verification of Gonka critical state transitions across inference, devshard escrow, off-chain accounting, settlement, epoch rotation, and reward recovery.

No vulnerability claim should be made from this document until a scenario has been reproduced and its evidence bundle independently checked.

## System under test

- Gonka protocol / implementation revision:
- Gateway revision:
- Network/environment:
- Epoch(s):
- Model:
- Test identity/account:

## Verification target

`actor -> action -> state transition -> invariant -> evidence`

## Scenario results

| Scenario | Invariant | Verdict | Evidence ref | Notes |
|---|---|---|---|---|
| G-001 | I2/I3/I4/I5/I6 | NOT RUN | — | control |
| G-002 | I3/I5 | NOT RUN | — | timeout/retry |
| G-004 | I6/I7 | NOT RUN | — | ambiguous settlement |
| G-005 | I3/I5/I6 | NOT RUN | — | restart/recovery |
| G-006 | I6/I8 | NOT RUN | — | epoch rotation |

## Evidence bundle schema

```json
{
  "profile": "gonka-verification-v0.1",
  "scenario_id": "G-000",
  "logical_operation_id": "",
  "execution_ids": [],
  "epoch": null,
  "devshard_id": "",
  "request_digest": "",
  "pre_state_digest": "",
  "observed_transitions": [],
  "post_state_digest": "",
  "settlement_refs": [],
  "expected_invariants": [],
  "verdict": "NOT_RUN",
  "evidence_refs": []
}
```

## Finding template

### CGQA-GONKA-XXX — title

- Severity / impact class:
- State transition:
- Preconditions:
- Expected invariant:
- Observed behavior:
- Minimal reproduction:
- Financial/accounting delta:
- Recovery behavior:
- Evidence references:
- Reproduction confidence:
- Disclosure status: PRIVATE / COORDINATED / PUBLIC

## Disclosure rule

Potential security-sensitive defects remain private until remediation or explicit coordinated-disclosure approval. The public profile may describe methodology and non-sensitive verification results without publishing exploitable details.

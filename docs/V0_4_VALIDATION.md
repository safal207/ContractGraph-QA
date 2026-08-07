# v0.4 validation matrix

| Capability | Authorized local demonstration | Expected result |
|---|---|---|
| Parameter boundary sweep | `fund(1)`, `fund(100)`, `fund(101)` | First cap violation is `fund(101)` |
| Temporal action search | `fund(1)`, `wait(1 day)`, `refund()` | Refund-timing invariant fails |
| Temporal control | `fund(100)`, `wait(7 days)`, `refund()` | Refund-timing invariant holds |
| Deterministic reset | Reset target and baseline clock for every candidate | Candidate order does not inherit prior time |
| Deterministic replay | Replay discovered `StepInput[]` on a fresh target | Same invariant outcome is reproduced |
| Client evidence | Render `CGQA-002` and `CGQA-003` through v0.3 renderer | Golden Markdown matches byte-for-byte |

All demonstrations use deliberately vulnerable local fixtures owned by this repository.

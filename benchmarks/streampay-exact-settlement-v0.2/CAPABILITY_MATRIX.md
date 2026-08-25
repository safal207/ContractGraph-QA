# v1.9 required capability execution matrix

The 30 rows below correspond one-for-one to the requested audit route. Engine
execution and semantic claim scope are distinct.

| # | Capability | Input / evidence | Status / bounded result |
| ---: | --- | --- | --- |
| 1 | Exact Subject / Artifact Gate | `verify.py`, `inputs/subject-freeze.json` | RUN — target `UNCHANGED`; exact commit/tree/base/diff and full CGQA release-tree fingerprint valid |
| 2 | Preregistered Verification Plan | `inputs/verification-plan.json` | RUN — plan/result binding only |
| 3 | Orientation Center | `inputs/orient.json` | RUN — `HOLD` / `INDETERMINATE` |
| 4 | Native Mapping / Adapter Review | `verify.py` + StreamPay source | RUN — production/model mapping reviewed; not a runtime adapter claim |
| 5 | Safety Invariants | `verify.py` + retained native harness | RUN — 45/47 model checks pass; two H2 host-boundary REDs; zero production-applicable failures |
| 6 | Liveness / Reachability | `inputs/lifecycle-liveness.json`, `inputs/reachability.json` | RUN — PASS over declared finite graphs; does not cover H10 custody/TTL |
| 7 | Financial Conservation | independent action-history oracle in `verify.py` | RUN — earned-time and three-way conservation clear for all production-applicable modeled scenarios |
| 8 | Authorization / Capabilities | retained native H8 matrix + model controls | RUN — payer-only rejection/atomicity and permissionless settle retained; no external witness claim |
| 9 | Replay / Idempotency | `verify.py`, `inputs/economic-cardinality.json`, `inputs/execution-trace.json` | RUN — once-only/repeat behavior clear over declared model/normalized events |
| 10 | Temporal Lifecycle | `verify.py` + retained H1–H10 native harness | RUN — H2 boundary held separately; H10 activated out of scope |
| 11 | Crash / Recovery | Soroban transaction boundary | `NOT_APPLICABLE` — rejected-batch rollback is native safety; no separate app-layer crash state |
| 12 | Causal / Ancestral Validity | `inputs/ancestry.json` | RUN — valid within declared trace |
| 13 | Transition Geometry | `inputs/geometry.json` + `verify.py` | RUN — one CLI pair plus nine computed pairs |
| 14 | Negative Control | `verify.py` | RUN — 9/9 dedicated mutants killed |
| 15 | Stateful / Property Search | historical v0.1 replay | RUN (historical) — 28 searches, 67 states, 686 transitions; v0.2 adds fixed scenarios, not another graph search |
| 16 | Independent Witness | manual `inputs/witness-blocked.json` status artifact | `BLOCKED` / `NOT_EXECUTED` — file is intentionally not witness-engine schema; no independent source was fabricated |
| 17 | Trace Integrity | `inputs/trace-integrity.json` | RUN — partial trace with explicit GAP |
| 18 | Evidence Type / Readiness | `inputs/evidence-readiness.json` | RUN — structural `READY`, not truth |
| 19 | Counterexample Minimization | `verify.py` + retained native harness | RUN — two minimal timestamp-zero witnesses retained separately |
| 20 | Root-Cause Collapse | `inputs/root-cause.json` | RUN — both H2 branches collapse to timestamp-zero sentinel collision |
| 21 | Deterministic Replay | `verify.py` | RUN — two byte-identical runs, 30,419 bytes, SHA-256 `f2ce20ad065483afe606670ea41c4c0ab15c7c56dd01ed9799de6d0ae636c2a2` |
| 22 | Metamorphic / Round-Trip Verification | `inputs/metamorphic.json` | RUN — two declared relations pass |
| 23 | Native Regression | `native/issue153_second_audit.rs`, native receipt | RUN — 18 tests: 16 pass, two intentional H2 test-host REDs |
| 24 | Durable Evidence Reopen / Integrity | `manifest.json` | RUN — final manifest built and reopened successfully |
| 25 | Verification Debt | `inputs/debt.json` | RUN — `HOLD`; no `COMPLETED_PASS` claim |
| 26 | Active Verification Planning | `inputs/plan-verification.json`, `inputs/record-verification-cost.json` | RUN — selected != verified; cost receipt != quality |
| 27 | Meaning Trajectory | README + trace/debt/watch | RUN — immutable H2/H3/H10 classifications |
| 28 | Dormant Patterns / Watchpoints | `inputs/watch.json` | RUN — H10 `ACTIVATED`, out of scope |
| 29 | Temporal / External Replication | `inputs/replicate.json` | RUN — temporal replay; not external independence |
| 30 | Forward Remediation | manual `inputs/remediate.json` fixture | `NOT_APPLICABLE` / `NOT_EXECUTED` — no production-applicable defect was fixed |

GitHub CI is separate and remains `BLOCKED_ACTION_REQUIRED` until jobs actually
run. Native Rust evidence is reported by the main audit and is not manufactured
from normalized CGQA projections.

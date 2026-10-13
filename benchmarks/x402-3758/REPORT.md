# Bounded verification report

Subject: `johnInarti/x402@4d3f2387bd3f2db8007cca324ef8dea23264c248`, draft
v0.2.1; host base `safal207/ContractGraph-QA@f13e586ea9118e026c69438b8c93d0585b8e38ba`.
Spine: `x402-3758-body-composition-20261011` (see preregistered `scope.md`).
Verdict: **PASS_WITHIN_BOUND**, F3 fixture evidence after two fresh-process native
attempts and closed-manifest verification. This is not an adjudicated SDK defect.

Both retained attempts execute all three cases with 3 PASS, 0 FAIL, 0 SKIP.
Linux, Node 24.19.0, pnpm 11.25.0, Python 3.12.14, native Vitest 3.2.7;
frozen native lockfile, lifecycle scripts disabled. Core exports are rebuilt
from the exact source before each attempt. Native production/lockfile bytes
remain unchanged; final native Git worktree is entirely clean. The new test
exists only as a temporary test overlay during each run.

Observed payload/paid-dispatch/synthetic-settlement counts are 1/1/1, 1/1/1
and 2/2/2 for valid, strict-missing/HOLD and unsafe-reinvocation paths.
Normal payment-result hooks run 1, 0 and 0 times. `onResult` precedes both
strict catches; exact body bytes and decoded settlement headers survive.
Distinct synthetic transactions witness the two explicit unsafe outer attempts.
The positive receipt is verified on the session/Ed25519 path; ML-DSA-65 is
explicitly unverified and `longTermEvidence=false`.

Existing native checks: 54 delivery-receipt unit tests, 17 red-team regressions
and 24 fetch-wrapper tests PASS. Relevant host payment regressions: 35 PASS.
The implementation agent also ran targeted native ESLint successfully. These
checks are separate from the new three-case assertions. Full host Foundry,
Slither/product checks are not run locally for this additive external fixture;
their actual draft CI states must be read separately. Cross-runtime native CI
is PENDING_PUBLICATION at packet assembly and is never inferred from host checks.

The native clients/wrappers are exercised rather than copied into a reference
model. The synthetic scheme and HTTP adapter intentionally define payment
preparation and settlement counters; they cannot prove on-chain execution.
Missing receipt evaluation stays `settlement=null`, even when the synthetic
header reports success. The new reachability concern is an unsafe external
caller, not automatic repayment in the native wrappers. Existing §8.4 states
the expectation, and existing #3260/#3349 work owns the separate validator API.

## Capability/debt matrix

RUN below names the actual procedural/native check; no CGQA explorer execution
or financial authorization is implied.

| Capability | State | Bound / evidence |
|---|---|---|
| Exact Subject / Artifact Gate | RUN | Native HEAD, clean tracked/final worktree, test hash and closed manifest |
| Preregistered Verification Plan | RUN | scope.md written before test implementation/execution |
| Orientation Center | RUN | Exact subject, expectation, overlap and debt in scope.md |
| Native Mapping / Adapter Review | RUN | Real wrappers/clients; fake scheme and HTTP adapter explicitly identified |
| Safety Invariants | RUN | Safe path counts remain one; receipt error follows synthetic settlement |
| Liveness / Reachability | RUN | Three finite paths reach return/HOLD/detected-control endpoints |
| Financial Conservation | NOT_APPLICABLE | No value transfer or modeled balances; attempt counters only |
| Authorization / Capabilities | NOT_APPLICABLE | Synthetic payloads/public test seeds are not operational authority |
| Replay / Idempotency | RUN | One invocation versus explicit reinvocation; no dedupe guarantee |
| Temporal Lifecycle | RUN | Fixed verifier Date clock and explicit ordered stages; no expiry boundaries |
| Crash / Recovery | NOT_APPLICABLE | No process crash or persistent dispatch state under test |
| Causal / Ancestral Validity | RUN | Settlement → response → onResult → catch ordering; prior evidence retained |
| Transition Geometry | RUN | Shared first failure followed by HOLD versus retry; history/counters diverge |
| Negative Control | RUN | Deliberately unsafe outer reinvocation detected as two synthetic attempts |
| Stateful / Property Search | SKIPPED_WITH_REASON | Explicit three-path native matrix; no new defect/model-search claim |
| Independent Witness | RUN | Adapter counts separate from client receipt verdict; same-process fixture only |
| Trace Integrity | RUN | Test hash, ordered snapshots and closed artifact membership |
| Evidence Type / Readiness | RUN | Two retained native attempts; F3 fixture observations |
| Counterexample Minimization | NOT_APPLICABLE | No newly discovered production counterexample |
| Root-Cause Collapse | NOT_APPLICABLE | No production root-cause claim or patch |
| Deterministic Replay | RUN | Fresh processes agree on counts, case outcomes and event ordering |
| Metamorphic / Round-Trip Verification | RUN | Exact response body and decoded encoded headers preserved |
| Native Regression | RUN | Three native Vitest tests at actual wrapper seam |
| Durable Evidence Reopen / Integrity | RUN | Retained JSON reopened and manifest verified; not crash-durability proof |
| Verification Debt | RUN | This matrix and explicit missing production/acceptance evidence |
| Active Verification Planning | RUN | Scope/stop conditions and independent review |
| Meaning Trajectory | RUN | Existing rule → source seam → native controls → bounded report |
| Dormant Patterns / Watchpoints | RUN | Outer catch-all retry is the explicit activation condition; no prediction |
| Temporal / External Replication | NOT_RUN | Fresh local processes only; dedicated Node 22/24 CI not yet published |
| Forward Remediation | NOT_APPLICABLE | No production state or runtime changed |

Learning decision: **DEFER** for upstream adoption; retain the test packet as
reviewable native evidence. The trigger is strict receipt failure after a paid
response. Applicability requires this exact wrapper order and an outer caller
that decides whether to reinvoke; it does not generalize to every x402 client.
No rules or product runtime are promoted/rewritten. Own draft publication is
authorized by the conversation; merge/deploy and live spending are excluded.

Remaining debt: no human review/maintainer acceptance, no cross-vendor or live
provider test, no external chain witness, no SSE/by-reference-failure or durable
retry coverage. Hashes establish byte integrity only. See README for reproduction.

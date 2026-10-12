# Bounded evidence record

Verdict: **COUNTEREXAMPLE_FOUND** for approval-owner preservation through the measured public JSON reconstruction path. This is a native SDK execution packet, not a ContractGraph-QA engine verdict or a framework-wide safety score.

## Exact subject and orientation

- Target: `openai/openai-agents-python`, issue #5341, originally reported by digit50.
- Released distribution: `openai-agents==0.23.1`, dependency freeze in `requirements.txt`.
- Source target: main `125efa029b4bfd84238bd2c4fd69c3406f802663`, tree `2b36e7911664ef8cd56f0a5b9b42a5724af5a253`. Checkout clean after execution.
- Identity implementation blob: `db0db775c9ec9877096a463c7c64e66290a7c533`; file SHA-256 `c80b214b355f57fcbdaf4d13636ab7b3731da1e747363e445b472cef7b0de7ff`. This file is byte-identical in the installed release and pinned source.
- Evidence host repository base: `safal207/ContractGraph-QA@f13e586ea9118e026c69438b8c93d0585b8e38ba`. Its engine was NOT_RUN; no engine or production runtime modification is proposed.
- Scope was recorded before execution in `scope.md`. Runner hash, execution environment and invocation are in `provenance.json`.
- Current state: disclosed issue open at pre-publication check; both native subjects exhibit the same bounded result. Six controls per subject contradict any blanket claim that every restoration fails.
- Independent oracle: owner Y is asserted literally; actual tool closures record their owners. This is independent of alias generation, but remains an in-process synthetic observation channel, not an external production witness.
- Authority: current user instruction “Го” continues the selected SDK validation/outreach step. Evidence does not create publication or retry authority. Any own-repository draft is reviewable and is not merge authority; an issue follow-up stays on the already public mechanism.
- Debt: no proposed fix, native GREEN run, upstream CI, live provider, unclean crash or distributed effect test. Readiness is sufficient for a bounded issue follow-up, not production release approval.

## Observed transitions

| Boundary | Observation | Authority / identity |
|---|---|---|
| Save: root hands off | Y owns interruption d1; effects empty | Explicit handoff to Y |
| Save: approval | Exact Y/record_effect/d1/approved-op approved | Single-call or sticky mode selected explicitly |
| Serialize | Public JSON written unchanged; counters X=0/Y=1 | Saved current-agent alias and owner-bearing approvals retained |
| Fresh-process restore | Fresh graph; counters preserved or reset | Same-name reset resolves to X; controls resolve to Y |
| Resume saved call | Callback appends approved-op under X or Y | Literal expected owner Y exposes the two failures |
| Provider continuation d2 | Single mode pauses; sticky mode appends follow-up-op | Single mode limits the next call, but does not repair the saved-call owner swap |

The ordered path is handoff → interrupt → approve → serialize → fresh construction → restore → saved call → new call. No wall-clock deadline or TTL is part of this claim. Preserve/reset challenges the reconstruction boundary; single/sticky challenges authorization scope. Unrelated order permutations and crash windows are not inferred from this trace.

## Cause, controls, replay and learning

Static source review agrees with the reported cause: same-name identity ordering includes normalized public hook attributes, so ephemeral counter changes can alter alias assignment. Tool-owner observations show execution, rather than only an internal pointer difference. Preserving counters or choosing unique names produces six passing controls; default hook reconstruction supplies the disclosed known-bad negative control.

The two failing approval modes collapse to this one cause. The bounded witness path uses two candidate agents and one saved operation. An automated minimizer or shortest-trace proof was not run. Preliminary and final executions matched on the outcome-bearing fields; final raw observations alone are published. Release and pinned-source executions independently repeat the same 8-case pattern with fixed scripts and `PYTHONHASHSEED=0`.

Learning candidate: regression coverage should separately bind logical owner, saved operation and approval scope across graph reconstruction. **PROMOTE as a regression candidate** supported by these executions; **DEFER** any universal action-safety rule or fix endorsement. Watchpoint: when a maintainer supplies a fix SHA or a new release, rerun the matrix and retain the historical FAIL evidence. A new result does not erase the old observation and does not authorize automatic deployment.

## Capability matrix

Statuses describe what was actually exercised for this native packet. `RUN` is a manual/native experiment capability, never an assertion that the corresponding ContractGraph-QA engine module ran.

| Capability | Status | Evidence or boundary |
|---|---|---|
| Exact Subject / Artifact Gate | RUN | Pinned source, distribution, runner hash, clean checkout |
| Preregistered Verification Plan | RUN | Scope recorded before the native matrix |
| Orientation Center | RUN | Exact subject, controls, debt and authority above |
| Native Mapping / Adapter Review | RUN | Public RunState boundaries; fake provider continuation reviewed |
| Safety Invariants | RUN | Exact callback owner and per-operation sequence |
| Liveness / Reachability | RUN | Only bounded returned/pending outcomes within five turns |
| Financial Conservation | NOT_APPLICABLE | No financial or custody model |
| Authorization / Capabilities | RUN | Single vs sticky approval, owner and new-call controls |
| Replay / Idempotency | SKIPPED_WITH_REASON | Saved-state round trip tested; retry/duplicate-effect idempotency outside scope |
| Temporal Lifecycle | RUN | Ordered checkpoint and continuation transitions; no clock deadlines |
| Crash / Recovery | SKIPPED_WITH_REASON | Separate-process reconstruction tested; unclean crash not exercised |
| Causal / Ancestral Validity | RUN | Original Y interruption and explicit approval verified before serialization |
| Transition Geometry | SKIPPED_WITH_REASON | Restore-state variants tested; general order permutations not run |
| Negative Control | RUN | Exact same-name/reset wrong-owner behavior detected |
| Stateful / Property Search | SKIPPED_WITH_REASON | Fixed 2×2×2 stateful matrix; no randomized/exhaustive search |
| Independent Witness | RUN | Closure effect oracle independent of alias helper; no external witness |
| Trace Integrity | RUN | Captured save/state/resume logs and SHA-256 manifest |
| Evidence Type / Readiness | RUN | Native observation separated from interpretation and authority |
| Counterexample Minimization | SKIPPED_WITH_REASON | Small bounded witness; automated minimization not run |
| Root-Cause Collapse | RUN | Two failing modes classified as one disclosed identity-ordering cause |
| Deterministic Replay | RUN | Repeated native executions; release/main share exact final pattern |
| Metamorphic / Round-Trip Verification | RUN | Public JSON round trip; preserve/reset and same/unique variants |
| Native Regression | RUN | External runner calls actual SDK; no regression added upstream |
| Durable Evidence Reopen / Integrity | RUN | Files reopened and manifest verified, with byte-tamper negative control |
| Verification Debt | RUN | Missing fix, CI, provider, concurrency and crash coverage stated |
| Active Verification Planning | RUN | Maintainer fix-SHA rerun and rejection-oracle question recorded |
| Meaning Trajectory | RUN | Public signal → pinned source → execution → candidate regression → watchpoint |
| Dormant Patterns / Watchpoints | RUN | Recheck changed source; no predicted exploit or automatic remediation |
| Temporal / External Replication | SKIPPED_WITH_REASON | Two SDK subjects measured now; no later-time or independent-operator run |
| Forward Remediation | NOT_RUN | No fix/deployment; preserve historical results for later comparison |

## Completion limits

The oracle does not use the SDK's identity helpers and therefore cannot mirror their alias swap. The saved approval ancestry is checked, known-bad behavior is detected, and actual SDK execution confirms the disclosed defect under the stated bounds. Controls limit the claim. Source inspection supports the cause but is not a substitute for a maintainer's accepted fix. Another reviewer can verify packet bytes and rerun both exact subjects using the documented commands. CI status remains NOT_RUN.

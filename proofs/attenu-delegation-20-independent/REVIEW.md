# Scoped completion review

This records the original local handoff. Subsequent user approval to publish the branch and PR is recorded in PUBLICATION.md; it does not retroactively turn these local checks into hosted CI or human review.

Spine: `attenu-delegation-20-2026-09-06`; parent boundary and authority remain in PLAN.md. Verdict: **PASS_WITHIN_BOUND for the twenty frozen files**, with external publication and hosted CI pending.

## Capability matrix

RUN identifies the method actually used below. Native CGQA execution is explicitly named; a manual review or Node test is not presented as execution of a CGQA model-search CLI.

| Capability | Status | Current-subject evidence or reason |
|---|---|---|
| Exact Subject / Artifact Gate | RUN | Node source/corpus/artifact gates and native CGQA subject-freeze; changed-digest control detected |
| Preregistered Verification Plan | RUN | PLAN.md was written before implementation and scoring; unchanged hash bound into first report. Native plan evaluator not used |
| Orientation Center | RUN | Manual: exact source, corpus, parent draft, user authority, initial state and debt documented; BALANCED for this bounded task |
| Native Mapping / Adapter Review | RUN | Reviewed API accepts only wire data, signer and explicit time; expectations remain in the harness. No production CGQA adapter claimed |
| Safety Invariants | RUN | Corpus rejections, malformed-data checks, no mutation of input, errors not collapsed into expected rejection |
| Liveness / Reachability | NOT_APPLICABLE | No persistent workflow or recovery state is modeled; only a terminating offline scorer |
| Financial Conservation | NOT_APPLICABLE | No money, balances or transfers |
| Authorization / Capabilities | RUN | Single test signer, parent authority, scope direction and constraint narrowing within corpus profile |
| Replay / Idempotency | RUN | Repeated pure calls and fresh-process report replay; no production idempotency store is claimed |
| Temporal Lifecycle | RUN | Explicit clock path around existing leaf expiry; no signed nbf fixture in corpus |
| Crash / Recovery | NOT_APPLICABLE | Verifier has no persistent state or external effects; harness output is regenerated |
| Causal / Ancestral Validity | RUN | Parent Signing Input commitment and parent-to-child authority/expiry/depth checks on the frozen chains |
| Transition Geometry | RUN | Corpus-order reversal and temporal replay tests; no stateful production geometry model |
| Negative Control | RUN | Constant-answer scorers, simulated exceptions, changed metadata, altered corpus identity and native changed-subject control |
| Stateful / Property Search | SKIPPED_WITH_REASON | Request is a fixed twenty-file offline conformance run. No fuzzing, live target or expanded offensive search |
| Independent Witness | NOT_RUN | Separately authored code exists; no second human reviewer, external execution witness or hosted CI result |
| Trace Integrity | NOT_APPLICABLE | No production execution trace. Finite case inventory and report/artifact hashes are checked without claiming observation completeness |
| Evidence Type / Readiness | RUN | Manual evidence classification: raw frozen inputs, generated local report, replayable commands; no host statement promoted to independent witness. Native readiness model not used |
| Counterexample Minimization | NOT_APPLICABLE | No unexpected corpus disagreement or production counterexample was found |
| Root-Cause Collapse | NOT_APPLICABLE | No production defect or multiple causal findings to collapse |
| Deterministic Replay | RUN | Fresh process regenerates first-run.json/report.json byte-for-byte |
| Metamorphic / Round-Trip Verification | RUN | JCS component round-trip, metadata independence, case-order invariance; no native cross-system transformation model |
| Native Regression | RUN | Eleven Node tests in verify.test.mjs. Upstream native suites not run because no upstream change or runtime-correctness claim |
| Durable Evidence Reopen / Integrity | RUN | Retained artifact inventory rehashed; native CGQA durable-manifest verification; clean local commit reopened |
| Verification Debt | RUN | Explicit coverage and evidence debt below; no absent check counted as a pass |
| Active Verification Planning | SKIPPED_WITH_REASON | Fixed corpus and preregistered controls; no candidate/cost optimization problem for native planning CLI |
| Meaning Trajectory | RUN | Initial snapshot → first generated score in immutable commit → unchanged implementation → replay and scoped interpretation; no history rewritten |
| Dormant Patterns / Watchpoints | SKIPPED_WITH_REASON | No partially activated production failure observed; uncovered dimensions remain coverage debt |
| Temporal / External Replication | NOT_RUN | Local repeat is not fresh third-party evidence; external run and hosted CI pending |
| Forward Remediation | NOT_APPLICABLE | No production repair, rollback or migration |

## Completion answers

The exact tested subject is the twenty upstream data files at `419f6584c120736688aa946b9c46cfe1c8124292`, consumed by the new verifier at `921173318176165a0d16e8b81c6913dbda4aa472`, based on CGQA `f861b934d77e64fd35f768e2a33bb4a00963bc19`. An upstream production service was not tested. All participating source and verifier identities are bound by hashes; labels alone are insufficient.

Orientation is resolved for conformance, with broader profile questions explicit. The authority ancestry is the user's instruction and Rafaela's bounded request. It permits this local work; it is not permission to send a reply, change upstream, merge, or claim payment.

Checked invariant families are input identity, syntactic validity, canonical bytes, test-key signatures, parent commitment, positional depth, authority narrowing and time. The forbidden outcomes exercised are accepting the thirteen published rejection cases, rejecting the seven controls, wrong rejection vocabulary, scoring an execution error as rejection, and scoring altered corpus bytes. No production state space was searched.

Mirroring risk remains because the corpus and its expected outcomes were authored by the upstream project, and the published fixture descriptions were read. It is reduced by a separately authored language/runtime implementation, no upstream runtime import or execution, separation of expectations from the verifier, constant-answer negative controls and explicit profile exceptions. Passing is not proof that the corpus is complete or internally normative in every dimension.

Ancestry is checked through signatures and parent commitments, not inferred from a locally plausible leaf. Case iteration order does not change results. Time changes produce the declared expiry transition; returning to an earlier explicit clock is only replay of immutable data. Every tested call leaves inputs unchanged. No irreversible state or hidden value movement is involved.

No actual mismatch or production defect was found, so counterexample minimization, upstream native regression and remediation do not apply. The first score is preserved and never silently replaced. Another reviewer can reproduce the finite result using the checked-in data, built-in Node primitives and documented commands.

## Remaining debt and counterevidence

- DPoP, Token Status Lists, actual actions, audience policy, production Ed25519 and multiple signing identities are outside scope.
- The safe-integer restriction, omitted child limit inheritance and egress rank order are declared corpus choices.
- Signed-token coverage of other constraint forms, omitted constraints, nbf, reduced child limits and JOSE extensions is absent. Direct comparison tests cannot fill that coverage.
- Upstream README says 1e16 for the exponent case; the actual vector uses 1e15. Preserve this small documentation discrepancy for maintainer consideration.
- No independent human review, external replay, hosted CI or upstream README pin. Local checks must not be described as those states.
- Repository-wide Foundry, Slither and product pipelines were not executed locally: only a new isolated proof and workflow were added, with no production, Solidity or earlier-proof edits. Prepared workflow execution is pending publication.

## Learning harvest

Trigger: a request described as draft steps 1–5 uses a deliberately narrower corpus profile. Invariant: the observed acceptance domain and key model must remain attached to any conformance score. Evidence: frozen valid-token claim shapes, exact README/spec pins, first run, unchanged replay and negative controls. Applicability is limited to this corpus; generalizing it into a production authorization rule would overfit.

Existing related proof artifacts were inspected. This adds a distinct Delegation Token proof, not another copy of the observer-envelope proof. No existing rule or runtime policy was changed.

Decision: **DEFER** specification/profile clarification and documentation drift for the maintainer; **NO_PROMOTION** of generalized security lessons or repository rules. Publication authority remains false at this local handoff. The next proposed transition is publishing the prepared PR after the user's explicit instruction, as required by `.cursor/rules/scoped-verdict-evidence-routing.mdc`.

# External Smart-Contract Investigation Gate v0.1

ContractGraph-QA now has a chain-neutral intake boundary for useful external investigations that begin before a complete adapter, native regression, or CGQA evidence bundle exists.

The gate answers a narrow question:

> Is this investigation record exact, evidence-classified, capability-complete, and honest about what did not run?

It does **not** answer whether the target contract is secure.

## Why this exists

Real smart-contract work often starts from:

- an assigned public issue;
- a source review;
- a reported external harness result;
- an architectural question owned by the maintainer;
- an incomplete ABI or dependency boundary;
- a production patch that should not be invented before semantics are approved.

Discarding that work loses useful evidence. Calling it a completed CGQA run overstates the result.

The external investigation record preserves the middle state:

```text
assigned or authorized source review
→ exact source subject
→ protected economic property
→ direct vs reported evidence
→ bounded finding
→ blocker + verification debt
→ smallest next transition
→ native RED / fix / GREEN
→ exact CGQA run and durable bundle
```

## Run the repository fixture

```bash
cgqa external-investigation \
  --record scenarios/external-investigation-stellar-dice-duel.json
```

The checked-in Soroban fixture returns:

```json
{
  "recordValidationStatus": "VALID",
  "findingStatus": "COUNTEREXAMPLE_FOUND",
  "workflowStatus": "BLOCKED",
  "nativeRegressionStatus": "NOT_RUN",
  "contractGraphQaStatus": "NOT_RUN",
  "boundedRemediationVerified": false,
  "securityVerdictAuthorized": false
}
```

The command exits successfully when the record is structurally and semantically valid, even if its workflow is blocked. `workflowStatus` is the continuation state, not the CLI validation state. A consuming release gate must inspect the output instead of treating exit code `0` as a security PASS.

## Contract

The runtime model is implemented in:

- `contractgraph_qa/external_investigation.py`

The provider-neutral JSON Schema is:

- `graph/schema/external-investigation.schema.json`

The complete example is:

- `scenarios/external-investigation-stellar-dice-duel.json`

The runtime validates stricter cross-field rules than JSON Schema alone can conveniently express.

## Exact subject gate

Every record requires:

- repository in `owner/name` form;
- lowercase 40-character source commit SHA;
- exact issue/reference URL;
- one or more relative source paths;
- ecosystem, language, and framework;
- explicit network or `null` when no deployed network subject was exercised.

A branch, issue number, filename, or mutable tag is not sufficient identity.

## Authorization boundary

Authorization is classified independently from source visibility:

| Status | Meaning |
|---|---|
| `CONFIRMED` | Written or public scope reference exists |
| `UNCONFIRMED` | Authority is unresolved; workflow is blocked |
| `NOT_REQUIRED` | Only genuinely non-invasive, owned, or otherwise non-actionable analysis is in scope |

Supported bases include assigned public issues, written scope, owned targets, public safe harbor, and source-review-only work.

Public source code alone is not permission to interact with a production deployment.

## Evidence states

The gate keeps evidence readiness separate from the finding:

| State | Meaning |
|---|---|
| `DIRECTLY_OBSERVED` | The reviewer inspected the referenced source or public record |
| `REPORTED_NOT_ARCHIVED` | A result was reported, but its executable bytes are not preserved in this record |
| `ARCHIVED_UNVERIFIED` | Bytes and SHA-256 exist, but independent verification is pending |
| `VERIFIED` | Archived bytes were independently checked inside the declared boundary |

`REPORTED_NOT_ARCHIVED` must not carry an invented artifact digest. Archived states require one.

## Execution states

Native regression and ContractGraph-QA execution are recorded separately:

```text
NOT_RUN | BLOCKED | RUN_FAIL | RUN_PASS
```

Any executed state requires an evidence reference and SHA-256. A CGQA execution also requires its own exact 40-character head SHA.

The following is rejected:

```text
remediationStatus = VERIFIED_WITHIN_BOUND
nativeRegression = NOT_RUN
ContractGraph-QA = NOT_RUN
```

Bounded remediation verification requires both native and CGQA `RUN_PASS` evidence.

## Finding language

The record deliberately has no blanket `PASS` finding state. It supports:

- `COUNTEREXAMPLE_FOUND`;
- `NO_COUNTEREXAMPLE_WITHIN_BOUND`;
- `INCONCLUSIVE`;
- `NOT_RUN`.

`NO_COUNTEREXAMPLE_WITHIN_BOUND` requires an explicit search bound and at least one executed passing search. Missing execution cannot become a clean result.

## Complete capability accounting

Every record classifies all 30 capabilities required by `AGENTS.md` as:

```text
RUN
NOT_APPLICABLE
BLOCKED
SKIPPED_WITH_REASON
NOT_RUN
```

The runtime rejects a missing, duplicate, or unknown capability row. This prevents a short journal from silently omitting the difficult checks.

`RUN` still means only that the named capability was exercised inside the stated evidence boundary. It does not imply that the ContractGraph-QA engine executed it.

## Verification debt and blockers

Blockers identify a question and its owner. Verification-debt items identify the missing evidence needed to advance.

For the Soroban dice-duel case, the load-bearing blocker is neutral settlement:

```text
both reveal      → normal settlement
only one reveals → forfeiture
neither reveals  → neutral return
```

The visible Game Hub boolean winner interface cannot represent the last path. Production remediation remains blocked until the maintainer supplies the official ABI or authorizes an additive cancellation path.

## Product impact boundary

Impact is always classified as:

- `QUALITATIVE`;
- `MODELED`;
- `MEASURED`.

Measured impact requires digest-bound `VERIFIED` evidence classified as `IMPACT_MEASUREMENT`. Modeled impact requires explicit assumptions. The Soroban record is qualitative because the technical fairness risk is supported, but no affected population, realized loss, or monetary value-at-risk was measured.

This supports a buyer-facing promise without fabricating ROI:

> Preserve one economically important contract property as an exact, reproducible, retestable evidence chain.

The first paid cases should later measure:

- value under control;
- failure or unfair settlement prevented;
- manual recovery avoided;
- time to reproduce and retest;
- pilot price and accepted buyer outcome.

## Transition to a full engagement

The external record is an intake artifact, not the final deliverable.

```text
valid investigation record
→ resolve maintainer-owned semantics
→ archive native RED regression
→ implement the smallest authorized fix
→ native GREEN + build + CI
→ execute CGQA against the exact final head
→ reopen and verify the durable evidence bundle
→ deliver finding + fix + retest
```

Use the [authorized engagement playbook](ENGAGEMENT.md) when the subject, semantics, and executable target are ready.

## Non-claims

Passing this gate does not establish:

- that ContractGraph-QA executed against the target;
- that a native regression exists;
- that the reported harness is independently replayable;
- that remediation is correct;
- that all vulnerabilities were found;
- that the target or repository is secure;
- that a reward, payment, or commercial result is owed.

It establishes only that the investigation record itself is strict, exact-subject-bound, capability-complete, and honest about its evidence state.

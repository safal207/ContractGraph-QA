# Pinned external mapping record: SafeAgent / Crashpoint v0.1

**External comparison: recorded as azender1's published report, not independently recomputed here. Local check: 12/12 unmodified adapter unit tests passed. SafeAgent core: not invoked.**

This record fulfills the request in CrewAI #5802 to reference the published
adapter beside its Crashpoint source. Publication improves inspectability and
attribution; it does not expand the experiment's claim boundary. It is not an
`ADMITTED` raw-evidence decision or an end-to-end runtime proof.

## Attribution and immutable subjects

- External adapter, tests, and sanitized aggregate: **azender1 / SafeAgent**, commit
  `52049faa07a1f24da60a65a02025d72274006e50`.
- Source fixture/evidence: **mstevens843 / crashpoint**, commit
  `bb9cd47c4b0b02527aab7b369d17b32829cc4e20`, bundle
  `evidence/action_readback/action_readback_self_reviewed_v2`.
- ContractGraph-QA contribution in this record: preserve provenance, acceptance
  boundaries, and non-claims; review the published mapping; rerun its unit tests.
  The adapter and source corpus are not represented as ContractGraph-QA code.
- [Publication comment, 2026-09-22](https://github.com/crewAIInc/crewAI/issues/5802#issuecomment-5770798945).
- [Pinned Crashpoint bundle](https://github.com/mstevens843/crashpoint/tree/bb9cd47c4b0b02527aab7b369d17b32829cc4e20/evidence/action_readback/action_readback_self_reviewed_v2).
- [Pinned adapter code](https://github.com/azender1/SafeAgent/blob/52049faa07a1f24da60a65a02025d72274006e50/evidence/action-readback-control-v1/action_readback_adapter.py).
- [Pinned adapter tests](https://github.com/azender1/SafeAgent/blob/52049faa07a1f24da60a65a02025d72274006e50/evidence/action-readback-control-v1/test_action_readback_adapter.py).
- [Pinned sanitized aggregate](https://github.com/azender1/SafeAgent/blob/52049faa07a1f24da60a65a02025d72274006e50/evidence/action-readback-control-v1/sanitized_result.json).
- [Pinned upstream scope](https://github.com/azender1/SafeAgent/blob/52049faa07a1f24da60a65a02025d72274006e50/evidence/action-readback-control-v1/README.md).

This is a **different corpus** from the [90-trial CrewAI retry admission](../crewai-retry-external-admission-v0.1/README.md).
Its counts and verification status must not be added to or inherited from that proof.

## What the external author reports

| Control classification | Reported trials | Meaning within the fixture boundary |
|---|---:|---|
| `CONFIRMED` | 6 | One observed effect with the admitted payload |
| `CONTRADICTION` | 6 | Multiple effects or a payload mismatch |
| `MISSING_EXTERNALLY` | 3 | No effect in the complete terminal readback |
| `UNCERTAIN` | 3 | Readback unavailable; outcome unresolved |

These are **18 classification results, not 18 successful executions**. The
published aggregate also reports a valid upstream manifest receipt and zero
upstream verification problems. Those remain author-reported observations here.
The publication comment reports CI on Python 3.10, 3.11, and 3.12; this review
has not independently checked those workflow runs or rerun the full suite.

## The boundary that survives the mapping

`CONFIRMED` requires the adapter's input contract to represent a committed
pre-dispatch action ID, a valid protocol, full authoritative readback, exactly
one effect, and a payload digest matching admission. `passed` is not used as
confirmation input. A duplicate or mismatched effect is not success; unavailable
readback is not absence of an effect.

Every returned trial has `replay_authorized=false`. In particular,
`MISSING_EXTERNALLY` is not a permit to execute again and must not be silently
converted into an authorization-bearing `NOT_EXECUTED` state in another adapter.
SafeAgent claim/TTL/sweep semantics are not exercised by this mapping.

## Important trust boundary

The adapter reads manifest fields such as `admission_commit_confirmed`,
`externally_verified`, `protocol_valid`, `effect_count`, and
`digests_match_admission`. It does **not** independently read the ledger or
admission database, validate the raw receipts, authenticate the observer, or
prove capture completeness. Its output source commit is hard-coded metadata,
not a verification that the supplied manifest came from that commit.

Consequently, its precondition is an already verified, correctly typed manifest
from the named source. The published rejection tests cover specific missing or
contradictory input cases; they are not exhaustive hostile-input validation.
A future raw-corpus recheck must establish source identity and run the pinned
Crashpoint offline verifier before invoking this mapper. Mapping consistency
alone cannot establish the truth of the supplied evidence.

The sanitized result deliberately omits action IDs, payload digests,
provider/subject identifiers, and credentials. It is an aggregate disclosure,
not a complete raw execution trace. Its counts alone cannot establish trial-by-
trial identity alignment or permit reconstruction of the original run.

## What was checked locally on 2026-09-23

The four published files were read through the GitHub connector, reconstructed
locally from its UTF-8 content, and matched against the Git blob SHA-1 values
returned for the exact SafeAgent commit. SHA-256 values of those matched bytes
are recorded in [evidence.json](evidence.json).

The unmodified published adapter tests passed **12/12** on Python **3.13.5**,
pytest **9.0.2**, Linux. Plugin autoload was disabled. See the retained
[stdout](local-unit-tests.stdout.txt); stderr was empty and exit code was zero.
This is a separate execution of upstream-authored tests, not an independently
implemented verifier and not the author's 18-trial comparison.

The container could not download the full Crashpoint bundle, so no fresh
18-trial raw-bundle verification or aggregate recomputation is claimed. No
Crashpoint acquisition run, SafeAgent reconciliation core, CrewAI runtime,
provider, or distributed service was started.

To repeat **only the adapter unit-test check**, in a disposable checkout:

```bash
git clone https://github.com/azender1/SafeAgent.git SafeAgent-pinned
cd SafeAgent-pinned
git checkout --detach 52049faa07a1f24da60a65a02025d72274006e50
test "$(git rev-parse HEAD)" = "52049faa07a1f24da60a65a02025d72274006e50"
cd evidence/action-readback-control-v1
python3.13 -m venv .venv
.venv/bin/python -m pip install 'pytest==9.0.2'
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
  .venv/bin/python -m pytest -q -p no:cacheprovider test_action_readback_adapter.py
```

These instructions require network access for checkout and installation. The
recorded local interpreter was 3.13.5; this command does not pin an OS image or
all transitive packages. Compare the four file hashes with `evidence.json` before
running changed or locally modified sources.

## Non-claims

This record establishes no global exactly-once execution, replay safety,
provider-side idempotency, distributed durability, SafeAgent crash/fresh-worker
recovery, complete reconciliation lifecycle, or CrewAI framework fix. It does
not show `CONFIRMED -> return_prior` through SafeAgent's frozen core, claim/TTL/
sweep behavior, or production readiness. No CrewAI maintainer endorsement,
certification, or exhaustive safety guarantee is inferred from an issue comment,
a pinned commit, a passing unit test, or the aggregate classifications.

## Portfolio wording

> Contributed to evidence-boundary review in CrewAI #5802 and requested pinned
> artifacts. SafeAgent author azender1 published an external adapter and a
> bounded 18-trial classification report over a pinned Crashpoint corpus.
> ContractGraph-QA records the provenance and non-claims and separately reran
> the 12 published adapter unit tests. This demonstrates inspectable evidence
> mapping and explicit handling of uncertainty, not exactly-once execution or
> end-to-end SafeAgent/CrewAI validation.

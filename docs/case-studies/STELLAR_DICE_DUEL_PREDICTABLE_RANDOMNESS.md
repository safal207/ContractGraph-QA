# External Investigation Journal — Soroban Dice-Duel Predictable Outcome

**Recorded:** 2026-08-27  
**Journal status:** COUNTEREXAMPLE_FOUND / REMEDIATION_BLOCKED  
**Upstream issue:** [Bitcoindefi/Stellar-Game-Studio #1](https://github.com/Bitcoindefi/Stellar-Game-Studio/issues/1)  
**Upstream subject:** [43a933a84c7c3133365bf56b6998a26fdf360b24](https://github.com/Bitcoindefi/Stellar-Game-Studio/commit/43a933a84c7c3133365bf56b6998a26fdf360b24)  
**Assigned investigator:** [safal207](https://github.com/safal207)  
**Primary contract:** contracts/dice-duel/src/lib.rs  
**ContractGraph-QA execution:** NOT_RUN

This is a source-bound journal entry for an authorized public issue investigation. It records what was observed and reported before any production patch. It is not a full audit, a merged fix, or a claim that ContractGraph-QA has already verified the remediation.

## Property under review

A participant who assembles a game must not be able to select the winner before both wagers are committed.

~~~text
known public inputs before betting
!=
participant-selectable winning outcome
~~~

## Direct source observation

At the pinned upstream commit:

- start_game accepts a caller-supplied session_id;
- both players authorize arguments containing that session_id and their points;
- roll only records that each player has rolled;
- reveal_winner later derives the dice seed from session_id, player1, and player2;
- ledger sequence and timestamp are intentionally excluded so simulation and submission remain deterministic.

All seed inputs are therefore known before the wager is finalized. Changing session_id changes the deterministic dice outcome without requiring either player to contribute hidden entropy.

[Inspect the pinned contract source](https://github.com/Bitcoindefi/Stellar-Game-Studio/blob/43a933a84c7c3133365bf56b6998a26fdf360b24/contracts/dice-duel/src/lib.rs)

## Reported RED counterexample

The public investigation update reports an independent Soroban harness that reconstructed the production seed and dice logic for the exact subject above.

With the same players and point amounts:

| Session | Dice | Winner |
|---|---|---|
| session_id = 1 | [5, 4, 3, 2] | player 1 |
| session_id = 3 | [4, 4, 4, 6] | player 2 |

The reported values matched the contract result. The same update also reports that:

~~~text
roll(P1) → roll(P2)
~~~

and:

~~~text
roll(P2) → roll(P1)
~~~

produced the same outcome, and changing the ledgers used for the two roll calls did not change the dice.

Bounded conclusion:

> roll() does not add entropy, and an actor able to choose session_id can search candidate IDs before creating the game and select a favorable winner.

The harness itself is not yet archived in this repository, so this journal preserves the public result and source binding but does not claim a locally replayable ContractGraph-QA evidence bundle.

[Read the public counterexample and resource update](https://github.com/Bitcoindefi/Stellar-Game-Studio/issues/1#issuecomment-5429093502)

## Root cause

The implementation preserves deterministic equality between Soroban simulation and submission by excluding ledger-dependent values. That solves one consistency problem but leaves the outcome derived entirely from values known before betting.

The defect is therefore not that deterministic execution exists. The unsafe boundary is that one participant can search a deterministic, caller-controlled input before the other participant commits value.

## Scope triage

The initial review considered three contracts:

- dice-duel;
- number-guess;
- twenty-one.

The current issue should remain focused on dice-duel.

The other two are retained as watchpoints, not confirmed equivalent defects:

- number-guess may require hidden guesses to prevent a second-mover advantage;
- twenty-one may require sequential randomness because revealing one initial seed could expose future cards.

A shared patch must not be forced across three different game semantics.

## Candidate remediation

The proposed direction is a two-party commit-reveal state machine:

~~~text
Open
→ Committed
→ Revealing
→ Settled | Forfeited | Cancelled
~~~

Candidate controls include:

- a uniformly random BytesN<32> secret from each player;
- a domain-separated canonical commitment bound to contract, game, session, role, addresses, and exact wagers;
- reveal verification before combined-seed derivation;
- explicit commit and reveal deadlines;
- rejection of wrong secrets, duplicate reveals, cross-game replay, and reused commitments;
- mutually exclusive normal settlement, forfeiture, and neutral cancellation paths;
- once-only terminal value movement.

This is a design proposal, not approved production semantics.

## Architecture blocker

For dice-duel, commit-reveal creates four terminal situations:

1. both players reveal → normal settlement;
2. only player 1 reveals → player 2 forfeits;
3. only player 2 reveals → player 1 forfeits;
4. neither reveals → neutral return of the original points.

The visible Game Hub interface exposes:

~~~text
end_game(session_id, player1_won: bool)
~~~

That boolean cannot represent a neutral terminal outcome. Selecting either player would invent a winner; performing no terminal call could leave points locked.

The upstream maintainer has therefore been asked to provide the official Game Hub ABI or authorize an additive operation such as:

~~~text
cancel_game(session_id)
~~~

No production implementation should proceed until that authority boundary is resolved.

[Read the architecture question](https://github.com/Bitcoindefi/Stellar-Game-Studio/issues/1#issuecomment-5428236790)

## Reported Soroban resource observation

A test-only native commitment prototype was reported with the following measurements:

| Measurement | Reported value |
|---|---:|
| Canonical preimage | 344 bytes |
| Worst observed ratio against the SDK limit snapshot | 2.25% |
| Maximum CPU | 193,499 instructions |
| Maximum memory | 42,820 bytes |
| Maximum write footprint | 3 entries / 500 bytes |

The prototype bound version/domain, contract, game, session, role, player address, both players, both wagers, and one random 32-byte secret.

These figures do **not** include deployed WASM execution, real signatures, the production Game Hub, network rent, or fees. They support early feasibility only.

## Capability demonstrated

This investigation records practical evidence for:

- adversarial smart-contract QA focused on economic advantage rather than only code coverage;
- Rust/Soroban source review and native-harness reasoning;
- deterministic negative controls and exact-subject binding;
- commit-reveal, replay protection, deadline, forfeiture, and cancellation design;
- state-machine separation of Settled, Forfeited, and Cancelled;
- value-conservation and once-only terminal-path analysis;
- resource-aware security design;
- stopping at a maintainer-owned semantic boundary instead of coding an invented fix.

A concise market description is:

> Independent Smart Contract Security and Economic Invariant Testing

## Capability snapshot

This table reports the state of the upstream investigation. It is **not** a claim that the ContractGraph-QA engine has already executed these capabilities.

| Capability | Status | Evidence boundary |
|---|---|---|
| Exact Subject / Artifact Gate | RUN | Repository, contract path, and 40-character commit pinned |
| Preregistered Verification Plan | RUN | Public pre-implementation plan |
| Orientation Center | RUN | Open issue, assignment, finding, and blocker recorded |
| Native Mapping / Adapter Review | RUN | Pinned dice-duel source inspected |
| Safety Invariants | RUN | Winner-selectability path identified |
| Liveness / Reachability | BLOCKED | Neutral no-reveal terminal path is undefined |
| Financial Conservation | BLOCKED | Neutral return semantics require Game Hub authority |
| Authorization / Capabilities | RUN | Player authorization and caller-controlled session input inspected |
| Replay / Idempotency | NOT_RUN | Candidate controls exist; no implementation to test |
| Temporal Lifecycle | BLOCKED | Commit/reveal deadlines are not yet authoritative |
| Crash / Recovery | NOT_APPLICABLE | Not part of the current bounded finding |
| Causal / Ancestral Validity | NOT_APPLICABLE | Not part of the current bounded finding |
| Transition Geometry | RUN | Roll order and ledger variation reportedly challenged |
| Negative Control | RUN | Current implementation used as the RED baseline |
| Stateful / Property Search | RUN | Offline session_id search reported; full bounds not archived |
| Independent Witness | RUN | Independent harness reported; artifact not yet archived |
| Trace Integrity | NOT_RUN | No durable trace bundle exists yet |
| Evidence Type / Readiness | RUN | Source and issue evidence public; executable bundle incomplete |
| Counterexample Minimization | SKIPPED_WITH_REASON | Two-ID witness preserved; no formal minimizer executed |
| Root-Cause Collapse | RUN | Caller-controlled deterministic seed isolated |
| Deterministic Replay | RUN | Predicted values reportedly matched contract execution |
| Metamorphic / Round-Trip Verification | RUN | Roll order and ledger variation reportedly preserved outcome |
| Native Regression | NOT_RUN | No committed native RED/GREEN test yet |
| Durable Evidence Reopen / Integrity | NOT_RUN | No archived harness bundle yet |
| Verification Debt | RUN | Missing ABI, regression, fix, WASM, CI, and CGQA run listed |
| Active Verification Planning | RUN | Next work is gated on maintainer semantics |
| Meaning Trajectory | RUN | Signal → counterexample → cause → authority blocker recorded |
| Dormant Patterns / Watchpoints | RUN | number-guess and twenty-one retained separately |
| Temporal / External Replication | NOT_RUN | No later subject or independent external replay checked |
| Forward Remediation | BLOCKED | Awaiting official neutral-settlement semantics |

## Verification debt and next transition

The smallest justified continuation is:

1. obtain the official Game Hub ABI or explicit approval for neutral cancellation;
2. freeze the resulting authoritative semantics;
3. commit the native RED regression;
4. implement the smallest dice-duel fix;
5. run cargo fmt, Clippy with warnings denied, native tests, and the relevant WASM build;
6. run ContractGraph-QA externally against the final exact head;
7. archive deterministic replay and evidence-integrity artifacts;
8. open a focused upstream PR containing Closes #1.

Until step 1 is complete, production modification remains BLOCKED.

## Explicit non-claims

This journal does not claim:

- a production fix, upstream commit, or pull request exists;
- native GREEN, WASM, CI, or ContractGraph-QA verification has run;
- number-guess or twenty-one have the identical defect;
- the whole repository or deployed system is secure or insecure;
- the native resource sample predicts production network cost;
- a GrantFox reward, amount, payment, or eligibility is confirmed;
- the upstream author's nationality is known from the Spanish-language discussion.

The upstream issue is labeled Maybe Rewarded; payment is handled by the campaign platform and is not an existing receivable.

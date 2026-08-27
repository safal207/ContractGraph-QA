# Smart Contract Continuity Bridge v0.1 validation record

Status: `BRIDGE_READY_WITH_LIMITATIONS`.

This evidence snapshot was captured while the candidate was still local and
uncommitted on two named branches. During the collection window no commit,
push, pull request, release, live RPC call, external write, or production
mutation was performed. Any later publication is a separately authorized
transition and does not alter this historical validation record.

## RED / GREEN chronology

1. The bridge test was added before implementation and failed RED with
   `ModuleNotFoundError: contractgraph_qa.ltp_continuity_bridge`.
2. The minimal producer/adapter, schemas, CLI, benchmark, and cross-repository
   test were then implemented.
3. The LTP continuity verifier and all normative LTP schemas remained
   unchanged.

## Exact subject gate

| Repository | Frozen source | Publication base | Relationship |
|---|---|---|---|
| ContractGraph-QA | `007c1fa68dac5b19b73e6ab1b4f606727e620ed7` / `4abd38371fdedc907825b17f27d6ccbd3ee2519c` | `ff617b3cbbf29ad6a0e5bdee5760e44f30d77ab7` / `bd9bf9f2243c3251c1c0040276c1c85c299f0aee` | main advanced by one unrelated documentation-only commit |
| LTP | `08734d248c24dfb2ee8e4f4a3f689887ead0ea24` / `5eb684d990701fa959f0b2a87125ebd765df70cd` | same | unchanged |

Both source worktrees were clean before branching. The final worktrees contain
only the intended candidate changes. ContractGraph-QA `main` moved after the
initial evidence snapshot: the only intervening path was
`docs/LANGGRAPH_RECOVERY_SAFETY.md`. The candidate was rebased onto that exact
head and the full 661-test CGQA suite, compile gate, CLI help, and diff check were
rerun successfully. The movement and revalidation remain explicit rather than
being rewritten as an unchanged subject.

## ContractGraph-QA gates

| Command / check | Exit | Result |
|---|---:|---|
| `python -m pytest -q` | 0 | 661 passed, 14 skipped, 31 subtests passed |
| bridge + benchmark targeted tests | 0 | 21 passed, 15 subtests passed |
| `python -m compileall -q contractgraph_qa` | 0 | compile clean |
| `python -m contractgraph_qa.cli --help` | 0 | unified command listed |
| `python -m contractgraph_qa.cli continuity-export --help` | 0 | final CLI contract rendered |
| JSON Schema validation for 2 intents, 11 observations, 1 bridge report | 0 | all valid against the new schemas |
| offline wheel build | 0 | `contractgraph_qa-1.9.0-py3-none-any.whl`, SHA-256 `9c9052e7ee2b2e35395abe0b21b02251bee8e3c9ae41ed0b7129b16a0a4851c4` |
| installed-wheel portability gate | 0 | deterministic artifacts, canonical LF, version 1.9.0 |
| installed-wheel `continuity-export` outside checkout | 0 | LTP input and bridge report byte-identical to benchmark |
| `git diff --check` | 0 | no whitespace errors |

Baseline before bridge changes was 640 passed, 14 skipped, 16 subtests. Build
residue was moved outside the repository after the wheel gate.

## LTP gates

All final test execution used the repository-declared `pnpm 9.15.0`. Dependencies
were restored without network access from the local pnpm content-addressed store
using a frozen lockfile and ignored lifecycle scripts. Neither the lockfile nor
`pnpm-workspace.yaml` changed.

| Command / check | Exit | Result |
|---|---:|---|
| `pnpm test` | 0 | 21 files, 148 tests passed |
| `pnpm -w test:lifecycle-integrity` | 0 | 4 files, 54 tests passed |
| pass fixture through `ltp:continuity` | 0 | `CONTINUOUS`; report matches committed bytes |
| broken fixture through `ltp:continuity` | 2 | `BROKEN_MISSING_OUTCOME`; report matches committed bytes |
| invalid fixture through `ltp:continuity` | 1 | schema rejected; no report created |
| second pass-fixture run | 0 | byte-identical report |
| `git diff --check` | 0 | no whitespace errors |

Baseline lifecycle-integrity count before the compatibility test was 52 tests.
The final count is 54. The fixture in LTP is an exact byte copy of the CGQA
single-request pass case.

## Verified fixture matrix

| Case | Exit | Normative result |
|---|---:|---|
| one request / one completed receipt-event | 0 | `CONTINUOUS` |
| timeout retry / one canonical outcome | 0 | `CONTINUOUS` |
| deadline elapsed / no outcome | 2 | `BROKEN_MISSING_OUTCOME` |
| outcome without request | 2 | `BROKEN_ORPHAN_RESPONSE` |
| incompatible terminal outcomes | 2 | `BROKEN_CONFLICTING_OUTCOMES` |
| retry parent missing | 2 | `BROKEN_RETRY_GAP` |
| event/indexer trace mismatch | 2 | `BROKEN_TRACE_MISMATCH` |
| receipt present / indexer outcome absent | 2 | `BROKEN_MISSING_OUTCOME` |
| both transaction attempts paid | 2 | `BROKEN_CONFLICTING_OUTCOMES` |
| duplicate exact outcome | 0 | `CONTINUOUS` + `REPLAY_DETECTED` |
| one attempt owned by two requests | 1 | semantic input rejection |
| unexpected schema property | 1 | JSON Schema rejection |

## Negative controls

Bridge-level controls reject or prevent:

- transaction hash used as logical `requestId`;
- one `attemptId` owned by two logical requests;
- chain ID, contract address, or args digest mismatch;
- API success fabricated as root on-chain completion;
- receipt without a reviewed exact binding;
- duplicate JSON object keys and non-finite JSON numbers;
- unknown critical fields;
- output overwrite without `--force`;
- direct, hard-link, and symbolic-link input/output aliases, plus paths that
  contain parent-directory traversal;
- raw observation metadata, synthetic endpoint markers, credential markers, and
  local path markers leaking into output.

## Deterministic artifacts

| Artifact | SHA-256 |
|---|---|
| generated LTP input file | `a738785a60166e71ac4f8e7111b1384a87c18925715a5bcfe5eb832878cf3f74` |
| generated bridge report file | `214414fd80017d9ca82373119f49c7fa9070c51bf47eddbcb7bdac38dc6f0916` |
| generated LTP report file | `48744831e209647e155b82e836f7e9521a6bb513a82c2081f93fb93b409d75c8` |
| replayed LTP report file | `48744831e209647e155b82e836f7e9521a6bb513a82c2081f93fb93b409d75c8` |

The compact canonical LTP-input digest inside the bridge report intentionally
differs from the pretty-printed file-byte digest; both are deterministic and
serve different identity layers.

## Advisory boundary

- ContractGraph-QA produces reviewed evidence and LTP envelopes; it does not
  compute continuity status.
- LTP remains the sole normative continuity verifier.
- Current capture does not independently decode transaction calldata, sender,
  or nonce; those are reviewed binding declarations in v0.1.
- One RPC observation and observed confirmations do not establish canonical
  finality, reorg absence, or observation completeness.
- Authorization policy, live economic balance conservation, and Soroban are not
  verified by this candidate.
- The durable manifest proves local byte integrity and replayability, not
  external authenticity.

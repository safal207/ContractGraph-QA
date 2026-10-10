# Fresh-process approval-owner checks for OpenAI Agents SDK #5341

An independent reproduction of [digit50's public report](https://github.com/openai/openai-agents-python/issues/5341). With duplicate agent names and reconstructed default hook counters, an operation approved for Y executes X's tool after `RunState.from_json`. The same controlled result occurs on released `openai-agents==0.23.1` and upstream main `125efa029b4bfd84238bd2c4fd69c3406f802663`.

This packet adds separate save/resume processes, newly constructed Agent/hook/tool/model instances, six positive controls, and separate single-call and sticky-approval cases. Discovery and the original reproduction belong to digit50. Validation by Alexey Safonov / safal207, with AI-assisted implementation and review.

## Measured results

Each row was executed on both SDK subjects. Y is the literal expected owner, independently of SDK identity helpers.

| Names | Hooks on fresh graph | Approval | Release 0.23.1 | Pinned main | Observed operations |
|---|---|---|---|---|---|
| Same | Preserved | Single | PASS | PASS | Y executes approved-op; Y/d2 awaits approval |
| Same | Preserved | Sticky | PASS | PASS | Y executes approved-op and follow-up-op |
| Same | Reset | Single | FAIL | FAIL | X executes approved-op; X/d2 awaits approval |
| Same | Reset | Sticky | FAIL | FAIL | X executes approved-op and follow-up-op |
| Unique | Preserved | Single | PASS | PASS | Y executes approved-op; Y/d2 awaits approval |
| Unique | Preserved | Sticky | PASS | PASS | Y executes approved-op and follow-up-op |
| Unique | Reset | Single | PASS | PASS | Y executes approved-op; Y/d2 awaits approval |
| Unique | Reset | Sticky | PASS | PASS | Y executes approved-op and follow-up-op |

Per subject: **6 PASS / 2 FAIL / 0 ERROR**. The two failures share the already reported root cause; they are not two independent discoveries. Raw JSON and process logs for all 16 cases are under `evidence/`. Assertions include exact effect sequences, public last agent, interruption owner/call ID, final output, and different save/resume PIDs. The private `_current_agent` field is diagnostic only.

## Reproduce

Tested with CPython 3.12.14 on Linux. `requirements.txt` freezes the installed runtime dependencies; it is not a signed supply-chain attestation. Run from this directory. Each output path must be new.

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
python3.12 verify_packet.py
.venv/bin/python reproduce.py --output out-release --label release-0.23.1 --expect-known-bug
```

To test the exact upstream source using the same installed dependencies:

```bash
git clone --no-checkout https://github.com/openai/openai-agents-python.git sdk-source
git -C sdk-source checkout --detach 125efa029b4bfd84238bd2c4fd69c3406f802663
.venv/bin/python reproduce.py --output out-main --sdk-src sdk-source/src --label main-125efa029b4bfd84238bd2c4fd69c3406f802663 --expect-known-bug
```

`--expect-known-bug` returns zero only when all six controls PASS and the two failing cases return the exact measured X-owned behavior. It **preserves FAIL verdicts**. Any unexpected failure, exception, safe rejection or changed result rejects that baseline. Omit this flag when checking a candidate fix: default exit zero requires all eight owner assertions to PASS; the tested subjects return one in that mode. A fix that deliberately rejects ambiguous restoration may need a separately agreed rejection oracle.

## Experiment boundary

The save process hands off to Y, stops before `record_effect(approved-op)`, approves that exact pending call, and writes unmodified public `RunState.to_json()` output. The resume process constructs a new graph. The preserved-hooks control copies the recorded counters X=0/Y=1; reset uses constructors' X=0/Y=0. Names and approval mode are the other two axes.

After restoration both scripted models emit **a new call d2 / follow-up-op**. They do not repeat the saved d1 request. This isolates approval scope from resetting a fake provider response queue. Only the synthetic continuation position is modeled; no provider checkpoint persistence is claimed.

Tool effects are closure-owned memory appends, observed independently of the SDK's alias resolver. They are not real external effects. Tracing is disabled; child environments omit credentials, and a Python audit hook denies socket connect/name-resolution/sendto attempts. This is not an OS network sandbox. No blocked network attempt surfaced in the captured outputs.

Separate processes demonstrate this controlled JSON reconstruction boundary. They do not demonstrate unclean-crash recovery, external settlement, retry durability, concurrency, exactly-once behavior, exploit severity, or comprehensive SDK safety. Unique names pass this matrix; that is not a universal mitigation guarantee. No SDK runtime changes, upstream PR, upstream CI results, or ContractGraph-QA engine execution are included.

## Evidence and next check

`provenance.json` binds source identities, environment, invocation and runner hash. `EVIDENCE.md` records transition observations, verification debt and capability status. `manifest.json` plus `verify_packet.py` detect file changes; hashes establish integrity relative to this manifest, not authorship or authenticity.

The existing issue is the contribution channel: the pinned upstream [contribution policy](https://github.com/openai/openai-agents-python/blob/125efa029b4bfd84238bd2c4fd69c3406f802663/CONTRIBUTING.md) welcomes reproductions/RCA from non-collaborators and limits PRs to collaborators. `MESSAGE.md` is the scoped follow-up. After a maintainer fix, rerun on its exact SHA and retain these historical observations alongside the new result.

# SDK #5341 final runtime evidence review

Review outcome: **accepted for the stated bounded regression claim**. The publication datasets support 6 PASS / 2 FAIL / 0 ERROR on both the released-package run and the pinned-main run. The earlier import-path traceability concern is resolved by actual resolved-path fields checked in all save/resume records. No matrix execution or external publication was performed by this reviewer.

## Evidence inspected

All 16 rows in `runs/release-published/results.json` and `runs/main-published/results.json`, and their individual `save.json`, `state.json` and `resume.json` files were inspected. Each aggregate observation equals its individual resume record. All captured child stdout/stderr streams are empty. The runner's expected-owner and known-bug oracles were read from `packet/reproduce.py`. Removing the two new provenance fields makes each publication aggregate identical to its corresponding reviewed `*-final` aggregate; the observed behavior and verdicts did not change.

More detailed serialized call/owner provenance was inspected for release `same-reset-single`, main `same-reset-sticky`, and main `unique-reset-single`: original handoff is `to_y`; the pending call is `record_effect(operation="approved-op")` with call ID `d1`; current agent, interruption, generated call item and function-tool approval share the saved owner reference.

## Results across both runs

Each entry below was checked in **both** final result sets. Operations are distinct: `approved-op` is the saved d1 invocation; `follow-up-op` is the new scripted d2 invocation.

| Case | Verdict | Actual effect owner(s) | New d2 approval interruption | Final output |
|---|---|---|---|---|
| same-preserve-single | PASS | Y: approved-op | Y / d2 | null |
| same-preserve-sticky | PASS | Y: approved-op, follow-up-op | none | done-y |
| same-reset-single | FAIL | X: approved-op | X / d2 | null |
| same-reset-sticky | FAIL | X: approved-op, follow-up-op | none | done-x |
| unique-preserve-single | PASS | Y: approved-op | Y / d2 | null |
| unique-preserve-sticky | PASS | Y: approved-op, follow-up-op | none | done-y |
| unique-reset-single | PASS | Y: approved-op | Y / d2 | null |
| unique-reset-sticky | PASS | Y: approved-op, follow-up-op | none | done-y |

All save phases have zero synthetic effects, hooks X=0 / Y=1, and d1 marked `executed=false`, `completed=false`. Single approvals serialize `approved=["d1"]`; sticky approvals serialize `approved=true` with a sticky scope. Duplicate-name references are `sub#2`; unique-name references name `sub-y`.

Thus the single failure does **not** show the follow-up call being authorized: it shows d1 executed by the wrong owner, followed by a correctly blocked new d2 call on that wrong owner. The sticky failure additionally shows the saved permanent decision applied to a fresh d2 call on X. Neither observation is a duplicate execution of the same operation: two differently named operations are intentionally used.

## Process and oracle checks

Every save/resume pair has different PIDs: 5/7, 11/13, 17/19, 23/25, 29/31, 35/37, 41/43, and 47/49 in each isolated run. The driver starts save and resume using separate `subprocess.run` calls; each child constructs its own agents, hooks, closures and scripted models. Old save-process closures cannot produce the resume effects. This is a real process-separated reconstruction check, not just an in-place hook reset.

Expected owner is the independent literal Y. Save setup verifies Y, the exact d1 tool and arguments, one interruption and zero effects before approving. The oracle compares actual closure-recorded owner/operation effects, public interruption owner/call ID, final output and last agent. It does not derive expected owner from SDK identity signatures. Private `_current_agent` is only supplementary diagnostic.

Resume models deliberately start with fresh d2 continuation responses; d1 comes from the saved SDK checkpoint. This avoids confusing a reset ScriptedModel queue with SDK replay of a new action. The exact wrong-owner characteristic is required by `--expect-known-bug`; errors or safe rejection cannot receive reproduced-bug success, and the contract verdicts remain FAIL.

## Pins and traceability

- Local SDK checkout HEAD: `125efa029b4bfd84238bd2c4fd69c3406f802663`; working tree clean.
- Identity source Git blob: `db0db775c9ec9877096a463c7c64e66290a7c533`, matching the primary GitHub currentness read.
- Identity source SHA-256: `c80b214b355f57fcbdaf4d13636ab7b3731da1e747363e445b472cef7b0de7ff`; matches **every** recorded save and resume in both runs.
- Reviewed runner SHA-256: `3293b055d1fd7c6dfd23f914ece888a19b88b058db37561e9b6c347e2ff8ca04`.
- Release publication aggregate SHA-256: `1d1d26363b54a274a79c1e163c57e9d9ff28a29a38d2393e526f5d204e7a16cb`.
- Main publication aggregate SHA-256: `9f3361352470338ad7c3c9f2f8a2e5d0c17dc42e6904d555e1ece9829238fc1b`.
- Both executions report Python 3.12.14 / Linux and distribution metadata 0.23.1.

In every release save/resume record, `sdk_import_root` resolves to `/workspace/scratch/5b0f6da052fa/sdk-5341-20261011/venv/lib/python3.12/site-packages/agents`. In every main save/resume record, it resolves to `/workspace/scratch/5b0f6da052fa/sdk-5341-20261011/sdk-source/src/agents`. Each `identity_source_path` names `_run_state_agent_identity.py` inside that same observed root. These fields come from the imported `agents.__file__`, not from the requested label or argument. All 32 child records have the expected roots and matching identity-source digest.

The main checkout/source pin and release package are now distinguished by observed import paths. The identity file happens to have identical bytes in the two runs; distribution metadata remains 0.23.1 in both and must still not be mistaken for the executing-source identity. No remaining blocking provenance issue for this packet's claim.

## Claim boundary

Supported: independent confirmation of digit50's publicly reported mutable-hooks/duplicate-name owner defect, with process-separated reconstructed objects and explicit single-versus-sticky controls, on the recorded package/source configuration. The six passing controls limit the finding to this fixture's name/counter interaction.

Not established: an unclean process crash, external provider effects, durable receiver state, adversarial exploitability, arbitrary graph compatibility, exactly-once execution or SDK-wide safety. The synthetic effects are child-local memory records. No SDK fix was proposed, the upstream checkout is unchanged, and no publication is authorized by this review.


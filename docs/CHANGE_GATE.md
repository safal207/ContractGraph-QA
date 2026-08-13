# Causal Security Change Gate

The change gate turns adversarial reachability into a repository-level regression check for pull requests and adapter/policy changes.

## Core question

> Did this change make a historically forbidden capability newly reachable, alter the historical forbidden definition to manufacture a pass, or manufacture a fix by shrinking the modeled search bound while the exact failing path still exists?

The gate reuses `contractgraph_qa.graph_delta` and `contractgraph_qa.path_replay`; it does not implement a second risk model.

## Repository configuration

`causal-security-gate.toml` is strict and repository-owned:

```toml
schemaVersion = 1

[[models]]
id = "adapter-terminal-reachability"
path = "scenarios/adversarial-adapter-fixture.json"
```

Model ids and paths must be unique. Paths must stay inside the repository and cannot contain traversal segments.

Once the gate configuration exists in the base commit, removing a configured model or changing its path is a blocking configuration drift. A newly configured model must still have base model bytes at the same path; otherwise the gate fails closed instead of silently treating the model as safe.

## Local runner

```bash
python tools/run_change_gate.py \
  --base-ref origin/main \
  --config causal-security-gate.toml \
  --repo-root .
```

The runner resolves `base-ref` and `HEAD` to full commit SHAs, reads the base model with `git show <base-sha>:<path>`, reads the proposed model from the checked-out worktree, and binds both commit SHAs plus both canonical model hashes into the result.

The CI trust boundary is stricter than this convenience mode: CI uses an exact clean candidate checkout and executes the gate engine only from the trusted base checkout.

No target execution, external RPC, or network request is performed by the gate after repository checkout.

## Trusted pull-request workflow

`.github/workflows/causal-security-gate.yml` uses `pull_request_target` so the workflow definition and enforcement code come from the base repository rather than from the candidate change.

The workflow creates two separate checkouts:

```text
trusted/
  exact pull-request base SHA
  gate engine + summary renderer + proof binder

candidate/
  exact pull-request head SHA
  treated as data only
```

The candidate checkout is never used as `PYTHONPATH`, never used as the working directory for Python execution, and no shell script, build step, repository executable, or imported module from `candidate/` is run by the gate. Candidate TOML/JSON/model files are parsed by the trusted base implementation.

Both checkouts use pinned `actions/checkout`, full history where needed, and `persist-credentials: false`. The workflow explicitly verifies the resolved base and head SHAs before evaluating the candidate. Permissions are limited to `contents: read`, and the workflow consumes no repository secrets.

The workflow writes `trusted/.cgqa/causal-security-gate.json`, renders a concise Markdown job summary using trusted code, binds the same machine result into a client proof using trusted code, uploads both evidence files, and only then enforces the gate decision. Blocking changes therefore retain machine-readable evidence.

Because `pull_request_target` workflow code must already exist on the default branch, the trust-hardened automation becomes the independent gate for pull requests after the workflow itself has first landed on `main`. The bootstrap PR that introduces the workflow must be reviewed and validated by the repository's existing CI before that trust anchor exists.

The job summary surfaces, where applicable:

- model id and gate status;
- gate reason;
- forbidden target capability;
- invariant ids;
- crossed or removed control boundaries;
- exact introduced transition sequence;
- exact historical fix replay and alternate-path result.

The evidence is deterministic for the same base/head/config/model bytes and is retained for 14 days by the repository workflow.

## Result semantics

Top-level statuses are:

- `pass` — no blocking delta and no boundary-only review condition;
- `review` — no forbidden capability became newly reachable, but a declared control boundary changed;
- `blocked` — at least one configured model fails closed.

Blocking reasons include:

- `new_forbidden_reachability`;
- `forbidden_definition_changed`;
- `fix_replay_not_verified`;
- `configured_model_removed`;
- `configured_model_path_changed`;
- `base_model_missing`;
- `head_model_missing`;
- `invalid_model`.

For valid model pairs, the embedded `delta` contains the exact shortest introduced forbidden path, invariant ids, crossed boundaries, impact, model hashes, and forbidden-definition changes.

The local runner exits `10` on `blocked` and `0` on `pass` or `review`.

## Exact historical fix replay

A non-blocking delta that says a formerly reachable forbidden capability is no longer reachable is treated as a machine-level fix claim. The gate does not accept that claim from the bounded search result alone.

For every such historical target, the gate reconstructs the exact shortest path from the base model and replays that transition sequence against the head model. The replay must return `fix_verified`: the historical target definition must remain forbidden, the exact path must be blocked, and a fresh alternate-path search must not reach the same target.

The replay evidence is embedded under each model's `fixReplays` entry and binds the historical model SHA-256 to the fixed model SHA-256. The GitHub job summary renders the same machine evidence without reinterpreting it.

This catches a subtle bound-manipulation failure mode. If a two-edge forbidden path remains structurally traversable but a PR merely reduces `maxDepth` from `2` to `1`, graph delta alone can report the target as no longer reachable within the new bound. Exact historical replay still traverses the old two-edge sequence, returns `failing_path_persists`, and the change gate blocks with `fix_replay_not_verified`.

## Client proof binding

The same `causal-security-gate.json` object can be attached to a client proof pack without recalculating its causal claims. The proof layer stores the machine result verbatim together with a canonical SHA-256 digest. Nested tampering or conflicting re-binding is rejected.

This digest is a content-integrity binding, not a standalone signer identity or external attestation. Provenance still comes from the reviewed repository/workflow context and the retained CI artifact.

## Bootstrap behavior

The first merge that introduces `causal-security-gate.toml` can compare configured model paths against a base commit that has no gate config yet; the result records `baselineConfigPresent: false`. After the config is present on `main`, later attempts to remove or rename configured entries are detected explicitly.

The trusted `pull_request_target` enforcement workflow itself similarly becomes available only after its first reviewed merge to the default branch.

## Safety boundary

The gate is bounded model evidence. A pass means the configured model did not introduce one of the declared blocking deltas within the modeled bound, and any machine-reported removal of a formerly reachable forbidden target survived exact historical replay. It is not proof that the production system is secure or that an unmodeled path cannot exist.

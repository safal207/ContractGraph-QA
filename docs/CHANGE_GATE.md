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

The runner resolves `base-ref` and `HEAD` to full commit SHAs, reads the base model with `git show <base-sha>:<path>`, reads the head model from the checked-out worktree, and binds both commit SHAs plus both canonical model hashes into the result.

No target execution, external RPC, or network request is performed after the repository checkout.

## Pull-request workflow

`.github/workflows/causal-security-gate.yml` runs the same gate automatically for every pull request.

The workflow checks out the exact pull-request head SHA with full git history, passes the exact pull-request base SHA to the runner, and keeps repository credentials disabled after checkout. The gate therefore compares the reviewed base commit with the actual proposed head rather than relying on GitHub's synthetic merge commit.

The workflow always writes `.cgqa/causal-security-gate.json`, renders a concise Markdown job summary, uploads the JSON as the `causal-security-gate-<PR number>` artifact, and only then enforces the gate decision. This preserves machine evidence even when the final decision is blocking.

The job summary surfaces, where applicable:

- model id and gate status;
- gate reason;
- forbidden target capability;
- invariant ids;
- crossed or removed control boundaries;
- exact introduced transition sequence;
- exact historical fix replay and alternate-path result.

The artifact is deterministic for the same base/head/config/model bytes and is retained for 14 days by the repository workflow.

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

## Bootstrap behavior

The first PR that introduces `causal-security-gate.toml` can still compare configured model paths against the supplied base commit even though the base commit has no gate config yet. The result records `baselineConfigPresent: false`. After the config is merged once, later attempts to remove or rename configured entries are detected explicitly.

## Safety boundary

The gate is bounded model evidence. A pass means the configured model did not introduce one of the declared blocking deltas within the modeled bound, and any machine-reported removal of a formerly reachable forbidden target survived exact historical replay. It is not proof that the production system is secure or that an unmodeled path cannot exist.

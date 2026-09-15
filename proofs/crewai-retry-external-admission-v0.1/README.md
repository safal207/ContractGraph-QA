# CrewAI retry duplication — External Proof Admission v0.1

**Status: ADMITTED (BOUNDED).** ContractGraph-QA independently inspected the published
`mstevens843/crashpoint` evidence bundle for the CrewAI retry experiment, verified the
artifact hashes, and recomputed the raw 90-trial receipts.

This is an **evidence-admission result**, not a second execution of the experiment.

## Frozen source

| Field | Frozen value |
|---|---|
| Producer repository | `mstevens843/crashpoint` |
| Publication commit | `606893ebb353df5dab3ac68738051eb5fbb7286e` |
| Published evidence | `evidence/crewai_retry.json` |
| Git blob SHA-1 | `13f35572ebd0d0f56f57e893c62e38132793f4b1` |
| Evidence SHA-256 | `0d2eb2cf3c835b022298d52e807f7d0328b023d5c4d88a669af5c1965f6b56d1` |
| Evidence bytes | `581,573` |
| GitHub Actions run | `35008887794` |
| Artifact | `10411829570` |
| Recorded receipt | `cp1_a7376a114c8eeb06eb7042039a8557b00630fde0cf946788d8be9a2cdd22541d` |
| Recorded crashpoint commit | `a08ef36f435b68343befa1c39681c1b4691302af` |
| CrewAI source | `1.15.21 @ a8d330de00812e52356f32d32c715b86392bfd41` |

The publication commit and the experiment commit are intentionally kept separate.
The publication workflow preserves existing evidence; its own manifest says the experiment
was **not** rerun in that publication job.

## Independent admission checks

The GitHub Actions artifact was downloaded and its files were hashed independently:

| File | Bytes | SHA-256 |
|---|---:|---|
| `evidence/crewai_retry.json` | 581,573 | `0d2eb2cf3c835b022298d52e807f7d0328b023d5c4d88a669af5c1965f6b56d1` |
| `results/11-crewai-retry-prediction.json` | 2,437 | `94bb09e0c71f23cda96b985b495b765439b1e4a3ce1ebe40d573c4171e5aa1b4` |
| `results/11-crewai-retry.md` | 8,735 | `1e0ecda17afe903404811f0d241bb34f3e3f763c8fc0d520f7dd837177d855d0` |
| `manifest.json` | 2,099 | `7e2b121d044d23ef727fb2fa348d9698db1cd35edcd6c275a2686fc69ffa6129` |

The first three hashes match the producer's publication manifest.

The raw evidence was then recomputed without relying on its aggregate summary:

| Case | Trials | Tool attempts | Effects | Verdict |
|---|---:|---:|---:|---|
| `clean` | 30/30 | 1 | 1 | `EXACTLY_ONCE` |
| `pre_effect` | 30/30 | 2 | 1 | `EXACTLY_ONCE` |
| `post_effect` | 30/30 | 2 | 2 | `DUPLICATED` |

For every `post_effect` row the raw event order is:

`tool_enter(attempt 1) -> effect_ack(attempt 1) -> injected_failure(after_effect_before_tool_return) -> tool_enter(attempt 2) -> effect_ack(attempt 2) -> tool_return`

For every trial:

- `same_process = true`;
- `fresh_process = false`;
- `external_retrigger = false`;
- runtime-reported `agent_retries = 0`.

So the admitted claim is narrow: **inside the recorded CrewAI 1.15.21 synchronous
`ToolUsage._use` retry path, an unguarded external effect that commits before the tool raises
can be performed again by the built-in retry.**

## Why this is useful

This is the first ContractGraph-QA record that treats a third party's published execution
evidence as an input object rather than requiring ContractGraph-QA to own the original run.

The trust transition is:

`external source -> immutable pin -> byte integrity -> receipt recomputation -> bounded claim -> non-claims -> next experiment`

That is the minimum shape needed for a proof platform where one independently inspectable
proof becomes an input to the next trust decision without silently inheriting stronger claims.

## Claim ceiling

Admission does **not** establish:

- that ContractGraph-QA reran the 90 trials;
- the original execution time or a clean original checkout;
- process-crash or fresh-worker recovery behavior;
- checkpoint/resume behavior;
- real-LLM/provider behavior;
- idempotency-guard behavior;
- host power-loss durability of the ledger;
- exactly-once execution for CrewAI generally.

## Next boundary

The next experiment should connect this observed duplication boundary to authorization:

`stable action identity -> fresh authorization -> one-use permit -> dispatch -> external receipt/read-back`

The key question is whether persisted identity can survive retry/recovery while **persisted
state is never treated as fresh authority to execute again**.

## Files

- [`admission.json`](./admission.json) — machine-readable admitted subject, claim and non-claims.
- [`report.json`](./report.json) — independent recomputation summary.
- [`verify_admission.py`](./verify_admission.py) — stdlib verifier for the pinned raw evidence.

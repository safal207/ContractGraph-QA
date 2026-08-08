# ContractGraph-QA Outreach

Use these as short starting points. Keep the first message about the buyer's risk, not about the tool architecture.

## Founder / protocol team

Hi — I’m running a small Smart Contract QA pilot focused on stateful bugs that are easy to miss in function-by-function testing: role transitions, release/refund sequences, accounting invariants, deadlines, and terminal states.

I model the contract as a reachable state graph, search bounded transaction paths in Foundry, and return the shortest reproducible path for each violated invariant plus a verifiable evidence bundle.

I’m offering a **$200 fixed pilot** for one small authorized contract/feature, up to 5 prioritized invariants, with one retest pass. I can send a repository-owned sample showing exactly what the deliverable looks like.

## Solidity developer

Hi — if you have a contract that is already implemented but you want stronger regression evidence before audit/release, I can take one narrow slice and turn its business rules into state/invariant tests.

The output is not just “test failed”: it includes the minimal action sequence, pre/post states, coverage status for every declared invariant, and a deterministic evidence bundle you can keep with the fix.

Current pilot: **$200 fixed**, one small authorized scope, up to 5 invariants + one retest.

## Audit-readiness lead

Hi — I’m testing a narrow audit-readiness service for smart contracts: explicit invariant model → bounded Foundry state exploration → reproducible findings → retest evidence.

It is designed to complement, not replace, a security audit. The useful part is that unresolved coverage stays explicitly `inconclusive`, while violations carry a shortest replayable path.

I’m taking small authorized pilots at **$200 fixed**. If useful, I can share the complete sample engagement and evidence format first.

## Follow-up after interest

Great. For the pilot I need only:

- repo/source;
- exact contract or feature in scope;
- authorization boundary;
- expected roles/business rules;
- ideally the 3–5 properties you most want protected.

I’ll turn that into a reviewed manifest of actors/actions/state/invariants, run the bounded search, and deliver findings + coverage + a verifiable evidence ZIP. If a fix is made inside the pilot scope, one retest is included.

## Proof-first reply

Here is the key distinction in the sample: one search checks three invariants and returns three different evidence states — one real violation with the shortest path, one `not_found_within_bound`, and one `inconclusive`.

That matters because the tool does not turn incomplete coverage into a fake PASS. The bundle can also be independently reopened and verified from the CLI.

## One-line positioning

I test smart contracts as **stateful financial systems**, turning business rules into actor/state/invariant models, Foundry regression evidence, shortest reproducible failure paths, and retestable QA artifacts.

## Qualification boundary

Do not pitch unauthorized testing. Before active testing of a non-local target, confirm written scope or a clearly applicable bounty/safe-harbor program. A public contract address alone is not authorization.

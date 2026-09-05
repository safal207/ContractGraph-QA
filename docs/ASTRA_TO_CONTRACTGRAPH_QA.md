# Astra-inspired hardening map

This note translates the public [OpenAI Path to Astra](https://openai.com/index/path-to-astra/)
principles into controls that fit ContractGraph-QA. It is an engineering map,
not a claim that this repository has Astra-level capability or safeguards.

| Astra lesson | ContractGraph-QA control | Current state |
| --- | --- | --- |
| Capability must be measured with realistic evaluations | Run the five-contract matrix through deterministic, exact-name tests and preserve snapshots | In place |
| Prevent both malicious use and unauthorized model actions | Keep the public core read-only and discovery graphs separate from the Action Guard policy graph | In place |
| Monitoring must be able to stop an action | Enforce preflight and stop controls in a separate isolated runner | Roadmap |
| Evidence must survive review | Hash saved inputs, outputs, exact subject identity, and normalized evidence | Partly in place |
| Tool identity must not be spoofable by path resolution | Verify executable identity inside the external runner, not from self-declared trace fields | Roadmap |
| A single monitor is not independent proof | Require an authenticated witness from a different actor and failure domain | Roadmap |
| Sandboxing claims need real isolation | Keep execution outside the core until OS and network containment are independently tested | Explicit boundary |
| Red-team against bypasses and honeypots | Add negative controls for canary paths/networks, retry-after-denial, and exact command mutation | In place |
| Release decisions should tolerate safe friction | Preserve `pass` / `hold` / `fail` separately from vulnerability severity or bounty eligibility | In place |

The practical next milestone is exact-subject verification for saved evidence.
Execution comes later, only through a separately reviewed OS/network-isolated
runner with an external replay ledger and authenticated witness.

Do not collect or expose hidden model reasoning as evidence. The useful analogue
of Astra's monitoring is a minimal, replayable action trace: who proposed the
command, what exact bytes were authorized, what process ran, and what an
independent observer verified. See the [Astra-6 roadmap](ASTRA6_ROADMAP.md) for
the deliberately small implementation sequence.

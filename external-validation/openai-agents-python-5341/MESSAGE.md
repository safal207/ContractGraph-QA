Thanks @digit50 for the report. I independently reproduced this on `openai-agents==0.23.1` and main `125efa029b4bfd84238bd2c4fd69c3406f802663`, adding genuinely separate save/resume processes and fresh Agent/hook/tool/model instances.

The 8-case matrix varies same/unique names, preserved/reset hook counters, and single/sticky approval. Both subjects return **6 passing controls and 2 owner failures**, with no runtime errors:

- Same names + reset hooks + single approval: X executes the saved operation approved for Y; the new call d2 correctly pauses, but under X.
- Same names + reset hooks + sticky approval: X executes both the saved operation and a new follow-up operation.
- Preserved-hook and unique-name controls keep both execution and approval ownership on Y.

The resumed scripted provider emits a **new** operation/call ID, so this is not a reset fake-model queue repeating the saved request. Assertions use actual closure-owned memory effects; the private current-agent field is diagnostic only. Public serialized state is not edited.

Reproducible packet, exact observations, dependency freeze and bounded claims: https://github.com/safal207/ContractGraph-QA/tree/validation/openai-sdk-5341-20261011/external-validation/openai-agents-python-5341

This corroborates the already reported mechanism; it does not establish real external effects, unclean-crash durability, exploit severity, or general SDK safety. No runtime patch is proposed. Would this matrix be useful as regression coverage for a maintainer fix, including whether ambiguous restoration should reject rather than remap?

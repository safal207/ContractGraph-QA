# Attribution

The RS1, RS2, and RS3 property names and definitions are adapted from:

> Nasopoulos, V. (2026). *Recovery safety: persist inputs, or persist outcomes.*
> https://github.com/vasilisnasopoulos/recovery-safety-property

Pinned source commit: `22e34841226c41d80c8646b33f1439a87e8549af`.

The source property is licensed under CC BY 4.0. This benchmark preserves attribution and implements a bounded executable mapping; it does not claim authorship of the underlying property or equivalence to the related TLA+/TLAPS proof.

The live crash-injection shape is adapted from the public minimal reproduction in `langchain-ai/langgraph#8039`. ContractGraph-QA adds semantic logical-action identity, separate attempt/admission records, receiver-dedup control, structured observations, and the RS1–RS3 evaluator.

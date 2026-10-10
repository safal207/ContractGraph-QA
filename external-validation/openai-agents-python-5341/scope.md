# SDK #5341 independent validation scope

- Required behavior: after public RunState JSON serialization and restoration on a newly constructed agent graph, a pending approval for synthetic owner Y must execute Y's approved operation, never X's operation. Single-call approval must not execute a new operation; sticky approval may authorize the new operation only for Y.
- Compatibility boundary: released openai-agents 0.23.1 plus exact upstream main 125efa029b4bfd84238bd2c4fd69c3406f802663; public Agent, AgentHooks, Runner, RunState, function_tool and ScriptedModel. No runtime fix or persisted schema change.
- Included controls: same/unique agent names, restored/default hook counters, single/sticky approval. Save and resume use separate subprocesses and synthetic memory-only effect counters. Continuation scripts emit a NEW operation, because ScriptedModel does not persist its own provider queue through application restart.
- Unsupported/non-goals: live model/API, real privileged tools, unclean crash, distributed persistence, exactly-once external effects, comprehensive SDK safety, new undisclosed root causes. No serialized state tampering; only the supported application graph is rebuilt.
- Alternative: unique agent names are the positive control, not a universal mitigation claim.
- Attribution: digit50 reported the public finding; Alexey Safonov/safal207 contributes independent execution and new graph/process/single-vs-sticky controls, with AI-assisted implementation and review.
- Independent oracle: literal expected owner Y plus per-operation counts; it does not recompute expectations using SDK identity helpers. Last-agent/approval-owner observations are diagnostic; callback side effects determine the boundary violation.
- No SDK checkout edits. The validation packet lives outside the upstream repository. SDK full test stack is not claimed or required for this external investigation packet.

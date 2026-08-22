# Agent Runtime Conformance Matrix

`Witness Projection Conformance v0.1` measures one narrow property: whether an exact recorded witness sequence can be projected deterministically, append-only, and replayably without ambient time/config creating new facts.

Scores below are **boundary-specific**. They are not overall framework rankings.

| Runtime | Pinned source | Boundary type | Result | Key interpretation |
|---|---|---|---:|---|
| CrewAI | `crewAIInc/crewAI@f4731f5025f861c78e3af0487cc80bf5e7c64782` | native tool-event evidence vocabulary | **6/8** | Current event vocabulary cannot represent explicit absence + bound deadline at the measured boundary. |
| LangGraph | `langchain-ai/langgraph@f09cfe8ffc1eeffd68f4b628ed69c30f7cad229f` | hosted state/checkpoint boundary | **8/8** | User reducer state and checkpoint `channel_values` can preserve the complete witness sequence. |
| AutoGen | `microsoft/autogen@027ecf0a379bcc1d09956d46d12d44a3ad9cee14` | hosted JSON-serializable saved-state boundary | **8/8** | `save_state()/load_state()` can carry the complete witness set through replay. |
| Microsoft Agent Framework | `microsoft/agent-framework@d9d3fb6252f7ae9e7f8104edce7266f0782a813c` | framework-native workflow checkpoint hosting domain state | **8/8** | `WorkflowCheckpoint.state` can preserve explicit witnesses while checkpoint timestamp/lineage remain non-decision metadata. |

## The eight checks

1. deterministic across evaluator time;
2. explicit absence enables transition;
3. replay stability;
4. prefix stability;
5. non-monotone state over monotone evidence;
6. deadline bound to evidence;
7. missing deadline fails closed;
8. projection does not mutate evidence.

## Comparison discipline

The matrix deliberately distinguishes **native evidence vocabulary** from **hosted state/checkpoint capability**.

A `6/8` native-event result is not directly equivalent to an `8/8` hosted-state result. The useful question is where each runtime exposes a boundary capable of preserving the facts required for deterministic replay.

The matrix therefore answers:

> At this pinned source boundary, can the runtime represent and replay the complete witness contract without inventing facts from ambient time?

It does not answer which framework is better overall, which framework has stronger security, or whether arbitrary applications built on a conformant substrate are themselves conformant.

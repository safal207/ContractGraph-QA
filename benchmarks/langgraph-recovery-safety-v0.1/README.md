# LangGraph recovery safety v0.1

Executable RS1–RS3 crash/recovery benchmark for [`langchain-ai/langgraph#8039`](https://github.com/langchain-ai/langgraph/issues/8039).

The committed baseline maps the issue's two forced interleavings onto the recovery-safety property from [`vasilisnasopoulos/recovery-safety-property`](https://github.com/vasilisnasopoulos/recovery-safety-property) at commit `22e34841226c41d80c8646b33f1439a87e8549af`.

## Committed baseline

Pinned runtime profile:

```text
langgraph==1.2.4
langgraph-checkpoint-sqlite==3.1.0
```

`3.1.0` is a contemporaneous reproducibility pin, not a claim about the reporter's exact installed SQLite-checkpointer version.

Result from the public forced-interleaving observations:

```text
RS1 Input determinism      FAIL
RS2 Crash independence     FAIL
RS3 At-most-once identity  FAIL
```

The evaluator requires equal explicit graph input, equal ordered logical-action plan, and the same declared crash boundary before two observations are comparable. It also recomputes every action ID and state digest rather than trusting summary fields.

See [`observations.json`](observations.json) and [`result.json`](result.json).

## Live probe

The live probe adds a semantic action identity and separates node attempts from receiver admissions:

```bash
python -m pip install -e . \
  "langgraph==1.2.4" \
  "langgraph-checkpoint-sqlite==3.1.0"

python -m tools.langgraph_recovery_safety_probe \
  writes-delay --receiver append --expect duplicate

python -m tools.langgraph_recovery_safety_probe \
  put-delay --receiver append --expect exactly-once

python -m tools.langgraph_recovery_safety_probe \
  writes-delay --receiver dedup --expect deduped-reexecution
```

The third command is the RS3 control: the runtime may re-execute the node, while a receiver that honours the stable semantic identity admits the external action once.

The dedicated GitHub Actions workflow runs the same probe against the historical baseline and a separately pinned publication-time comparison profile. Each job uploads the crash frontier, attempts, admissions, and RS1–RS3 report.

## Scope

This benchmark is bounded evidence for the declared fault set. It does not prove that LangGraph, SQLite, or any application provides universal exactly-once execution. RS3 cannot be closed by a runtime alone; the external receiver must recognise and honour the repeated identity.

Full design and claim boundary: [`../../docs/LANGGRAPH_RECOVERY_SAFETY.md`](../../docs/LANGGRAPH_RECOVERY_SAFETY.md).

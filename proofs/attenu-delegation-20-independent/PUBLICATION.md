# Publication transition

Spine: `attenu-delegation-20-2026-09-06`.

On 2026-09-06, after receiving the completed local result and being asked specifically whether to publish the prepared PR, the user replied **Go**. This authorizes publishing the proof branch and PR and checking its CI. It does not authorize merging or sending a separate message to Rafaela.

Ordinary HTTPS git push had no credentials in this environment. Publication therefore uses the authenticated GitHub connector's Git-data operations. The connector creates new commit metadata; the original local SHA is not represented as a public commit.

| Identity | Value |
|---|---|
| Base, unchanged | `f861b934d77e64fd35f768e2a33bb4a00963bc19` |
| First local verifier/run commit | `921173318176165a0d16e8b81c6913dbda4aa472` |
| Published verifier/run snapshot | `cb080a795f26bd1c0417d32cdd297960511cad88` |
| Tree shared by those two commits | `7bdc14c6d88bd2fee56d3b3a2d5da13972ebad7d` |
| Completed local evidence commit before publication | `0b360ecb986adf775b9e234e04068d1d8f163908` |

GitHub returned exactly the expected tree hash for the original twenty-eight-file first-run addition. The published verifier snapshot therefore contains the same verifier, harness, plan, source pins, original input bytes and first report as the local first run.

Publication metadata changes the README, PR body, artifact metadata and this transition record. **The semantic verifier, scorer, frozen corpus and both generated reports are unchanged.** Their SHA-256 identities remain in the report and source manifest. Historical PLAN.md, collection.json and validation.json stay historical; their earlier NOT_RUN states are not rewritten.

This document records publication preparation and authority. The PR's actual head, check runs and review states are live GitHub evidence; no successful hosted run or human approval is predeclared here. A later green CI result is evidence for its own exact head and does not grant merge authority or strengthen the conformance claim.

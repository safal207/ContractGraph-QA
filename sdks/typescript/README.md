# ContractGraph-QA interop report adapter for TypeScript and JavaScript

This dependency-free package validates a completed `cgqa-liminalqa-v0.1`
conformance report. It pins all 14 cases, both producer contracts, the suite
digest, and the non-authority boundary. Ambiguous JSON, unknown fields, suite
drift, missing cases, side-effect claims, and `UNSAFE_ACCEPTED` are rejected.

After the package is published:

```bash
npm install --save-dev @contractgraph-qa/interop-report
cgqa liminalqa-conformance | npx cgqa-report-validate
```

Library use:

```ts
import {readFile} from "node:fs/promises";
import {validateConformanceReportJson} from "@contractgraph-qa/interop-report";

const summary = validateConformanceReportJson(await readFile("report.json", "utf8"));
console.log(summary.passed); // 14
console.log(summary.mayAuthorizeAction); // false
```

Until registry publication, install from a repository checkout with
`npm install ./sdks/typescript`.

A valid summary is conformance evidence only. It never grants permission to
run a candidate or perform an external action.

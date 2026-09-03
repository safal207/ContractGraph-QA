# ContractGraph-QA इंटरऑपरेबिलिटी: पाँच मिनट की गाइड

[English](../en/GETTING_STARTED.md) · [简体中文](../zh-CN/GETTING_STARTED.md) · हिन्दी · [Español](../es/GETTING_STARTED.md) · [العربية](../ar/GETTING_STARTED.md)

ContractGraph-QA, LiminalQA और PythiaLabs मिलकर stateful और high-risk agent
workflows के लिए evidence-first safety stack बनाते हैं। हर project अपना verdict
authority बनाए रखता है; adapters केवल सख़्त JSON evidence साझा करते हैं। कोई
report अपने-आप कार्रवाई की अनुमति नहीं बनता।

## हर project की भूमिका

| Project | भूमिका | क्या दावा नहीं करता |
|---|---|---|
| ContractGraph-QA | सीमित state/action search, exact-subject evidence, replay input | पूर्ण correctness या action authority |
| LiminalQA | bi-temporal QA context और non-authoritative replay/debt candidates | verified CGQA finding या LTP continuity verdict |
| PythiaLabs | external evidence को advisory context मानकर नया deterministic authorization gate | केवल external evidence से `ALLOW` |

## Pinned contract चलाएँ

ContractGraph-QA checkout में:

```bash
python -m pip install .
cgqa liminalqa-conformance > report.json
```

सफल report में सभी 14 golden और fail-closed vectors होते हैं:

```json
{"status":"PASS","counts":{"total":14,"passed":14,"failed":0},"authority":{"classification":"conformance_evidence_only","mayAuthorizeAction":false}}
```

पूरी report suite SHA-256, दोनों producer contracts, हर case ID और input digest,
`sideEffectExecuted=false` और claim boundary को भी pin करती है।

## अपनी programming language में validate करें

Repository में TypeScript/JavaScript, Go, Java/JVM और .NET के thin adapters हैं।
ये native runner के evidence को validate करते हैं; CGQA/LiminalQA verdict logic
को दोबारा implement नहीं करते।

```bash
node sdks/typescript/bin/cgqa-report-validate.js report.json

cd sdks/go && go run ./cmd/cgqa-report-validate ../../report.json

mvn -q -f sdks/java/pom.xml exec:java -Dexec.args=report.json

dotnet run --project sdks/dotnet/src/ContractGraphQA.Interop.Cli -- report.json
```

Package coordinates और local references के लिए [SDK release guide](../../SDK_RELEASE.md)
देखें। Python ContractGraph-QA reference runner है, Rust LiminalQA native runner
है और Elixir PythiaLabs native runner है।

## Fail-closed सीमा

हर adapter duplicate JSON keys, unknown critical fields, pin drift, missing या
duplicate cases, `UNSAFE_ACCEPTED`, `mayAuthorizeAction=true` और किसी भी reported
side effect को अस्वीकार करता है। Input सीमा 1 MiB है। Validation network call,
candidate execution, database write या target-system action नहीं करती।

Valid report केवल pinned synthetic vectors पर conformance दिखाती है। वास्तविक
action से पहले exact subject को current evidence पर replay करें और सक्रिय Pythia
या operator authorization gate चलाएँ। `PASS` कभी अनुमति नहीं है।

पूरा protocol: [ContractGraph-QA ↔ LiminalQA interop](../../LIMINALQA_INTEROP.md)।

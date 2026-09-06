# ContractGraph-QA interop report adapter for Go

The Go module validates the exact `cgqa-liminalqa-v0.1` passing report and
fails closed on duplicate JSON keys, unknown fields, pin drift, missing cases,
side-effect claims, or authority escalation.

The tagged v0.1.0 module is public:

```bash
go get github.com/safal207/ContractGraph-QA/sdks/go@v0.1.0
go install github.com/safal207/ContractGraph-QA/sdks/go/cmd/cgqa-report-validate@v0.1.0
cgqa liminalqa-conformance | cgqa-report-validate
```

Library use:

```go
summary, err := interop.ValidateJSON(reportBytes)
if err != nil {
    return err
}
fmt.Println(summary.Passed, summary.MayAuthorizeAction) // 14 false
```

A valid summary is evidence only and cannot authorize an external action.

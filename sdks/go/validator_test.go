package interop

import (
	"encoding/json"
	"os"
	"testing"
)

func fixture(t *testing.T) []byte {
	t.Helper()
	raw, err := os.ReadFile("../testdata/pass-report.json")
	if err != nil {
		t.Fatal(err)
	}
	return raw
}

func mutate(t *testing.T, raw []byte, change func(map[string]any)) []byte {
	t.Helper()
	var report map[string]any
	if err := json.Unmarshal(raw, &report); err != nil {
		t.Fatal(err)
	}
	change(report)
	result, err := json.Marshal(report)
	if err != nil {
		t.Fatal(err)
	}
	return result
}

func TestValidateJSONAcceptsPinnedReport(t *testing.T) {
	summary, err := ValidateJSON(fixture(t))
	if err != nil {
		t.Fatal(err)
	}
	if !summary.Valid || summary.Passed != 14 || summary.MayAuthorizeAction {
		t.Fatalf("unexpected summary: %#v", summary)
	}
}

func TestValidateJSONRejectsSafetyDrift(t *testing.T) {
	tests := map[string]func(map[string]any){
		"authority escalation": func(report map[string]any) { report["authority"].(map[string]any)["mayAuthorizeAction"] = true },
		"suite drift": func(report map[string]any) { report["suiteSha256"] = "drift" },
		"count mismatch": func(report map[string]any) { report["counts"].(map[string]any)["passed"] = 13 },
		"reported side effect": func(report map[string]any) { report["results"].([]any)[0].(map[string]any)["sideEffectExecuted"] = true },
		"unsafe acceptance": func(report map[string]any) { report["results"].([]any)[1].(map[string]any)["observedSemantics"] = "UNSAFE_ACCEPTED" },
		"missing case": func(report map[string]any) { report["results"] = report["results"].([]any)[:13] },
		"unknown root field": func(report map[string]any) { report["authorization"] = "ALLOW" },
	}
	for name, change := range tests {
		t.Run(name, func(t *testing.T) {
			if _, err := ValidateJSON(mutate(t, fixture(t), change)); err == nil {
				t.Fatal("expected validation failure")
			}
		})
	}
}

func TestValidateJSONRejectsDuplicateKeys(t *testing.T) {
	raw := fixture(t)
	ambiguous := append([]byte(`{"schema":"duplicate",`), raw[1:]...)
	if _, err := ValidateJSON(ambiguous); err == nil {
		t.Fatal("expected duplicate-key rejection")
	}
}

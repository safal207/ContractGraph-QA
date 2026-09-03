// Package interop validates pinned ContractGraph-QA/LiminalQA conformance evidence.
package interop

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"regexp"
	"strconv"
	"strings"
)

const (
	MaxReportBytes = 1_048_576
	reportSchema   = "org.contractgraph-qa.liminalqa-interop-conformance-result.v0.1"
	suiteID        = "cgqa-liminalqa-v0.1"
	suiteVersion   = "0.1.0"
	suiteSHA256    = "562e2f9ae699f001b9ccf1b2b9f6dd30c435d53d668b5fd9a04ca15ca1e4faac"
	claimBoundary  = "Synthetic conformance verifies adapter behavior only for these pinned fixtures and mutations. It does not verify a production system, prove security or completeness, authorize an action, or replace independent replay against the exact subject."
)

var safeID = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9._:-]{0,199}$`)

type contractPin struct {
	artifactSchema  string
	artifactProfile string
	ownerRepository string
	producerCommit  string
	schemaSHA256    string
	fixtureSHA256   string
}

var contractPins = map[string]contractPin{
	"cgqa-evidence": {
		artifactSchema:  "org.contractgraph-qa.liminalqa-evidence.v0.1",
		artifactProfile: "org.contractgraph-qa.bounded-invariant-evidence.v0.1",
		ownerRepository: "safal207/ContractGraph-QA",
		producerCommit:  "bdf7ced074e3a7baf57cf89ac68be9674bd76a02",
		schemaSHA256:    "53b0b4a0b1f4d77de26b8be9dbb90006ea0bd30c5cd3960a2f3e7d44d9664184",
		fixtureSHA256:   "e1d5a14c5c1b75e2cfffaf87bf526fd61e141a0c5b7828de4f275e9792fda3ce",
	},
	"liminal-candidates": {
		artifactSchema:  "org.liminalqa.cgqa-candidates.v0.1",
		artifactProfile: "org.liminalqa.non-authoritative-candidate-seeds.v0.1",
		ownerRepository: "safal207/LiminalQAengineer",
		producerCommit:  "db9c85f678aafd6e28487e0679a9fb6c3ebfb0c3",
		schemaSHA256:    "896e32921d41925a976fef5d0ba561a08bd1f2265a08bc9ccf5065a3238a4f60",
		fixtureSHA256:   "60b794934959c30f9957d0e54de83d7760ac38b618b0676603d721daa8ef11d3",
	},
}

type casePin struct {
	contract          string
	category          string
	expectedSemantics string
	inputSHA256       string
}

var casePins = map[string]casePin{
	"cgqa-evidence-golden":                     {"cgqa-evidence", "golden", "VALID_NON_AUTHORIZING", "e1d5a14c5c1b75e2cfffaf87bf526fd61e141a0c5b7828de4f275e9792fda3ce"},
	"cgqa-evidence-authority-escalation":        {"cgqa-evidence", "authority_escalation", "INVALID_BLOCKED", "33eb3122738032c3ebc1043f5058bc7a9cc469c6ecff8ad0a602aaa3a80067ce"},
	"cgqa-evidence-count-mismatch":              {"cgqa-evidence", "semantic_mismatch", "INVALID_BLOCKED", "3f348306ba20fdb780b662ec3aadbdf8d1a805a1d81cb2eb66103824e9f8b95f"},
	"cgqa-evidence-temporal-inversion":          {"cgqa-evidence", "temporal_inversion", "INVALID_BLOCKED", "dbc7d64eda4aeb497bf360e10335896b3f9b4316973306e37a8a21134cc85ba8"},
	"cgqa-evidence-unknown-authority-field":      {"cgqa-evidence", "unknown_field", "INVALID_BLOCKED", "49d7eab11be2a4fc5b90776a9822156573ef5753bff25e674629fdb8e742edea"},
	"cgqa-evidence-unsafe-causal-parent":         {"cgqa-evidence", "unsafe_identifier", "INVALID_BLOCKED", "e50dfe383bbd2577b72dba043bbe129b6370b81ec8226d6fa9ed206bf6bf51af"},
	"cgqa-evidence-duplicate-schema-key":         {"cgqa-evidence", "ambiguous_json", "INVALID_BLOCKED", "6ff810788c268a93af16daa7a814cfe84616542951de92be8dbe79aabf3d41c9"},
	"liminal-candidates-golden":                  {"liminal-candidates", "golden", "VALID_NON_AUTHORIZING", "60b794934959c30f9957d0e54de83d7760ac38b618b0676603d721daa8ef11d3"},
	"liminal-candidates-authority-escalation":    {"liminal-candidates", "authority_escalation", "INVALID_BLOCKED", "261570efc9e6c13d46686a6f5941ee7d39db620c4603cf30a64e0f0baae3abff"},
	"liminal-candidates-unknown-authority-field": {"liminal-candidates", "unknown_field", "INVALID_BLOCKED", "1a3841322a8dae89e793f92cedcf341c5fafa4a70e308426d76f674434291941"},
	"liminal-candidates-missing-independent-replay": {"liminal-candidates", "verification_weakening", "INVALID_BLOCKED", "8030649160511f62065f4ba33d703fb4dcbf96bc25480d8fa9c7d4e85d715423"},
	"liminal-candidates-debt-mismatch":           {"liminal-candidates", "semantic_mismatch", "INVALID_BLOCKED", "172a1567897dc4a78deaf2c9f50bc6634e59d2d671ab23d414ca8b4a089f8185"},
	"liminal-candidates-unsafe-causal-parent":    {"liminal-candidates", "unsafe_identifier", "INVALID_BLOCKED", "61b8e74f52248e50fc90e0765b6cc0449ea5b588cb6aa525d148dcb9ac447960"},
	"liminal-candidates-duplicate-schema-key":    {"liminal-candidates", "ambiguous_json", "INVALID_BLOCKED", "9bf53f54b15a2eb09731c28dfffc5ba39f7c04b0d5fa4d076f300f8107ae2d40"},
}

// Implementation identifies the native runner that produced the report.
type Implementation struct {
	Name     string `json:"name"`
	Version  string `json:"version"`
	Language string `json:"language"`
}

// Summary is returned only after every pinned invariant passes.
type Summary struct {
	Valid              bool           `json:"valid"`
	SuiteID            string         `json:"suiteId"`
	Implementation     Implementation `json:"implementation"`
	Passed             int            `json:"passed"`
	MayAuthorizeAction bool           `json:"mayAuthorizeAction"`
	ClaimBoundary      string         `json:"claimBoundary"`
}

func invalid(path, message string) error {
	return fmt.Errorf("%s: %s", path, message)
}

func object(value any, path string) (map[string]any, error) {
	result, ok := value.(map[string]any)
	if !ok {
		return nil, invalid(path, "must be an object")
	}
	return result, nil
}

func array(value any, path string) ([]any, error) {
	result, ok := value.([]any)
	if !ok {
		return nil, invalid(path, "must be an array")
	}
	return result, nil
}

func exactKeys(value map[string]any, expected []string, path string) error {
	if len(value) != len(expected) {
		return invalid(path, "has an unexpected or missing field")
	}
	for _, key := range expected {
		if _, ok := value[key]; !ok {
			return invalid(path, "is missing field "+key)
		}
	}
	return nil
}

func text(value any, path string) (string, error) {
	result, ok := value.(string)
	if !ok || strings.TrimSpace(result) == "" {
		return "", invalid(path, "must be a non-blank string")
	}
	return result, nil
}

func equalText(value any, expected, path string) error {
	actual, err := text(value, path)
	if err != nil {
		return err
	}
	if actual != expected {
		return invalid(path, "does not match the v0.1 pin")
	}
	return nil
}

func equalInt(value any, expected int, path string) error {
	number, ok := value.(json.Number)
	if !ok {
		return invalid(path, "must be an integer")
	}
	actual, err := strconv.Atoi(number.String())
	if err != nil || actual != expected {
		return invalid(path, fmt.Sprintf("must equal %d", expected))
	}
	return nil
}

func equalBool(value any, expected bool, path string) error {
	actual, ok := value.(bool)
	if !ok || actual != expected {
		return invalid(path, fmt.Sprintf("must equal %t", expected))
	}
	return nil
}

func scanValue(decoder *json.Decoder, depth int, path string) error {
	if depth > 64 {
		return invalid(path, "maximum nesting depth exceeded")
	}
	token, err := decoder.Token()
	if err != nil {
		return invalid(path, "invalid JSON: "+err.Error())
	}
	delimiter, ok := token.(json.Delim)
	if !ok {
		return nil
	}
	switch delimiter {
	case '{':
		seen := make(map[string]struct{})
		for decoder.More() {
			keyToken, keyErr := decoder.Token()
			if keyErr != nil {
				return invalid(path, "invalid object key")
			}
			key, ok := keyToken.(string)
			if !ok {
				return invalid(path, "object key must be a string")
			}
			if _, duplicate := seen[key]; duplicate {
				return invalid(path, "duplicate object key "+strconv.Quote(key))
			}
			seen[key] = struct{}{}
			if err := scanValue(decoder, depth+1, path+"."+key); err != nil {
				return err
			}
		}
		_, err = decoder.Token()
		return err
	case '[':
		index := 0
		for decoder.More() {
			if err := scanValue(decoder, depth+1, fmt.Sprintf("%s[%d]", path, index)); err != nil {
				return err
			}
			index++
		}
		_, err = decoder.Token()
		return err
	default:
		return invalid(path, "unexpected closing delimiter")
	}
}

func rejectDuplicateKeys(raw []byte) error {
	decoder := json.NewDecoder(bytes.NewReader(raw))
	decoder.UseNumber()
	if err := scanValue(decoder, 0, "json"); err != nil {
		return err
	}
	if _, err := decoder.Token(); !errors.Is(err, io.EOF) {
		if err == nil {
			return invalid("json", "contains more than one value")
		}
		return invalid("json", "has trailing invalid content")
	}
	return nil
}

func validateContractPins(value any) error {
	pins, err := array(value, "contractPins")
	if err != nil || len(pins) != len(contractPins) {
		return invalid("contractPins", "must contain both pinned contracts")
	}
	seen := make(map[string]struct{})
	for index, item := range pins {
		path := fmt.Sprintf("contractPins[%d]", index)
		pin, err := object(item, path)
		if err != nil {
			return err
		}
		if err := exactKeys(pin, []string{"id", "artifactSchema", "artifactProfile", "ownerRepository", "producerCommit", "schemaSha256", "fixtureSha256"}, path); err != nil {
			return err
		}
		id, err := text(pin["id"], path+".id")
		if err != nil {
			return err
		}
		expected, ok := contractPins[id]
		_, duplicate := seen[id]
		if !ok || duplicate {
			return invalid(path+".id", "must identify one unique pinned contract")
		}
		seen[id] = struct{}{}
		checks := map[string]string{
			"artifactSchema": expected.artifactSchema, "artifactProfile": expected.artifactProfile,
			"ownerRepository": expected.ownerRepository, "producerCommit": expected.producerCommit,
			"schemaSha256": expected.schemaSHA256, "fixtureSha256": expected.fixtureSHA256,
		}
		for field, expectedValue := range checks {
			if err := equalText(pin[field], expectedValue, path+"."+field); err != nil {
				return err
			}
		}
	}
	return nil
}

func validateResults(value any) error {
	results, err := array(value, "results")
	if err != nil || len(results) != len(casePins) {
		return invalid("results", "must contain all 14 pinned case results")
	}
	seen := make(map[string]struct{})
	for index, item := range results {
		path := fmt.Sprintf("results[%d]", index)
		result, err := object(item, path)
		if err != nil {
			return err
		}
		if err := exactKeys(result, []string{"id", "contract", "category", "status", "expectedSemantics", "observedSemantics", "inputSha256", "diagnostic", "sideEffectExecuted"}, path); err != nil {
			return err
		}
		id, err := text(result["id"], path+".id")
		if err != nil {
			return err
		}
		expected, ok := casePins[id]
		_, duplicate := seen[id]
		if !ok || duplicate {
			return invalid(path+".id", "must identify one unique pinned case")
		}
		seen[id] = struct{}{}
		checks := map[string]string{
			"contract": expected.contract, "category": expected.category, "status": "PASS",
			"expectedSemantics": expected.expectedSemantics, "observedSemantics": expected.expectedSemantics,
			"inputSha256": expected.inputSHA256,
		}
		for field, expectedValue := range checks {
			if err := equalText(result[field], expectedValue, path+"."+field); err != nil {
				return err
			}
		}
		if _, err := text(result["diagnostic"], path+".diagnostic"); err != nil {
			return err
		}
		if err := equalBool(result["sideEffectExecuted"], false, path+".sideEffectExecuted"); err != nil {
			return err
		}
	}
	return nil
}

// ValidateJSON rejects drift or ambiguity and returns a non-authorizing summary.
func ValidateJSON(raw []byte) (Summary, error) {
	if len(raw) > MaxReportBytes {
		return Summary{}, invalid("json", fmt.Sprintf("must not exceed %d bytes", MaxReportBytes))
	}
	if err := rejectDuplicateKeys(raw); err != nil {
		return Summary{}, err
	}
	decoder := json.NewDecoder(bytes.NewReader(raw))
	decoder.UseNumber()
	var decoded any
	if err := decoder.Decode(&decoded); err != nil {
		return Summary{}, invalid("json", "invalid JSON: "+err.Error())
	}
	report, err := object(decoded, "report")
	if err != nil {
		return Summary{}, err
	}
	if err := exactKeys(report, []string{"schema", "reportId", "suiteId", "suiteVersion", "suiteSha256", "implementation", "status", "counts", "contractPins", "results", "authority", "claimBoundary"}, "report"); err != nil {
		return Summary{}, err
	}
	for field, expected := range map[string]string{
		"schema": reportSchema, "suiteId": suiteID, "suiteVersion": suiteVersion,
		"suiteSha256": suiteSHA256, "status": "PASS", "claimBoundary": claimBoundary,
	} {
		if err := equalText(report[field], expected, field); err != nil {
			return Summary{}, err
		}
	}
	reportID, err := text(report["reportId"], "reportId")
	if err != nil || !safeID.MatchString(reportID) {
		return Summary{}, invalid("reportId", "must be a safe identifier")
	}
	implementationValue, err := object(report["implementation"], "implementation")
	if err != nil {
		return Summary{}, err
	}
	if err := exactKeys(implementationValue, []string{"name", "version", "language"}, "implementation"); err != nil {
		return Summary{}, err
	}
	name, err := text(implementationValue["name"], "implementation.name")
	if err != nil {
		return Summary{}, err
	}
	version, err := text(implementationValue["version"], "implementation.version")
	if err != nil {
		return Summary{}, err
	}
	language, err := text(implementationValue["language"], "implementation.language")
	if err != nil {
		return Summary{}, err
	}
	counts, err := object(report["counts"], "counts")
	if err != nil {
		return Summary{}, err
	}
	if err := exactKeys(counts, []string{"total", "passed", "failed"}, "counts"); err != nil {
		return Summary{}, err
	}
	for field, expected := range map[string]int{"total": 14, "passed": 14, "failed": 0} {
		if err := equalInt(counts[field], expected, "counts."+field); err != nil {
			return Summary{}, err
		}
	}
	authority, err := object(report["authority"], "authority")
	if err != nil {
		return Summary{}, err
	}
	if err := exactKeys(authority, []string{"classification", "mayAuthorizeAction"}, "authority"); err != nil {
		return Summary{}, err
	}
	if err := equalText(authority["classification"], "conformance_evidence_only", "authority.classification"); err != nil {
		return Summary{}, err
	}
	if err := equalBool(authority["mayAuthorizeAction"], false, "authority.mayAuthorizeAction"); err != nil {
		return Summary{}, err
	}
	if err := validateContractPins(report["contractPins"]); err != nil {
		return Summary{}, err
	}
	if err := validateResults(report["results"]); err != nil {
		return Summary{}, err
	}
	return Summary{
		Valid: true, SuiteID: suiteID, Implementation: Implementation{Name: name, Version: version, Language: language},
		Passed: 14, MayAuthorizeAction: false, ClaimBoundary: claimBoundary,
	}, nil
}

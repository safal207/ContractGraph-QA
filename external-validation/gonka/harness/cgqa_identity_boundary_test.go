//go:build testenvci

package citest

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"devshard/testenv/citest/harness"
	"devshard/testenv/config"

	"github.com/stretchr/testify/require"
)

type identityHTTPResult struct {
	Status            int
	Body              []byte
	ClientRequestID   string
	ResponseRequestID string
	StartedAt         time.Time
	EndedAt           time.Time
	Err               error
}

type accountingAddressProbe struct {
	RequestID  string          `json:"request_id"`
	Endpoint   string          `json:"endpoint"`
	HTTPStatus int             `json:"http_status"`
	Resolved   bool            `json:"resolved"`
	ObservedAt string          `json:"observed_at"`
	Body       json.RawMessage `json:"body"`
}

type identityTransportEvidence struct {
	ClientRequestID   string `json:"client_request_id"`
	ResponseRequestID string `json:"response_request_id"`
	HTTPStatus        int    `json:"http_status"`
	StartedAt         string `json:"started_at"`
	EndedAt           string `json:"ended_at"`
	Outcome           string `json:"outcome"`
}

type identityBoundaryEvidence struct {
	SchemaVersion                 string  `json:"schema_version"`
	CaseID                        string  `json:"case_id"`
	RunID                         string  `json:"run_id"`
	UpstreamRevision              string  `json:"upstream_revision"`
	Environment                   string  `json:"environment"`
	ClientRequestID               string  `json:"client_request_id"`
	ResponseRequestID             string  `json:"response_request_id"`
	RequestSucceeded              bool    `json:"request_succeeded"`
	HTTPStatus                    int     `json:"http_status"`
	EscrowID                      string  `json:"escrow_id"`
	AccountingResolvedByClientID  bool    `json:"accounting_resolved_by_client_id"`
	AccountingResolvedByResponseID bool   `json:"accounting_resolved_by_response_id"`
	StateNonceBefore              *uint64 `json:"state_nonce_before"`
	StateNonceAfter               *uint64 `json:"state_nonce_after"`
	StateProgressed               bool    `json:"state_progressed"`
	Verdict                       string  `json:"verdict"`
	PrivateHypothesisID           *string `json:"private_hypothesis_id"`
	Notes                         string  `json:"notes"`
}

func TestCGQAGonkaIdentityBoundary(t *testing.T) {
	harness.SkipUnlessEnv(t, "TESTENV_CITEST")
	harness.RequireDocker(t)

	stack, cfg, eps := harness.BootAdversarialStack(t, "cgqa-gonka-id-*")
	client := harness.GatewayChatClient()
	model := config.PrimaryModelID(cfg)
	adminKey := harness.TestenvAdminAPIKey
	escrowID := harness.GetGatewayEscrowID(t, client, eps.GatewayHTTP)
	runID := fmt.Sprintf("cgqa-gonka-id-%d", time.Now().UTC().UnixNano())
	caseDir := identityCaseDir(t)

	t.Cleanup(func() {
		if t.Failed() {
			harness.DumpComposeLogs(t, stack, "devshardctl", "versiond-0", "versiond-1", "mock-openai")
		}
	})

	beforeStatus := requireGatewayJSON(t, client, eps.GatewayHTTP, adminKey, "/v1/status")
	beforeState := requireDevshardState(t, client, eps.GatewayHTTP, adminKey, escrowID)
	writeRawJSONArtifact(t, caseDir, "gateway_status.before.json", beforeStatus)
	writeRawJSONArtifact(t, caseDir, "devshard_state.before.json", beforeState)

	body := chatBody(t, model, "CGQA G-001-ID request accounting identity boundary control")
	writeRawJSONArtifact(t, caseDir, "request.redacted.json", body)

	clientRequestID := runID + "-client"
	writeJSONArtifact(t, caseDir, "run_metadata.json", map[string]any{
		"case_id": "G-001-ID",
		"run_id": runID,
		"upstream_revision": cgqaUpstreamRevision,
		"environment": "gonka-local-devshard-testenv",
		"model": model,
		"escrow_id": escrowID,
		"client_request_id": clientRequestID,
		"started_at": time.Now().UTC().Format(time.RFC3339Nano),
	})

	transport := postIdentityChat(eps.GatewayHTTP, adminKey, clientRequestID, body, client)
	if len(transport.Body) > 0 && json.Valid(transport.Body) {
		writeRawJSONArtifact(t, caseDir, "response.redacted.json", transport.Body)
	} else {
		writeJSONArtifact(t, caseDir, "response.redacted.json", map[string]any{
			"observed": len(transport.Body) > 0,
			"body_text": string(transport.Body),
		})
	}
	transportOutcome := "success"
	if transport.Err != nil {
		transportOutcome = "transport_error"
	} else if transport.Status < 200 || transport.Status >= 300 {
		transportOutcome = "http_error"
	}
	writeJSONArtifact(t, caseDir, "transport.json", identityTransportEvidence{
		ClientRequestID: clientRequestID,
		ResponseRequestID: transport.ResponseRequestID,
		HTTPStatus: transport.Status,
		StartedAt: transport.StartedAt.Format(time.RFC3339Nano),
		EndedAt: transport.EndedAt.Format(time.RFC3339Nano),
		Outcome: transportOutcome,
	})

	afterStatus := requireGatewayJSON(t, client, eps.GatewayHTTP, adminKey, "/v1/status")
	afterState := requireDevshardState(t, client, eps.GatewayHTTP, adminKey, escrowID)
	writeRawJSONArtifact(t, caseDir, "gateway_status.after.json", afterStatus)
	writeRawJSONArtifact(t, caseDir, "devshard_state.after.json", afterState)
	writeRawJSONArtifact(t, caseDir, "debug_perf.after.json", requireDevshardDebugPerf(t, client, eps.GatewayHTTP, adminKey, escrowID))

	clientProbe := waitAccountingAddressProbe(client, eps.GatewayHTTP, adminKey, escrowID, clientRequestID, 8*time.Second)
	writeJSONArtifact(t, caseDir, "accounting.client-id.json", clientProbe)

	responseProbe := accountingAddressProbe{
		RequestID: transport.ResponseRequestID,
		Endpoint: strings.TrimRight(eps.GatewayHTTP, "/") + "/devshard/" + url.PathEscape(escrowID) + "/v1/requests/" + url.PathEscape(transport.ResponseRequestID),
		HTTPStatus: 0,
		Resolved: false,
		ObservedAt: time.Now().UTC().Format(time.RFC3339Nano),
		Body: json.RawMessage(`{"error":{"message":"response X-Request-Id missing"}}`),
	}
	if transport.ResponseRequestID != "" {
		if transport.ResponseRequestID == clientRequestID {
			responseProbe = clientProbe
		} else {
			responseProbe = waitAccountingAddressProbe(client, eps.GatewayHTTP, adminKey, escrowID, transport.ResponseRequestID, 8*time.Second)
		}
	}
	writeJSONArtifact(t, caseDir, "accounting.response-id.json", responseProbe)

	beforeNonce := extractNonce(beforeState)
	afterNonce := extractNonce(afterState)
	stateProgressed := beforeNonce != nil && afterNonce != nil && *afterNonce > *beforeNonce
	requestSucceeded := transport.Err == nil && transport.Status >= 200 && transport.Status < 300

	verdict := "INCONCLUSIVE"
	notes := "request did not produce a successful control response, so request-accounting addressability was not evaluated"
	var hypothesis *string
	if requestSucceeded && (clientProbe.Resolved || responseProbe.Resolved) {
		verdict = "PASS"
		notes = "successful inference request accounting is addressable by at least one externally available request identity"
	} else if requestSucceeded && !clientProbe.Resolved && !responseProbe.Resolved {
		verdict = "FAIL"
		notes = "successful inference completed, but request accounting was not addressable by either the client-supplied X-Request-Id or the response-visible X-Request-Id"
		h := "CGQA-GONKA-001"
		hypothesis = &h
	}

	evidence := identityBoundaryEvidence{
		SchemaVersion: "gonka-identity-boundary-v0.1",
		CaseID: "G-001-ID",
		RunID: runID,
		UpstreamRevision: cgqaUpstreamRevision,
		Environment: "gonka-local-devshard-testenv",
		ClientRequestID: clientRequestID,
		ResponseRequestID: transport.ResponseRequestID,
		RequestSucceeded: requestSucceeded,
		HTTPStatus: transport.Status,
		EscrowID: escrowID,
		AccountingResolvedByClientID: clientProbe.Resolved,
		AccountingResolvedByResponseID: responseProbe.Resolved,
		StateNonceBefore: beforeNonce,
		StateNonceAfter: afterNonce,
		StateProgressed: stateProgressed,
		Verdict: verdict,
		PrivateHypothesisID: hypothesis,
		Notes: notes,
	}
	writeJSONArtifact(t, caseDir, "reconciliation.json", evidence)

	if verdict == "FAIL" {
		t.Errorf("G-001-ID causal observability FAIL: %s", notes)
	} else if verdict == "INCONCLUSIVE" {
		t.Logf("G-001-ID INCONCLUSIVE: %s", notes)
	}
}

func postIdentityChat(baseURL, adminKey, clientRequestID string, body []byte, client *http.Client) identityHTTPResult {
	result := identityHTTPResult{ClientRequestID: clientRequestID, StartedAt: time.Now().UTC()}
	req, err := http.NewRequest(http.MethodPost, strings.TrimRight(baseURL, "/")+"/v1/chat/completions", bytes.NewReader(body))
	if err != nil {
		result.Err = err
		result.EndedAt = time.Now().UTC()
		return result
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Request-Id", clientRequestID)
	if adminKey != "" {
		req.Header.Set("Authorization", "Bearer "+adminKey)
	}
	resp, err := client.Do(req)
	result.EndedAt = time.Now().UTC()
	if err != nil {
		result.Err = err
		return result
	}
	defer resp.Body.Close()
	result.Status = resp.StatusCode
	result.ResponseRequestID = strings.TrimSpace(resp.Header.Get("X-Request-Id"))
	result.Body, _ = io.ReadAll(resp.Body)
	return result
}

func waitAccountingAddressProbe(client *http.Client, gatewayURL, adminKey, escrowID, requestID string, timeout time.Duration) accountingAddressProbe {
	endpoint := strings.TrimRight(gatewayURL, "/") + "/devshard/" + url.PathEscape(escrowID) + "/v1/requests/" + url.PathEscape(requestID)
	deadline := time.Now().Add(timeout)
	last := accountingAddressProbe{RequestID: requestID, Endpoint: endpoint}
	for time.Now().Before(deadline) {
		raw, status, err := getBytes(client, endpoint, adminKey)
		last.HTTPStatus = status
		last.ObservedAt = time.Now().UTC().Format(time.RFC3339Nano)
		if err != nil {
			last.Body = json.RawMessage(fmt.Sprintf(`{"error":{"message":%q}}`, err.Error()))
			time.Sleep(250 * time.Millisecond)
			continue
		}
		if json.Valid(raw) {
			last.Body = append(json.RawMessage(nil), raw...)
		} else {
			encoded, _ := json.Marshal(map[string]any{"body_text": string(raw)})
			last.Body = encoded
		}
		if status >= 200 && status < 300 {
			last.Resolved = true
			return last
		}
		time.Sleep(250 * time.Millisecond)
	}
	return last
}

func requireDevshardDebugPerf(t *testing.T, client *http.Client, gatewayURL, adminKey, escrowID string) []byte {
	t.Helper()
	endpoint := strings.TrimRight(gatewayURL, "/") + "/devshard/" + url.PathEscape(escrowID) + "/v1/debug/perf"
	raw, status, err := getBytes(client, endpoint, adminKey)
	require.NoError(t, err)
	require.Less(t, status, 300, "GET debug perf returned %d: %s", status, string(raw))
	require.True(t, json.Valid(raw), "debug perf did not return JSON: %s", string(raw))
	return raw
}

func extractNonce(raw []byte) *uint64 {
	var direct struct {
		Nonce uint64 `json:"nonce"`
	}
	if json.Unmarshal(raw, &direct) == nil {
		v := direct.Nonce
		return &v
	}
	return nil
}

func identityCaseDir(t *testing.T) string {
	t.Helper()
	root := strings.TrimSpace(os.Getenv("CGQA_EVIDENCE_DIR"))
	if root == "" {
		root = filepath.Join(t.TempDir(), "cgqa-evidence")
	}
	dir := filepath.Join(root, "G-001-ID")
	require.NoError(t, os.MkdirAll(dir, 0o755))
	return dir
}

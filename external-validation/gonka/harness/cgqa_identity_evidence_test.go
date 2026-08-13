//go:build testenvci

package citest

import (
	"encoding/json"
	"fmt"
	"net/http"
	"testing"
	"time"

	"devshard/testenv/citest/harness"
	"devshard/testenv/config"
)

// TestCGQAGonkaIdentityBoundaryEvidence collects the G-001-ID bundle without
// failing the Go test on a verification verdict. CI validates/uploads the
// evidence first and enforces PASS as a separate final gate, so a finding
// cannot prevent its own evidence from being preserved.
func TestCGQAGonkaIdentityBoundaryEvidence(t *testing.T) {
	harness.SkipUnlessEnv(t, "TESTENV_CITEST")
	harness.RequireDocker(t)

	_, cfg, eps := harness.BootAdversarialStack(t, "cgqa-gonka-id-evidence-*")
	client := harness.GatewayChatClient()
	model := config.PrimaryModelID(cfg)
	adminKey := harness.TestenvAdminAPIKey
	escrowID := harness.GetGatewayEscrowID(t, client, eps.GatewayHTTP)
	runID := fmt.Sprintf("cgqa-gonka-id-%d", time.Now().UTC().UnixNano())
	caseDir := identityCaseDir(t)

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
	} else if transport.Status < http.StatusOK || transport.Status >= http.StatusMultipleChoices {
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

	responseProbe := clientProbe
	if transport.ResponseRequestID == "" {
		responseProbe = accountingAddressProbe{
			RequestID: "",
			Endpoint: "",
			HTTPStatus: 0,
			Resolved: false,
			ObservedAt: time.Now().UTC().Format(time.RFC3339Nano),
			Body: json.RawMessage(`{"error":{"message":"response X-Request-Id missing"}}`),
		}
	} else if transport.ResponseRequestID != clientRequestID {
		responseProbe = waitAccountingAddressProbe(client, eps.GatewayHTTP, adminKey, escrowID, transport.ResponseRequestID, 8*time.Second)
	}
	writeJSONArtifact(t, caseDir, "accounting.response-id.json", responseProbe)

	beforeNonce := extractNonce(beforeState)
	afterNonce := extractNonce(afterState)
	stateProgressed := beforeNonce != nil && afterNonce != nil && *afterNonce > *beforeNonce
	requestSucceeded := transport.Err == nil && transport.Status >= http.StatusOK && transport.Status < http.StatusMultipleChoices

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
	t.Logf("G-001-ID evidence collected with verdict=%s", verdict)
}

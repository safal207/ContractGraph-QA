//go:build testenvci

package citest

import (
	"fmt"
	"net/http"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"testing"
	"time"

	"devshard/testenv/citest/harness"
	"devshard/testenv/config"
	"devshard/testenv/mockopenai"

	"github.com/stretchr/testify/require"
)

type cgqaSafeRetryCaseEvidence struct {
	SchemaVersion            string   `json:"schema_version"`
	CaseID                   string   `json:"case_id"`
	LogicalOperationID       string   `json:"logical_operation_id"`
	ClientCorrelationIDs     []string `json:"client_correlation_ids"`
	InternalRequestIDs       []string `json:"internal_request_ids"`
	WinnerNonces             []uint64 `json:"winner_nonces"`
	TimeoutObserved          bool     `json:"timeout_observed"`
	FirstCompletionObserved  bool     `json:"first_completion_observed"`
	RetryHTTPStatus          int      `json:"retry_http_status"`
	AllAccountingResolved    bool     `json:"all_accounting_resolved"`
	CanonicalIDsDistinct     bool     `json:"canonical_ids_distinct"`
	WinnerNoncesDistinct     bool     `json:"winner_nonces_distinct"`
	UnexplainedEffects       []string `json:"unexplained_effects"`
	Verdict                  string   `json:"verdict"`
	Notes                    string   `json:"notes"`
}

type cgqaSafeRetryBundle struct {
	SchemaVersion string                    `json:"schema_version"`
	UpstreamSHA   string                    `json:"upstream_revision"`
	Environment   string                    `json:"environment"`
	Cases         []cgqaSafeRetryCaseEvidence `json:"cases"`
	Verdict       string                    `json:"verdict"`
}

func TestCGQAGonkaSafeTimeoutRetryEvidence(t *testing.T) {
	harness.SkipUnlessEnv(t, "TESTENV_CITEST")
	harness.RequireDocker(t)

	_, cfg, eps := harness.BootAdversarialStack(t, "cgqa-gonka-safe-retry-*")
	client := harness.GatewayChatClient()
	model := config.PrimaryModelID(cfg)
	adminKey := harness.TestenvAdminAPIKey
	escrowID := harness.GetGatewayEscrowID(t, client, eps.GatewayHTTP)
	root := safeRetryEvidenceRoot(t)

	t.Cleanup(func() { harness.ResetMockOpenAIFault(t, client, eps.MockOpenAIHTTP) })

	a := runSafeRetryCase(t, client, eps.GatewayHTTP, eps.MockOpenAIHTTP, adminKey, escrowID, model, "G-002A", true)
	b := runSafeRetryCase(t, client, eps.GatewayHTTP, eps.MockOpenAIHTTP, adminKey, escrowID, model, "G-002B", false)
	bundleVerdict := "PASS"
	if a.Verdict != "PASS" || b.Verdict != "PASS" {
		bundleVerdict = "FAIL"
	}
	writeJSONArtifact(t, root, "reconciliation.json", cgqaSafeRetryBundle{
		SchemaVersion: "gonka-safe-timeout-retry-v0.1",
		UpstreamSHA:   cgqaUpstreamRevision,
		Environment:   "gonka-local-devshard-testenv",
		Cases:         []cgqaSafeRetryCaseEvidence{a, b},
		Verdict:       bundleVerdict,
	})
	t.Logf("safe timeout/retry verdict=%s G-002A=%s G-002B=%s", bundleVerdict, a.Verdict, b.Verdict)
}

func runSafeRetryCase(t *testing.T, client *http.Client, gatewayURL, mockOpenAIURL, adminKey, escrowID, model, caseID string, reuseCorrelation bool) cgqaSafeRetryCaseEvidence {
	t.Helper()
	stamp := time.Now().UTC().UnixNano()
	logicalID := fmt.Sprintf("cgqa-%s-logical-%d", strings.ToLower(caseID), stamp)
	corr1 := fmt.Sprintf("cgqa-%s-corr-1-%d", strings.ToLower(caseID), stamp)
	corr2 := corr1
	if !reuseCorrelation {
		corr2 = fmt.Sprintf("cgqa-%s-corr-2-%d", strings.ToLower(caseID), stamp)
	}
	body := chatBody(t, model, "CGQA "+caseID+" safe-correlation timeout retry")

	beforePerf := requireDevshardDebugPerf(t, client, gatewayURL, adminKey, escrowID)
	beforeCount, ok := timeoutPerfRequestCount(beforePerf)
	require.True(t, ok)

	latencyMS := 1800
	harness.PatchMockOpenAIFault(t, client, mockOpenAIURL, mockopenai.FaultPatch{LatencyMs: &latencyMS})
	shortClient := &http.Client{Timeout: 350 * time.Millisecond}
	first := postIdentityChat(gatewayURL, adminKey, corr1, body, shortClient)
	timeoutObserved := isTimeout(first.Err)

	_, _, firstCompletion := waitForPerfRequestAfter(client, gatewayURL, adminKey, escrowID, beforeCount, 15*time.Second)
	firstLookup := requireCorrelationLookup(t, client, gatewayURL, adminKey, escrowID, corr1, 1, 8*time.Second)
	firstIDs := correlationInternalIDs(firstLookup)

	zero := 0
	harness.PatchMockOpenAIFault(t, client, mockOpenAIURL, mockopenai.FaultPatch{LatencyMs: &zero})
	second := postIdentityChat(gatewayURL, adminKey, corr2, body, client)
	require.NoError(t, second.Err)
	require.GreaterOrEqual(t, second.Status, http.StatusOK)
	require.Less(t, second.Status, http.StatusMultipleChoices)

	var allIDs []string
	if reuseCorrelation {
		lookup := requireCorrelationLookup(t, client, gatewayURL, adminKey, escrowID, corr1, 2, 8*time.Second)
		allIDs = correlationInternalIDs(lookup)
	} else {
		lookup1 := requireCorrelationLookup(t, client, gatewayURL, adminKey, escrowID, corr1, 1, 8*time.Second)
		lookup2 := requireCorrelationLookup(t, client, gatewayURL, adminKey, escrowID, corr2, 1, 8*time.Second)
		allIDs = append(correlationInternalIDs(lookup1), correlationInternalIDs(lookup2)...)
		sort.Strings(allIDs)
	}

	accountingResolved := true
	winnerNonces := make([]uint64, 0, len(allIDs))
	for _, internalID := range allIDs {
		acct, resolved := requireInternalAccounting(t, client, gatewayURL, adminKey, escrowID, internalID, 8*time.Second)
		if !resolved {
			accountingResolved = false
			continue
		}
		winnerNonces = append(winnerNonces, acct.WinnerNonce)
	}

	canonicalDistinct := len(allIDs) == 2 && allIDs[0] != allIDs[1]
	winnerDistinct := len(winnerNonces) == 2 && winnerNonces[0] != 0 && winnerNonces[1] != 0 && winnerNonces[0] != winnerNonces[1]
	unexplained := []string{}
	if !timeoutObserved { unexplained = append(unexplained, "first transport did not produce expected client timeout") }
	if !firstCompletion { unexplained = append(unexplained, "first timed-out operation did not produce completion witness") }
	if len(firstIDs) != 1 { unexplained = append(unexplained, "first correlation did not resolve exactly one internal request before retry") }
	if !canonicalDistinct { unexplained = append(unexplained, "two completed operations did not retain two distinct canonical internal request IDs") }
	if !accountingResolved { unexplained = append(unexplained, "not every internal request ID resolved request accounting") }
	if !winnerDistinct { unexplained = append(unexplained, "completed operations did not retain distinct winner nonces") }

	verdict := "PASS"
	if len(unexplained) > 0 { verdict = "FAIL" }
	return cgqaSafeRetryCaseEvidence{
		SchemaVersion:           "gonka-safe-timeout-retry-case-v0.1",
		CaseID:                  caseID,
		LogicalOperationID:      logicalID,
		ClientCorrelationIDs:    []string{corr1, corr2},
		InternalRequestIDs:      allIDs,
		WinnerNonces:            winnerNonces,
		TimeoutObserved:         timeoutObserved,
		FirstCompletionObserved: firstCompletion,
		RetryHTTPStatus:         second.Status,
		AllAccountingResolved:   accountingResolved,
		CanonicalIDsDistinct:    canonicalDistinct,
		WinnerNoncesDistinct:    winnerDistinct,
		UnexplainedEffects:      unexplained,
		Verdict:                 verdict,
		Notes:                   "PASS means both post-timeout operations remain independently addressable and causally reconcilable; it does not imply retry idempotency",
	}
}

func safeRetryEvidenceRoot(t *testing.T) string {
	t.Helper()
	root := strings.TrimSpace(os.Getenv("CGQA_EVIDENCE_DIR"))
	if root == "" { root = filepath.Join(t.TempDir(), "cgqa-safe-timeout-retry") }
	require.NoError(t, os.MkdirAll(root, 0o755))
	return root
}

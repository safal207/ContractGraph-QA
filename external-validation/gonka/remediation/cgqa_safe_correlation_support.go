package main

import (
	"context"
	"fmt"
	"net/http"
	"strings"
	"time"

	"devshard/logging"
)

// This file is copied into a pinned Gonka checkout only by CGQA proof
// workflows. It is not an upstream patch. It demonstrates a non-collapsing
// correlation shape while leaving request_accounting.request_id canonical and
// gateway-generated.

type cgqaClientCorrelationContextKey struct{}

func withCGQAClientCorrelationID(ctx context.Context, id string) context.Context {
	id = strings.TrimSpace(id)
	if id == "" {
		return ctx
	}
	return context.WithValue(ctx, cgqaClientCorrelationContextKey{}, id)
}

func cgqaClientCorrelationIDFromContext(ctx context.Context) string {
	if ctx == nil {
		return ""
	}
	id, _ := ctx.Value(cgqaClientCorrelationContextKey{}).(string)
	return strings.TrimSpace(id)
}

func propagateCGQARequestContext(dst, src context.Context) context.Context {
	dst = logging.PropagateRequestID(dst, src)
	return withCGQAClientCorrelationID(dst, cgqaClientCorrelationIDFromContext(src))
}

type cgqaRequestCorrelation struct {
	ClientCorrelationID string `json:"client_correlation_id"`
	InternalRequestID   string `json:"internal_request_id"`
	EscrowID            string `json:"escrow_id"`
	CreatedAt           string `json:"created_at"`
}

func (s *PerfStore) ensureCGQARequestCorrelationSchema() error {
	if s == nil || s.db == nil {
		return nil
	}
	_, err := s.db.Exec(`
		CREATE TABLE IF NOT EXISTS cgqa_request_correlations (
			client_correlation_id TEXT NOT NULL,
			internal_request_id   TEXT NOT NULL,
			escrow_id             TEXT NOT NULL,
			created_at            TEXT NOT NULL,
			PRIMARY KEY (client_correlation_id, internal_request_id, escrow_id)
		);
		CREATE INDEX IF NOT EXISTS cgqa_request_correlations_lookup_idx
		ON cgqa_request_correlations(client_correlation_id, escrow_id, created_at);
	`)
	return err
}

// upsertCGQAAccountingRequestWithCorrelation preserves the upstream canonical
// request_accounting key and persists the caller-controlled correlation in the
// same SQLite transaction. The proof originally used two independent writes;
// under the single-connection PerfStore that introduced an avoidable hot-path
// interleaving/blocking surface. One transaction also gives the desired causal
// invariant: a visible correlation mapping cannot exist without its canonical
// request row, and the request row cannot commit without the mapping when a
// correlation was supplied.
func (s *PerfStore) upsertCGQAAccountingRequestWithCorrelation(requestID, escrowID, model, clientID string, startedAt time.Time) error {
	requestID = strings.TrimSpace(requestID)
	escrowID = strings.TrimSpace(escrowID)
	clientID = strings.TrimSpace(clientID)
	if s == nil || s.db == nil || requestID == "" || escrowID == "" {
		return nil
	}
	if startedAt.IsZero() {
		startedAt = time.Now()
	}

	logging.Info("CGQA safe correlation accounting", "subsystem", "cgqa-correlation", "stage", "tx-begin-enter", "request_id", requestID, "client_correlation_id", clientID, "escrow_id", escrowID)
	tx, err := s.db.Begin()
	if err != nil {
		logging.Info("CGQA safe correlation accounting", "subsystem", "cgqa-correlation", "stage", "tx-begin-error", "request_id", requestID, "error", err)
		return err
	}
	logging.Info("CGQA safe correlation accounting", "subsystem", "cgqa-correlation", "stage", "tx-begin-complete", "request_id", requestID)
	defer tx.Rollback()

	logging.Info("CGQA safe correlation accounting", "subsystem", "cgqa-correlation", "stage", "accounting-upsert-enter", "request_id", requestID)
	if _, err := tx.Exec(
		`INSERT INTO request_accounting (request_id, escrow_id, model, started_at)
		 VALUES (?, ?, ?, ?)
		 ON CONFLICT(request_id, escrow_id) DO UPDATE SET
		   model = CASE WHEN excluded.model <> '' THEN excluded.model ELSE request_accounting.model END`,
		requestID,
		escrowID,
		model,
		startedAt.Format(time.RFC3339Nano),
	); err != nil {
		logging.Info("CGQA safe correlation accounting", "subsystem", "cgqa-correlation", "stage", "accounting-upsert-error", "request_id", requestID, "error", err)
		return err
	}
	logging.Info("CGQA safe correlation accounting", "subsystem", "cgqa-correlation", "stage", "accounting-upsert-complete", "request_id", requestID)

	if clientID != "" {
		logging.Info("CGQA safe correlation accounting", "subsystem", "cgqa-correlation", "stage", "correlation-upsert-enter", "request_id", requestID, "client_correlation_id", clientID)
		if _, err := tx.Exec(
			`INSERT OR IGNORE INTO cgqa_request_correlations
			 (client_correlation_id, internal_request_id, escrow_id, created_at)
			 VALUES (?, ?, ?, ?)`,
			clientID,
			requestID,
			escrowID,
			startedAt.Format(time.RFC3339Nano),
		); err != nil {
			logging.Info("CGQA safe correlation accounting", "subsystem", "cgqa-correlation", "stage", "correlation-upsert-error", "request_id", requestID, "client_correlation_id", clientID, "error", err)
			return err
		}
		logging.Info("CGQA safe correlation accounting", "subsystem", "cgqa-correlation", "stage", "correlation-upsert-complete", "request_id", requestID, "client_correlation_id", clientID)
	}

	logging.Info("CGQA safe correlation accounting", "subsystem", "cgqa-correlation", "stage", "tx-commit-enter", "request_id", requestID)
	if err := tx.Commit(); err != nil {
		logging.Info("CGQA safe correlation accounting", "subsystem", "cgqa-correlation", "stage", "tx-commit-error", "request_id", requestID, "error", err)
		return err
	}
	logging.Info("CGQA safe correlation accounting", "subsystem", "cgqa-correlation", "stage", "tx-commit-complete", "request_id", requestID)
	return nil
}

func (s *PerfStore) findCGQARequestCorrelations(clientID, escrowID string) ([]cgqaRequestCorrelation, error) {
	clientID = strings.TrimSpace(clientID)
	escrowID = strings.TrimSpace(escrowID)
	if s == nil || clientID == "" || escrowID == "" {
		return nil, nil
	}
	rows, err := s.db.Query(
		`SELECT client_correlation_id, internal_request_id, escrow_id, created_at
		 FROM cgqa_request_correlations
		 WHERE client_correlation_id = ? AND escrow_id = ?
		 ORDER BY created_at ASC, internal_request_id ASC`,
		clientID, escrowID,
	)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []cgqaRequestCorrelation
	for rows.Next() {
		var rec cgqaRequestCorrelation
		if err := rows.Scan(&rec.ClientCorrelationID, &rec.InternalRequestID, &rec.EscrowID, &rec.CreatedAt); err != nil {
			return nil, err
		}
		out = append(out, rec)
	}
	return out, rows.Err()
}

func (t *PerfTracker) recordCGQAAccountingRequestStart(requestID, escrowID, model, clientID string, startedAt time.Time) {
	if t == nil || t.store == nil {
		return
	}
	logging.Info("CGQA safe correlation accounting", "subsystem", "cgqa-correlation", "stage", "record-start-enter", "request_id", strings.TrimSpace(requestID), "client_correlation_id", strings.TrimSpace(clientID), "escrow_id", strings.TrimSpace(escrowID))
	if strings.TrimSpace(clientID) == "" {
		t.RecordAccountingRequestStart(requestID, escrowID, model, startedAt)
		logging.Info("CGQA safe correlation accounting", "subsystem", "cgqa-correlation", "stage", "record-start-upstream-complete", "request_id", strings.TrimSpace(requestID))
		return
	}
	if err := t.store.upsertCGQAAccountingRequestWithCorrelation(requestID, escrowID, model, clientID, startedAt); err != nil {
		fmt.Printf("cgqa: persist atomic request accounting correlation: %v\n", err)
		logging.Info("CGQA safe correlation accounting", "subsystem", "cgqa-correlation", "stage", "record-start-error", "request_id", strings.TrimSpace(requestID), "error", err)
		return
	}
	logging.Info("CGQA safe correlation accounting", "subsystem", "cgqa-correlation", "stage", "record-start-complete", "request_id", strings.TrimSpace(requestID))
}

func (p *Proxy) handleCGQARequestCorrelation(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	clientID := strings.TrimSpace(r.PathValue("client_request_id"))
	if clientID == "" {
		http.Error(w, `{"error":{"message":"client_request_id is required"}}`, http.StatusBadRequest)
		return
	}
	if p == nil || p.perf == nil || p.perf.store == nil {
		http.Error(w, `{"error":{"message":"request correlation unavailable"}}`, http.StatusServiceUnavailable)
		return
	}
	matches, err := p.perf.store.findCGQARequestCorrelations(clientID, p.escrowID)
	if err != nil {
		http.Error(w, fmt.Sprintf(`{"error":{"message":%q}}`, err.Error()), http.StatusInternalServerError)
		return
	}
	writeJSON(w, map[string]any{
		"client_correlation_id": clientID,
		"escrow_id":             p.escrowID,
		"matches":               matches,
		"match_count":           len(matches),
	})
}

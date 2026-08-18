use std::collections::BTreeMap;
use std::env;
use std::fs;
use std::path::PathBuf;

use liminal_store::{
    sha256_ref, TransitionDimensions, TransitionEventInput, TransitionProjection,
    TrustworthyTransitionLedger,
};
use serde::{Deserialize, Serialize};

const BUNDLE_SCHEMA: &str = "cgqa-gonka-liminaldb-transition-bundle-v0.1";
const RECEIPT_SCHEMA: &str = "cgqa-gonka-liminaldb-bridge-receipt-v0.1";

#[derive(Debug, Deserialize)]
struct BridgeBundle {
    schema: String,
    source_evidence_digest: String,
    liminaldb_revision: String,
    source_schema: String,
    transition_ids: Vec<String>,
    events: Vec<TransitionEventInput>,
}

#[derive(Debug, Serialize)]
struct ProjectionReceipt {
    transition_id: String,
    subject_id: String,
    event_count: u64,
    last_sequence: u64,
    last_event_hash: String,
    side_effect_committed: bool,
    dimensions: Option<TransitionDimensions>,
}

#[derive(Debug, Serialize)]
struct BridgeReceipt {
    schema: String,
    source_evidence_digest: String,
    source_schema: String,
    liminaldb_revision: String,
    event_count: u64,
    transition_count: usize,
    event_chain_head: String,
    snapshot_digest: String,
    replay_verified: bool,
    event_hashes: Vec<String>,
    projections: Vec<ProjectionReceipt>,
}

fn projection_receipts(
    projections: &BTreeMap<String, TransitionProjection>,
) -> Vec<ProjectionReceipt> {
    projections
        .values()
        .map(|projection| ProjectionReceipt {
            transition_id: projection.transition_id.clone(),
            subject_id: projection.subject_id.clone(),
            event_count: projection.event_count,
            last_sequence: projection.last_sequence,
            last_event_hash: projection.last_event_hash.clone(),
            side_effect_committed: projection.side_effect_committed,
            dimensions: projection.dimensions.clone(),
        })
        .collect()
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<String> = env::args().collect();
    if args.len() != 5 {
        return Err("usage: cgqa_gonka_bridge <source-evidence.json> <transition-bundle.json> <ledger-root> <receipt.json>".into());
    }

    let source_path = PathBuf::from(&args[1]);
    let bundle_path = PathBuf::from(&args[2]);
    let ledger_root = PathBuf::from(&args[3]);
    let receipt_path = PathBuf::from(&args[4]);

    let source_bytes = fs::read(&source_path)?;
    let bundle_bytes = fs::read(&bundle_path)?;
    let bundle: BridgeBundle = serde_json::from_slice(&bundle_bytes)?;

    if bundle.schema != BUNDLE_SCHEMA {
        return Err(format!("unexpected bridge bundle schema: {}", bundle.schema).into());
    }
    let observed_source_digest = sha256_ref(&source_bytes);
    if observed_source_digest != bundle.source_evidence_digest {
        return Err(format!(
            "source evidence digest mismatch: expected {}, observed {}",
            bundle.source_evidence_digest, observed_source_digest
        )
        .into());
    }
    let expected_revision = env::var("LIMINALDB_SHA").unwrap_or_default();
    if !expected_revision.is_empty() && expected_revision != bundle.liminaldb_revision {
        return Err(format!(
            "LiminalDB revision mismatch: bundle={}, env={}",
            bundle.liminaldb_revision, expected_revision
        )
        .into());
    }
    if bundle.events.is_empty() || bundle.transition_ids.is_empty() {
        return Err("bridge bundle contains no transition events".into());
    }

    if ledger_root.exists() {
        fs::remove_dir_all(&ledger_root)?;
    }
    fs::create_dir_all(&ledger_root)?;

    let (before_reopen, event_hashes, snapshot_digest, event_count, event_chain_head) = {
        let mut ledger = TrustworthyTransitionLedger::open(&ledger_root)?;
        let mut hashes = Vec::with_capacity(bundle.events.len());
        let mut last_captured_at_ms = 0u64;

        for input in bundle.events.iter().cloned() {
            last_captured_at_ms = last_captured_at_ms.max(input.captured_at_ms);
            let event = ledger.append(input)?;
            hashes.push(event.event_hash);
        }

        let snapshot = ledger.write_snapshot(last_captured_at_ms.saturating_add(1))?;
        let projections = ledger.projections().clone();
        let count = ledger.event_count();
        let head = ledger
            .head_event_hash()
            .ok_or("LiminalDB event chain has no head after append")?
            .to_owned();
        (
            projections,
            hashes,
            snapshot.snapshot_digest().to_owned(),
            count,
            head,
        )
    };

    let reopened = TrustworthyTransitionLedger::open(&ledger_root)?;
    let replay_verified = reopened.projections() == &before_reopen
        && reopened.event_count() == event_count
        && reopened.head_event_hash() == Some(event_chain_head.as_str());
    if !replay_verified {
        return Err("LiminalDB reopen/full-replay projection mismatch".into());
    }
    if reopened.projections().len() != bundle.transition_ids.len() {
        return Err(format!(
            "transition projection count mismatch: expected {}, observed {}",
            bundle.transition_ids.len(),
            reopened.projections().len()
        )
        .into());
    }
    for transition_id in &bundle.transition_ids {
        if reopened.projection(transition_id).is_none() {
            return Err(format!("missing LiminalDB projection for {transition_id}").into());
        }
    }

    let receipt = BridgeReceipt {
        schema: RECEIPT_SCHEMA.to_owned(),
        source_evidence_digest: bundle.source_evidence_digest,
        source_schema: bundle.source_schema,
        liminaldb_revision: bundle.liminaldb_revision,
        event_count,
        transition_count: reopened.projections().len(),
        event_chain_head,
        snapshot_digest,
        replay_verified,
        event_hashes,
        projections: projection_receipts(reopened.projections()),
    };

    if let Some(parent) = receipt_path.parent() {
        fs::create_dir_all(parent)?;
    }
    fs::write(&receipt_path, serde_json::to_vec_pretty(&receipt)?)?;
    println!("{}", serde_json::to_string_pretty(&receipt)?);
    Ok(())
}

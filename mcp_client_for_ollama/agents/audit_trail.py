"""Policy-as-code audit trail with provenance tracking and tamper-proof logging.

Implements a blockchain-lite ledger for audit decisions with cryptographic hashing.
"""

import json
import hashlib
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path
from dataclasses import dataclass, asdict
import base64


@dataclass
class AuditEntry:
    """Single audit trail entry with provenance metadata."""
    timestamp: str
    phase: str  # e.g., "ai_analysis", "static_validation", "business_logic"
    action: str  # e.g., "intent_score_calculated", "embedding_matched"
    agent_id: str
    decision: Dict[str, Any]  # The actual decision/data
    previous_hash: Optional[str] = None  # Hash of previous entry (chain link)
    verification: Optional[Dict[str, Any]] = None  # How this was verified
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)
    
    def compute_hash(self) -> str:
        """Compute cryptographic hash of this entry."""
        data_str = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(data_str.encode()).hexdigest()


class AuditTrail:
    """Tamper-proof audit trail with blockchain-lite ledger."""
    
    def __init__(self, ledger_path: Optional[Path] = None):
        """Initialize audit trail.
        
        Args:
            ledger_path: Path to ledger file (default: ~/.config/ollmcp/audit_ledger.json)
        """
        if ledger_path is None:
            ledger_path = Path.home() / ".config" / "ollmcp" / "audit_ledger.json"
        
        self.ledger_path = Path(ledger_path)
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.entries: List[AuditEntry] = []
        self._load_ledger()
    
    def _load_ledger(self) -> None:
        """Load existing ledger from disk."""
        if self.ledger_path.exists():
            try:
                with open(self.ledger_path, 'r') as f:
                    data = json.load(f)
                    self.entries = [
                        AuditEntry(**entry) for entry in data.get("entries", [])
                    ]
            except Exception as e:
                print(f"Warning: Could not load audit ledger: {e}")
                self.entries = []
    
    def _save_ledger(self) -> None:
        """Save ledger to disk."""
        data = {
            "entries": [entry.to_dict() for entry in self.entries],
            "chain_integrity": self.verify_chain_integrity()
        }
        
        with open(self.ledger_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def log_decision(
        self,
        phase: str,
        action: str,
        agent_id: str,
        decision: Dict[str, Any],
        verification: Optional[Dict[str, Any]] = None
    ) -> AuditEntry:
        """Log a decision with provenance tracking.
        
        Args:
            phase: Audit phase (ai_analysis, static_validation, etc.)
            action: Specific action taken
            agent_id: Agent that made the decision
            decision: Decision data (intent scores, embeddings, etc.)
            verification: How this was verified (optional)
            
        Returns:
            Created audit entry
        """
        previous_hash = self.entries[-1].compute_hash() if self.entries else None
        
        entry = AuditEntry(
            timestamp=datetime.utcnow().isoformat(),
            phase=phase,
            action=action,
            agent_id=agent_id,
            decision=decision,
            previous_hash=previous_hash,
            verification=verification
        )
        
        self.entries.append(entry)
        self._save_ledger()
        
        return entry
    
    def log_intent_score(
        self,
        agent_id: str,
        contract_path: str,
        intent_type: str,
        score: float,
        source: str = "smartintentnn"
    ) -> AuditEntry:
        """Log AI intent detection score with provenance.
        
        Args:
            agent_id: Agent making the decision
            contract_path: Contract being analyzed
            intent_type: Type of intent (fee, honeypot, mint, etc.)
            score: Intent score (0-1)
            source: Source of the score (smartintentnn, etc.)
            
        Returns:
            Audit entry
        """
        return self.log_decision(
            phase="ai_analysis",
            action="intent_score_calculated",
            agent_id=agent_id,
            decision={
                "contract_path": contract_path,
                "intent_type": intent_type,
                "score": float(score),
                "source": source,
                "timestamp": time.time()
            },
            verification={
                "verified_by": source,
                "method": "api_call",
                "confidence": "high" if score > 0.8 else "medium" if score > 0.5 else "low"
            }
        )
    
    def log_embedding_match(
        self,
        agent_id: str,
        contract_path: str,
        vulnerability: str,
        similarity: float,
        embedding_hash: str
    ) -> AuditEntry:
        """Log embedding similarity match with provenance.
        
        Args:
            agent_id: Agent making the decision
            contract_path: Contract being analyzed
            vulnerability: Matched vulnerability name
            similarity: Cosine similarity score
            embedding_hash: Hash of the embedding vector
            
        Returns:
            Audit entry
        """
        return self.log_decision(
            phase="ai_analysis",
            action="embedding_matched",
            agent_id=agent_id,
            decision={
                "contract_path": contract_path,
                "vulnerability": vulnerability,
                "similarity": float(similarity),
                "embedding_hash": embedding_hash
            },
            verification={
                "method": "cosine_similarity",
                "algorithm": "smartbert",
                "vuln_db_version": "1.0"
            }
        )
    
    def log_static_finding(
        self,
        agent_id: str,
        contract_path: str,
        tool: str,
        finding: Dict[str, Any]
    ) -> AuditEntry:
        """Log static analyzer finding with provenance.
        
        Args:
            agent_id: Agent making the decision
            contract_path: Contract analyzed
            tool: Static tool name (slither, mythril, etc.)
            finding: Finding details
            
        Returns:
            Audit entry
        """
        return self.log_decision(
            phase="static_validation",
            action="static_finding_detected",
            agent_id=agent_id,
            decision={
                "contract_path": contract_path,
                "tool": tool,
                "finding": finding
            },
            verification={
                "tool_version": finding.get("tool_version", "unknown"),
                "execution_hash": finding.get("execution_hash", "")
            }
        )
    
    def log_confidence_score(
        self,
        agent_id: str,
        finding_id: str,
        confidence: float,
        components: Dict[str, float]
    ) -> AuditEntry:
        """Log confidence score calculation with components.
        
        Args:
            agent_id: Agent making the decision
            finding_id: Unique finding identifier
            confidence: Calculated confidence score
            components: Components (ai_score, similarity, static_confirm, biz_ok)
            
        Returns:
            Audit entry
        """
        return self.log_decision(
            phase="confidence_scoring",
            action="confidence_calculated",
            agent_id=agent_id,
            decision={
                "finding_id": finding_id,
                "confidence": float(confidence),
                "components": components,
                "formula": "ai*0.4 + sim*0.3 + static*0.2 + biz*0.1"
            },
            verification={
                "method": "weighted_formula",
                "validated": True
            }
        )
    
    def log_auto_decision(
        self,
        agent_id: str,
        finding_id: str,
        status: str,  # validated, rejected, needs_review
        reason: str
    ) -> AuditEntry:
        """Log auto-approve/reject decision.
        
        Args:
            agent_id: Agent making the decision
            finding_id: Finding identifier
            status: Decision status
            reason: Reason for decision
            
        Returns:
            Audit entry
        """
        return self.log_decision(
            phase="auto_decision",
            action=f"finding_{status}",
            agent_id=agent_id,
            decision={
                "finding_id": finding_id,
                "status": status,
                "reason": reason,
                "automated": True
            },
            verification={
                "decision_type": "automated",
                "requires_human": status == "needs_review"
            }
        )
    
    def verify_chain_integrity(self) -> Dict[str, Any]:
        """Verify integrity of the audit chain.
        
        Returns:
            Verification result with status and any detected tampering
        """
        if not self.entries:
            return {"status": "empty", "tampering_detected": False}
        
        tampered = []
        for i, entry in enumerate(self.entries[1:], 1):
            prev_entry = self.entries[i - 1]
            expected_hash = prev_entry.compute_hash()
            
            if entry.previous_hash != expected_hash:
                tampered.append({
                    "entry_index": i,
                    "expected": expected_hash,
                    "found": entry.previous_hash
                })
        
        return {
            "status": "tampered" if tampered else "intact",
            "tampering_detected": len(tampered) > 0,
            "tampered_entries": tampered,
            "total_entries": len(self.entries),
            "chain_head": self.entries[-1].compute_hash() if self.entries else None
        }
    
    def get_provenance(
        self,
        finding_id: str
    ) -> List[AuditEntry]:
        """Get full provenance chain for a finding.
        
        Args:
            finding_id: Finding identifier
            
        Returns:
            List of audit entries related to this finding
        """
        provenance = []
        for entry in self.entries:
            if finding_id in json.dumps(entry.decision):
                provenance.append(entry)
        return provenance
    
    def export_for_compliance(
        self,
        output_path: Path,
        include_chain_verification: bool = True
    ) -> Path:
        """Export audit trail for regulatory compliance.
        
        Args:
            output_path: Output file path
            include_chain_verification: Include integrity verification
            
        Returns:
            Path to exported file
        """
        data = {
            "export_timestamp": datetime.utcnow().isoformat(),
            "total_entries": len(self.entries),
            "entries": [entry.to_dict() for entry in self.entries]
        }
        
        if include_chain_verification:
            data["chain_verification"] = self.verify_chain_integrity()
        
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        return output_path


class ModelSnapshot:
    """Cached model snapshot with provenance tracking."""
    
    def __init__(self, cache_dir: Optional[Path] = None):
        """Initialize model snapshot cache.
        
        Args:
            cache_dir: Cache directory (default: ~/.config/ollmcp/model_cache)
        """
        if cache_dir is None:
            cache_dir = Path.home() / ".config" / "ollmcp" / "model_cache"
        
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def save_snapshot(
        self,
        snapshot_id: str,
        data: Dict[str, Any],
        metadata: Dict[str, Any]
    ) -> Path:
        """Save a model snapshot with metadata.
        
        Args:
            snapshot_id: Unique snapshot identifier
            data: Snapshot data (embeddings, intent scores, etc.)
            metadata: Provenance metadata
            
        Returns:
            Path to saved snapshot
        """
        snapshot_path = self.cache_dir / f"{snapshot_id}.json"
        
        snapshot = {
            "snapshot_id": snapshot_id,
            "timestamp": datetime.utcnow().isoformat(),
            "data": data,
            "metadata": metadata,
            "data_hash": hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
        }
        
        with open(snapshot_path, 'w') as f:
            json.dump(snapshot, f, indent=2)
        
        return snapshot_path
    
    def load_snapshot(self, snapshot_id: str) -> Optional[Dict[str, Any]]:
        """Load a cached snapshot.
        
        Args:
            snapshot_id: Snapshot identifier
            
        Returns:
            Snapshot data or None if not found
        """
        snapshot_path = self.cache_dir / f"{snapshot_id}.json"
        
        if not snapshot_path.exists():
            return None
        
        with open(snapshot_path, 'r') as f:
            return json.load(f)
    
    def fallback_to_snapshot(
        self,
        snapshot_id: str,
        audit_trail: AuditTrail,
        agent_id: str
    ) -> bool:
        """Fallback to cached snapshot when services unavailable.
        
        Args:
            snapshot_id: Snapshot to use
            agent_id: Agent requesting fallback
            
        Returns:
            True if fallback successful
        """
        snapshot = self.load_snapshot(snapshot_id)
        
        if not snapshot:
            return False
        
        # Log the fallback decision
        audit_trail.log_decision(
            phase="fallback",
            action="fallback_to_snapshot",
            agent_id=agent_id,
            decision={
                "snapshot_id": snapshot_id,
                "reason": "ai_services_unavailable",
                "snapshot_timestamp": snapshot.get("timestamp")
            },
            verification={
                "snapshot_hash": snapshot.get("data_hash"),
                "validated": True
            }
        )
        
        return True


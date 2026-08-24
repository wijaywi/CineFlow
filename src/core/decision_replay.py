"""
Decision Replay System

Provides rigorous auditability by securely recording the context, reasoning, evidence, 
and alternatives considered for every autonomous decision executed by the agents. 
This is a critical component of the Agent Governance Layer, enabling human oversight.
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class AgentDecisionRecord(BaseModel):
    """
    Immutable forensic record of a single autonomous decision.
    """
    decision_id: str
    project_id: str
    agent_name: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    action: str = Field(description="The specific action taken (e.g., 'REMOVE SHOT_027')")
    reasoning: str = Field(description="The semantic justification for the action")
    evidence: str = Field(description="The data/metadata supporting the reasoning")
    confidence: float = Field(description="Agent's internal confidence score (0.0 - 1.0)")
    alternatives_considered: List[str] = Field(default_factory=list)

import hashlib
import json

class DecisionReplayEngine:
    def __init__(self):
        self._decision_log: List[AgentDecisionRecord] = []
        self._hash_chain: List[str] = ["GENESIS_HASH"]
        
    def _calculate_hash(self, record: AgentDecisionRecord, previous_hash: str) -> str:
        record_data = record.model_dump_json()
        payload = f"{previous_hash}|{record_data}".encode('utf-8')
        return hashlib.sha256(payload).hexdigest()

    def log_decision(self, record: AgentDecisionRecord) -> None:
        """Records an agent's decision into the immutable ledger with a cryptographic hash."""
        self._decision_log.append(record)
        new_hash = self._calculate_hash(record, self._hash_chain[-1])
        self._hash_chain.append(new_hash)
        logger.info(f"Recorded Decision {record.decision_id} (Hash: {new_hash[:8]}...)")
        
    def verify_integrity(self) -> bool:
        """Cryptographically verifies the entire audit chain."""
        logger.info("Starting cryptographic audit trail verification...")
        for i in range(len(self._decision_log)):
            record = self._decision_log[i]
            expected_hash = self._hash_chain[i+1]
            calculated = self._calculate_hash(record, self._hash_chain[i])
            if calculated != expected_hash:
                logger.error(f"[INTEGRITY FAILURE] Decision {record.decision_id} has been tampered with!")
                return False
        logger.info("[INTEGRITY VERIFIED] Audit chain is cryptographically sound.")
        return True

    def query_decisions(self, project_id: str, agent_name: Optional[str] = None) -> List[AgentDecisionRecord]:
        """
        Retrieves the complete reasoning pipeline for a specific project.
        """
        results = [d for d in self._decision_log if d.project_id == project_id]
        if agent_name:
            results = [d for d in results if d.agent_name == agent_name]
        return sorted(results, key=lambda x: x.timestamp)

    def replay_decision(self, decision_id: str) -> Optional[str]:
        """
        Formats a forensic audit trail into a human-readable 'Producer Desk' view.
        """
        for record in self._decision_log:
            if record.decision_id == decision_id:
                alternatives = ", ".join(record.alternatives_considered) if record.alternatives_considered else "None"
                
                replay_output = (
                    f"--- DECISION REPLAY: {decision_id} ---\n"
                    f"Agent:       {record.agent_name}\n"
                    f"Action:      {record.action}\n"
                    f"Reasoning:   {record.reasoning}\n"
                    f"Evidence:    {record.evidence}\n"
                    f"Confidence:  {record.confidence:.2f}\n"
                    f"Alternatives: {alternatives}\n"
                    f"----------------------------------------"
                )
                return replay_output
        return None

"""
Orchestrator

This module defines the Orchestrator, which acts as the central Mission Control.
It manages project lifecycles, orchestrates multi-agent workflows, and enforces 
global governance policies such as budget limits and maximum iteration loops.
"""

from typing import List, Dict, Any, Optional
import logging
from .models import QualityScore, ProjectState
from .agent_constitution import AgentConstitution
from .models import TimelineManifest, AssetItem

logger = logging.getLogger(__name__)

class Agent:
    """
    Base representation of an autonomous participant in the production pipeline.
    """
    def __init__(self, name: str, role: str):
        self.name = name
        self.role = role

class Orchestrator:
    def __init__(self, constitution: AgentConstitution):
        """
        Initializes the Orchestrator with the governing constitution.
        """
        self.constitution = constitution
        self.agents: Dict[str, Agent] = {}
        self.projects: Dict[str, ProjectState] = {}
        self._deadlock_state: Dict[str, Dict[str, Any]] = {}

    def check_revision_convergence(self, project_id: str, failure_reason: str, current_quality: float, manifest_hash: str) -> None:
        """
        Detects if the agent loop is stuck in a non-convergent revision cycle.
        If the same failure fingerprint repeats 3 times without material improvement
        in quality or manifest semantic hash, it halts the project.
        """
        state = self._deadlock_state.setdefault(project_id, {
            "failure_fingerprint": "",
            "count": 0,
            "last_quality": 0.0,
            "last_manifest_hash": ""
        })
        
        if state["failure_fingerprint"] == failure_reason:
            quality_delta = abs(current_quality - state["last_quality"])
            if quality_delta < 0.01:
                state["count"] += 1
            else:
                state["count"] = 1
        else:
            state["failure_fingerprint"] = failure_reason
            state["count"] = 1
            
        state["last_quality"] = current_quality
        state["last_manifest_hash"] = manifest_hash
        
        if state["count"] >= 3:
            logger.error(f"[SECURITY] Project {project_id} HALTED: REVISION_DEADLOCK detected.")
            if project_id in self.projects:
                self.projects[project_id].status = "REVISION_DEADLOCK"
            raise RuntimeError(f"REVISION_DEADLOCK: No material improvement over {state['count']} consecutive revisions for failure: '{failure_reason}'.")

    def register_agent(self, agent_id: str, agent: Agent) -> None:
        """Registers a specialized agent to the pipeline."""
        self.agents[agent_id] = agent

    def initialize_project(self, project_id: str, budget_limit: float = 10.0, max_iterations: int = 5) -> ProjectState:
        if project_id in self.projects:
            return self.projects[project_id]
        
        state = ProjectState(
            project_id=project_id, 
            budget_limit=budget_limit, 
            max_iterations=max_iterations
        )
        self.projects[project_id] = state
        return state

    def check_governance_limits(self, project_id: str, estimated_cost: float = 0.0) -> bool:
        """
        Validates that the project has not breached runtime constraints and reserves cost.
        Returns True if safe to proceed, False if halted.
        """
        import math
        if not math.isfinite(estimated_cost) or estimated_cost < 0:
            logger.error("[SECURITY] Invalid cost estimate.")
            return False
            
        if project_id not in self.projects:
            return False
            
        state = self.projects[project_id]
        
        if state.status.startswith("HALTED"):
            logger.error(f"[SECURITY] Project {project_id} is already HALTED.")
            return False

        if not self.constitution.evaluate_action("Orchestrator", "commit_cost", {"estimated_cost": estimated_cost}):
            logger.error(f"[SECURITY] Constitution rejected cost commit.")
            return False
            
        if state.iteration_count >= state.max_iterations:
            logger.error(f"[ALERT] Project {project_id} HALTED: Max iterations ({state.max_iterations}) reached. Escalate to Human.")
            state.status = "HALTED_ITERATION_LIMIT"
            return False
            
        if state.current_cost + estimated_cost > state.budget_limit:
            logger.error(f"[ALERT] Project {project_id} HALTED: Budget limit (${state.budget_limit}) will be exceeded by estimated cost (${estimated_cost}). Escalate to Human.")
            state.status = "HALTED_BUDGET_LIMIT"
            return False
            
        return True

    def check_confidence_threshold(self, project_id: str, confidence: float, agent_name: str, threshold: float = 0.75) -> bool:
        """
        The Agent Confidence Layer:
        Escalates to a human if an agent's internal confidence score falls below the required threshold.
        """
        state = self.projects.get(project_id)
        if not state:
            return False
            
        if confidence < threshold:
            logger.error(f"[ESCALATION] Project {project_id} HALTED: {agent_name} confidence ({confidence:.2f}) is below safety threshold ({threshold:.2f}). Human intervention required.")
            state.status = "HALTED_LOW_CONFIDENCE"
            return False
            
        return True

    def increment_version(self, project_id: str) -> None:
        """Increments the official project manifest version."""
        if project_id in self.projects:
            self.projects[project_id].current_version += 1

    def record_agent_cost(self, project_id: str, cost: float) -> None:
        """Records token/compute cost incurred by an agent's operation."""
        import math
        if not math.isfinite(cost) or cost < 0:
            logger.error(f"[SECURITY] Attempted to record invalid cost: {cost}")
            raise ValueError("Agent costs must be finite and non-negative.")
            
        if project_id in self.projects:
            state = self.projects[project_id]
            if state.current_cost + cost > state.budget_limit:
                logger.error(f"[ALERT] Project {project_id} HALTED: Anticipated cost (${state.current_cost + cost:.2f}) exceeds budget limit (${state.budget_limit}).")
                state.status = "HALTED_BUDGET_LIMIT"
                raise ValueError("Budget Exceeded")
            
            state.current_cost += cost

    def estimate_render_cost(self, manifest: TimelineManifest) -> float:
        """Estimates the compute cost of rendering a manifest."""
        cost = len(manifest.v1_audio_video) * 0.15 + len(manifest.v2_video_only) * 0.05
        return float(cost)

    def increment_iteration(self, project_id: str) -> None:
        """Tracks the 'Director ↔ Editor' debate cycles to prevent infinite loops."""
        if project_id in self.projects:
            self.projects[project_id].iteration_count += 1


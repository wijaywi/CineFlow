"""
Agent Constitution

This module defines the foundational principles, rules, and constraints that govern
the behavior of agents within the system. It ensures that agents operate safely,
ethically, and effectively.
"""

from typing import List, Dict, Any

class AgentConstitution:
    def __init__(self, principles: List[str] = None, constraints: List[str] = None):
        """
        Initializes the Agent Constitution.

        Args:
            principles: A list of core principles the agent must adhere to.
            constraints: A list of strict limitations on the agent's actions.
        """
        self.principles = principles or []
        self.constraints = constraints or []

    def evaluate_action(self, agent_name: str, action_type: str, action_details: Dict[str, Any]) -> bool:
        """
        Enforces constraints BEFORE an agent performs a critical action.
        """
        if action_type == "publish":
            if action_details.get("status") != "RENDER_COMPLETE":
                return False
        if action_type == "commit_cost":
            if action_details.get("estimated_cost", 0) < 0:
                return False
                
        return True

    def get_principles(self) -> List[str]:
        """
        Retrieves the governing principles.
        """
        return self.principles

    def get_constraints(self) -> List[str]:
        """
        Retrieves the strict constraints.
        """
        return self.constraints

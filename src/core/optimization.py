"""
Optimization Engine (Quality vs Cost Routing)

Evaluates the marginal improvements in video quality across iterative debate loops 
against the financial API/Compute costs incurred. It acts autonomously to halt 
revision cycles if the ROI (Return on Investment) per iteration becomes negligible,
preventing the system from burning budget for microscopic aesthetic improvements.
"""

import logging
from typing import Dict, List
from .models import QualityScore, ProjectState

logger = logging.getLogger(__name__)

class OptimizationEngine:
    def __init__(self, min_marginal_improvement: float = 1.0):
        """
        Args:
            min_marginal_improvement: The minimum required increase in the aggregate 
                                      quality score to justify the cost of another iteration.
        """
        self.min_marginal_improvement = min_marginal_improvement
        # Stores historical data: project_id -> list of {"cost": float, "quality": float}
        self._history: Dict[str, List[Dict[str, float]]] = {}
        
    def evaluate_roi(self, project: ProjectState, quality: QualityScore) -> bool:
        """
        Analyzes the current state of an iteration and calculates if further 
        optimization (revisions) is financially viable.
        
        Returns:
            bool: True if optimization should continue, False if it should halt due to low ROI.
        """
        project_id = project.project_id
        if project_id not in self._history:
            self._history[project_id] = []
            
        current_data = {"cost": project.current_cost, "quality": quality.aggregate}
        history = self._history[project_id]
        
        if len(history) > 0:
            previous_data = history[-1]
            quality_delta = current_data["quality"] - previous_data["quality"]
            cost_delta = current_data["cost"] - previous_data["cost"]
            
            if cost_delta <= 0:
                cost_delta = 0.01 # Prevent division by zero
                
            roi = quality_delta / cost_delta
            
            logger.info(f"[Optimization] Project {project_id} | Iteration {project.iteration_count} | ROI: {roi:.2f} (Quality: +{quality_delta:.2f} / Cost: +${cost_delta:.2f})")
            
            # If ROI is below threshold, stop optimizing
            if roi < self.min_marginal_improvement:
                logger.warning(f"[Optimization] STOP OPTIMIZATION: ROI ({roi:.2f}) is below threshold ({self.min_marginal_improvement}). Halting loops to preserve budget.")
                self._history[project_id].append(current_data)
                return False
                
        self._history[project_id].append(current_data)
        return True

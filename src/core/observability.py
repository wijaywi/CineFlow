"""
Observability Engine (Grafana / OpenTelemetry)

Provides the telemetry instrumentation required for the 'Producer's Desk'.
It tracks project costs, agent iteration loops, quality scores, and emits
structured metrics to Grafana Cloud via OTLP.
"""

from typing import Dict, Any, Optional, Iterable
from opentelemetry import trace, metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.resources import Resource
import logging
from .models import QualityScore

logger = logging.getLogger(__name__)

class ObservabilityEngine:
    def __init__(self, service_name: str = "cineflow-orchestrator"):
        logger.info("Initializing Grafana/OTel Observability Engine...")
        
        # Define the Telemetry Resource
        resource = Resource.create({"service.name": service_name})
        
        # Instantiate the OTLP Metric Exporter (Requires environment variables)
        try:
            exporter = OTLPMetricExporter(timeout=1)
            reader = PeriodicExportingMetricReader(exporter, export_interval_millis=15000, export_timeout_millis=1000)
            self.meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
            metrics.set_meter_provider(self.meter_provider)
        except Exception as e:
            logger.warning(f"Failed to initialize OTLP Metric Exporter. Telemetry will be disabled. Error: {e}")
            self.meter_provider = MeterProvider(resource=resource)
            metrics.set_meter_provider(self.meter_provider)
        
        # Retrieve the application meter
        self.meter = metrics.get_meter(service_name)
        
        # --- Define Mission Control Metrics ---
        
        # 1. Cost Tracking (Crucial for autonomous agents)
        self.cost_counter = self.meter.create_counter(
            name="cineflow.project.cost",
            description="Total API (LLM) and compute costs incurred",
            unit="USD"
        )
        
        # 2. Iteration Tracking (Director <-> Editor debate cycles)
        self.iteration_histogram = self.meter.create_histogram(
            name="cineflow.agent.iterations",
            description="Number of autonomous revision cycles",
            unit="cycles"
        )
        
        # Internal state to serve the asynchronous gauge
        self._current_scores: Dict[str, float] = {}
        
        # 3. Quality Scoring Gauge (Live updates on Producer's Desk)
        self.meter.create_observable_gauge(
            name="cineflow.project.quality_score",
            description="Aggregate quality score of the active manifest",
            callbacks=[self._yield_quality_score]
        )

    def _yield_quality_score(self, options) -> Iterable[metrics.Observation]:
        """Asynchronous callback to emit the current quality scores to Grafana."""
        for project_id, score in self._current_scores.items():
            yield metrics.Observation(score, {"project_id": project_id})

    def record_cost(self, project_id: str, agent_name: str, cost: float) -> None:
        """Emits financial cost data to Grafana Cloud."""
        self.cost_counter.add(cost, {"project_id": project_id, "agent": agent_name})
        
    def record_iterations(self, project_id: str, count: int) -> None:
        """Emits agent debate cycles to monitor pipeline efficiency."""
        self.iteration_histogram.record(count, {"project_id": project_id})
        
    def update_quality_score(self, project_id: str, score: QualityScore) -> None:
        """Updates the live quality score visible on the dashboard."""
        self._current_scores[project_id] = score.aggregate
        logger.info(f"Observability: Quality score for {project_id} updated to {score.aggregate:.2f}")

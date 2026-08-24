"""
Telemetry Configuration

This module establishes the OpenTelemetry tracing configuration required for system observability,
specifically targeting Grafana Cloud via the OpenTelemetry Protocol (OTLP).
"""

import os
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource

def setup_tracing(service_name: str = "orchestrator-agent-system"):
    """
    Initializes the OpenTelemetry tracing pipeline.

    This function configures a TracerProvider and an OTLPSpanExporter designed to transmit 
    span data to Grafana Cloud. It relies on standard OpenTelemetry environment variables 
    for endpoint and authentication configuration.

    Required Environment Variables for Grafana Cloud:
        OTEL_EXPORTER_OTLP_ENDPOINT: The Grafana Cloud OTLP HTTP endpoint.
                                     (e.g., https://otlp-gateway-prod-us-east-0.grafana.net/otlp)
        OTEL_EXPORTER_OTLP_HEADERS: The authorization header.
                                    (e.g., Authorization=Basic <base64_encoded_credentials>)

    Args:
        service_name: The nominal identifier for this service within the distributed trace.

    Returns:
        tracer: An initialized OpenTelemetry Tracer instance.
    """
    
    # Construct the Resource identifying the service entity
    resource = Resource.create({"service.name": service_name})
    
    # Instantiate the global TracerProvider
    tracer_provider = TracerProvider(resource=resource)
    
    # Instantiate the OTLP HTTP Exporter
    # Environment variables dictate the precise endpoint and authentication mechanisms
    otlp_exporter = OTLPSpanExporter()
    
    # Attach the exporter to the provider via a BatchSpanProcessor for asynchronous processing
    span_processor = BatchSpanProcessor(otlp_exporter)
    tracer_provider.add_span_processor(span_processor)
    
    # Establish the configured provider as the global default
    trace.set_tracer_provider(tracer_provider)
    
    # Return a generic tracer associated with the module
    return trace.get_tracer(service_name)

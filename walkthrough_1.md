# ADK Migration Walkthrough

This document summarizes the changes made to migrate the CineFlow project to use the Google Cloud Agent Development Kit (ADK).

## What Was Changed

1.  **Dependencies**: Added `google-cloud-aiplatform[agent_engines,adk]` to `requirements.txt`.
2.  **Director Agent Refactor (`src/agents/director_agent.py`)**:
    *   Replaced the pure `google.genai` logic with the ADK framework.
    *   Created `adk.Tool` wrappers for checking Grafana metrics and verifying compliance.
    *   Defined an `adk.Agent` that takes instructions and natively uses the provided tools.
    *   Maintained a fallback mechanism for when ADK is unavailable, preserving the deterministic manifest generation.
3.  **Orchestrator Refactor (`src/main.py`)**:
    *   Passed `mcp_client` and `compliance_agent` into the `DirectorAgent` upon instantiation so they can be wrapped as ADK Tools.
    *   Removed the manual `asyncio.run()` call that checked Grafana at the start of the pipeline.
    *   Replaced the complex `while` loop governing the Director/Compliance feedback loop. The delegation is now handed off directly to the ADK `DirectorAgent`, which internally decides to check compliance and metrics before returning the final manifest.

## What to Test

You can test the refactored workflow by running:
```bash
python src/main.py
```
If you have the `google-cloud-aiplatform` package installed and Vertex AI enabled in your environment, the ADK Agent will autonomously manage the function calls. Otherwise, it will gracefully fallback to the deterministic logic.

# Migrating CineFlow to Google Cloud ADK (Agent Engine)

This document outlines the steps to refactor `main.py` and `director_agent.py` to use the native Google Cloud ADK (`google.cloud.aiplatform.agent_engines.adk`). This will fulfill the hackathon's Agent Builder requirement by enabling native function calling and tool integration.

## User Review Required

> [!WARNING]
> Migrating to ADK requires rewriting the core orchestration logic. The explicit `while` loop that handles Director/Compliance iteration in `main.py` will be replaced by the internal orchestration of Vertex AI Agent Engine. Please review if you are comfortable ceding this control to the autonomous agent.

## Open Questions

> [!IMPORTANT]
> 1. The ADK currently targets Vertex AI. Do you have a Google Cloud Project with the Vertex AI API enabled and authenticated via `gcloud auth application-default login`?
> 2. Should we also convert the `ComplianceAgent` into an ADK Tool, so the `DirectorAgent` can call it autonomously, or keep them as separate agents?

## Proposed Changes

### Core Dependencies

#### [MODIFY] [requirements.txt](file:///d:/zzzzzzzzzzz%20AntiGravity/Bounty/src2/requirements.txt)
- Add dependency: `google-cloud-aiplatform[agent_engines,adk]>=1.101.0`

---

### Agent Definition

#### [MODIFY] [director_agent.py](file:///d:/zzzzzzzzzzz%20AntiGravity/Bounty/src2/src/agents/director_agent.py)
Replace the raw `google.genai` Client calls with the ADK `Agent` definition.

1.  **Define Agent Tools**: Create python functions for the agent to use, wrapping them with ADK.
    ```python
    from google.cloud.aiplatform.agent_engines import adk

    def check_compliance(manifest_json: str) -> str:
        """Sends a proposed manifest to the Compliance Agent for verification."""
        # Wrap existing compliance_agent logic
        pass

    compliance_tool = adk.Tool(
        name="verify_compliance",
        function=check_compliance
    )
    ```
2.  **Define the ADK Agent**:
    ```python
    class DirectorAgent:
        def __init__(self, media_db):
            self.agent = adk.Agent(
                name="cineflow-director",
                model="gemini-1.5-pro",
                instructions="""You are the Director Agent. 
                1. Check Grafana for active incidents. 
                2. Generate an EditDecision manifest based on the prompt. 
                3. Call the 'verify_compliance' tool to check your manifest.
                4. Revise if compliance rejects it.""",
                tools=[compliance_tool, grafana_mcp_tool]
            )

        def create_rough_cut(self, semantic_script):
            # Let the ADK handle the loop and tool calling natively
            response = self.agent.query(semantic_script)
            return response.output
    ```

---

### Core Orchestration

#### [MODIFY] [main.py](file:///d:/zzzzzzzzzzz%20AntiGravity/Bounty/src2/src/main.py)
Remove the hardcoded iterative loops and manual tool calls in favor of ADK execution.

1.  **Remove Manual Tools:** Remove the `asyncio.run(run_mcp_health_check())` block. The agent will call the Grafana MCP tool itself if we provide it.
2.  **Simplify the Creative Loop:** Replace the `while not manifest_approved:` loop.
    ```python
    # NEW ADK LOGIC:
    logger.info("Delegating execution to ADK Director Agent...")
    
    # The ADK Agent handles tool calling (Grafana, Compliance) autonomously
    final_manifest = director_agent.create_rough_cut(
        f"Generate a video for: Explain the new product..."
    )
    
    if final_manifest:
        logger.info("Agent successfully delivered a verified manifest.")
    ```

## Verification Plan

### Manual Verification
1. Run `python src/main.py`
2. Observe the terminal logs: We should see the ADK tracing output showing the agent *autonomously* deciding to call `check_grafana_metrics` and `verify_compliance` before generating its final output.
3. Check Vertex AI Agent Builder console to ensure the agent deployment and session history are tracked.

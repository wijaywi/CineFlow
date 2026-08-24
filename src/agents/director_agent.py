"""
Director Agent

Responsible for creative decision-making. Now powered natively by Google Cloud ADK (Agent Engine)
to autonomously orchestrate compliance checks and Grafana MCP metrics before finalizing the manifest.
"""

from typing import Dict, Any, List
import logging
import json
from core.models import EditDecision, BRollInsert, TimelineManifest
from core.models import ProjectState
from core.media_intelligence import MediaIntelligenceDB

try:
    from google.cloud.aiplatform.agent_engines import adk
    ADK_AVAILABLE = True
except ImportError:
    ADK_AVAILABLE = False
    logging.warning("google-cloud-aiplatform[agent_engines,adk] is not installed. Will use fallback mechanism.")

logger = logging.getLogger(__name__)


class DirectorAgent:
    def __init__(self, media_db: MediaIntelligenceDB, compliance_agent=None, mcp_client=None):
        self.media_db = media_db
        self.compliance_agent = compliance_agent
        self.mcp_client = mcp_client
        self.name = "Director_Agent"
        
        if ADK_AVAILABLE:
            # 1. Define ADK Tools
            
            def check_grafana_incidents(project_id: str) -> str:
                """Checks Grafana for active rendering or system incidents via MCP."""
                logger.info(f"[{self.name} - ADK Tool] Autonomously checking Grafana MCP...")
                if self.mcp_client:
                    import asyncio
                    try:
                        loop = asyncio.get_event_loop()
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                    status = loop.run_until_complete(self.mcp_client.query_incident_status(project_id))
                    return f"Active Incidents: {status.get('active_incidents', 0)}. Message: {status.get('message', 'OK')}"
                return "Grafana MCP not connected."
                
            def verify_manifest_compliance(manifest_json: str) -> str:
                """Sends a proposed manifest to the Compliance Agent for verification."""
                logger.info(f"[{self.name} - ADK Tool] Autonomously consulting Compliance Agent...")
                if not self.compliance_agent:
                    return "Compliance Agent not connected."
                try:
                    manifest = TimelineManifest.model_validate_json(manifest_json)
                    is_approved, reason = self.compliance_agent.verify_manifest(manifest)
                    if is_approved:
                        return "COMPLIANCE APPROVED."
                    else:
                        return f"COMPLIANCE REJECTED. Reason: {reason}"
                except Exception as e:
                    return f"Failed to parse or verify manifest: {e}"
            
            self.grafana_tool = adk.Tool(
                name="check_grafana_incidents",
                function=check_grafana_incidents
            )
            
            self.compliance_tool = adk.Tool(
                name="verify_manifest_compliance",
                function=verify_manifest_compliance
            )
            
            # 2. Define ADK Agent
            self.agent = adk.Agent(
                name="cineflow-director",
                model="gemini-1.5-pro",
                instructions="""You are the CineFlow Director Agent. 
You are responsible for generating a TimelineManifest.
Before finalizing the manifest, you MUST:
1. Check Grafana for active incidents using `check_grafana_incidents`. If there are active incidents, stop and report the error.
2. Formulate a draft manifest (JSON).
3. Check the draft manifest with `verify_manifest_compliance`.
4. If compliance rejects it, revise the manifest and check again.
Once compliance is approved, return the final JSON manifest and nothing else.
""",
                tools=[self.grafana_tool, self.compliance_tool]
            )

    def generate_draft_manifest(self, project: ProjectState, semantic_script: str, feedback: str = None) -> TimelineManifest:
        """Internal helper to generate the mathematical structure (legacy logic preserved)."""
        logger.info(f"[{self.name}] Generating draft manifest structure...")
        
        # Determine rejected asset if any
        rejected_assets = set()
        if feedback:
            for asset in self.media_db._asset_store.values():
                if asset.asset_id in feedback:
                    rejected_assets.add(asset.asset_id)
        
        primary_assets = [asset for asset in self.media_db._asset_store.values() if asset.asset_type == "A-Roll"]
        selected_primary_id = "raw_video_01"  
        source_uri = "raw_video_01.mp4"
        for asset in primary_assets:
            if asset.asset_id not in rejected_assets:
                selected_primary_id = asset.asset_id
                source_uri = asset.source_uri
                break

        decisions: List[EditDecision] = []
        import os
        from pydantic import BaseModel
        
        class EditDecisionList(BaseModel):
            decisions: List[EditDecision]
            
        api_key = os.environ.get("GEMINI_API_KEY")
        if api_key and os.path.exists(source_uri):
            try:
                from google import genai
                client = genai.Client(api_key=api_key)
                uploaded_file = client.files.upload(file=source_uri)
                import time
                while True:
                    file_info = client.files.get(name=uploaded_file.name)
                    if file_info.state == "ACTIVE":
                        break
                    elif file_info.state == "FAILED":
                        raise ValueError("Video processing failed.")
                    time.sleep(2)
                
                prompt = f"""Analyze the provided video. Instruction: "{semantic_script}". 
Create EditDecisions to KEEP good parts or CUT bad parts. Return JSON schema."""
                response = client.models.generate_content(
                    model='gemini-3.6-flash',
                    contents=[uploaded_file, prompt],
                    config=genai.types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=EditDecisionList,
                        temperature=0.0
                    )
                )
                if response.parsed:
                    decisions = response.parsed.decisions
                    for d in decisions:
                        d.clip_id = selected_primary_id
                try:
                    client.files.delete(name=uploaded_file.name)
                except:
                    pass
            except Exception as e:
                logger.error(f"[{self.name}] Gemini error: {e}")
                
        if not decisions:
            decisions = [
                EditDecision(clip_id=selected_primary_id, action="KEEP", start_time=1.023, end_time=5.800, reasoning="Intro", confidence=0.98),
                EditDecision(clip_id=selected_primary_id, action="CUT", start_time=5.801, end_time=12.000, reasoning="Dead air", confidence=0.95),
                EditDecision(clip_id=selected_primary_id, action="KEEP", start_time=12.001, end_time=25.000, reasoning="Main", confidence=0.92)
            ]
        
        broll_results = self.media_db.search_broll(query=semantic_script, min_duration=4.5)
        brolls: List[BRollInsert] = []
        if broll_results:
            brolls.append(BRollInsert(
                clip_id=broll_results[0].asset_id,
                insert_at_timeline=12.000,
                duration=4.500,
                reasoning="Covering visual."
            ))
            
        manifest = TimelineManifest(
            project_id=project.project_id,
            version=project.current_version,
            context=semantic_script,
            v1_audio_video=decisions,
            v2_video_only=brolls
        )
        return manifest

    def create_rough_cut(self, project: ProjectState, semantic_script: str, feedback: str = None) -> TimelineManifest:
        """
        Translates semantic script into mathematical timecodes. 
        If ADK is available, it orchestrates compliance/MCP tools natively.
        """
        logger.info(f"[{self.name}] Generating rough cut for project {project.project_id}")
        
        if ADK_AVAILABLE and self.compliance_agent and self.mcp_client:
            logger.info(f"[{self.name}] Delegating execution to ADK Engine...")
            
            # 1. Generate a base draft to pass to the ADK agent
            draft = self.generate_draft_manifest(project, semantic_script, feedback)
            draft_json = draft.model_dump_json()
            
            # 2. Instruct the ADK agent to finalize it
            adk_prompt = f"""
            Project ID: {project.project_id}
            User Instruction: {semantic_script}
            Draft Manifest (JSON): {draft_json}
            
            Please use your tools to check Grafana and Compliance. If Compliance rejects, 
            modify the draft manifest to resolve the issue (e.g., change asset ids, adjust times).
            Return the final verified JSON manifest.
            """
            
            try:
                response = self.agent.query(adk_prompt)
                # Parse the response back into a TimelineManifest
                # This assumes the ADK agent returned valid JSON. 
                # In production, we'd add JSON parsing logic or retries.
                # For this demo, we'll extract the JSON block if it exists
                text_out = response.output
                if "```json" in text_out:
                    import re
                    match = re.search(r"```json\s+(.*?)\s+```", text_out, re.DOTALL)
                    if match:
                        text_out = match.group(1)
                
                final_manifest = TimelineManifest.model_validate_json(text_out)
                return final_manifest
                
            except Exception as e:
                logger.error(f"[{self.name}] ADK execution failed or returned invalid format: {e}. Falling back.")
                # Fallback to returning the draft if ADK fails
                return draft
        else:
            # Legacy fallback if ADK is not installed or agents not provided
            return self.generate_draft_manifest(project, semantic_script, feedback)

"""
Director Agent

Responsible for creative decision-making. It translates semantic goals into 
deterministic, frame-accurate EditDecision structures. It leverages the 
Media Intelligence DB to select appropriate B-Roll without modifying raw files.
"""

from typing import Dict, Any, List
import logging
from core.models import EditDecision, BRollInsert, TimelineManifest
from core.models import ProjectState
from core.media_intelligence import MediaIntelligenceDB

logger = logging.getLogger(__name__)

class DirectorAgent:
    def __init__(self, media_db: MediaIntelligenceDB):
        self.media_db = media_db
        self.name = "Director_Agent"
        
    def create_rough_cut(self, project: ProjectState, semantic_script: str, feedback: str = None) -> TimelineManifest:
        """
        Translates semantic script (and optional rejection feedback) into mathematical timecodes.
        """
        logger.info(f"[{self.name}] Generating rough cut for project {project.project_id}")
        
        # Adaptive Revision Logic
        if feedback:
            logger.info(f"[{self.name}] Analyzing rejection feedback: '{feedback}'")
            logger.info(f"[{self.name}] Adapting semantic decisions to resolve compliance/quality violations...")
            if "waterproof" in feedback.lower() or "water-resistant" in feedback.lower():
                semantic_script = semantic_script.replace("waterproof", "water-resistant")
            else:
                semantic_script += f" [CORRECTED: {feedback}]"
        
        # In a real scenario, an LLM would parse the `semantic_script` and query 
        # the Media Intelligence DB for exact word-level timecodes.
        
        # Get all primary assets (A-Roll)
        primary_assets = [asset for asset in self.media_db._asset_store.values() if asset.asset_type == "A-Roll"]
        
        # Determine rejected asset if any
        rejected_assets = set()
        if feedback:
            for asset in self.media_db._asset_store.values():
                if asset.asset_id in feedback:
                    rejected_assets.add(asset.asset_id)
        
        # Pick the first valid primary asset
        selected_primary_id = "raw_video_01"  # Default fallback
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
            logger.info(f"[{self.name}] Uploading {source_uri} to Gemini 3.1 Pro for analysis...")
            try:
                from google import genai
                client = genai.Client(api_key=api_key)
                uploaded_file = client.files.upload(file=source_uri)
                logger.info(f"[{self.name}] File uploaded successfully. URI: {uploaded_file.uri}")
                
                # Check file state - for larger files, we might need to wait for processing to complete.
                # Since raw_video_01.mp4 is 30s long, it should be ready quickly, but let's poll just in case.
                import time
                while True:
                    file_info = client.files.get(name=uploaded_file.name)
                    if file_info.state == "ACTIVE":
                        break
                    elif file_info.state == "FAILED":
                        raise ValueError("Video processing failed in Gemini.")
                    logger.info(f"[{self.name}] Waiting for video processing... state: {file_info.state}")
                    time.sleep(2)
                
                prompt = f"""
You are an expert video editor. Analyze the provided video.
The user requested the following narrative script/instruction:
"{semantic_script}"

Identify the segments where the subject is speaking or where the visuals match the script.
Ignore segments with silence or "dead air".
Create a list of EditDecisions to 'KEEP' the good parts or 'CUT' the bad parts.
Use precise start_time and end_time (in seconds, e.g., 1.50). 
Ensure chronological order and that end_time > start_time.
Return exactly the requested JSON schema.
"""
                logger.info(f"[{self.name}] Prompting gemini-3.6-flash with multimodal video analysis...")
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
                    # Ensure clip IDs match our pipeline
                    for d in decisions:
                        d.clip_id = selected_primary_id
                    logger.info(f"[{self.name}] Received {len(decisions)} dynamic edit decisions from Gemini.")
                else:
                    logger.error("Failed to parse EditDecisionList from response.")
            except ImportError:
                logger.warning(f"[{self.name}] google.genai package not installed. Skipping multimodal analysis.")
            except Exception as e:
                logger.error(f"[{self.name}] Gemini processing error: {e}")
            finally:
                # ZERO-TRUST: Clean up uploaded asset from Google servers immediately
                if 'uploaded_file' in locals() and 'client' in locals():
                    try:
                        logger.info(f"[{self.name}] [Zero-Trust] Deleting asset {uploaded_file.name} from Google Cloud...")
                        client.files.delete(name=uploaded_file.name)
                    except Exception as e:
                        logger.error(f"Failed to delete {uploaded_file.name}: {e}")
        
        # Fallback if API fails or is not available
        if not decisions:
            logger.warning(f"[{self.name}] Falling back to simulated deterministic decisions.")
            decisions = [
                EditDecision(clip_id=selected_primary_id, action="KEEP", start_time=1.023, end_time=5.800, reasoning="Primary subject introduction.", confidence=0.98),
                EditDecision(clip_id=selected_primary_id, action="CUT", start_time=5.801, end_time=12.000, reasoning="Subject dead air and looking at script.", confidence=0.95),
                EditDecision(clip_id=selected_primary_id, action="KEEP", start_time=12.001, end_time=25.000, reasoning="Subject explaining the main concept.", confidence=0.92)
            ]
        
        # B-Roll Retrieval process via RAG (Retrieval-Augmented Generation)
        broll_results = self.media_db.search_broll(query=semantic_script, min_duration=4.5)
        brolls: List[BRollInsert] = []
        
        if broll_results:
            brolls.append(BRollInsert(
                clip_id=broll_results[0].asset_id,
                insert_at_timeline=12.000,
                duration=4.500,
                reasoning="Covering visual while subject discusses traffic, keeping primary audio."
            ))
        else:
            logger.warning(f"[{self.name}] Recommended B-Roll not found in vector database.")
            
        manifest = TimelineManifest(
            project_id=project.project_id,
            version=project.current_version,
            context=semantic_script,
            v1_audio_video=decisions,
            v2_video_only=brolls
        )
        
        return manifest

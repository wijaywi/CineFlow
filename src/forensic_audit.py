import os
import subprocess
import json
import secrets
import logging
from core.models import ProjectState, AssetItem, EditDecision, TimelineManifest
from agents.render_agent import RenderAgent
from core.media_intelligence import MediaIntelligenceDB
from core.quality_scoring import QualityScoringEngine
from core.agent_constitution import AgentConstitution

logging.basicConfig(level=logging.ERROR)

os.environ["CINEFLOW_SIGNING_SECRET"] = secrets.token_hex(32)
db = MediaIntelligenceDB()
constitution = AgentConstitution()
quality_engine = QualityScoringEngine(db)

input_vid = "audit_input.mp4"
proj = ProjectState(project_id="audit_proj")

print("\n=== PHASE 3: NEGATIVE RUNTIME TESTS ===")
asset_unk = AssetItem(asset_id="asset_unk", source_uri=input_vid, asset_type="A-Roll", owner="Test", license_type="unknown", commercial_use=False)
db.ingest_asset(asset_unk)
m_unk = TimelineManifest(project_id="audit_proj", version=1, context="Audit", v1_audio_video=[EditDecision(clip_id="asset_unk", action="KEEP", start_time=0.0, end_time=1.0, reasoning="test")])
score_unk = quality_engine.evaluate_project(proj, m_unk)
print(f"TEST A (Unknown License) - Rights Score: {score_unk.compliance}")

asset_no = AssetItem(asset_id="asset_no", source_uri=input_vid, asset_type="A-Roll", owner="Test", license_type="unlicensed", commercial_use=False)
db.ingest_asset(asset_no)
m_no = TimelineManifest(project_id="audit_proj", version=1, context="Audit", v1_audio_video=[EditDecision(clip_id="asset_no", action="KEEP", start_time=0.0, end_time=1.0, reasoning="test")])
score_no = quality_engine.evaluate_project(proj, m_no)
print(f"TEST B (Explicit Unlicensed) - Rights Score: {score_no.compliance}")

asset_tamper = AssetItem(asset_id="asset_tamper", source_uri=input_vid, asset_type="A-Roll", owner="Test", license_type="unlicensed", commercial_use=False)
db.ingest_asset(asset_tamper)
db._asset_store["asset_tamper"].commercial_use = True
m_tamper = TimelineManifest(project_id="audit_proj", version=1, context="Audit", v1_audio_video=[EditDecision(clip_id="asset_tamper", action="KEEP", start_time=0.0, end_time=1.0, reasoning="test")])
score_tamper = quality_engine.evaluate_project(proj, m_tamper)
print(f"TEST C (Metadata Tampering in DB) - Rights Score: {score_tamper.compliance}")


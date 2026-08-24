import os
import subprocess
import secrets
import logging
from core.models import ProjectState, AssetItem, EditDecision, TimelineManifest, LicenseStatus
from agents.render_agent import RenderAgent
from agents.compliance_agent import ComplianceAgent
from core.media_intelligence import MediaIntelligenceDB
from core.quality_scoring import QualityScoringEngine
from core.agent_constitution import AgentConstitution

logging.basicConfig(level=logging.WARNING)

os.environ["CINEFLOW_SIGNING_SECRET"] = secrets.token_hex(32)
db = MediaIntelligenceDB()
constitution = AgentConstitution()
quality_engine = QualityScoringEngine(db)
compliance_agent = ComplianceAgent(db)
render_agent = RenderAgent(db, constitution)

input_vid = "audit_input.mp4"
if not os.path.exists(input_vid):
    subprocess.run([
        "ffmpeg", "-f", "lavfi", "-i", "testsrc=duration=2:size=640x360:rate=30",
        "-c:v", "libx264", input_vid, "-y"
    ], check=True, capture_output=True)

proj = ProjectState(project_id="compliance_patch_tests")

tests = [
    ("TEST 1 (VERIFIED)", LicenseStatus.VERIFIED),
    ("TEST 2 (UNVERIFIED)", LicenseStatus.UNVERIFIED),
    ("TEST 3 (UNLICENSED)", LicenseStatus.UNLICENSED),
    ("TEST 4 (POTENTIAL_COPYRIGHT_MATCH)", LicenseStatus.POTENTIAL_COPYRIGHT_MATCH),
    ("TEST 5 (CHECK_FAILED)", LicenseStatus.CHECK_FAILED),
    ("TEST 6 (UNKNOWN)", LicenseStatus.UNKNOWN),
]

results = []

for test_name, status in tests:
    asset_id = f"asset_{status.name}"
    asset = AssetItem(asset_id=asset_id, source_uri=input_vid, asset_type="A-Roll", owner="Test", license_status=status)
    db.ingest_asset(asset)
    
    m = TimelineManifest(
        project_id="compliance_patch_tests", version=1, context="Audit",
        v1_audio_video=[EditDecision(clip_id=asset_id, action="KEEP", start_time=0.0, end_time=1.0, reasoning="test")]
    )
    
    # Run Quality Gate
    score = quality_engine.evaluate_project(proj, m)
    
    # Run Compliance Agent
    is_approved, reason = compliance_agent.verify_manifest(m)
    
    # Ensure Render Permission is ALLOWED
    render_permission = asset.render_permission.value
    
    # Run Render Agent
    receipt = render_agent.generate_and_execute(m)
    
    render_started = receipt is not None
    render_completed = receipt is not None and os.path.exists(receipt.artifact_path)
    
    results.append({
        "Status": status.name,
        "RenderPermission": render_permission,
        "ComplianceApproved": is_approved,
        "RenderStarted": render_started,
        "RenderCompleted": render_completed
    })

print("\n=== FINAL TEST RESULTS ===")
print(f"{'License Status':<30} | {'Compliance Approved':<20} | {'Render Permission':<20} | {'Render Started':<15} | {'Render Completed':<15}")
print("-" * 110)
for r in results:
    print(f"{r['Status']:<30} | {str(r['ComplianceApproved']):<20} | {r['RenderPermission']:<20} | {str(r['RenderStarted']):<15} | {str(r['RenderCompleted']):<15}")


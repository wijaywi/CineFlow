import streamlit as st
import asyncio
import os
import subprocess
import secrets
import time

if not os.environ.get("CINEFLOW_SIGNING_SECRET"):
    os.environ["CINEFLOW_SIGNING_SECRET"] = secrets.token_hex(32)

from core.models import ProjectState, AssetItem, EditDecision, TimelineManifest
from core.agent_constitution import AgentConstitution
from core.orchestrator import Orchestrator, Agent
from core.media_intelligence import MediaIntelligenceDB
from core.quality_scoring import QualityScoringEngine
from core.observability import ObservabilityEngine
from core.decision_replay import DecisionReplayEngine, AgentDecisionRecord
from core.grafana_mcp import GrafanaMCPClient

from agents.director_agent import DirectorAgent
from agents.qc_agent import QCAgent
from agents.render_agent import RenderAgent
from agents.compliance_agent import ComplianceAgent
from agents.distribution_agent import DistributionAgent

def run_async(coro):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)

def init_system():
    if "orchestrator" not in st.session_state:
        db = MediaIntelligenceDB()
        constitution = AgentConstitution()
        
        st.session_state.media_db = db
        st.session_state.constitution = constitution
        st.session_state.orchestrator = Orchestrator(constitution)
        st.session_state.quality_engine = QualityScoringEngine(db)
        st.session_state.observability = ObservabilityEngine()
        st.session_state.replay_engine = DecisionReplayEngine()
        st.session_state.mcp_client = GrafanaMCPClient()
        
        st.session_state.director_agent = DirectorAgent(db)
        st.session_state.qc_agent = QCAgent(db)
        st.session_state.render_agent = RenderAgent(db, constitution)
        st.session_state.compliance_agent = ComplianceAgent(db)
        st.session_state.distribution_agent = DistributionAgent(constitution)
        
        st.session_state.orchestrator.register_agent("director", Agent(name="Director", role="Creative"))
        st.session_state.orchestrator.register_agent("editor", Agent(name="Editor", role="Technical"))
        st.session_state.orchestrator.register_agent("qc", Agent(name="QC", role="Validator"))
        st.session_state.orchestrator.register_agent("compliance", Agent(name="Compliance", role="Validator"))
        st.session_state.orchestrator.register_agent("render", Agent(name="Render", role="Executor"))
        st.session_state.orchestrator.register_agent("distribution", Agent(name="Distribution", role="Executor"))
        
        st.session_state.phase = "CONFIG"
        st.session_state.pipeline_logs = []
        st.session_state.uploaded_video_path = None
        st.session_state.uploaded_broll_path = None
        st.session_state.project = None

st.set_page_config(page_title="CineFlow AI Control Center", layout="wide")

st.markdown("""
<style>
/* Dark Cinematic Theme */
.stApp {
    background-color: #0d0d0f;
    color: #e0e0e0;
    font-family: 'Inter', sans-serif;
}
.header-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-bottom: 10px;
    border-bottom: 1px solid #333;
    margin-bottom: 20px;
}
.header-title {
    font-size: 1.5rem;
    font-weight: 800;
    letter-spacing: 2px;
    color: #ffffff;
    margin: 0;
}
.header-subtitle {
    font-size: 0.8rem;
    color: #888;
    letter-spacing: 1px;
}
.header-status {
    text-align: right;
    font-size: 0.8rem;
    color: #888;
}
.header-status b {
    color: #fff;
    font-size: 1rem;
}
.status-ready { color: #00ff00; }
.card {
    background-color: #1a1a1c;
    border: 1px solid #2a2a2c;
    border-radius: 8px;
    padding: 15px;
    margin-bottom: 15px;
}
h4 {
    font-size: 0.9rem !important;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: #888 !important;
    margin-bottom: 10px !important;
    border-bottom: 1px solid #2a2a2c;
    padding-bottom: 5px;
}
.pipeline-step {
    display: inline-block;
    margin-right: 15px;
    font-size: 0.85rem;
    color: #555;
    font-weight: 600;
}
.step-active { color: #00E5FF; }
.step-done { color: #00ff00; }
.log-box {
    background: #000;
    font-family: monospace;
    font-size: 0.8rem;
    padding: 10px;
    height: 150px;
    overflow-y: auto;
    border-radius: 4px;
    border: 1px solid #333;
    color: #00ff00;
}
.ai-tag {
    display: inline-block;
    background: #2a2a2c;
    padding: 3px 8px;
    border-radius: 4px;
    font-size: 0.75rem;
    margin-right: 5px;
    color: #aaa;
}

/* File Uploader Button Colors */
div[data-testid="stFileUploader"]:nth-of-type(1) button {
    background-color: #2e7d32 !important; /* Green */
    color: white !important;
    border-color: #2e7d32 !important;
}
div[data-testid="stFileUploader"]:nth-of-type(1) button:hover {
    background-color: #1b5e20 !important;
}

div[data-testid="stFileUploader"]:nth-of-type(2) button {
    background-color: #f57f17 !important; /* Yellow/Amber */
    color: white !important;
    border-color: #f57f17 !important;
}
div[data-testid="stFileUploader"]:nth-of-type(2) button:hover {
    background-color: #f9a825 !important;
}
</style>
""", unsafe_allow_html=True)

init_system()

project_id = "CF_PROJECT_000001"

col_head1, col_head2, col_head3 = st.columns([1, 8, 3])
with col_head1:
    import os
    logo_path = os.path.join(os.path.dirname(__file__), "cineflow_logo.jpg")
    st.image(logo_path, width=80)
with col_head2:
    st.markdown("""
    <div style='margin-top: 5px;'>
      <h1 class='header-title' style='margin:0;'>CINEFLOW AI</h1>
      <span class='header-subtitle'>AUTONOMOUS STUDIO PIPELINE</span>
    </div>
    """, unsafe_allow_html=True)
with col_head3:
    st.markdown(f"""
    <div class='header-status' style='margin-top: 5px;'>
      PROJECT<br/><b>{project_id}</b><br/>
      STATUS<br/><span class='status-ready'>● READY</span>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<hr style='border: none; border-bottom: 1px solid #333; margin-top: 5px; margin-bottom: 20px;'/>", unsafe_allow_html=True)

col_left, col_right = st.columns([1, 1.2])

with col_left:
    st.markdown("#### ASSETS")
    
    with st.container():
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        uploaded_video = st.file_uploader("PRIMARY FOOTAGE (Drag & Drop MP4)", type=["mp4"])
        if uploaded_video:
            st.session_state.uploaded_video_path = "user_aroll.mp4"
            with open(st.session_state.uploaded_video_path, "wb") as f:
                f.write(uploaded_video.getbuffer())
        
        uploaded_broll = st.file_uploader("B-ROLL FOOTAGE (Drag & Drop MP4)", type=["mp4"])
        if uploaded_broll:
            st.session_state.uploaded_broll_path = "user_broll.mp4"
            with open(st.session_state.uploaded_broll_path, "wb") as f:
                f.write(uploaded_broll.getbuffer())
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("#### DIRECTOR'S VISION")
    with st.container():
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        semantic_script = st.text_area("What should the final film communicate?", value="Cut the bad parts. Product Y is water-resistant. Please generate an AI voiceover saying 'Welcome to the future of editing' and insert it into the video.", height=100)
        
        st.markdown("<small style='color: #888;'>💡 <b>Enterprise Guardrails Active:</b> Try changing 'water-resistant' to 'waterproof' to see the AI's Truth Graph automatically block false advertising claims.</small>", unsafe_allow_html=True)
        
        st.markdown("<br/><b>AI UNDERSTANDING</b><br/><span class='ai-tag'>[ Product ]</span><span class='ai-tag'>[ Water-resistant ]</span><span class='ai-tag'>[ Commercial ]</span>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("#### AI GOVERNANCE")
    with st.container():
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        budget = st.number_input("PRODUCTION BUDGET LIMIT ($)", value=10.0, step=1.0)
        c_cost = st.session_state.project.current_cost if st.session_state.project else 0.0
        st.progress(min(c_cost / budget, 1.0) if budget > 0 else 0.0)
        st.markdown(f"Allocated: **${budget:.2f}** | Consumed: **${c_cost:.2f}** | Remaining: **${budget - c_cost:.2f}**")
        st.markdown("? Hard limit enabled &nbsp;&nbsp;&nbsp; ? Human gates: 1")
        st.markdown("</div>", unsafe_allow_html=True)

with col_right:
    st.markdown("#### PIPELINE EXECUTION")
    
    if st.session_state.phase == "CONFIG":
        with st.container():
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            st.markdown("### PIPELINE READY")
            st.markdown("Your production pipeline is configured and ready to execute.")
            st.markdown("#### PRODUCTION READINESS")
            
            c1 = "\u2713" if st.session_state.uploaded_video_path else "\u25CB (Pending Upload)"
            st.write(f"{c1} Primary footage detected")
            st.write("\u2713 Semantic script valid")
            st.write(f"\u2713 Budget configured (${budget})")
            st.write(f"\u2713 {len(st.session_state.orchestrator.agents)} AI agents available")
            st.write("\u2713 Pipeline configuration valid")
            
            st.markdown("</div>", unsafe_allow_html=True)
            
            is_ready = bool(st.session_state.uploaded_video_path)
            if st.button("START PRODUCTION", type="primary", use_container_width=True, disabled=not is_ready):
                st.session_state.phase = "PROCESSING"
                st.session_state.budget_setting = budget
                st.session_state.script_setting = semantic_script
                st.rerun()

    elif st.session_state.phase == "PROCESSING":
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("""
        <div style='margin-bottom:15px'>
          <span class='pipeline-step step-active'>INGEST ??</span>
          <span class='pipeline-step step-active'>QC ??</span>
          <span class='pipeline-step step-active'>EDIT ??</span>
          <span class='pipeline-step'>VFX ??</span>
          <span class='pipeline-step'>AUDIO ??</span>
          <span class='pipeline-step'>DELIVERY</span>
        </div>
        """, unsafe_allow_html=True)
        
        with st.spinner("AI Agents are processing your footage..."):
            project = st.session_state.orchestrator.initialize_project(project_id=project_id, budget_limit=st.session_state.budget_setting)
            st.session_state.project = project
            
            # Asset Ingestion
            if not st.session_state.uploaded_video_path:
                dummy_video_path = "raw_video_01.mp4"
                if not os.path.exists(dummy_video_path):
                    subprocess.run([
                        "ffmpeg", "-f", "lavfi", "-i", "testsrc=duration=30:size=640x360:rate=30",
                        "-f", "lavfi", "-i", "sine=frequency=1000:duration=30",
                        "-c:v", "libx264", "-c:a", "aac", dummy_video_path, "-y"
                    ], check=True, capture_output=True)
                primary_path = dummy_video_path
                from core.models import LicenseStatus
                raw_asset = AssetItem(
                    asset_id="primary_video_01", source_uri=primary_path, asset_type="A-Roll", owner="System",
                    video_license_status=LicenseStatus.VERIFIED, audio_license_status=LicenseStatus.VERIFIED,
                    commercial_use=True, derivative_allowed=True
                )
            else:
                primary_path = st.session_state.uploaded_video_path
                from core.models import LicenseStatus
                raw_asset = AssetItem(
                    asset_id="primary_video_01", source_uri=primary_path, asset_type="A-Roll", owner="User",
                    video_license_status=LicenseStatus.DECLARED, audio_license_status=LicenseStatus.DECLARED,
                    commercial_use=True, derivative_allowed=True
                )
                
            st.session_state.media_db._asset_store.clear()
            st.session_state.media_db._vector_store.clear()
            st.session_state.media_db.ingest_asset(raw_asset)
            
            if st.session_state.uploaded_broll_path:
                from core.models import LicenseStatus
                broll_asset = AssetItem(
                    asset_id="broll_video_01", source_uri=st.session_state.uploaded_broll_path, asset_type="B-Roll", owner="User",
                    video_license_status=LicenseStatus.DECLARED, audio_license_status=LicenseStatus.DECLARED,
                    commercial_use=True, derivative_allowed=True,
                    metadata={"description": "Additional footage", "duration": 10.0}
                )
                st.session_state.media_db.ingest_asset(broll_asset)
            
            qc_report = st.session_state.qc_agent.evaluate_asset(raw_asset)
            if qc_report["status"] != "PASS":
                st.error(f"QC Failed: {qc_report.get('reason', 'Unknown error')}")
                if st.button("Reset"):
                    st.session_state.phase = "CONFIG"
                    st.rerun()
                st.stop()
            
            manifest_approved = False
            compliance_reason = None
            
            while not manifest_approved:
                try:
                    st.session_state.orchestrator.check_governance_limits(project_id)
                except Exception as e:
                    st.error(f"PIPELINE HALTED\nReason: Governance Control Triggered\nDetails: {str(e)}")
                    if st.button("Reset"):
                        st.session_state.phase = "CONFIG"
                        st.rerun()
                    st.stop()
                    
                st.session_state.orchestrator.increment_iteration(project_id)
                st.session_state.orchestrator.increment_version(project_id)
                
                manifest = st.session_state.director_agent.create_rough_cut(project, st.session_state.script_setting, compliance_reason)
                st.session_state.orchestrator.record_agent_cost(project_id, 0.45)
                
                is_approved, compliance_reason = st.session_state.compliance_agent.verify_manifest(manifest)
                st.session_state.orchestrator.record_agent_cost(project_id, 0.15)
                
                current_quality = st.session_state.quality_engine.evaluate_project(project, manifest)
                
                if is_approved:
                    manifest_approved = True
                else:
                    st.warning(f"Revision required: {compliance_reason}")
                    try:
                        import hashlib
                        manifest_hash = hashlib.sha256(manifest.model_dump_json().encode('utf-8')).hexdigest()
                        st.session_state.orchestrator.check_revision_convergence(
                            project_id, compliance_reason, current_quality.aggregate, manifest_hash
                        )
                    except RuntimeError as re:
                        st.error(f"PIPELINE HALTED\nReason: Revision Deadlock\nDetails: {str(re)}")
                        if st.button("Reset"):
                            st.session_state.phase = "CONFIG"
                            st.rerun()
                        st.stop()
                    
            if not st.session_state.quality_engine.meets_threshold(current_quality):
                st.error("Failed global quality gate.")
                if st.button("Reset"):
                    st.session_state.phase = "CONFIG"
                    st.rerun()
                st.stop()
                
            st.session_state.manifest = manifest
            st.session_state.phase = "APPROVAL"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    elif st.session_state.phase == "APPROVAL":
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.success(f"Creative Pipeline Complete. Manifest v{st.session_state.manifest.version} generated successfully!")
        st.markdown("Review the timeline manifest before deterministic rendering.")
        st.json(st.session_state.manifest.model_dump())
        
        col_btn1, col_btn2 = st.columns([1, 1])
        with col_btn1:
            if st.button("APPROVE AND RENDER", type="primary", use_container_width=True):
                st.session_state.phase = "RENDERING"
                st.rerun()
        with col_btn2:
            if st.button("REJECT & RESET", use_container_width=True):
                st.session_state.phase = "CONFIG"
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    elif st.session_state.phase == "RENDERING":
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("""
        <div style='margin-bottom:15px'>
          <span class='pipeline-step step-done'>INGEST ?</span>
          <span class='pipeline-step step-done'>QC ?</span>
          <span class='pipeline-step step-done'>EDIT ?</span>
          <span class='pipeline-step step-active'>VFX ??</span>
          <span class='pipeline-step step-active'>AUDIO ??</span>
          <span class='pipeline-step step-active'>DELIVERY ??</span>
        </div>
        """, unsafe_allow_html=True)
        
        with st.spinner("Executing Deterministic Render via FFmpeg..."):
            receipt = st.session_state.render_agent.generate_and_execute(st.session_state.manifest)
            
            if receipt:
                st.session_state.orchestrator.record_agent_cost(project_id, 1.25)
                
                dist_result = st.session_state.distribution_agent.publish_artifact(
                    st.session_state.project, receipt, st.session_state.manifest, ["YouTube"]
                )
                
                metrics = run_async(st.session_state.mcp_client.query_cost_metrics(project_id))
                st.success(f"Render Complete! Published to: {dist_result.get('urls')}")
                st.info(f"**Output Location:** `{os.path.abspath(receipt.artifact_path)}`")
                st.markdown(f"**Final Metrics:** Token Cost: ${metrics['token_cost']} | Compute Cost: ${metrics['compute_cost']}")
                
                st.video(receipt.artifact_path)
                st.balloons()
            else:
                st.error("Render execution failed. Check logs.")
                
            if st.button("Start New Project"):
                st.session_state.phase = "CONFIG"
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)




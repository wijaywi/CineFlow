"""
CineFlow AI: Autonomous Studio Pipeline - Simulation Execution

This script demonstrates the end-to-end execution of the multi-agent pipeline,
showcasing the Orchestrator, Agent Governance, Deterministic Rendering, 
and Observability mechanisms working in concert securely.
"""

import logging
import sys
import asyncio
import os
import secrets

if not os.environ.get("CINEFLOW_SIGNING_SECRET"):
    os.environ["CINEFLOW_SIGNING_SECRET"] = secrets.token_hex(32)

from core.agent_constitution import AgentConstitution
from core.orchestrator import Orchestrator, Agent
from core.media_intelligence import MediaIntelligenceDB
from core.models import AssetItem
from core.truth_graph import TruthGraph
from core.quality_scoring import QualityScoringEngine
from core.observability import ObservabilityEngine
from core.decision_replay import DecisionReplayEngine, AgentDecisionRecord

from core.optimization import OptimizationEngine
from agents.qc_agent import QCAgent
from agents.director_agent import DirectorAgent
from agents.compliance_agent import ComplianceAgent
from agents.render_agent import RenderAgent
from agents.distribution_agent import DistributionAgent

# Configure structured logging for the demonstration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_simulation():
    logger.info("Initializing CineFlow AI: Autonomous Studio Pipeline...")
    
    # 1. Initialize Core Infrastructure & Observability
    constitution = AgentConstitution(
        principles=["Preserve original media", "Maintain absolute factual integrity"],
        constraints=["Never exceed budget", "Never use unlicensed media"]
    )
    orchestrator = Orchestrator(constitution=constitution)
    media_db = MediaIntelligenceDB()
    quality_engine = QualityScoringEngine(media_db=media_db, minimum_passing_score=85.0)
    optimization_engine = OptimizationEngine()
    observability = ObservabilityEngine()
    replay_engine = DecisionReplayEngine()
    
    # 2. Instantiate and Register Agents
    qc_agent = QCAgent(media_db=media_db)
    compliance_agent = ComplianceAgent(media_db=media_db)
    
    # Initialize Grafana MCP Client for ADK tools
    from core.grafana_mcp import GrafanaMCPClient
    mcp_client = GrafanaMCPClient(endpoint="https://mcp-grafana.hosted.local", api_key="SIMULATED_KEY")
    
    # DirectorAgent now takes compliance and mcp_client as ADK Tools
    director_agent = DirectorAgent(media_db=media_db, compliance_agent=compliance_agent, mcp_client=mcp_client)
    
    render_agent = RenderAgent(media_db=media_db, constitution=constitution)
    distribution_agent = DistributionAgent(constitution=constitution)
    
    orchestrator.register_agent("QC", Agent("QC_Agent", "Quality Control"))
    orchestrator.register_agent("Director", Agent("Director_Agent", "Creative Direction"))
    orchestrator.register_agent("Compliance", Agent("Compliance_Agent", "Verification"))
    orchestrator.register_agent("Render", Agent("Render_Agent", "Execution"))
    orchestrator.register_agent("Distribution", Agent("Distribution_Agent", "Publishing"))

    # 3. Project Initialization
    project_id = "CF_PROJECT_000001"
    project = orchestrator.initialize_project(project_id=project_id, budget_limit=10.0)
    logger.info(f"Project {project_id} initialized with budget ${project.budget_limit}")


    # --- SIMULATION WORKFLOW ---
    
    # Step A: Ingest Asset (Simulated)
    logger.info("\n--- PHASE 1: INGESTION & QC ---")
    
    # Generate a dummy video file for real ffmpeg execution
    import subprocess
    dummy_video_path = "raw_video_01.mp4"
    if not __import__('os').path.exists(dummy_video_path):
        subprocess.run([
            "ffmpeg", "-f", "lavfi", "-i", "testsrc=duration=30:size=640x360:rate=30",
            "-f", "lavfi", "-i", "sine=frequency=1000:duration=30",
            "-c:v", "libx264", "-c:a", "aac", dummy_video_path, "-y"
        ], check=True, capture_output=True)
        
    dummy_broll_path = "broll_video_01.mp4"
    if not __import__('os').path.exists(dummy_broll_path):
        subprocess.run([
            "ffmpeg", "-f", "lavfi", "-i", "testsrc=duration=10:size=640x360:rate=30",
            "-f", "lavfi", "-i", "sine=frequency=500:duration=10",
            "-c:v", "libx264", "-c:a", "aac", dummy_broll_path, "-y"
        ], check=True, capture_output=True)

    raw_asset = AssetItem(
        asset_id="raw_video_01",
        source_uri=dummy_video_path,
        asset_type="A-Roll",
        owner="CineFlow Studios",
        license_type="commercial",
        commercial_use=True,
        derivative_allowed=True
    )
    media_db.ingest_asset(raw_asset)
    
    broll_asset = AssetItem(
        asset_id="broll_video_01",
        source_uri=dummy_broll_path,
        asset_type="B-Roll",
        owner="CineFlow Studios",
        license_type="commercial",
        commercial_use=True,
        derivative_allowed=True,
        metadata={"description": "Additional footage showing traffic and cars", "duration": 10.0}
    )
    media_db.ingest_asset(broll_asset)
    
    qc_report = qc_agent.evaluate_asset(raw_asset)
    if qc_report["status"] != "PASS":
        logger.error("Initial asset failed QC. Halting pipeline.")
        return
        
    # Step B: Creative Loop (Director <-> Compliance)
    logger.info("\n--- PHASE 2: CREATIVE DIRECTION & COMPLIANCE ---")
    
    logger.info("Delegating execution to ADK Director Agent...")
    
    orchestrator.increment_iteration(project_id)
    orchestrator.increment_version(project_id)
    observability.record_iterations(project_id, project.iteration_count)
    
    manifest = director_agent.create_rough_cut(
        project, 
        semantic_script="Explain the new product and show traffic. Product Y is waterproof."
    )
    
    if not manifest:
        logger.error("Agent failed to deliver a verified manifest. Escalating to Human.")
        return
        
    logger.info("Agent successfully delivered a verified manifest.")
    orchestrator.record_agent_cost(project_id, 0.60) # Combined cost for Director + Compliance
    observability.record_cost(project_id, "Director", 0.45)
    observability.record_cost(project_id, "Compliance", 0.15)
    
    # Log decision for auditability
    decision_record = AgentDecisionRecord(
        decision_id=f"dec_{project.iteration_count}",
        project_id=project_id,
        agent_name="Director_Agent",
        action="Generated Rough Cut via ADK",
        reasoning="Autonomously verified via Compliance and MCP tools.",
        evidence="Media Intelligence DB exact timestamps.",
        confidence=0.95
    )
    replay_engine.log_decision(decision_record)
        
    # Step C: Quality Gate
    logger.info("\n--- PHASE 3: GLOBAL QUALITY GATE ---")
    quality_score = quality_engine.evaluate_project(project, manifest)
    observability.update_quality_score(project_id, quality_score)
    
    if not quality_engine.meets_threshold(quality_score):
        logger.error("Project failed the global quality gate.")
        return
        
    # --- ADD MANUAL APPROVAL GATE ---
    est_cost = orchestrator.estimate_render_cost(manifest)
    print(f"\n[APPROVAL GATE] Manifest version {manifest.version} generated.")
    print(f"[APPROVAL GATE] Estimated render cost: ${est_cost:.2f}")
    
    import sys
    import os
    auto_approve = "--approve-render" in sys.argv or os.environ.get("CINEFLOW_AUTO_APPROVE_RENDER", "").lower() == "true"
    
    if auto_approve:
        logger.info("[APPROVAL GATE] Automated acceptance mode active. Proceeding to render.")
    else:
        approval = input("Proceed to render? (y/n): ")
        if approval.lower() != 'y':
            logger.warning("User rejected the manifest/cost. Halting.")
            return

    # Demonstrate saving and loading project state
    logger.info("Saving project state to JSON...")
    project.save()
    from core.models import ProjectState
    loaded_state = ProjectState.load(project.project_id)
    if loaded_state:
        logger.info(f"Successfully loaded project state for {loaded_state.project_id}")

    # Step D: Rendering
    logger.info("\n--- PHASE 4: DETERMINISTIC RENDERING ---")
    receipt = render_agent.generate_and_execute(manifest)
    if not receipt:
        logger.error("Render Agent failed to produce the final artifact.")
        return
        
    project.status = "RENDER_COMPLETE"
    orchestrator.record_agent_cost(project_id, 1.25) # Simulate compute cost
    observability.record_cost(project_id, "Render", 1.25)
    
    # Step E: Secure Distribution
    logger.info("\n--- PHASE 5: SECURE DISTRIBUTION ---")
    dist_result = distribution_agent.publish_artifact(project, receipt, manifest, ["YouTube"])
    if dist_result["success"]:
        logger.info(f"Published URLs: {dist_result['urls']}")
        observability.record_cost(project_id, "Distribution", dist_result["network_cost"])
    
    logger.info("\n--- PIPELINE EXECUTION COMPLETE ---")
    logger.info(f"Total Project Cost: ${project.current_cost:.2f}")
    logger.info(f"Total Iterations: {project.iteration_count}")
    
    # Grafana MCP Post-Flight Metrics Query
    async def run_mcp_metrics_query():
        metrics = await mcp_client.query_cost_metrics(project_id)
        logger.info(f"Grafana MCP Post-Flight Metrics: Token Cost: ${metrics['token_cost']}, Compute Cost: ${metrics['compute_cost']}, Total: ${metrics['total']}")
        
    asyncio.run(run_mcp_metrics_query())
    
    # Display an audit replay example
    logger.info("\n--- AUDIT REPLAY EXAMPLE ---")
    print(replay_engine.replay_decision("dec_1"))

if __name__ == "__main__":
    run_simulation()

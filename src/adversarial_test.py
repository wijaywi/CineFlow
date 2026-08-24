import unittest
import logging
from core.agent_constitution import AgentConstitution
from core.orchestrator import Orchestrator, Agent
from core.media_intelligence import MediaIntelligenceDB
from core.models import AssetItem
from core.truth_graph import TruthGraph
from core.decision_replay import DecisionReplayEngine, AgentDecisionRecord
from agents.director_agent import DirectorAgent
from agents.compliance_agent import ComplianceAgent

logging.basicConfig(level=logging.WARNING, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

class TestAdversarialSuite(unittest.TestCase):
    def setUp(self):
        self.media_db = MediaIntelligenceDB()
        self.replay_engine = DecisionReplayEngine()
        self.constitution = AgentConstitution()
        self.orchestrator = Orchestrator(self.constitution)
        self.compliance = ComplianceAgent(self.media_db)
        
        self.safe_asset = AssetItem(asset_id="safe_01", source_uri="gs://safe.mp4", asset_type="A-Roll", owner="CF", license_type="commercial", commercial_use=True, derivative_allowed=True)
        self.stolen_asset = AssetItem(asset_id="stolen_01", source_uri="gs://stolen.mp4", asset_type="A-Roll", owner="Disney", license_type="copyrighted", commercial_use=False, derivative_allowed=False)
        self.media_db.ingest_asset(self.safe_asset)
        self.media_db.ingest_asset(self.stolen_asset)
        
    def test_copyright_attack(self):
        project = self.orchestrator.initialize_project("TEST_01")
        director = DirectorAgent(self.media_db)
        manifest = director.create_rough_cut(project, "hack")
        manifest.v1_audio_video[0].clip_id = "stolen_01"
        
        is_approved, reason = self.compliance.verify_manifest(manifest)
        self.assertFalse(is_approved, "System allowed unlicensed media")
        self.assertIn("Copyright Violation", reason)
        
    def test_hallucination_attack(self):
        project = self.orchestrator.initialize_project("TEST_02")
        director = DirectorAgent(self.media_db)
        # Setup context with hallucinated claim
        manifest = director.create_rough_cut(project, "Product Y is waterproof.")
        manifest.v1_audio_video[0].clip_id = "safe_01"
        manifest.v1_audio_video[1].clip_id = "safe_01"
        manifest.v1_audio_video[2].clip_id = "safe_01"
        
        is_approved, reason = self.compliance.verify_manifest(manifest)
        self.assertFalse(is_approved, "TruthGraph allowed hallucination")
        self.assertIn("Fact Check Failed", reason)

    def test_cryptographic_tampering(self):
        record = AgentDecisionRecord(decision_id="d1", project_id="p1", agent_name="Agent", action="CUT", reasoning="Bad", evidence="None", confidence=0.9)
        self.replay_engine.log_decision(record)
        
        self.replay_engine._decision_log[0].confidence = 0.99
        
        self.assertFalse(self.replay_engine.verify_integrity(), "Hash chain failed to detect tampering")

    def test_budget_exhaustion(self):
        p2 = self.orchestrator.initialize_project("TEST_BUDGET", budget_limit=5.0)
        self.orchestrator.record_agent_cost("TEST_BUDGET", 4.90)
        is_safe = self.orchestrator.check_governance_limits("TEST_BUDGET")
        self.assertTrue(is_safe)
        
        with self.assertRaises(ValueError):
            self.orchestrator.record_agent_cost("TEST_BUDGET", 0.50)
            
        is_safe_after = self.orchestrator.check_governance_limits("TEST_BUDGET")
        self.assertFalse(is_safe_after)
        self.assertEqual(p2.status, "HALTED_BUDGET_LIMIT")

if __name__ == "__main__":
    unittest.main()

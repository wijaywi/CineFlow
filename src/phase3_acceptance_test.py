import os
import unittest
import sys
import subprocess
import shutil
import hashlib
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from core.models import ProjectState, TimelineManifest, EditDecision, AssetItem, RenderReceipt
from core.quality_scoring import QualityScoringEngine
from core.media_intelligence import MediaIntelligenceDB
from core.truth_graph import TruthGraph
from core.orchestrator import Orchestrator
from core.decision_replay import DecisionReplayEngine, AgentDecisionRecord
from core.agent_constitution import AgentConstitution
from agents.compliance_agent import ComplianceAgent
from agents.render_agent import RenderAgent
from agents.distribution_agent import DistributionAgent

class TestCineFlowAcceptance(unittest.TestCase):
    def setUp(self):
        self.db = MediaIntelligenceDB()
        self.constitution = AgentConstitution(principles=[], constraints=[])
        self.orchestrator = Orchestrator(constitution=self.constitution)
        self.quality = QualityScoringEngine(media_db=self.db)
        
        self.db.ingest_asset(AssetItem(
            asset_id='good_asset', source_uri='dummy.mp4', asset_type='A-Roll',
            owner='X', license_type='commercial', commercial_use=True, derivative_allowed=True
        ))
        self.db.ingest_asset(AssetItem(
            asset_id='bad_asset', source_uri='dummy.mp4', asset_type='A-Roll',
            owner='X', license_type='editorial', commercial_use=False, derivative_allowed=False
        ))
        
        if not os.path.exists("dummy.mp4"):
            subprocess.run(["ffmpeg", "-f", "lavfi", "-i", "color=c=black:s=640x360:d=2", "-c:v", "libx264", "-y", "dummy.mp4"], check=True, capture_output=True)

    # --- A. Schema ---
    def test_A_schema_invalid_time_range(self):
        with self.assertRaises(ValueError):
            EditDecision(clip_id='x', action="KEEP", start_time=10.0, end_time=5.0, reasoning="test")

    def test_A_schema_negative_time(self):
        with self.assertRaises(ValueError):
            EditDecision(clip_id='x', action="KEEP", start_time=-1.0, end_time=5.0, reasoning="test")

    def test_A_schema_invalid_confidence(self):
        with self.assertRaises(ValueError):
            EditDecision(clip_id='x', action="KEEP", start_time=1.0, end_time=5.0, reasoning="test", confidence=-0.5)
        with self.assertRaises(ValueError):
            EditDecision(clip_id='x', action="KEEP", start_time=1.0, end_time=5.0, reasoning="test", confidence=1.5)

    def test_A_schema_invalid_budget(self):
        with self.assertRaises(ValueError):
            ProjectState(project_id="test", budget_limit=-10.0)

    # --- B. Rights ---
    def test_B_rights_missing_media_db_fails_closed(self):
        q = QualityScoringEngine(media_db=None)
        m = TimelineManifest(project_id="t", version=1, v1_audio_video=[EditDecision(clip_id='good_asset', action="KEEP", start_time=0.0, end_time=1.0, reasoning="test")])
        score = q.evaluate_project(ProjectState(project_id="t"), m)
        self.assertEqual(score.compliance, 0.0)

    def test_B_rights_missing_asset_fails_closed(self):
        m = TimelineManifest(project_id="t", version=1, v1_audio_video=[EditDecision(clip_id='unknown_asset', action="KEEP", start_time=0.0, end_time=1.0, reasoning="test")])
        score = self.quality.evaluate_project(ProjectState(project_id="t"), m)
        self.assertEqual(score.compliance, 0.0)

    def test_B_rights_commercial_use_false_fails(self):
        m = TimelineManifest(project_id="t", version=1, v1_audio_video=[EditDecision(clip_id='bad_asset', action="KEEP", start_time=0.0, end_time=1.0, reasoning="test")])
        score = self.quality.evaluate_project(ProjectState(project_id="t"), m)
        self.assertEqual(score.compliance, 0.0)

    def test_B_rights_valid_asset_passes(self):
        m = TimelineManifest(project_id="t", version=1, v1_audio_video=[EditDecision(clip_id='good_asset', action="KEEP", start_time=0.0, end_time=1.0, reasoning="test")])
        score = self.quality.evaluate_project(ProjectState(project_id="t"), m)
        self.assertEqual(score.compliance, 100.0)

    # --- C. Truth ---
    def test_C_truth_variations(self):
        tg = TruthGraph()
        with patch.dict(os.environ, clear=True):
            self.assertEqual(tg.verify_claim("Product Y is waterproof").status, 'CONTRADICTED')
            self.assertEqual(tg.verify_claim("Product Y is waterproof.").status, 'CONTRADICTED')
            self.assertEqual(tg.verify_claim("product y is waterproof").status, 'CONTRADICTED')
            self.assertEqual(tg.verify_claim("PRODUCT Y IS WATERPROOF").status, 'CONTRADICTED')
            
            self.assertEqual(tg.verify_claim("Product Y is water-resistant").status, 'SUPPORTED')
            self.assertEqual(tg.verify_claim("Some completely unknown thing").status, 'UNVERIFIED')

    def test_C_truth_no_gemini_api_key_does_not_crash(self):
        tg = TruthGraph()
        with patch.dict(os.environ, clear=True):
            self.assertEqual(tg.verify_claim("Product Y is waterproof").status, 'CONTRADICTED')

    def test_C_truth_missing_dependency_handled(self):
        tg = TruthGraph()
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'fake_key'}):
            with patch.dict(sys.modules, {'google.genai': None}): 
                self.assertEqual(tg.verify_claim("Product Y is waterproof").status, 'CONTRADICTED')
                
    def test_C_truth_api_runtime_exception(self):
        tg = TruthGraph()
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'fake_key'}):
            import sys
            from unittest.mock import MagicMock
            mock_genai = MagicMock()
            mock_genai.Client.side_effect = Exception("API Error")
            with patch.dict(sys.modules, {'google.genai': mock_genai}):
                self.assertNotEqual(tg.verify_claim("Product Y is waterproof").status, 'SUPPORTED')

    # --- D. Governance ---
    def test_D_governance_budget_exceeded(self):
        proj = self.orchestrator.initialize_project("test_budget", budget_limit=1.0)
        proj.current_cost = 0.9
        self.assertTrue(self.orchestrator.check_governance_limits(proj.project_id))
        proj.current_cost = 1.1
        self.assertFalse(self.orchestrator.check_governance_limits(proj.project_id))

    def test_D_governance_negative_cost(self):
        proj = self.orchestrator.initialize_project("test_neg", budget_limit=1.0)
        self.assertFalse(self.orchestrator.check_governance_limits(proj.project_id, estimated_cost=-1.0))

    def test_D_governance_nan_cost(self):
        proj = self.orchestrator.initialize_project("test_nan", budget_limit=1.0)
        self.assertFalse(self.orchestrator.check_governance_limits(proj.project_id, estimated_cost=float('nan')))

    def test_D_governance_infinity_cost(self):
        proj = self.orchestrator.initialize_project("test_inf", budget_limit=1.0)
        self.assertFalse(self.orchestrator.check_governance_limits(proj.project_id, estimated_cost=float('inf')))

    def test_D_governance_iteration_limit(self):
        proj = self.orchestrator.initialize_project("test_iter", budget_limit=10.0, max_iterations=5)
        proj.iteration_count = 5
        self.assertFalse(self.orchestrator.check_governance_limits(proj.project_id))

    def test_D_governance_low_confidence(self):
        proj = self.orchestrator.initialize_project("test_conf")
        self.assertTrue(self.orchestrator.check_confidence_threshold(proj.project_id, 0.9, "a"))
        self.assertFalse(self.orchestrator.check_confidence_threshold(proj.project_id, 0.5, "a"))

    def test_D_governance_invalid_state(self):
        proj = self.orchestrator.initialize_project("test_halted")
        proj.status = "HALTED_BY_USER"
        self.assertFalse(self.orchestrator.check_governance_limits(proj.project_id))

    # --- E. Decision Integrity ---
    def test_E_audit_integrity(self):
        replay = DecisionReplayEngine()
        rec = AgentDecisionRecord(decision_id='d1', project_id='p1', agent_name='a1', action='KEEP', reasoning='r', evidence='e', confidence=0.9)
        replay.log_decision(rec)
        self.assertTrue(replay.verify_integrity())
        self.assertIsNotNone(replay.replay_decision('d1'))
        
        # Tamper confidence
        replay._decision_log[0].confidence = 0.1
        self.assertFalse(replay.verify_integrity())
        
        # Rebuild correctly
        replay = DecisionReplayEngine()
        rec = AgentDecisionRecord(decision_id='d1', project_id='p1', agent_name='a1', action='KEEP', reasoning='r', evidence='e', confidence=0.9)
        replay.log_decision(rec)
        
        # Tamper reasoning
        replay._decision_log[0].reasoning = 'tampered'
        self.assertFalse(replay.verify_integrity())
        
        # Hash chain manipulation
        replay = DecisionReplayEngine()
        rec = AgentDecisionRecord(decision_id='d1', project_id='p1', agent_name='a1', action='KEEP', reasoning='r', evidence='e', confidence=0.9)
        replay.log_decision(rec)
        replay._hash_chain[1] = 'invalid_hash'
        self.assertFalse(replay.verify_integrity())

    # --- F. Rendering ---
    def test_F_rendering_valid_manifest(self):
        os.environ['CINEFLOW_SIGNING_SECRET'] = 'test_secret'
        render_agent = RenderAgent(self.db, self.constitution)
        m = TimelineManifest(project_id="test_render", version=1, v1_audio_video=[EditDecision(clip_id='good_asset', action="KEEP", start_time=0.0, end_time=1.0, reasoning="test")])
        receipt = render_agent.generate_and_execute(m)
        self.assertIsNotNone(receipt)
        self.assertTrue(os.path.exists(receipt.artifact_path))
        self.assertGreater(os.path.getsize(receipt.artifact_path), 0)
        # ffprobe
        proc = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", receipt.artifact_path], capture_output=True, text=True)
        self.assertGreater(float(proc.stdout.strip()), 0.0)
        # SHA256 matches
        import hashlib
        with open(receipt.artifact_path, "rb") as f:
            self.assertEqual(receipt.artifact_sha256, hashlib.sha256(f.read()).hexdigest())

    def test_F_rendering_missing_asset(self):
        render_agent = RenderAgent(self.db, self.constitution)
        m = TimelineManifest(project_id="test_render_2", version=1, v1_audio_video=[EditDecision(clip_id='missing', action="KEEP", start_time=0.0, end_time=1.0, reasoning="test")])
        receipt = render_agent.generate_and_execute(m)
        self.assertIsNone(receipt)

    def test_F_rendering_empty_manifest(self):
        render_agent = RenderAgent(self.db, self.constitution)
        m = TimelineManifest(project_id="test_render_3", version=1)
        receipt = render_agent.generate_and_execute(m)
        self.assertIsNone(receipt)

    # --- G. Distribution ---
    def test_G_distribution_checks(self):
        dist = DistributionAgent(self.constitution)
        proj = ProjectState(project_id="t")
        m = TimelineManifest(project_id="t", version=1)
        manifest_hash = hashlib.sha256(m.model_dump_json().encode('utf-8')).hexdigest()
        
        rec = RenderReceipt(project_id="t", manifest_version=1, manifest_hash=manifest_hash, artifact_path="dummy.mp4", artifact_sha256="sh", render_job_id="j", ffmpeg_exit_code=0, executor_signature="s")
        
        # Before RENDER_COMPLETE
        self.assertFalse(dist.publish_artifact(proj, rec, m, ["YouTube"])["success"])
        
        proj.status = "RENDER_COMPLETE"
        
        # DistributionAgent(None) test
        dist_no_const = DistributionAgent(None)
        proj.status = "PLANNED"
        self.assertFalse(dist_no_const.publish_artifact(proj, rec, m, ["YouTube"])["success"])
        proj.status = "RENDER_COMPLETE"
        
        # Fabricated VALIDATED receipt (different hash)
        rec.status = "INVALID"
        self.assertFalse(dist.publish_artifact(proj, rec, m, ["YouTube"])["success"])
        rec.status = "VALIDATED"
        
        # ffmpeg_exit_code != 0
        rec.ffmpeg_exit_code = 999
        self.assertFalse(dist.publish_artifact(proj, rec, m, ["YouTube"])["success"])
        rec.ffmpeg_exit_code = 0
        
        # Invalid missing artifact
        rec.artifact_path = "non_existent.mp4"
        self.assertFalse(dist.publish_artifact(proj, rec, m, ["YouTube"])["success"])
        
        # Modified artifact (hash mismatch)
        rec.artifact_path = "dummy.mp4"
        self.assertFalse(dist.publish_artifact(proj, rec, m, ["YouTube"])["success"])
        
        # Wrong manifest hash
        rec.manifest_hash = "wrong_hash"
        self.assertFalse(dist.publish_artifact(proj, rec, m, ["YouTube"])["success"])
        rec.manifest_hash = manifest_hash
        
        # Fake executor signature
        with open("dummy.mp4", "rb") as f:
            rec.artifact_sha256 = hashlib.sha256(f.read()).hexdigest()
        
        import hmac
        os.environ["CINEFLOW_SIGNING_SECRET"] = "test_secret"
        expected_sig = hmac.new(b"test_secret", f"{manifest_hash}:{rec.artifact_sha256}".encode(), hashlib.sha256).hexdigest()
        rec.executor_signature = "fake_sig"
        self.assertFalse(dist.publish_artifact(proj, rec, m, ["YouTube"])["success"])
        
        # Valid receipt succeeds
        rec.executor_signature = expected_sig
        self.assertTrue(dist.publish_artifact(proj, rec, m, ["YouTube"])["success"])

    # --- H. Quality Gate ---
    def test_H_quality_gate(self):
        proj = ProjectState(project_id="t")
        
        # Helper for scoring
        def check_score(context_text, expect_pass):
            m = TimelineManifest(project_id="t", version=1, context=context_text, v1_audio_video=[EditDecision(clip_id='good_asset', action="KEEP", start_time=0.0, end_time=1.0, reasoning="test")])
            with patch.dict(os.environ, clear=True):
                score = self.quality.evaluate_project(proj, m)
                meets = self.quality.meets_threshold(score)
                self.assertEqual(meets, expect_pass, f"Context '{context_text}' expected pass={expect_pass} but got {meets}")

        # Healthy (Supported)
        check_score("Product Y is water-resistant.", True)
        
        # Contradicted
        check_score("Product Y is waterproof.", False)
        
        # Unknown factual claim / Arbitrary claim not in KB
        check_score("The moon is made of cheese.", False)
        check_score("This product cures cancer.", False)
        
        # Multiple claims where one is contradicted
        check_score("Product Y is water-resistant. Product Y is waterproof.", False)
        
        # Multiple claims where one is unverified
        check_score("Company X revenue increased 42%. Also, we opened a new store on Mars.", False)
        
        # Punctuation/case variants
        check_score("pRoDuCt y iS wATeRproOF!", False)
        check_score("Is Product Y waterproof?", False) # Depends on extraction, if extracted it should fail
        
        # Ambiguous claims / Extraction failure
        # If extraction produces nothing but text exists, it fails.
        check_score("Just some random text without clear claims.", False)
        
        # Missing db
        q_no_db = QualityScoringEngine(media_db=None)
        m_good = TimelineManifest(project_id="t", version=1, context="Product Y is water-resistant.", v1_audio_video=[EditDecision(clip_id='good_asset', action="KEEP", start_time=0.0, end_time=1.0, reasoning="test")])
        self.assertFalse(q_no_db.meets_threshold(q_no_db.evaluate_project(proj, m_good)))
        
        # Rights violation
        m_bad_rights = TimelineManifest(project_id="t", version=1, context="Product Y is water-resistant.", v1_audio_video=[EditDecision(clip_id='bad_asset', action="KEEP", start_time=0.0, end_time=1.0, reasoning="test")])
        self.assertFalse(self.quality.meets_threshold(self.quality.evaluate_project(proj, m_bad_rights)))
        
        # Low aggregate score
        self.quality.minimum_passing_score = 101.0
        self.assertFalse(self.quality.meets_threshold(self.quality.evaluate_project(proj, m_good)))


    # --- I. Revision Deadlock ---
    def test_I_revision_deadlock_detection(self):
        from core.orchestrator import Orchestrator
        from core.agent_constitution import AgentConstitution
        orch = Orchestrator(AgentConstitution())
        proj = orch.initialize_project("test_deadlock")
        
        # 1st failure
        orch.check_revision_convergence(proj.project_id, "Fact check failed", 50.0, "hash1")
        # 2nd failure
        orch.check_revision_convergence(proj.project_id, "Fact check failed", 50.0, "hash2")
        
        # 3rd identical failure raises deadlock BEFORE budget exhausts
        with self.assertRaisesRegex(RuntimeError, "REVISION_DEADLOCK"):
            orch.check_revision_convergence(proj.project_id, "Fact check failed", 50.0, "hash3")
            
        self.assertEqual(proj.status, "REVISION_DEADLOCK")
        
    def test_I_revision_deadlock_reset_on_improvement(self):
        from core.orchestrator import Orchestrator
        from core.agent_constitution import AgentConstitution
        orch = Orchestrator(AgentConstitution())
        proj = orch.initialize_project("test_deadlock_reset")
        
        orch.check_revision_convergence(proj.project_id, "Fact check failed", 50.0, "hash1")
        orch.check_revision_convergence(proj.project_id, "Fact check failed", 50.0, "hash2")
        
        # Materially improved quality (50.0 -> 80.0) even if reason is the same should not trigger deadlock
        orch.check_revision_convergence(proj.project_id, "Fact check failed", 80.0, "hash3")
        
        # And if the failure reason changes, it resets
        orch.check_revision_convergence(proj.project_id, "Different reason", 80.0, "hash4")

    def test_I_semantic_boundary_creative_instructions(self):
        from core.truth_graph import TruthGraph
        tg = TruthGraph()
        
        # Creative instructions skipped
        self.assertEqual(tg.extract_claims("Explain the new product."), [])
        self.assertEqual(tg.extract_claims("Show traffic footage."), [])
        self.assertEqual(tg.extract_claims("Make it pop!"), [])
        
        # Unsupported factual claim extracted
        claims = tg.extract_claims("The moon is made of cheese.")
        self.assertIn("The moon is made of cheese", claims)
        
        # Mixed
        claims_mixed = tg.extract_claims("Show traffic footage. The moon is made of cheese.")
        self.assertEqual(len(claims_mixed), 1)
        self.assertIn("The moon is made of cheese", claims_mixed)

if __name__ == '__main__':
    import os
    if 'GEMINI_API_KEY' in os.environ:
        del os.environ['GEMINI_API_KEY']
    import unittest
    unittest.main(verbosity=2)

import sys
sys.path.insert(0, 'D:\\zzzzzzzzzzz AntiGravity\\Bounty\\src2\\src')
from agents.director_agent import DirectorAgent
from agents.compliance_agent import ComplianceAgent
from core.truth_graph import TruthGraph
from core.models import ProjectState

class DummyDB:
    def search_broll(self, **kwargs): return []
    def get_asset(self, clip_id): 
        class DummyAsset:
            commercial_use = True
            derivative_allowed = True
            asset_id = clip_id
        return DummyAsset()
    _asset_store = {}

db = DummyDB()
director = DirectorAgent(db)
comp = ComplianceAgent(db)

proj = ProjectState(project_id='test', budget_limit=10)
semantic_script = 'Explain the new product and show traffic. Product Y is waterproof.'
manifest_approved = False
compliance_reason = None
from core.orchestrator import Orchestrator
from core.agent_constitution import AgentConstitution
orch = Orchestrator(AgentConstitution())

for i in range(5):
    proj.iteration_count += 1
    proj.current_version += 1
    
    print(f'\n--- Iteration {i+1} ---')
    manifest = director.create_rough_cut(proj, semantic_script, compliance_reason)
    print(f'> Director Agent generated manifest v{manifest.version}')
    print(f'Context: {manifest.context}')
    
    is_approved, compliance_reason = comp.verify_manifest(manifest)
    print(f'> Compliance Check: {"Passed" if is_approved else "Failed"}')
    
    if is_approved:
        manifest_approved = True
        break
    else:
        print(f'Revision required: {compliance_reason}')
        import hashlib
        m_hash = hashlib.sha256(manifest.model_dump_json().encode()).hexdigest()
        try:
            orch.check_revision_convergence(proj.project_id, compliance_reason, 50.0, m_hash)
        except RuntimeError as e:
            print(f"PIPELINE HALTED: REVISION_DEADLOCK")
            break

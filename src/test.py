import sys
sys.path.insert(0, 'D:\\zzzzzzzzzzz AntiGravity\\Bounty\\src2\\src')
from agents.director_agent import DirectorAgent
from core.models import ProjectState

class DummyDB:
    def search_broll(self, **kwargs): return []
    _asset_store = {}

db = DummyDB()
director = DirectorAgent(db)

proj = ProjectState(project_id='test', budget_limit=10)
script = 'Explain the new product and show traffic. Product Y is waterproof.'
reason1 = "Fact Check Failed: Unverified claim 'Product Y is waterproof'"

manifest2 = director.create_rough_cut(proj, script, reason1)
print('Manifest 2 context:', manifest2.context)

import sys
sys.path.insert(0, 'D:\\zzzzzzzzzzz AntiGravity\\Bounty\\src2\\src')
from core.truth_graph import TruthGraph

truth = TruthGraph()
print('Claims:', truth.extract_claims('Explain the new product and show traffic. Product Y is water-resistant.'))

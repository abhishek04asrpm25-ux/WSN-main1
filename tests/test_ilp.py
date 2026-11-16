
import networkx as nx
from simulation.algorithms.ilp_routing import ILPRouting

G = nx.Graph()

G.add_edge(1, 2, weight=10)
G.add_edge(1, 3, weight=20)
G.add_edge(2, 3, weight=8)
G.add_edge(2, "BS", weight=15)
G.add_edge(3, "BS", weight=12)

selected_ch_ids = [1, 2, 3]

algorithm = ILPRouting()
result = algorithm.solve(G, selected_ch_ids)

print("Algorithm:", result["algorithm"])
print("Parent map:", result["parent_map"])
print("Routes:", result["validation"]["routes"])
print("Total distance:", result["validation"]["total_distance"])
print("Valid:", result["validation"]["valid"])

assert result["validation"]["valid"]
assert len(result["parent_map"]) == 3

print("\nILP ROUTING TEST PASSED")

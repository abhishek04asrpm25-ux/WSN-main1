
from simulation.network import generate_network
from simulation.algorithms.ann_ch_selection import (
    ANNClusterHeadSelector,
)

from pathlib import Path
import json


ROOT = Path(__file__).resolve().parents[1]

with open(ROOT / "input" / "simulation_config.json") as file:
    config = json.load(file)

network = generate_network(
    config,
    communication_range=60,
)

selector = ANNClusterHeadSelector(
    num_cluster_heads=10,
    random_seed=42,
)

training_result = selector.train()

result = selector.select_cluster_heads(
    nodes=network["nodes"],
    base_station=network["base_station"],
)

selected_ids = result["selected_ch_ids"]

print("Training result:", training_result)
print("Selected CH IDs:", selected_ids)
print("Number of CHs:", len(selected_ids))
print("Algorithm:", result["algorithm"])

assert len(selected_ids) == 10
assert len(set(selected_ids)) == 10

alive_ids = {
    node["id"]
    for node in network["nodes"]
    if node.get("alive", True)
}

assert set(selected_ids).issubset(alive_ids)

print("\nANN CLUSTER-HEAD SELECTION TEST PASSED")

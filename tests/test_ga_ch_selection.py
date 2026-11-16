
import json
from pathlib import Path

from simulation.network import generate_network
from simulation.algorithms.ga_ch_selection import (
    GeneticAlgorithmCHSelector
)


# Project root directory
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Load configuration
config_path = PROJECT_ROOT / "input" / "simulation_config.json"

with open(config_path, "r", encoding="utf-8") as file:
    config = json.load(file)


# Use the configured communication range if available.
# Otherwise, use the first candidate range from Phase 1.
communication_range = config.get("communication_range_m")

if communication_range is None:
    communication_range = config.get(
        "candidate_communication_ranges_m",
        [60]
    )[0]


# Generate a fresh network
network = generate_network(
    config,
    communication_range
)


# Create GA selector
selector = GeneticAlgorithmCHSelector(
    config,
    communication_range
)


# Run GA
result = selector.select_cluster_heads(network)


print("\n========== GA CLUSTER HEAD SELECTION ==========")

print("Communication range:", communication_range, "m")
print("Selected CH IDs:", result["selected_ch_ids"])
print("Number of selected CHs:", len(result["selected_ch_ids"]))
print("Best fitness:", round(result["fitness"], 4))

print("\n========== CLUSTERING METRICS ==========")

for metric, value in result["metrics"].items():
    if isinstance(value, float):
        print(f"{metric}: {value:.4f}")
    else:
        print(f"{metric}: {value}")

print("\n========== CLUSTER MEMBERS ==========")

for ch_id, members in result["cluster_members"].items():
    print(f"CH {ch_id}: {members}")
    print("Cluster size:", len(members))

print("\n========== GA CONVERGENCE ==========")

print("First generation fitness:",
      round(result["history"][0]["overall_best_fitness"], 4))

print("Last generation fitness:",
      round(result["history"][-1]["overall_best_fitness"], 4))


# Basic correctness checks
assert len(result["selected_ch_ids"]) == selector.num_cluster_heads
assert len(set(result["selected_ch_ids"])) == selector.num_cluster_heads

alive_ids = {
    node["id"]
    for node in network["nodes"]
    if node.get("alive", True) and node.get("residual_energy", 0) > 0
}

assert set(result["selected_ch_ids"]).issubset(alive_ids)

for ch_id in result["selected_ch_ids"]:
    assert network["nodes"][ch_id]["is_cluster_head"] is True

print("\nGA Cluster Head Selection Test: PASSED")

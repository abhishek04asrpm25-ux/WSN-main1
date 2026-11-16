
import json
from pathlib import Path

from simulation.network import generate_network
from simulation.algorithms.ga_ch_selection import (
    GeneticAlgorithmCHSelector
)
from simulation.clustering import ClusterManager
from simulation.packet_generation import PacketGenerator


# --------------------------------------------------
# 1. Load project configuration
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

config_path = PROJECT_ROOT / "input" / "simulation_config.json"

with open(config_path, "r", encoding="utf-8") as file:
    config = json.load(file)


# --------------------------------------------------
# 2. Determine communication range
# --------------------------------------------------

communication_range = config.get("communication_range_m")

if communication_range is None:
    candidate_ranges = config.get(
        "candidate_communication_ranges_m",
        config.get("candidate_communication_ranges", [60])
    )
    communication_range = candidate_ranges[0]


# --------------------------------------------------
# 3. Deploy the network
# --------------------------------------------------

network = generate_network(
    config,
    communication_range
)


# --------------------------------------------------
# 4. Select Cluster Heads using GA
# --------------------------------------------------

ga_selector = GeneticAlgorithmCHSelector(
    config,
    communication_range
)

ga_result = ga_selector.select_cluster_heads(network)

selected_ch_ids = ga_result["selected_ch_ids"]


# --------------------------------------------------
# 5. Form clusters
# --------------------------------------------------

cluster_manager = ClusterManager(
    communication_range
)

clustering_result = cluster_manager.form_clusters(
    network,
    selected_ch_ids
)


# --------------------------------------------------
# 6. Generate packets and aggregate cluster data
# --------------------------------------------------

packet_generator = PacketGenerator(config)

packet_result = packet_generator.generate_packets(
    network,
    clustering_result,
    round_number=1
)


# --------------------------------------------------
# 7. Display results
# --------------------------------------------------

print("\n========== PHASE 4: CLUSTER FORMATION ==========")

print("Communication range:", communication_range, "m")
print("Selected CH IDs:", selected_ch_ids)

print(
    "Total alive nodes:",
    clustering_result["total_alive_nodes"]
)

print(
    "Total assigned nodes:",
    clustering_result["total_assigned_nodes"]
)

print(
    "Unassigned nodes:",
    clustering_result["unassigned_node_ids"]
)

print(
    "Cluster coverage:",
    round(clustering_result["coverage"] * 100, 2),
    "%"
)


print("\n========== CLUSTER MEMBERSHIP ==========")

for ch_id, members in clustering_result["clusters"].items():
    print(f"CH {ch_id}: {members}")
    print("Cluster size:", len(members))


print("\n========== PACKET GENERATION ==========")

for key, value in packet_result["summary"].items():
    print(f"{key}: {value}")


print("\n========== CLUSTER AGGREGATION ==========")

for ch_id, details in packet_result["cluster_details"].items():
    print(f"\nCluster Head: {ch_id}")
    print("Member nodes:", details["member_node_ids"])
    print("Input packet count:", details["input_packet_count"])
    print("Total input bits:", details["input_bits"])
    print(
        "Aggregated packet size:",
        details["aggregated_packet_bits"],
        "bits"
    )


# --------------------------------------------------
# 8. Automatic correctness checks
# --------------------------------------------------

node_map = {
    node["id"]: node
    for node in network["nodes"]
}

alive_ids = {
    node["id"]
    for node in network["nodes"]
    if node.get("alive", True)
    and node.get("residual_energy", 0) > 0
}

# Every selected CH must be alive.
assert set(selected_ch_ids).issubset(alive_ids)

# Every selected CH must have its own cluster.
assert set(selected_ch_ids) == set(
    clustering_result["clusters"].keys()
)

# Every cluster must contain its CH.
for ch_id, members in clustering_result["clusters"].items():
    assert ch_id in members

# A normal node must belong to only one cluster.
all_assigned_members = [
    member_id
    for members in clustering_result["clusters"].values()
    for member_id in members
]

assert len(all_assigned_members) == len(set(all_assigned_members))

# Every assigned normal node must be within range of its CH.
for ch_id, members in clustering_result["clusters"].items():
    ch = node_map[ch_id]

    for member_id in members:
        if member_id == ch_id:
            continue

        node = node_map[member_id]

        distance = cluster_manager.calculate_distance(node, ch)

        assert distance <= communication_range

# One original packet must be generated per alive node.
assert len(packet_result["generated_packets"]) == len(alive_ids)

# One aggregated packet must be generated per cluster.
assert len(packet_result["aggregated_packets"]) == len(
    clustering_result["clusters"]
)

# All assigned nodes must contribute one packet to a cluster.
total_cluster_input_packets = sum(
    details["input_packet_count"]
    for details in packet_result["cluster_details"].values()
)

assert total_cluster_input_packets == (
    clustering_result["total_assigned_nodes"]
)

# Pending packets must belong to unassigned nodes.
assert set(packet_result["pending_packets"].keys()) == set(
    clustering_result["unassigned_node_ids"]
)

# Each aggregate must contain the correct number of source nodes.
for ch_id, aggregate in packet_result["aggregated_packets"].items():
    assert aggregate["input_packet_count"] == len(
        aggregate["source_node_ids"]
    )

    assert aggregate["packet_size_bits"] > 0

print("\nPHASE 4 TEST: PASSED")

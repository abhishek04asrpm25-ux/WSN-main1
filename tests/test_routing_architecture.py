
import json
from pathlib import Path

import networkx as nx  # type: ignore[import-not-found]

from simulation.network import generate_network
from simulation.algorithms.ga_ch_selection import (
    GeneticAlgorithmCHSelector
)
from simulation.clustering import ClusterManager
from simulation.routing import RoutingGraphBuilder
from simulation.algorithms.routing_interface import (
    RoutingResultValidator
)


# --------------------------------------------------
# 1. Load configuration
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

config_path = PROJECT_ROOT / "input" / "simulation_config.json"

with open(config_path, "r", encoding="utf-8") as file:
    config = json.load(file)


# --------------------------------------------------
# 2. Get communication range
# --------------------------------------------------

communication_range = config.get("communication_range_m")

if communication_range is None:
    candidate_ranges = config.get(
        "candidate_communication_ranges_m",
        config.get("candidate_communication_ranges", [60])
    )
    communication_range = candidate_ranges[0]


# --------------------------------------------------
# 3. Deploy network
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

cluster_result = cluster_manager.form_clusters(
    network,
    selected_ch_ids
)


# --------------------------------------------------
# 6. Build global routing graph
# --------------------------------------------------

graph_builder = RoutingGraphBuilder(
    communication_range
)

graph_result = graph_builder.build_graph(
    network,
    config,
    selected_ch_ids
)

graph = graph_result["graph"]


# --------------------------------------------------
# 7. Display graph information
# --------------------------------------------------

graph_builder.print_graph_summary(graph_result)


# --------------------------------------------------
# 8. Check communication range of every link
# --------------------------------------------------

for node_a, node_b, edge_data in graph.edges(data=True):
    assert edge_data["distance"] <= communication_range + 1e-9
    assert edge_data["weight"] == edge_data["distance"]

    assert edge_data["link_type"] in (
        "CH_TO_CH",
        "CH_TO_BS"
    )


# --------------------------------------------------
# 9. Check graph node information
# --------------------------------------------------

assert graph.has_node("BS")

assert set(selected_ch_ids).issubset(
    set(graph.nodes)
)

assert graph_result["reachable_ch_ids"] == [
    ch_id for ch_id in selected_ch_ids
    if nx.has_path(graph, ch_id, "BS")
]

assert set(graph_result["reachable_ch_ids"]).isdisjoint(
    set(graph_result["unreachable_ch_ids"])
)

assert set(graph_result["reachable_ch_ids"]) | set(
    graph_result["unreachable_ch_ids"]
) == set(selected_ch_ids)


# --------------------------------------------------
# 10. Build a test parent map for reachable CHs
# --------------------------------------------------

# This uses NetworkX shortest paths ONLY to test the
# common route-result format and validator.
# It is not our final Dijkstra implementation.

test_parent_map = {}

for ch_id in graph_result["reachable_ch_ids"]:
    path = nx.shortest_path(
        graph,
        source=ch_id,
        target="BS",
        weight="weight"
    )

    test_parent_map[ch_id] = path[1]


# --------------------------------------------------
# 11. Validate the test routes
# --------------------------------------------------

if graph_result["reachable_ch_ids"]:

    validation = RoutingResultValidator.validate_parent_map(
        graph,
        graph_result["reachable_ch_ids"],
        test_parent_map,
        "BS"
    )

    assert validation["valid"] is True
    assert len(validation["errors"]) == 0

    for ch_id, route in validation["routes"].items():
        assert route[0] == ch_id
        assert route[-1] == "BS"

    print("\nTEST ROUTES:")

    for ch_id, route in validation["routes"].items():
        print(f"CH {ch_id}: {' -> '.join(map(str, route))}")

    print(
        "\nTest routing tree distance:",
        round(validation["total_distance"], 3),
        "m"
    )

else:
    print(
        "\nNo CH can currently reach the BS. "
        "The graph was built correctly, but no route is feasible."
    )


# --------------------------------------------------
# 12. Final correctness checks
# --------------------------------------------------

assert graph.number_of_nodes() == len(selected_ch_ids) + 1

assert len(graph_result["reachable_ch_ids"]) + len(
    graph_result["unreachable_ch_ids"]
) == len(selected_ch_ids)

print("\nPHASE 5 ROUTING ARCHITECTURE TEST: PASSED")

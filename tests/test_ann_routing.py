
import networkx as nx

from simulation.algorithms.ann_routing import ANNRouting


def test_ann_routing():
    graph = nx.Graph()

    graph.add_weighted_edges_from([
        ("BS", 10, 5),
        ("BS", 20, 8),
        (10, 30, 3),
        (20, 30, 2),
        (10, 40, 4),
        (20, 40, 3),
        (30, 40, 2),
    ])

    # Add residual energy to sensor nodes.
    for node in [10, 20, 30, 40]:
        graph.nodes[node]["residual_energy"] = 0.5

    selected_ch_ids = [10, 20, 30, 40]

    algorithm = ANNRouting(
        training_samples=5000,
        random_seed=42,
    )

    result = algorithm.solve(
        graph=graph,
        selected_ch_ids=selected_ch_ids,
        bs_id="BS",
    )

    print("\n========== ANN ROUTING TEST ==========")
    print("Algorithm:", result["algorithm"])
    print("Training:", algorithm.training_result)
    print("Parent map:", result["parent_map"])
    print("Routes:", result["validation"]["routes"])
    print("Total distance:", result["validation"]["total_distance"])
    print("Validation:", result["validation"]["valid"])

    assert result["validation"]["valid"]
    assert set(result["parent_map"]) == set(selected_ch_ids)

    for route in result["validation"]["routes"].values():
        assert route[-1] == "BS"

    print("\nANN ROUTING TEST PASSED")


if __name__ == "__main__":
    test_ann_routing()

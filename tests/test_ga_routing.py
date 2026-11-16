
import networkx as nx

from simulation.algorithms.ga_routing import GARouting


def test_ga_routing():
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

    selected_ch_ids = [10, 20, 30, 40]

    algorithm = GARouting(
        population_size=40,
        generations=50,
        random_seed=42,
    )

    result = algorithm.solve(
        graph=graph,
        selected_ch_ids=selected_ch_ids,
        bs_id="BS",
    )

    print("\n========== GA ROUTING TEST ==========")
    print("Algorithm:", result["algorithm"])
    print("Parent map:", result["parent_map"])
    print("Routes:", result["validation"]["routes"])
    print("Total distance:", result["validation"]["total_distance"])
    print("Validation:", result["validation"]["valid"])

    assert result["validation"]["valid"]
    assert set(result["parent_map"]) == set(selected_ch_ids)

    for route in result["validation"]["routes"].values():
        assert route[-1] == "BS"

    print("\nGA ROUTING TEST PASSED")


if __name__ == "__main__":
    test_ga_routing()

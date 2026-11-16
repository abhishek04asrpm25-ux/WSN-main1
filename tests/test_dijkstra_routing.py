
import networkx as nx

from simulation.algorithms.dijkstra_routing import DijkstraRouting


def test_dijkstra_routing():

    # Create a NetworkX graph.
    graph = nx.Graph()

    # Add base station and cluster heads.
    graph.add_nodes_from(["BS", 1, 2, 3, 4])

    # Add communication links with distances.
    graph.add_edge("BS", 1, weight=10)
    graph.add_edge("BS", 2, weight=25)
    graph.add_edge(1, 2, weight=8)
    graph.add_edge(1, 3, weight=20)
    graph.add_edge(2, 3, weight=6)
    graph.add_edge(3, 4, weight=7)

    selected_ch_ids = [1, 2, 3, 4]

    algorithm = DijkstraRouting()

    result = algorithm.solve(
        graph=graph,
        selected_ch_ids=selected_ch_ids,
        bs_id="BS",
    )

    expected_parent_map = {
        1: "BS",
        2: 1,
        3: 2,
        4: 3,
    }

    assert result["parent_map"] == expected_parent_map

    validation = result["validation"]

    assert validation["valid"] is True
    assert validation["errors"] == []
    assert validation["total_distance"] == 31.0

    print("\nDIJKSTRA ROUTING TEST PASSED")
    print("--------------------------------")
    print("Parent map:", result["parent_map"])
    print("Routes:", validation["routes"])
    print("Total tree distance:", validation["total_distance"])
    print("Validation:", validation["valid"])


if __name__ == "__main__":
    test_dijkstra_routing()

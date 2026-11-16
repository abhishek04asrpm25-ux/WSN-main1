
try:
    import networkx as nx  # pyright: ignore[reportMissingModuleSource]
except ImportError as exc:
    raise RuntimeError(
        "The 'networkx' package is required for connectivity testing. "
        "Install it with: pip install networkx"
    ) from exc

from simulation.network import (
    generate_network,
    print_network_summary
)


def analyze_connectivity(network):

    graph = network["graph"]
    nodes = network["nodes"]

    bs = "BS"

    # Find all nodes that can reach the BS
    reachable_nodes = set()

    for node in nodes:

        node_id = node["id"]

        if nx.has_path(graph, node_id, bs):
            reachable_nodes.add(node_id)

    total_nodes = len(nodes)

    reachable_count = len(reachable_nodes)

    unreachable_count = total_nodes - reachable_count

    # Count nodes having direct links to BS
    direct_bs_nodes = list(graph.neighbors(bs))

    # Calculate shortest paths to BS
    hop_counts = []

    for node_id in reachable_nodes:

        hops = nx.shortest_path_length(
            graph,
            source=node_id,
            target=bs
        )

        hop_counts.append(hops)

    if hop_counts:
        average_hops = sum(hop_counts) / len(hop_counts)
        maximum_hops = max(hop_counts)
    else:
        average_hops = 0
        maximum_hops = 0

    connectivity_percentage = (
        reachable_count / total_nodes
    ) * 100

    return {
        "total_nodes": total_nodes,
        "reachable_nodes": reachable_count,
        "unreachable_nodes": unreachable_count,
        "direct_bs_links": len(direct_bs_nodes),
        "connectivity_percentage": connectivity_percentage,
        "average_hops_to_bs": average_hops,
        "maximum_hops_to_bs": maximum_hops,
        "reachable_node_ids": sorted(reachable_nodes)
    }


def test_communication_ranges(config):

    candidate_ranges = config[
        "communication"
    ]["candidate_ranges_m"]

    results = []

    print("\n========== RANGE COMPARISON ==========\n")

    for radius in candidate_ranges:

        network = generate_network(
            config,
            communication_range=radius
        )

        metrics = analyze_connectivity(network)

        results.append({
            "range": radius,
            **metrics
        })

        print(f"Communication Range: {radius} m")

        print(
            "Reachable nodes:",
            metrics["reachable_nodes"],
            "/",
            metrics["total_nodes"]
        )

        print(
            "Unreachable nodes:",
            metrics["unreachable_nodes"]
        )

        print(
            "Direct BS connections:",
            metrics["direct_bs_links"]
        )

        print(
            "Connectivity:",
            round(metrics["connectivity_percentage"], 2),
            "%"
        )

        print(
            "Average hops to BS:",
            round(metrics["average_hops_to_bs"], 2)
        )

        print(
            "Maximum hops to BS:",
            metrics["maximum_hops_to_bs"]
        )

        print("--------------------------------------")

    print("\nRange testing completed.")

    return results

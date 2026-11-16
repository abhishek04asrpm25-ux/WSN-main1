
import math
import random


class _Graph:
    """Minimal undirected graph for the operations used in this module."""

    def __init__(self):
        self._adjacency = {}
        self._node_attributes = {}

    def add_node(self, node_id, **attributes):
        self._adjacency.setdefault(node_id, {})
        self._node_attributes[node_id] = attributes

    def add_edge(self, node1, node2, **attributes):
        self._adjacency.setdefault(node1, {})[node2] = attributes
        self._adjacency.setdefault(node2, {})[node1] = attributes

    def degree(self, node_id):
        return len(self._adjacency.get(node_id, {}))


def calculate_distance(node1, node2):
    """
    Calculate Euclidean distance between two positions.

    Each position must contain x and y coordinates.
    """

    dx = node1["x"] - node2["x"]
    dy = node1["y"] - node2["y"]

    return math.hypot(dx, dy)


def generate_network(config, communication_range):
    """
    Generate a wireless sensor network.

    Parameters
    ----------
    config : dict
        Network configuration.

    communication_range : float
        Common communication range in metres.

    Returns
    -------
    network : dict
        Contains nodes, BS, graph and network information.
    """

    settings = config["network"]

    num_nodes = settings["num_nodes"]
    width = settings["area_width"]
    height = settings["area_height"]
    initial_energy = settings["initial_energy_j"]
    seed = settings["random_seed"]

    bs_settings = settings["base_station"]

    # Validate configuration
    if num_nodes <= 0:
        raise ValueError("Number of nodes must be positive.")

    if width <= 0 or height <= 0:
        raise ValueError("Area dimensions must be positive.")

    if initial_energy <= 0:
        raise ValueError("Initial energy must be positive.")

    if communication_range <= 0:
        raise ValueError("Communication range must be positive.")

    # Reproducible random deployment
    rng = random.Random(seed)

    # Generate sensor node coordinates
    x_positions = [rng.uniform(0, width) for _ in range(num_nodes)]
    y_positions = [rng.uniform(0, height) for _ in range(num_nodes)]

    nodes = []

    for i in range(num_nodes):

        node = {
            "id": i,
            "x": float(x_positions[i]),
            "y": float(y_positions[i]),
            "initial_energy": float(initial_energy),
            "residual_energy": float(initial_energy),
            "alive": True,
            "is_cluster_head": False,
            "cluster_id": None,
            "neighbors": [],
            "degree": 0
        }

        nodes.append(node)

    # Create Base Station
    base_station = {
        "id": "BS",
        "x": float(bs_settings["x"]),
        "y": float(bs_settings["y"])
    }

    # Create an undirected connectivity graph
    graph = _Graph()

    # Add sensor nodes
    for node in nodes:

        graph.add_node(
            node["id"],
            x=node["x"],
            y=node["y"],
            node_type="sensor",
            energy=node["residual_energy"]
        )

    # Add Base Station
    graph.add_node(
        "BS",
        x=base_station["x"],
        y=base_station["y"],
        node_type="base_station"
    )

    # Find sensor-to-sensor links
    for i in range(num_nodes):

        for j in range(i + 1, num_nodes):

            distance = calculate_distance(
                nodes[i],
                nodes[j]
            )

            if distance <= communication_range:

                graph.add_edge(
                    i,
                    j,
                    distance=distance
                )

                nodes[i]["neighbors"].append(j)
                nodes[j]["neighbors"].append(i)

    # Find sensor-to-BS links
    for node in nodes:

        distance = calculate_distance(
            node,
            base_station
        )

        if distance <= communication_range:

            graph.add_edge(
                node["id"],
                "BS",
                distance=distance
            )

    # Calculate node degrees
    for node in nodes:

        node["degree"] = len(node["neighbors"])

    # Return the complete network
    network = {
        "nodes": nodes,
        "base_station": base_station,
        "graph": graph,
        "communication_range": communication_range,
        "num_nodes": num_nodes,
        "area_width": width,
        "area_height": height
    }

    return network


def print_network_summary(network):

    nodes = network["nodes"]
    graph = network["graph"]

    total_nodes = len(nodes)

    total_sensor_links = sum(
        len(node["neighbors"]) for node in nodes
    ) // 2

    direct_bs_links = graph.degree("BS")

    average_degree = sum(node["degree"] for node in nodes) / total_nodes

    print("\n========== NETWORK SUMMARY ==========")

    print("Total sensor nodes:", total_nodes)

    print(
        "Communication range:",
        network["communication_range"],
        "metres"
    )

    print("Sensor-to-sensor links:", total_sensor_links)

    print("Direct links to BS:", direct_bs_links)

    print("Average sensor degree:", round(average_degree, 2))

    print(
        "Base Station:",
        network["base_station"]["x"],
        network["base_station"]["y"]
    )

    print("=====================================\n")

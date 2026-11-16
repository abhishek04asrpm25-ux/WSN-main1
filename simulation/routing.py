
import math
import networkx as nx


class RoutingGraphBuilder:
    """
    Builds a common routing graph containing:
    - Selected alive Cluster Heads
    - The Base Station
    - Valid CH-to-CH links
    - Valid CH-to-BS links

    Every wireless link must satisfy the same communication range.
    """

    BS_ID = "BS"

    def __init__(self, communication_range):
        self.communication_range = float(communication_range)

        if not math.isfinite(self.communication_range):
            raise ValueError("Communication range must be finite.")

        if self.communication_range <= 0:
            raise ValueError("Communication range must be positive.")

    @staticmethod
    def calculate_distance(point_a, point_b):
        dx = float(point_a["x"]) - float(point_b["x"])
        dy = float(point_a["y"]) - float(point_b["y"])
        return math.hypot(dx, dy)

    @staticmethod
    def _get_base_station(network, config):
        """
        Finds the BS coordinates from the generated network first,
        then from the configuration if necessary.
        """

        base_station = network.get("base_station")

        if not isinstance(base_station, dict):
            base_station = network.get("bs")

        if isinstance(base_station, dict):
            if "x" in base_station and "y" in base_station:
                return {
                    "x": float(base_station["x"]),
                    "y": float(base_station["y"])
                }

        # Your configuration stores the BS under config["network"].
        network_settings = config.get("network", {})
        base_station = network_settings.get("base_station", {})

        if isinstance(base_station, dict):
            if "x" in base_station and "y" in base_station:
                return {
                    "x": float(base_station["x"]),
                    "y": float(base_station["y"])
                }

        # Also support alternative configuration formats.
        for key in ("base_station", "bs"):
            base_station = config.get(key)

            if isinstance(base_station, dict):
                if "x" in base_station and "y" in base_station:
                    return {
                        "x": float(base_station["x"]),
                        "y": float(base_station["y"])
                    }

        position = config.get("base_station_position")

        if isinstance(position, (list, tuple)) and len(position) == 2:
            return {
                "x": float(position[0]),
                "y": float(position[1])
            }

        raise ValueError(
            "Base Station coordinates were not found. "
            "Expected network['base_station'] or "
            "config['network']['base_station']."
        )

    def build_graph(self, network, config, selected_ch_ids):
        """
        Creates a NetworkX graph containing selected alive CHs and BS.
        """

        nodes = network["nodes"]

        node_map = {node["id"]: node for node in nodes}

        if len(node_map) != len(nodes):
            raise ValueError("Sensor node IDs must be unique.")

        selected_ch_ids = list(selected_ch_ids)

        if len(selected_ch_ids) != len(set(selected_ch_ids)):
            raise ValueError("Selected CH IDs must be unique.")

        if not selected_ch_ids:
            raise ValueError("At least one Cluster Head is required.")

        for ch_id in selected_ch_ids:
            if ch_id not in node_map:
                raise ValueError(f"Unknown Cluster Head ID: {ch_id}")

            node = node_map[ch_id]

            if (
                not node.get("alive", True)
                or float(node.get("residual_energy", 0)) <= 0
            ):
                raise ValueError(f"Cluster Head {ch_id} is not alive.")

        bs_position = self._get_base_station(network, config)

        # Create a standard NetworkX undirected graph.
        graph = nx.Graph()

        graph.add_node(
            self.BS_ID,
            node_type="base_station",
            x=bs_position["x"],
            y=bs_position["y"]
        )

        # Add selected Cluster Heads.
        for ch_id in selected_ch_ids:
            node = node_map[ch_id]

            graph.add_node(
                ch_id,
                node_type="cluster_head",
                x=float(node["x"]),
                y=float(node["y"]),
                residual_energy=float(node["residual_energy"])
            )

        # Add CH-to-CH links.
        for index, ch_id_a in enumerate(selected_ch_ids):
            node_a = node_map[ch_id_a]

            for ch_id_b in selected_ch_ids[index + 1:]:
                node_b = node_map[ch_id_b]

                distance = self.calculate_distance(node_a, node_b)

                if distance <= self.communication_range + 1e-9:
                    graph.add_edge(
                        ch_id_a,
                        ch_id_b,
                        weight=distance,
                        distance=distance,
                        link_type="CH_TO_CH"
                    )

        # Add CH-to-BS links.
        for ch_id in selected_ch_ids:
            node = node_map[ch_id]

            distance = self.calculate_distance(node, bs_position)

            if distance <= self.communication_range + 1e-9:
                graph.add_edge(
                    ch_id,
                    self.BS_ID,
                    weight=distance,
                    distance=distance,
                    link_type="CH_TO_BS"
                )

        # Determine which CHs can reach the BS.
        reachable_ch_ids = []
        unreachable_ch_ids = []

        for ch_id in selected_ch_ids:
            if nx.has_path(graph, ch_id, self.BS_ID):
                reachable_ch_ids.append(ch_id)
            else:
                unreachable_ch_ids.append(ch_id)

        ch_link_count = sum(
            1
            for _, _, data in graph.edges(data=True)
            if data["link_type"] == "CH_TO_CH"
        )

        bs_link_count = sum(
            1
            for _, _, data in graph.edges(data=True)
            if data["link_type"] == "CH_TO_BS"
        )

        return {
            "graph": graph,
            "base_station_id": self.BS_ID,
            "selected_ch_ids": selected_ch_ids,
            "reachable_ch_ids": reachable_ch_ids,
            "unreachable_ch_ids": unreachable_ch_ids,
            "communication_range": self.communication_range,
            "number_of_ch_links": ch_link_count,
            "number_of_bs_links": bs_link_count
        }

    @staticmethod
    def print_graph_summary(graph_result):
        graph = graph_result["graph"]

        print("\n========== ROUTING GRAPH SUMMARY ==========")

        print("Total graph nodes:", graph.number_of_nodes())
        print("Total graph links:", graph.number_of_edges())

        print("CH-to-CH links:", graph_result["number_of_ch_links"])
        print("CH-to-BS links:", graph_result["number_of_bs_links"])

        print("Reachable CHs:", graph_result["reachable_ch_ids"])
        print("Unreachable CHs:", graph_result["unreachable_ch_ids"])

        print(
            "All CHs can reach BS:",
            len(graph_result["unreachable_ch_ids"]) == 0
        )

        print("\n========== GRAPH EDGES ==========")

        for node_a, node_b, data in graph.edges(data=True):
            print(
                f"{node_a} <--> {node_b} | "
                f"Distance: {data['distance']:.2f} m | "
                f"Type: {data['link_type']}"
            )

        print("==========================================\n")

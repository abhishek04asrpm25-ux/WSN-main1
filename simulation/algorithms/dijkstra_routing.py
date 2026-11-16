
import heapq

from simulation.algorithms.routing_interface import RoutingAlgorithm


class DijkstraRouting(RoutingAlgorithm):
    """
    Global Dijkstra routing.

    The base station is the source. The algorithm calculates the
    shortest path from the BS to every reachable cluster head.

    parent_map[CH] stores the next hop from that CH towards the BS.
    """

    algorithm_name = "Dijkstra"

    def find_routes(self, graph, selected_ch_ids, bs_id="BS"):

        if bs_id not in graph.nodes:
            raise ValueError(
                f"Base station {bs_id} is not present in the graph."
            )

        selected_ch_ids = list(selected_ch_ids)

        if not selected_ch_ids:
            raise ValueError("No cluster heads were provided.")

        for ch_id in selected_ch_ids:
            if ch_id not in graph.nodes:
                raise ValueError(
                    f"Cluster head {ch_id} is missing from the graph."
                )

        # Build adjacency lists from the custom graph.
        adjacency = {node_id: [] for node_id in graph.nodes}

        for u, v, data in graph.edges(data=True):
            weight = float(data.get("weight", 1.0))

            if weight < 0:
                raise ValueError("Dijkstra cannot use negative edge weights.")

            adjacency[u].append((v, weight))
            adjacency[v].append((u, weight))

        # Initialize shortest distances and predecessor information.
        distances = {node_id: float("inf") for node_id in graph.nodes}
        predecessor = {node_id: None for node_id in graph.nodes}

        distances[bs_id] = 0.0

        priority_queue = [(0.0, bs_id)]

        # Dijkstra's shortest-path calculation.
        while priority_queue:
            current_distance, current_node = heapq.heappop(
                priority_queue
            )

            if current_distance > distances[current_node]:
                continue

            for neighbor, edge_weight in adjacency[current_node]:

                new_distance = current_distance + edge_weight

                if new_distance < distances[neighbor]:
                    distances[neighbor] = new_distance
                    predecessor[neighbor] = current_node

                    heapq.heappush(
                        priority_queue,
                        (new_distance, neighbor),
                    )

        # Check whether all selected CHs can reach the BS.
        unreachable = [
            ch_id
            for ch_id in selected_ch_ids
            if distances[ch_id] == float("inf")
        ]

        if unreachable:
            raise ValueError(
                f"These cluster heads cannot reach the BS: {unreachable}"
            )

        # Convert predecessor information into a global parent map.
        parent_map = {}

        for ch_id in selected_ch_ids:
            next_hop = predecessor[ch_id]

            if next_hop is None:
                raise ValueError(
                    f"No next hop was found for cluster head {ch_id}."
                )

            parent_map[ch_id] = next_hop

        return parent_map

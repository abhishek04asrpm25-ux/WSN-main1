
import math


class ClusterManager:
    """
    Forms clusters by assigning each alive normal sensor node
    to its nearest reachable Cluster Head.
    """

    def __init__(self, communication_range):
        self.communication_range = float(communication_range)

        if self.communication_range <= 0:
            raise ValueError("Communication range must be positive.")

    @staticmethod
    def calculate_distance(node_a, node_b):
        dx = float(node_a["x"]) - float(node_b["x"])
        dy = float(node_a["y"]) - float(node_b["y"])

        return math.sqrt(dx ** 2 + dy ** 2)

    def form_clusters(self, network, selected_ch_ids):
        nodes = network["nodes"]

        node_map = {
            node["id"]: node
            for node in nodes
        }

        alive_nodes = [
            node for node in nodes
            if node.get("alive", True)
            and float(node.get("residual_energy", 0)) > 0
        ]

        alive_ids = {
            node["id"] for node in alive_nodes
        }

        selected_ch_ids = list(selected_ch_ids)

        if len(selected_ch_ids) != len(set(selected_ch_ids)):
            raise ValueError("Cluster Head IDs must be unique.")

        if not selected_ch_ids:
            raise ValueError("At least one Cluster Head is required.")

        for ch_id in selected_ch_ids:
            if ch_id not in node_map or ch_id not in alive_ids:
                raise ValueError(
                    f"Selected Cluster Head {ch_id} is not alive or does not exist."
                )

        clusters = {
            ch_id: [ch_id]
            for ch_id in selected_ch_ids
        }

        # Reset cluster information for every node, including nodes that
        # died in an earlier round, so snapshots never show stale membership.
        for node in nodes:
            node["is_cluster_head"] = False
            node["cluster_id"] = None

        # Mark each selected Cluster Head.
        for ch_id in selected_ch_ids:
            node_map[ch_id]["is_cluster_head"] = True
            node_map[ch_id]["cluster_id"] = ch_id

        assigned_nodes = set(selected_ch_ids)
        unassigned_nodes = []

        # Assign every normal node to its nearest reachable CH.
        for node in alive_nodes:
            node_id = node["id"]

            if node_id in selected_ch_ids:
                continue

            nearest_ch_id = None
            minimum_distance = float("inf")

            for ch_id in selected_ch_ids:
                ch = node_map[ch_id]

                distance = self.calculate_distance(node, ch)

                if (
                    distance <= self.communication_range
                    and distance < minimum_distance
                ):
                    minimum_distance = distance
                    nearest_ch_id = ch_id

            if nearest_ch_id is None:
                unassigned_nodes.append(node_id)
                continue

            clusters[nearest_ch_id].append(node_id)
            node["cluster_id"] = nearest_ch_id
            assigned_nodes.add(node_id)

        # Sort member IDs for consistent output.
        for ch_id in clusters:
            clusters[ch_id].sort()

        total_alive = len(alive_nodes)

        if total_alive == 0:
            coverage = 0.0
        else:
            coverage = len(assigned_nodes) / total_alive

        return {
            "clusters": clusters,
            "selected_ch_ids": selected_ch_ids,
            "assigned_node_ids": sorted(assigned_nodes),
            "unassigned_node_ids": sorted(unassigned_nodes),
            "total_alive_nodes": total_alive,
            "total_assigned_nodes": len(assigned_nodes),
            "coverage": coverage
        }

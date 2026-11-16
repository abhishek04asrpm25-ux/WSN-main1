
class PacketGenerator:
    """
    Generates one data packet per alive sensor node and creates
    one aggregated packet for each Cluster Head.

    This module models packet creation and aggregation only.
    It does not perform radio transmission or consume energy.
    """

    def __init__(self, config):
        simulation_config = config.get("simulation", {})

        self.packet_size_bits = int(
            simulation_config.get("packet_size_bits", 4000)
        )

        self.aggregated_packet_size_bits = int(
            simulation_config.get(
                "aggregated_packet_size_bits",
                self.packet_size_bits
            )
        )

        if self.packet_size_bits <= 0:
            raise ValueError("Packet size must be positive.")

        if self.aggregated_packet_size_bits <= 0:
            raise ValueError(
                "Aggregated packet size must be positive."
            )

    def generate_packets(self, network, clustering_result, round_number=1):
        if round_number < 0:
            raise ValueError("Round number cannot be negative.")

        nodes = network["nodes"]

        node_map = {
            node["id"]: node
            for node in nodes
        }

        clusters = clustering_result["clusters"]

        alive_nodes = [
            node for node in nodes
            if node.get("alive", True)
            and float(node.get("residual_energy", 0)) > 0
        ]

        # Generate one original data packet for every alive node.
        generated_packets = {}

        for node in alive_nodes:
            node_id = node["id"]

            packet = {
                "packet_id": f"R{round_number}_N{node_id}",
                "source_node_id": node_id,
                "generated_round": round_number,
                "packet_size_bits": self.packet_size_bits,
                "packet_type": "sensor_data"
            }

            generated_packets[node_id] = packet

        aggregated_packets = {}
        cluster_details = {}

        # Process each cluster independently.
        for ch_id, member_ids in clusters.items():

            if ch_id not in generated_packets:
                continue

            valid_member_ids = [
                member_id
                for member_id in member_ids
                if member_id in generated_packets
            ]

            if ch_id not in valid_member_ids:
                raise ValueError(
                    f"Cluster Head {ch_id} is missing from its own cluster."
                )

            input_packets = [
                generated_packets[member_id]
                for member_id in valid_member_ids
            ]

            input_packet_ids = [
                packet["packet_id"]
                for packet in input_packets
            ]

            input_source_ids = sorted(valid_member_ids)

            total_input_bits = (
                len(input_packets) * self.packet_size_bits
            )

            # One outgoing aggregated packet per cluster.
            aggregated_packet = {
                "packet_id": f"R{round_number}_AGG_CH{ch_id}",
                "packet_type": "cluster_aggregate",
                "origin_ch_id": ch_id,
                "current_holder": ch_id,
                "generated_round": round_number,
                "source_node_ids": input_source_ids,
                "input_packet_ids": input_packet_ids,
                "input_packet_count": len(input_packets),
                "input_bits": total_input_bits,
                "packet_size_bits": self.aggregated_packet_size_bits,
                "hop_count": 0
            }

            aggregated_packets[ch_id] = aggregated_packet

            cluster_details[ch_id] = {
                "member_node_ids": valid_member_ids,
                "input_packet_count": len(input_packets),
                "input_bits": total_input_bits,
                "aggregated_packet_bits": (
                    self.aggregated_packet_size_bits
                )
            }

        # Nodes outside all reachable clusters retain pending packets.
        assigned_node_ids = set(
            clustering_result["assigned_node_ids"]
        )

        pending_packets = {
            node_id: packet
            for node_id, packet in generated_packets.items()
            if node_id not in assigned_node_ids
        }

        return {
            "round_number": round_number,
            "generated_packets": generated_packets,
            "aggregated_packets": aggregated_packets,
            "pending_packets": pending_packets,
            "cluster_details": cluster_details,
            "summary": {
                "alive_nodes": len(alive_nodes),
                "generated_packets": len(generated_packets),
                "aggregated_packets": len(aggregated_packets),
                "pending_packets": len(pending_packets),
                "total_original_data_bits": (
                    len(generated_packets) * self.packet_size_bits
                )
            }
        }

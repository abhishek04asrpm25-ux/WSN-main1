
import copy
import math
import time

from simulation.network import generate_network
from simulation.energy_model import EnergyModel
from simulation.clustering import ClusterManager
from simulation.packet_generation import PacketGenerator
from simulation.routing import RoutingGraphBuilder

from simulation.algorithms.ann_ch_selection import (
    ANNClusterHeadSelector
)
from simulation.algorithms.dijkstra_routing import DijkstraRouting


class WSNSimulationEngine:
    """
    WSN simulation engine.

    Architecture:
        ANN: Cluster-head selection only.
        Routing algorithm: Multi-hop routing.

    Supports:
        Dijkstra, ILP, GA, PSO, ACO and ANN routing.

    Each engine maintains its own independent network and
    energy history.
    """

    def __init__(
        self,
        config,
        routing_algorithm=None,
        initial_network=None,
    ):
        self.config = copy.deepcopy(config)

        communication = self.config.get("communication", {})

        self.communication_range = float(
            communication.get("communication_range_m") or 60
        )

        if not math.isfinite(self.communication_range):
            raise ValueError("Invalid communication range.")

        if self.communication_range <= 0:
            raise ValueError("Communication range must be positive.")

        # -------------------------------------------------
        # 1. NETWORK INITIALIZATION
        # -------------------------------------------------

        if initial_network is None:
            self.network = generate_network(
                self.config,
                self.communication_range
            )
        else:
            self.network = copy.deepcopy(initial_network)

        self.energy_model = EnergyModel(self.config)

        self.cluster_manager = ClusterManager(
            self.communication_range
        )

        self.packet_generator = PacketGenerator(self.config)

        self.routing_builder = RoutingGraphBuilder(
            self.communication_range
        )

        # -------------------------------------------------
        # 2. ANN CLUSTER-HEAD SELECTION
        # -------------------------------------------------

        simulation_config = self.config.get("simulation", {})

        self.ann_selector = ANNClusterHeadSelector(
            num_cluster_heads=int(
                simulation_config.get("num_cluster_heads", 10)
            ),
            random_seed=42,
            communication_range=self.communication_range,
            initial_energy=float(
                self.config.get("network", {}).get("initial_energy_j", 0.5)
            ),
        )

        self.ann_training_result = self.ann_selector.train()

        # -------------------------------------------------
        # 3. MULTI-HOP ROUTING ALGORITHM
        # -------------------------------------------------

        self.routing_algorithm = (
            routing_algorithm
            if routing_algorithm is not None
            else DijkstraRouting()
        )

        if not callable(
            getattr(self.routing_algorithm, "solve", None)
        ):
            raise TypeError(
                "Routing algorithm must implement solve()."
            )

        if not hasattr(
            self.routing_algorithm,
            "algorithm_name"
        ):
            raise TypeError(
                "Routing algorithm must define algorithm_name."
            )

        # -------------------------------------------------
        # 4. HISTORY
        # -------------------------------------------------

        self.round_history = []
        self.cumulative_successful_packets = 0
        self.cumulative_lost_packets = 0
        self.initial_node_count = len(self.network["nodes"])
        self.fnd_round = None
        self.hnd_round = None
        self.lnd_round = None
        self.transmission_rate_bps = float(
            self.config.get("radio_model", {}).get("transmission_rate_bps", 250000)
        )
        if self.transmission_rate_bps <= 0:
            raise ValueError("Transmission rate must be positive.")

    @staticmethod
    def _alive(node):
        return (
            node.get("alive", True)
            and float(node.get("residual_energy", 0)) > 0
        )

    def _consume(self, node, energy):
        before = float(node["residual_energy"])

        success = self.energy_model.consume_energy(
            node,
            energy
        )

        after = float(node["residual_energy"])

        return {
            "success": success,
            "requested_energy": float(energy),
            "actual_energy": before - after
        }

    def _calculate_route_depths(
        self,
        parent_map,
        selected_ch_ids
    ):
        depths = {}

        for ch_id in selected_ch_ids:
            current = ch_id
            depth = 0
            visited = set()

            while current != "BS":

                if current in visited:
                    raise ValueError(
                        "Routing loop detected."
                    )

                visited.add(current)

                if current not in parent_map:
                    raise ValueError(
                        f"Missing parent for CH {current}."
                    )

                current = parent_map[current]
                depth += 1

            depths[ch_id] = depth

        return depths

    def run_round(self, round_number=1):
        round_started_at = time.perf_counter()
        nodes = self.network["nodes"]

        alive_before = sum(
            1 for node in nodes if self._alive(node)
        )

        if alive_before == 0:
            raise ValueError("All sensor nodes are dead.")

        # -------------------------------------------------
        # 1. ANN CLUSTER-HEAD SELECTION
        # -------------------------------------------------

        ann_result = self.ann_selector.select_cluster_heads(
            nodes=nodes,
            base_station=self.network["base_station"]
        )

        selected_ch_ids = ann_result["selected_ch_ids"]

        # -------------------------------------------------
        # 2. FORM CLUSTERS
        # -------------------------------------------------

        clustering_result = self.cluster_manager.form_clusters(
            self.network,
            selected_ch_ids
        )

        # -------------------------------------------------
        # 3. GENERATE PACKETS
        # -------------------------------------------------

        self.packet_generator.generate_packets(
            self.network,
            clustering_result,
            round_number
        )

        # -------------------------------------------------
        # 4. BUILD CH ROUTING GRAPH
        # -------------------------------------------------

        graph_result = self.routing_builder.build_graph(
            self.network,
            self.config,
            selected_ch_ids
        )

        if graph_result["unreachable_ch_ids"]:
            raise ValueError(
                "Some CHs cannot reach the BS: "
                f"{graph_result['unreachable_ch_ids']}"
            )

        graph = graph_result["graph"]

        # -------------------------------------------------
        # 5. MULTI-HOP ROUTING
        # -------------------------------------------------

        routing_started_at = time.perf_counter()
        routing_result = self.routing_algorithm.solve(
            graph,
            selected_ch_ids,
            bs_id="BS"
        )
        routing_computation_time = time.perf_counter() - routing_started_at

        parent_map = routing_result["parent_map"]

        routes = routing_result["validation"]["routes"]

        depths = self._calculate_route_depths(
            parent_map,
            selected_ch_ids
        )

        # -------------------------------------------------
        # 6. NORMAL NODE TRANSMISSION TO CH
        # -------------------------------------------------

        node_map = {
            node["id"]: node for node in nodes
        }

        energy_used = 0.0

        successful_normal_packets = 0
        lost_normal_packets = 0

        packet_size = self.packet_generator.packet_size_bits

        for ch_id, member_ids in clustering_result["clusters"].items():

            ch = node_map[ch_id]

            for member_id in member_ids:

                if member_id == ch_id:
                    continue

                member = node_map[member_id]

                if not self._alive(member) or not self._alive(ch):
                    lost_normal_packets += 1
                    continue

                distance = self.routing_builder.calculate_distance(
                    member,
                    ch
                )

                tx_energy = self.energy_model.transmission_energy(
                    distance,
                    packet_size
                )

                tx = self._consume(member, tx_energy)

                energy_used += tx["actual_energy"]

                if not tx["success"]:
                    lost_normal_packets += 1
                    continue

                rx_energy = self.energy_model.reception_energy(
                    packet_size
                )

                rx = self._consume(ch, rx_energy)

                energy_used += rx["actual_energy"]

                if not rx["success"]:
                    lost_normal_packets += 1
                    continue

                successful_normal_packets += 1

        # -------------------------------------------------
        # 7. MULTI-HOP FORWARDING AND AGGREGATION
        # -------------------------------------------------

        child_map = {
            ch_id: [] for ch_id in selected_ch_ids
        }

        for child, parent in parent_map.items():

            if parent != "BS":
                child_map[parent].append(child)

        aggregated_size = (
            self.packet_generator.aggregated_packet_size_bits
        )

        successful_ch_packets = 0
        lost_ch_packets = 0

        forwarding_records = []

        processing_order = sorted(
            selected_ch_ids,
            key=lambda ch_id: depths[ch_id],
            reverse=True
        )

        for ch_id in processing_order:

            ch = node_map[ch_id]

            if not self._alive(ch):
                lost_ch_packets += 1
                continue

            cluster_members = clustering_result["clusters"][ch_id]

            own_input_count = 1 + sum(
                1
                for member_id in cluster_members
                if member_id != ch_id
                and member_id in node_map
                and self._alive(node_map[member_id])
            )

            received_child_count = sum(
                1
                for child in child_map[ch_id]
                if node_map[child].get(
                    "_forwarded_successfully",
                    False
                )
            )

            input_bits = (
                own_input_count * packet_size
                + received_child_count * aggregated_size
            )

            aggregation_energy = self.energy_model.aggregation_energy(
                input_bits
            )

            aggregation = self._consume(
                ch,
                aggregation_energy
            )

            energy_used += aggregation["actual_energy"]

            if not aggregation["success"]:

                ch["_forwarded_successfully"] = False

                lost_ch_packets += 1

                continue

            parent = parent_map[ch_id]

            parent_position = (
                self.network["base_station"]
                if parent == "BS"
                else node_map[parent]
            )

            distance = self.routing_builder.calculate_distance(
                ch,
                parent_position
            )

            tx_energy = self.energy_model.transmission_energy(
                distance,
                aggregated_size
            )

            tx = self._consume(ch, tx_energy)

            energy_used += tx["actual_energy"]

            if not tx["success"]:

                ch["_forwarded_successfully"] = False

                lost_ch_packets += 1

                continue

            if parent != "BS":

                receiver = node_map[parent]

                if not self._alive(receiver):

                    ch["_forwarded_successfully"] = False

                    lost_ch_packets += 1

                    continue

                rx_energy = self.energy_model.reception_energy(
                    aggregated_size
                )

                rx = self._consume(
                    receiver,
                    rx_energy
                )

                energy_used += rx["actual_energy"]

                if not rx["success"]:

                    ch["_forwarded_successfully"] = False

                    lost_ch_packets += 1

                    continue

            ch["_forwarded_successfully"] = True

            successful_ch_packets += 1

            forwarding_records.append({
                "cluster_head": ch_id,
                "next_hop": parent,
                "distance": distance,
                "route": routes[ch_id],
                "packet_size_bits": aggregated_size,
                "success": True
            })

        # -------------------------------------------------
        # 8. REMOVE TEMPORARY FIELDS
        # -------------------------------------------------

        for node in nodes:
            node.pop("_forwarded_successfully", None)

        # -------------------------------------------------
        # 9. ROUND METRICS
        # -------------------------------------------------

        round_successful_packets = (
            successful_normal_packets + successful_ch_packets
        )
        round_lost_packets = lost_normal_packets + lost_ch_packets
        self.cumulative_successful_packets += round_successful_packets
        self.cumulative_lost_packets += round_lost_packets
        cumulative_total = (
            self.cumulative_successful_packets + self.cumulative_lost_packets
        )
        cumulative_delivery_ratio = (
            self.cumulative_successful_packets / cumulative_total
            if cumulative_total else 0.0
        )

        alive_after = sum(
            1 for node in nodes if self._alive(node)
        )

        dead_after = len(nodes) - alive_after
        if self.fnd_round is None and dead_after >= 1:
            self.fnd_round = round_number
        if self.hnd_round is None and alive_after <= self.initial_node_count / 2:
            self.hnd_round = round_number
        if self.lnd_round is None and alive_after == 0:
            self.lnd_round = round_number

        total_residual_energy = sum(
            float(node["residual_energy"])
            for node in nodes
        )

        snapshot_nodes = [
            {
                "id": node["id"],
                "x": node["x"],
                "y": node["y"],
                "alive": self._alive(node),
                "residual_energy": node["residual_energy"],
                "is_cluster_head": node["id"] in selected_ch_ids,
                "cluster_id": node.get("cluster_id")
            }
            for node in nodes
        ]

        snapshot = {
            "round": round_number,

            "algorithm": self.routing_algorithm.algorithm_name,

            "cluster_head_algorithm": "ANN",

            "selected_ch_ids": selected_ch_ids,

            "ann_scores": ann_result["scores"],

            "clusters": clustering_result["clusters"],

            "parent_map": parent_map,

            "routes": routes,

            "forwarding": forwarding_records,

            "nodes": snapshot_nodes,

            "metrics": {
                "alive_nodes_before": alive_before,
                "alive_nodes": alive_after,
                "dead_nodes": dead_after,
                "total_residual_energy": total_residual_energy,
                "energy_consumed": energy_used,
                "successful_normal_packets": successful_normal_packets,
                "lost_normal_packets": lost_normal_packets,
                "successful_ch_packets": successful_ch_packets,
                "lost_ch_packets": lost_ch_packets,
                "cluster_coverage": clustering_result["coverage"],
                "ann_cluster_head_count": len(selected_ch_ids),
                "routing_distance": routing_result[
                    "validation"
                ]["total_distance"],
                "round_successful_packets": round_successful_packets,
                "round_lost_packets": round_lost_packets,
                "cumulative_successful_packets": self.cumulative_successful_packets,
                "cumulative_lost_packets": self.cumulative_lost_packets,
                "cumulative_packet_delivery_ratio": cumulative_delivery_ratio,
                "round_packet_delivery_ratio": (
                    round_successful_packets / (round_successful_packets + round_lost_packets)
                    if round_successful_packets + round_lost_packets else 0.0
                ),
                "average_hop_count": (
                    float(sum(depths.values()) / len(depths)) if depths else 0.0
                ),
                "estimated_end_to_end_delay_s": (
                    float(sum(depths.values()) / len(depths)) * packet_size
                    / self.transmission_rate_bps if depths else 0.0
                ),
                "routing_computation_time_s": routing_computation_time,
                "round_execution_time_s": time.perf_counter() - round_started_at,
                "FND_round": self.fnd_round,
                "HND_round": self.hnd_round,
                "LND_round": self.lnd_round,
                "transmission_rate_bps_assumption": self.transmission_rate_bps
            }
        }

        self.round_history.append(snapshot)

        return snapshot

    def run(self, number_of_rounds=1):

        if number_of_rounds < 1:
            raise ValueError(
                "Number of rounds must be positive."
            )

        results = []

        for round_number in range(
            1,
            number_of_rounds + 1
        ):

            if not any(
                self._alive(node)
                for node in self.network["nodes"]
            ):
                break

            result = self.run_round(round_number)

            results.append(result)

        return {
            "status": "success",

            "algorithm": self.routing_algorithm.algorithm_name,

            "cluster_head_algorithm": "ANN",

            "communication_range": self.communication_range,

            "ann_training": self.ann_training_result,
            "routing_training": getattr(
                self.routing_algorithm, "training_result", None
            ),

            "total_rounds_completed": len(results),

            "history": results
        }


import copy

from simulation.network import generate_network
from simulation.simulation_engine import WSNSimulationEngine

from simulation.algorithms.dijkstra_routing import DijkstraRouting
from simulation.algorithms.ilp_routing import ILPRouting
from simulation.algorithms.ga_routing import GARouting
from simulation.algorithms.pso_routing import PSORouting
from simulation.algorithms.aco_routing import ACORouting
from simulation.algorithms.ann_routing import ANNRouting


class MultiAlgorithmSimulationRunner:
    """
    Runs six multi-hop routing algorithms.

    ANN is used exclusively for cluster-head selection.

    All six algorithms:
        - Start from the same initial network deployment.
        - Use independent network copies.
        - Maintain independent residual-energy histories.
        - Use the same simulation and radio configuration.
    """

    def __init__(self, config):
        self.config = copy.deepcopy(config)

        communication = self.config.get("communication", {})

        self.communication_range = float(
            communication.get("communication_range_m") or 60
        )

        if self.communication_range <= 0:
            raise ValueError(
                "Communication range must be positive."
            )

        # Generate the deployment only once.
        self.initial_network = generate_network(
            self.config,
            self.communication_range
        )

        # Moderate optimization settings for the first benchmark.
        # These can be increased after measuring runtime.
        self.algorithm_factories = {
            "Dijkstra": lambda: DijkstraRouting(),

            "ILP": lambda: ILPRouting(),

            "GA": lambda: GARouting(
                population_size=20,
                generations=20,
                random_seed=42
            ),

            "PSO": lambda: PSORouting(
                swarm_size=20,
                iterations=20,
                random_seed=42
            ),

            "ACO": lambda: ACORouting(
                num_ants=20,
                iterations=20,
                random_seed=42
            ),

            "ANN": lambda: ANNRouting(
                training_samples=5000,
                random_seed=42
            ),
        }

    @staticmethod
    def _build_summary(result):
        history = result["history"]

        if not history:
            return {
                "completed_rounds": 0
            }

        final_metrics = history[-1]["metrics"]

        total_energy_consumed = sum(
            snapshot["metrics"]["energy_consumed"]
            for snapshot in history
        )

        total_successful_normal = sum(
            snapshot["metrics"]["successful_normal_packets"]
            for snapshot in history
        )

        total_lost_normal = sum(
            snapshot["metrics"]["lost_normal_packets"]
            for snapshot in history
        )

        total_successful_ch = sum(
            snapshot["metrics"]["successful_ch_packets"]
            for snapshot in history
        )

        total_lost_ch = sum(
            snapshot["metrics"]["lost_ch_packets"]
            for snapshot in history
        )

        return {
            "completed_rounds": result["total_rounds_completed"],
            "final_alive_nodes": final_metrics["alive_nodes"],
            "final_dead_nodes": final_metrics["dead_nodes"],
            "final_residual_energy": final_metrics[
                "total_residual_energy"
            ],
            "total_energy_consumed": total_energy_consumed,
            "successful_normal_packets": total_successful_normal,
            "lost_normal_packets": total_lost_normal,
            "successful_ch_packets": total_successful_ch,
            "lost_ch_packets": total_lost_ch,
            "final_routing_distance": final_metrics["routing_distance"],
            "FND_round": next((x["metrics"]["FND_round"] for x in history if x["metrics"]["FND_round"] is not None), None),
            "HND_round": next((x["metrics"]["HND_round"] for x in history if x["metrics"]["HND_round"] is not None), None),
            "LND_round": next((x["metrics"]["LND_round"] for x in history if x["metrics"]["LND_round"] is not None), None),
            "average_packet_delivery_ratio": sum(x["metrics"]["round_packet_delivery_ratio"] for x in history) / len(history),
            "average_hop_count": sum(x["metrics"]["average_hop_count"] for x in history) / len(history),
            "average_estimated_delay_s": sum(x["metrics"]["estimated_end_to_end_delay_s"] for x in history) / len(history),
            "total_routing_computation_time_s": sum(x["metrics"]["routing_computation_time_s"] for x in history),
            "total_execution_time_s": sum(x["metrics"]["round_execution_time_s"] for x in history),
        }

    def run(self, number_of_rounds=1):

        if not isinstance(number_of_rounds, int):
            raise TypeError(
                "Number of rounds must be an integer."
            )

        if number_of_rounds < 1:
            raise ValueError(
                "Number of rounds must be positive."
            )

        algorithm_results = {}
        comparison = []

        for algorithm_key, factory in self.algorithm_factories.items():

            print(
                f"\nRunning {algorithm_key} routing..."
            )

            routing_algorithm = factory()

            engine = WSNSimulationEngine(
                config=self.config,
                routing_algorithm=routing_algorithm,
                initial_network=self.initial_network
            )

            result = engine.run(
                number_of_rounds=number_of_rounds
            )

            result["algorithm_key"] = algorithm_key

            algorithm_results[algorithm_key] = result

            summary = self._build_summary(result)

            comparison.append({
                "algorithm": algorithm_key,
                **summary
            })

            print(
                f"{algorithm_key}: "
                f"{result['total_rounds_completed']} rounds completed."
            )

        baseline_energy = next(
            (item["total_energy_consumed"] for item in comparison
             if item["algorithm"] == "Dijkstra"), 0.0
        )
        for item in comparison:
            item["energy_gap_vs_dijkstra_j"] = (
                item["total_energy_consumed"] - baseline_energy
            )
            item["energy_reduction_vs_dijkstra_pct"] = (
                (baseline_energy - item["total_energy_consumed"]) / baseline_energy * 100.0
                if baseline_energy > 0 else 0.0
            )

        return {
            "status": "success",
            "cluster_head_algorithm": "ANN",
            "experiment_metadata": {
                "deployment_seed": self.config.get("network", {}).get("random_seed", 42),
                "routing_seed": 42,
                "independent_topology_replicates": 1,
                "note": "Single fixed-seed topology; repeat with multiple seeds for statistical mean and spread."
            },
            "requested_rounds": number_of_rounds,
            "communication_range": self.communication_range,
            "network_nodes": self.initial_network["num_nodes"],
            "algorithms": list(self.algorithm_factories.keys()),
            "total_algorithms": len(self.algorithm_factories),
            "results": algorithm_results,
            "comparison": comparison
        }

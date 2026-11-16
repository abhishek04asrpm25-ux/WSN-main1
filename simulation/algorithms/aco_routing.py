
import random
import networkx as nx

from simulation.algorithms.routing_interface import RoutingAlgorithm


class ACORouting(RoutingAlgorithm):
    """
    Ant Colony Optimization for multi-hop WSN routing.

    Each ant constructs a valid next-hop choice for every CH.
    Pheromone and distance influence the selection probability.

    Only neighbors closer to the BS in shortest-path distance
    are allowed, preventing routing loops.
    """

    algorithm_name = "ACO Multi-Hop Routing"

    def __init__(
        self,
        num_ants=40,
        iterations=100,
        alpha=1.0,
        beta=2.0,
        evaporation_rate=0.3,
        pheromone_deposit=1.0,
        random_seed=42,
    ):
        self.num_ants = max(5, int(num_ants))
        self.iterations = max(1, int(iterations))
        self.alpha = float(alpha)
        self.beta = float(beta)
        self.evaporation_rate = float(evaporation_rate)
        self.pheromone_deposit = float(pheromone_deposit)
        self.random_seed = random_seed

        if not 0 <= self.evaporation_rate < 1:
            raise ValueError("Evaporation rate must be in [0, 1).")

        if self.alpha < 0 or self.beta < 0:
            raise ValueError("Alpha and beta must be non-negative.")

    def find_routes(self, graph, selected_ch_ids, bs_id="BS"):
        rng = random.Random(self.random_seed)
        selected_ch_ids = list(selected_ch_ids)

        if not selected_ch_ids:
            return {}

        if bs_id not in graph:
            raise ValueError("Base station is missing from graph.")

        if not nx.is_connected(graph):
            raise ValueError("Routing graph must be connected.")

        distances = nx.single_source_dijkstra_path_length(
            graph,
            bs_id,
            weight="weight",
        )

        candidates = {}

        for ch in selected_ch_ids:
            if ch not in graph or ch not in distances:
                raise ValueError(f"CH {ch} cannot reach the BS.")

            valid_neighbors = [
                neighbor
                for neighbor in graph.neighbors(ch)
                if neighbor in distances
                and distances[neighbor] < distances[ch]
            ]

            if not valid_neighbors:
                raise ValueError(
                    f"No valid next hop exists for CH {ch}."
                )

            candidates[ch] = valid_neighbors

        # Initialize pheromone for each allowed directed choice.
        pheromone = {
            (ch, neighbor): 1.0
            for ch, neighbors in candidates.items()
            for neighbor in neighbors
        }

        def choose_next_hop(ch):
            neighbors = candidates[ch]
            weights = []

            for neighbor in neighbors:
                distance = max(
                    float(graph[ch][neighbor].get("weight", 1.0)),
                    1e-9,
                )

                tau = pheromone[(ch, neighbor)] ** self.alpha
                eta = (1.0 / distance) ** self.beta

                weights.append(tau * eta)

            total = sum(weights)

            if total <= 0 or not all(
                weight < float("inf") for weight in weights
            ):
                return rng.choice(neighbors)

            probabilities = [
                weight / total for weight in weights
            ]

            return rng.choices(
                neighbors,
                weights=probabilities,
                k=1,
            )[0]

        def construct_solution():
            return {
                ch: choose_next_hop(ch)
                for ch in selected_ch_ids
            }

        def calculate_cost(parent_map):
            return sum(
                float(graph[ch][parent].get("weight", 1.0))
                for ch, parent in parent_map.items()
            )

        best_solution = None
        best_cost = float("inf")

        for _ in range(self.iterations):
            iteration_solutions = []

            # Every ant constructs a complete routing solution.
            for _ in range(self.num_ants):
                solution = construct_solution()
                cost = calculate_cost(solution)

                iteration_solutions.append((solution, cost))

                if cost < best_cost:
                    best_cost = cost
                    best_solution = solution.copy()

            # Evaporate old pheromone.
            for edge in pheromone:
                pheromone[edge] *= (
                    1.0 - self.evaporation_rate
                )

            # Deposit pheromone on good solutions.
            for solution, cost in iteration_solutions:
                deposit = self.pheromone_deposit / max(cost, 1e-9)

                for ch, parent in solution.items():
                    pheromone[(ch, parent)] += deposit

        return best_solution

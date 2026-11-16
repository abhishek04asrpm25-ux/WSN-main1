
import random
import networkx as nx

from simulation.algorithms.routing_interface import RoutingAlgorithm


class PSORouting(RoutingAlgorithm):
    """
    Particle Swarm Optimization for multi-hop routing.

    Each particle represents one next-hop choice for every CH.
    The objective is to minimize total CH-to-parent distance.

    Only neighbors that are closer to the BS in shortest-path
    distance are allowed. This prevents routing loops.
    """

    algorithm_name = "PSO Multi-Hop Routing"

    def __init__(
        self,
        swarm_size=40,
        iterations=100,
        inertia=0.7,
        cognitive=1.5,
        social=1.5,
        random_seed=42,
    ):
        self.swarm_size = max(5, int(swarm_size))
        self.iterations = max(1, int(iterations))
        self.inertia = float(inertia)
        self.cognitive = float(cognitive)
        self.social = float(social)
        self.random_seed = random_seed

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

        dimensions = len(selected_ch_ids)

        def decode(position):
            parent_map = {}

            for index, ch in enumerate(selected_ch_ids):
                options = candidates[ch]
                option_index = min(
                    int(position[index] * len(options)),
                    len(options) - 1,
                )
                parent_map[ch] = options[option_index]

            return parent_map

        def fitness(position):
            parent_map = decode(position)
            total_distance = 0.0

            for ch, parent in parent_map.items():
                total_distance += float(
                    graph[ch][parent].get("weight", 1.0)
                )

            return total_distance

        # Initialize particles.
        particles = [
            [rng.random() for _ in range(dimensions)]
            for _ in range(self.swarm_size)
        ]

        velocities = [
            [
                rng.uniform(-0.1, 0.1)
                for _ in range(dimensions)
            ]
            for _ in range(self.swarm_size)
        ]

        personal_best = [
            particle[:]
            for particle in particles
        ]

        personal_best_scores = [
            fitness(particle)
            for particle in particles
        ]

        best_index = min(
            range(self.swarm_size),
            key=lambda i: personal_best_scores[i],
        )

        global_best = personal_best[best_index][:]
        global_best_score = personal_best_scores[best_index]

        # PSO optimization.
        for _ in range(self.iterations):
            for particle_index in range(self.swarm_size):
                for dimension in range(dimensions):
                    r1 = rng.random()
                    r2 = rng.random()

                    velocity = (
                        self.inertia
                        * velocities[particle_index][dimension]
                        + self.cognitive
                        * r1
                        * (
                            personal_best[particle_index][dimension]
                            - particles[particle_index][dimension]
                        )
                        + self.social
                        * r2
                        * (
                            global_best[dimension]
                            - particles[particle_index][dimension]
                        )
                    )

                    # Limit velocity to keep the search stable.
                    velocity = max(-0.5, min(0.5, velocity))

                    velocities[particle_index][dimension] = velocity

                    position = (
                        particles[particle_index][dimension] + velocity
                    )

                    # Keep random-key positions in [0, 1).
                    position = max(0.0, min(0.999999, position))

                    particles[particle_index][dimension] = position

                current_score = fitness(particles[particle_index])

                if current_score < personal_best_scores[particle_index]:
                    personal_best_scores[particle_index] = current_score
                    personal_best[particle_index] = (
                        particles[particle_index][:]
                    )

                    if current_score < global_best_score:
                        global_best_score = current_score
                        global_best = particles[particle_index][:]

        return decode(global_best)

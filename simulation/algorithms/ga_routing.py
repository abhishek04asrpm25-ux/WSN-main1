
import random
import networkx as nx

from simulation.algorithms.routing_interface import RoutingAlgorithm


class GARouting(RoutingAlgorithm):
    """
    Genetic Algorithm for multi-hop routing between
    ANN-selected cluster heads and the Base Station.

    Chromosome:
        One next-hop choice for each selected cluster head.

    Objective:
        Minimize total routing distance while ensuring
        that every route reaches the Base Station.
    """

    algorithm_name = "GA Multi-Hop Routing"

    def __init__(
        self,
        population_size=60,
        generations=100,
        mutation_rate=0.10,
        crossover_rate=0.80,
        random_seed=42,
    ):
        self.population_size = max(10, int(population_size))
        self.generations = max(1, int(generations))
        self.mutation_rate = float(mutation_rate)
        self.crossover_rate = float(crossover_rate)
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

        # Find a shortest-path distance-to-BS potential.
        distances = nx.single_source_dijkstra_path_length(
            graph,
            bs_id,
            weight="weight",
        )

        # Every CH can choose only a neighbor closer to the BS.
        # This guarantees that routes cannot form cycles.
        candidates = {}

        for ch in selected_ch_ids:
            if ch not in graph or ch not in distances:
                raise ValueError(f"CH {ch} cannot reach the BS.")

            valid_neighbors = []

            for neighbor in graph.neighbors(ch):
                if neighbor not in distances:
                    continue

                if distances[neighbor] < distances[ch]:
                    valid_neighbors.append(neighbor)

            if not valid_neighbors:
                raise ValueError(
                    f"No valid next hop exists for CH {ch}."
                )

            candidates[ch] = valid_neighbors

        def chromosome_to_map(chromosome):
            return {
                ch: chromosome[index]
                for index, ch in enumerate(selected_ch_ids)
            }

        def fitness(chromosome):
            parent_map = chromosome_to_map(chromosome)

            total_distance = 0.0

            for ch in selected_ch_ids:
                parent = parent_map[ch]

                if not graph.has_edge(ch, parent):
                    return float("inf")

                total_distance += float(
                    graph[ch][parent].get("weight", 1.0)
                )

            return total_distance

        def create_individual():
            return [
                rng.choice(candidates[ch])
                for ch in selected_ch_ids
            ]

        def tournament_selection(population, scores):
            choices = rng.sample(
                range(len(population)),
                min(3, len(population)),
            )

            winner = min(choices, key=lambda i: scores[i])
            return population[winner][:]

        population = [
            create_individual()
            for _ in range(self.population_size)
        ]

        best_chromosome = None
        best_score = float("inf")

        for _ in range(self.generations):
            scores = [fitness(ind) for ind in population]

            generation_best = min(
                range(len(population)),
                key=lambda i: scores[i],
            )

            if scores[generation_best] < best_score:
                best_score = scores[generation_best]
                best_chromosome = population[generation_best][:]

            # Elitism: preserve the best solution.
            new_population = [best_chromosome[:]]

            while len(new_population) < self.population_size:
                parent1 = tournament_selection(population, scores)
                parent2 = tournament_selection(population, scores)

                child1 = parent1[:]
                child2 = parent2[:]

                # Uniform crossover.
                if rng.random() < self.crossover_rate:
                    for i in range(len(selected_ch_ids)):
                        if rng.random() < 0.5:
                            child1[i], child2[i] = (
                                child2[i],
                                child1[i],
                            )

                # Mutation.
                for child in (child1, child2):
                    for i, ch in enumerate(selected_ch_ids):
                        if rng.random() < self.mutation_rate:
                            child[i] = rng.choice(candidates[ch])

                new_population.append(child1)

                if len(new_population) < self.population_size:
                    new_population.append(child2)

            population = new_population

        return chromosome_to_map(best_chromosome)

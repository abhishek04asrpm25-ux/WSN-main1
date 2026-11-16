
import random
import math


class GeneticAlgorithmCHSelector:
    """
    Connectivity-aware Genetic Algorithm for WSN Cluster Head selection.

    Each chromosome contains exactly K unique alive sensor-node IDs.

    Important connectivity condition:
        Every selected CH must be able to reach the BS using
        only selected CHs as intermediate forwarding nodes.

    All links use the same communication range.
    """

    BS_ID = "BS"

    def __init__(self, config, communication_range):
        self.config = config
        self.communication_range = float(communication_range)

        ga_config = config.get("ga_parameters", {})

        self.population_size = int(
            ga_config.get("population_size", 40)
        )
        self.generations = int(
            ga_config.get("generations", 60)
        )
        self.tournament_size = int(
            ga_config.get("tournament_size", 3)
        )
        self.crossover_rate = float(
            ga_config.get("crossover_rate", 0.85)
        )
        self.mutation_rate = float(
            ga_config.get("mutation_rate", 0.15)
        )
        self.elitism_count = int(
            ga_config.get("elitism_count", 2)
        )
        self.random_seed = int(
            ga_config.get("random_seed", 42)
        )

        simulation_config = config.get("simulation", {})
        self.num_cluster_heads = int(
            simulation_config.get("num_cluster_heads", 10)
        )

        self._validate_parameters()

        self.rng = random.Random(self.random_seed)
        self.history = []

        self.adjacency = {}
        self.gateway_ids = []
        self.reachable_sensor_ids = set()
        self.base_station = None

    def _validate_parameters(self):
        if not math.isfinite(self.communication_range):
            raise ValueError("Communication range must be finite.")

        if self.communication_range <= 0:
            raise ValueError("Communication range must be positive.")

        if self.population_size < 2:
            raise ValueError("Population size must be at least 2.")

        if self.generations < 1:
            raise ValueError("Generations must be at least 1.")

        if self.tournament_size < 1:
            raise ValueError("Tournament size must be at least 1.")

        if not 0 <= self.crossover_rate <= 1:
            raise ValueError("Crossover rate must be between 0 and 1.")

        if not 0 <= self.mutation_rate <= 1:
            raise ValueError("Mutation rate must be between 0 and 1.")

        if not 1 <= self.elitism_count < self.population_size:
            raise ValueError(
                "Elitism count must be at least 1 "
                "and less than population size."
            )

        if self.num_cluster_heads < 1:
            raise ValueError("Number of Cluster Heads must be positive.")

    @staticmethod
    def distance(node_a, node_b):
        dx = float(node_a["x"]) - float(node_b["x"])
        dy = float(node_a["y"]) - float(node_b["y"])
        return math.hypot(dx, dy)

    @staticmethod
    def _get_node_map(nodes):
        return {node["id"]: node for node in nodes}

    def _get_alive_nodes(self, network):
        return [
            node for node in network["nodes"]
            if node.get("alive", True)
            and float(node.get("residual_energy", 0)) > 0
        ]

    def _get_base_station(self, network):
        """
        Read BS coordinates from the generated network first.
        Fall back to the original configuration if necessary.
        """

        bs = network.get("base_station") or network.get("bs")

        if isinstance(bs, dict) and "x" in bs and "y" in bs:
            return {
                "x": float(bs["x"]),
                "y": float(bs["y"])
            }

        network_config = self.config.get("network", {})
        bs = network_config.get("base_station", {})

        if isinstance(bs, dict) and "x" in bs and "y" in bs:
            return {
                "x": float(bs["x"]),
                "y": float(bs["y"])
            }

        raise ValueError(
            "Base Station coordinates were not found. "
            "Expected network['base_station'] or "
            "config['network']['base_station']."
        )

    def _build_connectivity(self, nodes, network):
        """
        Build an adjacency list using all alive sensor nodes and BS.

        This full network is used only to find feasible CH candidates.
        A selected chromosome must still be connected using only
        its selected CHs and the BS.
        """

        self.base_station = self._get_base_station(network)

        self.adjacency = {
            node["id"]: set()
            for node in nodes
        }
        self.adjacency[self.BS_ID] = set()

        # Sensor-to-sensor links.
        for index, node_a in enumerate(nodes):
            for node_b in nodes[index + 1:]:
                distance = self.distance(node_a, node_b)

                if distance <= self.communication_range + 1e-9:
                    self.adjacency[node_a["id"]].add(node_b["id"])
                    self.adjacency[node_b["id"]].add(node_a["id"])

        # Sensor-to-BS links.
        self.gateway_ids = []

        for node in nodes:
            distance = self.distance(node, self.base_station)

            if distance <= self.communication_range + 1e-9:
                node_id = node["id"]

                self.adjacency[node_id].add(self.BS_ID)
                self.adjacency[self.BS_ID].add(node_id)

                self.gateway_ids.append(node_id)

        # Find all alive sensor nodes connected to the BS
        # in the complete alive-node connectivity graph.
        self.reachable_sensor_ids = set()
        pending = [self.BS_ID]
        visited = {self.BS_ID}

        while pending:
            current = pending.pop()

            for neighbor in self.adjacency[current]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    pending.append(neighbor)

                    if neighbor != self.BS_ID:
                        self.reachable_sensor_ids.add(neighbor)

    def _is_connected_chromosome(self, chromosome):
        """
        Check whether every selected CH can reach BS using
        only selected CHs and the BS.
        """

        selected = set(chromosome)

        if not selected:
            return False

        if not selected.intersection(self.gateway_ids):
            return False

        pending = [self.BS_ID]
        visited = {self.BS_ID}

        while pending:
            current = pending.pop()

            for neighbor in self.adjacency.get(current, set()):
                if neighbor == self.BS_ID:
                    continue

                if neighbor in selected and neighbor not in visited:
                    visited.add(neighbor)
                    pending.append(neighbor)

        return selected.issubset(visited)

    def _grow_connected_chromosome(self, preferred_ids=None):
        """
        Construct a connected chromosome.

        Start from a CH that has a direct BS link, then repeatedly
        add a sensor node adjacent to an already selected CH.

        preferred_ids are genes inherited from the parents.
        They are preferred when they are valid frontier candidates.
        """

        if not self.gateway_ids:
            raise ValueError(
                "No alive sensor node is within communication range "
                "of the Base Station. A CH-to-BS route is impossible."
            )

        preferred = set(preferred_ids or [])

        gateway = self.rng.choice(self.gateway_ids)
        selected = {gateway}

        while len(selected) < self.num_cluster_heads:
            frontier = set()

            for selected_id in selected:
                frontier.update(self.adjacency[selected_id])

            frontier.discard(self.BS_ID)
            frontier.difference_update(selected)

            frontier.intersection_update(self.reachable_sensor_ids)

            if not frontier:
                raise ValueError(
                    "Unable to construct a connected CH group. "
                    "The BS-connected sensor component contains "
                    "too few eligible nodes."
                )

            preferred_frontier = frontier.intersection(preferred)

            if preferred_frontier and self.rng.random() < 0.75:
                candidate = self.rng.choice(list(preferred_frontier))
            else:
                candidate = self.rng.choice(list(frontier))

            selected.add(candidate)

        chromosome = tuple(
            sorted(selected, key=str)
        )

        return chromosome

    def _create_chromosome(self, eligible_ids=None):
        return self._grow_connected_chromosome()

    def _evaluate_fitness(self, chromosome, nodes, node_map):
        """
        Higher fitness is better.

        Objectives:
        1. Normal-node coverage.
        2. Cluster compactness.
        3. Residual energy of selected CHs.
        4. Cluster-size balance.

        Connectivity is a hard feasibility condition:
        an invalid chromosome receives negative infinity.
        """

        if len(chromosome) != self.num_cluster_heads:
            return float("-inf"), {}

        if len(set(chromosome)) != self.num_cluster_heads:
            return float("-inf"), {}

        if not self._is_connected_chromosome(chromosome):
            return float("-inf"), {}

        selected_heads = [
            node_map[node_id]
            for node_id in chromosome
        ]

        cluster_members = {
            ch_id: [ch_id]
            for ch_id in chromosome
        }

        total_distance = 0.0
        assigned_normal_nodes = 0

        alive_normal_nodes = [
            node for node in nodes
            if node["id"] not in chromosome
        ]

        for node in alive_normal_nodes:
            best_ch_id = None
            best_distance = float("inf")

            for ch in selected_heads:
                distance = self.distance(node, ch)

                if (
                    distance <= self.communication_range
                    and distance < best_distance
                ):
                    best_distance = distance
                    best_ch_id = ch["id"]

            if best_ch_id is not None:
                cluster_members[best_ch_id].append(node["id"])
                total_distance += best_distance
                assigned_normal_nodes += 1

        total_normal_nodes = len(alive_normal_nodes)

        if total_normal_nodes == 0:
            coverage = 1.0
        else:
            coverage = assigned_normal_nodes / total_normal_nodes

        if assigned_normal_nodes == 0:
            compactness = 0.0
        else:
            average_distance = total_distance / assigned_normal_nodes

            compactness = max(
                0.0,
                1.0 - average_distance / self.communication_range
            )

        initial_energy = float(
            nodes[0].get("initial_energy", 0.5)
        )

        if initial_energy <= 0:
            raise ValueError("Initial node energy must be positive.")

        average_ch_energy = sum(
            float(ch["residual_energy"]) / initial_energy
            for ch in selected_heads
        ) / len(selected_heads)

        energy_score = max(
            0.0,
            min(1.0, average_ch_energy)
        )

        cluster_sizes = [
            len(members)
            for members in cluster_members.values()
        ]

        mean_size = sum(cluster_sizes) / len(cluster_sizes)

        if mean_size == 0:
            balance_score = 0.0
        else:
            variance = sum(
                (size - mean_size) ** 2
                for size in cluster_sizes
            ) / len(cluster_sizes)

            standard_deviation = math.sqrt(variance)
            coefficient_of_variation = standard_deviation / mean_size

            balance_score = 1.0 / (
                1.0 + coefficient_of_variation
            )

        fitness = (
            0.50 * coverage
            + 0.20 * compactness
            + 0.20 * energy_score
            + 0.10 * balance_score
        )

        details = {
            "coverage": coverage,
            "compactness": compactness,
            "energy_score": energy_score,
            "balance_score": balance_score,
            "cluster_members": cluster_members,
            "assigned_nodes": assigned_normal_nodes,
            "unassigned_nodes": total_normal_nodes - assigned_normal_nodes,
            "connectivity_feasible": True
        }

        return fitness, details

    def _tournament_selection(self, population, fitness_scores):
        contestants = self.rng.sample(
            population,
            min(self.tournament_size, len(population))
        )

        return max(
            contestants,
            key=lambda chromosome: fitness_scores[chromosome]
        )

    def _crossover(self, parent_a, parent_b, eligible_ids=None):
        """
        Produce exactly K unique CH IDs while preserving connectivity.
        """

        preferred = set(parent_a) | set(parent_b)

        return self._grow_connected_chromosome(preferred)

    def _mutate(self, chromosome, eligible_ids=None):
        """
        Mutation regenerates a connected chromosome.

        The original chromosome is retained when mutation does not occur.
        """

        if self.rng.random() >= self.mutation_rate:
            return chromosome

        return self._grow_connected_chromosome(
            preferred_ids=chromosome
        )

    def select_cluster_heads(self, network):
        nodes = self._get_alive_nodes(network)

        if len(nodes) < self.num_cluster_heads:
            raise ValueError(
                f"Only {len(nodes)} alive nodes are available, "
                f"but {self.num_cluster_heads} Cluster Heads are required."
            )

        node_map = self._get_node_map(nodes)

        if len(node_map) != len(nodes):
            raise ValueError("Sensor node IDs must be unique.")

        # Build the full alive-node connectivity information.
        self._build_connectivity(nodes, network)

        if not self.gateway_ids:
            raise ValueError(
                "No alive sensor node can directly communicate with BS "
                f"within the {self.communication_range} m range."
            )

        if len(self.reachable_sensor_ids) < self.num_cluster_heads:
            raise ValueError(
                "The BS-connected component contains only "
                f"{len(self.reachable_sensor_ids)} alive sensor nodes, "
                f"but {self.num_cluster_heads} connected CHs are required. "
                "Check the deployment, BS position or communication range."
            )

        eligible_ids = list(self.reachable_sensor_ids)

        self.history = []

        # Every initial chromosome is connected to the BS.
        population = [
            self._create_chromosome(eligible_ids)
            for _ in range(self.population_size)
        ]

        best_chromosome = None
        best_fitness = float("-inf")
        best_details = None

        for generation in range(self.generations):
            fitness_scores = {}
            details_by_chromosome = {}

            for chromosome in population:
                fitness, details = self._evaluate_fitness(
                    chromosome,
                    nodes,
                    node_map
                )

                fitness_scores[chromosome] = fitness
                details_by_chromosome[chromosome] = details

            generation_best = max(
                population,
                key=lambda chromosome: fitness_scores[chromosome]
            )

            generation_best_fitness = fitness_scores[generation_best]

            if generation_best_fitness > best_fitness:
                best_fitness = generation_best_fitness
                best_chromosome = generation_best
                best_details = details_by_chromosome[generation_best]

            self.history.append({
                "generation": generation + 1,
                "best_fitness": generation_best_fitness,
                "overall_best_fitness": best_fitness
            })

            ranked_population = sorted(
                population,
                key=lambda chromosome: fitness_scores[chromosome],
                reverse=True
            )

            next_population = ranked_population[
                :self.elitism_count
            ]

            while len(next_population) < self.population_size:
                parent_a = self._tournament_selection(
                    population,
                    fitness_scores
                )

                parent_b = self._tournament_selection(
                    population,
                    fitness_scores
                )

                if self.rng.random() < self.crossover_rate:
                    child = self._crossover(
                        parent_a,
                        parent_b,
                        eligible_ids
                    )
                else:
                    child = parent_a

                child = self._mutate(child, eligible_ids)

                next_population.append(child)

            population = next_population

        selected_ch_ids = list(best_chromosome)

        # Reset cluster information for all sensor nodes.
        for node in network["nodes"]:
            node["is_cluster_head"] = False
            node["cluster_id"] = None

        # Mark selected Cluster Heads.
        for ch_id in selected_ch_ids:
            node_map[ch_id]["is_cluster_head"] = True
            node_map[ch_id]["cluster_id"] = ch_id

        # Assign covered normal nodes to their nearest selected CH.
        for ch_id, member_ids in best_details["cluster_members"].items():
            for member_id in member_ids:
                node_map[member_id]["cluster_id"] = ch_id

        # Identify selected CHs with direct BS links.
        direct_bs_ch_ids = [
            ch_id
            for ch_id in selected_ch_ids
            if self.BS_ID in self.adjacency[ch_id]
        ]

        return {
            "selected_ch_ids": selected_ch_ids,
            "fitness": best_fitness,
            "cluster_members": best_details["cluster_members"],
            "metrics": {
                "coverage": best_details["coverage"],
                "compactness": best_details["compactness"],
                "energy_score": best_details["energy_score"],
                "balance_score": best_details["balance_score"],
                "assigned_nodes": best_details["assigned_nodes"],
                "unassigned_nodes": best_details["unassigned_nodes"],
                "connectivity_feasible": True,
                "direct_bs_ch_ids": direct_bs_ch_ids,
                "number_of_direct_bs_links": len(direct_bs_ch_ids)
            },
            "history": self.history
        }

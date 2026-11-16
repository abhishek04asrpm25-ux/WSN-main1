"""ANN-based multi-hop next-hop selection.

Inputs follow the project specification: neighbor residual energy,
CH-to-neighbor distance, neighbor-to-BS distance, estimated TX energy,
and link quality (LQI).

Training labels in this prototype are heuristic pseudo-labels, not
optimal labels produced by Dijkstra/ILP. The API reports this explicitly.
"""
import numpy as np
import networkx as nx
import time
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler

from simulation.algorithms.routing_interface import RoutingAlgorithm


class ANNRouting(RoutingAlgorithm):
    algorithm_name = "ANN Multi-Hop Routing"

    def __init__(self, training_samples=5000, random_seed=42):
        self.training_samples = int(training_samples)
        self.random_seed = int(random_seed)
        if self.training_samples < 100:
            raise ValueError("Use at least 100 training samples.")
        self.scaler = StandardScaler()
        # Three dense hidden layers; sklearn's logistic output and log-loss
        # implement a binary cross-entropy style objective.
        self.model = MLPClassifier(
            hidden_layer_sizes=(64, 32, 16),
            activation="relu",
            solver="adam",
            max_iter=500,
            random_state=self.random_seed,
            early_stopping=True,
        )
        self.training_result = self.train()

    def train(self):
        training_started_at = time.perf_counter()
        rng = np.random.default_rng(self.random_seed)
        X = rng.uniform(0.0, 1.0, size=(self.training_samples, 5))
        energy, link_distance, neighbor_bs_distance, tx_energy, lqi = X.T
        # Explicit prototype labels. Replace with topology-generated
        # Dijkstra/ILP optimal labels for research-grade supervised training.
        suitability = (
            0.30 * energy
            + 0.20 * (1.0 - link_distance)
            + 0.20 * (1.0 - neighbor_bs_distance)
            + 0.20 * (1.0 - tx_energy)
            + 0.10 * lqi
        )
        y = (suitability >= np.quantile(suitability, 0.60)).astype(int)
        X_scaled = self.scaler.fit_transform(X)
        self.model.fit(X_scaled, y)
        return {
            "training_samples": self.training_samples,
            "training_accuracy": float(self.model.score(X_scaled, y)),
            "label_source": "synthetic heuristic pseudo-labels",
            "architecture": "5-64-32-16-1",
            "output": "sigmoid probability",
            "loss": "binary cross-entropy (log loss)",
            "optimal_dijkstra_ilp_labels": False,
            "training_time_s": time.perf_counter() - training_started_at,
        }

    @staticmethod
    def _energy(graph, node_id):
        return max(0.0, float(graph.nodes[node_id].get(
            "residual_energy", graph.nodes[node_id].get("energy", 0.5)
        )))

    @staticmethod
    def _tx_energy(distance, packet_bits=4000):
        d = max(0.0, float(distance))
        d0 = 87.7
        if d < d0:
            return packet_bits * (5e-8 + 1e-11 * d * d)
        return packet_bits * (5e-8 + 1.3e-15 * d ** 4)

    def find_routes(self, graph, selected_ch_ids, bs_id="BS"):
        selected_ch_ids = list(selected_ch_ids)
        if not selected_ch_ids:
            return {}
        if bs_id not in graph:
            raise ValueError("Base station is missing from graph.")
        if not nx.is_connected(graph):
            raise ValueError("Routing graph must be connected.")

        # Shortest-path distance to BS supplies a strict progress measure.
        distances = nx.single_source_dijkstra_path_length(
            graph, bs_id, weight="weight"
        )
        max_energy = max(
            (self._energy(graph, n) for n in graph if n != bs_id), default=1.0
        ) or 1.0
        max_dist = max(distances.values(), default=1.0) or 1.0
        edge_lengths = [float(d.get("weight", 1.0)) for _, _, d in graph.edges(data=True)]
        max_link = max(edge_lengths, default=1.0) or 1.0
        max_tx = max((self._tx_energy(d) for d in edge_lengths), default=1.0) or 1.0

        parent_map = {}
        for ch in selected_ch_ids:
            if ch not in graph or ch not in distances:
                raise ValueError(f"CH {ch} cannot reach the BS.")
            candidates = [
                n for n in graph.neighbors(ch)
                if n in distances and distances[n] < distances[ch]
                and self._energy(graph, n) > 0
            ]
            if not candidates:
                # Safe fallback: shortest path's first hop, if available.
                try:
                    path = nx.shortest_path(graph, ch, bs_id, weight="weight")
                    candidates = [path[1]] if len(path) > 1 else []
                except (nx.NetworkXNoPath, nx.NodeNotFound):
                    candidates = []
            if not candidates:
                raise ValueError(f"No feasible next hop exists for CH {ch}.")

            rows = []
            for candidate in candidates:
                edge_distance = float(graph[ch][candidate].get("weight", 1.0))
                lqi = float(graph[ch][candidate].get("lqi", 0.8))
                rows.append([
                    np.clip(self._energy(graph, candidate) / max_energy, 0, 1),
                    np.clip(edge_distance / max_link, 0, 1),
                    np.clip(distances[candidate] / max_dist, 0, 1),
                    np.clip(self._tx_energy(edge_distance) / max_tx, 0, 1),
                    np.clip(lqi, 0, 1),
                ])
            X = self.scaler.transform(np.asarray(rows, dtype=float))
            probabilities = self.model.predict_proba(X)[:, 1]
            parent_map[ch] = candidates[int(np.argmax(probabilities))]
        return parent_map

    def solve(self, graph, selected_ch_ids, bs_id="BS"):
        parent_map = self.find_routes(graph, selected_ch_ids, bs_id)
        routes = {}
        total_distance = 0.0
        for ch in selected_ch_ids:
            path = [ch]
            seen = set()
            current = ch
            while current != bs_id:
                if current in seen:
                    raise ValueError("ANN routing loop detected.")
                seen.add(current)
                if current not in parent_map:
                    raise ValueError(f"Missing ANN next hop for CH {current}.")
                nxt = parent_map[current]
                total_distance += float(graph[current][nxt].get("weight", 1.0))
                path.append(nxt)
                current = nxt
            routes[ch] = path
        valid = all(
            route and route[-1] == bs_id and len(route) == len(set(route))
            for route in routes.values()
        )
        return {
            "algorithm": self.algorithm_name,
            "parent_map": parent_map,
            "validation": {
                "valid": valid,
                "routes": routes,
                "total_distance": total_distance,
            },
            "training": self.training_result,
        }

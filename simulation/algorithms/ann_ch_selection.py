
import numpy as np
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler


class ANNClusterHeadSelector:
    """
    ANN-based cluster-head selection.

    Six input features:
        1. Residual energy
        2. Distance to BS
        3. Average distance to neighbours
        4. Node degree
        5. Average neighbour energy
        6. Average link quality (LQI)

    The initial model uses heuristic-generated training labels.
    This is a prototype and must be evaluated against independent
    baselines before making research performance claims.
    """

    def __init__(
        self,
        num_cluster_heads=10,
        random_seed=42,
        communication_range=60.0,
        initial_energy=0.5,
    ):
        self.num_cluster_heads = num_cluster_heads
        self.random_seed = random_seed
        self.communication_range = max(float(communication_range), 1e-9)
        self.initial_energy = max(float(initial_energy), 1e-9)

        self.scaler = StandardScaler()

        self.model = MLPClassifier(
            hidden_layer_sizes=(32, 16),
            activation="relu",
            solver="adam",
            max_iter=500,
            random_state=random_seed,
            early_stopping=True,
        )

        self.is_trained = False

    @staticmethod
    def _distance(a, b):
        return float(
            np.hypot(
                float(a["x"]) - float(b["x"]),
                float(a["y"]) - float(b["y"]),
            )
        )

    def _extract_features(self, nodes, base_station):
        alive_nodes = [
            node for node in nodes
            if node.get("alive", True)
            and float(node.get("residual_energy", 0)) > 0
        ]

        node_map = {node["id"]: node for node in alive_nodes}

        features = []
        valid_nodes = []

        for node in alive_nodes:
            neighbors = [
                node_map[nid]
                for nid in node.get("neighbors", [])
                if nid in node_map and nid != node["id"]
            ]

            avg_neighbor_distance = (
                np.mean([
                    self._distance(node, neighbor)
                    for neighbor in neighbors
                ])
                if neighbors else 0.0
            )

            avg_neighbor_energy = (
                np.mean([
                    float(neighbor["residual_energy"])
                    for neighbor in neighbors
                ])
                if neighbors else 0.0
            )

            lqi_values = [
                float(neighbor.get("lqi", 0.8))
                for neighbor in neighbors
            ]

            avg_lqi = (
                np.mean(lqi_values)
                if lqi_values else 0.0
            )

            distance_to_bs = self._distance(
                node,
                base_station,
            )

            # The ANN is trained on [0, 1] features. Keep inference on
            # the same scale so distance/degree cannot overwhelm energy.
            max_bs_distance = max(
                self.communication_range * 3.0,
                1.0,
            )
            max_degree = max(
                len(node.get("neighbors", [])) for node in alive_nodes
            ) or 1
            features.append([
                np.clip(float(node["residual_energy"]) / self.initial_energy, 0.0, 1.0),
                np.clip(distance_to_bs / max_bs_distance, 0.0, 1.0),
                np.clip(avg_neighbor_distance / self.communication_range, 0.0, 1.0),
                np.clip(len(neighbors) / max_degree, 0.0, 1.0),
                np.clip(avg_neighbor_energy / self.initial_energy, 0.0, 1.0),
                np.clip(avg_lqi, 0.0, 1.0),
            ])

            valid_nodes.append(node)

        return np.asarray(features, dtype=float), valid_nodes

    def train(self, training_samples=5000):
        rng = np.random.default_rng(self.random_seed)

        X = rng.uniform(0, 1, size=(training_samples, 6))

        # Features are normalized for training.
        # A transparent heuristic supplies prototype labels.
        energy = X[:, 0]
        distance_score = 1.0 - X[:, 1]
        connectivity = X[:, 3]
        neighbor_energy = X[:, 4]
        lqi = X[:, 5]

        degree_score = connectivity

        suitability = (
            0.35 * energy
            + 0.20 * distance_score
            + 0.15 * degree_score
            + 0.15 * neighbor_energy
            + 0.15 * lqi
        )

        threshold = np.quantile(suitability, 0.65)
        y = (suitability >= threshold).astype(int)

        X_scaled = self.scaler.fit_transform(X)

        self.model.fit(X_scaled, y)
        self.is_trained = True

        return {
            "training_samples": training_samples,
            "training_accuracy": float(
                self.model.score(X_scaled, y)
            ),
            "label_source": "heuristic",
        }

    def select_cluster_heads(
        self,
        nodes,
        base_station,
    ):
        if not self.is_trained:
            self.train()

        X, valid_nodes = self._extract_features(
            nodes,
            base_station,
        )

        if len(valid_nodes) < self.num_cluster_heads:
            raise ValueError(
                "Not enough alive nodes for cluster-head selection."
            )

        X_scaled = self.scaler.transform(X)

        probabilities = self.model.predict_proba(X_scaled)

        positive_class_index = list(
            self.model.classes_
        ).index(1)

        model_scores = probabilities[:, positive_class_index]

        # Keep the trained ANN as the primary selector while using its
        # normalized live inputs to make round-to-round energy changes
        # influence rankings. This is a transparent hybrid score, not a
        # claim that the prototype ANN learned from real deployment data.
        energy = X[:, 0]
        distance_score = 1.0 - X[:, 1]
        degree_score = X[:, 3]
        neighbor_energy = X[:, 4]
        lqi = X[:, 5]
        live_suitability = (
            0.35 * energy
            + 0.20 * distance_score
            + 0.15 * degree_score
            + 0.15 * neighbor_energy
            + 0.15 * lqi
        )
        scores = 0.70 * model_scores + 0.30 * live_suitability

        # Stable deterministic tie breaking by node ID.
        ranked_indices = sorted(
            range(len(scores)),
            key=lambda index: (float(scores[index]), -int(valid_nodes[index]["id"])),
            reverse=True,
        )

        # Connectivity-constrained ANN selection: first choose from nodes
        # that can directly reach the BS, then expand the CH set through
        # one-hop reachable candidates. This guarantees every selected CH
        # has a CH-to-BS path in the routing graph.
        node_by_id = {node["id"]: node for node in valid_nodes}
        score_by_id = {
            valid_nodes[index]["id"]: float(scores[index])
            for index in range(len(valid_nodes))
        }
        base_candidates = [
            node for node in valid_nodes
            if self._distance(node, base_station) <= self.communication_range
        ]
        if not base_candidates:
            raise ValueError(
                "No alive sensor node can directly reach the base station."
            )

        base_candidates.sort(
            key=lambda node: (-score_by_id[node["id"]], int(node["id"]))
        )
        selected_ids = [node["id"] for node in base_candidates[:self.num_cluster_heads]]

        while len(selected_ids) < min(self.num_cluster_heads, len(valid_nodes)):
            frontier = []
            for candidate in valid_nodes:
                candidate_id = candidate["id"]
                if candidate_id in selected_ids:
                    continue
                if any(
                    self._distance(candidate, node_by_id[selected_id]) <= self.communication_range
                    for selected_id in selected_ids
                ):
                    frontier.append(candidate)
            if not frontier:
                break
            frontier.sort(
                key=lambda node: (-score_by_id[node["id"]], int(node["id"]))
            )
            selected_ids.append(frontier[0]["id"])

        if len(selected_ids) < min(self.num_cluster_heads, len(valid_nodes)):
            raise ValueError(
                "Could not select enough connected cluster heads."
            )

        return {
            "selected_ch_ids": selected_ids,
            "scores": {
                valid_nodes[index]["id"]: float(scores[index])
                for index in range(len(valid_nodes))
            },
            "algorithm": "ANN Cluster-Head Selection",
        }

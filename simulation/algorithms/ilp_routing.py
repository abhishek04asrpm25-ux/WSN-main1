
import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import lil_matrix

from simulation.algorithms.routing_interface import RoutingAlgorithm


class ILPRouting(RoutingAlgorithm):
    """
    Integer Linear Programming (ILP) based global WSN routing.

    Decision variable:
        x[i,j] = 1 if cluster head i sends data to parent j.

    Each CH selects exactly one parent. A flow formulation ensures
    that every selected CH eventually reaches the base station.

    Objective:
        Minimize total CH-to-parent communication distance.
    """

    algorithm_name = "ILP"

    def find_routes(self, graph, selected_ch_ids, bs_id="BS"):
        selected_ch_ids = list(selected_ch_ids)

        if not selected_ch_ids:
            raise ValueError("No cluster heads were provided.")

        if bs_id not in graph.nodes:
            raise ValueError("Base station is missing from the graph.")

        if len(selected_ch_ids) != len(set(selected_ch_ids)):
            raise ValueError("Duplicate cluster-head IDs were provided.")

        for ch in selected_ch_ids:
            if ch not in graph.nodes:
                raise ValueError(f"Cluster head {ch} is missing from graph.")

        ch_set = set(selected_ch_ids)
        n = len(selected_ch_ids)

        # Create directed candidate links: CH -> another CH or BS.
        arcs = []
        weights = []

        for u, v, data in graph.edges(data=True):
            weight = float(data.get("weight", 1.0))

            if not np.isfinite(weight) or weight < 0:
                raise ValueError("ILP requires finite, non-negative link weights.")

            if u in ch_set and (v in ch_set or v == bs_id):
                arcs.append((u, v))
                weights.append(weight)

            if v in ch_set and (u in ch_set or u == bs_id):
                arcs.append((v, u))
                weights.append(weight)

        if not arcs:
            raise ValueError("No valid CH-to-parent communication links exist.")

        m = len(arcs)

        # Variables:
        # First m variables: binary parent-selection variables x.
        # Next m variables: continuous flow variables f.
        variable_count = 2 * m

        objective = np.zeros(variable_count)
        objective[:m] = weights

        integrality = np.zeros(variable_count, dtype=int)
        integrality[:m] = 1

        lower_bounds = np.zeros(variable_count)
        upper_bounds = np.ones(variable_count)
        upper_bounds[m:] = n

        bounds = Bounds(lower_bounds, upper_bounds)

        # Constraints:
        # 1. Exactly one outgoing parent edge per CH.
        # 2. Each CH sends one unit of flow towards BS.
        # 3. BS receives n units of flow.
        # 4. Flow can use an edge only when that edge is selected.
        row_count = n + n + 1 + m
        matrix = lil_matrix((row_count, variable_count), dtype=float)

        constraint_lower = np.full(row_count, -np.inf)
        constraint_upper = np.full(row_count, np.inf)

        row = 0

        # Constraint 1: one parent per CH.
        for ch in selected_ch_ids:
            for edge_index, (child, parent) in enumerate(arcs):
                if child == ch:
                    matrix[row, edge_index] = 1.0

            constraint_lower[row] = 1.0
            constraint_upper[row] = 1.0
            row += 1

        # Constraint 2: every CH contributes one unit of flow.
        for ch in selected_ch_ids:
            for edge_index, (child, parent) in enumerate(arcs):
                flow_index = m + edge_index

                if child == ch:
                    matrix[row, flow_index] += 1.0

                if parent == ch:
                    matrix[row, flow_index] -= 1.0

            constraint_lower[row] = 1.0
            constraint_upper[row] = 1.0
            row += 1

        # Constraint 3: the BS receives all n units.
        for edge_index, (child, parent) in enumerate(arcs):
            if parent == bs_id:
                matrix[row, m + edge_index] = 1.0

        constraint_lower[row] = float(n)
        constraint_upper[row] = float(n)
        row += 1

        # Constraint 4: f[i,j] <= n * x[i,j].
        for edge_index in range(m):
            matrix[row, m + edge_index] = 1.0
            matrix[row, edge_index] = -float(n)

            constraint_upper[row] = 0.0
            row += 1

        constraints = LinearConstraint(
            matrix.tocsr(),
            constraint_lower,
            constraint_upper,
        )

        result = milp(
            c=objective,
            integrality=integrality,
            bounds=bounds,
            constraints=constraints,
            options={"time_limit": 30.0},
        )

        if not result.success or result.x is None:
            raise RuntimeError(
                f"ILP optimization failed: {result.message}"
            )

        parent_map = {}

        for edge_index, (child, parent) in enumerate(arcs):
            if result.x[edge_index] > 0.5:
                if child in parent_map:
                    raise RuntimeError(
                        f"ILP selected multiple parents for CH {child}."
                    )

                parent_map[child] = parent

        if set(parent_map) != ch_set:
            raise RuntimeError(
                "ILP did not select exactly one parent for every CH."
            )

        return parent_map

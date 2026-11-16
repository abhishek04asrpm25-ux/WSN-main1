
class RoutingResultValidator:
    """
    Validates a global routing solution.

    Convention:
        parent_map[child_CH] = next hop towards the base station.
    """

    @staticmethod
    def validate_parent_map(graph, selected_ch_ids, parent_map, bs_id="BS"):
        errors = []
        routes = {}
        total_distance = 0.0

        nodes = graph.nodes

        if bs_id not in nodes:
            return {
                "valid": False,
                "is_valid": False,
                "errors": [f"Base station {bs_id} is missing from graph."],
                "routes": {},
                "total_distance": 0.0,
            }

        selected_ch_ids = list(selected_ch_ids)

        if len(selected_ch_ids) != len(set(selected_ch_ids)):
            errors.append("Duplicate cluster-head IDs were supplied.")

        if set(parent_map.keys()) != set(selected_ch_ids):
            errors.append(
                "Parent map must contain exactly one entry for every selected CH."
            )

        # Build a convenient undirected edge lookup.
        edge_lookup = {}

        for u, v, data in graph.edges(data=True):
            edge_lookup[frozenset((u, v))] = data

        # Validate every CH route independently.
        for ch_id in selected_ch_ids:
            if ch_id not in nodes:
                errors.append(f"Cluster head {ch_id} is missing from graph.")
                continue

            if ch_id not in parent_map:
                errors.append(f"Cluster head {ch_id} has no parent.")
                continue

            route = [ch_id]
            visited = {ch_id}
            current = ch_id

            while current != bs_id:
                if current not in parent_map:
                    errors.append(
                        f"Route from CH {ch_id} does not reach the base station."
                    )
                    break

                next_hop = parent_map[current]

                if next_hop not in nodes:
                    errors.append(
                        f"Invalid next hop {next_hop} in route from CH {ch_id}."
                    )
                    break

                edge_key = frozenset((current, next_hop))

                if edge_key not in edge_lookup:
                    errors.append(
                        f"No communication link exists between {current} "
                        f"and {next_hop}."
                    )
                    break

                if next_hop in visited:
                    errors.append(
                        f"Routing loop detected in route from CH {ch_id}."
                    )
                    break

                visited.add(next_hop)
                route.append(next_hop)
                current = next_hop

            if current == bs_id:
                routes[ch_id] = route

        # Every CH has one outgoing parent link.
        if not errors:
            for ch_id in selected_ch_ids:
                parent = parent_map[ch_id]
                edge_data = edge_lookup[frozenset((ch_id, parent))]
                total_distance += float(edge_data.get("weight", 0.0))

        valid = len(errors) == 0 and len(routes) == len(selected_ch_ids)

        return {
            "valid": valid,
            "is_valid": valid,
            "errors": errors,
            "routes": routes,
            "total_distance": total_distance,
        }


class RoutingAlgorithm:
    """Common interface for global routing algorithms."""

    algorithm_name = "Base Routing Algorithm"

    def find_routes(self, graph, selected_ch_ids, bs_id="BS"):
        raise NotImplementedError(
            "Every routing algorithm must implement find_routes()."
        )

    def solve(self, graph, selected_ch_ids, bs_id="BS"):
        parent_map = self.find_routes(
            graph=graph,
            selected_ch_ids=selected_ch_ids,
            bs_id=bs_id,
        )

        validation = RoutingResultValidator.validate_parent_map(
            graph=graph,
            selected_ch_ids=selected_ch_ids,
            parent_map=parent_map,
            bs_id=bs_id,
        )

        if not validation["valid"]:
            raise ValueError(
                f"{self.algorithm_name} produced an invalid routing solution: "
                + "; ".join(validation["errors"])
            )

        return {
            "algorithm": self.algorithm_name,
            "parent_map": parent_map,
            "validation": validation,
        }

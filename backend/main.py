from pathlib import Path
import json
import math
from simulation.simulation_engine import WSNSimulationEngine
from simulation.multi_algorithm_runner import MultiAlgorithmSimulationRunner
from fastapi import Query

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from simulation.network import generate_network
from simulation.algorithms.ann_ch_selection import ANNClusterHeadSelector
from simulation.clustering import ClusterManager


app = FastAPI(
    title="WSN Routing Optimization API",
    description="Backend API for Wireless Sensor Network simulation.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "input" / "simulation_config.json"


def load_config():
    if not CONFIG_PATH.exists():
        raise FileNotFoundError("simulation_config.json not found")

    with open(CONFIG_PATH, "r", encoding="utf-8") as file:
        return json.load(file)


def get_communication_range(config):
    communication_config = config.get("communication", {})

    candidate_ranges = communication_config.get(
        "candidate_ranges_m", [60]
    )

    configured_range = communication_config.get(
        "communication_range_m"
    )

    if configured_range is not None:
        return float(configured_range), "configured"

    if not candidate_ranges:
        raise ValueError("No communication range candidates found.")

    return float(candidate_ranges[0]), "preview_candidate"


def serialize_nodes(raw_nodes):
    return [
        {
            "id": int(node["id"]),
            "x": float(node["x"]),
            "y": float(node["y"]),
            "alive": bool(node.get("alive", True)),
            "is_cluster_head": bool(
                node.get("is_cluster_head", False)
            ),
            "residual_energy": float(
                node.get("residual_energy", 0)
            ),
            "cluster_id": node.get("cluster_id"),
        }
        for node in raw_nodes
    ]


def build_physical_links(nodes, base_station, communication_range):
    links = []

    for index, node_a in enumerate(nodes):
        for node_b in nodes[index + 1:]:
            distance = math.hypot(
                node_a["x"] - node_b["x"],
                node_a["y"] - node_b["y"],
            )

            if distance <= communication_range + 1e-9:
                links.append({
                    "source": node_a["id"],
                    "target": node_b["id"],
                    "distance": round(distance, 3),
                    "type": "sensor",
                })

        bs_distance = math.hypot(
            node_a["x"] - base_station["x"],
            node_a["y"] - base_station["y"],
        )

        if bs_distance <= communication_range + 1e-9:
            links.append({
                "source": node_a["id"],
                "target": "BS",
                "distance": round(bs_distance, 3),
                "type": "base_station",
            })

    return links


@app.get("/")
def home():
    return {
        "message": "WSN Routing Optimization API",
        "status": "running",
        "version": "1.0.0",
    }


@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "message": "WSN backend is running successfully.",
        "project": "Wireless Sensor Network",
    }


@app.get("/api/config")
def get_configuration():
    try:
        return {
            "status": "success",
            "configuration": load_config(),
        }
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=500,
            detail="Invalid JSON in simulation_config.json",
        )


@app.get("/api/network/deployment")
def get_network_deployment():
    try:
        config = load_config()
        communication_range, range_mode = get_communication_range(config)

        network = generate_network(config, communication_range)

        nodes = serialize_nodes(network["nodes"])

        base_station_data = network["base_station"]
        base_station = {
            "x": float(base_station_data["x"]),
            "y": float(base_station_data["y"]),
        }

        links = build_physical_links(
            nodes,
            base_station,
            communication_range,
        )

        return {
            "status": "success",
            "network": {
                "num_nodes": len(nodes),
                "area_width": config["network"]["area_width"],
                "area_height": config["network"]["area_height"],
                "communication_range_m": communication_range,
                "range_mode": range_mode,
                "base_station": base_station,
                "nodes": nodes,
                "links": links,
                "total_links": len(links),
            },
        }

    except (KeyError, TypeError, ValueError) as error:
        raise HTTPException(
            status_code=500,
            detail=f"Network generation error: {error}",
        )
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected deployment error: {error}",
        )


@app.get("/api/network/clustered-deployment")
def get_clustered_network_deployment():
    try:
        config = load_config()
        communication_range, range_mode = get_communication_range(config)

        # Generate a fresh network deployment.
        network = generate_network(config, communication_range)

        # ANN is the only cluster-head selection algorithm.
        ann_selector = ANNClusterHeadSelector(
            num_cluster_heads=config["simulation"].get(
                "num_cluster_heads", 10
            ),
            random_seed=42,
            communication_range=communication_range,
            initial_energy=config["network"]["initial_energy_j"],
        )

        ann_training_result = ann_selector.train()
        ann_result = ann_selector.select_cluster_heads(
            nodes=network["nodes"],
            base_station=network["base_station"],
        )
        selected_ch_ids = ann_result["selected_ch_ids"]

        # Form clusters around the ANN-selected cluster heads.
        cluster_manager = ClusterManager(communication_range)
        cluster_result = cluster_manager.form_clusters(
            network,
            selected_ch_ids,
        )

        nodes = serialize_nodes(network["nodes"])

        base_station_data = network["base_station"]
        base_station = {
            "x": float(base_station_data["x"]),
            "y": float(base_station_data["y"]),
        }

        physical_links = build_physical_links(
            nodes,
            base_station,
            communication_range,
        )

        visualization_links = []
        node_map = {node["id"]: node for node in nodes}

        # Normal-node to cluster-head visualization links.
        for ch_id, member_ids in cluster_result["clusters"].items():
            if ch_id not in node_map:
                continue

            ch = node_map[ch_id]

            for member_id in member_ids:
                if member_id == ch_id or member_id not in node_map:
                    continue

                member = node_map[member_id]
                distance = math.hypot(
                    member["x"] - ch["x"],
                    member["y"] - ch["y"],
                )

                visualization_links.append({
                    "source": member_id,
                    "target": ch_id,
                    "distance": round(distance, 3),
                    "type": "cluster",
                })

        # Communication links between selected cluster heads.
        for index, ch_id_a in enumerate(selected_ch_ids):
            if ch_id_a not in node_map:
                continue

            ch_a = node_map[ch_id_a]

            for ch_id_b in selected_ch_ids[index + 1:]:
                if ch_id_b not in node_map:
                    continue

                ch_b = node_map[ch_id_b]
                distance = math.hypot(
                    ch_a["x"] - ch_b["x"],
                    ch_a["y"] - ch_b["y"],
                )

                if distance <= communication_range + 1e-9:
                    visualization_links.append({
                        "source": ch_id_a,
                        "target": ch_id_b,
                        "distance": round(distance, 3),
                        "type": "ch_connectivity",
                    })

        # Direct communication links from cluster heads to the BS.
        for ch_id in selected_ch_ids:
            if ch_id not in node_map:
                continue

            ch = node_map[ch_id]
            distance = math.hypot(
                ch["x"] - base_station["x"],
                ch["y"] - base_station["y"],
            )

            if distance <= communication_range + 1e-9:
                visualization_links.append({
                    "source": ch_id,
                    "target": "BS",
                    "distance": round(distance, 3),
                    "type": "base_station",
                })

        return {
            "status": "success",
            "network": {
                "num_nodes": len(nodes),
                "area_width": config["network"]["area_width"],
                "area_height": config["network"]["area_height"],
                "communication_range_m": communication_range,
                "range_mode": range_mode,
                "base_station": base_station,
                "nodes": nodes,
                "links": visualization_links,
                "total_links": len(visualization_links),
                "physical_links": physical_links,
                "total_physical_links": len(physical_links),
                "selected_ch_ids": selected_ch_ids,
                "clusters": cluster_result["clusters"],
                "cluster_metrics": {
                    "total_alive_nodes": cluster_result["total_alive_nodes"],
                    "total_assigned_nodes": cluster_result["total_assigned_nodes"],
                    "unassigned_node_ids": cluster_result["unassigned_node_ids"],
                    "coverage": cluster_result["coverage"],
                },
                "cluster_head_algorithm": "ANN",
                "ann": {
                    "scores": ann_result["scores"],
                    "training": ann_training_result,
                },
            },
        }

    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except (KeyError, TypeError, ValueError) as error:
        raise HTTPException(
            status_code=500,
            detail=f"Clustered network generation error: {error}",
        )
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected clustered deployment error: {error}",
        )


@app.post("/api/simulation/run")
def run_simulation(
    rounds: int = Query(default=1, ge=1, le=200)
):
    try:
        config = load_config()

        engine = WSNSimulationEngine(config)

        result = engine.run(number_of_rounds=rounds)

        # Add network information required by React.
        base_station = engine.network["base_station"]

        for snapshot in result["history"]:
            snapshot["base_station"] = {
                "x": float(base_station["x"]),
                "y": float(base_station["y"]),
            }

            snapshot["communication_range_m"] = (
                engine.communication_range
            )

            snapshot["area_width"] = config["network"]["area_width"]
            snapshot["area_height"] = config["network"]["area_height"]

            snapshot["links"] = []

            node_map = {
                node["id"]: node
                for node in snapshot["nodes"]
            }

            # Normal sensor-to-CH connections.
            for ch_id, members in snapshot["clusters"].items():
                for member_id in members:
                    if member_id == ch_id:
                        continue

                    a = node_map[member_id]
                    b = node_map[ch_id]

                    snapshot["links"].append({
                        "source": member_id,
                        "target": ch_id,
                        "type": "cluster",
                        "distance": round(
                            math.hypot(
                                a["x"] - b["x"],
                                a["y"] - b["y"]
                            ), 3
                        ),
                    })

            # Actual multi-hop routing connections.
            for child, parent in snapshot["parent_map"].items():
                a = node_map[child]

                b = (
                    snapshot["base_station"]
                    if parent == "BS"
                    else node_map[parent]
                )

                snapshot["links"].append({
                    "source": child,
                    "target": parent,
                    "type": "route",
                    "distance": round(
                        math.hypot(
                            a["x"] - b["x"],
                            a["y"] - b["y"]
                        ), 3
                    ),
                })

        return result

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Simulation execution failed: {error}"
        )
    
@app.post("/api/simulation/run-all")
def run_all_algorithms(
    rounds: int = Query(default=1, ge=1, le=200)
):
    try:
        config = load_config()

        # Run all six routing algorithms using ANN-selected CHs.
        runner = MultiAlgorithmSimulationRunner(config)
        result = runner.run(number_of_rounds=rounds)

        # Add visualization information to every algorithm's history.
        for algorithm_key, algorithm_result in result["results"].items():

            history = algorithm_result.get("history", [])

            for snapshot in history:
                base_station = algorithm_result.get(
                    "base_station"
                )

                if base_station is None:
                    # The engine's network contains the BS coordinates.
                    # Use the common initial deployment from the runner.
                    base_station = runner.initial_network[
                        "base_station"
                    ]

                bs = {
                    "x": float(base_station["x"]),
                    "y": float(base_station["y"]),
                }

                snapshot["base_station"] = bs
                snapshot["communication_range_m"] = (
                    runner.communication_range
                )
                snapshot["area_width"] = config["network"][
                    "area_width"
                ]
                snapshot["area_height"] = config["network"][
                    "area_height"
                ]

                snapshot["links"] = []

                node_map = {
                    node["id"]: node
                    for node in snapshot["nodes"]
                }

                # Draw normal-node to cluster-head connections.
                for ch_id, members in snapshot["clusters"].items():
                    for member_id in members:
                        if member_id == ch_id:
                            continue

                        if member_id not in node_map or ch_id not in node_map:
                            continue

                        a = node_map[member_id]
                        b = node_map[ch_id]

                        snapshot["links"].append({
                            "source": member_id,
                            "target": ch_id,
                            "type": "cluster",
                            "distance": round(
                                math.hypot(
                                    a["x"] - b["x"],
                                    a["y"] - b["y"]
                                ), 3
                            ),
                        })

                # Draw actual multi-hop routing connections.
                for child, parent in snapshot["parent_map"].items():
                    if child not in node_map:
                        continue

                    a = node_map[child]

                    if parent == "BS":
                        b = bs
                    else:
                        if parent not in node_map:
                            continue
                        b = node_map[parent]

                    snapshot["links"].append({
                        "source": child,
                        "target": parent,
                        "type": "route",
                        "distance": round(
                            math.hypot(
                                a["x"] - b["x"],
                                a["y"] - b["y"]
                            ), 3
                        ),
                    })

        return result

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Six-algorithm simulation failed: {error}"
        )

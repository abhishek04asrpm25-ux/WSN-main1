import json
from pathlib import Path

from simulation.multi_algorithm_runner import MultiAlgorithmSimulationRunner

ROOT = Path(__file__).resolve().parents[1]


def test_six_algorithms_produce_dynamic_50_round_histories():
    with open(ROOT / "input" / "simulation_config.json", encoding="utf-8") as file:
        config = json.load(file)

    result = MultiAlgorithmSimulationRunner(config).run(number_of_rounds=50)

    assert result["cluster_head_algorithm"] == "ANN"
    assert len(result["results"]) == 6

    for algorithm, algorithm_result in result["results"].items():
        history = algorithm_result["history"]
        assert len(history) == 50, algorithm
        assert history[0]["metrics"]["total_residual_energy"] > history[-1]["metrics"]["total_residual_energy"]
        assert any(
            history[index]["selected_ch_ids"] != history[index - 1]["selected_ch_ids"]
            for index in range(1, len(history))
        ), f"ANN cluster heads did not update for {algorithm}"
        assert any(
            history[index]["parent_map"] != history[index - 1]["parent_map"]
            for index in range(1, len(history))
        ), f"Routing paths did not update for {algorithm}"
        assert history[-1]["metrics"]["cumulative_successful_packets"] > 0
        assert history[-1]["metrics"]["cumulative_packet_delivery_ratio"] >= 0

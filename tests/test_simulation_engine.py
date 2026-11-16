
import json

from simulation.simulation_engine import WSNSimulationEngine


def main():
    with open(
        "input/simulation_config.json",
        "r",
        encoding="utf-8"
    ) as file:
        config = json.load(file)

    engine = WSNSimulationEngine(config)

    result = engine.run(number_of_rounds=1)

    print("\n========== SIMULATION TEST ==========")

    print("Status:", result["status"])
    print("Algorithm:", result["algorithm"])
    print("Completed rounds:", result["total_rounds_completed"])

    first_round = result["history"][0]

    print("\nSelected CHs:")
    print(first_round["selected_ch_ids"])

    print("\nMulti-hop routes:")

    for ch_id, route in first_round["routes"].items():
        print(f"CH {ch_id}: {' -> '.join(map(str, route))}")

    print("\nMetrics:")

    for key, value in first_round["metrics"].items():
        print(f"{key}: {value}")

    print("\nTEST COMPLETED")


if __name__ == "__main__":
    main()

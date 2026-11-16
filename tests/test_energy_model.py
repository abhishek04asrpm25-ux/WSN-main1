
import json

from simulation.energy_model import EnergyModel


def load_config():

    with open(
        "input/simulation_config.json",
        "r"
    ) as file:

        return json.load(file)


def main():

    config = load_config()

    energy = EnergyModel(config)

    energy.print_parameters()

    packet_size = 4000

    print("========== ENERGY CALCULATIONS ==========")

    # Test 1: Transmission over 10 metres
    tx_energy = energy.transmission_energy(
        distance=10,
        packet_size_bits=packet_size
    )

    print(
        "TX energy at 10 m:",
        f"{tx_energy:.10f} J"
    )

    # Test 2: Transmission over 100 metres
    tx_energy_long = energy.transmission_energy(
        distance=100,
        packet_size_bits=packet_size
    )

    print(
        "TX energy at 100 m:",
        f"{tx_energy_long:.10f} J"
    )

    # Test 3: Reception energy
    rx_energy = energy.reception_energy(
        packet_size
    )

    print(
        "RX energy:",
        f"{rx_energy:.10f} J"
    )

    # Test 4: Aggregation energy
    aggregation = energy.aggregation_energy(
        packet_size
    )

    print(
        "Aggregation energy:",
        f"{aggregation:.10f} J"
    )

    print("==========================================")

    # Test 5: Node energy consumption
    node = {
        "id": 1,
        "residual_energy": 0.5,
        "alive": True
    }

    result = energy.transmit(
        node,
        distance=10,
        packet_size_bits=packet_size
    )

    print("\n========== NODE ENERGY UPDATE ==========")

    print("Transmission successful:", result["success"])

    print(
        "Energy consumed:",
        f'{result["energy_consumed"]:.10f} J'
    )

    print(
        "Residual energy:",
        f'{node["residual_energy"]:.10f} J'
    )

    print("Node alive:", node["alive"])

    print("========================================")


if __name__ == "__main__":
    main()

from simulation.visualization import plot_network
import json

from simulation.network import (
    generate_network,
    print_network_summary
)

from simulation.connectivity_test import (
    analyze_connectivity,
    test_communication_ranges
)


def load_configuration():

    with open(
        "input/simulation_config.json",
        "r"
    ) as file:

        config = json.load(file)

    return config


def main():

    print("\n")
    print("==========================================")
    print(" WSN ROUTING OPTIMIZATION PROJECT")
    print(" PHASE 1: NETWORK DEPLOYMENT")
    print("==========================================")

    # Load configuration
    config = load_configuration()

    # Test candidate communication ranges
    results = test_communication_ranges(config)

    # Generate the network using the first
    # candidate range for initial inspection
    selected_range = config[
        "communication"
    ]["candidate_ranges_m"][0]

    network = generate_network(
        config,
        communication_range=selected_range
    )

    # Display network information
    print_network_summary(network)

    # Analyze connectivity
    metrics = analyze_connectivity(network)

    print("========== CONNECTIVITY DETAILS ==========")

    for key, value in metrics.items():

        print(f"{key}: {value}")

    print("==========================================")

    print("\nPhase 1 initial deployment completed.")
# Display network visualization
    plot_network(network)

if __name__ == "__main__":
    main()
    
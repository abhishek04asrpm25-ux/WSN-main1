
from importlib import import_module


def plot_network(network):

    try:
        plt = import_module("matplotlib.pyplot")
    except ModuleNotFoundError as exc:
        if exc.name == "matplotlib":
            raise RuntimeError(
                "Plotting requires matplotlib. Install it with 'python -m pip install matplotlib'."
            ) from exc
        raise

    nodes = network["nodes"]
    bs = network["base_station"]
    graph = network["graph"]

    plt.figure(figsize=(10, 8))

    # Draw sensor nodes
    x = [node["x"] for node in nodes]
    y = [node["y"] for node in nodes]

    plt.scatter(
        x,
        y,
        s=45,
        label="Sensor Nodes"
    )

    # Draw sensor-to-sensor communication links
    for u, v in graph.edges():

        if u != "BS" and v != "BS":

            node1 = nodes[u]
            node2 = nodes[v]

            plt.plot(
                [node1["x"], node2["x"]],
                [node1["y"], node2["y"]],
                alpha=0.18,
                linewidth=0.7
            )

    # Draw Base Station
    plt.scatter(
        bs["x"],
        bs["y"],
        color="red",
        marker="*",
        s=300,
        label="Base Station"
    )

    # Draw direct links to Base Station
    for neighbor in graph.neighbors("BS"):

        node = nodes[neighbor]

        plt.plot(
            [node["x"], bs["x"]],
            [node["y"], bs["y"]],
            linestyle="--",
            alpha=0.6,
            linewidth=1
        )

    # Deployment area
    plt.xlim(0, network["area_width"])
    plt.ylim(0, bs["y"] + 10)

    plt.xlabel("X coordinate (metres)")
    plt.ylabel("Y coordinate (metres)")

    plt.title(
        "Wireless Sensor Network Deployment"
    )

    plt.legend()
    plt.grid(alpha=0.2)
    plt.tight_layout()

    plt.show()


import { useEffect, useState } from "react";

const API_URL = "http://127.0.0.1:8000/api/network/deployment";

export default function NetworkTopology({ simulationSnapshot }) {
  const [network, setNetwork] = useState(null);
  const [status, setStatus] = useState("Loading network...");
  const [error, setError] = useState("");
  const [retryCount, setRetryCount] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    let cancelled = false;

    async function loadNetwork() {
      setNetwork(null);
      setError("");
      setStatus("Connecting to Python backend...");

      try {
        const response = await fetch(API_URL, {
          method: "GET",
          headers: { Accept: "application/json" },
          signal: controller.signal,
        });

        const result = await response.json();

        if (!response.ok) {
          throw new Error(
            result.detail || "Network deployment request failed."
          );
        }

        if (
          result.status !== "success" ||
          !result.network ||
          !Array.isArray(result.network.nodes) ||
          !result.network.base_station ||
          !Array.isArray(result.network.links)
        ) {
          throw new Error("Unexpected network deployment response.");
        }

        if (!cancelled) {
          setNetwork(result.network);
          setStatus("Live Python deployment");
          setError("");
        }
      } catch (err) {
        if (!cancelled) {
          if (err.name === "AbortError") return;

          setError(err.message || "Could not connect to backend.");
          setStatus("Connection failed");
        }
      }
    }

    loadNetwork();

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [retryCount]);

  const displayNetwork = simulationSnapshot && network
    ? {
        ...network,
        nodes: simulationSnapshot.nodes,
        links: simulationSnapshot.links || [],
        base_station:
          simulationSnapshot.base_station || network.base_station,
        communication_range_m:
          simulationSnapshot.communication_range_m ||
          network.communication_range_m,
      }
    : network;

  const toX = (x) => 30 + x * 6.4;
  const toY = (y) => 430 - y * 2.2;

  if (error) {
    return (
      <div className="topology-card">
        <h2>Network Topology</h2>
        <p>{status}</p>

        <p style={{ color: "#f87171", lineHeight: 1.6 }}>
          {error}
        </p>

        <button onClick={() => setRetryCount((count) => count + 1)}>
          Retry connection
        </button>
      </div>
    );
  }

  if (!displayNetwork) {
    return (
      <div className="topology-card">
        <h2>Network Topology</h2>
        <p>{status}</p>

        <p style={{ color: "#91a7c8", fontSize: "12px" }}>
          Waiting for the network deployment from FastAPI...
        </p>
      </div>
    );
  }

  const nodeMap = new Map(
    displayNetwork.nodes.map((node) => [node.id, node])
  );

  const hasSimulation = Boolean(simulationSnapshot);

  return (
    <div className="topology-card">
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: "12px",
          flexWrap: "wrap",
          marginBottom: "12px",
        }}
      >
        <div>
          <h2>Network Topology</h2>

          <p>
            {hasSimulation
              ? "Actual simulation network"
              : status}{" "}
            · {displayNetwork.nodes.length} sensor nodes
          </p>
        </div>

        <span
          style={{
            background: "rgba(34,197,94,0.12)",
            color: "#4ade80",
            borderRadius: "20px",
            padding: "7px 12px",
            fontSize: "12px",
          }}
        >
          {displayNetwork.communication_range_m} m range
        </span>
      </div>

      <div
        style={{
          width: "100%",
          overflow: "hidden",
          border: "1px solid #263650",
          borderRadius: "12px",
          background: "#0c172a",
        }}
      >
        <svg
          viewBox="0 0 700 480"
          role="img"
          aria-label="Wireless sensor network topology"
          style={{
            display: "block",
            width: "100%",
            height: "auto",
          }}
        >
          <defs>
            <pattern
              id="network-grid"
              width="32"
              height="32"
              patternUnits="userSpaceOnUse"
            >
              <path
                d="M 32 0 L 0 0 0 32"
                fill="none"
                stroke="#263650"
                strokeWidth="1"
              />
            </pattern>
          </defs>

          <rect
            x="0"
            y="0"
            width="700"
            height="480"
            fill="url(#network-grid)"
          />

          <rect
            x="30"
            y={toY(100)}
            width="640"
            height={toY(0) - toY(100)}
            fill="none"
            stroke="#7185a5"
            strokeDasharray="5 5"
            strokeWidth="1.5"
          />

          <text
            x="40"
            y={toY(100) + 18}
            fill="#91a7c8"
            fontSize="11"
          >
            100 × 100 m SENSOR AREA
          </text>

          {/* Actual cluster and routing links */}
          {displayNetwork.links.map((link, index) => {
            const source = nodeMap.get(link.source);

            const target =
              link.target === "BS"
                ? displayNetwork.base_station
                : nodeMap.get(link.target);

            if (!source || !target) return null;

            let stroke = "#526d96";
            let width = 1;
            let opacity = 0.45;

            if (link.type === "route") {
              stroke = "#9b7aff";
              width = 2.2;
              opacity = 0.95;
            } else if (link.type === "cluster") {
              stroke = "#f3b64e";
              width = 1.4;
              opacity = 0.8;
            } else if (link.type === "base_station") {
              stroke = "#9b7aff";
              width = 1.8;
              opacity = 0.8;
            }

            return (
              <line
                key={`link-${index}`}
                x1={toX(source.x)}
                y1={toY(source.y)}
                x2={toX(target.x)}
                y2={toY(target.y)}
                stroke={stroke}
                strokeWidth={width}
                opacity={opacity}
              >
                <title>
                  {`Link: ${link.source} to ${link.target}, ${link.distance} m`}
                </title>
              </line>
            );
          })}

          {/* Sensor nodes */}
          {displayNetwork.nodes.map((node) => (
            <g key={node.id}>
              <circle
                cx={toX(node.x)}
                cy={toY(node.y)}
                r={node.is_cluster_head ? 7 : 4.5}
                fill={
                  !node.alive
                    ? "#64748b"
                    : node.is_cluster_head
                      ? "#f3b64e"
                      : "#25b9dc"
                }
                stroke={
                  node.is_cluster_head ? "#ffe0a0" : "#a5f3fc"
                }
                strokeWidth="1"
              >
                <title>
                  {`Node ${node.id} | Position: (${Number(node.x).toFixed(2)}, ${Number(node.y).toFixed(2)}) | Energy: ${Number(node.residual_energy).toFixed(3)} J`}
                </title>
              </circle>
            </g>
          ))}

          {/* Base station */}
          <rect
            x={toX(displayNetwork.base_station.x) - 9}
            y={toY(displayNetwork.base_station.y) - 9}
            width="18"
            height="18"
            rx="4"
            fill="#9b7aff"
            stroke="#d2c5ff"
            strokeWidth="2"
          />

          <text
            x={toX(displayNetwork.base_station.x)}
            y={toY(displayNetwork.base_station.y) - 17}
            fill="#c4b5fd"
            fontSize="12"
            textAnchor="middle"
          >
            BASE STATION
          </text>
        </svg>
      </div>

      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: "18px",
          marginTop: "14px",
          color: "#aabbd4",
          fontSize: "12px",
        }}
      >
        <span>🔵 Sensor node</span>
        <span>🟠 ANN Cluster Head</span>
        <span>🟣 Base station</span>
        <span>🟡 Cluster link</span>
        <span>🟣 Multi-hop route</span>
      </div>

      <p
        style={{
          color: "#91a7c8",
          fontSize: "12px",
          marginTop: "12px",
        }}
      >
        {displayNetwork.nodes.length} nodes ·{" "}
        {displayNetwork.links.length} displayed links ·{" "}
        {hasSimulation
          ? "Simulation data"
          : "Initial physical deployment"}
      </p>
    </div>
  );
}

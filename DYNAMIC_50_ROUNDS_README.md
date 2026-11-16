# Dynamic 50-round WSN simulation

## What changed

- ANN cluster-head selection now receives normalized live network features (residual energy, distance, neighbor distance, degree, neighbor energy and LQI).
- ANN cluster-head selection is connectivity-constrained: the selected CH set starts from nodes that can reach the base station and expands through reachable CH candidates. This prevents selecting a disconnected CH set that cannot route to the BS.
- Each routing algorithm still gets an independent copy of the same initial deployment and runs its own 50-round energy history.
- Each round stores fresh CH IDs, cluster membership, multi-hop parent map/routes, per-node energy/alive state, topology links and packet statistics.
- Packet metrics now include per-round and cumulative successful/lost packets and cumulative delivery ratio.
- React defaults to 50 rounds and includes Play, Pause, Previous, Next, Restart and a round slider. The map, CH list, cluster assignments, paths and metrics are read from the selected real backend snapshot.

## Run on Windows PowerShell

Open two PowerShell windows.

### 1. Backend

From the extracted `WSN-main` folder:

```powershell
python -m uvicorn backend.main:app --reload
```

### 2. Frontend

```powershell
cd .\frontend
npm install
npm run dev
```

Open the Vite URL printed in the terminal (normally `http://localhost:5173`). Click **Run All Algorithms**, keep the round count at 50, then use the round playback controls. Change the selected routing algorithm to inspect its independent history.

## Tests

From the extracted `WSN-main` folder:

```powershell
python -m pytest -q tests
```

The dynamic 50-round test verifies that all six algorithms complete 50 snapshots, residual energy decreases, ANN CH IDs and routing parent maps change, and cumulative packet statistics are populated.

## Interpretation note

With the supplied radio-energy parameters and 0.5 J initial energy per node, the verified 50-round run does not kill any nodes (100 alive, 0 dead at round 50). The alive/dead counts are recalculated and stored every round; this run does not artificially kill nodes just to force a changing count. A longer simulation or a separately justified energy model is needed to observe node deaths.

The ANN model in this research prototype is trained on heuristic-generated synthetic labels. Treat it as a prototype selector, not as evidence of validated real-world ANN performance.

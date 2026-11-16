# WSN Routing Optimization — Updated Build

## Included in this update
- ANN cluster-head selection is retained and recalculated every round from current node state.
- Six routing strategies are run on independent copies of the same seeded deployment: Dijkstra, ILP, GA, PSO, ACO, ANN.
- ANN routing now uses the five specification-aligned input features: next-hop residual energy, CH-to-neighbor distance, neighbor-to-BS shortest-path distance, estimated transmission energy, and LQI.
- ANN routing network uses dense 64/32/16 hidden layers and a sigmoid probability output trained with binary cross-entropy/log-loss.
- Routing candidates must make progress toward the BS; routes are checked for loops and missing next hops.
- Per-round metrics include energy, alive/dead nodes, packet delivery ratio, average hop count, estimated delay, routing computation time, round execution time, and FND/HND/LND milestones.
- Six-algorithm comparison includes energy gap and percentage energy reduction relative to Dijkstra.
- Frontend includes CSV export of round-level metrics, selected CHs and routes, plus ANN training transparency.
- Added a configurable PHY bit-rate assumption (250,000 bit/s) for estimated delay.

## Run
Backend (PowerShell, from WSN-main):
```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```
Frontend (a second PowerShell window):
```powershell
cd frontend
npm install
npm run dev
```
Open the Vite URL shown in the terminal (normally http://localhost:5173).

## Verification performed on this build
- Python compileall succeeded.
- Project test suite: 6 passed.
- Six algorithms completed a 50-round run in the local verification environment.
- Each algorithm produced 50 distinct ANN-selected CH sets across the 50 rounds.
- All six algorithms completed all 50 rounds; all 100 nodes remained alive under the current radio/traffic settings.

## Research limitations — do not overclaim
- ANN routing training samples currently use synthetic heuristic pseudo-labels, not optimal next-hop labels generated from Dijkstra/ILP. The UI explicitly discloses this. Reported ANN training accuracy is only accuracy against those pseudo-labels.
- The delay value is an estimate using the configured 250 kb/s PHY-rate assumption; it is not a measured packet-level delay.
- The comparison currently uses one fixed-seed topology replicate. It does not provide statistical mean/standard deviation across multiple independent seeds.
- FND/HND/LND remain blank until those death thresholds are actually reached. They are not artificially assigned.
- The PHY-rate assumption and routing objective weights should be stated in the project report and calibrated against the intended WSN hardware/model.

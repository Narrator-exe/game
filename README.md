# NPC Smallville Simulation Server

Installable **all-in-one NPC simulation software** with:

- Generative-agent style memory + observation + action loop
- Ollama integration for local/free LLM inference
- Real-time dashboard
- Smallville-compatible API surface (`/ping`, `/state`, `/agents`, `/locations`, `/objects`, `/react`)
- JavaScript + Java client libraries in `clients/`

> This implementation is inspired by and API-shaped from: https://github.com/nmatter1/smallville

## Built for typical Windows i5 laptops

The default configuration is tuned for mid-range laptops:

- Default model: `tinyllama:1.1b` (lighter than 7B/8B models)
- Slower tick cadence (`8s`) to reduce CPU usage
- Lower memory retention per agent (`48`) to reduce RAM pressure

## Option A: Windows (easy)

1. Install Docker Desktop (Windows).
2. Open PowerShell in this folder.
3. Run:

```powershell
.\run_all_in_one_windows.bat
```

Then open:

- Dashboard: `http://localhost:8000`

## Option B: macOS/Linux

```bash
./run_all_in_one.sh
```

Services started:

- Ollama: `http://localhost:11434`
- NPC server + dashboard: `http://localhost:8000`

## Option C: Install as software (pip)

```bash
pip install .
npc-sim
```

The `npc-sim` CLI is installed via `pyproject.toml` entry points.

## Tuning for weaker/stronger laptops

Set environment variables before startup:

- `OLLAMA_MODEL` (default: `tinyllama:1.1b`)
- `SIM_TICK_SECONDS` (default: `8`)
- `MAX_MEMORIES` (default: `48`)

Example (PowerShell):

```powershell
$env:OLLAMA_MODEL="tinyllama:1.1b"
$env:SIM_TICK_SECONDS="10"
$env:MAX_MEMORIES="32"
.\run_all_in_one_windows.bat
```

## API

### New API

- `GET /api/health`
- `GET /api/sim`
- `POST /api/sim`
- `POST /api/sim/tick`
- `GET /api/agents`
- `GET /api/agents/{id}`
- `GET /api/agents/{id}/memories`
- `POST /api/agents/{id}/ask`
- `WS /ws/events`

### Smallville-compatible API

- `GET /ping`
- `GET /state`
- `POST /state` (advances one tick)
- `POST /agents`
- `POST /locations`
- `POST /objects`
- `POST /react`

## JavaScript and Java clients

- JavaScript client: `clients/javascript/src/index.js`
- Java client: `clients/java/src/main/java/com/game/npc/NpcSimClient.java`

## Notes

- The system continues running if Ollama is unavailable by using a fallback decision policy.
- Dashboard assets are packaged inside the Python install under `backend/dashboard/` so `npc-sim` works after `pip install .`.

# Mini Agentic RAG IT Incident Investigator

Enterprise-style incident investigation command center with a React/Vite frontend and a planned FastAPI backend.

## Run the frontend

### Prerequisites

- Node.js 18 or newer
- npm

### Install and start

From PowerShell at the repository root:

```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm run dev
```

Open the URL Vite prints in the terminal (by default, <http://localhost:5173>). Stop the development server with `Ctrl+C`.

The `.env` copy is optional if you want to use the default API settings. To run the frontend without the backend, leave the API settings unchanged: the interface should still load, but backend-dependent data and actions will show as unavailable.

### Configure the backend URL

Edit `frontend/.env` before starting Vite:

```dotenv
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_API_HEALTH_PATH=/health
```

Restart Vite after changing environment variables. The health indicator shows **Connected** only when the configured health endpoint returns a successful response.

Other `VITE_API_*_PATH` settings in `frontend/.env.example` are optional. Set them only when the corresponding backend routes exist and return the expected data. You can also change the API base URL in the app's Settings page.

> **Backend integration status:** the checked-in backend route and schema files are currently empty. Incident submission is therefore not enabled, and dashboard, log, metric, MCP, RAG, and report data are not simulated. See [frontend/API_CONTRACT.md](frontend/API_CONTRACT.md) for the routes and frontend configuration details.

## Build and preview

From the `frontend` directory:

```powershell
npm run build
npm run preview
```

The production bundle is generated in `frontend/dist/`. The preview server prints the local URL to open.

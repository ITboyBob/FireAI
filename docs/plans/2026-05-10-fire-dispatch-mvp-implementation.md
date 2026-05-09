# Fire Dispatch MVP Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create a standalone MVP for the Fire Dispatch System with a FastAPI backend and a Vite+React frontend, focusing purely on verifying LLM capabilities (parsing and generation) using mock external resources.

**Architecture:** A new monorepo `fire-dispatch-mvp` alongside the current `fire` project. It contains a `backend` directory (FastAPI) and a `frontend` directory (Vite+React+Tailwind). The backend exposes a single POST endpoint that handles LLM extraction, mock data injection, and LLM generation. The frontend consumes this and displays the flow with premium styling.

**Tech Stack:** Python, FastAPI, pytest, Vite, React, TypeScript, TailwindCSS.

---

### Task 1: Project Scaffolding

**Files:**
- Create: `/Users/itboybob/Project/fire-dispatch-mvp/backend/main.py`
- Create: `/Users/itboybob/Project/fire-dispatch-mvp/backend/tests/test_api.py`

**Step 1: Create Monorepo and Backend scaffold**

```bash
mkdir -p /Users/itboybob/Project/fire-dispatch-mvp/backend
mkdir -p /Users/itboybob/Project/fire-dispatch-mvp/frontend
cd /Users/itboybob/Project/fire-dispatch-mvp
git init
```

**Step 2: Initialize Backend with failing test**

Create `/Users/itboybob/Project/fire-dispatch-mvp/backend/tests/test_api.py`:
```python
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

**Step 3: Run test to verify it fails**

Run: `cd /Users/itboybob/Project/fire-dispatch-mvp/backend && pytest tests/test_api.py`
Expected: FAIL (main module not found)

**Step 4: Write minimal implementation**

Create `/Users/itboybob/Project/fire-dispatch-mvp/backend/main.py`:
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Fire Dispatch MVP API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_check():
    return {"status": "ok"}
```

**Step 5: Run test to verify it passes**

Run: `cd /Users/itboybob/Project/fire-dispatch-mvp/backend && pytest tests/test_api.py`
Expected: PASS

**Step 6: Commit**

```bash
cd /Users/itboybob/Project/fire-dispatch-mvp
git add backend/
git commit -m "chore: initialize backend scaffold with FastAPI and pytest"
```

---

### Task 2: Backend Mock Context & Schemas

**Files:**
- Create: `/Users/itboybob/Project/fire-dispatch-mvp/backend/schemas.py`
- Create: `/Users/itboybob/Project/fire-dispatch-mvp/backend/mock_data.py`

**Step 1: Define Schemas**

Create `/Users/itboybob/Project/fire-dispatch-mvp/backend/schemas.py`:
```python
from pydantic import BaseModel
from typing import List

class SimulationRequest(BaseModel):
    alarm_text: str

class ParsedIncident(BaseModel):
    disaster_type: str
    location: str
    phenomenon: str
    casualty_risk: str
    missing_info: List[str]
    follow_up_questions: List[str]

class MockContext(BaseModel):
    closest_station: str
    available_vehicles: List[str]
    rule_applied: str

class SimulationResponse(BaseModel):
    parsed_incident: ParsedIncident
    mock_context_applied: MockContext
    command_draft: str
```

**Step 2: Create Mock Data Provider**

Create `/Users/itboybob/Project/fire-dispatch-mvp/backend/mock_data.py`:
```python
def get_mock_context() -> dict:
    return {
        "closest_station": "A消防救援站",
        "available_vehicles": ["水罐车", "抢险救援车"],
        "rule_applied": "高层建筑火灾预案"
    }
```

**Step 3: Commit**

```bash
cd /Users/itboybob/Project/fire-dispatch-mvp
git add backend/schemas.py backend/mock_data.py
git commit -m "feat: define schemas and static mock context for MVP"
```

---

### Task 3: Backend LLM Integration (Simulate Endpoint)

**Files:**
- Modify: `/Users/itboybob/Project/fire-dispatch-mvp/backend/main.py`
- Create: `/Users/itboybob/Project/fire-dispatch-mvp/backend/tests/test_simulation.py`
- Create: `/Users/itboybob/Project/fire-dispatch-mvp/backend/llm_service.py`

*(Note: In a real TDD environment, we mock the LLM call. For this MVP plan, we will structure the endpoint to accept the request, call a dummy LLM service, and return the response. Actual LLM implementation details depends on the chosen SDK/model.)*

**Step 1: Write failing test**

Create `/Users/itboybob/Project/fire-dispatch-mvp/backend/tests/test_simulation.py`:
```python
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_simulate_dispatch():
    response = client.post("/api/v1/dispatch/simulate", json={"alarm_text": "3号楼着火了"})
    assert response.status_code == 200
    data = response.json()
    assert "parsed_incident" in data
    assert "mock_context_applied" in data
    assert "command_draft" in data
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/itboybob/Project/fire-dispatch-mvp/backend && pytest tests/test_simulation.py`
Expected: FAIL (404 Not Found)

**Step 3: Write minimal implementation**

Create `/Users/itboybob/Project/fire-dispatch-mvp/backend/llm_service.py`:
```python
from schemas import ParsedIncident

def call_llm_parse(text: str) -> ParsedIncident:
    # TODO: Replace with real LLM prompt call
    return ParsedIncident(
        disaster_type="火灾",
        location="3号楼",
        phenomenon="着火",
        casualty_risk="未知",
        missing_info=["具体楼层", "有无被困人员"],
        follow_up_questions=["请问在几层？"]
    )

def call_llm_generate(incident: ParsedIncident, context: dict) -> str:
    # TODO: Replace with real LLM generation
    return f"【指令草稿】前往{incident.location}处置{incident.disaster_type}，出动{','.join(context['available_vehicles'])}"
```

Update `main.py` to include the route:
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from schemas import SimulationRequest, SimulationResponse, MockContext
from mock_data import get_mock_context
from llm_service import call_llm_parse, call_llm_generate

app = FastAPI(title="Fire Dispatch MVP API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/api/v1/dispatch/simulate", response_model=SimulationResponse)
def simulate_dispatch(request: SimulationRequest):
    parsed = call_llm_parse(request.alarm_text)
    mock_ctx = get_mock_context()
    draft = call_llm_generate(parsed, mock_ctx)
    return SimulationResponse(
        parsed_incident=parsed,
        mock_context_applied=MockContext(**mock_ctx),
        command_draft=draft
    )
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/itboybob/Project/fire-dispatch-mvp/backend && pytest tests/test_simulation.py`
Expected: PASS

**Step 5: Commit**

```bash
cd /Users/itboybob/Project/fire-dispatch-mvp
git add backend/
git commit -m "feat: implement simulate endpoint with LLM service stubs"
```

---

### Task 4: Frontend Vite + React Scaffolding

**Files:**
- Create: Frontend via Vite CLI

**Step 1: Scaffold Vite Project**

```bash
cd /Users/itboybob/Project/fire-dispatch-mvp
npx -y create-vite@latest frontend --template react-ts
cd frontend
npm install
npm install tailwindcss postcss autoprefixer
npx tailwindcss init -p
```

**Step 2: Configure Tailwind**

Modify `/Users/itboybob/Project/fire-dispatch-mvp/frontend/tailwind.config.js`:
```javascript
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}
```

Modify `/Users/itboybob/Project/fire-dispatch-mvp/frontend/src/index.css`:
```css
@tailwind base;
@tailwind components;
@tailwind utilities;

body {
  @apply bg-slate-900 text-slate-100; /* Premium dark mode base */
}
```

**Step 3: Commit**

```bash
cd /Users/itboybob/Project/fire-dispatch-mvp
git add frontend/
git commit -m "chore: initialize frontend with Vite, React, and TailwindCSS"
```

---

### Task 5: Frontend Dashboard UI Implementation

**Files:**
- Modify: `/Users/itboybob/Project/fire-dispatch-mvp/frontend/src/App.tsx`

**Step 1: Implement basic layout and state**

*(Note: Real implementation will use components. For the plan, we put it in App.tsx for simplicity to verify connection)*

Modify `App.tsx`:
```tsx
import { useState } from 'react'

function App() {
  const [alarmText, setAlarmText] = useState('')
  const [result, setResult] = useState<any>(null)
  const [loading, setLoading] = useState(false)

  const handleSimulate = async () => {
    setLoading(true)
    try {
      const res = await fetch('http://localhost:8000/api/v1/dispatch/simulate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ alarm_text: alarmText })
      })
      const data = await res.json()
      setResult(data)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen p-8 flex flex-col items-center">
      <h1 className="text-3xl font-bold mb-8 text-blue-400">Fire Dispatch Command Center</h1>
      <div className="w-full max-w-4xl grid grid-cols-1 md:grid-cols-2 gap-8">
        <div className="flex flex-col gap-4 p-6 bg-slate-800 rounded-xl shadow-2xl border border-slate-700">
          <h2 className="text-xl font-semibold">Alarm Input</h2>
          <textarea 
            className="w-full h-32 p-3 bg-slate-900 rounded border border-slate-600 focus:border-blue-500 outline-none"
            value={alarmText}
            onChange={e => setAlarmText(e.target.value)}
            placeholder="Enter alarm details here..."
          />
          <button 
            onClick={handleSimulate}
            disabled={loading}
            className="px-6 py-2 bg-blue-600 hover:bg-blue-500 rounded font-medium transition-colors"
          >
            {loading ? 'Processing...' : 'Simulate Dispatch'}
          </button>
        </div>
        
        {result && (
          <div className="flex flex-col gap-6 p-6 bg-slate-800 rounded-xl shadow-2xl border border-slate-700">
            <div>
              <h3 className="text-lg font-semibold text-emerald-400">1. Incident Extraction</h3>
              <pre className="text-sm bg-slate-900 p-3 rounded mt-2 overflow-x-auto">
                {JSON.stringify(result.parsed_incident, null, 2)}
              </pre>
            </div>
            <div>
              <h3 className="text-lg font-semibold text-purple-400">2. Mock Rules Applied</h3>
              <pre className="text-sm bg-slate-900 p-3 rounded mt-2 overflow-x-auto">
                {JSON.stringify(result.mock_context_applied, null, 2)}
              </pre>
            </div>
            <div>
              <h3 className="text-lg font-semibold text-orange-400">3. Command Generated</h3>
              <div className="text-sm bg-slate-900 p-3 rounded mt-2 whitespace-pre-wrap">
                {result.command_draft}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default App
```

**Step 2: Commit**

```bash
cd /Users/itboybob/Project/fire-dispatch-mvp
git add frontend/src/
git commit -m "feat: build React dashboard UI and integrate with backend API"
```

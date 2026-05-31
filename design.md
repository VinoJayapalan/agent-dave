# Workspace Design

Two projects in this workspace:

- **agent-dave** — the Python CLI agent that automates code changes
- **operations-dashboard** — the React target app that the agent modifies

---

## 0. Demo — how it works

```
 YOU                      AGENT-DAVE                    CLAUDE SONNET 4.6
  │                           │                               │
  │  python3 agent.py         │                               │
  │  "add a live clock        │                               │
  │   to the header"          │                               │
  │ ─────────────────────────▶│                               │
  │                           │                               │
  │                           │── scan operations-dashboard ──│
  │                           │   src/**/*.{js,jsx,json}      │
  │                           │   collect file previews       │
  │                           │                               │
  │                           │──── plan_change() ───────────▶│
  │                           │     requirement +             │
  │                           │     file list +               │
  │                           │     file previews             │
  │                           │                               │
  │                           │◀─── AgentPlan ────────────────│
  │                           │     summary                   │
  │                           │     relevant_files            │
  │                           │     suggested_change          │
  │                           │                               │
  │                           │── read full file content ─────│
  │                           │   for each relevant file      │
  │                           │                               │
  │                           │──── generate_edits() ────────▶│
  │                           │     (one API call per file)   │
  │                           │     original content +        │
  │                           │     requirement + plan        │
  │                           │                               │
  │                           │◀─── FileEdit ─────────────────│
  │                           │     { changed, new_content }  │
  │                           │                               │
  │                           │── write to disk ──────────────│
  │                           │   operations-dashboard/src/   │
  │                           │                               │
  │   Running build           │── npm run build ──────────────│
  │   validation...           │   (validate no compile errors)│
  │◀──────────────────────────│                               │
  │                           │                               │
  │   Build: ✅ PASSED        │── git checkout -b ────────────│
  │   Creating branch...      │   agent-dave/<slug>           │
  │   Committing changes...   │── git add + commit ───────────│
  │   Pushing branch...       │── git push origin ────────────│
  │   Opening pull request...  │                               │
  │                           │── GitHub REST API ────────────│
  │                           │   POST /repos/.../pulls       │
  │                           │                               │
  │   Pull request opened:    │                               │
  │   github.com/.../pull/N   │                               │
  │◀──────────────────────────│                               │
```

### Demo command

```bash
cd /home/jvino/workspace/operations-dashboard && git checkout main
cd /home/jvino/workspace/agent-dave
source .venv/bin/activate
python3 agent.py "add a live clock to the dashboard header"
```

### What happens in the browser after the PR is merged

```
 Before                          After
 ┌──────────────────────┐        ┌──────────────────────────────┐
 │  Operations Dashboard│        │  Operations Dashboard  12:34 │
 │  ──────────────────  │        │  ────────────────────────── │
 │  INCIDENTS  [2]      │        │  INCIDENTS  [2]              │
 │  System Status...    │  ───▶  │  System Status...            │
 │  Active Alerts...    │        │  Active Alerts...            │
 └──────────────────────┘        └──────────────────────────────┘
         main                            agent-dave/... → PR → merge
```

---

## 1. agent-dave — component flow

```
┌─────────────────────────────────────────────────────────────┐
│                        agent.py                             │
│              CLI entry — reads requirement arg              │
└──────────────────────────┬──────────────────────────────────┘
                           │ run_agent(requirement)
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                     orchestrator.py                         │
│                                                             │
│  1. list_repo_files()   ← repo_tools.py                     │
│     scan src/**/*.{js,jsx,json}  (up to 300 files)          │
│                                                             │
│  2. read_file()[:1200]  ← file_tools.py                     │
│     collect previews of first 8 files                       │
│                                                             │
│  3. adapter.plan_change()   ← model_adapter.py              │
│     → returns AgentPlan                                     │
│       - summary                                             │
│       - relevant_files                                      │
│       - suggested_change                                    │
│                                                             │
│  4. read_file() full content                                │
│     for each file in relevant_files                         │
│                                                             │
│  5. adapter.generate_edits()  ← model_adapter.py            │
│     → returns AgentEdits                                    │
│       - list of FileEdit(path, new_content)                 │
│                                                             │
│  6. write_file()  ← file_tools.py                           │
│     write each edit to disk                                 │
│                                                             │
│  7. run_build()   ← validator_tools.py                      │
│     npm run build  (120s timeout)                           │
│     ❌ FAILED → print errors, stop                          │
│     ✅ PASSED → continue                                    │
│                                                             │
│  8. create_branch()   ← git_tools.py                        │
│     git checkout -b agent-dave/<slug>                       │
│                                                             │
│  9. commit_changes()  ← git_tools.py                        │
│     git add <edited files> && git commit                    │
│                                                             │
│  10. push_branch()    ← git_tools.py                        │
│      git push origin <branch>                               │
│                                                             │
│  11. create_pull_request()  ← github_tools.py               │
│      POST /repos/.../pulls  (GitHub REST API)               │
│      → returns PullRequest(url, number, title)              │
└─────────────────────────────────────────────────────────────┘
```

### model_adapter.py — provider-agnostic LLM interface

```
ModelAdapter (Protocol)
│
├── StubAdapter
│   ├── plan_change()      → deterministic no-op, no API call
│   └── generate_edits()   → returns empty edits
│
└── AnthropicAdapter
    ├── plan_change()      → POST /v1/messages  (max_tokens=1024)
    │   └── _build_prompt()
    ├── generate_edits()   → one POST per relevant file  (max_tokens=4096)
    │   └── _build_edit_prompt()
    └── shared helpers
        ├── _call_api()         single requests.post wrapper
        ├── _extract_text()     pulls text blocks from response
        ├── _extract_json()     strips fences + prose preamble
        ├── _parse_json()       json.loads with clear error on failure
        └── _raise_for_api_error()  surfaces Anthropic error.message

get_model_adapter()  →  reads MODEL_PROVIDER env var
                        "anthropic" → AnthropicAdapter
                        anything else → StubAdapter
```

---

## 2. operations-dashboard — React component tree

```
index.js
└── App.js
    └── MainLayout.jsx                   (layout/MainLayout.jsx)
        │   props: children
        │   state: time (live clock, updates every 1s)
        │         center (lat/lng from browser geolocation)
        │   data:  APP_NAME  ← constants/index.js
        │
        ├── Header bar
        │   ├── <APP_NAME> title
        │   ├── Live clock  (time state)
        │   └── Google Maps iframe  (center state)
        │
        └── DashboardPage.jsx            (pages/DashboardPage.jsx)
                state: geo (lat/lon from geolocation API)
                data:  mockSystems, mockAlerts, mockWeatherForecast
                       ← data/mockDashboard.js
                utils: formatTimestamp()  ← utils/index.js
                │
                ├── Incident count tile
                │   ├── "INCIDENTS" label
                │   └── Red circle badge  (mockAlerts.length)
                │
                ├── Weather forecast row
                │   └── WeatherCard × 5  (mockWeatherForecast)
                │       icon / condition / high / low
                │
                ├── System Status table
                │   └── Row × N  (mockSystems)
                │       ├── system name
                │       ├── StatusBadge  ← components/StatusBadge.jsx
                │       └── formatTimestamp(lastChecked)
                │
                └── Active Alerts table
                    └── Row × N  (mockAlerts)
                        ├── severity  (CRITICAL → alertBadgeStyle red span)
                        │            (other    → StatusBadge)
                        ├── message
                        └── formatTimestamp(timestamp)
```

### Supporting modules

```
constants/index.js
├── APP_NAME = 'Operations Dashboard'
├── STATUS        { OK, WARNING, CRITICAL, UNKNOWN }
├── STATUS_COLORS { OK:#2e7d32, WARNING:#f9a825, CRITICAL:#c62828, UNKNOWN:#757575 }
└── REFRESH_INTERVAL_MS = 30000

utils/index.js
├── getStatusColor(status)   → hex color from STATUS_COLORS
└── formatTimestamp(iso)     → toLocaleString()

data/mockDashboard.js
├── mockSystems[5]           → Flight Ops API, Ground Control Feed, ...
├── mockAlerts[2]            → CRITICAL + WARNING entries
└── mockWeatherForecast[5]   → Mon–Fri weather cards

components/StatusBadge.jsx
└── StatusBadge({ status })
    └── getStatusColor(status) → inline span with colored background
```

---

## 3. Data flow — end to end

```
Terminal
  │
  │  python3 agent.py "add a live clock to the header"
  │
  ▼
agent-dave
  │  reads src/ files from operations-dashboard
  │  sends to Claude Sonnet 4.6
  │  Claude identifies: src/layout/MainLayout.jsx
  │  Claude returns new file content
  │  writes to disk
  │  npm run build ✅
  │  git branch + commit + push
  │  GitHub REST API
  │
  ▼
GitHub
  └── Pull Request opened
        head: agent-dave/add-a-live-clock-to-the-header
        base: main
        body: summary + suggested change + files edited
```

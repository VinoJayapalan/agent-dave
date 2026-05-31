# agent-dave

A local Python CLI developer agent that accepts a plain-English requirement,
inspects the `operations-dashboard` React repository, applies the minimal code
change, validates the build, and opens a pull request for review — all from a
single terminal command.

---

## Workspace layout

```
workspace/
├── agent-dave/               ← this project (the agent)
│   ├── agent.py              ← CLI entry point
│   ├── orchestrator.py       ← end-to-end pipeline
│   ├── model_adapter.py      ← provider-agnostic LLM interface
│   ├── config.py             ← env var loading
│   ├── requirements.txt
│   ├── .env                  ← secrets (not committed)
│   ├── prompts/
│   │   └── system_prompt.txt
│   └── tools/
│       ├── file_tools.py     ← read / write files
│       ├── repo_tools.py     ← scan repo, list files
│       ├── validator_tools.py← npm run build validation
│       ├── git_tools.py      ← branch / commit / push
│       └── github_tools.py   ← GitHub REST API (PR creation)
│
└── operations-dashboard/     ← target React app (modified by the agent)
```

---

## How to run

```bash
cd /home/jvino/workspace/agent-dave

# Activate virtual environment
source .venv/bin/activate

# Run the agent with a requirement
python3 agent.py "add a red alert badge to the incident count tile"
```

---

## Full pipeline — step by step

```
CLI input
    │
    ▼
1. Scan repo
   └─ list_repo_files()  →  up to 300 src/ files from operations-dashboard

    │
    ▼
2. Collect file previews
   └─ first 8 src/**/*.{js,jsx,json} files, first 1200 chars each

    │
    ▼
3. Plan (Claude Sonnet 4.6)
   └─ ModelAdapter.plan_change()
   └─ Returns AgentPlan:
        - summary          short description of the change
        - relevant_files   which files need editing
        - suggested_change what exactly to do

    │
    ▼
4. Per-file edit (Claude Sonnet 4.6)
   └─ For each relevant file:
        read full content
        → ModelAdapter.generate_edits()
        → Claude returns { changed: bool, new_content: string }
        → write_file() if changed

    │
    ▼
5. Build validation
   └─ run_build()  →  npm run build  (120s timeout)
   └─ ❌ FAILED  → print compiler errors, stop
   └─ ✅ PASSED  → continue

    │
    ▼
6. Git branch
   └─ create_branch()
        branch name: agent-dave/<slugified-requirement>
        if branch already exists locally → checkout main, delete, recreate

    │
    ▼
7. Commit
   └─ commit_changes()
        git add -- <edited files only>
        git commit -m "feat: <requirement>"

    │
    ▼
8. Push
   └─ push_branch()  →  git push origin <branch>

    │
    ▼
9. Pull Request
   └─ create_pull_request()  →  GitHub REST API
   └─ PR body includes: summary, suggested change, files edited
   └─ Prints PR URL to terminal
```

---

## Example output

```
Running build validation...
Creating branch: agent-dave/add-a-red-alert-badge-to-the-incident-count-tile
Committing changes...
Pushing branch: agent-dave/add-a-red-alert-badge-to-the-incident-count-tile
Opening pull request...

Requirement: add a red alert badge to the incident count tile

Plan summary: Add a red alert badge to the incident count tile in the dashboard

Relevant files:
src/pages/DashboardPage.jsx

Suggested change:
Add alertBadgeStyle span inside the tile showing mockAlerts.length

Edits applied to:
  src/pages/DashboardPage.jsx

Build: ✅ PASSED

Pull request opened: https://github.com/VinoJayapalan/operations-dashboard/pull/1
```

---

## Configuration — `.env`

```env
# LLM provider: "anthropic" for live calls, "stub" for no-op testing
MODEL_PROVIDER=anthropic

# Anthropic
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-sonnet-4-6

# GitHub fine-grained personal access token
# Required permissions: Contents (read/write), Pull requests (read/write)
GITHUB_TOKEN=github_pat_...
GITHUB_OWNER=VinoJayapalan
GITHUB_REPO=operations-dashboard
GITHUB_BASE_BRANCH=main

# Local path to the target React app
TARGET_REPO_PATH=/home/jvino/workspace/operations-dashboard
```

---

## Model adapter — provider-agnostic design

```
ModelAdapter (Protocol)
├── StubAdapter        → deterministic no-op, no API calls, safe for testing
└── AnthropicAdapter   → Claude Sonnet 4.6 via requests (no SDK dependency)
```

Switch provider with `MODEL_PROVIDER=stub` — no code changes needed.

The adapter exposes two methods:

| Method | Purpose |
|---|---|
| `plan_change(requirement, repo_files, file_previews)` | Returns `AgentPlan` — summary, relevant files, suggested change |
| `generate_edits(requirement, plan, file_contents)` | Returns `AgentEdits` — list of `FileEdit(path, new_content)` |

---

## Tools reference

| Module | Function | What it does |
|---|---|---|
| `file_tools` | `read_file(path)` | Read a file as string |
| `file_tools` | `write_file(path, content)` | Write full file content to disk |
| `repo_tools` | `list_repo_files(repo_path, limit)` | Walk repo, return relative paths, skip node_modules/dist/.git |
| `repo_tools` | `find_files_by_name(repo_path, filename)` | Find files by name glob |
| `validator_tools` | `run_build(repo_path)` | Run `npm run build`, return `BuildResult(success, output, error)` |
| `git_tools` | `create_branch(repo_path, branch_name)` | Checkout new branch, handles stale local branch cleanup |
| `git_tools` | `commit_changes(repo_path, files, message)` | Stage only edited files and commit |
| `git_tools` | `push_branch(repo_path, branch_name)` | Push branch to origin |
| `github_tools` | `create_pull_request(title, body, branch)` | Open PR via GitHub REST API, return `PullRequest(url, number, title)` |

---

## Setup

```bash
cd /home/jvino/workspace/agent-dave

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy and fill in secrets
cp .env.example .env   # then edit .env with your keys
```

### Requirements

- Python 3.12+
- Node.js + npm (for build validation)
- Git configured with SSH access to the target repo
- Anthropic API key
- GitHub fine-grained PAT with **Contents: read/write** and **Pull requests: read/write**

---

## Testing without API calls

```bash
MODEL_PROVIDER=stub python3 agent.py "add a status column to the alerts table"
```

The stub adapter returns a deterministic plan and skips all API calls and disk writes.

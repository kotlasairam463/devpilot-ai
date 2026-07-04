# DevPilot AI — Project Documentation

Multi-agent AI code review system that automatically reviews GitHub pull requests using Gemini, and posts results back as PR comments. Includes a live analytics dashboard.

---

## 1. Architecture Overview

```
┌─────────────┐      webhook       ┌──────────────────┐
│   GitHub    │ ─────────────────▶ │  FastAPI Backend  │
│  Repository │ ◀───────────────── │   (Cloud Run)      │
└─────────────┘   PR comment       └────────┬──────────┘
                                             │
                    ┌────────────────────────┼────────────────────────┐
                    ▼                        ▼                        ▼
            ┌───────────────┐        ┌──────────────┐        ┌───────────────┐
            │  Gemini AI     │        │  MongoDB      │        │  Angular       │
            │ (Vertex AI /   │        │  Atlas        │        │  Dashboard     │
            │  API key)      │        │  (M0 free)    │        │  (Cloud Run)   │
            └───────────────┘        └──────────────┘        └───────────────┘
```

**Flow in one sentence:** a PR is opened/updated → GitHub fires a webhook → FastAPI fetches the changed files → five AI agents analyze the code sequentially → results are saved to MongoDB and posted back as a single PR comment → the Angular dashboard polls MongoDB via REST to show analytics and history.

---

## 2. Tech Stack

| Layer | Technology |
|---|---|
| Backend API | FastAPI (Python) |
| AI models | Google Gemini 2.5 Flash (dev) / Gemini 2.5 Pro via Vertex AI (prod) |
| Database | MongoDB Atlas (M0 free tier) |
| GitHub integration | PyGithub + GitHub webhooks |
| Frontend | Angular (standalone components) |
| Hosting | Google Cloud Run (both frontend and backend) |
| Containerization | Docker |
| Secrets | Google Secret Manager |

---

## 3. Backend Structure

```
backend/
├── api/
│   └── main.py                 # FastAPI app, routes, webhook handler
├── workflow/
│   ├── orchestrator.py         # Runs all agents in sequence
│   └── state.py                # PipelineState TypedDict (shared state contract)
├── agents/
│   ├── base_agent.py           # Shared Gemini client + JSON-parsing helper
│   ├── review_agent.py         # Code quality review
│   ├── security_agent.py       # Vulnerability scanning
│   ├── test_agent.py           # Unit test generation
│   ├── autofix_agent.py        # Auto-remediation of found issues
│   └── documentation_agent.py  # Plain-English code summary
├── database/
│   └── mongo.py                # MongoDB Atlas connection + CRUD
├── mcp/
│   └── github_mcp.py           # PyGithub wrapper: fetch PR files, post comments
├── requirements.txt
├── Dockerfile
└── .env                        # Local-only secrets (never committed)
```

---

## 4. How the Agents Work (Pipeline)

`orchestrator.run_pipeline()` runs five agents **sequentially**, passing a shared `PipelineState` dict between them:

| Step | Agent | Input | Output |
|---|---|---|---|
| 1 | **Review Agent** | Raw PR code | Code quality score (0–10), list of issues, suggestions |
| 2 | **Security Agent** | Raw PR code | `is_safe` flag, list of vulnerabilities with severity + fix |
| 3 | **AutoFix Agent** | Code + issues + vulnerabilities (only runs if any exist) | `fixed_code` — a corrected version |
| 4 | **Test Agent** | Fixed code (or original if no fix was needed) | Generated unit tests |
| 5 | **Documentation Agent** | Fixed code (or original) | Plain-English `doc_summary` of what the code does |

After all agents finish, the orchestrator computes:
- `overall_score` — from the Review Agent
- `should_block_merge` — `true` if any **critical** vulnerability exists or score < 5
- `severity_level` — `critical` / `high` / `low`
- `final_summary` — a formatted Markdown report combining all agent outputs, posted directly as the GitHub PR comment

Each agent is isolated with its own try/except — if one agent fails (e.g. Gemini API 503 overload), the pipeline **degrades gracefully** instead of crashing: it logs a warning, substitutes a placeholder, and continues to the next agent.

**Why sequential, not parallel:** AutoFix depends on Review + Security's output, and Test/Documentation operate on the *fixed* code where possible — so agents 3–5 have data dependencies on 1–2.

---

## 5. GitHub Integration

### Webhook flow (`POST /webhook` in `main.py`)
1. GitHub sends a JSON payload on `pull_request` events (`opened`, `synchronize`)
2. Backend validates the payload shape (repo name, PR number, title present)
3. `GitHubMCP.get_pr_files()` fetches up to 3 changed files' full content via the GitHub API (not just diffs)
4. The review is queued as a **FastAPI `BackgroundTask`** — the webhook responds to GitHub immediately (`"status": "accepted"`) instead of blocking until the AI agents finish, avoiding GitHub's webhook delivery timeout
5. In the background, `process_webhook_pipeline()` runs `run_pipeline()` per file, saves each result to MongoDB, then combines all file summaries into **one** PR comment via `GitHubMCP.post_comment()`

### `GitHubMCP` responsibilities
- `get_pr_files()` — fetches full file content (not just patch diffs) for changed files in a PR, skips removed/binary files
- `post_comment()` — posts the consolidated review as an issue comment on the PR
- `create_security_issue()` — (available, not yet wired in) opens a GitHub issue for critical vulnerabilities

### Manual trigger (no GitHub needed)
`POST /api/review` — accepts a single code snippet directly (used for local testing without a real PR)

---

## 6. Database — MongoDB Atlas

**Setup steps followed:**
1. Created free account at cloud.mongodb.com
2. Created an M0 (free tier) cluster
3. Created a database user (`devpilot_user`) with read/write access
4. Network Access → allowed `0.0.0.0/0` (required since Cloud Run has no static outbound IP on the free tier)
5. Copied the **Drivers → Python** connection string, added `/devpilot_ai` as the database name

**Schema — `reviews` collection** (one document per file reviewed):
```json
{
  "pr_title": "string",
  "pr_url": "string",
  "filename": "string",
  "score": 8,
  "is_safe": true,
  "vulnerabilities": [{ "type": "...", "severity": "...", "line": "...", "fix": "..." }],
  "issues": ["..."],
  "blocked": false,
  "severity": "low",
  "summary": "markdown final_summary text",
  "generated_tests": "...",
  "fixed_code": "...",
  "doc_summary": "...",
  "created_at": "datetime"
}
```

**Key methods (`database/mongo.py`):**
- `save_review()` — inserts one document per reviewed file
- `get_analytics()` — aggregates total reviews, blocked count, unsafe count, average score, approval rate
- `get_recent_reviews(limit=10)` — powers the dashboard history table
- `delete_all_reviews()` — wipes all collections (used by the dashboard's "Clear history" action, requires `?confirm=true`)

**Local DNS issue encountered:** `mongodb+srv://` connection strings require DNS SRV record resolution, which failed on a home router's default DNS. Fixed by switching the machine's DNS to `8.8.8.8` / `8.8.4.4` (Google DNS) — this is a per-device setting, doesn't affect the network or other users.

---

## 7. API Reference

| Method | Route | Purpose |
|---|---|---|
| GET | `/` | Health check |
| POST | `/api/review` | Manually submit one code snippet for review |
| POST | `/webhook` | GitHub webhook receiver (PR opened/updated) |
| GET | `/api/analytics` | Aggregated stats for dashboard KPI cards |
| GET | `/api/history` | Last 10 reviews for dashboard table |
| DELETE | `/api/history?confirm=true` | Deletes all stored reviews |

---

## 8. Frontend — Angular Dashboard

Single-page dashboard (no review-submission UI — analytics/history only):
- **KPI cards** — total reviews, average score, approval rate, security flags
- **Score trend chart** — hand-built SVG line chart (no charting library) plotting the last 10 review scores
- **Two donut charts** — Approved vs Blocked, Safe vs Flagged (via CSS `conic-gradient`)
- **History table** — searchable, sortable, filterable (status/safety), paginated, with expandable rows showing per-review issues, vulnerabilities, and the documentation summary
- **Auto-refresh** — polls `/api/analytics` and `/api/history` every 60 seconds
- **Clear history** — confirmation modal → calls the delete endpoint

Structure:
```
frontend/src/app/
├── app.ts             # Component logic: polling, filters, sort, pagination, chart math
├── app.html            # Template
├── app.scss            # Styles (design tokens: indigo/slate palette)
└── services/
    └── api.service.ts # Typed HTTP client for analytics/history/delete
```

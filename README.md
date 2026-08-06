# DevPilot AI — Project Documentation

Multi-agent AI code review system that automatically reviews GitHub pull requests using Gemini via Google's Agent Development Kit (ADK), and posts results back as PR comments. Includes a live analytics dashboard.

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
            │  via ADK       │        │  Atlas        │        │  Dashboard     │
            │ (Vertex AI /   │        │  (M0 free)    │        │  (Cloud Run)   │
            │  API key)      │        │               │        │               │
            └───────────────┘        └──────────────┘        └───────────────┘
```

**Flow in one sentence:** a PR is opened/updated → GitHub fires a webhook → FastAPI fetches only the files changed since the last review → a 5-agent ADK pipeline analyzes each file across two parallel waves plus one dependent step → results are saved to MongoDB and posted back as a single PR comment → the Angular dashboard polls MongoDB via REST to show analytics and history in IST.

---

## 2. Tech Stack

| Layer | Technology |
|---|---|
| Backend API | FastAPI (Python), fully async |
| Agent framework | Google ADK (`google-adk>=2.2.0,<3.0.0`) — `LlmAgent`, `SequentialAgent`, `ParallelAgent` |
| AI models | Gemini 2.5 Flash (dev) / Gemini 2.5 Pro via Vertex AI (prod) |
| Structured output | Pydantic schemas via ADK's `output_schema` |
| Database | MongoDB Atlas (M0 free tier) |
| GitHub integration | PyGithub + GitHub webhooks, incremental diff-based review |
| Frontend | Angular (standalone components) |
| Hosting | Google Cloud Run (both frontend and backend) |
| CI/CD | Cloud Build trigger on push to `main` (`cloudbuild.yaml`) |
| Containerization | Docker |
| Secrets | Google Secret Manager |

---

## 3. Backend Structure

```
backend/
├── api/
│   └── main.py                  # FastAPI app, routes, async webhook handler
├── config.py                    # MODEL_NAME + Vertex/API-key env var bridging for ADK
├── schemas.py                   # Pydantic output contracts (ReviewOutput, SecurityOutput, etc.)
├── rate_limiter.py               # Token-bucket limiter shared across agent calls
├── workflow/
│   └── orchestrator.py          # ADK pipeline: parallel waves + AutoFix + event capture
├── agents/
│   ├── review_agent.py          # Code quality review (LlmAgent)
│   ├── security_agent.py        # Vulnerability scanning (LlmAgent)
│   ├── autofix_agent.py         # Conditional auto-remediation (custom BaseAgent)
│   ├── testcase_agent.py        # Unit test generation (LlmAgent, raw text output) — renamed from test_agent.py
│   └── documentation_agent.py   # Plain-English code summary (LlmAgent)
├── database/
│   └── mongo.py                 # MongoDB Atlas connection + CRUD + incremental-review tracking
├── mcp/
│   └── github_mcp.py            # PyGithub wrapper: fetch PR files (full + incremental), post comments
├── requirements.txt
├── Dockerfile
├── .dockerignore                # Excludes venv/, __pycache__, .env from build context
└── .env                         # Local-only secrets (never committed)
```

`agents/base_agent.py` and `workflow/state.py` from the original SDK-based version have been
**removed** — ADK's `LlmAgent`/session state replaces both.

---

## 4. How the Agents Work (ADK Pipeline)

The pipeline is no longer fully sequential. Based on actual data dependencies, it runs as
**two parallel waves with one dependent step in between**:

```python
analysis_wave = ParallelAgent(sub_agents=[review_agent, security_agent])
finalization_wave = ParallelAgent(sub_agents=[testcase_agent, documentation_agent])
pipeline = SequentialAgent(sub_agents=[analysis_wave, autofix_agent, finalization_wave])
```

| Wave | Agent | Depends on | Produces |
|---|---|---|---|
| 1 (parallel) | **Review Agent** | `pr_code` only | Score (0–10), issues, suggestions |
| 1 (parallel) | **Security Agent** | `pr_code` only | `is_safe`, vulnerabilities with severity + fix |
| 2 | **AutoFix Agent** | Review + Security output (only runs if issues/vulns exist) | `fixed_code`, `changes_made`, `explanation` |
| 3 (parallel) | **TestCase Agent** | Fixed code (or original) | Raw unit test code |
| 3 (parallel) | **Documentation Agent** | Fixed code (or original) | Plain-English summary |

Review and Security don't depend on each other, and TestCase/Documentation don't depend on each
other either — only AutoFix has a genuine dependency on prior output. Running the independent
pairs concurrently cuts wall-clock latency roughly 40% versus a fully sequential chain, at no
cost to output quality.

**AutoFix is a custom `BaseAgent`, not a plain `LlmAgent`** — it's the only agent that needs to
conditionally skip calling the LLM entirely when Review/Security found nothing to fix, which
`LlmAgent`/`SequentialAgent` can't do on their own (they always execute every step).

**Structured output via Pydantic (`schemas.py`)** — every agent except TestCase uses ADK's
`output_schema` parameter with a Pydantic model (`ReviewOutput`, `SecurityOutput`,
`AutoFixOutput`, `DocumentationOutput`), instead of manually parsing JSON strings out of raw model
text. TestCase has no schema since its job is to return raw, executable code, not JSON.

**Known workaround — event-based output capture, not `session.state`:** in the installed ADK
version, `output_key`'s automatic state-write did not reliably populate `session.state` when
running under `SequentialAgent`/`ParallelAgent`. `run_pipeline()` instead listens to the runner's
event stream directly and captures each agent's final output keyed by its `author` name. This is
documented as a pragmatic fix, not the "textbook" ADK 2.0 pattern — a future migration to the
newer graph-based `Workflow`/`Agent` API would likely make this unnecessary, but was deferred
since the current approach works reliably in production.

**`RetryConfig` is not used on `LlmAgent`/`BaseAgent`** — it turned out to belong to ADK's newer
`Workflow`/`BaseNode` execution model, not the legacy agent classes this project uses. Retries are
handled by allowing exceptions to propagate up to a wrapping try/except in `run_pipeline()`, which
logs the failure and returns partial/empty results rather than crashing.

**`SequentialAgent`/`ParallelAgent` are deprecated (warning only, not broken)** — ADK is moving
toward a unified `Workflow` class. Migration was deferred as non-urgent since these classes are
still functional; only a warning is emitted today.

---

## 5. GitHub Integration

### Webhook flow (`POST /webhook` in `main.py`, fully async)
1. GitHub sends a JSON payload on `pull_request` events (`opened`, `synchronize`)
2. Backend validates the payload shape (repo name, PR number, title, head SHA present)
3. Checks MongoDB (`pr_tracking` collection) for a previously reviewed commit SHA for this PR
4. **First review of a PR** → `GitHubMCP.get_pr_files()` fetches up to 5 changed files' full content
5. **Subsequent pushes to the same PR** → `GitHubMCP.get_pr_files_since(last_sha)` fetches only
   files changed since the last reviewed commit, via GitHub's compare API — avoiding redundant
   re-review of unchanged files on every push
6. The review is queued as a **FastAPI `BackgroundTask`** (`await`ed, since the pipeline is async)
   — the webhook responds to GitHub immediately (`"status": "accepted"`) instead of blocking until
   the AI agents finish, avoiding GitHub's webhook delivery timeout
7. In the background, `process_webhook_pipeline()` runs `run_pipeline()` per file, saves each
   result to MongoDB, combines all file summaries into **one** PR comment via
   `GitHubMCP.post_comment()`, and records the new head SHA in `pr_tracking` for next time

### `GitHubMCP` responsibilities
- `get_pr_files(max_files=5)` — fetches full file content (not just patch diffs) for changed
  files in a PR, skips removed/binary files
- `get_pr_files_since(since_sha, max_files=5)` — incremental variant, diffs against a prior
  commit SHA; falls back to `get_pr_files()` if the comparison fails (e.g. after a force-push)
- `post_comment()` — posts the consolidated review as an issue comment on the PR
- `create_security_issue()` — (available, not yet wired in) opens a GitHub issue for critical
  vulnerabilities

### File limit
Currently capped at **5 files per PR trigger**. Each file costs up to 5 Gemini calls across the
pipeline (fewer if AutoFix skips), so a full 5-file PR is up to 25 calls per webhook trigger. This
is a cost/latency control, not a technical ceiling — raise `max_files` in both `github_mcp.py` and
`main.py` if larger PRs need full coverage.

### Manual trigger (no GitHub needed)
`POST /api/review` — accepts a single code snippet directly (used for local/Swagger testing
without a real PR). Fully async, `await`s `run_pipeline()`.

---

## 6. Database — MongoDB Atlas

**Setup steps followed:**
1. Created free account at cloud.mongodb.com
2. Created an M0 (free tier) cluster
3. Created a database user (`devpilot_user`) with read/write access
4. Network Access → allowed `0.0.0.0/0` (required since Cloud Run has no static outbound IP on
   the free tier)
5. Copied the **Drivers → Python** connection string, added `/devpilot_ai` as the database name

**Collections:**

`reviews` — one document per file reviewed:
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
  "summary": "markdown final_summary text, includes fixed_code inline",
  "generated_tests": "...",
  "fixed_code": "...",
  "doc_summary": "...",
  "created_at": "datetime (stored UTC)"
}
```

`pr_tracking` — one document per PR, supports incremental review:
```json
{ "pr_url": "string", "last_sha": "commit sha", "updated_at": "datetime" }
```

**Key methods (`database/mongo.py`):**
- `save_review()` — inserts one document per reviewed file
- `get_analytics()` — aggregates total reviews, blocked count, unsafe count, average score,
  approval rate, computed on read via Mongo's aggregation pipeline (not a maintained counter)
- `get_recent_reviews(limit=10)` — powers the dashboard history table
- `get_last_reviewed_sha(pr_url)` / `set_last_reviewed_sha(pr_url, sha)` — incremental-review
  tracking, backs the webhook's diff-since-last-push logic
- `delete_all_reviews()` — wipes `reviews`, `security_issues`, and `analytics` collections (used
  by the dashboard's "Clear history" action, requires `?confirm=true`)

**Timezone note:** `created_at` is stored as UTC (`datetime.utcnow()`), which is correct practice
for storage. The Angular dashboard converts to IST for display using Angular's date pipe with an
explicit `+0530` offset, rather than relying on the browser's local timezone.

**Local DNS issue encountered:** `mongodb+srv://` connection strings require DNS SRV record
resolution, which failed on a home router's default DNS. Fixed by switching the machine's DNS to
`8.8.8.8` / `8.8.4.4` (Google DNS) — a per-device setting, doesn't affect the network or other
users.

---

## 7. API Reference

| Method | Route | Purpose |
|---|---|---|
| GET | `/` | Health check |
| POST | `/api/review` | Manually submit one code snippet for review (async) |
| POST | `/webhook` | GitHub webhook receiver — incremental or full review depending on PR history |
| GET | `/api/analytics` | Aggregated stats for dashboard KPI cards |
| GET | `/api/history` | Last 10 reviews for dashboard table |
| DELETE | `/api/history?confirm=true` | Deletes all stored reviews across all collections |

---

## 8. Frontend — Angular Dashboard

Single-page dashboard (no review-submission UI — analytics/history only):
- **KPI cards** — total reviews, average score, approval rate, security flags
- **Score trend chart** — hand-built SVG line chart (no charting library) plotting the last 10
  review scores
- **Two donut charts** — Approved vs Blocked, Safe vs Flagged (via CSS `conic-gradient`)
- **History table** — searchable, sortable, filterable (status/safety), paginated, with
  expandable rows showing per-review issues, vulnerabilities, and the documentation summary;
  dates displayed in IST regardless of viewer's local timezone
- **Auto-refresh** — polls `/api/analytics` and `/api/history` every 60 seconds, no manual toggle
- **Clear history** — confirmation modal → calls the delete endpoint → shows loading state (not a
  blank flash) while fresh data loads

Structure:
```
frontend/src/app/
├── app.ts              # Component logic: polling, filters, sort, pagination, chart math
├── app.html             # Template
├── app.scss             # Styles (design tokens: indigo/slate palette)
├── tsconfig.app.json     # rootDir explicitly set to ./src
└── services/
    └── api.service.ts   # Typed HTTP client for analytics/history/delete
```

`angular.json`'s production config includes `fileReplacements` (swaps `environment.ts` for
`environment.prod.ts` at build time — required for the deployed dashboard to hit the real backend
URL instead of `localhost`) and a raised `anyComponentStyle` budget (12kb/16kb) to accommodate the
dashboard's SCSS.

---

## 9. Docker Setup

**`backend/Dockerfile`:**
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
ENV PORT=8080
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

**`backend/.dockerignore`:**
```
venv/
__pycache__/
*.pyc
.env
.git
```

**`frontend/Dockerfile`:**
```dockerfile
FROM node:22 AS build
WORKDIR /app
COPY . .
RUN npm install && npm run build -- --configuration production

FROM nginx:alpine
COPY --from=build /app/dist/*/browser /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 8080
```
(Node 22 required — Angular CLI 22 needs Node ≥22.22.3; Node 20 fails the build.)

**`frontend/.dockerignore`** — critical fix, not optional:
```
node_modules
dist
.angular
.git
```
Without this, a locally-generated `node_modules/` (with Windows file permissions) gets copied
into the Linux build context, producing `sh: 1: ng: Permission denied` during build. Excluding it
forces a clean in-container `npm install` with correct Linux permissions every time.

**`frontend/nginx.conf`:**
```nginx
server {
    listen 8080;
    root /usr/share/nginx/html;
    index index.html;
    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

Both are stateless — Cloud Run doesn't persist local files between requests/restarts, which is
why MongoDB is external (Atlas), not a local container.

---

## 10. Google Cloud Setup

**Steps followed, in order:**

1. **Created project** `devpilot-ai` → actual Project ID: `devpilot-ai-501413`
2. **Installed Google Cloud CLI** (Windows installer), verified with `gcloud --version`
3. **Authenticated:**
   ```powershell
   gcloud auth login
   gcloud config set project devpilot-ai-501413
   ```
4. **Enabled required APIs:**
   ```powershell
   gcloud services enable run.googleapis.com
   gcloud services enable artifactregistry.googleapis.com
   gcloud services enable cloudbuild.googleapis.com
   gcloud services enable aiplatform.googleapis.com
   gcloud services enable secretmanager.googleapis.com
   ```
5. **Granted IAM permissions** to Cloud Run's default service account:
   ```powershell
   gcloud projects add-iam-policy-binding devpilot-ai-501413 --member="serviceAccount:1062543079462-compute@developer.gserviceaccount.com" --role="roles/aiplatform.user"
   gcloud projects add-iam-policy-binding devpilot-ai-501413 --member="serviceAccount:1062543079462-compute@developer.gserviceaccount.com" --role="roles/secretmanager.secretAccessor"
   ```
6. **Stored secrets** in Secret Manager instead of plaintext env vars:
   ```powershell
   "your_github_token" | gcloud secrets create github-token --data-file=-
   "your_mongodb_url" | gcloud secrets create mongodb-url --data-file=-
   ```
   To rotate a secret later without deleting it:
   ```powershell
  echo -n "new_value" | gcloud secrets versions add github-token --data-file=-
   ```
   Then force the running revision to pick up the new version:
   ```powershell
   gcloud run services update devpilot-backend --region us-central1 --update-env-vars "FORCE_RESTART=1"
   ```
7. **Deployed backend (first time, full flags):**
   ```powershell
   gcloud run deploy devpilot-backend --source ./backend --region us-central1 --allow-unauthenticated --memory 1Gi --set-env-vars "PROD_ENV=true,GCP_PROJECT_ID=devpilot-ai-501413,GCP_LOCATION=us-central1" --set-secrets "GITHUB_TOKEN=github-token:latest,MONGODB_URL=mongodb-url:latest"
   ```
8. **Deployed frontend (first time):**
   ```powershell
   gcloud run deploy devpilot-frontend --source ./frontend --region us-central1 --allow-unauthenticated --memory 512Mi
   ```
9. **Redeploys after that (env vars/secrets already attached to the service, no need to repeat
   flags):**
   ```powershell
   gcloud run deploy devpilot-backend --source ./backend --region us-central1
   gcloud run deploy devpilot-frontend --source ./frontend --region us-central1
   ```

**Why `PROD_ENV=true` needs no Gemini API key:** production uses Vertex AI, authenticated via
Cloud Run's service account (IAM-based), not an API key. `config.py` sets
`GOOGLE_GENAI_USE_VERTEXAI=TRUE` + `GOOGLE_CLOUD_PROJECT` + `GOOGLE_CLOUD_LOCATION` when
`PROD_ENV=true`, which ADK reads automatically. Locally (`PROD_ENV=false`), it sets
`GOOGLE_GENAI_USE_VERTEXAI=FALSE` + `GOOGLE_API_KEY` instead.

### CI/CD — Cloud Build trigger (optional, not required for manual deploys)

`cloudbuild.yaml` at repo root:
```yaml
steps:
  - name: 'gcr.io/cloud-builders/gcloud'
    args: ['run', 'deploy', 'devpilot-backend', '--source', './backend', '--region', 'us-central1', '--allow-unauthenticated']
  - name: 'gcr.io/cloud-builders/gcloud'
    args: ['run', 'deploy', 'devpilot-frontend', '--source', './frontend', '--region', 'us-central1', '--allow-unauthenticated']
```
Connected via **Cloud Build → Triggers → Connect Repository** → push to `^main$` → this config
file. Once set up, merging to `main` auto-deploys both services with no manual `gcloud run deploy`
needed.

### Cost notes
- Cloud Run, Artifact Registry, MongoDB Atlas M0 — effectively free at hobby scale (scale-to-zero,
  generous free tiers)
- **Vertex AI Gemini 2.5 Pro is pay-as-you-go, no free tier** — $1.25/1M input tokens, $10/1M
  output tokens. A 5-file PR (~25 Gemini calls) costs roughly $0.03–0.16 depending on file size
- New Google Cloud accounts get $300/90-day free credit; **exhausting it does not auto-charge the
  card** — services get suspended until the account is manually upgraded

---

## 11. Environment Variables

**Local (`.env`, never committed):**
```dotenv
GEMINI_API_KEY=...
GITHUB_TOKEN=...
MONGODB_URL=...
PROD_ENV=false
GCP_PROJECT_ID=devpilot-ai-501413
GCP_LOCATION=us-central1
```
`config.py` calls `load_dotenv()` before reading any of these — a real bug hit during development
was `config.py` reading `os.getenv()` without loading `.env` first, causing "No API key was
provided" locally despite the key being present in the file.

**Cloud Run (set via `--set-env-vars` / `--set-secrets`, not `.env`):**
- `PROD_ENV=true`
- `GCP_PROJECT_ID`, `GCP_LOCATION` — plain env vars
- `GITHUB_TOKEN`, `MONGODB_URL` — Secret Manager references

**Model naming caution:** `gemini-3.5-pro` is **not yet generally available** as of this writing
— using it in `config.py`/agent definitions will fail with a model-not-found error. Use
`gemini-2.5-pro` (production) / `gemini-2.5-flash` (local) until 3.5 Pro actually ships.

---

## 12. GitHub Webhook Setup (Live Trigger)

1. Repo → **Settings → Webhooks → Add webhook**
2. Payload URL: `https://devpilot-backend-1062543079462.us-central1.run.app/webhook`
3. Content type: `application/json`
4. Events: **Pull requests** only (not review comments/threads/reviews — those aren't handled)
5. No secret configured — signature verification was deliberately omitted for this project
6. Save

Every PR open or push to an open PR triggers the pipeline automatically, running on Cloud Run
regardless of whether any developer's machine is on. A webhook can be added to any repo the
token's owner has write access to — `repo_name` comes from the payload, not hardcoded — though a
GitHub App would be a better long-term fit than a personal access token for multi-repo use.

**Local testing before going live** used `ngrok http 8000` to expose the local FastAPI server
temporarily, since GitHub needs a public HTTPS URL — replaced by the permanent Cloud Run URL for
the real deployment.

---

## 13. Local Development Setup

```powershell
# Backend
cd backend
pip install -r requirements.txt --break-system-packages
uvicorn api.main:app --reload --port 8000

# Frontend
cd frontend
npm install
ng serve
```

Test the pipeline directly without the API layer:
```powershell
cd backend
python -m workflow.orchestrator
```

With `PROD_ENV=false`, the backend uses the direct Gemini API (`gemini-2.5-flash`) via ADK's
API-key mode — no Google Cloud project or Vertex AI needed for local dev.

---




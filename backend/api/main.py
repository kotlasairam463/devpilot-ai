
from fastapi import FastAPI, status, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from workflow.orchestrator import run_pipeline
from database.mongo import DevPilotDB
from mcp.github_mcp import GitHubMCP

app = FastAPI(title="DevPilot AI Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200","https://devpilot-frontend-1062543079462.us-central1.run.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db = DevPilotDB()
github = GitHubMCP()


class PRRequest(BaseModel):
    pr_title: str
    pr_code: str
    filename: str
    pr_url: str = "http://github.com/test/pr/1"


def process_webhook_pipeline(repo_name: str, pr_number: int, pr_title: str, pr_url: str, files: list):
    """
    Background worker that runs the multi-agent pipeline over files
    without blocking the primary web application request-response threads.
    """
    results = []

    for file in files[:3]:
        if not file.get("code") or len(file["code"].strip()) == 0:
            continue

        print(f"⚙️ Background Worker processing file: {file.get('filename')}")

        try:
            result = run_pipeline(
                pr_title=pr_title,
                pr_code=file["code"],
                filename=file["filename"],
                pr_url=pr_url
            )
        except Exception as e:
            print(f"❌ Pipeline failed for {file.get('filename')}: {e}")
            continue

        try:
            db.save_review(
                {"pr_title": pr_title, "pr_url": pr_url, "filename": file["filename"]},
                result
            )
        except Exception as e:
            print(f"⚠️ Failed to save review to DB: {e}")

        results.append(result)

    if results:
        combined_comment = "\n\n---\n\n".join(r["final_summary"] for r in results)
        try:
            github.post_comment(repo_name, pr_number, combined_comment)
            print(f"🎉 Completed background analysis for PR #{pr_number}")
        except Exception as e:
            print(f"❌ Failed to post GitHub comment: {e}")


@app.get("/")
def home():
    return {
        "status": "online",
        "message": "DevPilot AI Multi-Agent Core Engine Operational! 🚀",
        "version": "1.0.0"
    }


@app.post("/api/review", status_code=status.HTTP_200_OK)
def review_pr(request: PRRequest):
    """Manual trigger endpoint — handles single-file data streams from frontends"""
    result = run_pipeline(
        pr_title=request.pr_title,
        pr_code=request.pr_code,
        filename=request.filename,
        pr_url=request.pr_url
    )

    db.save_review(
        {"pr_title": request.pr_title, "pr_url": request.pr_url, "filename": request.filename},
        result
    )

    return {
        "success": True,
        "score": result.get("overall_score"),
        "is_safe": result.get("security_result", {}).get("is_safe", True),
        "blocked": result.get("should_block_merge", False),
        "severity": result.get("severity_level", "low"),
        "summary": result.get("final_summary"),
        "issues": result.get("review_result", {}).get("issues", []),
        "vulnerabilities": result.get("security_result", {}).get("vulnerabilities", []),
        "tests": result.get("generated_tests"),
        "fixed_code": result.get("fixed_code"),
        "doc_summary": result.get("doc_summary")
    }


@app.post("/webhook")
async def github_webhook(request: Request, background_tasks: BackgroundTasks):
    """Receives GitHub PR events automatically — triggered by GitHub webhook"""

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON payload")

    # GitHub sends a "ping" event (no "action") when the webhook is first registered
    if payload.get("action") not in ["opened", "synchronize"]:
        return {"status": "ignored"}

    pr = payload.get("pull_request")
    repository = payload.get("repository")

    if not pr or not repository:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing pull_request or repository in payload")

    repo_name = repository.get("full_name")
    pr_number = pr.get("number")
    pr_title = pr.get("title")
    pr_url = pr.get("html_url", "")

    if not all([repo_name, pr_number, pr_title]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing required PR fields")

    print(f"📥 PR received: #{pr_number} — {pr_title}")

    try:
        files = github.get_pr_files(repo_name, pr_number)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Failed to fetch PR files from GitHub: {e}")

    if not files:
        return {"status": "no files to review"}

    # Queue the review as a background task so we respond to GitHub
    # immediately instead of risking a webhook delivery timeout.
    background_tasks.add_task(
        process_webhook_pipeline,
        repo_name=repo_name,
        pr_number=pr_number,
        pr_title=pr_title,
        pr_url=pr_url,
        files=files
    )

    return {
        "status": "accepted",
        "message": f"Review queued for PR #{pr_number}",
        "files_queued": min(len(files), 3)
    }

@app.get("/api/analytics")
def get_analytics():
    """Fetches real-time consolidated analytics metrics for UI dashboards"""
    try:
        analytics = db.get_analytics()
        if "error" in analytics:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=analytics
            )
        return analytics
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.get("/api/history")
def get_history():
    """Extracts historical log list objects for dashboard components"""
    try:
        history = db.get_recent_reviews(limit=10)
        return history
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    
@app.delete("/api/history")
def delete_all_history(confirm: bool = False):
    """Deletes ALL review records from MongoDB. Irreversible — requires confirm=true."""
    if not confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This will permanently delete all records. Pass ?confirm=true to proceed."
        )
    try:
        result = db.delete_all_reviews()
        return {
            "success": True,
            "message": "All records deleted",
            **result
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
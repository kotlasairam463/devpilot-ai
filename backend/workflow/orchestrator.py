import config  # noqa: F401 — must import first

import json
import uuid
from google.adk.agents import SequentialAgent, ParallelAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from agents.review_agent import review_agent
from agents.security_agent import security_agent
from agents.autofix_agent import autofix_agent
from agents.testcase_agent import testcase_agent
from agents.documentation_agent import documentation_agent

APP_NAME = "devpilot_ai"

# Wave 1 — Review and Security are independent, run concurrently
analysis_wave = ParallelAgent(
    name="AnalysisWave",
    sub_agents=[review_agent, security_agent]
)

# Wave 3 — TestCase and Documentation both only need the (possibly fixed) code
finalization_wave = ParallelAgent(
    name="FinalizationWave",
    sub_agents=[testcase_agent, documentation_agent]
)

# AutoFix (Wave 2) has a real data dependency on both Review and Security,
# so it sits between the two parallel waves.
pipeline = SequentialAgent(
    name="DevPilotPipeline",
    sub_agents=[analysis_wave, autofix_agent, finalization_wave]
)

_session_service = InMemorySessionService()
_runner = Runner(agent=pipeline, app_name=APP_NAME, session_service=_session_service)


def _parse(raw, default):
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except Exception as e:
        print(f"⚠️ Failed to parse agent output: {e} | raw={raw!r}")
        return default


async def run_pipeline(pr_title: str, pr_code: str, filename: str, pr_url: str = "") -> dict:
    user_id = "webhook"
    session_id = str(uuid.uuid4())

    session = await _session_service.create_session(
        app_name=APP_NAME,
        user_id=user_id,
        session_id=session_id,
        state={"pr_title": pr_title, "pr_code": pr_code, "filename": filename, "pr_url": pr_url}
    )

    trigger_message = types.Content(role="user", parts=[types.Part(text=f"Review this PR: {pr_title}")])

    agent_outputs = {}

    try:
        async for _event in _runner.run_async(user_id=user_id, session_id=session_id, new_message=trigger_message):
            author = getattr(_event, "author", None)
            if hasattr(_event, "content") and _event.content and author:
                try:
                    text = _event.content.parts[0].text
                    agent_outputs[author] = text
                except (AttributeError, IndexError):
                    pass
    except Exception as e:
        print(f"⚠️ Pipeline execution error (likely transient API issue): {e}")
        
    print(f"🔍 CAPTURED AGENT OUTPUTS: {agent_outputs}")

    review_data = _parse(agent_outputs.get("ReviewAgent"), {})
    security_data = _parse(agent_outputs.get("SecurityAgent"), {})
    autofix_data = _parse(agent_outputs.get("AutoFixLLM") or agent_outputs.get("AutoFixAgent"), {})
    doc_data = _parse(agent_outputs.get("DocumentationAgent"), {})
    generated_testcases = agent_outputs.get("TestCaseAgent")

    issues = review_data.get("issues", [])
    vulns = security_data.get("vulnerabilities", [])
    score = review_data.get("score", 5)
    fixed_code = autofix_data.get("fixed_code")
    doc_summary = doc_data.get("summary")

    has_critical = any(v.get("severity") == "critical" for v in vulns if isinstance(v, dict))
    should_block_merge = has_critical or score < 5
    severity_level = "critical" if has_critical else "high" if vulns else "low"

    issues_text = "\n".join(f"- {i}" for i in issues)
    vulns_text = "\n".join(
        f"- {v.get('type','Unknown')} ({v.get('severity','high')}): {v.get('fix','')}"
        for v in vulns if isinstance(v, dict)
    )
    suggestions_text = "\n".join(f"- {s}" for s in review_data.get("suggestions", []))

    autofix_section = (
    f"A refactored version was generated. View it on the DevPilot dashboard, or see below:\n\n```\n{fixed_code}\n```"
    if fixed_code else "No auto-remediation updates were requested."
    )
    
    final_summary = f"""
## 🤖 DevPilot AI Review

**PR:** {pr_title}
**File:** {filename}
**Code Quality Score:** {score}/10
**Security Status:** {'🔴 UNSAFE' if vulns else '✅ SAFE'}
**Merge Decision:** {'🚫 BLOCKED — Fix issues before merging' if should_block_merge else '✅ APPROVED — Safe to merge'}

---

### 📋 Code Issues:
{issues_text if issues_text else "No major issues found ✅"}

### 🔐 Security Vulnerabilities:
{vulns_text if vulns_text else "No vulnerabilities found ✅"}

### 💡 Suggestions:
{suggestions_text if suggestions_text else "No alternative adjustments suggested."}

---
### 🛠️ Auto-Fix Code Changes:

{autofix_section}

---
### 📚 Documentation:
{doc_summary or "No documentation summary generated."}
---
*Reviewed by DevPilot AI — Powered by Gemini via Google ADK*
    """

    return {
        "pr_title": pr_title, "pr_code": pr_code, "filename": filename, "pr_url": pr_url,
        "review_result": review_data, "security_result": security_data,
        "fixed_code": fixed_code, "generated_tests": generated_testcases,
        "doc_summary": doc_summary, "final_summary": final_summary,
        "should_block_merge": should_block_merge, "severity_level": severity_level,
        "overall_score": score,
    }


if __name__ == "__main__":
    import asyncio
    result = asyncio.run(run_pipeline(
        pr_title="Add user login feature",
        pr_code="def login(u,p):\n    q = \"SELECT * FROM users WHERE u='\"+u+\"'\"\n    return db.execute(q)",
        filename="auth.py",
        pr_url="https://github.com"
    ))
    print(result["final_summary"])
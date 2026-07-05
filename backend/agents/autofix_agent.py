import json
from typing import AsyncGenerator
from google.adk.agents import LlmAgent, BaseAgent
from google.adk.workflow import RetryConfig
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from config import MODEL_NAME
from schemas import AutoFixOutput

_autofix_llm = LlmAgent(
    name="AutoFixLLM",
    model=MODEL_NAME,
    instruction="""You are a senior systems developer and automation engineer.
    Review the code provided alongside the specific security flaws and structural issues listed.
    Refactor the source code completely to repair all defects, preserving original intended
    features and using language-idiomatic safety structures.

    Original code:
    {pr_code}

    Issues found: {review_result}
    Vulnerabilities found: {security_result}""",
    description="Generates a fixed version of the code based on found issues and vulnerabilities.",
    output_schema=AutoFixOutput,
    output_key="autofix_result",
    retry_config=RetryConfig(max_attempts=3, backoff_factor=2.0, jitter=0.5)
)


def _safe_parse(raw, default):
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return default


class AutoFixAgent(BaseAgent):
    """Only invokes the AutoFix LLM if Review or Security actually found something."""

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        review_data = _safe_parse(state.get("review_result"), {})
        security_data = _safe_parse(state.get("security_result"), {})

        issues = review_data.get("issues", [])
        vulns = security_data.get("vulnerabilities", [])

        if issues or vulns:
            async for event in _autofix_llm.run_async(ctx):
                yield event
        else:
            ctx.session.state["autofix_result"] = json.dumps({
                "fixed_code": None,
                "changes_made": [],
                "explanation": "No issues or vulnerabilities found — no fix needed."
            })


autofix_agent = AutoFixAgent(name="AutoFixAgent")
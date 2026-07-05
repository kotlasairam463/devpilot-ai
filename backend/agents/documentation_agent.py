from google.adk.agents import LlmAgent
from google.adk.workflow import RetryConfig
from config import MODEL_NAME
from schemas import DocumentationOutput

documentation_agent = LlmAgent(
    name="DocumentationAgent",
    model=MODEL_NAME,
    instruction="""You are a senior technical writer producing documentation summaries for a
    code review dashboard, read by both engineers and non-technical stakeholders.

    Write a 5-6 sentence plain-English summary covering:
    1. What the code does (core purpose, one sentence)
    2. Key inputs/outputs
    3. External systems or side effects touched (DB, network, filesystem)
    4. Notable logic or edge cases
    5. What a future maintainer should be cautious about

    Filename: {filename}
    Fixed code result: {autofix_result}
    Original code: {pr_code}
    (Document the fixed code if present, otherwise the original.)""",
    description="Produces a plain-English summary of the code for dashboard and PR-comment readers.",
    output_schema=DocumentationOutput,
    output_key="doc_summary",
    retry_config=RetryConfig(max_attempts=3, backoff_factor=2.0, jitter=0.5)
)
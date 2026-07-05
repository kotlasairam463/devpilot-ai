from google.adk.agents import LlmAgent
from google.adk.workflow import RetryConfig
from config import MODEL_NAME
from schemas import ReviewOutput

review_agent = LlmAgent(
    name="ReviewAgent",
    model=MODEL_NAME,
    instruction="""You are a senior software engineer performing a rigorous code review across
    multiple programming languages and frameworks.

    STEP 1 — LANGUAGE DETECTION:
    Detect the programming language from the filename extension and code syntax. Apply the
    idioms, style conventions, and best practices native to that specific language and its
    dominant ecosystem (e.g. PEP 8 for Python, Effective Go for Go, Airbnb style for JS/TS).

    STEP 2 — REVIEW DIMENSIONS:
    1. Correctness — logic errors, off-by-one bugs, incorrect edge-case handling
    2. Error handling — missing try/except, unhandled nulls, unchecked return values
    3. Readability — unclear naming, missing type hints/annotations, overly dense logic
    4. Maintainability — tight coupling, duplicated logic, magic numbers/strings
    5. Performance — obvious inefficiencies (unnecessary loops, N+1 patterns, blocking calls)
    6. Idiomatic style — whether the code "looks native" to its language and ecosystem

    STEP 3 — SCORING RUBRIC:
    9-10 production-ready · 7-8 minor issues only · 5-6 real gaps · 3-4 needs rework · 0-2 broken

    Filename: {filename}
    Code:
    {pr_code}""",
    description="Reviews code quality across languages and produces a score, issues, and suggestions.",
    output_schema=ReviewOutput,
    output_key="review_result",
    retry_config=RetryConfig(max_attempts=3, backoff_factor=2.0, jitter=0.5)
)
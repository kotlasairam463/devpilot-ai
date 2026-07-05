from google.adk.agents import LlmAgent
from google.adk.workflow import RetryConfig
from config import MODEL_NAME

testcase_agent = LlmAgent(
    name="TestCaseAgent",
    model=MODEL_NAME,
    instruction="""You are a senior, multi-language software test engineer.
    Detect the language from the filename extension and apply the exact idiom, testing
    conventions, and framework syntax native to that ecosystem.

    FRAMEWORK SELECTOR RULE:
    - Python: `pytest` (independent functions, native assert statements)
    - JavaScript / TypeScript: native `node:test` and `node:assert`
    - Go: native `testing` library (`func TestXxx(t *testing.T)`)
    - Rust: native `#[cfg(test)]`
    - Java: `JUnit 5`
    - C#: `xUnit`
    - Other: the most dominant, modern standard framework for that language.

    TESTING COVERAGE:
    1. Success scenarios with ideal inputs
    2. Structural boundaries — empty limits, zero arrays, null pointers, negative values
    3. Exception propagation on catastrophic fault inputs

    Filename: {filename}
    Fixed code result: {autofix_result}
    Original code: {pr_code}
    (Use the fixed code if fixed_code is present inside the fixed code result, otherwise the original.)

    STRICT OUTPUT FORMAT RULES:
    Return RAW executable test code only. No markdown backticks, no explanations, no summaries.""",
    description="Generates unit tests for the reviewed code.",
    output_key="generated_testcases",
    retry_config=RetryConfig(max_attempts=3, backoff_factor=2.0, jitter=0.5)
)
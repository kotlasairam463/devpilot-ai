from google.adk.agents import LlmAgent
from google.adk.workflow import RetryConfig
from config import MODEL_NAME
from schemas import SecurityOutput

security_agent = LlmAgent(
    name="SecurityAgent",
    model=MODEL_NAME,
    instruction="""You are an expert application security engineer performing a deep security
    audit on multi-language source code.

    STEP 1 — LANGUAGE-AWARE ANALYSIS:
    Detect the language and apply relevant secure coding standards (OWASP Top 10, CWE patterns,
    and language-specific pitfalls — e.g. pickle deserialization in Python, prototype pollution
    in JS, unsafe reflection in Java).

    STEP 2 — CHECK FOR:
    1. Injection — SQL, NoSQL, command, template injection via string concatenation
    2. Broken authentication/authorization — hardcoded credentials, weak session handling
    3. Sensitive data exposure — hardcoded API keys, secrets, passwords in source
    4. XSS / output encoding failures — unescaped user input rendered in HTML/JS
    5. Insecure deserialization — unsafe pickle/eval/exec on untrusted input
    6. Security misconfiguration — permissive CORS, debug mode enabled, verbose errors
    7. Known-vulnerable dependency patterns
    8. Insufficient input validation

    STEP 3 — SEVERITY:
    critical = directly exploitable, breach/RCE/auth-bypass · high = exploitable with effort
    medium = real weakness, needs specific conditions · low = best-practice violation only

    Code:
    {pr_code}

    If no vulnerabilities are found, return is_safe=true, risk_score=0, vulnerabilities=[].""",
    description="Scans code for security vulnerabilities using OWASP-style analysis.",
    output_schema=SecurityOutput,
    output_key="security_result",
    retry_config=RetryConfig(max_attempts=3, backoff_factor=2.0, jitter=0.5)
)